# Redis Failure Scenarios — Production Handling

## 1. Scenario: Redis Goes Down Completely

### What happens by default

```python
# Without any protection:
value = r.get("user:42")
# → redis.exceptions.ConnectionError: Error 111 connecting to localhost:6379
# → Unhandled exception → 500 to user → cascading failure
```

### Fix 1: Graceful degradation — fall through to DB

```python
import redis
import logging

log = logging.getLogger(__name__)

r = redis.Redis(socket_connect_timeout=1, socket_timeout=1)

def get_user(user_id: int) -> dict:
    key = f"user:{user_id}"
    try:
        cached = r.get(key)
        if cached:
            return json.loads(cached)
    except redis.RedisError as e:
        log.warning("Redis unavailable, falling back to DB: %s", e)
        # Fall through — do NOT raise here

    # DB fallback — always works even without Redis
    user = User.objects.get(pk=user_id)
    try:
        r.setex(key, 300, json.dumps(user.to_dict()))
    except redis.RedisError:
        pass  # can't cache — that's OK
    return user.to_dict()
```

### Fix 2: django-redis IGNORE_EXCEPTIONS

```python
# settings.py
"OPTIONS": {
    "IGNORE_EXCEPTIONS": True   # cache.get() returns None instead of raising
}
```

### Fix 3: Circuit Breaker Pattern

```python
import time

class RedisCircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=30):
        self.failures = 0
        self.threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.last_failure = 0.0
        self.open = False

    def get(self, r, key):
        if self.open:
            if time.time() - self.last_failure > self.recovery_timeout:
                self.open = False   # try again (half-open)
            else:
                return None  # fail fast — don't even attempt Redis

        try:
            result = r.get(key)
            self.failures = 0
            return result
        except redis.RedisError:
            self.failures += 1
            self.last_failure = time.time()
            if self.failures >= self.threshold:
                self.open = True
                log.error("Redis circuit breaker OPEN — failing fast")
            return None

cb = RedisCircuitBreaker()

def get_product(product_id):
    key = f"product:{product_id}"
    cached = cb.get(r, key)
    if cached:
        return json.loads(cached)
    return db.get_product(product_id)
```

---

## 2. Scenario: Redis Becomes Slow (High Latency)

### Detection

```bash
# Real-time latency monitoring
redis-cli --latency
redis-cli --latency-history    # latency over time

# Slow command log (commands taking > 10ms)
CONFIG SET slowlog-log-slower-than 10000   # microseconds
SLOWLOG GET 25
SLOWLOG LEN   # how many slow commands in log

# Response time from app
redis-cli PING   # should be < 1ms locally
```

### Common causes + fixes

```
Slow Redis?
    │
    ├── SLOWLOG shows slow commands?
    │       YES → Large key (SMEMBERS on 1M-member set) or O(N) command
    │           → Break up large keys, use SCAN instead of KEYS *
    │
    ├── High CPU on Redis server?
    │       YES → Too many connections, complex Lua scripts, SORT on large sets
    │           → Connection pooling, simplify scripts, add replicas for reads
    │
    ├── Network latency high?
    │       YES → Redis on different datacenter / region
    │           → Use pipeline to batch commands, reduce round trips
    │
    ├── Memory fragmentation high?
    │       → redis-cli INFO memory → mem_fragmentation_ratio > 1.5 is concerning
    │       → MEMORY PURGE (Redis 4+) to defragment
    │
    └── Persistence causing slowness?
            → BGSAVE / AOF rewrite adds I/O pressure
            → Check redis-cli INFO persistence → rdb_last_bgsave_status
            → Move persistence to replica, not primary
```

### Application-level timeout

```python
# Always set connection timeout in production
r = redis.Redis(
    host="redis-host",
    socket_connect_timeout=2,   # fail fast if can't connect
    socket_timeout=1,           # fail if command takes > 1s
    retry_on_timeout=True,
    retry=redis.retry.Retry(redis.backoff.ExponentialBackoff(), 3)
)
```

---

## 3. Scenario: Cache Corrupted / Wrong Data

### Detection

```bash
# Check key type
TYPE user:42
# → string (expected)

# Inspect value
GET user:42
# → "{invalid json" — corrupted!

# Check memory for anomalies
MEMORY USAGE user:42   # unusually large?
DEBUG OBJECT user:42   # encoding, serializedlength, lru_seconds_idle
```

### Fix: Versioned keys + forced re-hydration

```python
CACHE_VERSION = 2   # bump when data format changes

def get_user(user_id: int) -> dict:
    key = f"user:{user_id}:v{CACHE_VERSION}"
    try:
        cached = r.get(key)
        if cached:
            data = json.loads(cached)
            # Validate expected fields
            if "email" in data and "id" in data:
                return data
            # Corrupted — delete and re-fetch
            r.delete(key)
    except (redis.RedisError, json.JSONDecodeError):
        pass

    user = User.objects.get(pk=user_id)
    result = user.to_dict()
    r.setex(key, 300, json.dumps(result))
    return result
```

### Nuclear option: targeted flush (not FLUSHALL)

```bash
# Delete all keys matching pattern (use SCAN — never KEYS * in production)
redis-cli --scan --pattern "user:*:v1" | xargs redis-cli DEL

# Or from Python
for key in r.scan_iter("user:*:v1"):
    r.delete(key)
```

---

## 4. Scenario: Redis Memory Full

### What happens

```
maxmemory reached
        │
        ├── noeviction policy → SET commands return OOM error
        │       Application crashes / 500 errors
        │
        ├── allkeys-lru → evicts least-recently-used keys
        │       Cache miss rate spikes → DB load increases
        │
        └── volatile-lru → evicts LRU keys WITH TTL set
                Keys without TTL never evicted → potential memory leak
```

### Investigation steps

```bash
# 1. Check memory usage
INFO memory
# → used_memory_human: 14.5G
# → maxmemory_human: 16.0G
# → mem_fragmentation_ratio: 1.8   (high fragmentation!)

# 2. Find largest keys
redis-cli --bigkeys
# → Biggest string: "session:abc123" (2.1MB)
# → Biggest list: "event_log" (500,000 elements)

# 3. Check key count and TTLs
INFO keyspace
# → db0: keys=2500000, expires=800000   ← 1.7M keys with NO TTL!

# 4. Check eviction stats
INFO stats
# → evicted_keys: 150000   ← evictions happening
# → keyspace_hits: 8500000
# → keyspace_misses: 450000  ← hit ratio = 95% (acceptable)
```

### Fixes

```python
# Fix 1: Find and delete keys with no TTL
for key in r.scan_iter("*"):
    if r.ttl(key) == -1:   # -1 = no TTL set
        log.warning("Key with no TTL: %s", key)
        # Either set a TTL or delete if safe
        r.expire(key, 3600)  # retroactively add TTL

# Fix 2: Compress large values
import zlib, json

def cache_set_compressed(r, key, data, ttl=3600):
    serialized = json.dumps(data).encode()
    compressed = zlib.compress(serialized)
    r.setex(key, ttl, compressed)

def cache_get_compressed(r, key):
    raw = r.get(key)
    if raw:
        return json.loads(zlib.decompress(raw))
    return None

# Fix 3: Prevent large keys
MAX_CACHE_SIZE = 1024 * 100  # 100KB limit
def safe_cache_set(r, key, data, ttl=300):
    serialized = json.dumps(data)
    if len(serialized) > MAX_CACHE_SIZE:
        log.warning("Cache value too large for key %s (%d bytes) — skipping", key, len(serialized))
        return
    r.setex(key, ttl, serialized)
```

---

## 5. Scenario: Primary Fails — Sentinel Failover

```
Timeline:
T=0   Primary goes down (crash / OOM / network)
T=5s  Sentinel detects: no response to PING
T=10s Sentinel quorum reached: promote Replica-A to Primary
T=12s Clients get notified of new Primary address
T=15s Application reconnects to new Primary
T=30s Old primary comes back — now joins as Replica

Application impact: ~15–30 seconds of elevated errors / write failures
```

### Application must handle reconnection

```python
from redis.sentinel import Sentinel

sentinel = Sentinel(
    [("sentinel1", 26379), ("sentinel2", 26379), ("sentinel3", 26379)],
    socket_timeout=0.5
)

# Always get fresh master connection — Sentinel handles failover transparently
master = sentinel.master_for("mymaster", socket_timeout=0.5, decode_responses=True)
slave  = sentinel.slave_for("mymaster",  socket_timeout=0.5, decode_responses=True)

# After failover, sentinel.master_for() returns the NEW primary automatically
master.set("key", "value")   # works after failover
```

---

## 6. Scenario: Network Partition

```
Scenario: Redis primary can't reach replica — network split
    ├── Primary: still accepting writes (doesn't know it's isolated)
    ├── Sentinel (on replica side): promotes Replica to new Primary
    ├── Two primaries accepting writes: SPLIT-BRAIN
    └── When partition heals: old primary demoted → its writes LOST
```

### Mitigation

```python
# redis.conf on primary:
# min-replicas-to-write 1
# min-replicas-max-lag 10
# → If no replicas connected for 10s, primary STOPS accepting writes
# → Prevents split-brain at cost of availability
```

---

## 7. Production Monitoring Checklist

```bash
# Key metrics to alert on:

redis-cli INFO all | grep -E "
used_memory_human          # alert > 80% of maxmemory
mem_fragmentation_ratio    # alert > 1.5
connected_clients          # alert > 80% of maxclients
evicted_keys               # alert > 0 (any eviction is a warning)
keyspace_hits              # track hit ratio
keyspace_misses            # hit ratio = hits / (hits + misses)
rejected_connections       # alert > 0 (maxclients reached)
rdb_last_bgsave_status     # alert if 'err'
aof_last_rewrite_status    # alert if 'err'
replication lag            # INFO replication → master_repl_offset vs slave_repl_offset
"
```

---

## 8. Interview Questions

**Q: Redis down ho jaaye toh application pe kya effect hota hai?**
Default mein `ConnectionError` → unhandled exception → 500. Fix: try/except with DB fallback. `IGNORE_EXCEPTIONS: True` in django-redis. Circuit breaker for repeated failures.

**Q: Redis memory full ho jaaye toh kya hota hai?**
`noeviction` policy mein SET commands OOM error return karte hain. `allkeys-lru` mein least recently used keys evict hoti hain — cache miss rate badhti hai, DB load badhta hai. Fix: monitor evictions, `--bigkeys` se large keys dhundo, sabko TTL set karo.

**Q: Cache corrupted ho jaaye toh kaise handle karo?**
Versioned keys use karo — format change pe version bump. Read pe validation karo, invalid data pe delete + re-fetch. Targeted SCAN + DEL (kabhi FLUSHALL nahi production pe).

**Q: Sentinel failover ke dauran application kya experience karta hai?**
10–30 seconds ka write failure. Sentinel `master_for()` automatically new primary return karta hai after failover. Retry logic + connection timeout zaroori hai.

**Q: Split-brain kya hai? Redis mein kaise hota hai?**
Network partition pe agar sentinel replica ko promote kare aur purana primary bhi writes accept kare — do primaries, conflicting writes. `min-replicas-to-write` setting se prevent karte hain — primary writes band kar deta hai agar koi replica connected na ho.
