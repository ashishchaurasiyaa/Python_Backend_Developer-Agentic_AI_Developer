"""
DAY 31 — asyncio Advanced: gather, TaskGroup, shield, timeout, Semaphore
Architecture Level: Senior Python Backend + Agentic AI

This is the MOST CRITICAL day for Agentic AI.
Agents make PARALLEL LLM calls, tool calls, and API requests.
"""

import asyncio
import time
from typing import Any


# ═══════════════════════════════════════════════════════
# PART A: asyncio.gather — run coroutines concurrently
# ═══════════════════════════════════════════════════════

async def call_llm(model: str, prompt: str, delay: float) -> dict:
    """Simulate LLM API call with latency."""
    await asyncio.sleep(delay)  # simulate network I/O
    return {"model": model, "response": f"Answer to: {prompt}", "tokens": 100}


async def demo_gather():
    print("\n=== asyncio.gather ===")
    start = time.perf_counter()

    # SEQUENTIAL (bad for AI agents):
    # r1 = await call_llm("gpt-4", "What is Python?", 1.0)
    # r2 = await call_llm("claude-3", "What is FastAPI?", 1.0)
    # Total: 2 seconds

    # CONCURRENT with gather (good):
    results = await asyncio.gather(
        call_llm("gpt-4", "What is Python?", 1.0),
        call_llm("claude-3", "What is FastAPI?", 1.0),
        call_llm("gemini", "What is LangChain?", 0.5),
    )
    elapsed = time.perf_counter() - start
    print(f"3 LLM calls in {elapsed:.2f}s (would be 2.5s sequential)")
    for r in results:
        print(f"  {r['model']}: {r['response']}")

    # gather with return_exceptions=True — don't fail fast
    async def might_fail(i: int):
        await asyncio.sleep(0.1)
        if i == 1:
            raise ValueError(f"Tool {i} failed")
        return f"result_{i}"

    results_with_errors = await asyncio.gather(
        might_fail(0), might_fail(1), might_fail(2),
        return_exceptions=True,  # exceptions returned as values, not raised
    )
    for i, r in enumerate(results_with_errors):
        if isinstance(r, Exception):
            print(f"  Task {i} ERROR: {r}")
        else:
            print(f"  Task {i} OK: {r}")


asyncio.run(demo_gather())


# ═══════════════════════════════════════════════════════
# PART B: asyncio.TaskGroup — Python 3.11+ (preferred over gather)
# ═══════════════════════════════════════════════════════

async def demo_taskgroup():
    print("\n=== asyncio.TaskGroup (Python 3.11+) ===")
    start = time.perf_counter()

    # TaskGroup advantages over gather:
    # 1. Structured concurrency — tasks are scoped to the group
    # 2. If one task raises, others are CANCELLED (not left orphaned)
    # 3. Better error messages with ExceptionGroup
    # 4. Type checker friendly

    results: list[dict] = []

    async with asyncio.TaskGroup() as tg:
        task1 = tg.create_task(call_llm("gpt-4", "Python?", 0.5))
        task2 = tg.create_task(call_llm("claude", "FastAPI?", 0.3))
        task3 = tg.create_task(call_llm("gemini", "Redis?", 0.4))
    # All tasks complete here — or all cancelled if one fails

    elapsed = time.perf_counter() - start
    print(f"TaskGroup done in {elapsed:.2f}s")
    print(f"  task1: {task1.result()['model']}")
    print(f"  task2: {task2.result()['model']}")


asyncio.run(demo_taskgroup())


# ═══════════════════════════════════════════════════════
# PART C: Semaphore — limit concurrent API calls
# ═══════════════════════════════════════════════════════

async def demo_semaphore():
    print("\n=== asyncio.Semaphore (rate limiting) ===")

    # Problem: 100 documents, each needs LLM embedding call
    # Sending all 100 simultaneously → rate limit error (429)
    # Solution: Semaphore limits concurrent calls

    sem = asyncio.Semaphore(5)  # max 5 concurrent API calls

    async def embed_document(doc_id: int) -> str:
        async with sem:  # blocks if 5 are already running
            await asyncio.sleep(0.1)  # simulate API call
            return f"embedding_{doc_id}"

    start = time.perf_counter()
    tasks = [embed_document(i) for i in range(20)]
    embeddings = await asyncio.gather(*tasks)
    elapsed = time.perf_counter() - start

    print(f"Embedded 20 docs (max 5 concurrent) in {elapsed:.2f}s")
    print(f"First 3: {embeddings[:3]}")


asyncio.run(demo_semaphore())


# ═══════════════════════════════════════════════════════
# PART D: asyncio.timeout + shield
# ═══════════════════════════════════════════════════════

async def demo_timeout():
    print("\n=== asyncio.timeout ===")

    async def slow_tool(name: str, delay: float) -> str:
        await asyncio.sleep(delay)
        return f"{name} result"

    # asyncio.timeout — Python 3.11+ (preferred)
    try:
        async with asyncio.timeout(0.5):  # 500ms timeout
            result = await slow_tool("web_search", 0.3)  # OK
            print(f"  Fast tool: {result}")

        async with asyncio.timeout(0.5):
            result = await slow_tool("slow_api", 1.0)   # TIMEOUT
    except TimeoutError:
        print("  Slow tool timed out — fallback to cached result")

    # asyncio.wait_for — Python 3.10 and earlier
    try:
        result = await asyncio.wait_for(slow_tool("api", 1.0), timeout=0.3)
    except asyncio.TimeoutError:
        print("  wait_for timeout caught")


asyncio.run(demo_timeout())


async def demo_shield():
    print("\n=== asyncio.shield — protect critical tasks ===")

    async def save_to_db(data: str) -> None:
        """Critical operation — must NOT be cancelled mid-flight."""
        await asyncio.sleep(0.2)
        print(f"  Saved: {data}")

    async def agent_task():
        # shield() protects save_to_db from cancellation
        # Even if agent_task is cancelled, save_to_db completes
        try:
            await asyncio.shield(save_to_db("agent_state"))
        except asyncio.CancelledError:
            print("  Agent was cancelled, but DB save continues!")

    task = asyncio.create_task(agent_task())
    await asyncio.sleep(0.05)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await asyncio.sleep(0.3)  # let shielded task finish


asyncio.run(demo_shield())


# ═══════════════════════════════════════════════════════
# PART E: REAL AGENTIC AI PATTERN — Parallel tool execution
# ═══════════════════════════════════════════════════════

async def web_search(query: str) -> str:
    await asyncio.sleep(0.5)
    return f"Search results for: {query}"

async def get_weather(city: str) -> str:
    await asyncio.sleep(0.3)
    return f"Weather in {city}: Sunny 25°C"

async def run_code(code: str) -> str:
    await asyncio.sleep(0.2)
    return f"Code output: 42"


class AgentExecutor:
    """
    Executes multiple tools in parallel with:
    - Rate limiting via Semaphore
    - Timeout per tool
    - Error isolation (one tool failure doesn't kill others)
    """

    def __init__(self, max_concurrent: int = 5, tool_timeout: float = 10.0):
        self._sem = asyncio.Semaphore(max_concurrent)
        self._timeout = tool_timeout

    async def run_tool(self, tool_name: str, coro) -> dict:
        """Run single tool with timeout and error handling."""
        async with self._sem:
            try:
                async with asyncio.timeout(self._timeout):
                    result = await coro
                    return {"tool": tool_name, "success": True, "result": result}
            except TimeoutError:
                return {"tool": tool_name, "success": False, "error": "timeout"}
            except Exception as e:
                return {"tool": tool_name, "success": False, "error": str(e)}

    async def run_parallel(self, tool_calls: list[tuple[str, Any]]) -> list[dict]:
        """Run all tools concurrently."""
        tasks = [self.run_tool(name, coro) for name, coro in tool_calls]
        return await asyncio.gather(*tasks)


async def demo_agent():
    executor = AgentExecutor(max_concurrent=3, tool_timeout=5.0)

    tool_calls = [
        ("web_search", web_search("Python asyncio")),
        ("weather", get_weather("San Francisco")),
        ("code_runner", run_code("print(6 * 7)")),
    ]

    start = time.perf_counter()
    results = await executor.run_parallel(tool_calls)
    elapsed = time.perf_counter() - start

    print(f"\n=== Parallel Agent Tool Execution ({elapsed:.2f}s) ===")
    for r in results:
        status = "OK" if r["success"] else f"FAIL: {r.get('error')}"
        print(f"  {r['tool']}: {status}")
        if r["success"]:
            print(f"    → {r['result'][:60]}")


asyncio.run(demo_agent())


# ─────────────────────────────────────────────
# INTERVIEW CHEAT SHEET
# ─────────────────────────────────────────────
# gather()        — run N coroutines concurrently, wait for all
# TaskGroup       — structured concurrency, cancels all on failure (3.11+)
# Semaphore(n)    — max N concurrent operations (rate limiting)
# timeout(s)      — cancel if exceeds s seconds (3.11+)
# wait_for(c, t)  — timeout for single coroutine (3.10-)
# shield(c)       — protect coroutine from external cancellation
# create_task()   — schedule coroutine, don't wait immediately
# asyncio.Queue   — async-safe producer/consumer queue
#
# COMMON MISTAKE: await inside gather without wrapping in coroutine
# asyncio.gather(await func())  ← WRONG (evaluates func() immediately)
# asyncio.gather(func())        ← CORRECT (passes coroutine object)
