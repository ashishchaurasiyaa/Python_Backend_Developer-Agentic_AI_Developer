# 04 — Caching

## Why cache?

Caches solve **latency** and **throughput** problems by keeping frequently-accessed data closer to the consumer (CPU cache, RAM, regional DC). Typical wins:

- DB read at 5ms → Redis read at 0.5ms (10×)
- Cross-region API call at 150ms → local CDN at 5ms (30×)
- Serving 1M QPS from cache vs hammering the DB (often impossible)

**Cost:** complexity (invalidation, consistency, capacity), memory $, and the risk that the cache becomes a hidden critical dependency.

## Cache layers — where to put them

| Layer | Latency | Examples | Best for |
|-------|---------|----------|----------|
| **Browser cache** | ~0 | HTTP `Cache-Control`, `ETag` | Static assets, public APIs |
| **CDN edge cache** | 5-30 ms | Cloudflare, CloudFront, Fastly, Akamai | Images, videos, static HTML, public API responses |
| **Reverse-proxy cache** | <1 ms | nginx, Varnish | HTML fragments, anonymous traffic |
| **App-level in-memory** | µs | Caffeine (Java), `functools.lru_cache` (Py) | Hot config, per-instance computation |
| **Distributed cache** | 0.5-2 ms | Redis, Memcached | Sessions, hot DB rows, computed results |
| **DB internal cache** | varies | Postgres shared_buffers, MySQL buffer pool | Auto, free, but limited |

**Cache hierarchy strategy:** cascade from cheapest/fastest down. Most requests should die at the browser or CDN. The fewer requests reach your DB, the cheaper your system.

## Read patterns

### Cache-aside (lazy loading)

```
read(key):
    val = cache.get(key)
    if val is None:
        val = db.get(key)
        cache.set(key, val, ttl=300)
    return val
```

- **Pros:** Cache only stores what's actually requested. App controls what's cached. Simple.
- **Cons:** First read after a miss is slow (DB hit). Stale data if DB updated but cache not invalidated.
- **Most common pattern.**

### Read-through

App always reads from cache. Cache itself fetches from DB on miss.

- **Pros:** App code simpler (no DB read path).
- **Cons:** Tight coupling between cache and DB; usually needs a managed product (e.g., Amazon ElastiCache with auto-loader).

## Write patterns

### Write-through

```
write(key, val):
    cache.set(key, val)
    db.set(key, val)
```

- Cache always fresh. **Cons:** Write latency = cache + DB. Writes that aren't followed by reads waste cache space.

### Write-back / write-behind

```
write(key, val):
    cache.set(key, val)
    queue_for_db_write(key, val)  # async
```

- **Pros:** Fast writes. Batch DB writes.
- **Cons:** Data loss if cache dies before flush. Strong consistency lost.
- Used in: high write rate counters, analytics, leaderboards.

### Write-around

```
write(key, val):
    db.set(key, val)
    cache.invalidate(key)  # or just skip cache
```

- **Pros:** Doesn't pollute cache with write-only data.
- **Cons:** First read after write misses.
- Good for: large infrequently-read data.

## Eviction policies

When the cache is full, which entry do you drop?

| Policy | Logic | When to use |
|--------|-------|-------------|
| **LRU** (Least Recently Used) | Drop least recently accessed | Default. Good for general workloads. |
| **LFU** (Least Frequently Used) | Drop least often accessed | Stable access patterns. Avoid for trending workloads. |
| **FIFO** | Drop oldest inserted | Time-series, log-shaped data |
| **Random** | Drop random entry | Simple; surprisingly OK |
| **TTL** | Drop expired | Combined with above |
| **ARC** (Adaptive Replacement) | Balances LRU + LFU dynamically | Postgres uses similar for buffer cache |
| **W-TinyLFU** | Sketch-based frequency + recency | Caffeine; near-optimal in benchmarks |

**Reality:** LRU is the safe default; Redis offers `allkeys-lru`, `allkeys-lfu`, `volatile-lru` (only keys with TTL).

## TTL (Time To Live)

Every cache entry should have a TTL. Without one, you have an *un-invalidatable* cache — a recipe for stale data forever.

- **Short TTL (seconds):** acceptable staleness, more DB load
- **Long TTL (hours):** fewer DB hits, more stale risk
- **Add jitter** (e.g., 300s ± 30s) to avoid synchronized expiry → thundering herd

## Invalidation strategies

> "There are only two hard things in CS: cache invalidation and naming things." — Phil Karlton

1. **TTL expiry** — simple, eventually consistent. Most common.
2. **Write-through invalidation** — on write, also invalidate/update cache entry.
3. **Event-based** — DB CDC stream (Debezium, Kafka) emits change events; cache listens and invalidates.
4. **Version-keyed** — cache key includes a version; bump the version on writes (forces a new key, old cache GC'd by TTL).
5. **Manual purge API** — admin endpoint to bust specific keys.

## Cache stampede (thundering herd)

Many requests miss simultaneously and slam the DB. Causes:

- A hot key expires (1M users all hit it at once)
- Many keys expire together (no TTL jitter)
- Cache server restarts

**Fixes:**

1. **Probabilistic early expiry** — refresh probabilistically before TTL hits 0.
2. **Single-flight / request coalescing** — first miss locks the key; others wait on the result.
3. **Lock + recompute** — `SETNX cache:key:lock` ensures only one rebuild thread.
4. **Stale-while-revalidate** — serve stale value while refreshing in background.
5. **Pre-warm cache** — populate before traffic arrives (deploys, peak hours).

## Hot key problem

A single key gets disproportionate traffic — overwhelms one shard.

**Fixes:**

- **Local cache** in front of distributed cache (each app instance keeps its own copy of the hot key, short TTL)
- **Replicate the hot key** across multiple cache shards manually (sharded by suffix: `key:0`, `key:1`, ..., `key:9`)
- **CDN it** if data is publicly cacheable

## Redis vs Memcached

| | Redis | Memcached |
|---|-------|-----------|
| Data types | String, list, hash, set, sorted set, stream, geo, bitmap, HLL | String only |
| Persistence | Yes (RDB snapshot, AOF log) | No |
| Replication | Yes (master-replica, cluster) | No native |
| Scripting | Lua | No |
| Pub-sub | Yes | No |
| Memory model | Single-threaded I/O, multi-threaded I/O in 6+ | Multi-threaded |
| Use case | Versatile: cache + queue + counters + leaderboards | Pure cache |

**Default choice:** Redis, unless you need pure cache simplicity. Memcached is faster for plain GET/SET but loses everything on restart.

## Consistency: cache vs DB

The fundamental problem: you have two stores, they must agree.

**Inconsistency window** = time between DB write and cache update/invalidate.

| Approach | Window | Notes |
|----------|--------|-------|
| Write-through (cache then DB) | 0, but DB might fail leaving cache wrong | Need rollback logic |
| Write-through (DB then cache) | Tiny (network) | If cache write fails, retry or rely on TTL |
| Cache-aside + invalidate | Network round trip | Standard pattern |
| Read after write | Stale until TTL | Common; use "read-your-writes" if needed |
| CDC-based | Milliseconds | Most robust but complex |

**Subtle bug:** invalidate-then-write race condition:
```
T1: write DB
T1: invalidate cache
T2: read cache (miss), reads DB (old data — replication lag!)
T2: writes old data back to cache
```
Fix: invalidate AFTER write; serialize via locks; or use read replicas only after a delay.

## CDN specifics

CDNs serve content from the geographically closest "edge" node. Critical for:
- Static assets (JS, CSS, images, video segments)
- API responses (with proper `Cache-Control`)
- DDoS protection (absorbing traffic before origin)

Key HTTP headers:
- `Cache-Control: public, max-age=3600` — cacheable, fresh for 1h
- `Cache-Control: private, no-store` — never cache
- `ETag: "abc123"` — version tag for conditional GETs
- `Vary: Accept-Encoding` — vary cache by header (e.g., gzip vs br)

**Cache key composition** — usually URL + query + a few headers. Be wary of cookies; they bust cache by default.

## Real-world cache architectures

**Twitter timeline:**
- Push timeline = cached fan-out into Redis per user (Tweetstore)
- Hybrid: precompute for non-celebs, pull for celebs

**Facebook TAO:**
- Massive Memcached layer + custom graph cache
- Multi-tier (leaders + followers per region)

**Netflix:**
- EVCache (Memcached-based, replicated across AZs)
- Open Connect (their own CDN)

## Interview Q&A

**Q1: A read takes 200ms because the DB is overloaded. Walk me through your fix.**
*A:* (1) Identify what's hot — likely a few keys account for >50% of reads. (2) Add Redis cache in front (cache-aside, TTL 60s). (3) For homepage-like content, also add CDN layer. (4) Measure — should drop p95 dramatically. (5) Later, optimize DB query (index, denorm). (6) Monitor cache hit ratio; target >90%.

**Q2: Your cache hit ratio dropped from 95% to 60% overnight. What happened?**
*A:* Possible causes: (1) Memory pressure → evictions started; (2) traffic pattern shifted (cold keys becoming common); (3) cache cluster restarted; (4) TTLs synchronized and all expired together (no jitter); (5) bad deploy invalidated everything; (6) hot key was removed from app logic. Investigate by checking eviction count, memory usage, key churn rate.

**Q3: How do you cache user-specific data efficiently?**
*A:* Key includes user_id: `user:profile:12345`. Set short TTL for freshness. Use cache-aside. For very large per-user data, hash large blobs and reference by hash (content-addressable). If hot user generates huge traffic, add local in-process cache layer.

**Q4: Two services updating the same DB row. How do you keep cache consistent?**
*A:* Options: (1) Pessimistic — both go through a write service that controls cache invalidation. (2) Optimistic — each service invalidates on write; rely on short TTL to recover from misses. (3) Best — use CDC (DB binlog stream → Kafka → cache invalidator). The CDC approach decouples and reliably propagates all writes.

**Q5: What's the difference between caching and replication?**
*A:* **Replication** = full copy of data on another node, kept in sync via the DB's replication protocol. Used for HA and read scale. **Caching** = subset of data, possibly transformed, eventually consistent, evicted when stale or unused. Read replicas are still the source of truth; caches are derived.

**Q6: When would you NOT use a cache?**
*A:* (1) Workload has no read locality (every request unique). (2) Strong consistency required and you can't tolerate any staleness. (3) Data changes on nearly every read. (4) Write-heavy workload with negligible reads. (5) Tiny dataset that fits in DB memory anyway.

## Further reading

- *DDIA* — Ch 1 (Reliable systems), passim
- Existing notes: `../*_Cache*.md` if present
- "Scaling Memcache at Facebook" — Nishtala et al., NSDI 2013
- "Caching at Netflix" — EVCache blog posts
