"""
Caching Patterns — Practical Implementation
============================================
Python Backend Developer Interview Prep (40 LPA)

Har demo standalone runnable hai — Redis ki zarurat nahi (in-memory mock use karta hai).
Redis wala code bhi dikhaya hai (commented) taaki production reference mile.

Usage:
    python 01_caching_patterns.py         # All demos run karo
    python 01_caching_patterns.py demo    # Specific demo (same as all)
    python 01_caching_patterns.py list    # List all available demos

Dependencies:
    Required  : None (standard library only)
    Optional  : cachetools (pip install cachetools) — graceful fallback included
    Production: redis (pip install redis), aiocache, aioredis
"""

import time
import threading
import queue
import random
import json
import sys
from functools import wraps, lru_cache
from typing import Optional, Any, Callable, Dict, List, Tuple
from collections import OrderedDict

# ---------------------------------------------------------------------------
# Optional dependency: cachetools (graceful fallback)
# ---------------------------------------------------------------------------
try:
    from cachetools import TTLCache, LRUCache, LFUCache, cached as ct_cached
    CACHETOOLS_AVAILABLE = True
except ImportError:
    CACHETOOLS_AVAILABLE = False
    print("[INFO] cachetools not installed. Some demos will use fallback implementation.")
    print("       Install: pip install cachetools\n")


# ===========================================================================
# SECTION 0 — InMemoryCache (Redis ka in-process mock)
# ===========================================================================

class InMemoryCache:
    """
    Thread-safe TTL-based in-memory cache.
    Redis ko simulate karta hai local demos ke liye.

    Production mein is class ki jagah redis.Redis() use karo.
    """

    def __init__(self):
        self._store: Dict[str, Any] = {}
        self._expiry: Dict[str, float] = {}
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            # TTL check
            if key in self._expiry and time.time() > self._expiry[key]:
                self._store.pop(key, None)
                self._expiry.pop(key, None)
                self._misses += 1
                return None
            val = self._store.get(key)
            if val is not None:
                self._hits += 1
            else:
                self._misses += 1
            return val

    def set(self, key: str, value: Any, ttl: int = 60) -> None:
        with self._lock:
            self._store[key] = value
            self._expiry[key] = time.time() + ttl

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)
            self._expiry.pop(key, None)

    def exists(self, key: str) -> bool:
        return self.get(key) is not None

    def incr(self, key: str) -> int:
        with self._lock:
            val = self._store.get(key, 0) + 1
            self._store[key] = val
            return val

    def flush(self) -> None:
        with self._lock:
            self._store.clear()
            self._expiry.clear()

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    def stats(self) -> Dict[str, Any]:
        return {
            "keys": len(self._store),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{self.hit_rate:.1%}",
        }


# ===========================================================================
# SECTION 1 — Cache-Aside (Lazy Loading)
# ===========================================================================

# Fake DB — production mein yeh actual DB calls honge
_fake_db: Dict[int, Dict] = {
    1: {"id": 1, "name": "Alice", "email": "alice@example.com", "role": "admin"},
    2: {"id": 2, "name": "Bob",   "email": "bob@example.com",   "role": "user"},
    3: {"id": 3, "name": "Carol", "email": "carol@example.com", "role": "user"},
}
_db_call_count = 0


def _reset_db_call_count():
    global _db_call_count
    _db_call_count = 0


def get_user_from_db(user_id: int) -> Optional[Dict]:
    """Simulates a slow DB call (50ms latency)."""
    global _db_call_count
    _db_call_count += 1
    time.sleep(0.05)  # 50ms DB latency
    return _fake_db.get(user_id)


def update_user_in_db(user_id: int, data: Dict) -> bool:
    """Simulates DB write."""
    global _fake_db
    if user_id in _fake_db:
        _fake_db[user_id].update(data)
        return True
    return False


def get_user_cache_aside(cache: InMemoryCache, user_id: int) -> Optional[Dict]:
    """
    Cache-Aside pattern implementation.

    Flow:
      1. Cache mein check karo
      2. HIT → return immediately
      3. MISS → DB se fetch → cache mein store → return
    """
    key = f"user:{user_id}"

    # Step 1: Cache check
    cached = cache.get(key)
    if cached is not None:
        print(f"    [HIT]  Cache hit  → user:{user_id}")
        return cached

    # Step 2: Cache miss — DB se fetch
    print(f"    [MISS] Cache miss → user:{user_id} (fetching from DB...)")
    user = get_user_from_db(user_id)

    # Step 3: Store in cache with TTL
    if user:
        cache.set(key, user, ttl=30)

    return user


def update_user_cache_aside(cache: InMemoryCache, user_id: int, data: Dict) -> bool:
    """Update pattern: DB mein write → cache invalidate karo."""
    success = update_user_in_db(user_id, data)
    if success:
        cache.delete(f"user:{user_id}")
        print(f"    [INV]  Cache invalidated → user:{user_id}")
    return success


def demo_cache_aside():
    print("\n" + "=" * 60)
    print("DEMO 1: Cache-Aside (Lazy Loading)")
    print("=" * 60)

    cache = InMemoryCache()
    _reset_db_call_count()

    print("\n--- 3 requests for user:1 (expect 1 DB call) ---")
    for i in range(3):
        t0 = time.time()
        user = get_user_cache_aside(cache, 1)
        elapsed_ms = (time.time() - t0) * 1000
        print(f"    Request {i+1}: {user['name']!r} in {elapsed_ms:.1f}ms")

    print(f"\n    DB calls made: {_db_call_count} (expected: 1)")

    print("\n--- Update user:1 → cache invalidated ---")
    update_user_cache_aside(cache, 1, {"role": "superadmin"})

    print("\n--- Next request after update (expect 1 more DB call) ---")
    _reset_db_call_count()
    user = get_user_cache_aside(cache, 1)
    print(f"    Updated role: {user['role']!r}")
    print(f"    DB calls after update: {_db_call_count} (expected: 1)")

    print(f"\n    Cache stats: {cache.stats()}")


# ===========================================================================
# SECTION 2 — Read-Through Cache
# ===========================================================================

class ReadThroughCache:
    """
    Read-Through: Cache internally DB se data laata hai on miss.
    App ko sirf cache se baat karni hai — miss handling hidden hai.

    Cache-Aside se fark:
      Cache-Aside: App cache miss detect karta hai aur DB call karta hai
      Read-Through: Cache khud DB call karta hai — app agnostic hai
    """

    def __init__(self, loader_fn: Callable, ttl: int = 60):
        self._cache = InMemoryCache()
        self._loader = loader_fn
        self._ttl = ttl

    def get(self, key: str, *loader_args, **loader_kwargs) -> Optional[Any]:
        """
        Single interface — app bas get() call karta hai.
        Miss hone par loader_fn automatically call hoti hai.
        """
        val = self._cache.get(key)
        if val is not None:
            return val

        # Cache internally DB se load karta hai (app ko pata nahi)
        val = self._loader(*loader_args, **loader_kwargs)
        if val is not None:
            self._cache.set(key, val, ttl=self._ttl)
        return val

    def invalidate(self, key: str):
        self._cache.delete(key)

    @property
    def stats(self):
        return self._cache.stats()


def demo_read_through():
    print("\n" + "=" * 60)
    print("DEMO 2: Read-Through Cache")
    print("=" * 60)

    _reset_db_call_count()

    # App ko pata nahi DB kab hit hota hai
    product_cache = ReadThroughCache(
        loader_fn=lambda pid: {
            "id": pid,
            "name": f"Product {pid}",
            "price": pid * 99,
        },
        ttl=60,
    )

    print("\n--- App sirf cache.get() karta hai ---")
    for req_num in range(1, 5):
        key = f"product:{req_num % 2 + 1}"  # product:1 aur product:2 alternate
        product = product_cache.get(key, pid=req_num % 2 + 1)
        src = "cache" if req_num > 2 else "DB (via cache)"
        print(f"    Request {req_num}: {product['name']!r} — loaded from {src}")

    print(f"\n    Cache stats: {product_cache.stats}")
    print("    Notice: App code mein koi DB logic nahi hai!")


# ===========================================================================
# SECTION 3 — Write-Through Cache
# ===========================================================================

class WriteThroughCache:
    """
    Write-Through: Har write cache + DB dono mein simultaneously.
    Cache hamesha consistent rehta hai DB ke saath.

    Pros: Strong consistency, reads hamesha fresh
    Cons: Write latency (2 writes), cache fills with rarely-read data
    """

    def __init__(self, db_write_fn: Callable, db_read_fn: Callable):
        self._cache = InMemoryCache()
        self._db_write = db_write_fn
        self._db_read = db_read_fn
        self.write_count = 0

    def write(self, key: str, value: Any, ttl: int = 60) -> bool:
        """
        Write karo — BOTH cache aur DB mein.
        DB fail hone par cache update mat karo.
        """
        try:
            # DB pehle (source of truth)
            self._db_write(key, value)

            # Sirf DB success par cache update
            self._cache.set(key, value, ttl=ttl)
            self.write_count += 1
            return True

        except Exception as e:
            # DB fail → cache touch mat karo
            print(f"    [ERROR] DB write failed, cache NOT updated: {e}")
            return False

    def read(self, key: str) -> Optional[Any]:
        """Read — cache se (write-through ensures freshness)."""
        val = self._cache.get(key)
        if val is not None:
            return val

        # Edge case: cache miss (Redis restart, TTL expire)
        val = self._db_read(key)
        if val:
            self._cache.set(key, val)
        return val


def demo_write_through():
    print("\n" + "=" * 60)
    print("DEMO 3: Write-Through Cache")
    print("=" * 60)

    # Simulated DB store
    _db_store = {}

    def db_write(key, value):
        time.sleep(0.02)  # 20ms DB write latency
        _db_store[key] = value
        print(f"    [DB]   Written to DB: {key}")

    def db_read(key):
        return _db_store.get(key)

    wt_cache = WriteThroughCache(db_write_fn=db_write, db_read_fn=db_read)

    print("\n--- Write user data ---")
    users = [
        ("user:10", {"id": 10, "name": "Dave", "email": "dave@test.com"}),
        ("user:11", {"id": 11, "name": "Eve",  "email": "eve@test.com"}),
    ]

    for key, user_data in users:
        t0 = time.time()
        wt_cache.write(key, user_data, ttl=300)
        elapsed_ms = (time.time() - t0) * 1000
        print(f"    Write {key}: {elapsed_ms:.1f}ms (DB + Cache both written)")

    print("\n--- Read back (should be instant from cache) ---")
    for key, _ in users:
        t0 = time.time()
        user = wt_cache.read(key)
        elapsed_ms = (time.time() - t0) * 1000
        print(f"    Read {key}: {user['name']!r} in {elapsed_ms:.2f}ms (cache hit!)")

    print(f"\n    Total writes: {wt_cache.write_count}")
    print(f"    DB store: {list(_db_store.keys())}")
    print("    Consistency verified: DB aur Cache dono mein same data")


# ===========================================================================
# SECTION 4 — Write-Behind (Write-Back) with Background Flush
# ===========================================================================

class WriteBehindCache:
    """
    Write-Behind: Cache mein immediately likho, DB mein async flush karo.

    Use case: High-write workloads — view counters, likes, analytics
    Risk: Cache crash = unflushed data lost (WAL se mitigate karo)
    """

    def __init__(self, db_flush_fn: Callable, flush_interval: float = 0.5,
                 batch_size: int = 50):
        self._cache: Dict[str, Any] = {}
        self._dirty: set = set()
        self._write_queue: queue.Queue = queue.Queue()
        self._db_flush = db_flush_fn
        self._flush_interval = flush_interval
        self._batch_size = batch_size
        self._lock = threading.Lock()
        self._flush_count = 0
        self._items_flushed = 0
        self._running = True

        # Background flush thread
        self._flush_thread = threading.Thread(
            target=self._background_flush,
            daemon=True,
            name="WriteBehind-Flush",
        )
        self._flush_thread.start()

    def write(self, key: str, value: Any) -> None:
        """Instant write — sirf cache mein (fast!)."""
        with self._lock:
            self._cache[key] = value
            self._dirty.add(key)
        self._write_queue.put((key, value))

    def read(self, key: str) -> Optional[Any]:
        """Read — cache se (may include data not yet in DB)."""
        with self._lock:
            return self._cache.get(key)

    def _background_flush(self) -> None:
        """Background thread: batch collect karke DB mein flush karo."""
        pending: Dict[str, Any] = {}

        while self._running:
            # Batch collect within time window
            deadline = time.time() + self._flush_interval

            while time.time() < deadline and len(pending) < self._batch_size:
                try:
                    key, value = self._write_queue.get(timeout=0.05)
                    pending[key] = value  # Latest value rakhte hain (automatic dedup)
                except queue.Empty:
                    pass

            # Flush accumulated batch
            if pending:
                try:
                    self._db_flush(pending.copy())
                    with self._lock:
                        for key in pending:
                            self._dirty.discard(key)
                    self._flush_count += 1
                    self._items_flushed += len(pending)
                    print(f"    [Flush #{self._flush_count}] {len(pending)} keys → DB")
                except Exception as e:
                    print(f"    [Flush ERROR] {e}")
                pending.clear()

    def stop_and_flush(self):
        """Graceful shutdown: remaining writes flush karo."""
        self._running = False
        # Drain queue
        remaining = {}
        while not self._write_queue.empty():
            try:
                key, value = self._write_queue.get_nowait()
                remaining[key] = value
            except queue.Empty:
                break
        if remaining:
            self._db_flush(remaining)
            print(f"    [Final Flush] {len(remaining)} keys flushed on shutdown")

    @property
    def pending_count(self) -> int:
        return len(self._dirty)


def demo_write_behind():
    print("\n" + "=" * 60)
    print("DEMO 4: Write-Behind (Write-Back) Cache")
    print("=" * 60)

    db_records: Dict[str, Any] = {}
    flush_calls = [0]

    def db_flush_fn(batch: Dict):
        """Simulates batch DB write."""
        time.sleep(0.03)  # 30ms for entire batch
        db_records.update(batch)
        flush_calls[0] += 1

    wb_cache = WriteBehindCache(
        db_flush_fn=db_flush_fn,
        flush_interval=0.3,
        batch_size=20,
    )

    print("\n--- Rapid writes (counter simulation) ---")
    t0 = time.time()
    for video_id in range(1, 6):  # 5 videos
        for _ in range(10):  # 10 views each
            current = wb_cache.read(f"views:video:{video_id}") or 0
            wb_cache.write(f"views:video:{video_id}", current + 1)

    write_time_ms = (time.time() - t0) * 1000
    print(f"    50 writes completed in {write_time_ms:.1f}ms (all in-memory, NO DB wait)")
    print(f"    Pending flush: {wb_cache.pending_count} keys")

    # Cache mein immediately readable
    print("\n--- Cache reads (instant, includes unflushed data) ---")
    for video_id in range(1, 6):
        views = wb_cache.read(f"views:video:{video_id}")
        print(f"    video:{video_id} views = {views}")

    print("\n--- Waiting for background flush (1 second) ---")
    time.sleep(1.0)

    print("\n--- DB state after flush ---")
    for video_id in range(1, 6):
        db_val = db_records.get(f"views:video:{video_id}", "NOT YET FLUSHED")
        print(f"    DB video:{video_id} views = {db_val}")

    wb_cache.stop_and_flush()
    print(f"\n    Total flush batches: {flush_calls[0]}")
    print(f"    Total items in DB: {len(db_records)}")
    print("    Note: 50 writes → DB but via batching (efficient!)")


# ===========================================================================
# SECTION 5 — Cache Stampede Prevention (Thundering Herd)
# ===========================================================================

class StampedeProtectedCache:
    """
    Thundering Herd solution: Mutex lock per cache key.

    Sirf ek thread DB se fetch karta hai.
    Baaki sab wait karte hain aur cached result lete hain.
    Double-checked locking pattern use kiya hai.
    """

    def __init__(self):
        self._cache = InMemoryCache()
        self._key_locks: Dict[str, threading.Lock] = {}
        self._meta_lock = threading.Lock()
        self.compute_count = 0

    def _get_key_lock(self, key: str) -> threading.Lock:
        """Per-key lock laao (create agar exist nahi karta)."""
        with self._meta_lock:
            if key not in self._key_locks:
                self._key_locks[key] = threading.Lock()
            return self._key_locks[key]

    def get_or_compute(self, key: str, compute_fn: Callable,
                        ttl: int = 30) -> Any:
        """
        1. Fast path: Cache check (no lock)
        2. Slow path: Acquire per-key lock → double-check → compute → cache
        """
        # Fast path (no lock — concurrent reads allowed)
        val = self._cache.get(key)
        if val is not None:
            return val

        # Slow path — per-key lock
        key_lock = self._get_key_lock(key)

        with key_lock:
            # Double-check: ho sakta hai lock wait mein kisi ne fill kar diya
            val = self._cache.get(key)
            if val is not None:
                return val

            # Yeh request "winner" hai — DB se fetch karega
            self.compute_count += 1
            val = compute_fn()
            self._cache.set(key, val, ttl=ttl)
            return val


def demo_stampede_prevention():
    print("\n" + "=" * 60)
    print("DEMO 5: Cache Stampede Prevention (Thundering Herd)")
    print("=" * 60)

    protected_cache = StampedeProtectedCache()
    results = []
    errors = []

    def expensive_db_query():
        """Simulate 200ms slow DB query."""
        time.sleep(0.2)
        return {
            "trending_posts": [f"post_{i}" for i in range(10)],
            "computed_at": time.time(),
        }

    print("\n--- Without protection: 20 concurrent requests would fire 20 DB queries ---")
    print("--- With Mutex Lock: Only 1 DB query, 19 threads wait ---\n")

    def worker():
        try:
            result = protected_cache.get_or_compute(
                "trending:posts",
                expensive_db_query,
                ttl=60,
            )
            results.append(result)
        except Exception as e:
            errors.append(str(e))

    # Launch 20 concurrent requests simultaneously
    threads = [threading.Thread(target=worker) for _ in range(20)]
    t0 = time.time()

    # Start all threads at once
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    elapsed_ms = (time.time() - t0) * 1000

    print(f"    20 concurrent requests completed in {elapsed_ms:.0f}ms")
    print(f"    DB (compute_fn) called: {protected_cache.compute_count} times (expected: 1)")
    print(f"    All 20 results identical: {len(set(str(r) for r in results)) == 1}")
    if errors:
        print(f"    Errors: {errors}")


# ===========================================================================
# SECTION 6 — Multi-Layer Cache (L1 + L2)
# ===========================================================================

# Fallback TTLCache agar cachetools nahi hai
class _FallbackTTLCache:
    """Simple TTL dict — cachetools ka fallback."""

    def __init__(self, maxsize: int, ttl: int):
        self._store: OrderedDict = OrderedDict()
        self._expiry: Dict[str, float] = {}
        self._maxsize = maxsize
        self._ttl = ttl
        self._lock = threading.Lock()

    def __contains__(self, key: str) -> bool:
        with self._lock:
            if key in self._store:
                if time.time() < self._expiry.get(key, 0):
                    return True
                self._store.pop(key, None)
                self._expiry.pop(key, None)
            return False

    def __getitem__(self, key: str):
        with self._lock:
            if key in self._store and time.time() < self._expiry.get(key, 0):
                self._store.move_to_end(key)
                return self._store[key]
            raise KeyError(key)

    def __setitem__(self, key: str, value):
        with self._lock:
            if len(self._store) >= self._maxsize:
                # Evict LRU
                self._store.popitem(last=False)
            self._store[key] = value
            self._expiry[key] = time.time() + self._ttl

    def pop(self, key, default=None):
        with self._lock:
            self._expiry.pop(key, None)
            return self._store.pop(key, default)

    def __len__(self):
        return len(self._store)


class MultiLayerCache:
    """
    L1 + L2 Multi-Layer Cache:
      L1 = In-process (microseconds, per-process, small)
      L2 = Redis-like (milliseconds, shared, large)

    Production mein L2 = actual Redis.
    """

    def __init__(self, l1_maxsize: int = 100, l1_ttl: int = 10,
                 l2_ttl: int = 300):
        # L1: Very fast in-process cache
        if CACHETOOLS_AVAILABLE:
            self._l1 = TTLCache(maxsize=l1_maxsize, ttl=l1_ttl)
        else:
            self._l1 = _FallbackTTLCache(maxsize=l1_maxsize, ttl=l1_ttl)
        self._l1_lock = threading.RLock()

        # L2: Shared cache (Redis simulator)
        self._l2 = InMemoryCache()
        self._l2_ttl = l2_ttl

        # Stats
        self._l1_hits = 0
        self._l2_hits = 0
        self._db_hits = 0
        self._total = 0

    def get(self, key: str,
            db_loader: Optional[Callable] = None,
            *loader_args) -> Tuple[Optional[Any], str]:
        """
        Returns (value, source) where source in {"L1", "L2", "DB", "MISS"}
        """
        self._total += 1

        # L1 check (in-process, no network)
        with self._l1_lock:
            if key in self._l1:
                self._l1_hits += 1
                return self._l1[key], "L1"

        # L2 check (Redis-like, network hop)
        l2_val = self._l2.get(key)
        if l2_val is not None:
            # Promote to L1
            with self._l1_lock:
                self._l1[key] = l2_val
            self._l2_hits += 1
            return l2_val, "L2"

        # DB fallback
        if db_loader:
            val = db_loader(*loader_args)
            if val is not None:
                self.set(key, val)
            self._db_hits += 1
            return val, "DB"

        return None, "MISS"

    def set(self, key: str, value: Any, l1_override_ttl: Optional[int] = None) -> None:
        with self._l1_lock:
            self._l1[key] = value
        self._l2.set(key, value, ttl=self._l2_ttl)

    def invalidate(self, key: str) -> None:
        with self._l1_lock:
            self._l1.pop(key, None)
        self._l2.delete(key)

    def hit_rate_summary(self) -> Dict[str, Any]:
        total = max(self._total, 1)
        return {
            "total_requests": self._total,
            "l1_hits": self._l1_hits,
            "l2_hits": self._l2_hits,
            "db_hits": self._db_hits,
            "l1_hit_rate": f"{self._l1_hits / total:.1%}",
            "l2_hit_rate": f"{self._l2_hits / total:.1%}",
            "db_hit_rate": f"{self._db_hits / total:.1%}",
        }


def demo_multi_layer_cache():
    print("\n" + "=" * 60)
    print("DEMO 6: Multi-Layer Cache (L1 In-Process + L2 Redis-like)")
    print("=" * 60)

    lib_name = "cachetools" if CACHETOOLS_AVAILABLE else "fallback (OrderedDict)"
    print(f"\n    L1 implementation: {lib_name}")

    ml_cache = MultiLayerCache(l1_maxsize=10, l1_ttl=5, l2_ttl=60)

    # Seed L2 (simulate data already in Redis from another instance)
    for i in range(1, 6):
        ml_cache._l2.set(f"product:{i}", {"id": i, "name": f"Product {i}"}, ttl=60)

    print("\n--- First pass: L2 hits (data in Redis, not in L1 yet) ---")
    source_counts = {"L1": 0, "L2": 0, "DB": 0, "MISS": 0}

    for i in range(1, 6):
        val, source = ml_cache.get(f"product:{i}")
        source_counts[source] += 1
        print(f"    product:{i} → {val['name']!r} (from {source})")

    print("\n--- Second pass: L1 hits (promoted from L2) ---")
    for i in range(1, 6):
        val, source = ml_cache.get(f"product:{i}")
        source_counts[source] += 1
        print(f"    product:{i} → {val['name']!r} (from {source})")

    print("\n--- DB fallback (product:99 not in any cache) ---")
    def db_fetch(pid):
        time.sleep(0.05)
        return {"id": pid, "name": f"Product {pid} (from DB)"}

    val, source = ml_cache.get("product:99", db_fetch, 99)
    print(f"    product:99 → {val['name']!r} (from {source})")
    source_counts[source] += 1

    print(f"\n    Source breakdown: {source_counts}")
    print(f"    Hit rate summary: {ml_cache.hit_rate_summary()}")


# ===========================================================================
# SECTION 7 — Cache Decorator (Universal)
# ===========================================================================

def cached(ttl: int = 60, key_fn: Optional[Callable] = None):
    """
    Universal caching decorator.

    Features:
      - Custom key function support
      - Built-in invalidation method
      - Per-function cache instance
      - Thread-safe

    Usage:
        @cached(ttl=30, key_fn=lambda user_id: f"user:{user_id}")
        def get_user(user_id: int) -> dict: ...

        # Invalidate
        get_user.invalidate(user_id=123)
    """
    cache_instance = InMemoryCache()

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            # Key generate karo
            if key_fn:
                key = key_fn(*args, **kwargs)
            else:
                # Default key: function name + args
                key = f"{fn.__module__}.{fn.__name__}:{args}:{sorted(kwargs.items())}"

            result = cache_instance.get(key)
            if result is not None:
                return result

            result = fn(*args, **kwargs)
            if result is not None:
                cache_instance.set(key, result, ttl=ttl)
            return result

        # Attach helpers to decorated function
        wrapper.cache = cache_instance
        wrapper.cache_stats = lambda: cache_instance.stats()

        def invalidate(*args, **kwargs):
            if key_fn:
                key = key_fn(*args, **kwargs)
            else:
                key = f"{fn.__module__}.{fn.__name__}:{args}:{sorted(kwargs.items())}"
            cache_instance.delete(key)
            print(f"    [INV] Invalidated: {key}")

        wrapper.invalidate = invalidate
        return wrapper

    return decorator


# Decorated function examples
@cached(ttl=30, key_fn=lambda user_id: f"profile:{user_id}")
def get_user_profile(user_id: int) -> Dict:
    """Simulates expensive profile fetch."""
    time.sleep(0.08)
    return {
        "id": user_id,
        "name": f"User {user_id}",
        "bio": f"Bio for user {user_id}",
        "followers": user_id * 100,
    }


@cached(ttl=10)  # Default key (function name + args)
def compute_recommendations(user_id: int, category: str) -> List[str]:
    """Simulates ML recommendation computation."""
    time.sleep(0.1)
    return [f"{category}_item_{i}" for i in range(5)]


def demo_cache_decorator():
    print("\n" + "=" * 60)
    print("DEMO 7: Cache Decorator (Universal)")
    print("=" * 60)

    print("\n--- Profile fetch with custom key function ---")
    for i in range(3):
        t0 = time.time()
        profile = get_user_profile(user_id=42)
        elapsed_ms = (time.time() - t0) * 1000
        src = "DB (~80ms)" if i == 0 else "Cache (~0ms)"
        print(f"    Call {i+1}: {profile['name']!r} in {elapsed_ms:.1f}ms [{src}]")

    print(f"\n    Cache stats: {get_user_profile.cache_stats()}")

    print("\n--- Invalidation ---")
    get_user_profile.invalidate(user_id=42)
    t0 = time.time()
    profile = get_user_profile(user_id=42)
    elapsed_ms = (time.time() - t0) * 1000
    print(f"    Post-invalidation fetch: {elapsed_ms:.1f}ms (DB call again)")

    print("\n--- Recommendations with default key ---")
    recs1 = compute_recommendations(user_id=1, category="tech")
    recs2 = compute_recommendations(user_id=1, category="tech")  # cached
    recs3 = compute_recommendations(user_id=1, category="sports")  # different key
    print(f"    tech recommendations: {recs1[:3]}... (cached on 2nd call)")
    print(f"    sports recommendations: {recs3[:3]}... (different key)")
    print(f"    Cache stats: {compute_recommendations.cache_stats()}")


# ===========================================================================
# SECTION 8 — Version-Based Cache Invalidation
# ===========================================================================

class VersionedCache:
    """
    Version-based invalidation:
    Update pe version increment karo → old keys auto-stale
    SCAN karne ki zarurat nahi, atomic invalidation.

    Key pattern: {prefix}:{id}:v{version}
    """

    def __init__(self):
        self._cache = InMemoryCache()
        self._versions: Dict[str, int] = {}
        self._v_lock = threading.Lock()

    def _get_version(self, entity_id: str) -> int:
        with self._v_lock:
            return self._versions.get(entity_id, 1)

    def _increment_version(self, entity_id: str) -> int:
        with self._v_lock:
            new_version = self._versions.get(entity_id, 1) + 1
            self._versions[entity_id] = new_version
            return new_version

    def get(self, prefix: str, entity_id: str) -> Optional[Any]:
        version = self._get_version(entity_id)
        key = f"{prefix}:{entity_id}:v{version}"
        val = self._cache.get(key)
        if val is not None:
            print(f"    [HIT]  {key}")
        else:
            print(f"    [MISS] {key}")
        return val

    def set(self, prefix: str, entity_id: str, value: Any, ttl: int = 300) -> None:
        version = self._get_version(entity_id)
        key = f"{prefix}:{entity_id}:v{version}"
        self._cache.set(key, value, ttl=ttl)
        print(f"    [SET]  {key}")

    def invalidate(self, entity_id: str) -> None:
        """
        Increment version → all old keys become unreachable (stale).
        No need to find and delete old keys.
        """
        old_v = self._get_version(entity_id)
        new_v = self._increment_version(entity_id)
        print(f"    [VER]  {entity_id}: v{old_v} → v{new_v} (old cache auto-stale)")


def demo_versioned_invalidation():
    print("\n" + "=" * 60)
    print("DEMO 8: Version-Based Cache Invalidation")
    print("=" * 60)

    vc = VersionedCache()

    print("\n--- Initial fetch and cache ---")
    user_data = {"id": "u100", "name": "Frank", "email": "frank@test.com"}
    vc.set("user", "u100", user_data)
    result = vc.get("user", "u100")
    print(f"    Retrieved: {result['name']!r}")

    print("\n--- Update user (version increment = instant invalidation) ---")
    vc.invalidate("u100")

    print("\n--- Next read (different version key = cache miss) ---")
    result_after = vc.get("user", "u100")
    print(f"    Result: {result_after} (None = miss, would fetch from DB)")

    print("\n--- Set with new version ---")
    updated_user = {**user_data, "name": "Frank Updated"}
    vc.set("user", "u100", updated_user)
    result_new = vc.get("user", "u100")
    print(f"    New data: {result_new['name']!r}")

    print("\n    Benefit: No SCAN/DEL needed — just increment version counter!")


# ===========================================================================
# SECTION 9 — Cache Hit Rate Monitoring + Warm-Up Simulation
# ===========================================================================

class MonitoredCache:
    """
    Cache with hit rate tracking.
    Production mein yeh metrics Prometheus mein push karo.
    """

    def __init__(self, name: str = "default"):
        self._cache = InMemoryCache()
        self.name = name
        self._hits = 0
        self._misses = 0
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        val = self._cache.get(key)
        with self._lock:
            if val is not None:
                self._hits += 1
            else:
                self._misses += 1
        return val

    def set(self, key: str, value: Any, ttl: int = 60) -> None:
        self._cache.set(key, value, ttl=ttl)

    def delete(self, key: str) -> None:
        self._cache.delete(key)

    @property
    def hit_rate(self) -> float:
        with self._lock:
            total = self._hits + self._misses
            return self._hits / total if total > 0 else 0.0

    @property
    def total_requests(self) -> int:
        with self._lock:
            return self._hits + self._misses

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            total = max(self._hits + self._misses, 1)
            return {
                "name": self.name,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": f"{self._hits / total:.1%}",
                "total": self._hits + self._misses,
            }


def demo_cache_warmup_and_monitoring():
    print("\n" + "=" * 60)
    print("DEMO 9: Cache Hit Rate Monitoring + Warm-Up Simulation")
    print("=" * 60)

    monitored = MonitoredCache("product-cache")

    # Simulate 200 products in DB
    products = {f"product:{i}": {"id": i, "name": f"Product {i}"} for i in range(1, 201)}

    print("\n--- Cold start simulation (no warm-up) ---")
    print("    First 100 requests on empty cache:")

    checkpoints = []
    for req_num in range(1, 101):
        key = f"product:{random.randint(1, 20)}"  # 80/20 — 20 popular products
        val = monitored.get(key)

        if val is None:
            # Cache miss — simulate DB fetch + store
            monitored.set(key, products[key], ttl=300)

        if req_num % 10 == 0:
            checkpoints.append((req_num, monitored.hit_rate))
            print(f"    After {req_num:3d} requests: hit rate = {monitored.hit_rate:.1%}")

    print(f"\n    Final stats: {monitored.snapshot()}")

    print("\n--- Now simulate cache warm-up before load ---")
    warm_cache = MonitoredCache("product-cache-warmed")

    # Pre-populate top 20 products (warm-up)
    print("    Pre-warming top 20 products...")
    for i in range(1, 21):
        warm_cache.set(f"product:{i}", products[f"product:{i}"], ttl=300)
    print("    Warm-up complete!")

    print("\n    First 100 requests on warmed cache:")
    for req_num in range(1, 101):
        key = f"product:{random.randint(1, 20)}"
        val = warm_cache.get(key)

        if val is None:
            warm_cache.set(key, products[key], ttl=300)

        if req_num % 10 == 0:
            print(f"    After {req_num:3d} requests: hit rate = {warm_cache.hit_rate:.1%}")

    print(f"\n    Warmed cache stats: {warm_cache.snapshot()}")

    print("\n--- Comparison ---")
    print(f"    Cold start  hit rate at req 10: {checkpoints[0][1]:.1%}")
    print(f"    Cold start  hit rate at req 50: {checkpoints[4][1]:.1%}")
    print(f"    Cold start  hit rate at req 100: {checkpoints[-1][1]:.1%}")
    print(f"    Warmed cache hit rate at req 100: {warm_cache.hit_rate:.1%}")
    print("\n    Warm-up ensures high hit rate from request #1!")


# ===========================================================================
# SECTION 10 — functools.lru_cache Demo
# ===========================================================================

# lru_cache as settings loader (FastAPI pattern)
@lru_cache(maxsize=1)
def get_app_settings(env: str = "prod") -> Dict[str, Any]:
    """
    Settings loader — lru_cache ensures single load per process.
    FastAPI mein: @lru_cache() on get_settings() function.
    """
    print(f"    [LOAD] Loading settings for env={env!r} (only once per process!)")
    time.sleep(0.05)  # Simulate reading .env file
    return {
        "env": env,
        "db_url": "postgresql://localhost:5432/mydb",
        "redis_url": "redis://localhost:6379",
        "debug": env == "dev",
        "max_connections": 50,
    }


@lru_cache(maxsize=256)
def fibonacci(n: int) -> int:
    """Classic memoization with lru_cache — exponential to linear."""
    if n < 2:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)


def demo_lru_cache():
    print("\n" + "=" * 60)
    print("DEMO 10: functools.lru_cache")
    print("=" * 60)

    print("\n--- Settings singleton pattern ---")
    for i in range(3):
        settings = get_app_settings("prod")
        print(f"    Call {i+1}: db_url = {settings['db_url']!r}")
    print(f"    Cache info: {get_app_settings.cache_info()}")
    print("    Notice: Settings only loaded once, 2 cache hits!")

    print("\n--- Fibonacci memoization ---")
    t0 = time.time()
    result = fibonacci(35)
    elapsed_ms = (time.time() - t0) * 1000
    print(f"    fibonacci(35) = {result} in {elapsed_ms:.2f}ms")

    t0 = time.time()
    result = fibonacci(35)  # cached
    elapsed_ms = (time.time() - t0) * 1000
    print(f"    fibonacci(35) again = {result} in {elapsed_ms:.3f}ms (cached!)")
    print(f"    Cache info: {fibonacci.cache_info()}")


# ===========================================================================
# SECTION 11 — cachetools Demo (with fallback)
# ===========================================================================

def demo_cachetools():
    print("\n" + "=" * 60)
    print("DEMO 11: cachetools (TTLCache, LRUCache, LFUCache)")
    print("=" * 60)

    if not CACHETOOLS_AVAILABLE:
        print("\n    [SKIP] cachetools not installed.")
        print("    Install with: pip install cachetools")
        print("    Using fallback TTLCache for this demo...")

        # Fallback demo
        fallback_cache = _FallbackTTLCache(maxsize=10, ttl=5)
        for i in range(5):
            fallback_cache[f"item:{i}"] = {"id": i, "data": f"value_{i}"}

        hits = sum(1 for i in range(5) if f"item:{i}" in fallback_cache)
        print(f"\n    Fallback TTLCache: {hits}/5 items found (TTL=5s)")
        return

    print("\n--- TTLCache: Time-based expiry ---")
    ttl_cache = TTLCache(maxsize=100, ttl=2)  # 2s TTL for demo
    ttl_cache["session:abc"] = {"user": "Alice", "token": "xyz123"}
    ttl_cache["session:def"] = {"user": "Bob", "token": "abc456"}

    print(f"    Sessions cached: {len(ttl_cache)}")
    print(f"    session:abc exists: {'session:abc' in ttl_cache}")

    print("    Waiting 2.5s for TTL expiry...")
    time.sleep(2.5)
    print(f"    session:abc exists after TTL: {'session:abc' in ttl_cache} (expired!)")

    print("\n--- LRUCache: Least Recently Used eviction ---")
    lru_cache_inst = LRUCache(maxsize=3)  # Sirf 3 items
    for i in range(5):
        lru_cache_inst[f"item:{i}"] = f"value_{i}"
        print(f"    Added item:{i} → cache size: {len(lru_cache_inst)}")

    print(f"    Cache keys after 5 inserts (maxsize=3): {list(lru_cache_inst.keys())}")
    print("    item:0 and item:1 were evicted (LRU)")

    print("\n--- LFUCache: Least Frequently Used eviction ---")
    lfu_cache_inst = LFUCache(maxsize=3)
    lfu_cache_inst["popular"] = "high_freq_item"
    lfu_cache_inst["occasional"] = "med_freq_item"
    lfu_cache_inst["rare"] = "low_freq_item"

    # Access 'popular' many times
    for _ in range(10):
        _ = lfu_cache_inst.get("popular")
    for _ in range(3):
        _ = lfu_cache_inst.get("occasional")

    # Add new item — 'rare' should be evicted (least frequency)
    lfu_cache_inst["new_item"] = "new"
    print(f"    After eviction, remaining keys: {list(lfu_cache_inst.keys())}")
    print("    'rare' evicted because it had lowest access frequency")

    print("\n--- Thread-safe caching with lock ---")
    safe_cache = TTLCache(maxsize=100, ttl=60)
    lock = threading.Lock()

    @ct_cached(cache=safe_cache, lock=lock)
    def get_product_price(product_id: int) -> float:
        time.sleep(0.01)  # DB call
        return product_id * 9.99

    results = []
    threads = [
        threading.Thread(target=lambda: results.append(get_product_price(42)))
        for _ in range(10)
    ]
    for t in threads: t.start()
    for t in threads: t.join()

    print(f"    10 concurrent calls for product:42 → all got: {results[0]:.2f}")
    print(f"    Unique results (should be 1): {len(set(results))}")


# ===========================================================================
# SECTION 12 — Production Redis Reference (for 40 LPA interviews)
# ===========================================================================

REDIS_REFERENCE = """
╔══════════════════════════════════════════════════════════════════╗
║          PRODUCTION REDIS REFERENCE (Interview Notes)           ║
╚══════════════════════════════════════════════════════════════════╝

# 1. Connection Pool (ALWAYS use in production)
import redis

pool = redis.ConnectionPool(
    host='redis.prod.internal',
    port=6379,
    db=0,
    max_connections=50,
    decode_responses=True,
    socket_connect_timeout=2,
    socket_timeout=1,
    retry_on_timeout=True,
    health_check_interval=30,
)
r = redis.Redis(connection_pool=pool)

# 2. Cache-Aside with proper error handling
import json
from contextlib import suppress

def cache_aside_production(key: str, loader_fn, ttl: int = 300):
    # Try cache (don't crash if Redis is down)
    with suppress(redis.RedisError):
        cached = r.get(key)
        if cached:
            return json.loads(cached)

    # DB fallback (always works even if Redis is down)
    value = loader_fn()

    # Try to cache (don't crash if Redis is down)
    with suppress(redis.RedisError):
        if value:
            r.setex(key, ttl, json.dumps(value, default=str))

    return value

# 3. Distributed Lock (Cache Stampede Prevention)
import uuid

def get_with_lock(key: str, compute_fn, ttl: int = 300):
    lock_key = f"lock:{key}"
    lock_val = str(uuid.uuid4())

    cached = r.get(key)
    if cached:
        return json.loads(cached)

    acquired = r.set(lock_key, lock_val, nx=True, ex=5)

    if acquired:
        try:
            value = compute_fn()
            r.setex(key, ttl, json.dumps(value, default=str))
            return value
        finally:
            # Atomic check-and-delete (Lua script)
            lua = "if redis.call('get',KEYS[1])==ARGV[1] then return redis.call('del',KEYS[1]) else return 0 end"
            r.eval(lua, 1, lock_key, lock_val)
    else:
        # Wait for winner
        for _ in range(40):  # 2s max wait
            time.sleep(0.05)
            cached = r.get(key)
            if cached:
                return json.loads(cached)
        return compute_fn()  # Fallback

# 4. Pipeline for batch operations (10x faster)
def batch_get_users(user_ids: list) -> dict:
    pipe = r.pipeline()
    for uid in user_ids:
        pipe.get(f"user:{uid}")
    results = pipe.execute()

    return {uid: (json.loads(val) if val else None)
            for uid, val in zip(user_ids, results)}

# 5. SCAN for safe pattern deletion
def safe_pattern_delete(pattern: str) -> int:
    count = 0
    cursor = 0
    while True:
        cursor, keys = r.scan(cursor, match=pattern, count=100)
        if keys:
            r.delete(*keys)
            count += len(keys)
        if cursor == 0:
            break
    return count

# 6. Key naming convention
# {service}:{resource}:{id}:{attribute?}
# user-svc:user:123                → user profile
# user-svc:user:123:perms          → permissions
# order-svc:order:456              → order data
# session:{session_id}             → session
# rate:{user_id}:{window}          → rate limit counter
# lock:{resource_key}              → distributed lock

# 7. FastAPI async Redis
import aioredis

async def get_redis_client():
    return aioredis.from_url(
        "redis://localhost:6379",
        encoding="utf-8",
        decode_responses=True,
        max_connections=100,
    )
"""


def demo_redis_reference():
    print("\n" + "=" * 60)
    print("DEMO 12: Production Redis Reference")
    print("=" * 60)
    print(REDIS_REFERENCE)


# ===========================================================================
# SECTION 13 — Refresh-Ahead Cache Demo
# ===========================================================================

class RefreshAheadCache:
    """
    Refresh-Ahead: TTL expire hone se pehle background mein refresh.
    User ko kabhi cache miss nahi milti.
    News feeds, leaderboards ke liye ideal.
    """

    def __init__(self, loader_fn: Callable, ttl: int = 60,
                 refresh_ratio: float = 0.75):
        self._loader = loader_fn
        self._ttl = ttl
        self._refresh_threshold = ttl * refresh_ratio
        self._store: Dict[str, Tuple[Any, float]] = {}  # key → (value, set_time)
        self._lock = threading.Lock()
        self._refreshing: set = set()
        self._refresh_count = 0

    def get(self, key: str, *args, **kwargs) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)

        if entry is None:
            # Complete miss — synchronous load
            return self._load_and_store(key, *args, **kwargs)

        value, set_time = entry
        age = time.time() - set_time

        # Expired — synchronous reload
        if age > self._ttl:
            return self._load_and_store(key, *args, **kwargs)

        # Refresh-ahead threshold — background refresh, return current value
        if age > self._refresh_threshold and key not in self._refreshing:
            print(f"    [Refresh-Ahead] Triggering background refresh for {key!r} (age={age:.1f}s)")
            self._async_refresh(key, *args, **kwargs)

        return value

    def _load_and_store(self, key: str, *args, **kwargs) -> Any:
        value = self._loader(*args, **kwargs)
        with self._lock:
            self._store[key] = (value, time.time())
        return value

    def _async_refresh(self, key: str, *args, **kwargs) -> None:
        self._refreshing.add(key)

        def refresh_task():
            try:
                new_value = self._loader(*args, **kwargs)
                with self._lock:
                    self._store[key] = (new_value, time.time())
                self._refresh_count += 1
                print(f"    [Refresh-Ahead] {key!r} refreshed (total refreshes: {self._refresh_count})")
            finally:
                self._refreshing.discard(key)

        threading.Thread(target=refresh_task, daemon=True, name=f"Refresh-{key}").start()


def demo_refresh_ahead():
    print("\n" + "=" * 60)
    print("DEMO 13: Refresh-Ahead Cache")
    print("=" * 60)

    fetch_count = [0]

    def fetch_leaderboard():
        fetch_count[0] += 1
        time.sleep(0.05)
        return {
            "top_players": [f"Player_{i}" for i in range(1, 6)],
            "fetched_at": time.strftime("%H:%M:%S"),
            "fetch_num": fetch_count[0],
        }

    ra_cache = RefreshAheadCache(
        loader_fn=fetch_leaderboard,
        ttl=2.0,           # 2s TTL for demo
        refresh_ratio=0.5, # Refresh at 50% (1s)
    )

    print("\n--- Simulating requests over 3 seconds ---")
    print("    (TTL=2s, refresh threshold=1s — background refresh at 1s)")
    key = "leaderboard:global"

    for i in range(6):
        result = ra_cache.get(key)
        print(f"    t={i*0.5:.1f}s: fetch#{result['fetch_num']} at {result['fetched_at']!r}")
        time.sleep(0.5)

    print(f"\n    Total background refreshes: {ra_cache._refresh_count}")
    print("    User never experienced a cache miss despite TTL expiry!")


# ===========================================================================
# MAIN — Run all demos
# ===========================================================================

DEMOS = [
    ("Cache-Aside",              demo_cache_aside),
    ("Read-Through",             demo_read_through),
    ("Write-Through",            demo_write_through),
    ("Write-Behind",             demo_write_behind),
    ("Stampede Prevention",      demo_stampede_prevention),
    ("Multi-Layer Cache",        demo_multi_layer_cache),
    ("Cache Decorator",          demo_cache_decorator),
    ("Version Invalidation",     demo_versioned_invalidation),
    ("Hit Rate + Warm-Up",       demo_cache_warmup_and_monitoring),
    ("functools.lru_cache",      demo_lru_cache),
    ("cachetools",               demo_cachetools),
    ("Redis Reference",          demo_redis_reference),
    ("Refresh-Ahead",            demo_refresh_ahead),
]


def main():
    args = sys.argv[1:]

    if args and args[0] == "list":
        print("\nAvailable demos:")
        for i, (name, _) in enumerate(DEMOS, 1):
            print(f"  {i:2d}. {name}")
        return

    print("=" * 60)
    print("  Caching Patterns — Python Backend Developer Prep")
    print("  Target: 40 LPA | Hinglish Theory + Production Code")
    print("=" * 60)
    print(f"\n  Running {len(DEMOS)} demos...\n")
    print(f"  Python {sys.version.split()[0]}")
    print(f"  cachetools: {'available' if CACHETOOLS_AVAILABLE else 'not installed (fallback active)'}")

    for name, demo_fn in DEMOS:
        try:
            demo_fn()
        except KeyboardInterrupt:
            print("\n\n[Interrupted by user]")
            break
        except Exception as e:
            print(f"\n  [ERROR in {name}]: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print("  All demos complete!")
    print("  Theory file: theory/01_caching_patterns.md")
    print("=" * 60)


if __name__ == "__main__":
    main()
