# Performance Optimization — Profiling, Vectorization, C Extensions, Cython

## Quick Concepts

**WHAT:**
- **Profiling** = Measure where time/memory spent
- **Vectorization** = NumPy operations on arrays (C-level)
- **Cython** = Compile Python → C for speed
- **PyO3** = Write Python extensions in Rust
- **Numba** = JIT compiler for numeric Python
- **PyPy** = Alternative Python with JIT (5-10x faster)
- **uvloop** = Faster asyncio event loop

**WHY optimization matters:**
- Slow apps = unhappy users
- Cloud costs scale with CPU/memory
- Senior = knows WHEN and HOW to optimize

**HOW optimization rules:**
```
1. Measure first (don't guess)
2. Algorithmic improvements first (O(n²) → O(n log n))
3. Then language-level (Python → vectorized)
4. Then C extensions (numpy, Cython, PyO3)
5. Then horizontal scaling (more processes)
6. Last: rewrite in faster language (Go, Rust)
```

---

## Interview Questions & Answers

### Q1: Profiling — find bottlenecks first?

**Answer:**

**WHAT:** Measure before optimizing.

**WHY:** Knuth: "Premature optimization is the root of all evil"

**HOW — cProfile (function-level):**

```python
import cProfile
import pstats

def slow_function():
    return sum(i*i for i in range(1_000_000))

# Profile + sort by time
cProfile.run("slow_function()", sort="cumulative")
# Output:
#         3 function calls in 0.234 seconds
#    Ordered by: cumulative time
#    ncalls  tottime  percall  cumtime  percall filename:lineno
#         1    0.234    0.234    0.234    0.234 script.py:1(slow_function)


# Profile + save for analysis
profiler = cProfile.Profile()
profiler.enable()
slow_function()
profiler.disable()

stats = pstats.Stats(profiler)
stats.strip_dirs().sort_stats("cumulative").print_stats(20)
```

**HOW — line_profiler (line-level):**

```bash
pip install line_profiler

# Add @profile decorator (no import)
```

```python
@profile
def slow():
    total = 0
    for i in range(1_000_000):
        total += i * i
    return total
```

```bash
# Run
kernprof -l -v script.py

# Output (line-by-line):
# Line #      Hits     Time   Per Hit   % Time  Line Contents
# ==============================================================
#    25         1      4.0      4.0      0.0    def slow():
#    26         1      1.0      1.0      0.0        total = 0
#    27   1000001  150000.0      0.1     90.0        for i in range(1_000_000):
#    28   1000000   20000.0      0.0     10.0            total += i * i
#    29         1      2.0      2.0      0.0        return total
```

**HOW — py-spy (production, no restart):**

```bash
pip install py-spy

# Live top
sudo py-spy top --pid <PID>

# Sample for 60s → flame graph
sudo py-spy record -o profile.svg --pid <PID> --duration 60
```

**HOW — Memory profiling:**

```python
# pip install memory_profiler

from memory_profiler import profile

@profile
def my_function():
    big_list = [0] * 1_000_000
    return sum(big_list)


# Run with python -m memory_profiler script.py
# Output: line-by-line memory usage
```

---

### Q2: Algorithmic improvements?

**Answer:**

**WHAT:** Choose better algorithm/data structure.

**HOW — Common improvements:**

```python
# 1. Set membership vs list (O(n) → O(1))
items_list = list(range(1_000_000))
items_set = set(items_list)

# Slow
if 999_999 in items_list:  # O(n) ~10ms
    pass

# Fast
if 999_999 in items_set:   # O(1) ~10μs
    pass


# 2. Dict lookup vs nested loops (O(n²) → O(n))
# ❌ SLOW
def find_pairs_slow(items, targets):
    pairs = []
    for item in items:
        for target in targets:
            if item == target:
                pairs.append((item, target))
    return pairs

# ✅ FAST
def find_pairs_fast(items, targets):
    target_set = set(targets)  # O(n) once
    return [(item, item) for item in items if item in target_set]


# 3. Sorting + binary search (O(n²) → O(n log n))
import bisect

# ❌ SLOW: O(n²)
def search_in_unsorted(arr, target):
    for item in arr:
        if item == target:
            return True
    return False

# ✅ FAST: O(n log n) sort + O(log n) search
def search_in_sorted(sorted_arr, target):
    idx = bisect.bisect_left(sorted_arr, target)
    return idx < len(sorted_arr) and sorted_arr[idx] == target


# 4. Counter for frequency
from collections import Counter

# ❌ SLOW
freq = {}
for item in items:
    if item in freq:
        freq[item] += 1
    else:
        freq[item] = 1

# ✅ FAST
freq = Counter(items)


# 5. defaultdict for grouping
from collections import defaultdict

# ❌ SLOW
groups = {}
for item in items:
    if item.category not in groups:
        groups[item.category] = []
    groups[item.category].append(item)

# ✅ FAST
groups = defaultdict(list)
for item in items:
    groups[item.category].append(item)
```

---

### Q3: NumPy vectorization?

**Answer:**

**WHAT:** Numpy operates on arrays at C speed.

**WHY:**
- 10-100x faster than pure Python
- Memory efficient (contiguous arrays)
- Releases GIL (true parallelism)

**HOW — Replace loops with vectorized ops:**

```python
import numpy as np

# ❌ SLOW: Python loop
def add_lists(a, b):
    return [x + y for x, y in zip(a, b)]


# ✅ FAST: NumPy
def add_arrays(a, b):
    return a + b  # ⭐ Vectorized


# Benchmark
a_list = list(range(1_000_000))
b_list = list(range(1_000_000))

import time

start = time.time()
result = add_lists(a_list, b_list)
print(f"List: {time.time() - start:.3f}s")  # ~0.10s

a = np.arange(1_000_000)
b = np.arange(1_000_000)

start = time.time()
result = a + b
print(f"NumPy: {time.time() - start:.3f}s")  # ~0.001s (100x faster!)
```

**HOW — Common vectorizations:**

```python
import numpy as np

# Sum of squares
# ❌ Pure Python
result = sum(x*x for x in items)

# ✅ NumPy
arr = np.array(items)
result = (arr ** 2).sum()


# Filter
# ❌ Pure Python
result = [x for x in items if x > 100]

# ✅ NumPy
arr = np.array(items)
result = arr[arr > 100]


# Apply function
# ❌ Pure Python
result = [math.sqrt(x) for x in items]

# ✅ NumPy
arr = np.array(items)
result = np.sqrt(arr)


# Matrix operations (huge speedup)
# ❌ Pure Python (O(n³))
def matmul_python(A, B):
    n = len(A)
    C = [[0]*n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            for k in range(n):
                C[i][j] += A[i][k] * B[k][j]
    return C

# ✅ NumPy (BLAS optimized)
C = A @ B  # ⭐ 1000x faster
```

---

### Q4: Memory optimization techniques?

**Answer:**

**HOW — __slots__:**

```python
# Without slots: each instance ~344 bytes
class WithoutSlots:
    def __init__(self, x, y):
        self.x = x
        self.y = y


# With slots: each instance ~56 bytes (6x smaller!)
class WithSlots:
    __slots__ = ("x", "y")
    def __init__(self, x, y):
        self.x = x
        self.y = y


# Test: 1M instances
import sys
without = [WithoutSlots(i, i) for i in range(1_000_000)]
with_slots = [WithSlots(i, i) for i in range(1_000_000)]

# Memory: 344MB vs 56MB
```

**HOW — Generators (lazy):**

```python
# ❌ BAD: Load everything in memory
def get_all_users():
    return [User(line) for line in open("100GB.txt")]  # OOM!


# ✅ GOOD: Generator (one at a time)
def get_users_gen():
    with open("100GB.txt") as f:
        for line in f:
            yield User(line)  # ⭐ Constant memory


# Usage
for user in get_users_gen():
    process(user)
```

**HOW — array module (numeric):**

```python
# Pure Python list of 1M ints: ~36 MB
data = [0] * 1_000_000


# array module: ~4 MB (9x less)
from array import array
data = array("i", [0] * 1_000_000)  # 'i' = signed int

# But NumPy is even better for numeric
import numpy as np
data = np.zeros(1_000_000, dtype=np.int32)  # ~4 MB + fast ops
```

**HOW — weakref:**

```python
import weakref

# ❌ Strong refs prevent GC
class Cache:
    def __init__(self):
        self.data = {}

    def add(self, key, obj):
        self.data[key] = obj  # ⚠️ Object lives forever

# ✅ Weak refs allow GC
cache = weakref.WeakValueDictionary()
cache["key"] = obj  # ⭐ Removed when no other refs
```

**HOW — Streaming JSON (large files):**

```python
# ❌ BAD: Load all
import json
with open("huge.json") as f:
    data = json.load(f)  # OOM!


# ✅ GOOD: Streaming
import ijson

with open("huge.json", "rb") as f:
    for item in ijson.items(f, "items.item"):
        process(item)  # ⭐ Constant memory
```

---

### Q5: Caching strategies?

**Answer:**

**HOW — functools.lru_cache:**

```python
from functools import lru_cache

# ⭐ Cache up to 128 results
@lru_cache(maxsize=128)
def expensive_function(x):
    print(f"Computing {x}")
    return x * x * x


expensive_function(5)  # Prints: Computing 5
expensive_function(5)  # Cached, no print
expensive_function(10)  # Prints: Computing 10

# Cache stats
print(expensive_function.cache_info())
# CacheInfo(hits=1, misses=2, maxsize=128, currsize=2)

# Clear cache
expensive_function.cache_clear()
```

**HOW — functools.cache (3.9+, unlimited):**

```python
from functools import cache

@cache  # ⭐ No size limit (use carefully)
def fibonacci(n):
    if n < 2:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

print(fibonacci(100))  # Instant (memoized)
```

**HOW — functools.cached_property:**

```python
from functools import cached_property

class User:
    def __init__(self, id):
        self.id = id

    @cached_property  # ⭐ Compute once per instance
    def expensive_data(self):
        print("Computing...")
        return load_from_db(self.id)


user = User(1)
user.expensive_data  # Prints: Computing...
user.expensive_data  # Cached
```

**HOW — TTL cache:**

```python
# pip install cachetools

from cachetools import TTLCache, cached

# ⭐ Cache with time-to-live
cache = TTLCache(maxsize=100, ttl=300)  # 5 min TTL

@cached(cache)
def fetch_user(user_id):
    return db.get_user(user_id)
```

**HOW — Redis cache (distributed):**

```python
import redis
import json
from functools import wraps

r = redis.Redis(host="localhost", port=6379)

def redis_cache(ttl=300):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Build cache key
            key = f"cache:{func.__name__}:{args}:{kwargs}"

            # Check cache
            cached = r.get(key)
            if cached:
                return json.loads(cached)

            # Compute
            result = func(*args, **kwargs)
            r.setex(key, ttl, json.dumps(result))
            return result
        return wrapper
    return decorator


@redis_cache(ttl=600)
def fetch_user(user_id):
    return db.get_user(user_id)
```

---

### Q6: Cython — compile Python to C?

**Answer:**

**WHAT:** Cython compiles Python (with type hints) to C.

**WHY:**
- 10-100x speedup for CPU-bound
- Drop-in replacement (mostly)
- Still importable from Python

**HOW — Simple Cython:**

```cython
# fastcompute.pyx
def compute(int n):  # ⭐ C int (not Python int)
    cdef int i  # ⭐ Declare C variable
    cdef int total = 0
    for i in range(n):
        total += i * i
    return total
```

```python
# setup.py
from setuptools import setup
from Cython.Build import cythonize

setup(ext_modules=cythonize("fastcompute.pyx"))
```

```bash
# Build
python setup.py build_ext --inplace

# Use
python -c "import fastcompute; print(fastcompute.compute(10_000_000))"
```

**Benchmark:**

```python
# Pure Python
def compute_py(n):
    total = 0
    for i in range(n):
        total += i * i
    return total

import time

start = time.time()
compute_py(10_000_000)
print(f"Python: {time.time() - start:.2f}s")  # ~1.5s


import fastcompute
start = time.time()
fastcompute.compute(10_000_000)
print(f"Cython: {time.time() - start:.2f}s")  # ~0.05s (30x faster!)
```

---

### Q7: Numba — JIT for numerical code?

**Answer:**

**WHAT:** Just-in-time compiler for numeric Python.

**WHY:**
- @jit decorator — no rewriting
- Optimized for NumPy
- Auto-parallel (@njit parallel=True)

**HOW:**

```python
# pip install numba

import numba
import numpy as np
import time


# Pure Python
def py_sum_sq(arr):
    total = 0.0
    for x in arr:
        total += x * x
    return total


# Numba JIT
@numba.njit  # ⭐ "no Python" mode (fastest)
def numba_sum_sq(arr):
    total = 0.0
    for x in arr:
        total += x * x
    return total


# Benchmark
arr = np.random.random(10_000_000)

start = time.time()
py_sum_sq(arr)
print(f"Python: {time.time() - start:.2f}s")  # ~2.5s

# First call compiles
numba_sum_sq(arr)

start = time.time()
numba_sum_sq(arr)
print(f"Numba: {time.time() - start:.3f}s")  # ~0.01s (250x faster!)
```

**HOW — Parallel Numba:**

```python
import numba

@numba.njit(parallel=True)  # ⭐ Auto-parallel
def parallel_sum(arr):
    total = 0.0
    for i in numba.prange(len(arr)):  # ⭐ Parallel range
        total += arr[i] * arr[i]
    return total
```

---

### Q8: PyPy — alternative interpreter?

**Answer:**

**WHAT:** Python with JIT compiler (vs CPython).

**WHY:**
- 5-10x faster for pure Python
- Drop-in replacement
- Same standard library

**HOW:**

```bash
# Install
brew install pypy3

# Use instead of python
pypy3 script.py


# Benchmark
$ cat fib.py
def fib(n):
    if n < 2: return n
    return fib(n-1) + fib(n-2)

print(fib(35))


$ time python3 fib.py    # ~3 seconds
$ time pypy3 fib.py      # ~0.5 seconds (6x faster)
```

**LIMITATIONS:**
- Slower startup
- C extensions slower (numpy, scipy)
- Some libraries don't work

**WHEN to use:**
- Pure Python code (no heavy C extensions)
- Long-running processes
- Web servers (Sanic with PyPy)

---

### Q9: Async optimization with uvloop?

**Answer:**

**WHAT:** Drop-in replacement for asyncio event loop.

**WHY:**
- 2-4x faster than default asyncio
- Built on libuv (Node.js loop)
- Used by FastAPI, Sanic in production

**HOW:**

```python
# pip install uvloop

import uvloop
import asyncio

# ⭐ One line speedup
uvloop.install()

asyncio.run(main())


# Or explicitly (3.12+)
uvloop.run(main())
```

**Benchmark:**

```
Async TCP echo server with 10,000 connections:

Standard asyncio: 50,000 req/s
uvloop:          150,000 req/s (3x faster!)
```

---

### Q10: When to rewrite in faster language?

**Answer:**

**SIGNS to consider rewrite:**

```
1. Profiled hot path → still slow after all Python optimizations
2. CPU-bound at scale (millions ops/sec)
3. Latency requirements (< 1ms)
4. High concurrency (100K+ connections)
5. Resource constraints (mobile, edge)


Common rewrites:
- Python → Rust (PyO3 — Python calls Rust)
- Python → Go (microservice extraction)
- Python → C/C++ (Cython, CFFI, ctypes)
```

**HOW — PyO3 (Python + Rust):**

```rust
// src/lib.rs
use pyo3::prelude::*;

#[pyfunction]
fn sum_squares(arr: Vec<i64>) -> i64 {
    arr.iter().map(|x| x * x).sum()
}

#[pymodule]
fn fastlib(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(sum_squares, m)?)?;
    Ok(())
}
```

```bash
# Build
pip install maturin
maturin develop

# Use from Python
python -c "import fastlib; print(fastlib.sum_squares([1,2,3,4]))"  # 30
```

**HOW — Microservice extraction:**

```
Architecture:
- Main app: Python (FastAPI)
- Hot path: Go microservice
- gRPC between them


Examples:
- Instagram: Python + C++ for image processing
- Uber: Python + Go for hot paths
- Dropbox: Python → Go for Magic Pocket storage
```

---

## Performance Toolkit

| Tool | Use Case | Cost |
|---|---|---|
| **cProfile** | Function profiling | Built-in |
| **line_profiler** | Line-level timing | Free |
| **py-spy** | Production profiling | Free |
| **memory_profiler** | Memory line-level | Free |
| **tracemalloc** | Memory tracking | Built-in |
| **NumPy** | Vectorize numeric | Free |
| **Cython** | Compile to C | Free |
| **Numba** | JIT numeric | Free |
| **PyPy** | Faster interpreter | Free |
| **uvloop** | Faster asyncio | Free |
| **orjson** | Faster JSON | Free |
| **PyO3** | Rust extensions | Free |

---

## Production Optimization Checklist

```markdown
### Profile First
- [ ] Identify hot spots (cProfile + py-spy)
- [ ] Don't optimize what's not slow
- [ ] Measure improvement (before/after)

### Quick Wins
- [ ] orjson instead of stdlib json (3-5x)
- [ ] uvloop instead of asyncio default (2-4x)
- [ ] httpx async instead of requests sync
- [ ] Caching with @lru_cache where useful
- [ ] Set membership instead of list `in`

### Algorithmic
- [ ] Use right data structure (set, dict, deque)
- [ ] Avoid O(n²) when O(n log n) possible
- [ ] Sort once, search many times
- [ ] Generators for large data (memory)

### Vectorization
- [ ] NumPy for numeric arrays
- [ ] Pandas for tabular data
- [ ] Vectorize loops

### Memory
- [ ] __slots__ for many instances
- [ ] Generators for large datasets
- [ ] Streaming JSON for large files
- [ ] Drop unused references

### When Python's Limit
- [ ] Cython for hot functions
- [ ] Numba for numerical
- [ ] PyO3 for new modules in Rust
- [ ] Microservice in Go for hot paths
- [ ] PyPy for long-running pure Python
```

---

## Optimization Order (Pareto Principle)

```
Step 1: Algorithm + Data Structures (60% of wins)
  - O(n²) → O(n log n) or O(n)
  - List → Set/Dict for lookups
  - Generator instead of list (memory)

Step 2: Python idioms (20%)
  - List comprehensions
  - Built-in functions (sum, max, etc.)
  - functools.lru_cache
  - " ".join() not += in loops

Step 3: Better libraries (10%)
  - orjson > json
  - uvloop > asyncio default
  - httpx > requests
  - asyncpg > psycopg2

Step 4: Vectorization (5%)
  - NumPy for numeric
  - Pandas for tabular
  - polars for big data

Step 5: C extensions (3%)
  - Cython
  - Numba (numerical)
  - Existing C libs

Step 6: Rewrite (2%)
  - PyO3 (Rust)
  - Go microservice
  - Last resort!
```
