# Microservices Anti-Patterns — Distributed Monolith, Death Star, Wrong Boundaries

## Quick Concepts

**WHAT:** Common mistakes when adopting microservices.

**WHY know anti-patterns:**
- ❌ Most "microservices failures" = these anti-patterns
- ❌ Hard to recover from once in place
- ✅ Avoid them = save years of pain
- ✅ Recognize early = course correct

**HOW patterns evolve into anti-patterns:**

```
Year 1: "Let's go microservices!" (excitement)
Year 2: "Why is everything so slow?" (distributed monolith)
Year 3: "We can't change anything without breaking 5 services" (death star)
Year 4: "Let's merge services back" (de-microservicing)

Often outcome: Premature/wrong microservices → painful refactoring
```

---

## Interview Questions & Answers

### Q1: Distributed Monolith — sabse common anti-pattern?

**Answer:**

**WHAT:** Services that LOOK like microservices but BEHAVE like a monolith.

**WHY it happens:**
- Wrong boundaries (split by tech layer, not business domain)
- Services tightly coupled (need to deploy together)
- Synchronous calls everywhere
- Shared database

**HOW — Symptoms:**

| Symptom | Diagnosis |
|---|---|
| Must deploy services in specific order | Distributed monolith |
| One service change requires testing 5 others | Distributed monolith |
| Services share database | Distributed monolith |
| Service A waits for B for every request | Distributed monolith |
| Can't roll back individual service | Distributed monolith |
| Latency = 5x monolith | Distributed monolith |
| Adding service requires touching 10 others | Distributed monolith |

**HOW — Real example:**

```
❌ Distributed Monolith (split by technical layer):

API Gateway → UserController-service → UserService-service → UserDAO-service → Database

Problems:
- Every request: 4 network hops
- Adding field requires changing 4 services
- All deploys must coordinate
- One service down = entire flow down


✅ Proper Microservices (split by business capability):

API Gateway → User Service (full stack: controller + service + DAO + own DB)
            → Order Service (full stack + own DB)
            → Payment Service (full stack + own DB)

Each service:
- Owns vertical slice of functionality
- Independent deploy
- Independent scaling
- Own database
```

**HOW — Refactor distributed monolith:**

```python
# Step 1: Identify "service clusters" that always change together
# These should be ONE service

# Step 2: Move shared data into one owner
# If user-controller, user-service, user-dao all manipulate users
# → merge into single "user-service"

# Step 3: Reduce synchronous coupling
# Replace sync calls with async events where possible

# Step 4: Independent deployment
# Each service has own CI/CD, own version, own rollback
```

---

### Q2: Death Star Architecture — explain?

**Answer:**

**WHAT:** Microservices with complex tangled dependencies (looks like the Death Star).

**WHY:**
- Organic growth without boundaries
- "Just one more sync call" pattern
- No architectural review

**HOW — Visual:**

```
❌ Death Star:
        ┌────┐ ────────► ┌────┐ ◄──── ┌────┐
        │ S1 │ ◄──────── │ S2 │ ────► │ S3 │
        └─┬──┘           └─┬──┘       └─┬──┘
          │     ┌─────┐    │            │
          ├────►│ S4  │◄───┤            │
          │     └─────┘    │            │
          ▼                ▼            ▼
        ┌────┐ ────────► ┌────┐ ◄──── ┌────┐
        │ S5 │           │ S6 │       │ S7 │
        └────┘           └────┘       └────┘
          (synchronous calls everywhere)

Result:
- Cascading failures (one slow = all slow)
- Impossible to reason about
- Latency = sum of all calls
- Debugging nightmare
```

**HOW — Detect Death Star:**

```bash
# Count cross-service calls per request
# Tool: distributed tracing (Jaeger, X-Ray)

# Sample trace analysis
SELECT request_id, COUNT(DISTINCT service_name) as services_touched
FROM traces
GROUP BY request_id
ORDER BY services_touched DESC
LIMIT 10;

# Healthy: 2-5 services per request
# Death Star: 10-20+ services per request
```

**HOW — Recover:**

```
1. Map current architecture (service dependency graph)
2. Identify hot paths (most requests)
3. Reduce sync calls:
   - Convert to async events
   - Cache external data locally
   - Use CQRS materialized views
4. Define clear service boundaries (DDD bounded contexts)
5. Merge over-decomposed services
```

---

### Q3: Shared database — kyu anti-pattern hai?

**Answer:**

**WHAT:** Multiple services share same database (often same tables).

**WHY tempting:**
- Easier transactions (single DB ACID)
- No data sync complexity
- Familiar pattern

**WHY actually anti-pattern:**

```
Service A and B share "users" table

Service A team wants to add column → breaks Service B
Service B team wants to optimize index → affects Service A
Both teams need to coordinate every schema change

⭐ Tight coupling at DATA layer
⭐ Worse than monolith (more processes, same coupling)
```

**HOW — Symptoms:**

- Schema migration requires multi-team coordination
- Performance issues affect multiple services
- Can't deploy schema changes independently
- Joining tables in queries across services
- Shared ORM models

**HOW — Fix:**

```
Step 1: Identify table ownership
  - Which service writes to this table the most?
  - Which service has business logic for this entity?
  - That's the owner.

Step 2: Move table to owner's DB (physically separate)

Step 3: Other services access via API
  - Replace direct SQL with HTTP calls
  - Cache results to reduce calls

Step 4: For complex queries
  - Use CQRS materialized views
  - Or accept eventual consistency
```

**Real-world refactor example:**

```python
# ❌ Before: shared database
# Service A (order-service) queries users table:
SELECT u.name, u.email, o.amount
FROM users u
JOIN orders o ON u.id = o.user_id
WHERE o.id = $1


# ✅ After: separate databases + API call
# order-service own DB has only orders
order = await db.orders.get(order_id)

# Call user-service for user data
async with httpx.AsyncClient() as client:
    response = await client.get(f"http://user-service/users/{order.user_id}")
    user = response.json()

return {"order": order, "user": user}
```

---

### Q4: Synchronous chain calls — latency killer?

**Answer:**

**WHAT:** A → B → C → D → E, each waiting for next.

**WHY problem:**

```
Latency multiplies:
Service A: 50ms
Service B: 50ms (called by A)
Service C: 50ms (called by B)
Service D: 50ms (called by C)
Service E: 50ms (called by D)

Total user-perceived latency: 250ms
And: cascading failure (any one down = all down)
And: bandwidth waste (5x payload across network)
```

**HOW — Symptoms:**

```python
# Anti-pattern code
@app.get("/api/checkout")
async def checkout(user_id):
    user = await user_service.get_user(user_id)              # 50ms
    cart = await cart_service.get_cart(user_id)              # 50ms
    inventory = await inventory_service.check(cart.items)    # 50ms
    payment = await payment_service.charge(user, cart)       # 100ms
    order = await order_service.create(user, cart, payment)  # 50ms
    notification = await notif_service.send_email(user)      # 100ms

    # Total: 400ms
    return order
```

**HOW — Fix Pattern 1: Parallel calls (asyncio.gather)**

```python
@app.get("/api/checkout")
async def checkout(user_id):
    # Parallel independent calls
    user, cart, inventory = await asyncio.gather(
        user_service.get_user(user_id),
        cart_service.get_cart(user_id),
        inventory_service.check(user_id),  # Pre-load
    )
    # Total: max(50, 50, 50) = 50ms instead of 150ms

    # Sequential only when truly dependent
    payment = await payment_service.charge(user, cart)
    order = await order_service.create(user, cart, payment)

    # Async fire-and-forget (don't wait)
    asyncio.create_task(notif_service.send_email(user))

    return order
```

**HOW — Fix Pattern 2: API Composition (BFF)**

```python
# Move composition logic to dedicated BFF
# So that service-to-service stays simple

# BFF for mobile app
@app.get("/api/mobile/dashboard")
async def mobile_dashboard(user_id):
    # BFF makes parallel calls, composes response
    user, recent_orders, recommendations = await asyncio.gather(
        user_service.get_user(user_id),
        order_service.get_recent(user_id, limit=5),
        recommendation_service.get_for_user(user_id),
    )

    # Mobile-specific format
    return {
        "user_name": user["name"],
        "order_count": len(recent_orders),
        "recommendations": recommendations[:3],  # Smaller for mobile
    }
```

**HOW — Fix Pattern 3: Async events**

```python
# Convert "checkout" to event-driven
@app.post("/api/checkout")
async def checkout(user_id):
    # Just create checkout event, return immediately
    checkout_id = await db.checkouts.create(user_id, status="processing")

    # Async event processing
    await kafka_producer.send("checkout.initiated", {
        "checkout_id": checkout_id,
        "user_id": user_id,
    })

    return {"checkout_id": checkout_id, "status": "processing"}


# Client polls for status (or WebSocket update)
@app.get("/api/checkout/{checkout_id}/status")
async def get_status(checkout_id):
    return await db.checkouts.get(checkout_id)


# Workers handle each step asynchronously
@event_handler("checkout.initiated")
async def reserve_inventory(event):
    await inventory_service.reserve(...)
    await kafka_producer.send("inventory.reserved", ...)

@event_handler("inventory.reserved")
async def charge_payment(event):
    ...
```

---

### Q5: Service sprawl — too many services?

**Answer:**

**WHAT:** Hundreds of tiny services without clear purpose.

**WHY happens:**
- "Microservices = smaller is better" myth
- Every team builds own
- Splitting at function level (anti-DDD)

**HOW — Symptoms:**

- 100+ services, 10 engineers
- Each service has 1-2 endpoints
- More boilerplate than business logic
- Ops nightmare (100 deployments, 100 dashboards)
- New engineer takes weeks to understand

**HOW — Right-sizing rule of thumb:**

```
Bad signs (too small):
- Service can fit in single .py file (~100 lines)
- "User-name-update-service" (function as service)
- Tons of HTTP overhead vs actual work

Bad signs (too large):
- Service is 100K LOC
- Multiple teams own different parts
- Frequent merge conflicts
- Hard to fully understand

Goldilocks:
- 1 team can own 1-3 services
- 2K-50K lines of code
- 5-50 endpoints
- Coherent business capability
```

**HOW — When to merge services back:**

```python
# Indicators that two services should merge:
# 1. They deploy together >80% of the time
# 2. Changes to one usually require changes to other
# 3. Latency due to inter-service calls dominates
# 4. Same team owns both
# 5. Same data model (just split for "purity")

# Real example: shopping-cart-service + cart-validation-service
# - Always deployed together
# - validation has 2 endpoints, called only by cart
# - Cart and validation share 60% of data models
# → MERGE into single cart-service
```

---

### Q6: Wrong service boundaries — kaise detect?

**Answer:**

**WHAT:** Services split by wrong criteria (technical vs business).

**HOW — Bad splits:**

**1. Split by technical layer**
```
❌ user-controller-service, user-service-service, user-dao-service
✅ user-service (full vertical)
```

**2. Split by data type**
```
❌ string-validator-service, integer-validator-service
✅ Library inside services (not separate service)
```

**3. Split by CRUD operation**
```
❌ user-create-service, user-read-service, user-update-service
✅ user-service (all operations on User)
```

**4. Split by team alone**
```
❌ "Each developer gets own service"
✅ Service per business capability (multiple devs work on one if needed)
```

**HOW — Right way: DDD Bounded Contexts**

```
✅ Right boundaries (e-commerce):
- catalog-service       (products, search, recommendations)
- order-service         (cart, checkout, orders)
- payment-service       (transactions, refunds)
- shipping-service      (tracking, carriers)
- user-service          (accounts, profiles, addresses)
- notification-service  (email, SMS, push)
- analytics-service     (events, reports)
```

**HOW — Test if boundaries are right:**

```
Question 1: If I delete this service, does ONE business capability disappear?
  - Yes ✅ Good boundary
  - No → likely wrong boundary

Question 2: Does this service's name include "and" or "or"?
  - "user-and-account-service" → too much
  - "user-service" → focused

Question 3: Can one team fully own this service?
  - Yes ✅
  - "We need 3 teams to make changes" → too big

Question 4: Does it have own data?
  - Yes ✅
  - "Just reads from shared DB" → not really a service
```

---

### Q7: Premature microservices — start with monolith?

**Answer:**

**WHAT:** Building microservices for small/early-stage apps.

**WHY anti-pattern:**

```
Costs of microservices:
- Operational complexity (10+ deployments)
- Network latency (was function call, now HTTP)
- Distributed system bugs (timeouts, retries, partial failures)
- Observability needs (tracing, logging across services)
- Team coordination

For 5-engineer startup with 1000 users:
- Above costs HUGE
- Benefits NEGLIGIBLE
- Net negative

✅ "Monolith first" — Martin Fowler
```

**HOW — When microservices justified:**

| Factor | Stay Monolith | Go Microservices |
|---|---|---|
| **Team size** | < 20 engineers | 20+ engineers |
| **User scale** | < 100K DAU | 100K+ DAU |
| **Domain complexity** | Simple/medium | Multiple subdomains |
| **Polyglot need** | Python OK | Need Go + Java + Python |
| **Independent scaling** | Not critical | Different services need different scale |
| **Different release cycles** | Same cadence | Independent releases |
| **Compliance** | None | PCI for payment only |

**HOW — Monolith done right (modular monolith):**

```python
# Modular monolith — same process, clear boundaries
# Can become microservices later

# myapp/
#   ├── catalog/        ← Module (bounded context)
#   │   ├── domain.py
#   │   ├── service.py
#   │   ├── repository.py
#   │   └── api.py
#   ├── orders/         ← Module
#   │   ├── domain.py
#   │   ├── service.py
#   │   ├── repository.py
#   │   └── api.py
#   ├── payments/       ← Module
#   ├── notifications/  ← Module
#   ├── shared/         ← Truly shared (logging, db conn)
#   └── main.py

# Rules:
# 1. Modules communicate only via public API (service classes)
# 2. NEVER cross-module DB queries
# 3. Each module owns its DB schema (separate tables)
# 4. Use in-process events for module communication

# Later: pull each module out as microservice (cheap if done right)
```

---

### Q8: When to merge services back (de-microservice)?

**Answer:**

**WHAT:** Recognize when microservices aren't working and merge.

**WHY:**
- Microservices not religion
- Wrong split = pain
- Reversing is OK

**HOW — Signs to merge:**

**1. Always deployed together**
```
If service A and B always release in same PR → they're one service in two boxes
```

**2. Tight coupling at API**
```
Service A makes 5+ different calls to Service B per request
→ The API is "leaking" internals
→ Merge them
```

**3. Same team, same domain**
```
Same team owns both services
Both implement same business capability
No real boundary → merge
```

**4. Cascading failures**
```
B down → A down (no graceful degradation possible)
→ Why not just one process?
```

**5. Performance issues from network calls**
```
70% of A's CPU spent on HTTP overhead to B
→ Inline B's logic into A
```

**HOW — Merge process:**

```python
# Step 1: Choose target service (usually the "outer" one)
# Step 2: Add Service B's logic as a module in Service A
# Step 3: Update Service A's API to use module directly (not HTTP)
# Step 4: Migrate Service B's data into Service A's DB
# Step 5: Deprecate Service B
# Step 6: Delete Service B

# Before: order-service + order-validation-service
# After: order-service (with validation module)


# Famous real example: Amazon's Audible
# - Started microservices for everything
# - Found some services should be merged
# - Moved back to "macro-services" (medium-sized)
```

---

## Microservices Anti-Patterns Cheatsheet

```markdown
### Distributed Monolith
- [ ] Services deploy together → too coupled
- [ ] Shared database → consolidate ownership
- [ ] Sync chain calls → async events
- [ ] One change = test all → wrong boundaries

### Death Star
- [ ] Trace shows 10+ services per request → too many calls
- [ ] No service can fail gracefully → no fallbacks
- [ ] Map dependency graph → find tangles
- [ ] Reduce via caching, async, BFF

### Shared Database
- [ ] Multiple services accessing same tables
- [ ] Solution: DB per service, API for cross-service
- [ ] Migration: CDC, expand-contract

### Wrong Boundaries
- [ ] Split by tech layer (controller/service/dao)
- [ ] Split by CRUD operation
- [ ] One person per service
- [ ] Fix: DDD bounded contexts

### Service Sprawl
- [ ] 100+ services, 10 engineers → over-decomposed
- [ ] Services with 1-2 endpoints → too small
- [ ] Merge related services

### Premature Microservices
- [ ] < 20 engineers? Stay monolith
- [ ] Modular monolith first, microservices later
- [ ] Don't follow hype

### Operational Anti-Patterns
- [ ] No distributed tracing → blind
- [ ] No service mesh / standardization → chaos
- [ ] Per-service CI/CD inconsistent → toil
- [ ] No on-call rotation per service → unowned
```

---

## Quick Decision Rules

| If you see... | Likely problem | Fix |
|---|---|---|
| Deploy 3 services together | Distributed monolith | Merge or async |
| Cross-service joins in code | Shared DB | API + DB per service |
| Service makes 10+ calls per request | Death star | Async events |
| 100 services, 10 engineers | Service sprawl | Merge similar |
| Service has 1 endpoint | Too small | Inline into caller |
| "Why is everything slow?" | Sync chains | Parallel + cache |
| Schema change blocks team | Shared DB | Per-service DB |
| 5-engineer startup with 30 services | Premature | Refactor to modular monolith |
