# FastAPI Rate Limiting — slowapi, Token Bucket, Redis-backed

## Why It Matters

Every public API needs rate limiting or one client (buggy retry loop, scraper,
abusive user) can starve everyone else. It's also a classic system-design
follow-up after any FastAPI question: "You've built the endpoint — now how do
you stop it being hammered?"

Senior interview: "Design rate limiting for a multi-instance API." →
Redis-backed token bucket (not in-memory — breaks across replicas), per-user
+ per-IP layered limits, 429 with `Retry-After`.

---

## Core Concepts

### Why in-memory rate limiting breaks in production

```python
# NAIVE — works on 1 process, breaks the moment you run 2+ replicas
# behind a load balancer, since each process has its own counter dict.
from collections import defaultdict
import time

request_log = defaultdict(list)

def is_allowed(client_id: str, limit: int = 10, window: int = 60) -> bool:
    now = time.time()
    request_log[client_id] = [t for t in request_log[client_id] if now - t < window]
    if len(request_log[client_id]) >= limit:
        return False
    request_log[client_id].append(now)
    return True
```

Fix: back the counter with **Redis**, shared across every replica.

---

### slowapi — the standard FastAPI rate-limiting library

```python
# pip install slowapi
from fastapi import FastAPI, Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)  # default: rate-limit by IP
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.get("/search")
@limiter.limit("10/minute")
async def search(request: Request, q: str):
    return {"results": []}
```

`slowapi` wraps the battle-tested `limits` library and supports Redis/Memcached
storage backends for multi-replica correctness:

```python
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="redis://localhost:6379",
)
```

### Per-user limits (not just per-IP)

```python
def get_user_key(request: Request) -> str:
    # Use authenticated user id if available, fall back to IP
    user = getattr(request.state, "user", None)
    return f"user:{user.id}" if user else get_remote_address(request)

limiter = Limiter(key_func=get_user_key, storage_uri="redis://localhost:6379")

@app.get("/reports")
@limiter.limit("5/minute")   # tighter limit — expensive endpoint
async def generate_report(request: Request):
    ...
```

---

### Token Bucket algorithm (what's happening under the hood)

```
Bucket holds up to N tokens, refills at rate R tokens/second.
Each request consumes 1 token. No tokens → reject (429).

Why token bucket over fixed window:
- Fixed window: burst of 2x limit possible right at window boundary
  (e.g., 100 req at 11:59:59 + 100 req at 12:00:00 = 200 in 1 second)
- Token bucket: smooths bursts, allows short bursts up to bucket size
  while enforcing a true average rate
```

```python
# Manual Redis token-bucket (if not using slowapi) — Lua script for atomicity
import redis.asyncio as redis

TOKEN_BUCKET_LUA = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(bucket[1]) or capacity
local last_refill = tonumber(bucket[2]) or now

local elapsed = now - last_refill
tokens = math.min(capacity, tokens + elapsed * refill_rate)

if tokens < 1 then
    return 0
end

tokens = tokens - 1
redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
redis.call('EXPIRE', key, 3600)
return 1
"""

async def is_allowed(r: redis.Redis, user_id: str, capacity=10, refill_rate=0.5) -> bool:
    import time
    result = await r.eval(TOKEN_BUCKET_LUA, 1, f"ratelimit:{user_id}",
                           capacity, refill_rate, time.time())
    return bool(result)
```

The Lua script matters: without it, "read tokens → check → decrement" is 3
separate Redis round-trips, race-prone under concurrent requests. Lua runs
atomically inside Redis.

---

### Layered limits (defense in depth)

```python
# Different limits at different layers — narrowest wins
@app.get("/api/expensive-ml-endpoint")
@limiter.limit("100/day")      # daily ceiling per user
@limiter.limit("5/minute")     # burst protection
async def expensive_endpoint(request: Request):
    ...
```

Production APIs typically layer: **global IP limit** (anti-DDoS, at the
load-balancer/API-gateway level) → **per-user limit** (fairness) →
**per-endpoint limit** (protect expensive operations specifically).

---

### 429 Response + Retry-After (client contract)

```python
from fastapi import Request
from fastapi.responses import JSONResponse

async def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded", "retry_after": 60},
        headers={"Retry-After": "60"},
    )

app.add_exception_handler(RateLimitExceeded, custom_rate_limit_handler)
```

`Retry-After` is the standard header well-behaved clients read to back off —
without it, retry storms just hit you again immediately.

---

## Interview Q&A

**Q: Why not just use a Python dict for rate limiting?**
A: Breaks the moment you scale to 2+ processes/replicas — each has its own
counter, so the real limit becomes `N × limit`. Must be centralized (Redis).

**Q: Token bucket vs fixed window vs sliding window log?**
A: Fixed window is simplest but allows 2x burst at window boundaries. Sliding
window log is most accurate but stores every timestamp (memory-heavy). Token
bucket is the production standard — smooths bursts, O(1) memory per key.

**Q: How do you rate-limit differently for free vs paid tiers?**
A: Key the limiter by user tier, not just user id — `Limiter` supports a
dynamic limit string via a callable, e.g., `"100/minute" if user.is_premium else "10/minute"`.

---

Related: [23_fastapi_caching.md](23_fastapi_caching.md) (same Redis instance
often backs both caching and rate limiting), [20_owasp_api_top10.md](20_owasp_api_top10.md)
(API4:2023 — Unrestricted Resource Consumption, which rate limiting directly mitigates).
