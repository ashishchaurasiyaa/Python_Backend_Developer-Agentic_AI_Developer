# 07 — Performance Profiling & Optimization
**Python Backend Developer Interview Prep | Target: 40 LPA**
**Theory in Hinglish (Hindi explanations + English code/terms)**

---

## Table of Contents

1. [Performance Profiling kya hai?](#1-performance-profiling-kya-hai)
2. [timeit — Micro-benchmarks](#2-timeit--micro-benchmarks)
3. [cProfile — Function-Level Profiling](#3-cprofile--function-level-profiling)
4. [line_profiler — Line-by-Line Analysis](#4-line_profiler--line-by-line-analysis)
5. [memory_profiler — Memory Usage](#5-memory_profiler--memory-usage)
6. [tracemalloc — Built-in Memory Tracking](#6-tracemalloc--built-in-memory-tracking)
7. [Py-Spy — Sampling Profiler (Production Safe)](#7-py-spy--sampling-profiler-production-safe)
8. [Flame Graphs](#8-flame-graphs)
9. [Common Optimization Patterns](#9-common-optimization-patterns)
10. [asyncio Performance](#10-asyncio-performance)
11. [Database Query Optimization](#11-database-query-optimization)
12. [Profiling Web Applications](#12-profiling-web-applications)
13. [Interview Q&As](#13-interview-qas)

---

## 1. Performance Profiling kya hai?

### Concept

**Profiling** = apne program ka behavior measure karna — kaunsa code kitna time le raha hai, kitni memory use ho rahi hai, disk I/O kahan bottleneck ban raha hai.

Ek common galti jo junior developers karti hai: bina measurement ke optimize karna. Donald Knuth ne famous quote diya:

> "Premature optimization is the root of all evil."

Matlab: **pehle measure karo, phir optimize karo.** Bina profiling ke tune karna = dark mein shooting karna.

### Profiling ke Types

| Type | Kya measure karta hai | Tools |
|------|-----------------------|-------|
| **CPU Profiling** | Function execution time | cProfile, py-spy, line_profiler |
| **Memory Profiling** | RAM usage, allocations | tracemalloc, memory_profiler |
| **I/O Profiling** | Disk reads/writes, network latency | strace, py-spy, APM tools |
| **Concurrency Profiling** | Thread/async blocking | asyncio debug mode, py-spy |

### Profiling Overhead

Profiling khud bhi CPU/memory use karta hai. Iska matlab:

- **Deterministic profilers** (cProfile): har function call ko trace karte hain → **accurate lekin slow** (30-50% overhead)
- **Sampling profilers** (py-spy): periodically stack sample lete hain → **approximate lekin fast** (~1% overhead)

**Production pe deterministic profiler mat chalaao.** Production pe sampling profiler (py-spy) use karo.

```
Development flow:
  1. timeit → micro-level: specific expression kitna fast?
  2. cProfile → macro-level: kaunsa function most time le raha hai?
  3. line_profiler → micro-level: wo function ki kaunsi line?
  4. tracemalloc → memory: kaunsa code RAM le raha hai?
  5. py-spy → production: live server pe bina code change ke?
```

### 80/20 Rule in Profiling

**Pareto principle**: 80% execution time sirf 20% code mein hota hai. Profiling se wo 20% dhundho, wahi optimize karo.

---

## 2. timeit — Micro-benchmarks

### timeit kya hai?

`timeit` Python ka standard library module hai jo **small code snippets ko accurately measure** karta hai. Regular `time.time()` se better hai kyunki:
- Multiple runs karke average leta hai
- GC (garbage collection) temporarily disable karta hai
- Warmup ke baad measure karta hai

### Basic Usage

```python
import timeit

# Simple expression
result = timeit.timeit("x = [i**2 for i in range(1000)]", number=10000)
print(f"10000 runs: {result:.3f}s")
print(f"Per run: {result/10000*1000:.3f}ms")
```

### `timeit.timeit(stmt, number=N)`

```python
import timeit

# Method 1: string statement (global scope mein chalega)
t = timeit.timeit(
    stmt="sum(range(100))",
    number=100_000
)
print(f"sum(range(100)) × 100k = {t:.3f}s")

# Method 2: callable (lambda ya function)
def my_func():
    return sum(range(100))

t = timeit.timeit(my_func, number=100_000)
print(f"my_func() × 100k = {t:.3f}s")

# Method 3: setup statement (imports, data preparation)
t = timeit.timeit(
    stmt="x in data",
    setup="data = list(range(10000)); x = 9999",  # worst case
    number=100_000
)
print(f"list search worst case × 100k = {t:.3f}s")
```

### `timeit.repeat(stmt, repeat=5, number=1000)`

```python
import timeit

# 5 trials, each 1000 runs → return list of 5 times
results = timeit.repeat(
    stmt="'-'.join(str(n) for n in range(100))",
    number=1000,
    repeat=5
)
print(f"All trials: {[f'{r:.4f}' for r in results]}")
print(f"Best:    {min(results):.4f}s")
print(f"Worst:   {max(results):.4f}s")
print(f"Average: {sum(results)/len(results):.4f}s")

# Best practice: min() use karo, average nahi
# Kyunki: best run = no OS interference, cleanest signal
```

### `%timeit` in Jupyter

```python
# Jupyter notebook mein:
%timeit sum(range(1000))
# Output: 19.8 µs ± 312 ns per loop (mean ± std. dev. of 7 runs, 100,000 loops each)

# Custom iterations:
%timeit -n 10000 -r 5 sum(range(1000))

# Multi-line cell magic:
%%timeit
data = list(range(10000))
result = sorted(data, reverse=True)
```

### CLI: `python -m timeit "..."`

```bash
# Basic
python -m timeit "sum(range(1000))"

# With setup
python -m timeit -s "data = list(range(10000))" "x = 5000 in data"

# Specify number of loops
python -m timeit -n 100000 -r 5 "x = 2**10"

# Useful for quick comparison without writing a script
```

### Best Practices

```python
# 1. Multiple runs lena (min use karo, not mean)
results = timeit.repeat(stmt, number=1000, repeat=7)
best_time = min(results)  # cleanest signal

# 2. Warmup implicitly ho jata hai kyunki timeit khud warm up karta hai
# Agar manually chahiye:
_ = timeit.timeit(stmt, number=100)       # warmup
actual = timeit.timeit(stmt, number=1000) # real measurement

# 3. Side effects avoid karo — pure computations measure karo
# BAD: global state change karta hai
counter = 0
def bad_bench():
    global counter
    counter += 1  # har run pe state change = inconsistent results

# GOOD: pure function
def good_bench(n=1000):
    return sum(range(n))  # no side effects

# 4. Realistic data use karo
# BAD: empty data structure
timeit.timeit("x in []", number=100_000)

# GOOD: realistic size data
timeit.timeit("x in data", 
              setup="data=list(range(10000)); x=5000",
              number=10_000)
```

### Comparison: list comprehension vs map vs for loop

```python
import timeit

n = 10_000
data = list(range(n))

# Three ways to square all numbers
t_comp = timeit.timeit(
    lambda: [x*x for x in range(n)], number=1000)

t_map = timeit.timeit(
    lambda: list(map(lambda x: x*x, range(n))), number=1000)

t_loop = timeit.timeit(
    """
result = []
for x in range(n):
    result.append(x*x)
""",
    setup=f"n={n}",
    number=1000
)

print(f"List comprehension: {t_comp:.3f}s")
print(f"map():              {t_map:.3f}s")  
print(f"for loop:           {t_loop:.3f}s")

# Typical results:
# List comprehension fastest ya same as map
# for loop with .append() slightly slower
# map() with lambda overhead adds up
```

---

## 3. cProfile — Function-Level Profiling

### cProfile kya hai?

`cProfile` Python ka **built-in deterministic profiler** hai. Har function call ko trace karta hai, count karta hai, aur time measure karta hai. Zero extra install chahiye.

Ye profiler bataata hai: **kaunsi function kitne baar call hui aur kitna time liya.**

### CLI se Run karna

```bash
# Sabse simple — script directly profile karo
python -m cProfile script.py

# Sort by cumulative time (most useful)
python -m cProfile -s cumulative script.py

# Sort options: calls, cumulative, filename, ncalls, pcalls,
#               line, name, nfl, stdname, time, tottime
python -m cProfile -s tottime script.py

# Output file save karo (pstats ya snakeviz se read karo)
python -m cProfile -o profile_output.prof script.py
```

### Code ke Andar Use karna

```python
import cProfile

# Method 1: run() — simplest
cProfile.run("main()")

# Method 2: enable/disable manual control
pr = cProfile.Profile()
pr.enable()
some_function_to_profile()
pr.disable()
pr.print_stats(sort='cumulative')

# Method 3: runctx — variables pass karna
cProfile.runctx("func(data)", 
                globals={"func": my_function}, 
                locals={"data": my_data})
```

### Stats Columns Samajhna

```
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
      100    0.123    0.001    0.456    0.005  mymodule.py:42(my_func)
```

| Column | Matlab |
|--------|--------|
| `ncalls` | Function kitni baar call hui |
| `tottime` | Is function mein sirf hi spend hua time (sub-calls minus) |
| `percall` | tottime / ncalls |
| `cumtime` | Is function + uske sabhi sub-calls ka total time |
| `percall` (2nd) | cumtime / ncalls |

**Key insight:**
- **tottime high** → is function ka apna logic slow hai
- **cumtime high** → ye function slow sub-calls call kar raha hai
- **ncalls high** → function bahut baar call ho rahi hai (loop mein?)

### pstats.Stats — Filter aur Sort

```python
import cProfile
import pstats
import io

pr = cProfile.Profile()
pr.enable()
# ... code to profile ...
pr.disable()

# StringIO mein capture karo
stream = io.StringIO()
ps = pstats.Stats(pr, stream=stream)

# Sort by different criteria
ps.sort_stats('cumulative')  # cumtime se sort
ps.print_stats(20)           # top 20 functions show karo

# Filter by function name
ps.print_stats('mymodule')   # sirf mymodule.py ke functions

# Strip long paths
ps.strip_dirs()
ps.print_stats(10)

print(stream.getvalue())
```

### `snakeviz` — Browser Visualization

```bash
# Install
pip install snakeviz

# Profile save karo
python -m cProfile -o output.prof my_script.py

# Browser mein sunburst chart open karo
snakeviz output.prof
```

`snakeviz` ek **sunburst (icicle) chart** show karta hai:
- Center = main function
- Outer rings = sub-calls
- Arc width = time proportion
- Click karo to zoom in

### Hot Path Kaise Dhundho

```python
# Step-by-step approach:

# 1. cProfile run karo, cumulative sort karo
# 2. Top functions dekho — kaunse unexpected hain?
# 3. ncalls dekho — koi function millions of times call ho rahi hai?
# 4. tottime dekho — agar high tottime hai, wo function khud slow hai
# 5. cumtime dekho — agar high cumtime hai, kuch sub-function slow hai

# Example output reading:
"""
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
        1    0.000    0.000    2.543    2.543  main.py:1(<module>)
        1    0.001    0.001    2.543    2.543  main.py:45(process_data)
    10000    0.234    0.000    2.541    0.000  main.py:30(fetch_user)  ← 10k calls! N+1?
    10000    2.307    0.000    2.307    0.000  db.py:12(execute_query) ← slow DB
"""
# Clearly: fetch_user 10000 times call ho rahi hai → N+1 problem
```

---

## 4. line_profiler — Line-by-Line Analysis

### line_profiler kya hai?

cProfile bataata hai **kaunsi function slow hai**. Lekin phir? Us function ki **kaunsi line** slow hai — ye `line_profiler` bataata hai.

```bash
pip install line_profiler
```

### @profile Decorator

```python
# script.py
from line_profiler import profile  # ya kernprof ke saath chalaane pe auto-inject hota hai

@profile
def slow_function(data):
    result = []
    for item in data:                    # Line 1
        processed = item ** 2            # Line 2
        if processed > 1000:             # Line 3
            result.append(processed)     # Line 4
    return sorted(result)                # Line 5

# Note: agar kernprof se chalaaoge, toh from line_profiler import profile nahi chahiye
# kernprof khud @profile inject karta hai global scope mein
```

### kernprof se Run karna

```bash
# Profile file save karo
kernprof -l script.py

# Results show karo
python -m line_profiler script.py.lprof

# Ya direct verbose output
kernprof -l -v script.py
```

### Output Samajhna

```
Line #      Hits         Time  Per Hit   % Time  Line Contents
==============================================================
     1                                           def slow_function(data):
     2      1000       1234.0      1.2      2.1      result = []
     3    100000     456789.0      4.6     77.8      for item in data:        ← 77% time!
     4    100000      34567.0      0.3      5.9          processed = item ** 2
     5    100000      45678.0      0.5      7.8          if processed > 1000:
     6     49823      49123.0      1.0      8.4              result.append(processed)
     7         1       1234.0   1234.0      2.1      return sorted(result)
```

| Column | Matlab |
|--------|--------|
| `Hits` | Ye line kitni baar execute hui |
| `Time` | Total time in microseconds |
| `Per Hit` | Time / Hits |
| `% Time` | Is line ka total function time mein share |

**Hotspot**: `% Time` highest wali line = optimization target.

### Kab Use Karna

```
cProfile output mein ek function bahut slow dikhe
    ↓
line_profiler se us specific function ki lines dekho
    ↓
Kaunsi line 50%+ time le rahi hai?
    ↓
Wahan optimize karo
```

---

## 5. memory_profiler — Memory Usage

### memory_profiler kya hai?

CPU profiling ke saath memory bhi important hai. `memory_profiler` **line-by-line RAM usage** track karta hai.

```bash
pip install memory_profiler
```

### @memory_profiler.profile Decorator

```python
from memory_profiler import profile

@profile
def allocate_memory():
    big_list = [i for i in range(1_000_000)]    # allocate
    big_dict = {i: i**2 for i in range(100_000)} # more
    del big_list                                   # free
    return big_dict
```

```bash
python -m memory_profiler script.py
```

Output:
```
Line #    Mem usage    Increment   Line Contents
================================================
     1   45.3 MiB     45.3 MiB   @profile
     2                           def allocate_memory():
     3   52.7 MiB    +38.2 MiB       big_list = [i for i in range(1_000_000)]
     4   67.4 MiB    +14.7 MiB       big_dict = {i: i**2 for i in range(100_000)}
     5   35.1 MiB    -32.3 MiB       del big_list
     6   67.4 MiB     +0.0 MiB       return big_dict
```

### mprof — Memory Over Time Plot

```bash
# Run with mprof (memory over time track karo)
mprof run python script.py

# Plot show karo (matplotlib required)
mprof plot

# Save to file
mprof plot -o memory_plot.png
```

### `memory_usage()` Function

```python
from memory_profiler import memory_usage

def my_func():
    data = [i**2 for i in range(500_000)]
    return sum(data)

# Run function aur memory track karo (every 0.1s sample)
mem_usage = memory_usage(my_func, interval=0.1, timeout=30)
print(f"Peak memory: {max(mem_usage):.1f} MiB")
print(f"Memory before: {mem_usage[0]:.1f} MiB")
print(f"Memory after:  {mem_usage[-1]:.1f} MiB")
```

### Memory Leak Detection

```python
from memory_profiler import memory_usage

# Repeated calls pe memory badhni chahiye ya stable rehni chahiye?
def potentially_leaky():
    # Simulate some work
    cache = {}
    for i in range(10000):
        cache[i] = [j**2 for j in range(100)]
    return cache  # returns new dict, no leak

baseline = memory_usage()[0]
mems = []
for _ in range(10):
    mems.append(memory_usage(potentially_leaky)[0])

print("Memory after each call:")
for i, m in enumerate(mems):
    print(f"  Call {i+1}: {m:.1f} MiB (+{m-baseline:.1f})")
```

---

## 6. tracemalloc — Built-in Memory Tracking

### tracemalloc kya hai?

`tracemalloc` Python 3.4+ mein built-in hai — **koi install nahi chahiye.** Ye memory allocations ko trace karta hai aur bata sakta hai:
- Ab kitni memory use ho rahi hai
- Peak memory kitni thi
- Kaunsi line ne kitna allocate kiya

Production environment mein **safer choice** hai memory_profiler se.

### Basic API

```python
import tracemalloc

# Tracking start karo
tracemalloc.start()

# ... apna code ...

# Current aur peak memory lo
current, peak = tracemalloc.get_traced_memory()
print(f"Current: {current / 1024 / 1024:.2f} MB")
print(f"Peak:    {peak / 1024 / 1024:.2f} MB")

# Tracking band karo
tracemalloc.stop()
```

### Snapshot — Top Allocators Dhundho

```python
import tracemalloc

tracemalloc.start()

# Code run karo
data = {str(i): [j**2 for j in range(100)] for i in range(5000)}

# Snapshot lo
snapshot = tracemalloc.take_snapshot()
tracemalloc.stop()

# Top allocations by line number
stats = snapshot.statistics('lineno')
print("Top 10 memory allocations:")
for stat in stats[:10]:
    print(f"  {stat.size / 1024:.1f} KB — {stat.traceback.format()[0]}")
```

### Two Snapshots Compare karna (Memory Growth)

```python
import tracemalloc

tracemalloc.start()

# State 1
snap1 = tracemalloc.take_snapshot()

# Kuch allocations karo
new_data = [[i**2 for i in range(1000)] for _ in range(100)]

# State 2
snap2 = tracemalloc.take_snapshot()

# Diff nikalo — kya naya allocate hua?
top_stats = snap2.compare_to(snap1, 'lineno')
print("Memory growth:")
for stat in top_stats[:5]:
    print(stat)
```

### Filters Use karna

```python
# Sirf apna code dekho, stdlib nahi
filters = [
    tracemalloc.Filter(inclusive=True, filename_pattern="*/myapp/*"),
    tracemalloc.Filter(inclusive=False, filename_pattern="<frozen*"),
]
filtered = snapshot.filter_traces(filters)
stats = filtered.statistics('lineno')
```

### Traceback depth badhaana

```python
# nframe=25 → deeper stack trace, identify exact caller
tracemalloc.start(nframe=25)

# ... code ...

snapshot = tracemalloc.take_snapshot()
stats = snapshot.statistics('traceback')
for stat in stats[:3]:
    print(f"\n{stat.size/1024:.1f} KB allocated:")
    for line in stat.traceback.format():
        print(f"  {line}")
```

---

## 7. Py-Spy — Sampling Profiler (Production Safe)

### Py-Spy kya hai?

`py-spy` ek **sampling profiler** hai jo:
- Bina code change ke kisi bhi running Python process se attach ho sakta hai
- **Near-zero overhead** hai (~1%) → production safe
- Rust mein likha gaya hai → fast aur reliable
- Root/sudo permissions ke saath kisi bhi process profile kar sakta hai

```bash
pip install py-spy
```

### Running Process se Attach karna

```bash
# Process ID dhundho
ps aux | grep python

# Live top-like view (htop jaisa)
py-spy top --pid 12345

# Duration ke baad automatically stop
py-spy top --pid 12345 --duration 30
```

### Flame Graph Record karna

```bash
# 30 seconds profile karo, SVG save karo
py-spy record -o profile.svg --pid 12345 --duration 30

# Script directly profile karo
py-spy record -o profile.svg -- python my_script.py

# Native C extension frames bhi dikhao
py-spy record -o profile.svg --native --pid 12345

# Browser mein open karo
open profile.svg  # macOS
xdg-open profile.svg  # Linux
```

### Current Stack Dump

```bash
# Ek baar ka stack trace dump (debugging ke liye)
py-spy dump --pid 12345

# JSON format mein
py-spy dump --pid 12345 --json
```

### Subprocess Spawn karna

```bash
# Naya process spawn karo aur immediately profile karo
py-spy top -- python -c "
import time
def slow():
    time.sleep(0.1)
while True:
    slow()
"
```

### Sampling vs Deterministic Profiler

| Aspect | cProfile (Deterministic) | py-spy (Sampling) |
|--------|--------------------------|-------------------|
| **How** | Har function call hook | Periodic stack snapshot |
| **Accuracy** | Exact call counts | Statistical approximation |
| **Overhead** | 30-50% slowdown | ~1% overhead |
| **Production safe** | No | Yes |
| **Code changes** | `cProfile.Profile()` | Zero |
| **Output** | Exact ncalls/time | Flame graph |
| **Use case** | Development debugging | Production diagnosis |

---

## 8. Flame Graphs

### Flame Graph kya hai?

Flame graph ek visualization hai jo **call stack depth aur time ko simultaneously** show karta hai. Brendan Gregg ne develop kiya (Netflix engineer).

```
    [main]
    [process_orders]
    [fetch_product]  [calculate_tax]
    [db_query]       [tax_api_call]
    
Y-axis: call stack depth (upar = callee)
X-axis: sampled time (wide = slow)
```

### Kaise Read karna

```
1. BOTTOM dekho: main() ya entry point
2. Upar jaate jaate: function calls
3. WIDE bars = zyada time spend hua
4. TOP ke wide bars = leaf functions (actual work ho raha hai)
5. MIDDLE mein wide bar = ek function bahut kuch call kar raha hai

GOOD: flat wide bar at top → one function is slow → easy to fix
BAD: many thin bars → overhead is distributed → harder to fix
```

### Flame Graph Types

| Type | X-axis | Best for |
|------|--------|----------|
| **CPU Flame Graph** | On-CPU time | CPU hotspots |
| **Off-CPU Flame Graph** | Off-CPU time (waiting) | I/O, locks, sleep |
| **Memory Flame Graph** | Allocations | Memory leaks |

### Flame Graph Generate karna

```bash
# py-spy se (easiest)
py-spy record -o flamegraph.svg -- python script.py

# cProfile + gprof2dot + graphviz
pip install gprof2dot
python -m cProfile -o output.prof script.py
gprof2dot -f pstats output.prof | dot -Tpng -o graph.png

# snakeviz (interactive HTML)
pip install snakeviz
python -m cProfile -o output.prof script.py
snakeviz output.prof

# Austin profiler (another sampling profiler)
pip install austin-dist
austin python script.py > austin.out
austin-tui python script.py  # terminal UI
```

---

## 9. Common Optimization Patterns

### Pattern 1: List vs Generator (Memory)

```python
# BAD — 10M integers memory mein load karo
numbers = [i for i in range(10_000_000)]  # ~80 MB
total = sum(numbers)

# GOOD — lazily evaluate, peak ~1 KB
total = sum(i for i in range(10_000_000))

# Rule: agar sirf ek baar iterate karna hai → generator use karo
# Rule: agar random access chahiye ya multiple iterations → list use karo
```

### Pattern 2: String Concatenation (O(n²) vs O(n))

```python
# BAD — O(n²) kyunki har += naya string object banata hai
result = ""
for i in range(10000):
    result += str(i)  # har step pe naya string allocate + copy

# GOOD — O(n), single join at the end
result = "".join(str(i) for i in range(10000))

# Ya list collect karke join
parts = []
for i in range(10000):
    parts.append(str(i))
result = "".join(parts)

# Python 3.12+ mein += internally optimized hai for simple cases
# Lekin production code mein join() hi use karo — intent clear bhi hai
```

**Why O(n²)?**
```
"" + "0" = "0"           # 1 char copy
"0" + "1" = "01"         # 2 chars copy
"01" + "2" = "012"       # 3 chars copy
...
Total copies = 1+2+3+...+n = n(n+1)/2 = O(n²)
```

### Pattern 3: Dict/Set Lookup vs List Search

```python
# BAD — O(n) per lookup
banned_words = ["spam", "hate", "abuse", "malware"]  # list
def is_banned(word):
    return word in banned_words  # O(n) each time!

# GOOD — O(1) per lookup (hash table)
banned_words = {"spam", "hate", "abuse", "malware"}  # set
def is_banned(word):
    return word in banned_words  # O(1) each time!

# Difference matters at scale:
# 1M lookups, 10k element list: ~50 seconds
# 1M lookups, 10k element set: ~0.1 seconds
```

### Pattern 4: functools.lru_cache (Memoization)

```python
from functools import lru_cache

# BAD — redundant computation
def fibonacci(n):
    if n < 2: return n
    return fibonacci(n-1) + fibonacci(n-2)
# fibonacci(35) → 29M+ recursive calls!

# GOOD — memoized
@lru_cache(maxsize=None)  # unlimited cache
def fibonacci_cached(n):
    if n < 2: return n
    return fibonacci_cached(n-1) + fibonacci_cached(n-2)
# fibonacci_cached(35) → 35 unique calls!

# Cache info
print(fibonacci_cached.cache_info())
# CacheInfo(hits=32, misses=36, maxsize=None, currsize=36)

# Cache clear karna
fibonacci_cached.cache_clear()

# maxsize=128 → LRU eviction (128 most recent results keep)
# maxsize=None → grow without limit (memory careful!)

# IMPORTANT: function arguments hashable honi chahiye (list nahi, tuple/int/str haan)
```

### Pattern 5: Avoid Global Variable Lookup

```python
# BAD — Python har bar global dict mein dhundta hai
import math

def compute_bad(data):
    result = []
    for x in data:
        result.append(math.sqrt(x))  # 'math' → global lookup, 'sqrt' → attribute lookup
    return result

# GOOD — local reference banao
def compute_good(data):
    _sqrt = math.sqrt  # local variable = faster lookup (LEGB: Local first)
    result = []
    for x in data:
        result.append(_sqrt(x))  # direct local reference
    return result

# More idiomatic:
def compute_best(data):
    from math import sqrt  # function-level import = local binding
    return [sqrt(x) for x in data]
```

### Pattern 6: __slots__ (Memory Optimization)

```python
# BAD — default __dict__ based class
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y
# Each instance: ~200-300 bytes (dict overhead)

# GOOD — slots based class
class PointSlots:
    __slots__ = ('x', 'y')  # tuple is slightly faster than list
    def __init__(self, x, y):
        self.x = x
        self.y = y
# Each instance: ~56 bytes (just the values)

# When to use:
# - Millions of instances banate ho (e.g., graph nodes, game objects)
# - Fixed attributes (runtime mein naya attribute nahi add karna)

# Trade-offs:
# - Can't add new attributes dynamically
# - Multiple inheritance ke saath careful rehna
# - Pickling thoda different hai
```

### Pattern 7: NumPy Vectorization

```python
import numpy as np
import time

data = list(range(1_000_000))
arr = np.array(data)

# SLOW — Python loop
start = time.time()
result = [x * 2 + 1 for x in data]
print(f"Python loop: {time.time()-start:.3f}s")

# FAST — NumPy vectorized (C mein chalti hai)
start = time.time()
result = arr * 2 + 1
print(f"NumPy:       {time.time()-start:.3f}s")

# Typically 10-100x faster
# Because: single BLAS/LAPACK call, no Python loop overhead, SIMD instructions

# Common numpy optimizations:
# np.sum() vs sum()
# np.where() vs if-else in loop
# Broadcasting vs nested loops
# np.dot() vs manual matrix multiply
```

### Pattern 8: `in` Operator — Set/Dict vs List

```python
# Performance hierarchy for 'x in collection':
# 
# set:  O(1)   ← hash lookup
# dict: O(1)   ← hash lookup  
# list: O(n)   ← linear scan
# tuple: O(n)  ← linear scan

# Practical rule:
# Agar static lookup table hai → set use karo
# Agar key-value mapping hai → dict use karo
# Agar ordered sequence hai aur lookups kam hain → list theek hai

STATUS_CODES_LIST = [200, 201, 204, 400, 401, 403, 404, 500]  # O(n)
STATUS_CODES_SET = {200, 201, 204, 400, 401, 403, 404, 500}  # O(1)

# 1M lookups pe:
# List: ~0.5 seconds
# Set:  ~0.05 seconds
```

### Pattern 9: Lazy Evaluation with itertools

```python
import itertools

# BAD — sab kuch pehle compute karo
all_combos = [(x, y) for x in range(1000) for y in range(1000)]  # 1M items!
for combo in all_combos:
    if combo[0] + combo[1] == 999:
        print(combo)
        break  # pehle element pe stop hona tha, lekin sab generate ho gaye

# GOOD — lazy, sirf zaroorat pe evaluate
combos = itertools.product(range(1000), range(1000))  # generator
for combo in combos:
    if combo[0] + combo[1] == 999:
        print(combo)
        break  # abhi bhi 1M combinations nahi bane

# Useful itertools:
# itertools.islice(gen, n)      — first n elements lo
# itertools.takewhile(pred, it) — condition true rehne tak lo
# itertools.chain(iter1, iter2) — concatenate generators
# itertools.groupby(data, key)  — group by key
```

### Pattern 10: Compiled Extensions for Hot Paths

```python
# Pure Python bahut slow ho to kya karein?

# Option 1: Cython (Python → C compilation)
# .pyx file likho, compile karo → C extension

# Option 2: Numba (JIT compilation)
from numba import jit

@jit(nopython=True)  # machine code compile karo
def fast_loop(n):
    total = 0.0
    for i in range(n):
        total += i ** 0.5
    return total

# First call: compile hoga (slow)
# Subsequent calls: compiled code (100x+ faster than Python)

# Option 3: ctypes — C library directly call karo
# Option 4: CFFI — C Foreign Function Interface
# Option 5: PyPy — JIT-based Python interpreter
```

---

## 10. asyncio Performance

### Event Loop ko Block Mat Karo

```python
import asyncio
import time

# BAD — CPU-intensive work event loop block karta hai
async def bad_handler():
    # Ye synchronous heavy computation hai
    result = sum(i**2 for i in range(10_000_000))  # blocks event loop!
    return result

# GOOD — thread pool mein offload karo
async def good_handler():
    loop = asyncio.get_event_loop()
    result = await asyncio.to_thread(
        lambda: sum(i**2 for i in range(10_000_000))
    )
    return result

# Rule: async functions mein sirf I/O-bound awaitable operations
# CPU-bound kaam → to_thread() ya ProcessPoolExecutor
```

### asyncio.to_thread() — Blocking Operations

```python
import asyncio
import time

def blocking_db_call(query: str) -> list:
    time.sleep(0.1)  # simulate slow DB (legacy sync driver)
    return [{"result": query}]

async def handle_request(query: str):
    # Blocking call ko thread mein run karo
    result = await asyncio.to_thread(blocking_db_call, query)
    return result

async def main():
    # Multiple requests concurrently (even though DB calls are blocking!)
    tasks = [handle_request(f"query_{i}") for i in range(10)]
    results = await asyncio.gather(*tasks)
    print(f"Got {len(results)} results")
```

### Semaphore — Concurrency Limit

```python
import asyncio
import aiohttp

# BAD — unlimited concurrency → server overwhelm
async def fetch_all_bad(urls):
    async with aiohttp.ClientSession() as session:
        tasks = [session.get(url) for url in urls]
        return await asyncio.gather(*tasks)  # 10000 simultaneous connections!

# GOOD — semaphore se limit karo
async def fetch_all_good(urls, max_concurrent=50):
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def fetch_one(session, url):
        async with semaphore:  # max 50 concurrent requests
            async with session.get(url) as response:
                return await response.json()
    
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_one(session, url) for url in urls]
        return await asyncio.gather(*tasks)
```

### Connection Pooling

```python
# BAD — har request pe naya connection
async def bad_db_query(query):
    conn = await asyncpg.connect(DATABASE_URL)  # expensive!
    result = await conn.fetch(query)
    await conn.close()
    return result

# GOOD — connection pool (startup pe banao, reuse karo)
pool = None

async def startup():
    global pool
    pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=5,   # minimum connections ready
        max_size=20,  # maximum connections allowed
    )

async def good_db_query(query):
    async with pool.acquire() as conn:  # pool se lo, reuse karo
        return await conn.fetch(query)
```

### P50/P95/P99 Latency Measurement

```python
import asyncio
import time
import statistics

async def measure_latency(func, calls=1000):
    latencies = []
    for _ in range(calls):
        start = time.perf_counter()
        await func()
        latencies.append((time.perf_counter() - start) * 1000)
    
    latencies.sort()
    n = len(latencies)
    
    print(f"Latency stats ({calls} calls):")
    print(f"  P50:  {latencies[int(n*0.50)]:.2f}ms")
    print(f"  P90:  {latencies[int(n*0.90)]:.2f}ms")
    print(f"  P95:  {latencies[int(n*0.95)]:.2f}ms")
    print(f"  P99:  {latencies[int(n*0.99)]:.2f}ms")
    print(f"  P99.9:{latencies[int(n*0.999)]:.2f}ms")
    print(f"  Max:  {max(latencies):.2f}ms")

# P99 important hai kyunki:
# P50 = median user experience (50% users ye ya better)
# P95 = 95th percentile (5% users worse experience)
# P99 = ye slow requests usually affect high-value users
# P99.9 = SLA boundaries ke liye important
```

---

## 11. Database Query Optimization

### N+1 Problem aur Django ORM

```python
# Classic N+1 problem:
# 1 query to get all orders
# N queries to get each order's customer
# = N+1 total queries

# BAD — N+1
from myapp.models import Order

def get_orders_bad():
    orders = Order.objects.all()  # Query 1: get orders
    for order in orders:
        print(order.customer.name)  # Query 2...N+1: get each customer!
    # 1 + N queries total

# GOOD — select_related (JOIN)
def get_orders_good():
    orders = Order.objects.select_related('customer')  # Single JOIN query
    for order in orders:
        print(order.customer.name)  # No extra query! Data already loaded

# GOOD — prefetch_related (separate optimized query)
def get_orders_prefetch():
    orders = Order.objects.prefetch_related('items')  # 2 queries total
    for order in orders:
        for item in order.items.all():  # No extra query!
            print(item.name)

# select_related: ForeignKey, OneToOne (SQL JOIN)
# prefetch_related: ManyToMany, reverse ForeignKey (separate SELECT + Python join)
```

### Slow Query Logging

```python
# Django settings.py
import logging

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'loggers': {
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'DEBUG',  # SQL queries log hongi
        },
    },
}

# Ya programmatically:
from django.db import connection

def view_with_query_count(request):
    initial_count = len(connection.queries)
    
    # ... your view logic ...
    result = Order.objects.all()
    for order in result:
        _ = order.customer  # potential N+1
    
    queries_used = len(connection.queries) - initial_count
    if queries_used > 10:
        print(f"WARNING: {queries_used} queries in one request!")
    
    return JsonResponse({"data": list(result.values())})
```

### EXPLAIN ANALYZE Reading

```sql
-- PostgreSQL mein slow query analyze karo
EXPLAIN ANALYZE
SELECT o.*, c.name 
FROM orders o 
JOIN customers c ON o.customer_id = c.id
WHERE o.created_at > '2024-01-01';

-- Output mein dekho:
-- "Seq Scan" → full table scan → index missing?
-- "Index Scan" → index use ho raha hai → good
-- cost=0.00..1234.56 → estimated cost
-- actual time=0.123..456.789 → actual time
-- rows=10000 → actual rows returned
```

```python
# Django se raw explain:
from django.db import connection

qs = Order.objects.filter(status='pending').select_related('customer')
explained = qs.explain(verbose=True, analyze=True)
print(explained)
```

### Django Debug Toolbar

```python
# settings.py (development only!)
INSTALLED_APPS = ['debug_toolbar', ...]
MIDDLEWARE = ['debug_toolbar.middleware.DebugToolbarMiddleware', ...]
INTERNAL_IPS = ['127.0.0.1']

# urls.py
import debug_toolbar
urlpatterns = [
    path('__debug__/', include(debug_toolbar.urls)),
    # ...
]

# Browser mein: right side toolbar dikhega
# "SQL" section: number of queries, duplicate queries, slow queries
# "Time" section: request breakdown
```

---

## 12. Profiling Web Applications

### FastAPI Middleware for Request Timing

```python
import time
import logging
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

class TimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        
        try:
            response = await call_next(request)
        except Exception as e:
            logger.error(f"Request failed: {e}")
            raise
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            
            # Header mein timing add karo
            if hasattr(response, 'headers'):
                response.headers["X-Process-Time"] = f"{duration_ms:.2f}ms"
            
            # Slow requests log karo
            level = logging.WARNING if duration_ms > 500 else logging.INFO
            logger.log(level, 
                f"{request.method} {request.url.path} "
                f"status={response.status_code} "
                f"time={duration_ms:.2f}ms"
            )
        
        return response

app = FastAPI()
app.add_middleware(TimingMiddleware)
```

### pyinstrument — Statistical Profiler

```python
# pip install pyinstrument
from pyinstrument import Profiler

# Context manager
profiler = Profiler()
with profiler:
    # ... code to profile ...
    result = process_large_dataset()

profiler.print()  # nice tree output in terminal

# Agar FastAPI mein:
@app.get("/slow-endpoint")
async def slow_endpoint():
    profiler = Profiler()
    with profiler:
        result = await expensive_operation()
    
    # Development mein HTML output
    print(profiler.output_text(unicode=True, color=True))
    return result
```

### Prometheus Histogram for P95

```python
from prometheus_client import Histogram, generate_latest
import time

# Histogram define karo (buckets in seconds)
REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint'],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)

@app.middleware("http")
async def prometheus_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start
    
    REQUEST_DURATION.labels(
        method=request.method,
        endpoint=request.url.path
    ).observe(duration)
    
    return response

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type="text/plain")

# Prometheus query for P95:
# histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))
```

### APM Tools Overview

| Tool | Strength | Pricing |
|------|----------|---------|
| **Datadog APM** | Full stack visibility, traces, logs correlation | Paid |
| **New Relic** | Application insights, custom dashboards | Freemium |
| **Sentry Performance** | Error + performance in one, transaction traces | Freemium |
| **Elastic APM** | Open source, Elasticsearch backend | Free (self-hosted) |
| **Jaeger** | Distributed tracing, OpenTelemetry | Free |
| **Grafana Tempo** | Traces, integrates with Prometheus | Free |

```python
# OpenTelemetry — vendor agnostic instrumentation
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

tracer = trace.get_tracer(__name__)

FastAPIInstrumentor.instrument_app(app)  # auto-instrument all endpoints

@app.get("/users/{user_id}")
async def get_user(user_id: int):
    with tracer.start_as_current_span("fetch_user_from_db") as span:
        span.set_attribute("user.id", user_id)
        user = await db.get_user(user_id)
        return user
```

---

## 13. Interview Q&As

---

### Q1: Profiling aur Benchmarking mein kya fark hai?

**Answer:**

**Benchmarking** = performance measure karna (kitna fast hai?)
- Absolute time ya throughput measure karna
- Tool: `timeit`, `pytest-benchmark`
- Example: "ye function 5ms leta hai"

**Profiling** = kahan time ja raha hai ye measure karna (kyun slow hai?)
- Relative breakdown — which part is bottleneck
- Tool: `cProfile`, `py-spy`, `line_profiler`
- Example: "is function ka 80% time `db_query()` mein ja raha hai"

**Flow**: Profile karo → bottleneck dhundho → benchmark karo (baseline) → optimize karo → benchmark karo (improvement verify karo)

---

### Q2: cProfile mein tottime aur cumtime mein kya difference hai?

**Answer:**

```
def parent():       ← cumtime includes child() time
    child()         ← tottime = only parent's own code

def child():
    expensive()
```

- **`tottime`** (total time): Sirf is function ka apna execution time. Sub-functions ka time minus kiya hua.
  - High tottime → is function ka khud ka logic slow hai → optimize here
  
- **`cumtime`** (cumulative time): Is function + iske sabhi sub-function calls ka total time.
  - High cumtime, low tottime → ye function slow kuch aur call kar raha hai → drill down to children

**Example**: `main()` ka cumtime always high hoga (sab kuch call karta hai), lekin tottime low hoga. Optimization ke liye **tottime** dekho.

---

### Q3: Production pe kab py-spy use karein, cProfile nahi?

**Answer:**

**cProfile use karo when:**
- Development/staging environment hai
- Code change kar sakte ho (context manager add karna ok hai)
- Exact call counts chahiye
- Function-level breakdown exact chahiye

**py-spy use karo when:**
- Production server chalu hai, band nahi kar sakte
- Code change possible nahi (deploy nahi kar sakte)
- Hung process debug karna hai (`py-spy dump` for stack trace)
- Overhead concern hai (py-spy ~1% vs cProfile 30-50%)
- PID se attach karna hai

**Real world scenario**: "Production pe ek endpoint suddenly slow ho gaya hai. Rollback possible nahi hai. `py-spy top --pid $(pgrep gunicorn)` se live flame graph dekho without any code change or downtime."

---

### Q4: Sampling profiler vs deterministic profiler — internals explain karo

**Answer:**

**Deterministic Profiler (cProfile):**
```python
# Python's sys.setprofile() hook use karta hai
# Har 'call', 'return', 'exception' event pe callback fire hota hai
import sys

def tracer(frame, event, arg):
    if event == 'call':
        record_function_start(frame)
    elif event == 'return':
        record_function_end(frame)

sys.setprofile(tracer)
```
- Every function call tracked → accurate
- Overhead: every call = overhead → 30-50% slowdown

**Sampling Profiler (py-spy):**
```
Every N milliseconds (e.g., 1ms):
    1. Pause process briefly
    2. Read current call stack
    3. Record stack snapshot
    4. Resume process
```
- Statistical approximation: agar function 10% samples mein hai → ~10% CPU time
- Overhead minimal: interrupt every 1ms → 1ms/1000ms = ~0.1% overhead
- **Not exact**: rare fast functions might be missed

---

### Q5: Memory leak kaise detect karein Python mein?

**Answer:**

**Step 1: tracemalloc se snapshots compare karo**
```python
import tracemalloc

tracemalloc.start()
snap1 = tracemalloc.take_snapshot()

# Suspicious code run karo repeatedly
for _ in range(100):
    potentially_leaky_function()

snap2 = tracemalloc.take_snapshot()
diff = snap2.compare_to(snap1, 'lineno')
for stat in diff[:10]:
    print(stat)  # Lines where memory grew
```

**Step 2: Repeated calls pe memory growth check karo**
```python
import gc
import tracemalloc

tracemalloc.start()
mems = []
for i in range(20):
    function_under_test()
    gc.collect()  # explicit GC
    mems.append(tracemalloc.get_traced_memory()[0])

# Monotonically growing? → leak
print(mems)
```

**Common leak sources:**
- Module-level list/dict mein append karte rehna (never clear)
- Event listeners register karna, deregister bhool jaana
- Circular references (gc handles most, but not if `__del__`)
- C extension leaks (numpy/pandas internal)
- Thread-local storage accumulation

---

### Q6: String concatenation O(n²) kyun hai? Solve kaise karte hain?

**Answer:**

```python
# Har += ek naya string object banata hai aur copy karta hai
s = ""
s += "a"    # "a" create karo (1 char copy)
s += "b"    # "ab" create karo (2 chars copy)
s += "c"    # "abc" create karo (3 chars copy)
# ... n steps mein: 1+2+3+...+n = n(n+1)/2 = O(n²) copies

# Solution: join() — sirf ek baar allocate, sirf ek baar copy
parts = ["a", "b", "c", ..., "z"]
result = "".join(parts)
# join() pehle total length calculate karta hai, ek baar allocate karta hai
# Phir sab parts copy karta hai → O(n) total

# F-strings fast hain for small concatenations
name = f"{first} {last}"  # O(1) allocation

# StringBuilder pattern (explicit):
parts = []
for item in data:
    parts.append(transform(item))
result = "".join(parts)
```

---

### Q7: Set vs List membership testing — kab kya use karein?

**Answer:**

```python
# Hash table vs array scan
data_list = [1, 2, 3, ..., n]  # O(n) search
data_set  = {1, 2, 3, ..., n}  # O(1) search

# Use set when:
# - Membership testing frequent hai
# - Duplicates nahi chahiye
# - Order zaruri nahi
# - Elements hashable hain

# Use list when:
# - Order maintain karna hai
# - Duplicates allowed hain
# - Index-based access chahiye
# - Sequential processing hai

# Practical rule:
# Lookup table → set
# Sequence → list
# Key-value store → dict
```

---

### Q8: Generator vs List memory difference — internals explain karo

**Answer:**

```python
# List — eager evaluation
lst = [x**2 for x in range(1_000_000)]
# Python pehle sab 1M integers generate karta hai
# Memory: ~8 MB (1M × 8 bytes per int pointer) + int objects

# Generator — lazy evaluation
gen = (x**2 for x in range(1_000_000))
# Sirf ek generator object create hota hai
# Memory: ~112 bytes (generator frame object)
# Har .next() call pe ek value compute + return

# Internals:
# List: contiguous array of pointers in heap
# Generator: frame object with local variables + position pointer
#            Har next() pe frame resume hota hai

# Use generator when:
# - Large data ek baar iterate karna hai
# - Processing pipeline (map, filter, transform chains)
# - Infinite sequences

# Use list when:
# - Multiple iterations chahiye
# - Random access chahiye (lst[i])
# - Length check karna hai (len())
# - Data cache karna hai
```

---

### Q9: lru_cache internals — kaise kaam karta hai?

**Answer:**

```python
from functools import lru_cache

@lru_cache(maxsize=128)
def get_user(user_id: int) -> dict:
    return db.fetch(user_id)  # slow DB call
```

**Internally:**
1. **Hash map** (OrderedDict): `{args_tuple: result}` store karta hai
2. **LRU linked list**: recently used items ko track karta hai
3. **Lookup**: `args` tuple hash karo → O(1) dict lookup
4. **Eviction**: maxsize hit hone pe LRU (Least Recently Used) item remove karo
5. **Thread safety**: Python 3 mein thread-safe hai (GIL helps + internal locks)

```python
# Cache statistics
info = get_user.cache_info()
# CacheInfo(hits=85, misses=15, maxsize=128, currsize=15)

# hit rate = hits / (hits + misses)
hit_rate = info.hits / (info.hits + info.misses)

# Cache invalidate karna
get_user.cache_clear()

# maxsize=None → unbounded cache (dict only, no LRU, faster)
# maxsize=0 → cache disabled (for testing)

# Limitations:
# - Arguments hashable honi chahiye
# - Mutable defaults with state → bugs
# - Memory leak possible with large unique args
```

---

### Q10: Profiling overhead — production pe kya impact hota hai?

**Answer:**

| Profiler | Overhead | Production Safe? |
|----------|----------|-----------------|
| cProfile | 30-50% CPU | No |
| line_profiler | 50-100% CPU | No |
| memory_profiler | 10-30% + slow | No |
| tracemalloc | 5-15% | Conditional |
| py-spy | <1% | Yes |
| Prometheus metrics | <1% | Yes |
| Sentry/Datadog | 1-3% | Yes (configurable) |

**Best practices:**
```python
# 1. Development mein cProfile
# 2. Staging mein controlled tracemalloc
# 3. Production mein only:
#    - py-spy (when needed, temporary)
#    - Prometheus counters/histograms (always on, very low overhead)
#    - APM agent (1-2% overhead, acceptable)

# Conditional profiling:
import os
PROFILING_ENABLED = os.getenv("ENABLE_PROFILING", "false").lower() == "true"

if PROFILING_ENABLED:
    import cProfile
    profiler = cProfile.Profile()
    profiler.enable()

# ... code ...

if PROFILING_ENABLED:
    profiler.disable()
    profiler.print_stats(sort='cumulative')
```

---

## Quick Reference Cheat Sheet

```
Problem                          → Tool
─────────────────────────────────────────────────────────
"Kaunsi expression faster hai?" → timeit.timeit()
"Kaunsi function slow hai?"     → cProfile / snakeviz
"Kaunsi LINE slow hai?"         → line_profiler / kernprof
"Kitni RAM use ho rahi hai?"    → tracemalloc / memory_profiler
"Production pe live debug?"     → py-spy top/record
"Web request slow?"             → pyinstrument / APM tool
"DB queries zyada hain?"        → Django Debug Toolbar / EXPLAIN
"Memory leak?"                  → tracemalloc snapshots diff
─────────────────────────────────────────────────────────

Optimization Priority:
1. Algorithm change (O(n²) → O(n log n))
2. Data structure change (list → set for lookups)
3. Caching (lru_cache, Redis)
4. I/O optimization (connection pool, batch queries)
5. Code-level tweaks (__slots__, local vars, generators)
6. Native extensions (NumPy, Cython) — last resort
```

---

*End of Theory — 07_performance_profiling.md*
*Next: 08_concurrency_advanced.md*
