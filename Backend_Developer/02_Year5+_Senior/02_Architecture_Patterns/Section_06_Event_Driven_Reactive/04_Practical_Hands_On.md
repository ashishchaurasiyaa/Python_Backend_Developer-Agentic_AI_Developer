# Lecture 4 — Practical Hands-On: Saga & Outbox Patterns

> **Theory file:** [04_Saga_Outbox_Patterns.md](04_Saga_Outbox_Patterns.md)

---

## 🎯 Is Practical Mein Kya Banayenge?

Production-ready Saga + Outbox:

1. ✅ **Choreography saga** for e-commerce
2. ✅ **Orchestration saga** with central coordinator
3. ✅ **Outbox pattern** with atomic writes
4. ✅ **Outbox publisher** background process
5. ✅ **Idempotent consumers** with dedup
6. ✅ **Compensation logic** with retry
7. ✅ **Saga state tracking**
8. ✅ **CDC with Debezium** (alternative to polling)
9. ✅ **Failure injection tests**
10. ✅ **End-to-end e-commerce flow**

By end: aap **production saga + outbox** system bana sakte ho.

---

## 1. Project Structure

```
saga_outbox_demo/
├── docker-compose.yml
├── README.md
│
├── shared/
│   ├── events.py
│   ├── kafka_helpers.py
│   └── idempotency.py
│
├── outbox/
│   ├── models.py
│   ├── publisher.py
│   └── cdc_setup.sql
│
├── choreography/
│   ├── order_service.py
│   ├── inventory_service.py
│   ├── payment_service.py
│   └── shipping_service.py
│
├── orchestration/
│   ├── orchestrator.py
│   ├── saga_state.py
│   └── workflow_definition.py
│
└── tests/
    └── chaos_test.py
```

---

## 2. Setup

```bash
pip install fastapi uvicorn
pip install asyncpg sqlalchemy
pip install aiokafka
pip install debezium-connector  # CDC alternative
```

---

## 3. 📦 Outbox Pattern Implementation

### `outbox/models.py`

```python
"""Outbox table schema"""
from sqlalchemy import Column, BigInteger, String, JSON, DateTime, Index
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime

class Base(DeclarativeBase):
    pass

class OutboxEvent(Base):
    __tablename__ = "outbox"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    event_id = Column(String, unique=True, nullable=False)
    aggregate_type = Column(String, nullable=False)
    aggregate_id = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    published_at = Column(DateTime, nullable=True)
    
    __table_args__ = (
        Index('idx_unpublished', 'published_at', 'id'),
    )
```

### Schema SQL

```sql
CREATE TABLE outbox (
    id BIGSERIAL PRIMARY KEY,
    event_id VARCHAR UNIQUE NOT NULL,
    aggregate_type VARCHAR NOT NULL,
    aggregate_id VARCHAR NOT NULL,
    event_type VARCHAR NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_at TIMESTAMPTZ
);

-- Index for fast polling of unpublished events
CREATE INDEX idx_outbox_unpublished 
    ON outbox (published_at, id) 
    WHERE published_at IS NULL;

-- Processed events (for idempotency)
CREATE TABLE processed_events (
    event_id VARCHAR PRIMARY KEY,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### Atomic Write Pattern

```python
"""
ATOMIC: business state + outbox event in same transaction.
"""
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

async def create_order_with_event(
    session: AsyncSession,
    user_id: int,
    items: list,
) -> str:
    """Create order + outbox event ATOMICALLY"""
    order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"
    
    async with session.begin():
        # 1. Save business state
        order = Order(
            id=order_id,
            user_id=user_id,
            items=items,
            status="CREATED",
            total=sum(i["price"] * i["quantity"] for i in items),
        )
        session.add(order)
        
        # 2. Add event to outbox (SAME transaction!)
        event = OutboxEvent(
            event_id=str(uuid.uuid4()),
            aggregate_type="order",
            aggregate_id=order_id,
            event_type="OrderCreated",
            payload={
                "order_id": order_id,
                "user_id": user_id,
                "items": items,
                "total": order.total,
            }
        )
        session.add(event)
        
        # COMMIT: both succeed or both fail
    
    return order_id
```

### `outbox/publisher.py`

```python
"""
Outbox publisher - polls and publishes events.
"""
import asyncio
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from aiokafka import AIOKafkaProducer
import json

logger = logging.getLogger(__name__)

class OutboxPublisher:
    """
    Polls outbox table, publishes to Kafka.
    Marks as published only after success.
    """
    
    def __init__(self, session_factory, kafka_servers: str):
        self.session_factory = session_factory
        self.producer = AIOKafkaProducer(
            bootstrap_servers=kafka_servers,
            value_serializer=lambda v: json.dumps(v).encode(),
            key_serializer=lambda k: str(k).encode() if k else None,
            acks="all",
            enable_idempotence=True,
            compression_type="gzip",
        )
        self.running = False
    
    async def start(self):
        await self.producer.start()
        self.running = True
    
    async def stop(self):
        self.running = False
        await self.producer.stop()
    
    async def run(self, poll_interval: float = 1.0, batch_size: int = 100):
        """Main loop"""
        while self.running:
            try:
                count = await self._publish_batch(batch_size)
                if count == 0:
                    await asyncio.sleep(poll_interval)
                else:
                    logger.info(f"Published {count} events")
            except Exception as e:
                logger.error(f"Publisher error: {e}")
                await asyncio.sleep(5)
    
    async def _publish_batch(self, batch_size: int) -> int:
        """Publish a batch of unpublished events"""
        async with self.session_factory() as session:
            # Fetch unpublished with row locking (concurrent publishers OK)
            result = await session.execute(
                select(OutboxEvent)
                .where(OutboxEvent.published_at.is_(None))
                .order_by(OutboxEvent.id.asc())
                .limit(batch_size)
                .with_for_update(skip_locked=True)
            )
            events = result.scalars().all()
            
            if not events:
                return 0
            
            # Publish each
            for event in events:
                try:
                    # Topic = event_type or service-specific topic
                    topic = self._topic_for_event(event.event_type)
                    
                    await self.producer.send_and_wait(
                        topic,
                        value={
                            "event_id": event.event_id,
                            "aggregate_id": event.aggregate_id,
                            "data": event.payload,
                            "timestamp": event.created_at.isoformat(),
                        },
                        key=event.aggregate_id,  # Partition by aggregate
                    )
                    
                    # Mark published
                    event.published_at = datetime.utcnow()
                    logger.debug(f"Published {event.event_id}")
                
                except Exception as e:
                    logger.error(f"Failed to publish {event.event_id}: {e}")
                    # Don't update published_at - will retry
            
            await session.commit()
            return len(events)
    
    def _topic_for_event(self, event_type: str) -> str:
        """Map event type to Kafka topic"""
        # E.g., "OrderCreated" → "orders" topic
        # Could be more sophisticated
        return event_type.replace("Created", "").replace("Updated", "").lower()
```

### Cleanup Old Events

```python
"""
Periodic cleanup of published events (free up DB space).
"""
async def cleanup_old_events(session_factory, older_than_hours: int = 24):
    async with session_factory() as session:
        await session.execute(text("""
            DELETE FROM outbox
            WHERE published_at IS NOT NULL
            AND published_at < NOW() - INTERVAL ':hours hours'
        """).bindparams(hours=older_than_hours))
        await session.commit()

# Run nightly:
async def cleanup_scheduler():
    while True:
        await cleanup_old_events(session_factory)
        await asyncio.sleep(3600)  # Every hour
```

---

## 4. 🔁 Idempotent Consumer

### `shared/idempotency.py`

```python
"""Idempotent event handler decorator"""
import functools
from sqlalchemy.ext.asyncio import AsyncSession

def idempotent_handler(handler):
    """
    Decorator: ensures handler is called only ONCE per event_id.
    """
    @functools.wraps(handler)
    async def wrapper(event: dict, session: AsyncSession):
        event_id = event["event_id"]
        
        # Check if already processed
        result = await session.execute(text(
            "SELECT 1 FROM processed_events WHERE event_id = :event_id"
        ), {"event_id": event_id})
        
        if result.scalar():
            print(f"[IDEMPOTENT] Skipping {event_id} (already processed)")
            return
        
        async with session.begin():
            # Process event
            await handler(event, session)
            
            # Mark as processed in SAME transaction
            await session.execute(text(
                "INSERT INTO processed_events (event_id) VALUES (:event_id)"
            ), {"event_id": event_id})
    
    return wrapper

# Usage
@idempotent_handler
async def on_order_created(event, session):
    """Safe even if called multiple times!"""
    order_id = event["data"]["order_id"]
    items = event["data"]["items"]
    
    # Process - this won't run twice
    for item in items:
        await reserve_stock(session, item["sku"], item["quantity"])
```

---

## 5. 🎼 Choreography Saga

### `choreography/order_service.py`

```python
"""
Order Service - emits initial event, reacts to outcomes.
"""
from fastapi import FastAPI
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize Kafka consumer for compensation events
    consumer_task = asyncio.create_task(consume_events())
    yield
    consumer_task.cancel()

app = FastAPI(lifespan=lifespan)

@app.post("/orders")
async def create_order(req: dict):
    """Start the saga"""
    async with session_factory() as session:
        order_id = await create_order_with_event(
            session,
            user_id=req["user_id"],
            items=req["items"],
        )
    
    return {"order_id": order_id, "status": "PROCESSING"}

async def consume_events():
    """React to saga events"""
    consumer = AIOKafkaConsumer(
        "itemsreserved", "paymentcharged", "paymentfailed",
        "itemsreleased", "shippingscheduled",
        bootstrap_servers="kafka:9092",
        group_id="order-service",
        value_deserializer=lambda v: json.loads(v.decode()),
    )
    await consumer.start()
    
    async for msg in consumer:
        event = msg.value
        async with session_factory() as session:
            if event["event_type"] == "PaymentCharged":
                await on_payment_charged(event, session)
            elif event["event_type"] == "PaymentFailed":
                await on_payment_failed(event, session)
            elif event["event_type"] == "ShippingScheduled":
                await on_shipping_scheduled(event, session)
            elif event["event_type"] == "ItemsReleased":
                await on_items_released(event, session)

@idempotent_handler
async def on_payment_charged(event, session):
    """Mark order as paid"""
    order_id = event["data"]["order_id"]
    await session.execute(text("""
        UPDATE orders SET status = 'PAID' WHERE id = :order_id
    """), {"order_id": order_id})

@idempotent_handler
async def on_payment_failed(event, session):
    """Compensation: cancel order"""
    order_id = event["data"]["order_id"]
    
    async with session.begin():
        await session.execute(text("""
            UPDATE orders SET status = 'CANCELLED', failure_reason = :reason
            WHERE id = :order_id
        """), {"order_id": order_id, "reason": event["data"]["reason"]})
        
        # Emit cancellation event (for analytics, etc.)
        session.add(OutboxEvent(
            event_id=str(uuid.uuid4()),
            event_type="OrderCancelled",
            aggregate_type="order",
            aggregate_id=order_id,
            payload={"order_id": order_id, "reason": event["data"]["reason"]},
        ))

@idempotent_handler
async def on_shipping_scheduled(event, session):
    """Mark order as confirmed"""
    order_id = event["data"]["order_id"]
    await session.execute(text("""
        UPDATE orders SET 
            status = 'CONFIRMED', 
            tracking_number = :tracking
        WHERE id = :order_id
    """), {
        "order_id": order_id,
        "tracking": event["data"]["tracking_number"],
    })
```

### `choreography/inventory_service.py`

```python
"""
Inventory Service - reserves on order, releases on failure.
"""
import asyncio
from aiokafka import AIOKafkaConsumer
import json
import uuid

async def consume_events():
    consumer = AIOKafkaConsumer(
        "ordercreated", "paymentfailed",
        bootstrap_servers="kafka:9092",
        group_id="inventory-service",
        value_deserializer=lambda v: json.loads(v.decode()),
    )
    await consumer.start()
    
    async for msg in consumer:
        event = msg.value
        async with session_factory() as session:
            if event["event_type"] == "OrderCreated":
                await on_order_created(event, session)
            elif event["event_type"] == "PaymentFailed":
                await on_payment_failed(event, session)

@idempotent_handler
async def on_order_created(event, session):
    """Reserve inventory for order"""
    order_id = event["data"]["order_id"]
    items = event["data"]["items"]
    
    async with session.begin():
        try:
            # Try to reserve all items atomically
            for item in items:
                result = await session.execute(text("""
                    UPDATE products
                    SET reserved = reserved + :qty
                    WHERE sku = :sku
                      AND (stock - reserved) >= :qty
                    RETURNING sku
                """), {"sku": item["sku"], "qty": item["quantity"]})
                
                if result.scalar() is None:
                    raise InsufficientStockError(item["sku"])
            
            # Success: emit ItemsReserved
            session.add(OutboxEvent(
                event_id=str(uuid.uuid4()),
                event_type="ItemsReserved",
                aggregate_type="order",
                aggregate_id=order_id,
                payload={
                    "order_id": order_id,
                    "items": items,
                    "user_id": event["data"]["user_id"],
                    "total": event["data"]["total"],
                }
            ))
        
        except InsufficientStockError as e:
            # Compensation: emit failure event
            session.add(OutboxEvent(
                event_id=str(uuid.uuid4()),
                event_type="InsufficientStock",
                aggregate_type="order",
                aggregate_id=order_id,
                payload={
                    "order_id": order_id,
                    "reason": str(e),
                }
            ))

@idempotent_handler
async def on_payment_failed(event, session):
    """Compensation: release reserved stock"""
    order_id = event["data"]["order_id"]
    
    async with session.begin():
        # Get order's items
        order = await session.execute(text("""
            SELECT items FROM orders WHERE id = :order_id
        """), {"order_id": order_id})
        items = order.scalar()
        
        # Release each
        for item in items:
            await session.execute(text("""
                UPDATE products
                SET reserved = reserved - :qty
                WHERE sku = :sku
            """), {"sku": item["sku"], "qty": item["quantity"]})
        
        # Emit confirmation
        session.add(OutboxEvent(
            event_id=str(uuid.uuid4()),
            event_type="ItemsReleased",
            aggregate_type="order",
            aggregate_id=order_id,
            payload={"order_id": order_id},
        ))
```

### `choreography/payment_service.py`

```python
"""
Payment Service - charges on reservation.
"""
@idempotent_handler
async def on_items_reserved(event, session):
    """Try to charge payment"""
    order_id = event["data"]["order_id"]
    
    async with session.begin():
        try:
            # Call payment gateway (with idempotency key!)
            txn_id = await charge_payment(
                user_id=event["data"]["user_id"],
                amount=event["data"]["total"],
                idempotency_key=order_id,  # Critical for safe retries
            )
            
            # Success: emit PaymentCharged
            session.add(OutboxEvent(
                event_id=str(uuid.uuid4()),
                event_type="PaymentCharged",
                aggregate_type="order",
                aggregate_id=order_id,
                payload={
                    "order_id": order_id,
                    "transaction_id": txn_id,
                    "amount": event["data"]["total"],
                    "items": event["data"]["items"],
                }
            ))
        
        except PaymentDeclinedError as e:
            # Compensation event
            session.add(OutboxEvent(
                event_id=str(uuid.uuid4()),
                event_type="PaymentFailed",
                aggregate_type="order",
                aggregate_id=order_id,
                payload={
                    "order_id": order_id,
                    "reason": str(e),
                }
            ))
```

---

## 6. 🎭 Orchestration Saga

### `orchestration/orchestrator.py`

```python
"""
Saga orchestrator - central coordinator.
Knows the entire workflow.
"""
from enum import Enum
from dataclasses import dataclass
from typing import Optional
import asyncio

class SagaState(str, Enum):
    STARTED = "started"
    INVENTORY_RESERVED = "inventory_reserved"
    PAYMENT_CHARGED = "payment_charged"
    SHIPPING_SCHEDULED = "shipping_scheduled"
    COMPLETED = "completed"
    
    # Failure states
    FAILED = "failed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"

@dataclass
class OrderSagaState:
    saga_id: str
    order_id: str
    user_id: int
    items: list
    total: float
    state: SagaState
    failed_step: Optional[str] = None
    error: Optional[str] = None

class OrderSagaOrchestrator:
    """
    Central orchestrator for order saga.
    Maintains state, drives workflow, handles compensations.
    """
    
    def __init__(self, kafka_producer, db):
        self.producer = kafka_producer
        self.db = db
    
    async def start_saga(self, order_id: str, user_id: int, items: list, total: float):
        """Start a new order saga"""
        saga_id = f"saga-{uuid.uuid4().hex[:8]}"
        
        # Save saga state
        saga = OrderSagaState(
            saga_id=saga_id,
            order_id=order_id,
            user_id=user_id,
            items=items,
            total=total,
            state=SagaState.STARTED,
        )
        await self._save_saga(saga)
        
        # Step 1: Reserve inventory
        await self._send_command("ReserveInventoryCommand", {
            "saga_id": saga_id,
            "order_id": order_id,
            "items": items,
        })
    
    async def handle_event(self, event: dict):
        """Handle reply events from services"""
        saga_id = event["saga_id"]
        saga = await self._load_saga(saga_id)
        
        event_type = event["event_type"]
        
        try:
            if event_type == "InventoryReserved":
                await self._handle_inventory_reserved(saga)
            elif event_type == "InventoryReservationFailed":
                await self._handle_inventory_failed(saga, event)
            elif event_type == "PaymentCharged":
                await self._handle_payment_charged(saga, event)
            elif event_type == "PaymentFailed":
                await self._handle_payment_failed(saga, event)
            elif event_type == "ShippingScheduled":
                await self._handle_shipping_scheduled(saga, event)
            elif event_type == "InventoryReleased":
                await self._handle_inventory_released(saga)
            elif event_type == "PaymentRefunded":
                await self._handle_payment_refunded(saga)
        
        except Exception as e:
            print(f"Saga {saga_id} error: {e}")
    
    # ─── Forward Path ───
    async def _handle_inventory_reserved(self, saga: OrderSagaState):
        saga.state = SagaState.INVENTORY_RESERVED
        await self._save_saga(saga)
        
        # Next step: charge payment
        await self._send_command("ChargePaymentCommand", {
            "saga_id": saga.saga_id,
            "order_id": saga.order_id,
            "user_id": saga.user_id,
            "amount": saga.total,
        })
    
    async def _handle_payment_charged(self, saga: OrderSagaState, event):
        saga.state = SagaState.PAYMENT_CHARGED
        await self._save_saga(saga)
        
        # Next step: schedule shipping
        await self._send_command("ScheduleShippingCommand", {
            "saga_id": saga.saga_id,
            "order_id": saga.order_id,
            "items": saga.items,
        })
    
    async def _handle_shipping_scheduled(self, saga: OrderSagaState, event):
        saga.state = SagaState.COMPLETED
        await self._save_saga(saga)
        
        # Saga complete!
        print(f"[SAGA] {saga.saga_id} COMPLETED")
    
    # ─── Compensation Path ───
    async def _handle_inventory_failed(self, saga: OrderSagaState, event):
        saga.state = SagaState.FAILED
        saga.failed_step = "inventory"
        saga.error = event.get("reason")
        await self._save_saga(saga)
        # No compensation needed - nothing happened yet
        print(f"[SAGA] {saga.saga_id} FAILED at inventory: {event.get('reason')}")
    
    async def _handle_payment_failed(self, saga: OrderSagaState, event):
        saga.state = SagaState.COMPENSATING
        saga.failed_step = "payment"
        saga.error = event.get("reason")
        await self._save_saga(saga)
        
        # COMPENSATE: release inventory
        await self._send_command("ReleaseInventoryCommand", {
            "saga_id": saga.saga_id,
            "order_id": saga.order_id,
            "items": saga.items,
        })
    
    async def _handle_inventory_released(self, saga: OrderSagaState):
        """Compensation complete"""
        saga.state = SagaState.COMPENSATED
        await self._save_saga(saga)
        print(f"[SAGA] {saga.saga_id} COMPENSATED")
    
    # ─── Utilities ───
    async def _send_command(self, command_type: str, payload: dict):
        """Send command to service"""
        topic = command_type.lower().replace("command", "")
        await self.producer.send_and_wait(
            topic,
            value=json.dumps({
                "command_type": command_type,
                "payload": payload,
            }).encode(),
        )
    
    async def _save_saga(self, saga: OrderSagaState):
        # Persist state to DB
        ...
    
    async def _load_saga(self, saga_id: str) -> OrderSagaState:
        # Load from DB
        ...
```

---

## 7. 🔧 CDC with Debezium (Alternative to Polling)

### Why CDC?

```
Polling-based outbox publisher:
   ✓ Simple to implement
   ✗ Latency (poll interval)
   ✗ DB load

CDC (Change Data Capture):
   ✓ Real-time (reads from WAL)
   ✓ No polling overhead
   ✗ Requires Debezium setup
```

### Debezium Configuration

```yaml
# docker-compose.yml
services:
  debezium:
    image: debezium/connect:2.4
    ports: ["8083:8083"]
    environment:
      BOOTSTRAP_SERVERS: kafka:9092
      GROUP_ID: 1
      CONFIG_STORAGE_TOPIC: connect_configs
      OFFSET_STORAGE_TOPIC: connect_offsets
      STATUS_STORAGE_TOPIC: connect_statuses
    depends_on: [kafka, postgres]
```

### Configure PostgreSQL CDC

```sql
-- Enable logical replication
ALTER SYSTEM SET wal_level = logical;

-- Create replication user
CREATE USER cdc_user WITH REPLICATION PASSWORD 'cdc_pass';
GRANT SELECT ON outbox TO cdc_user;

-- Create publication for outbox table
CREATE PUBLICATION outbox_publication FOR TABLE outbox;
```

### Register Connector

```bash
$ curl -X POST http://localhost:8083/connectors \
    -H "Content-Type: application/json" \
    -d '{
      "name": "outbox-connector",
      "config": {
        "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
        "database.hostname": "postgres",
        "database.user": "cdc_user",
        "database.password": "cdc_pass",
        "database.dbname": "myapp",
        "database.server.name": "myapp",
        "table.include.list": "public.outbox",
        "transforms": "outbox",
        "transforms.outbox.type": "io.debezium.transforms.outbox.EventRouter",
        "transforms.outbox.route.by.field": "event_type",
        "transforms.outbox.route.topic.replacement": "${routedByValue}"
      }
    }'
```

### Now Events Flow Automatically

```
Application writes to outbox table
   ↓
Debezium reads from WAL (real-time!)
   ↓
Routes to Kafka topic by event_type
   ↓
Consumers receive events
```

---

## 8. 🧪 Chaos Testing

### `tests/chaos_test.py`

```python
"""
Test saga under failure conditions.
"""
import pytest
import asyncio
from unittest.mock import patch

@pytest.mark.asyncio
async def test_payment_failure_triggers_compensation():
    """When payment fails, inventory should be released"""
    
    # Create order
    order_id = await create_order(user_id=1, items=[
        {"sku": "SKU-1", "quantity": 2, "price": 100}
    ])
    
    # Mock payment failure
    with patch("payment_service.charge_payment", side_effect=PaymentDeclinedError("Insufficient funds")):
        # Wait for saga to complete (with compensation)
        await asyncio.sleep(5)
    
    # Verify order cancelled
    order = await get_order(order_id)
    assert order["status"] == "CANCELLED"
    
    # Verify inventory released
    product = await get_product("SKU-1")
    assert product["reserved"] == 0

@pytest.mark.asyncio
async def test_outbox_handles_publisher_crash():
    """Publisher crash should not lose events"""
    
    async with session_factory() as session:
        async with session.begin():
            # Write order + outbox event
            order_id = await create_order_with_event(
                session, user_id=1, items=[...]
            )
        
        # Verify event in outbox
        events = await session.execute(
            select(OutboxEvent).where(OutboxEvent.aggregate_id == order_id)
        )
        assert len(events.scalars().all()) > 0
    
    # Kill publisher
    publisher.stop()
    
    # Restart publisher
    await publisher.start()
    
    # Wait for publishing
    await asyncio.sleep(2)
    
    # Verify event published
    consumer = AIOKafkaConsumer("ordercreated")
    await consumer.start()
    
    msgs = []
    async for msg in consumer:
        msgs.append(msg)
        if msg.value["aggregate_id"] == order_id:
            break
    
    assert any(m.value["aggregate_id"] == order_id for m in msgs)

@pytest.mark.asyncio
async def test_duplicate_event_processed_once():
    """Idempotent consumer should skip duplicates"""
    event = {
        "event_id": "test-event-1",
        "event_type": "OrderCreated",
        "data": {...}
    }
    
    # Process twice
    await handle_order_created(event)
    await handle_order_created(event)  # Should be skipped
    
    # Verify only one inventory reservation
    reservations = await get_reservations(order_id=event["data"]["order_id"])
    assert len(reservations) == 1
```

---

## 9. 🎯 End-to-End Demo

### Run Everything

```bash
# 1. Start infrastructure
$ docker-compose up -d

# 2. Run database migrations
$ python migrate.py

# 3. Start services (separate terminals)
$ python -m choreography.order_service       # port 8001
$ python -m choreography.inventory_service   # port 8002
$ python -m choreography.payment_service     # port 8003
$ python -m choreography.shipping_service    # port 8004

# 4. Start outbox publishers (one per service)
$ python -m outbox.publisher --service order
$ python -m outbox.publisher --service inventory
$ python -m outbox.publisher --service payment
$ python -m outbox.publisher --service shipping

# 5. Place an order
$ curl -X POST http://localhost:8001/orders \
    -H "Content-Type: application/json" \
    -d '{
      "user_id": 1,
      "items": [
        {"sku": "SKU-1", "quantity": 2, "price": 500}
      ]
    }'

# Response (instant):
{
  "order_id": "ORD-abc123",
  "status": "PROCESSING"
}

# Watch the saga unfold across services:
# [order-service] Created order ORD-abc123 → OrderCreated event
# [inventory-service] Reserved 2x SKU-1 → ItemsReserved event
# [payment-service] Charged $1000 → PaymentCharged event
# [shipping-service] Scheduled pickup → ShippingScheduled event
# [order-service] Marked as CONFIRMED

# Query order:
$ curl http://localhost:8001/orders/ORD-abc123
{
  "order_id": "ORD-abc123",
  "status": "CONFIRMED",
  "tracking_number": "TRK-xxxx"
}
```

### Test Failure Path

```bash
# Force payment failure
$ curl -X POST http://localhost:8003/admin/fail-next-payment

# Place order
$ curl -X POST http://localhost:8001/orders \
    -d '{"user_id": 1, "items": [{"sku": "SKU-1", "quantity": 1, "price": 999}]}'

# Watch saga:
# [order-service] Created order → OrderCreated
# [inventory-service] Reserved → ItemsReserved
# [payment-service] FAILED → PaymentFailed
# [inventory-service] Released stock → ItemsReleased
# [order-service] Cancelled order

# Query order:
$ curl http://localhost:8001/orders/ORD-xyz789
{
  "order_id": "ORD-xyz789",
  "status": "CANCELLED",
  "failure_reason": "Payment declined"
}

# Verify inventory restored
$ curl http://localhost:8002/inventory/SKU-1
{"sku": "SKU-1", "stock": 100, "reserved": 0}  # Released!
```

---

## 10. 📊 Saga Visualization

### Monitoring Dashboard

```python
"""
Query saga state for monitoring.
"""
@app.get("/saga/{saga_id}/status")
async def get_saga_status(saga_id: str):
    saga = await load_saga(saga_id)
    
    return {
        "saga_id": saga.saga_id,
        "order_id": saga.order_id,
        "state": saga.state,
        "current_step": saga.current_step,
        "steps_completed": saga.completed_steps,
        "compensation_triggered": saga.failed_step is not None,
        "duration_seconds": (datetime.utcnow() - saga.started_at).total_seconds(),
        "events": await get_saga_events(saga_id),
    }

@app.get("/sagas/active")
async def list_active_sagas():
    """All in-progress sagas"""
    return await db.fetch_all(
        "SELECT * FROM saga_state WHERE state NOT IN ('completed', 'compensated', 'failed')"
    )
```

---

## 11. Key Learnings Summary

```
✅ Atomic write: business state + outbox event in same TX
✅ Outbox publisher polls + publishes (or use CDC)
✅ Choreography: services react to events
✅ Orchestration: central coordinator manages flow
✅ All consumers IDEMPOTENT (event_id dedup)
✅ Compensations undo previous steps
✅ Saga state stored for visibility
✅ Debezium CDC for real-time publishing
✅ Chaos testing validates failure paths

🎯 Production saga + outbox stack:
   Atomic DB writes → Debezium → Kafka → 
   Idempotent consumers → Compensations as events
   + Saga state DB for monitoring
```

---

## 🎬 Section Complete!

Congratulations! You've completed **Section 6: Event-Driven & Reactive Systems**!

### Files Created

```
Section_06_Event_Driven_Reactive/
├── 01_Event_Driven_Architecture_Basics.md    (theory)
├── 01_Practical_Hands_On.md                   (practical)
├── 02_Event_Sourcing_CQRS.md                  (theory)
├── 02_Practical_Hands_On.md                   (practical)
├── 03_Reactive_Principles.md                  (theory)
├── 03_Practical_Hands_On.md                   (practical)
├── 04_Saga_Outbox_Patterns.md                 (theory)
└── 04_Practical_Hands_On.md                   (practical)  ← you are here
```

### What You Can Now Build

```
✓ Event-driven architecture with Kafka + schema registry
✓ Event Sourcing + CQRS with multiple read models
✓ Reactive systems (responsive, resilient, elastic, message-driven)
✓ Saga pattern for distributed transactions
✓ Outbox pattern for reliable event publishing
✓ Idempotent consumers with deduplication
✓ Compensation logic for failure recovery
✓ CDC-based event streaming with Debezium
```

---

## 🚀 Next Steps

Continue with:
- **Section 7**: Cloud-Native & Scalable Architecture
- **Section 8**: UI Architecture Patterns
- **Section 9**: Architectural Decision-Making
- **Section 10**: Conclusion & Next Steps

---

## 📚 Try It Yourself

1. Build **Saga visualizer UI** showing real-time state
2. Implement **compensating action retry** with DLQ
3. Set up **Debezium** end-to-end
4. Add **distributed tracing** across saga steps
5. Run **chaos tests** in CI/CD pipeline
