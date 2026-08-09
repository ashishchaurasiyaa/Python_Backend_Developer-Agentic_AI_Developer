# 🧱 LLD Theory — 28 notes

> Low-Level Design ka poora base: OOP → SOLID → 21 GoF patterns → concurrency/CQRS.
> **Machine-coding round** aur **code-review round** dono yahin se nikalte hain.

---

## 📖 Padhne ka order (yeh order tod mat do)

**1. Base pehle** — patterns baad me matlab denge
1. [OOP_Fundamentals.md](OOP_Fundamentals.md)
2. [SOLID_Principles.md](SOLID_Principles.md) 🔴 *(sabse zyada poocha jata hai)*
3. [10_UML_Class_Diagrams.md](10_UML_Class_Diagrams.md) — whiteboard pe class diagram banana aana chahiye

**2. Creational**
| # | Pattern | Backend me kahan |
|---|---|---|
| 01 | [Singleton](01_Singleton_Pattern.md) | DB connection pool, config, logger |
| 02 | [Factory](02_Factory_Pattern.md) | Payment provider chunna, notification channel |
| 03 | [Abstract Factory](03_Abstract_Factory_Pattern.md) | Multi-vendor document/report families |
| 04 | [Builder](04_Builder_Pattern.md) | Query builder, complex request objects |
| 12 | [Prototype](12_Prototype_Pattern.md) | Template se object clone |

**3. Structural**
| # | Pattern | Backend me kahan |
|---|---|---|
| 05 | [Decorator](05_Decorator_Pattern.md) | Middleware, retry/cache wrappers |
| 06 | [Adapter](06_Adapter_Pattern.md) | Third-party SDK ko apne interface me lana |
| 13 | [Facade](13_Facade_Pattern.md) | Service layer — complex subsystem chhupao |
| 20 | [Bridge](20_Bridge_Pattern.md) | Abstraction aur implementation alag |
| — | [Command / Composite / Proxy / Flyweight](Command_Composite_Proxy_Flyweight_Patterns.md) | Ek file me 4 patterns |

**4. Behavioural**
| # | Pattern | Backend me kahan |
|---|---|---|
| 07 | [Strategy](07_Strategy_Pattern.md) 🔴 | Pricing rules, routing algorithms — sabse useful |
| 08 | [Observer](08_Observer_Pattern.md) 🔴 | Events, signals, webhooks |
| 09 | [Template Method](09_Template_Method_Pattern.md) | Report generation skeleton |
| 14 | [Iterator](14_Iterator_Pattern.md) | Pagination, streaming cursors |
| 15 | [Mediator](15_Mediator_Pattern.md) | Orchestration, chat rooms |
| 16 | [Visitor](16_Visitor_Pattern.md) | AST/report traversal |
| 17 | [Chain of Responsibility](17_Chain_of_Responsibility_Pattern.md) | Middleware chain, approval flow |
| 18 | [State](18_State_Pattern.md) 🔴 | Order/payment state machine |
| 19 | [Memento](19_Memento_Pattern.md) | Undo, snapshots |
| 21 | [Interpreter](21_Interpreter_Pattern.md) | Rule/DSL evaluation |

**5. Advanced (senior signal)**
- [11_Dependency_Injection_Repository_StateMachine.md](11_Dependency_Injection_Repository_StateMachine.md) 🔴 — DI + Repository, testability ka asli jawab
- [Concurrency_Thread_Safety.md](Concurrency_Thread_Safety.md) 🔴 — race conditions, locks, real project war stories
- [Event_Sourcing_CQRS.md](Event_Sourcing_CQRS.md)
- [Database_Design.md](Database_Design.md)
- [Resume_Based_LLD_Interview_Prep.md](Resume_Based_LLD_Interview_Prep.md) — apne hi project pe LLD questions

---

## ▶️ Aage kya

| Kya | Kahan |
|---|---|
| Patterns ko **chala ke** dekhna | [`../Design_Patterns_Code/`](../Design_Patterns_Code/) — 16 runnable Django projects |
| **Machine-coding drill** karna | [`../LLD_Problems/`](../LLD_Problems/) — 20 problems (Parking Lot, Splitwise, LRU…) |
| Concise pattern revision | [Mid-track 15_Design_Patterns_SOLID](../../../01_Year3-4_Mid/15_Design_Patterns_SOLID/README.md) |
