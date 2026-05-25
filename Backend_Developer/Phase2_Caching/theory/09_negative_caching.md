# Negative Caching

> **Interview angle:** "API endpoint /user/{id} — 80% requests for non-existent IDs from bots. DB hammered. Kya karoge?"

---

## 1. The Problem: Missing Data Hammers DB

```python
@app.get("/users/{user_id}")
async def get_user(user_id):
    cached = await cache.get(f"user:{user_id}")
    if cached:
        return cached
    user = await db.fetch_user(user_id)   # ← bot requests "1", "2", "999" non-existent → DB hit every time
    if not user:
        raise HTTPException(404)
    await cache.set(f"user:{user_id}", user)
    return user
```

**Bug:** Missing users → never cached → every request hits DB. Bots can amplify attack.

---

## 2. Solution: Cache the Miss (Negative Cache)

```python
@app.get("/users/{user_id}")
async def get_user(user_id):
    cached = await cache.get(f"user:{user_id}")
    if cached == "__NOT_FOUND__":
        raise HTTPException(404)
    if cached:
        return cached
    user = await db.fetch_user(user_id)
    if not user:
        await cache.set(f"user:{user_id}", "__NOT_FOUND__", ttl=60)   # cache miss
        raise HTTPException(404)
    await cache.set(f"user:{user_id}", user, ttl=300)
    return user
```

Now repeated "user 999 not found" lookups hit cache, not DB.

---

## 3. TTL Trade-off

**Negative cache TTL = shorter than positive.**
- User _was_ missing
- User _may be created_ in 1 minute
- TTL too long → user creates account but still "not found" until cache expires
- TTL too short → DB hammered

### Typical
- Positive cache TTL: 5-60 minutes
- Negative cache TTL: 30 seconds - 5 minutes

### Use case dependent
- "Item permanently deleted": TTL = forever (or very long)
- "User not found yet": TTL = short
- "404 page route": medium

---

## 4. Bloom Filter — Zero False Negatives

For very large key spaces, even negative cache memory adds up.

**Bloom filter:**
- Probabilistic data structure
- Says "definitely not present" or "maybe present"
- Tiny memory (~10 bits per item)
- No false negatives (if it says "not in set", it really isn't)
- False positives possible (says "maybe", might really not be)

```python
from pybloom_live import BloomFilter

# Initial setup: load all valid user IDs into Bloom filter
bf = BloomFilter(capacity=10_000_000, error_rate=0.001)
for user_id in await db.all_user_ids():
    bf.add(str(user_id))

# Request handler
@app.get("/users/{user_id}")
async def get_user(user_id):
    if str(user_id) not in bf:
        # Definitely doesn't exist — fail fast, no DB call
        raise HTTPException(404)
    # Else: maybe exists, check cache + DB normally
    return await full_lookup(user_id)
```

**Trade-off:** Bloom filter false positive = unnecessary cache check (acceptable). Bloom filter doesn't update when new users created — need refresh strategy.

---

## 5. When to Use Negative Caching

✅ **Use for:**
- 404 lookups (user_id not found)
- Failed external API calls (don't retry rapidly)
- Permission checks ("can user X access Y?" → no)
- Geocoding lookups (invalid address)
- Search queries with 0 results

❌ **Don't use for:**
- Critical operations (cached 404 may delay correct state)
- Highly dynamic data
- Personalized lookups (each user different)

---

## 6. Negative Cache with Sentinel Values

```python
NOT_FOUND_SENTINEL = "__NOT_FOUND__"
FORBIDDEN_SENTINEL = "__FORBIDDEN__"

class NegativeAwareCache:
    async def get(self, key):
        value = await self.redis.get(key)
        if value is None:
            return None, "miss"
        if value == NOT_FOUND_SENTINEL:
            return None, "negative_hit"
        if value == FORBIDDEN_SENTINEL:
            raise PermissionError()
        return json.loads(value), "hit"

    async def set_positive(self, key, value, ttl=300):
        await self.redis.set(key, json.dumps(value), ex=ttl)

    async def set_negative(self, key, ttl=30):
        await self.redis.set(key, NOT_FOUND_SENTINEL, ex=ttl)
```

---

## 7. Invalidation on Creation

When user creates account → invalidate negative cache.

```python
@app.post("/users")
async def create_user(data):
    user = await db.create_user(data)
    # Invalidate negative cache so next lookup hits DB
    await cache.delete(f"user:{user.id}")
    return user
```

**Critical:** Without this, new user can't be fetched until negative TTL expires.

---

## 8. Combining Negative Cache + Bloom Filter

```
Request → Bloom filter (fast definitively-not check)
        ├── Definitely not in set → 404 immediately, no cache/DB call
        └── Maybe in set:
                ↓
            Check cache
            ├── Cache hit (positive) → return
            ├── Cache hit (negative sentinel) → 404
            └── Cache miss:
                    ↓
                DB query
                ├── Found → cache positive, return
                └── Not found → cache negative sentinel
```

---

## 9. Handling Race: Cache Negative During Migration

Suppose user 12345 is being created (in flight). Concurrent reader sees miss → caches negative → user created shortly after → all subsequent reads see negative cache.

### Mitigations
1. Short negative TTL (30s)
2. Explicit invalidation in create_user handler
3. Versioned cache (check version after write)

---

## 10. External Service Failure Caching

Useful pattern: cache failures for short period to prevent retry storms.

```python
async def call_external_api(url):
    failure_key = f"api_failure:{url}"
    if await cache.exists(failure_key):
        raise ServiceUnavailable("recent failure, retry later")

    try:
        return await http.get(url)
    except Exception as e:
        await cache.set(failure_key, "1", ex=30)   # 30s cooldown
        raise
```

Similar to circuit breaker — but cache-based.

---

## 11. Anti-Patterns

### Anti-pattern 1: Negative cache too long
User account created but app still says "not found" for 30 minutes.

### Anti-pattern 2: Caching transient errors as 404
DB timeout → cache as "not found" → user actually exists. Wrong.

**Fix:** only cache definitive 404s, not 500s/timeouts.

### Anti-pattern 3: No invalidation on create
Forget to delete negative cache when user created → bug.

### Anti-pattern 4: Caching too many negatives
Bots enumerate all 1B possible IDs → cache fills with 1B negatives → eviction churn.

**Fix:** Bloom filter or shorter TTL.

### Anti-pattern 5: Same TTL for positive + negative
Often want different. Negative shorter.

---

## 12. Stale-While-Error Pattern

Variant: serve last-known-good value when source fails.

```python
async def fetch_with_fallback(key):
    try:
        value = await fresh_db.fetch(key)
        await cache.set(key, value, ttl=300)
        await cache.set(f"{key}:backup", value, ttl=86400)   # long backup
        return value
    except DBError:
        backup = await cache.get(f"{key}:backup")
        if backup:
            return backup        # serve stale rather than 500
        raise
```

---

## 13. Negative Caching for Authorization

```python
@app.get("/resources/{id}")
async def get_resource(id, user=Depends(current_user)):
    perm_key = f"perm:{user.id}:{id}"
    cached_perm = await cache.get(perm_key)

    if cached_perm == "DENIED":
        raise HTTPException(403)
    if cached_perm == "ALLOWED":
        return await fetch_resource(id)

    # Check fresh
    if not await check_permission(user.id, id):
        await cache.set(perm_key, "DENIED", ex=60)
        raise HTTPException(403)
    await cache.set(perm_key, "ALLOWED", ex=300)
    return await fetch_resource(id)
```

⚠️ **Caution:** Permission revocations need invalidation.

---

## 14. Interview Questions

**Q1: Negative cache kya?**
Cache the absence/miss. Prevents repeated DB hits for non-existent keys.

**Q2: TTL kaise pick?**
Shorter than positive cache. 30s-5min typically. Balance stampede prevention vs creation latency.

**Q3: Bloom filter kab use?**
When key space huge (e.g., 1B possible IDs), can't afford to cache all negatives. Bloom = O(1) lookup, tiny memory.

**Q4: False positive in Bloom?**
Says "maybe in set" — falls through to normal cache/DB check. False negatives are impossible (the guarantee that matters).

**Q5: Invalidation on creation?**
When user is created, explicitly delete negative cache entry. Otherwise new user "doesn't exist" until TTL expires.

**Q6: Cache transient errors?**
NO — only cache definitive 404s. 500/timeout = retry-able. Caching transient errors = data loss.

**Q7: Permission caching?**
Yes, but careful: revocations need fast propagation. Short TTL + explicit invalidation on role change.

---

## 15. Best Practices

1. **Always cache 404s** if reads exceed creates by 100x
2. **TTL: negative shorter than positive** (30s-5min vs 5-60min)
3. **Sentinel value** distinguishes negative from missing cache
4. **Invalidate on creation** — explicit `cache.delete(key)`
5. **Don't cache transient errors** (500, timeouts)
6. **Bloom filter** for huge key spaces
7. **Monitor negative cache hit rate** — > 50% = under attack or normal?
8. **Stale-while-error** for fallback values
9. **Permission caching** with short TTL + revocation hooks
10. **Test negative cache invalidation** in CI

---

## Related
- [[03_cache_stampede_cold_start]]
- [[08_cache_warming_strategies]]
- [[../../Phase2_Redis/theory/01_basics_installation_cli]]
