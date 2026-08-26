"""
================================================================================
TOPIC: Dictionary Internals — CPython Hash Table Architecture
================================================================================

KYA HOTA HAI:
    Python dict ek hash table hai — ek array of "slots" jahan keys store hoti hain.
    Har slot mein: (hash_value, key, value).
    Key lookup O(1) average — direct slot calculate karke jump karo.

    CPython 3.6+ mein dict ka structure:
    ┌─────────────────────────────────────────────────────────┐
    │  Indices Array (hash index → slot number)               │
    │  [_, _, 2, _, 0, _, _, 1, _]  ← sparse, for fast lookup│
    │                                                         │
    │  Entries Array (compact, insertion-ordered)             │
    │  [(hash, key, value), ...]    ← dense storage           │
    └─────────────────────────────────────────────────────────┘

    Ye "compact dict" design Python 3.6 se aaya (originally by Raymond Hettinger).
    Iska benefit: insertion order preserve hoti hai + memory 20-25% kam leti hai.

KYO ZAROORI HAI:
    1. Python mein EVERY object lookup dict-based hai:
       - Attribute access: obj.name → obj.__dict__['name'] → dict lookup
       - Module namespace: import os → sys.modules['os'] → dict lookup
       - Global variables: globals() → dict
       - Local variables: locals() → dict
       - Class variables: MyClass.__dict__ → mappingproxy (dict-like)

    2. Interview mein dict ka O(1) claim explain karna padta hai — "kyon O(1)?"

    3. dict ki limitations: keys must be HASHABLE (immutable).
       List as key = TypeError. Tuple as key = OK (agar elements hashable).

KAISE KAAM KARTA HAI (architecture):

    STEP 1 — Hash calculation:
        slot_index = hash(key) % capacity
        hash() built-in calls key.__hash__()
        Python ints ka hash = value itself (small ints)
        Python strings: SipHash-1-3 (randomized at startup — PYTHONHASHSEED)

    STEP 2 — Slot lookup:
        Agar slot[index] empty hai → key NOT found (KeyError ya insert)
        Agar slot[index].key == key (via __eq__) → FOUND
        Agar slot[index].key != key → COLLISION → probe next slot

    STEP 3 — Collision resolution (open addressing, perturbation):
        CPython: index = (index * 5 + 1 + perturbation) % capacity
                 perturbation >>= 5
        (Not simple linear probing — avoids clustering)

    STEP 4 — Resize:
        When load factor > 2/3: capacity doubles (rehash all entries)
        New capacity = smallest power of 2 >= len * 4 (leaves room)

    STEP 5 — Deletion:
        Slot marked as DUMMY (not empty) — ke chain nahi tutey

KAHAN USE HOTA HAI:
    - Caching: {user_id: user_data} — O(1) lookup
    - SAP HANA: column-to-type mapping dict — accessed thousands of times per query
    - Niroskos: request deduplication {idempotency_key: response_body}
    - FastAPI: route registry, dependency cache, response model cache
    - Django ORM: field name → field object mapping

INTERVIEW ANSWER (English — recite this):
    "Python dicts are hash tables with O(1) average lookup. When you access d[key],
    Python calls hash(key) to compute a slot index, then checks if the slot contains
    the key (using __eq__). Collisions are resolved by open addressing with
    perturbation — not chaining. Since Python 3.6, CPython uses a compact layout
    that separates a sparse indices array from a dense entries array, which preserves
    insertion order and reduces memory usage by ~20%. The table resizes (doubles)
    when the load factor exceeds 2/3, which amortizes the O(n) rehash cost."
================================================================================
"""

import sys
import time

# ============================================================================
# SECTION 1 — HASH FUNCTION: __hash__ and __eq__
# ============================================================================
print("=" * 65)
print("SECTION 1 — __hash__ and __eq__")
print("=" * 65)

# Python calls __hash__ to find the slot, then __eq__ to verify the key
print(f"hash('hello')      = {hash('hello')}")
print(f"hash(42)           = {hash(42)}")
print(f"hash(42.0)         = {hash(42.0)}")   # Same as hash(42) — by design
print(f"42 == 42.0         = {42 == 42.0}")   # Equal values → same hash
print(f"hash(True)         = {hash(True)}")   # True == 1 → hash(True) == hash(1)

# Custom class: default hash = based on id() (memory address)
class DefaultHash:
    def __init__(self, val):
        self.val = val

obj1 = DefaultHash(10)
obj2 = DefaultHash(10)
print(f"\nDefaultHash(10) hash: {hash(obj1)}, {hash(obj2)}")
print(f"  obj1 == obj2: {obj1 == obj2}")   # False — different objects
print(f"  obj1 is obj1: {obj1 is obj1}")   # True

# Value-based hash: override __hash__ AND __eq__ together
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __hash__(self):
        return hash((self.x, self.y))   # Tuple hash → stable, collision-resistant

    def __eq__(self, other):
        return isinstance(other, Point) and self.x == other.x and self.y == other.y

    def __repr__(self):
        return f"Point({self.x}, {self.y})"

p1 = Point(1, 2)
p2 = Point(1, 2)
print(f"\nPoint(1,2) hash: {hash(p1)}, {hash(p2)}")
print(f"p1 == p2: {p1 == p2}")   # True — value equality
print(f"p1 is p2: {p1 is p2}")   # False — different objects

# Usable as dict key because __hash__ + __eq__ defined
location_data = {p1: "Mumbai", Point(3, 4): "Delhi"}
print(f"\nlocation_data[Point(1,2)] = {location_data[Point(1, 2)]}")  # O(1) lookup


# ============================================================================
# SECTION 2 — COLLISION: when two keys map to same slot
# ============================================================================
print("\n" + "=" * 65)
print("SECTION 2 — Hash Collision")
print("=" * 65)

# Demonstrate collision: two objects with same hash but different value
class CollidingKey:
    """Forces a hash collision — both instances hash to same value."""
    def __init__(self, name: str, fixed_hash: int):
        self.name = name
        self._hash = fixed_hash

    def __hash__(self):
        return self._hash  # Same hash = collision guaranteed

    def __eq__(self, other):
        return isinstance(other, CollidingKey) and self.name == other.name

    def __repr__(self):
        return f"Key({self.name})"

key_a = CollidingKey("alpha", 42)
key_b = CollidingKey("beta",  42)  # Same hash as key_a!

# Dict handles collision via open addressing — both keys coexist
collision_dict = {key_a: "value_A", key_b: "value_B"}
print(f"key_a hash: {hash(key_a)}, key_b hash: {hash(key_b)}")
print(f"Collision dict has {len(collision_dict)} entries (both coexist)")
print(f"collision_dict[key_a] = {collision_dict[key_a]}")
print(f"collision_dict[key_b] = {collision_dict[key_b]}")

# This works because: same hash → find slot → __eq__ check → different keys → probe next slot


# ============================================================================
# SECTION 3 — MUTABILITY RULE: why lists can't be dict keys
# ============================================================================
print("\n" + "=" * 65)
print("SECTION 3 — Mutability and Hashability")
print("=" * 65)

# List is NOT hashable — it's mutable (can change after insertion)
try:
    bad = {[1, 2]: "value"}
except TypeError as e:
    print(f"List as key → TypeError: {e}")

# Tuple IS hashable (if contents are hashable)
good = {(1, 2): "Mumbai", (3, 4): "Delhi"}
print(f"Tuple as key → OK: {good[(1, 2)]}")

# Why must keys be immutable?
# If you could change the key after insertion:
#   d = {[1,2]: "value"}
#   key = [1,2]
#   key.append(3)   # now hash([1,2,3]) ≠ hash([1,2])
#   d[key]          # can't find it! slot mismatch

# Frozenset IS hashable (frozen = immutable)
fs = frozenset([1, 2, 3])
d = {fs: "frozenset key"}
print(f"frozenset key → OK: {d[fs]}")


# ============================================================================
# SECTION 4 — DICT RESIZE AND MEMORY
# ============================================================================
print("\n" + "=" * 65)
print("SECTION 4 — Dict Size, Load Factor, Resize")
print("=" * 65)

def dict_size_demo():
    d = {}
    prev_size = sys.getsizeof(d)
    resize_at = []

    for i in range(64):
        d[i] = i * 10
        curr_size = sys.getsizeof(d)
        if curr_size != prev_size:
            resize_at.append((i, prev_size, curr_size))
            prev_size = curr_size

    print(f"Dict resized at keys: {[r[0] for r in resize_at]}")
    print(f"Sizes at resize: {[(r[0], f'{r[1]}B→{r[2]}B') for r in resize_at]}")
    print("Notice: resize happens at ~2/3 capacity (load factor threshold)")

dict_size_demo()

# Memory comparison: dict vs list for lookup
print("\nMemory: 1000-key dict")
d = {str(i): i for i in range(1_000)}
print(f"  dict size: {sys.getsizeof(d):,} bytes (sparse hash table)")


# ============================================================================
# SECTION 5 — INSERTION ORDER (Python 3.7+)
# ============================================================================
print("\n" + "=" * 65)
print("SECTION 5 — Insertion Order Preservation")
print("=" * 65)

# Python 3.7+ guarantees insertion order is preserved
d = {}
for key in ["banana", "apple", "cherry", "date"]:
    d[key] = len(key)

print(f"Insertion order preserved: {list(d.keys())}")
# ['banana', 'apple', 'cherry', 'date'] — always!

# dict as ordered registry (real use case)
middleware_stack = {}
middleware_stack["auth"] = lambda r: "check token"
middleware_stack["logging"] = lambda r: "log request"
middleware_stack["rate_limit"] = lambda r: "check limit"
middleware_stack["cors"] = lambda r: "add headers"
print(f"Middleware order: {list(middleware_stack.keys())}")  # exact insertion order


# ============================================================================
# SECTION 6 — PERFORMANCE PATTERNS
# ============================================================================
print("\n" + "=" * 65)
print("SECTION 6 — Performance Patterns and Pitfalls")
print("=" * 65)

# O(1) lookup — constant regardless of dict size
def benchmark_lookup(n: int) -> float:
    d = {str(i): i for i in range(n)}
    target = str(n - 1)
    start = time.perf_counter()
    for _ in range(100_000):
        _ = d[target]
    return time.perf_counter() - start

t_small = benchmark_lookup(10)
t_large = benchmark_lookup(10_000)
print(f"Lookup in 10-key dict:     {t_small:.4f}s")
print(f"Lookup in 10,000-key dict: {t_large:.4f}s")
print(f"  Ratio: {t_large / t_small:.1f}x (should be ~1.0 — O(1) verified)")

# setdefault vs get vs [] for missing keys
d = {"a": 1, "b": 2}
print(f"\nd.get('c', 0)       = {d.get('c', 0)}")         # safe, no insertion
print(f"d.setdefault('c',0) = {d.setdefault('c', 0)}")    # inserts if missing
print(f"'c' in d now?       = {'c' in d}")

# dict comprehension vs loop — same speed, comprehension more Pythonic
import cProfile
# dict comprehension:
squares_comp = {i: i**2 for i in range(1000)}
# loop:
squares_loop = {}
for i in range(1000):
    squares_loop[i] = i**2
print(f"\nsquares_comp == squares_loop: {squares_comp == squares_loop}")

# Counter pattern — count occurrences O(n)
words = ["apple", "banana", "apple", "cherry", "banana", "apple"]
freq = {}
for w in words:
    freq[w] = freq.get(w, 0) + 1
print(f"\nWord frequency: {freq}")
# Better: collections.Counter(words) — same result, C-level speed


# ============================================================================
# SECTION 7 — DICT METHODS DEEP DIVE
# ============================================================================
print("\n" + "=" * 65)
print("SECTION 7 — Dict Methods and Views")
print("=" * 65)

config = {"host": "localhost", "port": 5432, "db": "myapp"}

# Views — LIVE views, not copies
keys_view = config.keys()
values_view = config.values()
items_view = config.items()

config["timeout"] = 30
print(f"keys_view (after adding 'timeout'): {list(keys_view)}")
# Views reflect the live dict — no stale data

# Merge dicts — Python 3.9+ | operator
defaults = {"timeout": 30, "retries": 3, "ssl": False}
overrides = {"ssl": True, "host": "prod.db.example.com"}
merged = defaults | overrides   # overrides win
print(f"\nMerged: {merged}")

# In-place merge (|=)
defaults |= overrides
print(f"defaults after |=: {defaults}")

# dict.update() — same as |= but older syntax
d1 = {"a": 1, "b": 2}
d1.update({"b": 99, "c": 3})
print(f"\nAfter update: {d1}")

# pop with default — avoid KeyError
val = config.pop("nonexistent", "default_value")
print(f"\npop nonexistent key: {val}")


# ============================================================================
# BREAK-IT — What Goes Wrong
# ============================================================================
print("\n" + "=" * 65)
print("BREAK-IT — Common Dict Mistakes")
print("=" * 65)

# BUG 1: Modifying dict while iterating
d = {"a": 1, "b": 2, "c": 3}
try:
    for k in d:
        if k == "b":
            d.pop(k)   # RuntimeError!
except RuntimeError as e:
    print(f"Bug 1 — Modify during iteration: {e}")
# Fix: iterate over list(d.keys()) or collect keys first

# BUG 2: Mutable default argument (dict)
def add_user(name: str, cache={}):   # SHARED ACROSS ALL CALLS!
    cache[name] = True
    return cache

r1 = add_user("alice")
r2 = add_user("bob")
print(f"\nBug 2 — Mutable default: r1={r1}, r2={r2}")  # Both have both users!
# Fix: def add_user(name, cache=None): if cache is None: cache = {}

# BUG 3: __hash__ without __eq__ (or vice versa)
class BadKey:
    def __hash__(self):
        return 42  # All instances hash to 42 — massive collision!
    # No __eq__ defined → uses identity (id) → correct but slow

d = {BadKey(): i for i in range(5)}
print(f"\nBug 3 — Same hash for all: {len(d)} keys (correct) but O(n) lookup risk")


# ============================================================================
# TODO — Implement this in SAP HANA context
# ============================================================================
"""
SAP HANA connector mein ek table schema cache banana hai:
  - table_name → {column_name: (data_type, nullable, max_length)}
  - Schema ek baar fetch hoti hai, phir cache se read hoti hai
  - Agar same table_name aur same column structure do alag Column objects
    represent karte hain, woh same key hone chahiye

Implement:
  1. Column dataclass (name, dtype, nullable, max_length)
  2. SchemaCache class jisme:
       - get_schema(table_name) → schema dict ya None
       - set_schema(table_name, columns: list[Column])
       - invalidate(table_name)
  3. Column ko hashable banao (hint: @dataclass(frozen=True))
  4. Demonstrate: same schema cached, invalidated, refetched

Verify: two Column('id', 'int', False, None) instances == True aur same hash.
"""


if __name__ == "__main__":
    print("\n" + "=" * 65)
    print("RUN: python 31_dict_internals_and_hash_tables.py")
    print("Sab sections automatically run hote hain above.")
    print("TODO: Implement the SAP HANA schema cache at the bottom.")
    print("=" * 65)
