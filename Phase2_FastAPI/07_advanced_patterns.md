# FastAPI — Advanced Production Patterns
**Phase 2 FastAPI | Senior Backend + Agentic AI**

## Quick Concepts
- **Cursor pagination** = large datasets ke liye (offset se better for 10M+ rows)
- **Rate limiting** = per user/IP — Redis token bucket ya sliding window
- **API versioning** = backward-compatible changes — `/v1/`, `/v2/`
- **SSE** = Server-Sent Events — one-way real-time push (LLM streaming ke liye)
- **Streaming responses** = large files ya LLM output stream karo
- **Request deduplication** = idempotency keys — duplicate requests safe bana'o
- **Health checks** = liveness + readiness probes (Kubernetes ke liye)

---

## Interview Questions & Answers

### Q1: Cursor vs Offset pagination — kab kya use karte hain?
**Answer:**
```python
from fastapi import APIRouter, Query, Depends
from pydantic import BaseModel
from typing import Generic, TypeVar, Optional
import base64, json

T = TypeVar("T")

class CursorPage(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: Optional[str] = None   # opaque — client passes back
    prev_cursor: Optional[str] = None
    has_more: bool

class OffsetPage(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int

router = APIRouter()

# ─── Offset Pagination (simple, small datasets) ───
@router.get("/products", response_model=OffsetPage[dict])
async def list_products_offset(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db = Depends(get_db),
):
    offset = (page - 1) * page_size
    # SELECT * FROM products LIMIT :limit OFFSET :offset
    items  = await product_repo.list(db, limit=page_size, offset=offset)
    total  = await product_repo.count(db)
    return OffsetPage(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=-(-total // page_size),  # ceiling division
    )

# ─── Cursor Pagination (large datasets, consistent) ───
def encode_cursor(data: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(data).encode()).decode()

def decode_cursor(cursor: str) -> dict:
    try:
        return json.loads(base64.urlsafe_b64decode(cursor.encode()))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid cursor")

@router.get("/events", response_model=CursorPage[dict])
async def list_events_cursor(
    cursor: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db = Depends(get_db),
):
    """
    Cursor-based: SELECT * FROM events WHERE id > :last_id ORDER BY id LIMIT :limit+1
    No OFFSET — consistent even if rows are inserted between pages.
    """
    last_id = decode_cursor(cursor)["id"] if cursor else 0

    # Fetch limit+1 to know if there are more items
    items = await event_repo.list_after(db, after_id=last_id, limit=limit + 1)

    has_more = len(items) > limit
    items = items[:limit]

    next_cursor = encode_cursor({"id": items[-1]["id"]}) if has_more else None

    return CursorPage(items=items, next_cursor=next_cursor, has_more=has_more)

# WHY CURSOR > OFFSET for large data:
# - OFFSET 100000 scans 100000 rows before returning — slow!
# - Cursor uses indexed WHERE id > X — always O(1)
# - Consistent: new rows don't shift pages
```

---

### Q2: Rate limiting per user/IP — Redis sliding window kaise implement karte hain?
**Answer:**
```python
import time
import redis.asyncio as aioredis
from fastapi import Request, HTTPException

class RateLimiter:
    """
    Sliding window rate limiter using Redis sorted sets.
    Key = f"rate:{identifier}:{endpoint}"
    """
    def __init__(self, redis: aioredis.Redis):
        self.redis = redis

    async def check(
        self,
        identifier: str,    # user_id or IP address
        endpoint: str,      # route key e.g. "POST:/api/chat"
        limit: int,
        window_seconds: int,
    ) -> tuple[bool, dict]:
        """
        Returns (is_allowed, info_dict)
        """
        now = time.time()
        window_start = now - window_seconds
        key = f"rate:{identifier}:{endpoint}"

        async with self.redis.pipeline() as pipe:
            # Remove old entries outside window
            pipe.zremrangebyscore(key, 0, window_start)
            # Count requests in window
            pipe.zcard(key)
            # Add current request
            pipe.zadd(key, {str(now): now})
            # Set expiry
            pipe.expire(key, window_seconds)
            _, count, _, _ = await pipe.execute()

        remaining = max(0, limit - count - 1)
        reset_at = int(now) + window_seconds

        if count >= limit:
            return False, {
                "limit": limit,
                "remaining": 0,
                "reset": reset_at,
                "retry_after": window_seconds,
            }

        return True, {"limit": limit, "remaining": remaining, "reset": reset_at}


# ─── Rate limit middleware ───
from starlette.middleware.base import BaseHTTPMiddleware

class RateLimitMiddleware(BaseHTTPMiddleware):
    LIMITS = {
        "POST:/auth/login":    (5,  60),     # 5 per minute
        "POST:/api/chat":      (60, 60),     # 60 per minute
        "default":             (300, 60),    # 300 per minute
    }

    async def dispatch(self, request: Request, call_next):
        # Get identifier: user_id from JWT, else IP
        identifier = request.headers.get("X-User-ID") or request.client.host
        endpoint   = f"{request.method}:{request.url.path}"

        limit, window = self.LIMITS.get(endpoint, self.LIMITS["default"])

        limiter = RateLimiter(request.app.state.redis)
        allowed, info = await limiter.check(identifier, endpoint, limit, window)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded", "retry_after": info["retry_after"]},
                headers={
                    "X-RateLimit-Limit": str(info["limit"]),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(info["reset"]),
                    "Retry-After": str(info["retry_after"]),
                }
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"]     = str(info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
        response.headers["X-RateLimit-Reset"]     = str(info["reset"])
        return response
```

---

### Q3: API versioning kaise karte hain?
**Answer:**
```python
from fastapi import FastAPI, APIRouter

# ─── Strategy 1: URL prefix versioning (most common) ───
app = FastAPI()

v1_router = APIRouter(prefix="/v1")
v2_router = APIRouter(prefix="/v2")

@v1_router.get("/users/{user_id}")
async def get_user_v1(user_id: int):
    return {"id": user_id, "name": "Alice"}  # flat response

@v2_router.get("/users/{user_id}")
async def get_user_v2(user_id: int):
    return {                                   # nested + extra fields
        "data": {"id": user_id, "name": "Alice"},
        "meta": {"version": "2.0"}
    }

app.include_router(v1_router, tags=["v1"])
app.include_router(v2_router, tags=["v2"])

# ─── Strategy 2: Header versioning ───
from fastapi import Header

async def get_api_version(x_api_version: str = Header(default="1")):
    return int(x_api_version)

@app.get("/users/{user_id}")
async def get_user_versioned(
    user_id: int,
    version: int = Depends(get_api_version)
):
    if version == 2:
        return {"data": {"id": user_id}, "meta": {}}
    return {"id": user_id}  # v1 default

# ─── Deprecation warning ───
from fastapi import Response

@v1_router.get("/orders", deprecated=True)
async def list_orders_v1(response: Response):
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = "2025-12-31"
    response.headers["Link"] = '</v2/orders>; rel="successor-version"'
    return []
```

---

### Q4: SSE (Server-Sent Events) — LLM streaming kaise karte hain?
**Answer:**
```python
import asyncio
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import json

router = APIRouter()

# ─── Basic SSE ───
async def event_generator(topic: str):
    """Yield SSE-formatted events."""
    for i in range(10):
        data = {"message": f"Update {i} for {topic}", "index": i}
        yield f"data: {json.dumps(data)}\n\n"   # SSE format: "data: ...\n\n"
        await asyncio.sleep(0.5)
    yield "data: [DONE]\n\n"  # OpenAI-style termination

@router.get("/events/stream")
async def stream_events(topic: str = "default"):
    return StreamingResponse(
        event_generator(topic),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # nginx buffering disable
        }
    )

# ─── LLM Streaming (Anthropic Claude style) ───
async def llm_stream_generator(prompt: str):
    """Stream LLM response token by token."""
    import anthropic
    client = anthropic.AsyncAnthropic()

    async with client.messages.stream(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    ) as stream:
        async for text in stream.text_stream:
            # SSE format with data
            chunk = {"type": "token", "text": text}
            yield f"data: {json.dumps(chunk)}\n\n"

        # Final message with usage stats
        message = await stream.get_final_message()
        final = {
            "type": "done",
            "input_tokens": message.usage.input_tokens,
            "output_tokens": message.usage.output_tokens,
        }
        yield f"data: {json.dumps(final)}\n\n"

@router.get("/chat/stream")
async def stream_chat(prompt: str):
    return StreamingResponse(
        llm_stream_generator(prompt),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

# ─── Frontend (JavaScript) ───
# const es = new EventSource('/chat/stream?prompt=Hello');
# es.onmessage = (event) => {
#     const data = JSON.parse(event.data);
#     if (data.type === 'done') { es.close(); return; }
#     appendToken(data.text);
# };
```

---

### Q5: Idempotency keys — duplicate request prevention kaise karte hain?
**Answer:**
```python
from fastapi import Header
import hashlib

async def idempotency_check(
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    redis: aioredis.Redis = Depends(get_redis),
) -> Optional[str]:
    return idempotency_key

@router.post("/payments", status_code=201)
async def create_payment(
    payload: PaymentRequest,
    idempotency_key: Optional[str] = Depends(idempotency_check),
    redis: aioredis.Redis = Depends(get_redis),
):
    """
    Idempotent payment endpoint.
    Same Idempotency-Key = return cached response (no double charge).
    """
    if idempotency_key:
        cache_key = f"idem:{idempotency_key}"
        cached = await redis.get(cache_key)
        if cached:
            # Return same response as first request
            return json.loads(cached)

    # Process payment (only once)
    result = await payment_service.charge(payload)

    if idempotency_key:
        # Cache for 24 hours
        await redis.setex(cache_key, 86400, json.dumps(result))

    return result
```

---

### Q6: Health checks + Kubernetes readiness/liveness probes?
**Answer:**
```python
from fastapi import APIRouter
from pydantic import BaseModel
import time

health_router = APIRouter(tags=["health"])

class HealthStatus(BaseModel):
    status: str           # "healthy" | "degraded" | "unhealthy"
    uptime_seconds: float
    checks: dict[str, str]

START_TIME = time.time()

@health_router.get("/health/live")
async def liveness():
    """Kubernetes liveness — app is running (not deadlocked)."""
    return {"status": "ok"}

@health_router.get("/health/ready", response_model=HealthStatus)
async def readiness(
    db = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """Kubernetes readiness — app is ready to receive traffic."""
    checks = {}
    overall = "healthy"

    # Check DB
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {str(e)[:50]}"
        overall = "unhealthy"

    # Check Redis
    try:
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {str(e)[:50]}"
        overall = "degraded"  # degraded but not down

    status_code = 200 if overall in ("healthy", "degraded") else 503

    return JSONResponse(
        status_code=status_code,
        content=HealthStatus(
            status=overall,
            uptime_seconds=time.time() - START_TIME,
            checks=checks
        ).model_dump()
    )

# Kubernetes config:
# livenessProbe:
#   httpGet:
#     path: /health/live
#     port: 8000
#   initialDelaySeconds: 10
#   periodSeconds: 30
#
# readinessProbe:
#   httpGet:
#     path: /health/ready
#     port: 8000
#   initialDelaySeconds: 5
#   periodSeconds: 10
```

---

### Q7: Large file download — streaming response?
**Answer:**
```python
import aiofiles
from fastapi.responses import StreamingResponse, FileResponse

CHUNK_SIZE = 1024 * 1024  # 1 MB

@router.get("/files/{filename}")
async def download_file(filename: str):
    file_path = f"/data/files/{filename}"

    # ─── Option 1: FileResponse (simple, for known files) ───
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/octet-stream"
    )

@router.get("/export/large-dataset")
async def download_large_csv():
    """Stream large CSV without loading into memory."""

    async def generate_csv():
        yield "id,name,email\n"          # header
        for i in range(1_000_000):
            yield f"{i},User{i},u{i}@x.com\n"
            if i % 10000 == 0:
                await asyncio.sleep(0)   # yield control to event loop

    return StreamingResponse(
        generate_csv(),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=export.csv"
        }
    )

@router.get("/files/stream/{filename}")
async def stream_file(filename: str):
    """Async file streaming — 1MB chunks."""
    file_path = f"/data/files/{filename}"

    async def file_chunks():
        async with aiofiles.open(file_path, "rb") as f:
            while chunk := await f.read(CHUNK_SIZE):
                yield chunk

    return StreamingResponse(
        file_chunks(),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
```

---

## Production FastAPI App Structure

```
app/
├── main.py              # FastAPI app, middleware, routers, lifespan
├── config.py            # Settings with pydantic-settings
├── database.py          # Engine, session factory, get_db dependency
├── dependencies.py      # Shared deps: auth, redis, pagination
├── exceptions.py        # AppException subclasses + handlers
├── schemas/             # Pydantic request/response models
│   ├── base.py          # BaseResponse, PaginatedPage, ErrorDetail
│   ├── user.py
│   └── order.py
├── models/              # SQLAlchemy ORM models
│   ├── base.py          # Base, TimestampMixin
│   ├── user.py
│   └── order.py
├── repositories/        # DB access layer (no business logic)
│   ├── base.py          # Generic CRUD
│   ├── user.py
│   └── order.py
├── services/            # Business logic (uses repositories)
│   ├── user.py
│   └── order.py
├── routers/             # APIRouter per domain
│   ├── auth.py
│   ├── users.py
│   └── orders.py
└── tests/
    ├── conftest.py
    ├── test_users.py
    └── test_orders.py
```

---

## Summary: Senior FastAPI Interview Checklist

| Topic | Key Points |
|---|---|
| Pagination | Cursor for large data, offset for small; encode cursor as base64 |
| Rate limiting | Redis sliding window; per-user AND per-endpoint |
| API versioning | URL prefix `/v1/`; deprecation headers; no breaking changes |
| SSE streaming | `StreamingResponse` + `text/event-stream`; `X-Accel-Buffering: no` |
| LLM streaming | `async for text in stream.text_stream` → SSE chunks |
| Idempotency | `Idempotency-Key` header + Redis cache = no double charges |
| Health checks | `/health/live` (liveness) + `/health/ready` (readiness) for K8s |
| File streaming | `StreamingResponse` + async generator + 1MB chunks |
| Error response | `BaseResponse[T]` wrapper; `ErrorDetail` with `code` field |
