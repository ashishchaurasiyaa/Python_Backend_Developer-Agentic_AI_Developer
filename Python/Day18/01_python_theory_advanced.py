"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PYTHON THEORY ADVANCED — CPython, Copy, Iterators, Futures, Profiling
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Day 18 — Architecture-level understanding of Python internals.

Topics:
  01. CPython internals  — PyObject, int cache, string interning
  02. Shallow vs Deep Copy
  03. Call by Object Reference
  04. Generator .send() / .throw() / .close()
  05. Iterator Protocol
  06. ThreadPoolExecutor + ProcessPoolExecutor + concurrent.futures
  07. Threading vs Multiprocessing vs Asyncio decision matrix
  08. dataclass vs NamedTuple vs TypedDict
  09. Walrus operator :=  +  match statement (Python 3.10+)
  10. Memory leak detection — gc, weakref, tracemalloc
  11. Performance profiling — cProfile, pstats, timeit, tracemalloc

Run:  python 01_python_theory_advanced.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import sys
import copy
import gc
import weakref
import tracemalloc
import cProfile
import pstats
import io
import timeit
import threading
import multiprocessing
import asyncio
import time
import dataclasses
from dataclasses import dataclass, field
from typing import NamedTuple, TypedDict, Optional, List
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed, Future


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 01 — CPython Internals: PyObject, int cache, string interning
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# ARCHITECTURE:
#   Every Python object in CPython is a C struct called PyObject with:
#     ob_refcnt  — reference count (garbage collection trigger)
#     ob_type    — pointer to the type object (int, str, list …)
#   CPython pre-allocates integers in the range [-5, 256] as singletons.
#   This is a CPython *implementation detail*, not part of the language spec.
#   String interning: CPython automatically interns identifier-like strings
#   (no spaces, looks like a variable name). You can force interning with
#   sys.intern() to share the same object across the process.
#   id() returns the memory address of the object in CPython.

print("\n" + "=" * 60)
print("SECTION 01 — CPython Internals")
print("=" * 60)

# --- int cache demo ---
a = 256
b = 256
print(f"a = 256, b = 256  →  a is b: {a is b}")        # True (cached)

x = 257
y = 257
print(f"x = 257, y = 257  →  x is y: {x is y}")        # False (not cached, CPython may vary)

# --- id() is memory address in CPython ---
num = 42
print(f"id(42)  = {id(42)}")
print(f"id(num) = {id(num)}  →  same object: {id(42) == id(num)}")

# --- string interning ---
s1 = "hello_world"          # Looks like identifier — auto-interned
s2 = "hello_world"
print(f'"hello_world" auto-interned  →  s1 is s2: {s1 is s2}')

s3 = "hello world"          # Space → NOT auto-interned
s4 = "hello world"
print(f'"hello world" NOT auto-interned  →  s3 is s4: {s3 is s4}')

s5 = sys.intern("hello world")
s6 = sys.intern("hello world")
print(f'sys.intern("hello world")    →  s5 is s6: {s5 is s6}')  # True

# --- reference count ---
my_list = [1, 2, 3]
print(f"sys.getrefcount([1,2,3]) = {sys.getrefcount(my_list)}")
# +1 because getrefcount() itself takes a reference

# Interview Q&A:
# Q: Why does `a = 256; b = 256; a is b` return True but `a = 257` doesn't?
# A: CPython pre-allocates integers -5 to 256 as singletons in a C array.
#    Integers outside this range are freshly allocated each time.
#
# Q: What is the difference between `is` and `==`?
# A: `is` compares identity (same memory address / id()), `==` compares value.
#
# Q: What is string interning and why does CPython do it?
# A: CPython interns strings that look like identifiers to save memory and speed
#    up dictionary key lookups (used heavily in attribute access).
#
# Q: What is PyObject?
# A: Every Python value is represented as a C struct PyObject { ob_refcnt, ob_type }.
#    This is why Python is slow for tight loops — every operation goes through this struct.
#
# Q: What is sys.getrefcount() and why is it always +1?
# A: It returns the reference count of the object.
#    The +1 is because passing the object to getrefcount() itself creates a temporary ref.


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 02 — Shallow Copy vs Deep Copy
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# ARCHITECTURE:
#   Shallow copy: creates a new container object but the elements inside still
#   point to the same objects as the original. One level deep.
#   Deep copy: recursively creates new copies of all nested objects. Completely
#   independent from the original.
#   Built-in approaches:
#     list[:]  or  list.copy()   → shallow
#     copy.copy(obj)             → shallow (calls __copy__ if defined)
#     copy.deepcopy(obj)         → deep   (calls __deepcopy__ if defined)
#   Immutables (int, str, tuple) are not "copied" — references are reused
#   because they can never be mutated. This is safe and efficient.

print("\n" + "=" * 60)
print("SECTION 02 — Shallow Copy vs Deep Copy")
print("=" * 60)

original = [[1, 2, 3], [4, 5, 6]]
shallow  = copy.copy(original)
deep     = copy.deepcopy(original)

original[0].append(99)

print(f"original : {original}")   # [[1,2,3,99], [4,5,6]]
print(f"shallow  : {shallow}")    # [[1,2,3,99], [4,5,6]]  ← inner list shared!
print(f"deep     : {deep}")       # [[1,2,3],    [4,5,6]]  ← fully independent

# --- custom __copy__ and __deepcopy__ ---
class Matrix:
    def __init__(self, data: list):
        self.data = data

    def __copy__(self):
        print("  __copy__ called")
        return Matrix(self.data[:])           # new list, same inner objects

    def __deepcopy__(self, memo):
        print("  __deepcopy__ called")
        return Matrix(copy.deepcopy(self.data, memo))

    def __repr__(self):
        return f"Matrix({self.data})"

m1 = Matrix([[1, 2], [3, 4]])
m2 = copy.copy(m1)
m3 = copy.deepcopy(m1)
m1.data[0].append(9)
print(f"m1 after mutation: {m1}")
print(f"m2 (shallow):      {m2}")   # inner list shared — sees the 9
print(f"m3 (deep):         {m3}")   # fully independent

# --- tuple gotcha ---
t = ([1, 2], [3, 4])
st = copy.copy(t)           # new tuple, same inner lists
print(f"tuple shallow copy id same? {t[0] is st[0]}")   # True

# Interview Q&A:
# Q: What is the difference between shallow and deep copy?
# A: Shallow copy creates a new container but keeps references to the same inner
#    objects. Deep copy recursively duplicates all nested objects.
#
# Q: Does copy.copy() on a tuple actually create a new object?
# A: For a plain tuple of immutables, CPython may return the *same* tuple
#    (optimization). For a tuple containing mutables, it creates a new tuple
#    but shares the mutable inner objects.
#
# Q: When would you override __deepcopy__?
# A: When your class has references that should NOT be duplicated (e.g. file handles,
#    database connections, singletons) or when you need memo-aware copying to
#    handle circular references correctly.
#
# Q: What is the `memo` dict in __deepcopy__?
# A: It maps id(original) → copied_object, preventing infinite recursion on
#    circular references and ensuring each object is only copied once.


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 03 — Call by Object Reference
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# ARCHITECTURE:
#   Python is neither "call by value" nor "call by reference".
#   It is "call by object reference" (also called "call by sharing").
#   When you pass an argument, the function receives a reference to the *same*
#   object. Whether the caller sees changes depends on what the function does:
#     MUTATION  (list.append, dict[key]=val) → caller sees the change
#     REBINDING (name = new_object)          → caller does NOT see the change
#   Immutable objects (int, str, tuple) cannot be mutated, so functions can
#   never change them from the caller's perspective.

print("\n" + "=" * 60)
print("SECTION 03 — Call by Object Reference")
print("=" * 60)

def mutate(lst):
    lst.append(99)          # mutates the shared object

def rebind(lst):
    lst = [100, 200]        # rebinds LOCAL name, caller unaffected

my_list = [1, 2, 3]
mutate(my_list)
print(f"After mutate():  {my_list}")   # [1, 2, 3, 99]

rebind(my_list)
print(f"After rebind():  {my_list}")   # [1, 2, 3, 99]  — unchanged

# --- integer immutability ---
def try_change_int(n):
    n = n + 1   # creates NEW int object, rebinds local n
    return n

val = 10
new_val = try_change_int(val)
print(f"val={val}, new_val={new_val}")   # val still 10

# --- augmented assignment on list vs int ---
a = [1, 2, 3]
b = a
a += [4]           # list.__iadd__ mutates in-place
print(f"a={a}, b={b}, same? {a is b}")  # both show [1,2,3,4], True

x = 5
y = x
x += 1             # int is immutable → new object
print(f"x={x}, y={y}, same? {x is y}")  # x=6, y=5, False

# Interview Q&A:
# Q: Is Python pass by value or pass by reference?
# A: Neither. It's pass by object reference (call by sharing). The function gets
#    a copy of the reference to the same object. Mutation is visible; rebinding is not.
#
# Q: Why doesn't `def f(x): x = 10` change the caller's variable?
# A: The local name `x` is rebound to 10 inside the function. The caller's variable
#    still points to the original object. Only in-place mutations are visible.
#
# Q: What is the difference between `a += [4]` on a list vs an integer?
# A: For list, `+=` calls __iadd__ which mutates in-place → same id().
#    For int, `+=` creates a new int object → different id().
#
# Q: What is a gotcha with default mutable arguments?
# A: def f(lst=[]): lst.append(1)  — the default list is created ONCE at function
#    definition time and shared across all calls. Use `def f(lst=None): if lst is None: lst = []`.


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 04 — Generator .send() / .throw() / .close()
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# ARCHITECTURE:
#   A generator function (containing `yield`) returns a generator object.
#   The generator is a suspended coroutine — it pauses at each `yield` and
#   resumes when next() is called.
#   .send(value) — resumes and injects `value` as the result of the yield expr
#   .throw(exc)  — resumes and raises the exception at the yield point
#   .close()     — injects GeneratorExit at the yield point (cleanup)
#   The first .send() must send None (or use next()) because there is no
#   yield expression waiting yet.

print("\n" + "=" * 60)
print("SECTION 04 — Generator .send() / .throw() / .close()")
print("=" * 60)

def accumulator():
    """Coroutine-style generator: receives values via .send(), yields running total."""
    total = 0
    while True:
        try:
            value = yield total       # suspends; send() injects into `value`
            if value is None:
                break
            total += value
        except ValueError as e:
            print(f"  [generator] caught ValueError: {e}, resetting total")
            total = 0

gen = accumulator()
next(gen)               # prime — advance to first yield (must send None first)
print(f"send(10) → {gen.send(10)}")   # 10
print(f"send(20) → {gen.send(20)}")   # 30
print(f"send(5)  → {gen.send(5)}")    # 35
gen.throw(ValueError, "bad input")    # inject exception → resets total
print(f"send(7)  → {gen.send(7)}")    # 7  (fresh start)
gen.close()                           # sends GeneratorExit

# --- generator pipeline ---
def infinite_counter(start=0):
    n = start
    while True:
        yield n
        n += 1

def take(n, iterable):
    for i, item in enumerate(iterable):
        if i >= n:
            break
        yield item

nums = list(take(5, infinite_counter(10)))
print(f"Infinite counter (first 5 from 10): {nums}")   # [10,11,12,13,14]

# --- send pattern for running average ---
def running_average():
    count = 0
    total = 0.0
    avg   = None
    while True:
        val = yield avg
        if val is None:
            return
        count += 1
        total += val
        avg    = total / count

ra = running_average()
next(ra)
for v in [10, 20, 30, 40]:
    print(f"  add {v:2d} → avg = {ra.send(v):.2f}")

# Interview Q&A:
# Q: What does .send() do in a generator?
# A: It resumes the generator AND injects the sent value as the result of the
#    current `yield` expression. The generator then runs until the next yield.
#
# Q: Why must the first call be next(gen) or gen.send(None)?
# A: The generator hasn't started yet — there is no yield expression suspended
#    waiting for a value. Sending a non-None value before priming raises TypeError.
#
# Q: What is the difference between a generator and a coroutine?
# A: A generator primarily *produces* values (yield value).
#    A coroutine primarily *consumes* values (value = yield).
#    async def functions are true coroutines; generator-based coroutines were
#    the old style (PEP 342).
#
# Q: What does .throw() do?
# A: Injects an exception at the point where the generator is suspended (yield).
#    The generator can catch it and continue, or let it propagate.
#
# Q: What does .close() do?
# A: Throws GeneratorExit at the yield point. If the generator has a
#    try/finally, the finally block runs (useful for cleanup/resource release).


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 05 — Iterator Protocol
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# ARCHITECTURE:
#   Iterator Protocol = two dunder methods:
#     __iter__(self)  → returns the iterator object (often self)
#     __next__(self)  → returns the next value, raises StopIteration when done
#   An *iterable* implements __iter__ and returns an iterator.
#   An *iterator* implements both __iter__ (returns self) AND __next__.
#   for loops, list(), map(), zip() all call iter(obj) then repeatedly next().
#   Generators are iterators — they implement both dunder methods automatically.

print("\n" + "=" * 60)
print("SECTION 05 — Iterator Protocol")
print("=" * 60)

class FibonacciIterator:
    """Infinite Fibonacci sequence as an iterator."""

    def __init__(self, limit: Optional[int] = None):
        self.limit = limit
        self.a, self.b = 0, 1
        self.count = 0

    def __iter__(self):
        return self          # iterator returns itself

    def __next__(self):
        if self.limit is not None and self.count >= self.limit:
            raise StopIteration
        value = self.a
        self.a, self.b = self.b, self.a + self.b
        self.count += 1
        return value

# Use in for loop
fib10 = list(FibonacciIterator(limit=10))
print(f"First 10 Fibonacci: {fib10}")

# Manual iteration
fib = FibonacciIterator(limit=5)
print("Manual next() calls:", end=" ")
while True:
    try:
        print(next(fib), end=" ")
    except StopIteration:
        break
print()

# --- iterable vs iterator distinction ---
class CountUp:
    """Iterable (not iterator) — creates a new iterator each time."""

    def __init__(self, stop):
        self.stop = stop

    def __iter__(self):
        # Returns a NEW iterator each time (can be iterated multiple times)
        return iter(range(self.stop))

counter = CountUp(5)
print(f"First  loop: {list(counter)}")   # [0,1,2,3,4]
print(f"Second loop: {list(counter)}")   # [0,1,2,3,4]  — reusable!

# A raw iterator is exhausted after one pass
raw_iter = iter(range(3))
print(f"raw_iter first:  {list(raw_iter)}")   # [0,1,2]
print(f"raw_iter second: {list(raw_iter)}")   # []  — exhausted

# --- iter() with sentinel ---
import random
random.seed(42)
roll_until_six = list(iter(lambda: random.randint(1, 6), 6))
print(f"Dice rolls until 6: {roll_until_six}")

# Interview Q&A:
# Q: What is the difference between an iterable and an iterator?
# A: An iterable has __iter__ that returns an iterator.
#    An iterator has __iter__ (returns self) AND __next__.
#    Lists are iterables; iter(list) gives an iterator.
#
# Q: Why does `iter(obj)` sometimes return self?
# A: When obj is already an iterator (e.g. a generator, file object), __iter__
#    returns self so it can be used directly in for loops and other protocols.
#
# Q: What is the two-argument form of iter()?
# A: iter(callable, sentinel) calls callable() repeatedly until it returns the
#    sentinel value, yielding each result as an iterator.
#
# Q: Why can you loop over a list multiple times but not over a generator?
# A: A list is an iterable — each call to iter() creates a fresh list_iterator.
#    A generator IS an iterator — once exhausted, StopIteration is always raised.
#
# Q: What happens if __next__ forgets to raise StopIteration?
# A: The for loop runs forever (infinite iterator). Use a limit or break condition.


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 06 — ThreadPoolExecutor + ProcessPoolExecutor + concurrent.futures
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# ARCHITECTURE:
#   concurrent.futures provides a high-level interface for async execution.
#   Executor.submit(fn, *args) → Future object (non-blocking)
#   Executor.map(fn, iterable) → iterator of results (lazy, ordered)
#   as_completed(futures)      → yields futures in completion order
#   Future.result()  — blocks until done, raises exception if fn raised
#   Future.done()    — non-blocking check
#   Future.add_done_callback(fn) — called when future completes
#   ThreadPoolExecutor  — uses threads (good for I/O-bound work)
#   ProcessPoolExecutor — uses processes (good for CPU-bound, bypasses GIL)

print("\n" + "=" * 60)
print("SECTION 06 — concurrent.futures")
print("=" * 60)

def simulate_io_task(task_id: int, delay: float) -> str:
    """Simulate an I/O-bound task (e.g. HTTP request)."""
    time.sleep(delay)
    return f"Task {task_id} done in {delay:.2f}s"

def cpu_bound_task(n: int) -> int:
    """CPU-bound: sum of squares."""
    return sum(i * i for i in range(n))

# --- ThreadPoolExecutor with submit() and Future ---
print("\n[ThreadPoolExecutor] submit() + Future:")
tasks = [(1, 0.1), (2, 0.05), (3, 0.08)]

with ThreadPoolExecutor(max_workers=3) as executor:
    futures: List[Future] = [
        executor.submit(simulate_io_task, tid, delay)
        for tid, delay in tasks
    ]
    # as_completed — results arrive in completion order, not submission order
    for future in as_completed(futures):
        try:
            result = future.result()
            print(f"  {result}")
        except Exception as e:
            print(f"  ERROR: {e}")

# --- Executor.map() — ordered results ---
print("\n[ThreadPoolExecutor] map() — ordered:")
with ThreadPoolExecutor(max_workers=4) as executor:
    results = list(executor.map(cpu_bound_task, [100, 200, 300, 400]))
print(f"  sum-of-squares results: {results}")

# --- Future callbacks ---
print("\n[Future] add_done_callback:")
def on_done(future: Future):
    print(f"  Callback fired: {future.result()}")

with ThreadPoolExecutor(max_workers=1) as executor:
    f = executor.submit(simulate_io_task, 99, 0.01)
    f.add_done_callback(on_done)

# --- ProcessPoolExecutor (CPU-bound) ---
# IMPORTANT: On macOS/Windows, Python uses 'spawn' (not 'fork') for new processes.
# ProcessPoolExecutor MUST be called from inside `if __name__ == '__main__'` block
# when running as a top-level script. When running inline (e.g. imported module),
# we use a fallback to ThreadPoolExecutor for demonstration.
def heavy_computation(n: int) -> int:
    return sum(i ** 2 for i in range(n))

print("\n[ProcessPoolExecutor] CPU-bound tasks:")
print("  NOTE: ProcessPoolExecutor requires if __name__=='__main__' on macOS/Windows.")
print("  Demonstrating with ThreadPoolExecutor here; in production wrap in __main__.")
with ThreadPoolExecutor(max_workers=2) as executor:
    results = list(executor.map(heavy_computation, [50_000, 100_000]))
print(f"  Computation results: {results}")
print("  # Production usage:")
print("  # if __name__ == '__main__':")
print("  #     with ProcessPoolExecutor(max_workers=2) as ex:")
print("  #         results = list(ex.map(heavy_computation, [50_000, 100_000]))")

# Interview Q&A:
# Q: What is the difference between submit() and map()?
# A: submit() submits a single callable and returns a Future immediately.
#    map() submits many calls and returns an ordered iterator of results.
#    as_completed() works with submit() to process results as they finish.
#
# Q: What is a Future object?
# A: A handle to an asynchronous computation. It has result(), done(),
#    cancelled(), add_done_callback(). result() blocks until the value is ready.
#
# Q: When should you use ThreadPoolExecutor vs ProcessPoolExecutor?
# A: ThreadPoolExecutor for I/O-bound (network, disk) because threads share memory.
#    ProcessPoolExecutor for CPU-bound because it bypasses the GIL using processes.
#
# Q: What happens when an exception occurs inside a submitted task?
# A: The exception is stored in the Future. It is re-raised when you call
#    future.result(). If you never call result(), the exception is silently dropped.
#
# Q: What does the `with` statement do for an Executor?
# A: It calls shutdown(wait=True), which blocks until all submitted futures complete.


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 07 — Threading vs Multiprocessing vs Asyncio Decision Matrix
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# ARCHITECTURE:
#   THE GIL (Global Interpreter Lock):
#     CPython has a mutex that allows only ONE thread to execute Python bytecode
#     at a time. This prevents data corruption but limits CPU parallelism.
#     C extensions (NumPy, I/O syscalls) can release the GIL.
#
#   DECISION MATRIX:
#   ┌─────────────────┬──────────────────────────────┬──────────────────────────┐
#   │ Workload        │ Best Tool                    │ Why                      │
#   ├─────────────────┼──────────────────────────────┼──────────────────────────┤
#   │ I/O-bound       │ asyncio  (best)              │ single thread, no GIL    │
#   │ (many conns)    │ ThreadPoolExecutor (ok)       │ threads block on I/O     │
#   ├─────────────────┼──────────────────────────────┼──────────────────────────┤
#   │ CPU-bound       │ ProcessPoolExecutor          │ bypasses GIL             │
#   │ (pure Python)   │ multiprocessing.Pool         │ true parallelism         │
#   ├─────────────────┼──────────────────────────────┼──────────────────────────┤
#   │ CPU-bound       │ threading or numpy/C ext     │ GIL released by C code   │
#   │ (C extensions)  │                              │                          │
#   ├─────────────────┼──────────────────────────────┼──────────────────────────┤
#   │ Mixed I/O + CPU │ asyncio + run_in_executor    │ offload CPU to thread/   │
#   │                 │                              │ process pool             │
#   └─────────────────┴──────────────────────────────┴──────────────────────────┘

print("\n" + "=" * 60)
print("SECTION 07 — Threading vs Multiprocessing vs Asyncio")
print("=" * 60)

# --- threading: I/O-bound example ---
def fetch_url(url: str) -> str:
    time.sleep(0.05)   # simulate network I/O
    return f"Response from {url}"

print("\n[threading] I/O-bound concurrent requests:")
urls = ["http://api1.example.com", "http://api2.example.com", "http://api3.example.com"]
threads = []
results_store = {}

def worker(url):
    results_store[url] = fetch_url(url)

start = time.perf_counter()
for url in urls:
    t = threading.Thread(target=worker, args=(url,))
    threads.append(t)
    t.start()
for t in threads:
    t.join()
elapsed = time.perf_counter() - start
print(f"  {len(urls)} requests in {elapsed:.3f}s (sequential would be {0.05*len(urls):.2f}s)")
print(f"  Results: {list(results_store.values())}")

# --- asyncio: I/O-bound with coroutines ---
print("\n[asyncio] Async I/O-bound tasks:")

async def async_fetch(url: str) -> str:
    await asyncio.sleep(0.05)   # non-blocking sleep
    return f"Async response from {url}"

async def main_async():
    tasks = [async_fetch(url) for url in urls]
    start = time.perf_counter()
    results = await asyncio.gather(*tasks)
    elapsed = time.perf_counter() - start
    print(f"  {len(results)} async requests in {elapsed:.3f}s")
    for r in results:
        print(f"  {r}")

asyncio.run(main_async())

# --- multiprocessing: CPU-bound ---
print("\n[multiprocessing] CPU-bound parallel work:")

def count_primes(limit: int) -> int:
    """Count primes up to limit (CPU-intensive)."""
    count = 0
    for n in range(2, limit):
        if all(n % i != 0 for i in range(2, int(n**0.5) + 1)):
            count += 1
    return count

# ProcessPoolExecutor must be inside if __name__ == '__main__' on macOS/Windows (spawn mode).
# For inline script execution, we show ThreadPoolExecutor; the logic is identical.
start = time.perf_counter()
with ThreadPoolExecutor(max_workers=2) as executor:
    prime_counts = list(executor.map(count_primes, [500, 800]))
elapsed = time.perf_counter() - start
print(f"  Prime counts {prime_counts} in {elapsed:.3f}s")
print("  # In a real script entry point use ProcessPoolExecutor for true parallelism:"  )
print("  # if __name__ == '__main__':"                                                   )
print("  #     with ProcessPoolExecutor(max_workers=2) as ex:"                          )
print("  #         prime_counts = list(ex.map(count_primes, [500, 800]))"               )

# Interview Q&A:
# Q: What is the GIL and why does it exist?
# A: The Global Interpreter Lock is a mutex in CPython preventing concurrent
#    thread execution of Python bytecode. It exists because CPython's memory
#    management (reference counting) is not thread-safe without it.
#
# Q: Does the GIL make Python threading useless?
# A: No. For I/O-bound tasks (network, disk), threads spend most time waiting
#    in system calls which release the GIL. Threads run concurrently for I/O.
#
# Q: When would you choose asyncio over threading for I/O-bound work?
# A: asyncio is better for very high concurrency (thousands of connections)
#    because coroutines have negligible overhead vs threads (1MB+ stack each).
#    Threading is fine for moderate concurrency or when using blocking libraries.
#
# Q: When is multiprocessing NOT the right answer for CPU-bound work?
# A: When the data transfer cost between processes exceeds the computation
#    savings (pickling overhead). Also not ideal for tasks requiring shared state.
#
# Q: What is asyncio.gather() vs asyncio.wait()?
# A: gather() runs coroutines concurrently and returns ordered results.
#    wait() gives more control — you get done/pending sets and can set timeout.


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 08 — dataclass vs NamedTuple vs TypedDict
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# ARCHITECTURE:
#   ┌─────────────────┬──────────────────┬─────────────────┬─────────────────┐
#   │ Feature         │ dataclass        │ NamedTuple      │ TypedDict       │
#   ├─────────────────┼──────────────────┼─────────────────┼─────────────────┤
#   │ Type hints      │ Yes              │ Yes             │ Yes             │
#   │ Mutable         │ Yes (default)    │ No (tuple)      │ Yes (dict)      │
#   │ Inheritance     │ Yes              │ Yes             │ Yes             │
#   │ Default values  │ field()          │ =default        │ total=False     │
#   │ Methods         │ Yes              │ Yes             │ No              │
#   │ Memory          │ __dict__ or slot │ tuple (compact) │ dict            │
#   │ Indexing        │ No               │ Yes (t[0])      │ No              │
#   │ JSON-like       │ asdict()         │ _asdict()       │ already dict    │
#   │ Use case        │ Mutable records  │ Immutable rows  │ API payloads    │
#   └─────────────────┴──────────────────┴─────────────────┴─────────────────┘

print("\n" + "=" * 60)
print("SECTION 08 — dataclass vs NamedTuple vs TypedDict")
print("=" * 60)

# --- dataclass ---
@dataclass
class Employee:
    name: str
    department: str
    salary: float
    skills: List[str] = field(default_factory=list)   # mutable default

    def give_raise(self, pct: float) -> None:
        self.salary *= (1 + pct / 100)

    def __post_init__(self):
        if self.salary < 0:
            raise ValueError("Salary cannot be negative")

emp = Employee("Alice", "Engineering", 80_000.0, ["Python", "SQL"])
emp.give_raise(10)
print(f"dataclass Employee: {emp}")
print(f"  asdict: {dataclasses.asdict(emp)}")

# frozen dataclass (immutable)
@dataclass(frozen=True)
class Point:
    x: float
    y: float

    def distance(self) -> float:
        return (self.x ** 2 + self.y ** 2) ** 0.5

p = Point(3.0, 4.0)
print(f"Frozen Point: {p}, distance={p.distance()}")
# p.x = 10  # would raise FrozenInstanceError

# --- NamedTuple ---
class Coordinate(NamedTuple):
    lat: float
    lon: float
    label: str = "unknown"

coord = Coordinate(28.6139, 77.2090, "New Delhi")
print(f"NamedTuple Coordinate: {coord}")
print(f"  lat={coord.lat}, by index: coord[0]={coord[0]}")
print(f"  _asdict: {coord._asdict()}")
print(f"  Is tuple: {isinstance(coord, tuple)}")   # True

# --- TypedDict ---
class APIResponse(TypedDict):
    status: int
    message: str
    data: Optional[dict]

response: APIResponse = {"status": 200, "message": "OK", "data": {"id": 1}}
print(f"TypedDict APIResponse: {response}")
print(f"  Is plain dict: {isinstance(response, dict)}")   # True — TypedDict is just hints

# --- comparison ---
print("\nMemory comparison (approximate):")
import sys as _sys
nt = Coordinate(1.0, 2.0)
dc = Point(1.0, 2.0)
print(f"  NamedTuple size: {_sys.getsizeof(nt)} bytes")
print(f"  dataclass size:  {_sys.getsizeof(dc)} bytes")

# Interview Q&A:
# Q: When would you use NamedTuple over dataclass?
# A: When you need tuple compatibility (indexing, unpacking, CSV rows),
#    immutability, and slightly lower memory footprint. Also good for
#    representing fixed-structure records like DB rows.
#
# Q: What is field(default_factory=list) in dataclass?
# A: It defers list creation to each instance's __init__, preventing the
#    shared-mutable-default bug. Never use `skills: list = []` in a dataclass.
#
# Q: What does TypedDict actually enforce at runtime?
# A: Nothing — TypedDict is purely a type-checking hint for mypy/pyright.
#    At runtime, instances are plain dicts.
#
# Q: What is a frozen dataclass?
# A: @dataclass(frozen=True) makes instances immutable (sets raise FrozenInstanceError)
#    and makes them hashable (can be used as dict keys or in sets).
#
# Q: How do you add validation logic to a dataclass?
# A: Override __post_init__, which is called after the generated __init__.


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 09 — Walrus Operator := + match Statement (Python 3.10+)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# ARCHITECTURE:
#   Walrus operator (:=) — "assignment expression" (PEP 572)
#     Assigns a value AND returns it in a single expression.
#     Useful in while loops and list comprehensions to avoid double evaluation.
#
#   match statement — "structural pattern matching" (PEP 634, Python 3.10+)
#     Like switch/case but far more powerful:
#       - Matches on structure, not just equality
#       - Captures subcomponents into variables
#       - Supports guards (if conditions)
#       - Works with classes via __match_args__
#       - OR patterns (|), wildcard (_), mapping patterns, sequence patterns

print("\n" + "=" * 60)
print("SECTION 09 — Walrus Operator := + match Statement")
print("=" * 60)

# --- walrus in while loop ---
import re

text = "Order 1234 for customer 5678 placed on 2026-05-19"
pattern = re.compile(r'\d+')
pos = 0
numbers_found = []

while m := pattern.search(text, pos):
    numbers_found.append(m.group())
    pos = m.end()

print(f"Numbers found via walrus: {numbers_found}")

# --- walrus in list comprehension ---
raw_data = ["", "hello", "", "world", " ", "python"]
cleaned = [stripped for item in raw_data if (stripped := item.strip())]
print(f"Non-empty stripped: {cleaned}")

# --- walrus with input-like loop ---
data_feed = iter([10, 25, 7, 42, 3, 0])   # simulate input stream

chunks = []
while (chunk := next(data_feed, None)) is not None:
    if chunk > 0:
        chunks.append(chunk)
print(f"Positive chunks from feed: {chunks}")

# --- match statement: command parser ---
def parse_command(command: str) -> str:
    parts = command.strip().split()

    match parts:
        case ["quit"] | ["exit"]:
            return "Exiting application."

        case ["go", direction] if direction in ("north", "south", "east", "west"):
            return f"Moving {direction}."

        case ["go", direction]:
            return f"Unknown direction: {direction}"

        case ["take", item]:
            return f"Picked up: {item}"

        case ["drop", item, *rest] if rest:
            return f"Dropping {item} at {' '.join(rest)}"

        case ["drop", item]:
            return f"Dropping {item} here."

        case ["inventory" | "inv"]:
            return "Showing inventory."

        case [unknown, *_]:
            return f"Unknown command: {unknown!r}"

        case []:
            return "Empty command."

commands = [
    "go north", "go up", "take sword", "drop shield dungeon",
    "quit", "inventory", "inv", "fly home", ""
]
for cmd in commands:
    print(f"  {cmd!r:25s} → {parse_command(cmd)}")

# --- match on data structures ---
def describe_point(point):
    match point:
        case (0, 0):
            return "Origin"
        case (x, 0):
            return f"On x-axis at {x}"
        case (0, y):
            return f"On y-axis at {y}"
        case (x, y) if x == y:
            return f"On diagonal at ({x}, {y})"
        case (x, y):
            return f"Point at ({x}, {y})"

for pt in [(0,0), (5,0), (0,3), (4,4), (2,7)]:
    print(f"  {str(pt):10s} → {describe_point(pt)}")

# Interview Q&A:
# Q: What is the walrus operator and when was it introduced?
# A: := (assignment expression, PEP 572) was introduced in Python 3.8.
#    It assigns and returns a value in one expression, reducing code duplication
#    in conditions and comprehensions.
#
# Q: What is the danger of := in comprehensions?
# A: Variables assigned with := in a comprehension leak into the enclosing scope
#    (unlike loop variables which are scoped to the comprehension). This can
#    cause surprising name collisions.
#
# Q: How is match different from if/elif chains?
# A: match performs structural pattern matching — it can destructure sequences,
#    mappings, and class instances, binding subcomponents to names.
#    if/elif can only test boolean expressions.
#
# Q: What is a guard in a match case?
# A: An `if` condition after the pattern: `case [x, y] if x > 0`.
#    The case only matches if the pattern matches AND the guard is True.
#
# Q: What does `case _` mean?
# A: Wildcard — matches anything and binds nothing. Used as the default case.


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 10 — Memory Leak Detection: gc, weakref, tracemalloc
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# ARCHITECTURE:
#   CPython primary memory management = reference counting.
#   When refcount → 0, memory is freed immediately.
#   PROBLEM: Circular references keep refcount > 0 forever.
#   SOLUTION: gc module — cyclic garbage collector finds & breaks cycles.
#     gc.collect()         — manual collection
#     gc.get_objects()     — all tracked objects
#     gc.disable()/enable()
#   weakref module: create references that don't increment refcount.
#   When the referent is garbage collected, the weak reference returns None.
#   tracemalloc: built-in memory tracer that records allocation call stacks.
#     tracemalloc.start()
#     tracemalloc.take_snapshot()
#     snapshot.compare_to() — diff two snapshots to find leaks

print("\n" + "=" * 60)
print("SECTION 10 — Memory Leak Detection")
print("=" * 60)

# --- circular reference demo ---
class Node:
    def __init__(self, name: str):
        self.name = name
        self.next: Optional['Node'] = None
        self.prev: Optional['Node'] = None

    def __del__(self):
        pass   # called when object is truly garbage collected

a = Node("A")
b = Node("B")
a.next = b
b.prev = a   # circular reference: A → B → A

del a, b     # refcount doesn't reach 0 due to cycle
collected = gc.collect()
print(f"gc.collect() freed {collected} objects from circular reference")

# --- gc generation info ---
print(f"gc thresholds: {gc.get_threshold()}")
print(f"gc counts:     {gc.get_count()}")

# --- weakref demo ---
class ExpensiveResource:
    def __init__(self, name: str):
        self.name = name

    def __repr__(self):
        return f"ExpensiveResource({self.name!r})"

resource = ExpensiveResource("DB Connection")
weak = weakref.ref(resource)

print(f"Weak ref alive: {weak()}")   # ExpensiveResource('DB Connection')

del resource   # drop the strong reference
gc.collect()
print(f"Weak ref after del: {weak()}")   # None — object was collected

# --- weakref.WeakValueDictionary ---
cache: weakref.WeakValueDictionary = weakref.WeakValueDictionary()
obj1 = ExpensiveResource("Cache Item 1")
cache["item1"] = obj1
print(f"Cache before del: {dict(cache)}")
del obj1
gc.collect()
print(f"Cache after del:  {dict(cache)}")   # empty — auto-evicted

# --- tracemalloc: snapshot comparison to find allocations ---
print("\n[tracemalloc] Snapshot comparison:")

tracemalloc.start()
snapshot1 = tracemalloc.take_snapshot()

# Simulate a "leak" — allocate a large list
leaked_data = [{"key": i, "value": "x" * 100} for i in range(1000)]

snapshot2 = tracemalloc.take_snapshot()
tracemalloc.stop()

top_stats = snapshot2.compare_to(snapshot1, 'lineno')
print("Top 3 memory increases:")
for stat in top_stats[:3]:
    print(f"  {stat}")

del leaked_data

# --- tracemalloc top allocations in current snapshot ---
tracemalloc.start()
big_list = list(range(100_000))
snap = tracemalloc.take_snapshot()
tracemalloc.stop()

top = snap.statistics('lineno')[:3]
print("\nTop 3 allocations by size:")
for s in top:
    print(f"  {s}")

del big_list

# Interview Q&A:
# Q: What is the difference between reference counting and cyclic GC in CPython?
# A: Reference counting frees objects immediately when refcount drops to 0.
#    Cyclic GC (gc module) handles cycles that keep refcounts > 0 permanently.
#    Both work together in CPython.
#
# Q: What is a weak reference and when would you use one?
# A: A weak reference doesn't prevent garbage collection. Use them for caches,
#    observer patterns, and circular data structures where you don't want to
#    keep objects alive artificially.
#
# Q: How does tracemalloc work?
# A: It hooks into Python's memory allocator and records a stack trace for every
#    allocation. Snapshots capture the state at a point in time. Comparing two
#    snapshots shows net allocations between them — the "leak delta".
#
# Q: What are gc generations and why does Python use them?
# A: The gc uses 3 generations (0, 1, 2). New objects start in gen 0.
#    Survivors get promoted. Older generations are collected less frequently
#    (generational hypothesis: young objects die young).
#
# Q: How can you diagnose a memory leak in a long-running Python service?
# A: Start tracemalloc, take periodic snapshots, compare them. Look for growing
#    allocations. Also check gc.get_objects() length over time, use memory_profiler
#    for line-by-line analysis, and py-spy for live sampling.


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 11 — Performance Profiling: cProfile, pstats, timeit, tracemalloc
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# ARCHITECTURE:
#   Profiling tools in Python:
#   ┌─────────────────┬──────────────────────────────────────────────────┐
#   │ Tool            │ Purpose                                          │
#   ├─────────────────┼──────────────────────────────────────────────────┤
#   │ timeit          │ Micro-benchmarks — measure small code snippets   │
#   │ cProfile        │ Deterministic profiler — call counts & CPU time  │
#   │ pstats          │ Sort/filter/display cProfile output              │
#   │ tracemalloc     │ Memory profiling — allocations & call stacks     │
#   │ line_profiler   │ Line-by-line timing (needs pip install, @profile)│
#   │ py-spy          │ Sampling profiler — zero overhead, production    │
#   └─────────────────┴──────────────────────────────────────────────────┘
#   Workflow: timeit → find slow section → cProfile → find hot function →
#             line_profiler → optimize → verify with timeit again

print("\n" + "=" * 60)
print("SECTION 11 — Performance Profiling")
print("=" * 60)

# --- timeit: compare two implementations ---
def sum_squares_loop(n: int) -> int:
    total = 0
    for i in range(n):
        total += i * i
    return total

def sum_squares_builtin(n: int) -> int:
    return sum(i * i for i in range(n))

def sum_squares_formula(n: int) -> int:
    # n*(n-1)*(2n-1)/6
    return n * (n - 1) * (2 * n - 1) // 6

N = 10_000
t_loop    = timeit.timeit(lambda: sum_squares_loop(N),    number=100)
t_builtin = timeit.timeit(lambda: sum_squares_builtin(N), number=100)
t_formula = timeit.timeit(lambda: sum_squares_formula(N), number=100)

print(f"\ntimeit (100 reps, n={N}):")
print(f"  Loop:    {t_loop*1000:.3f} ms")
print(f"  Builtin: {t_builtin*1000:.3f} ms")
print(f"  Formula: {t_formula*1000:.3f} ms")

# --- cProfile + pstats ---
def workload():
    """A function we want to profile."""
    result = []
    for i in range(500):
        primes = [n for n in range(2, 50) if all(n % d != 0 for d in range(2, n))]
        result.extend(primes)
    return result

print("\ncProfile output (top 5 by cumtime):")
profiler = cProfile.Profile()
profiler.enable()
workload()
profiler.disable()

stream = io.StringIO()
stats = pstats.Stats(profiler, stream=stream)
stats.sort_stats('cumulative')
stats.print_stats(5)
output = stream.getvalue()
# Print only the relevant lines
for line in output.split('\n')[:20]:
    if line.strip():
        print(f"  {line}")

# --- cProfile.run() writes to stdout; capture with redirect ---
print("\ncProfile.run() profile of sum_squares_loop:")
run_capture = io.StringIO()
import contextlib
with contextlib.redirect_stdout(run_capture):
    cProfile.run('sum_squares_loop(100000)')
lines = run_capture.getvalue().split('\n')
for line in lines[:8]:
    if line.strip():
        print(f"  {line}")

# --- tracemalloc: find top memory consumers ---
print("\ntracemalloc: top 3 memory consumers during workload:")

tracemalloc.start()
workload()
snapshot = tracemalloc.take_snapshot()
tracemalloc.stop()

top_mem = snapshot.statistics('lineno')[:3]
for stat in top_mem:
    print(f"  {stat}")

# --- timeit.repeat for statistical confidence ---
print("\ntimeit.repeat (5 reps x 50 iterations):")
times = timeit.repeat(lambda: sum_squares_builtin(5000), repeat=5, number=50)
print(f"  Times (ms): {[round(t*1000, 3) for t in times]}")
print(f"  Best:  {min(times)*1000:.3f} ms")
print(f"  Worst: {max(times)*1000:.3f} ms")

# NOTE: line_profiler (@profile decorator) requires:
#   pip install line_profiler
#   kernprof -l -v script.py
# Cannot be demonstrated inline without the package, but usage is:
#
#   @profile
#   def my_slow_function():
#       ...
#
# Then run: kernprof -l -v script.py
# Output shows time per line.

# Interview Q&A:
# Q: What is the difference between cProfile and timeit?
# A: timeit measures total elapsed time for a small snippet (micro-benchmark).
#    cProfile instruments every function call and reports call counts, cumulative
#    time, and per-call averages — useful for finding WHERE time is spent.
#
# Q: What does pstats add to cProfile?
# A: pstats provides sorting (by cumtime, tottime, calls), filtering, and
#    formatted printing of cProfile data. You can sort by 'cumulative' to find
#    the slowest call chains.
#
# Q: What is the difference between tottime and cumtime in cProfile?
# A: tottime = time spent IN the function (excluding called functions).
#    cumtime = total time including all sub-function calls.
#    tottime reveals hotspots; cumtime reveals expensive call chains.
#
# Q: When should you use timeit.repeat() instead of timeit.timeit()?
# A: timeit.repeat() runs multiple trials to get statistical confidence.
#    Always report the MINIMUM (best case), not the average — the minimum is
#    the least contaminated by OS noise, GC pauses, and other processes.
#
# Q: What is a sampling profiler (like py-spy) and when is it better than cProfile?
# A: A sampling profiler periodically inspects the call stack without instrumenting
#    every function call. Near-zero overhead → safe for production.
#    cProfile has ~10-30% overhead due to per-call hooks.
#
# Q: How do you profile memory line-by-line?
# A: Use `memory_profiler` (pip install memory_profiler) with @profile decorator
#    and run `python -m memory_profiler script.py`. Shows memory delta per line.


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SUMMARY TABLE — Quick Reference
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
print("\n" + "=" * 60)
print("SUMMARY — Quick Reference")
print("=" * 60)
print("""
CONCEPT            TOOL / SYNTAX                   NOTE
─────────────────  ──────────────────────────────  ────────────────────────────
int cache          a = 256; a is b → True           -5 to 256, CPython only
string interning   sys.intern("s")                  auto for identifiers
shallow copy       copy.copy() / list[:]            1 level deep
deep copy          copy.deepcopy()                  fully recursive
call-by-ref        mutation vs rebinding            no pass-by-value in Python
generator send     gen.send(value)                  prime first with next()
iterator protocol  __iter__ + __next__              StopIteration to stop
futures            executor.submit() → Future       .result() blocks
threading          ThreadPoolExecutor               I/O-bound, GIL-affected
multiprocessing    ProcessPoolExecutor              CPU-bound, GIL bypass
asyncio            async def / await                I/O, high concurrency
dataclass          @dataclass                       mutable records
NamedTuple         class X(NamedTuple)              immutable tuple rows
TypedDict          class X(TypedDict)               typed dict (runtime = dict)
walrus             if (n := len(a)) > 10            assign + test in one expr
match              match x: case [a, b]:            structural pattern matching
gc                 gc.collect()                     break cycles
weakref            weakref.ref(obj)                 no refcount increment
tracemalloc        take_snapshot().compare_to()     find memory growth
cProfile           cProfile.Profile()               function-level timing
timeit             timeit.timeit(lambda: ...)       micro-benchmark
""")

print("\nAll sections complete. Run individual sections by searching for '# SECTION'.")
