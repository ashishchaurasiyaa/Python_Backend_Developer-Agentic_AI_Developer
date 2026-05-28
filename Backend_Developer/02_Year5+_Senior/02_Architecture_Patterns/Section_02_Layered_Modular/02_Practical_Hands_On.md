# Lecture 2 — Practical Hands-On: Building a Hexagonal App

> **Theory file:** [02_Hexagonal_Architecture.md](02_Hexagonal_Architecture.md)

---

## 🎯 Is Practical Mein Kya Banayenge?

Ek **fully working hexagonal "Place Order" app** with:

1. ✅ **Pure domain core** (zero framework dependencies)
2. ✅ **Multiple inbound adapters** (REST, CLI, gRPC)
3. ✅ **Multiple outbound adapters** (PostgreSQL, In-Memory, Stripe, Mock)
4. ✅ **Adapter switching** at runtime via configuration
5. ✅ **Fast unit tests** (no DB, no network)
6. ✅ **Integration tests** (real adapters)
7. ✅ **Dependency injection** pattern in Python

By end: aap **production-grade hexagonal architecture** likhna seekh jaoge.

---

## 1. Project Structure

### Folder Layout (Mirrors Architecture)

```
hexagonal_order_app/
├── pyproject.toml
├── docker-compose.yml
├── README.md
│
├── src/
│   ├── __init__.py
│   │
│   ├── core/                      # 🟪 THE HEART (pure logic)
│   │   ├── __init__.py
│   │   ├── domain/                # Domain entities + value objects
│   │   │   ├── order.py
│   │   │   ├── product.py
│   │   │   ├── customer.py
│   │   │   └── money.py
│   │   ├── ports/                 # Interfaces (contracts)
│   │   │   ├── inbound/           # Driver ports (use cases)
│   │   │   │   ├── place_order.py
│   │   │   │   ├── cancel_order.py
│   │   │   │   └── get_order.py
│   │   │   └── outbound/          # Driven ports
│   │   │       ├── order_repository.py
│   │   │       ├── product_repository.py
│   │   │       ├── payment_gateway.py
│   │   │       ├── notification_service.py
│   │   │       └── event_publisher.py
│   │   ├── use_cases/             # Implementations of inbound ports
│   │   │   ├── place_order.py
│   │   │   ├── cancel_order.py
│   │   │   └── get_order.py
│   │   └── exceptions.py
│   │
│   ├── adapters/                  # 🔄 OUTSIDE THE CORE
│   │   ├── inbound/               # Adapters that call core
│   │   │   ├── rest/              # FastAPI REST adapter
│   │   │   │   ├── main.py
│   │   │   │   ├── routers/
│   │   │   │   └── schemas/
│   │   │   ├── cli/               # CLI adapter
│   │   │   │   └── commands.py
│   │   │   └── grpc/              # gRPC adapter
│   │   │       └── server.py
│   │   └── outbound/              # Adapters called by core
│   │       ├── persistence/
│   │       │   ├── postgres/      # Real PostgreSQL adapter
│   │       │   │   ├── order_repository.py
│   │       │   │   └── product_repository.py
│   │       │   └── in_memory/     # Test/dev in-memory adapter
│   │       │       ├── order_repository.py
│   │       │       └── product_repository.py
│   │       ├── payment/
│   │       │   ├── stripe_adapter.py
│   │       │   ├── razorpay_adapter.py
│   │       │   └── mock_adapter.py
│   │       ├── notification/
│   │       │   ├── sendgrid_adapter.py
│   │       │   └── console_adapter.py
│   │       └── event/
│   │           ├── kafka_publisher.py
│   │           └── in_memory_publisher.py
│   │
│   └── composition_root.py        # Wire everything together
│
└── tests/
    ├── unit/                      # Test core only (fake adapters)
    │   ├── test_place_order.py
    │   └── test_cancel_order.py
    └── integration/               # Test with real adapters
        ├── test_postgres_repo.py
        └── test_stripe_adapter.py
```

> **Notice:** Folder structure makes hexagonal architecture **immediately visible**.

---

## 2. 🟪 The Core (Pure Domain)

### Domain Entities (Pure Python)

```python
# src/core/domain/money.py
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Money:
    """Value object — immutable, no dependencies."""
    amount: Decimal
    currency: str = "INR"

    def __post_init__(self):
        if self.amount < 0:
            raise ValueError("Amount cannot be negative")

    def add(self, other: "Money") -> "Money":
        if self.currency != other.currency:
            raise ValueError(f"Cannot add {self.currency} and {other.currency}")
        return Money(self.amount + other.amount, self.currency)

    def multiply(self, factor: int) -> "Money":
        return Money(self.amount * factor, self.currency)

    def __str__(self) -> str:
        return f"{self.amount} {self.currency}"
```

```python
# src/core/domain/product.py
from dataclasses import dataclass
from src.core.domain.money import Money


@dataclass
class Product:
    """Domain entity — pure Python, no framework."""
    id: int
    name: str
    price: Money
    stock: int

    def has_stock(self, quantity: int) -> bool:
        return self.stock >= quantity

    def reserve(self, quantity: int) -> None:
        if not self.has_stock(quantity):
            raise ValueError(f"Insufficient stock for {self.name}")
        self.stock -= quantity
```

```python
# src/core/domain/order.py
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List
from uuid import UUID, uuid4

from src.core.domain.money import Money


class OrderStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    DELIVERED = "delivered"


@dataclass
class OrderLine:
    product_id: int
    product_name: str
    quantity: int
    unit_price: Money

    def line_total(self) -> Money:
        return self.unit_price.multiply(self.quantity)


@dataclass
class Order:
    """Aggregate root — encapsulates business invariants."""
    id: UUID
    customer_id: int
    lines: List[OrderLine]
    status: OrderStatus
    total: Money
    payment_id: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)

    @classmethod
    def create(
        cls,
        customer_id: int,
        lines: List[OrderLine],
    ) -> "Order":
        """Factory method enforcing invariants."""
        if not lines:
            raise ValueError("Order must have at least one line")

        # Calculate total
        total = Money(amount=lines[0].unit_price.amount * 0)  # Zero of same currency
        for line in lines:
            total = total.add(line.line_total())

        return cls(
            id=uuid4(),
            customer_id=customer_id,
            lines=lines,
            status=OrderStatus.PENDING,
            total=total,
        )

    def confirm(self, payment_id: str) -> None:
        """Business rule: only pending orders can be confirmed."""
        if self.status != OrderStatus.PENDING:
            raise ValueError(f"Cannot confirm order in status {self.status}")
        self.status = OrderStatus.CONFIRMED
        self.payment_id = payment_id

    def cancel(self) -> None:
        if self.status == OrderStatus.DELIVERED:
            raise ValueError("Cannot cancel delivered order")
        self.status = OrderStatus.CANCELLED
```

### Core Exceptions

```python
# src/core/exceptions.py
class CoreException(Exception):
    """Base exception for core logic."""


class ProductNotFound(CoreException):
    pass


class OrderNotFound(CoreException):
    pass


class InsufficientStock(CoreException):
    pass


class PaymentFailed(CoreException):
    pass
```

### Inbound Ports (Use Case Interfaces)

```python
# src/core/ports/inbound/place_order.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List
from uuid import UUID


@dataclass
class OrderItemRequest:
    product_id: int
    quantity: int


@dataclass
class PlaceOrderRequest:
    customer_id: int
    items: List[OrderItemRequest]
    payment_method: str  # "stripe", "razorpay", "mock"


@dataclass
class PlaceOrderResponse:
    order_id: UUID
    status: str
    total_amount: float
    payment_id: str


class PlaceOrderUseCase(ABC):
    """Inbound port — interface for placing an order."""

    @abstractmethod
    def execute(self, request: PlaceOrderRequest) -> PlaceOrderResponse:
        """Execute place order use case."""
```

### Outbound Ports

```python
# src/core/ports/outbound/order_repository.py
from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from src.core.domain.order import Order


class OrderRepository(ABC):
    """Outbound port — what core needs from data layer."""

    @abstractmethod
    def save(self, order: Order) -> None: ...

    @abstractmethod
    def get(self, order_id: UUID) -> Optional[Order]: ...

    @abstractmethod
    def find_by_customer(self, customer_id: int) -> list[Order]: ...
```

```python
# src/core/ports/outbound/product_repository.py
from abc import ABC, abstractmethod
from typing import Optional, List

from src.core.domain.product import Product


class ProductRepository(ABC):
    @abstractmethod
    def get(self, product_id: int) -> Optional[Product]: ...

    @abstractmethod
    def get_many(self, product_ids: List[int]) -> List[Product]: ...

    @abstractmethod
    def save(self, product: Product) -> None: ...
```

```python
# src/core/ports/outbound/payment_gateway.py
from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.core.domain.money import Money


@dataclass
class PaymentResult:
    success: bool
    payment_id: str
    error_message: str = ""


class PaymentGateway(ABC):
    """Outbound port — payment provider abstraction."""

    @abstractmethod
    def charge(
        self,
        customer_id: int,
        amount: Money,
        idempotency_key: str,
    ) -> PaymentResult: ...

    @abstractmethod
    def refund(self, payment_id: str, amount: Money) -> PaymentResult: ...
```

```python
# src/core/ports/outbound/notification_service.py
from abc import ABC, abstractmethod
from uuid import UUID


class NotificationService(ABC):
    @abstractmethod
    def notify_order_placed(self, customer_id: int, order_id: UUID) -> None: ...

    @abstractmethod
    def notify_payment_failed(self, customer_id: int, order_id: UUID, reason: str) -> None: ...
```

### Use Case Implementation (The Heart!)

```python
# src/core/use_cases/place_order.py
from uuid import uuid4
import logging
from typing import List

from src.core.domain.order import Order, OrderLine
from src.core.domain.money import Money
from src.core.exceptions import ProductNotFound, InsufficientStock, PaymentFailed
from src.core.ports.inbound.place_order import (
    PlaceOrderUseCase,
    PlaceOrderRequest,
    PlaceOrderResponse,
)
from src.core.ports.outbound.order_repository import OrderRepository
from src.core.ports.outbound.product_repository import ProductRepository
from src.core.ports.outbound.payment_gateway import PaymentGateway
from src.core.ports.outbound.notification_service import NotificationService


logger = logging.getLogger(__name__)


class PlaceOrder(PlaceOrderUseCase):
    """
    THE CORE USE CASE.
    
    Notice:
    - No HTTP knowledge
    - No SQL knowledge
    - No framework dependencies
    - Just business logic + port interfaces
    """

    def __init__(
        self,
        order_repo: OrderRepository,         # Outbound port
        product_repo: ProductRepository,     # Outbound port
        payment_gateway: PaymentGateway,     # Outbound port
        notification_service: NotificationService,  # Outbound port
    ):
        self.order_repo = order_repo
        self.product_repo = product_repo
        self.payment_gateway = payment_gateway
        self.notification_service = notification_service

    def execute(self, request: PlaceOrderRequest) -> PlaceOrderResponse:
        # 1. Load products (outbound port)
        product_ids = [item.product_id for item in request.items]
        products = self.product_repo.get_many(product_ids)
        product_dict = {p.id: p for p in products}

        # 2. Validate all products exist
        for item in request.items:
            if item.product_id not in product_dict:
                raise ProductNotFound(f"Product {item.product_id} not found")

        # 3. Check stock + build order lines
        lines: List[OrderLine] = []
        for item in request.items:
            product = product_dict[item.product_id]
            if not product.has_stock(item.quantity):
                raise InsufficientStock(
                    f"Insufficient stock for {product.name}: requested {item.quantity}, have {product.stock}"
                )
            lines.append(OrderLine(
                product_id=product.id,
                product_name=product.name,
                quantity=item.quantity,
                unit_price=product.price,
            ))

        # 4. Create order (domain logic)
        order = Order.create(
            customer_id=request.customer_id,
            lines=lines,
        )

        # 5. Save order (outbound port)
        self.order_repo.save(order)

        # 6. Charge payment (outbound port)
        payment_result = self.payment_gateway.charge(
            customer_id=request.customer_id,
            amount=order.total,
            idempotency_key=str(order.id),
        )

        if not payment_result.success:
            # Notify failure
            self.notification_service.notify_payment_failed(
                request.customer_id,
                order.id,
                payment_result.error_message,
            )
            raise PaymentFailed(payment_result.error_message)

        # 7. Confirm order + reserve stock
        order.confirm(payment_result.payment_id)
        for item in request.items:
            product = product_dict[item.product_id]
            product.reserve(item.quantity)
            self.product_repo.save(product)

        self.order_repo.save(order)

        # 8. Notify success
        self.notification_service.notify_order_placed(
            request.customer_id,
            order.id,
        )

        # 9. Return response
        return PlaceOrderResponse(
            order_id=order.id,
            status=order.status.value,
            total_amount=float(order.total.amount),
            payment_id=order.payment_id,
        )
```

> **Notice:** This file has **ZERO** dependency on FastAPI, SQLAlchemy, Stripe SDK, or anything else. Pure logic.

---

## 3. 🔄 Outbound Adapters

### A. PostgreSQL Adapter (Production)

```python
# src/adapters/outbound/persistence/postgres/order_repository.py
from typing import Optional, List
from uuid import UUID
import json
from sqlalchemy import Column, String, JSON, DateTime
from sqlalchemy.orm import declarative_base, Session
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from datetime import datetime

from src.core.domain.order import Order, OrderLine, OrderStatus
from src.core.domain.money import Money
from src.core.ports.outbound.order_repository import OrderRepository


Base = declarative_base()


class OrderModel(Base):
    """SQLAlchemy model — INTERNAL to this adapter."""
    __tablename__ = "orders"

    id = Column(PgUUID(as_uuid=True), primary_key=True)
    customer_id = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False)
    lines = Column(JSON, nullable=False)
    total_amount = Column(String, nullable=False)
    currency = Column(String, nullable=False)
    payment_id = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class PostgresOrderRepository(OrderRepository):
    """Implements OrderRepository port using PostgreSQL."""

    def __init__(self, session: Session):
        self.session = session

    def save(self, order: Order) -> None:
        model = OrderModel(
            id=order.id,
            customer_id=str(order.customer_id),
            status=order.status.value,
            lines=[
                {
                    "product_id": line.product_id,
                    "product_name": line.product_name,
                    "quantity": line.quantity,
                    "unit_price_amount": str(line.unit_price.amount),
                    "unit_price_currency": line.unit_price.currency,
                }
                for line in order.lines
            ],
            total_amount=str(order.total.amount),
            currency=order.total.currency,
            payment_id=order.payment_id,
            created_at=order.created_at,
        )
        # Upsert
        self.session.merge(model)
        self.session.flush()

    def get(self, order_id: UUID) -> Optional[Order]:
        model = self.session.query(OrderModel).filter(OrderModel.id == order_id).first()
        if not model:
            return None
        return self._to_domain(model)

    def find_by_customer(self, customer_id: int) -> list[Order]:
        models = self.session.query(OrderModel).filter(
            OrderModel.customer_id == str(customer_id)
        ).all()
        return [self._to_domain(m) for m in models]

    def _to_domain(self, model: OrderModel) -> Order:
        """Map DB model to domain entity."""
        from decimal import Decimal
        lines = [
            OrderLine(
                product_id=line["product_id"],
                product_name=line["product_name"],
                quantity=line["quantity"],
                unit_price=Money(
                    amount=Decimal(line["unit_price_amount"]),
                    currency=line["unit_price_currency"],
                ),
            )
            for line in model.lines
        ]
        return Order(
            id=model.id,
            customer_id=int(model.customer_id),
            lines=lines,
            status=OrderStatus(model.status),
            total=Money(amount=Decimal(model.total_amount), currency=model.currency),
            payment_id=model.payment_id,
            created_at=model.created_at,
        )
```

### B. In-Memory Adapter (For Tests + Dev)

```python
# src/adapters/outbound/persistence/in_memory/order_repository.py
from typing import Optional, List
from uuid import UUID

from src.core.domain.order import Order
from src.core.ports.outbound.order_repository import OrderRepository


class InMemoryOrderRepository(OrderRepository):
    """In-memory implementation — perfect for tests."""

    def __init__(self):
        self.orders: dict[UUID, Order] = {}

    def save(self, order: Order) -> None:
        self.orders[order.id] = order

    def get(self, order_id: UUID) -> Optional[Order]:
        return self.orders.get(order_id)

    def find_by_customer(self, customer_id: int) -> List[Order]:
        return [o for o in self.orders.values() if o.customer_id == customer_id]

    def clear(self):
        """Test helper."""
        self.orders.clear()
```

### C. Stripe Payment Adapter

```python
# src/adapters/outbound/payment/stripe_adapter.py
import stripe
import logging

from src.core.domain.money import Money
from src.core.ports.outbound.payment_gateway import PaymentGateway, PaymentResult


logger = logging.getLogger(__name__)


class StripePaymentAdapter(PaymentGateway):
    """Stripe implementation of PaymentGateway port."""

    def __init__(self, api_key: str):
        stripe.api_key = api_key

    def charge(
        self,
        customer_id: int,
        amount: Money,
        idempotency_key: str,
    ) -> PaymentResult:
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(amount.amount * 100),  # cents
                currency=amount.currency.lower(),
                customer=str(customer_id),
                idempotency_key=idempotency_key,
            )
            return PaymentResult(
                success=True,
                payment_id=intent.id,
            )
        except stripe.error.CardError as e:
            logger.warning(f"Card declined: {e.user_message}")
            return PaymentResult(
                success=False,
                payment_id="",
                error_message=e.user_message,
            )
        except Exception as e:
            logger.exception("Stripe charge failed")
            return PaymentResult(
                success=False,
                payment_id="",
                error_message=str(e),
            )

    def refund(self, payment_id: str, amount: Money) -> PaymentResult:
        try:
            refund = stripe.Refund.create(
                payment_intent=payment_id,
                amount=int(amount.amount * 100),
            )
            return PaymentResult(success=True, payment_id=refund.id)
        except Exception as e:
            return PaymentResult(
                success=False,
                payment_id="",
                error_message=str(e),
            )
```

### D. Mock Payment Adapter (For Tests)

```python
# src/adapters/outbound/payment/mock_adapter.py
from uuid import uuid4

from src.core.domain.money import Money
from src.core.ports.outbound.payment_gateway import PaymentGateway, PaymentResult


class MockPaymentAdapter(PaymentGateway):
    """Mock payment — for tests + development."""

    def __init__(self, always_succeed: bool = True):
        self.always_succeed = always_succeed
        self.charges = []  # Recording for assertions

    def charge(
        self,
        customer_id: int,
        amount: Money,
        idempotency_key: str,
    ) -> PaymentResult:
        self.charges.append({
            "customer_id": customer_id,
            "amount": amount,
            "idempotency_key": idempotency_key,
        })

        if self.always_succeed:
            return PaymentResult(
                success=True,
                payment_id=f"mock-{uuid4().hex[:8]}",
            )
        return PaymentResult(
            success=False,
            payment_id="",
            error_message="Mock payment failure",
        )

    def refund(self, payment_id: str, amount: Money) -> PaymentResult:
        return PaymentResult(success=True, payment_id=f"refund-{payment_id}")
```

### E. Console Notification Adapter

```python
# src/adapters/outbound/notification/console_adapter.py
from uuid import UUID
import logging

from src.core.ports.outbound.notification_service import NotificationService


logger = logging.getLogger(__name__)


class ConsoleNotificationAdapter(NotificationService):
    """Notification adapter that just logs — for dev."""

    def notify_order_placed(self, customer_id: int, order_id: UUID) -> None:
        logger.info(f"📦 Order {order_id} placed for customer {customer_id}")

    def notify_payment_failed(self, customer_id: int, order_id: UUID, reason: str) -> None:
        logger.warning(f"❌ Payment failed for order {order_id}: {reason}")
```

---

## 4. 📡 Inbound Adapters

### A. REST API Adapter (FastAPI)

```python
# src/adapters/inbound/rest/main.py
from fastapi import FastAPI, Depends, HTTPException
from typing import List
from pydantic import BaseModel
from uuid import UUID

from src.core.ports.inbound.place_order import (
    PlaceOrderUseCase,
    PlaceOrderRequest,
    OrderItemRequest,
)
from src.core.exceptions import (
    ProductNotFound,
    InsufficientStock,
    PaymentFailed,
)
from src.composition_root import get_place_order_use_case


app = FastAPI(title="Hexagonal Order App")


class OrderItemSchema(BaseModel):
    product_id: int
    quantity: int


class PlaceOrderSchema(BaseModel):
    customer_id: int
    items: List[OrderItemSchema]
    payment_method: str = "stripe"


class OrderResponseSchema(BaseModel):
    order_id: UUID
    status: str
    total_amount: float
    payment_id: str


@app.post("/orders", response_model=OrderResponseSchema, status_code=201)
def place_order(
    request: PlaceOrderSchema,
    use_case: PlaceOrderUseCase = Depends(get_place_order_use_case),
):
    """REST adapter — translates HTTP to use case call."""
    try:
        # Map HTTP DTO → core DTO
        core_request = PlaceOrderRequest(
            customer_id=request.customer_id,
            items=[
                OrderItemRequest(product_id=i.product_id, quantity=i.quantity)
                for i in request.items
            ],
            payment_method=request.payment_method,
        )

        # Call use case (inbound port)
        result = use_case.execute(core_request)

        # Map core DTO → HTTP response
        return OrderResponseSchema(
            order_id=result.order_id,
            status=result.status,
            total_amount=result.total_amount,
            payment_id=result.payment_id,
        )

    except ProductNotFound as e:
        raise HTTPException(404, str(e))
    except InsufficientStock as e:
        raise HTTPException(400, str(e))
    except PaymentFailed as e:
        raise HTTPException(402, str(e))
```

### B. CLI Adapter

```python
# src/adapters/inbound/cli/commands.py
import argparse
import sys
import json

from src.core.ports.inbound.place_order import (
    PlaceOrderRequest,
    OrderItemRequest,
)
from src.core.exceptions import CoreException
from src.composition_root import get_place_order_use_case


def main():
    parser = argparse.ArgumentParser(description="Order CLI")
    subparsers = parser.add_subparsers(dest="command")

    # Place order command
    place = subparsers.add_parser("place-order")
    place.add_argument("--customer-id", type=int, required=True)
    place.add_argument("--items-json", required=True,
                       help='JSON: [{"product_id": 1, "quantity": 2}]')
    place.add_argument("--payment", default="mock")

    args = parser.parse_args()

    if args.command == "place-order":
        items = json.loads(args.items_json)
        request = PlaceOrderRequest(
            customer_id=args.customer_id,
            items=[OrderItemRequest(**i) for i in items],
            payment_method=args.payment,
        )

        use_case = get_place_order_use_case()
        try:
            result = use_case.execute(request)
            print(f"✅ Order placed: {result.order_id}")
            print(f"   Status: {result.status}")
            print(f"   Total: {result.total_amount}")
            print(f"   Payment: {result.payment_id}")
        except CoreException as e:
            print(f"❌ Error: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
```

**Usage:**
```bash
python -m src.adapters.inbound.cli.commands place-order \
  --customer-id 1 \
  --items-json '[{"product_id": 1, "quantity": 2}]' \
  --payment mock
```

### C. gRPC Adapter (Bonus)

```python
# src/adapters/inbound/grpc/server.py
import grpc
from concurrent import futures
# Assume generated from .proto
from src.adapters.inbound.grpc import orders_pb2_grpc, orders_pb2

from src.composition_root import get_place_order_use_case
from src.core.ports.inbound.place_order import PlaceOrderRequest, OrderItemRequest
from src.core.exceptions import CoreException


class OrderServiceServicer(orders_pb2_grpc.OrderServiceServicer):
    """gRPC adapter — same use case, different protocol."""

    def PlaceOrder(self, request, context):
        try:
            core_request = PlaceOrderRequest(
                customer_id=request.customer_id,
                items=[
                    OrderItemRequest(product_id=i.product_id, quantity=i.quantity)
                    for i in request.items
                ],
                payment_method=request.payment_method or "stripe",
            )

            use_case = get_place_order_use_case()
            result = use_case.execute(core_request)

            return orders_pb2.OrderResponse(
                order_id=str(result.order_id),
                status=result.status,
                total_amount=result.total_amount,
                payment_id=result.payment_id,
            )
        except CoreException as e:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(e))


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    orders_pb2_grpc.add_OrderServiceServicer_to_server(
        OrderServiceServicer(), server
    )
    server.add_insecure_port("[::]:50051")
    server.start()
    print("gRPC server started on :50051")
    server.wait_for_termination()
```

---

## 5. 🔌 Composition Root (Wire It All)

```python
# src/composition_root.py
"""
Composition root — wires adapters to ports at runtime.
This is the ONLY place that knows about both core and adapters.
"""

import os
from functools import lru_cache
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from src.core.use_cases.place_order import PlaceOrder
from src.core.ports.inbound.place_order import PlaceOrderUseCase

# Adapters (production)
from src.adapters.outbound.persistence.postgres.order_repository import PostgresOrderRepository
from src.adapters.outbound.persistence.postgres.product_repository import PostgresProductRepository
from src.adapters.outbound.payment.stripe_adapter import StripePaymentAdapter
from src.adapters.outbound.notification.console_adapter import ConsoleNotificationAdapter

# Adapters (dev/test)
from src.adapters.outbound.persistence.in_memory.order_repository import InMemoryOrderRepository
from src.adapters.outbound.persistence.in_memory.product_repository import InMemoryProductRepository
from src.adapters.outbound.payment.mock_adapter import MockPaymentAdapter


def get_db_session() -> Session:
    """Get a SQLAlchemy session."""
    DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://localhost/orders")
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


@lru_cache()
def get_place_order_use_case() -> PlaceOrderUseCase:
    """
    Wire up the use case with appropriate adapters.
    Switch implementations based on environment!
    """
    env = os.environ.get("APP_ENV", "production")

    if env == "production":
        session = get_db_session()
        order_repo = PostgresOrderRepository(session)
        product_repo = PostgresProductRepository(session)
        payment = StripePaymentAdapter(os.environ["STRIPE_API_KEY"])
        notifier = ConsoleNotificationAdapter()  # Replace with SendGrid in real prod
    
    elif env == "development":
        # In-memory for fast dev iteration
        order_repo = InMemoryOrderRepository()
        product_repo = InMemoryProductRepository()
        payment = MockPaymentAdapter(always_succeed=True)
        notifier = ConsoleNotificationAdapter()
    
    else:  # test
        order_repo = InMemoryOrderRepository()
        product_repo = InMemoryProductRepository()
        payment = MockPaymentAdapter()
        notifier = ConsoleNotificationAdapter()

    return PlaceOrder(
        order_repo=order_repo,
        product_repo=product_repo,
        payment_gateway=payment,
        notification_service=notifier,
    )
```

> **The wiring** is the ONLY place that knows both core and adapters. Domain logic stays clean.

---

## 6. 🧪 Tests

### Fast Unit Test (Pure Core, No DB)

```python
# tests/unit/test_place_order.py
import pytest
from decimal import Decimal
from uuid import uuid4

from src.core.domain.product import Product
from src.core.domain.money import Money
from src.core.use_cases.place_order import PlaceOrder
from src.core.ports.inbound.place_order import (
    PlaceOrderRequest,
    OrderItemRequest,
)
from src.core.exceptions import ProductNotFound, InsufficientStock, PaymentFailed

# Fake adapters
from src.adapters.outbound.persistence.in_memory.order_repository import InMemoryOrderRepository
from src.adapters.outbound.persistence.in_memory.product_repository import InMemoryProductRepository
from src.adapters.outbound.payment.mock_adapter import MockPaymentAdapter
from src.adapters.outbound.notification.console_adapter import ConsoleNotificationAdapter


@pytest.fixture
def use_case():
    """Build use case with FAKE adapters — no real DB, no Stripe."""
    order_repo = InMemoryOrderRepository()
    product_repo = InMemoryProductRepository()
    
    # Seed test products
    product_repo.save(Product(
        id=1,
        name="iPhone",
        price=Money(Decimal("80000")),
        stock=10,
    ))
    product_repo.save(Product(
        id=2,
        name="AirPods",
        price=Money(Decimal("20000")),
        stock=5,
    ))
    
    payment = MockPaymentAdapter(always_succeed=True)
    notifier = ConsoleNotificationAdapter()
    
    return PlaceOrder(
        order_repo=order_repo,
        product_repo=product_repo,
        payment_gateway=payment,
        notification_service=notifier,
    ), product_repo, order_repo, payment


def test_place_order_success(use_case):
    """Happy path test — NO DATABASE NEEDED!"""
    uc, product_repo, order_repo, payment = use_case
    
    request = PlaceOrderRequest(
        customer_id=1,
        items=[
            OrderItemRequest(product_id=1, quantity=2),
            OrderItemRequest(product_id=2, quantity=1),
        ],
        payment_method="mock",
    )
    
    result = uc.execute(request)
    
    # Verify
    assert result.status == "confirmed"
    assert result.total_amount == 180000.0  # 80000*2 + 20000*1
    assert result.payment_id.startswith("mock-")
    
    # Verify order saved
    saved_order = order_repo.get(result.order_id)
    assert saved_order is not None
    assert saved_order.customer_id == 1
    
    # Verify stock decremented
    assert product_repo.get(1).stock == 8  # 10 - 2
    assert product_repo.get(2).stock == 4  # 5 - 1
    
    # Verify payment called
    assert len(payment.charges) == 1


def test_place_order_product_not_found(use_case):
    uc, _, _, _ = use_case
    
    request = PlaceOrderRequest(
        customer_id=1,
        items=[OrderItemRequest(product_id=999, quantity=1)],
        payment_method="mock",
    )
    
    with pytest.raises(ProductNotFound):
        uc.execute(request)


def test_place_order_insufficient_stock(use_case):
    uc, _, _, _ = use_case
    
    request = PlaceOrderRequest(
        customer_id=1,
        items=[OrderItemRequest(product_id=1, quantity=999)],
        payment_method="mock",
    )
    
    with pytest.raises(InsufficientStock):
        uc.execute(request)


def test_place_order_payment_failure():
    """Test when payment fails."""
    order_repo = InMemoryOrderRepository()
    product_repo = InMemoryProductRepository()
    product_repo.save(Product(id=1, name="iPhone", price=Money(Decimal("80000")), stock=10))
    
    # Payment ALWAYS fails
    payment = MockPaymentAdapter(always_succeed=False)
    notifier = ConsoleNotificationAdapter()
    
    uc = PlaceOrder(
        order_repo=order_repo,
        product_repo=product_repo,
        payment_gateway=payment,
        notification_service=notifier,
    )
    
    request = PlaceOrderRequest(
        customer_id=1,
        items=[OrderItemRequest(product_id=1, quantity=1)],
        payment_method="mock",
    )
    
    with pytest.raises(PaymentFailed):
        uc.execute(request)
    
    # Stock should NOT be decremented on payment failure
    assert product_repo.get(1).stock == 10
```

**Run:** `pytest tests/unit/ -v` → **runs in milliseconds!**

### Integration Test (Real DB)

```python
# tests/integration/test_postgres_repo.py
import pytest
from uuid import uuid4
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.domain.order import Order, OrderLine, OrderStatus
from src.core.domain.money import Money
from src.adapters.outbound.persistence.postgres.order_repository import (
    PostgresOrderRepository,
    Base,
)


@pytest.fixture(scope="module")
def db_session():
    """Real PostgreSQL test DB."""
    engine = create_engine("postgresql://test:test@localhost:5432/orders_test")
    Base.metadata.create_all(engine)
    
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    yield session
    
    # Cleanup
    Base.metadata.drop_all(engine)
    session.close()


def test_save_and_retrieve_order(db_session):
    repo = PostgresOrderRepository(db_session)
    
    order = Order.create(
        customer_id=1,
        lines=[OrderLine(
            product_id=1,
            product_name="Test",
            quantity=2,
            unit_price=Money(Decimal("100")),
        )],
    )
    
    repo.save(order)
    db_session.commit()
    
    retrieved = repo.get(order.id)
    assert retrieved is not None
    assert retrieved.customer_id == 1
    assert len(retrieved.lines) == 1
    assert retrieved.total.amount == Decimal("200")
```

**Run:** `pytest tests/integration/ -v` → slower, real DB needed.

---

## 7. Running The App

### Setup

```bash
# 1. Install
pip install -r requirements.txt

# 2. Environment variables
cat > .env <<EOF
APP_ENV=development
STRIPE_API_KEY=sk_test_xxx
DATABASE_URL=postgresql://user:pass@localhost/orders
EOF

# 3. Start DB (if production)
docker-compose up -d postgres

# 4. Run REST API
uvicorn src.adapters.inbound.rest.main:app --reload --port 8000

# 5. OR Run CLI
python -m src.adapters.inbound.cli.commands place-order \
  --customer-id 1 \
  --items-json '[{"product_id":1,"quantity":2}]'

# 6. OR Run gRPC
python -m src.adapters.inbound.grpc.server
```

### Test REST

```bash
curl -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": 1,
    "items": [
      {"product_id": 1, "quantity": 2}
    ],
    "payment_method": "mock"
  }'
```

---

## 8. Switching Adapters at Runtime

The **power of hexagonal**: change behavior without touching code.

### Example: Production vs Dev

```bash
# Development (in-memory, no DB)
APP_ENV=development uvicorn src.adapters.inbound.rest.main:app

# Production (PostgreSQL + Stripe)
APP_ENV=production uvicorn src.adapters.inbound.rest.main:app

# Tests (in-memory, mock payment)
APP_ENV=test pytest
```

**Same code, different adapters, different behavior.**

### Example: Multi-Region Payment

```python
# Could even switch by customer country
def get_payment_for_customer(country: str) -> PaymentGateway:
    if country == "IN":
        return RazorpayAdapter()
    elif country == "US":
        return StripeAdapter()
    else:
        return PayPalAdapter()
```

---

## 9. Common Mistakes

### Mistake 1: Domain Knows About Framework

```python
# ❌ BAD — domain imports FastAPI
from fastapi import HTTPException

class PlaceOrder:
    def execute(self, request):
        if not request.items:
            raise HTTPException(400, "No items")  # ❌ Framework leak!

# ✅ GOOD — domain has its own exceptions
class PlaceOrder:
    def execute(self, request):
        if not request.items:
            raise InvalidOrder("No items")  # ✅ Core exception
# Adapter translates to HTTPException
```

### Mistake 2: Adapter Bypassing Port

```python
# ❌ BAD — use case directly creates adapter
class PlaceOrder:
    def execute(self, request):
        repo = PostgresOrderRepository(...)  # ❌ Direct dependency!
        ...

# ✅ GOOD — receive port via DI
class PlaceOrder:
    def __init__(self, repo: OrderRepository):
        self.repo = repo  # ✅ Abstract port
```

### Mistake 3: Leaky Domain Models

```python
# ❌ BAD — domain has DB column annotations
from sqlalchemy import Column, Integer

class Order:  # ❌ SQLAlchemy in domain!
    id = Column(Integer)
    ...

# ✅ GOOD — domain is pure Python
@dataclass
class Order:
    id: UUID  # Pure Python
```

### Mistake 4: Forgetting Composition Root

```python
# ❌ BAD — adapters created throughout code
def some_function():
    repo = PostgresOrderRepository(...)  # ❌ Spread out
    payment = StripeAdapter(...)
    use_case = PlaceOrder(repo, payment)

# ✅ GOOD — single composition root
# src/composition_root.py — ONE place to wire everything
```

---

## 10. Project Configuration Files

### pyproject.toml

```toml
[project]
name = "hexagonal-order-app"
version = "0.1.0"
dependencies = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.29",
    "sqlalchemy>=2.0",
    "psycopg2-binary>=2.9",
    "pydantic>=2.0",
    "stripe>=8.0",
    "grpcio>=1.62",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=4.1",
    "httpx>=0.27",
    "ruff>=0.3",
    "mypy>=1.9",
]
```

### docker-compose.yml

```yaml
version: '3.8'

services:
  api:
    build: .
    ports: ["8000:8000"]
    environment:
      APP_ENV: production
      DATABASE_URL: postgresql://orders:orders@postgres/orders
      STRIPE_API_KEY: ${STRIPE_API_KEY}
    depends_on: [postgres]

  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: orders
      POSTGRES_PASSWORD: orders
      POSTGRES_DB: orders
    volumes: ["pgdata:/var/lib/postgresql/data"]

volumes:
  pgdata:
```

---

## 11. Summary

```
✅ Core has NO framework / NO I/O dependencies
✅ Same use case → multiple inbound adapters (REST + CLI + gRPC)
✅ Same port → multiple outbound adapters (Postgres + In-Memory + Stripe + Mock)
✅ Tests run in MILLISECONDS (no DB, no network)
✅ Switch behavior via configuration (composition root)
```

### Action Items

1. ✅ **Clone this project structure** for your next service
2. ✅ **Write a use case** with pure domain logic
3. ✅ **Implement 2 inbound adapters** (REST + CLI)
4. ✅ **Implement 2 outbound adapters** (real + fake)
5. ✅ **Write fast unit tests** with fake adapters

---

## 12. Related Resources

- [Section_01_Foundations/02_Practical_Hands_On.md](../Section_01_Foundations/02_Practical_Hands_On.md) — Food delivery example
- [00_Year0-2_Junior/06_FastAPI/12_clean_architecture_ddd.md](../../../00_Year0-2_Junior/06_FastAPI/12_clean_architecture_ddd.md)
- [02_Year5+_Senior/01_System_Design/LLD_Theory/](../../01_System_Design/LLD_Theory) — Design patterns
- Book: "Get Your Hands Dirty on Clean Architecture" by Tom Hombergs
