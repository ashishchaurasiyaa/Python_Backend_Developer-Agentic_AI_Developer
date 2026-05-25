# Mediator Pattern

> **Category:** Behavioral Design Pattern
> **Intent:** Reduce direct coupling between many objects by introducing a **central coordinator** that handles their interactions.

---

## 1. Problem Statement

Without Mediator: Every object knows every other → **N*N references** → spaghetti.

```
User ─── ChatRoom ─── User ─── User    (everyone talks to everyone)
```

With Mediator: All communication goes **through one central mediator**.

```
User ──→ Mediator ←── User
         ↑    ↑
         User User
```

Objects only know the mediator, not each other.

---

## 2. Real-World Analogies

- **Air traffic control** — pilots talk to ATC, not each other
- **Chat room** — users send to room, room broadcasts
- **Form validator** — fields don't talk; form coordinates
- **Event bus** — publishers + subscribers connected via bus

---

## 3. Structure (UML)

```
┌─────────────┐         ┌─────────────┐
│  Colleague  │─────────│  Mediator   │
│  (sender)   │ <──────>│             │
└─────────────┘         └─────────────┘
                              ↑
                              │ coordinates
                              ↓
                        ┌─────────────┐
                        │  Colleague  │
                        │  (receiver) │
                        └─────────────┘
```

---

## 4. Mediator vs Other Patterns

| Pattern | Direction | Purpose |
|---|---|---|
| **Mediator** | Many ↔ Many via central | Reduce coupling between peers |
| Observer | One → Many (push) | Notify state changes |
| Facade | One → Subsystem (1-way) | Simplify access |
| Event Bus | Producer → Consumer (decoupled) | Event-driven |

**Mediator vs Observer:**
- Observer: 1 subject, N listeners — listeners care about subject's events
- Mediator: N peers, all routed through mediator — peers don't know each other

---

## 5. Python Implementation

```python
from abc import ABC, abstractmethod

class Mediator(ABC):
    @abstractmethod
    def notify(self, sender, event, data=None): ...

class ChatRoom(Mediator):
    def __init__(self):
        self.users = {}

    def register(self, user):
        self.users[user.name] = user
        user.mediator = self

    def notify(self, sender, event, data=None):
        if event == "message":
            for name, user in self.users.items():
                if name != sender.name:
                    user.receive(sender.name, data)

class User:
    def __init__(self, name):
        self.name = name
        self.mediator = None
    def send(self, msg):
        self.mediator.notify(self, "message", msg)
    def receive(self, from_, msg):
        print(f"  [{self.name}] <{from_}> {msg}")
```

---

## 6. Use Cases

### ✅ Use when:
- Many objects need to communicate
- Components shouldn't tightly couple
- Behavior changes based on group state
- You're refactoring spaghetti object graph

### ❌ Don't use when:
- Only 2-3 objects (overkill)
- Simple pub/sub (use observer/event bus)
- Mediator becomes God class — split it

---

## 7. Real Production Examples

### Example 1: Form Validation
```python
class FormMediator:
    def field_changed(self, field):
        if field.name == "country":
            self.fields["state"].update_options(field.value)
        if field.name == "password":
            self.fields["submit"].enabled = field.value_strength_ok()
```

### Example 2: Chat / Discord channel
Every message goes through the channel, not user-to-user.

### Example 3: Workflow Engine
Tasks don't know which is next — workflow engine routes them.

### Example 4: GUI Components
Button click triggers mediator → updates label, enables submit, hides error.

### Example 5: Microservices Orchestrator
Saga orchestrator coordinates payment → inventory → shipping.

### Example 6: Game Lobby
Players don't message each other — lobby mediator routes invites, ready status, kicks.

---

## 8. Mediator vs Event Bus

| Mediator | Event Bus |
|---|---|
| Knows all participants | Decoupled — pub/sub |
| Synchronous, ordered | Async, fire-and-forget |
| Embeds business logic | Pure routing |
| One mediator per group | One bus for system |

**Choose mediator** when you need controlled, ordered interaction with logic.
**Choose event bus** for loose coupling, async, unknown subscribers.

---

## 9. Pitfalls

### Pitfall 1: Mediator becomes God Class
All logic concentrates → unmaintainable. Split into multiple mediators by concern.

### Pitfall 2: Hidden dependencies
Components depend on mediator's behavior, not other components — but mediator's logic is opaque. Document carefully.

### Pitfall 3: Performance bottleneck
All traffic through one mediator → may become hot path. Consider sharding.

### Pitfall 4: Too rigid
Mediator hardcodes interactions → adding new participant requires changes. Use registration pattern.

---

## 10. Interview Questions

**Q1: Mediator vs Observer?**
- Mediator: coordinates N peers (many-to-many)
- Observer: notifies N listeners of changes (one-to-many)

**Q2: Mediator vs Facade?**
- Mediator: bidirectional coordination
- Facade: one-way simplified access

**Q3: Real-world Mediator?**
- Saga orchestrator in distributed systems
- React Redux store (state mediator)
- Air traffic control
- Workflow engines (Temporal, Airflow DAG)

**Q4: How to avoid God Class?**
Split by domain. E.g., separate `AuthMediator`, `OrderMediator`, `NotificationMediator`.

**Q5: When NOT to use?**
- Few objects (2-3) — direct calls fine
- Loose async coupling — use event bus
- Pure pub/sub — use observer

**Q6: How to test mediator?**
Mock all colleagues. Verify mediator calls correct ones in correct order on each event.

---

## 11. Best Practices

1. **Keep mediator focused** — one domain
2. **Use registration** — colleagues register, don't hardcode
3. **Inject mediator** into colleagues — testability
4. **Document the contract** — events, signatures
5. **Avoid making mediator stateful** beyond necessary
6. **Combine with Observer** for hybrid pub/sub patterns

---

## 12. Key Takeaways

1. **Mediator centralizes** communication between peers
2. Reduces **N*N coupling** to N-to-1
3. Different from Observer (push) and Facade (one-way)
4. Real examples: chat, forms, saga orchestrator, workflow engine
5. Beware God Class — split by domain
6. Use registration for flexibility

---

## Related
- [[08_Observer_Pattern]] — push notification model
- [[13_Facade_Pattern]] — one-way wrapper
- [[Event_Sourcing_CQRS]] — distributed coordination
