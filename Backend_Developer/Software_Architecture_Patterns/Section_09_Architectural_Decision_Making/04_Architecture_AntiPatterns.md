# Lecture 4: Architecture Anti-Patterns & Real-World Failures

> *"Anti-patterns usually come from good intentions gone unchecked."*

**Section 9 — Architectural Decision-Making & Trade-offs**

---

## 🎯 Is Lecture Mein Kya Seekhenge?

- **What are architecture anti-patterns**
- **Chatty microservices** — too much talk, too little work
- **Over-modularization** — modular for the sake of modular
- **God classes / Everything controllers** — the legacy classics
- **Hidden cost** — latency, burnout, slow rollouts
- **Early warning signs** to spot them
- **Recovery strategies**

---

## 1. What is an Architecture Anti-Pattern?

```
Repeated poor solution to a recurring design problem

Looks logical at first glance
Consistently leads to bad outcomes

Origin:
   ✓ Over-engineering (trying to be clever)
   ✓ Ignorance of real constraints
   ✓ Cargo-culting trends
   ✓ Premature optimization

Impact:
   ✓ Technical debt
   ✓ Slow performance
   ✓ Hard debugging
   ✓ Slow onboarding
   ✓ Painful releases
   ✓ Team burnout
```

**Good news**: spot them early → recover cheaply.

---

## 2. Anti-Pattern #1: Chatty Microservices

### What It Looks Like

```
Single user request →

  API Gateway
       │
       ▼
   UserService ──► NameService ──► AddressService ──► PrefService
       │
       ▼
   OrderService ──► ProductService ──► InventoryService ──► PriceService
       │
       ▼
   ... 17 more calls ...

   p99 latency: 8 seconds
   1 service down → entire request fails
```

### Why It Happens

```
✗ Over-decomposition
   - Splitting responsibilities too finely
   - "Each thing should be its own service"

✗ Service-per-table anti-pattern
   - Microservices designed around data, not capability

✗ Missing domain analysis
   - No bounded contexts → arbitrary boundaries
```

### Why It's Bad

```
✗ Network latency multiplies
✗ Failure domains explode
✗ Tracing becomes essential just to debug "what called what"
✗ Operational toil per service
✗ Violates microservices principle:
   service should own a full business capability
```

### Recovery

```
✓ Identify hot paths (most-traveled call chains)
✓ Merge related services back into one
✓ Use Backend-for-Frontend (BFF) to aggregate calls
✓ Co-locate frequently-accessed data
✓ Cache aggressively at boundaries
```

---

## 3. Anti-Pattern #2: Over-Modularization

### What It Looks Like

```
Project structure:

  src/
   ├── domains/
   │   ├── user/
   │   │   ├── creation/
   │   │   │   ├── service/
   │   │   │   │   ├── interface/
   │   │   │   │   ├── implementation/
   │   │   │   │   ├── factory/
   │   │   │   │   ├── adapter/
   │   │   │   │   └── helper/
   │   │   │   ├── validator/
   │   │   │   ├── normalizer/
   │   │   │   ├── persistence/
   │   │   │   └── 12 more folders ...

To add a "middle name" field → touch 7 files,
understand 4 abstractions, align 2 teams.
```

### Why It Happens

```
✗ Misapplied "clean code" / "separation of concerns"
✗ Layering for layering's sake
✗ Premature abstraction
✗ Pattern-matching from books without context
```

### Why It's Bad

```
✗ Cognitive load multiplies
✗ Every change is a coordination problem
✗ Onboarding takes weeks
✗ Wrapper layers add zero value
✗ Symptoms:
   - Circular dependencies
   - Helper classes everywhere
   - Adapters wrapping adapters
   - 5x file count vs feature count
```

### Recovery

```
✓ Inline simple wrappers
✓ Collapse single-use abstractions
✓ Apply "rule of three" — abstract only after 3rd duplicate
✓ Prefer cohesion over arbitrary separation
✓ Measure: file count per feature → trend down
```

### Healthy Modularity

```
Modularity is about MEANINGFUL grouping, not maximum splitting.
```

---

## 4. Anti-Pattern #3: God Class / Everything Controller

### What It Looks Like

```
class UserController:
    def create_user(self, ...): ...
    def update_user(self, ...): ...
    def delete_user(self, ...): ...
    def send_password_reset(self, ...): ...
    def authenticate(self, ...): ...
    def authorize(self, ...): ...
    def calculate_billing(self, ...): ...
    def export_report(self, ...): ...
    def send_email(self, ...): ...
    def cache_session(self, ...): ...
    def encrypt_token(self, ...): ...
    def upload_avatar(self, ...): ...
    def search_users(self, ...): ...
    # ... 2,341 more lines ...
```

### Why It Happens

```
✗ "Just one more method, this fits here"
✗ Deadline pressure
✗ Path of least resistance
✗ Silent growth — no one says "no" early enough
```

### Why It's Bad

```
✗ Violates Single Responsibility Principle
✗ Dependency magnet:
   - Everything depends on it
   - Every change risks breaking many features

✗ Untestable:
   - Massive setup
   - Brittle mocks

✗ Zero reusability

✗ Centralization creates coupling at scale
```

### Recovery

```
✓ Identify responsibilities (look at method clusters)
✓ Extract by domain (auth/, billing/, profile/, ...)
✓ Move via strangler fig pattern (route calls to new class incrementally)
✓ Add tests at the seams as you split
```

---

## 5. Hidden Costs

### Performance Costs

```
✗ Latency under peak traffic
✗ Bloated controllers choke under load
✗ Tangled modules add CPU + network overhead
```

### Human Costs

```
✗ Wading through complex code for tiny fixes
✗ Frustration → burnout
✗ Velocity drops
✗ Turnover rises
```

### Delivery Costs

```
✗ Simple change ripples across many services/modules
✗ A 1-day task becomes a week
✗ Releases get scary
```

### Recovery Costs

```
✗ Rewrites
✗ Re-architectures
✗ Team retraining

→ The longer you wait, the more expensive it gets.
```

---

## 6. Early Warning Signs

### Spot Them Before They Spread

```
✗ Too many services / modules that do little
   → over-modularization brewing

✗ Central controller growing in size + responsibility
   → God class in the making

✗ Cross-team meetings for minor changes
   → boundaries are wrong, responsibilities unclear

✗ A small service failure causes unrelated outages
   → hidden tight coupling

✗ Build times growing faster than features
   → architecture is fighting you

✗ New devs take > 2 weeks to ship anything
   → cognitive load is too high
```

### Action Triggers

```
Weekly retrospective question:
   "What surprised us this week about the system?"
   → Surprises = hidden coupling / hidden complexity
```

---

## 7. Real-World Failure Stories (Brief)

### Story 1: The Microservices Migration That Killed Velocity

```
Mid-size company split monolith into 23 services for "scale."
Result:
   ✗ Latency went UP (more network hops)
   ✗ Velocity went DOWN (every change touches 5 services)
   ✗ Required 4 SREs to keep it running

Recovery: consolidated back to 6 services.
Lesson: scale wasn't the problem. Team size was.
```

### Story 2: The God Service in a Microservices App

```
"AuthService" started doing auth.
6 months later: auth + user CRUD + permissions + billing + notifications.
One bug fix → entire org's deploys frozen for 3 days.

Recovery: extracted by domain over 6 months using strangler fig.
Lesson: anti-patterns don't care about your architecture style.
```

### Story 3: The Folder Explosion

```
"Clean architecture" project: 412 files for a 30-screen app.
New devs took 6 weeks to ship first PR.

Recovery: collapsed adapters/interfaces with single implementation.
File count: 412 → 89. Velocity: 4x.
Lesson: modularity must add value, not just files.
```

---

## 8. Summary

```
✓ Anti-patterns come from good intentions
   - Don't start as bad decisions
   - Grow silently when unchecked

Three big ones:
   1. Chatty microservices
   2. Over-modularization
   3. God classes / everything controllers

Real value = learning from failure stories
   → Builds architectural instinct
   → Documentation can't teach this

Good architecture:
   ✓ Cohesion — group right things together
   ✓ Context awareness — patterns that fit team + product
   ✓ Design for change — systems WILL evolve
```

---

## 🎤 Interview Q&A

**Q1. What's the difference between chatty microservices and necessary service-to-service communication?**

A: Necessary communication serves a real business capability — Service A needs data Service B owns to complete its job. Chatty communication is when a single request fans out to 20+ services because boundaries were drawn wrong (e.g., service-per-table). The smell: removing one service breaks the user-facing feature in ways no one expected.

**Q2. How do you tell over-modularization from healthy modularity?**

A: Healthy modularity reduces cognitive load — modules align with how engineers think about the domain. Over-modularization adds layers without adding clarity. A test: ask a new engineer to explain the structure. If they can do it in 5 minutes, it's healthy. If they need a diagram and 30 minutes, it's likely over-modular.

**Q3. How do you recover from a God class without breaking everything?**

A: Strangler fig pattern. Identify one responsibility (e.g., billing). Create a new, focused class. Route new code paths through it. Migrate old call sites gradually, behind feature flags. Add tests at every seam. After all callers migrated, delete the old methods. Repeat per responsibility. Months, not weeks — but no big-bang risk.

**Q4. Why don't anti-patterns get caught earlier?**

A: They grow incrementally. Each individual change "makes sense in isolation." No one PR introduces the God class — 500 PRs do. Counter with explicit reviews of architecture-level metrics (file count growth, service-call depth, controller line count) at the team level, not the PR level.

**Q5. What's the biggest red flag in a code review that hints at an anti-pattern?**

A: Reviewers asking "where does this logic actually belong?" with no clear answer. If responsibility isn't obvious, the architecture isn't communicating its intent — and you're heading toward either a God class (it'll go in the convenient class) or fragmentation (it'll get its own micro-module). Either way: stop, clarify the model first.

---

## 🔗 Related

- Previous: [03_Pattern_Selection_Framework.md](03_Pattern_Selection_Framework.md)
- Next: [05_Domain_Driven_Design_Influence.md](05_Domain_Driven_Design_Influence.md)
