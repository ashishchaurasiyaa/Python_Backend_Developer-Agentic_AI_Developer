# Core Python & OOP Interview Q&A

> Format: **Q** → short answer → code/deep dive → follow-up. This is the round before the round — almost every backend interview opens with 5–10 minutes of "explain X" before moving to coding or system design. Deep-dive material lives in [`01_Year3-4_Mid/01_Python_Advanced/`](../../01_Year3-4_Mid/01_Python_Advanced/) and [`00_Year0-2_Junior/02_Python_Daily/`](../../00_Year0-2_Junior/02_Python_Daily/) — this file condenses both into interview-answer form.

---

## SECTION 1 — OOP FUNDAMENTALS (Q1–Q10)

### Q1. What are the four pillars of OOP, and give a Python-specific example of each?

- **Encapsulation** — bundling data + behavior, controlling access with `_protected` / `__name_mangled` conventions (Python has no true `private`).
- **Abstraction** — hiding implementation via `ABC`/`Protocol`; caller only sees the interface.
- **Inheritance** — `class Dog(Animal):` — reuse + specialize.
- **Polymorphism** — same method name, different behavior per type (`len()` works on lists, strings, dicts because each implements `__len__`).

**Follow-up:** *"Does Python enforce encapsulation?"* → No. `_x` is a convention (leave alone), `__x` triggers name mangling (`_ClassName__x`) to avoid subclass collisions, not to hide data — it's still accessible.

---

### Q2. `@classmethod` vs `@staticmethod` vs instance method — when do you use each?

```python
class User:
    count = 0
    def __init__(self, name):
        self.name = name
        User.count += 1

    def greet(self):                      # instance method — needs self
        return f"Hi, {self.name}"

    @classmethod
    def from_dict(cls, data):              # classmethod — needs cls, used as alt constructor
        return cls(data["name"])

    @staticmethod
    def is_valid_name(name):               # staticmethod — needs neither, just namespacing
        return len(name) > 0
```

**Rule of thumb:** needs instance state → instance method. Needs the class (alt constructors, factory patterns) → `classmethod`. Needs neither → `staticmethod` (could just be a module function, but grouped for organization).

**Production use:** Django/DRF `Model.objects.create()`-style factories, Pydantic's `@classmethod` validators, ORM `from_orm`.

---

### Q3. What is MRO (Method Resolution Order) and why does it matter?

MRO decides which class's method runs when multiple inheritance is involved. Python uses **C3 linearization**.

```python
class A:
    def hello(self): return "A"
class B(A):
    def hello(self): return "B"
class C(A):
    def hello(self): return "C"
class D(B, C):
    pass

print(D().hello())     # "B" — MRO is D → B → C → A → object
print(D.__mro__)
```

**Why it matters:** Django's class-based views and DRF mixins rely on MRO — `class MyView(CreateAPIView, UpdateAPIView)` resolves `.post()`/`.put()` through cooperative `super()` calls across the MRO chain. Get the mixin order wrong and the wrong method wins silently.

---

### Q4. `super()` — what does it actually do, and why not just call `ParentClass.method(self)` directly?

`super()` follows the **MRO**, not just "my direct parent." In single inheritance the difference is invisible; in multiple/diamond inheritance, calling the parent class by name breaks cooperative chains — every class in the hierarchy must call `super().__init__()` for the chain to reach `object.__init__()` correctly.

```python
class Base:
    def __init__(self):
        print("Base")
class A(Base):
    def __init__(self):
        super().__init__()
        print("A")
class B(Base):
    def __init__(self):
        super().__init__()
        print("B")
class C(A, B):
    def __init__(self):
        super().__init__()
        print("C")

C()  # Base, B, A, C — each super() call moves to the NEXT class in C's MRO, not "my parent"
```

---

### Q5. Composition vs inheritance — how do you decide?

**Rule:** "is-a" → inheritance. "has-a" / "uses-a" → composition. Prefer composition when behavior needs to change at runtime or when the relationship is really about capability, not identity.

```python
# Inheritance — Dog IS-A Animal, correct
class Animal: ...
class Dog(Animal): ...

# Composition — Car HAS-A Engine, not IS-A
class Engine:
    def start(self): ...
class Car:
    def __init__(self, engine: Engine):
        self.engine = engine   # can swap engines without changing Car's class
```

**Interview answer:** "Deep inheritance hierarchies are brittle — a change two levels up breaks three levels down. Composition + dependency injection (what FastAPI's `Depends()` and Django's service-layer pattern both lean on) keeps components swappable and testable in isolation." Full pattern comparison: [`15_Design_Patterns_SOLID/Section_02_SOLID_Principles/`](../../01_Year3-4_Mid/15_Design_Patterns_SOLID/Section_02_SOLID_Principles/).

---

### Q6. What's the difference between `__new__` and `__init__`?

`__new__` **creates** the instance (allocates memory, returns the object) — it's a `staticmethod` under the hood. `__init__` **initializes** an already-created instance — returns `None`.

```python
class Singleton:
    _instance = None
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
```

**When you need `__new__`:** immutable types (subclassing `int`/`str`/`tuple`), singleton pattern, metaclasses, controlling whether an instance is even created (caching/pooling).

---

### Q7. Abstract Base Classes (`ABC`) vs `Protocol` — when do you reach for which?

- **`ABC`** — nominal typing. Subclass must explicitly inherit and implement `@abstractmethod`s. Enforced at instantiation time.
- **`Protocol`** (structural typing / "duck typing with type hints") — no inheritance needed. If it has the right shape, it satisfies the protocol.

```python
from abc import ABC, abstractmethod
from typing import Protocol

class Shape(ABC):                      # nominal — must inherit
    @abstractmethod
    def area(self) -> float: ...

class Sized(Protocol):                  # structural — no inheritance needed
    def __len__(self) -> int: ...

def total_size(items: list[Sized]) -> int:
    return sum(len(i) for i in items)   # any object with __len__ works — lists, strings, custom classes
```

**Interview answer:** "Use `ABC` when you own the hierarchy and want to force a contract (plugin systems, strategy pattern). Use `Protocol` when you don't own the classes — third-party objects, or when you just want type-checker support without runtime coupling." Deep dive: [`02_abc_protocols.md`](../../01_Year3-4_Mid/01_Python_Advanced/theory/02_abc_protocols.md).

---

### Q8. What are dunder (magic) methods and name three you'd implement for a custom `Money` class?

Dunder methods let your objects hook into Python's built-in syntax/protocols.

```python
class Money:
    def __init__(self, cents: int):
        self.cents = cents

    def __repr__(self):                          # dev-facing string
        return f"Money({self.cents})"
    def __eq__(self, other):                     # ==
        return self.cents == other.cents
    def __add__(self, other):                    # +
        return Money(self.cents + other.cents)
    def __lt__(self, other):                     # <  (needed for sorting)
        return self.cents < other.cents
    def __hash__(self):                          # needed if used in a set/dict key
        return hash(self.cents)
```

**Gotcha:** defining `__eq__` without `__hash__` makes the class unhashable (Python sets `__hash__ = None` automatically) — breaks `set()`/`dict` key usage unless you define both.

---

### Q9. Explain `@property` and why it's preferred over plain getter/setter methods.

`@property` lets you expose computed or validated attributes through normal attribute syntax (`obj.value`, not `obj.get_value()`), while keeping the option to add validation later without breaking the calling code.

```python
class Temperature:
    def __init__(self, celsius):
        self._celsius = celsius

    @property
    def fahrenheit(self):
        return self._celsius * 9/5 + 32

    @property
    def celsius(self):
        return self._celsius

    @celsius.setter
    def celsius(self, value):
        if value < -273.15:
            raise ValueError("Below absolute zero")
        self._celsius = value

t = Temperature(25)
t.celsius = 30         # goes through the setter, validated
print(t.fahrenheit)    # computed, read-only
```

**Interview angle:** "It's Python's way of doing encapsulation without Java-style boilerplate getters/setters everywhere — you start with a plain attribute and only add a `@property` when you actually need validation or computation, without changing the caller's code."

---

### Q10. What's the difference between `__str__` and `__repr__`?

`__str__` → human-readable, for end users (`print(obj)`). `__repr__` → unambiguous, for developers (should ideally be valid Python to recreate the object; shown in REPL/logs/debugger). If `__str__` is missing, Python falls back to `__repr__`.

```python
class Point:
    def __init__(self, x, y): self.x, self.y = x, y
    def __repr__(self): return f"Point(x={self.x}, y={self.y})"
    def __str__(self): return f"({self.x}, {self.y})"

p = Point(1, 2)
print(p)        # (1, 2)          — __str__
print([p])      # [Point(x=1, y=2)] — repr used inside containers
```

**Production rule:** always implement `__repr__`, even if `__str__` is skipped — logs and stack traces use `repr()`, and a good `__repr__` saves debugging time.

---

## SECTION 2 — MEMORY, GIL & CONCURRENCY (Q11–Q18)

### Q11. What is the GIL and why does it exist?

The **Global Interpreter Lock** ensures only one thread executes Python bytecode at a time in CPython, even on multi-core machines. It exists because CPython's memory management (reference counting) is not thread-safe — the GIL is the cheap way to avoid needing fine-grained locks on every object.

**Consequence:** CPU-bound multi-threaded code doesn't get faster with more threads. I/O-bound code does — the GIL is released during I/O waits (network, disk, `time.sleep`).

**Follow-up:** *"How do you get real parallelism in Python?"* → `multiprocessing` (separate processes, separate GILs, separate memory — pay a serialization cost), or drop to C extensions that release the GIL (NumPy, most DB drivers do this internally).

---

### Q12. Threading vs multiprocessing vs asyncio — decision framework.

| | Threading | Multiprocessing | asyncio |
|---|---|---|---|
| Best for | I/O-bound, blocking libraries | CPU-bound | I/O-bound, high concurrency |
| Parallelism | No (GIL) | Yes (separate processes) | No (single thread, cooperative) |
| Memory | Shared | Separate (IPC needed) | Shared |
| Overhead | Low | High (process spawn, pickling) | Very low |
| Example use | calling a blocking SDK | image processing, ML inference | thousands of concurrent HTTP calls |

**One-liner interview answer:** "CPU-bound → multiprocessing. I/O-bound with a library that's already async → asyncio. I/O-bound with a blocking library you can't change → threading, or run it in asyncio's thread-pool executor." Full framework: [`26_concurrency_decision_framework.md`](../../01_Year3-4_Mid/01_Python_Advanced/theory/26_concurrency_decision_framework.md).

---

### Q13. What is PEP 703 (free-threaded / no-GIL Python) and should you care yet?

Python 3.13 shipped an experimental **build** without the GIL. It's not the default build, C extensions need to opt in (`Py_mod_gil` slot), and single-threaded performance regresses somewhat due to per-object locking overhead. For interviews: know it exists and what problem it solves (true multi-core parallelism for pure-Python CPU-bound code), but production adoption is still early. Deeper read: [`03_Senior_Leadership/08_pep_703_nogil_deep.md`](../../02_Year5+_Senior/03_Senior_Leadership/08_pep_703_nogil_deep.md).

---

### Q14. Explain Python's memory model — reference counting + garbage collection.

Every object has a refcount; when it hits 0, memory is freed immediately (deterministic, unlike Java/Go's GC). A separate **generational garbage collector** handles reference cycles (`a.ref = b; b.ref = a`) that refcounting alone can't clean up, since neither object's count ever reaches 0.

```python
import sys
a = []
print(sys.getrefcount(a))   # 2 — one for `a`, one for the getrefcount() call argument

import gc
gc.collect()                 # forces a cycle-collection pass
```

**Interview trap:** *"Does Python have a garbage collector?"* → Yes, but it's a hybrid: refcounting for the common case (deterministic, immediate), generational GC as a backstop for cycles only.

---

### Q15. What are `__slots__` and when would you use them?

By default, instances store attributes in a per-object `__dict__`, which is flexible but memory-heavy. `__slots__` declares a fixed attribute set, using a more compact storage layout — no per-instance `__dict__`.

```python
class Point:
    __slots__ = ("x", "y")
    def __init__(self, x, y):
        self.x = x
        self.y = y

p = Point(1, 2)
p.z = 5   # AttributeError — slots blocks dynamic attribute creation
```

**When it matters:** creating millions of small objects (data pipelines, graph nodes, game entities) — `__slots__` can cut memory 40–50% and speed up attribute access. Trade-off: no dynamic attributes, more careful multiple-inheritance handling. Deep dive: [`09_slots_deep_dive.md`](../../01_Year3-4_Mid/01_Python_Advanced/theory/09_slots_deep_dive.md).

---

### Q16. What's a race condition, and show a minimal fix.

A race condition happens when two threads/processes read-modify-write shared state without synchronization, and the interleaving of operations produces a wrong result.

```python
import threading
counter = 0
def increment():
    global counter
    for _ in range(100_000):
        counter += 1     # NOT atomic: read, add 1, write — three steps, can interleave

threads = [threading.Thread(target=increment) for _ in range(4)]
[t.start() for t in threads]; [t.join() for t in threads]
print(counter)   # usually < 400,000 — lost updates

# Fix: a lock around the critical section
lock = threading.Lock()
def safe_increment():
    global counter
    for _ in range(100_000):
        with lock:
            counter += 1
```

**Interview answer for "how did you debug a race condition in prod?":** look for symptoms that are intermittent and load-dependent (not reproducible with a single request), check anything touching shared mutable state without a lock/transaction, and in distributed systems reach for `SELECT ... FOR UPDATE`, Redis `WATCH`/optimistic locking, or a distributed lock (Redlock). Detailed scenario: [`09_debugging_scenarios.md`](09_debugging_scenarios.md).

---

### Q17. Deadlock — what causes it, and the standard prevention rule?

Deadlock happens when two or more threads each hold a lock the other needs, and neither releases. Classic cause: acquiring the **same two locks in different orders** in different code paths.

```python
# Thread 1: lock_a then lock_b
# Thread 2: lock_b then lock_a   ← inconsistent order = deadlock risk
```

**Prevention rule:** always acquire locks in a **consistent global order** (e.g., sort by object id). Or avoid holding multiple locks at once entirely — restructure so each critical section needs only one lock.

---

### Q18. What does `async`/`await` actually do under the hood?

`async def` creates a **coroutine function** — calling it doesn't run the body, it returns a coroutine object. `await` suspends execution at that point, hands control back to the **event loop**, and resumes when the awaited thing (I/O, timer) completes. It's cooperative multitasking on a single thread — no OS-level context switch, no GIL contention between coroutines.

```python
import asyncio

async def fetch(id):
    await asyncio.sleep(1)      # yields control here — event loop runs other coroutines meanwhile
    return f"result-{id}"

async def main():
    results = await asyncio.gather(*[fetch(i) for i in range(5)])   # all 5 run concurrently, ~1s total not 5s
    print(results)

asyncio.run(main())
```

**Common trap:** calling a blocking function (`time.sleep`, a sync DB driver call) inside an `async def` **blocks the entire event loop** — nothing else runs. Use `await asyncio.to_thread(blocking_fn)` or an async-native driver instead.

---

## SECTION 3 — DECORATORS, GENERATORS & FUNCTIONAL TOOLS (Q19–Q26)

### Q19. Write a timing decorator and explain what `functools.wraps` fixes.

```python
import functools, time

def timed(fn):
    @functools.wraps(fn)              # without this, fn.__name__/__doc__ get replaced by wrapper's
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = fn(*args, **kwargs)
        print(f"{fn.__name__} took {time.perf_counter() - start:.4f}s")
        return result
    return wrapper

@timed
def slow_query():
    """Runs a slow query."""
    time.sleep(1)

print(slow_query.__name__)   # "slow_query" (correct, thanks to @wraps)
                              # without @wraps this would print "wrapper" — breaks introspection,
                              # debuggers, and frameworks (FastAPI/DRF) that inspect function metadata
```

---

### Q20. Decorator with arguments — how do you write one?

Needs an extra layer: the outer function takes the decorator's arguments and returns the actual decorator.

```python
def retry(times=3):
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            for attempt in range(times):
                try:
                    return fn(*args, **kwargs)
                except Exception as e:
                    if attempt == times - 1:
                        raise
                    print(f"Retry {attempt+1}/{times} after: {e}")
        return wrapper
    return decorator

@retry(times=5)
def flaky_api_call(): ...
```

**Production analogue:** this is essentially what Celery's `@app.task(max_retries=5)` and `tenacity`'s `@retry` do.

---

### Q21. Generators — how are they different from returning a list, and why do they matter for backend work?

A generator produces values **lazily**, one at a time, on demand — it doesn't hold the whole sequence in memory.

```python
def read_large_file(path):
    with open(path) as f:
        for line in f:
            yield line.strip()      # one line in memory at a time, not the whole file

# vs:
def read_large_file_bad(path):
    with open(path) as f:
        return [line.strip() for line in f]   # loads entire file into memory
```

**Backend relevance:** streaming API responses (`StreamingResponse` in FastAPI), processing large CSV/DB exports without OOM, paginating a queryset lazily instead of `.all()`-ing millions of rows.

---

### Q22. What's the difference between `yield` and `yield from`?

`yield` produces one value. `yield from` delegates to a sub-generator/iterable, yielding all its values as if they came from the outer generator — also used for two-way communication with sub-generators (`send()`/`throw()` pass through).

```python
def inner():
    yield 1
    yield 2

def outer():
    yield from inner()   # equivalent to: for x in inner(): yield x
    yield 3

print(list(outer()))   # [1, 2, 3]
```

---

### Q23. Explain context managers — `with` statement, `__enter__`/`__exit__`, and `contextlib.contextmanager`.

```python
class DBConnection:
    def __enter__(self):
        self.conn = connect()
        return self.conn
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.close()
        return False   # False = don't suppress the exception; True would swallow it

with DBConnection() as conn:
    conn.execute(...)   # conn.close() guaranteed even if this raises

# Simpler with a generator:
from contextlib import contextmanager

@contextmanager
def db_connection():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()
```

**Interview answer for "why not just try/finally everywhere?":** context managers make cleanup impossible to forget and composable (`with a(), b():`) — this is exactly how DB sessions (SQLAlchemy), file handles, and locks are managed correctly in production code.

---

### Q24. `functools.lru_cache` — how does it work, and what's the gotcha with mutable/unhashable arguments?

```python
from functools import lru_cache

@lru_cache(maxsize=128)
def fib(n):
    if n < 2: return n
    return fib(n-1) + fib(n-2)   # O(n) instead of O(2^n) — memoized
```

Caches by argument values (must be hashable) — calling with a `list` argument raises `TypeError: unhashable type`. Cache is **process-local and in-memory**, unbounded growth if `maxsize=None` and arguments vary widely — not a substitute for Redis in a multi-process/multi-server deployment.

---

### Q25. Closures — what are they, and the classic late-binding bug.

A closure is a function that captures variables from its enclosing scope, even after that scope has finished executing.

```python
def make_multiplier(x):
    def multiply(y):
        return x * y      # `x` is captured from the enclosing scope
    return multiply

double = make_multiplier(2)
print(double(5))   # 10 — `x=2` is remembered even though make_multiplier() has returned
```

**Classic bug (late binding in loops):**
```python
funcs = [lambda: i for i in range(3)]
print([f() for f in funcs])   # [2, 2, 2] — all closures share the SAME `i`, evaluated at call time

funcs = [lambda i=i: i for i in range(3)]   # fix: default arg captures value at definition time
print([f() for f in funcs])   # [0, 1, 2]
```

---

### Q26. `*args`, `**kwargs`, and positional-only / keyword-only parameters — what's each for?

```python
def f(a, b, /, c, d, *, e, f):
    #     ^-- a, b: positional-only (can't pass as keyword)
    #             c, d: normal (positional or keyword)
    #                    ^-- e, f: keyword-only (must pass as keyword)
    ...

def flexible(*args, **kwargs):
    # args: tuple of extra positional args
    # kwargs: dict of extra keyword args
    ...
```

**Where this shows up:** FastAPI/Pydantic use keyword-only extensively to force explicit, self-documenting calls; `/` positional-only markers appear in stdlib signatures (`dict.get(key, /, default=None)` style) to keep the parameter name an implementation detail.

---

## SECTION 4 — EXCEPTIONS & ERROR HANDLING (Q27–Q31)

### Q27. Custom exception hierarchy — how do you design one for a backend service?

```python
class AppError(Exception):
    """Base for all app-raised errors — never raise this directly."""
    status_code = 500

class NotFoundError(AppError):
    status_code = 404

class ValidationError(AppError):
    status_code = 422

class PaymentDeclinedError(AppError):
    status_code = 402
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Payment declined: {reason}")
```

**Why a hierarchy:** a single `except AppError` at the API boundary catches everything app-raised and maps `status_code` → HTTP response, while unexpected exceptions (bugs) propagate uncaught and get logged/alerted instead of silently swallowed as a generic 500.

---

### Q28. `try`/`except`/`else`/`finally` — what does each block actually guarantee?

```python
try:
    result = risky_call()
except ValueError as e:
    handle(e)
else:
    # runs ONLY if try succeeded with no exception
    use(result)
finally:
    # ALWAYS runs — exception or not, even if except/else re-raises
    cleanup()
```

**Why `else` exists:** without it, code that should only run on success sits inside the `try` block, where it could accidentally raise a `ValueError` itself and get miscaught by the `except`. `else` keeps success-path code outside the try's exception net.

---

### Q29. What's exception chaining (`raise ... from ...`) and why does it matter for debugging?

```python
def load_config():
    try:
        return json.load(open("config.json"))
    except FileNotFoundError as e:
        raise ConfigError("Config missing") from e   # preserves original traceback as __cause__

# Without `from e`, Python still shows both, but with a vaguer
# "During handling of the above exception, another exception occurred" —
# `from e` makes the causal link explicit and intentional.
```

**Suppressing chaining:** `raise ConfigError(...) from None` — use when the original exception is noise (e.g., re-raising a sanitized error to an external API caller who shouldn't see internal stack details).

---

### Q30. What happens if an exception is raised inside a `finally` block?

It **replaces** any exception that was propagating from the `try`/`except` — the original is lost (available as `__context__` but not raised). This is a common source of "swallowed" bugs.

```python
def risky():
    try:
        raise ValueError("original")
    finally:
        raise RuntimeError("in finally")   # this is what the caller sees — ValueError is gone

risky()   # RuntimeError: in finally  (ValueError silently discarded)
```

**Rule:** never raise in a `finally` unless intentional — prefer logging + `return` there, or the original exception vanishes silently in production logs.

---

### Q31. Exception groups (`except*`) — new in Python 3.11, what problem do they solve?

Before 3.11, if multiple independent operations (e.g. concurrent `asyncio.gather` tasks) each failed, you only got the first exception — the rest were lost. `ExceptionGroup` + `except*` let you catch and handle **multiple simultaneous exceptions** from concurrent operations.

```python
try:
    raise ExceptionGroup("multiple failures", [ValueError("bad input"), TimeoutError("slow")])
except* ValueError as eg:
    print("Validation errors:", eg.exceptions)
except* TimeoutError as eg:
    print("Timeouts:", eg.exceptions)
```

**Interview signal:** mentioning this unprompted signals you're current on modern Python (3.11+), not just familiar with the language as it was five years ago.

---

## SECTION 5 — TYPE SYSTEM (Q32–Q35)

### Q32. Duck typing vs static typing — how does Python's type-hint system fit in?

Python is **dynamically typed at runtime** — `type()` is checked when an operation happens, not before. Type hints (`def f(x: int) -> str:`) add **optional static analysis** via tools like `mypy`/`pyright` — they're not enforced at runtime by the interpreter itself.

```python
def add(a: int, b: int) -> int:
    return a + b

add("1", "2")   # runs fine at runtime, returns "12" — mypy would flag this as a type error, Python won't
```

**Where runtime enforcement comes from:** Pydantic and FastAPI validate types **at the boundary** (request parsing) using the same hints, converting them from documentation into runtime guarantees for that layer specifically.

---

### Q33. `Optional[X]` vs `X | None` — any real difference?

None functionally in modern Python (3.10+) — `X | None` is the newer, cleaner syntax for the same thing `Optional[X]` (from `typing`) means. `Optional[X]` still works and is common in codebases targeting <3.10 or using Pydantic v1 conventions.

```python
from typing import Optional
def f(x: Optional[int] = None): ...   # older style
def g(x: int | None = None): ...       # 3.10+ style, same meaning
```

---

### Q34. Generic types — write a type-safe `Stack[T]`.

```python
from typing import Generic, TypeVar

T = TypeVar("T")

class Stack(Generic[T]):
    def __init__(self) -> None:
        self._items: list[T] = []
    def push(self, item: T) -> None:
        self._items.append(item)
    def pop(self) -> T:
        return self._items.pop()

int_stack: Stack[int] = Stack()
int_stack.push(5)
int_stack.push("hello")   # mypy flags this — type checker enforces T=int for this instance
```

---

### Q35. What's `TypedDict` and when would you reach for it over a Pydantic model?

`TypedDict` describes the **shape of a plain dict** for the type checker — zero runtime overhead, no validation, just static hints.

```python
from typing import TypedDict

class UserDict(TypedDict):
    id: int
    name: str

def process(user: UserDict) -> None: ...   # still just a dict at runtime — no validation happens
```

**Decision rule:** `TypedDict` when you're working with plain dicts (e.g., JSON already parsed, internal function signatures) and want type-checker help without conversion overhead. Pydantic when you need actual runtime validation, serialization, or the object needs behavior beyond data (methods, computed fields).

---

## Quick-fire round (rapid Q&A, expect these as warm-ups)

| Q | A |
|---|---|
| Is Python pass-by-value or pass-by-reference? | Neither exactly — "pass by object reference." Mutable objects (list, dict) can be mutated in place; rebinding the name inside the function doesn't affect the caller's variable. |
| Difference between `list` and `tuple`? | Mutable vs immutable. Tuples are hashable (usable as dict keys) if their contents are; lists are not. |
| Why are dict keys required to be hashable? | Dicts are hash tables — the key's hash determines its bucket. Mutable objects could change their hash after insertion, corrupting lookup. |
| `==` vs `is`? | `==` compares value equality (`__eq__`), `is` compares identity (same object in memory). |
| What does `__init__.py` do? | Marks a directory as a package (optional since Python 3.3's implicit namespace packages, but still standard for explicit exports/`__all__`). |
| Shallow copy vs deep copy? | `copy.copy()` copies one level — nested mutable objects are still shared references. `copy.deepcopy()` recursively copies everything. |
| What's a metaclass, one sentence? | The class of a class — `type` is the default metaclass; overriding `__new__`/`__init__` on a custom metaclass lets you control how classes themselves are constructed (this is how Django's `ModelBase` builds the ORM's `Meta` machinery). |
| GIL released during what? | I/O operations, `time.sleep`, and any C extension that explicitly releases it (NumPy vectorized ops, most DB drivers). |

---

**Related:** deeper internals in [`01_Year3-4_Mid/01_Python_Advanced/`](../../01_Year3-4_Mid/01_Python_Advanced/) · tricky gotchas in [`07_python_tricky_questions.md`](07_python_tricky_questions.md) · design patterns in [`15_Design_Patterns_SOLID/`](../../01_Year3-4_Mid/15_Design_Patterns_SOLID/) and [`LLD_Theory/`](../../02_Year5+_Senior/01_System_Design/LLD_Theory/).
