# Lecture 3 — Practical Hands-On: Messaging & Event Brokers

> **Theory file:** [03_Messaging_Event_Brokers.md](03_Messaging_Event_Brokers.md)

---

## 🎯 Is Practical Mein Kya Banayenge?

Production-ready messaging patterns:

1. ✅ **RabbitMQ work queue** with manual ack + DLQ
2. ✅ **Kafka pub/sub** with multiple consumer groups
3. ✅ **Order placed event** flow across services
4. ✅ **Idempotent consumers** with deduplication
5. ✅ **Dead Letter Queue** handling
6. ✅ **Outbox pattern** for reliable publishing
7. ✅ **Schema registry** integration
8. ✅ **Consumer lag monitoring**
9. ✅ **Partitioning** for ordering + scaling
10. ✅ **Hybrid: sync API + async events**

By end: aap **production messaging system** bana sakte ho with proper reliability.

---

## 1. Project Structure

```
messaging_demo/
├── docker-compose.yml
├── README.md
│
├── rabbitmq_demos/
│   ├── basic/
│   │   ├── producer.py
│   │   └── consumer.py
│   ├── work_queue/
│   │   ├── producer.py
│   │   └── consumer.py
│   ├── pub_sub/
│   │   ├── producer.py
│   │   └── consumer.py
│   └── with_dlq/
│       ├── producer.py
│       └── consumer.py
│
├── kafka_demos/
│   ├── basic/
│   │   ├── producer.py
│   │   └── consumer.py
│   ├── multi_consumer/
│   │   ├── inventory_consumer.py
│   │   ├── email_consumer.py
│   │   └── analytics_consumer.py
│   └── partitioning/
│       ├── producer.py
│       └── consumer.py
│
├── patterns/
│   ├── outbox/
│   │   ├── service.py
│   │   └── publisher.py
│   ├── idempotency/
│   │   └── consumer.py
│   └── monitoring/
│       └── lag_monitor.py
│
└── e2e_demo/
    ├── order_service.py        # Publishes events
    ├── inventory_service.py    # Reacts to events
    ├── email_service.py        # Reacts to events
    └── analytics_service.py    # Reacts to events
```

---

## 2. Setup & Dependencies

```bash
pip install aio-pika                # RabbitMQ async client
pip install aiokafka                # Kafka async client
pip install confluent-kafka         # Alternative Kafka client
pip install fastapi uvicorn         # For HTTP endpoints
pip install pydantic
pip install sqlalchemy asyncpg      # For outbox pattern
pip install redis                   # For idempotency dedup
```

---

## 3. 📨 RabbitMQ Basic Work Queue

### Producer (`rabbitmq_demos/work_queue/producer.py`)

```python
"""
RabbitMQ work queue producer - sends tasks to be processed by workers.
"""
import asyncio
import aio_pika
import json
import uuid
from datetime import datetime

async def send_task(message_id: str, payload: dict):
    """Send a durable task to the queue"""
    connection = await aio_pika.connect_robust("amqp://guest:guest@localhost/")
    
    async with connection:
        channel = await connection.channel()
        
        # Declare DURABLE queue (survives broker restart)
        queue = await channel.declare_queue(
            "email_tasks",
            durable=True,
            arguments={
                "x-message-ttl": 3600000,  # Messages expire after 1h
                "x-dead-letter-exchange": "dlx",  # Failed → DLX
            }
        )
        
        # Build message
        message = aio_pika.Message(
            body=json.dumps(payload).encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,  # Survive crash
            message_id=message_id,
            timestamp=datetime.utcnow(),
            content_type="application/json",
        )
        
        await channel.default_exchange.publish(message, routing_key="email_tasks")
        print(f"[PRODUCER] Sent task {message_id}")

async def main():
    tasks = [
        ("email-001", {"to": "user1@ex.com", "subject": "Welcome!"}),
        ("email-002", {"to": "user2@ex.com", "subject": "Hello!"}),
        ("email-003", {"to": "user3@ex.com", "subject": "Hi there!"}),
    ]
    
    for msg_id, payload in tasks:
        await send_task(msg_id, payload)
    
    print(f"\n✓ Sent {len(tasks)} tasks. Producer done immediately!")

if __name__ == "__main__":
    asyncio.run(main())
```

### Consumer with Manual Ack (`rabbitmq_demos/work_queue/consumer.py`)

```python
"""
Consumer with manual ack + retry + DLQ.
"""
import asyncio
import aio_pika
import json
import random

MAX_RETRIES = 3

async def process_email(message: aio_pika.IncomingMessage):
    """Process email with proper error handling"""
    
    # Get retry count from headers
    retries = int(message.headers.get("x-retry-count", 0)) if message.headers else 0
    
    try:
        data = json.loads(message.body.decode())
        print(f"[CONSUMER] Processing {message.message_id} (attempt {retries + 1})")
        
        # Simulate work
        await asyncio.sleep(1)
        
        # Simulate occasional failure
        if random.random() < 0.3:
            raise Exception("Email service temporarily down")
        
        print(f"[CONSUMER] ✓ Sent email to {data['to']}")
        
        # ACK only on success
        await message.ack()
    
    except Exception as e:
        print(f"[CONSUMER] ✗ Error processing {message.message_id}: {e}")
        
        if retries < MAX_RETRIES - 1:
            # Retry: republish with incremented counter
            await message.reject(requeue=False)  # Don't requeue
            
            channel = message.channel
            new_message = aio_pika.Message(
                body=message.body,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                message_id=message.message_id,
                headers={"x-retry-count": retries + 1}
            )
            await channel.default_exchange.publish(new_message, routing_key="email_tasks")
            print(f"[CONSUMER] Requeued (retry {retries + 1}/{MAX_RETRIES})")
        else:
            # Send to DLQ
            await message.reject(requeue=False)  # Will route to DLX
            print(f"[CONSUMER] ✗✗✗ Max retries hit, sending to DLQ")

async def main():
    connection = await aio_pika.connect_robust("amqp://guest:guest@localhost/")
    
    async with connection:
        channel = await connection.channel()
        
        # Process one message at a time (fair dispatch)
        await channel.set_qos(prefetch_count=1)
        
        queue = await channel.declare_queue(
            "email_tasks",
            durable=True,
            arguments={"x-dead-letter-exchange": "dlx"}
        )
        
        await queue.consume(process_email)
        print("[CONSUMER] Waiting for messages...")
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 4. 💀 Dead Letter Queue Setup

### DLQ Configuration (`rabbitmq_demos/with_dlq/setup_dlq.py`)

```python
"""
Set up Dead Letter Queue for failed messages.
"""
import asyncio
import aio_pika

async def setup_dlq():
    connection = await aio_pika.connect_robust("amqp://guest:guest@localhost/")
    
    async with connection:
        channel = await connection.channel()
        
        # Create DLX (Dead Letter Exchange)
        dlx = await channel.declare_exchange("dlx", aio_pika.ExchangeType.FANOUT, durable=True)
        
        # Create DLQ
        dlq = await channel.declare_queue("dead_letters", durable=True)
        await dlq.bind(dlx)
        
        # Create main queue that routes failures to DLX
        main_queue = await channel.declare_queue(
            "email_tasks",
            durable=True,
            arguments={
                "x-dead-letter-exchange": "dlx",
                "x-message-ttl": 3600000,
            }
        )
        
        print("✓ DLQ setup complete")

asyncio.run(setup_dlq())
```

### DLQ Inspector

```python
"""
Inspect failed messages in DLQ.
"""
import asyncio
import aio_pika
import json

async def inspect_dlq():
    connection = await aio_pika.connect_robust("amqp://guest:guest@localhost/")
    
    async with connection:
        channel = await connection.channel()
        dlq = await channel.get_queue("dead_letters")
        
        # Get message count
        info = await dlq.declare()
        print(f"Messages in DLQ: {info.message_count}")
        
        # Peek at messages
        async for message in dlq:
            async with message.process(requeue=True):  # Don't ack - just look
                print(f"\n--- Message {message.message_id} ---")
                print(f"Headers: {message.headers}")
                print(f"Body: {message.body.decode()}")
                print(f"Original queue: {message.headers.get('x-first-death-queue', 'N/A')}")
                
                # Could: replay to main queue, fix, etc.
                break  # Only inspect first

asyncio.run(inspect_dlq())
```

### Replay Failed Messages

```python
"""
Replay DLQ messages back to main queue after fixing root cause.
"""
async def replay_dlq():
    connection = await aio_pika.connect_robust("amqp://guest:guest@localhost/")
    
    async with connection:
        channel = await connection.channel()
        dlq = await channel.get_queue("dead_letters")
        
        replayed = 0
        async for message in dlq:
            async with message.process():
                # Republish to main queue
                await channel.default_exchange.publish(
                    aio_pika.Message(
                        body=message.body,
                        message_id=message.message_id,
                        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                    ),
                    routing_key="email_tasks"
                )
                replayed += 1
        
        print(f"Replayed {replayed} messages")

asyncio.run(replay_dlq())
```

---

## 5. 🚀 Kafka Multi-Consumer Pub/Sub

### Producer

```python
"""
Kafka producer - publishes events that multiple services consume.
"""
import asyncio
from aiokafka import AIOKafkaProducer
import json
import uuid
from datetime import datetime

async def publish_order_event(order_data: dict):
    producer = AIOKafkaProducer(
        bootstrap_servers='localhost:9092',
        value_serializer=lambda v: json.dumps(v).encode(),
        key_serializer=lambda v: str(v).encode(),
        # Reliability settings
        acks="all",            # Wait for all replicas to ack
        enable_idempotence=True,  # Producer-side idempotency
        compression_type="gzip",
    )
    
    await producer.start()
    
    try:
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "order.placed",
            "version": "v1",
            "timestamp": datetime.utcnow().isoformat(),
            "data": order_data,
        }
        
        # Partition by user_id for ordering
        await producer.send_and_wait(
            "orders",
            value=event,
            key=str(order_data["user_id"]),  # Same user → same partition
        )
        print(f"[PRODUCER] Published: {event['event_id']}")
        
    finally:
        await producer.stop()

async def main():
    orders = [
        {"order_id": "ORD-001", "user_id": 123, "amount": 1000},
        {"order_id": "ORD-002", "user_id": 456, "amount": 2000},
        {"order_id": "ORD-003", "user_id": 123, "amount": 500},
    ]
    
    for order in orders:
        await publish_order_event(order)

if __name__ == "__main__":
    asyncio.run(main())
```

### Consumer 1: Inventory Service

```python
"""Inventory consumer - one of MANY independent consumers"""
import asyncio
from aiokafka import AIOKafkaConsumer
import json

async def consume():
    consumer = AIOKafkaConsumer(
        "orders",
        bootstrap_servers='localhost:9092',
        group_id="inventory-service",  # ← Each service uses different group
        value_deserializer=lambda v: json.loads(v.decode()),
        auto_offset_reset="earliest",
        enable_auto_commit=False,  # Manual commit for reliability
    )
    await consumer.start()
    
    try:
        async for msg in consumer:
            event = msg.value
            print(f"[INVENTORY] Processing {event['event_id']}")
            
            try:
                # Reserve stock for order
                order_data = event["data"]
                await reserve_inventory(order_data)
                
                # Commit ONLY after successful processing
                await consumer.commit()
                print(f"[INVENTORY] ✓ Done")
                
            except Exception as e:
                print(f"[INVENTORY] ✗ Error: {e}")
                # Don't commit → will retry on restart
    finally:
        await consumer.stop()

async def reserve_inventory(order_data):
    await asyncio.sleep(0.5)  # Simulate DB work
    print(f"  Reserved stock for order {order_data['order_id']}")

if __name__ == "__main__":
    asyncio.run(consume())
```

### Consumer 2: Email Service

```python
"""Email consumer - INDEPENDENT of inventory consumer"""
import asyncio
from aiokafka import AIOKafkaConsumer
import json

async def consume():
    consumer = AIOKafkaConsumer(
        "orders",
        bootstrap_servers='localhost:9092',
        group_id="email-service",  # ← Different group from inventory!
        value_deserializer=lambda v: json.loads(v.decode()),
        auto_offset_reset="earliest",
    )
    await consumer.start()
    
    try:
        async for msg in consumer:
            event = msg.value
            print(f"[EMAIL] Sending confirmation for {event['data']['order_id']}")
            await asyncio.sleep(0.3)
            print(f"[EMAIL] ✓ Sent")
    finally:
        await consumer.stop()

if __name__ == "__main__":
    asyncio.run(consume())
```

### Run All Three Consumers Independently

```bash
# Terminal 1: Start Kafka
$ docker-compose up -d kafka

# Terminal 2: Start inventory consumer
$ python inventory_consumer.py
[INVENTORY] Waiting for messages...

# Terminal 3: Start email consumer
$ python email_consumer.py
[EMAIL] Waiting for messages...

# Terminal 4: Start analytics consumer
$ python analytics_consumer.py
[ANALYTICS] Waiting for messages...

# Terminal 5: Produce
$ python producer.py
[PRODUCER] Published: evt-abc123

# All three consumers receive the SAME event!
```

---

## 6. 🔄 Idempotent Consumer Pattern

### `patterns/idempotency/consumer.py`

```python
"""
Idempotent consumer - safe against duplicate messages.
Same message processed N times → same result as processing once.
"""
import asyncio
import redis.asyncio as redis
from aiokafka import AIOKafkaConsumer
import json

class IdempotentConsumer:
    """
    Tracks processed event IDs in Redis.
    Skips already-processed messages.
    """
    
    def __init__(self, redis_url: str = "redis://localhost"):
        self.redis = redis.from_url(redis_url)
        self.dedup_ttl = 86400 * 7  # Remember for 7 days
    
    async def is_processed(self, event_id: str) -> bool:
        return await self.redis.exists(f"processed:{event_id}")
    
    async def mark_processed(self, event_id: str):
        await self.redis.setex(
            f"processed:{event_id}",
            self.dedup_ttl,
            "1"
        )
    
    async def handle_event(self, event: dict, handler):
        event_id = event["event_id"]
        
        # Check if already processed
        if await self.is_processed(event_id):
            print(f"[IDEMP] Already processed: {event_id}, skipping")
            return
        
        # Process
        try:
            await handler(event)
            
            # Mark as processed
            await self.mark_processed(event_id)
            print(f"[IDEMP] Processed and marked: {event_id}")
            
        except Exception as e:
            # Don't mark on failure → can retry
            print(f"[IDEMP] Failed: {event_id}, can retry")
            raise

async def process_order(event):
    """Actual business logic"""
    print(f"  Processing order: {event['data']['order_id']}")
    await asyncio.sleep(0.5)

async def main():
    idemp = IdempotentConsumer()
    
    consumer = AIOKafkaConsumer(
        "orders",
        bootstrap_servers='localhost:9092',
        group_id="inventory-service",
        value_deserializer=lambda v: json.loads(v.decode()),
    )
    await consumer.start()
    
    try:
        async for msg in consumer:
            await idemp.handle_event(msg.value, process_order)
    finally:
        await consumer.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

### Test Idempotency

```bash
# Publish same event twice
$ python producer.py  # Sends event-abc
$ python producer.py  # Sends event-abc (same ID, simulating retry)

# Consumer output:
[IDEMP] Processed and marked: event-abc
[IDEMP] Already processed: event-abc, skipping  ← Safe!
```

---

## 7. 📤 Outbox Pattern for Reliable Publishing

### `patterns/outbox/service.py`

```python
"""
Outbox pattern: atomic DB write + event guarantee.

Problem: What if you save to DB but crash before publishing to Kafka?
Solution: Save event to outbox table in SAME transaction.
         Separate publisher polls outbox.
"""
from sqlalchemy import Column, Integer, String, JSON, DateTime, Boolean
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import uuid

Base = declarative_base()

class Order(Base):
    __tablename__ = "orders"
    id = Column(String, primary_key=True)
    user_id = Column(Integer)
    amount = Column(Integer)
    status = Column(String)

class OutboxEvent(Base):
    __tablename__ = "outbox"
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String, unique=True)
    event_type = Column(String)
    aggregate_id = Column(String)
    payload = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    published_at = Column(DateTime, nullable=True)

engine = create_async_engine("postgresql+asyncpg://user:pass@localhost/orders_db")
SessionFactory = async_sessionmaker(engine)

async def create_order_with_outbox(user_id: int, amount: int) -> Order:
    """Atomic: order + outbox event in same transaction"""
    order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"
    
    async with SessionFactory() as session:
        async with session.begin():
            # 1. Create order
            order = Order(
                id=order_id,
                user_id=user_id,
                amount=amount,
                status="CREATED"
            )
            session.add(order)
            
            # 2. Create outbox event in SAME transaction
            event = OutboxEvent(
                event_id=str(uuid.uuid4()),
                event_type="order.placed",
                aggregate_id=order_id,
                payload={
                    "order_id": order_id,
                    "user_id": user_id,
                    "amount": amount,
                }
            )
            session.add(event)
            
            # Commit BOTH atomically
            # If anything fails: BOTH roll back
    
    print(f"✓ Order {order_id} created + outbox event saved atomically")
    return order
```

### `patterns/outbox/publisher.py`

```python
"""
Outbox publisher: polls outbox table, publishes to Kafka.
Runs as separate background process.
"""
import asyncio
from sqlalchemy import select
from aiokafka import AIOKafkaProducer
import json

async def publish_outbox_events():
    """Run forever - polls outbox and publishes"""
    producer = AIOKafkaProducer(
        bootstrap_servers='localhost:9092',
        value_serializer=lambda v: json.dumps(v).encode(),
    )
    await producer.start()
    
    try:
        while True:
            async with SessionFactory() as session:
                # Get unpublished events (with lock to prevent duplicates)
                result = await session.execute(
                    select(OutboxEvent)
                    .where(OutboxEvent.published_at.is_(None))
                    .order_by(OutboxEvent.id)
                    .limit(100)
                    .with_for_update(skip_locked=True)
                )
                events = result.scalars().all()
                
                if not events:
                    await asyncio.sleep(1)
                    continue
                
                for event in events:
                    try:
                        await producer.send_and_wait(
                            event.event_type,
                            value={
                                "event_id": event.event_id,
                                "event_type": event.event_type,
                                "data": event.payload,
                            },
                            key=event.aggregate_id.encode(),
                        )
                        
                        # Mark as published
                        event.published_at = datetime.utcnow()
                        print(f"✓ Published {event.event_id}")
                    
                    except Exception as e:
                        print(f"✗ Failed to publish {event.event_id}: {e}")
                
                await session.commit()
    
    finally:
        await producer.stop()

if __name__ == "__main__":
    asyncio.run(publish_outbox_events())
```

### Why This Pattern Matters

```
Without outbox:
   1. Save order to DB ✓
   2. Publish to Kafka ✗ (crash here)
   → Order exists but no event → inconsistent state!

With outbox:
   1. Save order + outbox event ATOMICALLY ✓
   2. Publisher polls outbox separately
   3. Always eventually publishes
   → Guaranteed consistency
```

---

## 8. 🔍 Consumer Lag Monitoring

### `patterns/monitoring/lag_monitor.py`

```python
"""
Monitor Kafka consumer lag - critical metric for ops.
"""
import asyncio
from aiokafka.admin import AIOKafkaAdminClient
from aiokafka import AIOKafkaConsumer
from kafka.admin import ConsumerGroupDescription

async def get_consumer_lag(group_id: str, topic: str):
    """Calculate lag for a consumer group on a topic"""
    
    # Get consumer's current offsets
    consumer = AIOKafkaConsumer(
        bootstrap_servers='localhost:9092',
        group_id=group_id,
    )
    await consumer.start()
    
    try:
        # Get end offsets (latest position)
        partitions = consumer.partitions_for_topic(topic)
        topic_partitions = [TopicPartition(topic, p) for p in partitions]
        
        end_offsets = await consumer.end_offsets(topic_partitions)
        
        # Get committed offsets (consumer position)
        committed = {}
        for tp in topic_partitions:
            committed[tp] = await consumer.committed(tp) or 0
        
        # Calculate lag
        total_lag = 0
        for tp in topic_partitions:
            lag = end_offsets[tp] - committed[tp]
            print(f"Partition {tp.partition}: lag = {lag}")
            total_lag += lag
        
        print(f"\nTotal lag for {group_id}: {total_lag}")
        
        return total_lag
    finally:
        await consumer.stop()

async def monitor_continuously():
    while True:
        lag = await get_consumer_lag("inventory-service", "orders")
        
        if lag > 1000:
            print(f"⚠️  ALERT: Consumer lag exceeded threshold!")
            # In prod: send to PagerDuty, Slack, etc.
        
        await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(monitor_continuously())
```

### Prometheus Exporter

```python
"""Export Kafka lag to Prometheus"""
from prometheus_client import Gauge, start_http_server

LAG_GAUGE = Gauge(
    'kafka_consumer_lag',
    'Number of messages behind',
    ['group', 'topic', 'partition']
)

async def export_metrics():
    while True:
        lag = await get_consumer_lag("inventory-service", "orders")
        LAG_GAUGE.labels(
            group="inventory-service",
            topic="orders",
            partition="0"
        ).set(lag)
        await asyncio.sleep(15)

# Start Prometheus HTTP server
start_http_server(9091)
asyncio.run(export_metrics())
```

---

## 9. 🌐 End-to-End Demo: Order Placed Event

### Order Service

```python
# e2e_demo/order_service.py
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from aiokafka import AIOKafkaProducer
import json
import uuid
from datetime import datetime
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.producer = AIOKafkaProducer(
        bootstrap_servers='localhost:9092',
        value_serializer=lambda v: json.dumps(v).encode(),
    )
    await app.state.producer.start()
    yield
    await app.state.producer.stop()

app = FastAPI(lifespan=lifespan)

class CreateOrderRequest(BaseModel):
    user_id: int
    sku: str
    quantity: int
    amount: float

@app.post("/orders", status_code=201)
async def create_order(req: CreateOrderRequest, background: BackgroundTasks):
    """Place order: sync save + async event"""
    order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"
    
    # 1. SYNC: Save order
    # ... save to DB ...
    print(f"[ORDER] Saved order {order_id}")
    
    # 2. ASYNC: Publish event
    event = {
        "event_id": str(uuid.uuid4()),
        "event_type": "order.placed",
        "timestamp": datetime.utcnow().isoformat(),
        "data": {
            "order_id": order_id,
            "user_id": req.user_id,
            "sku": req.sku,
            "quantity": req.quantity,
            "amount": req.amount,
        }
    }
    
    background.add_task(
        publish_event,
        app.state.producer,
        "orders",
        event
    )
    
    return {"order_id": order_id, "status": "CONFIRMED"}

async def publish_event(producer, topic, event):
    await producer.send_and_wait(topic, value=event, key=str(event["data"]["user_id"]).encode())
    print(f"[ORDER] Published event {event['event_id']}")
```

### Inventory Service (Consumer)

```python
# e2e_demo/inventory_service.py
import asyncio
from aiokafka import AIOKafkaConsumer
import json

async def consume():
    consumer = AIOKafkaConsumer(
        "orders",
        bootstrap_servers='localhost:9092',
        group_id="inventory-service",
        value_deserializer=lambda v: json.loads(v.decode()),
    )
    await consumer.start()
    
    try:
        async for msg in consumer:
            event = msg.value
            data = event["data"]
            print(f"[INVENTORY] Reserve {data['quantity']} of {data['sku']}")
            await asyncio.sleep(0.5)
            print(f"[INVENTORY] ✓ Reserved")
    finally:
        await consumer.stop()

asyncio.run(consume())
```

### Email Service (Consumer)

```python
# e2e_demo/email_service.py
import asyncio
from aiokafka import AIOKafkaConsumer
import json

async def consume():
    consumer = AIOKafkaConsumer(
        "orders",
        bootstrap_servers='localhost:9092',
        group_id="email-service",  # Different group from inventory!
        value_deserializer=lambda v: json.loads(v.decode()),
    )
    await consumer.start()
    
    try:
        async for msg in consumer:
            event = msg.value
            data = event["data"]
            print(f"[EMAIL] Send confirmation to user {data['user_id']}")
            await asyncio.sleep(0.3)
            print(f"[EMAIL] ✓ Sent")
    finally:
        await consumer.stop()

asyncio.run(consume())
```

### Run It

```bash
# Terminal 1: Order service (HTTP API)
$ uvicorn order_service:app --port 8000

# Terminal 2: Inventory consumer
$ python inventory_service.py
[INVENTORY] Waiting for events...

# Terminal 3: Email consumer
$ python email_service.py
[EMAIL] Waiting for events...

# Terminal 4: Analytics consumer
$ python analytics_service.py
[ANALYTICS] Waiting for events...

# Terminal 5: Place order
$ curl -X POST http://localhost:8000/orders \
    -H "Content-Type: application/json" \
    -d '{"user_id": 123, "sku": "iPhone-15", "quantity": 1, "amount": 79999}'

Response (instant!): {"order_id": "ORD-ABC123", "status": "CONFIRMED"}

# All 3 consumers IN PARALLEL:
[INVENTORY] Reserve 1 of iPhone-15
[EMAIL] Send confirmation to user 123
[ANALYTICS] Log order event
```

---

## 10. 🐳 Docker Compose Setup

```yaml
version: '3.8'

services:
  # ───── RabbitMQ ─────
  rabbitmq:
    image: rabbitmq:3-management-alpine
    ports:
      - "5672:5672"
      - "15672:15672"  # Management UI: http://localhost:15672 (guest/guest)
    environment:
      RABBITMQ_DEFAULT_USER: guest
      RABBITMQ_DEFAULT_PASS: guest
  
  # ───── Kafka ─────
  zookeeper:
    image: confluentinc/cp-zookeeper:7.5.0
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
  
  kafka:
    image: confluentinc/cp-kafka:7.5.0
    depends_on: [zookeeper]
    ports:
      - "9092:9092"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_AUTO_CREATE_TOPICS_ENABLE: "true"
  
  # ───── Kafka UI ─────
  kafka_ui:
    image: provectuslabs/kafka-ui:latest
    ports: ["8080:8080"]
    environment:
      KAFKA_CLUSTERS_0_NAME: local
      KAFKA_CLUSTERS_0_BOOTSTRAPSERVERS: kafka:9092
    depends_on: [kafka]
  
  # ───── Schema Registry ─────
  schema_registry:
    image: confluentinc/cp-schema-registry:7.5.0
    depends_on: [kafka]
    ports: ["8081:8081"]
    environment:
      SCHEMA_REGISTRY_HOST_NAME: schema-registry
      SCHEMA_REGISTRY_KAFKASTORE_BOOTSTRAP_SERVERS: kafka:9092
  
  # ───── Redis (for idempotency) ─────
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
```

---

## 11. 📊 Schema Registry Integration

### Producer with Avro Schema

```python
"""Producer with schema validation"""
from confluent_kafka import Producer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer
from confluent_kafka.serialization import StringSerializer, SerializationContext, MessageField

# Schema definition
order_schema = """
{
    "namespace": "com.example",
    "name": "OrderPlaced",
    "type": "record",
    "fields": [
        {"name": "order_id", "type": "string"},
        {"name": "user_id", "type": "int"},
        {"name": "amount", "type": "double"},
        {"name": "timestamp", "type": "string"}
    ]
}
"""

# Register schema
schema_registry_client = SchemaRegistryClient({'url': 'http://localhost:8081'})

avro_serializer = AvroSerializer(
    schema_registry_client,
    order_schema,
)

producer = Producer({'bootstrap.servers': 'localhost:9092'})

# Publish
order = {
    "order_id": "ORD-001",
    "user_id": 123,
    "amount": 999.99,
    "timestamp": "2026-05-26T10:00:00Z"
}

producer.produce(
    topic="orders",
    value=avro_serializer(order, SerializationContext("orders", MessageField.VALUE)),
)
producer.flush()
```

---

## 12. Key Learnings Summary

```
✅ RabbitMQ for tasks: manual ack, retries, DLQ
✅ Kafka for events: pub/sub, multiple consumer groups, replay
✅ Outbox pattern: atomic DB + event guarantee
✅ Idempotent consumers: safe against duplicates
✅ Partitioning by key: ordering + scaling
✅ Schema registry: evolve events safely
✅ Monitor consumer lag: critical ops metric
✅ DLQ for poison messages

🎯 Production pattern:
   Service publishes events to Kafka (via outbox)
   Multiple consumers react independently  
   Each idempotent and resilient
   Monitored end-to-end
```

---

## 🎬 What's Next?

In **Lecture 4**, we'll cover **Resilience Patterns** — retry, circuit breaker, timeout, bulkhead — the building blocks of fault-tolerant systems.

> **Next lecture:** [04_Resilience_Patterns.md](04_Resilience_Patterns.md)

---

## 📚 Try It Yourself

1. Implement **fanout exchange** in RabbitMQ for pub/sub
2. Add **schema evolution** with backward compatibility
3. Build a **DLQ replay UI** for ops team
4. Set up **Kafka Streams** for real-time aggregation
5. Implement **Saga pattern** with Kafka events
