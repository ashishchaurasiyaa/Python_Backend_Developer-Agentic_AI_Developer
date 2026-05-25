# CPython vs PyPy — Deep Dive

> **Senior interview angle:** "Aapne kabhi PyPy production mein use kiya? Kab use karoge, kab nahi?"

---

## 1. Python is a Language, Not an Implementation

Python ek **specification** hai. Use implement karne wale multiple runtimes hain:

| Implementation | Written In | JIT? | Use Case |
|---|---|---|---|
| **CPython** | C | ❌ No | Default, reference implementation |
| **PyPy** | RPython | ✅ Yes (tracing JIT) | CPU-heavy pure-Python code |
| **Jython** | Java | ❌ | JVM interop (dead) |
| **IronPython** | C# | ❌ | .NET interop |
| **MicroPython** | C | ❌ | Embedded / microcontrollers |
| **GraalPy** | Java (GraalVM) | ✅ | Polyglot apps |

Jab koi `python script.py` kehta hai, **99% time CPython** chal raha hai.

---

## 2. CPython Internals (How `python file.py` actually runs)

```
.py source
   ↓ (lexer + parser)
AST (Abstract Syntax Tree)
   ↓ (compiler)
Bytecode (.pyc cached in __pycache__)
   ↓ (CPython VM — ceval.c main loop)
Execution (stack-based interpreter)
```

### Bytecode dekhne ka tareeqa

```python
import dis

def add(a, b):
    return a + b

dis.dis(add)
#   2           0 LOAD_FAST                0 (a)
#               2 LOAD_FAST                1 (b)
#               4 BINARY_OP                0 (+)
#               8 RETURN_VALUE
```

### CPython ka core loop — `ceval.c`

CPython ek **giant switch statement** hai jo har bytecode opcode ke liye C code execute karta hai. Yahi reason hai k CPython slow hai — har Python instruction = 5-10 C operations + reference counting + GIL acquire/release.

### GIL (Global Interpreter Lock)
- Ek hi thread Python bytecode execute kar sakta hai at a time
- CPython memory model thread-safe nahi hai (reference counting race-prone hai)
- I/O bound mein GIL release ho jaata hai (sleep, network, file I/O)
- CPU-bound multi-threading **useless** — use `multiprocessing` or PyPy

### Python 3.13+ ke changes
- **PEP 703** — Free-threaded CPython (`--disable-gil` build) experimental hai
- **PEP 744** — JIT compiler (copy-and-patch) experimental
- Matlab CPython slowly PyPy ke features adopt kar raha hai

---

## 3. PyPy Internals

PyPy ek **JIT (Just-In-Time)** compiler hai. Approach:

1. **Tracing JIT** — code run hota hai interpreted mode mein
2. Hot loops detect karta hai (e.g., `for i in range(1M)`)
3. Loop ka **machine code** generate karta hai (x86/ARM assembly)
4. Aage iterations native speed pe chalti hain

### Speed comparison (real benchmark)

```python
# Fibonacci, n=35
# CPython 3.11: ~3.2 seconds
# PyPy 3.10:    ~0.15 seconds   (20x faster)

# But for I/O bound (requests.get loop):
# CPython:  10 sec
# PyPy:     10 sec  (no improvement — bottleneck is network)
```

### PyPy ki strengths
- Pure Python loops/computation → **10-50x faster**
- Long-running processes (warmup time accha hai)
- Less memory (sometimes — depends on workload)

### PyPy ki weaknesses (Production gotchas)
- **C extensions slow** — cffi/cpyext layer overhead. NumPy/Pandas/lxml = slower than CPython!
- **Warmup time** — first few iterations slow (JIT compile ho raha hai)
- **Memory spike** — JIT compiled code RAM kha sakta hai
- **Some libs incompatible** — Django works, but TensorFlow/PyTorch nahi chalte
- **Debugging hard** — stack traces JIT optimization se confusing

---

## 4. Kab kya use karein? (Decision Framework)

| Scenario | Choose | Why |
|---|---|---|
| Web API (FastAPI/Django + Postgres) | **CPython** | I/O bound, libs mature |
| AI/ML pipeline (NumPy, PyTorch) | **CPython** | C extensions dominate |
| Pure Python algorithm crunching | **PyPy** | 10-50x speedup |
| Long-running data processing daemon | **PyPy** | JIT pays off |
| Quick scripts, CLIs | **CPython** | PyPy warmup overhead |
| Multi-core CPU-bound | **PyPy + multiprocessing** OR **C extension** | GIL bypass |

---

## 5. Free-threaded Python (PEP 703) — Future

Python 3.13 ne `--disable-gil` (no-GIL) build introduce kiya:

```bash
python3.13 --version  # default GIL build
python3.13t           # 't' = free-threaded
```

**Implications:**
- True parallel threads possible
- C extensions ko rewrite karna padega (thread-safe banane ke liye)
- 5-10% single-threaded slowdown (atomic refcounting overhead)
- Production-ready by Python 3.15 (~2027)

---

## 6. Practical Implications for Backend Engineer

1. **CPython me CPU-bound? → multiprocessing or write extension in Rust (PyO3) / C (Cython)**
2. **Server choose karte time:**
   - `uvicorn` + multiple workers (`--workers 4`) = process-level parallelism
   - GIL workers ke beech share nahi hota
3. **AI workloads:** model inference C++ mein hota hai, Python sirf glue — CPython fine
4. **PyPy try kab karein:** profiler dikhata hai 90% time pure Python loop mein — PyPy switch karke benchmark karo

---

## 7. Interview Questions

**Q1: GIL kya hai? CPython mein hi kyu hai?**
Reference counting thread-safe banane ka simplest way. Per-object lock dene se 30-40% slowdown aata single-thread mein.

**Q2: PyPy production mein kab nahi use karoge?**
- Heavy C extension dependency (NumPy, ML libs)
- Short-running scripts
- Memory-constrained environment
- Cutting-edge Python features (PyPy 1-2 versions peeche)

**Q3: GIL release kab hota hai?**
- Every ~100 bytecode instructions (configurable: `sys.setswitchinterval`)
- I/O syscalls ke time
- C extension explicitly release kare to (`Py_BEGIN_ALLOW_THREADS`)

**Q4: CPython ka future kya hai?**
- Faster CPython project (Sam Gross + Microsoft) — 5x improvement target
- JIT compiler (Brandt Bucher) — copy-and-patch approach
- Free-threading (PEP 703) — kill GIL gradually

**Q5: Free-threaded Python mein refcount kaise safe hota hai?**
- Biased reference counting (owner thread = fast path)
- Immortal objects (small ints, None, True/False — never decremented)
- Deferred decrement queue

---

## 8. Key Takeaways

- CPython = default, mature, slow but predictable
- PyPy = JIT speed for pure Python, breaks with C extensions
- GIL = single biggest CPython limitation (going away soon-ish)
- Production backend almost always CPython + horizontal scaling
- Senior engineer ka job: bottleneck identify karna — language switch ki bajaye sahi tool choose karna

---

## Related
- [[03_memory_gil]] — GIL deep dive
- [[05_async_concurrency_deep_dive]] — concurrency without GIL pain
- [[07_performance_profiling]] — when to PyPy vs profile-first
