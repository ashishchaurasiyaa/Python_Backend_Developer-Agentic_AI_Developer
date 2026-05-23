# Monolithic vs Microservices Architecture

## Quick Reference Card
```
Monolithic   → Ek hi codebase, ek hi deploy unit. Simple but hard to scale.
Microservices→ Alag alag services, independently deployable. Complex but scalable.
When Mono?  → Small team, startup, MVP, tight deadline
When Micro? → Large team, high scale, different scaling needs per module
Key trade-off → Simplicity vs Scalability + Operational complexity
Interview hook → "We migrated from PHP Laravel monolith to Django microservices at Youngman"
```

---

## PART 1: HINGLISH — Samjhne ke liye

### 1.1 Kya hai?

**Ek bakery ki kahani:**

**Monolithic** = Ek hi badi dukaan jisme sab kuch hota hai — bread banana, cake banana, delivery karna, accounts maintain karna. Sab ek hi room mein, ek hi team.

- Koi problem aayi bread oven mein → **puri dukaan band** karni padti hai
- Sirf oven wale section ko zyada log chahiye → **puri dukaan ka staff badhana padta hai**
- Code change karna hai → **sab cheez redeploy** hoti hai

**Microservices** = Alag alag counters — ek sirf bread ke liye, ek cake ke liye, ek delivery ke liye. Sab independent.

- Bread oven kharab → sirf bread counter band, **baaki chalta rahta hai**
- Delivery mein zyada load → sirf **delivery counter ke log badhao**
- Bread recipe change karo → sirf **bread service redeploy**

---

### 1.2 Monolithic — Deep Dive

```
┌─────────────────────────────────────────────┐
│              MONOLITHIC APP                 │
│                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │   User   │  │  Order   │  │ Payment  │  │
│  │  Module  │  │  Module  │  │  Module  │  │
│  └──────────┘  └──────────┘  └──────────┘  │
│                                             │
│  ┌──────────┐  ┌──────────┐                 │
│  │Inventory │  │Notifica- │                 │
│  │  Module  │  │  tions   │                 │
│  └──────────┘  └──────────┘                 │
│                    │                        │
│              Single DB                      │
└─────────────────────────────────────────────┘
         One Deploy → Everything together
```

**Pros:**
- Simple development — ek hi repo, ek hi deploy
- Easy debugging — sab ek jagah
- No network calls between modules — function call hi kaafi
- Less infrastructure — ek server pe sab

**Cons:**
- Ek bug → poora system down
- Ek module ko scale karna → pura app scale karna
- Team size badhne pe conflicts (merges, deployments)
- Different tech stack use nahi kar sakte per module
- Deploy cycle slow — chota sa change = puri rebuild

---

### 1.3 Microservices — Deep Dive

```
┌──────────┐   ┌──────────┐   ┌──────────┐
│   User   │   │  Order   │   │ Payment  │
│ Service  │   │ Service  │   │ Service  │
│  :8001   │   │  :8002   │   │  :8003   │
└────┬─────┘   └────┬─────┘   └────┬─────┘
     │              │              │
  User DB        Order DB      Payment DB
  (PostgreSQL)   (MongoDB)     (PostgreSQL)
     │              │              │
     └──────────────┴──────────────┘
                    │
             API Gateway / Load Balancer
                    │
                 Client
```

**Pros:**
- Independent deploy — sirf changed service deploy karo
- Independent scaling — payment service 10x scale, notification service 1x
- Technology freedom — Python, Go, Node — kuch bhi
- Fault isolation — ek service fail → baaki chalta hai
- Small teams own small services

**Cons:**
- Network latency — function call ki jagah HTTP/gRPC call
- Distributed transactions hard — 2-phase commit, saga pattern
- Service discovery complexity
- More infrastructure — Docker, Kubernetes, API Gateway
- Debugging harder — distributed tracing chahiye (Jaeger, Zipkin)
- Data consistency — har service ka apna DB

---

### 1.4 Transition Challenges (Real experience)

**Youngman ERP ka journey:**
```
Phase 1 (2022): PHP Laravel Monolith
  - Operations + Invoicing + CRM + Accounts → ek hi app
  - Problem: Invoicing heavy load pe poora CRM slow hota tha
  - Problem: Different modules different deploy speeds chahte the

Phase 2 (2023): Python Django Microservices
  - Operations Service → alag
  - Invoicing Service → alag (Celery + RabbitMQ async)
  - CRM/Odoo → alag
  - SAP Connector → alag service
  
Problem faced: Inter-service communication
  - Pehle: direct function call
  - Baad mein: REST APIs + Celery tasks (async events)
```

---

### 1.5 Kab kya choose karo?

```
Monolithic choose karo jab:
✓ Startup ya MVP (fast iteration chahiye)
✓ Team size < 5-6 developers
✓ Simple domain (zyada modules nahi)
✓ Budget limited (infrastructure cost)
✓ Proof of concept

Microservices choose karo jab:
✓ Team size > 10, multiple teams
✓ Different modules ka scaling need alag hai
✓ Different tech stacks needed
✓ High availability required (99.9%+)
✓ Domain clear aur stable hai (premature micro = disaster)
```

---

## PART 2: ENGLISH — Interviewer ko bolne ke liye

### 2.1 Definition

> **Monolithic Architecture**: A single deployable unit containing all application modules — UI, business logic, and data access — tightly coupled and sharing the same process and database.

> **Microservices Architecture**: An architectural style where an application is structured as a collection of small, independently deployable services, each running in its own process and communicating via lightweight APIs.

---

### 2.2 Key Differences Table

| Dimension | Monolithic | Microservices |
|-----------|-----------|---------------|
| Deployment | Entire app redeployed | Individual service redeployed |
| Scaling | Scale entire app | Scale specific service |
| Database | Shared single DB | Database per service |
| Communication | In-process function calls | Network calls (REST/gRPC/events) |
| Fault isolation | Single failure = total outage | Failure contained to service |
| Tech stack | Single language/framework | Polyglot (any language per service) |
| Team structure | Single team | One team per service |
| Debugging | Simple stack traces | Distributed tracing needed |
| Latency | No network overhead | Network hop per service call |
| Data consistency | ACID transactions easy | Eventual consistency, Saga pattern |

---

### 2.3 When to Use Each

**Monolithic is appropriate when:**
- Team size is small (< 8 engineers)
- Domain is not well-understood (high change rate)
- Time-to-market is the priority (startups, MVPs)
- The application is inherently low-scale

**Microservices are appropriate when:**
- Multiple teams need independent deploy cadences
- Individual components have vastly different scaling requirements
- High availability (> 99.9%) is required
- Domain is stable and bounded contexts are clear (DDD)

---

### 2.4 Service Communication Patterns

```
Synchronous (tight coupling):
  Service A → REST/gRPC → Service B (waits for response)
  Use: Real-time queries (check payment status)
  Risk: Service B down = Service A fails

Asynchronous (loose coupling):
  Service A → Message Queue → Service B (fire and forget)
  Use: Events (payment processed → send email)
  Benefit: Service B down = message waits, retried later

Example (Youngman):
  Invoice created → Celery task published to RabbitMQ
  → SAP HANA Connector consumes → pushes to SAP
  Invoice service doesn't wait for SAP response
```

---

### 2.5 Real Project Answer

> "At Y Equipment Services, I led the migration from a PHP Laravel monolith to Django microservices. The monolith had Operations, Invoicing, CRM, and Accounts all coupled together. The problem was that the invoicing module — processing Rs 50 Crore+ annually — had very different scaling and reliability needs from CRM. We broke it into separate services with Celery + RabbitMQ for async communication between them. The SAP HANA connector became a separate service entirely, isolating that external dependency. This let us deploy invoicing changes independently without touching CRM."

---

### 2.6 Common Follow-up Q&A

**Q1: How do you handle transactions that span multiple services?**
> "Saga Pattern. Two approaches: (1) Choreography — each service publishes events, others react. (2) Orchestration — a central saga orchestrator coordinates. Example: booking a safari — Booking Service creates draft, Payment Service charges, Inventory Service reduces availability. If payment fails, compensating transaction cancels the booking. We prefer choreography for simple flows and orchestration for complex multi-step flows."

**Q2: How do you debug issues that span multiple services?**
> "Distributed tracing — we assign a correlation_id (UUID) to every incoming request. This ID propagates through every service call via HTTP headers. Tools like Jaeger or Zipkin visualize the full request path. In our setup, we log the correlation_id in every service log, so a single grep on the ID gives the full journey."

**Q3: When is microservices a bad choice?**
> "Microservices are premature optimization for small teams. Martin Fowler calls it the 'microservices premium' — you pay the operational complexity cost upfront before reaping scaling benefits. The rule I follow: start monolithic, identify the bottlenecks under real load, then extract those specific services. Don't design microservices based on domain intuition alone."

**Q4: What is a Service Mesh?**
> "A service mesh (Istio, Linkerd) handles cross-cutting concerns — service discovery, load balancing, circuit breaking, mutual TLS — at the infrastructure level so application code doesn't have to. It adds a sidecar proxy (Envoy) next to every service instance. Useful when you have 50+ services. Overkill for < 10 services."

---

## Comparison: Monolithic → SOA → Microservices Evolution

```
Monolithic (1990s-2000s)
  └── Everything in one app

SOA — Service Oriented Architecture (2000s)
  └── Services communicate via ESB (Enterprise Service Bus)
  └── Heavy XML/SOAP — complex, enterprise-grade
  └── Shared database still common

Microservices (2010s-present)
  └── Lightweight REST/gRPC, no central bus
  └── Database per service
  └── Docker + Kubernetes for deployment
  └── CI/CD per service
```

---

## Interview Cheat Sheet

```
Monolithic:
- Single codebase, single deploy, shared DB
- Good for: startups, small teams, MVPs
- Problem: can't scale parts independently, one bug = all down

Microservices:
- Independent services, own DB, own deploy
- Good for: large teams, different scale needs, high availability
- Problem: network latency, distributed transactions, more infra

Key patterns:
- API Gateway: single entry point for clients
- Saga: distributed transactions
- Circuit Breaker: prevent cascade failures
- Event Sourcing: async inter-service communication

My project: PHP Laravel monolith → Django microservices
Reason: Invoicing vs CRM had different scaling + deploy needs
```
