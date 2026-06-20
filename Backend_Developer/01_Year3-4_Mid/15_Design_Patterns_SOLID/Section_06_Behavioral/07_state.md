# State

## 1. Intent

Allow an object to alter its behaviour when its internal **state** changes — as if it changed class.

## 2. Problem

An object's behaviour depends on what state it's in, and there are many states. Encoding all the rules as `if/elif self.state == ...` ladders becomes unreadable and bug-prone.

Examples:
- Order: created → paid → shipped → delivered → returned; each state allows different methods.
- TCP connection: closed → listen → established → closed.
- Document workflow: draft → review → approved → published.

Symptoms:
- `if self.status == "...":` ladders inside every method.
- "Why can I cancel a delivered order?" bugs.

## 3. Solution (UML sketch)

```
┌──────────────┐                 ┌──────────────┐
│  Context     │◇──────────────> │  <<State>>   │
├──────────────┤  current_state  ├──────────────┤
│ +request()   │                 │ +handle(ctx) │
└──────────────┘                 └──────────────┘
                                        △
                            ┌───────────┼───────────┐
                       ┌──────────┐ ┌──────────┐ ┌──────────┐
                       │  StateA  │ │  StateB  │ │  StateC  │
                       └──────────┘ └──────────┘ └──────────┘
```

The Context delegates to a State object; the State decides what to do and may transition.

## 4. Participants

- **Context** — owns a current State; delegates work to it.
- **State** — interface for state-specific behaviour.
- **ConcreteState** — implements behaviour for one state; may switch context to the next state.

## 5. Python implementation

### Order lifecycle

```python
from __future__ import annotations
from typing import Protocol

class State(Protocol):
    def pay(self, ctx: "Order"): ...
    def ship(self, ctx: "Order"): ...
    def cancel(self, ctx: "Order"): ...

class Order:
    def __init__(self):
        self.state: State = Draft()
    def pay(self):    self.state.pay(self)
    def ship(self):   self.state.ship(self)
    def cancel(self): self.state.cancel(self)
    def _set(self, s: State):
        print(f"-> {s.__class__.__name__}")
        self.state = s

def _illegal(action, state):
    raise RuntimeError(f"{action} not allowed in {state}")

class Draft:
    def pay(self, ctx):    ctx._set(Paid())
    def ship(self, ctx):   _illegal("ship", "Draft")
    def cancel(self, ctx): ctx._set(Cancelled())

class Paid:
    def pay(self, ctx):    _illegal("pay", "Paid")
    def ship(self, ctx):   ctx._set(Shipped())
    def cancel(self, ctx): ctx._set(Refunded())

class Shipped:
    def pay(self, ctx):    _illegal("pay", "Shipped")
    def ship(self, ctx):   _illegal("ship", "Shipped")
    def cancel(self, ctx): _illegal("cancel", "Shipped")

class Cancelled: ...
class Refunded:  ...

# Use
o = Order()
o.pay()           # -> Paid
o.ship()          # -> Shipped
# o.cancel()      # RuntimeError
```

### Pythonic — dict-of-transitions / `transitions` lib

For non-trivial workflows, a table-driven approach is cleaner:

```python
TRANSITIONS = {
    ("draft",  "pay"):    "paid",
    ("draft",  "cancel"): "cancelled",
    ("paid",   "ship"):   "shipped",
    ("paid",   "cancel"): "refunded",
}

class Order:
    def __init__(self): self.state = "draft"
    def do(self, action):
        nxt = TRANSITIONS.get((self.state, action))
        if nxt is None: raise RuntimeError(f"{action} from {self.state} illegal")
        self.state = nxt
```

For real workflows use the `transitions` library — it gives you callbacks, persistence, and graph visualisation.

## 6. Backend examples

- **Django FSM** (`django-fsm`) — model field with declared transitions.
- **Workflow engines** — Camunda, Temporal, Step Functions.
- **TCP/IP stack** — every kernel implements a State machine.
- **Order/payment systems** — most real businesses have one underneath.
- **CI/CD job statuses** — `queued → running → success | failure | cancelled`.
- **Database connection** — `idle → in_transaction → committed | rolled_back`.

## 7. Pros / Cons

**Pros**
- Each state is single-responsibility; one place to read the rules.
- Illegal transitions are rejected explicitly.
- Adding a new state doesn't sprawl edits across methods.

**Cons**
- More classes / more files than a switch table.
- Some states share most behaviour — risk of duplication.

**Don't use when**
- 2-3 states and no growth expected — a flag is fine.
- States have entirely independent shapes (then they're really different objects, not states).

## 8. State vs Strategy — the classic confusion

Both look the same in UML. The intent differs:

| | Strategy | State |
|---|---|---|
| Switches when? | At caller's discretion | Object's internal lifecycle |
| Who chooses? | The caller | The object (or one of its states) |
| Coupling | Strategies don't know each other | States often know each other (to transition) |

If algorithms differ but lifecycle doesn't — Strategy. If lifecycle matters — State.

## 9. Related patterns

- **Strategy** — same shape, different intent.
- **Flyweight** — stateless State objects can be shared as Flyweights.
- **Memento** — to restore an FSM to a saved state.

## 9. Self-check

1. What's the smell that calls for State?
2. State vs Strategy in one sentence.
3. Why does a table-driven FSM scale better than nested `if/elif`?
4. Where in Django is the State pattern formalised?
5. Give two states where one transitions to another — who initiates the transition?
