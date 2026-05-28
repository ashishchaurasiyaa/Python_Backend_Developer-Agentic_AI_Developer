# Modern Python 3.11 / 3.12 / 3.13 — Pattern Matching, ExceptionGroup, No-GIL

## Quick Concepts

**WHAT:**
- **Python 3.10** = `match/case`, parenthesized context managers, structural pattern matching
- **Python 3.11** = ExceptionGroup, asyncio.TaskGroup, asyncio.timeout, tomllib, ~25% faster
- **Python 3.12** = PEP 695 generic syntax, sub-interpreters (PEP 684), better error messages
- **Python 3.13** = Free-threaded mode (no GIL), JIT compiler (experimental)

**WHY know these:**
- 2024+ projects use 3.11/3.12 defaults
- New features replace old patterns (gather → TaskGroup)
- Performance gains are significant
- Senior interviewers test "you stay current"

**HOW versions stack:**
```
Python 3.10 (2021) → match/case, parenthesized with
Python 3.11 (2022) → ExceptionGroup, TaskGroup, faster, tomllib
Python 3.12 (2023) → PEP 695 generics, sub-interpreters, no distutils
Python 3.13 (2024) → No-GIL (PEP 703), JIT (experimental)
Python 3.14 (2025) → ... future
```

---

## Interview Questions & Answers

### Q1: Structural Pattern Matching (3.10+) — replacement for if/elif?

**Answer:**

**WHAT:** `match/case` for sophisticated structural matching.

**WHY:**
- More expressive than if/elif chains
- Match patterns (types, structures), not just values
- Cleaner code for state machines, parsing

**HOW — Basic match:**

```python
def http_error_handler(status_code: int) -> str:
    match status_code:
        case 200:
            return "OK"
        case 404:
            return "Not Found"
        case 500 | 502 | 503:  # ⭐ OR pattern
            return "Server Error"
        case code if 400 <= code < 500:  # ⭐ Guard
            return f"Client Error: {code}"
        case _:  # ⭐ Default (like default in switch)
            return "Unknown"
```

**HOW — Match types + dataclasses:**

```python
from dataclasses import dataclass

@dataclass
class Click:
    x: int
    y: int

@dataclass
class KeyPress:
    key: str

@dataclass
class Scroll:
    direction: str

def handle_event(event):
    match event:
        case Click(x=0, y=0):
            return "Click at origin"
        case Click(x=x, y=y) if x > 100:  # ⭐ Destructure + guard
            return f"Click at right side: ({x}, {y})"
        case Click(x=x, y=y):
            return f"Click at ({x}, {y})"
        case KeyPress(key="Enter"):
            return "Enter pressed"
        case KeyPress(key=k) if k.isupper():
            return f"Uppercase key: {k}"
        case Scroll():
            return "Scrolled"
        case _:
            return "Unknown event"
```

**HOW — Match dicts (for JSON):**

```python
def process_message(msg: dict):
    match msg:
        # ⭐ Match dict structure
        case {"type": "login", "user": str(user), "password": str(pwd)}:
            return f"Login: {user}"

        case {"type": "logout"}:
            return "Logout"

        case {"type": "purchase", "items": [*items], "total": float(total)}:
            return f"Purchase: {len(items)} items, ${total}"

        # ⭐ Match nested
        case {"type": "error", "error": {"code": int(code), "message": str(msg)}}:
            return f"Error {code}: {msg}"

        case _:
            return "Unknown message"


# Usage
process_message({"type": "login", "user": "alice", "password": "x"})
process_message({"type": "purchase", "items": ["a", "b"], "total": 99.99})
process_message({"type": "error", "error": {"code": 500, "message": "Server died"}})
```

**HOW — Match lists/tuples:**

```python
def process_command(cmd: list):
    match cmd:
        case []:
            return "Empty"
        case [single]:
            return f"Single: {single}"
        case ["help"]:
            return "Show help"
        case ["delete", item]:
            return f"Delete {item}"
        case ["create", *args]:  # ⭐ Variadic
            return f"Create with: {args}"
        case [first, *middle, last]:
            return f"First={first}, Last={last}, Middle={middle}"
```

**HOW — Class hierarchies:**

```python
class Shape: pass
class Circle(Shape):
    def __init__(self, r): self.r = r
class Square(Shape):
    def __init__(self, side): self.side = side

def area(shape):
    match shape:
        case Circle(r=r):
            return 3.14159 * r * r
        case Square(side=s):
            return s * s
        case Shape():  # Base class
            return 0
```

---

### Q2: ExceptionGroup + except* (3.11) — concurrent error handling?

**Answer:**

**WHAT:** Group multiple exceptions into one (useful with TaskGroup).

**WHY:**
- Concurrent code (asyncio, threads) can raise multiple errors
- Pre-3.11: only first error reported, others lost
- 3.11: ExceptionGroup preserves all

**HOW — TaskGroup with ExceptionGroup:**

```python
import asyncio

async def task1():
    raise ValueError("Task 1 failed")

async def task2():
    raise TypeError("Task 2 failed")

async def task3():
    raise RuntimeError("Task 3 failed")


async def main():
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(task1())
            tg.create_task(task2())
            tg.create_task(task3())
    except* ValueError as eg:  # ⭐ except* for ExceptionGroup
        print(f"Got {len(eg.exceptions)} ValueErrors")
        for e in eg.exceptions:
            print(f"  - {e}")

    except* TypeError as eg:
        print(f"Got {len(eg.exceptions)} TypeErrors")

    except* RuntimeError as eg:
        print(f"Got {len(eg.exceptions)} RuntimeErrors")


asyncio.run(main())
# Output:
# Got 1 ValueErrors
#   - Task 1 failed
# Got 1 TypeErrors
# Got 1 RuntimeErrors
```

**HOW — Manual ExceptionGroup:**

```python
def validate_all(data: dict) -> None:
    errors = []

    if not data.get("name"):
        errors.append(ValueError("Name required"))
    if not data.get("email"):
        errors.append(ValueError("Email required"))
    if "age" in data and data["age"] < 0:
        errors.append(ValueError("Age must be positive"))

    if errors:
        # ⭐ Raise all errors at once
        raise ExceptionGroup("Validation failed", errors)


try:
    validate_all({"age": -5})
except* ValueError as eg:
    for error in eg.exceptions:
        print(f"Validation error: {error}")
```

**HOW — Split ExceptionGroup:**

```python
try:
    raise ExceptionGroup("multiple errors", [
        ValueError("bad value"),
        TypeError("bad type"),
        RuntimeError("runtime issue"),
    ])
except ExceptionGroup as eg:
    # Split by type
    type_errors, rest = eg.split(TypeError)
    print(f"Type errors: {type_errors}")
    print(f"Other errors: {rest}")
```

---

### Q3: asyncio.TaskGroup (3.11) — better than gather?

**Answer:**

**WHAT:** Context manager for managing groups of tasks.

**WHY over gather:**
- Cleaner syntax (no list building)
- Error in one cancels all (structured concurrency)
- ExceptionGroup for multiple errors
- Easier to reason about

**HOW — Comparison:**

```python
# ❌ OLD WAY (asyncio.gather)
async def old_way():
    try:
        results = await asyncio.gather(
            fetch_user(1),
            fetch_user(2),
            fetch_user(3),
        )
    except Exception as e:
        # ⚠️ Only first error caught; others still running!
        # ⚠️ Manual cancellation needed
        ...


# ✅ NEW WAY (TaskGroup)
async def new_way():
    try:
        async with asyncio.TaskGroup() as tg:
            t1 = tg.create_task(fetch_user(1))
            t2 = tg.create_task(fetch_user(2))
            t3 = tg.create_task(fetch_user(3))

        # ⭐ All tasks done — get results
        results = [t1.result(), t2.result(), t3.result()]

    except* Exception as eg:
        # ⭐ All errors captured
        for e in eg.exceptions:
            print(f"Error: {e}")
        # All sibling tasks already cancelled
```

**HOW — Dynamic task creation:**

```python
async def fetch_many_users(user_ids):
    async with asyncio.TaskGroup() as tg:
        tasks = [
            tg.create_task(fetch_user(uid), name=f"user-{uid}")
            for uid in user_ids
        ]

    return [t.result() for t in tasks]
```

---

### Q4: asyncio.timeout (3.11) — modern timeout pattern?

**Answer:**

**WHAT:** Context manager for timeouts.

**WHY over wait_for:**
- Cleaner syntax
- Can be rescheduled
- Plays nicely with TaskGroup

**HOW:**

```python
import asyncio

# ❌ OLD WAY
async def old():
    try:
        result = await asyncio.wait_for(slow_op(), timeout=5.0)
    except asyncio.TimeoutError:
        ...


# ✅ NEW WAY
async def new():
    try:
        async with asyncio.timeout(5.0):
            result = await slow_op()
    except TimeoutError:  # ⭐ Built-in TimeoutError now
        ...
```

**HOW — Reschedule timeout:**

```python
async def with_dynamic_timeout():
    async with asyncio.timeout(5.0) as cm:
        await initial_setup()

        # ⭐ Extend timeout if needed
        loop = asyncio.get_running_loop()
        cm.reschedule(loop.time() + 10.0)

        await long_operation()


# Disable timeout temporarily
async def cm_control():
    async with asyncio.timeout(5.0) as cm:
        if some_condition:
            cm.reschedule(None)  # ⭐ Remove timeout
        await operation()
```

**HOW — timeout_at (absolute time):**

```python
async def with_deadline():
    deadline = asyncio.get_running_loop().time() + 30.0

    async with asyncio.timeout_at(deadline):
        await operation1()
        await operation2()  # Still subject to overall 30s deadline
```

---

### Q5: tomllib (3.11) — built-in TOML support?

**Answer:**

**WHAT:** Stdlib TOML parser (replaces 3rd-party `toml`/`tomli`).

**WHY:**
- TOML is config standard (pyproject.toml)
- Was 3rd party — now built-in
- Read-only (use `tomli_w` for writing)

**HOW:**

```python
import tomllib

# Read TOML file
with open("pyproject.toml", "rb") as f:  # ⭐ "rb" not "r"
    config = tomllib.load(f)

print(config["project"]["name"])
print(config["project"]["dependencies"])


# Parse TOML string
toml_str = """
[project]
name = "myapp"
version = "1.0.0"
"""

data = tomllib.loads(toml_str)
print(data["project"]["name"])  # myapp


# Real example: read pyproject.toml deps
def get_dependencies():
    with open("pyproject.toml", "rb") as f:
        config = tomllib.load(f)
    return config.get("project", {}).get("dependencies", [])
```

**Write TOML (3rd party needed):**

```python
# pip install tomli_w
import tomli_w

data = {"project": {"name": "myapp", "version": "1.0.0"}}

with open("output.toml", "wb") as f:
    tomli_w.dump(data, f)
```

---

### Q6: PEP 695 Generic Syntax (3.12) — cleaner generics?

**Answer:**

**WHAT:** New cleaner syntax for type variables and generics.

**WHY:**
- Old syntax verbose (`from typing import TypeVar`)
- New syntax inline
- No runtime cost

**HOW — Comparison:**

```python
# ❌ OLD WAY (Python ≤ 3.11)
from typing import TypeVar, Generic

T = TypeVar("T")

class Stack(Generic[T]):
    def __init__(self):
        self.items: list[T] = []

    def push(self, item: T) -> None:
        self.items.append(item)

    def pop(self) -> T:
        return self.items.pop()


def first(items: list[T]) -> T:
    return items[0]


# ✅ NEW WAY (Python 3.12+)
class Stack[T]:  # ⭐ Generic syntax inline
    def __init__(self):
        self.items: list[T] = []

    def push(self, item: T) -> None:
        self.items.append(item)

    def pop(self) -> T:
        return self.items.pop()


def first[T](items: list[T]) -> T:
    return items[0]
```

**HOW — Type aliases:**

```python
# OLD
from typing import TypeAlias
UserID: TypeAlias = int

# NEW (Python 3.12+)
type UserID = int


# Generic type alias
type Vector[T] = list[T]
type Result[T, E] = T | E
```

**HOW — Bound + constraints:**

```python
# OLD
T = TypeVar("T", bound=Comparable)
Numeric = TypeVar("Numeric", int, float, complex)


# NEW (Python 3.12+)
def sort_items[T: Comparable](items: list[T]) -> list[T]:
    ...


def calc[T: (int, float, complex)](x: T, y: T) -> T:
    return x + y
```

---

### Q7: Sub-interpreters (3.12) — true parallelism without multiprocessing?

**Answer:**

**WHAT:** Multiple isolated interpreters in same process (PEP 684).

**WHY:**
- True parallelism (each has own GIL)
- Cheaper than multiprocessing (shared memory possible)
- Better isolation than threading

**HOW:**

```python
# Python 3.12+
import _xxsubinterpreters as interpreters

# Create new interpreter
interp = interpreters.create()

# Run code in it
interpreters.run_string(interp, """
import math
result = sum(math.sqrt(i) for i in range(1_000_000))
print(f"Result: {result}")
""")

interpreters.destroy(interp)
```

**HOW — Better API coming (Python 3.13):**

```python
# Python 3.13+ public API (PEP 734)
from interpreters import create, destroy, run

interp = create()
try:
    run(interp, "print('Hello from sub-interpreter')")
finally:
    destroy(interp)
```

---

### Q8: Free-threaded Python (3.13) — no GIL?

**Answer:**

**WHAT:** Optional no-GIL build of CPython.

**WHY:**
- Threads can ACTUALLY run in parallel (CPU-bound)
- Game changer for Python performance
- Backward compatible (C extensions need updates)

**HOW:**

```bash
# Build no-GIL Python
./configure --disable-gil
make
./python --version
# Python 3.13.0+ free-threading build
```

**HOW — Check at runtime:**

```python
import sys
import sysconfig

# Check if no-GIL build
if sysconfig.get_config_var("Py_GIL_DISABLED"):
    print("Running with NO GIL!")
else:
    print("Standard GIL build")
```

**HOW — Benefit example:**

```python
import threading
import time

def cpu_work():
    """CPU-bound — usually blocked by GIL."""
    sum(i*i for i in range(10_000_000))


# With GIL: single-threaded speed
start = time.time()
threads = [threading.Thread(target=cpu_work) for _ in range(8)]
for t in threads:
    t.start()
for t in threads:
    t.join()
elapsed = time.time() - start

# Standard CPython: ~8x base time (GIL serializes)
# No-GIL CPython: ~1.5x base time (true parallel)
print(f"8 threads: {elapsed:.2f}s")
```

---

### Q9: Performance improvements (3.11+)?

**Answer:**

**WHAT:** Major perf gains in 3.11+ (often called "Faster CPython").

**Speedups:**
- Python 3.11: 10-60% faster than 3.10
- Python 3.12: another 5%
- Python 3.13: another 5-10% + JIT (experimental)

**HOW — Key optimizations:**

```
1. Specialized adaptive interpreter (PEP 659)
   - Bytecode adapts to types seen
   - Hot loops compile to specialized opcodes

2. Frame object simplification
   - Faster function calls
   - Less memory per frame

3. Better error messages
   - PEP 657: precise error locations
   - PEP 678: exception notes

4. Faster startup
   - 10-15% faster Python startup

5. Improved asyncio
   - TaskGroup, timeout, faster overall

6. C API improvements
   - Faster string ops
   - Better dict/list internals
```

**HOW — Better error messages (3.11+):**

```python
# Old (3.10)
# > Traceback (most recent call last):
# >   File "main.py", line 1, in <module>
# >     x = (1 + 2) / (3 * 4) + (5 * 6)
# > ZeroDivisionError: division by zero

# New (3.11+)
# > Traceback (most recent call last):
# >   File "main.py", line 1, in <module>
# >     x = (1 + 2) / (3 * 4) + (5 * 6)
# >                  ~~~~~~~ ^ ~~~~~~~
# > ZeroDivisionError: division by zero
```

**HOW — Exception notes (3.11+):**

```python
try:
    do_thing()
except Exception as e:
    e.add_note("Context: processing user-123 order")
    e.add_note("Request ID: abc-def-123")
    raise

# Traceback shows:
# Exception: ...
# Context: processing user-123 order
# Request ID: abc-def-123
```

---

### Q10: Parenthesized context managers (3.10+)?

**Answer:**

**WHAT:** Multi-line `with` statements with parentheses.

**HOW:**

```python
# ❌ OLD WAY (ugly with many context managers)
with open("a.txt") as a, open("b.txt") as b, open("c.txt") as c, open("d.txt") as d:
    ...


# Or with backslash (also ugly)
with open("a.txt") as a, \
     open("b.txt") as b, \
     open("c.txt") as c, \
     open("d.txt") as d:
    ...


# ✅ NEW WAY (Python 3.10+)
with (
    open("a.txt") as a,
    open("b.txt") as b,
    open("c.txt") as c,
    open("d.txt") as d,
):
    ...
```

---

### Q11: typing.override (3.12) — explicit method override?

**Answer:**

**WHAT:** Decorator marking method as overriding parent method.

**WHY:**
- Type checker catches typos (renamed parent method)
- Code intent clearer
- Common in TypeScript, Java, C#

**HOW:**

```python
from typing import override

class Animal:
    def speak(self) -> str:
        return "Some sound"


class Dog(Animal):
    @override  # ⭐ Explicit override
    def speak(self) -> str:
        return "Bark"


class Cat(Animal):
    @override
    def speak(self) -> str:
        return "Meow"


# Refactoring scenario
class Animal:
    def make_sound(self) -> str:  # ⚠️ Renamed from speak
        return "..."


class Dog(Animal):
    @override  # ⭐ mypy will catch: parent has no 'speak'
    def speak(self) -> str:
        return "Bark"
```

---

### Q12: Migration guide — upgrading from 3.10?

**Answer:**

**HOW — Step-by-step upgrade:**

```markdown
### 1. Update Python version
- Update pyproject.toml: python = "^3.11"
- Update CI matrix (test on 3.11, 3.12)
- Update Docker base: python:3.12-slim

### 2. Replace deprecated patterns
| Old | New |
|-----|-----|
| asyncio.wait_for() | asyncio.timeout() |
| asyncio.gather() (for groups) | asyncio.TaskGroup() |
| typing.List/Dict | list/dict (3.9+) |
| typing.Union | X | Y (3.10+) |
| typing.Optional[X] | X | None (3.10+) |
| if x == 1: elif x == 2 | match/case (3.10+) |
| toml.load | tomllib.load (3.11+) |
| Multiple `with` lines | Parenthesized `with` (3.10+) |

### 3. Adopt new features
- [ ] match/case for state machines
- [ ] ExceptionGroup for parallel errors
- [ ] except* for exception groups
- [ ] TaskGroup for structured concurrency
- [ ] asyncio.timeout context manager
- [ ] PEP 695 generic syntax (3.12+)
- [ ] @override decorator (3.12+)
- [ ] tomllib for TOML
```

---

## Quick Reference — What's New

| Feature | Python | Replaces |
|---|---|---|
| `match/case` | 3.10 | Long if/elif chains |
| `int \| str` syntax | 3.10 | `Union[int, str]` |
| Parenthesized `with` | 3.10 | Backslash multi-line |
| ExceptionGroup | 3.11 | (new) |
| `except*` | 3.11 | (new) |
| `asyncio.TaskGroup` | 3.11 | `asyncio.gather` for groups |
| `asyncio.timeout` | 3.11 | `asyncio.wait_for` |
| `tomllib` | 3.11 | 3rd-party `toml` |
| Self type | 3.11 | TypeVar bound to self |
| Exception notes (`add_note`) | 3.11 | Manual error context |
| PEP 695 `class C[T]` | 3.12 | `class C(Generic[T])` |
| `type Alias = ...` | 3.12 | `TypeAlias` |
| Sub-interpreters | 3.12 | multiprocessing for some cases |
| `typing.override` | 3.12 | Comments noting overrides |
| Free-threaded (no-GIL) | 3.13 | (build option) |
| Experimental JIT | 3.13 | (build option) |

---

## Production Adoption Checklist

```markdown
### Code Modernization
- [ ] Migrate to TaskGroup from gather
- [ ] Use asyncio.timeout
- [ ] Adopt match/case for state machines
- [ ] Use ExceptionGroup for parallel errors
- [ ] Use built-in types (list[X] not List[X])
- [ ] Replace Optional[X] with X | None

### Tooling
- [ ] ruff/mypy support latest Python
- [ ] Tests pass on 3.11/3.12
- [ ] Docker base image updated
- [ ] CI matrix includes latest

### Performance
- [ ] Benchmark old vs new (often 20-40% faster)
- [ ] Monitor memory (sub-interpreters help)
- [ ] Consider no-GIL for CPU-bound (3.13)

### Documentation
- [ ] README mentions min Python version
- [ ] Setup guide updated
- [ ] Migration notes for users
```
