# Decorator

> Confusion alert: the **Decorator pattern (GoF)** ≠ **Python's `@decorator` syntax**, though they share intent.

## 1. Intent

Attach **additional behaviour** to an object **dynamically**, by wrapping it. Keeps the original interface.

## 2. Problem

You need to add cross-cutting features (logging, caching, retries, auth, metrics, compression) to objects. Subclassing for every combination explodes (`LoggingCachingRetryingClient`).

Symptoms:
- Wanting to "stack" features at runtime.
- Same wrapping logic copied across many handler/service classes.

## 3. Solution (UML sketch)

```
       ┌──────────────────┐
       │  <<Component>>   │
       ├──────────────────┤
       │ +operation()     │
       └──────────────────┘
              △
   ┌──────────┼──────────────────┐
   │                              │
┌─────────────────┐    ┌────────────────────┐
│ ConcreteCompnt  │    │  Decorator (base)  │◇──┐
└─────────────────┘    ├────────────────────┤   │ wraps a Component
                       │ +operation()       │   │
                       └────────────────────┘<──┘
                              △
                              │
                ┌─────────────┴─────────────┐
                │                           │
        ┌────────────────┐         ┌────────────────┐
        │ LoggingDecor.  │         │ CachingDecor.  │
        └────────────────┘         └────────────────┘
```

## 4. Participants

- **Component** — interface for objects that can be wrapped.
- **ConcreteComponent** — the actual object.
- **Decorator** — also implements Component; holds a reference to a wrapped Component.
- **ConcreteDecorator** — adds behaviour before/after delegating to the wrappee.

## 5. Python — both flavours

### A) Object/class Decorator (classical GoF)

```python
from typing import Protocol

class DataSource(Protocol):
    def read(self) -> bytes: ...
    def write(self, data: bytes) -> None: ...

class FileDataSource:
    def __init__(self, path): self.path = path
    def read(self):           return open(self.path, "rb").read()
    def write(self, data):    open(self.path, "wb").write(data)

class DataSourceDecorator:
    def __init__(self, wrappee: DataSource):
        self._wrappee = wrappee
    def read(self):        return self._wrappee.read()
    def write(self, data): self._wrappee.write(data)

class EncryptionDecorator(DataSourceDecorator):
    def write(self, data):
        super().write(self._encrypt(data))
    def read(self):
        return self._decrypt(super().read())
    def _encrypt(self, b): return b[::-1]   # toy
    def _decrypt(self, b): return b[::-1]

class CompressionDecorator(DataSourceDecorator):
    def write(self, data):
        import gzip
        super().write(gzip.compress(data))
    def read(self):
        import gzip
        return gzip.decompress(super().read())

# Stack them at runtime
src = EncryptionDecorator(CompressionDecorator(FileDataSource("data.bin")))
src.write(b"hello world")     # compress → encrypt → write
src.read()                    # read → decrypt → decompress
```

### B) Python `@decorator` syntax (for functions)

```python
from functools import wraps
import time

def retries(n=3):
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            for i in range(n):
                try: return fn(*a, **kw)
                except Exception:
                    if i == n - 1: raise
                    time.sleep(0.1)
        return wrapper
    return deco

def cached(fn):
    cache = {}
    @wraps(fn)
    def wrapper(*a):
        if a not in cache: cache[a] = fn(*a)
        return cache[a]
    return wrapper

@retries(3)
@cached
def get_user(uid): return fetch_from_db(uid)
```

The `@deco` syntax IS Decorator pattern at the function level: it wraps `get_user` with `cached`, then with `retries`. Same intent, different unit (function vs object).

## 6. Backend examples

- **FastAPI/Flask route decorators** — `@app.get(...)`: function wrapping.
- **`@property`, `@staticmethod`, `@classmethod`** — class-attribute decorators.
- **Django's `@login_required`, `@cache_page`, `@csrf_exempt`** — Decorator pattern on view functions.
- **Logging / metrics / tracing middleware** — Starlette / Django middleware is the *class-Decorator* form: each middleware wraps the next.
- **DRF permission classes / throttling** — composed as decorators on viewsets.
- **`functools.lru_cache`** — caching decorator from the stdlib.

## 7. Pros / Cons

**Pros**
- Add features at runtime without subclassing.
- Combine features freely.
- Each decorator is single-responsibility.

**Cons**
- Order matters and is easy to get wrong (`encrypt(compress(x))` vs `compress(encrypt(x))`).
- Many layers = hard to debug ("why is this so slow?").
- Identity confusion: `isinstance(wrapped, FileDataSource)` is `False`.

**Don't use when**
- Features are static and few — subclass or inline them.
- You need to introspect the original object frequently (decorators hide it).

## 8. Related patterns

- **Adapter** — changes interface; Decorator preserves it.
- **Proxy** — also wraps preserving interface, but controls **access** rather than adding behaviour.
- **Composite** — also a recursive wrap, but multiple children; Decorator wraps one.
- **Chain of Responsibility** — middleware-like stacking; CoR can short-circuit, Decorator typically delegates always.

## 9. Self-check

1. Why is Decorator preferred over subclassing for cross-cutting features?
2. Difference between Decorator and Proxy.
3. Where in FastAPI/Django is the Decorator pattern explicit?
4. Why does order of decorators matter? Give an example.
5. What does `functools.wraps` do and why use it?
