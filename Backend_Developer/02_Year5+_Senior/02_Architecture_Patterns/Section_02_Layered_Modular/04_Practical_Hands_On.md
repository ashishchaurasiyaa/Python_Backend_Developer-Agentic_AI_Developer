# Lecture 4 — Practical Hands-On: Building a Modular Monolith

> **Theory file:** [04_Applying_Modular_Architectures.md](04_Applying_Modular_Architectures.md)

---

## 🎯 Is Practical Mein Kya Banayenge?

Ek **fully-working e-commerce modular monolith** with:

1. ✅ **3 bounded contexts** (Orders, Payments, Inventory)
2. ✅ **Public vs Internal API** distinction enforced
3. ✅ **Event-based communication** between modules
4. ✅ **Per-module structure** (each module = mini app)
5. ✅ **Architectural tests** in Python (`import-linter`)
6. ✅ **Strangler pattern** migration example
7. ✅ **Anti-corruption layer** for legacy integration
8. ✅ **Per-module CI/CD pipeline** in GitHub Actions

By end: aap **production-grade modular monolith** likh sakte ho.

---

## 1. Project Structure

### Folder Layout

```
modular_monolith/
├── pyproject.toml
├── .importlinter                  # Enforce module boundaries!
├── docker-compose.yml
├── README.md
├── .github/
│   └── workflows/
│       ├── orders-ci.yml          # Per-module CI
│       ├── payments-ci.yml
│       └── inventory-ci.yml
│
├── src/
│   ├── main.py                    # Single entry point
│   ├── shared/                    # Cross-module shared (be careful!)
│   │   ├── __init__.py
│   │   ├── events.py              # Event bus
│   │   ├── database.py            # Shared DB connection
│   │   └── exceptions.py          # Base exceptions
│   │
│   └── modules/                   # 🎯 THE MODULES
│       │
│       ├── orders/                # 📦 ORDERS MODULE
│       │   ├── __init__.py
│       │   ├── api.py             # 🔓 PUBLIC API
│       │   ├── events.py          # 📡 Events this module publishes
│       │   ├── _internal/         # 🔒 PRIVATE (underscore convention)
│       │   │   ├── domain.py
│       │   │   ├── services.py
│       │   │   ├── repository.py
│       │   │   └── controllers.py
│       │   └── tests/
│       │
│       ├── payments/              # 💳 PAYMENTS MODULE
│       │   ├── __init__.py
│       │   ├── api.py             # 🔓 PUBLIC API
│       │   ├── events.py
│       │   ├── _internal/         # 🔒 PRIVATE
│       │   │   ├── domain.py
│       │   │   ├── services.py
│       │   │   ├── repository.py
│       │   │   └── controllers.py
│       │   └── tests/
│       │
│       └── inventory/             # 📋 INVENTORY MODULE
│           ├── __init__.py
│           ├── api.py             # 🔓 PUBLIC API
│           ├── events.py
│           ├── _internal/         # 🔒 PRIVATE
│           │   ├── domain.py
│           │   ├── services.py
│           │   ├── repository.py
│           │   └── controllers.py
│           └── tests/
│
└── tests/
    ├── architectural/             # Tests that verify architecture!
    │   └── test_module_boundaries.py
    └── integration/
        └── test_module_interactions.py
```

> **Key Insight:** Each module is **self-contained**. Public API in `api.py`, internals in `_internal/`.

---

## 2. 📦 Orders Module — Full Implementation

### Public API (`api.py`)

```python
# src/modules/orders/api.py
"""
🔓 PUBLIC API of Orders Module.
This is what OTHER modules can import.
Everything else is INTERNAL.
"""
from typing import Optional
from dataclasses import dataclass
from uuid import UUID

# Import only from _internal — never expose internals directly
from src.modules.orders._internal.services import OrderService
from src.modules.orders._internal.repository import OrderRepository
from src.shared.database import get_db_session


@dataclass
class OrderDTO:
    """Public DTO — what other modules see."""
    id: str
    customer_id: int
    total_amount: float
    status: str


@dataclass
class CreateOrderRequest:
    customer_id: int
    items: list  # [{"product_id": int, "quantity": int, "price": float}]


class OrdersAPI:
    """
    🔓 PUBLIC INTERFACE — other modules use this.
    They never see what's inside.
    """
    
    @staticmethod
    def create_order(request: CreateOrderRequest) -> OrderDTO:
        """Create a new order."""
        session = get_db_session()
        service = OrderService(OrderRepository(session))
        order = service.create_order(
            customer_id=request.customer_id,
            items=request.items,
        )
        return OrderDTO(
            id=str(order.id),
            customer_id=order.customer_id,
            total_amount=float(order.total),
            status=order.status,
        )
    
    @staticmethod
    def get_order(order_id: str) -> Optional[OrderDTO]:
        session = get_db_session()
        service = OrderService(OrderRepository(session))
        order = service.get_order(UUID(order_id))
        if not order:
            return None
        return OrderDTO(
            id=str(order.id),
            customer_id=order.customer_id,
            total_amount=float(order.total),
            status=order.status,
        )
    
    @staticmethod
    def confirm_order(order_id: str, payment_id: str) -> bool:
        session = get_db_session()
        service = OrderService(OrderRepository(session))
        return service.confirm_order(UUID(order_id), payment_id)
```

### Events (`events.py`)

```python
# src/modules/orders/events.py
"""
📡 Events Orders Module PUBLISHES.
Other modules can subscribe to these.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import List


@dataclass
class OrderCreatedEvent:
    """Published when a new order is created."""
    order_id: str
    customer_id: int
    items: List[dict]
    total_amount: float
    created_at: datetime


@dataclass
class OrderConfirmedEvent:
    """Published when an order is confirmed (payment success)."""
    order_id: str
    customer_id: int
    payment_id: str
    confirmed_at: datetime


@dataclass
class OrderCancelledEvent:
    """Published when an order is cancelled."""
    order_id: str
    customer_id: int
    reason: str
    cancelled_at: datetime
```

### Internal Domain (`_internal/domain.py`)

```python
# src/modules/orders/_internal/domain.py
"""
🔒 INTERNAL — only Orders module sees this.
Other modules CANNOT import from here.
"""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import List
from uuid import UUID, uuid4


class OrderStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


@dataclass
class OrderItem:
    product_id: int
    quantity: int
    price: Decimal


@dataclass
class Order:
    """Orders module's domain entity — INTERNAL."""
    id: UUID
    customer_id: int
    items: List[OrderItem]
    status: OrderStatus
    total: Decimal
    payment_id: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    @classmethod
    def create(cls, customer_id: int, items: List[OrderItem]) -> "Order":
        if not items:
            raise ValueError("Order must have items")
        total = sum((item.price * item.quantity for item in items), Decimal("0"))
        return cls(
            id=uuid4(),
            customer_id=customer_id,
            items=items,
            status=OrderStatus.PENDING,
            total=total,
        )
    
    def confirm(self, payment_id: str) -> None:
        if self.status != OrderStatus.PENDING:
            raise ValueError(f"Cannot confirm in status {self.status}")
        self.status = OrderStatus.CONFIRMED
        self.payment_id = payment_id
```

### Internal Services (`_internal/services.py`)

```python
# src/modules/orders/_internal/services.py
"""
🔒 INTERNAL service logic.
"""
from typing import Optional, List
from decimal import Decimal
from uuid import UUID

from src.modules.orders._internal.domain import Order, OrderItem, OrderStatus
from src.modules.orders._internal.repository import OrderRepository
from src.modules.orders.events import OrderCreatedEvent, OrderConfirmedEvent
from src.shared.events import EventBus


class OrderService:
    """Orchestrates Order business logic."""
    
    def __init__(self, repo: OrderRepository):
        self.repo = repo
        self.event_bus = EventBus.instance()
    
    def create_order(self, customer_id: int, items: List[dict]) -> Order:
        # Build items as domain objects
        domain_items = [
            OrderItem(
                product_id=item["product_id"],
                quantity=item["quantity"],
                price=Decimal(str(item["price"])),
            )
            for item in items
        ]
        
        # Create order via domain factory
        order = Order.create(customer_id, domain_items)
        
        # Persist
        self.repo.save(order)
        
        # Publish event — other modules can react!
        self.event_bus.publish(OrderCreatedEvent(
            order_id=str(order.id),
            customer_id=order.customer_id,
            items=items,
            total_amount=float(order.total),
            created_at=order.created_at,
        ))
        
        return order
    
    def get_order(self, order_id: UUID) -> Optional[Order]:
        return self.repo.get(order_id)
    
    def confirm_order(self, order_id: UUID, payment_id: str) -> bool:
        order = self.repo.get(order_id)
        if not order:
            return False
        
        order.confirm(payment_id)
        self.repo.save(order)
        
        # Publish confirmation event
        from datetime import datetime
        self.event_bus.publish(OrderConfirmedEvent(
            order_id=str(order.id),
            customer_id=order.customer_id,
            payment_id=payment_id,
            confirmed_at=datetime.utcnow(),
        ))
        
        return True
```

### Internal Repository (`_internal/repository.py`)

```python
# src/modules/orders/_internal/repository.py
"""
🔒 INTERNAL persistence.
"""
from typing import Optional
from uuid import UUID
from sqlalchemy import Column, String, Integer, JSON, DateTime, create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from datetime import datetime
from decimal import Decimal

from src.modules.orders._internal.domain import Order, OrderItem, OrderStatus
from src.shared.database import Base


class OrderModel(Base):
    """SQLAlchemy model — INTERNAL to orders module."""
    __tablename__ = "orders_orders"  # Module prefix!
    
    id = Column(PgUUID(as_uuid=True), primary_key=True)
    customer_id = Column(Integer, nullable=False, index=True)
    status = Column(String, nullable=False)
    items = Column(JSON, nullable=False)
    total = Column(String, nullable=False)
    payment_id = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class OrderRepository:
    """🔒 INTERNAL repository."""
    
    def __init__(self, session):
        self.session = session
    
    def save(self, order: Order) -> None:
        model = OrderModel(
            id=order.id,
            customer_id=order.customer_id,
            status=order.status.value,
            items=[
                {"product_id": i.product_id, "quantity": i.quantity, "price": str(i.price)}
                for i in order.items
            ],
            total=str(order.total),
            payment_id=order.payment_id,
            created_at=order.created_at,
        )
        self.session.merge(model)
        self.session.flush()
    
    def get(self, order_id: UUID) -> Optional[Order]:
        model = self.session.query(OrderModel).filter_by(id=order_id).first()
        if not model:
            return None
        return Order(
            id=model.id,
            customer_id=model.customer_id,
            items=[
                OrderItem(
                    product_id=i["product_id"],
                    quantity=i["quantity"],
                    price=Decimal(i["price"]),
                )
                for i in model.items
            ],
            status=OrderStatus(model.status),
            total=Decimal(model.total),
            payment_id=model.payment_id,
            created_at=model.created_at,
        )
```

### Internal Controllers (`_internal/controllers.py`)

```python
# src/modules/orders/_internal/controllers.py
"""
🔒 INTERNAL — HTTP endpoints for this module.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List

from src.modules.orders.api import OrdersAPI, CreateOrderRequest


router = APIRouter(prefix="/orders", tags=["Orders"])


class OrderItemSchema(BaseModel):
    product_id: int
    quantity: int
    price: float


class CreateOrderSchema(BaseModel):
    customer_id: int
    items: List[OrderItemSchema]


@router.post("")
def create_order(req: CreateOrderSchema):
    try:
        result = OrdersAPI.create_order(CreateOrderRequest(
            customer_id=req.customer_id,
            items=[i.dict() for i in req.items],
        ))
        return result.__dict__
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/{order_id}")
def get_order(order_id: str):
    order = OrdersAPI.get_order(order_id)
    if not order:
        raise HTTPException(404, "Not found")
    return order.__dict__
```

---

## 3. 💳 Payments Module (Brief)

```python
# src/modules/payments/api.py
"""🔓 PUBLIC API of Payments Module."""
from dataclasses import dataclass

from src.modules.payments._internal.services import PaymentService


@dataclass
class ChargeRequest:
    customer_id: int
    order_id: str
    amount: float


@dataclass
class PaymentDTO:
    id: str
    order_id: str
    status: str
    amount: float


class PaymentsAPI:
    @staticmethod
    def charge(request: ChargeRequest) -> PaymentDTO:
        service = PaymentService()
        return service.charge(request)
```

```python
# src/modules/payments/_internal/services.py
"""🔒 INTERNAL — Payment service that reacts to Orders events."""
from uuid import uuid4
from datetime import datetime

from src.shared.events import EventBus
from src.modules.payments.events import PaymentSucceededEvent, PaymentFailedEvent
from src.modules.orders.events import OrderCreatedEvent  # Subscribe to Orders module


class PaymentService:
    def __init__(self):
        self.event_bus = EventBus.instance()
    
    def charge(self, request):
        from src.modules.payments.api import PaymentDTO
        # Simulate payment
        payment_id = str(uuid4())
        
        self.event_bus.publish(PaymentSucceededEvent(
            payment_id=payment_id,
            order_id=request.order_id,
            amount=request.amount,
            succeeded_at=datetime.utcnow(),
        ))
        
        return PaymentDTO(
            id=payment_id,
            order_id=request.order_id,
            status="succeeded",
            amount=request.amount,
        )


# Register event handler at module init
def handle_order_created(event: OrderCreatedEvent):
    """When order is created → auto-charge!"""
    from src.modules.payments.api import PaymentsAPI, ChargeRequest
    PaymentsAPI.charge(ChargeRequest(
        customer_id=event.customer_id,
        order_id=event.order_id,
        amount=event.total_amount,
    ))


# Subscribe at module load
EventBus.instance().subscribe(OrderCreatedEvent, handle_order_created)
```

---

## 4. 📋 Inventory Module (Brief)

```python
# src/modules/inventory/api.py
"""🔓 PUBLIC API of Inventory Module."""
from dataclasses import dataclass


@dataclass
class StockCheckRequest:
    product_id: int
    quantity: int


@dataclass
class StockCheckResponse:
    is_available: bool
    current_stock: int


class InventoryAPI:
    @staticmethod
    def check_stock(req: StockCheckRequest) -> StockCheckResponse:
        from src.modules.inventory._internal.services import InventoryService
        return InventoryService().check_stock(req)


# Event handler — react to OrderConfirmed
from src.shared.events import EventBus
from src.modules.orders.events import OrderConfirmedEvent
from src.modules.inventory._internal.services import InventoryService


def handle_order_confirmed(event: OrderConfirmedEvent):
    """When order confirmed → reduce inventory."""
    InventoryService().reserve_stock_for_order(event.order_id)


EventBus.instance().subscribe(OrderConfirmedEvent, handle_order_confirmed)
```

---

## 5. 🔄 Event Bus (Cross-Module Communication)

```python
# src/shared/events.py
"""
📡 In-process event bus for inter-module communication.
"""
from typing import Callable, Dict, List, Type
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class EventBus:
    """
    Singleton event bus.
    Modules subscribe to events; other modules publish them.
    No direct coupling!
    """
    _instance = None
    
    def __init__(self):
        self._handlers: Dict[Type, List[Callable]] = defaultdict(list)
    
    @classmethod
    def instance(cls) -> "EventBus":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def subscribe(self, event_type: Type, handler: Callable):
        """Register a handler for an event."""
        self._handlers[event_type].append(handler)
        logger.info(f"Subscribed {handler.__name__} to {event_type.__name__}")
    
    def publish(self, event):
        """Publish an event to all subscribers."""
        event_type = type(event)
        handlers = self._handlers.get(event_type, [])
        logger.info(f"Publishing {event_type.__name__} to {len(handlers)} handler(s)")
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.exception(f"Handler {handler.__name__} failed: {e}")
```

### Event Flow Visualization

```
1. OrdersAPI.create_order() called
2. OrderService creates Order
3. Publishes OrderCreatedEvent
   ↓
4. EventBus delivers to subscribers
   ↓
5. PaymentService.handle_order_created() fires
   → Charges customer
   → Publishes PaymentSucceededEvent
   ↓
6. EventBus delivers to subscribers
   ↓
7. Orders module subscribes to PaymentSucceededEvent
   → OrderService.confirm_order() runs
   → Publishes OrderConfirmedEvent
   ↓
8. InventoryService.handle_order_confirmed() fires
   → Reserves stock
```

**No module directly knows about another module.** All communication via events!

---

## 6. 🏗 Main App — Wiring Everything

```python
# src/main.py
"""
Single entry point — wires all modules together.
"""
from fastapi import FastAPI
import logging

from src.shared.database import init_db
from src.modules.orders._internal.controllers import router as orders_router
from src.modules.payments._internal.controllers import router as payments_router
from src.modules.inventory._internal.controllers import router as inventory_router

# Importing these registers event handlers
from src.modules.payments import api  # registers handlers
from src.modules.inventory import api


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Modular E-Commerce Monolith",
    description="A monolith with strong module boundaries",
)

# Mount each module's router
app.include_router(orders_router, prefix="/api")
app.include_router(payments_router, prefix="/api")
app.include_router(inventory_router, prefix="/api")


@app.on_event("startup")
async def startup():
    logger.info("Initializing modular monolith...")
    init_db()
    logger.info("Modules loaded: orders, payments, inventory")


@app.get("/health")
def health():
    return {"status": "ok", "modules": ["orders", "payments", "inventory"]}
```

---

## 7. 🚫 Enforcing Module Boundaries with `import-linter`

> **The technical secret sauce.** Without enforcement, boundaries decay.

### Configuration

```toml
# .importlinter
[importlinter]
root_package = src

# Contract 1: Modules can't import each other's internals
[importlinter:contract:1]
name = "Modules don't import internals of other modules"
type = forbidden
source_modules =
    src.modules.orders
    src.modules.payments
    src.modules.inventory
forbidden_modules =
    src.modules.orders._internal
    src.modules.payments._internal
    src.modules.inventory._internal
# Exception: a module can import its OWN internals
ignore_imports =
    src.modules.orders.* -> src.modules.orders._internal.*
    src.modules.payments.* -> src.modules.payments._internal.*
    src.modules.inventory.* -> src.modules.inventory._internal.*

# Contract 2: No circular dependencies between modules
[importlinter:contract:2]
name = "No circular dependencies"
type = independence
modules =
    src.modules.orders
    src.modules.payments
    src.modules.inventory
```

### Run Linter

```bash
# Install
pip install import-linter

# Run
lint-imports

# Output:
# Analysed 47 files, 142 dependencies.
# ====================
# Contracts: Pass
```

If a developer **accidentally** imports another module's internals:

```python
# In src/modules/payments/_internal/services.py
from src.modules.orders._internal.domain import Order  # ❌ FORBIDDEN!
```

```bash
lint-imports
# Output:
# ❌ Modules don't import internals of other modules: BROKEN
#    Forbidden import: src.modules.payments._internal.services 
#    -> src.modules.orders._internal.domain
```

**Build fails. No bad code merged.** 🛡

---

## 8. 🧪 Architectural Tests

```python
# tests/architectural/test_module_boundaries.py
"""
Tests that VERIFY architectural rules.
Run these in CI to catch boundary violations.
"""
import pytest
import os
import ast
from pathlib import Path


def find_all_imports(file_path: Path) -> list[str]:
    """Parse Python file to find all imports."""
    with open(file_path) as f:
        tree = ast.parse(f.read())
    
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
    return imports


def test_modules_dont_import_each_others_internals():
    """
    🚫 ARCHITECTURAL RULE:
    Module A cannot import Module B's _internal.
    """
    modules = ["orders", "payments", "inventory"]
    base = Path("src/modules")
    
    violations = []
    
    for module in modules:
        module_path = base / module
        for py_file in module_path.rglob("*.py"):
            imports = find_all_imports(py_file)
            
            for imp in imports:
                # Check if importing from another module's _internal
                for other_module in modules:
                    if other_module == module:
                        continue  # Module can import own internals
                    
                    forbidden = f"src.modules.{other_module}._internal"
                    if forbidden in imp:
                        violations.append(f"{py_file} imports {imp}")
    
    assert not violations, f"Boundary violations: {violations}"


def test_no_circular_dependencies():
    """
    🔄 No circular imports between modules.
    """
    # Build dependency graph
    modules = ["orders", "payments", "inventory"]
    deps = {m: set() for m in modules}
    
    base = Path("src/modules")
    for module in modules:
        for py_file in (base / module).rglob("*.py"):
            for imp in find_all_imports(py_file):
                for other in modules:
                    if other != module and f"src.modules.{other}" in imp:
                        deps[module].add(other)
    
    # Check for cycles via DFS
    def has_cycle(node, visited, rec_stack):
        visited.add(node)
        rec_stack.add(node)
        for neighbor in deps[node]:
            if neighbor not in visited:
                if has_cycle(neighbor, visited, rec_stack):
                    return True
            elif neighbor in rec_stack:
                return True
        rec_stack.remove(node)
        return False
    
    for module in modules:
        visited = set()
        rec_stack = set()
        assert not has_cycle(module, visited, rec_stack), f"Cycle starting at {module}"
```

---

## 9. 🌳 Strangler Pattern Migration

Let's say you're migrating from a legacy monolith to this modular monolith.

```python
# src/legacy_bridge/strangler_facade.py
"""
🌳 STRANGLER FAÇADE
Routes requests between legacy and modern modules.
"""
from fastapi import FastAPI, Request, Response
import httpx
from typing import Optional


app = FastAPI(title="Strangler Façade")


# Configuration: which routes are migrated to modern modules
MIGRATED_ROUTES = {
    "/api/orders": "modern",       # ✅ Migrated
    "/api/payments": "modern",      # ✅ Migrated
    "/api/inventory": "legacy",     # ❌ Still legacy
    "/api/customers": "legacy",     # ❌ Still legacy
    "/api/reports": "legacy",       # ❌ Still legacy
}

LEGACY_HOST = "http://legacy-monolith:3000"
MODERN_HOST = "http://modern-monolith:8000"


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy(path: str, request: Request):
    """Route to legacy or modern based on config."""
    full_path = f"/{path}"
    
    # Determine routing
    target = None
    for route, system in MIGRATED_ROUTES.items():
        if full_path.startswith(route):
            target = MODERN_HOST if system == "modern" else LEGACY_HOST
            break
    
    if target is None:
        target = LEGACY_HOST  # Default to legacy
    
    # Proxy the request
    async with httpx.AsyncClient() as client:
        body = await request.body()
        response = await client.request(
            method=request.method,
            url=f"{target}{full_path}",
            headers=dict(request.headers),
            content=body,
        )
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=dict(response.headers),
        )
```

### Migration Progress

```
Phase 1 (Day 1):
   MIGRATED_ROUTES = {
       "/api/orders": "legacy",      # ALL legacy
       "/api/payments": "legacy",
       "/api/inventory": "legacy",
   }

Phase 2 (Week 4):
   MIGRATED_ROUTES = {
       "/api/orders": "modern",       # ✅ Migrated
       "/api/payments": "legacy",
       "/api/inventory": "legacy",
   }

Phase 3 (Month 3):
   MIGRATED_ROUTES = {
       "/api/orders": "modern",
       "/api/payments": "modern",     # ✅ Migrated
       "/api/inventory": "legacy",
   }

Phase 4 (Month 6):
   MIGRATED_ROUTES = {
       "/api/orders": "modern",
       "/api/payments": "modern",
       "/api/inventory": "modern",    # ✅ Migrated
   }
   # Legacy can be retired now!
```

---

## 10. 🔌 Anti-Corruption Layer (Legacy Integration)

When new module needs to talk to legacy system:

```python
# src/modules/orders/_internal/anti_corruption_layer.py
"""
🛡 ANTI-CORRUPTION LAYER
Translates between legacy data formats and clean domain model.
"""
import httpx
from dataclasses import dataclass
from typing import Optional


@dataclass
class LegacyCustomerData:
    """What legacy returns (messy, weird)."""
    CUSTID: str  # Legacy uses uppercase
    CustomerName: str
    cust_type: str  # Inconsistent naming
    PHONE_NUM: Optional[str]
    addr_1: Optional[str]
    addr_2: Optional[str]


@dataclass
class Customer:
    """Clean domain model — what Orders module wants."""
    id: int
    name: str
    type: str
    phone: Optional[str]
    address: Optional[str]


class LegacyCustomerACL:
    """
    🛡 Wraps legacy customer service.
    Translates messy legacy to clean domain.
    """
    
    def __init__(self, legacy_url: str = "http://legacy/customers"):
        self.legacy_url = legacy_url
    
    async def get_customer(self, customer_id: int) -> Optional[Customer]:
        """Fetch from legacy, translate to clean model."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.legacy_url}/{customer_id}")
            if response.status_code != 200:
                return None
            
            legacy_data = LegacyCustomerData(**response.json())
            
            # Translate
            return Customer(
                id=int(legacy_data.CUSTID),
                name=legacy_data.CustomerName,
                type=legacy_data.cust_type.lower(),
                phone=legacy_data.PHONE_NUM,
                address=self._combine_address(legacy_data.addr_1, legacy_data.addr_2),
            )
    
    def _combine_address(self, addr1: Optional[str], addr2: Optional[str]) -> Optional[str]:
        """Convert legacy 2-line address to single string."""
        parts = [a for a in [addr1, addr2] if a]
        return ", ".join(parts) if parts else None
```

> **The ACL protects new code from old chaos.** Clean domain stays pure.

---

## 11. 🚀 Per-Module CI/CD

Each module can have its **own pipeline**:

```yaml
# .github/workflows/orders-ci.yml
name: Orders Module CI

on:
  push:
    paths:
      - 'src/modules/orders/**'    # Trigger only on Orders changes
      - 'src/shared/**'             # Or shared changes
  pull_request:
    paths:
      - 'src/modules/orders/**'

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      
      - name: Install deps
        run: pip install -e ".[dev]"
      
      - name: 🚫 Verify boundaries
        run: |
          pip install import-linter
          lint-imports
      
      - name: 🧪 Architectural tests
        run: pytest tests/architectural/
      
      - name: 🧪 Module unit tests
        run: pytest src/modules/orders/tests/
      
      - name: 🧪 Integration tests
        run: pytest tests/integration/
      
      - name: 📊 Coverage
        run: pytest --cov=src/modules/orders src/modules/orders/tests/
```

```yaml
# .github/workflows/payments-ci.yml
name: Payments Module CI

on:
  push:
    paths:
      - 'src/modules/payments/**'
      - 'src/shared/**'

jobs:
  test:
    # Same pattern but for payments
    ...
```

> **Only changed module rebuilds + tests.** Fast feedback loop!

---

## 12. 🐳 Deployment

### docker-compose.yml

```yaml
version: '3.8'

services:
  # Single deployment of modular monolith
  app:
    build: .
    ports: ["8000:8000"]
    environment:
      DATABASE_URL: postgresql://app:app@db:5432/app
    depends_on: [db]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: app
      POSTGRES_PASSWORD: app
      POSTGRES_DB: app
    volumes: ["pgdata:/var/lib/postgresql/data"]

volumes:
  pgdata:
```

### Dockerfile

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install -e ".[prod]"
COPY src/ src/
EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Run

```bash
docker-compose up -d

# Test the full event chain
curl -X POST http://localhost:8000/api/orders \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": 1,
    "items": [
      {"product_id": 1, "quantity": 2, "price": 5000.00}
    ]
  }'

# Watch logs to see event flow:
# - Orders module creates order
# - OrderCreatedEvent published
# - Payments module receives event, charges
# - PaymentSucceededEvent published
# - Orders module confirms order
# - OrderConfirmedEvent published
# - Inventory module reduces stock
```

---

## 13. 🪦 Future Migration to Microservices

When time comes to **split into microservices**, your modular monolith makes it easy:

### Step 1: Replace In-Process EventBus with Kafka

```python
# src/shared/events.py — BEFORE (modular monolith)
class EventBus:
    def publish(self, event):
        # In-process synchronous
        for handler in self._handlers[type(event)]:
            handler(event)


# src/shared/events.py — AFTER (microservice-ready)
class EventBus:
    def __init__(self, kafka_producer):
        self.producer = kafka_producer
    
    def publish(self, event):
        # Send to Kafka — distributed!
        topic = self._get_topic(event)
        self.producer.send(topic, json.dumps(asdict(event)))
```

### Step 2: Extract Module into Service

```bash
# Today (modular monolith)
src/modules/payments/

# Tomorrow (microservice)
payments-service/    # ← Separate repo + deployment
├── src/payments/   # Same code structure
├── Dockerfile
├── requirements.txt
└── k8s.yaml
```

**The code structure stays nearly identical** — that's the beauty of modular monolith!

### Step 3: Per-Module Database

```python
# Modular monolith — shared DB, prefixed tables
class OrderModel(Base):
    __tablename__ = "orders_orders"  # Prefixed!

# Microservice — own DB per service
# Orders Service → orders-db
# Payments Service → payments-db
```

---

## 14. 📊 Real Production Wins

### Before (Tangled Monolith)
- 200K LOC
- 1 deployment pipeline (45 min)
- Merge conflicts daily
- 1 service degradation = whole app down

### After (Modular Monolith)
- Same 200K LOC, organized into 8 modules
- 8 deployment pipelines (5-10 min each)
- Conflicts rare (per-module ownership)
- Module failure isolated

### Further (Microservices, year later)
- Split out 3 highest-traffic modules
- Independent scaling
- Different tech stacks per service

---

## 15. Summary

```
✅ Built modular monolith with 3 bounded contexts
✅ Each module: public API + private internals
✅ Communication via EVENTS (no direct coupling)
✅ Boundaries ENFORCED by tooling (import-linter)
✅ Architectural tests catch violations in CI
✅ Strangler pattern for legacy migration
✅ Anti-corruption layer for clean integration
✅ Ready to split into microservices when needed
```

### What You've Learned

```
🟦 Modular monolith = single deploy + service-like internal structure
📡 Events = clean inter-module communication
🚫 Enforcement = tooling that breaks build on violations
🌳 Strangler pattern = safe legacy migration
🛡 Anti-corruption layer = isolation from messy systems
🚀 Per-module CI/CD = faster feedback
```

---

## 16. Action Items

1. ✅ **Build this modular monolith** end-to-end
2. ✅ **Add `import-linter`** to your CI
3. ✅ **Identify** 3 bounded contexts in your current project
4. ✅ **Try Strangler pattern** for one legacy area
5. ✅ **Implement event bus** for cross-module communication

---

## 17. Related Resources

- [01_Year3-4_Mid/05_Microservices/01_microservices_patterns.md](../../../01_Year3-4_Mid/05_Microservices/01_microservices_patterns.md)
- [01_Year3-4_Mid/05_Microservices/09_domain_driven_design.md](../../../01_Year3-4_Mid/05_Microservices/09_domain_driven_design.md)
- [02_Year5+_Senior/01_System_Design/HLD_Theory/01_Monolithic_vs_Microservices.md](../../01_System_Design/HLD_Theory/01_Monolithic_vs_Microservices.md)
- [import-linter docs](https://import-linter.readthedocs.io/)
- Book: "Building Microservices" by Sam Newman (Modular monolith chapter)
- Book: "Monolith to Microservices" by Sam Newman
