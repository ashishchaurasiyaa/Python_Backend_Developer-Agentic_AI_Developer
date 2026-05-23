# ABC & Protocols — Complete Guide

---

# PART 1 — THEORY (Deep Concepts)

## 1.1 ABC Kya Hai?

**ABC (Abstract Base Class)** = ek blueprint class jo directly instantiate nahi ho sakti.  
Sirf subclasses instantiate ho sakti hain — **aur unhe sare abstract methods implement karne padenge**.

```
ABC (blueprint)
├── abstract method: process()   ← subclass MUST implement
├── abstract method: validate()  ← subclass MUST implement
└── concrete method: log()       ← subclass inherit karti hai (optional override)

Subclass A: process() ✅  validate() ✅  → instantiate ho sakti hai
Subclass B: process() ✅  validate() ❌  → TypeError on instantiate
```

**Kab use karein ABC:**
- Jab tum chahte ho ki subclasses ek specific interface follow karein
- Plugin system: naye providers add karo bina existing code todhe
- Template Method Pattern: base class mein flow define, subclass mein steps

---

## 1.2 Protocol Kya Hai?

**Protocol** = structural subtyping — duck typing + type checking.

```
ABC check:      isinstance(obj, ABC) → True sirf agar ABC subclass ho
Protocol check: isinstance(obj, Protocol) → True agar shape match kare
```

**Protocol ka idea:** "Mujhe parwah nahi tum kaun ho — bas yeh methods hone chahiye."

```
# ABC approach — inheritance zaroori
class Drawable(ABC):
    @abstractmethod
    def draw(self): ...

class Circle(Drawable):   # explicit inherit karna padega
    def draw(self): ...

# Protocol approach — inheritance zaroori NAHI
class Drawable(Protocol):
    def draw(self) -> None: ...

class Circle:             # koi inheritance nahi
    def draw(self): ...   # bas method hona chahiye

# Dono kaam karenge:
def render(shape: Drawable): shape.draw()
render(Circle())   # works — Circle has draw()
```

---

## 1.3 ABC vs Protocol — Key Difference

| Feature | ABC | Protocol |
|---------|-----|---------|
| Inheritance | Required (`class Dog(Animal)`) | Not required |
| `isinstance()` check | Works (explicit subclass) | Only with `@runtime_checkable` |
| Shared implementation | Yes — concrete methods | No |
| Type checker support | Yes | Yes (better for duck typing) |
| Best for | Apna codebase, shared methods | Third-party classes, duck typing |
| Python version | 3.4+ | 3.8+ |

**Rule of thumb:**
- Apna codebase → ABC (control hai, shared methods bhi dene hain)
- Baahri library classes → Protocol (unhe inherit nahi kara sakte)

---

## 1.4 ABC Internals — `ABCMeta` Kaise Kaam Karta Hai

```
ABCMeta = metaclass for ABC

Jab tum class ABC(metaclass=ABCMeta) likhte ho:
  1. ABCMeta track karta hai kaunse methods @abstractmethod decorated hain
  2. Jab subclass banate ho — ABCMeta check karta hai sab implement hue?
  3. Agar nahi → __abstractmethods__ frozenset set hota hai
  4. Instantiate karte waqt → TypeError: Can't instantiate abstract class

ABC = shortcut = class jo ABCMeta ko metaclass use karti hai
  class MyABC(ABC): ...
  ==
  class MyABC(metaclass=ABCMeta): ...
```

---

## 1.5 Validator Types — `@abstractmethod` Ke Saath

```
@abstractmethod alone        → abstract instance method
@property + @abstractmethod  → abstract property (must implement as @property)
@classmethod + @abstractmethod → abstract classmethod
@staticmethod + @abstractmethod → abstract staticmethod
```

Order: `@property` / `@classmethod` / `@staticmethod` pehle, phir `@abstractmethod`.

---

## 1.6 `__subclasshook__` — Custom isinstance Logic

Kabhi kabhi `isinstance()` check customize karna hota hai.  
`__subclasshook__` se tum decide karte ho: "Is class ko meri ABC ka subclass maano?"

```
Return True          → haan, subclass hai
Return False         → nahi, subclass nahi
Return NotImplemented → normal MRO check karo
```

**Use case:** Standard library ABCs (`Iterable`, `Sized`, `Mapping`) yahi karte hain.  
`isinstance([], Iterable)` → True — list ne `Iterable` inherit nahi kiya, lekin `__iter__` hai.

---

## 1.7 `@runtime_checkable` Protocol

By default Protocol `isinstance()` se check nahi hota — sirf type checker ke liye hai.  
`@runtime_checkable` lagao toh `isinstance(obj, MyProtocol)` kaam karta hai.

**Warning:** Sirf method **presence** check hoti hai — signature nahi.

---

## 1.8 Template Method Pattern — ABC Ka Common Use

```
Abstract class mein algorithm ka skeleton likhte hain:
  def run(self):           ← concrete — order fixed
      self.validate()      ← abstract — subclass implements
      self.process()       ← abstract — subclass implements
      self.notify()        ← concrete — shared implementation

Subclass sirf steps override kare — overall flow ABC control karta hai.
```

---

# PART 2 — PRACTICAL (Working Code)

## 2.1 Basic ABC — Payment Gateway Example

```python
from abc import ABC, abstractmethod
from decimal import Decimal
import time

class PaymentGateway(ABC):
    """All payment gateways must implement these methods."""

    # Abstract methods — subclass MUST implement
    @abstractmethod
    def charge(self, amount: Decimal, currency: str, token: str) -> dict:
        """Charge the customer. Returns transaction dict."""
        ...

    @abstractmethod
    def refund(self, transaction_id: str, amount: Decimal) -> bool:
        """Refund a transaction. Returns success bool."""
        ...

    @abstractmethod
    def verify_webhook(self, payload: bytes, signature: str) -> bool:
        """Verify webhook signature from gateway."""
        ...

    # Concrete method — shared implementation for ALL gateways
    def charge_with_retry(self, amount: Decimal, currency: str,
                           token: str, max_retries: int = 3) -> dict:
        """Retry logic — same for all gateways."""
        for attempt in range(max_retries):
            try:
                return self.charge(amount, currency, token)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                time.sleep(2 ** attempt)   # exponential backoff
        return {}

    def log_transaction(self, txn: dict):
        """Logging — same for all gateways."""
        print(f"[{self.__class__.__name__}] Transaction: {txn}")


# --- Concrete Implementations ---
class StripeGateway(PaymentGateway):
    def __init__(self, api_key: str):
        self.api_key = api_key

    def charge(self, amount: Decimal, currency: str, token: str) -> dict:
        # Real: import stripe; stripe.PaymentIntent.create(...)
        return {"id": "ch_stripe_001", "amount": float(amount),
                "currency": currency, "status": "succeeded", "gateway": "stripe"}

    def refund(self, transaction_id: str, amount: Decimal) -> bool:
        print(f"Stripe refund: {transaction_id}, amount: {amount}")
        return True

    def verify_webhook(self, payload: bytes, signature: str) -> bool:
        import hmac, hashlib
        expected = hmac.new(self.api_key.encode(), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)


class RazorpayGateway(PaymentGateway):
    def __init__(self, key_id: str, key_secret: str):
        self.key_id = key_id
        self.key_secret = key_secret

    def charge(self, amount: Decimal, currency: str, token: str) -> dict:
        return {"id": "pay_razorpay_001", "amount": float(amount),
                "currency": currency, "status": "captured", "gateway": "razorpay"}

    def refund(self, transaction_id: str, amount: Decimal) -> bool:
        print(f"Razorpay refund: {transaction_id}")
        return True

    def verify_webhook(self, payload: bytes, signature: str) -> bool:
        return True  # simplified


# --- Polymorphic usage ---
def process_payment(gateway: PaymentGateway, amount: Decimal):
    """Works with ANY PaymentGateway implementation."""
    txn = gateway.charge_with_retry(amount, "INR", "tok_test")
    gateway.log_transaction(txn)
    return txn

stripe   = StripeGateway("sk_test_...")
razorpay = RazorpayGateway("rzp_key", "rzp_secret")

process_payment(stripe, Decimal("999.00"))
process_payment(razorpay, Decimal("499.00"))

# ABC cannot be instantiated directly
try:
    PaymentGateway()
except TypeError as e:
    print(e)  # Can't instantiate abstract class PaymentGateway with abstract methods
```

---

## 2.2 Abstract Property + Classmethod + Staticmethod

```python
from abc import ABC, abstractmethod

class DataStore(ABC):

    # Abstract property
    @property
    @abstractmethod
    def connection_string(self) -> str:
        """Return DB connection string."""
        ...

    # Abstract classmethod
    @classmethod
    @abstractmethod
    def from_env(cls) -> "DataStore":
        """Create instance from environment variables."""
        ...

    # Abstract staticmethod
    @staticmethod
    @abstractmethod
    def validate_config(config: dict) -> bool:
        """Validate configuration dict."""
        ...

    @abstractmethod
    def connect(self) -> bool: ...

    @abstractmethod
    def disconnect(self) -> None: ...

    # Concrete template method
    def connect_and_verify(self) -> bool:
        if self.connect():
            print(f"Connected: {self.connection_string}")
            return True
        return False


class PostgresStore(DataStore):
    def __init__(self, host: str, port: int, db: str):
        self.host, self.port, self.db = host, port, db

    @property
    def connection_string(self) -> str:
        return f"postgresql://{self.host}:{self.port}/{self.db}"

    @classmethod
    def from_env(cls) -> "PostgresStore":
        import os
        return cls(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "5432")),
            db=os.getenv("DB_NAME", "mydb")
        )

    @staticmethod
    def validate_config(config: dict) -> bool:
        return all(k in config for k in ["host", "port", "db"])

    def connect(self) -> bool:
        print(f"Connecting to Postgres...")
        return True

    def disconnect(self) -> None:
        print("Disconnected from Postgres")


pg = PostgresStore("localhost", 5432, "appdb")
pg.connect_and_verify()         # "Connecting..." + "Connected: postgresql://..."
pg_env = PostgresStore.from_env()
print(PostgresStore.validate_config({"host": "x", "port": 5432, "db": "y"}))  # True
```

---

## 2.3 Protocol — Structural Subtyping

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class Serializable(Protocol):
    def to_dict(self) -> dict: ...
    def to_json(self) -> str: ...


# These classes DO NOT inherit from Serializable
class UserRecord:
    def __init__(self, id: int, name: str):
        self.id, self.name = id, name

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name}

    def to_json(self) -> str:
        import json
        return json.dumps(self.to_dict())


class OrderRecord:
    def __init__(self, order_id: str, total: float):
        self.order_id, self.total = order_id, total

    def to_dict(self) -> dict:
        return {"order_id": self.order_id, "total": self.total}

    def to_json(self) -> str:
        import json
        return json.dumps(self.to_dict())


# Function accepts ANYTHING with to_dict() + to_json()
def save_to_db(record: Serializable) -> None:
    data = record.to_dict()
    print(f"Saving: {data}")

def export_json(record: Serializable) -> str:
    return record.to_json()

save_to_db(UserRecord(1, "Ashish"))        # works
save_to_db(OrderRecord("ORD-001", 999.0)) # works

# runtime_checkable isinstance
print(isinstance(UserRecord(1, "x"), Serializable))  # True
print(isinstance("string", Serializable))             # False
print(isinstance(42, Serializable))                   # False
```

---

## 2.4 Protocol with Generics — Repository Pattern

```python
from typing import Protocol, TypeVar

T = TypeVar("T")

class Repository(Protocol[T]):
    """Generic Repository — works with any entity type."""
    def get(self, id: int) -> T | None: ...
    def save(self, entity: T) -> T: ...
    def delete(self, id: int) -> bool: ...
    def list_all(self) -> list[T]: ...


class User:
    def __init__(self, id: int, name: str):
        self.id, self.name = id, name
    def __repr__(self):
        return f"User({self.id}, {self.name})"


class InMemoryUserRepo:
    """No inheritance — just satisfies Repository[User] shape."""

    def __init__(self):
        self._store: dict[int, User] = {}

    def get(self, id: int) -> User | None:
        return self._store.get(id)

    def save(self, entity: User) -> User:
        self._store[entity.id] = entity
        return entity

    def delete(self, id: int) -> bool:
        return bool(self._store.pop(id, None))

    def list_all(self) -> list[User]:
        return list(self._store.values())


class UserService:
    def __init__(self, repo: Repository[User]):
        self.repo = repo

    def create_user(self, id: int, name: str) -> User:
        return self.repo.save(User(id, name))

    def get_all(self) -> list[User]:
        return self.repo.list_all()


repo    = InMemoryUserRepo()
service = UserService(repo)    # Type checker: satisfies Repository[User]

service.create_user(1, "Ashish")
service.create_user(2, "Bob")
print(service.get_all())    # [User(1, Ashish), User(2, Bob)]
```

---

## 2.5 `__subclasshook__` — Custom isinstance

```python
from abc import ABC, abstractmethod

class Drawable(ABC):
    @abstractmethod
    def draw(self) -> None: ...

    @classmethod
    def __subclasshook__(cls, subclass):
        """
        Agar class mein draw() method hai — maano Drawable subclass hai.
        Inheritance zaroori nahi.
        """
        if cls is Drawable:
            if any("draw" in B.__dict__ for B in subclass.__mro__):
                return True
        return NotImplemented


class Circle:
    """No inheritance from Drawable — but has draw()"""
    def draw(self) -> None:
        print("Drawing circle...")


class Square:
    """No draw() method"""
    def render(self) -> None:
        print("Rendering square...")


print(isinstance(Circle(), Drawable))   # True  — has draw()
print(isinstance(Square(), Drawable))   # False — no draw()
print(issubclass(Circle, Drawable))     # True
print(issubclass(Square, Drawable))     # False
```

---

## 2.6 ABC + Protocol — Template Method Pattern

```python
from abc import ABC, abstractmethod
from typing import Protocol

# Protocol for external dependency (logger can be any library)
class Logger(Protocol):
    def info(self, msg: str) -> None: ...
    def error(self, msg: str) -> None: ...

# ABC for internal worker hierarchy
class BaseWorker(ABC):
    def __init__(self, logger: Logger):
        self.logger = logger

    @abstractmethod
    def process(self, data: dict) -> dict: ...

    @abstractmethod
    def validate_input(self, data: dict) -> bool: ...

    # Template method — flow is fixed, steps are customizable
    def run(self, data: dict) -> dict | None:
        if not self.validate_input(data):
            self.logger.error(f"Invalid input: {data}")
            return None
        self.logger.info(f"Processing: {data}")
        result = self.process(data)
        self.logger.info(f"Done: {result}")
        return result


class OrderWorker(BaseWorker):
    def validate_input(self, data: dict) -> bool:
        return "order_id" in data and "amount" in data

    def process(self, data: dict) -> dict:
        return {"order_id": data["order_id"],
                "status": "processed", "amount": data["amount"]}


class InvoiceWorker(BaseWorker):
    def validate_input(self, data: dict) -> bool:
        return "invoice_id" in data and "user_id" in data

    def process(self, data: dict) -> dict:
        return {"invoice_id": data["invoice_id"],
                "generated_at": "2026-05-21", "status": "sent"}


# Simple logger — satisfies Logger Protocol (no inheritance needed)
class PrintLogger:
    def info(self, msg: str) -> None:  print(f"INFO: {msg}")
    def error(self, msg: str) -> None: print(f"ERROR: {msg}")


logger  = PrintLogger()
workers = [OrderWorker(logger), InvoiceWorker(logger)]

workers[0].run({"order_id": "ORD-001", "amount": 999.0})
workers[1].run({"invoice_id": "INV-001", "user_id": "USR-01"})
workers[0].run({"bad": "data"})   # None — validation fails
```

---

## 2.7 Interview Q&A

**Q1: ABC aur Protocol mein kab kya choose karein?**
> ABC: apna codebase, subclasses control mein, shared concrete methods deni hain. Protocol: third-party classes integrate karni hों jo ABC inherit nahi kar sakti, ya sirf "shape" matter karta hai interface ke liye. Example: `logging.Logger` class Protocol se type hint karo — wo tumhara ABC inherit nahi karega.

**Q2: ABC instantiate kyun nahi hoti?**
> `ABCMeta` metaclass `__abstractmethods__` frozenset maintain karta hai. Jab class mein unimplemented abstract methods hain, yeh frozenset non-empty hoti hai. `type.__call__()` mein check hota hai — non-empty frozenset → `TypeError`. Subclass sab implement kare toh `__abstractmethods__` empty hoti hai → instantiate ho sakti hai.

**Q3: `@runtime_checkable` Protocol ki limitation kya hai?**
> `isinstance()` sirf method **presence** check karta hai, **signature** nahi. Agar class mein `draw` attribute hai jo string hai (callable nahi) — phir bhi `isinstance(obj, Drawable)` True return karega. Complete type safety ke liye `mypy` type checker use karo runtime pe nahi.

**Q4: Abstract property kaise likhte hain correctly?**
> `@property` pehle, phir `@abstractmethod`. Subclass mein `@property` se implement karo — `@abstractmethod` dobara likhna nahi padta. Common mistake: order ulta likhna ya sirf `@abstractmethod` likhna bina `@property` ke — toh subclass normal method se bhi satisfy kar deti hai.

**Q5: Template Method Pattern ABC ke saath kaise kaam karta hai?**
> ABC base class mein `run()` concrete method hoti hai jo algorithm ka order define karti hai: `validate() → process() → notify()`. Yeh methods abstract hoti hain. Subclass sirf steps implement kare — overall flow ABC control karta hai. Benefit: flow change karna ho toh sirf ABC mein badlo, saari subclasses update ho jaati hain.
