# FastAPI — Middleware, CORS, WebSockets, Background Tasks

## Quick Concepts
- **Middleware** = every request/response se pehle/baad run hota hai
- **CORS** = browser same-origin policy — allowed origins define karo
- **WebSocket** = full-duplex real-time connection (HTTP upgrade)
- **Background Tasks** = response bhejne ke baad kaam karo (email, logs)

---

## Andar kya hota hai — Middleware Onion + WebSocket Handshake

### Middleware — LIFO stack hai, "list of functions" nahi

```python
app.add_middleware(LoggingMiddleware)     # 1st added
app.add_middleware(AuthMiddleware)        # 2nd added
app.add_middleware(CORSMiddleware)        # 3rd added (LAST)
```

Har `add_middleware()` call app ko ek NAYI LAYER se WRAP karta hai — sabse BAAD
mein add hui middleware sabse BAHAR ki layer banti hai. Request andar jaate waqt
**last-added-first** chalti hai, response bahar aate waqt **reverse** order mein:

```
Request  →  CORS  →  Auth  →  Logging  →  [route handler]
Response ←  CORS  ←  Auth  ←  Logging  ←  [route handler]
```

Yehi wajah hai CORS middleware ko usually SABSE LAST add karte hain — taaki woh
sabse PEHLE (outermost) chale aur preflight `OPTIONS` request ko baaki middleware
tak pahunchne se pehle hi handle kar sake.

### WebSocket — ek HTTP request hi hai, jab tak "Upgrade" na ho

```
1. Client normal HTTP GET bhejta hai extra headers ke saath:
     Connection: Upgrade
     Upgrade: websocket
     Sec-WebSocket-Key: <random base64>

2. Server 101 Switching Protocols response deta hai:
     Sec-WebSocket-Accept: <SHA1(key + fixed GUID), base64>
     (yeh hash prove karta hai server ne genuinely WebSocket samjha, random
      HTTP server ne accidentally 101 nahi bhej diya)

3. Is point ke baad, SAME TCP connection ab WebSocket FRAMING protocol use
   karta hai — na ki HTTP request/response. Ab dono directions FULL-DUPLEX
   hain: server kabhi bhi push kar sakta hai, client kabhi bhi bhej sakta hai,
   bina naya request banaye.
```

FastAPI ka `@app.websocket("/ws")` handler yeh handshake khud handle karta hai —
tumhara code seedha step 3 ke baad start hota hai, `await websocket.accept()` ke
saath.

---

## Interview Questions & Answers

### Q1: Custom middleware kaise likhte hain?
**Answer:**
```python
import time
import uuid
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware

app = FastAPI()

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        start = time.perf_counter()
        response = await call_next(request)
        duration = (time.perf_counter() - start) * 1000

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration:.2f}ms"
        return response

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, calls: int = 100, period: int = 60):
        super().__init__(app)
        self.calls = calls
        self.period = period
        self._store = {}   # production mein Redis use karo

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host
        now = time.time()
        window_start = now - self.period

        # Clean old entries
        self._store[client_ip] = [
            t for t in self._store.get(client_ip, []) if t > window_start
        ]

        if len(self._store[client_ip]) >= self.calls:
            from starlette.responses import JSONResponse
            return JSONResponse(
                {"error": "Rate limit exceeded"},
                status_code=429,
                headers={"Retry-After": str(self.period)}
            )

        self._store[client_ip].append(now)
        return await call_next(request)

app.add_middleware(RequestIDMiddleware)
app.add_middleware(RateLimitMiddleware, calls=100, period=60)
```

---

### Q2: CORS kaise setup karte hain?
**Answer:**
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://myapp.com",
        "https://www.myapp.com",
        "http://localhost:3000",   # dev frontend
    ],
    allow_credentials=True,        # cookies allow
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
    max_age=86400,
)

# Development ke liye (sab allow):
# allow_origins=["*"]   # production mein KABHI MAT karo
```

---

### Q3: WebSocket FastAPI mein kaise implement karte hain?
**Answer:**
```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import dict

app = FastAPI()

# Connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: str):
        self.active_connections.pop(client_id, None)

    async def send_personal(self, message: dict, client_id: str):
        ws = self.active_connections.get(client_id)
        if ws:
            await ws.send_json(message)

    async def broadcast(self, message: dict, exclude: str = None):
        for cid, ws in self.active_connections.items():
            if cid != exclude:
                await ws.send_json(message)

manager = ConnectionManager()

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(websocket, client_id)
    try:
        while True:
            data = await websocket.receive_json()

            if data["type"] == "message":
                await manager.broadcast(
                    {"type": "message", "from": client_id, "text": data["text"]},
                    exclude=client_id
                )
            elif data["type"] == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        manager.disconnect(client_id)
        await manager.broadcast({"type": "leave", "user": client_id})

# WebSocket with authentication
@app.websocket("/ws/protected/{client_id}")
async def protected_ws(
    websocket: WebSocket,
    client_id: str,
    token: str,           # query param se token
):
    try:
        user = verify_jwt_token(token)
    except Exception:
        await websocket.close(code=1008, reason="Unauthorized")
        return

    await manager.connect(websocket, client_id)
    # ...
```

---

### Q4: Background Tasks kya hai? Kab use karte hain?
**Answer:**
Background tasks response bhejne ke BAAD run hoti hain — user ko wait nahi karna padta.

```python
from fastapi import BackgroundTasks
import asyncio

app = FastAPI()

# Sync task
def send_welcome_email(email: str, name: str):
    # Email send karo (blocking ok hai — background thread mein hoga)
    print(f"Sending welcome email to {email}")
    time.sleep(2)  # simulate email sending
    print(f"Email sent to {email}")

# Async task
async def log_activity(user_id: int, action: str):
    await asyncio.sleep(0)  # async-friendly
    await db.execute(
        "INSERT INTO activity_logs (user_id, action) VALUES ($1, $2)",
        user_id, action
    )

@app.post("/register")
async def register_user(user: UserCreate, background_tasks: BackgroundTasks):
    # User create karo
    new_user = await create_user_in_db(user)

    # Background mein email bhejo — response wait nahi karega
    background_tasks.add_task(send_welcome_email, user.email, user.name)
    background_tasks.add_task(log_activity, new_user.id, "registered")

    return new_user  # immediately return karo

# Multiple tasks chain
@app.post("/orders")
async def create_order(
    order: OrderCreate,
    background_tasks: BackgroundTasks,
    db: DbSession,
):
    new_order = await save_order(db, order)

    background_tasks.add_task(send_order_confirmation, order.user_email)
    background_tasks.add_task(notify_warehouse, new_order.id)
    background_tasks.add_task(update_inventory, order.items)

    return new_order
```

**Background Tasks vs Celery:**
| | Background Tasks | Celery |
|---|---|---|
| Setup | Zero | Broker (Redis/RabbitMQ) chahiye |
| Retry | No | Yes |
| Distributed | No | Yes |
| Monitoring | No | Flower dashboard |
| Use case | Simple, fire-and-forget | Complex, retry-able, distributed |

---

### Q5: Timing middleware aur request logging ek saath
**Answer:**
```python
import structlog

log = structlog.get_logger()

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        start = time.perf_counter()

        # Bind request_id to all logs in this request
        with structlog.contextvars.bound_contextvars(request_id=request_id):
            log.info(
                "request_started",
                method=request.method,
                path=request.url.path,
                query=str(request.query_params),
            )

            response = await call_next(request)
            duration_ms = (time.perf_counter() - start) * 1000

            log.info(
                "request_finished",
                status=response.status_code,
                duration_ms=round(duration_ms, 2),
            )

            response.headers["X-Request-ID"] = request_id
            return response
```
