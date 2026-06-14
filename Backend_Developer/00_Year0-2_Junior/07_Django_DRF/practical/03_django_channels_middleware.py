"""
Django Channels, Custom Middleware, Management Commands, and Auth Backends
— Production Patterns

Topics covered (grounded in 03_django_channels_middleware.md):
  1. ASGI application wiring  — ProtocolTypeRouter, URLRouter
  2. AsyncWebsocketConsumer   — connect / disconnect / receive / broadcast
  3. Channel-layer group API  — group_add / group_send / group_discard
  4. Request logging middleware — UUID request-id, structured timing
  5. Maintenance-mode middleware — admin/health path exclusions
  6. Custom management command  — update_or_create, dry-run, atomic
  7. Email-based auth backend  — override authenticate / get_user
  8. OTP-based auth backend    — cache-backed one-time-password verify
  9. Standalone demo           — middleware chain simulation (no Django infra)

All code is importable as library modules.
The __main__ block at the bottom runs without any Django or Redis infrastructure.

pip install channels channels-redis django
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Tuple

# ==========================================================================
# LOGGING (stdlib — no external dep)
# ==========================================================================

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
log = logging.getLogger("django_channels_practical")


# ==========================================================================
# 1. ASGI APPLICATION WIRING
# ==========================================================================
# pip install channels channels-redis

ASGI_WIRING_EXAMPLE = '''
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
'''

ROUTING_EXAMPLE = '''
# chat/routing.py
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/chat/(?P<room_name>\\w+)/$", consumers.ChatConsumer.as_asgi()),
]
'''

SETTINGS_CHANNELS_EXAMPLE = '''
# settings.py
INSTALLED_APPS = ["channels", "chat", ...]
ASGI_APPLICATION = "myproject.asgi.application"

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [("redis", 6379)]},
    }
}
'''


# ==========================================================================
# 2. ASYNC WEBSOCKET CONSUMER — real-time chat room
# ==========================================================================
# pip install channels

class ChatConsumerStub:
    """
    Stand-alone stub that documents every lifecycle method and the
    channel-layer group API.

    In production, inherit from channels.generic.websocket.AsyncWebsocketConsumer
    and remove the stub scaffolding.

    Production usage:
        from channels.generic.websocket import AsyncWebsocketConsumer
        class ChatConsumer(AsyncWebsocketConsumer): ...
    """

    # ------------------------------------------------------------------
    # Lifecycle — called by Channels automatically
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """
        Called when the WebSocket handshake is initiated.

        Steps:
          1. Extract room name from the URL route.
          2. Reject unauthenticated users with close code 4001.
          3. Join the Redis channel-layer group for that room.
          4. Accept the handshake.
          5. Broadcast a join notification to all room members.
        """
        self.room_name: str = self.scope["url_route"]["kwargs"]["room_name"]
        self.room_group_name: str = f"chat_{self.room_name}"
        self.user = self.scope["user"]

        if not self.user.is_authenticated:
            # Close before accept — client receives 4001
            await self.close(code=4001)
            return

        # Join the channel-layer group so we receive group_send messages
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name,
        )
        await self.accept()

        # Notify all members that a new user has joined
        await self.channel_layer.group_send(
            self.room_group_name,
            {"type": "user_join", "user": self.user.username},
        )

    async def disconnect(self, close_code: int) -> None:
        """
        Called when the WebSocket closes (client disconnect, server shutdown,
        network failure, or explicit close()).

        Always clean up the channel-layer group membership to avoid
        memory leaks inside the Redis layer.
        """
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name,
        )

    async def receive(self, text_data: str) -> None:
        """
        Called when a text frame arrives from the client.

        Flow:
          1. Deserialise the JSON payload.
          2. Persist the message to the database (via database_sync_to_async).
          3. Fan-out the message to every member in the room group.
        """
        data: Dict[str, Any] = json.loads(text_data)
        message: str = data["message"]

        # Persist asynchronously — wraps a synchronous ORM call
        await self.save_message(message)

        # Broadcast to every consumer subscribed to this group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",       # maps to the handler below
                "message": message,
                "username": self.user.username,
            },
        )

    # ------------------------------------------------------------------
    # Group-message handlers — invoked by Channels when group_send fires
    # ------------------------------------------------------------------

    async def chat_message(self, event: Dict[str, Any]) -> None:
        """
        Receive a chat_message event from the channel layer and push the
        payload down to the individual WebSocket client.
        """
        await self.send(
            text_data=json.dumps(
                {
                    "type": "message",
                    "message": event["message"],
                    "username": event["username"],
                }
            )
        )

    async def user_join(self, event: Dict[str, Any]) -> None:
        """Push a join notification to the client."""
        await self.send(
            text_data=json.dumps(
                {"type": "join", "user": event["user"]}
            )
        )

    # ------------------------------------------------------------------
    # Database helper
    # ------------------------------------------------------------------

    # In production annotate with @database_sync_to_async from channels.db
    def save_message(self, message: str) -> None:
        """
        Synchronous ORM write, wrapped with database_sync_to_async so it
        executes in Django's thread pool rather than blocking the event loop.

        Production:
            from channels.db import database_sync_to_async
            @database_sync_to_async
            def save_message(self, message: str) -> None:
                from .models import Message
                Message.objects.create(
                    room=self.room_name,
                    user=self.user,
                    content=message,
                )
        """
        log.debug("save_message room=%s message=%.40s", self.room_name, message)

    # ------------------------------------------------------------------
    # Stub wiring — not present in a real consumer
    # ------------------------------------------------------------------

    def __init__(self) -> None:
        # Minimal scope mock for demonstration
        self.scope: Dict[str, Any] = {
            "url_route": {"kwargs": {"room_name": "general"}},
            "user": type(
                "User",
                (),
                {"is_authenticated": True, "username": "alice"},
            )(),
        }
        self.channel_name: str = "specific.abc123"
        self.channel_layer: _InMemoryChannelLayerStub = _InMemoryChannelLayerStub()


class _InMemoryChannelLayerStub:
    """
    Minimal in-memory stand-in for channels_redis.core.RedisChannelLayer.

    Demonstrates the group_add / group_send / group_discard API surface
    without requiring a running Redis instance.
    """

    def __init__(self) -> None:
        self._groups: Dict[str, List[str]] = {}
        self._sent: List[Dict[str, Any]] = []

    async def group_add(self, group: str, channel: str) -> None:
        self._groups.setdefault(group, []).append(channel)
        log.debug("group_add  group=%s channel=%s", group, channel)

    async def group_discard(self, group: str, channel: str) -> None:
        members = self._groups.get(group, [])
        if channel in members:
            members.remove(channel)
        log.debug("group_discard  group=%s channel=%s", group, channel)

    async def group_send(self, group: str, message: Dict[str, Any]) -> None:
        self._sent.append({"group": group, "message": message})
        log.debug("group_send  group=%s type=%s", group, message.get("type"))

    async def send(self, channel: str, message: Dict[str, Any]) -> None:
        log.debug("send  channel=%s type=%s", channel, message.get("type"))

    # close is a no-op in the stub
    async def close(self) -> None:
        pass


# ==========================================================================
# 3. DJANGO SYNC (WSGI) MIDDLEWARE
# ==========================================================================

# --------------------------------------------------------------------------
# 3a. Request logging middleware
# --------------------------------------------------------------------------

class RequestLoggingMiddleware:
    """
    Assigns a UUID request-id to every HTTP request, logs entry/exit with
    timing, and injects the id into the response as an X-Request-ID header.

    MIDDLEWARE registration order matters — place this early so all
    downstream middleware and views are covered by the timing window.

    settings.py:
        MIDDLEWARE = [
            "django.middleware.security.SecurityMiddleware",
            "myapp.middleware.RequestLoggingMiddleware",
            ...
        ]
    """

    def __init__(self, get_response: Callable) -> None:
        # Called once at server startup — perform any one-time setup here.
        self.get_response = get_response

    def __call__(self, request: Any) -> Any:
        request_id = str(uuid.uuid4())
        # Attach to the request object so views/serializers can reference it
        request.request_id = request_id
        start = time.perf_counter()

        log.info(
            "request_started  request_id=%s  method=%s  path=%s  user_id=%s",
            request_id,
            getattr(request, "method", "UNKNOWN"),
            getattr(request, "path", "/"),
            getattr(getattr(request, "user", None), "id", None),
        )

        response = self.get_response(request)

        duration_ms = (time.perf_counter() - start) * 1000
        log.info(
            "request_finished  request_id=%s  status=%s  duration_ms=%.2f",
            request_id,
            getattr(response, "status_code", "?"),
            duration_ms,
        )

        # Surface the id in the response so clients/load-balancers can correlate logs
        response["X-Request-ID"] = request_id
        return response


# --------------------------------------------------------------------------
# 3b. Maintenance-mode middleware
# --------------------------------------------------------------------------

class MaintenanceModeMiddleware:
    """
    Returns 503 for all requests while MAINTENANCE_MODE = True in settings,
    but excludes the Django admin and a /health/ endpoint so ops teams
    can check server status and disable maintenance mode without downtime.

    settings.py:
        MAINTENANCE_MODE = True   # toggle via env var / feature flag
    """

    EXCLUDED_PATHS: List[str] = ["/admin/", "/health/"]

    def __init__(self, get_response: Callable) -> None:
        self.get_response = get_response

    def __call__(self, request: Any) -> Any:
        # Late import avoids circular-import issues at module load time
        try:
            from django.conf import settings as django_settings
            maintenance = getattr(django_settings, "MAINTENANCE_MODE", False)
        except Exception:
            maintenance = False

        path: str = getattr(request, "path", "/")
        in_excluded = any(path.startswith(p) for p in self.EXCLUDED_PATHS)

        if maintenance and not in_excluded:
            # Return a minimal JsonResponse — avoids importing Django here
            body = json.dumps({"error": "Service temporarily unavailable"}).encode()
            response = _MockResponse(body=body, status_code=503)
            response["Content-Type"] = "application/json"
            return response

        return self.get_response(request)


# ==========================================================================
# 4. CUSTOM MANAGEMENT COMMAND
# ==========================================================================

class SyncUsersCommand:
    """
    Mirrors the production management command at
    myapp/management/commands/sync_users.py.

    Usage:
        python manage.py sync_users --dry-run --limit=50
        python manage.py sync_users --source=csv

    In production inherit from django.core.management.base.BaseCommand and
    implement add_arguments + handle. This class illustrates the same logic
    in a plain Python class so it compiles without Django.
    """

    help: str = "Sync users from an external API or CSV file"

    # ------------------------------------------------------------------
    # Argument specification (mirrors add_arguments)
    # ------------------------------------------------------------------

    ARGUMENT_SPEC: List[Dict[str, Any]] = [
        {"name": "--dry-run",  "action": "store_true", "help": "Preview changes without writing to the DB"},
        {"name": "--limit",    "type": int,            "default": 100,   "help": "Maximum records to process"},
        {"name": "--source",   "choices": ["api", "csv"], "default": "api", "help": "Data source"},
    ]

    # ------------------------------------------------------------------
    # Core logic (mirrors handle)
    # ------------------------------------------------------------------

    def handle(
        self,
        dry_run: bool = False,
        limit: int = 100,
        source: str = "api",
    ) -> None:
        """
        1. Fetch users from the chosen source.
        2. Upsert each record inside a single DB transaction.
        3. Roll back the transaction when --dry-run is active.
        4. Report counts to stdout.
        """
        log.info("Starting sync  dry_run=%s  limit=%d  source=%s", dry_run, limit, source)

        try:
            users = self._fetch_users(source=source, limit=limit)
            created, updated, skipped = self._upsert_users(
                users=users, dry_run=dry_run
            )
        except Exception as exc:
            raise RuntimeError(f"Sync failed: {exc}") from exc

        status = "DRY-RUN — no changes persisted" if dry_run else "committed"
        log.info(
            "Sync complete (%s)  created=%d  updated=%d  skipped=%d",
            status,
            created,
            updated,
            skipped,
        )

    def _fetch_users(
        self, source: str, limit: int
    ) -> List[Dict[str, str]]:
        """
        Returns a list of user dicts.  In production, call an external REST
        API or parse a CSV file.  Here we return synthetic fixtures.
        """
        fake_users: List[Dict[str, str]] = [
            {"email": f"user{i}@example.com", "name": f"User {i}"}
            for i in range(1, min(limit + 1, 6))
        ]
        log.debug("_fetch_users  source=%s  count=%d", source, len(fake_users))
        return fake_users

    def _upsert_users(
        self,
        users: List[Dict[str, str]],
        dry_run: bool,
    ) -> Tuple[int, int, int]:
        """
        Performs update_or_create for each record inside an atomic block.

        In production replace the in-memory dict store with:
            with transaction.atomic():
                for user_data in users:
                    obj, was_created = User.objects.update_or_create(
                        email=user_data["email"],
                        defaults={"name": user_data["name"]},
                    )
                    ...
                if dry_run:
                    transaction.set_rollback(True)
        """
        # In-memory store simulates the DB for the standalone demo
        _db: Dict[str, str] = {}
        created = updated = skipped = 0

        for user_data in users:
            email = user_data["email"]
            if email in _db:
                _db[email] = user_data["name"]
                updated += 1
            else:
                _db[email] = user_data["name"]
                created += 1

        if dry_run:
            # Simulate transaction.set_rollback(True) by discarding the dict
            _db.clear()
            log.debug("Dry-run: all changes discarded")

        return created, updated, skipped


# ==========================================================================
# 5. CUSTOM AUTHENTICATION BACKENDS
# ==========================================================================

class EmailAuthBackend:
    """
    Allows users to log in with their email address instead of a username.

    settings.py:
        AUTHENTICATION_BACKENDS = [
            "myapp.backends.EmailAuthBackend",
            "django.contrib.auth.backends.ModelBackend",  # username fallback
        ]

    Production implementation:
        from django.contrib.auth.backends import BaseBackend
        from django.contrib.auth import get_user_model
        User = get_user_model()

        class EmailAuthBackend(BaseBackend):
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
    """

    # Simulated user store for the standalone demo
    _USERS: Dict[str, Dict[str, Any]] = {
        "alice@example.com": {"id": 1, "password_hash": "hashed_abc", "is_active": True},
        "bob@example.com":   {"id": 2, "password_hash": "hashed_xyz", "is_active": False},
    }

    def authenticate(
        self,
        request: Optional[Any],
        email: Optional[str] = None,
        password: Optional[str] = None,
        **kwargs: Any,
    ) -> Optional[Dict[str, Any]]:
        """
        Return the user record if email exists, password is correct, and
        the account is active.  Return None on any failure to avoid leaking
        which condition failed (timing-safe pattern).
        """
        if email is None or password is None:
            return None

        user = self._USERS.get(email)
        if user is None:
            return None

        # Production: use user.check_password(password)
        password_ok = self._check_password(password, user["password_hash"])
        if password_ok and user["is_active"]:
            return user
        return None

    def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve a user by primary key — called on every authenticated request."""
        for user in self._USERS.values():
            if user["id"] == user_id:
                return user
        return None

    @staticmethod
    def _check_password(plain: str, stored_hash: str) -> bool:
        """
        Placeholder — production uses Django's PBKDF2 hasher via
        django.contrib.auth.hashers.check_password.
        """
        # Trivial stub: accept any non-empty password for demo
        return bool(plain)


class OTPAuthBackend:
    """
    Allows users to log in with a phone number and a one-time password
    stored in Django's cache (backed by Redis in production).

    Flow:
      1. An SMS gateway sends OTP → backend stores it in cache with a short TTL.
      2. The client posts phone + OTP to the login endpoint.
      3. This backend retrieves the cached OTP and compares it.

    Production:
        from django.core.cache import cache

        class OTPAuthBackend(BaseBackend):
            def authenticate(self, request, phone=None, otp=None, **kwargs):
                try:
                    user = User.objects.get(phone=phone)
                except User.DoesNotExist:
                    return None
                if self._verify_otp(phone, otp):
                    return user
                return None

            def _verify_otp(self, phone: str, otp: str) -> bool:
                stored = cache.get(f"otp:{phone}")
                return stored == otp
    """

    # Simulated cache for the standalone demo
    _CACHE: Dict[str, str] = {}

    # Simulated user store for the standalone demo
    _USERS: Dict[str, Dict[str, Any]] = {
        "+919876543210": {"id": 3, "name": "Charlie"},
    }

    def store_otp(self, phone: str, otp: str, ttl_seconds: int = 300) -> None:
        """
        Called by the OTP-send view.  In production:
            cache.set(f"otp:{phone}", otp, timeout=ttl_seconds)
        """
        self._CACHE[f"otp:{phone}"] = otp
        log.debug("OTP stored  phone=%s  ttl=%ds", phone, ttl_seconds)

    def authenticate(
        self,
        request: Optional[Any],
        phone: Optional[str] = None,
        otp: Optional[str] = None,
        **kwargs: Any,
    ) -> Optional[Dict[str, Any]]:
        if phone is None or otp is None:
            return None

        user = self._USERS.get(phone)
        if user is None:
            return None

        if self._verify_otp(phone, otp):
            return user
        return None

    def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        for user in self._USERS.values():
            if user["id"] == user_id:
                return user
        return None

    def _verify_otp(self, phone: str, otp: str) -> bool:
        """Compare the submitted OTP against the value in the cache."""
        stored: Optional[str] = self._CACHE.get(f"otp:{phone}")
        return stored is not None and stored == otp


# ==========================================================================
# 6. MIDDLEWARE PIPELINE SIMULATION UTILITIES
# ==========================================================================

class _MockRequest:
    """Lightweight stand-in for django.http.HttpRequest."""

    def __init__(
        self,
        method: str = "GET",
        path: str = "/api/data/",
    ) -> None:
        self.method: str = method
        self.path: str = path
        self.user = type(
            "User",
            (),
            {"id": 42, "is_authenticated": True, "username": "demo_user"},
        )()
        self.request_id: Optional[str] = None


class _MockResponse:
    """Lightweight stand-in for django.http.HttpResponse."""

    def __init__(
        self,
        body: bytes = b"OK",
        status_code: int = 200,
    ) -> None:
        self.body: bytes = body
        self.status_code: int = status_code
        self._headers: Dict[str, str] = {}

    def __setitem__(self, key: str, value: str) -> None:
        self._headers[key] = value

    def __getitem__(self, key: str) -> str:
        return self._headers[key]

    def __repr__(self) -> str:
        return f"<MockResponse status={self.status_code} headers={self._headers}>"


def build_middleware_chain(
    middlewares: List[type],
    final_view: Callable[[Any], Any],
) -> Callable[[Any], Any]:
    """
    Compose a Django-style WSGI middleware stack.

    Django wraps handlers from the outermost inward, so the first item in
    the list is the first to execute on request and the last to execute on
    response.

    Each middleware class must accept a single ``get_response`` callable and
    expose a ``__call__(request)`` method — the standard Django interface.
    """
    handler: Callable[[Any], Any] = final_view
    for middleware_class in reversed(middlewares):
        handler = middleware_class(handler)
    return handler


# ==========================================================================
# 7. DECORATOR UTILITIES (useful alongside middleware)
# ==========================================================================

def retry_on_exception(
    exceptions: Tuple[type, ...] = (Exception,),
    max_attempts: int = 3,
    delay_seconds: float = 0.5,
) -> Callable:
    """
    Decorator that retries a function on transient failures.

    Commonly used with management-command helpers that call external APIs
    subject to rate limits or brief network blips.

    Example:
        @retry_on_exception(exceptions=(requests.Timeout,), max_attempts=5)
        def fetch_users_from_api(limit: int) -> list: ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Optional[Exception] = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    log.warning(
                        "retry  func=%s  attempt=%d/%d  error=%s",
                        func.__name__,
                        attempt,
                        max_attempts,
                        exc,
                    )
                    if attempt < max_attempts:
                        time.sleep(delay_seconds)
            raise RuntimeError(
                f"All {max_attempts} attempts failed for {func.__name__}"
            ) from last_exc
        return wrapper
    return decorator


def log_execution_time(func: Callable) -> Callable:
    """
    Decorator that logs the wall-clock execution time of a function.

    Useful when wrapping management-command handle() methods to surface
    slow syncs without adding timing boilerplate to every command.
    """
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            elapsed = (time.perf_counter() - start) * 1000
            log.info("completed  func=%s  elapsed_ms=%.2f", func.__name__, elapsed)
            return result
        except Exception:
            elapsed = (time.perf_counter() - start) * 1000
            log.error("failed  func=%s  elapsed_ms=%.2f", func.__name__, elapsed)
            raise
    return wrapper


# ==========================================================================
# 8. STANDALONE DEMO — runs without Django, Redis, or any external infra
# ==========================================================================

def _demo_middleware_chain() -> None:
    print("\n" + "=" * 68)
    print("DEMO 1: Middleware pipeline simulation")
    print("=" * 68)

    def final_view(request: _MockRequest) -> _MockResponse:
        """Pretend Django view that returns a 200 response."""
        return _MockResponse(body=b'{"status": "ok"}', status_code=200)

    chain = build_middleware_chain(
        middlewares=[RequestLoggingMiddleware, MaintenanceModeMiddleware],
        final_view=final_view,
    )

    req = _MockRequest(method="GET", path="/api/items/")
    resp = chain(req)

    print(f"  Response status : {resp.status_code}")
    print(f"  X-Request-ID    : {resp._headers.get('X-Request-ID', '(none)')}")
    print(f"  request_id set  : {req.request_id}")


def _demo_maintenance_mode() -> None:
    print("\n" + "=" * 68)
    print("DEMO 2: Maintenance-mode middleware (503 returned)")
    print("=" * 68)

    # Monkey-patch a minimal Django settings shim for the demo
    import types
    import sys

    fake_settings = types.ModuleType("django.conf")
    fake_settings.settings = type(  # type: ignore[attr-defined]
        "Settings", (), {"MAINTENANCE_MODE": True}
    )()
    sys.modules.setdefault("django", types.ModuleType("django"))
    sys.modules.setdefault("django.conf", fake_settings)

    def final_view(request: _MockRequest) -> _MockResponse:
        return _MockResponse(body=b"OK", status_code=200)

    chain = build_middleware_chain(
        middlewares=[MaintenanceModeMiddleware],
        final_view=final_view,
    )

    for path, expected in [("/api/data/", 503), ("/health/", 200), ("/admin/", 200)]:
        req = _MockRequest(path=path)
        resp = chain(req)
        status = "PASS" if resp.status_code == expected else "FAIL"
        print(f"  [{status}]  path={path:<20}  status={resp.status_code}  (expected {expected})")

    # Cleanup shim
    sys.modules.pop("django.conf", None)
    sys.modules.pop("django", None)


def _demo_management_command() -> None:
    print("\n" + "=" * 68)
    print("DEMO 3: Management command — SyncUsersCommand")
    print("=" * 68)

    cmd = SyncUsersCommand()

    print("  -- Live run (source=api, limit=3) --")
    cmd.handle(dry_run=False, limit=3, source="api")

    print("  -- Dry run (source=csv, limit=5) --")
    cmd.handle(dry_run=True, limit=5, source="csv")


def _demo_email_auth_backend() -> None:
    print("\n" + "=" * 68)
    print("DEMO 4: EmailAuthBackend")
    print("=" * 68)

    backend = EmailAuthBackend()

    cases: List[Tuple[Optional[str], Optional[str], str]] = [
        ("alice@example.com", "any_password", "active user — should authenticate"),
        ("bob@example.com",   "any_password", "inactive user — should fail"),
        ("ghost@example.com", "any_password", "unknown email — should fail"),
        (None,                 None,           "no credentials — should fail"),
    ]

    for email, password, note in cases:
        user = backend.authenticate(None, email=email, password=password)
        result = f"authenticated as id={user['id']}" if user else "rejected"
        print(f"  {note}")
        print(f"    => {result}")


def _demo_otp_auth_backend() -> None:
    print("\n" + "=" * 68)
    print("DEMO 5: OTPAuthBackend")
    print("=" * 68)

    backend = OTPAuthBackend()
    phone = "+919876543210"

    # Step 1 — store the OTP as if the SMS gateway has delivered it
    backend.store_otp(phone=phone, otp="482910", ttl_seconds=300)

    cases: List[Tuple[str, str, str]] = [
        (phone, "482910", "correct OTP — should authenticate"),
        (phone, "000000", "wrong OTP   — should fail"),
        ("+440000000000", "482910", "unknown phone — should fail"),
    ]

    for p, otp, note in cases:
        user = backend.authenticate(None, phone=p, otp=otp)
        result = f"authenticated as '{user['name']}'" if user else "rejected"
        print(f"  {note}")
        print(f"    => {result}")


def _demo_retry_decorator() -> None:
    print("\n" + "=" * 68)
    print("DEMO 6: retry_on_exception decorator")
    print("=" * 68)

    attempt_counter: Dict[str, int] = {"count": 0}

    @retry_on_exception(exceptions=(ValueError,), max_attempts=3, delay_seconds=0.0)
    @log_execution_time
    def flaky_api_call() -> str:
        attempt_counter["count"] += 1
        if attempt_counter["count"] < 3:
            raise ValueError("transient network error")
        return "success"

    result = flaky_api_call()
    print(f"  Succeeded after {attempt_counter['count']} attempt(s): {result}")


# ==========================================================================
# ENTRY POINT
# ==========================================================================

if __name__ == "__main__":
    print("\nDjango Channels, Middleware, Management Commands — Practical Demo")
    print("(No Django, Redis, or external infrastructure required)\n")

    _demo_middleware_chain()
    _demo_maintenance_mode()
    _demo_management_command()
    _demo_email_auth_backend()
    _demo_otp_auth_backend()
    _demo_retry_decorator()

    print("\n" + "=" * 68)
    print("All demos complete.")
    print("=" * 68)
