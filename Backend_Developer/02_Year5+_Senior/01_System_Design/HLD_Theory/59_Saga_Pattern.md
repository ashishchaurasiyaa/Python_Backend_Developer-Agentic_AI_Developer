# Saga Pattern — Distributed Transactions

## Problem
In microservices, a single business operation (e.g. "place order") spans multiple services.
You can't use a DB transaction across services. How do you keep data consistent?

## What is Saga?
A sequence of local transactions where each step publishes an event or message to trigger the next step.
If any step fails → run compensating transactions to undo previous steps.

---

## Two Types

### 1. Choreography (Event-based)
Each service listens to events and reacts. No central coordinator.

```
Order Service        Payment Service       Inventory Service
     │                     │                      │
     │── OrderCreated ────►│                      │
     │                     │── PaymentDone ───────►│
     │                     │                      │── InventoryReserved ──► Done
     │                     │                      │
     │◄── PaymentFailed ───│ (if fails)
     │  (run compensating: cancel order)
```

**Pros:** Loose coupling, no single point of failure
**Cons:** Hard to track overall flow, harder to debug

---

### 2. Orchestration (Central coordinator)
A Saga Orchestrator tells each service what to do next.

```
         Saga Orchestrator
              │
    ┌─────────┼─────────┐
    ▼         ▼         ▼
Order Svc  Payment Svc  Inventory Svc

Orchestrator calls each step → on failure → calls compensating steps in reverse
```

**Pros:** Centralized flow, easy to monitor and debug
**Cons:** Orchestrator can become a bottleneck

---

## Compensating Transactions
Every step must have a "rollback" equivalent:

| Step | Forward | Compensating |
|------|---------|--------------|
| 1 | Create Order | Cancel Order |
| 2 | Charge Payment | Refund Payment |
| 3 | Reserve Inventory | Release Inventory |

---

## When to Use Saga

✅ Distributed transaction across multiple microservices
✅ Long-running business processes
✅ When 2PC is too heavy or not supported

❌ Don't use when a single DB transaction is possible
❌ Don't use for simple CRUD in one service

---

## Real World Examples
- **Uber:** Trip booking (match driver → charge card → start trip)
- **Amazon:** Order placement (payment → inventory → shipping)
- **Flipkart:** Checkout flow

---

## Saga vs 2PC

| | Saga | 2PC |
|--|------|-----|
| Consistency | Eventual | Strong |
| Availability | High | Lower (blocking) |
| Complexity | Medium | High |
| Failure handling | Compensating transactions | Rollback |
| Use case | Microservices | Single DB cluster |

---

## Interview Tip
> "We use Saga with orchestration when we need distributed coordination. Each step is idempotent so retries are safe. We use outbox pattern with Kafka to guarantee event delivery."
