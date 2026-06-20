# L — Liskov Substitution Principle (LSP)

## Statement (Barbara Liskov)

> *Subtypes must be substitutable for their base types — without the caller noticing.*

Anywhere code uses a `Base`, you must be able to drop in a `Sub` and have nothing break — same expectations, same contract.

LSP is what makes polymorphism trustworthy. Break LSP and every "is-a" lie becomes a runtime bug.

## The classic violation — Rectangle / Square

```python
# BAD: Square IS-A Rectangle… until you set width and height independently
class Rectangle:
    def __init__(self, w: int, h: int):
        self.w, self.h = w, h
    def set_width(self, w):  self.w = w
    def set_height(self, h): self.h = h
    @property
    def area(self):          return self.w * self.h

class Square(Rectangle):
    def set_width(self, w):
        self.w = self.h = w           # squashes height too
    def set_height(self, h):
        self.w = self.h = h

def stretch(r: Rectangle):
    r.set_width(5)
    r.set_height(4)
    assert r.area == 20               # holds for Rectangle, FAILS for Square (25)
```

`Square` *is-a* `Rectangle` mathematically, but **its behaviour violates the caller's expectations**. LSP broken.

**Fix:** drop the inheritance. Square and Rectangle both implement a `Shape` interface; neither extends the other.

```python
class Shape(Protocol):
    @property
    def area(self) -> int: ...

class Rectangle:
    def __init__(self, w, h): self.w, self.h = w, h
    @property
    def area(self): return self.w * self.h

class Square:
    def __init__(self, side): self.side = side
    @property
    def area(self): return self.side ** 2
```

## Subtle violations to watch for

LSP breaks not only via wrong return values but via:

### 1. Strengthening preconditions

```python
class FileWriter:
    def write(self, data: bytes) -> None: ...

class AuditedWriter(FileWriter):
    def write(self, data: bytes) -> None:
        if not data.startswith(b"AUDIT|"):
            raise ValueError("must start with AUDIT|")   # caller didn't expect this
```

Subclass demands *more* than the base — callers built for `FileWriter` break.

### 2. Weakening postconditions

```python
class UserRepo:
    def save(self, user) -> User:           # contract: returns saved user
        ...

class CachingUserRepo(UserRepo):
    def save(self, user):                   # silently returns None
        cache.set(user.id, user)
```

Caller did `saved = repo.save(u); print(saved.id)` — now crashes.

### 3. Throwing new exceptions

```python
class Sender:
    def send(self, msg) -> None: ...

class SMSSender(Sender):
    def send(self, msg):
        raise TimeoutError(...)   # base never declared this
```

If callers don't expect `TimeoutError`, the substitution is unsafe.

### 4. Changing invariants

```python
class Account:
    def __init__(self):
        self.balance = 0       # invariant: balance >= 0

class OverdraftAccount(Account):
    def withdraw(self, x):
        self.balance -= x      # breaks the invariant; existing code may divide by it
```

## How LSP shows up in backend code

| Smell | LSP fix |
|---|---|
| `class ReadOnlyList(list)` raises on `append` | Don't subclass `list`; implement `collections.abc.Sequence` |
| Custom `Exception` subclass that the caller can't handle generically | Inherit at the right level; preserve the contract |
| ORM model subclass that breaks queries (e.g., `Manager` returns a filtered queryset, surprises callers) | Use proxy models or explicit managers, not silent overrides |
| `MockEmailer` raises in tests but real `Emailer` doesn't | Mock must obey the same contract as production |

## The right inheritance question

Before `class Sub(Base)`, ask: **"Can every caller of Base work with Sub without knowing the difference?"** If the honest answer is no, **don't inherit** — use composition (Adapter / Decorator / Strategy).

## SOLID linkage

- **LSP enables OCP.** OCP only works if subtypes are interchangeable.
- **LSP enforces DIP.** Depending on abstractions only pays off if substitutions are safe.
- Patterns most affected: **Template Method, Strategy, Decorator, State**.

## Self-check

1. State LSP in your own words.
2. Why is the Square/Rectangle case a violation even though Square *is-a* Rectangle mathematically?
3. Give an example of an LSP violation via "strengthened preconditions".
4. Why is `class ReadOnlyList(list)` a code smell?
5. What's the rule of thumb question to ask before `class Sub(Base):`?
