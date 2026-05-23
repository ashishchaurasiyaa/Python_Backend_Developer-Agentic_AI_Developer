"""
╔══════════════════════════════════════════════════════════════╗
║  PYTHON COMPLETE PRACTICAL — Section 01                      ║
║  Topic: Control Flow + Functions — Complete Reference        ║
╚══════════════════════════════════════════════════════════════╝
"""

from typing import Callable, TypeVar, Any, Generator

# ══════════════════════════════════════════════════════════════
# PART A: CONTROL FLOW
# ══════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────
# 1. IF / ELIF / ELSE
# ─────────────────────────────────────────────────────────────

def classify_response(status_code: int) -> str:
    if status_code == 200:
        return "OK"
    elif status_code == 201:
        return "Created"
    elif 400 <= status_code < 500:
        return f"Client Error ({status_code})"
    elif status_code >= 500:
        return "Server Error"
    else:
        return "Unknown"

# Ternary (conditional expression)
score = 85
grade = "PASS" if score >= 60 else "FAIL"

# Chained comparison (Pythonic)
temperature = 0.7
is_valid = 0.0 <= temperature <= 2.0    # Pythonic!
# vs: temperature >= 0.0 and temperature <= 2.0 (verbose)

# None check — always use 'is' or 'is not'
result = None
if result is None:
    print("No result")
if result is not None:
    print(result)

# Falsy check
data = []
if not data:
    print("Empty list")


# ─────────────────────────────────────────────────────────────
# 2. MATCH-CASE (Python 3.10+) — structural pattern matching
# ─────────────────────────────────────────────────────────────

def handle_event(event: dict) -> str:
    match event:
        case {"type": "message", "role": "user", "content": str(content)}:
            return f"User said: {content}"

        case {"type": "tool_call", "tool": str(tool), "args": dict(args)}:
            return f"Tool '{tool}' called with {args}"

        case {"type": "error", "message": str(msg), "retryable": True}:
            return f"Retryable error: {msg}"

        case {"type": "error", "message": str(msg)}:
            return f"Fatal error: {msg}"

        case {"type": str(unknown_type)}:
            return f"Unknown event: {unknown_type}"

        case _:
            return "Invalid event format"

events = [
    {"type": "message", "role": "user", "content": "Hello!"},
    {"type": "tool_call", "tool": "search", "args": {"query": "Python"}},
    {"type": "error", "message": "timeout", "retryable": True},
]
for e in events:
    print(handle_event(e))


# ─────────────────────────────────────────────────────────────
# 3. FOR LOOPS — complete patterns
# ─────────────────────────────────────────────────────────────

items = ["alpha", "beta", "gamma", "delta"]

# Basic
for item in items:
    print(item)

# Enumerate — index + value
for i, item in enumerate(items):
    print(f"{i}: {item}")

for i, item in enumerate(items, start=1):  # 1-indexed
    print(f"{i}: {item}")

# Zip — parallel iteration
names   = ["Alice", "Bob", "Charlie"]
scores  = [95, 87, 92]
models  = ["gpt-4", "claude", "gemini"]
for name, score, model in zip(names, scores, models):
    print(f"{name}: {score} ({model})")

# zip_longest — for unequal lengths
from itertools import zip_longest
for name, score in zip_longest(names, [95, 87], fillvalue=0):
    print(f"{name}: {score}")

# Dict iteration
config = {"model": "gpt-4", "temp": 0.7}
for key, value in config.items():
    print(f"{key} = {value}")

# Nested loops
matrix = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
for row in matrix:
    for val in row:
        print(val, end=" ")
    print()


# ─────────────────────────────────────────────────────────────
# 4. LOOP CONTROL — break, continue, else
# ─────────────────────────────────────────────────────────────

# break — exit loop immediately
for i in range(10):
    if i == 5:
        break
    print(i, end=" ")
print()   # 0 1 2 3 4

# continue — skip to next iteration
for i in range(10):
    if i % 2 == 0:
        continue
    print(i, end=" ")
print()   # 1 3 5 7 9

# for-else — else runs if loop completes WITHOUT break
def find_model(models: list[str], target: str) -> str:
    for model in models:
        if model == target:
            print(f"Found: {model}")
            break
    else:
        print(f"Not found: {target}")
    return target

find_model(["gpt-4", "claude", "gemini"], "claude")
find_model(["gpt-4", "claude", "gemini"], "llama")


# ─────────────────────────────────────────────────────────────
# 5. WHILE LOOPS
# ─────────────────────────────────────────────────────────────

# Retry pattern (common in backend/AI)
import time
import random

def call_api_with_retry(max_retries: int = 3, delay: float = 1.0) -> dict | None:
    attempt = 0
    while attempt < max_retries:
        attempt += 1
        try:
            # Simulate API call that might fail
            if random.random() < 0.6:
                raise ConnectionError("API timeout")
            return {"status": 200, "data": "response"}
        except ConnectionError as e:
            print(f"  Attempt {attempt}/{max_retries} failed: {e}")
            if attempt < max_retries:
                time.sleep(delay * (2 ** (attempt - 1)))  # exponential backoff
    return None

# Walrus operator in while (Python 3.8+)
import io
stream = io.StringIO("line1\nline2\nline3")
while line := stream.readline():
    print(f"Read: {line.rstrip()}")


# ══════════════════════════════════════════════════════════════
# PART B: FUNCTIONS — complete reference
# ══════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────
# 6. FUNCTION BASICS
# ─────────────────────────────────────────────────────────────

def greet(name: str, greeting: str = "Hello") -> str:
    """Return a greeting string."""
    return f"{greeting}, {name}!"

print(greet("Alice"))            # Hello, Alice!
print(greet("Bob", "Hi"))       # Hi, Bob!
print(greet(greeting="Hey", name="Charlie"))  # keyword args


# ─────────────────────────────────────────────────────────────
# 7. *ARGS AND **KWARGS
# ─────────────────────────────────────────────────────────────

def variadic(*args: int) -> int:
    """Accepts any number of positional arguments."""
    print(f"args: {args}")     # args is a tuple
    return sum(args)

variadic(1, 2, 3)
variadic(1, 2, 3, 4, 5)
nums = [1, 2, 3]
variadic(*nums)   # unpack list as args


def keyword_variadic(**kwargs: Any) -> None:
    """Accepts any number of keyword arguments."""
    print(f"kwargs: {kwargs}")  # kwargs is a dict

keyword_variadic(model="gpt-4", temp=0.7, stream=True)
config = {"model": "gpt-4", "temp": 0.7}
keyword_variadic(**config)   # unpack dict as kwargs


def combined(req: str, *args: int, flag: bool = False, **kwargs: str) -> None:
    """Combines all parameter types."""
    print(f"req={req}, args={args}, flag={flag}, kwargs={kwargs}")

combined("hello", 1, 2, 3, flag=True, key="value")


# ─────────────────────────────────────────────────────────────
# 8. KEYWORD-ONLY AND POSITIONAL-ONLY PARAMETERS
# ─────────────────────────────────────────────────────────────

# * separator — everything after * is keyword-only
def create_agent(name: str, model: str, *, temperature: float = 0.7, stream: bool = False):
    """temperature and stream MUST be passed as keywords."""
    return {"name": name, "model": model, "temp": temperature}

create_agent("agent1", "gpt-4", temperature=0.9)
# create_agent("agent1", "gpt-4", 0.9)  # TypeError!

# / separator — everything before / is positional-only (Python 3.8+)
def process_text(text: str, /, encoding: str = "utf-8") -> bytes:
    """text MUST be positional (cannot use text=)."""
    return text.encode(encoding)

process_text("hello")
# process_text(text="hello")  # TypeError!


# ─────────────────────────────────────────────────────────────
# 9. CLOSURES
# ─────────────────────────────────────────────────────────────

def make_multiplier(factor: float) -> Callable[[float], float]:
    """Returns a function that multiplies by factor."""
    def multiply(x: float) -> float:
        return x * factor   # 'factor' is closed over
    return multiply

double = make_multiplier(2.0)
triple = make_multiplier(3.0)
print(double(5))   # 10.0
print(triple(5))   # 15.0

# Closure captures the VARIABLE, not the value — classic gotcha
def make_adders_wrong() -> list[Callable]:
    funcs = []
    for i in range(5):
        funcs.append(lambda x: x + i)   # all capture same 'i'
    return funcs

adders_wrong = make_adders_wrong()
print([f(10) for f in adders_wrong])   # [14,14,14,14,14] — all use i=4!

def make_adders_correct() -> list[Callable]:
    funcs = []
    for i in range(5):
        funcs.append(lambda x, n=i: x + n)  # capture value with default arg
    return funcs

adders = make_adders_correct()
print([f(10) for f in adders])   # [10,11,12,13,14] — correct!


# ─────────────────────────────────────────────────────────────
# 10. HIGHER-ORDER FUNCTIONS
# ─────────────────────────────────────────────────────────────

# map — apply function to each element (lazy)
nums = [1, 2, 3, 4, 5]
squared = list(map(lambda x: x**2, nums))
print(squared)

# filter — keep elements passing predicate (lazy)
evens = list(filter(lambda x: x % 2 == 0, nums))
print(evens)

# reduce — fold (from functools)
from functools import reduce
product = reduce(lambda acc, x: acc * x, nums, 1)
print(product)   # 120

# sorted with key
agents = [{"name": "Bob", "score": 85}, {"name": "Alice", "score": 95}]
by_score = sorted(agents, key=lambda a: a["score"], reverse=True)

# Function as argument
def apply_twice(func: Callable[[int], int], value: int) -> int:
    return func(func(value))

print(apply_twice(lambda x: x * 2, 3))   # 12


# ─────────────────────────────────────────────────────────────
# 11. DECORATORS — complete guide
# ─────────────────────────────────────────────────────────────

import functools
import time

# Basic decorator
def timer(func: Callable) -> Callable:
    @functools.wraps(func)   # preserve metadata
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = (time.perf_counter() - start) * 1000
        print(f"[TIMER] {func.__name__}: {elapsed:.2f}ms")
        return result
    return wrapper

@timer
def slow_function(n: int) -> int:
    return sum(range(n))

slow_function(100_000)


# Decorator with arguments (factory pattern)
def retry(max_attempts: int = 3, exceptions: tuple = (Exception,)):
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    print(f"  Attempt {attempt}/{max_attempts}: {e}")
                    if attempt == max_attempts:
                        raise
            return None
        return wrapper
    return decorator

@retry(max_attempts=3, exceptions=(ConnectionError, TimeoutError))
def call_api(url: str) -> dict:
    if random.random() < 0.7:
        raise ConnectionError("timeout")
    return {"status": 200}


# Stacking decorators — applied bottom-up
def log_call(func: Callable) -> Callable:
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        print(f"[LOG] Calling {func.__name__}")
        result = func(*args, **kwargs)
        print(f"[LOG] Done {func.__name__}")
        return result
    return wrapper

@log_call
@timer
def process(n: int) -> int:
    return n * 2

process(42)
# Order: log_call → timer → process (outer first)


# Class-based decorator
class memoize:
    """Cache decorator using a class."""
    def __init__(self, func: Callable):
        functools.update_wrapper(self, func)
        self._func = func
        self._cache: dict = {}

    def __call__(self, *args):
        if args not in self._cache:
            self._cache[args] = self._func(*args)
        return self._cache[args]

@memoize
def fibonacci(n: int) -> int:
    if n < 2:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)

print(fibonacci(35))   # instant with memoization


# ─────────────────────────────────────────────────────────────
# 12. GENERATORS
# ─────────────────────────────────────────────────────────────

# Generator function — yields values lazily
def count_up(start: int, end: int) -> Generator[int, None, None]:
    current = start
    while current <= end:
        yield current
        current += 1

for num in count_up(1, 5):
    print(num, end=" ")
print()

# Generator is lazy — doesn't compute until requested
def infinite_sequence() -> Generator[int, None, None]:
    n = 0
    while True:
        yield n
        n += 1

gen = infinite_sequence()
print([next(gen) for _ in range(5)])   # [0,1,2,3,4]

# Generator expression (lazy comprehension)
squares_gen = (x**2 for x in range(1_000_000))  # no memory allocation!
print(next(squares_gen))   # 0
print(next(squares_gen))   # 1

# yield from — delegate to sub-generator
def flatten(nested: list) -> Generator:
    for item in nested:
        if isinstance(item, list):
            yield from flatten(item)
        else:
            yield item

print(list(flatten([1, [2, 3], [4, [5, 6]]])))  # [1,2,3,4,5,6]

# Generator pipeline — memory efficient processing
def read_lines(text: str) -> Generator[str, None, None]:
    for line in text.splitlines():
        yield line

def filter_empty(lines: Generator) -> Generator[str, None, None]:
    for line in lines:
        if line.strip():
            yield line

def to_upper(lines: Generator) -> Generator[str, None, None]:
    for line in lines:
        yield line.upper()

# Pipeline — only processes one line at a time
text_data = "hello\n\nworld\n\npython"
pipeline = to_upper(filter_empty(read_lines(text_data)))
print(list(pipeline))


# ─────────────────────────────────────────────────────────────
# INTERVIEW QUESTIONS
# ─────────────────────────────────────────────────────────────
"""
Q: What is the difference between *args and **kwargs?
A: *args collects extra positional arguments into a tuple.
   **kwargs collects extra keyword arguments into a dict.
   Both names are convention — the * and ** are what matter.

Q: What is a closure?
A: A function that retains access to variables from its enclosing scope
   even after the outer function has returned.
   The captured variables form a "closure" around the inner function.

Q: What does @functools.wraps do?
A: Copies __name__, __doc__, __annotations__ from wrapped function to wrapper.
   Without it, all decorated functions appear as 'wrapper' in tracebacks.

Q: What's the difference between a generator and a list comprehension?
A: List comprehension: eager (computes all at once), stores in memory.
   Generator expression: lazy (computes one at a time), minimal memory.
   Use generators for large datasets or infinite sequences.

Q: What is the for-else construct?
A: The else block runs when the loop completes WITHOUT hitting break.
   Used to detect if a search succeeded or failed.
   Common pattern: search for something, else = not found.

Q: What's the closure bug with for loops and lambdas?
A: lambda x: x + i captures the variable 'i', not its current value.
   When the lambda runs later, i has its final value (4 in range(5)).
   Fix: use default argument to capture value: lambda x, n=i: x + n
"""
