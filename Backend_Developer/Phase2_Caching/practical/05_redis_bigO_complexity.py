"""
============================================================
REDIS BIG-O COMPLEXITY — Practical
============================================================
Demonstrates:
1. Slow vs safe iteration patterns
2. SCAN family (SCAN, SSCAN, HSCAN, ZSCAN)
3. Pipelining vs sequential
4. UNLINK vs DEL
5. SLOWLOG analysis
6. MEMORY USAGE inspection
"""
import time


# ============================================================
# 1. SAFE ITERATION: SCAN
# ============================================================
SCAN_VS_KEYS = """
# ❌ DANGEROUS — blocks Redis O(N)
all_keys = redis.keys("user:*")          # if 10M keys → blocks for seconds!

# ✅ SAFE — non-blocking, cursor-based, O(1) per call
def safe_scan(pattern, count=1000):
    cursor = 0
    while True:
        cursor, batch = redis.scan(cursor, match=pattern, count=count)
        for key in batch:
            yield key
        if cursor == 0:
            break

for key in safe_scan("user:*"):
    process(key)

# Async version
async def async_scan(redis, pattern):
    cursor = 0
    while True:
        cursor, batch = await redis.scan(cursor, match=pattern, count=1000)
        for key in batch:
            yield key
        if cursor == 0:
            break
"""


# ============================================================
# 2. SSCAN / HSCAN / ZSCAN
# ============================================================
COLLECTION_SCAN = """
# Iterating large sets/hashes/sorted sets without blocking

# Set
cursor = 0
while True:
    cursor, members = redis.sscan("followers:42", cursor, count=1000)
    for m in members: process(m)
    if cursor == 0: break

# Hash
cursor = 0
while True:
    cursor, fields = redis.hscan("user:42", cursor, count=100)
    for field, value in fields.items(): process(field, value)
    if cursor == 0: break

# Sorted set (returns members WITH scores)
cursor = 0
while True:
    cursor, items = redis.zscan("leaderboard", cursor, count=100)
    for member, score in items: process(member, score)
    if cursor == 0: break
"""


# ============================================================
# 3. PIPELINING (Round-trip optimization)
# ============================================================
PIPELINE_DEMO = """
import redis
import time

r = redis.Redis()

# WITHOUT pipeline — 1000 round trips
start = time.perf_counter()
for i in range(1000):
    r.set(f"key:{i}", i)
print(f"Sequential: {time.perf_counter()-start:.2f}s")

# WITH pipeline — single round trip
start = time.perf_counter()
pipe = r.pipeline()
for i in range(1000):
    pipe.set(f"key:{i}", i)
pipe.execute()
print(f"Pipelined: {time.perf_counter()-start:.2f}s")

# Typical: 100x faster

# Pipeline with mixed commands
pipe = r.pipeline()
pipe.set("a", 1)
pipe.incr("a")
pipe.get("a")
pipe.zadd("scores", {"alice": 100})
results = pipe.execute()
# results = [True, 2, b'2', 1]

# Pipeline with transaction (MULTI/EXEC)
with r.pipeline(transaction=True) as pipe:
    pipe.watch("balance")               # optimistic locking
    balance = int(pipe.get("balance"))
    pipe.multi()
    pipe.set("balance", balance - 10)
    pipe.execute()                       # atomic
"""


# ============================================================
# 4. UNLINK vs DEL (Big collections)
# ============================================================
UNLINK_VS_DEL = """
# Imagine a hash with 10M fields, or a list with 10M items

# ❌ DEL — synchronous, blocks Redis
redis.delete("huge_collection")          # blocks for seconds!

# ✅ UNLINK — async, background deletion
redis.unlink("huge_collection")          # returns immediately

# Available since Redis 4.0
# Works on ANY key — large or small

# For DEL of normal keys, no difference. For huge keys, ALWAYS use UNLINK.
"""


# ============================================================
# 5. SLOWLOG (find slow commands)
# ============================================================
SLOWLOG_USAGE = """
# Configure: log commands taking > 10ms
redis.config_set("slowlog-log-slower-than", 10000)   # microseconds!
redis.config_set("slowlog-max-len", 1000)            # keep 1000 entries

# View slow commands
slow = redis.slowlog_get(20)
for entry in slow:
    print(f"  {entry['duration']/1000:.2f}ms  {' '.join(entry['command'])}")

# Reset
redis.slowlog_reset()

# In production: scrape via Prometheus exporter
# Alert: any command > 50ms is suspect
"""


# ============================================================
# 6. MEMORY USAGE — inspect per-key memory
# ============================================================
MEMORY_INSPECTION = """
# Per-key memory (bytes)
size = redis.memory_usage("myhash")
print(f"myhash uses {size} bytes")

# CLI: find biggest keys
# $ redis-cli --bigkeys --i 0.1
# Sampled X keys in the keyspace!
# Total: ...
# Biggest string found 'session:foo' has 50KB
# Biggest hash found 'user:42' has 12500 fields

# Memory stats overview
redis.memory_stats()
# Returns dict with: total.allocated, dataset.bytes, fragmentation, ...

# Memory used / max
info = redis.info('memory')
print(f"Used: {info['used_memory_human']}")
print(f"Max:  {info['maxmemory_human']}")
print(f"Fragmentation: {info['mem_fragmentation_ratio']:.2f}")
"""


# ============================================================
# 7. CHEAT SHEET — Commands by O complexity
# ============================================================
BIG_O_TABLE = """
================================================================
                 COMMAND COMPLEXITY CHEAT SHEET
================================================================

O(1) — SAFE
  GET, SET, DEL                          STRINGS
  INCR, DECR, INCRBY                     STRINGS
  HGET, HSET, HDEL, HEXISTS              HASHES
  HINCRBY, HLEN                          HASHES
  LPUSH, RPUSH, LPOP, RPOP, LLEN         LISTS
  SADD, SREM, SISMEMBER, SCARD           SETS
  EXISTS, EXPIRE, TTL, PERSIST           KEYS
  DBSIZE                                 SERVER

O(log N) — FAST
  ZADD, ZREM, ZSCORE                     SORTED SETS
  ZRANK, ZINCRBY                         SORTED SETS

O(N) — CAREFUL (N = elements involved)
  MGET, MSET                             N = number of keys
  HMGET, HMSET                           N = fields
  LRANGE                                 N = range size
  SUNION, SINTER, SDIFF                  N = total elements
  ZADD with N elements                   N inserts

O(N) — DANGER (N = entire collection)
  KEYS pattern                           ❌ NEVER in prod
  SMEMBERS                               ❌ huge sets
  HGETALL, HKEYS, HVALS                  ❌ huge hashes
  LRANGE 0 -1                            ❌ entire list
  ZRANGE 0 -1                            ❌ entire sorted set
  DEL huge_collection                    ❌ use UNLINK
  FLUSHDB / FLUSHALL                     ⚠️  use async option

REPLACE WITH (SCAN family — cursor-based, batched)
  KEYS pat       → SCAN cursor MATCH pat
  SMEMBERS k     → SSCAN k cursor
  HGETALL k      → HSCAN k cursor
  ZRANGE k 0 -1  → ZSCAN k cursor
================================================================
"""


# ============================================================
# 8. CONNECTION POOL BEST PRACTICES
# ============================================================
CONNECTION_POOL = """
import redis

# Connection pool (reuse connections, save TCP handshake)
pool = redis.ConnectionPool(
    host='localhost',
    port=6379,
    max_connections=50,
    decode_responses=True,
)
r = redis.Redis(connection_pool=pool)

# Async
import redis.asyncio as aredis
pool = aredis.ConnectionPool(host='localhost', max_connections=50)
r = aredis.Redis(connection_pool=pool)
"""


# ============================================================
# 9. CLUSTER GOTCHAS
# ============================================================
CLUSTER_GOTCHAS = """
# MGET across cluster — keys must be in same slot!

# ❌ FAILS: different slots
redis.mget("user:1", "session:2")

# ✅ WORKS: hash tag forces same slot
redis.mget("{user42}:profile", "{user42}:settings")
# Both hash to same slot via {user42}

# SCAN in cluster: iterate per-node
from redis.cluster import RedisCluster
rc = RedisCluster(host='node1', port=6379)
for node_key, keys in rc.scan_iter(match="user:*"):
    for key in keys:
        process(key)
"""


# ============================================================
# 10. PERFORMANCE COMPARISON BENCHMARK
# ============================================================
def demo_pipeline_speedup():
    """Demonstrates 100x speedup via pipelining (vs network latency)."""
    print("=" * 60)
    print("PIPELINE vs SEQUENTIAL")
    print("=" * 60)

    class FakeRedis:
        """Simulates network round-trip delay."""
        def __init__(self):
            self._store = {}

        def get(self, key):
            time.sleep(0.0001)   # 100µs network RTT
            return self._store.get(key)

        def set(self, key, val):
            time.sleep(0.0001)
            self._store[key] = val
            return True

        def pipeline_execute(self, ops):
            time.sleep(0.0001)   # one RTT for entire pipeline
            results = []
            for op, args in ops:
                if op == "set":
                    self._store[args[0]] = args[1]
                    results.append(True)
                elif op == "get":
                    results.append(self._store.get(args[0]))
            return results

    r = FakeRedis()
    N = 1000

    # Sequential
    start = time.perf_counter()
    for i in range(N):
        r.set(f"key:{i}", i)
    seq_time = time.perf_counter() - start

    # Pipelined
    start = time.perf_counter()
    ops = [("set", (f"key:{i}", i)) for i in range(N)]
    r.pipeline_execute(ops)
    pipe_time = time.perf_counter() - start

    print(f"  {N} SETs sequential : {seq_time*1000:.1f}ms")
    print(f"  {N} SETs pipelined  : {pipe_time*1000:.1f}ms")
    print(f"  Speedup            : {seq_time/pipe_time:.0f}x")


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    demo_pipeline_speedup()

    print("\n" + "=" * 60)
    print("REDIS COMMAND COMPLEXITY GUIDE")
    print("=" * 60)
    print(BIG_O_TABLE)

    print("\n--- SCAN vs KEYS ---")
    print(SCAN_VS_KEYS)
    print("\n--- COLLECTION SCANS ---")
    print(COLLECTION_SCAN)
    print("\n--- PIPELINE ---")
    print(PIPELINE_DEMO)
    print("\n--- UNLINK vs DEL ---")
    print(UNLINK_VS_DEL)
    print("\n--- SLOWLOG ---")
    print(SLOWLOG_USAGE)
    print("\n--- MEMORY INSPECTION ---")
    print(MEMORY_INSPECTION)
    print("\n--- CONNECTION POOL ---")
    print(CONNECTION_POOL)
    print("\n--- CLUSTER GOTCHAS ---")
    print(CLUSTER_GOTCHAS)
