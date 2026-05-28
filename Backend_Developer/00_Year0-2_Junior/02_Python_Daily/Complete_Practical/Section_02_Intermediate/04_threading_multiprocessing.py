"""
╔══════════════════════════════════════════════════════════════╗
║  PYTHON COMPLETE PRACTICAL — Section 02                      ║
║  Topic: Threading, Multiprocessing, concurrent.futures       ║
╚══════════════════════════════════════════════════════════════╝
"""

import threading
import multiprocessing
import concurrent.futures
import queue
import time
import os
from typing import Any, Callable


# ══════════════════════════════════════════════════════════════
# PART A: THREADING
# ══════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────
# 1. BASIC THREADING
# ─────────────────────────────────────────────────────────────

def download_file(url: str, result_dict: dict, key: str) -> None:
    """Simulate file download (I/O-bound)."""
    time.sleep(0.5)   # simulate network I/O
    result_dict[key] = f"Content of {url}"

results: dict[str, str] = {}

# Sequential — 3 × 0.5s = 1.5s
start = time.perf_counter()
for i, url in enumerate(["url1", "url2", "url3"]):
    download_file(url, results, f"file_{i}")
print(f"Sequential: {time.perf_counter()-start:.2f}s")

# Threaded — ~0.5s (all run concurrently)
results.clear()
threads: list[threading.Thread] = []
start = time.perf_counter()

for i, url in enumerate(["url1", "url2", "url3"]):
    t = threading.Thread(
        target=download_file,
        args=(url, results, f"file_{i}"),
        daemon=True,   # daemon threads die with main thread
    )
    t.start()
    threads.append(t)

for t in threads:
    t.join()   # wait for all to complete

print(f"Threaded:   {time.perf_counter()-start:.2f}s")
print(f"Results:    {list(results.keys())}")


# ─────────────────────────────────────────────────────────────
# 2. THREAD-SAFE DATA STRUCTURES
# ─────────────────────────────────────────────────────────────

# Race condition — dangerous
unsafe_counter = 0
lock = threading.Lock()
safe_counter = 0

def increment_safe(n: int) -> None:
    global safe_counter
    for _ in range(n):
        with lock:
            safe_counter += 1   # atomic with lock

def increment_unsafe(n: int) -> None:
    global unsafe_counter
    for _ in range(n):
        unsafe_counter += 1     # NOT atomic — race condition!

# threading.Lock — mutual exclusion
threads = [threading.Thread(target=increment_safe, args=(1000,)) for _ in range(10)]
for t in threads:
    t.start()
for t in threads:
    t.join()
print(f"\nSafe counter: {safe_counter}")    # always 10000

# threading.Event — signal between threads
stop_event = threading.Event()

def worker_with_stop(name: str, event: threading.Event) -> None:
    while not event.is_set():
        print(f"  [{name}] working...")
        time.sleep(0.1)
    print(f"  [{name}] stopped")

# threading.RLock — re-entrant lock (same thread can acquire multiple times)
rlock = threading.RLock()

# threading.Semaphore — limit concurrent access
db_semaphore = threading.Semaphore(3)  # max 3 concurrent DB connections

def access_db(thread_id: int) -> None:
    with db_semaphore:
        print(f"  Thread {thread_id}: using DB connection")
        time.sleep(0.1)


# ─────────────────────────────────────────────────────────────
# 3. THREAD-SAFE QUEUE
# ─────────────────────────────────────────────────────────────

def producer_consumer_demo():
    task_queue: queue.Queue[str | None] = queue.Queue(maxsize=5)
    result_queue: queue.Queue[str] = queue.Queue()

    def producer(n_tasks: int) -> None:
        for i in range(n_tasks):
            task = f"task_{i}"
            task_queue.put(task)   # blocks if full
            print(f"  [PRODUCER] Added: {task}")
        task_queue.put(None)       # sentinel

    def consumer(worker_id: int) -> None:
        while True:
            task = task_queue.get()   # blocks until item available
            if task is None:
                task_queue.put(None)  # pass sentinel to other workers
                break
            time.sleep(0.05)
            result_queue.put(f"result_{task}")
            task_queue.task_done()
            print(f"  [WORKER {worker_id}] Processed: {task}")

    p = threading.Thread(target=producer, args=(6,))
    workers = [threading.Thread(target=consumer, args=(i,)) for i in range(3)]

    p.start()
    for w in workers:
        w.start()

    p.join()
    for w in workers:
        w.join()

    results = []
    while not result_queue.empty():
        results.append(result_queue.get())
    print(f"  Results: {len(results)} tasks processed")

print("\nProducer/Consumer:")
producer_consumer_demo()


# ══════════════════════════════════════════════════════════════
# PART B: MULTIPROCESSING
# ══════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────
# 4. WHY MULTIPROCESSING FOR CPU-BOUND
# ─────────────────────────────────────────────────────────────

def cpu_bound_task(n: int) -> int:
    """CPU-intensive — blocked by GIL with threading."""
    return sum(i * i for i in range(n))


# Multiprocessing bypasses GIL — true parallelism
if __name__ == "__main__":  # REQUIRED for multiprocessing
    numbers = [5_000_000, 5_000_000, 5_000_000, 5_000_000]

    # Sequential
    start = time.perf_counter()
    results = [cpu_bound_task(n) for n in numbers]
    seq_time = time.perf_counter() - start
    print(f"\nSequential CPU: {seq_time:.2f}s")

    # Multiprocessing Pool
    start = time.perf_counter()
    with multiprocessing.Pool(processes=4) as pool:
        results = pool.map(cpu_bound_task, numbers)
    mp_time = time.perf_counter() - start
    print(f"Multiprocessing: {mp_time:.2f}s (speedup: {seq_time/mp_time:.1f}x)")


# ─────────────────────────────────────────────────────────────
# 5. PROCESS — basic usage
# ─────────────────────────────────────────────────────────────

def process_worker(name: str, shared_dict, lock) -> None:
    """Runs in separate process."""
    time.sleep(0.1)
    with lock:
        shared_dict[name] = f"result from {name} (PID: {os.getpid()})"

if __name__ == "__main__":
    manager = multiprocessing.Manager()
    shared = manager.dict()    # shared dict between processes
    mp_lock = manager.Lock()   # shared lock

    processes = [
        multiprocessing.Process(
            target=process_worker,
            args=(f"proc_{i}", shared, mp_lock)
        )
        for i in range(3)
    ]

    for p in processes:
        p.start()
    for p in processes:
        p.join()

    print(f"\nProcess results: {dict(shared)}")


# ─────────────────────────────────────────────────────────────
# 6. MULTIPROCESSING QUEUE
# ─────────────────────────────────────────────────────────────

def mp_worker(task_q: multiprocessing.Queue, result_q: multiprocessing.Queue) -> None:
    while True:
        task = task_q.get()
        if task is None:
            break
        result = cpu_bound_task(task)
        result_q.put(result)


# ══════════════════════════════════════════════════════════════
# PART C: concurrent.futures — CLEANEST API
# ══════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────
# 7. ThreadPoolExecutor — I/O-bound
# ─────────────────────────────────────────────────────────────

def fetch_url(url: str) -> str:
    """Simulate HTTP request."""
    time.sleep(0.3)
    return f"Response from {url}"

urls = ["https://api1.com", "https://api2.com", "https://api3.com", "https://api4.com"]

print("\n=== ThreadPoolExecutor ===")
start = time.perf_counter()

with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
    # map — submit all, returns results in order
    results = list(executor.map(fetch_url, urls))

elapsed = time.perf_counter() - start
print(f"4 URLs in {elapsed:.2f}s: {[r[:20] for r in results]}")


# submit — individual futures
print("\n=== submit() with futures ===")
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
    futures = {executor.submit(fetch_url, url): url for url in urls}

    for future in concurrent.futures.as_completed(futures):
        url = futures[future]
        try:
            result = future.result(timeout=5)
            print(f"  {url}: {result[:25]}")
        except Exception as e:
            print(f"  {url}: FAILED — {e}")


# ─────────────────────────────────────────────────────────────
# 8. ProcessPoolExecutor — CPU-bound
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n=== ProcessPoolExecutor ===")
    numbers = [3_000_000, 3_000_000, 3_000_000, 3_000_000]

    start = time.perf_counter()
    with concurrent.futures.ProcessPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(cpu_bound_task, numbers))
    elapsed = time.perf_counter() - start
    print(f"CPU work in {elapsed:.2f}s: first result = {results[0]}")


# ─────────────────────────────────────────────────────────────
# 9. PRODUCTION PATTERN — async + executor
# ─────────────────────────────────────────────────────────────

import asyncio

async def async_with_thread_pool():
    """
    Run blocking I/O in thread pool without blocking event loop.
    Used when library doesn't support async (e.g., boto3, some DB drivers).
    """
    loop = asyncio.get_event_loop()

    def blocking_io(n: int) -> str:
        time.sleep(0.1)  # blocking — would freeze event loop if awaited directly
        return f"Blocking result {n}"

    # run_in_executor — thread pool by default
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        tasks = [
            loop.run_in_executor(pool, blocking_io, i)
            for i in range(5)
        ]
        results = await asyncio.gather(*tasks)

    print(f"\nAsync+threads: {results}")

asyncio.run(async_with_thread_pool())


# ─────────────────────────────────────────────────────────────
# INTERVIEW SUMMARY
# ─────────────────────────────────────────────────────────────
"""
GIL (Global Interpreter Lock):
  CPython allows only 1 thread to execute Python bytecode at a time.
  Released during I/O operations and C extensions.
  Affects: CPU-bound threading (no speedup), not I/O-bound.

┌─────────────────────┬──────────────────────────────────────────┐
│ Tool                │ When to Use                              │
├─────────────────────┼──────────────────────────────────────────┤
│ asyncio             │ I/O-bound, async-compatible libraries     │
│ ThreadPoolExecutor  │ I/O-bound, legacy blocking libraries      │
│ ProcessPoolExecutor │ CPU-bound (ML inference, data processing) │
│ multiprocessing.Pool│ Same as ProcessPoolExecutor (lower-level) │
└─────────────────────┴──────────────────────────────────────────┘

Thread safety tools:
  threading.Lock()      — mutual exclusion (non-reentrant)
  threading.RLock()     — reentrant lock (same thread can acquire again)
  threading.Event()     — signal between threads (set/wait)
  threading.Semaphore() — limit concurrent access count
  queue.Queue()         — thread-safe FIFO (use for producer/consumer)
  concurrent.futures    — highest-level API, use this in production

For Agentic AI:
  LLM API calls → asyncio (they're async I/O)
  ML inference  → ProcessPoolExecutor (CPU-bound)
  Legacy APIs   → ThreadPoolExecutor + run_in_executor
"""
