# Distributed Data Management — DB per Service, CDC, Eventual Consistency

## Quick Concepts

**WHAT:**
- **Database per service** = Each microservice owns its data
- **Shared database** = Multiple services share same DB (anti-pattern)
- **2PC (Two-Phase Commit)** = Distributed transaction (XA) — avoid
- **Eventual consistency** = Data syncs across services over time
- **CDC (Change Data Capture)** = Stream DB changes to other systems
- **Polyglot persistence** = Right DB type per service
- **Data ownership** = Single service owns each piece of data

**WHY distributed data is hard:**
- Monolith: ACID transactions across all tables
- Microservices: ACID only within ONE service's DB
- Cross-service consistency = harder
- CAP theorem trade-offs become real

**HOW data ownership rules:**

```
┌─────────────────────────────────────────────────────┐
│                Monolith Pattern                      │
│  ┌──────────────────────────────────────────────┐  │
│  │  Single Database                              │  │
│  │  users, orders, products, payments, ...      │  │
│  └──────────────────────────────────────────────┘  │
│  All services query directly                        │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│           Microservices Pattern                      │
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐         │
│  │ User Svc │  │ Order Svc│  │ Pay Svc  │         │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘         │
│       │             │             │                │
│  ┌────▼─────┐  ┌────▼─────┐  ┌────▼─────┐         │
│  │ Users DB │  │ Orders DB│  │ Pay DB   │         │
│  └──────────┘  └──────────┘  └──────────┘         │
│                                                      │
│  ⭐ Each service owns its data exclusively         │
│  ⭐ Other services request via API (not direct SQL) │
└─────────────────────────────────────────────────────┘
```

---

## Interview Questions & Answers

### Q1: Database per service — kyu jaruri hai?

**Answer:**

**WHY each service should own its data:**

**1. Loose coupling**
```
Shared DB scenario:
- User service changes "users" table schema
- Order service breaks (queries same table)
- Coordination across teams needed

Per-service DB:
- User service evolves independently
- Order service unaffected
- Teams move independently
```

**2. Right DB per service**
```
Different services have different needs:
- User service: PostgreSQL (relational)
- Catalog: Elasticsearch (full-text search)
- Session: Redis (key-value)
- Analytics: ClickHouse (columnar)
- Audit: S3 + Athena (object storage)
```

**3. Failure isolation**
```
Shared DB:
- DB down → ALL services down

Per-service DB:
- User DB down → only user service affected
- Order service continues with degraded mode
```

**4. Scaling independently**
```
Shared DB scaling = scale everything together (wasteful)

Per-service:
- User DB: small (low read/write)
- Order DB: large (high write volume)
- Scale each based on actual load
```

**HOW — Anti-pattern: Shared database**

```python
# ❌ DO NOT DO THIS
# user-service code:
def get_user_with_orders(user_id):
    cursor.execute("""
        SELECT u.*, o.*
        FROM users u
        JOIN orders o ON u.id = o.user_id   ← ❌ Cross-service join
        WHERE u.id = %s
    """, (user_id,))

# Problems:
# 1. user-service knows order schema
# 2. Order schema change breaks user-service
# 3. No clear ownership
```

**HOW — Correct pattern: API call**

```python
# ✅ user-service code:
async def get_user_with_orders(user_id):
    user = await db.users.get(user_id)              # Own DB

    # Call order-service for orders
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"http://order-service/api/orders?user_id={user_id}"
        )
        orders = response.json()

    return {"user": user, "orders": orders}
```

---

### Q2: 2PC (Two-Phase Commit) — kyu avoid karein?

**Answer:**

**WHAT:** Distributed transaction protocol — coordinator + participants.

**HOW it works:**

```
Phase 1: Prepare
Coordinator → Service A: "Can you commit?" → A locks resources, says "Yes"
Coordinator → Service B: "Can you commit?" → B locks resources, says "Yes"

Phase 2: Commit
If all "Yes" → Coordinator says "COMMIT" → both commit
If any "No"  → Coordinator says "ROLLBACK" → both rollback
```

**WHY avoid in microservices:**

```
Problem 1: Blocking
- Resources LOCKED during entire 2PC
- One slow service = all services slow
- Concurrent transactions block each other

Problem 2: Coordinator failure
- If coordinator crashes after Phase 1
- Participants don't know if commit or rollback
- "In doubt" transactions hang forever

Problem 3: Network partition
- Split brain — half think commit, half rollback
- Inconsistent state

Problem 4: Performance
- 2 round trips minimum
- Lock contention at scale

Problem 5: Tight coupling
- All services need XA transaction support
- Coordinator becomes SPOF
```

**HOW — Alternatives to 2PC:**

| Pattern | Use Case | Trade-off |
|---|---|---|
| **Saga** | Long workflows | Eventual consistency |
| **Outbox** | Reliable event publishing | Latency for outbox table |
| **Event Sourcing** | Audit + replay needed | Complexity |
| **CDC** | Sync without app changes | Database-level coupling |

---

### Q3: Eventual consistency — patterns + handling?

**Answer:**

**WHAT:** Data converges to consistent state OVER TIME (not immediately).

**WHY accept it:**
- Required for distributed systems (CAP theorem)
- Better availability + performance
- Most business operations tolerate small delays

**HOW — Common patterns:**

**Pattern 1: Read-your-writes (session consistency)**

```python
# User submits form → expects to see their data immediately
# But: write to primary, read from replica → may not show yet

# Solution: After write, read from primary for that user briefly
@app.post("/api/profile")
async def update_profile(data, user, response):
    await db.users.update(user.id, data)

    # Mark this user to read from primary for 30 seconds
    response.set_cookie("read_from_primary_until",
                       str(time.time() + 30),
                       max_age=30)

    return {"status": "updated"}


@app.get("/api/profile")
async def get_profile(request, user):
    read_until = request.cookies.get("read_from_primary_until", "0")
    if time.time() < float(read_until):
        # Recent write — read from primary
        db_session = primary_db_session()
    else:
        # Old data OK — read from replica
        db_session = replica_db_session()

    return await db_session.users.get(user.id)
```

**Pattern 2: Compensating transactions (Saga)**

```python
# Order workflow: reserve inventory, charge payment, create order
async def create_order_saga(items, user_id):
    inventory_reservation = None
    payment_id = None

    try:
        # Step 1: Reserve inventory
        inventory_reservation = await inventory_service.reserve(items)

        # Step 2: Charge payment
        payment_id = await payment_service.charge(user_id, total_amount)

        # Step 3: Create order
        order = await order_service.create(items, payment_id)

        return order

    except Exception as e:
        # ⭐ Compensate (rollback in reverse order)
        if payment_id:
            await payment_service.refund(payment_id)
        if inventory_reservation:
            await inventory_service.release(inventory_reservation)

        raise OrderFailedException(e)
```

**Pattern 3: Eventually consistent reads**

```python
# User updates email
@app.post("/api/users/email")
async def update_email(new_email, user):
    # Write to user-service DB
    await user_service.update_email(user.id, new_email)

    # Publish event for other services to sync
    await kafka_producer.send("user.email.updated", {
        "user_id": user.id,
        "new_email": new_email
    })

    return {"status": "queued"}


# Other services lazily sync via consumer
# Notification-service consumer
@kafka_consumer("user.email.updated")
async def sync_notification_email(event):
    await notification_db.users.update_email(
        event["user_id"],
        event["new_email"]
    )
    # ⭐ Eventually consistent — may take seconds to propagate
```

---

### Q4: CDC (Change Data Capture) — DB to events?

**Answer:**

**WHAT:** Stream database changes as events.

**WHY:**
- Sync data without dual-write problem
- Migrate monolith → microservices gradually
- Build read models (CQRS)
- Real-time analytics

**HOW it works:**

```
┌─────────────┐  WAL/Binlog   ┌──────────┐    Events     ┌──────────┐
│ PostgreSQL  ├──────────────►│ Debezium ├──────────────►│  Kafka   │
└─────────────┘                └──────────┘                └──────────┘
                                                                │
                                                ┌───────────────┼──────────────┐
                                                ▼               ▼              ▼
                                          Elasticsearch    Other service    Analytics
                                          (search index)   (cache update)   (data lake)
```

**HOW — Debezium setup (already covered in Kafka file, brief here):**

```yaml
# Connector config — read PostgreSQL WAL
{
  "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
  "database.hostname": "postgres",
  "database.dbname": "myapp",
  "table.include.list": "public.users,public.orders",
  "plugin.name": "pgoutput",
  "snapshot.mode": "initial"
}
```

**HOW — Consume CDC events:**

```python
from kafka import KafkaConsumer
import json

consumer = KafkaConsumer(
    'db.public.users',     # Debezium topic naming
    bootstrap_servers='kafka:9092',
    group_id='user-search-indexer',
    value_deserializer=lambda v: json.loads(v.decode('utf-8')),
)

for message in consumer:
    event = message.value

    op = event['op']           # c=create, u=update, d=delete
    after = event.get('after')
    before = event.get('before')

    if op == 'c':
        # New user created
        await elasticsearch.index('users', after['id'], {
            'name': after['name'],
            'email': after['email'],
        })
    elif op == 'u':
        # User updated
        await elasticsearch.update('users', after['id'], after)
    elif op == 'd':
        # User deleted
        await elasticsearch.delete('users', before['id'])

    consumer.commit()
```

---

### Q5: Polyglot persistence — kab kya DB use karein?

**Answer:**

**WHAT:** Different services use different DB types based on needs.

**HOW — Decision matrix:**

| Use Case | Best DB | Why |
|---|---|---|
| **User accounts** | PostgreSQL | ACID, relations |
| **Order management** | PostgreSQL | Transactions, complex queries |
| **Product catalog** | Elasticsearch | Full-text search, faceting |
| **Session storage** | Redis | Fast key-value, TTL |
| **Cache** | Redis | Speed, expiry |
| **Real-time analytics** | ClickHouse | Columnar, aggregations |
| **Audit logs** | S3 + Athena | Cheap storage, append-only |
| **Time-series metrics** | TimescaleDB / InfluxDB | Time-series optimized |
| **Graph data (social)** | Neo4j | Relationships |
| **Document store** | MongoDB | Flexible schema |
| **Geo data** | PostGIS | Spatial queries |
| **Vector embeddings (AI)** | Pinecone / pgvector | Vector search |
| **Event log** | Kafka | Streaming, replay |
| **File metadata** | DynamoDB | Key-value, scale |

**HOW — Example architecture:**

```python
# E-commerce platform — polyglot example
SERVICES = {
    "user-service": {
        "primary_db": "PostgreSQL",
        "cache": "Redis",
        "reason": "ACID transactions for user accounts"
    },
    "catalog-service": {
        "primary_db": "PostgreSQL (truth)",
        "search_db": "Elasticsearch (indexes)",
        "sync": "Debezium CDC → Kafka → ES",
        "reason": "Need both queries + full-text search"
    },
    "cart-service": {
        "primary_db": "Redis",
        "reason": "Fast read/write, TTL for abandoned carts"
    },
    "order-service": {
        "primary_db": "PostgreSQL",
        "event_store": "Kafka",
        "reason": "ACID for transactions + event sourcing"
    },
    "payment-service": {
        "primary_db": "PostgreSQL",
        "reason": "Financial integrity requires ACID"
    },
    "analytics-service": {
        "primary_db": "ClickHouse",
        "reason": "Aggregations over billions of rows"
    },
    "recommendation-service": {
        "primary_db": "DynamoDB (user preferences)",
        "vector_db": "Pinecone (product embeddings)",
        "reason": "Scale + AI similarity search"
    },
    "audit-service": {
        "primary_db": "S3 (write-only) + Athena (queries)",
        "reason": "Append-only, compliance retention, cheap"
    },
}
```

---

### Q6: Data ownership boundaries — services kaise design karein?

**Answer:**

**WHAT:** Each piece of data has ONE owner service.

**HOW — Identify boundaries:**

**Bad: Anemic boundaries**
```
user-service: owns User entity
order-service: also reads/writes User fields

Problem: dual ownership, no clear API
```

**Good: Bounded contexts (DDD)**
```
user-service: owns "user account" data
  - id, email, password_hash, profile
  - Authoritative source

order-service: owns "customer" view
  - user_id (foreign reference)
  - shipping_addresses (specific to orders)
  - Cached copy of name/email (for display)

If user-service updates email:
- Event published → order-service updates its cached copy
```

**HOW — Reference vs Duplicate:**

```python
# Pattern 1: Reference (call other service for data)
class Order:
    id: int
    user_id: int        # ⭐ Reference only
    items: list[Item]

# When showing order details
async def get_order_details(order_id):
    order = await db.orders.get(order_id)
    user = await user_service_client.get_user(order.user_id)
    return {"order": order, "user": user}

# ✅ Pros: Single source of truth
# ❌ Cons: Network call, latency, dependency


# Pattern 2: Duplicate (cache critical data locally)
class Order:
    id: int
    user_id: int
    # ⭐ Cached for performance + display
    customer_name: str
    customer_email: str
    items: list[Item]

# When user updates email, event syncs to orders
@event_handler("user.email.updated")
async def sync_order_emails(event):
    await db.orders.update_many(
        {"user_id": event.user_id},
        {"customer_email": event.new_email}
    )

# ✅ Pros: No network call
# ❌ Cons: Sync complexity, eventual consistency
```

**Decision: Reference vs Duplicate**

```
Use REFERENCE when:
- Data changes often
- Single source of truth important
- Latency acceptable

Use DUPLICATE when:
- Data is mostly static (user name)
- Performance critical
- Service must work even if owner down
- Display data only (not for business logic)
```

---

### Q7: Cross-service queries — kaise handle karein?

**Answer:**

**WHAT:** Need data from multiple services.

**HOW — 4 patterns:**

**Pattern 1: API Composition (BFF)**

```python
# Frontend BFF calls multiple services, composes response
@app.get("/api/dashboard")
async def get_dashboard(user_id: int):
    # Parallel calls (asyncio.gather)
    user, orders, recommendations = await asyncio.gather(
        user_service.get_user(user_id),
        order_service.get_recent_orders(user_id, limit=5),
        recommendation_service.get_for_user(user_id),
    )

    return {
        "user": user,
        "recent_orders": orders,
        "recommendations": recommendations,
    }

# ✅ Pros: No data duplication
# ❌ Cons: Multiple network calls, latency
```

**Pattern 2: CQRS — Materialized Views**

```python
# Build read-optimized view by consuming events from all services

# Read model in dedicated DB (Elasticsearch, DynamoDB)
class UserDashboardView:
    user_id: int
    user_name: str          # From user-service
    user_email: str
    recent_orders_count: int  # From order-service
    total_spent: float
    recommendation_ids: list[int]  # From rec-service

# Updated by event consumers
@event_handler("user.created")
async def init_dashboard(event):
    await dashboard_view_db.insert(
        UserDashboardView(user_id=event.user_id, user_name=event.name)
    )

@event_handler("order.placed")
async def update_order_stats(event):
    await dashboard_view_db.update(
        event.user_id,
        {
            "recent_orders_count": "$inc(1)",
            "total_spent": f"$inc({event.amount})",
        }
    )

# Single fast query
@app.get("/api/dashboard")
async def get_dashboard(user_id):
    return await dashboard_view_db.get(user_id)

# ✅ Pros: One fast query
# ❌ Cons: Eventual consistency, more storage, sync complexity
```

**Pattern 3: GraphQL Federation**

```python
# Each service exposes GraphQL schema for its data
# Gateway federates them

# user-service schema
type User @key(fields: "id") {
    id: ID!
    name: String!
    email: String!
}

# order-service schema (extends User)
extend type User @key(fields: "id") {
    id: ID! @external
    orders: [Order!]!
}

type Order {
    id: ID!
    amount: Float!
}

# Client query (federated)
query {
    user(id: 123) {
        name           # From user-service
        email
        orders {       # From order-service
            id
            amount
        }
    }
}
```

**Pattern 4: Data Lake (offline analytics)**

```python
# All services dump data to data lake (S3)
# Analytics queries run there (Athena, Spark)

# Not for real-time, but for:
# - Business intelligence
# - ML training data
# - Reporting
# - Compliance queries
```

---

### Q8: Data consistency patterns — strong vs eventual?

**Answer:**

**WHAT — Consistency models:**

| Model | Description | Use Case |
|---|---|---|
| **Strong** | All reads see latest write | Bank balance |
| **Eventual** | Reads eventually see writes | User profile update |
| **Causal** | Causally related events ordered | Comments + replies |
| **Read-your-writes** | User sees own writes immediately | Form submission |
| **Monotonic reads** | Reads progress forward only | Activity feed |
| **Bounded staleness** | Max delay guarantee (e.g., 10s) | Reports |

**HOW — Implement bounded staleness:**

```python
async def get_with_max_staleness(user_id, max_seconds=10):
    # Check cache age
    cached = await redis.get(f"user:{user_id}")
    if cached:
        data = json.loads(cached)
        age = time.time() - data["cached_at"]
        if age <= max_seconds:
            return data["value"]

    # Cache stale or missing → fresh read
    user = await user_service.get_user(user_id)
    await redis.set(
        f"user:{user_id}",
        json.dumps({"value": user, "cached_at": time.time()}),
        ex=max_seconds
    )
    return user
```

**HOW — Strong consistency when needed:**

```python
# Critical: account balance
@app.post("/api/transfer")
async def transfer_funds(from_account, to_account, amount):
    async with db.transaction():       # ACID within payment-service DB
        # Pessimistic lock
        from_acct = await db.accounts.get_for_update(from_account)
        to_acct = await db.accounts.get_for_update(to_account)

        if from_acct.balance < amount:
            raise InsufficientFunds()

        from_acct.balance -= amount
        to_acct.balance += amount

        await db.accounts.save(from_acct)
        await db.accounts.save(to_acct)
        # Commit atomic (both succeed or both fail)
```

---

## Distributed Data Checklist

```markdown
### Architecture
- [ ] Each service owns its data (no shared DB)
- [ ] Clear data ownership boundaries (DDD)
- [ ] Right DB per service (polyglot)
- [ ] No cross-service joins in code

### Consistency
- [ ] Identify strong consistency needs (rare)
- [ ] Accept eventual consistency for most
- [ ] Saga pattern for distributed workflows
- [ ] No 2PC

### Communication
- [ ] API calls for current data
- [ ] Events for state changes
- [ ] CDC for sync (without app changes)
- [ ] Outbox pattern for reliable events

### Read Patterns
- [ ] API composition for simple aggregations
- [ ] CQRS materialized views for complex
- [ ] GraphQL federation for unified API
- [ ] Caching with bounded staleness

### Resilience
- [ ] Circuit breakers for downstream calls
- [ ] Cached fallbacks
- [ ] Graceful degradation
- [ ] Async event processing

### Migration
- [ ] Strangler Fig for monolith → microservices
- [ ] CDC for incremental data sync
- [ ] Feature flags for gradual cutover
- [ ] Rollback plan
```

---

## Common Pitfalls

| Pitfall | Risk | Fix |
|---|---|---|
| Shared database | Tight coupling | DB per service |
| Cross-service joins | Schema coupling | API calls or CDC |
| 2PC for consistency | Performance, complexity | Saga + eventual consistency |
| No event versioning | Breaking consumers | Schema Registry |
| Synchronous chains (A→B→C→D) | Latency, cascading failures | Async events |
| Same data updated by multiple services | Conflicts | Single owner |
| No retry/idempotency | Data inconsistency | Idempotency keys |
| Skipping eventual consistency UX | Confusing users | Show "syncing..." states |
