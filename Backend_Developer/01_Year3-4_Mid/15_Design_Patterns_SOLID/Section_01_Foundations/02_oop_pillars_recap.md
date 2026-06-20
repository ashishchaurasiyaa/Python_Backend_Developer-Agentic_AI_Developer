# 02 · OOP Pillars Recap (in Python)

> Patterns are built on these four pillars. If any feel shaky, every pattern will feel arbitrary.

## 1. Encapsulation — hide *what changes*

Bundle data + methods that operate on it, and **hide the internals** so callers depend on the interface, not the implementation. In Python there are no `private` keywords — convention does the work:

```python
class BankAccount:
    def __init__(self, owner: str, balance: float = 0):
        self.owner = owner          # public
        self._balance = balance     # protected (convention)
        self.__pin = None           # name-mangled (rare)

    # public interface — stable
    def deposit(self, amount: float) -> None:
        if amount <= 0:
            raise ValueError("amount must be positive")
        self._apply(amount)

    # private mechanism — can change freely
    def _apply(self, delta: float) -> None:
        self._balance += delta

    @property
    def balance(self) -> float:        # read-only view
        return self._balance
```

Why it matters for patterns: every pattern *isolates a thing that varies* behind a stable interface. That isolation is encapsulation.

## 2. Abstraction — expose *only* the essential

Encapsulation hides; abstraction **decides what to expose in the first place**. In Python the tools are:

- **Duck typing** — "if it has `.read()`, it's a file"
- **`abc.ABC`** + `@abstractmethod` — formal abstract base classes
- **`typing.Protocol`** — structural typing (PEP 544), modern preferred way for "interface" thinking

```python
from typing import Protocol

class Cache(Protocol):
    def get(self, key: str) -> bytes | None: ...
    def set(self, key: str, value: bytes, ttl: int = 0) -> None: ...

# Any class with those two methods IS a Cache. No inheritance required.
class RedisCache:
    def get(self, key): ...
    def set(self, key, value, ttl=0): ...

def warm_up(cache: Cache) -> None:    # depends on abstraction
    cache.set("ping", b"pong")
```

`Protocol` is how Python expresses "interface" without the Java weight.

## 3. Inheritance — *is-a*, share behavior

```python
class Animal:
    def __init__(self, name: str):
        self.name = name
    def speak(self) -> str:
        raise NotImplementedError

class Dog(Animal):
    def speak(self) -> str:
        return "woof"
```

**Use inheritance only when:**
- The child is genuinely an *is-a* of the parent (Liskov-substitutable)
- You want to share *implementation*, not just an interface

**Prefer composition when:**
- You want to share *behaviour without identity* (a `Logger` is not a `BaseService`; pass it in)
- The relationship is *has-a* or *uses-a*

> "Favour composition over inheritance" — the most repeated GoF advice. Patterns like Strategy, Decorator, Bridge exist *because* deep inheritance breaks.

### Multiple inheritance + MRO (Python-specific)

```python
class A: ...
class B(A): ...
class C(A): ...
class D(B, C): ...
print(D.__mro__)  # (D, B, C, A, object) — C3 linearization
```

Mixins exploit this:

```python
class TimestampMixin:
    @property
    def now(self):
        import datetime; return datetime.datetime.utcnow()

class User(TimestampMixin, BaseModel):
    ...
```

## 4. Polymorphism — same call, different behaviour

Two flavours matter:

### a) Subtype polymorphism (classical)
```python
def make_noise(a: Animal) -> str:
    return a.speak()      # works for Dog, Cat, Cow — same call

make_noise(Dog("Rex"))
```

### b) Duck-typed polymorphism (Pythonic)
```python
def write_all(stream, items):
    for x in items:
        stream.write(str(x))   # any object with .write() works
```

Patterns lean heavily on polymorphism — Strategy, State, Command, Visitor all dispatch on type.

## How the pillars map onto patterns

| Pillar | Patterns that lean on it |
|---|---|
| Encapsulation | Facade, Proxy, Memento (hides state) |
| Abstraction | Strategy, Bridge, Adapter (depend on interface, not class) |
| Inheritance | Template Method, Factory Method (subclasses customise) |
| Polymorphism | Strategy, State, Command, Visitor, Observer (same call, varying behaviour) |

## Self-check

1. Why is `_balance` "protected" rather than truly private?
2. When do you prefer `typing.Protocol` over `abc.ABC`?
3. State one reason to prefer composition over inheritance.
4. What does `D.__mro__` print, and what is C3 linearization?
5. Give an example of duck-typed polymorphism from the standard library.
