# 15 · Design Patterns + SOLID (Python flavour)

> Companion to https://refactoring.guru/design-patterns — but written for Python backend engineers (FastAPI / Django / Celery / Kafka / Redis stack).

## Why this folder exists

Design patterns are **named solutions to recurring object-design problems**. They are *not* algorithms and *not* architecture (monolith vs microservices is architecture). They live between OOP fundamentals and architecture: how do you wire a handful of classes/objects so the code stays soft when the requirement changes?

A Python developer needs them for three concrete reasons:

1. **Interview signal** — senior loops ask "where would you use Strategy?", "Adapter vs Facade?", "why is Singleton a code smell?". Vague answers fail.
2. **Reading real codebases** — Django ORM is Active Record + Unit of Work; DRF serializers are Adapter; FastAPI `Depends()` is dependency injection (Factory + IoC). You can't navigate them without the vocabulary.
3. **Avoiding two failure modes** — Java-flavored over-engineering (writing `AbstractFactoryBuilderFactory` in Python where a function would do) AND under-engineering (10-level `if/elif` chains that should have been Strategy or State).

## Runnable code — this folder is theory only

Every file in `Section_01`–`Section_10` is markdown. There are **zero `.py` files here on purpose** — the runnable implementations live one tier up, at [`../../02_Year5+_Senior/01_System_Design/Design_Patterns_Code/`](../../02_Year5+_Senior/01_System_Design/Design_Patterns_Code/).

That directory is **not toy code**. It's 16 patterns, each a self-contained Django project (or standalone script for the simpler ones) built against the same domain as the repo owner's actual SAP-integration work at Youngman India — `SapConnectionManager` (Singleton), `ChallanFactory` (Factory Method), `PaymentService` + `DIContainer` (Dependency Injection), a 12-state credit-pipeline state machine driven by `Command` objects, and more. Each has a real `manage.py test <app>` suite proving the pattern's actual behavioural guarantee (e.g. Singleton: two constructions really are `is` the same object; Factory: each input dispatches to the right subclass; DI: swapping the injected gateway changes nothing in the service class).

[Section_08 (Backend Mapping)](Section_08_Backend_Mapping/) is the file that maps *unnamed* patterns already hiding in FastAPI/Django/Celery/Kafka/Redis — read the runnable code above for the *named*, hand-built versions instead. Individual pattern notes below also link straight to their matching implementation where one exists.

## Study order (do not skip)

| # | Section | Why first |
|---|---|---|
| 01 | Foundations | OOP, UML, object relations — the vocabulary patterns use |
| 02 | SOLID | The "why" behind every pattern. Patterns are SOLID applied. |
| 03 | Code Smells + Refactoring | The symptoms patterns cure. Pattern without smell = over-engineering. |
| 04 | Creational | How objects come into existence |
| 05 | Structural | How objects are composed |
| 06 | Behavioral | How objects talk |
| 07 | Python Idioms vs GoF | Where Python eats the pattern (functions, decorators, dunders) |
| 08 | Backend Mapping | Spotting patterns in FastAPI / Django / Celery / Kafka / Redis |
| 09 | Anti-patterns | When patterns become the problem |
| 10 | Interview Drills | Comparisons, callouts, 15-min coding tasks |

## How each pattern note is structured

Every file under sections 04–06 follows the same shape so you can grade yourself the same way every time:

```
1. Intent           — one line, no jargon
2. Problem          — the smell that calls for it
3. Solution         — UML sketch (ASCII)
4. Participants     — the roles + their responsibilities
5. Python code      — idiomatic, not a Java port
6. Backend example  — where it shows up in our stack
7. Pros / Cons      — when NOT to use
8. Related patterns — link to siblings
9. Self-check       — 5 questions you must answer cold
```

## Mental model — the 3 GoF categories in one sentence each

- **Creational** — *who* makes the object, *when*, *how flexible* is the choice.
- **Structural** — *how* objects glue together to form bigger things without becoming rigid.
- **Behavioral** — *how* objects distribute responsibility and communicate.

## The "is it really needed?" gate

Before adding any pattern, the cost must be smaller than the pain it removes. Three checks:

1. Has the smell appeared **3+ times**? (Rule of three — don't abstract on the first occurrence.)
2. Will the abstraction be **stable**? (If requirements still churn, premature abstraction will be wrong.)
3. Can a Python idiom solve it more cheaply? (A function > a Strategy class. A `dict` of callables > a Command. A module > a Singleton.)

If any answer is no — skip the pattern, write the boring code.

## 📑 File index (all 38 files)

### Section 01 — Foundations
[01 What is a pattern](Section_01_Foundations/01_what_is_a_pattern.md) · [02 OOP pillars recap](Section_01_Foundations/02_oop_pillars_recap.md) · [03 UML quick reference](Section_01_Foundations/03_uml_quick_reference.md) · [04 Relations between objects](Section_01_Foundations/04_relations_between_objects.md)

### Section 02 — SOLID Principles 🔴
[01 Single Responsibility](Section_02_SOLID_Principles/01_single_responsibility.md) · [02 Open/Closed](Section_02_SOLID_Principles/02_open_closed.md) · [03 Liskov Substitution](Section_02_SOLID_Principles/03_liskov_substitution.md) · [04 Interface Segregation](Section_02_SOLID_Principles/04_interface_segregation.md) · [05 Dependency Inversion](Section_02_SOLID_Principles/05_dependency_inversion.md) · [99 SOLID in FastAPI/Django](Section_02_SOLID_Principles/99_solid_in_fastapi_django.md) ← *apne stack me kaise dikhta hai*

### Section 03 — Code Smells & Refactoring
[01 Code smells catalog](Section_03_Code_Smells_Refactoring/01_code_smells_catalog.md)

### Section 04 — Creational (5)
[01 Factory Method](Section_04_Creational/01_factory_method.md) · [02 Abstract Factory](Section_04_Creational/02_abstract_factory.md) · [03 Builder](Section_04_Creational/03_builder.md) · [04 Prototype](Section_04_Creational/04_prototype.md) · [05 Singleton](Section_04_Creational/05_singleton.md)

### Section 05 — Structural (7)
[01 Adapter](Section_05_Structural/01_adapter.md) · [02 Bridge](Section_05_Structural/02_bridge.md) · [03 Composite](Section_05_Structural/03_composite.md) · [04 Decorator](Section_05_Structural/04_decorator.md) · [05 Facade](Section_05_Structural/05_facade.md) · [06 Flyweight](Section_05_Structural/06_flyweight.md) · [07 Proxy](Section_05_Structural/07_proxy.md)

### Section 06 — Behavioural (10)
[01 Chain of Responsibility](Section_06_Behavioral/01_chain_of_responsibility.md) · [02 Command](Section_06_Behavioral/02_command.md) · [03 Iterator](Section_06_Behavioral/03_iterator.md) · [04 Mediator](Section_06_Behavioral/04_mediator.md) · [05 Memento](Section_06_Behavioral/05_memento.md) · [06 Observer](Section_06_Behavioral/06_observer.md) · [07 State](Section_06_Behavioral/07_state.md) · [08 Strategy](Section_06_Behavioral/08_strategy.md) 🔴 · [09 Template Method](Section_06_Behavioral/09_template_method.md) · [10 Visitor](Section_06_Behavioral/10_visitor.md)

### Sections 07–10 — judgment layer *(yahi senior se alag karta hai)*
[07 Python eats the pattern](Section_07_Python_Idioms_vs_GoF/01_python_eats_the_pattern.md) — kab pattern ki zaroorat hi nahi
[08 Patterns in our stack](Section_08_Backend_Mapping/01_patterns_in_our_stack.md) — Django/FastAPI me kahan already use ho rahe hain
[09 When patterns become the problem](Section_09_Anti_Patterns/01_when_patterns_become_the_problem.md) — over-engineering
[10 Comparisons and drills](Section_10_Interview_Drills/01_comparisons_and_drills.md) 🔴 — **interview drills, yahi last me revise karo**

> **22 GoF patterns hain yahan** (Interpreter senior track me hai → [21_Interpreter_Pattern.md](../../02_Year5%2B_Senior/01_System_Design/LLD_Theory/21_Interpreter_Pattern.md)).

## Cross-references

- SOLID drives most patterns → [02 SOLID](Section_02_SOLID_Principles/)
- Code smells trigger pattern adoption → [03 Smells](Section_03_Code_Smells_Refactoring/)
- Architecture-level patterns (CQRS, Event Sourcing, Saga) live one tier up → [`02_Architecture_Patterns/`](../../02_Year5%2B_Senior/02_Architecture_Patterns/README.md)
- Patterns ko **chala ke** dekhna hai → [`Design_Patterns_Code/`](../../02_Year5%2B_Senior/01_System_Design/Design_Patterns_Code/) (10 Django projects + 6 scripts)
- Machine-coding drill → [`LLD_Problems/`](../../02_Year5%2B_Senior/01_System_Design/LLD_Problems/README.md)
