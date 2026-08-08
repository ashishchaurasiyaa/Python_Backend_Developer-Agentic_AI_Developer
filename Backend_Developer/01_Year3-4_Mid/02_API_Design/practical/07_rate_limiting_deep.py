"""
Rate Limiting — Production Patterns

All major algorithms + framework integrations.
"""

import os
import time
import uuid
import redis


r = redis.Redis(host='localhost', port=6379, decode_responses=True)


# ==========================================================================
# 1. TOKEN BUCKET (most flexible, Lua-atomic)
# ==========================================================================

TOKEN_BUCKET_SCRIPT = r.register_script("""
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local cost = tonumber(ARGV[4])

local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(bucket[1]) or capacity
local last_refill = tonumber(bucket[2]) or now

-- Refill
local elapsed = now - last_refill
tokens = math.min(capacity, tokens + elapsed * refill_rate)

if tokens >= cost then
    tokens = tokens - cost
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
    redis.call('EXPIRE', key, 3600)
    return {1, tokens}
end

redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
redis.call('EXPIRE', key, 3600)
return {0, tokens}
""")


def token_bucket(key, capacity=10, refill_rate=0.5, cost=1):
    """Returns (allowed, tokens_remaining)."""
    result = TOKEN_BUCKET_SCRIPT(
        keys=[key],
        args=[capacity, refill_rate, time.time(), cost],
    )
    return bool(result[0]), float(result[1])


# Usage examples:
# token_bucket('user:123', capacity=10, refill_rate=1)  # burst 10, sustain 1/sec
# token_bucket('user:123:expensive', capacity=5, refill_rate=5/3600, cost=1)


# ==========================================================================
# 2. SLIDING WINDOW LOG (exact count)
# ==========================================================================

SLIDING_LOG_SCRIPT = r.register_script("""
local key = KEYS[1]
local cutoff = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local entry = ARGV[4]
local window = tonumber(ARGV[5])

-- Remove old entries
redis.call('ZREMRANGEBYSCORE', key, 0, cutoff)

-- Count current
local count = redis.call('ZCARD', key)

if count >= limit then
    -- Get oldest entry to compute retry_after
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local retry_after = 0
    if oldest[2] then
        retry_after = math.ceil(tonumber(oldest[2]) + window - now)
    end
    return {0, count, retry_after}
end

redis.call('ZADD', key, now, entry)
redis.call('EXPIRE', key, window)
return {1, count + 1, 0}
""")


def sliding_window_log(key, limit=100, window_seconds=60):
    """Returns (allowed, count, retry_after_seconds)."""
    now = time.time()
    entry = f'{now}:{uuid.uuid4().hex[:8]}'   # unique per request
    cutoff = now - window_seconds

    result = SLIDING_LOG_SCRIPT(
        keys=[key],
        args=[cutoff, limit, now, entry, window_seconds],
    )
    return bool(result[0]), int(result[1]), int(result[2])


# ==========================================================================
# 3. SLIDING WINDOW COUNTER (memory-efficient hybrid)
# ==========================================================================

def sliding_window_counter(key, limit=100, window=60):
    """Returns (allowed, estimated_count)."""
    now = int(time.time())
    current_bucket = now // window
    previous_bucket = current_bucket - 1
    elapsed_in_current = now % window
    weight = (window - elapsed_in_current) / window

    current_key = f'{key}:{current_bucket}'
    previous_key = f'{key}:{previous_bucket}'

    pipe = r.pipeline()
    pipe.incr(current_key)
    pipe.expire(current_key, window * 2)
    pipe.get(previous_key)
    current_count, _, previous_count = pipe.execute()

    previous_count = int(previous_count or 0)
    estimated = previous_count * weight + current_count

    return estimated <= limit, estimated


# ==========================================================================
# 4. FIXED WINDOW (simplest)
# ==========================================================================

def fixed_window(key, limit=100, window=60):
    """Returns (allowed, current_count)."""
    bucket = int(time.time()) // window
    full_key = f'{key}:{bucket}'

    count = r.incr(full_key)
    if count == 1:
        r.expire(full_key, window)

    return count <= limit, count


# ==========================================================================
# 5. MULTI-DIMENSIONAL RATE LIMIT
# ==========================================================================

def multi_dimension_check(user_id, endpoint, tier='free'):
    """Check all rate limit dimensions; return (allowed, violated_dimension)."""

    tier_limits = {
        'free': {'global': (100, 3600), 'per_endpoint': (10, 60)},
        'pro': {'global': (5000, 3600), 'per_endpoint': (100, 60)},
        'enterprise': {'global': (100000, 3600), 'per_endpoint': (1000, 60)},
    }
    limits = tier_limits[tier]

    expensive_endpoints = {'/llm/chat', '/search', '/export'}

    checks = [
        ('global', f'rl:g:{user_id}', limits['global'][0], limits['global'][0] / limits['global'][1]),
        ('endpoint', f'rl:e:{user_id}:{endpoint}', limits['per_endpoint'][0], limits['per_endpoint'][0] / limits['per_endpoint'][1]),
    ]

    if endpoint in expensive_endpoints:
        # Extra strict on expensive
        checks.append(('expensive', f'rl:exp:{user_id}', 50, 50 / 3600))

    for name, key, capacity, rate in checks:
        allowed, _ = token_bucket(key, capacity=capacity, refill_rate=rate)
        if not allowed:
            return False, name

    return True, None


# ==========================================================================
# 6. COST-BASED (LLM/expensive endpoints)
# ==========================================================================

ENDPOINT_COSTS = {
    '/chat/completions': 100,
    '/embeddings': 10,
    '/moderation': 1,
    '/health': 0,
}


def cost_based_check(user_id, endpoint, daily_budget=10000):
    """Each user has daily token budget; expensive endpoints cost more."""
    cost = ENDPOINT_COSTS.get(endpoint, 1)
    if cost == 0:
        return True, daily_budget

    return token_bucket(
        f'cost:{user_id}',
        capacity=daily_budget,
        refill_rate=daily_budget / 86400,
        cost=cost,
    )


# ==========================================================================
# 7. FASTAPI MIDDLEWARE
# ==========================================================================

"""
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse


app = FastAPI()


@app.middleware('http')
async def rate_limit_middleware(request: Request, call_next):
    # Skip health checks
    if request.url.path in ('/health/live', '/health/ready', '/metrics'):
        return await call_next(request)

    # Get identifier (user_id if authenticated, else IP)
    user_id = getattr(request.state, 'user_id', None)
    identifier = f'user:{user_id}' if user_id else f'ip:{request.client.host}'

    # Get tier from auth
    tier = getattr(request.state, 'user_tier', 'free')

    # Check multi-dimension
    allowed, violated = multi_dimension_check(identifier, request.url.path, tier)

    if not allowed:
        return JSONResponse(
            {
                'error': 'rate_limited',
                'detail': f'Rate limit exceeded ({violated})',
            },
            status_code=429,
            headers={
                'Retry-After': '60',
                'X-RateLimit-Resource': violated,
            },
        )

    response = await call_next(request)

    # Add headers showing remaining
    _, remaining = token_bucket(f'rl:g:{identifier}', capacity=100, refill_rate=1, cost=0)
    response.headers['X-RateLimit-Limit'] = '100'
    response.headers['X-RateLimit-Remaining'] = str(int(remaining))

    return response
"""


# ==========================================================================
# 8. SLOWAPI INTEGRATION (FastAPI)
# ==========================================================================

"""
# pip install slowapi

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded


# Use user_id as key if authenticated
def get_user_or_ip(request):
    user_id = getattr(request.state, 'user_id', None)
    if user_id:
        return f'user:{user_id}'
    return get_remote_address(request)


limiter = Limiter(
    key_func=get_user_or_ip,
    storage_uri='redis://localhost:6379/3',
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.get('/articles')
@limiter.limit('100/minute')
async def list_articles(request: Request):
    ...


# Dynamic limit by tier
@app.get('/expensive')
@limiter.limit(lambda: '1000/hour' if get_tier() == 'pro' else '100/hour')
async def expensive(request: Request):
    ...
"""


# ==========================================================================
# 9. DJANGO INTEGRATION
# ==========================================================================

"""
# Option 1: django-ratelimit
# pip install django-ratelimit

from django_ratelimit.decorators import ratelimit


@ratelimit(key='user', rate='100/m', block=True)
def my_view(request):
    return JsonResponse({})


# Custom key
@ratelimit(key=lambda req: req.user.tier, rate='1000/m')
def tiered_view(request):
    return JsonResponse({})


# Option 2: DRF custom throttle (already covered in Phase 2)
# from rest_framework.throttling import SimpleRateThrottle


# Option 3: Middleware
class RateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user_id = request.user.id if request.user.is_authenticated else None
        if user_id:
            allowed, _ = token_bucket(f'rl:{user_id}', capacity=100, refill_rate=1)
            if not allowed:
                return JsonResponse({'error': 'rate_limited'}, status=429)
        return self.get_response(request)
"""


# ==========================================================================
# 10. NGINX EDGE RATE LIMITING
# ==========================================================================

NGINX_CONFIG = """
# /etc/nginx/conf.d/rate_limit.conf

# Define zones (10M = ~80k IPs tracked)
limit_req_zone $binary_remote_addr zone=ip_limit:10m rate=100r/s;
limit_req_zone $http_authorization zone=auth_limit:10m rate=1000r/m;

# Different zones for different endpoints
limit_req_zone $binary_remote_addr zone=login_limit:10m rate=5r/m;

# Status code
limit_req_status 429;

# Default log
limit_req_log_level warn;


server {
    # Per-endpoint limits
    location /api/login {
        limit_req zone=login_limit burst=3 nodelay;
        proxy_pass http://backend;
    }

    location /api/ {
        # Use auth header if present, fallback to IP
        limit_req zone=auth_limit burst=20 nodelay;
        limit_req zone=ip_limit burst=200 nodelay;
        proxy_pass http://backend;
    }
}


# Cloudflare-style "Worker" can do more sophisticated logic
"""


# ==========================================================================
# 11. RATE LIMIT BYPASS (whitelist)
# ==========================================================================

WHITELIST_TOKENS = {
    os.environ.get('INTERNAL_API_TOKEN_1', ''),
    os.environ.get('MONITORING_TOKEN', ''),
}


def is_whitelisted(request):
    """Bypass rate limit for internal services."""
    token = request.headers.get('X-Internal-Token', '')
    return token in WHITELIST_TOKENS and token != ''


# ==========================================================================
# 12. RESPONSE HEADER HELPERS
# ==========================================================================

def add_rate_limit_headers(response, limit, remaining, reset_unix):
    """Add standard rate limit headers."""
    response.headers['X-RateLimit-Limit'] = str(limit)
    response.headers['X-RateLimit-Remaining'] = str(int(remaining))
    response.headers['X-RateLimit-Reset'] = str(int(reset_unix))
    return response


def make_429_response(retry_after_seconds=60, violated_dimension=None):
    body = {
        'error': 'rate_limited',
        'detail': f'Rate limit exceeded. Retry in {retry_after_seconds}s.',
    }
    if violated_dimension:
        body['violated'] = violated_dimension

    headers = {
        'Retry-After': str(retry_after_seconds),
        'Content-Type': 'application/json',
    }
    return body, headers


# ==========================================================================
# 13. METRICS
# ==========================================================================

"""
from prometheus_client import Counter, Histogram


RATE_LIMIT_HITS = Counter(
    'rate_limit_hits_total',
    'Rate limit decisions',
    ['decision', 'dimension', 'endpoint'],
)


def track_rate_limit(decision, dimension, endpoint):
    RATE_LIMIT_HITS.labels(decision=decision, dimension=dimension, endpoint=endpoint).inc()


# Alert on:
# - rate_limit_hits{decision="blocked"} > N per hour (abuse pattern)
# - rate_limit_hits{decision="blocked"} == 0 for long time (limits too loose?)
# - Specific user hit > 100 times — investigate (bot?)
"""


# ==========================================================================
# 14. TESTING
# ==========================================================================

"""
import pytest
from unittest.mock import patch


def test_token_bucket_allows_within_limit():
    key = f'test:{uuid.uuid4()}'

    for _ in range(10):
        allowed, _ = token_bucket(key, capacity=10, refill_rate=1)
        assert allowed

    # 11th request — over capacity
    allowed, _ = token_bucket(key, capacity=10, refill_rate=1)
    assert not allowed


def test_token_bucket_refills_over_time():
    key = f'test:{uuid.uuid4()}'

    # Use all tokens
    for _ in range(10):
        token_bucket(key, capacity=10, refill_rate=1)

    # Wait for refill
    time.sleep(2)

    allowed, tokens = token_bucket(key, capacity=10, refill_rate=1)
    assert allowed
    assert tokens >= 1
"""


# ==========================================================================
# 15. DECISION FRAMEWORK
# ==========================================================================

DECISION_GUIDE = """
Algorithm choice:

1. Need burst tolerance + low memory?
   → Token bucket

2. Need exact count (compliance, billing)?
   → Sliding window log

3. Memory-constrained + smooth?
   → Sliding window counter

4. Simplest possible?
   → Fixed window (accept 2x edge artifact)


Layer choice:

1. Global DDoS protection?
   → Edge (Cloudflare, AWS WAF) — cheapest, lowest latency

2. Per-user fine-grained?
   → App layer + Redis (works post-auth)

3. Cross-instance consistency?
   → Centralized Redis (single instance or cluster)

4. Massive scale (>100k RPS)?
   → Edge first + sharded Redis (cluster mode)


Storage choice:

- In-memory (single instance dev only)
- Redis (default for prod)
- DynamoDB / Cosmos (multi-region)
- Hazelcast (Java shops)
"""


# ==========================================================================
# RUNNABLE LAB — In-Memory Token Bucket (Docker-free port of Section 1)
# ==========================================================================
"""
LAB OBJECTIVE: TOKEN_BUCKET_SCRIPT (Section 1, top of file) IS the real
algorithm — Lua running inside Redis. Yeh lab usi refill+cost math ko
plain Python dict me le aata hai, taaki bina Docker/Redis chalaye burst
behavior verify kar sako.

TASK:
  1. TODO: `_bucket_check()` bharo — refill karo, phir cost check karo
     (same math jo TOKEN_BUCKET_SCRIPT me hai, bas Lua ki jagah Python)
  2. Run: python3 07_rate_limiting_deep.py
"""

_buckets: dict[str, dict] = {}


def _bucket_check(key: str, capacity: float, refill_rate: float, cost: float, now: float) -> tuple[bool, float]:
    """In-memory twin of TOKEN_BUCKET_SCRIPT above. Returns (allowed, tokens_remaining)."""
    bucket = _buckets.get(key, {"tokens": capacity, "last_refill": now})
    tokens = bucket["tokens"]
    last_refill = bucket["last_refill"]

    # ─────────────────────────────────────────────────────
    # TODO: refill + decide — same math as TOKEN_BUCKET_SCRIPT (Section 1):
    #   elapsed = now - last_refill
    #   tokens = min(capacity, tokens + elapsed * refill_rate)
    #   if tokens >= cost: tokens -= cost; allowed = True
    #   else: allowed = False
    #
    elapsed = now - last_refill
    tokens = min(capacity, tokens + elapsed * refill_rate)
    if tokens >= cost:
        tokens -= cost
        allowed = True
    else:
        allowed = False
    # ─────────────────────────────────────────────────────

    _buckets[key] = {"tokens": tokens, "last_refill": now}
    return allowed, tokens


def in_memory_token_bucket(key: str, capacity: int = 5, refill_rate: float = 0.0, cost: int = 1) -> tuple[bool, float]:
    return _bucket_check(key, capacity, refill_rate, cost, time.time())


def main() -> None:
    print("\n[setup] capacity=5 tokens, refill_rate=0 (no refill during burst → clean test)")
    key = f"test:{uuid.uuid4().hex[:6]}"

    results = []
    for i in range(8):
        allowed, remaining = in_memory_token_bucket(key, capacity=5, refill_rate=0.0, cost=1)
        results.append(allowed)
        tag = "" if allowed else " → 429"
        print(f"  request {i + 1}: allowed={allowed}, tokens_remaining={remaining:.1f}{tag}")

    allowed_count = sum(results)
    rejected_count = len(results) - allowed_count

    # Reuse the file's own 429 helper (Section 12) for the rejected ones —
    # proves the in-memory check plugs into the same response shape as prod.
    for i, ok in enumerate(results):
        if not ok:
            body, headers = make_429_response(retry_after_seconds=60)
            assert body["error"] == "rate_limited", "make_429_response() shape changed?"

    print("\n" + "─" * 55)
    if results == [True] * 5 + [False] * 3:
        print(f"✅ PASS — exactly 5 requests allowed (capacity), 3 rejected (burst > capacity), "
              "in order")
    else:
        print(f"❌ FAIL — expected [True]*5 + [False]*3, got {results} "
              f"({allowed_count} allowed / {rejected_count} rejected)")
        print("   TODO block bharo _bucket_check() me — refill/cost check missing lagta hai "
              "(placeholder sab kuch allow kar raha hai).")

    print("""
SOCH:
  1. refill_rate=0 rakha isliye ki burst-limit clean test ho — production
     me refill_rate > 0 hota, to eventually saare allow ho jaate. Kyun?
  2. Yeh same Lua script hai jo Section 1 me Redis ke against chalta hai —
     single-instance dev me dict thik hai, par 2 app instances ho to?
     (Hint: isliye centralized Redis chahiye — dict per-instance state hai,
     dusra instance ko iska pata hi nahi chalega)
  3. cost-based check (Section 6) isi bucket function ko reuse karta hai,
     bas cost=100 jaisa bada number deta hai. Iska kya matlab hai practically?
  4. Multi-dimensional check (Section 5) — global + per-endpoint + expensive,
     teeno independent buckets hain. Kaunsa dimension violate hua wo track
     karna kyun zaroori hai (sirf allow/deny se zyada)?
""")


if __name__ == "__main__":
    main()
