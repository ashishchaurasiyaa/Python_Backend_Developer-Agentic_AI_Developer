# Circuit Breaker + Event-Driven Architecture + Service Mesh

## PART 1 — Circuit Breaker Pattern

### WHAT
A fault-tolerance mechanism that **stops calling a failing service** and returns fallback responses, preventing cascading failures.

Named after electrical circuit breakers that cut power to prevent fires.

### States
```
CLOSED    → Normal operation. All requests pass through.
              If errors exceed threshold → move to OPEN
              
OPEN      → Short-circuit! Reject all requests immediately.
              After timeout → move to HALF-OPEN
              
HALF-OPEN → Test mode. Let ONE request through.
              If success → CLOSED
              If fail    → back to OPEN
```

### WHY
Without circuit breaker:
- User Service calls LLM Service (which is slow/down)
- All User Service threads block waiting
- User Service also goes down
- Entire system collapses (cascading failure)

With circuit breaker:
- LLM Service starts failing → OPEN circuit
- User Service gets instant error (no waiting)
- User Service stays healthy
- LLM Service recovers → HALF-OPEN → CLOSED

### Python Implementation

```python
import time
import asyncio
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Callable, Any

class State(Enum):
    CLOSED    = auto()
    OPEN      = auto()
    HALF_OPEN = auto()

@dataclass
class CircuitBreaker:
    name:            str
    failure_threshold: int   = 5      # open after 5 failures
    success_threshold: int   = 2      # close after 2 successes in HALF_OPEN
    timeout:         float   = 30.0   # seconds in OPEN before trying HALF_OPEN
    
    _state:          State   = field(default=State.CLOSED, init=False)
    _failures:       int     = field(default=0, init=False)
    _successes:      int     = field(default=0, init=False)
    _opened_at:      float   = field(default=0.0, init=False)

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        if self._state == State.OPEN:
            if time.time() - self._opened_at >= self.timeout:
                self._state    = State.HALF_OPEN
                self._successes = 0
                print(f"[{self.name}] → HALF_OPEN (testing)")
            else:
                raise Exception(f"CircuitBreaker OPEN: {self.name} unavailable")
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as exc:
            self._on_failure()
            raise

    def _on_success(self):
        self._failures = 0
        if self._state == State.HALF_OPEN:
            self._successes += 1
            if self._successes >= self.success_threshold:
                self._state = State.CLOSED
                print(f"[{self.name}] → CLOSED (recovered)")

    def _on_failure(self):
        self._failures += 1
        if self._state == State.HALF_OPEN or self._failures >= self.failure_threshold:
            self._state    = State.OPEN
            self._opened_at = time.time()
            print(f"[{self.name}] → OPEN (tripped at {self._failures} failures)")


# Usage
llm_breaker = CircuitBreaker(name="llm-service", failure_threshold=3)

async def call_llm_safe(prompt: str) -> str:
    try:
        return await llm_breaker.call(call_llm_api, prompt)
    except Exception:
        # Fallback response
        return "Service temporarily unavailable. Please try again."
```

---

## PART 2 — Event-Driven Architecture (EDA)

### WHAT
Services communicate by **publishing events** to a message broker. Other services **subscribe** and react asynchronously.

```
Synchronous (REST):
  Order Service → HTTP POST → Payment Service → waits → response

Event-Driven:
  Order Service → publishes "order.created" → Kafka
                                             ↳ Payment Service (async)
                                             ↳ Inventory Service (async)
                                             ↳ Email Service (async)
                                             ↳ Analytics Service (async)
```

### WHY EDA

| Problem | EDA Solution |
|---|---|
| Tight coupling | Services don't know each other |
| Single point of failure | Broker handles failures |
| Slow downstream blocking | Async → order returns immediately |
| Can't add new consumers | Add new subscriber without changing publisher |
| Peak load handling | Broker buffers, consumers pace themselves |

### Event Types
```
Domain events:    order.created, user.registered, payment.failed
Integration events: Sent across service boundaries
Command events:   process.payment (tells a specific service what to do)
```

### Python EDA with Kafka

```python
# Producer (Order Service)
from kafka import KafkaProducer
import json

producer = KafkaProducer(
    bootstrap_servers=["kafka:9092"],
    value_serializer=lambda v: json.dumps(v).encode(),
)

def create_order(user_id: str, items: list) -> dict:
    order = {"id": "ord-123", "user_id": user_id, "items": items, "status": "pending"}
    # Save to DB first
    db.save(order)
    # Publish event (fire and forget)
    producer.send("order.created", value={
        "event": "order.created",
        "order_id": order["id"],
        "user_id": user_id,
        "timestamp": datetime.utcnow().isoformat(),
    })
    return order   # return immediately — don't wait for payment


# Consumer (Payment Service)
from kafka import KafkaConsumer

consumer = KafkaConsumer(
    "order.created",
    bootstrap_servers=["kafka:9092"],
    group_id="payment-service",
    value_deserializer=lambda m: json.loads(m.decode()),
    auto_offset_reset="earliest",
)

for message in consumer:
    event = message.value
    if event["event"] == "order.created":
        process_payment(event["order_id"], event["user_id"])
        # On success: publish "payment.completed"
        # On failure: publish "payment.failed" → Order Service handles
```

### EDA with asyncio + in-process (simpler, for single service)

```python
# Simple in-process event bus (Observer pattern at scale)
from collections import defaultdict
from typing import Callable
import asyncio

class EventBus:
    def __init__(self):
        self._handlers: dict[str, list[Callable]] = defaultdict(list)

    def subscribe(self, event: str, handler: Callable):
        self._handlers[event].append(handler)

    async def publish(self, event: str, payload: dict):
        for handler in self._handlers[event]:
            asyncio.create_task(handler(payload))   # non-blocking

bus = EventBus()

@bus.subscribe("order.created")  # type: ignore
async def send_confirmation_email(payload: dict):
    await email_service.send(payload["user_id"], "Order confirmed!")

@bus.subscribe("order.created")
async def update_inventory(payload: dict):
    await inventory_service.deduct(payload["items"])
```

---

## PART 3 — Service Mesh

### WHAT
Infrastructure layer that handles **service-to-service communication** (east-west traffic) with mTLS, retries, circuit breaking — without changing application code.

**Tools:** Istio, Linkerd, Consul Connect

### Sidecar Proxy Pattern
```
┌─────────────────────────────┐
│  Pod A                      │
│  ┌───────────┐ ┌──────────┐ │
│  │ App Code  │ │ Envoy    │ │ ← sidecar proxy
│  │ (Python)  │ │ (sidecar)│ │
│  └─────┬─────┘ └────┬─────┘ │
└────────│─────────────│───────┘
         │ localhost   │ network calls
         └─────────────┘
```
All traffic goes through the sidecar proxy. App code doesn't change.

### Service Mesh vs API Gateway

| | API Gateway | Service Mesh |
|---|---|---|
| Traffic | North-south (client ↔ service) | East-west (service ↔ service) |
| Auth | JWT / API key | mTLS (mutual TLS) |
| Config | Centralised | Distributed (per pod) |
| Focus | External API | Internal reliability |

---

## Interview Q&A

**Q: What is cascading failure and how does circuit breaker prevent it?**
A: Cascading failure = one service failure causes dependent services to also fail (like dominoes). Circuit breaker opens and returns fast errors instead of blocking → upstream services stay healthy.

**Q: What is the difference between event-driven and pub-sub?**
A: Pub-sub is a pattern (publisher → topic → subscribers). Event-driven is the broader architecture philosophy. Pub-sub is one implementation of EDA. Other implementations: event sourcing, CQRS.

**Q: What is exactly-once delivery in Kafka?**
A: Guarantees each message is processed exactly once (not 0 times or 2+ times). Requires: idempotent producer + transactional consumer + same consumer group. More expensive — use only when needed (payments, inventory).

**Q: What does a service mesh give you that a library doesn't?**
A: Language-agnostic (works for Python, Go, Java services equally). No code changes. Centralised observability (all traces, metrics from one place). Automatic mTLS encryption between all services.
