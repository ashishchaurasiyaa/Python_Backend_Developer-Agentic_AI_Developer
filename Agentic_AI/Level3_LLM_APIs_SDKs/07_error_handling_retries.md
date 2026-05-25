# Level 3 — Doc 7: Error Handling & Retries (Production)

> **Goal:** LLM calls fail. Network down, rate limits, timeouts. Production code MUST handle these.

---

## 1. Common Errors

| Error | Code | Cause |
|---|---|---|
| `RateLimitError` | 429 | Too many requests |
| `APITimeoutError` | — | Took too long |
| `APIConnectionError` | — | Network issue |
| `InternalServerError` | 500 | OpenAI's side |
| `BadRequestError` | 400 | Invalid request |
| `AuthenticationError` | 401 | Bad API key |
| `PermissionDeniedError` | 403 | Account issue |
| `NotFoundError` | 404 | Model doesn't exist |
| `UnprocessableEntityError` | 422 | Content issue |

**Most common in production:** 429 (rate limit) and 500 (server side).

---

## 2. Basic Try-Except

```python
from openai import OpenAI, RateLimitError, APITimeoutError, APIConnectionError

client = OpenAI(timeout=30.0)

def safe_call(messages):
    try:
        return client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages
        )
    except RateLimitError as e:
        print(f"Rate limited. Retry in {e.response.headers.get('retry-after', 60)}s")
        return None
    except APITimeoutError:
        print("Timeout")
        return None
    except APIConnectionError as e:
        print(f"Connection error: {e}")
        return None
    except Exception as e:
        print(f"Unknown error: {e}")
        return None
```

Better: use **tenacity** for production retry logic.

---

## 3. Tenacity (Production Standard)

```bash
pip install tenacity
```

```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)
from openai import RateLimitError, APITimeoutError, APIConnectionError

RETRYABLE_ERRORS = (RateLimitError, APITimeoutError, APIConnectionError)

@retry(
    retry=retry_if_exception_type(RETRYABLE_ERRORS),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    reraise=True
)
def robust_llm_call(messages, model="gpt-4o-mini"):
    return client.chat.completions.create(
        model=model,
        messages=messages,
        timeout=30
    )
```

This retries 5 times with exponential backoff (2s, 4s, 8s, 16s, 32s capped at 60s).

---

## 4. Exponential Backoff with Jitter

Without jitter, retries can synchronize → thundering herd.

```python
import random

@retry(
    retry=retry_if_exception_type(RETRYABLE_ERRORS),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60) +
         wait_random_exponential(min=0, max=2),  # Add jitter
    reraise=True
)
def robust_llm_call(messages):
    ...
```

---

## 5. Different Strategies for Different Errors

```python
from tenacity import retry_if_exception_type, retry_any

@retry(
    retry=retry_any(
        retry_if_exception_type(RateLimitError),  # Retry
        retry_if_exception_type(APITimeoutError),
        retry_if_exception_type(APIConnectionError),
    ),
    # NOT retried: BadRequestError, AuthenticationError (your fault)
    stop=stop_after_attempt(5),
    wait=wait_exponential(min=2, max=60),
)
def robust_call(messages):
    ...
```

**Don't retry:**
- BadRequestError (fix your code)
- AuthenticationError (check API key)
- NotFoundError (wrong model name)

---

## 6. Respect Rate Limit Headers

OpenAI returns headers indicating limits:
```
x-ratelimit-remaining-requests: 999
x-ratelimit-remaining-tokens: 9999
x-ratelimit-reset-requests: 1m23s
x-ratelimit-reset-tokens: 1m23s
```

```python
def smart_retry_on_429(messages):
    try:
        return client.chat.completions.create(...)
    except RateLimitError as e:
        retry_after = float(e.response.headers.get("retry-after", 60))
        time.sleep(retry_after + random.uniform(0, 2))
        return client.chat.completions.create(...)
```

---

## 7. Timeout Configuration

```python
# Global timeout
client = OpenAI(timeout=30.0)

# Per-call timeout
client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[...],
    timeout=10  # 10 seconds
)
```

For streaming, set per-chunk timeout:
```python
import httpx

client = OpenAI(
    timeout=httpx.Timeout(
        timeout=60.0,        # total
        connect=10.0,        # establish connection
        read=30.0,           # read each chunk
    )
)
```

---

## 8. Async Error Handling

```python
from openai import AsyncOpenAI
import asyncio

async_client = AsyncOpenAI()

@retry(
    retry=retry_if_exception_type(RETRYABLE_ERRORS),
    stop=stop_after_attempt(5),
    wait=wait_exponential(min=2, max=60),
)
async def async_robust_call(messages):
    return await async_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages
    )
```

For parallel calls:
```python
async def parallel_safe(prompts):
    tasks = [async_robust_call([{"role": "user", "content": p}]) for p in prompts]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    # Returns list of (response | Exception)
    
    # Handle individual failures
    success = [r for r in results if not isinstance(r, Exception)]
    failed = [(p, r) for p, r in zip(prompts, results) if isinstance(r, Exception)]
    
    return success, failed
```

---

## 9. Fallback Models

```python
def fallback_call(messages):
    """Try primary, fall back to others."""
    models = ["gpt-4o", "gpt-4o-mini", "claude-3-5-sonnet-20241022"]
    
    for model in models:
        try:
            return llm_call(messages, model=model)
        except (RateLimitError, InternalServerError):
            continue  # Try next model
    
    raise Exception("All models failed")
```

LiteLLM has built-in fallback:
```python
from litellm import completion

completion(
    model="gpt-4o",
    messages=messages,
    fallbacks=["gpt-4o-mini", "claude-3-5-haiku-20241022"]
)
```

---

## 10. Circuit Breaker

If an API is repeatedly failing, stop calling for a while:

```python
class CircuitBreaker:
    def __init__(self, threshold=5, recovery_sec=60):
        self.failures = 0
        self.threshold = threshold
        self.recovery_sec = recovery_sec
        self.open_until = None
    
    def call(self, func, *args, **kwargs):
        if self.open_until and time.time() < self.open_until:
            raise Exception(f"Circuit open until {self.open_until}")
        
        try:
            result = func(*args, **kwargs)
            self.failures = 0
            return result
        except Exception as e:
            self.failures += 1
            if self.failures >= self.threshold:
                self.open_until = time.time() + self.recovery_sec
                self.failures = 0
            raise

breaker = CircuitBreaker()
result = breaker.call(robust_llm_call, messages)
```

---

## 11. Graceful Degradation

```python
def serve_user(query):
    try:
        # Full pipeline
        return full_rag_pipeline(query)
    except LLMError:
        # Fallback: simpler response
        try:
            return simple_chat(query)
        except LLMError:
            # Last resort: static response
            return "I'm experiencing issues. Please try again later."
```

User always gets SOMETHING, even if degraded.

---

## 12. Logging Errors

```python
import logging

logger = logging.getLogger(__name__)

@retry(...)
def llm_call_with_logging(messages):
    try:
        return client.chat.completions.create(messages=messages)
    except RateLimitError as e:
        logger.warning("Rate limited", extra={
            "retry_after": e.response.headers.get("retry-after"),
            "request_id": e.request_id
        })
        raise
    except Exception as e:
        logger.error("LLM call failed", extra={
            "error_type": type(e).__name__,
            "error_message": str(e)
        }, exc_info=True)
        raise
```

---

## 13. Key Takeaways

✅ Use `tenacity` for production retries
✅ Exponential backoff + jitter
✅ Retry: rate limit, timeout, connection. Don't retry: bad request, auth
✅ Respect `retry-after` header for 429s
✅ Set sensible timeouts (30s typical)
✅ Implement fallback models (LiteLLM helps)
✅ Circuit breaker for repeatedly failing endpoints
✅ Graceful degradation — always return SOMETHING
✅ Log errors with context (request_id, type, retry count)

**Next:** [10_cost_optimization.md](10_cost_optimization.md) — Track and reduce LLM costs
