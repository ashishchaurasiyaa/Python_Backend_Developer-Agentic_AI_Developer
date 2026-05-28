# Multi-Level Caching (L1 + L2 + L3)

> **Interview angle:** "Redis network round-trip ~1ms. Page load needs 50 lookups. Can we do faster?"

---

## 1. Why Multiple Levels?

| Layer | Latency | Capacity | Shared |
|---|---|---|---|
| **L1: In-process** (dict/LRU) | ~100ns | 100MB | ❌ per-pod |
| **L2: Redis** | ~1ms (network) | 10GB | ✅ all pods |
| **L3: Database** | ~10-100ms | TB | ✅ |

**10000x latency difference** between L1 and L3. Multi-level = best of all.

---

## 2. Architecture

```
Request → L1 (process memory) ─── miss ──→ L2 (Redis) ─── miss ──→ L3 (DB)
   ↑                                  ↑                          │
   └── populate ◄──────────────────────┴── populate ◄─────────────┘
```

### Pattern: cache-aside
1. Try L1 → hit? return
2. Try L2 → hit? populate L1, return
3. Query L3 (DB) → populate L2 + L1, return

---

## 3. Code Sketch

```python
class MultiLevelCache:
    def __init__(self, l1_size=1000, l2_redis=None, l3_db=None):
        self.l1 = LRUCache(l1_size)        # in-process
        self.l2 = l2_redis                  # shared Redis
        self.l3_db = l3_db

    async def get(self, key):
        # L1
        if (value := self.l1.get(key)) is not None:
            self.metrics.inc("l1_hit")
            return value

        # L2
        value = await self.l2.get(key)
        if value is not None:
            self.metrics.inc("l2_hit")
            self.l1.put(key, value)
            return value

        # L3
        self.metrics.inc("l3_hit")    # actually miss but final source
        value = await self.l3_db.fetch(key)
        if value is not None:
            await self.l2.set(key, value, ttl=300)
            self.l1.put(key, value)
        return value

    async def invalidate(self, key):
        self.l1.delete(key)
        await self.l2.delete(key)
        # Also notify other pods to evict from their L1!
```

---

## 4. The Big Problem: L1 Consistency Across Pods

L2 (Redis) is shared. L1 is **per-pod**.

If pod A updates key X:
- A's L1 updated
- A's L2 (Redis) updated
- **B's L1 still has stale value!**

User hits pod B → sees old value. **Bug.**

---

## 5. Invalidation Strategies for L1

### Strategy 1: Short TTL on L1 (cheap, accepts staleness)
```python
self.l1 = TTLCache(max_size=1000, ttl=60)   # 60s freshness
```
- Simple
- Eventual consistency (staleness window = L1 TTL)
- Best for read-heavy, rarely-updated data

### Strategy 2: Pub/Sub invalidation
Pod updates key → publish "invalidate X" → all pods listen → evict from L1.

```python
async def invalidate(self, key):
    self.l1.delete(key)
    await self.l2.delete(key)
    await self.l2.publish("cache_invalidate", key)

async def listen_for_invalidations(self):
    pubsub = await self.l2.pubsub()
    await pubsub.subscribe("cache_invalidate")
    async for message in pubsub.listen():
        if message["type"] == "message":
            self.l1.delete(message["data"])
```

- Strong consistency (with some lag)
- Pub/Sub failure → divergence
- Network overhead

### Strategy 3: Versioning
Store version with value. Compare versions before serving from L1.

```python
# Set in L2 with version
await l2.hset(key, {"value": "...", "version": 5})

# L1 stores (value, version)
# On L1 hit, check L2 version (1 lightweight call)
async def get(self, key):
    l1_entry = self.l1.get(key)
    if l1_entry:
        l2_version = await self.l2.hget(key, "version")
        if l2_version == l1_entry["version"]:
            return l1_entry["value"]
        # version stale → fetch fresh
```

- Strong consistency
- Adds 1 Redis call per L1 hit (defeats purpose)
- Useful only if versions cached separately

### Strategy 4: TTL + accept eventual consistency
**Most common in production.** 30-60s L1 TTL = simple, fast, OK for most data.

---

## 6. When NOT to use L1

❌ **Critical writes:** balance, inventory. Stale L1 = bugs.
❌ **Per-user personalized data:** unlikely to repeat hits.
❌ **Large objects:** L1 memory bloat per pod.
❌ **High write rate:** invalidation overhead exceeds gains.

✅ **Use L1 for:**
- Reference data (countries, configs)
- Hot read-mostly data (top products)
- Computed results (rendered HTML fragments)
- Auth tokens (with short TTL)

---

## 7. CDN as L0 (in front of L1)

For HTTP responses:
```
Browser → CDN (CloudFlare) → App Server (L1 + L2 + L3)
```

- L0 (CDN edge): ~50ms (geographic)
- L1: ~100ns
- L2: ~1ms
- L3: ~10ms

CDN caches static + dynamic responses with `Cache-Control` headers.

```python
@app.get("/articles/{id}")
async def get_article(id: int):
    response = await fetch(id)
    return JSONResponse(
        response,
        headers={
            "Cache-Control": "public, max-age=300, stale-while-revalidate=60",
        }
    )
```

---

## 8. Read-Through vs Write-Through

### Read-Through (cache-aside)
App reads from cache → on miss, app fetches DB → app populates cache.

### Write-Through
App writes to cache → cache writes to DB synchronously.

### Write-Behind (write-back)
App writes to cache → cache writes to DB asynchronously.
Fast but risky (data loss on cache crash).

### Refresh-Ahead
Periodically refresh hot keys before expiry.

**Multi-level usually: cache-aside (Read-Through).**

---

## 9. Real Implementation (Python)

```python
from cachetools import TTLCache
import redis.asyncio as redis

class MultiLevelCache:
    def __init__(self, l1_max=10000, l1_ttl=60, l2_url="redis://localhost"):
        self.l1 = TTLCache(maxsize=l1_max, ttl=l1_ttl)
        self.l2 = redis.from_url(l2_url, decode_responses=True)
        self._pubsub_task = None

    async def start(self):
        # Listen for invalidations from other pods
        self._pubsub_task = asyncio.create_task(self._listen())

    async def _listen(self):
        pubsub = self.l2.pubsub()
        await pubsub.subscribe("cache_invalidate")
        async for msg in pubsub.listen():
            if msg["type"] == "message":
                key = msg["data"]
                self.l1.pop(key, None)

    async def get(self, key, fetch_fn=None, ttl=300):
        # L1
        try:
            return self.l1[key]
        except KeyError:
            pass

        # L2
        value = await self.l2.get(key)
        if value is not None:
            self.l1[key] = value
            return value

        # L3
        if fetch_fn is None:
            return None
        value = await fetch_fn(key)
        if value is not None:
            await self.l2.setex(key, ttl, value)
            self.l1[key] = value
        return value

    async def invalidate(self, key):
        self.l1.pop(key, None)
        await self.l2.delete(key)
        await self.l2.publish("cache_invalidate", key)
```

---

## 10. Metrics to Monitor

| Metric | Purpose |
|---|---|
| L1 hit rate | Goal: > 70% for hot data |
| L2 hit rate | Goal: > 90% overall |
| Combined hit rate | Goal: > 95% |
| L1 miss → L2 hit | Validates L1 isn't too small |
| L2 miss → L3 hit | Detect cache evictions |
| L1 memory used | Tune capacity |
| Pub/Sub lag | Invalidation freshness |
| Stale reads count | If versioning used |

---

## 11. Tiered Storage Pattern (cost optimization)

```
L1: in-process (free)
L2: Redis (paid memory)
L3: PostgreSQL (cheaper storage)
L4: S3 / cold storage (cheapest)
```

For analytics: hot recent data in L1/L2, older in L3, archives in L4. Promote/demote as access patterns shift.

---

## 12. Common Pitfalls

### Pitfall 1: L1 too large
Each pod has its own L1. 100 pods × 1GB L1 = 100GB total memory across cluster!

### Pitfall 2: No invalidation strategy
L1 stale → users see old data → support tickets.

### Pitfall 3: Storing big objects in L1
Pod memory bloat. Limit value size.

### Pitfall 4: Cache used for source of truth
L1 evicted → data lost. Cache = optimization, not storage.

### Pitfall 5: Network calls inside cache lookup
```python
# ❌ awaits even on L1 hit
async def get(self, key):
    await some_metric_call()        # blocks fast path
    if key in self.l1: ...
```

---

## 13. Interview Questions

**Q1: L1 + L2 architecture kya hai?**
L1 in-process (per pod, fastest). L2 shared (Redis). L3 DB. Read order: L1 → L2 → L3.

**Q2: L1 stale problem?**
Pod A updates → A's L1 + L2 fresh. Pod B's L1 stale. Solutions: short TTL, Pub/Sub invalidation, versioning.

**Q3: Cost of multi-level?**
L1 memory per pod × N pods. Pub/Sub overhead. Code complexity. Pays off when L2 latency matters.

**Q4: CDN as L0?**
Yes. CloudFlare/Cloudfront edge cache before app. ~50ms latency reduction for far users.

**Q5: Write-through vs cache-aside?**
Cache-aside (Read-Through): app reads cache, populates on miss. Write-through: writes go through cache to DB. Multi-level usually cache-aside.

**Q6: L1 size kaise tune?**
Watch L1 hit rate. < 70% = increase. > 95% = decrease (waste). Trade-off with per-pod memory.

**Q7: Cache stampede in multi-level?**
L1 expires for many keys → all hit L2. L2 doesn't stampede (shared). But L1 misses spike.

---

## 14. Best Practices

1. **L1 TTL short** (30-60s) — limits staleness
2. **Pub/Sub invalidate** for strong consistency
3. **L1 capacity small** — only hot data
4. **L2 capacity larger** — broader coverage
5. **Monitor hit rates per layer**
6. **Don't L1 cache personalized data**
7. **CDN for HTTP responses** (L0)
8. **TTL jitter** at every layer
9. **Don't store huge objects in L1**
10. **Versioning** for critical consistency

---

## Related
- [[01_caching_patterns]]
- [[03_cache_stampede_cold_start]]
- [[04_memory_eviction_policies]]
- [[../../00_Year0-2_Junior/08_Redis/theory/01_basics_installation_cli]]
