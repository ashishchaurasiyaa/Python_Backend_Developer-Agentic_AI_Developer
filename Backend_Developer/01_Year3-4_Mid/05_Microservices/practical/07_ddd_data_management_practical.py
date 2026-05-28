"""
Phase3_Microservices — DDD + Data Management Practical
=========================================================
Topics covered:
  1. Aggregate root pattern (Order with LineItems)
  2. Value Objects (Money, Address, EmailAddress)
  3. Domain Events (OrderPlaced, etc.)
  4. Repository pattern (per aggregate)
  5. Database per service pattern
  6. API composition (parallel calls)
  7. CQRS materialized views
  8. Eventual consistency handling
  9. Saga compensating transactions
  10. Distributed systems patterns (CAP, vector clocks)
  11. Distributed lock (Redis simulation)

Run:
  python 07_ddd_data_management_practical.py
"""

import asyncio
import json
import time
import uuid
import hashlib
import secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Set

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Value Objects (Immutable, Equal by Attributes)
# INTERVIEW: Value vs Entity distinction
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Money:
    """
    INTERVIEW: Value Object — immutable, equal by value.
    No identity (two $100 USD are interchangeable).
    """
    amount: float
    currency: str = "USD"

    def __add__(self, other: "Money") -> "Money":
        if self.currency != other.currency:
            raise ValueError(f"Currency mismatch: {self.currency} vs {other.currency}")
        return Money(self.amount + other.amount, self.currency)

    def __mul__(self, factor: float) -> "Money":
        return Money(self.amount * factor, self.currency)


@dataclass(frozen=True)
class EmailAddress:
    """Value Object with validation."""
    value: str

    def __post_init__(self):
        if "@" not in self.value:
            raise ValueError("Invalid email format")

    @property
    def domain(self) -> str:
        return self.value.split("@")[1]


@dataclass(frozen=True)
class Address:
    """Value Object — composite."""
    street: str
    city: str
    country: str
    zipcode: str = ""


@dataclass(frozen=True)
class DateRange:
    """Value Object with behavior."""
    start: datetime
    end: datetime

    def __post_init__(self):
        if self.end < self.start:
            raise ValueError("End before start")

    @property
    def duration_days(self) -> int:
        return (self.end - self.start).days


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Domain Events
# INTERVIEW: Past tense, immutable, fact about domain
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class DomainEvent:
    """Base for all domain events."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: datetime = field(default_factory=datetime.utcnow)
    aggregate_id: int = 0
    aggregate_type: str = ""


@dataclass(frozen=True)
class OrderPlaced(DomainEvent):
    aggregate_type: str = "Order"
    customer_id: int = 0
    total_amount: float = 0
    item_count: int = 0


@dataclass(frozen=True)
class OrderShipped(DomainEvent):
    aggregate_type: str = "Order"
    tracking_number: str = ""
    carrier: str = ""


@dataclass(frozen=True)
class ItemAddedToOrder(DomainEvent):
    aggregate_type: str = "Order"
    product_id: int = 0
    quantity: int = 0


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Entity Inside Aggregate
# INTERVIEW: Has identity, but accessed only through aggregate root
# ─────────────────────────────────────────────────────────────────────────────

class LineItem:
    """
    Entity (has identity via product_id+order_id) but inside Order aggregate.
    NOT accessed from outside the aggregate.
    """
    def __init__(self, product_id: int, quantity: int, unit_price: Money):
        self.product_id = product_id
        self.quantity = quantity
        self.unit_price = unit_price

    @property
    def total(self) -> Money:
        return self.unit_price * self.quantity


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Aggregate Root (Order)
# INTERVIEW: Entry point for entire aggregate, enforces invariants
# ─────────────────────────────────────────────────────────────────────────────

class OrderStatus(Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    FULFILLED = "fulfilled"
    CANCELLED = "cancelled"


class InvalidOperation(Exception):
    pass


class Order:
    """
    INTERVIEW: Aggregate Root.
    - Only object accessed from outside aggregate
    - Enforces business rules (invariants)
    - Manages internal entities (LineItems)
    - Raises domain events on state changes
    """
    MAX_ITEMS = 100

    def __init__(self, order_id: int, customer_id: int, shipping_address: Address):
        self.id = order_id
        self.customer_id = customer_id
        self.shipping_address = shipping_address
        self.line_items: List[LineItem] = []
        self.status = OrderStatus.DRAFT
        self.created_at = datetime.utcnow()
        self._events: List[DomainEvent] = []

    # ⭐ All mutations through aggregate root
    def add_item(self, product_id: int, quantity: int, unit_price: Money):
        # Business rule: only draft orders mutable
        if self.status != OrderStatus.DRAFT:
            raise InvalidOperation(f"Cannot add to {self.status.value} order")

        # Business rule: item count limit
        if len(self.line_items) >= self.MAX_ITEMS:
            raise InvalidOperation(f"Max {self.MAX_ITEMS} items per order")

        # Business rule: positive quantity
        if quantity < 1:
            raise InvalidOperation("Quantity must be positive")

        # Business rule: no duplicate products
        if any(item.product_id == product_id for item in self.line_items):
            raise InvalidOperation(f"Product {product_id} already in order")

        item = LineItem(product_id, quantity, unit_price)
        self.line_items.append(item)

        # ⭐ Raise domain event
        self._events.append(ItemAddedToOrder(
            aggregate_id=self.id,
            product_id=product_id,
            quantity=quantity,
        ))

    def remove_item(self, product_id: int):
        if self.status != OrderStatus.DRAFT:
            raise InvalidOperation(f"Cannot modify {self.status.value} order")
        self.line_items = [i for i in self.line_items if i.product_id != product_id]

    def submit(self):
        # Business rules
        if not self.line_items:
            raise InvalidOperation("Cannot submit empty order")
        if not self.shipping_address:
            raise InvalidOperation("Shipping address required")
        if self.status != OrderStatus.DRAFT:
            raise InvalidOperation(f"Cannot submit {self.status.value} order")

        self.status = OrderStatus.SUBMITTED

        self._events.append(OrderPlaced(
            aggregate_id=self.id,
            customer_id=self.customer_id,
            total_amount=self.total.amount,
            item_count=len(self.line_items),
        ))

    @property
    def total(self) -> Money:
        if not self.line_items:
            return Money(0)
        total = self.line_items[0].total
        for item in self.line_items[1:]:
            total = total + item.total
        return total

    def get_events(self) -> List[DomainEvent]:
        """Pull events for publishing (clears internal buffer)."""
        events = self._events[:]
        self._events.clear()
        return events


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Repository Pattern
# INTERVIEW: Per aggregate, NOT per entity
# ─────────────────────────────────────────────────────────────────────────────

class OrderRepository:
    """
    INTERVIEW: Repository per aggregate root.
    Saves/loads entire aggregate atomically.
    """
    def __init__(self):
        self._storage: Dict[int, dict] = {}
        self._next_id = 1

    async def save(self, order: Order) -> Order:
        """
        Save entire aggregate.
        In production: transactional DB write.
        """
        if not order.id or order.id not in self._storage:
            order.id = self._next_id
            self._next_id += 1

        # Serialize aggregate
        self._storage[order.id] = {
            "id": order.id,
            "customer_id": order.customer_id,
            "shipping_address": order.shipping_address,
            "status": order.status.value,
            "line_items": [
                {
                    "product_id": item.product_id,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                }
                for item in order.line_items
            ],
            "created_at": order.created_at,
        }

        return order

    async def get(self, order_id: int) -> Optional[Order]:
        data = self._storage.get(order_id)
        if not data:
            return None

        # Reconstruct aggregate
        order = Order(
            order_id=data["id"],
            customer_id=data["customer_id"],
            shipping_address=data["shipping_address"],
        )
        order.status = OrderStatus(data["status"])
        order.line_items = [
            LineItem(
                product_id=item["product_id"],
                quantity=item["quantity"],
                unit_price=item["unit_price"],
            )
            for item in data["line_items"]
        ]
        order.created_at = data["created_at"]

        return order


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Database Per Service Pattern
# INTERVIEW: Each service owns its data
# ─────────────────────────────────────────────────────────────────────────────

# ❌ ANTI-PATTERN: Cross-service join
ANTIPATTERN_SHARED_DB = """
# ❌ order-service code:
def get_user_with_orders(user_id):
    cursor.execute('''
        SELECT u.*, o.*
        FROM users u
        JOIN orders o ON u.id = o.user_id   ← Cross-service join
        WHERE u.id = %s
    ''', (user_id,))

# Problems:
# - order-service knows user schema
# - User schema change breaks order-service
# - No clear ownership
"""

# ✅ CORRECT: API call pattern
class UserServiceClient:
    """Client to call user-service for cross-service data."""
    async def get_user(self, user_id: int) -> dict:
        # In production: HTTP call to user-service
        # async with httpx.AsyncClient() as client:
        #     response = await client.get(f"http://user-service/users/{user_id}")
        #     return response.json()

        # Simulated
        return {"id": user_id, "name": f"User{user_id}", "email": f"user{user_id}@x.com"}


async def get_order_with_user(order_repo: OrderRepository, user_client: UserServiceClient,
                                order_id: int):
    """Correct: own data from repo, other service via API."""
    order = await order_repo.get(order_id)
    if not order:
        return None

    user = await user_client.get_user(order.customer_id)

    return {"order": order, "user": user}


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: API Composition (Parallel Calls)
# INTERVIEW: Aggregate from multiple services
# ─────────────────────────────────────────────────────────────────────────────

async def get_dashboard_via_composition(user_id: int):
    """
    INTERVIEW: API composition for cross-service queries.
    Parallel calls for performance.
    """
    user_client = UserServiceClient()

    # Simulate multiple service clients
    async def get_user_data():
        await asyncio.sleep(0.05)   # Simulate network
        return {"id": user_id, "name": "Alice"}

    async def get_recent_orders():
        await asyncio.sleep(0.05)
        return [{"id": 1, "amount": 100}, {"id": 2, "amount": 200}]

    async def get_recommendations():
        await asyncio.sleep(0.05)
        return [{"id": 10}, {"id": 20}]

    # ⭐ Parallel — total time = max(0.05, 0.05, 0.05) = 0.05s
    # NOT sequential (0.15s)
    user, orders, recommendations = await asyncio.gather(
        get_user_data(),
        get_recent_orders(),
        get_recommendations(),
    )

    return {
        "user": user,
        "recent_orders": orders,
        "recommendations": recommendations,
    }


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8: CQRS Materialized Views
# INTERVIEW: Read-optimized denormalized view
# ─────────────────────────────────────────────────────────────────────────────

class DashboardView:
    """
    INTERVIEW: CQRS read model.
    Updated by consuming events from multiple services.
    Single fast query for dashboard.
    """
    def __init__(self):
        self._views: Dict[int, dict] = {}   # user_id → dashboard data

    async def on_user_created(self, event: dict):
        """Event handler from user-service."""
        self._views[event["user_id"]] = {
            "user_id": event["user_id"],
            "user_name": event["name"],
            "total_orders": 0,
            "total_spent": 0,
        }

    async def on_order_placed(self, event: OrderPlaced):
        """Event handler from order-service."""
        user_id = event.customer_id
        view = self._views.get(user_id)
        if view:
            view["total_orders"] += 1
            view["total_spent"] += event.total_amount

    async def get_dashboard(self, user_id: int) -> Optional[dict]:
        """Single fast query (no joins, no API calls)."""
        return self._views.get(user_id)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 9: Saga Compensating Transactions
# INTERVIEW: Distributed transaction alternative
# ─────────────────────────────────────────────────────────────────────────────

class OrderSaga:
    """
    INTERVIEW: Saga pattern with compensation.
    No 2PC — uses compensating actions on failure.
    """
    def __init__(self, inventory_service, payment_service, order_service):
        self.inventory = inventory_service
        self.payment = payment_service
        self.order = order_service

    async def execute(self, items: list, user_id: int):
        inventory_reservation = None
        payment_id = None

        try:
            # Step 1: Reserve inventory
            inventory_reservation = await self.inventory.reserve(items)
            print(f"  ✅ Inventory reserved: {inventory_reservation}")

            # Step 2: Charge payment
            total = sum(item["price"] * item["qty"] for item in items)
            payment_id = await self.payment.charge(user_id, total)
            print(f"  ✅ Payment charged: {payment_id}")

            # Step 3: Create order
            order_id = await self.order.create(user_id, items, payment_id)
            print(f"  ✅ Order created: {order_id}")

            return order_id

        except Exception as e:
            print(f"  ❌ Saga failed: {e}")

            # ⭐ Compensate in REVERSE order
            if payment_id:
                print(f"  Compensating: refund {payment_id}")
                await self.payment.refund(payment_id)

            if inventory_reservation:
                print(f"  Compensating: release {inventory_reservation}")
                await self.inventory.release(inventory_reservation)

            raise


# Fake services for demo
class FakeInventoryService:
    def __init__(self, fail=False):
        self.fail = fail
    async def reserve(self, items):
        if self.fail: raise Exception("Inventory unavailable")
        return f"reservation-{uuid.uuid4().hex[:8]}"
    async def release(self, reservation): pass


class FakePaymentService:
    def __init__(self, fail=False):
        self.fail = fail
    async def charge(self, user_id, amount):
        if self.fail: raise Exception("Payment failed")
        return f"payment-{uuid.uuid4().hex[:8]}"
    async def refund(self, payment_id): pass


class FakeOrderService:
    async def create(self, user_id, items, payment_id):
        return f"order-{uuid.uuid4().hex[:8]}"


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 10: Distributed Lock (Redis simulation)
# INTERVIEW: Mutex across processes
# ─────────────────────────────────────────────────────────────────────────────

class InMemoryDistributedLock:
    """
    INTERVIEW: Distributed lock simulation.
    In production: use Redis SET NX + TTL, or etcd/ZooKeeper.
    """
    _locks: Dict[str, dict] = {}

    def __init__(self, key: str, ttl_seconds: int = 30):
        self.key = key
        self.ttl = ttl_seconds
        self.token = str(uuid.uuid4())   # Unique to this acquisition

    def acquire(self) -> bool:
        existing = self._locks.get(self.key)
        if existing:
            # Check if expired
            if existing["expires_at"] < time.time():
                del self._locks[self.key]
            else:
                return False

        self._locks[self.key] = {
            "token": self.token,
            "expires_at": time.time() + self.ttl,
        }
        return True

    def release(self):
        existing = self._locks.get(self.key)
        if existing and existing["token"] == self.token:
            del self._locks[self.key]


REDIS_LOCK_LUA = """
-- Atomic: check token THEN delete
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 11: Demos
# ─────────────────────────────────────────────────────────────────────────────

async def demo_aggregate_root():
    print("\n[Aggregate Root + DDD Demo]")

    # Create order
    address = Address(street="123 Main St", city="NYC", country="USA")
    order = Order(order_id=1, customer_id=42, shipping_address=address)

    # Add items via aggregate root (NOT directly to line_items list)
    order.add_item(product_id=10, quantity=2, unit_price=Money(50))
    order.add_item(product_id=20, quantity=1, unit_price=Money(100))

    print(f"  Order total: {order.total}")
    print(f"  Items: {len(order.line_items)}")

    # Submit (triggers domain event)
    order.submit()
    print(f"  Status: {order.status.value}")

    events = order.get_events()
    print(f"  Events raised: {len(events)}")
    for event in events:
        print(f"    - {type(event).__name__}")

    # Business rule enforcement
    try:
        order.add_item(product_id=30, quantity=1, unit_price=Money(50))
    except InvalidOperation as e:
        print(f"  ✅ Business rule enforced: {e}")


async def demo_repository_pattern():
    print("\n[Repository Pattern Demo]")
    repo = OrderRepository()

    # Save
    order = Order(0, 42, Address("123 Main", "NYC", "USA"))
    order.add_item(10, 2, Money(50))
    saved = await repo.save(order)
    print(f"  Saved order with id={saved.id}")

    # Retrieve (reconstructs aggregate)
    retrieved = await repo.get(saved.id)
    print(f"  Retrieved: {len(retrieved.line_items)} items, total={retrieved.total}")


async def demo_api_composition():
    print("\n[API Composition Demo]")

    start = time.time()
    dashboard = await get_dashboard_via_composition(user_id=42)
    elapsed = time.time() - start

    print(f"  Dashboard fetched in {elapsed*1000:.0f}ms (parallel)")
    print(f"  Components: {list(dashboard.keys())}")
    print(f"  Sequential would take ~150ms (3 × 50ms)")


async def demo_cqrs_view():
    print("\n[CQRS Materialized View Demo]")
    view = DashboardView()

    # User created event
    await view.on_user_created({"user_id": 42, "name": "Alice"})

    # Order events accumulate
    await view.on_order_placed(OrderPlaced(customer_id=42, total_amount=100))
    await view.on_order_placed(OrderPlaced(customer_id=42, total_amount=200))
    await view.on_order_placed(OrderPlaced(customer_id=42, total_amount=50))

    # Single fast query
    dashboard = await view.get_dashboard(user_id=42)
    print(f"  Dashboard: {dashboard}")
    print("  ✅ Single query — no joins or API calls")


async def demo_saga_success():
    print("\n[Saga Success Demo]")
    saga = OrderSaga(
        FakeInventoryService(),
        FakePaymentService(),
        FakeOrderService(),
    )

    items = [{"product_id": 1, "qty": 2, "price": 50}]
    order_id = await saga.execute(items, user_id=42)
    print(f"  ✅ Saga succeeded: {order_id}")


async def demo_saga_failure_compensation():
    print("\n[Saga Failure + Compensation Demo]")
    # Payment fails — must compensate inventory
    saga = OrderSaga(
        FakeInventoryService(),
        FakePaymentService(fail=True),   # ⭐ Payment fails
        FakeOrderService(),
    )

    items = [{"product_id": 1, "qty": 2, "price": 50}]
    try:
        await saga.execute(items, user_id=42)
    except Exception:
        pass
    print("  ✅ Saga compensated (inventory released even though payment failed)")


def demo_distributed_lock():
    print("\n[Distributed Lock Demo]")
    lock1 = InMemoryDistributedLock("user-123-process", ttl_seconds=30)
    lock2 = InMemoryDistributedLock("user-123-process", ttl_seconds=30)

    # First instance acquires
    acquired1 = lock1.acquire()
    print(f"  Lock acquired by instance 1: {acquired1}")

    # Second instance fails
    acquired2 = lock2.acquire()
    print(f"  Lock acquired by instance 2: {acquired2}")

    # Release first
    lock1.release()
    print("  Instance 1 released")

    # Now second can acquire
    acquired2 = lock2.acquire()
    print(f"  Lock acquired by instance 2 (after release): {acquired2}")

    lock2.release()


# ─────────────────────────────────────────────────────────────────────────────
# Q&A
# ─────────────────────────────────────────────────────────────────────────────

QA = [
    ("Aggregate Root vs Entity?",
     "Aggregate Root = entry point, accessed from outside\n"
     "     Entity inside aggregate = has identity but accessed via root\n"
     "     Value Object = no identity, equal by attributes (Money)"),

    ("Why repository per aggregate (not per entity)?",
     "Aggregate = consistency boundary\n"
     "     Save/load atomically (all parts together)\n"
     "     Per-entity repos let you bypass business rules"),

    ("Database per service vs shared DB?",
     "Per service: loose coupling, independent scaling\n"
     "     Shared DB: tight coupling, schema changes need coordination\n"
     "     Per service ALWAYS in real microservices"),

    ("Why not 2PC for distributed transactions?",
     "Blocking (resources locked during entire 2PC)\n"
     "     Coordinator failure = 'in doubt' transactions\n"
     "     Performance + reliability issues\n"
     "     Use Saga pattern instead"),

    ("Eventual consistency — how handle in UI?",
     "Show 'syncing' indicator\n"
     "     Read-your-writes: read from primary briefly after write\n"
     "     Optimistic UI updates"),

    ("API composition vs CQRS?",
     "API composition: real-time aggregation (multiple service calls)\n"
     "     CQRS: pre-built materialized view (one fast query)\n"
     "     CQRS better for read-heavy with complex aggregations"),

    ("Saga choreography vs orchestration?",
     "Choreography: services react to events (decentralized)\n"
     "     Orchestration: central coordinator manages flow\n"
     "     Choreography for simple, orchestration for complex"),

    ("Distributed lock — Redis vs ZooKeeper?",
     "Redis: fast, simple, but failover can lose locks\n"
     "     ZooKeeper/etcd: stronger guarantees but slower\n"
     "     Use ZooKeeper for correctness-critical, Redis for best-effort"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    print("=" * 60)
    print("DDD + DATA MANAGEMENT PRACTICAL")
    print("=" * 60)

    await demo_aggregate_root()
    await demo_repository_pattern()
    await demo_api_composition()
    await demo_cqrs_view()
    await demo_saga_success()
    await demo_saga_failure_compensation()
    demo_distributed_lock()

    print("\n[DDD Building Blocks Summary]")
    blocks = {
        "Value Object": "Immutable, equal by value (Money, Address)",
        "Entity": "Has identity, mutable (User)",
        "Aggregate": "Cluster of objects, consistency boundary",
        "Aggregate Root": "Entry point for aggregate (only public reference)",
        "Repository": "Save/load aggregates atomically",
        "Domain Event": "Past-tense fact about domain (OrderPlaced)",
        "Domain Service": "Logic that doesn't belong to entity",
        "Bounded Context": "Logical boundary = microservice boundary",
    }
    for block, description in blocks.items():
        print(f"  {block:<18}: {description}")

    print("\n[Q&A Summary]")
    for q, a in QA:
        print(f"\n  Q: {q}")
        print(f"  A: {a}")

    print("\n" + "=" * 60)
    print("FILES TO KNOW:")
    print("  domain/aggregates.py    → Order, LineItem (rich domain)")
    print("  domain/value_objects.py → Money, Address, EmailAddress")
    print("  domain/events.py        → OrderPlaced, OrderShipped")
    print("  repositories/           → One per aggregate root")
    print("  services/saga.py        → Compensating transactions")
    print("  views/dashboard.py      → CQRS read model")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
