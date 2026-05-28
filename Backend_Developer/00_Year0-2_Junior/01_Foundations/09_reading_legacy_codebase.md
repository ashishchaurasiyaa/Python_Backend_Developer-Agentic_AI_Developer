# 📚 Reading Legacy Codebase — Architecture Survival Guide

> **Target:** 0-2 YOE | **Goal:** Onboard kisi bhi codebase me, samjho code kya kar raha hai, kaise navigate karo — bina ghante waste kiye.

---

## Part 1: WHAT — Legacy Code Kya Hai?

### Definition

> **Legacy code** = jo code tujhse pehle kisi aur ne likha hai aur ab tujhe samjhna/modify karna hai. **Naya code likhne se zyada mushkil.**

### Real-Life Analogy 🏠

Soch tu ek **purana ghar khareeda** hai:
- Pichle owner ne kya banaya tha?
- Plumbing kahaan se jaati hai?
- Electric wiring kis pattern me?
- Kuch dewar load-bearing hai, kuch nahi?

Pehle din se hi tu repair start nahi kar sakta — **samjhna padega pehle**.

**Legacy code bilkul waisa hi.**

---

## Part 2: WHY — Legacy Reading Skill Critical Kyu?

### Reality Check

> **90% of your career, you'll work on legacy code, not greenfield projects.**

- Naya project: 10% time
- Existing code samjhna + modify: 90% time

### Reason 1: First Day Onboarding

New job, 5 lakh lines of code. Productive kab banoge?
- **Without skill**: 3-6 months
- **With skill**: 2-4 weeks

### Reason 2: Bug Fixing

Bug aaya. Code samjhna padega pehle. Direct fix kiya = bigger bug.

### Reason 3: Feature Addition

Feature add karne se pehle existing flow samjho, warna conflicts.

### Reason 4: Refactoring

Code clean karne ke liye pehle context chahiye.

### Reason 5: Senior Skill

Senior developer **kisi bhi codebase me drop kar do** — kuch dino me productive. Yeh skill hi senior banata hai.

---

## Part 3: HOW — Codebase Navigation Architecture

### The 4-Layer Approach

```
┌─────────────────────────────────────────┐
│  LAYER 1: BIG PICTURE                   │
│  - What does the system do?             │
│  - Architecture diagram                  │
│  - High-level data flow                  │
├─────────────────────────────────────────┤
│  LAYER 2: STRUCTURE                     │
│  - Folder organization                   │
│  - File naming conventions               │
│  - Module boundaries                     │
├─────────────────────────────────────────┤
│  LAYER 3: PATTERNS                      │
│  - Design patterns used                  │
│  - Coding style                          │
│  - Common abstractions                   │
├─────────────────────────────────────────┤
│  LAYER 4: SPECIFIC CODE                 │
│  - Read specific files                   │
│  - Trace execution paths                 │
│  - Understand functions                  │
└─────────────────────────────────────────┘
```

**Top-down approach** — never start with random file.

---

## Part 4: Day 1 — Big Picture Strategy

### Step 1: Read README.md (Carefully)

Most repos have README. Read it like a book:
- What does this project do?
- How to set it up?
- Architecture decisions?
- Tech stack?

### Step 2: Look for Architecture Docs

- `/docs` folder
- ADRs (Architecture Decision Records)
- Wiki / Confluence
- Diagrams (PlantUML, mermaid)

### Step 3: Find Entry Points

Every project has **entry points** — code start here.

| Project Type | Entry Point |
|--------------|-------------|
| Django | `manage.py`, `urls.py` |
| FastAPI | `main.py` (uvicorn) |
| Flask | `app.py` |
| Script | `__main__` block |
| Library | `__init__.py` of package |

**From entry point, trace outward.**

### Step 4: Get a Mental Map

Don't start coding yet. **Just understand.**
- What problems does this solve?
- Who uses it?
- What are the main user flows?

---

## Part 5: Day 2-3 — Structure Understanding

### Folder Organization Patterns

#### Pattern 1: Domain-Driven (Modern)
```
src/
├── users/
│   ├── models.py
│   ├── views.py
│   ├── serializers.py
│   └── services.py
├── orders/
│   ├── models.py
│   └── ...
└── products/
    └── ...
```

#### Pattern 2: Layer-Based (Traditional)
```
src/
├── models/
│   ├── user.py
│   ├── order.py
│   └── product.py
├── views/
├── services/
└── utils/
```

#### Pattern 3: Django Convention
```
project/
├── manage.py
├── settings/
├── apps/
│   ├── users/
│   ├── orders/
│   └── products/
└── core/
```

### Reading Folders

```
Start with:
1. README.md
2. Top-level configuration (settings.py, .env.example)
3. Main entry point
4. URL routing / Route definitions
5. Models (data structures)
6. Then views/controllers (business logic)
7. Then services/utilities (helpers)
```

---

## Part 6: Day 4-5 — Patterns Recognition

### Common Patterns to Spot

#### MVC / MVT
- **Model**: Database table representation
- **View**: HTTP request handler
- **Template/Controller**: UI / response logic

#### Repository Pattern
```
services/
├── user_repository.py    ← all user DB queries here
├── order_repository.py
```

#### Service Layer
```
services/
├── auth_service.py       ← business logic
├── payment_service.py
```

#### Factory Pattern
Object creation in one place.

#### Singleton
Single instance shared everywhere.

### Spotting Patterns Quickly

- File names tell pattern (`*_repository.py`, `*_service.py`)
- Folder names (`repositories/`, `services/`)
- Class names (`UserManager`, `OrderFactory`)

---

## Part 7: Reading Code — The Process

### Step 1: Don't Read Linearly

Don't start at `main.py` line 1 and go down. **Read by purpose.**

### Step 2: Use Search Aggressively

When you need to understand something:
- `Cmd+P` (Quick Open) — find file
- `Cmd+Shift+F` — search across files
- `Cmd+Click` — jump to definition
- `F12` — go to definition

### Step 3: Follow the Trace

Pick one user flow, trace it:

```
User logs in
   ↓
Trace: /login endpoint
   ↓
Find: views/auth.py → login_view()
   ↓
Read: which serializer used?
   ↓
Find: serializers/auth.py → LoginSerializer
   ↓
Read: which service called?
   ↓
Find: services/auth_service.py → authenticate()
   ↓
Read: which DB queries?
   ↓
Done — full flow understood
```

**Trace one flow fully > read 100 random files.**

### Step 4: Use Debugger

Run code with debugger, put breakpoint, **watch execution**.
- See actual values
- Step through line by line
- Best teacher

### Step 5: Read Tests

Tests show **how code is meant to be used**. Often clearer than implementation.

```
test_user_can_login()    ← shows login flow
test_admin_can_delete()  ← shows admin flow
```

---

## Part 8: Architecture-Level Investigation

### Question to Ask

#### About the Project
1. What problem does it solve?
2. Who are users?
3. What are core features?

#### About Tech
4. Tech stack? Languages, frameworks, databases?
5. Why these choices?
6. What scale (users, requests/day)?

#### About Architecture
7. Monolith or microservices?
8. Sync or async?
9. Caching layer?
10. Background tasks?

#### About Data
11. Main database tables?
12. Relationships?
13. Data flow?

#### About Deployment
14. Where hosted? (AWS, GCP, on-prem)
15. CI/CD pipeline?
16. Monitoring?

**Make a 1-page summary** when answering these.

---

## Part 9: Tools for Reading Code

### IDE Features

**VS Code:**
- `F12` — Go to definition
- `Shift+F12` — Find all references
- `Ctrl+T` — Search symbol
- `Cmd+Shift+O` — File outline
- Breadcrumbs at top

**PyCharm:**
- Same shortcuts
- "Find Usages" deeper
- Diagram view (paid)

### Static Analysis Tools

- **pyreverse** — generates class diagrams
- **pydeps** — module dependency graph
- **Sourcegraph** — searchable code map

### Git Tools

- **git blame** — who wrote this line, when, why
- **git log -p file.py** — history of changes
- **git log --grep="bug fix"** — find commits by keyword

### Documentation Tools

- **Sphinx-generated docs** — if available
- **OpenAPI/Swagger** — for APIs

---

## Part 10: Git Archaeology (Reading History)

### Why Git History Matters

Often, **why** code is written a certain way is in **commit history**.

### Useful Investigations

#### `git blame`
> Who wrote this line? When? Which commit?

Right-click → "Open Git Blame" in IDE.

#### Commit Message Reading
```
fix: prevent SQL injection in user search
- Added parameterized queries
- See JIRA-1234
```

Often explains **why** code is written certain way.

#### PR History
GitHub PR me discussions:
- Why this approach?
- What alternatives rejected?
- Review feedback

### When to Investigate

- "This code looks weird" → check history
- "Why this hack?" → blame + commit
- "Can I remove this?" → check who depends

---

## Part 11: Communication — Ask Questions Right

### The Art of Asking

#### Bad Question
> "How does this work?"

Too vague. Senior won't answer.

#### Good Question
> "I'm trying to understand the order workflow. I see `order_service.py` calls `payment_service.py`. But I can't find where webhook validates the payment. Did I miss it?"

Specific, shows effort, easier to answer.

### Where to Ask

1. **Codebase comments** — often answer is here
2. **README / docs** — read first
3. **Slack / Teams** — for team
4. **Tech lead / Mentor** — last resort

### Document Answers

Got answer? **Write it down somewhere** — wiki, personal notes. Next person benefits.

---

## Part 12: Common Legacy Code Smells

### Smell 1: Giant Files
Files with 2000+ lines = nightmare. Multiple responsibilities mixed.

### Smell 2: God Classes
Classes that "do everything" — User, Order, Payment all in one.

### Smell 3: Magic Numbers/Strings
```python
if user.status == 5:  # what does 5 mean?
```
Better: `if user.status == STATUS_ACTIVE`.

### Smell 4: Copy-Paste Code
Same logic in 10 files. Bug fix needs 10 places.

### Smell 5: No Tests
Can't safely change anything.

### Smell 6: Outdated Dependencies
Security issues, performance issues.

### Smell 7: Mixed Languages
Python + bash + JS + SQL in one file = nightmare.

### What to Do?

Don't refactor everything immediately. Make a **tech debt list**. Address gradually.

---

## Part 13: Mental Models for Legacy Code

### Model 1: Layered Onion

```
       OUTSIDE
    ┌────────────┐
    │  HTTP      │
    │  ┌─────────┐
    │  │  ROUTES │
    │  │  ┌──────┐
    │  │  │ VIEWS│
    │  │  │ ┌────┐
    │  │  │ │SVC │
    │  │  │ │┌───┐
    │  │  │ ││DB │
    │  │  │ │└───┘
    │  │  │ └────┘
    │  │  └──────┘
    │  └─────────┘
    └────────────┘
```

Outer layers → inner layers (one direction).

### Model 2: City Map

Codebase = city. Folders = neighborhoods. Files = buildings. Don't try to map whole city day 1 — start with your neighborhood.

### Model 3: Family Tree

Class inheritance = family tree. Parent classes, child classes, mixins.

### Model 4: Pipeline

Data flows through stages. Find pipe stages, understand transformations.

---

## Part 14: Strategies for Different Project Types

### Strategy 1: Django Project

```
1. Read settings.py (configuration)
2. Read urls.py (routes)
3. For each app:
   - models.py (data)
   - views.py (logic)
   - serializers.py (API format)
4. Check signals.py (event-driven code)
5. Check middlewares
6. Look at admin.py for data view
```

### Strategy 2: FastAPI Project

```
1. Read main.py (app setup)
2. Read routers/ (endpoints)
3. Read models/ (Pydantic + DB)
4. Read services/ (business logic)
5. Check dependencies/ (DI)
6. Check middleware
7. Check exception handlers
```

### Strategy 3: Generic Python Lib

```
1. Read README
2. Read setup.py / pyproject.toml (dependencies)
3. Read __init__.py (public API)
4. Read main module
5. Check tests/ for usage examples
```

### Strategy 4: Microservices

```
1. Identify each service
2. Map service-to-service communication
3. Find shared contracts (proto files, OpenAPI specs)
4. Pick ONE service, learn deeply
5. Then expand
```

---

## Part 15: Time Estimates

### Realistic Expectations

| Codebase Size | Time to Productive |
|---------------|---------------------|
| < 10k lines | 1-3 days |
| 10k-100k lines | 1-3 weeks |
| 100k-1M lines | 1-3 months |
| > 1M lines | 6+ months for parts |

**Senior devs accept**: you'll never know all of large codebase. Just know **your area**.

---

## Part 16: First Week Checklist

### Day 1
- [ ] Read README
- [ ] Set up local environment
- [ ] Run the app
- [ ] Make first API call
- [ ] Understand high-level architecture

### Day 2
- [ ] Identify main folders
- [ ] Map URL routes to view files
- [ ] Read 3-5 model files
- [ ] Understand data model

### Day 3
- [ ] Trace one user flow end-to-end
- [ ] Read related tests
- [ ] Run tests successfully

### Day 4
- [ ] Pick a small bug or task
- [ ] Make first change
- [ ] Submit first PR

### Day 5
- [ ] Get PR reviewed
- [ ] Iterate on feedback
- [ ] Merge!

### Week 1 Goal
**One successful PR.** Doesn't matter how small.

---

## Part 17: Code Reading Routine

### Daily Practice (15 min/day)

Pick a random file in codebase, read it, ask:
- What does this file do?
- Who calls this code?
- What does it depend on?
- How would I test it?
- How would I improve it?

After 6 months — you'll know the codebase intimately.

---

## Part 18: When Stuck

### The Debugger Strategy

```
1. Set breakpoint at top of suspected function
2. Run with debugger
3. Step through line by line
4. Watch variables
5. Understand flow
```

**1 hour debugger > 10 hours reading**.

### The Print Strategy (Cave-man Debug)

```
print("Got here, value is:", value)
```

Yes, professional devs still do this.

### The Test Strategy

Write a test that uses the function. **Writing test = understanding code.**

### The Rubber Duck

Explain code to inanimate object. Often, you realize the answer mid-explanation.

---

## Part 19: Avoid Common Pitfalls

### Pitfall 1: Reading Top-to-Bottom
**Wrong**: Open file, read line 1 to end.
**Right**: Find entry, trace specific flow.

### Pitfall 2: Trying to Understand Everything Day 1
**Wrong**: Read entire 100k line codebase first day.
**Right**: Pick one slice, learn it deeply.

### Pitfall 3: Not Running the App
**Wrong**: Just read code.
**Right**: Run it, debug, see actual behavior.

### Pitfall 4: Not Reading Tests
**Wrong**: Skip tests folder.
**Right**: Tests = documentation by example.

### Pitfall 5: Refactoring Too Early
**Wrong**: "This is bad code, let me rewrite."
**Right**: Understand first, then propose changes.

### Pitfall 6: Not Asking for Help
**Wrong**: Stuck for 3 days, no questions asked.
**Right**: 30 min stuck → ask team.

---

## Part 20: Q&A

### Q: Senior on team doesn't want to explain code, what do?
**A**: Self-learn via debugger, read tests, ask specific questions. Don't ask "explain everything"; ask "how does X work between Y and Z?"

### Q: Code has no docs, no tests. What now?
**A**: Add docs and tests yourself as you learn. Document your learning.

### Q: How long should I take to feel productive?
**A**: 2-4 weeks for typical projects. 2-3 months for very complex ones. If 6 months and still lost, ask for help.

### Q: Should I trust legacy code or rewrite?
**A**: 99% — trust and learn. Legacy works because it solved real problems. Rewrites usually fail.

### Q: When can I criticize code?
**A**: After 3 months. You'll likely understand why "weird" code is that way.

---

## 🎯 Bhai's Final Words

> **Legacy code reading is the #1 skill that separates good from great developers. New code likhna sab seekh leta hai. Purana code samjhna — wahi tujhe seniority dilata hai.**

3 Golden Rules:
1. **Patience** — Slow down, understand before changing
2. **Trace, don't read** — Follow execution paths
3. **Ask & document** — Help future you

Practice on open source projects on GitHub. Pick a project, spend a week understanding it. Repeat. 🚀
