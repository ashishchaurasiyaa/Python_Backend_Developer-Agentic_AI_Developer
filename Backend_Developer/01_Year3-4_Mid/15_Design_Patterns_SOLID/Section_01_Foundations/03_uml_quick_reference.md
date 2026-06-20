# 03 · UML Quick Reference (for reading pattern diagrams)

You don't need to *draw* UML in Python work, but you must **read** the class diagrams on refactoring.guru / GoF without stalling.

## Class box

```
┌────────────────────┐
│   ClassName        │   ← class name
├────────────────────┤
│ - private_field    │   ← '-' private, '+' public, '#' protected
│ + public_field     │
├────────────────────┤
│ + method(arg): Ret │   ← signature
│ - helper(): void   │
└────────────────────┘
```

Italic class name OR `<<abstract>>` → abstract class. Italic method → abstract method.

Python equivalent:

```python
from abc import ABC, abstractmethod

class ClassName(ABC):           # italic / <<abstract>>
    public_field: int           # + public_field
    _protected: int             # # protected
    __private: int              # - private (name-mangled)

    @abstractmethod
    def method(self, arg) -> Ret: ...   # italic method
    def _helper(self) -> None: ...      # concrete
```

## Relationship arrows — the only 5 you'll see

| Arrow | Meaning | Strength | Python example |
|---|---|---|---|
| `──▷` solid + open triangle | **Inheritance** (is-a) | strong | `class Dog(Animal):` |
| `╌╌▷` dashed + open triangle | **Realises interface** (implements) | strong | `class S(Protocol):` consumed by `class C:` |
| `───>` solid arrow | **Association** ("knows about") | weak | `class Order: def __init__(self, customer)` — Order holds ref to Customer |
| `◇───>` open diamond | **Aggregation** (has-a, shared) | medium | `class Team: members: list[Player]` — players outlive the team |
| `◆───>` filled diamond | **Composition** (has-a, owned) | strong | `class House: rooms: list[Room]` — destroy house, rooms die |
| `╌╌>` dashed arrow | **Dependency** (uses temporarily) | weakest | a method parameter, a local variable |

### Memory aid

- Filled diamond = *I own you*. (House owns Rooms.)
- Open diamond = *we share you*. (Team has Players, but Players exist independently.)
- Solid line = *I have a long-term reference*.
- Dashed line = *I only touch you in passing*.

## Multiplicity (the numbers on arrows)

```
Order ───────* Item        Order has 0..* Items
       1
```

- `1` exactly one
- `0..1` optional
- `*` or `0..*` many
- `1..*` at least one

## Sequence diagram (used to show call flow in Behavioral patterns)

```
:Client      :Subject     :Observer
   │            │             │
   │── attach ─>│             │
   │            │             │
   │── notify ─>│── update ──>│
   │            │<── ack ─────│
```

- Vertical lines = lifelines.
- Horizontal arrows = method calls.
- Time flows top → bottom.

You'll see these in Observer, Mediator, Chain of Responsibility, Command.

## Reading a real pattern diagram — example: Strategy

```
            ┌──────────────┐
            │   Context    │◆───────┐
            ├──────────────┤        │ has-a (composition)
            │ +execute()   │        ▼
            └──────────────┘   ┌──────────────────┐
                               │  <<Strategy>>    │  ← interface
                               ├──────────────────┤
                               │ +algorithm()     │
                               └──────────────────┘
                                       △
                                       │ realises
                          ┌────────────┼────────────┐
                          │            │            │
                  ┌───────────┐  ┌───────────┐  ┌───────────┐
                  │ StratA    │  │ StratB    │  │ StratC    │
                  │ +algo()   │  │ +algo()   │  │ +algo()   │
                  └───────────┘  └───────────┘  └───────────┘
```

Read it as:
- Context **owns** a Strategy (filled diamond).
- Strategy is an **interface** (italic).
- StratA/B/C **realise** Strategy (open triangle, dashed).
- Context calls `strategy.algorithm()` without knowing which concrete one it has.

Python:

```python
class Strategy(Protocol):
    def algorithm(self, data): ...

class Context:
    def __init__(self, strategy: Strategy):
        self._strategy = strategy
    def execute(self, data):
        return self._strategy.algorithm(data)
```

## Self-check

1. What's the difference between aggregation (◇) and composition (◆)?
2. In UML, what does an italic class name mean? An italic method?
3. Sketch the relationship: `Order` holds many `Items`, and Items are destroyed when the Order is.
4. Which arrow style means "uses temporarily, e.g. as a parameter"?
5. In the Strategy diagram above, why is the diamond on the Context side, not the Strategy side?
