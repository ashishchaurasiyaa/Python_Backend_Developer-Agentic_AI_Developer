# Lecture 3: Pattern Selection Framework

> *"Frameworks help you reason — the thinking still matters."*

**Section 9 — Architectural Decision-Making & Trade-offs**

---

## 🎯 Is Lecture Mein Kya Seekhenge?

- **Why we need selection frameworks** at all
- **Four framework types** — decision trees, checklists, scoring models, constraint matrices
- **When to use which** framework
- **Creating your own** team/project-specific framework
- **Common pitfalls** in using frameworks
- **The mindset** — frameworks support thinking, don't replace it

---

## 1. Why We Need Selection Frameworks

```
Architectural decisions rarely have a single answer.

Balancing:
   ✓ Scalability
   ✓ Latency
   ✓ Team skill
   ✓ Delivery timeline
   ✓ Budget
   ✓ Compliance

→ Forces pull in different directions

Without structure:
   ✗ Decisions made on opinion
   ✗ High cost mistakes
   ✗ Hard to explain or defend
   ✗ Hard to revisit
```

### What Frameworks Bring

```
✓ Reduced personal bias
✓ Repeatable structure
✓ Shared language across teams
✓ Scalable design conversations
```

---

## 2. The Four Framework Types

```
┌────────────────────┬──────────────────────────────────────┐
│ Framework          │ Best For                             │
├────────────────────┼──────────────────────────────────────┤
│ Decision Tree      │ Structured rule-based flows          │
│                    │ Repeatable / automatable decisions   │
│ Checklist          │ Ensuring coverage                    │
│                    │ Onboarding, reviews                  │
│ Scoring Model      │ Comparing multiple viable options    │
│                    │ Building consensus                   │
│ Constraint Matrix  │ Quickly eliminating non-viable opts  │
│                    │ Early-stage filtering                │
└────────────────────┴──────────────────────────────────────┘
```

---

## 3. Decision Trees

### When They Shine

```
✓ Standardized recurring decisions
✓ Well-scoped domain
✓ Clear branching logic ("if X then Y")
```

### Example: API Style Choice

```
                Real-time updates needed?
                       │
              ┌────────┴────────┐
              │                 │
            yes                no
              │                 │
              ▼                 ▼
       Event-driven       Synchronous?
       /WebSocket               │
                       ┌────────┴────────┐
                       │                 │
                     yes               no
                       │                 │
                       ▼                 ▼
                     REST           Async REST
                                  + message queue
```

### Strengths

```
✓ Encodes organizational knowledge
✓ Onboards juniors quickly
✓ Automation-friendly
```

### Limitations

```
✗ Doesn't scale to complex spaces
✗ Fuzzy inputs ("how mature is the team?") don't branch cleanly
✗ Can oversimplify
```

---

## 4. Checklists

### When They Shine

```
✓ Ensuring coverage during reviews
✓ Architecture reviews + trade-off discussions
✓ Onboarding architects
```

### Example: Architecture Review Checklist

```
□ Scale dimension considered?
   - QPS / users / data volume

□ Latency requirements documented?
   - p50, p95, p99

□ Failure modes identified?
   - What happens if Service X is down?

□ Cost projection done?
   - TCO over 3 years

□ Compliance reviewed?
   - PCI, HIPAA, GDPR, DPDP, etc.

□ Observability planned?
   - Logs / metrics / traces

□ Disaster recovery thought through?
   - RTO, RPO

□ Team skill match assessed?
```

### Strengths

```
✓ Easy to create + scale
✓ Tailorable per team/domain
✓ Catches blind spots
✓ Useful for novices + experts
```

### Limitations

```
✗ Can become box-ticking
✗ Lose value if treated passively
```

### How to Keep Checklists Alive

```
✓ Trigger real conversations, not just ticks
✓ Pair with discussion ("why did we tick that?")
```

---

## 5. Scoring Models

### When They Shine

```
✓ Comparing multiple viable options
✓ Need structured, defensible reasoning
✓ Cross-functional / large team alignment
```

### How It Works

```
1. Identify decision factors
   (latency, cost, scalability, team-fit)

2. Assign weights based on importance
   weights sum to 1.0
   e.g., latency 0.30, cost 0.20, team-fit 0.15, ...

3. Score each option per factor (1–5)
   based on known trade-offs

4. Compute weighted total
   score = Σ (weight × factor_score)

5. Compare totals
```

### Example

```
┌───────────────┬─────┬─────┬─────┬─────┐
│ Factor        │ Wt  │ A   │ B   │ C   │
├───────────────┼─────┼─────┼─────┼─────┤
│ Latency       │ 0.3 │ 4   │ 5   │ 3   │
│ Cost          │ 0.2 │ 5   │ 3   │ 4   │
│ Scalability   │ 0.2 │ 3   │ 5   │ 5   │
│ Team-fit      │ 0.2 │ 5   │ 3   │ 4   │
│ Vendor risk   │ 0.1 │ 4   │ 4   │ 5   │
├───────────────┼─────┼─────┼─────┼─────┤
│ Total         │     │ 4.2 │ 4.1 │ 4.0 │
└───────────────┴─────┴─────┴─────┴─────┘

Result: A wins narrowly. Discussion focuses on whether
the weights are right + whether scores are calibrated.
```

### Strengths

```
✓ Brings structure to fuzzy decisions
✓ Makes trade-offs visible + discussable
✓ Reduces opinion battles
✓ Builds consensus in large teams
```

### Limitations

```
✗ Numbers can create false precision
✗ "1–5" scores are subjective
✗ Garbage-in-garbage-out (if weights wrong, result wrong)
```

---

## 6. Constraint Matrices

### When They Shine

```
✓ Early-stage architecture filtering
✓ Quickly eliminating non-viable options
✓ Visual + stakeholder-friendly
```

### Example

```
                Latency  Compliance  Team  Cost
                <100ms   PCI         <10   <$10k/mo
─────────────────────────────────────────────────────
Monolith          ✓        ✓         ✓       ✓
Microservices     ✓        ✓         ✗       ✗
Serverless        ✗        ✓         ✓       ✓
SaaS              ✓        ✗         ✓       ✓
─────────────────────────────────────────────────────
Viable:           Monolith only ✓
```

### Strengths

```
✓ Fast filtering
✓ Visual — easy to present
✓ Forces explicit constraint capture
```

### Limitations

```
✗ Binary fit — doesn't show "almost fits"
✗ Doesn't capture trade-offs within viable set
```

---

## 7. When to Use Which

```
Decision Tree   → Speed + consistency
                  Automated tooling
                  Architecture playbooks

Checklist       → Review + onboarding
                  Trade-off discussion
                  Junior guidance

Scoring Model   → High stakes
                  3+ valid patterns to compare
                  Strategic, transparent comparison

Constraint Matr → Early stage filtering
                  Quick stakeholder alignment
                  Eliminate non-viable options
```

### Combine for Best Results

```
Constraint Matrix → narrow to viable set
        ↓
Scoring Model     → rank the viable ones
        ↓
Checklist         → review the chosen one
        ↓
Decision Tree     → reuse logic for similar future decisions
```

---

## 8. Creating Your Own Framework

### Step-by-Step

```
1. Audit your recurring decisions
   ✓ REST vs event-driven?
   ✓ Break up the monolith?
   ✓ Build vs buy auth?

2. Identify common constraints + priorities
   ✓ Latency tolerance
   ✓ Delivery speed
   ✓ Compliance needs

3. Build templates
   ✓ Your decision tree
   ✓ Your checklist
   ✓ Your scoring template (with your weights)

4. Tune to your context
   Example: if ops simplicity matters more than latency,
            give it more weight

5. Keep it lightweight
   A framework that slows you down is worse than no framework
```

### Iterate

```
✓ Use it on real decisions
✓ Refine after each use
✓ Retire what doesn't help
```

---

## 9. Common Pitfalls

### 1. Overfitting

```
✗ Designed around past problem
✗ Force-fit into new problem
→ Architecture evolves; frameworks must evolve too
```

### 2. Ignoring the Human Side

```
✗ Picking "best" technical solution
✗ Team can't build or maintain it
→ Frameworks must consider team capability
```

### 3. Over-Scoring

```
✗ Precise numbers for fuzzy ideas
✗ Illusion of objectivity
→ Numbers structure the discussion, they don't decide it
```

### 4. Checklist Fatigue

```
✗ Adding too many items
✗ Team skips or fakes them
→ More items ≠ better decisions
   Keep checklists short + meaningful
```

### Key Insight

```
Frameworks GUIDE thinking — they don't REPLACE it.
```

---

## 10. Summary

```
✓ Tools don't give you answers — they structure your thinking

Decision Tree  → speed + consistency
Checklist      → coverage + onboarding
Scoring Model  → multi-option comparison
Constraint Mtx → eliminating non-viables

✓ Combine multiple for best results
✓ Build your own, tailored to team + domain
✓ Keep them lightweight + adaptable
✓ Review + refine regularly

Frameworks are TOOLS, not RULES.
```

---

## 🎤 Interview Q&A

**Q1. Why use a weighted scoring model instead of just gut feel?**

A: Gut feel works when one person decides; it fails when teams need to align. Weighted scoring forces explicit conversation about what matters and how much. The number isn't the point — the discussion that produces it is. It also creates a defensible record for re-evaluation later.

**Q2. When is a decision tree the wrong tool?**

A: When inputs are fuzzy or the space is complex. "How mature is your team?" doesn't have a clean Yes/No branch. Trees also age poorly — they encode yesterday's good answers, and you can keep following them blindly when reality has shifted.

**Q3. What's the difference between a constraint matrix and a scoring model?**

A: Constraint matrix is binary — does this option meet hard requirements? (Yes/No, in/out.) Scoring model is graded — how well does each viable option meet weighted priorities? You typically use the matrix to narrow down, then scoring to choose among survivors.

**Q4. How do you prevent checklist fatigue on your team?**

A: Keep checklists short (≤ 10 items), tied to real failure modes you've seen ("we forgot to check X last time"). Pair every item with a one-sentence "why." Retire items that haven't caught anything in 6 months. Make the review verbal, not just box-ticking.

**Q5. How would you create a framework for your current team?**

A: Look at the last 5 architecture decisions. What did we argue about repeatedly? Those become my factors. What did we miss and learn? Those become my checklist items. What were the constraints we kept hitting? Those become my matrix axes. Then I'd use it on the next 3 decisions and refine.

---

## 🔗 Related

- Previous: [02_Tradeoff_Analysis.md](02_Tradeoff_Analysis.md)
- Next: [04_Architecture_AntiPatterns.md](04_Architecture_AntiPatterns.md)
