# Python Anti-Patterns — Common Bugs + Code Smells

## Quick Concepts

**WHAT:**
- **Anti-pattern** = Common solution that LOOKS right but causes bugs/issues
- **Code smell** = Not necessarily wrong but suggests deeper problem
- **Pythonic** = Idiomatic Python (PEP 8, "There should be one obvious way")

**WHY know anti-patterns:**
- Catch juniors disguised as seniors
- Avoid common production bugs
- Code review skills
- Interview "gotcha" rounds

**HOW categorize:**
```
1. Mutable defaults     → Hidden state bugs
2. Late binding         → Loop closure surprises
3. Exception handling   → Silent failures
4. Iteration            → Modifying during iter
5. Threading            → Race conditions
6. Imports              → Circular dependencies
7. Performance          → Premature optimization
8. Style                → Unreadable code
```

---

## Interview Questions & Answers

### Q1: Mutable default arguments — why dangerous?

**Answer:**

**WHAT:** Default arguments evaluated ONCE at function definition.

**HOW the bug works:**

```python
# ❌ BUG
def add_user(user, users=[]):
    users.append(user)
    return users


print(add_user("Alice"))  # ['Alice']
print(add_user("Bob"))    # ['Alice', 'Bob'] ⚠️ NOT just ['Bob']
print(add_user("Carol"))  # ['Alice', 'Bob', 'Carol']

# WHY: `users=[]` is created ONCE when function defined
# Same list reused across calls!
```

**HOW — Demonstrate the issue:**

```python
def show_id(items=[]):
    print(f"id={id(items)}")
    items.append("x")

show_id()  # id=140123, items=['x']
show_id()  # id=140123 (SAME), items=['x', 'x']
show_id()  # id=140123 (SAME), items=['x', 'x', 'x']

# ⭐ Same object across all calls
```

**HOW — FIX:**

```python
# ✅ Use None sentinel
def add_user(user, users=None):
    if users is None:
        users = []  # ⭐ NEW list each call
    users.append(user)
    return users


print(add_user("Alice"))  # ['Alice']
print(add_user("Bob"))    # ['Bob'] ✅
```

**Same applies to all mutable defaults:**

```python
# ❌ All these are bugs
def func(x={}): ...
def func(x=set()): ...
def func(x=[]): ...
def func(x=MyClass()): ...   # Even objects!


# ✅ Use None
def func(x=None):
    if x is None:
        x = {}  # or [] or set() or MyClass()
```

---

### Q2: Late binding closures in loops?

**Answer:**

**WHAT:** Closures capture VARIABLE, not value.

**HOW the bug:**

```python
# ❌ BUG
funcs = []
for i in range(5):
    funcs.append(lambda: i)

for f in funcs:
    print(f())
# Output: 4, 4, 4, 4, 4 ⚠️ ALL print 4 (last value of i)

# WHY: Each lambda captures `i` by reference
# By time they execute, i = 4 (last value)
```

**HOW — FIXES:**

```python
# ✅ FIX 1: Default argument (captures at definition)
funcs = []
for i in range(5):
    funcs.append(lambda x=i: x)  # ⭐ x=i captures NOW

for f in funcs:
    print(f())  # 0, 1, 2, 3, 4 ✅


# ✅ FIX 2: functools.partial
from functools import partial

def echo(x):
    return x

funcs = [partial(echo, i) for i in range(5)]


# ✅ FIX 3: Comprehension with explicit binding
funcs = [(lambda x: lambda: x)(i) for i in range(5)]


# ✅ FIX 4: Use a class instead
class Echo:
    def __init__(self, value):
        self.value = value
    def __call__(self):
        return self.value

funcs = [Echo(i) for i in range(5)]
```

---

### Q3: Bare except — silent bug?

**Answer:**

**WHAT:** `except:` catches EVERYTHING, including system exits.

**HOW the bug:**

```python
# ❌ BUG
def do_thing():
    try:
        risky_operation()
    except:  # ⚠️ Catches EVERYTHING
        pass  # Silent fail


# Problems:
# 1. Catches KeyboardInterrupt (Ctrl-C ignored!)
# 2. Catches SystemExit (sys.exit() ignored!)
# 3. Catches MemoryError (out of memory hidden!)
# 4. Hides actual bugs
# 5. No way to debug
```

**HOW — FIX:**

```python
# ✅ Catch specific exceptions
def do_thing():
    try:
        risky_operation()
    except ValueError as e:
        # Handle ValueError specifically
        log.error("validation failed", error=str(e))
    except IOError as e:
        # Handle I/O errors
        log.error("io error", error=str(e))


# ✅ If you MUST catch all (rare), use Exception (not bare except)
try:
    risky_operation()
except Exception as e:  # ⭐ Doesn't catch SystemExit, KeyboardInterrupt
    log.error("unexpected error", error=str(e), exc_info=True)
    raise  # ⭐ Re-raise unless you can recover


# ✅ Log before re-raising
try:
    risky_operation()
except Exception:
    log.exception("failed in critical section")  # Logs full traceback
    raise
```

---

### Q4: Catching too broad — masks bugs?

**Answer:**

**HOW:**

```python
# ❌ BAD
def parse_user(data):
    try:
        return User(name=data["name"], age=int(data["age"]))
    except Exception:
        return None  # ⚠️ ANY error → None (typo bugs hidden)


# Problems:
# - data["nmae"] (typo) → KeyError → None
# - int("abc") → ValueError → None
# - data is None → AttributeError → None
# - All look the same!


# ✅ GOOD
def parse_user(data):
    try:
        return User(name=data["name"], age=int(data["age"]))
    except (KeyError, ValueError, TypeError) as e:  # ⭐ Specific
        log.warning("user parse failed", error=str(e), data=data)
        return None
    # AttributeError, MemoryError, etc. propagate (real bugs)
```

---

### Q5: == vs is — confusion?

**Answer:**

**WHAT:**
- `==` checks VALUE equality
- `is` checks IDENTITY (same object in memory)

**HOW common bugs:**

```python
# ❌ BUG 1: Using is for value comparison
x = 1000
y = 1000
print(x == y)  # True ✅
print(x is y)  # False ⚠️ (different objects, same value)


# Tricky: small ints cached
a = 5
b = 5
print(a is b)  # True (cached pool -5 to 256)

a = 1000
b = 1000
print(a is b)  # False (not cached)


# ⭐ RULE: Use `is` only for sentinels
# Use `is None`, `is True`, `is False`
# Use `==` for everything else
```

**HOW — Correct usage:**

```python
# ✅ None check
if x is None: ...  # ⭐ ALWAYS use `is`
if x is not None: ...


# ❌ Wrong
if x == None: ...  # Works but unpythonic


# ✅ Boolean check (special case)
if flag is True: ...  # Strictly True
if flag: ...           # ⭐ Truthy (covers any truthy value)
if flag is False: ...  # Strictly False
if not flag: ...       # ⭐ Falsy


# ✅ Value comparison
if x == 5: ...
if name == "Alice": ...
if list_a == list_b: ...
```

---

### Q6: Modifying list during iteration?

**Answer:**

**WHAT:** Modifying collection while iterating = undefined behavior.

**HOW the bug:**

```python
# ❌ BUG
items = [1, 2, 3, 4, 5]
for item in items:
    if item % 2 == 0:
        items.remove(item)  # ⚠️ Skips items!

print(items)  # [1, 3, 5] ← might look correct but...

# Try this:
items = [1, 2, 2, 3, 4]
for item in items:
    if item == 2:
        items.remove(item)

print(items)  # [1, 2, 3, 4] ⚠️ One 2 left!
```

**HOW — FIXES:**

```python
# ✅ FIX 1: Iterate over copy
items = [1, 2, 3, 4, 5]
for item in items[:]:  # ⭐ Copy with [:]
    if item % 2 == 0:
        items.remove(item)


# ✅ FIX 2: List comprehension (preferred)
items = [i for i in items if i % 2 != 0]


# ✅ FIX 3: Filter
items = list(filter(lambda i: i % 2 != 0, items))


# ✅ FIX 4: Iterate backwards
for i in range(len(items) - 1, -1, -1):
    if items[i] % 2 == 0:
        del items[i]


# Same applies to dict
d = {"a": 1, "b": 2, "c": 3}
for key in d:  # ❌ Bug if you delete during iter
    if d[key] > 1:
        del d[key]

# ✅ FIX: Iterate over keys copy
for key in list(d.keys()):
    if d[key] > 1:
        del d[key]
```

---

### Q7: Type checking with type() vs isinstance()?

**Answer:**

**HOW:**

```python
# ❌ BAD: type() check
class Animal: pass
class Dog(Animal): pass

dog = Dog()
print(type(dog) == Animal)  # False ⚠️ (exact type)


# ✅ GOOD: isinstance()
print(isinstance(dog, Animal))  # True ✅ (handles inheritance)


# isinstance also supports tuple
def is_number(x):
    return isinstance(x, (int, float, complex))


# ✅ For protocol checking
from typing import Iterable
def process(items):
    if not isinstance(items, Iterable):
        raise TypeError("Need iterable")
```

---

### Q8: String concatenation in loops?

**Answer:**

**WHAT:** Strings are immutable; `+=` creates new string each time.

**HOW the bug:**

```python
# ❌ BAD: O(n²) — creates new string each iteration
result = ""
for word in words:
    result += word + " "
# 1M words = 1 trillion ops (slow!)


# ✅ GOOD: O(n) — single allocation
result = " ".join(words)


# Or for building gradually
parts = []
for word in words:
    parts.append(word)
result = " ".join(parts)


# Or use io.StringIO for complex building
from io import StringIO
buf = StringIO()
for word in words:
    buf.write(word)
    buf.write(" ")
result = buf.getvalue()
```

**Benchmark:**

```python
import time

words = ["hello"] * 1_000_000

# Bad
start = time.time()
result = ""
for w in words:
    result += w
print(f"Bad: {time.time() - start:.2f}s")  # ~10s

# Good
start = time.time()
result = "".join(words)
print(f"Good: {time.time() - start:.4f}s")  # ~0.01s
```

---

### Q9: Using global state?

**Answer:**

**WHAT:** Module-level mutable state.

**HOW the bug:**

```python
# ❌ BAD
counter = 0
cache = {}

def increment():
    global counter
    counter += 1


# Problems:
# - Hard to test (test pollution)
# - Threading issues (race conditions)
# - Hidden dependencies
# - Hard to refactor
```

**HOW — FIXES:**

```python
# ✅ FIX 1: Class instance state
class Counter:
    def __init__(self):
        self.value = 0
        self.cache = {}

    def increment(self):
        self.value += 1


counter = Counter()


# ✅ FIX 2: Closure (functional)
def make_counter():
    count = 0
    def increment():
        nonlocal count
        count += 1
        return count
    return increment


counter = make_counter()


# ✅ FIX 3: Dependency injection (best)
def increment(counter: dict) -> None:
    counter["value"] += 1


# ✅ FIX 4: contextvars (per-task state)
from contextvars import ContextVar
request_id = ContextVar("request_id")
```

---

### Q10: Premature optimization?

**Answer:**

**WHAT:** Optimizing before profiling.

**HOW the anti-pattern:**

```python
# ❌ Optimizing for nothing
def get_users():
    # Worried about list creation cost
    return tuple(db.fetch_all())  # ⚠️ Tuple "faster"?

# Reality: tuple vs list = negligible difference
# Premature optimization = ugly code, no benefit


# ❌ Caching everything
@lru_cache(maxsize=None)
def add(x, y):
    return x + y  # ⚠️ Cache overhead > function cost


# ❌ Using regex for simple string ops
import re
if re.match(r"^hello", text):  # ⚠️ Overkill
    pass

# Better: text.startswith("hello")
```

**HOW — RIGHT approach:**

```python
# ✅ Profile FIRST, optimize SECOND
import cProfile
cProfile.run("my_app()")

# Identify hot spot (e.g., function X takes 80% time)

# Optimize hot spot:
# 1. Better algorithm
# 2. Caching with @lru_cache (where it helps)
# 3. C extension (numpy, cython)
# 4. Async/threading if I/O bound


# ⭐ Donald Knuth: "Premature optimization is the root of all evil"
```

---

### Q11: Magic numbers?

**Answer:**

**WHAT:** Unexplained numbers in code.

**HOW the bug:**

```python
# ❌ BAD
def calculate_price(quantity):
    if quantity > 100:
        return quantity * 9.50
    elif quantity > 50:
        return quantity * 10.25
    else:
        return quantity * 11.00


# What's 9.50? 10.25? Why 100, 50?
```

**HOW — FIX:**

```python
# ✅ Named constants
BULK_DISCOUNT_THRESHOLD = 100
MEDIUM_DISCOUNT_THRESHOLD = 50
PRICE_BULK = 9.50
PRICE_MEDIUM = 10.25
PRICE_REGULAR = 11.00


def calculate_price(quantity: int) -> float:
    if quantity > BULK_DISCOUNT_THRESHOLD:
        return quantity * PRICE_BULK
    elif quantity > MEDIUM_DISCOUNT_THRESHOLD:
        return quantity * PRICE_MEDIUM
    else:
        return quantity * PRICE_REGULAR


# ✅ Or use Enum
from enum import Enum

class Tier(Enum):
    BULK = (100, 9.50)
    MEDIUM = (50, 10.25)
    REGULAR = (0, 11.00)
```

---

### Q12: Not using context managers?

**Answer:**

**HOW the bug:**

```python
# ❌ BAD: Manual cleanup
f = open("file.txt")
data = f.read()
f.close()  # ⚠️ If exception above, file not closed


# ✅ GOOD: Context manager
with open("file.txt") as f:
    data = f.read()
# ⭐ Auto-closes even on exception


# Same for connections
import sqlite3
with sqlite3.connect("db.sqlite") as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")


# Same for threading
from threading import Lock
lock = Lock()
with lock:
    # critical section
    pass
```

---

### Q13: Bad exception messages?

**Answer:**

**HOW:**

```python
# ❌ BAD
def get_user(user_id):
    user = db.find(user_id)
    if not user:
        raise Exception("Error")  # ⚠️ Useless


# ✅ GOOD
def get_user(user_id):
    user = db.find(user_id)
    if not user:
        raise UserNotFoundError(
            f"User with id={user_id} not found in database"
        )


# ✅ EVEN BETTER: Custom exception with context
class UserNotFoundError(Exception):
    def __init__(self, user_id, db_name=None):
        self.user_id = user_id
        self.db_name = db_name
        super().__init__(f"User {user_id} not found")


# Caller can:
try:
    user = get_user(123)
except UserNotFoundError as e:
    log.error("user not found", user_id=e.user_id)
```

---

### Q14: Comparing floats for equality?

**Answer:**

**WHAT:** Floating point precision issues.

**HOW the bug:**

```python
# ❌ BAD
a = 0.1 + 0.2
b = 0.3
print(a == b)  # False ⚠️ (0.30000000000000004 != 0.3)


# ✅ GOOD: math.isclose
import math
print(math.isclose(a, b))  # True


# ✅ With tolerance
math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)


# ✅ Or use Decimal for exact math
from decimal import Decimal
a = Decimal("0.1") + Decimal("0.2")
b = Decimal("0.3")
print(a == b)  # True ✅
```

---

### Q15: Print vs logging?

**Answer:**

**HOW:**

```python
# ❌ BAD: print in production code
def process(data):
    print(f"Processing {data}")
    # Output goes to stdout
    # No level filtering
    # No timestamp
    # Hard to disable


# ✅ GOOD: logging
import logging
log = logging.getLogger(__name__)

def process(data):
    log.debug("Processing", data=data)
    # ⭐ Has level (filter in prod)
    # ⭐ Has timestamp
    # ⭐ Can route to file/syslog
    # ⭐ Can format as JSON
```

---

## Anti-Pattern Checklist (Code Review)

```markdown
### Function Design
- [ ] No mutable default args
- [ ] No global state mutation
- [ ] Type hints on all functions
- [ ] Docstrings for public APIs

### Error Handling
- [ ] No bare except
- [ ] No `except Exception: pass`
- [ ] Specific exception types caught
- [ ] Useful error messages
- [ ] exc_info=True for logging exceptions

### Iteration
- [ ] No modifying list during iter
- [ ] List comprehension over loops where simple
- [ ] " ".join() not += in loops
- [ ] Use enumerate, not manual counter

### Comparisons
- [ ] `is None` not `== None`
- [ ] `isinstance()` not `type()`
- [ ] `math.isclose()` for floats
- [ ] `Decimal` for currency

### Imports
- [ ] No circular imports
- [ ] Standard library imports first
- [ ] No wildcard imports (`from x import *`)
- [ ] Lazy imports for expensive modules

### Performance
- [ ] No premature optimization
- [ ] Profile before optimizing
- [ ] Cache where measured to help
- [ ] No regex for simple string ops

### Style
- [ ] No magic numbers (use constants)
- [ ] Context managers for resources
- [ ] Logging not print
- [ ] f-strings for formatting

### Threading
- [ ] No shared mutable state without lock
- [ ] queue.Queue for thread communication
- [ ] threading.local for per-thread data
- [ ] No race conditions on counters
```

---

## Code Review Red Flags

```python
# 🚩 Red flag patterns to watch for:

# 1. Mutable default
def f(x=[]): ...

# 2. Bare except
try: ...
except: ...

# 3. Late binding
funcs = [lambda: i for i in range(5)]

# 4. Modifying iter
for x in items: items.remove(x)

# 5. Global mutation
global counter; counter += 1

# 6. == None
if x == None: ...

# 7. Hardcoded values
if quantity > 100: ...

# 8. Bare Exception
raise Exception("error")

# 9. eval/exec on input
eval(user_input)  # Code injection!

# 10. Float equality
if a == 0.1 + 0.2: ...

# 11. type() check
if type(x) == int: ...

# 12. String concat in loop
result = ""
for x in items: result += x

# 13. Print debugging
print(f"DEBUG: {var}")
```

---

## Pythonic Replacements Cheatsheet

| Anti-pattern | Pythonic |
|---|---|
| `if x == None` | `if x is None` |
| `if len(items) == 0` | `if not items` |
| `if len(items) > 0` | `if items` |
| `for i in range(len(items))` | `for i, item in enumerate(items)` |
| `result = []; for x: result.append(...)` | `[... for x]` |
| `result = ""; for x: result += x` | `"".join(items)` |
| `try: x = d[k]; except KeyError: x = default` | `x = d.get(k, default)` |
| `if "a" in d: x = d["a"]` | `x = d.get("a")` |
| `d.has_key("a")` | `"a" in d` (Python 3) |
| `type(x) == int` | `isinstance(x, int)` |
| Multiple `with` lines | Parenthesized `with` (3.10+) |
| `Optional[X]` | `X \| None` (3.10+) |
| `List[X], Dict[K,V]` | `list[X], dict[K, V]` (3.9+) |
| `from typing import Union` | `X \| Y` (3.10+) |
