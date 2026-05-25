"""
============================================================
CACHE WARMING STRATEGIES — Practical
============================================================
Implements:
1. Eager startup warmer
2. Background continuous refresh
3. Progressive (rate-limited) warming
4. Refresh-ahead pattern
5. Scheduled warming
6. Multi-pod warming with distributed lock
7. Readiness probe integration
"""
from __future__ import annotations
import asyncio
import time
import random
from dataclasses import dataclass


# ============================================================
# Simulated dependencies
# ============================================================
class FakeDB:
    def __init__(self):
        self._data = {f"key_{i}": f"db_value_{i}" for i in range(10000)}
        self.fetch_count = 0
        self.fetch_times = []

    async def fetch(self, key):
        await asyncio.sleep(0.02)   # 20ms DB lookup
        self.fetch_count += 1
        self.fetch_times.append(time.time())
        return self._data.get(key)


class FakeCache:
    def __init__(self):
        self._store: dict[str, tuple] = {}

    def get(self, key):
        entry = self._store.get(key)
        if not entry: return None
        value, expiry = entry
        if time.time() > expiry:
            del self._store[key]
            return None
        return value

    def set(self, key, value, ttl: float = 300):
        self._store[key] = (value, time.time() + ttl)

    def __len__(self):
        return len(self._store)


class FakeAnalytics:
    """Returns top-N most accessed keys."""
    async def top_keys(self, limit: int = 100) -> list[str]:
        # Simulate: keys 0-99 are "hot"
        await asyncio.sleep(0.01)
        return [f"key_{i}" for i in range(limit)]


# ============================================================
# 1. EAGER STARTUP WARMER
# ============================================================
class EagerWarmer:
    def __init__(self, cache: FakeCache, db: FakeDB, analytics: FakeAnalytics):
        self.cache, self.db, self.analytics = cache, db, analytics

    async def warm(self, limit: int = 100):
        keys = await self.analytics.top_keys(limit)
        start = time.time()
        for key in keys:
            value = await self.db.fetch(key)
            if value is not None:
                self.cache.set(key, value)
        return time.time() - start


# ============================================================
# 2. PROGRESSIVE WARMER (rate-limited)
# ============================================================
class ProgressiveWarmer:
    def __init__(self, cache, db, analytics, concurrency: int = 5, delay: float = 0.0):
        self.cache, self.db, self.analytics = cache, db, analytics
        self.concurrency = concurrency
        self.delay = delay
        self.sem = asyncio.Semaphore(concurrency)

    async def warm(self, limit: int = 100):
        keys = await self.analytics.top_keys(limit)
        start = time.time()
        await asyncio.gather(*[self._fetch_one(k) for k in keys])
        return time.time() - start

    async def _fetch_one(self, key):
        async with self.sem:
            value = await self.db.fetch(key)
            if value is not None:
                self.cache.set(key, value)
            await asyncio.sleep(self.delay)


# ============================================================
# 3. BACKGROUND REFRESH
# ============================================================
class BackgroundRefresher:
    def __init__(self, cache, db, analytics, interval: float = 60):
        self.cache, self.db, self.analytics = cache, db, analytics
        self.interval = interval
        self._task = None
        self.running = False

    def start(self):
        self.running = True
        self._task = asyncio.create_task(self._loop())

    def stop(self):
        self.running = False
        if self._task:
            self._task.cancel()

    async def _loop(self):
        while self.running:
            try:
                top = await self.analytics.top_keys(50)
                for k in top:
                    value = await self.db.fetch(k)
                    if value is not None:
                        self.cache.set(k, value)
                await asyncio.sleep(self.interval)
            except asyncio.CancelledError:
                return


# ============================================================
# 4. REFRESH-AHEAD
# ============================================================
class RefreshAheadCache:
    """Refresh key before TTL expires."""

    def __init__(self, cache, db, refresh_at_pct: float = 0.8):
        self.cache, self.db = cache, db
        self.refresh_at_pct = refresh_at_pct
        self._refreshing: set[str] = set()

    async def get(self, key: str, ttl: float = 60):
        cached = self.cache.get(key)
        meta_key = f"{key}:meta"
        meta = self.cache.get(meta_key)

        if cached and meta:
            created_at = meta["created_at"]
            age = time.time() - created_at
            if age > ttl * self.refresh_at_pct and key not in self._refreshing:
                # Refresh in background
                self._refreshing.add(key)
                asyncio.create_task(self._refresh(key, ttl))
            return cached

        # Sync fetch
        return await self._fetch_sync(key, ttl)

    async def _refresh(self, key, ttl):
        try:
            value = await self.db.fetch(key)
            if value is not None:
                self.cache.set(key, value, ttl=ttl)
                self.cache.set(f"{key}:meta", {"created_at": time.time()}, ttl=ttl)
        finally:
            self._refreshing.discard(key)

    async def _fetch_sync(self, key, ttl):
        value = await self.db.fetch(key)
        if value is not None:
            self.cache.set(key, value, ttl=ttl)
            self.cache.set(f"{key}:meta", {"created_at": time.time()}, ttl=ttl)
        return value


# ============================================================
# 5. SCHEDULED WARMING (cron-like)
# ============================================================
SCHEDULED_WARMING = """
# Using Celery Beat
from celery.schedules import crontab

@celery_app.on_after_configure.connect
def setup_periodic(sender, **kwargs):
    # Warm checkout cache 5 min before midnight rush
    sender.add_periodic_task(
        crontab(hour=23, minute=55),
        warm_checkout_cache.s(),
    )
    # Warm lunch traffic at 11:55 daily
    sender.add_periodic_task(
        crontab(hour=11, minute=55),
        warm_lunch_cache.s(),
    )

@celery_app.task
def warm_checkout_cache():
    # ... warming logic ...
    pass

# Using APScheduler
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()
scheduler.add_job(warm_lunch_cache, 'cron', hour=11, minute=55)
scheduler.start()
"""


# ============================================================
# 6. MULTI-POD WARMING WITH DISTRIBUTED LOCK
# ============================================================
MULTI_POD_WARMING = """
async def warm_with_lock(redis, pod_name):
    # Try to acquire warming lock (only one pod warms shared L2)
    acquired = await redis.set("warm_lock", pod_name, nx=True, ex=600)
    if acquired:
        try:
            await warm_l2_cache()
        finally:
            # Atomic release if we own it
            lua = '''
            if redis.call("GET", KEYS[1]) == ARGV[1] then
                return redis.call("DEL", KEYS[1])
            end
            '''
            await redis.eval(lua, 1, "warm_lock", pod_name)
    else:
        # Wait for the warming pod to finish
        while await redis.exists("warm_lock"):
            await asyncio.sleep(2)

    # Now warm our own L1 from L2
    await warm_l1_from_l2()
"""


# ============================================================
# 7. READINESS PROBE INTEGRATION
# ============================================================
READINESS_INTEGRATION = """
# FastAPI

from fastapi import FastAPI
app = FastAPI()

class WarmingState:
    def __init__(self):
        self.complete = False
        self.progress = 0

state = WarmingState()

@app.on_event("startup")
async def startup():
    asyncio.create_task(do_warming(state))

async def do_warming(state):
    keys = await analytics.top_keys(1000)
    for i, key in enumerate(keys):
        await fetch_and_cache(key)
        state.progress = i + 1
    state.complete = True

@app.get("/health/live")
async def live():
    \"\"\"Always 200 — process is alive.\"\"\"
    return {"status": "live"}

@app.get("/health/ready")
async def ready():
    \"\"\"Only 200 when warming complete.\"\"\"
    if not state.complete:
        return JSONResponse(
            {"ready": False, "progress": state.progress},
            status_code=503,
        )
    return {"ready": True}

# Kubernetes:
# livenessProbe:    /health/live  (don't kill during warming)
# readinessProbe:   /health/ready (no traffic until warm)
"""


# ============================================================
# DEMOS
# ============================================================
async def demo_eager_vs_progressive():
    print("=" * 60)
    print("EAGER vs PROGRESSIVE WARMING")
    print("=" * 60)

    # Eager (sequential, no rate limit)
    db1 = FakeDB()
    cache1 = FakeCache()
    eager = EagerWarmer(cache1, db1, FakeAnalytics())
    t1 = await eager.warm(100)
    print(f"  Eager (sequential): {t1*1000:.0f}ms, {db1.fetch_count} DB calls, cache size {len(cache1)}")

    # Progressive (parallel, rate-limited)
    db2 = FakeDB()
    cache2 = FakeCache()
    progressive = ProgressiveWarmer(cache2, db2, FakeAnalytics(), concurrency=10)
    t2 = await progressive.warm(100)
    print(f"  Progressive (10 concurrent): {t2*1000:.0f}ms, {db2.fetch_count} DB calls")
    print(f"  Speedup: {t1/t2:.1f}x")


async def demo_background_refresh():
    print("\n" + "=" * 60)
    print("BACKGROUND REFRESH")
    print("=" * 60)
    cache = FakeCache()
    db = FakeDB()
    refresher = BackgroundRefresher(cache, db, FakeAnalytics(), interval=0.5)
    refresher.start()

    print(f"  Starting refresher... (running for 2s)")
    await asyncio.sleep(2)
    refresher.stop()
    print(f"  After 2s of background warming:")
    print(f"    Cache size: {len(cache)}")
    print(f"    DB fetches: {db.fetch_count}")


async def demo_refresh_ahead():
    print("\n" + "=" * 60)
    print("REFRESH-AHEAD PATTERN")
    print("=" * 60)
    cache = FakeCache()
    db = FakeDB()
    refresh_cache = RefreshAheadCache(cache, db, refresh_at_pct=0.7)

    print("  Initial fetch (cache miss):")
    val = await refresh_cache.get("key_42", ttl=1.0)
    print(f"    Got: {val}, DB calls: {db.fetch_count}")

    print("  Reading at 30% TTL (should be cache hit, no refresh):")
    await asyncio.sleep(0.3)
    val = await refresh_cache.get("key_42", ttl=1.0)
    print(f"    DB calls: {db.fetch_count}")

    print("  Reading at 80% TTL (cache hit + background refresh):")
    await asyncio.sleep(0.5)
    val = await refresh_cache.get("key_42", ttl=1.0)
    await asyncio.sleep(0.1)   # let background refresh complete
    print(f"    DB calls: {db.fetch_count} (should be 2 — initial + background)")


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    async def main():
        await demo_eager_vs_progressive()
        await demo_background_refresh()
        await demo_refresh_ahead()

        print("\n" + "=" * 60)
        print("PRODUCTION TEMPLATES")
        print("=" * 60)
        print("\n--- Scheduled warming ---")
        print(SCHEDULED_WARMING)
        print("\n--- Multi-pod with distributed lock ---")
        print(MULTI_POD_WARMING)
        print("\n--- Readiness probe integration ---")
        print(READINESS_INTEGRATION)

    asyncio.run(main())
