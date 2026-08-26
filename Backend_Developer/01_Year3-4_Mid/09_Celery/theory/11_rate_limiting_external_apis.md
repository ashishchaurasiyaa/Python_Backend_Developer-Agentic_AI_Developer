# Rate Limiting & External APIs — Celery Workers

## 1. The Problem

Celery workers often call external APIs (payment gateways, SMS providers, ML inference endpoints). These APIs have rate limits.

```
Your setup:        External API:
100 workers        allows 20 req/sec
     ↓
Each worker calls API → 100 req/sec → API returns 429 Too Many Requests
```

**Simply adding more workers makes it WORSE**, not better. You need controlled concurrency.

---

## 2. Solution 1 — Dedicated Queue with Limited Worker Concurrency (Simplest)

Route API-calling tasks to a separate queue, then run workers for that queue with `--concurrency=N` where N ≤ rate limit.

```bash
# Start ONLY 5 workers for the API queue → max 5 concurrent API calls
celery -A myapp worker -Q api_calls --concurrency=5 --loglevel=info

# Separate workers for non-API tasks (can have higher concurrency)
celery -A myapp worker -Q default --concurrency=20 --loglevel=info
```

```python
# settings / celery config
CELERY_TASK_ROUTES = {
    "tasks.call_external_api": {"queue": "api_calls"},
    "tasks.send_email":        {"queue": "default"},
}
```

**Works when:** rate limit is requests/concurrent, API has simple per-second limits.

---

## 3. Solution 2 — Redis-Based Semaphore (Precise Rate Limiting)

For APIs that allow, say, exactly 20 req/sec — use a sliding window counter in Redis.

```python
import redis
import time

r = redis.Redis()

def acquire_api_slot(api_name: str, max_per_second: int, timeout: float = 5.0) -> bool:
    """
    Sliding window rate limiter.
    Returns True if slot acquired, False if rate limit hit.
    """
    now = time.time()
    window_start = now - 1.0   # last 1 second
    key = f"ratelimit:{api_name}"

    pipe = r.pipeline()
    pipe.zremrangebyscore(key, 0, window_start)  # remove old entries
    pipe.zadd(key, {str(now): now})              # add current request
    pipe.zcard(key)                              # count in window
    pipe.expire(key, 2)                          # cleanup TTL
    _, _, count, _ = pipe.execute()

    if count > max_per_second:
        r.zrem(key, str(now))                    # rollback our addition
        return False
    return True


@app.task(bind=True, max_retries=10)
def call_payment_api(self, order_id: int, amount: float) -> dict:
    if not acquire_api_slot("razorpay", max_per_second=20):
        # Rate limited — retry with exponential backoff + jitter
        raise self.retry(
            exc=Exception("rate limited"),
            countdown=2 ** self.request.retries + random.uniform(0, 1)
        )
    # Proceed with API call
    return razorpay_client.charge(order_id, amount)
```

---

## 4. Solution 3 — Token Bucket per Worker (Smooth Rate Limiting)

Distribute rate limit across workers. If 20 req/sec and 4 workers → each worker gets 5 req/sec.

```python
import threading
import time

class TokenBucket:
    """Thread-safe token bucket for per-worker rate limiting."""

    def __init__(self, rate_per_sec: float, capacity: int):
        self.rate       = rate_per_sec
        self.capacity   = capacity
        self.tokens     = float(capacity)
        self.last_refill = time.monotonic()
        self._lock      = threading.Lock()

    def consume(self, tokens: int = 1) -> bool:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_refill
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_refill = now

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    def wait_and_consume(self, tokens: int = 1, max_wait: float = 10.0):
        start = time.monotonic()
        while time.monotonic() - start < max_wait:
            if self.consume(tokens):
                return
            time.sleep(0.05)
        raise TimeoutError("Could not acquire rate limit token in time")


# 5 req/sec per worker (20 total across 4 workers)
_api_bucket = TokenBucket(rate_per_sec=5, capacity=10)

@app.task
def call_sms_api(phone: str, message: str) -> dict:
    _api_bucket.wait_and_consume()
    return sms_client.send(phone, message)
```

---

## 5. Solution 4 — Circuit Breaker (Failure Protection)

When external API starts returning errors, stop hammering it. Open the circuit after N failures.

```python
import time
from enum import Enum

class State(Enum):
    CLOSED    = "closed"     # normal operation
    OPEN      = "open"       # failing fast
    HALF_OPEN = "half_open"  # testing recovery

class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=30):
        self.state     = State.CLOSED
        self.failures  = 0
        self.threshold = failure_threshold
        self.timeout   = recovery_timeout
        self.opened_at = 0.0

    def call(self, fn, *args, **kwargs):
        if self.state == State.OPEN:
            if time.time() - self.opened_at >= self.timeout:
                self.state = State.HALF_OPEN
            else:
                raise Exception(f"Circuit OPEN — API protected for {self.timeout}s")

        try:
            result = fn(*args, **kwargs)
            if self.state == State.HALF_OPEN:
                self.state    = State.CLOSED
                self.failures = 0
            return result
        except Exception:
            self.failures += 1
            if self.failures >= self.threshold:
                self.state    = State.OPEN
                self.opened_at = time.time()
            raise


_payment_cb = CircuitBreaker(failure_threshold=5, recovery_timeout=60)

@app.task(bind=True, max_retries=3)
def charge_card(self, order_id: int, amount: float) -> dict:
    try:
        return _payment_cb.call(payment_client.charge, order_id, amount)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
```

---

## 6. Retry-After Header Handling

Many APIs return `Retry-After` header on 429.

```python
import requests
from celery.exceptions import Retry

@app.task(bind=True, max_retries=8)
def call_openai(self, prompt: str) -> str:
    try:
        response = requests.post(
            "https://api.openai.com/v1/completions",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json={"model": "gpt-4", "prompt": prompt},
            timeout=30,
        )
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 5))
            raise self.retry(
                exc=Exception("rate limited"),
                countdown=retry_after + random.uniform(0, 2)   # +jitter
            )
        response.raise_for_status()
        return response.json()["choices"][0]["text"]
    except requests.RequestException as exc:
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
```

---

## 7. Choosing the Right Solution

| Scenario | Solution |
|----------|----------|
| Simple API, low volume | Dedicated queue + `--concurrency=N` |
| Precise req/sec limit | Redis sliding window semaphore |
| Smooth per-worker limiting | Token bucket |
| API going down frequently | Circuit breaker |
| API returns `Retry-After` | Parse header + countdown |
| All of the above | Layer them: concurrency + circuit breaker + retry |

---

## 8. What NOT to Do

```python
# ❌ WRONG: blindly increasing workers
celery worker --concurrency=100   # 100 concurrent calls to API that allows 20/sec

# ❌ WRONG: fixed sleep (thundering herd after sleep)
time.sleep(1)
retry()

# ❌ WRONG: retry without timeout
@app.task(bind=True)
def call_api(self):
    try:
        return slow_api()    # no timeout → worker hangs forever
    except Exception:
        raise self.retry()
```

---

## 9. Interview Questions

**Q: 100 Celery workers hain, API sirf 20 req/sec allow karta hai. Kya karoge?**
Dedicated queue + `--concurrency=5` (ya 4 workers of concurrency 5). Optional: Redis sliding window semaphore for precise enforcement. Retry with backoff + jitter for any 429 responses.

**Q: External API intermittently fail kar raha hai. Kaise handle karoge?**
Exponential backoff + jitter + max retries + `autoretry_for`. Circuit breaker after N consecutive failures. Alert on circuit open. `Retry-After` header parse karo on 429.

**Q: Circuit breaker ka HALF_OPEN state kyun hota hai?**
OPEN se directly CLOSED nahi jaate — pehle ek test request karte hain (HALF_OPEN). Agar succeed kare → CLOSED. Fail kare → wapas OPEN. Premature recovery se bachata hai.

**Q: Rate limiting aur retry mein jitter kyun zaroori hai?**
Bina jitter ke: 100 workers sab ek saath retry karte hain (thundering herd) → phir se 429. Jitter se retries spread ho jaate hain.
