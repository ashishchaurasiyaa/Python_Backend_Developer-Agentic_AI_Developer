"""
╔══════════════════════════════════════════════════════════════════════════╗
║         PYTHON THEORY — What, Why, How + Real Life Examples             ║
║         Topic: Core Python — Variables, Types, Strings, Collections     ║
╚══════════════════════════════════════════════════════════════════════════╝

STRUCTURE per concept:
  ► WHAT  — Definition / kya hota hai
  ► WHY   — Problem it solves / kyun chahiye
  ► HOW   — Mechanism / kaise kaam karta hai
  ► REAL LIFE — Real world analogy + production example
  ► CODE  — Runnable example
  ► Q&A   — Interview questions with answers
"""

# ══════════════════════════════════════════════════════════════════════════
# 1. VARIABLES & MEMORY MODEL
# ══════════════════════════════════════════════════════════════════════════
"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT:
  Variable = name (label) pointing to an object in memory.
  Python variables are NOT boxes (like C/Java).
  They are REFERENCES (name tags on objects).

WHY:
  Store and reuse data without rewriting values.
  Allow programs to work with changing data.

HOW (Internal Mechanism):
  ┌─────────────────────────────────────────────┐
  │  x = 42                                     │
  │                                             │
  │  MEMORY:                                    │
  │  ┌─────────┐       ┌──────────────────┐    │
  │  │  name   │──────►│  int object: 42  │    │
  │  │  "x"    │       │  id: 140234...   │    │
  │  └─────────┘       │  refcount: 1     │    │
  │                    └──────────────────┘    │
  │                                             │
  │  y = x   (y ALSO points to same object)    │
  │  ┌─────────┐   ┌──────────────────┐         │
  │  │  "x"   │──►│  int object: 42  │         │
  │  └─────────┘  │  refcount: 2     │         │
  │  ┌─────────┐  └──────────────────┘         │
  │  │  "y"   │──►  same object!               │
  │  └─────────┘                               │
  └─────────────────────────────────────────────┘

REAL LIFE ANALOGY:
  Variable = sticky note with a name.
  Object = actual thing in a room.
  Multiple sticky notes CAN point to same thing.
  Removing a sticky note doesn't destroy the thing
  (until NO sticky notes point to it → garbage collected).

PRODUCTION REAL LIFE:
  config = {"model": "gpt-4"}      # 'config' label → dict object
  active = config                   # 'active' SAME dict object
  active["model"] = "claude"        # modifies SHARED object
  print(config["model"])            # "claude" ← SURPRISE!
  # Fix: active = config.copy()     # shallow copy
  # Fix: active = copy.deepcopy(config)  # deep copy
"""

import sys
import copy

x = 42
y = x
print(f"x id: {id(x)}, y id: {id(y)}, same? {x is y}")  # True — same object

# Mutable vs Immutable
a = [1, 2, 3]
b = a              # both point to SAME list
b.append(4)
print(f"a = {a}")  # [1,2,3,4] — a ALSO changed! (mutable)

c = "hello"
d = c              # both point to SAME string
d = d + " world"   # NEW string created — c unchanged (immutable)
print(f"c = {c}")  # "hello" — unchanged


"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Q&A:

Q: Python mein variable kya hota hai?
A: Variable ek naam hai (label/reference) jo memory mein kisi object ko
   point karta hai. It does NOT hold the value directly.

Q: Mutable aur Immutable kya hota hai?
A: Immutable: change nahi ho sakta (int, str, tuple, frozenset)
   Mutable: change ho sakta hai (list, dict, set)
   int: x = 5; x = 6 — new object ban gaya, 5 same raha
   list: x = [1]; x.append(2) — SAME object modify hua

Q: 'is' aur '==' mein kya difference hai?
A: == checks VALUE equality (value same hai?)
   is checks IDENTITY (same memory object hai?)
   Always use 'is' for None, True, False comparisons.
"""


# ══════════════════════════════════════════════════════════════════════════
# 2. DATA TYPES — MUTABLE vs IMMUTABLE
# ══════════════════════════════════════════════════════════════════════════
"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT:
  Python ke har value ka ek TYPE hota hai jo batata hai
  ki object ki memory mein kya structure hai aur kya operations allowed hain.

WHY:
  ► Type system ensure karta hai ki valid operations hi ho sakein
  ► Memory allocation type pe depend karti hai
  ► Performance characteristics type se decide hoti hain

HOW — INTERNAL:
  ┌─────────────────────────────────────────────────┐
  │  IMMUTABLE TYPES (cannot change after creation) │
  │  int, float, complex, str, tuple, frozenset     │
  │  bool (subclass of int)                         │
  │                                                 │
  │  MUTABLE TYPES (can change after creation)      │
  │  list, dict, set, bytearray, user-defined class │
  └─────────────────────────────────────────────────┘

  WHY immutable exists:
  ► Hashable (can be dict key / set member)
  ► Thread-safe (no locks needed)
  ► Cached by Python (small ints, short strings)

REAL LIFE:
  Immutable = ek marble stone pe likha number. Change karna ho
              toh naya marble banana padega.
  Mutable   = ek whiteboard pe lika number. Erase karke
              same whiteboard pe naya likh sakte ho.

PRODUCTION EXAMPLE:
  # API response keys are immutable strings (safe as dict keys)
  cache = {("gpt-4", 0.7): "cached_response"}  # tuple as key — OK
  # cache[["gpt-4", 0.7]] = ...  # ERROR — list not hashable!

  # Config frozen for thread safety
  from dataclasses import dataclass
  @dataclass(frozen=True)
  class ModelConfig:
      model: str
      temperature: float
  # config.model = "x"  # FrozenInstanceError
"""

# int — immutable, cached -5 to 256
x = 256; y = 256
print(f"\nint caching: {x is y}")   # True (CPython caches small ints)
x = 257; y = 257
print(f"Large int: {x is y}")       # False (not cached)

# str — immutable, interned for simple strings
s1 = "hello"; s2 = "hello"
print(f"str interning: {s1 is s2}") # True (same string literal)

# bool is subclass of int
print(f"bool is int: {isinstance(True, int)}")  # True
print(f"True + True = {True + True}")            # 2
print(f"True * 5 = {True * 5}")                  # 5

# Truthy / Falsy — CRITICAL
falsy = [False, None, 0, 0.0, 0j, "", [], {}, set(), ()]
print(f"\nFalsy values count: {len(falsy)}")
print(f"All falsy: {all(not v for v in falsy)}")  # True


"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Q&A:

Q: Why is bool a subclass of int in Python?
A: Historical reasons + convenience. True==1, False==0.
   sum([True, True, False, True]) = 3 (count of True values)

Q: What are falsy values in Python?
A: False, None, 0, 0.0, 0j, "", [], {}, set(), ()
   Empty containers are falsy. Non-empty are truthy.

Q: Why can't you use a list as a dictionary key?
A: Lists are mutable and NOT hashable. Dict keys must be hashable
   (because dict uses hash table internally). Use tuple instead.
"""


# ══════════════════════════════════════════════════════════════════════════
# 3. STRINGS — IMMUTABLE SEQUENCE
# ══════════════════════════════════════════════════════════════════════════
"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT:
  String = immutable sequence of Unicode characters.
  In Python 3, ALL strings are Unicode by default.

WHY:
  ► Text ko store, manipulate, aur transmit karne ke liye
  ► AI/Backend mein: prompts, API responses, JSON, logs, URLs

HOW (Internal):
  ┌────────────────────────────────────────────┐
  │  s = "hello"                               │
  │                                            │
  │  Memory: [h][e][l][l][o]                   │
  │  Index:   0  1  2  3  4                    │
  │           -5 -4 -3 -2 -1  (negative)       │
  │                                            │
  │  String Object:                            │
  │  ┌──────────────────────────────────┐      │
  │  │ type: str                        │      │
  │  │ length: 5                        │      │
  │  │ data: h,e,l,l,o (UTF-8/UCS)     │      │
  │  │ hash: computed on first use      │      │
  │  │ interned: True (for simple str) │      │
  │  └──────────────────────────────────┘      │
  └────────────────────────────────────────────┘

  String Operations are O(n) — new string created every time!
  This is why "".join(list) is O(n) but repeated += is O(n²)

REAL LIFE ANALOGY:
  String is like a printed book.
  You cannot change letters in it.
  To "change" it, you must print a new book.

PRODUCTION EXAMPLE (AI Backend):
  # Building prompt — WRONG way (O(n²))
  prompt = ""
  for part in ["You are", " a helpful", " assistant"]:
      prompt += part   # creates NEW string each time!

  # CORRECT way (O(n))
  parts = ["You are", " a helpful", " assistant"]
  prompt = "".join(parts)   # ONE allocation

  # Template pattern for prompts
  system_prompt = f\"\"\"
  You are a {role} AI assistant.
  Current date: {date}
  Task: {task}
  \"\"\"
"""

# String methods — production patterns
text = "  Hello, World! Python AI Backend Developer  "

# Chain operations
processed = text.strip().lower().replace(",", "").replace("!", "")
print(f"\nProcessed: '{processed}'")

# String as sequence
s = "Python"
print(f"Length: {len(s)}, First: {s[0]}, Last: {s[-1]}, Slice: {s[2:5]}")
print(f"Reversed: {s[::-1]}")

# String building performance
import time

parts = ["word"] * 10_000

# SLOW — O(n²)
start = time.perf_counter()
result = ""
for p in parts:
    result += p
slow_time = time.perf_counter() - start

# FAST — O(n)
start = time.perf_counter()
result = "".join(parts)
fast_time = time.perf_counter() - start

print(f"\nString += (10k):  {slow_time*1000:.2f}ms")
print(f"String join(10k): {fast_time*1000:.2f}ms")
print(f"join is {slow_time/fast_time:.0f}x faster")


# ══════════════════════════════════════════════════════════════════════════
# 4. LIST — DYNAMIC ARRAY
# ══════════════════════════════════════════════════════════════════════════
"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT:
  List = ordered, mutable, dynamic array of object references.
  Can hold elements of ANY type (even mixed).

WHY:
  ► Ordered data maintain karne ke liye
  ► Elements add/remove karne ke liye dynamically
  ► Sequential processing ke liye (for loops)

HOW (Internal — Dynamic Array):
  ┌──────────────────────────────────────────────────────┐
  │  lst = [1, 2, 3]                                     │
  │                                                       │
  │  List Object:                                         │
  │  ┌───────────────────────────────────────────┐       │
  │  │ ob_refcnt: 1                              │       │
  │  │ ob_size: 3  (current items)              │       │
  │  │ allocated: 4  (capacity, over-allocated) │       │
  │  │ ob_item: [ *ptr1, *ptr2, *ptr3, None ]   │       │
  │  │             ↓       ↓       ↓             │       │
  │  │           int:1  int:2  int:3             │       │
  │  └───────────────────────────────────────────┘       │
  │                                                       │
  │  OVER-ALLOCATION: Python allocates extra space to    │
  │  avoid resizing on every append → amortized O(1)     │
  │                                                       │
  │  BIG O:                                              │
  │  append(x)    → O(1) amortized (over-allocation)    │
  │  insert(0, x) → O(n) — shift all elements right     │
  │  pop()        → O(1) — from end                     │
  │  pop(0)       → O(n) — shift all left               │
  │  x in list    → O(n) — linear search                │
  │  list[i]      → O(1) — direct pointer access        │
  └──────────────────────────────────────────────────────┘

REAL LIFE ANALOGY:
  List = numbered queue at bank.
  Add person at end (append) → instant.
  Add person at front (insert 0) → everyone shuffles back.
  Find person by name → check everyone one by one.
  Find person by number → direct.

PRODUCTION EXAMPLE:
  # Conversation history for LLM — ordered!
  messages = [
      {"role": "system", "content": "You are helpful."},
      {"role": "user", "content": "Hello!"},
      {"role": "assistant", "content": "Hi!"},
  ]
  messages.append({"role": "user", "content": "Next question"})

  # Batch processing documents
  documents = ["doc1", "doc2", ... "doc1000"]
  for batch in chunks(documents, size=10):   # process 10 at a time
      embed_batch(batch)

SHALLOW vs DEEP COPY — CRITICAL BUG:
  a = [[1, 2], [3, 4]]
  b = a.copy()          # shallow copy — inner lists SHARED
  b[0][0] = 99          # modifies a[0][0] too!
  # Fix: import copy; b = copy.deepcopy(a)
"""

lst = [1, 2, 3, 4, 5]

# Slicing creates a copy
sliced = lst[1:4]
sliced[0] = 99
print(f"\nOriginal unchanged: {lst}")  # [1,2,3,4,5]

# List comprehension vs map — when to use
numbers = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

# Comprehension — eager, returns list
evens_squared = [x**2 for x in numbers if x % 2 == 0]

# Generator — lazy, memory efficient
evens_sq_gen = (x**2 for x in numbers if x % 2 == 0)
# Neither computes all at once if you just need sum:
total = sum(x**2 for x in numbers if x % 2 == 0)   # no intermediate list!


# ══════════════════════════════════════════════════════════════════════════
# 5. DICTIONARY — HASH TABLE
# ══════════════════════════════════════════════════════════════════════════
"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT:
  Dict = hash table implementation.
  Key-value pairs with O(1) average-case lookup.
  Maintains INSERTION ORDER (Python 3.7+).

WHY:
  ► O(1) lookup by key (vs O(n) for list)
  ► Associate data meaningfully (name→age, id→user)
  ► JSON data structure (API responses, config files)

HOW (Hash Table Internals):
  ┌──────────────────────────────────────────────────────┐
  │  d = {"model": "gpt-4", "temp": 0.7}                │
  │                                                       │
  │  Step 1: hash("model")  → some_integer_hash          │
  │  Step 2: hash % table_size → slot_index              │
  │  Step 3: store (hash, key, value) at slot_index      │
  │                                                       │
  │  Hash Table (simplified):                            │
  │  ┌──────┬──────────┬──────────────────┐              │
  │  │ Slot │   Key    │     Value        │              │
  │  ├──────┼──────────┼──────────────────┤              │
  │  │  0   │ "model"  │ "gpt-4"          │              │
  │  │  1   │  empty   │                  │              │
  │  │  2   │ "temp"   │ 0.7              │              │
  │  │  3   │  empty   │                  │              │
  │  └──────┴──────────┴──────────────────┘              │
  │                                                       │
  │  LOOKUP:                                             │
  │  d["model"]                                          │
  │  1. hash("model") → same hash → slot 0              │
  │  2. Check key matches → YES                          │
  │  3. Return "gpt-4"                                   │
  │  Total: O(1) !                                       │
  │                                                       │
  │  COLLISION: two keys → same slot                     │
  │  Python uses open addressing (probing)               │
  │  Worst case: O(n) — very rare in practice            │
  │                                                       │
  │  KEY REQUIREMENT: must be HASHABLE (immutable)       │
  └──────────────────────────────────────────────────────┘

REAL LIFE ANALOGY:
  Dict = library catalog system.
  Book title (key) → shelf location (hash) → book (value).
  Instead of checking every shelf, catalog gives direct location.

PRODUCTION EXAMPLE:
  # User session store — O(1) lookup by session_id
  sessions: dict[str, dict] = {}
  sessions["sess_abc123"] = {"user_id": 1, "model": "gpt-4"}
  user = sessions["sess_abc123"]   # O(1)!

  # Model routing config
  MODEL_COSTS = {
      "gpt-4": 0.03,
      "gpt-3.5-turbo": 0.002,
      "claude-3-opus": 0.015,
  }
  cost = MODEL_COSTS.get("gpt-4", 0.01)   # O(1)
"""

# Dict internal behavior
d = {}
for i in range(5):
    d[f"key_{i}"] = i * 10

# Insertion order preserved (Python 3.7+)
print(f"\nDict insertion order: {list(d.keys())}")

# dict.setdefault — get or set
config = {}
config.setdefault("retries", 3)       # sets to 3
config.setdefault("retries", 99)      # NOT overwritten
print(f"setdefault: {config['retries']}")  # 3

# Merge dicts — Python 3.9+ | operator
base    = {"model": "gpt-4", "temp": 0.5}
override = {"temp": 0.9, "stream": True}
merged  = base | override   # right wins on conflict
print(f"Merged: {merged}")


# ══════════════════════════════════════════════════════════════════════════
# 6. SET — HASH SET
# ══════════════════════════════════════════════════════════════════════════
"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT:
  Set = unordered collection of UNIQUE hashable elements.
  Implemented as hash table (like dict but keys only).

WHY:
  ► Duplicate removal
  ► O(1) membership testing (vs O(n) for list)
  ► Mathematical set operations (union, intersection, difference)

HOW:
  ┌────────────────────────────────────────────────┐
  │  Same as dict hash table, but stores only keys │
  │                                                 │
  │  x in large_set  → O(1) hash lookup            │
  │  x in large_list → O(n) scan every element     │
  │                                                 │
  │  Set Operations:                               │
  │  A = {1,2,3,4,5}   B = {3,4,5,6,7}            │
  │  A | B = {1,2,3,4,5,6,7}  (union)             │
  │  A & B = {3,4,5}           (intersection)      │
  │  A - B = {1,2}             (difference)        │
  │  A ^ B = {1,2,6,7}        (symmetric diff)    │
  └────────────────────────────────────────────────┘

REAL LIFE ANALOGY:
  Set = VIP guest list at a party.
  Each guest appears only ONCE.
  Checking if someone is on the list = instant (O(1)).
  Finding common guests between two lists = easy (intersection).

PRODUCTION EXAMPLE:
  # Permission system
  user_perms  = {"read", "write"}
  admin_perms = {"read", "write", "delete", "manage"}
  required    = {"read", "delete"}

  has_access = required.issubset(user_perms)   # False
  missing    = required - user_perms           # {"delete"}

  # Deduplication
  seen_emails = set()
  unique_users = [u for u in users if u["email"] not in seen_emails
                  and not seen_emails.add(u["email"])]

  # Fast lookup — which models are available
  AVAILABLE_MODELS = frozenset({"gpt-4", "claude-3", "gemini"})
  if user_request.model in AVAILABLE_MODELS:   # O(1)
      process(user_request)
"""


# ══════════════════════════════════════════════════════════════════════════
# 7. TUPLE — IMMUTABLE SEQUENCE
# ══════════════════════════════════════════════════════════════════════════
"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT:
  Tuple = immutable, ordered sequence.
  Like a list but CANNOT be modified after creation.

WHY:
  ► Hashable → can be dict key / set member
  ► Signals "this data should not change"
  ► Faster than list for read operations
  ► Multiple return values from functions
  ► Named tuples for structured, readable data

HOW:
  ┌──────────────────────────────────────────┐
  │  t = (1, 2, 3)                           │
  │  Similar to list internally, BUT:        │
  │  - No extra allocated slots              │
  │  - Immutable flag set → no mutation ops  │
  │  - Cached/reused by Python for small tuples│
  │                                          │
  │  Memory: tuple uses LESS than list       │
  │  list(range(10)):  200 bytes             │
  │  tuple(range(10)): 120 bytes             │
  └──────────────────────────────────────────┘

REAL LIFE ANALOGY:
  Tuple = record in a database row.
  (id=1, name="Alice", role="admin") — fixed structure, read-only.
  You don't "change" a DB row; you read it or replace it.

PRODUCTION EXAMPLE:
  # Function returning multiple values (returns tuple)
  def get_llm_stats(model: str) -> tuple[float, int, float]:
      return 0.03, 8192, 0.7   # price, ctx_window, default_temp

  price, ctx, temp = get_llm_stats("gpt-4")

  # Cache key — tuple as dict key
  @lru_cache(maxsize=256)
  def get_embedding(text: str, model: str) -> tuple[float, ...]:
      ...
  # Call as: get_embedding("hello", "text-embedding-3-small")

  # NamedTuple — best for structured read-only data
  from typing import NamedTuple
  class LLMStats(NamedTuple):
      model: str
      price_per_1k: float
      context_window: int

  stats = LLMStats("gpt-4", 0.03, 8192)
  print(stats.model)    # named access
  print(stats[0])       # index access
  m, p, c = stats       # unpacking
"""

# Single element tuple — needs trailing comma!
single = (42,)         # tuple
not_tuple = (42)       # just int with parens!
print(f"\nsingle tuple: {type(single)}")    # <class 'tuple'>
print(f"not tuple:    {type(not_tuple)}")   # <class 'int'>

# Tuple unpacking — Pythonic
coordinates = (10.5, 20.3, 5.0)
x, y, z = coordinates

# Extended unpacking
first, *middle, last = (1, 2, 3, 4, 5)
print(f"first={first}, middle={middle}, last={last}")

# Swap — elegant with tuple packing
a, b = 1, 2
a, b = b, a   # internally: (a,b) = (b,a)
print(f"After swap: a={a}, b={b}")


"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COMPREHENSIVE Q&A:

Q: list() vs tuple() — kab use karein?
A: list  → data change hoga, items add/remove karenge
   tuple → data fixed hai, function se multiple values return,
           dict key chahiye, database row represent karna ho

Q: dict mein keys hashable kyun honi chahiye?
A: Dict hash table use karta hai. hash(key) se slot calculate hota hai.
   Mutable objects ka hash change ho sakta hai — isliye not allowed.
   str, int, tuple hashable hain. list, dict, set nahi hain.

Q: Set mein order maintained hota hai?
A: No! Set unordered hai. Order guaranteed nahi.
   Sorted set chahiye? → sorted(my_set)
   Order maintained + unique? → list(dict.fromkeys(items))

Q: dict.get() vs dict[] — kya difference hai?
A: dict["key"] → KeyError if key missing
   dict.get("key") → None if missing (safe)
   dict.get("key", "default") → "default" if missing (safest)

Q: Shallow copy vs Deep copy kya hota hai?
A: Shallow copy: new outer container, same inner objects (shared!)
   Deep copy: new outer + new inner objects (completely independent)
   Use: a.copy() or a[:] for shallow; copy.deepcopy(a) for deep
   Shallow is enough for flat structures; deep needed for nested.
"""
