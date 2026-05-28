"""
py-spy & scalene — Practical Demos
====================================
Install:
    pip install py-spy scalene

This file is meant to be PROFILED by external tools.
Run in another terminal:

    # In terminal 1:
    python 14_pyspy_scalene_profiling.py

    # In terminal 2 (find PID first):
    py-spy top    --pid <PID>
    py-spy record --pid <PID> -o flame.svg --duration 30
    py-spy dump   --pid <PID>

    # Or profile directly:
    py-spy record -o flame.svg -- python 14_pyspy_scalene_profiling.py
    scalene 14_pyspy_scalene_profiling.py
"""
import os
import time
import random
import threading


# ============================================================
# Workload 1: CPU-heavy Python loop (will show wide bar in flame)
# ============================================================
def slow_python_loop(n=5_000_000):
    """Pure Python loop — should dominate flame graph."""
    total = 0
    for i in range(n):
        total += i * i - i
    return total


# ============================================================
# Workload 2: Memory-allocating function (scalene will flag)
# ============================================================
def memory_hog():
    """Allocates large lists repeatedly."""
    data = []
    for i in range(100):
        data.append([j * 2 for j in range(10000)])
    return len(data)


# ============================================================
# Workload 3: Recursive function (deep stack)
# ============================================================
def fib_recursive(n):
    if n < 2:
        return n
    return fib_recursive(n - 1) + fib_recursive(n - 2)


# ============================================================
# Workload 4: I/O simulation (sleep — appears as "idle" in py-spy)
# ============================================================
def fake_io_call():
    time.sleep(0.05)
    return "data"


# ============================================================
# Workload 5: NumPy native code (scalene shows native vs Python)
# ============================================================
def numpy_workload():
    try:
        import numpy as np
        arr = np.random.rand(1_000_000)
        return (arr ** 2 - arr).sum()
    except ImportError:
        return slow_python_loop(1_000_000)


# ============================================================
# Workload 6: Multi-threaded (py-spy can profile each thread)
# ============================================================
def threaded_work():
    threads = [threading.Thread(target=slow_python_loop, args=(2_000_000,))
               for _ in range(4)]
    for t in threads: t.start()
    for t in threads: t.join()


# ============================================================
# Workload 7: Mixed — hot path with one slow function
# ============================================================
def process_request(req_id):
    # 80% simple
    data = {"id": req_id}
    # 20% slow path
    if req_id % 5 == 0:
        slow_python_loop(500_000)
    fake_io_call()
    return data


def request_loop():
    for i in range(100):
        process_request(i)


# ============================================================
# Print PID for external attach
# ============================================================
def print_pid():
    print("=" * 60)
    print(f"PID: {os.getpid()}")
    print("=" * 60)
    print("\nIn another terminal, run:")
    print(f"  py-spy top   --pid {os.getpid()}")
    print(f"  py-spy record -o flame.svg --pid {os.getpid()} --duration 30")
    print(f"  py-spy dump  --pid {os.getpid()}")
    print()


# ============================================================
# Main workload loop (long enough to profile)
# ============================================================
def main():
    print_pid()

    print("Starting workloads...\n")

    for iteration in range(3):
        print(f"\n--- Iteration {iteration+1} ---")

        print("  [1] Slow Python loop...")
        t = time.perf_counter()
        slow_python_loop()
        print(f"      {time.perf_counter()-t:.2f}s")

        print("  [2] Memory hog...")
        t = time.perf_counter()
        memory_hog()
        print(f"      {time.perf_counter()-t:.2f}s")

        print("  [3] Recursive fib(28)...")
        t = time.perf_counter()
        fib_recursive(28)
        print(f"      {time.perf_counter()-t:.2f}s")

        print("  [4] NumPy workload...")
        t = time.perf_counter()
        numpy_workload()
        print(f"      {time.perf_counter()-t:.2f}s")

        print("  [5] Threaded work...")
        t = time.perf_counter()
        threaded_work()
        print(f"      {time.perf_counter()-t:.2f}s")

        print("  [6] Request loop (mixed)...")
        t = time.perf_counter()
        request_loop()
        print(f"      {time.perf_counter()-t:.2f}s")


# ============================================================
# Quick interpretation guide
# ============================================================
INTERPRETATION = """
============================================================
INTERPRETING THE RESULTS
============================================================

PY-SPY FLAME GRAPH (flame.svg):
  - Open in browser
  - Look for WIDEST bars at TOP — those are bottlenecks
  - slow_python_loop should dominate
  - fib_recursive shows tall stack
  - numpy_workload shows time in C extension

PY-SPY TOP:
  - %Own = time in this function (excl. children)
  - %Total = time including children
  - Refresh shows live changes

PY-SPY DUMP:
  - Shows EVERY thread's current frame
  - Useful for hangs/deadlocks
  - Look for repeated 'lock.acquire' across threads

SCALENE OUTPUT:
  - "% Python" vs "% Native" columns
  - High % Python = candidate for C extension or PyPy
  - High % Native = your C lib is the bottleneck
  - "Memory" column shows per-line allocations

OPTIMIZATION ORDER:
  1. Profile FIRST — never guess
  2. Fix biggest contributor first (Amdahl's law)
  3. Re-profile after each fix
  4. Stop when "good enough" (define SLO upfront)

PRODUCTION TIPS:
  - Containerize with py-spy installed
  - Need SYS_PTRACE capability on Linux/k8s
  - Save flame graphs as build artifacts
  - Use Pyroscope/Datadog for continuous profiling
============================================================
"""


if __name__ == "__main__":
    main()
    print(INTERPRETATION)
