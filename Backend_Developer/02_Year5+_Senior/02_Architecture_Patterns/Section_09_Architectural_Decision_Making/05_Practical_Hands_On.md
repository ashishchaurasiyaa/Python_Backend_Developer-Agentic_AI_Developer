# Lecture 5 — Practical Hands-On: DDD Foundations

> **Theory file:** [05_Domain_Driven_Design_Influence.md](05_Domain_Driven_Design_Influence.md)

---

## 🎯 Is Practical Mein Kya Banayenge?

1. ✅ **Bounded context map** — Markdown template
2. ✅ **Aggregate** in Python (Order with line items + invariants)
3. ✅ **Layered project** — domain / application / infrastructure
4. ✅ **Repository pattern** — abstract over persistence
5. ✅ **Domain events** — publish from aggregate, dispatch async
6. ✅ **Anti-corruption layer** demo

By end: aap ek complete DDD-flavored Order service banao.

---

## 1. Project Structure

```
ddd_order_service/
├── README.md
├── context_map.md
├── src/
│   ├── domain/
│   │   ├── order.py            # Aggregate root
│   │   ├── line_item.py
│   │   ├── events.py
│   │   ├── value_objects.py
│   │   └── repository.py       # interface only
│   ├── application/
│   │   ├── place_order.py
│   │   ├── ship_order.py
│   │   └── event_dispatcher.py
│   ├── infrastructure/
│   │   ├── sqlite_repo.py
│   │   ├── kafka_publisher.py
│   │   └── acl/
│   │       └── legacy_pricing_acl.py
│   └── api/
│       └── routes.py           # FastAPI endpoint
└── tests/
    ├── test_order_aggregate.py
    ├── test_place_order_uc.py
    └── test_acl.py
```

---

## 2. Bounded Context Map

### `context_map.md`

```markdown
# Bounded Context Map — E-Commerce

## Contexts

### Sales
- Concepts: Customer, Lead, Quote
- Owner team: sales-platform

### Order
- Concepts: Order, LineItem, ShippingInfo, OrderStatus
- Owner team: order-platform     ← THIS service

### Billing
- Concepts: Customer (different!), Invoice, Payment
- Owner team: payments

### Inventory
- Concepts: Product, Stock, Warehouse
- Owner team: inventory

### Notification
- Concepts: NotificationTemplate, Channel
- Owner team: comms

## Integrations

| From → To           | Style          | Reason                       |
|---------------------|----------------|------------------------------|
| Order → Inventory   | Sync (gRPC)    | Stock check before commit    |
| Order → Pricing     | Sync (REST)    | Price calc                   |
| Order → Billing     | Async event    | "OrderPlaced" → invoice gen  |
| Order → Notification| Async event    | "OrderPlaced" → confirm mail |

## ACLs

| From      | To       | Reason                              |
|-----------|----------|-------------------------------------|
| Order     | Pricing  | Legacy system uses cents + XML      |
```

---

## 3. Domain Layer — Aggregate

### `src/domain/value_objects.py`

```python
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str = "INR"

    def __add__(self, other):
        assert self.currency == other.currency
        return Money(self.amount + other.amount, self.currency)

    def __mul__(self, qty: int):
        return Money(self.amount * qty, self.currency)


@dataclass(frozen=True)
class ProductRef:
    id: str
    sku: str
```

### `src/domain/line_item.py`

```python
from dataclasses import dataclass
from .value_objects import Money, ProductRef


@dataclass
class LineItem:
    product: ProductRef
    quantity: int
    unit_price: Money

    def subtotal(self) -> Money:
        return self.unit_price * self.quantity
```

### `src/domain/events.py`

```python
from dataclasses import dataclass
from datetime import datetime
from .value_objects import Money


@dataclass(frozen=True)
class DomainEvent:
    occurred_at: datetime


@dataclass(frozen=True)
class OrderPlaced(DomainEvent):
    order_id: str
    total: Money


@dataclass(frozen=True)
class OrderShipped(DomainEvent):
    order_id: str
    tracking_number: str
```

### `src/domain/order.py`

```python
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
import uuid

from .line_item import LineItem
from .value_objects import Money, ProductRef
from .events import OrderPlaced, OrderShipped


class OrderError(Exception): ...


@dataclass
class Order:
    """Aggregate Root — only entry point to modify the cluster."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    customer_id: str = ""
    _lines: list[LineItem] = field(default_factory=list)
    _status: str = "DRAFT"      # DRAFT → PLACED → SHIPPED
    _events: list = field(default_factory=list)

    # ─── Behavior (NOT setters) ───
    def add_line(self, product: ProductRef, qty: int, price: Money):
        if self._status != "DRAFT":
            raise OrderError("Cannot modify a placed order")
        if qty <= 0:
            raise OrderError("Quantity must be positive")
        # invariant: max 50 distinct lines
        if len(self._lines) >= 50:
            raise OrderError("Max 50 line items per order")
        self._lines.append(LineItem(product, qty, price))

    def place(self):
        if self._status != "DRAFT":
            raise OrderError("Order already placed")
        if not self._lines:
            raise OrderError("Cannot place empty order")
        self._status = "PLACED"
        self._events.append(
            OrderPlaced(
                occurred_at=datetime.utcnow(),
                order_id=self.id,
                total=self.total(),
            )
        )

    def ship(self, tracking_number: str):
        if self._status != "PLACED":
            raise OrderError("Only PLACED orders can be shipped")
        self._status = "SHIPPED"
        self._events.append(
            OrderShipped(
                occurred_at=datetime.utcnow(),
                order_id=self.id,
                tracking_number=tracking_number,
            )
        )

    # ─── Queries ───
    def total(self) -> Money:
        return sum(
            (li.subtotal() for li in self._lines),
            Money(Decimal("0")),
        )

    @property
    def status(self):
        return self._status

    @property
    def lines(self):
        return tuple(self._lines)  # immutable view

    # ─── Events ───
    def pull_events(self):
        events = list(self._events)
        self._events.clear()
        return events
```

### `src/domain/repository.py`

```python
from abc import ABC, abstractmethod
from .order import Order


class OrderRepository(ABC):
    """Abstract — domain doesn't know HOW orders are stored."""

    @abstractmethod
    def get(self, order_id: str) -> Order | None: ...

    @abstractmethod
    def save(self, order: Order) -> None: ...
```

---

## 4. Application Layer — Use Cases

### `src/application/event_dispatcher.py`

```python
from collections import defaultdict


class EventDispatcher:
    """Routes domain events to subscribers."""

    def __init__(self):
        self._subs = defaultdict(list)

    def subscribe(self, event_type, handler):
        self._subs[event_type].append(handler)

    def dispatch(self, event):
        for h in self._subs[type(event)]:
            h(event)
```

### `src/application/place_order.py`

```python
from ..domain.order import Order
from ..domain.repository import OrderRepository
from .event_dispatcher import EventDispatcher


class PlaceOrderUseCase:
    """Orchestrates — NO business rules itself."""

    def __init__(self, repo: OrderRepository, events: EventDispatcher):
        self.repo = repo
        self.events = events

    def execute(self, order_id: str):
        order = self.repo.get(order_id)
        if not order:
            raise LookupError(f"order {order_id} not found")
        order.place()                  # domain enforces invariants
        self.repo.save(order)
        for e in order.pull_events():
            self.events.dispatch(e)
```

---

## 5. Infrastructure Layer — SQLite Repo

### `src/infrastructure/sqlite_repo.py`

```python
import sqlite3
import json
from decimal import Decimal

from ..domain.order import Order
from ..domain.line_item import LineItem
from ..domain.value_objects import Money, ProductRef
from ..domain.repository import OrderRepository


class SqliteOrderRepository(OrderRepository):
    def __init__(self, db_path: str = "orders.db"):
        self.conn = sqlite3.connect(db_path)
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                customer_id TEXT,
                status TEXT,
                lines TEXT  -- JSON
            );
            """
        )

    def get(self, order_id: str) -> Order | None:
        cur = self.conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        row = cur.fetchone()
        if not row:
            return None
        order = Order(id=row[0], customer_id=row[1])
        order._status = row[2]
        for li in json.loads(row[3]):
            order._lines.append(
                LineItem(
                    product=ProductRef(li["product_id"], li["sku"]),
                    quantity=li["qty"],
                    unit_price=Money(Decimal(li["price"]), li["currency"]),
                )
            )
        return order

    def save(self, order: Order):
        lines_json = json.dumps([
            {
                "product_id": li.product.id,
                "sku": li.product.sku,
                "qty": li.quantity,
                "price": str(li.unit_price.amount),
                "currency": li.unit_price.currency,
            }
            for li in order.lines
        ])
        self.conn.execute(
            """
            INSERT INTO orders (id, customer_id, status, lines)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                customer_id = excluded.customer_id,
                status      = excluded.status,
                lines       = excluded.lines
            """,
            (order.id, order.customer_id, order.status, lines_json),
        )
        self.conn.commit()
```

---

## 6. Anti-Corruption Layer

### Imagine a legacy Pricing API returns:

```xml
<priceQuoteResponse>
   <priceInCents>199500</priceInCents>
   <ccy>INR</ccy>
   <productSkuCode>SKU-001</productSkuCode>
</priceQuoteResponse>
```

### `src/infrastructure/acl/legacy_pricing_acl.py`

```python
from decimal import Decimal
import xml.etree.ElementTree as ET
from ...domain.value_objects import Money, ProductRef


class LegacyPricingClient:
    """Pretend HTTP client to a legacy XML API."""

    def fetch_price_xml(self, sku: str) -> str:
        # in real code: HTTP call; here mocked
        return f"""
        <priceQuoteResponse>
           <priceInCents>199500</priceInCents>
           <ccy>INR</ccy>
           <productSkuCode>{sku}</productSkuCode>
        </priceQuoteResponse>
        """


class PricingACL:
    """
    Anti-Corruption Layer:
    Translates legacy XML/cents into clean domain Money + ProductRef.
    """

    def __init__(self, client: LegacyPricingClient):
        self.client = client

    def get_price(self, product: ProductRef) -> Money:
        xml_str = self.client.fetch_price_xml(product.sku)
        root = ET.fromstring(xml_str)
        cents = int(root.findtext("priceInCents"))
        currency = root.findtext("ccy")
        return Money(Decimal(cents) / Decimal(100), currency)
```

---

## 7. Tests

### `tests/test_order_aggregate.py`

```python
from decimal import Decimal
import pytest

from src.domain.order import Order, OrderError
from src.domain.value_objects import Money, ProductRef
from src.domain.events import OrderPlaced


@pytest.fixture
def draft_order():
    o = Order(customer_id="c1")
    o.add_line(ProductRef("p1", "SKU-1"), 2, Money(Decimal("100")))
    o.add_line(ProductRef("p2", "SKU-2"), 1, Money(Decimal("50")))
    return o


def test_total_sums_lines(draft_order):
    assert draft_order.total() == Money(Decimal("250"))


def test_cannot_place_empty():
    o = Order()
    with pytest.raises(OrderError):
        o.place()


def test_cannot_modify_after_place(draft_order):
    draft_order.place()
    with pytest.raises(OrderError):
        draft_order.add_line(ProductRef("p3", "SKU-3"), 1, Money(Decimal("10")))


def test_place_emits_order_placed_event(draft_order):
    draft_order.place()
    events = draft_order.pull_events()
    assert len(events) == 1
    assert isinstance(events[0], OrderPlaced)
    assert events[0].total == Money(Decimal("250"))


def test_pull_events_is_idempotent(draft_order):
    draft_order.place()
    _ = draft_order.pull_events()
    assert draft_order.pull_events() == []  # no more
```

### `tests/test_place_order_uc.py`

```python
from decimal import Decimal
from src.domain.order import Order
from src.domain.value_objects import Money, ProductRef
from src.domain.events import OrderPlaced
from src.domain.repository import OrderRepository
from src.application.place_order import PlaceOrderUseCase
from src.application.event_dispatcher import EventDispatcher


class InMemoryRepo(OrderRepository):
    def __init__(self):
        self._store = {}

    def get(self, id):
        return self._store.get(id)

    def save(self, order):
        self._store[order.id] = order


def test_use_case_places_and_dispatches():
    repo = InMemoryRepo()
    events = EventDispatcher()
    received = []
    events.subscribe(OrderPlaced, lambda e: received.append(e))

    o = Order()
    o.customer_id = "c1"
    o.add_line(ProductRef("p1", "SKU-1"), 1, Money(Decimal("100")))
    repo.save(o)

    PlaceOrderUseCase(repo, events).execute(o.id)

    assert len(received) == 1
    assert received[0].order_id == o.id
    assert repo.get(o.id).status == "PLACED"
```

### `tests/test_acl.py`

```python
from decimal import Decimal
from src.infrastructure.acl.legacy_pricing_acl import (
    LegacyPricingClient, PricingACL
)
from src.domain.value_objects import ProductRef


def test_acl_translates_cents_to_money():
    acl = PricingACL(LegacyPricingClient())
    price = acl.get_price(ProductRef("p1", "SKU-001"))
    assert price.amount == Decimal("1995.00")
    assert price.currency == "INR"
```

---

## 8. Wire It Together

### `demo.py`

```python
from decimal import Decimal

from src.domain.order import Order
from src.domain.value_objects import Money, ProductRef
from src.domain.events import OrderPlaced, OrderShipped
from src.infrastructure.sqlite_repo import SqliteOrderRepository
from src.application.place_order import PlaceOrderUseCase
from src.application.event_dispatcher import EventDispatcher


def main():
    repo = SqliteOrderRepository(":memory:")
    events = EventDispatcher()

    # subscribers from other bounded contexts (simulated)
    events.subscribe(OrderPlaced,  lambda e: print(f"📦 BILLING: invoice for {e.order_id} total={e.total.amount}"))
    events.subscribe(OrderPlaced,  lambda e: print(f"📧 NOTIF:   confirmation email for {e.order_id}"))
    events.subscribe(OrderShipped, lambda e: print(f"🚚 NOTIF:   shipping mail tracking={e.tracking_number}"))

    # build order
    o = Order(customer_id="c-42")
    o.add_line(ProductRef("p1", "SKU-1"), 2, Money(Decimal("100")))
    o.add_line(ProductRef("p2", "SKU-2"), 1, Money(Decimal("50")))
    repo.save(o)

    # place — invariant checks + event emitted
    PlaceOrderUseCase(repo, events).execute(o.id)

    # ship
    o2 = repo.get(o.id)
    o2.ship("TRACK-001")
    repo.save(o2)
    for e in o2.pull_events():
        events.dispatch(e)


if __name__ == "__main__":
    main()
```

### Run

```bash
cd ddd_order_service
pytest tests/ -v
python demo.py
```

---

## 9. ✅ Hands-On Checklist

```
□ Drew context_map.md for your real product
□ Modeled an Aggregate Root with invariants
□ Repository pattern: domain doesn't know storage
□ Use case orchestrates, doesn't contain rules
□ Domain events emitted from aggregate
□ ACL translates one external system
□ Tests cover invariants + use case + ACL
```

---

## 🔗 Next

- Next section: [Section 10 — Conclusion & Next Steps](../Section_10_Conclusion_Next_Steps)
