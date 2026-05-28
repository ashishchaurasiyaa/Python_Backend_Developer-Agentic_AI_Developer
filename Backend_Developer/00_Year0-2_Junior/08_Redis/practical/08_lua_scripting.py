"""
Redis Lua Scripts — Production Patterns
"""

import time
import secrets
import redis


r = redis.Redis(host='localhost', port=6379, decode_responses=True)


# ==========================================================================
# 1. DISTRIBUTED LOCK (correct implementation)
# ==========================================================================

ACQUIRE_LOCK_SCRIPT = r.register_script("""
return redis.call('SET', KEYS[1], ARGV[1], 'NX', 'EX', tonumber(ARGV[2]))
""")


RELEASE_LOCK_SCRIPT = r.register_script("""
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end
return 0
""")


EXTEND_LOCK_SCRIPT = r.register_script("""
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('EXPIRE', KEYS[1], tonumber(ARGV[2]))
end
return 0
""")


class DistributedLock:
    def __init__(self, key, ttl=10):
        self.key = key
        self.ttl = ttl
        self.token = secrets.token_hex(16)
        self.acquired = False

    def acquire(self) -> bool:
        result = ACQUIRE_LOCK_SCRIPT(keys=[self.key], args=[self.token, self.ttl])
        self.acquired = bool(result)
        return self.acquired

    def release(self) -> bool:
        if not self.acquired:
            return False
        result = RELEASE_LOCK_SCRIPT(keys=[self.key], args=[self.token])
        self.acquired = False
        return bool(result)

    def extend(self, ttl):
        return bool(EXTEND_LOCK_SCRIPT(keys=[self.key], args=[self.token, ttl]))

    def __enter__(self):
        if not self.acquire():
            raise Exception(f"Lock {self.key} already held")
        return self

    def __exit__(self, *args):
        self.release()


# Usage
# with DistributedLock('inventory:product-5', ttl=30):
#     # Critical section
#     decrement_stock()


# ==========================================================================
# 2. SLIDING WINDOW RATE LIMITER
# ==========================================================================

SLIDING_WINDOW_RATE_LIMIT = r.register_script("""
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window_ms = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])

-- Remove expired entries
redis.call('ZREMRANGEBYSCORE', key, 0, now - window_ms)

-- Count current
local count = redis.call('ZCARD', key)

if count >= limit then
    -- Return seconds until oldest expires
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local retry_after = 0
    if oldest[2] then
        retry_after = math.ceil((tonumber(oldest[2]) + window_ms - now) / 1000)
    end
    return {0, retry_after}
end

-- Add this request
redis.call('ZADD', key, now, now .. ':' .. redis.sha1hex(tostring(math.random())))
redis.call('PEXPIRE', key, window_ms)

return {1, limit - count - 1}
""")


def check_rate_limit(user_id: str, limit: int = 100, window_seconds: int = 60):
    """Returns (allowed, remaining_or_retry_after)."""
    now_ms = int(time.time() * 1000)
    result = SLIDING_WINDOW_RATE_LIMIT(
        keys=[f'rl:{user_id}'],
        args=[now_ms, window_seconds * 1000, limit],
    )
    return bool(result[0]), int(result[1])


# Usage
# allowed, remaining = check_rate_limit('user:123', limit=10, window_seconds=60)


# ==========================================================================
# 3. TOKEN BUCKET RATE LIMITER
# ==========================================================================

TOKEN_BUCKET = r.register_script("""
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local cost = tonumber(ARGV[4])

local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(bucket[1]) or capacity
local last_refill = tonumber(bucket[2]) or now

local elapsed = now - last_refill
tokens = math.min(capacity, tokens + elapsed * refill_rate)

if tokens >= cost then
    tokens = tokens - cost
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
    redis.call('EXPIRE', key, 3600)
    return {1, tokens}
end

redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
redis.call('EXPIRE', key, 3600)
return {0, tokens}
""")


def token_bucket_allow(user_id, capacity=10, refill_rate=0.5, cost=1):
    """refill_rate = tokens/sec. cost = tokens this request needs."""
    result = TOKEN_BUCKET(
        keys=[f'tb:{user_id}'],
        args=[capacity, refill_rate, time.time(), cost],
    )
    return bool(result[0]), float(result[1])


# ==========================================================================
# 4. ATOMIC COUNTER WITH CAP
# ==========================================================================

INCR_WITH_CAP = r.register_script("""
local current = tonumber(redis.call('GET', KEYS[1])) or 0
local cap = tonumber(ARGV[1])

if current >= cap then
    return -1
end

return redis.call('INCR', KEYS[1])
""")


def safe_increment(key, cap):
    return int(INCR_WITH_CAP(keys=[key], args=[cap]))


# ==========================================================================
# 5. CONDITIONAL UPDATE (compare-and-swap)
# ==========================================================================

COMPARE_AND_SWAP = r.register_script("""
if redis.call('GET', KEYS[1]) == ARGV[1] then
    redis.call('SET', KEYS[1], ARGV[2])
    return 1
end
return 0
""")


def cas(key, expected, new_value):
    """Update key to new_value only if current == expected."""
    return bool(COMPARE_AND_SWAP(keys=[key], args=[expected, new_value]))


# ==========================================================================
# 6. INVENTORY DECREMENT (atomic check + decrement)
# ==========================================================================

DECREMENT_INVENTORY = r.register_script("""
local stock = tonumber(redis.call('GET', KEYS[1])) or 0
local amount = tonumber(ARGV[1])

if stock < amount then
    return 0
end

return redis.call('DECRBY', KEYS[1], amount)
""")


def reserve_inventory(product_id, amount):
    """Returns new stock or 0 if insufficient."""
    result = DECREMENT_INVENTORY(
        keys=[f'inventory:{product_id}'],
        args=[amount],
    )
    return int(result)


# ==========================================================================
# 7. ATOMIC JSON FIELD UPDATE
# ==========================================================================

UPDATE_JSON_FIELD = r.register_script("""
local current = redis.call('GET', KEYS[1])
if not current then return nil end

local obj = cjson.decode(current)
obj[ARGV[1]] = cjson.decode(ARGV[2])
redis.call('SET', KEYS[1], cjson.encode(obj))
return 1
""")


def update_json_field(key, field, value):
    import json
    return UPDATE_JSON_FIELD(
        keys=[key],
        args=[field, json.dumps(value)],
    )


# ==========================================================================
# 8. PRIORITY QUEUE POP (multi-list)
# ==========================================================================

POP_PRIORITY = r.register_script("""
for i, key in ipairs(KEYS) do
    local v = redis.call('LPOP', key)
    if v then
        return {key, v}
    end
end
return {nil, nil}
""")


def pop_highest_priority():
    """Try queues high → medium → low."""
    result = POP_PRIORITY(keys=['queue:high', 'queue:medium', 'queue:low'])
    return result[0], result[1]


# ==========================================================================
# 9. REDIS 7+ FUNCTIONS (persistent scripts)
# ==========================================================================

# Function = persisted Lua, no NOSCRIPT errors
FUNCTION_CODE = """
#!lua name=myrate

redis.register_function('rate_limit', function(keys, args)
    local key = keys[1]
    local now = tonumber(args[1])
    local window_ms = tonumber(args[2])
    local limit = tonumber(args[3])

    redis.call('ZREMRANGEBYSCORE', key, 0, now - window_ms)
    local count = redis.call('ZCARD', key)

    if count >= limit then return 0 end

    redis.call('ZADD', key, now, tostring(now))
    redis.call('PEXPIRE', key, window_ms)
    return 1
end)
"""

# Load via:
# r.function_load(FUNCTION_CODE)
# Call: r.fcall('rate_limit', 1, 'rl:user:1', time_ms, 60000, 100)


# ==========================================================================
# 10. SCRIPT DEBUGGING
# ==========================================================================

DEBUG_TIPS = """
1. Log inside script:
   redis.log(redis.LOG_WARNING, 'Debug: stock=' .. tostring(stock))

2. Test in redis-cli:
   redis-cli --eval script.lua key1 , arg1 arg2

3. Sync debugger:
   SCRIPT DEBUG SYNC
   EVAL "..." 0
   # Step through with: continue, step, list, break <line>

4. Check cached scripts:
   SCRIPT EXISTS <sha1>
   SCRIPT LOAD <script>   # returns sha
   SCRIPT FLUSH           # clear all

5. Common gotchas:
   - cjson.encode returns "[]" for empty array, "{}" for empty object
   - redis.call vs redis.pcall (pcall doesn't raise)
   - Lua tables 1-indexed (not 0)
   - Math errors silently — use tonumber() carefully
"""


# ==========================================================================
# 11. PROD MONITORING
# ==========================================================================

PROD_QUERIES = """
# Slow scripts (use slowlog)
SLOWLOG GET 10

# Latency for scripts
LATENCY HISTORY script

# How many scripts cached
DEBUG OBJECT script_cache_keys

# Long-running scripts
SCRIPT KILL    # if no writes
SHUTDOWN NOSAVE  # if writes happened (data may be inconsistent)
"""
