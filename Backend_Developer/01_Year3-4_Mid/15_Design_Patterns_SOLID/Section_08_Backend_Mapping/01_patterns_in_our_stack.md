# Patterns in Our Stack — FastAPI, Django, Celery, Kafka, Redis

> Naming the pattern inside a framework you already use is the fastest way to make pattern knowledge *stick* — and it's exactly what "have you read real codebases?" interview questions are probing.

## 1. Django

| Where | Pattern | Note |
|---|---|---|
| `Model.objects.filter(...)` | **Active Record** (+ Manager = Repository-ish) | Model knows how to persist itself — contrast with SQLAlchemy's Data Mapper |
| `QuerySet` chaining, lazy eval | **Builder** + lazy **Iterator** | `.filter().exclude().order_by()` builds a query object; SQL fires on iteration |
| Custom `Manager`/`QuerySet` | **Repository** | Your query vocabulary lives here, not in views |
| Middleware stack | **Chain of Responsibility** | Each layer may short-circuit the request |
| Signals (`post_save`) | **Observer** | Loose coupling — and its cost: hidden control flow ([anti-patterns](../Section_09_Anti_Patterns/)) |
| Class-Based Views | **Template Method** | `get()`/`post()` hooks in a fixed dispatch skeleton |
| Form/Serializer `validate_x()` | **Template Method** + **Strategy** | Framework calls your hooks in order |
| `settings.py` | **Singleton** (module-level) | The Pythonic singleton, not `__new__` |
| Storage backends (`FileSystemStorage`, `S3Storage`) | **Strategy** + **Adapter** | Swap by config |
| DB routers | **Strategy** | Route reads/writes per model |

```python
# Repository via custom QuerySet — the Django-idiomatic form
class OrderQuerySet(models.QuerySet):
    def pending(self):  return self.filter(status="pending")
    def for_tenant(self, t): return self.filter(tenant_id=t)

class Order(models.Model):
    objects = OrderQuerySet.as_manager()

Order.objects.for_tenant(t).pending()   # vocabulary, not raw filters in views
```

---

## 2. FastAPI

| Where | Pattern |
|---|---|
| `Depends(get_db)` | **Dependency Injection** (IoC container built into the framework) |
| `@lru_cache get_settings()` | **Singleton** + **Factory** |
| Yield-dependencies (`yield` + cleanup) | **Context/Disposable** — RAII-ish resource scoping |
| `app.add_middleware(...)`, ASGI chain | **Chain of Responsibility** / **Decorator** |
| Pydantic models at the boundary | **DTO** + **Adapter** (wire format ↔ domain) |
| `app.dependency_overrides[...]` in tests | **Strategy swap** — the seam DI buys you |
| `BackgroundTasks` | **Command** (deferred work object) |
| Custom `APIRoute` classes | **Template Method** |

```python
# DI + Strategy swap: one line makes the whole app testable
def get_payment_gateway() -> PaymentGateway:      # Factory
    return StripeGateway(settings.stripe_key)

@app.post("/pay")
def pay(gw: PaymentGateway = Depends(get_payment_gateway)): ...

app.dependency_overrides[get_payment_gateway] = lambda: FakeGateway()   # tests
```

---

## 3. Celery

| Where | Pattern |
|---|---|
| `@app.task` + `.delay()` | **Command** — call packaged as an object, queued, executed later, retryable |
| `chain`, `group`, `chord` | **Composite** (workflows of workflows) |
| Broker abstraction (Redis/RabbitMQ/SQS) | **Strategy** + **Adapter** |
| `Task.retry()` with backoff | **Template Method** (framework skeleton, your `run()`) |
| Beat scheduler | **Scheduler/Command queue** |
| Custom `Task` base class | **Template Method** (`on_failure`, `on_success` hooks) |

---

## 4. Kafka / messaging

| Where | Pattern |
|---|---|
| Producer → topic → many consumer groups | **Observer/Pub-Sub** at infrastructure scale |
| Consumer group rebalancing | **Mediator** (coordinator assigns partitions) |
| Kafka Connect + SMTs | **Pipes & Filters** / **Decorator** chain |
| Outbox pattern | **Command log** + **Observer** — see [`../../05_Microservices/04_outbox_event_sourcing.md`](../../05_Microservices/04_outbox_event_sourcing.md) |
| Schema registry + Avro evolution | **Adapter** across versions |
| DLQ | **Null Object**-ish sink / error channel |

---

## 5. Redis / caching

| Where | Pattern |
|---|---|
| Cache-aside (`get` → miss → load → `set`) | **Proxy** (caching proxy in front of the DB) |
| `lru_cache`, memoization | **Flyweight** / **Proxy** |
| Redis Pub/Sub | **Observer** |
| Distributed lock (Redlock) | **Mutex/Guard** |
| Rate limiter (token bucket in Lua) | **Strategy** (swap algorithm: fixed window / sliding / token bucket) |

```python
# Caching Proxy — same interface, transparently cached
class CachedUserRepo:
    def __init__(self, inner: UserRepo, r: Redis): self.inner, self.r = inner, r
    def get(self, uid: int) -> User:                  # SAME signature as inner
        if hit := self.r.get(f"u:{uid}"): return User.model_validate_json(hit)
        u = self.inner.get(uid)
        self.r.setex(f"u:{uid}", 300, u.model_dump_json())
        return u
# Callers don't change — that's what makes it a Proxy and not just "some caching code"
```

---

## 6. SQLAlchemy

| Where | Pattern |
|---|---|
| `Session` | **Unit of Work** — tracks changes, flushes as one transaction |
| ORM mapping | **Data Mapper** (contrast: Django's Active Record) |
| `Session.identity_map` | **Identity Map** — one object per PK per session |
| Lazy relationships | **Proxy** (loads on attribute access) |
| Query object | **Builder** |
| Connection pool | **Object Pool** |

**Interview gold:** *"Django is Active Record — the model knows persistence; great for CRUD speed, harder to unit-test domain logic without a DB. SQLAlchemy is Data Mapper + Unit of Work — domain objects stay persistence-ignorant, better for rich domain models. That's the actual trade-off behind 'Django vs FastAPI+SQLAlchemy'."*

---

## 7. Spotting drill (do this in your own repo)

```
Open any file you wrote last month and answer:
  1. Which pattern is already there, unnamed?
  2. Which if/elif ladder wants to be Strategy or State?
  3. Which class has a second reason to change (SRP)?
  4. Where is a signal/observer hiding control flow that should be explicit?
```

---

## 8. Self-check

1. Django Manager vs Repository pattern — same thing or not?
2. Where exactly is Unit of Work in SQLAlchemy, and what does it buy you?
3. Why is `Depends()` DI and not just "a function call"?
4. Celery task = which GoF pattern, and why does that framing explain retries?
5. Cache-aside is which pattern, and what makes it a Proxy rather than ad-hoc caching?

---

**Related:** [Behavioral](../Section_06_Behavioral/) · [Python Idioms](../Section_07_Python_Idioms_vs_GoF/) · [Interview Drills](../Section_10_Interview_Drills/) · Runnable code: [`../../../02_Year5+_Senior/01_System_Design/Design_Patterns_Code/`](../../../02_Year5+_Senior/01_System_Design/Design_Patterns_Code/)
