# Caching — Write-Through, Write-Back, Write-Around, Read-Through

## Quick Reference Card
```
Cache         → Fast in-memory store — DB hit bachhata hai
Write-Through → Write to cache + DB simultaneously — consistent, slower write
Write-Back    → Write to cache only, DB baad mein — fast write, data loss risk
Write-Around  → Write to DB directly, bypass cache — for infrequent-read data
Read-Through  → Cache miss → cache itself DB se fetch karta hai
Cache-Aside   → App code DB se fetch karta hai, cache mein daalti hai (most common)
Interview hook → "Niroskos: Read-through SAP token cache | Write-around for invoices"
```

---

## PART 1: HINGLISH — Samjhne ke liye

### 1.1 Cache Kya Hai?

**Analogy: Chai waala aur fridge**

Chai waala doodh morning mein bazaar se laata hai (slow, expensive). Ye doodh apne fridge mein rakh leta hai (fast access). Din bhar chai ke liye fridge se doodh nikalta hai — bazaar nahi jaata.

- **Bazaar** = Database (slow, 5-50ms per query)
- **Fridge** = Cache/Redis (fast, <1ms)
- **Chai banana** = API request serving

Cache ke bina: Har request → DB query (slow)
Cache ke saath: Most requests → Redis (fast)

```
WITHOUT CACHE:
  User Request → App → DB (10ms) → Response
  1000 requests → 1000 DB queries → DB overloaded!

WITH CACHE:
  User Request → App → Redis (0.5ms) → Response (CACHE HIT!)
  Only on CACHE MISS → App → DB (10ms) → Update Cache
  1000 requests → ~950 Redis hits + ~50 DB queries
```

---

### 1.2 Cache-Aside (Lazy Loading) — Sabse Common

```
Cache-Aside: App code manages cache explicitly

READ:
  1. App checks cache: "Cache mein data hai?"
  2a. CACHE HIT: Return cached value (fast!)
  2b. CACHE MISS:
      - App queries DB
      - App writes result to cache
      - Return result
  
  ┌─────┐    GET key     ┌───────┐
  │ App │ ─────────────► │ Cache │
  │     │ ◄─────────────  │ (Redis)│
  │     │  MISS (null)   └───────┘
  │     │
  │     │   SELECT...    ┌─────┐
  │     │ ─────────────► │ DB  │
  │     │ ◄─────────────  │     │
  │     │   data          └─────┘
  │     │
  │     │   SET key val  ┌───────┐
  │     │ ─────────────► │ Cache │
  └─────┘                └───────┘

WRITE (no cache involvement by default):
  App → DB directly
  Cache becomes stale!
  
  Solution: Invalidate cache on write
  After DB write: cache.delete(key)
  Next read → cache miss → fresh DB fetch → cache updated

CODE:
  def get_package(package_id):
      cache_key = f'package:{package_id}'
      
      # Try cache first
      cached = redis.get(cache_key)
      if cached:
          return json.loads(cached)
      
      # Cache miss — hit DB
      package = Package.objects.get(id=package_id)
      data = PackageSerializer(package).data
      
      # Store in cache with TTL
      redis.setex(cache_key, 300, json.dumps(data))  # 5 min TTL
      return data
  
  def update_package(package_id, data):
      Package.objects.filter(id=package_id).update(**data)
      # Invalidate cache
      redis.delete(f'package:{package_id}')

Pros:
  Only cache what's actually read (no wasted memory)
  Cache failure doesn't break app (falls back to DB)
  Flexible — app controls what gets cached

Cons:
  Cold start: Empty cache → all requests hit DB initially
  Stampede risk: Many requests for same key miss simultaneously
  Stale data: If invalidation missed → wrong data served
```

---

### 1.3 Read-Through Cache

```
READ-THROUGH: Cache itself queries DB on miss

App → Cache → (if miss) Cache queries DB → returns to App

  ┌─────┐    GET key     ┌───────────────┐
  │ App │ ─────────────► │ Cache Library  │
  │     │                │               │
  │     │                │ MISS?          │
  │     │                │ → Query DB ───►│──► DB
  │     │                │ ← Get data ───│◄── DB
  │     │                │ → Store in    │
  │     │                │   cache       │
  │     │ ◄─────────────  │ Return data  │
  └─────┘                └───────────────┘

DIFFERENCE from Cache-Aside:
  Cache-Aside: App code fetches from DB on miss
  Read-Through: Cache library/layer fetches from DB on miss
  
  From app's perspective → same result
  But cache-aside = manual, read-through = automated by library

Examples:
  - AWS ElastiCache with read-through configuration
  - Ehcache (Java) with CacheLoader
  - Django's cache framework with custom backend
  
Code example (simulating read-through):
  class ReadThroughCache:
      def __init__(self, redis_client, loader_fn):
          self.redis = redis_client
          self.loader = loader_fn  # Function to load from DB
      
      def get(self, key, ttl=300):
          cached = self.redis.get(key)
          if cached:
              return json.loads(cached)
          
          # Cache library itself fetches
          value = self.loader(key)
          if value:
              self.redis.setex(key, ttl, json.dumps(value))
          return value

# Usage:
package_cache = ReadThroughCache(
    redis_client=redis,
    loader_fn=lambda key: Package.objects.get(id=key.split(':')[1])
)
package = package_cache.get(f'package:{package_id}')

Pros:
  Simpler app code (no explicit DB-then-cache logic)
  Cache always has data if it was ever requested

Cons:
  First request always slow (cache miss + DB + write)
  Cache and DB tightly coupled
```

---

### 1.4 Write-Through Cache

```
WRITE-THROUGH: Write to cache AND DB simultaneously

App → Cache → DB (both updated together)

  WRITE operation:
  ┌─────┐   Write(key, val)   ┌───────┐   Write to DB   ┌─────┐
  │ App │ ──────────────────► │ Cache │ ───────────────► │ DB  │
  │     │ ◄────ack─────────── │       │ ◄────ack──────── │     │
  └─────┘    (after both)     └───────┘                   └─────┘
  
  Both writes must succeed before acknowledging to App.

  Result:
  - Cache always in sync with DB
  - No stale data
  - Slower writes (wait for both)

READ operation:
  Cache hit guaranteed (just written!)
  
Code example:
  def update_booking(booking_id, status):
      # Write to DB
      Booking.objects.filter(id=booking_id).update(status=status)
      
      # Write to cache simultaneously (write-through pattern)
      booking_data = Booking.objects.get(id=booking_id)
      redis.setex(
          f'booking:{booking_id}',
          3600,
          json.dumps(BookingSerializer(booking_data).data)
      )
      # Both DB + cache updated

Pros:
  Cache always consistent with DB
  No separate invalidation needed
  Reads always fast (cache always populated)

Cons:
  Every write goes to both → higher write latency
  Cache fills with data that may never be read (wasted)
  Write amplification — data written twice

Best for:
  Read-heavy workloads where freshness critical
  User profile, booking status
```

---

### 1.5 Write-Back (Write-Behind) Cache

```
WRITE-BACK: Write to cache first, DB updated asynchronously later

  WRITE operation:
  ┌─────┐   Write(key, val)   ┌───────┐
  │ App │ ──────────────────► │ Cache │ ──ack──► App (fast!)
  │     │                     │ (dirty│
  └─────┘                     │  data)│
                              └───┬───┘
                                  │  Later (async batch)
                                  ▼
                              ┌───────┐
                              │  DB   │
                              └───────┘
  
  "dirty" = cache has newer data than DB

  Steps:
  1. App writes to cache → immediate ACK
  2. Cache marks key as "dirty"
  3. Background process: flush dirty keys to DB
     (Every 1 second, or every 100 writes, or on cache eviction)

Pros:
  Extremely fast writes (cache is RAM, ~microseconds)
  Batch DB writes — reduces DB I/O
  Good for write-heavy workloads

Cons:
  DATA LOSS RISK: Cache crashes → dirty data lost → DB never updated!
  Complexity: Need to manage dirty flags, flush queue
  Inconsistency window: Cache has newer data than DB

Best for:
  High-frequency counter updates (likes, views, pagecount)
  Gaming leaderboards (real-time scores)
  IoT sensor data (write every second, flush hourly)
  
  NOT for: Financial data, bookings — data loss is catastrophic!

Example (like counter):
  # Write-back for view count (losing a few views is OK)
  def increment_view_count(package_id):
      redis.incr(f'views:{package_id}')  # Fast! Immediate
      # Background task (every 60 sec):
      #   DB UPDATE packages SET views = redis.get('views:X') WHERE id = X
```

---

### 1.6 Write-Around Cache

```
WRITE-AROUND: Write directly to DB, bypass cache

  WRITE operation:
  ┌─────┐   Write    ┌─────┐
  │ App │ ─────────► │ DB  │ (cache bypassed)
  └─────┘            └─────┘
  
  Cache is NOT updated on write.
  
READ operation (if cached):
  → Cache hit → return cached
  
READ operation (first time after write):
  → Cache miss → DB → populate cache

Use when:
  Data written once, rarely read (archive, audit logs)
  Written in bulk, read never or infrequently
  Don't want to pollute cache with one-time data
  
Example:
  Invoice created → Saved to DB (write-around, not cached)
  Admin queries that invoice (once) → DB fetch (no cache needed)
  Frequent invoice lookup → would be cached on first read

Youngman invoices:
  Invoice creation: Write-Around
  - Invoice created → PostgreSQL (direct)
  - Cache not populated (most invoices only read 1-2 times)
  - If invoice looked up → Cache-Aside kicks in on read
  
  SAP token: Read-Through
  - Token fetched from SAP → cached in Redis (5 hour TTL)
  - All SAP API calls use cached token → 200ms → <1ms
  - Token refresh → Write-Through (cache + DB both updated)
```

---

### 1.7 Cache Write Strategies Comparison

```
SCENARIO: User updates their profile

WRITE-THROUGH:
  Update DB + Update cache simultaneously
  Next read: cache hit (fresh data!) ✓
  Write latency: +10ms (DB write) + cache write time
  Risk: low

WRITE-BACK:
  Update cache only
  Next read: cache hit (fresh!) ✓
  Write latency: ~1ms (just RAM write!)
  Risk: Cache crash → profile update lost! ✗

WRITE-AROUND:
  Update DB, bypass cache
  Cache now stale!
  Next read: cache miss → DB → repopulate cache
  Write latency: ~10ms (just DB write, no cache)
  Risk: One request after write → DB hit (not terrible)

CACHE-ASIDE:
  Update DB, delete cache key
  Next read: cache miss → DB → repopulate
  Clean but: thundering herd on popular keys

Choosing:
  Payment/financial: Write-Through (consistency > speed)
  Counter/views: Write-Back (speed > occasional loss)
  Archive/logs: Write-Around (rarely read)
  General web app: Cache-Aside (simplest, most flexible)
```

---

### 1.8 Cache Stampede / Thundering Herd

```
PROBLEM: Popular cache key expires
  10,000 users requesting same data
  All see cache miss simultaneously
  → 10,000 DB queries at once!
  → DB crashes

SOLUTION 1: Cache warming (pre-populate)
  Before key expires, proactively refresh
  Background job: check if TTL < 30 seconds → refresh

SOLUTION 2: Mutex/Lock
  First requester gets DB, others wait
  
  def get_with_lock(key, loader_fn, ttl=300):
      data = redis.get(key)
      if data:
          return json.loads(data)
      
      lock_key = f'lock:{key}'
      if redis.set(lock_key, '1', nx=True, ex=10):
          # Got lock — fetch from DB
          data = loader_fn()
          redis.setex(key, ttl, json.dumps(data))
          redis.delete(lock_key)
          return data
      else:
          # Another request has lock — wait and retry
          time.sleep(0.1)
          return get_with_lock(key, loader_fn, ttl)

SOLUTION 3: XFetch (Probabilistic Early Expiry)
  Before actual expiry, randomly refresh early
  Based on TTL remaining and fetch time
  
  import math, time, random
  
  def get_xfetch(key, loader_fn, ttl=300, beta=1.0):
      cached = redis.get(key)
      if cached:
          data = json.loads(cached)
          remaining_ttl = redis.ttl(key)
          fetch_time = data.get('_fetch_time', 0.001)
          
          # Should we early refresh?
          if remaining_ttl - beta * fetch_time * math.log(random.random()) < 0:
              # Probabilistically refresh early
              pass  # Fall through to DB fetch
          else:
              return data['value']
      
      start = time.time()
      value = loader_fn()
      fetch_time = time.time() - start
      
      redis.setex(key, ttl, json.dumps({'value': value, '_fetch_time': fetch_time}))
      return value
```

---

### 1.9 Ashish ke projects mein

```python
# Youngman — SAP Token Cache (Read-Through + Write-Through)
class SAPTokenCache:
    """
    Read-Through: On miss, fetches from SAP and caches
    Write-Through: On token refresh, updates both cache and DB
    """
    
    def get_valid_token(self):
        token = self.redis.get('sap:access_token')
        if token:
            return token.decode()  # Cache hit — <1ms
        
        # Cache miss — Read-Through: fetch from SAP
        token_data = self._fetch_from_sap()
        
        # Cache with TTL slightly less than expiry
        self.redis.setex(
            'sap:access_token',
            token_data['expires_in'] - 60,
            token_data['access_token']
        )
        return token_data['access_token']

# Niroskos — Package search results (Cache-Aside)
def get_package_listings(filters_hash):
    cache_key = f'packages:listing:{filters_hash}'
    
    # Cache-Aside: Check cache first
    cached = cache.get(cache_key)
    if cached:
        return cached
    
    # Miss: DB query
    packages = Package.objects.filter(is_active=True).select_related(...)
    data = PackageListSerializer(packages, many=True).data
    
    # Populate cache
    cache.set(cache_key, data, timeout=300)  # 5 min TTL
    return data

# Signal-based cache invalidation
@receiver(post_save, sender=Package)
def invalidate_package_cache(sender, instance, **kwargs):
    # Delete all listing caches (pattern delete)
    keys = cache.keys('packages:listing:*')
    cache.delete_many(keys)
    # Also delete specific package cache
    cache.delete(f'package:{instance.id}')
```

---

## PART 2: ENGLISH — Interviewer ko bolne ke liye

### 2.1 Definitions

> **Cache-Aside (Lazy Loading)**: Application code is responsible for loading data into the cache. On cache miss, the app queries the database and populates the cache. Most common pattern — flexible, only caches what's actually needed.

> **Read-Through**: Cache layer itself fetches from DB on miss. App always reads from cache. Simplifies app code but couples cache to data source.

> **Write-Through**: Every write goes to cache and DB simultaneously. Cache always consistent with DB. Higher write latency.

> **Write-Back (Write-Behind)**: Writes go to cache immediately, DB is updated asynchronously. Fast writes, risk of data loss on cache failure.

> **Write-Around**: Writes go directly to DB, bypassing cache. Cache only populated on subsequent reads. Good for write-once data.

---

### 2.2 Write Strategy Comparison

| Strategy | Write Path | Read Path | Consistency | Write Latency | Risk |
|----------|-----------|-----------|-------------|---------------|------|
| Cache-Aside | DB only + delete cache | Cache → (miss) → DB | Eventually consistent | DB write only | Stale data if invalidation missed |
| Read-Through | DB only + delete cache | Cache (auto-loads) | Eventually consistent | DB write only | Same as cache-aside |
| Write-Through | Cache + DB (sync) | Cache (always hit) | Strong | Cache + DB latency | Write amplification |
| Write-Back | Cache only (fast) | Cache (always hit) | Eventually consistent | Cache only (~µs) | Data loss on crash |
| Write-Around | DB only (bypass) | (miss) → DB → Cache | Consistent (no cache) | DB write only | Cache pollution avoided |

---

### 2.3 Cache-Aside vs Read-Through

```
Cache-Aside:
  - App code: "redis.get → miss → db.query → redis.set"
  - App has full control over cache logic
  - Can cache partial data, transform before caching
  - Good when: Different representations need caching

Read-Through:
  - Cache library: "app.get(key) → library handles miss"
  - Simpler app code
  - Cache and data model tightly coupled
  - Good when: Direct object caching, consistent TTL

In practice, Cache-Aside is used in ~90% of web apps
because frameworks (Django cache, Flask-Caching) implement it simply.
Read-Through is more common in Java ecosystem (Spring Cache, Ehcache).
```

---

### 2.4 Real Project Answer

> "In our projects, we use different caching strategies based on access patterns. For the SAP HANA OAuth token in Youngman, we use a read-through pattern — on the first API call, the cache misses, we fetch the token from SAP and cache it for 5 hours. All subsequent SAP calls hit the cache, reducing per-call overhead from 200ms to under 1ms. For package listings in Niroskos, we use cache-aside with signal-based invalidation — when a package is updated via Django post_save signal, we delete all related cache keys. We explicitly chose write-around for invoice data — invoices are written once and infrequently read, so caching them would waste Redis memory without meaningful benefit."

---

### 2.5 Common Follow-up Q&A

**Q1: How do you decide cache TTL?**
> "TTL is a trade-off between freshness and performance. Formula: `acceptable_staleness ÷ update_frequency`. For package listings that update a few times per day, 5-minute TTL is acceptable. For user session tokens, 24-hour TTL matches session duration. For financial balances, we don't cache — freshness is critical. For reference data like country/city lists that change monthly, 24-hour TTL is fine. Long TTL = better performance but stale data risk. Short TTL = more DB hits but fresher data. Always pair TTL with event-driven invalidation (signals/triggers) for data that changes unpredictably."

**Q2: How do you handle cache invalidation at scale?**
> "Cache invalidation is famously hard — there are only two hard things in computer science: cache invalidation and naming things. Our approach: (1) Signal-based invalidation — Django post_save/post_delete signals delete related cache keys immediately. (2) Short TTL as safety net — even if signal missed, cache expires and self-heals. (3) Versioned cache keys — when data model changes, increment key version: `package:v2:123` — old `package:v1:123` naturally expires, no mass invalidation needed. (4) Cache tags (if using Redis with tag support) — tag all package caches with `package:123`, then on update, invalidate all by tag."

**Q3: What is cache warming and when do you use it?**
> "Cache warming is pre-populating the cache before traffic hits, to avoid a cold start where every request misses the cache and hammers the database. Use cases: (1) After deployment — run a warmup script that reads popular queries to populate cache. (2) Before scheduled high-traffic events (sale, marketing campaign). (3) After cache server restart. In Youngman, after a Redis failover or restart, we have a management command that pre-populates the SAP token and common package listings. Without this, the first few minutes after restart would hit the database hard."

---

## Interview Cheat Sheet

```
Cache Patterns:

Cache-Aside (most common):
  Read: Check cache → miss → DB → set cache
  Write: Update DB → delete cache key
  Good for: General web app, flexible, most used

Read-Through:
  Cache library itself fetches from DB on miss
  App just calls cache.get(key)
  Good for: Simpler app code, consistent caching

Write-Through:
  Write to cache AND DB together
  Strong consistency, higher write latency
  Good for: Read-heavy, freshness critical

Write-Back:
  Write to cache only, DB async later
  Fast writes, DATA LOSS RISK on crash
  Good for: Counters, views (loss acceptable)

Write-Around:
  Write to DB, skip cache
  Next read: cache miss → DB → populate
  Good for: Write-once data (logs, archives)

Cache Stampede Prevention:
  Mutex lock on miss (only one DB call)
  XFetch (probabilistic early expiry)
  Cache warming (pre-populate)

My project:
  SAP token: Read-Through (miss → SAP fetch → cache 5hrs)
  Package listings: Cache-Aside (5min TTL + signal invalidation)
  Invoice creation: Write-Around (infrequently read)
  View counts: Write-Back (increment in Redis, flush to DB hourly)
```
