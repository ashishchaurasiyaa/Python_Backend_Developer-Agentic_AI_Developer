# RFC & ADR Writing — Staff/Senior Engineer Skill

**Senior Leadership · Year 5+ | Staff Engineer Track**

---

## Quick Concepts

**WHAT:**
- **RFC (Request for Comments)** = ek proposal document jo team ke saath technical decision share karne ke liye likha jata hai *before* implementation
- **ADR (Architecture Decision Record)** = ek short doc jo *after* decision log karta hai — "humne yeh kyun choose kiya"
- **Difference**: RFC = future proposal (feedback maango), ADR = past decision (history preserve karo)

**WHY (Senior/Staff interview me kyun important):**
- Senior engineer akela code nahi karta — uske decisions ka impact 10x hota hai
- RFC culture = async alignment (sync meetings se better)
- ADRs = future engineers ko context milta hai ("yeh Django kyun hai, FastAPI kyun nahi?")
- Big companies (Amazon, Google, Netflix) me senior promotions me RFC quality matter karti hai

---

## Part 1: RFC Format

### Standard RFC Template
```markdown
# RFC-042: Replace Celery with Temporal for Workflow Orchestration

**Author:** Ashish C.  
**Date:** 2025-06-23  
**Status:** DRAFT | UNDER REVIEW | ACCEPTED | REJECTED | SUPERSEDED
**Reviewers:** @backend-team, @platform-team  
**Decision Deadline:** 2025-07-07

---

## Summary (TL;DR — 2-3 lines)

Celery worker failures me visibility nahi hai aur retry logic complex ho gayi hai.
Temporal adopt karein — durable execution + built-in retry + workflow history milega.

---

## Problem Statement

Kya problem solve karna hai? Kya evidence hai ki problem real hai?

Current system:
- 3 Celery workers, 2 Redis queues
- Month me ~50 silent failures (job silently drop hoti hain)
- Debugging ke liye 30-40 min lagta hai per incident
- Retry logic: 400 LOC ka spaghetti code

Evidence:
- Sentry: 50 silent failures/month
- Oncall: 15 hours/month debugging Celery issues
- Customer impact: 200 delayed notifications/month

---

## Goals

- [ ] Zero silent failures (failures visible + alertable)
- [ ] Retry logic: custom code → framework-level
- [ ] Debugging time: 40 min → 5 min
- [ ] Zero customer impact during migration

---

## Non-Goals

- Database migration (out of scope)  
- Real-time streaming (Kafka handles this)
- Eliminating all async processing

---

## Proposed Solution

**Temporal** adopt karein for durable workflow execution.

### Architecture Change
```
Before:
Django → Celery → Redis → Worker
                         (silent failures possible)

After:
Django → Temporal SDK → Temporal Server → Worker
                        (every state persisted in DB)
```

### Key Benefits
1. **Durable Execution**: Worker crash hone pe automatically resume
2. **Built-in Retry**: Exponential backoff, max attempts — no custom code
3. **Workflow Visibility**: UI me har step ka status
4. **Testing**: Deterministic workflow testing built-in

### Implementation Plan
- Week 1-2: Temporal setup + pilot (1 workflow)
- Week 3-4: Critical workflows migrate
- Week 5-6: Celery deprecate + monitoring

---

## Alternatives Considered

| Option              | Pros                      | Cons                        | Verdict     |
|---------------------|---------------------------|-----------------------------|-------------|
| Fix Celery          | No migration cost         | Root cause nahi solve hota  | ❌ Reject   |
| Celery + Flower     | Visibility add hoti       | Retry logic still bad       | ❌ Partial  |
| **Temporal**        | Durable, testable, UI     | Learning curve, infra cost  | ✅ Recommend |
| Prefect             | Python-native, easy setup | Less mature, smaller community | 🟡 Backup |
| Airflow             | Battle-tested             | Batch-only, overkill        | ❌ Reject   |

---

## Risks & Mitigations

| Risk                          | Likelihood | Impact | Mitigation                          |
|-------------------------------|-----------|--------|-------------------------------------|
| Team Temporal learning curve  | High      | Medium | 1-week training + pilot project     |
| Migration bugs                | Medium    | High   | Feature flag + rollback plan        |
| Temporal server downtime      | Low       | High   | HA cluster + fallback to Celery     |
| Vendor lock-in                | Low       | Low    | Temporal is open-source             |

---

## Cost

- Engineering: 6 weeks × 2 engineers = 12 engineer-weeks
- Infrastructure: +$200/month (Temporal Cloud) or self-hosted
- Training: 1 week

---

## Success Metrics

- Silent failures: 50/month → 0
- Debugging time: 40 min → 5 min per incident
- Oncall burden: 15 hr/month → 2 hr/month
- 30 days after launch: zero customer-impacting failures

---

## Open Questions

1. Self-hosted Temporal vs Temporal Cloud? (cost vs ops burden)
2. Existing Celery tasks ke parallel period me monitoring kaise?
3. Team me kisko Temporal champion banana chahiye?

---

## References
- [Temporal docs](https://docs.temporal.io)
- [Uber Cadence → Temporal migration case study]
- Slack thread: #backend-infra (June 15)
```

---

## Part 2: ADR Format

ADR = shorter, decision capture. RFC ke baad ya kisi bhi important decision ke liye.

### ADR Template
```markdown
# ADR-017: Use PostgreSQL JSONB for Product Metadata

**Date:** 2025-04-10  
**Status:** Accepted  
**Deciders:** Ashish C., Priya S.  
**Supersedes:** ADR-009 (MongoDB for metadata)

---

## Context

E-commerce platform ke product catalog me har product ka metadata highly variable hai —
electronics ke liye voltage/warranty, clothing ke liye size/material, etc.
Alag-alag schema chahiye tha aur querying bhi.

## Decision

MongoDB (ADR-009) ki bajaye PostgreSQL JSONB use karein.

## Reasoning

- Team already PostgreSQL expert hai — MongoDB ops overhead nahi chahiye
- JSONB pe GIN index se JSON field queries fast (comparable to MongoDB)
- ACID transactions ka faida milta hai (order + product update atomic)
- Single database = simpler backup, monitoring, connection pooling
- Tested: 10M product query = 45ms (acceptable)

## Alternatives Rejected

- **MongoDB**: Ops overhead, team unfamiliar, separate backup
- **EAV (Entity-Attribute-Value)**: Slow queries, complex ORM code
- **Separate table per category**: 50+ tables, schema migration nightmare

## Consequences

**Positive:**
- Database count: 2 → 1
- One less technology to operate
- JSON queries aur SQL queries ek hi place se

**Negative:**
- JSON field pe complex aggregations slow (acceptable for our use case)
- Typo in JSON key = runtime error (add schema validation in app layer)

## Follow-up Actions

- [ ] GIN index on `metadata` column add karna
- [ ] Pydantic model for metadata validation
- [ ] ADR-009 ko "Superseded" mark karna
```

---

## Part 3: When to Write RFC vs ADR

| Situation                                   | Write         |
|---------------------------------------------|---------------|
| New tech/framework adopt karna              | RFC first, then ADR |
| Database schema major change                | RFC (if complex), ADR |
| Architecture overhaul                       | RFC mandatory |
| Quick library choice (one engineer decides) | ADR only |
| Bug fix / refactor                          | Nothing       |
| Breaking API change                         | RFC mandatory |
| Third-party vendor evaluation               | RFC           |
| Already decided, document history           | ADR only      |

---

## Part 4: RFC Process (Team me kaise kaam karta hai)

```
1. DRAFT       Ashish RFC likhta hai, self-review karta hai
       ↓
2. SHARE       Slack / GitHub PR me share karta hai, reviewers tag karta hai
       ↓
3. COMMENT     Team 5-7 days me async comments karta hai (GitHub PR comments best)
       ↓
4. SYNC        Agar controversy hai to 30-min meeting (optional)
       ↓
5. DECISION    Author status update karta hai: ACCEPTED / REJECTED / REVISED
       ↓
6. ADR         Ek short ADR banata hai final decision capture ke liye
       ↓
7. IMPLEMENT   Code implementation start
```

### GitHub PR as RFC
```bash
# RFC as PR = comments per line, version history, link in commit
git checkout -b rfc/temporal-migration
# RFC likhta hoon
git add docs/rfcs/042_temporal_migration.md
git commit -m "RFC-042: Propose Temporal for workflow orchestration"
git push && gh pr create --title "[RFC] Temporal Migration"
# PR pe review → merge → decision documented
```

---

## Part 5: Common RFC Mistakes

### Mistake 1: Solution-first RFC
```markdown
# BAD: RFC to use Temporal
"Humne decide kar liya hai ki Temporal use karein. Yeh document yeh explain karta hai."

# GOOD: Problem-first RFC  
"Celery me yeh 3 problems hain (evidence ke saath). Temporal ek potential solution hai.
Alternatives bhi consider kiye. Feedback chahiye."
```

### Mistake 2: Too long / Too detailed
- RFC = decision, implementation nahi
- Design details → implementation phase me
- Target: 1-2 pages. 5+ pages = usually too much

### Mistake 3: No alternatives section
- Alternatives section = yeh dikhata hai ki tumne seriously socha
- "I considered X, Y, Z but chose W because..." = credibility

### Mistake 4: No success metrics
- "Yeh better hai" = vague
- "Debugging time 40 min → 5 min" = measurable

---

## Part 6: ADR Storage

```
docs/
├── rfcs/
│   ├── 001_microservices_architecture.md
│   ├── 042_temporal_migration.md
│   └── README.md  ← index of all RFCs
└── adr/
    ├── 001_use_postgresql.md
    ├── 017_jsonb_metadata.md
    └── README.md  ← index of all ADRs
```

```markdown
# ADR Index (docs/adr/README.md)

| # | Title | Status | Date |
|---|-------|--------|------|
| 001 | Use PostgreSQL as primary DB | Accepted | 2023-01 |
| 017 | JSONB for product metadata | Accepted | 2025-04 |
| 018 | Reject GraphQL for v1 | Rejected | 2025-05 |
```

---

## Interview Q&A

**Q: RFC aur ADR me kya fark hai?**
A: RFC = prospective — decision lene SE PEHLE likha jata hai, team se feedback maanga jata hai. ADR = retrospective — decision ho jane ke baad short doc me capture kiya jata hai: context, decision, consequences. RFC optional hai (small decisions me nahi), ADR mandatory hai important architectural choices ke liye.

**Q: Team RFC culture kaise build karte hain?**
A: Pehle khud likhna shuru karo — ek good RFC example set karo. Template provide karo. PR-based review (GitHub) easy hota hai than separate wiki. "RFC required" rule 3 scenarios ke liye: new tech adopt, breaking change, architecture overhaul. Baaki ke liye optional.

**Q: Kisi ne RFC disagree kiya to kya karte ho?**
A: Disagreement async comments me document karo, alternatives seriously consider karo. Agar consensus nahi ban raha to synchronous meeting + decision deadline set karo. "Disagree and commit" principle: team decision hone ke baad sab implement karte hain even if personally disagree, par disagreement RFC me documented rehta hai.

**Q: ADR kab update karte hain?**
A: ADR immutable hona chahiye — purana ADR mat update karo. Naya ADR banao jo "Supersedes ADR-XXX" likhe. Purane ADR ka status "Superseded" kar do. History preserve rehti hai — future mein samajh aata hai ki decision kaise evolve hua.

---

## Related Topics
- `02_engineering_leadership.md` — Engineering leadership broader skills
- `05_tech_strategy_documentation.md` — Tech strategy docs
- `01_System_Design/HLD_Theory` — Architecture patterns jo RFC/ADR trigger karte hain
