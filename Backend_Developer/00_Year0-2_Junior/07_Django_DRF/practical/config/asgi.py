"""
ASGI Configuration — Django Channels
═══════════════════════════════════════
INTERVIEW: WSGI vs ASGI kya fark hai?
  WSGI = synchronous, HTTP only, one request at a time per worker
  ASGI = asynchronous, supports HTTP + WebSocket + HTTP/2
         multiple concurrent connections per worker

Run with Daphne (ASGI server):
  daphne -p 8000 config.asgi:application

Or with uvicorn:
  uvicorn config.asgi:application --reload
"""
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Initialize Django ASGI app early for settings.
django_asgi_app = get_asgi_application()

# Import after Django setup
from chat.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter({
    # Standard HTTP → Django view handler
    "http": django_asgi_app,

    # WebSocket → Channels consumer
    # AllowedHostsOriginValidator — CSRF-like protection for WS
    # AuthMiddlewareStack — populates request.user from session/token
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        )
    ),
})
