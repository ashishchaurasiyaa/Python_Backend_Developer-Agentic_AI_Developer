# Observer (Publish-Subscribe)

## 1. Intent

Define a **one-to-many** dependency: when one object (Subject) changes, all its observers are notified automatically.

## 2. Problem

Multiple parts of the system need to react to events in another part, **without that part knowing them**. Hard-coding the dependencies couples the source to every consumer and prevents adding new ones without edits.

Examples:
- A user signs up → send welcome email, create profile, log analytics, warm cache.
- A row is saved → invalidate caches, push to search index, emit metric.
- A WebSocket sends a message → broadcast to subscribers.

## 3. Solution (UML sketch)

```
┌─────────────────┐               ┌─────────────────┐
│    Subject      │ ─── notify ─> │   <<Observer>>  │
├─────────────────┤               ├─────────────────┤
│ +attach(o)      │               │ +update(event)  │
│ +detach(o)      │               └─────────────────┘
│ +notify()       │                        △
└─────────────────┘                        │
                         ┌─────────────────┼─────────────────┐
                         │                 │                 │
                ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
                │ Emailer      │  │ Analytics    │  │ CacheWarmer  │
                └──────────────┘  └──────────────┘  └──────────────┘
```

## 4. Participants

- **Subject** — keeps a list of observers; provides attach/detach/notify.
- **Observer** — interface with `update(event)`.
- **ConcreteObservers** — react to events.

## 5. Python implementation

### Classical

```python
from typing import Protocol

class Observer(Protocol):
    def update(self, event: str, payload): ...

class Subject:
    def __init__(self):
        self._observers: list[Observer] = []
    def attach(self, o: Observer):  self._observers.append(o)
    def detach(self, o: Observer):  self._observers.remove(o)
    def notify(self, event, payload=None):
        for o in self._observers:
            o.update(event, payload)

class UserSignups(Subject):
    def register(self, user):
        # … create row
        self.notify("user_signed_up", user)

class Emailer:
    def update(self, event, payload):
        if event == "user_signed_up":
            print(f"emailing {payload}")

class Analytics:
    def update(self, event, payload):
        if event == "user_signed_up":
            print(f"track signup {payload}")

s = UserSignups()
s.attach(Emailer()); s.attach(Analytics())
s.register("ash")
```

### Pythonic — callables + dict

```python
from collections import defaultdict
from typing import Callable

class EventBus:
    def __init__(self): self._subs: dict[str, list[Callable]] = defaultdict(list)
    def on(self, event: str):
        def deco(fn): self._subs[event].append(fn); return fn
        return deco
    def emit(self, event, payload=None):
        for fn in self._subs[event]: fn(payload)

bus = EventBus()

@bus.on("user_signed_up")
def send_email(u): print(f"emailing {u}")

@bus.on("user_signed_up")
def track(u): print(f"track {u}")

bus.emit("user_signed_up", "ash")
```

### Async Observer

```python
import asyncio

class AsyncBus:
    def __init__(self): self._subs = defaultdict(list)
    def on(self, e):
        def deco(fn): self._subs[e].append(fn); return fn
        return deco
    async def emit(self, e, payload=None):
        await asyncio.gather(*(fn(payload) for fn in self._subs[e]))
```

## 6. Backend examples

- **Django signals** — `post_save`, `pre_delete`, `request_started`. Senders emit; observers subscribe.
- **SQLAlchemy `event.listen`** — `before_insert`, `after_flush`, etc.
- **Pub/Sub brokers** — Redis pub-sub, Kafka topics, RabbitMQ fanout — Observer across processes.
- **Webhooks** — HTTP Observer: third parties subscribe; we POST when events happen.
- **WebSocket fan-out** — a connection registers as observer of a topic.
- **`asyncio.Event` / `asyncio.Queue`** — small Observer-flavoured primitives.

## 7. Pros / Cons

**Pros**
- OCP-friendly: add new observers without touching the subject.
- Loose coupling between producer and consumers.
- Natural fit for reactive flows.

**Cons**
- Order of notification is implicit — hard to reason about cascades.
- Memory leaks: observers that aren't detached hold references.
- Failures: one observer raising can take the whole notify down (mitigate with isolation).
- Silent ordering bugs: when observer A modifies the subject, observer B sees the new state.

**Don't use when**
- One consumer, predictable trigger — direct call is fine.
- Strong ordering / transactional semantics required — use a saga / orchestration.

## 8. Pull vs Push

- **Push** — Subject sends the new value(s) in `update(event, payload)`. Simpler; observers may receive data they don't need.
- **Pull** — Subject sends only "something happened, ask me"; observers pull state from the subject. More flexible; more coupling.

Most real systems use Push with structured event payloads.

## 9. Related patterns

- **Mediator** — Mediator centralises N-to-N coordination; Observer is one-to-many one-way.
- **Command** — events emitted to observers are often Commands.
- **Chain of Responsibility** — alternative when notifications should short-circuit.

## 9. Self-check

1. Difference between Observer and Mediator.
2. Why are Django signals an Observer mechanism?
3. List 3 failure modes of Observer.
4. Push vs Pull.
5. Show in 10 lines a Pythonic event bus using a `defaultdict` and a decorator.
