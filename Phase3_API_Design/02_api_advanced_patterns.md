# API Advanced Patterns — Caching, Long-Running Ops, Error Standards, Gateway

## Quick Concepts
- **ETag** = response ka fingerprint/hash — client bhejta hai, server check karta hai → 304 if unchanged
- **Cache-Control** = caching directives — `max-age`, `no-cache`, `no-store`, `private`, `public`
- **304 Not Modified** = server bol raha hai "data change nahi hua — apna cached version use karo"
- **202 Accepted** = request received, processing async — "hum kar rahe hain, baad mein check karna"
- **RFC 7807** = Problem Details standard — `application/problem+json` format for errors
- **API Gateway** = single entry point — auth, rate limit, routing, logging
- **BFF** = Backend for Frontend — mobile/web ke liye alag optimized backends
- **HATEOAS** = response mein next actions ke links — self-describing API
- **Batch API** = ek request mein multiple operations — reduce round trips

---

## Interview Questions & Answers

### Q1: HTTP Caching — ETag aur Cache-Control kaise kaam karte hain?

**Answer:**
```python
import hashlib
import json
from fastapi import Request, Response
from fastapi.responses import JSONResponse

# ─── Cache-Control directives ───
# public:        CDN/proxy cache kar sakta hai
# private:       sirf browser cache kare (user-specific data)
# no-cache:      har baar revalidate karo (ETag se) before serving
# no-store:      kabhi cache mat karo (sensitive data)
# max-age=N:     N seconds tak fresh hai
# s-maxage=N:    shared cache (CDN) ke liye max-age override
# must-revalidate: expire hone ke baad revalidate karo (stale serve mat karo)

# ─── ETag (Entity Tag) — fingerprint-based caching ───
# Flow:
# 1. Client:  GET /users/1
# 2. Server:  200 OK + ETag: "abc123"
# 3. Client:  GET /users/1 + If-None-Match: "abc123"
# 4. Server:  304 Not Modified (no body!) if data unchanged
#             200 OK + new ETag if data changed

def generate_etag(data: dict) -> str:
    """Generate ETag from response data."""
    content = json.dumps(data, sort_keys=True)
    return hashlib.md5(content.encode()).hexdigest()


@app.get("/users/{user_id}")
async def get_user(
    user_id: int,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")

    data = user.model_dump()
    etag = f'"{generate_etag(data)}"'

    # Client ne If-None-Match bheja? Check karo
    if_none_match = request.headers.get("If-None-Match")
    if if_none_match == etag:
        # Data change nahi hua → 304, no body (saves bandwidth!)
        return Response(status_code=304, headers={"ETag": etag})

    # Set caching headers
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "private, max-age=60, must-revalidate"
    response.headers["Last-Modified"] = user.updated_at.strftime(
        "%a, %d %b %Y %H:%M:%S GMT"
    )
    return data


# ─── Last-Modified / If-Modified-Since ───
@app.get("/posts")
async def list_posts(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    # Get latest updated_at across all posts
    result = await db.execute(select(func.max(Post.updated_at)))
    latest = result.scalar()

    if latest:
        last_modified = latest.strftime("%a, %d %b %Y %H:%M:%S GMT")

        # Check If-Modified-Since header
        ims = request.headers.get("If-Modified-Since")
        if ims == last_modified:
            return Response(status_code=304, headers={"Last-Modified": last_modified})

        response.headers["Last-Modified"] = last_modified

    response.headers["Cache-Control"] = "public, max-age=300"  # 5 min CDN cache
    posts = await db.scalars(select(Post).where(Post.status == "published"))
    return posts.all()


# ─── Cache-Control per endpoint type ───
# Public static data (product catalog):     Cache-Control: public, max-age=3600
# User-specific data (profile):             Cache-Control: private, max-age=60
# Real-time data (live prices):             Cache-Control: no-cache
# Sensitive (payments, auth):               Cache-Control: no-store
# Public + must revalidate:                 Cache-Control: public, no-cache

# ─── INTERVIEW ───
# ETag kab use karo?
# - GET endpoints jo frequently call hote hain
# - Large response bodies (bandwidth save karo)
# - CDN caching ke saath

# Cache-Control: no-cache vs no-store?
# no-cache:  cache mein rakh, har baar server se validate karo (ETag se)
# no-store:  bilkul cache mat karo (auth tokens, payment data)
```

---

### Q2: Long-running Operations — 202 Accepted + Polling pattern?

**Answer:**
```python
import uuid
from enum import Enum

class JobStatus(str, Enum):
    PENDING    = "pending"
    PROCESSING = "processing"
    COMPLETED  = "completed"
    FAILED     = "failed"

# ─── 202 Accepted pattern ───
# When: operation > 1-2 seconds (report generation, bulk import, ML inference)
# Flow:
#   POST /reports → 202 Accepted + Location: /jobs/{job_id}
#   GET  /jobs/{job_id} → { status: "processing", progress: 45 }
#   GET  /jobs/{job_id} → { status: "completed", result_url: "..." }

@app.post("/reports", status_code=202)
async def create_report(
    request: ReportRequest,
    background_tasks: BackgroundTasks,
    redis: Redis = Depends(get_redis),
):
    """
    INTERVIEW: 202 vs 200 kab?
    200: response body mein result hai — synchronous
    202: background mein process ho raha hai — async
    202 + Location header: client jaa ke status check kare
    """
    job_id = str(uuid.uuid4())

    # Initial state in Redis
    await redis.setex(
        f"job:{job_id}",
        3600,  # 1 hour TTL
        json.dumps({
            "status":    JobStatus.PENDING,
            "progress":  0,
            "created_at": datetime.utcnow().isoformat(),
        })
    )

    # Start background processing
    background_tasks.add_task(process_report_job, job_id, request, redis)

    return JSONResponse(
        status_code=202,
        content={"job_id": job_id, "status": "pending"},
        headers={
            "Location":     f"/jobs/{job_id}",  # where to poll
            "Retry-After":  "5",                # poll after 5 seconds
        }
    )


async def process_report_job(job_id: str, request, redis):
    """Background worker — updates progress in Redis."""
    try:
        await redis.set(f"job:{job_id}", json.dumps({
            "status": JobStatus.PROCESSING, "progress": 10
        }))

        # Simulate work in stages
        for progress in [25, 50, 75, 90]:
            await asyncio.sleep(1)
            await redis.setex(f"job:{job_id}", 3600, json.dumps({
                "status": JobStatus.PROCESSING, "progress": progress
            }))

        # Done
        result_url = f"/reports/results/{job_id}.csv"
        await redis.setex(f"job:{job_id}", 3600, json.dumps({
            "status":     JobStatus.COMPLETED,
            "progress":   100,
            "result_url": result_url,
            "completed_at": datetime.utcnow().isoformat(),
        }))

    except Exception as e:
        await redis.setex(f"job:{job_id}", 3600, json.dumps({
            "status": JobStatus.FAILED,
            "error":  str(e),
        }))


@app.get("/jobs/{job_id}")
async def get_job_status(job_id: str, redis: Redis = Depends(get_redis)):
    data = await redis.get(f"job:{job_id}")
    if not data:
        raise HTTPException(404, "Job not found")

    job = json.loads(data)

    # Add Retry-After if still processing
    headers = {}
    if job["status"] in (JobStatus.PENDING, JobStatus.PROCESSING):
        headers["Retry-After"] = "3"

    return JSONResponse(content=job, headers=headers)


# ─── Webhook callback variant ───
# Client registers callback URL upfront
# Server calls it when done (instead of polling)

@app.post("/bulk-import", status_code=202)
async def bulk_import(
    file: UploadFile,
    callback_url: Optional[str] = Body(None),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    job_id = str(uuid.uuid4())
    background_tasks.add_task(
        process_bulk_import, job_id, file, callback_url
    )
    return {"job_id": job_id}


async def process_bulk_import(job_id: str, file, callback_url: Optional[str]):
    # ... process file ...
    result = {"imported": 500, "errors": 3}

    if callback_url:
        # Notify client when done (webhook)
        async with httpx.AsyncClient() as client:
            await client.post(callback_url, json={
                "job_id": job_id,
                "status": "completed",
                **result
            })
```

---

### Q3: RFC 7807 — Problem Details standard error format?

**Answer:**
```python
# ─── RFC 7807: application/problem+json ───
# Standard error format — consistent across APIs
# Fields:
#   type:     URI — error type (documentation link)
#   title:    human-readable summary (same for all instances of this type)
#   status:   HTTP status code
#   detail:   specific instance detail
#   instance: URI identifying this specific error occurrence

from fastapi.responses import JSONResponse

PROBLEM_CONTENT_TYPE = "application/problem+json"

def problem_response(
    status: int,
    type_: str,
    title: str,
    detail: str,
    instance: str = None,
    **extra
) -> JSONResponse:
    body = {
        "type":     f"https://api.myapp.com/errors/{type_}",
        "title":    title,
        "status":   status,
        "detail":   detail,
    }
    if instance:
        body["instance"] = instance
    body.update(extra)

    return JSONResponse(
        status_code=status,
        content=body,
        media_type=PROBLEM_CONTENT_TYPE,
        headers={"Content-Type": PROBLEM_CONTENT_TYPE},
    )


# FastAPI global exception handler
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    error_map = {
        400: ("bad-request",       "Bad Request"),
        401: ("unauthorized",      "Authentication Required"),
        403: ("forbidden",         "Access Denied"),
        404: ("not-found",         "Resource Not Found"),
        409: ("conflict",          "Resource Conflict"),
        422: ("validation-error",  "Validation Failed"),
        429: ("rate-limit",        "Too Many Requests"),
        500: ("internal-error",    "Internal Server Error"),
    }
    type_, title = error_map.get(exc.status_code, ("error", "Error"))
    return problem_response(
        status=exc.status_code,
        type_=type_,
        title=title,
        detail=str(exc.detail),
        instance=str(request.url),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return problem_response(
        status=422,
        type_="validation-error",
        title="Validation Failed",
        detail="One or more fields failed validation",
        instance=str(request.url),
        errors=[{
            "field":   " → ".join(str(l) for l in e["loc"]),
            "message": e["msg"],
            "type":    e["type"],
        } for e in exc.errors()],
    )


# Custom business errors
class AppError(Exception):
    def __init__(self, status: int, type_: str, title: str, detail: str, **kwargs):
        self.status = status
        self.type_  = type_
        self.title  = title
        self.detail = detail
        self.extra  = kwargs


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return problem_response(
        status=exc.status, type_=exc.type_,
        title=exc.title, detail=exc.detail,
        instance=str(request.url), **exc.extra
    )


# Usage
def create_payment(amount: float, user_id: int):
    if amount <= 0:
        raise AppError(400, "invalid-amount", "Invalid Amount",
                       f"Amount must be positive, got {amount}")

    user = get_user(user_id)
    if user.credits < amount:
        raise AppError(402, "insufficient-credits", "Insufficient Credits",
                       f"Need {amount} credits, have {user.credits}",
                       required=amount, available=user.credits)

# Response looks like:
# {
#   "type":     "https://api.myapp.com/errors/insufficient-credits",
#   "title":    "Insufficient Credits",
#   "status":   402,
#   "detail":   "Need 100.0 credits, have 50.0",
#   "instance": "/payments",
#   "required": 100.0,
#   "available": 50.0
# }
```

---

### Q4: API Gateway + BFF (Backend for Frontend) pattern?

**Answer:**
```
─── API Gateway ───
Single entry point for all microservices.

  Client → [API Gateway] → [User Service]
                         → [Order Service]
                         → [Payment Service]
                         → [Notification Service]

Gateway responsibilities:
  ✓ Authentication/Authorization (JWT verify once)
  ✓ Rate limiting (per client/API key)
  ✓ Request routing (path → service)
  ✓ SSL termination
  ✓ Request/response transformation
  ✓ Logging + tracing (correlation ID inject karo)
  ✓ Circuit breaker (failing service ko bypass karo)
  ✓ Caching (GET responses)

Popular options:
  AWS API Gateway:   managed, serverless-friendly
  Kong:              open-source, plugin ecosystem
  Nginx + Lua:       custom, high performance
  Traefik:           Kubernetes-native, auto-discovery
  FastAPI app:       custom gateway for full control

─── BFF (Backend for Frontend) ───
Different clients have different data needs:
  Mobile app:   small payload, battery-efficient, different fields
  Web app:      rich data, multiple sections in one page
  Third-party:  standardized, versioned, stable

Single generic API mein problem:
  Mobile client over-fetching (too many fields)
  Web client under-fetching (N+1 API calls for page)

BFF solution:
  Client → [Mobile BFF]     → Microservices
         → [Web BFF]        → Microservices
         → [Partner API]    → Microservices

Each BFF:
  - Aggregates multiple service calls (fan-out + merge)
  - Returns exactly what that client needs
  - Owned by frontend team
```

```python
# ─── Simple BFF with FastAPI ───
import asyncio, httpx

USER_SERVICE    = "http://user-service:8001"
ORDER_SERVICE   = "http://order-service:8002"
PRODUCT_SERVICE = "http://product-service:8003"

@app.get("/mobile/dashboard/{user_id}")
async def mobile_dashboard(user_id: int):
    """
    Mobile BFF — aggregates 3 service calls in parallel.
    Returns only fields mobile app needs (small payload).
    """
    async with httpx.AsyncClient(timeout=5.0) as client:
        # Fan-out: 3 calls in parallel
        user_resp, orders_resp, notif_resp = await asyncio.gather(
            client.get(f"{USER_SERVICE}/users/{user_id}"),
            client.get(f"{ORDER_SERVICE}/users/{user_id}/orders?limit=5"),
            client.get(f"{USER_SERVICE}/users/{user_id}/notifications?unread=true"),
            return_exceptions=True,
        )

    # Mobile-optimized response (minimal fields)
    return {
        "user": {
            "name":   user_resp.json()["name"],
            "avatar": user_resp.json()["avatar_url"],
            "plan":   user_resp.json()["plan"],
        },
        "recent_orders": [
            {"id": o["id"], "status": o["status"], "total": o["total"]}
            for o in (orders_resp.json() if not isinstance(orders_resp, Exception) else [])
        ],
        "unread_count": len(notif_resp.json()) if not isinstance(notif_resp, Exception) else 0,
    }


@app.get("/web/dashboard/{user_id}")
async def web_dashboard(user_id: int):
    """
    Web BFF — richer data, more fields, browser-optimized.
    """
    async with httpx.AsyncClient(timeout=5.0) as client:
        user_resp, orders_resp, products_resp = await asyncio.gather(
            client.get(f"{USER_SERVICE}/users/{user_id}"),
            client.get(f"{ORDER_SERVICE}/users/{user_id}/orders?limit=10"),
            client.get(f"{PRODUCT_SERVICE}/recommended/{user_id}"),
            return_exceptions=True,
        )

    return {
        "user":        user_resp.json() if not isinstance(user_resp, Exception) else {},
        "orders":      orders_resp.json() if not isinstance(orders_resp, Exception) else [],
        "recommended": products_resp.json() if not isinstance(products_resp, Exception) else [],
    }
```

---

### Q5: HATEOAS — Hypermedia links in API responses?

**Answer:**
```python
# ─── HATEOAS = Hypermedia As The Engine Of Application State ───
# Responses contain links to available actions
# Client discovers API dynamically — no hardcoded URLs
# REST maturity level 3 (Richardson Maturity Model)

# Without HATEOAS (Level 2 REST):
# GET /orders/123 → { "id": 123, "status": "pending" }
# Client must KNOW that it can POST /orders/123/cancel

# With HATEOAS (Level 3 REST):
# GET /orders/123 → {
#   "id": 123,
#   "status": "pending",
#   "_links": {
#     "self":    { "href": "/orders/123", "method": "GET" },
#     "cancel":  { "href": "/orders/123/cancel", "method": "POST" },
#     "pay":     { "href": "/orders/123/payment", "method": "POST" }
#   }
# }

from pydantic import BaseModel
from typing import Optional

class Link(BaseModel):
    href:   str
    method: str = "GET"
    title:  Optional[str] = None

class OrderResponse(BaseModel):
    id:     int
    status: str
    total:  float
    links:  dict[str, Link]


def order_links(order_id: int, status: str) -> dict[str, Link]:
    """Generate available actions based on current order state."""
    links = {
        "self": Link(href=f"/orders/{order_id}", method="GET"),
    }
    if status == "pending":
        links["cancel"] = Link(href=f"/orders/{order_id}/cancel", method="POST",  title="Cancel order")
        links["pay"]    = Link(href=f"/orders/{order_id}/payment", method="POST", title="Pay now")
    elif status == "shipped":
        links["track"]  = Link(href=f"/orders/{order_id}/tracking", method="GET", title="Track shipment")
    elif status == "delivered":
        links["return"] = Link(href=f"/orders/{order_id}/return", method="POST", title="Request return")
    return links


@app.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(order_id: int):
    order = await get_order_from_db(order_id)
    return OrderResponse(
        id=order.id,
        status=order.status,
        total=order.total,
        links=order_links(order.id, order.status),
    )

# INTERVIEW: Production mein HATEOAS use karte hain?
# Pure HATEOAS rarely used — overhead high, client complexity bhi badhta hai
# Practical middle ground:
#   - Important next-actions ke links dalo (cancel, pay)
#   - Pagination links (next, prev, first, last) — almost always useful
#   - Full HATEOAS sirf when API is truly public + client-agnostic
```

---

### Q6: Batch API — multiple operations ek request mein?

**Answer:**
```python
from pydantic import BaseModel
from typing import Union

# ─── Batch request pattern ───
# When: create/update/delete 1000 items — don't want 1000 HTTP calls

class BatchOperation(BaseModel):
    method: str           # GET, POST, PUT, DELETE
    path:   str           # /users/1
    body:   Optional[dict] = None

class BatchRequest(BaseModel):
    operations: list[BatchOperation]
    atomic: bool = False  # True = all or nothing

class BatchResult(BaseModel):
    path:    str
    status:  int
    body:    Optional[dict]
    error:   Optional[str]


@app.post("/batch")
async def batch_endpoint(batch: BatchRequest) -> list[BatchResult]:
    """
    INTERVIEW: Batch API kab useful hai?
    Mobile app startup: profile + settings + notifications = 1 request instead of 3
    Bulk operations: create 500 users = 1 request instead of 500
    Atomic: all succeed or all rollback (atomic=True)
    """
    results = []

    if batch.atomic:
        # All or nothing — run in transaction
        async with db.begin():
            for op in batch.operations:
                try:
                    result = await execute_operation(op)
                    results.append(BatchResult(path=op.path, status=200, body=result))
                except Exception as e:
                    # Rollback all
                    raise HTTPException(400, f"Batch failed at {op.path}: {e}")
    else:
        # Best effort — each op independent
        for op in batch.operations:
            try:
                result = await execute_operation(op)
                results.append(BatchResult(path=op.path, status=200, body=result))
            except Exception as e:
                results.append(BatchResult(path=op.path, status=400, body=None, error=str(e)))

    return results


# ─── Bulk create (simpler version) ───
@app.post("/users/bulk", status_code=207)  # 207 Multi-Status
async def bulk_create_users(users: list[UserCreate]) -> dict:
    results = {"created": [], "errors": []}

    for user_data in users:
        try:
            user = await user_service.create(user_data)
            results["created"].append({"id": user.id, "email": user.email})
        except DuplicateEmailError:
            results["errors"].append({
                "email": user_data.email,
                "error": "Email already exists"
            })

    return {
        **results,
        "summary": {
            "total":   len(users),
            "created": len(results["created"]),
            "errors":  len(results["errors"]),
        }
    }
# 207 Multi-Status: partial success possible — not all 200, not all 400
```

---

## Summary

| Pattern | HTTP Status | When |
|---------|-------------|------|
| Synchronous response | 200, 201 | < 1-2 seconds |
| Async (long-running) | 202 Accepted | > 2 seconds, background job |
| Cached (unchanged) | 304 Not Modified | ETag match — save bandwidth |
| Partial success | 207 Multi-Status | Batch API — some succeed, some fail |
| Standard error | `application/problem+json` | RFC 7807 compliance |

| Caching Header | Meaning |
|---------------|---------|
| `Cache-Control: public, max-age=3600` | CDN + browser cache, 1 hour |
| `Cache-Control: private, max-age=60` | Browser only, 60 seconds |
| `Cache-Control: no-cache` | Cache but revalidate (ETag) |
| `Cache-Control: no-store` | Never cache (auth, payments) |
| `ETag: "abc123"` | Content fingerprint |
| `If-None-Match: "abc123"` | Client sends back, server checks → 304 |

| Pattern | Use When |
|---------|---------|
| API Gateway | Single entry point, auth once, rate limit, routing |
| BFF | Mobile/Web have different data needs, frontend team owns it |
| HATEOAS | Public API, client-agnostic, pagination links always useful |
| Batch API | Multiple operations, reduce round trips, mobile startup |
