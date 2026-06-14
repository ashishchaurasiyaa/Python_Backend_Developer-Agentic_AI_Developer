"""
FastAPI WebSocket Deep Dive — Production Patterns
=================================================
This module demonstrates advanced FastAPI WebSocket patterns used in production:

  - Basic echo endpoint (accept / receive / send loop)
  - Path and query parameters on WebSocket routes
  - Three authentication strategies: subprotocol, first-message, cookie + Origin check
  - Dependency injection with WebSocketException
  - ConnectionManager: broadcast to all connected clients
  - RoomManager: per-room broadcasts with sender exclusion
  - Structured message protocol with Pydantic discriminated union
  - Per-connection state tracking
  - Background task (periodic push) alongside the receive loop
  - Concurrent send/receive via asyncio.gather + asyncio.Queue
  - Per-connection rate limiting and message-size guard
  - Error handling: soft errors as messages, fatal errors via close codes
  - Heartbeat/ping configuration note
  - Memory and scaling notes

pip install fastapi uvicorn[standard] pydantic

Run (with heartbeat flags):
    uvicorn 04_fastapi_websocket_deep:app --reload \
            --ws-ping-interval 20 --ws-ping-timeout 10

The app is structured as production importable code; no __main__ is needed
because WebSocket apps must be driven by a proper ASGI server.
"""

import asyncio
import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Literal, Optional

import pydantic
from fastapi import Depends, FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi import status as http_status
from fastapi.exceptions import WebSocketException
from pydantic import BaseModel

# ==========================================================================
# LOGGING
# ==========================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger("ws_deep")

# ==========================================================================
# FASTAPI APPLICATION
# ==========================================================================

app = FastAPI(
    title="FastAPI WebSocket Deep Dive",
    description="Production WebSocket patterns — auth, rooms, protocol, limits",
    version="1.0.0",
)

# ==========================================================================
# ALLOWED ORIGINS — used for CSRF guard on cookie auth
# ==========================================================================

ALLOWED_ORIGINS: set[str] = {
    "https://example.com",
    "http://localhost:3000",
    "http://localhost:8000",
}

# ==========================================================================
# 1. BASIC ECHO ENDPOINT
# ==========================================================================

@app.websocket("/ws/echo")
async def ws_echo(websocket: WebSocket) -> None:
    """
    Simplest possible endpoint: accept, echo every text message back.

    Demonstrates the mandatory accept() call and the WebSocketDisconnect
    exception that signals a clean client close.
    """
    await websocket.accept()
    logger.info("echo: client connected from %s", websocket.client)
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Got: {data}")
    except WebSocketDisconnect:
        logger.info("echo: client disconnected")


# ==========================================================================
# 2. PATH & QUERY PARAMETERS
# ==========================================================================

@app.websocket("/ws/rooms/{room_id}")
async def ws_path_params(websocket: WebSocket, room_id: str) -> None:
    """
    Path parameter extracted directly into the handler signature — identical
    to HTTP route parameters.  Query parameters work the same way.
    """
    await websocket.accept()
    logger.info("path_params: client joined room %s", room_id)
    try:
        while True:
            msg = await websocket.receive_text()
            await websocket.send_text(f"[{room_id}] {msg}")
    except WebSocketDisconnect:
        logger.info("path_params: client left room %s", room_id)


@app.websocket("/ws/with-token")
async def ws_query_token(websocket: WebSocket, token: str = Query(default="")) -> None:
    """
    Query parameter token: wss://host/ws/with-token?token=<value>.
    Validation should happen before accept(); close with 1008 on failure.
    """
    if not token:
        await websocket.close(1008, "Missing token")
        return
    await websocket.accept()
    logger.info("query_token: authenticated via query param")
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"echo (authed): {data}")
    except WebSocketDisconnect:
        pass


# ==========================================================================
# 3. AUTHENTICATION STRATEGIES
# ==========================================================================

# --- Shared JWT stub ---

async def verify_jwt(token: Optional[str]) -> Optional[dict]:
    """
    Stub JWT verifier.  Replace with your actual jwt.decode() call.
    Returns a user dict on success, None on failure.
    """
    if token and token.startswith("valid-"):
        return {"user_id": token.split("-", 1)[1]}
    return None


async def get_user_from_session(session_id: Optional[str]) -> Optional[dict]:
    """
    Stub session lookup.  Replace with an actual Redis / DB call.
    """
    if session_id and session_id.startswith("sess-"):
        return {"user_id": session_id[5:]}
    return None


# --- Pattern 1: Subprotocol auth ---

@app.websocket("/ws/auth/subprotocol")
async def ws_auth_subprotocol(websocket: WebSocket) -> None:
    """
    Client passes JWT inside the Sec-WebSocket-Protocol header:
        new WebSocket("wss://host/ws/auth/subprotocol", ["jwt", token])

    Server reads the header, validates the token, then accepts with the
    negotiated subprotocol so the browser handshake succeeds.
    """
    raw_protocols = websocket.headers.get("sec-websocket-protocol", "")
    parts = [p.strip() for p in raw_protocols.split(",")]

    if len(parts) != 2 or parts[0] != "jwt":
        await websocket.close(1008, "Expected subprotocol: jwt, <token>")
        return

    token = parts[1]
    user = await verify_jwt(token)
    if not user:
        await websocket.close(1008, "Invalid JWT")
        return

    await websocket.accept(subprotocol="jwt")
    logger.info("subprotocol auth: user=%s connected", user["user_id"])

    try:
        while True:
            msg = await websocket.receive_text()
            await websocket.send_text(f"hello {user['user_id']}: {msg}")
    except WebSocketDisconnect:
        logger.info("subprotocol auth: user=%s disconnected", user["user_id"])


# --- Pattern 2: First-message auth ---

@app.websocket("/ws/auth/first-message")
async def ws_auth_first_message(websocket: WebSocket) -> None:
    """
    Accept the socket immediately, then wait up to 5 seconds for a JSON
    auth message ``{"type": "auth", "token": "<jwt>"}``.
    Close with 1008 on timeout or invalid credentials.
    """
    await websocket.accept()

    try:
        auth_msg = await asyncio.wait_for(websocket.receive_json(), timeout=5.0)
    except asyncio.TimeoutError:
        await websocket.close(1008, "Auth timeout")
        return

    token = auth_msg.get("token")
    user = await verify_jwt(token)
    if not user:
        await websocket.send_json({"type": "auth_error", "msg": "Invalid token"})
        await websocket.close(1008, "Unauthorized")
        return

    await websocket.send_json({"type": "auth_ok", "user_id": user["user_id"]})
    logger.info("first-message auth: user=%s connected", user["user_id"])

    try:
        while True:
            data = await websocket.receive_json()
            await websocket.send_json({"type": "echo", "payload": data})
    except WebSocketDisconnect:
        logger.info("first-message auth: user=%s disconnected", user["user_id"])


# --- Pattern 3: Cookie auth with Origin check (CSRF guard) ---

@app.websocket("/ws/auth/cookie")
async def ws_auth_cookie(websocket: WebSocket) -> None:
    """
    Browser sends HttpOnly cookies automatically during the HTTP upgrade.
    Validate Origin to prevent cross-site WebSocket hijacking (CSRF via WS).
    """
    origin = websocket.headers.get("origin", "")
    if origin not in ALLOWED_ORIGINS:
        logger.warning("cookie auth: rejected origin=%s", origin)
        await websocket.close(1008, "Origin not allowed")
        return

    session_id = websocket.cookies.get("session_id")
    user = await get_user_from_session(session_id)
    if not user:
        await websocket.close(1008, "Session invalid or expired")
        return

    await websocket.accept()
    logger.info("cookie auth: user=%s connected (origin=%s)", user["user_id"], origin)

    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"[cookie-authed] {data}")
    except WebSocketDisconnect:
        pass


# ==========================================================================
# 4. DEPENDENCY INJECTION
# ==========================================================================

async def _get_current_user(token: str = Query(default="")) -> dict:
    """
    FastAPI Depends-compatible dependency for WebSocket auth.
    Raises WebSocketException (code 1008) instead of HTTPException.
    """
    user = await verify_jwt(token)
    if not user:
        raise WebSocketException(code=http_status.WS_1008_POLICY_VIOLATION)
    return user


@app.websocket("/ws/depends")
async def ws_with_dependency(
    websocket: WebSocket,
    user: dict = Depends(_get_current_user),
) -> None:
    """
    Demonstrates that FastAPI's Depends() works on WebSocket routes exactly
    as it does on HTTP routes.  The dependency resolves before the handler
    body runs; on failure it short-circuits and closes the connection.
    """
    await websocket.accept()
    logger.info("depends: user=%s connected", user["user_id"])
    try:
        while True:
            msg = await websocket.receive_text()
            await websocket.send_text(f"[{user['user_id']}] {msg}")
    except WebSocketDisconnect:
        pass


# ==========================================================================
# 5. CONNECTION MANAGER — broadcast to all clients
# ==========================================================================

class ConnectionManager:
    """
    Thread-safe (within a single event-loop process) manager for a flat set
    of active WebSocket connections.  Suitable for a single-worker process;
    for multi-worker deployments use a Redis pub/sub backplane instead.
    """

    def __init__(self) -> None:
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.append(ws)
        logger.info("manager: +1 connection (total=%d)", len(self.active))

    def disconnect(self, ws: WebSocket) -> None:
        self.active.remove(ws)
        logger.info("manager: -1 connection (total=%d)", len(self.active))

    async def broadcast(self, message: str) -> None:
        """
        Send to all connected clients.  Silently skip broken connections;
        the disconnect event will clean them up.
        """
        dead: list[WebSocket] = []
        for ws in self.active:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            if ws in self.active:
                self.active.remove(ws)

    async def send_personal(self, ws: WebSocket, message: str) -> None:
        """Send a private message to a single connection."""
        try:
            await ws.send_text(message)
        except Exception:
            logger.warning("manager: failed to send personal message")


manager = ConnectionManager()


@app.websocket("/ws/broadcast")
async def ws_broadcast(websocket: WebSocket) -> None:
    """
    Every message received from any client is re-broadcast to all clients.
    Classic chat-room pattern without room isolation.
    """
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(data)
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ==========================================================================
# 6. ROOM MANAGER — per-room broadcasts
# ==========================================================================

class RoomManager:
    """
    Organises connections into named rooms.  A client can only be in one room
    per WebSocket connection; join a new URL to switch rooms.
    """

    def __init__(self) -> None:
        self.rooms: dict[str, set[WebSocket]] = defaultdict(set)

    async def join(self, room_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self.rooms[room_id].add(ws)
        member_count = len(self.rooms[room_id])
        logger.info("room[%s]: +1 (total=%d)", room_id, member_count)

    def leave(self, room_id: str, ws: WebSocket) -> None:
        self.rooms[room_id].discard(ws)
        if not self.rooms[room_id]:
            del self.rooms[room_id]
            logger.info("room[%s]: deleted (empty)", room_id)
        else:
            logger.info("room[%s]: -1 (total=%d)", room_id, len(self.rooms[room_id]))

    async def broadcast_to_room(
        self,
        room_id: str,
        message: str,
        exclude: Optional[WebSocket] = None,
    ) -> None:
        """Broadcast to every member of a room, optionally skipping the sender."""
        dead: list[WebSocket] = []
        for ws in list(self.rooms.get(room_id, set())):
            if ws is exclude:
                continue
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.rooms[room_id].discard(ws)

    def room_count(self, room_id: str) -> int:
        return len(self.rooms.get(room_id, set()))


rooms = RoomManager()


@app.websocket("/ws/room/{room_id}")
async def ws_room(websocket: WebSocket, room_id: str) -> None:
    """
    Room-based chat.  The sender's own message is not echoed back to them —
    the ``exclude`` parameter forwards to all other room members only.
    """
    await rooms.join(room_id, websocket)
    count = rooms.room_count(room_id)
    await websocket.send_text(
        f"Joined room '{room_id}' ({count} member(s) now)."
    )
    try:
        while True:
            msg = await websocket.receive_text()
            await rooms.broadcast_to_room(room_id, msg, exclude=websocket)
    except WebSocketDisconnect:
        rooms.leave(room_id, websocket)


# ==========================================================================
# 7. STRUCTURED MESSAGE PROTOCOL (Pydantic discriminated union)
# ==========================================================================

class ChatMessage(BaseModel):
    type: Literal["chat"]
    text: str
    room: str = "general"


class TypingIndicator(BaseModel):
    type: Literal["typing"]
    is_typing: bool


class ReadReceipt(BaseModel):
    type: Literal["read"]
    msg_id: str


# Union used for type-hint documentation; routing is manual via "type" field.
Message = ChatMessage | TypingIndicator | ReadReceipt


async def handle_chat(ws: WebSocket, msg: ChatMessage) -> None:
    await ws.send_json({"type": "ack", "text": msg.text, "room": msg.room})


async def handle_typing(ws: WebSocket, msg: TypingIndicator) -> None:
    await ws.send_json({"type": "typing_ack", "is_typing": msg.is_typing})


async def handle_read(ws: WebSocket, msg: ReadReceipt) -> None:
    await ws.send_json({"type": "read_ack", "msg_id": msg.msg_id})


@app.websocket("/ws/protocol")
async def ws_protocol(websocket: WebSocket) -> None:
    """
    Parses every incoming JSON frame with Pydantic using a ``type`` field as
    discriminator.  Validation errors are sent back as error frames rather
    than crashing the connection.
    """
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            try:
                if msg_type == "chat":
                    await handle_chat(websocket, ChatMessage(**data))
                elif msg_type == "typing":
                    await handle_typing(websocket, TypingIndicator(**data))
                elif msg_type == "read":
                    await handle_read(websocket, ReadReceipt(**data))
                else:
                    await websocket.send_json(
                        {"type": "error", "msg": f"Unknown type: {msg_type!r}"}
                    )
            except pydantic.ValidationError as exc:
                await websocket.send_json(
                    {"type": "error", "msg": str(exc)}
                )
    except WebSocketDisconnect:
        pass


# ==========================================================================
# 8. PER-CONNECTION STATE
# ==========================================================================

async def _unsubscribe_all(
    subscribed_channels: set[str],
    websocket: WebSocket,
) -> None:
    """Cleanup helper: remove this socket from every channel it joined."""
    for channel in subscribed_channels:
        logger.info("state: unsubscribing ws from channel=%s", channel)
        # In production: call your pub/sub adapter here.


@app.websocket("/ws/stateful")
async def ws_stateful(websocket: WebSocket) -> None:
    """
    Carries per-connection metadata through the lifetime of the connection.
    The ``finally`` block guarantees cleanup even on server-side errors.
    """
    await websocket.accept()

    state: dict = {
        "user_id": None,
        "subscribed_channels": set(),
        "connected_at": datetime.now(tz=timezone.utc),
        "msg_count": 0,
    }

    try:
        # First message is expected to be an auth frame.
        auth = await asyncio.wait_for(websocket.receive_json(), timeout=5.0)
        user = await verify_jwt(auth.get("token"))
        if not user:
            await websocket.send_json({"type": "error", "msg": "Auth failed"})
            await websocket.close(1008)
            return

        state["user_id"] = user["user_id"]
        await websocket.send_json({"type": "auth_ok"})

        while True:
            frame = await websocket.receive_json()
            state["msg_count"] += 1

            if frame.get("type") == "subscribe":
                ch = frame.get("channel", "")
                state["subscribed_channels"].add(ch)
                await websocket.send_json({"type": "subscribed", "channel": ch})

            elif frame.get("type") == "unsubscribe":
                ch = frame.get("channel", "")
                state["subscribed_channels"].discard(ch)
                await websocket.send_json({"type": "unsubscribed", "channel": ch})

            else:
                await websocket.send_json({"type": "echo", "data": frame})

    except asyncio.TimeoutError:
        await websocket.close(1008, "Auth timeout")
    except WebSocketDisconnect:
        pass
    finally:
        # Always cleanup regardless of disconnect reason.
        await _unsubscribe_all(state["subscribed_channels"], websocket)
        logger.info(
            "stateful: user=%s processed %d messages",
            state["user_id"],
            state["msg_count"],
        )


# ==========================================================================
# 9. BACKGROUND TASK — periodic push alongside receive loop
# ==========================================================================

async def _periodic_updates(ws: WebSocket, interval: float = 10.0) -> None:
    """
    Pushes a server-clock tick to the client every ``interval`` seconds.
    Designed to be run as an asyncio Task; cancelled on client disconnect.
    """
    while True:
        try:
            await ws.send_json(
                {"type": "tick", "ts": datetime.now(tz=timezone.utc).isoformat()}
            )
        except Exception:
            # Connection gone — the main handler will catch WebSocketDisconnect.
            break
        await asyncio.sleep(interval)


@app.websocket("/ws/with-background-task")
async def ws_background_task(websocket: WebSocket) -> None:
    """
    Runs a periodic push task concurrently with the receive loop.
    The task is cancelled in the ``finally`` block to avoid resource leaks.
    """
    await websocket.accept()
    tick_task = asyncio.create_task(_periodic_updates(websocket, interval=5.0))

    try:
        while True:
            msg = await websocket.receive_text()
            await websocket.send_text(f"received: {msg}")
    except WebSocketDisconnect:
        pass
    finally:
        tick_task.cancel()
        try:
            await tick_task
        except asyncio.CancelledError:
            pass


# ==========================================================================
# 10. CONCURRENT SEND / RECEIVE (asyncio.gather + Queue)
# ==========================================================================

# In-memory push-queue registry: maps user_id -> set of asyncio.Queue
_push_queues: dict[str, set[asyncio.Queue]] = defaultdict(set)


def _register_queue(user_id: str, q: asyncio.Queue) -> None:
    _push_queues[user_id].add(q)


def _unregister_queue(user_id: str, q: asyncio.Queue) -> None:
    _push_queues[user_id].discard(q)
    if not _push_queues[user_id]:
        del _push_queues[user_id]


async def push_to_user(user_id: str, payload: dict) -> None:
    """
    Enqueue a server-initiated push for a specific user.
    Can be called from any coroutine (e.g. a REST endpoint).
    """
    for q in _push_queues.get(user_id, set()):
        await q.put(payload)


async def _receive_loop(ws: WebSocket) -> None:
    """Drain incoming client messages."""
    while True:
        frame = await ws.receive_json()
        logger.debug("concurrent_ws: received %s", frame)


async def _push_loop(ws: WebSocket, push_queue: asyncio.Queue) -> None:
    """Drain the push queue and forward each item to the client."""
    while True:
        payload = await push_queue.get()
        await ws.send_json(payload)


@app.websocket("/ws/concurrent/{user_id}")
async def ws_concurrent(websocket: WebSocket, user_id: str) -> None:
    """
    Runs receive and push loops concurrently with asyncio.gather.
    Either loop raising WebSocketDisconnect cancels the other via gather.

    To push a message from elsewhere in the app:
        await push_to_user("alice", {"type": "notification", "msg": "Hello!"})
    """
    await websocket.accept()
    push_queue: asyncio.Queue = asyncio.Queue()
    _register_queue(user_id, push_queue)

    try:
        await asyncio.gather(
            _receive_loop(websocket),
            _push_loop(websocket, push_queue),
        )
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        _unregister_queue(user_id, push_queue)
        logger.info("concurrent: user=%s disconnected", user_id)


# ==========================================================================
# 11. PER-CONNECTION RATE LIMITING & MESSAGE-SIZE GUARD
# ==========================================================================

_MAX_MESSAGE_BYTES = 64 * 1024   # 64 KB hard limit
_RATE_LIMIT_MSGS  = 100           # max messages per second
_RATE_LIMIT_WINDOW = 1.0          # seconds


@app.websocket("/ws/limited")
async def ws_limited(websocket: WebSocket) -> None:
    """
    Enforces two protective limits per connection:

      1. Message size: close with 1009 (message too large) if exceeded.
      2. Rate limit:  close with 1008 (policy violation) if the client
         sends more than ``_RATE_LIMIT_MSGS`` messages per second.

    These run inside the handler, so they apply per-connection without a
    shared counter — appropriate for protecting individual clients from
    accidental or intentional flooding.
    """
    await websocket.accept()

    msg_count = 0
    window_start = time.monotonic()

    try:
        while True:
            raw = await websocket.receive_bytes()

            # --- size guard ---
            if len(raw) > _MAX_MESSAGE_BYTES:
                await websocket.close(1009, "Message too large")
                return

            # --- rate limit ---
            now = time.monotonic()
            if now - window_start >= _RATE_LIMIT_WINDOW:
                window_start = now
                msg_count = 0
            msg_count += 1
            if msg_count > _RATE_LIMIT_MSGS:
                await websocket.close(1008, "Rate limit exceeded")
                return

            # Echo back as text for demonstration.
            await websocket.send_text(raw.decode("utf-8", errors="replace"))

    except WebSocketDisconnect:
        pass


# ==========================================================================
# 12. ERROR HANDLING — soft vs fatal errors, close codes
# ==========================================================================

# Close codes reference (RFC 6455 + common app-defined range):
# 1000 — normal closure
# 1001 — server going away
# 1008 — policy violation (auth, rate limit)
# 1009 — message too large
# 1011 — unexpected server error
# 4000-4999 — application-defined


class BusinessError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


async def _process_frame(frame: dict) -> dict:
    """Stub business logic that may raise application-level errors."""
    if frame.get("action") == "fail":
        raise BusinessError("ERR_DEMO", "Intentional demo failure")
    return {"processed": True, "input": frame}


@app.websocket("/ws/error-handling")
async def ws_error_handling(websocket: WebSocket) -> None:
    """
    Illustrates the two error-handling strategies:

      - Soft (recoverable) errors: send an error JSON frame, keep connection open.
      - Fatal errors: close the socket with an appropriate close code.
    """
    await websocket.accept()
    try:
        while True:
            frame = await websocket.receive_json()
            try:
                result = await _process_frame(frame)
                await websocket.send_json({"type": "result", "data": result})
            except BusinessError as exc:
                # Soft error — report to client and continue.
                await websocket.send_json(
                    {"type": "error", "code": exc.code, "msg": str(exc)}
                )
            except Exception:
                # Fatal — log and close with 1011 (internal server error).
                logger.exception("ws_error_handling: unexpected error")
                await websocket.close(1011, "Internal server error")
                return
    except WebSocketDisconnect:
        pass


# ==========================================================================
# 13. HEARTBEAT / PING CONFIGURATION NOTE
# ==========================================================================

HEARTBEAT_NOTE = """
Heartbeat is configured at the ASGI server level, not in application code.

Uvicorn CLI:
    uvicorn app:app --ws-ping-interval 20 --ws-ping-timeout 10

Uvicorn programmatic:
    uvicorn.run(app, ws_ping_interval=20, ws_ping_timeout=10)

Browsers auto-respond to WebSocket pings (RFC 6455 §5.5.2).
For Python clients using the 'websockets' library:
    async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
        ...

No application-level keep-alive loop is needed when using these flags.
"""


# ==========================================================================
# 14. SCALING NOTE — multi-worker requires a pub/sub backplane
# ==========================================================================

SCALING_NOTE = """
Each Gunicorn/Uvicorn worker runs in its own process with its own event loop.
ConnectionManager and RoomManager instances are NOT shared across processes.

Single-worker deployment (development / small scale):
    uvicorn app:app

Multi-worker deployment (production):
    gunicorn app:app -k uvicorn.workers.UvicornWorker -w 4

For multi-worker: replace in-process managers with a Redis pub/sub backplane
(see 03_scaling_with_redis_pubsub.py in this folder).

Memory footprint per connection: ~10–50 KB (coroutine stack + TCP buffers).
    100 000 connections × 30 KB ≈ 3 GB
For massive connection counts consider a dedicated gateway tier (Go/Rust).
"""


# ==========================================================================
# 15. TESTING REFERENCE (kept as a comment — requires pytest / httpx-ws)
# ==========================================================================

# pip install pytest httpx httpx-ws pytest-asyncio
#
# Synchronous TestClient (most tests):
#
#   from fastapi.testclient import TestClient
#
#   def test_echo():
#       with TestClient(app) as client:
#           with client.websocket_connect("/ws/echo") as ws:
#               ws.send_text("hello")
#               assert ws.receive_text() == "Got: hello"
#
#
# Async test with httpx-ws:
#
#   import pytest
#   from httpx_ws import aconnect_ws
#
#   @pytest.mark.asyncio
#   async def test_echo_async():
#       async with aconnect_ws("ws://test/ws/echo", app=app) as ws:
#           await ws.send_text("hello")
#           msg = await ws.receive_text()
#           assert msg == "Got: hello"


# ==========================================================================
# 16. STARTUP CHECKS
# ==========================================================================

@app.on_event("startup")
async def _startup_checks() -> None:
    """Log advisory warnings for optional but recommended packages."""
    try:
        import uvloop  # noqa: F401
        logger.info("startup: uvloop available — pass --loop uvloop to uvicorn")
    except ImportError:
        logger.warning(
            "startup: uvloop not installed; default asyncio loop is ~2x slower "
            "under load.  pip install uvloop"
        )
