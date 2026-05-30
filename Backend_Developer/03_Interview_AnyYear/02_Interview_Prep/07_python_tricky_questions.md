# Python Tricky Interview Questions — Senior-Level Gotchas

> The questions that separate juniors from seniors. Each one comes with: code → predict output → explanation → "why this matters in production".

---

## CATEGORY 1 — LANGUAGE GOTCHAS

### Q1. Mutable default argument

```python
def append_one(items=[]):
    items.append(1)
    return items

print(append_one())  # [1]
print(append_one())  # [1, 1]  ← WHY?
print(append_one())  # [1, 1, 1]
```

**Why:** Default args are evaluated **once at function definition time**, not per call. The list is shared across calls.

**Fix:**
```python
def append_one(items=None):
    if items is None:
        items = []
    items.append(1)
    return items
```

**Production impact:** This bug shows up in Django views, FastAPI dependencies, cache decorators. Once it bit someone, they remember it forever.

---

### Q2. Late binding in closures

```python
funcs = [lambda: i for i in range(3)]
print([f() for f in funcs])  # [2, 2, 2]  ← not [0, 1, 2]!
```

**Why:** `i` is looked up when lambda is *called*, not when defined. By then, loop is done and `i == 2`.

**Fix:**
```python
funcs = [lambda i=i: i for i in range(3)]  # bind at def time
# or
funcs = [partial(lambda x: x, i) for i in range(3)]
```

---

### Q3. `is` vs `==`

```python
a = 256
b = 256
print(a is b)  # True

a = 257
b = 257
print(a is b)  # False ... wait, what?
```

**Why:** CPython interns small ints (-5 to 256) and short strings. Beyond that, identity differs.

**Rule:** Use `is` only for `None`, `True`, `False`, and singletons. Use `==` for values.

---

### Q4. List multiplication trap

```python
matrix = [[0] * 3] * 3
matrix[0][0] = 1
print(matrix)  # [[1,0,0], [1,0,0], [1,0,0]]  ← not what you want!
```

**Why:** `[[0]*3] * 3` creates 3 references to the *same* inner list.

**Fix:**
```python
matrix = [[0] * 3 for _ in range(3)]
```

---

### Q5. Chained comparisons

```python
print(1 < 2 < 3)         # True
print(1 < 2 > 1)         # True
print(False == False == True)  # False ?!
```

**Why:** `1 < 2 < 3` is `(1 < 2) and (2 < 3)`. `False == False == True` is `(False == False) and (False == True)` = `True and False` = `False`.

---

### Q6. `+=` vs `x = x + ...` on lists in shared state

```python
def use_iadd(x):
    x += [4]          # __iadd__: mutates the list in place
    return x

def use_concat(x):
    x = x + [4]       # builds a NEW list, rebinds local x only
    return x

a = [1, 2, 3]
use_iadd(a)
print(a)              # [1, 2, 3, 4]  ← caller's list IS mutated

b = [1, 2, 3]
use_concat(b)
print(b)              # [1, 2, 3]     ← caller's list unchanged
```

**Why:** For lists, `+=` calls `__iadd__`, which mutates the list in place (like `.extend()`) and returns the *same* object — so the caller sees the change. `x = x + [4]` builds a brand-new list and only rebinds the local name `x`; the caller's list is untouched. So `+=` and `x = x + ...` are **not** equivalent for mutable types.

---

### Q7. Tuple with one element

```python
print(type((1)))    # <class 'int'>     ← parens, not tuple
print(type((1,)))   # <class 'tuple'>   ← trailing comma needed
print(type(()))     # <class 'tuple'>   ← empty tuple
```

**Why:** `(x)` is grouping; `(x,)` is tuple. The trailing comma is the marker.

---

### Q8. Dict comprehension shadowing

```python
x = 10
d = {x: y for x in range(3) for y in range(3)}
print(x)  # 10 ← preserved! comprehensions have own scope (Py3+)
```

**Why:** List/dict/set comps in Python 3 have their own scope (fixed from Python 2 leak).

---

### Q9. Multiple assignment + mutation

```python
a = b = []
a.append(1)
print(b)  # [1]
```

**Why:** `a = b = []` makes both names point to the *same* list. Common bug for "two empty lists".

---

### Q10. Augmented assignment with tuple in dict

```python
d = {"a": (1, 2)}
try:
    d["a"][0] += 1
except TypeError as e:
    print(e)  # 'tuple' object does not support item assignment
# But what about d["a"] += (3,)?
d["a"] += (3,)
print(d["a"])  # (1, 2, 3)
```

`+=` on tuple creates a new tuple, which gets stored back in the dict.

---

## CATEGORY 2 — GIL, THREADING, ASYNC

### Q11. Why is the GIL a problem (and when is it NOT)?

```python
import threading
counter = 0

def inc(n):
    global counter
    for _ in range(n):
        counter += 1

t1 = threading.Thread(target=inc, args=(1_000_000,))
t2 = threading.Thread(target=inc, args=(1_000_000,))
t1.start(); t2.start()
t1.join(); t2.join()
print(counter)  # NOT 2,000,000 — race condition
```

**GIL:** Only one Python opcode runs at a time, BUT `counter += 1` is multiple opcodes (LOAD, ADD, STORE). Context switch can happen mid-update.

**GIL is fine for:** IO-bound (released during system calls, sleeps, network).
**GIL hurts:** CPU-bound multi-threaded code → use `multiprocessing` or `concurrent.futures.ProcessPoolExecutor`.

**Python 3.13+:** Optional no-GIL mode (PEP 703), experimental.

---

### Q12. Async deadlock — predict

```python
import asyncio
lock = asyncio.Lock()

async def task():
    async with lock:
        await another()  # also acquires lock!

async def another():
    async with lock:
        pass

asyncio.run(task())  # hangs forever
```

**Fix:** Use `asyncio.Lock`'s reentrant version isn't built-in; use `RLock` from `threading` carefully or restructure.

**Better fix:** Don't nest lock acquisitions; restructure code.

---

### Q13. `asyncio.gather` vs `asyncio.TaskGroup` (Python 3.11+)

```python
# Old style — error in one task doesn't cancel others by default
async def gather_demo():
    results = await asyncio.gather(t1(), t2(), t3(), return_exceptions=True)

# New style — error cancels all others, structured concurrency
async def tg_demo():
    async with asyncio.TaskGroup() as tg:
        tg.create_task(t1())
        tg.create_task(t2())
        tg.create_task(t3())
```

**Use TaskGroup** for new code — structured concurrency, atomic group cancellation.

---

### Q14. Why this async code is broken

```python
import asyncio
import time

async def slow():
    time.sleep(2)   # ← blocks event loop!
    return "done"

async def main():
    return await asyncio.gather(slow(), slow(), slow())

asyncio.run(main())  # takes 6 seconds, not 2
```

**Why:** `time.sleep` is blocking sync call. Event loop is single-threaded; you must use `await asyncio.sleep(2)`.

**Detect:** `asyncio.get_event_loop().slow_callback_duration = 0.1` warns on blocking callbacks.

---

### Q15. Coroutine never awaited

```python
async def fire_and_forget():
    print("hi")

fire_and_forget()  # warning: coroutine was never awaited
```

**Why:** Calling an async function returns a coroutine; you must `await` it or `asyncio.create_task()` it.

**Production trap:** `await some_async_func` vs `some_async_func()` — forgetting `await` returns a coroutine object that you then unintentionally store/return.

---

### Q16. Threading + signal handlers

```python
# Signals only delivered to main thread.
# This handler in a background thread will NEVER fire.
threading.Thread(target=lambda: signal.signal(signal.SIGINT, handler)).start()
```

**Always** register signal handlers in main thread before starting workers.

---

### Q17. Spawn vs fork vs forkserver

| Method | OS | Fork-safe? | Speed |
|---|---|---|---|
| fork | Linux/Mac | risky (locks, threads copied) | fast |
| spawn | Windows default; safer | no inheritance | slow |
| forkserver | Linux only, dedicated forker | safer than fork | medium |

**macOS Catalina+:** spawn is default → globals don't transfer to child.

```python
import multiprocessing as mp
mp.set_start_method("spawn", force=True)
```

---

## CATEGORY 3 — OOP & DESCRIPTORS

### Q18. MRO (Method Resolution Order) — predict

```python
class A: pass
class B(A): pass
class C(A): pass
class D(B, C): pass

print(D.__mro__)
# (D, B, C, A, object) — C3 linearization
```

**Diamond problem solved:** Python uses C3 linearization. Read left-to-right, depth-first, no duplicates.

---

### Q19. `__new__` vs `__init__`

```python
class Singleton:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self.x = 1  # called every time, even on existing instance!

a = Singleton(); a.x = 99
b = Singleton(); print(b.x)  # 1 ← __init__ ran again
```

**Lesson:** `__init__` runs every call, even if `__new__` returns existing instance. Use a flag if you want one-time init.

---

### Q20. Properties + inheritance trap

```python
class A:
    @property
    def x(self):
        return self._x
    @x.setter
    def x(self, v):
        self._x = v

class B(A):
    @property      # ← overrides A.x, no setter!
    def x(self):
        return self._x * 2

b = B()
b.x = 5  # AttributeError: can't set attribute
```

**Fix:** Re-declare setter in subclass, or `B.x = B.x.setter(...)`.

---

### Q21. Descriptors — manual implementation

```python
class TypedAttribute:
    def __init__(self, expected_type):
        self.expected_type = expected_type

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, obj, objtype=None):
        return obj.__dict__.get(self.name)

    def __set__(self, obj, value):
        if not isinstance(value, self.expected_type):
            raise TypeError(f"{self.name} must be {self.expected_type}")
        obj.__dict__[self.name] = value

class User:
    name = TypedAttribute(str)
    age = TypedAttribute(int)

u = User()
u.name = "alice"     # ok
u.age = "twenty"     # TypeError
```

**Used by:** Django ORM fields, SQLAlchemy columns, Pydantic.

---

### Q22. `__slots__` impact

```python
class Regular:
    pass

class Slotted:
    __slots__ = ("x", "y")

import sys
r = Regular(); r.x = 1
s = Slotted();  s.x = 1
print(sys.getsizeof(r.__dict__))  # ~64 bytes
print(sys.getsizeof(s))            # ~48 bytes, no __dict__
```

**Trade-offs:**
- ✓ ~40% less memory per instance.
- ✓ Faster attribute access.
- ✗ Can't add attributes dynamically.
- ✗ Multiple inheritance painful.

**Use for:** millions of small objects (graph nodes, data records).

---

### Q23. Metaclass — when to actually use?

```python
class SingletonMeta(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]

class Settings(metaclass=SingletonMeta):
    def __init__(self):
        self.debug = False
```

**Real uses:** Django ORM (auto-registers models), Pydantic (validates fields at class creation), ABCs.

**99% of code:** Use a class decorator or `__init_subclass__` instead. Metaclasses are overkill.

---

### Q24. ABC abuse vs Protocol

```python
from abc import ABC, abstractmethod
from typing import Protocol

class StorageABC(ABC):
    @abstractmethod
    def save(self, data): ...

class StorageProto(Protocol):
    def save(self, data) -> None: ...

# ABC: nominal subtyping — must inherit
# Protocol: structural — duck typing with type hints
```

**Modern preference:** `Protocol` for duck typing without inheritance coupling. Better for libraries.

---

## CATEGORY 4 — MEMORY & PERFORMANCE

### Q25. Garbage collection cycles

```python
import gc

class Node:
    def __init__(self):
        self.next = None

a = Node()
b = Node()
a.next = b
b.next = a   # cycle!

del a, b
# refcount alone wouldn't free these — they reference each other.
gc.collect()  # cycle detector frees them
```

**Detection:** `gc.set_debug(gc.DEBUG_LEAK)`.

**Avoid cycles:** Use `weakref` for back-pointers.

---

### Q26. Why `id(a) == id(b)` after `b = a`?

```python
a = [1, 2, 3]
b = a
print(id(a) == id(b))  # True

b.append(4)
print(a)  # [1, 2, 3, 4] — same list!
```

Names bind to objects. `=` doesn't copy. Use `copy.copy()` or `list(a)`.

---

### Q27. Copy vs deepcopy

```python
import copy
a = {"users": [{"name": "alice"}]}
b = copy.copy(a)       # shallow
c = copy.deepcopy(a)   # deep

a["users"][0]["name"] = "BOB"
print(b["users"][0]["name"])  # "BOB" — shared!
print(c["users"][0]["name"])  # "alice" — independent
```

**Cost:** deepcopy is expensive on large structures. Use sparingly.

---

### Q28. String concatenation in loop — performance

```python
# ✗ O(N²) — strings immutable, each += creates new string
s = ""
for x in items:
    s += str(x)

# ✓ O(N)
parts = []
for x in items:
    parts.append(str(x))
s = "".join(parts)

# ✓ best
s = "".join(str(x) for x in items)
```

CPython has an optimization for `s += x` in some cases (refcount=1), but don't rely on it.

---

### Q29. Why is `dict.get()` faster than `try/except`?

Not always! In Python:
- "Look before you leap" (`if k in d`): slower if key usually exists.
- "Easier to ask forgiveness" (`try/except`): slower if exception is often raised.

Rule: use `try/except` when the exception is exceptional. Use `if` when it's normal flow.

---

### Q30. `__hash__` and dict key

```python
class Bad:
    def __init__(self, x):
        self.x = x
    def __eq__(self, other):
        return self.x == other.x
    # __hash__ NOT overridden!

d = {Bad(1): "a"}
print(d[Bad(1)])  # KeyError!
```

**Why:** Once `__eq__` is defined, `__hash__` is set to `None` (unhashable). Must define both or neither.

**Fix:**
```python
def __hash__(self):
    return hash(self.x)
```

---

## CATEGORY 5 — TYPING, DATACLASSES, MODERN

### Q31. Dataclass with mutable default — same trap!

```python
from dataclasses import dataclass, field

@dataclass
class Bad:
    items: list = []  # SyntaxError in Py3.11+!

@dataclass
class Good:
    items: list = field(default_factory=list)
```

The dataclass machinery now catches this at definition time.

---

### Q32. `frozen=True` + `__post_init__`

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Point:
    x: int
    y: int

    def __post_init__(self):
        # self.x = abs(self.x)  ← FrozenInstanceError
        object.__setattr__(self, "x", abs(self.x))  # bypass
```

Frozen = immutable. Mutation requires `object.__setattr__` workaround.

---

### Q33. `Optional[X]` vs `X | None`

```python
# Same thing, but X | None requires Py3.10+
def f(x: Optional[int]): ...
def g(x: int | None): ...
```

Use `|` syntax in new code. PEP 604.

---

### Q34. `TypedDict` vs `dataclass` vs `Pydantic`

| Feature | TypedDict | Dataclass | Pydantic |
|---|---|---|---|
| Runtime validation | No | No | Yes |
| Static type hint | Yes | Yes | Yes |
| Mutation | Yes (dict) | Yes | Yes |
| Serialization | Yes (dict) | Manual | `.model_dump()` |
| Performance | Fastest | Fast | Slower (v1), Fast (v2 Rust) |

**Use:**
- `TypedDict`: API response shapes, no validation needed.
- `dataclass`: internal value objects, no I/O.
- `Pydantic`: API I/O validation (FastAPI uses it).

---

### Q35. Pydantic v1 vs v2 — gotcha

```python
# v1
class User(BaseModel):
    name: str
    class Config:
        orm_mode = True

# v2
class User(BaseModel):
    name: str
    model_config = ConfigDict(from_attributes=True)
```

`orm_mode` → `from_attributes`. v2 is Rust-backed, ~5-50x faster but breaking changes.

---

## CATEGORY 6 — EXCEPTIONS & CONTROL FLOW

### Q36. `finally` overrides return

```python
def f():
    try:
        return 1
    finally:
        return 2

print(f())  # 2
```

**Lesson:** `finally` clause's `return` overrides try's. Same for exceptions — finally `return` swallows the exception.

---

### Q37. Catching `Exception` vs `BaseException`

```python
try:
    do_thing()
except Exception:  # catches normal errors
    pass
except KeyboardInterrupt:  # also caught? NO
    pass
```

`Exception` doesn't catch `KeyboardInterrupt`, `SystemExit`, `GeneratorExit`. Use `BaseException` only in truly top-level handlers (and rarely).

---

### Q38. `else` on `try/except`

```python
try:
    x = risky()
except ValueError:
    handle()
else:
    # runs only if NO exception in try block
    process(x)
finally:
    cleanup()
```

Most devs don't know `else` exists in `try`. Use it to scope "what to do after success" tightly.

---

### Q39. Exception chaining

```python
try:
    int("abc")
except ValueError as e:
    raise RuntimeError("Couldn't parse") from e

# Traceback shows BOTH errors
```

Use `from e` to preserve context. `from None` suppresses the original.

---

### Q40. `with` statement and exceptions

```python
class CM:
    def __enter__(self): return self
    def __exit__(self, exc_type, exc, tb):
        return True  # swallows exception!

with CM():
    raise ValueError("oops")
print("alive")  # prints — exception swallowed
```

**Lesson:** `__exit__` returning truthy swallows exceptions. Use `contextlib.suppress(ValueError)` more explicitly.

---

## CATEGORY 7 — GENERATORS & ITERATORS

### Q41. Generator vs iterator

```python
# Iterator (manual)
class Counter:
    def __init__(self, n): self.n = n; self.i = 0
    def __iter__(self): return self
    def __next__(self):
        if self.i >= self.n: raise StopIteration
        self.i += 1
        return self.i - 1

# Generator (sugar)
def counter(n):
    for i in range(n):
        yield i
```

Both produce iterators. Generators are usually 10x shorter and cleaner.

---

### Q42. Generator `send` and coroutines

```python
def echo():
    while True:
        x = yield
        print(f"got: {x}")

g = echo()
next(g)        # prime the generator (advance to first yield)
g.send("hi")   # prints "got: hi"
g.send("bye")  # prints "got: bye"
```

This was Python's coroutine system before `async/await`. Mostly historical now.

---

### Q43. `yield from`

```python
def chain(a, b):
    yield from a
    yield from b

list(chain([1, 2], [3, 4]))  # [1, 2, 3, 4]
```

Delegates iteration. Also propagates `send()` and exceptions. Used heavily in pre-async Python.

---

### Q44. Generator memory advantage

```python
# Eager: builds full list (millions of ints)
sum([i*i for i in range(10_000_000)])

# Lazy: 1 int at a time
sum(i*i for i in range(10_000_000))
```

Difference: ~80MB vs negligible.

---

### Q45. itertools tricks

```python
from itertools import groupby, accumulate, chain, islice

# Sliding window (Py3.12+)
from itertools import pairwise
list(pairwise([1,2,3,4]))  # [(1,2),(2,3),(3,4)]

# Group consecutive
list(groupby([1,1,2,3,3,3]))  # [(1,[1,1]),(2,[2]),(3,[3,3,3])]

# Running total
list(accumulate([1,2,3,4]))   # [1,3,6,10]

# Take N
list(islice(iter(range(100)), 5))  # [0,1,2,3,4]
```

---

## CATEGORY 8 — IMPORT, MODULES, PACKAGES

### Q46. Circular imports — how to fix?

```python
# a.py
from b import B
class A:
    def foo(self): return B()

# b.py
from a import A   # CIRCULAR — ImportError
class B:
    def bar(self): return A()
```

**Fixes:**
1. Move import inside function: `def bar(): from a import A; return A()`.
2. Restructure: extract shared bits to `c.py`.
3. Use forward references with strings (Pydantic, dataclass).

---

### Q47. `__name__ == "__main__"` — why exactly?

When a `.py` is imported as a module, its `__name__` is the module name. When run directly, it's `"__main__"`. The block guards "run only if this file is the entry point."

Critical for `multiprocessing` on Windows/Mac (spawn re-imports the file).

---

### Q48. `from x import *` — what comes through?

```python
# module.py
_secret = 1
public = 2
__all__ = ["public"]   # only this exported by `from module import *`
```

Without `__all__`: all non-underscore names exported.

---

### Q49. Module reloading

```python
import importlib
import mymodule
importlib.reload(mymodule)  # re-executes the module
```

Caveat: existing references to old classes/functions still point to old code. Useful in REPL/dev, dangerous in production.

---

### Q50. `__init__.py` — empty or with logic?

```python
# Empty: package marker only
# With logic: runs at import time of package
# mypkg/__init__.py
from .core import MainClass  # users can do `from mypkg import MainClass`
__version__ = "1.0.0"
```

Don't put heavy work in `__init__.py` (slow imports). Lazy-load via `__getattr__` (PEP 562).

---

## CATEGORY 9 — REAL-WORLD INTERVIEW FAVORITES

### Q51. Implement `@cached_property` from scratch

```python
class cached_property:
    def __init__(self, fn):
        self.fn = fn
        self.attr = fn.__name__

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        val = self.fn(obj)
        obj.__dict__[self.attr] = val  # bypass descriptor on next access
        return val
```

Then `from functools import cached_property` — Py 3.8+.

---

### Q52. Implement `@contextmanager` from scratch

```python
from functools import wraps

def contextmanager(fn):
    @wraps(fn)
    def helper(*args, **kwargs):
        gen = fn(*args, **kwargs)
        class CM:
            def __enter__(self): return next(gen)
            def __exit__(self, *exc):
                try:
                    next(gen)
                except StopIteration: return
                else: raise RuntimeError("generator didn't stop")
        return CM()
    return helper

@contextmanager
def my_cm():
    print("setup")
    yield 42
    print("teardown")
```

---

### Q53. Implement `lru_cache` from scratch

```python
from functools import wraps
from collections import OrderedDict

def lru_cache(maxsize=128):
    def decorator(fn):
        cache = OrderedDict()
        @wraps(fn)
        def wrapper(*args):
            if args in cache:
                cache.move_to_end(args)
                return cache[args]
            result = fn(*args)
            cache[args] = result
            if len(cache) > maxsize:
                cache.popitem(last=False)
            return result
        return wrapper
    return decorator
```

---

### Q54. Implement a decorator with optional arguments

```python
def retry(fn=None, *, attempts=3):
    def decorator(fn):
        def wrapper(*args, **kwargs):
            for i in range(attempts):
                try:
                    return fn(*args, **kwargs)
                except Exception:
                    if i == attempts - 1: raise
        return wrapper
    if fn is not None:
        return decorator(fn)  # @retry
    return decorator          # @retry(attempts=5)

@retry
def a(): ...

@retry(attempts=5)
def b(): ...
```

---

### Q55. Deep dive: what does `super()` do without args?

```python
class A:
    def greet(self): return "A"

class B(A):
    def greet(self): return super().greet() + "B"

print(B().greet())  # "AB"
```

`super()` (no args) uses two implicit arguments: `__class__` and the first method arg (`self`). It walks MRO.

In Python 2 you had to write `super(B, self).greet()`. Py3 auto-fills.

---

## How interviewers use these

1. **One question → "Why?"** — they're testing depth, not lookup speed.
2. **Show implementation knowledge** — "Yeah, this works because dict is implemented as open-addressed hash table."
3. **Connect to production** — "I once saw this in code that..."

**Goal:** Sound like someone who's debugged Python at 3am, not someone who learned from a textbook.
