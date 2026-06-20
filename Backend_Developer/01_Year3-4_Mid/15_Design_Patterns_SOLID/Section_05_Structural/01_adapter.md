# Adapter

## 1. Intent

Convert the interface of a class into another interface clients expect. **Translate** between two incompatible APIs.

## 2. Problem

You have a working class (legacy, third-party, vendor SDK) whose API doesn't match what your code expects. You can't (or shouldn't) modify it.

Symptoms:
- New library has `.fetch(query)`, your code expects `.get(key)`.
- Old payment SDK returns dicts; new code expects Pydantic models.
- Two services with the same semantics but different method names.

## 3. Solution (UML sketch)

```
┌────────────┐         ┌──────────────┐         ┌──────────────┐
│  Client    │────────>│   Target     │         │   Adaptee    │
└────────────┘         ├──────────────┤         ├──────────────┤
                       │ +request()   │         │ +specific()  │
                       └──────────────┘         └──────────────┘
                              △                         △
                              │                         │
                       ┌──────────────┐                 │
                       │   Adapter    │─────────────────┘
                       ├──────────────┤  wraps
                       │ +request()   │  (calls specific())
                       └──────────────┘
```

## 4. Participants

- **Target** — the interface the client expects.
- **Adaptee** — the existing class with the incompatible interface.
- **Adapter** — wraps an Adaptee, exposes the Target interface, translates calls.

## 5. Python implementation

### Composition-based (preferred)

```python
from typing import Protocol

# Target — what our code wants
class Cache(Protocol):
    def get(self, key: str) -> bytes | None: ...
    def set(self, key: str, value: bytes, ttl: int = 0) -> None: ...

# Adaptee — third-party with a different shape
class LegacyMemcacheClient:
    def fetch(self, k): ...
    def store(self, k, v, expire_seconds): ...
    def delete_key(self, k): ...

# Adapter
class MemcacheAdapter:
    def __init__(self, legacy: LegacyMemcacheClient):
        self._inner = legacy
    def get(self, key: str) -> bytes | None:
        return self._inner.fetch(key)
    def set(self, key: str, value: bytes, ttl: int = 0) -> None:
        self._inner.store(key, value, ttl)

def warm_up(cache: Cache):
    cache.set("ping", b"pong")

warm_up(MemcacheAdapter(LegacyMemcacheClient()))
```

### Inheritance-based (rare, only when the Adaptee is friendly)

```python
class MemcacheAdapter(LegacyMemcacheClient):
    def get(self, key):   return self.fetch(key)
    def set(self, key, value, ttl=0): self.store(key, value, ttl)
```

Avoid if you'd inherit lots of methods you don't want exposed. **Composition wins by default.**

### Function adapter — the Pythonic version

When the "interface" is one method, an adapter is a function:

```python
def adapt(legacy: LegacyMemcacheClient) -> Cache:
    class _A:
        def get(self, k): return legacy.fetch(k)
        def set(self, k, v, ttl=0): legacy.store(k, v, ttl)
    return _A()
```

Or even simpler — a `lambda` passed to code expecting a callable.

## 6. Backend examples

- **DRF serializers** — Adapter between a Django Model and JSON/dict.
- **SQLAlchemy `TypeDecorator`** — Adapter between Python types and column types.
- **Logging handlers** — `logging.handlers.SysLogHandler` adapts Python `LogRecord` to the syslog protocol.
- **Auth backends** — adapt LDAP / OAuth / SAML to Django's `User` interface.
- **Message brokers** — `kombu` (Celery's transport layer) adapts AMQP, Redis, SQS, etc. to a single interface.
- **Storage backends** — `django-storages` adapts S3, GCS, Azure to Django's `Storage` ABC.

## 7. Pros / Cons

**Pros**
- Reuse legacy / third-party code without modifying it.
- Decouple client from a specific vendor's API.
- Easy substitution in tests (mock the Target, not the Adaptee).

**Cons**
- Extra layer of indirection.
- Easy to write thick adapters that grow business logic — keep them thin.

**Don't use when**
- The Adaptee already matches your interface.
- You're allowed to change the Adaptee (just rename methods).

## 8. Related patterns

- **Facade** — also wraps existing code, but offers a **simpler** interface, not a *converted* one. Adapter is intent-preserving; Facade is intent-narrowing.
- **Decorator** — wraps to **add behaviour**, not translate. Same interface in and out.
- **Bridge** — pre-designed to swap implementations. Adapter is retrofitted.
- **Proxy** — same interface in and out, controls **access**.

## 9. Self-check

1. State Adapter's intent in one line.
2. Difference between Adapter and Facade.
3. Why prefer composition over inheritance for Adapter?
4. Where does DRF use Adapter implicitly?
5. When is Adapter unnecessary?
