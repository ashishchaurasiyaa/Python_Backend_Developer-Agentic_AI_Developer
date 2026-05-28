"""
============================================================
CACHE STAMPEDE / COLD START — Practical Solutions
============================================================
Implements:
1. Naive (vulnerable to stampede) — for comparison
2. Lock-based single-flight
3. Probabilistic early expiration (XFetch)
4. Stale-While-Revalidate (SWR)
5. TTL jitter
6. Request coalescing (in-process)

Run:
    python 03_cache_stampede_cold_start.py
"""
from __future__ import annotations
import asyncio
import time
import math
import random
import secrets
from dataclasses import dataclass, field
from collections import defaultdict


# ============================================================
# Simulated cache + slow DB
# ============================================================
class FakeCache:
    def __init__(self):
        self._store: dict[str, tuple] = {}    # key -> (value, expiry_ts, metadata)

    async def get(self, key):
        entry = self._store.get(key)
        if not entry: return None
        value, expiry, _ = entry
        if time.monotonic() >= expiry:
            del self._store[key]
            return None
        return value

    async def get_with_meta(self, key):
        entry = self._store.get(key)
        if not entry: return None
        value, expiry, meta = entry
        if time.monotonic() >= expiry:
            del self._store[key]
            return None
        return {"value": value, "expiry": expiry, "meta": meta}

    async def set(self, key, value, ttl: float, metadata=None):
        self._store[key] = (value, time.monotonic() + ttl, metadata or {})

    async def delete(self, key):
        self._store.pop(key, None)


DB_HITS = 0
DB_LOCK = asyncio.Lock()


async def slow_db_query(key):
    """Simulates a slow, expensive DB query."""
    global DB_HITS
    async with DB_LOCK:
        DB_HITS += 1
    await asyncio.sleep(0.2)   # 200ms query
    return f"value-for-{key}-{time.monotonic():.2f}"


def reset_db_counter():
    global DB_HITS
    DB_HITS = 0


# ============================================================
# 1. NAIVE — vulnerable to stampede
# ============================================================
async def naive_get(cache, key, ttl=2.0):
    value = await cache.get(key)
    if value is None:
        value = await slow_db_query(key)
        await cache.set(key, value, ttl)
    return value


async def demo_naive_stampede():
    print("=" * 60)
    print("DEMO 1: NAIVE — Vulnerable to stampede")
    print("=" * 60)
    cache = FakeCache()
    reset_db_counter()

    # 50 concurrent requests for SAME key, no cache
    tasks = [naive_get(cache, "homepage") for _ in range(50)]
    await asyncio.gather(*tasks)
    print(f"  50 concurrent requests, cache empty: DB hits = {DB_HITS}")
    print(f"  ❌ All 50 hit DB simultaneously!")


# ============================================================
# 2. LOCK-BASED SINGLE-FLIGHT
# ============================================================
class LockedCache:
    def __init__(self, cache):
        self.cache = cache
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def get_or_compute(self, key, fetch_fn, ttl=2.0):
        value = await self.cache.get(key)
        if value is not None:
            return value

        async with self._locks[key]:
            # Re-check inside lock (another worker may have computed)
            value = await self.cache.get(key)
            if value is not None:
                return value
            value = await fetch_fn(key)
            await self.cache.set(key, value, ttl)
            return value


async def demo_locked_stampede():
    print("\n" + "=" * 60)
    print("DEMO 2: LOCK-BASED Single-Flight")
    print("=" * 60)
    cache = FakeCache()
    locked = LockedCache(cache)
    reset_db_counter()

    tasks = [locked.get_or_compute("homepage", slow_db_query) for _ in range(50)]
    await asyncio.gather(*tasks)
    print(f"  50 concurrent requests: DB hits = {DB_HITS} ✅ (only 1)")


# ============================================================
# 3. PROBABILISTIC EARLY EXPIRATION (XFetch)
# ============================================================
class XFetchCache:
    """Vattani et al. — probabilistically refresh BEFORE expiry."""

    def __init__(self, cache, beta=1.0):
        self.cache = cache
        self.beta = beta

    async def get(self, key, fetch_fn, ttl=2.0):
        cached = await self.cache.get_with_meta(key)
        now = time.monotonic()

        if cached is None:
            return await self._refresh(key, fetch_fn, ttl)

        delta = cached["meta"].get("delta", 0.5)   # recompute duration
        expiry = cached["expiry"]

        # Probability of recompute grows as expiry approaches
        # Random sample: math.log(random()) is negative
        # delta * beta * log(rand) is negative — more negative = recompute later
        if now - delta * self.beta * math.log(random.random()) >= expiry:
            return await self._refresh(key, fetch_fn, ttl)

        return cached["value"]

    async def _refresh(self, key, fetch_fn, ttl):
        start = time.monotonic()
        value = await fetch_fn(key)
        delta = time.monotonic() - start
        await self.cache.set(key, value, ttl, metadata={"delta": delta})
        return value


async def demo_xfetch():
    print("\n" + "=" * 60)
    print("DEMO 3: PROBABILISTIC EARLY EXPIRATION (XFetch)")
    print("=" * 60)
    cache = FakeCache()
    xfetch = XFetchCache(cache, beta=1.0)
    reset_db_counter()

    # Initial population
    await xfetch.get("homepage", slow_db_query, ttl=2.0)
    reset_db_counter()

    # Now constant traffic for ~3 seconds
    print("  Sending requests during cache lifetime...")
    end = time.monotonic() + 3.0
    request_count = 0
    while time.monotonic() < end:
        # Burst of 10 concurrent requests
        await asyncio.gather(*[xfetch.get("homepage", slow_db_query, ttl=2.0) for _ in range(10)])
        request_count += 10
        await asyncio.sleep(0.1)

    print(f"  Total requests: {request_count}, DB hits: {DB_HITS}")
    print(f"  Hit rate: {(1 - DB_HITS/request_count)*100:.1f}%")
    print(f"  ✅ Stampede avoided via probabilistic refresh")


# ============================================================
# 4. STALE-WHILE-REVALIDATE
# ============================================================
class SWRCache:
    """Stale-While-Revalidate — serve stale, refresh in background."""

    def __init__(self, cache):
        self.cache = cache
        self._refresh_tasks: set = set()

    async def get(self, key, fetch_fn, fresh_ttl=2.0, stale_ttl=4.0):
        cached = await self.cache.get_with_meta(key)
        now = time.monotonic()

        if cached is None:
            # Cold — must compute
            return await self._compute(key, fetch_fn, fresh_ttl)

        age = now - cached["meta"]["created_at"]

        if age < fresh_ttl:
            return cached["value"]

        if age < fresh_ttl + stale_ttl:
            # Stale but usable — refresh in background
            if key not in [t.get_name() for t in self._refresh_tasks]:
                task = asyncio.create_task(
                    self._compute(key, fetch_fn, fresh_ttl), name=key,
                )
                self._refresh_tasks.add(task)
                task.add_done_callback(self._refresh_tasks.discard)
            return cached["value"]

        # Too stale — must wait for fresh data
        return await self._compute(key, fetch_fn, fresh_ttl)

    async def _compute(self, key, fetch_fn, ttl):
        value = await fetch_fn(key)
        await self.cache.set(key, value, ttl + 100, metadata={"created_at": time.monotonic()})
        return value


async def demo_swr():
    print("\n" + "=" * 60)
    print("DEMO 4: STALE-WHILE-REVALIDATE")
    print("=" * 60)
    cache = FakeCache()
    swr = SWRCache(cache)
    reset_db_counter()

    # Initial fetch
    await swr.get("homepage", slow_db_query, fresh_ttl=1.0, stale_ttl=2.0)
    reset_db_counter()
    print(f"  After initial fetch: DB hits = {DB_HITS}")

    # Wait until stale period (between fresh_ttl and fresh+stale)
    await asyncio.sleep(1.2)

    # Many requests during stale period — get instantly, ONE background refresh
    tasks = [swr.get("homepage", slow_db_query, fresh_ttl=1.0, stale_ttl=2.0) for _ in range(20)]
    await asyncio.gather(*tasks)
    await asyncio.sleep(0.3)   # let background refresh complete

    print(f"  20 requests during stale: DB hits = {DB_HITS} ✅ (1 background refresh)")
    print(f"  Users got instant stale response, cache refreshed once")


# ============================================================
# 5. TTL JITTER
# ============================================================
async def demo_ttl_jitter():
    print("\n" + "=" * 60)
    print("DEMO 5: TTL JITTER")
    print("=" * 60)

    base_ttl = 60.0
    print(f"  Base TTL: {base_ttl}s")
    print(f"  With ±10% jitter:")
    samples = [base_ttl + random.uniform(-base_ttl * 0.1, base_ttl * 0.1) for _ in range(5)]
    for i, ttl in enumerate(samples):
        print(f"    Key {i}: {ttl:.1f}s")
    print(f"  → Expirations spread over ~12s, not all at once")


# ============================================================
# 6. REQUEST COALESCING (in-process)
# ============================================================
class RequestCoalescer:
    """Multiple concurrent requests for same key → only ONE fetch."""

    def __init__(self):
        self._pending: dict[str, asyncio.Future] = {}
        self._lock = asyncio.Lock()

    async def get(self, key, fetch_fn):
        async with self._lock:
            future = self._pending.get(key)
            if future is None:
                future = asyncio.Future()
                self._pending[key] = future
                asyncio.create_task(self._fetch(key, fetch_fn, future))
        return await future

    async def _fetch(self, key, fetch_fn, future):
        try:
            result = await fetch_fn(key)
            future.set_result(result)
        except Exception as e:
            future.set_exception(e)
        finally:
            self._pending.pop(key, None)


async def demo_coalescing():
    print("\n" + "=" * 60)
    print("DEMO 6: REQUEST COALESCING (in-process)")
    print("=" * 60)
    reset_db_counter()
    coalescer = RequestCoalescer()

    tasks = [coalescer.get("homepage", slow_db_query) for _ in range(50)]
    results = await asyncio.gather(*tasks)

    print(f"  50 concurrent requests: DB hits = {DB_HITS} ✅ (only 1)")
    print(f"  All 50 got same result: {all(r == results[0] for r in results)}")


# ============================================================
# 7. COMBINED PRODUCTION PATTERN
# ============================================================
class ProductionCache:
    """Layered defense: coalescing + lock + SWR."""

    def __init__(self, cache):
        self.cache = cache
        self.coalescer = RequestCoalescer()
        self.locked = LockedCache(cache)
        self.swr = SWRCache(cache)

    async def get(self, key, fetch_fn, fresh_ttl=60, stale_ttl=30):
        # In-process coalescing first
        return await self.coalescer.get(
            key,
            lambda k: self.swr.get(k, fetch_fn, fresh_ttl, stale_ttl),
        )


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    async def main():
        await demo_naive_stampede()
        await demo_locked_stampede()
        await demo_xfetch()
        await demo_swr()
        await demo_ttl_jitter()
        await demo_coalescing()

        print("\n" + "=" * 60)
        print("RECOMMENDED PRODUCTION STACK")
        print("=" * 60)
        print("""
1. Request coalescing (in-process)       → 50 reqs → 1 fetch
2. SWR (stale-while-revalidate)          → instant response
3. Distributed lock as fallback          → multi-instance safety
4. TTL jitter on every set               → avoid time-aligned expiries
5. Cache warming on startup              → no cold start
6. Probabilistic refresh for very-hot    → preempt expiry
""")

    asyncio.run(main())
