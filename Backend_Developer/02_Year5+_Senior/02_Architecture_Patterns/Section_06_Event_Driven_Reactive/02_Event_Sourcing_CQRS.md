# Lecture 2: Event Sourcing & CQRS

> *"Event Sourcing keeps a detailed diary of everything that happens. CQRS gives separate lanes to writes and reads."*

**Section 6 — Event-Driven & Reactive Systems**

---

## 🎯 Is Lecture Mein Kya Seekhenge?

- **Why Event Sourcing + CQRS?** — limitations of CRUD
- **What is Event Sourcing?** — events as source of truth
- **Benefits of ES** — auditability, replay, flexibility
- **Challenges of ES** — schema evolution, performance
- **What is CQRS?** — command + query separation
- **Write model deep dive**
- **Read model deep dive**
- **Event Store** — the heart of the system
- **Projections** — building read models
- **Event versioning** — evolving safely
- **Full end-to-end flow**
- **When to use these patterns**

---

## 1. Why Event Sourcing + CQRS?

### Limitations of Traditional CRUD

```
Traditional model:
   CREATE → row in DB
   READ   → row from DB
   UPDATE → row in DB (overwrites previous!)
   DELETE → row from DB (gone forever)

Problems:
   ✗ Lost history (only latest state remains)
   ✗ Read + write share same model (compromise)
   ✗ Hard to audit who did what
   ✗ Can't time-travel
   ✗ Read scale = write scale
```

### What Event Sourcing Brings

```
Instead of storing current state:
   Store the SEQUENCE of EVENTS that led to it.

Current state = replay all events
   = derived data, not source of truth
```

### What CQRS Brings

```
Instead of one model for read + write:
   ✓ Write model: enforce rules, capture intent
   ✓ Read model: optimized for queries

   = Each side independently designed + scaled
```

### When Combined

```
Powerful foundation for:
   ✓ Scalability
   ✓ Performance
   ✓ Traceability
   ✓ Maintainability
   ✓ Adaptability

→ Modern, complex systems benefit enormously.
```

---

## 2. What Is Event Sourcing?

### Core Idea

**Store every state change as an immutable event. Current state = replay of all events.**

### Traditional vs Event Sourcing

```
TRADITIONAL CRUD:
   Account:
      balance = 100

   (Single row, no history of how we got there)

EVENT SOURCING:
   Events for account:
      AccountCreated (balance=0)
      Deposited (amount=200)
      Withdrew (amount=50)
      Deposited (amount=50)
      Withdrew (amount=100)
   
   Current state = sum of events = 100
   But FULL HISTORY preserved!
```

### Visual

```
                     Event Log
   ┌─────────────────────────────────────────┐
   │ t=0: AccountCreated (balance=0)         │
   │ t=1: Deposited (+200)                   │
   │ t=2: Withdrew (-50)                     │
   │ t=3: Deposited (+50)                    │
   │ t=4: Withdrew (-100)                    │
   └─────────────────────────────────────────┘
                       │
                       │ Replay
                       ▼
              Current state: 100
```

### Key Properties

```
✓ Events are IMMUTABLE
   Never change or delete
   Append-only log

✓ Events are TIME-STAMPED
   Know exact order + when

✓ Events are the SOURCE OF TRUTH
   Not the current state!
   State is derived/computed

✓ Full HISTORY preserved
   Reconstruct ANY past state
```

### Where Data Lives

```
Event Store: Append-only log of events
   ✓ The source of truth
   ✓ All changes recorded here
   ✓ Never modified

Read Models: Derived views
   ✓ For querying
   ✓ Built from events
   ✓ Can be rebuilt anytime
```

---

## 3. Key Benefits of Event Sourcing

### Benefit 1: Complete Audit Trail

```
Every change captured as event:
   ✓ Who did it (user ID)
   ✓ What changed (event payload)
   ✓ When (timestamp)
   ✓ Why (event type / context)

Result:
   ✓ Compliance ready (SOX, GDPR)
   ✓ Forensic analysis
   ✓ Debugging gold mine
   ✓ Customer support: "What happened to my order?"
```

### Benefit 2: Time-Travel Debugging

```
Problem in production?
   ✓ Replay events up to incident time
   ✓ See exact state when bug occurred
   ✓ Reproduce locally
   ✓ Test fix against historical data
```

### Benefit 3: Multiple Read Models

```
Same event stream → multiple views:

   Event Stream:
      OrderPlaced, OrderShipped, OrderDelivered
              │
              ▼
   ┌──────────┬──────────┬──────────┬──────────┐
   │ User     │ Admin    │ Analytics│ Mobile   │
   │ Dashboard│ Panel    │ Reports  │ App View │
   └──────────┴──────────┴──────────┴──────────┘
   
   Each tailored to its specific need!
```

### Benefit 4: Easy to Add New Features

```
New requirement: "Show 30-day order trend per user"

With CRUD:
   ✗ Data might not exist
   ✗ Backfill from when?

With Event Sourcing:
   ✓ Replay events from 30 days ago
   ✓ Build new projection
   ✓ Done!
```

### Benefit 5: Natural Fit for DDD

```
Domain-Driven Design (DDD) emphasizes:
   ✓ Domain events
   ✓ Bounded contexts
   ✓ Eventual consistency

Event Sourcing aligns naturally:
   ✓ Events ARE the domain
   ✓ Services emit events about their context
   ✓ Other services react asynchronously
```

### Benefit 6: Enables Reactive Patterns

```
Events trigger downstream actions:
   OrderPlaced
      → Send confirmation email
      → Update analytics
      → Award loyalty points
      → Trigger fulfillment
   
   All without touching core logic!
```

---

## 4. Challenges of Event Sourcing

### Challenge 1: Schema Evolution

```
Events are IMMUTABLE — can't go back and change them.

But business logic evolves:
   ✗ Field renamed
   ✗ New required field added
   ✗ Data structure changed

Solutions:
   ✓ Versioned events (UserSignedUp.v1, UserSignedUp.v2)
   ✓ Up-casters (transform old → new format at read)
   ✓ Backward-compatible changes only (additive)
   ✓ Never remove or rename existing fields
```

### Challenge 2: Replay Performance

```
1000s of events for one entity?
   ✗ Slow to replay every time
   
Solutions:
   ✓ SNAPSHOTS: periodic state checkpoints
      Replay only events SINCE last snapshot
   
   ✓ CACHING: in-memory state
   
   ✓ READ MODELS: pre-computed views
      (don't replay for queries)
```

### Challenge 3: Mental Model Shift

```
Developers used to CRUD:
   ✗ "Where's the row?"
   ✗ "Just update this field"

Event Sourcing mindset:
   ✓ "What event represents this change?"
   ✓ "What's the intent?"
   ✓ Think in events, not rows

→ Requires team training + discipline
```

### Challenge 4: Debugging Distributed Events

```
Event flow across services is harder to trace:
   ✗ Where did this event go?
   ✗ Why didn't it cause expected reaction?

Solutions:
   ✓ Distributed tracing (correlation IDs)
   ✓ Centralized event log
   ✓ Visualization tools
```

### Challenge 5: Not Always the Right Fit

```
Event Sourcing is HEAVY:
   ✓ Justified for complex domains
   ✓ When audit + history matter
   ✓ When events drive workflows

NOT justified for:
   ✗ Simple CRUD apps
   ✗ Internal admin tools
   ✗ Read-only systems

→ Use it when domain complexity justifies it.
```

---

## 5. What Is CQRS?

### Core Idea

**CQRS = Command Query Responsibility Segregation**

**Separate models for writing (commands) and reading (queries).**

### Without CQRS

```
                  ┌──────────────┐
   Client ───►   │  ONE MODEL   │   ◄─── Database
                  │  for both    │
                  │  read + write│
                  └──────────────┘
   
   Compromise: not optimal for either.
   Mixed concerns.
```

### With CQRS

```
                  ┌──────────────┐
   Client ───►   │ WRITE MODEL  │   ──► Event Store
   (commands)    │ (logic +     │       (source of truth)
                  │  validation) │
                  └──────────────┘
                         │
                         │ events
                         ▼
                  ┌──────────────┐
                  │ READ MODEL   │   ◄─── Client
                  │ (optimized   │       (queries)
                  │  for reads)  │
                  └──────────────┘
```

### Why Separate?

```
Reads and writes have DIFFERENT needs:

WRITES:
   ✓ Validate inputs
   ✓ Enforce business rules
   ✓ Maintain consistency
   ✓ Low volume usually

READS:
   ✓ Fast retrieval
   ✓ Flexible queries
   ✓ Denormalized data
   ✓ High volume usually
   ✓ Often 100x more reads than writes
```

### Benefits

```
✓ INDEPENDENT SCALING
   Scale reads + writes separately

✓ OPTIMIZED MODELS
   Each tailored to its purpose

✓ FLEXIBILITY
   Multiple read models from same writes

✓ CLEANER CODE
   Separate concerns
```

---

## 6. Write Model Deep Dive

### Responsibilities

```
✓ Validate commands
✓ Enforce business rules
✓ Capture intent as events
✓ Persist events
✓ Reject invalid operations
```

### Visual: Command Flow

```
   ┌──────────────┐
   │   Client     │
   └──────┬───────┘
          │
          │ Command: ChangeShippingAddress
          ▼
   ┌──────────────────────────────────────┐
   │       WRITE MODEL                     │
   │                                       │
   │   1. Validate command                 │
   │      - Is user authorized?            │
   │      - Is new address valid?          │
   │                                       │
   │   2. Apply business rules             │
   │      - Order not yet shipped?         │
   │      - Within edit window?            │
   │                                       │
   │   3. Emit domain event                │
   │      "ShippingAddressChanged"         │
   │                                       │
   │   4. Persist to event store           │
   └──────────────────────────────────────┘
          │
          ▼
   ┌──────────────────────────────────────┐
   │       EVENT STORE                     │
   │   ✓ Source of truth                   │
   │   ✓ Append-only                       │
   └──────────────────────────────────────┘
```

### Properties

```
✓ SYNCHRONOUS
   Command accepted → events stored
   OR
   Command rejected → no events

✓ CONSISTENT
   Business rules enforced atomically
   Within aggregate boundary

✓ EXPRESSIVE
   Captures intent + context
```

### Example: Order Aggregate

```python
class OrderAggregate:
    """Write model for orders"""
    
    def __init__(self):
        self.id = None
        self.status = None
        self.items = []
        self.total = 0
        self.events = []
    
    # ── Apply command ──
    def place_order(self, user_id, items):
        if self.status is not None:
            raise ValueError("Order already placed")
        
        total = sum(i["price"] * i["quantity"] for i in items)
        
        # Emit event (don't update state directly!)
        self._apply_event(OrderPlacedEvent(
            order_id=str(uuid.uuid4()),
            user_id=user_id,
            items=items,
            total=total,
        ))
    
    def cancel(self):
        if self.status != "PLACED":
            raise ValueError("Cannot cancel")
        if datetime.utcnow() - self.placed_at > timedelta(hours=2):
            raise ValueError("Cancellation window expired")
        
        self._apply_event(OrderCancelledEvent(order_id=self.id))
    
    # ── Apply event (updates state) ──
    def _apply_event(self, event):
        self.events.append(event)
        if isinstance(event, OrderPlacedEvent):
            self.id = event.order_id
            self.status = "PLACED"
            self.items = event.items
            self.total = event.total
            self.placed_at = datetime.utcnow()
        elif isinstance(event, OrderCancelledEvent):
            self.status = "CANCELLED"
    
    # ── Rebuild from events ──
    @classmethod
    def from_events(cls, events):
        order = cls()
        for event in events:
            order._apply_event(event)
        return order
```

---

## 7. Read Model Deep Dive

### Responsibilities

```
✓ Optimize for queries
✓ Denormalize data
✓ Index appropriately
✓ Update via projections (from events)
```

### Visual: Read Flow

```
   ┌──────────────┐
   │ EVENT STORE  │
   │              │
   │ OrderPlaced  │ ─── projection ──┐
   │ OrderShipped │                    │
   │ OrderDelivered                    │
   └──────────────┘                    │
                                       ▼
                          ┌──────────────────────┐
                          │   READ MODEL          │
                          │                       │
                          │  Optimized for fast   │
                          │  queries.             │
                          │                       │
                          │  ✓ Denormalized       │
                          │  ✓ Indexed            │
                          │  ✓ Tailored per use   │
                          └───────────┬───────────┘
                                      │
                                      │ query
                                      ▼
                              ┌────────────┐
                              │   Client    │
                              └────────────┘
```

### Multiple Read Models From Same Stream

```
Event Stream
      │
      ├─► User dashboard model    (per-user view)
      ├─► Admin reporting model    (aggregated)
      ├─► Search index             (Elasticsearch)
      ├─► Cache                    (Redis)
      ├─► Analytics warehouse      (BigQuery)
      └─► Mobile API view          (lightweight)

Each independently designed!
```

### Polyglot Persistence

```
Each read model picks the BEST database:

✓ User profile     → PostgreSQL (relational)
✓ Search           → Elasticsearch
✓ Real-time        → Redis
✓ Analytics        → BigQuery / Snowflake
✓ Graph queries    → Neo4j

→ Use right tool for each job!
```

### Eventual Consistency

```
Write happens:
   t=0: OrderPlaced event emitted

Read model updates:
   t=50ms: Inventory view updated
   t=100ms: User dashboard updated
   t=2s:    Analytics warehouse updated

→ Slight delay (eventual consistency)
→ Acceptable for most use cases
→ Plan for it (show "Processing..." messages)
```

---

## 8. Event Store — The Heart

### What It Is

**Specialized database optimized for storing append-only events.**

### Visual

```
   ┌──────────────────────────────────────┐
   │           EVENT STORE                 │
   │     (append-only event log)           │
   │                                        │
   │  Stream: order-123                     │
   │  ────────────────────                  │
   │  1: OrderPlaced (t=0)                  │
   │  2: PaymentReceived (t=10)             │
   │  3: OrderShipped (t=3600)              │
   │  4: OrderDelivered (t=86400)           │
   │                                        │
   │  Stream: user-456                      │
   │  ────────────────────                  │
   │  1: UserSignedUp (t=0)                 │
   │  2: EmailChanged (t=100)               │
   │  3: PasswordUpdated (t=500)            │
   │                                        │
   └──────────────────────────────────────┘
```

### Key Properties

```
✓ APPEND-ONLY
   Never modify or delete
   New events go at the end

✓ ORDERED
   Within stream/aggregate: strict order
   Across streams: no guarantee

✓ DURABLE
   Survives crashes
   Often replicated

✓ STREAMED
   Subscribers get new events real-time

✓ REPLAYABLE
   Read from beginning anytime
```

### Popular Event Stores

```
✓ EventStoreDB (purpose-built)
✓ Apache Kafka (with long retention)
✓ AWS Kinesis Data Streams
✓ PostgreSQL (append-only tables)
✓ Axon Server (Java-focused)
```

### Storage Schema (PostgreSQL Example)

```sql
CREATE TABLE events (
    sequence_number BIGSERIAL PRIMARY KEY,
    stream_id VARCHAR NOT NULL,           -- e.g., "order-123"
    stream_version INTEGER NOT NULL,      -- 1, 2, 3...
    event_type VARCHAR NOT NULL,
    event_data JSONB NOT NULL,
    metadata JSONB,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Optimistic concurrency control
    UNIQUE (stream_id, stream_version)
);

CREATE INDEX idx_stream ON events (stream_id, stream_version);
CREATE INDEX idx_event_type ON events (event_type, timestamp);
```

---

## 9. Projections — Building Read Models

### What Are Projections?

**Processes that listen to events and update read-optimized views.**

### Visual

```
   ┌──────────────┐
   │ EVENT STORE  │
   └──────┬───────┘
          │
          │ subscribe
          ▼
   ┌─────────────────────┐
   │   PROJECTION         │
   │                      │
   │   Receives events    │
   │   Updates read DB    │
   └──────────┬───────────┘
              │
              ▼
   ┌─────────────────────┐
   │   READ MODEL DB      │
   │   (denormalized)     │
   └─────────────────────┘
```

### Example: User Dashboard Projection

```python
class UserDashboardProjection:
    """
    Listens to events, maintains per-user dashboard view.
    """
    
    def __init__(self, db):
        self.db = db
    
    async def handle(self, event):
        if event.type == "OrderPlaced":
            await self._on_order_placed(event)
        elif event.type == "OrderShipped":
            await self._on_order_shipped(event)
        elif event.type == "OrderDelivered":
            await self._on_order_delivered(event)
    
    async def _on_order_placed(self, event):
        # Insert order summary
        await self.db.execute("""
            INSERT INTO user_orders 
                (user_id, order_id, status, total, items_count, placed_at)
            VALUES ($1, $2, 'PLACED', $3, $4, $5)
        """,
            event.user_id,
            event.order_id,
            event.total,
            len(event.items),
            event.timestamp,
        )
    
    async def _on_order_shipped(self, event):
        await self.db.execute("""
            UPDATE user_orders SET status = 'SHIPPED', shipped_at = $1
            WHERE order_id = $2
        """, event.timestamp, event.order_id)
```

### Replayable Projections

```
Bug in projection? Rebuild from scratch:

   1. Delete read model data
   2. Reset projection position to 0
   3. Replay events from beginning
   4. Read model rebuilt with new logic!
   
No data loss — event store is intact.
```

### Multiple Projections from Same Stream

```python
# Same events, different projections

# Projection 1: User dashboard (denormalized per user)
user_dashboard_projection = ...

# Projection 2: Admin reporting (aggregated by date)
admin_reports_projection = ...

# Projection 3: Search index (Elasticsearch)
search_index_projection = ...

# Projection 4: ML feature store
ml_features_projection = ...

# All process the same events independently!
```

---

## 10. Event Versioning

### The Challenge

```
Events are IMMUTABLE.
Business logic evolves.

How to handle?
   ✓ Versioning strategies
   ✓ Up-casters
   ✓ Backward compatibility discipline
```

### Strategy 1: Versioned Event Types

```python
class UserRegisteredV1(BaseEvent):
    """Original version"""
    event_type: str = "UserRegistered.v1"
    user_id: str
    email: str
    name: str

class UserRegisteredV2(BaseEvent):
    """v2 - added phone (new required field)"""
    event_type: str = "UserRegistered.v2"
    user_id: str
    email: str
    name: str
    phone: str  # NEW required field

# Consumers handle both versions:
async def handle_user_registered(event):
    if event.event_type == "UserRegistered.v1":
        # Old version - phone unknown
        await user_db.create(event.user_id, event.email, event.name, phone=None)
    elif event.event_type == "UserRegistered.v2":
        # New version
        await user_db.create(event.user_id, event.email, event.name, event.phone)
```

### Strategy 2: Up-Casters

```python
"""
Up-caster: transforms old event format to new format at runtime.
Single handler code, regardless of stored version.
"""

class UserRegisteredUpCaster:
    """Converts v1 → v2 on the fly"""
    
    def upcast(self, event):
        if event.event_type == "UserRegistered.v1":
            # Convert v1 → v2 (assume default phone)
            return UserRegisteredV2(
                **event.dict(exclude={"event_type"}),
                event_type="UserRegistered.v2",
                phone="UNKNOWN",  # Default for old events
            )
        return event

# In consumer:
async def handle(raw_event):
    event = upcaster.upcast(raw_event)
    # Always work with v2 format internally
    await handle_v2(event)
```

### Strategy 3: Additive Changes Only

```
✓ ADD new optional fields
✓ DEPRECATE old fields (keep accepting them)
✓ Use semantic versioning

✗ REMOVE existing fields
✗ RENAME fields
✗ CHANGE types
✗ REORDER fields (in some formats)
```

### Best Practices

```
1. Plan for evolution from day 1
2. Use schema registry to track versions
3. Test backward compatibility in CI
4. Keep up-casters as separate, testable units
5. Document migration paths
6. Never modify events in the store
```

---

## 11. Putting It All Together — Full Flow

### End-to-End Example: Place Order

```
1. CLIENT
   │
   │ POST /orders {user_id, items}
   ▼
2. WRITE SIDE (Command Handler)
   │
   │ ✓ Validate command
   │ ✓ Apply business rules
   │ ✓ Emit OrderPlaced event
   ▼
3. EVENT STORE
   │
   │ ✓ Persist event (append-only)
   │ ✓ Publish to event stream
   ▼
4. PROJECTIONS (listening)
   │
   ├─► User dashboard view (PostgreSQL)
   ├─► Admin reports (BigQuery)
   ├─► Search index (Elasticsearch)
   └─► Cache (Redis)
   ▼
5. CLIENT QUERIES
   │
   │ GET /users/123/orders
   ▼
6. READ MODEL
   │
   │ ✓ Fast query
   │ ✓ Pre-computed
   │ ✓ Denormalized
   ▼
7. RESPONSE → CLIENT
```

### Sample Code Flow

```python
# WRITE SIDE
@app.post("/orders")
async def place_order(cmd: PlaceOrderCommand):
    # 1. Load aggregate from event store
    events = await event_store.load(f"order-{cmd.order_id}")
    order = OrderAggregate.from_events(events)
    
    # 2. Execute command (may emit events)
    order.place_order(cmd.user_id, cmd.items)
    
    # 3. Save new events
    await event_store.append(
        stream_id=f"order-{order.id}",
        events=order.events,
    )
    
    return {"order_id": order.id, "status": "ACCEPTED"}

# PROJECTION (separate process)
async def projection_runner():
    async for event in event_store.subscribe("orders"):
        # Update read model
        await user_dashboard_projection.handle(event)
        await admin_reports_projection.handle(event)
        await search_projection.handle(event)

# READ SIDE
@app.get("/users/{user_id}/orders")
async def get_user_orders(user_id: int):
    # Query the read model (fast!)
    return await read_db.fetch(
        "SELECT * FROM user_orders WHERE user_id = $1 ORDER BY placed_at DESC",
        user_id,
    )
```

---

## 12. When to Use Event Sourcing + CQRS

### Use When:

```
✓ Complex business domain
   - Lots of business rules
   - State transitions matter
   - Audit critical

✓ Audit + compliance required
   - Financial systems
   - Healthcare
   - Government

✓ Read >> Write
   - Heavy reporting
   - Many query views
   - Need to scale reads separately

✓ Time-travel debugging valuable
   - Bug reproduction
   - Replay scenarios

✓ Event-driven architecture
   - Microservices coordination
   - Reactive systems
   - DDD-aligned design
```

### Don't Use When:

```
✗ Simple CRUD application
   - No complex domain
   - Just data in / data out

✗ Small team / limited resources
   - Learning curve
   - Operational overhead

✗ Strict consistency required everywhere
   - Eventually consistent reads may not work

✗ Performance-critical for writes
   - Replay can be slow without snapshots
```

### Decision Matrix

```
Domain complexity:    Low   →   High
                       ↓         ↓
Use ES + CQRS?     Avoid     Strong fit

Team experience:    Junior  →  Senior
                       ↓         ↓
Use ES + CQRS?     Risky     Manageable

Audit needs:        None    →   Critical
                       ↓         ↓
Use ES + CQRS?     Skip      Required
```

---

## 13. Real-World Examples

### Banking & Finance

```
Transactions = events
   ✓ Money deposited
   ✓ Money withdrawn
   ✓ Transfer initiated
   ✓ Transfer completed
   
Balance = derived from events
Full audit trail for compliance
```

### E-commerce

```
Order lifecycle as events:
   ✓ Order placed
   ✓ Payment received
   ✓ Items reserved
   ✓ Order shipped
   ✓ Delivered
   ✓ Returned

State at any point = replay events
```

### Healthcare

```
Patient records as events:
   ✓ Diagnosis recorded
   ✓ Medication prescribed
   ✓ Lab result added
   ✓ Treatment performed
   
Required for medical-legal compliance
```

### Real-World Adopters

```
✓ EventStore (the company) - banking, finance
✓ Walmart - inventory management
✓ ING Bank - account systems
✓ Uber - dispatching, billing
✓ LinkedIn - many internal systems
✓ Most modern fintechs
```

---

## 14. Common Patterns

### Pattern 1: Snapshots

```
Replay 1000s of events = slow.

Solution: periodic snapshots.

   t=0:   AccountCreated
   t=10:  Deposit
   t=20:  Withdraw
   ...
   t=1000: <-- SNAPSHOT at version 1000
   t=1001: Deposit
   t=1002: Withdraw

To get current state:
   1. Load snapshot (version 1000)
   2. Replay events since (1001, 1002, ...)
   
Much faster!
```

### Pattern 2: Saga (for workflows)

```
Multi-step processes coordinated by events:
   OrderPlaced → reserve inventory → charge payment → ship
   
Each step emits events.
Failed step triggers compensating events.

(See Lecture 4 for full saga details!)
```

### Pattern 3: Process Manager

```
State machine tracking multi-event workflows:
   ✓ Subscribes to events
   ✓ Tracks workflow state
   ✓ Emits commands based on state
   
Used for complex orchestration logic.
```

### Pattern 4: Outbox

```
Atomic DB write + event publishing:
   ✓ Write business data + event in same transaction
   ✓ Publisher process picks up + delivers events
   ✓ Guaranteed event delivery if write succeeds

(See Lecture 4 for outbox details!)
```

---

## 15. Summary — Key Takeaways

```
┌──────────────────────────────────────────────────────────────┐
│  ✅ Event Sourcing = events are source of truth                │
│  ✅ State is DERIVED by replaying events                       │
│  ✅ Events are IMMUTABLE, append-only                          │
│  ✅ Full audit trail + time-travel debugging                   │
│  ✅ CQRS = separate read + write models                        │
│  ✅ Write side: validate + enforce rules + emit events         │
│  ✅ Read side: optimized views built via projections           │
│  ✅ Event Store = the heart (e.g., EventStoreDB, Kafka)        │
│  ✅ Projections build multiple read models                     │
│  ✅ Event versioning via up-casters + additive changes         │
└──────────────────────────────────────────────────────────────┘
```

### The Universal Rules

```
1. Events are FACTS - immutable, past tense
2. State = derived from events (not stored directly)
3. Separate write model (commands) from read model (queries)
4. Multiple read models from same event stream
5. Event Store is append-only - never modify or delete
6. Use snapshots for performance with long event streams
7. Version events from day 1
8. Embrace eventual consistency on read side
9. Use only for COMPLEX domains - simple CRUD doesn't need this
10. Combines naturally with microservices + DDD
```

---

## 🎬 What's Next?

In **Lecture 3**, we'll dive into **Reactive Principles** — how to build systems that stay responsive, resilient, elastic, and message-driven under any load.

> **Practical file:** [02_Practical_Hands_On.md](02_Practical_Hands_On.md)

---

## 📚 References

- *Implementing Domain-Driven Design* — Vaughn Vernon
- *CQRS Documents* — Greg Young
- *Event Sourcing* — Martin Fowler
- EventStoreDB documentation
- Axon Framework documentation
- *Building Event-Driven Microservices* — Adam Bellemare
