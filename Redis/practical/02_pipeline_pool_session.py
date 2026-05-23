"""
Redis Practical 02 — Pipeline, Connection Pool & Session Store
Run: python 02_pipeline_pool_session.py [pipeline|pool|session|transaction|all]

Prerequisites:
  pip install redis[hiredis] fastapi uvicorn
  docker run -d --name redis -p 6379:6379 redis:7-alpine
"""

import asyncio
import json
import time
import uuid
import sys
import hashlib
from datetime import datetime

import redis
import redis.asyncio as aioredis

# ─── Sync connection ───
r = redis.Redis(host='localhost', port=6379, decode_responses=True)


# ════════════════════════════════════════════
# SECTION 1: PIPELINE — Sync
# ════════════════════════════════════════════
def demo_pipeline_sync():
    print("\n" + "="*50)
    print("  SECTION 1: PIPELINE — Sync")
    print("="*50)

    # ─── Without Pipeline — Slow ───
    print("\n📊 Performance Comparison:")
    start = time.time()
    for i in range(200):
        r.set(f"nopipe:key:{i}", f"value:{i}", ex=60)
    elapsed_no_pipe = time.time() - start
    print(f"  Without pipeline (200 SETs): {elapsed_no_pipe:.4f}s")

    # ─── With Pipeline — Fast ───
    start = time.time()
    pipe = r.pipeline(transaction=False)  # non-atomic (faster)
    for i in range(200):
        pipe.set(f"pipe:key:{i}", f"value:{i}", ex=60)
    results = pipe.execute()
    elapsed_pipe = time.time() - start
    print(f"  With pipeline (200 SETs):    {elapsed_pipe:.4f}s")
    print(f"  Speedup: {elapsed_no_pipe / elapsed_pipe:.1f}x faster ✅")
    print(f"  All success: {all(results)}")

    # ─── Pipeline with Mixed Commands ───
    print("\n🔀 Mixed Commands Pipeline:")
    pipe = r.pipeline()
    pipe.set("user:500:name", "Alice")
    pipe.set("user:500:email", "alice@example.com")
    pipe.hset("user:500:profile", mapping={"age": "28", "city": "Mumbai", "role": "admin"})
    pipe.incr("counter:new_users")
    pipe.expire("user:500:name", 3600)
    pipe.expire("user:500:email", 3600)
    pipe.lpush("recent:signups", "user:500")
    pipe.ltrim("recent:signups", 0, 9)   # keep last 10

    mixed_results = pipe.execute()
    print(f"  Pipeline results: {mixed_results}")

    # ─── Pipeline Bulk READ ───
    print("\n📖 Bulk Read Pipeline:")
    pipe = r.pipeline()
    user_keys = ["user:500:name", "user:500:email"]
    for key in user_keys:
        pipe.get(key)
    pipe.hgetall("user:500:profile")
    pipe.lrange("recent:signups", 0, -1)
    name, email, profile, recent = pipe.execute()
    print(f"  Name: {name}")
    print(f"  Email: {email}")
    print(f"  Profile: {profile}")
    print(f"  Recent signups: {recent}")

    # Cleanup
    for key in r.scan_iter("nopipe:key:*"):
        r.delete(key)
    for key in r.scan_iter("pipe:key:*"):
        r.delete(key)
    r.delete("user:500:name", "user:500:email", "user:500:profile",
             "counter:new_users", "recent:signups")
    print("\n✅ Sync Pipeline demo complete!")


# ════════════════════════════════════════════
# SECTION 2: PIPELINE — Async
# ════════════════════════════════════════════
async def demo_pipeline_async():
    print("\n" + "="*50)
    print("  SECTION 2: PIPELINE — Async")
    print("="*50)

    r_async = aioredis.Redis(host='localhost', port=6379, decode_responses=True)

    # ─── Async Pipeline — non-atomic ───
    print("\n🚀 Async Pipeline (non-atomic, fast):")
    start = time.time()
    async with r_async.pipeline(transaction=False) as pipe:
        for i in range(200):
            pipe.set(f"async:key:{i}", f"value:{i}", ex=60)
        results = await pipe.execute()
    print(f"  200 async SETs: {time.time() - start:.4f}s")
    print(f"  All success: {all(results)}")

    # ─── Async Pipeline — atomic (MULTI/EXEC) ───
    print("\n🔒 Atomic Pipeline (MULTI/EXEC):")
    async with r_async.pipeline(transaction=True) as pipe:
        pipe.incr("order:counter")
        pipe.lpush("recent:orders", f"order:{int(time.time())}")
        pipe.ltrim("recent:orders", 0, 99)    # keep last 100
        pipe.zadd("orders:timeline", {f"order:{int(time.time())}": time.time()})
        atomic_results = await pipe.execute()
    print(f"  Atomic results: {atomic_results}")

    # ─── Async Bulk Read ───
    print("\n📖 Async Bulk Read:")
    # First seed some data
    async with r_async.pipeline(transaction=False) as pipe:
        for i in range(5):
            pipe.set(f"product:{i}:price", str(100 * (i + 1)), ex=300)
        await pipe.execute()

    async with r_async.pipeline(transaction=False) as pipe:
        for i in range(5):
            pipe.get(f"product:{i}:price")
        prices = await pipe.execute()
    print(f"  Product prices: {prices}")

    # Cleanup
    async for key in r_async.scan_iter("async:key:*"):
        await r_async.delete(key)
    async for key in r_async.scan_iter("product:*:price"):
        await r_async.delete(key)
    await r_async.delete("order:counter", "recent:orders", "orders:timeline")
    await r_async.aclose()
    print("\n✅ Async Pipeline demo complete!")


# ════════════════════════════════════════════
# SECTION 3: CONNECTION POOL
# ════════════════════════════════════════════
def demo_connection_pool_sync():
    print("\n" + "="*50)
    print("  SECTION 3: CONNECTION POOL — Sync")
    print("="*50)

    # ─── Connection Pool create karo ───
    pool = redis.ConnectionPool(
        host='localhost',
        port=6379,
        db=0,
        max_connections=20,           # max 20 simultaneous connections
        decode_responses=True,
        socket_timeout=5,             # 5 sec read timeout
        socket_connect_timeout=2,     # 2 sec connect timeout
        retry_on_timeout=True,
        health_check_interval=30,     # 30 sec background health check
    )

    # Pool se Redis client banao
    r_pool = redis.Redis(connection_pool=pool)

    # Pool stats
    print(f"Pool max connections: {pool.max_connections}")
    print(f"Pool created connections: {pool._created_connections}")

    # Multiple operations — same pool reuse
    r_pool.set("pool:test:1", "value1", ex=60)
    r_pool.set("pool:test:2", "value2", ex=60)
    r_pool.set("pool:test:3", "value3", ex=60)

    print(f"Pool created connections after 3 ops: {pool._created_connections}")

    # Pipeline with pool
    pipe = r_pool.pipeline()
    pipe.mset({"pool:a": "1", "pool:b": "2", "pool:c": "3"})
    pipe.execute()

    # Cleanup
    r_pool.delete("pool:test:1", "pool:test:2", "pool:test:3",
                  "pool:a", "pool:b", "pool:c")

    # Pool close karo (app shutdown pe)
    pool.disconnect()
    print("Pool disconnected!")
    print("✅ Sync Connection Pool demo complete!")


async def demo_connection_pool_async():
    print("\n⚡ Async Connection Pool:")

    # Async pool
    async_pool = aioredis.ConnectionPool(
        host='localhost',
        port=6379,
        db=0,
        max_connections=50,     # production: 50-100
        decode_responses=True,
    )

    r_async = aioredis.Redis(connection_pool=async_pool)

    # Concurrent requests — pool reuse test
    async def concurrent_task(task_id: int):
        key = f"concurrent:{task_id}"
        await r_async.set(key, f"data:{task_id}", ex=60)
        val = await r_async.get(key)
        await r_async.delete(key)
        return val

    # 10 concurrent tasks
    tasks = [concurrent_task(i) for i in range(10)]
    results = await asyncio.gather(*tasks)
    print(f"  10 concurrent tasks completed: {len(results)} results")
    print(f"  Sample: {results[:3]}")

    await r_async.aclose()
    await async_pool.aclose()
    print("  Async pool closed!")


# ════════════════════════════════════════════
# SECTION 4: SESSION STORE
# ════════════════════════════════════════════
class SessionStore:
    """Production-ready Redis Session Store"""

    def __init__(self, redis_client, ttl: int = 86400):
        self.redis = redis_client
        self.ttl = ttl  # 24 hours default

    def create(self, user_data: dict) -> str:
        """New session create karo — session_id return"""
        session_id = str(uuid.uuid4())
        session_data = {
            **user_data,
            "session_id":  session_id,
            "created_at":  datetime.now().isoformat(),
            "last_active": datetime.now().isoformat(),
        }
        self.redis.setex(
            f"session:{session_id}",
            self.ttl,
            json.dumps(session_data)
        )
        # User ke sessions track karo (for bulk delete)
        self.redis.sadd(f"user:{user_data['user_id']}:sessions", session_id)
        self.redis.expire(f"user:{user_data['user_id']}:sessions", self.ttl * 2)
        return session_id

    def get(self, session_id: str) -> dict | None:
        """Session fetch + TTL refresh"""
        raw = self.redis.get(f"session:{session_id}")
        if not raw:
            return None

        session = json.loads(raw)
        # Last active update + TTL refresh (sliding window)
        session["last_active"] = datetime.now().isoformat()
        self.redis.setex(f"session:{session_id}", self.ttl, json.dumps(session))
        return session

    def delete(self, session_id: str) -> bool:
        """Session delete (logout)"""
        raw = self.redis.get(f"session:{session_id}")
        if raw:
            session = json.loads(raw)
            # User's session set se bhi remove karo
            self.redis.srem(
                f"user:{session['user_id']}:sessions",
                session_id
            )
        return bool(self.redis.delete(f"session:{session_id}"))

    def delete_all_for_user(self, user_id: int):
        """User ke sabhi sessions delete karo (password change, security)"""
        sessions_key = f"user:{user_id}:sessions"
        session_ids = self.redis.smembers(sessions_key)

        if session_ids:
            # All session keys delete karo
            pipe = self.redis.pipeline()
            for sid in session_ids:
                pipe.delete(f"session:{sid}")
            pipe.delete(sessions_key)
            pipe.execute()
            print(f"  Deleted {len(session_ids)} sessions for user:{user_id}")
        else:
            print(f"  No active sessions for user:{user_id}")

    def get_user_sessions(self, user_id: int) -> list:
        """User ke sab active sessions list karo"""
        sessions_key = f"user:{user_id}:sessions"
        session_ids = self.redis.smembers(sessions_key)
        sessions = []
        for sid in session_ids:
            raw = self.redis.get(f"session:{sid}")
            if raw:
                sessions.append(json.loads(raw))
        return sessions

    def extend(self, session_id: str, extra_seconds: int = 3600) -> bool:
        """Session TTL extend karo"""
        current_ttl = self.redis.ttl(f"session:{session_id}")
        if current_ttl <= 0:
            return False
        self.redis.expire(f"session:{session_id}", current_ttl + extra_seconds)
        return True


def demo_session_store():
    print("\n" + "="*50)
    print("  SECTION 4: SESSION STORE")
    print("="*50)

    store = SessionStore(r, ttl=3600)  # 1 hour sessions

    # ─── Login — session create ───
    print("\n🔐 Login Flow:")
    user_data = {
        "user_id":  1001,
        "username": "alice",
        "email":    "alice@example.com",
        "role":     "admin",
    }
    session_id = store.create(user_data)
    print(f"  Created session: {session_id[:8]}...")

    # ─── Request — session validate ───
    print("\n✅ Session Validation:")
    session = store.get(session_id)
    if session:
        print(f"  Valid session for: {session['username']} (role: {session['role']})")
        print(f"  Last active: {session['last_active']}")
    else:
        print("  ❌ Session not found!")

    # ─── Multiple sessions (same user — different devices) ───
    print("\n📱 Multiple Device Sessions:")
    session_mobile = store.create({**user_data, "device": "mobile"})
    session_tablet = store.create({**user_data, "device": "tablet"})
    print(f"  Mobile session: {session_mobile[:8]}...")
    print(f"  Tablet session: {session_tablet[:8]}...")

    all_sessions = store.get_user_sessions(user_id=1001)
    print(f"  Total active sessions: {len(all_sessions)}")

    # ─── Session extend ───
    print("\n⏰ Session Extend:")
    before_ttl = r.ttl(f"session:{session_id}")
    store.extend(session_id, extra_seconds=1800)
    after_ttl = r.ttl(f"session:{session_id}")
    print(f"  TTL before extend: {before_ttl}s")
    print(f"  TTL after extend:  {after_ttl}s (+1800s)")

    # ─── Logout — single session ───
    print("\n🚪 Logout (single session):")
    deleted = store.delete(session_mobile)
    print(f"  Mobile session deleted: {deleted}")
    print(f"  Mobile session now: {store.get(session_mobile)}")  # None

    # ─── Security: Delete ALL sessions (password change) ───
    print("\n🔒 Security: Delete ALL user sessions:")
    store.delete_all_for_user(user_id=1001)
    remaining = store.get_user_sessions(user_id=1001)
    print(f"  Remaining sessions: {len(remaining)}")

    print("\n✅ Session Store demo complete!")


# ════════════════════════════════════════════
# SECTION 5: PIPELINE vs TRANSACTION
# ════════════════════════════════════════════
def demo_pipeline_vs_transaction():
    print("\n" + "="*50)
    print("  SECTION 5: PIPELINE vs TRANSACTION (MULTI/EXEC)")
    print("="*50)

    r.set("balance:user:A", "1000")
    r.set("balance:user:B", "500")

    # ─── Pipeline (transaction=False) — Non-atomic ───
    print("\n📦 Non-atomic Pipeline (batch speed):")
    pipe = r.pipeline(transaction=False)
    pipe.set("stat:1", "v1")
    pipe.set("stat:2", "v2")
    pipe.incr("visits:today")
    pipe.incr("visits:today")
    results = pipe.execute()
    print(f"  Results: {results}")
    print(f"  visits:today = {r.get('visits:today')}")
    # Note: if server error between commands — partial execution possible

    # ─── Pipeline (transaction=True) — MULTI/EXEC atomic ───
    print("\n🔒 Atomic Transaction (MULTI/EXEC):")
    # Money transfer: A → B (100 rupees)
    pipe = r.pipeline(transaction=True)
    pipe.decrby("balance:user:A", 100)  # A se ghata
    pipe.incrby("balance:user:B", 100)  # B ko badhao
    results = pipe.execute()
    print(f"  Transfer results: {results}")
    print(f"  Balance A: {r.get('balance:user:A')}")  # 900
    print(f"  Balance B: {r.get('balance:user:B')}")  # 600

    # ─── WATCH + MULTI/EXEC — Optimistic Lock ───
    print("\n👁️  WATCH + Transaction (Optimistic Lock):")
    r.set("inventory:item:42", "10")

    def purchase_item(item_id: str, quantity: int) -> bool:
        """Inventory check + decrement — race condition safe"""
        while True:
            try:
                # WATCH — agar key change ho toh transaction fail karo
                r.watch(f"inventory:item:{item_id}")

                current = int(r.get(f"inventory:item:{item_id}") or 0)
                if current < quantity:
                    r.unwatch()
                    print(f"  ❌ Not enough inventory ({current} < {quantity})")
                    return False

                # Transaction start
                pipe = r.pipeline(transaction=True)
                pipe.decrby(f"inventory:item:{item_id}", quantity)
                results = pipe.execute()  # EXEC — if WATCH key changed → WatchError
                print(f"  ✅ Purchased {quantity} items. Remaining: {results[0]}")
                return True

            except redis.WatchError:
                # Kisi aur ne concurrently change kar diya — retry
                print("  ⚡ WatchError! Retrying...")
                continue

    purchase_item("42", 3)   # Success: 10 → 7
    purchase_item("42", 5)   # Success: 7 → 2
    purchase_item("42", 5)   # Fail: not enough

    # Cleanup
    r.delete("stat:1", "stat:2", "visits:today",
             "balance:user:A", "balance:user:B",
             "inventory:item:42")
    print("\n✅ Pipeline vs Transaction demo complete!")


# ════════════════════════════════════════════
# SECTION 6: RATE LIMITER with Pipeline
# ════════════════════════════════════════════
def demo_rate_limiter():
    print("\n" + "="*50)
    print("  SECTION 6: RATE LIMITER using Pipeline")
    print("="*50)

    def rate_limit_fixed_window(user_id: str, limit: int = 5, window: int = 60) -> dict:
        """Fixed window rate limiter"""
        window_key = int(time.time()) // window
        key = f"rate:fixed:{user_id}:{window_key}"

        pipe = r.pipeline()
        pipe.incr(key)
        pipe.expire(key, window)
        count, _ = pipe.execute()

        allowed = count <= limit
        return {
            "allowed":   allowed,
            "count":     count,
            "limit":     limit,
            "remaining": max(0, limit - count),
        }

    def rate_limit_sliding_window(user_id: str, limit: int = 5, window: int = 60) -> dict:
        """Sliding window rate limiter using Sorted Set"""
        key = f"rate:sliding:{user_id}"
        now = time.time()
        window_start = now - window

        pipe = r.pipeline()
        # Old entries remove karo
        pipe.zremrangebyscore(key, 0, window_start)
        # Current request add karo
        pipe.zadd(key, {str(now): now})
        # Count karo
        pipe.zcard(key)
        # TTL set karo
        pipe.expire(key, window)
        _, _, count, _ = pipe.execute()

        allowed = count <= limit
        return {
            "allowed":   allowed,
            "count":     count,
            "limit":     limit,
            "remaining": max(0, limit - count),
        }

    print("\n📊 Fixed Window Rate Limit (limit=3, window=60s):")
    for i in range(5):
        result = rate_limit_fixed_window("user:test", limit=3, window=60)
        status = "✅ ALLOWED" if result["allowed"] else "❌ BLOCKED"
        print(f"  Request {i+1}: {status} — count={result['count']}, remaining={result['remaining']}")

    print("\n📊 Sliding Window Rate Limit (limit=3, window=60s):")
    for i in range(5):
        result = rate_limit_sliding_window("user:slide", limit=3, window=60)
        status = "✅ ALLOWED" if result["allowed"] else "❌ BLOCKED"
        print(f"  Request {i+1}: {status} — count={result['count']}, remaining={result['remaining']}")

    # Cleanup
    for key in r.scan_iter("rate:fixed:*"):
        r.delete(key)
    for key in r.scan_iter("rate:sliding:*"):
        r.delete(key)
    print("\n✅ Rate Limiter demo complete!")


# ════════════════════════════════════════════
# ASYNC RUNNER
# ════════════════════════════════════════════
async def run_async_demos():
    await demo_pipeline_async()
    await demo_connection_pool_async()


# ════════════════════════════════════════════
# MAIN RUNNER
# ════════════════════════════════════════════
def main():
    try:
        r.ping()
        print("✅ Redis connected!")
    except redis.ConnectionError:
        print("❌ Redis not running! Start: docker run -d -p 6379:6379 redis:7-alpine")
        sys.exit(1)

    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"

    sync_demos = {
        "pipeline":    demo_pipeline_sync,
        "pool":        demo_connection_pool_sync,
        "session":     demo_session_store,
        "transaction": demo_pipeline_vs_transaction,
        "ratelimit":   demo_rate_limiter,
    }

    if cmd == "all":
        # Sync demos
        for fn in sync_demos.values():
            fn()
        # Async demos
        asyncio.run(run_async_demos())
    elif cmd == "async":
        asyncio.run(run_async_demos())
    elif cmd in sync_demos:
        sync_demos[cmd]()
    else:
        print(f"Usage: python {sys.argv[0]} [{'|'.join(sync_demos.keys())}|async|all]")


if __name__ == "__main__":
    main()
