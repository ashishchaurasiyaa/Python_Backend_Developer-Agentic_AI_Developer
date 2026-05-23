"""
Redis Deep Dive — Practical Examples
═══════════════════════════════════════════════════════════════
Run: python 02_redis_practical.py
Install: pip install redis[hiredis] asyncio

Topics:
  - All data structures (String, Hash, List, Set, SortedSet, Stream)
  - Distributed lock (Redlock pattern)
  - Rate limiting (sliding window + token bucket)
  - Cache patterns (cache-aside, stampede prevention)
  - Pub/Sub (publish + subscribe demo)
  - Redis Transactions (MULTI/EXEC + WATCH)
  - Consumer groups (Streams)

INTERVIEW QUICK REFERENCE at bottom.
"""

import asyncio
import time
import uuid
import json
import redis.asyncio as aioredis

REDIS_URL = "redis://localhost:6379"


async def get_redis():
    return await aioredis.from_url(REDIS_URL, decode_responses=True)


# ═══════════════════════════════════════════════════════════
# SECTION 1: All Data Structures
# ═══════════════════════════════════════════════════════════

async def demo_strings(r):
    print("\n--- STRINGS ---")
    # Basic set/get
    await r.set("user:1:name", "Alice")
    name = await r.get("user:1:name")
    print(f"  GET user:1:name = {name}")

    # TTL
    await r.setex("session:abc123", 3600, json.dumps({"user_id": 1, "role": "admin"}))
    ttl = await r.ttl("session:abc123")
    print(f"  session TTL = {ttl}s")

    # Atomic counter
    await r.set("post:42:views", 0)
    for _ in range(5):
        await r.incr("post:42:views")
    views = await r.get("post:42:views")
    print(f"  post:42:views after 5 incr = {views}")

    # SET NX — only if not exists (distributed lock simple version)
    result1 = await r.setnx("lock:job:1", "worker-1")
    result2 = await r.setnx("lock:job:1", "worker-2")  # fails
    print(f"  SETNX results: {result1}, {result2} (second should be 0)")
    await r.delete("lock:job:1")


async def demo_hashes(r):
    print("\n--- HASHES ---")
    # Set multiple fields
    await r.hset("user:1", mapping={
        "name": "Alice", "email": "alice@test.com",
        "plan": "premium", "credits": "500"
    })
    # Get single field
    name = await r.hget("user:1", "name")
    print(f"  HGET name = {name}")

    # Get all fields
    user = await r.hgetall("user:1")
    print(f"  HGETALL = {user}")

    # Increment field (shopping cart quantity)
    await r.hset("cart:user:1", mapping={"item:42": "1", "item:99": "2"})
    await r.hincrby("cart:user:1", "item:42", 2)  # +2
    cart = await r.hgetall("cart:user:1")
    print(f"  Cart after increment: {cart}")


async def demo_lists(r):
    print("\n--- LISTS (Queue) ---")
    await r.delete("task_queue")

    # Producer: push tasks
    await r.rpush("task_queue", "task:email:1", "task:email:2", "task:sms:1")
    length = await r.llen("task_queue")
    print(f"  Queue length: {length}")

    # Consumer: pop tasks (FIFO)
    task = await r.lpop("task_queue")
    print(f"  Popped: {task}")
    remaining = await r.lrange("task_queue", 0, -1)
    print(f"  Remaining: {remaining}")

    # Activity feed (newest first, max 100 items)
    await r.delete("feed:user:1")
    for i in range(5):
        await r.lpush("feed:user:1", f"post:{i}")
    await r.ltrim("feed:user:1", 0, 99)  # keep max 100
    feed = await r.lrange("feed:user:1", 0, 4)
    print(f"  Feed (newest first): {feed}")


async def demo_sets(r):
    print("\n--- SETS ---")
    await r.delete("post:42:viewers", "user:1:tags", "user:2:tags")

    # Unique visitors
    for uid in [1, 2, 3, 2, 1]:  # duplicates ignored
        await r.sadd("post:42:viewers", f"user:{uid}")
    count = await r.scard("post:42:viewers")
    print(f"  Unique viewers (5 adds, 2 dups): {count}")

    # Set operations
    await r.sadd("user:1:tags", "python", "django", "postgres")
    await r.sadd("user:2:tags", "python", "fastapi", "redis")
    common   = await r.sinter("user:1:tags", "user:2:tags")
    combined = await r.sunion("user:1:tags", "user:2:tags")
    print(f"  Common tags: {common}")
    print(f"  All tags: {combined}")


async def demo_sorted_sets(r):
    print("\n--- SORTED SETS (Leaderboard) ---")
    await r.delete("leaderboard")

    players = {"alice": 1500, "bob": 1200, "charlie": 1800,
               "diana": 1650, "evan": 1350}
    await r.zadd("leaderboard", players)

    # Top 3
    top3 = await r.zrange("leaderboard", 0, 2, withscores=True, rev=True)
    print("  Top 3:")
    for i, (player, score) in enumerate(top3, 1):
        print(f"    #{i} {player}: {score:.0f}")

    # Get rank (0-indexed)
    rank = await r.zrevrank("leaderboard", "alice")
    print(f"  Alice rank: #{rank + 1}")

    # Add score
    await r.zincrby("leaderboard", 200, "alice")
    new_score = await r.zscore("leaderboard", "alice")
    print(f"  Alice new score: {new_score:.0f}")

    # Delayed tasks
    await r.delete("delayed_tasks")
    now = time.time()
    await r.zadd("delayed_tasks", {
        "task:cleanup": now + 10,   # 10 seconds from now
        "task:report": now + 30,    # 30 seconds from now
        "task:backup": now - 5,     # overdue!
    })
    overdue = await r.zrangebyscore("delayed_tasks", 0, time.time())
    print(f"  Overdue tasks: {overdue}")


# ═══════════════════════════════════════════════════════════
# SECTION 2: Distributed Lock
# ═══════════════════════════════════════════════════════════

class RedisLock:
    """
    INTERVIEW: Distributed lock kyu?
    Prevent multiple workers from running same task.
    e.g., cron job pada 3 pods → sirf 1 run karo.

    INTERVIEW: Why SET NX EX?
    Atomic: SET only if Not eXists + set Expiry
    If worker crashes, lock auto-expires (no deadlock).
    """
    def __init__(self, redis, key: str, timeout: int = 30):
        self.redis   = redis
        self.key     = f"lock:{key}"
        self.timeout = timeout
        self.token   = str(uuid.uuid4())

    async def acquire(self) -> bool:
        result = await self.redis.set(
            self.key, self.token, nx=True, ex=self.timeout
        )
        return result is True

    async def release(self):
        """Release ONLY if we own it — Lua for atomicity."""
        script = """
        if redis.call("GET", KEYS[1]) == ARGV[1] then
            return redis.call("DEL", KEYS[1])
        else
            return 0
        end
        """
        await self.redis.eval(script, 1, self.key, self.token)

    async def __aenter__(self):
        acquired = await self.acquire()
        if not acquired:
            raise RuntimeError(f"Lock busy: {self.key}")
        return self

    async def __aexit__(self, *args):
        await self.release()


async def demo_lock(r):
    print("\n--- DISTRIBUTED LOCK ---")
    lock = RedisLock(r, "daily_report", timeout=10)

    # First acquire succeeds
    ok1 = await lock.acquire()
    print(f"  First acquire: {ok1}")

    # Second acquire fails (lock held)
    lock2 = RedisLock(r, "daily_report", timeout=10)
    ok2 = await lock2.acquire()
    print(f"  Second acquire (should fail): {ok2}")

    # Release
    await lock.release()
    ok3 = await lock2.acquire()
    print(f"  After release, third acquire: {ok3}")
    await lock2.release()


# ═══════════════════════════════════════════════════════════
# SECTION 3: Rate Limiting
# ═══════════════════════════════════════════════════════════

async def rate_limit_sliding_window(r, user_id: str, limit: int = 5, window: int = 60) -> bool:
    """
    Sliding window rate limiter using Sorted Set.
    INTERVIEW: Kaise kaam karta hai?
      - Score = timestamp (milliseconds)
      - Window se purane entries remove karo
      - Count karo — limit exceed kiya kya?
      - Agar nahi → add karo current timestamp
    """
    key = f"rate:{user_id}"
    now = int(time.time() * 1000)
    window_start = now - (window * 1000)

    pipe = r.pipeline()
    # Remove old entries outside window
    pipe.zremrangebyscore(key, 0, window_start)
    # Count current entries
    pipe.zcard(key)
    # Add current request
    pipe.zadd(key, {str(now): now})
    # Set TTL
    pipe.expire(key, window)
    results = await pipe.execute()

    count = results[1]  # count before adding current
    return count < limit  # True = allowed


async def demo_rate_limiting(r):
    print("\n--- RATE LIMITING (Sliding Window, 5 req/10s) ---")
    await r.delete("rate:user_test")

    for i in range(7):
        allowed = await rate_limit_sliding_window(r, "user_test", limit=5, window=10)
        status = "✓ allowed" if allowed else "✗ blocked"
        print(f"  Request {i+1}: {status}")


# ═══════════════════════════════════════════════════════════
# SECTION 4: Redis Transactions (MULTI/EXEC)
# ═══════════════════════════════════════════════════════════

async def demo_transactions(r):
    print("\n--- TRANSACTIONS (MULTI/EXEC) ---")
    await r.set("credits:alice", 500)
    await r.set("credits:bob", 200)

    # Transfer 100 credits from alice to bob
    pipe = r.pipeline(transaction=True)
    await pipe.decrby("credits:alice", 100)
    await pipe.incrby("credits:bob", 100)
    results = await pipe.execute()
    print(f"  Transfer results: alice={results[0]}, bob={results[1]}")

    alice = await r.get("credits:alice")
    bob   = await r.get("credits:bob")
    print(f"  Final: alice={alice}, bob={bob}")


# ═══════════════════════════════════════════════════════════
# SECTION 5: Redis Streams (Event Sourcing)
# ═══════════════════════════════════════════════════════════

async def demo_streams(r):
    print("\n--- STREAMS (Event Sourcing) ---")
    stream_key = "order_events"
    group_name = "email-service"

    # Cleanup
    await r.delete(stream_key)

    # Produce events
    ids = []
    for i in range(5):
        event_id = await r.xadd(stream_key, {
            "type":     "order_placed",
            "order_id": f"ord-{100+i}",
            "user_id":  str(i),
            "amount":   str(100 * (i + 1)),
        })
        ids.append(event_id)
    print(f"  Produced 5 events: {ids[0]} ... {ids[-1]}")

    # Create consumer group
    try:
        await r.xgroup_create(stream_key, group_name, id="0", mkstream=True)
    except Exception:
        pass  # group already exists

    # Consume messages
    messages = await r.xreadgroup(
        groupname=group_name,
        consumername="worker-1",
        streams={stream_key: ">"},
        count=3,
    )
    print(f"  Consumer group read 3 messages:")
    for stream, msgs in messages:
        for msg_id, data in msgs:
            print(f"    [{msg_id}] order_id={data.get('order_id')} amount=${data.get('amount')}")
            # ACK — processed successfully
            await r.xack(stream_key, group_name, msg_id)

    # Pending messages (not acked)
    pending = await r.xpending(stream_key, group_name)
    print(f"  Pending (not acked): {pending['pending']}")


# ═══════════════════════════════════════════════════════════
# SECTION 6: Token Bucket Rate Limiter
# ═══════════════════════════════════════════════════════════

async def token_bucket_rate_limit(r, user_id: str, capacity: int = 10, refill_rate: float = 1.0) -> bool:
    """
    Token Bucket algorithm using Lua (atomic).

    INTERVIEW: Sliding window vs Token bucket?
    Sliding window:  exact count in window — strict limit
    Token bucket:    allows short bursts (up to capacity),
                     then refills at `refill_rate` tokens/second
                     More realistic for API clients (burst-friendly)

    How it works:
      - Bucket has max `capacity` tokens
      - Each request consumes 1 token
      - Tokens refill at `refill_rate` per second
      - Request allowed if tokens >= 1, else blocked
    """
    script = """
    local key       = KEYS[1]
    local capacity  = tonumber(ARGV[1])
    local refill    = tonumber(ARGV[2])
    local now       = tonumber(ARGV[3])

    local bucket = redis.call("HMGET", key, "tokens", "last_refill")
    local tokens      = tonumber(bucket[1]) or capacity
    local last_refill = tonumber(bucket[2]) or now

    -- Refill tokens based on elapsed time
    local elapsed = now - last_refill
    tokens = math.min(capacity, tokens + elapsed * refill)

    if tokens >= 1 then
        tokens = tokens - 1
        redis.call("HMSET", key, "tokens", tokens, "last_refill", now)
        redis.call("EXPIRE", key, 3600)
        return 1   -- allowed
    else
        redis.call("HMSET", key, "tokens", tokens, "last_refill", now)
        redis.call("EXPIRE", key, 3600)
        return 0   -- blocked
    end
    """
    key = f"tokenbucket:{user_id}"
    now = time.time()
    result = await r.eval(script, 1, key, capacity, refill_rate, now)
    return result == 1


async def demo_token_bucket(r):
    print("\n--- TOKEN BUCKET RATE LIMITER (burst-friendly) ---")
    await r.delete("tokenbucket:user_demo")

    # Burst: 5 rapid requests allowed (capacity=5)
    print("  Burst of 5 rapid requests (capacity=5, refill=1/sec):")
    for i in range(7):
        allowed = await token_bucket_rate_limit(r, "user_demo", capacity=5, refill_rate=1.0)
        status = "✓ allowed" if allowed else "✗ blocked"
        print(f"  Request {i+1}: {status}")

    # Wait 2 seconds → 2 tokens refilled
    print("  Waiting 2 seconds for token refill...")
    await asyncio.sleep(2)
    for i in range(3):
        allowed = await token_bucket_rate_limit(r, "user_demo", capacity=5, refill_rate=1.0)
        status = "✓ allowed" if allowed else "✗ blocked"
        print(f"  After refill request {i+1}: {status}")


# ═══════════════════════════════════════════════════════════
# SECTION 7: Pub/Sub
# ═══════════════════════════════════════════════════════════

async def demo_pubsub(r):
    print("\n--- PUB/SUB ---")
    """
    INTERVIEW: Pub/Sub kab use karte hain?
    Real-time notifications — chat, live scores, dashboard updates.
    Fire-and-forget: subscriber offline → message LOST.
    Use Streams if you need persistence/reliability.

    INTERVIEW: Pub/Sub vs Streams?
    Pub/Sub:  no persistence, no consumer groups, subscriber offline = lost
    Streams:  persistent log, consumer groups, redelivery on crash
    """

    received_messages = []

    async def subscriber():
        """Subscriber listens on a channel."""
        sub_r = await aioredis.from_url(REDIS_URL, decode_responses=True)
        pubsub = sub_r.pubsub()
        await pubsub.subscribe("notifications:user:1")
        print("  Subscriber: listening on 'notifications:user:1'...")

        count = 0
        async for message in pubsub.listen():
            if message["type"] == "message":
                received_messages.append(message["data"])
                print(f"  Subscriber received: {message['data']}")
                count += 1
                if count >= 3:
                    break

        await pubsub.unsubscribe("notifications:user:1")
        await sub_r.aclose()

    async def publisher():
        """Publisher sends messages after a short delay."""
        await asyncio.sleep(0.1)  # let subscriber connect first
        events = [
            '{"type": "like", "post_id": 42, "user": "alice"}',
            '{"type": "comment", "post_id": 42, "user": "bob"}',
            '{"type": "follow", "follower": "charlie"}',
        ]
        for event in events:
            await r.publish("notifications:user:1", event)
            print(f"  Publisher sent: {event[:50]}...")
            await asyncio.sleep(0.05)

    # Run subscriber + publisher concurrently
    await asyncio.gather(subscriber(), publisher())
    print(f"  Total messages received: {len(received_messages)}")

    # Pattern subscribe (wildcard)
    print("\n  Pattern subscribe demo (notifications:*):")
    sub_r2 = await aioredis.from_url(REDIS_URL, decode_responses=True)
    pubsub2 = sub_r2.pubsub()
    await pubsub2.psubscribe("notifications:*")  # wildcard

    # Publish to different channels
    await r.publish("notifications:user:2", "user2 message")
    await r.publish("notifications:admin",  "admin alert")

    count = 0
    async for message in pubsub2.listen():
        if message["type"] == "pmessage":
            print(f"  Pattern match [{message['channel']}]: {message['data']}")
            count += 1
            if count >= 2:
                break

    await pubsub2.punsubscribe("notifications:*")
    await sub_r2.aclose()


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

async def main():
    print("Connecting to Redis...")
    try:
        r = await get_redis()
        await r.ping()
    except Exception as e:
        print(f"Connection failed: {e}")
        print("Make sure Redis is running: docker run -d -p 6379:6379 redis")
        return
    print("✓ Connected")

    await demo_strings(r)
    await demo_hashes(r)
    await demo_lists(r)
    await demo_sets(r)
    await demo_sorted_sets(r)
    await demo_lock(r)
    await demo_rate_limiting(r)
    await demo_token_bucket(r)
    await demo_transactions(r)
    await demo_streams(r)
    await demo_pubsub(r)

    await r.aclose()
    print("\n✓ All demos complete!")


# ═══════════════════════════════════════════════════════════
# INTERVIEW QUICK REFERENCE
# ═══════════════════════════════════════════════════════════
"""
Q: Redis data structure kaunsa kab?
A: String  → counter, cache, session, simple flag
   Hash    → object fields (user profile, cart)
   List    → queue (RPUSH/LPOP), stack (LPUSH/LPOP), feed
   Set     → unique members, set operations
   Sorted Set → leaderboard, delayed tasks, rate limit
   Stream  → event log, reliable message queue

Q: Redis persistence options?
A: RDB:  snapshot (point-in-time backup) — can lose data since last snap
   AOF:  every write logged — max 1 second loss (everysec)
   Both: production recommendation

Q: MULTI/EXEC vs Lua script?
A: MULTI/EXEC: batch commands, atomic execution
   Lua: truly atomic + conditional logic (read-compute-write)

Q: WATCH kya karta hai?
A: Optimistic locking — watched key change pe EXEC fail karta hai
   Client retry karta hai → compare-and-swap pattern

Q: Distributed lock requirements?
A: 1. SET NX EX (atomic acquire + expiry)
   2. Unique token (release sirf owner kare — Lua)
   3. Expiry (auto-release on crash)

Q: Cache stampede kya hai? Solution?
A: Thousands of requests hit DB when cache expires simultaneously
   Solution: probabilistic early expiry OR
             use lock (only 1 request fetches, rest wait)

Q: Pub/Sub vs Streams?
A: Pub/Sub: fire-and-forget, subscriber offline → message lost
   Streams: persistent, consumer groups, redelivery on failure

Q: Sliding window vs Token bucket?
A: Sliding window: strict count in time window — no bursting
   Token bucket:   allows burst up to capacity, then refills
                   More natural for API clients
   Both use Sorted Sets or Lua for atomicity

Q: Redis Lua script kyu?
A: Truly atomic — no interleaving, read-compute-write in one shot
   MULTI/EXEC: atomic batch but no conditional logic
   Lua: conditional logic + atomic = best for rate limiting, locks
"""

if __name__ == "__main__":
    asyncio.run(main())
