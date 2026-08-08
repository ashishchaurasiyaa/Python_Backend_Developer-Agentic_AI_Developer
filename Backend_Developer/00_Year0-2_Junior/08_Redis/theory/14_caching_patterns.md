# Redis Caching Patterns

## Why It Matters (Senior 5 YOE Context)

"There are only two hard things in Computer Science: cache invalidation and
naming things." — this line exists as an interview icebreaker for a reason:
caching LOOKS trivial (SET, GET, done) but every senior system-design
interview drills into the failure modes — stale reads, thundering herds,
lost writes on crash, cache/DB inconsistency under concurrency.

You already have `04_vector_search_fastapi.md`'s coverage of **semantic
caching** (caching LLM responses by embedding similarity — same MEANING of
query hits cache). This doc is the general case: caching arbitrary
DB rows/query results/API responses by EXACT key, which is what "design a
caching layer for a read-heavy service" actually means in an interview.

Senior interview: "Design the caching layer for a product-detail API doing
50K reads/sec against a DB that can't handle more than 5K/sec." → This is a
cache-aside + stampede-protection + TTL-jitter conversation, and being able
to name WHY each piece exists (not just that it exists) is what separates a
5 YOE answer from a tutorial answer.

---

## Core Concepts

### 1. Cache-Aside (Lazy Loading) — the default pattern

App owns the logic: check cache → miss → read DB → populate cache → return.

```
Read path:
  App → GET cache
          │
          ├─ HIT  → return value
          │
          └─ MISS → App → READ DB → App → SET cache (with TTL) → return value

Write path:
  App → WRITE DB → App → DEL cache key (invalidate, don't update-in-place)
```

```python
def get_user(user_id):
    key = f"user:{user_id}"
    cached = r.get(key)
    if cached:
        return json.loads(cached)          # cache HIT

    user = db.query(f"SELECT * FROM users WHERE id = {user_id}")  # MISS → DB
    r.set(key, json.dumps(user), ex=300)   # populate cache, TTL 5 min
    return user
```

**Why it's the default:** cache only holds keys that were actually
requested (no wasted memory on cold data), and a cache outage degrades to
"every read hits the DB" rather than breaking reads entirely — the app
still works, just slower.

### 2. Write-Through

Write goes to cache AND DB synchronously, as one logical operation, before
returning to the caller.

```
App → WRITE cache → WRITE DB → return success (only after BOTH succeed)
```

```python
def update_user(user_id, data):
    key = f"user:{user_id}"
    db.execute(f"UPDATE users SET ... WHERE id = {user_id}", data)  # DB first
    r.set(key, json.dumps(data), ex=300)                            # then cache
    # cache is now guaranteed consistent with DB — no stale-read window
```

**Trade-off:** every write pays the latency of BOTH writes (cache + DB), so
write-heavy workloads get slower — but reads are always fresh, no
cache-aside "first reader after write sees a miss" cost either.

### 3. Write-Behind (Write-Back)

Write goes to cache immediately (fast return to caller); the DB write is
deferred and done asynchronously via a queue/buffer that flushes in batches.

```
App → WRITE cache → return success (fast!)
                │
                └─(async, batched)→  Queue → Worker → WRITE DB
```

```python
def update_user_writebehind(user_id, data):
    key = f"user:{user_id}"
    r.set(key, json.dumps(data), ex=300)      # fast: cache only
    r.rpush("writebehind:queue", json.dumps({"key": key, "data": data}))
    # background worker drains "writebehind:queue" and batches DB writes
```

**Trade-off:** fastest possible writes, and batching DB writes reduces DB
load — but if the cache/queue is lost before the flush happens (crash,
eviction), those writes are GONE. Only acceptable when some data loss is
tolerable (metrics, view counters, non-critical analytics) — never for
financial/critical state.

### 4. Read-Through

Architecturally different from cache-aside: the APP never talks to the DB
directly on a miss — the CACHE (or a caching layer/library sitting in front
of it) is responsible for loading from the DB itself. The app only ever
calls `get()`.

```
Cache-aside:                          Read-through:
  App → cache.get()                     App → cache.get()
  if miss:                                          │
    App → db.query()                    (cache itself, internally)
    App → cache.set()                      cache miss → cache → db.query()
                                                     → cache stores it
                                                     → returns to App
  App owns the miss-handling logic.     Cache/library owns the miss-handling
                                         logic — app code stays a single
                                         call, no if/else miss branch.
```

Redis itself has no native read-through — this is usually implemented via
a caching library/ORM layer (e.g. Spring Cache `@Cacheable` with a
`CacheLoader`, or a custom wrapper) that hides the DB-fetch-on-miss inside
the `get()` call:

```python
class ReadThroughCache:
    def __init__(self, redis_client, loader_fn, ttl=300):
        self.r = redis_client
        self.loader_fn = loader_fn     # e.g. lambda id: db.query(...)
        self.ttl = ttl

    def get(self, key, loader_arg):
        cached = self.r.get(key)
        if cached:
            return json.loads(cached)
        value = self.loader_fn(loader_arg)   # cache handles the miss internally
        self.r.set(key, json.dumps(value), ex=self.ttl)
        return value

user_cache = ReadThroughCache(r, lambda uid: db.query(f"SELECT * FROM users WHERE id={uid}"))
user = user_cache.get("user:42", 42)   # app never sees a miss branch
```

**Interview framing:** cache-aside and read-through do the SAME work — the
difference is WHO owns the DB-fetch-on-miss code. Cache-aside = app code.
Read-through = cache/library code. In practice with Redis (no built-in
loader), most systems ARE cache-aside even when people casually say
"read-through cache."

### 5. Cache Stampede / Thundering Herd

**The problem:** a hot key expires (or is evicted). In the next instant,
hundreds/thousands of concurrent requests all miss the cache simultaneously
and ALL hammer the DB at once trying to repopulate it — the exact load
spike the cache existed to prevent.

```
t=0: key "product:99" (very hot, 10K req/sec) expires
t=0+ε: 10,000 concurrent requests all see cache MISS
       → all 10,000 hit the DB simultaneously
       → DB falls over
```

**Mitigation (a) — Distributed lock, only one request repopulates:**

```python
def get_product_with_lock(product_id):
    key = f"product:{product_id}"
    cached = r.get(key)
    if cached:
        return json.loads(cached)

    lock_key = f"lock:{key}"
    # SET NX PX = atomic "acquire lock for 5s, only if nobody holds it"
    got_lock = r.set(lock_key, "1", nx=True, px=5000)

    if got_lock:
        try:
            value = db.query(f"SELECT * FROM products WHERE id = {product_id}")
            r.set(key, json.dumps(value), ex=300)
            return value
        finally:
            r.delete(lock_key)
    else:
        # someone else is repopulating — wait briefly and retry from cache
        time.sleep(0.05)
        return get_product_with_lock(product_id)   # retry (bounded in real code)
```

Only the request that wins `SET NX PX` hits the DB; everyone else
spin-waits and retries the cache a few ms later, once the winner has
repopulated it.

**Mitigation (b) — Probabilistic early expiration (XFetch-style):**
instead of waiting for a hard expiry, each read has a small, growing
probability of proactively recomputing the value BEFORE it actually
expires — spread across many requests over time, so no single instant sees
a mass-miss. Roughly: `if now > expiry - delta * beta * log(random())`, trigger
early recompute (one request does it, others still get the still-valid
cached value in the meantime).

**Mitigation (c) — Request coalescing / single-flight:** in-process, if two
requests for the same missing key arrive concurrently, only the first
actually calls the DB — the second (and all others) wait on the SAME
in-flight future/promise and get the same result once it resolves. Avoids
redundant DB calls even before the distributed lock layer is involved
(e.g. `singleflight` in Go, or an `asyncio.Future` keyed by cache key in
Python).

### 6. TTL Jitter

If many keys are all written with the same TTL, they all expire at the
same instant — which turns into a stampede across MANY keys at once (worse
than a single hot key expiring).

```python
# BAD: all keys expire in exactly 300s → mass-expiry stampede
r.set(key, value, ex=300)

# GOOD: jitter the TTL so expiries spread out over time
import random
jitter = random.randint(-30, 30)          # +/- 30s spread
r.set(key, value, ex=300 + jitter)
```

Same idea as `09_persistence_memory.md`'s "TTL Distribution Matters" note —
this doc applies it specifically to the stampede-prevention angle rather
than the eviction-burst angle.

### 7. Cache Invalidation Strategies

- **TTL-based (passive):** simplest — set a TTL, let it expire, next read
  repopulates. Accepts an "eventual consistency window" (up to TTL length)
  where cache may be stale.
- **Explicit invalidation on write (active):** when the source of truth
  (DB) changes, immediately `DEL` (or update) the cache key — no waiting
  for TTL. Tighter consistency, more code to get right (every write path
  must remember to invalidate).
- Production systems usually combine BOTH: explicit invalidation on write
  as the primary mechanism, PLUS a TTL as a safety net for any invalidation
  path that gets missed (bug, out-of-band DB write, etc.).

**"There are only two hard things in computer science: cache invalidation
and naming things (and off-by-one errors)."** — worth dropping as the
icebreaker line when a system-design interview turns to caching; it signals
you take invalidation correctness seriously rather than treating caching
as "just add Redis."

### 8. Negative Caching

Cache the FACT that something doesn't exist (short TTL), so repeated
lookups of the same non-existent key don't all fall through to the DB —
this is "cache penetration" protection (someone hammering
`GET /users/999999999` where that ID never existed).

```python
def get_user_safe(user_id):
    key = f"user:{user_id}"
    cached = r.get(key)
    if cached is not None:
        return None if cached == "__NULL__" else json.loads(cached)

    user = db.query(f"SELECT * FROM users WHERE id = {user_id}")
    if user is None:
        r.set(key, "__NULL__", ex=60)     # negative cache, SHORT ttl
        return None
    r.set(key, json.dumps(user), ex=300)
    return user
```

**At larger scale:** instead of one negative-cache key per missing ID
(which itself becomes memory pressure under an ID-scanning attack), use a
**Bloom filter** of all EXISTING IDs — a lookup that returns "definitely
not present" skips the DB entirely with O(1) memory-efficient checking, no
per-miss cache key needed at all. Trade-off: Bloom filters have false
positives (says "maybe present" for some non-existent IDs — falls through
to DB rarely) but never false negatives (never wrongly says "absent" for a
real ID).

---

## How It Works Internally

### Why `SET NX PX` Is the Right Lock Primitive

```
SET lock_key "owner_id" NX PX 5000
```

- `NX` — only set if key does NOT already exist → atomic "acquire only if
  free," no separate EXISTS-then-SET race (that would itself be a
  check-then-act race condition).
- `PX 5000` — auto-expiring in 5000ms → if the lock holder crashes before
  releasing, the lock self-heals instead of deadlocking forever.
- Single command = atomic in Redis (single-threaded execution per command)
  — no Lua script needed for the acquire step itself.

Release should ideally check ownership (`GET` == the value you set, then
`DEL`) via a Lua script, to avoid accidentally deleting a lock acquired by
someone else after yours expired — same pattern as the distributed-lock
material a senior candidate should already know from Redlock discussions.

### Cache-Aside Read/Write Timeline Under Concurrency

```
Correct order (write DB, THEN invalidate cache):

T1 (writer): UPDATE DB row  ──────────────► DEL cache key
T2 (reader):        GET cache (miss, old data expired naturally or absent)
                                    │
                                    └──► READ DB (sees NEW value) → SET cache

Result: cache ends up with the fresh value. Safe.
```

```
Race if you invalidate BEFORE writing DB (wrong order):

T1 (writer): DEL cache key ────────────────► UPDATE DB row
T2 (reader):        GET cache (miss)
                     │
                     └──► READ DB (sees OLD value, write hasn't landed yet!)
                          → SET cache with STALE value
                                                        │
T1 continues:                                    UPDATE DB row (now fresh)

Result: cache now holds the STALE value, and — because there's no further
write to trigger another invalidation — it can stay stale until TTL expiry.
```

This is why the rule is **update DB, then invalidate/delete cache** — never
the reverse. A reader that slips in during the invalidate-first window can
repopulate the cache with data that's about to be overwritten.

---

## Common Pitfalls

### 1. Invalidate-Then-Write Instead of Write-Then-Invalidate

Covered above — invalidating the cache BEFORE the DB write opens a race
window where a concurrent reader repopulates the cache with the
about-to-be-stale value. Always: **write DB → then DEL/update cache.**

### 2. No Stampede Protection on Hot Keys

A key doing 10K req/sec that's cached with a flat TTL and no lock/jitter
WILL eventually cause a stampede the moment it expires. If a key is hot
enough to matter, it's hot enough to need `SET NX PX` locking or
probabilistic early refresh — don't add this only after the outage.

### 3. TTL Too Long vs Too Short

```
TTL too long  → stale data served for longer, correctness complaints
TTL too short → cache barely helps, DB gets hammered almost as if
                there were no cache at all
```

There's no universal right number — it's a business-tolerance-for-staleness
question, tuned per key type (product price: short TTL; static content:
long TTL).

### 4. Serialization Format Mismatches Across App Versions

```
App v1 writes cache values as pickled Python objects.
App v2 (new deploy, different schema/library version) tries to
unpickle a v1-written value → crash, or silent wrong-field bugs.
```

During rolling deploys, multiple app versions share the same cache
simultaneously. Mitigate by: versioning the cache key itself
(`user:v2:{id}`) so old and new formats never collide, or using a
schema-stable format (JSON with explicit field names) instead of a
language-specific serializer like `pickle`.

### 5. Forgetting Negative Caching → Cache Penetration

Without it, a client (malicious or buggy) repeatedly requesting
non-existent keys bypasses the cache entirely on every single request,
because "not found" never gets cached — every miss becomes a DB hit.

### 6. Write-Behind Without Understanding the Durability Trade-off

Using write-behind for data that actually needs durability (e.g. order
state) means a cache crash before the async flush = silently lost writes.
Write-behind is for data where losing the last few seconds is acceptable
(counters, analytics events), not for anything that needs to survive a
crash.

---

## Interview Q&A

**Q: Cache-aside vs write-through — jab konsa use karoge?**
A: Cache-aside for read-heavy workloads where write latency matters more
than read-after-write freshness (most APIs) — cache only fills lazily on
reads. Write-through when reads must NEVER see stale data right after a
write (e.g. a config value another service reads immediately after you
change it) — accept the extra write latency for guaranteed consistency.

**Q: Cache stampede kya hai aur usse kaise bachoge?**
A: A hot key expires, and every concurrent request misses simultaneously
and hits the DB at once — can take the DB down. Mitigate with: (1) a
distributed lock (`SET key val NX PX 5000`) so only one request
repopulates while others wait/retry, (2) probabilistic early expiration so
recompute happens gradually before hard expiry, (3) request coalescing /
single-flight so concurrent in-process misses share one DB call, and
(4) TTL jitter so many keys don't expire in the same instant to begin with.

**Q: Cache invalidate karte time write DB pehle ya cache DEL pehle?**
A: Always write the DB first, then delete/invalidate the cache — never the
reverse. Invalidating first opens a race window: a concurrent reader can
miss the (now-empty) cache, read the OLD value still in the DB, and
repopulate the cache with stale data right as your write is landing — and
that staleness then persists until TTL expiry since nothing else triggers
another invalidation.

**Q: Read-through aur cache-aside mein architecturally kya farak hai?**
A: Same behavior (miss → DB → populate cache → return), different owner of
the miss-handling code. Cache-aside: the APPLICATION code explicitly checks
cache, falls back to DB, and writes back on miss. Read-through: the CACHE
(or a caching library/loader layer in front of it) handles the DB fetch
internally — app code just calls `get()` and never sees a miss branch.
Redis has no built-in read-through loader, so most Redis-based systems are
cache-aside even when described casually as "read-through."

**Q: Negative caching kya hai, aur Bloom filter se compare karo.**
A: Negative caching = caching the FACT that a key doesn't exist (short
TTL), so repeated lookups of the same missing ID don't all fall through to
the DB — protects against cache penetration. At larger scale (e.g. an
attacker scanning millions of random IDs), a Bloom filter of all valid IDs
is more memory-efficient: O(1) "definitely absent" checks with no
per-missing-key cache entry needed, at the cost of a small false-positive
rate (never false negatives).

**Q: Write-behind mein data loss kaise hota hai, aur kab acceptable hai?**
A: Write-behind acknowledges the write as soon as it hits the cache, and
flushes to the DB asynchronously later (often batched, via a queue). If the
cache/queue is lost (crash, eviction) before that flush runs, the write
never reaches the DB — silently gone. Acceptable for data where losing the
last few seconds doesn't matter (view counters, non-critical metrics,
analytics events); never acceptable for financial or otherwise
durability-critical state.

---

## Real-World Use Cases

### 1. Product Catalog API (Cache-Aside + Stampede Protection)

High-read, low-write product data. Cache-aside with a 5-minute TTL (+
jitter) covers the common case; `SET NX PX` locking protects the handful of
very-hot product pages from a stampede on expiry.

### 2. Feature Flags / Config (Write-Through)

Low write volume, but reads across the fleet must see a change almost
immediately — write-through keeps cache and DB in lockstep on every config
change, and the extra write latency is irrelevant since writes are rare.

### 3. Analytics Event Counters (Write-Behind)

High write volume (page views, click counts). Writes go to Redis instantly
(fast, absorbs the burst); a background worker batches and flushes to the
DB every few seconds. Losing the last couple seconds of counts on a crash
is an acceptable trade for the throughput win.

### 4. User Lookup by ID (Negative Caching)

A public API where `GET /users/{id}` gets hit with scanning/enumeration
traffic including many non-existent IDs — negative caching with a short
TTL (or a Bloom filter at scale) keeps that traffic from becoming DB load.

---

## References

- [Redis Caching Patterns](https://redis.io/docs/latest/develop/use/patterns/caching/)
- [Redis SET command — NX/PX flags](https://redis.io/commands/set/)
- "Designing Data-Intensive Applications" — Caching & consistency chapters
- `04_vector_search_fastapi.md` — Q2: Semantic Caching (LLM-response caching
  by embedding similarity, not covered again here)
- `09_persistence_memory.md` — "TTL Distribution Matters" (same jitter idea
  applied to eviction bursts rather than stampede prevention)
