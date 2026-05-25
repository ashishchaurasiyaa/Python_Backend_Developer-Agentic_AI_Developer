# Redis Persistence & Memory Optimization

## Why It Matters

Redis = in-memory but persistence + memory tuning critical:
- **Persistence** → survive restart without data loss
- **Memory** → 80% of OPEX is RAM cost
- **Eviction** → graceful degradation when full

Senior interview: "Redis lost data after server reboot — debug." → AOF off or fsync misconfigured.

---

## Persistence

### RDB (Snapshot)

Periodic point-in-time snapshot to disk:

```conf
save 3600 1      # save if >= 1 key changed in 3600s
save 300 100     # OR >= 100 keys in 300s
save 60 10000    # OR >= 10000 in 60s

dbfilename dump.rdb
dir /var/lib/redis
rdbcompression yes
rdbchecksum yes
```

**Pros:** Compact single file, fast restart, good for backups.
**Cons:** Data loss between snapshots (up to save interval).

**Commands:**
- `SAVE` — synchronous (blocks Redis)
- `BGSAVE` — background (fork + write)
- `LASTSAVE` — timestamp of last successful save

### AOF (Append-Only File)

Logs every write command:

```conf
appendonly yes
appendfilename "appendonly.aof"

appendfsync everysec    # fsync once per second (default, balanced)
# appendfsync always    # fsync every write — safest, slowest
# appendfsync no        # OS decides (rare)
```

**Pros:** Minimal data loss (worst case 1s with `everysec`).
**Cons:** Larger file, slower restart, AOF rewrite needed periodically.

### Hybrid Persistence (Default Modern Redis)

```conf
aof-use-rdb-preamble yes
```

AOF rewrite starts with RDB snapshot, appends incremental commands. Fast restart + minimal data loss.

### AOF Rewrite

Compacts AOF by replaying current state:

```conf
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb
```

Or manually: `BGREWRITEAOF`.

### Fsync Policies

| Policy | Data Loss Worst Case | Performance |
|---|---|---|
| `always` | 0 | Slowest |
| `everysec` | 1 second | Recommended |
| `no` | Whenever OS flushes | Fastest |

For financial data: `always`. For caches: `no` or skip AOF entirely.

### When to Skip Persistence

Pure cache (data regeneratable): no persistence saves CPU, disk I/O.

```conf
save ""
appendonly no
```

---

## Memory Optimization

### Max Memory + Eviction Policies

```conf
maxmemory 4gb
maxmemory-policy allkeys-lru
```

**Policies:**

| Policy | Behavior |
|---|---|
| `noeviction` | Reject writes when full (default) |
| `allkeys-lru` | Evict least-recently-used (any key) |
| `allkeys-lfu` | Evict least-frequently-used |
| `allkeys-random` | Random eviction |
| `volatile-lru` | LRU among keys with TTL |
| `volatile-lfu` | LFU among keys with TTL |
| `volatile-random` | Random among keys with TTL |
| `volatile-ttl` | Shortest TTL first |

**Recommendation:**
- Cache only: `allkeys-lru` or `allkeys-lfu`
- Mixed (cache + critical): `volatile-lru` + set TTL on cache keys, no TTL on critical
- Critical data: `noeviction` (fail fast, monitor)

### Memory Inspection

```bash
INFO memory
# used_memory_human: 1.50G
# used_memory_rss_human: 1.62G
# mem_fragmentation_ratio: 1.08

MEMORY USAGE mykey               # bytes used by one key
MEMORY STATS                     # detailed breakdown
DEBUG OBJECT mykey               # internal info

# Top keys by size (use SCAN + MEMORY USAGE)
redis-cli --bigkeys
redis-cli --memkeys              # in-memory analysis
```

### Encoding Optimization

Redis uses compact encodings for small data:

```bash
OBJECT ENCODING mykey
# ziplist (small list)
# listpack (small list/hash/zset, Redis 7+)
# intset (small set of integers)
# hashtable (large hash)
# skiplist (large sorted set)
```

**Thresholds:**

```conf
hash-max-listpack-entries 128      # hash uses listpack if entries <= 128
hash-max-listpack-value 64

list-max-listpack-size -2           # -2 = 8kb max
list-max-listpack-entries 128

zset-max-listpack-entries 128
zset-max-listpack-value 64

set-max-listpack-entries 128         # Redis 7.2+
set-max-listpack-value 64
set-max-intset-entries 512
```

Tune thresholds higher → more compact but slower ops on large structures.

### Hash for Multi-Field Records (Memory Win)

```bash
# BAD: 10 separate keys for user fields
SET user:1:name "Alice"
SET user:1:email "a@b.com"
# ... 10 keys × 100 bytes overhead = 1KB just for keys


# GOOD: single hash
HSET user:1 name "Alice" email "a@b.com" age 30
# Single key, encoded as listpack → smaller
```

### Shared Integers (Redis Optimization)

Redis pre-allocates integers 0-9999 — references shared. So `SET counter 5000` is essentially free vs `SET counter 50000`.

### Compress at App Level

For large values, gzip before storing:

```python
import gzip, json


def cache_set(key, value, ttl=300):
    data = gzip.compress(json.dumps(value).encode(), compresslevel=6)
    r.set(key, data, ex=ttl)


def cache_get(key):
    data = r.get(key)
    if data:
        return json.loads(gzip.decompress(data))
    return None
```

### Memory Fragmentation

```bash
INFO memory | grep mem_fragmentation_ratio
# mem_fragmentation_ratio:1.5   # using 50% more RAM than data
```

Fragmentation > 1.5 = problem. Mitigation:
- `MEMORY PURGE` — release fragmented memory
- `CONFIG SET activedefrag yes` — automatic defrag (Redis 4+)
- Restart Redis (releases all memory)

### TTL Distribution Matters

```bash
# All keys expire at same minute → bursty eviction
EXPIRE key1 60
EXPIRE key2 60

# Better: randomize within bounds
EXPIRE key1 $((60 + RANDOM % 30))
```

---

## How It Works Internally

### RDB Process

```
1. BGSAVE forks child process
2. Child writes snapshot to temp file (copy-on-write)
3. Parent continues serving
4. On completion, child renames temp → dump.rdb
5. Memory peak: 2x during fork (worst case)
```

### AOF Rewrite

```
1. BGREWRITEAOF forks child
2. Child writes current dataset as commands to temp AOF
3. Parent buffers new commands during rewrite
4. On completion, parent appends buffered commands to new AOF
5. Atomic rename
```

### Eviction Algorithm (LRU Approximation)

Redis LRU = approximate. Samples N keys (`maxmemory-samples 5` default), evicts least-recent. Higher N = more accurate, slower. For LFU: tracks log(frequency).

---

## Common Pitfalls

### 1. AOF Disabled + Backup Only RDB

```
RDB snapshot every 5 min → up to 5 min data loss on crash
```

For critical data: AOF `everysec` + RDB for compact backups.

### 2. `noeviction` + No Monitoring

Redis full → all writes fail. App errors mysteriously. Set alert at 80% memory.

### 3. Fork Overhead on Big Datasets

```
BGSAVE on 100GB Redis → fork takes seconds, blocks
```

Use replicas — let replica do snapshots (`save 3600 1` on replica only).

### 4. Many Small Keys

```python
for i in range(1000000):
    r.set(f'item:{i}:value', '...')
# 1M keys × 100 bytes overhead = 100MB just for key storage
```

Use HASH instead:

```python
r.hset(f'batch:{i // 1000}', f'item:{i % 1000}', '...')
```

### 5. EXPIRE on Already-Expired Key Race

```python
r.set('key', 'value')
# ... key expires before next line
r.expire('key', 60)   # returns 0 (key doesn't exist)
```

Use `SET key value EX 60` for atomicity.

### 6. AOF Corrupted

If Redis crashes mid-write, AOF may have partial command. Recovery:

```bash
redis-check-aof --fix appendonly.aof
```

### 7. `KEYS *` in Production

Blocks Redis for huge datasets. Use SCAN:

```python
for k in r.scan_iter(match='user:*', count=100):
    ...
```

---

## Interview Q&A

**Q1:** RDB vs AOF — kab kya use?
**A:** RDB: periodic snapshots, compact, fast restart, but data loss between snapshots. AOF: every write logged, minimal data loss (1s with everysec), slower restart, larger file. Production: enable both — AOF for durability, RDB for fast restart + compact backups. Default modern: hybrid (RDB preamble in AOF).

**Q2:** AOF fsync policies trade-offs?
**A:** `always`: every write fsynced — zero data loss, slow (limited to disk IOPS). `everysec`: fsync once/sec — 1s data loss worst case, much faster (recommended). `no`: OS decides — fastest, up to 30s loss. Choose by durability requirement vs throughput.

**Q3:** maxmemory + noeviction kab choose karoge?
**A:** When all data critical and can't tolerate eviction (financial state, sessions). Risk: writes fail when full. Must monitor + scale before hitting limit. For cache (regeneratable): allkeys-lru. For mixed: volatile-lru + TTL on cache keys.

**Q4:** Memory optimization techniques?
**A:** (1) Use HASH for multi-field records (single key vs many). (2) Tune listpack/ziplist thresholds. (3) Compress large values (gzip). (4) Set TTL on cache data. (5) Use Redis 7+ listpacks (smaller than ziplist). (6) Shared integers for small ints. (7) Hyperloglog for cardinality (12KB regardless of unique count).

**Q5:** Memory fragmentation kya hota hai aur kaise solve?
**A:** Process RSS > used_memory due to allocator fragmentation. Common after many deletes/updates. Solve: `activedefrag yes` (auto), `MEMORY PURGE` (manual), restart (releases all). Fragmentation > 1.5 = investigate.

**Q6:** BGSAVE memory spike kyun hota hai?
**A:** Fork uses copy-on-write — initially no memory overhead. But as parent modifies pages during child's snapshot, those pages get copied → memory doubles in worst case. Mitigation: do BGSAVE on replica (no writes there), or schedule during low-traffic.

**Q7:** Eviction policy choose karne ka framework?
**A:** Cache only → `allkeys-lru` or `allkeys-lfu`. Cache + critical → `volatile-lru` with TTLs on cache keys. Critical only → `noeviction` + monitoring. LFU better than LRU when access pattern has hot keys (some keys very frequent).

**Q8:** Big keys detect kaise karoge?
**A:** `redis-cli --bigkeys` — samples + reports largest. Or SCAN + MEMORY USAGE per key in script. Or RedisInsight visual tool. Common big keys: huge lists (queue not consumed), large strings (uncompressed JSON), big sets/hashes (no sharding).

---

## Real-World Use Cases

### 1. Cache Layer Config

```conf
maxmemory 8gb
maxmemory-policy allkeys-lru
save ""               # no RDB
appendonly no         # no AOF
maxmemory-samples 10  # better LRU approximation
```

### 2. Session Store Config

```conf
maxmemory 4gb
maxmemory-policy volatile-lru
appendonly yes
appendfsync everysec
```

Sessions have TTL — volatile-lru evicts old. AOF for durability.

### 3. Critical State Config

```conf
maxmemory 16gb
maxmemory-policy noeviction
appendonly yes
appendfsync always
save 3600 1
save 300 100
```

Worst-case: writes fail. Alert at 70% → scale.

---

## References

- [Redis Persistence](https://redis.io/docs/management/persistence/)
- [Memory Optimization](https://redis.io/docs/management/optimization/memory-optimization/)
- [Eviction Policies](https://redis.io/docs/reference/eviction/)
- "Redis in Action" — Tuning chapter
