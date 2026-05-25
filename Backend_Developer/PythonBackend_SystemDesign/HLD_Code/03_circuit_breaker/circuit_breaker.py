"""
============================================================
CIRCUIT BREAKER PATTERN — Working Implementation
============================================================
Prevents cascading failures by tripping a "circuit" when a
downstream service is failing.

STATE MACHINE:
  CLOSED  ──[failures ≥ threshold]──→ OPEN
  OPEN    ──[after cooldown]────────→ HALF_OPEN
  HALF_OPEN ─[N consecutive success]→ CLOSED
  HALF_OPEN ─[any failure]──────────→ OPEN

CLOSED   = normal — requests pass through
OPEN     = service unhealthy — requests fail fast (no call)
HALF_OPEN = probe state — allow limited traffic to test recovery

Run: python circuit_breaker.py
"""
from __future__ import annotations
import time
import random
import threading
import functools
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
from typing import Callable, Any


class CircuitState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreakerError(Exception):
    """Raised when circuit is OPEN and request is rejected."""
    pass


# ============================================================
# 1. CIRCUIT BREAKER — full implementation
# ============================================================
@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5      # failures before tripping
    success_threshold: int = 2      # successes in HALF_OPEN to close
    timeout: float = 10.0           # cooldown in OPEN before HALF_OPEN
    window_size: int = 10           # rolling window for stats
    failure_rate_threshold: float = 0.5   # 50% failure rate trips
    excluded_exceptions: tuple = ()   # don't count these as failures


@dataclass
class CircuitMetrics:
    total_calls: int = 0
    failed_calls: int = 0
    successful_calls: int = 0
    rejected_calls: int = 0
    state_changes: int = 0
    last_failure_time: float = 0.0
    last_success_time: float = 0.0


class CircuitBreaker:
    def __init__(self, name: str, config: CircuitBreakerConfig | None = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0       # used in HALF_OPEN
        self._last_failure_time = 0.0
        self._results: deque = deque(maxlen=self.config.window_size)
        self._lock = threading.RLock()
        self.metrics = CircuitMetrics()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            self._maybe_transition_to_half_open()
            return self._state

    def _maybe_transition_to_half_open(self):
        if (self._state == CircuitState.OPEN and
                time.time() - self._last_failure_time >= self.config.timeout):
            self._transition(CircuitState.HALF_OPEN)
            self._success_count = 0

    def _transition(self, new_state: CircuitState):
        if self._state != new_state:
            print(f"  ⚡ [{self.name}] {self._state.value} → {new_state.value}")
            self._state = new_state
            self.metrics.state_changes += 1

    def call(self, func: Callable, *args, **kwargs) -> Any:
        with self._lock:
            self._maybe_transition_to_half_open()
            self.metrics.total_calls += 1

            if self._state == CircuitState.OPEN:
                self.metrics.rejected_calls += 1
                raise CircuitBreakerError(
                    f"Circuit '{self.name}' is OPEN — fast-failing"
                )

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.config.excluded_exceptions:
            # Don't count as failure (e.g., HTTP 4xx is client error)
            raise
        except Exception:
            self._on_failure()
            raise

    def _on_success(self):
        with self._lock:
            self.metrics.successful_calls += 1
            self.metrics.last_success_time = time.time()
            self._results.append(True)
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self._transition(CircuitState.CLOSED)
                    self._failure_count = 0
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0

    def _on_failure(self):
        with self._lock:
            self.metrics.failed_calls += 1
            self.metrics.last_failure_time = time.time()
            self._last_failure_time = time.time()
            self._results.append(False)

            if self._state == CircuitState.HALF_OPEN:
                # Any failure in HALF_OPEN trips back to OPEN
                self._transition(CircuitState.OPEN)
                return

            if self._state == CircuitState.CLOSED:
                self._failure_count += 1
                # Trip on absolute count OR failure rate (whichever first)
                if self._failure_count >= self.config.failure_threshold:
                    self._transition(CircuitState.OPEN)
                elif len(self._results) >= self.config.window_size:
                    rate = sum(1 for r in self._results if not r) / len(self._results)
                    if rate >= self.config.failure_rate_threshold:
                        self._transition(CircuitState.OPEN)

    def reset(self):
        with self._lock:
            self._transition(CircuitState.CLOSED)
            self._failure_count = 0
            self._success_count = 0
            self._results.clear()

    def stats(self) -> dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "metrics": {
                "total": self.metrics.total_calls,
                "success": self.metrics.successful_calls,
                "failed": self.metrics.failed_calls,
                "rejected": self.metrics.rejected_calls,
                "state_changes": self.metrics.state_changes,
            },
        }


# ============================================================
# 2. DECORATOR API
# ============================================================
def circuit_breaker(name: str, config: CircuitBreakerConfig | None = None):
    """Decorator for protecting a function."""
    cb = CircuitBreaker(name, config)
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return cb.call(func, *args, **kwargs)
        wrapper.circuit_breaker = cb
        return wrapper
    return decorator


# ============================================================
# 3. RETRY + CIRCUIT BREAKER COMBO
# ============================================================
def with_retry(retries=3, backoff=0.1):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(retries):
                try:
                    return func(*args, **kwargs)
                except CircuitBreakerError:
                    raise   # don't retry when circuit is open
                except Exception as e:
                    last_exc = e
                    if attempt < retries - 1:
                        time.sleep(backoff * (2 ** attempt))
            raise last_exc
        return wrapper
    return decorator


# ============================================================
# 4. DEMO — Simulated flaky service
# ============================================================
class FlakyService:
    """Simulates a service that becomes unhealthy then recovers."""
    def __init__(self):
        self.calls = 0
        self.unhealthy_until = 0

    def make_unhealthy(self, duration=5):
        self.unhealthy_until = time.time() + duration
        print(f"  🔥 Service is now unhealthy for {duration}s")

    def call(self, payload="test"):
        self.calls += 1
        if time.time() < self.unhealthy_until:
            raise ConnectionError("Service unreachable")
        return f"OK[{payload}]"


def demo_basic():
    print("=" * 60)
    print("DEMO 1: Basic circuit breaker behavior")
    print("=" * 60)

    config = CircuitBreakerConfig(
        failure_threshold=3,
        success_threshold=2,
        timeout=2.0,
    )
    cb = CircuitBreaker("payment-service", config)
    svc = FlakyService()

    # Phase 1: CLOSED — successful calls
    print("\n--- Phase 1: CLOSED, healthy calls ---")
    for i in range(3):
        try:
            r = cb.call(svc.call, f"req-{i}")
            print(f"  Call {i}: {r}")
        except Exception as e:
            print(f"  Call {i}: ❌ {e}")

    # Phase 2: Service becomes unhealthy
    print("\n--- Phase 2: Service unhealthy, trip the circuit ---")
    svc.make_unhealthy(duration=3)
    for i in range(5):
        try:
            cb.call(svc.call, f"req-{i}")
        except Exception as e:
            print(f"  Call {i}: ❌ {type(e).__name__}: {e}")

    print(f"\n  State after failures: {cb.state.value}")

    # Phase 3: OPEN — fast fail
    print("\n--- Phase 3: OPEN — requests rejected without calling service ---")
    before_calls = svc.calls
    for i in range(3):
        try:
            cb.call(svc.call)
        except CircuitBreakerError as e:
            print(f"  Call {i}: ⛔ {e}")
    print(f"  Service NOT called: {svc.calls - before_calls} new calls (expected 0)")

    # Phase 4: Wait for timeout → HALF_OPEN
    print("\n--- Phase 4: Wait cooldown → HALF_OPEN, probe ---")
    time.sleep(2.1)
    # Service has recovered by now
    for i in range(3):
        try:
            r = cb.call(svc.call, f"probe-{i}")
            print(f"  Probe {i}: {r}")
        except Exception as e:
            print(f"  Probe {i}: ❌ {e}")

    print(f"\n  Final state: {cb.state.value}")
    print(f"\n  Stats: {cb.stats()}")


# ============================================================
# 5. Decorator demo
# ============================================================
@circuit_breaker("user-api", CircuitBreakerConfig(failure_threshold=2, timeout=1))
def fetch_user(user_id):
    if random.random() < 0.7:
        raise ConnectionError("API timeout")
    return {"id": user_id, "name": "Ashish"}


def demo_decorator():
    print("\n" + "=" * 60)
    print("DEMO 2: Decorator-based circuit breaker")
    print("=" * 60)
    random.seed(0)
    for i in range(10):
        try:
            r = fetch_user(i)
            print(f"  Call {i}: {r}")
        except CircuitBreakerError as e:
            print(f"  Call {i}: ⛔ FAST-FAIL")
        except Exception as e:
            print(f"  Call {i}: ❌ {e}")

    cb = fetch_user.circuit_breaker
    print(f"\n  Final stats: {cb.stats()}")


# ============================================================
# 6. Retry + Circuit Breaker
# ============================================================
@circuit_breaker("retry-svc", CircuitBreakerConfig(failure_threshold=3, timeout=2))
@with_retry(retries=2, backoff=0.05)
def fetch_with_retry():
    if random.random() < 0.6:
        raise ConnectionError("transient")
    return "OK"


def demo_retry_combo():
    print("\n" + "=" * 60)
    print("DEMO 3: Retry + Circuit Breaker combo")
    print("=" * 60)
    random.seed(2)
    for i in range(10):
        try:
            r = fetch_with_retry()
            print(f"  Call {i}: {r}")
        except CircuitBreakerError:
            print(f"  Call {i}: ⛔ CIRCUIT OPEN (no retry)")
        except Exception as e:
            print(f"  Call {i}: ❌ {e}")


# ============================================================
# 7. Per-endpoint circuit breakers (production pattern)
# ============================================================
class CircuitBreakerRegistry:
    def __init__(self, default_config: CircuitBreakerConfig | None = None):
        self._cbs: dict[str, CircuitBreaker] = {}
        self._default = default_config or CircuitBreakerConfig()
        self._lock = threading.Lock()

    def get(self, name: str) -> CircuitBreaker:
        with self._lock:
            if name not in self._cbs:
                self._cbs[name] = CircuitBreaker(name, self._default)
            return self._cbs[name]

    def stats(self) -> list:
        return [cb.stats() for cb in self._cbs.values()]


def demo_registry():
    print("\n" + "=" * 60)
    print("DEMO 4: Per-endpoint registry (production pattern)")
    print("=" * 60)
    registry = CircuitBreakerRegistry()

    def call_endpoint(name, fail_rate=0.5):
        cb = registry.get(name)
        try:
            return cb.call(lambda: None if random.random() > fail_rate
                           else (_ for _ in ()).throw(IOError("fail")))
        except Exception:
            pass

    random.seed(3)
    for _ in range(20):
        call_endpoint("payment", fail_rate=0.8)
        call_endpoint("inventory", fail_rate=0.1)

    print("\n  Per-endpoint stats:")
    for s in registry.stats():
        print(f"    {s['name']:12s} [{s['state']:9s}] {s['metrics']}")


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    demo_basic()
    demo_decorator()
    demo_retry_combo()
    demo_registry()

    print("\n" + "=" * 60)
    print("KEY TAKEAWAYS")
    print("=" * 60)
    print("""
1. STATES: CLOSED → OPEN → HALF_OPEN → CLOSED
2. CLOSED:   pass through, count failures
3. OPEN:     fast-fail without calling service
4. HALF_OPEN: probe with limited traffic, decide to close or re-open
5. Combine with retry — but DON'T retry when circuit is open

PRODUCTION:
- Per-endpoint circuit breakers (registry pattern)
- Expose state + metrics for monitoring (Prometheus)
- Alert when state changes (PagerDuty)
- Excluded exceptions: 4xx HTTP, validation errors

LIBRARIES:
- pybreaker — Python circuit breaker
- circuitbreaker — alt library
- tenacity — retry + can integrate with breaker
- Resilience4j (Java) — pattern reference
""")
