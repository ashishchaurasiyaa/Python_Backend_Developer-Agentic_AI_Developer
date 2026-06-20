# Flyweight

## 1. Intent

Use sharing to support large numbers of fine-grained objects efficiently — split each object's state into **intrinsic** (shared) and **extrinsic** (passed in per call).

## 2. Problem

You need millions of small objects, but most of their fields repeat. Storing them all naively blows up memory.

Examples:
- Each character in a document holds font, size, colour — but only 5 distinct fonts are used.
- A particle system with 100 000 particles — texture/colour repeat; position/velocity don't.
- Connection pool entries — the connection config is shared; the in-flight request data isn't.

## 3. Solution (UML sketch)

```
                                    ┌─────────────────────┐
                                    │   FlyweightFactory  │
                                    ├─────────────────────┤
                                    │ pool: dict[k, Fly]  │
                                    │ +get(key)           │
                                    └─────────────────────┘
                                              │
                                              ▼ returns shared
┌─────────────────┐                  ┌─────────────────────┐
│  Client         │ ───── uses ─────>│     Flyweight       │
└─────────────────┘   extrinsic→     ├─────────────────────┤
                                    │ intrinsic state…    │
                                    │ +operation(extrinsic)│
                                    └─────────────────────┘
```

- **Intrinsic** = stored *inside* the Flyweight; shared across users.
- **Extrinsic** = passed in per call; varies per user.

## 4. Participants

- **Flyweight** — stores intrinsic state, accepts extrinsic state per method call.
- **FlyweightFactory** — interns / dedupes flyweights so identical ones aren't recreated.
- **Client** — owns extrinsic state; asks the factory for the shared Flyweight.

## 5. Python implementation

### Tree-rendering example

```python
from dataclasses import dataclass

# Intrinsic — shared, expensive
@dataclass(frozen=True)
class TreeType:
    name: str
    color: str
    texture: str           # imagine this is a 1 MB asset

# Factory — dedupes
class TreeTypeFactory:
    _cache: dict[tuple, TreeType] = {}
    @classmethod
    def get(cls, name, color, texture) -> TreeType:
        key = (name, color, texture)
        if key not in cls._cache:
            cls._cache[key] = TreeType(name, color, texture)
        return cls._cache[key]

# Extrinsic — per instance, cheap
@dataclass
class Tree:
    x: int
    y: int
    type: TreeType         # shared reference

    def draw(self):
        # uses intrinsic state from self.type and extrinsic (x, y)
        print(f"draw {self.type.name}@({self.x},{self.y})")

# Use
forest = [
    Tree(x, y, TreeTypeFactory.get("oak", "green", "oak.png"))
    for x in range(1000) for y in range(1000)
]
# 1 million Trees but only ONE shared TreeType in memory
```

### Stdlib examples of interning (Flyweight in disguise)

- `sys.intern("string")` — string interning makes equal strings share memory.
- Small int caching (`-5 .. 256` are shared singletons in CPython).
- `True`, `False`, `None` — single shared instances.

## 6. Backend examples

- **ORM identity map** — SQLAlchemy's `Session.identity_map` ensures one Python object per (class, PK), Flyweight-style.
- **Connection pools** — shared connection objects fronting expensive sockets.
- **Logger registry** — `logging.getLogger("name")` returns the same instance for the same name.
- **HTTP/2 connection multiplexing** — one connection serving many streams.
- **Template engines** — compiled templates cached; render context (extrinsic) passed per call.

## 7. Pros / Cons

**Pros**
- Massive memory savings when objects share state.
- Faster construction (factory returns existing instance).

**Cons**
- Splitting state into intrinsic/extrinsic is hard to get right.
- Shared objects must be **immutable** or you'll get spooky mutation across clients.
- Lookup via factory adds a tiny per-call cost.

**Don't use when**
- Objects are few, or each has mostly unique state.
- Memory isn't a constraint and code clarity matters more.

## 8. Related patterns

- **Singleton** — both share instances; Singleton has exactly one; Flyweight has a *pool* keyed by intrinsic state.
- **Factory Method** — `FlyweightFactory.get(...)` is a Factory Method.
- **Composite** — Flyweight is often used in Composite leaves (e.g., glyphs in a document tree).

## 9. Self-check

1. Define intrinsic vs extrinsic state.
2. Why must Flyweights be immutable?
3. How is `sys.intern` a Flyweight mechanism?
4. Difference between Singleton and Flyweight.
5. When does Flyweight stop being worth it?
