"""
================================================================================
TOPIC: copy / deepcopy — Shallow vs Deep Copy Semantics
================================================================================

KYA HOTA HAI:
    Python mein assignment (a = b) koi copy nahi karta — dono same object point
    karte hain. Copy ke liye:

    copy.copy(obj)      → Shallow copy: naya container, SAME inner objects
    copy.deepcopy(obj)  → Deep copy:    naya container + RECURSIVE naye inner objects

    Shallow:  outer shell naya, inner data SHARED
    Deep:     poora tree naya, kuch bhi shared nahi

KYO ZAROORI HAI:
    1. Defensive programming — caller ke data ko mutate mat karo
    2. Config objects — default config se instance-specific copy banao
    3. Undo/redo — state snapshot lena
    4. Concurrency — thread ko safe independent copy dena
    5. Bug prevention — mutable default arguments ka safer alternative

KAISE KAAM KARTA HAI (architecture):

    Shallow copy (copy.copy):
        1. __copy__ defined? → call karo
        2. Nahin: type ke hisaab se:
           - list/dict/set → built-in C-level shallow copy
           - Custom class  → new instance, __dict__ shallow copy

    Deep copy (copy.deepcopy):
        1. memo dict (id → copy) — cyclic reference prevention
        2. __deepcopy__ defined? → call karo
        3. Nahin: recursively deepcopy every attribute
        4. Memo pe check: agar same object pehle copy ho chuka → reuse (no infinite loop)

KAHAN USE HOTA HAI:
    - API responses: response dict ko shallow copy karo before enriching
    - Django form: bound form data ko copy karo before validation
    - Test fixtures: mutable fixture ko each test ke liye deepcopy karo
    - Config: default settings ko deepcopy karo per-tenant config ke liye

INTERVIEW ANSWER (English — recite this):
    "copy.copy() creates a new container but shares references to inner objects —
    mutating a nested list in the copy also mutates the original. copy.deepcopy()
    recursively creates new objects at every level, using a memo dict to handle
    cyclic references without infinite recursion. For custom classes, define
    __copy__ and __deepcopy__ to control what gets copied — useful for objects
    with external resources (DB connections, file handles) that shouldn't be
    duplicated."
================================================================================
"""

import copy
import sys

# ============================================================================
# SECTION 1 — ASSIGNMENT vs COPY: THE CONFUSION
# ============================================================================
print("=" * 65)
print("SECTION 1 — Assignment vs Shallow vs Deep Copy")
print("=" * 65)

original = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]

# Assignment — NO copy, same object
ref = original
# Shallow copy — new outer list, same inner lists
shallow = copy.copy(original)
# Deep copy — everything new
deep = copy.deepcopy(original)

# Mutate original's inner list
original[0].append(99)
original.append([10, 11, 12])

print(f"original  = {original}")
print(f"ref       = {ref}")      # ALL changes visible (same object)
print(f"shallow   = {shallow}")  # Inner mutation [99] visible, append NOT (new outer)
print(f"deep      = {deep}")     # NO changes visible (completely independent)

print(f"\noriginal is ref:    {original is ref}")        # True
print(f"original is shallow: {original is shallow}")    # False (new outer)
print(f"original[0] is shallow[0]: {original[0] is shallow[0]}")  # True — SHARED inner!
print(f"original[0] is deep[0]:    {original[0] is deep[0]}")     # False — independent!


# ============================================================================
# SECTION 2 — SHALLOW COPY IN PRACTICE
# ============================================================================
print("\n" + "=" * 65)
print("SECTION 2 — Shallow Copy Methods")
print("=" * 65)

# Multiple ways to do shallow copy
d = {"name": "Alice", "tags": ["admin", "user"]}

shallow_1 = copy.copy(d)
shallow_2 = dict(d)           # dict constructor
shallow_3 = d.copy()          # dict.copy() method
shallow_4 = {**d}             # dict unpacking

print(f"copy.copy(d) is d:   {shallow_1 is d}")     # False
print(f"dict(d) is d:        {shallow_2 is d}")     # False
print(f"d.copy() is d:       {shallow_3 is d}")     # False

# But inner 'tags' list is SHARED in all shallow copies
print(f"\nd['tags'] is shallow_1['tags']: {d['tags'] is shallow_1['tags']}")  # True
print(f"d['tags'] is shallow_2['tags']: {d['tags'] is shallow_2['tags']}")  # True

# Mutate nested — affects ALL shallow copies
d["tags"].append("superuser")
print(f"\nAfter d['tags'].append('superuser'):")
print(f"  d['tags']        = {d['tags']}")
print(f"  shallow_1['tags'] = {shallow_1['tags']}")  # Also has 'superuser'!
print(f"  shallow_2['tags'] = {shallow_2['tags']}")  # Also has 'superuser'!

# For lists, shallow copy methods:
lst = [1, [2, 3], [4, 5]]
lst_shallow_a = lst[:]           # Slice copy
lst_shallow_b = list(lst)        # list() constructor
lst_shallow_c = lst.copy()       # list.copy()
print(f"\nList shallow: lst[:] is lst: {lst[:] is lst}")  # False


# ============================================================================
# SECTION 3 — DEEP COPY IN PRACTICE
# ============================================================================
print("\n" + "=" * 65)
print("SECTION 3 — Deep Copy — Full Independence")
print("=" * 65)

# Real backend scenario: per-request config from shared default
DEFAULT_CONFIG = {
    "db": {"host": "localhost", "port": 5432, "pool_size": 5},
    "cache": {"backend": "redis", "timeout": 300},
    "feature_flags": ["new_ui", "beta_api"],
}

# BAD — shallow copy: db dict is shared!
tenant_config_bad = copy.copy(DEFAULT_CONFIG)
tenant_config_bad["db"]["host"] = "tenant1.db.example.com"
print(f"After shallow copy + mutate host:")
print(f"  DEFAULT_CONFIG['db']['host'] = {DEFAULT_CONFIG['db']['host']}")  # MUTATED!

# Restore
DEFAULT_CONFIG["db"]["host"] = "localhost"

# GOOD — deep copy: completely independent
tenant_config = copy.deepcopy(DEFAULT_CONFIG)
tenant_config["db"]["host"] = "tenant1.db.example.com"
tenant_config["db"]["pool_size"] = 20
tenant_config["feature_flags"].append("tenant_analytics")

print(f"\nAfter deep copy + mutate:")
print(f"  DEFAULT_CONFIG['db']['host']   = {DEFAULT_CONFIG['db']['host']}")       # unchanged
print(f"  DEFAULT_CONFIG['db']['pool_size'] = {DEFAULT_CONFIG['db']['pool_size']}") # unchanged
print(f"  DEFAULT_CONFIG['feature_flags'] = {DEFAULT_CONFIG['feature_flags']}")   # unchanged
print(f"  tenant_config['db']['host']    = {tenant_config['db']['host']}")
print(f"  tenant_config['feature_flags'] = {tenant_config['feature_flags']}")


# ============================================================================
# SECTION 4 — CUSTOM __copy__ and __deepcopy__
# ============================================================================
print("\n" + "=" * 65)
print("SECTION 4 — Custom __copy__ and __deepcopy__")
print("=" * 65)

class DatabaseConnection:
    """Resource object: connection should NOT be copied — share or create new."""

    def __init__(self, url: str):
        self.url = url
        self._connection_id = id(self)  # Simulates an external resource handle
        self._query_count = 0

    def query(self, sql: str):
        self._query_count += 1
        return f"Result of: {sql}"

    def __copy__(self):
        # Shallow copy: return SAME connection (resource sharing)
        print(f"  __copy__ called — sharing existing connection {self._connection_id}")
        return self  # Don't create new DB connection just for a shallow copy

    def __deepcopy__(self, memo):
        # Deep copy: create NEW connection to same URL (new resource)
        print(f"  __deepcopy__ called — creating new connection to {self.url}")
        new_conn = DatabaseConnection(self.url)
        memo[id(self)] = new_conn  # Register in memo dict for cyclic safety
        return new_conn

    def __repr__(self):
        return f"DBConn(url={self.url!r}, id={self._connection_id}, queries={self._query_count})"

conn = DatabaseConnection("postgresql://localhost/myapp")
print(f"Original: {conn}")

shallow_conn = copy.copy(conn)
print(f"Shallow:  {shallow_conn}")
print(f"original is shallow_conn: {conn is shallow_conn}")  # True — same object!

deep_conn = copy.deepcopy(conn)
print(f"Deep:     {deep_conn}")
print(f"original is deep_conn:    {conn is deep_conn}")     # False — new connection


# ============================================================================
# SECTION 5 — CYCLIC REFERENCES
# ============================================================================
print("\n" + "=" * 65)
print("SECTION 5 — Cyclic References — deepcopy handles them safely")
print("=" * 65)

# Cyclic structure: node.children contains nodes that point back
class Node:
    def __init__(self, name: str):
        self.name = name
        self.parent = None
        self.children = []

    def add_child(self, child):
        child.parent = self  # Back reference!
        self.children.append(child)

    def __repr__(self):
        return f"Node({self.name!r})"

root = Node("root")
child1 = Node("child1")
child2 = Node("child2")
root.add_child(child1)
root.add_child(child2)

# Cyclic: root → child1 → root (via .parent)
print(f"root.children = {root.children}")
print(f"child1.parent = {child1.parent}")  # → root (cycle!)

# deepcopy handles cycles via memo dict — no infinite recursion
root_copy = copy.deepcopy(root)
print(f"\ndeep copy succeeded despite cycle!")
print(f"root_copy = {root_copy}")
print(f"root_copy.children[0].parent is root_copy: {root_copy.children[0].parent is root_copy}")
# True — cycle preserved in copy, but points to NEW nodes

# copy.copy would only copy root shallowly — children still point to originals
root_shallow = copy.copy(root)
print(f"\nroot_shallow.children[0] is child1: {root_shallow.children[0] is child1}")  # True — shared!


# ============================================================================
# SECTION 6 — PERFORMANCE: WHEN TO USE WHICH
# ============================================================================
print("\n" + "=" * 65)
print("SECTION 6 — Performance: copy vs deepcopy vs manual")
print("=" * 65)

import time

data = {"key": list(range(100)), "nested": {"a": list(range(50))}}

def bench(label, fn, n=10_000):
    start = time.perf_counter()
    for _ in range(n):
        fn()
    return (time.perf_counter() - start) * 1000

t_shallow  = bench("copy.copy",     lambda: copy.copy(data))
t_deep     = bench("copy.deepcopy", lambda: copy.deepcopy(data))
t_manual   = bench("dict()",        lambda: dict(data))  # Only copies top level

print(f"copy.copy(data):     {t_shallow:.1f}ms for 10k iterations")
print(f"copy.deepcopy(data): {t_deep:.1f}ms for 10k iterations")
print(f"dict(data):          {t_manual:.1f}ms for 10k iterations (shallow only)")
print(f"\ndeep/shallow ratio: {t_deep/t_shallow:.1f}x (deep is always slower)")
print("Rule: Use shallow unless you NEED independence of nested objects.")


# ============================================================================
# BREAK-IT — Common copy/deepcopy Mistakes
# ============================================================================
print("\n" + "=" * 65)
print("BREAK-IT — Common Mistakes")
print("=" * 65)

# BUG 1: Thinking dict.copy() does deep copy
config = {"db": {"host": "localhost"}}
config_copy = config.copy()  # Shallow — db dict is SHARED
config_copy["db"]["host"] = "production.db.com"
print(f"Bug 1 — dict.copy() is shallow:")
print(f"  config['db']['host'] = {config['db']['host']}")  # MUTATED!

# BUG 2: __copy__ infinite recursion
class BadCopy:
    def __copy__(self):
        return copy.copy(self)  # INFINITE RECURSION!

# Don't call this — it'll crash. Fix: use copy.copy(self.__class__()) or super()
print("\nBug 2 — __copy__ calling copy.copy(self) = infinite recursion (don't run!)")

# BUG 3: deepcopy of unpicklable objects
class UnpicklableResource:
    def __init__(self):
        self.lock = __import__("threading").Lock()

res = UnpicklableResource()
try:
    res_copy = copy.deepcopy(res)
    print(f"\nBug 3 — deepcopy of Lock: succeeded (Python deepcopies Locks now)")
except TypeError as e:
    print(f"\nBug 3 — deepcopy of unpicklable: {e}")
# Fix: define __deepcopy__ to create new Lock instead of copying

# BUG 4: Mutable default argument — copy avoids this
def process_items(items, results=None):
    if results is None:
        results = []  # Correct — new list each call
    results.extend(items)
    return results

r1 = process_items([1, 2])
r2 = process_items([3, 4])
print(f"\nBug 4 (fixed pattern): r1={r1}, r2={r2}")  # Independent!


# ============================================================================
# TODO — Test fixture manager
# ============================================================================
"""
Django/pytest mein fixtures ko isolate karna padta hai per-test.

Implement ek FixtureManager class jo:
  1. `register(name: str, data: dict)` — master fixture store karo
  2. `get(name: str) → dict` — har call pe deepcopy return karo
     (taaki test fixture mutate kare toh dusre tests affected na hon)
  3. `snapshot(name: str) → dict` — current fixture ki shallow copy return karo
     (cheap read-only view, mutation allowed toh shallow kaafi hai)

Verify:
  - f1 = manager.get('user')
  - f1['roles'].append('superuser')
  - f2 = manager.get('user')
  - f2['roles'] should NOT have 'superuser' (deepcopy isolation)

  - s1 = manager.snapshot('user')
  - s1['name'] = 'Modified'
  - s2 = manager.snapshot('user')
  - s2['name'] should still be 'Alice' (top-level key isolation in shallow)
  - BUT: s1['roles'] is s2['roles'] should be True (shared inner list in shallow)
"""

if __name__ == "__main__":
    print("\n" + "=" * 65)
    print("RUN: python 33_copy_deepcopy.py")
    print("Sab sections automatically run hote hain above.")
    print("TODO: Implement FixtureManager with get() + snapshot() at the bottom.")
    print("=" * 65)
