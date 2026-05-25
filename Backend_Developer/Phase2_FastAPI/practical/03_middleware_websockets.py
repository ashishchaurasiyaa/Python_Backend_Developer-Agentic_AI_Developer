"""
PHASE 2 FastAPI — Practical 03: Middleware, CORS, WebSockets, Background Tasks
Run: uvicorn 03_middleware_websockets:app --reload
Docs: http://127.0.0.1:8000/docs
WS:  ws://127.0.0.1:8000/ws/chat/{room}

Topics:
  - BaseHTTPMiddleware — timing, request ID, logging
  - CORS setup
  - WebSocket — single client + broadcast room
  - Background Tasks — fire-and-forget after response
  - GZip / Trusted Host middleware
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    FastAPI,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger("app")


# ═══════════════════════════════════════════════════════
# SECTION 1: Custom Middleware
# ═══════════════════════════════════════════════════════

class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Assigns a unique X-Request-ID to every request.
    Useful for distributed tracing — logs correlated across services.
    """
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class TimingMiddleware(BaseHTTPMiddleware):
    """Measures response time, adds X-Response-Time header."""
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
        return response


class RequestLogMiddleware(BaseHTTPMiddleware):
    """Logs every request with method, path, status, time, request_id."""

    SKIP_PATHS = {"/health", "/favicon.ico"}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000

        rid = getattr(request.state, "request_id", "-")
        logger.info(
            f"{request.method} {request.url.path} → {response.status_code} "
            f"[{duration_ms:.1f}ms] rid={rid}"
        )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple IP-based rate limit — 30 requests/minute."""

    def __init__(self, app, limit: int = 30, window: int = 60):
        super().__init__(app)
        self.limit  = limit
        self.window = window
        self._buckets: dict[str, list[float]] = {}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        ip  = (request.client.host if request.client else "unknown")
        now = time.time()
        window_start = now - self.window

        calls = [t for t in self._buckets.get(ip, []) if t > window_start]
        if len(calls) >= self.limit:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded", "retry_after": self.window},
                headers={"Retry-After": str(self.window)},
            )
        calls.append(now)
        self._buckets[ip] = calls
        return await call_next(request)


# ═══════════════════════════════════════════════════════
# SECTION 2: WebSocket Connection Manager
# ═══════════════════════════════════════════════════════

class ConnectionManager:
    """Manages WebSocket connections per room."""

    def __init__(self):
        self._rooms: dict[str, list[WebSocket]] = {}

    async def connect(self, room: str, ws: WebSocket):
        await ws.accept()
        self._rooms.setdefault(room, []).append(ws)
        logger.info(f"[WS] Connected to room '{room}'. Total in room: {len(self._rooms[room])}")

    def disconnect(self, room: str, ws: WebSocket):
        room_clients = self._rooms.get(room, [])
        if ws in room_clients:
            room_clients.remove(ws)
        if not room_clients:
            self._rooms.pop(room, None)
        logger.info(f"[WS] Disconnected from room '{room}'.")

    async def send_personal(self, ws: WebSocket, message: dict):
        """Send to one specific client."""
        await ws.send_text(json.dumps(message))

    async def broadcast(self, room: str, message: dict, exclude: Optional[WebSocket] = None):
        """Broadcast to all clients in a room."""
        clients = self._rooms.get(room, [])
        dead = []
        for client in clients:
            if client is exclude:
                continue
            try:
                await client.send_text(json.dumps(message))
            except Exception:
                dead.append(client)
        for d in dead:
            clients.remove(d)

    @property
    def room_counts(self) -> dict[str, int]:
        return {room: len(clients) for room, clients in self._rooms.items()}


manager = ConnectionManager()


# ═══════════════════════════════════════════════════════
# SECTION 3: Background Task Functions
# ═══════════════════════════════════════════════════════

async def send_welcome_email(email: str, name: str):
    """Simulated async email send — runs AFTER response is sent."""
    logger.info(f"[BG] Sending welcome email to {email}...")
    await asyncio.sleep(2)  # simulate SMTP latency
    logger.info(f"[BG] ✅ Email sent to {email}")


async def write_audit_log(user_id: int, action: str, details: dict):
    """Write to audit log table — background, non-blocking."""
    logger.info(f"[BG] Audit: user={user_id} action={action} details={details}")
    await asyncio.sleep(0.1)


async def process_uploaded_file(filename: str, user_id: int):
    """Heavy processing after upload — thumbnail, OCR, etc."""
    logger.info(f"[BG] Processing file: {filename} for user {user_id}...")
    await asyncio.sleep(3)
    logger.info(f"[BG] ✅ File {filename} processed")


def sync_notify_slack(channel: str, message: str):
    """Sync background task (no await needed)."""
    logger.info(f"[BG-SYNC] Slack #{channel}: {message}")
    time.sleep(0.5)  # simulate API call
    logger.info(f"[BG-SYNC] ✅ Slack sent to #{channel}")


# ═══════════════════════════════════════════════════════
# SECTION 4: App + Lifespan
# ═══════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 App starting...")
    yield
    logger.info("🛑 App shutting down...")


app = FastAPI(
    title="FastAPI Middleware & WebSockets Practical",
    version="1.0.0",
    lifespan=lifespan,
)

# ─── Middleware stack (order matters — bottom-up for requests) ───

# CORS — must be before custom middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # React/Vite dev
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Response-Time", "X-RateLimit-Remaining"],
)

# Compression for responses > 1KB
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Security: reject requests from unknown hosts
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", "*.yourdomain.com", "*"],  # allow all in dev
)

# Custom middleware (applied bottom to top — RateLimit → Log → Timing → RequestID)
app.add_middleware(RateLimitMiddleware, limit=100, window=60)
app.add_middleware(RequestLogMiddleware)
app.add_middleware(TimingMiddleware)
app.add_middleware(RequestIDMiddleware)  # applied first (outermost)


# ═══════════════════════════════════════════════════════
# SECTION 5: HTTP Routes
# ═══════════════════════════════════════════════════════

class UserRegister(BaseModel):
    name: str
    email: str


@app.get("/", tags=["Root"])
async def root(request: Request):
    return {
        "message": "Middleware + WebSocket Practical",
        "request_id": getattr(request.state, "request_id", None),
    }


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}


# ─── Background Tasks usage ───
@app.post("/users/register", status_code=201, tags=["Users"])
async def register_user(
    user: UserRegister,
    background_tasks: BackgroundTasks,
):
    """
    Responds immediately.
    Email + audit log happen in background AFTER response.
    """
    user_id = 42  # would be DB-inserted ID

    # Add background tasks — they run after response is sent
    background_tasks.add_task(send_welcome_email, user.email, user.name)
    background_tasks.add_task(write_audit_log, user_id, "register", {"email": user.email})
    background_tasks.add_task(sync_notify_slack, "signups", f"New user: {user.name}")

    # Response is sent immediately — client doesn't wait for email
    return {
        "user_id": user_id,
        "message": "Registration successful. Welcome email will arrive shortly.",
    }


@app.post("/upload-heavy", status_code=202, tags=["Files"])
async def upload_and_process(
    filename: str,
    user_id: int,
    background_tasks: BackgroundTasks,
):
    """
    202 Accepted — file queued for processing.
    Heavy work happens in background.
    """
    job_id = str(uuid.uuid4())
    background_tasks.add_task(process_uploaded_file, filename, user_id)
    return {
        "status": "accepted",
        "job_id": job_id,
        "message": f"File '{filename}' queued for processing",
    }


@app.get("/middleware-info", tags=["Debug"])
async def middleware_info(request: Request):
    """Shows middleware-injected request state."""
    return {
        "request_id": getattr(request.state, "request_id", None),
        "client_ip": request.client.host if request.client else None,
        "headers": dict(request.headers),
    }


@app.get("/ws/rooms", tags=["WebSocket"])
async def get_ws_rooms():
    """List active WebSocket rooms."""
    return {"rooms": manager.room_counts}


# ═══════════════════════════════════════════════════════
# SECTION 6: WebSocket Endpoints
# ═══════════════════════════════════════════════════════

@app.websocket("/ws/chat/{room}")
async def websocket_chat(ws: WebSocket, room: str):
    """
    Room-based chat WebSocket.
    Connect: ws://localhost:8000/ws/chat/general
    Send: {"type": "message", "text": "Hello!"}
    Receive: {"type": "message", "from": "...", "text": "...", "room": "..."}
    """
    client_id = str(uuid.uuid4())[:8]
    await manager.connect(room, ws)

    # Notify others in room
    await manager.broadcast(room, {
        "type": "join",
        "client_id": client_id,
        "room": room,
        "message": f"Client {client_id} joined room '{room}'",
    }, exclude=ws)

    try:
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)
            msg_type = data.get("type", "message")

            if msg_type == "message":
                await manager.broadcast(room, {
                    "type": "message",
                    "from": client_id,
                    "text": data.get("text", ""),
                    "room": room,
                    "timestamp": time.time(),
                })
            elif msg_type == "ping":
                await manager.send_personal(ws, {"type": "pong", "ts": time.time()})
            elif msg_type == "private":
                # Personal echo
                await manager.send_personal(ws, {
                    "type": "echo",
                    "original": data.get("text", ""),
                })

    except WebSocketDisconnect:
        manager.disconnect(room, ws)
        await manager.broadcast(room, {
            "type": "leave",
            "client_id": client_id,
            "room": room,
            "message": f"Client {client_id} left room '{room}'",
        })


@app.websocket("/ws/notifications/{user_id}")
async def websocket_notifications(ws: WebSocket, user_id: int):
    """
    Per-user notification stream.
    Server pushes events to client — client doesn't send messages.
    Connect: ws://localhost:8000/ws/notifications/42
    """
    await ws.accept()
    logger.info(f"[WS] User {user_id} subscribed to notifications")

    try:
        # Push 5 simulated notifications
        for i in range(5):
            await asyncio.sleep(2)
            notification = {
                "type": "notification",
                "user_id": user_id,
                "event": f"event_{i}",
                "message": f"Notification {i + 1} for user {user_id}",
                "timestamp": time.time(),
            }
            await ws.send_text(json.dumps(notification))

        await ws.send_text(json.dumps({"type": "done", "message": "All notifications sent"}))

    except WebSocketDisconnect:
        logger.info(f"[WS] User {user_id} disconnected from notifications")


# ─── WebSocket test HTML page ───
@app.get("/ws-test", response_class=None, tags=["WebSocket"])
async def ws_test_page():
    from fastapi.responses import HTMLResponse
    html = """
    <!DOCTYPE html>
    <html>
    <head><title>WebSocket Test</title></head>
    <body>
    <h2>WebSocket Chat Test</h2>
    <input id="room" value="general" placeholder="Room name">
    <button onclick="connect()">Connect</button>
    <br><br>
    <input id="msg" placeholder="Message..." style="width:300px">
    <button onclick="send()">Send</button>
    <button onclick="disconnect()">Disconnect</button>
    <hr>
    <div id="log" style="height:300px;overflow:auto;border:1px solid #ccc;padding:10px;font-family:monospace;"></div>

    <script>
    let ws;
    function log(msg) {
        const d = document.getElementById('log');
        d.innerHTML += msg + '<br>';
        d.scrollTop = d.scrollHeight;
    }
    function connect() {
        const room = document.getElementById('room').value;
        ws = new WebSocket(`ws://localhost:8000/ws/chat/${room}`);
        ws.onopen = () => log('✅ Connected to room: ' + room);
        ws.onmessage = (e) => log('📨 ' + e.data);
        ws.onclose = () => log('❌ Disconnected');
    }
    function send() {
        const text = document.getElementById('msg').value;
        ws.send(JSON.stringify({type: 'message', text}));
        document.getElementById('msg').value = '';
    }
    function disconnect() { ws.close(); }
    </script>
    </body></html>
    """
    return HTMLResponse(content=html)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("03_middleware_websockets:app", host="0.0.0.0", port=8002, reload=True)
