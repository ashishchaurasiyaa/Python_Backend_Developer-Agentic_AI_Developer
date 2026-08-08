# Mediator

> Runnable version of this pattern: [`Design_Patterns_Code/18_mediator/`](../../../02_Year5+_Senior/01_System_Design/Design_Patterns_Code/18_mediator/) — standalone script, `python mediator.py`.

## 1. Intent

Reduce coupling between many objects by centralising their interaction in a **mediator** that they all talk to (instead of to each other).

Before: N components, up to N×N connections.
After: N components + 1 mediator, N connections.

## 2. Problem

A handful of objects need to coordinate, and they've started holding references to each other directly. Adding a new component touches multiple existing ones — classic shotgun surgery.

Examples:
- A dialog box where clicking one field changes another.
- An order workflow: cart, inventory, pricing, payment, shipping must all react to each other.
- Air-traffic control: planes don't talk to each other; they talk to the tower.

## 3. Solution (UML sketch)

```
        ┌────────────┐       ┌────────────┐       ┌────────────┐
        │ Component1 │       │ Component2 │       │ Component3 │
        └────────────┘       └────────────┘       └────────────┘
              │                   │                    │
              └──────┬────────────┴────────────────────┘
                     ▼
              ┌────────────────────────┐
              │      Mediator          │
              ├────────────────────────┤
              │ +notify(sender, event) │
              └────────────────────────┘
```

Components only know the Mediator. Mediator knows all components and the rules.

## 4. Participants

- **Mediator** — interface with `notify(sender, event)`.
- **ConcreteMediator** — owns the components, encodes coordination rules.
- **Component** — knows its Mediator; raises events to it; never holds peers.

## 5. Python implementation

### Order workflow

```python
from typing import Protocol

class Mediator(Protocol):
    def notify(self, sender, event: str, payload=None): ...

class BaseComponent:
    def __init__(self, mediator: Mediator | None = None):
        self.mediator = mediator

class Cart(BaseComponent):
    def add_item(self, sku, qty):
        self.mediator.notify(self, "item_added", (sku, qty))

class Inventory(BaseComponent):
    def reserve(self, sku, qty):
        print(f"reserving {qty}× {sku}")

class Pricing(BaseComponent):
    def quote(self, sku, qty):
        print(f"price for {qty}× {sku} = …")

class OrderMediator:
    def __init__(self):
        self.cart      = Cart(self)
        self.inventory = Inventory(self)
        self.pricing   = Pricing(self)

    def notify(self, sender, event, payload=None):
        if event == "item_added":
            sku, qty = payload
            self.inventory.reserve(sku, qty)
            self.pricing.quote(sku, qty)

m = OrderMediator()
m.cart.add_item("SKU-1", 2)
```

`Cart` doesn't know `Inventory` exists; it just shouts to the mediator.

### Pythonic — an event bus / pub-sub

```python
from collections import defaultdict
from typing import Callable

class Bus:
    def __init__(self):
        self.subs: dict[str, list[Callable]] = defaultdict(list)
    def on(self, event):
        def deco(fn): self.subs[event].append(fn); return fn
        return deco
    def emit(self, event, payload=None):
        for fn in self.subs[event]: fn(payload)

bus = Bus()

@bus.on("item_added")
def reserve(payload): sku, qty = payload; print("reserve", sku, qty)

@bus.on("item_added")
def quote(payload): sku, qty = payload; print("quote", sku, qty)

bus.emit("item_added", ("SKU-1", 2))
```

This is the Mediator + Observer hybrid most real codebases use.

## 6. Backend examples

- **Django signals** — `post_save.send(sender, instance=…)` — Django acts as the Mediator.
- **Celery beat + tasks** — beat schedules; tasks subscribe via task names.
- **Kafka / Redis pub-sub** — message broker IS the Mediator across services.
- **Saga orchestrators** — central coordinator across microservices (Mediator at the architecture level).
- **GraphQL subscriptions** — schema mediates between mutation triggers and subscriber clients.
- **Front-controllers** — `dispatch(request) → view` in Django/Flask is a Mediator.

## 7. Pros / Cons

**Pros**
- Components are reusable and unit-testable in isolation.
- Coordination logic lives in one place.
- Adding a component = wire it to the mediator only.

**Cons**
- Mediator can grow into a **God class** — anti-pattern alert.
- Indirect calls are harder to trace.
- Wrong choice when the coordination is actually trivial.

**Don't use when**
- Only 2 components talk; just let them.
- Coordination is so simple that a direct call is clearer.

## 8. Mediator vs Observer vs Facade

| | Direction | Knows whom |
|---|---|---|
| **Mediator** | Many ↔ Many (via centre) | Mediator knows everyone |
| **Observer** | One → Many | Subject doesn't know observers' identities |
| **Facade** | Client → Subsystem | Facade knows subsystem; subsystem doesn't know caller |

Mediator and Observer often combine: the Mediator is the Subject; components are Observers.

## 9. Related patterns

- **Observer** — see above; commonly fused.
- **Command** — events flowing through the Mediator are often Commands.
- **Facade** — Mediator coordinates peers two-way; Facade simplifies one-way.

## 9. Self-check

1. State the N×N → N+1 argument.
2. Why is Django's signals system a Mediator?
3. What's the biggest risk in introducing a Mediator?
4. Difference between Mediator and Facade.
5. Show in 10 lines how a Pythonic Bus combines Mediator and Observer.
