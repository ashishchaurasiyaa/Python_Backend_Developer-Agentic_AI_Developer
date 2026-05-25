"""
Phase3_Microservices — Complete Practical
==========================================
Topics covered:
  1. Circuit Breaker (CLOSED/OPEN/HALF_OPEN)
  2. Retry with exponential backoff + jitter
  3. Saga Pattern (orchestration + choreography)
  4. Event-Driven Architecture (in-process EventBus)
  5. CQRS (Command/Query separation)
  6. API Gateway pattern (aggregation + auth + rate limit)
  7. Service health check / heartbeat
  8. Inter-service communication patterns

Run:
  python 01_microservices_practical.py
"""

import asyncio
import random
import time
import json
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Awaitable
from collections import defaultdict

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Circuit Breaker
# INTERVIEW: Cascade failure rokne ka pattern
# CLOSED → OPEN (on failures) → HALF_OPEN (after timeout) → CLOSED/OPEN
# ─────────────────────────────────────────────────────────────────────────────

class CircuitState(Enum):
    CLOSED    = "closed"     # Normal — all calls pass through
    OPEN      = "open"       # Failing — all calls rejected (fast fail)
    HALF_OPEN = "half_open"  # Testing — limited calls to check recovery


class CircuitBreakerOpenError(Exception):
    pass


@dataclass
class CircuitBreaker:
    """
    INTERVIEW: Circuit Breaker states:
    CLOSED → if failures >= threshold → OPEN
    OPEN   → after recovery_timeout → HALF_OPEN
    HALF_OPEN → if success >= success_threshold → CLOSED
              → if any failure → OPEN again
    """
    name:              str
    failure_threshold: int   = 5
    recovery_timeout:  float = 10.0   # seconds
    success_threshold: int   = 2

    _state:           CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failures:        int          = field(default=0, init=False)
    _successes:       int          = field(default=0, init=False)
    _last_fail_time:  float        = field(default=0.0, init=False)
    _call_count:      int          = field(default=0, init=False)

    @property
    def state(self) -> CircuitState:
        """Auto-transition OPEN → HALF_OPEN after timeout."""
        if self._state == CircuitState.OPEN:
            elapsed = time.time() - self._last_fail_time
            if elapsed >= self.recovery_timeout:
                self._state    = CircuitState.HALF_OPEN
                self._successes = 0
                print(f"  [CB:{self.name}] → HALF_OPEN (testing recovery after {elapsed:.1f}s)")
        return self._state

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        self._call_count += 1

        if self.state == CircuitState.OPEN:
            raise CircuitBreakerOpenError(
                f"Circuit '{self.name}' is OPEN — service unavailable (fast fail)"
            )

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except CircuitBreakerOpenError:
            raise
        except Exception as e:
            self._on_failure(e)
            raise

    def _on_success(self):
        if self._state == CircuitState.HALF_OPEN:
            self._successes += 1
            if self._successes >= self.success_threshold:
                self._state   = CircuitState.CLOSED
                self._failures = 0
                print(f"  [CB:{self.name}] → CLOSED (service recovered!)")
        elif self._state == CircuitState.CLOSED:
            self._failures = 0

    def _on_failure(self, exc: Exception):
        self._failures      += 1
        self._last_fail_time = time.time()
        print(f"  [CB:{self.name}] Failure #{self._failures}/{self.failure_threshold}: {exc}")
        if self._failures >= self.failure_threshold:
            self._state = CircuitState.OPEN
            print(f"  [CB:{self.name}] → OPEN (circuit tripped!)")
        elif self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
            print(f"  [CB:{self.name}] → OPEN (half-open test failed)")

    def status(self) -> dict:
        return {
            "name": self.name, "state": self.state.value,
            "failures": self._failures, "total_calls": self._call_count,
        }


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Retry with Exponential Backoff + Jitter
# INTERVIEW: Retry storms rokne ke liye jitter important hai
# ─────────────────────────────────────────────────────────────────────────────

async def retry_with_backoff(
    func:           Callable,
    *args,
    max_attempts:   int   = 3,
    base_delay:     float = 1.0,
    max_delay:      float = 30.0,
    backoff_factor: float = 2.0,
    jitter:         bool  = True,
    **kwargs,
) -> Any:
    """
    INTERVIEW: Exponential backoff formula:
    delay = min(base_delay * backoff_factor^attempt, max_delay)
    jitter = delay * random(0.5, 1.5)  ← prevents retry storm (thundering herd)
    """
    last_exception = None
    for attempt in range(max_attempts):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            if attempt == max_attempts - 1:
                break

            delay = min(base_delay * (backoff_factor ** attempt), max_delay)
            if jitter:
                delay *= random.uniform(0.5, 1.5)   # ← jitter prevents thundering herd

            print(f"  [Retry] Attempt {attempt + 1}/{max_attempts} failed: {e}")
            print(f"          Waiting {delay:.2f}s before retry...")
            await asyncio.sleep(delay)

    raise last_exception


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Saga Pattern
# INTERVIEW: Distributed transactions without 2PC (2-Phase Commit)
# ─────────────────────────────────────────────────────────────────────────────

# ── Saga Step ──────────────────────────────────────────────────────────────

@dataclass
class SagaStep:
    name:           str
    action:         Callable
    compensate:     Callable  # Rollback action


class SagaOrchestrator:
    """
    INTERVIEW: Orchestration Saga = central coordinator
    vs Choreography Saga = services react to each other's events

    Orchestration:
      + Clearer flow, easy to debug
      - Single point of failure (orchestrator)

    Choreography:
      + Truly decoupled
      - Hard to debug, no central view
    """

    async def execute(self, steps: list[SagaStep], context: dict) -> dict:
        completed_steps: list[SagaStep] = []

        for step in steps:
            try:
                print(f"  [Saga] Executing: {step.name}")
                result = await step.action(context)
                context[step.name] = result
                completed_steps.append(step)
                print(f"  [Saga] ✓ {step.name}: {result}")

            except Exception as e:
                print(f"  [Saga] ✗ {step.name} FAILED: {e}")
                print(f"  [Saga] Starting compensations (reverse order)...")

                # Compensate in reverse order
                for completed in reversed(completed_steps):
                    try:
                        print(f"  [Saga] Compensating: {completed.name}")
                        await completed.compensate(context)
                        print(f"  [Saga] ✓ Compensation done: {completed.name}")
                    except Exception as comp_err:
                        print(f"  [Saga] ✗ Compensation FAILED for {completed.name}: {comp_err}")
                        # Log for manual intervention — saga stuck!

                raise e

        return context


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Event-Driven Architecture (In-Process EventBus)
# INTERVIEW: Loose coupling — publisher doesn't know subscribers
# ─────────────────────────────────────────────────────────────────────────────

class EventBus:
    """
    INTERVIEW: Production mein Kafka / RabbitMQ / AWS SQS use karo.
    This simulates the publish/subscribe pattern in-process.
    """

    def __init__(self):
        self._handlers: dict[str, list[Callable]] = defaultdict(list)
        self._event_log: list[dict] = []

    def subscribe(self, event_type: str, handler: Callable):
        self._handlers[event_type].append(handler)
        print(f"  [EventBus] Subscribed: {handler.__name__} → {event_type}")

    async def publish(self, event_type: str, data: dict) -> None:
        event = {
            "id":         str(uuid.uuid4())[:8],
            "type":       event_type,
            "data":       data,
            "timestamp":  time.time(),
        }
        self._event_log.append(event)
        print(f"  [EventBus] Publishing: {event_type} → {data}")

        handlers = self._handlers.get(event_type, [])
        if not handlers:
            print(f"  [EventBus] No subscribers for {event_type}")
            return

        # Execute all handlers concurrently
        await asyncio.gather(
            *[handler(event["data"]) for handler in handlers],
            return_exceptions=True
        )

    def event_count(self) -> int:
        return len(self._event_log)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: CQRS Pattern
# INTERVIEW: Command = write, Query = read (separate models + handlers)
# ─────────────────────────────────────────────────────────────────────────────

# ── Write side (Commands) ──────────────────────────────────────────────────

@dataclass
class CreateOrderCommand:
    user_id:  int
    items:    list[dict]
    amount:   float


@dataclass
class Order:
    id:       str
    user_id:  int
    items:    list[dict]
    amount:   float
    status:   str = "pending"


# Normalized write store
ORDERS_WRITE_DB: dict[str, Order] = {}


class OrderCommandHandler:
    """
    INTERVIEW: Command side = normalized, ACID transactions, validation-heavy.
    After write: publish event → read model (projection) update karo.
    """

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus

    async def handle_create(self, cmd: CreateOrderCommand) -> str:
        order = Order(
            id      = str(uuid.uuid4())[:8],
            user_id = cmd.user_id,
            items   = cmd.items,
            amount  = cmd.amount,
        )
        ORDERS_WRITE_DB[order.id] = order

        # Publish event → read model will update
        await self.event_bus.publish("order.created", {
            "order_id": order.id, "user_id": order.user_id,
            "amount": order.amount, "item_count": len(order.items),
        })
        return order.id


# ── Read side (Queries) — denormalized view ───────────────────────────────

@dataclass
class OrderSummaryView:
    """
    INTERVIEW: Read model = denormalized, optimized for display.
    Updated via events from write side.
    May be on different DB (e.g., write→PostgreSQL, read→Elasticsearch).
    """
    order_id:   str
    user_name:  str   # denormalized from Users
    amount:     float
    item_count: int
    status:     str


ORDERS_READ_DB: dict[str, OrderSummaryView] = {}

# Fake users for denormalization
USERS = {1: "Alice Johnson", 2: "Bob Smith", 3: "Charlie Lee"}


class OrderQueryHandler:
    async def get_user_orders(self, user_id: int) -> list[OrderSummaryView]:
        return [v for v in ORDERS_READ_DB.values() if True]  # simplified

    async def get_order(self, order_id: str) -> OrderSummaryView | None:
        return ORDERS_READ_DB.get(order_id)


async def update_order_read_model(event_data: dict) -> None:
    """
    INTERVIEW: Event handler updates read model.
    This is the "projection" in CQRS event sourcing.
    """
    order_id  = event_data["order_id"]
    user_id   = event_data["user_id"]
    view = OrderSummaryView(
        order_id   = order_id,
        user_name  = USERS.get(user_id, "Unknown"),
        amount     = event_data["amount"],
        item_count = event_data["item_count"],
        status     = "pending",
    )
    ORDERS_READ_DB[order_id] = view
    print(f"  [ReadModel] Updated: order {order_id} for {view.user_name}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: API Gateway Pattern
# INTERVIEW: Single entry point, aggregates multiple services
# ─────────────────────────────────────────────────────────────────────────────

class ApiGateway:
    """
    INTERVIEW: API Gateway responsibilities:
    1. Authentication / Authorization
    2. Rate limiting
    3. Request aggregation (BFF - Backend for Frontend)
    4. Protocol translation
    5. Load balancing
    6. SSL termination
    7. Request/Response transformation
    """

    def __init__(self):
        self._rate_limits: dict[str, list[float]] = defaultdict(list)
        self._valid_tokens = {"token-alice": 1, "token-bob": 2}

    def authenticate(self, token: str) -> int | None:
        return self._valid_tokens.get(token)

    def check_rate_limit(self, user_id: int, limit: int = 10, window: float = 1.0) -> bool:
        """Sliding window rate limit."""
        now = time.time()
        key = f"user:{user_id}"
        calls = [t for t in self._rate_limits[key] if now - t < window]
        self._rate_limits[key] = calls

        if len(calls) >= limit:
            return False

        self._rate_limits[key].append(now)
        return True

    async def handle_request(self, path: str, token: str, data: dict = None) -> dict:
        """
        INTERVIEW: Gateway aggregates responses from multiple services.
        Fan-out: call multiple services concurrently → merge results.
        """
        user_id = self.authenticate(token)
        if not user_id:
            return {"error": "Unauthorized", "status": 401}

        if not self.check_rate_limit(user_id):
            return {"error": "Rate limit exceeded", "status": 429}

        if path == "/dashboard":
            # BFF: aggregate multiple service calls concurrently
            user_data, orders, notifications = await asyncio.gather(
                self._call_user_service(user_id),
                self._call_order_service(user_id),
                self._call_notification_service(user_id),
            )
            return {
                "user":          user_data,
                "orders":        orders,
                "notifications": notifications,
                "status":        200,
            }

        return {"error": "Not found", "status": 404}

    async def _call_user_service(self, user_id: int) -> dict:
        await asyncio.sleep(0.01)  # simulate network
        return {"id": user_id, "name": USERS.get(user_id, "Unknown")}

    async def _call_order_service(self, user_id: int) -> list:
        await asyncio.sleep(0.02)
        return [{"order_id": oid, "status": v.status}
                for oid, v in ORDERS_READ_DB.items()]

    async def _call_notification_service(self, user_id: int) -> list:
        await asyncio.sleep(0.01)
        return [{"type": "email", "msg": "Your order is ready"}]


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: Service Health Checks
# INTERVIEW: Kubernetes liveness/readiness probe ka Python equivalent
# ─────────────────────────────────────────────────────────────────────────────

class ServiceRegistry:
    """
    INTERVIEW: Service discovery pattern.
    Production: use Consul, AWS Route53, Kubernetes DNS
    """

    def __init__(self):
        self._services: dict[str, dict] = {}

    def register(self, name: str, url: str, health_url: str):
        self._services[name] = {
            "url": url, "health_url": health_url,
            "status": "unknown", "last_check": None,
        }

    async def health_check_all(self):
        for name, info in self._services.items():
            try:
                # Simulate health check (real: aiohttp GET health_url)
                await asyncio.sleep(0.01)
                is_healthy = random.random() > 0.2  # 80% healthy
                info["status"]     = "healthy" if is_healthy else "unhealthy"
                info["last_check"] = time.time()
            except Exception as e:
                info["status"] = f"error: {e}"

    def get_healthy(self, name: str) -> str | None:
        info = self._services.get(name)
        if info and info["status"] == "healthy":
            return info["url"]
        return None


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8: Demo Runner
# ─────────────────────────────────────────────────────────────────────────────

async def run_demo():
    print("=" * 60)
    print("MICROSERVICES PATTERNS DEMO")
    print("=" * 60)

    # ── 1. Circuit Breaker ──
    print("\n[1] Circuit Breaker Demo")
    print("-" * 40)
    cb = CircuitBreaker("payment-service", failure_threshold=3, recovery_timeout=0.5)

    call_count = 0
    async def payment_service(should_fail: bool = False):
        nonlocal call_count
        call_count += 1
        if should_fail:
            raise ConnectionError("Payment service connection refused")
        return {"payment_id": f"pay_{call_count}", "status": "success"}

    # Successful calls
    for _ in range(2):
        r = await cb.call(payment_service, False)
        print(f"  ✓ Success: {r}")

    # Trigger failures → OPEN
    for _ in range(3):
        try:
            await cb.call(payment_service, True)
        except ConnectionError:
            pass
        except CircuitBreakerOpenError as e:
            print(f"  ⚡ Fast fail: {e}")

    # Try when OPEN
    try:
        await cb.call(payment_service, False)
    except CircuitBreakerOpenError as e:
        print(f"  ⚡ Circuit OPEN: {e}")

    print(f"\n  CB Status: {cb.status()}")

    # Wait for recovery_timeout → HALF_OPEN
    print("  Waiting for recovery timeout (0.5s)...")
    await asyncio.sleep(0.6)

    # Success in HALF_OPEN → CLOSED
    for _ in range(2):
        r = await cb.call(payment_service, False)
        print(f"  ✓ Recovery success: {r}")
    print(f"  CB Status after recovery: {cb.status()}")

    # ── 2. Retry with Backoff ──
    print("\n[2] Retry with Exponential Backoff + Jitter")
    print("-" * 40)
    attempt_num = 0

    async def flaky_service():
        nonlocal attempt_num
        attempt_num += 1
        if attempt_num < 3:
            raise TimeoutError(f"Service timeout (attempt {attempt_num})")
        return {"data": "finally worked!"}

    result = await retry_with_backoff(
        flaky_service, max_attempts=3, base_delay=0.1
    )
    print(f"  Final result: {result}")

    # ── 3. Saga Pattern ──
    print("\n[3] Saga Pattern (Orchestration)")
    print("-" * 40)

    # Simulate e-commerce order flow
    order_context = {"user_id": 1, "amount": 99.99, "items": ["product-1"]}

    # Mock service calls
    async def create_order(ctx): return f"order_{uuid.uuid4().hex[:6]}"
    async def charge_payment(ctx): return f"pay_{uuid.uuid4().hex[:6]}"
    async def reserve_inventory(ctx):
        if random.random() < 0.3:  # 30% chance of failure
            raise Exception("Insufficient stock!")
        return "reserved"
    async def send_confirmation(ctx): return "email_sent"

    # Compensating transactions
    async def cancel_order(ctx):      print(f"    ↩ Cancelling order {ctx.get('create_order')}")
    async def refund_payment(ctx):    print(f"    ↩ Refunding {ctx.get('charge_payment')}")
    async def release_inventory(ctx): print(f"    ↩ Releasing inventory")
    async def noop(ctx): pass

    saga = SagaOrchestrator()
    steps = [
        SagaStep("create_order",      create_order,      cancel_order),
        SagaStep("charge_payment",    charge_payment,    refund_payment),
        SagaStep("reserve_inventory", reserve_inventory, release_inventory),
        SagaStep("send_confirmation", send_confirmation, noop),
    ]

    # Run up to 3 times to show both success and failure scenarios
    for attempt in range(3):
        try:
            result = await saga.execute(steps, order_context.copy())
            print(f"  ✓ Saga completed: {result}")
            break
        except Exception as e:
            print(f"  ✗ Saga failed (attempt {attempt+1}): {e}")

    # ── 4. Event-Driven / CQRS ──
    print("\n[4] Event-Driven + CQRS Demo")
    print("-" * 40)

    event_bus = EventBus()
    # Subscribe read model updater
    event_bus.subscribe("order.created", update_order_read_model)
    event_bus.subscribe("order.created", lambda d: asyncio.create_task(
        asyncio.coroutine(lambda: print(f"  [Notify] User {d['user_id']} notified"))()
    ))

    # CQRS Command Handler
    cmd_handler   = OrderCommandHandler(event_bus)
    query_handler = OrderQueryHandler()

    # Write side: create orders
    for user_id, amount in [(1, 49.99), (2, 129.50)]:
        order_id = await cmd_handler.handle_create(CreateOrderCommand(
            user_id=user_id,
            items=[{"product": "widget", "qty": 2}],
            amount=amount,
        ))
        print(f"  Write: Created order {order_id}")

    # Read side: query the denormalized view
    print("\n  Read model (denormalized):")
    for oid, view in ORDERS_READ_DB.items():
        print(f"    Order {oid}: {view.user_name} — ${view.amount} — {view.item_count} items")

    # ── 5. API Gateway ──
    print("\n[5] API Gateway Demo")
    print("-" * 40)
    gateway = ApiGateway()

    result = await gateway.handle_request("/dashboard", "token-alice")
    print(f"  Dashboard response: user={result['user']['name']}")
    print(f"  Orders count: {len(result['orders'])}")
    print(f"  Notifications: {result['notifications']}")

    # Unauthorized
    result = await gateway.handle_request("/dashboard", "INVALID-TOKEN")
    print(f"  Invalid token: {result}")

    # ── 6. Service Registry ──
    print("\n[6] Service Health Check")
    print("-" * 40)
    registry = ServiceRegistry()
    registry.register("user-service",    "http://users:8001",    "/health")
    registry.register("order-service",   "http://orders:8002",   "/health")
    registry.register("payment-service", "http://payments:8003", "/health")

    await registry.health_check_all()
    for name, info in registry._services.items():
        print(f"  {name}: {info['status']}")

    # ── Summary ──
    print("\n" + "=" * 60)
    print("MICROSERVICES PATTERNS INTERVIEW SUMMARY")
    print("=" * 60)
    patterns = [
        ("Circuit Breaker",    "Cascade failure rokna",      "CLOSED→OPEN→HALF_OPEN states"),
        ("Retry + Backoff",    "Transient failures handle",  "Jitter = thundering herd rokta hai"),
        ("Saga",               "Distributed transactions",   "Compensating transactions for rollback"),
        ("Event-Driven",       "Loose coupling",             "Publisher doesn't know subscribers"),
        ("CQRS",               "Read/Write alag karo",       "Different models, different DBs"),
        ("API Gateway",        "Single entry point",         "Auth + rate limit + aggregation"),
        ("Service Discovery",  "Dynamic service location",   "Consul, K8s DNS, Route53"),
    ]
    for pattern, what, how in patterns:
        print(f"  {pattern:<20} │ {what:<28} │ {how}")


if __name__ == "__main__":
    asyncio.run(run_demo())
