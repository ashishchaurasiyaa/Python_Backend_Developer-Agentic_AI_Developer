# REST API Design — Best Practices, Versioning, Idempotency, Pagination, Webhooks

## Quick Concepts
- **REST** = Representational State Transfer — stateless, resource-based URLs
- **Versioning** = API changes breaking nahi hone chahiye — `/v1/`, `/v2/`
- **Idempotency** = same request baar baar bhejo — same result (PUT, DELETE safe hain)
- **Pagination** = cursor-based vs offset-based
- **Webhook** = server tumhare server ko notify karta hai (push vs poll)

---

## Interview Questions & Answers

### Q1: REST API design ke best practices kya hain?
**Answer:**
```
Resources noun hone chahiye, verbs nahi:
  GOOD: GET /users/123/orders
  BAD:  GET /getUserOrders?userId=123

HTTP methods sahi use karo:
  GET    → Read (idempotent, cacheable)
  POST   → Create (not idempotent)
  PUT    → Full update (idempotent)
  PATCH  → Partial update
  DELETE → Delete (idempotent)

Status codes sahi use karo:
  200 OK          → success
  201 Created     → resource created (POST)
  204 No Content  → success, no body (DELETE)
  400 Bad Request → client ne galat data bheja
  401 Unauthorized → authentication required
  403 Forbidden   → authenticated but no permission
  404 Not Found   → resource nahi mila
  409 Conflict    → duplicate resource
  422 Unprocessable → validation failed
  429 Too Many Requests → rate limit
  500 Internal Server Error → server ka fault
```

```python
# Consistent response format — BaseResponse pattern
from pydantic import BaseModel
from typing import Optional, Any, Generic, TypeVar
from datetime import datetime

T = TypeVar("T")

class APIResponse(BaseModel, Generic[T]):
    success: bool
    data: Optional[T] = None
    error: Optional[dict] = None
    meta: Optional[dict] = None
    request_id: Optional[str] = None
    timestamp: str = datetime.utcnow().isoformat()

class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool

# FastAPI usage
@app.get("/users/{user_id}", response_model=APIResponse[UserResponse])
async def get_user(user_id: int):
    user = await user_service.get(user_id)
    return APIResponse(success=True, data=user)

@app.post("/users", response_model=APIResponse[UserResponse], status_code=201)
async def create_user(user: UserCreate):
    try:
        new_user = await user_service.create(user)
        return APIResponse(success=True, data=new_user)
    except DuplicateEmailError:
        return JSONResponse(
            status_code=409,
            content=APIResponse(
                success=False,
                error={"code": "DUPLICATE_EMAIL", "message": "Email already exists"}
            ).model_dump()
        )
```

---

### Q2: API Versioning strategies kya hain? Kaunsa best hai?
**Answer:**
```python
# Strategy 1: URL path versioning (MOST COMMON — recommended)
# /api/v1/users  →  /api/v2/users
from fastapi import FastAPI
from fastapi.routing import APIRouter

v1_router = APIRouter(prefix="/api/v1")
v2_router = APIRouter(prefix="/api/v2")

@v1_router.get("/users/{id}")
async def get_user_v1(id: int):
    return {"id": id, "name": "old format"}

@v2_router.get("/users/{id}")
async def get_user_v2(id: int):
    return {"id": id, "full_name": "new format", "metadata": {}}

app = FastAPI()
app.include_router(v1_router)
app.include_router(v2_router)

# Strategy 2: Header versioning
@app.get("/users/{id}")
async def get_user(
    id: int,
    api_version: str = Header(default="v1", alias="X-API-Version")
):
    if api_version == "v2":
        return v2_response(id)
    return v1_response(id)

# Strategy 3: Query param (least recommended)
# /users/123?version=2

# Versioning best practices:
# - v1 ko deprecate karo, delete mat karo abhi
# - Deprecation header add karo: Deprecation: true, Sunset: 2025-12-31
# - Breaking changes = new version (field remove/rename = breaking)
# - Non-breaking = same version ok (new field add, new endpoint)
```

---

### Q3: Rate Limiting — Token Bucket vs Sliding Window?
**Answer:**
```python
import redis.asyncio as aioredis
import time
from fastapi import Request, HTTPException

redis = aioredis.from_url("redis://localhost:6379")

# SLIDING WINDOW — accurate, per-user
async def sliding_window_rate_limit(
    user_id: str,
    limit: int = 100,
    window_seconds: int = 60
) -> tuple[bool, dict]:
    key = f"ratelimit:{user_id}"
    now = time.time()
    window_start = now - window_seconds

    pipe = redis.pipeline()
    pipe.zremrangebyscore(key, 0, window_start)    # old requests hataao
    pipe.zadd(key, {str(now): now})                 # current request add
    pipe.zcard(key)                                 # count
    pipe.expire(key, window_seconds)
    results = await pipe.execute()

    count = results[2]
    remaining = max(0, limit - count)
    allowed = count <= limit

    return allowed, {
        "X-RateLimit-Limit": limit,
        "X-RateLimit-Remaining": remaining,
        "X-RateLimit-Reset": int(now + window_seconds),
    }

# TOKEN BUCKET — burst allow karta hai
async def token_bucket(
    user_id: str,
    capacity: int = 100,
    refill_rate: float = 1.0    # tokens per second
) -> bool:
    key = f"bucket:{user_id}"
    now = time.time()

    pipe = redis.pipeline()
    pipe.hmget(key, "tokens", "last_refill")
    results = await pipe.execute()

    tokens_str, last_refill_str = results[0]
    tokens = float(tokens_str) if tokens_str else capacity
    last_refill = float(last_refill_str) if last_refill_str else now

    # Refill
    elapsed = now - last_refill
    tokens = min(capacity, tokens + elapsed * refill_rate)

    if tokens >= 1:
        tokens -= 1
        await redis.hmset(key, {"tokens": tokens, "last_refill": now})
        await redis.expire(key, 3600)
        return True
    return False

# FastAPI middleware
class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        user_id = request.headers.get("X-User-ID", request.client.host)
        allowed, headers = await sliding_window_rate_limit(user_id)

        if not allowed:
            return JSONResponse(
                {"error": "Rate limit exceeded"},
                status_code=429,
                headers={**headers, "Retry-After": "60"}
            )

        response = await call_next(request)
        for key, value in headers.items():
            response.headers[key] = str(value)
        return response
```

---

### Q4: Idempotency Keys kaise implement karte hain?
**Answer:**
Idempotency key = client ek unique key bhejta hai. Same key dobara aaye → same response, duplicate operation nahi.

```python
import hashlib
import json
from fastapi import Header, Request

async def idempotent_request(
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    db: DbSession = Depends(get_db),
    redis: RedisDep = Depends(get_redis),
):
    return idempotency_key

@app.post("/payments", response_model=PaymentResponse)
async def create_payment(
    payment: PaymentCreate,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    redis: RedisDep = Depends(get_redis),
    db: DbSession = Depends(get_db),
):
    if idempotency_key:
        cache_key = f"idempotency:{idempotency_key}"
        cached = await redis.get(cache_key)
        if cached:
            # Same request already processed — return same response
            return JSONResponse(
                content=json.loads(cached),
                headers={"X-Idempotency-Replayed": "true"}
            )

    # Process payment
    result = await payment_service.charge(payment)

    if idempotency_key:
        # 24 ghante ke liye store karo
        await redis.setex(cache_key, 86400, json.dumps(result.model_dump()))

    return result
```

---

### Q5: Pagination — Cursor vs Offset?
**Answer:**
```python
# OFFSET PAGINATION — simple but slow on large datasets
@app.get("/users")
async def list_users_offset(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, le=100),
    db: DbSession = Depends(get_db),
):
    skip = (page - 1) * page_size
    total = await db.scalar(select(func.count(User.id)).where(User.is_active == True))
    users = await db.scalars(
        select(User).where(User.is_active == True)
        .offset(skip).limit(page_size).order_by(User.id)
    )
    return {
        "items": users.all(),
        "total": total,
        "page": page,
        "total_pages": (total + page_size - 1) // page_size,
    }
# Problem: OFFSET 10000 = 10000 rows skip karne padte hain → slow!

# CURSOR PAGINATION — fast, consistent (recommended for large data)
@app.get("/users/cursor")
async def list_users_cursor(
    cursor: Optional[str] = Query(None),   # last item ka ID/timestamp
    limit: int = Query(20, le=100),
    db: DbSession = Depends(get_db),
):
    stmt = select(User).where(User.is_active == True).order_by(User.id).limit(limit + 1)

    if cursor:
        import base64
        decoded = int(base64.b64decode(cursor).decode())
        stmt = stmt.where(User.id > decoded)

    users = (await db.scalars(stmt)).all()
    has_next = len(users) > limit
    items = users[:limit]

    next_cursor = None
    if has_next and items:
        import base64
        next_cursor = base64.b64encode(str(items[-1].id).encode()).decode()

    return {
        "items": items,
        "next_cursor": next_cursor,
        "has_next": has_next,
    }
```

---

### Q6: Webhooks kaise implement karte hain?
**Answer:**
```python
import hmac
import hashlib
import httpx

# Webhook sender (apna server)
class WebhookService:
    def __init__(self, secret: str):
        self.secret = secret

    def sign_payload(self, payload: str) -> str:
        return hmac.new(
            self.secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()

    async def deliver(self, url: str, event: str, data: dict) -> bool:
        payload = json.dumps({"event": event, "data": data, "timestamp": time.time()})
        signature = self.sign_payload(payload)

        async with httpx.AsyncClient(timeout=10) as client:
            try:
                response = await client.post(
                    url,
                    content=payload,
                    headers={
                        "Content-Type": "application/json",
                        "X-Webhook-Signature": f"sha256={signature}",
                        "X-Webhook-Event": event,
                    }
                )
                return response.status_code < 300
            except Exception:
                return False

# Webhook receiver (client ka server — verify signature)
@app.post("/webhooks/payment")
async def receive_payment_webhook(
    request: Request,
    x_webhook_signature: str = Header(...),
):
    payload = await request.body()
    expected = hmac.new(WEBHOOK_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    received = x_webhook_signature.replace("sha256=", "")

    if not hmac.compare_digest(expected, received):
        raise HTTPException(401, "Invalid webhook signature")

    data = json.loads(payload)
    event = data["event"]

    if event == "payment.completed":
        await handle_payment_completed(data["data"])
    elif event == "payment.failed":
        await handle_payment_failed(data["data"])

    return {"received": True}
```
