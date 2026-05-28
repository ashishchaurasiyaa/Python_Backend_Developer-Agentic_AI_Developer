"""
╔══════════════════════════════════════════════════════════════╗
║  PYTHON COMPLETE PRACTICAL — Section 03                      ║
║  Topic: Python Internals, GIL, Memory, Performance           ║
╚══════════════════════════════════════════════════════════════╝
"""

import sys
import gc
import dis
import weakref
import time
import tracemalloc
import cProfile
import pstats
import io
import functools
from typing import Any


# ══════════════════════════════════════════════════════════════
# PART A: GIL — Global Interpreter Lock
# ══════════════════════════════════════════════════════════════

"""
GIL EXPLAINED:
  - CPython mutex that allows only 1 thread to hold control of the Python interpreter
  - Released during I/O operations (sleep, network, file ops)
  - Released every 100 bytecode instructions (pre-3.2) or 5ms (3.2+)

IMPLICATIONS:
  - I/O-bound threading: WORKS (GIL released during I/O)
  - CPU-bound threading: NO SPEEDUP (GIL prevents parallel execution)
  - Multiprocessing: BYPASSES GIL (each process has own interpreter)
  - asyncio: SINGLE THREAD, no GIL contention
"""

import threading

shared = 0
lock = threading.Lock()

def cpu_bound_thread(n: int) -> None:
    """CPU-bound — GIL prevents true parallelism."""
    global shared
    total = 0
    for i in range(n):
        total += i * i
    with lock:
        shared += total

# Threads don't help for CPU-bound
start = time.perf_counter()
threads = [threading.Thread(target=cpu_bound_thread, args=(500_000,)) for _ in range(4)]
for t in threads:
    t.start()
for t in threads:
    t.join()
cpu_time = time.perf_counter() - start
print(f"CPU-bound threading (4 threads): {cpu_time:.3f}s (GIL limits parallelism)")


# ══════════════════════════════════════════════════════════════
# PART B: MEMORY MODEL
# ══════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────
# 1. REFERENCE COUNTING
# ─────────────────────────────────────────────────────────────

x = [1, 2, 3]
print(f"\nRef count of x: {sys.getrefcount(x)}")   # 2 (x + getrefcount arg)

y = x          # creates new reference
print(f"Ref count after y=x: {sys.getsizeof(x)} bytes, refs={sys.getrefcount(x)}")

z = [x, x, x]  # 3 more references
print(f"Ref count after z=[x,x,x]: {sys.getrefcount(x)}")

del z, y
print(f"Ref count after del: {sys.getrefcount(x)}")


# ─────────────────────────────────────────────────────────────
# 2. GARBAGE COLLECTOR — handles circular references
# ─────────────────────────────────────────────────────────────

class Node:
    def __init__(self, val: int):
        self.val = val
        self.next: Node | None = None
        print(f"  [Node] Created: {val}")

    def __del__(self):
        print(f"  [Node] Destroyed: {self.val}")

# Circular reference — refcount stays at 1, not freed automatically
a = Node(1)
b = Node(2)
a.next = b
b.next = a   # circular!

del a, b     # refcount doesn't reach 0!

print(f"\nBefore gc.collect: cyclic objects not freed")
collected = gc.collect()   # force garbage collection
print(f"GC collected: {collected} objects")

# GC configuration
print(f"\nGC thresholds: {gc.get_threshold()}")  # (700, 10, 10)
# gc.disable()  — disable GC (if you manage refcounts carefully)
# gc.enable()   — re-enable


# ─────────────────────────────────────────────────────────────
# 3. OBJECT SIZE
# ─────────────────────────────────────────────────────────────

print("\n=== Object Memory Sizes ===")
objects = [
    ("int(0)",      0),
    ("int(1000)",   1000),
    ("float",       3.14),
    ("str(10)",     "hello12345"),
    ("list(10)",    list(range(10))),
    ("tuple(10)",   tuple(range(10))),
    ("dict(10)",    {i: i for i in range(10)}),
    ("set(10)",     set(range(10))),
    ("None",        None),
    ("True",        True),
]

for name, obj in objects:
    size = sys.getsizeof(obj)
    print(f"  {name:<20}: {size:>6} bytes")


# ─────────────────────────────────────────────────────────────
# 4. __SLOTS__ — reduce memory footprint
# ─────────────────────────────────────────────────────────────

class WithDict:
    def __init__(self, x: int, y: int, z: int):
        self.x = x
        self.y = y
        self.z = z

class WithSlots:
    __slots__ = ("x", "y", "z")

    def __init__(self, x: int, y: int, z: int):
        self.x = x
        self.y = y
        self.z = z


n = 100_000
start = time.perf_counter()
dict_objects = [WithDict(i, i, i) for i in range(n)]
dict_time = time.perf_counter() - start

start = time.perf_counter()
slot_objects = [WithSlots(i, i, i) for i in range(n)]
slot_time = time.perf_counter() - start

d_obj = WithDict(1, 2, 3)
s_obj = WithSlots(1, 2, 3)

print(f"\n__slots__ comparison (100k objects):")
print(f"  WithDict  size: {sys.getsizeof(d_obj) + sys.getsizeof(d_obj.__dict__)} bytes, time: {dict_time:.3f}s")
print(f"  WithSlots size: {sys.getsizeof(s_obj)} bytes, time: {slot_time:.3f}s")
print(f"  Memory savings: ~{(1 - sys.getsizeof(s_obj)/(sys.getsizeof(d_obj)+sys.getsizeof(d_obj.__dict__)))*100:.0f}%")


# ─────────────────────────────────────────────────────────────
# 5. WEAKREF — reference without preventing GC
# ─────────────────────────────────────────────────────────────

class LLMSession:
    def __init__(self, session_id: str):
        self.session_id = session_id
        print(f"  [Session] Created: {session_id}")

    def __del__(self):
        print(f"  [Session] Destroyed: {self.session_id}")


print("\n=== weakref ===")
sess = LLMSession("sess_001")
weak = weakref.ref(sess)

print(f"Before del: {weak()}")      # LLMSession object
del sess
gc.collect()
print(f"After del: {weak()}")       # None

# WeakValueDictionary — auto-removes entries when values are GC'd
session_cache: weakref.WeakValueDictionary = weakref.WeakValueDictionary()
s1 = LLMSession("A")
s2 = LLMSession("B")
session_cache["A"] = s1
session_cache["B"] = s2

del s1
gc.collect()
print(f"Cache keys after del s1: {list(session_cache.keys())}")  # only B


# ══════════════════════════════════════════════════════════════
# PART C: PROFILING
# ══════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────
# 6. CPU PROFILING with cProfile
# ─────────────────────────────────────────────────────────────

def slow_fib(n: int) -> int:
    if n < 2: return n
    return slow_fib(n - 1) + slow_fib(n - 2)

def profile(func, *args) -> Any:
    pr = cProfile.Profile()
    pr.enable()
    result = func(*args)
    pr.disable()

    stream = io.StringIO()
    ps = pstats.Stats(pr, stream=stream).sort_stats("cumulative")
    ps.print_stats(5)
    print(stream.getvalue())
    return result

print("=== CPU Profile ===")
profile(slow_fib, 25)


# ─────────────────────────────────────────────────────────────
# 7. MEMORY PROFILING with tracemalloc
# ─────────────────────────────────────────────────────────────

print("=== Memory Profile ===")
tracemalloc.start()

# Simulate memory-heavy operation
data = [[float(i * j) for j in range(100)] for i in range(1000)]

snapshot = tracemalloc.take_snapshot()
top = snapshot.statistics("lineno")[:3]
for stat in top:
    print(f"  {stat}")

tracemalloc.stop()


# ─────────────────────────────────────────────────────────────
# 8. TIMING DECORATORS
# ─────────────────────────────────────────────────────────────

def timeit(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = (time.perf_counter() - start) * 1000
        print(f"[TIMER] {func.__name__}: {elapsed:.3f}ms")
        return result
    return wrapper

@timeit
def process_documents(docs: list[str]) -> list[str]:
    return [d.upper().strip() for d in docs]

process_documents(["doc1", "doc2", "doc3"] * 10_000)


# ══════════════════════════════════════════════════════════════
# PART D: PERFORMANCE OPTIMIZATION
# ══════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────
# 9. BYTECODE — dis module
# ─────────────────────────────────────────────────────────────

def add(a, b):
    return a + b

print("\n=== Bytecode for add(a, b) ===")
dis.dis(add)


# ─────────────────────────────────────────────────────────────
# 10. PERFORMANCE TIPS
# ─────────────────────────────────────────────────────────────

# TIP 1: Local variables faster than global
import math

# Slow — global lookup every iteration
def slow_compute(n):
    result = 0
    for i in range(n):
        result += math.sqrt(i)
    return result

# Fast — local reference
def fast_compute(n):
    local_sqrt = math.sqrt   # local lookup
    result = 0
    for i in range(n):
        result += local_sqrt(i)
    return result

n = 100_000
start = time.perf_counter(); slow_compute(n); slow = time.perf_counter() - start
start = time.perf_counter(); fast_compute(n); fast = time.perf_counter() - start
print(f"\nGlobal lookup: {slow*1000:.2f}ms")
print(f"Local lookup:  {fast*1000:.2f}ms")


# TIP 2: List comprehension vs for loop
n = 100_000

start = time.perf_counter()
result1 = []
for i in range(n):
    result1.append(i * 2)
loop_time = time.perf_counter() - start

start = time.perf_counter()
result2 = [i * 2 for i in range(n)]
comp_time = time.perf_counter() - start

print(f"for loop:      {loop_time*1000:.2f}ms")
print(f"comprehension: {comp_time*1000:.2f}ms")


# TIP 3: join vs += for strings
parts = [f"word_{i}" for i in range(10000)]

start = time.perf_counter()
s = ""
for p in parts:
    s += p   # O(n²) — creates new string each time
concat_time = time.perf_counter() - start

start = time.perf_counter()
s = "".join(parts)  # O(n) — one allocation
join_time = time.perf_counter() - start

print(f"String +=:  {concat_time*1000:.2f}ms")
print(f"str.join(): {join_time*1000:.2f}ms")


# TIP 4: set lookup vs list lookup
large_list = list(range(10_000))
large_set  = set(large_list)

start = time.perf_counter()
for _ in range(1000):
    9999 in large_list
list_lookup = time.perf_counter() - start

start = time.perf_counter()
for _ in range(1000):
    9999 in large_set
set_lookup = time.perf_counter() - start

print(f"\nList lookup 1000×: {list_lookup*1000:.2f}ms")
print(f"Set lookup 1000×:  {set_lookup*1000:.4f}ms (much faster)")


# TIP 5: functools.lru_cache for repeated computations
@functools.lru_cache(maxsize=None)
def cached_fib(n: int) -> int:
    if n < 2: return n
    return cached_fib(n - 1) + cached_fib(n - 2)

start = time.perf_counter()
result = cached_fib(50)
cached_time = time.perf_counter() - start
print(f"\nCached fib(50): {result} in {cached_time*1000:.4f}ms")
print(f"Cache info: {cached_fib.cache_info()}")


# ─────────────────────────────────────────────────────────────
# INTERVIEW QUESTIONS
# ─────────────────────────────────────────────────────────────
"""
Q: What is the GIL and how does it affect concurrency?
A: Global Interpreter Lock — mutex ensuring only 1 thread runs Python bytecode
   at a time. Released during I/O. CPU-bound threading gets no speedup.
   Solutions: asyncio for I/O-bound, multiprocessing for CPU-bound.

Q: How does Python manage memory?
A: 1. Reference counting (primary) — object freed when refcount hits 0.
   2. Cyclic GC (secondary) — handles circular references refcount can't.
   3. Memory pools — CPython uses pymalloc for small objects.

Q: What is the difference between __del__ and garbage collection?
A: __del__ is called when refcount reaches 0 (or GC collects it).
   Don't rely on __del__ for resource cleanup — use context managers instead.
   With circular refs, __del__ may be called unpredictably.

Q: When should you use __slots__?
A: When creating MANY instances of a class (thousands/millions).
   Reduces per-instance memory ~30-40% by avoiding __dict__.
   Trade-off: can't add arbitrary attributes dynamically.

Q: What does dis.dis() do?
A: Shows the CPython bytecode for a function.
   Useful for understanding low-level performance and Python internals.
   Helps explain why x = x + 1 is slower than x += 1 in some cases.
"""
