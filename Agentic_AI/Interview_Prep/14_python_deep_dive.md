# Python Deep Guide — Internals · OOP · Async · Decorators · Performance
### Resume Skills: Python (Senior Level), Type Hints, Async, OOP
### PwC Interview Ready · 3-4 baar padho

> **Reading plan:**
> - Pass 1: Poora padho — internals samjho
> - Pass 2: Interview answers loud bolke practice karo
> - Pass 3: Code examples khud likho (without reading)
> - Pass 4: Quick Recall Card only

---

## TABLE OF CONTENTS

| # | Topic | Why PwC Puchega |
|---|---|---|
| 1 | Python Internals — GIL, Memory, CPython | Senior level question |
| 2 | Data Structures — Time Complexity | Optimization questions |
| 3 | OOP — Classes, MRO, Dunder Methods | Django/FastAPI base |
| 4 | Decorators + Context Managers | Middleware, retry patterns |
| 5 | Generators + Iterators | Memory efficient processing |
| 6 | Async/Await — event loop internals | FastAPI, AI streaming |
| 7 | Type Hints + mypy | Code quality |
| 8 | Testing — pytest patterns | Professional practice |
| 9 | Performance — profiling + optimization | Scale questions |
| 10 | Common Patterns | Design pattern questions |
| 11 | Interview Q&A — 20 Questions | PwC specific |
| 12 | Quick Recall Card | 1 ghanta pehle |

---

## TOPIC 1: PYTHON INTERNALS

### CPython — Python kaise kaam karta hai

```
PYTHON CODE EXECUTION PIPELINE:
────────────────────────────────────────────────────────────────

SOURCE CODE (.py)
    │
    ▼ Parser
ABSTRACT SYNTAX TREE (AST)
    │
    ▼ Compiler
BYTECODE (.pyc files in __pycache__)
    │
    ▼ Python Virtual Machine (PVM / CPython interpreter)
EXECUTION

EXAMPLE:
x = 1 + 2

AST:
  Assign
  ├── target: Name(x)
  └── value: BinOp(Num(1), Add, Num(2))

Bytecode (dis module):
  LOAD_CONST 1
  LOAD_CONST 2
  BINARY_ADD
  STORE_NAME x

import dis
dis.dis("x = 1 + 2")
```

### GIL — Global Interpreter Lock

```
GIL = Global Interpreter Lock
CPython mein: ek time pe sirf ek thread Python bytecode execute kar sakta hai.

WHY GIL EXISTS:
CPython reference counting (memory management) thread-safe nahi hota without GIL.
Python objects ke refcount update atomic nahi → race condition.
GIL = simpler implementation, single-threaded performance good.

GIL KA IMPACT:
──────────────────────────────────────────────────────────────

CPU-BOUND TASKS (GIL problem):
Thread 1: heavy computation
Thread 2: heavy computation
→ Both want CPU → GIL allows only one at a time
→ 2 threads = same speed as 1 thread! (no speedup)
FIX: multiprocessing (separate processes, each has own GIL)

I/O-BOUND TASKS (GIL released!):
Thread 1: wait for HTTP response  ← GIL released during I/O wait
Thread 2: runs while Thread 1 waits ← can execute!
→ Threading works great for I/O bound
FIX: threading, asyncio (both work)

PROOF:
import time, threading

# CPU-bound: threads don't help
def count(n):
    while n > 0: n -= 1

# Sequential: 2.0s
# 2 threads: 2.1s (overhead from GIL switching!)
# 2 processes: 1.0s ← actual speedup

FUTURE: Python 3.13+ "free-threaded" mode (no GIL experiment!)
PEP 703 — per-object locking instead of global lock
```

### Memory management — reference counting

```
REFERENCE COUNTING:
Every Python object has refcount.
refcount = 0 → memory freed immediately (deterministic!)

import sys
x = []
sys.getrefcount(x)   # 2 (x + getrefcount argument)

y = x
sys.getrefcount(x)   # 3

del y
sys.getrefcount(x)   # 2

del x
# refcount = 0 → freed!

CYCLIC GARBAGE COLLECTOR:
Problem: circular references → refcount never 0!
a = []
b = []
a.append(b)   # b refcount: 2
b.append(a)   # a refcount: 2
del a         # a refcount: 1 (still referenced by b)
del b         # b refcount: 1 (still referenced by a)
# Neither freed! Memory leak!

Python's cyclic GC detects these cycles:
import gc
gc.collect()   # manually trigger
gc.get_count() # (gen0, gen1, gen2) — generational GC

MEMORY POOLS (pymalloc):
Python allocates small objects (<512 bytes) from its own pool.
Not directly from OS (malloc) → faster allocation.
Pool → Block → Arena hierarchy.

INTERNING:
Small integers (-5 to 256) and short strings are cached:
a = 256; b = 256; a is b  → True  (same object!)
a = 257; b = 257; a is b  → False (different objects)
"hello" is "hello"         → True  (interned)
"hello world" is "hello world" → False (not interned)
```

### `is` vs `==`

```python
# == checks VALUE equality (calls __eq__)
# is checks IDENTITY (same object in memory, same id())

a = [1, 2, 3]
b = [1, 2, 3]
a == b  # True  (same values)
a is b  # False (different objects)

a = [1, 2, 3]
b = a
a is b  # True (same object!)

# COMMON BUG:
x = None
if x == None:  # works but wrong style
if x is None:  # CORRECT — None is singleton, always use `is`
if x is not None:  # CORRECT
```

---

## TOPIC 2: DATA STRUCTURES — TIME COMPLEXITY

### Built-in structures

```
LIST (array-based, ordered, mutable):
────────────────────────────────────────────────────────
append(x)     O(1) amortized   ← fast
insert(i, x)  O(n)             ← slow (shifts elements)
pop()         O(1)             ← from end: fast
pop(i)        O(n)             ← from middle: slow (shifts)
x in list     O(n)             ← linear search!
index(x)      O(n)
sort()        O(n log n)       ← Timsort

DICT (hash table, ordered since 3.7, mutable):
────────────────────────────────────────────────────────
d[key]        O(1) average     ← hash lookup
d[key] = v    O(1) average
key in d      O(1) average     ← FAST! (vs list O(n))
del d[key]    O(1) average

SET (hash table, unordered, mutable):
────────────────────────────────────────────────────────
add(x)        O(1) average
x in set      O(1) average     ← FAST membership check
remove(x)     O(1) average
intersection  O(min(n, m))
union         O(n + m)

DEQUE (double-ended queue):
────────────────────────────────────────────────────────
appendleft(x) O(1)             ← O(n) for list!
popleft()     O(1)             ← O(n) for list!
append(x)     O(1)
pop()         O(1)
Use: BFS queue, sliding window, task queue
```

### Choosing the right structure

```python
# Membership check — SET vs LIST
# BAD:
items = [1, 2, 3, ..., 10000]
if x in items:   # O(n) every time!

# GOOD:
items = {1, 2, 3, ..., 10000}
if x in items:   # O(1) always!

# Counter (frequency dict)
from collections import Counter
words = ["apple", "banana", "apple", "cherry", "banana", "apple"]
freq = Counter(words)
# Counter({'apple': 3, 'banana': 2, 'cherry': 1})
freq.most_common(2)   # [('apple', 3), ('banana', 2)]

# defaultdict (no KeyError)
from collections import defaultdict
graph = defaultdict(list)
graph["A"].append("B")   # no need to check if "A" exists
graph["A"].append("C")

# OrderedDict (LRU cache pattern)
from collections import OrderedDict
class LRUCache:
    def __init__(self, capacity):
        self.cache = OrderedDict()
        self.capacity = capacity

    def get(self, key):
        if key not in self.cache:
            return -1
        self.cache.move_to_end(key)   # mark as recently used
        return self.cache[key]

    def put(self, key, value):
        self.cache[key] = value
        self.cache.move_to_end(key)
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)  # remove LRU

# heapq (priority queue)
import heapq
tasks = []
heapq.heappush(tasks, (1, "low priority"))
heapq.heappush(tasks, (10, "high priority"))
priority, task = heapq.heappop(tasks)   # always pops smallest
```

---

## TOPIC 3: OOP — CLASSES, MRO, DUNDER METHODS

### Classes — everything

```python
class Invoice:
    # Class variable (shared by all instances)
    tax_rate = 0.18
    _count = 0

    def __init__(self, number: str, amount: float):
        # Instance variables (per object)
        self.number = number
        self.amount = amount
        self._status = "pending"    # "protected" (convention)
        self.__secret = "shhh"      # "private" (name mangled)
        Invoice._count += 1

    # ── DUNDER / MAGIC METHODS ──────────────────────────────

    def __repr__(self):
        # For developers: unambiguous, eval-able
        return f"Invoice(number={self.number!r}, amount={self.amount})"

    def __str__(self):
        # For users: readable
        return f"Invoice #{self.number}: ₹{self.amount:,.2f}"

    def __eq__(self, other):
        if not isinstance(other, Invoice):
            return NotImplemented
        return self.number == other.number

    def __hash__(self):
        # Required if __eq__ defined (to use in sets/dict keys)
        return hash(self.number)

    def __lt__(self, other):
        return self.amount < other.amount

    def __len__(self):
        # len(invoice) = number of line items
        return len(self.line_items)

    def __contains__(self, item):
        # "SKU123" in invoice
        return any(li.sku == item for li in self.line_items)

    def __getitem__(self, key):
        # invoice["discount"] — dict-like access
        return getattr(self, key)

    def __enter__(self):
        # with Invoice(...) as inv:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self._status = "error"
        return False  # don't suppress exceptions

    def __add__(self, other):
        # invoice1 + invoice2 → combined amount
        return Invoice(f"COMBINED", self.amount + other.amount)

    # ── PROPERTIES ──────────────────────────────────────────

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, value):
        if value not in ("pending", "paid", "cancelled"):
            raise ValueError(f"Invalid status: {value}")
        self._status = value

    @property
    def tax_amount(self):
        return self.amount * self.tax_rate

    @property
    def total(self):
        return self.amount + self.tax_amount

    # ── CLASS + STATIC METHODS ───────────────────────────────

    @classmethod
    def from_dict(cls, data: dict) -> "Invoice":
        """Alternative constructor (factory method)"""
        return cls(data["number"], float(data["amount"]))

    @classmethod
    def get_count(cls) -> int:
        return cls._count

    @staticmethod
    def validate_number(number: str) -> bool:
        """No access to class or instance — pure utility"""
        return bool(number and number.startswith("INV-"))

    # ── NAME MANGLING ────────────────────────────────────────
    # self.__secret → stored as self._Invoice__secret
    # Prevents accidental override in subclasses
```

### Inheritance + MRO

```python
# MRO = Method Resolution Order
# Python uses C3 linearization algorithm

class A:
    def method(self): return "A"

class B(A):
    def method(self): return "B"

class C(A):
    def method(self): return "C"

class D(B, C):   # Multiple inheritance
    pass

# MRO: D → B → C → A → object
print(D.__mro__)
# (<class 'D'>, <class 'B'>, <class 'C'>, <class 'A'>, <class 'object'>)
D().method()   # "B" (follows MRO order)

# super() — calls next in MRO (not necessarily parent!)
class Animal:
    def __init__(self, name):
        self.name = name

class Dog(Animal):
    def __init__(self, name, breed):
        super().__init__(name)   # Animal.__init__
        self.breed = breed

# Mixin pattern (common in Django):
class TimestampMixin:
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Invoice(TimestampMixin, models.Model):
    # Gets created_at, updated_at from mixin
    number = models.CharField(...)

# Django CBV uses mixins extensively:
class BookingCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    # MRO: BookingCreate → LoginRequired → PermissionRequired → Create → View
    pass
```

### Dataclasses (Python 3.7+)

```python
from dataclasses import dataclass, field, asdict, astuple
from typing import ClassVar

@dataclass(frozen=True)   # immutable (hashable — can use in sets)
class Money:
    amount: float
    currency: str = "INR"

    def __post_init__(self):
        if self.amount < 0:
            raise ValueError("Amount cannot be negative")

    def __add__(self, other: "Money") -> "Money":
        if self.currency != other.currency:
            raise ValueError("Currency mismatch")
        return Money(self.amount + other.amount, self.currency)

@dataclass
class BookingRequest:
    tour_id: int
    user_id: int
    guests: int
    travel_date: str
    notes: str = ""                       # default value
    tags: list[str] = field(default_factory=list)  # mutable default!
    _internal: str = field(default="", repr=False, compare=False)
    VALID_STATUSES: ClassVar[list] = ["pending", "confirmed"]  # class var

m1 = Money(1000)
m2 = Money(500)
m3 = m1 + m2   # Money(amount=1500, currency='INR')

# __repr__, __eq__, __hash__ (if frozen) auto-generated!
print(m1)   # Money(amount=1000, currency='INR')
asdict(m1)  # {"amount": 1000, "currency": "INR"}
```

---

## TOPIC 4: DECORATORS + CONTEXT MANAGERS

### Decorators — how they work

```python
# DECORATOR = function that takes function, returns function
# Syntactic sugar for: func = decorator(func)

import functools
import time
import logging

logger = logging.getLogger(__name__)

# ── BASIC DECORATOR ────────────────────────────────────────────
def timer(func):
    @functools.wraps(func)   # preserves __name__, __doc__, etc.
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        logger.info(f"{func.__name__} took {elapsed:.3f}s")
        return result
    return wrapper

@timer
def slow_function():
    time.sleep(1)

# ── DECORATOR WITH ARGUMENTS ───────────────────────────────────
def retry(max_attempts: int = 3, exceptions: tuple = (Exception,), delay: float = 1.0):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_attempts:
                        raise
                    logger.warning(f"Attempt {attempt}/{max_attempts} failed: {e}")
                    time.sleep(delay * attempt)   # exponential backoff
        return wrapper
    return decorator

@retry(max_attempts=3, exceptions=(requests.Timeout,), delay=2.0)
def call_sap_api(invoice_id):
    return requests.post(SAP_URL, json={"id": invoice_id}, timeout=10)

# ── CLASS-BASED DECORATOR ──────────────────────────────────────
class cache:
    def __init__(self, ttl: int = 300):
        self.ttl = ttl
        self.store = {}

    def __call__(self, func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            key = (args, tuple(sorted(kwargs.items())))
            if key in self.store:
                value, expires = self.store[key]
                if time.time() < expires:
                    return value
            result = func(*args, **kwargs)
            self.store[key] = (result, time.time() + self.ttl)
            return result
        return wrapper

@cache(ttl=300)
def get_tour_details(tour_id: int) -> dict:
    return db.query(Tour).get(tour_id)

# ── STACKING DECORATORS ────────────────────────────────────────
# Order: applied bottom-up, executed top-down
@timer           # applied last, runs first
@retry(3)        # applied first
def api_call():  # original
    pass

# Equivalent:
api_call = timer(retry(3)(api_call))
```

### Context Managers

```python
from contextlib import contextmanager, asynccontextmanager
import contextlib

# ── CLASS-BASED CONTEXT MANAGER ────────────────────────────────
class DatabaseTransaction:
    def __init__(self, connection):
        self.conn = connection
        self.tx = None

    def __enter__(self):
        self.tx = self.conn.begin()
        return self.tx

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.tx.rollback()
            logger.error(f"Transaction rolled back: {exc_val}")
        else:
            self.tx.commit()
        return False   # don't suppress exception

with DatabaseTransaction(conn) as tx:
    tx.execute("INSERT INTO invoices ...")
    tx.execute("INSERT INTO sap_log ...")
    # Both commit or both rollback

# ── GENERATOR-BASED CONTEXT MANAGER ───────────────────────────
@contextmanager
def timer_context(label: str):
    start = time.perf_counter()
    try:
        yield   # execution pauses here while inside 'with' block
    finally:
        elapsed = time.perf_counter() - start
        logger.info(f"{label}: {elapsed:.3f}s")

with timer_context("SAP sync"):
    sync_all_invoices()

# ── ASYNC CONTEXT MANAGER ──────────────────────────────────────
@asynccontextmanager
async def managed_session(session_factory):
    session = session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()

async def create_booking(data):
    async with managed_session(AsyncSession) as session:
        booking = Booking(**data)
        session.add(booking)
        # commit automatic on exit

# ── contextlib UTILITIES ───────────────────────────────────────
# Suppress specific exceptions:
with contextlib.suppress(FileNotFoundError):
    os.remove("temp_file.txt")   # OK if doesn't exist

# Redirect stdout:
with contextlib.redirect_stdout(io.StringIO()) as buf:
    print("captured")
output = buf.getvalue()   # "captured\n"

# ExitStack (dynamic number of context managers):
with contextlib.ExitStack() as stack:
    files = [stack.enter_context(open(f)) for f in file_list]
    # All files opened, all closed on exit
```

---

## TOPIC 5: GENERATORS + ITERATORS

### Generators — memory efficient processing

```python
# ITERATOR PROTOCOL:
# Object with __iter__() and __next__() methods
# StopIteration when exhausted

# GENERATOR FUNCTION (yield):
def fibonacci():
    a, b = 0, 1
    while True:
        yield a        # pauses here, returns a, remembers state
        a, b = b, a + b

gen = fibonacci()
next(gen)   # 0
next(gen)   # 1
next(gen)   # 1
next(gen)   # 2

# MEMORY COMPARISON:
# 1 million numbers:
list(range(1_000_000))           # 8MB in memory
(x for x in range(1_000_000))   # ~120 bytes! (generator object only)

# ── REAL USE CASE: Large file processing ─────────────────────────
def read_invoices_in_batches(filepath: str, batch_size: int = 1000):
    """Process 1M invoice CSV without loading all in memory"""
    with open(filepath) as f:
        batch = []
        for line in f:                    # f is also a generator!
            batch.append(parse_line(line))
            if len(batch) == batch_size:
                yield batch               # yield batch, pause
                batch = []               # reset
        if batch:
            yield batch                  # last partial batch

for batch in read_invoices_in_batches("invoices.csv"):
    Invoice.objects.bulk_create(batch)   # 1000 at a time

# ── GENERATOR EXPRESSION ──────────────────────────────────────
total = sum(inv.amount for inv in invoices if inv.status == "paid")
# vs list comprehension (loads all in memory):
total = sum([inv.amount for inv in invoices if inv.status == "paid"])

# ── YIELD FROM (delegate to sub-generator) ────────────────────
def chain(*iterables):
    for it in iterables:
        yield from it   # delegates to each

list(chain([1, 2], [3, 4], [5]))   # [1, 2, 3, 4, 5]

# ── SEND TO GENERATOR (coroutine-like) ────────────────────────
def accumulator():
    total = 0
    while True:
        value = yield total   # yield current total, receive new value
        if value is None:
            break
        total += value

acc = accumulator()
next(acc)           # prime the generator (run to first yield)
acc.send(10)        # 10
acc.send(20)        # 30
acc.send(5)         # 35
```

---

## TOPIC 6: ASYNC/AWAIT — EVENT LOOP INTERNALS

### How async works

```
ASYNC ARCHITECTURE
────────────────────────────────────────────────────────────────

EVENT LOOP (single thread)
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  READY QUEUE (coroutines ready to run)                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                    │
│  │ coro A   │ │ coro B   │ │ coro C   │                    │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘                    │
│       │            │             │                           │
│  Run A until "await"             │                           │
│  A: await asyncio.sleep(1) ─────────────────► IO WAITING    │
│  (A suspended, B runs)           │              │            │
│  Run B until "await"             │              │            │
│  B: await http_request() ───────────────────►  │            │
│  (B suspended, C runs)           │              │            │
│  Run C...                        │              │            │
│                                  │  (1 second later)         │
│  A's sleep done ◄─────────────────────────────┘            │
│  A added back to ready queue     │                           │
│                                  │                           │
└──────────────────────────────────┘                           │

KEY INSIGHT:
Single thread, no parallelism for CPU work.
But: while waiting for I/O, other coroutines run.
N coroutines waiting for I/O = N concurrent "waits" in one thread!
```

### Async patterns

```python
import asyncio
import aiohttp
import time

# ── BASIC ASYNC ────────────────────────────────────────────────
async def fetch_tour(session, tour_id: int) -> dict:
    async with session.get(f"/api/tours/{tour_id}") as response:
        return await response.json()

async def main():
    async with aiohttp.ClientSession(base_url="https://api.example.com") as session:
        tour = await fetch_tour(session, 42)
        print(tour)

asyncio.run(main())

# ── CONCURRENT EXECUTION ───────────────────────────────────────
async def fetch_all_tours(tour_ids: list[int]) -> list[dict]:
    async with aiohttp.ClientSession() as session:
        # SEQUENTIAL (bad — waits for each one):
        # results = [await fetch_tour(session, id) for id in tour_ids]
        # 100 tours × 100ms = 10 seconds

        # CONCURRENT (good — all fired at once):
        tasks = [fetch_tour(session, id) for id in tour_ids]
        results = await asyncio.gather(*tasks)
        # 100 tours × 100ms = ~100ms (all concurrent!)
        return results

# ── gather vs wait ────────────────────────────────────────────
# gather: all complete → return all results (or raise on first error)
results = await asyncio.gather(coro1(), coro2(), coro3())

# gather with return_exceptions: don't raise, return exception in result
results = await asyncio.gather(
    coro1(), coro2(), coro3(),
    return_exceptions=True
)
valid = [r for r in results if not isinstance(r, Exception)]

# wait: more control (FIRST_COMPLETED, ALL_COMPLETED, FIRST_EXCEPTION)
tasks = [asyncio.create_task(coro()) for coro in coros]
done, pending = await asyncio.wait(tasks, timeout=5.0,
                                   return_when=asyncio.FIRST_COMPLETED)
# Cancel pending:
for task in pending:
    task.cancel()

# ── ASYNC CONTEXT MANAGER ─────────────────────────────────────
class AsyncDBConnection:
    async def __aenter__(self):
        self.conn = await asyncpg.connect(DATABASE_URL)
        return self.conn

    async def __aexit__(self, *args):
        await self.conn.close()

async with AsyncDBConnection() as conn:
    rows = await conn.fetch("SELECT * FROM bookings")

# ── ASYNC GENERATOR ───────────────────────────────────────────
async def stream_ai_tokens(prompt: str):
    async with anthropic_client.messages.stream(
        model="claude-sonnet-4-6",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1000,
    ) as stream:
        async for text in stream.text_stream:
            yield text

# FastAPI SSE endpoint:
from fastapi.responses import StreamingResponse

@app.get("/ai/stream")
async def ai_stream(prompt: str):
    async def generate():
        async for token in stream_ai_tokens(prompt):
            yield f"data: {json.dumps({'token': token})}\n\n"
    return StreamingResponse(generate(), media_type="text/event-stream")

# ── THE TRAP: blocking in async ─────────────────────────────────
# BAD: CPU/blocking call in async → blocks entire event loop!
@app.get("/bad")
async def bad_endpoint():
    time.sleep(5)              # BLOCKS event loop for 5s!
    result = heavy_compute()   # BLOCKS event loop!
    return result

# GOOD: run blocking in thread pool
import asyncio
from concurrent.futures import ThreadPoolExecutor

@app.get("/good")
async def good_endpoint():
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,           # default ThreadPoolExecutor
        heavy_compute   # blocking function
    )
    return result

# OR with FastAPI:
@app.get("/also-good")
def sync_endpoint():   # no async def → FastAPI runs in thread pool
    time.sleep(5)      # OK! not blocking event loop
    return result
```

---

## TOPIC 7: TYPE HINTS + MYPY

### Type system

```python
from typing import (
    Optional, Union, Any, Callable, TypeVar,
    Generic, Protocol, TypedDict, Literal, overload
)
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bookings.models import Booking   # avoid circular import

# ── BASIC TYPES ────────────────────────────────────────────────
def process_invoice(
    invoice_id: int,
    amount: float,
    status: str,
    notes: str | None = None,        # Python 3.10+ syntax
    tags: list[str] | None = None,   # equivalent to Optional[list[str]]
) -> dict[str, Any]:
    ...

# ── UNION ─────────────────────────────────────────────────────
def parse_amount(value: str | int | float) -> float:
    return float(value)

# ── CALLABLE ──────────────────────────────────────────────────
def apply_transform(
    data: list[dict],
    transform: Callable[[dict], dict]
) -> list[dict]:
    return [transform(item) for item in data]

# ── TYPEVAR (generic functions) ────────────────────────────────
T = TypeVar("T")

def first(items: list[T]) -> T | None:
    return items[0] if items else None

result: int | None = first([1, 2, 3])      # T inferred as int
result: str | None = first(["a", "b"])     # T inferred as str

# ── GENERIC CLASS ─────────────────────────────────────────────
class Repository(Generic[T]):
    def __init__(self, model_class: type[T]):
        self.model = model_class

    def get(self, id: int) -> T | None:
        return self.model.objects.filter(id=id).first()

    def create(self, **data) -> T:
        return self.model.objects.create(**data)

invoice_repo = Repository(Invoice)
booking_repo = Repository(Booking)

# ── PROTOCOL (structural subtyping / duck typing) ─────────────
class Serializable(Protocol):
    def to_dict(self) -> dict: ...
    def to_json(self) -> str: ...

def save_to_cache(obj: Serializable, key: str) -> None:
    cache.set(key, obj.to_json(), timeout=300)
# Any class with to_dict + to_json works, no explicit inheritance!

# ── TYPEDDICT ──────────────────────────────────────────────────
class BookingData(TypedDict):
    tour_id: int
    user_id: int
    guests: int
    travel_date: str
    notes: str   # required

class BookingDataOptional(TypedDict, total=False):
    notes: str   # optional when total=False

def create_booking(data: BookingData) -> Booking: ...

# ── LITERAL ───────────────────────────────────────────────────
Status = Literal["pending", "confirmed", "cancelled", "completed"]

def update_status(booking_id: int, status: Status) -> None: ...
# update_status(1, "invalid")  ← mypy error!

# ── OVERLOAD ──────────────────────────────────────────────────
@overload
def parse(value: str) -> dict: ...
@overload
def parse(value: bytes) -> list: ...

def parse(value: str | bytes) -> dict | list:
    if isinstance(value, str):
        return json.loads(value)
    return list(value)
```

---

## TOPIC 8: TESTING — PYTEST PATTERNS

### Pytest patterns

```python
# ── BASIC TEST ────────────────────────────────────────────────
# tests/test_invoice.py

def test_invoice_creation():
    invoice = Invoice(number="INV-001", amount=1000.0)
    assert invoice.number == "INV-001"
    assert invoice.amount == 1000.0
    assert invoice.status == "pending"

def test_invalid_status_raises():
    invoice = Invoice("INV-001", 1000.0)
    with pytest.raises(ValueError, match="Invalid status"):
        invoice.status = "invalid_status"

# ── FIXTURES ──────────────────────────────────────────────────
import pytest
from django.test import RequestFactory

@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="admin@test.com",
        password="testpass123",
        role="admin"
    )

@pytest.fixture
def api_client(admin_user):
    from rest_framework.test import APIClient
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client

@pytest.fixture
def invoice_data():
    return {
        "number": "INV-001",
        "amount": "1000.00",
        "company": 1,
    }

# Scope: function (default), class, module, session
@pytest.fixture(scope="session")
def db_connection():
    conn = create_db_connection()
    yield conn
    conn.close()

# ── PARAMETRIZE ──────────────────────────────────────────────
@pytest.mark.parametrize("amount,expected_tax", [
    (1000, 180),
    (5000, 900),
    (10000, 1800),
    (0, 0),
])
def test_tax_calculation(amount, expected_tax):
    invoice = Invoice("INV-001", amount)
    assert invoice.tax_amount == pytest.approx(expected_tax)

@pytest.mark.parametrize("status,should_raise", [
    ("pending", False),
    ("paid", False),
    ("invalid", True),
    ("", True),
])
def test_status_validation(status, should_raise):
    invoice = Invoice("INV-001", 1000)
    if should_raise:
        with pytest.raises(ValueError):
            invoice.status = status
    else:
        invoice.status = status
        assert invoice.status == status

# ── MOCKING ───────────────────────────────────────────────────
from unittest.mock import patch, MagicMock, AsyncMock

def test_sap_sync_success():
    with patch("invoicing.tasks.sap_client.push_invoice") as mock_push:
        mock_push.return_value = {"ref": "SAP-12345"}
        result = sync_invoice_to_sap(invoice_id=1)
        mock_push.assert_called_once_with(...)
        assert result["sap_ref"] == "SAP-12345"

def test_sap_sync_retries_on_timeout():
    with patch("invoicing.tasks.sap_client.push_invoice") as mock_push:
        mock_push.side_effect = [
            requests.Timeout(),    # first call fails
            requests.Timeout(),    # second call fails
            {"ref": "SAP-999"},    # third call succeeds
        ]
        result = sync_invoice_to_sap.apply(args=[1], retries=0)
        assert mock_push.call_count == 3

# Async mock:
@pytest.mark.asyncio
async def test_async_function():
    with patch("module.async_func", new_callable=AsyncMock) as mock:
        mock.return_value = {"result": "ok"}
        result = await my_async_function()
        assert result == {"result": "ok"}

# ── DRF API TESTS ─────────────────────────────────────────────
@pytest.mark.django_db
class TestBookingAPI:
    def test_create_booking_success(self, api_client, invoice_data):
        response = api_client.post("/api/v1/bookings/", invoice_data)
        assert response.status_code == 201
        assert response.data["number"] == invoice_data["number"]

    def test_create_booking_unauthenticated(self):
        from rest_framework.test import APIClient
        client = APIClient()   # no auth
        response = client.post("/api/v1/bookings/", {})
        assert response.status_code == 401

    def test_list_only_own_bookings(self, api_client, admin_user):
        # User can only see their own bookings
        other_booking = Booking.objects.create(user=other_user, ...)
        my_booking = Booking.objects.create(user=admin_user, ...)
        response = api_client.get("/api/v1/bookings/")
        ids = [b["id"] for b in response.data["results"]]
        assert my_booking.id in ids
        assert other_booking.id not in ids
```

---

## TOPIC 9: PERFORMANCE — PROFILING + OPTIMIZATION

### Profiling tools

```python
# ── cPROFILE ──────────────────────────────────────────────────
import cProfile
import pstats

# Profile a function
profiler = cProfile.Profile()
profiler.enable()
slow_function()
profiler.disable()

stats = pstats.Stats(profiler)
stats.sort_stats("cumulative")
stats.print_stats(20)   # top 20 functions by cumulative time

# CLI:
python -m cProfile -s cumulative script.py

# ── LINE PROFILER ─────────────────────────────────────────────
# pip install line_profiler
@profile   # added by line_profiler
def process_invoices():
    for invoice in invoices:    # time per line shown!
        total += invoice.amount
        ...

# kernprof -l -v script.py

# ── MEMORY PROFILER ───────────────────────────────────────────
# pip install memory-profiler
@memory_profiler.profile
def load_all_invoices():
    return Invoice.objects.all()   # memory usage per line!

# ── timeit (micro-benchmarks) ─────────────────────────────────
import timeit

# x in list vs x in set:
setup = "data = list(range(10000)); s = set(range(10000)); x = 9999"
list_time = timeit.timeit("x in data", setup=setup, number=100000)
set_time = timeit.timeit("x in s", setup=setup, number=100000)
print(f"List: {list_time:.3f}s, Set: {set_time:.3f}s")
# List: 2.3s, Set: 0.002s → 1000x faster!
```

### Optimization techniques

```python
# ── __SLOTS__ (memory optimization for many instances) ─────────
class Point:
    __slots__ = ["x", "y"]   # prevents __dict__ creation
    def __init__(self, x, y):
        self.x = x
        self.y = y

# 1M Point objects:
# Without slots: ~140MB
# With slots: ~60MB (57% less!)

# ── LRUCACHE (memoization) ────────────────────────────────────
from functools import lru_cache, cache

@lru_cache(maxsize=128)   # cache last 128 calls
def fibonacci(n: int) -> int:
    if n < 2:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)

# cache = lru_cache(maxsize=None) — unlimited cache (Python 3.9+)
@cache
def get_tour_permissions(user_id: int, tour_id: int) -> bool:
    return db.check_permission(user_id, tour_id)

fibonacci.cache_info()   # hits, misses, maxsize, currsize
fibonacci.cache_clear()  # invalidate

# ── STRING CONCATENATION ───────────────────────────────────────
# BAD: O(n²) — creates new string each time
result = ""
for item in large_list:
    result += str(item)

# GOOD: O(n)
result = "".join(str(item) for item in large_list)

# ── LIST COMPREHENSION vs map/filter ──────────────────────────
# List comprehension: fastest, most readable
squares = [x**2 for x in range(1000)]

# Generator expression: memory efficient (no list created)
total = sum(x**2 for x in range(1000000))

# map/filter: slightly slower than comprehension, less readable
squares = list(map(lambda x: x**2, range(1000)))

# ── BULK DB OPERATIONS ────────────────────────────────────────
# BAD: 1000 INSERT queries
for data in invoice_data_list:
    Invoice.objects.create(**data)

# GOOD: 1 INSERT query
Invoice.objects.bulk_create([Invoice(**d) for d in invoice_data_list])

# BAD: 1000 UPDATE queries
for invoice in Invoice.objects.all():
    invoice.status = "processed"
    invoice.save()

# GOOD: 1 UPDATE query
Invoice.objects.all().update(status="processed")

# F expression (atomic update, no race condition):
from django.db.models import F
Invoice.objects.filter(status="pending").update(
    retry_count=F("retry_count") + 1
)
```

---

## TOPIC 10: COMMON PATTERNS

### Design patterns in Python

```python
# ── SINGLETON ─────────────────────────────────────────────────
class DatabasePool:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.pool = create_pool()
        return cls._instance

# Thread-safe singleton:
import threading

class SafeSingleton:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
        return cls._instance

# ── FACTORY ───────────────────────────────────────────────────
class NotificationFactory:
    _registry: dict[str, type] = {}

    @classmethod
    def register(cls, channel: str):
        def decorator(notifier_class):
            cls._registry[channel] = notifier_class
            return notifier_class
        return decorator

    @classmethod
    def create(cls, channel: str) -> "Notifier":
        notifier_class = cls._registry.get(channel)
        if not notifier_class:
            raise ValueError(f"Unknown channel: {channel}")
        return notifier_class()

@NotificationFactory.register("email")
class EmailNotifier:
    def send(self, message): ...

@NotificationFactory.register("sms")
class SMSNotifier:
    def send(self, message): ...

# Usage:
notifier = NotificationFactory.create("email")
notifier.send("Booking confirmed!")

# ── OBSERVER (signals) ────────────────────────────────────────
from typing import Callable

class EventBus:
    _handlers: dict[str, list[Callable]] = {}

    @classmethod
    def subscribe(cls, event: str):
        def decorator(handler: Callable):
            cls._handlers.setdefault(event, []).append(handler)
            return handler
        return decorator

    @classmethod
    def publish(cls, event: str, **kwargs):
        for handler in cls._handlers.get(event, []):
            handler(**kwargs)

@EventBus.subscribe("booking.created")
def send_confirmation(booking_id: int, **kwargs):
    send_booking_email.delay(booking_id)

@EventBus.subscribe("booking.created")
def update_guide_calendar(booking_id: int, **kwargs):
    update_calendar.delay(booking_id)

EventBus.publish("booking.created", booking_id=42)

# ── STRATEGY PATTERN ─────────────────────────────────────────
from abc import ABC, abstractmethod

class PricingStrategy(ABC):
    @abstractmethod
    def calculate(self, base_price: float, guests: int) -> float: ...

class RegularPricing(PricingStrategy):
    def calculate(self, base_price, guests):
        return base_price * guests

class GroupDiscountPricing(PricingStrategy):
    def calculate(self, base_price, guests):
        discount = 0.1 if guests >= 10 else 0
        return base_price * guests * (1 - discount)

class EarlyBirdPricing(PricingStrategy):
    def calculate(self, base_price, guests):
        return base_price * guests * 0.85   # 15% off

class BookingPriceCalculator:
    def __init__(self, strategy: PricingStrategy):
        self.strategy = strategy

    def calculate_total(self, base_price: float, guests: int) -> float:
        return self.strategy.calculate(base_price, guests)

# ── DESCRIPTOR PROTOCOL ─────────────────────────────────────
class PositiveNumber:
    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, obj, type=None):
        if obj is None:
            return self
        return obj.__dict__.get(self.name, 0)

    def __set__(self, obj, value):
        if value < 0:
            raise ValueError(f"{self.name} must be positive")
        obj.__dict__[self.name] = value

class Invoice:
    amount = PositiveNumber()   # descriptor
    quantity = PositiveNumber()

inv = Invoice()
inv.amount = -100   # ValueError: amount must be positive
```

---

## TOPIC 11: INTERVIEW Q&A — 20 Questions

---

**Q1. GIL kya hai — CPU-bound vs I/O-bound mein kya difference hai?**

```
GIL = Global Interpreter Lock.
CPython mein sirf ek thread ek time pe Python bytecode execute kar sakta hai.

CPU-BOUND (GIL problem):
Image resize, heavy computation, ML inference.
2 threads = same speed as 1 thread.
WHY: Both threads want CPU, GIL only lets one run.
FIX: multiprocessing.Pool (separate processes, each has own GIL)

I/O-BOUND (GIL released):
HTTP requests, DB queries, file I/O.
Thread 1 waits for HTTP → GIL released → Thread 2 runs.
FIX: threading OR asyncio (both work)

REAL EXAMPLE (Youngman Beta):
SAP HANA sync: HTTP I/O → asyncio / threading both fine
PDF generation: CPU-bound → multiprocessing

asyncio BETTER than threading for I/O because:
Thousands of concurrent operations, single thread, no OS thread overhead.
threading: OS-managed, context switch cost, 1000 threads = heavy.
```

---

**Q2. `@staticmethod` vs `@classmethod` vs instance method — kab kya?**

```
INSTANCE METHOD (self):
Ek specific object ke liye kaam karta hai.
invoice.calculate_tax()   ← invoice object ka amount use karta hai

CLASSMETHOD (cls):
Class-level operation. Alternative constructors.
Invoice.from_sap_response(sap_dict)  ← sap dict se Invoice banao
Invoice.from_csv_row(row)            ← CSV row se Invoice banao
cls.tax_rate  ← class variable access kar sakta hai

STATICMETHOD:
No self, no cls — pure utility function.
Invoice.validate_invoice_number("INV-001")  ← format check
Bas class ke namespace mein rakha hai (logically belongs here).
Could be a module-level function but here it's cleaner.

RULE:
Uses self? → instance method
Needs cls (class variable, alternative constructor)? → classmethod
Neither? → staticmethod (or module function)
```

---

**Q3. Generator vs list comprehension — kab kya?**

```
LIST COMPREHENSION:
[x for x in range(1000)]
→ 1000 items in memory immediately
→ Use when: small dataset, need random access, iterate multiple times

GENERATOR EXPRESSION:
(x for x in range(1000))
→ One item at a time, ~120 bytes
→ Use when: large dataset, iterate once, memory critical

REAL EXAMPLE (Youngman Beta):
10,000 invoices from DB → process each → send to SAP

# BAD: loads all 10k in memory
invoices = list(Invoice.objects.all())   # all in RAM!

# GOOD: generator via QuerySet (already lazy)
for invoice in Invoice.objects.filter(status="pending").iterator():
    sync_to_sap(invoice)   # one at a time

# .iterator(): disables Django's per-queryset caching
# Perfect for large datasets, memory stays low
```

---

**Q4. `__enter__` aur `__exit__` kya hain — context manager kyu useful hai?**

```
with statement ke liye zaroorat hai:
__enter__: setup, return resource
__exit__: cleanup (called even if exception!)

WHY USEFUL:
Guaranteed cleanup:
- File: always closed (even on exception)
- DB connection: always released
- Lock: always released (deadlock prevention)

WITHOUT CONTEXT MANAGER:
conn = db.get_connection()
try:
    result = conn.execute(query)
    conn.commit()
except:
    conn.rollback()
finally:
    conn.close()   # must remember every time!

WITH CONTEXT MANAGER:
with db.transaction() as conn:
    conn.execute(query)
# commit/rollback/close automatic!

TERA REAL USE:
Django transaction.atomic() = context manager
with transaction.atomic():
    invoice = Invoice.objects.create(...)
    sap_log = SAPLog.objects.create(...)
    # Both commit or both rollback automatically

Timer, profiler, temp directory — all context managers.
```

---

**Q5. Python `*args` aur `**kwargs` — kab kya?**

```python
def flexible_function(required, *args, keyword_only, **kwargs):
    #  required = positional, mandatory
    #  *args    = variable positional (tuple)
    #  keyword_only = after *, must be named
    #  **kwargs = variable keyword (dict)
    pass

# REAL USE CASE: decorator that passes through arguments
def log_call(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):    # capture everything
        logger.info(f"Calling {func.__name__}")
        return func(*args, **kwargs)  # pass everything through
    return wrapper

# Unpacking:
def add(a, b, c):
    return a + b + c

numbers = [1, 2, 3]
add(*numbers)        # add(1, 2, 3) — positional unpack

config = {"a": 1, "b": 2, "c": 3}
add(**config)        # add(a=1, b=2, c=3) — keyword unpack

# Forcing keyword-only arguments:
def create_user(*, email, password, role="customer"):
    # * forces all args after it to be keyword-only
    # Can't call: create_user("a@b.com", "pass")
    # Must call: create_user(email="a@b.com", password="pass")
    pass
```

---

**Q6. Python memory management — garbage collection kaise kaam karta hai?**

```
TWO MECHANISMS:

1. REFERENCE COUNTING (primary):
Every object has refcount.
refcount = 0 → immediately freed.
Fast, deterministic (freed right away).

Problem: Cycles
a = []; b = []
a.append(b); b.append(a)  # circular reference!
del a, b  # both refcount = 1 (not 0!) → not freed!

2. CYCLIC GC (secondary):
Periodically scans for cycles.
3 generations: 0 (young), 1, 2 (old)
gen0 collected most often (new objects die young — generational hypothesis)
gc.collect() → manual trigger
gc.disable() → turn off (if you know no cycles, for performance)

PRACTICAL IMPACT:
Django: ORM objects → large querysets → memory grows
Fix: queryset.iterator() (streaming)
Fix: del large_object → explicit free

Memory profiler to find leaks:
from memory_profiler import memory_usage
mem = memory_usage((my_function, args), interval=0.1)
```

---

**Q7. `deepcopy` vs `copy` vs assignment — kab kya?**

```python
import copy

original = {"key": [1, 2, 3]}

# ASSIGNMENT (no copy — shared reference)
ref = original
ref["key"].append(4)   # original["key"] also changed!
# original["key"] = [1, 2, 3, 4]

# SHALLOW COPY (new dict, but nested objects shared)
shallow = copy.copy(original)
shallow["key"].append(5)   # original["key"] also changed!
# Both point to same list object

# DEEP COPY (fully independent)
deep = copy.deepcopy(original)
deep["key"].append(6)   # original unchanged!

WHEN:
Assignment: just want another name for same object
Shallow copy: top-level independent, nested OK to share (immutable data)
Deep copy: truly independent clone needed

DJANGO REAL CASE:
initial_config = {"timeout": 30, "retries": 3, "headers": []}
# Deep copy per request, so one request's headers don't pollute another's
request_config = copy.deepcopy(initial_config)
```

---

**Q8. Python `__slots__` kya hai — kab use karo?**

```
DEFAULT (no slots):
Every instance has __dict__ (a dictionary).
Flexible: add any attribute anytime.
Memory: dict overhead ~200-300 bytes per instance.

WITH __slots__:
class Point:
    __slots__ = ("x", "y")
    def __init__(self, x, y):
        self.x = x; self.y = y

No __dict__ created.
Only x and y can be set (no dynamic attributes).
Memory: ~50 bytes per instance.

WHEN TO USE:
- Millions of small instances (coordinates, records)
- Performance-critical code
- Data class where you know all attributes upfront

TRADEOFFS:
❌ Can't add new attributes dynamically
❌ Multiple inheritance complications
❌ Can't pickle easily without __getstate__/__setstate__
✅ 50-60% less memory
✅ Slightly faster attribute access

MY EXPERIENCE:
NFC Asset Tracker: location Point objects with lat/lng
→ 100k location history entries → __slots__ → 40% less RAM
```

---

**Q9. Difference between `iter()` and `next()` — how does for loop work?**

```python
# FOR LOOP DESUGARS TO:
for item in iterable:
    process(item)

# Is equivalent to:
iterator = iter(iterable)   # calls __iter__
while True:
    try:
        item = next(iterator)   # calls __next__
        process(item)
    except StopIteration:
        break

# CUSTOM ITERATOR:
class Countdown:
    def __init__(self, start):
        self.current = start

    def __iter__(self):
        return self   # returns itself (it IS the iterator)

    def __next__(self):
        if self.current <= 0:
            raise StopIteration
        value = self.current
        self.current -= 1
        return value

list(Countdown(5))   # [5, 4, 3, 2, 1]

# LAZY FILE READING:
# Python's file object is an iterator!
with open("large_file.txt") as f:
    for line in f:   # reads one line at a time!
        process(line)
# vs f.readlines() → loads entire file in memory!
```

---

**Q10. `functools.wraps` kyon zaroori hai decorator mein?**

```python
def bad_decorator(func):
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper

def good_decorator(func):
    @functools.wraps(func)   # copies metadata
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper

@bad_decorator
def my_function():
    """This is my function's docstring"""
    pass

@good_decorator
def my_function2():
    """This is my function2's docstring"""
    pass

my_function.__name__    # "wrapper" — WRONG!
my_function.__doc__     # None — WRONG!

my_function2.__name__   # "my_function2" — CORRECT!
my_function2.__doc__    # "This is my function2's docstring"

WHY MATTERS:
- Debugging: stack traces show "wrapper" everywhere (confusing!)
- Sphinx docs: wrong function names
- pytest: wrong test names
- DRF: introspection for schema generation breaks

ALWAYS use @functools.wraps in decorators!
```

---

## QUICK RECALL CARD

```
╔══════════════════════════════════════════════════════════════════╗
║              PYTHON DEEP DIVE RECALL CARD                        ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  INTERNALS                                                       ║
║  CPython = bytecode + PVM (not compiled to machine code)        ║
║  GIL = one thread runs Python at a time (CPython only)         ║
║  GIL released during I/O → threading works for I/O bound       ║
║  CPU-bound → multiprocessing (separate GIL per process)         ║
║  refcount = 0 → freed immediately (deterministic)               ║
║  Cyclic GC → handles circular references (3 generations)        ║
║  is = identity (same object), == = equality (same value)        ║
║  None/True/False → always use `is`, not ==                      ║
║                                                                  ║
║  DATA STRUCTURES                                                 ║
║  list: append O(1), insert O(n), in O(n)                        ║
║  dict: get/set/in O(1) average                                  ║
║  set: add/in O(1) — use for fast membership check!             ║
║  deque: appendleft/popleft O(1) (list is O(n))                 ║
║                                                                  ║
║  OOP                                                             ║
║  MRO = D→B→C→A→object (C3 linearization)                       ║
║  __repr__ = developer, __str__ = user                           ║
║  @property = computed attribute, setter = validation            ║
║  @classmethod = cls (alternative constructor)                   ║
║  @staticmethod = utility (no self, no cls)                      ║
║  __slots__ = no __dict__, 50% less memory                      ║
║  dataclass = auto __init__ __repr__ __eq__                      ║
║                                                                  ║
║  DECORATORS + CONTEXT MANAGERS                                   ║
║  @functools.wraps → preserves __name__ __doc__                 ║
║  Decorator order: outer runs first                               ║
║  __enter__/__exit__ = setup + guaranteed cleanup                ║
║  @contextmanager → yield-based (try/finally)                    ║
║                                                                  ║
║  GENERATORS                                                      ║
║  yield = pause + return (lazy evaluation)                       ║
║  Generator expression = memory efficient (vs list comp)         ║
║  .iterator() on Django QuerySet = stream from DB               ║
║  yield from = delegate to sub-generator                         ║
║                                                                  ║
║  ASYNC                                                           ║
║  Event loop = single thread, switches on await                  ║
║  await = pause coroutine, let others run                        ║
║  asyncio.gather = concurrent (all at once)                      ║
║  blocking in async = blocks ENTIRE event loop!                  ║
║  Fix: loop.run_in_executor() or sync def (FastAPI threadpool)  ║
║                                                                  ║
║  PERFORMANCE                                                     ║
║  cProfile → function-level profiling                            ║
║  @lru_cache → memoization (functools)                           ║
║  bulk_create / update() → avoid N individual queries           ║
║  "".join() → O(n), += strings → O(n²)                         ║
║  set membership → O(1) vs list O(n)                            ║
╚══════════════════════════════════════════════════════════════════╝
```

---

*Last updated: 2026-08-15 · PwC Interview 2026-08-18*
*Skills: Python Internals · OOP · Async · Decorators · Generators · Type Hints · Testing*