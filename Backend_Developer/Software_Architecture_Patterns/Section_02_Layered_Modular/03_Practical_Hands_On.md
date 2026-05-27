# Lecture 3 — Practical Hands-On: Clean vs Onion (Side-by-Side)

> **Theory file:** [03_Clean_and_Onion_Architecture.md](03_Clean_and_Onion_Architecture.md)

---

## 🎯 Is Practical Mein Kya Banayenge?

**Same use case** ko **dono architectures mein** implement karenge — to see the **real differences in code**:

1. ✅ **Clean Architecture** Python project — full implementation
2. ✅ **Onion Architecture** Python project — full implementation
3. ✅ **Same use case** in both (Place Order)
4. ✅ **Side-by-side comparison** — folder, code, tests
5. ✅ **Migration path** from one to the other
6. ✅ **Common mistakes** with fixes

By end: aap **practically samjhoge** which one fits which scenario.

---

## 1. Project Setup — Two Parallel Projects

We'll build **same e-commerce "Place Order" feature** in both architectures.

### Folder Layouts (Side-by-Side)

```
clean_arch_project/                    onion_arch_project/
│                                      │
├── src/                                ├── src/
│   ├── entities/          🟡           │   ├── domain/             🟩 (Core)
│   │   ├── order.py                    │   │   ├── model/
│   │   ├── product.py                  │   │   │   ├── order.py
│   │   └── customer.py                 │   │   │   ├── product.py
│   │                                    │   │   │   └── customer.py
│   ├── use_cases/         🔴           │   │   ├── services/      🟪 (Domain Services)
│   │   ├── place_order.py              │   │   │   ├── pricing.py
│   │   ├── cancel_order.py             │   │   │   └── inventory.py
│   │   ├── interfaces/                 │   │   └── repositories/   (Interfaces)
│   │   │   ├── order_repo.py           │   │       ├── order_repo.py
│   │   │   ├── product_repo.py         │   │       └── product_repo.py
│   │   │   └── payment.py              │   │
│   │   └── dto/                        │   ├── application/         🔵 (App Services)
│   │       ├── place_order_request.py  │   │   ├── services/
│   │       └── place_order_response.py │   │   │   └── order_service.py
│   │                                    │   │   ├── dto/
│   ├── interface_adapters/  🟢         │   │   └── interfaces/
│   │   ├── controllers/                │   │
│   │   │   └── order_controller.py     │   ├── infrastructure/      🟧 (Outer)
│   │   ├── presenters/                 │   │   ├── persistence/
│   │   │   └── order_presenter.py      │   │   │   ├── postgres_order_repo.py
│   │   └── gateways/                   │   │   │   └── postgres_product_repo.py
│   │       └── stripe_gateway.py       │   │   ├── web/
│   │                                    │   │   │   └── controllers/
│   └── frameworks_drivers/  🔵         │   │   └── external/
│       ├── web/                        │   │       └── stripe_client.py
│       │   └── fastapi_app.py          │   │
│       ├── db/                         │   └── main.py
│       │   ├── models.py                │
│       │   └── repository.py            └── tests/
│       └── external/                   
│           └── stripe_api.py           
│                                      
└── tests/                             
```

> **Notice:** Folder structure **literally reflects** each architecture's layer terminology.

---

## 2. 🟡 CLEAN ARCHITECTURE — Implementation

### Layer 1: Entities (Pure Domain)

```python
# src/entities/order.py
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
class OrderLine:
    product_id: int
    product_name: str
    quantity: int
    unit_price: Decimal

    @property
    def line_total(self) -> Decimal:
        return self.unit_price * self.quantity


@dataclass
class Order:
    """
    🟡 ENTITY — pure business object
    NO frameworks, NO I/O dependencies
    """
    id: UUID
    customer_id: int
    lines: List[OrderLine]
    status: OrderStatus
    total: Decimal
    payment_id: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)

    @classmethod
    def create(cls, customer_id: int, lines: List[OrderLine]) -> "Order":
        """Factory — enforces business invariants."""
        if not lines:
            raise ValueError("Order must have items")
        
        total = sum((line.line_total for line in lines), Decimal("0"))
        
        return cls(
            id=uuid4(),
            customer_id=customer_id,
            lines=lines,
            status=OrderStatus.PENDING,
            total=total,
        )

    def confirm(self, payment_id: str) -> None:
        if self.status != OrderStatus.PENDING:
            raise ValueError(f"Cannot confirm in status {self.status}")
        self.status = OrderStatus.CONFIRMED
        self.payment_id = payment_id

    def cancel(self) -> None:
        if self.status == OrderStatus.CONFIRMED:
            self.status = OrderStatus.CANCELLED
        else:
            raise ValueError(f"Cannot cancel in status {self.status}")


# src/entities/product.py
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class Product:
    """🟡 ENTITY"""
    id: int
    name: str
    price: Decimal
    stock: int

    def has_stock(self, qty: int) -> bool:
        return self.stock >= qty

    def reduce_stock(self, qty: int) -> None:
        if not self.has_stock(qty):
            raise ValueError(f"Insufficient stock: have {self.stock}, need {qty}")
        self.stock -= qty
```

### Layer 2: Use Cases (Application Business Rules)

```python
# src/use_cases/interfaces/order_repo.py
from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from src.entities.order import Order


class IOrderRepository(ABC):
    """
    🔴 INTERFACE defined by Use Case layer.
    Implemented by outer Infrastructure layer.
    """
    @abstractmethod
    def save(self, order: Order) -> None: ...

    @abstractmethod
    def find_by_id(self, order_id: UUID) -> Optional[Order]: ...


# src/use_cases/interfaces/product_repo.py
from typing import Optional, List

class IProductRepository(ABC):
    @abstractmethod
    def get(self, product_id: int) -> Optional[Product]: ...

    @abstractmethod
    def get_many(self, ids: List[int]) -> List[Product]: ...

    @abstractmethod
    def save(self, product: Product) -> None: ...


# src/use_cases/interfaces/payment.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class PaymentResult:
    success: bool
    payment_id: str
    error: str = ""


class IPaymentService(ABC):
    @abstractmethod
    def charge(
        self,
        customer_id: int,
        amount: Decimal,
        idempotency_key: str,
    ) -> PaymentResult: ...
```

```python
# src/use_cases/dto/place_order_request.py
from dataclasses import dataclass
from typing import List


@dataclass
class OrderItemDTO:
    product_id: int
    quantity: int


@dataclass
class PlaceOrderRequest:
    """DTO — input to use case."""
    customer_id: int
    items: List[OrderItemDTO]
    payment_method: str


# src/use_cases/dto/place_order_response.py
@dataclass
class PlaceOrderResponse:
    """DTO — output of use case."""
    order_id: str
    status: str
    total_amount: float
    payment_id: str
```

```python
# src/use_cases/place_order.py
from typing import List

from src.entities.order import Order, OrderLine
from src.entities.product import Product
from src.use_cases.interfaces.order_repo import IOrderRepository
from src.use_cases.interfaces.product_repo import IProductRepository
from src.use_cases.interfaces.payment import IPaymentService
from src.use_cases.dto.place_order_request import PlaceOrderRequest
from src.use_cases.dto.place_order_response import PlaceOrderResponse


class PlaceOrder:
    """
    🔴 USE CASE
    
    Orchestrates the "Place Order" application workflow.
    Depends only on INTERFACES (defined in this layer).
    NO direct dependency on infrastructure.
    """
    
    def __init__(
        self,
        order_repo: IOrderRepository,
        product_repo: IProductRepository,
        payment: IPaymentService,
    ):
        self.order_repo = order_repo
        self.product_repo = product_repo
        self.payment = payment

    def execute(self, request: PlaceOrderRequest) -> PlaceOrderResponse:
        # 1. Load products via interface (use case doesn't know it's SQL)
        product_ids = [item.product_id for item in request.items]
        products = self.product_repo.get_many(product_ids)
        product_dict = {p.id: p for p in products}
        
        # 2. Validate
        for item in request.items:
            if item.product_id not in product_dict:
                raise ValueError(f"Product {item.product_id} not found")
        
        # 3. Build order lines
        lines: List[OrderLine] = []
        for item in request.items:
            product = product_dict[item.product_id]
            if not product.has_stock(item.quantity):
                raise ValueError(f"Insufficient stock for {product.name}")
            lines.append(OrderLine(
                product_id=product.id,
                product_name=product.name,
                quantity=item.quantity,
                unit_price=product.price,
            ))
        
        # 4. Create order entity (delegates to entity factory)
        order = Order.create(request.customer_id, lines)
        
        # 5. Save (interface call)
        self.order_repo.save(order)
        
        # 6. Charge payment (interface call)
        payment_result = self.payment.charge(
            customer_id=request.customer_id,
            amount=order.total,
            idempotency_key=str(order.id),
        )
        
        if not payment_result.success:
            raise ValueError(f"Payment failed: {payment_result.error}")
        
        # 7. Confirm + reduce stock
        order.confirm(payment_result.payment_id)
        for item in request.items:
            product = product_dict[item.product_id]
            product.reduce_stock(item.quantity)
            self.product_repo.save(product)
        
        self.order_repo.save(order)
        
        # 8. Return DTO (no entity leaking out!)
        return PlaceOrderResponse(
            order_id=str(order.id),
            status=order.status.value,
            total_amount=float(order.total),
            payment_id=order.payment_id,
        )
```

### Layer 3: Interface Adapters (Controllers, Presenters)

```python
# src/interface_adapters/controllers/order_controller.py
from src.use_cases.place_order import PlaceOrder
from src.use_cases.dto.place_order_request import PlaceOrderRequest, OrderItemDTO


class OrderController:
    """
    🟢 INTERFACE ADAPTER
    
    Translates HTTP / external requests → use case calls.
    Translates use case results → external format.
    """
    
    def __init__(self, place_order: PlaceOrder):
        self.place_order = place_order
    
    def post_order(self, http_body: dict) -> dict:
        """Translate HTTP → use case → HTTP."""
        # Translate HTTP body to use case DTO
        request = PlaceOrderRequest(
            customer_id=http_body["customer_id"],
            items=[
                OrderItemDTO(
                    product_id=i["product_id"],
                    quantity=i["quantity"],
                )
                for i in http_body["items"]
            ],
            payment_method=http_body.get("payment_method", "stripe"),
        )
        
        # Execute use case
        response = self.place_order.execute(request)
        
        # Translate result to HTTP response
        return {
            "order_id": response.order_id,
            "status": response.status,
            "total": response.total_amount,
            "payment": response.payment_id,
        }
```

### Layer 4: Frameworks & Drivers (FastAPI, DB)

```python
# src/frameworks_drivers/web/fastapi_app.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List

from src.frameworks_drivers.bootstrap import build_application


app = FastAPI(title="Clean Architecture App")


class OrderItemSchema(BaseModel):
    product_id: int
    quantity: int


class PlaceOrderSchema(BaseModel):
    customer_id: int
    items: List[OrderItemSchema]
    payment_method: str = "stripe"


@app.post("/orders")
def place_order(req: PlaceOrderSchema):
    """🔵 FRAMEWORK layer — FastAPI specific."""
    container = build_application()
    controller = container["order_controller"]
    
    try:
        result = controller.post_order(req.model_dump())
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))
```

```python
# src/frameworks_drivers/db/repository.py
from sqlalchemy import create_engine, Column, String, Integer, JSON, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from typing import Optional, List
from uuid import UUID
import json

from src.entities.order import Order, OrderLine, OrderStatus
from src.entities.product import Product
from src.use_cases.interfaces.order_repo import IOrderRepository
from src.use_cases.interfaces.product_repo import IProductRepository


Base = declarative_base()


class OrderModel(Base):
    """🔵 FRAMEWORK — SQLAlchemy model lives in infrastructure."""
    __tablename__ = "orders"
    id = Column(PgUUID(as_uuid=True), primary_key=True)
    customer_id = Column(Integer, nullable=False)
    status = Column(String, nullable=False)
    lines = Column(JSON, nullable=False)
    total = Column(String, nullable=False)
    payment_id = Column(String)
    created_at = Column(DateTime)


class ProductModel(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    price = Column(String, nullable=False)
    stock = Column(Integer, nullable=False)


class SqlOrderRepository(IOrderRepository):
    """🔵 INFRASTRUCTURE — implements interface from Use Case layer."""
    
    def __init__(self, session):
        self.session = session
    
    def save(self, order: Order) -> None:
        from decimal import Decimal
        model = OrderModel(
            id=order.id,
            customer_id=order.customer_id,
            status=order.status.value,
            lines=[
                {
                    "product_id": l.product_id,
                    "product_name": l.product_name,
                    "quantity": l.quantity,
                    "unit_price": str(l.unit_price),
                }
                for l in order.lines
            ],
            total=str(order.total),
            payment_id=order.payment_id,
            created_at=order.created_at,
        )
        self.session.merge(model)
        self.session.flush()
    
    def find_by_id(self, order_id: UUID) -> Optional[Order]:
        from decimal import Decimal
        model = self.session.query(OrderModel).filter_by(id=order_id).first()
        if not model:
            return None
        return Order(
            id=model.id,
            customer_id=model.customer_id,
            lines=[
                OrderLine(
                    product_id=l["product_id"],
                    product_name=l["product_name"],
                    quantity=l["quantity"],
                    unit_price=Decimal(l["unit_price"]),
                )
                for l in model.lines
            ],
            status=OrderStatus(model.status),
            total=Decimal(model.total),
            payment_id=model.payment_id,
            created_at=model.created_at,
        )


class SqlProductRepository(IProductRepository):
    def __init__(self, session):
        self.session = session
    
    def get(self, product_id: int) -> Optional[Product]:
        from decimal import Decimal
        model = self.session.query(ProductModel).filter_by(id=product_id).first()
        if not model:
            return None
        return Product(
            id=model.id,
            name=model.name,
            price=Decimal(model.price),
            stock=model.stock,
        )
    
    def get_many(self, ids: List[int]) -> List[Product]:
        from decimal import Decimal
        models = self.session.query(ProductModel).filter(ProductModel.id.in_(ids)).all()
        return [
            Product(id=m.id, name=m.name, price=Decimal(m.price), stock=m.stock)
            for m in models
        ]
    
    def save(self, product: Product) -> None:
        model = self.session.query(ProductModel).filter_by(id=product.id).first()
        if model:
            model.stock = product.stock
        else:
            model = ProductModel(
                id=product.id, name=product.name,
                price=str(product.price), stock=product.stock,
            )
            self.session.add(model)
        self.session.flush()
```

```python
# src/frameworks_drivers/external/stripe_api.py
import stripe
from decimal import Decimal

from src.use_cases.interfaces.payment import IPaymentService, PaymentResult


class StripePaymentService(IPaymentService):
    """🔵 FRAMEWORK — Stripe SDK lives at outermost layer."""
    
    def __init__(self, api_key: str):
        stripe.api_key = api_key
    
    def charge(
        self,
        customer_id: int,
        amount: Decimal,
        idempotency_key: str,
    ) -> PaymentResult:
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),
                currency="inr",
                idempotency_key=idempotency_key,
            )
            return PaymentResult(success=True, payment_id=intent.id)
        except stripe.error.StripeError as e:
            return PaymentResult(success=False, payment_id="", error=str(e))
```

### Bootstrap (Wire It All)

```python
# src/frameworks_drivers/bootstrap.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.use_cases.place_order import PlaceOrder
from src.frameworks_drivers.db.repository import (
    SqlOrderRepository,
    SqlProductRepository,
    Base,
)
from src.frameworks_drivers.external.stripe_api import StripePaymentService
from src.interface_adapters.controllers.order_controller import OrderController


def build_application():
    """
    🔵 OUTER LAYER WIRING
    
    The ONLY place that knows both inner and outer layers.
    """
    # Setup DB
    db_url = os.environ.get("DATABASE_URL", "sqlite:///clean.db")
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Build outer adapters
    order_repo = SqlOrderRepository(session)
    product_repo = SqlProductRepository(session)
    payment = StripePaymentService(os.environ.get("STRIPE_KEY", "test"))
    
    # Build use case (with interfaces — doesn't know about Stripe/SQL)
    place_order = PlaceOrder(
        order_repo=order_repo,
        product_repo=product_repo,
        payment=payment,
    )
    
    # Build controller (interface adapter)
    controller = OrderController(place_order)
    
    return {
        "order_controller": controller,
        "place_order": place_order,
        "session": session,
    }
```

---

## 3. 🟩 ONION ARCHITECTURE — Implementation

Same use case, **different layout**.

### Layer 1: Domain Model (Innermost)

```python
# src/domain/model/order.py
"""
🟩 DOMAIN MODEL — same as Clean entities but emphasizes DDD aggregate
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
class OrderLine:
    """Value Object."""
    product_id: int
    product_name: str
    quantity: int
    unit_price: Decimal

    @property
    def line_total(self) -> Decimal:
        return self.unit_price * self.quantity


@dataclass
class Order:
    """🟩 AGGREGATE ROOT — owns its invariants."""
    id: UUID
    customer_id: int
    lines: List[OrderLine]
    status: OrderStatus
    total: Decimal
    payment_id: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)

    @classmethod
    def create(cls, customer_id: int, lines: List[OrderLine]) -> "Order":
        if not lines:
            raise ValueError("Order must have items")
        total = sum((l.line_total for l in lines), Decimal("0"))
        return cls(
            id=uuid4(), customer_id=customer_id, lines=lines,
            status=OrderStatus.PENDING, total=total,
        )

    def confirm(self, payment_id: str) -> None:
        if self.status != OrderStatus.PENDING:
            raise ValueError("Already processed")
        self.status = OrderStatus.CONFIRMED
        self.payment_id = payment_id
```

### Layer 2: Domain Services (Cross-Entity Logic)

```python
# src/domain/services/pricing.py
from decimal import Decimal
from typing import List

from src.domain.model.product import Product
from src.domain.model.customer import Customer


class PricingService:
    """
    🟪 DOMAIN SERVICE
    
    Cross-entity logic that doesn't fit in any single entity.
    Pure business logic — no I/O.
    """
    
    def calculate_subtotal(self, items: List[dict], products: dict) -> Decimal:
        subtotal = Decimal("0")
        for item in items:
            product = products[item["product_id"]]
            subtotal += product.price * item["quantity"]
        return subtotal
    
    def apply_customer_discount(
        self,
        subtotal: Decimal,
        customer: Customer,
    ) -> Decimal:
        """Different discount logic for different customer tiers."""
        if customer.tier == "platinum":
            return subtotal * Decimal("0.85")  # 15% discount
        elif customer.tier == "gold":
            return subtotal * Decimal("0.90")  # 10% discount
        return subtotal
    
    def add_tax(self, amount: Decimal, tax_rate: Decimal = Decimal("0.18")) -> Decimal:
        """India GST."""
        return amount * (1 + tax_rate)


# src/domain/services/inventory.py
from typing import List

from src.domain.model.product import Product


class InventoryService:
    """🟪 DOMAIN SERVICE — inventory-related logic."""
    
    def can_fulfill_order(self, items: List[dict], products: dict) -> tuple[bool, str]:
        for item in items:
            product = products.get(item["product_id"])
            if not product:
                return False, f"Product {item['product_id']} not found"
            if not product.has_stock(item["quantity"]):
                return False, f"Insufficient stock for {product.name}"
        return True, ""
```

### Repository Interfaces (Domain Layer)

```python
# src/domain/repositories/order_repo.py
from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from src.domain.model.order import Order


class IOrderRepository(ABC):
    """🟩 Interface defined in DOMAIN layer."""
    
    @abstractmethod
    def save(self, order: Order) -> None: ...
    
    @abstractmethod
    def get(self, order_id: UUID) -> Optional[Order]: ...


# src/domain/repositories/product_repo.py
# Similar to Clean's
```

### Layer 3: Application Services

```python
# src/application/services/order_service.py
"""
🔵 APPLICATION SERVICE
Coordinates workflows using domain services + repositories.
"""
from dataclasses import dataclass
from typing import List
from decimal import Decimal

from src.domain.model.order import Order, OrderLine
from src.domain.services.pricing import PricingService
from src.domain.services.inventory import InventoryService
from src.domain.repositories.order_repo import IOrderRepository
from src.domain.repositories.product_repo import IProductRepository
from src.domain.repositories.customer_repo import ICustomerRepository
from src.application.interfaces.payment import IPaymentService


@dataclass
class PlaceOrderCommand:
    customer_id: int
    items: List[dict]  # [{"product_id": 1, "quantity": 2}]
    payment_method: str


@dataclass
class PlaceOrderResult:
    order_id: str
    status: str
    total_amount: float


class OrderService:
    """🔵 ORCHESTRATOR — calls domain services + repos."""
    
    def __init__(
        self,
        order_repo: IOrderRepository,
        product_repo: IProductRepository,
        customer_repo: ICustomerRepository,
        payment: IPaymentService,
        pricing: PricingService,
        inventory: InventoryService,
    ):
        self.order_repo = order_repo
        self.product_repo = product_repo
        self.customer_repo = customer_repo
        self.payment = payment
        self.pricing = pricing
        self.inventory = inventory
    
    def place_order(self, command: PlaceOrderCommand) -> PlaceOrderResult:
        # 1. Load entities
        customer = self.customer_repo.get(command.customer_id)
        if not customer:
            raise ValueError(f"Customer {command.customer_id} not found")
        
        product_ids = [item["product_id"] for item in command.items]
        products = self.product_repo.get_many(product_ids)
        product_dict = {p.id: p for p in products}
        
        # 2. Use Domain Service: inventory check
        can_fulfill, error = self.inventory.can_fulfill_order(command.items, product_dict)
        if not can_fulfill:
            raise ValueError(error)
        
        # 3. Use Domain Service: pricing
        subtotal = self.pricing.calculate_subtotal(command.items, product_dict)
        after_discount = self.pricing.apply_customer_discount(subtotal, customer)
        total = self.pricing.add_tax(after_discount)
        
        # 4. Build order using domain model
        lines = [
            OrderLine(
                product_id=item["product_id"],
                product_name=product_dict[item["product_id"]].name,
                quantity=item["quantity"],
                unit_price=product_dict[item["product_id"]].price,
            )
            for item in command.items
        ]
        order = Order.create(command.customer_id, lines)
        order.total = total  # Apply calculated total
        
        # 5. Save + Charge
        self.order_repo.save(order)
        
        payment_result = self.payment.charge(
            customer_id=command.customer_id,
            amount=order.total,
            idempotency_key=str(order.id),
        )
        
        if not payment_result.success:
            raise ValueError(payment_result.error)
        
        # 6. Confirm + reduce inventory
        order.confirm(payment_result.payment_id)
        for item in command.items:
            product = product_dict[item["product_id"]]
            product.reduce_stock(item["quantity"])
            self.product_repo.save(product)
        
        self.order_repo.save(order)
        
        return PlaceOrderResult(
            order_id=str(order.id),
            status=order.status.value,
            total_amount=float(order.total),
        )
```

### Layer 4: Infrastructure (Outermost)

```python
# src/infrastructure/persistence/postgres_order_repo.py
"""
🟧 INFRASTRUCTURE — same as Clean's outer layer
"""
from sqlalchemy import Column, JSON, String, Integer
from sqlalchemy.orm import declarative_base
from src.domain.repositories.order_repo import IOrderRepository
# ... (same SQLAlchemy code as Clean version)


# src/infrastructure/web/controllers/order_controller.py
"""
🟧 INFRASTRUCTURE — web layer (FastAPI specific)
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List

from src.application.services.order_service import OrderService, PlaceOrderCommand
from src.infrastructure.bootstrap import build_app


app = FastAPI(title="Onion Architecture App")


class OrderItemSchema(BaseModel):
    product_id: int
    quantity: int


class PlaceOrderSchema(BaseModel):
    customer_id: int
    items: List[OrderItemSchema]
    payment_method: str = "stripe"


@app.post("/orders")
def place_order(req: PlaceOrderSchema):
    """🟧 Web controller — at outermost layer."""
    container = build_app()
    order_service: OrderService = container["order_service"]
    
    try:
        command = PlaceOrderCommand(
            customer_id=req.customer_id,
            items=[{"product_id": i.product_id, "quantity": i.quantity} for i in req.items],
            payment_method=req.payment_method,
        )
        result = order_service.place_order(command)
        return {
            "order_id": result.order_id,
            "status": result.status,
            "total": result.total_amount,
        }
    except ValueError as e:
        raise HTTPException(400, str(e))
```

### Bootstrap

```python
# src/infrastructure/bootstrap.py
"""🟧 Wiring at outermost layer."""
from src.application.services.order_service import OrderService
from src.domain.services.pricing import PricingService
from src.domain.services.inventory import InventoryService
from src.infrastructure.persistence.postgres_order_repo import SqlOrderRepository
# ... (other imports)


def build_app():
    # DB session
    session = create_db_session()
    
    # Repositories (Infrastructure)
    order_repo = SqlOrderRepository(session)
    product_repo = SqlProductRepository(session)
    customer_repo = SqlCustomerRepository(session)
    payment = StripePaymentService(...)
    
    # Domain Services (Pure)
    pricing = PricingService()
    inventory = InventoryService()
    
    # Application Service (orchestrator)
    order_service = OrderService(
        order_repo=order_repo,
        product_repo=product_repo,
        customer_repo=customer_repo,
        payment=payment,
        pricing=pricing,
        inventory=inventory,
    )
    
    return {"order_service": order_service}
```

---

## 4. Side-by-Side Comparison

### Code Differences

```
CLEAN ARCHITECTURE                    ONION ARCHITECTURE
──────────────────                    ──────────────────

Layer 1: Entities (Yellow)            Layer 1: Domain Model (Green)
  - Pure business objects               - Pure business objects (aggregates)
  - Pure Python                          - Pure Python
  - SAME concept, different name        - SAME concept, different name

Layer 2: Use Cases (Red)              Layer 2: Domain Services (Purple)
  - PlaceOrder, RegisterUser            - PricingService, InventoryService
  - Application workflows                - Cross-entity business logic
  
                                       Layer 3: Application Services (Blue)
                                         - OrderService.place_order()
                                         - Orchestrates domain services

Layer 3: Interface Adapters (Green)    Layer 4: Infrastructure (Orange)
  - Controllers, Presenters              - All technology code:
  - Gateways                               • Web controllers
                                          • Repositories
Layer 4: Frameworks & Drivers (Blue)     • External APIs
  - Web, DB, External                    • Frameworks
```

### Key Observation

> **Clean** has a **dedicated Use Case layer** to focus on application behavior.
> **Onion** has a **dedicated Domain Services layer** to focus on cross-entity domain logic.

Both achieve same goals via different layer organization.

### Pros & Cons Comparison

| Aspect | Clean | Onion |
|---|---|---|
| **Strength** | Clear use case isolation | Strong DDD alignment |
| **Naming clarity** | Excellent (Entity, Use Case) | Industry/DDD-friendly |
| **Best for** | App-behavior focus | Rich domain modeling |
| **Layer count** | 4 explicit | 4-5 (incl. domain svc) |
| **Diagram** | Bull's eye | Onion rings |
| **Adoption** | Recently popular | Older, in DDD community |

---

## 5. Migration: Clean → Onion (or vice versa)

If you start with Clean and realize you want richer domain logic, here's how to evolve:

### Step 1: Extract Domain Services

```python
# CLEAN: Logic in use case
class PlaceOrder:
    def execute(self, request):
        # Pricing inline
        subtotal = sum(p.price * i.qty for p, i in zip(products, items))
        if customer.tier == "gold":
            subtotal *= 0.9
        # ... lots of pricing logic
        
        # Then save, charge, etc.

# ONION-friendly: Extract to domain service
class PlaceOrder:  # or OrderService
    def execute(self, request):
        # Delegate to domain service
        total = self.pricing.calculate_total(items, customer, products)
        
        # Then save, charge, etc.

class PricingService:  # New domain service
    def calculate_total(self, items, customer, products):
        # Pricing logic isolated
        ...
```

### Step 2: Identify Cross-Entity Logic

Look for places where business logic involves multiple entities:
- Pricing (Product + Customer + Discount)
- Shipping (Order + Address + Zone)
- Inventory (Product + Order + Warehouse)

Extract these into **Domain Services**.

### Step 3: Reorganize Folders

```
BEFORE (Clean):                       AFTER (Onion):
─────────────                          ─────────────

src/                                   src/
├── entities/                          ├── domain/
├── use_cases/                          │   ├── model/        ← entities
├── interface_adapters/                 │   ├── services/     ← extracted
└── frameworks_drivers/                 │   └── repositories/
                                       ├── application/        ← was use_cases
                                       └── infrastructure/     ← merged
```

---

## 6. Testing Both Architectures

### Clean Architecture Test

```python
# tests/clean/test_place_order.py
import pytest
from decimal import Decimal
from uuid import uuid4
from unittest.mock import MagicMock

from src.entities.order import Order, OrderStatus
from src.entities.product import Product
from src.use_cases.place_order import PlaceOrder
from src.use_cases.dto.place_order_request import PlaceOrderRequest, OrderItemDTO
from src.use_cases.interfaces.payment import PaymentResult


def test_place_order_clean():
    # Mock interfaces
    order_repo = MagicMock()
    product_repo = MagicMock()
    payment = MagicMock()
    
    # Setup mocks
    product_repo.get_many.return_value = [
        Product(id=1, name="iPhone", price=Decimal("80000"), stock=10),
    ]
    payment.charge.return_value = PaymentResult(success=True, payment_id="pay_123")
    
    # Execute use case
    use_case = PlaceOrder(order_repo, product_repo, payment)
    request = PlaceOrderRequest(
        customer_id=1,
        items=[OrderItemDTO(product_id=1, quantity=2)],
        payment_method="stripe",
    )
    
    result = use_case.execute(request)
    
    # Assertions
    assert result.status == "confirmed"
    assert result.payment_id == "pay_123"
    payment.charge.assert_called_once()
    order_repo.save.assert_called()
```

### Onion Architecture Test

```python
# tests/onion/test_order_service.py
import pytest
from decimal import Decimal
from unittest.mock import MagicMock

from src.application.services.order_service import OrderService, PlaceOrderCommand
from src.domain.services.pricing import PricingService
from src.domain.services.inventory import InventoryService
from src.domain.model.product import Product
from src.domain.model.customer import Customer


def test_place_order_onion():
    # Mocks
    order_repo = MagicMock()
    product_repo = MagicMock()
    customer_repo = MagicMock()
    payment = MagicMock()
    
    # REAL domain services (pure logic, no mocks needed!)
    pricing = PricingService()
    inventory = InventoryService()
    
    # Setup
    customer_repo.get.return_value = Customer(id=1, name="Ashish", tier="gold")
    product_repo.get_many.return_value = [
        Product(id=1, name="iPhone", price=Decimal("80000"), stock=10),
    ]
    payment.charge.return_value = MagicMock(success=True, payment_id="pay_456")
    
    # Service
    order_service = OrderService(
        order_repo, product_repo, customer_repo, payment,
        pricing, inventory,
    )
    
    command = PlaceOrderCommand(
        customer_id=1,
        items=[{"product_id": 1, "quantity": 2}],
        payment_method="stripe",
    )
    
    result = order_service.place_order(command)
    
    # Assertions
    assert result.status == "confirmed"
    # Gold customer discount applied:
    # 80000 * 2 = 160000 → 10% off = 144000 → +18% tax = 169920
    expected = Decimal("160000") * Decimal("0.90") * Decimal("1.18")
    assert abs(result.total_amount - float(expected)) < 0.01


def test_pricing_service_isolated():
    """Domain service can be tested in pure isolation."""
    pricing = PricingService()
    
    products = {1: Product(id=1, name="A", price=Decimal("100"), stock=5)}
    items = [{"product_id": 1, "quantity": 3}]
    customer = Customer(id=1, name="X", tier="platinum")
    
    subtotal = pricing.calculate_subtotal(items, products)
    discounted = pricing.apply_customer_discount(subtotal, customer)
    
    # 100 * 3 = 300 → 15% off = 255
    assert subtotal == Decimal("300")
    assert discounted == Decimal("255")
```

> **Key difference**: Onion's **PricingService** is pure logic — can be tested without ANY mocks!

---

## 7. When To Choose Which (Practical)

### Choose CLEAN When:

```python
# Your code reads like:
class PlaceOrder:
    def execute(self, request):
        # Use case-driven thinking
        ...

class RegisterUser:
    def execute(self, request):
        ...

# Each "Use Case" is a clear application behavior
```

### Choose ONION When:

```python
# Your code reads like:
class PricingService:
    def calculate_discount(self, customer, product):
        # Domain-driven thinking
        ...

class OrderAggregate:
    def add_line_item(self, product, qty):
        # Rich domain model
        ...

# Domain is rich; many cross-entity rules
```

### Hybrid (Most Real Projects)

```python
# Mix of both!
src/
├── domain/
│   ├── model/          # Onion-style entities (aggregates)
│   ├── services/        # Onion-style domain services
│   └── repositories/    # Interfaces
├── application/
│   ├── use_cases/      # Clean-style use cases
│   └── dtos/
└── infrastructure/
    ├── web/
    ├── persistence/
    └── external/
```

**Best of both worlds!** Many production systems do this.

---

## 8. Running Both Projects

### Clean Architecture

```bash
cd clean_arch_project
pip install -r requirements.txt
uvicorn src.frameworks_drivers.web.fastapi_app:app --reload --port 8001

# Test
curl -X POST http://localhost:8001/orders \
  -H "Content-Type: application/json" \
  -d '{"customer_id": 1, "items": [{"product_id": 1, "quantity": 2}], "payment_method": "stripe"}'
```

### Onion Architecture

```bash
cd onion_arch_project
pip install -r requirements.txt
uvicorn src.infrastructure.web.controllers.order_controller:app --reload --port 8002

# Test
curl -X POST http://localhost:8002/orders \
  -H "Content-Type: application/json" \
  -d '{"customer_id": 1, "items": [{"product_id": 1, "quantity": 2}], "payment_method": "stripe"}'
```

Both should produce **same result** — just structured differently internally.

---

## 9. Summary

```
✅ Both Clean & Onion: Domain at center, dependencies inward
✅ Clean: Use case-focused, prescriptive layers
✅ Onion: Domain-focused, DDD-aligned
✅ In practice: Many projects blend both
✅ The CORE PRINCIPLE matters more than the SPECIFIC PATTERN
```

### Quick Decision Framework

```
Q: Is your domain rich and complex (e.g., financial, logistics)?
   → Onion

Q: Is your domain simpler but you have many use cases?
   → Clean

Q: In doubt?
   → Hybrid — use whatever names fit your team
```

### Most Important Takeaway

> **Whichever architecture you choose, ALWAYS protect your domain.**

That's where the real value of your system lives.

---

## 10. Action Items

1. ✅ **Implement same use case** in Clean style
2. ✅ **Implement same use case** in Onion style
3. ✅ **Compare** the resulting folder + code structure
4. ✅ **Decide** which fits your current/next project
5. ✅ **Or blend** elements of both based on context

---

## 11. Related Resources

- [Phase2_FastAPI/12_clean_architecture_ddd.md](../../Phase2_FastAPI/12_clean_architecture_ddd.md)
- [PythonBackend_SystemDesign/LLD_Theory/](../../PythonBackend_SystemDesign/LLD_Theory/) — Design patterns
- [Section_02 Lecture 2 Practical](02_Practical_Hands_On.md) — Hexagonal example
- Book: "Clean Architecture" by Robert C. Martin
- Book: "Get Your Hands Dirty on Clean Architecture" by Tom Hombergs
