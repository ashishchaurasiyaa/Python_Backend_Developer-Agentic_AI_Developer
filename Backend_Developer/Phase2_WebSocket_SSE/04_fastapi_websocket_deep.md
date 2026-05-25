# 04 — FastAPI WebSocket Deep

> FastAPI is Starlette-based WebSocket support. This file shows production patterns: connection manager, auth, error handling, rooms, scaling.

---

## Basic Setup

```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI()

@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Got: {data}")
    except WebSocketDisconnect:
        print("Disconnected")
```

`receive_text`, `receive_json`, `receive_bytes` are available. Match what client sends.

---

## Path Parameters

```python
@app.websocket("/ws/{room_id}")
async def ws(websocket: WebSocket, room_id: str):
    await websocket.accept()
    print(f"Joined room {room_id}")
    ...
```

Query params work too:
```python
@app.websocket("/ws")
async def ws(websocket: WebSocket, token: str = ""):
    await websocket.accept()
```

---

## Authentication

### Pattern 1: Subprotocol
```python
@app.websocket("/ws")
async def ws(websocket: WebSocket):
    subprotocols = websocket.headers.get("sec-websocket-protocol", "")
    parts = [p.strip() for p in subprotocols.split(",")]
    if len(parts) != 2 or parts[0] != "jwt":
        await websocket.close(1008)
        return
    token = parts[1]
    user = await verify_jwt(token)
    if not user:
        await websocket.close(1008)
        return
    await websocket.accept(subprotocol="jwt")
    # Connected, authed
```

Client:
```javascript
new WebSocket("wss://example.com/ws", ["jwt", token])
```

### Pattern 2: First-message auth
```python
@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    try:
        # Wait for auth message (with timeout)
        auth_msg = await asyncio.wait_for(websocket.receive_json(), timeout=5)
        token = auth_msg.get("token")
        user = await verify_jwt(token)
        if not user:
            await websocket.send_json({"type": "auth_error"})
            await websocket.close(1008)
            return
        await websocket.send_json({"type": "auth_ok"})
        # Proceed
    except asyncio.TimeoutError:
        await websocket.close(1008, "Auth timeout")
        return
```

### Pattern 3: Cookie auth
If client is a browser using HttpOnly cookies, the cookie is sent during handshake:
```python
@app.websocket("/ws")
async def ws(websocket: WebSocket):
    session = websocket.cookies.get("session_id")
    user = await get_user_from_session(session)
    if not user:
        await websocket.close(1008)
        return
    await websocket.accept()
```

CSRF caveat: Browser sends cookies on WS upgrade automatically. Add Origin check.

```python
origin = websocket.headers.get("origin")
if origin not in ALLOWED_ORIGINS:
    await websocket.close(1008)
    return
```

---

## Dependency Injection

FastAPI's `Depends` works on WebSocket too!

```python
from fastapi import Depends, Header, WebSocketException, status

async def get_user(token: str = Query(...)):
    user = await verify_jwt(token)
    if not user:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
    return user

@app.websocket("/ws")
async def ws(websocket: WebSocket, user: User = Depends(get_user)):
    await websocket.accept()
    # user is verified
```

---

## Connection Manager (Standard Pattern)

For broadcasting:

```python
class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        self.active.remove(ws)

    async def broadcast(self, message: str):
        for ws in self.active:
            try:
                await ws.send_text(message)
            except Exception:
                pass  # ignore failed sends


manager = ConnectionManager()

@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(data)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
```

---

## Rooms / Channels

```python
from collections import defaultdict

class RoomManager:
    def __init__(self):
        self.rooms: dict[str, set[WebSocket]] = defaultdict(set)

    async def join(self, room_id: str, ws: WebSocket):
        await ws.accept()
        self.rooms[room_id].add(ws)

    def leave(self, room_id: str, ws: WebSocket):
        self.rooms[room_id].discard(ws)
        if not self.rooms[room_id]:
            del self.rooms[room_id]

    async def broadcast_to_room(self, room_id: str, message: str, exclude: WebSocket = None):
        for ws in self.rooms.get(room_id, []):
            if ws is exclude: continue
            try:
                await ws.send_text(message)
            except Exception:
                pass


rooms = RoomManager()

@app.websocket("/ws/{room_id}")
async def ws(websocket: WebSocket, room_id: str):
    await rooms.join(room_id, websocket)
    try:
        while True:
            msg = await websocket.receive_text()
            await rooms.broadcast_to_room(room_id, msg, exclude=websocket)
    except WebSocketDisconnect:
        rooms.leave(room_id, websocket)
```

---

## Message Protocol

Define a structured message format:

```python
from pydantic import BaseModel
from typing import Literal

class ChatMessage(BaseModel):
    type: Literal["chat"]
    text: str

class TypingIndicator(BaseModel):
    type: Literal["typing"]
    is_typing: bool

class ReadReceipt(BaseModel):
    type: Literal["read"]
    msg_id: str

# Union for routing
Message = ChatMessage | TypingIndicator | ReadReceipt
```

Use Pydantic to parse:
```python
import pydantic

@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    while True:
        data = await websocket.receive_json()
        try:
            # Discriminated union
            type_ = data.get("type")
            if type_ == "chat":
                msg = ChatMessage(**data)
                await handle_chat(msg)
            elif type_ == "typing":
                msg = TypingIndicator(**data)
                await handle_typing(msg)
            elif type_ == "read":
                msg = ReadReceipt(**data)
                await handle_read(msg)
            else:
                await websocket.send_json({"type": "error", "msg": "Unknown type"})
        except pydantic.ValidationError as e:
            await websocket.send_json({"type": "error", "msg": str(e)})
```

---

## Error Handling

### Send errors as messages
```python
try:
    await process(msg)
except BusinessError as e:
    await websocket.send_json({"type": "error", "code": e.code, "msg": str(e)})
```

### Close on fatal errors
```python
try:
    ...
except UnauthorizedError:
    await websocket.close(1008, "Unauthorized")
except Exception as e:
    logger.exception("WS error")
    await websocket.close(1011, "Server error")
```

### Common close codes
- 1000: normal
- 1001: server going away
- 1008: policy (auth fail)
- 1011: server error
- 4000-4999: app-defined

---

## Heartbeat

Set keep-alive at server level:
```python
import uvicorn
uvicorn.run(app, ws_ping_interval=20, ws_ping_timeout=10)
```

Browser auto-responds to pings. For Python client:
```python
async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
    ...
```

---

## Per-Connection State

```python
@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    state = {
        "user_id": None,
        "subscribed_channels": set(),
        "connected_at": datetime.utcnow(),
    }
    try:
        # Auth, then use state through this handler
        ...
    finally:
        # Cleanup based on state
        for ch in state["subscribed_channels"]:
            await unsubscribe(ch, websocket)
```

---

## Background Tasks

Long-running task while WS is open:
```python
import asyncio

@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    task = asyncio.create_task(periodic_updates(websocket))
    try:
        while True:
            msg = await websocket.receive_text()
            ...
    except WebSocketDisconnect:
        pass
    finally:
        task.cancel()

async def periodic_updates(ws):
    while True:
        await ws.send_json({"type": "tick", "ts": datetime.utcnow().isoformat()})
        await asyncio.sleep(10)
```

Make sure to cancel the task on disconnect.

---

## Concurrent Send/Receive

Need to receive AND push simultaneously?

```python
async def receive_loop(ws):
    while True:
        msg = await ws.receive_json()
        await handle(msg)

async def push_loop(ws, push_queue):
    while True:
        msg = await push_queue.get()
        await ws.send_json(msg)

@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    push_queue = asyncio.Queue()
    # Register queue with pub/sub system
    register_queue(user_id, push_queue)

    try:
        await asyncio.gather(
            receive_loop(websocket),
            push_loop(websocket, push_queue),
        )
    except WebSocketDisconnect:
        pass
    finally:
        unregister_queue(user_id, push_queue)
```

---

## Limits per Connection

```python
@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    msg_count = 0
    last_reset = time.monotonic()

    while True:
        msg = await websocket.receive_text()
        if len(msg) > 64 * 1024:
            await websocket.close(1009, "Message too large")
            return

        # Rate limit: 100 msgs/sec
        msg_count += 1
        if time.monotonic() - last_reset >= 1:
            last_reset = time.monotonic()
            msg_count = 0
        if msg_count > 100:
            await websocket.close(1008, "Rate limit")
            return
```

---

## Testing WebSocket

```python
from fastapi.testclient import TestClient

def test_ws():
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_text("hello")
            data = ws.receive_text()
            assert data == "Got: hello"
```

Synchronous TestClient is fine for most tests.

For pytest-asyncio:
```python
from httpx_ws import aconnect_ws

@pytest.mark.asyncio
async def test_ws_async(app):
    async with aconnect_ws("ws://test/ws", app=app) as ws:
        await ws.send_text("hi")
        msg = await ws.receive_text()
        assert msg == "Got: hi"
```

---

## Deploying WebSocket Apps

### Uvicorn
```bash
uvicorn app:app --host 0.0.0.0 --port 8000 \
                --ws-ping-interval 20 \
                --ws-ping-timeout 10
```

### Gunicorn + Uvicorn workers
```bash
gunicorn app:app -k uvicorn.workers.UvicornWorker -w 4
```

Note: each worker is separate; state not shared → need pub/sub.

### Behind NGINX
```nginx
location /ws {
    proxy_pass http://app:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "Upgrade";
    proxy_set_header Host $host;
    proxy_read_timeout 86400;
    proxy_send_timeout 86400;
}
```

### K8s
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  annotations:
    nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "3600"
spec:
  ...
```

Plus sticky sessions or backplane (Redis).

---

## Memory Considerations

Each WS connection holds:
- Python coroutine + state.
- TCP socket.
- App-level buffers.

Typical: ~10-50KB per connection. 100K connections × 30KB = 3GB.

Pure Python is limited to ~10K concurrent on single process. For more: multiple workers + backplane.

For massive scale: dedicated gateway tier (Go/Rust).

---

## Common Mistakes

### 1. Forgetting `await websocket.accept()`
Connection hangs.

### 2. Blocking calls inside handler
`time.sleep`, `requests.get` block event loop. Use async.

### 3. Not handling disconnect
Resources leak.

### 4. Sending huge messages
Memory + bandwidth issue. Chunk or paginate.

### 5. No error handling on `send_text`
If client gone, raises exception. Wrap in try/except.

### 6. Sharing manager across processes
Each worker has its own; need pub/sub.

---

## TL;DR

- FastAPI WS = Starlette WebSocket + auto routing.
- Pattern: ConnectionManager / RoomManager.
- Auth via subprotocol / first-message / cookie.
- Structured message protocol (Pydantic).
- Heartbeat + close codes.
- Background tasks via `asyncio.create_task`.
- Limits: per-message size, rate limit.
- Multi-worker: need Redis pub/sub backplane.
- Test with TestClient.
- Deploy: Uvicorn, behind NGINX with upgrade headers.
