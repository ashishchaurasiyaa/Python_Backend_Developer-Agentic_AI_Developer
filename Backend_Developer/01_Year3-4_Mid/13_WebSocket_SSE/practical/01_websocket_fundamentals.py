"""
WebSocket Fundamentals — Production Patterns
=============================================

Covers the full lifecycle of WebSocket connections in Python:

  - Protocol handshake mechanics and frame structure reference
  - Standalone echo server and client using the `websockets` library
  - FastAPI WebSocket endpoint with authentication, origin checking, and
    structured JSON message dispatch
  - Heartbeat / keep-alive loop to detect dead connections
  - Backpressure and message-size limiting configuration
  - Connection manager for tracking active clients
  - Application-level message framing with JSON and msgpack
  - Close-code reference and graceful shutdown helpers

Run modes
---------
  # Start the standalone websockets echo server (port 8765):
  python 01_websocket_fundamentals.py server

  # Run the websockets client against the echo server:
  python 01_websocket_fundamentals.py client

  # Start the FastAPI app (requires uvicorn):
  uvicorn 01_websocket_fundamentals:fastapi_app --port 8000

Install
-------
  pip install websockets fastapi uvicorn msgpack
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, Optional, Set

# pip install websockets
import websockets
from websockets.server import WebSocketServerProtocol

# pip install fastapi uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

# pip install msgpack
import msgpack  # noqa: F401  (imported for the binary framing section)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


# ==========================================================================
# 1. WEBSOCKET FRAME OPCODES — reference enum
# ==========================================================================

class Opcode(IntEnum):
    """RFC 6455 §5.2 opcodes.

    Knowing these helps when debugging raw WS traffic in Wireshark or
    when writing low-level protocol handlers.
    """
    CONTINUATION = 0x0   # continuation frame for fragmented messages
    TEXT         = 0x1   # UTF-8 text payload
    BINARY       = 0x2   # arbitrary binary payload
    CLOSE        = 0x8   # initiate or acknowledge connection close
    PING         = 0x9   # heartbeat request
    PONG         = 0xA   # heartbeat response


# ==========================================================================
# 2. CLOSE CODE REFERENCE
# ==========================================================================

class CloseCode(IntEnum):
    """RFC 6455 §7.4.1 status codes sent in a Close frame."""
    NORMAL_CLOSURE   = 1000  # clean close by either party
    GOING_AWAY       = 1001  # server shutting down / browser navigating away
    PROTOCOL_ERROR   = 1002
    UNSUPPORTED_DATA = 1003
    POLICY_VIOLATION = 1008  # e.g. failed auth, origin not allowed
    INTERNAL_ERROR   = 1011  # server-side bug
    # 4000-4999 — application-defined range
    AUTH_FAILED      = 4001
    RATE_LIMITED     = 4029
    SESSION_EXPIRED  = 4401


# ==========================================================================
# 3. APPLICATION MESSAGE SCHEMA
# ==========================================================================

@dataclass
class AppMessage:
    """Typed wrapper around the JSON envelope used in this application.

    All messages (both directions) follow the shape:
        {"type": "<event_name>", "data": <any>}

    This keeps the WebSocket transport agnostic to business logic; handlers
    are dispatched by the `type` field.
    """
    type: str
    data: object

    def to_json(self) -> str:
        return json.dumps({"type": self.type, "data": self.data})

    def to_msgpack(self) -> bytes:
        """Binary encoding for higher-throughput payloads (games, telemetry)."""
        return msgpack.packb({"type": self.type, "data": self.data})

    @classmethod
    def from_json(cls, raw: str) -> "AppMessage":
        obj = json.loads(raw)
        return cls(type=obj["type"], data=obj.get("data"))

    @classmethod
    def from_msgpack(cls, raw: bytes) -> "AppMessage":
        obj = msgpack.unpackb(raw, raw=False)
        return cls(type=obj["type"], data=obj.get("data"))


# ==========================================================================
# 4. STANDALONE ECHO SERVER (websockets library)
# ==========================================================================

# pip install websockets

ALLOWED_ORIGINS: Set[str] = {"http://localhost:3000", "https://myapp.example.com"}
MAX_MESSAGE_BYTES = 1 * 1024 * 1024   # 1 MB — prevent memory exhaustion
PING_INTERVAL_SEC = 20
PING_TIMEOUT_SEC  = 10


async def echo_handler(websocket: WebSocketServerProtocol) -> None:
    """Simple echo server — returns every received message prefixed with 'Echo:'.

    Demonstrates:
      - Origin validation before accepting
      - Structured JSON message dispatch
      - Graceful close on disconnect
    """
    # --- Origin check (CORS equivalent for WebSocket) ---
    origin = websocket.request_headers.get("Origin", "")
    if origin and origin not in ALLOWED_ORIGINS:
        log.warning("Rejected connection from disallowed origin: %s", origin)
        await websocket.close(CloseCode.POLICY_VIOLATION, "Origin not allowed")
        return

    remote = websocket.remote_address
    log.info("Client connected: %s", remote)

    try:
        async for raw in websocket:
            try:
                msg = AppMessage.from_json(raw)
            except (json.JSONDecodeError, KeyError):
                # Unknown format — send an error frame and continue
                err = AppMessage(type="error", data="Invalid message format")
                await websocket.send(err.to_json())
                continue

            # Dispatch by message type
            if msg.type == "ping":
                reply = AppMessage(type="pong", data=None)
            elif msg.type == "echo":
                reply = AppMessage(type="echo_reply", data=msg.data)
            elif msg.type == "chat":
                reply = AppMessage(type="chat", data=f"Server received: {msg.data}")
            else:
                reply = AppMessage(type="error", data=f"Unknown type: {msg.type}")

            await websocket.send(reply.to_json())

    except websockets.ConnectionClosedOK:
        log.info("Client disconnected cleanly: %s", remote)
    except websockets.ConnectionClosedError as exc:
        log.warning("Client dropped (abnormal close 1006): %s — %s", remote, exc)


async def run_echo_server() -> None:
    """Start the echo server with recommended production settings."""
    async with websockets.serve(
        echo_handler,
        host="localhost",
        port=8765,
        max_size=MAX_MESSAGE_BYTES,          # reject oversized frames
        ping_interval=PING_INTERVAL_SEC,     # send Ping every 20 s
        ping_timeout=PING_TIMEOUT_SEC,       # close if Pong not received in 10 s
    ):
        log.info("Echo server listening on ws://localhost:8765")
        await asyncio.Future()  # run forever until cancelled


# ==========================================================================
# 5. WEBSOCKET CLIENT (websockets library)
# ==========================================================================

async def run_demo_client() -> None:
    """Connect to the echo server, send a few messages, then disconnect.

    Shows the client-side pattern including reconnect logic skeleton.
    """
    url = "ws://localhost:8765"
    attempt = 0

    while True:
        attempt += 1
        try:
            async with websockets.connect(url) as ws:
                log.info("Connected to %s (attempt %d)", url, attempt)
                attempt = 0  # reset backoff on successful connection

                # Send a structured chat message
                msg = AppMessage(type="chat", data="Hello from the client!")
                await ws.send(msg.to_json())
                raw = await ws.recv()
                reply = AppMessage.from_json(raw)
                log.info("Received reply — type=%s data=%s", reply.type, reply.data)

                # Send a ping message (application-level, not WS Ping frame)
                await ws.send(AppMessage(type="ping", data=None).to_json())
                pong_raw = await ws.recv()
                pong = AppMessage.from_json(pong_raw)
                log.info("Pong: %s", pong.type)

                # Clean shutdown
                await ws.close(CloseCode.NORMAL_CLOSURE, "Demo complete")
                break  # exit the reconnect loop

        except (OSError, websockets.InvalidHandshake) as exc:
            # --- Exponential backoff with jitter for client-side reconnect ---
            import random
            wait = min(2 ** attempt, 60) + random.uniform(0, 1)
            log.warning("Connection failed: %s. Retrying in %.1fs…", exc, wait)
            await asyncio.sleep(wait)
            if attempt > 5:
                log.error("Max reconnect attempts reached — giving up.")
                raise


# ==========================================================================
# 6. MANUAL HEARTBEAT LOOP (without library-level ping_interval)
# ==========================================================================

async def heartbeat_loop(ws: WebSocketServerProtocol, interval: int = 20, timeout: int = 10) -> None:
    """Send a WS-level Ping frame every `interval` seconds.

    If the Pong does not arrive within `timeout` seconds the connection is
    considered dead and closed with code 1006 (abnormal closure).

    In production, prefer the `ping_interval` / `ping_timeout` parameters
    on `websockets.serve()` — they do exactly this.  This function is
    illustrative of what happens underneath.
    """
    while True:
        try:
            pong_waiter = await ws.ping()
            await asyncio.wait_for(pong_waiter, timeout=timeout)
            log.debug("Pong received from %s", ws.remote_address)
        except asyncio.TimeoutError:
            log.warning("Heartbeat timeout — closing %s", ws.remote_address)
            await ws.close(CloseCode.INTERNAL_ERROR, "Heartbeat timeout")
            return
        await asyncio.sleep(interval)


# ==========================================================================
# 7. FASTAPI WEBSOCKET APP
# ==========================================================================

fastapi_app = FastAPI(title="WebSocket Fundamentals")

# -- Fake auth helper (replace with real JWT / session logic) ---------------

def verify_token(token: str) -> Optional[str]:
    """Return the user-id associated with the token, or None if invalid."""
    # In production: decode JWT, check expiry, look up session in Redis, etc.
    if token == "secret-dev-token":
        return "user-42"
    return None


# ==========================================================================
# 7a. SIMPLE FASTAPI ECHO ENDPOINT
# ==========================================================================

@fastapi_app.websocket("/ws/echo")
async def ws_echo(websocket: WebSocket) -> None:
    """Basic echo endpoint — accepts any text and echoes it back.

    Illustrates the minimal FastAPI WebSocket pattern.
    """
    await websocket.accept()
    try:
        while True:
            text = await websocket.receive_text()
            await websocket.send_text(f"Echo: {text}")
    except WebSocketDisconnect:
        log.info("Echo client disconnected")


# ==========================================================================
# 7b. AUTHENTICATED FASTAPI ENDPOINT (first-message auth pattern)
# ==========================================================================

@fastapi_app.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket) -> None:
    """Authenticated chat endpoint using the first-message auth pattern.

    Flow:
      1. Accept connection (TLS handshake done, but client NOT yet verified).
      2. Receive first message containing {"type": "auth", "data": {"token": "…"}}.
      3. Verify token — close with 4001 if invalid.
      4. Enter the message loop.

    This avoids putting the token in the query string (visible in server
    logs) while remaining simple to implement.
    """
    # --- Origin validation ---
    origin = websocket.headers.get("origin", "")
    if origin and origin not in ALLOWED_ORIGINS:
        await websocket.close(CloseCode.POLICY_VIOLATION, "Origin not allowed")
        return

    await websocket.accept()

    # --- Step 1: Authentication handshake ---
    try:
        auth_raw = await asyncio.wait_for(websocket.receive_json(), timeout=10.0)
    except asyncio.TimeoutError:
        await websocket.close(CloseCode.POLICY_VIOLATION, "Auth timeout")
        return
    except WebSocketDisconnect:
        return

    if auth_raw.get("type") != "auth":
        await websocket.send_json({"type": "error", "data": "Expected auth message first"})
        await websocket.close(CloseCode.POLICY_VIOLATION, "Auth required")
        return

    token = (auth_raw.get("data") or {}).get("token", "")
    user_id = verify_token(token)
    if not user_id:
        await websocket.send_json({"type": "error", "data": "Invalid token"})
        await websocket.close(CloseCode.AUTH_FAILED, "Unauthorized")
        return

    await websocket.send_json({"type": "auth_ok", "data": {"user_id": user_id}})
    log.info("User %s authenticated via WebSocket", user_id)

    # --- Step 2: Message loop ---
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = AppMessage.from_json(raw)
            except (json.JSONDecodeError, KeyError):
                await websocket.send_json({"type": "error", "data": "Malformed message"})
                continue

            if msg.type == "chat":
                # Broadcast logic would call ConnectionManager here (see §8)
                reply = AppMessage(type="chat", data=f"[{user_id}]: {msg.data}")
            elif msg.type == "typing":
                reply = AppMessage(type="typing", data={"user_id": user_id})
            else:
                reply = AppMessage(type="error", data=f"Unknown type: {msg.type}")

            await websocket.send_text(reply.to_json())

    except WebSocketDisconnect:
        log.info("User %s disconnected", user_id)


# ==========================================================================
# 7c. QUERY-STRING TOKEN ENDPOINT (simpler but less secure)
# ==========================================================================

@fastapi_app.websocket("/ws/stream")
async def ws_stream(websocket: WebSocket, token: str = "") -> None:
    """Auth via query-string token: ws://host/ws/stream?token=<jwt>.

    Simpler to implement but tokens appear in server access logs.
    Use only for non-sensitive contexts or server-to-server connections.
    """
    user_id = verify_token(token)
    if not user_id:
        await websocket.close(CloseCode.AUTH_FAILED, "Invalid token")
        return

    await websocket.accept()

    try:
        counter = 0
        while True:
            counter += 1
            payload = AppMessage(type="tick", data={"n": counter, "ts": time.time()})
            await websocket.send_text(payload.to_json())
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        log.info("Stream client %s disconnected", user_id)


# ==========================================================================
# 8. CONNECTION MANAGER — multi-client broadcast
# ==========================================================================

@dataclass
class ConnectionManager:
    """Track all active WebSocket connections and broadcast messages.

    In a single-process deployment this is sufficient.  For multi-process
    (multiple Uvicorn workers or Kubernetes pods), replace the local set
    with a Redis Pub/Sub backplane — see 03_scaling_with_redis_pubsub.md.
    """
    _connections: Dict[str, WebSocket] = field(default_factory=dict)

    async def connect(self, user_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._connections[user_id] = ws
        log.info("ConnectionManager: %s connected (%d total)", user_id, len(self._connections))

    def disconnect(self, user_id: str) -> None:
        self._connections.pop(user_id, None)
        log.info("ConnectionManager: %s disconnected (%d remain)", user_id, len(self._connections))

    async def send_personal(self, user_id: str, message: AppMessage) -> None:
        ws = self._connections.get(user_id)
        if ws:
            try:
                await ws.send_text(message.to_json())
            except Exception:
                self.disconnect(user_id)

    async def broadcast(self, message: AppMessage, exclude: Optional[str] = None) -> None:
        """Send to every connected client except the optional `exclude` user."""
        dead: list[str] = []
        for uid, ws in self._connections.items():
            if uid == exclude:
                continue
            try:
                await ws.send_text(message.to_json())
            except Exception:
                dead.append(uid)
        for uid in dead:
            self.disconnect(uid)

    @property
    def active_count(self) -> int:
        return len(self._connections)


# Singleton for the FastAPI application
manager = ConnectionManager()


@fastapi_app.websocket("/ws/room")
async def ws_room(websocket: WebSocket, user_id: str = "anonymous") -> None:
    """Chat room using the ConnectionManager — broadcasts every message to all clients."""
    await manager.connect(user_id, websocket)
    try:
        while True:
            text = await websocket.receive_text()
            broadcast_msg = AppMessage(type="chat", data={"user": user_id, "text": text})
            await manager.broadcast(broadcast_msg)
    except WebSocketDisconnect:
        manager.disconnect(user_id)
        leave_msg = AppMessage(type="system", data=f"{user_id} left the room")
        await manager.broadcast(leave_msg)


# ==========================================================================
# 9. BACKPRESSURE CONFIGURATION REFERENCE
# ==========================================================================

BACKPRESSURE_NOTE = """
Backpressure strategies for slow consumers
===========================================

1. Drop messages
   If the outbound queue exceeds a threshold, skip sending rather than
   accumulating indefinitely:

       try:
           ws.send_nowait(payload)     # hypothetical non-blocking send
       except asyncio.QueueFull:
           log.warning("Dropping message for slow client %s", uid)

2. Application-level ACK / flow control
   Send the next batch only after the client acknowledges the previous one.
   Works well for ordered feeds (event replay, file transfer).

3. Close slow clients
   In streaming dashboards, disconnect clients whose buffers fill beyond a
   threshold to free server resources:

       await ws.close(CloseCode.POLICY_VIOLATION, "Send queue overflow")

websockets library knobs
------------------------
   async with websockets.serve(
       handler,
       write_limit=64 * 1024,   # bytes buffered before back-pressure applied
       max_queue=32,             # max queued incoming messages per connection
       ping_interval=20,        # detect dead connections early
       ping_timeout=10,
   ):
       ...
"""


# ==========================================================================
# 10. MESSAGE SIZE LIMITING REFERENCE
# ==========================================================================

SIZE_LIMITING_NOTE = """
Limit incoming message size
============================

Without a limit a single malicious client can send a multi-GB message,
exhausting server memory.

websockets library:
    websockets.serve(handler, max_size=1 * 1024 * 1024)  # 1 MB

FastAPI / Starlette:
    Starlette does not expose a per-message size limit at the WebSocket
    layer directly.  Apply it in the handler:

        raw = await websocket.receive_bytes()
        if len(raw) > MAX_MESSAGE_BYTES:
            await websocket.close(CloseCode.POLICY_VIOLATION, "Message too large")
            return
"""


# ==========================================================================
# 11. NGINX CONFIGURATION REFERENCE
# ==========================================================================

NGINX_CONFIG = """
# Nginx reverse-proxy configuration for WebSocket upstream
# =========================================================
# /etc/nginx/conf.d/ws.conf

upstream ws_backend {
    ip_hash;               # sticky sessions — same client IP → same upstream
    server 127.0.0.1:8000;
    server 127.0.0.1:8001;
}

server {
    listen 443 ssl;
    server_name myapp.example.com;

    location /ws/ {
        proxy_pass http://ws_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;      # required for WS upgrade
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 86400;                    # keep long-lived WS connections
        proxy_send_timeout 86400;
    }
}

# Notes:
#   - proxy_http_version 1.1  — HTTP/1.0 does not support Upgrade.
#   - proxy_read_timeout       — default is 60 s; increase for persistent WS.
#   - ip_hash                  — sticky sessions; replace with Redis pub/sub
#     backplane for stateless multi-instance deployments.
"""


# ==========================================================================
# 12. COMMON ISSUES QUICK-REFERENCE
# ==========================================================================

COMMON_ISSUES = {
    "Connection upgrade failed": (
        "Proxy/LB not forwarding Upgrade + Connection headers. "
        "Add proxy_set_header Upgrade and Connection directives."
    ),
    "Client disconnects after 60s": (
        "LB idle timeout exceeded. Set ping_interval < LB timeout, "
        "or increase the LB idle-connection timeout."
    ),
    "1006 abnormal close": (
        "Network blip — no Close frame received. Client should reconnect "
        "with exponential backoff + jitter."
    ),
    "Memory leak with many clients": (
        "Ensure every connection is removed from ConnectionManager on "
        "disconnect. Set a maximum per-process connection limit."
    ),
    "CORS / origin mismatch": (
        "Check the origin header in the WS upgrade request. "
        "Reject unknown origins with close code 1008."
    ),
}


# ==========================================================================
# 13. TECHNOLOGY COMPARISON TABLE (as a data structure)
# ==========================================================================

TECHNOLOGY_COMPARISON = [
    {
        "technology":  "WebSocket",
        "direction":   "Bidirectional",
        "protocol":    "TCP upgrade",
        "binary":      True,
        "auto_reconnect": False,
        "browser":     True,
        "use_case":    "Chat, gaming, collaborative editing",
    },
    {
        "technology":  "SSE",
        "direction":   "Server → Client",
        "protocol":    "HTTP",
        "binary":      False,
        "auto_reconnect": True,
        "browser":     True,
        "use_case":    "Live feeds, notifications, dashboards",
    },
    {
        "technology":  "HTTP Long Poll",
        "direction":   "Client → Server",
        "protocol":    "HTTP",
        "binary":      True,
        "auto_reconnect": False,
        "browser":     True,
        "use_case":    "Legacy environments without WS/SSE support",
    },
    {
        "technology":  "gRPC Streaming",
        "direction":   "Bidirectional",
        "protocol":    "HTTP/2",
        "binary":      True,
        "auto_reconnect": False,
        "browser":     False,  # gRPC-Web required
        "use_case":    "Internal microservice streaming",
    },
]


# ==========================================================================
# 14. __main__ DEMO — echo server OR demo client
# ==========================================================================

def _print_comparison_table() -> None:
    cols = ["technology", "direction", "binary", "auto_reconnect", "use_case"]
    header = " | ".join(f"{c:<22}" for c in cols)
    print(header)
    print("-" * len(header))
    for row in TECHNOLOGY_COMPARISON:
        print(" | ".join(f"{str(row[c]):<22}" for c in cols))
    print()


def _print_close_codes() -> None:
    print("Close code reference:")
    for member in CloseCode:
        print(f"  {member.value}  {member.name}")
    print()


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "info"

    if command == "server":
        print("Starting WebSocket echo server on ws://localhost:8765 …")
        print("Press Ctrl+C to stop.\n")
        try:
            asyncio.run(run_echo_server())
        except KeyboardInterrupt:
            print("\nServer stopped.")

    elif command == "client":
        print("Running demo client against ws://localhost:8765 …\n")
        asyncio.run(run_demo_client())

    else:
        print(__doc__)
        print("=" * 70)
        print("Technology comparison")
        print("=" * 70)
        _print_comparison_table()
        print("=" * 70)
        _print_close_codes()
        print("Common production issues:")
        for issue, advice in COMMON_ISSUES.items():
            print(f"  [{issue}]")
            print(f"    {advice}")
        print()
        print("Usage:")
        print("  python 01_websocket_fundamentals.py server   # echo server")
        print("  python 01_websocket_fundamentals.py client   # demo client")
        print("  uvicorn 01_websocket_fundamentals:fastapi_app --port 8000")
