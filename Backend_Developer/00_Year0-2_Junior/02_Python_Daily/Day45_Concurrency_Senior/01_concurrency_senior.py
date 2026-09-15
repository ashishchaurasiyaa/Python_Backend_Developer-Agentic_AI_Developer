"""
DAY 51 — Senior Concurrency: ThreadPoolExecutor, ProcessPoolExecutor, Patterns
Architecture Level: Senior Python Backend + Agentic AI

THE THREE MODELS:
  threading     → I/O-bound, GIL-limited, same process memory
  multiprocessing → CPU-bound, bypasses GIL, separate memory
  asyncio       → I/O-bound, single thread, highest throughput for network I/O

THIS FILE focuses on PRODUCTION patterns you use in:
  - FastAPI background tasks
  - Agentic AI parallel tool calls
  - Data pipeline workers
  - LLM batch processing
"""

import asyncio
import concurrent.futures
import multiprocessing
import os
import threading
import time
from typing import Callable, TypeVar

T = TypeVar("T")


# ═══════════════════════════════════════════════════════
# PART A: The GIL — What It Means Practically
# ═══════════════════════════════════════════════════════

# ─────────────────────────────────────────────
# 1. GIL = Global Interpreter Lock
#    - Only ONE Python thread executes Python bytecode at a time
#    - Released during I/O (file, network, sleep) → threading works for I/O
#    - NEVER released for CPU computation → threading useless for CPU work
# ─────────────────────────────────────────────

def cpu_task(n: int) -> int:
    """CPU-bound: sum squares. GIL stays locked."""
    return sum(i * i for i in range(n))

def io_task(seconds: float) -> str:
    """I/O-bound: sleep releases GIL — threads run concurrently."""
    time.sleep(seconds)
    return f"done after {seconds}s"


# ─────────────────────────────────────────────
# 2. Decision Table
# ─────────────────────────────────────────────
#
# ┌─────────────────────────────┬───────────────────────────────┐
# │ Workload                    │ Use                           │
# ├─────────────────────────────┼───────────────────────────────┤
# │ Network I/O (APIs, DBs)     │ asyncio (best) or threading   │
# │ File I/O                    │ asyncio or threading          │
# │ CPU computation (ML, image) │ multiprocessing               │
# │ Mixed I/O + CPU             │ asyncio + ProcessPoolExecutor │
# │ Calling blocking libs       │ run_in_executor(thread)       │
# │ Parallel LLM calls          │ asyncio.gather                │
# └─────────────────────────────┴───────────────────────────────┘


# ═══════════════════════════════════════════════════════
# PART B: ThreadPoolExecutor — Production Patterns
# ═══════════════════════════════════════════════════════

# ─────────────────────────────────────────────
# 1. Basic usage
# ─────────────────────────────────────────────

def fetch_user(user_id: int) -> dict:
    """Simulate blocking I/O call (e.g., legacy sync SDK)."""
    time.sleep(0.05)
    return {"id": user_id, "name": f"User {user_id}", "thread": threading.current_thread().name}


print("\n=== ThreadPoolExecutor: parallel I/O ===")
start = time.perf_counter()

with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
    futures = [executor.submit(fetch_user, i) for i in range(1, 6)]
    results = [f.result() for f in concurrent.futures.as_completed(futures)]

elapsed = time.perf_counter() - start
print(f"5 users in {elapsed:.3f}s (would be 0.25s sequential)")
print(f"Sample: {results[0]}")


# ─────────────────────────────────────────────
# 2. map() — simpler when order matters
# ─────────────────────────────────────────────

with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
    users = list(executor.map(fetch_user, range(1, 6)))
    # results are IN ORDER (unlike as_completed)


# ─────────────────────────────────────────────
# 3. Exception handling with futures
# ─────────────────────────────────────────────

def risky_task(task_id: int) -> str:
    if task_id == 3:
        raise ValueError(f"Task {task_id} failed")
    time.sleep(0.01)
    return f"Task {task_id} OK"


print("\n=== Exception handling ===")
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
    futures = {executor.submit(risky_task, i): i for i in range(1, 6)}

    for future in concurrent.futures.as_completed(futures):
        task_id = futures[future]
        try:
            result = future.result()
            print(f"  {result}")
        except Exception as e:
            print(f"  Task {task_id} raised: {e}")


# ─────────────────────────────────────────────
# 4. FastAPI pattern: run_in_executor for blocking calls
# ─────────────────────────────────────────────

# Blocking sync function (e.g., legacy library, OpenCV, PDF parsing)
def parse_pdf_sync(file_path: str) -> dict:
    time.sleep(0.1)  # simulate heavy sync work
    return {"pages": 10, "text": "extracted content", "file": file_path}


async def parse_pdf_async(file_path: str) -> dict:
    """Wrap blocking function to not block the event loop."""
    loop = asyncio.get_event_loop()
    # run in thread pool — event loop stays free for other requests
    result = await loop.run_in_executor(None, parse_pdf_sync, file_path)
    return result


# In FastAPI:
# @app.post("/parse-pdf")
# async def parse_pdf_endpoint(file: UploadFile):
#     result = await parse_pdf_async(file.filename)
#     return result

print("\n=== run_in_executor ===")
result = asyncio.run(parse_pdf_async("report.pdf"))
print(f"PDF parsed: {result}")


# ═══════════════════════════════════════════════════════
# PART C: ProcessPoolExecutor — CPU-Bound Work
# ═══════════════════════════════════════════════════════

# ─────────────────────────────────────────────
# 1. When to use: image processing, ML inference, data compression
# ─────────────────────────────────────────────

def compute_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Simulate CPU-heavy embedding computation (e.g., sentence-transformers)."""
    time.sleep(0.1)  # simulate CPU work
    return [[0.1, 0.2, 0.3] for _ in texts]


def process_chunk(chunk: list[str]) -> list[list[float]]:
    """Must be top-level function (not lambda) for multiprocessing."""
    return compute_embeddings_batch(chunk)


print("\n=== ProcessPoolExecutor: CPU-bound ===")

texts = [f"Document {i}" for i in range(16)]
chunks = [texts[i:i+4] for i in range(0, len(texts), 4)]  # 4 chunks of 4

# Use max_workers=cpu_count-1 to leave one core for the OS
cpu_count = os.cpu_count() or 4

start = time.perf_counter()
with concurrent.futures.ProcessPoolExecutor(max_workers=min(4, cpu_count)) as executor:
    chunk_results = list(executor.map(process_chunk, chunks))

embeddings = [emb for batch in chunk_results for emb in batch]
elapsed = time.perf_counter() - start
print(f"16 embeddings in {elapsed:.3f}s across {cpu_count} cores")
print(f"Total embeddings: {len(embeddings)}")


# ─────────────────────────────────────────────
# 2. asyncio + ProcessPoolExecutor (the power combo)
#    Use when: async FastAPI handler needs CPU-heavy work
# ─────────────────────────────────────────────

_process_pool = concurrent.futures.ProcessPoolExecutor(max_workers=2)


async def embed_documents_async(texts: list[str]) -> list[list[float]]:
    """Async wrapper: runs CPU-bound embedding in process pool."""
    loop = asyncio.get_event_loop()
    chunks = [texts[i:i+4] for i in range(0, len(texts), 4)]

    futures = [
        loop.run_in_executor(_process_pool, process_chunk, chunk)
        for chunk in chunks
    ]
    results = await asyncio.gather(*futures)
    return [emb for batch in results for emb in batch]


# Cleanup: always shut down process pool at app shutdown
# @app.on_event("shutdown")
# async def shutdown():
#     _process_pool.shutdown(wait=True)

print("\n=== asyncio + ProcessPoolExecutor ===")
result = asyncio.run(embed_documents_async(texts))
print(f"Async embeddings: {len(result)} vectors")


# ═══════════════════════════════════════════════════════
# PART D: Concurrency Primitives
# ═══════════════════════════════════════════════════════

# ─────────────────────────────────────────────
# 1. threading.Lock vs asyncio.Lock
# ─────────────────────────────────────────────

# threading.Lock — for threads
thread_lock = threading.Lock()
shared_counter = 0

def increment_thread_safe():
    global shared_counter
    with thread_lock:
        shared_counter += 1


# asyncio.Lock — for coroutines
async def demo_async_lock():
    lock = asyncio.Lock()
    counter = {"value": 0}

    async def increment():
        async with lock:
            val = counter["value"]
            await asyncio.sleep(0)  # yield to event loop
            counter["value"] = val + 1

    await asyncio.gather(*[increment() for _ in range(100)])
    print(f"\nasyncio.Lock counter: {counter['value']}")  # always 100


asyncio.run(demo_async_lock())


# ─────────────────────────────────────────────
# 2. asyncio.Semaphore — rate limit concurrent operations
# ─────────────────────────────────────────────

async def demo_semaphore():
    """Limit to 3 concurrent LLM API calls."""
    semaphore = asyncio.Semaphore(3)
    results = []

    async def call_llm(i: int) -> str:
        async with semaphore:  # at most 3 at a time
            await asyncio.sleep(0.05)  # simulate API latency
            return f"response_{i}"

    results = await asyncio.gather(*[call_llm(i) for i in range(10)])
    print(f"\nSemaphore: {len(results)} results, max 3 concurrent")

asyncio.run(demo_semaphore())


# ─────────────────────────────────────────────
# 3. asyncio.Queue — producer/consumer pattern (agents)
# ─────────────────────────────────────────────

async def demo_queue():
    """Agent task queue: producer creates tasks, workers consume."""
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=10)

    async def producer():
        for i in range(5):
            await queue.put(f"task_{i}")
            await asyncio.sleep(0.01)
        await queue.put(None)  # sentinel to stop workers

    async def worker(worker_id: int):
        while True:
            task = await queue.get()
            if task is None:
                queue.task_done()
                break
            await asyncio.sleep(0.02)  # simulate processing
            print(f"  Worker {worker_id} processed {task}")
            queue.task_done()

    await asyncio.gather(producer(), worker(1), worker(2))
    print("\nQueue: all tasks processed")

asyncio.run(demo_queue())


# ═══════════════════════════════════════════════════════
# PART E: Agentic AI — Parallel Tool Execution
# ═══════════════════════════════════════════════════════

# ─────────────────────────────────────────────
# 1. Pattern: run multiple agent tools concurrently
# ─────────────────────────────────────────────

async def web_search(query: str) -> list[str]:
    await asyncio.sleep(0.1)
    return [f"Search result for {query}"]

async def read_file(path: str) -> str:
    await asyncio.sleep(0.05)
    return f"File content from {path}"

async def query_db(sql: str) -> list[dict]:
    await asyncio.sleep(0.08)
    return [{"row": 1}]


async def agent_parallel_tools():
    """Run independent tool calls in parallel — critical for agent performance."""
    print("\n=== Parallel Tool Execution ===")
    start = time.perf_counter()

    # All 3 run concurrently — total time = max(0.1, 0.05, 0.08) = 0.1s
    search_results, file_content, db_rows = await asyncio.gather(
        web_search("Python async patterns"),
        read_file("/data/config.json"),
        query_db("SELECT * FROM users LIMIT 10"),
    )

    elapsed = time.perf_counter() - start
    print(f"3 tools completed in {elapsed:.3f}s (0.1s max, not 0.23s sequential)")

asyncio.run(agent_parallel_tools())


# ─────────────────────────────────────────────
# 2. asyncio.timeout — don't let slow tools block agents
# ─────────────────────────────────────────────

async def demo_timeout():
    async def slow_tool():
        await asyncio.sleep(10)  # too slow
        return "result"

    print("\n=== asyncio.timeout ===")
    try:
        async with asyncio.timeout(0.1):  # Python 3.11+
            result = await slow_tool()
    except TimeoutError:
        print("Tool timed out — agent can continue with partial results")

asyncio.run(demo_timeout())


# ─────────────────────────────────────────────
# 3. asyncio.TaskGroup — structured concurrency (Python 3.11+)
#    If ANY task fails, ALL others are cancelled automatically
# ─────────────────────────────────────────────

async def demo_taskgroup():
    print("\n=== TaskGroup: structured concurrency ===")
    results = []

    async def agent_task(name: str, delay: float):
        await asyncio.sleep(delay)
        results.append(f"{name} done")

    async with asyncio.TaskGroup() as tg:
        tg.create_task(agent_task("planner", 0.02))
        tg.create_task(agent_task("researcher", 0.03))
        tg.create_task(agent_task("writer", 0.01))
    # All tasks complete here, or all cancelled on first failure

    print(f"TaskGroup results: {results}")

asyncio.run(demo_taskgroup())


# ═══════════════════════════════════════════════════════
# PART F: Interview Questions
# ═══════════════════════════════════════════════════════

"""
Q1: When do you use threading vs multiprocessing?
    threading: I/O-bound (network, file, DB) — GIL released during I/O
    multiprocessing: CPU-bound (ML, image, data) — bypasses GIL entirely

Q2: Can asyncio replace threading?
    Yes for I/O-bound work. asyncio is more efficient (single thread, no
    context switching overhead). But you can't use blocking libraries
    directly — wrap with run_in_executor(thread_pool).

Q3: How do you run a blocking sync function in an async FastAPI handler?
    loop.run_in_executor(None, sync_fn, arg)
    None → uses default thread pool. Pass a ProcessPoolExecutor for CPU work.

Q4: What is asyncio.Semaphore used for?
    Rate limiting: cap concurrent operations (e.g., max 5 LLM API calls at once)
    Prevents overwhelming external APIs or exhausting DB connections.

Q5: What is the difference between asyncio.Lock and threading.Lock?
    threading.Lock: for thread-safe access (sync code, multiple threads)
    asyncio.Lock: for coroutine-safe access (async code, single thread)
    Using threading.Lock in async code blocks the entire event loop.

Q6: What is asyncio.TaskGroup and why is it better than gather?
    TaskGroup (Python 3.11+) provides structured concurrency — if one task
    fails, ALL others are automatically cancelled. gather continues unless
    return_exceptions=False, and cancellation is manual.

Q7: What max_workers should you use for ThreadPoolExecutor?
    I/O-bound: (CPU count × 5) is a common heuristic, or tune by profiling.
    CPU-bound (ProcessPool): os.cpu_count() - 1 to leave one core for OS.
"""
