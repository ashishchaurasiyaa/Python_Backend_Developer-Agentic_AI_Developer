# Server-Sent Events (SSE) — Streaming Deep Dive

## Why It Matters

SSE = lightweight server → client streaming. Use cases:
- **LLM token streaming** (ChatGPT-style typewriter)
- **Real-time notifications**
- **Live progress updates** (long jobs)
- **Stock tickers, dashboards**

vs WebSocket: SSE is HTTP-native (passes firewalls), auto-reconnect, simpler. WebSocket is bidirectional + binary.

Senior interview: "Stream LLM response to browser without WebSocket." → SSE.

---

## Core Concepts

### SSE Wire Protocol

```
HTTP/1.1 200 OK
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive

event: message
data: hello

event: progress
data: {"percent": 50}

id: 42
data: with id for resume

retry: 5000
data: tells client to retry after 5s if disconnect

: this is a comment / keep-alive ping

data: line 1
data: line 2

```

**Message format:**
- Empty line = message delimiter
- `data:` = the data
- `event:` = event name (default: 'message')
- `id:` = last-event-id for resume
- `retry:` = client reconnect delay in ms
- `:` = comment / heartbeat

### FastAPI SSE Endpoint

```python
from fastapi import FastAPI, Request
from sse_starlette.sse import EventSourceResponse
import asyncio


app = FastAPI()


@app.get("/stream")
async def stream(request: Request):
    async def event_generator():
        for i in range(100):
            # Check if client disconnected
            if await request.is_disconnected():
                break

            yield {
                "event": "progress",
                "id": str(i),
                "data": f"Step {i}/100",
            }
            await asyncio.sleep(0.1)

        yield {
            "event": "complete",
            "data": "done",
        }

    return EventSourceResponse(event_generator())
```

### LLM Token Streaming

```python
@app.post("/chat")
async def chat(message: str):
    async def stream_llm():
        # Stream from Claude/OpenAI
        async with httpx.AsyncClient() as client:
            async with client.stream(
                'POST',
                'https://api.anthropic.com/v1/messages',
                json={
                    'model': 'claude-sonnet-4-6',
                    'messages': [{'role': 'user', 'content': message}],
                    'stream': True,
                    'max_tokens': 1024,
                },
                headers={'x-api-key': API_KEY, 'anthropic-version': '2023-06-01'},
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith('data: '):
                        try:
                            chunk = json.loads(line[6:])
                            if chunk.get('type') == 'content_block_delta':
                                text = chunk['delta'].get('text', '')
                                yield {'data': text}
                        except json.JSONDecodeError:
                            pass

        yield {'event': 'done', 'data': '[DONE]'}

    return EventSourceResponse(stream_llm())
```

### Client (JavaScript)

```javascript
const evt = new EventSource('/stream');

evt.onmessage = (e) => {
  console.log('default message:', e.data);
};

evt.addEventListener('progress', (e) => {
  const data = JSON.parse(e.data);
  console.log(`Progress: ${data.percent}%`);
});

evt.addEventListener('complete', (e) => {
  evt.close();
});

evt.onerror = (e) => {
  // Auto-reconnect — EventSource does this automatically
};
```

### Last-Event-ID + Resume

Client sends `Last-Event-ID` header on reconnect. Server resumes from there:

```python
@app.get("/stream")
async def stream(request: Request, last_event_id: str | None = Header(None)):
    start_from = int(last_event_id or '0') + 1

    async def gen():
        for i in range(start_from, 1000):
            if await request.is_disconnected():
                break
            yield {'id': str(i), 'data': f'event {i}'}
            await asyncio.sleep(0.1)

    return EventSourceResponse(gen())
```

### Redis Pub/Sub Fan-Out

Multiple SSE consumers, single Redis channel:

```python
import redis.asyncio as aioredis


@app.get("/notifications")
async def notifications(request: Request, user=Depends(get_current_user)):
    r = aioredis.from_url("redis://localhost")
    pubsub = r.pubsub()
    await pubsub.subscribe(f'user:{user.id}:notifications')

    async def gen():
        try:
            async for msg in pubsub.listen():
                if msg['type'] != 'message':
                    continue
                if await request.is_disconnected():
                    break
                yield {'data': msg['data'].decode()}
        finally:
            await pubsub.unsubscribe()
            await pubsub.close()

    return EventSourceResponse(gen())


# Producer (e.g., from a worker):
async def notify_user(user_id, message):
    r = aioredis.from_url("redis://localhost")
    await r.publish(f'user:{user_id}:notifications', json.dumps(message))
```

### Heartbeats (Keep Connection Alive)

```python
async def stream_with_heartbeat():
    while True:
        # Send actual event or heartbeat every 15s
        # Heartbeat = comment (ignored by client)
        yield {'event': 'heartbeat', 'data': str(time.time())}
        await asyncio.sleep(15)
```

Or via `sse-starlette` ping option:

```python
return EventSourceResponse(gen(), ping=15)  # auto-comment every 15s
```

---

## How It Works Internally

### HTTP Long-Lived Connection

SSE = HTTP GET that never closes. Browser keeps connection open. Server streams in chunks (Transfer-Encoding: chunked).

### Auto-Reconnect

`EventSource` browser API auto-reconnects on connection drop. `retry:` field controls delay. Includes `Last-Event-ID` header.

### vs WebSocket

| | SSE | WebSocket |
|---|---|---|
| Direction | Server → Client only | Bidirectional |
| Protocol | HTTP | WS upgrade |
| Auto-reconnect | Yes (built-in) | Manual |
| Binary | No | Yes |
| Firewall-friendly | Yes | Sometimes blocked |
| Headers/cookies | Yes (standard HTTP) | Limited |

---

## Common Pitfalls

### 1. Buffering by Reverse Proxy

nginx buffers SSE → choppy. Disable:

```nginx
location /stream {
    proxy_pass http://app;
    proxy_buffering off;
    proxy_cache off;
    proxy_set_header Connection '';
    proxy_http_version 1.1;
    chunked_transfer_encoding off;
}
```

### 2. ASGI Server Timeout

Uvicorn `--timeout-keep-alive 75` default. For long streams, tune higher or send heartbeats.

### 3. Client Disconnect Not Detected

Without `request.is_disconnected()` check, server keeps generating events forever:

```python
async def gen():
    while True:
        if await request.is_disconnected():
            break  # critical!
        yield {...}
```

### 4. Multiple Connections per User

```python
# Browser opens 6 connections to same origin = throttled
# Use one SSE per user, multiplex events
```

### 5. CORS for SSE

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=['https://app.example.com'],
    allow_credentials=True,
)
```

### 6. Cache by CDN

Set headers to prevent caching:

```python
response.headers['Cache-Control'] = 'no-cache, no-store, no-transform'
response.headers['X-Accel-Buffering'] = 'no'  # for nginx
```

### 7. Memory Leak in Producer

If generator catches exception but Redis pubsub doesn't close → resource leak. Use try/finally.

---

## Interview Q&A

**Q1:** SSE vs WebSocket — kab kya use karoge?
**A:** SSE for one-way server → client (notifications, LLM streaming, progress). HTTP-native, auto-reconnect, simpler. WebSocket for bidirectional (chat), binary data, low-latency interactive. SSE wins on simplicity for one-way.

**Q2:** LLM streaming kaise implement karoge SSE se?
**A:** FastAPI endpoint returns EventSourceResponse. Internally calls LLM API with `stream=True`. For each token from LLM stream, yield `{data: token}` to client. Client uses EventSource API; JS appends each token to UI. Final `event: done`.

**Q3:** Reconnection + resume kaise implement karte ho?
**A:** Each event has `id`. Client (EventSource) sends `Last-Event-ID` header on reconnect. Server reads header, resumes from id+1. Persistent event log (Redis Streams, Postgres) backs the resume.

**Q4:** Multiple SSE consumers same data ke liye?
**A:** Redis Pub/Sub fan-out. Producer publishes to channel. Each SSE handler subscribes to channel + forwards messages. Decouples producer from N consumers. Or Redis Streams with consumer groups for delivery guarantees.

**Q5:** nginx + SSE issues kya hain?
**A:** Default buffering = events held until buffer fills. Disable: `proxy_buffering off`. Plus `proxy_read_timeout` high enough for long streams (default 60s). Disable gzip on event-stream (interferes with chunked encoding).

**Q6:** Heartbeat zaroori kyun hai?
**A:** (1) Detect connection drops fast. (2) Keep load balancer / proxy from timing out idle connection. (3) Client-side disconnect detection (EventSource only triggers `error` on read). Send comment line `:\n\n` every 15-30s.

**Q7:** Scale SSE to 100K concurrent connections?
**A:** ASGI server with high concurrency (uvicorn workers tuned). Stateless app — connection state in Redis. Each pod handles ~5-10K connections (FD limits + memory). Horizontal scale + sticky sessions for resume.

**Q8:** SSE production failure modes?
**A:** (1) Client disconnects but server keeps generating → memory leak (use `is_disconnected()`). (2) Producer crashes → consumers stuck waiting forever (heartbeat detects). (3) Proxy buffers → no real-time (disable buffering). (4) CORS issues (allow credentials). (5) Mobile networks drop idle connections.

---

## Real-World Use Cases

### 1. Anthropic-style Chat UI

LLM streams tokens → SSE to browser → JS appends to message div. User sees typewriter effect.

### 2. Long-Running Job Progress

```python
@app.post("/jobs/{job_id}/follow")
async def follow_job(job_id: str, request: Request):
    async def gen():
        while True:
            if await request.is_disconnected():
                return
            job = await db.get_job(job_id)
            yield {
                'event': 'status',
                'data': json.dumps({
                    'status': job.status,
                    'progress': job.progress,
                }),
            }
            if job.status in ('done', 'failed'):
                return
            await asyncio.sleep(2)
    return EventSourceResponse(gen())
```

### 3. Multi-User Notifications

Each user subscribes via SSE to their notifications channel.

---

## References

- [HTML5 SSE spec](https://html.spec.whatwg.org/multipage/server-sent-events.html)
- [sse-starlette](https://github.com/sysid/sse-starlette)
- Anthropic / OpenAI streaming docs
- nginx SSE tuning
