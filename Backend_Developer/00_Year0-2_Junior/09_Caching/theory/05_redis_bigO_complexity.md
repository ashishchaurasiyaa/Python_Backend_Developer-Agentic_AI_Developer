# Big-O Complexity of Redis Commands

> **Interview angle:** "Redis fast hai" — galat. Galat command use karoge to slow hi hoga. Big-O dekhna padta.

---

## 1. Redis is Single-Threaded — Each Command Blocks

All commands run in ONE thread (per shard). A slow command blocks **all other clients**.

```
Client A: KEYS *      ← takes 5 seconds on 10M keys
Client B: GET foo     ← blocked, waits 5s
Client C: SET bar 1   ← also blocked
```

**This is the #1 reason to know Big-O of every command you use.**

---

## 2. Quick Reference — Most Common Commands

### Strings — Mostly O(1)
| Command | Complexity | Notes |
|---|---|---|
| `GET`, `SET`, `DEL` | O(1) | Constant |
| `INCR`, `DECR`, `INCRBY` | O(1) | |
| `MGET`, `MSET` | O(N) | N = number of keys |
| `STRLEN` | O(1) | |
| `GETRANGE` | O(N) | N = length returned |
| `APPEND` | O(1) amortized | |

### Hashes — Mostly O(1)
| Command | Complexity |
|---|---|
| `HGET`, `HSET`, `HDEL` | O(1) |
| `HMGET`, `HMSET` | O(N) where N = fields |
| `HGETALL`, `HKEYS`, `HVALS` | **O(N)** — N = ALL fields! |
| `HLEN`, `HEXISTS` | O(1) |
| `HINCRBY` | O(1) |

### Lists — Mixed
| Command | Complexity | Notes |
|---|---|---|
| `LPUSH`, `RPUSH`, `LPOP`, `RPOP` | O(1) | Both ends fast |
| `LRANGE start end` | O(S+N) | S = start offset, N = elements |
| `LINDEX` | O(N) | Walks list! |
| `LREM` | O(N) | |
| `LLEN` | O(1) | |
| `LINSERT` | O(N) | Walks list to find pivot |

### Sets — Mostly O(1)
| Command | Complexity |
|---|---|
| `SADD`, `SREM`, `SISMEMBER`, `SCARD` | O(1) |
| `SMEMBERS` | **O(N)** — all members! |
| `SUNION`, `SINTER`, `SDIFF` | O(N+M+...) |
| `SRANDMEMBER count` | O(N) for large counts |
| `SPOP` | O(1) |

### Sorted Sets — O(log N)
| Command | Complexity |
|---|---|
| `ZADD`, `ZREM`, `ZSCORE` | O(log N) |
| `ZRANGEBYSCORE` | O(log N + M) — M returned |
| `ZRANGE start end` | O(log N + M) |
| `ZRANK` | O(log N) |
| `ZCARD`, `ZCOUNT` | O(log N) ish |
| `ZINCRBY` | O(log N) |

### Keys / Server — Some DANGEROUS
| Command | Complexity | Warning |
|---|---|---|
| `KEYS pattern` | **O(N)** — ALL keys! | ❌ NEVER in production |
| `SCAN cursor` | O(1) per call | ✅ Cursor-based |
| `DBSIZE` | O(1) | |
| `FLUSHDB`, `FLUSHALL` | O(N) | Blocks |
| `EXISTS key` | O(1) | |
| `EXPIRE`, `TTL` | O(1) | |

---

## 3. Commands to AVOID in Production

### `KEYS pattern` — NEVER
```python
keys = redis.keys("user:*")    # ❌ blocks Redis for seconds
```
**Replacement:**
```python
cursor = 0
while True:
    cursor, batch = redis.scan(cursor, match="user:*", count=1000)
    process(batch)
    if cursor == 0: break
```

### `SMEMBERS` on huge sets
```python
all_followers = redis.smembers("followers:42")   # ❌ if 1M followers
```
**Replacement:**
```python
cursor = 0
while True:
    cursor, batch = redis.sscan("followers:42", cursor, count=1000)
    ...
```

Similar: `HGETALL` for huge hashes → use `HSCAN`.

### `DEL` on huge collections
```python
redis.del("session_history")   # if 1M items inside → blocks
```
**Replacement:**
```python
redis.unlink("session_history")   # async DEL (Redis 4+)
```

### `FLUSHDB` synchronous
```python
redis.flushdb()                    # blocks
redis.flushdb(asynchronous=True)   # ✅ background
```

### `SORT` without index
```python
redis.sort("big_list", by="weight_*")    # O(N log N)
```
Sorting in Redis = often a sign of wrong data model. Use sorted set.

---

## 4. Pipeline + Multi-Get for Throughput

### Without pipeline: N round trips
```python
for key in keys:
    value = redis.get(key)    # 1 RTT each
# 1000 keys = 1000 round trips = ~100ms over network
```

### With MGET: 1 call, O(N) on server
```python
values = redis.mget(keys)     # 1 round trip
# 1000 keys = ~1ms
```

### With pipeline: 1 round trip, multiple commands
```python
pipe = redis.pipeline()
for key in keys:
    pipe.get(key)
values = pipe.execute()
```

---

## 5. Cluster — Same Command, Different Considerations

In Redis Cluster, keys hashed to slots → different nodes.

- `MGET` with keys on different slots → ERROR
- Use hash tags `{user}` to force same slot:
  ```python
  redis.mget("{user42}:profile", "{user42}:settings")  # same slot
  ```
- `KEYS`, `SCAN` per-node — need to iterate all nodes

---

## 6. Lua Scripts — Atomic Multi-Command

```lua
-- Atomically: GET + check + SET
local current = redis.call("GET", KEYS[1])
if current == ARGV[1] then
    redis.call("DEL", KEYS[1])
    return 1
end
return 0
```

**Complexity:** Sum of all commands inside. Whole script blocks Redis.
**Use for:** atomicity (replaces MULTI/EXEC, less round trips).

---

## 7. Memory Cost of Different Structures

### String
- Small string: ~56 bytes overhead + value length
- Up to 512 MB per string

### Hash
- ~80 bytes per hash + per-field overhead
- **Use compact encoding** if entries ≤ `hash-max-listpack-entries` (default 128)
- Compact hash: ~40% less memory than separate strings

### List
- O(N) memory
- Quicklist encoding (linked list of ziplists)

### Set
- ~80 bytes + per-element overhead
- Use intset encoding for integer-only sets (very compact)

### Sorted Set
- Skip list + hash table = more memory
- Each entry: ~64 bytes minimum
- For top-N leaderboards, fine. For huge sorted data, expensive.

### Quick estimates
- 1M small strings: ~150 MB
- 1M hash entries (in same hash): ~80 MB
- 1M sorted set entries: ~100 MB

---

## 8. Common Anti-Patterns

### Anti-pattern 1: Storing big JSON as string
```python
redis.set("user:42", json.dumps(large_user_obj))  # 50KB
```
**Bad:** every read transfers 50KB. Every update overwrites all.
**Better:** hash with fields, update individual.

### Anti-pattern 2: One big list for ordered events
```python
redis.lpush("events", json.dumps(event))     # millions of entries
redis.lrange("events", 0, -1)                # ❌ huge transfer
```
**Better:** Redis Streams (XADD/XREAD).

### Anti-pattern 3: Using sorted set as unique counter
```python
redis.zincrby("counts", 1, "user")   # works but O(log N)
```
**Better:** hash with HINCRBY (O(1)).

### Anti-pattern 4: Pub/Sub for persistence
Pub/Sub messages dropped if no subscriber. Use Streams for durability.

### Anti-pattern 5: Long-running Lua script
Whole Redis blocked while script runs. Keep scripts short.

---

## 9. Performance Targets

### Latency budgets
- Local Redis: < 1ms p99
- Same DC: < 2ms p99
- Cross-DC: ~10ms p99

### Throughput
- Single Redis instance: 100K-1M ops/sec on modern hardware
- Cluster: scales linearly
- Pipelining: 10x throughput improvement
- Lua scripts: avoid round trips

### When you see > 5ms latency
- Check `SLOWLOG GET 10` for slow commands
- Check `CLIENT LIST` for blocked clients
- Check network round-trip
- Check if running KEYS or SMEMBERS somewhere

---

## 10. SLOWLOG — Find Slow Commands

```bash
# Configure (set threshold)
CONFIG SET slowlog-log-slower-than 10000   # log queries > 10ms (in microseconds)

# View
SLOWLOG GET 10
# Returns:
# 1) (integer) 14         # ID
# 2) (integer) 1234567    # timestamp
# 3) (integer) 25000      # duration microseconds
# 4) 1) "KEYS" 2) "user:*"   # command + args

# Reset
SLOWLOG RESET
```

---

## 11. MEMORY USAGE Command

```bash
# Bytes used by a specific key
MEMORY USAGE myhash
# (integer) 1842

# Top N keys by memory
redis-cli --bigkeys
```

---

## 12. Pitfalls Summary

❌ `KEYS *` — use SCAN
❌ `SMEMBERS` huge set — use SSCAN
❌ `HGETALL` huge hash — use HSCAN
❌ `DEL` huge collection — use UNLINK
❌ Storing big JSON blobs — use hashes
❌ Pub/Sub for durable messaging — use Streams
❌ Long Lua scripts — keep them short
❌ No SLOWLOG — flying blind
❌ No `maxmemory` set — eats all RAM
❌ MGET across cluster slots — use hash tags

---

## 13. Interview Questions

**Q1: Redis single-threaded — slow command kya hota?**
Blocks all clients. Slow command = all other commands wait. SLOWLOG monitor karna critical.

**Q2: KEYS pattern production safe?**
NO. O(N) on all keys = blocks Redis for seconds. Use SCAN with cursor.

**Q3: SMEMBERS huge set safe?**
No — O(N). Use SSCAN to iterate.

**Q4: ZADD complexity?**
O(log N) — sorted set uses skip list.

**Q5: HGETALL vs HSCAN?**
HGETALL = O(N) blocks. HSCAN = cursor-based, batched, non-blocking.

**Q6: DEL vs UNLINK?**
DEL = sync, blocks Redis on huge keys. UNLINK = async background deletion.

**Q7: Pipeline vs MGET?**
MGET = single command, multiple keys, atomic, faster on server.
Pipeline = multiple commands of any type, fewer RTTs.

**Q8: Lua script ka risk?**
Blocks all Redis ops. Keep scripts short (< 1ms ideally).

---

## 14. Best Practices

1. **Know Big-O of every command** you use
2. **SCAN, never KEYS** in production
3. **Pipeline / MGET** for bulk ops
4. **SLOWLOG** in monitoring
5. **MEMORY USAGE** for key size checks
6. **UNLINK over DEL** for large collections
7. **Hash structures** for related fields
8. **Hash tags** for cluster co-location
9. **Lua scripts**: short, well-tested
10. **maxmemory** + eviction policy = safety net

---

## Related
- [[../../00_Year0-2_Junior/08_Redis/theory/02_pipeline_connection_pool]]
- [[04_memory_eviction_policies]]
- [[02_redlock_distributed_locks]] — Lua usage
