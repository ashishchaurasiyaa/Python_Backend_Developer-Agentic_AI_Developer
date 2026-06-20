# Bridge

## 1. Intent

Decouple an **abstraction** from its **implementation** so both can vary independently. Prevents combinatorial explosion of subclasses (M × N → M + N).

## 2. Problem

You have an abstraction with multiple variants, and each variant needs to work with multiple low-level implementations. Modelling this with inheritance gives a class explosion.

Example: `Notification` has variants `Simple`, `Urgent`, `Marketing` × channels `Email`, `SMS`, `Push`. Inheritance gives 9 classes: `SimpleEmail`, `SimpleSMS`, `UrgentEmail`, … Adding a 4th channel = +3 more classes.

## 3. Solution (UML sketch)

```
        Abstraction                Implementation (Implementor)
   ┌──────────────────┐        ┌──────────────────────┐
   │  Notification    │ ─────> │  <<MessageSender>>   │  (interface)
   ├──────────────────┤        ├──────────────────────┤
   │ -sender          │        │ +send(to, body)      │
   │ +notify(user,msg)│        └──────────────────────┘
   └──────────────────┘                  △
        △                                │
        │                ┌───────────────┼───────────────┐
        │                │               │               │
┌────────────┐   ┌────────────┐  ┌────────────┐  ┌────────────┐
│Simple…     │   │Urgent…     │  │EmailSender │  │SMSSender   │  PushSender
└────────────┘   └────────────┘  └────────────┘  └────────────┘
```

Now: 2 abstractions + 3 implementations = 5 classes total. Add a 4th channel = +1 class, not +3.

## 4. Participants

- **Abstraction** — high-level interface; holds a reference to an Implementor.
- **RefinedAbstraction** — variants of the abstraction.
- **Implementor** — interface for low-level operations.
- **ConcreteImplementor** — actual implementation.

## 5. Python implementation

```python
from typing import Protocol

# --- Implementor (low-level) ---
class MessageSender(Protocol):
    def send(self, to: str, body: str) -> None: ...

class EmailSender:
    def send(self, to, body): print(f"EMAIL→{to}: {body}")

class SMSSender:
    def send(self, to, body): print(f"SMS→{to}: {body}")

class PushSender:
    def send(self, to, body): print(f"PUSH→{to}: {body}")

# --- Abstraction (high-level) ---
class Notification:
    def __init__(self, sender: MessageSender):
        self._sender = sender
    def notify(self, user, msg: str):
        self._sender.send(user, msg)

class UrgentNotification(Notification):
    def notify(self, user, msg):
        self._sender.send(user, f"[URGENT] {msg}")
        self._sender.send(user, f"[URGENT] {msg}")   # send twice

class MarketingNotification(Notification):
    def notify(self, user, msg):
        if user.opted_in_marketing:
            self._sender.send(user, msg)

# --- Use ---
n = UrgentNotification(SMSSender())     # mix any abstraction with any sender
n.notify(user="ash", msg="server down")
```

Changing channel → swap the sender at construction. Adding a new variant → new subclass of `Notification`. Adding a new channel → new `Sender`. No combinatorial explosion.

## 6. Backend examples

- **Python `logging`** — `Logger` (abstraction) decoupled from `Handler` (implementation). Same logger writes to file, stderr, syslog, Sentry by swapping handlers.
- **Database drivers via DB-API** — `psycopg2`, `mysqlclient`, `sqlite3` all expose the same DB-API; high-level code (SQLAlchemy core) is the abstraction.
- **`asyncio` event loop policies** — same `asyncio` API, different concrete loops (default, uvloop, Proactor on Windows).
- **Storage abstractions** — Django's `Storage` class with `FileSystemStorage`, `S3Storage`, `GCSStorage` swappable underneath.

## 7. Pros / Cons

**Pros**
- Beats M × N inheritance explosion.
- High-level and low-level evolve independently.
- Single-Responsibility-friendly: each side has its own reason to change.

**Cons**
- Indirection — one call hops through the bridge.
- Overkill when there's only one implementation.

**Don't use when**
- You have one implementation and no real plan for a second.
- Adapter is enough (you have one external API to translate).

## 8. Bridge vs Adapter — the common confusion

| | Adapter | Bridge |
|---|---|---|
| Designed when | After the fact (retrofit) | Up front |
| Goal | Make incompatible code work | Allow two dimensions to vary |
| Shape | Wraps **one** thing | Holds a reference to a swappable Implementor |

If you're choosing between them on a greenfield design with multiple variants × multiple implementations → Bridge. If you're integrating an existing library → Adapter.

## 9. Related patterns

- **Adapter** — close cousin; see above.
- **Strategy** — Bridge looks like Strategy structurally; the *intent* differs. Strategy swaps **algorithm**; Bridge swaps **implementation of an abstraction**.
- **Abstract Factory** — often pairs with Bridge to assemble matching abstraction+implementor pairs.

## 9. Self-check

1. Explain "M × N → M + N" in your own words.
2. What's the difference between Bridge and Strategy?
3. Why is Python's `logging.Logger / Handler` design a Bridge?
4. Give a case where Adapter, not Bridge, is the right answer.
5. When is Bridge overkill?
