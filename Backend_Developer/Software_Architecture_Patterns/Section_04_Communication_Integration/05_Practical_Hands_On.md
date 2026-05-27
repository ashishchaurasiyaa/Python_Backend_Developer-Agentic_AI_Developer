# Lecture 5 — Practical Hands-On: Building Fault-Tolerant Systems

> **Theory file:** [05_Building_Fault_Tolerant_Systems.md](05_Building_Fault_Tolerant_Systems.md)

---

## 🎯 Is Practical Mein Kya Banayenge?

End-to-end fault-tolerant system:

1. ✅ **Layered resilience** — gateway + mesh + service patterns
2. ✅ **Idempotency** with Idempotency-Key
3. ✅ **Outbox pattern** for reliable events
4. ✅ **Saga pattern** with compensation
5. ✅ **Observability stack** — Prometheus + Jaeger + ELK
6. ✅ **SLO tracking** with error budgets
7. ✅ **Chaos engineering** experiments
8. ✅ **Auto-scaling** based on queue depth
9. ✅ **Graceful shutdown**
10. ✅ **Production incident drill**

By end: aap **production-ready fault-tolerant system** bana sakte ho.

---

## 1. Project Structure

```
fault_tolerant_demo/
├── docker-compose.yml
├── README.md
│
├── services/
│   ├── order_service/
│   │   ├── main.py              # With outbox + saga
│   │   ├── saga.py
│   │   └── outbox.py
│   ├── payment_service/
│   │   ├── main.py              # With idempotency
│   │   └── idempotency.py
│   └── inventory_service/
│       └── main.py
│
├── chaos/
│   ├── chaos_monkey.py          # Kill random instances
│   ├── latency_injector.py
│   └── disk_filler.py
│
├── observability/
│   ├── metrics.py
│   ├── tracing.py
│   ├── slo_tracker.py
│   └── grafana_dashboards/
│
├── runbooks/
│   ├── high_latency.md
│   ├── circuit_open.md
│   └── queue_backlog.md
│
└── tests/
    ├── chaos/
    ├── integration/
    └── load/
```

---

## 2. Setup

```bash
pip install fastapi uvicorn httpx
pip install tenacity circuitbreaker
pip install aiokafka aio-pika
pip install redis sqlalchemy asyncpg
pip install opentelemetry-distro opentelemetry-exporter-jaeger
pip install prometheus-client
```

---

## 3. 🔁 Idempotency Implementation

### `services/payment_service/idempotency.py`

```python
"""
Production-grade idempotency for payment APIs.
Stripe-style implementation.
"""
import hashlib
import json
from typing import Optional, Callable, Awaitable
import redis.asyncio as redis
from datetime import timedelta

class IdempotencyManager:
    """
    Handles idempotency for safe retries.
    
    Behavior:
    - Same key + same body → return cached response
    - Same key + DIFFERENT body → 409 Conflict (replay protection)
    - New key → process and cache for 24h
    """
    
    def __init__(self, redis_client: redis.Redis, ttl_hours: int = 24):
        self.redis = redis_client
        self.ttl = timedelta(hours=ttl_hours)
    
    def _body_hash(self, body: dict) -> str:
        """Hash request body for replay detection"""
        serialized = json.dumps(body, sort_keys=True)
        return hashlib.sha256(serialized.encode()).hexdigest()
    
    async def execute(
        self,
        key: str,
        body: dict,
        handler: Callable[[], Awaitable[dict]],
    ) -> dict:
        """
        Execute handler with idempotency guarantee.
        """
        if not key:
            return await handler()
        
        cache_key = f"idemp:{key}"
        body_hash = self._body_hash(body)
        
        # Check cache
        cached = await self.redis.get(cache_key)
        if cached:
            cached_data = json.loads(cached)
            
            # Verify body matches
            if cached_data["body_hash"] != body_hash:
                raise ValueError(
                    "Idempotency-Key conflict: different request body"
                )
            
            return cached_data["response"]
        
        # Acquire lock to prevent concurrent processing
        lock_key = f"idemp_lock:{key}"
        acquired = await self.redis.set(
            lock_key, "1",
            ex=60,  # 60s lock
            nx=True
        )
        
        if not acquired:
            # Another request is processing
            raise ValueError("Concurrent request with same idempotency key")
        
        try:
            # Process
            response = await handler()
            
            # Cache
            await self.redis.setex(
                cache_key,
                self.ttl,
                json.dumps({
                    "body_hash": body_hash,
                    "response": response,
                })
            )
            
            return response
        
        finally:
            # Release lock
            await self.redis.delete(lock_key)
```

### Usage in FastAPI

```python
from fastapi import FastAPI, Header, HTTPException
from typing import Optional
import uuid

app = FastAPI()
idemp = IdempotencyManager(redis_client)

@app.post("/charges")
async def create_charge(
    request: dict,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    async def process():
        # Actual business logic
        transaction_id = f"txn-{uuid.uuid4().hex[:10]}"
        # ... charge customer ...
        return {
            "id": transaction_id,
            "amount": request["amount"],
            "status": "succeeded"
        }
    
    try:
        return await idemp.execute(
            key=idempotency_key,
            body=request,
            handler=process,
        )
    except ValueError as e:
        raise HTTPException(409, str(e))
```

### Test Idempotency

```bash
# First call
$ curl -X POST http://localhost:8000/charges \
    -H "Idempotency-Key: charge-001" \
    -H "Content-Type: application/json" \
    -d '{"amount": 1000}'

{"id": "txn-abc123", "status": "succeeded"}

# Same key, same body → returns SAME response (no double-charge!)
$ curl -X POST http://localhost:8000/charges \
    -H "Idempotency-Key: charge-001" \
    -H "Content-Type: application/json" \
    -d '{"amount": 1000}'

{"id": "txn-abc123", "status": "succeeded"}  ← Same!

# Same key, DIFFERENT body → 409 Conflict
$ curl -X POST http://localhost:8000/charges \
    -H "Idempotency-Key: charge-001" \
    -d '{"amount": 9999}'

409 Conflict: Idempotency-Key conflict
```

---

## 4. 📤 Outbox Pattern

### `services/order_service/outbox.py`

```python
"""
Outbox pattern: atomic DB writes + reliable event publishing.
"""
from sqlalchemy import Column, Integer, String, JSON, DateTime, Boolean, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from aiokafka import AIOKafkaProducer
from datetime import datetime
import asyncio
import json
import uuid
import logging

logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

class Order(Base):
    __tablename__ = "orders"
    id = Column(String, primary_key=True)
    user_id = Column(Integer, nullable=False)
    amount = Column(Integer, nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String, unique=True, nullable=False)
    aggregate_type = Column(String, nullable=False)
    aggregate_id = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    published_at = Column(DateTime, nullable=True)

# ─────────────────────────────────────────────────────────────
# WRITER: atomic DB + outbox
# ─────────────────────────────────────────────────────────────
async def create_order_with_event(
    session: AsyncSession,
    user_id: int,
    amount: int
) -> Order:
    """Create order AND outbox event ATOMICALLY"""
    order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"
    
    async with session.begin():
        # 1. Create order
        order = Order(
            id=order_id,
            user_id=user_id,
            amount=amount,
            status="CREATED",
        )
        session.add(order)
        
        # 2. Create outbox event in SAME transaction
        event = OutboxEvent(
            event_id=str(uuid.uuid4()),
            aggregate_type="order",
            aggregate_id=order_id,
            event_type="order.created",
            payload={
                "order_id": order_id,
                "user_id": user_id,
                "amount": amount,
            }
        )
        session.add(event)
        
        # Both commit atomically
    
    logger.info(f"✓ Order {order_id} + outbox event saved atomically")
    return order

# ─────────────────────────────────────────────────────────────
# PUBLISHER: background process
# ─────────────────────────────────────────────────────────────
class OutboxPublisher:
    """Continuously polls outbox and publishes to Kafka"""
    
    def __init__(self, session_factory, kafka_servers="localhost:9092"):
        self.session_factory = session_factory
        self.producer = AIOKafkaProducer(
            bootstrap_servers=kafka_servers,
            value_serializer=lambda v: json.dumps(v).encode(),
            acks="all",  # Wait for all replicas
            enable_idempotence=True,  # Producer-side idempotency
        )
        self.running = False
    
    async def start(self):
        await self.producer.start()
        self.running = True
        await self.run()
    
    async def stop(self):
        self.running = False
        await self.producer.stop()
    
    async def run(self):
        """Run forever, polling outbox"""
        while self.running:
            try:
                count = await self.publish_batch()
                if count == 0:
                    await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Publisher error: {e}")
                await asyncio.sleep(5)
    
    async def publish_batch(self, batch_size: int = 100) -> int:
        """Publish unpublished events"""
        async with self.session_factory() as session:
            # Lock rows to prevent concurrent publishers
            result = await session.execute(
                select(OutboxEvent)
                .where(OutboxEvent.published_at.is_(None))
                .order_by(OutboxEvent.id)
                .limit(batch_size)
                .with_for_update(skip_locked=True)
            )
            events = result.scalars().all()
            
            if not events:
                return 0
            
            for event in events:
                try:
                    await self.producer.send_and_wait(
                        event.event_type,
                        value={
                            "event_id": event.event_id,
                            "aggregate_id": event.aggregate_id,
                            "data": event.payload,
                            "timestamp": event.created_at.isoformat(),
                        },
                        key=event.aggregate_id.encode(),
                    )
                    
                    event.published_at = datetime.utcnow()
                    logger.info(f"✓ Published {event.event_id}")
                
                except Exception as e:
                    logger.error(f"Failed to publish {event.event_id}: {e}")
                    # Don't update published_at → will retry
            
            await session.commit()
            return len(events)
```

---

## 5. 🎭 Saga Pattern with Compensations

### `services/order_service/saga.py`

```python
"""
Production saga for distributed transactions.
"""
import asyncio
import logging
from typing import Callable, List, Awaitable, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

class StepStatus(Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"
    COMPENSATION_FAILED = "compensation_failed"

@dataclass
class SagaStep:
    name: str
    action: Callable[..., Awaitable[Any]]
    compensation: Optional[Callable[..., Awaitable[Any]]] = None
    status: StepStatus = StepStatus.PENDING
    result: Any = None
    error: Optional[str] = None

class Saga:
    """Distributed transaction with automatic compensation"""
    
    def __init__(self, saga_id: str, name: str):
        self.saga_id = saga_id
        self.name = name
        self.steps: List[SagaStep] = []
        self.executed: List[SagaStep] = []
    
    def add_step(
        self,
        name: str,
        action: Callable[..., Awaitable[Any]],
        compensation: Optional[Callable[..., Awaitable[Any]]] = None,
    ) -> 'Saga':
        self.steps.append(SagaStep(name=name, action=action, compensation=compensation))
        return self
    
    async def execute(self) -> dict:
        """Execute all steps, compensate on failure"""
        logger.info(f"[SAGA:{self.name}] Starting {self.saga_id}")
        
        for step in self.steps:
            try:
                await self._execute_step(step)
                self.executed.append(step)
            except Exception as e:
                logger.error(f"[SAGA:{self.name}] Failed at {step.name}: {e}")
                await self._compensate()
                return {
                    "status": "FAILED",
                    "failed_step": step.name,
                    "error": str(e),
                }
        
        logger.info(f"[SAGA:{self.name}] ✓ Completed successfully")
        return {
            "status": "SUCCESS",
            "results": [s.result for s in self.executed]
        }
    
    async def _execute_step(self, step: SagaStep):
        logger.info(f"[SAGA] Executing: {step.name}")
        try:
            step.result = await step.action()
            step.status = StepStatus.SUCCESS
            logger.info(f"[SAGA] ✓ {step.name}")
        except Exception as e:
            step.status = StepStatus.FAILED
            step.error = str(e)
            raise
    
    async def _compensate(self):
        """Run compensations in REVERSE order"""
        for step in reversed(self.executed):
            if step.compensation:
                step.status = StepStatus.COMPENSATING
                logger.info(f"[SAGA] Compensating: {step.name}")
                
                try:
                    await step.compensation(step.result)
                    step.status = StepStatus.COMPENSATED
                    logger.info(f"[SAGA] ✓ Compensated: {step.name}")
                except Exception as e:
                    step.status = StepStatus.COMPENSATION_FAILED
                    logger.error(f"[SAGA] ✗✗ Compensation FAILED for {step.name}: {e}")
                    # Critical alert! Manual intervention needed.

# ─────────────────────────────────────────────────────────────
# USAGE: Order placement saga
# ─────────────────────────────────────────────────────────────
async def place_order_saga(user_id: int, items: list):
    """Distributed transaction across multiple services"""
    order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"
    
    saga = Saga(saga_id=order_id, name="place_order")
    
    # Step 1: Reserve inventory
    saga.add_step(
        name="reserve_inventory",
        action=lambda: inventory_client.reserve(order_id, items),
        compensation=lambda r: inventory_client.release(order_id),
    )
    
    # Step 2: Charge payment
    saga.add_step(
        name="charge_payment",
        action=lambda: payment_client.charge(
            user_id=user_id,
            amount=calculate_total(items),
            idempotency_key=order_id,
        ),
        compensation=lambda r: payment_client.refund(r["txn_id"]),
    )
    
    # Step 3: Create order record (with outbox)
    saga.add_step(
        name="create_order",
        action=lambda: order_repo.create_with_outbox(order_id, user_id, items),
        # No compensation - last step
    )
    
    result = await saga.execute()
    return result
```

---

## 6. 📊 Observability Stack

### `observability/metrics.py`

```python
"""Comprehensive metrics for fault tolerance"""
from prometheus_client import Counter, Histogram, Gauge

# ─────────────────────────────────────────────────────────────
# REQUEST METRICS
# ─────────────────────────────────────────────────────────────
REQUESTS = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['service', 'method', 'endpoint', 'status']
)

LATENCY = Histogram(
    'http_request_duration_seconds',
    'Request latency',
    ['service', 'endpoint']
)

# ─────────────────────────────────────────────────────────────
# RESILIENCE METRICS
# ─────────────────────────────────────────────────────────────
RETRY_ATTEMPTS = Counter(
    'service_retry_attempts_total',
    'Retry attempts',
    ['service', 'success']
)

CIRCUIT_STATE = Gauge(
    'circuit_breaker_state',
    'Circuit state (0=closed, 1=half_open, 2=open)',
    ['service']
)

CIRCUIT_TRIPS = Counter(
    'circuit_breaker_trips_total',
    'Times circuit opened',
    ['service']
)

TIMEOUTS = Counter(
    'request_timeouts_total',
    'Total timeouts',
    ['service']
)

BULKHEAD_REJECTIONS = Counter(
    'bulkhead_rejections_total',
    'Calls rejected by bulkhead',
    ['service']
)

FALLBACK_USED = Counter(
    'fallback_invocations_total',
    'Fallback executions',
    ['service']
)

# ─────────────────────────────────────────────────────────────
# QUEUE METRICS
# ─────────────────────────────────────────────────────────────
QUEUE_DEPTH = Gauge(
    'queue_depth',
    'Messages in queue',
    ['queue']
)

CONSUMER_LAG = Gauge(
    'consumer_lag',
    'Messages behind for consumer',
    ['consumer_group', 'topic']
)

DLQ_SIZE = Gauge(
    'dead_letter_queue_size',
    'Messages in DLQ',
    ['queue']
)

# ─────────────────────────────────────────────────────────────
# SAGA METRICS
# ─────────────────────────────────────────────────────────────
SAGAS = Counter(
    'saga_executions_total',
    'Saga executions',
    ['saga_name', 'status']
)

SAGA_COMPENSATIONS = Counter(
    'saga_compensations_total',
    'Compensation actions',
    ['saga_name', 'step', 'success']
)
```

### `observability/slo_tracker.py`

```python
"""SLO tracking and error budget calculation"""
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class SLO:
    """Service Level Objective"""
    name: str
    target: float          # e.g., 0.999 (99.9%)
    window_hours: int      # Time window
    
    @property
    def error_budget(self) -> float:
        return 1.0 - self.target  # e.g., 0.001 (0.1%)
    
    @property
    def error_budget_minutes(self) -> float:
        return self.error_budget * self.window_hours * 60

class SLOTracker:
    """Tracks SLOs and calculates error budget consumption"""
    
    def __init__(self, slo: SLO):
        self.slo = slo
        # Track events in sliding window
        self.window = deque()
    
    def record(self, success: bool):
        now = time.time()
        cutoff = now - (self.slo.window_hours * 3600)
        
        # Remove old events
        while self.window and self.window[0][0] < cutoff:
            self.window.popleft()
        
        # Add new event
        self.window.append((now, success))
    
    @property
    def current_success_rate(self) -> float:
        if not self.window:
            return 1.0
        successes = sum(1 for _, s in self.window if s)
        return successes / len(self.window)
    
    @property
    def error_budget_remaining(self) -> float:
        """% of error budget left"""
        current_error_rate = 1.0 - self.current_success_rate
        budget_consumed = current_error_rate / self.slo.error_budget
        return max(0, 1 - budget_consumed)
    
    @property
    def is_burning_too_fast(self) -> bool:
        """Alert if burning budget faster than allowed"""
        return self.error_budget_remaining < 0.5

# ─────────────────────────────────────────────────────────────
# USAGE
# ─────────────────────────────────────────────────────────────
payment_slo = SLO(
    name="payment_success",
    target=0.999,
    window_hours=24
)

tracker = SLOTracker(payment_slo)

# Track each request
tracker.record(success=True)
tracker.record(success=False)

print(f"Success rate: {tracker.current_success_rate:.4%}")
print(f"Budget remaining: {tracker.error_budget_remaining:.2%}")

if tracker.is_burning_too_fast:
    print("⚠️ SLO violation imminent - alert!")
```

### `observability/tracing.py`

```python
"""Distributed tracing with OpenTelemetry"""
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

def setup_tracing(app, service_name: str):
    """Set up distributed tracing"""
    resource = Resource.create({"service.name": service_name})
    trace.set_tracer_provider(TracerProvider(resource=resource))
    
    jaeger_exporter = JaegerExporter(
        agent_host_name="jaeger",
        agent_port=6831,
    )
    
    trace.get_tracer_provider().add_span_processor(
        BatchSpanProcessor(jaeger_exporter)
    )
    
    FastAPIInstrumentor.instrument_app(app)
    HTTPXClientInstrumentor().instrument()
    
    return trace.get_tracer(service_name)
```

---

## 7. 🐒 Chaos Engineering

### `chaos/chaos_monkey.py`

```python
"""
Chaos Monkey - randomly inject failures.
Run only in staging or controlled environments!
"""
import asyncio
import random
import httpx
import docker
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class ChaosMonkey:
    """
    Inject various failures to test resilience.
    
    Experiments:
    - Kill random container
    - Inject latency
    - Drop network
    - Fill disk
    - Memory pressure
    """
    
    def __init__(self, allowed_services: list, blast_radius_pct: int = 10):
        """
        allowed_services: list of services chaos can affect
        blast_radius_pct: max % of instances to affect
        """
        self.allowed_services = allowed_services
        self.blast_radius = blast_radius_pct
        self.docker_client = docker.from_env()
    
    async def kill_random_container(self):
        """Kill a random container"""
        containers = self.docker_client.containers.list(
            filters={"name": self.allowed_services}
        )
        
        if not containers:
            return
        
        target = random.choice(containers)
        logger.warning(f"🐒 CHAOS: Killing {target.name}")
        target.kill()
        
        # Wait, then verify it was restarted
        await asyncio.sleep(30)
        running = self.docker_client.containers.list()
        names = [c.name for c in running]
        
        if target.name in names:
            logger.info(f"✓ {target.name} auto-recovered")
        else:
            logger.error(f"✗ {target.name} did NOT recover!")
    
    async def inject_latency(self, service: str, latency_ms: int, duration: int):
        """Slow down service for duration seconds"""
        logger.warning(f"🐒 CHAOS: Injecting {latency_ms}ms latency to {service}")
        
        # Using toxiproxy
        async with httpx.AsyncClient() as client:
            # Add toxic
            await client.post(
                f"http://toxiproxy:8474/proxies/{service}/toxics",
                json={
                    "name": "chaos_latency",
                    "type": "latency",
                    "attributes": {"latency": latency_ms}
                }
            )
            
            await asyncio.sleep(duration)
            
            # Remove toxic
            await client.delete(
                f"http://toxiproxy:8474/proxies/{service}/toxics/chaos_latency"
            )
        
        logger.info(f"✓ Latency removed from {service}")
    
    async def network_partition(self, service: str, duration: int):
        """Cut network for service"""
        logger.warning(f"🐒 CHAOS: Cutting network for {service}")
        
        async with httpx.AsyncClient() as client:
            await client.post(
                f"http://toxiproxy:8474/proxies/{service}/toxics",
                json={
                    "name": "chaos_drop",
                    "type": "limit_data",
                    "attributes": {"bytes": 0}
                }
            )
            
            await asyncio.sleep(duration)
            
            await client.delete(
                f"http://toxiproxy:8474/proxies/{service}/toxics/chaos_drop"
            )
    
    async def run_continuous(self):
        """Run chaos experiments on schedule"""
        experiments = [
            self.kill_random_container,
            lambda: self.inject_latency("payment-svc", 2000, 60),
            lambda: self.network_partition("inventory-svc", 30),
        ]
        
        while True:
            # Random experiment
            experiment = random.choice(experiments)
            
            logger.info(f"Starting experiment at {datetime.utcnow()}")
            
            try:
                await experiment()
            except Exception as e:
                logger.error(f"Experiment failed: {e}")
            
            # Wait between experiments
            wait_time = random.randint(300, 600)  # 5-10 min
            logger.info(f"Next experiment in {wait_time}s")
            await asyncio.sleep(wait_time)

# Schedule (only in non-prod!)
chaos = ChaosMonkey(
    allowed_services=["payment-svc", "inventory-svc", "order-svc"],
    blast_radius_pct=20,
)
asyncio.run(chaos.run_continuous())
```

### Hypothesis-Driven Experiment

```python
"""
Run specific hypothesis-driven experiment.
"""
import asyncio
import httpx

async def experiment_payment_resilience():
    """
    HYPOTHESIS: If payment service is down for 60s,
                checkout still works via async fallback.
    
    EXPERIMENT: Kill payment service for 60s, hit checkout.
    
    SUCCESS: 
       - Checkout endpoint returns 200 (with queued status)
       - User sees "Processing..." message
       - Order is eventually completed
    
    FAILURE:
       - Checkout returns 5xx
       - User sees error
       - No graceful degradation
    """
    print("Starting experiment: Payment service resilience")
    
    # 1. Baseline (normal operation)
    print("\n[BASELINE] Hitting checkout normally...")
    baseline_results = []
    for _ in range(10):
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                r = await client.post("http://localhost:8000/checkout", 
                                        json={"items": [...]})
                baseline_results.append(r.status_code)
            except Exception as e:
                baseline_results.append(f"error: {e}")
    
    print(f"Baseline results: {baseline_results}")
    success_rate_baseline = sum(1 for r in baseline_results if r == 200) / len(baseline_results)
    print(f"Baseline success rate: {success_rate_baseline:.2%}")
    
    # 2. Inject chaos: kill payment service
    print("\n[CHAOS] Killing payment service for 60s...")
    docker.from_env().containers.get("payment-svc").kill()
    
    # 3. During chaos: hit checkout
    print("[CHAOS] Hitting checkout during outage...")
    chaos_results = []
    for _ in range(20):
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                r = await client.post("http://localhost:8000/checkout", 
                                        json={"items": [...]})
                chaos_results.append({
                    "status": r.status_code,
                    "body": r.json() if r.status_code < 400 else None,
                })
            except Exception as e:
                chaos_results.append({"error": str(e)})
        
        await asyncio.sleep(2)
    
    # 4. Wait for recovery
    await asyncio.sleep(70)
    
    # 5. Verify recovery
    print("\n[RECOVERY] Hitting checkout after recovery...")
    recovery_results = []
    for _ in range(10):
        async with httpx.AsyncClient() as client:
            r = await client.post("http://localhost:8000/checkout", 
                                    json={"items": [...]})
            recovery_results.append(r.status_code)
    
    # 6. Analyze
    print("\n[RESULTS]")
    success_during_chaos = sum(
        1 for r in chaos_results 
        if isinstance(r, dict) and r.get("status") == 200
    )
    print(f"Successful checkouts during chaos: {success_during_chaos}/20")
    
    if success_during_chaos >= 18:  # Allow 10% failure
        print("✓ HYPOTHESIS CONFIRMED: System resilient to payment outage")
    else:
        print("✗ HYPOTHESIS FAILED: System NOT resilient. Fix gaps!")

asyncio.run(experiment_payment_resilience())
```

---

## 8. 🛑 Graceful Shutdown

### `services/order_service/graceful_shutdown.py`

```python
"""
Graceful shutdown - handle SIGTERM properly.
Critical for K8s deployments.
"""
import asyncio
import signal
from contextlib import asynccontextmanager
from fastapi import FastAPI
import logging

logger = logging.getLogger(__name__)

class GracefulShutdown:
    """Track in-flight requests and wait for completion before shutdown"""
    
    def __init__(self):
        self.in_flight = 0
        self.shutdown_event = asyncio.Event()
    
    async def track_request(self, request_handler):
        self.in_flight += 1
        try:
            return await request_handler()
        finally:
            self.in_flight -= 1
            if self.shutdown_event.is_set() and self.in_flight == 0:
                logger.info("All requests drained, ready to shut down")
    
    async def wait_for_drain(self, timeout: float = 30.0):
        """Wait for in-flight requests to complete"""
        logger.info(f"Waiting for {self.in_flight} in-flight requests to drain...")
        
        start = asyncio.get_event_loop().time()
        while self.in_flight > 0:
            if asyncio.get_event_loop().time() - start > timeout:
                logger.warning(f"Timeout: {self.in_flight} requests still in flight")
                break
            await asyncio.sleep(0.1)
        
        logger.info("Drain complete")

shutdown = GracefulShutdown()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Service starting...")
    
    # Set up signal handlers
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig,
            lambda s=sig: asyncio.create_task(handle_shutdown(s))
        )
    
    yield  # App runs
    
    # Shutdown
    logger.info("Shutdown initiated...")
    
    # 1. Stop accepting new requests (handled by framework)
    # 2. Wait for in-flight to drain
    await shutdown.wait_for_drain(timeout=30)
    
    # 3. Close resources
    await close_db_connections()
    await flush_pending_events()
    
    logger.info("Shutdown complete")

async def handle_shutdown(sig):
    logger.info(f"Received signal {sig}")
    shutdown.shutdown_event.set()
```

---

## 9. 📈 Auto-Scaling Based on Queue Depth

### Kubernetes HPA Configuration

```yaml
# k8s/order-worker-hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: order-worker
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: order-worker
  minReplicas: 2
  maxReplicas: 20
  metrics:
  # Scale based on queue depth
  - type: External
    external:
      metric:
        name: kafka_consumer_lag
        selector:
          matchLabels:
            consumer_group: order-worker
            topic: orders
      target:
        type: AverageValue
        averageValue: "100"  # Each pod handles 100 messages of lag
  
  # Also scale on CPU
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 30   # Quick to scale up
      policies:
      - type: Percent
        value: 100  # Double instances
        periodSeconds: 30
    scaleDown:
      stabilizationWindowSeconds: 300  # Slow to scale down
      policies:
      - type: Percent
        value: 25
        periodSeconds: 60
```

---

## 10. 📚 Runbooks

### `runbooks/high_latency.md`

```markdown
# Runbook: High Latency Alert

## Alert
P99 latency for order-service > 2s for 5 minutes

## Severity
SEV-2

## First Response (within 15 min)
1. Check dashboard: http://grafana/order-service
2. Identify which endpoint is slow:
   ```
   sum by (endpoint) (rate(http_request_duration_seconds_bucket[5m]))
   ```
3. Check downstream services in trace: http://jaeger

## Common Causes
1. **DB slow query** → check pg_stat_activity
2. **Cache miss storm** → check redis-info
3. **Downstream API slow** → check Jaeger traces
4. **Network issue** → check VPC flow logs

## Mitigation
1. **Scale up**: `kubectl scale deploy order-service --replicas=10`
2. **Enable circuit breaker on slow dependency**: feature flag
3. **Flush hot cache key if necessary**

## Long-term Fix
Create JIRA ticket if pattern repeats.
```

---

## 11. 🐳 Complete Docker Compose Stack

```yaml
version: '3.8'

services:
  # ───── Databases ─────
  postgres:
    image: postgres:15
    ports: ["5432:5432"]
    environment:
      POSTGRES_USER: app
      POSTGRES_PASSWORD: app
      POSTGRES_DB: orders
  
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
  
  # ───── Messaging ─────
  zookeeper:
    image: confluentinc/cp-zookeeper:7.5.0
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
  
  kafka:
    image: confluentinc/cp-kafka:7.5.0
    depends_on: [zookeeper]
    ports: ["9092:9092"]
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
  
  # ───── Observability ─────
  prometheus:
    image: prom/prometheus
    volumes:
      - ./observability/prometheus.yml:/etc/prometheus/prometheus.yml
    ports: ["9090:9090"]
  
  grafana:
    image: grafana/grafana
    ports: ["3000:3000"]
    environment:
      GF_SECURITY_ADMIN_PASSWORD: admin
    depends_on: [prometheus]
  
  jaeger:
    image: jaegertracing/all-in-one
    ports:
      - "16686:16686"
      - "6831:6831/udp"
  
  # ───── Chaos ─────
  toxiproxy:
    image: shopify/toxiproxy
    ports:
      - "8474:8474"  # admin
      - "8001:8001"  # proxy
  
  # ───── Services ─────
  order-service:
    build: ./services/order_service
    ports: ["8001:8001"]
    depends_on: [postgres, kafka, redis]
    environment:
      - JAEGER_HOST=jaeger
  
  payment-service:
    build: ./services/payment_service
    ports: ["8002:8002"]
    depends_on: [redis]
    environment:
      - JAEGER_HOST=jaeger
  
  inventory-service:
    build: ./services/inventory_service
    ports: ["8003:8003"]
    depends_on: [kafka]
```

---

## 12. 🎯 Production Incident Drill

```python
"""
Simulated production incident drill.
"""
import asyncio
import httpx
import random
from datetime import datetime

async def incident_drill():
    """
    Simulate a real incident scenario.
    Practice incident response.
    """
    print(f"=" * 60)
    print(f"INCIDENT DRILL - {datetime.utcnow().isoformat()}")
    print(f"=" * 60)
    
    print("""
    SCENARIO:
    User complaints flooding in: "Checkout is broken!"
    
    Your tasks:
    1. Identify the issue (use observability tools)
    2. Mitigate (reduce user impact)
    3. Root cause analysis
    4. Permanent fix
    5. Write postmortem
    """)
    
    # Inject a hidden problem
    print("\n[CHAOS] Injecting unknown failure mode...")
    
    # Random chaos
    chaos_type = random.choice([
        "db_slow",
        "payment_circuit_open",
        "kafka_lag",
        "cache_evicted",
    ])
    
    await inject_chaos(chaos_type)
    
    print("\n[INCIDENT START] You're paged at 3 AM. GO!")
    
    # Drill timer
    start = datetime.utcnow()
    
    # Wait for user to mitigate
    input("\nPress ENTER when you've mitigated the issue...")
    mitigation_time = (datetime.utcnow() - start).total_seconds()
    
    # Wait for root cause identification
    root_cause_input = input("\nWhat was the root cause? > ")
    
    correct = chaos_type in root_cause_input.lower().replace("_", " ")
    
    print(f"\n=" * 60)
    print(f"DRILL RESULTS")
    print(f"=" * 60)
    print(f"Mitigation time: {mitigation_time:.0f} seconds")
    print(f"Root cause identified: {'✓' if correct else '✗'}")
    print(f"Actual cause: {chaos_type}")
    
    if mitigation_time > 1800:  # 30 min
        print("⚠️  Slow mitigation - improve runbooks")
    if not correct:
        print("⚠️  Wrong root cause - improve observability")

asyncio.run(incident_drill())
```

---

## 13. Key Learnings Summary

```
✅ Idempotency-Key prevents duplicate operations
✅ Outbox pattern guarantees event delivery
✅ Saga + compensations handle distributed transactions
✅ Layered observability (logs + metrics + traces)
✅ SLO tracking with error budgets
✅ Chaos engineering builds confidence
✅ Graceful shutdown handles SIGTERM properly
✅ Auto-scaling based on real metrics (queue depth)
✅ Runbooks for fast incident response
✅ Regular incident drills

🎯 Production resilience stack:
   - Idempotent endpoints
   - Outbox + Kafka for events
   - Saga for transactions
   - Full observability
   - SLO-driven operations
   - Chaos testing in staging
   - Auto-recovery via HPA
```

---

## 🎬 Section Complete!

Congratulations! You've completed **Section 4: Communication & Integration Patterns**!

### Files Created

```
Section_04_Communication_Integration/
├── 01_Sync_vs_Async_Communication.md      (theory)
├── 01_Practical_Hands_On.md                (practical)
├── 02_API_Gateway_BFF.md                   (theory)
├── 02_Practical_Hands_On.md                (practical)
├── 03_Messaging_Event_Brokers.md           (theory)
├── 03_Practical_Hands_On.md                (practical)
├── 04_Resilience_Patterns.md               (theory)
├── 04_Practical_Hands_On.md                (practical)
├── 05_Building_Fault_Tolerant_Systems.md   (theory)
└── 05_Practical_Hands_On.md                (practical)  ← you are here
```

### What You Can Now Build

```
✓ Hybrid sync + async systems
✓ Custom API gateways with auth/rate limiting
✓ BFFs for different clients
✓ Production messaging with Kafka/RabbitMQ
✓ Idempotent + resilient endpoints
✓ Saga-based distributed transactions
✓ Outbox pattern for reliable events
✓ Chaos engineering experiments
✓ Full observability + SLO tracking
✓ Graceful shutdowns + auto-scaling
```

---

## 🚀 Next Steps

Continue your journey with:
- **Section 5**: Security & Governance in Architecture
- **Section 6**: Event-Driven & Reactive Systems
- **Section 7**: Cloud-Native & Scalable Architecture
- **Section 8**: UI Architecture Patterns
- **Section 9**: Architectural Decision-Making
- **Section 10**: Conclusion & Next Steps

Good luck building resilient systems! 🎓
