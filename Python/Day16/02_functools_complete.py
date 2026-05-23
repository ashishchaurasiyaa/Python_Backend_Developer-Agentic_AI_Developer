"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FUNCTOOLS MODULE — lru_cache, partial, reduce, total_ordering
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ARCHITECTURE UNDERSTANDING:
  functools = higher-order function utilities
  "Functions that work with other functions"

  KEY TOOLS:
  lru_cache      → memoization (cache function results)
  cache          → lru_cache with unlimited size (Python 3.9+)
  partial        → pre-fill function arguments
  reduce         → fold iterable into single value
  total_ordering → auto-generate comparison methods from 2
  wraps          → preserve metadata in decorators (already covered)
  singledispatch → function overloading by type

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import functools
import time

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. LRU_CACHE — MEMOIZATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
LRU = Least Recently Used
maxsize=128: cache stores last 128 unique calls
maxsize=None: unlimited (same as @cache)

WHEN TO USE: pure functions (same input → same output), expensive computation
WHEN NOT:    functions with side effects, functions taking mutable args (list, dict)
"""

@functools.lru_cache(maxsize=128)
def fibonacci(n: int) -> int:
    """Classic example — without cache: O(2^n), with cache: O(n)"""
    if n < 2:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)

# Test speed difference
start = time.perf_counter()
print(fibonacci(40))    # 102334155
print(f"Cached: {time.perf_counter() - start:.4f}s")   # near 0

# Cache info
info = fibonacci.cache_info()
print(info)     # CacheInfo(hits=38, misses=41, maxsize=128, currsize=41)

# Clear cache (useful in tests)
fibonacci.cache_clear()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LRU_CACHE with class methods — needs special handling
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ExpensiveCalculator:
    @functools.cached_property          # for properties
    def heavy_result(self):
        return sum(range(1_000_000))

    def expensive_method(self, n: int) -> int:
        # Can't use @lru_cache on instance method directly
        # (self is not hashable by default behavior issues)
        return self._compute(n)

    @functools.lru_cache(maxsize=256)
    def _compute(self, n: int) -> int:  # called via self, works fine
        return n ** 3

calc = ExpensiveCalculator()
print(calc._compute(10))   # computed
print(calc._compute(10))   # cached

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# Real use: API response caching
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

@functools.lru_cache(maxsize=1000)
def get_country_info(country_code: str) -> dict:
    """
    Cache country data — rarely changes, expensive to fetch.
    Note: returns frozenset/tuple, not dict (dict isn't hashable).
    For dicts, use Redis or manual cache instead.
    """
    # simulated expensive call
    time.sleep(0.01)
    return country_code.upper()     # simplified

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. PARTIAL — PRE-FILL ARGUMENTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
partial(func, *args, **kwargs) → new function with some args pre-filled
Use when: same function called many times with same arguments
"""

def power(base, exponent):
    return base ** exponent

square  = functools.partial(power, exponent=2)
cube    = functools.partial(power, exponent=3)
square2 = functools.partial(power, exponent=0.5)  # square root

print(square(4))        # 16
print(cube(3))          # 27
print(square2(16))      # 4.0

# partial with positional args
def log(level, message, timestamp=None):
    ts = timestamp or time.strftime("%H:%M:%S")
    print(f"[{level}] {ts} — {message}")

info_log  = functools.partial(log, "INFO")
error_log = functools.partial(log, "ERROR")
debug_log = functools.partial(log, "DEBUG")

info_log("Server started")          # [INFO] 10:30:00 — Server started
error_log("Connection failed")      # [ERROR] 10:30:00 — Connection failed

# Real use: pre-configure functions for map/filter
numbers = [1, -2, 3, -4, 5]

clamp = functools.partial(max, 0)           # clamp negatives to 0
clamped = list(map(clamp, numbers))
print(clamped)  # [1, 0, 3, 0, 5]

# sorting with custom key
from operator import attrgetter, itemgetter

students = [("Alice", 85), ("Bob", 92), ("Carol", 78)]
by_score = functools.partial(sorted, key=itemgetter(1))
print(by_score(students))   # sorted by score

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. REDUCE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
reduce(function, iterable, initializer=None)
Accumulates iterable into single value from left to right.
reduce(f, [a,b,c,d]) = f(f(f(a,b),c),d)
"""

numbers = [1, 2, 3, 4, 5]

# Basic accumulation
total   = functools.reduce(lambda acc, x: acc + x, numbers)      # 15
product = functools.reduce(lambda acc, x: acc * x, numbers)      # 120
maximum = functools.reduce(lambda a, b: a if a > b else b, numbers)  # 5

# With initializer (important for empty lists)
total_with_init = functools.reduce(lambda acc, x: acc + x, [], 0)  # 0 (not error)

# Flatten nested list
nested = [[1, 2], [3, 4], [5, 6]]
flat = functools.reduce(lambda acc, lst: acc + lst, nested, [])
print(flat)     # [1, 2, 3, 4, 5, 6]

# Build pipeline (function composition)
def compose(*functions):
    """Compose functions right-to-left: compose(f, g, h)(x) = f(g(h(x)))"""
    return functools.reduce(lambda f, g: lambda x: f(g(x)), functions)

add_one   = lambda x: x + 1
double    = lambda x: x * 2
square    = lambda x: x ** 2

# square then double then add_one
pipeline = compose(add_one, double, square)
print(pipeline(3))      # ((3^2)*2)+1 = 19

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. TOTAL_ORDERING
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
Define only __eq__ and ONE of __lt__, __le__, __gt__, __ge__
@total_ordering fills in the rest automatically.
"""

@functools.total_ordering
class Version:
    """Semantic version comparison: 1.2.3"""

    def __init__(self, version_str: str):
        parts = version_str.split(".")
        self.major, self.minor, self.patch = map(int, parts)

    def _as_tuple(self):
        return (self.major, self.minor, self.patch)

    def __eq__(self, other):
        return self._as_tuple() == other._as_tuple()

    def __lt__(self, other):                    # only need ONE comparison
        return self._as_tuple() < other._as_tuple()

    def __repr__(self):
        return f"Version({self.major}.{self.minor}.{self.patch})"


v1 = Version("1.2.3")
v2 = Version("2.0.0")
v3 = Version("1.2.3")

print(v1 < v2)      # True
print(v1 > v2)      # False  ← auto-generated!
print(v1 <= v3)     # True   ← auto-generated!
print(v1 >= v2)     # False  ← auto-generated!
print(v1 == v3)     # True

versions = [Version("2.1.0"), Version("1.0.0"), Version("1.2.3")]
print(sorted(versions))     # [Version(1.0.0), Version(1.2.3), Version(2.1.0)]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. SINGLEDISPATCH — Function Overloading by Type
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
singledispatch: different behavior based on TYPE of first argument.
"""

@functools.singledispatch
def process(data):
    """Default handler."""
    raise TypeError(f"Unsupported type: {type(data)}")

@process.register(int)
def _(data: int):
    return f"Integer: {data * 2}"

@process.register(str)
def _(data: str):
    return f"String: {data.upper()}"

@process.register(list)
def _(data: list):
    return f"List with {len(data)} items: {sum(data) if all(isinstance(x, (int,float)) for x in data) else data}"

print(process(42))              # Integer: 84
print(process("hello"))         # String: HELLO
print(process([1, 2, 3]))       # List with 3 items: 6

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INTERVIEW Q&A:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q: lru_cache aur cache ka difference?
A: lru_cache(maxsize=N) — LRU eviction when N entries filled
   cache = lru_cache(maxsize=None) — unlimited, no eviction, faster
   Use cache when memory isn't a concern (small result set).

Q: lru_cache ke saath mutable arguments?
A: lru_cache requires HASHABLE arguments.
   list/dict pass nahi kar sakte directly.
   Fix: convert to tuple before calling → cached_func(tuple(lst))

Q: partial vs lambda for pre-filling?
A: partial → cleaner, introspectable, preserves __doc__
   lambda  → ok for simple throwaway, harder to inspect
   partial(int, base=16) is cleaner than lambda x: int(x, base=16)

Q: reduce kab avoid karein?
A: When Python has built-in: sum(), max(), min(), any(), all().
   reduce() for non-standard accumulation logic only.
"""
