# Redlock — Distributed Locks with Redis

> **Interview angle:** "Multi-instance app mein same Celery task 2 baar trigger ho rahi. Sirf ek bar execute karne ka guarantee kaise?"

---

## 1. Why Distributed Locks?

Single-process locks (`threading.Lock`) work only within ONE process.

**Multi-instance scenarios needing distributed locks:**
- Cron job running on N replicas — only one should execute
- Resource exclusivity (one writer per resource)
- Leader election in cluster
- Preventing duplicate API calls (idempotency)
- Singleton initialization (cache warming, DB seeding)

---

## 2. Simple Redis Lock (Naive, has bugs)

```python
# DANGEROUS — has multiple race conditions
def acquire(key):
    if redis.setnx(key, "1"):    # SET if not exists
        redis.expire(key, 30)    # ← gap! could crash between setnx and expire
        return True
    return False
```

**Problems:**
1. **Race between SETNX + EXPIRE** — if app crashes between, lock never released
2. **No owner check** — anyone can release
3. **Clock drift** — lease can expire mid-operation
4. **Single Redis = single point of failure**

---

## 3. Better: Atomic SET with NX + EX

```python
# Use SET with all options in one atomic command
lock_id = str(uuid.uuid4())   # unique owner ID
acquired = redis.set(key, lock_id, nx=True, ex=30)
if acquired:
    try:
        # do work
        pass
    finally:
        # Only release if WE own it (Lua script for atomicity)
        release_lua = """
        if redis.call("GET", KEYS[1]) == ARGV[1] then
            return redis.call("DEL", KEYS[1])
        else
            return 0
        end
        """
        redis.eval(release_lua, 1, key, lock_id)
```

**Key properties:**
- Atomic SET NX + EX (no race)
- Random `lock_id` = owner check
- Lua script = atomic check-and-delete
- TTL = auto-release on crash

This works for **most cases**. But not bulletproof for split brain.

---

## 4. THE REDLOCK ALGORITHM (Martin Kleppmann's critique aside)

Antirez (Redis creator) proposed **Redlock** for higher safety using **N independent Redis instances** (typically 5).

### Algorithm
1. Get current time T_start
2. Try to acquire lock on **all N Redis instances** with same key + UUID + TTL
3. Use short connect/operation timeout to avoid hanging
4. Lock considered acquired if:
   - Majority (N/2 + 1) instances succeeded
   - Time elapsed (T_end - T_start) < TTL
5. Effective lock duration = TTL - elapsed_time
6. If failed, release on ALL instances anyway (best-effort)

### Why N Redis instances?
- Failure of single Redis = lock not lost (still on majority)
- Split brain less likely

### Implementation
```python
class Redlock:
    def __init__(self, redis_nodes: list, retry_count=3, retry_delay_ms=200):
        self.nodes = redis_nodes
        self.quorum = len(redis_nodes) // 2 + 1
        self.retry_count = retry_count
        self.retry_delay_ms = retry_delay_ms

    def acquire(self, resource: str, ttl_ms: int) -> dict | None:
        val = secrets.token_hex(16)
        for _ in range(self.retry_count):
            start = time.monotonic() * 1000
            acquired_count = 0
            for node in self.nodes:
                try:
                    if node.set(resource, val, nx=True, px=ttl_ms):
                        acquired_count += 1
                except Exception:
                    pass
            elapsed = time.monotonic() * 1000 - start
            validity = ttl_ms - elapsed - CLOCK_DRIFT_FACTOR
            if acquired_count >= self.quorum and validity > 0:
                return {"resource": resource, "val": val, "validity": validity}
            # Failed — release everywhere
            for node in self.nodes:
                self._safe_release(node, resource, val)
            time.sleep(self.retry_delay_ms / 1000)
        return None
```

### Production library: `redis-py-redlock` or `aioredlock`
```python
from aioredlock import Aioredlock

lock_manager = Aioredlock([
    {"host": "redis1", "port": 6379},
    {"host": "redis2", "port": 6379},
    {"host": "redis3", "port": 6379},
])

async with await lock_manager.lock("resource_key", lock_timeout=10):
    # critical section
    do_work()
```

---

## 5. Martin Kleppmann's Critique

Kleppmann argued Redlock is **not safe** in adverse conditions:

### Issue 1: GC pause / network partition
```
1. Client A acquires lock
2. App pauses (GC, network delay)
3. Lock TTL expires on Redis
4. Client B acquires lock (Redis thinks A's lock gone)
5. Client A wakes up, thinks it still holds lock
6. Both A and B in critical section → race condition!
```

### Solution: Fencing Tokens
Each lock acquisition returns a **monotonically increasing token**.
Downstream service must check token > last seen.

```python
def acquire_with_fence(resource):
    # Get monotonic counter from Redis
    token = redis.incr(f"{resource}:fence")
    return {"lock": acquire_lock(resource), "fence_token": token}

# Storage service rejects writes with stale tokens
def write_storage(data, fence_token):
    if fence_token < last_seen_token:
        raise StaleTokenError()
    last_seen_token = fence_token
    write(data)
```

### Issue 2: Clock drift across Redis nodes
If one Redis node's clock is off, TTL math breaks.

### Bottom Line
- Redlock OK for **best-effort locking** (mutual exclusion most of the time)
- For **safety-critical correctness** (financial txns), use ZooKeeper/etcd/Postgres advisory lock + fencing tokens

---

## 6. Alternatives to Redlock

### Single-Redis Lock (simplest, "good enough" for many cases)
```python
# Single Redis + SET NX EX + Lua release
# Works if Redis is mostly available + ops are idempotent
```

### Postgres Advisory Lock
```sql
SELECT pg_try_advisory_lock(12345);   -- non-blocking
SELECT pg_advisory_lock(12345);       -- blocking
SELECT pg_advisory_unlock(12345);
```
- Released when transaction ends (or explicitly)
- Strong consistency (Postgres = single source of truth)
- No clock drift issues

### ZooKeeper / etcd
- Built for consensus
- Linearizable
- Used by Kafka, K8s
- More complex setup

### Lease-based (Chubby / etcd)
- Get lease for N seconds
- Heartbeat to extend
- Lose heartbeat → lose lease

| Tool | Safety | Latency | Complexity |
|---|---|---|---|
| Single Redis SET NX | Best-effort | Low | Low |
| Redlock | Improved (debated) | Medium | Medium |
| Postgres Advisory | Strong | Medium | Low |
| ZooKeeper/etcd | Linearizable | Higher | High |

**Default recommendation:** Single Redis + SET NX + Lua release. Add fencing if criticality high.

---

## 7. Locking Patterns

### Pattern 1: Mutex (mutual exclusion)
Standard lock — one holder at a time.

### Pattern 2: Read-Write Lock
Multiple readers OR one writer.
```python
# Redis-based — readers increment, writers acquire exclusive
def acquire_read(key):
    if redis.get(f"{key}:write"):
        return False
    redis.incr(f"{key}:readers")
    return True
```

### Pattern 3: Leader Election
N instances compete; one becomes leader.
```python
def become_leader(node_id):
    return redis.set("leader", node_id, nx=True, ex=30)

# Leader periodically refreshes
def refresh_leader(node_id):
    lua = """
    if redis.call("GET", KEYS[1]) == ARGV[1] then
        return redis.call("EXPIRE", KEYS[1], ARGV[2])
    else
        return 0
    end
    """
    return redis.eval(lua, 1, "leader", node_id, 30)
```

### Pattern 4: Distributed Semaphore
N concurrent allowed.
```lua
-- Acquire semaphore (max 5 concurrent)
-- KEYS[1] = semaphore key, ARGV[1] = max, ARGV[2] = id
local current = redis.call("SCARD", KEYS[1])
if current < tonumber(ARGV[1]) then
    redis.call("SADD", KEYS[1], ARGV[2])
    return 1
end
return 0
```

### Pattern 5: Re-entrant Lock (same client can re-acquire)
Store count + thread/client ID. Increment on acquire, decrement on release.

---

## 8. Lock TTL Selection

### Too short
- Lock expires mid-work
- Another process grabs it
- Race condition

### Too long
- If holder crashes, others wait too long
- Operations queued up

### Best practice
- TTL = **2-3x typical operation time**
- Use **lock extender / watchdog** for variable-duration work
  ```python
  # Extend lock every N seconds while working
  async def extend_lock(lock_key, lock_id, ttl=30):
      while still_working:
          await asyncio.sleep(ttl / 3)
          extend_lua(...)
  ```

---

## 9. Common Pitfalls

### Pitfall 1: Forgetting to release
Always use `try/finally` or context manager.
```python
with redlock.lock(resource, ttl=10):
    # auto-release
    do_work()
```

### Pitfall 2: Releasing someone else's lock
Always check owner ID before release.

### Pitfall 3: Long operation without lock extension
Lock expires → another worker starts → both running.

### Pitfall 4: Single-Redis bottleneck
All locks through one Redis = SPOF. Use Redis Cluster or accept single point.

### Pitfall 5: Lock held during external call
```python
with lock:
    await call_external_api()   # could take 30s — lock expires!
```
**Fix:** Set TTL > max external call time, OR do call OUTSIDE lock.

---

## 10. Real Use Cases

### Use Case 1: Singleton Initialization
Multiple replicas start → only one runs DB migration.
```python
with redlock("db_migration", ttl=60):
    if not migration_done():
        run_migrations()
```

### Use Case 2: Idempotent API
```python
def process_payment(payment_id):
    with redlock(f"pay:{payment_id}", ttl=30):
        if already_processed(payment_id):
            return  # idempotent
        charge_card()
        mark_processed(payment_id)
```

### Use Case 3: Cron deduplication
N instances trigger same cron at 0:00:00. Only one should run.
```python
@cron("0 0 * * *")
def daily_report():
    with redlock("daily_report", ttl=3600):
        generate_report()
```

### Use Case 4: Resource exclusivity
Each user has at most one active session.
```python
def login(user_id, session_id):
    with redlock(f"user:{user_id}:session", ttl=86400):
        revoke_old_sessions(user_id)
        create_session(session_id)
```

---

## 11. Interview Questions

**Q1: SETNX + EXPIRE in two calls — kya problem?**
Race: crash between two calls → lock without TTL → orphaned forever. Use atomic `SET NX EX`.

**Q2: Redlock 5 Redis nodes kyu?**
Majority quorum (3 of 5). Withstands 2 node failures while maintaining lock validity.

**Q3: Redlock safe hai?**
Debated. Martin Kleppmann showed pauses can break it. Use fencing tokens for safety-critical.

**Q4: Fencing token kya?**
Monotonic counter returned with lock. Downstream rejects stale tokens. Prevents zombie holders from causing damage.

**Q5: Redis lock vs Postgres advisory?**
Postgres = stronger consistency, tied to transaction. Redis = faster, lower commitment to durability.

**Q6: Long operation lock kaise handle?**
Lock extender — background task extends TTL every N seconds while operation running.

**Q7: Cron deduplication kaise?**
Single Redis lock with TTL > expected job duration. First to acquire wins.

---

## 12. Best Practices

1. **Use atomic SET NX EX** — never separate SETNX + EXPIRE
2. **Owner-tagged release** with Lua script (atomic)
3. **Context manager API** — `with redlock(...):`
4. **TTL = 2-3× expected operation time**
5. **Extend lock for long-running ops**
6. **Use fencing tokens** for critical writes
7. **Idempotent operations + locks** = belt + suspenders
8. **Postgres advisory lock** when DB already involved
9. **Library, don't roll your own** — aioredlock, redlock-py
10. **Monitor lock contention** — high = bottleneck

---

## Related
- [[../../Phase2_Redis/theory/01_basics_installation_cli]]
- [[03_cache_stampede_cold_start]] — uses locks for stampede prevention
- [[../../PythonBackend_SystemDesign/HLD_Theory/35_Service_Discovery_Distributed_Locking]]
