# CORS, OpenAPI/Swagger, SSE & Streaming, WebSocket vs SSE

---

# PART 1: CORS (Cross-Origin Resource Sharing)

## What is CORS?
- **CORS** = browser security mechanism — ek origin ka JavaScript doosre origin ko request kar sakta hai ya nahi
- **Origin** = `scheme + domain + port` (`https://myapp.com:443`)
- Browser **blocks** cross-origin requests by default (Same-Origin Policy)
- CORS headers allow server to whitelist specific origins
- **Server-side concern** — browser enforce karta hai, server allow/deny karta hai

## Why CORS?
```
Problem:
  Frontend: https://myapp.com
  API:      https://api.myapp.com  ← different origin!
  
  Browser: "api.myapp.com ne allow nahi kiya → block!"
  
  Without CORS config → every API call fails from browser
  
Why exists?
  Malicious site (evil.com) aapke browser ki cookies use karke
  api.mybank.com pe request nahi kar sake
  → CSRF attacks rokta hai
```

## How — Interview Questions & Answers

### Q1: CORS kaise kaam karta hai? Preflight kya hota hai?

**Answer:**
```
─── Simple Request (no preflight) ───
Methods: GET, POST (only)
Headers: Only standard headers (Content-Type: text/plain, etc.)

  Browser → GET https://api.myapp.com/users
  Server  → 200 OK + Access-Control-Allow-Origin: https://myapp.com
  Browser → Allowed! Response pass hogi JS ko

─── Preflight Request (complex requests) ───
Triggered when:
  - Method: PUT, PATCH, DELETE
  - Custom headers: Authorization, X-Custom-Header
  - Content-Type: application/json

  Browser → OPTIONS https://api.myapp.com/users/1
             Origin: https://myapp.com
             Access-Control-Request-Method: DELETE
             Access-Control-Request-Headers: Authorization

  Server  → 204 No Content
             Access-Control-Allow-Origin: https://myapp.com
             Access-Control-Allow-Methods: GET, POST, PUT, DELETE, PATCH
             Access-Control-Allow-Headers: Authorization, Content-Type
             Access-Control-Max-Age: 86400   ← preflight 24h cache karo

  Browser → Actual DELETE request bhejta hai (server ne allow kiya)

─── CORS headers ───
Response headers (server bhejta hai):
  Access-Control-Allow-Origin:      https://myapp.com  (ya * for public)
  Access-Control-Allow-Methods:     GET, POST, PUT, DELETE, PATCH, OPTIONS
  Access-Control-Allow-Headers:     Authorization, Content-Type, X-Request-ID
  Access-Control-Allow-Credentials: true   (cookies/auth include karo)
  Access-Control-Max-Age:           86400  (preflight cache duration)
  Access-Control-Expose-Headers:    X-RateLimit-Remaining, X-Request-ID

Request headers (browser automatically bhejta hai):
  Origin:                           https://myapp.com
  Access-Control-Request-Method:    DELETE  (preflight mein)
  Access-Control-Request-Headers:   Authorization  (preflight mein)
```

### Q2: FastAPI mein CORS kaise configure karte hain?

**Answer:**
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# ─── Development ───
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Production ───
import os

ALLOWED_ORIGINS = os.getenv("CORS_ORIGINS", "").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,           # ["https://myapp.com", "https://admin.myapp.com"]
    allow_credentials=True,                  # cookies/Authorization header allow
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-User-ID"],
    expose_headers=["X-RateLimit-Remaining", "X-RateLimit-Reset", "X-Request-ID"],
    max_age=86400,                           # preflight 24h cache
)

# ─── Dynamic CORS (per-origin logic) ───
from fastapi.middleware.base import BaseHTTPMiddleware

TRUSTED_ORIGINS = {"https://myapp.com", "https://partner.com"}

class DynamicCORSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        origin = request.headers.get("origin", "")
        response = await call_next(request)

        if origin in TRUSTED_ORIGINS:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Vary"] = "Origin"   # IMPORTANT: CDN ko batao per-origin cache karo

        return response

# ─── INTERVIEW: allow_origins=["*"] + allow_credentials=True problem? ───
# INVALID! Browser reject karta hai.
# Wildcard (*) ke saath credentials (cookies/auth) allowed nahi.
# Solution: specific origins list karo.
```

### Q3: CORS common mistakes?

**Answer:**
```
❌ Mistake 1: allow_origins=["*"] with allow_credentials=True
   → Browser: "Wildcard + credentials = blocked"
   ✓ Fix: Specific origins list karo

❌ Mistake 2: CORS headers missing on error responses
   → 401, 500 pe browser bolta hai "CORS error" — actual error hide ho jaata hai
   ✓ Fix: Middleware ensure karo errors pe bhi headers add hote hain

❌ Mistake 3: Vary header missing
   → CDN same CORS response cache karta hai different origins ke liye
   ✓ Fix: Vary: Origin header add karo (FastAPI automatically karta hai)

❌ Mistake 4: OPTIONS preflight return 405
   → Server ne OPTIONS method allow nahi kiya
   ✓ Fix: allow_methods mein OPTIONS include karo (ya FastAPI auto-handles)

❌ Mistake 5: Custom header expose nahi kiya
   → JS: response.headers.get("X-Request-ID") → null
   ✓ Fix: expose_headers=["X-Request-ID", "X-RateLimit-Remaining"]
```

---

# PART 2: OpenAPI / Swagger

## What is OpenAPI?
- **OpenAPI** (formerly Swagger) = standard for describing REST APIs in YAML/JSON
- Machine-readable API contract — tools generate docs, clients, tests from it
- **FastAPI automatically generates** OpenAPI spec from type hints + docstrings
- `/docs` → Swagger UI (interactive), `/redoc` → ReDoc, `/openapi.json` → raw spec

## Why OpenAPI?
```
✓ Interactive documentation — Swagger UI se directly test karo
✓ Client code generation — openapi-generator → TypeScript, Python, Java clients
✓ Contract testing — frontend + backend agree on spec before coding
✓ API mocking — server spec se fake server banao
✓ Validation — request/response against spec validate karo
```

## How

### Q1: FastAPI mein OpenAPI customize kaise karte hain?

**Answer:**
```python
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.openapi.docs import get_swagger_ui_html

app = FastAPI(
    title="My API",
    description="""
## My Production API

### Features
- User management
- Post CRUD
- Real-time notifications

### Authentication
Use JWT Bearer token: `Authorization: Bearer <token>`
    """,
    version="2.1.0",
    terms_of_service="https://myapp.com/terms",
    contact={"name": "API Support", "email": "api@myapp.com"},
    license_info={"name": "MIT"},
    # Disable default docs if you want custom:
    # docs_url=None, redoc_url=None,
)

# ─── Tags for grouping endpoints ───
from fastapi import APIRouter

users_router = APIRouter(prefix="/users", tags=["Users"])
posts_router = APIRouter(prefix="/posts", tags=["Posts"])


# ─── Endpoint documentation ───
@users_router.get(
    "/{user_id}",
    summary="Get User by ID",
    description="Fetch a single user with their profile details.",
    response_description="User object with all fields",
    responses={
        200: {"description": "User found", "content": {"application/json": {
            "example": {"id": 1, "name": "Alice", "email": "alice@test.com"}
        }}},
        404: {"description": "User not found"},
        401: {"description": "Authentication required"},
    },
    deprecated=False,
)
async def get_user(user_id: int):
    """
    Retrieve user details by their unique ID.

    - **user_id**: Integer user ID
    - Returns full user profile including plan and credits
    """
    pass


# ─── Pydantic model with examples ───
from pydantic import BaseModel, Field

class UserCreate(BaseModel):
    name:  str = Field(..., min_length=1, max_length=100, example="Alice Smith")
    email: str = Field(..., example="alice@test.com")
    plan:  str = Field(default="free", example="premium")

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "name":  "Alice Smith",
                "email": "alice@test.com",
                "plan":  "premium",
            }]
        }
    }


# ─── Custom OpenAPI with security schemes ───
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # Add JWT security scheme
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type":         "http",
            "scheme":       "bearer",
            "bearerFormat": "JWT",
            "description":  "JWT access token",
        },
        "ApiKeyAuth": {
            "type": "apiKey",
            "in":   "header",
            "name": "X-API-Key",
        },
    }

    # Apply security globally
    openapi_schema["security"] = [{"BearerAuth": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


# ─── Mark endpoint with security ───
from fastapi import Security
from fastapi.security import HTTPBearer, APIKeyHeader

bearer_scheme = HTTPBearer()
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

@app.get(
    "/admin/stats",
    security=[{"BearerAuth": []}, {"ApiKeyAuth": []}],  # shows in Swagger
)
async def admin_stats(token: str = Security(bearer_scheme)):
    pass
```

### Q2: API versioning OpenAPI mein kaise handle karo?

**Answer:**
```python
# Multiple versioned apps → separate OpenAPI specs
app_v1 = FastAPI(title="My API v1", version="1.0.0", docs_url="/v1/docs")
app_v2 = FastAPI(title="My API v2", version="2.0.0", docs_url="/v2/docs")

# Mount both
from fastapi import FastAPI
main_app = FastAPI()
main_app.mount("/v1", app_v1)
main_app.mount("/v2", app_v2)

# Deprecation in OpenAPI
@app_v1.get("/users", deprecated=True)
async def list_users_v1():
    """
    ⚠️ Deprecated: Use `/v2/users` instead.
    This endpoint will be removed on 2025-12-31.
    """
    pass
```

---

# PART 3: SSE — Server-Sent Events

## What is SSE?
- **SSE** = one-way streaming from **server → client** over HTTP
- Client ek baar request karta hai → server continuously events push karta hai
- Native browser support (`EventSource` API)
- Text-based, `text/event-stream` content type
- **Auto-reconnect** built-in (browser automatically reconnect karta hai)

## Why SSE?
```
When to use SSE:
  ✓ LLM/AI response streaming (token-by-token — ChatGPT style!)
  ✓ Live notifications (order status, job progress)
  ✓ Live dashboard updates (prices, metrics)
  ✓ Log streaming
  ✓ One-way push — client sirf receive karta hai

SSE vs WebSocket vs Polling:
  SSE:       Simple, HTTP, auto-reconnect, one-way only
  WebSocket: Bidirectional, more complex, full-duplex
  Polling:   Simplest, wasteful, high latency

Why SSE for LLM streaming?
  OpenAI API SSE use karta hai for streaming responses
  FastAPI → Anthropic/OpenAI → SSE stream → browser
  Token milte hi browser mein dikhte hain (perceived speed!)
```

## How

### Q1: FastAPI mein SSE kaise implement karte hain?

**Answer:**
```python
import asyncio
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator

app = FastAPI()

# ─── Basic SSE response ───
async def event_generator(topic: str) -> AsyncGenerator[str, None]:
    """
    SSE format:
      data: <message>\n\n          ← simple message
      
      event: <type>\n              ← named event
      data: <json_data>\n\n
      
      id: <event_id>\n             ← for reconnection (Last-Event-ID)
      event: update\n
      data: <data>\n\n
      
      : <comment>\n\n              ← keep-alive ping
    """
    count = 0
    while True:
        count += 1
        yield f"data: {json.dumps({'count': count, 'topic': topic})}\n\n"
        await asyncio.sleep(1)


@app.get("/events/{topic}")
async def stream_events(topic: str):
    return StreamingResponse(
        event_generator(topic),
        media_type="text/event-stream",
        headers={
            "Cache-Control":        "no-cache",
            "X-Accel-Buffering":    "no",   # Nginx buffering disable karo!
            "Access-Control-Allow-Origin": "*",
        }
    )


# ─── LLM Streaming (ChatGPT-style) ───
import anthropic

@app.post("/chat/stream")
async def chat_stream(payload: dict):
    """
    INTERVIEW: LLM response streaming kaise karte hain?
    1. Anthropic/OpenAI API se streaming request karo
    2. FastAPI StreamingResponse mein wrap karo
    3. Client ko SSE format mein tokens bhejo
    Client token-by-token dekhta hai → better UX!
    """
    messages = payload.get("messages", [])

    async def generate():
        client = anthropic.AsyncAnthropic()

        async with client.messages.stream(
            model="claude-opus-4-5",
            max_tokens=1024,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                # SSE format: data: <token>\n\n
                yield f"data: {json.dumps({'token': text})}\n\n"

            # Final message with usage
            final = await stream.get_final_message()
            yield f"event: done\ndata: {json.dumps({'usage': final.usage.model_dump()})}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ─── Named events + reconnection ───
@app.get("/notifications/stream")
async def notification_stream(
    request: Request,
    last_event_id: Optional[str] = Header(None, alias="Last-Event-ID"),
    redis: Redis = Depends(get_redis),
):
    """
    last_event_id: Browser disconnected hone ke baad reconnect pe
                   ye last seen event ID bhejta hai
    Server: missed events replay karo from that ID
    """
    user_id = get_user_id(request)

    async def generate():
        event_id = int(last_event_id) if last_event_id else 0

        # Replay missed events
        missed = await redis.zrangebyscore(
            f"events:{user_id}", event_id + 1, "+inf"
        )
        for event_data in missed:
            event = json.loads(event_data)
            yield (
                f"id: {event['id']}\n"
                f"event: {event['type']}\n"
                f"data: {json.dumps(event['payload'])}\n\n"
            )

        # Live events
        pubsub = redis.pubsub()
        await pubsub.subscribe(f"user:{user_id}:notifications")

        async for message in pubsub.listen():
            # Check if client disconnected
            if await request.is_disconnected():
                await pubsub.unsubscribe()
                break

            if message["type"] == "message":
                event = json.loads(message["data"])
                event_id += 1
                yield (
                    f"id: {event_id}\n"
                    f"event: notification\n"
                    f"data: {json.dumps(event)}\n\n"
                )

            # Keepalive ping every 30s
            yield ": keepalive\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache"})


# ─── Frontend JavaScript ───
SSE_FRONTEND_JS = """
// Basic SSE
const evtSource = new EventSource('/events/orders');

evtSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Received:', data);
};

evtSource.onerror = () => {
  console.log('Disconnected — browser auto-reconnects in 3s');
};

// Named events
evtSource.addEventListener('notification', (event) => {
  const notif = JSON.parse(event.data);
  showNotification(notif);
});

// LLM Streaming
const response = await fetch('/chat/stream', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
  body: JSON.stringify({ messages: [...] }),
});

const reader = response.body.getReader();
const decoder = new TextDecoder();
let output = '';

while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  
  const chunk = decoder.decode(value);
  const lines = chunk.split('\\n');
  
  for (const line of lines) {
    if (line.startsWith('data: ')) {
      const data = JSON.parse(line.slice(6));
      if (data !== '[DONE]') {
        output += data.token;
        updateUI(output);  // Stream to UI
      }
    }
  }
}
"""
```

---

# PART 4: WebSocket vs SSE vs Polling — Comparison

## What
```
Polling:    Client regular intervals mein request karta hai
Long Poll:  Client request bhejta hai, server tab tak hold karta hai jab tak data na ho
SSE:        Server → Client one-way stream (HTTP)
WebSocket:  Full-duplex bidirectional connection (WS protocol)
```

## Why — When to Choose

### Q1: WebSocket vs SSE vs Polling — kab kaunsa?

**Answer:**
```
─── Polling ───
  How: setInterval(() => fetch('/updates'), 5000)
  
  Pros:  Simplest, works everywhere, no special server
  Cons:  Wasteful (requests even when no data), high latency
  
  Use when:
    ✓ Updates infrequent (every few minutes)
    ✓ Simplicity priority
    ✓ Legacy server infrastructure
  
  Example: Dashboard refresh every 5 minutes

─── Long Polling ───
  How: fetch('/updates') → server holds until data → client immediately re-requests
  
  Pros:  Near-real-time, works everywhere
  Cons:  Complex server (hold connections), high connection count
  
  Use when:
    ✓ Browser compatibility important
    ✓ SSE not supported (very rare now)

─── SSE (Server-Sent Events) ───
  How: EventSource API, text/event-stream
  
  Pros:  Simple, HTTP (proxies work), auto-reconnect, multiplexed in HTTP/2
  Cons:  One-way only (server → client), text only (binary awkward)
  
  Use when:
    ✓ Server → client push only (notifications, live feeds, LLM streaming)
    ✓ Client doesn't send data back in real-time
    ✓ Auto-reconnect behavior needed
  
  Examples: LLM token streaming, live notifications, log tail, progress updates

─── WebSocket ───
  How: ws:// or wss://, Upgrade: websocket handshake
  
  Pros:  Bidirectional, low latency, binary support, true full-duplex
  Cons:  More complex (state management, reconnect logic), proxy issues
  
  Use when:
    ✓ Client bhi data bhejta hai in real-time (typing indicators, game input)
    ✓ Bidirectional: chat, live collaboration, multiplayer games
    ✓ Low latency critical: trading, gaming
  
  Examples: Chat apps, Google Docs co-edit, multiplayer games, live bidding
```

```python
# ─── WebSocket in FastAPI ───
from fastapi import WebSocket, WebSocketDisconnect

class ConnectionManager:
    def __init__(self):
        self.active: dict[str, list[WebSocket]] = {}

    async def connect(self, room: str, ws: WebSocket):
        await ws.accept()
        self.active.setdefault(room, []).append(ws)

    def disconnect(self, room: str, ws: WebSocket):
        self.active[room].remove(ws)

    async def broadcast(self, room: str, message: dict):
        for ws in self.active.get(room, []):
            await ws.send_json(message)


manager = ConnectionManager()


@app.websocket("/ws/chat/{room_id}")
async def chat_websocket(websocket: WebSocket, room_id: str):
    """
    INTERVIEW: WebSocket connection lifecycle?
    1. HTTP GET /ws/chat/room1 + Upgrade: websocket
    2. Server: 101 Switching Protocols
    3. Full-duplex WS connection established
    4. Send/receive messages bidirectionally
    5. Either side sends CLOSE frame
    """
    await manager.connect(room_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            # Broadcast to all in room
            await manager.broadcast(room_id, {
                "user":    data["user"],
                "message": data["message"],
                "time":    datetime.utcnow().isoformat(),
            })
    except WebSocketDisconnect:
        manager.disconnect(room_id, websocket)
        await manager.broadcast(room_id, {"system": f"User left {room_id}"})
```

---

# PART 5: File Upload / Download API

## What & Why
```
What: Multipart form-data upload, chunked download, streaming
Why:  REST mein binary data handle karna JSON se alag hai
      Large files: memory mein load mat karo — stream karo
```

### Q1: File upload/download kaise implement karte hain?

**Answer:**
```python
from fastapi import UploadFile, File
import aiofiles
import os

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

@app.post("/upload")
async def upload_file(
    file:    UploadFile = File(...),
    user_id: int        = Depends(get_current_user_id),
):
    """
    INTERVIEW: Large file upload kaise handle karo?
    file.read() → memory mein load → bad for large files
    Streaming read with chunks → memory efficient
    """
    # Validate
    allowed_types = {"image/jpeg", "image/png", "application/pdf"}
    if file.content_type not in allowed_types:
        raise HTTPException(400, f"File type {file.content_type} not allowed")

    # Stream to disk (not entire file in memory)
    file_path = f"/uploads/{user_id}/{uuid.uuid4()}_{file.filename}"
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    size = 0
    async with aiofiles.open(file_path, "wb") as f:
        while chunk := await file.read(8192):  # 8KB chunks
            size += len(chunk)
            if size > MAX_FILE_SIZE:
                raise HTTPException(413, "File too large")
            await f.write(chunk)

    return {"filename": file.filename, "size": size, "path": file_path}


# ─── Streaming download ───
from fastapi.responses import StreamingResponse, FileResponse
import aiofiles

@app.get("/download/{file_id}")
async def download_file(file_id: str):
    """
    FileResponse:      entire file in memory → small files
    StreamingResponse: chunked → large files, memory efficient
    """
    file_path = get_file_path(file_id)

    # Option 1: FileResponse (small files, simple)
    # return FileResponse(file_path, filename="report.pdf")

    # Option 2: StreamingResponse (large files)
    async def file_stream():
        async with aiofiles.open(file_path, "rb") as f:
            while chunk := await f.read(65536):  # 64KB chunks
                yield chunk

    file_size = os.path.getsize(file_path)
    return StreamingResponse(
        file_stream(),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="report.pdf"',
            "Content-Length":      str(file_size),
            "Accept-Ranges":       "bytes",  # resume support
        }
    )
```

---

# PART 6: API Deprecation Lifecycle

## What, Why, How

### Q1: API endpoint deprecate kaise karte hain properly?

**Answer:**
```python
# ─── Sunset + Deprecation headers (RFC 8594) ───
from datetime import datetime, timezone

SUNSET_DATE = "2025-12-31T00:00:00Z"

class DeprecationMiddleware(BaseHTTPMiddleware):
    DEPRECATED_PATHS = {
        "/api/v1/users":  SUNSET_DATE,
        "/api/v1/posts":  SUNSET_DATE,
    }

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        path = request.url.path

        for deprecated_path, sunset in self.DEPRECATED_PATHS.items():
            if path.startswith(deprecated_path):
                response.headers["Deprecation"] = "true"
                response.headers["Sunset"]       = sunset
                response.headers["Link"]         = (
                    '</api/v2/users>; rel="successor-version"'
                )
                response.headers["Warning"]      = (
                    '299 - "This API version is deprecated. '
                    f'Migrate to v2 before {sunset}"'
                )
        return response

app.add_middleware(DeprecationMiddleware)


# ─── Deprecation in OpenAPI ───
@app.get("/api/v1/users", deprecated=True)
async def list_users_v1():
    """
    ⚠️ **DEPRECATED** — Use `/api/v2/users` instead.

    Sunset date: **2025-12-31**

    Migration guide: https://docs.myapp.com/migration/v1-to-v2
    """
    pass

# ─── Version lifecycle ───
# v1 release:    /api/v1 active
# v2 release:    /api/v2 active + /api/v1 gets Deprecation header
# Sunset notice: 6-12 months advance notice
# Sunset date:   /api/v1 returns 410 Gone (not 404)
# Cleanup:       /api/v1 removed from codebase
```

---

## Summary

| Concept | What | Why | Key Points |
|---------|------|-----|------------|
| CORS | Browser cross-origin policy | Security — prevent CSRF | `allow_origins`, `allow_credentials`, preflight OPTIONS |
| OpenAPI | API contract spec | Docs, client gen, testing | FastAPI auto-generates, customize with `get_openapi()` |
| SSE | HTTP one-way streaming | LLM tokens, live updates | `text/event-stream`, auto-reconnect, no binary |
| WebSocket | Full-duplex channel | Chat, real-time bidirectional | `ws://`, Upgrade header, WS protocol |
| File upload | Multipart/form-data | Binary data via REST | `UploadFile`, stream chunks, validate type+size |
| Deprecation | Sunset headers | API lifecycle mgmt | `Deprecation: true`, `Sunset: date`, `Link: successor` |

| Use SSE when | Use WebSocket when |
|---|---|
| Server → Client only | Bidirectional needed |
| LLM streaming | Chat, games, collaboration |
| Live notifications | Trading, live bidding |
| Log streaming | Typing indicators |
| Simple HTTP infrastructure | Low latency critical |
