# Microservices — Service Decomposition, Circuit Breaker, Saga, Event-Driven, CQRS

## Quick Concepts
- **Microservices** = ek bada app → chote independent services mein tod do
- **Circuit Breaker** = failing service ko calls band karo — cascade failure rokta hai
- **Saga Pattern** = distributed transactions — rollback logic chain karo
- **Event-Driven** = services events publish/consume karte hain (loose coupling)
- **CQRS** = Command Query Responsibility Segregation — read aur write alag

---

## Interview Questions & Answers

### Q1: Monolith vs Microservices — kab kya choose karo?
**Answer:**
```
MONOLITH choose karo jab:
- Team chhoti hai (< 10 devs)
- Product naya hai — requirements change hoti hain
- Domain well-understood nahi hai
- Simple deployment chahiye

MICROSERVICES choose karo jab:
- Different parts ko alag scale karna ho (checkout vs search)
- Different teams alag components own karein
- Technology diversity chahiye (Python + Go + Node)
- High availability — ek service down = baaki chal rahi hain

Domain-Driven Design se decompose karo:
  E-commerce → User Service, Product Service, Order Service,
               Payment Service, Notification Service, Inventory Service

Decomposition principles:
  - Single Responsibility: ek service ek bounded context
  - Loose Coupling: services independently deploy ho sakein
  - High Cohesion: related logic ek saath
  - Database per service: shared DB mat karo!
```

---

### Q2: Circuit Breaker pattern kya hai? Python mein kaise implement karte hain?
**Answer:**
```
PROBLEM: Service B down hai → Service A baar baar call karta hai → timeouts → thread pool exhaust → Service A bhi down

SOLUTION: Circuit Breaker
  CLOSED state: normal — sab calls allow
  OPEN state: circuit trip ho gaya — calls immediately fail (fast fail)
  HALF-OPEN: thodi calls allow karo — recover hua kya check karo
```

```python
from enum import Enum
import asyncio
import time
from dataclasses import dataclass, field

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

@dataclass
class CircuitBreaker:
    failure_threshold: int = 5       # kitne failures par open ho
    recovery_timeout: int = 30       # seconds open rehne ke baad half-open
    success_threshold: int = 2       # half-open mein kitne success par close ho

    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failures: int = field(default=0, init=False)
    _last_failure_time: float = field(default=0.0, init=False)
    _successes: int = field(default=0, init=False)

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.time() - self._last_failure_time > self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._successes = 0
        return self._state

    async def call(self, func, *args, **kwargs):
        if self.state == CircuitState.OPEN:
            raise CircuitBreakerOpenError(f"Circuit is OPEN — service unavailable")

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self):
        if self._state == CircuitState.HALF_OPEN:
            self._successes += 1
            if self._successes >= self.success_threshold:
                self._state = CircuitState.CLOSED
                self._failures = 0
        elif self._state == CircuitState.CLOSED:
            self._failures = 0

    def _on_failure(self):
        self._failures += 1
        self._last_failure_time = time.time()
        if self._failures >= self.failure_threshold:
            self._state = CircuitState.OPEN

# Usage
payment_cb = CircuitBreaker(failure_threshold=5, recovery_timeout=30)

async def call_payment_service(order_id: int) -> dict:
    async def _call():
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.post(
                "http://payment-service/charge",
                json={"order_id": order_id}
            )
            response.raise_for_status()
            return response.json()

    try:
        return await payment_cb.call(_call)
    except CircuitBreakerOpenError:
        # Fallback — queue mein daalo ya user ko retry bolao
        await queue_for_retry(order_id)
        return {"status": "queued", "message": "Payment will be processed shortly"}

# Production mein: tenacity ya circuitbreaker library use karo
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(httpx.HTTPError),
)
async def call_service_with_retry(url: str, data: dict) -> dict:
    async with httpx.AsyncClient(timeout=5) as client:
        response = await client.post(url, json=data)
        response.raise_for_status()
        return response.json()
```

---

### Q3: Saga Pattern — distributed transactions kaise handle karte hain?
**Answer:**
```
PROBLEM: Order service → Payment service → Inventory service
         Payment succeed hua, Inventory fail → kaise rollback karo?

SOLUTION: Saga Pattern
  Choreography: services events publish karte hain → doosri services react karti hain
  Orchestration: central orchestrator batata hai kya karo
```

```python
# CHOREOGRAPHY SAGA (event-driven)
# Har service apna kaam kare aur event publish kare

# Order Service
async def place_order(order_data: dict):
    order = await create_order(order_data)
    await publish_event("order.created", {"order_id": order.id, "amount": order.amount})
    return order

# Payment Service — listens to "order.created"
async def on_order_created(event: dict):
    try:
        payment = await charge_payment(event["order_id"], event["amount"])
        await publish_event("payment.completed", {"order_id": event["order_id"]})
    except PaymentFailed as e:
        await publish_event("payment.failed", {"order_id": event["order_id"], "reason": str(e)})

# Inventory Service — listens to "payment.completed"
async def on_payment_completed(event: dict):
    try:
        await reserve_inventory(event["order_id"])
        await publish_event("inventory.reserved", {"order_id": event["order_id"]})
    except InsufficientStock:
        await publish_event("inventory.failed", {"order_id": event["order_id"]})

# Order Service — listens to failures → compensating transaction
async def on_payment_failed(event: dict):
    await cancel_order(event["order_id"])   # compensating transaction

async def on_inventory_failed(event: dict):
    await refund_payment(event["order_id"])  # compensating transaction
    await cancel_order(event["order_id"])

# ORCHESTRATION SAGA (central coordinator)
class OrderSagaOrchestrator:
    async def execute(self, order_data: dict):
        order_id = None
        payment_id = None
        try:
            # Step 1
            order_id = await order_service.create(order_data)

            # Step 2
            payment_id = await payment_service.charge(order_id, order_data["amount"])

            # Step 3
            await inventory_service.reserve(order_id, order_data["items"])

            # Step 4
            await order_service.confirm(order_id)

        except PaymentError:
            if order_id:
                await order_service.cancel(order_id)  # compensate
            raise

        except InventoryError:
            if payment_id:
                await payment_service.refund(payment_id)  # compensate
            if order_id:
                await order_service.cancel(order_id)    # compensate
            raise
```

---

### Q4: Event-Driven Architecture kaise kaam karta hai?
**Answer:**
```python
# Kafka ya RabbitMQ se event-driven architecture
# aiokafka use karo Python mein

from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
import json

# Producer (event publish karo)
class EventPublisher:
    def __init__(self):
        self.producer = None

    async def start(self):
        self.producer = AIOKafkaProducer(
            bootstrap_servers="kafka:9092",
            value_serializer=lambda v: json.dumps(v).encode()
        )
        await self.producer.start()

    async def publish(self, topic: str, event_type: str, data: dict):
        message = {
            "event_type": event_type,
            "data": data,
            "timestamp": time.time(),
            "service": "order-service",
        }
        await self.producer.send(topic, message)

publisher = EventPublisher()

# Consumer (events sun karo)
async def consume_events():
    consumer = AIOKafkaConsumer(
        "order-events", "payment-events",
        bootstrap_servers="kafka:9092",
        group_id="inventory-service",
        value_deserializer=lambda m: json.loads(m.decode()),
        auto_offset_reset="earliest",
    )
    await consumer.start()

    handlers = {
        "order.created": handle_order_created,
        "payment.completed": handle_payment_completed,
        "payment.failed": handle_payment_failed,
    }

    async for msg in consumer:
        event = msg.value
        handler = handlers.get(event["event_type"])
        if handler:
            try:
                await handler(event["data"])
            except Exception as e:
                logger.error(f"Failed to handle {event['event_type']}: {e}")
                # Dead letter queue mein bhejo
```

---

### Q5: CQRS kya hai? Kab use karo?
**Answer:**
```
CQRS = Command Query Responsibility Segregation
Read operations alag model → Write operations alag model

WHY: Read aur Write ke requirements alag hote hain
  - Read: denormalized, fast, many joins
  - Write: normalized, transactional, validation heavy

WHEN:
  - High read/write ratio (reads >> writes)
  - Complex reporting queries
  - Read replicas use karna ho
```

```python
# Command side (writes) — normalized DB
class CreateOrderCommand(BaseModel):
    user_id: int
    items: list[OrderItem]

class OrderCommandHandler:
    async def handle(self, cmd: CreateOrderCommand, db: AsyncSession):
        order = Order(user_id=cmd.user_id)
        db.add(order)
        await db.flush()
        for item in cmd.items:
            db.add(OrderItem(order_id=order.id, **item.model_dump()))
        await db.commit()
        # Publish event for read model update
        await publisher.publish("orders", "order.created", {"order_id": order.id})
        return order.id

# Query side (reads) — denormalized, optimized for display
class OrderSummaryView(Base):
    """Materialized view — denormalized for fast reads"""
    __tablename__ = "order_summary_view"
    order_id: Mapped[int] = mapped_column(primary_key=True)
    user_name: Mapped[str]          # denormalized from users table
    user_email: Mapped[str]
    total_amount: Mapped[float]
    item_count: Mapped[int]
    status: Mapped[str]
    created_at: Mapped[datetime]

class OrderQueryHandler:
    async def get_user_orders(self, user_id: int, db: AsyncSession):
        return await db.scalars(
            select(OrderSummaryView)
            .where(OrderSummaryView.user_id == user_id)
            .order_by(OrderSummaryView.created_at.desc())
        )

# Read model update karo when order.created event aaye
async def handle_order_created(event_data: dict):
    order_id = event_data["order_id"]
    # Full order fetch karke summary banao
    order = await fetch_full_order(order_id)
    await upsert_order_summary(order)
```

---

### Q6: Inter-service communication — REST vs gRPC vs Message Queue?
**Answer:**
```
REST (HTTP/JSON):
  + Simple, universal, human-readable
  + Easy debugging (curl, Postman)
  - Slower (HTTP overhead, JSON parsing)
  - Tight coupling (sync)
  Use: Public APIs, external clients

gRPC (HTTP/2 + Protobuf):
  + Fast (binary, multiplexed)
  + Type-safe (protobuf schema)
  + Streaming support
  - Complex setup
  - Not human-readable
  Use: Internal microservices, high-performance

Message Queue (Kafka/RabbitMQ):
  + Async — caller wait nahi karta
  + Loose coupling
  + Retry, replay, audit log
  - Eventual consistency (not immediate)
  - Complex debugging
  Use: Event-driven, background processing, cross-service events

RECOMMENDATION:
  Internal sync calls: gRPC
  Internal async events: Kafka/RabbitMQ
  External APIs: REST
```
