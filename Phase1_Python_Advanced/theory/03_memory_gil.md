# Python Memory Management & GIL — Complete Guide

---

# PART 1 — THEORY (Deep Concepts)

## 1.1 Python Memory Management — Kaise Kaam Karta Hai

Python memory management do layers mein hoti hai:

```
Layer 1: Reference Counting (primary mechanism)
         ↓ (cyclic references handle nahi hoti)
Layer 2: Cyclic Garbage Collector (secondary — cycles ke liye)
```

### Reference Counting

Har Python object ke saath ek **reference count** hota hai.

```
x = [1, 2, 3]    → list object ka ref_count = 1
y = x             → ref_count = 2
del x             → ref_count = 1
del y             → ref_count = 0 → IMMEDIATELY DEALLOCATED
```

**`sys.getrefcount(obj)`** se check karo — hamesha 1 extra count aata hai (function call ka argument bhi ref hai).

**Advantages:** Deterministic — jaise hi count 0 hota hai, turant memory free.  
**Disadvantage:** Cyclic references handle nahi hoti.

---

## 1.2 Cyclic Garbage Collector

```python
# Problem: Cyclic reference — ref count kabhi 0 nahi hota
class Node:
    def __init__(self):
        self.other = None

a = Node()
b = Node()
a.other = b   # a → b
b.other = a   # b → a (cycle!)

del a
del b
# a ka ref_count = 1 (b.other still points to it)
# b ka ref_count = 1 (a.other still points to it)
# Reference counting fail — memory leak!
```

**Solution: Python ka `gc` module** — cyclic garbage collector.

```
Generation-based collection (3 generations):
  Gen 0: Naye objects — frequently collected (threshold: 700)
  Gen 1: Gen 0 survive karne wale
  Gen 2: Gen 1 survive karne wale — rarely collected

Algorithm: Mark-and-sweep style
  1. Find all objects reachable from roots
  2. Objects with cycles but no external references → collect
```

---

## 1.3 Memory Pools — `pymalloc`

Python har allocation ke liye OS se memory nahi maangta — **memory pools** use karta hai.

```
Object size ≤ 512 bytes → pymalloc (Python's own allocator)
Object size > 512 bytes → malloc (OS level)

pymalloc structure:
  Arena (256 KB)
    └── Pool (4 KB pages)
          └── Block (8, 16, 24, ..., 512 bytes — size classes)

Same size objects → same pool → no fragmentation
```

**Small int cache:** `-5` se `256` tak integers always cached — same object reuse hota hai.  
**String interning:** Short strings aur identifiers automatically interned (shared).

---

## 1.4 GIL — Global Interpreter Lock

**GIL** = ek mutex lock jo ensure karta hai ki ek waqt mein sirf ek thread Python bytecode execute kare.

```
Thread 1:  acquire GIL → execute → release GIL
Thread 2:  wait --------→ acquire GIL → execute → release
Thread 3:  wait ----wait --------→ acquire GIL → execute
```

**Kyun hai GIL?**
- CPython ke internal data structures (reference counts, dicts) thread-safe nahi hain
- GIL unhe protect karta hai — simplicity ke liye performance trade-off

---

## 1.5 GIL ka Impact — I/O vs CPU

```
I/O-bound tasks (file read, network, sleep):
  Thread blocks karte waqt GIL release hota hai!
  → Threading USEFUL hai — threads switch kar sakte hain

CPU-bound tasks (computation, loops, math):
  GIL release nahi hota jab tak execution active hai
  → Threading USELESS for parallelism
  → Multiprocessing use karo — separate process = separate GIL
```

---

## 1.6 Memory Optimization Techniques

```
1. __slots__:
   Normal class: har instance dict store karta hai → overhead
   With __slots__: fixed attributes, no dict → 30-50% memory save

2. generators vs lists:
   List: sab values memory mein at once
   Generator: ek ek value on demand — O(1) memory

3. weakref:
   Normal reference: ref count badhata hai
   Weak reference: ref count nahi badhata → GC collect kar sakta hai

4. del + gc.collect():
   Large objects manually delete karo → gc cycle trigger karo

5. array vs list:
   list[int]: each int = Python object (28 bytes each)
   array.array('i'): C-level int (4 bytes each) — 7x memory save

6. numpy arrays:
   Homogeneous data → C arrays internally → very memory efficient
```

---

## 1.7 Shallow vs Deep Copy

```
Assignment (=):   Same object, same reference — no copy at all
Shallow copy:     New container, same nested objects (shared)
Deep copy:        New container + new nested objects (fully independent)

original = {"a": [1, 2, 3]}

# Assignment
ref = original
ref["a"].append(4)    → original["a"] = [1, 2, 3, 4]  (same object!)

# Shallow copy
shallow = original.copy()
shallow["a"].append(4)  → original["a"] ALSO changes! (nested list shared)

# Deep copy
deep = copy.deepcopy(original)
deep["a"].append(4)   → original["a"] unchanged (fully independent)
```

---

# PART 2 — PRACTICAL (Working Code)

## 2.1 Reference Counting — Direct Observation

```python
import sys
import gc

# Basic reference counting
x = [1, 2, 3]
print(sys.getrefcount(x))   # 2 (x + function arg)

y = x
print(sys.getrefcount(x))   # 3 (x, y, + function arg)

z = x
print(sys.getrefcount(x))   # 4

del y
print(sys.getrefcount(x))   # 3

del z
print(sys.getrefcount(x))   # 2

# Small int cache — same object
a = 100
b = 100
print(a is b)   # True — same object (cached)

c = 1000
d = 1000
print(c is d)   # False — different objects (not cached, >256)

# String interning
s1 = "hello"
s2 = "hello"
print(s1 is s2)   # True — interned (short string)

s3 = "hello world! this is long"
s4 = "hello world! this is long"
print(s3 is s4)   # False — not interned
```

---

## 2.2 Cyclic Reference + GC

```python
import gc
import weakref

# --- Demonstrate cycle problem ---
class Node:
    def __init__(self, name: str):
        self.name = name
        self.other: "Node | None" = None

    def __del__(self):
        print(f"Node '{self.name}' destroyed")

# Create cycle
gc.disable()   # disable automatic GC to demonstrate

a = Node("A")
b = Node("B")
a.other = b
b.other = a   # cycle!

del a
del b
# Neither "Node A destroyed" nor "Node B destroyed" printed yet
# ref counts not 0 due to cycle

print("Manually running GC...")
collected = gc.collect()
print(f"Objects collected: {collected}")
# Now: "Node A destroyed", "Node B destroyed"

gc.enable()

# --- GC stats ---
print(gc.get_count())       # (gen0_count, gen1_count, gen2_count)
print(gc.get_threshold())   # (700, 10, 10) — default thresholds

# --- Force collection ---
gc.collect(generation=0)   # gen0 only (fastest)
gc.collect(generation=2)   # full collection (slowest)
```

---

## 2.3 `__slots__` — Memory Optimization

```python
import sys

# Normal class — each instance has __dict__
class PointNormal:
    def __init__(self, x: float, y: float, z: float):
        self.x = x
        self.y = y
        self.z = z

# With __slots__ — no __dict__, fixed attributes
class PointSlots:
    __slots__ = ("x", "y", "z")

    def __init__(self, x: float, y: float, z: float):
        self.x = x
        self.y = y
        self.z = z

# Memory comparison
pn = PointNormal(1.0, 2.0, 3.0)
ps = PointSlots(1.0, 2.0, 3.0)

print(f"Normal:  {sys.getsizeof(pn)} bytes + {sys.getsizeof(pn.__dict__)} dict")
# Normal:  48 bytes + 104 dict  →  total ~152 bytes

print(f"Slots:   {sys.getsizeof(ps)} bytes (no dict)")
# Slots:   56 bytes — no __dict__

# Slots restricts dynamic attribute addition
try:
    ps.w = 4.0   # AttributeError!
except AttributeError as e:
    print(e)     # 'PointSlots' object has no attribute 'w'

# --- Real impact: 1 million objects ---
import tracemalloc

tracemalloc.start()

# Normal
objects_normal = [PointNormal(i, i*2, i*3) for i in range(100_000)]
snap1 = tracemalloc.take_snapshot()

del objects_normal

# Slots
objects_slots = [PointSlots(i, i*2, i*3) for i in range(100_000)]
snap2 = tracemalloc.take_snapshot()

stats = snap2.statistics("lineno")
print(f"Memory for 100K objects with slots: {stats[0].size / 1024:.1f} KB")
```

---

## 2.4 `weakref` — Weak References

```python
import weakref
import gc

class HeavyObject:
    def __init__(self, data: list):
        self.data = data
        print(f"HeavyObject created, size: {len(data)}")

    def __del__(self):
        print("HeavyObject destroyed!")

# Normal reference — ref count badhta hai
obj = HeavyObject([1] * 1_000_000)
ref1 = obj          # ref count = 2

# Weak reference — ref count NAHI badhta
weak_ref = weakref.ref(obj)

print(f"Object alive: {weak_ref() is not None}")  # True
print(f"Accessing: {type(weak_ref())}")            # <class 'HeavyObject'>

# Cleanup — only strong ref 'obj' deleted
del obj
del ref1
# ref count → 0 → destroyed! (weakref doesn't prevent it)

print(f"After del, ref alive: {weak_ref() is not None}")  # False
print(f"Weak ref value: {weak_ref()}")                     # None

# --- WeakValueDictionary — cache jo memory free karne deta hai ---
import weakref

class ExpensiveResource:
    def __init__(self, name: str):
        self.name = name

# Normal dict — GC kabhi collect nahi karega (dict holds strong ref)
normal_cache: dict[str, ExpensiveResource] = {}

# Weak value dict — GC collect kar sakta hai when no other references
weak_cache: weakref.WeakValueDictionary[str, ExpensiveResource] = weakref.WeakValueDictionary()

resource = ExpensiveResource("db_connection")
weak_cache["db"] = resource
normal_cache["db"] = resource

print(f"In weak_cache: {'db' in weak_cache}")  # True

del resource   # remove external reference

gc.collect()
print(f"In weak_cache after del: {'db' in weak_cache}")   # False (GC collected it)
print(f"In normal_cache after del: {'db' in normal_cache}") # True (dict holds ref)
```

---

## 2.5 GIL — Threading vs Multiprocessing

```python
import threading
import multiprocessing
import time

def cpu_bound_task(n: int) -> int:
    """Pure CPU work — GIL blocks other threads."""
    count = 0
    for i in range(n):
        count += i * i
    return count

def io_bound_task(seconds: float):
    """I/O wait — GIL released during sleep."""
    time.sleep(seconds)

# --- I/O bound: Threading wins ---
print("=== I/O Bound: Threading ===")
start = time.perf_counter()

threads = [threading.Thread(target=io_bound_task, args=(0.5,)) for _ in range(4)]
for t in threads: t.start()
for t in threads: t.join()

print(f"4 threads, 0.5s each: {time.perf_counter() - start:.2f}s")
# ~0.5s — all run concurrently (GIL released during sleep)

# --- CPU bound: Threading fails, Multiprocessing wins ---
print("\n=== CPU Bound: Multiprocessing ===")
N = 5_000_000

# Threading (serial due to GIL)
start = time.perf_counter()
threads = [threading.Thread(target=cpu_bound_task, args=(N,)) for _ in range(4)]
for t in threads: t.start()
for t in threads: t.join()
threading_time = time.perf_counter() - start
print(f"Threading (4 threads): {threading_time:.2f}s")
# ~2.0s — GIL prevents true parallelism

# Multiprocessing (true parallel — separate GIL per process)
start = time.perf_counter()
with multiprocessing.Pool(4) as pool:
    pool.map(cpu_bound_task, [N] * 4)
mp_time = time.perf_counter() - start
print(f"Multiprocessing (4 procs): {mp_time:.2f}s")
# ~0.5s — 4x speedup on 4 cores
```

---

## 2.6 Memory Profiling — `tracemalloc` + `memory_profiler`

```python
import tracemalloc
import sys

# --- tracemalloc: track allocations ---
tracemalloc.start()

# Do some work
data = [i ** 2 for i in range(100_000)]

snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics("lineno")

print("Top memory allocations:")
for stat in top_stats[:3]:
    print(f"  {stat}")

current, peak = tracemalloc.get_traced_memory()
print(f"\nCurrent: {current / 1024:.1f} KB")
print(f"Peak:    {peak / 1024:.1f} KB")
tracemalloc.stop()

# --- sys.getsizeof — object size ---
print(f"\nList of 1000 ints: {sys.getsizeof([0]*1000)} bytes")
print(f"Single int:        {sys.getsizeof(0)} bytes")
print(f"Empty list:        {sys.getsizeof([])} bytes")
print(f"Empty dict:        {sys.getsizeof({})} bytes")
print(f"Empty string:      {sys.getsizeof('')} bytes")

# Note: sys.getsizeof is SHALLOW — nested objects ka size nahi deta
import json
nested = {"a": [1, 2, 3], "b": {"c": 4}}
print(f"\nNested dict shallow: {sys.getsizeof(nested)} bytes")  # ~232

# Deep size calculation
def deep_size(obj, seen=None):
    """Recursively calculate total object size."""
    if seen is None:
        seen = set()
    obj_id = id(obj)
    if obj_id in seen:
        return 0
    seen.add(obj_id)
    size = sys.getsizeof(obj)
    if isinstance(obj, dict):
        size += sum(deep_size(k, seen) + deep_size(v, seen) for k, v in obj.items())
    elif isinstance(obj, (list, tuple, set)):
        size += sum(deep_size(i, seen) for i in obj)
    return size

print(f"Nested dict deep:   {deep_size(nested)} bytes")
```

---

## 2.7 Shallow vs Deep Copy — Practical

```python
import copy

original = {
    "name": "Ashish",
    "scores": [95, 87, 92],
    "address": {"city": "Mumbai", "pin": "400001"}
}

# Assignment — same object
ref = original
ref["name"] = "Changed"
print(original["name"])   # "Changed" — same object!

# Shallow copy — new dict, shared nested objects
original["name"] = "Ashish"  # restore
shallow = original.copy()    # or: copy.copy(original)

shallow["name"] = "Bob"         # top-level: independent
shallow["scores"].append(100)   # nested: SHARED — both change!
shallow["address"]["city"] = "Delhi"   # nested: SHARED

print(original["name"])           # "Ashish" — not affected (top-level)
print(original["scores"])         # [95, 87, 92, 100] — AFFECTED!
print(original["address"]["city"])  # "Delhi" — AFFECTED!

# Deep copy — fully independent
original = {"name": "Ashish", "scores": [95, 87, 92],
            "address": {"city": "Mumbai", "pin": "400001"}}

deep = copy.deepcopy(original)
deep["name"] = "Charlie"
deep["scores"].append(100)
deep["address"]["city"] = "Pune"

print(original["name"])             # "Ashish" — safe
print(original["scores"])           # [95, 87, 92] — safe
print(original["address"]["city"])  # "Mumbai" — safe

# When to use what:
# Assignment: intentional aliasing (same object chahiye)
# Shallow:    flat structures, or nested won't change
# Deep:       nested mutable objects, truly independent copy chahiye
```

---

## 2.8 Interview Q&A

**Q1: Python mein memory management kaise hoti hai?**
> Two mechanisms: (1) Reference counting — har object ka ref count maintain hota hai, 0 hone par turant deallocate. (2) Cyclic GC — cycles detect karta hai jo ref counting miss kar deta hai. `gc` module generation-based collection karta hai (gen0 → gen1 → gen2). `pymalloc` small objects ke liye OS bypass karta hai — memory pools use karta hai.

**Q2: GIL kya hai aur kyun exist karta hai?**
> GIL (Global Interpreter Lock) = CPython ka mutex jo ensure karta hai ek waqt mein sirf ek thread Python bytecode execute kare. Exist isliye karta hai kyunki CPython ke internals (reference counts, dict operations) thread-safe nahi hain. GIL inhe protect karta hai. Tradeoff: simplicity + C extension safety vs. CPU-bound threading limitations.

**Q3: GIL bypass kaise karein?**
> (1) Multiprocessing: separate processes = separate GIL — true parallelism for CPU-bound. (2) C extensions like NumPy — GIL release karte hain computation ke dauran. (3) asyncio — I/O bound ke liye single-thread cooperative multitasking. (4) PyPy — different GIL implementation. (5) Python 3.13+ — nogil experimental mode.

**Q4: `__slots__` kab use karein?**
> Jab bahut saare instances banane hों (100K+) aur attributes fixed hoin. `__slots__` `__dict__` remove karta hai — 30-50% memory save. Drawbacks: dynamic attribute add nahi kar sakte, multiple inheritance tricky ho jati hai, pickling me issues aa sakte hain. Use case: data classes, point/vector classes, high-frequency objects.

**Q5: weakref kab use karein?**
> Jab circular reference ka risk ho aur tum chahte ho GC freely collect kare. Common use: cache jo memory pressure mein automatically entries drop kare (`WeakValueDictionary`). Observer pattern mein observers weak references se hold karo — agar observer delete ho gaya, callback automatically remove ho. Event systems mein useful.
