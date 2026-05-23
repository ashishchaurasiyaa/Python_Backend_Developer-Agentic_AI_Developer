"""
Django Channels WebSocket Consumer
═══════════════════════════════════════════════════════════
INTERVIEW: Consumer kya hota hai?
  - Django views ka WebSocket equivalent
  - AsyncWebsocketConsumer — async, non-blocking
  - channel_layer — Redis-backed pub/sub for broadcasting

INTERVIEW: Channel Layer ka flow kya hai?
  Client A connects → joins group "chat_roomname"
  Client A sends message →
    consumer receives text_data →
    saves to DB →
    group_send to "chat_roomname" →
    ALL consumers in that group ka chat_message() method call →
    each consumer sends to their WebSocket client

INTERVIEW: @database_sync_to_async kyu use karte hain?
  Channels async environment mein Django ORM synchronous hai.
  Directly call karne se event loop block hoga.
  database_sync_to_async → thread pool mein run karta hai.

INTERVIEW: WebSocket authentication kaise karte hain?
  Option 1: AuthMiddlewareStack (session-based) — scope["user"]
  Option 2: Token in query param: ws://host/ws/chat/?token=<jwt>
             Custom JWTAuthMiddleware (see below)

WebSocket URL: ws://localhost:8000/ws/chat/<room_name>/
"""

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

log = logging.getLogger(__name__)


class ChatConsumer(AsyncWebsocketConsumer):
    """
    Async WebSocket consumer for chat rooms.

    Lifecycle:
      connect()    → called when client opens WS connection
      receive()    → called when client sends a message
      disconnect() → called when client closes connection
    """

    async def connect(self):
        """
        Accept WebSocket connection and join channel group.
        self.scope — contains request metadata (user, URL route, headers)
        """
        self.room_name       = self.scope["url_route"]["kwargs"]["room_name"]
        self.room_group_name = f"chat_{self.room_name}"
        self.user            = self.scope.get("user")

        # Authentication check
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4001)  # 4001 = Unauthorized
            return

        # Check room exists + user is allowed
        room = await self.get_room(self.room_name)
        if room is None:
            await self.close(code=4004)  # 4004 = Not Found
            return

        self.room = room

        # Join the channel group (all consumers in this room share this group)
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name,  # unique identifier for THIS consumer/connection
        )

        await self.accept()

        # Notify room that user joined
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type":     "user_event",   # maps to self.user_event() method
                "event":    "join",
                "username": self.user.email,
            },
        )

        log.info("WS connected: user=%s room=%s", self.user.email, self.room_name)

    async def disconnect(self, close_code: int):
        """Leave channel group on disconnect."""
        if hasattr(self, "room_group_name"):
            # Notify room that user left
            if hasattr(self, "user") and self.user.is_authenticated:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type":     "user_event",
                        "event":    "leave",
                        "username": self.user.email,
                    },
                )

            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name,
            )

        log.info("WS disconnected: code=%s room=%s", close_code, self.room_name)

    async def receive(self, text_data: str):
        """
        Handle incoming WebSocket message from client.

        Expected format:
          {"type": "message", "content": "Hello world"}
          {"type": "typing", "is_typing": true}
        """
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send_error("Invalid JSON")
            return

        msg_type = data.get("type", "message")

        if msg_type == "message":
            content = data.get("content", "").strip()
            if not content:
                return
            if len(content) > 4000:
                await self.send_error("Message too long (max 4000 chars)")
                return

            # Save to DB (sync ORM in thread pool)
            message = await self.save_message(content)

            # Broadcast to all in group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type":       "chat_message",  # maps to self.chat_message()
                    "message_id": message.id,
                    "content":    content,
                    "username":   self.user.email,
                    "timestamp":  message.created_at.isoformat(),
                },
            )

        elif msg_type == "typing":
            # Broadcast typing indicator to others (not sender)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type":      "typing_indicator",
                    "username":  self.user.email,
                    "is_typing": data.get("is_typing", False),
                },
            )

    # ── Channel Layer Event Handlers ──────────────────────
    # These are called when group_send dispatches to this consumer

    async def chat_message(self, event: dict):
        """Receive chat message from group and forward to WebSocket client."""
        await self.send(text_data=json.dumps({
            "type":       "message",
            "message_id": event["message_id"],
            "content":    event["content"],
            "username":   event["username"],
            "timestamp":  event["timestamp"],
        }))

    async def user_event(self, event: dict):
        """Receive user join/leave from group and forward to WebSocket client."""
        await self.send(text_data=json.dumps({
            "type":     "user_event",
            "event":    event["event"],
            "username": event["username"],
        }))

    async def typing_indicator(self, event: dict):
        """Forward typing indicator — skip the sender themselves."""
        if event["username"] != self.user.email:
            await self.send(text_data=json.dumps({
                "type":      "typing",
                "username":  event["username"],
                "is_typing": event["is_typing"],
            }))

    # ── DB helpers ────────────────────────────────────────

    @database_sync_to_async
    def get_room(self, room_name: str):
        """Fetch Room from DB synchronously in thread pool."""
        from .models import Room
        try:
            return Room.objects.get(name=room_name)
        except Room.DoesNotExist:
            return None

    @database_sync_to_async
    def save_message(self, content: str):
        """Save Message to DB synchronously in thread pool."""
        from .models import Message
        return Message.objects.create(
            room=self.room,
            author=self.user,
            content=content,
        )

    # ── Utility ───────────────────────────────────────────

    async def send_error(self, message: str):
        await self.send(text_data=json.dumps({
            "type":    "error",
            "message": message,
        }))


# ─── JWT Auth Middleware for WebSocket ────────────────────
class JWTAuthMiddleware:
    """
    Custom middleware that authenticates WS connections via JWT in query param.

    Usage (client-side):
      const ws = new WebSocket("ws://localhost:8000/ws/chat/general/?token=<jwt>")

    INTERVIEW: Session auth vs JWT for WebSocket?
      Session auth (AuthMiddlewareStack): works if user has session cookie
      JWT in query param: better for SPA/mobile where session cookie not set

    Wrap in asgi.py:
      "websocket": JWTAuthMiddleware(URLRouter(websocket_urlpatterns))
    """
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        from urllib.parse import parse_qs
        from channels.db import database_sync_to_async

        if scope["type"] == "websocket":
            query_string = scope.get("query_string", b"").decode()
            params       = parse_qs(query_string)
            token_list   = params.get("token", [])

            if token_list:
                token_str = token_list[0]
                scope["user"] = await self._get_user_from_token(token_str)

        return await self.inner(scope, receive, send)

    @database_sync_to_async
    def _get_user_from_token(self, token: str):
        from rest_framework_simplejwt.tokens import UntypedToken
        from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import AnonymousUser

        User = get_user_model()
        try:
            UntypedToken(token)  # validates signature + expiry
            from rest_framework_simplejwt.tokens import AccessToken
            data    = AccessToken(token)
            user_id = data["user_id"]
            return User.objects.get(id=user_id)
        except (InvalidToken, TokenError, User.DoesNotExist):
            return AnonymousUser()
