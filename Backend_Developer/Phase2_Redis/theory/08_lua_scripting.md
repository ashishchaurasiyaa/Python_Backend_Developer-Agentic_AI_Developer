# Redis Lua Scripting

## Why It Matters

Redis is single-threaded — but multi-step ops via MULTI/EXEC aren't atomic against concurrent script use. Lua = **server-side atomic execution**:
- **Atomicity** → multi-step ops without race conditions
- **Network round-trip savings** → 1 round-trip per script vs N per command
- **Custom logic** → rate limiters, locks, complex queries

Senior interview: "Implement distributed rate limiter atomically" → EVAL with Lua.

---

## Core Concepts

### Basic EVAL

```bash
EVAL "return 'hello'" 0
# (returns "hello")


EVAL "return redis.call('SET', KEYS[1], ARGV[1])" 1 mykey myvalue
# KEYS[1] = mykey, ARGV[1] = myvalue
```

### Python

```python
import redis


r = redis.Redis()


# Inline
result = r.eval("return redis.call('GET', KEYS[1])", 1, 'mykey')


# Cached via SCRIPT LOAD + EVALSHA
script = r.register_script("""
    local current = redis.call('GET', KEYS[1])
    if not current then
        redis.call('SET', KEYS[1], ARGV[1])
        return 1
    end
    return 0
""")
result = script(keys=['mykey'], args=['myvalue'])
```

`register_script` returns object that does EVALSHA + falls back to EVAL if script not in cache.

### Atomic Patterns

#### Distributed Lock (Correct Implementation)

```lua
-- Acquire (only if not held)
if redis.call('SET', KEYS[1], ARGV[1], 'NX', 'EX', tonumber(ARGV[2])) then
    return 1
end
return 0
```

```lua
-- Release (only if owner)
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end
return 0
```

Without Lua, race condition: GET + DEL not atomic; another process might acquire between.

#### Rate Limiter (Sliding Window)

```lua
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window_ms = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])

-- Remove old entries
redis.call('ZREMRANGEBYSCORE', key, 0, now - window_ms)

-- Count current
local count = redis.call('ZCARD', key)

if count < limit then
    -- Add new entry
    redis.call('ZADD', key, now, now)
    redis.call('PEXPIRE', key, window_ms)
    return limit - count - 1
end

return -1  -- rate limited
```

#### Atomic Counter with Cap

```lua
local current = tonumber(redis.call('GET', KEYS[1])) or 0
local cap = tonumber(ARGV[1])

if current >= cap then
    return -1
end

return redis.call('INCR', KEYS[1])
```

#### Pop from Multiple Lists (priority queue)

```lua
for i, key in ipairs(KEYS) do
    local v = redis.call('LPOP', key)
    if v then
        return {key, v}
    end
end
return nil
```

### `KEYS` vs `ARGV`

- `KEYS[]` = key names (Redis can route to correct shard in cluster mode)
- `ARGV[]` = values/parameters (not keys)

**Critical for Cluster:** All `KEYS[]` must hash to same slot. Use hash tags.

```python
# WRONG in cluster
r.eval(script, 2, 'user:1', 'user:2', ...)  # different slots → CROSSSLOT


# RIGHT
r.eval(script, 2, '{user:1}:profile', '{user:1}:settings', ...)
```

### Script Caching

```python
# First call: EVAL → caches script, returns SHA
script_sha = r.script_load("return 1")


# Subsequent: EVALSHA (faster, smaller payload)
r.evalsha(script_sha, 0)


# If cache flushed (server restart), get NOSCRIPT error
# redis-py register_script auto-handles
```

### Functions (Redis 7+)

```bash
# Persisted scripts (survive restart, no NOSCRIPT)
FUNCTION LOAD "redis.register_function('myfunc', function(keys, args) return 1 end)"
FCALL myfunc 0
```

Replaces EVAL for persistent scripts. Manage via `FUNCTION LIST`, `FUNCTION DUMP/RESTORE`.

### Limitations

- **No async ops** — script blocks Redis (single-threaded)
- **Max execution time** — `lua-time-limit` config (default 5s) — abort if longer
- **No global state** — each script is fresh
- **No external I/O** — no network, no filesystem
- **No `os.time()` directly** — use `redis.call('TIME')`

### Aborting Long Script

```bash
SCRIPT KILL   # if script doesn't have write ops
SHUTDOWN NOSAVE   # if it does (avoid corruption)
```

### Atomicity Guarantees

Inside one EVAL, the script runs to completion before any other command. Even Pub/Sub messages held. No interleaving.

---

## How It Works Internally

### Single-Threaded Atomicity

Redis = single event loop. Script runs as one "command" — no other commands until done. Hence true atomicity.

### Script Compilation

```
1. Script text → compile Lua bytecode (cached)
2. Execute bytecode in Lua VM (embedded)
3. Each redis.call → invoke Redis command handler
4. Return value → marshalled to Redis protocol
```

### Cluster Compatibility

EVAL in Cluster: all keys must be on same slot. EVALSHA respected via script replication to all nodes.

---

## Common Pitfalls

### 1. Long-Running Script Blocks Redis

```lua
for i = 1, 1000000 do
    redis.call('SET', 'k' .. i, 'v')
end
-- Blocks everyone for seconds
```

Keep scripts short (< 50ms). Loop count bounded. For bulk ops use pipeline instead.

### 2. Writes After Reads in Non-Deterministic Order

```lua
-- BAD: depends on iteration order
for i = 1, 10 do
    local val = redis.call('GET', 'k' .. i)
    redis.call('SET', 'k' .. (i + 100), val)
end
```

Redis script replication mode matters. `effects` mode (default 5+) replicates effects, not script — safer.

### 3. KEYS Hard-Coded Inside Script

```lua
-- WRONG — Cluster can't route
redis.call('GET', 'user:1')


-- RIGHT
redis.call('GET', KEYS[1])
```

Always pass keys via KEYS[] for cluster compatibility.

### 4. Forgetting EXPIRE in Rate Limiter

Memory leak — key never expires:

```lua
redis.call('INCR', KEYS[1])
-- Missing: redis.call('EXPIRE', KEYS[1], 60)
```

### 5. Returning Nil Confusion

Lua `nil` returned to Redis as Redis nil (not False, not 0). Check carefully in client.

### 6. Floating Point Precision

Lua numbers are doubles. For money, use cents (integers).

### 7. SCRIPT FLUSH Wipes Cache

```bash
SCRIPT FLUSH
# Next EVALSHA → NOSCRIPT error
```

Use `register_script` (auto-recover) or `FUNCTION` (persistent).

---

## Interview Q&A

**Q1:** Lua kab use karte ho Redis mein?
**A:** Multi-step atomic operations: distributed locks (SET + DEL based on owner), rate limiters (check + increment + expire), conditional updates (read + check + write). Saves network round-trips, prevents races. Don't use for: long-running logic, simple ops (use commands directly).

**Q2:** Distributed lock with Lua kaise implement karte ho?
**A:** Acquire: `SET key owner_id NX EX ttl`. Release: Lua script — `if GET == owner_id then DEL`. Without Lua, GET + DEL is racy (another acquires between). With Lua, atomic. For HA: Redlock across multiple Redis instances.

**Q3:** KEYS vs ARGV difference?
**A:** KEYS = names of Redis keys. ARGV = parameters/values. Cluster routes script based on KEYS[]. All KEYS[] must be on same slot (use hash tags). Don't hard-code key names in script — pass via KEYS[].

**Q4:** Script + Pipeline ka difference?
**A:** Pipeline: batches commands, NOT atomic against concurrent clients. Lua: atomic AND batched. For independent ops, pipeline cheaper. For ops that depend on each other (read-then-write), need Lua.

**Q5:** lua-time-limit kya hai?
**A:** Default 5s. Script running longer = Redis still single-threaded → other clients wait. If exceeded, Redis returns BUSY error to other clients. Admin can `SCRIPT KILL` if no writes done. Sliently kills entire DB if writes done — SHUTDOWN NOSAVE.

**Q6:** EVAL vs EVALSHA vs FUNCTION?
**A:** EVAL: send script text every time. EVALSHA: send SHA hash (server has cached). FUNCTION (Redis 7+): persisted, survives restart, no NOSCRIPT errors. For prod: register_script (auto-fallback EVALSHA → EVAL) or FUNCTION.

**Q7:** Cluster mein Lua limitations?
**A:** Multi-key ops only across same slot. All KEYS[] must hash to same slot (use hash tags `{user:1}:profile`). Cross-shard impossible in single script. Workaround: scatter-gather in app code (run Lua per shard, combine results).

**Q8:** Lua script debug kaise karte ho?
**A:** `SCRIPT DEBUG SYNC` then EVAL — pauses, allows `b`, `s`, `c` debugger commands. Or log via `redis.log(level, msg)` — appears in Redis log file. For testing, run in dev environment, use `EVAL` with sample data.

---

## Real-World Use Cases

### 1. Token Bucket Rate Limiter

```python
TOKEN_BUCKET = r.register_script("""
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])  -- tokens per sec
local now = tonumber(ARGV[3])

local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(bucket[1]) or capacity
local last_refill = tonumber(bucket[2]) or now

-- Refill
local elapsed = now - last_refill
tokens = math.min(capacity, tokens + elapsed * refill_rate)

if tokens >= 1 then
    tokens = tokens - 1
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
    redis.call('EXPIRE', key, 3600)
    return 1
end

redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
return 0
""")


def allow(user_id, capacity=10, refill_rate=0.5):
    return bool(TOKEN_BUCKET(
        keys=[f'rl:{user_id}'],
        args=[capacity, refill_rate, time.time()],
    ))
```

### 2. Atomic JSON Field Update

```lua
local current = redis.call('GET', KEYS[1])
if not current then return nil end

local obj = cjson.decode(current)
obj[ARGV[1]] = ARGV[2]
redis.call('SET', KEYS[1], cjson.encode(obj))
return 1
```

### 3. Inventory Decrement with Reservation

```lua
local stock = tonumber(redis.call('GET', KEYS[1]))
if not stock or stock < tonumber(ARGV[1]) then
    return 0  -- insufficient
end
redis.call('DECRBY', KEYS[1], ARGV[1])
return 1
```

---

## References

- [Redis Lua Scripting](https://redis.io/docs/manual/programmability/eval-intro/)
- [EVAL command](https://redis.io/commands/eval/)
- [Functions (Redis 7+)](https://redis.io/docs/manual/programmability/functions-intro/)
- Redlock algorithm
