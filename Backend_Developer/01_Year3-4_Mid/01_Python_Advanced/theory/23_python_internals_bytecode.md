# Python Internals — Bytecode, Frame Objects, GC

## Quick Concepts

**WHAT:**
- **CPython** = Reference Python implementation (C-based)
- **Bytecode** = Compiled Python (.pyc files)
- **dis** = Disassemble bytecode to human-readable
- **Frame** = Execution context (stack frame)
- **gc** = Garbage collector
- **PyObject** = C-level representation of every Python object
- **AST** = Abstract Syntax Tree (Python code as data)

**WHY internals matter:**
- Performance optimization (know what's expensive)
- Debug subtle bugs (memory leaks, GC issues)
- Senior engineers understand systems they use

**HOW Python execution:**
```
Source code (.py)
    ↓ compile
AST (Abstract Syntax Tree)
    ↓ compile
Bytecode (.pyc)
    ↓ execute
Python Virtual Machine (PVM)
    ↓
C function calls in CPython
```

---

## Interview Questions & Answers

### Q1: dis module — bytecode disassembly?

**Answer:**

**WHAT:** Show Python bytecode for any function.

**WHY:**
- Understand what code actually does
- Compare optimization techniques
- Debug performance

**HOW — Basic disassembly:**

```python
import dis

def add(x, y):
    return x + y

dis.dis(add)
# Output:
#   2           0 RESUME                   0
#
#   3           2 LOAD_FAST                0 (x)
#               4 LOAD_FAST                1 (y)
#               6 BINARY_OP                0 (+)
#              10 RETURN_VALUE
```

**HOW — Compare implementations:**

```python
import dis

# Method 1: list comprehension
def squares_comp():
    return [x**2 for x in range(10)]


# Method 2: for loop
def squares_loop():
    result = []
    for x in range(10):
        result.append(x**2)
    return result


print("=== Comprehension ===")
dis.dis(squares_comp)

print("\n=== For loop ===")
dis.dis(squares_loop)


# Comprehension uses MAKE_FUNCTION + faster opcodes
# For loop uses LOAD_METHOD + CALL_METHOD (more overhead)
```

**HOW — Detailed analysis:**

```python
import dis
import inspect

def my_function(x, y, z=10):
    if x > 0:
        return x * y + z
    return 0

# Get bytecode info
bytecode = dis.Bytecode(my_function)

# Iterate instructions
for instr in bytecode:
    print(f"{instr.opname:<20} {instr.argrepr}")


# Code object info
print(f"Name: {my_function.__code__.co_name}")
print(f"Vars: {my_function.__code__.co_varnames}")
print(f"Consts: {my_function.__code__.co_consts}")
print(f"Stack size: {my_function.__code__.co_stacksize}")
```

**Common opcodes:**

| Opcode | Description |
|---|---|
| `LOAD_FAST` | Load local variable |
| `LOAD_GLOBAL` | Load global variable |
| `STORE_FAST` | Store to local |
| `BINARY_OP` | Binary operation (+, -, etc.) |
| `CALL` | Function call |
| `RETURN_VALUE` | Return from function |
| `JUMP_FORWARD` | Unconditional jump |
| `POP_JUMP_IF_FALSE` | Jump if top of stack is False |
| `LOAD_CONST` | Load constant value |

---

### Q2: Frame objects — call stack introspection?

**Answer:**

**WHAT:** Each function call creates a Frame object.

**WHY:**
- Debugging (pdb uses this)
- Profiling
- Decorators that inspect caller
- Custom error tracking

**HOW — Inspect current frame:**

```python
import sys
import inspect

def outer():
    inner()

def inner():
    # ⭐ Get current frame
    frame = sys._getframe()
    print(f"Function: {frame.f_code.co_name}")
    print(f"File: {frame.f_code.co_filename}")
    print(f"Line: {frame.f_lineno}")
    print(f"Locals: {frame.f_locals}")

    # ⭐ Get caller's frame
    caller_frame = frame.f_back
    print(f"Called from: {caller_frame.f_code.co_name}")


outer()
# Output:
# Function: inner
# File: ...
# Line: 12
# Locals: {'frame': <frame ...>}
# Called from: outer
```

**HOW — inspect module (cleaner):**

```python
import inspect

def log_caller():
    # ⭐ Get caller info
    caller = inspect.stack()[1]
    print(f"Called from {caller.function} at line {caller.lineno}")


def my_function():
    log_caller()  # Called from my_function at line 9


my_function()
```

**HOW — Get full traceback (without exception):**

```python
import traceback

def function_a():
    function_b()

def function_b():
    function_c()

def function_c():
    # ⭐ Print stack without exception
    traceback.print_stack()

function_a()
```

**HOW — Custom decorator with caller info:**

```python
import inspect
import functools

def log_calls(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # ⭐ Get who called this function
        caller_frame = inspect.stack()[1]
        caller_name = caller_frame.function
        caller_file = caller_frame.filename

        print(f"{func.__name__} called from {caller_name} ({caller_file})")
        return func(*args, **kwargs)
    return wrapper


@log_calls
def my_function():
    pass


def main():
    my_function()  # my_function called from main ...


main()
```

---

### Q3: Garbage Collection — how Python manages memory?

**Answer:**

**WHAT:** Python uses TWO mechanisms:
1. **Reference counting** (immediate cleanup)
2. **Cycle collector** (handles circular refs)

**HOW reference counting works:**

```python
import sys

# Create object
x = [1, 2, 3]
print(sys.getrefcount(x))  # 2 (x + temporary ref for getrefcount)

# Add reference
y = x
print(sys.getrefcount(x))  # 3

# Remove reference
del y
print(sys.getrefcount(x))  # 2

# When count → 0, object freed immediately
del x
# [1, 2, 3] is freed
```

**HOW cycle collector handles circular refs:**

```python
import gc

# Create circular reference
class Node:
    def __init__(self):
        self.ref = None

a = Node()
b = Node()
a.ref = b
b.ref = a

# Reference count never reaches 0 (a refs b, b refs a)
del a, b
# Memory leak without cycle collector!

# ⭐ gc collects cycles
gc.collect()
print(gc.get_count())  # Lower count after collection
```

**HOW — gc module:**

```python
import gc

# ⭐ Inspect garbage
gc.set_debug(gc.DEBUG_LEAK)

# Force collection
collected = gc.collect()
print(f"Collected {collected} objects")

# Get stats
stats = gc.get_stats()
print(stats)
# [{'collections': 100, 'collected': 500, 'uncollectable': 0}, ...]

# ⭐ Disable GC (for benchmarks)
gc.disable()
# ... critical section
gc.enable()


# ⭐ Tune thresholds
# (700, 10, 10) = (gen0_threshold, gen1_threshold, gen2_threshold)
gc.set_threshold(1000, 10, 10)
```

**Generations explained:**

```python
# Python uses generational GC
# - Gen 0: Newly created objects
# - Gen 1: Survived 1 collection
# - Gen 2: Survived 2 collections (long-lived)

# Most objects die young (Gen 0)
# Gen 2 collected less often (saves time)
```

**HOW — Detect memory leaks:**

```python
import gc
import sys

# Print objects of specific type
def count_objects(klass):
    return len([o for o in gc.get_objects() if isinstance(o, klass)])


before = count_objects(MyClass)
do_thing()
after = count_objects(MyClass)
print(f"Leaked {after - before} objects")


# Find what holds object
def find_referrers(obj):
    return gc.get_referrers(obj)
```

---

### Q4: __slots__ — memory optimization deep?

**Answer:**

**WHAT:** Restrict class attributes, save memory.

**WHY:**
- Default class uses __dict__ (memory overhead)
- __slots__ uses fixed attribute array (compact)
- 50-70% memory savings for many instances

**HOW — Without slots:**

```python
class WithoutSlots:
    def __init__(self, x, y):
        self.x = x
        self.y = y


import sys

obj = WithoutSlots(1, 2)
# Has __dict__
print(obj.__dict__)  # {'x': 1, 'y': 2}
print(sys.getsizeof(obj))  # 48 bytes
print(sys.getsizeof(obj.__dict__))  # 296 bytes
# Total: ~344 bytes
```

**HOW — With slots:**

```python
class WithSlots:
    __slots__ = ("x", "y")  # ⭐ Fixed attributes only

    def __init__(self, x, y):
        self.x = x
        self.y = y


obj = WithSlots(1, 2)
print(sys.getsizeof(obj))  # ~56 bytes (10x smaller!)
# Total: ~56 bytes

# Can't add new attrs
# obj.z = 3  # ❌ AttributeError
# obj.__dict__  # ❌ AttributeError

# Can't have weakref unless explicit
class WithSlotsAndRef:
    __slots__ = ("x", "y", "__weakref__")
```

**HOW — Inheritance with slots:**

```python
class Base:
    __slots__ = ("a",)

class Child(Base):
    __slots__ = ("b",)  # ⭐ Combined with parent's slots
    
child = Child()
child.a = 1
child.b = 2

# ⚠️ If ANY ancestor lacks __slots__, you get __dict__ anyway
class BaseNoSlots:
    pass  # No __slots__

class ChildWithSlots(BaseNoSlots):
    __slots__ = ("x",)  # ⚠️ Still has __dict__ (inherited)
```

**Benchmark (1M instances):**

```python
import sys

class WithoutSlots:
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z

class WithSlots:
    __slots__ = ("x", "y", "z")
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z


# Create 1M instances
without = [WithoutSlots(1, 2, 3) for _ in range(1_000_000)]
with_slots = [WithSlots(1, 2, 3) for _ in range(1_000_000)]

# Memory usage
import resource
mem = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
print(f"Total memory: {mem / 1024:.0f} MB")

# Typical: WithoutSlots = 350 MB, WithSlots = 70 MB (5x less!)
```

---

### Q5: PyObject structure — C level?

**Answer:**

**WHAT:** Every Python object is a `PyObject` in C.

**HOW:**

```c
// CPython source (simplified)
typedef struct _object {
    Py_ssize_t ob_refcnt;        // Reference count
    PyTypeObject *ob_type;        // Type pointer
} PyObject;

typedef struct {
    PyObject_HEAD                 // Standard header
    long ob_ival;                 // The int value (for PyLongObject)
} PyLongObject;
```

**Why this matters:**

```python
import sys

# Every Python object has overhead
print(sys.getsizeof(0))         # 28 bytes (int)
print(sys.getsizeof(""))        # 49 bytes (str)
print(sys.getsizeof([]))        # 56 bytes (list)
print(sys.getsizeof({}))        # 64 bytes (dict)

# ⭐ Why list of ints is so big
print(sys.getsizeof([1,2,3]))  # 88 bytes
# Each int: 28 bytes + list overhead

# ⭐ array module much smaller (C-level array)
from array import array
arr = array("i", [1, 2, 3])
print(sys.getsizeof(arr))  # 80 bytes total, includes 3 ints
```

**HOW — Use C arrays for numeric data:**

```python
# Pure Python (slow + big)
data = [0] * 1_000_000  # ~8 MB (8 bytes per int reference)


# array module (fast + compact)
from array import array
data = array("i", [0] * 1_000_000)  # ~4 MB


# NumPy (fastest + compact)
import numpy as np
data = np.zeros(1_000_000, dtype=np.int32)  # ~4 MB, vectorized ops
```

---

### Q6: AST module — code as data?

**Answer:**

**WHAT:** Parse Python code into tree representation.

**WHY:**
- Static analysis (linters)
- Code generation
- Refactoring tools
- Custom DSLs

**HOW — Parse code:**

```python
import ast

code = """
def add(x, y):
    return x + y

result = add(1, 2)
print(result)
"""

tree = ast.parse(code)
print(ast.dump(tree, indent=2))
# Output: full AST representation
```

**HOW — Walk AST:**

```python
import ast

code = """
def function_a():
    pass

def function_b():
    pass

class MyClass:
    def method(self):
        pass
"""

tree = ast.parse(code)

# ⭐ Find all function definitions
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef):
        print(f"Function: {node.name} at line {node.lineno}")
    elif isinstance(node, ast.ClassDef):
        print(f"Class: {node.name} at line {node.lineno}")
```

**HOW — Modify AST (refactor):**

```python
import ast

class RenameFunction(ast.NodeTransformer):
    """Rename function calls."""
    def __init__(self, old_name, new_name):
        self.old_name = old_name
        self.new_name = new_name

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name) and node.func.id == self.old_name:
            node.func.id = self.new_name
        return self.generic_visit(node)


code = "result = old_func(1, 2); print(old_func(3, 4))"
tree = ast.parse(code)

# Rename old_func → new_func
transformer = RenameFunction("old_func", "new_func")
new_tree = transformer.visit(tree)
ast.fix_missing_locations(new_tree)

# Convert back to code
new_code = ast.unparse(new_tree)  # Python 3.9+
print(new_code)
# result = new_func(1, 2)
# print(new_func(3, 4))
```

**HOW — Compile and execute:**

```python
import ast

code = "x + y"
tree = ast.parse(code, mode="eval")

# Compile
compiled = compile(tree, "<string>", "eval")

# Execute with namespace
result = eval(compiled, {"x": 5, "y": 3})
print(result)  # 8
```

---

### Q7: How dict works internally?

**Answer:**

**WHAT:** Hash table with open addressing.

**HOW (simplified):**

```python
# When you do d[key] = value:
# 1. hash(key) → 64-bit integer
# 2. hash modulo table_size → slot index
# 3. Store (key, value) at slot
# 4. If collision, probe to next slot

# Why iteration order is insertion order (3.7+):
# Python 3.7+ uses compact dict (PEP 468)
# - Hash table maps hash → index in entries array
# - Entries array preserves insertion order
```

**HOW — Hash collisions:**

```python
class BadHash:
    def __init__(self, x):
        self.x = x

    def __hash__(self):
        return 0  # ⚠️ ALL objects hash to 0!

    def __eq__(self, other):
        return self.x == other.x


# Dict with hash collisions → O(n) lookups (DoS attack vector)
d = {}
for i in range(1000):
    d[BadHash(i)] = i
# Slow access!
```

**HOW — Custom __hash__:**

```python
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __hash__(self):
        return hash((self.x, self.y))  # ⭐ Use tuple of attrs

    def __eq__(self, other):
        return self.x == other.x and self.y == other.y

# ⚠️ Must implement BOTH __hash__ and __eq__
# ⚠️ a == b MUST imply hash(a) == hash(b)
```

---

### Q8: GIL — what it is, when it matters?

**Answer:**

**WHAT:** Global Interpreter Lock — only one thread executes Python bytecode at a time.

**WHY:**
- CPython memory management not thread-safe
- Simplifies C extensions
- Performance hit for CPU-bound multithreading

**HOW — GIL released during:**

```python
# ✅ I/O operations (file, network, sleep)
import time
import threading

def io_bound():
    time.sleep(1)  # ⭐ GIL released here

# Multiple threads run concurrently for I/O
threads = [threading.Thread(target=io_bound) for _ in range(10)]
start = time.time()
for t in threads:
    t.start()
for t in threads:
    t.join()
print(f"Time: {time.time() - start}")  # ~1 second (parallel)
```

**HOW — GIL kept during:**

```python
# ❌ CPU operations
def cpu_bound():
    sum(i*i for i in range(10_000_000))

# Multiple threads run SERIALLY for CPU
threads = [threading.Thread(target=cpu_bound) for _ in range(4)]
start = time.time()
for t in threads:
    t.start()
for t in threads:
    t.join()
print(f"Time: {time.time() - start}")  # ~8 seconds (serial)
# 4 threads = ~4x base time (no parallel)
```

**HOW — Workaround for CPU:**

```python
# Option 1: multiprocessing (separate processes = no GIL)
from multiprocessing import Pool

with Pool(4) as p:
    results = p.map(cpu_bound, range(4))
# True parallel — 4x speedup


# Option 2: C extensions release GIL
import numpy as np
# numpy ops release GIL during execution
arr = np.zeros(10_000_000)
result = arr.sum()  # Fast, GIL released


# Option 3: Python 3.13 free-threaded build (no GIL!)
# ./configure --disable-gil
# Then threads ACTUALLY parallelize CPU
```

---

### Q9: Memory profiling — find leaks?

**Answer:**

**HOW — tracemalloc (stdlib):**

```python
import tracemalloc

# Start tracking
tracemalloc.start()

# Take snapshot
snapshot1 = tracemalloc.take_snapshot()

# Do operations
data = [i for i in range(1_000_000)]
result = {i: str(i) for i in data}

# Take another snapshot
snapshot2 = tracemalloc.take_snapshot()

# Compare
top_stats = snapshot2.compare_to(snapshot1, "lineno")
print("[Top 10 differences]")
for stat in top_stats[:10]:
    print(stat)
# Shows what allocated most memory between snapshots
```

**HOW — pympler:**

```python
# pip install pympler

from pympler import asizeof, tracker

# Size of object + all referenced objects
data = {"users": [{"id": i} for i in range(1000)]}
size = asizeof.asizeof(data)
print(f"Total size: {size} bytes")


# Track new objects
tr = tracker.SummaryTracker()
# ... operations
tr.print_diff()
# Shows what objects were created
```

**HOW — memray (Bloomberg, very powerful):**

```bash
# pip install memray

memray run script.py
memray flamegraph memray-*.bin
# Visualize memory usage as flame graph
```

---

### Q10: Profiling — find slow code?

**Answer:**

**HOW — cProfile (stdlib):**

```python
import cProfile
import pstats

def slow_function():
    return sum(i*i for i in range(1_000_000))


cProfile.run("slow_function()", sort="cumulative")
# Shows: function calls, time per call


# Or save to file
profiler = cProfile.Profile()
profiler.enable()
slow_function()
profiler.disable()

stats = pstats.Stats(profiler)
stats.sort_stats("cumulative")
stats.print_stats(10)  # Top 10
```

**HOW — line_profiler:**

```python
# pip install line_profiler

# Add @profile decorator (no import needed)
@profile
def slow():
    total = 0
    for i in range(1_000_000):
        total += i * i
    return total


# Run with kernprof
# kernprof -l -v script.py
# Shows time per LINE
```

**HOW — py-spy (no code changes!):**

```bash
# pip install py-spy

# Profile running process
py-spy record -o profile.svg --pid $(pgrep python)

# Live top
py-spy top --pid $(pgrep python)

# Doesn't need code changes!
```

---

## How Debuggers & Coverage Work — sys.settrace vs sys.monitoring (PEP 669)

Ever wondered how `pdb`, `coverage.py`, and IDE debuggers actually hook into your running code? Two mechanisms:

### The old way — `sys.settrace` (slow but universal)

```python
import sys

def tracer(frame, event, arg):
    # Called for EVERY event in EVERY frame: 'call', 'line', 'return', 'exception'
    if event == "line":
        print(f"{frame.f_code.co_filename}:{frame.f_lineno}")
    return tracer          # return self to keep tracing nested calls

sys.settrace(tracer)       # pdb.set_trace() and old coverage.py sit on THIS
```

Problem: the interpreter must check "is there a tracer?" and call your Python function on **every line executed** — 2-10x slowdown even when you only care about one file. That's why running under a debugger or coverage used to hurt so much.

### The new way — `sys.monitoring` (Python 3.12+, PEP 669)

```python
import sys
mon = sys.monitoring
TOOL = mon.PROFILER_ID

mon.use_tool_id(TOOL, "mytool")
def on_line(code, line_number):
    if code.co_filename != "myapp.py":
        return mon.DISABLE          # ← the magic: per-code-object opt-out,
                                    #   interpreter stops firing events HERE entirely
    record(line_number)

mon.register_callback(TOOL, mon.events.LINE, on_line)
mon.set_events(TOOL, mon.events.LINE)
```

Events are compiled into the adaptive interpreter (same machinery as the 3.11+ specializing/3.13 JIT work), and `DISABLE` turns instrumentation off per-location — near-zero overhead for code you're not watching. `coverage.py` 7.4+ uses this on 3.12+; that's why modern coverage runs are dramatically faster.

**Interview line:** *"`sys.settrace` fires a Python callback on every line globally — that's the historic debugger/coverage overhead. PEP 669's `sys.monitoring` (3.12) registers per-event, per-tool callbacks that the adaptive interpreter can disable per code location, so instrumentation costs near-zero where you're not looking."*

Related niche hook: **audit hooks** (`sys.addaudithook`, PEP 578) — security-event stream (`open`, `exec`, socket connects) for sandboxing/compliance logging; unrelated to tracing performance but same "hook into the interpreter" family.

---

## Python Internals Checklist

```markdown
### Bytecode
- [ ] dis.dis to compare implementations
- [ ] Understand common opcodes
- [ ] Use bytecode insight for micro-optimization

### Memory
- [ ] __slots__ for many instances
- [ ] array module for numeric data
- [ ] NumPy for large numeric arrays
- [ ] tracemalloc for leak detection

### GC
- [ ] gc.collect() rarely needed (auto)
- [ ] gc.disable() for benchmarks
- [ ] Watch for circular references
- [ ] weakref for caches

### GIL
- [ ] threading for I/O-bound
- [ ] multiprocessing for CPU-bound
- [ ] Pure Python = GIL bottleneck for CPU
- [ ] C extensions can release GIL

### Profiling
- [ ] cProfile for function-level
- [ ] line_profiler for line-level
- [ ] py-spy for production (no restart)
- [ ] memray for memory profiling

### AST
- [ ] Use for static analysis
- [ ] ast.unparse to recover code (3.9+)
- [ ] NodeTransformer for refactoring
- [ ] Be careful with eval/compile (security)
```
