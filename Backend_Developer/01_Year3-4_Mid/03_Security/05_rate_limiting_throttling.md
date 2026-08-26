# Rate Limiting + Throttling — Token Bucket, Sliding Window, Distributed

## Quick Concepts

**WHAT:**
- **Rate limiting** = restrict requests per unit time per identifier (IP, user, API key)
- **Throttling** = slow down (queue) instead of reject
- **Token bucket** = fill rate × bucket size (allows bursts)
- **Leaky bucket** = constant outflow rate (smooth)
- **Sliding window** = exact count in last N seconds (accurate)
- **Fixed window** = count per calendar period (simple but bursty at edges)
- **429 Too Many Requests** = HTTP status for rate limit hit

---

## Andar kya hota hai — Fixed Window Bursty Kyun Hai, Sliding Window Kaise Fix Karta Hai

### Fixed window — boundary pe DOUBLE burst ho sakta hai

```
Limit: 100 req/minute, fixed window (e.g. 10:00:00-10:00:59, phir reset)

Attack: user 10:00:59 pe 100 requests bhejta hai (window ke ANT mein, sab
allowed — count abhi tak 0 tha), phir 10:01:00 pe (naya window shuru) 100
MORE requests bhejta hai — window reset hote hi count wapas 0.

Result: 2 seconds ke andar 200 requests gaye, chahe "limit" 100/min tha.
```

### Sliding window — koi FIXED reset boundary hai hi nahi

```
Sliding window log: har request ka TIMESTAMP ek log mein store karo.
  Naya request aane par: "last N seconds mein kitne timestamps hain?"
  count karo (purane timestamps expire/discard karke) — koi ek "window
  reset" moment nahi, har request apna "trailing N seconds" khud check
  karta hai.

Sliding window COUNTER (cheaper, approximate): current window ka count +
  PREVIOUS window ka count × (kitna % overlap abhi bhi "sliding window"
  mein hai) — poora log store kiye bina, approximately sliding behavior.
```

Fixed window ka boundary-double-burst bug isliye nahi hota — koi single
"reset moment" hi nahi hai jispe attacker time kar sake.

### Token bucket — implementation Redis mein ATOMIC hona zaroori hai

```
Bucket state: {tokens: N, last_refill: timestamp}
Har request: (1) time-elapsed se naye tokens calculate karke ADD karo
  (capped at bucket_size), (2) agar tokens >= 1, ek token consume karo aur
  ALLOW, warna REJECT
```

Yeh READ-MODIFY-WRITE hai — do concurrent requests agar ek-doosre ke
BEECH mein "read" kar len to dono ko token available dikh sakta hai jo
actually ek hi tha (race condition, same TOCTOU bug jo `07_advanced_patterns.md`
FastAPI file mein cover hua). Production mein yeh ek ATOMIC Lua script se
Redis mein implement hota hai — poora read+update ek hi atomic operation.

**WHY rate limit:**
- ✅ Prevent abuse (scraping, brute force)
- ✅ Protect downstream services
- ✅ Fair usage across users
- ✅ Cost control (per-user API quotas)
- ✅ Prevent DoS attacks

**HOW algorithm comparison:**

```
┌──────────────────┬─────────────┬─────────────┬──────────────┐
│   Algorithm      │ Allows burst│  Accurate   │  Memory      │
├──────────────────┼─────────────┼─────────────┼──────────────┤
│ Fixed Window     │  Yes (edge) │  No         │  O(1)        │
│ Sliding Window   │  No         │  Yes        │  O(N)        │
│ Token Bucket     │  Yes        │  Yes        │  O(1)        │
│ Leaky Bucket     │  No (smooth)│  Yes        │  O(1)        │
└──────────────────┴─────────────┴─────────────┴──────────────┘
```

---

## Interview Questions & Answers

### Q1: Token Bucket algorithm explain karo with implementation?

**Answer:**

**WHAT:** Bucket with capacity N, refills at rate R tokens/sec. Each request consumes 1 token.

**WHY:**
- ✅ Allows controlled bursts (good for user experience)
- ✅ O(1) memory per user
- ✅ Simple math
- ✅ Industry standard (AWS, Stripe use it)

**HOW — Mental model:**
```
Bucket capacity: 10 tokens
Refill rate: 2 tokens/sec

t=0:   [████████████] 10 tokens
       User makes 5 requests → 5 tokens consumed
t=0.5: [██████░░░░░░] 5 tokens
       Refill: 1 token (0.5 × 2)
t=1.0: [███████░░░░░] 6 tokens
       User makes 8 requests → only 6 allowed (rate limited)
```

**HOW — Python implementation:**

```python
import time
import asyncio
from dataclasses import dataclass

@dataclass
class TokenBucket:
    """
    INTERVIEW: Token bucket — simple, allows bursts.
    """
    capacity: int           # Max tokens (burst size)
    refill_rate: float      # Tokens per second
    tokens: float = 0
    last_refill: float = 0

    def __post_init__(self):
        self.tokens = self.capacity
        self.last_refill = time.time()

    def try_consume(self, count: int = 1) -> bool:
        """
        Returns True if allowed, False if rate limited.
        """
        now = time.time()

        # Refill tokens since last check
        elapsed = now - self.last_refill
        self.tokens = min(
            self.capacity,
            self.tokens + elapsed * self.refill_rate
        )
        self.last_refill = now

        # Try to consume
        if self.tokens >= count:
            self.tokens -= count
            return True
        return False


# Usage
bucket = TokenBucket(capacity=10, refill_rate=2)   # 10 burst, 2/sec sustain

for i in range(15):
    if bucket.try_consume():
        print(f"Request {i+1}: ✅ Allowed")
    else:
        print(f"Request {i+1}: ❌ Rate limited")
    time.sleep(0.1)
```

**Real-world params:**
- API: `capacity=100, refill_rate=10` (10 RPS sustained, 100 burst)
- Login: `capacity=5, refill_rate=0.1` (1 every 10s, 5 burst)
- Heavy endpoint: `capacity=10, refill_rate=1`

---

### Q2: Sliding Window algorithm — Redis se distributed kaise karein?

**Answer:**

**WHAT:** Count requests in EXACT last N seconds (no edge bursting like fixed window).

**WHY:**
- ✅ More accurate than fixed window
- ✅ No bursting issues
- ❌ More memory (stores timestamps)

**HOW — Redis sorted sets:**

```python
import redis.asyncio as redis
import time
import uuid

class SlidingWindowRateLimiter:
    """
    INTERVIEW: Sliding window using Redis sorted set.
    Score = timestamp, Member = unique request ID.
    """
    def __init__(self, redis_client: redis.Redis, limit: int, window_seconds: int):
        self.redis = redis_client
        self.limit = limit
        self.window = window_seconds

    async def is_allowed(self, identifier: str) -> tuple[bool, dict]:
        """
        Returns (allowed, info_dict).
        """
        key = f"ratelimit:{identifier}"
        now = time.time() * 1000   # milliseconds
        window_start = now - (self.window * 1000)

        pipe = self.redis.pipeline()

        # 1. Remove expired entries
        pipe.zremrangebyscore(key, 0, window_start)

        # 2. Count current entries in window
        pipe.zcard(key)

        # 3. Add this request (unique ID to avoid duplicates)
        request_id = f"{now}:{uuid.uuid4().hex[:8]}"
        pipe.zadd(key, {request_id: now})

        # 4. Set expiry (cleanup if no activity)
        pipe.expire(key, self.window + 1)

        results = await pipe.execute()
        current_count = results[1]   # Count BEFORE adding new one

        allowed = current_count < self.limit
        remaining = max(0, self.limit - current_count - 1)

        # Calculate reset time
        if not allowed:
            # When does oldest request expire?
            oldest = await self.redis.zrange(key, 0, 0, withscores=True)
            reset_at = (oldest[0][1] + self.window * 1000) / 1000 if oldest else now / 1000
        else:
            reset_at = (now + self.window * 1000) / 1000

        return allowed, {
            "limit": self.limit,
            "remaining": remaining,
            "reset_at": int(reset_at),
            "retry_after": max(0, int(reset_at - now / 1000)) if not allowed else 0,
        }


# Usage in FastAPI
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

app = FastAPI()
redis_client = redis.from_url("redis://localhost:6379/2")
limiter = SlidingWindowRateLimiter(redis_client, limit=100, window_seconds=60)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # Identify by user_id (preferred) or IP
    user_id = request.headers.get("X-User-Id")
    identifier = user_id if user_id else request.client.host

    allowed, info = await limiter.is_allowed(identifier)

    if not allowed:
        return JSONResponse(
            status_code=429,
            headers={
                "X-RateLimit-Limit": str(info["limit"]),
                "X-RateLimit-Remaining": str(info["remaining"]),
                "X-RateLimit-Reset": str(info["reset_at"]),
                "Retry-After": str(info["retry_after"]),
            },
            content={"error": "Rate limit exceeded", "retry_after": info["retry_after"]}
        )

    response = await call_next(request)

    # Add headers to successful responses too
    response.headers["X-RateLimit-Limit"] = str(info["limit"])
    response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
    response.headers["X-RateLimit-Reset"] = str(info["reset_at"])

    return response
```

---

### Q3: Per-user vs per-IP vs per-endpoint rate limits — kab kya?

**Answer:**

**WHAT:** Different strategies for different threat models.

**HOW — Multi-tier rate limiting:**

```python
class MultiTierRateLimiter:
    """
    INTERVIEW: Real production rate limiting has MULTIPLE limits per request.
    """
    def __init__(self, redis_client):
        self.redis = redis_client

        # ⭐ Tier 1: Global (DDoS protection)
        self.global_limiter = SlidingWindowRateLimiter(redis_client, 10000, 60)

        # ⭐ Tier 2: Per IP (anonymous abuse)
        self.ip_limiter = SlidingWindowRateLimiter(redis_client, 100, 60)

        # ⭐ Tier 3: Per user (authenticated)
        self.user_limiter = SlidingWindowRateLimiter(redis_client, 1000, 60)

        # ⭐ Tier 4: Per endpoint (expensive operations)
        self.endpoint_limiters = {
            "/api/login": SlidingWindowRateLimiter(redis_client, 5, 60),     # 5/min login
            "/api/upload": SlidingWindowRateLimiter(redis_client, 10, 60),   # 10/min upload
            "/api/search": SlidingWindowRateLimiter(redis_client, 60, 60),   # 60/min search
        }

    async def check(self, ip: str, user_id: str | None, endpoint: str) -> tuple[bool, dict]:
        # Check all applicable tiers
        checks = []

        # Global
        global_ok, global_info = await self.global_limiter.is_allowed("global")
        checks.append(("global", global_ok, global_info))

        # Per IP
        ip_ok, ip_info = await self.ip_limiter.is_allowed(f"ip:{ip}")
        checks.append(("ip", ip_ok, ip_info))

        # Per user (if authenticated)
        if user_id:
            user_ok, user_info = await self.user_limiter.is_allowed(f"user:{user_id}")
            checks.append(("user", user_ok, user_info))

        # Per endpoint
        if endpoint in self.endpoint_limiters:
            ep_ok, ep_info = await self.endpoint_limiters[endpoint].is_allowed(
                f"{endpoint}:{user_id or ip}"
            )
            checks.append(("endpoint", ep_ok, ep_info))

        # ANY tier rejecting = reject
        for tier, ok, info in checks:
            if not ok:
                return False, {"failed_tier": tier, **info}

        # Return most restrictive remaining count
        min_remaining = min(c[2]["remaining"] for c in checks)
        return True, {"remaining": min_remaining}
```

**Recommended limits:**

| Identifier | Endpoint | Limit | Window | Why |
|---|---|---|---|---|
| Anonymous IP | GET /api/* | 100 | 60s | Scraping prevention |
| Anonymous IP | POST /api/login | 5 | 60s | Brute force |
| Authenticated user | GET /api/* | 1000 | 60s | Free tier |
| Pro user | GET /api/* | 10000 | 60s | Paid tier |
| API key | All | 10000 | 60s | Server-to-server |
| Global | All | 50000 | 60s | DDoS guard |

---

### Q4: Distributed rate limiting — multi-instance challenges?

**Answer:**

**WHAT:** Rate limiting across multiple application instances.

**WHY distributed is hard:**
```
Single instance:
- In-memory counter works fine

Multi-instance (5 pods):
- Each pod tracks separately
- User can do 100 req/min × 5 pods = 500 req/min total!
- Solution: shared store (Redis)
```

**HOW — Centralized counter (Redis):**

```python
# Already covered in Q2 with sliding window
# Key: distributed key naming
async def rate_limit_check(user_id: str):
    key = f"ratelimit:{user_id}:{int(time.time() // 60)}"   # Per-minute key
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, 60)
    return count <= LIMIT
```

**HOW — Hierarchical (local + central):**

```python
class HierarchicalRateLimiter:
    """
    INTERVIEW: Combine local cache + central Redis.
    Local: fast, allows burst.
    Central: enforces hard limit across instances.
    """
    def __init__(self, redis_client, local_limit: int, global_limit: int, window: int):
        self.redis = redis_client
        # Local bucket (allows N before checking Redis)
        self.local_buckets: dict[str, TokenBucket] = {}
        self.local_limit = local_limit
        self.global_limit = global_limit
        self.window = window

    async def is_allowed(self, identifier: str) -> bool:
        # 1. Local check first (fast path)
        if identifier not in self.local_buckets:
            self.local_buckets[identifier] = TokenBucket(
                capacity=self.local_limit,
                refill_rate=self.local_limit / self.window
            )

        if not self.local_buckets[identifier].try_consume():
            return False    # Rejected locally

        # 2. Central check (slower but accurate)
        key = f"ratelimit:{identifier}:{int(time.time() // self.window)}"
        count = await self.redis.incr(key)
        if count == 1:
            await self.redis.expire(key, self.window)

        return count <= self.global_limit
```

**HOW — Token bucket sync via Redis Lua (atomic):**

```python
LUA_TOKEN_BUCKET = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local requested = tonumber(ARGV[4])

local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(bucket[1]) or capacity
local last_refill = tonumber(bucket[2]) or now

-- Refill
local elapsed = now - last_refill
tokens = math.min(capacity, tokens + elapsed * refill_rate)

-- Try consume
local allowed = 0
if tokens >= requested then
    tokens = tokens - requested
    allowed = 1
end

-- Save
redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
redis.call('EXPIRE', key, 3600)

return {allowed, tokens}
"""


async def atomic_token_bucket_check(redis, key: str, capacity: int, rate: float):
    """Atomic — no race conditions between instances."""
    script = redis.register_script(LUA_TOKEN_BUCKET)
    result = await script(
        keys=[key],
        args=[capacity, rate, time.time(), 1]
    )
    allowed, tokens_left = result
    return bool(allowed), tokens_left
```

---

### Q5: 429 response format + Retry-After header — proper way?

**Answer:**

**WHAT:** Standard HTTP response format for rate-limited requests.

**HOW — RFC-compliant response:**

```python
from fastapi.responses import JSONResponse

def rate_limit_response(info: dict) -> JSONResponse:
    """
    INTERVIEW: 429 with proper headers.
    """
    return JSONResponse(
        status_code=429,
        headers={
            # ⭐ Standard headers (clients understand these)
            "X-RateLimit-Limit": str(info["limit"]),
            "X-RateLimit-Remaining": str(info["remaining"]),
            "X-RateLimit-Reset": str(info["reset_at"]),     # Unix timestamp

            # ⭐ Retry-After (RFC 7231) — seconds OR HTTP date
            "Retry-After": str(info["retry_after"]),
        },
        content={
            "error": "rate_limit_exceeded",
            "message": "Too many requests",
            "limit": info["limit"],
            "remaining": info["remaining"],
            "reset_at": info["reset_at"],
            "retry_after_seconds": info["retry_after"],
        }
    )
```

**HOW — Client respects Retry-After:**

```python
import httpx
import asyncio

async def make_request_with_retry(url: str, max_retries: int = 3):
    """
    INTERVIEW: Respect server's Retry-After header.
    """
    for attempt in range(max_retries):
        async with httpx.AsyncClient() as client:
            response = await client.get(url)

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            print(f"Rate limited. Waiting {retry_after}s...")
            await asyncio.sleep(retry_after)
            continue

        return response

    raise Exception("Max retries exceeded")
```

---

### Q6: DDoS protection — application + infrastructure layers?

**Answer:**

**WHAT:** Defense against Distributed Denial of Service.

**WHY layered approach:**
- Application alone can't handle volumetric DDoS
- Need infrastructure + edge + application defense

**HOW — Layered defense:**

```
┌─────────────────────────────────────────────────────┐
│ Layer 1: Edge (Cloudflare / AWS Shield)             │
│ - L3/L4 DDoS protection                             │
│ - Geographic blocking                                │
│ - Bot detection                                      │
├─────────────────────────────────────────────────────┤
│ Layer 2: AWS WAF                                    │
│ - Rule-based filtering                              │
│ - Rate limiting per IP                              │
│ - Geo-blocking                                       │
├─────────────────────────────────────────────────────┤
│ Layer 3: ALB / Nginx                                │
│ - Connection limits                                  │
│ - SSL termination                                    │
│ - Request size limits                                │
├─────────────────────────────────────────────────────┤
│ Layer 4: Application                                │
│ - Per-user rate limiting                            │
│ - Per-endpoint quotas                               │
│ - CAPTCHA for suspicious traffic                    │
└─────────────────────────────────────────────────────┘
```

**HOW — AWS WAF rate limiting:**

```hcl
# Terraform — AWS WAF rate limit rule
resource "aws_wafv2_web_acl" "main" {
  name  = "api-protection"
  scope = "REGIONAL"

  default_action {
    allow {}
  }

  rule {
    name     = "RateLimitPerIP"
    priority = 1

    statement {
      rate_based_statement {
        limit              = 2000           # ⭐ 2000 requests per 5 min per IP
        aggregate_key_type = "IP"
      }
    }

    action {
      block {}
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "RateLimitPerIP"
      sampled_requests_enabled   = true
    }
  }

  # Geo blocking
  rule {
    name     = "BlockHighRiskCountries"
    priority = 2

    statement {
      geo_match_statement {
        country_codes = ["XX", "YY"]    # ISO codes
      }
    }

    action {
      block {}
    }
  }
}
```

**HOW — Nginx rate limiting (infrastructure):**

```nginx
# nginx.conf

# Define zones (shared memory)
http {
  # Per IP, 10 MB zone, 10 req/sec
  limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;

  # Per user (from header), 100 req/sec
  limit_req_zone $http_x_user_id zone=user_limit:10m rate=100r/s;

  # Connection limit
  limit_conn_zone $binary_remote_addr zone=conn_limit:10m;

  server {
    listen 443 ssl;

    # 5 concurrent connections per IP
    limit_conn conn_limit 5;

    location /api/ {
      # Per IP rate limit (burst 20, delay queue rejected)
      limit_req zone=api_limit burst=20 nodelay;

      # Per user rate limit
      limit_req zone=user_limit burst=200 nodelay;

      # 429 response
      limit_req_status 429;

      proxy_pass http://backend;
    }
  }
}
```

---

### Q7: slowapi (FastAPI library) — production usage?

**Answer:**

**WHAT:** Python rate limiting library for Flask + FastAPI.

**HOW — FastAPI integration:**

```python
# pip install slowapi

from fastapi import FastAPI, Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# ⭐ Use Redis backend for distributed
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="redis://localhost:6379/3",
    strategy="moving-window",    # sliding window
)

app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ⭐ Per-endpoint limits
@app.get("/api/users")
@limiter.limit("100/minute")
async def list_users(request: Request):
    return {"users": []}


@app.post("/api/login")
@limiter.limit("5/minute")        # Strict for login
async def login(request: Request):
    return {"token": "..."}


# ⭐ Custom key function (per user)
async def get_user_id(request: Request):
    return request.headers.get("X-User-Id", get_remote_address(request))


@app.get("/api/data")
@limiter.limit("1000/minute", key_func=get_user_id)
async def get_data(request: Request):
    return {"data": []}


# ⭐ Multiple limits (any failing rejects)
@app.get("/api/expensive")
@limiter.limit("10/minute")
@limiter.limit("100/hour")
@limiter.limit("1000/day")
async def expensive_endpoint(request: Request):
    return {"result": "..."}


# ⭐ Bypass for specific keys (admin)
@app.get("/api/admin")
@limiter.limit("10000/minute", exempt_when=lambda: is_admin())
async def admin_endpoint(request: Request):
    return {"data": "..."}
```

---

### Q8: Pricing/quota tiers — Stripe-style implementation?

**Answer:**

**WHAT:** Different rate limits per subscription tier.

**HOW — Tiered limits:**

```python
from enum import Enum

class Tier(str, Enum):
    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    ENTERPRISE = "enterprise"


TIER_LIMITS = {
    Tier.FREE: {
        "requests_per_minute": 60,
        "requests_per_day": 1000,
        "max_request_size_mb": 1,
        "concurrent_connections": 5,
    },
    Tier.STARTER: {
        "requests_per_minute": 600,
        "requests_per_day": 100000,
        "max_request_size_mb": 10,
        "concurrent_connections": 50,
    },
    Tier.PRO: {
        "requests_per_minute": 6000,
        "requests_per_day": 10_000_000,
        "max_request_size_mb": 100,
        "concurrent_connections": 500,
    },
    Tier.ENTERPRISE: {
        "requests_per_minute": 60000,
        "requests_per_day": float("inf"),
        "max_request_size_mb": 1000,
        "concurrent_connections": 5000,
    },
}


class TieredRateLimiter:
    """
    INTERVIEW: Different limits per subscription tier.
    """
    def __init__(self, redis_client):
        self.redis = redis_client

    async def check(self, user_id: str, tier: Tier) -> tuple[bool, dict]:
        limits = TIER_LIMITS[tier]

        # Per-minute
        minute_limiter = SlidingWindowRateLimiter(
            self.redis,
            limits["requests_per_minute"],
            60
        )
        minute_ok, minute_info = await minute_limiter.is_allowed(f"user:{user_id}:min")

        if not minute_ok:
            return False, {"limit_type": "per_minute", **minute_info}

        # Per-day (separate key)
        day_limiter = SlidingWindowRateLimiter(
            self.redis,
            limits["requests_per_day"],
            86400
        )
        day_ok, day_info = await day_limiter.is_allowed(f"user:{user_id}:day")

        if not day_ok:
            return False, {"limit_type": "per_day", **day_info}

        return True, {"tier": tier.value, **minute_info}


# Usage
@app.middleware("http")
async def tiered_rate_limit(request: Request, call_next):
    user = await get_current_user(request)
    if not user:
        return await call_next(request)

    allowed, info = await tiered_limiter.check(user.id, user.tier)
    if not allowed:
        return rate_limit_response(info)

    return await call_next(request)
```

---

## Rate Limiting Checklist

```markdown
### Configuration
- [ ] Define limits per tier (free, paid)
- [ ] Per-endpoint limits for expensive operations
- [ ] Separate limits for auth endpoints (login, signup)
- [ ] Global DDoS limit

### Implementation
- [ ] Use Redis for distributed (not in-memory)
- [ ] Atomic operations (Lua script OR sorted sets)
- [ ] Multi-tier (IP + user + endpoint)
- [ ] Skip authenticated admin/internal calls

### Response
- [ ] Return 429 status code
- [ ] Include Retry-After header
- [ ] X-RateLimit-Limit, Remaining, Reset headers
- [ ] Clear error message in body

### Monitoring
- [ ] Metrics: rate_limit_hits_total{endpoint, tier}
- [ ] Alerts on sustained 429 spike (real attack vs misconfig)
- [ ] Log rate-limited requests for analysis
- [ ] Dashboard for top rate-limited IPs/users

### Edge Protection
- [ ] AWS WAF / Cloudflare for L7 DDoS
- [ ] AWS Shield for L3/L4 DDoS
- [ ] Geo-blocking high-risk countries
- [ ] Bot detection
```

---

## Common Pitfalls

| Pitfall | Impact | Fix |
|---|---|---|
| In-memory rate limiter | Doesn't work across instances | Use Redis |
| Race condition (check + increment) | Allows over limit | Use atomic Lua script |
| Per-IP only | Shared IPs (NAT, mobile) over-blocked | Per-user when authenticated |
| No 429 + headers | Clients can't auto-recover | Always include Retry-After |
| Fixed window | Edge bursting (2x limit possible) | Use sliding window |
| Same limit for login + GET | Brute force easier | Strict limits on auth endpoints |
| No DDoS edge protection | Application overwhelmed | AWS WAF / Cloudflare |
