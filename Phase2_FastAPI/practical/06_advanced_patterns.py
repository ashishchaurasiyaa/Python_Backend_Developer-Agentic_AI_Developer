"""
PHASE 2 FastAPI — Practical 06: Advanced Patterns
Run: uvicorn 06_advanced_patterns:app --reload
Docs: http://127.0.0.1:8000/docs

Topics:
  - Cursor + Offset pagination
  - Rate limiting (sliding window)
  - API versioning (/v1 /v2)
  - SSE / LLM streaming
  - Idempotency keys
  - Health checks (liveness + readiness)
  - Large file streaming
"""

from __future__ import annotations

import asyncio
import base64
import json
import time
import uuid
from contextlib import asynccontextmanager
from typing import Annotated, Any, Generic, Optional, TypeVar

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

T = TypeVar("T")

START_TIME = time.time()


# ═══════════════════════════════════════════════════════
# SECTION 1: Response Models
# ═══════════════════════════════════════════════════════

class OffsetPage(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool


class CursorPage(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: Optional[str] = None
    prev_cursor: Optional[str] = None
    has_more: bool
    count: int


class Product(BaseModel):
    id: int
    name: str
    price: float
    category: str
    created_at: float


class Event(BaseModel):
    id: int
    title: str
    user_id: int
    timestamp: float


# ─── Fake data ───
PRODUCTS: list[dict] = [
    {"id": i, "name": f"Product {i}", "price": float(i * 100),
     "category": ["electronics", "clothing", "books"][i % 3],
     "created_at": time.time() - i * 3600}
    for i in range(1, 51)  # 50 products
]

EVENTS: list[dict] = [
    {"id": i, "title": f"Event {i}", "user_id": (i % 5) + 1, "timestamp": time.time() - i * 60}
    for i in range(1, 101)  # 100 events
]

# Simulated stores
REDIS_STORE: dict[str, Any] = {}      # rate limit + cache
IDEMPOTENCY_CACHE: dict[str, Any] = {}  # idempotency key → response


# ═══════════════════════════════════════════════════════
# SECTION 2: Pagination
# ═══════════════════════════════════════════════════════

def encode_cursor(data: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(data).encode()).decode()

def decode_cursor(cursor: str) -> dict:
    try:
        return json.loads(base64.urlsafe_b64decode(cursor.encode()))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid cursor value")


v1_router = APIRouter(prefix="/v1", tags=["v1 — Offset Pagination"])
v2_router = APIRouter(prefix="/v2", tags=["v2 — Cursor Pagination"])

# ─── v1: Offset pagination ───
@v1_router.get("/products", response_model=OffsetPage[Product])
async def list_products_offset(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    category: Optional[str] = Query(None),
):
    """
    OFFSET pagination — simple but slow on large tables.
    Consistent only when data doesn't change between pages.
    """
    filtered = PRODUCTS
    if category:
        filtered = [p for p in PRODUCTS if p["category"] == category]

    total = len(filtered)
    start = (page - 1) * page_size
    items = filtered[start : start + page_size]

    return OffsetPage(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=-(-total // page_size),  # ceiling div
        has_next=(start + page_size) < total,
        has_prev=page > 1,
    )


# ─── v2: Cursor pagination ───
@v2_router.get("/events", response_model=CursorPage[Event])
async def list_events_cursor(
    cursor: Optional[str] = Query(None, description="Opaque cursor from previous page"),
    limit: int = Query(10, ge=1, le=50),
):
    """
    CURSOR pagination — consistent, efficient for large tables.
    Uses WHERE id > :last_id  (indexed, no offset scan).
    Pass next_cursor from response to get next page.
    """
    last_id = decode_cursor(cursor)["id"] if cursor else 0

    # Simulate: SELECT * FROM events WHERE id > last_id ORDER BY id LIMIT limit+1
    filtered = [e for e in EVENTS if e["id"] > last_id]
    filtered.sort(key=lambda e: e["id"])

    # Fetch one extra to detect if there's more
    fetched  = filtered[: limit + 1]
    has_more = len(fetched) > limit
    items    = fetched[:limit]

    next_cursor = encode_cursor({"id": items[-1]["id"]}) if has_more and items else None

    return CursorPage(
        items=items,
        next_cursor=next_cursor,
        has_more=has_more,
        count=len(items),
    )


# ═══════════════════════════════════════════════════════
# SECTION 3: Rate Limiting (sliding window)
# ═══════════════════════════════════════════════════════

class SlidingWindowLimiter:
    """In-memory sliding window. Use Redis in production."""

    def __init__(self, limit: int, window_seconds: int):
        self.limit  = limit
        self.window = window_seconds
        self._buckets: dict[str, list[float]] = {}

    def check(self, key: str) -> tuple[bool, dict]:
        now          = time.time()
        window_start = now - self.window

        calls     = [t for t in self._buckets.get(key, []) if t > window_start]
        remaining = max(0, self.limit - len(calls))
        reset_at  = int(now) + self.window

        if len(calls) >= self.limit:
            return False, {"limit": self.limit, "remaining": 0, "reset": reset_at}

        calls.append(now)
        self._buckets[key] = calls
        return True, {"limit": self.limit, "remaining": remaining - 1, "reset": reset_at}


strict_limiter  = SlidingWindowLimiter(limit=5,   window_seconds=60)   # 5/min
relaxed_limiter = SlidingWindowLimiter(limit=100,  window_seconds=60)  # 100/min


def rate_limited(limiter: SlidingWindowLimiter):
    """Dependency factory for rate limiting."""
    def checker(request: Request):
        ip = request.client.host if request.client else "unknown"
        allowed, info = limiter.check(ip)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Try again in {info['reset'] - int(time.time())}s",
                headers={
                    "X-RateLimit-Limit":     str(info["limit"]),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset":     str(info["reset"]),
                    "Retry-After":           str(info["reset"] - int(time.time())),
                },
            )
        return info
    return Depends(checker)


# ═══════════════════════════════════════════════════════
# SECTION 4: SSE — Server-Sent Events + LLM Streaming
# ═══════════════════════════════════════════════════════

stream_router = APIRouter(prefix="/stream", tags=["Streaming + SSE"])


async def sse_event(data: dict, event: str = "message", retry: int = 3000) -> str:
    """Format a single SSE event."""
    return f"event: {event}\nretry: {retry}\ndata: {json.dumps(data)}\n\n"


@stream_router.get("/events")
async def sse_demo(topic: str = Query("updates")):
    """
    Server-Sent Events demo.
    Browser: const es = new EventSource('/stream/events?topic=prices');
    """
    async def generator():
        for i in range(10):
            data = {
                "index": i,
                "topic": topic,
                "value": round(i * 1.5, 2),
                "timestamp": time.time(),
            }
            yield await sse_event(data)
            await asyncio.sleep(0.5)
        yield await sse_event({"type": "done"}, event="close")

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",   # disable nginx buffering
        },
    )


@stream_router.get("/llm")
async def llm_streaming(prompt: str = Query(default="Tell me about Python")):
    """
    Simulates LLM token-by-token streaming (like Claude/OpenAI).
    Real code: async for text in anthropic_client.messages.stream(...)
    """
    tokens = f"Great question! Python is a versatile language. Your prompt was: '{prompt}'.".split()

    async def generator():
        for token in tokens:
            chunk = {"type": "token", "text": token + " "}
            yield await sse_event(chunk, event="token")
            await asyncio.sleep(0.05)  # simulate LLM latency per token

        # Final usage stats
        usage = {"type": "done", "input_tokens": len(prompt.split()), "output_tokens": len(tokens)}
        yield await sse_event(usage, event="done")

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@stream_router.get("/large-csv")
async def stream_large_csv():
    """Stream a large CSV without loading into memory."""
    async def generate_rows():
        yield "id,name,email,amount\n"
        for i in range(1, 100_001):
            yield f"{i},User{i},user{i}@example.com,{i * 9.99:.2f}\n"
            if i % 1000 == 0:
                await asyncio.sleep(0)  # yield to event loop

    return StreamingResponse(
        generate_rows(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=export.csv"},
    )


@stream_router.get("/sse-demo-page", response_class=HTMLResponse)
async def sse_demo_page():
    """Browser page to test SSE."""
    return HTMLResponse("""
    <!DOCTYPE html><html><body>
    <h2>SSE / LLM Streaming Demo</h2>
    <button onclick="startSSE()">Start Events</button>
    <button onclick="startLLM()">Stream LLM</button>
    <button onclick="stop()">Stop</button>
    <div id="output" style="border:1px solid #ccc;padding:10px;height:300px;overflow:auto;font-family:monospace;margin-top:10px;"></div>
    <script>
    let es;
    const out = document.getElementById('output');
    const log = m => { out.innerHTML += m + '<br>'; out.scrollTop = out.scrollHeight; };
    function startSSE() {
        if (es) es.close();
        es = new EventSource('/stream/events?topic=prices');
        es.onmessage = e => log('📨 ' + e.data);
        es.addEventListener('close', () => { log('✅ Done'); es.close(); });
        es.onerror = () => log('❌ Error');
    }
    function startLLM() {
        if (es) es.close();
        let text = '';
        es = new EventSource('/stream/llm?prompt=What+is+FastAPI');
        es.addEventListener('token', e => {
            const d = JSON.parse(e.data);
            text += d.text;
            out.innerHTML = text;
        });
        es.addEventListener('done', e => { log('<br>✅ ' + e.data); es.close(); });
    }
    function stop() { if (es) es.close(); log('🛑 Stopped'); }
    </script>
    </body></html>
    """)


# ═══════════════════════════════════════════════════════
# SECTION 5: Idempotency Keys
# ═══════════════════════════════════════════════════════

idempotency_router = APIRouter(prefix="/payments", tags=["Idempotency"])


class PaymentRequest(BaseModel):
    amount: float
    currency: str = "INR"
    to_account: str


@idempotency_router.post("", status_code=201)
async def create_payment(
    body: PaymentRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    """
    Idempotent payment.
    Same Idempotency-Key → same response (no double charge).
    Test: send same request twice with header 'Idempotency-Key: pay-001'
    """
    if idempotency_key:
        cached = IDEMPOTENCY_CACHE.get(idempotency_key)
        if cached:
            return JSONResponse(
                status_code=200,
                content={**cached, "idempotent_replay": True},
                headers={"Idempotency-Key": idempotency_key},
            )

    payment_id = f"pay_{uuid.uuid4().hex[:8]}"
    result = {
        "payment_id": payment_id,
        "amount": body.amount,
        "currency": body.currency,
        "to_account": body.to_account,
        "status": "success",
        "processed_at": time.time(),
    }

    if idempotency_key:
        IDEMPOTENCY_CACHE[idempotency_key] = result

    return result


# ═══════════════════════════════════════════════════════
# SECTION 6: Health Checks
# ═══════════════════════════════════════════════════════

health_router = APIRouter(prefix="/health", tags=["Health"])


@health_router.get("/live")
async def liveness():
    """
    Kubernetes liveness probe.
    Returns 200 if app process is running and not deadlocked.
    """
    return {"status": "ok", "timestamp": time.time()}


@health_router.get("/ready")
async def readiness():
    """
    Kubernetes readiness probe.
    Returns 200 only when app is ready to receive traffic.
    Checks DB, Redis, external dependencies.
    """
    checks: dict[str, str] = {}
    overall = "healthy"

    # Simulate DB check
    try:
        _ = len(PRODUCTS)  # simulates SELECT 1
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"
        overall = "unhealthy"

    # Simulate Redis check
    try:
        REDIS_STORE["ping"] = "pong"
        assert REDIS_STORE["ping"] == "pong"
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"
        overall = "degraded"

    status_code = 200 if overall in ("healthy", "degraded") else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": overall,
            "uptime_seconds": round(time.time() - START_TIME, 1),
            "checks": checks,
        },
    )


@health_router.get("/info")
async def app_info():
    return {
        "version": "1.0.0",
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "products_count": len(PRODUCTS),
        "events_count": len(EVENTS),
    }


# ═══════════════════════════════════════════════════════
# SECTION 7: App Setup
# ═══════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 App starting...")
    yield
    print("🛑 App shutting down...")


app = FastAPI(
    title="FastAPI Advanced Patterns",
    description="Phase 2 — Pagination, Rate Limiting, Versioning, SSE, Idempotency, Health",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(v1_router)
app.include_router(v2_router)
app.include_router(stream_router)
app.include_router(idempotency_router)
app.include_router(health_router)


@app.get("/rate-limited", tags=["Rate Limiting"])
async def rate_limited_endpoint(
    rate_info: Annotated[dict, rate_limited(strict_limiter)],
):
    """5 requests/minute. Hit it 6 times to see 429."""
    return {"message": "OK", "rate_info": rate_info}


@app.get("/", tags=["Root"])
async def root():
    return {
        "message": "Advanced Patterns Practical",
        "endpoints": {
            "offset_pagination": "GET /v1/products?page=1&page_size=10",
            "cursor_pagination": "GET /v2/events?limit=10",
            "sse_demo":          "GET /stream/sse-demo-page",
            "llm_stream":        "GET /stream/llm?prompt=Hello",
            "idempotency":       "POST /payments (Idempotency-Key header)",
            "rate_limit":        "GET /rate-limited (5 req/min)",
            "health":            "GET /health/ready",
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("06_advanced_patterns:app", host="0.0.0.0", port=8005, reload=True)
