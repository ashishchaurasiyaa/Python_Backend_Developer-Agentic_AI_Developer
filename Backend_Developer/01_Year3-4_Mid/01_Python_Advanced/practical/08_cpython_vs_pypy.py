"""
CPython vs PyPy — Practical Demos
==================================

Run with both interpreters to compare:
    python 08_cpython_vs_pypy.py
    pypy3  08_cpython_vs_pypy.py

Install PyPy on Mac:
    brew install pypy3
"""
import sys
import time
import dis
import platform


# ============================================================
# DEMO 1: Identify which interpreter is running
# ============================================================
def show_interpreter():
    print("=" * 60)
    print(f"Implementation : {platform.python_implementation()}")
    print(f"Version        : {platform.python_version()}")
    print(f"Executable     : {sys.executable}")
    is_pypy = platform.python_implementation() == "PyPy"
    print(f"Is PyPy?       : {is_pypy}")
    print("=" * 60)


# ============================================================
# DEMO 2: Bytecode inspection (CPython only — PyPy compiles to machine code)
# ============================================================
def inspect_bytecode():
    def add_two(a, b):
        x = a + b
        return x * 2

    print("\n--- Bytecode of add_two() ---")
    dis.dis(add_two)

    # Also show compile-time info
    print("\n--- Code object attributes ---")
    co = add_two.__code__
    print(f"co_varnames : {co.co_varnames}")
    print(f"co_consts   : {co.co_consts}")
    print(f"co_argcount : {co.co_argcount}")


# ============================================================
# DEMO 3: Pure-Python loop — PyPy crushes CPython here
# ============================================================
def benchmark_pure_python_loop(n: int = 10_000_000) -> float:
    start = time.perf_counter()
    total = 0
    for i in range(n):
        total += i * i - i
    elapsed = time.perf_counter() - start
    print(f"Pure Python loop ({n:,} iters) -> {elapsed:.3f}s, total={total}")
    return elapsed


# ============================================================
# DEMO 4: Recursive Fibonacci — JIT-friendly
# ============================================================
def fib(n: int) -> int:
    if n < 2:
        return n
    return fib(n - 1) + fib(n - 2)


def benchmark_fib(n: int = 32) -> float:
    start = time.perf_counter()
    result = fib(n)
    elapsed = time.perf_counter() - start
    print(f"fib({n}) = {result} in {elapsed:.3f}s")
    return elapsed


# ============================================================
# DEMO 5: C extension workload — PyPy LOSES here
# ============================================================
def benchmark_c_extension():
    """NumPy is a C extension. PyPy ko cpyext compatibility layer use karna padta hai
    jo slow hai. CPython direct C API use karta hai."""
    try:
        import numpy as np
        arr = np.arange(10_000_000)
        start = time.perf_counter()
        result = (arr * arr - arr).sum()
        elapsed = time.perf_counter() - start
        print(f"NumPy sum ({len(arr):,} items) -> {elapsed:.3f}s, result={result}")
    except ImportError:
        print("NumPy not installed — skip")


# ============================================================
# DEMO 6: GIL impact — threading vs multiprocessing for CPU-bound
# ============================================================
def cpu_bound_task(n: int) -> int:
    """Pure CPU work — GIL holds the lock; threads don't help."""
    total = 0
    for i in range(n):
        total += i * i
    return total


def benchmark_threading_vs_multiprocessing():
    import threading
    import multiprocessing
    import os

    n = 10_000_000
    workers = 4

    # Sequential
    start = time.perf_counter()
    for _ in range(workers):
        cpu_bound_task(n)
    seq_time = time.perf_counter() - start

    # Threading (CPython me useless due to GIL)
    start = time.perf_counter()
    threads = [threading.Thread(target=cpu_bound_task, args=(n,)) for _ in range(workers)]
    for t in threads: t.start()
    for t in threads: t.join()
    thread_time = time.perf_counter() - start

    # Multiprocessing (true parallelism — each process has own GIL)
    start = time.perf_counter()
    with multiprocessing.Pool(workers) as pool:
        pool.map(cpu_bound_task, [n] * workers)
    mp_time = time.perf_counter() - start

    print(f"\nCPU cores available: {os.cpu_count()}")
    print(f"Sequential        : {seq_time:.3f}s")
    print(f"Threading (4)     : {thread_time:.3f}s  (GIL bottleneck)")
    print(f"Multiprocessing(4): {mp_time:.3f}s  (true parallelism)")
    print(f"Threading speedup : {seq_time/thread_time:.2f}x (CPython ~1x expected)")
    print(f"MP speedup        : {seq_time/mp_time:.2f}x (close to {workers}x ideal)")


# ============================================================
# DEMO 7: GIL switch interval inspection
# ============================================================
def show_gil_info():
    print("\n--- GIL Configuration ---")
    print(f"Switch interval: {sys.getswitchinterval()} seconds")
    print(f"  (every {sys.getswitchinterval()*1000:.1f}ms GIL can switch threads)")

    # Tweak it (rarely needed)
    # sys.setswitchinterval(0.001)  # 1ms — more responsive but more overhead


# ============================================================
# DEMO 8: Check if free-threaded build (Python 3.13+)
# ============================================================
def check_free_threaded():
    """Python 3.13t (no-GIL build) detection."""
    print("\n--- Free-threaded Python check ---")
    try:
        # sys.flags.gil exists only on 3.13+
        if hasattr(sys.flags, "gil"):
            gil_enabled = sys.flags.gil
            print(f"GIL enabled? {bool(gil_enabled)}")
        else:
            print("Python < 3.13 — GIL always on")
    except AttributeError:
        print("Not on 3.13+")


# ============================================================
# DEMO 9: When PyPy DOESN'T help — short script
# ============================================================
def short_script_demo():
    """Run-once scripts: PyPy ka JIT warmup CPython se mehnga padta hai."""
    start = time.perf_counter()
    # Simulate a CLI tool — import + small work + exit
    data = [i ** 2 for i in range(1000)]
    print(f"Quick task: {sum(data)} in {time.perf_counter()-start:.4f}s")
    print("(PyPy would be SLOWER here due to startup + JIT compile cost)")


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    show_interpreter()

    print("\n### DEMO 2: Bytecode")
    inspect_bytecode()

    print("\n### DEMO 3: Pure Python loop")
    benchmark_pure_python_loop()

    print("\n### DEMO 4: Recursive fib (small n for CPython)")
    benchmark_fib(30)

    print("\n### DEMO 5: NumPy (C extension)")
    benchmark_c_extension()

    print("\n### DEMO 6: GIL — threading vs multiprocessing")
    benchmark_threading_vs_multiprocessing()

    show_gil_info()
    check_free_threaded()

    print("\n### DEMO 9: Short script")
    short_script_demo()

    print("\n" + "=" * 60)
    print("RUN AGAIN WITH:  pypy3 08_cpython_vs_pypy.py")
    print("Compare timings — Demo 3 & 4 should be 5-20x faster on PyPy")
    print("Demo 5 (NumPy) may be SLOWER on PyPy")
    print("=" * 60)
