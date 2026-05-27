# Lecture 1 — Practical Hands-On: Event-Driven Architecture Basics

> **Theory file:** [01_Event_Driven_Architecture_Basics.md](01_Event_Driven_Architecture_Basics.md)

---

## 🎯 Is Practical Mein Kya Banayenge?

Production-ready EDA patterns:

1. ✅ **Event schema** with versioning + validation
2. ✅ **Pub/Sub** with Kafka + multiple consumers
3. ✅ **Event broker** abstraction layer
4. ✅ **In-process event bus** for monoliths
5. ✅ **Schema registry** integration
6. ✅ **Event log** with replay capability
7. ✅ **Distributed tracing** for events
8. ✅ **Dead Letter Queue** for failures
9. ✅ **CloudEvents** standard
10. ✅ **End-to-end** order placement example

By end: aap **production event-driven system** bana sakte ho.

---

## 1. Project Structure

```
eda_demo/
├── docker-compose.yml
├── README.md
│
├── events/
│   ├── schemas.py          # Pydantic event schemas
│   ├── envelope.py         # Event envelope (CloudEvents)
│   └── registry.py         # Schema registry
│
├── broker/
│   ├── kafka_publisher.py
│   ├── kafka_consumer.py
│   ├── inprocess_bus.py
│   └── abstraction.py      # Common interface
│
├── services/
│   ├── order_service.py    # Producer
│   ├── inventory_consumer.py
│   ├── email_consumer.py
│   ├── analytics_consumer.py
│   └── loyalty_consumer.py
│
├── observability/
│   ├── tracing.py
│   └── event_audit.py
│
└── tests/
    └── test_events.py
```

---

## 2. Setup

```bash
pip install fastapi uvicorn
pip install aiokafka                # Kafka async client
pip install pydantic
pip install cloudevents             # CloudEvents standard
pip install confluent-kafka         # Schema registry support
pip install opentelemetry-distro
pip install opentelemetry-exporter-jaeger
```

---

## 3. 📜 Event Schemas with Pydantic

### `events/schemas.py`

```python
"""
Event schemas - the contracts of our event-driven system.
"""
from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime
from enum import Enum
import uuid

# ─────────────────────────────────────────────────────────────
# BASE EVENT (all events extend this)
# ─────────────────────────────────────────────────────────────
class BaseEvent(BaseModel):
    """Common metadata for all events"""
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str
    version: str = "v1"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str  # Service that emitted
    correlation_id: Optional[str] = None  # For tracing
    
    class Config:
        # Immutable!
        frozen = True

# ─────────────────────────────────────────────────────────────
# DOMAIN EVENTS
# ─────────────────────────────────────────────────────────────
class OrderItem(BaseModel):
    sku: str
    quantity: int
    price: float

class OrderPlacedV1(BaseEvent):
    """OrderPlaced event - v1"""
    event_type: Literal["OrderPlaced"] = "OrderPlaced"
    version: Literal["v1"] = "v1"
    
    # Event data
    order_id: str
    user_id: int
    items: list[OrderItem]
    total: float
    currency: str = "INR"

class OrderPlacedV2(BaseEvent):
    """OrderPlaced event - v2 (added shipping info)"""
    event_type: Literal["OrderPlaced"] = "OrderPlaced"
    version: Literal["v2"] = "v2"
    
    order_id: str
    user_id: int
    items: list[OrderItem]
    total: float
    currency: str = "INR"
    shipping_address: Optional[dict] = None  # NEW in v2
    expedited: bool = False                    # NEW in v2

class PaymentReceivedEvent(BaseEvent):
    event_type: Literal["PaymentReceived"] = "PaymentReceived"
    
    payment_id: str
    order_id: str
    amount: float
    method: str  # "card", "upi", "wallet"

class OrderShippedEvent(BaseEvent):
    event_type: Literal["OrderShipped"] = "OrderShipped"
    
    order_id: str
    tracking_number: str
    carrier: str
    estimated_delivery: datetime

# ─────────────────────────────────────────────────────────────
# USAGE
# ─────────────────────────────────────────────────────────────
event = OrderPlacedV1(
    source="order-service",
    order_id="ORD-001",
    user_id=123,
    items=[OrderItem(sku="SKU-1", quantity=2, price=499.0)],
    total=998.0,
)

print(event.model_dump_json(indent=2))
```

### Example Event JSON

```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "event_type": "OrderPlaced",
  "version": "v1",
  "timestamp": "2026-05-26T10:00:00",
  "source": "order-service",
  "correlation_id": null,
  "order_id": "ORD-001",
  "user_id": 123,
  "items": [
    {"sku": "SKU-1", "quantity": 2, "price": 499.0}
  ],
  "total": 998.0,
  "currency": "INR"
}
```

---

## 4. ☁️ CloudEvents Standard

### Why CloudEvents?

```
Industry standard for event metadata.
Specifications by CNCF (Cloud Native Computing Foundation).
Works across:
   ✓ Cloud providers (AWS, Azure, GCP)
   ✓ Event brokers (Kafka, RabbitMQ)
   ✓ Programming languages

Adopted by:
   ✓ Knative
   ✓ Argo Events
   ✓ AWS EventBridge
   ✓ Azure Event Grid
```

### `events/envelope.py`

```python
"""
CloudEvents envelope.
"""
from cloudevents.http import CloudEvent
from cloudevents.conversion import to_json, from_json
from typing import Any
import uuid
from datetime import datetime

def create_cloudevent(
    event_type: str,
    source: str,
    data: dict,
    subject: str = None,
) -> CloudEvent:
    """Create a CloudEvent following the spec"""
    attributes = {
        "type": event_type,           # e.g., "com.example.order.placed"
        "source": source,              # e.g., "order-service"
        "id": str(uuid.uuid4()),
        "time": datetime.utcnow().isoformat() + "Z",
        "specversion": "1.0",
        "datacontenttype": "application/json",
    }
    
    if subject:
        attributes["subject"] = subject  # e.g., "order-123"
    
    return CloudEvent(attributes, data)

# Usage
event = create_cloudevent(
    event_type="com.example.order.placed",
    source="order-service",
    data={"order_id": "ORD-001", "user_id": 123},
    subject="ORD-001",
)

# Serialize
event_json = to_json(event).decode()
print(event_json)
# {
#   "type": "com.example.order.placed",
#   "source": "order-service",
#   "id": "...",
#   "time": "2026-05-26T10:00:00Z",
#   "specversion": "1.0",
#   "datacontenttype": "application/json",
#   "subject": "ORD-001",
#   "data": {"order_id": "ORD-001", "user_id": 123}
# }

# Deserialize on consumer side
received_event = from_json(event_json.encode())
print(received_event["type"], received_event.data)
```

---

## 5. 📤 Kafka Producer

### `broker/kafka_publisher.py`

```python
"""
Kafka event publisher with reliability features.
"""
import asyncio
import json
from aiokafka import AIOKafkaProducer
from typing import Optional
from events.schemas import BaseEvent

class EventPublisher:
    """
    Reliable Kafka event publisher.
    
    Features:
    - Idempotent producer (no duplicates)
    - All-replicas ACK (durability)
    - Compression (efficiency)
    - Batching (throughput)
    """
    
    def __init__(self, bootstrap_servers: str = "localhost:9092"):
        self.producer: Optional[AIOKafkaProducer] = None
        self.bootstrap_servers = bootstrap_servers
    
    async def start(self):
        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: v.encode() if isinstance(v, str) else json.dumps(v).encode(),
            key_serializer=lambda k: k.encode() if k else None,
            
            # Reliability
            acks="all",                  # Wait for all replicas
            enable_idempotence=True,      # No duplicate producers
            
            # Performance
            compression_type="gzip",
            linger_ms=10,                 # Batch up to 10ms
            
            # Retries
            request_timeout_ms=30000,
            retry_backoff_ms=100,
        )
        await self.producer.start()
        print("[Publisher] Started")
    
    async def stop(self):
        if self.producer:
            await self.producer.stop()
    
    async def publish(
        self,
        topic: str,
        event: BaseEvent,
        key: Optional[str] = None,
    ):
        """Publish event to topic"""
        if not self.producer:
            raise RuntimeError("Publisher not started")
        
        # Use event_id as default key (for partitioning)
        # Or use aggregate ID for ordering by aggregate
        key = key or event.event_id
        
        # Serialize event
        value = event.model_dump_json()
        
        # Add tracing headers
        headers = [
            ("event_type", event.event_type.encode()),
            ("version", event.version.encode()),
            ("source", event.source.encode()),
        ]
        if event.correlation_id:
            headers.append(("correlation_id", event.correlation_id.encode()))
        
        # Send and wait for ack
        metadata = await self.producer.send_and_wait(
            topic,
            value=value,
            key=key,
            headers=headers,
        )
        
        print(f"[Publisher] {event.event_type} → {topic} (partition={metadata.partition}, offset={metadata.offset})")
        return metadata

# ─────────────────────────────────────────────────────────────
# USAGE
# ─────────────────────────────────────────────────────────────
async def example():
    from events.schemas import OrderPlacedV1, OrderItem
    
    publisher = EventPublisher()
    await publisher.start()
    
    event = OrderPlacedV1(
        source="order-service",
        order_id="ORD-001",
        user_id=123,
        items=[OrderItem(sku="SKU-1", quantity=2, price=499.0)],
        total=998.0,
    )
    
    # Use user_id as key for partition ordering
    await publisher.publish(
        topic="orders",
        event=event,
        key=str(event.user_id),
    )
    
    await publisher.stop()

asyncio.run(example())
```

---

## 6. 📥 Kafka Consumer

### `broker/kafka_consumer.py`

```python
"""
Kafka consumer with offset management + DLQ.
"""
import asyncio
import json
import logging
from aiokafka import AIOKafkaConsumer
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)

class EventConsumer:
    """
    Reliable Kafka consumer.
    
    Features:
    - Manual commit (only after success)
    - DLQ for failed messages
    - Concurrent processing
    - Graceful shutdown
    """
    
    def __init__(
        self,
        topic: str,
        group_id: str,
        handler: Callable[[dict], Awaitable[None]],
        bootstrap_servers: str = "localhost:9092",
        max_retries: int = 3,
    ):
        self.topic = topic
        self.group_id = group_id
        self.handler = handler
        self.bootstrap_servers = bootstrap_servers
        self.max_retries = max_retries
        self.consumer: AIOKafkaConsumer = None
        self.dlq_producer = None
        self.running = False
    
    async def start(self):
        self.consumer = AIOKafkaConsumer(
            self.topic,
            bootstrap_servers=self.bootstrap_servers,
            group_id=self.group_id,
            value_deserializer=lambda v: json.loads(v.decode()),
            auto_offset_reset="earliest",
            enable_auto_commit=False,  # Manual commits!
            max_poll_records=10,
        )
        await self.consumer.start()
        
        # DLQ producer
        from aiokafka import AIOKafkaProducer
        self.dlq_producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode(),
        )
        await self.dlq_producer.start()
        
        self.running = True
        print(f"[Consumer:{self.group_id}] Started on {self.topic}")
    
    async def stop(self):
        self.running = False
        if self.consumer:
            await self.consumer.stop()
        if self.dlq_producer:
            await self.dlq_producer.stop()
    
    async def run(self):
        """Main consumption loop"""
        try:
            async for msg in self.consumer:
                event = msg.value
                
                # Extract trace info from headers
                trace = {h[0]: h[1].decode() for h in msg.headers}
                correlation_id = trace.get("correlation_id")
                
                try:
                    print(f"[Consumer:{self.group_id}] Processing {event.get('event_type')}")
                    
                    # Process with retries
                    for attempt in range(self.max_retries):
                        try:
                            await self.handler(event)
                            break
                        except Exception as e:
                            if attempt == self.max_retries - 1:
                                raise
                            logger.warning(f"Attempt {attempt + 1} failed: {e}")
                            await asyncio.sleep(2 ** attempt)
                    
                    # Commit ONLY after successful processing
                    await self.consumer.commit()
                
                except Exception as e:
                    logger.error(f"All retries failed: {e}")
                    # Send to DLQ
                    await self._send_to_dlq(event, str(e))
                    # Still commit to avoid blocking
                    await self.consumer.commit()
        
        except Exception as e:
            logger.error(f"Consumer error: {e}")
    
    async def _send_to_dlq(self, event: dict, error: str):
        """Send failed message to dead letter queue"""
        dlq_event = {
            "original_event": event,
            "error": error,
            "failed_at": datetime.utcnow().isoformat(),
            "consumer_group": self.group_id,
        }
        await self.dlq_producer.send_and_wait(
            f"{self.topic}.dlq",
            value=dlq_event,
        )
        logger.error(f"Sent to DLQ: {event.get('event_id')}")

# ─────────────────────────────────────────────────────────────
# USAGE
# ─────────────────────────────────────────────────────────────
async def handle_order(event: dict):
    """Process an order event"""
    print(f"  Order ID: {event['order_id']}")
    print(f"  User: {event['user_id']}")
    print(f"  Total: {event['total']}")

consumer = EventConsumer(
    topic="orders",
    group_id="inventory-service",
    handler=handle_order,
)

await consumer.start()
await consumer.run()  # Runs forever
```

---

## 7. 🔀 Pub/Sub with Multiple Consumer Groups

### Demonstrating Fanout

```python
"""
ONE event → MULTIPLE consumer groups → each gets COPY
"""
import asyncio

# Inventory consumer group
async def inventory_handler(event):
    print(f"[INVENTORY] Reserve stock for {event['order_id']}")

# Email consumer group
async def email_handler(event):
    print(f"[EMAIL] Send confirmation for {event['order_id']}")

# Analytics consumer group
async def analytics_handler(event):
    print(f"[ANALYTICS] Log order {event['order_id']}")

# Loyalty consumer group
async def loyalty_handler(event):
    print(f"[LOYALTY] Award points for {event['order_id']}")

async def main():
    # Create consumers with DIFFERENT group_ids
    # → each gets independent copy of events!
    consumers = [
        EventConsumer("orders", "inventory-service", inventory_handler),
        EventConsumer("orders", "email-service", email_handler),
        EventConsumer("orders", "analytics-service", analytics_handler),
        EventConsumer("orders", "loyalty-service", loyalty_handler),
    ]
    
    # Start all
    for c in consumers:
        await c.start()
    
    # Run all concurrently
    await asyncio.gather(*[c.run() for c in consumers])

asyncio.run(main())
```

### Why Different Group IDs?

```
Same group_id (e.g., "service-x"):
   - Kafka load-balances messages across consumers in group
   - Each message → ONE consumer in group
   - Used for scaling a single service horizontally

Different group_ids:
   - Each group reads ALL messages independently
   - Used for FANOUT (multiple services reacting)
```

---

## 8. 🏠 In-Process Event Bus (for Monoliths)

### `broker/inprocess_bus.py`

```python
"""
In-process event bus for modular monoliths.
Same interface as Kafka publisher → easy migration later!
"""
import asyncio
from typing import Callable, Awaitable, Dict, List
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

class InProcessEventBus:
    """
    Lightweight in-process pub/sub.
    
    Use case: Modular monolith
    Future: Replace with Kafka without changing application code
    """
    
    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = defaultdict(list)
    
    def subscribe(self, event_type: str, handler: Callable[[dict], Awaitable[None]]):
        """Subscribe handler to event type"""
        self._handlers[event_type].append(handler)
        logger.info(f"[Bus] {handler.__name__} subscribed to {event_type}")
    
    async def publish(self, event_type: str, event: dict):
        """Publish event - in-process, async"""
        handlers = self._handlers.get(event_type, [])
        
        if not handlers:
            logger.debug(f"[Bus] No handlers for {event_type}")
            return
        
        # Fire all handlers in parallel
        # return_exceptions: one handler's failure shouldn't break others
        results = await asyncio.gather(
            *[h(event) for h in handlers],
            return_exceptions=True,
        )
        
        # Log failures
        for handler, result in zip(handlers, results):
            if isinstance(result, Exception):
                logger.error(f"[Bus] Handler {handler.__name__} failed: {result}")

# Global bus instance
event_bus = InProcessEventBus()

# ─────────────────────────────────────────────────────────────
# USAGE (same interface as Kafka!)
# ─────────────────────────────────────────────────────────────
async def update_inventory(event):
    print(f"Inventory updated for order {event['order_id']}")

async def send_email(event):
    print(f"Email sent for order {event['order_id']}")

# Subscribe
event_bus.subscribe("OrderPlaced", update_inventory)
event_bus.subscribe("OrderPlaced", send_email)

# Publish
await event_bus.publish("OrderPlaced", {
    "order_id": "ORD-001",
    "user_id": 123,
})
```

### Migration Path

```python
# 🏠 Phase 1: Monolith
event_bus = InProcessEventBus()

# 🌐 Phase 2: Replace with Kafka (same interface!)
class KafkaEventBus:
    async def publish(self, event_type: str, event: dict):
        # Send to Kafka instead
        await kafka_producer.send(event_type, event)

# Application code doesn't change!
event_bus = KafkaEventBus()
```

---

## 9. 📊 Schema Registry Integration

### `events/registry.py`

```python
"""
Schema registry for event evolution + validation.
"""
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer, AvroDeserializer
from confluent_kafka.serialization import SerializationContext, MessageField

# Schema in Avro format
ORDER_PLACED_SCHEMA_V1 = """
{
  "type": "record",
  "name": "OrderPlaced",
  "namespace": "com.example.events",
  "fields": [
    {"name": "order_id", "type": "string"},
    {"name": "user_id", "type": "int"},
    {"name": "items", "type": {
      "type": "array",
      "items": {
        "type": "record",
        "name": "OrderItem",
        "fields": [
          {"name": "sku", "type": "string"},
          {"name": "quantity", "type": "int"},
          {"name": "price", "type": "double"}
        ]
      }
    }},
    {"name": "total", "type": "double"},
    {"name": "currency", "type": "string", "default": "INR"}
  ]
}
"""

# v2 - backward compatible (new optional fields)
ORDER_PLACED_SCHEMA_V2 = """
{
  "type": "record",
  "name": "OrderPlaced",
  "namespace": "com.example.events",
  "fields": [
    {"name": "order_id", "type": "string"},
    {"name": "user_id", "type": "int"},
    {"name": "items", "type": "array", "items": {...}},
    {"name": "total", "type": "double"},
    {"name": "currency", "type": "string", "default": "INR"},
    {"name": "shipping_address", "type": ["null", "string"], "default": null},
    {"name": "expedited", "type": "boolean", "default": false}
  ]
}
"""

# Connect to Schema Registry
schema_registry = SchemaRegistryClient({
    'url': 'http://localhost:8081',
})

# Register schema (returns subject ID)
schema_id = schema_registry.register_schema(
    subject_name='orders-value',
    schema=ORDER_PLACED_SCHEMA_V2,
)

# Serializer for producers
avro_serializer = AvroSerializer(
    schema_registry,
    ORDER_PLACED_SCHEMA_V2,
)

# Deserializer for consumers (auto-fetches schema)
avro_deserializer = AvroDeserializer(schema_registry)
```

---

## 10. 📜 Event Audit & Replay

### `observability/event_audit.py`

```python
"""
Audit log of all events for replay + debugging.
"""
import asyncio
from aiokafka import AIOKafkaConsumer
import json
import sqlite3
from datetime import datetime

class EventAuditor:
    """
    Persistent audit log of all events.
    Enables replay + investigation.
    """
    
    def __init__(self, db_path: str = "events_audit.db"):
        self.conn = sqlite3.connect(db_path)
        self._init_db()
    
    def _init_db(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS events_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT UNIQUE NOT NULL,
                event_type TEXT NOT NULL,
                source TEXT NOT NULL,
                topic TEXT NOT NULL,
                partition INTEGER,
                offset_val INTEGER,
                timestamp TEXT NOT NULL,
                payload TEXT NOT NULL,
                INDEX idx_event_type (event_type),
                INDEX idx_timestamp (timestamp)
            )
        """)
        self.conn.commit()
    
    def record(self, msg):
        """Record event to audit log"""
        event = msg.value
        try:
            self.conn.execute("""
                INSERT OR IGNORE INTO events_log
                    (event_id, event_type, source, topic, partition, offset_val, timestamp, payload)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.get("event_id"),
                event.get("event_type"),
                event.get("source"),
                msg.topic,
                msg.partition,
                msg.offset,
                event.get("timestamp", datetime.utcnow().isoformat()),
                json.dumps(event),
            ))
            self.conn.commit()
        except Exception as e:
            print(f"Audit error: {e}")
    
    async def replay(
        self,
        event_type: str = None,
        from_timestamp: str = None,
        to_timestamp: str = None,
    ):
        """Replay events matching criteria"""
        query = "SELECT payload FROM events_log WHERE 1=1"
        params = []
        
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        
        if from_timestamp:
            query += " AND timestamp >= ?"
            params.append(from_timestamp)
        
        if to_timestamp:
            query += " AND timestamp <= ?"
            params.append(to_timestamp)
        
        query += " ORDER BY timestamp ASC"
        
        cursor = self.conn.execute(query, params)
        return [json.loads(row[0]) for row in cursor]

# ─────────────────────────────────────────────────────────────
# USAGE: Audit consumer (records all events)
# ─────────────────────────────────────────────────────────────
auditor = EventAuditor()

async def audit_consumer():
    consumer = AIOKafkaConsumer(
        "orders", "payments", "shipping",  # Multiple topics
        bootstrap_servers="localhost:9092",
        group_id="audit-service",
        value_deserializer=lambda v: json.loads(v.decode()),
    )
    await consumer.start()
    
    try:
        async for msg in consumer:
            auditor.record(msg)
            print(f"[AUDIT] Recorded {msg.value.get('event_id')}")
    finally:
        await consumer.stop()

# Replay events to debug
async def replay_yesterday_orders():
    events = await auditor.replay(
        event_type="OrderPlaced",
        from_timestamp="2026-05-25T00:00:00",
        to_timestamp="2026-05-26T00:00:00",
    )
    print(f"Replaying {len(events)} events...")
    for event in events:
        await event_bus.publish("OrderPlaced", event)
```

---

## 11. 🔍 Distributed Tracing for Events

### `observability/tracing.py`

```python
"""
Trace events across services with OpenTelemetry.
"""
from opentelemetry import trace, propagate
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.resources import Resource

def setup_tracing(service_name: str):
    """Configure distributed tracing"""
    resource = Resource.create({"service.name": service_name})
    trace.set_tracer_provider(TracerProvider(resource=resource))
    
    jaeger_exporter = JaegerExporter(
        agent_host_name="jaeger",
        agent_port=6831,
    )
    trace.get_tracer_provider().add_span_processor(
        BatchSpanProcessor(jaeger_exporter)
    )
    
    return trace.get_tracer(service_name)

# ─────────────────────────────────────────────────────────────
# Producer: inject trace context into event
# ─────────────────────────────────────────────────────────────
tracer = setup_tracing("order-service")

async def publish_with_trace(publisher, topic: str, event):
    with tracer.start_as_current_span(f"publish.{event.event_type}") as span:
        span.set_attribute("event.type", event.event_type)
        span.set_attribute("event.id", event.event_id)
        
        # Inject trace context into event headers
        carrier = {}
        propagate.inject(carrier)
        
        # Add to event headers
        headers = [(k, v.encode()) for k, v in carrier.items()]
        
        await publisher.publish(topic, event, headers=headers)

# ─────────────────────────────────────────────────────────────
# Consumer: extract trace context, continue trace
# ─────────────────────────────────────────────────────────────
async def consume_with_trace(msg):
    # Extract trace context from headers
    carrier = {h[0]: h[1].decode() for h in msg.headers}
    context = propagate.extract(carrier)
    
    # Continue trace
    with tracer.start_as_current_span(
        f"consume.{msg.value['event_type']}",
        context=context,
    ) as span:
        span.set_attribute("event.id", msg.value.get("event_id"))
        # Process event...
        await process_event(msg.value)
```

### View Traces in Jaeger

```
Browser: http://localhost:16686

You'll see:
   order-service: publish.OrderPlaced
        ↓
   inventory-service: consume.OrderPlaced
   email-service: consume.OrderPlaced
   analytics-service: consume.OrderPlaced
   
   All linked in single trace!
```

---

## 12. 🎯 End-to-End Example: Order Placement

### Producer (Order Service)

```python
"""order_service.py - producer"""
from fastapi import FastAPI, BackgroundTasks
from contextlib import asynccontextmanager
from events.schemas import OrderPlacedV1, OrderItem
from broker.kafka_publisher import EventPublisher

publisher = EventPublisher()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await publisher.start()
    yield
    await publisher.stop()

app = FastAPI(lifespan=lifespan)

@app.post("/orders")
async def create_order(req: dict, background: BackgroundTasks):
    # 1. Validate + save (sync part)
    order_id = f"ORD-{uuid.uuid4().hex[:8]}"
    # ... save to DB ...
    
    # 2. Emit event (async, broadcast)
    event = OrderPlacedV1(
        source="order-service",
        order_id=order_id,
        user_id=req["user_id"],
        items=[OrderItem(**i) for i in req["items"]],
        total=req["total"],
    )
    
    background.add_task(
        publisher.publish,
        "orders",
        event,
        key=str(req["user_id"]),  # Partition by user
    )
    
    return {"order_id": order_id, "status": "PROCESSING"}
```

### Inventory Consumer

```python
"""inventory_consumer.py"""
import asyncio
from broker.kafka_consumer import EventConsumer

async def handle_order(event: dict):
    print(f"[INVENTORY] Reserving stock for {event['order_id']}")
    
    for item in event["items"]:
        # Reserve stock
        await reserve_stock(item["sku"], item["quantity"])
    
    print(f"[INVENTORY] ✓ Reserved")

async def main():
    consumer = EventConsumer(
        topic="orders",
        group_id="inventory-service",
        handler=handle_order,
    )
    await consumer.start()
    await consumer.run()

asyncio.run(main())
```

### Email Consumer

```python
"""email_consumer.py"""
async def handle_order(event: dict):
    print(f"[EMAIL] Sending confirmation for {event['order_id']}")
    
    # Get user email
    user = await user_service.get(event["user_id"])
    
    # Send email
    await email_service.send(
        to=user.email,
        subject=f"Order {event['order_id']} confirmed",
        template="order_confirmation",
        data=event,
    )

# Same boilerplate as inventory_consumer
```

### Test the Flow

```bash
# Start all consumers in different terminals:
$ python inventory_consumer.py
$ python email_consumer.py
$ python analytics_consumer.py
$ python loyalty_consumer.py

# Start order service:
$ uvicorn order_service:app --port 8000

# Place an order:
$ curl -X POST http://localhost:8000/orders \
    -H "Content-Type: application/json" \
    -d '{
      "user_id": 123,
      "items": [{"sku": "SKU-1", "quantity": 2, "price": 499}],
      "total": 998
    }'

# Response (instant!):
{"order_id": "ORD-abc123", "status": "PROCESSING"}

# All 4 consumers react IN PARALLEL:
[INVENTORY] Reserving stock for ORD-abc123
[EMAIL] Sending confirmation for ORD-abc123
[ANALYTICS] Logging order ORD-abc123
[LOYALTY] Awarding 50 points for ORD-abc123
```

---

## 13. 🐳 Docker Compose

```yaml
version: '3.8'

services:
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
  
  schema-registry:
    image: confluentinc/cp-schema-registry:7.5.0
    depends_on: [kafka]
    ports: ["8081:8081"]
    environment:
      SCHEMA_REGISTRY_HOST_NAME: schema-registry
      SCHEMA_REGISTRY_KAFKASTORE_BOOTSTRAP_SERVERS: kafka:9092
  
  kafka-ui:
    image: provectuslabs/kafka-ui
    ports: ["8080:8080"]
    environment:
      KAFKA_CLUSTERS_0_NAME: local
      KAFKA_CLUSTERS_0_BOOTSTRAPSERVERS: kafka:9092
      KAFKA_CLUSTERS_0_SCHEMAREGISTRY: http://schema-registry:8081
    depends_on: [kafka, schema-registry]
  
  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "16686:16686"  # UI
      - "6831:6831/udp"
```

---

## 14. Key Learnings Summary

```
✅ Strongly-typed events with Pydantic
✅ CloudEvents standard for interoperability
✅ Kafka producer with reliability features
✅ Consumer with manual commit + DLQ
✅ Multiple consumer groups = fanout
✅ In-process bus for monoliths (migration-ready)
✅ Schema registry for evolution
✅ Audit log for replay + debugging
✅ Distributed tracing across events
✅ End-to-end demo with 4 consumers

🎯 Production EDA stack:
   Kafka + Schema Registry + Audit + Jaeger + DLQ
```

---

## 🎬 What's Next?

In **Lecture 2**, we'll explore **Event Sourcing and CQRS** — patterns that take EDA to the next level.

> **Next lecture:** [02_Event_Sourcing_CQRS.md](02_Event_Sourcing_CQRS.md)

---

## 📚 Try It Yourself

1. Add **schema validation** with Confluent Schema Registry
2. Implement **event versioning** with up-casters
3. Build **event replay UI** for ops team
4. Add **CDC (Change Data Capture)** from DB to events
5. Migrate **in-process bus** to Kafka without changing app code
