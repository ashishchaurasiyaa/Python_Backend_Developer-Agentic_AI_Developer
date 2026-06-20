# Proxy

## 1. Intent

Provide a **surrogate** or placeholder for another object to **control access** to it. The proxy presents the *same interface* as the real subject.

## 2. Problem

You need to do something *around* every access to an object: lazy-loading, caching, access control, logging, remote calls, refcount, etc. The real object shouldn't carry that concern, and callers shouldn't write the surrounding logic by hand.

## 3. Solution (UML sketch)

```
                ┌─────────────────┐
                │  <<Subject>>    │
                ├─────────────────┤
                │ +request()      │
                └─────────────────┘
                        △
            ┌───────────┴───────────┐
            │                       │
   ┌────────────────┐      ┌────────────────┐
   │  RealSubject   │      │     Proxy      │◇──┐
   ├────────────────┤      ├────────────────┤   │ real_subject
   │ +request()     │      │ +request()     │<──┘
   └────────────────┘      └────────────────┘
                                   │
                                   ▼ delegates to RealSubject
                                   (with extra logic before/after)
```

## 4. Participants

- **Subject** — interface used by clients.
- **RealSubject** — the real object doing the work.
- **Proxy** — implements Subject, holds a reference to RealSubject, controls access.

## 5. Python implementations (4 common flavours)

### A) Virtual Proxy (lazy initialisation)

```python
from typing import Protocol

class Report(Protocol):
    def generate(self) -> bytes: ...

class HeavyReport:
    def __init__(self):
        print("loading 200 MB of data…")          # expensive ctor
        self.data = ...
    def generate(self): return b"…"

class LazyReportProxy:
    def __init__(self):
        self._real: HeavyReport | None = None
    def generate(self):
        if self._real is None:
            self._real = HeavyReport()
        return self._real.generate()

r = LazyReportProxy()        # cheap
# … only when .generate() is called does HeavyReport instantiate
```

### B) Protection Proxy (access control)

```python
class ProtectedRepo:
    def __init__(self, real, user):
        self._real, self._user = real, user
    def delete(self, id):
        if not self._user.is_admin:
            raise PermissionError("admins only")
        return self._real.delete(id)
    def read(self, id):
        return self._real.read(id)
```

### C) Caching Proxy

```python
class CachingClient:
    def __init__(self, real):
        self._real = real
        self._cache: dict = {}
    def get_user(self, uid):
        if uid not in self._cache:
            self._cache[uid] = self._real.get_user(uid)
        return self._cache[uid]
```

### D) Remote Proxy (stub for a network object)

```python
class UserServiceClient:
    """Behaves like a local UserService; actually calls a microservice."""
    def __init__(self, base_url): self.base_url = base_url
    def get(self, uid):
        import httpx
        return httpx.get(f"{self.base_url}/users/{uid}").json()
```

### Generic Proxy via `__getattr__`

```python
class LoggingProxy:
    def __init__(self, target):
        self._target = target
    def __getattr__(self, name):
        attr = getattr(self._target, name)
        if callable(attr):
            def wrapper(*a, **kw):
                print(f"call {name}({a},{kw})")
                return attr(*a, **kw)
            return wrapper
        return attr

logger = LoggingProxy(SomeService())
logger.do_thing("x")        # prints "call do_thing(('x',),{})", then runs
```

## 6. Backend examples

- **Django querysets** — lazy: `User.objects.filter(...)` is a Virtual Proxy; SQL fires only on iteration.
- **SQLAlchemy lazy relationships** — `lazy="select"` loads related rows on attribute access.
- **`weakref.proxy`** — Protection Proxy variant that doesn't keep the target alive.
- **gRPC / Thrift / Pyro stubs** — Remote Proxies for cross-process calls.
- **CDN edge caches** — Caching Proxy at the network layer.
- **DRF permission classes / throttling** — Protection Proxies wrapping the view.

## 7. Pros / Cons

**Pros**
- Add control / lazy / cache / remote semantics transparently.
- Real subject is reused; can be swapped behind the same proxy.

**Cons**
- Indirection — bugs in the proxy look like bugs in the real subject.
- Caching proxies introduce invalidation problems.
- Lazy proxies surprise on errors at first-use, not at construction.

**Don't use when**
- A Decorator is what you want (adding behaviour, not controlling access).
- The real subject can host the concern itself without bloat.

## 8. Proxy vs Decorator vs Adapter vs Facade

| | Same interface in/out? | Adds behaviour? | Translates? |
|---|---|---|---|
| **Adapter** | No | No | Yes |
| **Decorator** | Yes | Yes (purpose) | No |
| **Proxy** | Yes | Yes (control/lazy) | No |
| **Facade** | No (narrower) | No | No |

Proxy's distinguishing word is **"control"** — access, lifetime, location, freshness.

## 9. Related patterns

- **Decorator** — see above.
- **Adapter** — different interface, same intent of wrapping.
- **Singleton** — common backing pattern for stateful proxies.

## 9. Self-check

1. Difference between Proxy and Decorator — one sentence each.
2. Name the four common Proxy flavours.
3. Why is Django's queryset a Virtual Proxy?
4. What's the catch with Caching Proxies?
5. Show how `__getattr__` enables a transparent proxy.
