# Cache Stampede + Cold Start

> **Interview angle:** "Popular product ka cache expire ho gaya — 1000 requests simultaneously DB hit kar rahi. DB crash hone wala. Kya karoge?"

---

## 1. The Problem: Cache Stampede (Thundering Herd)

```
Time 0: Cache HIT for "homepage_html" (200ms saved)
        ...
Time T: Cache EXPIRES
        At exactly T+1ms: 1000 concurrent requests arrive
        All check cache → MISS
        All hit database simultaneously
        Database load spikes 1000x → CRASH
```

This is the **thundering herd problem**. Common with:
- Hot keys (homepage, top products)
- Time-aligned TTLs (everyone expires at 00:00:00)
- High-traffic events (Black Friday, viral content)

---

## 2. Cold Start Variant

Fresh server, empty cache:
- Day 1 deploy: cache empty
- All requests miss → all hit DB
- DB overwhelmed before cache fills

Similar root cause: **multiple workers do the same expensive work**.

---

## 3. Solution 1: Locking (Single Flight)

Only ONE process recomputes; others wait for result.

```python
async def get_or_compute(key):
    value = await cache.get(key)
    if value is not None:
        return value

    # Cache miss — try to acquire lock
    lock_key = f"lock:{key}"
    if await redis.set(lock_key, "1", nx=True, ex=10):
        try:
            # We have the lock — compute
            value = await expensive_db_query(key)
            await cache.set(key, value, ttl=300)
            return value
        finally:
            await redis.delete(lock_key)
    else:
        # Wait briefly + retry
        await asyncio.sleep(0.05)
        value = await cache.get(key)
        if value is not None:
            return value
        # Lock holder still computing — return stale or default
        return await expensive_db_query(key)   # fallback (rare path)
```

**Trade-off:** Adds latency (waiting). One lock per key.

---

## 4. Solution 2: Probabilistic Early Expiration (XFetch)

Each request **probabilistically refreshes** the cache BEFORE expiry. Probability increases as expiry approaches.

```python
import random
import math
import time

# Beta = how aggressively to recompute early (typically 1.0)
BETA = 1.0

async def xfetch(key, ttl_seconds, recompute_fn):
    cached = await cache.get_with_metadata(key)
    if cached is None:
        # First access — compute
        value, delta = await time_recompute(recompute_fn)
        await cache.set(key, {"value": value, "delta": delta}, ttl=ttl_seconds)
        return value

    value = cached["value"]
    delta = cached["delta"]    # how long recompute took last time
    expiry = cached["expiry"]
    now = time.time()

    # Probabilistically recompute before expiry
    if now + delta * BETA * math.log(random.random()) >= expiry:
        # Recompute early
        new_value, new_delta = await time_recompute(recompute_fn)
        await cache.set(key, {"value": new_value, "delta": new_delta}, ttl=ttl_seconds)
        return new_value

    return value
```

**Genius:** Probability so designed that:
- Early in TTL: ~0% chance of recompute
- Near expiry: high chance ONE request recomputes
- No coordination needed across processes
- No locks

Algorithm by Vattani et al. (paper: "Optimal Probabilistic Cache Stampede Prevention").

---

## 5. Solution 3: Stale-While-Revalidate (SWR)

Return stale value immediately, refresh in background.

```python
async def swr(key, ttl_seconds, stale_seconds, recompute_fn):
    cached = await cache.get_with_metadata(key)

    if cached is None:
        # Cold start — must compute
        return await compute_and_cache(key, recompute_fn, ttl_seconds)

    age = time.time() - cached["created_at"]

    if age < ttl_seconds:
        return cached["value"]    # fresh

    if age < ttl_seconds + stale_seconds:
        # Return stale, refresh in background
        asyncio.create_task(refresh_in_background(key, recompute_fn, ttl_seconds))
        return cached["value"]

    # Too stale — must recompute synchronously
    return await compute_and_cache(key, recompute_fn, ttl_seconds)
```

Used by:
- CDNs (Cloudflare's `stale-while-revalidate` directive)
- HTTP cache headers: `Cache-Control: max-age=60, stale-while-revalidate=300`
- Vercel/Next.js ISR (Incremental Static Regeneration)

**Trade-off:** Returns slightly outdated data. Acceptable for read-heavy systems.

---

## 6. Solution 4: TTL Jitter

Add randomness to TTL → spread expirations.

```python
import random

base_ttl = 300
jitter = random.uniform(-30, 30)    # ±10%
await cache.set(key, value, ttl=base_ttl + jitter)
```

**Without jitter:** All keys set at 12:00:00 expire at 12:05:00 → simultaneous miss.
**With jitter:** Expire across 12:04:30 - 12:05:30 → spread load.

Simple, cheap, effective.

---

## 7. Solution 5: Cache Warming on Startup

Don't wait for first request — preload cache at boot.

```python
@app.on_event("startup")
async def warm_cache():
    popular_keys = await get_top_100_keys()
    await asyncio.gather(*[
        load_to_cache(k) for k in popular_keys
    ])
```

See `08_cache_warming_strategies.md` for details.

---

## 8. Solution 6: Request Coalescing

In-process: multiple concurrent requests for same key → coalesce into one DB call.

```python
import asyncio

class RequestCoalescer:
    def __init__(self):
        self._pending: dict[str, asyncio.Future] = {}
        self._lock = asyncio.Lock()

    async def get(self, key, fetch_fn):
        async with self._lock:
            if key in self._pending:
                # Already fetching — wait for it
                future = self._pending[key]
                # Release the lock before awaiting
            else:
                future = asyncio.Future()
                self._pending[key] = future
                asyncio.create_task(self._fetch(key, fetch_fn, future))

        return await future

    async def _fetch(self, key, fetch_fn, future):
        try:
            result = await fetch_fn(key)
            future.set_result(result)
        except Exception as e:
            future.set_exception(e)
        finally:
            self._pending.pop(key, None)
```

**Used by:** Go's `singleflight`, Node.js `dataloader`.

---

## 9. Combining Solutions (Production Best Practice)

```python
async def production_get(key):
    # Layer 1: Request coalescing (in-process)
    return await coalescer.get(key, lambda k: _layer2(k))

async def _layer2(key):
    # Layer 2: SWR with probabilistic refresh
    return await xfetch_swr(key, ...)

async def _layer3(key):
    # Layer 3: Distributed lock fallback
    return await locked_recompute(key, ...)
```

---

## 10. Database-Level Mitigations

### Connection pool limits
```python
engine = create_async_engine(url, pool_size=20, max_overflow=10)
# Even if cache stampedes, only 30 DB connections max
```

### Statement timeout
```sql
SET statement_timeout = '5s';
-- Kill slow queries before they cascade
```

### PgBouncer rate limiting
```ini
max_db_connections = 50    # absolute cap
```

---

## 11. Monitoring Cache Stampede

### Metrics
- **Cache miss rate** → spike = potential stampede
- **DB query rate** → 10x normal = stampede happening
- **Lock contention** (Redis `OBJECT IDLETIME`)
- **`COMPUTE`/`get_or_compute` latency p99**

### Alerts
- Cache miss rate > 5x baseline for 30s
- DB CPU > 80%
- Request queue depth growing

---

## 12. Pitfalls

### Pitfall 1: Lock timeout too short
Recompute takes 10s, lock TTL=5s → another worker starts. **Set TTL > expected work + buffer.**

### Pitfall 2: Lock held during cache write
Lock released while still computing → next request starts second copy.
**Always:** acquire lock → compute → write cache → release lock.

### Pitfall 3: No fallback on stampede
If lock contention high, requests timeout → 500s.
**Have:** stale-data fallback, default values, graceful degradation.

### Pitfall 4: Probabilistic params wrong
β too small = stampede still happens. β too big = constant recompute (wasteful).
**Tune:** measure recompute cost vs miss cost.

### Pitfall 5: TTL aligned across keys
Don't use `expire_at = midnight`. All keys expire together = mass stampede.

---

## 13. Interview Questions

**Q1: Cache stampede kya hai?**
Hot key expires → many concurrent requests miss → all hit DB → DB overwhelmed.

**Q2: Solutions?**
- Lock + single-flight
- Probabilistic early expiration (XFetch)
- Stale-while-revalidate
- TTL jitter
- Cache warming
- Request coalescing in-app

**Q3: SWR kab use karte?**
Read-heavy, slight staleness OK. Return cached, refresh in background. CDNs, ISR (Next.js).

**Q4: Lock pattern problem?**
Adds latency, single point of contention. Workers wait. Probabilistic refresh avoids this.

**Q5: TTL jitter kyu?**
Spread expirations across time. Without it, time-aligned TTLs cause synchronized misses.

**Q6: Cold start vs stampede?**
Stampede = hot key expires. Cold start = fresh deployment, cache empty. Both = same fix.

**Q7: Probabilistic refresh kaise kaam karta?**
Each request has tiny probability of refreshing pre-expiry. Probability grows as expiry approaches. Statistically, one will refresh before mass miss.

---

## 14. Best Practices

1. **TTL jitter always** — cheapest win
2. **SWR for read-heavy** — best user experience
3. **Locks as fallback** — when SWR not feasible
4. **Probabilistic refresh** for very hot keys
5. **Cache warming on deploy** — avoid cold start
6. **Request coalescing in-app** — handles burst
7. **DB connection pool limits** — defense in depth
8. **Monitor miss rate** — detect early
9. **Stale data acceptable** for many use cases
10. **Test stampede in load tests** — simulate cache flush

---

## Related
- [[02_redlock_distributed_locks]]
- [[08_cache_warming_strategies]]
- [[09_negative_caching]]
- [[07_multi_level_caching]]
