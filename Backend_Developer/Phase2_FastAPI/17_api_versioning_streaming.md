# API Versioning + Streaming Responses

> **Interview angle:** "API breaking change karna hai bina clients tode — kya karoge?"
> **+** "10GB JSON response bhejna hai memory mein 10GB load kiye bina — kaise?"

---

## PART 1: API Versioning

### 1. Why Version APIs?

- Old clients (mobile apps, integrations) can't update overnight
- Breaking changes: removed field, renamed endpoint, changed response shape
- Support window: 6-12 months for old versions typically
- Without versioning: every deploy is a breaking change

---

### 2. Four Versioning Strategies

| Strategy | Example | Pros | Cons |
|---|---|---|---|
| **URL Path** | `/v1/users` | Visible, easy to route | URL pollution |
| **Header** | `Accept-Version: v1` | Clean URLs | Less discoverable |
| **Query Param** | `/users?version=1` | Easy testing | Logs noisy |
| **Content Negotiation** | `Accept: application/vnd.api.v1+json` | RESTful, semantic | Complex |

**Most production: URL Path versioning** (Stripe, GitHub, Twitter use this).

---

### 3. URL Path Versioning in FastAPI

```python
from fastapi import APIRouter, FastAPI

app = FastAPI()

v1 = APIRouter(prefix="/v1")
v2 = APIRouter(prefix="/v2")

@v1.get("/users/{id}")
async def get_user_v1(id: int):
    return {"id": id, "name": "Ashish"}     # old shape

@v2.get("/users/{id}")
async def get_user_v2(id: int):
    return {                                 # new shape
        "id": id,
        "profile": {"first_name": "Ashish", "last_name": ""},
        "_links": {"self": f"/v2/users/{id}"},
    }

app.include_router(v1)
app.include_router(v2)
```

---

### 4. Header-Based Versioning

```python
from fastapi import FastAPI, Header, HTTPException

app = FastAPI()

@app.get("/users/{id}")
async def get_user(
    id: int,
    api_version: str = Header("v1", alias="X-API-Version"),
):
    if api_version == "v1":
        return {"id": id, "name": "Ashish"}
    elif api_version == "v2":
        return {"id": id, "profile": {...}}
    raise HTTPException(400, f"Unsupported version: {api_version}")
```

---

### 5. Stripe's API Versioning (date-based)

```
Stripe-Version: 2024-04-10
```
Each version = snapshot of API on that date. Customer pins a version, gets stable behavior.

```python
@app.get("/charges")
async def list_charges(stripe_version: str = Header(...)):
    version_date = parse_date(stripe_version)
    if version_date < date(2023, 1, 1):
        return legacy_format()
    elif version_date < date(2024, 4, 10):
        return mid_format()
    return current_format()
```

---

### 6. Deprecation Strategy

```python
@app.get("/v1/users")
async def list_v1(response: Response):
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = "Wed, 31 Dec 2025 23:59:59 GMT"
    response.headers["Link"] = '</v2/users>; rel="successor-version"'
    # ... old logic
```

Standard RFCs:
- `Deprecation: true` (RFC 8594)
- `Sunset: <date>` — when it will be removed
- `Link: rel="successor-version"` — point to new

---

### 7. Backward-Compatible Changes (don't need new version)

✅ **Additive changes (safe):**
- New optional fields in response
- New optional query params
- New endpoints
- New enum values (if clients don't reject unknowns)

❌ **Breaking changes (need new version):**
- Removing/renaming fields
- Changing field types (int → string)
- Stricter validation (was optional, now required)
- Changed default behavior

---

### 8. Multi-Version Code Maintenance

### Option A: Separate files per version (cleanest)
```
app/
├── v1/
│   └── users.py
└── v2/
    └── users.py
```

### Option B: Shared logic + version-specific schemas
```python
from app.services.users import UserService

@v1.get("/users/{id}")
async def get_v1(id: int):
    user = await UserService.get(id)
    return UserSchemaV1.from_orm(user)

@v2.get("/users/{id}")
async def get_v2(id: int):
    user = await UserService.get(id)
    return UserSchemaV2.from_orm(user)
```

---

## PART 2: Streaming Responses

### 9. Why Streaming?

**Use cases:**
- Export 1M rows as CSV (don't load all in memory)
- LLM streaming (token-by-token)
- Real-time updates (logs, events)
- Large file downloads
- Progress updates during long tasks

**Without streaming:**
- 10GB response = 10GB RAM
- Client waits until ALL data ready
- Timeout if takes > 30s

**With streaming:**
- Constant memory regardless of size
- Client sees data immediately
- No timeout on long operations

---

### 10. FastAPI Streaming Patterns

### Pattern A: `StreamingResponse` with generator
```python
from fastapi.responses import StreamingResponse

async def csv_generator():
    yield "id,name,email\n"            # header
    async for row in db.stream_users():
        yield f"{row.id},{row.name},{row.email}\n"

@app.get("/users.csv")
async def download_csv():
    return StreamingResponse(
        csv_generator(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=users.csv"}
    )
```

### Pattern B: NDJSON (newline-delimited JSON)
```python
import json

async def ndjson_users():
    async for user in fetch_users():
        yield json.dumps(user.dict()) + "\n"

@app.get("/users.ndjson")
async def ndjson():
    return StreamingResponse(ndjson_users(), media_type="application/x-ndjson")
```

Client reads line-by-line — perfect for big datasets, log streams.

### Pattern C: Server-Sent Events (SSE)
Browser-friendly, one-way real-time updates.
```python
from fastapi.responses import StreamingResponse

async def event_stream():
    for i in range(100):
        event = {"event": "progress", "data": json.dumps({"step": i})}
        yield f"event: {event['event']}\ndata: {event['data']}\n\n"
        await asyncio.sleep(0.5)

@app.get("/progress")
async def progress():
    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

Browser JS:
```javascript
const evtSource = new EventSource("/progress");
evtSource.addEventListener("progress", (e) => {
    const data = JSON.parse(e.data);
    console.log("Step:", data.step);
});
```

### Pattern D: Chunked file download
```python
@app.get("/large-file")
async def large_file():
    async def file_iterator():
        with open("/path/to/big.bin", "rb") as f:
            while chunk := f.read(8192):
                yield chunk
    return StreamingResponse(file_iterator(), media_type="application/octet-stream")
```

For very large files, prefer `FileResponse` (uses sendfile syscall = faster).

### Pattern E: LLM token streaming
```python
async def llm_stream(prompt: str):
    async for token in openai_client.chat.completions.stream(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
    ):
        if token.choices[0].delta.content:
            yield f"data: {token.choices[0].delta.content}\n\n"
    yield "data: [DONE]\n\n"

@app.post("/chat/stream")
async def chat_stream(prompt: str):
    return StreamingResponse(llm_stream(prompt), media_type="text/event-stream")
```

---

### 11. Streaming Database Results

### Async SQLAlchemy (with server-side cursor)
```python
from sqlalchemy.ext.asyncio import AsyncSession

async def stream_users(session: AsyncSession):
    result = await session.stream(select(User))
    async for row in result.scalars():
        yield row
```

### Postgres named cursor (no client-side buffering)
```python
async with engine.connect() as conn:
    async with conn.stream(text("SELECT * FROM users")) as result:
        async for row in result:
            yield row
```

---

### 12. SSE vs WebSocket

| Feature | SSE | WebSocket |
|---|---|---|
| Direction | Server → Client only | Bidirectional |
| Protocol | HTTP/1.1 + HTTP/2 | Upgrade from HTTP |
| Reconnect | Automatic by browser | Manual |
| Behind proxies | Works (just HTTP) | Sometimes blocked |
| Browser API | EventSource | WebSocket |
| Use case | Notifications, progress, AI streaming | Chat, gaming, full duplex |

**Default to SSE for one-way streams** — simpler, more compatible.

---

### 13. Chunked Transfer Encoding

HTTP `Transfer-Encoding: chunked` lets server send unknown-length response in chunks.

```
HTTP/1.1 200 OK
Transfer-Encoding: chunked

7\r\n
Hello, \r\n
6\r\n
World!\r\n
0\r\n
\r\n
```

FastAPI's `StreamingResponse` uses this automatically when content length unknown.

---

### 14. Common Pitfalls

### Pitfall 1: Buffer middleware breaking streaming
GZip middleware buffers the response → defeats streaming.

**Fix:** Add streaming exemption:
```python
@app.middleware("http")
async def conditional_compress(request, call_next):
    response = await call_next(request)
    if response.media_type == "text/event-stream":
        return response   # don't compress
    return await gzip_response(response)
```

### Pitfall 2: Nginx buffering
Nginx buffers responses by default → client doesn't see chunks.

**Fix:** Add headers:
```python
response.headers["X-Accel-Buffering"] = "no"
response.headers["Cache-Control"] = "no-cache"
```

Or Nginx config:
```nginx
location /stream {
    proxy_buffering off;
}
```

### Pitfall 3: SSE connection limit (6 per origin)
Browsers cap SSE/HTTP1.1 connections at ~6 per origin. Use HTTP/2 to bypass.

### Pitfall 4: Forgetting flush
Some clients buffer until newline. Always end SSE event with `\n\n`.

### Pitfall 5: Error handling mid-stream
```python
async def gen():
    try:
        yield first_chunk
        yield second_chunk
        raise SomeError("oops")
    except Exception as e:
        # Can't change status code mid-stream!
        # Emit error event
        yield f"event: error\ndata: {str(e)}\n\n"
```

---

### 15. Performance Tips

- Use `media_type` to set correct MIME type
- For files: `FileResponse` > `StreamingResponse` (sendfile)
- For DB streams: server-side cursors (no client buffer)
- For LLM: yield as soon as token arrives (don't batch)
- Set `X-Accel-Buffering: no` for SSE behind Nginx
- Monitor open connection count (each stream is long-lived)

---

## 16. Interview Questions

**Q1: API versioning strategies?**
URL path (Stripe, GitHub), Header (Accept-Version), Content negotiation (Accept: vnd.api.v1+json), Query param. URL path most common.

**Q2: Breaking vs non-breaking changes?**
Breaking: remove field, rename, type change, stricter validation. Non-breaking: add optional field/endpoint, new enum (if clients tolerant).

**Q3: Streaming kab use karte?**
- Large datasets (CSV/NDJSON export)
- LLM token streaming
- Real-time progress
- Server-sent events for notifications

**Q4: SSE vs WebSocket?**
SSE: one-way, simpler, auto-reconnect, HTTP. WebSocket: bidirectional, requires upgrade, more setup.

**Q5: Nginx mein streaming kyu break?**
Default buffering. Set `proxy_buffering off` or `X-Accel-Buffering: no` header.

**Q6: 1M rows export kaise?**
Streaming response + async DB cursor + chunked transfer. Yields per row, constant memory.

**Q7: Stripe ka date-based versioning?**
Customer pins date. Server snapshots API behavior at that date. No URL pollution. Better than v1/v2 for fine-grained evolution.

---

## 17. Best Practices

### Versioning
1. Pick ONE strategy and stick to it
2. Document sunset dates clearly
3. Use `Deprecation`/`Sunset` headers
4. Test all supported versions in CI
5. Migrate clients gradually (analytics on version usage)
6. Limit to 2-3 supported versions max

### Streaming
1. Stream by default for large responses (CSV, exports)
2. Disable Nginx buffering for SSE
3. Use `FileResponse` for static files
4. Set proper `Content-Type` (text/event-stream, application/x-ndjson)
5. Handle disconnects (client may close mid-stream)
6. Monitor memory — generators should be lazy
7. Heartbeat in long-lived SSE (every 30s, send comment line)

---

## Related
- [[13_asgi_internals_uvicorn_tuning]]
- [[15_websocket_scaling_patterns]] — bidirectional alternative
- [[03_middleware_websockets]]
