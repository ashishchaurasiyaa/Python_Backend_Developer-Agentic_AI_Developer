# Django Channels Deep — WebSockets, Groups, Layers

## Why It Matters

Django Channels adds WebSocket / async support beyond HTTP. Real-time apps:
- **Chat / collaboration** → bidirectional messages
- **Live dashboards** → server pushes updates
- **Notifications** → real-time alerts
- **Multiplayer games** → game state sync

vs SSE: bidirectional, lower latency, but more complex.

Senior interview: "Chat system with 10k concurrent connections — design?" → Channels + Redis channel layer + horizontal scaling.

---

## Core Concepts

### Setup

```python
# pip install channels channels-redis
INSTALLED_APPS = ['daphne', 'channels', ...]   # daphne FIRST


# settings.py
ASGI_APPLICATION = 'config.asgi.application'

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [('redis', 6379)],
        },
    },
}
```

### ASGI Routing

```python
# config/asgi.py
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from chat import routing


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django_asgi_app = get_asgi_application()


application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': AuthMiddlewareStack(
        URLRouter(routing.websocket_urlpatterns)
    ),
})
```

### URL Routing

```python
# chat/routing.py
from django.urls import re_path
from . import consumers


websocket_urlpatterns = [
    re_path(r'ws/chat/(?P<room_name>\w+)/$', consumers.ChatConsumer.as_asgi()),
    re_path(r'ws/notifications/$', consumers.NotificationConsumer.as_asgi()),
]
```

### Async Consumer (Basic)

```python
# chat/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'chat_{self.room_name}'

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name,
        )

        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name,
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data['message']

        # Broadcast to room
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',   # → calls self.chat_message
                'message': message,
                'user': self.scope['user'].username if self.scope['user'].is_authenticated else 'Anon',
            }
        )

    # Handler for type='chat_message'
    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'user': event['user'],
        }))
```

### Authentication in WebSocket

```python
async def connect(self):
    user = self.scope.get('user')
    if not user or user.is_anonymous:
        await self.close()
        return

    self.user = user
    await self.accept()
```

### Channels with JWT (custom middleware)

```python
# auth.py
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from urllib.parse import parse_qs


@database_sync_to_async
def get_user(token):
    from rest_framework_simplejwt.tokens import AccessToken
    from django.contrib.auth import get_user_model
    User = get_user_model()
    try:
        access = AccessToken(token)
        return User.objects.get(id=access['user_id'])
    except Exception:
        from django.contrib.auth.models import AnonymousUser
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        query = parse_qs(scope['query_string'].decode())
        token = query.get('token', [None])[0]
        scope['user'] = await get_user(token) if token else AnonymousUser()
        return await super().__call__(scope, receive, send)


# asgi.py
application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': JWTAuthMiddleware(URLRouter(...)),
})


# Client connects: ws://example.com/ws/chat/room1/?token=<jwt>
```

### Channel Layer Operations

```python
# In consumer
await self.channel_layer.group_add(group_name, self.channel_name)
await self.channel_layer.group_discard(group_name, self.channel_name)

# Send to specific channel
await self.channel_layer.send(channel_name, {'type': 'event_type', 'data': ...})

# Send to all in group
await self.channel_layer.group_send(group_name, {'type': 'event_type', 'data': ...})
```

### Sending from Django Views (push to clients)

```python
# views.py
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


def send_notification(request, user_id):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'user_{user_id}',
        {
            'type': 'notification',
            'message': 'You have a new message',
        }
    )
    return JsonResponse({'sent': True})
```

### Database Access in Consumers

```python
from channels.db import database_sync_to_async


class ChatConsumer(AsyncWebsocketConsumer):
    @database_sync_to_async
    def save_message(self, content):
        from chat.models import Message
        return Message.objects.create(
            user=self.scope['user'],
            content=content,
            room=self.room,
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        msg = await self.save_message(data['message'])
        # ... broadcast
```

### Per-User Channel (private notifications)

```python
class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope['user']
        if user.is_anonymous:
            await self.close()
            return

        self.group_name = f'user_{user.id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def notification(self, event):
        await self.send(text_data=json.dumps(event['data']))


# Trigger from anywhere:
async_to_sync(channel_layer.group_send)(
    f'user_{user.id}',
    {'type': 'notification', 'data': {'msg': 'New comment on your post'}},
)
```

### Scaling Horizontally

```
[Client]  ←→  [Daphne 1]  ←→ ┐
[Client]  ←→  [Daphne 2]  ←→ ├→ Redis (channel layer)
[Client]  ←→  [Daphne 3]  ←→ ┘
```

Each Daphne handles ~10k connections. Redis backs channel layer → messages forwarded between instances.

### Deployment

```bash
# daphne
daphne -b 0.0.0.0 -p 8000 config.asgi:application


# uvicorn (alternative)
uvicorn config.asgi:application --host 0.0.0.0 --port 8000 --workers 4


# Behind nginx with WS upgrade
location /ws/ {
    proxy_pass http://app:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "Upgrade";
    proxy_set_header Host $host;
    proxy_read_timeout 86400;
}
```

### Connection Limits

```python
# settings.py
ASGI_THREADS = 32   # async threadpool size


# channels-redis tuning
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [('redis', 6379)],
            'capacity': 1500,     # max messages per channel before discard
            'expiry': 60,         # message TTL in queue
            'group_expiry': 86400,
        },
    },
}
```

### Heartbeat (Connection Health)

```python
class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        asyncio.create_task(self._heartbeat())

    async def _heartbeat(self):
        while True:
            try:
                await self.send(text_data=json.dumps({'type': 'ping'}))
                await asyncio.sleep(30)
            except Exception:
                break
```

---

## Common Pitfalls

### 1. Sync ORM in Async Consumer

```python
async def receive(self, text_data):
    Message.objects.create(...)   # blocks event loop
```

Wrap with `database_sync_to_async`.

### 2. No Auth Check on Connect

```python
async def connect(self):
    await self.accept()   # anyone can connect
```

Always check scope['user']; close if anonymous (where appropriate).

### 3. Channel Layer = In-Memory (Dev Only)

```python
CHANNEL_LAYERS = {
    'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'},
}
```

Doesn't scale beyond single process. Use Redis in prod.

### 4. Group Names Too Specific

```python
group_name = f'chat_{room_id}_{user_id}_{timestamp}'
```

Channels has 100-char limit on group names. Keep short.

### 5. Sending Large Messages

WS frame max ~1MB. For large data: split or use HTTP fetch. Channel layer also has size limits.

### 6. Not Cleaning Up on Disconnect

```python
async def disconnect(self, close_code):
    pass   # group still includes this dead channel
```

Always `group_discard`.

### 7. No Origin Check

WS doesn't have CORS by default → CSRF-like vulnerability. Use AllowedHostsOriginValidator:

```python
from channels.security.websocket import AllowedHostsOriginValidator


application = ProtocolTypeRouter({
    'websocket': AllowedHostsOriginValidator(
        AuthMiddlewareStack(URLRouter(...))
    ),
})
```

---

## Interview Q&A

**Q1:** Django Channels architecture?
**A:** ASGI app (vs WSGI). Daphne/Uvicorn serves async. Consumers = async classes handling WS connections. Channel layer (Redis) = inter-process messaging. Groups = pub/sub for broadcasting. Routing maps URL patterns to consumers.

**Q2:** Chat 10k concurrent connections — design?
**A:** Multiple Daphne instances (each ~10k conns). Redis channel layer for cross-instance messaging. Room = group. User joins group on connect, broadcasts via group_send. Persistence: save messages to DB via database_sync_to_async. Load balancer with sticky sessions optional (not strictly needed since channels in Redis).

**Q3:** WS authentication?
**A:** Default AuthMiddlewareStack reads session cookie. For JWT: custom middleware reads token from query param / header, validates, attaches user to scope. Cookie-based auth works for browser; JWT for SPAs/mobile.

**Q4:** group_send vs send?
**A:** `send` (`channel_layer.send`) → specific channel (one consumer instance). `group_send` → all channels in group. Most chat/notifications use groups. Direct `send` rare — when you have specific channel_name handy.

**Q5:** Database access async consumer mein?
**A:** Django ORM is sync. Wrap with `@database_sync_to_async` decorator or `database_sync_to_async(func)(*args)`. Runs in threadpool. Django 5+ has async ORM (`aget`, `acreate`) — even better.

**Q6:** Channels horizontal scale kaise?
**A:** Multiple ASGI workers (Daphne/Uvicorn instances). Each handles fraction of connections. Redis channel layer routes group_send across all instances. Load balancer with WebSocket support (nginx with Upgrade header). No sticky sessions needed.

**Q7:** Heartbeat zaroori hai?
**A:** Idle connections may be dropped by intermediate proxies. Periodic ping (every 30s) keeps alive + detects dead clients. Client should also send pong. WebSocket protocol has native ping/pong frames (handled by lower layer in Daphne).

**Q8:** Channels vs FastAPI WebSocket?
**A:** Channels: full Django integration (auth, ORM, sessions, signals). FastAPI: lighter, async-native, faster for pure WS. For Django app: Channels. For new async-first WS-heavy app: FastAPI. Both can scale via similar patterns (Redis pub/sub).

---

## Real-World Use Cases

### 1. Real-Time Chat

Room = group. Each user joins room group. Messages broadcasted via group_send. Persisted to DB. Pagination for history via REST.

### 2. Live Dashboard Updates

Background task (Celery) computes metrics, then sends to dashboard group:

```python
from channels.layers import get_channel_layer

def update_dashboard(metric):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        'dashboard',
        {'type': 'metric_update', 'data': metric},
    )
```

### 3. Notifications

Per-user group. Backend sends to `user_{id}` group on event. Client subscribes on login.

### 4. Collaborative Editing

Document = group. Each edit broadcasted. Conflict resolution via CRDTs or operational transform.

---

## References

- [Channels docs](https://channels.readthedocs.io/)
- [Channels tutorial](https://channels.readthedocs.io/en/stable/tutorial/)
- [channels-redis](https://github.com/django/channels_redis)
- "Real-time Web with Django Channels" — book
