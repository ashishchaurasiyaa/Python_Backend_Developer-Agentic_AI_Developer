# Level 4 — Doc 8: Tool Error Handling

> **Goal:** Tools production mein fail karte hain. Network down, API timeout, invalid args. Graceful handling = robust agent.

---

## 1. What Can Go Wrong?

| Error | Cause | Fix |
|---|---|---|
| Network timeout | External API slow | Timeout + retry |
| Rate limit (429) | Too many calls | Exponential backoff |
| Invalid args | LLM gave wrong types | Pydantic validation |
| Tool exception | Bug in tool code | Catch + return error |
| Tool not found | LLM hallucinated tool | Validate against registry |
| Permission denied | Auth issue | Re-auth or surface to user |
| Resource not found | Bad ID | Return 404 to LLM, let it retry |
| Internal server error | Their bug | Retry or surface to user |

---

## 2. Pattern: Try-Catch Tool Wrapper

```python
def safe_tool_call(tool_func, args: dict) -> dict:
    """Always returns dict, never raises."""
    try:
        result = tool_func(**args)
        return result if isinstance(result, dict) else {"value": result}
    except TypeError as e:
        # Wrong args
        return {"error": "invalid_args", "details": str(e)}
    except ConnectionError as e:
        return {"error": "network_error", "details": str(e)}
    except TimeoutError as e:
        return {"error": "timeout", "details": str(e)}
    except Exception as e:
        # Catch-all
        return {"error": "execution_failed", "details": str(e), "type": type(e).__name__}
```

---

## 3. Pattern: Retry with Exponential Backoff

```python
import time
from functools import wraps

def with_retry(max_attempts=3, base_delay=1.0):
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
                        delay = base_delay * (2 ** attempt)  # 1s, 2s, 4s
                        time.sleep(delay)
            return {"error": "max_retries_exceeded", "details": str(last_error)}
        return wrapper
    return decorator

@with_retry(max_attempts=3)
def flaky_api_call(query):
    response = requests.get(...)
    response.raise_for_status()
    return response.json()
```

### Library: tenacity (production)
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(requests.RequestException)
)
def api_call(...):
    ...
```

---

## 4. Pattern: Send Errors Back to LLM

LLM can recover from errors if you tell it what went wrong:

```python
# Tool fails
result = {"error": "city_not_found", "details": "Could not find weather for 'Mubai' (did you mean 'Mumbai'?)"}

# Send error as tool result
messages.append({
    "role": "tool",
    "tool_call_id": tc.id,
    "content": json.dumps(result)
})

# LLM reads error, can adjust:
# Next iteration: try get_weather(city="Mumbai")
```

**For Anthropic:** Use `is_error: True` flag:
```python
{
    "type": "tool_result",
    "tool_use_id": "...",
    "content": "Error: City 'Mubai' not found",
    "is_error": True  # ← Signals failure
}
```

---

## 5. Pattern: Validate Args Before Calling

```python
from pydantic import BaseModel, ValidationError, Field

class WeatherArgs(BaseModel):
    city: str = Field(min_length=2, max_length=50)

def safe_get_weather(raw_args: dict) -> dict:
    try:
        args = WeatherArgs(**raw_args)
        return get_weather(args.city)
    except ValidationError as e:
        return {
            "error": "invalid_args",
            "details": e.errors()[0]["msg"],
            "schema": WeatherArgs.model_json_schema()
        }
```

LLM sees the error + schema → corrects next attempt.

---

## 6. Pattern: Timeout Per Tool

```python
import signal
from contextlib import contextmanager

class TimeoutError(Exception): pass

@contextmanager
def time_limit(seconds):
    def handler(signum, frame):
        raise TimeoutError(f"Timeout after {seconds}s")
    signal.signal(signal.SIGALRM, handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)

def tool_with_timeout(tool_func, args, timeout_sec=10):
    try:
        with time_limit(timeout_sec):
            return tool_func(**args)
    except TimeoutError as e:
        return {"error": "timeout", "details": str(e)}
```

For threads:
```python
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout

def tool_with_timeout(tool_func, args, timeout_sec=10):
    with ThreadPoolExecutor(max_workers=1) as ex:
        future = ex.submit(tool_func, **args)
        try:
            return future.result(timeout=timeout_sec)
        except FutureTimeout:
            return {"error": "timeout"}
```

---

## 7. Pattern: Circuit Breaker

Prevent cascading failures:

```python
from datetime import datetime, timedelta

class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_time_sec=60):
        self.failures = 0
        self.threshold = failure_threshold
        self.recovery = recovery_time_sec
        self.open_until = None
    
    def call(self, func, *args, **kwargs):
        # Circuit open? Refuse
        if self.open_until and datetime.now() < self.open_until:
            return {"error": "circuit_open", "retry_after": str(self.open_until)}
        
        try:
            result = func(*args, **kwargs)
            self.failures = 0  # Reset on success
            return result
        except Exception as e:
            self.failures += 1
            if self.failures >= self.threshold:
                # Open circuit
                self.open_until = datetime.now() + timedelta(seconds=self.recovery)
                self.failures = 0
            return {"error": str(e)}

# Usage
weather_breaker = CircuitBreaker()

def safe_weather(city):
    return weather_breaker.call(get_weather, city)
```

---

## 8. Pattern: Fallback Tools

```python
def search_with_fallback(query: str) -> dict:
    """Try Tavily, fall back to SerpAPI, then DuckDuckGo."""
    providers = [
        ("tavily", lambda q: tavily_search(q)),
        ("serpapi", lambda q: serpapi_search(q)),
        ("duckduckgo", lambda q: ddg_search(q)),
    ]
    
    for name, fn in providers:
        try:
            result = fn(query)
            if result.get("results"):
                return {"provider": name, **result}
        except Exception as e:
            continue  # Try next
    
    return {"error": "all_search_providers_failed"}
```

---

## 9. Pattern: Graceful Degradation

If non-critical tool fails, agent should continue:

```python
def agent_with_degradation(user_msg):
    optional_tools = ["get_user_history", "get_recommendations"]
    critical_tools = ["get_order_status", "process_refund"]
    
    for tc in response.tool_calls:
        result = safe_tool_call(tc.function.name, tc.args)
        
        if "error" in result:
            if tc.function.name in critical_tools:
                # Critical failure — surface to user
                return f"Sorry, I'm having trouble. Please try again."
            elif tc.function.name in optional_tools:
                # Non-critical — log and continue
                logger.warning(f"Optional tool {tc.function.name} failed: {result['error']}")
                result = {"warning": "data unavailable", "fallback": True}
        
        messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result)})
```

---

## 10. Error Logging & Monitoring

Production agents need observability:

```python
def log_tool_call(name, args, result, latency):
    """Structured logging for analysis."""
    logger.info({
        "event": "tool_call",
        "tool_name": name,
        "args": args,
        "success": "error" not in result,
        "error_type": result.get("error"),
        "latency_ms": int(latency * 1000),
        "timestamp": time.time()
    })
```

Track:
- Error rate per tool
- P50/P99 latency per tool
- Most common errors
- Retry success rate

---

## 11. User-Facing Error Messages

LLM may share tool errors with user. Make them helpful:

```python
# Bad — exposes internals
return {"error": "psycopg2.OperationalError: connection refused"}

# Good — user-actionable
return {"error": "database_unavailable", "user_message": "I can't access account info right now. Please try again in a few minutes."}
```

---

## 12. Common Mistakes

### ❌ Letting tools raise exceptions
```python
def get_weather(city):
    if not valid(city):
        raise ValueError("bad city")  # ← Crashes agent
```
**Fix:** Return error dicts.

### ❌ Generic catch-all without details
```python
except:
    return {"error": "something failed"}  # ← Useless to LLM
```
**Fix:** Include type, details, suggestions.

### ❌ Infinite retry without backoff
```python
while not success:
    try: ...
    except: continue  # ← DDoS your own API
```
**Fix:** Limit attempts + exponential backoff.

### ❌ No circuit breakers
External API goes down → your agent calls it 1M times.
**Fix:** Circuit breaker pattern.

---

## 13. Interview Questions

1. **Q: How do you handle tool failures gracefully?**
   - Try-catch wrappers, return error dicts, LLM can retry, circuit breakers for repeated failures

2. **Q: What's a circuit breaker?**
   - After N failures, "open" the circuit, refuse calls for cooldown period, retry later

3. **Q: How do you prevent infinite retry loops?**
   - max_attempts + exponential backoff (tenacity library)

4. **Q: Should errors go back to LLM or user?**
   - Critical/recoverable → LLM (it can retry). Catastrophic → user (with helpful message)

5. **Q: How do you debug tool failures in production?**
   - Structured logging, error rate dashboards, sample failed traces

---

## 14. Exercises

1. **Easy:** Wrap all tools with `safe_tool_call`. Verify they never raise.
2. **Medium:** Add `@with_retry` to a flaky tool. Test with intentional failures.
3. **Hard:** Implement circuit breaker for external API tool.
4. **Pro:** Build full observability — structured logs, dashboards, alerts on error spikes.

---

## 15. Key Takeaways

✅ Tools should NEVER raise — return error dicts
✅ Retry with exponential backoff (tenacity)
✅ Validate args with Pydantic before execution
✅ Send errors back to LLM (it can adjust)
✅ Use `is_error: True` for Anthropic
✅ Circuit breakers for repeated failures
✅ Fallback chains for critical paths
✅ Graceful degradation for optional tools
✅ Structured logging for observability

**Level 4 Complete!** 🎉 Tool use mastered. Next: Level 5 (RAG) or jump to Level 6 (Agent Patterns).
