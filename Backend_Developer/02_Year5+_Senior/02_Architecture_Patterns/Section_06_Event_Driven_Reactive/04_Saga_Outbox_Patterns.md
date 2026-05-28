# Lecture 4: Distributed Consistency — Saga & Outbox Patterns

> *"In distributed systems, ACID dies. Long live eventual consistency with discipline."*

**Section 6 — Event-Driven & Reactive Systems**

---

## 🎯 Is Lecture Mein Kya Seekhenge?

- **The distributed consistency problem**
- **Why ACID doesn't scale across services**
- **Saga pattern** — coordinated local transactions
- **Saga execution styles** — choreography vs orchestration
- **Real-world saga example** — e-commerce
- **Saga challenges**
- **Reliable messaging** — the foundation
- **Outbox pattern** — atomic writes + reliable events
- **Outbox in action**
- **Outbox challenges**
- **Combining Saga + Outbox**

---

## 1. The Distributed Consistency Problem

### Traditional World (Monolith)

```
   ┌──────────────────────────────┐
   │      ACID Transaction         │
   │                                │
   │  BEGIN                         │
   │    UPDATE accounts SET ...     │
   │    UPDATE inventory SET ...    │
   │    INSERT orders ...           │
   │  COMMIT                        │
   │                                │
   │  Either ALL or NONE             │
   └──────────────────────────────┘
   
   ✓ Atomicity
   ✓ Consistency
   ✓ Isolation
   ✓ Durability
```

### Distributed Reality

```
   ┌──────────┐  ┌──────────┐  ┌──────────┐
   │ Order    │  │ Payment  │  │ Inventory│
   │ Service  │  │ Service  │  │ Service  │
   │ + DB     │  │ + DB     │  │ + DB     │
   └─────┬────┘  └─────┬────┘  └─────┬────┘
         │              │              │
         └──────────────┴──────────────┘
                Network in between
   
   ✗ No global transaction
   ✗ Each service has own DB
   ✗ Network failures inevitable
   ✗ Partial failures common
```

### Why ACID Doesn't Scale

```
Distributed transactions (2PC):
   ✗ Locks resources across services
   ✗ Synchronous coordination
   ✗ Slow (waits for everyone)
   ✗ Doesn't handle partition well
   ✗ Single point of failure (coordinator)
   ✗ Hard to implement well

→ Most modern systems AVOID 2PC.
```

### CAP Theorem

```
In presence of network PARTITION:
   You must choose between CONSISTENCY and AVAILABILITY.

Most modern systems choose:
   ✓ Availability (always respond)
   ✗ Strong Consistency
   = Eventual Consistency

→ Designs accept "eventually consistent" reality.
```

### The Question

```
If we can't have ACID across services...

How do we maintain consistency?

Answer: SAGA + OUTBOX patterns
```

---

## 2. What Is the Saga Pattern?

### Core Idea

**Break a long-running transaction into a sequence of local transactions, each with a compensating action.**

### Visual

```
TRADITIONAL TRANSACTION:
   [          one big transaction           ]
   BEGIN → step1 → step2 → step3 → COMMIT
   
   If any step fails: rollback all

SAGA:
   [step 1 local TX] → emit event
                          ↓
   [step 2 local TX] → emit event
                          ↓
   [step 3 local TX] → emit event
   
   Each step:
   ✓ Atomic locally
   ✗ Not atomic globally
   
   If step 2 fails:
   ✓ Emit compensating event for step 1
   ✓ Step 1 undoes itself
```

### Properties

```
✓ Each step = LOCAL transaction (ACID guarantees apply locally)
✓ Steps connected by EVENTS
✓ Compensating actions UNDO previous steps if needed
✓ NO global lock
✓ NO global transaction coordinator
✓ EVENTUAL consistency
✗ NO isolation (other services see intermediate states)
```

### Example: E-commerce Order

```
1. Create order (Order Service)
   → emit OrderCreated event
   
2. Reserve inventory (Inventory Service)
   → emit InventoryReserved event
   
3. Charge payment (Payment Service)
   → emit PaymentCharged event
   
4. Confirm order (Order Service)
   → emit OrderConfirmed event

If step 3 fails (payment declined):
   → Compensating:
     - Release inventory (undo step 2)
     - Cancel order (undo step 1)
```

---

## 3. Saga Execution Styles

### Style 1: Choreography

```
   No central coordinator!
   Each service reacts to events autonomously.

   Order Service           Inventory Service       Payment Service
        │                          │                       │
        │ emit OrderCreated         │                       │
        ├──────────────────────────►│                       │
        │                          │                       │
        │                          │ Reserve stock          │
        │                          │ emit InventoryReserved │
        │                          ├──────────────────────►│
        │                          │                       │
        │                          │                       │ Charge
        │                          │                       │ emit PaymentCharged
        │                          ├──────────────────────►│
        │                          │                       │
        │                          │                       │ ...
```

```
✓ Highly decoupled
✓ No central bottleneck
✓ Easy to add new participants
✗ Hard to understand overall flow
✗ Hard to debug
✗ Cyclic dependencies possible
```

### Style 2: Orchestration

```
   Central orchestrator drives the flow.

           ┌──────────────────────────┐
           │      ORCHESTRATOR        │
           │                          │
           │  1. Start saga           │
           │  2. Call services        │
           │  3. Handle responses     │
           │  4. Decide next step     │
           │  5. Compensate on fail   │
           └────┬──────────┬─────────┘
                │           │
       ┌────────┴────────┐  │
       ▼                 │  │
   Order Service ────────┘  │
                            │
       ┌────────────────────┘
       ▼
   Inventory Service
       │
       └────────────────────┐
                            ▼
                        Payment Service
```

```
✓ Clear visibility of flow
✓ Easy to debug + monitor
✓ Centralized error handling
✓ Easy to add new steps
✗ Tighter coupling
✗ Orchestrator becomes critical
✗ Can be bottleneck
```

### When to Use Which

```
CHOREOGRAPHY:
   ✓ Simple workflows
   ✓ Few participants
   ✓ Decoupling priority
   ✓ Each service truly autonomous

ORCHESTRATION:
   ✓ Complex workflows
   ✓ Many steps
   ✓ Visibility matters
   ✓ Strong governance needed

HYBRID (most common):
   ✓ Mix based on use case
   ✓ Some flows orchestrated, others choreographed
```

---

## 4. Saga in Action: E-commerce Order

### Happy Path

```
   User places order
        │
        ▼
   Order Service: Save order, emit OrderCreated
        │
        ▼
   Inventory Service receives OrderCreated:
        ✓ Check stock
        ✓ Reserve items
        emit ItemsReserved
        │
        ▼
   Payment Service receives ItemsReserved:
        ✓ Charge customer's card
        emit PaymentCharged
        │
        ▼
   Shipping Service receives PaymentCharged:
        ✓ Schedule pickup
        emit ShippingScheduled
        │
        ▼
   Order Service receives ShippingScheduled:
        ✓ Mark order CONFIRMED
        emit OrderConfirmed
```

### Compensation Path (Payment Fails)

```
   ... up to ItemsReserved ...
        │
        ▼
   Payment Service receives ItemsReserved:
        ✗ Payment DECLINED
        emit PaymentFailed
        │
        ▼
   Inventory Service receives PaymentFailed:
        ✓ Release reserved items
        emit ItemsReleased
        │
        ▼
   Order Service receives ItemsReleased:
        ✓ Mark order CANCELLED
        emit OrderCancelled
        
   System is back to consistent state!
   (Though intermediate state existed temporarily)
```

### Code Sketch

```python
"""Choreography-style saga"""

# Order Service
async def create_order(req):
    order = await save_order(req)
    await event_bus.publish("OrderCreated", order)

async def on_payment_failed(event):
    await update_order_status(event["order_id"], "CANCELLED")
    await event_bus.publish("OrderCancelled", event)

# Inventory Service
async def on_order_created(event):
    success = await reserve_items(event["items"])
    if success:
        await event_bus.publish("ItemsReserved", event)
    else:
        await event_bus.publish("InsufficientStock", event)

async def on_payment_failed(event):
    # Compensating action
    await release_items(event["order_id"])
    await event_bus.publish("ItemsReleased", event)

# Payment Service
async def on_items_reserved(event):
    success = await charge_card(event)
    if success:
        await event_bus.publish("PaymentCharged", event)
    else:
        await event_bus.publish("PaymentFailed", event)
```

---

## 5. Saga Challenges

### Challenge 1: Designing Compensations

```
NOT all actions are easily reversible:

EASY to compensate:
   ✓ Reserve item → Release item
   ✓ Add points → Subtract points
   ✓ Insert row → Delete row

HARD to compensate:
   ✗ Send email (can't unsend!)
   ✗ Make external API call with side effects
   ✗ Charge customer (need refund flow)
   ✗ Trigger physical action (shipment)

Solutions:
   ✓ Design compensations carefully
   ✓ Use semantic compensations (send apology email, not "unsend")
   ✓ Delay irreversible actions until late
   ✓ Use "pivot" steps (point of no return)
```

### Challenge 2: No Isolation

```
Sagas don't provide isolation:
   ✗ Other services see INTERMEDIATE states
   
Example:
   Step 1: Reserve $100 from account
   Step 2: Pay merchant
   
   In between, user might see:
   ✗ "Available balance: -$100"
   
Solutions:
   ✓ Hide intermediate states from users
   ✓ Show "Pending" status
   ✓ Use commutative operations where possible
   ✓ Semantic locks (mark "in saga" without locking)
```

### Challenge 3: Idempotency & Out-of-Order

```
Events may:
   ✗ Arrive out of order
   ✗ Be delivered more than once

If consumer is not idempotent:
   ✗ Same action applied twice
   ✗ Wrong state
   
Solutions:
   ✓ Use idempotency keys
   ✓ Track processed event IDs
   ✓ Make actions naturally idempotent
   ✓ Order matters? Use saga ID + step number
```

### Challenge 4: Knowing Saga Status

```
Saga in progress... what's the status?

In orchestration:
   ✓ Easy - orchestrator tracks state

In choreography:
   ✗ No single source of truth
   ✗ State scattered across services
   
Solutions:
   ✓ Saga state store
   ✓ Distributed tracing
   ✓ Workflow visualization
   ✓ Timeout-based detection
```

### Challenge 5: Cascading Compensations

```
Step 5 fails:
   → Compensate step 4
   → Compensate step 3
   → Compensate step 2
   → Compensate step 1

What if a compensation FAILS?
   ✗ Partial compensation
   ✗ Inconsistent state

Solutions:
   ✓ Compensations must be idempotent too
   ✓ Retry compensations
   ✓ Manual intervention queue (DLQ)
   ✓ Plan for impossible cases (apology emails, etc.)
```

---

## 6. Reliable Messaging — The Foundation

### Why It Matters

```
Sagas rely on EVENTS to coordinate.
If events get lost → saga breaks!

Without reliable messaging:
   ✗ Step completed but event lost
   ✗ Next step never triggered
   ✗ System stuck inconsistent
```

### Common Issues

```
1. MESSAGE LOSS
   Producer crashed before publishing
   Network drops message
   Broker fails before persisting

2. DUPLICATES
   Retries deliver same message twice
   Consumer processes, fails ack, re-delivered

3. OUT-OF-ORDER
   Different partition / queue
   Network jitter
```

### Requirements

```
For sagas to work, you need:

1. AT-LEAST-ONCE DELIVERY
   ✓ Messages eventually reach destination
   ✗ But may be delivered more than once

2. IDEMPOTENT CONSUMERS
   ✓ Safe to process same message multiple times
   ✓ Same result either way

3. ATOMIC PUBLISH WITH STATE CHANGE
   ✓ Either both happen, or neither
   ✓ Where outbox pattern comes in!
```

---

## 7. The Outbox Pattern

### The Problem It Solves

```
You want to:
   1. Update database (business state)
   2. Publish event (notify others)

Approach A: DB first, then publish
   1. Save order to DB ✓
   2. Publish OrderCreated ✗ (crash here)
   → Order saved but no event → inconsistent!

Approach B: Publish first, then DB
   1. Publish OrderCreated ✓
   2. Save order to DB ✗ (crash here)
   → Event sent but no order → ghost event!

Approach C: Use distributed transaction (2PC)
   → Slow, complex, doesn't scale
```

### Outbox Solution

```
ATOMIC: business write + event in SAME local transaction
   
   BEGIN TRANSACTION
     UPDATE orders SET ...     -- business state
     INSERT INTO outbox ...     -- event for publishing
   COMMIT
   
Both happen or neither.

Then SEPARATE PROCESS reads outbox + publishes:
   → If publishing fails, event still in outbox
   → Retry until successful
   → Then mark as published / delete
```

### Visual

```
   ┌─────────────┐
   │ Application  │
   └──────┬───────┘
          │
          │ Business request
          ▼
   ┌──────────────────────────┐
   │   DATABASE                │
   │                            │
   │  ┌──────────┐ ┌─────────┐ │
   │  │ orders   │ │ outbox   │ │  ← Both written
   │  │  table   │ │  table   │ │     atomically
   │  └──────────┘ └─────────┘ │
   └──────────────────┬─────────┘
                      │
                      │
                      │ Poll outbox
                      ▼
              ┌──────────────────┐
              │ Outbox Publisher │
              │ (separate process)│
              └──────┬───────────┘
                     │
                     │ Publish events
                     ▼
              ┌──────────────┐
              │ Event Broker │
              │ (Kafka, etc.)│
              └──────────────┘
```

---

## 8. Outbox Pattern Details

### Schema

```sql
CREATE TABLE outbox (
    id BIGSERIAL PRIMARY KEY,
    aggregate_type VARCHAR NOT NULL,   -- e.g., "order"
    aggregate_id VARCHAR NOT NULL,     -- e.g., "ORD-123"
    event_type VARCHAR NOT NULL,       -- e.g., "OrderCreated"
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    published_at TIMESTAMPTZ,          -- NULL = not yet published
    
    INDEX idx_unpublished (published_at)
        WHERE published_at IS NULL
);
```

### Writer Side

```python
"""Atomic DB write + outbox entry"""

async def create_order(session, user_id, items):
    async with session.begin():
        # 1. Save business state
        order = Order(user_id=user_id, items=items, status="CREATED")
        session.add(order)
        await session.flush()  # Get ID
        
        # 2. Add to outbox IN SAME TRANSACTION
        event = OutboxEvent(
            aggregate_type="order",
            aggregate_id=order.id,
            event_type="OrderCreated",
            payload={
                "order_id": order.id,
                "user_id": user_id,
                "items": items,
            }
        )
        session.add(event)
        
        # Commit BOTH atomically
        # If either fails, BOTH roll back
    
    return order
```

### Publisher Side

```python
"""Background publisher process"""

class OutboxPublisher:
    async def run(self):
        while True:
            try:
                count = await self._publish_batch()
                if count == 0:
                    await asyncio.sleep(1)
            except Exception as e:
                print(f"Publisher error: {e}")
                await asyncio.sleep(5)
    
    async def _publish_batch(self, batch_size=100):
        async with session_factory() as session:
            # Lock + fetch unpublished
            events = await session.execute(
                select(OutboxEvent)
                .where(OutboxEvent.published_at.is_(None))
                .order_by(OutboxEvent.id)
                .limit(batch_size)
                .with_for_update(skip_locked=True)  # Concurrent publishers OK
            )
            events = events.scalars().all()
            
            if not events:
                return 0
            
            # Publish each
            for event in events:
                try:
                    await kafka_producer.send(
                        event.event_type,
                        value=event.payload,
                        key=event.aggregate_id,
                    )
                    event.published_at = datetime.utcnow()
                except Exception as e:
                    # Don't update published_at - will retry
                    print(f"Publish failed: {e}")
            
            await session.commit()
            return len(events)
```

---

## 9. Outbox Challenges

### Challenge 1: Duplicates Possible

```
Scenario:
   1. Publisher sends event
   2. Kafka acks
   3. Publisher crashes BEFORE marking sent
   4. Restart → publishes again

→ Consumers may receive DUPLICATE events

Solution:
   ✓ Consumers MUST be idempotent
   ✓ Use event_id for deduplication
   ✓ At-least-once is the trade-off
```

### Challenge 2: Polling Latency

```
Polling outbox introduces delay:
   t=0:    Order saved + event in outbox
   t=100ms: Publisher polls, finds it
   t=110ms: Published to Kafka

For most apps: 100ms is fine
For real-time: maybe too slow

Solutions:
   ✓ Faster polling (every 100ms)
   ✓ Notify-based (PostgreSQL LISTEN/NOTIFY)
   ✓ Debezium CDC (read directly from WAL)
```

### Challenge 3: Database Load

```
Polling adds query load:
   ✗ Constant SELECT from outbox
   ✗ Index updates on insert
   ✗ Cleanup of old rows

Solutions:
   ✓ Cleanup old published rows (>1 hour)
   ✓ Partition by date
   ✓ Use efficient indexes
   ✓ CDC instead of polling for high volume
```

### Challenge 4: Ordering

```
If multiple publishers run:
   ✗ Order across instances not guaranteed
   ✗ Different events may publish out of order

Solutions:
   ✓ SKIP LOCKED with sequence ID
   ✓ Single publisher per partition
   ✓ Partition by aggregate_id (same aggregate's events in order)
```

### Challenge 5: Schema Coupling

```
Outbox rows tie tightly to business model:
   ✗ Schema changes break publishers
   
Solutions:
   ✓ Treat outbox as integration contract
   ✓ Version events
   ✓ Test publisher independently
```

---

## 10. Saga + Outbox Combined

### Why Together?

```
Saga handles MULTI-STEP coordination.
Outbox ensures EVENT DELIVERY.

→ Each saga step:
   ✓ Local transaction includes outbox entry
   ✓ Event guaranteed to be published
   ✓ Next step in saga is reliably triggered

Without outbox:
   ✗ Step could complete but event lost
   ✗ Saga gets stuck
```

### Full Architecture

```
   ┌──────────────────────────────────────────────────────────┐
   │                                                            │
   │   Service A           Service B           Service C       │
   │   ┌────────┐         ┌────────┐         ┌────────┐        │
   │   │ Local  │         │ Local  │         │ Local  │        │
   │   │  DB    │         │  DB    │         │  DB    │        │
   │   │+outbox │         │+outbox │         │+outbox │        │
   │   └───┬────┘         └───┬────┘         └───┬────┘        │
   │       │                   │                   │            │
   │   Publisher           Publisher           Publisher       │
   │       │                   │                   │            │
   │       ▼                   ▼                   ▼            │
   │   ┌────────────────────────────────────────────────────┐  │
   │   │              Kafka / Event Broker                   │  │
   │   └────────────────────────────────────────────────────┘  │
   │       │                   │                   │            │
   │       ▼                   ▼                   ▼            │
   │   Consumer            Consumer            Consumer        │
   │   (idempotent)        (idempotent)        (idempotent)    │
   │                                                            │
   └──────────────────────────────────────────────────────────┘
   
   Each step:
      1. Receive event
      2. Local transaction:
         - Update business state
         - Add NEXT event to outbox
      3. Publisher emits next event
      4. Next service reacts
```

### Example: Order Saga with Outbox

```python
"""Inventory service handling OrderCreated event"""

@event_handler("OrderCreated")
async def on_order_created(event):
    order_id = event["order_id"]
    
    # Idempotency check
    if await db.is_event_processed(event["event_id"]):
        return
    
    async with session.begin():
        # Try to reserve stock
        success = await reserve_inventory(order_id, event["items"])
        
        # Add NEXT event to outbox (in same transaction)
        if success:
            session.add(OutboxEvent(
                event_type="ItemsReserved",
                aggregate_id=order_id,
                payload={"order_id": order_id, "items": event["items"]},
            ))
        else:
            session.add(OutboxEvent(
                event_type="InsufficientStock",
                aggregate_id=order_id,
                payload={"order_id": order_id, "reason": "Out of stock"},
            ))
        
        # Mark event as processed (idempotency)
        await db.mark_event_processed(event["event_id"])
        
        # COMMIT: state change + outbox event are atomic
```

---

## 11. Real-World Use Cases

### Use Case 1: E-commerce Order Flow

```
Place order → Reserve inventory → Charge payment → 
Schedule shipping → Send confirmation → Award points

8+ services involved, all coordinated by events.
Saga + Outbox = reliable end-to-end flow.
```

### Use Case 2: Travel Booking

```
Book hotel → Book flight → Reserve car → Charge credit card

If any fails:
   → Cancel previous bookings (compensations)
   → Refund any charges
   → Send apology to customer
```

### Use Case 3: Financial Trading

```
Buy order → Reserve funds → Match with seller → 
Transfer ownership → Settle payment

Strict audit + compensations required.
```

### Use Case 4: Healthcare Workflows

```
Patient registration → Insurance verification → 
Schedule appointment → Send reminders

Each step a separate service.
Saga ensures consistency.
```

---

## 12. Alternative Approaches

### Alternative 1: Two-Phase Commit (2PC)

```
Distributed transaction coordinator:
   Phase 1: Prepare (all participants vote)
   Phase 2: Commit/Rollback (based on votes)

Problems:
   ✗ Synchronous blocking
   ✗ Coordinator = SPOF
   ✗ Doesn't handle partition well
   ✗ Slow
   
→ Rarely used in modern microservices.
```

### Alternative 2: Distributed Locks

```
Lock all resources before changing:
   ✗ Long-held locks
   ✗ Deadlocks possible
   ✗ Doesn't scale
```

### Alternative 3: Eventual Consistency Without Saga

```
"Hope it works out" approach:
   ✗ No compensations
   ✗ No coordination
   ✗ Data drifts inconsistent
   
→ Only OK for non-critical data.
```

### Why Saga + Outbox Wins

```
✓ Handles failures gracefully
✓ Reliable event delivery
✓ Scales horizontally
✓ Each service autonomous
✓ Battle-tested in production
✓ Industry standard for microservices
```

---

## 13. When to Use Saga + Outbox

### Use When:

```
✓ Multi-step business workflows
✓ Crossing service boundaries
✓ ACID across services needed
✓ Events drive your architecture
✓ High reliability requirements
✓ Compensations feasible
```

### Don't Use When:

```
✗ Single-service workflows (use local TX!)
✗ Workflows that complete in <100ms
✗ Read-only operations
✗ Cannot define compensations
✗ Tolerable to have some inconsistency
```

### Maturity Required

```
Saga + Outbox needs:
   ✓ Event-driven architecture
   ✓ Idempotent operations
   ✓ Comprehensive monitoring
   ✓ Distributed tracing
   ✓ Strong team discipline

→ Not for beginners.
→ Right tool when you need it.
```

---

## 14. Common Patterns

### Pattern 1: Saga State Machine

```
Track saga state explicitly:
   - Started
   - Step 1 Complete
   - Step 2 Complete
   - ...
   - Completed
   - Compensating
   - Failed
   
Stored in DB, drives saga execution.
```

### Pattern 2: Process Manager

```
Orchestrator-style saga implementation:
   ✓ Tracks saga state
   ✓ Subscribes to events
   ✓ Emits commands
   ✓ Handles compensations
```

### Pattern 3: Choreography with Saga Log

```
Even in choreography, maintain saga log:
   ✓ Visibility
   ✓ Debugging
   ✓ Manual intervention if stuck
```

### Pattern 4: Timeout-Based Recovery

```
Step takes too long?
   ✓ Timeout triggers compensation
   ✓ Prevents indefinite hangs
```

### Pattern 5: CDC + Outbox

```
Skip polling - use Change Data Capture:
   ✓ Debezium reads PostgreSQL WAL
   ✓ Streams changes to Kafka
   ✓ Near-zero latency
   ✓ No polling overhead
```

---

## 15. Summary — Key Takeaways

```
┌──────────────────────────────────────────────────────────────┐
│  ✅ Distributed ACID doesn't scale - use Sagas                 │
│  ✅ Saga = sequence of local TX + compensations                 │
│  ✅ Two styles: Choreography vs Orchestration                  │
│  ✅ Compensations undo previous steps on failure                │
│  ✅ Sagas don't provide isolation (intermediate states visible) │
│  ✅ Reliable messaging is essential                            │
│  ✅ Outbox = atomic DB write + event guarantee                  │
│  ✅ Polling-based publisher emits events                        │
│  ✅ Consumers must be IDEMPOTENT                                │
│  ✅ Saga + Outbox = production-grade distributed consistency    │
└──────────────────────────────────────────────────────────────┘
```

### The Universal Rules

```
1. Forget global ACID across services
2. Use Saga for multi-step workflows
3. Design compensations from the start
4. Use Outbox for reliable event delivery
5. Make ALL consumers idempotent
6. Track saga state for visibility
7. Handle compensation failures gracefully
8. Embrace eventual consistency
9. Test failure scenarios extensively
10. Combine sync APIs + async sagas pragmatically
```

---

## 🎬 Section Complete!

You've completed **Section 6: Event-Driven & Reactive Systems**!

### What You've Learned

```
✓ Event-Driven Architecture basics
✓ Event Sourcing + CQRS
✓ Reactive Manifesto and principles
✓ Saga + Outbox patterns
```

### Practical file: [04_Practical_Hands_On.md](04_Practical_Hands_On.md)

---

## 🚀 What's Next?

Continue with:
- **Section 7**: Cloud-Native & Scalable Architecture
- **Section 8**: UI Architecture Patterns
- **Section 9**: Architectural Decision-Making
- **Section 10**: Conclusion & Next Steps

---

## 📚 References

- *Microservices Patterns* — Chris Richardson (saga chapter!)
- *Designing Data-Intensive Applications* — Martin Kleppmann
- *Building Microservices* — Sam Newman
- Pattern: Saga — microservices.io
- Pattern: Outbox — debezium.io
- Eventuate framework documentation
- Axon Framework saga implementation
