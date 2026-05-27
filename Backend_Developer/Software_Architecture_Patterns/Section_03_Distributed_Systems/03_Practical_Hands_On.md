# Lecture 3 — Practical Hands-On: Modular Monolith & Migration

> **Theory file:** [03_Modular_Monoliths_Migration.md](03_Modular_Monoliths_Migration.md)

---

## 🎯 Is Practical Mein Kya Banayenge?

A **working e-commerce modular monolith** that:

1. ✅ Has **3 bounded contexts** (Orders, Payments, Inventory)
2. ✅ Enforces **module boundaries** with `import-linter`
3. ✅ Uses **in-process event bus** (upgradeable to Kafka)
4. ✅ Has **module-owned schemas** in single database
5. ✅ Demonstrates **public vs private** API distinction
6. ✅ Has **per-module tests**
7. ✅ Shows **Strangler Fig pattern** for extraction
8. ✅ Includes **architectural tests** that verify boundaries
9. ✅ Demonstrates **branch by abstraction** for migration

By end: aap **production-ready modular monolith** likh sakte ho aur **extract karna seekh jaaoge** when needed.

---

## 1. Project Structure

```
modular_monolith/
├── pyproject.toml
├── .importlinter                  # ENFORCES boundaries!
├── docker-compose.yml
├── README.md
│
├── src/
│   ├── main.py                    # Single entry point
│   ├── shared/
│   │   ├── __init__.py
│   │   ├── database.py            # Shared DB pool
│   │   ├── events.py              # In-process event bus
│   │   └── exceptions.py
│   │
│   └── modules/
│       │
│       ├── orders/                # 📦 ORDERS MODULE
│       │   ├── __init__.py        # Exports public API
│       │   ├── api.py             # 🔓 PUBLIC HTTP routes
│       │   ├── service.py         # 🔓 PUBLIC service interface
│       │   ├── events.py          # 🔓 PUBLIC events published
│       │   ├── _internal/         # 🔒 PRIVATE (underscore!)
│       │   │   ├── __init__.py
│       │   │   ├── domain.py
│       │   │   ├── repository.py
│       │   │   └── policies.py
│       │   └── tests/
│       │
│       ├── payments/              # 💳 PAYMENTS MODULE
│       │   ├── api.py             # 🔓 PUBLIC
│       │   ├── service.py         # 🔓 PUBLIC
│       │   ├── events.py
│       │   ├── _internal/         # 🔒 PRIVATE
│       │   └── tests/
│       │
│       └── inventory/             # 📋 INVENTORY MODULE
│           ├── api.py
│           ├── service.py
│           ├── events.py
│           ├── _internal/
│           └── tests/
│
└── tests/
    ├── architectural/             # Verifies boundaries!
    │   └── test_module_boundaries.py
    └── integration/
        └── test_module_interactions.py
```

---

## 2. Setup & Dependencies

```bash
pip install fastapi uvicorn
pip install sqlalchemy asyncpg
pip install pydantic
pip install import-linter            # KEY: enforces module boundaries
pip install pytest pytest-asyncio
```

### `pyproject.toml`

```toml
[project]
name = "modular-monolith"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "fastapi>=0.104",
    "uvicorn>=0.24",
    "sqlalchemy>=2.0",
    "asyncpg>=0.29",
    "pydantic>=2.0",
]

[project.optional-dependencies]
dev = ["import-linter>=2.0", "pytest>=7.4", "pytest-asyncio>=0.21"]
```

---

## 3. 🔒 Enforce Module Boundaries with import-linter

### `.importlinter` Configuration

```ini
[importlinter]
root_package = src

[importlinter:contract:modules-isolated]
name = Modules cannot reach into each other's internals
type = forbidden
source_modules =
    src.modules.orders
    src.modules.payments
    src.modules.inventory
forbidden_modules =
    src.modules.orders._internal
    src.modules.payments._internal
    src.modules.inventory._internal
ignore_imports =
    # Allow each module to use its own internals
    src.modules.orders.* -> src.modules.orders._internal.*
    src.modules.payments.* -> src.modules.payments._internal.*
    src.modules.inventory.* -> src.modules.inventory._internal.*

[importlinter:contract:no-cross-module-direct-deps]
name = Modules can only depend on shared, never directly on other modules' internals
type = layers
layers =
    src.modules.orders | src.modules.payments | src.modules.inventory
    src.shared
```

### Run the Linter

```bash
$ lint-imports

✓ Modules cannot reach into each other's internals
✓ Modules can only depend on shared

# If a violation exists:
✗ Modules cannot reach into each other's internals
  src.modules.orders.api imports forbidden src.modules.payments._internal.domain
```

### CI Integration

```yaml
# .github/workflows/architecture.yml
name: Architecture Tests
on: [push, pull_request]

jobs:
  lint-imports:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
      - run: pip install import-linter
      - run: lint-imports  # FAILS BUILD if violations exist
```

---

## 4. 📡 In-Process Event Bus (Future-Proof)

### `src/shared/events.py`

```python
"""
In-process event bus.
Today: synchronous, in-process
Tomorrow: replace internals with Kafka, no caller changes needed.
"""
import asyncio
from typing import Callable, Dict, List, Any, Awaitable
import logging

logger = logging.getLogger(__name__)

EventHandler = Callable[[dict], Awaitable[None]]

class EventBus:
    """
    Pub-sub event bus.
    
    Modules:
    - Publish events to announce state changes
    - Subscribe to events from other modules
    
    All in-process today, but designed for Kafka migration.
    """
    
    def __init__(self):
        self._handlers: Dict[str, List[EventHandler]] = {}
    
    def subscribe(self, event_type: str, handler: EventHandler):
        """Subscribe a handler to an event type"""
        self._handlers.setdefault(event_type, []).append(handler)
        logger.info(f"[EventBus] {handler.__name__} subscribed to {event_type}")
    
    async def publish(self, event_type: str, payload: dict):
        """
        Publish an event.
        TODAY: synchronous, in-process call to handlers
        TOMORROW: replace with kafka_producer.send(event_type, payload)
        Callers don't need to change!
        """
        handlers = self._handlers.get(event_type, [])
        logger.info(f"[EventBus] Publishing {event_type} to {len(handlers)} handlers")
        
        # Fire all handlers in parallel
        if handlers:
            results = await asyncio.gather(
                *[h(payload) for h in handlers],
                return_exceptions=True  # Don't let one failure kill others
            )
            for h, result in zip(handlers, results):
                if isinstance(result, Exception):
                    logger.error(f"Handler {h.__name__} failed: {result}")

# Single instance for the whole app
event_bus = EventBus()
```

---

## 5. 📦 Orders Module (Full Implementation)

### `src/modules/orders/__init__.py` (Public API)

```python
"""
Orders Module - public API.
ONLY things exported here can be used by other modules.
"""
from .service import OrderService
from .events import OrderCreated, OrderCancelled

__all__ = ["OrderService", "OrderCreated", "OrderCancelled"]
```

### `src/modules/orders/service.py` (Public Service)

```python
"""
Orders public service.
This is the ONLY interface other modules can use.
"""
from typing import Protocol
from ._internal.domain import Order
from ._internal.repository import OrderRepository
from .events import OrderCreated, OrderCancelled
from src.shared.events import event_bus

# ── Other modules' interfaces (loose coupling) ──
class PaymentService(Protocol):
    """Just the interface — payment module implements this"""
    async def charge(self, user_id: int, amount: float) -> str: ...

class InventoryService(Protocol):
    async def reserve(self, sku: str, quantity: int) -> bool: ...

class OrderService:
    """Public Order service - what other modules can call"""
    
    def __init__(
        self,
        payment_service: PaymentService,
        inventory_service: InventoryService,
    ):
        self._payment = payment_service
        self._inventory = inventory_service
        self._repo = OrderRepository()
    
    async def create_order(
        self,
        user_id: int,
        sku: str,
        quantity: int,
        amount: float,
    ) -> Order:
        """
        Create an order - coordinates with payment & inventory.
        
        Notice: We call other modules through their PUBLIC interface only.
        We never reach into _internal/.
        """
        # 1. Reserve inventory
        reserved = await self._inventory.reserve(sku, quantity)
        if not reserved:
            raise ValueError("Insufficient stock")
        
        # 2. Process payment
        txn_id = await self._payment.charge(user_id, amount)
        
        # 3. Create order
        order = Order.create(user_id=user_id, sku=sku, quantity=quantity, total=amount)
        await self._repo.save(order)
        
        # 4. Publish event (other modules can react)
        await event_bus.publish("order.created", {
            "order_id": order.id,
            "user_id": user_id,
            "sku": sku,
            "amount": amount,
        })
        
        return order
    
    async def cancel_order(self, order_id: str) -> None:
        order = await self._repo.get(order_id)
        if not order:
            raise ValueError("Order not found")
        
        order.cancel()
        await self._repo.save(order)
        
        await event_bus.publish("order.cancelled", {
            "order_id": order_id,
            "sku": order.sku,
            "quantity": order.quantity,
        })
    
    async def get_order(self, order_id: str) -> Order:
        return await self._repo.get(order_id)
```

### `src/modules/orders/api.py` (HTTP Layer)

```python
"""HTTP API for Orders module"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from .service import OrderService
from .._dependencies import get_order_service  # Composition root

router = APIRouter(prefix="/orders", tags=["orders"])

class CreateOrderRequest(BaseModel):
    user_id: int
    sku: str
    quantity: int
    amount: float

class OrderResponse(BaseModel):
    order_id: str
    user_id: int
    status: str
    total: float

@router.post("", response_model=OrderResponse, status_code=201)
async def create_order(
    req: CreateOrderRequest,
    service: OrderService = Depends(get_order_service),
):
    try:
        order = await service.create_order(
            user_id=req.user_id,
            sku=req.sku,
            quantity=req.quantity,
            amount=req.amount,
        )
        return OrderResponse(
            order_id=order.id,
            user_id=order.user_id,
            status=order.status,
            total=order.total,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: str,
    service: OrderService = Depends(get_order_service),
):
    order = await service.get_order(order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    return OrderResponse(
        order_id=order.id,
        user_id=order.user_id,
        status=order.status,
        total=order.total,
    )
```

### `src/modules/orders/_internal/domain.py` (PRIVATE)

```python
"""
PRIVATE domain logic.
The underscore in _internal makes this module-private.
Other modules CANNOT import from here.
"""
import uuid
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Order:
    id: str
    user_id: int
    sku: str
    quantity: int
    total: float
    status: str
    created_at: datetime
    
    @classmethod
    def create(cls, user_id: int, sku: str, quantity: int, total: float) -> 'Order':
        return cls(
            id=f"ORD-{uuid.uuid4().hex[:8].upper()}",
            user_id=user_id,
            sku=sku,
            quantity=quantity,
            total=total,
            status="CONFIRMED",
            created_at=datetime.utcnow(),
        )
    
    def cancel(self):
        if self.status == "CANCELLED":
            raise ValueError("Already cancelled")
        self.status = "CANCELLED"
```

### `src/modules/orders/_internal/repository.py` (PRIVATE)

```python
"""PRIVATE - Database access for orders module"""
import asyncpg
from typing import Optional
from .domain import Order
from src.shared.database import get_pool

class OrderRepository:
    SCHEMA = "orders"  # Module-owned schema!
    
    async def save(self, order: Order) -> None:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(f"""
                INSERT INTO {self.SCHEMA}.orders
                    (id, user_id, sku, quantity, total, status, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (id) DO UPDATE
                    SET status = EXCLUDED.status
            """, order.id, order.user_id, order.sku, order.quantity,
                order.total, order.status, order.created_at)
    
    async def get(self, order_id: str) -> Optional[Order]:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(f"""
                SELECT * FROM {self.SCHEMA}.orders WHERE id = $1
            """, order_id)
            if not row:
                return None
            return Order(
                id=row["id"],
                user_id=row["user_id"],
                sku=row["sku"],
                quantity=row["quantity"],
                total=float(row["total"]),
                status=row["status"],
                created_at=row["created_at"],
            )
```

### `src/modules/orders/events.py` (PUBLIC Event Schemas)

```python
"""Events that the Orders module publishes"""
from pydantic import BaseModel

class OrderCreated(BaseModel):
    order_id: str
    user_id: int
    sku: str
    amount: float

class OrderCancelled(BaseModel):
    order_id: str
    sku: str
    quantity: int
```

---

## 6. 💳 Payments Module

### `src/modules/payments/service.py`

```python
"""Payments public service"""
import uuid
from ._internal.gateway import PaymentGateway
from ._internal.repository import PaymentRepository

class PaymentService:
    """Public Payment service"""
    
    def __init__(self):
        self._gateway = PaymentGateway()
        self._repo = PaymentRepository()
    
    async def charge(self, user_id: int, amount: float) -> str:
        """Charge a customer - returns transaction_id"""
        txn_id = f"TXN-{uuid.uuid4().hex[:10].upper()}"
        
        # Call gateway
        success = await self._gateway.charge(user_id, amount)
        if not success:
            raise ValueError("Payment failed")
        
        # Save record
        await self._repo.save({
            "txn_id": txn_id,
            "user_id": user_id,
            "amount": amount,
            "status": "SUCCESS",
        })
        
        return txn_id
    
    async def refund(self, txn_id: str) -> None:
        """Refund a transaction"""
        await self._gateway.refund(txn_id)
        await self._repo.mark_refunded(txn_id)
```

### `src/modules/payments/_internal/gateway.py`

```python
"""PRIVATE - External payment gateway integration"""
import random
import asyncio

class PaymentGateway:
    async def charge(self, user_id: int, amount: float) -> bool:
        await asyncio.sleep(0.1)  # Simulate API call
        # In real: call Stripe/Razorpay
        return random.random() > 0.05  # 95% success rate
    
    async def refund(self, txn_id: str) -> None:
        await asyncio.sleep(0.1)
        # In real: call refund API
```

---

## 7. 📋 Inventory Module (with Event Subscription)

### `src/modules/inventory/service.py`

```python
"""Inventory public service - also subscribes to order events!"""
from ._internal.repository import InventoryRepository
from src.shared.events import event_bus

class InventoryService:
    def __init__(self):
        self._repo = InventoryRepository()
        # Subscribe to order events
        event_bus.subscribe("order.cancelled", self._on_order_cancelled)
    
    async def reserve(self, sku: str, quantity: int) -> bool:
        """Reserve stock for an order"""
        product = await self._repo.get(sku)
        if not product or product.stock < quantity:
            return False
        product.stock -= quantity
        await self._repo.save(product)
        return True
    
    async def _on_order_cancelled(self, payload: dict):
        """React to order cancellation - release stock"""
        sku = payload["sku"]
        quantity = payload["quantity"]
        product = await self._repo.get(sku)
        if product:
            product.stock += quantity
            await self._repo.save(product)
            print(f"[Inventory] Released {quantity} of {sku} after cancellation")
```

---

## 8. 🎯 Composition Root

### `src/modules/_dependencies.py`

```python
"""
Composition root - where dependencies are wired together.
This is the ONE place where modules know about each other.
"""
from functools import lru_cache
from src.modules.orders.service import OrderService
from src.modules.payments.service import PaymentService
from src.modules.inventory.service import InventoryService

@lru_cache
def get_payment_service() -> PaymentService:
    return PaymentService()

@lru_cache
def get_inventory_service() -> InventoryService:
    return InventoryService()

@lru_cache
def get_order_service() -> OrderService:
    return OrderService(
        payment_service=get_payment_service(),
        inventory_service=get_inventory_service(),
    )
```

### `src/main.py`

```python
"""Application entry point"""
from fastapi import FastAPI
from src.modules.orders.api import router as orders_router
from src.modules.payments.api import router as payments_router
from src.modules.inventory.api import router as inventory_router
from src.shared.database import init_db

app = FastAPI(title="Modular Monolith Demo")

@app.on_event("startup")
async def startup():
    await init_db()

app.include_router(orders_router)
app.include_router(payments_router)
app.include_router(inventory_router)

@app.get("/health")
def health():
    return {"status": "healthy"}
```

---

## 9. 🧪 Architectural Tests

### `tests/architectural/test_module_boundaries.py`

```python
"""
Verify module boundaries with code.
These tests RUN in CI and FAIL the build if boundaries are violated.
"""
import subprocess
import pytest
import ast
from pathlib import Path

def test_import_linter_passes():
    """Run import-linter to verify boundaries"""
    result = subprocess.run(
        ["lint-imports"],
        capture_output=True, text=True
    )
    assert result.returncode == 0, f"Module boundaries violated:\n{result.stdout}"

def test_no_cross_module_internal_imports():
    """No module imports another module's _internal"""
    forbidden_imports = []
    
    for py_file in Path("src/modules").rglob("*.py"):
        with open(py_file) as f:
            tree = ast.parse(f.read())
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                # Detect imports like: from src.modules.X._internal import ...
                if node.module and "_internal" in node.module:
                    # Check if it's importing from a DIFFERENT module
                    current_module = py_file.relative_to("src/modules").parts[0]
                    if not node.module.startswith(f"src.modules.{current_module}"):
                        forbidden_imports.append(f"{py_file}: {node.module}")
    
    assert not forbidden_imports, f"Forbidden cross-module internal imports:\n" + "\n".join(forbidden_imports)

def test_each_module_has_public_api():
    """Each module must have api.py and service.py"""
    modules_dir = Path("src/modules")
    for module_dir in modules_dir.iterdir():
        if module_dir.is_dir() and not module_dir.name.startswith("_"):
            assert (module_dir / "api.py").exists(), f"Module {module_dir.name} missing api.py"
            assert (module_dir / "service.py").exists(), f"Module {module_dir.name} missing service.py"
```

---

## 10. 🌳 Strangler Fig: Extracting Payments Service

### Step 1: Define the Abstraction

```python
# src/modules/orders/service.py
from typing import Protocol

class PaymentService(Protocol):
    """The contract — both in-monolith and remote impl follow this"""
    async def charge(self, user_id: int, amount: float) -> str: ...
    async def refund(self, txn_id: str) -> None: ...
```

### Step 2: Two Implementations

```python
# In-monolith implementation (current)
from src.modules.payments.service import PaymentService as InMonolithPayment

# Remote implementation (new microservice)
import httpx

class RemotePaymentService:
    """Same interface, different transport"""
    
    def __init__(self, base_url: str):
        self._base_url = base_url
    
    async def charge(self, user_id: int, amount: float) -> str:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"{self._base_url}/charge",
                json={"user_id": user_id, "amount": amount}
            )
            response.raise_for_status()
            return response.json()["txn_id"]
    
    async def refund(self, txn_id: str) -> None:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(f"{self._base_url}/refund", json={"txn_id": txn_id})
```

### Step 3: Hybrid Routing with Feature Flag

```python
"""
Hybrid service - routes traffic between old and new based on feature flag.
This is the STRANGLER FIG in action.
"""
import random
import logging

class HybridPaymentService:
    """
    Route some traffic to new service, rest to monolith.
    Gradually increase % until 100% on new service.
    """
    
    def __init__(
        self,
        in_monolith: PaymentService,
        remote: RemotePaymentService,
        traffic_pct_to_remote: int = 10,
    ):
        self._in_monolith = in_monolith
        self._remote = remote
        self._traffic_pct = traffic_pct_to_remote
    
    async def charge(self, user_id: int, amount: float) -> str:
        # Route % of traffic to new service
        use_remote = random.randint(1, 100) <= self._traffic_pct
        
        if use_remote:
            try:
                txn_id = await self._remote.charge(user_id, amount)
                logging.info(f"[REMOTE] Charged successfully")
                return txn_id
            except Exception as e:
                logging.error(f"[REMOTE] Failed: {e}, falling back to monolith")
                return await self._in_monolith.charge(user_id, amount)
        else:
            return await self._in_monolith.charge(user_id, amount)
    
    async def refund(self, txn_id: str) -> None:
        # Use whichever processed the original
        if txn_id.startswith("REM-"):
            await self._remote.refund(txn_id)
        else:
            await self._in_monolith.refund(txn_id)
```

### Step 4: Shadow Mode (Optional, Safer)

```python
class ShadowPaymentService:
    """
    Call BOTH services, but only use monolith's result.
    Useful for comparing results before switching.
    """
    
    async def charge(self, user_id: int, amount: float) -> str:
        # Primary: monolith
        result_main = await self._in_monolith.charge(user_id, amount)
        
        # Shadow: call new service, don't use result
        try:
            result_shadow = await self._remote.charge(user_id, amount)
            if result_shadow != result_main:
                logging.warning(f"[SHADOW] Results differ: {result_main} vs {result_shadow}")
        except Exception as e:
            logging.error(f"[SHADOW] New service error: {e}")
        
        return result_main
```

### Step 5: Migration Timeline

```
Week 1: Deploy with 0% traffic to remote (shadow mode)
        → Verify behavior matches

Week 2: 1% traffic to remote
        → Monitor errors, latency

Week 3: 10% traffic
Week 4: 25% traffic
Week 5: 50% traffic
Week 6: 75% traffic
Week 7: 100% traffic
Week 8: Remove in-monolith implementation
```

### Configuration via Feature Flag

```python
# src/shared/feature_flags.py
import os

def get_payment_remote_traffic_pct() -> int:
    """Read from env, defaults to 0 (safe)"""
    return int(os.getenv("PAYMENT_REMOTE_TRAFFIC_PCT", "0"))

# In composition root:
def get_order_service() -> OrderService:
    in_monolith = InMonolithPayment()
    remote = RemotePaymentService("http://payment-service:8000")
    
    payment_service = HybridPaymentService(
        in_monolith=in_monolith,
        remote=remote,
        traffic_pct_to_remote=get_payment_remote_traffic_pct(),
    )
    
    return OrderService(
        payment_service=payment_service,
        inventory_service=get_inventory_service(),
    )
```

---

## 11. 🧪 Integration Tests

### `tests/integration/test_order_flow.py`

```python
"""Test the modular monolith end-to-end"""
import pytest
from httpx import AsyncClient
from src.main import app

@pytest.mark.asyncio
async def test_full_order_flow():
    """Create an order, verify other modules reacted"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # 1. Create order
        response = await client.post("/orders", json={
            "user_id": 1,
            "sku": "SKU-001",
            "quantity": 2,
            "amount": 199.99,
        })
        assert response.status_code == 201
        order = response.json()
        
        # 2. Verify order created
        response = await client.get(f"/orders/{order['order_id']}")
        assert response.json()["status"] == "CONFIRMED"
        
        # 3. Verify inventory was decremented
        response = await client.get("/inventory/SKU-001")
        # ... assertion ...
        
        # 4. Verify payment was charged
        # ... check payment records ...
```

---

## 12. 🚀 Running the Monolith

### `docker-compose.yml`

```yaml
version: '3.8'

services:
  db:
    image: postgres:15
    environment:
      POSTGRES_USER: app
      POSTGRES_PASSWORD: app
      POSTGRES_DB: monolith
    ports: ["5432:5432"]
    volumes:
      - ./schemas.sql:/docker-entrypoint-initdb.d/schemas.sql
  
  app:
    build: .
    ports: ["8000:8000"]
    environment:
      DATABASE_URL: postgresql://app:app@db:5432/monolith
      PAYMENT_REMOTE_TRAFFIC_PCT: "0"  # Start with 0 (safe)
    depends_on: [db]
```

### `schemas.sql`

```sql
-- Each module gets its own schema!
CREATE SCHEMA orders;
CREATE SCHEMA payments;
CREATE SCHEMA inventory;

-- Orders module tables
CREATE TABLE orders.orders (
    id VARCHAR PRIMARY KEY,
    user_id INTEGER NOT NULL,
    sku VARCHAR NOT NULL,
    quantity INTEGER NOT NULL,
    total NUMERIC NOT NULL,
    status VARCHAR NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

-- Payments module tables
CREATE TABLE payments.transactions (
    txn_id VARCHAR PRIMARY KEY,
    user_id INTEGER NOT NULL,
    amount NUMERIC NOT NULL,
    status VARCHAR NOT NULL
);

-- Inventory module tables
CREATE TABLE inventory.products (
    sku VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    stock INTEGER NOT NULL,
    price NUMERIC NOT NULL
);

INSERT INTO inventory.products VALUES
    ('SKU-001', 'iPhone 15', 100, 79999.0),
    ('SKU-002', 'MacBook Pro', 50, 199999.0);
```

### Run It

```bash
$ docker-compose up -d

# In another terminal
$ curl http://localhost:8000/health
{"status": "healthy"}

$ curl -X POST http://localhost:8000/orders \
    -H "Content-Type: application/json" \
    -d '{"user_id": 1, "sku": "SKU-001", "quantity": 1, "amount": 79999.0}'

# Run architecture tests
$ pytest tests/architectural/
$ lint-imports
```

---

## 13. 📊 Module Extraction Decision Helper

### Script: `tools/extraction_readiness.py`

```python
"""
Check if a module is ready to extract as microservice.
Runs the 8-point checklist programmatically.
"""
import ast
from pathlib import Path

def check_module_readiness(module_name: str) -> dict:
    """Returns checklist scores"""
    module_path = Path(f"src/modules/{module_name}")
    
    checks = {
        "has_public_api": (module_path / "api.py").exists(),
        "has_service_interface": (module_path / "service.py").exists(),
        "has_internal_folder": (module_path / "_internal").exists(),
        "has_tests": (module_path / "tests").exists(),
        "no_cross_module_internal_imports": _check_no_internal_imports(module_path),
        "owns_db_schema": _check_owns_schema(module_name),
        "publishes_events": (module_path / "events.py").exists(),
        "tests_pass": _run_tests(module_name),
    }
    
    score = sum(checks.values())
    return {
        "module": module_name,
        "score": f"{score}/8",
        "checks": checks,
        "ready_to_extract": score >= 7,
    }

# Usage:
if __name__ == "__main__":
    for module in ["orders", "payments", "inventory"]:
        result = check_module_readiness(module)
        print(f"\n{module}: {result['score']}")
        for check, passed in result["checks"].items():
            print(f"  {'✓' if passed else '✗'} {check}")
```

```bash
$ python tools/extraction_readiness.py

orders: 8/8
  ✓ has_public_api
  ✓ has_service_interface
  ✓ has_internal_folder
  ✓ has_tests
  ✓ no_cross_module_internal_imports
  ✓ owns_db_schema
  ✓ publishes_events
  ✓ tests_pass

→ Orders is READY to extract!

payments: 6/8
  ✓ has_public_api
  ✓ has_service_interface
  ✓ has_internal_folder
  ✓ has_tests
  ✗ no_cross_module_internal_imports  ← FIX FIRST!
  ✓ owns_db_schema
  ✓ publishes_events
  ✗ tests_pass

→ Payments needs work before extraction
```

---

## 14. Key Learnings Summary

```
✅ Modular monolith = structure WITHOUT distribution tax
✅ Underscore convention for private code (_internal/)
✅ Each module owns its schema in shared DB
✅ Cross-module communication via public service interface
✅ Event bus enables loose coupling
✅ import-linter enforces boundaries in CI
✅ Strangler fig + feature flags = safe extraction
✅ Hybrid implementations route traffic gradually

🎯 The pattern lets you:
   1. Start fast (modular monolith)
   2. Learn the domain
   3. Extract microservices WHEN justified
   4. Without rewriting from scratch
```

---

## 🎬 What's Next?

In **Lecture 4**, we'll apply these ideas to the **frontend** — building **micro-frontends** that compose into a unified UI while remaining independently developed.

> **Next lecture:** [04_Micro_Frontends_UI_Composition.md](04_Micro_Frontends_UI_Composition.md)

---

## 📚 Try It Yourself

1. Add a **Notifications module** that subscribes to `order.created`
2. Implement **outbox pattern** for guaranteed event delivery
3. Build the **payment-service microservice** for Strangler Fig demo
4. Add **module-level metrics** (Prometheus per module)
5. Write **mutation tests** to verify module isolation
