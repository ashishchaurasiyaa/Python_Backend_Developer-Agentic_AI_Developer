# gRPC Resilience — Retries, Circuit Breakers, Deadlines, Backoff

## Quick Concepts

**WHAT:**
- **Retry** = Re-attempt failed RPC (transient errors only)
- **Backoff** = Wait time between retries (exponential + jitter)
- **Deadline** = Absolute time by which RPC must complete
- **Timeout** = Relative duration from RPC start (translates to deadline)
- **Circuit Breaker** = Stop calling failing service for cooldown period
- **Idempotency** = Safe to retry without side effects

**WHY resilience matters:**
- Distributed systems = networks fail, services crash, dependencies slow
- Without retries → transient errors become user-facing
- Without circuit breakers → cascading failures bring down whole system
- Without deadlines → goroutine/coroutine leaks, resource exhaustion

**HOW resilience layers work together:**
```
Client Request
    ↓
[Deadline = 5s]
    ↓
[Retry: max 3 attempts, exp backoff]
    ↓
[Circuit Breaker: skip if open]
    ↓
[Per-Try Timeout: 1s]
    ↓
gRPC Server
```

---

## Interview Questions & Answers

### Q1: gRPC retry policy kaise configure karte hain? Service Config kya hai?

**Answer:**

**WHAT:** gRPC service config = JSON-based runtime configuration for retries, LB, timeouts.

**WHY use built-in vs custom:**
- ✅ Standard across all gRPC clients (Python, Go, Java)
- ✅ Configurable via DNS TXT records or proxy
- ✅ Handles edge cases (pushback header, retry throttling)
- ❌ Limited to gRPC-defined retry conditions

**HOW — Service Config JSON:**

```python
import grpc
import json

# Service config defines retry policy per method
service_config = {
    "methodConfig": [{
        "name": [
            {"service": "userservice.UserService"}
            # Or specific: {"service": "userservice.UserService", "method": "GetUser"}
        ],
        "retryPolicy": {
            "maxAttempts": 5,                  # Initial attempt + 4 retries
            "initialBackoff": "0.1s",          # First retry after 100ms
            "maxBackoff": "10s",               # Cap at 10s
            "backoffMultiplier": 2,            # Exponential: 0.1 → 0.2 → 0.4 → 0.8s
            "retryableStatusCodes": [          # ⭐ ONLY these are retried
                "UNAVAILABLE",
                "DEADLINE_EXCEEDED",
                "RESOURCE_EXHAUSTED",
                # Note: ABORTED is sometimes retryable, depends on use case
                # NEVER retry: INVALID_ARGUMENT, NOT_FOUND, PERMISSION_DENIED, UNAUTHENTICATED
            ]
        },
        # OR hedging (more aggressive — send multiple in parallel)
        # "hedgingPolicy": {
        #     "maxAttempts": 3,
        #     "hedgingDelay": "0.5s",
        # }
    }]
}

channel = grpc.aio.secure_channel(
    "user-service:50051",
    credentials,
    options=[
        ("grpc.service_config", json.dumps(service_config)),
        ("grpc.enable_retries", 1),           # ⭐ MUST enable
    ]
)
```

**HOW — Per-call deadline:**
```python
import datetime

# Option 1: Timeout (relative)
response = await stub.GetUser(
    GetUserRequest(user_id=123),
    timeout=5.0       # 5 seconds from now
)

# Option 2: Deadline (absolute)
deadline = datetime.datetime.now() + datetime.timedelta(seconds=5)
response = await stub.GetUser(
    GetUserRequest(user_id=123),
    timeout=(deadline - datetime.datetime.now()).total_seconds()
)
```

---

### Q2: Retry kab karna hai aur kab NAHI karna hai?

**Answer:**

**WHAT:** gRPC status codes determine retry safety.

**WHY some codes shouldn't be retried:**
```
NOT_FOUND          → Resource doesn't exist (retry won't help)
PERMISSION_DENIED  → Auth/auth issue (retry = same denial)
INVALID_ARGUMENT   → Bad request (will fail again)
ALREADY_EXISTS     → Duplicate (retry creates more dupes!)
```

**HOW — Decision matrix:**

| Status Code | Retry? | Reason |
|---|---|---|
| `OK` | N/A | Success |
| `CANCELLED` | ⚠️ | Only if client didn't cancel |
| `UNKNOWN` | ❌ | Unknown error, unsafe |
| `INVALID_ARGUMENT` | ❌ | Bad input, will fail again |
| `DEADLINE_EXCEEDED` | ✅ | Network slow, try again |
| `NOT_FOUND` | ❌ | Resource missing |
| `ALREADY_EXISTS` | ❌ | Would duplicate |
| `PERMISSION_DENIED` | ❌ | Auth issue |
| `RESOURCE_EXHAUSTED` | ✅ | Rate limit/quota — backoff and retry |
| `FAILED_PRECONDITION` | ❌ | State issue, won't fix itself |
| `ABORTED` | ⚠️ | Concurrent op (transaction) — sometimes safe |
| `OUT_OF_RANGE` | ❌ | Pagination beyond end |
| `UNIMPLEMENTED` | ❌ | Method doesn't exist |
| `INTERNAL` | ⚠️ | Server bug — limited retries |
| `UNAVAILABLE` | ✅ | Transient (typical retry case) |
| `DATA_LOSS` | ❌ | Corruption, escalate |
| `UNAUTHENTICATED` | ❌ | Need to re-auth first |

**HOW — Idempotency check before retry:**

```python
async def safe_retry(operation, max_attempts=3, idempotent=False):
    """
    INTERVIEW: Retry only if operation is idempotent OR
    if we can guarantee no side effects on retry.
    """
    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await operation()
        except grpc.RpcError as e:
            last_error = e
            code = e.code()

            # Non-retryable codes
            if code in (grpc.StatusCode.INVALID_ARGUMENT,
                        grpc.StatusCode.NOT_FOUND,
                        grpc.StatusCode.PERMISSION_DENIED,
                        grpc.StatusCode.UNAUTHENTICATED):
                raise

            # Idempotency check for mutating operations
            if not idempotent and code in (grpc.StatusCode.UNKNOWN,
                                            grpc.StatusCode.INTERNAL):
                # Can't tell if previous call had side effect → don't retry
                raise

            # Calculate backoff with jitter
            backoff = min(0.1 * (2 ** (attempt - 1)), 10.0)
            jitter = backoff * 0.1 * random.random()
            await asyncio.sleep(backoff + jitter)

    raise last_error
```

---

### Q3: Exponential backoff with jitter — kya hai aur kyu zaruri hai?

**Answer:**

**WHAT:**
- **Exponential backoff** = wait time doubles after each retry
- **Jitter** = random offset added to backoff time

**WHY both needed:**

**Problem 1: Linear backoff**
```
Attempt 1 fails → wait 1s → retry
Attempt 2 fails → wait 1s → retry   ← Still hammering server
Attempt 3 fails → wait 1s → retry
```
Server stays overloaded.

**Problem 2: Pure exponential (no jitter)**
```
1000 clients all start at same time
All retry at t=1s, t=2s, t=4s, t=8s ← Synchronized waves
```
Server gets hit by waves of synchronized retries = "thundering herd"

**Solution: Exponential + Jitter**
```
Attempt 1 fails → wait 1s + rand(0..0.5)s → retry
Attempt 2 fails → wait 2s + rand(0..1)s → retry   ← Spread out
Attempt 3 fails → wait 4s + rand(0..2)s → retry
```

**HOW — Implementation:**

```python
import random
import asyncio

async def exponential_backoff_with_jitter(
    operation,
    max_attempts: int = 5,
    base_delay: float = 0.1,
    max_delay: float = 30.0,
    jitter_factor: float = 0.3,
):
    """
    INTERVIEW: Full backoff with jitter implementation.
    Formula: delay = min(base * 2^attempt, max) + random(0, delay * jitter)
    """
    for attempt in range(max_attempts):
        try:
            return await operation()
        except grpc.RpcError as e:
            if not _is_retryable(e):
                raise
            if attempt == max_attempts - 1:
                raise   # Last attempt — re-raise

            # ⭐ Exponential + jitter
            delay = min(base_delay * (2 ** attempt), max_delay)
            jitter = delay * jitter_factor * random.random()
            await asyncio.sleep(delay + jitter)


# Jitter strategies comparison:
# 1. Full jitter:   delay = random(0, base * 2^n)
# 2. Equal jitter:  delay = base * 2^n / 2 + random(0, base * 2^n / 2)
# 3. Decorrelated:  delay = random(base, previous_delay * 3)  ← AWS recommended
```

**AWS-recommended Decorrelated Jitter:**
```python
def decorrelated_jitter(previous_delay: float, base: float = 0.1, cap: float = 30.0):
    """
    AWS architecture blog recommendation:
    Less correlation between retries from different clients.
    """
    return min(cap, random.uniform(base, previous_delay * 3))


# Usage
previous = 0.1
for attempt in range(5):
    previous = decorrelated_jitter(previous)
    await asyncio.sleep(previous)
    try:
        return await operation()
    except RetryableError:
        continue
```

---

### Q4: Deadline vs Timeout — exact difference + propagation kaise karein?

**Answer:**

**WHAT:**
- **Timeout** = Duration (`5 seconds`)
- **Deadline** = Absolute time (`2024-01-15T10:30:00Z`)
- gRPC translates timeout → deadline at call time

**WHY deadline propagation is critical:**

```
Bad scenario without propagation:
Client → API Gateway (timeout 5s)
         ↓
         → Service A (timeout 5s)
                       ↓
                       → Service B (timeout 5s)
                                     ↓
                                     → DB query (no timeout!)

Total possible time: 5s + 5s + 5s + ∞ = 15s+ before client times out
Client already gave up at 5s, but services still working!
```

**HOW — Deadline propagation:**

```python
# Server interceptor: propagate deadline to downstream
class DeadlinePropagationInterceptor(grpc.aio.ServerInterceptor):
    async def intercept_service(self, continuation, handler_call_details):
        # Get incoming deadline
        # context.time_remaining() = seconds until deadline

        # When calling downstream:
        # Pass REMAINING time (not original timeout)
        return await continuation(handler_call_details)


# In service method
class ServiceA(service_pb2_grpc.ServiceAServicer):
    async def DoWork(self, request, context):
        remaining = context.time_remaining()
        if remaining < 1.0:
            # Less than 1s left — fail fast
            await context.abort(grpc.StatusCode.DEADLINE_EXCEEDED, "Not enough time")

        # ⭐ Pass remaining time to downstream call
        # Reserve some buffer (e.g., 100ms for response transit)
        downstream_timeout = max(0, remaining - 0.1)

        try:
            response = await downstream_stub.SomeMethod(
                request,
                timeout=downstream_timeout
            )
        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.DEADLINE_EXCEEDED:
                # Convert to clear error for upstream
                await context.abort(grpc.StatusCode.DEADLINE_EXCEEDED, "Downstream timeout")
            raise

        return response
```

**HOW — Set deadline in client:**

```python
# Option 1: Timeout (relative)
response = await stub.GetUser(
    GetUserRequest(user_id=123),
    timeout=5.0
)

# Option 2: Explicit deadline (absolute)
import time
deadline_ts = time.time() + 5.0  # 5s from now

# Note: gRPC Python uses timeout (relative) internally
# For deadline-style API:
response = await stub.GetUser(
    GetUserRequest(user_id=123),
    timeout=max(0, deadline_ts - time.time())
)
```

**HOW — Per-RPC vs per-channel deadlines:**

```python
# Per-channel default (applies to ALL RPCs unless overridden)
channel = grpc.aio.secure_channel(
    "user-service:50051",
    credentials,
    options=[("grpc.default_deadline", 5)]
)

# Per-RPC (overrides channel default)
response = await stub.GetUser(request, timeout=2.0)
```

---

### Q5: Circuit Breaker pattern — implement kaise karte ho?

**Answer:**

**WHAT:** Stop calling a failing service for cooldown period.

**WHY:**
- Failing service likely won't recover instantly
- Continuing to call wastes resources
- Cascading failure prevention

**HOW — Circuit breaker states:**
```
        ┌─────────────────┐
        │   CLOSED        │  ← Normal: all requests pass
        │  (healthy)      │
        └────────┬────────┘
                 │ failures > threshold
                 ↓
        ┌─────────────────┐
        │     OPEN        │  ← Fail fast: reject immediately
        │   (broken)      │  ← No requests to backend
        └────────┬────────┘
                 │ cooldown timer expires
                 ↓
        ┌─────────────────┐
        │  HALF_OPEN      │  ← Test: allow 1 request
        │  (testing)      │
        └────┬─────────┬──┘
             │         │
        success     failure
             │         │
             ↓         ↓
         CLOSED      OPEN
```

**HOW — Python implementation with pybreaker:**

```python
import pybreaker
import grpc

# Define breaker per downstream service
user_service_breaker = pybreaker.CircuitBreaker(
    fail_max=5,              # ⭐ Open after 5 consecutive failures
    reset_timeout=60,        # ⭐ Try again after 60s
    exclude=[ValueError],    # Don't count these as failures
    name="user_service"
)

@user_service_breaker
async def call_user_service(user_id: int):
    try:
        return await stub.GetUser(GetUserRequest(user_id=user_id), timeout=5)
    except grpc.RpcError as e:
        # Only count 5xx-like errors as "failures"
        if e.code() in (grpc.StatusCode.UNAVAILABLE,
                        grpc.StatusCode.INTERNAL,
                        grpc.StatusCode.DEADLINE_EXCEEDED):
            raise
        # Other errors (NOT_FOUND, INVALID_ARGUMENT) don't trip breaker
        return None


# Usage
try:
    user = await call_user_service(123)
except pybreaker.CircuitBreakerError:
    # Circuit is OPEN — use fallback
    user = None   # Or cached value, default, etc.
```

**HOW — Custom async circuit breaker (lightweight):**

```python
import asyncio
import time
from enum import Enum

class State(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class AsyncCircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=60, expected_exception=Exception):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self._failures = 0
        self._state = State.CLOSED
        self._opened_at = 0
        self._lock = asyncio.Lock()

    async def call(self, func, *args, **kwargs):
        async with self._lock:
            if self._state == State.OPEN:
                if time.time() - self._opened_at > self.recovery_timeout:
                    self._state = State.HALF_OPEN
                else:
                    raise Exception(f"Circuit OPEN, retry after {self._opened_at + self.recovery_timeout - time.time():.0f}s")

        try:
            result = await func(*args, **kwargs)
        except self.expected_exception:
            async with self._lock:
                self._failures += 1
                if self._failures >= self.failure_threshold:
                    self._state = State.OPEN
                    self._opened_at = time.time()
            raise

        # Success
        async with self._lock:
            self._failures = 0
            self._state = State.CLOSED
        return result
```

---

### Q6: Idempotency keys gRPC mein kaise pass karte ho?

**Answer:**

**WHAT:** Client-generated unique ID per logical request — server deduplicates retries.

**WHY:**
```
Scenario without idempotency:
Client → CreateOrder → Server creates order ✓
       (network blip, client times out)
Client retries → CreateOrder → Server creates ANOTHER order!
Result: Duplicate orders, customer charged twice
```

**HOW — Client-side idempotency key:**

```python
import uuid
import grpc

async def create_order_idempotent(order_data):
    # Generate ONE key for this logical operation
    idempotency_key = str(uuid.uuid4())

    metadata = [
        ("x-idempotency-key", idempotency_key),
    ]

    # Retry with SAME key
    for attempt in range(3):
        try:
            return await stub.CreateOrder(
                order_data,
                metadata=metadata,
                timeout=10
            )
        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.UNAVAILABLE:
                await asyncio.sleep(2 ** attempt)
                continue
            raise
```

**HOW — Server-side deduplication:**

```python
import redis.asyncio as redis

class OrderServiceServicer(order_pb2_grpc.OrderServiceServicer):
    def __init__(self):
        self.redis = redis.from_url("redis://redis:6379/3")

    async def CreateOrder(self, request, context):
        # ⭐ Extract idempotency key from metadata
        metadata = dict(context.invocation_metadata())
        idempotency_key = metadata.get("x-idempotency-key")

        if not idempotency_key:
            # Optional: require it for mutating operations
            await context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                "x-idempotency-key header required"
            )

        # ⭐ Check if we've seen this key (with response cached)
        cache_key = f"idempotency:{idempotency_key}"
        cached_response = await self.redis.get(cache_key)

        if cached_response:
            # Return same response as first call
            return order_pb2.Order.FromString(cached_response)

        # First time — process the request
        order = await self._create_order_in_db(request)
        response = self._order_to_proto(order)

        # ⭐ Cache response for 24 hours
        await self.redis.setex(
            cache_key,
            86400,
            response.SerializeToString()
        )

        return response
```

**HOW — Database-level idempotency (alternative):**

```sql
-- Use UNIQUE constraint on idempotency_key
CREATE TABLE orders (
    id BIGSERIAL PRIMARY KEY,
    idempotency_key UUID UNIQUE NOT NULL,
    user_id INT,
    amount DECIMAL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Try insert; if duplicate key, fetch existing
INSERT INTO orders (idempotency_key, user_id, amount)
VALUES ($1, $2, $3)
ON CONFLICT (idempotency_key)
DO UPDATE SET id = orders.id    -- noop, just to return row
RETURNING *;
```

---

### Q7: Hedged requests kya hai? Kab use karein?

**Answer:**

**WHAT:** Send N parallel requests, use the first response, cancel others.

**WHY:**
- Reduces tail latency (p99) significantly
- Useful when service has variable response times
- Trade-off: extra load on backend (2-3x requests)

**HOW — Service Config:**

```python
service_config = {
    "methodConfig": [{
        "name": [{"service": "userservice.UserService", "method": "GetUser"}],
        "hedgingPolicy": {
            "maxAttempts": 3,                 # Max 3 in flight
            "hedgingDelay": "0.5s",           # Send 2nd after 500ms if no response
            "nonFatalStatusCodes": [          # These don't stop hedging
                "DEADLINE_EXCEEDED",
                "UNAVAILABLE"
            ]
        }
    }]
}
```

**HOW — Behavior:**
```
t=0ms:    Send request #1
t=500ms:  No response yet → Send request #2 (in parallel)
t=750ms:  Request #1 responds with success → cancel request #2 → return
```

**When to use hedging:**
- ✅ Read operations (idempotent)
- ✅ Latency-sensitive (p99 matters more than load)
- ✅ Have spare backend capacity (handles 2-3x load)
- ❌ Write operations (could duplicate)
- ❌ Expensive operations (LLM calls, large queries)
- ❌ Rate-limited backends

---

### Q8: Bulkhead pattern — gRPC clients ko isolate kaise karte ho?

**Answer:**

**WHAT:** Isolate resources so failure in one area doesn't take down others.

**WHY:**
```
Without bulkhead:
- 1 thread pool for all downstream calls
- Slow service A consumes all threads
- Service B calls can't even start (resource starved)
- Whole app slows down

With bulkhead:
- Separate pool/semaphore per downstream service
- Slow service A only consumes its allocated pool
- Service B continues normally
```

**HOW — Semaphore-based bulkhead:**

```python
import asyncio
from collections import defaultdict

class BulkheadClient:
    """
    INTERVIEW: Limit concurrent calls per downstream service.
    Prevents one slow service from starving others.
    """
    def __init__(self):
        # Different limits per service
        self.semaphores = {
            "user_service":    asyncio.Semaphore(50),   # High capacity
            "payment_service": asyncio.Semaphore(20),   # Critical, limited
            "analytics":       asyncio.Semaphore(10),   # Low priority
        }
        self.timeouts = {
            "user_service":    5.0,
            "payment_service": 10.0,
            "analytics":       2.0,
        }

    async def call(self, service: str, operation):
        sem = self.semaphores.get(service)
        timeout = self.timeouts.get(service, 5.0)

        # ⭐ Bound by semaphore + timeout
        try:
            await asyncio.wait_for(sem.acquire(), timeout=1.0)
        except asyncio.TimeoutError:
            raise Exception(f"Bulkhead full for {service}")

        try:
            return await asyncio.wait_for(operation, timeout=timeout)
        finally:
            sem.release()


# Usage
bulkhead = BulkheadClient()

# Call user service (max 50 concurrent)
user = await bulkhead.call(
    "user_service",
    user_stub.GetUser(GetUserRequest(user_id=123))
)
```

---

## Resilience Configuration Template

```python
# resilience_config.py
RESILIENCE_DEFAULTS = {
    "max_retries":       3,
    "retry_backoff_base": 0.1,
    "retry_backoff_max":  10.0,
    "retry_jitter_factor": 0.3,
    "circuit_breaker_threshold": 5,
    "circuit_breaker_timeout":   60,
    "default_deadline":  5.0,
    "bulkhead_max_concurrent": 50,
}

# Per-service overrides
SERVICE_CONFIG = {
    "payment_service": {
        "max_retries": 5,
        "default_deadline": 10.0,
        "bulkhead_max_concurrent": 20,  # More limited
    },
    "llm_service": {
        "max_retries": 2,
        "default_deadline": 60.0,        # LLMs slow
        "bulkhead_max_concurrent": 10,
    },
}
```

---

## Common Resilience Pitfalls

| Pitfall | Impact | Fix |
|---|---|---|
| **Retry non-idempotent** | Duplicate operations | Use idempotency keys |
| **No deadline** | Goroutine/connection leaks | Always set deadline |
| **Deadline not propagated** | Wasted downstream work | Pass remaining time |
| **No jitter in backoff** | Thundering herd on recovery | Add randomness |
| **Retry on all errors** | Hammer broken service | Only retry transient codes |
| **No circuit breaker** | Cascading failures | Use pybreaker or custom |
| **Shared thread pool** | One slow service blocks all | Bulkhead pattern |
| **Too many retries** | Amplifies traffic during outage | Retry budget pattern |
