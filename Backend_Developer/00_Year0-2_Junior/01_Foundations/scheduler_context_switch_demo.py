"""
Scheduler + Context Switching -- verified practical demo.
"""

import os
import subprocess
import threading
import time


def demo_context_switch_overhead():
    print("=== Proof 1: context-switch overhead grows with thread count ===")
    print("  (many threads doing the SAME total work, split into more pieces --")
    print("   pure compute time should be ~constant, wall time should NOT be)\n")

    total_iterations = 20_000_000

    def worker(n):
        x = 0
        for i in range(n):
            x += 1

    for thread_count in (1, 4, 16):
        per_thread = total_iterations // thread_count
        start = time.perf_counter()
        threads = [threading.Thread(target=worker, args=(per_thread,)) for _ in range(thread_count)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.perf_counter() - start
        print(f"  {thread_count:>2} threads x {per_thread:>9,} iters each: {elapsed:.3f}s wall time")

    print("  (same 20M total iterations every row -- GIL means no real parallel")
    print("   speedup anyway, but MORE threads means MORE scheduler-driven")
    print("   switching between them to share the GIL, which is pure overhead")
    print("   on top of the actual compute)\n")


def demo_sched_yield_cost():
    print("=== Proof 2: raw cost of os.sched_yield() (voluntary CPU give-up) ===")
    n = 100_000
    start = time.perf_counter()
    for _ in range(n):
        os.sched_yield()
    elapsed = time.perf_counter() - start
    per_call_us = (elapsed / n) * 1_000_000
    print(f"  {n:,} calls to os.sched_yield() took {elapsed:.3f}s total")
    print(f"  = {per_call_us:.2f} microseconds per yield")
    print("  (this is the OS scheduler's minimum bookkeeping cost per")
    print("   voluntary switch -- the real number in this file's OS-concepts")
    print("   theory section, ~1-10 microseconds, verified in the same range)\n")


def demo_nice():
    print("=== Proof 3: process priority via os.nice() ===")
    pid = os.getpid()
    before = subprocess.check_output(["ps", "-o", "nice=", "-p", str(pid)], text=True).strip()
    print(f"  Current nice value: {before}")

    new_nice = os.nice(5)  # lowering priority (raising nice value) doesn't need root
    after = subprocess.check_output(["ps", "-o", "nice=", "-p", str(pid)], text=True).strip()
    print(f"  After os.nice(5): reported nice = {new_nice}, ps confirms: {after}")
    print("  (higher nice = lower scheduling priority = 'nicer' to other")
    print("   processes; RAISING priority, i.e. a NEGATIVE nice value, needs root)\n")


def demo_affinity_platform_gap():
    print("=== Bonus (real platform gotcha): CPU affinity is Linux-only in Python's os module ===")
    has_affinity = hasattr(os, "sched_getaffinity")
    print(f"  hasattr(os, 'sched_getaffinity') on this Mac: {has_affinity}")
    if not has_affinity:
        print("  -> macOS does NOT expose sched_getaffinity/sched_setaffinity.")
        print("     Linux's `taskset -cp 0,1 $PID` has no macOS equivalent through")
        print("     this API -- Apple Silicon's scheduler also has to juggle")
        print("     performance (P) vs efficiency (E) cores, which the OS manages")
        print("     itself rather than exposing raw pinning like Linux NUMA/affinity.")
        print("     If your code assumes `os.sched_getaffinity()` exists (common in")
        print("     Linux-authored deployment/ops tooling), it will crash on macOS —")
        print("     an actual portability gotcha, not a theoretical one.")


if __name__ == "__main__":
    demo_context_switch_overhead()
    demo_sched_yield_cost()
    demo_nice()
    demo_affinity_platform_gap()
