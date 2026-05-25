"""
07 — Performance Profiling & Optimization
==========================================
Python Backend Developer Interview Prep | Target: 40 LPA

Usage:
    python 07_performance_profiling.py          # runs all demos
    python 07_performance_profiling.py demo     # runs quick demo (subset)
    python 07_performance_profiling.py all      # runs everything

Sections:
    1. timeit Benchmarks
    2. cProfile + pstats
    3. tracemalloc Memory Tracking
    4. Memory Leak Detection
    5. lru_cache Benchmarks
    6. __slots__ vs __dict__
    7. Generator vs List Memory
    8. FastAPI Timing Middleware (pattern demo, no server needed)
    9. Reusable @profile Decorator

All stdlib — no external installs required.
"""

import sys
import timeit
import cProfile
import pstats
import io
import tracemalloc
import time
import random
import functools
import gc
from functools import lru_cache

DIVIDER = "=" * 65

# ──────────────────────────────────────────────────────────────────
# SECTION 1 — timeit Benchmarks
# ──────────────────────────────────────────────────────────────────

def benchmark_string_concat():
    """
    String concatenation: + operator vs join() vs list+join
    Demonstrates O(n²) vs O(n) behaviour.
    """
    print(f"\n{DIVIDER}")
    print("SECTION 1a — String Concatenation Benchmark")
    print(DIVIDER)

    def concat_plus(n):
        """
        + concatenation — O(n²)
        Har iteration pe naya string object banata hai aur pura string copy karta hai.
        n=1000 pe: 1+2+3+...+1000 = 500500 characters copied
        """
        s = ""
        for i in range(n):
            s += str(i)
        return s

    def concat_join(n):
        """
        join() with generator — O(n)
        Generator lazily values produce karta hai,
        join() pehle total length calculate karta hai, ek hi baar allocate karta hai.
        """
        return "".join(str(i) for i in range(n))

    def concat_list_join(n):
        """
        list.append() + join() — O(n)
        Explicit list banao, phir join. concat_join ke similar,
        lekin list comprehension overhead slightly different hai.
        """
        parts = []
        for i in range(n):
            parts.append(str(i))
        return "".join(parts)

    n = 1000
    runs = 1000

    t_plus  = timeit.timeit(lambda: concat_plus(n),       number=runs)
    t_join  = timeit.timeit(lambda: concat_join(n),       number=runs)
    t_list  = timeit.timeit(lambda: concat_list_join(n),  number=runs)

    print(f"String concat n={n}, {runs} runs:")
    print(f"  + operator:       {t_plus:.3f}s  ← O(n²), creates new string each iter")
    print(f"  join(generator):  {t_join:.3f}s  ← O(n), single allocation")
    print(f"  list+join():      {t_list:.3f}s  ← O(n), explicit list")

    if t_join > 0:
        print(f"\n  join() is {t_plus/t_join:.1f}x faster than + operator")

    # Verify correctness
    assert concat_plus(50) == concat_join(50) == concat_list_join(50), \
        "Results must be identical!"
    print("  Correctness check: PASSED")


def benchmark_membership_test():
    """
    Membership testing: list O(n) vs set O(1) vs dict O(1)
    Critical for any lookup-heavy code (blocklists, caches, id sets).
    """
    print(f"\n{DIVIDER}")
    print("SECTION 1b — Membership Test: list vs set vs dict")
    print(DIVIDER)

    size = 10_000
    data_list = list(range(size))
    data_set  = set(range(size))
    data_dict = {i: True for i in range(size)}

    # Mix of hits and misses (50% outside range)
    targets = [random.randint(0, size * 2) for _ in range(1000)]
    runs = 100

    t_list = timeit.timeit(lambda: [x in data_list for x in targets], number=runs)
    t_set  = timeit.timeit(lambda: [x in data_set  for x in targets], number=runs)
    t_dict = timeit.timeit(lambda: [x in data_dict for x in targets], number=runs)

    print(f"Membership test: {size:,} elements, 1000 lookups × {runs} runs")
    print(f"  list (O(n)):  {t_list:.3f}s")
    print(f"  set  (O(1)):  {t_set:.3f}s")
    print(f"  dict (O(1)):  {t_dict:.3f}s")
    if t_set > 0:
        print(f"\n  set is {t_list/t_set:.0f}x faster than list")
    print(
        "\n  Rule: static lookup table → always use set/dict, never list."
        "\n  Akele ek API mein 10k lookups/sec hote hain → at scale ye HUGE difference hai."
    )


def benchmark_comprehensions():
    """
    List comprehension vs map() vs filtered comprehension.
    All are roughly similar, but map with lambda has overhead.
    """
    print(f"\n{DIVIDER}")
    print("SECTION 1c — List Comprehension vs map() vs Filtered")
    print(DIVIDER)

    n = 10_000
    runs = 1000

    # list comprehension
    t_comp = timeit.timeit(lambda: [x * x for x in range(n)], number=runs)

    # map with lambda (lambda call has overhead)
    t_map_lambda = timeit.timeit(
        lambda: list(map(lambda x: x * x, range(n))), number=runs
    )

    # map with built-in (no lambda overhead)
    t_map_builtin = timeit.timeit(
        lambda: list(map(pow, range(n), [2] * n)), number=runs  # pow(x, 2) for each x
    )

    # filtered comprehension
    t_filtered = timeit.timeit(
        lambda: [x * x for x in range(n) if x % 2 == 0], number=runs
    )

    print(f"List operations n={n:,}, {runs} runs:")
    print(f"  [x*x for x in range(n)]:       {t_comp:.3f}s")
    print(f"  list(map(lambda x:x*x, ...)):   {t_map_lambda:.3f}s  ← lambda overhead")
    print(f"  [x*x for x in range(n) if ...]: {t_filtered:.3f}s  ← half elements")
    print("\n  Key insight: list comprehension usually fastest due to optimized bytecode.")
    print("  map() with built-in (no lambda) can match or beat comprehension.")


# ──────────────────────────────────────────────────────────────────
# SECTION 2 — cProfile + pstats
# ──────────────────────────────────────────────────────────────────

def profile_fibonacci():
    """
    cProfile se recursive vs memoized fibonacci compare karo.
    Shows how to use cProfile.Profile() as context manager alternative
    and pstats.Stats for filtering/sorting.
    """
    print(f"\n{DIVIDER}")
    print("SECTION 2 — cProfile: Recursive vs Memoized Fibonacci")
    print(DIVIDER)

    def fibonacci_recursive(n):
        """Classic recursive — exponential calls O(2^n)."""
        if n < 2:
            return n
        return fibonacci_recursive(n - 1) + fibonacci_recursive(n - 2)

    def _fib_memo(n, memo):
        if n in memo:
            return memo[n]
        if n < 2:
            return n
        memo[n] = _fib_memo(n - 1, memo) + _fib_memo(n - 2, memo)
        return memo[n]

    def fibonacci_memoized(n):
        """Memoized — O(n) unique calls."""
        return _fib_memo(n, {})

    # --- Profile recursive fibonacci(25) ---
    pr = cProfile.Profile()
    pr.enable()
    result_recursive = fibonacci_recursive(25)
    pr.disable()

    stream = io.StringIO()
    ps = pstats.Stats(pr, stream=stream)
    ps.strip_dirs()
    ps.sort_stats("cumulative")
    ps.print_stats(5)

    print("cProfile output — fibonacci_recursive(25), top 5 by cumtime:")
    print(stream.getvalue())

    # --- Profile memoized fibonacci(25) ---
    pr2 = cProfile.Profile()
    pr2.enable()
    result_memo = fibonacci_memoized(25)
    pr2.disable()

    stream2 = io.StringIO()
    ps2 = pstats.Stats(pr2, stream=stream2)
    ps2.strip_dirs()
    ps2.sort_stats("cumulative")
    ps2.print_stats(5)

    print("cProfile output — fibonacci_memoized(25), top 5 by cumtime:")
    print(stream2.getvalue())

    # --- timeit comparison ---
    t_recursive = timeit.timeit(lambda: fibonacci_recursive(25), number=10)
    t_memoized  = timeit.timeit(lambda: fibonacci_memoized(25),  number=10)

    print(f"Both return: {result_recursive} (recursive) == {result_memo} (memo): "
          f"{'MATCH' if result_recursive == result_memo else 'MISMATCH!'}")
    print(f"\ntimeit — fibonacci(25), 10 runs:")
    print(f"  Recursive: {t_recursive:.4f}s ({t_recursive/10*1000:.1f}ms per call)")
    print(f"  Memoized:  {t_memoized:.6f}s ({t_memoized/10*1000:.3f}ms per call)")
    if t_memoized > 0:
        print(f"  Speedup:   {t_recursive/t_memoized:.0f}x")
    print("\n  cProfile ncalls column: recursive=242785, memoized=51 calls for n=25")
    print("  This is the power of memoization — same answer, exponentially fewer calls.")


# ──────────────────────────────────────────────────────────────────
# SECTION 3 — tracemalloc Memory Tracking
# ──────────────────────────────────────────────────────────────────

def demo_tracemalloc():
    """
    tracemalloc: built-in memory tracker, no external install.
    Demonstrates:
      - list vs generator memory
      - top allocation sites
    """
    print(f"\n{DIVIDER}")
    print("SECTION 3a — tracemalloc: List vs Generator Memory")
    print(DIVIDER)

    # ── List comprehension ──────────────────────────────────────
    gc.collect()
    tracemalloc.start()
    data_list = [x * x for x in range(1_000_000)]
    current_list, peak_list = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    del data_list
    gc.collect()

    # ── Generator expression ────────────────────────────────────
    tracemalloc.start()
    data_gen = (x * x for x in range(1_000_000))
    _ = next(data_gen)  # materialise one value so generator is "active"
    current_gen, peak_gen = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print(f"n = 1,000,000 squared values:")
    print(f"  List comprehension peak:  {peak_list / 1024 / 1024:.2f} MB")
    print(f"  Generator peak:           {peak_gen  / 1024:.2f} KB")
    if peak_gen > 0:
        print(f"  Memory ratio:             {peak_list / peak_gen:.0f}x")

    print("\n  Generator sirf ek value at a time hold karta hai.")
    print("  Same computation, ~8000x less memory.")

    # ── Top allocation sites ────────────────────────────────────
    print(f"\n{DIVIDER}")
    print("SECTION 3b — tracemalloc: Top Allocation Sites")
    print(DIVIDER)

    gc.collect()
    tracemalloc.start()

    # Allocate various structures
    big_dict  = {str(i): [j * j for j in range(50)] for i in range(500)}
    small_list = [i for i in range(50_000)]
    nested    = [[i + j for j in range(20)] for i in range(200)]

    snapshot = tracemalloc.take_snapshot()
    tracemalloc.stop()
    del big_dict, small_list, nested

    stats = snapshot.statistics("lineno")
    print("Top 5 memory allocations (by size):")
    for i, stat in enumerate(stats[:5], 1):
        size_kb = stat.size / 1024
        location = stat.traceback.format()[0] if stat.traceback else "unknown"
        print(f"  {i}. {size_kb:7.1f} KB — {location}")


def demo_snapshot_compare():
    """
    Two snapshots compare karo to find what grew.
    Useful for finding accumulations in long-running services.
    """
    print(f"\n{DIVIDER}")
    print("SECTION 3c — tracemalloc: Snapshot Diff (Before/After)")
    print(DIVIDER)

    gc.collect()
    tracemalloc.start()

    snap1 = tracemalloc.take_snapshot()  # baseline

    # Allocate new data
    new_data = {f"key_{i}": list(range(100)) for i in range(1000)}

    snap2 = tracemalloc.take_snapshot()  # after allocation
    tracemalloc.stop()

    top_diff = snap2.compare_to(snap1, "lineno")
    print("Top 5 lines where memory GREW between snapshot 1 and 2:")
    for stat in top_diff[:5]:
        if stat.size_diff > 0:
            print(f"  +{stat.size_diff / 1024:.1f} KB — {stat.traceback.format()[0]}")

    del new_data


# ──────────────────────────────────────────────────────────────────
# SECTION 4 — Memory Leak Detection
# ──────────────────────────────────────────────────────────────────

def demo_memory_leak_detection():
    """
    Module-level list accumulation → classic leak pattern.
    Repeated calls pe memory monotonically grow karti hai.
    """
    print(f"\n{DIVIDER}")
    print("SECTION 4 — Memory Leak Detection")
    print(DIVIDER)

    # ── Leaky function ──────────────────────────────────────────
    _leaked_cache = []  # module-level accumulator — intentional "bug"

    def leaky_function(n: int) -> int:
        """
        Bug: har call pe _leaked_cache mein data append hota hai.
        Kabhi clear nahi hota → memory monotonically grow karti hai.
        Real-world leak: event listeners, global registries, etc.
        """
        _leaked_cache.extend(i ** 2 for i in range(n))
        return sum(_leaked_cache[-n:])

    def clean_function(n: int) -> int:
        """
        Correct: local scope mein data banao, function exit pe GC collect karta hai.
        """
        data = [i ** 2 for i in range(n)]
        return sum(data)

    # ── Track memory over 10 calls ──────────────────────────────
    print(f"{'Call':>5}  {'Leaky (KB)':>12}  {'Clean (KB)':>12}  {'Leaked Change':>14}")
    print("─" * 55)

    gc.collect()
    tracemalloc.start()

    prev_leaky = 0
    for call_num in range(1, 11):
        leaky_function(500)
        clean_function(500)
        gc.collect()
        current, _ = tracemalloc.get_traced_memory()

        current_kb = current / 1024
        change = current_kb - prev_leaky
        trend = "↑ grows!" if change > 1 else "stable"
        print(f"  {call_num:>3}   {current_kb:>10.1f}   {'(local)':>12}   {trend}")
        prev_leaky = current_kb

    tracemalloc.stop()
    _leaked_cache.clear()  # cleanup

    print("\n  Leaky: memory grows each call (data accumulates in global list)")
    print("  Clean: memory stable (local data freed after each call)")
    print("\n  Detection strategy:")
    print("    1. tracemalloc.take_snapshot() before + after N calls")
    print("    2. snapshot.compare_to() for diff")
    print("    3. Lines with large positive size_diff are suspects")


# ──────────────────────────────────────────────────────────────────
# SECTION 5 — lru_cache Benchmarks
# ──────────────────────────────────────────────────────────────────

def demo_lru_cache():
    """
    lru_cache memoization: simulate repeated DB lookups.
    Shows cache hit/miss ratio and real speedup.
    """
    print(f"\n{DIVIDER}")
    print("SECTION 5 — lru_cache: Memoized Lookup Benchmark")
    print(DIVIDER)

    # ── Without cache ───────────────────────────────────────────
    def expensive_db_lookup(user_id: int) -> dict:
        """Simulate a slow DB call (~0.5ms)."""
        time.sleep(0.0005)
        return {"id": user_id, "name": f"User_{user_id}", "email": f"u{user_id}@co.com"}

    # ── With cache ──────────────────────────────────────────────
    @lru_cache(maxsize=128)
    def cached_db_lookup(user_id: int) -> dict:
        """Same function, but results cached (up to 128 unique user_ids)."""
        time.sleep(0.0005)
        return {"id": user_id, "name": f"User_{user_id}", "email": f"u{user_id}@co.com"}

    # Simulate 200 requests for 15 unique users
    # (realistic: hot users accessed frequently)
    unique_users = 15
    total_requests = 200
    user_ids = [random.randint(1, unique_users) for _ in range(total_requests)]

    # ── Without cache ───────────────────────────────────────────
    t_start = time.perf_counter()
    for uid in user_ids:
        expensive_db_lookup(uid)
    t_no_cache = time.perf_counter() - t_start

    # ── With cache ──────────────────────────────────────────────
    t_start = time.perf_counter()
    for uid in user_ids:
        cached_db_lookup(uid)
    t_cached = time.perf_counter() - t_start

    info = cached_db_lookup.cache_info()
    expected_misses = unique_users  # one miss per unique user
    hit_rate = info.hits / (info.hits + info.misses) * 100

    print(f"Scenario: {total_requests} requests, {unique_users} unique users")
    print(f"\n  Without lru_cache: {t_no_cache:.3f}s ({total_requests} DB calls)")
    print(f"  With lru_cache:    {t_cached:.3f}s  ({info.misses} DB calls, {info.hits} hits)")
    print(f"\n  Hit rate:  {hit_rate:.1f}%")
    if t_cached > 0:
        print(f"  Speedup:   {t_no_cache / t_cached:.1f}x")
    print(f"\n  cache_info(): {info}")

    # ── Demonstrate cache_clear ─────────────────────────────────
    cached_db_lookup.cache_clear()
    print(f"\n  After cache_clear(): {cached_db_lookup.cache_info()}")

    # ── LRU eviction demo ───────────────────────────────────────
    @lru_cache(maxsize=3)  # only 3 slots
    def tiny_cache(n: int) -> int:
        return n * n

    for i in [1, 2, 3]:
        tiny_cache(i)
    info_full = tiny_cache.cache_info()
    print(f"\n  LRU eviction demo (maxsize=3):")
    print(f"  After caching 1,2,3: currsize={info_full.currsize}")

    tiny_cache(4)  # evicts 1 (least recently used)
    tiny_cache(1)  # miss! 1 was evicted
    info_evict = tiny_cache.cache_info()
    print(f"  After add 4, access 1: misses={info_evict.misses} (1 was evicted by LRU)")


# ──────────────────────────────────────────────────────────────────
# SECTION 6 — __slots__ vs __dict__ Benchmark
# ──────────────────────────────────────────────────────────────────

class _WithDict:
    """Default Python class — instances use __dict__."""
    def __init__(self, x: float, y: float, z: float, name: str):
        self.x    = x
        self.y    = y
        self.z    = z
        self.name = name


class _WithSlots:
    """
    __slots__ class — no per-instance __dict__.
    Memory layout: fixed slots, no hash table overhead.
    """
    __slots__ = ("x", "y", "z", "name")

    def __init__(self, x: float, y: float, z: float, name: str):
        self.x    = x
        self.y    = y
        self.z    = z
        self.name = name


def benchmark_slots(n: int = 100_000):
    """
    Compare __dict__ vs __slots__ for:
      - Memory (tracemalloc)
      - Per-object sys.getsizeof()
      - Attribute access speed (timeit)
    """
    import sys

    print(f"\n{DIVIDER}")
    print(f"SECTION 6 — __slots__ vs __dict__ ({n:,} objects)")
    print(DIVIDER)

    # ── Memory ──────────────────────────────────────────────────
    gc.collect()
    tracemalloc.start()
    dict_objs = [_WithDict(i * 0.1, i * 0.2, i * 0.3, f"obj{i}") for i in range(n)]
    _, peak_dict = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    gc.collect()
    tracemalloc.start()
    slot_objs = [_WithSlots(i * 0.1, i * 0.2, i * 0.3, f"obj{i}") for i in range(n)]
    _, peak_slots = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # ── Per-object size ─────────────────────────────────────────
    dict_obj_size  = sys.getsizeof(dict_objs[0]) + sys.getsizeof(dict_objs[0].__dict__)
    slot_obj_size  = sys.getsizeof(slot_objs[0])

    # ── Attribute access speed ───────────────────────────────────
    d_obj = dict_objs[0]
    s_obj = slot_objs[0]
    t_dict_access = timeit.timeit(lambda: d_obj.x + d_obj.y + d_obj.z, number=1_000_000)
    t_slot_access = timeit.timeit(lambda: s_obj.x + s_obj.y + s_obj.z, number=1_000_000)

    mem_saved_pct = (peak_dict - peak_slots) / peak_dict * 100 if peak_dict > 0 else 0

    print(f"Memory (peak tracemalloc):")
    print(f"  __dict__ class:  {peak_dict  / 1024 / 1024:.2f} MB  | per-obj: {dict_obj_size}B")
    print(f"  __slots__ class: {peak_slots / 1024 / 1024:.2f} MB  | per-obj: {slot_obj_size}B")
    print(f"  Memory saved:    {mem_saved_pct:.1f}%")

    print(f"\nAttribute access (1M reads of x+y+z):")
    print(f"  __dict__:  {t_dict_access:.3f}s")
    print(f"  __slots__: {t_slot_access:.3f}s")
    if t_slot_access > 0:
        print(f"  Speedup:   {t_dict_access / t_slot_access:.2f}x")

    print("\n  When to use __slots__:")
    print("    - Millions of instances (graph nodes, game entities, point clouds)")
    print("    - Attributes are fixed at design time")
    print("  When NOT to use:")
    print("    - Dynamic attribute assignment chahiye")
    print("    - Complex multiple inheritance")

    # Cleanup
    del dict_objs, slot_objs
    gc.collect()


# ──────────────────────────────────────────────────────────────────
# SECTION 7 — Generator vs List Memory
# ──────────────────────────────────────────────────────────────────

def demo_generator_vs_list():
    """
    Generator expression vs list comprehension for large datasets.
    Same computation, dramatically different peak memory.
    """
    print(f"\n{DIVIDER}")
    print("SECTION 7 — Generator vs List: Memory & Speed")
    print(DIVIDER)

    n = 5_000_000  # 5M integers

    # ── List — eager ─────────────────────────────────────────────
    gc.collect()
    tracemalloc.start()
    t0 = time.perf_counter()
    data_list = [i * 2 for i in range(n)]
    total_list = sum(data_list)
    t_list = time.perf_counter() - t0
    _, peak_list = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    del data_list
    gc.collect()

    # ── Generator — lazy ─────────────────────────────────────────
    tracemalloc.start()
    t0 = time.perf_counter()
    total_gen = sum(i * 2 for i in range(n))
    t_gen = time.perf_counter() - t0
    _, peak_gen = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print(f"n = {n:,} doubled integers, sum computed")
    print(f"\n  List comprehension:")
    print(f"    Peak memory: {peak_list / 1024 / 1024:.2f} MB")
    print(f"    Time:        {t_list:.3f}s")
    print(f"\n  Generator expression:")
    print(f"    Peak memory: {peak_gen / 1024:.2f} KB")
    print(f"    Time:        {t_gen:.3f}s")
    if peak_gen > 0:
        print(f"\n  Memory ratio: {peak_list / peak_gen:.0f}x (list uses more)")

    print(f"\n  Same result? {total_list == total_gen} (both = {total_gen:,})")

    # ── When list is BETTER ──────────────────────────────────────
    print("\n  When to prefer LIST over generator:")
    print("    1. Multiple iterations needed (generator exhausted after 1 pass)")
    print("    2. Random access needed  (gen[i] not supported)")
    print("    3. len() needed          (generators have no __len__)")
    print("    4. Data needs to be shared/cached")
    print("\n  When to prefer GENERATOR:")
    print("    1. Single-pass processing (pipelines)")
    print("    2. Large datasets that don't fit in RAM")
    print("    3. Infinite sequences (e.g., itertools.count())")


# ──────────────────────────────────────────────────────────────────
# SECTION 8 — FastAPI Timing Middleware (Pattern Demo)
# ──────────────────────────────────────────────────────────────────

def demo_fastapi_middleware_pattern():
    """
    FastAPI middleware pattern for request timing.
    No server needed — shows the pattern and explains it.
    """
    print(f"\n{DIVIDER}")
    print("SECTION 8 — FastAPI Request Timing Middleware (Pattern)")
    print(DIVIDER)

    MIDDLEWARE_CODE = '''
from fastapi import FastAPI, Request
import time
import logging

logger = logging.getLogger(__name__)

app = FastAPI()

@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    """
    Har HTTP request ke liye:
    1. Start time record karo
    2. Request process karo
    3. Duration calculate karo
    4. Response header mein add karo
    5. Slow requests log karo
    """
    start = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception as exc:
        logger.error(f"Request error: {exc}", exc_info=True)
        raise

    duration_ms = (time.perf_counter() - start) * 1000

    # Client ko timing visible karein (debugging ke liye helpful)
    response.headers["X-Process-Time"] = f"{duration_ms:.2f}ms"

    # Structured logging (Datadog/ELK easily parse kar sake)
    log_data = {
        "method":    request.method,
        "path":      request.url.path,
        "status":    response.status_code,
        "time_ms":   round(duration_ms, 2),
        "client_ip": request.client.host if request.client else "unknown",
    }

    if duration_ms > 500:
        logger.warning("SLOW_REQUEST", extra=log_data)
    else:
        logger.info("REQUEST", extra=log_data)

    return response


# Alternative: pyinstrument for endpoint-level profiling in dev
# @app.get("/debug-profile")
# async def debug_endpoint():
#     from pyinstrument import Profiler
#     with Profiler() as profiler:
#         result = await expensive_function()
#     print(profiler.output_text(unicode=True, color=True))
#     return result
'''
    print(MIDDLEWARE_CODE)

    # ── Simulate the timing logic without FastAPI ────────────────
    print("  Simulating timing logic (no FastAPI needed):")

    def simulate_request(duration_s: float, path: str):
        start = time.perf_counter()
        time.sleep(duration_s)  # simulate work
        elapsed_ms = (time.perf_counter() - start) * 1000
        status = "SLOW" if elapsed_ms > 100 else "OK"
        print(f"    {path:<30} {elapsed_ms:.1f}ms  [{status}]")

    for path, dur in [("/health", 0.005), ("/api/users", 0.080), ("/api/report", 0.250)]:
        simulate_request(dur, path)


# ──────────────────────────────────────────────────────────────────
# SECTION 9 — Reusable @profile Decorator
# ──────────────────────────────────────────────────────────────────

def profile(sort_by: str = "cumulative", lines: int = 10):
    """
    Reusable cProfile decorator.
    Production code mein mat lagaao — dev/staging ke liye hai.

    Usage:
        @profile(sort_by='cumulative', lines=5)
        def my_slow_function():
            ...
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            pr = cProfile.Profile()
            pr.enable()
            t_start = time.perf_counter()

            try:
                result = fn(*args, **kwargs)
            finally:
                elapsed_ms = (time.perf_counter() - t_start) * 1000
                pr.disable()

            stream = io.StringIO()
            pstats.Stats(pr, stream=stream).strip_dirs().sort_stats(sort_by).print_stats(lines)

            print(f"\n[profile] {fn.__name__}() → {elapsed_ms:.2f}ms total")
            print(stream.getvalue())
            return result

        return wrapper
    return decorator


# ── Example function using the decorator ────────────────────────

@profile(sort_by="cumulative", lines=8)
def _profiled_example():
    """
    Intentionally mixes fast and slow operations
    so cProfile output is interesting.
    """
    # Fast: list comprehension
    squares = [i * i for i in range(10_000)]

    # Slow: nested generator with sum (many Python-level ops)
    total = sum(
        sum(j for j in range(i % 20))
        for i in range(5_000)
    )

    # Medium: string joins
    words = ["word"] * 500
    joined = " ".join(words)

    return total + len(joined) + len(squares)


def demo_profile_decorator():
    print(f"\n{DIVIDER}")
    print("SECTION 9 — Reusable @profile Decorator")
    print(DIVIDER)
    print("Running @profile decorated function...\n")
    result = _profiled_example()
    print(f"Function returned: {result}")


# ──────────────────────────────────────────────────────────────────
# SECTION 10 — Optimization Patterns Summary
# ──────────────────────────────────────────────────────────────────

def demo_optimization_patterns_summary():
    """
    Rapid-fire demonstration of common optimization patterns.
    Each pattern: BAD version timed, GOOD version timed, ratio printed.
    """
    print(f"\n{DIVIDER}")
    print("SECTION 10 — Common Optimization Patterns Summary")
    print(DIVIDER)

    results = []

    # ── Pattern A: Global vs Local Variable Lookup ───────────────
    import math

    def _global_lookup(n):
        result = 0.0
        for i in range(1, n + 1):
            result += math.sqrt(i)   # global 'math' + attribute 'sqrt'
        return result

    def _local_lookup(n):
        _sqrt = math.sqrt             # local reference
        result = 0.0
        for i in range(1, n + 1):
            result += _sqrt(i)        # direct local
        return result

    n = 50_000
    t_global = timeit.timeit(lambda: _global_lookup(n), number=50)
    t_local  = timeit.timeit(lambda: _local_lookup(n),  number=50)
    results.append(("Global vs local var lookup", t_global, t_local))

    # ── Pattern B: Set vs List for Membership ───────────────────
    banned_list = list(range(1000))
    banned_set  = set(range(1000))
    checks = [random.randint(0, 1500) for _ in range(500)]

    t_list_check = timeit.timeit(lambda: [x in banned_list for x in checks], number=500)
    t_set_check  = timeit.timeit(lambda: [x in banned_set  for x in checks], number=500)
    results.append(("Set vs list membership (1k elements, 500 checks)", t_list_check, t_set_check))

    # ── Pattern C: Avoiding repeated attribute lookup in loop ────
    class _Container:
        def __init__(self):
            self.items = list(range(10_000))

    c = _Container()

    def _repeated_attr(container):
        total = 0
        for i in range(len(container.items)):   # container.items looked up each iter
            total += container.items[i]
        return total

    def _cached_attr(container):
        items = container.items                   # single lookup, cached
        total = 0
        for i in range(len(items)):
            total += items[i]
        return total

    t_repeated = timeit.timeit(lambda: _repeated_attr(c), number=500)
    t_cached   = timeit.timeit(lambda: _cached_attr(c),   number=500)
    results.append(("Attribute lookup in loop vs cached", t_repeated, t_cached))

    # ── Pattern D: sum() built-in vs manual loop ─────────────────
    data = list(range(100_000))

    def _manual_sum(lst):
        total = 0
        for x in lst:
            total += x
        return total

    t_manual = timeit.timeit(lambda: _manual_sum(data), number=200)
    t_builtin = timeit.timeit(lambda: sum(data),        number=200)
    results.append(("Built-in sum() vs manual loop", t_manual, t_builtin))

    # ── Print results ────────────────────────────────────────────
    print(f"{'Pattern':<45}  {'Slow':>8}  {'Fast':>8}  {'Speedup':>8}")
    print("─" * 77)
    for name, slow, fast in results:
        speedup = slow / fast if fast > 0 else float("inf")
        marker = " ←" if speedup > 2 else ""
        print(f"  {name:<43}  {slow:>8.3f}  {fast:>8.3f}  {speedup:>7.1f}x{marker}")

    print("\n  All times in seconds for the stated number of runs.")
    print("  Speedup > 2x marked with ←")


# ──────────────────────────────────────────────────────────────────
# SECTION 11 — Interview Q&A Quick Recaps
# ──────────────────────────────────────────────────────────────────

def print_interview_qa():
    print(f"\n{DIVIDER}")
    print("SECTION 11 — Interview Q&A Quick Recaps")
    print(DIVIDER)

    qas = [
        (
            "Q: Profiling vs Benchmarking difference?",
            "Benchmarking = kitna fast hai (absolute time/throughput).\n"
            "  Profiling = kahan time ja raha hai (relative breakdown).\n"
            "  Flow: profile → bottleneck → benchmark baseline → optimize → benchmark verify.",
        ),
        (
            "Q: cProfile tottime vs cumtime?",
            "tottime = function ka sirf apna time (sub-calls minus).\n"
            "  cumtime = function + sab sub-calls ka total time.\n"
            "  High tottime → function khud slow. High cumtime → slow child call.",
        ),
        (
            "Q: Production pe py-spy kab use karein?",
            "jab: code change possible nahi, live process debug karna hai, overhead concern hai.\n"
            "  py-spy attach --pid XYZ  (no deploy, no restart, ~1% overhead).",
        ),
        (
            "Q: Sampling vs deterministic profiler internals?",
            "Deterministic (cProfile): sys.setprofile() → har call/return pe callback → exact.\n"
            "  Sampling (py-spy): every N ms stack snapshot → approximate → low overhead.",
        ),
        (
            "Q: Memory leak kaise detect karein?",
            "tracemalloc.take_snapshot() → repeated calls → snapshot.compare_to() → diff dekho.\n"
            "  Monotonically growing allocations = leak suspect.",
        ),
        (
            "Q: String concatenation O(n²) kyun? Fix?",
            "'+=' har step pe naya string + pura copy → total copies = n(n+1)/2 = O(n²).\n"
            "  Fix: ''.join(parts)  ← single allocation, O(n) copies.",
        ),
        (
            "Q: Set vs list membership at scale?",
            "set O(1) hash lookup, list O(n) linear scan.\n"
            "  1M lookups on 10k element set: ~100ms. List: ~50s. 500x difference.",
        ),
        (
            "Q: Generator vs list memory?",
            "List: sab values memory mein. Generator: sirf current frame (~112 bytes).\n"
            "  1M ints: list ~8MB, generator ~112B. 80,000x less memory.",
        ),
        (
            "Q: lru_cache internals?",
            "Internally: OrderedDict {args_tuple: result}. maxsize → LRU eviction.\n"
            "  Thread-safe in CPython. Arguments must be hashable. cache_info() for stats.",
        ),
        (
            "Q: cProfile production pe kyun nahi chalate?",
            "30-50% CPU overhead (sys.setprofile() per-call hook).\n"
            "  Production pe: py-spy (~1%) ya Prometheus counters use karo.",
        ),
    ]

    for i, (q, a) in enumerate(qas, 1):
        print(f"\n  {i:02d}. {q}")
        print(f"      {a}")


# ──────────────────────────────────────────────────────────────────
# RUNNER
# ──────────────────────────────────────────────────────────────────

DEMO_SECTIONS = [
    ("String Concat Benchmark",        benchmark_string_concat),
    ("Membership Test Benchmark",      benchmark_membership_test),
    ("Comprehension Benchmark",        benchmark_comprehensions),
    ("cProfile Fibonacci",             profile_fibonacci),
    ("tracemalloc Basic",              demo_tracemalloc),
    ("tracemalloc Snapshot Diff",      demo_snapshot_compare),
    ("Memory Leak Detection",          demo_memory_leak_detection),
    ("lru_cache Benchmark",            demo_lru_cache),
    ("__slots__ Benchmark",            lambda: benchmark_slots(n=50_000)),
    ("Generator vs List Memory",       demo_generator_vs_list),
    ("FastAPI Middleware Pattern",     demo_fastapi_middleware_pattern),
    ("@profile Decorator",             demo_profile_decorator),
    ("Optimization Patterns Summary",  demo_optimization_patterns_summary),
    ("Interview Q&A",                  print_interview_qa),
]

# Quick subset for 'demo' mode (faster, less memory-intensive)
DEMO_QUICK = [0, 1, 3, 5, 7, 10, 13]  # indices into DEMO_SECTIONS


def main():
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "all"

    print(f"\n{'#' * 65}")
    print(f"  07 — Performance Profiling & Optimization")
    print(f"  Mode: {mode.upper()}")
    print(f"{'#' * 65}")

    if mode == "demo":
        sections = [DEMO_SECTIONS[i] for i in DEMO_QUICK]
        print(f"  Running {len(sections)} quick demo sections...")
    else:
        sections = DEMO_SECTIONS
        print(f"  Running all {len(sections)} sections...")

    for name, fn in sections:
        try:
            fn()
        except Exception as exc:
            print(f"\n  [ERROR in '{name}']: {exc}")
            import traceback
            traceback.print_exc()

    print(f"\n{'#' * 65}")
    print("  All sections complete.")
    print(f"{'#' * 65}\n")


if __name__ == "__main__":
    main()
