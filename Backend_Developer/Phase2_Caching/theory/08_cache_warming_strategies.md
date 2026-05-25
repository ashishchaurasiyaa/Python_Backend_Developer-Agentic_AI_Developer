# Cache Warming Strategies

> **Interview angle:** "New deploy → empty cache → first 1000 requests hit DB → 503. Kya karoge?"

---

## 1. The Cold Start Problem

Fresh app deployment:
- All caches empty (L1 process, L2 Redis)
- First requests = cache misses
- All hit DB simultaneously
- DB overwhelmed → cascading failure

Same applies to:
- Cache cluster restart
- Cache eviction during low-traffic period
- Scaling out (new pods)

**Solution: Pre-populate cache before traffic arrives = cache warming.**

---

## 2. Warming Strategies

### Strategy 1: Eager (deploy-time)
Load known-hot keys at app startup.

```python
@app.on_event("startup")
async def warm_cache():
    hot_keys = await db.get_top_1000_keys()
    await asyncio.gather(*[load_to_cache(k) for k in hot_keys])
```

**Pros:** First request fast.
**Cons:** Slow startup. Hardcoded "top" list may be wrong.

### Strategy 2: Background warmer (continuous)
Worker continuously refreshes hot keys.

```python
async def background_warmer():
    while True:
        hot_keys = await analytics.top_keys(window="last_1h")
        for key in hot_keys:
            if not await cache.exists(key):
                await fetch_and_cache(key)
        await asyncio.sleep(60)
```

### Strategy 3: Lazy + accept first-miss
Don't warm. Accept first request hits DB. Rely on rate limiting / circuit breakers to protect DB.

**Simplest. Works for most cases.**

### Strategy 4: Replay traffic
Mirror production traffic to new instance pre-launch.

```bash
# AWS Application Load Balancer mirror target
# Sends % of traffic to "warming" target group
```

### Strategy 5: Snapshot + restore
Take cache snapshot before deploy → restore on new instances.

Redis: `BGSAVE` → dump.rdb → load on startup.

### Strategy 6: Sticky / progressive rollout
Don't replace ALL instances at once. Rotate slowly → existing cache helps new instances.

---

## 3. What to Warm?

### Sources of "hot keys" list
1. **Analytics:** top accessed keys (last hour/day)
2. **Predictive:** based on time of day, day of week
3. **Static configuration:** known content (homepage, top products)
4. **User behavior:** logged-in users' recent activity

```python
# Real example: warm homepage + top 100 products
async def production_warmer():
    await load_to_cache("homepage_html")
    products = await db.query("SELECT id FROM products ORDER BY views DESC LIMIT 100")
    for p in products:
        await load_to_cache(f"product:{p.id}")
```

---

## 4. Warming with Distributed Lock

Multiple pods starting simultaneously → all try to warm same keys → DB overload.

```python
async def warm_safely():
    if await redis.set("warming_lock", "1", nx=True, ex=600):
        try:
            await do_warming()
        finally:
            await redis.delete("warming_lock")
    else:
        # Another pod is warming — wait briefly
        await asyncio.sleep(10)
```

---

## 5. Progressive Warming (avoid DB burst)

Don't warm all 10K keys instantly — rate-limit yourself.

```python
async def progressive_warm(keys, batch_size=10, delay=0.1):
    for i in range(0, len(keys), batch_size):
        batch = keys[i:i+batch_size]
        await asyncio.gather(*[fetch_and_cache(k) for k in batch])
        await asyncio.sleep(delay)
```

Or use semaphore:
```python
semaphore = asyncio.Semaphore(5)

async def fetch_with_limit(key):
    async with semaphore:
        return await fetch_and_cache(key)

await asyncio.gather(*[fetch_with_limit(k) for k in keys])
```

---

## 6. Refresh-Ahead (predictive)

Refresh keys BEFORE expiry — prevent cold reads.

```python
async def refresh_ahead(key, ttl=300, refresh_at_fraction=0.8):
    cached = await cache.get_with_metadata(key)
    if not cached:
        return None

    age = time.time() - cached["created_at"]
    if age > ttl * refresh_at_fraction:
        # 80% through TTL — refresh in background
        asyncio.create_task(refresh(key))

    return cached["value"]
```

Equivalent to stale-while-revalidate but at app level.

---

## 7. Scheduled Warming

Some workloads have predictable patterns:
- Black Friday at midnight → warm checkout cache at 23:55
- Daily report at 8am → warm at 7:55
- Lunch traffic peak at 12pm → warm at 11:55

```python
# APScheduler or Celery Beat
@celery.scheduled_task(crontab(hour=11, minute=55))
def warm_lunch_traffic():
    warm_top_restaurants()
```

---

## 8. Warming Multi-Level Caches

Need to warm L1 AND L2.

```python
async def warm_both_levels(key):
    value = await db.fetch(key)
    if value is not None:
        await l2_redis.set(key, value, ttl=300)
        l1_in_process.put(key, value)
```

For multi-pod L1 warming: each pod must warm its own L1.

```python
# Each pod warms its L1 on startup
@app.on_event("startup")
async def warm_l1():
    hot_keys = await analytics.top_100()
    for key in hot_keys:
        value = await l2_redis.get(key)
        if value is not None:
            l1.put(key, value)
```

---

## 9. Anti-Patterns

### Anti-pattern 1: Warming everything
Tries to load entire DB to cache → fails. Pick top-N hot keys.

### Anti-pattern 2: Synchronous warming during request handling
First request triggers full warm → user waits seconds.

### Anti-pattern 3: No rate limiting on warmer
Warmer hammers DB → slows users.

### Anti-pattern 4: Stale "hot list"
Hot list from 6 months ago → warming irrelevant keys.

### Anti-pattern 5: Forgetting health checks
Warming takes 5 minutes → readiness probe fails → pod killed.

**Fix:** Liveness vs Readiness probes:
```yaml
livenessProbe:
  httpGet: { path: /health/live }     # process up
readinessProbe:
  httpGet: { path: /health/ready }    # warming complete
```

---

## 10. Production Pattern (Comprehensive)

```python
class CacheWarmer:
    def __init__(self, l1, l2, db, analytics):
        self.l1, self.l2, self.db = l1, l2, db
        self.analytics = analytics
        self.warming_complete = asyncio.Event()

    async def startup_warm(self):
        """Eager warm at startup — block until done."""
        if not await self._acquire_warming_lock():
            return  # another pod doing it

        try:
            top_keys = await self.analytics.top_keys(limit=1000)
            await self._progressive_warm(top_keys, batch=20)
        finally:
            await self._release_warming_lock()
            self.warming_complete.set()

    async def background_refresh(self):
        """Continuously refresh hot keys."""
        while True:
            top_keys = await self.analytics.top_keys(limit=500)
            await self._progressive_warm(top_keys, batch=10, delay=0.5)
            await asyncio.sleep(300)   # every 5 min

    async def _progressive_warm(self, keys, batch=10, delay=0.1):
        semaphore = asyncio.Semaphore(batch)
        async def fetch_one(k):
            async with semaphore:
                value = await self.db.fetch(k)
                if value:
                    await self.l2.set(k, value)
                    self.l1.put(k, value)
                await asyncio.sleep(delay)
        await asyncio.gather(*[fetch_one(k) for k in keys])


# FastAPI integration
warmer = CacheWarmer(...)

@app.on_event("startup")
async def startup():
    asyncio.create_task(warmer.background_refresh())
    await warmer.startup_warm()

@app.get("/health/ready")
async def ready():
    return {"ready": warmer.warming_complete.is_set()}
```

---

## 11. Monitoring Warming

### Metrics
- `cache_warm_duration_seconds`
- `cache_warm_keys_loaded_total`
- `cache_warm_keys_failed_total`
- `cache_hit_rate_after_warm` (should jump from ~0 to ~95%)

### Alerts
- Warming takes > expected (slow DB)
- Hit rate after warm still low (wrong keys)

---

## 12. Interview Questions

**Q1: Cache warming kya hai?**
Pre-populate cache before traffic arrives → avoid cold-start stampede.

**Q2: Strategies?**
- Eager startup
- Background continuous refresh
- Refresh-ahead pattern
- Scheduled (cron) warming
- Snapshot/restore

**Q3: Which keys to warm?**
Top-N from analytics (last hour/day), known static content (homepage, top products), predictive based on time pattern.

**Q4: Multi-pod cold start protection?**
Distributed lock so only ONE pod warms shared cache. Other pods just warm their L1 from L2.

**Q5: Warming without DB burst?**
Progressive batching + rate limiting. Use semaphore for concurrency control.

**Q6: Readiness probe + warming?**
Liveness = process alive (don't fail during warming). Readiness = warmed (only get traffic when ready). Crucial in K8s rollouts.

**Q7: Refresh-ahead pattern?**
Refresh key before it expires. Prevents subsequent miss. Equivalent to SWR.

---

## 13. Best Practices

1. **Always warm on startup** for known hot keys
2. **Background refresh** for changing top-N
3. **Distributed lock** prevents thundering-herd warming
4. **Progressive batching** — don't burst DB
5. **Use analytics** for hot key selection
6. **Don't warm everything** — top 100-1000 only
7. **Readiness probe** only true after warming
8. **Monitor warming duration + hit rate post-warm**
9. **Refresh-ahead** for known-popular keys
10. **Scheduled warming** for predictable peaks

---

## Related
- [[03_cache_stampede_cold_start]]
- [[07_multi_level_caching]]
- [[09_negative_caching]]
