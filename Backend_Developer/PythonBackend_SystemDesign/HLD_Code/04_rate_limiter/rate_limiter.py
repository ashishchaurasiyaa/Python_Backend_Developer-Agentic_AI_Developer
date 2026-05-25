"""
============================================================
RATE LIMITER — Working Implementations
============================================================
Four algorithms (most-used in production):

1. TOKEN BUCKET     — refills tokens at rate R, allows bursts
2. LEAKY BUCKET     — fixed outflow rate, queues excess
3. FIXED WINDOW     — count requests per minute (simple, has burst at boundary)
4. SLIDING WINDOW   — rolling time window (smoother, more memory)

Includes:
  - In-memory (single instance)
  - Redis-based (distributed) — simulated with dict + lock

Run: python rate_limiter.py
"""
from __future__ import annotations
import time
import threading
import asyncio
from abc import ABC, abstractmethod
from collections import deque, defaultdict
from dataclasses import dataclass, field
from typing import Optional


class RateLimitExceeded(Exception):
    """Raised when rate limit hit. Has retry_after in seconds."""
    def __init__(self, retry_after: float, key: str = ""):
        self.retry_after = retry_after
        self.key = key
        super().__init__(f"Rate limit exceeded for {key!r}, retry after {retry_after:.2f}s")


# ============================================================
# 1. TOKEN BUCKET — most flexible, supports bursts
# ============================================================
class TokenBucket:
    """
    Capacity tokens; refills at `rate` tokens/sec.
    Allows short bursts up to `capacity`, sustained rate = `rate`.
    """
    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = float(capacity)
        self.last_refill = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self):
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

    def acquire(self, n: int = 1) -> bool:
        with self._lock:
            self._refill()
            if self.tokens >= n:
                self.tokens -= n
                return True
            return False

    def acquire_or_raise(self, n: int = 1, key: str = ""):
        if not self.acquire(n):
            with self._lock:
                deficit = n - self.tokens
                retry = deficit / self.refill_rate
            raise RateLimitExceeded(retry, key)


# ============================================================
# 2. LEAKY BUCKET — queue-based smoothing
# ============================================================
class LeakyBucket:
    """
    Requests enter queue; leak at fixed rate.
    Drops requests when queue full.
    """
    def __init__(self, capacity: int, leak_rate: float):
        self.capacity = capacity
        self.leak_rate = leak_rate    # per second
        self.queue: deque = deque()
        self.last_leak = time.monotonic()
        self._lock = threading.Lock()

    def _leak(self):
        now = time.monotonic()
        elapsed = now - self.last_leak
        leak_count = int(elapsed * self.leak_rate)
        if leak_count > 0:
            for _ in range(min(leak_count, len(self.queue))):
                self.queue.popleft()
            self.last_leak = now

    def accept(self) -> bool:
        with self._lock:
            self._leak()
            if len(self.queue) < self.capacity:
                self.queue.append(time.monotonic())
                return True
            return False


# ============================================================
# 3. FIXED WINDOW COUNTER
# ============================================================
class FixedWindow:
    """N requests per window seconds. Reset at window boundary."""
    def __init__(self, max_requests: int, window_size: float = 60.0):
        self.max = max_requests
        self.window = window_size
        self._count: dict[str, int] = defaultdict(int)
        self._window_start: dict[str, float] = {}
        self._lock = threading.Lock()

    def allow(self, key: str = "global") -> bool:
        with self._lock:
            now = time.monotonic()
            start = self._window_start.get(key, now)
            if now - start >= self.window:
                # Reset window
                self._count[key] = 0
                self._window_start[key] = now
                start = now
            if self._count[key] >= self.max:
                return False
            self._count[key] += 1
            return True


# ============================================================
# 4. SLIDING WINDOW LOG (precise, more memory)
# ============================================================
class SlidingWindowLog:
    """Stores timestamp of each request. Precise but O(N) memory."""
    def __init__(self, max_requests: int, window_size: float = 60.0):
        self.max = max_requests
        self.window = window_size
        self._timestamps: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str = "global") -> bool:
        with self._lock:
            now = time.monotonic()
            cutoff = now - self.window
            ts = self._timestamps[key]
            # Drop old timestamps
            while ts and ts[0] < cutoff:
                ts.popleft()
            if len(ts) >= self.max:
                return False
            ts.append(now)
            return True


# ============================================================
# 5. SLIDING WINDOW COUNTER (hybrid — balanced approach)
# ============================================================
class SlidingWindowCounter:
    """
    Combines fixed window + interpolation from previous window.
    Memory: O(1) per key. Precision: ~5-10% off but close.
    Used by Cloudflare for production rate limiting.
    """
    def __init__(self, max_requests: int, window_size: float = 60.0):
        self.max = max_requests
        self.window = window_size
        self._curr: dict[str, int] = defaultdict(int)
        self._prev: dict[str, int] = defaultdict(int)
        self._window_start: dict[str, float] = {}
        self._lock = threading.Lock()

    def allow(self, key: str = "global") -> bool:
        with self._lock:
            now = time.monotonic()
            start = self._window_start.get(key, now)
            elapsed = now - start

            if elapsed >= self.window:
                # Roll: current → previous; reset current
                self._prev[key] = self._curr[key]
                self._curr[key] = 0
                self._window_start[key] = now
                elapsed = 0

            # Interpolate previous window's contribution
            weight = max(0, 1 - elapsed / self.window)
            estimated = self._prev[key] * weight + self._curr[key]

            if estimated >= self.max:
                return False
            self._curr[key] += 1
            return True


# ============================================================
# 6. DISTRIBUTED — Redis-like atomic counter (using dict + Lua-emulated)
# ============================================================
class RedisRateLimiter:
    """
    Simulates Redis-based distributed limiter.
    In production: use Redis INCR + EXPIRE, or Redis cell module.

    LUA SCRIPT (real implementation):
      local count = redis.call("INCR", KEYS[1])
      if count == 1 then
          redis.call("EXPIRE", KEYS[1], ARGV[1])
      end
      return count
    """
    def __init__(self, max_requests: int, window_size: float = 60.0):
        self.max = max_requests
        self.window = window_size
        self._store: dict[str, tuple[int, float]] = {}  # key -> (count, expires_at)
        self._lock = threading.Lock()

    def allow(self, key: str) -> tuple[bool, int]:
        with self._lock:
            now = time.monotonic()
            count, expires = self._store.get(key, (0, 0))
            if now > expires:
                count = 0
                expires = now + self.window
            count += 1
            self._store[key] = (count, expires)
            return count <= self.max, count


# ============================================================
# 7. ASYNC TOKEN BUCKET
# ============================================================
class AsyncTokenBucket:
    """For async code with await."""
    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = float(capacity)
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, n: int = 1, block: bool = True):
        async with self._lock:
            await self._refill_async()
            if self.tokens >= n:
                self.tokens -= n
                return True
            if not block:
                return False
            wait = (n - self.tokens) / self.refill_rate
        await asyncio.sleep(wait)
        return await self.acquire(n, block=False)

    async def _refill_async(self):
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now


# ============================================================
# DEMOS
# ============================================================
def demo_token_bucket():
    print("=" * 60)
    print("DEMO 1: Token Bucket")
    print("=" * 60)
    bucket = TokenBucket(capacity=5, refill_rate=2.0)  # 5 burst, 2/sec sustained

    print("  Burst of 7 requests (bucket=5):")
    for i in range(7):
        ok = bucket.acquire()
        print(f"    Req {i}: {'✅' if ok else '❌ DENIED'}")

    print("  Wait 1s (refills 2 tokens)...")
    time.sleep(1.0)
    for i in range(3):
        ok = bucket.acquire()
        print(f"    Req {i}: {'✅' if ok else '❌ DENIED'}")


def demo_leaky_bucket():
    print("\n" + "=" * 60)
    print("DEMO 2: Leaky Bucket")
    print("=" * 60)
    bucket = LeakyBucket(capacity=3, leak_rate=2.0)
    for i in range(6):
        ok = bucket.accept()
        print(f"    Req {i}: {'✅ queued' if ok else '❌ DROPPED'}")


def demo_fixed_window():
    print("\n" + "=" * 60)
    print("DEMO 3: Fixed Window (5 per 2 sec)")
    print("=" * 60)
    limiter = FixedWindow(max_requests=5, window_size=2.0)
    user = "user-123"

    print("  Burst of 7:")
    for i in range(7):
        ok = limiter.allow(user)
        print(f"    Req {i}: {'✅' if ok else '❌'}")
    print("  Wait 2s (new window)...")
    time.sleep(2.1)
    for i in range(3):
        ok = limiter.allow(user)
        print(f"    Req {i}: {'✅' if ok else '❌'}")


def demo_sliding_log():
    print("\n" + "=" * 60)
    print("DEMO 4: Sliding Window Log (3 per 1 sec)")
    print("=" * 60)
    limiter = SlidingWindowLog(max_requests=3, window_size=1.0)
    for i in range(5):
        ok = limiter.allow("user-1")
        print(f"    Req {i}: {'✅' if ok else '❌'}")
        time.sleep(0.1)


def demo_sliding_counter():
    print("\n" + "=" * 60)
    print("DEMO 5: Sliding Window Counter (Cloudflare style)")
    print("=" * 60)
    limiter = SlidingWindowCounter(max_requests=5, window_size=2.0)
    for i in range(8):
        ok = limiter.allow("user-1")
        print(f"    Req {i}: {'✅' if ok else '❌'}")
        time.sleep(0.2)


def demo_redis():
    print("\n" + "=" * 60)
    print("DEMO 6: Redis-style distributed limiter")
    print("=" * 60)
    rl = RedisRateLimiter(max_requests=3, window_size=2.0)
    for i in range(5):
        ok, count = rl.allow("api-key-abc")
        print(f"    Req {i}: count={count} {'✅' if ok else '❌ EXCEEDED'}")


async def demo_async():
    print("\n" + "=" * 60)
    print("DEMO 7: Async Token Bucket (with blocking acquire)")
    print("=" * 60)
    bucket = AsyncTokenBucket(capacity=3, refill_rate=2.0)

    async def request(i):
        start = time.monotonic()
        await bucket.acquire()
        elapsed = time.monotonic() - start
        print(f"    Req {i} got token after {elapsed*1000:.0f}ms")

    await asyncio.gather(*[request(i) for i in range(6)])


# ============================================================
# 8. FASTAPI MIDDLEWARE EXAMPLE (template)
# ============================================================
FASTAPI_INTEGRATION = """
# In FastAPI app:

from fastapi import FastAPI, Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

app = FastAPI()
limiter = TokenBucket(capacity=10, refill_rate=5)   # 5/sec, burst 10

class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        client_ip = request.client.host
        # Per-IP bucket
        if not limiter.acquire():
            raise HTTPException(
                status_code=429,
                detail="Too many requests",
                headers={"Retry-After": "1"},
            )
        return await call_next(request)

app.add_middleware(RateLimitMiddleware)
"""


if __name__ == "__main__":
    demo_token_bucket()
    demo_leaky_bucket()
    demo_fixed_window()
    demo_sliding_log()
    demo_sliding_counter()
    demo_redis()
    asyncio.run(demo_async())

    print("\n" + "=" * 60)
    print("FASTAPI INTEGRATION TEMPLATE")
    print("=" * 60)
    print(FASTAPI_INTEGRATION)

    print("=" * 60)
    print("ALGORITHM COMPARISON")
    print("=" * 60)
    print("""
| Algorithm           | Burst | Memory  | Precision | Use Case          |
|---------------------|-------|---------|-----------|-------------------|
| Token Bucket        | ✅ Yes | O(1)    | High      | Default — best    |
| Leaky Bucket        | ❌ No  | O(N)    | High      | Smoothing traffic |
| Fixed Window        | ⚠️ At boundary | O(1) | Low | Simple, OK        |
| Sliding Window Log  | ❌ No  | O(N)    | Perfect   | Strict APIs       |
| Sliding Window Cnt  | ⚠️ Small | O(1)  | ~95%      | Cloudflare uses   |

DISTRIBUTED:
- Use Redis INCR + EXPIRE for atomic counters
- Use Lua scripts for atomic check-and-increment
- Consider Redis Cell module for token bucket
- For huge scale: precomputed quotas per-shard

PRODUCTION:
- Send Retry-After header on 429
- Per-tier limits (free/paid)
- Per-API-key + per-IP combination
- Allowlist for internal services
- Metrics: requests/min, deny rate, top abusers
""")
