# Hot Keys — Redis

## 1. What is a Hot Key?

A **hot key** is a single Redis key that receives a disproportionately high volume of read or write requests — enough to saturate the CPU or network of the single Redis node that owns it.

```
Normal traffic:           Hot key traffic:
key_A  →  100 req/s       key_A  →  500,000 req/s  ← one node bottleneck
key_B  →  150 req/s       key_B  →  80 req/s
key_C  →  90 req/s        key_C  →  70 req/s
```

In Redis Cluster, each key lives on exactly one node. If millions of requests hit the same key, only one node handles all of them — no automatic spreading.

**Common causes:**
- Celebrity / viral content (one post liked by millions simultaneously)
- Global config key read by every API request
- Leaderboard key for a trending game
- Single session token for a shared account

---

## 2. Why It's a Problem

```
Redis Cluster — 3 nodes:

Node A  ← 800,000 req/s  (hot key "trending_post:9999")
Node B  ← 12,000 req/s
Node C  ← 9,000 req/s

Node A: CPU 100%, network saturated, latency spikes → timeouts
Node B, C: mostly idle — cluster sharding doesn't help
```

Problems:
- Single node CPU/network saturated
- Latency spikes for ALL keys on that node (not just the hot key)
- Connection exhaustion on that node
- Cascading failures if the node OOMs or crashes

---

## 3. Detection

### redis-cli built-in hot key detection

```bash
# Requires maxmemory-policy != noeviction and LFU policy
redis-cli --hotkeys

# Or use MONITOR (CAREFUL — use only on dev/staging, adds latency to prod)
redis-cli MONITOR | head -100

# OBJECT FREQ — LFU access counter (requires LFU eviction policy)
OBJECT FREQ trending_post:9999
```

### Application-level detection

```python
import redis
from collections import Counter
import time

r = redis.Redis()
key_hits = Counter()

def get_with_tracking(key: str):
    key_hits[key] += 1
    # Log top 10 every minute
    if key_hits.total() % 10000 == 0:
        print("Top keys:", key_hits.most_common(10))
    return r.get(key)
```

### Slow log analysis

```bash
# Check commands taking > 10ms
CONFIG SET slowlog-log-slower-than 10000
SLOWLOG GET 25
```

---

## 4. Solutions

### Solution 1: Local In-Process Cache (Most Effective)

Add a small in-memory cache in the application layer. Hot keys are served from RAM without touching Redis at all.

```python
from cachetools import TTLCache
import redis

r = redis.Redis()
# Local cache: max 1000 keys, 5-second TTL
local_cache = TTLCache(maxsize=1000, ttl=5)

def get_post(post_id: int) -> dict:
    key = f"post:{post_id}"

    # L1: local in-process cache (no network call)
    if key in local_cache:
        return local_cache[key]

    # L2: Redis
    data = r.get(key)
    if data:
        result = json.loads(data)
        local_cache[key] = result   # populate L1
        return result

    # L3: DB
    result = db.fetch_post(post_id)
    r.setex(key, 300, json.dumps(result))
    local_cache[key] = result
    return result
```

**Trade-off:** Stale data up to local TTL seconds. Acceptable for non-critical data (post content) but not for inventory counts or balances.

### Solution 2: Key Replication / Read Replicas

Shard the hot key across N virtual copies. Each app instance reads from a random copy.

```python
import random

HOT_KEY_REPLICAS = 10

def set_hot_key(r, key: str, value: str, ttl: int):
    """Write to all replicas."""
    pipe = r.pipeline()
    for i in range(HOT_KEY_REPLICAS):
        pipe.setex(f"{key}:replica:{i}", ttl, value)
    pipe.execute()

def get_hot_key(r, key: str) -> str | None:
    """Read from a random replica — spreads load across 10 Redis nodes in cluster."""
    replica_idx = random.randint(0, HOT_KEY_REPLICAS - 1)
    return r.get(f"{key}:replica:{replica_idx}")
```

**Trade-off:** Invalidation must update all N replicas. Write amplification × N.

### Solution 3: Request Coalescing (Collapse Duplicate Requests)

When a key is missing, only ONE request goes to DB/Redis — others wait for that result.

```python
import asyncio

_inflight: dict[str, asyncio.Future] = {}

async def get_coalesced(key: str) -> str:
    if key in _inflight:
        return await _inflight[key]   # wait for the in-flight request

    future = asyncio.get_event_loop().create_future()
    _inflight[key] = future

    try:
        result = await fetch_from_redis_or_db(key)
        future.set_result(result)
        return result
    except Exception as e:
        future.set_exception(e)
        raise
    finally:
        _inflight.pop(key, None)
```

### Solution 4: Cache Warming Before Traffic

For predictable hot keys (scheduled events, product launches):

```python
async def warm_hot_keys():
    """Pre-populate cache before traffic spike."""
    trending = await db.get_trending_posts(limit=100)
    pipe = r.pipeline()
    for post in trending:
        pipe.setex(f"post:{post.id}", 3600, json.dumps(post.to_dict()))
    pipe.execute()
    print(f"Warmed {len(trending)} hot keys")

# Run before scheduled event
# celery beat task: warm_hot_keys.apply_async(countdown=300)  # 5 min before event
```

---

## 5. Combined Strategy (Production)

```
Request
   │
   ▼
Local TTLCache (5s TTL)    ← L1: zero network, handles hot key
   │ MISS
   ▼
Redis read replica         ← L2: distributed, fast
   │ MISS
   ▼
PostgreSQL                 ← L3: source of truth
   │
   ▼
Populate Redis + local
```

---

## 6. Interview Questions

**Q: Hot key kya hai? Kyon problem hai Redis Cluster mein?**
Ek key jo bahut zyada requests receive kare. Cluster mein har key ek node pe hoti hai — hot key ek node ko saturate kar deti hai baaki nodes idle rehti hain. Sharding help nahi karta.

**Q: Hot key detect kaise karo?**
`redis-cli --hotkeys` (LFU policy chahiye), MONITOR (dev only), application-level Counter, SLOWLOG analysis.

**Q: Best solution kya hai hot key ke liye?**
Local in-process TTLCache (cachetools) — network call hi nahi hoti. 5-second stale acceptable hai most cases mein. Real-time data (inventory, balance) ke liye key replication better hai.

**Q: Key replication mein invalidation kaise karo?**
Write pe saare N replicas update karo (pipeline se atomic). Ya short TTL rakho aur expiry pe auto-invalidate ho.

**Q: Hot key aur cache stampede mein kya fark hai?**
Hot key: existing popular key pe bahut requests (key exists, just overloaded).
Cache stampede: expired key pe thundering herd (key missing, sab DB pe jaate hain).
Dono alag problems, alag solutions.
