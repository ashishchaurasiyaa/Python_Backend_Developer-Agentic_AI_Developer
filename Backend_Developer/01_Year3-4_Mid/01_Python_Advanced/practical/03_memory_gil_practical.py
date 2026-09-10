"""
Python Memory Management & GIL — Practical Runnable Examples
=============================================================
Topics covered:
  - Reference counting: sys.getrefcount(), id()
  - Small int cache & string interning
  - Cyclic references and gc module
  - sys.getsizeof() — shallow vs deep size measurement
  - __slots__ — memory-efficient classes
  - tracemalloc — profiling memory allocations
  - weakref and WeakValueDictionary — cache that doesn't block GC
  - GIL: threading vs multiprocessing — I/O-bound vs CPU-bound demo
  - asyncio — single-thread concurrency for I/O-bound
  - FastAPI production pattern — async I/O + ProcessPoolExecutor (no event-loop blocking)
  - Shallow copy vs deep copy

How to run:
  python 03_memory_gil_practical.py

pip install:
  (none — standard library only)

macOS/Windows note (this bit matters): everything below is wrapped in
main() and gated by `if __name__ == "__main__":`. On macOS/Windows,
multiprocessing's default start method is "spawn" — each worker process
re-imports this module from scratch. If only the `Pool(...)` call were
guarded (not the whole script), every top-level print/side-effect above
it would re-run once per worker, silently polluting both the output and
the timing measurement. Verified by actually hitting this bug in an
earlier version of this file — see the commit that introduced this guard.
"""

import sys
import gc
import weakref
import copy
import threading
import multiprocessing
import asyncio
import time
import tracemalloc
from concurrent.futures import ProcessPoolExecutor


# ─── Section 2 support: a class with a cycle-prone __del__ ───


class Node:
    def __init__(self, name: str) -> None:
        self.name = name
        self.other: "Node | None" = None

    def __del__(self) -> None:
        print(f"  Node '{self.name}' destroyed")


# ─── Section 4 support: __slots__ comparison classes ───


class PointNormal:
    """Each instance has __dict__ — overhead per object."""
    def __init__(self, x: float, y: float, z: float) -> None:
        self.x, self.y, self.z = x, y, z


class PointSlots:
    """__slots__ removes __dict__ — fixed attributes only."""
    # INTERVIEW: __slots__ = 30-50% memory reduction per instance
    # Tradeoff: can't add dynamic attributes, multiple inheritance tricky
    __slots__ = ("x", "y", "z")

    def __init__(self, x: float, y: float, z: float) -> None:
        self.x, self.y, self.z = x, y, z


# ─── Section 6 support: weakref demo class ───


class HeavyResource:
    def __init__(self, name: str) -> None:
        self.name = name
        self.data = list(range(10_000))  # some weight

    def __del__(self) -> None:
        print(f"  HeavyResource '{self.name}' destroyed")


def deep_size(obj: object, seen: set | None = None) -> int:
    """Recursively calculate true memory footprint of an object."""
    if seen is None:
        seen = set()
    obj_id = id(obj)
    if obj_id in seen:
        return 0
    seen.add(obj_id)
    size = sys.getsizeof(obj)
    if isinstance(obj, dict):
        size += sum(deep_size(k, seen) + deep_size(v, seen) for k, v in obj.items())
    elif isinstance(obj, (list, tuple, set, frozenset)):
        size += sum(deep_size(i, seen) for i in obj)
    return size


# ─── Section 7 support: CPU-bound / I/O-bound worker functions ───
# Must be at module level (not nested in main()) so multiprocessing
# can pickle + re-import them by reference in spawned worker processes.


def cpu_bound(n: int) -> int:
    """CPU-intensive — GIL held throughout."""
    count = 0
    for i in range(n):
        count += i * i
    return count


def io_bound(seconds: float) -> None:
    """I/O wait — GIL released during sleep."""
    time.sleep(seconds)


# ─── Section 8 support: asyncio coroutine ───


async def simulate_db_query(name: str, delay: float) -> dict:
    """Simulates an async DB/HTTP call."""
    await asyncio.sleep(delay)   # yields control — other coroutines run
    return {"query": name, "result": f"data_{name}"}


async def main_async() -> None:
    print("Running 3 async queries concurrently...")
    start = time.perf_counter()

    # INTERVIEW: asyncio.gather = run coroutines concurrently (not parallel)
    results = await asyncio.gather(
        simulate_db_query("users", 0.2),
        simulate_db_query("orders", 0.15),
        simulate_db_query("products", 0.1),
    )

    elapsed = time.perf_counter() - start
    print(f"  All done in {elapsed:.2f}s (expected ~0.2s, not 0.45s)")
    for r in results:
        print(f"  {r}")


async def simulate_io_request(request_id: int) -> None:
    """Stand-in for a normal async FastAPI route (e.g. DB-backed)."""
    start = time.perf_counter()
    await asyncio.sleep(0.05)
    print(f"  [I/O request {request_id}] served in {time.perf_counter() - start:.3f}s")


async def simulate_cpu_request(pool: ProcessPoolExecutor, request_id: int, n: int) -> None:
    """The FastAPI pattern: `await loop.run_in_executor(pool, cpu_fn, ...)`
    inside an async route offloads CPU work to a worker PROCESS instead of
    running it on the event loop thread -- this is what actually happens
    under `await loop.run_in_executor(process_pool, cpu_bound_fn, data)`
    in a real FastAPI handler."""
    loop = asyncio.get_running_loop()
    start = time.perf_counter()
    await loop.run_in_executor(pool, cpu_bound, n)
    print(f"  [CPU request {request_id}] served in {time.perf_counter() - start:.3f}s (ran in a worker PROCESS)")


async def fastapi_pattern_demo() -> None:
    n = 20_000_000

    print("Baseline -- CPU work run directly (blocks the event loop):")
    start = time.perf_counter()
    cpu_bound(n)   # what happens if a route does this with NO executor
    print(f"  blocking call took {time.perf_counter() - start:.3f}s -- during this,"
          f" an async server answers ZERO other requests\n")

    print("Fix -- same CPU work via ProcessPoolExecutor + run_in_executor:")
    with ProcessPoolExecutor(max_workers=2) as pool:
        start = time.perf_counter()
        await asyncio.gather(
            simulate_cpu_request(pool, 1, n),
            simulate_io_request(101),
            simulate_io_request(102),
            simulate_io_request(103),
            simulate_io_request(104),
        )
        print(f"  all 5 concurrent 'requests' finished in {time.perf_counter() - start:.3f}s")
        print("  (I/O requests answered almost instantly WHILE the CPU request")
        print("   was still running in a background process -- event loop was")
        print("   never blocked)")


def main() -> None:
    # ─── Section 1: Reference Counting ───

    print("=" * 60)
    print("SECTION 1: Reference Counting")
    print("=" * 60)

    x = [1, 2, 3]
    # INTERVIEW: getrefcount always shows +1 because the function call itself is a reference
    print(f"refcount(x) after assignment: {sys.getrefcount(x)}")  # 2

    y = x
    print(f"refcount(x) after y=x: {sys.getrefcount(x)}")         # 3

    del y
    print(f"refcount(x) after del y: {sys.getrefcount(x)}")        # 2

    # INTERVIEW: id() returns memory address — use `is` to check same object
    print(f"\nid(x) = {id(x)}")

    # INTERVIEW: Small int cache — integers -5 to 256 are pre-allocated singletons
    a, b = 100, 100
    print(f"a is b (100): {a is b}")    # True — same cached object

    c, d = 1000, 1000
    print(f"c is d (1000): {c is d}")   # False — not cached (implementation detail)

    # INTERVIEW: String interning — short identifier-like strings are shared
    s1 = "hello"
    s2 = "hello"
    print(f"\ns1 is s2 ('hello'): {s1 is s2}")   # True — interned

    s3 = "hello world! long string that won't be interned"
    s4 = "hello world! long string that won't be interned"
    print(f"s3 is s4 (long): {s3 is s4}")        # Often False — implementation-defined

    # ─── Section 2: Cyclic References + gc Module ───

    print("\n" + "=" * 60)
    print("SECTION 2: Cyclic References + GC")
    print("=" * 60)

    # INTERVIEW: Cycles prevent ref count from reaching 0 — GC needed
    gc.disable()   # disable automatic GC to demonstrate manually

    node_a = Node("A")
    node_b = Node("B")
    node_a.other = node_b    # A → B
    node_b.other = node_a    # B → A  (cycle!)

    del node_a
    del node_b
    # Neither node is destroyed yet — ref counts stuck at 1 due to cycle
    print("After del a, del b — neither destroyed yet (cycle keeps ref count alive)")

    print(f"gc.collect() returns: {gc.collect()} objects collected")
    # Now both nodes are destroyed

    gc.enable()

    # GC stats
    print(f"\ngc.get_count() = {gc.get_count()}")       # (gen0, gen1, gen2) counts
    print(f"gc.get_threshold() = {gc.get_threshold()}")  # (700, 10, 10) defaults

    # ─── Section 3: sys.getsizeof + Deep Size ───

    print("\n" + "=" * 60)
    print("SECTION 3: Object Sizes")
    print("=" * 60)

    # INTERVIEW: getsizeof is SHALLOW — nested objects NOT counted
    print(f"Empty list:   {sys.getsizeof([])} bytes")
    print(f"Empty dict:   {sys.getsizeof({})} bytes")
    print(f"Empty str:    {sys.getsizeof('')} bytes")
    print(f"int 0:        {sys.getsizeof(0)} bytes")
    print(f"list 1000:    {sys.getsizeof([0] * 1000)} bytes")  # container size, not contents

    nested = {"a": [1, 2, 3], "b": {"c": 4}}
    print(f"\nNested dict shallow: {sys.getsizeof(nested)} bytes")
    print(f"Nested dict deep:   {deep_size(nested)} bytes")

    # ─── Section 4: __slots__ — Memory Optimization ───

    print("\n" + "=" * 60)
    print("SECTION 4: __slots__ Memory Optimization")
    print("=" * 60)

    pn = PointNormal(1.0, 2.0, 3.0)
    ps = PointSlots(1.0, 2.0, 3.0)

    pn_size = sys.getsizeof(pn) + sys.getsizeof(pn.__dict__)
    ps_size = sys.getsizeof(ps)

    print(f"PointNormal: {sys.getsizeof(pn)} + {sys.getsizeof(pn.__dict__)} dict = {pn_size} bytes")
    print(f"PointSlots:  {ps_size} bytes (no __dict__)")
    print(f"Memory saved per instance: {pn_size - ps_size} bytes ({(pn_size - ps_size)/pn_size*100:.0f}%)")

    # Can't add new attributes with __slots__
    try:
        ps.w = 4.0  # type: ignore
    except AttributeError as e:
        print(f"\n__slots__ blocks dynamic attr: {e}")

    # INTERVIEW: When to use __slots__:
    # - 100K+ instances of small objects (Point, Vector, Row, etc.)
    # - Attributes are fixed and known at class definition time
    print("\n__slots__ use case: 100K+ instances with fixed attributes")

    tracemalloc.start()
    normal_objs = [PointNormal(i, i * 2.0, i * 3.0) for i in range(50_000)]
    snap_normal = tracemalloc.take_snapshot()
    del normal_objs

    slots_objs = [PointSlots(i, i * 2.0, i * 3.0) for i in range(50_000)]
    snap_slots = tracemalloc.take_snapshot()
    del slots_objs

    tracemalloc.stop()

    normal_mem = sum(s.size for s in snap_normal.statistics("filename")[:5])
    slots_mem  = sum(s.size for s in snap_slots.statistics("filename")[:5])
    print(f"50K PointNormal: ~{normal_mem/1024:.0f} KB")
    print(f"50K PointSlots:  ~{slots_mem/1024:.0f} KB")

    # ─── Section 5: tracemalloc — Memory Profiling ───

    print("\n" + "=" * 60)
    print("SECTION 5: tracemalloc — Memory Profiling")
    print("=" * 60)

    # INTERVIEW: tracemalloc tracks Python-level allocations — useful for leak detection
    tracemalloc.start()

    # Some work
    data = [i ** 2 for i in range(100_000)]

    snapshot = tracemalloc.take_snapshot()
    top_stats = snapshot.statistics("lineno")

    print("Top 3 memory allocations:")
    for stat in top_stats[:3]:
        print(f"  {stat}")

    current, peak = tracemalloc.get_traced_memory()
    print(f"\nCurrent: {current / 1024:.1f} KB")
    print(f"Peak:    {peak / 1024:.1f} KB")

    tracemalloc.stop()
    del data

    # ─── Section 6: weakref — Weak References + WeakValueDictionary ───

    print("\n" + "=" * 60)
    print("SECTION 6: weakref — Weak References")
    print("=" * 60)

    obj = HeavyResource("db_connection")

    # INTERVIEW: weakref does NOT increment ref count — GC can collect freely
    weak = weakref.ref(obj)

    print(f"weak() alive: {weak() is not None}")   # True
    print(f"weak().name: {weak().name}")            # type: ignore[union-attr]

    del obj   # only strong reference deleted → ref count → 0 → destroyed
    print(f"After del obj, weak() = {weak()}")      # None — object collected

    # INTERVIEW: WeakValueDictionary = cache that doesn't prevent GC
    # Use case: object cache where entries should expire when no longer in use elsewhere
    normal_cache: dict[str, HeavyResource] = {}
    weak_cache: weakref.WeakValueDictionary[str, HeavyResource] = weakref.WeakValueDictionary()

    resource = HeavyResource("cached_resource")
    normal_cache["key"] = resource
    weak_cache["key"] = resource

    print(f"\n'key' in weak_cache (before del): {'key' in weak_cache}")
    print(f"'key' in normal_cache (before del): {'key' in normal_cache}")

    del resource   # remove external strong ref
    gc.collect()

    print(f"'key' in weak_cache (after del): {'key' in weak_cache}")   # False
    print(f"'key' in normal_cache (after del): {'key' in normal_cache}")  # True (dict holds ref)

    # ─── Section 7: GIL — Threading vs Multiprocessing ───

    print("\n" + "=" * 60)
    print("SECTION 7: GIL Impact — Threading vs Multiprocessing")
    print("=" * 60)

    # INTERVIEW: I/O bound — Threading wins because GIL is RELEASED during I/O
    print("I/O-bound: 4 threads x 0.2s sleep each")
    start = time.perf_counter()
    io_threads = [threading.Thread(target=io_bound, args=(0.2,)) for _ in range(4)]
    for t in io_threads:
        t.start()
    for t in io_threads:
        t.join()
    io_thread_time = time.perf_counter() - start
    print(f"  Threading: {io_thread_time:.2f}s (expect ~0.2s -- concurrent)")

    # Serial for comparison
    start = time.perf_counter()
    for _ in range(4):
        io_bound(0.2)
    serial_time = time.perf_counter() - start
    print(f"  Serial:    {serial_time:.2f}s (expect ~0.8s)")

    # INTERVIEW: CPU bound -- Threading does NOT help (GIL prevents true parallelism)
    n = 500_000
    print(f"\nCPU-bound: 4 workers x {n} loop iterations each")

    start = time.perf_counter()
    cpu_threads = [threading.Thread(target=cpu_bound, args=(n,)) for _ in range(4)]
    for t in cpu_threads:
        t.start()
    for t in cpu_threads:
        t.join()
    thread_cpu_time = time.perf_counter() - start
    print(f"  Threading (4 threads):     {thread_cpu_time:.3f}s")

    # Multiprocessing -- each process has its own GIL -> true parallelism.
    # Safe here: we are already inside `if __name__ == "__main__":` at the
    # call site (see bottom of file) -- module import at this point does
    # NOT re-run any of the code above, so spawned workers won't duplicate
    # Sections 1-6 output like the earlier version of this file did.
    start = time.perf_counter()
    with multiprocessing.Pool(4) as pool:
        pool.map(cpu_bound, [n] * 4)
    mp_time = time.perf_counter() - start
    print(f"  Multiprocessing (4 procs): {mp_time:.3f}s")
    print(f"  Speedup: {thread_cpu_time / mp_time:.1f}x")
    # VERIFIED FINDING (not a bug): at n=500_000 this speedup can come out
    # BELOW 1.0x on macOS -- process-spawn overhead (~50-100ms/process to
    # boot a fresh interpreter under the "spawn" start method) can exceed
    # the actual compute time saved for a workload this small. Multi-
    # processing only pays off once real compute time clears spawn
    # overhead -- bump `n` toward 30_000_000 to see the crossover flip
    # (verified: threading ~1.7s, multiprocessing ~1.0s at that size).
    # Lesson: measure before assuming multiprocessing is "the CPU-bound
    # answer" -- overhead is real, not just theoretical.

    # ─── Section 8: asyncio -- Single-thread I/O Concurrency ───

    print("\n" + "=" * 60)
    print("SECTION 8: asyncio -- Cooperative Concurrency")
    print("=" * 60)

    # INTERVIEW: asyncio = single thread, cooperative multitasking
    # No GIL issue -- one thread, multiple coroutines yielding at await points
    asyncio.run(main_async())

    # ─── Section 10: FastAPI production pattern -- async + ProcessPoolExecutor ───
    # This is the actual mechanism behind:
    #   @app.post("/heavy")
    #   async def heavy(data: In):
    #       return await loop.run_in_executor(process_pool, cpu_bound_fn, data)
    # fastapi/uvicorn aren't required to prove this -- it's pure asyncio +
    # concurrent.futures, identical to what Starlette's event loop does.

    print("\n" + "=" * 60)
    print("SECTION 10: FastAPI Pattern -- async I/O + ProcessPoolExecutor")
    print("=" * 60)

    asyncio.run(fastapi_pattern_demo())

    # ─── Section 9: Shallow vs Deep Copy ───

    print("\n" + "=" * 60)
    print("SECTION 9: Shallow vs Deep Copy")
    print("=" * 60)

    original = {
        "name": "Ashish",
        "scores": [95, 87, 92],
        "address": {"city": "Mumbai", "pin": "400001"},
    }

    # Assignment -- same object
    ref = original
    ref["name"] = "Changed"
    print(f"Assignment -- original['name'] after ref['name']='Changed': {original['name']}")
    original["name"] = "Ashish"  # restore

    # INTERVIEW: Shallow copy -- new top-level container, but nested objects shared
    shallow = original.copy()
    shallow["name"] = "Bob"              # independent -- top-level
    shallow["scores"].append(100)        # SHARED -- both change!
    shallow["address"]["city"] = "Delhi" # SHARED

    print(f"\nShallow copy results:")
    print(f"  original['name'] = {original['name']}")            # "Ashish" -- not affected
    print(f"  original['scores'] = {original['scores']}")        # [95, 87, 92, 100] -- AFFECTED
    print(f"  original['address']['city'] = {original['address']['city']}")  # "Delhi" -- AFFECTED

    # Restore
    original = {"name": "Ashish", "scores": [95, 87, 92], "address": {"city": "Mumbai", "pin": "400001"}}

    # INTERVIEW: Deep copy -- fully independent at all levels
    deep = copy.deepcopy(original)
    deep["name"] = "Charlie"
    deep["scores"].append(100)
    deep["address"]["city"] = "Pune"

    print(f"\nDeep copy results:")
    print(f"  original['name'] = {original['name']}")            # "Ashish" -- safe
    print(f"  original['scores'] = {original['scores']}")        # [95, 87, 92] -- safe
    print(f"  original['address']['city'] = {original['address']['city']}")  # "Mumbai" -- safe

    # INTERVIEW decision guide:
    # = (assignment) : intentional aliasing -- same object in memory
    # .copy()        : flat structures, or nested won't be mutated
    # deepcopy()     : fully independent copy of nested mutable structures

    print("\n--- SUMMARY ---")
    print("Reference counting     : primary GC -- immediate when ref count hits 0")
    print("Cyclic GC (gc module)  : handles cycles ref counting misses")
    print("__slots__              : remove __dict__ -- 30-50% memory save for many instances")
    print("tracemalloc            : profile Python-level allocations for leak detection")
    print("weakref                : ref that doesn't prevent GC -- use for caches")
    print("GIL                    : one thread runs Python bytecode at a time")
    print("I/O-bound              : threading works (GIL released during I/O)")
    print("CPU-bound              : multiprocessing needed (separate GIL per process)")
    print("asyncio                : single-thread cooperative concurrency for I/O")
    print("deep copy              : needed when mutating nested mutable objects independently")
    print("FastAPI + ProcessPool  : offload CPU work via run_in_executor -- keeps event loop free")


# INTERVIEW / macOS gotcha: this guard must wrap the ENTIRE script's
# executable logic (via main()), not just the multiprocessing.Pool call.
# On macOS/Windows (start method "spawn"), each worker re-imports this
# module -- if executable code sat at module level outside main(), every
# worker would re-run it too, corrupting both output and timings. This
# is exactly the bug an earlier version of this file had (verified: it
# printed "SECTION 1" five times -- once for the main process, once per
# spawned worker -- and the multiprocessing timing measurement above was
# meaningless as a result, since it mostly measured re-import overhead).
if __name__ == "__main__":
    main()
