# 02 — Server-Sent Events (SSE)

> One-way server → client streaming over HTTP. Simpler than WebSocket. Auto-reconnect built in. Underrated.

---

## What SSE Is

A long-lived HTTP response with `Content-Type: text/event-stream`. Server keeps connection open and writes formatted events as they happen.

```
GET /events HTTP/1.1
Accept: text/event-stream
Cache-Control: no-cache

← HTTP/1.1 200 OK
← Content-Type: text/event-stream
← (connection stays open)
← data: hello
←
← data: world
←
```

---

## Why SSE Over WebSocket

| | SSE | WebSocket |
|---|---|---|
| Direction | Server → Client | Bidirectional |
| Protocol | HTTP | TCP upgrade |
| Reconnect | Auto | Manual |
| Last-Event-ID | Native (resume from offset) | DIY |
| Proxy/LB | Just HTTP — works everywhere | Needs config |
| Binary | No | Yes |
| Browser support | Native (`EventSource`) | Native |

**Use SSE when:**
- Server-to-client only (notifications, live data feeds).
- You want simple infra (just HTTP).
- Reconnect / replay matters.

**Use WebSocket when:**
- Bidirectional (chat, games).
- Binary data.

---

## Event Format

```
event: <type>     (optional, default "message")
id: <id>          (optional, for resume)
retry: <ms>       (optional, retry delay hint)
data: <line 1>
data: <line 2>
                  (empty line ends event)
```

Example:
```
event: new_order
id: 42
data: {"id": 42, "amount": 100}

event: status_update
id: 43
data: {"order_id": 42, "status": "paid"}
```

---

## FastAPI SSE

### Manual implementation
```python
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
import asyncio

app = FastAPI()

async def event_generator(request: Request):
    counter = 0
    while True:
        if await request.is_disconnected():
            break

        counter += 1
        yield f"id: {counter}\n"
        yield f"event: tick\n"
        yield f"data: {{\"count\": {counter}}}\n\n"
        await asyncio.sleep(1)

@app.get("/events")
async def events(request: Request):
    return StreamingResponse(
        event_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable proxy buffering
        }
    )
```

### Using `sse-starlette`
```python
from sse_starlette.sse import EventSourceResponse

async def event_generator():
    while True:
        yield {"event": "tick", "data": "{\"count\": 1}"}
        await asyncio.sleep(1)

@app.get("/events")
async def events():
    return EventSourceResponse(event_generator())
```

Library handles formatting, ping events, disconnect detection.

---

## Browser-Side

```javascript
const es = new EventSource("/events");

es.onmessage = (event) => {
    console.log("default message:", event.data);
};

es.addEventListener("new_order", (event) => {
    const order = JSON.parse(event.data);
    handleOrder(order);
});

es.onerror = (err) => {
    console.error(err);
    // Browser auto-reconnects (no need to handle)
};

// Close manually
es.close();
```

### Last-Event-ID for Resume
On reconnect, browser sends `Last-Event-ID` header:
```
GET /events HTTP/1.1
Last-Event-ID: 42
```

Server should replay events since that ID:
```python
async def event_generator(request: Request):
    last_id = int(request.headers.get("Last-Event-ID", 0))

    # Replay missed events
    missed = await db.fetch_events(since_id=last_id)
    for evt in missed:
        yield f"id: {evt.id}\n"
        yield f"data: {evt.data}\n\n"

    # Live stream
    async for evt in live_event_stream():
        yield f"id: {evt.id}\n"
        yield f"data: {evt.data}\n\n"
```

Resume semantics → built-in fault tolerance for clients on flaky networks.

---

## Heartbeat

To keep connection alive through proxies, send periodic comments:
```
: heartbeat\n\n
```

Client ignores them. Prevents 60s timeout idle disconnects.

```python
async def event_generator():
    last_event = time.time()
    while True:
        if time.time() - last_event > 15:
            yield ": heartbeat\n\n"
            last_event = time.time()
        # ... actual events
```

`sse-starlette` does this automatically with `ping=15` param.

---

## Use Cases

### Live notifications
```
Server pushes:
  data: {"type":"order_paid", "order_id":42}
```

### Progress updates (long-running tasks)
```
data: {"step":"validating", "progress":10}
data: {"step":"processing", "progress":50}
data: {"step":"done", "progress":100, "result":{"id":42}}
```

### Live dashboards
Real-time metrics streaming.

### Chat (one-way; sending via separate POST)
- POST /chat → store message
- SSE /chat/listen → receive new messages

### LLM streaming responses
ChatGPT-like token-by-token streaming.

```python
async def stream_llm(prompt):
    async with llm_client.stream(prompt) as resp:
        async for token in resp:
            yield {"event": "token", "data": token}
        yield {"event": "done", "data": ""}
```

OpenAI's API uses SSE.

---

## Pros vs Cons

### Pros
- Simple HTTP — works with any infra.
- Auto-reconnect built into browsers.
- Last-Event-ID resume.
- No protocol upgrade.
- Easy to debug with curl.

### Cons
- One-way only (need POST for client→server).
- Text only (no binary).
- IE doesn't support (whoever cares).
- Connections per browser per origin limited (6 in HTTP/1.1, unlimited in HTTP/2+).

---

## SSE Over HTTP/2 (Important)

In HTTP/1.1, browsers limit ~6 connections per origin. If you have 6 tabs of your app open, the 7th can't connect.

HTTP/2 multiplexes streams over one connection → no limit.

**Always serve SSE over HTTP/2 (or HTTP/3) in production.**

---

## Authentication

SSE is regular HTTP, so:
- Cookies work (with CORS + credentials).
- Authorization headers don't work natively with `EventSource` (no header support).

### Workaround for Auth header
```javascript
// Use fetch + polyfilled EventSource
import { EventSourcePolyfill } from "event-source-polyfill";

const es = new EventSourcePolyfill("/events", {
  headers: { "Authorization": `Bearer ${token}` }
});
```

Or use cookie auth.

---

## Scaling SSE

### Single server
Easy. Each client has one open connection.

### Multi-server
Need a backplane to route events to the right server.

```
Event published → Redis pub/sub →
                          ↓
                  Each app server subscribes →
                  Pushes to its connected clients
```

(See file 03 for backplane patterns.)

---

## Backpressure

SSE = TCP underneath. If client slow, TCP slows server's writes.

In async Python:
```python
async def event_generator():
    queue = asyncio.Queue(maxsize=100)

    async def producer():
        async for evt in event_source:
            try:
                queue.put_nowait(evt)
            except asyncio.QueueFull:
                pass  # drop event

    asyncio.create_task(producer())

    while True:
        evt = await queue.get()
        yield format_sse(evt)
```

---

## Proxy Configuration

### NGINX
```nginx
location /events {
    proxy_pass http://backend;
    proxy_buffering off;          # CRITICAL for SSE
    proxy_cache off;
    proxy_set_header Connection '';
    proxy_http_version 1.1;
    chunked_transfer_encoding off;
    proxy_read_timeout 24h;
}
```

`proxy_buffering off` is the #1 SSE gotcha — without it, events are buffered until response complete (never).

### Headers to set
```
Cache-Control: no-cache
X-Accel-Buffering: no   (NGINX-specific, disable buffering)
Connection: keep-alive
Content-Type: text/event-stream
```

---

## Compression

Gzip can cause buffering issues with SSE. Either disable or use streaming-compatible:

```nginx
location /events {
    gzip off;
    proxy_pass http://backend;
}
```

Some servers do streaming compression that works. Test in your env.

---

## Common Mistakes

### 1. Forgetting double newline
```
data: hello\n        ← single newline = not yet sent
data: hello\n\n     ← double newline = event complete
```

### 2. Buffering enabled in proxy
Client sees nothing until server closes connection.

### 3. Not setting Content-Type
```
Content-Type: text/event-stream    ← required
```

Without it, browsers don't parse as SSE.

### 4. Sending too much in `data:`
SSE clients re-assemble multi-line. But huge JSON payloads break some parsers.

### 5. No heartbeat
Connection killed at proxy timeout. Add `: ping\n\n` every 15s.

---

## Comparing to Alternatives

| Use case | SSE | WebSocket | Polling |
|---|---|---|---|
| Server → client only | ✓ ideal | overkill | wasteful |
| Live LLM tokens | ✓ used by OpenAI | works | bad |
| Chat | partial (only receive) | ✓ ideal | bad |
| Real-time dashboard | ✓ | ✓ | acceptable |
| File upload progress | ✓ ideal | ✓ | bad |
| Bidirectional game | bad | ✓ ideal | bad |
| Mobile app | partial (battery cost from open conn) | partial | better with push |

---

## Sample Production Setup

```python
# app/sse_router.py
from fastapi import APIRouter, Request, Depends
from sse_starlette.sse import EventSourceResponse
import asyncio
import redis.asyncio as redis

router = APIRouter()
r = redis.from_url("redis://localhost")

async def event_generator(user_id: str, last_id: int):
    # Replay missed events
    missed = await db.fetch_events_since(user_id, last_id)
    for evt in missed:
        yield {"id": str(evt.id), "event": evt.type, "data": evt.payload}

    # Subscribe to user's pub/sub channel
    pubsub = r.pubsub()
    await pubsub.subscribe(f"user:{user_id}")
    try:
        async for msg in pubsub.listen():
            if msg["type"] != "message": continue
            data = json.loads(msg["data"])
            yield {"id": data["id"], "event": data["type"], "data": data["payload"]}
    finally:
        await pubsub.unsubscribe(f"user:{user_id}")

@router.get("/events")
async def events(
    request: Request,
    user=Depends(get_current_user)
):
    last_id = int(request.headers.get("Last-Event-ID", 0))
    return EventSourceResponse(event_generator(user.id, last_id))
```

---

## TL;DR

- SSE = one-way server-pushed events over HTTP.
- Format: `event:`, `id:`, `data:`, blank line ends event.
- Browser auto-reconnects + sends `Last-Event-ID`.
- Serve over HTTP/2 in production.
- Disable proxy buffering.
- Heartbeat every 15s.
- Use for notifications, dashboards, LLM streaming.
- Simpler than WebSocket when bidirectional isn't needed.
