"""
Deadlock — Reproducible Examples + Detection + Fixes
======================================================
Each demo: (a) recreate deadlock, (b) detect, (c) fix.
"""
import threading
import asyncio
import time
import faulthandler
import sys
import signal
import traceback
import os


# ============================================================
# DEMO 1: Classic lock ordering deadlock
# ============================================================
def demo_lock_ordering_deadlock():
    print("=" * 60)
    print("DEMO 1: Lock ordering inversion (with timeout protection)")
    print("=" * 60)

    lock_a = threading.Lock()
    lock_b = threading.Lock()
    timeout = 2.0

    def task1():
        if lock_a.acquire(timeout=timeout):
            print("  Task1: got A, waiting for B...")
            time.sleep(0.1)
            if lock_b.acquire(timeout=timeout):
                print("  Task1: got B too")
                lock_b.release()
            else:
                print("  Task1: ❌ TIMEOUT on B — deadlock detected!")
            lock_a.release()
        else:
            print("  Task1: timeout on A")

    def task2():
        if lock_b.acquire(timeout=timeout):
            print("  Task2: got B, waiting for A...")
            time.sleep(0.1)
            if lock_a.acquire(timeout=timeout):
                print("  Task2: got A too")
                lock_a.release()
            else:
                print("  Task2: ❌ TIMEOUT on A — deadlock detected!")
            lock_b.release()
        else:
            print("  Task2: timeout on B")

    t1 = threading.Thread(target=task1)
    t2 = threading.Thread(target=task2)
    t1.start(); t2.start()
    t1.join(); t2.join()


# ============================================================
# DEMO 2: FIX — consistent ordering
# ============================================================
class Account:
    def __init__(self, id, balance):
        self.id = id
        self.balance = balance
        self.lock = threading.Lock()
    def __repr__(self):
        return f"Account({self.id}, ${self.balance})"


def transfer_safe(from_acc, to_acc, amt):
    # Sort by ID to guarantee global order
    first, second = sorted([from_acc, to_acc], key=lambda a: a.id)
    with first.lock:
        with second.lock:
            from_acc.balance -= amt
            to_acc.balance += amt


def demo_safe_transfer():
    print("\n" + "=" * 60)
    print("DEMO 2: Safe transfer with consistent lock ordering")
    print("=" * 60)

    a = Account(1, 1000)
    b = Account(2, 1000)

    # Simulate concurrent transfers in BOTH directions — would deadlock without ordering
    threads = []
    for _ in range(50):
        threads.append(threading.Thread(target=transfer_safe, args=(a, b, 1)))
        threads.append(threading.Thread(target=transfer_safe, args=(b, a, 1)))
    for t in threads: t.start()
    for t in threads: t.join()

    print(f"  Final: {a}, {b}")
    print(f"  Total preserved: {a.balance + b.balance == 2000} ✅")


# ============================================================
# DEMO 3: Lock vs RLock — re-entrant case
# ============================================================
def demo_lock_vs_rlock():
    print("\n" + "=" * 60)
    print("DEMO 3: Lock vs RLock for re-entrant calls")
    print("=" * 60)

    # Regular Lock — would deadlock if called recursively
    rlock = threading.RLock()

    def outer():
        with rlock:
            inner()

    def inner():
        with rlock:           # same thread re-acquires
            print("  inner() acquired RLock ✅ (Lock would deadlock here)")

    t = threading.Thread(target=outer)
    t.start()
    t.join()


# ============================================================
# DEMO 4: faulthandler — periodic stack dump
# ============================================================
def demo_faulthandler():
    print("\n" + "=" * 60)
    print("DEMO 4: faulthandler.dump_traceback_later")
    print("=" * 60)

    print("  Run with PYTHONFAULTHANDLER=1 or call faulthandler.enable()")
    print("  faulthandler.dump_traceback_later(timeout=N) prints stacks every N sec")

    # Enable
    faulthandler.enable()
    print("  ✅ faulthandler enabled — will dump on segfault/SIGABRT")

    # In real usage:
    # faulthandler.dump_traceback_later(timeout=30, repeat=True)
    # If app hangs, you see thread stacks in stderr


# ============================================================
# DEMO 5: SIGUSR1 handler — manual stack dump on demand
# ============================================================
def demo_signal_dump():
    print("\n" + "=" * 60)
    print("DEMO 5: SIGUSR1 handler for on-demand stack dump")
    print("=" * 60)

    def dump_stacks(sig, frame):
        print("\n[SIGUSR1] Dumping all thread stacks:")
        faulthandler.dump_traceback()

    if hasattr(signal, "SIGUSR1"):
        signal.signal(signal.SIGUSR1, dump_stacks)
        pid = os.getpid()
        print(f"  Send: kill -USR1 {pid}")
        print("  (skipping actual signal send in demo)")
    else:
        print("  SIGUSR1 not available on this platform")


# ============================================================
# DEMO 6: threading.enumerate + sys._current_frames
# ============================================================
def demo_live_thread_dump():
    print("\n" + "=" * 60)
    print("DEMO 6: Live thread stack inspection")
    print("=" * 60)

    def worker():
        time.sleep(2)

    workers = [threading.Thread(target=worker, name=f"Worker-{i}") for i in range(3)]
    for w in workers: w.start()
    time.sleep(0.5)  # let them start

    frames = sys._current_frames()
    for t in threading.enumerate():
        if t.ident in frames:
            print(f"\n  Thread: {t.name} (id={t.ident})")
            stack = traceback.format_stack(frames[t.ident])
            # Print just last frame for brevity
            print(f"    {stack[-1].strip()}")

    for w in workers: w.join()


# ============================================================
# DEMO 7: Async deadlock — sync lock in coroutine (BAD)
# ============================================================
async def demo_async_deadlock():
    print("\n" + "=" * 60)
    print("DEMO 7: Async + sync lock = event loop block")
    print("=" * 60)

    # Use asyncio.Lock instead of threading.Lock
    lock = asyncio.Lock()

    async def task(name):
        async with lock:
            print(f"  {name}: got async lock")
            await asyncio.sleep(0.1)
            print(f"  {name}: releasing")

    await asyncio.gather(task("T1"), task("T2"), task("T3"))
    print("  ✅ All tasks completed sequentially via async lock")


# ============================================================
# DEMO 8: try-lock with backoff (livelock prevention)
# ============================================================
import random


def demo_try_lock_backoff():
    print("\n" + "=" * 60)
    print("DEMO 8: try-lock with random backoff")
    print("=" * 60)

    lock_a = threading.Lock()
    lock_b = threading.Lock()
    success_count = [0]
    counter_lock = threading.Lock()

    def worker(name):
        attempts = 0
        while True:
            attempts += 1
            if lock_a.acquire(timeout=0.1):
                if lock_b.acquire(timeout=0.1):
                    with counter_lock:
                        success_count[0] += 1
                    lock_b.release()
                    lock_a.release()
                    return attempts
                lock_a.release()
            time.sleep(random.uniform(0, 0.05))  # backoff prevents livelock

    threads = [threading.Thread(target=worker, args=(f"W{i}",)) for i in range(5)]
    for t in threads: t.start()
    for t in threads: t.join()

    print(f"  {success_count[0]}/5 workers completed successfully ✅")


# ============================================================
# DEMO 9: Drop locks across I/O
# ============================================================
def demo_drop_lock_across_io():
    print("\n" + "=" * 60)
    print("DEMO 9: Don't hold locks across I/O")
    print("=" * 60)

    state_lock = threading.Lock()
    state = {"data": []}

    def buggy(item):
        with state_lock:
            time.sleep(0.05)        # ❌ simulated slow I/O — blocks others
            state["data"].append(item)

    def fixed(item):
        # Prepare outside lock
        time.sleep(0.05)            # I/O without lock
        # Only mutation inside lock
        with state_lock:
            state["data"].append(item)

    # Time both approaches
    state["data"] = []
    start = time.perf_counter()
    threads = [threading.Thread(target=buggy, args=(i,)) for i in range(5)]
    for t in threads: t.start()
    for t in threads: t.join()
    buggy_time = time.perf_counter() - start

    state["data"] = []
    start = time.perf_counter()
    threads = [threading.Thread(target=fixed, args=(i,)) for i in range(5)]
    for t in threads: t.start()
    for t in threads: t.join()
    fixed_time = time.perf_counter() - start

    print(f"  Buggy (lock across I/O): {buggy_time:.2f}s (serialized)")
    print(f"  Fixed (lock only mutate): {fixed_time:.2f}s (parallel I/O)")
    print(f"  Speedup: {buggy_time/fixed_time:.1f}x")


# ============================================================
# DEMO 10: Self-deadlock with Lock (then fix with RLock)
# ============================================================
def demo_self_deadlock():
    print("\n" + "=" * 60)
    print("DEMO 10: Self-deadlock detection")
    print("=" * 60)

    lock = threading.Lock()

    def recursive_bad(depth):
        if depth == 0:
            return
        acquired = lock.acquire(timeout=0.5)
        if not acquired:
            print(f"  Self-deadlock at depth {depth} ❌")
            return
        try:
            recursive_bad(depth - 1)
        finally:
            lock.release()

    t = threading.Thread(target=recursive_bad, args=(3,))
    t.start()
    t.join()

    # Fixed with RLock
    rlock = threading.RLock()

    def recursive_good(depth):
        if depth == 0:
            return
        with rlock:
            recursive_good(depth - 1)

    t = threading.Thread(target=recursive_good, args=(5,))
    t.start()
    t.join()
    print("  Recursive with RLock: ✅ depth 5 completed")


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    demo_lock_ordering_deadlock()
    demo_safe_transfer()
    demo_lock_vs_rlock()
    demo_faulthandler()
    demo_signal_dump()
    demo_live_thread_dump()
    asyncio.run(demo_async_deadlock())
    demo_try_lock_backoff()
    demo_drop_lock_across_io()
    demo_self_deadlock()

    print("\n" + "=" * 60)
    print("DETECTION TOOLS IN PROD")
    print("=" * 60)
    print("1. py-spy dump --pid <PID>")
    print("2. faulthandler.dump_traceback_later(30, repeat=True)")
    print("3. signal.SIGUSR1 handler -> kill -USR1 <PID>")
    print("4. PostgreSQL: log_lock_waits=on, deadlock_timeout=1s")
    print("5. asyncio.run(main(), debug=True)")
    print()
    print("PREVENTION:")
    print("- Consistent lock ordering (sort by id)")
    print("- Use RLock for re-entrant code")
    print("- Timeout on lock.acquire(timeout=N)")
    print("- Don't hold locks across I/O")
    print("- Prefer queue.Queue over manual locks")
