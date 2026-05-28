# Lecture 2 — Practical Hands-On: Building Microservices

> **Theory file:** [02_Microservices_Architecture.md](02_Microservices_Architecture.md)

---

## 🎯 Is Practical Mein Kya Banayenge?

Ek **complete microservices system** with:

1. ✅ **3 microservices** (Order, Inventory, Payment) in FastAPI
2. ✅ **Per-service database** (PostgreSQL + MongoDB + Redis)
3. ✅ **REST APIs** with OpenAPI documentation
4. ✅ **Async events via Kafka**
5. ✅ **Resilience patterns** (retry, circuit breaker, timeout)
6. ✅ **Distributed tracing** with OpenTelemetry + Jaeger
7. ✅ **Service discovery** via Consul / K8s DNS
8. ✅ **API Gateway** with rate limiting + auth
9. ✅ **Docker Compose** for local development
10. ✅ **Saga pattern** for distributed transactions

By end: aap **production-grade microservices system** bana sakte ho.

---

## 1. Project Structure

```
microservices_demo/
├── docker-compose.yml
├── README.md
│
├── api-gateway/
│   ├── main.py                  # Kong or FastAPI gateway
│   └── Dockerfile
│
├── services/
│   ├── order-service/
│   │   ├── main.py
│   │   ├── models.py
│   │   ├── repository.py
│   │   ├── events.py
│   │   ├── requirements.txt
│   │   ├── Dockerfile
│   │   └── tests/
│   │
│   ├── inventory-service/
│   │   ├── main.py
│   │   ├── models.py
│   │   ├── repository.py
│   │   ├── consumer.py          # Kafka consumer
│   │   ├── requirements.txt
│   │   ├── Dockerfile
│   │   └── tests/
│   │
│   └── payment-service/
│       ├── main.py
│       ├── models.py
│       ├── resilience.py        # Circuit breaker, retry
│       ├── requirements.txt
│       ├── Dockerfile
│       └── tests/
│
├── shared/
│   ├── tracing.py               # OpenTelemetry setup
│   ├── events.py                # Event schemas
│   └── kafka_helpers.py
│
└── infra/
    ├── prometheus.yml
    ├── grafana/
    └── jaeger/
```

---

## 2. Setup & Dependencies

### Install Required Packages

```bash
# Per-service requirements
pip install fastapi uvicorn
pip install httpx tenacity circuitbreaker  # Resilience
pip install aiokafka                       # Kafka client
pip install opentelemetry-distro            # Tracing
pip install opentelemetry-exporter-jaeger
pip install opentelemetry-instrumentation-fastapi
pip install opentelemetry-instrumentation-httpx
pip install sqlalchemy asyncpg              # PostgreSQL
pip install motor                            # MongoDB
pip install redis                            # Redis
pip install prometheus-client                # Metrics
pip install pydantic-settings
```

---

## 3. 📦 Order Service (FastAPI)

### `services/order-service/main.py`

```python
"""
Order Service - Microservice owning order lifecycle.

Responsibilities:
- Create/read orders
- Coordinate with Inventory + Payment services
- Publish order events to Kafka
- Own its database
"""
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
from typing import List
import httpx
import asyncio
import uuid
from datetime import datetime
from contextlib import asynccontextmanager

from .repository import OrderRepository, init_db
from .events import OrderEventPublisher
from shared.tracing import setup_tracing

# ─────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────
SERVICE_NAME = "order-service"
INVENTORY_URL = "http://inventory-service:8001"
PAYMENT_URL = "http://payment-service:8002"

# ─────────────────────────────────────────────────────────────
# LIFESPAN (startup/shutdown)
# ─────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    app.state.publisher = OrderEventPublisher()
    await app.state.publisher.start()
    yield
    await app.state.publisher.stop()

# ─────────────────────────────────────────────────────────────
# APP SETUP
# ─────────────────────────────────────────────────────────────
app = FastAPI(title="Order Service", lifespan=lifespan)
setup_tracing(app, SERVICE_NAME)

# ─────────────────────────────────────────────────────────────
# MODELS
# ─────────────────────────────────────────────────────────────
class OrderItem(BaseModel):
    sku: str
    quantity: int

class CreateOrderRequest(BaseModel):
    user_id: int
    items: List[OrderItem]

class OrderResponse(BaseModel):
    order_id: str
    user_id: int
    status: str
    total: float
    items: List[OrderItem]
    created_at: str

# ─────────────────────────────────────────────────────────────
# DEPENDENCY INJECTION
# ─────────────────────────────────────────────────────────────
def get_repo():
    return OrderRepository()

def get_publisher():
    return app.state.publisher

# ─────────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────────
@app.post("/orders", response_model=OrderResponse, status_code=201)
async def create_order(
    req: CreateOrderRequest,
    background: BackgroundTasks,
    repo: OrderRepository = Depends(get_repo),
    publisher: OrderEventPublisher = Depends(get_publisher),
):
    """
    Synchronous orchestration:
    1. Check inventory (sync - need result)
    2. Process payment (sync - need result)
    3. Save order
    4. Publish event (async - notify others)
    """
    order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"
    
    async with httpx.AsyncClient(timeout=5.0) as client:
        # 1. CHECK INVENTORY (parallel for all items)
        inventory_tasks = [
            client.get(f"{INVENTORY_URL}/items/{item.sku}")
            for item in req.items
        ]
        inventory_responses = await asyncio.gather(*inventory_tasks, return_exceptions=True)
        
        total = 0.0
        for item, resp in zip(req.items, inventory_responses):
            if isinstance(resp, Exception):
                raise HTTPException(503, f"Inventory service unavailable")
            if resp.status_code != 200:
                raise HTTPException(404, f"Product {item.sku} not found")
            
            product = resp.json()
            if product["stock"] < item.quantity:
                raise HTTPException(400, f"Insufficient stock for {item.sku}")
            total += product["price"] * item.quantity
        
        # 2. RESERVE STOCK
        reserve_resp = await client.post(
            f"{INVENTORY_URL}/reservations",
            json={"items": [item.dict() for item in req.items], "order_id": order_id}
        )
        if reserve_resp.status_code != 201:
            raise HTTPException(409, "Could not reserve stock")
        
        # 3. CHARGE PAYMENT
        try:
            payment_resp = await client.post(
                f"{PAYMENT_URL}/charges",
                json={"user_id": req.user_id, "amount": total, "order_id": order_id}
            )
            if payment_resp.status_code != 200:
                # COMPENSATE: release stock
                await client.delete(f"{INVENTORY_URL}/reservations/{order_id}")
                raise HTTPException(402, "Payment failed")
        except httpx.RequestError:
            # COMPENSATE: release stock
            await client.delete(f"{INVENTORY_URL}/reservations/{order_id}")
            raise HTTPException(503, "Payment service unavailable")
    
    # 4. SAVE ORDER
    order = await repo.create({
        "order_id": order_id,
        "user_id": req.user_id,
        "items": [item.dict() for item in req.items],
        "total": total,
        "status": "CONFIRMED",
        "created_at": datetime.utcnow().isoformat(),
    })
    
    # 5. PUBLISH EVENT (async, fire-and-forget)
    background.add_task(
        publisher.publish, "order.created",
        {"order_id": order_id, "user_id": req.user_id, "total": total}
    )
    
    return OrderResponse(**order)

@app.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(order_id: str, repo: OrderRepository = Depends(get_repo)):
    order = await repo.get(order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    return order

@app.get("/health")
async def health():
    return {"status": "healthy", "service": SERVICE_NAME}

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    from prometheus_client import generate_latest
    return generate_latest()
```

### `services/order-service/repository.py`

```python
"""Order repository - owns the order database"""
import asyncpg
import json
from typing import Optional

DATABASE_URL = "postgresql://order_user:order_pass@order-db:5432/orders"

_pool: Optional[asyncpg.Pool] = None

async def init_db():
    global _pool
    _pool = await asyncpg.create_pool(DATABASE_URL, min_size=5, max_size=20)
    
    async with _pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id VARCHAR PRIMARY KEY,
                user_id INTEGER NOT NULL,
                items JSONB NOT NULL,
                total NUMERIC NOT NULL,
                status VARCHAR NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

class OrderRepository:
    async def create(self, order: dict) -> dict:
        async with _pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO orders (order_id, user_id, items, total, status)
                VALUES ($1, $2, $3, $4, $5)
            """, order["order_id"], order["user_id"], 
                 json.dumps(order["items"]), order["total"], order["status"])
        return order
    
    async def get(self, order_id: str) -> Optional[dict]:
        async with _pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM orders WHERE order_id = $1", order_id)
            if not row:
                return None
            return {
                "order_id": row["order_id"],
                "user_id": row["user_id"],
                "items": json.loads(row["items"]),
                "total": float(row["total"]),
                "status": row["status"],
                "created_at": row["created_at"].isoformat(),
            }
```

### `services/order-service/events.py`

```python
"""Kafka event publisher"""
from aiokafka import AIOKafkaProducer
import json

class OrderEventPublisher:
    def __init__(self):
        self.producer = None
    
    async def start(self):
        self.producer = AIOKafkaProducer(
            bootstrap_servers="kafka:9092",
            value_serializer=lambda v: json.dumps(v).encode(),
        )
        await self.producer.start()
    
    async def stop(self):
        if self.producer:
            await self.producer.stop()
    
    async def publish(self, topic: str, payload: dict):
        await self.producer.send_and_wait(topic, payload)
        print(f"[EVENT] Published {topic}: {payload}")
```

---

## 4. 📋 Inventory Service

### `services/inventory-service/main.py`

```python
"""
Inventory Service - Owns product catalog & stock.

Responsibilities:
- Manage product inventory
- Handle stock reservations
- React to order events (release stock on cancel)
"""
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import List
import asyncio
from contextlib import asynccontextmanager

from .repository import InventoryRepository, init_db
from .consumer import OrderEventConsumer
from shared.tracing import setup_tracing

SERVICE_NAME = "inventory-service"

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    consumer = OrderEventConsumer()
    consumer_task = asyncio.create_task(consumer.start())
    yield
    consumer_task.cancel()

app = FastAPI(title="Inventory Service", lifespan=lifespan)
setup_tracing(app, SERVICE_NAME)

# ─────────────────────────────────────────────────────────────
# MODELS
# ─────────────────────────────────────────────────────────────
class Product(BaseModel):
    sku: str
    name: str
    stock: int
    price: float

class ReservationItem(BaseModel):
    sku: str
    quantity: int

class ReservationRequest(BaseModel):
    order_id: str
    items: List[ReservationItem]

# ─────────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────────
def get_repo():
    return InventoryRepository()

@app.get("/items/{sku}", response_model=Product)
async def get_item(sku: str, repo: InventoryRepository = Depends(get_repo)):
    product = await repo.get(sku)
    if not product:
        raise HTTPException(404, f"Product {sku} not found")
    return product

@app.post("/reservations", status_code=201)
async def create_reservation(
    req: ReservationRequest,
    repo: InventoryRepository = Depends(get_repo)
):
    """Reserve stock for an order (idempotent via order_id)"""
    success = await repo.reserve(req.order_id, req.items)
    if not success:
        raise HTTPException(409, "Insufficient stock")
    return {"order_id": req.order_id, "status": "RESERVED"}

@app.delete("/reservations/{order_id}", status_code=204)
async def release_reservation(
    order_id: str,
    repo: InventoryRepository = Depends(get_repo)
):
    """Release reserved stock (compensation)"""
    await repo.release(order_id)
    return None

@app.get("/health")
async def health():
    return {"status": "healthy", "service": SERVICE_NAME}
```

### `services/inventory-service/consumer.py`

```python
"""Kafka consumer - reacts to order events"""
from aiokafka import AIOKafkaConsumer
import json

class OrderEventConsumer:
    def __init__(self):
        self.consumer = None
    
    async def start(self):
        self.consumer = AIOKafkaConsumer(
            "order.cancelled",  # We care about cancellations
            bootstrap_servers="kafka:9092",
            group_id="inventory-service",  # Consumer group
            value_deserializer=lambda v: json.loads(v.decode()),
        )
        await self.consumer.start()
        
        try:
            async for msg in self.consumer:
                event = msg.value
                print(f"[EVENT] Received order.cancelled: {event}")
                # Release stock for cancelled order
                from .repository import InventoryRepository
                repo = InventoryRepository()
                await repo.release(event["order_id"])
        finally:
            await self.consumer.stop()
```

---

## 5. 💳 Payment Service with Resilience

### `services/payment-service/main.py`

```python
"""
Payment Service - Charges payments with resilience patterns.

Demonstrates:
- Retry with exponential backoff
- Circuit breaker
- Timeout
- Idempotency
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uuid
import httpx
from contextlib import asynccontextmanager

from .resilience import resilient_charge
from shared.tracing import setup_tracing

SERVICE_NAME = "payment-service"

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(title="Payment Service", lifespan=lifespan)
setup_tracing(app, SERVICE_NAME)

class ChargeRequest(BaseModel):
    user_id: int
    amount: float
    order_id: str  # for idempotency

class ChargeResponse(BaseModel):
    transaction_id: str
    status: str
    amount: float

# Idempotency cache (use Redis in production)
PROCESSED_ORDERS = {}

@app.post("/charges", response_model=ChargeResponse)
async def charge(req: ChargeRequest):
    # Idempotency: same order_id = same response
    if req.order_id in PROCESSED_ORDERS:
        return PROCESSED_ORDERS[req.order_id]
    
    # Call external payment gateway with resilience
    try:
        result = await resilient_charge(
            user_id=req.user_id,
            amount=req.amount
        )
    except Exception as e:
        raise HTTPException(503, f"Payment processing failed: {e}")
    
    response = ChargeResponse(
        transaction_id=f"TXN-{uuid.uuid4().hex[:10].upper()}",
        status="SUCCESS",
        amount=req.amount
    )
    PROCESSED_ORDERS[req.order_id] = response
    return response

@app.get("/health")
async def health():
    return {"status": "healthy", "service": SERVICE_NAME}
```

### `services/payment-service/resilience.py`

```python
"""
Resilience patterns for payment service.

- Retry with exponential backoff
- Circuit breaker
- Timeout
"""
import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from circuitbreaker import circuit
import logging

logger = logging.getLogger(__name__)

@circuit(
    failure_threshold=5,        # Open after 5 failures
    recovery_timeout=30,         # Try again after 30s
    expected_exception=httpx.HTTPError,
)
@retry(
    stop=stop_after_attempt(3),  # Try 3 times
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(httpx.RequestError),
    before_sleep=lambda r: logger.warning(f"Retry attempt {r.attempt_number}")
)
async def resilient_charge(user_id: int, amount: float) -> dict:
    """
    Call external payment gateway with resilience.
    
    Combined patterns:
    - Circuit breaker (fails fast after 5 failures)
    - Retry (3 attempts with exponential backoff)
    - Timeout (5 seconds per attempt)
    """
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.post(
            "https://payment-gateway.example.com/charge",
            json={"user_id": user_id, "amount": amount}
        )
        response.raise_for_status()
        return response.json()
```

---

## 6. 🔍 Distributed Tracing Setup

### `shared/tracing.py`

```python
"""
OpenTelemetry tracing setup.
One file shared by all services.
"""
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor

def setup_tracing(app, service_name: str):
    """
    Configure distributed tracing for a microservice.
    
    Traces will appear in Jaeger UI at http://localhost:16686
    """
    # 1. Set up tracer provider
    resource = Resource.create({"service.name": service_name})
    trace.set_tracer_provider(TracerProvider(resource=resource))
    
    # 2. Configure Jaeger exporter
    jaeger_exporter = JaegerExporter(
        agent_host_name="jaeger",
        agent_port=6831,
    )
    trace.get_tracer_provider().add_span_processor(
        BatchSpanProcessor(jaeger_exporter)
    )
    
    # 3. Auto-instrument frameworks
    FastAPIInstrumentor.instrument_app(app)
    HTTPXClientInstrumentor().instrument()
    AsyncPGInstrumentor().instrument()
    
    print(f"[TRACING] Configured for {service_name}")
```

### Manual Span Creation

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

@app.post("/orders")
async def create_order(req: CreateOrderRequest):
    # Custom span for business logic
    with tracer.start_as_current_span("create_order_workflow") as span:
        span.set_attribute("user_id", req.user_id)
        span.set_attribute("items_count", len(req.items))
        
        with tracer.start_as_current_span("inventory_check"):
            # ... check inventory ...
            pass
        
        with tracer.start_as_current_span("payment_processing"):
            # ... process payment ...
            pass
        
        span.set_attribute("order_id", order_id)
        return order
```

---

## 7. 🚪 API Gateway

### `api-gateway/main.py` (using FastAPI)

```python
"""
Simple API Gateway in FastAPI.
In production, use Kong, Tyk, AWS API Gateway, etc.
"""
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import httpx
import time
from collections import defaultdict, deque

app = FastAPI(title="API Gateway")
security = HTTPBearer()

# ─────────────────────────────────────────────────────────────
# RATE LIMITING (in-memory, use Redis in production)
# ─────────────────────────────────────────────────────────────
request_history: dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
RATE_LIMIT_PER_MIN = 60

def check_rate_limit(user_id: str):
    now = time.time()
    history = request_history[user_id]
    # Remove old entries
    while history and history[0] < now - 60:
        history.popleft()
    if len(history) >= RATE_LIMIT_PER_MIN:
        raise HTTPException(429, "Rate limit exceeded")
    history.append(now)

# ─────────────────────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────────────────────
def authenticate(creds: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Validate JWT, return user info"""
    # In production: validate JWT properly
    if creds.credentials != "VALID_TOKEN":
        raise HTTPException(401, "Invalid token")
    return {"user_id": "user-123"}

# ─────────────────────────────────────────────────────────────
# ROUTING
# ─────────────────────────────────────────────────────────────
SERVICE_MAP = {
    "orders": "http://order-service:8000",
    "inventory": "http://inventory-service:8001",
    "payments": "http://payment-service:8002",
}

@app.api_route("/api/{service}/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy(service: str, path: str, request: Request, user=Depends(authenticate)):
    # Rate limit check
    check_rate_limit(user["user_id"])
    
    # Route to correct service
    if service not in SERVICE_MAP:
        raise HTTPException(404, f"Service {service} not found")
    
    target_url = f"{SERVICE_MAP[service]}/{path}"
    
    # Forward request
    async with httpx.AsyncClient(timeout=30.0) as client:
        body = await request.body()
        response = await client.request(
            method=request.method,
            url=target_url,
            content=body,
            headers={
                **dict(request.headers),
                "X-User-Id": user["user_id"],  # Forward identity
                "X-Request-Id": request.headers.get("X-Request-Id", ""),
            }
        )
        return response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text
```

---

## 8. 🎼 Saga Pattern Implementation

### Distributed Transaction Across Services

```python
"""
saga.py - Saga pattern for "Place Order" workflow.

A saga is a sequence of local transactions with compensating
actions if any step fails.
"""
import asyncio
import httpx
from enum import Enum
from typing import Callable, List
import logging

logger = logging.getLogger(__name__)

class SagaStep:
    def __init__(
        self,
        name: str,
        action: Callable,
        compensation: Callable = None,
    ):
        self.name = name
        self.action = action
        self.compensation = compensation
        self.result = None

class Saga:
    """Orchestrator for distributed transactions"""
    
    def __init__(self, name: str):
        self.name = name
        self.steps: List[SagaStep] = []
        self.executed: List[SagaStep] = []
    
    def add_step(self, name: str, action: Callable, compensation: Callable = None):
        self.steps.append(SagaStep(name, action, compensation))
    
    async def execute(self):
        """Execute saga - rollback on failure"""
        try:
            for step in self.steps:
                logger.info(f"[SAGA:{self.name}] Executing: {step.name}")
                step.result = await step.action()
                self.executed.append(step)
                logger.info(f"[SAGA:{self.name}] ✓ {step.name}")
            return {"status": "SUCCESS", "results": [s.result for s in self.executed]}
        
        except Exception as e:
            logger.error(f"[SAGA:{self.name}] ✗ Failed at {step.name}: {e}")
            await self._compensate()
            return {"status": "FAILED", "error": str(e)}
    
    async def _compensate(self):
        """Run compensations in reverse order"""
        for step in reversed(self.executed):
            if step.compensation:
                try:
                    logger.info(f"[SAGA:{self.name}] Compensating: {step.name}")
                    await step.compensation(step.result)
                except Exception as e:
                    logger.error(f"Compensation failed for {step.name}: {e}")

# ─────────────────────────────────────────────────────────────
# USAGE
# ─────────────────────────────────────────────────────────────
async def place_order_saga(user_id: int, items: list):
    saga = Saga("place_order")
    
    async with httpx.AsyncClient() as client:
        order_id = f"ORD-{uuid.uuid4().hex[:8]}"
        
        # Step 1: Reserve inventory
        saga.add_step(
            name="reserve_inventory",
            action=lambda: client.post(
                "http://inventory-service:8001/reservations",
                json={"order_id": order_id, "items": items}
            ),
            compensation=lambda r: client.delete(
                f"http://inventory-service:8001/reservations/{order_id}"
            )
        )
        
        # Step 2: Charge payment
        saga.add_step(
            name="charge_payment",
            action=lambda: client.post(
                "http://payment-service:8002/charges",
                json={"user_id": user_id, "amount": 100, "order_id": order_id}
            ),
            compensation=lambda r: client.post(
                f"http://payment-service:8002/refunds",
                json={"transaction_id": r.json()["transaction_id"]}
            )
        )
        
        # Step 3: Create order record
        saga.add_step(
            name="create_order",
            action=lambda: client.post(
                "http://order-service:8000/orders",
                json={"order_id": order_id, "user_id": user_id, "items": items}
            ),
            # No compensation needed - if this fails, both above will be undone
        )
        
        return await saga.execute()
```

---

## 9. 🐳 Docker Compose Setup

### `docker-compose.yml`

```yaml
version: '3.8'

services:
  # ───── DATABASES ─────
  order-db:
    image: postgres:15
    environment:
      POSTGRES_USER: order_user
      POSTGRES_PASSWORD: order_pass
      POSTGRES_DB: orders
    ports: ["5432:5432"]
    volumes:
      - order_data:/var/lib/postgresql/data
  
  inventory-db:
    image: mongo:7
    environment:
      MONGO_INITDB_DATABASE: inventory
    ports: ["27017:27017"]
    volumes:
      - inventory_data:/data/db
  
  payment-db:
    image: redis:7-alpine
    ports: ["6379:6379"]
  
  # ───── MESSAGE BROKER ─────
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
  
  # ───── OBSERVABILITY ─────
  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "16686:16686"  # UI
      - "6831:6831/udp"  # Agent
  
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./infra/prometheus.yml:/etc/prometheus/prometheus.yml
    ports: ["9090:9090"]
  
  grafana:
    image: grafana/grafana:latest
    ports: ["3000:3000"]
    environment:
      GF_SECURITY_ADMIN_PASSWORD: admin
    depends_on: [prometheus]
  
  # ───── MICROSERVICES ─────
  order-service:
    build: ./services/order-service
    ports: ["8000:8000"]
    depends_on: [order-db, kafka, jaeger]
    environment:
      DATABASE_URL: postgresql://order_user:order_pass@order-db:5432/orders
      KAFKA_BROKERS: kafka:9092
      JAEGER_HOST: jaeger
  
  inventory-service:
    build: ./services/inventory-service
    ports: ["8001:8001"]
    depends_on: [inventory-db, kafka, jaeger]
  
  payment-service:
    build: ./services/payment-service
    ports: ["8002:8002"]
    depends_on: [payment-db, jaeger]
  
  api-gateway:
    build: ./api-gateway
    ports: ["8080:8080"]
    depends_on:
      - order-service
      - inventory-service
      - payment-service

volumes:
  order_data:
  inventory_data:
```

### Run Everything

```bash
$ docker-compose up -d

# Check services
$ docker-compose ps

# View logs
$ docker-compose logs -f order-service

# Hit the API
$ curl -X POST http://localhost:8080/api/orders/orders \
    -H "Authorization: Bearer VALID_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
        "user_id": 1,
        "items": [{"sku": "SKU-001", "quantity": 2}]
    }'

# View traces
$ open http://localhost:16686  # Jaeger UI

# View metrics
$ open http://localhost:3000   # Grafana
```

---

## 10. 🧪 Testing Microservices

### Contract Testing with Pact

```python
"""tests/test_order_contract.py"""
import pytest
from pact import Consumer, Provider

@pytest.fixture
def pact():
    return Consumer("order-service").has_pact_with(
        Provider("inventory-service"),
        host_name='localhost',
        port=1234
    )

def test_inventory_contract(pact):
    expected = {
        "sku": "SKU-001",
        "name": "iPhone 15",
        "stock": 50,
        "price": 79999.0
    }
    
    (pact
     .given("Product SKU-001 exists")
     .upon_receiving("A request for product SKU-001")
     .with_request("GET", "/items/SKU-001")
     .will_respond_with(200, body=expected))
    
    with pact:
        result = inventory_client.get_item("SKU-001")
        assert result == expected
```

### Integration Test

```python
"""tests/test_integration.py"""
import httpx
import pytest

@pytest.mark.asyncio
async def test_end_to_end_order_flow():
    """Test full order workflow across services"""
    async with httpx.AsyncClient() as client:
        # Place order
        response = await client.post(
            "http://localhost:8080/api/orders/orders",
            headers={"Authorization": "Bearer VALID_TOKEN"},
            json={
                "user_id": 1,
                "items": [{"sku": "SKU-001", "quantity": 1}]
            }
        )
        assert response.status_code == 201
        order = response.json()
        
        # Verify order was created
        response = await client.get(
            f"http://localhost:8080/api/orders/orders/{order['order_id']}",
            headers={"Authorization": "Bearer VALID_TOKEN"}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "CONFIRMED"
```

---

## 11. Resilience Patterns Summary

```
┌────────────────────────────────────────────────────────────────┐
│  PATTERN          │  PROBLEM IT SOLVES                          │
├───────────────────┼─────────────────────────────────────────────┤
│  Timeout          │  Hanging requests waste resources           │
│  Retry            │  Transient failures (network blips)          │
│  Circuit Breaker  │  Fail fast when downstream is dead          │
│  Bulkhead         │  Isolate resources per dependency           │
│  Rate Limiter     │  Prevent overload                           │
│  Fallback         │  Degrade gracefully                         │
│  Idempotency      │  Safe retries (no double-charge)            │
└───────────────────┴─────────────────────────────────────────────┘
```

---

## 12. Key Learnings Summary

```
✅ Microservices use REST/gRPC for sync, Kafka for async
✅ Each service has its own database
✅ Distributed tracing is non-negotiable
✅ Resilience patterns are essential (retry, circuit breaker)
✅ Saga pattern for distributed transactions
✅ Docker Compose for local dev
✅ API Gateway for routing/auth/rate limiting

🚨 Operational complexity is REAL:
   - 3 services = 3 DBs, 1 broker, 1 gateway, 1 tracing, 1 metrics
   - That's 8 components for a simple demo!
```

---

## 🎬 What's Next?

In **Lecture 3**, we'll see how to **avoid this complexity** by starting with a **Modular Monolith** and extracting services only when justified.

> **Next lecture:** [03_Modular_Monoliths_Migration.md](03_Modular_Monoliths_Migration.md)

---

## 📚 Try It Yourself

1. Add a **Notification Service** that consumes order events and sends email
2. Implement **circuit breaker** with metrics in Grafana
3. Add **shadow traffic** to test new version safely
4. Build a **Backstage service catalog** for discovery
5. Add **chaos engineering** tests (kill random pods)
