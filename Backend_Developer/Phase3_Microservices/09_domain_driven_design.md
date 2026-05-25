# Domain-Driven Design (DDD) — Bounded Contexts, Aggregates, Ubiquitous Language

## Quick Concepts

**WHAT:**
- **DDD** = Software design approach focusing on business domain
- **Bounded Context** = Logical boundary where domain model is consistent
- **Ubiquitous Language** = Shared vocabulary between devs + business
- **Aggregate** = Cluster of objects treated as one unit (consistency boundary)
- **Aggregate Root** = Entry point for aggregate (only way to modify)
- **Entity** = Has identity (User, Order) — same identity = same object
- **Value Object** = No identity (Money, Address) — equal by value
- **Domain Event** = Something happened in the domain (OrderPlaced)
- **Strategic vs Tactical** = Macro design vs micro implementation

**WHY DDD for microservices:**
- ✅ Service boundaries = Bounded Contexts
- ✅ Avoid distributed monolith
- ✅ Right-sized services (not too small, not too big)
- ✅ Aligned with business
- ✅ Reduces accidental complexity

**HOW DDD layers:**

```
┌─────────────────────────────────────────────────┐
│  Strategic Design (macro)                        │
│  - Bounded Contexts                              │
│  - Context Maps                                  │
│  - Ubiquitous Language                           │
├─────────────────────────────────────────────────┤
│  Tactical Design (micro — within context)        │
│  - Aggregates + Roots                            │
│  - Entities + Value Objects                      │
│  - Domain Services                               │
│  - Domain Events                                 │
│  - Repositories                                  │
└─────────────────────────────────────────────────┘
```

---

## Interview Questions & Answers

### Q1: Bounded Context — kya hai aur microservice se kaise relate karta hai?

**Answer:**

**WHAT:** Logical boundary where a specific domain model applies.

**WHY it matters:**

Same word can mean different things in different contexts:

```
Word: "Customer"

Sales context:
- Customer = potential buyer (lead, prospect)
- Properties: company name, industry, deal stage

Support context:
- Customer = existing user with active subscription
- Properties: user_id, tier, support_tickets

Billing context:
- Customer = entity being charged
- Properties: payment_method, invoice_address, tax_id

⭐ Each context has its own "Customer" model
⭐ Each context = potential microservice
```

**HOW — Identify Bounded Contexts:**

**Step 1: Event Storming**
```
Gather domain experts + developers
Map domain events on whiteboard (orange stickies)
Group events by context

Example for e-commerce:
- "Order placed" → Order context
- "Payment processed" → Payment context
- "Item shipped" → Shipping context
- "Inventory reserved" → Inventory context
- "Customer registered" → Identity context
```

**Step 2: Identify boundaries**
```
Sales context:
  - Lead
  - Opportunity
  - Quote

Order Management context:
  - Order
  - LineItem
  - OrderStatus

Inventory context:
  - Product
  - Stock
  - Warehouse

Customer context:
  - Customer
  - Address
  - PaymentMethod
```

**Step 3: Map to microservices**
```
Bounded Context → Microservice (usually 1:1)

⚠️ Caveat:
- Not always 1:1 (small contexts may share service)
- Big contexts may split (rare)
- Service boundaries should follow context boundaries
```

---

### Q2: Aggregate aur Aggregate Root kya hote hain?

**Answer:**

**WHAT:**
- **Aggregate** = Group of related objects treated as one
- **Aggregate Root** = The "entry point" — only object referenceable from outside

**WHY:**
- Consistency boundary (transactions don't cross aggregates)
- Encapsulation (internal objects hidden)
- Concurrency control (lock root only)

**HOW — Example: Order Aggregate**

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import List

# Value objects (immutable, no identity)
@dataclass(frozen=True)
class Money:
    amount: float
    currency: str = "USD"

    def __add__(self, other):
        if self.currency != other.currency:
            raise ValueError("Currency mismatch")
        return Money(self.amount + other.amount, self.currency)


@dataclass(frozen=True)
class Address:
    street: str
    city: str
    country: str


# Entity inside aggregate (has identity, but not the root)
class LineItem:
    def __init__(self, product_id: int, quantity: int, unit_price: Money):
        self.product_id = product_id
        self.quantity = quantity
        self.unit_price = unit_price

    @property
    def total(self) -> Money:
        return Money(self.unit_price.amount * self.quantity, self.unit_price.currency)


# Aggregate Root (entry point)
class Order:
    """
    INTERVIEW: Order is the Aggregate Root.
    Outside world only references Order — NOT LineItem directly.
    Order enforces business rules (invariants).
    """
    def __init__(self, order_id: int, customer_id: int, shipping_address: Address):
        self.id = order_id
        self.customer_id = customer_id
        self.shipping_address = shipping_address
        self.line_items: List[LineItem] = []
        self.status = "draft"
        self.created_at = datetime.utcnow()
        self.events = []   # Domain events

    # ⭐ Mutations go through aggregate root (NEVER mutate line items directly outside)
    def add_item(self, product_id: int, quantity: int, unit_price: Money):
        # Business rule: can only add to draft orders
        if self.status != "draft":
            raise InvalidOperation(f"Cannot add items to {self.status} order")

        # Business rule: max 100 items per order
        if len(self.line_items) >= 100:
            raise InvalidOperation("Order item limit exceeded")

        # Business rule: minimum quantity 1
        if quantity < 1:
            raise InvalidOperation("Quantity must be positive")

        item = LineItem(product_id, quantity, unit_price)
        self.line_items.append(item)

        # ⭐ Raise domain event
        self.events.append(ItemAddedToOrder(self.id, product_id, quantity))

    def remove_item(self, product_id: int):
        if self.status != "draft":
            raise InvalidOperation(f"Cannot remove items from {self.status} order")
        self.line_items = [i for i in self.line_items if i.product_id != product_id]

    def submit(self):
        # Business rule: order must have items
        if not self.line_items:
            raise InvalidOperation("Cannot submit empty order")

        # Business rule: must have shipping address
        if not self.shipping_address:
            raise InvalidOperation("Shipping address required")

        self.status = "submitted"
        self.events.append(OrderSubmitted(self.id, self.customer_id, self.total))

    @property
    def total(self) -> Money:
        if not self.line_items:
            return Money(0)
        return sum(item.total for item in self.line_items[1:], self.line_items[0].total)
```

**HOW — Repository pattern (load/save aggregate):**

```python
class OrderRepository:
    """
    INTERVIEW: Repository = collection of aggregates.
    Save/load entire aggregate atomically.
    """
    def __init__(self, db_session):
        self.session = db_session

    async def get(self, order_id: int) -> Order:
        """Load entire aggregate (root + children)."""
        order_record = await self.session.execute(
            "SELECT * FROM orders WHERE id = $1", order_id
        )
        items_records = await self.session.execute(
            "SELECT * FROM line_items WHERE order_id = $1", order_id
        )

        # Reconstruct aggregate
        order = Order(
            order_id=order_record["id"],
            customer_id=order_record["customer_id"],
            shipping_address=Address(**order_record["shipping_address"]),
        )

        for item_rec in items_records:
            # Use private constructor or factory
            order.line_items.append(LineItem(
                product_id=item_rec["product_id"],
                quantity=item_rec["quantity"],
                unit_price=Money(item_rec["unit_price"], item_rec["currency"]),
            ))

        return order

    async def save(self, order: Order):
        """Save entire aggregate atomically."""
        async with self.session.transaction():
            # Update root
            await self.session.execute(
                "UPDATE orders SET status = $1 WHERE id = $2",
                order.status, order.id
            )

            # Replace children (simplest approach)
            await self.session.execute(
                "DELETE FROM line_items WHERE order_id = $1", order.id
            )
            for item in order.line_items:
                await self.session.execute(
                    "INSERT INTO line_items (...) VALUES (...)",
                    order.id, item.product_id, item.quantity, ...
                )

            # Publish events
            for event in order.events:
                await event_bus.publish(event)

            order.events.clear()
```

---

### Q3: Entities vs Value Objects — kya difference hai?

**Answer:**

**WHAT:**
- **Entity** = Has identity (ID), mutable
- **Value Object** = No identity, immutable, equal by attributes

**WHY:**
- Different lifecycle, different equality
- Value objects can be safely shared
- Entities tracked separately

**HOW — Examples:**

```python
# ENTITY (has identity)
class User:
    def __init__(self, user_id: int, name: str, email: str):
        self.id = user_id           # ⭐ Identity
        self.name = name             # Can change
        self.email = email           # Can change

    def __eq__(self, other):
        # ⭐ Equal if SAME ID (even if attributes differ)
        return isinstance(other, User) and self.id == other.id

# Use case: same user with different timestamps still same user
user_v1 = User(1, "Alice", "alice@old.com")
user_v2 = User(1, "Alice", "alice@new.com")
assert user_v1 == user_v2   # ✅ True (same ID)


# VALUE OBJECT (no identity, immutable)
@dataclass(frozen=True)
class Money:
    amount: float
    currency: str

    # ⭐ Equal if SAME attributes
    # __eq__ auto-generated by @dataclass

# Use case: Two $100 USD bills are interchangeable
money_a = Money(100, "USD")
money_b = Money(100, "USD")
assert money_a == money_b   # ✅ True (same value)

# Cannot modify (frozen=True)
# money_a.amount = 200  # ❌ Error
```

**More Value Object examples:**

```python
@dataclass(frozen=True)
class Coordinates:
    latitude: float
    longitude: float

    def distance_to(self, other: "Coordinates") -> float:
        # Pure function on values
        return haversine(self, other)


@dataclass(frozen=True)
class EmailAddress:
    value: str

    def __post_init__(self):
        # Validation
        if "@" not in self.value:
            raise ValueError("Invalid email")

    @property
    def domain(self) -> str:
        return self.value.split("@")[1]


@dataclass(frozen=True)
class DateRange:
    start: datetime
    end: datetime

    def __post_init__(self):
        if self.end < self.start:
            raise ValueError("End before start")

    @property
    def duration_days(self) -> int:
        return (self.end - self.start).days

    def overlaps(self, other: "DateRange") -> bool:
        return self.start < other.end and other.start < self.end
```

**Decision: Entity or Value Object?**
- Has unique ID? → Entity
- Identical attributes = same thing? → Value Object
- Changes over time? → Entity
- Immutable concept? → Value Object

---

### Q4: Domain Events — pattern aur use cases?

**Answer:**

**WHAT:** Something significant happened in the domain.

**WHY:**
- Decouples services (publisher doesn't know subscribers)
- Audit trail (history of changes)
- Triggers side effects (send email, update read model)
- Foundation for Event Sourcing

**HOW — Naming convention:**

```python
# Past tense (already happened)
class OrderPlaced: ...           # ✅
class CustomerRegistered: ...    # ✅
class PaymentProcessed: ...      # ✅

# NOT commands (those are different)
class PlaceOrder: ...            # ❌ This is a command
class CancelOrder: ...           # ❌ This is a command
```

**HOW — Domain event structure:**

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import uuid

@dataclass(frozen=True)
class DomainEvent:
    """Base class for all domain events."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: datetime = field(default_factory=datetime.utcnow)
    aggregate_id: int = None
    aggregate_type: str = None


# Specific events
@dataclass(frozen=True)
class OrderPlaced(DomainEvent):
    aggregate_type: str = "Order"
    customer_id: int = None
    total_amount: float = None
    item_count: int = None


@dataclass(frozen=True)
class OrderShipped(DomainEvent):
    aggregate_type: str = "Order"
    tracking_number: str = None
    carrier: str = None


@dataclass(frozen=True)
class CustomerRegistered(DomainEvent):
    aggregate_type: str = "Customer"
    email: str = None
    registration_source: str = None
```

**HOW — Raise events from aggregate:**

```python
class Order:
    def __init__(self, ...):
        # ...
        self._events: List[DomainEvent] = []

    def place(self):
        # Business rules...
        self.status = "placed"

        # ⭐ Raise event (don't dispatch yet)
        self._events.append(OrderPlaced(
            aggregate_id=self.id,
            customer_id=self.customer_id,
            total_amount=self.total.amount,
            item_count=len(self.line_items),
        ))

    def get_events(self) -> List[DomainEvent]:
        events = self._events[:]
        self._events.clear()
        return events


# After save, dispatch events
async def save_and_dispatch(order: Order):
    await order_repo.save(order)
    for event in order.get_events():
        await event_bus.publish(event)
```

**HOW — Event handlers (different bounded contexts):**

```python
# In notification-service
@event_handler(OrderPlaced)
async def send_order_confirmation(event: OrderPlaced):
    customer = await customer_client.get(event.customer_id)
    await email_service.send(
        to=customer.email,
        subject="Order Confirmation",
        body=f"Your order {event.aggregate_id} placed!"
    )


# In inventory-service
@event_handler(OrderPlaced)
async def reserve_inventory(event: OrderPlaced):
    order_items = await order_client.get_items(event.aggregate_id)
    for item in order_items:
        await inventory.reserve(item.product_id, item.quantity)


# In analytics-service
@event_handler(OrderPlaced)
async def update_analytics(event: OrderPlaced):
    await analytics_db.increment("orders_today")
    await analytics_db.increment("revenue_today", event.total_amount)
```

---

### Q5: Context Mapping — services kaise integrate karte hain?

**Answer:**

**WHAT:** How Bounded Contexts relate to each other.

**HOW — 7 integration patterns:**

**1. Shared Kernel**
```
Two contexts share a small common model
Example: Both contexts use "Address" value object

Risk: Coupling — changes need coordination
Use when: Truly common, stable concepts
```

**2. Customer-Supplier (Upstream-Downstream)**
```
Upstream context supplies data
Downstream context depends on it

Example:
  Upstream: Identity context (publishes UserRegistered event)
  Downstream: Order context (consumes UserRegistered)

⭐ Negotiation between teams critical
⭐ Upstream commits to NOT breaking downstream
```

**3. Conformist**
```
Downstream conforms to upstream's model (no choice)
Example: External payment gateway — must use their API as-is

Use when: Can't change upstream
```

**4. Anti-Corruption Layer (ACL)**
```
Translate between contexts to keep models independent

Example:
  Legacy ERP has weird "Customer" model
  Our microservice has clean "Customer" model
  ACL translates legacy → clean
```

```python
# ACL example
class LegacyERPCustomerAdapter:
    """
    Translate legacy ERP customer to our clean domain model.
    """
    def __init__(self, legacy_client):
        self.legacy = legacy_client

    async def get_customer(self, customer_id: int) -> Customer:
        # Call legacy system
        legacy_data = await self.legacy.fetch_customer(customer_id)
        # legacy_data: {"CUST_ID": 1, "CUST_NM": "Alice", "EM": "a@b.com",
        #               "TYPE_CD": "GOLD"}

        # Translate to clean domain model
        return Customer(
            id=legacy_data["CUST_ID"],
            name=legacy_data["CUST_NM"],
            email=EmailAddress(legacy_data["EM"]),
            tier=self._map_tier(legacy_data["TYPE_CD"]),
        )

    def _map_tier(self, legacy_code: str) -> CustomerTier:
        return {
            "GOLD": CustomerTier.PREMIUM,
            "SLVR": CustomerTier.STANDARD,
        }.get(legacy_code, CustomerTier.BASIC)
```

**5. Open Host Service**
```
Context provides API for many consumers
Example: Public REST API
```

**6. Published Language**
```
Well-documented format for integration
Example: JSON schema, Protobuf

⭐ Like Open Host but with formal contract
```

**7. Separate Ways**
```
Two contexts deliberately NOT integrated
Example: Marketing analytics + financial reporting
```

**HOW — Visualize Context Map:**

```
┌─────────────────┐         ┌─────────────────┐
│  Identity       │────────►│   Order         │
│  Context        │  events │   Context       │
│  (Upstream)     │         │  (Downstream)   │
└─────────────────┘         └────────┬────────┘
                                     │ ACL
                                     ▼
                            ┌─────────────────┐
                            │   Legacy ERP    │
                            │  (Conformist)   │
                            └─────────────────┘

         ┌──────────────────┐
         │  Address VO      │ ← Shared Kernel
         └──────────────────┘
              ▲          ▲
              │          │
         ┌────┴────┐ ┌──┴────────┐
         │ Order   │ │ Shipping  │
         │ Context │ │ Context   │
         └─────────┘ └───────────┘
```

---

### Q6: Strategic vs Tactical Design — kya difference?

**Answer:**

**Strategic Design (Macro)**

**WHAT:** Large-scale structure of system

**Concerns:**
- Bounded Contexts
- Context Maps
- Ubiquitous Language
- Team boundaries

**HOW — Output:**
- Context map diagram
- Team structure
- Service decomposition

**Tactical Design (Micro)**

**WHAT:** Implementation within a context

**Concerns:**
- Aggregates
- Entities + Value Objects
- Repositories
- Domain Services
- Domain Events

**HOW — Output:**
- Class diagrams
- Code patterns
- Database schemas

**Real-world flow:**

```
Project starts:
  1. Event Storming workshop (strategic)
     → Identify bounded contexts
     → Map team responsibilities

  2. Per context: Design aggregates (tactical)
     → Identify entities, value objects
     → Define aggregate boundaries
     → Implement repositories

  3. Per context: Implement services
     → Apply patterns within boundaries
     → Use ubiquitous language in code

  4. Integration:
     → Context mapping patterns
     → Event-driven communication
     → ACLs where needed
```

---

### Q7: Ubiquitous Language — kya hai aur kyu zaruri?

**Answer:**

**WHAT:** Shared vocabulary between domain experts + developers.

**WHY:**

```
Without Ubiquitous Language:
- Domain expert: "When customer puts items in cart..."
- Dev hears: "When user adds product to ShoppingCart entity..."
- Translation between speech and code = bugs

With Ubiquitous Language:
- Both use: "Customer adds Item to Cart"
- Code: customer.add_item_to_cart(item)
- Class names, method names, conversations all match
- Less translation = fewer bugs
```

**HOW — Build Ubiquitous Language:**

**Step 1: Glossary**

```markdown
# Order Management Context — Glossary

| Term | Definition |
|---|---|
| **Order** | Customer's commitment to purchase items |
| **Line Item** | Single product entry in an order |
| **Submitted** | Order placed but not yet processed |
| **Fulfilled** | All items shipped to customer |
| **Backorder** | Item ordered but not in stock — wait list |
| **Cart** | Items being considered (not yet ordered) |
| **Checkout** | Process of converting Cart → Order |
```

**Step 2: Use in code**

```python
# ❌ Generic / tech-focused names
class CartModel:
    items: List[ProductDto]

    def process(self):
        ...

class OrderHandler:
    def execute(self, request):
        ...


# ✅ Ubiquitous language
class Cart:
    items: List[CartItem]

    def add_item(self, product_id: int, quantity: int): ...
    def remove_item(self, product_id: int): ...
    def checkout(self) -> Order: ...   # Returns Order!


class Order:
    line_items: List[LineItem]
    status: OrderStatus    # DRAFT, SUBMITTED, FULFILLED, CANCELLED

    def submit(self): ...
    def cancel(self, reason: str): ...
    def mark_fulfilled(self): ...
```

**Step 3: Use in conversations**

```
❌ "Did the API handle the request correctly?"
✅ "Did the order submit successfully?"

❌ "What's the status code?"
✅ "Is the order fulfilled or backordered?"
```

---

### Q8: DDD common mistakes — kya nahi karna?

**Answer:**

**❌ Mistake 1: Anemic Domain Model**

```python
# ❌ Just data classes — no behavior
class Order:
    id: int
    items: list
    total: float
    status: str

# Logic scattered everywhere
def submit_order(order):
    if not order.items:
        raise ValueError("No items")
    order.status = "submitted"
    db.save(order)


# ✅ Rich domain model — behavior with data
class Order:
    def __init__(self, ...): ...

    def submit(self):
        if not self.line_items:
            raise InvalidOperation("No items")
        self.status = "submitted"
        self._events.append(OrderSubmitted(...))
```

**❌ Mistake 2: Too small aggregates**

```python
# ❌ Each entity is its own aggregate
class Order:
    id: int
    customer_id: int

class LineItem:
    id: int
    order_id: int       # ← Reference to Order
    product_id: int

# Problem: line items can be modified independently
# Order business rules can't be enforced
# 100 transactions to update an order


# ✅ Order is aggregate root, LineItems are inside
class Order:
    id: int
    line_items: List[LineItem]   # ← Owned by Order

    def add_item(self, product, qty):
        # Enforce rules here
```

**❌ Mistake 3: Too large aggregates**

```python
# ❌ Aggregate too big — slow loading, lock contention
class Customer:
    id: int
    profile: Profile
    addresses: List[Address]
    orders: List[Order]              # ⚠️ Maybe 1000s of orders
    line_items: List[LineItem]       # ⚠️ Even more
    payments: List[Payment]
    audit_log: List[AuditEntry]

# Loading customer = loading entire history
# Concurrent updates lock entire customer


# ✅ Split into multiple aggregates
class Customer:
    id: int
    profile: Profile
    addresses: List[Address]
    # ⭐ Orders, payments referenced by ID, separate aggregates

class Order:
    customer_id: int                  # ⭐ Reference only
    line_items: List[LineItem]
```

**❌ Mistake 4: Cross-aggregate references**

```python
# ❌ Direct object reference
class Order:
    customer: Customer    # ← Whole Customer object loaded

class Customer:
    orders: List[Order]   # ← Bidirectional reference


# ✅ Reference by ID only
class Order:
    customer_id: int      # ⭐ Just the ID
```

**❌ Mistake 5: Repository per entity (instead of per aggregate)**

```python
# ❌ Separate repos for each entity
class OrderRepository: ...
class LineItemRepository: ...
class OrderStatusRepository: ...

# Problem: Can save line item without going through Order
# Business rules bypassed


# ✅ One repo per aggregate root
class OrderRepository:
    async def save(self, order: Order):
        # Saves entire aggregate (order + line items + ...)
```

**❌ Mistake 6: Skipping Ubiquitous Language**

```python
# ❌ Tech-speak in domain code
class UserDao:
    def fetch(self, dto):
        ...

class OrderProcessor:
    def execute(self, payload):
        ...


# ✅ Business language
class CustomerRepository:
    def find_by_email(self, email: EmailAddress) -> Customer:
        ...

class OrderService:
    def submit_order(self, order: Order):
        ...
```

---

## DDD Implementation Checklist

```markdown
### Strategic Design
- [ ] Event Storming workshop done
- [ ] Bounded Contexts identified
- [ ] Context Map documented
- [ ] Ubiquitous Language glossary
- [ ] Service boundaries align with contexts

### Tactical Design (per context)
- [ ] Aggregate roots identified
- [ ] Entities vs Value Objects classified
- [ ] Repositories per aggregate (not per entity)
- [ ] Domain events for state changes
- [ ] Cross-aggregate refs by ID only

### Code Quality
- [ ] Rich domain model (behavior in entities)
- [ ] No anemic data classes
- [ ] Business rules in aggregates
- [ ] No SQL in domain layer
- [ ] Validation at value object creation

### Integration
- [ ] ACL for external systems
- [ ] Events for inter-context communication
- [ ] No shared database between contexts
- [ ] Schema versioning for events
- [ ] Published Language for public APIs
```

---

## Common DDD Anti-Patterns

| Anti-Pattern | Problem | Fix |
|---|---|---|
| Anemic domain model | Logic scattered | Rich aggregates with behavior |
| Too small aggregates | Can't enforce rules | Group related entities |
| Too large aggregates | Performance, contention | Split, reference by ID |
| Cross-aggregate references | Tight coupling | ID references only |
| Generic naming | Translation needed | Ubiquitous language |
| Sharing DB across contexts | Tight coupling | DB per context |
| Skipping event storming | Wrong boundaries | Do the workshop |
| Ignoring domain experts | Wrong model | Collaborate constantly |
