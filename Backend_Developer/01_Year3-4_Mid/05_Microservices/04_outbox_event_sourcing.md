# Microservices — Outbox Pattern, Event Sourcing & Advanced Patterns
**Advanced | What, Why, How**

---

## Quick Concepts

| Pattern | Problem Solves | Key Idea |
|---|---|---|
| **Outbox Pattern** | Dual-write problem (DB + message broker) | DB transaction mein event save karo, relay publish kare |
| **Idempotency** | Duplicate requests on retry | Idempotency key se same request dobara process na ho |
| **Strangler Fig** | Monolith → Microservices migration | Proxy layer se slowly features extract karo |
| **Saga Orchestration** | Distributed transaction coordination | Central orchestrator steps coordinate kare, compensation run kare |
| **Event Sourcing** | State reconstruction, full audit trail | State nahi store karo — events store karo |
| **CDC** | Outbox polling overhead | DB transaction log (WAL) se events capture karo |

---

## Section A — Outbox Pattern (CRITICAL — frequently asked in interviews)

### The Core Problem: Dual-Write

```
Problem:
  Order create karo DB mein +
  RabbitMQ pe event publish karo

  ❌ What if DB saves BUT RabbitMQ publish fails?
     Order created, inventory never decremented!

  ❌ What if RabbitMQ publishes BUT DB save fails?
     Inventory decremented, order doesn't exist!

  "Dual-write problem" — 2 systems atomically update nahi kar sakte
```

### Solution — Outbox Pattern

```
DB transaction mein:
  1. orders table mein order save karo  ✅
  2. outbox table mein event save karo  ✅

Separate "Message Relay" process:
  1. outbox table poll karo
  2. Unpublished events → RabbitMQ publish karo
  3. Mark as published                  ✅

Now: DB + event are ATOMIC (same transaction)
```

### Complete Implementation

```python
# models.py
class Order(Base):
    __tablename__ = "orders"
    id         = Column(Integer, primary_key=True)
    user_id    = Column(Integer, nullable=False)
    product_id = Column(Integer, nullable=False)
    amount     = Column(Numeric(10, 2))
    status     = Column(String, default="placed")
    created_at = Column(DateTime, default=datetime.utcnow)

class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    id            = Column(Integer, primary_key=True)
    event_type    = Column(String, nullable=False)     # "order.placed"
    aggregate_id  = Column(String, nullable=False)     # "order:123"
    payload       = Column(JSON, nullable=False)
    status        = Column(String, default="pending")  # pending/published/failed
    created_at    = Column(DateTime, default=datetime.utcnow)
    published_at  = Column(DateTime, nullable=True)
    retry_count   = Column(Integer, default=0)

# service.py
async def create_order(session: AsyncSession, order_data: dict) -> Order:
    """Order + outbox event — SAME TRANSACTION"""
    async with session.begin():  # Transaction start
        # 1. Order create karo
        order = Order(**order_data)
        session.add(order)
        await session.flush()  # ID generate karo (commit nahi)

        # 2. Outbox event create karo (SAME transaction)
        event = OutboxEvent(
            event_type   = "order.placed",
            aggregate_id = f"order:{order.id}",
            payload      = {
                "order_id":   order.id,
                "user_id":    order.user_id,
                "product_id": order.product_id,
                "amount":     str(order.amount),
            }
        )
        session.add(event)
        # Commit on exit — dono save honge ya koi nahi

    return order

# Message Relay — background process
class OutboxRelay:
    def __init__(self, session_factory, rabbitmq_url: str):
        self.session_factory = session_factory
        self.rabbitmq_url = rabbitmq_url
        self.connection = None
        self.exchange = None

    async def _ensure_connection(self):
        """Connect once per relay (not per batch) and reuse channel + exchange."""
        if self.connection is None or self.connection.is_closed:
            self.connection = await aio_pika.connect_robust(self.rabbitmq_url)
            channel = await self.connection.channel()
            self.exchange = await channel.declare_exchange(
                "domain_events", aio_pika.ExchangeType.TOPIC
            )

    async def run(self, poll_interval: float = 1.0):
        """Continuously poll outbox and publish events"""
        print("Outbox Relay started")
        await self._ensure_connection()
        while True:
            try:
                await self._process_batch()
            except Exception as e:
                print(f"Relay error: {e}")
            await asyncio.sleep(poll_interval)

    async def _process_batch(self, batch_size: int = 100):
        async with self.session_factory() as session:
            # Pending events fetch karo (with row lock)
            result = await session.execute(
                select(OutboxEvent)
                .where(
                    OutboxEvent.status == "pending",
                    OutboxEvent.retry_count < 5
                )
                .order_by(OutboxEvent.created_at)
                .limit(batch_size)
                .with_for_update(skip_locked=True)  # Multiple relays ke liye
            )
            events = result.scalars().all()

            if not events:
                return

            # Reuse the relay's long-lived connection (NOT a new one per batch).
            # Note: SKIP LOCKED rows commit ke pehle locked rehte hain — yani publish
            # duration ke liye lock held hai (is simple variant ka known tradeoff).
            # Batch chhota rakho taaki lock-hold window short rahe.
            for event in events:
                try:
                    await self.exchange.publish(
                        aio_pika.Message(
                            json.dumps(event.payload).encode(),
                            message_id=str(event.id),
                            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                        ),
                        routing_key=event.event_type
                    )
                    event.status = "published"
                    event.published_at = datetime.utcnow()
                    print(f"Published: {event.event_type} ({event.aggregate_id})")
                except Exception as e:
                    event.retry_count += 1
                    if event.retry_count >= 5:
                        event.status = "failed"
                    print(f"Failed: {event.event_type}: {e}")

            await session.commit()
```

### Outbox Pattern Variants

| Variant | Mechanism | Pros | Cons |
|---|---|---|---|
| **Polling** (shown above) | Background process DB table poll kare | Simple, easy to implement | DB polling overhead, slight latency |
| **CDC — Change Data Capture** | Debezium PostgreSQL WAL (Write-Ahead Log) read kare | Near real-time, no polling overhead | Complex setup, Debezium/Kafka required |

**CDC Flow:**
```
PostgreSQL → WAL (transaction log) → Debezium → Kafka → Consumer
                                                ↑
                                    No polling, event-driven
```

---

## Section B — Idempotency in Microservices

### Problem

```
Network retry → same request 2 baar process → duplicate order!

Client          API Gateway         Order Service
  |----POST /orders--->|                |
  |                    |---create()---->|
  |                    |                | (processing...)
  |<-- timeout --------|                |
  |----POST /orders--->| (retry!)       |
  |                    |---create()---->| (2nd order created!)
```

### Solution — Idempotency Key

```python
class IdempotencyStore:
    def __init__(self, redis_client):
        self.redis = redis_client

    async def check_and_set(
        self,
        idempotency_key: str,
        ttl: int = 86400  # 24 hours
    ) -> tuple[bool, dict | None]:
        """
        Returns (is_first_time, cached_response)
        """
        cache_key = f"idempotency:{idempotency_key}"

        cached = await self.redis.get(cache_key)
        if cached:
            return False, json.loads(cached)

        # Placeholder set karo (lock)
        await self.redis.setex(cache_key, ttl, json.dumps({"status": "processing"}))
        return True, None

    async def store_response(self, idempotency_key: str, response: dict, ttl: int = 86400):
        cache_key = f"idempotency:{idempotency_key}"
        await self.redis.setex(cache_key, ttl, json.dumps(response))

# FastAPI endpoint
@app.post("/orders")
async def create_order(
    order: OrderCreate,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    redis = Depends(get_redis)
):
    store = IdempotencyStore(redis)
    is_first, cached = await store.check_and_set(idempotency_key)

    if not is_first:
        return cached  # Same response return karo

    # First time — actually process
    result = await order_service.create(order)
    response = result.model_dump()

    await store.store_response(idempotency_key, response)
    return response
```

**Idempotency Key kahan se aata hai?**
- Client generate karta hai (UUID4)
- Header mein bhejta hai: `Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000`
- Server same key pe same response return karta hai

**TTL kya rakhein?**
- Payments: 24 hours (Stripe bhi yahi karta hai)
- Orders: 1-7 days depending on business logic
- Idempotency key reuse hone ka risk nahi hona chahiye

---

## Section C — Strangler Fig Pattern

### Martin Fowler ka Pattern — Monolith ko safely replace karo

```
Phase 1: Proxy layer add karo (Nginx/API Gateway)
  All traffic → Proxy → Monolith (unchanged)

Phase 2: Ek feature extract karo (e.g., User Service)
  /api/users/*   → Proxy → New User Service
  /api/orders/*  → Proxy → Monolith (still)

Phase 3: More features extract karo over time
  /api/users/*    → User Service   (new)
  /api/products/* → Product Service (new)
  /api/orders/*   → Monolith        (shrinking)

Phase 4: Monolith "strangled" — fully replaced
  All traffic → New microservices
```

### Real Example — Nginx Config

```nginx
# Phase 3 — partially migrated
upstream user_service    { server user-service:8001; }
upstream product_service { server product-service:8002; }
upstream legacy_monolith { server monolith:8000; }

server {
    listen 80;

    # Extracted services
    location /api/users/ {
        proxy_pass http://user_service;
    }

    location /api/products/ {
        proxy_pass http://product_service;
    }

    # Everything else still goes to monolith
    location / {
        proxy_pass http://legacy_monolith;
    }
}
```

### Rollback Strategy

```
Agar new User Service fail ho → Nginx config update karo:
  /api/users/* → Monolith (rollback in seconds)

Feature flag approach:
  /api/users/* → Canary (10% traffic to new service)
  /api/users/* → Monolith (90% still)
  
  Gradually increase: 10% → 25% → 50% → 100%
```

---

## Section D — Saga Pattern — Orchestration Deep Dive

### Choreography vs Orchestration

```
Choreography (event-driven):
  Service A publish kare → Service B react kare → Service C react kare
  Pros: Loose coupling
  Cons: Hard to trace, distributed logic

Orchestration (central coordinator):
  Saga Orchestrator:
    → Step 1: Reserve inventory
    → Step 2: Process payment
    → Step 3: Confirm order
  Pros: Easy to trace, centralized
  Cons: Orchestrator is bottleneck/single point
```

### Orchestration Implementation

```python
class OrderSagaOrchestrator:
    """
    Place order saga:
    1. Reserve inventory
    2. Process payment
    3. Confirm order

    Compensation (rollback):
    3. Cancel order
    2. Refund payment
    1. Release inventory
    """

    def __init__(self, inventory_client, payment_client, order_repo):
        self.inventory = inventory_client
        self.payment = payment_client
        self.orders = order_repo

    async def execute(self, order_data: dict) -> dict:
        saga_id = str(uuid.uuid4())
        completed_steps = []

        try:
            # Step 1: Reserve inventory
            reservation = await self.inventory.reserve(
                product_id=order_data["product_id"],
                quantity=order_data["quantity"],
                saga_id=saga_id
            )
            completed_steps.append(("inventory_reserved", reservation))

            # Step 2: Process payment
            payment = await self.payment.charge(
                user_id=order_data["user_id"],
                amount=order_data["amount"],
                saga_id=saga_id
            )
            completed_steps.append(("payment_processed", payment))

            # Step 3: Confirm order
            order = await self.orders.confirm(
                order_data=order_data,
                reservation_id=reservation["id"],
                payment_id=payment["id"]
            )

            return {"status": "success", "order_id": order["id"]}

        except Exception as e:
            print(f"Saga {saga_id} failed at step {len(completed_steps)+1}: {e}")
            await self._compensate(completed_steps, saga_id)
            raise

    async def _compensate(self, completed_steps: list, saga_id: str):
        """Undo completed steps in REVERSE order"""
        for step_name, step_data in reversed(completed_steps):
            try:
                if step_name == "payment_processed":
                    await self.payment.refund(step_data["id"], saga_id=saga_id)
                elif step_name == "inventory_reserved":
                    await self.inventory.release(step_data["id"], saga_id=saga_id)
                print(f"Compensated: {step_name}")
            except Exception as e:
                print(f"Compensation failed for {step_name}: {e}")
                # DLQ mein bhejo for manual intervention
```

---

## Section E — Event Sourcing Basics

### What is Event Sourcing?

```
Traditional approach (State-based):
  Order table → current state store karo
  UPDATE orders SET status='shipped' WHERE id=123

  Problem: history lost! Kab create hua? Kab payment hua?

Event Sourcing:
  Events store karo (append-only)
  order_events table:
    {event: "order.created",  data: {...}, timestamp: T1}
    {event: "payment.charged", data: {...}, timestamp: T2}
    {event: "order.shipped",  data: {...}, timestamp: T3}

  Current state = replay all events
```

### Event Store Structure

```python
class OrderEvent(Base):
    __tablename__ = "order_events"
    id           = Column(Integer, primary_key=True)
    aggregate_id = Column(String, nullable=False)   # "order:123"
    event_type   = Column(String, nullable=False)   # "order.placed"
    event_data   = Column(JSON, nullable=False)
    version      = Column(Integer, nullable=False)  # Optimistic locking
    created_at   = Column(DateTime, default=datetime.utcnow)

def rebuild_order_state(events: list[OrderEvent]) -> dict:
    """Events replay karke current state reconstruct karo"""
    state = {}
    for event in sorted(events, key=lambda e: e.version):
        if event.event_type == "order.placed":
            state = {"status": "placed", **event.event_data}
        elif event.event_type == "payment.processed":
            state["status"] = "paid"
            state["payment_id"] = event.event_data["payment_id"]
        elif event.event_type == "order.shipped":
            state["status"] = "shipped"
            state["tracking_id"] = event.event_data["tracking_id"]
    return state
```

### Event Sourcing Benefits

```
1. Full audit trail — koi bhi state change track karo
2. Time travel — past state reconstruct karo (debugging/compliance)
3. Event replay — new read models build karo (CQRS ke saath)
4. Debugging — "5pm pe exactly kya hua?" easily answer karo
```

---

## Interview Questions & Answers

---

**Q1. Outbox pattern kyu use karte hain? Dual-write problem explain karo.**

**Answer:**

Jab hum ek hi operation mein database update karte hain aur message broker (RabbitMQ/Kafka) pe event publish karte hain, toh yeh do alag systems hain — unhe atomically update karna impossible hai without distributed transaction.

**Dual-write problem:**
- DB saves, but RabbitMQ publish fails → inconsistent state
- RabbitMQ publishes, but DB rollback hota hai → ghost event

**Outbox Pattern solution:**
1. DB transaction mein order + outbox event dono save karo (same transaction, atomic)
2. Separate relay process outbox table poll karta hai
3. Relay events publish karta hai aur mark karta hai as published

Is tarah DB aur event always consistent rahte hain — agar DB rollback hua toh event bhi nahi banega.

---

**Q2. Outbox polling vs CDC (Change Data Capture) — kya fark hai?**

**Answer:**

| | Polling | CDC (Debezium) |
|---|---|---|
| **Mechanism** | Background process DB table ko periodically query kare | Database WAL (Write-Ahead Log) read kare |
| **Latency** | Poll interval pe depend (1-5 sec) | Near real-time (milliseconds) |
| **DB Load** | Polling queries DB pe load daalta hai | WAL reading — minimal overhead |
| **Setup** | Simple — bas ek background process | Complex — Debezium + Kafka/Kinesis |
| **Use case** | Small-medium scale, simplicity priority | High throughput, low latency needed |

**CDC kab choose karo:** High-volume systems jahan millisecond latency matter kare (payments, inventory).
**Polling kab choose karo:** Simpler systems, external dependency avoid karna ho.

---

**Q3. Idempotency key ka TTL kitna rakhein aur kyu?**

**Answer:**

TTL business context pe depend karta hai:

- **Payments (Stripe model):** 24 hours — agar client 24 ghante baad retry kare, toh likely intentional new request hai
- **Order creation:** 1-7 days — duplicate order protection ke liye
- **Generic APIs:** 1 hour — short-lived operations ke liye

**Key considerations:**
1. TTL too short → legitimate retry miss ho sakta hai
2. TTL too long → memory waste, stale data
3. Client ko UUID v4 generate karni chahiye — collision probability negligible
4. Redis preferred (fast, TTL native support, distributed)

**Stripe actually 24 hours use karta hai** — yeh industry standard mana jaata hai financial operations ke liye.

---

**Q4. Strangler Fig pattern mein rollback kaise karein agar new service fail ho?**

**Answer:**

Strangler Fig ka beauty yahi hai ki rollback trivially easy hai:

**Option 1 — Nginx config change:**
```nginx
# New service fail hua — ek line change karo
location /api/users/ {
    proxy_pass http://legacy_monolith;  # was user_service
}
# Reload nginx — zero downtime
nginx -s reload
```

**Option 2 — Feature flags (recommended):**
```
Canary deployment:
  10%  traffic → new service
  90%  traffic → monolith

Agar errors aayein:
  0%   traffic → new service
  100% traffic → monolith  (instant rollback)
```

**Option 3 — API Gateway level:**
AWS API Gateway / Kong pe routing rules update karo — code change nahi, just config.

**Best practice:** Pehle 5-10% traffic new service pe route karo, monitor karo, phir gradually increase karo. Kisi bhi error threshold pe automatically rollback ho jaye.

---

**Q5. Saga orchestration vs choreography — kab kya choose karo?**

**Answer:**

**Choreography (Event-driven):**
- Services events publish/subscribe karte hain
- Koi central coordinator nahi
- **Choose when:** Loose coupling priority ho, services independent teams manage karein, simple 2-3 step flows hon

**Orchestration (Central coordinator):**
- Ek Saga Orchestrator sab steps control karta hai
- Compensation bhi orchestrator handle karta hai
- **Choose when:** Complex multi-step flows (5+ steps), clear visibility/tracing chahiye, compensation logic complex ho

**Rule of thumb:**
```
Simple saga (2-3 steps, same team)     → Choreography
Complex saga (5+ steps, multiple teams) → Orchestration
Financial transactions                  → Orchestration (traceability critical)
```

**Real world:** Order processing → Orchestration (inventory + payment + shipping + notification = complex). Notification fan-out → Choreography (email, SMS, push — all react to same event).

---

**Q6. `with_for_update(skip_locked=True)` kyu use karte hain Outbox mein?**

**Answer:**

Jab multiple relay instances chal rahe hon (horizontal scaling / HA setup), toh same outbox events multiple relays uthha sakte hain — **duplicate publishing** ka risk!

```sql
-- Without skip_locked:
Relay-1: SELECT * FROM outbox WHERE status='pending' FOR UPDATE
Relay-2: SELECT * FROM outbox WHERE status='pending' FOR UPDATE
-- Relay-2 WAIT karega jab tak Relay-1 lock release kare
-- Bottleneck + deadlock risk

-- With skip_locked:
Relay-1: SELECT * FROM outbox WHERE status='pending' FOR UPDATE SKIP LOCKED
-- Locks rows 1-100

Relay-2: SELECT * FROM outbox WHERE status='pending' FOR UPDATE SKIP LOCKED
-- Automatically rows 101-200 uthha leta hai (1-100 skip)
-- No waiting, no blocking!
```

**`skip_locked` benefits:**
1. Multiple relays parallel chal sakte hain
2. No blocking/waiting
3. Natural load distribution
4. Deadlock-free

**PostgreSQL specific feature** — SQLite mein simulate karna padta hai.

---

**Q7. Event Sourcing kab use karo aur kab avoid karo?**

**Answer:**

**Use Event Sourcing when:**
- Full audit trail required ho (banking, healthcare, compliance)
- Time-travel debugging chahiye ("3pm pe exact system state kya tha?")
- CQRS ke saath multiple read models build karne hon
- Business events first-class citizens hon (domain-driven design)

**Avoid Event Sourcing when:**
- Simple CRUD application ho (overkill)
- Team Event Sourcing se unfamiliar ho
- Simple reporting needs hon
- Latency-sensitive read operations ho (event replay costly)

**Complexity trade-off:**
```
Traditional DB:  Simple queries, easy aggregations
Event Sourcing:  Complex setup, but powerful audit/replay

"Agar audit log chahiye toh Event Sourcing consider karo.
 Agar sirf current state chahiye toh traditional approach better hai."
```

---

## Summary Table

| Pattern | Core Idea | Key Benefit | Watch Out |
|---|---|---|---|
| **Outbox Pattern** | DB + event same transaction | No dual-write inconsistency | Polling overhead / CDC complexity |
| **Idempotency Key** | UUID based deduplication | Safe retries, no duplicates | TTL tuning, Redis dependency |
| **Strangler Fig** | Proxy-based gradual migration | Zero-downtime monolith replacement | Data sync between old/new service |
| **Saga Orchestration** | Central coordinator manages steps | Clear flow, easy compensation | Orchestrator is single point |
| **Saga Choreography** | Events-driven reactive steps | Loose coupling, scalable | Hard to trace, distributed logic |
| **Event Sourcing** | Store events not state | Full audit, time travel | Complexity, query difficulty |
| **CDC** | DB WAL-based event capture | Real-time, low overhead | Debezium/Kafka setup needed |

---

*Interview tip: Outbox pattern ka flow diagram explain karo — DB transaction → outbox table → relay → broker. Yeh visually describe karna interviewers ko bahut impress karta hai.*
