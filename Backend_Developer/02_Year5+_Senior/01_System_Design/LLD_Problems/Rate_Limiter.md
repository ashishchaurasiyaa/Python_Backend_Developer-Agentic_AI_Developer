# Rate Limiter — LLD
> **Difficulty:** Medium-Hard | **Frequency:** ★★★★★ | **Your Strength:** Exotel 200 req/min real production

---

## What is a Rate Limiter?

```
Ek service ko protect karo over-use se:
  - User 200 req/min se zyada na kare
  - API provider ka limit respect karo (Exotel, Stripe, SAP)
  - DDoS / abuse prevention

Two sides:
  1. Inbound  → apni API protect karo (client aaye → limit lao)
  2. Outbound → third-party API call karo (Exotel, SAP) → unka limit respect karo

Niroskos/Youngman mein dono use hue:
  Inbound:  DRF throttling → per-user API rate limit
  Outbound: Exotel SMS/Call → 200 req/min → agar exceed karo → 429 milta hai
```

---

## 4 Algorithms — Quick Comparison

```
Algorithm          | Accuracy | Memory | Burst | Use Case
─────────────────────────────────────────────────────────────────
Fixed Window       | Low      | O(1)   | Yes   | Simple counters
Sliding Window Log | High     | O(n)   | No    | Strict per-user limits
Sliding Window     | High     | O(1)   | No    | Best balance
  Counter          |          |        |       |
Token Bucket       | Medium   | O(1)   | Yes   | API clients (Exotel pattern)
Leaky Bucket       | High     | O(1)   | No    | Smooth output rate

Interview: Token Bucket + Sliding Window — yeh do puchhe jaate hain
```

---

## Algorithm Deep-Dive

### Fixed Window — Simplest (and broken)

```
Counter reset every minute.

Problem — boundary burst:
  11:59:59 → 200 requests  (valid — window 1)
  12:00:01 → 200 requests  (valid — window 2)
  → 400 requests in 2 seconds! Window boundary pe double burst possible.
```

### Token Bucket — Most Common (Exotel pattern)

```
Ek bucket hai — max capacity = burst_limit tokens.
Tokens refill at rate = rate_limit per second.
Request aaye → 1 token consume. No token → reject.

capacity = 200, refill_rate = 200/60 = 3.33 tokens/sec

   [|||||||||||||||||||]   bucket (200 tokens)
    ↑ refill (3.33/sec)     ↓ consume (1 per request)

Burst allowed: bucket full hai → 200 requests instantly.
Long-term average enforced: average can't exceed refill_rate.

Real use:
  Exotel: 200 req/min → Token Bucket (capacity=200, refill=200/60 per sec)
  Stripe: 100 req/sec burst, 25 req/sec average
```

### Sliding Window Log — Most Accurate

```
Har request ka timestamp store karo (sorted list).
Check: last 60 seconds mein kitni requests hain?

get():
  timestamps list se old entries remove karo (> 60 sec)
  baaki count = current count
  count < limit → allow, timestamp add karo

Problem: memory O(n) — har request ka timestamp store
Use when: strict per-user limits, low traffic
```

### Sliding Window Counter — Best Balance

```
Fixed window ka boundary burst fix karo:
  current_window_count + previous_window_count × (overlap_ratio)

overlap_ratio = 1 - (elapsed in current window / window size)

Example — 60 sec window, limit=100:
  Previous window: 80 requests
  Current window:  30 requests (started 15 sec ago)
  overlap = 1 - (15/60) = 0.75
  estimate = 30 + 80 × 0.75 = 90 < 100 → allow

Memory: O(1) — sirf 2 counters
Accuracy: ~99% of sliding window log
```

---

## Full Implementation

```python
from __future__ import annotations
import time
import threading
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, Optional
import math


# ═══════════════════════════════════════════════════════════════
# BASE INTERFACE
# ═══════════════════════════════════════════════════════════════

@dataclass
class RateLimitResult:
    allowed:         bool
    remaining:       int      # Requests left in current window
    reset_after:     float    # Seconds until limit resets / tokens refill
    retry_after:     float    # If rejected: wait this many seconds
    limit:           int      # Total limit
    identifier:      str      # Which key was checked


class RateLimiter(ABC):
    """
    Strategy Interface — swap algorithm without changing caller.
    Caller (ExotelService, DRF throttle) sirf allow() call karta hai.
    """

    @abstractmethod
    def allow(self, identifier: str) -> RateLimitResult:
        """
        identifier = user_id / api_key / ip_address / 'exotel_outbound'
        Returns RateLimitResult — caller decides what to do (429, queue, etc.)
        """
        pass

    @abstractmethod
    def reset(self, identifier: str) -> None:
        """Force reset — testing ya admin override ke liye"""
        pass


# ═══════════════════════════════════════════════════════════════
# ALGORITHM 1: TOKEN BUCKET
# (Exotel 200 req/min → iska exact pattern)
# ═══════════════════════════════════════════════════════════════

class TokenBucketState:
    """Per-identifier bucket state"""
    __slots__ = ('tokens', 'last_refill_time', 'lock')

    def __init__(self, capacity: float):
        self.tokens:           float    = capacity   # Start full
        self.last_refill_time: float    = time.time()
        self.lock:             threading.Lock = threading.Lock()


class TokenBucketRateLimiter(RateLimiter):
    """
    Token Bucket algorithm.

    capacity    = burst_limit  (max tokens at once)
    refill_rate = tokens added per second

    Exotel config:
      capacity    = 200        (burst: 200 calls at once allowed)
      refill_rate = 200/60     = 3.33 tokens/sec
      → Long-term average = 200/min enforced
      → Short burst of 200 allowed if bucket was full

    How refill works (lazy — no background thread):
      On each request, calculate how many tokens should have
      accumulated since last_refill_time → add them (cap at capacity)
      This is called "lazy/on-demand refill" — no cron/thread needed
    """

    def __init__(self, capacity: int, refill_rate: float):
        """
        capacity:    max tokens (= burst limit)
        refill_rate: tokens per second (200/60 for Exotel)
        """
        self.capacity    = capacity
        self.refill_rate = refill_rate          # tokens/sec
        self._buckets: Dict[str, TokenBucketState] = {}
        self._global_lock = threading.Lock()

    def _get_or_create_bucket(self, identifier: str) -> TokenBucketState:
        with self._global_lock:
            if identifier not in self._buckets:
                self._buckets[identifier] = TokenBucketState(self.capacity)
            return self._buckets[identifier]

    def allow(self, identifier: str) -> RateLimitResult:
        bucket = self._get_or_create_bucket(identifier)

        with bucket.lock:
            now = time.time()

            # Lazy refill — add tokens for time elapsed
            elapsed        = now - bucket.last_refill_time
            tokens_to_add  = elapsed * self.refill_rate
            bucket.tokens  = min(self.capacity, bucket.tokens + tokens_to_add)
            bucket.last_refill_time = now

            if bucket.tokens >= 1:
                bucket.tokens -= 1
                remaining    = int(bucket.tokens)
                # Time until bucket is full (for informational header)
                time_to_full = (self.capacity - bucket.tokens) / self.refill_rate
                return RateLimitResult(
                    allowed=True, remaining=remaining,
                    reset_after=time_to_full, retry_after=0,
                    limit=self.capacity, identifier=identifier
                )
            else:
                # No tokens — calculate when next token arrives
                time_to_next_token = (1 - bucket.tokens) / self.refill_rate
                return RateLimitResult(
                    allowed=False, remaining=0,
                    reset_after=time_to_next_token,
                    retry_after=time_to_next_token,
                    limit=self.capacity, identifier=identifier
                )

    def reset(self, identifier: str) -> None:
        bucket = self._get_or_create_bucket(identifier)
        with bucket.lock:
            bucket.tokens = self.capacity
            bucket.last_refill_time = time.time()

    def get_token_count(self, identifier: str) -> float:
        """Debug — current token count"""
        bucket = self._buckets.get(identifier)
        return bucket.tokens if bucket else self.capacity


# ═══════════════════════════════════════════════════════════════
# ALGORITHM 2: SLIDING WINDOW LOG
# (Accurate — per-user strict limits)
# ═══════════════════════════════════════════════════════════════

class SlidingWindowLogRateLimiter(RateLimiter):
    """
    Store timestamp of every request in a sorted deque.
    Window = [now - window_size, now]
    Count requests in window → compare with limit.

    Memory: O(limit) per identifier — each slot = one timestamp
    Best for: strict per-user limits where accuracy matters
    """

    def __init__(self, limit: int, window_seconds: float):
        self.limit          = limit
        self.window_seconds = window_seconds
        self._logs: Dict[str, deque] = {}     # identifier → deque of timestamps
        self._locks: Dict[str, threading.Lock] = {}
        self._global_lock = threading.Lock()

    def _get_log_and_lock(self, identifier: str):
        with self._global_lock:
            if identifier not in self._logs:
                self._logs[identifier]  = deque()
                self._locks[identifier] = threading.Lock()
            return self._logs[identifier], self._locks[identifier]

    def allow(self, identifier: str) -> RateLimitResult:
        log, lock = self._get_log_and_lock(identifier)

        with lock:
            now        = time.time()
            window_start = now - self.window_seconds

            # Evict timestamps outside the window (from left)
            while log and log[0] <= window_start:
                log.popleft()

            current_count = len(log)

            if current_count < self.limit:
                log.append(now)
                remaining = self.limit - current_count - 1
                # Reset = when oldest request falls out of window
                reset_after = (log[0] + self.window_seconds - now) if log else 0
                return RateLimitResult(
                    allowed=True, remaining=remaining,
                    reset_after=reset_after, retry_after=0,
                    limit=self.limit, identifier=identifier
                )
            else:
                # Oldest request falls out in: log[0] + window - now
                retry_after = log[0] + self.window_seconds - now
                return RateLimitResult(
                    allowed=False, remaining=0,
                    reset_after=retry_after, retry_after=retry_after,
                    limit=self.limit, identifier=identifier
                )

    def reset(self, identifier: str) -> None:
        log, lock = self._get_log_and_lock(identifier)
        with lock:
            log.clear()


# ═══════════════════════════════════════════════════════════════
# ALGORITHM 3: SLIDING WINDOW COUNTER
# (Best balance — O(1) memory, ~accurate)
# ═══════════════════════════════════════════════════════════════

@dataclass
class WindowCounter:
    prev_count:      int   = 0
    curr_count:      int   = 0
    window_start:    float = field(default_factory=time.time)
    lock: threading.Lock   = field(default_factory=threading.Lock)


class SlidingWindowCounterRateLimiter(RateLimiter):
    """
    Two adjacent fixed windows + weighted estimate.

    estimate = curr_count + prev_count × (1 - elapsed/window_size)

    Accuracy: within 0.003% of true sliding window
    Memory:   O(1) per identifier — only 2 counters
    """

    def __init__(self, limit: int, window_seconds: float):
        self.limit          = limit
        self.window_seconds = window_seconds
        self._windows: Dict[str, WindowCounter] = {}
        self._global_lock = threading.Lock()

    def _get_window(self, identifier: str) -> WindowCounter:
        with self._global_lock:
            if identifier not in self._windows:
                self._windows[identifier] = WindowCounter(window_start=time.time())
            return self._windows[identifier]

    def allow(self, identifier: str) -> RateLimitResult:
        w = self._get_window(identifier)

        with w.lock:
            now     = time.time()
            elapsed = now - w.window_start

            # Slide the window if current window has passed
            if elapsed >= self.window_seconds:
                if elapsed >= 2 * self.window_seconds:
                    # More than 2 windows passed — full reset
                    w.prev_count  = 0
                    w.curr_count  = 0
                else:
                    # One window passed — curr becomes prev
                    w.prev_count = w.curr_count
                    w.curr_count = 0
                w.window_start = now
                elapsed        = 0

            # Weighted estimate
            overlap_ratio    = 1 - (elapsed / self.window_seconds)
            weighted_prev    = w.prev_count * overlap_ratio
            estimated_count  = w.curr_count + weighted_prev

            if estimated_count < self.limit:
                w.curr_count += 1
                remaining    = int(self.limit - estimated_count - 1)
                reset_after  = self.window_seconds - elapsed
                return RateLimitResult(
                    allowed=True, remaining=max(0, remaining),
                    reset_after=reset_after, retry_after=0,
                    limit=self.limit, identifier=identifier
                )
            else:
                reset_after = self.window_seconds - elapsed
                return RateLimitResult(
                    allowed=False, remaining=0,
                    reset_after=reset_after, retry_after=reset_after,
                    limit=self.limit, identifier=identifier
                )

    def reset(self, identifier: str) -> None:
        w = self._get_window(identifier)
        with w.lock:
            w.prev_count = w.curr_count = 0
            w.window_start = time.time()


# ═══════════════════════════════════════════════════════════════
# RATE LIMITER FACTORY
# ═══════════════════════════════════════════════════════════════

class RateLimiterFactory:
    """
    Config-driven limiter creation.
    DB ya settings se algorithm + params load karo.
    """

    @staticmethod
    def create(algorithm: str, limit: int, window_seconds: float) -> RateLimiter:
        if algorithm == "token_bucket":
            refill_rate = limit / window_seconds   # tokens per second
            return TokenBucketRateLimiter(capacity=limit, refill_rate=refill_rate)
        elif algorithm == "sliding_window_log":
            return SlidingWindowLogRateLimiter(limit=limit, window_seconds=window_seconds)
        elif algorithm == "sliding_window_counter":
            return SlidingWindowCounterRateLimiter(limit=limit, window_seconds=window_seconds)
        else:
            raise ValueError(f"Unknown algorithm: {algorithm}")

    # Pre-built configs matching real services
    @classmethod
    def exotel_sms(cls) -> RateLimiter:
        """Exotel: 200 req/min — token bucket allows burst"""
        return cls.create("token_bucket", limit=200, window_seconds=60)

    @classmethod
    def exotel_calls(cls) -> RateLimiter:
        """Exotel calls: stricter — 60 req/min"""
        return cls.create("token_bucket", limit=60, window_seconds=60)

    @classmethod
    def stripe_api(cls) -> RateLimiter:
        """Stripe: 100 req/sec"""
        return cls.create("token_bucket", limit=100, window_seconds=1)

    @classmethod
    def user_api(cls) -> RateLimiter:
        """Per-user inbound API: 1000 req/hour, strict"""
        return cls.create("sliding_window_counter", limit=1000, window_seconds=3600)

    @classmethod
    def sap_hana(cls) -> RateLimiter:
        """SAP HANA connector: conservative — 30 req/min"""
        return cls.create("token_bucket", limit=30, window_seconds=60)


# ═══════════════════════════════════════════════════════════════
# OUTBOUND RATE-LIMITED SERVICE (Niroskos Exotel Pattern)
# ═══════════════════════════════════════════════════════════════

class ExotelService:
    """
    Niroskos: Exotel SMS/Call API wrapper.
    200 req/min limit — exceed karo → Exotel returns 429.

    Strategy:
      Option A: Check limiter → reject if exceeded (caller handles retry)
      Option B: Check limiter → wait/sleep if exceeded (transparent to caller)
      Option C: Queue + worker (async, non-blocking)

    Niroskos mein: Option A (caller ke paas retry logic tha via Celery)
    Yahan: Option A + B dono implement karo
    """

    def __init__(self, account_sid: str, auth_token: str):
        self.account_sid  = account_sid
        self.auth_token   = auth_token
        self._sms_limiter  = RateLimiterFactory.exotel_sms()
        self._call_limiter = RateLimiterFactory.exotel_calls()
        self._stats        = {"sms_sent": 0, "calls_made": 0, "rejected": 0, "waited": 0}

    def send_sms(self, to: str, message: str, wait_if_limited: bool = False) -> dict:
        """
        wait_if_limited=True  → sleep until token available (sync, blocking)
        wait_if_limited=False → raise RateLimitError (caller handles via Celery retry)
        """
        result = self._sms_limiter.allow(f"exotel_sms")

        if not result.allowed:
            if wait_if_limited:
                print(f"[EXOTEL] Rate limited — waiting {result.retry_after:.2f}s")
                time.sleep(result.retry_after)
                self._stats["waited"] += 1
                # Retry after wait
                result = self._sms_limiter.allow("exotel_sms")
            else:
                self._stats["rejected"] += 1
                raise RateLimitError(
                    f"Exotel SMS rate limit exceeded. "
                    f"Retry after {result.retry_after:.2f}s",
                    retry_after=result.retry_after
                )

        # Actual Exotel API call
        # response = requests.post(
        #     f"https://api.exotel.com/v1/Accounts/{self.account_sid}/Sms/send",
        #     auth=(self.account_sid, self.auth_token),
        #     data={"From": "EXOTEL", "To": to, "Body": message}
        # )
        self._stats["sms_sent"] += 1
        print(f"[EXOTEL SMS] → {to}: {message[:40]}... | Remaining: {result.remaining}/200")
        return {
            "status":    "queued",
            "to":        to,
            "remaining": result.remaining
        }

    def make_call(self, to: str, caller_id: str) -> dict:
        result = self._call_limiter.allow("exotel_calls")
        if not result.allowed:
            raise RateLimitError(
                f"Exotel Call limit exceeded. Retry after {result.retry_after:.2f}s",
                retry_after=result.retry_after
            )
        self._stats["calls_made"] += 1
        print(f"[EXOTEL CALL] → {to} from {caller_id} | Remaining: {result.remaining}/60")
        return {"status": "initiated", "to": to}

    @property
    def stats(self) -> dict:
        return self._stats


class RateLimitError(Exception):
    def __init__(self, message: str, retry_after: float = 0):
        super().__init__(message)
        self.retry_after = retry_after


# ═══════════════════════════════════════════════════════════════
# INBOUND: DRF-STYLE THROTTLE DECORATOR
# ═══════════════════════════════════════════════════════════════

def rate_limit(limit: int, window_seconds: float, algorithm: str = "sliding_window_counter"):
    """
    Decorator for view functions — inbound API rate limiting.
    Equivalent to DRF's UserRateThrottle.

    Usage:
        @rate_limit(200, 60)
        def send_notification(request):
            ...

    DRF equivalent:
        REST_FRAMEWORK = {
            'DEFAULT_THROTTLE_CLASSES': ['rest_framework.throttling.UserRateThrottle'],
            'DEFAULT_THROTTLE_RATES': {'user': '200/min'}
        }
    """
    limiter = RateLimiterFactory.create(algorithm, limit, window_seconds)

    def decorator(func):
        def wrapper(request, *args, **kwargs):
            # Identifier = user_id or IP for anonymous
            identifier = getattr(request, 'user_id', None) or \
                         getattr(request, 'META', {}).get('REMOTE_ADDR', 'anonymous')

            result = limiter.allow(str(identifier))

            if not result.allowed:
                # Return 429 response
                print(f"[429] Rate limited: {identifier} | retry_after={result.retry_after:.1f}s")
                return {
                    "error":       "rate_limit_exceeded",
                    "retry_after": result.retry_after,
                    "limit":       result.limit
                }

            response = func(request, *args, **kwargs)

            # Add rate limit headers to response (standard practice)
            # response['X-RateLimit-Limit']     = result.limit
            # response['X-RateLimit-Remaining'] = result.remaining
            # response['X-RateLimit-Reset']     = int(time.time() + result.reset_after)
            return response

        return wrapper
    return decorator


# ═══════════════════════════════════════════════════════════════
# REDIS-BACKED RATE LIMITER (Production Pattern)
# ═══════════════════════════════════════════════════════════════

class RedisTokenBucketRateLimiter(RateLimiter):
    """
    Distributed rate limiter — Redis ke saath.
    Multiple servers → shared state in Redis.

    Lua script use karo → atomic check-and-update
    (MULTI/EXEC ya individual commands → race condition possible)

    Redis keys:
      rate_limit:{identifier}:tokens      → current token count (float as string)
      rate_limit:{identifier}:last_refill → last refill timestamp

    In Niroskos: Redis used for distributed locks (SET NX),
    same Redis for rate limiting — single Redis cluster serves both.
    """

    REFILL_AND_CONSUME_SCRIPT = """
    local key_tokens = KEYS[1]
    local key_time   = KEYS[2]
    local capacity   = tonumber(ARGV[1])
    local refill_rate = tonumber(ARGV[2])
    local now        = tonumber(ARGV[3])
    local ttl        = tonumber(ARGV[4])

    local last_refill = tonumber(redis.call('GET', key_time) or now)
    local tokens      = tonumber(redis.call('GET', key_tokens) or capacity)

    -- Refill tokens based on elapsed time
    local elapsed = now - last_refill
    tokens = math.min(capacity, tokens + elapsed * refill_rate)

    local allowed = 0
    local remaining = 0

    if tokens >= 1 then
        tokens  = tokens - 1
        allowed = 1
    end

    remaining = math.floor(tokens)

    -- Store updated state
    redis.call('SET', key_tokens, tokens, 'EX', ttl)
    redis.call('SET', key_time, now, 'EX', ttl)

    return {allowed, remaining}
    """

    def __init__(self, redis_client, capacity: int, refill_rate: float):
        self.redis       = redis_client
        self.capacity    = capacity
        self.refill_rate = refill_rate
        self._script_sha = None  # EVALSHA for cached script

    def allow(self, identifier: str) -> RateLimitResult:
        key_tokens = f"rate_limit:{identifier}:tokens"
        key_time   = f"rate_limit:{identifier}:last_refill"
        now        = time.time()
        ttl        = int(self.capacity / self.refill_rate) + 60  # auto-expire idle keys

        # Execute Lua script atomically
        # result = self.redis.eval(
        #     self.REFILL_AND_CONSUME_SCRIPT, 2,
        #     key_tokens, key_time,
        #     self.capacity, self.refill_rate, now, ttl
        # )
        # allowed, remaining = result

        # Simulated for this file (no actual Redis):
        allowed, remaining = 1, self.capacity - 1

        if allowed:
            time_to_next = 0
        else:
            time_to_next = 1 / self.refill_rate

        return RateLimitResult(
            allowed=bool(allowed), remaining=remaining,
            reset_after=time_to_next, retry_after=time_to_next,
            limit=self.capacity, identifier=identifier
        )

    def reset(self, identifier: str) -> None:
        # self.redis.delete(f"rate_limit:{identifier}:tokens")
        # self.redis.delete(f"rate_limit:{identifier}:last_refill")
        pass
```

---

## Demo

```python
print("=" * 55)
print("DEMO 1: Token Bucket — Exotel 200 req/min")
print("=" * 55)

exotel_limiter = RateLimiterFactory.exotel_sms()

# Send 5 SMS quickly — burst allowed
for i in range(5):
    result = exotel_limiter.allow("exotel_sms_outbound")
    print(f"  Request {i+1}: allowed={result.allowed} | remaining={result.remaining}")

# Exhaust tokens manually (simulate 200 requests)
exotel_limiter2 = TokenBucketRateLimiter(capacity=5, refill_rate=1.0)
for i in range(7):
    r = exotel_limiter2.allow("test_user")
    status = "✓ ALLOWED" if r.allowed else f"✗ BLOCKED (retry in {r.retry_after:.2f}s)"
    print(f"  Request {i+1}: {status} | tokens≈{exotel_limiter2.get_token_count('test_user'):.2f}")


print("\n" + "=" * 55)
print("DEMO 2: Sliding Window Log — Strict per-user")
print("=" * 55)

sw_limiter = SlidingWindowLogRateLimiter(limit=5, window_seconds=10)

for i in range(7):
    r = sw_limiter.allow("user_123")
    status = "✓" if r.allowed else f"✗ retry_after={r.retry_after:.2f}s"
    print(f"  Request {i+1}: {status} | remaining={r.remaining}")

print("\n" + "=" * 55)
print("DEMO 3: ExotelService — real usage pattern")
print("=" * 55)

exotel = ExotelService("AC_test_sid", "auth_token_xyz")

# Normal sends
for i in range(3):
    try:
        exotel.send_sms(f"+9198765432{i:02d}", f"Booking confirmed #{i+1}")
    except RateLimitError as e:
        print(f"  Rate limited: {e} — Celery retry scheduled")

print(f"Stats: {exotel.stats}")


print("\n" + "=" * 55)
print("DEMO 4: Sliding Window Counter — inbound API")
print("=" * 55)

api_limiter = SlidingWindowCounterRateLimiter(limit=10, window_seconds=5)

for i in range(13):
    r = api_limiter.allow("api_user_456")
    status = "✓ ALLOWED" if r.allowed else f"✗ BLOCKED"
    print(f"  Request {i+1:2d}: {status} | remaining={r.remaining}")


print("\n" + "=" * 55)
print("DEMO 5: Thread Safety Test")
print("=" * 55)

import threading
thread_limiter = TokenBucketRateLimiter(capacity=10, refill_rate=10.0)
allowed_count  = 0
blocked_count  = 0
lock           = threading.Lock()

def make_requests(n: int):
    global allowed_count, blocked_count
    for _ in range(n):
        r = thread_limiter.allow("concurrent_user")
        with lock:
            if r.allowed:
                allowed_count += 1
            else:
                blocked_count += 1

# 5 threads × 4 requests = 20 total (bucket = 10)
threads = [threading.Thread(target=make_requests, args=(4,)) for _ in range(5)]
for t in threads: t.start()
for t in threads: t.join()

print(f"  Allowed: {allowed_count} | Blocked: {blocked_count} | Total: {allowed_count + blocked_count}")
print(f"  No double-allow beyond capacity: {allowed_count <= 10 + 1}")  # +1 for refill during test
```

---

## Complexity Analysis

```
Algorithm               | Time  | Memory       | Burst  | Accuracy
──────────────────────────────────────────────────────────────────
Fixed Window Counter    | O(1)  | O(1)         | YES    | Low (boundary burst)
Token Bucket            | O(1)  | O(1)         | YES    | Medium (burst allowed by design)
Sliding Window Log      | O(n)  | O(limit)     | NO     | High (exact count)
Sliding Window Counter  | O(1)  | O(1)         | NO     | High (~99.7% accurate)
Leaky Bucket            | O(1)  | O(1)         | NO     | High (smooth output)

n = requests in current window
For Sliding Window Log: cleanup is amortized O(1) per request
```

---

## Interview Q&A

**Q: "Exotel rate limiting — how did you handle it in production?"**
> "Exotel allows 200 SMS per minute. I used a Token Bucket because it naturally fits their model — 200 tokens fill over 60 seconds (3.33 tokens/sec), but if we've accumulated a full bucket, we can burst 200 SMS instantly for a bulk notification campaign. The key insight is lazy refill — no background thread. On each outgoing request, I calculate how many tokens accumulated since the last call and add them (capped at 200). In Niroskos, when Exotel returned 429, the Celery task caught the RateLimitError and rescheduled itself with countdown equal to retry_after. This gave us automatic backoff without manual intervention."

**Q: "Token Bucket vs Sliding Window — when to use which?"**
> "Token Bucket when burst is acceptable — payment gateways, SMS providers, outbound API calls. You want to use bursts strategically (bulk notifications). Sliding Window when burst must be strictly prevented — per-user API limits, login attempts, OTP sends. You don't want a user to send 1000 login attempts in 2 seconds just because the previous minute was quiet. Sliding Window Log is most accurate but memory-heavy. Sliding Window Counter gives 99%+ accuracy at O(1) memory — my default choice for inbound API throttling."

**Q: "How do you rate limit in a distributed system (multiple servers)?"**
> "In-process rate limiters don't work — Server A and Server B have separate counters. Need shared state. Use Redis with a Lua script for atomic check-and-update. Lua runs atomically on Redis — no race condition possible between the read (check tokens) and write (decrement). The script takes the key, capacity, refill_rate, and current timestamp — calculates tokens, decrements if allowed, returns result. Two alternatives: Redis INCR + EXPIRE (fixed window, simpler, boundary burst possible) or Sorted Set ZADD/ZRANGEBYSCORE (sliding window log in Redis). For Niroskos, Redis was already in the stack for Celery broker — reusing it for rate limiting added zero infrastructure."

**Q: "What are the rate limit response headers?"**
> "Standard headers: X-RateLimit-Limit (total allowed), X-RateLimit-Remaining (left in window), X-RateLimit-Reset (epoch when resets), Retry-After (seconds to wait when 429). DRF throttling adds these automatically when you use DEFAULT_THROTTLE_CLASSES. For our outbound Exotel calls, the retry_after came from Exotel's 429 response header — I parsed it and passed directly to Celery's countdown parameter."

**Q: "Fixed Window's boundary burst problem — explain with example."**
> "Limit is 100 req/min. Window resets at 12:00:00. At 11:59:55 a user sends 100 requests — valid, within window 1. At 12:00:05 they send 100 more — valid, new window 2 just started. Result: 200 requests in 10 seconds, double the intended rate. Sliding Window fixes this: at any given moment, only look at the last 60 seconds regardless of clock boundaries. The estimate = current_count + previous_count × overlap_ratio smoothly handles the transition without the boundary jump."

**Q: "How does DRF throttling work internally?"**
> "DRF's UserRateThrottle is a Fixed Window implementation. It uses the cache backend (usually Redis or memcached) with key = throttle_user_{user_id}. On each request: cache.get(key) → count + 1 → if count > rate → 429. Reset happens when the cache key expires (TTL = window_size). It has the boundary burst problem but works well in practice because API abuse typically isn't precisely timed to window boundaries. For stricter requirements, you can override get_rate() and allow_request() to implement Sliding Window."

---

## Algorithms Visual Comparison

```
Scenario: limit=5/10sec, requests at t=0,1,2,3,4,5,6,7,8,9,10,11

Fixed Window (resets at t=10):
  t=0-4:  5 allowed  ✓✓✓✓✓
  t=5-9:  0 allowed  ✗✗✗✗✗  (window full)
  t=9:    200ms before reset → last request ✗
  t=10:   RESET! Window 2 starts
  t=10-14: 5 allowed ✓✓✓✓✓  ← boundary burst if t=9 also had requests

Token Bucket (refill_rate=0.5/sec):
  t=0:    bucket=5 → allow, bucket=4
  t=1:    bucket=4.5 → allow, bucket=3.5
  t=2:    bucket=4.0 → allow, bucket=3.0
  t=3:    bucket=3.5 → allow, bucket=2.5
  t=4:    bucket=3.0 → allow, bucket=2.0
  t=5:    bucket=2.5 → allow, bucket=1.5
  → Burst allowed at start, then smoothed

Sliding Window Log (exact):
  Always looks at last 10 sec
  [t0,t1,t2,t3,t4] → count=5 at t=4
  At t=10.1: t0 exits window → count=4 → allow
  No boundary burst — perfectly smooth
```

---

## Niroskos + Youngman Real Mapping

| Where | Algorithm | Config | Why |
|---|---|---|---|
| Exotel SMS outbound | Token Bucket | 200/min | Burst for campaigns; Celery retry on 429 |
| Exotel Call outbound | Token Bucket | 60/min | Stricter, no burst needed |
| SAP HANA API | Token Bucket | 30/min | SAP's internal limit |
| DRF inbound API | Sliding Window Counter | 1000/hour per user | Strict, memory-efficient |
| OTP send endpoint | Sliding Window Log | 5/10min per phone | Abuse prevention, exact |
| Admin bulk export | Fixed Window | 10/hour per user | Simple, burst OK |

---

*Last Updated: April 2026 | SDE-2 Interview Prep — Niroskos Exotel Rate Limiting*
