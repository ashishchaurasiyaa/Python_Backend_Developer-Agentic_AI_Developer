# Lecture 1: Event-Driven Architecture Basics

> *"Events are the facts of your system. They are not requests, not commands — just declarations: this happened."*

**Section 6 — Event-Driven & Reactive Systems**

---

## 🎯 Is Lecture Mein Kya Seekhenge?

- **What is Event-Driven Architecture (EDA)?**
- **What is an event?** — anatomy & properties
- **Events as first-class citizens**
- **Asynchronous flow** — producer-consumer decoupling
- **Pub/Sub model** — broadcast pattern
- **Event brokers** — Kafka, RabbitMQ
- **Event contracts** — schema + versioning
- **Auditability & event logs**
- **Benefits & trade-offs**
- **Common use cases**

---

## 1. Introduction to Event-Driven Architecture

### Definition

**EDA = A software design paradigm where systems communicate via events instead of direct calls.**

### Visual

```
                          ┌──────────────────┐
              OrderPlaced │ Inventory Svc    │
              ┌──────────►│                  │
              │           └──────────────────┘
              │
              │           ┌──────────────────┐
   ┌──────────┴─┐ PaymentReceived │ Billing Service  │
   │ Event Bus  │──────────►│                  │
   │            │           └──────────────────┘
   └──────────┬─┘
              │           ┌──────────────────┐
              │ OrderPlaced + PaymentReceived│ Notification│
              └──────────►│ Service          │
                          └──────────────────┘
```

### Core Properties

```
✓ Loose coupling
   Producer doesn't know who consumes events
   Consumers can change without affecting producer

✓ High scalability
   Components operate + scale independently

✓ Asynchronous communication
   Producer emits → moves on (no waiting)
```

### Why It Matters Today

```
Modern systems = distributed + cloud-native
   • Many services
   • Need to scale parts independently
   • Need to evolve without coordination
   • Need fault isolation

→ EDA fits naturally
```

---

## 2. What Is an Event?

### Definition

**An event represents a significant state change — something noteworthy that HAS HAPPENED.**

### Anatomy

```
┌─────────────────────────────────────────────┐
│  Event Object                                │
├─────────────────────────────────────────────┤
│  eventType:  UserSignedUp                    │
│  data:       userId=123, name=Ashish         │
│  timestamp:  2026-07-02T09:00:00Z            │
│  source:     AuthService                     │
│  eventId:    evt-abc123                      │
│  version:    v1                              │
└─────────────────────────────────────────────┘
```

### Key Properties

```
✓ IMMUTABLE
   Once created, never changes
   Reliable for auditing, debugging, replay

✓ DESCRIPTIVE
   Captures WHAT happened (past tense!)
   "OrderPlaced", "PaymentReceived"
   NOT "PlaceOrder" (that's a command)

✓ METADATA-RICH
   Unique ID, timestamp, source service
   Provides context for downstream consumers
```

### Events vs Commands vs Queries

```
┌──────────┬────────────────────┬─────────────────────────────┐
│  TYPE    │  TENSE              │  EXAMPLE                    │
├──────────┼────────────────────┼─────────────────────────────┤
│ Command  │  Imperative         │  "PlaceOrder" (will happen) │
│ Query    │  Question           │  "GetOrder" (give me data)  │
│ Event    │  Past tense (FACT)  │  "OrderPlaced" (happened)   │
└──────────┴────────────────────┴─────────────────────────────┘
```

### Mental Model

```
Events are FACTS about your system.
   ✗ Not requests
   ✗ Not commands
   ✗ Not promises
   ✓ Just declarations: "This thing happened."
```

---

## 3. Events as First-Class Citizens

### What That Means

```
In EDA, events aren't just signals.
They are CORE entities in the system:
   ✓ Stored
   ✓ Versioned
   ✓ Replayable
   ✓ Central to design (not byproducts!)
```

### Visual

```
   OrderPlaced ──────► Inventory
        │
        └────────────► Notifications

   PaymentReceived ──► Notifications
        │
        └────────────► Billing
   
   OrderShipped ─────► Notifications
        │
        └────────────► Shipping
```

### Power of First-Class Events

```
1. Event log = system memory
   Reconstruct state from events
   Time-travel debugging

2. Audit trail built-in
   Every change recorded
   Compliance + forensics ready

3. Easy to add consumers
   New service? Just subscribe to existing event
   Producer untouched

4. Loose coupling enforced
   Services interact through events, not APIs
```

### Different From Traditional Architecture

```
Traditional:
   Service A → calls → Service B → calls → Service C
   ✗ Tight coupling
   ✗ Synchronous chains
   ✗ Hard to evolve

Event-Driven:
   Service A → emits event
   Service B, C, D... all react independently
   ✓ Loose coupling
   ✓ Asynchronous
   ✓ Easy to evolve
```

---

## 4. Asynchronous Flow

### How It Works

```
   ┌──────────┐                              ┌──────────┐
   │ Producer │ ──► emit "OrderPlaced" ────►│  Event   │
   │ (Order   │                              │  Bus     │
   │  Service)│                              │          │
   └──────────┘                              └────┬─────┘
       │                                            │
       │ Continues immediately                      │ distributes
       │ (no waiting!)                              │ to consumers
       ▼                                            ▼
   Next task                            ┌──────────────┐
                                        │ Many         │
                                        │ Consumers    │
                                        │ each at own  │
                                        │ pace         │
                                        └──────────────┘
```

### Key Benefits

```
✓ PRODUCER doesn't block
   Emits event → continues
   No waiting for consumers

✓ CONSUMERS work independently
   Inventory updates stock right away
   Email sends notification 5 sec later
   Each operates at own pace

✓ TIME DECOUPLING
   Producer + consumers don't need to be online together
   Queue stores until consumer ready

✓ SCALABILITY
   Add more consumer instances for load
   Producer untouched

✓ SPIKE ABSORPTION
   Traffic burst? Queue buffers
   No cascading failures
```

### Example: User Signs Up

```
SYNCHRONOUS WAY (BAD):
   User clicks signup →
      AuthService.create()
        ↓ (waits)
      EmailService.send_welcome()
        ↓ (waits)
      AnalyticsService.log()
        ↓ (waits)
      LoyaltyService.create_account()
        ↓
   User finally sees success (5 seconds!)

ASYNCHRONOUS WAY (GOOD):
   User clicks signup →
      AuthService.create() →
      emit "UserSignedUp" event →
      User sees success (200ms)
   
   Then in background:
      EmailService reacts → send welcome email
      AnalyticsService reacts → log event
      LoyaltyService reacts → create points account
```

---

## 5. Publish-Subscribe (Pub/Sub) Model

### The Core Pattern

```
   Producer
       │
       │ publish("OrderPlaced", {...})
       ▼
   ┌────────────────────────┐
   │     TOPIC: orders       │
   │   (broker / event bus)  │
   └─┬────────┬────────┬─────┘
     │        │        │
     ▼        ▼        ▼
   Subscriber Subscriber Subscriber
   (each gets copy of event)
```

### Key Properties

```
✓ PUBLISHER doesn't know subscribers
✓ ONE event → MANY consumers
✓ Each subscriber gets COPY
✓ Topics organize events
✓ Subscribers can join/leave without affecting publisher
```

### Radio Broadcast Analogy

```
📻 Radio station broadcasts on 99.5 FM
   ✓ Doesn't know who's listening
   ✓ Anyone with right channel can tune in
   ✓ Add new listener? Just turn on their radio
   ✓ Listener doesn't affect broadcaster
```

### Real Example

```
Topic: order.placed

Subscribers:
   ✓ InventoryService (updates stock)
   ✓ EmailService (sends confirmation)
   ✓ AnalyticsService (tracks revenue)
   ✓ LoyaltyService (awards points)
   ✓ RecommendationService (updates user model)

→ Producer fires ONE event
→ ALL react independently
→ Add new consumer? Just subscribe.
```

---

## 6. Event Brokers

### What They Do

**Specialized middleware that routes events between producers and consumers.**

### Responsibilities

```
✓ Receive events from producers
✓ Store them durably (don't lose!)
✓ Route to right consumers
✓ Handle retries on failure
✓ Track consumer offsets
✓ Provide ordering guarantees
✓ Enable replay
```

### Visual

```
   ┌──────────┐               ┌────────────┐
   │ Producer │ ──── emit ───►│  Event     │ ──── Consumer A
   └──────────┘               │  Broker    │
                              │            │ ──── Consumer B
   ┌──────────┐               │  ✓ Routes  │
   │ Producer │ ──── emit ───►│  ✓ Stores  │ ──── Consumer C
   └──────────┘               │  ✓ Retries │
                              │  ✓ Replays │ ──── Consumer D
   ┌──────────┐               │            │
   │ Producer │ ──── emit ───►│            │
   └──────────┘               └────────────┘
```

### Popular Brokers

```
┌──────────────────┬──────────────────────────────────────┐
│  BROKER           │  STRENGTHS                            │
├──────────────────┼──────────────────────────────────────┤
│  Apache Kafka     │  Streaming, high throughput, replay   │
│  RabbitMQ         │  Task queues, complex routing         │
│  AWS Kinesis      │  Streaming on AWS                     │
│  Google Pub/Sub   │  Managed, scalable                    │
│  AWS SNS/SQS      │  Pub/Sub + Queue on AWS               │
│  Apache Pulsar    │  Both queue + stream                  │
│  NATS             │  Lightweight, low-latency             │
│  Redis Streams    │  In-memory, simple                    │
└──────────────────┴──────────────────────────────────────┘
```

---

## 7. Event Contracts

### What Is It?

**A defined SCHEMA that specifies the exact structure of an event.**

### Why It Matters

```
Without contracts:
   ✗ Producer changes event format
   ✗ Consumers break
   ✗ Mismatches cause errors
   ✗ Data loss possible

With contracts:
   ✓ Shared understanding
   ✓ Versioning supported
   ✓ Backward compatibility
   ✓ Safe evolution
```

### Example Schema

```json
{
  "eventType": "OrderPlaced",
  "version": "1.2",
  "schema": {
    "eventId": "string (uuid)",
    "timestamp": "string (ISO 8601)",
    "source": "string",
    "data": {
      "orderId": "string",
      "userId": "integer",
      "items": [
        {
          "sku": "string",
          "quantity": "integer",
          "price": "number"
        }
      ],
      "total": "number",
      "currency": "string (3-letter code)"
    }
  }
}
```

### Versioning Strategies

```
1. SEMANTIC VERSIONING
   v1.0 → v1.1 (add optional field, backward compatible)
   v1.0 → v2.0 (breaking change, separate events)

2. ADDITIVE CHANGES (recommended)
   ✓ Add new optional fields
   ✓ Deprecate old fields gradually
   ✗ Never remove or rename existing fields

3. SEPARATE EVENT TYPES
   OrderPlaced.v1
   OrderPlaced.v2
   Producers may emit both during transition
```

### Schema Registry

```
Centralized place to manage schemas:
   ✓ Confluent Schema Registry (Kafka)
   ✓ AWS Glue Schema Registry
   ✓ Apicurio
   
   Producers validate before emit
   Consumers validate before consume
   Detects breaking changes early
```

---

## 8. Event Log & Auditability

### Event Log = System's Memory

```
Every event is recorded.
Append-only.
Timestamped.
Versioned.

Time →
   evt-001: UserSignedUp (Ashish, t=0)
   evt-002: OrderPlaced (#001, t=10)
   evt-003: PaymentReceived (#001, t=11)
   evt-004: OrderShipped (#001, t=120)
   evt-005: OrderDelivered (#001, t=2000)
```

### What This Enables

```
✓ COMPLETE AUDIT TRAIL
   "Who did what when?"
   Answer is ALWAYS in the log

✓ DEBUGGING
   Replay events to reproduce issues
   "What was the state when bug occurred?"

✓ COMPLIANCE
   Required for GDPR, SOX, etc.
   Immutable + traceable

✓ TIME-TRAVEL DEBUGGING
   Reconstruct any past state

✓ ANALYTICS
   Rich historical data
   Train ML models on event history
```

### Where Events Are Stored

```
✓ Kafka topics (with long retention)
✓ EventStoreDB (purpose-built event store)
✓ AWS Kinesis Data Streams
✓ PostgreSQL append-only tables
✓ S3 / object storage for archival
```

---

## 9. Key Benefits of EDA

### Benefit 1: Loose Coupling

```
Services communicate via events, not direct calls.
   ✓ No tight binding to specific endpoints
   ✓ Each service evolves independently
   ✓ Replace one service without touching others
```

### Benefit 2: Scalability

```
✓ Add consumer instances horizontally
✓ Producer untouched
✓ Each service scales by own load
✓ Spike absorption via queues
```

### Benefit 3: Real-Time Responsiveness

```
Events propagate quickly:
   ✓ Live dashboards update instantly
   ✓ Notifications sent in real-time
   ✓ Workflows trigger immediately
   ✓ Better UX
```

### Benefit 4: Fault Tolerance

```
✓ One consumer fails → others keep running
✓ Broker buffers events during outage
✓ Consumer recovers → catches up
✓ No cascading failures
```

### Benefit 5: Extensibility

```
New requirement? Add new consumer.
   ✓ No changes to producers
   ✓ No changes to existing consumers
   ✓ Easy A/B testing of new behavior
```

---

## 10. Challenges & Trade-Offs

### Challenge 1: Event Flow Complexity

```
Hard to trace event flows across services:
   ✗ Where did this event come from?
   ✗ Who else handled it?
   ✗ Is the workflow done?

Mitigations:
   ✓ Distributed tracing (Jaeger, Zipkin)
   ✓ Correlation IDs in every event
   ✓ Centralized logging
   ✓ Event flow visualization tools
```

### Challenge 2: Ordering & Duplicates

```
Events may arrive:
   ✗ Out of order
   ✗ More than once (at-least-once delivery)

Consumer must handle:
   ✓ Idempotency (safe duplicate processing)
   ✓ Eventual consistency (not real-time)
   ✓ Partition keys for ordering when needed
```

### Challenge 3: Schema Evolution

```
Events are immutable → schemas must be evolved carefully

Without discipline:
   ✗ Breaking changes silently break consumers
   ✗ Old events incompatible with new code

Mitigations:
   ✓ Schema registry
   ✓ Backward-compatible changes only
   ✓ Versioned events
   ✓ Up-casters for old events
```

### Challenge 4: Debugging is Harder

```
Linear stack traces gone:
   ✗ Where did this event flow?
   ✗ Why didn't this consumer process it?

Mitigations:
   ✓ Distributed tracing
   ✓ Dead letter queues for failures
   ✓ Replay capability
   ✓ Comprehensive logging
```

### Challenge 5: Operational Overhead

```
EDA requires infrastructure:
   ✗ Brokers to manage
   ✗ Schema registry
   ✗ Monitoring stack
   ✗ Consumer scaling
```

---

## 11. Common Use Cases

### Use Case 1: User Activity Tracking

```
Events:
   ✓ ProductViewed
   ✓ ButtonClicked
   ✓ PageNavigated
   ✓ SearchPerformed

Consumers:
   ✓ Analytics (clickstream)
   ✓ Personalization (recommendations)
   ✓ A/B testing
   ✓ Heatmaps
```

### Use Case 2: Real-Time Analytics & Dashboards

```
Events feed live data streams:
   ✓ Stock prices
   ✓ Order volume
   ✓ System health
   ✓ Sales by region

Tools:
   ✓ Kafka → Kafka Streams / Flink
   ✓ Materialized views
   ✓ WebSockets to UI
```

### Use Case 3: Microservices Coordination

```
Loosely-coupled service workflows:
   OrderPlaced
      → Inventory reserves stock
      → Billing charges card
      → Shipping schedules pickup
      → Email sends confirmation
      → Loyalty awards points
```

### Use Case 4: Notification & Alerting

```
Events trigger notifications:
   ✓ ErrorLogged → PagerDuty alert
   ✓ OrderShipped → SMS to customer
   ✓ AccountLocked → Email to security
   ✓ PaymentFailed → Notify user
```

### Use Case 5: Data Integration

```
Event-driven ETL:
   ✓ App events → Kafka
   ✓ Kafka → Data warehouse
   ✓ Real-time data lake
   ✓ Decouple operational + analytical systems
```

### Use Case 6: IoT & Sensor Data

```
High-volume telemetry:
   ✓ Devices emit events
   ✓ Stream processing aggregates
   ✓ Anomaly detection
   ✓ Real-time dashboards
```

---

## 12. EDA Anti-Patterns

### Anti-Pattern 1: Events as RPC

```
❌ Emitting "GetUserData" event and waiting for response

→ This is request-reply, not events!
→ Use proper RPC (gRPC, REST) for this
```

### Anti-Pattern 2: Events Replacing All APIs

```
❌ Everything is async events, no sync APIs

Problem:
   ✗ Login needs immediate yes/no
   ✗ Read-your-writes consistency lost
   ✗ Bad UX for user-facing flows

✓ Use mix: sync for user actions, async for background
```

### Anti-Pattern 3: Event Bloat

```
❌ Putting entire object graphs in events

Result:
   ✗ Large messages
   ✗ Slow broker
   ✗ Stale data when consumed

✅ Events carry IDs + minimal context
✅ Consumers fetch fresh data if needed
```

### Anti-Pattern 4: Implicit Coupling Through Events

```
❌ "Consumer X must run BEFORE Consumer Y"
❌ Tight ordering assumptions

→ Defeats decoupling benefit
✅ Each consumer independent
✅ If you need orchestration, use explicit Saga
```

### Anti-Pattern 5: No Schema Discipline

```
❌ Free-form events, changed arbitrarily

Result:
   ✗ Consumers break silently
   ✗ Data quality issues

✅ Schema registry + versioning + tests
```

---

## 13. EDA vs Other Architectures

### EDA vs Request-Response

```
Request-Response (REST/gRPC):
   ✓ Immediate response
   ✓ Simple to reason
   ✗ Tight coupling in time
   ✗ Cascading failures

EDA:
   ✓ Loose coupling
   ✓ Resilient
   ✗ Eventual consistency
   ✗ Complex debugging
```

### EDA vs Pure Async Queues

```
Async Queues (point-to-point):
   ✓ Task distribution
   ✓ Worker pool pattern
   - One message → one consumer
   
EDA (pub/sub):
   ✓ One event → many consumers
   ✓ Better for fanout
   ✓ Broader use cases
```

### Hybrid Architectures (Most Common)

```
Real systems use BOTH:
   ✓ Sync APIs for user-facing requests
   ✓ Events for cross-service coordination
   ✓ Events for background workflows
   ✓ Events for data integration
```

---

## 14. EDA Maturity Levels

### Level 1: Basic Events

```
Some pub/sub usage:
   ✓ Notifications
   ✓ Background jobs
   - Most code still sync
```

### Level 2: Event-Centric Design

```
Many features built on events:
   ✓ Domain events emitted
   ✓ Multiple consumers
   ✓ Loose coupling improves
```

### Level 3: Mature Event-Driven

```
Event-first thinking:
   ✓ Schemas managed
   ✓ Event log preserved
   ✓ Replay capability
   ✓ Distributed tracing
```

### Level 4: Event Sourcing + CQRS

```
Events are the source of truth:
   ✓ All state derived from events
   ✓ Read/write separation
   ✓ See Lecture 2!
```

---

## 15. Summary — Key Takeaways

```
┌──────────────────────────────────────────────────────────────┐
│  ✅ EDA = software design around events                        │
│  ✅ Events = immutable facts about state changes               │
│  ✅ Past tense, descriptive, with metadata                     │
│  ✅ Pub/Sub: one event → many consumers                        │
│  ✅ Brokers (Kafka, RabbitMQ) route & store events             │
│  ✅ Event contracts ensure compatibility                       │
│  ✅ Event log = audit trail + replay capability                │
│  ✅ Benefits: loose coupling, scalability, resilience          │
│  ✅ Challenges: complexity, ordering, schema evolution         │
│  ✅ Use cases: real-time, microservices, analytics             │
└──────────────────────────────────────────────────────────────┘
```

### The Universal Rules

```
1. Events are FACTS, not requests
2. Use past tense for event names
3. Make events IMMUTABLE
4. Include metadata (ID, timestamp, source)
5. Define schemas + version them
6. Design consumers to be IDEMPOTENT
7. Track events in centralized log
8. Use distributed tracing for visibility
9. Combine sync + async pragmatically
10. EDA is foundation for advanced patterns (CQRS, ES, Sagas)
```

---

## 🎬 What's Next?

In **Lecture 2**, we'll explore **Event Sourcing and CQRS** — patterns that take event-driven thinking to the next level, making events the source of truth and separating reads from writes.

> **Practical file:** [01_Practical_Hands_On.md](01_Practical_Hands_On.md)

---

## 📚 References

- *Event-Driven Architecture* — Hugh Taylor
- *Designing Event-Driven Systems* — Ben Stopford (free Confluent eBook)
- *Domain-Driven Design* — Eric Evans (events as DDD building blocks)
- Martin Fowler's articles on event-driven patterns
- Kafka, RabbitMQ documentation
