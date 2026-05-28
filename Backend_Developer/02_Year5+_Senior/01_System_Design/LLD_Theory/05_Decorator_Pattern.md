# Decorator Pattern
> **Category:** Structural | **Difficulty:** Medium | **Interview Frequency:** ★★★★☆

---

## Quick Reference Card
```
Kya karta hai : Original class change kiye bina nayi functionality wrap karke add karo
Kab use karo  : Logging, Caching, Auth check, Rate limiting, Retry logic
Key mechanism : Wrapper class jo same interface implement kare + extra kaam kare
Real project  : Niroskos → @transaction.atomic, @shared_task | Youngman → @login_required
Pattern type  : Structural
```

---

## PART 1: HINGLISH — Samjhne ke liye

### 1.1 Kya hai?

Decorator pattern mein **original object ko wrap karte ho** — uski functionality change kiye bina uske upar extra layer add karte ho.

**Simple analogy:**
```
Chai ka glass socho:
  Plain chai       = base object
  Chai + adrak     = decorator 1 (adrak wrap kiya)
  Chai + adrak + elaichi = decorator 2 (elaichi aur wrap kiya)
  Chai + adrak + elaichi + sugar = decorator 3

Har decorator original ke upar add hota hai.
Original chai change nahi hui — sirf wrapper badla.
```

---

### 1.2 Kab use karo?

```
✅ Logging          → Har function call se pehle/baad log karo
✅ Caching          → Result cache mein check karo, calculate mat karo dobara
✅ Authentication   → @login_required — check karo pehle, phir execute
✅ Rate Limiting    → 200 req/min limit — check karo, phir process
✅ Retry Logic      → Fail hua → dobara try karo automatically
✅ Transaction      → @transaction.atomic — success pe commit, fail pe rollback
✅ Timing/Profiling → Function kitni der mein chali — measure karo
✅ Validation       → Input validate karo pehle, phir process
```

---

### 1.3 Kab mat use karo?

```
❌ Core business logic change karna hai — Decorator nahi, class modify karo
❌ Zyada decorators ek saath → debugging mushkil (decorator hell)
❌ Decorator order matter karta hai aur samajhna mushkil ho
```

---

### 1.4 Code — Hinglish Comments ke saath

```python
import time
import functools
from typing import Callable

# ─── Pattern 1: Python Function Decorator (Tumhare projects mein yahi hai) ───

def log_execution(func):
    """
    Har function call ke liye log karo.
    Original function change nahi hui — bas wrap kiya.
    """
    @functools.wraps(func)  # Function ka naam/docstring preserve karo
    def wrapper(*args, **kwargs):
        print(f"[LOG] {func.__name__} start hua")
        start = time.time()
        result = func(*args, **kwargs)       # Original function call karo
        elapsed = time.time() - start
        print(f"[LOG] {func.__name__} khatam — {elapsed:.3f}s")
        return result
    return wrapper


def require_auth(func):
    """Authentication decorator — pehle check karo"""
    @functools.wraps(func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise PermissionError("Login required")
        return func(request, *args, **kwargs)  # Auth OK → original call
    return wrapper


def rate_limit(max_calls: int, window_seconds: int):
    """Rate limiting decorator — Exotel 200 req/min jaisa"""
    def decorator(func):
        call_times = []  # Last window mein calls

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            now = time.time()
            # Old calls window se bahar nikalo
            while call_times and now - call_times[0] > window_seconds:
                call_times.pop(0)

            if len(call_times) >= max_calls:
                raise Exception(f"Rate limit: {max_calls} calls per {window_seconds}s")

            call_times.append(now)
            return func(*args, **kwargs)
        return wrapper
    return decorator


def retry(max_attempts: int = 3, delay: float = 1.0, exceptions=(Exception,)):
    """
    Retry decorator — SAP HANA connector mein use kiya
    Fail hua → wait karo → dobara try karo
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_error = e
                    if attempt < max_attempts:
                        wait = delay * (2 ** (attempt - 1))  # Exponential backoff
                        print(f"[RETRY] Attempt {attempt} fail — {wait}s wait")
                        time.sleep(wait)
            raise last_error  # Sab attempts fail → error raise karo
        return wrapper
    return decorator


def cache_result(ttl_seconds: int = 300):
    """
    Cache decorator — baar baar same calculation mat karo
    SAP token cache jaisa pattern
    """
    def decorator(func):
        _cache = {}  # {key: (result, expiry_time)}

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = str(args) + str(kwargs)
            now = time.time()

            if cache_key in _cache:
                result, expiry = _cache[cache_key]
                if now < expiry:
                    print(f"[CACHE HIT] {func.__name__}")
                    return result
                print(f"[CACHE MISS] {func.__name__} — expired")

            result = func(*args, **kwargs)
            _cache[cache_key] = (result, now + ttl_seconds)
            return result
        return wrapper
    return decorator


# ─── Usage — multiple decorators stack karo ───
@log_execution
@retry(max_attempts=3, delay=2.0)
@cache_result(ttl_seconds=300)
def fetch_sap_token(base_url: str, username: str) -> str:
    """SAP HANA se token fetch karo"""
    import requests
    response = requests.post(f"{base_url}/auth", json={"user": username})
    return response.json()['token']

# Stack order: log_execution → retry → cache_result → actual function
# Pehle log hoga, phir retry wrapper, phir cache check, phir SAP call


# ─── Pattern 2: Class-based Decorator (OOP style) ───
from abc import ABC, abstractmethod

class PaymentProcessor(ABC):
    @abstractmethod
    def process(self, amount: float) -> dict:
        pass


class CardPaymentProcessor(PaymentProcessor):
    # Base component
    def process(self, amount):
        print(f"[CARD] Processing {amount}")
        return {"status": "success", "amount": amount}


class LoggingDecorator(PaymentProcessor):
    """
    Class-based decorator — same interface implement karo + extra kaam
    """
    def __init__(self, processor: PaymentProcessor):
        self._processor = processor  # Wrapped object

    def process(self, amount):
        print(f"[LOG] Payment start: {amount}")
        result = self._processor.process(amount)  # Original call
        print(f"[LOG] Payment done: {result['status']}")
        return result


class RetryDecorator(PaymentProcessor):
    def __init__(self, processor: PaymentProcessor, max_retries: int = 3):
        self._processor  = processor
        self._max_retries = max_retries

    def process(self, amount):
        for attempt in range(self._max_retries):
            try:
                return self._processor.process(amount)
            except Exception as e:
                if attempt == self._max_retries - 1:
                    raise
                print(f"[RETRY] Attempt {attempt + 1} failed")
        return {"status": "failed"}


class RateLimitDecorator(PaymentProcessor):
    def __init__(self, processor: PaymentProcessor, max_per_minute: int = 200):
        self._processor      = processor
        self._max_per_minute = max_per_minute
        self._calls          = []

    def process(self, amount):
        now = time.time()
        self._calls = [t for t in self._calls if now - t < 60]
        if len(self._calls) >= self._max_per_minute:
            raise Exception(f"Rate limit exceeded: {self._max_per_minute}/min")
        self._calls.append(now)
        return self._processor.process(amount)


# ─── Stack multiple decorators ───
processor = CardPaymentProcessor()          # Base
processor = LoggingDecorator(processor)    # Add logging
processor = RetryDecorator(processor, 3)   # Add retry
processor = RateLimitDecorator(processor, 200)  # Add rate limit

# Sab layers ke saath ek call
processor.process(10000)
# [RATE-LIMIT CHECK] → [RETRY] → [LOG] → [CARD] actual process
```

---

### 1.5 Tumhara Real Project Mein Kahan Use Hua

```
Project 1 — Niroskos (Django Decorators):
  @transaction.atomic         → Payment complete — success: commit, fail: rollback
  @shared_task(bind=True)     → Celery async task
  @receiver(post_save, ...)   → Signal handler decorator
  @action(detail=False, ...)  → DRF custom endpoint

Project 2 — Youngman Django Backend:
  @login_required             → Auth check pehle
  @api_view(['POST'])         → DRF view decorator
  @permission_classes([...])  → RBAC check

Project 3 — Youngman ERP (Production):
  SAP HANA connector mein retry logic:
    @retry(max_attempts=3)
    def push_invoice_to_sap(invoice):
        ...
  Rate limiter for Exotel API:
    @rate_limit(200, 60)   # 200 requests per minute
    def make_call(phone):
        ...
```

---

## PART 2: ENGLISH — Interviewer ko bolne ke liye

### 2.1 Definition

> **Decorator is a structural pattern that attaches additional responsibilities to an object dynamically. It provides a flexible alternative to subclassing for extending functionality, by wrapping the object with decorator classes that implement the same interface.**

---

### 2.2 Problem It Solves

```
Without Decorator — inheritance explosion:
  LoggingPaymentProcessor
  RetryPaymentProcessor
  LoggingRetryPaymentProcessor
  RateLimitedPaymentProcessor
  LoggingRateLimitedRetryPaymentProcessor  ← class explosion!

With Decorator — compose dynamically:
  processor = CardPaymentProcessor()
  processor = LoggingDecorator(processor)
  processor = RetryDecorator(processor, 3)
  # Mix and match at runtime — no class explosion
```

---

### 2.3 Key Components

| Component | Role | Example |
|-----------|------|---------|
| **Component** (Interface) | Common interface | `PaymentProcessor(ABC)` |
| **Concrete Component** | Base object to decorate | `CardPaymentProcessor` |
| **Base Decorator** | Holds reference, delegates | `LoggingDecorator(processor)` |
| **Concrete Decorators** | Add specific behavior | `RetryDecorator`, `RateLimitDecorator` |

---

### 2.4 Clean Code Example

```python
import functools, time

def timing(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start  = time.perf_counter()
        result = func(*args, **kwargs)
        end    = time.perf_counter()
        print(f"{func.__name__} took {end - start:.4f}s")
        return result
    return wrapper

def validate_amount(func):
    @functools.wraps(func)
    def wrapper(self, amount: float, *args, **kwargs):
        if amount <= 0:
            raise ValueError(f"Invalid amount: {amount}")
        if amount > 1_000_000:
            raise ValueError(f"Amount exceeds limit: {amount}")
        return func(self, amount, *args, **kwargs)
    return wrapper

def idempotent(func):
    """Prevent duplicate payments"""
    processed = set()
    @functools.wraps(func)
    def wrapper(self, amount, idempotency_key: str, *args, **kwargs):
        if idempotency_key in processed:
            return {"status": "already_processed", "key": idempotency_key}
        result = func(self, amount, *args, **kwargs)
        processed.add(idempotency_key)
        return result
    return wrapper

class PaymentService:
    @timing
    @validate_amount
    @idempotent
    def process_payment(self, amount: float, idempotency_key: str) -> dict:
        # Core logic — decorators handle cross-cutting concerns
        return {"status": "success", "amount": amount}
```

---

### 2.5 Real Project Answer

**"How did you use Decorator pattern?"**

> "I used Decorator pattern extensively in both projects — as Python function decorators and conceptually as class wrappers.
>
> **In Niroskos**, `@transaction.atomic` on the `PaymentService.mark_completed()` method ensures atomicity — if payment update succeeds but order status update fails, everything rolls back. I also used `@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True)` on Celery tasks — this decorator adds retry behavior with exponential backoff without touching the task logic.
>
> **In Youngman ERP**, the SAP HANA connector processed 10,000+ invoices monthly. I wrapped SAP API calls with a retry decorator — 3 attempts with exponential backoff (2s, 4s, 8s). For Exotel cloud telephony, I implemented rate limiting — 200 requests per minute — as a decorator around the API call function. Both concerns were completely separated from business logic."

---

### 2.6 Follow-up Q&A

**Q: "Decorator vs Inheritance — difference?"**
> "Inheritance adds behavior at compile time — you define a subclass. Decorator adds behavior at runtime — you wrap an object. Inheritance creates tight coupling (child locked to parent), Decorator is flexible (mix any combination). Also, multiple inheritance gets complex; multiple decorators stack cleanly."

**Q: "What is @functools.wraps and why use it?"**
> "Without `@functools.wraps`, the wrapper function loses the original function's `__name__`, `__doc__`, and other attributes. This breaks debugging, logging, and introspection. `@functools.wraps(func)` copies these attributes from the original function to the wrapper."

**Q: "How do you debug stacked decorators?"**
> "The key is understanding execution order — decorators execute from innermost to outermost on application, but when called, outermost runs first. I use logging in each decorator to trace the flow. Also, `functools.wraps` preserves `__wrapped__` attribute — you can access original function via `func.__wrapped__`."

---

*Last Updated: April 2026 | SDE-2 Interview Prep*
