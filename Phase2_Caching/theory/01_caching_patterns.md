# Caching Patterns — Python Backend Developer Interview Prep (40 LPA)

> **Language Style**: Hinglish — concepts Hindi mein explain honge, code aur technical terms English mein rahenge.
> **Target**: Production-level understanding, not just "what is cache"

---

## Table of Contents

1. [Caching Kya Hai Aur Kyon Zaroori Hai](#1-caching-kya-hai-aur-kyon-zaroori-hai)
2. [Cache-Aside (Lazy Loading)](#2-cache-aside-lazy-loading)
3. [Read-Through Cache](#3-read-through-cache)
4. [Write-Through Cache](#4-write-through-cache)
5. [Write-Behind (Write-Back) Cache](#5-write-behind-write-back-cache)
6. [Refresh-Ahead Cache](#6-refresh-ahead-cache)
7. [Cache Stampede / Thundering Herd](#7-cache-stampede--thundering-herd)
8. [Cache Invalidation Strategies](#8-cache-invalidation-strategies)
9. [Multi-Layer Caching (L1 + L2 + L3)](#9-multi-layer-caching-l1--l2--l3)
10. [Local Cache Libraries](#10-local-cache-libraries)
11. [Distributed Cache with Redis](#11-distributed-cache-with-redis)
12. [Cache Warm-Up Strategies](#12-cache-warm-up-strategies)
13. [Semantic Cache (LLMs ke liye)](#13-semantic-cache-llms-ke-liye)
14. [Cache in FastAPI](#14-cache-in-fastapi)
15. [Interview Q&A (12 Questions)](#15-interview-qa-12-questions)

---

## 1. Caching Kya Hai Aur Kyon Zaroori Hai

### Simple Definition

**Cache** ek temporary, fast storage hai jahan frequently accessed data ko store karte hain taaki baar baar slow source (DB, API, disk) se fetch na karna pade.

Analogy: Sochao tumhare paas ek **notebook** hai (cache) aur ek **library** hai (database). Agar tumhe koi formula baar baar chahiye, toh tum library jaane ki jagah apni notebook mein likh lete ho. First time library jana padega — lekin uske baad notebook se milega directly.

### Kyon Zaroori Hai — Latency Numbers (Every Engineer Ko Yaad Hone Chahiye)

Yeh numbers **production systems mein decisions** karne ke liye critical hain:

| Storage Layer | Latency | Relative to L1 Cache |
|---|---|---|
| L1 CPU Cache | ~1 ns | 1x (baseline) |
| L2 CPU Cache | ~4 ns | 4x |
| L3 CPU Cache | ~10 ns | 10x |
| RAM (main memory) | ~100 ns | 100x |
| NVMe SSD (local) | ~100 µs | 100,000x |
| Network round-trip (same DC) | ~500 µs | 500,000x |
| HDD seek | ~10 ms | 10,000,000x |
| DB query (simple, indexed) | ~1-10 ms | 1,000,000x-10,000,000x |
| DB query (complex join, no index) | ~100ms-1s | 100,000,000x+ |
| Cross-region network call | ~150 ms | 150,000,000x |

**Redis (in-memory cache)**: ~100 µs to 1 ms (network + computation)

**Interview mein yeh bolna**: "L1 cache aur DB query mein 7-8 orders of magnitude ka difference hai. Isliye ek cached response aur uncached response mein 100x-1000x throughput difference aa sakta hai production mein."

### Real-World Impact

```
Without Cache:
User Request → Python App → PostgreSQL (10ms avg) → Response
1000 RPS → DB gets 1000 queries/sec → DB chokes at 500 QPS → 500ms+ latency

With Cache (90% hit rate):
User Request → Python App → Redis (0.3ms avg) → Response  [900 requests]
User Request → Python App → PostgreSQL (10ms avg) → Response [100 requests]
1000 RPS → DB gets only 100 queries/sec → DB happy → <1ms latency
```

### Kab Cache Karna Chahiye — Decision Framework

Cache karo jab:
- **Read-heavy workload**: Data zyada read hota hai, kam write hota hai (user profiles, product catalog, config)
- **Expensive computation**: DB join, aggregate queries, ML inference
- **Repeated identical requests**: Same query baar baar same result deta hai
- **Tolerable staleness**: Thoda purana data acceptable hai (2 minutes purana product price okay hai)
- **High traffic, low variance**: Same keys baar baar hit hote hain (80/20 rule)

Cache mat karo jab:
- **Real-time data required**: Stock prices, live scores, account balance deductions
- **Every request unique**: `/search?q=...` with infinite variations
- **Low traffic system**: DB can handle load, caching adds complexity for no gain
- **Strong consistency required**: Financial transactions, inventory (avoid oversell)
- **Data changes with every write**: Rapidly mutating user state

### Cache Hit Rate — Key Metric

```
Hit Rate = Cache Hits / (Cache Hits + Cache Misses)

Target:
- Good: > 80%
- Great: > 95%
- Excellent: > 99%

Agar hit rate < 70% hai, toh cache ka faayda kam aur overhead zyada.
```

---

## 2. Cache-Aside (Lazy Loading)

### Pattern Kya Hai

**Cache-Aside** sabse common aur samajhne mein sabse aasaan pattern hai. Application khud decide karta hai kab cache mein read karna hai aur kab DB se fetch karke cache mein store karna hai.

**"Lazy"** isliye kehte hain kyunki data tabhi cache mein aata hai jab uski pehli baar demand hoti hai — pehle se nahi bhara jaata.

### Flow Diagram (Text)

```
READ operation:
App → Cache → HIT → Return data
           ↓ MISS
           DB → Fetch data → Write to Cache → Return data

WRITE operation:
App → DB (write) → Invalidate/Delete from Cache (or let TTL expire)
```

### Python Implementation

```python
import redis
import json
import time
from typing import Optional, Any

# Redis connection
r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

def get_user(user_id: int) -> Optional[dict]:
    """Cache-Aside pattern: App manages cache explicitly"""
    cache_key = f"user:{user_id}"
    
    # Step 1: Cache mein dekho
    cached_data = r.get(cache_key)
    if cached_data:
        print(f"Cache HIT for user:{user_id}")
        return json.loads(cached_data)
    
    # Step 2: Cache MISS — DB se fetch karo
    print(f"Cache MISS for user:{user_id} — querying DB")
    user = fetch_user_from_db(user_id)  # actual DB call
    
    # Step 3: DB ka result cache mein store karo
    if user:
        r.setex(cache_key, 300, json.dumps(user))  # TTL: 5 minutes
    
    return user

def update_user(user_id: int, data: dict) -> bool:
    """On update: write to DB, then invalidate cache"""
    success = update_user_in_db(user_id, data)
    if success:
        r.delete(f"user:{user_id}")  # Cache invalidate karo
    return success
```

### Pros

1. **Resilient to cache failure**: Redis band ho jaye, app directly DB se kaam kar sakta hai (degraded performance, but no crash)
2. **Only needed data cached**: Jo kabhi access nahi hua, wo cache mein nahi hoga — memory efficient
3. **Simple to understand**: Developer clearly dekhta hai kab cache hit/miss hota hai
4. **Works with any DB**: SQL, MongoDB, Elasticsearch — sab ke saath kaam karta hai

### Cons

1. **Cache miss = 3 operations**: Read cache (miss) + Read DB + Write cache — first request slow hoti hai
2. **Stale data possible**: DB update hone par cache mein purana data ho sakta hai jab tak TTL expire na ho
3. **Cold start problem**: Naye server deployment par cache completely empty — DB par sudden spike

### TTL Strategy for Staleness

```python
# TTL kaise decide karein:

# 1. User profile (rarely changes) — long TTL
r.setex(f"user:{user_id}", 3600, data)  # 1 hour

# 2. Product inventory (changes frequently) — short TTL
r.setex(f"inventory:{product_id}", 30, data)  # 30 seconds

# 3. Config/settings (almost never changes) — very long TTL
r.setex("app:config", 86400, data)  # 24 hours

# 4. Search results (medium freshness) — medium TTL
r.setex(f"search:{query_hash}", 300, data)  # 5 minutes

# TTL Jitter — exact same TTL se mass expiry avoid karo
import random
base_ttl = 300
jitter = random.randint(0, 60)  # +0 to +60 seconds
r.setex(key, base_ttl + jitter, data)
```

### Cold Start Problem

```
Problem: 
- Naya server deploy hua → cache empty
- Users aate hain → sab DB hit karte hain → DB overload

Solutions:
1. Cache warming script deployment se pehle chalao
2. Gradual traffic shift (canary deployment)
3. Circuit breaker — DB overload hone par fail fast
4. Stale-while-revalidate pattern
```

```python
# Cold start mitigation: gradual warm-up
def warm_up_cache(user_ids: list):
    """Deployment se pehle popular keys pre-populate karo"""
    for user_id in user_ids:
        if not r.exists(f"user:{user_id}"):
            user = fetch_user_from_db(user_id)
            if user:
                r.setex(f"user:{user_id}", 3600, json.dumps(user))
        time.sleep(0.01)  # Rate limit: DB par ek saath load mat daalo

# Most accessed users (last 24h analytics se)
popular_user_ids = get_top_accessed_users(limit=10000)
warm_up_cache(popular_user_ids)
```

---

## 3. Read-Through Cache

### Pattern Kya Hai

**Read-Through** mein cache DB ke saamne khada ho jaata hai. Application sirf cache se baat karta hai — miss hone par cache **khud** DB se data laata hai aur store karta hai. Application ko yeh nahi pata ki data cache se aaya ya DB se.

**Cache-Aside vs Read-Through ka fark**:
- Cache-Aside: App cache aur DB dono ko directly manage karta hai
- Read-Through: App sirf cache se baat karta hai, cache internally DB se load karta hai

### Flow

```
READ operation:
App → Cache → HIT → Return data
           ↓ MISS (internally handled by cache)
           Cache → DB → Fetch → Store in cache → Return to App

App ko pata hi nahi ki miss hua tha. Bas data milta hai.
```

### Python Implementation

```python
from typing import Callable, Optional, Any
from functools import wraps

class ReadThroughCache:
    """
    Cache jo DB ko internally manage karta hai.
    App sirf cache se baat karta hai.
    """
    def __init__(self, loader_fn: Callable, ttl: int = 300):
        self._store = {}
        self._expiry = {}
        self._loader = loader_fn  # Function to load from DB
        self._ttl = ttl
    
    def get(self, key: str, *loader_args, **loader_kwargs) -> Optional[Any]:
        # Check cache
        if key in self._store:
            if time.time() < self._expiry.get(key, 0):
                return self._store[key]
            # Expired — delete
            del self._store[key], self._expiry[key]
        
        # Cache miss — loader internally call hota hai
        value = self._loader(*loader_args, **loader_kwargs)
        if value is not None:
            self._store[key] = value
            self._expiry[key] = time.time() + self._ttl
        
        return value
    
    def invalidate(self, key: str):
        self._store.pop(key, None)
        self._expiry.pop(key, None)

# Usage
def fetch_product_from_db(product_id: int) -> dict:
    # DB call (simulated)
    return {"id": product_id, "name": f"Product {product_id}", "price": 999}

product_cache = ReadThroughCache(
    loader_fn=fetch_product_from_db,
    ttl=600
)

# App sirf yeh karta hai:
product = product_cache.get("product:123", product_id=123)
# App ko nahi pata miss hua ya hit — seamless!
```

### Library: `aiocache` (Async Read-Through)

```python
from aiocache import Cache
from aiocache.decorators import cached

# Async read-through with Redis backend
@cached(ttl=300, cache=Cache.REDIS, endpoint="localhost", port=6379)
async def get_user_async(user_id: int) -> dict:
    # Yeh function tabhi call hoga jab cache miss ho
    user = await db.fetch_one(
        "SELECT * FROM users WHERE id = :id", {"id": user_id}
    )
    return dict(user)

# App simply await karta hai:
user = await get_user_async(user_id=1)
```

### Library: `dogpile.cache`

```python
from dogpile.cache import make_region

# Region = cache configuration
region = make_region().configure(
    'dogpile.cache.redis',
    expiration_time=300,
    arguments={
        'host': 'localhost',
        'port': 6379,
        'db': 0,
    }
)

@region.cache_on_arguments()
def get_user_profile(user_id: int):
    # Miss hone par automatically cache mein store ho jaata hai
    return db.query(User).filter_by(id=user_id).first()
```

### Kab Use Karein

- Jab cache miss handling **app layer se hide** karna ho
- Multiple services same data access karein (centralized read-through)
- Cache logic ko reuse karna ho across multiple callers
- Framework-level caching (e.g., ORM-level caching)

---

## 4. Write-Through Cache

### Pattern Kya Hai

Write hone par **dono jagah ek saath likhte hain** — pehle cache, phir DB (ya simultaneously). Cache aur DB hamesha consistent rehte hain.

```
WRITE operation:
App → Write to Cache → Write to DB → Return success

READ operation: (same as cache-aside/read-through)
App → Cache → HIT → Return (always fresh!)
```

### Python Implementation

```python
import json
import redis
from typing import Any

r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

class WriteThroughUserCache:
    
    def create_user(self, user: dict) -> dict:
        """Write-through: cache + DB dono mein likhte hain"""
        
        # DB mein pehle likhte hain (source of truth)
        user_id = db.insert_user(user)
        user['id'] = user_id
        
        # Cache mein bhi immediately store karo
        cache_key = f"user:{user_id}"
        r.setex(cache_key, 3600, json.dumps(user))
        
        return user
    
    def update_user(self, user_id: int, updates: dict) -> dict:
        """Update: DB + Cache dono update karo"""
        
        # DB update
        updated_user = db.update_user(user_id, updates)
        
        # Cache update (fresh data)
        cache_key = f"user:{user_id}"
        r.setex(cache_key, 3600, json.dumps(updated_user))
        
        return updated_user
    
    def get_user(self, user_id: int) -> dict:
        """Read: hamesha cache se milega (write-through ensure karta hai freshness)"""
        
        cache_key = f"user:{user_id}"
        cached = r.get(cache_key)
        
        if cached:
            return json.loads(cached)
        
        # Edge case: cache miss (e.g., Redis restart, TTL expire)
        user = db.get_user(user_id)
        if user:
            r.setex(cache_key, 3600, json.dumps(user))
        return user
```

### Transaction Handling — Critical Issue

```python
# Problem: DB write fail hone par cache mein stale data aa sakta hai
# Solution: Cache update sirf tab karo jab DB write succeed kare

def update_user_safe(user_id: int, updates: dict) -> dict:
    """Transactional write-through"""
    
    try:
        # 1. DB mein write karo
        updated_user = db.update_user(user_id, updates)
        
        # 2. Sirf success par cache update karo
        r.setex(f"user:{user_id}", 3600, json.dumps(updated_user))
        
        return updated_user
        
    except DatabaseException as e:
        # DB fail hua — cache ko touch mat karo
        # Cache mein purana data rahega (thoda stale, lekin correct hai)
        raise e
    
    except RedisException as e:
        # Cache update fail hua — DB mein data hai, cache miss ho jaayega next read par
        # Log karo, lekin data lost nahi hua
        logger.warning(f"Cache update failed for user:{user_id}: {e}")
        return updated_user  # DB write succeed hua, return karo

# Advanced: Redis WATCH + MULTI for optimistic locking (agar zarurat ho)
def atomic_update(user_id: int, new_data: dict):
    pipe = r.pipeline()
    try:
        pipe.watch(f"user:{user_id}")
        pipe.multi()
        pipe.setex(f"user:{user_id}", 3600, json.dumps(new_data))
        pipe.execute()
    except redis.WatchError:
        # Someone else updated between watch and execute
        pass
```

### Pros

1. **Cache always consistent**: DB write ke saath hi cache update hota hai — fresh reads guaranteed
2. **No cache miss for recently written data**: Write karo aur turant read milega
3. **Simple consistency model**: Write ke baad read hamesha latest data dega

### Cons

1. **Higher write latency**: Dono operations complete honi chahiye (2 network calls)
2. **Cache fills with rarely-read data**: Write hue data jo kabhi read na ho, wo bhi cache mein store hoga — memory waste
3. **Write amplification**: Har DB write ek extra cache write generate karta hai

---

## 5. Write-Behind (Write-Back) Cache

### Pattern Kya Hai

**Write-Behind** mein application sirf cache mein likhta hai. Cache ek queue mein yeh write daalta hai. Background process (async) eventually DB mein flush karta hai.

```
WRITE operation:
App → Write to Cache → Queue entry → Return immediately (fast!)

[Background process]:
Queue → Read entries → Batch write to DB → Remove from queue
```

### Kab Use Karein

- **High-write workloads**: Counters (views, likes), analytics events, game scores
- **Acceptable eventual consistency**: "Views count 5 minutes purana ho sakta hai"
- **Write batching beneficial**: 1000 individual writes ki jagah 1 batch write (10-50x faster)

### Python Implementation with Threading

```python
import queue
import threading
import time
from collections import defaultdict
from typing import Callable, Any

class WriteBehindCache:
    """
    Write cache mein, background mein DB ko flush karo.
    High-write scenarios ke liye best.
    """
    
    def __init__(self, db_flush_fn: Callable, flush_interval: float = 1.0,
                 batch_size: int = 100):
        self._cache = {}
        self._dirty_keys = set()  # Jinhe DB mein flush karna hai
        self._write_queue = queue.Queue()
        self._db_flush = db_flush_fn
        self._flush_interval = flush_interval
        self._batch_size = batch_size
        self._lock = threading.Lock()
        
        # Background flush thread
        self._flush_thread = threading.Thread(
            target=self._background_flush,
            daemon=True,
            name="WriteBehind-Flush"
        )
        self._flush_thread.start()
        print("WriteBehind cache started with background flush thread")
    
    def write(self, key: str, value: Any):
        """Fast write — sirf cache mein likhta hai"""
        with self._lock:
            self._cache[key] = value
            self._dirty_keys.add(key)
            self._write_queue.put((key, value))
    
    def read(self, key: str) -> Any:
        """Read — hamesha cache se (latest data, DB mein abhi tak nahi gaya hoga)"""
        with self._lock:
            return self._cache.get(key)
    
    def _background_flush(self):
        """Background thread: queue se batch read karke DB mein write karo"""
        pending = {}
        
        while True:
            try:
                # Batch collect karo
                deadline = time.time() + self._flush_interval
                
                while time.time() < deadline and len(pending) < self._batch_size:
                    try:
                        key, value = self._write_queue.get(timeout=0.1)
                        pending[key] = value  # Latest value rakhte hain (dedup)
                    except queue.Empty:
                        break
                
                # Flush pending writes
                if pending:
                    self._db_flush(pending)
                    with self._lock:
                        for key in pending:
                            self._dirty_keys.discard(key)
                    print(f"  [Flush] {len(pending)} keys written to DB")
                    pending.clear()
                    
            except Exception as e:
                print(f"  [Flush ERROR] {e}")
                time.sleep(1)  # Error par backoff
    
    def flush_now(self):
        """Graceful shutdown ke liye: remaining writes force flush karo"""
        # Remaining items queue se nikalo
        while not self._write_queue.empty():
            try:
                key, value = self._write_queue.get_nowait()
                # Direct DB write
                self._db_flush({key: value})
            except queue.Empty:
                break
        print("Force flush complete")

# Usage: View counter (millions of views/day)
view_cache = WriteBehindCache(
    db_flush_fn=lambda batch: db.bulk_update_view_counts(batch),
    flush_interval=5.0,  # Har 5 second mein DB update
    batch_size=500
)

def record_view(video_id: str):
    """Ye baar baar call hota hai — instantly return"""
    current = view_cache.read(f"views:{video_id}") or 0
    view_cache.write(f"views:{video_id}", current + 1)
```

### Data Loss Risk — WAL Solution

```python
# Problem: Cache crash hone par un-flushed writes lost ho jaate hain
# Solution: Write-Ahead Log (WAL) — write log file mein pehle, phir cache

import json
import os
from pathlib import Path

class DurableWriteBehindCache(WriteBehindCache):
    """WAL-based durability: crash recovery possible"""
    
    def __init__(self, wal_path: str, *args, **kwargs):
        self._wal_path = Path(wal_path)
        self._wal_file = open(wal_path, 'a')
        super().__init__(*args, **kwargs)
        
        # Recover from WAL on startup
        self._recover_from_wal()
    
    def write(self, key: str, value: Any):
        # 1. WAL mein pehle likho (durable)
        wal_entry = json.dumps({"key": key, "value": value, "ts": time.time()})
        self._wal_file.write(wal_entry + '\n')
        self._wal_file.flush()  # OS buffer bypass
        os.fsync(self._wal_file.fileno())  # Disk par force write
        
        # 2. Cache mein likho
        super().write(key, value)
    
    def _recover_from_wal(self):
        """Crash ke baad pending writes recover karo"""
        if not self._wal_path.exists():
            return
        
        recovered = 0
        with open(self._wal_path, 'r') as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    self._cache[entry['key']] = entry['value']
                    self._write_queue.put((entry['key'], entry['value']))
                    recovered += 1
                except json.JSONDecodeError:
                    pass
        
        if recovered:
            print(f"WAL recovery: {recovered} entries restored")
```

---

## 6. Refresh-Ahead Cache

### Pattern Kya Hai

**Refresh-Ahead** proactively cache ko refresh karta hai — **TTL expire hone se pehle** background mein fresh data la deta hai. User ko kabhi stale ya miss ka saamna nahi karna padta.

```
Timeline:
T=0: Data cached, TTL=60s
T=45s: (TTL 75% consumed) Background thread fresh data fetch karta hai
T=60s: TTL expire hoga — lekin fresh data already load ho chuka hai!
User: Hamesha fresh data milta hai, kabhi miss nahi hota
```

### Implementation

```python
import threading
import time
from typing import Callable, Optional

class RefreshAheadCache:
    """
    Proactively refresh karta hai TTL expire hone se pehle.
    News feeds, leaderboards ke liye perfect.
    """
    
    def __init__(self, loader_fn: Callable, ttl: int = 60,
                 refresh_ratio: float = 0.75):
        """
        refresh_ratio: TTL ka kitna percent consume hone par refresh trigger ho
        0.75 matlab: TTL ke 75% par refresh start ho jaata hai
        """
        self._loader = loader_fn
        self._ttl = ttl
        self._refresh_threshold = ttl * refresh_ratio
        self._store = {}  # key -> (value, set_time, ttl)
        self._lock = threading.Lock()
        self._refreshing = set()  # Kaunse keys currently refresh ho rahe hain
    
    def get(self, key: str, *args, **kwargs) -> Optional[any]:
        with self._lock:
            entry = self._store.get(key)
        
        if entry is None:
            # Complete miss — synchronously load karo
            return self._load_and_store(key, *args, **kwargs)
        
        value, set_time, ttl = entry
        age = time.time() - set_time
        
        # Expired check
        if age > ttl:
            return self._load_and_store(key, *args, **kwargs)
        
        # Refresh-ahead threshold check
        if age > self._refresh_threshold and key not in self._refreshing:
            # Background mein refresh karo — current request ko stale data do (fast!)
            self._async_refresh(key, *args, **kwargs)
        
        return value  # Stale data return karo (acceptable)
    
    def _load_and_store(self, key, *args, **kwargs):
        value = self._loader(*args, **kwargs)
        with self._lock:
            self._store[key] = (value, time.time(), self._ttl)
        return value
    
    def _async_refresh(self, key, *args, **kwargs):
        self._refreshing.add(key)
        
        def refresh_task():
            try:
                new_value = self._loader(*args, **kwargs)
                with self._lock:
                    self._store[key] = (new_value, time.time(), self._ttl)
                print(f"  [Refresh-Ahead] {key} refreshed in background")
            finally:
                self._refreshing.discard(key)
        
        threading.Thread(target=refresh_task, daemon=True).start()

# Usage: Leaderboard (high read, updates every few seconds)
leaderboard_cache = RefreshAheadCache(
    loader_fn=lambda: db.query_top_100_players(),
    ttl=30,
    refresh_ratio=0.8  # 24s par background refresh
)
```

### Staggered Expiry (Jitter) — Mass Expiry Problem

```python
# Problem: Ek saath 10,000 keys expire ho jaayein → 10,000 DB queries simultaneously

# Bad: Exact same TTL
for user_id in user_ids:
    r.setex(f"user:{user_id}", 3600, data)  # All expire at exactly same time!

# Good: TTL Jitter add karo
import random

def set_with_jitter(key: str, value: str, base_ttl: int, jitter_pct: float = 0.1):
    """Add random jitter to TTL to spread expiry"""
    jitter = int(base_ttl * jitter_pct)
    actual_ttl = base_ttl + random.randint(-jitter, jitter)
    r.setex(key, max(1, actual_ttl), value)

# 3600s TTL with ±360s jitter → 3240s to 3960s
set_with_jitter("user:1", data, base_ttl=3600, jitter_pct=0.1)
```

---

## 7. Cache Stampede / Thundering Herd

### Problem Kya Hai

Ek **highly popular cache key** expire ho jaati hai. Us time 500 concurrent requests aate hain. Sab 500 requests cache miss paate hain → sab 500 DB query karते हain simultaneously → DB overwhelm ho jaata hai → slow responses → more requests piling up → cascade failure.

```
T=0: "trending:posts" key expires
T=0.001: 500 requests simultaneously cache miss detect karte hain
T=0.002: 500 DB queries fire hoti hain
T=0.500: DB choke ho jaata hai, timeouts shuru ho jaate hain
T=1.0: Application down
```

### Solution 1: Mutex Lock (Only One Fetches)

```python
import redis
import json
import time
import uuid

r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

def get_trending_posts_safe(max_wait: float = 2.0) -> list:
    """
    Mutex lock: Sirf ek request DB se fetch kare, baaki wait karein.
    Double-checked locking pattern.
    """
    cache_key = "trending:posts"
    lock_key = "lock:trending:posts"
    lock_value = str(uuid.uuid4())  # Unique lock owner identifier
    
    # Step 1: Cache check (fast path)
    cached = r.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # Step 2: Try to acquire lock
    acquired = r.set(lock_key, lock_value, nx=True, ex=5)  # nx=only if not exists, ex=5s TTL
    
    if acquired:
        # Yeh request "winner" hai — DB se fetch karega
        try:
            posts = fetch_trending_from_db()
            r.setex(cache_key, 300, json.dumps(posts))
            return posts
        finally:
            # Lock release: sirf apna lock release karo (race condition prevent)
            pipe = r.pipeline()
            pipe.watch(lock_key)
            current = r.get(lock_key)
            if current == lock_value:
                pipe.multi()
                pipe.delete(lock_key)
                pipe.execute()
    else:
        # Doosra request DB se fetch kar raha hai — wait karo
        deadline = time.time() + max_wait
        while time.time() < deadline:
            time.sleep(0.05)  # 50ms polling
            cached = r.get(cache_key)
            if cached:
                return json.loads(cached)
        
        # Timeout — fallback to DB directly
        return fetch_trending_from_db()
```

### Solution 2: XFetch Algorithm (Probabilistic Early Expiration)

```python
import math
import random

def xfetch_get(key: str, compute_fn: Callable, ttl: int = 300,
               beta: float = 1.0) -> any:
    """
    XFetch: Probabilistically refresh BEFORE expiry.
    High-traffic keys automatically refresh ahead of time.
    
    Formula: current_time - (delta * beta * log(random())) > expire_time
    """
    
    # Redis mein value + recompute_time + TTL store karo
    meta_key = f"meta:{key}"
    
    cached_value = r.get(key)
    meta = r.hgetall(meta_key)
    
    if cached_value and meta:
        delta = float(meta.get('delta', 1))
        expire_time = float(meta.get('expire_time', 0))
        
        # Probabilistic early refresh decision
        now = time.time()
        should_refresh = now - (delta * beta * math.log(random.random())) > expire_time
        
        if not should_refresh:
            return json.loads(cached_value)
        
        print(f"  [XFetch] Probabilistic early refresh for {key}")
    
    # Recompute
    start = time.time()
    value = compute_fn()
    delta = time.time() - start
    
    expire_time = time.time() + ttl
    
    # Store with metadata
    pipe = r.pipeline()
    pipe.setex(key, ttl, json.dumps(value))
    pipe.hmset(meta_key, {'delta': delta, 'expire_time': expire_time})
    pipe.expire(meta_key, ttl)
    pipe.execute()
    
    return value
```

### Solution 3: Serve Stale + Background Refresh

```python
# "Stale-While-Revalidate" pattern
# User ko purana data instantly do, background mein fresh laao

import threading

_cache_data = {}
_cache_expiry = {}
_cache_refreshing = set()

def get_with_stale(key: str, compute_fn: Callable, ttl: int = 60,
                   stale_ttl: int = 300) -> any:
    """
    ttl: Fresh data ki age
    stale_ttl: Kitne time tak stale data acceptable hai
    """
    now = time.time()
    
    if key in _cache_data:
        age = now - _cache_expiry.get(f"{key}:set_time", 0)
        
        if age < ttl:
            return _cache_data[key]  # Fresh data
        
        elif age < stale_ttl:
            # Stale data hai — background mein refresh karo
            if key not in _cache_refreshing:
                _cache_refreshing.add(key)
                threading.Thread(
                    target=lambda: _refresh_key(key, compute_fn, ttl),
                    daemon=True
                ).start()
            return _cache_data[key]  # Stale return karo (user ko wait nahi karna)
    
    # Complete miss ya too stale — synchronously load karo
    return _refresh_key(key, compute_fn, ttl)

def _refresh_key(key, compute_fn, ttl):
    value = compute_fn()
    _cache_data[key] = value
    _cache_expiry[f"{key}:set_time"] = time.time()
    _cache_refreshing.discard(key)
    return value
```

---

## 8. Cache Invalidation Strategies

> **Phil Karlton quote (famous computer science quote)**:
> *"There are only two hard things in Computer Science: cache invalidation and naming things."*

### Why It's Hard

Cache invalidate karo toh consistency problem solve, lekin performance suffers.
Cache invalidate mat karo toh stale data, lekin performance great.
**Balance banana hi challenge hai.**

### Strategy 1: TTL-Based (Simplest)

```python
# Pros: Simple, no extra logic
# Cons: Maximum staleness = TTL duration

# Short TTL = fresh data, more DB hits
r.setex(key, 30, value)

# Long TTL = stale data, fewer DB hits  
r.setex(key, 3600, value)

# Use when: Exact invalidation timing mat'ter nahi karta
```

### Strategy 2: Event-Based Invalidation

```python
# Django signals ka use karke DB change par cache invalidate karo
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

@receiver(post_save, sender=User)
def invalidate_user_cache(sender, instance, **kwargs):
    """User save hone par cache delete karo"""
    cache_key = f"user:{instance.id}"
    r.delete(cache_key)
    print(f"Cache invalidated for user:{instance.id}")

@receiver(post_delete, sender=User)
def invalidate_user_cache_on_delete(sender, instance, **kwargs):
    r.delete(f"user:{instance.id}")

# SQLAlchemy ke liye (event listener)
from sqlalchemy import event

@event.listens_for(User, 'after_update')
def after_user_update(mapper, connection, target):
    r.delete(f"user:{target.id}")
```

### Strategy 3: Version-Based Invalidation (Cache Key Versioning)

```python
# Instead of invalidating, version increment karo
# Old keys naturally expire ya ignored ho jaate hain

def get_user_version(user_id: int) -> int:
    """User ki current version number redis se"""
    version = r.get(f"user:{user_id}:version")
    return int(version) if version else 1

def get_user_versioned(user_id: int) -> dict:
    version = get_user_version(user_id)
    cache_key = f"user:{user_id}:v{version}"
    
    cached = r.get(cache_key)
    if cached:
        return json.loads(cached)
    
    user = fetch_user_from_db(user_id)
    r.setex(cache_key, 3600, json.dumps(user))
    return user

def update_user_versioned(user_id: int, data: dict):
    """Update karo: version increment karo, old cache auto-stale"""
    db.update_user(user_id, data)
    r.incr(f"user:{user_id}:version")
    # Old version ki keys ab koi nahi access karega
    # Woh TTL expire hone tak RAM mein rahein (acceptable)

# Pattern powerful hai when: 
# - Invalidation signals unreliable hain
# - Atomic invalidation chahiye
```

### Strategy 4: Tag-Based Invalidation

```python
# Ek user ke saath related saari keys ek saath invalidate karo
# Without knowing exact key names

def tag_cache_key(key: str, tags: list):
    """Key ko tags ke saath store karo"""
    # Key store karo
    r.setex(key, 3600, "...")
    
    # Tags mein key add karo
    for tag in tags:
        r.sadd(f"tag:{tag}", key)
        r.expire(f"tag:{tag}", 86400)

def invalidate_by_tag(tag: str):
    """Is tag se related saari keys delete karo"""
    tag_key = f"tag:{tag}"
    keys = r.smembers(tag_key)
    
    if keys:
        pipe = r.pipeline()
        for key in keys:
            pipe.delete(key)
        pipe.delete(tag_key)
        pipe.execute()
        print(f"Invalidated {len(keys)} keys for tag:{tag}")

# Usage
tag_cache_key("user:1:profile", tags=["user:1", "users"])
tag_cache_key("user:1:orders", tags=["user:1", "orders"])
tag_cache_key("user:1:addresses", tags=["user:1"])

# Ek call mein user:1 ki saari cached data invalidate karo
invalidate_by_tag("user:1")  # Deletes profile, orders, addresses
```

### Strategy 5: Redis SCAN for Pattern-Based Invalidation

```python
# KEYS command dangerous hai (blocks Redis)
# SCAN use karo — non-blocking, iterative

def scan_and_delete(pattern: str):
    """Pattern match karke keys delete karo (production-safe)"""
    cursor = 0
    deleted_count = 0
    
    while True:
        cursor, keys = r.scan(cursor, match=pattern, count=100)
        
        if keys:
            pipe = r.pipeline()
            for key in keys:
                pipe.delete(key)
            pipe.execute()
            deleted_count += len(keys)
        
        if cursor == 0:  # Scan complete
            break
    
    print(f"Deleted {deleted_count} keys matching '{pattern}'")

# Usage: User 123 ki saari keys delete karo
scan_and_delete("user:123:*")
```

---

## 9. Multi-Layer Caching (L1 + L2 + L3)

### Concept

```
Request
   ↓
L1 Cache (In-process dict/cachetools) — 1-10 µs, per-process
   ↓ MISS
L2 Cache (Redis) — 100 µs - 1 ms, shared across instances
   ↓ MISS
L3 (Database) — 1ms - 100ms
   ↓ Result
(Store in L2 → Store in L1 → Return)
```

### Kyon Jaruri Hai Multi-Layer

Single process mein 10,000 requests/sec aa rahi hain:
- Without L1: 10,000 Redis calls/sec = significant network overhead
- With L1 (90% hit rate): sirf 1,000 Redis calls/sec = 10x improvement

### Python Implementation

```python
from cachetools import TTLCache
import threading
import json
import redis

class MultiLayerCache:
    """
    L1: In-process TTLCache (microseconds)
    L2: Redis (milliseconds)
    L3: Database (milliseconds - seconds)
    """
    
    def __init__(self, l1_maxsize: int = 500, l1_ttl: int = 10,
                 l2_ttl: int = 300, redis_client=None):
        # L1: In-process cache (very fast, limited size, per-process)
        self._l1 = TTLCache(maxsize=l1_maxsize, ttl=l1_ttl)
        self._l1_lock = threading.RLock()
        
        # L2: Redis (shared across all app instances)
        self._l2 = redis_client or redis.Redis(decode_responses=True)
        self._l2_ttl = l2_ttl
        
        # Stats
        self.stats = {"l1_hits": 0, "l2_hits": 0, "db_hits": 0}
    
    def get(self, key: str, db_loader: callable = None, *loader_args):
        # L1 check
        with self._l1_lock:
            if key in self._l1:
                self.stats["l1_hits"] += 1
                return self._l1[key], "L1"
        
        # L2 check (Redis)
        l2_val = self._l2.get(key)
        if l2_val:
            value = json.loads(l2_val)
            # Promote to L1
            with self._l1_lock:
                self._l1[key] = value
            self.stats["l2_hits"] += 1
            return value, "L2"
        
        # DB fallback
        if db_loader:
            value = db_loader(*loader_args)
            if value:
                self.set(key, value)
            self.stats["db_hits"] += 1
            return value, "DB"
        
        return None, "MISS"
    
    def set(self, key: str, value: any, l1_ttl: int = None):
        # Both layers mein store karo
        with self._l1_lock:
            self._l1[key] = value
        self._l2.setex(key, self._l2_ttl, json.dumps(value))
    
    def invalidate(self, key: str):
        # Dono layers se delete karo
        with self._l1_lock:
            self._l1.pop(key, None)
        self._l2.delete(key)
    
    def hit_rate_summary(self) -> dict:
        total = sum(self.stats.values())
        return {
            "l1_hit_rate": self.stats["l1_hits"] / total if total else 0,
            "l2_hit_rate": self.stats["l2_hits"] / total if total else 0,
            "db_hit_rate": self.stats["db_hits"] / total if total else 0,
            "total_requests": total
        }

# Usage
cache = MultiLayerCache(l1_maxsize=1000, l1_ttl=5, l2_ttl=300)

def get_product(product_id: int):
    value, source = cache.get(
        key=f"product:{product_id}",
        db_loader=lambda pid: db.get_product(pid),
        product_id
    )
    print(f"product:{product_id} from {source}")
    return value
```

### L1 Invalidation Challenge in Multi-Instance

```
Problem:
- 3 instances chal rahi hain (3 pods)
- User profile update hota hai
- Instance 1 Redis (L2) mein delete karta hai
- Instance 2 aur 3 ke L1 cache mein purana data rehta hai!

Solutions:
1. Short L1 TTL (10-30s) — stale data eventually expires
2. Pub/Sub invalidation:
   - Update karo → Redis PUBLISH "invalidation:user:123"
   - All instances SUBSCRIBE → message aya → L1 delete karo
3. Cache tagging — version-based approach

Redis Pub/Sub Invalidation:
```

```python
import redis
import threading

r_pubsub = redis.Redis(decode_responses=True)

class PubSubInvalidatedL1:
    def __init__(self):
        self._l1 = {}
        self._l1_lock = threading.Lock()
        
        # Subscribe to invalidation channel
        self._pubsub = r_pubsub.pubsub()
        self._pubsub.subscribe(**{"cache:invalidate": self._on_invalidation})
        
        # Listener thread
        self._listener = threading.Thread(
            target=self._pubsub.run_in_thread,
            kwargs={"sleep_time": 0.1},
            daemon=True
        )
        self._listener.start()
    
    def _on_invalidation(self, message):
        """Kisi bhi instance ne invalidate kiya → L1 se delete karo"""
        key = message.get('data')
        if key:
            with self._l1_lock:
                self._l1.pop(key, None)
            print(f"  [PubSub] L1 invalidated: {key}")
    
    def invalidate(self, key: str):
        """Invalidate karo aur saare instances ko broadcast karo"""
        with self._l1_lock:
            self._l1.pop(key, None)
        r_pubsub.publish("cache:invalidate", key)
```

---

## 10. Local Cache Libraries

### 1. `functools.lru_cache` — Built-in, Zero Dependencies

```python
from functools import lru_cache, cache
import time

# LRU Cache: Least Recently Used eviction
@lru_cache(maxsize=128)  # 128 items tak store karo, phir LRU evict
def get_config(env: str) -> dict:
    """Config bahut rarely change hoti — long-lived cache perfect hai"""
    time.sleep(0.1)  # DB/file read simulate
    return {"env": env, "debug": env == "dev"}

# Python 3.9+ — Unbounded cache (maxsize=None)
@cache
def fibonacci(n: int) -> int:
    if n < 2: return n
    return fibonacci(n-1) + fibonacci(n-2)

# Cache info check karo
get_config("prod")
get_config("dev")
get_config("prod")  # hit

print(get_config.cache_info())
# CacheInfo(hits=1, misses=2, maxsize=128, currsize=2)

# Cache clear karo (e.g., config reload par)
get_config.cache_clear()

# IMPORTANT: lru_cache is NOT TTL-based!
# Arguments hashable hone chahiye (dict/list allowed nahi)
# Thread-safe hai Python 3.2+
```

### 2. `cachetools` — Rich Local Cache Options

```python
from cachetools import TTLCache, LRUCache, LFUCache, cached
import threading

# TTLCache — time-based expiry ke saath
ttl_cache = TTLCache(maxsize=1000, ttl=300)  # 5 min TTL

# LRUCache — Least Recently Used eviction
lru_cache = LRUCache(maxsize=500)

# LFUCache — Least Frequently Used eviction (better for popularity-based)
lfu_cache = LFUCache(maxsize=500)

# Thread-safe caching decorator
_user_cache = TTLCache(maxsize=200, ttl=60)
_user_lock = threading.Lock()

@cached(cache=_user_cache, lock=_user_lock)
def get_user_profile(user_id: int) -> dict:
    return db.fetch_user(user_id)

# LRU vs LFU kab use karein:
# LRU: Recency matters (recently accessed likely to be accessed again)
#      Use: Web sessions, recent documents
# LFU: Frequency matters (popular items should stay)
#      Use: Product catalog, popular articles, config values
# TTL: Time-based freshness matters
#      Use: API responses, DB queries with known staleness requirement
```

### 3. `diskcache` — Persistent Local Cache

```python
import diskcache as dc

# Persistent cache — process restart par bhi data rahega
cache = dc.Cache('/tmp/my_cache')

# TTL ke saath set karo
cache.set('user:1', {"name": "Alice"}, expire=3600)

# Get
user = cache.get('user:1')

# Context manager
with dc.Cache('/tmp/cache') as cache:
    result = cache.get('expensive_query')
    if result is None:
        result = run_expensive_query()
        cache.set('expensive_query', result, expire=300)

# FanoutCache — multiple directories (sharded, faster concurrent access)
fanout = dc.FanoutCache('/tmp/fanout', shards=8)

# Use: 
# - ML model outputs cache (large, expensive to recompute)
# - Test fixtures
# - Offline-capable applications
```

---

## 11. Distributed Cache with Redis

### Cache Key Design — Production Naming Convention

```
Format: {service}:{resource}:{identifier}:{version?}

Examples:
user-service:user:123                → User 123 ka profile
user-service:user:123:permissions    → User 123 ki permissions
order-service:order:456              → Order 456
search-service:results:hash:{query_hash}  → Search results
product-service:product:789:price    → Product 789 ki price
leaderboard-service:global:top100    → Global top 100 players

Rules:
1. Lowercase
2. Colon separator (Redis convention)
3. Service prefix (namespace isolation)
4. ID before attribute
5. Version suffix (agar versioning chahiye)

Anti-patterns:
❌ "user_data_123"         → Underscore, no namespace
❌ "User:Profile:123"      → Mixed case
❌ "u:123"                  → Cryptic abbreviation
❌ "cache:user:name:email:age:123"  → Too many attributes in key
```

### Namespace Isolation

```python
class NamespacedRedisCache:
    """Service isolation with namespace prefix"""
    
    def __init__(self, namespace: str, redis_client):
        self._ns = namespace
        self._r = redis_client
    
    def _key(self, key: str) -> str:
        return f"{self._ns}:{key}"
    
    def get(self, key: str): 
        return self._r.get(self._key(key))
    
    def set(self, key: str, value: str, ttl: int = 300):
        self._r.setex(self._key(key), ttl, value)
    
    def delete(self, key: str):
        self._r.delete(self._key(key))
    
    def flush_namespace(self):
        """Namespace ki saari keys delete karo (production mein careful)"""
        pattern = f"{self._ns}:*"
        cursor = 0
        while True:
            cursor, keys = self._r.scan(cursor, match=pattern, count=200)
            if keys:
                self._r.delete(*keys)
            if cursor == 0:
                break

# Har service ka apna namespace
user_cache = NamespacedRedisCache("user-svc", redis_client)
order_cache = NamespacedRedisCache("order-svc", redis_client)
```

### Redis Cluster — Consistent Hashing

```python
# Redis Cluster: Data 16,384 hash slots mein distribute hota hai
# Key → CRC16(key) % 16384 → Slot → Node

# Hash Tags: Related keys same node par force karo
# {user:123}:profile  aur  {user:123}:orders
# Both will go to same slot (only {user:123} is hashed)

r.set("{user:123}:profile", profile_data)
r.set("{user:123}:orders", orders_data)
# Ab dono same Redis node par hain → atomic operations possible

from redis.cluster import RedisCluster

cluster = RedisCluster(
    startup_nodes=[
        {"host": "redis-node-1", "port": 7000},
        {"host": "redis-node-2", "port": 7001},
        {"host": "redis-node-3", "port": 7002},
    ],
    decode_responses=True
)

# Cluster MGET — keys different slots mein ho sakti hain
# RedisCluster handle karta hai automatically
values = cluster.mget(["user:1", "user:2", "user:3"])
```

### Connection Pooling

```python
import redis

# Production mein hamesha connection pool use karo
pool = redis.ConnectionPool(
    host='localhost',
    port=6379,
    db=0,
    max_connections=50,      # Maximum connections
    decode_responses=True,
    socket_connect_timeout=2,  # 2s connection timeout
    socket_timeout=1,           # 1s read/write timeout
    retry_on_timeout=True,
    health_check_interval=30   # 30s health check
)

r = redis.Redis(connection_pool=pool)

# Async Redis (FastAPI ke liye)
import aioredis

redis_pool = aioredis.ConnectionPool.from_url(
    "redis://localhost:6379",
    max_connections=100,
    decode_responses=True
)

async def get_redis():
    return aioredis.Redis(connection_pool=redis_pool)
```

---

## 12. Cache Warm-Up Strategies

### Problem

Naya server deploy hota hai → Cache empty → Pehli wave of requests DB par aati hai → Latency spike.

### Strategy 1: Pre-deployment Warm-Up Script

```python
async def warm_up_cache(batch_size: int = 100, delay: float = 0.01):
    """
    Deployment se pehle popular keys cache mein laao.
    Rate-limited taaki DB par spike na aaye.
    """
    print("Starting cache warm-up...")
    
    # Top accessed items (analytics se)
    popular_product_ids = await analytics.get_top_products(limit=5000)
    popular_user_ids = await analytics.get_active_users(days=7, limit=10000)
    
    # Batch warm-up with rate limiting
    for i in range(0, len(popular_product_ids), batch_size):
        batch = popular_product_ids[i:i+batch_size]
        
        # Parallel fetch from DB
        products = await asyncio.gather(*[
            db.get_product(pid) for pid in batch
        ])
        
        # Cache mein store karo
        pipe = redis.pipeline()
        for product in products:
            if product:
                pipe.setex(f"product:{product['id']}", 3600, json.dumps(product))
        await pipe.execute()
        
        # Rate limit: 100 items/10ms = 10,000 items/sec max
        await asyncio.sleep(delay)
        
        if i % 1000 == 0:
            print(f"Warmed up {i}/{len(popular_product_ids)} products")
    
    print("Cache warm-up complete")
```

### Strategy 2: Traffic Shadow / Canary Warm-Up

```
1. Naya instance deploy karo
2. 5% traffic naye instance par route karo (canary)
3. Cache gradually warm ho jaata hai
4. Hit rate > 70% hone par full traffic shift karo

Kubernetes: Traffic split with Istio/Nginx ingress
```

### Strategy 3: Cache Hit Rate Monitoring with Prometheus

```python
from prometheus_client import Counter, Histogram, Gauge, start_http_server

# Metrics define karo
cache_hits_total = Counter(
    'cache_hits_total',
    'Total cache hits',
    ['cache_layer', 'key_prefix']
)
cache_misses_total = Counter(
    'cache_misses_total', 
    'Total cache misses',
    ['cache_layer', 'key_prefix']
)
cache_hit_rate = Gauge(
    'cache_hit_rate',
    'Cache hit rate percentage',
    ['cache_layer']
)

class MonitoredCache:
    def __init__(self, layer_name: str):
        self._cache = {}
        self._layer = layer_name
        self._hits = 0
        self._misses = 0
    
    def get(self, key: str):
        prefix = key.split(':')[0]
        val = self._cache.get(key)
        
        if val is not None:
            self._hits += 1
            cache_hits_total.labels(cache_layer=self._layer, key_prefix=prefix).inc()
        else:
            self._misses += 1
            cache_misses_total.labels(cache_layer=self._layer, key_prefix=prefix).inc()
        
        total = self._hits + self._misses
        if total > 0:
            cache_hit_rate.labels(cache_layer=self._layer).set(
                self._hits / total * 100
            )
        
        return val

# Grafana dashboard mein dekhne layak metrics:
# cache_hit_rate{cache_layer="redis"} > 80 → Good
# cache_hit_rate{cache_layer="redis"} < 60 → Alert!
```

---

## 13. Semantic Cache (LLMs ke Liye)

### Concept

Traditional cache: **Exact key match** chahiye
Semantic cache: **Meaning/intent match** karo

```
Traditional: "What is Python?" aur "What is Python programming language?"
→ Different keys → 2 cache misses

Semantic: "What is Python?" aur "Tell me about Python language"
→ Similar embeddings → 1 cache hit (same meaning!)
```

### Implementation with Redis Vector Search

```python
import numpy as np
from typing import Optional

# Pseudocode (actual implementation in Phase3_LLM section)
class SemanticCache:
    def __init__(self, embedding_fn, similarity_threshold: float = 0.95):
        self._embedding_fn = embedding_fn  # e.g., OpenAI embeddings
        self._threshold = similarity_threshold
        self._entries = []  # (embedding, response) pairs
        # In production: Redis with Vector Search (VSS)
    
    def get(self, query: str) -> Optional[str]:
        query_embedding = self._embedding_fn(query)
        
        for stored_embedding, response in self._entries:
            similarity = cosine_similarity(query_embedding, stored_embedding)
            if similarity >= self._threshold:
                print(f"Semantic cache HIT (similarity: {similarity:.3f})")
                return response
        
        return None
    
    def set(self, query: str, response: str):
        embedding = self._embedding_fn(query)
        self._entries.append((embedding, response))

# Real-world solutions:
# 1. GPTCache: https://github.com/zilliztech/GPTCache
# 2. Redis Semantic Cache (LangChain integration)
# 3. Qdrant/Weaviate for vector storage
```

### Production: Redis Vector Search

```python
# Redis mein vector store karo (RedisVL library)
# from redisvl.index import SearchIndex
# from redisvl.query import VectorQuery

# Schema define karo
schema = {
    "index": {"name": "semantic_cache", "prefix": "llm_cache"},
    "fields": [
        {"name": "question", "type": "text"},
        {"name": "answer", "type": "text"},
        {"name": "embedding", "type": "vector", 
         "attrs": {"dims": 1536, "algorithm": "hnsw", "metric": "cosine"}}
    ]
}
# Detailed implementation Phase3_LLM section mein hai
```

---

## 14. Cache in FastAPI

### `@lru_cache` for Settings / Config

```python
from functools import lru_cache
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    redis_url: str
    secret_key: str
    debug: bool = False
    
    class Config:
        env_file = ".env"

@lru_cache()  # Ek baar load, process lifetime mein same object return
def get_settings() -> Settings:
    return Settings()

# FastAPI dependency injection
from fastapi import Depends

def some_endpoint(settings: Settings = Depends(get_settings)):
    # settings object hamesha same instance hoga (cached)
    return {"db_url": settings.database_url}
```

### Async Redis Cache as FastAPI Dependency

```python
from fastapi import FastAPI, Depends, HTTPException
import aioredis
import json
from typing import Optional

app = FastAPI()

# Startup par Redis connection pool create karo
@app.on_event("startup")
async def startup_event():
    app.state.redis = await aioredis.create_redis_pool("redis://localhost")

@app.on_event("shutdown")
async def shutdown_event():
    app.state.redis.close()
    await app.state.redis.wait_closed()

# Dependency: Redis instance
async def get_redis(request: Request) -> aioredis.Redis:
    return request.app.state.redis

# Endpoint with caching
@app.get("/users/{user_id}")
async def get_user(
    user_id: int,
    redis: aioredis.Redis = Depends(get_redis)
):
    cache_key = f"user:{user_id}"
    
    # Cache check
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # DB fetch
    user = await db.fetch_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Cache store
    await redis.setex(cache_key, 300, json.dumps(user))
    return user
```

### `aiocache` — Async Cache Decorator

```python
from aiocache import cached, Cache
from aiocache.serializers import JsonSerializer

@cached(
    ttl=300,
    cache=Cache.REDIS,
    serializer=JsonSerializer(),
    endpoint="localhost",
    port=6379,
    key_builder=lambda fn, *args, **kwargs: f"user:{args[0]}"
)
async def get_user_cached(user_id: int) -> dict:
    return await db.fetch_user(user_id)

# Invalidation
from aiocache import caches

async def update_user(user_id: int, data: dict):
    await db.update_user(user_id, data)
    cache = caches.get("default")
    await cache.delete(f"user:{user_id}")
```

### HTTP Caching Headers (Brief)

```python
from fastapi import Response
from fastapi.responses import JSONResponse

@app.get("/products/{product_id}")
async def get_product(product_id: int, response: Response):
    product = await get_product_cached(product_id)
    
    # Cache-Control header: Browser/CDN ko batao kitni der cache karo
    response.headers["Cache-Control"] = "public, max-age=300"  # 5 min
    
    # ETag: Conditional requests ke liye
    etag = f'"{hash(json.dumps(product, sort_keys=True))}"'
    response.headers["ETag"] = etag
    
    return product

# ETag validation
@app.get("/products/{product_id}")
async def get_product_conditional(
    product_id: int,
    request: Request,
    response: Response
):
    product = await get_product_cached(product_id)
    etag = f'"{hash(json.dumps(product, sort_keys=True))}"'
    
    if request.headers.get("If-None-Match") == etag:
        # Browser ke paas already fresh data hai
        return Response(status_code=304)  # Not Modified
    
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "public, max-age=60"
    return product
```

---

## 15. Interview Q&A (12 Questions)

### Q1: Cache-Aside vs Read-Through — Kya Fark Hai?

**Answer**:

**Cache-Aside (Lazy Loading)**:
- Application khud cache miss handle karta hai
- App → Cache (miss) → App → DB → App stores in Cache → App returns data
- Pros: Cache failure tolerant (app directly DB se kaam kar sakta hai), only requested data cached
- Cons: First request slow, potential stale data

**Read-Through**:
- Cache khud DB se data laata hai
- App → Cache (miss) → Cache → DB → Cache stores → Cache returns to App
- Pros: App logic clean (DB access hidden), consistent caching logic
- Cons: Cache failure = full outage, always goes through cache layer

**Kab kaunsa?**: Cache-Aside: jab multiple heterogeneous data sources ho ya cache failure tolerance chahiye. Read-Through: jab single DB source ho aur clean abstraction chahiye.

---

### Q2: Write-Through vs Write-Behind — Trade-offs Kya Hain?

**Answer**:

| Aspect | Write-Through | Write-Behind |
|---|---|---|
| Write Speed | Slow (2 writes synchronous) | Fast (only cache write, sync) |
| Consistency | Strong (cache always fresh) | Eventual (DB update delayed) |
| Data Loss Risk | None | Yes (cache crash = lost writes) |
| Complexity | Simple | Complex (flush queue, WAL) |
| Use Case | Read-heavy, strong consistency | Write-heavy, speed critical |

Write-Through: User profile updates, financial data
Write-Behind: View counters, analytics, game scores, likes

---

### Q3: Thundering Herd Problem Ko Kaise Solve Karoge?

**Answer**: Teen solutions hain:

1. **Mutex Lock**: Popular key expire hone par sirf ek request DB se fetch kare, baaki wait karein. Redis `SET NX EX` use karo distributed lock ke liye. Problem: Lock contention, timeout handling complex.

2. **Probabilistic Early Expiration (XFetch)**: TTL expire hone se pehle probabilistically refresh karo. High traffic keys automatically refresh hoti hain. No locks needed. Most elegant solution.

3. **Stale-While-Revalidate**: Expired data user ko de do (fast!), background mein refresh karo. User ko latency nahi dikti, DB par gradual load padta hai.

Production mein main XFetch ya SWR use karta hoon — lockless aur simpler.

---

### Q4: Cache Invalidation Sabse Hard Problem Kyon Hai?

**Answer**:

Cache invalidation hard hai kyunki ek **distributed consistency problem** hai:

1. **Multiple cache nodes**: 3 Redis replicas hain — sab invalidate karna chahoge
2. **Multiple app instances**: Har instance ka in-process L1 cache hai — L1 invalidation sirf local hai
3. **Race conditions**: Update aur read simultaneously ho sakte hain — window of stale data
4. **Cascade invalidation**: User update hone par user profile, user orders, user recommendations — sab invalidate?
5. **Partial failure**: Cache invalidated, DB update failed → cache mein stale/missing data

Solutions hierarchy:
- Simple: Short TTL (accept some staleness)
- Medium: Event-based invalidation (DB triggers)
- Complex: Version keys (increment version, old keys auto-stale)
- Advanced: Tag-based + Pub/Sub broadcast for L1 invalidation

"There are only two hard things in CS: cache invalidation and naming things" — Phil Karlton

---

### Q5: TTL Best Practice Kya Hai?

**Answer**:

TTL set karne ke principles:

1. **Data change frequency se match karo**: Fast-changing data (stock price, inventory) → short TTL (30s). Slow-changing (user profile) → long TTL (1h).

2. **Cost of stale data**: Financial data stale = loss → TTL bahut short ya no cache. Product description stale = minor UX issue → long TTL okay.

3. **Jitter add karo**: `ttl + random(0, ttl*0.1)` — mass expiry (thundering herd) prevent karo.

4. **Tiered TTL**: L1 (in-process) → 5-30s, L2 (Redis) → 5min-1hr, depends on data type.

5. **Monitor hit rate**: TTL too short → low hit rate. TTL too long → stale data complaints. Balance around 80-95% hit rate.

---

### Q6: Python Mein L1 vs L2 Cache Kya Hai?

**Answer**:

**L1 (In-process)**:
- `functools.lru_cache`, `cachetools.TTLCache`, simple dict
- Nanoseconds to microseconds (no network)
- Per-process: Multiple app instances mein shared nahi hota
- Memory limited by process RAM
- Use: Config, frequently computed values, hot data

**L2 (Distributed — Redis)**:
- Shared across all app instances
- 100µs-1ms (network round-trip)
- Centralized: Ek update sab instances ko milta hai
- Memory limited by Redis server
- Use: User sessions, shared data, distributed coordination

**Production strategy**: 2-tier — L1 (short TTL, small maxsize) + L2 (Redis). L1 mein hot data 5-10s cache. Cache miss → L2 check. L2 miss → DB. L1 ko L2 hit par populate karo.

---

### Q7: LRU vs LFU vs TTL — Kab Kaunsa?

**Answer**:

**LRU (Least Recently Used)**:
- Haal hi mein access na hua item evict karo
- Assumption: Recently accessed items will be accessed again
- Best for: Web sessions, recent documents, temporal locality
- Problem: Single large scan can evict all useful items

**LFU (Least Frequently Used)**:
- Sabse kam frequently accessed item evict karo
- Assumption: Popular items stay popular
- Best for: Product catalog, news articles, API responses
- Problem: New items get evicted before they can build frequency count

**TTL (Time-To-Live)**:
- Fixed time ke baad expire karo regardless of access
- Best for: Data freshness matters more than eviction strategy
- Database query results, external API responses

**Hybrid (Most Production Systems)**:
- LRU/LFU + TTL dono use karo
- `cachetools.TTLCache` = LRU + TTL

---

### Q8: Redis Key Naming Convention Kya Use Karte Ho?

**Answer**:

Convention: `{service}:{resource}:{id}:{attribute?}`

```
user-svc:user:123                 → User profile
user-svc:user:123:perms           → User permissions
order-svc:order:456               → Order data  
search-svc:results:{query_hash}   → Search results
rate-limiter:user:123:hour        → Rate limit counter
session:token:{session_id}        → Session data
```

Rules:
1. Lowercase, colon-separated
2. Service prefix for namespace isolation
3. Resource type before ID
4. Specific attribute last
5. Hash long values (query strings) — key max 512MB but best practice < 100 bytes
6. Version suffix agar version-based invalidation: `user-svc:user:123:v5`

Anti-patterns: No dots or spaces, no camelCase, no generic names like "data" or "cache"

---

### Q9: Cache Stampede Prevention Explain Karo

(Already covered in Q3 — add detail)

**Additional detail**: 

Redis mein lock implement karne ka exact code:

```python
lock_acquired = redis.set(
    "lock:hot_key",
    unique_id,    # Sirf apna lock release karo
    nx=True,      # Only set if not exists
    ex=5          # 5 second timeout (deadlock prevent)
)
```

Lock release safe tarike se:

```python
# WRONG: delete karne se pehle check nahi kiya — race condition!
redis.delete("lock:hot_key")

# CORRECT: Lua script for atomic check-then-delete
lua_script = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""
redis.eval(lua_script, 1, "lock:hot_key", unique_id)
```

---

### Q10: Kab Cache Use NAHI Karna Chahiye?

**Answer**:

1. **Real-time financial data**: Account balance, payment processing — stale data = financial loss
2. **Inventory management**: Oversell ho sakta hai agar cache stale ho
3. **Unique, low-frequency queries**: `SELECT * WHERE created_at BETWEEN X AND Y` — billions of variations, no reuse
4. **Very low traffic**: < 100 RPS → DB handles it fine, caching adds complexity
5. **Privacy-sensitive data**: PII, medical records — caching creates extra exposure surface
6. **Data that changes every request**: One-time tokens, CSRF tokens, OTP
7. **Already cached at another layer**: CDN already cache kar raha hai → app-level caching redundant

Rule of thumb: "Cache complexity ka cost justify karo performance gain se"

---

### Q11: Stale-While-Revalidate Pattern Kya Hai?

**Answer**:

HTTP caching concept jo application-level cache mein bhi apply hota hai:

- **Stale threshold**: 60 seconds — fresh data
- **Stale-while-revalidate window**: 60-300 seconds — stale but serve it + background refresh
- **After 300 seconds**: Synchronous refresh required

```
User request at T=90s (entry was set at T=0, TTL=60s):
- Entry is stale (age > 60s) BUT within revalidate window (age < 300s)
- Action: Return stale data immediately + background refresh start karo
- User gets fast response, DB gets gradual load
```

Implementation:

```python
def swr_get(key, loader_fn, fresh_ttl=60, stale_ttl=300):
    entry = cache.get_with_metadata(key)  # (value, set_time)
    if not entry: return loader_fn()  # Sync fetch
    
    value, set_time = entry
    age = time.time() - set_time
    
    if age < fresh_ttl: return value  # Fresh
    if age < stale_ttl:
        background_refresh(key, loader_fn)  # Async
        return value  # Stale but fast
    
    return loader_fn()  # Too stale, sync fetch
```

CDN mein: `Cache-Control: max-age=60, stale-while-revalidate=240`

---

### Q12: Microservices Mein Cache Consistency Kaise Maintain Karein?

**Answer**:

Microservices mein cache consistency ek **distributed systems problem** hai:

**Problem**:
- Service A: User profile cache karta hai
- Service B: User ko update karta hai (DB change)
- Service A ka cache stale ho jaata hai

**Solutions**:

1. **Event-driven invalidation**: Service B Kafka/RabbitMQ par `user.updated` event publish karta hai → Service A subscribe karta hai → L2 (Redis) invalidate karta hai

2. **Short TTL + Accept Staleness**: Services agree karte hain ki 5 min purana data acceptable hai → simple, no coordination needed

3. **Cache-Busting via API Gateway**: User update hone par API Gateway sab services ka cache invalidate karta hai (central invalidation)

4. **CQRS + Event Sourcing**: Separate read model maintain karo → events se rebuild → cache always consistent with events

5. **Distributed Cache with TTL**: Sirf L2 (Redis) use karo, no L1 in-process → Update hone par sirf Redis mein invalidate karo → Sab instances automatically miss karenge next request par

Production recommendation: Event-driven invalidation (Kafka) + short TTL as safety net + Redis Pub/Sub for L1 invalidation across instances.

---

*End of Theory File — 01_caching_patterns.md*

*Next: Practical implementation — `practical/01_caching_patterns.py`*
