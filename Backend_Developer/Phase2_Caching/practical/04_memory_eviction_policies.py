"""
============================================================
MEMORY EVICTION POLICIES — Practical
============================================================
Demonstrates LRU, LFU, FIFO, random in-process.
Shows how to configure Redis policies.
Plus Python LRU/LFU implementations from scratch.
"""
from __future__ import annotations
import random
import time
from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field
from typing import Any
import heapq


# ============================================================
# 1. LRU CACHE (from scratch)
# ============================================================
class LRUCache:
    """Least Recently Used — evict oldest access.
    O(1) get/put using OrderedDict."""

    def __init__(self, capacity: int):
        self.capacity = capacity
        self._store: OrderedDict[Any, Any] = OrderedDict()

    def get(self, key):
        if key not in self._store:
            return None
        # Move to end (most recent)
        self._store.move_to_end(key)
        return self._store[key]

    def put(self, key, value):
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = value
        if len(self._store) > self.capacity:
            evicted, _ = self._store.popitem(last=False)   # oldest = first
            return evicted   # what was evicted
        return None

    def __len__(self):
        return len(self._store)


# ============================================================
# 2. LFU CACHE (from scratch — O(1))
# ============================================================
class LFUCache:
    """Least Frequently Used — evict least accessed.
    Tracks frequency + recency within frequency tier."""

    def __init__(self, capacity: int):
        self.capacity = capacity
        self.min_freq = 0
        self._values: dict = {}                    # key -> value
        self._freqs: dict = {}                     # key -> freq
        self._buckets: dict[int, OrderedDict] = defaultdict(OrderedDict)  # freq -> ordered keys

    def _bump(self, key):
        freq = self._freqs[key]
        del self._buckets[freq][key]
        if not self._buckets[freq] and freq == self.min_freq:
            self.min_freq += 1
        new_freq = freq + 1
        self._freqs[key] = new_freq
        self._buckets[new_freq][key] = None

    def get(self, key):
        if key not in self._values:
            return None
        self._bump(key)
        return self._values[key]

    def put(self, key, value):
        evicted = None
        if key in self._values:
            self._values[key] = value
            self._bump(key)
            return None
        if len(self._values) >= self.capacity:
            # Evict from lowest freq bucket — oldest in that bucket
            evicted, _ = self._buckets[self.min_freq].popitem(last=False)
            del self._values[evicted]
            del self._freqs[evicted]
        self._values[key] = value
        self._freqs[key] = 1
        self._buckets[1][key] = None
        self.min_freq = 1
        return evicted


# ============================================================
# 3. FIFO CACHE (insertion order)
# ============================================================
class FIFOCache:
    """Evict in insertion order, ignoring access."""

    def __init__(self, capacity: int):
        self.capacity = capacity
        self._store = OrderedDict()

    def get(self, key):
        return self._store.get(key)

    def put(self, key, value):
        if key in self._store:
            self._store[key] = value
            return None
        self._store[key] = value
        if len(self._store) > self.capacity:
            evicted, _ = self._store.popitem(last=False)
            return evicted
        return None


# ============================================================
# 4. RANDOM CACHE
# ============================================================
class RandomCache:
    def __init__(self, capacity: int):
        self.capacity = capacity
        self._store: dict = {}

    def get(self, key):
        return self._store.get(key)

    def put(self, key, value):
        evicted = None
        if key not in self._store and len(self._store) >= self.capacity:
            evicted = random.choice(list(self._store))
            del self._store[evicted]
        self._store[key] = value
        return evicted


# ============================================================
# 5. TTL CACHE (volatile-ttl style)
# ============================================================
class TTLCache:
    """Evict by earliest expiry. Uses min-heap of expiries."""

    def __init__(self, capacity: int):
        self.capacity = capacity
        self._store: dict = {}                       # key -> (value, expiry)
        self._heap: list[tuple[float, str]] = []     # (expiry, key)

    def put(self, key, value, ttl: float):
        now = time.time()
        expiry = now + ttl

        self._cleanup_expired(now)

        if key in self._store:
            self._store[key] = (value, expiry)
        else:
            if len(self._store) >= self.capacity:
                # Evict earliest expiry
                while self._heap:
                    exp, ek = heapq.heappop(self._heap)
                    if ek in self._store and self._store[ek][1] == exp:
                        del self._store[ek]
                        break
            self._store[key] = (value, expiry)
        heapq.heappush(self._heap, (expiry, key))

    def get(self, key):
        if key not in self._store:
            return None
        value, expiry = self._store[key]
        if expiry < time.time():
            del self._store[key]
            return None
        return value

    def _cleanup_expired(self, now):
        while self._heap and self._heap[0][0] < now:
            exp, key = heapq.heappop(self._heap)
            if key in self._store and self._store[key][1] == exp:
                del self._store[key]


# ============================================================
# 6. REDIS CONFIGURATION TEMPLATE
# ============================================================
REDIS_CONFIG = """
# /etc/redis/redis.conf

# ===== MEMORY LIMIT =====
maxmemory 4gb                       # set max RAM

# ===== EVICTION POLICY =====
# Most common: allkeys-lru
maxmemory-policy allkeys-lru

# Other options:
#   noeviction          -- error on write when full
#   allkeys-lru         -- LRU on all keys (most common)
#   allkeys-lfu         -- LFU on all keys (popular content)
#   allkeys-random      -- random eviction
#   volatile-lru        -- LRU only on TTL keys
#   volatile-lfu        -- LFU only on TTL keys
#   volatile-random     -- random on TTL keys
#   volatile-ttl        -- earliest expiry first

# Eviction sampling accuracy (higher = better, slower)
maxmemory-samples 10                # default 5

# ===== LFU TUNING =====
lfu-log-factor 10                   # counter growth (higher = slower)
lfu-decay-time 1                    # decay in minutes

# ===== HASH ENCODING (memory optimization) =====
hash-max-listpack-entries 128
hash-max-listpack-value 64
list-max-listpack-size -2

# Check effective config
# 127.0.0.1:6379> CONFIG GET maxmemory-policy
# 127.0.0.1:6379> CONFIG SET maxmemory-policy allkeys-lfu
"""


# ============================================================
# 7. POLICY DEMO + COMPARISON
# ============================================================
def demo_policies():
    """Compare hit rate of different policies on same workload."""
    print("=" * 60)
    print("CACHE POLICY COMPARISON")
    print("=" * 60)

    # Simulated workload: 80% of accesses to 20% of keys (Pareto)
    HOT_KEYS = list(range(20))
    COLD_KEYS = list(range(20, 100))
    workload = []
    for _ in range(10000):
        if random.random() < 0.8:
            workload.append(random.choice(HOT_KEYS))
        else:
            workload.append(random.choice(COLD_KEYS))

    capacity = 30   # smaller than total keys

    def measure(cache_class):
        cache = cache_class(capacity)
        hits = misses = 0
        for key in workload:
            if cache.get(key) is None:
                misses += 1
                cache.put(key, f"value_{key}")
            else:
                hits += 1
        return hits / (hits + misses) * 100

    print(f"\n  Workload: 80% accesses on 20% keys (Pareto), capacity={capacity}")
    print(f"  Total accesses: {len(workload)}")
    print(f"\n  Hit rates:")
    print(f"    LRU    : {measure(LRUCache):.1f}%")
    print(f"    LFU    : {measure(LFUCache):.1f}%")
    print(f"    FIFO   : {measure(FIFOCache):.1f}%")
    print(f"    Random : {measure(RandomCache):.1f}%")
    print(f"\n  Result: LFU usually wins for skewed access patterns")


# ============================================================
# 8. LRU vs LFU specific scenario
# ============================================================
def demo_lru_vs_lfu():
    print("\n" + "=" * 60)
    print("LRU vs LFU — SCANNING ATTACK")
    print("=" * 60)

    # Scenario: 5 hot keys constantly accessed +
    # 1000 cold keys accessed once (scan)
    HOT = list(range(5))
    SCAN = list(range(100, 1100))

    workload = []
    for _ in range(2000):
        # 50% hot accesses
        workload.append(random.choice(HOT))
        # 50% scan accesses (one-time)
        workload.append(SCAN.pop() if SCAN else random.choice(HOT))

    capacity = 10

    def measure(cache_class):
        cache = cache_class(capacity)
        hits = 0
        for key in workload:
            if cache.get(key) is not None:
                hits += 1
            else:
                cache.put(key, f"v_{key}")
        return hits / len(workload) * 100

    print(f"  5 hot keys + 1000 one-time scan keys")
    print(f"  Capacity = {capacity}")
    print(f"  LRU hit rate: {measure(LRUCache):.1f}%  (scan evicts hot keys)")
    print(f"  LFU hit rate: {measure(LFUCache):.1f}%  (resilient to scans!)")


# ============================================================
# 9. PYTHON STDLIB — functools.lru_cache
# ============================================================
def demo_stdlib_lru():
    print("\n" + "=" * 60)
    print("Python stdlib: @functools.lru_cache")
    print("=" * 60)

    from functools import lru_cache

    @lru_cache(maxsize=128)
    def expensive(x):
        # Simulates slow computation
        return x ** 2

    # Fast after first call
    for i in [1, 2, 3, 1, 2, 3]:
        expensive(i)

    info = expensive.cache_info()
    print(f"  CacheInfo: {info}")
    print(f"  Hit rate: {info.hits / (info.hits + info.misses) * 100:.0f}%")


# ============================================================
# 10. Cachetools library reference
# ============================================================
CACHETOOLS_USAGE = """
# pip install cachetools
from cachetools import LRUCache, LFUCache, TTLCache, FIFOCache

# Simple LRU
cache = LRUCache(maxsize=128)
cache["key"] = "value"
print(cache["key"])

# TTL cache (expires after 60s)
cache = TTLCache(maxsize=128, ttl=60)

# As decorator
from cachetools import cached
@cached(LRUCache(maxsize=128))
def expensive(x):
    return x ** 2

# With locking (thread-safe)
import threading
@cached(LRUCache(128), lock=threading.Lock())
def thread_safe_fn(x):
    return x ** 2

# Async (asyncache)
# pip install asyncache
from asyncache import cached as async_cached
@async_cached(TTLCache(maxsize=100, ttl=60))
async def async_expensive(x):
    return x ** 2
"""


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    demo_policies()
    demo_lru_vs_lfu()
    demo_stdlib_lru()

    print("\n" + "=" * 60)
    print("REDIS CONFIG TEMPLATE")
    print("=" * 60)
    print(REDIS_CONFIG)

    print("\n--- CACHETOOLS REFERENCE ---")
    print(CACHETOOLS_USAGE)

    print("\n" + "=" * 60)
    print("KEY TAKEAWAYS")
    print("=" * 60)
    print("""
1. LRU = default choice (most workloads)
2. LFU = better for skewed access (top-N, scan-resistant)
3. FIFO = simple but ignores access (rarely used)
4. Random = baseline, surprisingly OK for uniform workloads
5. TTL = explicit expiry, no algorithm needed
6. Redis default: noeviction (DANGEROUS) — always set explicit policy
7. maxmemory-samples=10 for better LRU/LFU accuracy
""")
