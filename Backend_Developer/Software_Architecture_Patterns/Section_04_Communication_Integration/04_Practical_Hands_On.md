# Lecture 4 — Practical Hands-On: Resilience Patterns

> **Theory file:** [04_Resilience_Patterns.md](04_Resilience_Patterns.md)

---

## 🎯 Is Practical Mein Kya Banayenge?

Production-ready resilience implementations:

1. ✅ **Timeout pattern** — proper async timeouts
2. ✅ **Retry with exponential backoff + jitter** (tenacity)
3. ✅ **Circuit breaker** with three states (custom + library)
4. ✅ **Bulkhead** with semaphore-based isolation
5. ✅ **Graceful failure** with fallbacks
6. ✅ **Combined patterns** stack
7. ✅ **Production HTTP client** wrapper
8. ✅ **Monitoring & metrics** with Prometheus
9. ✅ **Chaos engineering** simulation
10. ✅ **Real-world payment service** resilient calls

By end: aap **production-grade resilience** code likh sakte ho.

---

## 1. Project Structure

```
resilience_demo/
├── docker-compose.yml
├── README.md
│
├── patterns/
│   ├── timeout.py
│   ├── retry.py
│   ├── circuit_breaker.py
│   ├── bulkhead.py
│   └── fallback.py
│
├── combined/
│   ├── resilient_client.py     # All patterns combined
│   └── payment_service.py      # Real-world example
│
├── chaos/
│   ├── inject_failures.py
│   └── chaos_test.py
│
├── monitoring/
│   ├── metrics.py              # Prometheus metrics
│   └── grafana_dashboard.json
│
└── flaky_server/
    └── main.py                  # Simulated flaky service
```

---

## 2. Setup & Dependencies

```bash
pip install httpx
pip install tenacity              # Retry with backoff
pip install circuitbreaker         # Circuit breaker
pip install pybreaker              # Alternative breaker
pip install prometheus-client      # Metrics
pip install asyncio
```

---

## 3. ⏱️ Timeout Pattern

### Sync Timeout (`patterns/timeout.py`)

```python
"""
Timeout patterns for both sync and async code.
"""
import httpx
import asyncio
from typing import TypeVar, Callable, Awaitable

T = TypeVar('T')

# ─────────────────────────────────────────────────────────────
# PATTERN 1: HTTP timeout
# ─────────────────────────────────────────────────────────────
async def http_with_timeout(url: str, timeout_seconds: float = 5.0):
    """
    Always set timeout on HTTP calls!
    Never use defaults (often infinite or too long).
    """
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        print(f"Timeout after {timeout_seconds}s for {url}")
        raise

# ─────────────────────────────────────────────────────────────
# PATTERN 2: Generic async timeout wrapper
# ─────────────────────────────────────────────────────────────
async def with_timeout(
    coro: Awaitable[T],
    timeout_seconds: float,
    fallback: T = None,
) -> T:
    """
    Wrap any coroutine with timeout.
    Returns fallback if timeout exceeded.
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        print(f"Timeout after {timeout_seconds}s")
        if fallback is not None:
            return fallback
        raise

# ─────────────────────────────────────────────────────────────
# PATTERN 3: Layered timeouts (different per operation)
# ─────────────────────────────────────────────────────────────
class TimeoutConfig:
    """Tune timeouts based on real-world latency data"""
    CACHE_READ = 0.1      # 100ms
    DB_QUERY = 1.0         # 1s
    INTERNAL_API = 3.0     # 3s
    EXTERNAL_API = 10.0    # 10s
    ML_INFERENCE = 30.0    # 30s

# Usage
async def fetch_user_profile(user_id: int):
    # Fast cache check first
    cached = await with_timeout(
        cache.get(user_id),
        TimeoutConfig.CACHE_READ
    )
    if cached:
        return cached
    
    # DB query if cache miss
    user = await with_timeout(
        db.query(f"SELECT * FROM users WHERE id={user_id}"),
        TimeoutConfig.DB_QUERY
    )
    return user

# ─────────────────────────────────────────────────────────────
# DEMO
# ─────────────────────────────────────────────────────────────
async def slow_operation():
    await asyncio.sleep(10)
    return "result"

async def demo():
    try:
        # Will timeout after 2 seconds
        result = await with_timeout(slow_operation(), timeout_seconds=2.0)
    except asyncio.TimeoutError:
        print("✓ Timed out as expected")

if __name__ == "__main__":
    asyncio.run(demo())
```

---

## 4. 🔁 Retry Pattern with Tenacity

### `patterns/retry.py`

```python
"""
Production-grade retry patterns using tenacity.
"""
import httpx
import asyncio
import random
import logging
from tenacity import (
    retry,
    stop_after_attempt,
    stop_after_delay,
    wait_exponential,
    wait_random,
    wait_exponential_jitter,
    retry_if_exception_type,
    retry_if_result,
    before_sleep_log,
    RetryError,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# PATTERN 1: Simple retry with exponential backoff
# ─────────────────────────────────────────────────────────────
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    before_sleep=lambda r: logger.warning(
        f"Attempt {r.attempt_number} failed, waiting..."
    ),
)
async def call_with_retry(url: str):
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()

# ─────────────────────────────────────────────────────────────
# PATTERN 2: Retry with EXPONENTIAL BACKOFF + JITTER (BEST!)
# ─────────────────────────────────────────────────────────────
@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential_jitter(initial=1, max=10, exp_base=2, jitter=2),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
async def call_with_jitter(url: str):
    """
    Best-practice retry:
    - Exponential backoff: 1, 2, 4, 8, 16s
    - + jitter: prevents thundering herd
    - Only retries network/5xx errors
    """
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()

# ─────────────────────────────────────────────────────────────
# PATTERN 3: Retry with timeout cap (give up after total time)
# ─────────────────────────────────────────────────────────────
@retry(
    stop=stop_after_delay(30),  # Give up after 30s TOTAL
    wait=wait_exponential(multiplier=1, max=10),
)
async def call_with_max_duration(url: str):
    """Retry until either success or total 30s elapsed"""
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()

# ─────────────────────────────────────────────────────────────
# PATTERN 4: Only retry SOME errors (don't retry 4xx!)
# ─────────────────────────────────────────────────────────────
def is_retryable(exception):
    """Decide what's worth retrying"""
    if isinstance(exception, httpx.HTTPStatusError):
        status = exception.response.status_code
        # Retry on 5xx, not 4xx (client errors won't change)
        return status >= 500
    if isinstance(exception, httpx.RequestError):
        return True  # Network errors - retry
    return False

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, max=10),
    retry=retry_if_exception_type(httpx.HTTPError) & ~retry_if_result(lambda x: x is None),
)
async def smart_retry(url: str):
    """Only retry transient/server errors"""
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        if 400 <= response.status_code < 500:
            return None  # Client error - don't retry
        response.raise_for_status()
        return response.json()

# ─────────────────────────────────────────────────────────────
# PATTERN 5: Manual retry with custom jitter
# ─────────────────────────────────────────────────────────────
async def custom_retry(url: str, max_attempts: int = 3):
    """
    Full control over retry logic.
    Educational - usually use tenacity instead.
    """
    last_exception = None
    
    for attempt in range(max_attempts):
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.json()
        
        except Exception as e:
            last_exception = e
            
            if attempt == max_attempts - 1:
                # Last attempt - give up
                raise
            
            # Calculate backoff with jitter
            base_delay = 2 ** attempt  # 1, 2, 4
            jitter = random.uniform(0, base_delay * 0.5)  # 0-50% extra
            total_delay = base_delay + jitter
            
            logger.warning(
                f"Attempt {attempt + 1} failed: {e}. "
                f"Retrying in {total_delay:.2f}s"
            )
            await asyncio.sleep(total_delay)

# ─────────────────────────────────────────────────────────────
# DEMO
# ─────────────────────────────────────────────────────────────
async def demo():
    """Test against flaky service"""
    try:
        result = await call_with_jitter("http://localhost:8080/flaky")
        print(f"✓ Got: {result}")
    except RetryError as e:
        print(f"✗ All retries exhausted: {e}")

if __name__ == "__main__":
    asyncio.run(demo())
```

---

## 5. 🔌 Circuit Breaker Pattern

### Custom Circuit Breaker (`patterns/circuit_breaker.py`)

```python
"""
Production circuit breaker with three states: CLOSED, OPEN, HALF_OPEN.
"""
import asyncio
import time
from enum import Enum
from typing import Callable, Optional, Awaitable, TypeVar
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class CircuitBreakerError(Exception):
    """Raised when circuit is open"""
    pass

class CircuitBreaker:
    """
    Three-state circuit breaker.
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Failing too much, reject immediately
    - HALF_OPEN: Test one request, then decide
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        expected_exceptions: tuple = (Exception,),
        name: str = "default",
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exceptions = expected_exceptions
        self.name = name
        
        # State
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.success_count = 0
    
    async def call(self, func: Callable[..., Awaitable[T]], *args, **kwargs) -> T:
        """Execute function with circuit breaker logic"""
        
        # Check current state
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self._transition_to(CircuitState.HALF_OPEN)
            else:
                raise CircuitBreakerError(
                    f"Circuit '{self.name}' is OPEN. "
                    f"Failing fast. Will retry in {self._time_until_retry():.1f}s"
                )
        
        # Try the call
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        
        except self.expected_exceptions as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        """Handle successful call"""
        if self.state == CircuitState.HALF_OPEN:
            # Test request succeeded → restore service
            logger.info(f"Circuit '{self.name}' test succeeded → CLOSED")
            self._transition_to(CircuitState.CLOSED)
            self.failure_count = 0
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            self.failure_count = 0
    
    def _on_failure(self):
        """Handle failed call"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            # Test request failed → back to OPEN
            logger.warning(f"Circuit '{self.name}' test failed → OPEN")
            self._transition_to(CircuitState.OPEN)
        
        elif self.state == CircuitState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                logger.warning(
                    f"Circuit '{self.name}' threshold reached "
                    f"({self.failure_count}) → OPEN"
                )
                self._transition_to(CircuitState.OPEN)
    
    def _should_attempt_reset(self) -> bool:
        """Check if it's time to try recovering"""
        if self.last_failure_time is None:
            return True
        return time.time() - self.last_failure_time >= self.recovery_timeout
    
    def _time_until_retry(self) -> float:
        if self.last_failure_time is None:
            return 0
        return max(0, self.recovery_timeout - (time.time() - self.last_failure_time))
    
    def _transition_to(self, new_state: CircuitState):
        old_state = self.state
        self.state = new_state
        logger.info(f"Circuit '{self.name}': {old_state.value} → {new_state.value}")
    
    @property
    def metrics(self) -> dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "failures": self.failure_count,
            "threshold": self.failure_threshold,
        }

# ─────────────────────────────────────────────────────────────
# USAGE
# ─────────────────────────────────────────────────────────────
import httpx

payment_breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=30,
    expected_exceptions=(httpx.RequestError, httpx.HTTPStatusError),
    name="payment_service",
)

async def call_payment(amount: float):
    """Call payment service through circuit breaker"""
    async def _call():
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                "http://payment-service/charge",
                json={"amount": amount}
            )
            response.raise_for_status()
            return response.json()
    
    return await payment_breaker.call(_call)

# Usage with fallback
async def process_payment(amount):
    try:
        return await call_payment(amount)
    except CircuitBreakerError:
        # Circuit open - use fallback
        print("Payment service circuit open. Using fallback.")
        return {"status": "queued", "message": "Will retry later"}
```

### Using circuitbreaker Library (Simpler)

```python
from circuitbreaker import circuit
import httpx

@circuit(
    failure_threshold=5,
    recovery_timeout=30,
    expected_exception=httpx.HTTPError,
)
async def call_external_api(url: str):
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()
```

---

## 6. 🚢 Bulkhead Pattern

### `patterns/bulkhead.py`

```python
"""
Bulkhead pattern: isolate resources between dependencies.
"""
import asyncio
from typing import Dict, Callable, Awaitable, TypeVar
import time

T = TypeVar('T')

class Bulkhead:
    """
    Limit concurrent calls per dependency.
    Like ship compartments - isolate failures.
    """
    
    def __init__(self, name: str, max_concurrent: int):
        self.name = name
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.max_concurrent = max_concurrent
        self.active = 0
        self.rejected = 0
        self.completed = 0
    
    async def call(self, func: Callable[..., Awaitable[T]], *args, **kwargs) -> T:
        """Execute function with concurrency limit"""
        
        # Try to acquire (non-blocking)
        if not self.semaphore.locked():
            await self.semaphore.acquire()
        else:
            # Pool full - this prevents resource exhaustion
            self.rejected += 1
            raise BulkheadFullError(
                f"Bulkhead '{self.name}' is FULL "
                f"({self.max_concurrent} concurrent calls)"
            )
        
        try:
            self.active += 1
            result = await func(*args, **kwargs)
            self.completed += 1
            return result
        finally:
            self.active -= 1
            self.semaphore.release()
    
    @property
    def metrics(self) -> dict:
        return {
            "name": self.name,
            "active": self.active,
            "completed": self.completed,
            "rejected": self.rejected,
            "max_concurrent": self.max_concurrent,
        }

class BulkheadFullError(Exception):
    """Raised when bulkhead is full"""
    pass

# ─────────────────────────────────────────────────────────────
# USAGE
# ─────────────────────────────────────────────────────────────

# Different bulkheads for different dependencies
payment_bulkhead = Bulkhead("payment", max_concurrent=50)
inventory_bulkhead = Bulkhead("inventory", max_concurrent=100)
recommendations_bulkhead = Bulkhead("recommendations", max_concurrent=20)  # Low priority

async def call_payment(amount):
    async def _call():
        # Actual payment API call
        await asyncio.sleep(0.5)
        return {"status": "ok"}
    
    return await payment_bulkhead.call(_call)

async def call_inventory(sku):
    async def _call():
        await asyncio.sleep(0.1)
        return {"stock": 100}
    
    return await inventory_bulkhead.call(_call)

# ─────────────────────────────────────────────────────────────
# DEMO: Show isolation
# ─────────────────────────────────────────────────────────────
async def demo():
    """If payment is slow, inventory should still work fast"""
    
    # Simulate slow payment
    async def slow_payment():
        await asyncio.sleep(10)
        return "ok"
    
    # 60 concurrent payment calls (exceeds limit of 50)
    payment_tasks = [
        payment_bulkhead.call(slow_payment) 
        for _ in range(60)
    ]
    
    # 10 inventory calls (should NOT be affected!)
    async def fast_inventory():
        await asyncio.sleep(0.1)
        return "stock_ok"
    
    inventory_tasks = [
        inventory_bulkhead.call(fast_inventory) 
        for _ in range(10)
    ]
    
    # Run all together
    results = await asyncio.gather(
        *payment_tasks,
        *inventory_tasks,
        return_exceptions=True
    )
    
    payment_results = results[:60]
    inventory_results = results[60:]
    
    payment_succeeded = sum(1 for r in payment_results if not isinstance(r, Exception))
    payment_rejected = sum(1 for r in payment_results if isinstance(r, BulkheadFullError))
    inventory_succeeded = sum(1 for r in inventory_results if not isinstance(r, Exception))
    
    print(f"Payment - succeeded: {payment_succeeded}, rejected: {payment_rejected}")
    print(f"Inventory - succeeded: {inventory_succeeded}/10")
    # Inventory should be 10/10 - bulkhead isolated it!

asyncio.run(demo())
```

---

## 7. 🛡️ Graceful Failure / Fallback

### `patterns/fallback.py`

```python
"""
Fallback patterns - graceful degradation.
"""
import asyncio
from typing import Callable, Awaitable, TypeVar, List, Optional

T = TypeVar('T')

# ─────────────────────────────────────────────────────────────
# PATTERN 1: Try → Fallback
# ─────────────────────────────────────────────────────────────
async def with_fallback(
    primary: Callable[..., Awaitable[T]],
    fallback: Callable[..., Awaitable[T]],
    *args, **kwargs
) -> T:
    """Try primary, use fallback on failure"""
    try:
        return await primary(*args, **kwargs)
    except Exception as e:
        print(f"Primary failed: {e}. Using fallback.")
        return await fallback(*args, **kwargs)

# ─────────────────────────────────────────────────────────────
# PATTERN 2: Chain of fallbacks
# ─────────────────────────────────────────────────────────────
async def with_fallback_chain(*sources):
    """Try sources in order until one succeeds"""
    last_error = None
    for source in sources:
        try:
            return await source()
        except Exception as e:
            last_error = e
            continue
    
    raise Exception(f"All fallbacks failed. Last error: {last_error}")

# Usage
async def get_user_data(user_id: int):
    """Try cache → DB → default in that order"""
    return await with_fallback_chain(
        lambda: cache.get(user_id),
        lambda: db.query(user_id),
        lambda: {"id": user_id, "name": "Guest"},  # Default
    )

# ─────────────────────────────────────────────────────────────
# PATTERN 3: Stale-while-revalidate (cache fallback)
# ─────────────────────────────────────────────────────────────
class StaleFallback:
    """Serve stale cache when live data fails"""
    
    def __init__(self, cache):
        self.cache = cache
    
    async def get(self, key: str, fetch_func: Callable):
        try:
            # Try fresh data
            data = await fetch_func()
            # Cache it
            await self.cache.set(key, data, ttl=300)
            return data
        except Exception:
            # Fall back to stale cache
            stale = await self.cache.get(f"stale:{key}")
            if stale:
                print(f"Serving stale data for {key}")
                return stale
            raise

# Usage
async def get_weather(city):
    return await stale_fallback.get(
        f"weather:{city}",
        fetch_func=lambda: weather_api.fetch(city)
    )

# ─────────────────────────────────────────────────────────────
# PATTERN 4: Partial response (degraded but functional)
# ─────────────────────────────────────────────────────────────
async def get_dashboard(user_id):
    """Return what we can, gracefully handle missing parts"""
    user = await safe_call(lambda: user_service.get(user_id), default={})
    orders = await safe_call(lambda: order_service.recent(user_id), default=[])
    recommendations = await safe_call(
        lambda: rec_service.get(user_id),
        default=[]  # Empty list if recommender down
    )
    
    return {
        "user": user,
        "orders": orders,
        "recommendations": recommendations,
        "_degraded": not all([user, orders, recommendations]),
    }

async def safe_call(func, default):
    try:
        return await func()
    except Exception as e:
        print(f"Safe call failed: {e}, using default")
        return default
```

---

## 8. 🎯 Combined Pattern Stack

### Production-Ready HTTP Client (`combined/resilient_client.py`)

```python
"""
All resilience patterns combined into one HTTP client.
"""
import httpx
import asyncio
import logging
from typing import Any
from tenacity import retry, stop_after_attempt, wait_exponential_jitter, retry_if_exception_type
from circuitbreaker import circuit
from prometheus_client import Counter, Histogram, Gauge

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# METRICS
# ─────────────────────────────────────────────────────────────
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['service', 'status']
)

http_request_duration = Histogram(
    'http_request_duration_seconds',
    'Request latency',
    ['service']
)

circuit_state = Gauge(
    'circuit_breaker_state',
    'Circuit breaker state (0=closed, 1=open)',
    ['service']
)

# ─────────────────────────────────────────────────────────────
# RESILIENT CLIENT
# ─────────────────────────────────────────────────────────────
class ResilientHTTPClient:
    """
    Production HTTP client combining:
    - Timeout (per request)
    - Retry (with jitter)
    - Circuit breaker
    - Bulkhead (semaphore)
    - Metrics
    """
    
    def __init__(
        self,
        service_name: str,
        base_url: str,
        max_concurrent: int = 50,
        timeout_seconds: float = 5.0,
        max_retries: int = 3,
        circuit_failure_threshold: int = 5,
    ):
        self.service_name = service_name
        self.base_url = base_url
        self.timeout = timeout_seconds
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.max_retries = max_retries
        
        # Circuit breaker decorator
        self._call_with_circuit = circuit(
            failure_threshold=circuit_failure_threshold,
            recovery_timeout=30,
            expected_exception=httpx.HTTPError,
        )(self._http_call)
    
    async def get(self, path: str, **kwargs) -> Any:
        return await self._make_request("GET", path, **kwargs)
    
    async def post(self, path: str, **kwargs) -> Any:
        return await self._make_request("POST", path, **kwargs)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=10, jitter=2),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        reraise=True,
    )
    async def _make_request(self, method: str, path: str, **kwargs) -> Any:
        """Make HTTP request with full resilience stack"""
        
        # Bulkhead: limit concurrent calls
        async with self.semaphore:
            with http_request_duration.labels(service=self.service_name).time():
                # Circuit breaker + timeout
                return await self._call_with_circuit(method, path, **kwargs)
    
    async def _http_call(self, method: str, path: str, **kwargs):
        """Actual HTTP call"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(
                    method,
                    f"{self.base_url}{path}",
                    **kwargs
                )
                response.raise_for_status()
                
                http_requests_total.labels(
                    service=self.service_name,
                    status=response.status_code
                ).inc()
                
                return response.json()
        
        except httpx.HTTPStatusError as e:
            http_requests_total.labels(
                service=self.service_name,
                status=e.response.status_code
            ).inc()
            raise
        
        except httpx.RequestError as e:
            http_requests_total.labels(
                service=self.service_name,
                status="error"
            ).inc()
            raise

# ─────────────────────────────────────────────────────────────
# USAGE
# ─────────────────────────────────────────────────────────────
payment_client = ResilientHTTPClient(
    service_name="payment",
    base_url="http://payment-service:8000",
    max_concurrent=50,
    timeout_seconds=5,
    max_retries=3,
    circuit_failure_threshold=5,
)

async def process_payment(amount: float):
    try:
        result = await payment_client.post(
            "/charge",
            json={"amount": amount}
        )
        return result
    except Exception as e:
        # All resilience exhausted - use fallback
        logger.error(f"Payment failed despite all retries: {e}")
        return {"status": "queued", "message": "Will retry async"}
```

---

## 9. 💳 Real-World Example: Payment Service

### `combined/payment_service.py`

```python
"""
Production payment integration with all resilience patterns.
"""
import asyncio
import logging
import uuid
from datetime import datetime
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential_jitter
from circuitbreaker import circuit

logger = logging.getLogger(__name__)

class PaymentService:
    """Resilient payment service integration"""
    
    def __init__(self, gateway_url: str):
        self.gateway_url = gateway_url
        self.semaphore = asyncio.Semaphore(50)  # Bulkhead
        self.processed_txns = set()  # Idempotency
    
    async def charge(self, user_id: int, amount: float, idempotency_key: str = None):
        """
        Charge user with full resilience.
        
        Layers:
        1. Idempotency (don't double-charge on retry)
        2. Bulkhead (limit concurrent calls)
        3. Circuit breaker (fail fast if dead)
        4. Retry (transient failures)
        5. Timeout (don't hang)
        6. Fallback (graceful degradation)
        """
        # 1. IDEMPOTENCY
        if not idempotency_key:
            idempotency_key = str(uuid.uuid4())
        
        if idempotency_key in self.processed_txns:
            logger.info(f"Duplicate request {idempotency_key}, returning cached")
            return {"status": "duplicate", "idempotency_key": idempotency_key}
        
        try:
            # 2. BULKHEAD
            async with self.semaphore:
                # 3-5: Circuit + Retry + Timeout
                result = await self._call_gateway(
                    user_id, amount, idempotency_key
                )
                self.processed_txns.add(idempotency_key)
                return result
        
        except Exception as e:
            # 6. FALLBACK
            logger.error(f"Payment failed: {e}. Queueing for async retry.")
            return await self._queue_for_async_retry(user_id, amount, idempotency_key)
    
    @circuit(
        failure_threshold=5,
        recovery_timeout=30,
        expected_exception=(httpx.HTTPError, asyncio.TimeoutError),
    )
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=5, jitter=1),
    )
    async def _call_gateway(self, user_id, amount, idempotency_key):
        """Actual gateway call with retry + circuit breaker"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{self.gateway_url}/charge",
                json={
                    "user_id": user_id,
                    "amount": amount,
                },
                headers={
                    "Idempotency-Key": idempotency_key,
                }
            )
            response.raise_for_status()
            return response.json()
    
    async def _queue_for_async_retry(self, user_id, amount, idempotency_key):
        """Fallback: queue for retry in background"""
        # Push to Kafka/RabbitMQ for delayed retry
        return {
            "status": "queued",
            "message": "Payment will be processed shortly",
            "idempotency_key": idempotency_key,
        }
```

---

## 10. 🎬 Chaos Testing

### `flaky_server/main.py`

```python
"""Simulated flaky service for testing resilience"""
from fastapi import FastAPI, HTTPException
import random
import asyncio
import time

app = FastAPI()

# Configurable failure modes
config = {
    "fail_rate": 0.5,         # 50% requests fail
    "slow_rate": 0.3,          # 30% requests are slow
    "down": False,             # Total outage
}

@app.get("/flaky")
async def flaky_endpoint():
    """Simulates various failure modes"""
    if config["down"]:
        raise HTTPException(503, "Service Unavailable")
    
    if random.random() < config["slow_rate"]:
        # Slow response (timeout territory)
        await asyncio.sleep(15)
    
    if random.random() < config["fail_rate"]:
        # Random error
        error_type = random.choice([500, 502, 503, 504])
        raise HTTPException(error_type, "Random failure")
    
    return {"status": "ok", "timestamp": time.time()}

@app.post("/config")
async def update_config(new_config: dict):
    """Update failure modes at runtime"""
    config.update(new_config)
    return config

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
```

### Chaos Test (`chaos/chaos_test.py`)

```python
"""Run resilience patterns against flaky service"""
import asyncio
import httpx
from patterns.retry import call_with_jitter
from patterns.circuit_breaker import CircuitBreaker

# Test scenarios
async def test_retry_handles_flakiness():
    """Verify retries succeed even when 50% fail"""
    success = 0
    failures = 0
    
    for i in range(20):
        try:
            await call_with_jitter("http://localhost:8080/flaky")
            success += 1
        except Exception:
            failures += 1
    
    print(f"Retry test: {success}/{20} succeeded")
    # Should be > 15/20 with retries

async def test_circuit_breaker_opens():
    """Verify circuit opens when service is fully down"""
    breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=10, name="test")
    
    # Mark service as down
    async with httpx.AsyncClient() as client:
        await client.post(
            "http://localhost:8080/config",
            json={"down": True}
        )
    
    # Make calls - should open circuit after 3 failures
    async def call_service():
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get("http://localhost:8080/flaky")
            response.raise_for_status()
            return response.json()
    
    for i in range(10):
        try:
            await breaker.call(call_service)
        except Exception as e:
            print(f"Call {i + 1}: {breaker.metrics}")
            if breaker.state.value == "open":
                print(f"✓ Circuit opened after {i + 1} calls")
                break

asyncio.run(test_retry_handles_flakiness())
asyncio.run(test_circuit_breaker_opens())
```

### Chaos Schedule

```python
"""Periodically inject failures to test resilience"""
import asyncio
import httpx
import random

async def chaos_monkey():
    """Randomly break things and observe behavior"""
    chaos_events = [
        {"fail_rate": 1.0, "duration": 30},     # Full outage 30s
        {"slow_rate": 0.9, "duration": 60},     # Mostly slow 60s
        {"fail_rate": 0.3, "duration": 120},    # Partial failure 2min
    ]
    
    while True:
        event = random.choice(chaos_events)
        duration = event.pop("duration")
        
        print(f"\n🔥 CHAOS: Applying {event} for {duration}s")
        
        async with httpx.AsyncClient() as client:
            # Apply chaos
            await client.post("http://localhost:8080/config", json=event)
            
            # Wait
            await asyncio.sleep(duration)
            
            # Reset
            await client.post(
                "http://localhost:8080/config",
                json={"fail_rate": 0, "slow_rate": 0, "down": False}
            )
        
        print("✓ Reset to normal\n")
        
        # Wait between chaos events
        await asyncio.sleep(60)

asyncio.run(chaos_monkey())
```

---

## 11. 📊 Monitoring with Prometheus

### `monitoring/metrics.py`

```python
"""Prometheus metrics for resilience patterns"""
from prometheus_client import Counter, Histogram, Gauge, start_http_server

# ─────────────────────────────────────────────────────────────
# METRICS
# ─────────────────────────────────────────────────────────────

# Retry metrics
RETRY_ATTEMPTS = Counter(
    'service_retry_attempts_total',
    'Total retry attempts',
    ['service', 'success']
)

# Circuit breaker
CIRCUIT_STATE = Gauge(
    'circuit_breaker_state',
    'State: 0=closed, 1=open, 2=half_open',
    ['service']
)

CIRCUIT_TRIPS = Counter(
    'circuit_breaker_trips_total',
    'Total times circuit opened',
    ['service']
)

# Timeouts
TIMEOUTS = Counter(
    'request_timeouts_total',
    'Total timeouts',
    ['service']
)

# Bulkhead
BULKHEAD_REJECTIONS = Counter(
    'bulkhead_rejections_total',
    'Calls rejected due to full pool',
    ['service']
)

BULKHEAD_ACTIVE = Gauge(
    'bulkhead_active_calls',
    'Currently active calls',
    ['service']
)

# Fallbacks
FALLBACK_INVOCATIONS = Counter(
    'fallback_invocations_total',
    'Times fallback was used',
    ['service']
)

# ─────────────────────────────────────────────────────────────
# Start metrics server
# ─────────────────────────────────────────────────────────────
start_http_server(9090)
print("Metrics available at http://localhost:9090/metrics")
```

### Grafana Dashboard Queries

```promql
# Retry success rate
sum(rate(service_retry_attempts_total{success="true"}[5m])) by (service)
/
sum(rate(service_retry_attempts_total[5m])) by (service)

# Circuit breaker state
circuit_breaker_state

# Timeouts per minute
rate(request_timeouts_total[1m])

# Bulkhead saturation
bulkhead_active_calls / bulkhead_max_concurrent

# Fallback rate (high = problem!)
rate(fallback_invocations_total[5m])
```

---

## 12. Key Learnings Summary

```
✅ Always set TIMEOUTS on external calls
✅ RETRY with exponential backoff + jitter (use tenacity)
✅ CIRCUIT BREAKER prevents cascading failures
✅ BULKHEAD isolates resources per dependency
✅ FALLBACKS keep UX smooth on failure
✅ COMBINE patterns: layered defense
✅ MONITOR everything (Prometheus + Grafana)
✅ TEST failure modes (chaos engineering)
✅ Idempotency makes retries SAFE

🎯 Production resilience stack:
   timeout(5s) → retry(3) → circuit_breaker → bulkhead → fallback
```

---

## 🎬 What's Next?

In **Lecture 5**, we'll bring it all together with **Building Fault Tolerant Systems** — end-to-end resilient architecture, chaos engineering, and SRE practices.

> **Next lecture:** [05_Building_Fault_Tolerant_Systems.md](05_Building_Fault_Tolerant_Systems.md)

---

## 📚 Try It Yourself

1. Build **resilient client** for a real API (e.g., Stripe)
2. Add **distributed tracing** to track retry/circuit state
3. Implement **adaptive timeout** based on rolling p99 latency
4. Build **chaos schedule** that runs nightly in staging
5. Create **Grafana dashboard** with all resilience metrics
