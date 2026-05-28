# Lecture 2: Trade-off Analysis

> *"There is no perfect solution — only the one that best fits your context."*

**Section 9 — Architectural Decision-Making & Trade-offs**

---

## 🎯 Is Lecture Mein Kya Seekhenge?

- **What is a trade-off** in system design
- **Why trade-off analysis matters**
- **Scalability vs Maintainability** — monolith vs microservices
- **Latency vs Consistency** — distributed databases
- **Cost vs Flexibility** — build vs buy
- **Framework** for evaluating trade-offs
- **Context-aware decision making**

---

## 1. What is a Trade-off?

```
Every architectural decision = consequences

Trade-offs come from:
   ✓ Conflicting goals
   ✓ Tight constraints
   ✓ Limited resources

✗ There's no perfect solution
✓ Only the one that fits YOUR context

Context = system + scale + team + goals
```

**Acknowledging trade-offs makes us better engineers.**

---

## 2. Why Trade-off Analysis Matters

```
✓ Informed, intentional decisions
✓ Prevents:
   ✗ Over-engineering
   ✗ Premature optimization

✓ Essential during architecture reviews
✓ Bridges PM ↔ Engineering communication
   - PM wants speed
   - Engineers worry about long-term
   - Trade-off doc aligns both
```

---

## 3. Trade-off #1: Scalability vs Maintainability

### Definitions

```
Scalability    → can the system handle 10x load?
Maintainability → can a new dev fix a bug in 1 day?
```

### The Tension

```
Aggressive scale:
   ✓ Microservices, message queues, distributed state, caches
   ✗ Complex, hard to debug, more moving parts

Simple maintainability:
   ✓ Monolith, one DB, simple deploy
   ✗ Bottleneck at scale
```

### Visualizing It

```
   maintainability ▲
                   │  ┌─ monolith
                   │  │
                   │  │
                   │  │      ┌─ modular monolith
                   │  │      │
                   │  │      │
                   │  │      │       ┌─ microservices
                   │  │      │       │
                   └──┴──────┴───────┴────────► scale
```

---

## 4. Real-World: Monolith vs Microservices

### Monolith Wins When

```
✓ Small team
✓ Single domain
✓ Early-stage product
✓ Centralized debugging is a benefit
✓ Easier to test, deploy, evolve
```

### Microservices Win When

```
✓ Large team
✓ Distinct domains
✓ Different scaling needs per service
✓ Independent deploy + release cycles

✗ Cost:
   - Service discovery
   - Logging + tracing
   - Failure handling
   - DevOps maturity
```

### Rule of Thumb

```
Start with a monolith.
Evolve to microservices only when scale + team size justify the complexity.
```

---

## 5. Trade-off #2: Latency vs Consistency

### Definitions

```
Consistency → data is correct + same across all nodes
Latency     → time to respond to a request
```

### The CAP Connection

```
In distributed systems, strong consistency often increases latency:
   ✓ Wait for replication across nodes
   ✓ Wait for distributed locks
   ✓ Wait for quorum acknowledgments

→ More correctness, more wait
```

### Eventual Consistency

```
✓ Faster responses
✓ Higher availability
✗ Users may see stale data
✗ Conflicting updates possible

Use when:
   ✓ Social feeds
   ✓ Product catalogs
   ✓ Analytics dashboards

Avoid when:
   ✗ Banking transactions
   ✗ Inventory (overselling = bad)
```

---

## 6. Real-World: Distributed Databases

```
┌─────────────────────────┬─────────────────────────┐
│ Strong Consistency       │ Eventual Consistency    │
├─────────────────────────┼─────────────────────────┤
│ PostgreSQL              │ Cassandra               │
│ MySQL (with InnoDB)     │ DynamoDB                │
│ Spanner                 │ MongoDB (default)       │
│ CockroachDB             │ Riak                    │
│ Higher latency          │ Lower latency           │
│ Lower availability      │ Higher availability     │
│ Banking, ledgers, regs  │ Social, catalogs        │
└─────────────────────────┴─────────────────────────┘
```

### Decision Question

```
Can your users tolerate temporary inconsistency?
   YES → eventual (fast, available)
   NO  → strong (slower, may sacrifice availability)
```

---

## 7. Trade-off #3: Cost vs Flexibility

### Definitions

```
Flexibility → ability to adapt + extend cheaply
Cost        → upfront + ongoing infra + dev expense
```

### The Tension

```
Highly flexible system:
   ✓ Modular, loosely coupled
   ✓ Easy to evolve
   ✗ More upfront + ongoing cost

Tightly coupled system:
   ✓ Cheap to build + run
   ✗ Hard to modify
   ✗ Ripple effects on every change
```

---

## 8. Real-World: Build vs Buy

### Buying (e.g., Auth0)

```
✓ Save time + upfront cost
✓ Tested, maintained, secure
✗ Less control + flexibility
✗ Vendor lock-in
✗ Can't deeply customize
```

### Building In-House

```
✓ Full customization
✓ No vendor risk
✗ Significant engineering effort
✗ Ongoing maintenance + on-call burden
✗ Reinventing the wheel
```

### Rule of Thumb

```
Buy: commodity functions where you add no value (auth, email, billing)
Build: core differentiators where you must own the experience
```

---

## 9. Evaluation Framework for Trade-offs

### Four-Step Method

```
1. Identify priorities
   What matters MOST RIGHT NOW?
   (scalability? time-to-market? cost?)

2. Clarify constraints
   - Team size + expertise
   - Budget
   - Expected scale
   - Tech stack

3. Evaluate options across dimensions
   - How does each affect priorities?
   - How does each respect constraints?

4. Revisit + reassess regularly
   Trade-offs are NOT set in stone
   - Reassess as system grows
   - Reassess as goals shift
```

### Worksheet Example

```
Priority   ──► Time-to-market
Constraint ──► 4 engineers, 3-month deadline
Options    ──► Monolith / Modular Monolith / Microservices

Monolith     → ★★★★★ time-to-market, ★★ scale
Modular      → ★★★★  time-to-market, ★★★ scale
Microsvc     → ★     time-to-market, ★★★★★ scale (but overkill now)

Choice: Monolith (revisit when team > 10 or scale > 50k QPS)
```

---

## 10. Summary

```
✓ Scalability ↔ Maintainability
   Growing capacity often increases complexity

✓ Latency ↔ Consistency
   Strong correctness costs response time

✓ Cost ↔ Flexibility
   Flexible architectures cost more to build + run

✓ No universal answer
   Every decision depends on YOUR context:
      - users
      - team
      - goals
      - constraints

Revisit + reassess as system evolves.
```

---

## 🎤 Interview Q&A

**Q1. How do you explain the CAP theorem trade-off to a non-technical stakeholder?**

A: In a distributed system, when networks fail (and they will), you must choose: "always answer, even with possibly old data" (availability) or "refuse to answer rather than risk being wrong" (consistency). It's not about being slow — it's about what your business prefers when something breaks.

**Q2. Why might a startup choose a monolith even though everyone "knows" microservices are scalable?**

A: Because at startup scale, the bottleneck isn't infrastructure — it's product-market fit. Microservices' operational complexity slows shipping, and you're optimizing for the wrong thing. A monolith ships faster, validates the idea, and can be decomposed later when you actually have the load and team to justify it.

**Q3. Walk through a build-vs-buy decision you've made.**

A: Example — choosing Stripe over building payment processing. The trade-off was full control + no fees vs months of PCI compliance work and ongoing fraud handling. Stripe charges 2.9% per transaction but saves us 6+ months of engineering. For us, time-to-market and compliance were higher-value than the fee savings. We'd revisit if our volume made the fee material.

**Q4. When is eventual consistency NOT acceptable?**

A: When stale reads can cause incorrect business decisions: banking balances, inventory (avoid overselling), seat booking (avoid double-booking), real-time fraud signals, leaderboards in competitive games. Anywhere "wrong answer" is worse than "no answer."

**Q5. Why must trade-off decisions be revisited?**

A: Because the inputs change. Team size grows. Scale changes. Compliance requirements appear. A decision that was right at 100 users may be wrong at 1M. Treating decisions as permanent prevents you from adapting. Document trigger conditions in your ADRs so you know when to revisit.

---

## 🔗 Related

- Previous: [01_Choosing_Architecture_Pattern.md](01_Choosing_Architecture_Pattern.md)
- Next: [03_Pattern_Selection_Framework.md](03_Pattern_Selection_Framework.md)
- Related: [Section 1 — Quality Attributes](../Section_01_Foundations/03_Quality_Attributes.md)
