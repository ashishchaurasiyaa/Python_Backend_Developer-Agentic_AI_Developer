# API Design — AsyncAPI Specification for Event-Driven APIs
**API Design · Year 3-4 | Senior Backend + Agentic AI**

## Quick Concepts
- **AsyncAPI** = OpenAPI for events — declarative spec for event-driven APIs
- **Why** = same problem OpenAPI solved for REST: standardize docs, codegen, tooling
- **Supports** = Kafka, AMQP (RabbitMQ), MQTT, WebSocket, NATS, Redis Pub/Sub, SNS/SQS
- **Operations** = `send` (publish) vs `receive` (subscribe)
- **Channels** = communication paths (Kafka topics, queue names, WebSocket paths)
- **Messages** = payload schemas (often JSON Schema)
- **Current version** = AsyncAPI 3.0 (released 2023, stable in 2026)
- **Tooling** = AsyncAPI Studio, Generator, Modelina (codegen), Glee

---

## Why Backend Devs Care

```
Without AsyncAPI:                       With AsyncAPI:
─────────────                           ───────────────
"Hey, what's the schema                 Look at the spec.
 of order-events?"
                                        Auto-generated docs.
"Let me grep the producer..."
                                        Codegen consumer skeleton.
3 hours later: still finding it.
                                        Validate at CI time.
Schema breaks → silent failures.        Mock servers for testing.
```

---

## AsyncAPI 3.0 — Minimal Example

```yaml
# asyncapi.yaml
asyncapi: 3.0.0
info:
  title: Order Service Events
  version: 1.2.0
  description: |
    Order lifecycle events published to Kafka.
    Consumed by: notification-service, search-indexer, analytics.
  contact:
    name: Backend Team
    email: backend@acme.com

servers:
  production:
    host: kafka.prod.internal:9092
    protocol: kafka
    description: Production Kafka cluster

  staging:
    host: kafka.staging.internal:9092
    protocol: kafka

channels:
  orderCreated:
    address: orders.created
    title: Order Created Event
    messages:
      orderCreated:
        $ref: '#/components/messages/OrderCreated'

  orderShipped:
    address: orders.shipped
    messages:
      orderShipped:
        $ref: '#/components/messages/OrderShipped'

operations:
  publishOrderCreated:
    action: send
    channel:
      $ref: '#/channels/orderCreated'
    summary: Publish when a new order is created
    messages:
      - $ref: '#/channels/orderCreated/messages/orderCreated'

  receiveOrderCreated:
    action: receive
    channel:
      $ref: '#/channels/orderCreated'
    summary: Consume order creation events
    messages:
      - $ref: '#/channels/orderCreated/messages/orderCreated'

components:
  messages:
    OrderCreated:
      name: OrderCreated
      title: Order Created
      contentType: application/json
      payload:
        $ref: '#/components/schemas/OrderCreatedPayload'

    OrderShipped:
      name: OrderShipped
      title: Order Shipped
      contentType: application/json
      payload:
        $ref: '#/components/schemas/OrderShippedPayload'

  schemas:
    OrderCreatedPayload:
      type: object
      required: [orderId, userId, total, items, createdAt]
      properties:
        orderId:
          type: string
          format: uuid
        userId:
          type: integer
          minimum: 1
        total:
          type: number
          format: float
          minimum: 0
        items:
          type: array
          items:
            $ref: '#/components/schemas/OrderItem'
        createdAt:
          type: string
          format: date-time

    OrderShippedPayload:
      type: object
      required: [orderId, trackingNumber, shippedAt]
      properties:
        orderId:
          type: string
          format: uuid
        trackingNumber:
          type: string
        carrier:
          type: string
          enum: [fedex, ups, dhl, bluedart]
        shippedAt:
          type: string
          format: date-time

    OrderItem:
      type: object
      required: [productId, quantity, price]
      properties:
        productId:
          type: string
        quantity:
          type: integer
          minimum: 1
        price:
          type: number
          minimum: 0
```

---

## Interview Questions & Answers

### Q1: AsyncAPI spec ko Python services se kaise integrate karte hain?

**Answer:** Spec as source of truth → validate messages at runtime.

```python
import json
import yaml
from jsonschema import validate, ValidationError
from pathlib import Path

# Load spec at startup
ASYNCAPI_SPEC = yaml.safe_load(Path("asyncapi.yaml").read_text())

class EventValidator:
    def __init__(self, spec: dict):
        self.spec = spec
        # Resolve $ref pointers to actual schemas
        self.message_schemas = self._build_schema_map()

    def _build_schema_map(self) -> dict[str, dict]:
        result = {}
        for msg_name, msg_def in self.spec["components"]["messages"].items():
            payload_ref = msg_def["payload"]["$ref"]
            schema_name = payload_ref.split("/")[-1]
            result[msg_name] = self.spec["components"]["schemas"][schema_name]
        return result

    def validate_message(self, message_name: str, payload: dict):
        if message_name not in self.message_schemas:
            raise ValueError(f"Unknown message: {message_name}")
        try:
            validate(instance=payload, schema=self.message_schemas[message_name])
        except ValidationError as e:
            raise ValueError(f"Schema validation failed: {e.message}")

validator = EventValidator(ASYNCAPI_SPEC)

# ─── Producer ───
from aiokafka import AIOKafkaProducer

class OrderEventProducer:
    def __init__(self, bootstrap_servers: str):
        self.producer = AIOKafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )

    async def publish_order_created(self, payload: dict):
        # Validate before publishing — fail fast
        validator.validate_message("OrderCreated", payload)
        await self.producer.send_and_wait("orders.created", payload)

# ─── Consumer ───
async def consume_orders():
    consumer = AIOKafkaConsumer(
        "orders.created",
        bootstrap_servers="kafka:9092",
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )
    await consumer.start()
    async for msg in consumer:
        try:
            validator.validate_message("OrderCreated", msg.value)
            await handle_order(msg.value)
        except ValueError as e:
            await send_to_dlq(msg, error=str(e))
```

---

### Q2: Code generation from AsyncAPI spec?

**Answer:** Use `@asyncapi/generator` CLI to scaffold producers/consumers.

```bash
# Install
npm install -g @asyncapi/cli

# Validate spec
asyncapi validate asyncapi.yaml

# Generate Python types (using Modelina)
asyncapi generate models python asyncapi.yaml -o ./generated/models

# Generate full consumer skeleton (Java template — Python templates emerging)
asyncapi generate fromTemplate asyncapi.yaml @asyncapi/python-paho-template -o ./generated
```

**Python equivalent with `datamodel-code-generator`** (more mature):
```bash
pip install datamodel-code-generator

# Extract just the schemas section
python -c "
import yaml, json
spec = yaml.safe_load(open('asyncapi.yaml'))
schemas = {'$schema': 'http://json-schema.org/draft-07/schema#', 'definitions': spec['components']['schemas']}
json.dump(schemas, open('schemas.json', 'w'), indent=2)
"

datamodel-codegen --input schemas.json --output models.py --target-python-version 3.12 --use-standard-collections
```

Generated `models.py`:
```python
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field

class OrderItem(BaseModel):
    productId: str
    quantity: int = Field(..., ge=1)
    price: float = Field(..., ge=0)

class OrderCreatedPayload(BaseModel):
    orderId: UUID
    userId: int = Field(..., ge=1)
    total: float = Field(..., ge=0)
    items: list[OrderItem]
    createdAt: datetime
```

Now producer is type-safe:
```python
async def publish(payload: OrderCreatedPayload):
    await producer.send_and_wait("orders.created", payload.model_dump(mode="json"))
```

---

### Q3: Multi-protocol support (Kafka + WebSocket + RabbitMQ in one spec)?

**Answer:** AsyncAPI handles all in one file — different servers/protocols.

```yaml
asyncapi: 3.0.0
info:
  title: Multi-Protocol Service
  version: 1.0.0

servers:
  kafka-prod:
    host: kafka.prod:9092
    protocol: kafka

  rabbitmq-prod:
    host: rabbitmq.prod:5672
    protocol: amqp

  websocket-public:
    host: ws.acme.com
    protocol: wss
    pathname: /ws

channels:
  # Kafka topic
  orderEvents:
    address: orders.events
    servers:
      - $ref: '#/servers/kafka-prod'
    messages:
      orderCreated: { $ref: '#/components/messages/OrderCreated' }

  # RabbitMQ queue
  emailQueue:
    address: emails.outbound
    servers:
      - $ref: '#/servers/rabbitmq-prod'
    bindings:
      amqp:
        is: queue
        queue:
          name: emails.outbound
          durable: true
          autoDelete: false
    messages:
      sendEmail: { $ref: '#/components/messages/SendEmail' }

  # WebSocket
  liveOrders:
    address: /orders/live
    servers:
      - $ref: '#/servers/websocket-public'
    bindings:
      ws:
        method: GET
        query:
          type: object
          properties:
            token: { type: string }
    messages:
      orderUpdate: { $ref: '#/components/messages/OrderUpdate' }
```

---

### Q4: CI validation — break build if spec doesn't match code?

**Answer:** Generated models + tests = drift detection.

```python
# tests/test_asyncapi_compliance.py
import yaml
from pathlib import Path

import pytest
from models import OrderCreatedPayload  # codegen'd

SPEC = yaml.safe_load(Path("asyncapi.yaml").read_text())

class TestAsyncAPICompliance:
    def test_order_created_schema_matches_pydantic(self):
        """Ensure Pydantic model fields match AsyncAPI schema."""
        spec_schema = SPEC["components"]["schemas"]["OrderCreatedPayload"]
        spec_fields = set(spec_schema["properties"].keys())
        pydantic_fields = set(OrderCreatedPayload.model_fields.keys())
        assert spec_fields == pydantic_fields, f"Schema drift: {spec_fields ^ pydantic_fields}"

    def test_required_fields_aligned(self):
        spec_required = set(SPEC["components"]["schemas"]["OrderCreatedPayload"]["required"])
        pydantic_required = {
            name for name, field in OrderCreatedPayload.model_fields.items()
            if field.is_required()
        }
        assert spec_required == pydantic_required

    def test_spec_is_valid(self):
        """Run asyncapi CLI to validate."""
        import subprocess
        result = subprocess.run(
            ["asyncapi", "validate", "asyncapi.yaml"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr
```

```yaml
# .github/workflows/asyncapi.yml
name: AsyncAPI CI
on: [push, pull_request]
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - run: npm install -g @asyncapi/cli
      - run: asyncapi validate asyncapi.yaml
      - run: asyncapi optimize asyncapi.yaml --no-tty  # check for issues
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install -r requirements.txt
      - run: pytest tests/test_asyncapi_compliance.py
```

---

### Q5: Auto-generate docs (HTML/PDF)?

**Answer:** `asyncapi generate fromTemplate` with HTML template.

```bash
# Beautiful HTML docs
asyncapi generate fromTemplate asyncapi.yaml @asyncapi/html-template -o ./docs/asyncapi

# Markdown for GitHub
asyncapi generate fromTemplate asyncapi.yaml @asyncapi/markdown-template -o ./docs

# Combine with mkdocs
mkdocs build
```

**Sample output structure:**
```
docs/
├── index.html          # interactive UI like Swagger
├── operations.html
└── schemas.html
```

**Host with FastAPI:**
```python
from fastapi.staticfiles import StaticFiles

app.mount("/asyncapi", StaticFiles(directory="docs/asyncapi", html=True), name="asyncapi")
```

---

### Q6: Versioning event schemas?

**Answer:** Three strategies — embed version, version channel, schema registry.

**Strategy 1: Version in payload**
```yaml
schemas:
  OrderCreatedPayload:
    properties:
      version:
        type: string
        enum: ["1.0", "1.1", "2.0"]
      orderId: { type: string }
      # ...
```

Consumer:
```python
async def handle(msg):
    if msg["version"] == "1.0":
        await handle_v1(msg)
    elif msg["version"].startswith("1."):
        await handle_v1(msg)  # backward compat
    else:
        await handle_v2(msg)
```

**Strategy 2: Versioned channels**
```yaml
channels:
  orderCreatedV1:
    address: orders.created.v1
  orderCreatedV2:
    address: orders.created.v2
```

Producer publishes to both during migration window.

**Strategy 3: Confluent Schema Registry (Avro)**
- External schema management
- Compatibility rules enforced (`BACKWARD`, `FORWARD`, `FULL`)
- Better than AsyncAPI alone for Avro-based pipelines

---

### Q7: AsyncAPI + OpenAPI together (full API surface)?

**Answer:** Document REST + events in one place.

```
project/
├── openapi.yaml         # REST endpoints
├── asyncapi.yaml        # Events
└── docs/
    ├── api/             # OpenAPI docs (Swagger)
    └── events/          # AsyncAPI docs
```

**Cross-reference example:**
```yaml
# asyncapi.yaml
info:
  title: Order Service Events
  externalDocs:
    url: https://api.acme.com/docs/openapi
    description: REST API counterpart

operations:
  publishOrderCreated:
    action: send
    bindings:
      http:
        type: response
        # Triggered after POST /orders (see openapi.yaml#/paths/~1orders/post)
```

---

### Q8: Common AsyncAPI bindings (protocol-specific config)?

**Answer:** Bindings let you specify protocol details.

**Kafka binding:**
```yaml
channels:
  orderEvents:
    address: orders.created
    bindings:
      kafka:
        topic: orders.created
        partitions: 12
        replicas: 3
        topicConfiguration:
          cleanup.policy: ["delete", "compact"]
          retention.ms: 604800000  # 7 days
```

**AMQP (RabbitMQ) binding:**
```yaml
channels:
  emailQueue:
    address: emails.outbound
    bindings:
      amqp:
        is: queue
        queue:
          name: emails.outbound
          durable: true
          exclusive: false
          autoDelete: false
        exchange:
          name: emails
          type: topic
          durable: true
        bindingKey: email.send.*
```

**WebSocket binding:**
```yaml
channels:
  chat:
    address: /chat/{roomId}
    parameters:
      roomId: { type: string }
    bindings:
      ws:
        method: GET
        query:
          type: object
          properties:
            token: { type: string }
        headers:
          type: object
          properties:
            Authorization: { type: string }
```

---

## Tooling Ecosystem

| Tool | Purpose |
|---|---|
| **AsyncAPI Studio** | Visual editor + live validation (studio.asyncapi.com) |
| **asyncapi CLI** | Validate, generate, optimize |
| **Generator** | Code/doc generation from spec |
| **Modelina** | Type generation (Python, TS, Java, Go) |
| **Glee** | Spec-first framework (build entire app from spec) |
| **AsyncAPI Diff** | Detect breaking changes between versions |
| **Microcks** | Mock servers + contract testing |

---

## Production Gotchas

| Gotcha | Fix |
|---|---|
| Spec drifts from code | CI validation + generated models |
| `$ref` not resolved by validator | Use full URL or absolute path |
| AsyncAPI 2.x vs 3.x | Migrate to 3.0 (operations are first-class) |
| Generators lack Python templates | Use `datamodel-code-generator` for models |
| Multi-line descriptions don't render | Use literal block (`|`) in YAML |
| Avro + AsyncAPI integration | Reference Avro schema in `schemaFormat` |
| Auth not documented | Add `securitySchemes` like OpenAPI |
| Spec size > 1MB | Split with `$ref` to external files |

---

## When to Use AsyncAPI

| Use AsyncAPI | Skip AsyncAPI |
|---|---|
| Microservices with multiple event streams | Single producer-consumer |
| Multi-team org (consumer teams need docs) | Solo project |
| Need codegen for consumers | Ad-hoc scripts |
| Avro/Protobuf already used | Plain JSON in tight team |
| Public event API | Internal-only, ephemeral |

---

## Senior-level Checklist

- [ ] `asyncapi.yaml` at root of every event-publishing service
- [ ] AsyncAPI 3.0 (not 2.x)
- [ ] All channels documented with descriptions
- [ ] Required fields explicit in schemas
- [ ] Bindings configured per protocol (kafka/amqp/ws)
- [ ] CI validates spec on every push
- [ ] CI checks Pydantic models match spec schemas
- [ ] HTML docs auto-generated + hosted
- [ ] Version strategy decided (channel vs payload)
- [ ] Compatibility rules in schema registry (if Avro)
- [ ] Cross-referenced with OpenAPI for REST counterparts
- [ ] Mock server for consumer integration tests (Microcks)

---

## Related Docs
- `01_rest_best_practices.md` — REST/OpenAPI complement
- `16_versioning_strategies_deep.md` — versioning patterns
- `01_Year3-4_Mid/07_Kafka/` — Kafka deep dive
- `01_Year3-4_Mid/08_RabbitMQ/` — AMQP patterns
- `01_Year3-4_Mid/05_Microservices/04_outbox_event_sourcing.md` — event-driven architecture

## External References
- AsyncAPI spec: https://www.asyncapi.com/docs/reference/specification/v3.0.0
- Bindings: https://github.com/asyncapi/bindings
- Studio: https://studio.asyncapi.com
