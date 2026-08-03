# Caching — Redis vs Memcached, Invalidation, Distributed Cache Ops

**DevOps Track · Phase 17: Caching**

> Complementary to the app-level coverage in Backend_Developer/ — this covers the infra/ops angle: hardening, deployment, and operating these systems.

## Quick Concepts

- **TTL (Time To Live)** = how long a cached entry lives before automatic expiry
- **Cache-aside (lazy loading)** = app checks cache first, on miss reads from DB and populates cache
- **Write-through** = app writes to cache and DB together, synchronously, on every write
- **Write-behind (write-back)** = app writes to cache immediately, DB write happens asynchronously later
- **Cache invalidation** = removing or updating stale cache entries when the underlying data changes
- **Consistent hashing** = a hashing scheme that minimizes key remapping when cache nodes are added/removed
- **Cache stampede / thundering herd** = many requests simultaneously miss the cache for the same key and all hit the DB at once, often when a hot key expires

---

## Why This Matters for Ops

```
Backend_Developer/08_Redis and 09_Caching teach "how do I call
cache.get() / cache.set() from Django/FastAPI."

This file is the layer above that:
   - Which cache technology do you actually deploy, and why?
   - When 10,000 requests all miss the cache for the same hot key
     at the exact same moment, does your DB survive?
   - When you add a 4th cache node to a 3-node cluster, does 75%
     of your cache go cold at once?

These are capacity-planning and failure-mode questions — the
difference between "cache improves latency" and "cache outage
takes down the database it was protecting."
```

---

## Redis vs Memcached — Ops Comparison

| | Redis | Memcached |
|---|---|---|
| Data structures | Strings, hashes, lists, sets, sorted sets, streams, bitmaps | Strings/blobs only |
| Persistence | RDB snapshots + AOF (optional) | None — pure in-memory, data lost on restart always |
| Replication / HA | Sentinel, Cluster (built-in) | None built-in — client-side sharding only |
| Clustering | Native (Redis Cluster, hash slots) | Client-side consistent hashing only (e.g. `ketama`) |
| Multithreading | Mostly single-threaded core (I/O threading added in 6+) | Multithreaded natively — better raw throughput per node for simple GET/SET |
| Memory overhead per key | Higher (richer metadata per data structure) | Lower — simpler storage model |
| Use beyond pure cache | Yes — queues, pub/sub, rate limiting, leaderboards | No — cache only, by design |
| Eviction policies | Multiple (LRU, LFU, TTL-based, random) configurable | LRU only |

```
Practical takeaway: choose Memcached when you want the simplest
possible pure cache with maximum raw throughput per node and don't
need persistence, pub/sub, or rich data structures. Choose Redis
for almost everything else — the ecosystem, HA tooling, and
versatility usually outweigh Memcached's narrower throughput edge
in modern deployments. Most new systems default to Redis.
```

```bash
# Memcached — minimal, no persistence, no auth by default (harden separately)
memcached -m 512 -p 11211 -u memcache -l 127.0.0.1

# Redis — richer config surface
redis-server --maxmemory 512mb --maxmemory-policy allkeys-lru
```

### Eviction Policies (Redis)

```conf
maxmemory 2gb
maxmemory-policy allkeys-lru
# noeviction        — errors on write when full (default — dangerous if unexpected)
# allkeys-lru        — evict least-recently-used key, any key
# volatile-lru       — evict LRU among keys WITH a TTL set only
# allkeys-lfu        — evict least-frequently-used (Redis 4+)
# volatile-ttl       — evict the key with the nearest expiry first
```

```
"noeviction" as the default catches people off guard in production —
once maxmemory is hit, WRITES START FAILING with an OOM error instead
of silently evicting old data. For a pure cache use case, allkeys-lru
or allkeys-lfu is almost always what you actually want.
```

---

## Cache Invalidation Strategies

```
"There are only two hard things in Computer Science: cache
invalidation and naming things." — Phil Karlton

It's a joke, but the underlying truth is real: caching is easy to
add and deceptively hard to keep CORRECT — stale data served
confidently is worse than no cache at all, because nothing looks
wrong until someone notices the numbers don't match reality.
```

### TTL — The Simplest Tool

```
Set an expiry on every cached entry. Simple, self-healing (bad data
ages out on its own), but means there's always a window where stale
data can be served — bounded by the TTL you choose.
```

```python
# TTL as the baseline safety net, even alongside other strategies
cache.set(f"user:{user_id}", data, ttl=300)   # 5 min max staleness
```

### Cache-Aside (Lazy Loading)

```
App logic:
   1. Check cache for key.
   2. On HIT: return cached value.
   3. On MISS: read from DB, write result to cache, return it.

Most common pattern. Cache only holds what's actually been requested
(no wasted memory on unused data). Downside: first request after
a miss always pays full DB latency, and there's a small window of
staleness if the underlying data changes without explicit invalidation.
```

```python
def get_user(user_id):
    cached = cache.get(f"user:{user_id}")
    if cached:
        return cached
    user = db.query(User).get(user_id)
    cache.set(f"user:{user_id}", user, ttl=300)
    return user
```

### Write-Through

```
Every write goes to cache AND the DB synchronously, in the same
request. Cache is always consistent with the DB (as of that write).
Downside: every write pays the latency cost of both operations, and
you're caching data that might never be read again.
```

```python
def update_user(user_id, data):
    db.update(User, user_id, data)
    cache.set(f"user:{user_id}", data, ttl=300)   # keep cache in sync
```

### Write-Behind (Write-Back)

```
Write goes to cache immediately (fast response to caller), DB write
is queued and happens asynchronously afterward — often batched.
Fastest write path, but risks data loss if the cache crashes before
the async DB write completes, and adds real complexity (ordering,
retry, failure handling for the deferred write).

Used less often at the app level than the other two — more common
in specialized systems (write-back disk caches, some CDN origins)
than typical web app caching.
```

### Explicit Invalidation on Write

```
Instead of (or in addition to) TTL, actively DELETE the cache key
when the underlying data changes — the app knows exactly when data
becomes stale, so it doesn't have to wait for a TTL to expire.
```

```python
def update_user(user_id, data):
    db.update(User, user_id, data)
    cache.delete(f"user:{user_id}")   # next read repopulates via cache-aside
```

```
Comparison, when to use which:

TTL alone           → simplest, acceptable when brief staleness is fine
Cache-aside + TTL    → the default for most read-heavy web apps
Write-through        → when reads must always see the latest write
                        immediately (rare — usually TTL is "good enough")
Explicit invalidation → when you need immediate consistency without
                         paying write-through's cost on every write
```

---

## Distributed Cache Considerations

### Consistent Hashing

```
Naive approach: key → hash(key) % N nodes. Add or remove a node
(N changes) and almost EVERY key remaps to a different node —
the entire cache goes cold at once, and every request becomes a
cache miss simultaneously, hammering the DB.

Consistent hashing: nodes and keys are placed on a hash ring. Adding
or removing a node only remaps the keys that fall in that node's
small arc of the ring — typically ~1/N of keys move, not ~(N-1)/N.
This is what Redis Cluster's hash-slot model and Memcached client
libraries (ketama) implement.
```

```
Ring example (simplified):
   Node A owns hash range [0, 5000)
   Node B owns hash range [5000, 10000)
   Node C owns hash range [10000, 16384)

Remove Node B → its range gets absorbed by A and C (their neighbors
on the ring), NOT redistributed across all nodes — only keys that
lived in B's range are affected.
```

### Cache Stampede / Thundering Herd

```
Real example: a product page's cached data has a 60-second TTL.
The product goes viral and gets 5,000 requests per second. At
second 60, the key expires. The NEXT request after expiry misses
the cache and starts a DB query — but before that query finishes
(say, 200ms later), 999 more requests have ALSO missed the same
now-expired key and ALSO started their own identical DB queries.

Result: 1000 simultaneous identical queries hit the DB in a 200ms
window for data that's about to be the same value all 1000 times —
the exact load spike a cache exists to prevent, all triggered by
the cache itself.
```

**Mitigation 1 — Locking / single-flight**
```python
def get_product(product_id):
    cached = cache.get(f"product:{product_id}")
    if cached:
        return cached

    lock_key = f"lock:product:{product_id}"
    if cache.set(lock_key, "1", nx=True, ttl=10):   # only ONE request wins the lock
        product = db.query(Product).get(product_id)
        cache.set(f"product:{product_id}", product, ttl=60)
        cache.delete(lock_key)
        return product
    else:
        time.sleep(0.05)          # short wait, then retry cache read
        return get_product(product_id)   # other requests wait for the winner
```

**Mitigation 2 — Early/probabilistic refresh (avoid the exact-expiry cliff)**
```python
# Refresh slightly BEFORE hard expiry, probabilistically, so refreshes
# spread out instead of all requests hitting the wall at the same second
import random

def get_with_early_refresh(key, ttl=60, beta=1.0):
    value, set_time = cache.get_with_metadata(key)
    if value and (time.time() - set_time) < ttl - (beta * random.random() * 5):
        return value
    # else: refresh now, this request pays the cost, others still serve stale briefly
    return refresh_and_cache(key, ttl)
```

**Mitigation 3 — Never let hot keys have hard TTLs with no stale-serve fallback**
```
Serve stale-while-revalidate: return the slightly-stale cached value
immediately while ONE background request refreshes it, instead of
every request blocking on a fresh DB read. Most CDNs and some cache
libraries support this pattern natively (stale-while-revalidate
header semantics, or manually via a background refresh task).
```

```
Rule of thumb for any high-traffic hot key: never rely on a bare
TTL expiry with no stampede protection. Add jitter to TTLs
(ttl = base + random(0, base*0.1)) at minimum, so mass-expiry of
many keys set at the same time doesn't compound into a single
synchronized stampede across MANY keys at once.
```

---

## Senior Tip

```
The most dangerous caching bug in production isn't "cache is stale"
— it's "cache expired and now the DB is getting the full uncached
load it was never sized for, all at once." Load-test what happens
when your cache is COLD (fresh deploy, cluster resize, mass
invalidation), not just what happens when it's warm. A cache that
makes the happy path fast but the cold-start path catastrophic is
a liability disguised as an optimization.
```

## Interview Angle

**Q: Why is `noeviction` a risky default maxmemory-policy for a cache use case?**
Once memory fills up, Redis starts rejecting WRITES with an OOM error
instead of evicting old entries — for a pure cache, that's almost
always the wrong failure mode. An LRU/LFU eviction policy degrades
gracefully (cache just gets less effective) instead of causing write
errors to propagate into the app.

**Q: How does consistent hashing reduce the blast radius of adding a cache node?**
Without it, changing the node count (N) remaps nearly every key
because of the `% N` modulo dependency. Consistent hashing places
nodes and keys on a ring so each node only "owns" a contiguous arc —
adding or removing a node only remaps the keys in that node's
neighborhood, roughly `1/N` of total keys instead of nearly all of them.

**Q: Design a mitigation for a cache stampede on a single very hot key.**
Use a lock/single-flight pattern so only one request per expired key
recomputes the value while others either wait briefly and re-check
the cache or (better) receive a still-fresh-enough stale value while
a background refresh runs — combined with TTL jitter so many keys
set at the same time don't all expire in the same instant.

---

## Related

- [../15_Databases/02_nosql_mongodb_redis.md](../15_Databases/02_nosql_mongodb_redis.md) — Redis persistence/HA (Sentinel vs Cluster) in depth
- [../../Backend_Developer/00_Year0-2_Junior/08_Redis/](../../Backend_Developer/00_Year0-2_Junior/08_Redis/) — app-level Redis usage
- [../../Backend_Developer/00_Year0-2_Junior/09_Caching/](../../Backend_Developer/00_Year0-2_Junior/09_Caching/) — app-level caching patterns
