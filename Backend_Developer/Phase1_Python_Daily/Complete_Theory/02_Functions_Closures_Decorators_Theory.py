"""
╔══════════════════════════════════════════════════════════════════════════╗
║  PYTHON THEORY — What, Why, How + Real Life Examples                    ║
║  Topic: Functions, Closures, Decorators, Generators                     ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

import functools, time, sys
from typing import Callable, Generator, Any

# ══════════════════════════════════════════════════════════════════════════
# 1. FUNCTIONS — FIRST CLASS OBJECTS
# ══════════════════════════════════════════════════════════════════════════
"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT:
  Function = reusable block of code that takes inputs,
  performs operations, and optionally returns output.

  "First-class object" means functions can be:
  → Assigned to variables
  → Passed as arguments
  → Returned from other functions
  → Stored in data structures

WHY:
  ► DRY principle — Don't Repeat Yourself
  ► Code organization and reusability
  ► Abstraction — hide complexity

HOW (Internal Mechanism):
  ┌──────────────────────────────────────────────────────┐
  │  def greet(name: str) -> str:                        │
  │      return f"Hello, {name}"                         │
  │                                                       │
  │  Python creates a FUNCTION OBJECT:                   │
  │  ┌─────────────────────────────────────┐             │
  │  │  __name__: "greet"                  │             │
  │  │  __code__: bytecode                 │             │
  │  │  __doc__: docstring                 │             │
  │  │  __annotations__: {"name": str,     │             │
  │  │                    "return": str}   │             │
  │  │  __defaults__: None (no defaults)   │             │
  │  │  __globals__: module globals dict   │             │
  │  └─────────────────────────────────────┘             │
  │                                                       │
  │  greet is just a NAME pointing to this object!       │
  │  other_name = greet  # another reference, same obj   │
  └──────────────────────────────────────────────────────┘

PARAMETER TYPES:
  ┌─────────────────────────────────────────────────────────────┐
  │  def func(a, b, c=10, *args, kw_only, **kwargs):            │
  │           │  │  │     │     │          │                    │
  │           │  │  │     │     │          └─ keyword dict      │
  │           │  │  │     │     └─ keyword-only (after *)       │
  │           │  │  │     └─ extra positional → tuple           │
  │           │  │  └─ optional with default                    │
  │           │  └─ required positional                         │
  │           └─ required positional                            │
  │                                                             │
  │  CALL: func(1, 2, 3, 4, 5, kw_only="x", extra="y")         │
  │  a=1, b=2, c=3, args=(4,5), kw_only="x", kwargs={"extra":"y"}│
  └─────────────────────────────────────────────────────────────┘

REAL LIFE ANALOGY:
  Function = recipe in a cookbook.
  Parameters = ingredients list.
  Return = finished dish.
  First-class = you can share/copy/modify the recipe itself,
                not just cook from it.

PRODUCTION EXAMPLE:
  # AI tool function — same function used as agent tool
  def web_search(query: str, max_results: int = 10) -> list[dict]:
      ...

  # Pass as argument to agent framework
  agent = Agent(tools=[web_search, calculate, read_file])
  # Agent calls tools by reference!
"""

# Functions as first-class objects
def add(a: int, b: int) -> int:
    return a + b

# Assign to variable
my_add = add
print(my_add(3, 4))   # 7

# Store in list
operations = [add, lambda a,b: a-b, lambda a,b: a*b]
for op in operations:
    print(op(10, 3), end=" ")   # 13 7 30
print()

# Pass as argument (higher-order function)
def apply(func: Callable[[int,int], int], a: int, b: int) -> int:
    return func(a, b)

print(apply(add, 5, 3))   # 8

# Return from function
def make_greeter(greeting: str) -> Callable[[str], str]:
    def greet(name: str) -> str:
        return f"{greeting}, {name}!"
    return greet   # returning function!

hello = make_greeter("Hello")
hi    = make_greeter("Hi")
print(hello("Alice"), hi("Bob"))


# ══════════════════════════════════════════════════════════════════════════
# 2. *ARGS AND **KWARGS — VARIADIC PARAMETERS
# ══════════════════════════════════════════════════════════════════════════
"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT:
  *args  = accepts any number of POSITIONAL arguments → packs into tuple
  **kwargs = accepts any number of KEYWORD arguments → packs into dict

WHY:
  ► Flexible APIs — don't know how many args caller will pass
  ► Forwarding arguments between functions
  ► Decorator pattern — wrap any function transparently

HOW:
  ┌─────────────────────────────────────────────────┐
  │  def func(*args, **kwargs):                     │
  │      print(args)    # tuple                     │
  │      print(kwargs)  # dict                      │
  │                                                 │
  │  func(1, 2, 3, name="Alice", age=30)            │
  │  args   = (1, 2, 3)                             │
  │  kwargs = {"name": "Alice", "age": 30}          │
  │                                                 │
  │  UNPACKING (calling with * and **):             │
  │  nums = [1, 2, 3]                               │
  │  func(*nums)    # same as func(1, 2, 3)         │
  │  d = {"a": 1, "b": 2}                           │
  │  func(**d)      # same as func(a=1, b=2)        │
  └─────────────────────────────────────────────────┘

REAL LIFE ANALOGY:
  *args  = "Take any number of items" — like ordering pizza toppings.
  **kwargs = "Take any labeled package" — like a config form with named fields.

PRODUCTION EXAMPLE:
  # LLM API wrapper — forwards unknown parameters
  def call_llm(prompt: str, model: str = "gpt-4", **kwargs) -> str:
      # kwargs might contain: temperature, max_tokens, stream, etc.
      # Forward all to actual API without knowing them upfront
      return openai.chat(prompt=prompt, model=model, **kwargs)

  # Usage — caller decides extra params
  response = call_llm(
      "Hello",
      model="gpt-4",
      temperature=0.9,
      max_tokens=500,
      stream=True
  )
"""

def log_api_call(endpoint: str, *args, method: str = "GET", **kwargs) -> None:
    print(f"\nEndpoint: {endpoint}")
    print(f"Args:     {args}")
    print(f"Method:   {method}")
    print(f"Kwargs:   {kwargs}")

log_api_call("/api/users", "param1", "param2",
             method="POST", token="abc", page=2)


# ══════════════════════════════════════════════════════════════════════════
# 3. CLOSURES — FUNCTION + CAPTURED ENVIRONMENT
# ══════════════════════════════════════════════════════════════════════════
"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT:
  Closure = inner function that REMEMBERS variables from its
  enclosing scope EVEN AFTER the outer function has returned.

  The inner function "closes over" the outer function's variables.

WHY:
  ► Create function factories (functions that make functions)
  ► Maintain state without classes
  ► Implement callbacks with context
  ► Foundation of Python decorators

HOW (Internal Mechanism):
  ┌───────────────────────────────────────────────────────┐
  │  def outer(multiplier):                               │
  │      def inner(x):                                    │
  │          return x * multiplier  ← captures 'multiplier'│
  │      return inner                                     │
  │                                                       │
  │  double = outer(2)                                    │
  │                                                       │
  │  Python creates CELL OBJECT:                          │
  │  ┌──────────────────────────────────────────┐        │
  │  │  double function object:                 │        │
  │  │    __code__: bytecode                    │        │
  │  │    __closure__: (cell: value=2,)         │        │
  │  │                  ↑                       │        │
  │  │                  multiplier captured here│        │
  │  └──────────────────────────────────────────┘        │
  │                                                       │
  │  outer() has returned, but 'multiplier=2' LIVES ON   │
  │  inside double.__closure__                            │
  └───────────────────────────────────────────────────────┘

REAL LIFE ANALOGY:
  Closure = chef who learned a secret recipe from a master.
  Master (outer function) is gone, but chef (inner function)
  still REMEMBERS the recipe (closed-over variables).

PRODUCTION EXAMPLE:
  # Pre-configured LLM caller
  def make_llm_caller(model: str, temperature: float):
      def call(prompt: str) -> str:
          return f"[{model}|t={temperature}] {prompt}"
      return call

  gpt4_creative = make_llm_caller("gpt-4", temperature=0.9)
  gpt4_precise  = make_llm_caller("gpt-4", temperature=0.1)
  # Both remember their own model/temperature!

  ─ CLASSIC GOTCHA ─
  funcs = []
  for i in range(5):
      funcs.append(lambda x: x + i)  # WRONG — all capture same 'i'
  # When called later, i=4 for all!

  # FIX: capture value with default arg
  funcs = [lambda x, n=i: x + n for i in range(5)]
"""

# Closure demonstration
def make_counter(start: int = 0, step: int = 1):
    """Closure with mutable state via list."""
    count = [start]   # use list to allow mutation in closure

    def increment() -> int:
        count[0] += step
        return count[0]

    def reset() -> None:
        count[0] = start

    def get() -> int:
        return count[0]

    return increment, reset, get


inc, reset, get = make_counter(start=0, step=5)
print(f"\nClosure counter:")
print(inc())    # 5
print(inc())    # 10
print(inc())    # 15
print(get())    # 15
reset()
print(get())    # 0

# View closure variables
print(f"Closure cells: {inc.__closure__}")
print(f"Captured value: {inc.__closure__[0].cell_contents}")


# ══════════════════════════════════════════════════════════════════════════
# 4. DECORATORS — MODIFY FUNCTION BEHAVIOR WITHOUT CHANGING IT
# ══════════════════════════════════════════════════════════════════════════
"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT:
  Decorator = function that takes a function as input,
  wraps it with additional behavior, returns new function.
  @decorator is syntax sugar for: func = decorator(func)

WHY:
  ► Add behavior (logging, timing, caching, auth) WITHOUT modifying function
  ► DRY principle — apply same behavior to many functions
  ► Separation of concerns — business logic vs cross-cutting concerns

HOW:
  ┌──────────────────────────────────────────────────────┐
  │  @timer                                              │
  │  def my_function():                                  │
  │      ...                                             │
  │                                                      │
  │  IS EXACTLY THE SAME AS:                            │
  │  def my_function():                                  │
  │      ...                                             │
  │  my_function = timer(my_function)                    │
  │                                                      │
  │  EXECUTION FLOW:                                     │
  │  ┌──────────────────────────────────────────┐        │
  │  │  @timer                                  │        │
  │  │  def greet(name):                        │        │
  │  │      return f"Hello {name}"              │        │
  │  │                                          │        │
  │  │  Call: greet("Alice")                   │        │
  │  │                                          │        │
  │  │  Actually calls: wrapper("Alice")        │        │
  │  │  wrapper → [start timer]                 │        │
  │  │         → calls original greet("Alice")  │        │
  │  │         → [stop timer, log]              │        │
  │  │         → returns original result        │        │
  │  └──────────────────────────────────────────┘        │
  │                                                      │
  │  @functools.wraps — CRITICAL!                        │
  │  Without it: greet.__name__ = "wrapper"  ← WRONG    │
  │  With it:    greet.__name__ = "greet"    ← CORRECT  │
  └──────────────────────────────────────────────────────┘

REAL LIFE ANALOGY:
  Decorator = security guard at a building.
  The building (function) does its job.
  Guard (decorator) checks ID before entry, logs exit.
  Building doesn't know about the guard.
  Guard doesn't change what the building does.

PRODUCTION EXAMPLES:
  @require_auth        → check JWT token before executing
  @cache(ttl=300)      → return cached result if available
  @retry(max=3)        → retry on failure
  @rate_limit(100)     → allow max 100 calls per minute
  @validate_input      → validate Pydantic model before calling
  @log_execution       → log all calls with timing
"""

# Pattern 1: Basic decorator with @functools.wraps
def timer(func: Callable) -> Callable:
    @functools.wraps(func)   # ALWAYS use this!
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = (time.perf_counter() - start) * 1000
        print(f"[TIMER] {func.__name__}: {elapsed:.2f}ms")
        return result
    return wrapper

@timer
def sum_range(n: int) -> int:
    return sum(range(n))

result = sum_range(1_000_000)
print(f"Result: {result}")
print(f"Name preserved: {sum_range.__name__}")   # sum_range (not wrapper!)


# Pattern 2: Decorator with arguments (factory)
def retry(max_attempts: int = 3, delay: float = 1.0, exceptions: tuple = (Exception,)):
    """Decorator factory — returns a decorator."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    print(f"  [RETRY] {func.__name__} attempt {attempt}/{max_attempts}: {e}")
                    if attempt < max_attempts:
                        time.sleep(delay * (2 ** (attempt - 1)))  # exponential backoff
            raise last_exc
        return wrapper
    return decorator

import random
@retry(max_attempts=3, delay=0.01, exceptions=(ConnectionError,))
def unstable_api_call(url: str) -> dict:
    """Simulates flaky API."""
    if random.random() < 0.6:
        raise ConnectionError(f"Timeout connecting to {url}")
    return {"status": 200, "data": "response"}

try:
    result = unstable_api_call("https://api.example.com")
    print(f"\nAPI result: {result}")
except ConnectionError:
    print("All retries failed")


# Pattern 3: Class-based decorator
class memoize:
    """Cache decorator — avoids repeated expensive calls."""
    def __init__(self, func: Callable):
        functools.update_wrapper(self, func)
        self._func = func
        self._cache: dict = {}
        self._hits = 0
        self._misses = 0

    def __call__(self, *args):
        if args in self._cache:
            self._hits += 1
            return self._cache[args]
        self._misses += 1
        result = self._func(*args)
        self._cache[args] = result
        return result

    @property
    def stats(self) -> dict:
        return {"hits": self._hits, "misses": self._misses, "cached": len(self._cache)}

@memoize
def fibonacci(n: int) -> int:
    if n < 2: return n
    return fibonacci(n - 1) + fibonacci(n - 2)

fibonacci(35)   # instant with memoization
print(f"\nFib cache stats: {fibonacci.stats}")


# Pattern 4: Stacking decorators
def log_call(func: Callable) -> Callable:
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        print(f"[LOG] Calling {func.__name__} with args={args}")
        result = func(*args, **kwargs)
        print(f"[LOG] {func.__name__} returned: {result}")
        return result
    return wrapper

@log_call      # applied second (outer)
@timer         # applied first (inner)
def calculate(a: int, b: int) -> int:
    return a ** b

# Execution: calculate → timer(log_call(calculate))
# Or more accurately: calculate calls timer wrapper, which calls log wrapper
calculate(2, 10)


# ══════════════════════════════════════════════════════════════════════════
# 5. GENERATORS — LAZY EVALUATION
# ══════════════════════════════════════════════════════════════════════════
"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT:
  Generator = function that uses 'yield' instead of 'return'.
  Returns a GENERATOR OBJECT — a lazy iterator.
  Values are computed ONE AT A TIME on demand.

WHY:
  ► Memory efficient — doesn't compute/store all values upfront
  ► Infinite sequences possible (fibonacci, counters)
  ► Pipeline processing — data flows through without accumulation
  ► LLM streaming — process tokens as they arrive

HOW (State Machine Internally):
  ┌──────────────────────────────────────────────────────┐
  │  def count(n):                                       │
  │      i = 0                                           │
  │      while i < n:                                    │
  │          yield i   ← PAUSE here, return i           │
  │          i += 1    ← RESUME here on next()          │
  │                                                      │
  │  gen = count(3)   # generator object created        │
  │                   # NO CODE RUNS YET!               │
  │                                                      │
  │  next(gen) → runs until yield → returns 0 → PAUSES │
  │  next(gen) → resumes → i=1 → yield 1 → PAUSES      │
  │  next(gen) → resumes → i=2 → yield 2 → PAUSES      │
  │  next(gen) → resumes → loop ends → StopIteration    │
  │                                                      │
  │  MEMORY COMPARISON:                                 │
  │  [x for x in range(10_000_000)] → 80MB in memory   │
  │  (x for x in range(10_000_000)) → ~200 bytes!       │
  └──────────────────────────────────────────────────────┘

REAL LIFE ANALOGY:
  List = printing all 1000 pages of a book before reading.
  Generator = reading one page, printing next only when needed.

  LLM Streaming = generator! Claude/GPT sends tokens one at a time.
  Your app processes each token as it arrives (streaming UI).

PRODUCTION EXAMPLES:
  # Process huge log file line by line (not all in memory)
  def read_logs(filename: str):
      with open(filename) as f:
          for line in f:
              yield line.strip()   # one line at a time

  # LLM streaming response
  def stream_response(prompt: str):
      for token in api.stream(prompt):
          yield token              # forward each token as it arrives

  # Batch processing — chunk large dataset
  def batches(items, size):
      for i in range(0, len(items), size):
          yield items[i:i+size]

  for batch in batches(documents, size=10):
      embed_batch(batch)           # 10 at a time, not all at once
"""

# Generator vs List — memory comparison
import tracemalloc

# List — all in memory
tracemalloc.start()
lst = [x**2 for x in range(100_000)]
_, list_mem = tracemalloc.get_traced_memory()
tracemalloc.stop()

# Generator — lazy
tracemalloc.start()
gen = (x**2 for x in range(100_000))
_, gen_mem = tracemalloc.get_traced_memory()
tracemalloc.stop()

print(f"\nList memory:      {list_mem/1024:.1f} KB")
print(f"Generator memory: {gen_mem/1024:.3f} KB")
print(f"Generator uses {list_mem/gen_mem:.0f}x less memory!")

# Generator pipeline — lazy processing chain
def read_data() -> Generator[str, None, None]:
    for line in ["  hello  ", "", "  world  ", "  AI  ", ""]:
        yield line

def strip_lines(gen) -> Generator[str, None, None]:
    for line in gen:
        yield line.strip()

def filter_empty(gen) -> Generator[str, None, None]:
    for line in gen:
        if line:
            yield line

def to_upper(gen) -> Generator[str, None, None]:
    for line in gen:
        yield line.upper()

# Pipeline — memory efficient!
pipeline = to_upper(filter_empty(strip_lines(read_data())))
print("\nPipeline output:")
for item in pipeline:
    print(f"  {item}")


# yield from — sub-generator delegation
def flatten(nested) -> Generator:
    for item in nested:
        if isinstance(item, (list, tuple)):
            yield from flatten(item)   # delegate!
        else:
            yield item

data = [1, [2, 3], [4, [5, [6, 7]]]]
print(f"\nFlattened: {list(flatten(data))}")


"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COMPREHENSIVE Q&A:

Q: Decorator ka purpose kya hota hai?
A: Kisi function ka behavior modify karna bina uska code change kiye.
   Cross-cutting concerns (logging, auth, cache, retry) ko
   business logic se alag rakhne ke liye.
   DRY principle follow karne ke liye.

Q: @functools.wraps kyun use karein?
A: Without it, decorated function ka __name__, __doc__, __annotations__
   sab "wrapper" ho jaata hai — debugging mein confusing hota hai.
   @wraps preserves original function's metadata.

Q: Closure aur Global variable mein kya difference hai?
A: Global — module level pe accessible, state shared between all calls
   Closure — function-level state, each call gets its own instance
   Closure is SAFER because state is encapsulated.

Q: Generator aur Iterator mein kya difference hai?
A: Iterator: class with __iter__ and __next__ methods.
   Generator: function with yield — Python auto-creates iterator.
   Generator is syntactic sugar for creating iterators.

Q: yield from kab use karein?
A: Jab ek generator dusre generator ko delegate karna ho.
   Recursive generators mein (like flatten).
   yield from properly passes send() values and handles StopIteration.

Q: Decorator stacking kaise kaam karta hai?
A: Bottom-up apply hote hain, top-down execute hote hain.
   @log @timer def f() → f = log(timer(f))
   Calling f() → log wrapper runs → calls timer wrapper → calls f
"""
