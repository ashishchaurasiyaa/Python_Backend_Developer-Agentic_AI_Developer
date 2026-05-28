# 📐 Architecture Decision Records (ADRs) — Complete Guide

> **Target:** 3-4 YOE | **Goal:** ADR kya hai, kyu likhe, kaise likhe — senior-level documentation skill.

---

## Part 1: WHAT — ADR Kya Hai?

### Definition

> **Architecture Decision Record (ADR)** = **short document** jisme ek important technical decision capture hoti hai — context, options, decision, consequences.

### Real-Life Analogy 📜

Soch ek **court judgment**:
- Case background (context)
- Arguments (options)
- Verdict (decision)
- Implications (consequences)

**ADR bilkul waisa hi** — technical decision ka "judgment."

### Example Decision

> "We're using PostgreSQL instead of MongoDB for our user database."

Without ADR: 6 months later, "kyu PostgreSQL liya tha?" Koi yaad nahi.

With ADR: Document hai — context, alternatives, reasoning.

---

## Part 2: WHY — ADR Kyu Zaroori?

### Reason 1: Institutional Memory

> Senior engineer left. Decisions ke peeche logic gaya. Naya engineer "why?" puchhe — koi nahi bata sakta.

ADR = team's collective memory.

### Reason 2: Onboarding

New developer joins. Sees codebase. **Why MongoDB? Why this architecture? Why this pattern?**

ADRs answer these.

### Reason 3: Avoid Re-Debating

Same decision discussed every 6 months because no record.

ADR = "We already decided this, here's why."

### Reason 4: Learning from Past

Decision worked? Document why.
Decision failed? Document for next time.

### Reason 5: Stakeholder Communication

Leadership asks "why microservices?" — ADR answers.

### Reason 6: Accountability

Who decided what, when, why. **No finger-pointing later.**

---

## Part 3: HOW — ADR Architecture

### When to Write ADR

> **Significant architectural decisions** that:
- Have long-term impact
- Are hard to reverse
- Affect multiple teams
- Cost money/time
- Choose between alternatives

### When NOT to Write ADR

- Trivial decisions (variable naming)
- Easily reversible (CSS color)
- Internal to single function
- No alternatives considered

### Real Examples — ADR-Worthy Decisions

```
✅ Database choice (PostgreSQL vs MongoDB)
✅ Framework choice (Django vs FastAPI)
✅ Authentication method (JWT vs Sessions)
✅ Cloud provider (AWS vs GCP)
✅ Architecture style (Monolith vs Microservices)
✅ Caching strategy (Redis vs Memcached)
✅ Message queue (Kafka vs RabbitMQ)
✅ Programming language (Python vs Go)
✅ API style (REST vs GraphQL vs gRPC)
✅ Deployment (Kubernetes vs ECS vs Lambda)
```

```
❌ Variable naming convention
❌ Linter rule choice
❌ Folder structure (minor)
❌ Test framework
```

---

## Part 4: ADR Template

### Standard Template

```markdown
# ADR-001: [Title — verb + noun]

**Date**: 2026-03-15
**Status**: Proposed / Accepted / Rejected / Deprecated / Superseded
**Deciders**: [Names of decision makers]
**Context**: [What's the situation?]

## Context

[Background. Why is this decision needed?]

## Decision

[What did we decide?]

## Consequences

### Positive
- [Good outcome 1]
- [Good outcome 2]

### Negative
- [Trade-off 1]
- [Trade-off 2]

### Risks
- [Risk 1]
- [Risk 2]

## Alternatives Considered

### Alternative 1: [Name]
- Pros: [...]
- Cons: [...]
- Why rejected: [...]

### Alternative 2: [Name]
- ...

## References

- [Link 1]
- [Link 2]
```

---

## Part 5: Writing Each Section

### Title

> **Verb + Noun.** Action-oriented.

✅ "Use PostgreSQL as Primary Database"
✅ "Adopt FastAPI for New Services"
✅ "Migrate to Kubernetes"

❌ "Database"
❌ "Backend Framework"
❌ "Kubernetes"

### Status

#### Proposed
> Decision drafted, awaiting approval.

#### Accepted
> Decision approved, being implemented.

#### Rejected
> Decision discussed but not taken. **Still document!**

#### Deprecated
> Was accepted, no longer applies. Keeping for history.

#### Superseded
> Replaced by newer ADR. Link to it.

### Context

> **Why are we deciding this?** Background. Problem.

Example:
> "Our user data is growing. Current SQLite database has reached its scalability limits with 100k users and 10M records. We need to choose a production database."

### Decision

> **What we decided.** Clear, definitive.

Example:
> "We will use PostgreSQL 15 hosted on AWS RDS as our primary database for all user data and transactional operations."

### Consequences

> **What will change because of this?**

#### Positive

> What benefits?

```
- Strong consistency guarantees (ACID)
- Mature ecosystem (Django ORM support)
- Skilled engineers available in market
- Proven for large-scale apps
```

#### Negative

> What trade-offs?

```
- Schema migrations require careful planning
- Vertical scaling limit (~few TB)
- Higher cost than self-hosted
```

#### Risks

> What could go wrong?

```
- RDS cost may exceed budget at 10x scale
- AWS vendor lock-in
- Backup strategy needs design
```

### Alternatives Considered

> **What else did we consider? Why rejected?**

This is **the most important section** for future readers.

```markdown
### Alternative 1: MongoDB

**Pros**:
- Flexible schema
- Better horizontal scaling
- JSON-native

**Cons**:
- No ACID across documents
- Less mature for our use case
- Team lacks experience

**Why rejected**: Our data is highly relational. 
Flexibility not needed. ACID critical for payments.

### Alternative 2: MySQL

**Pros**:
- Familiar
- Cheaper than PostgreSQL on RDS
- Adequate for our scale

**Cons**:
- Less feature-rich than PostgreSQL
- Slower JSON operations
- No native arrays

**Why rejected**: PostgreSQL has better feature
set for our roadmap (JSON, full-text search, etc.)
```

---

## Part 6: ADR Numbering

### Standard Convention

```
docs/adr/
├── 001-use-postgresql.md
├── 002-adopt-fastapi.md
├── 003-jwt-authentication.md
├── 004-redis-caching-layer.md
├── 005-kafka-event-bus.md
└── ...
```

**Sequential, never reused.** Even if ADR-003 is superseded, number stays.

---

## Part 7: ADR Lifecycle

### Phase 1: Identify Need

> "We need to choose X."

Discussion in Slack, meetings.

### Phase 2: Draft

> Engineer writes ADR with status "Proposed."

Includes:
- Context
- Proposed decision
- Alternatives
- Pros/cons

### Phase 3: Review

> Team reviews. Discussion. Iteration.

PR-based review (treat ADR like code).

### Phase 4: Decide

> Tech lead / Architecture team approves or rejects.

Update status: "Accepted" or "Rejected."

### Phase 5: Implement

> Decision now binding. Implementation begins.

### Phase 6: Live Forever

> ADR never deleted. Even if deprecated, kept for history.

---

## Part 8: Where to Store ADRs

### Option 1: In Git Repo

```
my-project/
├── docs/
│   └── adr/
│       ├── 001-use-postgresql.md
│       ├── 002-adopt-fastapi.md
│       └── README.md
```

**Pros**: Version controlled, PR review, lives with code
**Cons**: Mixed with code

### Option 2: Separate Docs Repo

```
company-docs/
├── architecture/
│   └── adrs/
```

**Pros**: Org-wide visibility
**Cons**: Disconnected from code

### Option 3: Confluence / Notion

**Pros**: Searchable, formatted
**Cons**: Not version controlled, can be edited silently

### Bhai's Recommendation

**In Git, with PR review.** Best of both worlds.

---

## Part 9: Real-World ADR Examples

### Example 1: Choosing Database

```markdown
# ADR-005: Use PostgreSQL for Primary Database

**Date**: 2026-03-15
**Status**: Accepted

## Context

We're building a SaaS application with:
- User accounts
- Subscription management
- Transactional data (payments)
- Reporting needs
- Expected scale: 1M users, 100M records

Current dev DB is SQLite. Need production-grade.

## Decision

Use PostgreSQL 15 hosted on AWS RDS.

## Consequences

### Positive
- ACID transactions for payments
- Excellent Python ecosystem (Django ORM, psycopg)
- Full-text search built-in
- JSON support for flexible data
- Mature, proven at scale

### Negative
- RDS cost (~$500/month at start)
- Requires careful migration management
- Vertical scaling has limits

### Risks
- AWS vendor lock-in
- Need DBA expertise for tuning at scale

## Alternatives Considered

### MongoDB
- Pros: Schema flexibility, horizontal scaling
- Cons: No ACID across docs, less mature for our needs
- Rejected: Strong consistency required for payments

### MySQL
- Pros: Familiar, cheaper
- Cons: Lacks advanced features we need
- Rejected: PostgreSQL feature set wins

### DynamoDB
- Pros: Serverless, infinite scale
- Cons: Limited query patterns, vendor lock-in
- Rejected: Not flexible enough for our queries

## References

- PostgreSQL vs MySQL comparison: [link]
- RDS pricing: [link]
- Team discussion: [Slack thread]
```

### Example 2: API Framework

```markdown
# ADR-008: Adopt FastAPI for Microservices

**Date**: 2026-04-01
**Status**: Accepted

## Context

Building 10+ microservices. Need framework with:
- Async support (high concurrency)
- Type safety
- Auto-generated OpenAPI docs
- Fast performance

## Decision

Use FastAPI for all new microservices. 
Existing Django services remain.

## Consequences

### Positive
- 5-10x performance vs Django (per benchmarks)
- Pydantic validation built-in
- Type hints first-class
- Async-native
- OpenAPI auto-gen

### Negative
- Smaller ecosystem than Django
- Need to build common patterns (auth, ORM)
- Team must learn async patterns

### Risks
- Team may struggle with async pitfalls
- FastAPI v1.0 not yet released (some volatility)

## Alternatives Considered

### Django
- Pros: Team experience, mature
- Cons: Sync-only (slower), heavy
- Rejected: Performance critical for microservices

### Flask
- Pros: Lightweight
- Cons: No async, no validation, no docs
- Rejected: Need modern features

### Starlette (raw)
- Pros: Even faster than FastAPI
- Cons: Lower level, more boilerplate
- Rejected: FastAPI gives best DX/perf balance

## Implementation Plan

1. Create FastAPI starter template
2. Document patterns (auth, db, testing)
3. Train team (1-week workshop)
4. Migrate 1 service as pilot
5. Roll out to other services

## References

- FastAPI docs: [link]
- Performance comparison: [link]
- Pilot service plan: [link]
```

### Example 3: Caching Strategy

```markdown
# ADR-012: Add Redis Caching Layer

**Date**: 2026-05-10
**Status**: Accepted

## Context

API p95 latency is 800ms. Database queries
account for 600ms. Most queries are repeated.

Need caching to reduce latency.

## Decision

Add Redis 7 as caching layer.
Use cache-aside pattern for read-heavy queries.

## Cache Strategy

- TTL: 5 minutes for product catalog
- TTL: 1 hour for user profiles
- Manual invalidation on write
- 16 GB Redis cluster (3 nodes)

## Consequences

### Positive
- p95 latency: 800ms → 150ms (estimated)
- Database load reduced ~70%
- Better user experience

### Negative
- Added infrastructure (~$200/month)
- Cache invalidation complexity
- Cache stampede risk

### Risks
- Stale data if invalidation buggy
- Redis outage → fall back to DB (handle gracefully)

## Alternatives Considered

### Memcached
- Pros: Simple, fast
- Cons: No persistence, no data structures
- Rejected: Need lists/sets for some features

### In-Memory (LRU)
- Pros: No infra
- Cons: Not shared across instances
- Rejected: Multi-instance deployment

### CDN Caching
- Pros: Edge caching
- Cons: Only HTTP responses
- Rejected: Need to cache DB queries

## References

- Redis docs
- Cache patterns guide
```

---

## Part 10: ADR Anti-Patterns

### Anti-Pattern 1: Too Late

> ADR written after implementation. "We did this because..."

Should be **before** decision. Capture reasoning.

### Anti-Pattern 2: No Alternatives

> "Decided to use X."

What else considered? Why X? **Always document alternatives.**

### Anti-Pattern 3: Vague Reasoning

> "X is better than Y."

Better how? Faster? Cheaper? More features?

### Anti-Pattern 4: Editing After Acceptance

> Status: Accepted → someone changes decision.

**Bad!** Create new ADR that supersedes old.

### Anti-Pattern 5: Too Long

> 30-page ADR with code samples.

ADR is **decision document**, not implementation guide.

### Anti-Pattern 6: ADR Tax

> "Every change needs ADR."

No. Only architectural decisions.

---

## Part 11: ADR vs Other Docs

### ADR vs RFC

- **RFC**: Request for Comments (proposal stage)
- **ADR**: Accepted decision (decision stage)

Sometimes RFC becomes ADR after approval.

### ADR vs Design Doc

- **Design Doc**: How to implement (detailed)
- **ADR**: What we decided (high-level)

Design doc references ADR. ADR doesn't include implementation.

### ADR vs Postmortem

- **Postmortem**: Incident analysis (reactive)
- **ADR**: Architectural decision (proactive)

Both important. Different purposes.

### ADR vs README

- **README**: How to use/run
- **ADR**: Why we built it this way

---

## Part 12: When to Supersede ADR

### Scenario

> 6 months ago, ADR said "use MongoDB."
> Now, MongoDB causing issues. Want to switch to PostgreSQL.

### Wrong Approach

❌ Edit ADR-005 to say "use PostgreSQL"

### Right Approach

✅ Create new ADR-023: "Migrate from MongoDB to PostgreSQL"
- Reference ADR-005
- Explain what changed
- Mark ADR-005 status: "Superseded by ADR-023"

### Why This Matters

**History matters.** Future reader sees:
- We chose MongoDB
- After 6 months, learned X
- Switched to PostgreSQL because Y

Learning preserved.

---

## Part 13: ADR Tools

### MADR (Markdown ADR)
> Lightweight template. Most popular.

### adr-tools
> CLI tool to manage ADRs.
- Create new ADR
- Number automatically
- Link superseded

### Log4brains
> Web UI for ADRs.

### Notion / Confluence Templates
> If you use these tools, use their template.

---

## Part 14: ADR Best Practices

### DO

✅ Keep them short (1-2 pages)
✅ Use clear titles
✅ Document alternatives
✅ Include trade-offs
✅ Number sequentially
✅ Treat like code (PR review)
✅ Make searchable

### DON'T

❌ Edit accepted ADRs
❌ Skip alternatives section
❌ Make them implementation guides
❌ Hide them (Confluence behind permissions)
❌ Write retroactively (ideally)

---

## Part 15: ADR Adoption Strategy

### Starting from Scratch

#### Week 1: Educate Team
- Show examples
- Pick template
- Decide storage location

#### Week 2: First ADR
- Take recent decision
- Write ADR
- Get feedback

#### Week 3: Make It Habit
- "Any architectural decision needs ADR"
- Add to definition of done
- Reviewers ask "where's the ADR?"

#### Month 2+: Mature Practice
- Regular ADRs
- Reference in code reviews
- Onboarding docs link

### Backfill Old Decisions

Don't need to ADR every past decision.
Just **important ones** for future reference.

---

## Part 16: ADR in Different Contexts

### Small Team (3-5 engineers)

Lightweight ADRs. Maybe just title + decision + reason. 1 page max.

### Medium Team (10-30 engineers)

Standard template. Reviewed by tech lead.

### Large Team (50+ engineers)

Formal process. Architecture review board. RFC stage first.

### Open Source

Public ADRs. Educational for community.

---

## Part 17: Famous Public ADRs (Read These!)

### Companies Sharing Publicly

1. **Spotify** — engineering blog, decision posts
2. **Netflix** — tech blog, architecture decisions
3. **Adobe** — open source ADRs on GitHub
4. **GitHub** — public RFCs

### Open Source Projects with ADRs

1. **Kubernetes** — KEPs (similar)
2. **Rust** — RFCs (public)
3. **Python** — PEPs (similar)

Read these to see professional examples.

---

## Part 18: Q&A

### Q: How long should an ADR be?
**A**: 1-3 pages. If longer, you're including implementation details.

### Q: Can ADR be rejected?
**A**: Yes! Document why. Future engineers might revisit.

### Q: Do I need ADR for small decisions?
**A**: No. Only architectural ones with long-term impact.

### Q: Should AI write ADRs?
**A**: AI can draft. Human must own decision and reasoning.

### Q: What if I disagree with old ADR?
**A**: Write new ADR superseding old, with new reasoning.

### Q: ADR not approved — what now?
**A**: Discuss. Iterate. Or pick different approach.

### Q: Where to start as a beginner?
**A**: Find recent decision your team made. Write retrospective ADR. Get feedback.

---

## 🎯 Bhai's Final Words

> **ADR senior engineer ka signature hai. Junior writes code. Senior writes decisions.**

3 Mantras:
1. **Document decisions, not code**
2. **Always include alternatives**
3. **Never edit history**

Start writing ADRs **today** for next architectural decision. After 10 ADRs, you'll see clearly why this practice is gold. 🚀
