"""
API Design Patterns — Practical (Runnable FastAPI App)
═══════════════════════════════════════════════════════════════
Run:
  pip install fastapi uvicorn redis httpx
  uvicorn 01_api_design_practical:app --reload --port 8000

Then test with:
  python 01_api_design_practical.py   ← runs all tests automatically

Prerequisites:
  docker run -d -p 6379:6379 redis

Topics:
  - Consistent response format (APIResponse wrapper)
  - ETag + Cache-Control + 304 Not Modified
  - Rate limiting middleware (sliding window)
  - Idempotency key middleware
  - 202 Accepted + job polling (long-running ops)
  - RFC 7807 Problem Details error format
  - Cursor + Offset pagination
  - Batch API (207 Multi-Status)
  - HATEOAS links
  - Request ID middleware

INTERVIEW QUICK REFERENCE at bottom.
"""

import asyncio
import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Generic, Optional, TypeVar

import redis.asyncio as aioredis
import httpx
from fastapi import (
    BackgroundTasks, Depends, FastAPI, Header, HTTPException,
    Query, Request, Response,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

# ═══════════════════════════════════════════════════════════
# APP + REDIS
# ═══════════════════════════════════════════════════════════

app = FastAPI(title="API Design Patterns Demo", version="1.0.0")
redis_client: Optional[aioredis.Redis] = None

FAKE_DB: dict[int, dict] = {
    1: {"id": 1, "name": "Alice",   "email": "alice@test.com", "plan": "premium", "credits": 500},
    2: {"id": 2, "name": "Bob",     "email": "bob@test.com",   "plan": "free",    "credits": 100},
    3: {"id": 3, "name": "Charlie", "email": "charlie@test.com","plan": "free",   "credits": 50},
}


@app.on_event("startup")
async def startup():
    global redis_client
    try:
        redis_client = await aioredis.from_url("redis://localhost:6379", decode_responses=True)
        await redis_client.ping()
        print("✓ Redis connected")
    except Exception as e:
        print(f"⚠ Redis not available: {e} — some demos will be limited")
        redis_client = None


@app.on_event("shutdown")
async def shutdown():
    if redis_client:
        await redis_client.aclose()


# ═══════════════════════════════════════════════════════════
# SECTION 1: Consistent Response Format
# ═══════════════════════════════════════════════════════════

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """
    INTERVIEW: Consistent response format kyu zaroori hai?
    Client ko predictable structure milti hai → easier parsing
    Error handling uniform hoti hai
    success field se client jaan sakta hai bina status code ke
    """
    success:    bool
    data:       Optional[T]   = None
    error:      Optional[dict]= None
    meta:       Optional[dict]= None
    request_id: Optional[str] = None
    timestamp:  str           = datetime.utcnow().isoformat()


def ok(data: Any, meta: dict = None, request_id: str = None) -> dict:
    return APIResponse(success=True, data=data, meta=meta, request_id=request_id).model_dump()


def fail(code: str, message: str, details: Any = None) -> dict:
    return APIResponse(
        success=False,
        error={"code": code, "message": message, "details": details}
    ).model_dump()


# ═══════════════════════════════════════════════════════════
# SECTION 2: Middleware — Request ID
# ═══════════════════════════════════════════════════════════

@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Inject X-Request-ID into every request for tracing."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# ═══════════════════════════════════════════════════════════
# SECTION 3: ETag + Cache-Control
# ═══════════════════════════════════════════════════════════

def compute_etag(data: Any) -> str:
    content = json.dumps(data, sort_keys=True, default=str)
    return f'"{hashlib.md5(content.encode()).hexdigest()}"'


@app.get("/users/{user_id}")
async def get_user(user_id: int, request: Request, response: Response):
    """
    INTERVIEW: ETag flow?
    1. GET /users/1           → 200 OK + ETag: "abc123"
    2. GET /users/1           → If-None-Match: "abc123"
       (data unchanged)      → 304 Not Modified (no body!)
       (data changed)        → 200 OK + new ETag: "def456"

    Saves bandwidth on large responses.
    """
    if user_id not in FAKE_DB:
        raise HTTPException(404, "User not found")

    user_data = FAKE_DB[user_id]
    etag = compute_etag(user_data)

    # Check If-None-Match
    if_none_match = request.headers.get("if-none-match")
    if if_none_match == etag:
        return Response(
            status_code=304,
            headers={"ETag": etag, "Cache-Control": "private, max-age=60"},
        )

    response.headers["ETag"]          = etag
    response.headers["Cache-Control"] = "private, max-age=60, must-revalidate"
    return ok(user_data, request_id=request.state.request_id)


@app.get("/users")
async def list_users(response: Response):
    """Public list — CDN cacheable."""
    users = list(FAKE_DB.values())
    etag  = compute_etag(users)
    response.headers["ETag"]          = etag
    response.headers["Cache-Control"] = "public, max-age=300"
    return ok(users, meta={"total": len(users)})


# ═══════════════════════════════════════════════════════════
# SECTION 4: Rate Limiting (Sliding Window)
# ═══════════════════════════════════════════════════════════

async def check_rate_limit(
    user_id: str,
    limit: int = 10,
    window: int = 60,
) -> tuple[bool, dict]:
    """Sliding window rate limiter using Redis sorted set."""
    if not redis_client:
        return True, {}

    key  = f"rl:{user_id}"
    now  = time.time()
    wstart = now - window

    pipe = redis_client.pipeline()
    pipe.zremrangebyscore(key, 0, wstart)
    pipe.zadd(key, {str(now): now})
    pipe.zcard(key)
    pipe.expire(key, window)
    results = await pipe.execute()

    count     = results[2]
    remaining = max(0, limit - count)
    headers   = {
        "X-RateLimit-Limit":     str(limit),
        "X-RateLimit-Remaining": str(remaining),
        "X-RateLimit-Reset":     str(int(now + window)),
    }
    return count <= limit, headers


@app.get("/protected/data")
async def protected_endpoint(request: Request, response: Response):
    """Rate-limited endpoint — 10 requests per minute."""
    client_id = request.headers.get("X-User-ID", request.client.host)
    allowed, rl_headers = await check_rate_limit(client_id, limit=10, window=60)

    for k, v in rl_headers.items():
        response.headers[k] = v

    if not allowed:
        return JSONResponse(
            status_code=429,
            content=fail("RATE_LIMIT_EXCEEDED", "Too many requests. Try again in 60 seconds."),
            headers={**rl_headers, "Retry-After": "60"},
        )

    return ok({"message": "Here is your protected data", "time": datetime.utcnow().isoformat()})


# ═══════════════════════════════════════════════════════════
# SECTION 5: Idempotency Key
# ═══════════════════════════════════════════════════════════

@app.post("/payments", status_code=201)
async def create_payment(
    payload: dict,
    request: Request,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    """
    INTERVIEW: Idempotency kyu zaroori hai?
    Network timeout pe client retry karta hai → duplicate payment!
    Idempotency-Key: same key dobara aaye → same result, no duplicate operation.
    24 ghante ke liye result store karo (Redis).
    """
    if idempotency_key and redis_client:
        cache_key = f"idem:{idempotency_key}"
        cached = await redis_client.get(cache_key)
        if cached:
            return JSONResponse(
                content=json.loads(cached),
                headers={"X-Idempotency-Replayed": "true"},
                status_code=200,
            )

    # Process payment
    result = {
        "payment_id": str(uuid.uuid4()),
        "amount":     payload.get("amount", 0),
        "status":     "charged",
        "created_at": datetime.utcnow().isoformat(),
    }

    if idempotency_key and redis_client:
        await redis_client.setex(
            f"idem:{idempotency_key}",
            86400,  # 24 hours
            json.dumps(ok(result))
        )

    return ok(result, request_id=request.state.request_id)


# ═══════════════════════════════════════════════════════════
# SECTION 6: 202 Accepted + Polling (Long-running ops)
# ═══════════════════════════════════════════════════════════

async def _process_report(job_id: str, report_type: str):
    """Background job — updates progress in Redis."""
    if not redis_client:
        return

    for progress in [10, 25, 50, 75, 90]:
        await asyncio.sleep(0.5)
        await redis_client.setex(f"job:{job_id}", 3600, json.dumps({
            "status":   "processing",
            "progress": progress,
        }))

    # Complete
    await redis_client.setex(f"job:{job_id}", 3600, json.dumps({
        "status":       "completed",
        "progress":     100,
        "result":       {"report_type": report_type, "records": 1250},
        "completed_at": datetime.utcnow().isoformat(),
    }))


@app.post("/reports", status_code=202)
async def start_report(
    payload: dict,
    background_tasks: BackgroundTasks,
):
    """
    INTERVIEW: 202 vs 200?
    200: result abhi return karo (synchronous < 2s)
    202: background mein process hoga — poll /jobs/{id} for status
    Location header = where to poll
    Retry-After = how long to wait before polling
    """
    job_id      = str(uuid.uuid4())
    report_type = payload.get("type", "daily")

    if redis_client:
        await redis_client.setex(f"job:{job_id}", 3600, json.dumps({
            "status": "pending", "progress": 0
        }))

    background_tasks.add_task(_process_report, job_id, report_type)

    return JSONResponse(
        status_code=202,
        content={"job_id": job_id, "status": "pending"},
        headers={
            "Location":    f"/jobs/{job_id}",
            "Retry-After": "3",
        },
    )


@app.get("/jobs/{job_id}")
async def get_job(job_id: str):
    if not redis_client:
        return ok({"status": "completed", "progress": 100, "note": "Redis not available"})

    data = await redis_client.get(f"job:{job_id}")
    if not data:
        raise HTTPException(404, "Job not found")

    job = json.loads(data)
    headers = {}
    if job["status"] in ("pending", "processing"):
        headers["Retry-After"] = "3"

    return JSONResponse(content=ok(job), headers=headers)


# ═══════════════════════════════════════════════════════════
# SECTION 7: RFC 7807 Problem Details
# ═══════════════════════════════════════════════════════════

PROBLEM_MEDIA = "application/problem+json"


def problem(status: int, type_: str, title: str, detail: str,
            instance: str = None, **extra) -> JSONResponse:
    body = {
        "type":   f"https://api.demo.com/errors/{type_}",
        "title":  title,
        "status": status,
        "detail": detail,
    }
    if instance:
        body["instance"] = instance
    body.update(extra)
    return JSONResponse(status_code=status, content=body,
                        media_type=PROBLEM_MEDIA)


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(req: Request, exc: StarletteHTTPException):
    MAP = {
        400: ("bad-request",   "Bad Request"),
        401: ("unauthorized",  "Unauthorized"),
        403: ("forbidden",     "Forbidden"),
        404: ("not-found",     "Not Found"),
        409: ("conflict",      "Conflict"),
        422: ("unprocessable", "Unprocessable Entity"),
        429: ("rate-limited",  "Rate Limited"),
        500: ("server-error",  "Internal Server Error"),
    }
    type_, title = MAP.get(exc.status_code, ("error", "Error"))
    return problem(exc.status_code, type_, title, str(exc.detail),
                   instance=str(req.url))


@app.exception_handler(RequestValidationError)
async def validation_error_handler(req: Request, exc: RequestValidationError):
    return problem(
        422, "validation-error", "Validation Failed",
        "One or more fields failed validation",
        instance=str(req.url),
        errors=[{
            "field":   ".".join(str(l) for l in e["loc"]),
            "message": e["msg"],
        } for e in exc.errors()],
    )


@app.get("/users/{user_id}/transfer")
async def transfer_credits(user_id: int, to: int, amount: float):
    """Demonstrates RFC 7807 structured error responses."""
    user = FAKE_DB.get(user_id)
    if not user:
        return problem(404, "user-not-found", "User Not Found",
                       f"User {user_id} does not exist", instance=f"/users/{user_id}")

    if amount <= 0:
        return problem(400, "invalid-amount", "Invalid Amount",
                       f"Amount must be positive, got {amount}")

    if user["credits"] < amount:
        return problem(402, "insufficient-credits", "Insufficient Credits",
                       f"Need {amount} credits, have {user['credits']}",
                       required=amount, available=user["credits"])

    return ok({"transferred": amount, "from": user_id, "to": to})


# ═══════════════════════════════════════════════════════════
# SECTION 8: Pagination (Cursor + Offset)
# ═══════════════════════════════════════════════════════════

import base64

ALL_USERS = [
    {"id": i, "name": f"User {i}", "email": f"user{i}@test.com"}
    for i in range(1, 51)
]


@app.get("/users-offset")
async def list_offset(
    page:      int = Query(1, ge=1),
    page_size: int = Query(10, le=50),
):
    """Offset pagination — simple but slow on large datasets (OFFSET skips rows)."""
    total      = len(ALL_USERS)
    skip       = (page - 1) * page_size
    items      = ALL_USERS[skip: skip + page_size]
    total_pages = (total + page_size - 1) // page_size

    return ok(items, meta={
        "total":       total,
        "page":        page,
        "page_size":   page_size,
        "total_pages": total_pages,
        "has_next":    page < total_pages,
        "has_prev":    page > 1,
    })


@app.get("/users-cursor")
async def list_cursor(
    cursor: Optional[str] = Query(None),
    limit:  int           = Query(10, le=50),
):
    """
    INTERVIEW: Cursor vs Offset kab?
    Offset: simple, supports jump-to-page, slow on large data (OFFSET 100000)
    Cursor: fast at any depth, no skipped rows, no random access
    Cursor best for: infinite scroll, feeds, large datasets
    """
    users = ALL_USERS.copy()

    if cursor:
        decoded_id = int(base64.b64decode(cursor).decode())
        users = [u for u in users if u["id"] > decoded_id]

    items    = users[:limit]
    has_next = len(users) > limit

    next_cursor = None
    if has_next and items:
        next_cursor = base64.b64encode(str(items[-1]["id"]).encode()).decode()

    return ok(items, meta={
        "next_cursor": next_cursor,
        "has_next":    has_next,
        "limit":       limit,
    })


# ═══════════════════════════════════════════════════════════
# SECTION 9: Batch API (207 Multi-Status)
# ═══════════════════════════════════════════════════════════

class UserCreate(BaseModel):
    name:  str
    email: str
    plan:  str = "free"


@app.post("/users/bulk", status_code=207)
async def bulk_create_users(users: list[UserCreate]):
    """
    INTERVIEW: 207 Multi-Status kab?
    Batch operation mein kuch succeed, kuch fail ho sakta hai.
    200 = all ok, 400 = all failed — 207 = mixed results.
    """
    created = []
    errors  = []

    existing_emails = {u["email"] for u in FAKE_DB.values()}
    next_id = max(FAKE_DB.keys()) + 1 if FAKE_DB else 1

    for user_data in users:
        if user_data.email in existing_emails:
            errors.append({"email": user_data.email, "error": "Email already exists"})
        else:
            new_user = {"id": next_id, "name": user_data.name,
                        "email": user_data.email, "plan": user_data.plan, "credits": 0}
            FAKE_DB[next_id] = new_user
            existing_emails.add(user_data.email)
            created.append({"id": next_id, "email": user_data.email})
            next_id += 1

    return {
        "created": created,
        "errors":  errors,
        "summary": {"total": len(users), "created": len(created), "errors": len(errors)},
    }


# ═══════════════════════════════════════════════════════════
# SECTION 10: HATEOAS
# ═══════════════════════════════════════════════════════════

def user_links(user_id: int, plan: str) -> dict:
    links = {
        "self":   {"href": f"/users/{user_id}",          "method": "GET"},
        "update": {"href": f"/users/{user_id}",          "method": "PATCH"},
        "delete": {"href": f"/users/{user_id}",          "method": "DELETE"},
        "posts":  {"href": f"/users/{user_id}/posts",    "method": "GET"},
    }
    if plan == "free":
        links["upgrade"] = {"href": f"/users/{user_id}/upgrade", "method": "POST",
                            "title": "Upgrade to Premium"}
    return links


@app.get("/users/{user_id}/hateoas")
async def get_user_hateoas(user_id: int):
    """User response with HATEOAS links — client discovers available actions."""
    user = FAKE_DB.get(user_id)
    if not user:
        raise HTTPException(404, "User not found")

    return {
        **user,
        "_links": user_links(user_id, user["plan"]),
    }


# ═══════════════════════════════════════════════════════════
# TEST CLIENT — Run all demos
# ═══════════════════════════════════════════════════════════

async def run_tests():
    base = "http://localhost:8000"
    async with httpx.AsyncClient(base_url=base, timeout=30.0) as client:

        print("\n" + "=" * 55)
        print("API DESIGN PATTERNS — LIVE TEST")
        print("=" * 55)

        # 1. Consistent response
        print("\n[1] Consistent Response Format")
        r = await client.get("/users/1")
        data = r.json()
        print(f"  GET /users/1 → success={data['success']}, has_data={data['data'] is not None}")

        # 2. ETag + 304
        print("\n[2] ETag + 304 Not Modified")
        r1 = await client.get("/users/1")
        etag = r1.headers.get("etag", "")
        print(f"  First request  → {r1.status_code}, ETag: {etag}")
        r2 = await client.get("/users/1", headers={"If-None-Match": etag})
        print(f"  Same ETag sent → {r2.status_code} (304 = not modified, no body)")

        # 3. Rate limiting
        print("\n[3] Rate Limiting (10 req/min)")
        for i in range(3):
            r = await client.get("/protected/data", headers={"X-User-ID": "test-user-rl"})
            remaining = r.headers.get("X-RateLimit-Remaining", "?")
            print(f"  Request {i+1}: {r.status_code}, remaining={remaining}")

        # 4. Idempotency key
        print("\n[4] Idempotency Key")
        idem_key = str(uuid.uuid4())
        payload  = {"amount": 99.99, "to": "seller@test.com"}
        r1 = await client.post("/payments", json=payload,
                                headers={"Idempotency-Key": idem_key})
        r2 = await client.post("/payments", json=payload,
                                headers={"Idempotency-Key": idem_key})
        print(f"  First  call  → {r1.status_code}, replayed={r1.headers.get('X-Idempotency-Replayed', 'false')}")
        print(f"  Repeat call  → {r2.status_code}, replayed={r2.headers.get('X-Idempotency-Replayed', 'false')}")

        # 5. 202 + polling
        print("\n[5] 202 Accepted + Job Polling")
        r = await client.post("/reports", json={"type": "monthly"})
        print(f"  POST /reports → {r.status_code}, Location: {r.headers.get('Location')}")
        job_id = r.json()["job_id"]

        for attempt in range(8):
            await asyncio.sleep(0.8)
            r = await client.get(f"/jobs/{job_id}")
            status = r.json()["data"]["status"]
            progress = r.json()["data"].get("progress", 0)
            print(f"  Poll {attempt+1}: status={status}, progress={progress}%")
            if status == "completed":
                break

        # 6. RFC 7807 Error Format
        print("\n[6] RFC 7807 Problem Details Errors")
        r = await client.get("/users/999")
        print(f"  404 error: {r.headers.get('content-type', '')}")
        print(f"  Body: {r.json()}")

        r = await client.get("/users/1/transfer?to=2&amount=-50")
        print(f"  Invalid amount: type={r.json().get('type', '').split('/')[-1]}, "
              f"status={r.json().get('status')}")

        r = await client.get("/users/2/transfer?to=1&amount=99999")
        body = r.json()
        print(f"  Insufficient: required={body.get('required')}, available={body.get('available')}")

        # 7. Pagination
        print("\n[7] Pagination")
        r = await client.get("/users-offset?page=1&page_size=5")
        meta = r.json()["meta"]
        print(f"  Offset p1: items={len(r.json()['data'])}, total={meta['total']}, total_pages={meta['total_pages']}")

        r = await client.get("/users-cursor?limit=5")
        meta = r.json()["meta"]
        cursor = meta.get("next_cursor")
        print(f"  Cursor p1: items={len(r.json()['data'])}, next_cursor={cursor[:10] if cursor else None}...")

        if cursor:
            r2 = await client.get(f"/users-cursor?limit=5&cursor={cursor}")
            print(f"  Cursor p2: items={len(r2.json()['data'])}, first_id={r2.json()['data'][0]['id']}")

        # 8. Batch + 207
        print("\n[8] Batch Create (207 Multi-Status)")
        batch = [
            {"name": "Dave",  "email": "dave@test.com"},
            {"name": "Alice", "email": "alice@test.com"},  # duplicate — should fail
            {"name": "Eve",   "email": "eve@test.com"},
        ]
        r = await client.post("/users/bulk", json=batch)
        body = r.json()
        print(f"  207 response: created={len(body['created'])}, errors={len(body['errors'])}")
        print(f"  Error: {body['errors'][0]['error'] if body['errors'] else 'none'}")

        # 9. HATEOAS
        print("\n[9] HATEOAS Links")
        r = await client.get("/users/2/hateoas")  # free user
        links = r.json().get("_links", {})
        print(f"  Free user links: {list(links.keys())}")

        print("\n✓ All API design pattern tests complete!")


if __name__ == "__main__":
    print("Starting server and running tests...")
    print("Make sure server is running: uvicorn 01_api_design_practical:app --port 8000")
    asyncio.run(run_tests())


# ═══════════════════════════════════════════════════════════
# INTERVIEW QUICK REFERENCE
# ═══════════════════════════════════════════════════════════
"""
Q: ETag kaise kaam karta hai?
A: Server response mein ETag: "hash" bhejta hai
   Client next request mein If-None-Match: "hash" bhejta hai
   Server check karta hai — data same? → 304 (no body, save bandwidth)
   Data changed? → 200 + new ETag

Q: 202 kab use karo?
A: Operation > 2 seconds hai → 202 Accepted
   Body mein job_id, Location header mein polling URL
   Client poll karta rahe GET /jobs/{id} until completed

Q: Idempotency key kab chahiye?
A: POST /payments jaise non-idempotent operations mein
   Network timeout pe client retry karta hai → duplicate risk
   Idempotency-Key: UUID → server 24h store karta hai → replay same response

Q: RFC 7807 kya hai?
A: Standard error format (application/problem+json)
   Fields: type (URI), title, status, detail, instance
   Consumers programmatically handle errors by type URL

Q: Cursor vs Offset pagination?
A: Offset: OFFSET 100000 = 100000 rows skip → slow on large tables
   Cursor: WHERE id > last_id → always uses index → fast at any depth
   Cursor con: no random page access, no "jump to page 50"
   Use cursor for feeds/infinite scroll, offset for admin tables

Q: 207 Multi-Status kab?
A: Batch API mein — kuch succeed, kuch fail
   200 wrong (not all succeeded), 400 wrong (not all failed)
   207 = mixed results, body mein per-item status

Q: HATEOAS production mein use karte ho?
A: Fully rarely — overhead high
   Practically: pagination links (next/prev) + important action links (cancel, pay)
   HAL, JSON:API formats implement HATEOAS formally

Q: API Gateway ke responsibilities?
A: Auth (verify JWT once), rate limiting, routing, SSL termination,
   request/response transform, logging+tracing, circuit breaker

Q: BFF pattern kyu?
A: Mobile vs Web ke different data needs
   Mobile: lightweight, fewer fields, battery-efficient
   Web: rich data, aggregated responses
   BFF = client-specific backend layer, owned by frontend team
"""
