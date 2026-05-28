# Event Sourcing + CQRS — Complete Interview Prep Guide
### Python Backend Developer | Target: 40 LPA
### Series: Microservices Architecture (Year 3-4)

---

## Table of Contents

1. Traditional State Storage ki Problem
2. Event Sourcing kya hai?
3. Benefits of Event Sourcing
4. Aggregate Design
5. Event Store
6. Snapshots
7. CQRS (Command Query Responsibility Segregation)
8. CQRS + Event Sourcing Together
9. Projections (Read Models)
10. Idempotency in Event Processing
11. Saga with Event Sourcing
12. Real-World Use Cases
13. Challenges
14. Interview Q&As (10 Questions)

---

## 1. Traditional State Storage ki Problem

### Mutable State — The Root Cause

Traditional databases mein hum **current state** store karte hain. Matlab:

```sql
-- Users table
UPDATE orders SET status = 'shipped', updated_at = NOW() WHERE order_id = 123;
```

Ye query chalane ke baad, pehle wala state **permanently destroy** ho gaya. Hume pata hi nahi ki order pehle `confirmed` tha, ya `payment_pending` tha, ya kisi ne manually override kiya tha.

### Problems with Mutable State

**Problem 1: No History / Audit Trail**

```python
# Traditional approach
class Order:
    def ship(self):
        self.status = "shipped"  # Previous status GONE forever
        self.updated_at = datetime.now()
        db.save(self)

# Agar kal koi puche: "ye order ship kyun hua? Kisne kiya?"
# Answer: Nobody knows.
```

Finance mein ye FATAL hai. RBI regulations kehti hain — har transaction ka record rakho. Traditional DB mein ye possible nahi bina separate audit table ke.

**Problem 2: Concurrent Updates — Lost Update Problem**

```
Thread A: Order load karo (status = "confirmed")
Thread B: Order load karo (status = "confirmed")
Thread A: status = "shipped", save karo → OK
Thread B: status = "cancelled", save karo → A ki update LOST!
```

Ye "lost update" problem hai. Traditional solution: pessimistic locking (slow) ya optimistic locking (manual).

**Problem 3: Debugging is Nightmare**

Production mein bug aaya. Order ka total galat hai — Rs 1500 hona chahiye tha, Rs 1200 hai.

```python
# Traditional DB mein:
SELECT * FROM orders WHERE order_id = 456;
# Result: total = 1200, status = "confirmed"
# But WHY is it 1200? No idea.
# Order kab create hua? Kaunse items the? Koi item remove hua tha?
# IMPOSSIBLE to know.
```

**Problem 4: Multiple Read Models Banana Mushkil**

Ek hi data ko different ways mein represent karna padta hai:
- Customer portal: order history with items
- Admin panel: orders by region, revenue
- Analytics: customer behavior, repeat orders
- Finance: revenue per product

Traditional approach: ya toh multiple tables maintain karo (data duplication), ya slow JOINs karo at query time.

**Problem 5: Temporal Queries Impossible**

"3 mahine pehle, is customer ka balance kya tha?" — Traditional DB: impossible without a separate history table.

---

## 2. Event Sourcing kya hai?

### Core Idea: State Store Mat Karo, Events Store Karo

Event Sourcing ek pattern hai jisme hum **current state** store karne ki bajaye **ek series of events** store karte hain. State is events se **derive** hoti hai.

```
Traditional:  Store WHAT IS (current state)
Event Sourcing: Store WHAT HAPPENED (events)
```

**Real-world analogy:**

Bank account ka socho:
- Traditional: Balance = Rs 5,000 (bus yahi store hai)
- Event Sourcing:
  - Account Opened (Rs 0)
  - Deposited Rs 10,000
  - Withdrawn Rs 3,000
  - Deposited Rs 1,500
  - Withdrawn Rs 3,500
  - **Current Balance = 10,000 - 3,000 + 1,500 - 3,500 = Rs 5,000** ← same result!

Balance **replay** se calculate hota hai. Aur hume POORA history mil gaya free mein!

### "Append-Only Event Log"

Event store mein sirf `INSERT` hota hai — kabhi `UPDATE` ya `DELETE` nahi. Events immutable hain.

```
Event Log (append-only):
┌────────┬───────────────────┬────────────────┬─────────┐
│ pos    │ event_type        │ aggregate_id   │ version │
├────────┼───────────────────┼────────────────┼─────────┤
│   1    │ OrderCreated      │ order-001      │    1    │
│   2    │ ItemAdded         │ order-001      │    2    │
│   3    │ ItemAdded         │ order-001      │    3    │
│   4    │ OrderConfirmed    │ order-001      │    4    │
│   5    │ OrderCreated      │ order-002      │    1    │
│   6    │ OrderShipped      │ order-001      │    5    │
└────────┴───────────────────┴────────────────┴─────────┘
```

### Event Anatomy — Ek Event ke Components

```python
@dataclass
class DomainEvent:
    # Unique identity of this specific event
    event_id: str          # UUID — "3f8a1b2c-4d5e-..."
    
    # What happened?
    event_type: str        # "OrderCreated", "ItemAdded", "OrderShipped"
    
    # Which object this event belongs to
    aggregate_id: str      # "order-001" — the specific order
    aggregate_type: str    # "Order" — the type of object
    
    # Sequence within this aggregate's history
    version: int           # 1, 2, 3, 4, ... (monotonically increasing)
    
    # The actual data of what happened
    payload: dict          # {"customer_id": "C001", "items": [...]}
    
    # When did it happen?
    timestamp: str         # ISO 8601 — "2024-01-15T10:30:00.000Z"
```

**event_id**: Idempotency ke liye. Agar same event dobara process ho, hum detect kar sakte hain.

**version**: Concurrency control ke liye. Agar do processes same aggregate pe kaam kar rahe hain, version conflict detect hoga.

**payload**: Event-specific data. `OrderCreated` mein customer info hogi, `ItemAdded` mein item details hongi.

### Immutable Events — NEVER Delete, NEVER Modify

```python
# WRONG — kabhi mat karo
event_store.update(event_id="3f8a...", payload={"new": "data"})  # NO!
event_store.delete(event_id="3f8a...")                            # NO!

# RIGHT — events are facts, facts don't change
# Agar galti hui? Compensating event likho
event_store.append(CorrectionApplied(
    aggregate_id="order-001",
    payload={"corrects_event": "3f8a...", "reason": "Wrong price entered"}
))
```

### BankAccount Example — Events vs State

```
Events:                              State after each event:
─────────────────────────────────    ─────────────────────────────────────
AccountOpened(customer="C001")   →   { balance: 0, status: "open" }
Deposited(amount=10000)          →   { balance: 10000, status: "open" }
Withdrawn(amount=3000)           →   { balance: 7000, status: "open" }
Deposited(amount=1500)           →   { balance: 8500, status: "open" }
Withdrawn(amount=3500)           →   { balance: 5000, status: "open" }
AccountLocked(reason="fraud")    →   { balance: 5000, status: "locked" }
```

Current state chahiye? Last event tak replay karo. 2 din pehle ka state chahiye? Timestamp se filter karo.

---

## 3. Benefits of Event Sourcing

### 3.1 Complete Audit Trail — Free mein!

```python
# Query: "Order 001 ke saath kya kya hua?"
events = event_store.load("order-001")

for event in events:
    print(f"{event.timestamp} | {event.event_type} | {event.payload}")

# Output:
# 2024-01-15T10:00:00 | OrderCreated   | {"customer": "C001", ...}
# 2024-01-15T10:01:00 | ItemAdded      | {"product": "Laptop", "price": 50000}
# 2024-01-15T10:02:00 | ItemAdded      | {"product": "Mouse", "price": 500}
# 2024-01-15T10:05:00 | OrderConfirmed | {"total": 50500}
# 2024-01-15T14:30:00 | OrderShipped   | {"tracking": "TRK123"}
```

Ye audit trail automatically banti hai — koi extra code nahi, koi separate audit table nahi.

### 3.2 Time Travel — Kisi bhi Point ka State Dekho

```python
# Order ka state 10:03 baje ka kya tha?
events_until_time = [e for e in events if e.timestamp <= "2024-01-15T10:03:00"]
order_at_10_03 = Order.from_events("order-001", events_until_time)
print(order_at_10_03.items)  # Only Laptop added (Mouse added at 10:02, Confirmed at 10:05)
# → [{"product": "Laptop", "price": 50000}]
```

Finance mein ye "point-in-time recovery" kehते hain. Banking regulators yahi requirement rakhte hain.

### 3.3 Event Replay — New Logic with Old Data

```python
# 6 mahine baad naya feature: "Loyalty points calculate karo"
# Purane events replay karo with new handler

class LoyaltyPointsHandler:
    def handle(self, event: DomainEvent):
        if event.event_type == "OrderConfirmed":
            total = event.payload["total"]
            points = int(total / 100)  # 1 point per Rs 100
            self.loyalty_db.add_points(event.payload["customer_id"], points)

# Sare purane events replay karo — 6 mahine ki history mein bhi loyalty points calculate
handler = LoyaltyPointsHandler()
for event in event_store.load_all():
    handler.handle(event)
```

Traditional DB mein ye **impossible** hota — purani transactions ka koi record hi nahi tha.

### 3.4 Multiple Projections — Same Events, Different Views

```
Same Events
     │
     ├──→ OrderSummaryProjection  → Customer ki order list (fast read)
     │
     ├──→ RevenueProjection       → Finance dashboard (aggregated revenue)
     │
     ├──→ InventoryProjection     → Stock levels (items confirmed/cancelled)
     │
     └──→ AnalyticsProjection     → ML features (customer behavior)
```

Ek event store, unlimited read models. Koi bhi projection rebuild kar sakte ho kisi bhi waqt.

### 3.5 Debugging — Bug Reproduction

```python
# Production bug: "Order 789 ka total galat calculate hua"
# Event sourcing ke saath:
events = event_store.load("order-789")
print_events(events)  # EXACT sequence of what happened

# Ab local machine pe replay karo same events with debugger
order = Order("order-789")
for event in events:
    print(f"Applying: {event.event_type}")
    order._apply(event)
    print(f"State after: total={order.total}, items={len(order.items)}")
```

Bug exact reproduce hoga. Traditional DB mein? Impossible — state overwrite ho chuka hai.

### 3.6 GDPR Compliance — Forget by Tombstone

Event sourcing mein events delete nahi hote. GDPR "right to be forgotten" ke liye:

```python
# Strategy 1: Tombstone Event
event_store.append(PersonalDataDeleted(
    aggregate_id="customer-001",
    payload={"reason": "GDPR deletion request", "deleted_fields": ["name", "email", "phone"]}
))
# Projection rebuild karte waqt, is event ke baad personal data NULL kar do

# Strategy 2: Encryption
# PII (name, email) encrypt karo per-customer key se
# GDPR request pe: encryption key delete karo
# Events remain, but personal data undecipherable (crypto-shredding)
```

---

## 4. Aggregate Design

### Aggregate kya hai?

Aggregate ek **consistency boundary** hai. Matlab: ek aggregate ke andar sab changes ek single transaction mein hote hain. Ek aggregate doosre aggregate ko directly nahi modify karta.

```
Order Aggregate:               Customer Aggregate:
┌─────────────────────┐        ┌──────────────────────┐
│ Order (Root)        │        │ Customer (Root)       │
│   ├── OrderId       │        │   ├── CustomerId      │
│   ├── Status        │        │   ├── Name            │
│   ├── Items[]       │        │   ├── Email           │
│   └── Total         │        │   └── LoyaltyPoints   │
└─────────────────────┘        └──────────────────────┘
         │                               │
         └── Communicate via Events, not direct reference
```

**Aggregate Root** = wo class jo externally accessible hai. Baaki sab internal.

### Version / Sequence Number — Optimistic Concurrency

```python
class Order:
    def __init__(self):
        self.version = 0  # Starts at 0
    
    def _apply(self, event: DomainEvent):
        # ... update state ...
        self.version = event.version  # Always increment
```

Jab save karo:
```python
# Event store mein UNIQUE constraint: (aggregate_id, version)
# Agar version already exists → IntegrityError → ConcurrencyError
INSERT INTO events (aggregate_id, version, ...) VALUES ('order-001', 5, ...)
-- If version 5 already exists → FAIL → retry required
```

Ye **optimistic concurrency control** hai — lock nahi lagata, but conflict detect karta hai.

### Apply Events — State Rebuild

```python
class Order:
    @classmethod
    def from_events(cls, order_id: str, events: list) -> 'Order':
        """Replay events to rebuild current state"""
        order = cls(order_id)
        for event in events:
            order._apply(event)  # Apply each event in sequence
        return order
    
    def _apply(self, event: DomainEvent):
        """Pure function — given current state + event → new state"""
        handlers = {
            "OrderCreated":   self._on_order_created,
            "ItemAdded":      self._on_item_added,
            "OrderConfirmed": self._on_order_confirmed,
            "OrderShipped":   self._on_order_shipped,
            "OrderCancelled": self._on_order_cancelled,
        }
        handler = handlers.get(event.event_type)
        if handler:
            handler(event)
        self.version = event.version
    
    def _on_order_created(self, event):
        self.customer_id = event.payload["customer_id"]
        self.status = "draft"
    
    def _on_item_added(self, event):
        self.items.append(event.payload)
        self.total += event.payload["price"] * event.payload["qty"]
    
    def _on_order_confirmed(self, event):
        self.status = "confirmed"
```

### Uncommitted vs Persisted Events

```python
class Order:
    def __init__(self):
        self._uncommitted_events: list = []  # In-memory, not yet saved
    
    def create(self, customer_id: str):
        event = OrderCreated(aggregate_id=self.order_id, ...)
        self._apply(event)           # Update in-memory state immediately
        self._uncommitted_events.append(event)  # Queue for persistence
    
    def get_uncommitted_events(self):
        return self._uncommitted_events.copy()
    
    def mark_committed(self):
        """Call this after successfully saving to event store"""
        self._uncommitted_events.clear()

# Usage:
order = Order("order-001")
order.create("C001")
order.add_item("Laptop", 50000, 1)

# Save to store
event_store.append(order.get_uncommitted_events())
order.mark_committed()  # Now in-memory matches persisted
```

### DomainEvent Base Class — Best Practice

```python
from dataclasses import dataclass, field
from datetime import datetime
import uuid

@dataclass
class DomainEvent:
    """Base class for all domain events"""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = field(default="")
    aggregate_id: str = field(default="")
    aggregate_type: str = field(default="")
    version: int = field(default=0)
    payload: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "aggregate_id": self.aggregate_id,
            "aggregate_type": self.aggregate_type,
            "version": self.version,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'DomainEvent':
        return cls(**data)
```

---

## 5. Event Store

### What is Event Store?

Event Store ek specialized database hai jo sirf events store karta hai. Main properties:

1. **Append-only**: Sirf INSERT, kabhi UPDATE/DELETE nahi
2. **Ordered**: Events ka order guaranteed hai
3. **Streams**: Har aggregate ka apna stream hota hai
4. **Global log**: Sare events ka combined ordered log

### Event Store Interface

```python
class IEventStore(ABC):
    @abstractmethod
    def append(self, events: list[DomainEvent]) -> None:
        """Atomically append events. Raises ConcurrencyError on version conflict."""
        pass
    
    @abstractmethod
    def load(self, aggregate_id: str, from_version: int = 0) -> list[DomainEvent]:
        """Load events for a specific aggregate, optionally from a version."""
        pass
    
    @abstractmethod
    def load_all(self, aggregate_type: str = None) -> list[DomainEvent]:
        """Load all events (for projection rebuild)."""
        pass
```

### Streams — One per Aggregate

```
Event Store:
├── Stream: order-001
│   ├── v1: OrderCreated
│   ├── v2: ItemAdded (Laptop)
│   ├── v3: ItemAdded (Mouse)
│   └── v4: OrderConfirmed
│
├── Stream: order-002
│   ├── v1: OrderCreated
│   └── v2: OrderCancelled
│
└── Stream: order-003
    ├── v1: OrderCreated
    ├── v2: ItemAdded (Phone)
    └── v3: OrderConfirmed
```

Each stream independently versioned. Concurrency conflict sirf same stream pe hota hai.

### Global Event Position

```sql
-- All events globally ordered
SELECT * FROM events ORDER BY global_position;

-- Position is auto-increment — guaranteed global ordering
-- Useful for:
-- 1. Projection rebuild (process in exact order)
-- 2. Event bus publishing (no gaps)
-- 3. Exactly-once processing
```

### PostgreSQL Custom Event Store

```sql
CREATE TABLE events (
    global_position BIGSERIAL PRIMARY KEY,  -- Global ordering
    event_id        UUID NOT NULL UNIQUE,
    event_type      VARCHAR(100) NOT NULL,
    aggregate_id    VARCHAR(255) NOT NULL,
    aggregate_type  VARCHAR(100) NOT NULL,
    version         INTEGER NOT NULL,
    payload         JSONB NOT NULL,
    metadata        JSONB DEFAULT '{}',
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT uq_aggregate_version UNIQUE (aggregate_id, version)
);

CREATE INDEX idx_events_aggregate ON events (aggregate_id, version);
CREATE INDEX idx_events_type      ON events (aggregate_type);
CREATE INDEX idx_events_timestamp ON events (timestamp);
```

### EventStoreDB (Dedicated Solution)

```
EventStoreDB ek purpose-built event store hai jo:
- Streams natively support karta hai
- Subscriptions ke through real-time event delivery karta hai
- Built-in projections support karta hai
- HTTP/gRPC API provide karta hai
- High performance: millions of events per second
```

```python
# EventStoreDB client (conceptual)
from esdbclient import EventStoreDBClient

client = EventStoreDBClient(uri="esdb://localhost:2113")

# Write events
client.append_to_stream(
    stream_name="order-001",
    current_version=ExpectedVersion.ANY,
    events=[NewEvent(type="OrderCreated", data=b'{"customer": "C001"}')]
)

# Read events
events = client.read_stream("order-001")
```

---

## 6. Snapshots

### Problem: 1000 Events to Rebuild State

```python
# 1 saal baad, order-001 ke 5000 events hain (unrealistic but illustrative)
# Har request pe:
events = event_store.load("order-001")  # 5000 rows fetch
order = Order.from_events("order-001", events)  # 5000 apply calls
# → SLOW! O(n) time complexity

# Production mein typical: 50-200 events per aggregate is manageable
# But 500+ events → snapshot consider karo
```

### Solution: Periodic Snapshots

```python
@dataclass
class Snapshot:
    aggregate_id: str
    aggregate_type: str
    state: dict        # Serialized aggregate state
    version: int       # "At this version, state was X"
    timestamp: str

class SnapshotStore:
    def save(self, snapshot: Snapshot): ...
    def load(self, aggregate_id: str) -> Optional[Snapshot]: ...

# Load with snapshot optimization:
def load_order_optimized(order_id: str) -> Order:
    # Step 1: Check for snapshot
    snapshot = snapshot_store.load(order_id)
    
    if snapshot:
        # Step 2a: Restore from snapshot
        order = Order.from_snapshot(order_id, snapshot.state)
        # Step 3: Load only NEWER events (after snapshot version)
        newer_events = event_store.load(order_id, from_version=snapshot.version)
        for event in newer_events:
            order._apply(event)
    else:
        # Step 2b: Full replay from beginning
        all_events = event_store.load(order_id)
        order = Order.from_events(order_id, all_events)
    
    return order
```

### Snapshot Frequency

```python
SNAPSHOT_EVERY_N_EVENTS = 50  # Industry typical: 50-100

def save_with_snapshot(order: Order, event_store, snapshot_store):
    events = order.get_uncommitted_events()
    event_store.append(events)
    order.mark_committed()
    
    # Check if snapshot needed
    if order.version % SNAPSHOT_EVERY_N_EVENTS == 0:
        snapshot = Snapshot(
            aggregate_id=order.order_id,
            aggregate_type="Order",
            state=order.to_dict(),  # Serialize current state
            version=order.version,
            timestamp=datetime.utcnow().isoformat()
        )
        snapshot_store.save(snapshot)
        print(f"Snapshot saved at version {order.version}")
```

### Performance Impact

```
Without Snapshot (100 events):
- DB Query: SELECT * FROM events WHERE aggregate_id=X  → 100 rows
- Memory:   Deserialize 100 events
- CPU:      Apply 100 events
- Time:     ~50ms

With Snapshot at v50 (100 events):
- DB Query 1: SELECT * FROM snapshots WHERE aggregate_id=X → 1 row
- Restore:    Deserialize snapshot state
- DB Query 2: SELECT * FROM events WHERE aggregate_id=X AND version>50 → 50 rows
- CPU:        Apply 50 events
- Time:       ~30ms (40% faster, increases with event count)
```

---

## 7. CQRS (Command Query Responsibility Segregation)

### Bertrand Meyer ka CQS Principle

1986 mein Bertrand Meyer ne "Command-Query Separation" principle diya:
> "Every method should either be a command that performs an action, or a query that returns data — never both."

CQRS is principle ko architecture level pe apply karta hai.

### Commands vs Queries

```
COMMAND                          QUERY
─────────────────────────────    ─────────────────────────────
Kuch change karta hai           Kuch return karta hai
Write operation                  Read operation
State mutate karta hai           State nahi change karta
Return: void or ID only         Return: data/DTO
Example: CreateOrder             Example: GetOrderById
         ConfirmOrder                     GetOrdersByCustomer
         CancelOrder                      GetOrderStatistics
         ProcessPayment                   GetRevenueReport
```

### Separate Models for Read and Write

```
WRITE SIDE (Command Side):          READ SIDE (Query Side):
────────────────────────────        ────────────────────────────
Optimized for:                      Optimized for:
  - Data consistency                  - Query performance
  - Business rule validation          - Denormalized data
  - Concurrency control               - Fast reads (no JOINs)
  - Complex domain logic              - Multiple formats

Data Model:                         Data Model:
  - Normalized                        - Denormalized / flat
  - Event-sourced aggregate           - Pre-computed aggregates
  - Strict invariants                 - Cache-friendly
  - Complex relationships             - Multiple projections
```

### Why Separate?

Real-world mein reads >> writes typically (90% reads, 10% writes).

```python
# Write Model: Complex domain logic required
class Order:
    def confirm(self):
        if self.status != "draft":
            raise ValueError("Only draft orders can be confirmed")
        if not self.items:
            raise ValueError("Order must have items")
        if self.total < 100:
            raise ValueError("Minimum order value Rs 100")
        if self.customer.credit_limit < self.total:
            raise ValueError("Customer credit limit exceeded")
        # ... many more validations ...

# Read Model: Simple, fast, denormalized
class OrderReadModel:
    order_id: str
    customer_name: str  # Denormalized from Customer
    status: str
    total: float
    items_count: int
    created_at: str
    # No validations, no business logic — just data for display
```

### Async vs Sync Read Model Update

```
SYNCHRONOUS (Strong Consistency):
Command → Save Events → Update Projection → Return to Client
         ↑                 ↑
         Same transaction  Projection updated before response

Pros: Read model always up-to-date
Cons: Slower writes (two DB operations per command)

ASYNCHRONOUS (Eventual Consistency):
Command → Save Events → Return to Client
               ↓
         Event Bus/Queue → Projection Handler → Update Projection
         (milliseconds to seconds later)

Pros: Faster writes, decoupled
Cons: "Eventual consistency" — read model may lag
```

---

## 8. CQRS + Event Sourcing Together

### Ye Combination Kyun Powerful hai?

Event Sourcing naturally Command side ke liye fit hai (events = write model).
CQRS naturally Query side optimize karta hai (projections = read models).
Together: Clean separation with full history + fast reads.

### Complete Flow

```
                         WRITE SIDE
┌──────────┐    ┌────────────────┐    ┌───────────┐    ┌─────────────┐
│  Client  │───▶│ CommandHandler │───▶│ Aggregate │───▶│ Event Store │
│          │    │                │    │           │    │ (SQLite/PG) │
└──────────┘    └────────────────┘    └───────────┘    └──────┬──────┘
                                                               │
                                                    Events published
                                                               │
                         READ SIDE                             ▼
┌──────────┐    ┌────────────────┐    ┌────────────┐   ┌──────────────┐
│  Client  │◀───│ QueryHandler   │◀───│ Read Model │◀──│ EventHandler │
│          │    │ (fast reads)   │    │ (flat DB)  │   │ /Projection  │
└──────────┘    └────────────────┘    └────────────┘   └──────────────┘
```

### ASCII Diagram — Full CQRS + ES Flow

```
Client
  │
  ├─[Command: CreateOrder]──────────────────────────────────────────────┐
  │                                                                      │
  │                                            WRITE SIDE               │
  │                                    ┌───────────────────────┐        │
  │                                    │  CommandHandler       │◀───────┘
  │                                    │  - Validate command   │
  │                                    │  - Load aggregate     │
  │                                    │  - Execute command    │
  │                                    └──────────┬────────────┘
  │                                               │ Load events
  │                                               ▼
  │                                    ┌───────────────────────┐
  │                                    │  Order Aggregate      │
  │                                    │  - Apply events       │
  │                                    │  - Business rules     │
  │                                    │  - Raise new events   │
  │                                    └──────────┬────────────┘
  │                                               │ New events
  │                                               ▼
  │                                    ┌───────────────────────┐
  │                                    │  Event Store          │
  │                                    │  (append-only)        │
  │                                    │  - UNIQUE(id, version)│
  │                                    └──────────┬────────────┘
  │                                               │ Events published
  │                                               ▼
  │                                    ┌───────────────────────┐
  │                                    │  Event Handlers       │
  │                                    │  (Projections)        │
  │                                    │  - Update read models │
  │                                    └──────────┬────────────┘
  │                                               │ Update
  │                                               ▼
  │                                    ┌───────────────────────┐
  │                                    │  Read Models (DB)     │
  │                                    │  - OrderSummary       │
  │                                    │  - CustomerHistory    │
  │                                    │  - RevenueReport      │
  │                                    └──────────┬────────────┘
  │                                               │
  └─[Query: GetMyOrders]─────────────▶[QueryHandler]◀──────────────────┘
                                                  │
                                          [Returns fast read data]
                                                  │
                                            Client Response
```

### Eventual Consistency — Kya Problem hai?

```
Timeline:
T=0ms:    Client sends "CreateOrder" command
T=5ms:    Event saved to event store
T=6ms:    Server responds "Order created: order-001"
T=6ms:    Client immediately sends "GET /orders/order-001"
T=8ms:    Query hits read model
T=10ms:   Event handler processes OrderCreated → updates read model
T=8ms?:   READ MODEL NOT YET UPDATED → 404 or stale data!
```

Solutions:
1. **Read-your-writes**: After command, wait for projection update before responding
2. **Optimistic UI**: Client shows tentative state immediately, confirm on next poll
3. **Version passing**: Return event version with command response, query waits for that version
4. **Polling**: Client polls until expected state appears

---

## 9. Projections (Read Models)

### Projection kya hai?

Projection ek function hai jo events ko ek specific read model mein transform karta hai.

```
Events (raw) → Projection Function → Read Model (optimized for queries)
```

### Multiple Projections from Same Events

```python
# Same events, different projections:

# Projection 1: Order Summary (for customer portal)
class OrderSummaryProjection:
    """Flat table: one row per order, optimized for listing"""
    def handle_OrderCreated(self, event):
        db.execute("INSERT INTO order_summary (order_id, customer_id, status) VALUES ...")
    
    def handle_ItemAdded(self, event):
        db.execute("UPDATE order_summary SET total = total + ?, items_count = items_count + 1 WHERE order_id = ?", ...)

# Projection 2: Revenue by Product (for finance dashboard)
class RevenueProjection:
    """Aggregated: product_id → total_revenue"""
    def handle_OrderConfirmed(self, event):
        for item in event.payload["items"]:
            db.execute("INSERT INTO revenue (product_id, revenue) VALUES (?,?) ON CONFLICT DO UPDATE ...", ...)

# Projection 3: Customer Activity (for ML/analytics)
class CustomerActivityProjection:
    """Time-series: customer_id, action, timestamp"""
    def handle_any(self, event):
        db.execute("INSERT INTO customer_activity (customer_id, action, timestamp) ...", ...)
```

### Projection Rebuild — Replay All Events

```python
def rebuild_projection(projection, event_store):
    """
    Projection rebuild kab karo:
    1. New projection add ki
    2. Projection code mein bug tha
    3. Schema change required
    4. Corruption hua
    """
    # Step 1: Clear existing projection data
    projection.reset()
    
    # Step 2: Load all events from beginning
    all_events = event_store.load_all()
    
    # Step 3: Replay
    for event in all_events:
        projection.handle(event)
    
    print(f"Rebuilt projection with {len(all_events)} events")
```

### Online vs Offline Projections

```
ONLINE PROJECTION (Real-time):
- Every write triggers projection update
- Always up-to-date (or eventually consistent)
- Used for: customer-facing read models
- Risk: slow projection = slow write path (if synchronous)

OFFLINE PROJECTION (Batch):
- Rebuild periodically (hourly/daily)
- Slight staleness acceptable
- Used for: analytics, reports, ML features
- Benefit: heavy computation without impacting write path
```

### Event-Driven Projection Update

```python
# Event Bus approach (async, decoupled)
class EventBus:
    def __init__(self):
        self._handlers: dict[str, list] = {}
    
    def subscribe(self, event_type: str, handler):
        self._handlers.setdefault(event_type, []).append(handler)
    
    def publish(self, event: DomainEvent):
        for handler in self._handlers.get(event.event_type, []):
            handler(event)
        for handler in self._handlers.get("*", []):  # Wildcard handlers
            handler(event)

# Setup
bus = EventBus()
bus.subscribe("OrderCreated", order_summary_projection.handle)
bus.subscribe("OrderConfirmed", revenue_projection.handle)
bus.subscribe("*", customer_activity_projection.handle)

# After saving events:
for event in new_events:
    bus.publish(event)  # All interested projections updated
```

---

## 10. Idempotency in Event Processing

### Problem: Exactly-Once Processing

```
Event Processing Pipeline:
Event Store → Message Queue → Projection Handler → Read Model DB

Failures can cause:
1. Network timeout after DB write, before ACK → event redelivered
2. Service crash mid-processing → event reprocessed on restart
3. Duplicate messages in message queue
```

Result: Event processed **multiple times** → Projection data corrupted (double-counting revenue, etc.)

### Solution: Idempotency Key

```python
class IdempotentProjection:
    def __init__(self, conn):
        # Track which events have been processed
        conn.execute("""
            CREATE TABLE IF NOT EXISTS processed_events (
                event_id TEXT PRIMARY KEY,
                processed_at TEXT NOT NULL
            )
        """)
    
    def handle(self, event: DomainEvent):
        # Check if already processed
        existing = self.conn.execute(
            "SELECT 1 FROM processed_events WHERE event_id = ?",
            (event.event_id,)
        ).fetchone()
        
        if existing:
            print(f"Event {event.event_id} already processed, skipping")
            return  # Idempotent — safe to skip
        
        # Process event in transaction
        with self.conn:  # Transaction
            self._process(event)
            # Mark as processed
            self.conn.execute(
                "INSERT INTO processed_events (event_id, processed_at) VALUES (?, ?)",
                (event.event_id, datetime.utcnow().isoformat())
            )
```

### Deduplication Table

```sql
CREATE TABLE processed_events (
    event_id    UUID PRIMARY KEY,
    handler_id  VARCHAR(100) NOT NULL,  -- Which projection processed it
    processed_at TIMESTAMPTZ NOT NULL,
    
    PRIMARY KEY (event_id, handler_id)  -- Same event, different handlers OK
);
```

### At-Least-Once vs Exactly-Once

```
Message delivery guarantees:
- At-most-once:   May miss events (fire-and-forget)
- At-least-once:  May duplicate events (standard message queues)
- Exactly-once:   Theoretically possible but complex (distributed transactions)

Practical approach: At-least-once + Idempotency = Effectively exactly-once
```

---

## 11. Saga with Event Sourcing

### Saga kya hai?

Saga ek **long-running business process** hai jo multiple aggregates ya services span karta hai.

```
Order Placement Saga:
1. Order Created
2. Payment Reserved (Payment Service)
3. Inventory Reserved (Inventory Service)
4. Order Confirmed
5. Shipping Initiated (Shipping Service)

Agar step 4 fail ho? Step 2 aur 3 ko rollback karna padega.
```

### Compensation Events

```python
# Normal flow:
OrderCreated → PaymentReserved → InventoryReserved → OrderConfirmed → OrderShipped

# Failure at InventoryReserved:
OrderCreated → PaymentReserved → InventoryReservationFailed
                    ↓
              PaymentReleased  ← Compensation event
                    ↓
              OrderCancelled   ← Compensation event
```

Compensation events bhi domain events hain — woh bhi event store mein store hote hain.

### Process Manager Pattern

```python
class OrderSaga:
    """Tracks the state of a long-running order process"""
    
    def __init__(self, saga_id: str):
        self.saga_id = saga_id
        self.state = "started"
        self._events = []
    
    def handle_payment_reserved(self, event):
        if self.state == "started":
            self.state = "payment_reserved"
            # Send command to inventory service
            self._events.append(ReserveInventoryCommand(...))
    
    def handle_inventory_failed(self, event):
        if self.state == "payment_reserved":
            self.state = "compensating"
            # Send compensation
            self._events.append(ReleasePaymentCommand(...))
    
    def handle_payment_released(self, event):
        self.state = "cancelled"
        self._events.append(CancelOrderCommand(...))
```

### Saga Event Store

Saga ka state bhi events se rebuild hota hai — same pattern as aggregates.

---

## 12. Real-World Use Cases

### 12.1 Banking — Core Use Case

```
BankAccount Events:
├── AccountOpened(initial_balance=0)
├── KYCCompleted(details={...})
├── Deposited(amount=10000, source="NEFT", ref="TXN001")
├── Withdrawn(amount=3000, method="ATM", location="Mumbai")
├── FDCreated(amount=5000, tenure=365, rate=7.5)
├── SuspiciousActivityFlagged(reason="multiple failed login")
├── AccountLocked(by="fraud_system")
└── AccountUnlocked(by="customer_support", ticket="CS-2024-001")

Benefits:
- Complete transaction history (RBI requirement)
- Account statement = filtered event replay
- Balance = sum of all credit/debit events
- Dispute resolution = show exact event sequence
```

### 12.2 E-Commerce — Order State Machine

```
Order Events:
CartCreated → ItemsAdded (N times) → CheckoutInitiated →
CouponApplied → AddressSelected → PaymentAttempted →
PaymentFailed → PaymentRetried → PaymentSucceeded →
WarehouseAssigned → PickingStarted → PickingCompleted →
PackingCompleted → HandedToShipping → OutForDelivery →
DeliveryAttempted → DeliveryFailed → ReDeliveryScheduled →
Delivered → ReviewRequested

vs Traditional:
Just: status = 'delivered'  (15 state transitions lost!)
```

### 12.3 Inventory Management

```
StockItem Events:
├── ProductAdded(sku="LAPTOP-001", initial_stock=100)
├── StockReceived(qty=50, po_number="PO-2024-001", supplier="Dell")
├── StockReserved(qty=2, order_id="ORD-123")  # On order placement
├── StockReleased(qty=2, order_id="ORD-123")  # On order cancellation
├── StockDeducted(qty=2, order_id="ORD-123")  # On order shipped
├── StockAdjusted(qty=-3, reason="damaged", by="warehouse_staff")
└── LowStockAlertTriggered(threshold=10, current=8)

Current stock = sum of all received - deducted - adjusted
```

### 12.4 User Activity Feed (Like Facebook/Twitter)

```
Events → ActivityFeedProjection → Personalized feed per user

Events:
- UserFollowed → Add to both users' feeds
- PostCreated → Push to all followers' feeds  
- PostLiked → Update engagement metrics
- CommentAdded → Notify post author + other commenters

Projection: Pre-computed feed per user (denormalized, sorted by time)
```

### 12.5 Collaborative Editing (Like Google Docs)

```
Document Events:
├── DocumentCreated(content="")
├── TextInserted(position=0, text="Hello World", by="User1")
├── TextDeleted(position=5, length=6, by="User2")
├── FormattingApplied(start=0, end=5, format="bold", by="User1")
└── DocumentSaved(version=4, checksum="abc123")

OT (Operational Transformation) = Event Sourcing applied to collaborative editing
```

---

## 13. Challenges

### 13.1 Schema Evolution — Old Events, New Handlers

```python
# Version 1 event (stored in 2023):
{
    "event_type": "OrderCreated",
    "payload": {"customer": "C001", "items": ["item1"]}
}

# Version 2 handler (written in 2024) expects:
{
    "event_type": "OrderCreated",
    "payload": {
        "customer_id": "C001",    # renamed from "customer"
        "items": ["item1"],
        "currency": "INR"         # new required field
    }
}

# Problem: Old events don't have "currency" field!
```

### Event Upcasting Solution

```python
class EventUpcaster:
    """Transform old event format to new format"""
    
    def upcast(self, event: DomainEvent) -> DomainEvent:
        if event.event_type == "OrderCreated":
            return self._upcast_order_created(event)
        return event
    
    def _upcast_order_created(self, event: DomainEvent) -> DomainEvent:
        payload = event.payload.copy()
        
        # Migration 1: "customer" → "customer_id"
        if "customer" in payload and "customer_id" not in payload:
            payload["customer_id"] = payload.pop("customer")
        
        # Migration 2: Add default currency
        if "currency" not in payload:
            payload["currency"] = "INR"  # Default for old events
        
        event.payload = payload
        return event
```

### 13.2 GDPR — Right to Be Forgotten

Problem: Events immutable hain, lekin GDPR kehti hai personal data delete karo.

**Solution 1: Crypto-Shredding**

```python
# Encryption approach:
class EncryptingEventStore:
    def store_event_with_pii(self, event: DomainEvent, customer_id: str):
        # Get customer's encryption key
        key = key_store.get_key(customer_id)
        
        # Encrypt PII fields
        payload = event.payload.copy()
        if "email" in payload:
            payload["email"] = encrypt(payload["email"], key)
        if "phone" in payload:
            payload["phone"] = encrypt(payload["phone"], key)
        
        event.payload = payload
        event_store.append([event])
    
    def gdpr_forget(self, customer_id: str):
        # Delete encryption key → all encrypted data becomes garbage
        key_store.delete_key(customer_id)
        # Events still exist but PII is unreadable → GDPR compliant
```

**Solution 2: Tombstone Event**

```python
# Add a "forget" event
gdpr_event = PersonalDataDeleted(
    aggregate_id=f"customer-{customer_id}",
    payload={
        "customer_id": customer_id,
        "deleted_fields": ["name", "email", "phone", "address"],
        "reason": "GDPR Article 17 Request",
        "request_id": "GDPR-2024-001"
    }
)
event_store.append([gdpr_event])

# Projection rebuild karte waqt:
# - Agar PersonalDataDeleted event aaye → woh customer ke saare PII fields NULL kar do
```

### 13.3 Query Complexity

```python
# Problem: "Orders jisme customer ne ek hi product 2 baar order ki ho"
# Event sourcing ke saath ye query complex hai — projection mein
# pre-compute karna padega

# Solution: Domain-specific projections
class RepeatPurchaseProjection:
    """Pre-compute repeat purchase data for analytics"""
    
    def handle_OrderConfirmed(self, event):
        for item in event.payload.get("items", []):
            # Upsert: customer_id, product_id, purchase_count
            self.db.execute("""
                INSERT INTO repeat_purchases (customer_id, product_id, count)
                VALUES (?, ?, 1)
                ON CONFLICT (customer_id, product_id) 
                DO UPDATE SET count = count + 1
            """, (event.payload["customer_id"], item["product_id"]))
```

### 13.4 Eventually Consistent UI

```
Problem:
1. User places order → "Order Created" confirmation shown
2. User navigates to "My Orders" page
3. Projection not yet updated → Order not in list!
4. User confused: "Mera order kahan gaya?"
```

Solutions:
```python
# Solution 1: Return version with command response
response = {
    "order_id": "order-001",
    "expected_version": 4,  # Read model should have this version
}

# Client side: poll until version >= 4
GET /orders?min_version=4  → 202 Accepted (not ready yet)
GET /orders?min_version=4  → 200 OK (ready)

# Solution 2: Optimistic UI
# Client shows created order immediately from local state
# Server confirms/corrects on next poll

# Solution 3: Read-after-write consistency
# After command: synchronously update projection before responding
# (Slower but consistent)
```

### 13.5 Operational Complexity

```
Event Sourcing adds:
- Event Store infrastructure
- Projection management
- Schema migration tooling
- Snapshot management
- Event bus/messaging

When NOT to use Event Sourcing:
1. Simple CRUD apps (blog, settings, profiles)
2. Small teams without domain expertise
3. Simple reporting only use case
4. No audit requirements
5. Data volume very low
```

---

## 14. Interview Q&As — 10 Questions

### Q1: Event Sourcing aur Traditional Storage mein kya difference hai?

**Answer:**

Traditional storage mein hum **current state** store karte hain — database ka ek row, ek object represent karta hai. Jab bhi state change hoti hai, row update ho jati hai aur purana state permanently lost ho jata hai.

Event Sourcing mein hum **events (facts)** store karte hain — "kya hua" track karte hain, "kya hai" nahi. State is events ko replay karke derive ki jaati hai. Event log append-only hota hai — kabhi update/delete nahi.

Key differences:
- Traditional: Mutable state, no history | Event Sourcing: Immutable events, complete history
- Traditional: Fast reads (direct query) | Event Sourcing: Fast reads via projections, audit trail free
- Traditional: Simple setup | Event Sourcing: Complex but powerful

---

### Q2: Snapshot kyun zaroori hai aur kab use karein?

**Answer:**

Jab ek aggregate pe bahut saare events ho jaate hain (typically 100+), toh har request pe saare events reload aur replay karne se performance degrade hoti hai. O(n) complexity issue hai.

Snapshot solution: Aggregate ke current state ka "photograph" periodically save karo. Load karte waqt:
1. Latest snapshot load karo (O(1))
2. Sirf snapshot ke baad ke events replay karo (much fewer)

Rule of thumb: Every 50-100 events ek snapshot save karo. Snapshot frequency domain-specific hai — high-write aggregates ko zyada frequent snapshots chahiye.

---

### Q3: CQRS ka main benefit kya hai? Kab use karein?

**Answer:**

CQRS ka main benefit **read aur write concerns ko separate karna** hai:

- **Write model** business logic aur consistency ke liye optimized — complex validations, domain rules
- **Read model** query performance ke liye optimized — denormalized, fast, no JOINs

Use karein jab:
1. Read/write ratio bahut different ho (e.g., 100:1 reads)
2. Read aur write models ka schema significantly different ho
3. Different scaling requirements (read replicas for queries)
4. Complex domain logic with many business rules

Avoid karein for simple CRUD applications — unnecessary complexity.

---

### Q4: Eventual Consistency kaise handle karte hain?

**Answer:**

CQRS + async projections mein write aur read models ke beech mein lag hota hai — "eventual consistency".

Strategies:
1. **Read-your-writes**: Projection update hone ka wait karo command response se pehle (synchronous projection)
2. **Version tracking**: Command response mein expected_version return karo, query side is version tak wait kare
3. **Optimistic UI**: Client side pe tentative state immediately show karo, server confirmation baad mein
4. **Stale indicator**: UI mein "Updating..." spinner show karo jab data potentially stale ho
5. **Polling**: Client retry kare jab tak expected data na aaye

Production mein typically optimistic UI + version tracking combination use hota hai.

---

### Q5: Projection rebuild kaise karte hain aur kab zaroori hota hai?

**Answer:**

Projection rebuild = event store se saare events replay karke read model dobara banao.

Kab rebuild karein:
- New projection add ki
- Projection code mein bug fix hua
- Schema change required (new column, renamed field)
- Data corruption hua

Process:
```
1. New/empty projection table create karo
2. All events event store se load karo (chronologically)
3. Each event projection handlers se pass karo
4. Old projection replace karo naye se
```

Production mein blue-green projection rebuild karte hain — naya projection background mein rebuild hota hai, jab complete ho jaaye toh swap karo.

---

### Q6: Event Schema Evolution kaise handle karte hain?

**Answer:**

Events ek baar persist ho jaate hain toh unhe change nahi kar sakte. Lekin business logic badalni padti hai — iska solution **Event Upcasting** hai.

Event Upcaster ek transformation layer hai jo old event format ko current expected format mein convert karta hai load karte waqt. Store mein old format rahta hai, but handler ko current format milta hai.

Strategies:
1. **Upcasting**: On-the-fly transformation during load
2. **Weak schema**: Payload mein optional fields — new fields optional rakhein
3. **Version in event type**: `OrderCreated_v1`, `OrderCreated_v2` — separate handlers
4. **Rebuild projections**: Naya upcaster add karo, projection rebuild karo

Best practice: Payload mein additive changes hi karo — new optional fields add karo, existing fields kabhi remove ya rename mat karo without upcaster.

---

### Q7: GDPR "Right to be Forgotten" Event Sourcing mein kaise implement karte hain?

**Answer:**

Event Sourcing mein events immutable hain — delete karna allowed nahi. GDPR ke saath yeh tension hai. Two main approaches:

**Crypto-Shredding (Preferred)**:
- PII fields (email, phone, name) ko per-customer encryption key se encrypt karo
- Key ek separate key store mein rakho
- GDPR request aane pe: encryption key delete karo
- Events store mein rehte hain, but PII fields decrypt nahi ho sakti — effectively forgotten

**Tombstone Events**:
- `PersonalDataDeleted` event append karo
- Projection rebuild karte waqt, is event ke baad woh customer ke PII fields NULL set karo
- Events exist karte hain but projection clean hoti hai

Both approaches auditable bhi hain — "kis ne, kab, kyun" GDPR request process hua, yeh bhi event se track hota hai.

---

### Q8: Aggregate Version number ka kya role hai?

**Answer:**

Version number do kaam karta hai:

**1. Optimistic Concurrency Control:**
```
Event store mein: UNIQUE constraint on (aggregate_id, version)
Thread A: Order load (version=5), confirm event raise (version=6)
Thread B: Order load (version=5), add item raise (version=6)
Thread A saves: version=6 → SUCCESS
Thread B saves: version=6 → CONFLICT! (already exists)
Thread B must reload and retry
```

**2. Event Ordering:**
Version ensures events ko exact sequence mein replay kar sako. Global timestamp se conflicts ho sakte hain (same millisecond), but version unambiguous hai.

Production best practice: Expected version event store ko pass karo — "I expect this aggregate to be at version 5 before I append version 6". This prevents concurrent modification bugs.

---

### Q9: Idempotency in Event Processing kaise ensure karte hain?

**Answer:**

Idempotency = same event multiple times process karna, same result produce karna — no duplicates.

Implementation:
1. **Deduplication table**: Processed event IDs track karo per projection
2. **Check before process**: Event handle karne se pehle check karo ki already processed hai ya nahi
3. **Atomic transaction**: Check + process + mark-as-processed ek transaction mein karo

```python
def handle(self, event):
    if self.is_processed(event.event_id):
        return  # Already handled, skip
    
    with transaction:
        self.process(event)           # Apply to read model
        self.mark_processed(event.event_id)  # Record as done
```

Event ID (UUID) idempotency key hai — globally unique, har event ke liye unique. Deduplication table cleanup periodically karo (old events after N days).

---

### Q10: Event Sourcing kab USE NAHI karna chahiye?

**Answer:**

Event Sourcing powerful hai but over-engineering ban sakti hai. Avoid karein jab:

1. **Simple CRUD**: Blog posts, user settings, product catalog — no complex state transitions
2. **No audit requirements**: App ko history chahiye hi nahi
3. **Small team, quick delivery**: Learning curve high hai, time investment significant
4. **Reporting-only**: Analytics apps where you just aggregate data
5. **Low complexity domain**: Less than 5-6 state transitions per aggregate
6. **Frequent schema changes**: Event schema migration painful hai — unstable domains mein avoid karo

Use karein jab:
- Complex state machines (order processing, loan approval, insurance claims)
- Audit trail mandatory (finance, healthcare, legal)
- Time-travel debugging zaroori
- Multiple read models required
- Event-driven integration between services

**Rule of thumb**: Event sourcing benefits tab milte hain jab aggregate ki lifecycle complex hoti hai. Simple entities (User profile, Product listing) ke liye traditional storage better hai.

---

## Summary — Key Takeaways

```
Event Sourcing:
├── Store events (immutable facts), not current state
├── State = replay of events
├── Append-only event log
├── Benefits: audit trail, time travel, replay, multiple projections
├── Challenges: schema evolution, GDPR, query complexity
└── Key components: Aggregate, Event Store, Snapshot Store

CQRS:
├── Separate Command (write) and Query (read) models
├── Commands: change state, return nothing/ID
├── Queries: return data, no state change
├── Benefits: optimize reads and writes independently
└── Tradeoff: eventual consistency

Together (ES + CQRS):
├── Write side: Command → Aggregate → Events → Event Store
├── Read side: Events → Projections → Read Models → Queries
├── Eventual consistency between write and read
└── Most powerful in complex domains with high audit requirements
```

---

*End of Event Sourcing + CQRS Theory Guide*
*Part of: Python Backend Developer — Microservices (Year 3-4)*
*Next: 06_distributed_transactions_2pc_saga.md*
