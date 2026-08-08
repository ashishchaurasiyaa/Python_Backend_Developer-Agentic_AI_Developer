# Abstract Factory

> Related directory: [`Design_Patterns_Code/03_abstract_factory/`](../../../02_Year5+_Senior/01_System_Design/Design_Patterns_Code/03_abstract_factory/) is scaffolded (Django project + app) but the `sap_documents` models/views are still stub boilerplate — no actual Abstract Factory logic implemented there yet. See `01_factory_method.md`'s link for a working sibling example (Factory Method) in the meantime.

## 1. Intent

Provide an interface for creating **families** of related objects without specifying their concrete classes. *Factory Method* makes one product; *Abstract Factory* makes a matched **set**.

## 2. Problem

You have multiple object families that must be used **together** consistently. Example:
- Dev env: in-memory cache + sqlite repo + console mailer
- Prod env: redis cache + postgres repo + SES mailer

Mixing one family's pieces with another's would crash. You want one place that says *"here is the consistent set for env X"*.

Symptoms:
- Many `if env == "prod"` branches scattered across modules.
- A single change (swap Redis → Memcached) edits 10 files.

## 3. Solution (UML sketch)

```
        ┌──────────────────┐
        │ AbstractFactory  │
        ├──────────────────┤
        │ +make_cache()    │
        │ +make_repo()     │
        │ +make_mailer()   │
        └──────────────────┘
              △
   ┌──────────┴──────────┐
   │                     │
┌────────────┐     ┌────────────┐
│ DevFactory │     │ ProdFactory│
└────────────┘     └────────────┘
   │make_cache → MemoryCache       │make_cache → RedisCache
   │make_repo  → SQLiteRepo        │make_repo  → PostgresRepo
   │make_mailer→ ConsoleMailer     │make_mailer→ SESMailer
```

## 4. Participants

- **AbstractFactory** — declares creation methods for each product type.
- **ConcreteFactory** — overrides them to return a consistent family.
- **AbstractProducts** — interfaces (Cache, Repo, Mailer).
- **ConcreteProducts** — Redis/SQLite/SES implementations.
- **Client** — receives a factory; never sees concrete products directly.

## 5. Python implementation

```python
from typing import Protocol

# --- Product interfaces ---
class Cache(Protocol):
    def get(self, k: str): ...
    def set(self, k: str, v): ...

class Repo(Protocol):
    def save(self, obj): ...

class Mailer(Protocol):
    def send(self, to, body): ...

# --- Concrete families ---
class MemoryCache:
    def __init__(self): self._d = {}
    def get(self, k):    return self._d.get(k)
    def set(self, k, v): self._d[k] = v

class RedisCache:
    def get(self, k): ...   # real redis client
    def set(self, k, v): ...

class SQLiteRepo:
    def save(self, obj): print("sqlite:", obj)

class PostgresRepo:
    def save(self, obj): print("postgres:", obj)

class ConsoleMailer:
    def send(self, to, body): print(f"MAIL→{to}: {body}")

class SESMailer:
    def send(self, to, body): ...  # boto3 SES

# --- Abstract Factory ---
class InfraFactory(Protocol):
    def cache(self)  -> Cache: ...
    def repo(self)   -> Repo: ...
    def mailer(self) -> Mailer: ...

class DevFactory:
    def cache(self):  return MemoryCache()
    def repo(self):   return SQLiteRepo()
    def mailer(self): return ConsoleMailer()

class ProdFactory:
    def cache(self):  return RedisCache()
    def repo(self):   return PostgresRepo()
    def mailer(self): return SESMailer()

# --- Composition root ---
import os
def pick_factory() -> InfraFactory:
    return ProdFactory() if os.getenv("ENV") == "prod" else DevFactory()

factory = pick_factory()
cache, repo, mailer = factory.cache(), factory.repo(), factory.mailer()
```

The business code receives `(cache, repo, mailer)` and never knows which env it's in.

## 6. Backend examples

- **Django DB backends** — `django.db.backends.postgresql` provides matched `DatabaseWrapper`, `DatabaseFeatures`, `DatabaseOperations`, `DatabaseIntrospection`. One backend = one consistent family.
- **SQLAlchemy dialects** — each dialect is an Abstract Factory: it bundles type compilers, DDL compilers, default value executors that must agree with each other.
- **Cloud SDKs** — `boto3.session.Session(profile_name=…)` produces a coherent family of clients (S3, SQS, DynamoDB) bound to one account/region.
- **Settings-driven swap** — `DEBUG=True` toggles the entire infra family in tests.

## 7. Pros / Cons

**Pros**
- Guarantees product consistency within a family.
- Single switch point to swap entire environments.
- Hides concrete classes from client code.

**Cons**
- Adding a **new product type** (e.g., adding `make_queue`) forces every factory subclass to implement it. Painful when families are many.
- Lots of classes for what is sometimes just a config tuple.

**Don't use when**
- Products don't actually need to be consistent with each other — Factory Method per product is simpler.
- The "family" is one or two items — a config dict works.

## 8. Related patterns

- **Factory Method** — Abstract Factory's methods are often Factory Methods internally.
- **Builder** — Builder constructs *one complex object* step-by-step; Abstract Factory returns *several different* products at once.
- **Singleton** — Concrete factories are often singletons in practice.

## 9. Self-check

1. Difference between Abstract Factory and Factory Method.
2. Why is product *consistency* the core selling point of Abstract Factory?
3. Why does adding a new product type to AF "hurt" while adding a new family doesn't?
4. How is SQLAlchemy's dialect system an Abstract Factory?
5. When would you use a config dict instead?
