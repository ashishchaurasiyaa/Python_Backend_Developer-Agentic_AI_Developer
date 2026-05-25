"""
Django Channels Deep — Production Patterns
"""

# ==========================================================================
# 1. ASGI APPLICATION CONFIGURATION
# ==========================================================================

"""
# config/asgi.py

import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django_asgi_app = get_asgi_application()

# Import after Django setup
from chat.routing import websocket_urlpatterns
from users.middleware import JWTAuthMiddleware


application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': AllowedHostsOriginValidator(
        JWTAuthMiddleware(
            AuthMiddlewareStack(
                URLRouter(websocket_urlpatterns)
            )
        )
    ),
})
"""


# ==========================================================================
# 2. SETTINGS
# ==========================================================================

CHANNELS_SETTINGS = """
# settings.py

INSTALLED_APPS = ['daphne'] + INSTALLED_APPS + ['channels']

ASGI_APPLICATION = 'config.asgi.application'

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [
                ('redis-host', 6379),
            ],
            'capacity': 1500,      # max messages buffered per channel
            'expiry': 60,          # seconds
            'group_expiry': 86400, # 24h
        },
    },
}
"""


# ==========================================================================
# 3. ROUTING
# ==========================================================================

"""
# chat/routing.py

from django.urls import re_path
from . import consumers


websocket_urlpatterns = [
    re_path(r'ws/chat/(?P<room_name>\\w+)/$', consumers.ChatConsumer.as_asgi()),
    re_path(r'ws/notifications/$', consumers.NotificationConsumer.as_asgi()),
    re_path(r'ws/dashboard/$', consumers.DashboardConsumer.as_asgi()),
]
"""


# ==========================================================================
# 4. CHAT CONSUMER (full pattern)
# ==========================================================================

"""
# chat/consumers.py

import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Auth check
        user = self.scope.get('user')
        if not user or user.is_anonymous:
            await self.close(code=4001)   # custom close code
            return

        self.user = user
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'chat_{self.room_name}'

        # Verify user has access to room
        if not await self.user_can_join_room():
            await self.close(code=4003)
            return

        # Join room group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        await self.accept()

        # Announce presence
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_joined',
                'user': self.user.username,
            },
        )

        # Heartbeat task
        self._heartbeat_task = asyncio.create_task(self._heartbeat())

    async def disconnect(self, close_code):
        if hasattr(self, '_heartbeat_task'):
            self._heartbeat_task.cancel()

        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_left',
                    'user': self.user.username if hasattr(self, 'user') else 'unknown',
                },
            )

    async def receive(self, text_data=None, bytes_data=None):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({'error': 'invalid JSON'}))
            return

        action = data.get('action')

        if action == 'message':
            await self._handle_message(data.get('message', '')[:5000])  # cap length
        elif action == 'typing':
            await self._handle_typing()
        elif action == 'ping':
            await self.send(text_data=json.dumps({'type': 'pong'}))

    async def _handle_message(self, content):
        if not content.strip():
            return

        # Save to DB
        msg = await self.save_message(content)

        # Broadcast
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message_id': msg.id,
                'message': msg.content,
                'user': self.user.username,
                'timestamp': msg.created_at.isoformat(),
            },
        )

    async def _handle_typing(self):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_typing',
                'user': self.user.username,
            },
        )

    async def _heartbeat(self):
        while True:
            await asyncio.sleep(30)
            try:
                await self.send(text_data=json.dumps({'type': 'ping'}))
            except Exception:
                break

    # ==== Handlers for group events ====

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message',
            'id': event['message_id'],
            'message': event['message'],
            'user': event['user'],
            'timestamp': event['timestamp'],
        }))

    async def user_joined(self, event):
        await self.send(text_data=json.dumps({
            'type': 'user_joined',
            'user': event['user'],
        }))

    async def user_left(self, event):
        await self.send(text_data=json.dumps({
            'type': 'user_left',
            'user': event['user'],
        }))

    async def user_typing(self, event):
        if event['user'] != self.user.username:
            await self.send(text_data=json.dumps({
                'type': 'typing',
                'user': event['user'],
            }))

    # ==== DB helpers (sync-wrapped) ====

    @database_sync_to_async
    def user_can_join_room(self):
        from chat.models import Room
        try:
            room = Room.objects.get(name=self.room_name)
        except Room.DoesNotExist:
            return False
        return room.is_public or room.members.filter(pk=self.user.pk).exists()

    @database_sync_to_async
    def save_message(self, content):
        from chat.models import Message, Room
        room = Room.objects.get(name=self.room_name)
        return Message.objects.create(
            user=self.user,
            room=room,
            content=content,
        )
"""


# ==========================================================================
# 5. JWT AUTHENTICATION MIDDLEWARE
# ==========================================================================

"""
# users/middleware.py

from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser


@database_sync_to_async
def get_user_from_jwt(token):
    from rest_framework_simplejwt.tokens import AccessToken
    from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
    from django.contrib.auth import get_user_model

    User = get_user_model()
    try:
        access = AccessToken(token)
        user = User.objects.get(id=access['user_id'])
        return user
    except (TokenError, InvalidToken, User.DoesNotExist):
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    \"\"\"Auth from ?token=<jwt> query param.\"\"\"

    async def __call__(self, scope, receive, send):
        query_string = scope.get('query_string', b'').decode()
        query_params = parse_qs(query_string)
        token = query_params.get('token', [None])[0]

        if token:
            scope['user'] = await get_user_from_jwt(token)
        else:
            scope['user'] = AnonymousUser()

        return await super().__call__(scope, receive, send)
"""


# ==========================================================================
# 6. PER-USER NOTIFICATIONS CONSUMER
# ==========================================================================

"""
# notifications/consumers.py

import json
from channels.generic.websocket import AsyncWebsocketConsumer


class NotificationConsumer(AsyncWebsocketConsumer):
    \"\"\"Subscribe to personal notifications.\"\"\"

    async def connect(self):
        user = self.scope.get('user')
        if not user or user.is_anonymous:
            await self.close(code=4001)
            return

        self.user = user
        self.group_name = f'user_{user.id}'

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def notification(self, event):
        \"\"\"Handler for 'notification' type events.\"\"\"
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'data': event['data'],
        }))


# To trigger from anywhere (signal handler, Celery task, view):
def send_notification_to_user(user_id, data):
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'user_{user_id}',
        {
            'type': 'notification',
            'data': data,
        },
    )


# Example: notify on new comment
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender='blog.Comment')
def notify_article_author(sender, instance, created, **kwargs):
    if created:
        article_author_id = instance.article.author_id
        send_notification_to_user(
            article_author_id,
            {'message': f'New comment on {instance.article.title}'},
        )
"""


# ==========================================================================
# 7. DASHBOARD CONSUMER (broadcast metrics)
# ==========================================================================

"""
class DashboardConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get('user')
        if not user or not user.is_staff:
            await self.close()
            return

        await self.channel_layer.group_add('dashboard', self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard('dashboard', self.channel_name)

    async def metric_update(self, event):
        await self.send(text_data=json.dumps(event['data']))


# Background task pushes metrics
# tasks.py (Celery)
from celery import shared_task


@shared_task
def push_dashboard_metrics():
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync

    metrics = compute_metrics()  # your aggregation
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        'dashboard',
        {
            'type': 'metric_update',
            'data': metrics,
        },
    )


# In Celery beat schedule:
# CELERY_BEAT_SCHEDULE = {
#     'dashboard-metrics': {
#         'task': 'tasks.push_dashboard_metrics',
#         'schedule': 5.0,   # every 5 seconds
#     },
# }
"""


# ==========================================================================
# 8. DEPLOY (Docker + nginx)
# ==========================================================================

DOCKER_DEPLOY = """
# Dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD daphne -b 0.0.0.0 -p 8000 config.asgi:application


# Or with uvicorn
# CMD uvicorn config.asgi:application --host 0.0.0.0 --port 8000 --workers 4


# docker-compose.yml
services:
  web:
    build: .
    depends_on: [redis, postgres]
    environment:
      REDIS_URL: redis://redis:6379/0
    deploy:
      replicas: 3
  nginx:
    image: nginx:alpine
    ports: ["80:80"]
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
  redis:
    image: redis:7-alpine
  postgres:
    image: postgres:16
"""


NGINX_CONF = """
# nginx.conf

upstream channels_backend {
    server web:8000;
}

server {
    listen 80;

    location / {
        proxy_pass http://channels_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /ws/ {
        proxy_pass http://channels_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;   # 24h for long-lived
        proxy_send_timeout 86400;
    }
}
"""


# ==========================================================================
# 9. CLIENT (JavaScript)
# ==========================================================================

JS_CLIENT = """
// React/vanilla JS client

const token = getJWT();
const ws = new WebSocket(`wss://api.example.com/ws/chat/general/?token=${token}`);

ws.onopen = () => {
    console.log('Connected');
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);

    if (data.type === 'message') {
        appendMessage(data);
    } else if (data.type === 'user_joined') {
        showUserJoined(data.user);
    } else if (data.type === 'ping') {
        // Server health ping — optionally respond
    }
};

ws.onerror = (error) => {
    console.error('WS error:', error);
};

ws.onclose = (event) => {
    if (event.code === 4001) {
        alert('Authentication required');
    } else if (event.code === 4003) {
        alert('Access denied');
    } else {
        // Reconnect with backoff
        setTimeout(reconnect, 5000);
    }
};

function sendMessage(text) {
    ws.send(JSON.stringify({
        action: 'message',
        message: text,
    }));
}
"""


# ==========================================================================
# 10. TESTING CHANNELS
# ==========================================================================

"""
# tests/test_consumers.py

import pytest
from channels.testing import WebsocketCommunicator
from config.asgi import application


@pytest.mark.asyncio
async def test_chat_consumer():
    communicator = WebsocketCommunicator(application, '/ws/chat/test_room/?token=valid-jwt')
    connected, _ = await communicator.connect()
    assert connected

    # Send message
    await communicator.send_json_to({'action': 'message', 'message': 'Hello'})

    # Receive broadcast
    response = await communicator.receive_json_from()
    assert response['type'] == 'message'
    assert response['message'] == 'Hello'

    await communicator.disconnect()
"""
