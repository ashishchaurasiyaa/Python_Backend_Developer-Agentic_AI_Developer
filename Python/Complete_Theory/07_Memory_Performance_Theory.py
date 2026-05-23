"""
╔══════════════════════════════════════════════════════════════════════════════╗
║   PYTHON COMPLETE THEORY — File 07                                           ║
║   Topic: Memory Management & Performance Optimization                        ║
║   Format: WHAT → WHY → HOW → REAL LIFE → PRODUCTION CODE → Q&A              ║
╚══════════════════════════════════════════════════════════════════════════════╝

Topics Covered:
  A. Python Memory Model — variables as references
  B. Reference Counting — primary garbage collection
  C. Cyclic Garbage Collector — handling circular references
  D. Object Interning — CPython optimizations (small ints, strings)
  E. __slots__ — reduce per-instance memory footprint
  F. weakref — reference without preventing GC
  G. Memory profiling — tracemalloc, sys.getsizeof
  H. CPU profiling — cProfile, timeit, dis module
  I. Performance optimization tips — 10 key techniques
  J. Memory-efficient patterns — generators vs lists
"""

import sys
import gc
import weakref
import time
import dis
import io
import tracemalloc
import cProfile
import pstats
import functools
from typing import Any


# ══════════════════════════════════════════════════════════════════════════════
# PART A: PYTHON MEMORY MODEL
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS PYTHON'S MEMORY MODEL?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Python variables are NOT boxes that hold data.
They are LABELS (references/pointers) that point to OBJECTS in memory.

The OBJECT lives in the heap — the variable is just a name pointing to it.

  a = [1, 2, 3]          Memory layout:
  b = a                  ┌────────────────────────────────────────────┐
                         │  HEAP                                      │
                         │                                            │
  Stack/Namespace:       │    ┌─────────────────────┐                │
  ┌──────┐               │    │ list object          │                │
  │ a ───┼───────────────┼──→ │  [1, 2, 3]           │ ← refcount=2  │
  └──────┘               │    │                     │                │
  ┌──────┐               │    └─────────────────────┘                │
  │ b ───┼───────────────┼──────────────↑ (same object!)             │
  └──────┘               │                                            │
                         └────────────────────────────────────────────┘

  b = a  → b points to the SAME list object (refcount becomes 2)
  b is a → True  (same object, same memory address)
  b == a → True  (same values)

CONSEQUENCES:
  a = [1, 2, 3]
  b = a
  b.append(4)     # mutates THE SAME OBJECT
  print(a)        # [1, 2, 3, 4] ← 'a' sees the change!

  To avoid this: b = a.copy() or b = list(a) or b = a[:]

IMMUTABLE vs MUTABLE in memory:
  int/str/tuple: immutable — "changing" creates a NEW object, old is untouched
    x = 5; y = x; x = 10   → y still points to 5 (new object 10 created)

  list/dict/set: mutable — "changing" modifies THE SAME OBJECT in place
    a = [1]; b = a; a.append(2)  → b sees the change!

EVERYTHING IS AN OBJECT:
  Even functions, classes, modules are objects in Python's heap.
  int, float, str, list, dict, function → all live in the heap.

REAL LIFE ANALOGY:
  Variables are like name tags on people:
  a = Person(name="Alice")  → stick name tag "a" on Alice
  b = a                     → stick name tag "b" also on Alice
  Now both 'a' and 'b' refer to the SAME person.
  If Alice changes her hair: both a.hair and b.hair changed!
  "Deleting a" just removes one name tag — Alice still exists.
"""

print("=== Python Memory Model ===")

a = [1, 2, 3]
b = a             # b points to SAME list
b.append(4)
print(f"a after b.append(4): {a}")  # [1, 2, 3, 4]  ← same object!

# id() returns the memory address
print(f"id(a): {id(a)}")
print(f"id(b): {id(b)}")
print(f"a is b: {a is b}")  # True — same object

# Immutable: reassignment creates NEW object
x = 5
y = x
x = 10           # new int object — y unchanged
print(f"\nx={x}, y={y}")   # x=10, y=5
print(f"id(x): {id(x)}, id(y): {id(y)}")  # different addresses


# ══════════════════════════════════════════════════════════════════════════════
# PART B: REFERENCE COUNTING
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS REFERENCE COUNTING?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CPython's PRIMARY garbage collection mechanism.
Every object has a REFERENCE COUNT — how many variables point to it.

When refcount reaches ZERO → object is IMMEDIATELY freed.

HOW:
  Refcount INCREASES when:
    - Variable assigned: a = obj          (a points to obj → refcount++)
    - Copied: b = a                       (another reference → refcount++)
    - Added to container: lst.append(obj) (container holds reference → refcount++)
    - Passed to function: func(obj)       (param holds reference → refcount++)

  Refcount DECREASES when:
    - del a                               (name removed → refcount--)
    - a = other_obj                       (a re-pointed → refcount--)
    - Function returns                    (local param gone → refcount--)
    - Container item removed              (refcount--)

sys.getrefcount(obj) adds 1 (the argument reference itself), so result is always +1.

ADVANTAGES:
  - Immediate deallocation — as soon as refcount=0, memory freed RIGHT AWAY
  - Predictable: no GC pause surprises
  - Simpler than tracing GC

DISADVANTAGE:
  - CANNOT handle circular references (a→b→a, both have refcount ≥ 1 always)
  - Python's cyclic GC handles this (Part C)

REAL LIFE ANALOGY:
  Refcount = Number of people who have the key to a safe:
  Safe stays accessible as long as at least 1 person has a key.
  When last person returns their key (refcount=0): safe is destroyed.
"""

print("\n=== Reference Counting ===")

lst = [1, 2, 3]
print(f"After lst = [1,2,3]: refcount = {sys.getrefcount(lst)}")   # 2 (lst + getrefcount arg)

a = lst    # another reference
print(f"After a = lst: refcount = {sys.getrefcount(lst)}")         # 3

container = [lst, lst, lst]  # 3 more references
print(f"After container = [lst,lst,lst]: refcount = {sys.getrefcount(lst)}")  # 6

del a
print(f"After del a: refcount = {sys.getrefcount(lst)}")           # 5

del container
print(f"After del container: refcount = {sys.getrefcount(lst)}")   # 2 (back to lst + getrefcount)

# When refcount reaches 0 — object freed
class Tracked:
    def __init__(self, name: str):
        self.name = name
        print(f"  [Created] {name}")
    def __del__(self):
        print(f"  [Freed]   {self.name}")

print(f"\nLifecycle demo:")
obj = Tracked("T1")         # refcount = 1
ref2 = obj                  # refcount = 2
del obj                     # refcount = 1 — NOT freed yet
print(f"  (T1 still alive — ref2 holds it)")
del ref2                    # refcount = 0 → FREED immediately


# ══════════════════════════════════════════════════════════════════════════════
# PART C: CYCLIC GARBAGE COLLECTOR
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS THE CYCLIC GARBAGE COLLECTOR?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Reference counting FAILS for circular references:

  a = Node()
  b = Node()
  a.next = b    → refcount(b) = 1
  b.next = a    → refcount(a) = 1  ← CIRCULAR! both have refcount ≥ 1

  del a → refcount(a) = 0? NO → b.next still points to a → refcount(a) = 1
  del b → refcount(b) = 0? NO → a.next still points to b → refcount(b) = 1
  Memory leak! Both objects will never be freed by refcount alone.

Python's CYCLIC GARBAGE COLLECTOR:
  - Uses a MARK-AND-SWEEP type algorithm
  - Periodically looks for objects that are only referenced BY EACH OTHER
    (forming isolated cycles with no external references)
  - Frees these "cycle islands" that refcount can't handle

THREE GENERATIONS (generational GC):
  New objects → Gen 0 → (survive?) → Gen 1 → (survive?) → Gen 2
  More frequently collect Gen 0 (newly created, likely short-lived)
  Less frequently collect Gen 2 (long-lived, likely still needed)

  gc.get_threshold() → (700, 10, 10)
    Gen 0: collect when 700 objects created since last Gen 0 collection
    Gen 1: collect when Gen 0 collected 10 times since last Gen 1 collection
    Gen 2: collect when Gen 1 collected 10 times

HOW TO USE:
  import gc
  gc.collect()            # force collection of all generations
  gc.collect(0)           # collect only Gen 0
  gc.disable()            # disable GC (if you're careful about cycles)
  gc.enable()             # re-enable
  gc.get_threshold()      # current thresholds
  gc.set_threshold(700, 10, 10)  # change thresholds

REAL LIFE ANALOGY:
  Cyclic GC = City trash collection for "orphaned communities":
  Refcount = Individual household that calls when done: "I'm done with this!"
  Cyclic GC = City inspector who periodically checks: "Is this neighborhood
              still connected to the rest of the city? No? Demolish it."
"""

print("\n=== Cyclic Garbage Collector ===")


class Node:
    def __init__(self, value: int):
        self.value = value
        self.next: "Node | None" = None
        print(f"  [Node.__init__] value={value}")

    def __del__(self):
        print(f"  [Node.__del__]  value={self.value}")


# Create circular reference
n1 = Node(1)
n2 = Node(2)
n1.next = n2   # n1 → n2
n2.next = n1   # n2 → n1 (CIRCULAR!)

del n1, n2     # refcounts don't reach 0 — NOT freed by refcount alone!

print(f"\nBefore gc.collect() — circular nodes NOT freed yet")
collected = gc.collect()
print(f"gc.collect() freed: {collected} objects")   # 2 (the circular nodes)

print(f"\nGC thresholds: {gc.get_threshold()}")
print(f"GC stats: {gc.get_stats()}")


# ══════════════════════════════════════════════════════════════════════════════
# PART D: OBJECT INTERNING
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS OBJECT INTERNING?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CPython REUSES (interns) certain objects for performance.
Instead of creating new objects for common values, it returns the SAME object.

SMALL INTEGER CACHE: Python pre-creates int objects for -5 to 256.
  a = 100; b = 100   → a is b → True  (same cached object)
  a = 300; b = 300   → a is b → False (outside range, different objects)

STRING INTERNING:
  Python automatically interns "identifier-like" strings (alphanumeric, no spaces).
  sys.intern() forces interning of any string.
  Interned strings: identity comparison is O(1) instead of O(n) character comparison.

WHY DOES IT MATTER?
  Performance: "word" is "word" → instant True (pointer comparison, O(1))
               vs "word" == "word" → character-by-character comparison (O(n))
  Memory: 257 copies of 100 → only 1 object in memory!

WARNING:
  Never use `is` to compare values — only for identity checks (None, True, False).
  The int cache is an implementation detail that can change.
  x = 256; y = 256; x is y  → True (cached)
  x = 257; y = 257; x is y  → False (not cached — DIFFERENT runs may differ!)
"""

print("\n=== Object Interning ===")

# Integer caching: -5 to 256
a, b = 100, 100
print(f"a=100, b=100 → a is b: {a is b}")  # True (cached)

c, d = 1000, 1000
print(f"c=1000, d=1000 → c is d: {c is d}")  # False (not cached)

# None, True, False — always singletons
x = None
print(f"x is None: {x is None}")   # True — CORRECT way to check None
print(f"True is True: {True is True}")   # True — singletons

# String interning
s1 = "hello"
s2 = "hello"
print(f"\n's1 is s2' (both 'hello'): {s1 is s2}")  # True (auto-interned)

s3 = "hello world"   # has space — may not be auto-interned
s4 = "hello world"
print(f"'hello world' is 'hello world': {s3 is s4}")  # True or False depending on Python version

# Force interning with sys.intern
s5 = sys.intern("this is a long string that won't be auto-interned normally")
s6 = sys.intern("this is a long string that won't be auto-interned normally")
print(f"After sys.intern: s5 is s6: {s5 is s6}")  # True — forced same object


# ══════════════════════════════════════════════════════════════════════════════
# PART E: __slots__ — REDUCE MEMORY FOOTPRINT
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT ARE __slots__?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

By default, every Python object has a __dict__ dictionary for attributes.
This is flexible but EXPENSIVE in memory (each instance carries its own dict).

__slots__ = declare attribute names at class level → NO __dict__ per instance.
Instead, attributes use a fixed-size ARRAY (like C struct).

WHY?
  With __dict__:    50-100 bytes overhead per instance JUST for the dict
  With __slots__:   No dict overhead → ~30-50% memory reduction

  For 1 MILLION instances: easily save 50-100 MB of RAM.

HOW:
  class WithSlots:
      __slots__ = ("x", "y", "z")   # declare allowed attributes

      def __init__(self, x, y, z):
          self.x = x                 # stored in fixed array
          self.y = y                 # stored in fixed array
          self.z = z                 # stored in fixed array

  Restrictions:
    - Can't add NEW attributes not in __slots__: obj.new_attr = 1 → AttributeError
    - No __dict__ → can't use vars(obj), obj.__dict__
    - To still have __dict__: add "__dict__" to __slots__
    - Inheritance: parent must also use __slots__ for full benefit

WHEN TO USE:
  ✅ Many instances (thousands, millions): Token, Coordinate, DataPoint, ChatMessage
  ✅ Data-heavy classes (AI embeddings, time series)
  ✅ Performance-critical inner loops
  ❌ Few instances (overhead not worth it)
  ❌ Need dynamic attribute addition
  ❌ Need pickle/copy without extra setup

REAL LIFE ANALOGY:
  Without __slots__ = renting a flexible office with unlimited rooms (expensive)
  With __slots__    = a fixed desk with only the drawers you declared (cheaper, faster)
"""

print("\n=== __slots__ ===")


class WithDict:
    def __init__(self, x: int, y: int, z: int, w: int):
        self.x = x
        self.y = y
        self.z = z
        self.w = w

    def magnitude(self) -> float:
        return (self.x**2 + self.y**2 + self.z**2 + self.w**2) ** 0.5


class WithSlots:
    __slots__ = ("x", "y", "z", "w")

    def __init__(self, x: int, y: int, z: int, w: int):
        self.x = x
        self.y = y
        self.z = z
        self.w = w

    def magnitude(self) -> float:
        return (self.x**2 + self.y**2 + self.z**2 + self.w**2) ** 0.5


n = 100_000

# Memory comparison
d_obj = WithDict(1, 2, 3, 4)
s_obj = WithSlots(1, 2, 3, 4)

d_size = sys.getsizeof(d_obj) + sys.getsizeof(d_obj.__dict__)
s_size = sys.getsizeof(s_obj)

print(f"WithDict size:  {d_size} bytes (object + __dict__)")
print(f"WithSlots size: {s_size} bytes (no __dict__)")
print(f"Savings per instance: {d_size - s_size} bytes")
print(f"Savings for {n:,} instances: {(d_size - s_size) * n / 1024 / 1024:.1f} MB")

# Timing comparison
start = time.perf_counter()
dict_objects = [WithDict(i, i, i, i) for i in range(n)]
dict_time = time.perf_counter() - start

start = time.perf_counter()
slot_objects = [WithSlots(i, i, i, i) for i in range(n)]
slot_time = time.perf_counter() - start

print(f"\nCreation time ({n:,} objects):")
print(f"  WithDict:   {dict_time*1000:.1f}ms")
print(f"  WithSlots:  {slot_time*1000:.1f}ms")
print(f"  Speedup:    {dict_time/slot_time:.2f}x")

# Attempt to add dynamic attribute (will fail for slots)
try:
    s_obj.new_attr = "hello"
except AttributeError as e:
    print(f"\n__slots__ restriction: {e}")

# Inheritance with __slots__
class Point2D:
    __slots__ = ("x", "y")
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y

class Point3D(Point2D):
    __slots__ = ("z",)   # only add NEW slots in child
    def __init__(self, x: float, y: float, z: float):
        super().__init__(x, y)
        self.z = z

p3 = Point3D(1.0, 2.0, 3.0)
print(f"\nInheritance with slots: Point3D({p3.x}, {p3.y}, {p3.z})")


# ══════════════════════════════════════════════════════════════════════════════
# PART F: weakref — REFERENCES WITHOUT PREVENTING GC
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS weakref?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

weakref = A reference to an object that does NOT increase its refcount.
The object can still be GC'd even if a weakref exists.

WHY?
  Caches with automatic expiration:
    You cache some objects. But you don't want the CACHE to prevent objects
    from being freed. When the original owner deletes the object,
    the cache should automatically expire (not hold a "dead" reference).

  Avoiding circular references in observer/callback patterns:
    Parent holds weak ref to child → parent doesn't prevent child's GC.

HOW:
  weak = weakref.ref(obj)  → creates weak reference
  obj_back = weak()        → dereference: returns obj or None if GC'd

  WeakValueDictionary: dict where VALUES are weakrefs
                        keys auto-removed when value is GC'd
  WeakKeyDictionary:   dict where KEYS are weakrefs
                        entries auto-removed when key is GC'd
  WeakSet:             set of weakrefs — auto-removes GC'd items

LIMITATIONS:
  Not all objects support weakref (int, str, tuple don't by default).
  Classes can support it by NOT using __slots__, or adding '__weakref__' to __slots__.

REAL LIFE ANALOGY:
  weakref = Subscription newsletter:
  - Publisher (object) lives independently
  - Subscriber (weakref holder) gets updates while publisher exists
  - If publisher shuts down (GC'd) → newsletter auto-cancelled
  - Subscriber doesn't keep publisher alive just by subscribing
"""

print("\n=== weakref ===")


class LLMSession:
    def __init__(self, session_id: str):
        self.session_id = session_id
        print(f"  [Session] Created: {session_id}")

    def get_context(self) -> str:
        return f"Context of {self.session_id}"

    def __del__(self):
        print(f"  [Session] Destroyed: {self.session_id}")


# Basic weak reference
sess = LLMSession("sess_001")
weak = weakref.ref(sess)

print(f"Before del: weak() = {weak()!r}")  # LLMSession object
print(f"Session id: {weak().session_id}")

del sess
gc.collect()  # force GC (though refcount should handle it immediately)
print(f"After del: weak() = {weak()}")   # None — object freed


# WeakValueDictionary — session cache
print(f"\nWeakValueDictionary cache:")
session_cache: weakref.WeakValueDictionary = weakref.WeakValueDictionary()

s1 = LLMSession("sess_A")
s2 = LLMSession("sess_B")
session_cache["sess_A"] = s1
session_cache["sess_B"] = s2

print(f"Cache keys: {list(session_cache.keys())}")

del s1  # session A freed
gc.collect()

print(f"After del s1 — Cache keys: {list(session_cache.keys())}")  # only sess_B

s2_via_cache = session_cache.get("sess_B")
print(f"s2 via cache: {s2_via_cache}")
del s2
gc.collect()

print(f"After del s2 — Cache keys: {list(session_cache.keys())}")  # empty


# ══════════════════════════════════════════════════════════════════════════════
# PART G: MEMORY PROFILING
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MEMORY PROFILING TOOLS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. sys.getsizeof(obj) — size of the object ITSELF (shallow, not contents)
   Does NOT include size of nested objects.

2. tracemalloc — line-by-line memory allocation tracking
   Shows WHERE memory was allocated, what's using the most.

3. memory_profiler (pip install) — line-by-line @profile decorator

COMMON OBJECT SIZES:
  ┌────────────────────┬──────────────┐
  │ Object             │ Approx Size  │
  ├────────────────────┼──────────────┤
  │ None               │  16 bytes    │
  │ True / False       │  28 bytes    │
  │ int (small)        │  28 bytes    │
  │ int (big)          │  varies      │
  │ float              │  24 bytes    │
  │ str (empty)        │  49 bytes    │
  │ str (10 chars)     │  59 bytes    │
  │ list (empty)       │  56 bytes    │
  │ list (10 items)    │ 136 bytes    │
  │ dict (empty)       │ 216 bytes    │
  │ tuple (empty)      │  40 bytes    │
  │ set (empty)        │ 216 bytes    │
  └────────────────────┴──────────────┘

NOTE: sys.getsizeof(list_with_10_items) only counts the LIST structure.
      The 10 items themselves are NOT counted (they have their own size).
      For deep size: write a recursive sizeof or use pympler.
"""

print("\n=== Memory Profiling ===")

# sys.getsizeof
objects = [
    ("None",         None),
    ("True",         True),
    ("int (0)",      0),
    ("int (1000)",   1000),
    ("float",        3.14),
    ("str (empty)",  ""),
    ("str ('hello')", "hello"),
    ("list (empty)", []),
    ("list (10)",    list(range(10))),
    ("dict (empty)", {}),
    ("dict (10)",    {i: i for i in range(10)}),
    ("tuple (10)",   tuple(range(10))),
    ("set (10)",     set(range(10))),
]

print("Object sizes (sys.getsizeof):")
for name, obj in objects:
    size = sys.getsizeof(obj)
    print(f"  {name:<25}: {size:>5} bytes")


# tracemalloc — track allocations by line
print(f"\ntracemalloc demo:")
tracemalloc.start()

# Simulated memory-intensive operation
conversation_histories = [
    [{"role": "user", "content": "x" * 100} for _ in range(50)]
    for _ in range(100)
]

snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics("lineno")

print(f"Top 3 memory allocations:")
for stat in top_stats[:3]:
    print(f"  {stat}")

tracemalloc.stop()
del conversation_histories


# ══════════════════════════════════════════════════════════════════════════════
# PART H: CPU PROFILING
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CPU PROFILING TOOLS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. cProfile — standard library, low overhead, production-safe
   Shows: how many times each function called, cumulative time, per-call time

2. time.perf_counter() — high-resolution timer for microbenchmarks

3. timeit module — repeat benchmarks for statistical accuracy

4. dis module — inspect bytecode to understand low-level performance

5. py-spy (pip install) — flame graph profiler, no code modification needed

PROFILING METHODOLOGY:
  MEASURE FIRST → IDENTIFY BOTTLENECK → OPTIMIZE → MEASURE AGAIN

  Common mistake: optimize by intuition without measuring first.
  "Premature optimization is the root of all evil" — Donald Knuth
"""

print("\n=== CPU Profiling (cProfile) ===")


def slow_fib(n: int) -> int:
    """Naive fibonacci — exponential time O(2^n)."""
    if n < 2:
        return n
    return slow_fib(n - 1) + slow_fib(n - 2)


@functools.lru_cache(maxsize=None)
def fast_fib(n: int) -> int:
    """Memoized fibonacci — O(n) time, O(n) space."""
    if n < 2:
        return n
    return fast_fib(n - 1) + fast_fib(n - 2)


# Profile slow_fib(25)
stream = io.StringIO()
pr = cProfile.Profile()
pr.enable()
result = slow_fib(25)
pr.disable()

ps = pstats.Stats(pr, stream=stream)
ps.sort_stats("cumulative")
ps.print_stats(5)
print(stream.getvalue())

# Timing comparison
start = time.perf_counter()
r1 = slow_fib(30)
slow_time = time.perf_counter() - start

start = time.perf_counter()
r2 = fast_fib(30)
fast_time = time.perf_counter() - start

print(f"slow_fib(30): {slow_time*1000:.2f}ms")
print(f"fast_fib(30): {fast_time*1000:.4f}ms")
print(f"Speedup: {slow_time/fast_time:,.0f}x")


# dis module — inspect bytecode
print(f"\n=== dis module (bytecode) ===")


def add_numbers(a, b):
    return a + b


def add_with_local(n: int) -> float:
    """Shows local variable optimization."""
    import math
    local_sqrt = math.sqrt   # local variable — faster lookup
    result = 0.0
    for i in range(n):
        result += local_sqrt(i)
    return result


print(f"Bytecode for add_numbers(a, b):")
dis.dis(add_numbers)


# ══════════════════════════════════════════════════════════════════════════════
# PART I: PERFORMANCE OPTIMIZATION TIPS
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TOP 10 PYTHON PERFORMANCE TIPS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

print("\n=== Performance Tips ===")

N = 100_000

# TIP 1: Local variables faster than global lookup
import math

def slow_global(n: int) -> float:
    """Global math.sqrt lookup every iteration."""
    return sum(math.sqrt(i) for i in range(n))

def fast_local(n: int) -> float:
    """Local reference — one lookup, then fast."""
    sqrt = math.sqrt    # cache in local variable
    return sum(sqrt(i) for i in range(n))

start = time.perf_counter(); slow_global(N); t1 = time.perf_counter() - start
start = time.perf_counter(); fast_local(N); t2 = time.perf_counter() - start
print(f"TIP 1 — Global vs Local lookup:")
print(f"  global: {t1*1000:.1f}ms, local: {t2*1000:.1f}ms, speedup: {t1/t2:.2f}x")


# TIP 2: List comprehension faster than for loop + append
start = time.perf_counter()
r1 = []
for i in range(N):
    r1.append(i * 2)
t1 = time.perf_counter() - start

start = time.perf_counter()
r2 = [i * 2 for i in range(N)]
t2 = time.perf_counter() - start

print(f"\nTIP 2 — List comp vs for+append:")
print(f"  for+append: {t1*1000:.1f}ms, comprehension: {t2*1000:.1f}ms, speedup: {t1/t2:.2f}x")


# TIP 3: str.join() vs += (string concatenation)
parts = [f"item_{i}" for i in range(10_000)]

start = time.perf_counter()
s = ""
for p in parts:
    s += p   # O(n²) — new string object each time
t1 = time.perf_counter() - start

start = time.perf_counter()
s = "".join(parts)   # O(n) — one allocation
t2 = time.perf_counter() - start

print(f"\nTIP 3 — str join vs +=:")
print(f"  +=: {t1*1000:.1f}ms, join: {t2*1000:.1f}ms, speedup: {t1/t2:.2f}x")
print(f"  (+=: O(n²) new string each time; join: O(n) single allocation)")


# TIP 4: set lookup O(1) vs list lookup O(n)
large_list = list(range(50_000))
large_set = set(large_list)
target = 49_999

start = time.perf_counter()
for _ in range(1000):
    _ = target in large_list
t1 = time.perf_counter() - start

start = time.perf_counter()
for _ in range(1000):
    _ = target in large_set
t2 = time.perf_counter() - start

print(f"\nTIP 4 — Set vs List lookup (1000 × membership test):")
print(f"  list: {t1*1000:.1f}ms, set: {t2*1000:.2f}ms, speedup: {t1/t2:.0f}x")


# TIP 5: Generator vs list for large sequences
tracemalloc.start()

# List approach — materializes all in memory
snapshot1_start = tracemalloc.take_snapshot()
big_list = [x * x for x in range(1_000_000)]
total_list = sum(big_list)
snapshot1_end = tracemalloc.take_snapshot()
del big_list

# Generator approach — lazy
snapshot2_start = tracemalloc.take_snapshot()
total_gen = sum(x * x for x in range(1_000_000))
snapshot2_end = tracemalloc.take_snapshot()

tracemalloc.stop()

print(f"\nTIP 5 — List vs Generator memory:")
list_stats = snapshot1_end.compare_to(snapshot1_start, "lineno")
gen_stats  = snapshot2_end.compare_to(snapshot2_start, "lineno")
# (both totals correct, generator uses near-zero memory during processing)
print(f"  List: materializes all 1M items in memory")
print(f"  Generator: processes one at a time, near-zero extra memory")
print(f"  Both give same result: {total_list == total_gen}")


# TIP 6: lru_cache for repeated calls
call_count = 0

def expensive_nlp(text: str) -> int:
    global call_count
    call_count += 1
    return len(text.encode())

@functools.lru_cache(maxsize=500)
def cached_nlp(text: str) -> int:
    global call_count
    call_count += 1
    return len(text.encode())

texts = ["hello world", "python rocks", "hello world"] * 100

call_count = 0
for t in texts: expensive_nlp(t)
without_cache = call_count

call_count = 0
for t in texts: cached_nlp(t)
with_cache = call_count

print(f"\nTIP 6 — lru_cache:")
print(f"  Without cache: {without_cache} calls")
print(f"  With cache:    {with_cache} unique calls")
print(f"  Cache hits:    {without_cache - with_cache}")
print(f"  Cache info:    {cached_nlp.cache_info()}")


# TIP 7: Use tuple for immutable pairs instead of list
# Tuples are faster to create and slightly faster to access
start = time.perf_counter()
t_result = [(i, i*2) for i in range(N)]
tuple_time = time.perf_counter() - start

start = time.perf_counter()
l_result = [[i, i*2] for i in range(N)]
list_time = time.perf_counter() - start

print(f"\nTIP 7 — tuple vs list for pairs ({N:,} items):")
print(f"  tuple creation: {tuple_time*1000:.1f}ms")
print(f"  list creation:  {list_time*1000:.1f}ms")
print(f"  tuple size: {sys.getsizeof((1, 2))}, list size: {sys.getsizeof([1, 2])}")


# TIP 8: dict.get() vs try/except for missing keys
d = {i: i * 2 for i in range(100)}

start = time.perf_counter()
for i in range(N):
    try:
        val = d[i % 200]  # half will miss
    except KeyError:
        val = 0
t1 = time.perf_counter() - start

start = time.perf_counter()
for i in range(N):
    val = d.get(i % 200, 0)  # no exception overhead
t2 = time.perf_counter() - start

print(f"\nTIP 8 — dict.get() vs try/except for missing keys:")
print(f"  try/except: {t1*1000:.1f}ms, dict.get(): {t2*1000:.1f}ms")
print(f"  Note: try/except is FASTER when key is usually present (no exception path)")
print(f"        dict.get() is FASTER when key is often missing (no exception overhead)")


# TIP 9: map() with built-in vs comprehension with lambda
words = ["hello", "world", "python", "rocks"] * 10_000

start = time.perf_counter()
r1 = list(map(str.upper, words))   # built-in C function
t1 = time.perf_counter() - start

start = time.perf_counter()
r2 = [w.upper() for w in words]   # Python loop
t2 = time.perf_counter() - start

print(f"\nTIP 9 — map(builtin) vs comprehension:")
print(f"  map(str.upper): {t1*1000:.1f}ms, comprehension: {t2*1000:.1f}ms")


# TIP 10: Avoid Python loops — use numpy/builtins for numeric work
print(f"\nTIP 10 — Use built-in functions (sum, max, min, any, all):")
numbers = list(range(1_000_000))

start = time.perf_counter()
s1 = 0
for n in numbers:
    s1 += n
t1 = time.perf_counter() - start

start = time.perf_counter()
s2 = sum(numbers)   # implemented in C
t2 = time.perf_counter() - start

print(f"  for loop sum: {t1*1000:.1f}ms")
print(f"  sum() builtin: {t2*1000:.1f}ms, speedup: {t1/t2:.1f}x")


# ══════════════════════════════════════════════════════════════════════════════
# PART J: MEMORY-EFFICIENT PATTERNS SUMMARY
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MEMORY-EFFICIENT PATTERNS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌─────────────────────────────────────────────────────────────────────────────┐
│ Situation               │ Technique              │ Why                       │
├─────────────────────────┼────────────────────────┼───────────────────────────┤
│ Many small instances    │ __slots__              │ No __dict__ per instance  │
│ Large data processing   │ Generators (yield)     │ One item at a time        │
│ Cache that auto-expires │ WeakValueDictionary    │ GC can evict entries      │
│ Immutable data records  │ namedtuple / NamedTuple│ Tuple efficiency          │
│ Frequent None keys      │ defaultdict            │ No repeated checks        │
│ Repeated computations   │ lru_cache              │ Avoid re-computing        │
│ Expn: avoid cycles      │ weakref                │ Don't pin objects in mem  │
│ Many string copies      │ sys.intern()           │ One object for same string│
└─────────────────────────┴────────────────────────┴───────────────────────────┘

GENERATOR vs LIST — When to choose:
  List:      when you need RANDOM ACCESS (items[42]), multiple passes,
             or the data fits comfortably in memory
  Generator: when processing LARGE datasets, streaming, one-pass consumption,
             or building lazy pipelines
"""

print("\n=== Memory-Efficient Example: Processing 1M LLM Logs ===")


def generate_llm_logs(n: int):
    """Memory-efficient: yields one log at a time."""
    import random
    random.seed(42)
    for i in range(n):
        yield {
            "id": i,
            "model": random.choice(["gpt-4", "claude-3"]),
            "tokens": random.randint(50, 2000),
            "latency_ms": random.uniform(100, 5000),
        }


# Process 1M logs with near-zero memory overhead
def total_tokens_memory_efficient(n_logs: int) -> int:
    """sum() consumes generator one item at a time."""
    return sum(log["tokens"] for log in generate_llm_logs(n_logs))


# This would use ~500 MB for 1M logs if materialized as list
# With generator: O(1) memory
start = time.perf_counter()
total = total_tokens_memory_efficient(100_000)
elapsed = time.perf_counter() - start

print(f"Processed 100k logs: total_tokens={total:,}")
print(f"Time: {elapsed*1000:.1f}ms, Memory: O(1) constant (generator)")


"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Q&A — Memory Management & Performance
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q1: What is the difference between __del__ and garbage collection?
A:  __del__ is called when refcount reaches 0 (or cyclic GC frees it).
    For simple objects without cycles: called immediately when refcount=0.
    For cycles: called by cyclic GC at non-deterministic time.

    DO NOT rely on __del__ for resource cleanup (file handles, DB connections).
    Use context managers (with statement / __enter__/__exit__) instead.

Q2: How does Python's GIL affect memory management?
A:  The GIL protects refcount operations from race conditions in threads.
    Without GIL: two threads could simultaneously increment/decrement refcount
    → race condition → object freed too early → segfault.
    GIL ensures refcount is ALWAYS consistent.

Q3: When should you use gc.disable()?
A:  In performance-critical code that:
    1. Creates many objects quickly
    2. Has no circular references
    3. Can't afford GC pauses

    Example: JSON parsing, data loading, batch processing.
    But: you must ensure NO circular references exist, or use gc.collect() manually.

Q4: What is the difference between deep copy and shallow copy?
A:  Shallow copy (copy.copy(), list[:], dict.copy()):
      Creates NEW container but REFERENCES to SAME nested objects.
    Deep copy (copy.deepcopy()):
      Recursively creates NEW copies of ALL nested objects.

    l1 = [[1, 2], [3, 4]]
    l2 = l1.copy()          # shallow
    l1[0].append(99)        # mutates shared inner list
    print(l2)               # [[1, 2, 99], [3, 4]] ← changed!

    l3 = copy.deepcopy(l1)  # deep
    l1[0].append(100)       # only l1 changes
    print(l3)               # [[1, 2, 99], [3, 4]] ← unchanged

Q5: What is the small integer cache in CPython?
A:  CPython pre-allocates int objects for -5 through 256.
    Accessing any of these values returns THE SAME OBJECT (identity check).
    This saves memory for the most commonly used integers.
    Outside this range: each computation creates a new int object.
    This is why: a = 1000; b = 1000; a is b → False (different objects)
"""

print("\n✅ 07_Memory_Performance_Theory.py complete — all sections covered.")
