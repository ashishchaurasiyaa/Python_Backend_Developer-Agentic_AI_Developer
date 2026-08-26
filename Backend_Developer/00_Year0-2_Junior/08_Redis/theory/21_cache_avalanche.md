# Cache Avalanche — Redis

## 1. What is Cache Avalanche?

**Cache avalanche** occurs when a large number of cache keys expire at the same time (or the entire cache restarts), causing a massive flood of requests to hit the database simultaneously.

```
Normal state:
Request → Redis HIT → fast response (1ms)

Avalanche trigger (mass expiry):
                    ┌── Request 1 → Redis MISS → DB
                    ├── Request 2 → Redis MISS → DB
10,000 req/s ───────├── Request 3 → Redis MISS → DB
                    ├── ...
                    └── Request 10,000 → Redis MISS → DB
                         DB: 10,000 concurrent queries → OVERLOAD → timeouts
```

**Difference from Cache Stampede:**

| | Cache Stampede | Cache Avalanche |
|--|----------------|-----------------|
| Trigger | ONE popular key expires | MANY keys expire simultaneously |
| Scale | One key, many requests | Many keys, many requests |
| Fix | Single lock / request coalescing | TTL jitter + staggered expiry |

---

## 2. Common Triggers

### Trigger 1: Same TTL for all keys set at once

```python
# ❌ WRONG: batch import — all 10,000 keys get TTL=3600
# All expire at exactly the same time 1 hour later
pipe = r.pipeline()
for product in products:
    pipe.setex(f"product:{product.id}", 3600, json.dumps(product))  # same TTL!
pipe.execute()
```

### Trigger 2: Redis restart / memory flush

```bash
redis-cli FLUSHALL   # wipes everything — next second: full DB load
# or: Redis OOM → evicts many keys → partial avalanche
```

### Trigger 3: Scheduled batch invalidation

```python
# ❌ WRONG: invalidate all product cache at midnight
def midnight_cache_clear():
    keys = r.scan_iter("product:*")
    r.delete(*keys)   # all expire simultaneously
```

---

## 3. Solutions

### Solution 1: TTL Jitter (Most Important Fix)

Add random variation to TTL so keys expire at different times.

```python
import random

BASE_TTL = 3600  # 1 hour

def set_with_jitter(r, key: str, value: str, base_ttl: int = BASE_TTL):
    """
    Add ±10% random jitter to TTL.
    1000 keys set at once → expire spread over 360 seconds, not all at once.
    """
    jitter = random.randint(-base_ttl // 10, base_ttl // 10)  # ±10%
    ttl = base_ttl + jitter
    r.setex(key, ttl, value)

# Batch import — spread expiry over ±360 seconds
pipe = r.pipeline()
for product in products:
    jitter = random.randint(0, 600)  # 0–10 min extra spread
    pipe.setex(f"product:{product.id}", 3600 + jitter, json.dumps(product))
pipe.execute()
```

### Solution 2: Staggered Cache Warming

Don't set all keys with the same TTL. Use tiered TTLs.

```python
def warm_cache_staggered(products: list):
    """
    Tier products by popularity — popular ones get longer TTL + refreshed more often.
    """
    for i, product in enumerate(products):
        # Spread TTL: first 1000 products → 1h, next 1000 → 1.5h, etc.
        tier_extra = (i // 1000) * 1800   # extra 30min per tier
        ttl = 3600 + tier_extra + random.randint(0, 300)
        r.setex(f"product:{product.id}", ttl, json.dumps(product))
```

### Solution 3: Background Refresh (Avoid Expiry Entirely)

Refresh keys BEFORE they expire — never let them go cold.

```python
import asyncio

REFRESH_THRESHOLD = 0.2  # refresh when < 20% TTL remaining

async def get_with_background_refresh(r, key: str, fetch_fn, ttl: int):
    value = r.get(key)
    remaining = r.ttl(key)

    if value and remaining > 0:
        # Proactively refresh if close to expiry
        if remaining < ttl * REFRESH_THRESHOLD:
            asyncio.create_task(_refresh_in_background(r, key, fetch_fn, ttl))
        return json.loads(value)

    # Cache miss — fetch synchronously
    data = await fetch_fn()
    r.setex(key, ttl + random.randint(0, 300), json.dumps(data))
    return data

async def _refresh_in_background(r, key, fetch_fn, ttl):
    """Refresh without blocking the current request."""
    try:
        data = await fetch_fn()
        r.setex(key, ttl + random.randint(0, 300), json.dumps(data))
    except Exception:
        pass  # keep stale data if refresh fails
```

### Solution 4: Multi-Level Cache (Circuit Breaker)

If Redis goes fully cold, a secondary in-memory cache absorbs the spike.

```python
from cachetools import TTLCache

L1 = TTLCache(maxsize=5000, ttl=60)   # 60-second local cache

def get_product(product_id: int):
    key = f"product:{product_id}"

    # L1: local cache (survives Redis restart)
    if key in L1:
        return L1[key]

    # L2: Redis
    data = r.get(key)
    if data:
        result = json.loads(data)
        L1[key] = result
        return result

    # L3: DB
    result = db.get_product(product_id)
    jittered_ttl = 3600 + random.randint(0, 600)
    r.setex(key, jittered_ttl, json.dumps(result))
    L1[key] = result
    return result
```

### Solution 5: Circuit Breaker for DB Protection

If DB is overwhelmed, fail fast rather than queuing thousands of requests.

```python
import time

class CircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=30):
        self.failures = 0
        self.threshold = failure_threshold
        self.timeout = timeout
        self.last_failure_time = 0
        self.state = "CLOSED"  # CLOSED=normal, OPEN=failing fast

    def call(self, fn):
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "HALF_OPEN"
            else:
                raise Exception("Circuit breaker OPEN — DB protected")
        try:
            result = fn()
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failures = 0
            return result
        except Exception:
            self.failures += 1
            self.last_failure_time = time.time()
            if self.failures >= self.threshold:
                self.state = "OPEN"
            raise

db_circuit = CircuitBreaker(failure_threshold=5, timeout=30)
```

---

## 4. Prevention Checklist

```
□ Never use the same fixed TTL for batch-imported keys
□ Add random jitter (±10-20%) to all cache TTLs
□ Use background refresh for critical high-traffic keys
□ Multi-level cache (local + Redis) for avalanche resilience
□ Circuit breaker on DB queries to prevent cascade failure
□ Redis restart procedure: warm cache before re-enabling traffic
□ Avoid FLUSHALL in production (use targeted key deletion)
□ Monitor cache hit ratio — sudden drop = avalanche signal
```

---

## 5. Avalanche vs Stampede vs Penetration — Quick Reference

| Problem | Trigger | Scale | Primary Fix |
|---------|---------|-------|-------------|
| **Stampede** | 1 popular key expires | 1 key, N req | Lock / request coalescing |
| **Avalanche** | Many keys expire at once | M keys, N req | TTL jitter + staggered warm |
| **Penetration** | Requests for non-existent keys | Any scale | Negative caching + Bloom filter |

---

## 6. Interview Questions

**Q: Cache avalanche kya hai? Stampede se kaise alag hai?**
Avalanche mein bahut saare keys ek saath expire hote hain — DB pe massive load. Stampede mein ek popular key expire hoti hai — thundering herd us ek key ke liye. Fix bhi alag: avalanche → TTL jitter; stampede → lock.

**Q: TTL jitter kya hai? Kaise implement karo?**
Random variation add karo TTL mein: `ttl = base_ttl + random.randint(-base//10, base//10)`. 1000 keys jo saath set huin, ab spread hoke expire hongi — DB pe gradual load.

**Q: Redis restart ke baad avalanche kaise rokein?**
Cache warming: Redis restart ke baad aur traffic re-enable karne se pehle critical keys populate karo. Multi-level cache (local in-process) se Redis restart survive hota hai.

**Q: Background refresh strategy kya hai?**
Key expire hone se pehle — jab TTL 20% reh jaaye — background task mein refresh karo. User ko fresh data milta hai, cache kabhi cold nahi hota.
