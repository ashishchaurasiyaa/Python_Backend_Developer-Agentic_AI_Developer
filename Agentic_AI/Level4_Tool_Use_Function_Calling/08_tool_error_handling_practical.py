"""
Level 4 — Doc 8: Tool Error Handling (PRACTICAL)
==================================================
Topics:
  1. Safe tool call wrapper
  2. Retry with exponential backoff
  3. Args validation with Pydantic
  4. Tool timeout
  5. Circuit breaker
  6. Fallback chain
  7. Structured error logging

Install: pip install pydantic tenacity python-dotenv
Run: python 08_tool_error_handling_practical.py
"""

import os
import time
import json
import logging
import random
from datetime import datetime, timedelta
from functools import wraps
from typing import Callable, Optional
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Safe Tool Call Wrapper
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 1: Safe Tool Call Wrapper")
print("=" * 70)


def safe_tool_call(tool_func: Callable, args: dict) -> dict:
    """Wraps tool execution to never raise. Returns dict always."""
    try:
        result = tool_func(**args)
        if isinstance(result, dict):
            return result
        return {"value": result}
    except TypeError as e:
        return {"error": "invalid_args", "details": str(e)}
    except ConnectionError as e:
        return {"error": "network_error", "details": str(e)}
    except TimeoutError as e:
        return {"error": "timeout", "details": str(e)}
    except Exception as e:
        return {"error": "execution_failed", "details": str(e), "type": type(e).__name__}


def buggy_tool(x: int) -> dict:
    """Tool that raises various errors."""
    if x == 0:
        raise ValueError("Zero not allowed")
    if x == 1:
        raise ConnectionError("Network down")
    if x < 0:
        raise TypeError("Negative not supported")
    return {"value": x * 2}


for x in [5, 0, 1, -3]:
    result = safe_tool_call(buggy_tool, {"x": x})
    print(f"  buggy_tool(x={x}) → {result}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Retry with Exponential Backoff
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 2: Retry with Exponential Backoff")
print("=" * 70)


def with_retry(max_attempts: int = 3, base_delay: float = 0.5):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_attempts - 1:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(f"  Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                        time.sleep(delay)
            return {"error": "max_retries_exceeded", "details": str(last_error)}
        return wrapper
    return decorator


call_count = {"value": 0}


@with_retry(max_attempts=3, base_delay=0.2)
def flaky_tool() -> dict:
    """Fails first 2 times, succeeds on 3rd."""
    call_count["value"] += 1
    if call_count["value"] < 3:
        raise ConnectionError(f"Attempt {call_count['value']}: network glitch")
    return {"data": "success on attempt 3"}


print("\n[Calling flaky tool]")
result = flaky_tool()
print(f"Result: {result}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Pydantic Args Validation
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 3: Pydantic Args Validation Before Tool Call")
print("=" * 70)


def validate_and_call(model_class, tool_func, raw_args: dict) -> dict:
    """Validate args with Pydantic before calling tool."""
    try:
        from pydantic import BaseModel, ValidationError
        validated = model_class(**raw_args)
        return tool_func(**validated.model_dump())
    except ValidationError as e:
        return {
            "error": "invalid_args",
            "details": [{"field": err["loc"], "msg": err["msg"]} for err in e.errors()],
            "expected_schema": model_class.model_json_schema() if hasattr(model_class, "model_json_schema") else {}
        }


try:
    from pydantic import BaseModel, Field, ValidationError

    class WeatherArgs(BaseModel):
        city: str = Field(min_length=2, max_length=50)

    def get_weather(city: str) -> dict:
        return {"city": city, "temp": 28}

    test_args = [
        {"city": "Mumbai"},     # Valid
        {"city": "M"},          # Too short
        {"city": ""},           # Empty
        {},                     # Missing
        {"city": 123},          # Wrong type
    ]

    for args in test_args:
        result = validate_and_call(WeatherArgs, get_weather, args)
        print(f"  args={args} → {result}")
except ImportError:
    print("Install pydantic")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Tool Timeout
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 4: Tool Timeout")
print("=" * 70)


def with_timeout(tool_func: Callable, args: dict, timeout_sec: float = 2.0) -> dict:
    """Run tool with timeout. Cancel if too slow."""
    with ThreadPoolExecutor(max_workers=1) as ex:
        future = ex.submit(lambda: tool_func(**args))
        try:
            return future.result(timeout=timeout_sec)
        except FutureTimeout:
            return {"error": "timeout", "limit_seconds": timeout_sec}


def slow_tool(seconds: int = 5) -> dict:
    time.sleep(seconds)
    return {"completed_in": seconds}


print("  Fast call (1s, limit 2s):", with_timeout(slow_tool, {"seconds": 1}, timeout_sec=2))
print("  Slow call (5s, limit 2s):", with_timeout(slow_tool, {"seconds": 5}, timeout_sec=2))


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Circuit Breaker
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 5: Circuit Breaker")
print("=" * 70)


class CircuitBreaker:
    def __init__(self, threshold: int = 3, recovery_sec: int = 5):
        self.failures = 0
        self.threshold = threshold
        self.recovery_sec = recovery_sec
        self.open_until: Optional[datetime] = None

    def call(self, func: Callable, *args, **kwargs) -> dict:
        # Circuit open?
        if self.open_until and datetime.now() < self.open_until:
            return {"error": "circuit_open", "until": self.open_until.isoformat()}

        try:
            result = func(*args, **kwargs)
            self.failures = 0
            self.open_until = None
            return result if isinstance(result, dict) else {"value": result}
        except Exception as e:
            self.failures += 1
            if self.failures >= self.threshold:
                self.open_until = datetime.now() + timedelta(seconds=self.recovery_sec)
                self.failures = 0
                return {"error": "circuit_now_open", "details": str(e), "open_until": self.open_until.isoformat()}
            return {"error": "execution_failed", "details": str(e), "failures": self.failures}


breaker = CircuitBreaker(threshold=3, recovery_sec=2)

def always_fails():
    raise ConnectionError("Always broken")

print("\n[Calling always-failing tool 5 times with circuit breaker]")
for i in range(5):
    result = breaker.call(always_fails)
    print(f"  Call {i + 1}: {result}")
    time.sleep(0.3)

print(f"\n  Wait 2s for circuit to reset...")
time.sleep(2.1)
print(f"  Call 6: {breaker.call(always_fails)}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Fallback Chain
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 6: Fallback Chain — Primary → Secondary → Tertiary")
print("=" * 70)


def search_with_fallback(query: str) -> dict:
    """Try primary, then fallbacks."""
    providers = [
        ("primary", lambda q: {"error": "down"} if random.random() < 0.7 else {"results": [f"primary: {q}"]}),
        ("secondary", lambda q: {"error": "rate_limit"} if random.random() < 0.5 else {"results": [f"secondary: {q}"]}),
        ("tertiary", lambda q: {"results": [f"tertiary: {q}"]}),  # Always works
    ]

    for name, fn in providers:
        result = fn(query)
        if "error" not in result:
            return {"provider": name, **result}

    return {"error": "all_providers_failed"}


random.seed(42)
for i in range(5):
    result = search_with_fallback(f"query_{i}")
    print(f"  Query {i}: {result}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: Structured Error Logging
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 7: Structured Error Logging")
print("=" * 70)


def log_tool_event(name: str, args: dict, result: dict, latency: float):
    """Structured log for observability."""
    event = {
        "event": "tool_call",
        "tool_name": name,
        "args": args,
        "success": "error" not in result,
        "error_type": result.get("error"),
        "latency_ms": int(latency * 1000),
        "timestamp": datetime.now().isoformat()
    }
    if event["success"]:
        logger.info(f"TOOL OK: {json.dumps(event)}")
    else:
        logger.error(f"TOOL FAIL: {json.dumps(event)}")


def execute_with_logging(name: str, tool_func: Callable, args: dict) -> dict:
    start = time.time()
    result = safe_tool_call(tool_func, args)
    elapsed = time.time() - start
    log_tool_event(name, args, result, elapsed)
    return result


# Demo
execute_with_logging("buggy_tool", buggy_tool, {"x": 5})    # success
execute_with_logging("buggy_tool", buggy_tool, {"x": 0})    # failure
execute_with_logging("get_weather", get_weather, {"city": "Mumbai"})


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8: Full Production Pattern
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 8: Full Production Pattern")
print("=" * 70)


def production_tool_call(name: str, args: dict, tool_func: Callable,
                          timeout_sec: float = 5, max_retries: int = 2) -> dict:
    """All best practices combined: timeout + retry + safe + logging."""
    start = time.time()
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            # Timeout-protected call
            with ThreadPoolExecutor(max_workers=1) as ex:
                future = ex.submit(tool_func, **args)
                try:
                    result = future.result(timeout=timeout_sec)
                    result_dict = result if isinstance(result, dict) else {"value": result}
                    elapsed = time.time() - start
                    log_tool_event(name, args, result_dict, elapsed)
                    return result_dict
                except FutureTimeout:
                    last_error = f"timeout after {timeout_sec}s"
                    if attempt < max_retries:
                        time.sleep(0.5 * (2 ** attempt))
        except Exception as e:
            last_error = str(e)
            if attempt < max_retries:
                time.sleep(0.5 * (2 ** attempt))

    elapsed = time.time() - start
    result = {"error": "max_retries_exceeded", "details": last_error}
    log_tool_event(name, args, result, elapsed)
    return result


print("\n[Production-grade call]")
result = production_tool_call("get_weather", {"city": "Mumbai"}, get_weather)
print(f"Result: {result}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 9: Exercises
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 9: EXERCISES")
print("=" * 70)
print("""
EASY:
1. Wrap 5 of your existing tools with safe_tool_call. Test that they never raise.
2. Add @with_retry to a flaky tool. Test recovery from transient failures.

MEDIUM:
3. Use Pydantic to validate args for 3 tools. Test with invalid inputs.
4. Implement circuit breaker for an external API tool. Force failures, watch breaker open.

HARD:
5. Build fallback chain — primary tool → secondary → tertiary with different providers.
6. Build a tool error dashboard:
   - Error rate per tool (last hour)
   - P50/P99 latency
   - Most common error types

PRO:
7. Implement chaos engineering for your agent:
   - Random failure injection
   - Latency injection
   - Network partition simulation
   Verify agent degrades gracefully.
""")

if __name__ == "__main__":
    print("\n✅ Level 4 (Tool Use) complete! 🎉 Production-grade agent foundations done.")
