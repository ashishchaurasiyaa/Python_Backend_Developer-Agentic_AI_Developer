# Prototype

## 1. Intent

Create new objects by **cloning** an existing instance (the *prototype*), instead of constructing from scratch.

## 2. Problem

Object construction is **expensive** (DB load, network, heavy compute) or **complex** (lots of setup), and you need many similar instances. Building each from raw config is wasteful or error-prone.

Symptoms:
- "Template" objects loaded once at startup and copied per request.
- Configuration objects that differ from a base by 1-2 fields.
- Tests that need 50 nearly-identical fixtures.

## 3. Solution (UML sketch)

```
┌──────────────────┐
│   <<Prototype>>  │
├──────────────────┤
│ +clone(): self   │
└──────────────────┘
        △
        │
┌──────────────────┐
│ ConcretePrototype│
├──────────────────┤
│ +clone(): self   │
└──────────────────┘
```

Caller calls `prototype.clone()` instead of `ConcretePrototype(…)`.

## 4. Participants

- **Prototype** — declares `clone()`.
- **ConcretePrototype** — implements `clone()` (usually via `copy.deepcopy`).
- **Client** — holds a prototype and clones when it needs an instance.

## 5. Python implementation

Python has cloning built in: `copy.copy` (shallow) and `copy.deepcopy` (deep).

```python
import copy
from dataclasses import dataclass, field

@dataclass
class ReportTemplate:
    title: str
    sections: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def clone(self) -> "ReportTemplate":
        return copy.deepcopy(self)

# Heavy to build once
base = ReportTemplate(
    title="Quarterly Report",
    sections=["intro", "metrics", "outlook"],
    metadata={"author": "ops-team", "format": "pdf"},
)

# Cheap to copy many
for customer in customers:
    report = base.clone()
    report.title = f"Quarterly Report — {customer.name}"
    report.metadata["customer_id"] = customer.id
    send(report)
```

### Customizing `clone` — `__copy__` and `__deepcopy__`

If you want to control what gets copied (e.g., reset cached connections, generate a new id):

```python
class Connection:
    def __init__(self, host):
        self.host = host
        self.socket = open_socket(host)        # not safe to copy

    def __deepcopy__(self, memo):
        new = self.__class__.__new__(self.__class__)
        new.host = self.host
        new.socket = open_socket(self.host)    # fresh socket
        return new
```

### Shallow vs deep — the gotcha

```python
import copy

original = {"items": [1, 2, 3]}
shallow = copy.copy(original)
shallow["items"].append(4)
print(original)   # {'items': [1, 2, 3, 4]}   ← shared list!

deep = copy.deepcopy(original)
deep["items"].append(5)
print(original)   # unchanged
```

Default to `deepcopy` for Prototype; use shallow only when you've thought about which sub-objects should be shared.

## 6. Backend examples

- **Django form / model `__init__` defaults** — load a "template" record once, clone for each new record (e.g., default permissions for a tenant).
- **FastAPI / Pydantic** — `model.model_copy(update={...})` is Prototype: copy a Pydantic model with overrides.
- **Sessions / configs** — a base config object cloned per request with request-specific overrides.
- **Test factories** — `factory_boy`'s `factory.SubFactory` is conceptually Prototype-ish: start from a base, override fields per call.
- **Heavy ML / NLP** — load model once, deep-copy for thread-/request-local mutations.

## 7. Pros / Cons

**Pros**
- Cheap creation of similar objects.
- Avoids re-running expensive constructors.
- Variations expressed as "base + delta", not "rebuild from scratch".

**Cons**
- Deep copy semantics can surprise (file handles, sockets, callbacks).
- Hidden coupling: changing the prototype after callers cloned it can silently affect them if shallow copy is used.

**Don't use when**
- Construction is cheap.
- The state graph is full of unhashable / unpicklable / non-copyable parts (sockets, locks, generators).

## 8. Related patterns

- **Factory Method** — alternative way to get an instance; Factory builds, Prototype clones.
- **Memento** — both involve snapshotting state, but Memento is for undo/redo, not for spawning new instances.
- **Builder** — Builder constructs from parts; Prototype starts from a finished example.

## 9. Self-check

1. State the difference between Prototype and Factory Method.
2. Why does `copy.copy` (shallow) sometimes break Prototype?
3. When would you override `__deepcopy__`?
4. How does Pydantic's `model_copy(update=…)` map to Prototype?
5. Give a case where Prototype is the wrong choice.
