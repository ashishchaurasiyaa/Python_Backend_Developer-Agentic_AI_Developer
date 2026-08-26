"""
Async Timeouts — asyncio.timeout() and asyncio.wait_for()

Production mein timeout HAMESHA lagao — bina timeout ke ek slow API
poori service ko hang kar deta hai.

asyncio.wait_for(coro, timeout)  → Python 3.8+, popular
asyncio.timeout(seconds)         → Python 3.11+ context manager syntax
"""

import asyncio

# ─── wait_for() — most common ────────────────────────────────────────────

async def slow_db_query(seconds: float) -> dict:
    print(f"  [DB] Query started (will take {seconds}s)...")
    await asyncio.sleep(seconds)
    return {"rows": 42}

async def demo_wait_for():
    print("=== asyncio.wait_for() ===")

    # Case 1: Query completes in time
    try:
        result = await asyncio.wait_for(slow_db_query(0.2), timeout=1.0)
        print(f"  Success: {result}")
    except asyncio.TimeoutError:
        print(f"  Timeout! Query too slow")

    # Case 2: Query too slow → TimeoutError
    try:
        result = await asyncio.wait_for(slow_db_query(3.0), timeout=0.5)
        print(f"  Success: {result}")
    except asyncio.TimeoutError:
        print(f"  Timeout after 0.5s — returning fallback")
        result = {"rows": 0, "fallback": True}

asyncio.run(demo_wait_for())

# ─── asyncio.timeout() — Python 3.11+ context manager ───────────────────

async def demo_timeout_context_manager():
    print("\n=== asyncio.timeout() — Python 3.11+ ===")
    try:
        async with asyncio.timeout(0.3):
            print("  Starting slow operation...")
            await asyncio.sleep(2.0)   # This will timeout
            print("  Done (never reached)")
    except TimeoutError:
        print("  TimeoutError caught — operation took too long")

# asyncio.run(demo_timeout_context_manager())  # Uncomment if Python 3.11+

# ─── Retry with timeout — production pattern ─────────────────────────────

async def unreliable_api_call(attempt: int) -> str:
    """Simulates API that sometimes hangs, sometimes fails, sometimes works."""
    await asyncio.sleep(0.1 * attempt)  # Later attempts simulate slower network
    if attempt < 3:
        raise ConnectionError(f"API error on attempt {attempt}")
    return f"Success on attempt {attempt}"

async def call_with_retry_and_timeout(
    max_retries: int = 4,
    timeout_per_attempt: float = 0.5,
) -> str:
    for attempt in range(1, max_retries + 1):
        try:
            result = await asyncio.wait_for(
                unreliable_api_call(attempt),
                timeout=timeout_per_attempt,
            )
            return result
        except asyncio.TimeoutError:
            print(f"  Attempt {attempt}: TIMEOUT")
        except ConnectionError as e:
            print(f"  Attempt {attempt}: {e}")
    return "All retries exhausted"

async def demo_retry():
    print("\n=== Retry + Timeout pattern ===")
    result = await call_with_retry_and_timeout()
    print(f"  Final result: {result}")

asyncio.run(demo_retry())

# ─── Multiple operations with individual timeouts ─────────────────────────

async def fetch_with_timeout(name: str, delay: float, timeout: float):
    try:
        result = await asyncio.wait_for(asyncio.sleep(delay), timeout=timeout)
        return f"{name}: OK"
    except asyncio.TimeoutError:
        return f"{name}: TIMEOUT"

async def demo_parallel_with_timeouts():
    print("\n=== Parallel calls with individual timeouts ===")
    results = await asyncio.gather(
        fetch_with_timeout("payment-api",  delay=0.1, timeout=0.5),
        fetch_with_timeout("inventory-api", delay=1.5, timeout=0.5),  # will timeout
        fetch_with_timeout("user-api",     delay=0.2, timeout=0.5),
        return_exceptions=True,
    )
    for r in results:
        print(f"  {r}")

asyncio.run(demo_parallel_with_timeouts())

# SOCH:
# Q1: wait_for() timeout hit hone pe kya cancel hota hai?
#     (Underlying task cancel ho jaati hai — cleanup karna padta hai)
# Q2: Backend mein timeout kahan kahan lagana chahiye?
#     DB query, external API call, Redis call, file read — everywhere!
# Q3: Global timeout vs per-call timeout — kaunsa better?
#     Per-call better — different operations ke liye alag SLA hoti hai
