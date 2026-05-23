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
  - Shallow copy vs deep copy

How to run:
  python 03_memory_gil_practical.py

pip install:
  (none — standard library only)
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


class Node:
    def __init__(self, name: str) -> None:
        self.name = name
        self.other: "Node | None" = None

    def __del__(self) -> None:
        print(f"  Node '{self.name}' destroyed")


# INTERVIEW: Cycles prevent ref count from reaching 0 — GC needed
gc.disable()   # disable automatic GC to demonstrate manually

a = Node("A")
b = Node("B")
a.other = b    # A → B
b.other = a    # B → A  (cycle!)

del a
del b
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


print(f"Nested dict deep:   {deep_size(nested)} bytes")


# ─── Section 4: __slots__ — Memory Optimization ───

print("\n" + "=" * 60)
print("SECTION 4: __slots__ Memory Optimization")
print("=" * 60)


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


class HeavyResource:
    def __init__(self, name: str) -> None:
        self.name = name
        self.data = list(range(10_000))  # some weight

    def __del__(self) -> None:
        print(f"  HeavyResource '{self.name}' destroyed")


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


def cpu_bound(n: int) -> int:
    """CPU-intensive — GIL held throughout."""
    count = 0
    for i in range(n):
        count += i * i
    return count


def io_bound(seconds: float) -> None:
    """I/O wait — GIL released during sleep."""
    time.sleep(seconds)


# INTERVIEW: I/O bound — Threading wins because GIL is RELEASED during I/O
print("I/O-bound: 4 threads × 0.2s sleep each")
start = time.perf_counter()
threads = [threading.Thread(target=io_bound, args=(0.2,)) for _ in range(4)]
for t in threads:
    t.start()
for t in threads:
    t.join()
io_thread_time = time.perf_counter() - start
print(f"  Threading: {io_thread_time:.2f}s (expected ~0.2s — concurrent)")

# Serial for comparison
start = time.perf_counter()
for _ in range(4):
    io_bound(0.2)
serial_time = time.perf_counter() - start
print(f"  Serial:    {serial_time:.2f}s (expected ~0.8s)")

# INTERVIEW: CPU bound — Threading does NOT help (GIL prevents true parallelism)
N = 500_000
print(f"\nCPU-bound: 4 workers × {N} loop iterations each")

start = time.perf_counter()
threads = [threading.Thread(target=cpu_bound, args=(N,)) for _ in range(4)]
for t in threads:
    t.start()
for t in threads:
    t.join()
thread_cpu_time = time.perf_counter() - start
print(f"  Threading (4 threads):     {thread_cpu_time:.3f}s")

# Multiprocessing — each process has its own GIL → true parallelism
if __name__ == "__main__":
    start = time.perf_counter()
    with multiprocessing.Pool(4) as pool:
        pool.map(cpu_bound, [N] * 4)
    mp_time = time.perf_counter() - start
    print(f"  Multiprocessing (4 procs): {mp_time:.3f}s")
    print(f"  Speedup: {thread_cpu_time / mp_time:.1f}x")


# ─── Section 8: asyncio — Single-thread I/O Concurrency ───

print("\n" + "=" * 60)
print("SECTION 8: asyncio — Cooperative Concurrency")
print("=" * 60)


# INTERVIEW: asyncio = single thread, cooperative multitasking
# No GIL issue — one thread, multiple coroutines yielding at await points
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


asyncio.run(main_async())


# ─── Section 9: Shallow vs Deep Copy ───

print("\n" + "=" * 60)
print("SECTION 9: Shallow vs Deep Copy")
print("=" * 60)

original = {
    "name": "Ashish",
    "scores": [95, 87, 92],
    "address": {"city": "Mumbai", "pin": "400001"},
}

# Assignment — same object
ref = original
ref["name"] = "Changed"
print(f"Assignment — original['name'] after ref['name']='Changed': {original['name']}")
original["name"] = "Ashish"  # restore

# INTERVIEW: Shallow copy — new top-level container, but nested objects shared
shallow = original.copy()
shallow["name"] = "Bob"              # independent — top-level
shallow["scores"].append(100)        # SHARED — both change!
shallow["address"]["city"] = "Delhi" # SHARED

print(f"\nShallow copy results:")
print(f"  original['name'] = {original['name']}")            # "Ashish" — not affected
print(f"  original['scores'] = {original['scores']}")        # [95, 87, 92, 100] — AFFECTED
print(f"  original['address']['city'] = {original['address']['city']}")  # "Delhi" — AFFECTED

# Restore
original = {"name": "Ashish", "scores": [95, 87, 92], "address": {"city": "Mumbai", "pin": "400001"}}

# INTERVIEW: Deep copy — fully independent at all levels
deep = copy.deepcopy(original)
deep["name"] = "Charlie"
deep["scores"].append(100)
deep["address"]["city"] = "Pune"

print(f"\nDeep copy results:")
print(f"  original['name'] = {original['name']}")            # "Ashish" — safe
print(f"  original['scores'] = {original['scores']}")        # [95, 87, 92] — safe
print(f"  original['address']['city'] = {original['address']['city']}")  # "Mumbai" — safe

# INTERVIEW decision guide:
# = (assignment) : intentional aliasing — same object in memory
# .copy()        : flat structures, or nested won't be mutated
# deepcopy()     : fully independent copy of nested mutable structures

print("\n--- SUMMARY ---")
print("Reference counting     : primary GC — immediate when ref count hits 0")
print("Cyclic GC (gc module)  : handles cycles ref counting misses")
print("__slots__              : remove __dict__ — 30-50% memory save for many instances")
print("tracemalloc            : profile Python-level allocations for leak detection")
print("weakref                : ref that doesn't prevent GC — use for caches")
print("GIL                    : one thread runs Python bytecode at a time")
print("I/O-bound              : threading works (GIL released during I/O)")
print("CPU-bound              : multiprocessing needed (separate GIL per process)")
print("asyncio                : single-thread cooperative concurrency for I/O")
print("deep copy              : needed when mutating nested mutable objects independently")
