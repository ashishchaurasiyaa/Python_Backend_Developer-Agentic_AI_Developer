# 04 · Relations Between Objects

The 5 ways one object can relate to another, in increasing strength of coupling. Picking the right one is half of good design.

## 1. Dependency (weakest)

> "I touch you, but I don't remember you afterwards."

```python
class Report:
    def render(self, formatter: Formatter) -> str:   # formatter passed in, not stored
        return formatter.format(self.data)
```

- `formatter` is a parameter — gone when the method returns.
- Easiest to swap, easiest to test.
- UML: `╌╌>` dashed arrow.

## 2. Association

> "I keep a reference to you. We have separate lifecycles."

```python
class Order:
    def __init__(self, customer: Customer):
        self.customer = customer       # held for the lifetime of Order
```

- Order remembers a Customer.
- Customer exists independently — deleting the Order doesn't delete the Customer.
- UML: `───>` solid arrow.

## 3. Aggregation

> "I'm made up of you, but you can survive without me."

```python
class Team:
    def __init__(self):
        self.players: list[Player] = []
    def add(self, p: Player):
        self.players.append(p)
```

- Players form the team, but a Player can switch teams or be unattached.
- Aggregation is a special case of association — semantic only, no code difference in Python.
- UML: `◇───>` open diamond on the container.

## 4. Composition (strongest non-inheritance)

> "I own you. When I die, you die."

```python
class House:
    def __init__(self):
        self.rooms = [Room(self), Room(self)]    # rooms born with the house

class Room:
    def __init__(self, house: "House"):
        self.house = house                        # back-ref, but room can't outlive house
```

- Rooms don't exist outside the house.
- Pythonically: when `House` is garbage-collected, its `Room`s are too (no external refs).
- UML: `◆───>` filled diamond on the owner.

## 5. Inheritance (strongest of all)

> "I *am* a kind of you."

```python
class HTTPError(Exception): ...
```

- Tightest coupling — child knows parent's *implementation*, not just interface.
- Hard to swap, hard to test, breaks Liskov easily.
- Use sparingly.

## The "favour composition over inheritance" maxim — why

Inheritance baked at compile time. Composition can change at runtime.

```python
# Inheritance: behaviour locked to subclass
class LoggingService(Service):
    def run(self):
        print("logging…")
        super().run()

# Composition: behaviour injected, swappable
class Service:
    def __init__(self, logger: Logger):
        self.logger = logger
    def run(self):
        self.logger.log("running")
```

In the composition version you can drop in a `NullLogger`, `JSONLogger`, `RemoteLogger` without touching `Service`. With inheritance you'd need a new subclass per logger.

This single insight powers **Strategy, Decorator, Bridge, Adapter, Proxy** — all 5 are "compose, don't inherit".

## How relations show up in patterns

| Pattern | Key relation | Why |
|---|---|---|
| **Strategy** | Composition (Context owns Strategy) | swap algorithm at runtime |
| **Decorator** | Aggregation (wrapper holds wrappee) | layer behaviour |
| **Adapter** | Composition (Adapter wraps Adaptee) | translate interface |
| **Observer** | Aggregation (Subject holds Observers) | observers can re-attach to other subjects |
| **Composite** | Composition (parent owns children) | tree lifecycle |
| **Template Method** | Inheritance (subclass fills hooks) | skeleton is locked |
| **Singleton** | (none — single instance) | global access |

## Decision rule

Ask: *"If A goes away, does B go away?"*

- Yes → composition or inheritance
- No → aggregation or association
- "B is here briefly inside one method" → dependency

Then ask: *"Is B truly a kind-of A?"*

- Yes → inheritance
- No → composition

## Self-check

1. Difference between aggregation and composition (give a Python example).
2. Why does "favour composition over inheritance" matter at runtime?
3. Which relation does Strategy use, and why not inheritance?
4. Give an example of dependency (not association).
5. If `Invoice` deletes its `LineItem`s when destroyed, which UML arrow?
