"""
05 — Async & Concurrency: Practical Deep Dive
==============================================
Python Backend Developer Interview Prep | Target: 40 LPA

Usage:
    python 05_async_concurrency.py                # Run all sections
    python 05_async_concurrency.py event_loop     # Section 1
    python 05_async_concurrency.py gather         # Section 2
    python 05_async_concurrency.py semaphore      # Section 3
    python 05_async_concurrency.py queue          # Section 4
    python 05_async_concurrency.py executor       # Section 5
    python 05_async_concurrency.py threading      # Section 6
    python 05_async_concurrency.py multiprocessing # Section 7
    python 05_async_concurrency.py contextvars    # Section 8
    python 05_async_concurrency.py async_gen      # Section 9
    python 05_async_concurrency.py retry          # Section 10

All sections run without external services.
"""

import asyncio
import sys
import time
import random
import threading
import multiprocessing
import os
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed, wait, FIRST_COMPLETED
from contextvars import ContextVar, copy_context
from contextlib import asynccontextmanager
from typing import AsyncIterator, Callable, TypeVar, Awaitable, Any
from dataclasses import dataclass, field
from functools import partial

# ─────────────────────────────────────────────
# Utility helpers
# ─────────────────────────────────────────────

def section_header(title: str) -> None:
    width = 60
    print(f"\n{'═' * width}")
    print(f"  {title}")
    print(f"{'═' * width}\n")


def sub_header(title: str) -> None:
    print(f"\n  ── {title} ──")


# ─────────────────────────────────────────────
# SECTION 1: Event Loop Basics
# ─────────────────────────────────────────────

async def _subtask(n: int) -> str:
    """Simulated subtask with variable delay."""
    await asyncio.sleep(0.05 * n)
    return f"Task-{n} done at t+{0.05 * n:.2f}s"


async def show_event_loop_phases() -> None:
    """
    Demonstrates:
    - get_running_loop() usage
    - loop.time() as monotonic clock
    - create_task() immediate scheduling
    - gather() collecting results
    """
    section_header("SECTION 1 — Event Loop Basics")

    loop = asyncio.get_running_loop()
    print(f"  Running loop  : {type(loop).__name__}")
    print(f"  loop.time()   : {loop.time():.6f}s  (monotonic clock)")
    print(f"  Debug mode    : {loop.get_debug()}")

    sub_header("Task Scheduling — create_task vs direct await")

    # create_task schedules immediately — all 5 are queued before any runs
    t_start = loop.time()
    tasks = [asyncio.create_task(_subtask(i), name=f"sub-{i}") for i in range(6)]
    results = await asyncio.gather(*tasks)
    elapsed = loop.time() - t_start

    for r in results:
        print(f"    {r}")
    print(f"\n  Total time (expected ~0.25s, max delay): {elapsed:.3f}s")

    sub_header("Coroutine vs Task — difference demo")

    # A coroutine object does NOT run until awaited or wrapped in a task
    coro = _subtask(1)          # Just an object — nothing runs
    print(f"  Coroutine object: {coro!r}")

    task = asyncio.create_task(_subtask(1))   # Immediately scheduled
    print(f"  Task object     : {task!r}")
    print(f"  Task done?      : {task.done()}")   # False — still running

    await coro   # Now it runs
    await task   # Now we wait for the task

    print(f"  Task done after await: {task.done()}")  # True

    sub_header("ensure_future() vs create_task()")
    # ensure_future can accept either a coroutine or a Future
    f1 = asyncio.ensure_future(_subtask(1))   # Returns a Task
    t1 = asyncio.create_task(_subtask(1))     # Explicitly a Task
    print(f"  ensure_future type : {type(f1).__name__}")
    print(f"  create_task type   : {type(t1).__name__}")
    await asyncio.gather(f1, t1)


# ─────────────────────────────────────────────
# SECTION 2: gather vs create_task vs wait vs as_completed
# ─────────────────────────────────────────────

async def _mock_api(endpoint: str, delay: float, fail: bool = False) -> str:
    """Simulates an HTTP API call."""
    await asyncio.sleep(delay)
    if fail:
        raise ValueError(f"API error for {endpoint}")
    return f"200 OK [{endpoint}] in {delay:.2f}s"


async def demo_gather_vs_wait() -> None:
    section_header("SECTION 2 — gather / create_task / wait / as_completed")

    delays = [0.30, 0.10, 0.20, 0.15, 0.25]
    endpoints = [f"/api/v1/item/{i}" for i in range(5)]

    # ── 2a: gather — all at once ──────────────────────────
    sub_header("2a: asyncio.gather() — all concurrent")
    t0 = time.perf_counter()
    results = await asyncio.gather(*[
        _mock_api(ep, d) for ep, d in zip(endpoints, delays)
    ])
    print(f"  gather() completed in {time.perf_counter()-t0:.3f}s (max delay = 0.30s)")
    for r in results:
        print(f"    {r}")

    # ── 2b: gather with return_exceptions ─────────────────
    sub_header("2b: gather(return_exceptions=True) — partial failure")
    results = await asyncio.gather(
        _mock_api("/good-1", 0.1),
        _mock_api("/fail",   0.05, fail=True),
        _mock_api("/good-2", 0.15),
        return_exceptions=True,
    )
    for r in results:
        if isinstance(r, Exception):
            print(f"    EXCEPTION: {r}")
        else:
            print(f"    OK: {r}")

    # ── 2c: create_task — individual cancel ───────────────
    sub_header("2c: create_task() — cancel one mid-flight")
    t1 = asyncio.create_task(_mock_api("/slow", 0.50), name="slow-task")
    t2 = asyncio.create_task(_mock_api("/fast", 0.10), name="fast-task")

    await asyncio.sleep(0.20)          # fast-task done, slow-task still running
    t1.cancel()                         # Cancel the slow one

    for task in [t1, t2]:
        try:
            r = await task
            print(f"    {task.get_name()}: {r}")
        except asyncio.CancelledError:
            print(f"    {task.get_name()}: CANCELLED ✓")

    # ── 2d: asyncio.wait with FIRST_COMPLETED ─────────────
    sub_header("2d: asyncio.wait(FIRST_COMPLETED)")
    task_set = {
        asyncio.create_task(_mock_api(ep, d), name=ep)
        for ep, d in zip(endpoints, delays)
    }
    done, pending = await asyncio.wait(task_set, return_when=asyncio.FIRST_COMPLETED)
    first = list(done)[0]
    print(f"  First completed: {first.get_name()} → {first.result()}")
    print(f"  Still pending  : {len(pending)} tasks")

    # Cancel the rest to keep output clean
    for p in pending:
        p.cancel()
    await asyncio.gather(*pending, return_exceptions=True)

    # ── 2e: as_completed — stream results ─────────────────
    sub_header("2e: asyncio.as_completed() — streaming results")
    coros = [_mock_api(ep, d) for ep, d in zip(endpoints, delays)]
    t0 = time.perf_counter()
    for coro in asyncio.as_completed(coros):
        result = await coro
        print(f"    +{time.perf_counter()-t0:.3f}s → {result}")

    print("\n  Note: results appear in completion order, not input order")


# ─────────────────────────────────────────────
# SECTION 3: Semaphore — Rate Limiting
# ─────────────────────────────────────────────

async def _rate_limited_fetch(semaphore: asyncio.Semaphore, item_id: int) -> str:
    async with semaphore:
        await asyncio.sleep(0.10)    # Simulate 100ms API call
        return f"fetched-{item_id}"


async def demo_semaphore() -> None:
    section_header("SECTION 3 — Semaphore (Rate Limiting / Concurrency Cap)")

    TOTAL = 20

    sub_header("Without semaphore — all 20 fire simultaneously")
    t0 = time.perf_counter()
    await asyncio.gather(*[asyncio.sleep(0.10) for _ in range(TOTAL)])
    print(f"  20 tasks (no limit)  : {time.perf_counter()-t0:.3f}s  ← all at once")

    sub_header("With Semaphore(5) — max 5 concurrent")
    sem = asyncio.Semaphore(5)
    t0 = time.perf_counter()
    results = await asyncio.gather(*[_rate_limited_fetch(sem, i) for i in range(TOTAL)])
    elapsed = time.perf_counter() - t0
    print(f"  20 tasks (limit=5)   : {elapsed:.3f}s  ← 4 batches × 0.10s ≈ 0.40s")
    print(f"  Sample results       : {results[:5]}...")

    sub_header("Semaphore as connection pool limiter")
    db_pool = asyncio.Semaphore(3)    # Max 3 DB connections

    async def db_query(qid: int) -> str:
        async with db_pool:
            acquired_at = time.perf_counter()
            await asyncio.sleep(0.05)
            return f"Q{qid} done (waited {time.perf_counter() - acquired_at:.3f}s in pool)"

    t0 = time.perf_counter()
    qresults = await asyncio.gather(*[db_query(i) for i in range(9)])
    print(f"  9 queries, pool=3: {time.perf_counter()-t0:.3f}s (expected ~0.15s)")
    for r in qresults:
        print(f"    {r}")


# ─────────────────────────────────────────────
# SECTION 4: Producer-Consumer Queue
# ─────────────────────────────────────────────

async def _producer(queue: asyncio.Queue, items: list, producer_id: int) -> None:
    for item in items:
        await queue.put(item)
        print(f"  [Producer-{producer_id}] put: {item!r}")
        await asyncio.sleep(0.02)
    await queue.put(None)    # Sentinel — this producer is done
    print(f"  [Producer-{producer_id}] sent sentinel")


async def _consumer(queue: asyncio.Queue, consumer_id: int, results: list) -> None:
    processed = 0
    while True:
        item = await queue.get()
        if item is None:
            queue.task_done()
            print(f"  [Consumer-{consumer_id}] got sentinel, exiting")
            break
        await asyncio.sleep(0.01)    # Simulate processing (faster than producer)
        result = f"{item}_processed"
        results.append(result)
        processed += 1
        queue.task_done()
    print(f"  [Consumer-{consumer_id}] handled {processed} items")


async def demo_queue() -> None:
    section_header("SECTION 4 — Producer-Consumer Queue")

    sub_header("Single producer, 3 consumers")
    queue: asyncio.Queue = asyncio.Queue(maxsize=5)   # Bounded buffer
    results: list = []

    items = [f"task-{i}" for i in range(9)]
    # 1 producer puts 9 items, 3 consumers each handle their share + 1 sentinel each
    # We need 3 sentinels (one per consumer)
    sentinel_queue: asyncio.Queue = asyncio.Queue(maxsize=5)

    # Custom producer that puts N sentinels
    async def multi_sentinel_producer(q: asyncio.Queue, items: list, num_consumers: int) -> None:
        for item in items:
            await q.put(item)
            await asyncio.sleep(0.02)
        for _ in range(num_consumers):
            await q.put(None)   # One sentinel per consumer

    t0 = time.perf_counter()
    await asyncio.gather(
        multi_sentinel_producer(queue, items, 3),
        _consumer(queue, 1, results),
        _consumer(queue, 2, results),
        _consumer(queue, 3, results),
    )

    print(f"\n  Total items processed : {len(results)}")
    print(f"  Time                  : {time.perf_counter()-t0:.3f}s")
    print(f"  Sample results        : {sorted(results)[:5]}...")

    sub_header("PriorityQueue — process high-priority first")
    pq: asyncio.PriorityQueue = asyncio.PriorityQueue()

    # (priority, task_name) — lower number = higher priority
    for priority, name in [(3, "low"), (1, "critical"), (2, "medium"), (1, "also-critical")]:
        await pq.put((priority, name))

    print("  Processing in priority order:")
    while not pq.empty():
        prio, name = await pq.get()
        print(f"    Priority {prio}: {name}")
        pq.task_done()

    sub_header("LIFO Queue — stack behaviour")
    lq: asyncio.LifoQueue = asyncio.LifoQueue()
    for i in range(5):
        await lq.put(f"item-{i}")

    print("  LIFO order:")
    while not lq.empty():
        item = await lq.get()
        print(f"    {item}")


# ─────────────────────────────────────────────
# SECTION 5: run_in_executor
# ─────────────────────────────────────────────

def _blocking_io(filename: str) -> str:
    """Simulates a synchronous file/DB read."""
    time.sleep(0.10)
    return f"sync-read({filename})"


def _blocking_cpu(n: int) -> int:
    """CPU-bound computation — no I/O."""
    return sum(i * i for i in range(n))


async def demo_executor() -> None:
    section_header("SECTION 5 — run_in_executor (Thread + Process Pool)")

    loop = asyncio.get_running_loop()

    sub_header("5a: ThreadPoolExecutor for blocking I/O")
    with ThreadPoolExecutor(max_workers=4) as thread_pool:
        t0 = time.perf_counter()
        # Run 4 blocking calls concurrently on separate threads
        results = await asyncio.gather(*[
            loop.run_in_executor(thread_pool, _blocking_io, f"file-{i}.dat")
            for i in range(4)
        ])
        print(f"  4 blocking I/O calls in {time.perf_counter()-t0:.3f}s (expected ~0.10s)")
        for r in results:
            print(f"    {r}")

    sub_header("5b: asyncio.to_thread() — Python 3.9+ shortcut")
    t0 = time.perf_counter()
    results = await asyncio.gather(*[
        asyncio.to_thread(_blocking_io, f"file-{i}.dat")
        for i in range(4)
    ])
    print(f"  4 calls via to_thread in {time.perf_counter()-t0:.3f}s")
    for r in results:
        print(f"    {r}")

    sub_header("5c: ProcessPoolExecutor for CPU-bound work")
    with ProcessPoolExecutor(max_workers=2) as proc_pool:
        t0 = time.perf_counter()
        # Sequential would take ~2x; parallel uses 2 cores
        results = await asyncio.gather(*[
            loop.run_in_executor(proc_pool, _blocking_cpu, 500_000)
            for _ in range(2)
        ])
        print(f"  2 CPU tasks (ProcessPool, 2 workers): {time.perf_counter()-t0:.3f}s")
        print(f"  Results: {results}")

    sub_header("5d: functools.partial for kwargs with run_in_executor")
    def greet(name: str, greeting: str = "Hello") -> str:
        time.sleep(0.05)
        return f"{greeting}, {name}!"

    fn = partial(greet, "Ashish", greeting="Namaste")
    result = await loop.run_in_executor(None, fn)
    print(f"  partial result: {result}")

    sub_header("5e: Comparing blocking vs non-blocking in event loop")

    async def measure(label: str, coro):
        t0 = time.perf_counter()
        r = await coro
        print(f"  {label}: {time.perf_counter()-t0:.3f}s  → {r!r}")

    await measure("asyncio.sleep (non-blocking)", asyncio.sleep(0.10))
    await measure("to_thread(sleep) (offloaded)", asyncio.to_thread(time.sleep, 0.10))


# ─────────────────────────────────────────────
# SECTION 6: Threading Patterns
# ─────────────────────────────────────────────

def _thread_worker(n: int, results: list, lock: threading.Lock) -> None:
    time.sleep(0.05)
    with lock:
        results.append(n * n)


def demo_threading() -> None:
    section_header("SECTION 6 — Threading Patterns")

    sub_header("6a: threading.Thread with Lock")
    results: list = []
    lock = threading.Lock()

    threads = [
        threading.Thread(target=_thread_worker, args=(i, results, lock))
        for i in range(10)
    ]
    t0 = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    print(f"  10 threads in {time.perf_counter()-t0:.3f}s")
    print(f"  Sorted results: {sorted(results)}")

    sub_header("6b: ThreadPoolExecutor.map() — cleaner API")
    def compute(n: int) -> int:
        time.sleep(0.05)
        return n * n

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=5) as executor:
        results2 = list(executor.map(compute, range(10)))
    print(f"  executor.map in {time.perf_counter()-t0:.3f}s")
    print(f"  Results: {results2}")

    sub_header("6c: ThreadPoolExecutor.submit() + as_completed()")
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_map = {executor.submit(compute, i): i for i in range(10)}
        ordered_by_completion = []
        for future in as_completed(future_map):
            original_arg = future_map[future]
            ordered_by_completion.append((original_arg, future.result()))

    print(f"  as_completed in {time.perf_counter()-t0:.3f}s")
    print(f"  Completion order (arg, result): {ordered_by_completion[:5]}...")

    sub_header("6d: threading.local() — per-thread storage")
    local_data = threading.local()

    def process_in_thread(request_id: str) -> None:
        local_data.request_id = request_id
        local_data.user = f"user_{request_id}"
        time.sleep(0.01)
        # Even after sleep, still our own value
        print(f"    Thread [{threading.current_thread().name}] "
              f"request_id={local_data.request_id}, user={local_data.user}")

    threads = [
        threading.Thread(
            target=process_in_thread,
            args=(f"REQ-{i:03d}",),
            name=f"T{i}"
        )
        for i in range(5)
    ]
    for t in threads: t.start()
    for t in threads: t.join()

    sub_header("6e: threading.Event — signal between threads")
    ready_event = threading.Event()

    def waiter_fn(eid: int) -> None:
        ready_event.wait()   # Block until set
        print(f"    Waiter-{eid} unblocked!")

    def setter_fn() -> None:
        time.sleep(0.15)
        print("    Setting event...")
        ready_event.set()

    threads = [threading.Thread(target=waiter_fn, args=(i,)) for i in range(3)]
    setter = threading.Thread(target=setter_fn)
    for t in threads: t.start()
    setter.start()
    for t in threads: t.join()
    setter.join()

    sub_header("6f: threading.Semaphore — limit concurrent threads")
    db_sem = threading.Semaphore(2)   # Max 2 concurrent DB connections

    def db_op(tid: int) -> None:
        with db_sem:
            print(f"    Thread {tid}: acquired DB connection")
            time.sleep(0.1)
            print(f"    Thread {tid}: released DB connection")

    threads = [threading.Thread(target=db_op, args=(i,)) for i in range(5)]
    t0 = time.perf_counter()
    for t in threads: t.start()
    for t in threads: t.join()
    print(f"  5 threads, semaphore(2): {time.perf_counter()-t0:.3f}s")


# ─────────────────────────────────────────────
# SECTION 7: Multiprocessing Pool
# ─────────────────────────────────────────────
# Note: Process targets must be module-level functions for pickle (spawn mode)

def _ipc_producer(q: multiprocessing.Queue, items: list) -> None:
    """Put items into queue, then send sentinel None."""
    for item in items:
        q.put(item)
    q.put(None)   # sentinel — signals consumer to stop


def _ipc_consumer(in_q: multiprocessing.Queue, out_q: multiprocessing.Queue) -> None:
    """Read items from in_q, double them, put in out_q."""
    while True:
        item = in_q.get()
        if item is None:
            break
        out_q.put(item * 2)


def _cpu_heavy(n: int) -> int:
    """CPU-bound: sum of squares up to n."""
    return sum(i * i for i in range(n))


def _add(a: int, b: int) -> int:
    return a + b


def demo_multiprocessing_pool() -> None:
    section_header("SECTION 7 — Multiprocessing Pool")

    N = 6          # Number of tasks
    SIZE = 200_000  # Size of each computation

    sub_header("7a: Sequential baseline")
    t0 = time.perf_counter()
    seq_results = [_cpu_heavy(SIZE) for _ in range(N)]
    seq_time = time.perf_counter() - t0
    print(f"  Sequential ({N} tasks, n={SIZE}): {seq_time:.3f}s")
    print(f"  Result[0]: {seq_results[0]}")

    sub_header("7b: ProcessPoolExecutor — parallel")
    cpu_count = multiprocessing.cpu_count()
    workers = min(4, cpu_count)
    print(f"  CPU count: {cpu_count}, using {workers} workers")

    t0 = time.perf_counter()
    with ProcessPoolExecutor(max_workers=workers) as executor:
        par_results = list(executor.map(_cpu_heavy, [SIZE] * N))
    par_time = time.perf_counter() - t0
    speedup = seq_time / par_time if par_time > 0 else float('inf')
    print(f"  Parallel   ({N} tasks, n={SIZE}): {par_time:.3f}s  (speedup: {speedup:.2f}x)")
    print(f"  Results match: {seq_results == par_results}")

    sub_header("7c: Pool.submit() with as_completed()")
    t0 = time.perf_counter()
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_cpu_heavy, SIZE + i * 1000): i for i in range(N)}
        for future in as_completed(futures):
            task_id = futures[future]
            result = future.result()
            print(f"    Task {task_id} completed: result={result}")
    print(f"  as_completed time: {time.perf_counter()-t0:.3f}s")

    sub_header("7d: starmap equivalent with multiple args")
    arg_pairs = [(i * 1000, i * 2000) for i in range(1, 5)]
    with ProcessPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(_add, a, b) for a, b in arg_pairs]
        results = [f.result() for f in futures]
    print(f"  Multi-arg results: {results}")

    sub_header("7e: multiprocessing.Queue IPC demo")
    work_q: multiprocessing.Queue = multiprocessing.Queue()
    result_q: multiprocessing.Queue = multiprocessing.Queue()
    items = list(range(8))

    # Use module-level functions — required for pickle with spawn start method
    p1 = multiprocessing.Process(target=_ipc_producer, args=(work_q, items))
    p2 = multiprocessing.Process(target=_ipc_consumer, args=(work_q, result_q))

    p1.start(); p2.start()
    p1.join(); p2.join()

    ipc_results = []
    while not result_q.empty():
        ipc_results.append(result_q.get())

    print(f"  IPC results (items * 2): {sorted(ipc_results)}")


# ─────────────────────────────────────────────
# SECTION 8: contextvars
# ─────────────────────────────────────────────

# Module-level ContextVars
request_id: ContextVar[str] = ContextVar('request_id', default='<no-request>')
user_id: ContextVar[int] = ContextVar('user_id', default=0)
trace_id: ContextVar[str] = ContextVar('trace_id', default='<no-trace>')


async def _log_middleware() -> None:
    """Reads context vars without receiving them as params."""
    rid = request_id.get()
    uid = user_id.get()
    tid = trace_id.get()
    await asyncio.sleep(0.01)
    # Simulate log entry
    print(f"    [LOG] request={rid}, user={uid}, trace={tid}")


async def _do_db_work() -> str:
    """Nested async call — still sees the parent context."""
    await asyncio.sleep(0.02)
    return f"DB row for request={request_id.get()}"


async def _process_one_request(req: str, uid: int, tid: str) -> str:
    """Simulates one HTTP request handler."""
    tok_r = request_id.set(req)
    tok_u = user_id.set(uid)
    tok_t = trace_id.set(tid)
    try:
        await _log_middleware()
        result = await _do_db_work()
        return result
    finally:
        request_id.reset(tok_r)
        user_id.reset(tok_u)
        trace_id.reset(tok_t)


async def demo_contextvars() -> None:
    section_header("SECTION 8 — contextvars (Per-Request Context)")

    sub_header("8a: 5 concurrent requests with isolated context")
    requests_data = [
        (f"req-{i:04d}", i * 100, f"trace-{i:08x}")
        for i in range(1, 6)
    ]

    results = await asyncio.gather(*[
        _process_one_request(req, uid, tid)
        for req, uid, tid in requests_data
    ])

    print(f"\n  Results:")
    for r in results:
        print(f"    {r}")

    print(f"\n  request_id after all tasks: {request_id.get()!r}  (unchanged in main)")

    sub_header("8b: copy_context() — background task inherits context")

    async def background_job() -> None:
        # Inherits the context from when copy_context() was called
        inherited = request_id.get()
        print(f"    [BG] Inherited request_id: {inherited!r}")
        request_id.set("bg-overridden")
        print(f"    [BG] After set: {request_id.get()!r}")

    tok = request_id.set("parent-req-999")
    print(f"  Parent context: {request_id.get()!r}")

    ctx = copy_context()
    task = asyncio.create_task(ctx.run(background_job))
    await task

    print(f"  Parent context after BG task: {request_id.get()!r}  (isolated!)")
    request_id.reset(tok)

    sub_header("8c: ContextVar.get() with default vs no default")
    optional_var: ContextVar[str] = ContextVar('optional')
    print(f"  .get() with no default raises LookupError:")
    try:
        optional_var.get()
    except LookupError as e:
        print(f"    LookupError raised as expected: {e}")

    print(f"  .get(default) returns default: {optional_var.get('fallback')!r}")


# ─────────────────────────────────────────────
# SECTION 9: Async Generator + Context Manager
# ─────────────────────────────────────────────

async def async_range(start: int, stop: int, delay: float = 0.05) -> AsyncIterator[int]:
    """Async generator — yields integers with a simulated async delay."""
    for i in range(start, stop):
        await asyncio.sleep(delay)
        yield i


async def _paginated_data(total_pages: int) -> AsyncIterator[dict]:
    """Simulates a paginated API — fetches one page at a time."""
    for page in range(1, total_pages + 1):
        await asyncio.sleep(0.03)   # Simulate network call
        yield {
            "page": page,
            "items": [f"item_{page}_{j}" for j in range(3)],
        }


@asynccontextmanager
async def managed_connection(url: str):
    """Async context manager — simulates a DB/cache connection."""
    print(f"  [CONN] Connecting to {url!r}...")
    await asyncio.sleep(0.02)
    conn = {"url": url, "status": "open", "queries": 0}
    print(f"  [CONN] Connected.")
    try:
        yield conn
    except Exception as e:
        print(f"  [CONN] Error during connection use: {e}")
        raise
    finally:
        conn["status"] = "closed"
        print(f"  [CONN] Disconnected from {url!r} ({conn['queries']} queries)")


class AsyncDBPool:
    """Manual __aenter__ / __aexit__ implementation."""

    def __init__(self, dsn: str, pool_size: int = 5):
        self.dsn = dsn
        self.pool_size = pool_size
        self._pool: list = []

    async def __aenter__(self) -> "AsyncDBPool":
        print(f"  [POOL] Opening pool (size={self.pool_size}) → {self.dsn}")
        await asyncio.sleep(0.02)
        self._pool = [{"id": i, "status": "idle"} for i in range(self.pool_size)]
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        print(f"  [POOL] Closing {len(self._pool)} connections...")
        await asyncio.sleep(0.01)
        return False    # Do not suppress exceptions

    async def query(self, sql: str) -> dict:
        conn = next(c for c in self._pool if c["status"] == "idle")
        conn["status"] = "busy"
        await asyncio.sleep(0.01)
        conn["status"] = "idle"
        return {"sql": sql, "rows": 42}


async def demo_async_gen() -> None:
    section_header("SECTION 9 — Async Generators & Context Managers")

    sub_header("9a: async for over async_range()")
    collected = []
    async for val in async_range(0, 5, delay=0.02):
        collected.append(val)
    print(f"  async_range(0, 5): {collected}")

    sub_header("9b: Async list comprehension")
    squares = [v * v async for v in async_range(1, 6, delay=0.01)]
    print(f"  [v*v async for v in async_range(1,6)]: {squares}")

    sub_header("9c: Async generator — paginated API")
    all_items = []
    async for page in _paginated_data(4):
        all_items.extend(page["items"])
        print(f"  Page {page['page']}: {page['items']}")
    print(f"  Total items collected: {len(all_items)}")

    sub_header("9d: @asynccontextmanager usage")
    async with managed_connection("redis://localhost:6379/0") as conn:
        for _ in range(3):
            conn["queries"] += 1
            await asyncio.sleep(0.01)
        print(f"  Connection object: {conn}")

    sub_header("9e: Manual __aenter__/__aexit__ pool")
    async with AsyncDBPool("postgresql://localhost/dev", pool_size=3) as pool:
        result = await pool.query("SELECT * FROM users LIMIT 10")
        print(f"  Query result: {result}")

    sub_header("9f: Nested async context managers")
    async with managed_connection("db://primary") as primary:
        async with managed_connection("db://replica") as replica:
            primary["queries"] += 1
            replica["queries"] += 2
            print(f"  Primary: {primary}")
            print(f"  Replica: {replica}")


# ─────────────────────────────────────────────
# SECTION 10: Async Retry with Exponential Backoff
# ─────────────────────────────────────────────

T = TypeVar('T')


async def with_retry(
    coro_fn: Callable[[], Awaitable[T]],
    max_retries: int = 4,
    base_delay: float = 0.05,
    max_delay: float = 2.0,
    jitter: float = 0.02,
    exceptions: tuple = (Exception,),
) -> T:
    """
    Exponential backoff retry with jitter.
    Delay = min(base * 2^attempt + random(0, jitter), max_delay)
    """
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            return await coro_fn()
        except exceptions as e:
            last_exc = e
            if attempt == max_retries - 1:
                print(f"  [RETRY] Attempt {attempt + 1}/{max_retries} FAILED: {e} — giving up.")
                raise
            delay = min(
                base_delay * (2 ** attempt) + random.uniform(0, jitter),
                max_delay,
            )
            print(f"  [RETRY] Attempt {attempt + 1}/{max_retries} failed: {e!r}. "
                  f"Retrying in {delay:.3f}s...")
            await asyncio.sleep(delay)

    raise RuntimeError("Unreachable")


async def demo_retry() -> None:
    section_header("SECTION 10 — Async Retry with Exponential Backoff")

    sub_header("10a: Transient failure that eventually succeeds")
    call_count = 0

    async def flaky_api() -> str:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionError(f"Server unavailable (attempt {call_count})")
        return f"Success on attempt {call_count}!"

    call_count = 0
    t0 = time.perf_counter()
    result = await with_retry(flaky_api, max_retries=5, base_delay=0.05)
    print(f"  Result  : {result}")
    print(f"  Time    : {time.perf_counter()-t0:.3f}s")

    sub_header("10b: Permanent failure exhausts retries")
    async def always_fails() -> str:
        raise TimeoutError("Service down")

    try:
        await with_retry(always_fails, max_retries=3, base_delay=0.03)
    except TimeoutError as e:
        print(f"  Caught expected exception: {e!r}")

    sub_header("10c: Retry only specific exceptions")
    attempt_c = 0

    async def sometimes_value_error() -> str:
        nonlocal attempt_c
        attempt_c += 1
        if attempt_c == 1:
            raise ConnectionError("network blip")
        if attempt_c == 2:
            raise ValueError("bad input")  # Not retried
        return "ok"

    attempt_c = 0
    try:
        result = await with_retry(
            sometimes_value_error,
            max_retries=4,
            base_delay=0.02,
            exceptions=(ConnectionError,),   # Only retry ConnectionError
        )
        print(f"  Result: {result}")
    except ValueError as e:
        print(f"  ValueError not retried, propagated: {e!r}")

    sub_header("10d: asyncio.wait_for with retry (timeout per attempt)")
    attempt_d = 0

    async def slow_then_fast() -> str:
        nonlocal attempt_d
        attempt_d += 1
        delay = 0.20 if attempt_d <= 1 else 0.05   # First attempt is slow
        await asyncio.sleep(delay)
        return f"done in {delay}s"

    attempt_d = 0
    async def timed_call() -> str:
        return await asyncio.wait_for(slow_then_fast(), timeout=0.10)

    try:
        result = await with_retry(timed_call, max_retries=3, base_delay=0.02,
                                   exceptions=(asyncio.TimeoutError,))
        print(f"  With timeout+retry: {result!r}")
    except asyncio.TimeoutError:
        print("  All attempts timed out")

    sub_header("10e: Cancellation demo — CancelledError handling")
    cleaned_up = False

    async def cancellable_work() -> None:
        nonlocal cleaned_up
        try:
            for i in range(10):
                print(f"    Working... step {i}")
                await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            print("    CancelledError caught — running cleanup")
            cleaned_up = True
            raise   # MUST re-raise

    task = asyncio.create_task(cancellable_work())
    await asyncio.sleep(0.12)   # Let it run 2-3 steps
    task.cancel()

    try:
        await task
    except asyncio.CancelledError:
        print(f"  Task confirmed cancelled. cleaned_up={cleaned_up}")

    sub_header("10f: asyncio.shield — protect critical section")
    saved = False

    async def critical_save(data: str) -> None:
        nonlocal saved
        await asyncio.sleep(0.10)   # Simulate DB write
        saved = True
        print(f"    SAVED: {data!r}")

    async def outer_handler() -> None:
        await asyncio.shield(critical_save("payment-txn-42"))

    task = asyncio.create_task(outer_handler())
    await asyncio.sleep(0.03)   # Cancel before critical_save finishes
    task.cancel()

    try:
        await task
    except asyncio.CancelledError:
        print(f"  Outer task cancelled")

    await asyncio.sleep(0.20)   # Wait for shielded task to complete
    print(f"  saved={saved}  ← critical_save still ran despite outer cancel!")


# ─────────────────────────────────────────────
# SECTION DISPATCHER
# ─────────────────────────────────────────────

ASYNC_SECTIONS: dict[str, Callable] = {
    "event_loop":       show_event_loop_phases,
    "gather":           demo_gather_vs_wait,
    "semaphore":        demo_semaphore,
    "queue":            demo_queue,
    "executor":         demo_executor,
    "async_gen":        demo_async_gen,
    "retry":            demo_retry,
    "contextvars":      demo_contextvars,
}

SYNC_SECTIONS: dict[str, Callable] = {
    "threading":        demo_threading,
    "multiprocessing":  demo_multiprocessing_pool,
}


async def run_async_sections(names: list[str]) -> None:
    for name in names:
        if name in ASYNC_SECTIONS:
            await ASYNC_SECTIONS[name]()


def run_all(names: list[str]) -> None:
    """Run async sections via asyncio.run(), then sync sections directly."""
    async_names = [n for n in names if n in ASYNC_SECTIONS]
    sync_names  = [n for n in names if n in SYNC_SECTIONS]

    if async_names:
        asyncio.run(run_async_sections(async_names))

    for name in sync_names:
        SYNC_SECTIONS[name]()


def main() -> None:
    all_names = list(ASYNC_SECTIONS.keys()) + list(SYNC_SECTIONS.keys())

    if len(sys.argv) == 1:
        # No args — run everything
        requested = all_names
    else:
        requested = sys.argv[1:]
        if requested == ["all"]:
            requested = all_names

    invalid = [n for n in requested if n not in all_names]
    if invalid:
        print(f"Unknown section(s): {invalid}")
        print(f"Available: {all_names}")
        sys.exit(1)

    print("\n" + "╔" + "═" * 58 + "╗")
    print("║  05 — Async & Concurrency Practical Demo" + " " * 17 + "║")
    print("║  Python Backend Developer Interview Prep  40 LPA" + " " * 7 + "║")
    print("╚" + "═" * 58 + "╝")
    print(f"\n  Running sections: {requested}\n")

    run_all(requested)

    print("\n" + "═" * 60)
    print("  All sections complete.")
    print("═" * 60 + "\n")


if __name__ == "__main__":
    # Guard required for multiprocessing on macOS/Windows
    multiprocessing.set_start_method("spawn", force=True)
    main()
