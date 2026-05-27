# Lecture 1: Choosing the Right Architecture Pattern

> *"Architecture should fit your constraints, not the other way around."*

**Section 9 — Architectural Decision-Making & Trade-offs**

---

## 🎯 Is Lecture Mein Kya Seekhenge?

- **Why architecture decisions matter** — long-term consequences
- **Common patterns recap** (monolith, microservices, EDA, layered, serverless)
- **Core criteria** for choosing — complexity, scale, team, time, regs
- **Five-step decision process**
- **When each pattern fits**
- **Architecture fit matrix** by use case
- **Real-world case study** — ride-hailing app

---

## 1. Why Architecture Patterns Matter

```
✓ Decisions influence:
   - Scalability
   - Maintainability
   - Performance
   - Team velocity

✓ Good choice → robust + adaptable
✗ Poor choice → bottlenecks, fragility, rework

✓ Patterns affect speed of change
   - Some promote modularity + independent deploy
   - Others create coordination bottlenecks

✗ Every pattern involves trade-offs
   - No perfect solution
   - Only choices that fit certain problems

✗ Wrong early choice → long-term technical debt
```

**Architecture isn't an academic exercise — it shapes the evolution of your entire system.**

---

## 2. Pattern Recap

### The Common Candidates

```
┌──────────────────┬─────────────────────────────────────┐
│ Pattern          │ Core Idea                           │
├──────────────────┼─────────────────────────────────────┤
│ Monolith         │ All-in-one code base + deployment   │
│ Microservices    │ Many small, independent services    │
│ Event-driven     │ Components communicate via events   │
│ Layered (N-tier) │ Stack of concerns: UI/Logic/Data    │
│ Serverless       │ Stateless functions triggered by    │
│                  │ events                              │
└──────────────────┴─────────────────────────────────────┘
```

### Each Solves a Different Problem

```
Monolith       → Simplicity, fast start
Microservices  → Scale + team autonomy
Event-driven   → Decoupling + real-time flows
Layered        → Organization + maintainability
Serverless     → Cost efficiency + on-demand scale
```

---

## 3. Core Criteria for Choosing

### 1. System Complexity & Domain Boundaries

```
Simple CRUD app?              → Monolith works
Multiple bounded contexts?    → Modular / microservices
```

### 2. Scale — Current and Anticipated

```
100s of users today  → Monolith fine
Millions expected    → Scalability becomes a deciding factor
```

### 3. Team Structure & Size

```
Small team (< 10)    → Distributed systems are painful
                       → Stick with monolith / modular
Large team (50+)     → Microservices give clear ownership
```

### 4. Time-to-Market

```
Need to ship fast?  → Monolith / serverless
Plenty of time?     → Can afford to model carefully
```

### 5. Regulatory / Security Constraints

```
Finance, healthcare, defense:
   ✓ Strict data control
   ✓ Auditability
   ✓ Separation of concerns
   → Often pushes toward modular or service-oriented
```

**Architecture should fit your constraints — never the other way around.**

---

## 4. Five-Step Decision Process

```
┌──────────────────────────────────────────────────────────┐
│                                                          │
│  Step 1: Define business + technical GOALS              │
│          ↓                                               │
│  Step 2: List CONSTRAINTS (scale, team, latency, regs)  │
│          ↓                                               │
│  Step 3: Identify CANDIDATE architectures               │
│          ↓                                               │
│  Step 4: Evaluate TRADE-OFFS for each option            │
│          ↓                                               │
│  Step 5: Validate with SPIKE / PROTOTYPE                │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### Why Step 5 Matters

```
✓ Tests your assumptions
✓ Uncovers hidden complexity
✓ Reduces risk before full commitment
```

---

## 5. When the Monolith Wins

```
✓ Simple application + small team
✓ Single code base, single deployment
✓ Centralized logging, debugging, monitoring
✓ Fast to develop, test, deploy
✓ Smart for MVPs / early product iteration

✗ Becomes bottleneck as scale + team grows
```

### Sweet Spot

```
✓ Team < 10 engineers
✓ Single domain or tightly related domains
✓ Need to validate product fit
✓ Want to ship in weeks, not quarters
```

---

## 6. When Microservices Shine

```
✓ Large-scale systems with clear domain boundaries
✓ Multiple teams owning different services
✓ Independent scale + deploy needs

✗ Requires DevOps maturity:
   - CI/CD pipelines
   - Service discovery
   - Centralized logging
   - Tracing (Jaeger/Zipkin)
   - Container orchestration (Kubernetes)

✗ Communication complexity
   - Network latency
   - Failure handling
   - Eventual consistency
```

### Sweet Spot

```
✓ Multiple teams (3+ pizza teams)
✓ Distinct domains (Payment, Order, Auth, ...)
✓ Different scale needs per service
✓ Mature DevOps culture
```

---

## 7. When Event-Driven Architecture Shines

```
✓ Real-time use cases:
   - Ride-hailing dispatch
   - Chat & messaging
   - Fraud detection
   - Inventory updates

✓ Logging, monitoring, analytics pipelines

✓ Loose coupling between producers + consumers
   - New consumers added without changing producers

✗ Complexity:
   - Event ordering
   - Duplicate handling
   - Retries
   - Eventual consistency
   → Affects UX design
```

---

## 8. When Layered / N-Tier Still Fits

```
✓ Clarity + modularity through layered structure
✓ Easy onboarding
✓ Common in enterprise + back-office systems
✓ Long-lived applications

✗ Can become rigid:
   - Layers become bottlenecks
   - Glue code multiplies
   - Changes ripple across layers
```

### Sweet Spot

```
✓ Large enterprise codebases
✓ Long-lived applications
✓ Heavy compliance / structure needs
✓ Junior-heavy teams that benefit from clear scaffolding
```

---

## 9. Architecture Fit Matrix

```
┌────────────────────────────┬────────────────────────────────┐
│ Use Case                   │ Recommended Pattern            │
├────────────────────────────┼────────────────────────────────┤
│ MVP / Early-stage          │ Monolith                       │
│ Small CRUD app             │ Monolith                       │
│ Real-time updates          │ Event-driven                   │
│ Live tracking / chat       │ Event-driven                   │
│ Large enterprise system    │ Microservices (mature)         │
│ IoT / event spikes         │ Serverless + EDA               │
│ Internal back office       │ Layered                        │
│ Mixed needs                │ Hybrid                         │
└────────────────────────────┴────────────────────────────────┘
```

### Hybrid is Often Best

Real systems rarely use a single pure pattern. **Modular monolith with event-driven async**, **microservices with layered services inside**, etc.

---

## 10. Real-World Case Study — Ride-Hailing App (Uber-like)

### Business Goals

```
✓ Real-time updates (driver location, trip progress)
✓ High availability, especially peak hours
✓ Sub-second latency for rider/driver matching
```

### Team Capability

```
✓ 6 experienced backend devs
✓ Comfortable with distributed systems
```

### Constraints

```
✓ Low latency
✓ Eventual consistency OK for payment confirmation
✓ Scaling pressure: regional + global
```

### The Choice — Hybrid

```
Microservices  → for domain separation + ownership
   ✓ Trip Service
   ✓ Pricing Service
   ✓ Notification Service
   ✓ Analytics Service

Event-driven   → for real-time + decoupling
   When trip booked:
      TripService emits "OrderPlaced" event
      ↓
      Pricing + Notification + Analytics consume independently
```

### Why This Matches Goals + Constraints

```
✓ Each service owns its domain
✓ Real-time responsiveness via events
✓ Scale services independently
✓ New consumers added without touching producers
```

---

## 11. Summary

```
✓ Start with constraints + goals — not patterns
✓ Patterns are trade-offs, not recipes
✓ When in doubt, keep it simple
   - Monolith / serverless for early systems
   - Add complexity only when justified
✓ Revisit architecture as system grows
   - What worked at 100 users won't at 1M
```

---

## 🎤 Interview Q&A

**Q1. When would you NOT choose microservices?**

A: For small teams, early-stage products, or systems with no clear domain boundaries. Microservices' operational overhead (CI/CD, service discovery, observability, distributed tracing) outweighs the autonomy benefits when you don't have multiple teams or distinct domains to split.

**Q2. How do you justify an architecture choice to non-technical stakeholders?**

A: Tie it to business outcomes: cost (infra + dev time), time-to-market (how fast can we ship a feature), risk (what breaks if a part fails), and scale (can we grow 10x without rebuilding). Avoid jargon; frame trade-offs in their language.

**Q3. What's a "hybrid architecture" and when is it appropriate?**

A: Mixing patterns where each fits — e.g., microservices for domain separation + event-driven for async flows + serverless for occasional jobs. It's appropriate (and common) in real-world systems because no single pattern solves every problem in a complex domain.

**Q4. How do you decide between a monolith and microservices for a new product?**

A: Default to monolith. Reasons to start with microservices: (a) you already have multiple teams ready to own services, (b) you have very different scale or tech needs per service, (c) the domain has well-known, stable boundaries. Otherwise, start monolith and extract services as boundaries clarify.

**Q5. Why is the five-step decision process useful?**

A: It forces deliberate reasoning instead of trend-chasing. Defining goals + constraints first prevents you from copying patterns that don't fit. Step 5 (prototype) is critical — it validates assumptions cheaply before a full commitment that's expensive to reverse.

---

## 🔗 Related

- Next: [02_Tradeoff_Analysis.md](02_Tradeoff_Analysis.md)
- Section 3 — Distributed patterns: [Section_03_Distributed_Systems/](../Section_03_Distributed_Systems/)
