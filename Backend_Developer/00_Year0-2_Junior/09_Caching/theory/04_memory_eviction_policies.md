# Memory Eviction Policies (Redis)

> **Interview angle:** "Redis full ho gaya — kya hota hai jab next SET aata?"
>
> Answer: depends on `maxmemory-policy`. Wrong policy = wrong keys evicted.

---

## 1. The Problem

Redis stores everything in RAM. When `maxmemory` reached:
- Without eviction: SET commands fail with OOM
- With eviction: Redis removes some keys to make room

**Choosing the right policy = preserving useful data, evicting useless.**

---

## 2. The 8 Policies

| Policy | Algorithm | Scope |
|---|---|---|
| `noeviction` | Don't evict, fail writes | — |
| `allkeys-lru` | LRU | All keys |
| `allkeys-lfu` | LFU | All keys |
| `allkeys-random` | Random | All keys |
| `volatile-lru` | LRU | Keys with TTL only |
| `volatile-lfu` | LFU | Keys with TTL only |
| `volatile-random` | Random | Keys with TTL only |
| `volatile-ttl` | Earliest expiry first | Keys with TTL only |

### Config
```bash
# redis.conf
maxmemory 4gb
maxmemory-policy allkeys-lru

# Or runtime
CONFIG SET maxmemory-policy allkeys-lru
```

---

## 3. LRU vs LFU (Detailed)

### LRU (Least Recently Used)
Evict the key NOT accessed for longest time.
```
GET key_a  → key_a moves to "recent"
GET key_b  → key_b is recent
... time passes ...
key_a (not accessed) → evicted first
```

### LFU (Least Frequently Used)
Evict the key accessed FEWEST times.
```
key_a: accessed 100 times
key_b: accessed 5 times
... time passes ...
key_b → evicted first (lower frequency)
```

### When to use which?

| Workload | Best | Why |
|---|---|---|
| Recent activity matters | **LRU** | News feed, recently viewed |
| Popular items stay hot | **LFU** | Top products, trending |
| Mixed | LRU usually safer | Default choice |
| Unknown / random access | random | No locality |

### LFU subtleties (Redis-specific)
Redis LFU doesn't truly count forever. Uses **probabilistic counter** that:
- Increments on access (with decreasing probability as counter grows)
- **Decays over time** to give recency some weight
- Capped at 255

```bash
# Tune LFU behavior
lfu-log-factor 10      # higher = slower counter growth (default 10)
lfu-decay-time 1       # minutes for counter to decay by 1 (default 1)
```

---

## 4. `volatile-*` vs `allkeys-*`

`volatile-*` evicts only keys with TTL set. Keys without TTL are protected.

### Use case
```python
# Session keys: TTL 30 min → can be evicted
redis.setex(f"session:{user}", 1800, data)

# Critical state: no TTL → never evicted
redis.set("system:config", config)
```

With `volatile-lru`, system:config survives even under memory pressure.

### Gotcha
If NO keys have TTL set, `volatile-*` won't evict anything → OOM error.

---

## 5. Algorithm Details

### Approximate LRU
Redis doesn't track exact LRU for all keys (too expensive). Instead:
- Samples K random keys (`maxmemory-samples`, default 5)
- Evicts the least-recently-used among the sample

```bash
maxmemory-samples 10    # higher = better accuracy, slower
```

### Approximate LFU
Same idea — samples + probabilistic counter.

### Random
Picks random key — fastest, but no intelligence.

### volatile-ttl
Picks key closest to expiry. Useful when TTL itself encodes priority.

---

## 6. Eviction Workflow

```
INCOMING WRITE
  ↓
Memory used > maxmemory?
  ├── No → proceed
  └── Yes:
      ↓
      Apply eviction policy
      ├── noeviction → return error to client
      └── Evict 1+ keys until under threshold
          ↓
          Proceed with write
```

### Eviction is per-write
Each SET that needs space triggers eviction. Heavy writes → many evictions → CPU overhead.

---

## 7. Monitoring Evictions

```bash
INFO stats
# evicted_keys: 12345    ← total ever evicted
# expired_keys: 67890    ← keys that hit TTL
```

### Alert when
- `evicted_keys` rapidly growing
- `evicted_keys` per minute > threshold
- Cache hit rate dropping while evictions rising

### Memory inspection
```bash
INFO memory
# used_memory_human: 3.8G
# maxmemory_human: 4.0G
# used_memory_peak_human: 4.0G
# maxmemory_policy: allkeys-lru
# mem_fragmentation_ratio: 1.2
```

---

## 8. Decision Tree

```
Need to NEVER lose data?
├── Yes → noeviction + separate persistent store
└── No:
    ↓
    All keys equally important?
    ├── Yes → allkeys-lru
    └── No (some keys are "ephemeral"):
        ↓
        Set TTL on ephemeral keys
        Use volatile-lru
```

### Common workload mappings

| Workload | Recommended |
|---|---|
| HTTP page cache | `allkeys-lru` |
| Session storage (mixed with state) | `volatile-lru` |
| Top-N leaderboard | `allkeys-lfu` |
| Rate limit counters | `allkeys-lfu` |
| Pure cache, no critical data | `allkeys-lru` |
| Session-only Redis | `volatile-ttl` |

---

## 9. Pitfalls

### Pitfall 1: `noeviction` in production
Default in some configs. App tries to write → error 503. Not a cache!

### Pitfall 2: Setting `maxmemory` lower than dataset
Constant eviction = thrashing. Cache hit rate plummets.

### Pitfall 3: No TTL with `volatile-*`
Nothing to evict → OOM error on writes.

### Pitfall 4: Same key access pattern for all data
LRU + uniform access = essentially random. Misleading "intelligence."

### Pitfall 5: maxmemory-samples too low
Default 5 = quite approximate. Increase to 10-20 for better accuracy at small CPU cost.

---

## 10. Real-World Numbers

### Memory overhead
- Empty Redis: ~3 MB
- Per key overhead: ~80-100 bytes
- 1M keys with small values: ~150 MB just for metadata

### Eviction throughput
- Modern Redis on SSD: ~50K-100K evictions/sec
- Bottleneck is rarely eviction itself; it's memory allocation

---

## 11. Combining with Other Strategies

### TTL-based eviction (cheap natural eviction)
Set TTL on everything → Redis expires keys → no manual eviction needed.

### Cache classes
Separate Redis instances by purpose:
- `redis-sessions:` → volatile-ttl, short TTLs
- `redis-cache:` → allkeys-lru, longer TTLs
- `redis-rate-limit:` → allkeys-lfu, very short TTLs

### Hybrid
- L1 in-process: LRU (small, fast)
- L2 Redis: LRU (medium, shared)
- L3 DB: source of truth

See `07_multi_level_caching.md`.

---

## 12. Memory Optimization Tips

### Use small data structures
- Hashes pack better than top-level keys
- `HSET user:42 name "X" email "y"` is denser than `SET user:42:name`

### Compress large values
- `gzip` before SET if value > 1KB
- Trade CPU for memory

### Use hash-max-ziplist
Small hashes use compact encoding:
```bash
hash-max-listpack-entries 128   # if <=128 entries, use compact format
hash-max-listpack-value 64
```

### Expire generously
Don't keep stale data. TTLs = natural eviction.

---

## 13. Interview Questions

**Q1: maxmemory hit kya hota?**
Depends on policy. `noeviction` = writes fail. Others = evict + write.

**Q2: LRU vs LFU?**
LRU = recency. LFU = frequency. LFU better for popular-item caches.

**Q3: allkeys vs volatile?**
allkeys = evict any. volatile = only evict keys with TTL set.

**Q4: LRU exact ya approximate?**
Redis uses approximate LRU — samples N random keys per eviction. Trade accuracy for speed.

**Q5: LFU counter overflow?**
Redis uses logarithmic counter (max 255). Decays over time so old hot keys cool down.

**Q6: Eviction monitor kaise?**
`INFO stats` → `evicted_keys`. Alert if growing rapidly.

**Q7: maxmemory-samples ka effect?**
Higher = better choice (closer to true LRU/LFU), more CPU. Default 5 is OK; 10 better for memory-pressure scenarios.

---

## 14. Best Practices

1. **NEVER use noeviction** as cache (causes errors)
2. **Set explicit maxmemory** — don't rely on OS killing Redis
3. **Default: `allkeys-lru`** for most caches
4. **`allkeys-lfu`** for top-N / popular content
5. **TTL on all cache keys** — natural eviction
6. **Increase `maxmemory-samples`** to 10
7. **Monitor `evicted_keys`** — alert on rapid growth
8. **Separate Redis** by purpose (sessions vs cache vs locks)
9. **Hash structures** for related data (memory efficient)
10. **Compress large values** if memory tight

---

## Related
- [[../../00_Year0-2_Junior/08_Redis/theory/01_basics_installation_cli]]
- [[05_redis_bigO_complexity]]
- [[07_multi_level_caching]]
