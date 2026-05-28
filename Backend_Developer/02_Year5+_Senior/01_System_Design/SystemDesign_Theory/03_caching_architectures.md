# 🔥 Caching Architectures — Complete System Design

> **Target:** 3-5 YOE | **Goal:** Caching deep — strategies, patterns, invalidation, distributed.

---

## Part 1: WHAT — Caching Kya Hai?

### Definition

> **Cache** = frequently accessed data ko **fast storage** me rakhna for quick retrieval. Slow source ko bypass karke speed badhana.

### Real-Life Analogy 📚

Soch tu **library research** kar raha hai:
- Book har baar shelf se uthana (slow)
- Notes table pe rakhna (fast access)
- "Notes" = cache

**Cache = quick reference for slow lookups.**

---

## Part 2: WHY — Caching Critical?

### Reason 1: Speed

- Database query: 50ms
- Cache hit: 1ms
- **50x faster!**

### Reason 2: Reduce Load

Same data fetched 1000 times:
- Without cache: 1000 DB queries
- With cache: 1 DB query + 999 cache hits

### Reason 3: Save Money

DB queries expensive (CPU, IO).
Cache: cheap memory operations.

### Reason 4: Scale

DB can handle 10k QPS.
Cache: 100k+ QPS.
Cache enables more scale.

### Reason 5: User Experience

Fast responses = happy users.

---

## Part 3: WHERE TO CACHE

### Level 1: Browser Cache

> User's browser stores assets.

Cached:
- Images
- CSS, JS
- Some API responses

### Level 2: CDN (Content Delivery Network)

> **Edge servers** caching static content close to users.

Cached:
- Images, videos
- Static files
- Sometimes API responses

Examples: Cloudflare, CloudFront, Akamai

### Level 3: Reverse Proxy Cache

> Cache at LB/proxy layer.

Nginx, Varnish.

Cached: HTTP responses.

### Level 4: Application Cache

> In-memory in your app.

Cached: Computed values, recent queries.

### Level 5: Distributed Cache

> Shared across servers.

Redis, Memcached.

Cached: Sessions, query results, anything.

### Level 6: Database Cache

> DB's own caching layer.

Built-in to PostgreSQL, MySQL.

---

## Part 4: CACHE STRATEGIES

### Strategy 1: Cache-Aside (Lazy Loading)

> **App manages cache.** Read from cache; if miss, get from DB and update cache.

#### Flow

```
1. App checks cache for key X
2. CACHE HIT → return data
3. CACHE MISS:
   a. Get from DB
   b. Store in cache
   c. Return data
```

#### Pros
- Only cache what's needed
- Cache failures don't break app
- Simple

#### Cons
- First request slow (cache miss)
- Stale data possible
- Complex invalidation

#### When to Use
- Read-heavy workloads
- Tolerate slight staleness
- Most common pattern

### Strategy 2: Write-Through

> **Cache and DB written together.** Always consistent.

#### Flow

```
WRITE:
1. App writes to cache
2. Cache writes to DB
3. Both updated → return success

READ: Always from cache (always fresh).
```

#### Pros
- Always consistent
- Simple reads

#### Cons
- Slow writes (2x time)
- Cache may have rarely-read data

#### When to Use
- Read-after-write consistency needed
- Write-then-read patterns

### Strategy 3: Write-Behind (Write-Back)

> **Write to cache immediately, DB updated asynchronously.**

#### Flow

```
WRITE:
1. App writes to cache (FAST)
2. Cache asynchronously writes to DB

READ: From cache.
```

#### Pros
- Very fast writes
- Batch DB writes

#### Cons
- Data loss if cache fails
- Complex
- Inconsistency possible

#### When to Use
- High-write workloads
- Can tolerate eventual persistence

### Strategy 4: Refresh-Ahead

> **Proactively refresh** cache before expiry.

#### Flow

```
Cache TTL: 60 min
At 50 min: refresh in background
Cache always fresh
```

#### Pros
- Always fresh
- No latency hit on expiry

#### Cons
- Wasted work if not accessed
- Complex

#### When to Use
- Predictable access patterns
- Latency-sensitive apps

### Strategy 5: Read-Through

> **Cache handles loading from DB.** App just reads from cache.

#### Flow

```
1. App reads from cache
2. Cache miss → cache loads from DB itself
3. Returns to app
```

#### Pros
- Simpler app code
- Encapsulated cache logic

#### Cons
- Cache library must support
- Less flexible

---

## Part 5: CACHE INVALIDATION

### "Hardest Problem in Computer Science"

> "There are only two hard things in CS: cache invalidation and naming things."
> — Phil Karlton

### Invalidation Strategies

#### Strategy 1: TTL (Time To Live)

> **Auto-expire after N seconds.**

```
Set key X with TTL = 300 seconds
After 300 seconds, cache returns miss
```

Simple. Always works. Stale possible.

#### Strategy 2: Explicit Invalidation

> **Delete from cache on write.**

```
UPDATE user X in DB
DELETE user X from cache
Next read = cache miss = fetch fresh
```

Fast invalidation. Manual.

#### Strategy 3: Write-Through

> Write to cache + DB together.
> Always fresh.

#### Strategy 4: Event-Based

> Subscribe to DB changes.
> Invalidate on event.

DB → Event Bus → Cache invalidator

Complex but real-time.

#### Strategy 5: Versioning

> Cache key includes version.
> Bump version = effective invalidation.

```
key: "user:123:v5"
After update: "user:123:v6"
Old cache effectively dead (different key)
```

---

## Part 6: CACHE KEYS

### Good Keys

- Unique per data item
- Descriptive
- Versioned

Examples:
- `user:123`
- `product:456:details`
- `user:123:cart:v2`

### Bad Keys

- Generic: `data`
- No identifier: `cache_result`
- No version: hard to invalidate

### Namespacing

```
Service:Type:ID:Variant

user-service:profile:123:full
product-service:listing:hot:page1
```

---

## Part 7: TTL STRATEGIES

### Short TTL (seconds-minutes)

For:
- Frequently changing data
- Personalized content
- Real-time features

### Medium TTL (minutes-hours)

For:
- User profiles
- Product catalog
- Most use cases

### Long TTL (days+)

For:
- Static content
- Rarely changing
- Reference data

### No TTL (Until Invalidation)

For:
- Critical fresh data
- Active management

---

## Part 8: DISTRIBUTED CACHING

### Why Distributed

Single cache:
- Memory limit
- Single point of failure
- Doesn't scale

### Solutions

#### Memcached

> Pure in-memory cache.

Simple, fast.
Less features.

#### Redis

> In-memory data store.

Features:
- Strings, lists, sets, sorted sets, hashes
- Pub/sub
- Persistence
- Clustering
- Lua scripts

Most popular.

#### Hazelcast

> Java-focused.
> Distributed computing too.

#### Cloud-Managed

- AWS ElastiCache
- Azure Cache for Redis
- GCP Memorystore

---

## Part 9: REDIS DEEP

### Why Redis Popular

- Fast (in-memory)
- Rich data types
- Persistence options
- Clustering
- Pub/sub
- Atomic operations

### Use Cases

#### Caching
Primary use case.

#### Session Store
User sessions.

#### Queue
Simple message queue.

#### Pub/Sub
Real-time messaging.

#### Counters
Atomic increment.

#### Leaderboard
Sorted sets.

#### Rate Limiting
Counters with TTL.

### Cluster Mode

> Shard data across multiple Redis instances.

Hash slots assigned to nodes.
Auto-failover.

### Persistence

#### RDB (Snapshots)
> Periodic dump to disk.

Fast restart.
Data loss possible (since last snapshot).

#### AOF (Append Only File)
> Log every write.

Durable.
Slower.

### Replication

> Master-slave.

Read scaling.
Failover.

---

## Part 10: CACHE PATTERNS

### Pattern 1: Cache Stampede (Thundering Herd)

> Cache expires.
> 1000 requests hit DB simultaneously.
> DB overwhelmed.

### Solutions

#### Locks
> First request gets lock, fetches, populates cache.
> Others wait or use stale.

#### Probabilistic Refresh
> Refresh before expiry, with randomness.

#### Stale-While-Revalidate
> Return stale immediately.
> Refresh in background.

### Pattern 2: Hot Keys

> Few keys get 90% of traffic.
> Cache uneven.

### Solutions

#### Local Caching
> Each server caches hot keys locally.

#### Sharding
> Distribute hot keys across multiple caches.

#### Replication
> Replicate hot keys to multiple nodes.

### Pattern 3: Negative Caching

> **Cache "not found" results.**

Prevents:
- Repeated DB queries for missing keys
- Attack via missing IDs

```
Get user 99999 → not found
Cache: "99999 = NULL" with short TTL
Next request: cache hit, return null
```

---

## Part 4: CACHE METRICS

### Key Metrics

#### Hit Rate
> % of requests served from cache.

```
Hit rate = hits / (hits + misses)

Good: > 80%
Great: > 95%
```

#### Latency
- Cache: < 1ms
- Backend: 50-500ms

#### Eviction Rate
- High eviction = cache too small
- Low eviction = good

#### Memory Usage
- % of allocated memory used

---

## Part 12: CACHE WARMING

### Why

> Cold cache = poor performance after restart.

### Strategies

#### On Startup
> Load frequently accessed data into cache.

#### Background Loader
> Continuously refresh popular items.

#### Predictive
> ML predicts what will be needed.

---

## Part 13: CACHE EVICTION POLICIES

### LRU (Least Recently Used)

> Evict least recently accessed.

Most common.

### LFU (Least Frequently Used)

> Evict least frequently accessed.

Good for stable patterns.

### FIFO

> Evict oldest.

Simple.

### TTL-Based

> Evict expired.

Auto cleanup.

### Random

> Random eviction.

Rare.

---

## Part 14: MULTI-LEVEL CACHING

### Architecture

```
USER
 ↓
BROWSER CACHE (level 1)
 ↓
CDN (level 2)
 ↓
APP CACHE (level 3, in-memory)
 ↓
DISTRIBUTED CACHE (level 4, Redis)
 ↓
DB QUERY CACHE (level 5)
 ↓
DATABASE
```

### Benefits

- Hit at higher level = faster
- Each level reduces load on next
- Resilient

---

## Part 15: CACHE CONSISTENCY MODELS

### Strong Consistency

> Cache and DB always in sync.

Write-through. Slow but safe.

### Eventual Consistency

> Cache may be stale briefly.

Cache-aside. Fast but stale possible.

### Read-Your-Writes

> User sees own writes immediately.

Per-user cache invalidation.

### Bounded Staleness

> Stale, but only by N seconds.

TTL-based.

---

## Part 16: COMMON ISSUES

### Issue 1: Stale Data

Cause: Cache not invalidated.
Fix: Better invalidation strategy.

### Issue 2: Cache Stampede

Cause: Many requests on cache miss.
Fix: Locks, refresh-ahead.

### Issue 3: Memory Pressure

Cause: Cache too small.
Fix: Scale up, evict properly.

### Issue 4: Wrong Items Cached

Cause: Caching everything.
Fix: Cache only frequently accessed.

### Issue 5: Cache Failures

Cause: Cache server down.
Fix: Fallback to DB, multi-cache, replicas.

---

## Part 17: CACHING ANTI-PATTERNS

### Anti-Pattern 1: Caching Everything

❌ Cache infrequent data.
✅ Cache hot data only.

### Anti-Pattern 2: No TTL

❌ Cache forever, never invalidate.
✅ Always have expiry strategy.

### Anti-Pattern 3: Big Objects

❌ Cache massive blobs.
✅ Cache smaller, related items.

### Anti-Pattern 4: Critical Path Dependency

❌ App breaks if cache down.
✅ Graceful degradation.

### Anti-Pattern 5: Cache as Source of Truth

❌ Only in cache.
✅ DB is source. Cache is acceleration.

---

## Part 18: CACHE IN MICROSERVICES

### Each Service Cache

> Service-level caching.

Per service:
- Service-specific data
- Domain logic

### Shared Cache

> Multiple services share cache.

Issues:
- Coupling
- Coordination

Generally avoid.

### Per-Request Caching

> Cache within single request lifecycle.

Avoid re-fetching same data.

---

## Part 19: PROFILING CACHE

### Questions to Answer

- What's hit rate?
- What's evicted?
- What's most accessed?
- What's wasting memory?

### Tools

- Redis: INFO command, slowlog
- Memcached: stats
- Application: custom metrics

---

## Part 20: REAL-WORLD EXAMPLES

### Example 1: E-Commerce

```
Product catalog: cached (rare changes)
User session: cached
Cart: cached
Inventory: NOT cached (must be accurate)
Prices: cached (short TTL)
```

### Example 2: Social Media

```
User profiles: heavily cached
Timeline: cached with refresh
Like counts: cached (eventual consistency)
Real-time messages: NOT cached
```

### Example 3: News Site

```
Article content: cached long
Comments: cached short
Trending: refresh-ahead
User preferences: cached
```

---

## Part 21: WHAT TO CACHE

### Cache These

✅ Frequently read
✅ Expensive to compute
✅ Rarely changes
✅ Same result for many users

### Don't Cache These

❌ Rarely accessed
❌ Always different
❌ Cheap to fetch
❌ Critical to be fresh

---

## Part 22: ARCHITECTURAL DECISIONS

### Where to Place Cache

#### Application Level
> In-process cache (LRU in app).

Pros: Fast, no network.
Cons: Per-instance, lost on restart.

#### Side-Car
> Cache as separate container.

Pros: Isolated, language-agnostic.
Cons: Network hop.

#### External
> Redis cluster.

Pros: Shared, persistent.
Cons: Network, ops.

### Which to Choose

Most apps: external (Redis).
Performance-critical: hybrid (L1 in-process + L2 Redis).

---

## Part 23: Q&A

### Q: When add cache?
**A**: When response time matters and data has read patterns.

### Q: Redis vs Memcached?
**A**: Redis usually. Memcached for pure simple cache.

### Q: How long TTL?
**A**: As long as data fresh enough for use case.

### Q: Cache invalidation hard?
**A**: Yes. Plan carefully. TTL + explicit + events.

### Q: What if cache down?
**A**: Fall back to DB. Don't crash.

### Q: How to handle cache stampede?
**A**: Locks or stale-while-revalidate.

### Q: Cache too big?
**A**: Larger instances, sharding, evict aggressively.

---

## 🎯 Bhai's Final Words

> **Caching = single biggest performance lever. 1 line of cache code = 50x faster API.**

3 Mantras:
1. **Cache-aside default**
2. **Always have TTL**
3. **Graceful degradation if cache fails**

After understanding caching deeply, you can architect systems for any scale. 🚀
