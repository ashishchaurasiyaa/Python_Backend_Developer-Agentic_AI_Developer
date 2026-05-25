"""
mypy + ruff — Practical Examples
==================================

This file demonstrates:
  - Modern typing patterns mypy catches
  - Code that ruff would flag/fix
  - Production-grade typed Python

To run checks:
    ruff check 15_mypy_ruff_production.py
    ruff format --check 15_mypy_ruff_production.py
    mypy --strict 15_mypy_ruff_production.py
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from contextlib import contextmanager
from dataclasses import dataclass
from typing import (
    Annotated,
    Any,
    Generic,
    Literal,
    ParamSpec,
    Protocol,
    Self,
    TypedDict,
    TypeVar,
    cast,
    overload,
)


# ============================================================
# DEMO 1: Strict function typing
# ============================================================
def add(a: int, b: int) -> int:
    return a + b


def greet(name: str, *, formal: bool = False) -> str:
    return f"Hello, Mr. {name}" if formal else f"Hi {name}"


# ============================================================
# DEMO 2: Literal — restricted values
# ============================================================
LogLevel = Literal["DEBUG", "INFO", "WARN", "ERROR"]


def set_log_level(level: LogLevel) -> None:
    print(f"Setting log level: {level}")
    # set_log_level("verbose")   # mypy: error


# ============================================================
# DEMO 3: TypedDict — typed dictionaries
# ============================================================
class UserDict(TypedDict):
    id: int
    name: str
    email: str | None
    active: bool


class PartialUser(TypedDict, total=False):
    id: int
    name: str
    email: str


def format_user(u: UserDict) -> str:
    return f"{u['id']}: {u['name']}"


# ============================================================
# DEMO 4: Protocol — structural typing (duck typing with safety)
# ============================================================
class Saveable(Protocol):
    def save(self) -> None: ...


class JsonSerializable(Protocol):
    def to_json(self) -> dict[str, Any]: ...


def persist(obj: Saveable) -> None:
    obj.save()


@dataclass(slots=True)
class User:
    id: int
    name: str

    def save(self) -> None:
        print(f"Saving {self.name}")

    def to_json(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name}


# ============================================================
# DEMO 5: Generic Repository
# ============================================================
T = TypeVar("T")


class Repository(Generic[T]):
    def __init__(self) -> None:
        self._items: dict[int, T] = {}

    def add(self, id: int, item: T) -> None:
        self._items[id] = item

    def get(self, id: int) -> T | None:
        return self._items.get(id)

    def list_all(self) -> list[T]:
        return list(self._items.values())


# Usage with full type inference
user_repo: Repository[User] = Repository()
user_repo.add(1, User(1, "Ashish"))
fetched: User | None = user_repo.get(1)


# ============================================================
# DEMO 6: ParamSpec — typed decorators
# ============================================================
P = ParamSpec("P")
R = TypeVar("R")


def log_calls(func: Callable[P, R]) -> Callable[P, R]:
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        print(f"Calling {func.__name__}({args}, {kwargs})")
        result = func(*args, **kwargs)
        print(f"  -> {result}")
        return result

    return wrapper


@log_calls
def multiply(a: int, b: int) -> int:
    return a * b


# ============================================================
# DEMO 7: Self — return-self chain (builder pattern)
# ============================================================
class QueryBuilder:
    def __init__(self) -> None:
        self.filters: list[str] = []
        self.limit_val: int | None = None

    def where(self, condition: str) -> Self:
        self.filters.append(condition)
        return self

    def limit(self, n: int) -> Self:
        self.limit_val = n
        return self

    def build(self) -> str:
        q = "SELECT * FROM users"
        if self.filters:
            q += " WHERE " + " AND ".join(self.filters)
        if self.limit_val:
            q += f" LIMIT {self.limit_val}"
        return q


# ============================================================
# DEMO 8: overload — multiple type signatures
# ============================================================
@overload
def parse(value: str) -> str: ...
@overload
def parse(value: int) -> int: ...
@overload
def parse(value: list[Any]) -> list[Any]: ...
def parse(value: str | int | list[Any]) -> str | int | list[Any]:
    if isinstance(value, str):
        return value.strip()
    return value


# ============================================================
# DEMO 9: Annotated — metadata in types (FastAPI/Pydantic style)
# ============================================================
PositiveInt = Annotated[int, "must be > 0"]
Email = Annotated[str, "RFC 5322 email"]


def create_user(name: str, age: PositiveInt, email: Email) -> User:
    if age <= 0:
        raise ValueError("age must be positive")
    return User(id=age, name=name)


# ============================================================
# DEMO 10: Context manager with proper typing
# ============================================================
from typing import Iterator


@contextmanager
def db_transaction() -> Iterator[str]:
    """Type-safe context manager."""
    print("BEGIN")
    try:
        yield "session-id-123"
        print("COMMIT")
    except Exception:
        print("ROLLBACK")
        raise


def use_transaction() -> None:
    with db_transaction() as session:
        print(f"Working in {session}")


# ============================================================
# DEMO 11: cast — explicit type assertion
# ============================================================
def get_user_data() -> dict[str, Any]:
    return {"id": 1, "name": "Ashish"}


def process() -> None:
    raw = get_user_data()
    # mypy doesn't know shape — cast tells it
    user = cast(UserDict, raw)
    print(format_user(user))


# ============================================================
# DEMO 12: TYPE_CHECKING — avoid circular imports + heavy imports
# ============================================================
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Only imported during type check — not at runtime
    from collections.abc import Mapping


def process_mapping(data: "Mapping[str, int]") -> int:
    return sum(data.values())


# ============================================================
# DEMO 13: Examples of CODE RUFF WOULD FLAG (commented out)
# ============================================================
def ruff_violations_example() -> None:
    """Examples of code that ruff would flag.
    Uncomment to see ruff errors.
    """

    # B008: Mutable default argument
    # def bad(items: list = []) -> None: ...

    # F401: Unused import — would be flagged at module level

    # SIM118: key in dict.keys()
    # d = {"a": 1}
    # if "a" in d.keys():   # ruff: use `if "a" in d`
    #     pass

    # UP007: Use X | Y instead of Union
    # from typing import Union
    # def f(x: Union[int, str]) -> None: ...   # ruff: x: int | str

    # C401: Unnecessary generator (use set comprehension)
    # s = set(x for x in range(10))   # ruff: {x for x in range(10)}

    # E711: comparison to None
    # if x == None: pass   # ruff: x is None

    # PERF401: Manual list comprehension
    # result = []
    # for x in range(10):
    #     result.append(x * 2)   # ruff: use list comp

    pass


# ============================================================
# DEMO 14: Pydantic-style with mypy
# ============================================================
try:
    from pydantic import BaseModel, EmailStr, Field

    class UserModel(BaseModel):
        id: int
        name: str = Field(min_length=1)
        email: EmailStr
        age: int = Field(gt=0, lt=150)

        model_config = {"frozen": True, "extra": "forbid"}

except ImportError:
    pass


# ============================================================
# DEMO 15: Avoid Any — use specific types
# ============================================================
def process_payload_bad(data: Any) -> Any:  # ❌ mypy --strict warns
    return data["key"]


def process_payload_good(data: dict[str, str | int]) -> str | int:  # ✅
    return data["key"]


# ============================================================
# MAIN — demonstrate
# ============================================================
def main() -> None:
    print("=" * 60)
    print("mypy + ruff — Demonstration")
    print("=" * 60)

    print("\n1. Basic:", add(2, 3), greet("Ashish", formal=True))

    print("\n2. Literal:", end=" ")
    set_log_level("INFO")

    print("\n3. TypedDict:", format_user({"id": 1, "name": "A", "email": None, "active": True}))

    print("\n4. Protocol:")
    persist(User(1, "Ashish"))

    print("\n5. Generic repo:")
    user_repo.add(2, User(2, "Bob"))
    print(f"   {user_repo.list_all()}")

    print("\n6. Decorator with ParamSpec:")
    multiply(3, 4)

    print("\n7. Self-returning builder:")
    sql = (
        QueryBuilder()
        .where("active = true")
        .where("age > 18")
        .limit(10)
        .build()
    )
    print(f"   {sql}")

    print("\n8. Overload:", parse("  hello  "), parse(42))

    print("\n10. Context manager:")
    use_transaction()

    print("\n" + "=" * 60)
    print("Run quality checks:")
    print("  ruff check 15_mypy_ruff_production.py --fix")
    print("  ruff format 15_mypy_ruff_production.py")
    print("  mypy --strict 15_mypy_ruff_production.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
