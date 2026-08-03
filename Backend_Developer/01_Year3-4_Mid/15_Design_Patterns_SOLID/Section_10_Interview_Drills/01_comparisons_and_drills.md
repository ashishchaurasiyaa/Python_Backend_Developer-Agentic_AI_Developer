# Interview Drills — Comparisons, Callouts & 15-Minute Tasks

> Patterns get tested three ways: **"X vs Y?"**, **"where would you use X?"**, and **"refactor this."** All three are drilled here. Answer out loud before reading the answer.

## 1. The comparison table (memorize the one-liners)

| Pair | The distinction that settles it |
|---|---|
| **Adapter vs Facade** | Adapter changes an interface to one the client expects (1 object, incompatible API). Facade *simplifies* access to many objects (N objects, complex API). |
| **Strategy vs State** | Same structure, different intent: Strategy is chosen by the **client** and variants don't know each other; State is chosen by the **object itself** and states trigger transitions. |
| **Factory Method vs Abstract Factory** | Factory Method = one product, chosen by subclass. Abstract Factory = a *family* of related products kept consistent. |
| **Builder vs Factory** | Factory: one call, object done. Builder: step-by-step construction for many optional params/representations. |
| **Decorator vs Proxy** | Decorator *adds* behavior, stackable, client opts in. Proxy *controls access* (lazy, cache, permission) with the same interface — usually transparent. |
| **Decorator vs Inheritance** | Decorator composes at runtime; inheritance fixes it at compile/class time. |
| **Observer vs Mediator** | Observer = one-to-many broadcast, publisher doesn't know subscribers. Mediator = many-to-many coordination, hub knows all colleagues. |
| **Chain of Responsibility vs Decorator** | CoR: any handler may **stop** the chain. Decorator: everyone runs, wrapping the result. |
| **Template Method vs Strategy** | Template = inheritance, skeleton fixed, hooks vary. Strategy = composition, whole algorithm swapped. |
| **Composite vs Decorator** | Composite = tree of *many* children (part-whole). Decorator = exactly *one* wrapped child. |
| **Repository vs DAO** | DAO ≈ per-table CRUD, DB-shaped. Repository is domain-shaped (collection illusion), may span tables. |
| **Repository vs Active Record** | AR: object persists itself (Django). Repository: separate object persists it (SQLAlchemy/DDD). |
| **Unit of Work vs Transaction** | Transaction is the DB primitive; UoW is the app-side change tracker that decides *what* goes in one transaction. |
| **DI vs Service Locator** | DI pushes dependencies in (explicit, testable). Service Locator pulls them from a global registry (hidden dependency — usually an anti-pattern). |

---

## 2. Rapid-fire "where would you use…?" (backend answers)

```
Strategy   → pricing per market, retry policies, storage backends, rate-limit algos
State      → order lifecycle (pending→paid→shipped), subscription status machine
Observer   → domain events (user.registered → email + analytics + CRM)
Command    → Celery tasks, undo stacks, request queues, audit logs
Adapter    → wrapping a 3rd-party SDK behind your own interface
Facade     → one `OnboardingService` over auth+billing+email+provisioning
Decorator  → @retry, @cache, @authorize; wrapping a Storage with encryption
Proxy      → cache-aside repo, lazy DB relationships, permission gate
Factory    → building the right notification channel from config
Builder    → complex query/report construction, test data builders
Composite  → nested comment trees, Celery chains-of-groups, permission trees
CoR        → middleware stacks, validation pipelines, escalation rules
Template   → CBVs, Celery Task base classes, ETL skeletons
Mediator   → chat room fan-out, workflow orchestrator, consumer-group coordinator
Flyweight  → interned config objects, lru_cache'd parsers/compiled regexes
```

---

## 3. Callout drills — name the smell, prescribe the pattern

**Drill 1.** A `PaymentService` has a 9-branch `if provider ==` ladder, repeated in `charge()`, `refund()`, and `webhook()`.
<details><summary>Answer</summary>Smell: Switch Statements + Shotgun Surgery. Cure: **Strategy** per provider (or a registry dict of provider objects), so a new provider adds one class, not three edits. If providers also need *families* of related objects (client + webhook parser + reconciler), escalate to **Abstract Factory**.</details>

**Drill 2.** `Order.save()` sends email, writes an audit row, calls the warehouse API, and updates a cache.
<details><summary>Answer</summary>Smell: God Object / SRP violation, plus hidden side effects in persistence. Cure: emit a **domain event** (Observer) or explicit application service that orchestrates; keep `save()` about persistence. Transactional safety → **outbox pattern**, not signals.</details>

**Drill 3.** Tests need a real Redis and real Stripe to run.
<details><summary>Answer</summary>Smell: concrete dependencies wired inside functions. Cure: **Dependency Injection** at the boundary (FastAPI `Depends`, constructor injection) + **Adapter** interfaces, then fakes in tests. Note the seam is what you're buying — not "abstraction for its own sake".</details>

**Drill 4.** Every new report type requires editing a 300-line `generate_report()`.
<details><summary>Answer</summary>Smell: Long Method + Open-Closed violation. Cure: **Template Method** if the skeleton is stable and only steps vary; **Strategy**/registry if whole algorithms differ; **Builder** if the difference is in assembling output sections.</details>

**Drill 5.** Someone proposes a `BaseAbstractServiceFactory` for the second payment provider.
<details><summary>Answer</summary>Anti-pattern watch: Speculative Generality / Golden Hammer. Rule of three — two providers rarely justify a factory hierarchy in Python; a dict of constructors does. Say the cost out loud (indirection, harder tracebacks) and propose the cheap version first.</details>

---

## 4. 15-minute coding tasks (do them in a file, not in your head)

1. **Strategy:** implement 3 rate-limit algorithms (fixed window, sliding window, token bucket) behind one `Protocol`; select via config string. *Pass criterion:* adding a 4th touches exactly one new class + one registry line.
2. **State:** model `Order` with pending→paid→shipped→delivered/cancelled; make illegal transitions raise. *Pass criterion:* no `if status ==` outside the state classes.
3. **Decorator:** write `@retry(times, backoff)` preserving signature + docstring (`functools.wraps`), then stack it with `@timed`. *Pass criterion:* `help()` still shows the original signature.
4. **Repository + UoW:** `OrderRepository` over SQLAlchemy with an in-memory fake; write one service test with zero DB.
5. **Observer vs explicit:** implement "user registered → welcome email + analytics" twice (signals, then explicit service). Write down which you'd ship and why.
6. **Refactor-out drill:** take an interface with one implementation in your own repo and delete it. Note what got simpler.

---

## 5. Questions candidates fail (be ready)

1. *"Why is Singleton considered an anti-pattern if it's in GoF?"* → global state, hidden deps, test pain; in Python use module/`lru_cache` + DI.
2. *"Strategy and State look identical — are they?"* → structure yes, intent/ownership of transitions no.
3. *"Which patterns does Python make unnecessary?"* → Strategy(fn), Command(closure), Singleton(module), Iterator(generator), Prototype(deepcopy), Flyweight(lru_cache).
4. *"Where is Unit of Work in your stack?"* → SQLAlchemy `Session` / Django's `transaction.atomic()` boundary.
5. *"Show me a pattern you removed."* → the answer that proves you weigh cost, not collect patterns.
6. *"Is Django's Manager a Repository?"* → close in role, but it's coupled to the ORM/model (Active Record family), not a persistence-ignorant domain collection.

---

## 6. Self-check

1. Can you give the Adapter/Facade, Strategy/State, Decorator/Proxy one-liners cold?
2. For each of the 14 comparisons above, can you name a backend example from *your* code?
3. Which two drills in §4 have you actually written? (Reading them doesn't count.)

---

**Related:** [Backend Mapping](../Section_08_Backend_Mapping/) · [Anti-Patterns](../Section_09_Anti_Patterns/) · [Code Smells](../Section_03_Code_Smells_Refactoring/) · Runnable: [`../../../02_Year5+_Senior/01_System_Design/Design_Patterns_Code/`](../../../02_Year5+_Senior/01_System_Design/Design_Patterns_Code/)
