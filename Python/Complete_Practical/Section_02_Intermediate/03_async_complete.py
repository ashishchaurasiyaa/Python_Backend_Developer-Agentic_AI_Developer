"""
╔══════════════════════════════════════════════════════════════╗
║  PYTHON COMPLETE PRACTICAL — Section 02                      ║
║  Topic: Async/Await — Complete Reference                     ║
║  This is the MOST IMPORTANT topic for Agentic AI             ║
╚══════════════════════════════════════════════════════════════╝
"""

import asyncio
import time
import random
from typing import AsyncGenerator, AsyncIterator


# ══════════════════════════════════════════════════════════════
# PART A: FOUNDATIONS
# ══════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────
# 1. SYNC vs ASYNC — why it matters
# ─────────────────────────────────────────────────────────────

def sync_fetch(url: str, delay: float) -> str:
    """Blocking — entire thread waits."""
    time.sleep(delay)
    return f"Response from {url}"

async def async_fetch(url: str, delay: float) -> str:
    """Non-blocking — yields control during wait."""
    await asyncio.sleep(delay)   # releases event loop, other tasks run
    return f"Response from {url}"


async def compare_sync_vs_async():
    urls = [("api1", 1.0), ("api2", 1.0), ("api3", 1.0)]

    # SEQUENTIAL (like sync) — 3 seconds total
    start = time.perf_counter()
    for url, delay in urls:
        result = await async_fetch(url, delay)
    seq_time = time.perf_counter() - start
    print(f"Sequential: {seq_time:.2f}s")

    # CONCURRENT (gather) — ~1 second total
    start = time.perf_counter()
    results = await asyncio.gather(*[async_fetch(url, delay) for url, delay in urls])
    con_time = time.perf_counter() - start
    print(f"Concurrent: {con_time:.2f}s")
    print(f"Speedup: {seq_time/con_time:.1f}x")

asyncio.run(compare_sync_vs_async())


# ─────────────────────────────────────────────────────────────
# 2. COROUTINES — the basics
# ─────────────────────────────────────────────────────────────

async def greet(name: str) -> str:
    """Simple coroutine."""
    await asyncio.sleep(0.1)   # simulate I/O
    return f"Hello, {name}!"

# Coroutine object — NOT executed yet
coro = greet("Alice")
print(f"\nCoroutine type: {type(coro)}")

# Execute with asyncio.run (entry point)
result = asyncio.run(greet("Alice"))
print(f"Result: {result}")


# ─────────────────────────────────────────────────────────────
# 3. TASKS — schedule without waiting
# ─────────────────────────────────────────────────────────────

async def demo_tasks():
    print("\n=== Tasks ===")

    async def worker(name: str, delay: float) -> str:
        await asyncio.sleep(delay)
        return f"{name} done"

    # Create tasks — start immediately, don't block
    task1 = asyncio.create_task(worker("task1", 0.5), name="task1")
    task2 = asyncio.create_task(worker("task2", 0.3), name="task2")
    task3 = asyncio.create_task(worker("task3", 0.4), name="task3")

    # All tasks are running concurrently now
    # Await each to get result
    r1 = await task1
    r2 = await task2
    r3 = await task3
    print(f"Results: {[r1, r2, r3]}")

    # Cancel a task
    slow_task = asyncio.create_task(worker("slow", 10.0))
    await asyncio.sleep(0.1)
    slow_task.cancel()
    try:
        await slow_task
    except asyncio.CancelledError:
        print("Task was cancelled")

asyncio.run(demo_tasks())


# ══════════════════════════════════════════════════════════════
# PART B: CONCURRENCY TOOLS
# ══════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────
# 4. asyncio.gather — run many coroutines
# ─────────────────────────────────────────────────────────────

async def call_llm(model: str, prompt: str, delay: float) -> dict:
    await asyncio.sleep(delay)
    return {"model": model, "response": f"Answer to: {prompt}", "tokens": 100}

async def demo_gather():
    print("\n=== asyncio.gather ===")
    start = time.perf_counter()

    # All 3 run concurrently — fastest is ~1.0s (max delay), not 2.5s (sum)
    results = await asyncio.gather(
        call_llm("gpt-4",    "What is Python?", 0.5),
        call_llm("claude-3", "What is FastAPI?", 0.8),
        call_llm("gemini",   "What is LangChain?", 1.0),
    )
    elapsed = time.perf_counter() - start

    print(f"Time: {elapsed:.2f}s (not {0.5+0.8+1.0:.1f}s)")
    for r in results:
        print(f"  {r['model']}: {r['response'][:40]}")

    # return_exceptions=True — don't fail all if one fails
    async def might_fail(n: int):
        await asyncio.sleep(0.1)
        if n == 1:
            raise ValueError(f"Tool {n} failed")
        return f"ok_{n}"

    results = await asyncio.gather(
        might_fail(0), might_fail(1), might_fail(2),
        return_exceptions=True,
    )
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            print(f"  Task {i}: FAILED — {r}")
        else:
            print(f"  Task {i}: OK — {r}")

asyncio.run(demo_gather())


# ─────────────────────────────────────────────────────────────
# 5. asyncio.TaskGroup (Python 3.11+) — structured concurrency
# ─────────────────────────────────────────────────────────────

async def demo_taskgroup():
    print("\n=== TaskGroup (Python 3.11+) ===")
    start = time.perf_counter()

    async with asyncio.TaskGroup() as tg:
        t1 = tg.create_task(call_llm("gpt-4",    "Python?", 0.3))
        t2 = tg.create_task(call_llm("claude-3", "FastAPI?", 0.5))
        t3 = tg.create_task(call_llm("gemini",   "Redis?", 0.4))
    # All 3 done here — or all cancelled if any fails

    elapsed = time.perf_counter() - start
    print(f"TaskGroup done in {elapsed:.2f}s")
    print(f"  {t1.result()['model']}: {t1.result()['response'][:30]}")
    print(f"  {t2.result()['model']}: {t2.result()['response'][:30]}")

asyncio.run(demo_taskgroup())


# ─────────────────────────────────────────────────────────────
# 6. asyncio.Semaphore — rate limiting
# ─────────────────────────────────────────────────────────────

async def demo_semaphore():
    print("\n=== Semaphore (max concurrent=5) ===")

    sem = asyncio.Semaphore(5)   # max 5 concurrent API calls

    async def embed(doc_id: int) -> str:
        async with sem:          # blocks if 5 already running
            await asyncio.sleep(0.1)   # simulate API call
            return f"embedding_{doc_id}"

    start = time.perf_counter()
    # 20 docs, max 5 at a time → ~4 batches × 0.1s = ~0.4s
    embeddings = await asyncio.gather(*[embed(i) for i in range(20)])
    elapsed = time.perf_counter() - start

    print(f"20 embeddings in {elapsed:.2f}s (max 5 concurrent)")
    print(f"First 3: {embeddings[:3]}")

asyncio.run(demo_semaphore())


# ─────────────────────────────────────────────────────────────
# 7. asyncio.timeout + asyncio.wait_for
# ─────────────────────────────────────────────────────────────

async def demo_timeouts():
    print("\n=== Timeouts ===")

    async def slow_tool(name: str, delay: float) -> str:
        await asyncio.sleep(delay)
        return f"{name} result"

    # asyncio.timeout (Python 3.11+) — context manager style
    try:
        async with asyncio.timeout(0.5):
            result = await slow_tool("fast_api", 0.3)
            print(f"Fast tool OK: {result}")

        async with asyncio.timeout(0.5):
            result = await slow_tool("slow_api", 1.0)   # will timeout
    except TimeoutError:
        print("Slow tool timed out → using fallback")

    # asyncio.wait_for — wrap single coroutine with timeout
    try:
        result = await asyncio.wait_for(slow_tool("api", 1.0), timeout=0.3)
    except asyncio.TimeoutError:
        print("wait_for timeout triggered")

asyncio.run(demo_timeouts())


# ─────────────────────────────────────────────────────────────
# 8. asyncio.shield — protect from cancellation
# ─────────────────────────────────────────────────────────────

async def demo_shield():
    print("\n=== Shield ===")

    async def save_agent_state(state: dict) -> None:
        """Critical — must not be interrupted."""
        await asyncio.sleep(0.2)
        print(f"  [DB] State saved: {state}")

    async def run_agent(task: str) -> str:
        try:
            result = f"Result: {task}"
            # Shield protects save from cancellation
            await asyncio.shield(save_agent_state({"task": task, "result": result}))
            return result
        except asyncio.CancelledError:
            print("  Agent was cancelled, but save continues!")
            raise

    task = asyncio.create_task(run_agent("Analyze data"))
    await asyncio.sleep(0.05)
    task.cancel()                      # cancel agent task
    try:
        await task
    except asyncio.CancelledError:
        pass
    await asyncio.sleep(0.3)           # let shielded save complete

asyncio.run(demo_shield())


# ─────────────────────────────────────────────────────────────
# 9. asyncio.Queue — producer/consumer pattern
# ─────────────────────────────────────────────────────────────

async def demo_queue():
    print("\n=== Queue (Producer/Consumer) ===")

    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=5)

    async def producer(n: int) -> None:
        for i in range(n):
            task_id = f"task_{i}"
            await queue.put(task_id)       # blocks if queue is full
            print(f"  [PRODUCER] Enqueued: {task_id}")
            await asyncio.sleep(0.05)
        await queue.put(None)              # sentinel to stop consumer

    async def consumer() -> None:
        while True:
            item = await queue.get()       # blocks until item available
            if item is None:
                break
            await asyncio.sleep(0.1)       # simulate processing
            print(f"  [CONSUMER] Processed: {item}")
            queue.task_done()

    await asyncio.gather(producer(5), consumer())

asyncio.run(demo_queue())


# ─────────────────────────────────────────────────────────────
# 10. ASYNC GENERATORS and ASYNC ITERATORS
# ─────────────────────────────────────────────────────────────

async def stream_llm_tokens(text: str) -> AsyncGenerator[str, None]:
    """Simulate LLM streaming response."""
    for word in text.split():
        await asyncio.sleep(0.05)   # simulate token generation
        yield word

async def async_range(n: int) -> AsyncGenerator[int, None]:
    for i in range(n):
        await asyncio.sleep(0.01)
        yield i

async def demo_async_gen():
    print("\n=== Async Generator (LLM Streaming) ===")
    response = ""
    async for token in stream_llm_tokens("Hello from async Python AI backend"):
        response += token + " "
        print(f"  token: {token}")
    print(f"Full response: {response.strip()}")

asyncio.run(demo_async_gen())


# ══════════════════════════════════════════════════════════════
# PART C: PRODUCTION PATTERNS
# ══════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────
# 11. COMPLETE AGENTIC AI PATTERN — parallel tool execution
# ─────────────────────────────────────────────────────────────

async def web_search(query: str) -> str:
    await asyncio.sleep(0.3)
    return f"Found 10 results for: {query}"

async def get_weather(city: str) -> str:
    await asyncio.sleep(0.2)
    return f"Weather in {city}: 25°C Sunny"

async def run_code(code: str) -> tuple[str, bool]:
    await asyncio.sleep(0.15)
    return "Output: 42", True

async def fetch_document(url: str) -> str:
    await asyncio.sleep(0.4)
    return f"Document content from {url}"


class AsyncAgentExecutor:
    """
    Production agent executor with:
    - Parallel tool execution
    - Rate limiting via Semaphore
    - Per-tool timeout
    - Error isolation
    """

    def __init__(self, max_concurrent: int = 5, tool_timeout: float = 10.0):
        self._sem = asyncio.Semaphore(max_concurrent)
        self._timeout = tool_timeout

    async def _run_tool(self, name: str, coro) -> dict:
        async with self._sem:
            try:
                async with asyncio.timeout(self._timeout):
                    result = await coro
                    return {"tool": name, "success": True, "result": result}
            except TimeoutError:
                return {"tool": name, "success": False, "error": "timeout"}
            except Exception as e:
                return {"tool": name, "success": False, "error": str(e)}

    async def run_parallel(self, tool_calls: list[tuple[str, object]]) -> list[dict]:
        """Execute all tools in parallel, collect results."""
        tasks = [self._run_tool(name, coro) for name, coro in tool_calls]
        return await asyncio.gather(*tasks)

    async def run_sequential(self, tool_calls: list[tuple[str, object]]) -> list[dict]:
        """Execute tools one by one (when order matters)."""
        results = []
        for name, coro in tool_calls:
            result = await self._run_tool(name, coro)
            results.append(result)
            if not result["success"]:
                break   # stop pipeline on failure
        return results


async def demo_full_agent():
    executor = AsyncAgentExecutor(max_concurrent=5, tool_timeout=5.0)

    tool_calls = [
        ("web_search",    web_search("Python asyncio tutorial")),
        ("weather",       get_weather("San Francisco")),
        ("code_runner",   run_code("print(6 * 7)")),
        ("doc_fetcher",   fetch_document("https://docs.python.org/asyncio")),
    ]

    print("\n=== Full Agentic AI Execution ===")
    start = time.perf_counter()
    results = await executor.run_parallel(tool_calls)
    elapsed = time.perf_counter() - start

    print(f"4 tools in {elapsed:.2f}s (would be ~{0.3+0.2+0.15+0.4:.2f}s sequential)")
    for r in results:
        status = "OK" if r["success"] else f"FAILED: {r.get('error')}"
        print(f"  {r['tool']}: {status}")
        if r["success"]:
            result_str = str(r["result"])[:60]
            print(f"    → {result_str}")

asyncio.run(demo_full_agent())


# ─────────────────────────────────────────────────────────────
# 12. EVENT LOOP — understanding
# ─────────────────────────────────────────────────────────────

# Event loop is the core of asyncio:
# 1. Schedules coroutines, tasks, callbacks
# 2. Runs until all tasks complete or loop.stop() called
# 3. I/O operations release the loop (await asyncio.sleep, await httpx.get, etc.)
# 4. CPU-bound code blocks the loop — use run_in_executor() instead

async def cpu_bound_with_executor() -> int:
    """Run CPU-intensive code without blocking the event loop."""
    loop = asyncio.get_event_loop()
    # Runs in a thread pool — doesn't block the event loop
    result = await loop.run_in_executor(
        None,                           # default ThreadPoolExecutor
        lambda: sum(range(1_000_000))   # CPU-bound work
    )
    return result

result = asyncio.run(cpu_bound_with_executor())
print(f"\nCPU result (non-blocking): {result}")


# ─────────────────────────────────────────────────────────────
# THREADING vs MULTIPROCESSING vs ASYNC — INTERVIEW CRITICAL
# ─────────────────────────────────────────────────────────────
"""
GIL (Global Interpreter Lock):
  Only 1 Python thread executes bytecode at a time.
  Released during I/O operations.

┌────────────────┬─────────────────────────────────────────────────┐
│ Concurrency    │ Best For                                        │
├────────────────┼─────────────────────────────────────────────────┤
│ asyncio        │ I/O-bound: API calls, DB queries, file ops      │
│                │ Single thread, event loop, minimal overhead      │
├────────────────┼─────────────────────────────────────────────────┤
│ threading      │ I/O-bound with blocking libs (requests, etc.)   │
│                │ Multiple threads, GIL limits CPU parallelism     │
├────────────────┼─────────────────────────────────────────────────┤
│ multiprocessing│ CPU-bound: data processing, ML inference        │
│                │ Multiple processes, each with own GIL           │
└────────────────┴─────────────────────────────────────────────────┘

For Agentic AI:
  Use asyncio — most LLM/API calls are I/O-bound.
  Use asyncio.Semaphore for rate limiting.
  Use run_in_executor for CPU-bound ML preprocessing.
"""
