"""
Redis Practical 01 — Basics, CLI Commands & Key Naming
Run: python 01_basics_cli_keys.py [strings|hashes|lists|sets|sorted|scan|encoding|all]

Prerequisites:
  pip install redis[hiredis]
  docker run -d --name redis -p 6379:6379 redis:7-alpine
"""

import redis
import time
import sys

# ─── Connection ───
r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)


# ════════════════════════════════════════════
# SECTION 1: STRING COMMANDS
# ════════════════════════════════════════════
def demo_strings():
    print("\n" + "="*50)
    print("  SECTION 1: STRING COMMANDS")
    print("="*50)

    # Basic SET / GET
    r.set("name", "Alice")
    print(f"SET name → GET: {r.get('name')}")

    # SET with TTL (expire after 10 seconds)
    r.set("temp:token", "abc123", ex=10)
    print(f"SET temp:token (ex=10) → TTL: {r.ttl('temp:token')}s")

    # SET with condition
    r.set("user:1:name", "Alice")
    result_nx = r.set("user:1:name", "Bob", nx=True)   # Only if NOT exists
    result_xx = r.set("user:1:name", "Bob", xx=True)   # Only if EXISTS
    print(f"SET NX (not exists): {result_nx}")  # None — already exists
    print(f"SET XX (exists):     {result_xx}")  # True  — exists, updated

    # GETSET — get old, set new (atomically)
    old_val = r.getset("user:1:name", "Charlie")
    print(f"GETSET: old='{old_val}', new='{r.get('user:1:name')}'")

    # MSET / MGET — multiple at once
    r.mset({
        "user:1:email": "alice@test.com",
        "user:1:age":   "25",
        "user:1:city":  "Mumbai"
    })
    values = r.mget("user:1:email", "user:1:age", "user:1:city")
    print(f"MGET: {values}")

    # INCR / DECR — atomic counter
    r.set("counter:visits", 100)
    r.incr("counter:visits")          # 101
    r.incrby("counter:visits", 9)     # 110
    r.decr("counter:visits")          # 109
    r.decrby("counter:visits", 9)     # 100
    print(f"Counter after ops: {r.get('counter:visits')}")

    # APPEND
    r.set("greeting", "Hello")
    r.append("greeting", ", World!")
    print(f"APPEND: {r.get('greeting')}")

    # STRLEN
    print(f"STRLEN: {r.strlen('greeting')}")

    # GETRANGE (substring)
    print(f"GETRANGE [0,4]: {r.getrange('greeting', 0, 4)}")

    # EXISTS / TYPE
    print(f"EXISTS name: {r.exists('name')}")
    print(f"TYPE name:   {r.type('name')}")

    # TTL Commands
    r.set("expire_demo", "will expire", ex=60)
    print(f"TTL: {r.ttl('expire_demo')}s")
    print(f"PTTL: {r.pttl('expire_demo')}ms")
    r.persist("expire_demo")          # TTL remove karo
    print(f"After PERSIST TTL: {r.ttl('expire_demo')}")  # -1 = no TTL

    # Cleanup
    r.delete("name", "temp:token", "user:1:name", "user:1:email",
             "user:1:age", "user:1:city", "counter:visits",
             "greeting", "expire_demo")
    print("✅ Strings demo complete!")


# ════════════════════════════════════════════
# SECTION 2: HASH COMMANDS
# ════════════════════════════════════════════
def demo_hashes():
    print("\n" + "="*50)
    print("  SECTION 2: HASH COMMANDS")
    print("="*50)

    # HSET — set one or multiple fields
    r.hset("user:100", mapping={
        "name":    "Bob",
        "email":   "bob@test.com",
        "age":     "30",
        "city":    "Delhi",
        "balance": "5000"
    })

    # HGET / HMGET
    name  = r.hget("user:100", "name")
    multi = r.hmget("user:100", "name", "email", "age")
    print(f"HGET name: {name}")
    print(f"HMGET: {multi}")

    # HGETALL — all fields
    all_data = r.hgetall("user:100")
    print(f"HGETALL: {all_data}")

    # HKEYS / HVALS / HLEN
    print(f"HKEYS: {r.hkeys('user:100')}")
    print(f"HVALS: {r.hvals('user:100')}")
    print(f"HLEN:  {r.hlen('user:100')}")

    # HINCRBY — increment numeric field
    r.hincrby("user:100", "age", 1)        # 30 → 31
    r.hincrbyfloat("user:100", "balance", 1500.50)  # 5000 → 6500.5
    print(f"Age after HINCRBY: {r.hget('user:100', 'age')}")
    print(f"Balance after HINCRBYFLOAT: {r.hget('user:100', 'balance')}")

    # HSETNX — set only if field not exists
    result = r.hsetnx("user:100", "name", "Alice")  # name already exists
    result2 = r.hsetnx("user:100", "phone", "9876543210")  # new field
    print(f"HSETNX existing field: {result}")   # 0 = not set
    print(f"HSETNX new field: {result2}")        # 1 = set

    # HDEL — delete specific fields
    r.hdel("user:100", "phone", "city")
    print(f"After HDEL: {r.hkeys('user:100')}")

    # HEXISTS — field exists check
    print(f"HEXISTS name: {r.hexists('user:100', 'name')}")
    print(f"HEXISTS city: {r.hexists('user:100', 'city')}")

    # HSCAN — iterate hash fields (large hashes ke liye)
    r.hset("big:hash", mapping={f"field:{i}": f"val:{i}" for i in range(20)})
    cursor, data = r.hscan("big:hash", cursor=0, match="field:1*", count=5)
    print(f"HSCAN result (field:1*): {list(data.keys())}")

    # Cleanup
    r.delete("user:100", "big:hash")
    print("✅ Hashes demo complete!")


# ════════════════════════════════════════════
# SECTION 3: LIST COMMANDS
# ════════════════════════════════════════════
def demo_lists():
    print("\n" + "="*50)
    print("  SECTION 3: LIST COMMANDS")
    print("="*50)

    # RPUSH / LPUSH — right/left push
    r.rpush("queue:tasks", "task1", "task2", "task3")
    r.lpush("queue:tasks", "urgent_task")  # front mein add
    print(f"List after pushes: {r.lrange('queue:tasks', 0, -1)}")

    # LLEN — length
    print(f"LLEN: {r.llen('queue:tasks')}")

    # LINDEX — element at index
    print(f"LINDEX 0 (first): {r.lindex('queue:tasks', 0)}")
    print(f"LINDEX -1 (last): {r.lindex('queue:tasks', -1)}")

    # LRANGE — range of elements
    print(f"LRANGE [0,2]: {r.lrange('queue:tasks', 0, 2)}")
    print(f"LRANGE all:   {r.lrange('queue:tasks', 0, -1)}")

    # LPOP / RPOP — remove from left/right
    left  = r.lpop("queue:tasks")    # queue behavior (FIFO)
    right = r.rpop("queue:tasks")    # stack behavior (LIFO)
    print(f"LPOP: {left}, RPOP: {right}")

    # LSET — update element at index
    r.lset("queue:tasks", 0, "updated_task1")
    print(f"After LSET: {r.lrange('queue:tasks', 0, -1)}")

    # LINSERT — insert before/after pivot
    r.linsert("queue:tasks", "BEFORE", "updated_task1", "new_first")
    print(f"After LINSERT BEFORE: {r.lrange('queue:tasks', 0, -1)}")

    # LREM — remove occurrences
    r.rpush("queue:tasks", "dup", "dup", "dup")
    r.lrem("queue:tasks", 2, "dup")   # 2 occurrences remove karo
    print(f"After LREM (2 dups): {r.lrange('queue:tasks', 0, -1)}")

    # LTRIM — keep only slice
    r.rpush("queue:tasks", "a", "b", "c", "d", "e")
    r.ltrim("queue:tasks", 0, 2)  # sirf first 3 rakho
    print(f"After LTRIM [0,2]: {r.lrange('queue:tasks', 0, -1)}")

    # LMOVE — atomic move between lists (Redis 6.2+)
    r.rpush("source:list", "item1", "item2")
    moved = r.lmove("source:list", "dest:list", "LEFT", "RIGHT")
    print(f"LMOVE: {moved} → dest: {r.lrange('dest:list', 0, -1)}")

    # BLPOP — blocking pop (timeout=1 second)
    r.rpush("blocking:queue", "blocked_item")
    result = r.blpop("blocking:queue", timeout=1)
    print(f"BLPOP: {result}")  # (queue_name, value)

    # Cleanup
    r.delete("queue:tasks", "source:list", "dest:list", "blocking:queue")
    print("✅ Lists demo complete!")


# ════════════════════════════════════════════
# SECTION 4: SET COMMANDS
# ════════════════════════════════════════════
def demo_sets():
    print("\n" + "="*50)
    print("  SECTION 4: SET COMMANDS")
    print("="*50)

    # SADD — add members (duplicates auto-ignored)
    r.sadd("users:online", "user:1", "user:2", "user:3", "user:4")
    r.sadd("users:premium", "user:2", "user:3", "user:5")

    # SMEMBERS — all members
    print(f"Online users: {r.smembers('users:online')}")

    # SCARD — count
    print(f"Online count: {r.scard('users:online')}")

    # SISMEMBER — membership check
    print(f"user:1 online? {r.sismember('users:online', 'user:1')}")
    print(f"user:99 online? {r.sismember('users:online', 'user:99')}")

    # SMISMEMBER — multiple membership check (Redis 6.2+)
    results = r.smismember("users:online", "user:1", "user:5", "user:99")
    print(f"SMISMEMBER [user:1, user:5, user:99]: {results}")

    # SET Operations — Intersection, Union, Difference
    inter = r.sinter("users:online", "users:premium")     # dono mein
    union = r.sunion("users:online", "users:premium")     # koi bhi ek
    diff  = r.sdiff("users:online", "users:premium")      # online but not premium

    print(f"SINTER (online ∩ premium): {inter}")
    print(f"SUNION (online ∪ premium): {union}")
    print(f"SDIFF  (online - premium): {diff}")

    # SINTERSTORE / SUNIONSTORE / SDIFFSTORE — result ko store karo
    r.sinterstore("users:online_and_premium", "users:online", "users:premium")
    print(f"Stored intersection: {r.smembers('users:online_and_premium')}")

    # SMOVE — ek set se doosre mein move karo
    r.smove("users:online", "users:offline", "user:4")
    print(f"After SMOVE user:4: online={r.smembers('users:online')}")

    # SPOP — random member nikalo
    popped = r.spop("users:online")
    print(f"SPOP random: {popped}")

    # SRANDMEMBER — random member (without removing)
    random_member = r.srandmember("users:online")
    two_random    = r.srandmember("users:online", 2)
    print(f"SRANDMEMBER 1: {random_member}")
    print(f"SRANDMEMBER 2: {two_random}")

    # SREM — specific member remove karo
    r.srem("users:online", "user:2")
    print(f"After SREM user:2: {r.smembers('users:online')}")

    # Cleanup
    r.delete("users:online", "users:premium", "users:online_and_premium", "users:offline")
    print("✅ Sets demo complete!")


# ════════════════════════════════════════════
# SECTION 5: SORTED SET COMMANDS
# ════════════════════════════════════════════
def demo_sorted_sets():
    print("\n" + "="*50)
    print("  SECTION 5: SORTED SET (ZSET) COMMANDS")
    print("="*50)

    # ZADD — add with score
    r.zadd("leaderboard:chess", {
        "Alice":   1500,
        "Bob":     1350,
        "Charlie": 1700,
        "Diana":   1600,
        "Eve":     1450
    })

    # ZRANGE — rank by score (low → high)
    print(f"ZRANGE (low→high): {r.zrange('leaderboard:chess', 0, -1, withscores=True)}")

    # ZREVRANGE — rank by score (high → low) = leaderboard!
    top3 = r.zrevrange("leaderboard:chess", 0, 2, withscores=True)
    print(f"Top 3 (high→low): {top3}")

    # ZRANGEBYSCORE — score range mein
    mid_range = r.zrangebyscore("leaderboard:chess", 1400, 1600, withscores=True)
    print(f"Score 1400-1600: {mid_range}")

    # ZRANK / ZREVRANK — position
    rank = r.zrank("leaderboard:chess", "Alice")
    revrank = r.zrevrank("leaderboard:chess", "Alice")
    print(f"Alice rank (0-indexed, asc): {rank}")
    print(f"Alice revrank (0-indexed, desc): {revrank}")

    # ZSCORE — score fetch
    print(f"Alice score: {r.zscore('leaderboard:chess', 'Alice')}")

    # ZINCRBY — score update
    r.zincrby("leaderboard:chess", 100, "Alice")   # Alice +100
    print(f"Alice score after ZINCRBY +100: {r.zscore('leaderboard:chess', 'Alice')}")

    # ZCARD — member count
    print(f"Total players: {r.zcard('leaderboard:chess')}")

    # ZCOUNT — count in score range
    print(f"Count 1400-1600: {r.zcount('leaderboard:chess', 1400, 1600)}")

    # ZREM — remove member
    r.zrem("leaderboard:chess", "Eve")
    print(f"After ZREM Eve: {r.zrange('leaderboard:chess', 0, -1)}")

    # ZPOPMIN / ZPOPMAX — lowest/highest score remove
    lowest  = r.zpopmin("leaderboard:chess")
    highest = r.zpopmax("leaderboard:chess")
    print(f"ZPOPMIN (lowest): {lowest}")
    print(f"ZPOPMAX (highest): {highest}")

    # ZRANGEBYLEX — same score → lexicographic order
    r.zadd("words", {"apple": 0, "banana": 0, "cherry": 0, "avocado": 0, "blueberry": 0})
    lex_range = r.zrangebylex("words", "[a", "[b\xff")   # 'a' se 'b' tak
    print(f"ZRANGEBYLEX [a-b]: {lex_range}")

    # ZUNIONSTORE / ZINTERSTORE — combine sorted sets
    r.zadd("game1:scores", {"Alice": 100, "Bob": 80})
    r.zadd("game2:scores", {"Alice": 120, "Charlie": 90})
    r.zunionstore("total:scores", ["game1:scores", "game2:scores"])  # scores add ho jaate
    print(f"ZUNIONSTORE total: {r.zrevrange('total:scores', 0, -1, withscores=True)}")

    # Cleanup
    r.delete("leaderboard:chess", "words", "game1:scores", "game2:scores", "total:scores")
    print("✅ Sorted Sets demo complete!")


# ════════════════════════════════════════════
# SECTION 6: SCAN — Production Safe Iteration
# ════════════════════════════════════════════
def demo_scan():
    print("\n" + "="*50)
    print("  SECTION 6: SCAN — Production Safe Key Iteration")
    print("="*50)

    # Test data create karo
    for i in range(50):
        r.set(f"user:{i}:profile", f"data:{i}", ex=300)
    for i in range(20):
        r.set(f"cache:{i}:result", f"cached:{i}", ex=300)

    # ─── KEYS — NEVER in production! ───
    # keys = r.keys("user:*")  # ❌ blocks server!

    # ─── SCAN — Production safe ✅ ───
    # Method 1: scan_iter (recommended — auto handles cursor)
    user_keys = list(r.scan_iter("user:*", count=10))
    print(f"scan_iter 'user:*' found: {len(user_keys)} keys")

    cache_keys = list(r.scan_iter("cache:*", count=10))
    print(f"scan_iter 'cache:*' found: {len(cache_keys)} keys")

    # Method 2: Manual cursor-based SCAN
    print("\nManual SCAN with cursor:")
    cursor = 0
    total_found = 0
    iterations = 0
    while True:
        cursor, keys = r.scan(cursor=cursor, match="user:*", count=20)
        total_found += len(keys)
        iterations += 1
        if cursor == 0:
            break
    print(f"  Found {total_found} user keys in {iterations} iterations")

    # HSCAN — Hash ke fields iterate karo
    r.hset("big:product", mapping={f"attr:{i}": f"value:{i}" for i in range(30)})
    all_attrs = {}
    cursor = 0
    while True:
        cursor, data = r.hscan("big:product", cursor=cursor, match="attr:1*", count=10)
        all_attrs.update(data)
        if cursor == 0:
            break
    print(f"\nHSCAN 'attr:1*': {len(all_attrs)} fields found")

    # SSCAN — Set ke members iterate karo
    r.sadd("big:set", *[f"member:{i}" for i in range(50)])
    found_members = []
    cursor = 0
    while True:
        cursor, members = r.sscan("big:set", cursor=cursor, match="member:2*", count=10)
        found_members.extend(members)
        if cursor == 0:
            break
    print(f"SSCAN 'member:2*': {len(found_members)} members found")

    # ZSCAN — Sorted Set iterate karo
    r.zadd("big:zset", {f"player:{i}": i * 10 for i in range(50)})
    found_players = []
    cursor = 0
    while True:
        cursor, players = r.zscan("big:zset", cursor=cursor, match="player:3*", count=10)
        found_players.extend(players)
        if cursor == 0:
            break
    print(f"ZSCAN 'player:3*': {len(found_players)} players found")

    # Cleanup
    for key in r.scan_iter("user:*"):
        r.delete(key)
    for key in r.scan_iter("cache:*"):
        r.delete(key)
    r.delete("big:product", "big:set", "big:zset")
    print("\n✅ SCAN demo complete!")


# ════════════════════════════════════════════
# SECTION 7: INTERNAL ENCODING
# ════════════════════════════════════════════
def demo_encoding():
    print("\n" + "="*50)
    print("  SECTION 7: INTERNAL ENCODING")
    print("="*50)

    # STRING encodings
    r.set("int_key", 12345)
    r.set("short_str", "Hello")
    r.set("long_str", "x" * 45)  # >44 chars

    print("STRING encodings:")
    print(f"  int (12345):    {r.object('encoding', 'int_key')}")      # int
    print(f"  short (<= 44):  {r.object('encoding', 'short_str')}")    # embstr
    print(f"  long (>44):     {r.object('encoding', 'long_str')}")     # raw

    # HASH encodings
    r.hset("small:hash", mapping={f"f{i}": f"v{i}" for i in range(3)})
    r.hset("big:hash2", mapping={f"f{i}": f"v{i}" for i in range(200)})  # > 128 fields

    print("\nHASH encodings:")
    print(f"  small hash (3 fields):   {r.object('encoding', 'small:hash')}")   # listpack
    print(f"  large hash (200 fields): {r.object('encoding', 'big:hash2')}")    # hashtable

    # LIST encodings
    r.rpush("small:list", *[f"item{i}" for i in range(3)])
    r.rpush("big:list", *[f"item{i}" for i in range(200)])  # > 128 items

    print("\nLIST encodings:")
    print(f"  small list (3 items):   {r.object('encoding', 'small:list')}")    # listpack
    print(f"  large list (200 items): {r.object('encoding', 'big:list')}")      # quicklist

    # SET encodings
    r.sadd("int:set", *[i for i in range(5)])     # all integers, < 512
    r.sadd("str:set", *[f"str{i}" for i in range(5)])  # strings
    r.sadd("big:set2", *[f"item{i}" for i in range(200)])  # large

    print("\nSET encodings:")
    print(f"  integer set (5 ints):   {r.object('encoding', 'int:set')}")   # intset
    print(f"  string set (5 strs):    {r.object('encoding', 'str:set')}")   # listpack
    print(f"  large set (200 items):  {r.object('encoding', 'big:set2')}")  # hashtable

    # ZSET encodings
    r.zadd("small:zset", {"a": 1.0, "b": 2.0})
    r.zadd("big:zset2", {f"member{i}": float(i) for i in range(200)})

    print("\nZSET encodings:")
    print(f"  small zset (2 members):   {r.object('encoding', 'small:zset')}")  # listpack
    print(f"  large zset (200 members): {r.object('encoding', 'big:zset2')}")   # skiplist

    print("\n💡 Why it matters:")
    print("  listpack  = compact memory (no pointers)")
    print("  hashtable = O(1) lookup (faster for large data)")
    print("  Redis auto-converts when threshold exceeded")

    # Cleanup
    for key in ["int_key", "short_str", "long_str", "small:hash", "big:hash2",
                "small:list", "big:list", "int:set", "str:set", "big:set2",
                "small:zset", "big:zset2"]:
        r.delete(key)
    print("\n✅ Encoding demo complete!")


# ════════════════════════════════════════════
# SECTION 8: KEY NAMING & TTL BEST PRACTICES
# ════════════════════════════════════════════
def demo_key_naming():
    print("\n" + "="*50)
    print("  SECTION 8: KEY NAMING CONVENTIONS & TTL")
    print("="*50)

    # ─── Key naming patterns ───
    # Pattern: object:id:field
    keys_example = {
        "user:1001:profile":          "User 1001's profile data",
        "user:1001:sessions":         "User 1001's active sessions",
        "order:uuid123:status":       "Order UUID status",
        "product:42:inventory":       "Product 42 inventory count",
        "cache:product:42":           "Cached product 42 data",
        "cache:search:laptops:pg1":   "Cached search results",
        "session:abc123def456":       "Session token data",
        "lock:order:processing:101":  "Processing lock for order 101",
        "queue:emails:welcome":       "Welcome email queue",
        "counter:page_views:today":   "Today's page view count",
        "rate:user:1001:api":         "API rate limit for user 1001",
        "leaderboard:game:chess":     "Chess game leaderboard",
    }

    print("Key naming examples:")
    for key, desc in keys_example.items():
        print(f"  {key:<40} → {desc}")

    # ─── TTL Strategy ───
    print("\nTTL Strategy:")

    # Short TTL — session tokens, OTPs
    r.setex("session:xyz789", 1800, "user_session_data")    # 30 min
    r.setex("otp:user:1001", 300, "123456")                 # 5 min

    # Medium TTL — cached DB results
    r.setex("cache:product:42", 3600, '{"id":42,"name":"Laptop"}')  # 1 hr

    # Long TTL — leaderboards, aggregated data
    r.setex("leaderboard:daily", 86400, "daily_scores")     # 24 hr

    # No TTL — permanent config, settings
    r.set("config:app:version", "1.0.0")  # permanent

    print("  session:xyz789  → TTL:", r.ttl("session:xyz789"), "s (30 min)")
    print("  otp:user:1001   → TTL:", r.ttl("otp:user:1001"), "s (5 min)")
    print("  cache:product:42→ TTL:", r.ttl("cache:product:42"), "s (1 hr)")
    print("  config:app:ver  → TTL:", r.ttl("config:app:version"), "(permanent)")

    # EXPIREAT — specific timestamp pe expire
    import time
    future_ts = int(time.time()) + 7200  # 2 hours from now
    r.set("temp:report:2024", "report_data")
    r.expireat("temp:report:2024", future_ts)
    print(f"  temp:report:2024 → EXPIREAT: {r.ttl('temp:report:2024')}s (~2hr)")

    # PEXPIRE / PEXPIREAT — millisecond precision
    r.set("precise:expiry", "short_lived")
    r.pexpire("precise:expiry", 5000)  # 5000 ms = 5 seconds
    print(f"  precise:expiry  → PTTL: {r.pttl('precise:expiry')}ms (5 sec)")

    # OBJECT IDLETIME — kitne seconds se use nahi hua
    r.set("idle:key", "value")
    time.sleep(0.1)
    # idle_time = r.object('idletime', 'idle:key')
    # print(f"  idle:key idletime: {idle_time}s")

    # MEMORY USAGE — specific key ka memory
    r.set("memory:test", "x" * 1000)
    mem = r.memory_usage("memory:test")
    print(f"\n  MEMORY USAGE 'memory:test': {mem} bytes")

    # Cleanup
    r.delete("session:xyz789", "otp:user:1001", "cache:product:42",
             "leaderboard:daily", "config:app:version", "temp:report:2024",
             "precise:expiry", "idle:key", "memory:test")
    print("\n✅ Key naming & TTL demo complete!")


# ════════════════════════════════════════════
# MAIN RUNNER
# ════════════════════════════════════════════
def main():
    # Redis connection test
    try:
        r.ping()
        print("✅ Redis connected!")
    except redis.ConnectionError:
        print("❌ Redis not running! Start: docker run -d -p 6379:6379 redis:7-alpine")
        sys.exit(1)

    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"

    demos = {
        "strings":  demo_strings,
        "hashes":   demo_hashes,
        "lists":    demo_lists,
        "sets":     demo_sets,
        "sorted":   demo_sorted_sets,
        "scan":     demo_scan,
        "encoding": demo_encoding,
        "naming":   demo_key_naming,
    }

    if cmd == "all":
        for fn in demos.values():
            fn()
    elif cmd in demos:
        demos[cmd]()
    else:
        print(f"Usage: python {sys.argv[0]} [{'|'.join(demos.keys())}|all]")


if __name__ == "__main__":
    main()
