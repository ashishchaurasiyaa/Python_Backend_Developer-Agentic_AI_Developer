"""
Level 4 — Doc 6: Parallel Tool Calls (PRACTICAL)
==================================================
Topics:
  1. Sequential vs parallel comparison
  2. ThreadPoolExecutor for sync tools
  3. asyncio for async tools
  4. Timeouts per tool
  5. Partial failure handling
  6. Speedup measurement

Install: pip install openai aiohttp python-dotenv
Run: python 06_parallel_tool_calls_practical.py
"""

import os
import time
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


# ─────────────────────────────────────────────────────────────────────────────
# Mock tools with simulated latency
# ─────────────────────────────────────────────────────────────────────────────

def slow_weather(city: str) -> dict:
    """Simulates a 500ms weather API call."""
    time.sleep(0.5)
    fake = {"Mumbai": 32, "Delhi": 28, "Bangalore": 24}
    return {"city": city, "temp": fake.get(city, 25)}


def slow_stock(symbol: str) -> dict:
    """Simulates a 500ms stock API call."""
    time.sleep(0.5)
    fake = {"AAPL": 178.5, "TSLA": 245.8}
    return {"symbol": symbol, "price": fake.get(symbol, 0)}


TOOL_FUNCTIONS = {"slow_weather": slow_weather, "slow_stock": slow_stock}


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Sequential vs Parallel Comparison
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 1: Sequential vs Parallel Execution")
print("=" * 70)

# Simulate 5 tool calls (the kind LLM might make)
mock_tool_calls = [
    {"id": "1", "name": "slow_weather", "args": {"city": "Mumbai"}},
    {"id": "2", "name": "slow_weather", "args": {"city": "Delhi"}},
    {"id": "3", "name": "slow_weather", "args": {"city": "Bangalore"}},
    {"id": "4", "name": "slow_stock", "args": {"symbol": "AAPL"}},
    {"id": "5", "name": "slow_stock", "args": {"symbol": "TSLA"}},
]


def run_sequential(tool_calls):
    """Run tool calls one at a time."""
    results = {}
    for tc in tool_calls:
        results[tc["id"]] = TOOL_FUNCTIONS[tc["name"]](**tc["args"])
    return results


def run_parallel_threads(tool_calls, max_workers=10):
    """Run tool calls in parallel using thread pool."""
    def run_one(tc):
        return tc["id"], TOOL_FUNCTIONS[tc["name"]](**tc["args"])

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        return dict(ex.map(run_one, tool_calls))


# Measure both
print(f"\nRunning {len(mock_tool_calls)} tool calls (each takes 500ms)...")

t1 = time.time()
seq_results = run_sequential(mock_tool_calls)
seq_time = time.time() - t1

t2 = time.time()
par_results = run_parallel_threads(mock_tool_calls)
par_time = time.time() - t2

print(f"\nSequential time: {seq_time:.2f}s")
print(f"Parallel time:   {par_time:.2f}s")
print(f"Speedup:         {seq_time / par_time:.1f}x faster")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Async Tools (Better for Network I/O)
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 2: Async Tools — Better for I/O")
print("=" * 70)


async def async_weather(city: str) -> dict:
    """Async simulation of weather API."""
    await asyncio.sleep(0.5)  # Non-blocking sleep
    fake = {"Mumbai": 32, "Delhi": 28, "Bangalore": 24}
    return {"city": city, "temp": fake.get(city, 25)}


async def async_stock(symbol: str) -> dict:
    await asyncio.sleep(0.5)
    fake = {"AAPL": 178.5, "TSLA": 245.8}
    return {"symbol": symbol, "price": fake.get(symbol, 0)}


ASYNC_TOOLS = {"async_weather": async_weather, "async_stock": async_stock}


async def run_async_parallel(tool_calls):
    """Run all async tools in parallel."""
    async def run_one(tc):
        return tc["id"], await ASYNC_TOOLS[tc["name"]](**tc["args"])

    tasks = [run_one(tc) for tc in tool_calls]
    results = await asyncio.gather(*tasks)
    return dict(results)


async_tool_calls = [
    {"id": "1", "name": "async_weather", "args": {"city": "Mumbai"}},
    {"id": "2", "name": "async_weather", "args": {"city": "Delhi"}},
    {"id": "3", "name": "async_stock", "args": {"symbol": "AAPL"}},
]

t3 = time.time()
async_results = asyncio.run(run_async_parallel(async_tool_calls))
async_time = time.time() - t3

print(f"\nAsync parallel time: {async_time:.2f}s")
print(f"Results: {async_results}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Timeouts Per Tool
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 3: Timeouts Per Tool")
print("=" * 70)


def very_slow_tool(x: int) -> dict:
    """Simulates a hanging API."""
    time.sleep(5)
    return {"value": x}


def run_with_timeout(tool_calls, per_tool_timeout=2.0):
    """Run tool calls with per-tool timeout."""
    results = {}

    def run_one(tc):
        return TOOL_FUNCTIONS_WITH_SLOW[tc["name"]](**tc["args"])

    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_tc = {executor.submit(run_one, tc): tc for tc in tool_calls}
        for future, tc in future_to_tc.items():
            try:
                results[tc["id"]] = future.result(timeout=per_tool_timeout)
            except FutureTimeout:
                results[tc["id"]] = {"error": f"timeout after {per_tool_timeout}s"}
                future.cancel()
            except Exception as e:
                results[tc["id"]] = {"error": str(e)}
    return results


TOOL_FUNCTIONS_WITH_SLOW = {
    "slow_weather": slow_weather,
    "very_slow_tool": very_slow_tool
}

mixed_calls = [
    {"id": "1", "name": "slow_weather", "args": {"city": "Mumbai"}},
    {"id": "2", "name": "very_slow_tool", "args": {"x": 42}},  # Will time out
    {"id": "3", "name": "slow_weather", "args": {"city": "Delhi"}},
]

t4 = time.time()
results = run_with_timeout(mixed_calls, per_tool_timeout=1.0)
t4_elapsed = time.time() - t4

print(f"\nTotal time: {t4_elapsed:.2f}s (timeout was 1.0s)")
print(f"Results:")
for tc_id, r in results.items():
    print(f"  {tc_id}: {r}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Partial Failure Handling
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 4: Partial Failure Handling")
print("=" * 70)


def failing_tool(x: int) -> dict:
    """Sometimes fails."""
    if x == 13:
        raise ValueError("Unlucky number!")
    return {"value": x * 2}


def run_with_partial_failure(tool_calls):
    """Continue even if some tools fail."""
    results = {}

    def run_one(tc):
        try:
            return tc["id"], failing_tool(**tc["args"])
        except Exception as e:
            return tc["id"], {"error": str(e), "tool": tc["name"]}

    with ThreadPoolExecutor() as ex:
        results = dict(ex.map(run_one, tool_calls))
    return results


calls = [{"id": str(i), "name": "failing_tool", "args": {"x": i}} for i in [10, 13, 20, 30]]
results = run_with_partial_failure(calls)

print("\nResults (some failures):")
for tc_id, r in results.items():
    status = "✗" if "error" in r else "✓"
    print(f"  {status} {tc_id}: {r}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Concurrency Limit
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 5: Concurrency Limits (Respect API Limits)")
print("=" * 70)


def run_with_concurrency_limit(tool_calls, max_concurrent=2):
    """Limit how many tools run simultaneously."""
    def run_one(tc):
        return tc["id"], TOOL_FUNCTIONS[tc["name"]](**tc["args"])

    with ThreadPoolExecutor(max_workers=max_concurrent) as ex:
        return dict(ex.map(run_one, tool_calls))


print(f"\n10 tools, max 2 concurrent (each takes 500ms):")
big_calls = [{"id": str(i), "name": "slow_weather", "args": {"city": "Mumbai"}} for i in range(10)]

t5 = time.time()
results = run_with_concurrency_limit(big_calls, max_concurrent=2)
t5_elapsed = time.time() - t5
print(f"Time: {t5_elapsed:.2f}s (theoretical: 10/2 × 0.5s = 2.5s)")

t6 = time.time()
results = run_with_concurrency_limit(big_calls, max_concurrent=10)
t6_elapsed = time.time() - t6
print(f"Time with 10 concurrent: {t6_elapsed:.2f}s (theoretical: 0.5s)")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Real LLM Parallel Tool Use Demo
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 6: Real LLM Parallel Tool Use")
print("=" * 70)


def real_llm_parallel_demo():
    if not os.getenv("OPENAI_API_KEY"):
        print("Skipped (no API key)")
        return

    from openai import OpenAI
    client = OpenAI()

    schemas = [
        {
            "type": "function",
            "function": {
                "name": "slow_weather",
                "description": "Get weather for a city. Takes 500ms.",
                "parameters": {
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                    "required": ["city"]
                }
            }
        }
    ]

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Get weather for Mumbai, Delhi, Bangalore, Pune, and Chennai."}],
        tools=schemas,
        parallel_tool_calls=True
    )

    tcs = response.choices[0].message.tool_calls or []
    print(f"\nLLM requested {len(tcs)} parallel tool calls")

    # Execute in parallel
    def run_one(tc):
        args = json.loads(tc.function.arguments)
        return tc.id, slow_weather(**args)

    t = time.time()
    with ThreadPoolExecutor() as ex:
        results = dict(ex.map(run_one, tcs))
    elapsed = time.time() - t

    print(f"Executed in {elapsed:.2f}s (would be {len(tcs) * 0.5}s sequential)")
    for tc_id, r in results.items():
        print(f"  {r}")


real_llm_parallel_demo()


# ─────────────────────────────────────────────────────────────────────────────
# Exercises
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("EXERCISES")
print("=" * 70)
print("""
EASY:
1. Convert 3 of your sync tools to async equivalents. Measure speedup.
2. Add timeouts to parallel execution. Test with intentionally slow tools.

MEDIUM:
3. Implement a rate-limited parallel executor (max 10 calls/sec).
4. Add retry logic on failures (3 retries with exponential backoff).

HARD:
5. Build a "tool budget" — each request has 5 second total time budget,
   regardless of how many tools called.
6. Implement priority queue — important tools run first.

PRO:
7. Build a fully observable parallel system:
   - OpenTelemetry traces
   - Latency histograms per tool
   - P50/P99 latency metrics
   - Failure rate alerts
""")

if __name__ == "__main__":
    print("\n✅ Parallel tool calls — multiply your agent's throughput!")
