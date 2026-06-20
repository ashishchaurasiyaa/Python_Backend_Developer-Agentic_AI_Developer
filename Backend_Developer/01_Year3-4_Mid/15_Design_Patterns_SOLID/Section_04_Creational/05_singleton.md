# Singleton

> ⚠️ The most abused pattern. Default stance: **don't use it.** Read the "When NOT to use" section first.

## 1. Intent

Ensure a class has **only one instance**, and provide a global point of access to it.

## 2. Problem

You want exactly one of something (a connection pool, a logger, a config) and you want everyone to share that one.

Symptoms (the alleged need):
- "We only have one DB connection."
- "Logging config must be globally consistent."
- "I don't want to thread this object through every call."

## 3. Solution (UML sketch)

```
┌──────────────────────┐
│      Singleton       │
├──────────────────────┤
│  -instance: Singleton│   ← private static reference
├──────────────────────┤
│  +get_instance()     │   ← returns the one and only
└──────────────────────┘
```

## 4. Participants

- **Singleton** — owns its only instance, exposes a static accessor, hides the constructor.

## 5. Python implementations (4 flavours)

### A) Module-level singleton (the *Pythonic* one)

Python modules are imported once. A module-level object **is** a singleton.

```python
# config.py
class _Settings:
    db_url = "postgres://…"
    debug = False

settings = _Settings()        # the one instance

# usage anywhere
from config import settings
print(settings.db_url)
```

Zero ceremony. Thread-safe import. **This is what 95% of "singleton" needs in Python actually want.**

### B) `__new__` override

```python
class Logger:
    _instance: "Logger | None" = None

    def __new__(cls, *a, **kw):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

a = Logger()
b = Logger()
assert a is b
```

### C) Metaclass

```python
class SingletonMeta(type):
    _instances: dict[type, object] = {}
    def __call__(cls, *a, **kw):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*a, **kw)
        return cls._instances[cls]

class Cache(metaclass=SingletonMeta):
    def __init__(self): self.store = {}

assert Cache() is Cache()
```

### D) Decorator

```python
def singleton(cls):
    instances = {}
    def get(*a, **kw):
        if cls not in instances:
            instances[cls] = cls(*a, **kw)
        return instances[cls]
    return get

@singleton
class Bus:
    def __init__(self): self.subscribers = []
```

### Thread-safety note

If the singleton is built lazily and threads race in `__new__`, you can get two instances. Wrap with a lock:

```python
import threading
_lock = threading.Lock()

class Logger:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            with _lock:
                if cls._instance is None:        # double-checked locking
                    cls._instance = super().__new__(cls)
        return cls._instance
```

For most apps the module-level approach (A) sidesteps this entirely.

## 6. Backend examples

- **Django's `connection`** — `django.db.connection` is a thread-local singleton-ish wrapper.
- **Celery's `current_app`** — global accessor to the configured app.
- **`logging.getLogger("name")`** — same name → same logger instance (Singleton-by-name).
- **FastAPI's `app`** — typically a single module-level instance.
- **Connection pools** (SQLAlchemy `engine`, `redis-py` `ConnectionPool`) — usually one per process.

## 7. Pros / Cons

**Pros**
- Single shared resource, lazy init, global access.

**Cons (large)**
- **Hidden dependency.** Any function reaching `Logger.get_instance()` is secretly coupled to Logger. Hard to spot in code review.
- **Untestable.** Tests can't substitute it. Worse: tests pollute each other through the shared state.
- **Thread / multiprocess pitfalls.** Forked workers can inherit half-initialised state.
- **Lifecycle problems.** When do you tear it down?
- **Violates DIP and SRP** — combines "create me" + "be me" + "expose me globally".

## 7b. When NOT to use Singleton (and use what instead)

| You think you need… | Better |
|---|---|
| One logger | `logging.getLogger(__name__)` — the stdlib already does it |
| One config | Module-level constants / Pydantic Settings |
| One DB connection | Connection *pool* injected via DI (FastAPI `Depends`) |
| Global cache | A repo abstraction, concrete cache injected |
| Counter / state | Stop. Multi-process workers will betray you. Use Redis. |

**Rule:** if you're tempted to write a Singleton, try **module-level + dependency injection** first. 9 times out of 10 you don't need the pattern.

## 8. Related patterns

- **Abstract Factory** — concrete factories are often singletons.
- **Facade** — the Facade is often a singleton at the boundary.
- **Monostate / Borg** (Python folklore) — all instances share `__dict__`; behaves like a singleton without the access restriction.

## 9. Self-check

1. Why is module-level state the Pythonic Singleton?
2. Give two reasons Singleton hurts testability.
3. What is the "double-checked locking" idiom and why does it exist?
4. Why is `logging.getLogger(name)` "singleton-by-name"?
5. When you're tempted to add a Singleton, what should you try first?
