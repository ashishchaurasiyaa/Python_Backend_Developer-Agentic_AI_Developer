"""
╔══════════════════════════════════════════════════════════════════════════════╗
║   PYTHON COMPLETE THEORY — File 04                                           ║
║   Topic: Async/Await + Concurrency (GIL, Threading, Multiprocessing)         ║
║   Format: WHAT → WHY → HOW → REAL LIFE → PRODUCTION CODE → Q&A              ║
╚══════════════════════════════════════════════════════════════════════════════╝

Topics Covered:
  A. Sync vs Async — What is the problem?
  B. Event Loop — The heart of asyncio
  C. async def, await, asyncio.run()
  D. asyncio.gather() — parallel coroutines
  E. asyncio.TaskGroup — structured concurrency (3.11+)
  F. asyncio.Semaphore — rate limiting
  G. asyncio.timeout — deadline management
  H. asyncio.shield — protect critical coroutines
  I. asyncio.Queue — producer/consumer pattern
  J. Async Generators — streaming results
  K. GIL — Global Interpreter Lock
  L. Threading — I/O bound concurrency
  M. Multiprocessing — CPU bound parallelism
  N. Decision Table — When to use what?
"""

import asyncio
import threading
import time
import sys
from typing import AsyncGenerator


# ══════════════════════════════════════════════════════════════════════════════
# PART A: THE PROBLEM — WHY ASYNC EXISTS
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS THE PROBLEM ASYNC SOLVES?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SYNCHRONOUS (Normal) CODE:
  Tasks execute ONE AT A TIME.
  While waiting for Task 1 to finish, Task 2 and 3 WAIT.

  Timeline (3 tasks, each takes 1 second):
  ──────────────────────────────────────────────
  Thread 1: [Task1 runs 1s] → [Task2 runs 1s] → [Task3 runs 1s]
  Total time: 3 seconds

  Problem: You call OpenAI API (takes 2 seconds), Python just SITS THERE.
  The CPU is doing NOTHING while waiting for the network response.
  This is I/O waiting — the bottleneck is NOT the CPU.

ASYNCHRONOUS CODE:
  While waiting for Task 1 (I/O), START Task 2 and Task 3.
  The CPU is doing USEFUL WORK while one task is waiting.

  Timeline (same 3 tasks, each waits 1 second):
  ──────────────────────────────────────────────
  Thread 1: [Task1 starts]
            [Task2 starts]   ← while Task1 is waiting on I/O
            [Task3 starts]   ← while Task1 and Task2 are waiting
            [All complete]
  Total time: ~1 second!

  3x speedup for I/O-bound work!

TWO TYPES OF WORK:
  1. I/O-BOUND: CPU waits for external resource (network, disk, database)
     Examples: API calls, database queries, file reads
     Solution: asyncio (or threading) — CPU can do other things while waiting

  2. CPU-BOUND: CPU is actively computing (no waiting)
     Examples: image processing, ML inference, number crunching
     Solution: multiprocessing — use multiple CPU cores in parallel

REAL LIFE ANALOGY:
  SYNC = Single chef in a restaurant:
    Cook dish 1 (20 min) → serve → Cook dish 2 (20 min) → serve
    Total: 40 minutes for 2 tables. Tables wait!

  ASYNC = Smart chef:
    Put dish 1 in oven (waiting) → While oven runs, prep dish 2 →
    Check dish 1 (done!) → Serve dish 1 → dish 2 is almost ready...
    Total: ~20 minutes for 2 tables. NO WASTED TIME!

  THREADING = Two chefs:
    Chef 1 makes dish 1, Chef 2 makes dish 2 simultaneously.
    (Works but has coordination overhead — two people in one kitchen)

  MULTIPROCESSING = Two separate kitchens:
    Each kitchen completely independent, truly parallel.
    Overhead: running two full kitchens.
"""

# Demonstrating the SPEEDUP
import asyncio


async def fetch_llm_response(prompt: str, delay: float = 1.0) -> str:
    """Simulates an LLM API call (I/O wait)."""
    await asyncio.sleep(delay)  # I/O waiting — CPU can do other things
    return f"Response to: {prompt}"


async def sync_style_demo():
    """Sequential — each call waits for the previous."""
    start = time.perf_counter()
    r1 = await fetch_llm_response("Q1", delay=1.0)
    r2 = await fetch_llm_response("Q2", delay=1.0)
    r3 = await fetch_llm_response("Q3", delay=1.0)
    elapsed = time.perf_counter() - start
    print(f"Sequential:  {elapsed:.2f}s (3 calls × 1s each = 3s)")
    return [r1, r2, r3]


async def async_style_demo():
    """Parallel — all calls run concurrently!"""
    start = time.perf_counter()
    results = await asyncio.gather(
        fetch_llm_response("Q1", delay=1.0),
        fetch_llm_response("Q2", delay=1.0),
        fetch_llm_response("Q3", delay=1.0),
    )
    elapsed = time.perf_counter() - start
    print(f"Concurrent:  {elapsed:.2f}s (3 calls run together ≈ 1s)")
    return results


print("=== Sync vs Async Speed Demo ===")
asyncio.run(sync_style_demo())
asyncio.run(async_style_demo())


# ══════════════════════════════════════════════════════════════════════════════
# PART B: EVENT LOOP — THE HEART OF ASYNCIO
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS THE EVENT LOOP?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The Event Loop is asyncio's SCHEDULER — it decides which coroutine runs next.

HOW IT WORKS (simplified):

  Event Loop cycle:
  ┌──────────────────────────────────────────────────────────────────────┐
  │  Loop starts                                                         │
  │   ↓                                                                  │
  │  Take next ready task from queue                                     │
  │   ↓                                                                  │
  │  Run task until it hits an `await`                                   │
  │   ↓                    ↓                                             │
  │  Task pauses here      Register callback: "wake me when I/O done"   │
  │   ↓                                                                  │
  │  Pick NEXT ready task → run until await → ...                        │
  │   ↓                                                                  │
  │  I/O completes → task becomes ready again → add back to queue        │
  │   ↓                                                                  │
  │  Eventually task resumes from where it paused                        │
  │   ↓                                                                  │
  │  Loop continues until all tasks done                                 │
  └──────────────────────────────────────────────────────────────────────┘

KEY INSIGHT:
  `await` = "I'm waiting for something — let other coroutines run while I wait"
  The event loop uses THIS pause to schedule other work.

  asyncio is SINGLE-THREADED — only ONE coroutine runs at a time.
  But because they PAUSE on I/O, many can be "in flight" simultaneously.

COROUTINE vs TASK:
  Coroutine = async def function — defined but NOT scheduled yet
  Task      = Coroutine wrapped and SUBMITTED to event loop for execution

  coro = my_async_func()          # just a coroutine object, not running
  task = asyncio.create_task(coro) # NOW it's scheduled in event loop

asyncio.run(main()):
  - Creates a NEW event loop
  - Runs `main()` as the top-level coroutine
  - Closes the loop when `main()` completes
  - This is the entry point for any asyncio program
"""


async def demonstrate_event_loop():
    """Shows how the event loop switches between coroutines."""

    async def worker(name: str, delay: float) -> str:
        print(f"    [{name}] Starting (will wait {delay}s)")
        await asyncio.sleep(delay)   # yields control to event loop
        print(f"    [{name}] Done after {delay}s")
        return f"{name} result"

    print(f"\nEvent loop demonstration:")
    print(f"  Creating tasks (they're scheduled, not run yet)")
    t1 = asyncio.create_task(worker("LLM-1", 0.3))
    t2 = asyncio.create_task(worker("LLM-2", 0.1))
    t3 = asyncio.create_task(worker("LLM-3", 0.2))
    print(f"  All tasks created, now awaiting...")
    results = await asyncio.gather(t1, t2, t3)
    print(f"  Results: {results}")
    # Note: LLM-2 finishes first (0.1s), then LLM-3 (0.2s), then LLM-1 (0.3s)
    # But we await ALL three — total ≈ 0.3s


asyncio.run(demonstrate_event_loop())


# ══════════════════════════════════════════════════════════════════════════════
# PART C: async def, await, asyncio.run()
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SYNTAX AND CONCEPTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def:
  Defines a COROUTINE FUNCTION. Calling it returns a coroutine OBJECT.
  The body doesn't run until you await it.

  async def greet():       # coroutine function
      return "hello"

  coro = greet()           # returns coroutine object — NOT "hello"
  result = await greet()   # NOW executes, returns "hello"

await:
  Suspends current coroutine, passes control to event loop.
  Can only be used INSIDE an async def function.
  Works on: coroutines, Tasks, asyncio.Future, anything that implements __await__

asyncio.run():
  Creates event loop, runs the top-level coroutine, cleans up.
  Use ONCE at the top of your program.
  Don't nest asyncio.run() — use asyncio.create_task() instead.

COMMON MISTAKES:
  ❌  result = my_async_func()          # forgot await → coroutine object, not result!
  ✅  result = await my_async_func()    # correct

  ❌  def my_func():
          await something()            # await outside async → SyntaxError

  ❌  asyncio.run(asyncio.run(main())) # nested run → RuntimeError
  ✅  asyncio.create_task(another())   # inside async, create task

WHAT MAKES A FUNCTION "AWAITABLE"?
  Any object with __await__ method. Built-in awaitables:
  - Coroutines (from async def)
  - asyncio.Task
  - asyncio.Future
  - asyncio.sleep()
  - Any I/O in asyncio: asyncio.open_connection, aiohttp calls, etc.
"""


async def production_llm_call(
    prompt: str,
    model: str = "gpt-4",
    timeout: float = 10.0,
) -> dict:
    """
    Production pattern: async LLM call with proper structure.
    """
    print(f"  → Calling {model} with: {prompt[:30]}...")
    await asyncio.sleep(0.5)  # simulate API latency
    return {
        "model": model,
        "prompt": prompt,
        "response": f"Response from {model}",
        "tokens_used": len(prompt.split()) * 2,
    }


async def main_llm_demo():
    result = await production_llm_call("Explain Python async in simple terms")
    print(f"  LLM result: {result['response']}")
    print(f"  Tokens: {result['tokens_used']}")


asyncio.run(main_llm_demo())


# ══════════════════════════════════════════════════════════════════════════════
# PART D: asyncio.gather() — PARALLEL EXECUTION
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS asyncio.gather()?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

gather() runs MULTIPLE coroutines CONCURRENTLY and waits for ALL to finish.
Returns a list of results in the SAME ORDER as the coroutines passed.

WHY?
  When you have multiple independent tasks that can run in parallel —
  instead of waiting for each one, run all together.

  Example: Agentic AI calling 5 different tools simultaneously.

HOW:
  results = await asyncio.gather(coro1(), coro2(), coro3())
  # results = [result1, result2, result3]  ← SAME ORDER as input

  With return_exceptions=True:
    If one coroutine fails, gather still completes.
    The exception is returned as an ITEM in results instead of propagating.
    Default (False): first exception propagates, cancels others.

REAL LIFE ANALOGY:
  You ask 5 different experts the same question at the same time.
  gather() = "Ask all 5, wait for all 5 answers, collect them."
  Without gather = Ask expert 1, wait, ask expert 2, wait, ... (slow!)
"""


async def call_tool(tool_name: str, query: str, latency: float = 0.5) -> dict:
    """Simulates an AI tool call."""
    await asyncio.sleep(latency)
    return {"tool": tool_name, "result": f"{tool_name}: {query}", "latency": latency}


async def parallel_tool_calls_demo():
    """Multi-tool agentic AI — all tools called simultaneously."""
    print(f"\ngather() — parallel tool calls:")

    start = time.perf_counter()
    results = await asyncio.gather(
        call_tool("web_search", "Python async patterns", 0.8),
        call_tool("code_execute", "print('hello')", 0.3),
        call_tool("file_read", "config.json", 0.5),
        call_tool("database_query", "SELECT * FROM users", 0.6),
        call_tool("api_call", "GET /weather/london", 0.4),
        return_exceptions=True,  # don't fail if one tool fails
    )
    elapsed = time.perf_counter() - start

    for r in results:
        if isinstance(r, Exception):
            print(f"  ❌ Tool failed: {r}")
        else:
            print(f"  ✅ {r['tool']}: latency={r['latency']}s")

    print(f"Total time: {elapsed:.2f}s (max latency: 0.8s)")
    # Sequential would be 0.8+0.3+0.5+0.6+0.4 = 2.6s!


asyncio.run(parallel_tool_calls_demo())


# ══════════════════════════════════════════════════════════════════════════════
# PART E: asyncio.TaskGroup (Python 3.11+)
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS TaskGroup?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TaskGroup is the STRUCTURED CONCURRENCY alternative to gather().
Python 3.11+ added this as the preferred way to run parallel tasks.

WHY TaskGroup over gather()?
  Problem with gather():
    - If one task fails, others may continue OR be cancelled (unclear behavior)
    - Hard to add tasks dynamically inside the group
    - No clean syntax for "these tasks belong together"

  TaskGroup:
    - If ANY task raises an exception → ALL other tasks are cancelled
    - Uses ExceptionGroup to collect ALL exceptions (not just first)
    - Clear structured scope: `async with asyncio.TaskGroup() as tg:`
    - Guaranteed cleanup — all tasks done when `async with` block exits

HOW:
  async with asyncio.TaskGroup() as tg:
      task1 = tg.create_task(coro1())   # task is scheduled
      task2 = tg.create_task(coro2())   # task is scheduled
      task3 = tg.create_task(coro3())   # task is scheduled
  # ← all tasks GUARANTEED complete or cancelled here

  results = [task1.result(), task2.result(), task3.result()]

REAL LIFE ANALOGY:
  TaskGroup = Project team with a MANAGER:
  "Everyone start your tasks. If ANYONE fails completely,
  the manager cancels the whole project." — no partial results allowed.

  gather() = More lenient: each person works independently.
"""

import sys

async def taskgroup_demo():
    print(f"\nTaskGroup demonstration (Python {sys.version_info.major}.{sys.version_info.minor}):")

    if sys.version_info < (3, 11):
        print("  (TaskGroup requires Python 3.11+ — showing gather() equivalent)")
        # Fallback to gather
        results = await asyncio.gather(
            call_tool("web_search", "TaskGroup docs", 0.2),
            call_tool("code_execute", "1+1", 0.1),
        )
        for r in results:
            print(f"  ✅ {r['tool']}")
        return

    # Python 3.11+
    async with asyncio.TaskGroup() as tg:
        t1 = tg.create_task(call_tool("web_search", "TaskGroup docs", 0.3))
        t2 = tg.create_task(call_tool("code_execute", "x = 1 + 1", 0.2))
        t3 = tg.create_task(call_tool("file_read", "data.json", 0.1))
    # All guaranteed done here

    for t in [t1, t2, t3]:
        r = t.result()
        print(f"  ✅ {r['tool']}: {r['result'][:40]}")


asyncio.run(taskgroup_demo())


# ══════════════════════════════════════════════════════════════════════════════
# PART F: asyncio.Semaphore — RATE LIMITING
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS asyncio.Semaphore?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Semaphore = A counter that limits HOW MANY coroutines can run at the same time.

WHY?
  Problem: You have 100 LLM API calls to make. But:
  - OpenAI has rate limit: max 10 concurrent requests
  - If you gather() all 100 at once → Rate limit error!

  Solution: Semaphore(10) — only 10 can run at once, others wait.

HOW:
  sem = asyncio.Semaphore(10)  # at most 10 concurrent

  async def limited_call(prompt):
      async with sem:           # acquire slot
          result = await api_call(prompt)
      return result             # release slot (on exit)

  # Now gather 100 but only 10 run at a time
  await asyncio.gather(*[limited_call(p) for p in prompts])

REAL LIFE ANALOGY:
  Semaphore = Parking lot with limited spots:
  - Only 10 cars can park at once (10 concurrent requests)
  - Others wait at the entrance until a spot frees up
  - No car is turned away — they just wait for their turn

INTERNAL MECHANISM:
  Semaphore has an internal counter:
  - acquire(): if counter > 0, decrement and continue
               if counter == 0, WAIT until someone releases
  - release(): increment counter, wake waiting coroutine
"""


async def semaphore_demo():
    MAX_CONCURRENT = 3   # only 3 at a time
    sem = asyncio.Semaphore(MAX_CONCURRENT)
    results = []

    async def rate_limited_llm(prompt_id: int) -> str:
        async with sem:  # wait for slot
            print(f"    Slot acquired for prompt_{prompt_id:02d}")
            await asyncio.sleep(0.5)  # simulate API call
            print(f"    Slot released for prompt_{prompt_id:02d}")
            return f"Result_{prompt_id}"

    print(f"\nSemaphore demo (max {MAX_CONCURRENT} concurrent):")
    start = time.perf_counter()
    results = await asyncio.gather(*[rate_limited_llm(i) for i in range(9)])
    elapsed = time.perf_counter() - start
    print(f"  9 calls, max {MAX_CONCURRENT} concurrent: {elapsed:.2f}s")
    # Expected: ~1.5s (3 batches of 3, each taking 0.5s)


asyncio.run(semaphore_demo())


# ══════════════════════════════════════════════════════════════════════════════
# PART G: asyncio.timeout — DEADLINE MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS asyncio.timeout?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

timeout() sets a DEADLINE — if the coroutine takes longer, it's cancelled.

TWO APPROACHES:
  1. asyncio.wait_for(coro, timeout=N)  → cancels after N seconds
  2. asyncio.timeout(N)                 → context manager (Python 3.11+)

WHY?
  External APIs can be slow or hang forever.
  In production: every external call MUST have a timeout.
  If not → your server hangs indefinitely waiting.

HOW:
  Method 1 (any Python 3.x):
    try:
        result = await asyncio.wait_for(slow_api(), timeout=5.0)
    except asyncio.TimeoutError:
        result = "timeout fallback"

  Method 2 (Python 3.11+):
    try:
        async with asyncio.timeout(5.0):
            result = await slow_api()
    except asyncio.TimeoutError:
        result = "timeout fallback"

REAL LIFE ANALOGY:
  Timeout = Kitchen timer:
  "If the dish isn't ready in 30 minutes, take it out anyway."
  Better a slightly undercooked dish than the kitchen on fire because chef forgot!
"""


async def timeout_demo():
    async def slow_llm(delay: float) -> str:
        await asyncio.sleep(delay)
        return "LLM response"

    print(f"\ntimeout demonstration:")

    # Case 1: Completes within timeout
    try:
        result = await asyncio.wait_for(slow_llm(0.3), timeout=1.0)
        print(f"  ✅ Completed: {result}")
    except asyncio.TimeoutError:
        print(f"  ❌ Timed out")

    # Case 2: Exceeds timeout
    try:
        result = await asyncio.wait_for(slow_llm(2.0), timeout=0.5)
        print(f"  ✅ Completed: {result}")
    except asyncio.TimeoutError:
        print(f"  ⏱️  Timed out! Using fallback response.")
        result = "I need more time to process this request."


asyncio.run(timeout_demo())


# ══════════════════════════════════════════════════════════════════════════════
# PART H: asyncio.shield — PROTECT CRITICAL OPERATIONS
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS asyncio.shield?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

shield() PROTECTS a coroutine from being cancelled by its parent task.

WHY?
  Problem:
    - Task is doing something CRITICAL (saving to database, sending webhook)
    - Parent task gets cancelled (timeout, user cancellation)
    - Normally: ALL child tasks get cancelled too
    - This means critical operation is interrupted! Data corruption risk!

  Solution: shield() — even if parent is cancelled, shielded coroutine continues.

HOW:
  async def main():
      try:
          result = await asyncio.wait_for(
              asyncio.shield(critical_save()),  # protected!
              timeout=1.0
          )
      except asyncio.TimeoutError:
          print("Outer timed out, but critical_save() still runs!")

REAL LIFE ANALOGY:
  You're evacuating a building (cancelled).
  shield() = "I must save this patient (critical operation) before I leave."
  The evacuation continues, but this person stays to finish the critical task.
"""


async def shield_demo():
    async def save_to_database(data: dict) -> str:
        """Critical operation — must not be interrupted."""
        print(f"    [DB] Saving data: {data}")
        await asyncio.sleep(0.8)  # simulates DB write
        print(f"    [DB] Data saved successfully!")
        return "saved"

    async def full_pipeline(data: dict) -> str:
        """Outer pipeline with timeout."""
        try:
            result = await asyncio.wait_for(
                asyncio.shield(save_to_database(data)),  # protected from timeout
                timeout=0.3,  # outer timeout is short
            )
            return result
        except asyncio.TimeoutError:
            print(f"    [Pipeline] Timeout hit, but DB save continues running...")
            return "timeout (but save still happening)"

    print(f"\nshield() demonstration:")
    result = await full_pipeline({"user_id": "123", "conversation": "..."})
    print(f"  Pipeline result: {result}")
    await asyncio.sleep(1.0)  # wait for shielded task to complete


asyncio.run(shield_demo())


# ══════════════════════════════════════════════════════════════════════════════
# PART I: asyncio.Queue — PRODUCER / CONSUMER
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS asyncio.Queue?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

asyncio.Queue is a FIFO queue for communication between coroutines.

WHY?
  Producer-Consumer pattern: one coroutine PRODUCES data, another CONSUMES it.
  They don't need to know about each other — queue is the middleman.

  Example:
    Producer: streams tokens from LLM → puts in queue
    Consumer: reads from queue → displays to user

HOW:
  queue = asyncio.Queue(maxsize=10)  # optional max size

  # Producer:
  await queue.put(item)      # wait if queue is full
  queue.put_nowait(item)     # raise QueueFull if full

  # Consumer:
  item = await queue.get()   # wait if queue is empty
  queue.task_done()          # signal this item processed
  await queue.join()         # wait until all items processed

REAL LIFE ANALOGY:
  Queue = Assembly line / conveyor belt:
  - Factory worker (producer) puts parts on belt
  - Assembler (consumer) takes parts and assembles them
  - Belt has limited capacity (maxsize)
  - Both work independently at their own speed
"""


async def queue_demo():
    queue: asyncio.Queue = asyncio.Queue(maxsize=5)

    async def llm_producer(num_prompts: int) -> None:
        """Produces prompts for processing."""
        for i in range(num_prompts):
            prompt = f"Explain concept #{i + 1}"
            await queue.put(prompt)
            print(f"  [Producer] Added: {prompt}")
            await asyncio.sleep(0.1)
        # Signal: no more items
        await queue.put(None)
        print(f"  [Producer] Done — sent sentinel")

    async def llm_consumer(consumer_id: int) -> list[str]:
        """Consumes and processes prompts."""
        results = []
        while True:
            prompt = await queue.get()
            if prompt is None:
                queue.task_done()
                # Put None back for other consumers
                await queue.put(None)
                break
            print(f"  [Consumer-{consumer_id}] Processing: {prompt}")
            await asyncio.sleep(0.2)  # simulate LLM call
            results.append(f"Result for '{prompt}'")
            queue.task_done()
        return results

    print(f"\nasyncio.Queue producer-consumer demo:")
    results = await asyncio.gather(
        llm_producer(5),
        llm_consumer(1),
    )
    print(f"  Consumer got {len(results[1])} results")


asyncio.run(queue_demo())


# ══════════════════════════════════════════════════════════════════════════════
# PART J: ASYNC GENERATORS — STREAMING
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT ARE ASYNC GENERATORS?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Async Generator = async def + yield
Produces values ONE AT A TIME, with async I/O between yields.

WHY?
  LLM STREAMING:
  - Old way: wait for full response (5-10 seconds) → show all at once
  - Streaming: show each token AS IT ARRIVES (much better UX)
  - ChatGPT, Claude — all use streaming!

HOW:
  async def stream_tokens(prompt: str) -> AsyncGenerator[str, None]:
      for token in generate_tokens(prompt):
          await asyncio.sleep(0.05)  # I/O between tokens
          yield token

  async def main():
      async for token in stream_tokens("Write a poem"):  # async for!
          print(token, end="", flush=True)

SYNTAX DIFFERENCE:
  Regular generator: def + yield        → iterate with for x in gen
  Async generator:   async def + yield  → iterate with async for x in gen

REAL LIFE ANALOGY:
  Async generator = Newspaper printing press:
  - Prints articles one page at a time as they're ready
  - You can start reading page 1 while page 2 is being printed
  - Not: "Wait until entire newspaper is done before giving you anything"
"""


async def stream_llm_tokens(
    prompt: str,
    model: str = "gpt-4",
) -> AsyncGenerator[str, None]:
    """Async generator that streams LLM tokens one by one."""
    # Simulate LLM streaming response
    words = f"[{model}] This is a streaming response to: {prompt}".split()

    for word in words:
        await asyncio.sleep(0.05)  # simulate token generation delay
        yield word + " "


async def streaming_demo():
    print(f"\nAsync generator streaming demo:")
    print("  Output: ", end="")

    full_response = []
    async for token in stream_llm_tokens("What is Python?"):
        print(token, end="", flush=True)
        full_response.append(token)

    print(f"\n  Total tokens: {len(full_response)}")


asyncio.run(streaming_demo())


# ══════════════════════════════════════════════════════════════════════════════
# PART K: GIL — GLOBAL INTERPRETER LOCK
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS THE GIL?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GIL = Global Interpreter Lock
A MUTEX (mutual exclusion lock) in CPython that ensures only ONE thread
can execute Python bytecode at a time.

WHY DOES GIL EXIST?
  CPython's memory management (reference counting) is NOT thread-safe.
  Without GIL: two threads could simultaneously modify an object's refcount
  → race condition → memory corruption → crashes.
  GIL is the simple solution: only one thread runs Python at a time.

IMPACT ON CONCURRENCY:
  ┌──────────────────┬─────────────────────────────────────────────┐
  │ Work Type        │ GIL Impact                                  │
  ├──────────────────┼─────────────────────────────────────────────┤
  │ I/O-bound thread │ GIL RELEASED during I/O wait → works well   │
  │ CPU-bound thread │ GIL NOT released → NO speedup from threads  │
  │ asyncio          │ Single thread → no GIL contention at all    │
  │ multiprocessing  │ Separate processes → each has own GIL       │
  └──────────────────┴─────────────────────────────────────────────┘

GIL IS RELEASED WHEN:
  - During I/O operations (file read, network, socket)
  - During certain C extensions (numpy, pandas, PIL)
  - Every ~5ms (sys.getswitchinterval()) — gives other threads a chance

THE GIL IS NOT:
  - A problem for I/O-bound code (asyncio and threading both work)
  - A problem for CPU-bound code using multiprocessing

PYTHON 3.13 UPDATE:
  Python 3.13 introduces "no-GIL" mode (experimental, PEP 703).
  This will eventually allow true CPU parallelism with threads.

HOW:
  ┌────────────────────────────────────────────────────────────────┐
  │  Thread 1    Thread 2    Thread 3                              │
  │  ┌──────┐                                                      │
  │  │ GIL  │                                                      │
  │  │LOCKED│   waiting     waiting                                │
  │  └──────┘                                                      │
  │     │   release GIL (I/O wait)                                 │
  │     ▼   ┌──────┐                                               │
  │  sleep  │ GIL  │  waiting                                      │
  │         │LOCKED│                                               │
  │         └──────┘                                               │
  │            │   release GIL                                     │
  │            ▼   ┌──────┐                                        │
  │          done  │ GIL  │                                        │
  │                │LOCKED│                                        │
  │                └──────┘                                        │
  └────────────────────────────────────────────────────────────────┘
"""

import threading as _threading
import time as _time


def demonstrate_gil():
    """CPU-bound threading — GIL prevents speedup."""
    result = {"total": 0}
    lock = _threading.Lock()

    def cpu_work(n: int) -> None:
        total = sum(i * i for i in range(n))
        with lock:
            result["total"] += total

    n = 500_000

    # Single thread
    start = _time.perf_counter()
    cpu_work(n * 2)
    single_time = _time.perf_counter() - start

    # Two threads (same work split)
    start = _time.perf_counter()
    t1 = _threading.Thread(target=cpu_work, args=(n,))
    t2 = _threading.Thread(target=cpu_work, args=(n,))
    t1.start(); t2.start()
    t1.join(); t2.join()
    thread_time = _time.perf_counter() - start

    print(f"\nGIL demonstration:")
    print(f"  Single thread (n={n*2}): {single_time*1000:.1f}ms")
    print(f"  Two threads   (n={n} ea): {thread_time*1000:.1f}ms")
    print(f"  Speedup: {single_time/thread_time:.2f}x (expected ~1x due to GIL)")
    print(f"  → CPU-bound threading provides NO benefit due to GIL")


demonstrate_gil()


# ══════════════════════════════════════════════════════════════════════════════
# PART L: THREADING
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS THREADING?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Threading = Multiple threads in ONE process sharing the same memory.
WORKS WELL for I/O-bound tasks (GIL released during I/O).
DOES NOT HELP for CPU-bound tasks (GIL prevents true parallelism).

USE THREADING WHEN:
  - You must use a BLOCKING LIBRARY that doesn't support async
    (old database drivers, some http clients, legacy SDKs)
  - I/O-bound work that you can't convert to async
  - Background tasks (polling, monitoring)

THREAD SAFETY CONCERNS:
  - Threads SHARE memory → race conditions possible
  - Use Lock() to protect shared data
  - Better: use asyncio (single-threaded, no race conditions)

ThreadPoolExecutor:
  High-level interface — submit tasks, get futures back.
  Best for: running blocking I/O in threads while using asyncio.

  loop.run_in_executor(None, blocking_func, *args)
  → runs blocking_func in a thread pool, compatible with await
"""

from concurrent.futures import ThreadPoolExecutor, as_completed


def blocking_io_call(item: str, delay: float = 0.5) -> str:
    """Simulates a blocking I/O operation (old-style library)."""
    _time.sleep(delay)
    return f"Processed: {item}"


def threading_demo():
    """ThreadPoolExecutor for I/O-bound blocking calls."""
    items = [f"item_{i}" for i in range(8)]

    start = _time.perf_counter()
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(blocking_io_call, item, 0.3): item for item in items}
        results = []
        for future in as_completed(futures):
            item = futures[future]
            result = future.result()
            results.append(result)

    elapsed = _time.perf_counter() - start
    print(f"\nThreadPoolExecutor (8 tasks, 4 workers, 0.3s each):")
    print(f"  Time: {elapsed:.2f}s (sequential would be {8 * 0.3:.1f}s)")
    print(f"  Results: {len(results)} items processed")


threading_demo()


# Async + thread pool (run blocking code in async context)
async def async_with_threadpool():
    """Use run_in_executor to call blocking code in async context."""
    loop = asyncio.get_event_loop()

    start = _time.perf_counter()
    results = await asyncio.gather(*[
        loop.run_in_executor(None, blocking_io_call, f"item_{i}", 0.3)
        for i in range(6)
    ])
    elapsed = _time.perf_counter() - start
    print(f"\nrun_in_executor (6 blocking calls, async context):")
    print(f"  Time: {elapsed:.2f}s")


asyncio.run(async_with_threadpool())


# ══════════════════════════════════════════════════════════════════════════════
# PART M: MULTIPROCESSING
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS MULTIPROCESSING?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Multiprocessing = Multiple SEPARATE processes, each with own memory + GIL.
TRUE PARALLEL execution on multiple CPU cores.

WHY?
  - Bypasses GIL (each process has its own interpreter + GIL)
  - TRUE parallelism for CPU-bound work
  - Uses all available CPU cores

WHEN TO USE:
  - Heavy computation: ML preprocessing, image processing, parsing
  - Each task is independent (no shared state)
  - Need true parallelism across CPU cores

DRAWBACKS:
  - Overhead: each process needs its own Python interpreter
  - No shared memory (must use Manager or Pipe for communication)
  - Data must be serializable (picklable) to send between processes
  - High startup cost vs threads

ProcessPoolExecutor:
  High-level interface, similar to ThreadPoolExecutor.
  Distributes work across CPU cores.
"""

from concurrent.futures import ProcessPoolExecutor
import os


def cpu_intensive_task(n: int) -> int:
    """Genuinely CPU-bound — no I/O."""
    return sum(i * i for i in range(n))


def multiprocessing_demo():
    """Compare single-process vs multi-process for CPU-bound work."""
    tasks = [500_000] * 8  # 8 identical CPU-bound tasks

    # Single process (sequential)
    start = _time.perf_counter()
    single_results = [cpu_intensive_task(n) for n in tasks]
    single_time = _time.perf_counter() - start

    # Multi-process (parallel)
    start = _time.perf_counter()
    cpu_count = min(4, os.cpu_count() or 2)
    with ProcessPoolExecutor(max_workers=cpu_count) as executor:
        multi_results = list(executor.map(cpu_intensive_task, tasks))
    multi_time = _time.perf_counter() - start

    print(f"\nMultiprocessing demo (8 CPU-bound tasks):")
    print(f"  Single process:    {single_time:.2f}s")
    print(f"  Multi-process ({cpu_count}): {multi_time:.2f}s")
    speedup = single_time / multi_time if multi_time > 0 else 1
    print(f"  Speedup: {speedup:.1f}x (on {os.cpu_count()} core machine)")
    print(f"  Results match: {single_results == multi_results}")


# NOTE: multiprocessing requires if __name__ == '__main__' on Windows/macOS
# For this module, we call it conditionally
if __name__ == "__main__":
    multiprocessing_demo()
else:
    print("\n  (Multiprocessing demo skipped — must run as __main__ on some platforms)")


# ══════════════════════════════════════════════════════════════════════════════
# PART N: DECISION TABLE
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHEN TO USE WHAT? — THE COMPLETE DECISION TABLE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌──────────────────────┬─────────────┬──────────────┬───────────────────────┐
│ Scenario             │ Use         │ Why          │ Example               │
├──────────────────────┼─────────────┼──────────────┼───────────────────────┤
│ API calls (LLM, DB,  │ asyncio     │ GIL released │ 10 LLM calls at once  │
│ HTTP, any I/O)       │             │ during I/O   │ aiohttp, httpx async  │
├──────────────────────┼─────────────┼──────────────┼───────────────────────┤
│ Blocking lib that    │ Threading + │ Run blocking │ requests library,     │
│ won't go async       │ executor    │ in thread    │ old SQLite driver     │
├──────────────────────┼─────────────┼──────────────┼───────────────────────┤
│ CPU-bound work       │ Multiproc.  │ Bypasses GIL,│ Image processing,     │
│ (heavy computation)  │             │ true parallel│ ML preprocessing      │
├──────────────────────┼─────────────┼──────────────┼───────────────────────┤
│ Streaming data       │ Async       │ Process as   │ LLM token streaming   │
│ (token by token)     │ generators  │ it arrives   │ WebSocket feeds       │
├──────────────────────┼─────────────┼──────────────┼───────────────────────┤
│ Rate limiting API    │ asyncio     │ Simple        │ OpenAI 10 req/s limit │
│ calls                │ Semaphore   │ async-native │                       │
├──────────────────────┼─────────────┼──────────────┼───────────────────────┤
│ Task with deadline   │ asyncio     │ Cancel on    │ LLM 30s timeout       │
│                      │ wait_for()  │ timeout      │                       │
├──────────────────────┼─────────────┼──────────────┼───────────────────────┤
│ Critical cleanup     │ asyncio     │ Protect from │ DB write on cancel    │
│ on cancellation      │ shield()    │ cancellation │                       │
├──────────────────────┼─────────────┼──────────────┼───────────────────────┤
│ Background daemon    │ Threading   │ OS thread,   │ Log watcher, cron     │
│                      │ (daemon)    │ simple setup │                       │
└──────────────────────┴─────────────┴──────────────┴───────────────────────┘

GOLDEN RULES:
  1. For I/O-bound: asyncio is BEST (single thread, no overhead, no races)
  2. For CPU-bound: multiprocessing only (threads don't help, GIL blocks them)
  3. For blocking libs in async code: run_in_executor with ThreadPoolExecutor
  4. NEVER mix asyncio.run() inside an existing event loop
  5. ALWAYS add timeouts to external API calls

AGENTIC AI GOLDEN PATTERN:
  async def agent_loop():
      sem = asyncio.Semaphore(5)     # max 5 concurrent LLM calls
      async def call_model(prompt):
          async with sem:
              return await asyncio.wait_for(
                  llm.complete(prompt),
                  timeout=30.0     # never hang forever
              )
      results = await asyncio.gather(*[
          call_model(p) for p in prompts
      ], return_exceptions=True)    # don't fail everything on one error
"""

print("\n✅ 04_Async_Concurrency_Theory.py complete — all sections covered.")


# ══════════════════════════════════════════════════════════════════════════════
# Q&A — COMPREHENSIVE ASYNC/CONCURRENCY
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Q&A — MOST IMPORTANT INTERVIEW QUESTIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q1: What is the difference between concurrency and parallelism?
A:  Concurrency: dealing with multiple tasks at the same time (not necessarily simultaneously)
    - asyncio, threading: concurrent (tasks interleaved on one or few cores)
    Parallelism: executing multiple tasks SIMULTANEOUSLY
    - multiprocessing: truly parallel on multiple CPU cores
    Python's asyncio is concurrent, NOT parallel.

Q2: When does asyncio NOT help?
A:  asyncio is useless for CPU-bound work.
    If your task doesn't do any I/O (pure computation), there's nothing to
    overlap — the CPU is always working. Use multiprocessing instead.

Q3: What is the difference between asyncio.gather() and asyncio.wait()?
A:  gather(): runs coroutines concurrently, returns results in SAME ORDER as input
              simpler API, returns list
    wait():   more control — set timeout, return when FIRST completes or ALL complete
              returns (done, pending) sets, order not guaranteed
    Use gather() for most cases. Use wait() when you need first-to-finish semantics.

Q4: What happens if you call a regular (blocking) sleep in asyncio?
A:  time.sleep(5) inside async code BLOCKS the entire event loop!
    No other coroutine can run during those 5 seconds.
    Always use: await asyncio.sleep(5) (cooperative, releases event loop)

Q5: How do you share data between two coroutines safely?
A:  asyncio is single-threaded → NO race conditions naturally!
    You can use: asyncio.Queue (built-in, safe producer/consumer)
    For threads: use thread-safe queue.Queue or asyncio.Queue from same thread.
    For processes: use multiprocessing.Manager, Queue, or Pipe.

Q6: What is the difference between asyncio.Task and a coroutine?
A:  Coroutine: async def function — just an object, NOT running yet
    Task: coroutine wrapped and SCHEDULED in event loop, running concurrently
    asyncio.create_task(coro()) → immediately schedules for execution
    await coro() → runs sequentially (not scheduled as Task)

Q7: What is backpressure in async systems?
A:  Backpressure = when consumer is slower than producer, queue fills up.
    Solution: asyncio.Queue(maxsize=N) — producer blocks when queue is full.
    This naturally throttles the producer to match consumer speed.

Q8: Explain asyncio.shield() use case.
A:  When you have a critical operation (like DB write) and want to protect it
    from being cancelled if the outer task is cancelled (e.g., timeout).
    The outer task sees a TimeoutError, but the inner shielded coroutine
    continues running independently.
"""
