# 01 · What is a Design Pattern?

## One-line definition

A **design pattern** is a *named, reusable solution* to a *commonly occurring* problem in object-oriented design — described as a template, not a copy-pasteable library.

## What a pattern is NOT

| Confused with | Difference |
|---|---|
| **Algorithm** (e.g. quicksort) | Algorithms give exact steps to compute a result. Patterns give a *structure of objects* — implementation differs every time. |
| **Library / Framework** | A library is code you import. A pattern is an idea you implement in your own classes. |
| **Architecture style** (microservices, hexagonal) | Architecture is about systems/processes. Patterns are about classes/objects inside one process. |
| **Idiom** (list comprehension, context manager) | Idioms are language-specific shortcuts. Patterns are language-agnostic structures. |

## Where the 23 GoF patterns came from

1994 book *Design Patterns: Elements of Reusable Object-Oriented Software* by the **Gang of Four** (Gamma, Helm, Johnson, Vlissides). They studied Smalltalk and C++ code, found 23 recurring micro-structures, gave them names. That's the canon.

> The book is Java/C++ flavoured. Many of those 23 patterns either dissolve into a Python feature (Strategy → function, Iterator → `__iter__`, Command → callable) or simplify drastically. Section 07 covers exactly which ones.

## Anatomy of a pattern description (the way Refactoring.Guru / GoF write it)

Every pattern has the same 5 fields. Train yourself to spot them.

```
1. Intent      — what problem it solves, in one sentence
2. Motivation  — a story / example where the smell shows up
3. Structure   — UML class diagram (the participants and their relations)
4. Participants— who plays what role (e.g. "Subject", "Observer", "ConcreteObserver")
5. Consequences— pros, cons, trade-offs
```

When asked in an interview "explain pattern X", give those 5 in 90 seconds. Don't dive into code first.

## The 3 categories (with the underlying question each answers)

| Category | Underlying question | Patterns |
|---|---|---|
| **Creational** | *How is this object created, and who decides which concrete type?* | Factory Method, Abstract Factory, Builder, Prototype, Singleton |
| **Structural** | *How are objects composed so the whole stays flexible?* | Adapter, Bridge, Composite, Decorator, Facade, Flyweight, Proxy |
| **Behavioral** | *How are responsibilities split, and how do objects talk?* | Chain of Responsibility, Command, Iterator, Mediator, Memento, Observer, State, Strategy, Template Method, Visitor |

## Why patterns are worth learning (even if Python kills half of them)

1. **Shared vocabulary.** "Use a Strategy here" carries 5 minutes of context in 3 words.
2. **Pre-vetted designs.** Each pattern's trade-offs were chewed over for decades. You don't re-discover them.
3. **Reading other people's code.** Half of Django/FastAPI/SQLAlchemy is named patterns — without the names you only see "weird classes".
4. **Interview signal.** Senior loops use them as a proxy for "have you read good code?".

## When patterns become a problem

- **Pattern fever.** Using a pattern *because* it's a pattern, not because the smell exists. Symptom: `OrderFactoryBuilderStrategy` for a 30-line script.
- **Java-porting.** Forcing GoF's class hierarchy into Python when a function + closure does the job in 5 lines.
- **Hiding intent.** Six layers of `Decorator` so the actual request flow is unreadable. Refactor *toward* clarity, not away from it.

> Rule: name the **smell** before you name the **pattern**. If you can't articulate the smell in one sentence, don't apply the pattern.

## Self-check

1. Why is "Singleton" a pattern but "list comprehension" an idiom?
2. What 5 fields describe every GoF pattern?
3. Give one Python feature that makes the GoF *Iterator* pattern almost invisible.
4. State the underlying question each of the 3 categories answers.
5. What is the "rule of three" for abstractions?
