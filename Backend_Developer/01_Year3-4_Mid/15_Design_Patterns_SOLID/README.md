# 15 · Design Patterns + SOLID (Python flavour)

> Companion to https://refactoring.guru/design-patterns — but written for Python backend engineers (FastAPI / Django / Celery / Kafka / Redis stack).

## Why this folder exists

Design patterns are **named solutions to recurring object-design problems**. They are *not* algorithms and *not* architecture (monolith vs microservices is architecture). They live between OOP fundamentals and architecture: how do you wire a handful of classes/objects so the code stays soft when the requirement changes?

A Python developer needs them for three concrete reasons:

1. **Interview signal** — senior loops ask "where would you use Strategy?", "Adapter vs Facade?", "why is Singleton a code smell?". Vague answers fail.
2. **Reading real codebases** — Django ORM is Active Record + Unit of Work; DRF serializers are Adapter; FastAPI `Depends()` is dependency injection (Factory + IoC). You can't navigate them without the vocabulary.
3. **Avoiding two failure modes** — Java-flavored over-engineering (writing `AbstractFactoryBuilderFactory` in Python where a function would do) AND under-engineering (10-level `if/elif` chains that should have been Strategy or State).

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

## Cross-references

- SOLID drives most patterns → [02 SOLID](Section_02_SOLID_Principles/)
- Code smells trigger pattern adoption → [03 Smells](Section_03_Code_Smells_Refactoring/)
- Architecture-level patterns (CQRS, Event Sourcing, Saga) live one tier up → `../../02_Year5+_Senior/02_Architecture_Patterns/`
