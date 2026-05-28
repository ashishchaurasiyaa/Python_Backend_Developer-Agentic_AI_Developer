# Rate Limiting Deep — Algorithms & Distributed Implementation

## Why It Matters (Senior 5 YOE Context)

Rate limiting = essential for any public API:
- **Prevent abuse** → bots, brute force, DDoS
- **Fair usage** → no single user hogs resources
- **Tier enforcement** → free vs paid quota
- **Cost control** → expensive endpoints (LLM, search)

Senior interview: "10K RPS API, prevent abuse + enforce per-user quota — design?" → multi-layer: edge (Cloudflare), nginx, app-level Redis-backed token bucket.

---

## Algorithms

### 1. Token Bucket (most flexible)

```
Bucket capacity: C tokens
Refill rate: R tokens/sec
Each request: consume 1 token (or N for expensive)
Empty bucket → reject (429)
```

**Pros:** Bursts allowed (up to C), smooth long-term rate
**Cons:** Memory per user (track tokens + last_refill)

```python
import time


def token_bucket_check(user_id, capacity=10, refill_rate=0.5, cost=1):
    """Returns (allowed, tokens_remaining)."""
    key = f'rl:tb:{user_id}'
    now = time.time()

    # Lua script for atomic check + update
    script = """
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
    """
    result = redis_client.eval(script, 1, key, capacity, refill_rate, now, cost)
    return bool(result[0]), float(result[1])
```

### 2. Sliding Window Log (precise)

```
Store every request's timestamp in sorted set
Count requests in last W seconds
If count >= limit → reject
```

**Pros:** Exact count, no edge artifacts
**Cons:** Memory O(N) per user (N = requests in window)

```python
def sliding_window_log(user_id, limit=100, window_seconds=60):
    key = f'rl:sw:{user_id}'
    now = time.time()
    cutoff = now - window_seconds

    # Lua atomic check
    script = """
    redis.call('ZREMRANGEBYSCORE', KEYS[1], 0, ARGV[1])
    local count = redis.call('ZCARD', KEYS[1])
    if count >= tonumber(ARGV[2]) then
        return {0, count}
    end
    redis.call('ZADD', KEYS[1], ARGV[3], ARGV[4])
    redis.call('EXPIRE', KEYS[1], ARGV[5])
    return {1, count + 1}
    """
    result = redis_client.eval(
        script, 1, key,
        cutoff, limit, now, f'{now}:{uuid.uuid4()}', window_seconds,
    )
    return bool(result[0]), int(result[1])
```

### 3. Sliding Window Counter (memory-efficient hybrid)

```
Two fixed windows: current + previous
Estimate: count_current + count_previous * (1 - elapsed_in_current / window)
```

**Pros:** O(1) memory, smoother than fixed window
**Cons:** Approximation (slight inaccuracy at window boundary)

```python
def sliding_window_counter(user_id, limit=100, window=60):
    now = int(time.time())
    current_window = now // window
    previous_window = current_window - 1
    elapsed = now % window
    weight = (window - elapsed) / window

    current_key = f'rl:swc:{user_id}:{current_window}'
    previous_key = f'rl:swc:{user_id}:{previous_window}'

    pipe = redis_client.pipeline()
    pipe.incr(current_key)
    pipe.expire(current_key, window * 2)
    pipe.get(previous_key)
    current_count, _, previous_count = pipe.execute()

    previous_count = int(previous_count or 0)
    estimated = previous_count * weight + current_count

    return estimated <= limit, estimated
```

### 4. Fixed Window Counter (simplest)

```
Bucket per minute. Count per bucket.
Bucket key: f'rl:{user}:{now // 60}'
INCR + check < limit
```

**Pros:** O(1) memory, simple
**Cons:** Edge artifact — 2x limit possible at minute boundary

```python
def fixed_window(user_id, limit=100, window=60):
    bucket = int(time.time()) // window
    key = f'rl:fw:{user_id}:{bucket}'
    count = redis_client.incr(key)
    if count == 1:
        redis_client.expire(key, window)
    return count <= limit, count
```

### 5. Leaky Bucket (smooth output)

```
Bucket leaks at constant rate
Requests fill bucket
Overflow → reject
Used for shaping, not just counting
```

Less common in APIs; more for traffic shaping in network gear.

---

## Comparison

| Algorithm | Memory | Precision | Bursts |
|---|---|---|---|
| Token Bucket | O(1) | Exact for tokens | Allowed up to capacity |
| Sliding Log | O(N) | Exact | Allowed |
| Sliding Counter | O(1) | Approximate | Allowed |
| Fixed Window | O(1) | Edge artifact | 2x at boundary |
| Leaky Bucket | O(1) | Exact | Smoothed |

**Production default:** Token Bucket (flexible, predictable).

---

## Distributed Rate Limiting

### Single Redis Instance

```
All app instances → single Redis → atomic Lua scripts
Throughput limited to Redis (100K+ ops/sec OK)
```

### Redis Cluster (sharded by user_id)

```
Hash user_id → shard
Each shard handles fraction of users
Linear scale
```

### Edge Rate Limiting (Cloudflare, AWS WAF)

```
Pre-app filtering at edge → bot blocked before reaching backend
Lower latency, cheaper than app-level
Combines well with app-level fine-grained limits
```

### Multi-Tier

```
Edge: 1000 RPS per IP (broad)
App: 100 RPM per user (fine)
DB: query budget per user
```

Each tier catches different abuse pattern.

---

## Rate Limit Headers (RFC 6585 + draft)

```http
HTTP/1.1 200 OK
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1709125200    # unix timestamp


HTTP/1.1 429 Too Many Requests
Retry-After: 60                  # seconds OR HTTP date
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1709125200

{
    "error": "rate_limited",
    "detail": "Try again in 60 seconds"
}
```

GitHub-style:
```http
X-RateLimit-Limit: 5000
X-RateLimit-Remaining: 4999
X-RateLimit-Reset: 1709125200
X-RateLimit-Used: 1
X-RateLimit-Resource: core
```

---

## Tier-Based Rate Limits

```python
TIER_LIMITS = {
    'free': {'requests': 100, 'window': 3600},          # 100/hr
    'pro': {'requests': 5000, 'window': 3600},          # 5K/hr
    'enterprise': {'requests': 100000, 'window': 3600}, # 100K/hr
}


def check_rate_limit(user):
    tier = user.tier or 'free'
    config = TIER_LIMITS[tier]
    allowed, remaining = token_bucket_check(
        f'{tier}:{user.id}',
        capacity=config['requests'],
        refill_rate=config['requests'] / config['window'],
    )
    return allowed, remaining
```

---

## Burst Allowance

```python
# Token bucket: capacity > refill_rate * window
# E.g., 100 tokens, refill 1/sec → 100 RPS burst, then 1 RPS sustained
```

Useful for:
- Search endpoints (rapid typing)
- Batch operations
- Mobile sync (initial burst)

---

## Multi-Dimensional Rate Limits

Same user can have multiple limits:

```python
def check_all_limits(user, endpoint):
    checks = [
        ('global', f'rl:g:{user.id}', 1000, 3600),         # 1000/hr global
        ('endpoint', f'rl:e:{user.id}:{endpoint}', 100, 60),  # 100/min per endpoint
        ('expensive', f'rl:exp:{user.id}', 10, 3600),       # 10/hr expensive ops
    ]
    for name, key, limit, window in checks:
        allowed, _ = token_bucket_check(key, limit, limit / window)
        if not allowed:
            return False, name
    return True, None
```

---

## Implementation in Frameworks

### FastAPI + slowapi

```python
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded


limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter


@app.get('/articles')
@limiter.limit('100/minute')
async def list_articles(request: Request):
    ...


# Per-user (after auth)
def get_user_id(request):
    return request.state.user_id


limiter = Limiter(key_func=get_user_id)
```

### Django + django-ratelimit

```python
from django_ratelimit.decorators import ratelimit


@ratelimit(key='user', rate='100/m')
def my_view(request):
    if getattr(request, 'limited', False):
        return JsonResponse({'error': 'rate limited'}, status=429)
    return JsonResponse({})
```

### nginx (edge layer)

```nginx
limit_req_zone $binary_remote_addr zone=api:10m rate=100r/s;
limit_req_status 429;

server {
    location /api/ {
        limit_req zone=api burst=20 nodelay;
        proxy_pass http://app;
    }
}
```

---

## Common Pitfalls

### 1. In-Memory State (Single Server)

```python
counters = {}   # in-memory dict
```

Doesn't scale beyond 1 server. Use Redis.

### 2. Race Conditions Without Atomicity

```python
count = r.get(key)
if int(count or 0) < limit:
    r.incr(key)   # race!
```

Use Lua scripts or `INCR + check after`.

### 3. No Differentiation by Endpoint

Same limit for `/health` and `/expensive-search`. Differentiate by cost.

### 4. IP-Only Limiting

Doesn't work for authenticated APIs (one office IP = many users). Use user_id post-auth.

### 5. No Burst Allowance

Strict 1 RPS limit kills legitimate users (autocomplete, search). Allow bursts via token bucket.

### 6. No 429 Response Headers

Client doesn't know retry timing. Always include `Retry-After`.

### 7. Banning by IP Permanently

Shared IPs (corporate, mobile NAT) → block innocent users. Use temporary blocks + verify.

### 8. Edge + App Limits Not Coordinated

App expects 1000/sec but edge passes 5000/sec. Cascading failure. Define limits at each layer.

---

## Interview Q&A

**Q1:** Token bucket vs sliding window — kab kya?
**A:** Token bucket: bursts allowed (good UX for legitimate spikes), low memory, simple. Sliding window log: exact, but O(N) memory per user. Sliding counter: O(1), approximate, smooth. Default: token bucket. For strict precision (financial): sliding log.

**Q2:** Distributed rate limit kaise implement?
**A:** Redis-backed Lua scripts for atomicity. Single Redis or Cluster (sharded by user_id). All app instances → same Redis → consistent counter. Lua = atomic check + decrement. For massive scale: edge layer (Cloudflare) + app layer (Redis).

**Q3:** Multi-tier rate limit?
**A:** Different limits per dimension: global (1000/hr per user), per-endpoint (100/min for expensive), tier-based (free vs paid). All checks run sequentially; any fails → 429. Compose via list of (name, key, limit, window).

**Q4:** 429 response best practices?
**A:** Always include `Retry-After` (seconds). Plus `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`. Standard error body. Document in API docs. Optionally: cost per endpoint header for clients to budget.

**Q5:** Bot detection vs rate limit?
**A:** Different concerns. Rate limit = abuse prevention via quotas. Bot detection = behavioral (CAPTCHA, honeypot, browser fingerprint). Combine: rate limit catches simple abuse; bot detection catches sophisticated. Edge WAFs (Cloudflare) handle both.

**Q6:** Whitelisting / bypass?
**A:** Internal services, admin tools, monitoring need bypass. Pattern: `if user.is_internal: skip_rate_limit()`. But still log + monitor — internal abuse possible. Or higher tier limits rather than bypass.

**Q7:** Cost-based rate limiting?
**A:** Some endpoints expensive (LLM = $0.10 each). Charge tokens based on cost: cheap endpoint = 1 token, expensive = 100 tokens. User has total budget (e.g., 1000 tokens/hour). Allows mixed usage; prevents expensive abuse.

**Q8:** Rate limit failover?
**A:** Redis down → fail open (allow) or fail closed (deny). Fail open: keeps service running, opens to abuse. Fail closed: safer, but minor outage = service unusable. Best: fail open + alert (treat as known-bad incident).

---

## Real-World Use Cases

### 1. Public API (GitHub-style)

```python
@app.middleware('http')
async def rate_limit_middleware(request, call_next):
    user = await authenticate(request)
    if user:
        allowed, remaining, reset = check_user_limit(user, request.url.path)
    else:
        allowed, remaining, reset = check_ip_limit(request.client.host)

    if not allowed:
        return JSONResponse(
            {'error': 'rate_limited'},
            status_code=429,
            headers={
                'Retry-After': str(int(reset - time.time())),
                'X-RateLimit-Limit': str(limit),
                'X-RateLimit-Remaining': '0',
                'X-RateLimit-Reset': str(reset),
            },
        )

    response = await call_next(request)
    response.headers['X-RateLimit-Limit'] = str(limit)
    response.headers['X-RateLimit-Remaining'] = str(remaining)
    response.headers['X-RateLimit-Reset'] = str(reset)
    return response
```

### 2. LLM API (cost-based)

```python
ENDPOINT_COSTS = {
    '/chat/completions': 100,
    '/embeddings': 10,
    '/moderation': 1,
}


def check_llm_quota(user, endpoint):
    cost = ENDPOINT_COSTS.get(endpoint, 1)
    return token_bucket_check(
        f'llm:{user.id}',
        capacity=user.daily_token_budget,
        refill_rate=user.daily_token_budget / 86400,
        cost=cost,
    )
```

### 3. Mobile App (sync allowance)

```python
# Allow burst of 100 on mobile sync, then sustained 10/min
token_bucket_check(
    f'mobile:{user.id}',
    capacity=100,
    refill_rate=10/60,   # 10 per minute
)
```

---

## References

- [Cloudflare blog: rate limiting algorithms](https://blog.cloudflare.com/counting-things-a-lot-of-different-things/)
- [Stripe API rate limits](https://stripe.com/docs/rate-limits)
- [draft-ietf-httpapi-ratelimit-headers](https://datatracker.ietf.org/doc/draft-ietf-httpapi-ratelimit-headers/)
- [slowapi for FastAPI](https://github.com/laurents/slowapi)
- [django-ratelimit](https://django-ratelimit.readthedocs.io/)
