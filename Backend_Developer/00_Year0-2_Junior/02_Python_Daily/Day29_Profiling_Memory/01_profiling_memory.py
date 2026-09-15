"""
DAY 35 — Profiling + Memory Management + weakref
Architecture Level: Senior Python Backend + Agentic AI
"""

import cProfile
import pstats
import io
import tracemalloc
import weakref
import gc
import sys
import time
from typing import Any


# ═══════════════════════════════════════════════════════
# PART A: cProfile — CPU profiling
# ═══════════════════════════════════════════════════════

def slow_fibonacci(n: int) -> int:
    """Deliberately inefficient — for profiling demo."""
    if n < 2:
        return n
    return slow_fibonacci(n - 1) + slow_fibonacci(n - 2)


def profile_function(func, *args, **kwargs):
    """Profile a function and print sorted stats."""
    pr = cProfile.Profile()
    pr.enable()
    result = func(*args, **kwargs)
    pr.disable()

    stream = io.StringIO()
    stats = pstats.Stats(pr, stream=stream)
    stats.sort_stats("cumulative")
    stats.print_stats(10)   # top 10 functions by cumulative time
    print(stream.getvalue())
    return result


print("=== CPU Profiling ===")
profile_function(slow_fibonacci, 25)


# ─────────────────────────────────────────────
# DECORATOR-based profiler
# ─────────────────────────────────────────────

import functools

def profiled(func):
    """Profile decorator — add to any function during debugging."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        pr = cProfile.Profile()
        pr.enable()
        result = func(*args, **kwargs)
        pr.disable()

        stats = pstats.Stats(pr)
        stats.sort_stats("cumulative")
        stats.print_stats(5)
        return result
    return wrapper


def timeit(func):
    """Lightweight timing decorator."""
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
    return [doc.upper().strip() for doc in docs]


docs = ["doc1", "doc2", "doc3"] * 1000
process_documents(docs)


# ═══════════════════════════════════════════════════════
# PART B: tracemalloc — Memory profiling
# ═══════════════════════════════════════════════════════

print("\n=== Memory Profiling with tracemalloc ===")

tracemalloc.start()

# Simulate memory-heavy operation
embeddings = [[0.1 * i for i in range(1536)] for _ in range(100)]

snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics("lineno")

print("Top 3 memory allocations:")
for stat in top_stats[:3]:
    print(f"  {stat}")

tracemalloc.stop()


# ─────────────────────────────────────────────
# Memory size of objects
# ─────────────────────────────────────────────

data_dict  = {"key": "value"} * 1     # note: this doesn't multiply
data_list  = list(range(10000))
data_tuple = tuple(range(10000))

print(f"\nMemory comparison:")
print(f"  list  of 10k ints: {sys.getsizeof(data_list):,} bytes")
print(f"  tuple of 10k ints: {sys.getsizeof(data_tuple):,} bytes")

# __slots__ vs __dict__
class WithDict:
    def __init__(self):
        self.x = 1
        self.y = 2
        self.z = 3

class WithSlots:
    __slots__ = ("x", "y", "z")
    def __init__(self):
        self.x = 1
        self.y = 2
        self.z = 3

d = WithDict()
s = WithSlots()
print(f"  WithDict instance:  {sys.getsizeof(d) + sys.getsizeof(d.__dict__)} bytes")
print(f"  WithSlots instance: {sys.getsizeof(s)} bytes")
print(f"  HasDict has __dict__: {hasattr(d, '__dict__')} | WithSlots: {hasattr(s, '__dict__')}")


# ═══════════════════════════════════════════════════════
# PART C: weakref — reference without preventing GC
# ═══════════════════════════════════════════════════════

print("\n=== weakref ===")

class LLMSession:
    def __init__(self, session_id: str):
        self.session_id = session_id
        print(f"  [Session] Created: {session_id}")

    def __del__(self):
        print(f"  [Session] Destroyed: {self.session_id}")


# Strong reference — keeps object alive
session = LLMSession("sess_001")
strong_ref = session            # strong reference

# Weak reference — does NOT keep object alive
weak_ref = weakref.ref(session)
print(f"  Weak ref alive: {weak_ref()}")  # returns the object

# Delete strong reference
del session
del strong_ref
gc.collect()                    # force garbage collection
print(f"  Weak ref after GC: {weak_ref()}")  # returns None


# ─────────────────────────────────────────────
# WeakValueDictionary — cache that auto-cleans
# ─────────────────────────────────────────────

class AgentSession:
    def __init__(self, session_id: str, user_id: int):
        self.session_id = session_id
        self.user_id = user_id
        self.messages = []

    def __repr__(self):
        return f"AgentSession({self.session_id})"


# WeakValueDictionary — sessions auto-removed when no longer referenced
session_cache: weakref.WeakValueDictionary = weakref.WeakValueDictionary()

sess1 = AgentSession("sess_A", user_id=1)
sess2 = AgentSession("sess_B", user_id=2)

session_cache["sess_A"] = sess1
session_cache["sess_B"] = sess2

print(f"\nCache size: {len(session_cache)}")  # 2

del sess1           # remove strong reference to sess1
gc.collect()

print(f"Cache after del sess1: {list(session_cache.keys())}")  # only 'sess_B'


# ─────────────────────────────────────────────
# ARCHITECTURE PATTERN — Observer with weakref (no memory leaks)
# ─────────────────────────────────────────────

class EventBus:
    """
    Event bus using weak references to subscribers.
    If subscriber is garbage collected, it's automatically removed.
    Without weakref: memory leak if subscribers forget to unsubscribe.
    """

    def __init__(self):
        self._subscribers: dict[str, list[weakref.ref]] = {}

    def subscribe(self, event: str, handler):
        if event not in self._subscribers:
            self._subscribers[event] = []
        self._subscribers[event].append(weakref.ref(handler))

    def publish(self, event: str, data: Any):
        if event not in self._subscribers:
            return
        alive = []
        for ref in self._subscribers[event]:
            handler = ref()
            if handler is not None:
                handler(data)
                alive.append(ref)
        self._subscribers[event] = alive  # prune dead refs


# ═══════════════════════════════════════════════════════
# PART D: GIL and Memory Management
# ═══════════════════════════════════════════════════════

print("\n=== Python Memory Management ===")

# Reference counting
x = [1, 2, 3]
print(f"Ref count of x: {sys.getrefcount(x)}")  # 2 (x + getrefcount arg)

y = x
print(f"Ref count after y=x: {sys.getrefcount(x)}")  # 3

del y
print(f"Ref count after del y: {sys.getrefcount(x)}")  # 2

# Circular reference — GC handles this, refcount cannot
a: dict = {}
b: dict = {}
a["ref"] = b
b["ref"] = a
del a, b
gc.collect()  # cyclic GC collects this


# ─────────────────────────────────────────────
# INTERVIEW CHEAT SHEET
# ─────────────────────────────────────────────
# GIL           → only 1 thread executes Python bytecode at a time
#                 I/O-bound: threading works (GIL released during I/O)
#                 CPU-bound: multiprocessing needed (separate GIL per process)
#
# Memory management:
#   1. Reference counting (primary)
#   2. Cyclic GC (secondary — handles circular refs)
#   3. gc.collect() — trigger manual GC
#
# weakref use cases:
#   - Caches (WeakValueDictionary)
#   - Observer/event systems
#   - Circular reference avoidance
#   - Session managers
#
# profiling tools:
#   cProfile      — CPU time per function
#   tracemalloc   — memory allocation per line
#   line_profiler — CPU time per LINE (pip install line_profiler)
#   memory_profiler — memory per line (pip install memory_profiler)
#   py-spy        — sampling profiler, no code changes needed
