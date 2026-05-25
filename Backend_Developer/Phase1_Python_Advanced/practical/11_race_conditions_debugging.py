"""
Race Conditions — Reproducible Bugs + Fixes
============================================
Each demo shows: (a) buggy version, (b) detection, (c) fix.
"""
import threading
import asyncio
import time
import queue
import sys
from itertools import count
from concurrent.futures import ThreadPoolExecutor


# ============================================================
# DEMO 1: Classic counter race
# ============================================================
def demo_counter_race():
    print("=" * 60)
    print("DEMO 1: Counter race (BUGGY)")
    print("=" * 60)

    counter = 0

    def increment():
        nonlocal counter
        for _ in range(100_000):
            counter += 1     # not atomic

    threads = [threading.Thread(target=increment) for _ in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()
    print(f"  Expected: 1,000,000")
    print(f"  Got     : {counter:,} (likely less due to race)")

    # FIX with Lock
    counter = 0
    lock = threading.Lock()

    def safe_increment():
        nonlocal counter
        for _ in range(100_000):
            with lock:
                counter += 1

    threads = [threading.Thread(target=safe_increment) for _ in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()
    print(f"  With Lock: {counter:,} ✅")


# ============================================================
# DEMO 2: TOCTOU (check-then-act) race
# ============================================================
def demo_toctou():
    print("\n" + "=" * 60)
    print("DEMO 2: TOCTOU (check-then-act)")
    print("=" * 60)

    cache = {}
    creation_count = 0
    create_lock = threading.Lock()

    def get_or_create_buggy(key):
        nonlocal creation_count
        if key not in cache:           # check
            time.sleep(0.001)          # simulate work — widens race window
            cache[key] = f"value_{key}"
            creation_count += 1
        return cache[key]

    cache.clear()
    creation_count = 0
    with ThreadPoolExecutor(max_workers=10) as ex:
        list(ex.map(get_or_create_buggy, ["A"] * 20))
    print(f"  Buggy: 'A' created {creation_count} times (expected: 1)")

    # FIX with lock
    cache.clear()
    creation_count = 0

    def get_or_create_safe(key):
        nonlocal creation_count
        with create_lock:
            if key not in cache:
                cache[key] = f"value_{key}"
                creation_count += 1
            return cache[key]

    with ThreadPoolExecutor(max_workers=10) as ex:
        list(ex.map(get_or_create_safe, ["A"] * 20))
    print(f"  Safe : 'A' created {creation_count} times ✅")


# ============================================================
# DEMO 3: Lazy singleton race
# ============================================================
class Heavy:
    instances_created = 0
    def __init__(self):
        type(self).instances_created += 1
        time.sleep(0.01)  # expensive init


def demo_singleton_race():
    print("\n" + "=" * 60)
    print("DEMO 3: Lazy singleton race")
    print("=" * 60)

    Heavy.instances_created = 0
    _instance = None

    def get_instance_buggy():
        nonlocal _instance
        if _instance is None:
            _instance = Heavy()
        return _instance

    threads = [threading.Thread(target=get_instance_buggy) for _ in range(20)]
    for t in threads: t.start()
    for t in threads: t.join()
    print(f"  Buggy: {Heavy.instances_created} instances (expected: 1)")

    # FIX with double-checked locking
    Heavy.instances_created = 0
    _instance = None
    _lock = threading.Lock()

    def get_instance_safe():
        nonlocal _instance
        if _instance is None:           # fast path
            with _lock:
                if _instance is None:   # re-check under lock
                    _instance = Heavy()
        return _instance

    threads = [threading.Thread(target=get_instance_safe) for _ in range(20)]
    for t in threads: t.start()
    for t in threads: t.join()
    print(f"  Safe : {Heavy.instances_created} instance ✅ (double-check lock)")


# ============================================================
# DEMO 4: async race with await
# ============================================================
async def demo_async_race():
    print("\n" + "=" * 60)
    print("DEMO 4: Async race condition")
    print("=" * 60)

    balance = {"alice": 1000}

    async def withdraw_buggy(amount):
        if balance["alice"] >= amount:        # check
            await asyncio.sleep(0.001)        # ← other coroutines run!
            balance["alice"] -= amount        # act

    balance["alice"] = 1000
    await asyncio.gather(*[withdraw_buggy(600) for _ in range(2)])
    print(f"  Buggy: balance = {balance['alice']} (expected ≥0, can go negative)")

    # FIX with asyncio.Lock
    lock = asyncio.Lock()
    balance["alice"] = 1000

    async def withdraw_safe(amount):
        async with lock:
            if balance["alice"] >= amount:
                await asyncio.sleep(0.001)
                balance["alice"] -= amount

    await asyncio.gather(*[withdraw_safe(600) for _ in range(2)])
    print(f"  Safe : balance = {balance['alice']} ✅")


# ============================================================
# DEMO 5: Producer-consumer with Queue (no manual locks needed)
# ============================================================
def demo_queue_pattern():
    print("\n" + "=" * 60)
    print("DEMO 5: Queue-based producer-consumer")
    print("=" * 60)

    q = queue.Queue(maxsize=10)
    results = []
    results_lock = threading.Lock()

    def producer():
        for i in range(50):
            q.put(i)
        q.put(None)  # sentinel

    def consumer():
        while True:
            item = q.get()
            if item is None:
                q.put(None)  # let other consumers exit
                break
            with results_lock:
                results.append(item * 2)
            q.task_done()

    p = threading.Thread(target=producer)
    cs = [threading.Thread(target=consumer) for _ in range(3)]
    p.start()
    for c in cs: c.start()
    p.join()
    for c in cs: c.join()
    print(f"  Processed {len(results)} items safely ✅")


# ============================================================
# DEMO 6: Detection — sys.setswitchinterval to expose races
# ============================================================
def demo_switch_interval_detection():
    print("\n" + "=" * 60)
    print("DEMO 6: Increase GIL switches to expose races")
    print("=" * 60)
    original = sys.getswitchinterval()
    print(f"  Default switch interval: {original}s")

    sys.setswitchinterval(0.00001)  # super aggressive
    print(f"  New switch interval    : {sys.getswitchinterval()}s")

    counter = 0
    def inc():
        nonlocal counter
        for _ in range(10_000):
            counter += 1

    threads = [threading.Thread(target=inc) for _ in range(5)]
    for t in threads: t.start()
    for t in threads: t.join()
    print(f"  Counter: {counter} (expected 50000 — race more visible now)")

    sys.setswitchinterval(original)  # restore


# ============================================================
# DEMO 7: Atomic counter using itertools.count
# ============================================================
def demo_itertools_count():
    print("\n" + "=" * 60)
    print("DEMO 7: Atomic counter via itertools.count")
    print("=" * 60)

    counter = count(1)   # itertools.count is C-implemented, GIL-atomic

    ids = []
    def get_id():
        for _ in range(1000):
            ids.append(next(counter))

    threads = [threading.Thread(target=get_id) for _ in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()

    print(f"  Generated {len(ids)} IDs")
    print(f"  Unique IDs: {len(set(ids))}")
    print(f"  All unique: {len(ids) == len(set(ids))} ✅")


# ============================================================
# DEMO 8: thread-local storage
# ============================================================
def demo_thread_local():
    print("\n" + "=" * 60)
    print("DEMO 8: threading.local() for per-thread state")
    print("=" * 60)

    local_data = threading.local()

    def worker(name):
        local_data.user = name        # per-thread variable
        time.sleep(0.01)
        print(f"  Thread {name}: local_data.user = {local_data.user}")

    threads = [threading.Thread(target=worker, args=(f"T{i}",)) for i in range(3)]
    for t in threads: t.start()
    for t in threads: t.join()
    print("  Each thread has isolated `user` ✅")


# ============================================================
# DEMO 9: pytest-style stress test pattern
# ============================================================
def demo_stress_test():
    print("\n" + "=" * 60)
    print("DEMO 9: Stress test pattern (run many times)")
    print("=" * 60)

    races_detected = 0
    for run in range(50):
        counter = 0
        def inc():
            nonlocal counter
            for _ in range(1000):
                counter += 1

        threads = [threading.Thread(target=inc) for _ in range(5)]
        for t in threads: t.start()
        for t in threads: t.join()

        if counter != 5000:
            races_detected += 1

    print(f"  Ran 50 times — race observed in {races_detected} runs")
    print("  In pytest:  pytest --count=50 test_concurrency.py")


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    demo_counter_race()
    demo_toctou()
    demo_singleton_race()
    asyncio.run(demo_async_race())
    demo_queue_pattern()
    demo_switch_interval_detection()
    demo_itertools_count()
    demo_thread_local()
    demo_stress_test()

    print("\n" + "=" * 60)
    print("KEY TAKEAWAYS")
    print("=" * 60)
    print("1. += is NOT atomic — always lock or use atomic primitives")
    print("2. Use double-checked locking for lazy init")
    print("3. asyncio.Lock for async — Lock won't work with await")
    print("4. Prefer queue.Queue / asyncio.Queue over shared state")
    print("5. Move atomicity to DB layer (F expressions, SELECT FOR UPDATE)")
    print("6. Stress test with pytest-repeat to expose races")
