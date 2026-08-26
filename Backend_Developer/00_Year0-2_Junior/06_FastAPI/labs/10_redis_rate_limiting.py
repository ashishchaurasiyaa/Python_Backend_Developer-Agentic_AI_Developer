"""
FastAPI Lab 10 — Redis Rate Limiting
=======================================
ARCHITECTURE — Three Rate Limiting Algorithms:

  ┌─────────────────────────────────────────────────────────────────────┐
  │  FIXED WINDOW COUNTER                                               │
  │  ─────────────────────                                              │
  │  Key: ratelimit:{user_id}:minute:{minute_number}                    │
  │  INCR key → count                                                   │
  │  if count == 1: EXPIRE key 60                                       │
  │  if count > limit: reject 429                                       │
  │                                                                     │
  │  Problem: burst at window boundary. User can fire 100 at :59       │
  │  and 100 more at :00 next minute = 200 in 2 seconds.               │
  ├─────────────────────────────────────────────────────────────────────┤
  │  SLIDING WINDOW LOG                                                 │
  │  ──────────────────                                                 │
  │  Key: ratelimit:log:{user_id}                                       │
  │  ZREMRANGEBYSCORE key 0 (now - window_secs)   ← evict old entries  │
  │  ZADD key now now                              ← log this request   │
  │  count = ZCARD key                             ← count in window    │
  │  EXPIRE key window_secs                                             │
  │  if count > limit: reject 429                                       │
  │                                                                     │
  │  Precise — no boundary burst. Cost: one ZSet entry per request.    │
  ├─────────────────────────────────────────────────────────────────────┤
  │  TOKEN BUCKET                                                       │
  │  ────────────                                                       │
  │  Key: ratelimit:bucket:{user_id}                                    │
  │  HGETALL key → {tokens, last_refill_time}                          │
  │  refill_tokens = (now - last_refill) * rate_per_sec                │
  │  tokens = min(capacity, stored_tokens + refill_tokens)             │
  │  if tokens >= 1: tokens -= 1; allow                                │
  │  else: reject 429                                                   │
  │                                                                     │
  │  Allows bursts up to `capacity`. Refills continuously.             │
  │  Smoothest UX — doesn't punish users for being idle.               │
  └─────────────────────────────────────────────────────────────────────┘

WHY Redis for rate limiting?
  - Distributed: works across multiple API server instances
  - Atomic ops (INCR, ZADD, EXPIRE): no race conditions
  - In-memory: sub-millisecond latency per check
  - TTL: keys auto-expire (no cleanup jobs needed)

TESTING:
  Uses `fakeredis` — a Python library that runs a Redis server in-process.
  `fakeredis.aioredis.FakeRedis()` has the same API as `redis.asyncio.Redis`.
  No real Redis process needed for tests.

INTERVIEW ANSWER:
  "Redis rate limiting mein INCR + EXPIRE se fixed window banate hain — atomic
   ops hai isliye race condition nahi hoti. Sliding window ke liye sorted set
   (ZADD/ZREMRANGEBYSCORE) use karte hain — har request ek timestamp entry hai.
   Token bucket smooth bursts allow karta hai, HGETALL/HSET se tokens +
   last_refill store karte hain."

TASK:
  1. TODO 1: fixed_window_check(redis, user_id, limit, window_secs) → bool
  2. TODO 2: sliding_window_check(redis, user_id, limit, window_secs) → bool
  3. TODO 3: token_bucket_check(redis, user_id, capacity, rate_per_sec) → bool
  4. TODO 4: wire RateLimitMiddleware — call fixed_window_check, return 429 if denied
  5. Run: python 10_redis_rate_limiting.py

Prereq: pip install fastapi httpx fakeredis
"""

from __future__ import annotations

import asyncio
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

app = FastAPI(title="Lab 10 — Redis Rate Limiting")

# ════════════════════════════════════════════════════════════════════════════
# FAKE REDIS — injected via middleware constructor for easy testing
# ════════════════════════════════════════════════════════════════════════════

try:
    import fakeredis.aioredis as fakeredis_async
    FAKEREDIS_AVAILABLE = True
except ImportError:
    FAKEREDIS_AVAILABLE = False
    fakeredis_async = None  # type: ignore


def make_fake_redis():
    """Create a fresh FakeRedis async client (in-process, no server needed)."""
    if not FAKEREDIS_AVAILABLE:
        raise ImportError(
            "fakeredis not installed. Run: pip install fakeredis"
        )
    return fakeredis_async.FakeRedis()


# ════════════════════════════════════════════════════════════════════════════
# TODO 1 — Fixed Window Counter
# ════════════════════════════════════════════════════════════════════════════
"""
Implement fixed_window_check(redis, user_id, limit, window_secs) -> bool:

  Returns True  if request is ALLOWED (count <= limit after increment)
  Returns False if request is DENIED  (count > limit)

  Algorithm:
    window_key = int(time.time() // window_secs)   ← current window number
    key = f"ratelimit:fixed:{user_id}:{window_key}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, window_secs)       ← set TTL on first request
    return count <= limit

  Why INCR is atomic:
    Redis is single-threaded. INCR reads + increments + writes atomically.
    No two clients can read the same count simultaneously.

  Hint:
    async def fixed_window_check(redis, user_id: str, limit: int, window_secs: int) -> bool:
        window_key = int(time.time() // window_secs)
        key = f"ratelimit:fixed:{user_id}:{window_key}"
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, window_secs)
        return count <= limit
"""

async def fixed_window_check(redis, user_id: str, limit: int, window_secs: int) -> bool:
    raise NotImplementedError(
        "TODO 1: INCR ratelimit:fixed:{user_id}:{window_key}, EXPIRE on first, return count <= limit"
    )


# ════════════════════════════════════════════════════════════════════════════
# TODO 2 — Sliding Window Log
# ════════════════════════════════════════════════════════════════════════════
"""
Implement sliding_window_check(redis, user_id, limit, window_secs) -> bool:

  Uses a sorted set (zset) where score = timestamp of each request.

  Algorithm:
    key   = f"ratelimit:sliding:{user_id}"
    now   = time.time()
    cutoff = now - window_secs

    # Remove entries older than window
    await redis.zremrangebyscore(key, 0, cutoff)

    # Count current window entries
    count = await redis.zcard(key)

    if count >= limit:
        return False  # DENIED

    # Log this request
    await redis.zadd(key, {str(now): now})   ← member=str(now), score=now
    await redis.expire(key, window_secs)

    return True  # ALLOWED

  Note on member uniqueness:
    Two requests at the exact same `time.time()` could collide as ZSet members.
    Fix: use str(now) + uuid suffix. For this lab, str(now) is fine.

  Hint:
    async def sliding_window_check(redis, user_id: str, limit: int, window_secs: int) -> bool:
        key = f"ratelimit:sliding:{user_id}"
        now = time.time()
        cutoff = now - window_secs
        await redis.zremrangebyscore(key, 0, cutoff)
        count = await redis.zcard(key)
        if count >= limit:
            return False
        await redis.zadd(key, {str(now): now})
        await redis.expire(key, window_secs)
        return True
"""

async def sliding_window_check(redis, user_id: str, limit: int, window_secs: int) -> bool:
    raise NotImplementedError(
        "TODO 2: zremrangebyscore evict old, zcard count, zadd log new — return count < limit"
    )


# ════════════════════════════════════════════════════════════════════════════
# TODO 3 — Token Bucket
# ════════════════════════════════════════════════════════════════════════════
"""
Implement token_bucket_check(redis, user_id, capacity, rate_per_sec) -> bool:

  Stores {tokens: float, last_refill: float} in a Redis hash.

  Algorithm:
    key = f"ratelimit:bucket:{user_id}"
    now = time.time()

    data = await redis.hgetall(key)

    if data:
        stored_tokens    = float(data[b"tokens"])
        last_refill_time = float(data[b"last_refill"])
        elapsed          = now - last_refill_time
        refilled         = elapsed * rate_per_sec
        current_tokens   = min(capacity, stored_tokens + refilled)
    else:
        current_tokens = capacity  # first request: full bucket

    if current_tokens < 1:
        return False  # DENIED — no tokens

    new_tokens = current_tokens - 1
    await redis.hset(key, mapping={"tokens": new_tokens, "last_refill": now})
    await redis.expire(key, int(capacity / rate_per_sec) + 60)  ← bucket TTL
    return True  # ALLOWED

  Hint: hgetall returns bytes keys/values → float(data[b"tokens"])
"""

async def token_bucket_check(redis, user_id: str, capacity: float, rate_per_sec: float) -> bool:
    raise NotImplementedError(
        "TODO 3: hgetall → refill tokens → consume 1 → hset back → return allowed"
    )


# ════════════════════════════════════════════════════════════════════════════
# TODO 4 — RateLimitMiddleware
# ════════════════════════════════════════════════════════════════════════════
"""
Implement RateLimitMiddleware(BaseHTTPMiddleware):

  __init__(app, redis, limit=5, window_secs=60):
    self.redis       = redis
    self.limit       = limit
    self.window_secs = window_secs
    super().__init__(app)

  dispatch(request: Request, call_next) -> Response:
    1. user_id = request.headers.get("X-User-ID", "anonymous")
    2. allowed = await fixed_window_check(self.redis, user_id, self.limit, self.window_secs)
    3. If NOT allowed:
         return JSONResponse(
             {"detail": "Rate limit exceeded", "limit": self.limit},
             status_code=429,
             headers={"Retry-After": str(self.window_secs)}
         )
    4. return await call_next(request)

  Hint:
    class RateLimitMiddleware(BaseHTTPMiddleware):
        def __init__(self, app, redis, limit=5, window_secs=60):
            super().__init__(app)
            self.redis = redis
            self.limit = limit
            self.window_secs = window_secs

        async def dispatch(self, request, call_next):
            user_id = request.headers.get("X-User-ID", "anonymous")
            allowed = await fixed_window_check(self.redis, user_id, self.limit, self.window_secs)
            if not allowed:
                return JSONResponse({"detail": "Rate limit exceeded", "limit": self.limit},
                                    status_code=429, headers={"Retry-After": str(self.window_secs)})
            return await call_next(request)
"""

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, redis=None, limit: int = 5, window_secs: int = 60):
        super().__init__(app)
        self.redis       = redis
        self.limit       = limit
        self.window_secs = window_secs

    async def dispatch(self, request: Request, call_next) -> Response:
        raise NotImplementedError(
            "TODO 4: fixed_window_check → 429 if denied, else call_next"
        )


# ════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ════════════════════════════════════════════════════════════════════════════

@app.get("/api/data")
async def api_data():
    return {"data": "valuable response"}


@app.get("/health")
async def health():
    return {"status": "ok"}


# ════════════════════════════════════════════════════════════════════════════
# TESTS
# ════════════════════════════════════════════════════════════════════════════

async def run_tests():
    if not FAKEREDIS_AVAILABLE:
        print("❌ fakeredis not installed. Run: pip install fakeredis")
        print("   All tests skipped.")
        return

    passed = 0
    failed = 0

    # ── TODO 1: Fixed Window ──────────────────────────────────────────────

    print("\n── TODO 1: Fixed Window Counter ──")

    redis1 = make_fake_redis()

    # 1a. First 3 requests allowed (limit=3)
    results = [await fixed_window_check(redis1, "user1", limit=3, window_secs=60) for _ in range(3)]
    if all(results):
        print("✅ 1a. First 3 requests allowed")
        passed += 1
    else:
        print(f"❌ 1a. FAIL: First 3 should be allowed. Got: {results}")
        failed += 1

    # 1b. 4th request denied
    denied = await fixed_window_check(redis1, "user1", limit=3, window_secs=60)
    if not denied:
        print("✅ 1b. 4th request denied (over limit)")
        passed += 1
    else:
        print("❌ 1b. FAIL: 4th request should be denied. Got: True (allowed)")
        failed += 1

    # 1c. Different user not affected
    other_allowed = await fixed_window_check(redis1, "user2", limit=3, window_secs=60)
    if other_allowed:
        print("✅ 1c. Different user's counter is independent")
        passed += 1
    else:
        print("❌ 1c. FAIL: user2 should not be affected by user1's limit")
        failed += 1

    # ── TODO 2: Sliding Window ────────────────────────────────────────────

    print("\n── TODO 2: Sliding Window Log ──")

    redis2 = make_fake_redis()

    # 2a. 3 requests in window — all allowed
    results2 = [await sliding_window_check(redis2, "user1", limit=3, window_secs=60) for _ in range(3)]
    if all(results2):
        print("✅ 2a. 3 requests in window — all allowed")
        passed += 1
    else:
        print(f"❌ 2a. FAIL: First 3 should be allowed. Got: {results2}")
        failed += 1

    # 2b. 4th in same window — denied
    denied2 = await sliding_window_check(redis2, "user1", limit=3, window_secs=60)
    if not denied2:
        print("✅ 2b. 4th request in window denied")
        passed += 1
    else:
        print("❌ 2b. FAIL: 4th should be denied. Got: True")
        failed += 1

    # 2c. After window expires, allowed again
    # Simulate expiry by using a very short window and sleeping
    redis2b = make_fake_redis()
    await sliding_window_check(redis2b, "userX", limit=2, window_secs=1)
    await sliding_window_check(redis2b, "userX", limit=2, window_secs=1)
    # Now at limit — wait for window to expire
    await asyncio.sleep(1.1)
    allowed_after = await sliding_window_check(redis2b, "userX", limit=2, window_secs=1)
    if allowed_after:
        print("✅ 2c. After window expires, request allowed again")
        passed += 1
    else:
        print("❌ 2c. FAIL: After 1s window, should be allowed again. Got: False")
        failed += 1

    # ── TODO 3: Token Bucket ──────────────────────────────────────────────

    print("\n── TODO 3: Token Bucket ──")

    redis3 = make_fake_redis()

    # 3a. First request — full bucket, allowed
    allowed_tb = await token_bucket_check(redis3, "user1", capacity=3.0, rate_per_sec=1.0)
    if allowed_tb:
        print("✅ 3a. First request (full bucket) allowed")
        passed += 1
    else:
        print("❌ 3a. FAIL: Full bucket — first request should be allowed")
        failed += 1

    # 3b. Drain 2 more (total 3 used, capacity=3)
    await token_bucket_check(redis3, "user1", capacity=3.0, rate_per_sec=1.0)
    await token_bucket_check(redis3, "user1", capacity=3.0, rate_per_sec=1.0)

    # 3c. 4th request — bucket empty, denied
    denied_tb = await token_bucket_check(redis3, "user1", capacity=3.0, rate_per_sec=1.0)
    if not denied_tb:
        print("✅ 3b. Bucket empty after 3 requests — 4th denied")
        passed += 1
    else:
        print("❌ 3b. FAIL: Bucket should be empty. 4th should be denied. Got: True")
        failed += 1

    # 3d. After 1 second (rate=1/sec), 1 token refilled
    await asyncio.sleep(1.1)
    refilled_tb = await token_bucket_check(redis3, "user1", capacity=3.0, rate_per_sec=1.0)
    if refilled_tb:
        print("✅ 3c. After 1s refill (rate=1/sec), request allowed again")
        passed += 1
    else:
        print("❌ 3c. FAIL: After 1s, 1 token should refill. Got: False (still denied)")
        failed += 1

    # ── TODO 4: RateLimitMiddleware ───────────────────────────────────────

    print("\n── TODO 4: RateLimitMiddleware (integrated) ──")

    rate_redis = make_fake_redis()
    app.add_middleware(RateLimitMiddleware, redis=rate_redis, limit=3, window_secs=60)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 4a. First 3 requests from user3 — all 200
        responses = [
            await client.get("/api/data", headers={"X-User-ID": "user3"})
            for _ in range(3)
        ]
        if all(r.status_code == 200 for r in responses):
            print("✅ 4a. First 3 requests via middleware — all 200")
            passed += 1
        else:
            codes = [r.status_code for r in responses]
            print(f"❌ 4a. FAIL: First 3 should be 200. Got: {codes}")
            failed += 1

        # 4b. 4th request — 429
        resp4 = await client.get("/api/data", headers={"X-User-ID": "user3"})
        if resp4.status_code == 429:
            print("✅ 4b. 4th request via middleware → 429")
            passed += 1
        else:
            print(f"❌ 4b. FAIL: 4th should be 429. Got {resp4.status_code}: {resp4.json()}")
            failed += 1

        # 4c. 429 response has Retry-After header
        if "retry-after" in {k.lower() for k in resp4.headers}:
            print("✅ 4c. 429 has Retry-After header")
            passed += 1
        else:
            print(f"❌ 4c. FAIL: 429 should have Retry-After. Headers: {dict(resp4.headers)}")
            failed += 1

        # 4d. Different user (user4) — not affected by user3's limit
        resp_other = await client.get("/api/data", headers={"X-User-ID": "user4"})
        if resp_other.status_code == 200:
            print("✅ 4d. Different user (user4) not affected by user3's limit")
            passed += 1
        else:
            print(f"❌ 4d. FAIL: user4 should be 200. Got {resp_other.status_code}")
            failed += 1

    # ── Summary ───────────────────────────────────────────────────────
    print(f"\n{'═'*50}")
    print(f"  {passed} passed  |  {failed} failed")
    if failed == 0:
        print("  ✅ ALL PASS — Lab 10 complete!")
    else:
        print("  ❌ Fix the failing TODOs above and rerun.")
    print('═'*50)


# ════════════════════════════════════════════════════════════════════════════
# SOCH (Answer ALOUD after Lab 10)
# ════════════════════════════════════════════════════════════════════════════
"""
SOCH:

Q1: Fixed window aur sliding window mein kya fark hai?
    Boundary burst problem kya hoti hai? Example deke samjhao.

Q2: Token bucket algorithm smooth bursts kyon allow karta hai?
    capacity aur rate_per_sec ka kya matlab hai real-world mein?

Q3: Redis INCR kyon atomic hai? Bina Redis ke in-memory dict se rate limiting
    karne mein kya problem hogi distributed system mein?

Q4: Sliding window mein ZADD member collision kab hota hai?
    Production mein kaise handle karte hain?
    (Use f"{now}:{uuid.uuid4()}" as member key for uniqueness)

Q5: Rate limiting ko middleware mein rakhne ke fayde kya hain vs. decorator vs. dependency?
    (Middleware = apply to all routes; decorator = per-route; dependency = injection-based,
     testable with overrides — choose based on scope)
"""

if __name__ == "__main__":
    asyncio.run(run_tests())
