# Lecture 5: Real-World Use Cases for Distributed Styles

> *"Architecture follows from understanding what we're actually building — and for whom."*

**Section 3 — Distributed Systems & Service Architectures**

---

## 🎯 Is Lecture Mein Kya Seekhenge?

- **Why distributed styles** — team, system, deployment perspectives
- **SaaS platforms** — evolution from monolith to distributed
- **Public API platforms** — Stripe, Twilio, Shopify pattern
- **Fintech architecture** — KYC, payments, fraud, ledger
- **E-commerce** — catalog, inventory, orders, recommendations
- **Social platforms** — feed, messaging, media, search
- **Real-world challenges** — latency, consistency, debugging
- **Production patterns** — Saga, Outbox, BFF, hybrid
- **Decision frameworks** — when to use what
- **Lessons learned** — from companies that did it right (and wrong)

---

## 1. Why Distributed Styles? (Three Perspectives)

### From Team Perspective

```
🧑‍🤝‍🧑 Teams want:
   ✓ Autonomy (decide their own tech, schedule)
   ✓ Ownership (build it, run it)
   ✓ Speed (no coordination overhead)
   ✓ Clear responsibilities

→ Distributed systems enable team independence
```

### From System Perspective

```
🖥 Systems need:
   ✓ Scalability (handle 10x growth)
   ✓ Resilience (one part fails, rest works)
   ✓ Performance (scale hot paths only)
   ✓ Global reach (low latency worldwide)

→ Distributed systems handle scale & failures
```

### From Deployment Perspective

```
🚀 Operations want:
   ✓ Independent releases (no big-bang deploys)
   ✓ Easy rollbacks (per service)
   ✓ Canary deployments (test in prod safely)
   ✓ Tech flexibility (right tool for the job)

→ Distributed systems enable continuous delivery
```

### The Trade-Off Reality

```
Distributed systems give:
   ✓ Team autonomy
   ✓ Scale per component
   ✓ Fault isolation
   ✓ Tech flexibility

But cost:
   ✗ Operational complexity (10x)
   ✗ Network latency
   ✗ Eventual consistency
   ✗ Debugging difficulty
   ✗ Higher infrastructure cost

→ Trade-off must be JUSTIFIED.
```

---

## 2. Use Case 1: SaaS Platform Evolution

### Typical SaaS Journey

```
YEAR 0 — MVP                YEAR 2 — Growing           YEAR 4 — Scaling
┌─────────────────┐         ┌─────────────────┐       ┌──────────────┐
│   Monolith      │         │ Modular         │       │ Microservices│
│   (5 devs)      │ ──────► │ Monolith        │ ────► │ + Modular    │
│                 │         │ (20 devs)       │       │ Monolith     │
│ Rails+Postgres  │         │ + extracted     │       │ (100+ devs)  │
│                 │         │ Billing svc     │       │              │
└─────────────────┘         └─────────────────┘       └──────────────┘
```

### What Drives the Evolution

```
At MVP:
   ✓ Focus on validation
   ✓ Quick iteration
   ✓ Small team
   → Monolith is ideal

At Growing Stage:
   ✓ Multiple teams forming
   ✓ Feature areas crystallizing
   ✓ Need clear boundaries
   → Modular monolith

At Scaling Stage:
   ✓ Independent scaling needed
   ✓ Different release cycles
   ✓ Multiple tech needs
   → Selective microservices
```

### Real Example: Shopify

```
2004: Single Rails monolith
2010: Began componentization within monolith
2015: Extracted high-load services (search, payments)
2020+: Most still monolithic + targeted services
       
Key insight: They DIDN'T rewrite as microservices.
They modularized monolith + extracted strategically.

Today: Handles BLACK FRIDAY with this architecture!
```

### Multi-Tenant Architecture Patterns

```
┌────────────────────────────────────────────────────────────┐
│  PATTERN              │  DESCRIPTION                        │
├───────────────────────┼─────────────────────────────────────┤
│  Shared everything    │  All tenants in same DB tables      │
│                       │  Cheap, simple, hard to isolate     │
├───────────────────────┼─────────────────────────────────────┤
│  Shared DB,           │  Each tenant gets own schema        │
│  separate schemas     │  Better isolation, more ops         │
├───────────────────────┼─────────────────────────────────────┤
│  Database per tenant  │  Each tenant gets own DB instance   │
│                       │  Best isolation, expensive          │
├───────────────────────┼─────────────────────────────────────┤
│  Hybrid               │  Small tenants share, large get own │
└───────────────────────┴─────────────────────────────────────┘
```

### Common SaaS Microservices

```
Common services in SaaS:
   ├─ User/Identity service       (multi-tenant aware)
   ├─ Billing/Subscription        (Stripe integration)
   ├─ Notification service        (email, SMS, push)
   ├─ Analytics service           (event processing)
   ├─ Audit/Compliance            (immutable logs)
   ├─ Reporting service           (heavy reads, async)
   ├─ Integration service         (webhooks, APIs)
   └─ Core business services      (varies by SaaS)
```

---

## 3. Use Case 2: Public API Platforms (Stripe, Twilio, Shopify)

### The "API as Product" Paradigm

```
These companies treat their APIs as the PRODUCT itself.

Stripe       → Payments API
Twilio       → Communications API
Shopify      → Commerce API
Plaid        → Banking API
Auth0        → Identity API
SendGrid     → Email API

Public devs are the users!
```

### Architecture Requirements

```
Public APIs demand:
   ✓ Ultra-high availability (99.99%+ SLA)
   ✓ Backward compatibility (forever)
   ✓ Rate limiting (per customer)
   ✓ Authentication (API keys, OAuth)
   ✓ Observability (per-customer usage)
   ✓ Developer experience (docs, SDKs)
   ✓ Versioning strategy
```

### Typical Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                   PUBLIC API PLATFORM                         │
│                                                                │
│  Developer's App                                               │
│       ↓                                                        │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  CDN / Edge Layer (CloudFront, Fastly)                  │  │
│  └─────────────────────────────────────────────────────────┘  │
│       ↓                                                        │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  API Gateway (Kong, AWS API Gateway)                    │  │
│  │  • Authentication (API keys)                            │  │
│  │  • Rate limiting per customer                           │  │
│  │  • Request validation                                   │  │
│  │  • Version routing (/v1, /v2)                          │  │
│  │  • Audit logging                                        │  │
│  └─────────────────────────────────────────────────────────┘  │
│       ↓                                                        │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  Service Mesh (Istio, Linkerd)                          │  │
│  │  • mTLS between services                                │  │
│  │  • Retries, timeouts                                    │  │
│  │  • Circuit breakers                                     │  │
│  └─────────────────────────────────────────────────────────┘  │
│       ↓                                                        │
│   ┌─────┴────┬─────────┬──────────┐                           │
│   ↓          ↓         ↓          ↓                            │
│ ┌────┐  ┌──────┐  ┌──────┐  ┌──────┐                          │
│ │Core│  │Webhk │  │Audit │  │ etc. │                          │
│ │ Svc│  │ Svc  │  │ Svc  │  │      │                          │
│ └────┘  └──────┘  └──────┘  └──────┘                          │
└──────────────────────────────────────────────────────────────┘
```

### Stripe's API Versioning Strategy

```
Stripe maintains backward compat for YEARS.

Versions are dated: 2024-04-15, 2024-03-01, etc.

Customer "pins" to a version:
   POST /v1/charges
   Stripe-Version: 2024-04-15

Stripe maintains:
   ✓ 50+ versions simultaneously
   ✓ Old APIs work indefinitely (mostly)
   ✓ Migration tools for upgrades
   ✓ Detailed changelogs

This is what API platforms must do.
```

### Idempotency for Public APIs

```python
# Customer's request
POST /v1/charges
Idempotency-Key: order_12345_charge
{
    "amount": 1000,
    "currency": "usd"
}

# If client retries with same key:
# Stripe returns the SAME response, doesn't double-charge

# Implementation:
async def create_charge(amount, currency, idempotency_key):
    if idempotency_key:
        cached = await cache.get(f"idempotency:{idempotency_key}")
        if cached:
            return cached  # Same response as before
    
    result = await process_charge(amount, currency)
    
    if idempotency_key:
        await cache.set(
            f"idempotency:{idempotency_key}",
            result,
            ttl=86400  # 24 hours
        )
    return result
```

---

## 4. Use Case 3: Fintech Architecture

### Why Fintech Is Different

```
Fintech = Real Money + Strict Regulations + Zero Tolerance for Errors

Requirements:
   ✓ Audit trail for EVERYTHING
   ✓ Idempotency (no double-charges)
   ✓ Strong consistency where it matters
   ✓ PCI-DSS compliance (cards)
   ✓ KYC/AML compliance (identity)
   ✓ Real-time fraud detection
   ✓ Disaster recovery (RPO < 1 min)
```

### Typical Fintech Service Topology

```
┌─────────────────────────────────────────────────────────────────┐
│              FINTECH MICROSERVICES TOPOLOGY                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│     Mobile/Web                                                    │
│         ↓                                                         │
│     API Gateway (Kong/Apigee)                                     │
│     • Auth • Rate limit • Audit                                   │
│         ↓                                                         │
│   ┌─────┴────┬─────────┬─────────┬──────────┬─────────┐         │
│   ↓          ↓         ↓         ↓          ↓         ↓          │
│ ┌────┐  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐        │
│ │KYC │  │Wallet│  │Payment│ │Fraud │  │Ledger│  │Notify│        │
│ │ Svc│  │ Svc  │  │ Svc   │ │ Svc  │  │ Svc  │  │ Svc  │        │
│ └─┬──┘  └──┬───┘  └──┬────┘ └──┬───┘  └──┬───┘  └──┬───┘        │
│   ↓        ↓         ↓         ↓         ↓         ↓             │
│  KYC      Wallet    Trans      Fraud    Ledger    Queue          │
│  DB       DB        DB         ML       DB (immutable)            │
│                                                                   │
│  Event Bus (Kafka) ←──── all services publish here ─────►        │
│                                                                   │
│  Compliance Layer:                                                │
│  • All services emit audit events                                 │
│  • Ledger is append-only (immutable)                              │
│  • PCI services in isolated network                               │
└─────────────────────────────────────────────────────────────────┘
```

### Core Fintech Services Deep Dive

#### KYC Service

```
Responsibilities:
   • Identity verification (Aadhaar, PAN in India)
   • Document upload & validation
   • Liveness checks (selfie)
   • Sanctions screening (OFAC, etc.)
   • PEP screening (Politically Exposed Persons)
   • Risk scoring

Tech:
   • External integrations (Onfido, Jumio, IDfy)
   • ML for document verification
   • Encrypted document storage
   
Compliance:
   • RBI KYC norms in India
   • CDD/EDD per customer risk tier
```

#### Wallet Service

```
Responsibilities:
   • Account balance management
   • Reserve funds for pending transactions
   • Handle multi-currency
   • Internal transfers

Critical:
   • Strong consistency (no money lost/duplicated!)
   • Idempotent operations
   • Double-entry bookkeeping
   
Schema:
   accounts (id, balance, available, reserved)
   transactions (id, account_id, amount, type, status)
   
Pattern: 
   For balance updates:
   ✗ NOT: SELECT then UPDATE (race condition!)
   ✓ USE: UPDATE accounts SET balance = balance - 100 WHERE id = ? AND balance >= 100
```

#### Payment Service

```
Responsibilities:
   • Integrate with payment gateways
   • Card / UPI / NEFT / IMPS processing
   • Refund handling
   • Reconciliation with banks

Pattern: Saga for distributed transactions
   1. Reserve funds (Wallet)
   2. Check fraud (Fraud)
   3. Process at gateway (External)
   4. Record in ledger (Ledger)
   5. Update wallet (Wallet)
   
   If any step fails → compensate previous steps
```

#### Fraud Detection Service

```
Responsibilities:
   • Real-time transaction scoring
   • Anomaly detection
   • Pattern matching
   • Blacklist management

Tech:
   • ML models (XGBoost, neural networks)
   • Real-time scoring (<100ms latency!)
   • Feature store (Redis, Feast)
   • Async batch jobs for retraining
   
Pattern:
   Sync call for real-time decisions
   Async events for batch analytics
```

#### Ledger Service (CRITICAL)

```
Responsibilities:
   • Immutable transaction log
   • Source of truth for money
   • Used for reconciliation, audits

Schema (append-only):
   CREATE TABLE ledger_entries (
       id BIGSERIAL PRIMARY KEY,
       transaction_id UUID NOT NULL,
       account_id UUID NOT NULL,
       amount NUMERIC(20,4) NOT NULL,
       direction CHAR(1) CHECK (direction IN ('D', 'C')), -- Debit/Credit
       created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
       -- NO updates allowed!
   );

Invariants:
   ✓ Every transaction has equal debits and credits
   ✓ Sum of all balances = 0
   ✓ Never delete, only add
```

### Saga Pattern for Payment Flow

```python
"""Payment saga with compensations"""
async def process_payment(order_id: str, user_id: int, amount: float):
    saga = Saga("payment")
    
    # Step 1: Reserve funds in wallet
    saga.add_step(
        action=lambda: wallet_service.reserve(user_id, amount),
        compensation=lambda r: wallet_service.cancel_reservation(r.reservation_id)
    )
    
    # Step 2: Fraud check
    saga.add_step(
        action=lambda: fraud_service.evaluate(user_id, amount),
        # No compensation needed - just a check
    )
    
    # Step 3: Charge via gateway
    saga.add_step(
        action=lambda: gateway.charge(amount),
        compensation=lambda r: gateway.refund(r.charge_id)
    )
    
    # Step 4: Record in ledger (immutable)
    saga.add_step(
        action=lambda: ledger_service.record(amount, user_id),
        compensation=lambda r: ledger_service.record_reversal(r.entry_id)
    )
    
    # Step 5: Confirm wallet deduction
    saga.add_step(
        action=lambda: wallet_service.confirm_deduction(user_id, amount),
        # No compensation - this is the last step
    )
    
    return await saga.execute()
```

### Real Companies: Indian Fintech

```
🏦 PhonePe
   • Microservices on AWS
   • Processes 5+ billion transactions/year
   • Kafka for event streaming

💳 Razorpay
   • API-first architecture
   • Independent service for each payment method
   • Real-time fraud detection

💰 Cred
   • Modular monolith with select services
   • Heavy focus on UX

📊 Zerodha
   • Hybrid: monolith + microservices
   • Real-time trading needs low latency
```

---

## 5. Use Case 4: E-Commerce Architecture

### Amazon-Style Service Map

```
┌──────────────────────────────────────────────────────────────────┐
│                  E-COMMERCE MICROSERVICES                         │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  Edge Layer:  CDN → WAF → API Gateway                             │
│                                                                    │
│  Core Services (READ-heavy):                                       │
│  • Catalog Service       → Elasticsearch + Redis cache            │
│  • Search Service        → Elasticsearch                          │
│  • Recommendation        → ML models + Redis                      │
│  • Reviews Service       → PostgreSQL + read replicas             │
│                                                                    │
│  Transactional Services (WRITE-heavy):                            │
│  • Cart Service          → Redis (TTL'd carts)                    │
│  • Order Service         → PostgreSQL + Kafka events              │
│  • Inventory Service     → DynamoDB (high write throughput)       │
│  • Payment Service       → PCI-isolated network                   │
│                                                                    │
│  Fulfillment Services (Async):                                     │
│  • Warehouse Service     → Kafka consumer                         │
│  • Shipping Service      → Carrier APIs                           │
│  • Tracking Service      → Real-time updates                      │
│                                                                    │
│  Support Services:                                                 │
│  • User Service          → PostgreSQL                             │
│  • Notification Service  → SMS/Email queue                        │
│  • Analytics Service     → Kafka → BigQuery                       │
└──────────────────────────────────────────────────────────────────┘
```

### Service Deep Dive

#### Catalog Service

```
Challenges:
   • Millions of products
   • Multi-language descriptions
   • Frequent updates
   • Fast lookups needed

Architecture:
   PostgreSQL (source of truth)
        ↓ (CDC)
   Elasticsearch (search index)
        ↓
   Redis (hot product cache)
   
   Read path: Redis → ES → PG
   Write path: PG → (Kafka) → ES + Redis invalidation
```

#### Inventory Service

```
Challenges:
   • Race conditions (last item!)
   • Multi-warehouse
   • Reservations (during checkout)
   • Returns/restocks

Architecture:
   DynamoDB or Postgres with strict locking
   
   Patterns:
   ✓ Optimistic locking with version numbers
   ✓ Reserved quantity tracking
   ✓ TTL on reservations (auto-release)
   ✓ Event sourcing for audit trail
```

#### Order Service

```
Order lifecycle states:
   PENDING → CONFIRMED → PAID → FULFILLED → SHIPPED → DELIVERED
                            ↓
                       CANCELLED → REFUNDED

Pattern: Saga + Event Sourcing
   Each state transition is an event
   Replay events to rebuild state
   Audit trail built-in
```

#### Recommendation Service

```
Hybrid approach:
   Real-time: Redis with pre-computed recommendations
   Batch: Spark jobs nightly to retrain models
   
   Multiple algorithms:
   • Collaborative filtering (people who bought X also bought Y)
   • Content-based (similar products)
   • Trending now
   • Personalized ranking
   
   Mix and rank at request time
```

### Real Companies

```
🛒 Amazon
   • 1000+ services
   • Custom service mesh (since before Istio existed)
   • DynamoDB for inventory

🛍 Flipkart
   • Migrated from monolith to microservices
   • Custom CDN
   • Heavy Kafka usage

🎁 Myntra
   • Microservices on Kubernetes
   • Personalization-heavy
   • Mobile-first
```

### Big Sale Day Patterns (Black Friday, Big Billion Days)

```
Pre-sale:
   ✓ Pre-warm caches
   ✓ Scale up infrastructure (10x normal)
   ✓ Disable expensive features (recommendations, etc.)
   ✓ Test failover scenarios

During sale:
   ✓ Aggressive caching (CDN, Redis)
   ✓ Queue-based checkout (avoid overload)
   ✓ Circuit breakers everywhere
   ✓ Real-time monitoring war room

Post-sale:
   ✓ Async order processing
   ✓ Batch updates
   ✓ Reconciliation runs
```

---

## 6. Use Case 5: Social Media Platforms

### Feed Generation Challenge

```
Twitter has 500M users.
Each writes a tweet.
Each follows 200 people.

If Alice tweets:
   → 200 people see it in their feed

If Justin Bieber tweets:
   → 100M+ people need to see it!

Two approaches:
   1. Push (fanout-on-write): Write to all followers' feeds
   2. Pull (fanout-on-read): Compute feed at read time
```

### Hybrid Push/Pull Model

```python
"""Twitter/Instagram-style feed generation"""

async def on_post_created(post):
    """When a user posts"""
    followers = await graph_service.get_followers(post.user_id)
    
    if len(followers) < 10000:
        # PUSH MODEL: Fan-out to all followers
        for follower_id in followers:
            await feed_cache.lpush(f"feed:{follower_id}", post.id)
    
    # For celebrities (>10k followers): don't push
    # Their followers will PULL at read time


async def get_feed(user_id):
    """When user opens app"""
    # Get pre-computed feed (from push model)
    cached_feed = await feed_cache.lrange(f"feed:{user_id}", 0, 100)
    
    # Get celebrities user follows
    celebrities = await graph_service.get_celebrity_following(user_id)
    
    # Pull recent posts from celebrities (read-time fanout)
    celebrity_posts = await post_service.get_recent_posts(celebrities)
    
    # Merge and rank with ML
    return await ranking_service.rank(cached_feed + celebrity_posts)
```

### Real-Time Messaging

```
Requirements:
   ✓ Low latency (<100ms)
   ✓ Bidirectional
   ✓ Persistent connections
   ✓ Presence indicators

Tech:
   • WebSockets (or HTTP/3)
   • Sticky session routing
   • Redis Pub/Sub for cross-server messages
   • Kafka for offline message persistence

Architecture:
   User → WebSocket Server → Redis Pub/Sub → Other WS Server → User
```

### Media Processing Pipeline

```
User uploads photo
        ↓
   Object Storage (S3)
        ↓
   Kafka event: "media.uploaded"
        ↓
   ┌────┴────┬─────────┬──────────┐
   ↓         ↓         ↓          ↓
Resize    Encode    Thumbnail  Moderation
Service   Service   Service    Service (ML)
   ↓         ↓         ↓          ↓
S3        S3        S3         Decision
   
   All async → user sees "Processing..." → notified when ready
```

### Search & Discovery

```
Indexes:
   • User search → Elasticsearch
   • Post search → Elasticsearch with custom analyzers
   • Hashtag trending → Redis sorted sets
   • Personalized → ML re-ranking

Real-time updates:
   Posts → Kafka → ES indexer (near-real-time)
   
Caching:
   Hot queries cached aggressively
   Personalized results not cached
```

### Real Companies

```
🐦 Twitter (now X)
   • 4500+ services
   • Custom fanout system
   • Manhattan distributed DB
   • Heavy Kafka

📷 Instagram
   • Python (Django) + microservices
   • Cassandra for feed
   • TAO graph storage

📘 Facebook
   • Hack/HHVM monolith + services
   • TAO + Cassandra
   • Real-time messaging
```

---

## 7. Common Real-World Challenges

### Challenge 1: Network Latency

```
Problem: Each network hop = 1-10ms
   10 hops = 10-100ms just on network!

Solutions:
   ✓ Aggressive caching (CDN, Redis)
   ✓ Reduce hops (API composition)
   ✓ Use co-location (same data center)
   ✓ Request batching
   ✓ HTTP/2 multiplexing
   ✓ gRPC for internal calls (faster than REST)
```

### Challenge 2: Eventual Consistency

```
Problem:
   You add to cart on Service A
   Service B doesn't see it yet (1 second later)

Acceptable in:
   ✓ Social media (post visible eventually)
   ✓ Analytics (numbers update soon)
   ✓ Search indexing

NOT acceptable in:
   ✗ Bank balance
   ✗ Inventory (overselling)
   ✗ Authentication

Solutions:
   ✓ Saga pattern
   ✓ Compensating transactions
   ✓ Outbox pattern
   ✓ CDC (Change Data Capture)
   ✓ Read-your-writes consistency
```

### Challenge 3: Distributed Debugging

```
Problem:
   User reports: "My order isn't going through"
   → Where is the issue? (50 services)

Solutions:
   ✓ Distributed tracing (Jaeger, Zipkin)
   ✓ Correlation IDs across all services
   ✓ Structured logging
   ✓ Centralized log aggregation
   ✓ Service dependency mapping
   ✓ Synthetic monitoring
```

### Challenge 4: Service Coordination

```
Problem:
   • Service A v2.0 needs Service B v3.0
   • But Service C still uses Service B v2.0
   • Coordinating deploys is HARD

Solutions:
   ✓ Backward-compatible APIs (mandatory!)
   ✓ Versioned endpoints (/v1, /v2)
   ✓ Consumer-driven contracts (Pact)
   ✓ Schema registry for events (Kafka Schema Registry)
   ✓ Feature flags
```

### Challenge 5: Onboarding Complexity

```
Problem: New engineer needs to:
   • Set up 50 services locally
   • Understand dependencies
   • Know on-call procedures
   
"Welcome to the team! Here's a 3-week setup guide..."

Solutions:
   ✓ Service catalog (Backstage)
   ✓ Docker Compose for local dev
   ✓ Cloud dev environments (Gitpod, Codespaces)
   ✓ Mocked dependencies
   ✓ Sandbox environments
   ✓ Detailed runbooks
```

---

## 8. Production Patterns Summary

### Pattern 1: API Gateway

```
Use for:
   • Single entry point
   • Auth/AuthZ
   • Rate limiting
   • Request routing
   • Protocol translation (HTTP → gRPC)

Tools: Kong, AWS API Gateway, Tyk, Apigee
```

### Pattern 2: Service Mesh

```
Use for:
   • Service-to-service traffic management
   • mTLS encryption
   • Retries, timeouts, circuit breakers
   • Observability
   • Traffic shifting (canary)

Tools: Istio, Linkerd, Consul Connect
```

### Pattern 3: Saga Pattern

```
Use for:
   • Distributed transactions
   • Multi-step business processes
   • Cross-service consistency

Types:
   • Orchestration (central coordinator)
   • Choreography (events drive flow)
```

### Pattern 4: Outbox Pattern

```
Use for:
   • Reliable event publishing
   • Avoiding lost events on crash
   • Atomic DB + Kafka writes

Implementation:
   1. Write event to outbox table (same TX as data)
   2. Separate publisher polls outbox
   3. Publish to Kafka
   4. Mark as published
```

### Pattern 5: BFF (Backend for Frontend)

```
Use for:
   • Different clients need different data
   • Mobile vs Web have different needs
   • Aggregate multiple services

Architecture:
   Web → Web BFF → Services
   Mobile → Mobile BFF → Services
   Each BFF tailored to its client
```

### Pattern 6: CQRS

```
Use for:
   • Read-heavy systems
   • Different read/write models
   • Performance optimization

Architecture:
   Writes → Write DB → Event Bus → Read DB (denormalized)
   Reads → Read DB only
```

### Pattern 7: Event Sourcing

```
Use for:
   • Audit trails (banking)
   • Time-travel queries
   • Complex business workflows

Idea:
   Store events, not state.
   Replay events to compute state.
```

---

## 9. Architecture Decision Framework

### When to Use What

```
┌────────────────────────────────────────────────────────────────┐
│  SITUATION                          │  ARCHITECTURE             │
├─────────────────────────────────────┼───────────────────────────┤
│  Building MVP, small team           │  Monolith                 │
│  Mid-stage, 10-20 devs              │  Modular Monolith         │
│  Multiple teams, scaling needs      │  Microservices            │
│  Legacy enterprise integration      │  SOA                      │
│  Cloud-native, new product          │  Microservices            │
│  Banking/Insurance core             │  SOA + Modular Monolith   │
│  Public API platform                │  Microservices            │
│  Mobile + Web frontend              │  Add BFFs                 │
│  Large frontend team                │  Micro-frontends          │
│  Real-time features                 │  Add WebSocket service    │
│  Async workloads                    │  Add event bus (Kafka)    │
│  Data analytics                     │  Add data pipeline        │
└─────────────────────────────────────┴───────────────────────────┘
```

### The Reality Check Questions

```
Before choosing microservices:

1. Do you have 10+ engineers?           → Yes/No
2. Do you have DevOps team?              → Yes/No
3. Do parts have different scale needs?  → Yes/No
4. Do you have observability tools?      → Yes/No
5. Is domain well-understood?            → Yes/No
6. Can you afford the operational cost?  → Yes/No

If 5+ "Yes" → Microservices makes sense
If 3-4 "Yes" → Modular monolith
If <3 "Yes" → Monolith
```

---

## 10. Hybrid Architectures (The Norm)

### Real Systems Are Usually Hybrid

```
Pure microservices is RARE.
Most systems are HYBRID:

┌─────────────────────────────────────────────────────────────┐
│                        Real System                           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Core App        Extracted Services      External           │
│  (Modular        (Microservices)         (SaaS)             │
│   Monolith)                                                  │
│                                                              │
│  ┌───────────┐   ┌─────────────┐         ┌───────────┐      │
│  │ Users     │   │ Search      │         │ Stripe    │      │
│  │ Orders    │   │ ML/Recs     │         │ SendGrid  │      │
│  │ Cart      │   │ Analytics   │         │ Twilio    │      │
│  │ Profile   │   │ Real-time   │         │ Algolia   │      │
│  └───────────┘   └─────────────┘         └───────────┘      │
│         ↓               ↓                      ↓             │
│         └───────────────┴──────────────────────┘             │
│                  Event Bus + API Gateway                     │
└─────────────────────────────────────────────────────────────┘

✓ Modular monolith for core (90% of code)
✓ Microservices for specialized needs (search, ML)
✓ External SaaS for commodity (payments, email)
```

### The Smart Approach

```
Don't be ideological:
   ✗ "Everything must be microservices!"
   ✗ "Monoliths are bad!"
   ✗ "We need event-driven everywhere!"

Be pragmatic:
   ✓ Right tool for each problem
   ✓ Start simple, add complexity when justified
   ✓ Measure before optimizing
   ✓ Solve actual problems, not imagined ones
```

---

## 11. Lessons Learned from the Field

### Lesson 1: Operational Cost Is Real

```
Story: A startup with 8 engineers built 20 microservices.

Result:
   • 80% time on infra, 20% on features
   • Constantly fighting outages
   • Couldn't ship features fast enough
   • Burned out, then pivoted to modular monolith
   
   Productivity 3x improvement after consolidation.

Lesson: Match architecture to team capacity.
```

### Lesson 2: Premature Distribution Hurts

```
Story: Company started with microservices from day 1.

Problems:
   • Domain boundaries WRONG (didn't understand yet)
   • Constant refactoring across services
   • Each refactor = multiple coordinated PRs
   • 6 months to ship a simple feature

Lesson: Understand domain BEFORE distributing.
```

### Lesson 3: Distributed Monolith Is Worst

```
Story: Migration from monolith to "microservices" went wrong.

What they did:
   ✗ Split into services
   ✓ But all deployed together
   ✓ Shared database
   ✓ Synchronous chains everywhere

Result:
   • Complexity of distribution
   • Coupling of monolith
   • Zero benefits

Lesson: Either fully commit or stay modular.
```

### Lesson 4: Observability Is Non-Negotiable

```
Story: Built microservices without proper observability.

When production issues:
   ✗ Couldn't tell which service was slow
   ✗ Couldn't trace requests
   ✗ Logs scattered everywhere
   ✗ Debugging took DAYS

Lesson: Set up tracing + metrics + logs BEFORE going distributed.
```

### Lesson 5: Conway's Law Always Wins

```
Story: Company restructured teams. Architecture followed.

   Old structure: Monolith team
   New structure: 5 product teams
   
   Within a year:
   - Code naturally split into 5 services
   - Even though no one mandated it
   
Lesson: If you want a different architecture, change team structure.
```

---

## 12. Final Decision Framework

### The Architecture Decision Tree

```
START
  │
  ├─ Team size?
  │    1-5    → Monolith
  │    5-20   → Modular Monolith
  │    20+    → Consider microservices
  │
  ├─ DevOps maturity?
  │    Low    → Stay simpler
  │    High   → Can handle distributed
  │
  ├─ Domain understanding?
  │    New    → Modular monolith (still discovering)
  │    Mature → Can extract microservices
  │
  ├─ Scaling needs?
  │    Uniform  → Monolith scales fine
  │    Variable → Extract hot paths
  │
  ├─ Compliance / Security?
  │    Strict → SOA or isolated services
  │    Normal → Any architecture
  │
  ├─ Frontend team size?
  │    Small  → Single SPA
  │    Large  → Consider micro-frontends
  │
  └─ Match architecture to YOUR situation,
     not what's trending on HackerNews.
```

---

## 13. Summary — Key Takeaways

```
┌──────────────────────────────────────────────────────────────┐
│  ✅ Distributed styles solve TEAM, SYSTEM, DEPLOY problems   │
│  ✅ SaaS evolves: Monolith → Modular → Selective Services    │
│  ✅ Public APIs need ultra-high availability + versioning    │
│  ✅ Fintech demands audit trail + strong consistency          │
│  ✅ E-commerce balances reads (heavy) vs writes (transactional│
│  ✅ Social platforms have unique scale challenges             │
│  ✅ Real challenges: latency, consistency, debugging, cost    │
│  ✅ Patterns: Saga, Outbox, BFF, CQRS, Event Sourcing         │
│  ✅ Most real systems are HYBRID (mix of styles)              │
│  ✅ Architecture follows team structure (Conway's Law)        │
└──────────────────────────────────────────────────────────────┘
```

### The Universal Rules

```
1. Start SIMPLE. Add complexity when needed.
2. Match architecture to TEAM scale.
3. Understand DOMAIN before distributing.
4. Observability is REQUIRED for distributed.
5. Eventual consistency is REAL, plan for it.
6. Distributed systems are HARDER, not better.
7. Patterns are TOOLS, not religions.
8. Pragmatism beats purism.
9. Measure, then decide.
10. Most systems end up HYBRID — that's okay!
```

---

## 🎬 What's Next?

This concludes **Section 3: Distributed Systems & Service Architectures**!

You now understand:
- ✅ Service-Oriented Architecture (SOA)
- ✅ Microservices Architecture
- ✅ Modular Monoliths & Migration
- ✅ Micro-frontends & UI Composition
- ✅ Real-world use cases and patterns

In the **next section**, you'll dive into specific **integration patterns** — how distributed services actually communicate, coordinate, and stay consistent.

> **Practical file:** [05_Practical_Hands_On.md](05_Practical_Hands_On.md)

---

## 📚 References

- *Building Microservices* — Sam Newman
- *Microservices Patterns* — Chris Richardson
- *Designing Data-Intensive Applications* — Martin Kleppmann
- *The DevOps Handbook* — Gene Kim et al.
- *Domain-Driven Design* — Eric Evans
- AWS / GCP / Azure architecture case studies
- Netflix, Uber, Spotify, Shopify engineering blogs
