"""
============================================================
MULTI-LEVEL CACHING (L1 + L2 + L3) — Practical
============================================================
Demonstrates:
1. Cache-aside read pattern across 3 levels
2. L1 (in-process LRU)
3. L2 (Redis-simulated)
4. L3 (database-simulated)
5. Pub/Sub invalidation across pods
6. Versioning strategy
7. Metrics collection
"""
from __future__ import annotations
import asyncio
import time
import random
from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field
from typing import Any


# ============================================================
# L1: In-process LRU with TTL
# ============================================================
class L1Cache:
    def __init__(self, capacity: int = 1000, ttl: float = 60):
        self.capacity = capacity
        self.ttl = ttl
        self._store: OrderedDict[str, tuple[Any, float]] = OrderedDict()

    def get(self, key):
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expiry = entry
        if time.monotonic() > expiry:
            del self._store[key]
            return None
        self._store.move_to_end(key)
        return value

    def put(self, key, value):
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = (value, time.monotonic() + self.ttl)
        if len(self._store) > self.capacity:
            self._store.popitem(last=False)

    def delete(self, key):
        self._store.pop(key, None)

    def __len__(self):
        return len(self._store)


# ============================================================
# L2: Simulated Redis with Pub/Sub
# ============================================================
class FakeRedis:
    def __init__(self):
        self._store: dict[str, tuple[Any, float]] = {}
        self._subscribers: list[asyncio.Queue] = []

    async def get(self, key):
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expiry = entry
        if time.monotonic() > expiry:
            del self._store[key]
            return None
        return value

    async def set(self, key, value, ttl: float = 300):
        self._store[key] = (value, time.monotonic() + ttl)

    async def delete(self, key):
        self._store.pop(key, None)

    async def publish(self, channel: str, message: str):
        for q in self._subscribers:
            await q.put((channel, message))

    def subscribe(self) -> asyncio.Queue:
        q = asyncio.Queue()
        self._subscribers.append(q)
        return q


# ============================================================
# L3: Simulated Database (slow)
# ============================================================
class FakeDB:
    def __init__(self):
        self._data = {f"key_{i}": f"db_value_{i}" for i in range(1000)}
        self.read_count = 0

    async def fetch(self, key):
        await asyncio.sleep(0.05)  # simulate slow DB
        self.read_count += 1
        return self._data.get(key)

    async def update(self, key, value):
        self._data[key] = value


# ============================================================
# Multi-Level Cache with Pub/Sub Invalidation
# ============================================================
@dataclass
class CacheMetrics:
    l1_hits: int = 0
    l2_hits: int = 0
    l3_hits: int = 0
    invalidations: int = 0

    @property
    def total(self):
        return self.l1_hits + self.l2_hits + self.l3_hits

    def report(self):
        if self.total == 0:
            return "no data"
        return (
            f"L1: {self.l1_hits}/{self.total} ({self.l1_hits/self.total*100:.1f}%)  "
            f"L2: {self.l2_hits}/{self.total} ({self.l2_hits/self.total*100:.1f}%)  "
            f"L3: {self.l3_hits}/{self.total} ({self.l3_hits/self.total*100:.1f}%)  "
            f"Invalidations: {self.invalidations}"
        )


class MultiLevelCache:
    def __init__(self, pod_name: str, redis: FakeRedis, db: FakeDB,
                 l1_capacity: int = 100, l1_ttl: float = 30):
        self.pod_name = pod_name
        self.l1 = L1Cache(l1_capacity, l1_ttl)
        self.l2 = redis
        self.l3 = db
        self.metrics = CacheMetrics()
        self._invalidation_queue: asyncio.Queue = self.l2.subscribe()
        self._listener_task = asyncio.create_task(self._listen())

    async def _listen(self):
        """Listen for invalidations from other pods."""
        while True:
            try:
                channel, key = await self._invalidation_queue.get()
                if channel == "cache_invalidate":
                    self.l1.delete(key)
                    self.metrics.invalidations += 1
            except Exception:
                pass

    async def get(self, key: str) -> Any:
        # L1
        value = self.l1.get(key)
        if value is not None:
            self.metrics.l1_hits += 1
            return value

        # L2
        value = await self.l2.get(key)
        if value is not None:
            self.metrics.l2_hits += 1
            self.l1.put(key, value)
            return value

        # L3
        value = await self.l3.fetch(key)
        if value is not None:
            self.metrics.l3_hits += 1
            await self.l2.set(key, value, ttl=300)
            self.l1.put(key, value)
        return value

    async def update(self, key: str, value: Any):
        """Write-through + propagate invalidation."""
        await self.l3.update(key, value)
        await self.l2.set(key, value, ttl=300)
        self.l1.put(key, value)
        # Tell other pods to evict from their L1
        await self.l2.publish("cache_invalidate", key)


# ============================================================
# DEMO 1: Single-pod multi-level
# ============================================================
async def demo_single_pod():
    print("=" * 60)
    print("DEMO 1: Single Pod — L1/L2/L3 cache hierarchy")
    print("=" * 60)
    redis = FakeRedis()
    db = FakeDB()
    cache = MultiLevelCache("pod-A", redis, db, l1_capacity=10)

    # First access — L3 miss, populates L2 and L1
    await cache.get("key_1")
    await cache.get("key_2")
    await cache.get("key_3")
    print(f"  After 3 unique reads: DB calls = {db.read_count}")

    # Re-read same keys — should ALL hit L1
    for _ in range(10):
        await cache.get("key_1")
        await cache.get("key_2")
    print(f"  After 20 repeated reads: DB calls = {db.read_count} (still 3)")

    print(f"  Metrics: {cache.metrics.report()}")


# ============================================================
# DEMO 2: Multi-pod with invalidation
# ============================================================
async def demo_multi_pod_invalidation():
    print("\n" + "=" * 60)
    print("DEMO 2: Multi-Pod with Pub/Sub Invalidation")
    print("=" * 60)
    redis = FakeRedis()
    db = FakeDB()

    pod_a = MultiLevelCache("pod-A", redis, db, l1_capacity=10)
    pod_b = MultiLevelCache("pod-B", redis, db, l1_capacity=10)

    # Both pods read key_1 — populate both L1s
    await pod_a.get("key_1")
    await pod_b.get("key_1")
    print(f"  Both pods cache key_1 in L1")
    print(f"  L1 size A: {len(pod_a.l1)}, L1 size B: {len(pod_b.l1)}")

    # Pod A updates key_1
    await pod_a.update("key_1", "UPDATED_VALUE")
    await asyncio.sleep(0.05)  # let invalidation propagate

    print(f"  After update on pod A:")
    print(f"    pod_a L1 has: '{pod_a.l1.get('key_1')}'")
    print(f"    pod_b L1 has: '{pod_b.l1.get('key_1')}' (should be None — invalidated)")

    # Pod B re-reads — gets fresh value from L2
    value = await pod_b.get("key_1")
    print(f"  Pod B reads key_1 after invalidation: '{value}'")


# ============================================================
# DEMO 3: Pareto workload (80/20)
# ============================================================
async def demo_pareto_workload():
    print("\n" + "=" * 60)
    print("DEMO 3: Pareto Access Pattern")
    print("=" * 60)
    redis = FakeRedis()
    db = FakeDB()
    cache = MultiLevelCache("pod-A", redis, db, l1_capacity=20)

    HOT = list(range(20))
    COLD = list(range(100, 1000))

    for _ in range(500):
        if random.random() < 0.8:
            await cache.get(f"key_{random.choice(HOT)}")
        else:
            await cache.get(f"key_{random.choice(COLD)}")

    print(f"  500 requests with 80/20 access pattern")
    print(f"  {cache.metrics.report()}")
    print(f"  DB calls: {db.read_count}")


# ============================================================
# DEMO 4: Versioned cache for strong consistency
# ============================================================
class VersionedMultiLevelCache:
    """L1 stores (value, version). On hit, check L2 version (cheap call)."""

    def __init__(self, pod_name, redis, db):
        self.pod_name = pod_name
        self.l1: dict[str, tuple[Any, int]] = {}
        self.l2 = redis
        self.l3 = db

    async def get(self, key):
        l1_entry = self.l1.get(key)
        # Check L2 version (lightweight)
        l2_version_str = await self.l2.get(f"{key}:version")
        l2_version = int(l2_version_str) if l2_version_str else 0

        if l1_entry and l1_entry[1] == l2_version:
            return l1_entry[0]

        # Stale or missing — fetch from L2
        value = await self.l2.get(key)
        if value is None:
            value = await self.l3.fetch(key)
            await self.l2.set(key, value)
            await self.l2.set(f"{key}:version", str(l2_version + 1))
            l2_version += 1
        self.l1[key] = (value, l2_version)
        return value

    async def update(self, key, value):
        await self.l3.update(key, value)
        # Increment version
        current = await self.l2.get(f"{key}:version")
        new_version = (int(current) if current else 0) + 1
        await self.l2.set(key, value)
        await self.l2.set(f"{key}:version", str(new_version))
        self.l1[key] = (value, new_version)


async def demo_versioning():
    print("\n" + "=" * 60)
    print("DEMO 4: Versioned Cache (strong consistency)")
    print("=" * 60)
    redis = FakeRedis()
    db = FakeDB()
    pod_a = VersionedMultiLevelCache("A", redis, db)
    pod_b = VersionedMultiLevelCache("B", redis, db)

    await pod_a.get("key_1")
    await pod_b.get("key_1")
    print(f"  Initial: both pods see same version")

    await pod_a.update("key_1", "NEW")
    # No pub/sub needed — version comparison catches it
    value = await pod_b.get("key_1")
    print(f"  Pod B after pod A's update: {value} (version compare worked)")


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    async def main():
        await demo_single_pod()
        await demo_multi_pod_invalidation()
        await demo_pareto_workload()
        await demo_versioning()

        print("\n" + "=" * 60)
        print("KEY TAKEAWAYS")
        print("=" * 60)
        print("""
1. L1 (in-process) — fastest, but per-pod
2. L2 (Redis) — shared, ~1ms
3. L3 (DB) — source of truth, slowest
4. Read order: L1 → L2 → L3, populate on miss
5. Invalidation: Pub/Sub OR short TTL OR versioning
6. Don't cache personalized data in L1
7. Monitor hit rate per level
8. L1 small + short TTL is usually right balance
""")

    asyncio.run(main())
