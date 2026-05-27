# Lecture 2: Microservices Architecture Overview

> *"Microservices: building applications as a suite of small, independently deployable services."* — Martin Fowler

**Section 3 — Distributed Systems & Service Architectures**

---

## 🎯 Is Lecture Mein Kya Seekhenge?

- **What are microservices** — definition aur philosophy
- **Core characteristics** — single responsibility, autonomy, polyglot
- **Monolith vs Microservices** — detailed comparison
- **Deployment autonomy** — independent CI/CD pipelines
- **Organizational alignment** — Conway's Law in action
- **Technology diversity** — polyglot architecture
- **Communication patterns** — sync vs async
- **Observability** — logs, metrics, traces
- **Common challenges** — eventual consistency, debugging
- **When to use microservices** — decision criteria

---

## 1. What Are Microservices?

### Definition

**Microservices = An architectural style that structures an application as a collection of loosely-coupled, independently deployable services organized around business capabilities.**

### Visual

```
┌─────────────────────────────────────────────────────────────────┐
│                      MICROSERVICES SYSTEM                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐         │
│  │   Auth   │  │  Orders  │  │ Payments │  │ Shipping │         │
│  │  Service │  │  Service │  │  Service │  │  Service │         │
│  │          │  │          │  │          │  │          │         │
│  │  Auth DB │  │ Order DB │  │ Pay DB   │  │ Ship DB  │         │
│  └─────┬────┘  └─────┬────┘  └─────┬────┘  └─────┬────┘         │
│        │             │             │             │                │
│        └─────────────┴─────────────┴─────────────┘                │
│                 ↓                                                  │
│       Event Bus (Kafka) + Service Mesh (Istio)                    │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Key Idea — Independence

```
Each service is:
   ✓ Built independently
   ✓ Deployed independently  
   ✓ Scaled independently
   ✓ Owned independently (by a team)
   ✓ Has its own database
   ✓ Speaks via API (REST/gRPC/Events)
```

### Example — Netflix Architecture

```
🎬 Netflix has 700+ microservices:
   ├─ User Service          (account management)
   ├─ Recommendation Engine (ML-powered)
   ├─ Encoding Service      (video transcoding)
   ├─ Playback Service      (streaming)
   ├─ Billing Service       (subscription)
   ├─ Search Service        (content discovery)
   ├─ Profile Service       (user preferences)
   └─ ... 690+ more
```

---

## 2. Core Characteristics of Microservices

### Characteristic 1: Single Responsibility

```
Each service owns ONE bounded context.

Example:
   PaymentService → Only payments
   - Process payment
   - Refund
   - Payment history
   ✗ NOT: user management, shipping, etc.
```

### Characteristic 2: Autonomous Deployment

```
Service A can deploy WITHOUT touching Service B.

   Day 1: Deploy Order Service v1.2 → no impact on others
   Day 2: Deploy Payment Service v3.0 → only payment affected
   Day 3: Roll back Auth Service → only auth affected
```

### Characteristic 3: Polyglot Programming

```
Each team chooses best tools:

   Auth Service       → Go (high concurrency)
   ML Recommendations → Python (PyTorch ecosystem)
   Real-time Chat     → Node.js (event loop)
   Banking Core       → Java (enterprise stability)
   Analytics          → Scala (Spark compatible)
```

### Characteristic 4: Fault Isolation

```
One service crashes → Others keep working.

   Recommendation Service down?
   ✓ Browsing still works
   ✓ Purchase still works
   ✓ Just no recommendations (graceful degradation)
```

### Characteristic 5: Decentralized Data

```
Each service owns its database.

   ❌ ANTI-PATTERN: All services share one DB
   ✅ CORRECT: Each service has its own DB
   
   Order Service     → PostgreSQL
   User Service      → MongoDB
   Cache Service     → Redis
   Search Service    → Elasticsearch
   Audit Service     → Kafka + S3
```

### Characteristic 6: DevOps-Friendly

```
Built for automation:
   ✓ CI/CD pipelines per service
   ✓ Containerized (Docker)
   ✓ Orchestrated (Kubernetes)
   ✓ Infrastructure as Code (Terraform)
   ✓ Automated testing
   ✓ Feature flags
```

### The 12 Microservice Principles

```
 1. Single responsibility (bounded context)
 2. Independently deployable
 3. Decentralized data
 4. Built around business capability
 5. Polyglot-capable
 6. Stateless (or externalized state)
 7. Loosely coupled, highly cohesive
 8. Designed for failure
 9. Observable (logs/metrics/traces)
10. Automated CI/CD
11. Domain-driven design
12. Evolution-friendly
```

---

## 3. Monolith vs Microservices

### Detailed Comparison Table

```
┌──────────────────────┬─────────────────────┬─────────────────────┐
│  ASPECT               │  MONOLITH            │  MICROSERVICES      │
├──────────────────────┼─────────────────────┼─────────────────────┤
│  Codebase             │  Single repo         │  Multiple repos     │
│  Deployment           │  All or nothing      │  Per service        │
│  Scaling              │  Vertical mostly     │  Horizontal per svc │
│  Tech stack           │  Single language     │  Polyglot           │
│  Database             │  Single DB           │  DB per service     │
│  Communication        │  Function calls      │  Network calls      │
│  Fault impact         │  Whole app down      │  One service down   │
│  Team structure       │  Shared codebase     │  Per-service teams  │
│  Onboarding           │  Easy (one repo)     │  Hard (many repos)  │
│  Operational complex  │  Low                 │  Very high          │
│  Build time           │  Slow (large codebase│  Fast (small svc)   │
│  Testing              │  Easy unit/integ     │  Hard distributed   │
│  Refactoring          │  IDE-level           │  Coordinated        │
│  Release coordination │  Single release      │  Per-team release   │
└──────────────────────┴─────────────────────┴─────────────────────┘
```

### Visual Architecture

```
MONOLITH:
┌─────────────────────────────────────────────────────────┐
│                  monolith.jar                            │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Auth │ Orders │ Payments │ Inventory │ Shipping  │  │
│  │  ↓                                                 │  │
│  │  Single Database                                   │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
   ✓ Simple to deploy
   ✗ One bug crashes everything
   ✗ Can't scale parts independently

MICROSERVICES:
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│   Auth   │ │  Orders  │ │ Payments │ │ Shipping │
│ Container│ │ Container│ │ Container│ │ Container│
└──────────┘ └──────────┘ └──────────┘ └──────────┘
  Auth DB     Order DB     Pay DB       Ship DB
  
  ✓ Scale per service
  ✓ Fault isolation
  ✗ Operational complexity
  ✗ Distributed system challenges
```

### Real-World Example — Amazon

```
🛒 Amazon migration journey:

1995: Monolithic e-commerce site (Perl, Mason)
   • Single deployment took days
   • One bug = entire site down
   • Hard to add features

2002: SOA + Service-based architecture
   • Better but still ESB-centric

2010+: Microservices
   • 1000+ services
   • Each deploy in seconds
   • Independent teams
   • 99.999% uptime
```

---

## 4. Deployment Autonomy

### The Power of Independent Deployment

```
Old way (Monolith):
   Tuesday 2 AM: Big release
   ├─ Deploy entire monolith
   ├─ All teams sync
   ├─ One bad change = roll back everything
   └─ Downtime risk

New way (Microservices):
   Anytime, multiple times a day:
   ├─ Team A deploys Order Service v1.5
   ├─ Team B deploys Payment Service v3.2
   ├─ Team C rolls back Auth Service v2.4 → only auth affected
   └─ Zero downtime
```

### Deployment Strategies

```
┌───────────────────────────────────────────────────────────────┐
│  STRATEGY            │  HOW IT WORKS                           │
├──────────────────────┼─────────────────────────────────────────┤
│  Rolling Deploy      │  Replace instances gradually            │
│                      │  v1 → v1, v1, v2 → v1, v2, v2 → v2, v2 │
├──────────────────────┼─────────────────────────────────────────┤
│  Blue/Green          │  Two identical envs, switch traffic     │
│                      │  Blue=current, Green=new, swap router   │
├──────────────────────┼─────────────────────────────────────────┤
│  Canary Release      │  Send small % traffic to new version    │
│                      │  1% → 10% → 50% → 100%                  │
├──────────────────────┼─────────────────────────────────────────┤
│  Feature Flags       │  Deploy code, toggle features on/off    │
│                      │  No re-deploy needed for rollback       │
├──────────────────────┼─────────────────────────────────────────┤
│  Shadow Traffic      │  Send copy of prod traffic to new vsn   │
│                      │  Compare results without user impact    │
└──────────────────────┴─────────────────────────────────────────┘
```

### CI/CD Per Service

```
Order Service Repo
├── .github/workflows/ci.yml
│   ├─ Run tests
│   ├─ Build Docker image
│   ├─ Push to registry
│   └─ Deploy to K8s
└── (commits trigger deploy independently)

Payment Service Repo
├── .github/workflows/ci.yml
│   └─ (separate pipeline, no coupling)
```

---

## 5. Organizational Alignment

### Conway's Law

> *"Any organization that designs a system will produce a design whose structure mirrors the organization's communication structure."* — Melvin Conway, 1967

### Visual

```
ORGANIZATION STRUCTURE       →    SOFTWARE STRUCTURE

3 teams                      →    3 monoliths or 3 service groups
                                  
10 small autonomous teams    →    10 microservices

Big shared engineering team  →    Big monolith

Cross-functional product     →    End-to-end owned services
teams (devs+QA+ops+PM)
```

### Inverse Conway Maneuver

```
Want a microservices architecture?
   → Restructure your teams FIRST
   → Then build software to match

Don't try to retrofit microservices onto monolith team!
```

### Team Ownership Model

```
🎯 "You build it, you run it" - Werner Vogels (Amazon CTO)

Each microservice has a team that owns:
   ✓ Code
   ✓ Database
   ✓ Deployment
   ✓ Monitoring
   ✓ On-call
   ✓ Performance
   ✓ Security
   ✓ Documentation
```

### Two-Pizza Team Rule

```
🍕 If your team can't be fed by 2 pizzas, it's too big.
   = 6-10 people max per service team
   
This enforces:
   - Small teams
   - Clear ownership
   - Faster decisions
   - High autonomy
```

---

## 6. Polyglot Architecture

### Choose Best Tool for Each Job

```
┌──────────────────────────────────────────────────────────────┐
│  SERVICE             │  LANGUAGE  │  WHY                     │
├──────────────────────┼────────────┼──────────────────────────┤
│  API Gateway         │  Go        │  High concurrency        │
│  Auth Service        │  Rust      │  Memory safety, speed    │
│  User Service        │  Python    │  Rapid development       │
│  ML Recommender      │  Python    │  PyTorch/TensorFlow      │
│  Real-time Chat      │  Node.js   │  Event loop, WebSockets  │
│  Banking Core        │  Java      │  Enterprise stability    │
│  Analytics           │  Scala     │  Spark integration       │
│  Frontend            │  TypeScript│  Type safety, React      │
└──────────────────────┴────────────┴──────────────────────────┘
```

### Polyglot Databases

```
┌──────────────────────────────────────────────────────────────┐
│  USE CASE            │  DATABASE  │  WHY                     │
├──────────────────────┼────────────┼──────────────────────────┤
│  Transactions        │  PostgreSQL│  ACID, joins             │
│  Sessions/Cache      │  Redis     │  In-memory, fast         │
│  User profiles       │  MongoDB   │  Flexible schema         │
│  Product search      │  Elastic   │  Full-text search        │
│  Time-series         │  InfluxDB  │  Metrics-optimized       │
│  Social graph        │  Neo4j     │  Relationship queries    │
│  High-write          │  Cassandra │  Distributed writes      │
│  Object storage      │  S3/MinIO  │  Blob storage            │
└──────────────────────┴────────────┴──────────────────────────┘
```

### Trade-Offs

```
✓ Pros of polyglot:
   - Best tool per job
   - Team autonomy
   - Faster innovation
   - Performance optimization

✗ Cons of polyglot:
   - Skills fragmentation
   - More tooling to learn
   - Harder ops/support
   - DevOps complexity

→ Use polyglot WHEN justified, not just because you can.
```

---

## 7. Communication Patterns

### Synchronous Communication

```
┌──────────────────────────────────────────────────────────────┐
│              SYNCHRONOUS (Request-Response)                   │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  Service A ──── REST/gRPC ───► Service B                     │
│            ◄─── Response ─────                                │
│                                                               │
│  Use when:                                                    │
│  • Need immediate response                                    │
│  • Caller depends on result                                   │
│  • Simple Q&A interactions                                    │
│                                                               │
│  Risks:                                                       │
│  • Cascading failures                                         │
│  • Tight runtime coupling                                     │
│  • Latency amplification (A→B→C→D = sum of all)              │
└──────────────────────────────────────────────────────────────┘
```

### Protocols Comparison

```
┌──────────────────────────────────────────────────────────────┐
│  PROTOCOL    │  PERFORMANCE  │  USE CASE                     │
├──────────────┼───────────────┼───────────────────────────────┤
│  REST/HTTP   │  Good          │  Public APIs, simple CRUD    │
│  gRPC        │  Excellent     │  Internal services, streaming│
│  GraphQL     │  Good          │  Frontend BFF, flexible Q    │
│  WebSocket   │  Excellent     │  Real-time bidirectional     │
│  SOAP        │  Slow          │  Legacy, enterprise B2B      │
└──────────────┴───────────────┴───────────────────────────────┘
```

### Asynchronous Communication

```
┌──────────────────────────────────────────────────────────────┐
│              ASYNCHRONOUS (Event-Driven)                      │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  Service A ──► [Event Broker: Kafka/RabbitMQ] ──► Service B  │
│                              │                                │
│                              └────────────────► Service C    │
│                                                               │
│  Use when:                                                    │
│  • Fire-and-forget (e.g., send email)                        │
│  • Multiple consumers of same event                          │
│  • Long-running operations                                    │
│  • Need decoupling                                            │
│                                                               │
│  Benefits:                                                    │
│  • Better resilience                                          │
│  • Decoupled services                                         │
│  • Easy to add new consumers                                  │
└──────────────────────────────────────────────────────────────┘
```

### Event Patterns

```
1. EVENT NOTIFICATION
   "User signed up"
   → Multiple services react independently
   → Each consumer fetches details if needed

2. EVENT-CARRIED STATE TRANSFER
   "User signed up" + ALL user data in event
   → Consumers don't need to call back
   → Reduces coupling

3. EVENT SOURCING
   Store events as source of truth
   → Reconstruct state by replaying events
   → Full audit trail

4. CQRS (Command Query Responsibility Segregation)
   Separate write model from read model
   → Optimized reads + writes
   → Often paired with event sourcing
```

### Hybrid Pattern (Most Common)

```
Real systems use BOTH:

   Synchronous for:
   • User-facing requests
   • Data lookups
   • Authentication

   Asynchronous for:
   • Notifications
   • Background jobs
   • Cross-service updates
   • Analytics
```

---

## 8. Observability in Microservices

### The Three Pillars

```
┌──────────────────────────────────────────────────────────────┐
│   1. LOGS    │   2. METRICS   │   3. TRACES                   │
│              │                │                                │
│  What        │  How many?     │  Where did the                 │
│  happened?   │  How fast?     │  request go?                   │
│              │                │                                │
│  ELK stack   │  Prometheus    │  Jaeger / Zipkin               │
│  Loki        │  Grafana       │  OpenTelemetry                 │
│  Datadog     │  Datadog       │  AWS X-Ray                     │
└──────────────────────────────────────────────────────────────┘
```

### Logs

```
✓ Structured (JSON, not plain text)
✓ Include correlation ID
✓ Include trace ID
✓ Include service name
✓ Centralized aggregation (ELK, Loki, Splunk)
✓ Searchable

Example log entry:
{
  "timestamp": "2026-05-26T10:00:00Z",
  "level": "INFO",
  "service": "order-service",
  "trace_id": "a1b2c3d4",
  "span_id": "e5f6g7h8",
  "user_id": "12345",
  "message": "Order created",
  "order_id": "ORD-001"
}
```

### Metrics

```
Golden Signals (Google SRE):

1. LATENCY    → How long requests take
2. TRAFFIC    → Requests per second
3. ERRORS     → Error rate
4. SATURATION → Resource usage (CPU, memory)

RED method (for services):
   R - Rate
   E - Errors
   D - Duration

USE method (for resources):
   U - Utilization
   S - Saturation
   E - Errors
```

### Distributed Tracing

```
Trace ID propagates across all services:

Request comes in → API Gateway
   trace_id: abc123, span_id: 1
      ↓
   Order Service
   trace_id: abc123, span_id: 2 (parent: 1)
      ↓
   Inventory Service
   trace_id: abc123, span_id: 3 (parent: 2)
      ↓
   Payment Service
   trace_id: abc123, span_id: 4 (parent: 2)
```

### Visual Trace

```
Request: POST /orders
│
├─ [10ms] API Gateway
│  └─ [8ms] Auth check
│
├─ [25ms] Order Service
│  │
│  ├─ [12ms] Inventory Service
│  │  └─ [10ms] DB query
│  │
│  └─ [30ms] Payment Service
│     ├─ [5ms]  Fraud check
│     └─ [20ms] Gateway call
│
└─ Total: 67ms
```

### Tooling Stack

```
┌──────────────────────────────────────────────────────────────┐
│  PURPOSE       │  TOOLS                                       │
├────────────────┼──────────────────────────────────────────────┤
│  Logs          │  ELK, Loki, Datadog, Splunk                  │
│  Metrics       │  Prometheus + Grafana, Datadog, NewRelic     │
│  Traces        │  Jaeger, Zipkin, AWS X-Ray, Datadog APM      │
│  Alerting      │  PagerDuty, Opsgenie, Grafana Alerting       │
│  Dashboards    │  Grafana, Kibana, Datadog                    │
│  Standard      │  OpenTelemetry (vendor-neutral)              │
└────────────────┴──────────────────────────────────────────────┘
```

---

## 9. Common Challenges

### Challenge 1: Distributed System Complexity

```
Things that "just work" in monolith are HARD in microservices:

   - Function call             → Network call (slower, can fail)
   - Database transaction      → Saga pattern (eventually consistent)
   - Try/except                → Retries + circuit breakers + DLQ
   - Stack trace               → Distributed tracing
   - print() debugging         → Log correlation across services
   - localhost                 → Service discovery
```

### Challenge 2: Eventual Consistency

```
Monolith:
   BEGIN TRANSACTION
     UPDATE accounts SET balance = balance - 100 WHERE id = 1;
     UPDATE accounts SET balance = balance + 100 WHERE id = 2;
   COMMIT  -- atomic!

Microservices:
   1. Debit Account Service (Service A's DB)
   2. ... what if step 1 succeeded but step 2 fails?
   3. Credit Account Service (Service B's DB)
   
   → Need SAGA pattern
   → Need compensating transactions
   → Need outbox pattern
   → Eventually consistent
```

### Challenge 3: Distributed Debugging

```
Where is the bug?
   - Service A logs say "called B"
   - Service B logs say "didn't get anything"
   - Service C logs show errors
   - Service D took 30 seconds
   
Without distributed tracing → nightmare!
With distributed tracing → click trace, see everything.
```

### Challenge 4: Service Coordination

```
Service A v2.0 needs Service B v3.0 (new API)
   But Service C still calls Service B v2.0 (old API)
   
Solutions:
   ✓ Versioned APIs (/v1/, /v2/)
   ✓ Backward compatibility
   ✓ Consumer-driven contracts
   ✓ Schema registry (Kafka)
```

### Challenge 5: Developer Onboarding

```
New dev joins your team:

Monolith: "Clone this repo, run docker-compose up"
   → Productive in 1 day

Microservices: "Clone these 50 repos, set up these 20 databases,
                run these 30 services locally..."
   → Productive in 3-4 weeks

Solutions:
   ✓ Dev environments (Docker Compose, Tilt, Skaffold)
   ✓ Service catalog (Backstage)
   ✓ Mocked dependencies
   ✓ Run only needed services
   ✓ Cloud-based dev (Gitpod, Codespaces)
```

### Challenge 6: Operational Costs

```
Monolith: 1 deployment, 1 monitor, 1 on-call rotation

Microservices: N deployments, N monitors, N on-call rotations
                + service discovery
                + service mesh
                + API gateway
                + message broker
                + distributed tracing
                + container orchestration
                + ... many more

→ Need DevOps maturity!
→ Need automation!
```

---

## 10. When to Use Microservices

### ✅ Good Fit Indicators

```
✓ Large team (15+ engineers)
✓ Multiple teams working in parallel
✓ Need independent scaling
✓ Different parts have different requirements
✓ Frequent deployments (daily/hourly)
✓ Cloud-native infrastructure
✓ DevOps maturity exists
✓ Complex domain with clear boundaries
✓ Need polyglot tech
✓ Want fault isolation
```

### ❌ Bad Fit Indicators

```
✗ Small team (< 5 engineers)
✗ Early-stage product (still iterating)
✗ No DevOps capabilities
✗ Domain still unclear
✗ Simple CRUD application
✗ Tight latency requirements
✗ Can't justify operational cost
✗ "Microservices because resume-driven development"
```

### Decision Tree

```
START
  │
  ├─ Is your team < 10 people?
  │    YES → Monolith or Modular Monolith
  │    NO  → Continue
  │
  ├─ Do you have DevOps team/maturity?
  │    NO  → Start with Modular Monolith
  │    YES → Continue
  │
  ├─ Are domain boundaries clear?
  │    NO  → Start with Modular Monolith, learn first
  │    YES → Continue
  │
  ├─ Do different parts have different scale needs?
  │    YES → Microservices
  │    NO  → Modular Monolith might be enough
  │
  ├─ Multiple teams need independent deployment?
  │    YES → Microservices
  │    NO  → Modular Monolith
```

### Team Size Heuristic

```
Team Size      → Recommended Architecture
─────────────────────────────────────────
1-5            → Monolith
5-15           → Modular Monolith
15-30          → Modular Monolith + selective extraction
30-100         → Microservices (cell-based)
100+           → Microservices (mature)
```

---

## 11. Common Anti-Patterns

### Anti-Pattern 1: Distributed Monolith

```
🚨 The WORST of both worlds:

   ❌ Multiple services
   ❌ But deployed together
   ❌ But share database
   ❌ But sync chains everywhere
   ❌ Can't deploy independently

You get:
   - Complexity of distribution
   - Coupling of monolith
   - None of the benefits
```

### Anti-Pattern 2: Chatty Services

```
❌ One user action = 50 service calls

   GET /user/profile
   → User Service (1 call)
   → Address Service (1 call)
   → Phone Service (1 call)
   → Email Service (1 call)
   → Avatar Service (1 call)
   ... 45 more calls

Result: 5-second response time!

Solutions:
   ✓ Composition at API Gateway
   ✓ Service aggregator (BFF pattern)
   ✓ CQRS (denormalized read models)
   ✓ GraphQL with DataLoader
```

### Anti-Pattern 3: Nano-Services

```
❌ Splitting too small:

   - GetUserNameService
   - GetUserEmailService
   - GetUserPhoneService
   - UpdateUserNameService
   ... 50 services for one entity!

→ Operational nightmare
→ More network calls than logic
→ Hard to maintain

Rule: Service should own a meaningful business capability.
```

### Anti-Pattern 4: Shared Database

```
❌ Multiple services writing to same table:

   Service A → Users table
   Service B → Users table  (also writes!)
   Service C → Users table  (also writes!)

→ You're NOT decoupled
→ Schema changes break everyone
→ Just distributed coupling

✅ Each service owns its data, exposes via API.
```

### Anti-Pattern 5: Premature Microservices

```
❌ Day 1 of new product: "Let's build 20 microservices!"

Reality:
   - You don't know the domain yet
   - Boundaries will change
   - Refactoring across services is HARD
   - You'll waste months on infrastructure

✅ Start with modular monolith. Extract when you understand the domain.
```

---

## 12. Microservices Maturity Model

### 5 Levels of Maturity

```
LEVEL 1: DISTRIBUTED MONOLITH (most start here)
   ❌ Services deployed together
   ❌ Shared database
   ❌ Sync chains
   
LEVEL 2: BASIC MICROSERVICES
   ✓ Independent deployments
   ✓ Service per database
   ❌ Manual ops
   ❌ Limited observability
   
LEVEL 3: AUTOMATED MICROSERVICES
   ✓ CI/CD per service
   ✓ Container orchestration
   ✓ Centralized logging
   ❌ Limited resilience
   
LEVEL 4: RESILIENT MICROSERVICES
   ✓ Circuit breakers
   ✓ Distributed tracing
   ✓ Chaos engineering
   ✓ Auto-scaling
   
LEVEL 5: SELF-HEALING MICROSERVICES
   ✓ Predictive autoscaling
   ✓ Auto-rollback
   ✓ AI-powered alerts
   ✓ Self-tuning
```

---

## 13. Key Infrastructure Components

### What You Need

```
┌──────────────────────────────────────────────────────────────┐
│  COMPONENT             │  PURPOSE                              │
├────────────────────────┼───────────────────────────────────────┤
│  API Gateway           │  Single entry point, auth, routing    │
│  Service Discovery     │  Find service endpoints dynamically   │
│  Service Mesh          │  Service-to-service traffic mgmt      │
│  Container Runtime     │  Run services (Docker)                │
│  Orchestrator          │  Schedule containers (Kubernetes)     │
│  Message Broker        │  Async communication (Kafka)          │
│  Config Management     │  Centralized config (Consul)          │
│  Secrets Management    │  Store secrets (Vault)                │
│  Logging               │  Aggregate logs (ELK, Loki)           │
│  Metrics               │  Collect metrics (Prometheus)         │
│  Tracing               │  Distributed tracing (Jaeger)         │
│  CI/CD                 │  Build & deploy (GitHub Actions)      │
│  Container Registry    │  Store images (ECR, Docker Hub)       │
└────────────────────────┴───────────────────────────────────────┘
```

---

## 14. Summary — Key Takeaways

```
┌──────────────────────────────────────────────────────────────┐
│  ✅ Microservices = independently deployable, autonomous svc  │
│  ✅ Built around business capabilities                        │
│  ✅ Each service owns its data                                │
│  ✅ Polyglot-capable (best tool for the job)                  │
│  ✅ Fault-isolated (one service down ≠ all down)              │
│  ✅ Requires significant DevOps maturity                      │
│  ✅ Trade complexity for agility & scale                      │
│  ✅ Not always the right choice — modular monolith first      │
└──────────────────────────────────────────────────────────────┘
```

### The Microservices Manifesto

```
1. Build around business capabilities, not technical layers
2. Smart endpoints, dumb pipes (no ESB orchestration)
3. Decentralized data management
4. Design for failure
5. Evolutionary design
6. Infrastructure automation
7. You build it, you run it
8. Polyglot persistence
9. Observability is non-negotiable
10. Loose coupling, high cohesion
```

---

## 🎬 What's Next?

In **Lecture 3**, we'll explore the **Modular Monolith** — the underrated middle ground that's often a better starting point than full microservices. Plus migration strategies for evolving from one to the other.

> **Practical file:** [02_Practical_Hands_On.md](02_Practical_Hands_On.md)

---

## 📚 References

- *Building Microservices* — Sam Newman
- *Microservices Patterns* — Chris Richardson
- *Domain-Driven Design* — Eric Evans
- *Release It!* — Michael Nygard
- *Site Reliability Engineering* — Google
