# Service Discovery + Distributed Locking + Distributed Transactions

## PART 1 — Service Discovery

### WHAT
In microservices, services start/stop/scale dynamically. **Service discovery** lets services find each other without hardcoded IPs.

```
Without:  Service A knows "User Service is at 10.0.1.42:8001"
          What if User Service restarts with a new IP? → broken

With:     Service A asks registry "where is User Service?" → gets current IP
```

### Two Patterns

**Client-Side Discovery (Eureka, Consul):**
```
Client → Service Registry → gets list of instances
Client picks one (load balances itself)

Pros: Client controls LB strategy
Cons: Client needs discovery logic (language-specific)
```

**Server-Side Discovery (AWS ALB, Kubernetes):**
```
Client → Load Balancer → Service Registry → correct instance
Client knows nothing about discovery

Pros: Client is simple
Cons: Extra hop (LB)
```

### DNS-Based Service Discovery (Kubernetes)
```yaml
# Every K8s Service gets a DNS name:
# user-service.default.svc.cluster.local:8001
# order-service.default.svc.cluster.local:8002

# Python code just uses service name
import httpx
response = httpx.get("http://user-service/api/users/123")
# Kubernetes DNS resolves "user-service" → ClusterIP → pods
```

### Consul Service Registry

```python
import consul

c = consul.Consul(host="consul", port=8500)

# Register a service
c.agent.service.register(
    name    = "llm-service",
    service_id = "llm-service-1",
    address = "10.0.1.50",
    port    = 8003,
    check   = consul.Check.http("http://10.0.1.50:8003/health", interval="10s"),
)

# Discover a service
index, services = c.health.service("llm-service", passing=True)
if services:
    service = services[0]["Service"]
    url = f"http://{service['Address']}:{service['Port']}"
    print(f"Found LLM service at: {url}")
```

---

## PART 2 — Distributed Locking

### WHAT
When multiple instances of a service run in parallel, you need to ensure only **one instance** executes a critical section at a time — across different machines.

### WHY Needed
```
Scenario: 10 instances of job-scheduler running
Each checks "are there pending jobs?" → all find job-001 → all try to process it
→ job-001 processed 10 times (bad!)

Solution: Distributed lock → only 1 instance gets the lock → processes job-001
```

### Redis-Based Distributed Lock (Redlock)

```python
import redis
import uuid
import time

r = redis.Redis()

class DistributedLock:
    def __init__(self, name: str, ttl_ms: int = 5000):
        self.name   = f"lock:{name}"
        self.ttl    = ttl_ms
        self.token  = str(uuid.uuid4())   # unique per lock acquisition

    def acquire(self, retry: int = 3, delay: float = 0.1) -> bool:
        """Try to acquire lock. Returns True if acquired."""
        for _ in range(retry):
            # SET key value NX PX ttl → atomic set if not exists
            acquired = r.set(self.name, self.token, nx=True, px=self.ttl)
            if acquired:
                return True
            time.sleep(delay)
        return False

    def release(self) -> bool:
        """Release lock — only if WE hold it (compare token)."""
        # Lua script for atomic check-and-delete
        lua = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        result = r.eval(lua, 1, self.name, self.token)
        return bool(result)

    def __enter__(self):
        if not self.acquire():
            raise TimeoutError(f"Could not acquire lock: {self.name}")
        return self

    def __exit__(self, *args):
        self.release()


# Usage
with DistributedLock("process-job-001", ttl_ms=10_000):
    # Only ONE instance reaches here at a time
    process_job("job-001")
```

### When to Use Distributed Locking

| Use case | Lock needed? |
|---|---|
| Cron job that runs on multiple instances | ✅ YES — only 1 should run |
| Inventory deduction (prevent oversell) | ✅ YES |
| Sending email notification | Maybe — use idempotency key instead |
| Updating user profile | ✅ YES (or DB row-level lock) |
| Counting views | ❌ NO — Redis INCR is atomic already |

---

## PART 3 — Distributed Transactions

### WHAT
A transaction that spans **multiple services/databases**. Much harder than single-DB transactions.

### Problem
```
Order Service → deducts inventory (DB-1)
             → charges payment (DB-2)
             → sends email (Service-3)

If payment fails after inventory deducted → inventory wrong
No single COMMIT can span all three
```

### Pattern 1 — Two-Phase Commit (2PC)

```
Phase 1 (Prepare):
  Coordinator asks all participants: "Can you commit?"
  Each participant: locks resources, responds YES or NO

Phase 2 (Commit/Rollback):
  If ALL said YES → Coordinator sends COMMIT → all commit
  If ANY said NO  → Coordinator sends ROLLBACK → all rollback

Problems:
  - Blocking: if coordinator dies in Phase 2, participants stuck with locks
  - Slow: 2 round trips + locks held
  - Used by: PostgreSQL, MySQL with XA transactions
```

### Pattern 2 — SAGA Pattern (preferred for microservices)

```
Sequence of local transactions, each publishing an event.
If one fails → compensating transactions undo previous steps.

Order Saga:
  1. Create Order (local) → publish "order.created"
  2. Reserve Inventory (local) → publish "inventory.reserved"
  3. Charge Payment (local) → publish "payment.charged"
  4. Confirm Order (local) → done ✓

If Step 3 fails:
  Compensate Step 2: "release inventory"
  Compensate Step 1: "cancel order"
```

```python
# Saga implementation
from dataclasses import dataclass, field
from typing import Callable, Awaitable

@dataclass
class SagaStep:
    name:      str
    execute:   Callable
    compensate: Callable   # undo action

class Saga:
    def __init__(self, steps: list[SagaStep]):
        self.steps = steps

    async def run(self, context: dict) -> dict:
        completed = []

        for step in self.steps:
            try:
                context = await step.execute(context)
                completed.append(step)
                print(f"✓ {step.name}")
            except Exception as exc:
                print(f"✗ {step.name}: {exc}. Compensating...")
                # Rollback completed steps in reverse
                for done in reversed(completed):
                    try:
                        await done.compensate(context)
                        print(f"  ↩ Compensated: {done.name}")
                    except Exception as comp_exc:
                        print(f"  ✗ Compensation failed: {done.name}: {comp_exc}")
                raise RuntimeError(f"Saga failed at {step.name}") from exc

        return context


# Define the Order Saga
order_saga = Saga([
    SagaStep(
        "create-order",
        execute    = create_order_in_db,
        compensate = cancel_order_in_db,
    ),
    SagaStep(
        "reserve-inventory",
        execute    = reserve_inventory,
        compensate = release_inventory,
    ),
    SagaStep(
        "charge-payment",
        execute    = charge_payment,
        compensate = refund_payment,
    ),
    SagaStep(
        "confirm-order",
        execute    = confirm_order,
        compensate = lambda ctx: None,   # final step — nothing to undo
    ),
])

# Run
await order_saga.run({"user_id": "u-123", "items": [...]})
```

### 2PC vs SAGA

| | 2PC | SAGA |
|---|---|---|
| Consistency | Strong | Eventual |
| Blocking | Yes (holds locks) | No |
| Failure handling | Automatic rollback | Compensating transactions |
| Performance | Slow | Fast |
| Best for | Short DB transactions | Long microservice flows |

---

## PART 4 — Idempotency

### WHAT
An operation is **idempotent** if calling it multiple times has the same effect as calling it once.

### WHY Critical
Networks fail. Clients retry. If your API isn't idempotent:
```
Client: POST /payments  (sent)
Server: processes payment → response lost in network
Client: POST /payments  (retry) → USER CHARGED TWICE ❌
```

### HOW — Idempotency Key

```python
import hashlib
import redis
r = redis.Redis()

def process_payment(payment_id: str, amount: float, idempotency_key: str) -> dict:
    """Idempotent payment — safe to retry."""
    cache_key = f"idem:{idempotency_key}"
    
    # Check if already processed
    cached = r.get(cache_key)
    if cached:
        return json.loads(cached)   # return same response
    
    # Process payment
    result = payment_gateway.charge(payment_id, amount)
    
    # Cache result with TTL (24h)
    r.setex(cache_key, 86400, json.dumps(result))
    return result


# FastAPI endpoint
@app.post("/payments")
async def create_payment(
    request: PaymentRequest,
    idempotency_key: str = Header(...),   # required header
):
    return process_payment(
        request.payment_id,
        request.amount,
        idempotency_key,
    )

# Client sends same Idempotency-Key on retry → same response, no double charge
```

---

## Interview Q&A

**Q: Why is 2PC problematic in microservices?**
A: 2PC requires all participants to lock resources during both phases. If the coordinator crashes after Phase 1, participants are stuck in limbo with locks held indefinitely. Doesn't work well across network partitions.

**Q: What is a compensating transaction?**
A: An operation that undoes the effect of a previous successful step. For example, if "reserve inventory" succeeded but "charge payment" failed, the compensating transaction for inventory is "release reservation". Compensations must be idempotent.

**Q: How is distributed locking different from database locking?**
A: DB locking (SELECT FOR UPDATE) works within one database. Distributed lock (Redis Redlock) works across multiple service instances that share no database. Redis lock is held in memory; DB lock is held in the DB.

**Q: What is the TTL (time-to-live) in a distributed lock for?**
A: Safety net for deadlocks. If the process holding the lock crashes before releasing it, the TTL ensures the lock automatically expires and others can acquire it. Set TTL slightly longer than your operation duration.
