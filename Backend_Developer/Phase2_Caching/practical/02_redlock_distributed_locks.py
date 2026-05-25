"""
============================================================
REDLOCK — Distributed Locks Practical
============================================================
Run:
    pip install redis aioredlock
    docker run -d -p 6379:6379 redis:latest

This file shows:
1. Simple SET NX EX lock + Lua release (safe single-Redis)
2. Lock as context manager + decorator
3. Lock extender / watchdog
4. Redlock multi-instance (using aioredlock)
5. Leader election
6. Fencing tokens
"""
from __future__ import annotations
import asyncio
import time
import secrets
import functools
import os
from contextlib import asynccontextmanager


# ============================================================
# 1. SIMPLE SAFE LOCK (single Redis, owner-tagged)
# ============================================================
LUA_RELEASE = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
else
    return 0
end
"""

LUA_EXTEND = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("PEXPIRE", KEYS[1], ARGV[2])
else
    return 0
end
"""


class SimpleRedisLock:
    """Single-Redis distributed lock with owner check.
    Production-ready for most cases."""

    def __init__(self, redis_client, resource: str, ttl_ms: int = 10000):
        self.redis = redis_client
        self.resource = f"lock:{resource}"
        self.ttl_ms = ttl_ms
        self.lock_id = secrets.token_hex(16)
        self.acquired = False

    async def acquire(self, block: bool = True, retry_delay_ms: int = 100) -> bool:
        end = time.monotonic() + (self.ttl_ms / 1000) if block else 0
        while True:
            if await self.redis.set(
                self.resource, self.lock_id,
                nx=True, px=self.ttl_ms,
            ):
                self.acquired = True
                return True
            if not block or time.monotonic() > end:
                return False
            await asyncio.sleep(retry_delay_ms / 1000)

    async def release(self) -> bool:
        if not self.acquired:
            return False
        result = await self.redis.eval(
            LUA_RELEASE, 1, self.resource, self.lock_id,
        )
        self.acquired = False
        return bool(result)

    async def extend(self, additional_ttl_ms: int) -> bool:
        return bool(await self.redis.eval(
            LUA_EXTEND, 1, self.resource,
            self.lock_id, additional_ttl_ms,
        ))

    async def __aenter__(self):
        if not await self.acquire():
            raise RuntimeError(f"Could not acquire {self.resource}")
        return self

    async def __aexit__(self, *exc):
        await self.release()


# ============================================================
# 2. DECORATOR
# ============================================================
def with_redis_lock(redis_client, resource_template: str, ttl_ms: int = 10000):
    """Decorator that acquires Redis lock around function call."""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            resource = resource_template.format(*args, **kwargs)
            lock = SimpleRedisLock(redis_client, resource, ttl_ms)
            async with lock:
                return await func(*args, **kwargs)
        return wrapper
    return decorator


# ============================================================
# 3. LOCK EXTENDER / WATCHDOG
# ============================================================
class WatchdogLock:
    """Lock that auto-extends TTL in background while held.
    Use for operations of unpredictable duration."""

    def __init__(self, redis_client, resource: str, ttl_ms: int = 30000):
        self.lock = SimpleRedisLock(redis_client, resource, ttl_ms)
        self.ttl_ms = ttl_ms
        self._watchdog_task: asyncio.Task | None = None

    async def __aenter__(self):
        if not await self.lock.acquire():
            raise RuntimeError(f"Lock unavailable")
        # Start watchdog — extend every ttl/3
        self._watchdog_task = asyncio.create_task(self._watchdog())
        return self

    async def _watchdog(self):
        try:
            while True:
                await asyncio.sleep(self.ttl_ms / 3 / 1000)
                ok = await self.lock.extend(self.ttl_ms)
                if not ok:
                    print(f"  ⚠️  Lost lock {self.lock.resource}!")
                    return
        except asyncio.CancelledError:
            pass

    async def __aexit__(self, *exc):
        if self._watchdog_task:
            self._watchdog_task.cancel()
            try:
                await self._watchdog_task
            except asyncio.CancelledError:
                pass
        await self.lock.release()


# ============================================================
# 4. FENCING TOKEN PATTERN
# ============================================================
class FencingLock:
    """Lock + monotonic fencing token.
    Downstream services must verify token > last seen."""

    def __init__(self, redis_client, resource: str, ttl_ms: int = 10000):
        self.redis = redis_client
        self.resource = resource
        self.ttl_ms = ttl_ms

    async def acquire(self) -> tuple[bool, int]:
        # Increment monotonic counter
        token = await self.redis.incr(f"fence:{self.resource}")
        lock = SimpleRedisLock(self.redis, self.resource, self.ttl_ms)
        acquired = await lock.acquire()
        return acquired, token


# ============================================================
# 5. AIOREDLOCK (multi-Redis Redlock)
# ============================================================
REDLOCK_USAGE = """
from aioredlock import Aioredlock, LockError

# Multiple independent Redis instances
lock_manager = Aioredlock([
    {"host": "redis1.internal", "port": 6379},
    {"host": "redis2.internal", "port": 6379},
    {"host": "redis3.internal", "port": 6379},
    {"host": "redis4.internal", "port": 6379},
    {"host": "redis5.internal", "port": 6379},
])

# Use as context manager
async with await lock_manager.lock("critical_resource", lock_timeout=10):
    # Quorum (3 of 5) acquired this lock
    await do_work()

# Without context manager
lock = await lock_manager.lock("resource", lock_timeout=5)
try:
    if lock.valid:
        await do_work()
finally:
    await lock_manager.unlock(lock)

# Cleanup
await lock_manager.destroy()
"""


# ============================================================
# 6. LEADER ELECTION
# ============================================================
class LeaderElection:
    """Multiple instances compete for leadership.
    Winner keeps refreshing their hold.
    On failure, another node becomes leader."""

    def __init__(self, redis_client, role: str, ttl_seconds: int = 30):
        self.redis = redis_client
        self.role = f"leader:{role}"
        self.node_id = f"{os.getpid()}-{secrets.token_hex(4)}"
        self.ttl = ttl_seconds
        self._task: asyncio.Task | None = None
        self.is_leader = False

    async def campaign(self) -> bool:
        """Try to become leader."""
        acquired = await self.redis.set(
            self.role, self.node_id,
            nx=True, ex=self.ttl,
        )
        self.is_leader = bool(acquired)
        if self.is_leader:
            print(f"  👑 Node {self.node_id} became leader")
            self._task = asyncio.create_task(self._heartbeat())
        return self.is_leader

    async def _heartbeat(self):
        while True:
            try:
                await asyncio.sleep(self.ttl / 3)
                refreshed = await self.redis.eval(
                    LUA_EXTEND, 1, self.role, self.node_id, self.ttl * 1000,
                )
                if not refreshed:
                    print(f"  💔 Lost leadership!")
                    self.is_leader = False
                    return
            except asyncio.CancelledError:
                return

    async def step_down(self):
        if self._task:
            self._task.cancel()
        await self.redis.eval(LUA_RELEASE, 1, self.role, self.node_id)
        self.is_leader = False


# ============================================================
# 7. POSTGRES ADVISORY LOCK (alternative)
# ============================================================
POSTGRES_ADVISORY = """
-- Lock per connection (auto-release on disconnect)
SELECT pg_try_advisory_lock(12345);    -- non-blocking, returns true/false
SELECT pg_advisory_lock(12345);        -- blocking
SELECT pg_advisory_unlock(12345);

-- Per-transaction lock (auto-release on commit/rollback)
BEGIN;
SELECT pg_try_advisory_xact_lock(12345);
-- ... work ...
COMMIT;  -- lock released

-- Python with asyncpg
async with conn.transaction():
    locked = await conn.fetchval("SELECT pg_try_advisory_xact_lock($1)", 12345)
    if locked:
        await do_work()
"""


# ============================================================
# 8. DEMO with simulated Redis
# ============================================================
class MockRedis:
    """In-memory Redis simulation for demo."""
    def __init__(self):
        self._store: dict[str, tuple[str, float]] = {}   # key -> (value, expiry_ts)

    async def set(self, key, value, nx=False, ex=None, px=None):
        now = time.monotonic()
        existing = self._store.get(key)
        if existing and now < existing[1]:
            if nx:
                return False
        ttl = ex if ex else (px / 1000 if px else 0)
        self._store[key] = (str(value), now + ttl if ttl else float("inf"))
        return True

    async def get(self, key):
        now = time.monotonic()
        existing = self._store.get(key)
        if not existing or now >= existing[1]:
            self._store.pop(key, None)
            return None
        return existing[0]

    async def incr(self, key):
        val = int(await self.get(key) or 0) + 1
        existing = self._store.get(key, (None, float("inf")))
        self._store[key] = (str(val), existing[1])
        return val

    async def eval(self, script, numkeys, *args):
        # Mock for LUA_RELEASE and LUA_EXTEND
        if "DEL" in script:
            key, val = args[0], args[1]
            if (await self.get(key)) == val:
                self._store.pop(key, None)
                return 1
            return 0
        if "PEXPIRE" in script:
            key, val, ttl = args[0], args[1], int(args[2])
            existing = self._store.get(key)
            if existing and existing[0] == val:
                self._store[key] = (existing[0], time.monotonic() + ttl / 1000)
                return 1
            return 0


# ============================================================
# DEMOS
# ============================================================
async def demo_simple_lock():
    print("=" * 60)
    print("DEMO 1: Simple Redis Lock with Owner Check")
    print("=" * 60)
    redis = MockRedis()

    async def worker(name):
        async with SimpleRedisLock(redis, "task-A", ttl_ms=2000) as lock:
            print(f"  [{name}] acquired lock at {time.monotonic():.2f}")
            await asyncio.sleep(0.5)
        print(f"  [{name}] released at {time.monotonic():.2f}")

    await asyncio.gather(worker("W1"), worker("W2"), worker("W3"))


async def demo_decorator():
    print("\n" + "=" * 60)
    print("DEMO 2: Decorator Pattern")
    print("=" * 60)
    redis = MockRedis()

    @with_redis_lock(redis, "user:{0}", ttl_ms=2000)
    async def process_user(user_id):
        print(f"  Processing user {user_id}")
        await asyncio.sleep(0.3)
        return f"done-{user_id}"

    await asyncio.gather(
        process_user(1),
        process_user(1),     # waits for above
        process_user(2),     # different lock — runs concurrently
    )


async def demo_watchdog():
    print("\n" + "=" * 60)
    print("DEMO 3: Watchdog Lock (auto-extend)")
    print("=" * 60)
    redis = MockRedis()

    async with WatchdogLock(redis, "long_task", ttl_ms=1000) as lock:
        print(f"  Starting 3s task with 1s TTL — watchdog extends every 333ms")
        await asyncio.sleep(2.5)   # exceeds TTL but watchdog keeps it alive
        print(f"  Long task done — lock survived!")


async def demo_fencing():
    print("\n" + "=" * 60)
    print("DEMO 4: Fencing Tokens")
    print("=" * 60)
    redis = MockRedis()
    fl = FencingLock(redis, "shared_resource")

    # Client A
    ok_a, token_a = await fl.acquire()
    print(f"  Client A: lock={ok_a}, token={token_a}")

    # Wait — lock expires (simulated)
    await asyncio.sleep(0.01)

    # Client B acquires
    fl2 = FencingLock(redis, "shared_resource")
    ok_b, token_b = await fl2.acquire()
    print(f"  Client B: lock={ok_b}, token={token_b}")
    print(f"  Storage service: accepts B (token {token_b} > {token_a})")
    print(f"  Storage service: rejects late A writes (stale token {token_a})")


async def demo_leader_election():
    print("\n" + "=" * 60)
    print("DEMO 5: Leader Election")
    print("=" * 60)
    redis = MockRedis()
    nodes = [LeaderElection(redis, "scheduler", ttl_seconds=2) for _ in range(5)]

    # All 5 try to become leader
    results = await asyncio.gather(*[n.campaign() for n in nodes])
    leader_count = sum(results)
    print(f"  Out of 5 nodes, {leader_count} became leader (expected 1)")

    leader = next(n for n in nodes if n.is_leader)
    print(f"  Leader: {leader.node_id}")

    # Step down
    await leader.step_down()
    print(f"  Leader stepped down. Now others can campaign.")


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    async def main():
        await demo_simple_lock()
        await demo_decorator()
        await demo_watchdog()
        await demo_fencing()
        await demo_leader_election()

        print("\n" + "=" * 60)
        print("REDLOCK (multi-Redis) USAGE")
        print("=" * 60)
        print(REDLOCK_USAGE)
        print("\n--- Postgres advisory lock ---")
        print(POSTGRES_ADVISORY)

    asyncio.run(main())
