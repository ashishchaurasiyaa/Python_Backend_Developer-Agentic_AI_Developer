"""
╔══════════════════════════════════════════════════════════════╗
║  PYTHON COMPLETE PRACTICAL — Section 01                      ║
║  Topic: Lists, Tuples, Sets — Complete Reference             ║
╚══════════════════════════════════════════════════════════════╝
"""

# ══════════════════════════════════════════════════════════════
# PART A: LISTS
# ══════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────
# 1. CREATION
# ─────────────────────────────────────────────────────────────

empty: list = []
nums: list[int] = [1, 2, 3, 4, 5]
mixed: list = [1, "two", 3.0, True, None]
nested: list[list[int]] = [[1, 2], [3, 4], [5, 6]]

# From other iterables
from_range  = list(range(10))        # [0,1,...,9]
from_str    = list("hello")          # ['h','e','l','l','o']
from_map    = list(map(int, ["1","2","3"]))  # [1,2,3]


# ─────────────────────────────────────────────────────────────
# 2. INDEXING AND SLICING
# ─────────────────────────────────────────────────────────────

lst = [10, 20, 30, 40, 50, 60, 70, 80]
#      0   1   2   3   4   5   6   7
#     -8  -7  -6  -5  -4  -3  -2  -1

print(lst[0])          # 10 (first)
print(lst[-1])         # 80 (last)
print(lst[2:5])        # [30, 40, 50]
print(lst[:3])         # [10, 20, 30]
print(lst[5:])         # [60, 70, 80]
print(lst[::2])        # [10, 30, 50, 70] every 2nd
print(lst[::-1])       # [80,70,...,10] reversed

# Slicing creates a COPY
copy = lst[:]          # shallow copy of entire list


# ─────────────────────────────────────────────────────────────
# 3. LIST METHODS — complete
# ─────────────────────────────────────────────────────────────

lst = [3, 1, 4, 1, 5, 9, 2, 6]

# ── Add ───────────────────────────────────────────────────────
lst.append(5)             # add to END — O(1)
lst.insert(0, 99)         # insert at index — O(n)
lst.extend([10, 11, 12])  # extend with iterable — O(k)
lst += [13, 14]           # same as extend

# ── Remove ───────────────────────────────────────────────────
lst.remove(99)            # remove FIRST occurrence by value — O(n)
popped = lst.pop()        # remove and return LAST — O(1)
popped_idx = lst.pop(0)   # remove and return at index — O(n)
del lst[0]                # delete at index
del lst[1:3]              # delete slice
# lst.clear()             # remove all elements

# ── Search ───────────────────────────────────────────────────
lst = [3, 1, 4, 1, 5, 9, 2, 6]
print(lst.index(4))       # 2 — raises ValueError if not found
print(lst.count(1))       # 2 — count occurrences
print(4 in lst)           # True — membership test O(n)

# ── Order ─────────────────────────────────────────────────────
lst.sort()                          # sort IN PLACE, returns None
lst.sort(reverse=True)              # descending
lst.sort(key=lambda x: -x)         # custom key
lst.reverse()                       # reverse IN PLACE

# sorted() — returns NEW list, original unchanged
nums = [3, 1, 4, 1, 5]
new_sorted = sorted(nums)           # [1, 1, 3, 4, 5]
new_sorted_rev = sorted(nums, reverse=True)

# Sort complex objects
agents = [
    {"name": "Bob", "tokens": 500},
    {"name": "Alice", "tokens": 300},
    {"name": "Charlie", "tokens": 700},
]
agents.sort(key=lambda a: a["tokens"])           # sort by tokens
agents_sorted = sorted(agents, key=lambda a: (a["tokens"], a["name"]))  # multi-key

# ── Other ─────────────────────────────────────────────────────
lst = [1, 2, 3]
lst_copy = lst.copy()     # shallow copy
print(len(lst))           # length


# ─────────────────────────────────────────────────────────────
# 4. SHALLOW vs DEEP COPY — critical bug source
# ─────────────────────────────────────────────────────────────

import copy

original = [[1, 2], [3, 4], [5, 6]]

# Shallow copy — new list, but SAME inner objects
shallow = original.copy()          # or original[:] or list(original)
shallow[0][0] = 99                 # modifies original too!
print(original[0])                 # [99, 2] — MODIFIED!

# Deep copy — new list AND new inner objects
original = [[1, 2], [3, 4], [5, 6]]
deep = copy.deepcopy(original)
deep[0][0] = 99
print(original[0])   # [1, 2] — unchanged


# ─────────────────────────────────────────────────────────────
# 5. LIST COMPREHENSIONS
# ─────────────────────────────────────────────────────────────

# [expression for item in iterable if condition]

squares     = [x**2 for x in range(10)]
even_sq     = [x**2 for x in range(10) if x % 2 == 0]
flat        = [x for row in [[1,2],[3,4],[5,6]] for x in row]  # flatten

# With function call
tokens = ["  hello  ", "  world  ", "  python  "]
cleaned = [t.strip().lower() for t in tokens]

# Nested comprehension (matrix transpose)
matrix = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
transposed = [[row[i] for row in matrix] for i in range(3)]
print(transposed)  # [[1,4,7],[2,5,8],[3,6,9]]

# Comprehension vs map/filter
# map/filter are lazy, comprehensions are eager
# Use comprehension when you need list result
# Use map/filter when chaining with other iterators


# ─────────────────────────────────────────────────────────────
# 6. LIST PERFORMANCE — Big O
# ─────────────────────────────────────────────────────────────

# append(x)     O(1) amortized
# insert(0, x)  O(n) — shifts all elements
# pop()         O(1) — from end
# pop(0)        O(n) — shifts all elements
# x in list     O(n) — linear search
# list[i]       O(1) — random access
# len(list)     O(1) — cached

# For fast append AND popleft → use collections.deque


# ══════════════════════════════════════════════════════════════
# PART B: TUPLES
# ══════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────
# 1. CREATION AND BASICS
# ─────────────────────────────────────────────────────────────

empty_t: tuple = ()
single: tuple = (42,)          # MUST have trailing comma for single element!
coords: tuple[float, float] = (10.5, 20.3)
mixed_t: tuple = (1, "two", 3.0)
nested_t: tuple = ((1, 2), (3, 4))

# Without parentheses (packing)
point = 3.5, 7.2
print(type(point))   # <class 'tuple'>

# Unpacking
x, y = coords
a, b, *rest = (1, 2, 3, 4, 5)

# ─────────────────────────────────────────────────────────────
# 2. TUPLE METHODS
# ─────────────────────────────────────────────────────────────

t = (1, 2, 3, 2, 4, 2)
print(t.count(2))     # 3
print(t.index(3))     # 2 (first occurrence)
print(len(t))         # 6
print(t[0:3])         # (1, 2, 3)
print(t[::-1])        # (2, 4, 2, 3, 2, 1)

# ─────────────────────────────────────────────────────────────
# 3. WHY TUPLES MATTER
# ─────────────────────────────────────────────────────────────

# Tuples are:
# - Immutable (safer, cannot be accidentally modified)
# - Hashable (can be used as dict keys or in sets)
# - Faster than lists for iteration
# - Less memory than lists

# Tuple as dict key
cache: dict[tuple[str, float], str] = {}
cache[("gpt-4", 0.7)] = "cached_response"
print(cache[("gpt-4", 0.7)])

# Function returning multiple values — returns tuple
def get_stats(data: list[float]) -> tuple[float, float, float]:
    return min(data), max(data), sum(data) / len(data)

mn, mx, avg = get_stats([1.0, 2.0, 3.0, 4.0, 5.0])
print(f"min={mn}, max={mx}, avg={avg}")

# Named tuple — best of both worlds
from typing import NamedTuple

class Point(NamedTuple):
    x: float
    y: float
    label: str = ""

p = Point(3.5, 7.2, "origin")
print(p.x, p.y)        # named access
print(p[0], p[1])      # index access
print(p._asdict())     # dict conversion
p2 = p._replace(x=10.0)  # create modified copy


# ══════════════════════════════════════════════════════════════
# PART C: SETS
# ══════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────
# 1. CREATION
# ─────────────────────────────────────────────────────────────

empty_s: set = set()          # NOT {} — that's an empty dict!
nums_s: set[int] = {1, 2, 3, 4, 5}
from_list: set[str] = set(["a", "b", "a", "c"])  # removes duplicates
print(from_list)              # {'a', 'b', 'c'} — order not guaranteed

# frozenset — immutable set (hashable, can be dict key)
fs = frozenset({1, 2, 3})
# fs.add(4)  # AttributeError


# ─────────────────────────────────────────────────────────────
# 2. SET METHODS
# ─────────────────────────────────────────────────────────────

s = {1, 2, 3, 4}

# Add/Remove
s.add(5)                     # add element
s.discard(99)                # remove if present (no error if missing)
s.remove(5)                  # remove — raises KeyError if missing
popped = s.pop()             # remove and return ARBITRARY element

# ─────────────────────────────────────────────────────────────
# 3. SET OPERATIONS — mathematical
# ─────────────────────────────────────────────────────────────

a = {1, 2, 3, 4, 5}
b = {3, 4, 5, 6, 7}

# Union — all elements from both
print(a | b)               # {1,2,3,4,5,6,7}
print(a.union(b))

# Intersection — only in both
print(a & b)               # {3,4,5}
print(a.intersection(b))

# Difference — in a but not in b
print(a - b)               # {1,2}
print(a.difference(b))

# Symmetric difference — in either but not both
print(a ^ b)               # {1,2,6,7}
print(a.symmetric_difference(b))

# Subset / Superset
small = {3, 4}
print(small.issubset(a))    # True — all of small in a
print(a.issuperset(small))  # True — a contains all of small
print(a.isdisjoint({8, 9})) # True — no common elements


# ─────────────────────────────────────────────────────────────
# 4. SET COMPREHENSION
# ─────────────────────────────────────────────────────────────

words = ["hello", "world", "hello", "python", "world"]
unique_lengths = {len(w) for w in words}
print(unique_lengths)    # {5, 6} (unique lengths only)


# ─────────────────────────────────────────────────────────────
# 5. SET PERFORMANCE — O(1) lookup
# ─────────────────────────────────────────────────────────────

# x in set    O(1) — hash-based lookup
# x in list   O(n) — linear search

import time

large_list = list(range(1_000_000))
large_set  = set(range(1_000_000))

# set lookup is ~100x faster than list for large collections
start = time.perf_counter()
999999 in large_set
set_time = time.perf_counter() - start

start = time.perf_counter()
999999 in large_list
list_time = time.perf_counter() - start

print(f"Set lookup:  {set_time*1e6:.2f}μs")
print(f"List lookup: {list_time*1e6:.2f}μs")


# ─────────────────────────────────────────────────────────────
# 6. PRODUCTION PATTERNS
# ─────────────────────────────────────────────────────────────

# ── Pattern 1: Deduplication ─────────────────────────────────
emails = ["a@x.com", "b@x.com", "a@x.com", "c@x.com"]
unique_emails = list(set(emails))
# Warning: set() loses order. To preserve order:
seen: set[str] = set()
unique_ordered = [e for e in emails if not (e in seen or seen.add(e))]  # type: ignore
print(unique_ordered)

# ── Pattern 2: Permission checking ───────────────────────────
ADMIN_PERMISSIONS: frozenset[str] = frozenset({
    "read", "write", "delete", "manage_users", "view_logs", "export"
})
USER_PERMISSIONS: frozenset[str] = frozenset({"read", "write"})

def has_all_permissions(user_perms: frozenset, required: frozenset) -> bool:
    return required.issubset(user_perms)

def missing_permissions(user_perms: frozenset, required: frozenset) -> frozenset:
    return required - user_perms

required = frozenset({"read", "delete"})
print(has_all_permissions(USER_PERMISSIONS, required))            # False
print(missing_permissions(USER_PERMISSIONS, required))            # {'delete'}

# ── Pattern 3: Find common/unique items between API responses ─
active_users_api1 = {"user_1", "user_2", "user_3", "user_4"}
active_users_api2 = {"user_2", "user_3", "user_5", "user_6"}

in_both  = active_users_api1 & active_users_api2   # intersection
only_api1 = active_users_api1 - active_users_api2  # difference
all_users = active_users_api1 | active_users_api2  # union

print(f"In both APIs: {in_both}")
print(f"Only in API1: {only_api1}")

# ── Pattern 4: Tag/category system ───────────────────────────
class Document:
    def __init__(self, title: str, tags: set[str]):
        self.title = title
        self.tags = tags

docs = [
    Document("Python Guide", {"python", "tutorial", "backend"}),
    Document("AI Basics", {"ai", "python", "machine-learning"}),
    Document("FastAPI Intro", {"fastapi", "backend", "python"}),
]

def find_by_tag(docs: list, tag: str) -> list:
    return [d for d in docs if tag in d.tags]

python_docs = find_by_tag(docs, "python")
print(f"Python docs: {[d.title for d in python_docs]}")

# Find docs with ALL specified tags
def find_by_all_tags(docs: list, tags: set[str]) -> list:
    return [d for d in docs if tags.issubset(d.tags)]

backend_python = find_by_all_tags(docs, {"python", "backend"})
print(f"Python+Backend docs: {[d.title for d in backend_python]}")


# ─────────────────────────────────────────────────────────────
# INTERVIEW QUESTIONS
# ─────────────────────────────────────────────────────────────
"""
Q: What's the difference between list, tuple, and set?
A: list   — ordered, mutable, allows duplicates, O(n) search
   tuple  — ordered, immutable, allows duplicates, O(n) search, hashable
   set    — unordered, mutable, NO duplicates, O(1) search

Q: When should you use a set instead of a list?
A: When you need O(1) membership testing, deduplication, or set operations.
   Sets use more memory than lists due to hash table overhead.

Q: Why can't you add a list to a set, but you can add a tuple?
A: Sets require hashable elements. Lists are mutable (unhashable).
   Tuples are immutable (hashable), so they can be in sets.

Q: What's the difference between remove() and discard() for sets?
A: remove() raises KeyError if element not present.
   discard() does nothing if element not present.
   Use discard() when absence is acceptable.

Q: How do you preserve insertion order while removing duplicates?
A: dict.fromkeys() or a seen-set comprehension trick:
   seen = set(); unique = [x for x in lst if not (x in seen or seen.add(x))]
   Or in Python 3.7+: list(dict.fromkeys(lst))
"""

# Cleanest deduplication with order preserved (Python 3.7+)
items = [3, 1, 4, 1, 5, 9, 2, 6, 5, 3]
unique = list(dict.fromkeys(items))
print(f"Unique ordered: {unique}")   # [3, 1, 4, 5, 9, 2, 6]
