# Django Channels, Middleware, Management Commands

## Quick Concepts
- **Django Channels** = Django mein WebSocket support — ASGI based
- **Channel Layer** = channels ke beech message pass karna (Redis backend)
- **Consumer** = WebSocket handler (views jaisa)
- **Middleware** = har request se pehle/baad process karo
- **Management Commands** = custom `manage.py` commands

---

## Interview Questions & Answers

### Q1: Django Channels se real-time chat kaise banate hain?
**Answer:**
```bash
pip install channels channels-redis
```

```python
# settings.py
INSTALLED_APPS = ["channels", ...]

ASGI_APPLICATION = "myproject.asgi.application"

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [("redis", 6379)]},
    }
}

# asgi.py
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from chat.routing import websocket_urlpatterns

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})

# chat/routing.py
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/chat/(?P<room_name>\w+)/$", consumers.ChatConsumer.as_asgi()),
]

# chat/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope["url_route"]["kwargs"]["room_name"]
        self.room_group_name = f"chat_{self.room_name}"
        self.user = self.scope["user"]

        if not self.user.is_authenticated:
            await self.close(code=4001)
            return

        # Room group mein join karo
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

        # Join message broadcast karo
        await self.channel_layer.group_send(
            self.room_group_name,
            {"type": "user_join", "user": self.user.username}
        )

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data["message"]

        # DB mein save karo
        await self.save_message(message)

        # Group ko broadcast karo
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "message": message,
                "username": self.user.username,
            }
        )

    # Group message handler
    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            "type": "message",
            "message": event["message"],
            "username": event["username"],
        }))

    async def user_join(self, event):
        await self.send(text_data=json.dumps({
            "type": "join",
            "user": event["user"],
        }))

    @database_sync_to_async
    def save_message(self, message: str):
        from .models import Message
        Message.objects.create(
            room=self.room_name,
            user=self.user,
            content=message
        )
```

---

### Q2: Django Custom Middleware kaise likhte hain?
**Answer:**
```python
# middleware.py
import time
import uuid
import structlog
from django.http import JsonResponse

log = structlog.get_logger()

class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = str(uuid.uuid4())
        request.request_id = request_id
        start = time.perf_counter()

        log.info(
            "request_started",
            request_id=request_id,
            method=request.method,
            path=request.path,
            user_id=getattr(request.user, "id", None),
        )

        response = self.get_response(request)
        duration_ms = (time.perf_counter() - start) * 1000

        log.info(
            "request_finished",
            request_id=request_id,
            status=response.status_code,
            duration_ms=round(duration_ms, 2),
        )

        response["X-Request-ID"] = request_id
        return response

class MaintenanceModeMiddleware:
    EXCLUDED_PATHS = ["/admin/", "/health/"]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.conf import settings
        if (
            getattr(settings, "MAINTENANCE_MODE", False)
            and not any(request.path.startswith(p) for p in self.EXCLUDED_PATHS)
        ):
            return JsonResponse(
                {"error": "Service temporarily unavailable"},
                status=503
            )
        return self.get_response(request)

# settings.py mein add karo
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "myapp.middleware.RequestLoggingMiddleware",
    "myapp.middleware.MaintenanceModeMiddleware",
    ...
]
```

---

### Q3: Custom Management Commands kaise banate hain?
**Answer:**
```python
# management/commands/sync_users.py
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

class Command(BaseCommand):
    help = "Sync users from external API"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Don't save to DB")
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--source", choices=["api", "csv"], default="api")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        limit = options["limit"]

        self.stdout.write(f"Starting sync (dry_run={dry_run}, limit={limit})")

        try:
            users = self.fetch_users(options["source"], limit)
            created, updated, skipped = 0, 0, 0

            with transaction.atomic():
                for user_data in users:
                    obj, was_created = User.objects.update_or_create(
                        email=user_data["email"],
                        defaults={"name": user_data["name"]}
                    )
                    if was_created:
                        created += 1
                    else:
                        updated += 1

                if dry_run:
                    transaction.set_rollback(True)

        except Exception as e:
            raise CommandError(f"Sync failed: {e}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Done: {created} created, {updated} updated, {skipped} skipped"
            )
        )

# Run karo
# python manage.py sync_users --dry-run --limit=50
# python manage.py sync_users --source=csv
```

---

### Q4: Django mein Custom Authentication Backend kaise banate hain?
**Answer:**
```python
# backends.py
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth import get_user_model

User = get_user_model()

class EmailBackend(BaseBackend):
    """Email se login allow karo (default is username)"""

    def authenticate(self, request, email=None, password=None, **kwargs):
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return None

        if user.check_password(password) and user.is_active:
            return user
        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None

class OTPBackend(BaseBackend):
    """OTP se login karo"""

    def authenticate(self, request, phone=None, otp=None, **kwargs):
        try:
            user = User.objects.get(phone=phone)
            if self.verify_otp(phone, otp):
                return user
        except User.DoesNotExist:
            pass
        return None

    def verify_otp(self, phone: str, otp: str) -> bool:
        from django.core.cache import cache
        stored_otp = cache.get(f"otp:{phone}")
        return stored_otp == otp

# settings.py
AUTHENTICATION_BACKENDS = [
    "myapp.backends.EmailBackend",
    "myapp.backends.OTPBackend",
    "django.contrib.auth.backends.ModelBackend",  # fallback
]
```
