# D — Dependency Inversion Principle (DIP)

> Runnable version of DIP applied via Dependency Injection: [`Design_Patterns_Code/14_dependency_injection/`](../../../02_Year5+_Senior/01_System_Design/Design_Patterns_Code/14_dependency_injection/) — `PaymentService` depends only on the abstract `PaymentGateway` interface; `DIContainer` binds Razorpay/PayU/Mock at runtime. 14 passing tests prove swapping the injected gateway changes nothing inside `PaymentService`.

## Statement

> *High-level modules should not depend on low-level modules. Both should depend on abstractions.*
> *Abstractions should not depend on details. Details should depend on abstractions.*

In plain words: **the business logic must not import the database driver**. Both should depend on an interface that says "I store stuff" — and the concrete database adapter implements it.

This is the principle behind **Hexagonal / Clean / Onion architecture** and FastAPI/Django dependency injection.

## The bad version — top-down concrete imports

```python
# BAD: business logic imports the concrete driver
import psycopg2

class OrderService:                                  # high-level
    def place(self, order):
        conn = psycopg2.connect("postgres://…")      # low-level detail
        conn.execute("INSERT INTO orders …", order)
```

Problems:
- Can't unit-test without a real Postgres.
- Can't swap to MySQL / Mongo / in-memory without rewriting business logic.
- High-level (use case) depends on low-level (driver). Wrong direction.

## The fixed version — invert the dependency

```python
from typing import Protocol

# 1. Abstraction (lives near the business logic)
class OrderRepository(Protocol):
    def save(self, order: "Order") -> None: ...

# 2. High-level depends on the abstraction
class OrderService:
    def __init__(self, repo: OrderRepository):
        self.repo = repo
    def place(self, order):
        self.repo.save(order)

# 3. Low-level details depend on the abstraction
class PostgresOrderRepository:
    def save(self, order): ...   # psycopg2 details here

class InMemoryOrderRepository:   # used in tests
    def __init__(self):
        self.items = []
    def save(self, order):
        self.items.append(order)

# 4. Composition root — only this place wires concretes together
service = OrderService(repo=PostgresOrderRepository())
```

Arrows now point from **details → abstraction ← high-level**. The business logic doesn't know Postgres exists.

## "Composition root" — the one place concretes meet

Build the object graph at the edge (FastAPI `main.py`, Django app startup, Celery `__init__`). Inside the business logic, **only protocols**. This single discipline gives you testability for free.

```python
# main.py — the composition root
from fastapi import FastAPI, Depends

app = FastAPI()

def get_repo() -> OrderRepository:
    return PostgresOrderRepository()

def get_service(repo: OrderRepository = Depends(get_repo)) -> OrderService:
    return OrderService(repo)

@app.post("/orders")
def create_order(order: Order, svc: OrderService = Depends(get_service)):
    svc.place(order)
```

In tests:
```python
app.dependency_overrides[get_repo] = lambda: InMemoryOrderRepository()
```

That's DIP + FastAPI in 6 lines.

## DIP vs Dependency Injection vs IoC

People conflate three things. Keep them separate:

| Term | What it is |
|---|---|
| **DIP** | A *principle*: depend on abstractions. |
| **DI** | A *technique*: pass dependencies in (constructor / setter / function arg) rather than `import`-and-instantiate inside. |
| **IoC** | A *pattern*: the framework calls your code, not vice versa. The framework owns the lifecycle (Django, FastAPI, Celery). |

DI is *how* you usually achieve DIP. IoC is the broader phenomenon.

## How DIP shows up in backend code

| Smell | DIP fix |
|---|---|
| `from redis import Redis` inside a use-case | Inject a `Cache` protocol; use-case never sees Redis |
| Django view directly calls `requests.post(...)` to a third-party API | Inject an `ExternalAPIClient`; mock in tests |
| Celery task imports the SMTP lib at module top | Inject a `Mailer`; the task takes it as a parameter |
| Business logic uses `datetime.utcnow()` and tests can't freeze time | Inject a `Clock` protocol |

## When DIP is overkill

- Throwaway scripts.
- Code with **one** implementation and **no** test isolation needed (e.g., a CLI calling `os.path`).
- Premature abstractions ("we *might* swap Postgres for Mongo someday" — no you won't).

The cost of DIP is one extra interface + one line of wiring. If the cost > the pain, skip it.

## Patterns built on DIP

Nearly all of them. Specifically:
- **Strategy, Adapter, Bridge** — explicit "depend on interface".
- **Factory Method, Abstract Factory** — *what to instantiate* is injected.
- **Repository pattern** (not in GoF but everywhere) — pure DIP.

## Self-check

1. Re-state DIP in your own words. Which two depend on which?
2. Why is "from psycopg2 import …" inside business logic a DIP violation?
3. What is a "composition root", and where does it live in a FastAPI app?
4. Difference between DIP and Dependency Injection.
5. Name a case where DIP is overkill.
