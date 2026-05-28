"""
ABC & Protocols — Practical Runnable Examples
==============================================
Topics covered:
  - ABC (Abstract Base Class) + abstractmethod
  - Abstract property, classmethod, staticmethod
  - Concrete (shared) methods on ABC — template method pattern
  - Protocol — structural subtyping (duck typing + type safety)
  - @runtime_checkable Protocol + isinstance()
  - Generic Protocol with TypeVar
  - __subclasshook__ — custom isinstance logic
  - ABC vs Protocol decision guide
  - Real-world patterns: PaymentGateway, Repository, Worker pipeline

How to run:
  python 02_abc_protocols_practical.py

pip install:
  (none — standard library only)
"""

from abc import ABC, abstractmethod, ABCMeta
from typing import Protocol, TypeVar, runtime_checkable, Generic
from decimal import Decimal
import json
import time

# ─── Section 1: ABC Basics — Payment Gateway Example ───

print("=" * 60)
print("SECTION 1: ABC — Payment Gateway")
print("=" * 60)


class PaymentGateway(ABC):
    """All payment gateways must implement these abstract methods.

    INTERVIEW: ABC enforces a contract — subclasses that miss any abstract
    method cannot be instantiated. ABCMeta tracks __abstractmethods__ frozenset.
    """

    # INTERVIEW: @abstractmethod = subclass MUST implement this
    @abstractmethod
    def charge(self, amount: Decimal, currency: str, token: str) -> dict:
        """Charge the customer. Return a transaction dict."""
        ...

    @abstractmethod
    def refund(self, transaction_id: str, amount: Decimal) -> bool:
        """Refund a transaction. Return success bool."""
        ...

    @abstractmethod
    def verify_webhook(self, payload: bytes, signature: str) -> bool:
        """Verify webhook signature from the gateway."""
        ...

    # INTERVIEW: Concrete method — shared across ALL gateways, no need to re-implement
    # This is the Template Method Pattern: ABC controls the flow
    def charge_with_retry(
        self, amount: Decimal, currency: str, token: str, max_retries: int = 3
    ) -> dict:
        """Retry logic with exponential backoff — same for all gateways."""
        last_exc: Exception = RuntimeError("No attempts made")
        for attempt in range(max_retries):
            try:
                return self.charge(amount, currency, token)
            except Exception as exc:
                last_exc = exc
                if attempt < max_retries - 1:
                    time.sleep(0.01 * (2 ** attempt))  # short sleep for demo
        raise last_exc

    def log_transaction(self, txn: dict) -> None:
        """Structured log — same format for all gateways."""
        print(f"[{self.__class__.__name__}] txn={txn}")


class StripeGateway(PaymentGateway):
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def charge(self, amount: Decimal, currency: str, token: str) -> dict:
        return {
            "id": "ch_stripe_001",
            "amount": float(amount),
            "currency": currency,
            "status": "succeeded",
            "gateway": "stripe",
        }

    def refund(self, transaction_id: str, amount: Decimal) -> bool:
        print(f"Stripe refund: {transaction_id}, ₹{amount}")
        return True

    def verify_webhook(self, payload: bytes, signature: str) -> bool:
        import hmac, hashlib
        expected = hmac.new(self.api_key.encode(), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)


class RazorpayGateway(PaymentGateway):
    def __init__(self, key_id: str, key_secret: str) -> None:
        self.key_id = key_id
        self.key_secret = key_secret

    def charge(self, amount: Decimal, currency: str, token: str) -> dict:
        return {
            "id": "pay_razorpay_001",
            "amount": float(amount),
            "currency": currency,
            "status": "captured",
            "gateway": "razorpay",
        }

    def refund(self, transaction_id: str, amount: Decimal) -> bool:
        print(f"Razorpay refund: {transaction_id}")
        return True

    def verify_webhook(self, payload: bytes, signature: str) -> bool:
        return True  # simplified


def process_payment(gateway: PaymentGateway, amount: Decimal) -> dict:
    """Works with ANY PaymentGateway subclass — polymorphism in action."""
    txn = gateway.charge_with_retry(amount, "INR", "tok_test")
    gateway.log_transaction(txn)
    return txn


stripe = StripeGateway("sk_test_abc")
razorpay = RazorpayGateway("rzp_key", "rzp_secret")

process_payment(stripe, Decimal("999.00"))
process_payment(razorpay, Decimal("499.00"))

# INTERVIEW: ABC cannot be instantiated directly
try:
    PaymentGateway()  # type: ignore
except TypeError as e:
    print(f"\nABC instantiation error: {e}")


# ─── Section 2: Abstract Property, Classmethod, Staticmethod ───

print("\n" + "=" * 60)
print("SECTION 2: Abstract Property / Classmethod / Staticmethod")
print("=" * 60)


class DataStore(ABC):
    """Abstract data store — demonstrates all abstract decorator combinations."""

    # INTERVIEW: Order matters — @property FIRST, then @abstractmethod
    @property
    @abstractmethod
    def connection_string(self) -> str:
        """Must be implemented as a @property in subclass."""
        ...

    # INTERVIEW: @classmethod FIRST, then @abstractmethod
    @classmethod
    @abstractmethod
    def from_env(cls) -> "DataStore":
        """Factory method — create instance from environment variables."""
        ...

    # INTERVIEW: @staticmethod FIRST, then @abstractmethod
    @staticmethod
    @abstractmethod
    def validate_config(config: dict) -> bool:
        """Validate a config dict — no instance or class state needed."""
        ...

    @abstractmethod
    def connect(self) -> bool:
        ...

    @abstractmethod
    def disconnect(self) -> None:
        ...

    # Concrete template method
    def connect_and_verify(self) -> bool:
        if self.connect():
            print(f"Connected: {self.connection_string}")
            return True
        return False


class PostgresStore(DataStore):
    def __init__(self, host: str, port: int, db: str) -> None:
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
            db=os.getenv("DB_NAME", "mydb"),
        )

    @staticmethod
    def validate_config(config: dict) -> bool:
        return all(k in config for k in ("host", "port", "db"))

    def connect(self) -> bool:
        print("Connecting to Postgres...")
        return True

    def disconnect(self) -> None:
        print("Disconnected from Postgres")


pg = PostgresStore("localhost", 5432, "appdb")
pg.connect_and_verify()
pg_from_env = PostgresStore.from_env()
print(f"from_env host: {pg_from_env.host}")
print(f"validate_config: {PostgresStore.validate_config({'host': 'x', 'port': 5432, 'db': 'y'})}")


# ─── Section 3: Protocol — Structural Subtyping ───

print("\n" + "=" * 60)
print("SECTION 3: Protocol — Structural Subtyping")
print("=" * 60)


# INTERVIEW: @runtime_checkable lets isinstance() check Protocol compliance
# WARNING: isinstance only checks method *presence*, not signature!
@runtime_checkable
class Serializable(Protocol):
    def to_dict(self) -> dict: ...
    def to_json(self) -> str: ...


# INTERVIEW: These classes do NOT inherit from Serializable — but they satisfy the Protocol
# This is "duck typing" + type safety. Useful for third-party classes you can't modify.
class UserRecord:
    def __init__(self, id: int, name: str) -> None:
        self.id, self.name = id, name

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name}

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class OrderRecord:
    def __init__(self, order_id: str, total: float) -> None:
        self.order_id, self.total = order_id, total

    def to_dict(self) -> dict:
        return {"order_id": self.order_id, "total": self.total}

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


def save_record(record: Serializable) -> None:
    """Accepts ANY object that has to_dict() + to_json() — no inheritance needed."""
    print(f"Saving: {record.to_dict()}")


def export_json(record: Serializable) -> str:
    return record.to_json()


save_record(UserRecord(1, "Ashish"))
save_record(OrderRecord("ORD-001", 999.0))

# runtime_checkable isinstance checks
print(f"\nisinstance UserRecord → Serializable: {isinstance(UserRecord(1, 'x'), Serializable)}")
print(f"isinstance str → Serializable: {isinstance('hello', Serializable)}")
print(f"isinstance int → Serializable: {isinstance(42, Serializable)}")


# ─── Section 4: Generic Protocol — Repository Pattern ───

print("\n" + "=" * 60)
print("SECTION 4: Generic Protocol — Repository Pattern")
print("=" * 60)

T = TypeVar("T")


# INTERVIEW: Protocol[T] = generic protocol — type-safe repository for any entity
class Repository(Protocol[T]):
    """Generic CRUD repository. Works with any entity type."""

    def get(self, id: int) -> T | None: ...
    def save(self, entity: T) -> T: ...
    def delete(self, id: int) -> bool: ...
    def list_all(self) -> list[T]: ...


class User:
    def __init__(self, id: int, name: str) -> None:
        self.id = id
        self.name = name

    def __repr__(self) -> str:
        return f"User({self.id}, {self.name!r})"


class InMemoryUserRepo:
    """No inheritance from Repository — just satisfies Repository[User] shape."""

    def __init__(self) -> None:
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
    """Takes a Repository[User] — any matching implementation works."""

    def __init__(self, repo: Repository[User]) -> None:
        self.repo = repo

    def create_user(self, id: int, name: str) -> User:
        return self.repo.save(User(id, name))

    def get_all(self) -> list[User]:
        return self.repo.list_all()

    def remove_user(self, id: int) -> bool:
        return self.repo.delete(id)


repo = InMemoryUserRepo()
service = UserService(repo)  # type checker: satisfies Repository[User]

service.create_user(1, "Ashish")
service.create_user(2, "Bob")
print(f"All users: {service.get_all()}")
print(f"Delete 1: {service.remove_user(1)}")
print(f"After delete: {service.get_all()}")


# ─── Section 5: __subclasshook__ — Custom isinstance ───

print("\n" + "=" * 60)
print("SECTION 5: __subclasshook__")
print("=" * 60)


class Drawable(ABC):
    """Custom isinstance — any class with draw() qualifies as Drawable."""

    @abstractmethod
    def draw(self) -> None: ...

    @classmethod
    def __subclasshook__(cls, subclass: type) -> bool | type(NotImplemented):
        # INTERVIEW: return True = yes it's a subclass, False = no, NotImplemented = default MRO
        if cls is Drawable:
            if any("draw" in B.__dict__ for B in subclass.__mro__):
                return True
        return NotImplemented  # type: ignore[return-value]


class Circle:
    """No Drawable inheritance — but has draw()."""
    def draw(self) -> None:
        print("Drawing circle...")


class Square:
    """No draw() — does not satisfy Drawable."""
    def render(self) -> None:
        print("Rendering square...")


print(f"isinstance(Circle(), Drawable): {isinstance(Circle(), Drawable)}")   # True
print(f"isinstance(Square(), Drawable): {isinstance(Square(), Drawable)}")   # False
print(f"issubclass(Circle, Drawable):   {issubclass(Circle, Drawable)}")     # True
print(f"issubclass(Square, Drawable):   {issubclass(Square, Drawable)}")     # False


# ─── Section 6: Template Method Pattern — ABC + Protocol together ───

print("\n" + "=" * 60)
print("SECTION 6: Template Method Pattern (ABC + Protocol)")
print("=" * 60)


# Protocol for external dependency (logger) — can be stdlib logging, structlog, etc.
class Logger(Protocol):
    def info(self, msg: str) -> None: ...
    def error(self, msg: str) -> None: ...


# ABC for internal worker hierarchy — controls algorithm flow
class BaseWorker(ABC):
    def __init__(self, logger: Logger) -> None:
        self.logger = logger

    @abstractmethod
    def validate_input(self, data: dict) -> bool: ...

    @abstractmethod
    def process(self, data: dict) -> dict: ...

    # INTERVIEW: Template method — flow fixed here, steps customised by subclasses
    def run(self, data: dict) -> dict | None:
        if not self.validate_input(data):
            self.logger.error(f"Invalid input: {data}")
            return None
        self.logger.info(f"Processing: {list(data.keys())}")
        result = self.process(data)
        self.logger.info(f"Done: {result}")
        return result


class OrderWorker(BaseWorker):
    def validate_input(self, data: dict) -> bool:
        return "order_id" in data and "amount" in data

    def process(self, data: dict) -> dict:
        return {"order_id": data["order_id"], "status": "processed", "amount": data["amount"]}


class InvoiceWorker(BaseWorker):
    def validate_input(self, data: dict) -> bool:
        return "invoice_id" in data and "user_id" in data

    def process(self, data: dict) -> dict:
        return {"invoice_id": data["invoice_id"], "generated_at": "2026-05-22", "status": "sent"}


# PrintLogger satisfies Logger Protocol — no inheritance needed
class PrintLogger:
    def info(self, msg: str) -> None:
        print(f"  INFO : {msg}")

    def error(self, msg: str) -> None:
        print(f"  ERROR: {msg}")


logger = PrintLogger()
workers: list[BaseWorker] = [OrderWorker(logger), InvoiceWorker(logger)]

print("OrderWorker valid input:")
workers[0].run({"order_id": "ORD-001", "amount": 999.0})

print("InvoiceWorker valid input:")
workers[1].run({"invoice_id": "INV-001", "user_id": "USR-01"})

print("OrderWorker invalid input:")
workers[0].run({"bad": "data"})  # → None, error logged


# ─── Section 7: ABCMeta internals — what happens under the hood ───

print("\n" + "=" * 60)
print("SECTION 7: ABCMeta Internals")
print("=" * 60)


class Incomplete(ABC):
    @abstractmethod
    def must_implement(self) -> str: ...

    @abstractmethod
    def also_required(self) -> int: ...


# INTERVIEW: __abstractmethods__ frozenset — if non-empty, instantiation raises TypeError
print(f"Incomplete.__abstractmethods__: {Incomplete.__abstractmethods__}")


class PartialImpl(Incomplete):
    def must_implement(self) -> str:
        return "implemented"
    # also_required NOT implemented


print(f"PartialImpl.__abstractmethods__: {PartialImpl.__abstractmethods__}")


class FullImpl(Incomplete):
    def must_implement(self) -> str:
        return "implemented"

    def also_required(self) -> int:
        return 42


print(f"FullImpl.__abstractmethods__: {FullImpl.__abstractmethods__}")  # frozenset() empty
obj = FullImpl()
print(f"FullImpl() works: {obj.must_implement()}, {obj.also_required()}")

print("\n--- SUMMARY ---")
print("ABC            : use when you OWN the classes, want shared methods")
print("Protocol       : use for third-party classes or pure duck typing")
print("runtime_checkable: isinstance() works, but only checks presence not signature")
print("Template Method: ABC controls flow, subclasses fill in steps")
print("Generic Protocol: Repository[User] = type-safe generics without inheritance")
