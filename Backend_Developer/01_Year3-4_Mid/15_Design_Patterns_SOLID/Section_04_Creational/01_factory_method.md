# Factory Method

> Runnable version of this pattern: [`Design_Patterns_Code/02_factory/`](../../../02_Year5+_Senior/01_System_Design/Design_Patterns_Code/02_factory/) — `ChallanFactory` dispatches to the correct challan-type handler (Delivery/Pickup/Inter-Branch/Capital-Purchase/Sales), with a real test suite proving each input resolves to the right subclass.

## 1. Intent (one line)

Define an *interface* for creating an object, but let **subclasses** decide which concrete class to instantiate.

## 2. Problem

A class needs to create objects, but the exact class isn't known until runtime (config, plugin, environment). Hard-coding `Concrete()` everywhere couples your code to that class.

Symptoms:
- `if type == "x": return X()`-style ladders
- A constructor that takes a string and switches on it
- The same `import` of a concrete class repeated across many modules

## 3. Solution (UML sketch)

```
       ┌──────────────────┐                ┌──────────────────┐
       │   Creator        │                │   <<Product>>    │
       ├──────────────────┤  creates       ├──────────────────┤
       │ +factory_method()│ ─ ─ ─ ─ ─ ─ ─>│ +operation()      │
       │ +operation()     │                └──────────────────┘
       └──────────────────┘                        △
              △                                    │
              │                                    │
       ┌──────────────────┐                ┌──────────────────┐
       │ ConcreteCreator  │                │ ConcreteProduct  │
       ├──────────────────┤   creates      ├──────────────────┤
       │ +factory_method()│ ─ ─ ─ ─ ─ ─ ─>│ +operation()      │
       └──────────────────┘                └──────────────────┘
```

The Creator declares `factory_method()`; concrete creators decide *which* concrete product to return.

## 4. Participants

- **Product** — the interface concrete products share.
- **ConcreteProduct** — actual class returned by the factory method.
- **Creator** — declares the factory method (often abstract) and uses it.
- **ConcreteCreator** — overrides the factory method to return a specific product.

## 5. Python — classical version

```python
from abc import ABC, abstractmethod

class Notification(ABC):
    @abstractmethod
    def send(self, to: str, msg: str) -> None: ...

class EmailNotification(Notification):
    def send(self, to, msg): print(f"EMAIL → {to}: {msg}")

class SMSNotification(Notification):
    def send(self, to, msg): print(f"SMS   → {to}: {msg}")

class NotificationCreator(ABC):
    @abstractmethod
    def factory(self) -> Notification: ...

    def notify(self, to: str, msg: str):
        product = self.factory()       # Creator uses the abstract product
        product.send(to, msg)

class EmailCreator(NotificationCreator):
    def factory(self): return EmailNotification()

class SMSCreator(NotificationCreator):
    def factory(self): return SMSNotification()

# Caller picks the creator — the rest is polymorphic
creator: NotificationCreator = EmailCreator()
creator.notify("ash@x.com", "hi")
```

## 5b. Pythonic version — a registry

A class hierarchy is overkill for many real cases. A dict of constructors works:

```python
_REGISTRY: dict[str, type[Notification]] = {}

def register(name):
    def deco(cls):
        _REGISTRY[name] = cls
        return cls
    return deco

@register("email")
class EmailNotification(Notification):
    def send(self, to, msg): ...

@register("sms")
class SMSNotification(Notification):
    def send(self, to, msg): ...

def make(name: str) -> Notification:
    return _REGISTRY[name]()             # this function IS the factory method
```

Adding a 3rd channel = `@register("push") class PushNotification…`. No `if/elif` ever.

## 6. Backend examples

- **Django** — `DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"`. The framework reads the dotted path and constructs the field — a factory method based on a settings string.
- **SQLAlchemy** — `create_engine("postgresql://…")` returns a `Dialect`-specific engine. The URL is parsed; a concrete factory picks `PGDialect` vs `SQLiteDialect`.
- **FastAPI dependencies** — `Depends(get_repo)` calls a function that returns the right repo for the env (a factory method by another name).
- **Celery brokers** — `broker_url` string → concrete `Broker` instance via internal registry.

## 7. Pros / Cons

**Pros**
- Decouples *who creates* from *who uses*.
- Adding a new product type doesn't touch existing creators.
- Easy to inject mocks/fakes in tests (override the factory).

**Cons**
- One extra layer (Creator + ConcreteCreator) per product family.
- Easy to over-engineer; a single function or `dict` often suffices.

**Don't use when**
- You only have one concrete class, and you're "future-proofing".
- A `dict[str, callable]` would obviously do the job.

## 8. Related patterns

- **Abstract Factory** — *family* of related products; Factory Method makes *one*.
- **Template Method** — Factory Method is often used *inside* a Template Method's hook.
- **Prototype** — alternative way to get an object: clone an existing one instead of constructing fresh.

## 9. Self-check

1. Difference between Factory Method and Abstract Factory in one sentence.
2. Why is `dict[str, type[T]]` a valid Pythonic Factory Method?
3. Where does the Django settings system implicitly use Factory Method?
4. Give an example of Factory Method enabling test substitution.
5. When is Factory Method an over-engineering trap?
