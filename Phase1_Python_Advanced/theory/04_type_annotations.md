# Type Annotations — Complete Guide

---

# PART 1 — THEORY (Deep Concepts)

## 1.1 Type Annotations Kya Hain?

Python dynamically typed language hai — types runtime pe decide hote hain.  
Type annotations = **hints** for type checkers (mypy, pyright) — runtime pe kuch nahi hota.

```python
# Without annotations — koi guarantee nahi
def add(a, b):
    return a + b

add("hello", 5)   # Runtime error: can't concatenate str and int

# With annotations — type checker pakad lega
def add(a: int, b: int) -> int:
    return a + b

add("hello", 5)   # mypy: error: Argument 1 to "add" has incompatible type "str"; expected "int"
```

**Key point:** Annotations runtime pe enforce nahi hote — sirf type checkers use karte hain.  
`__annotations__` dict mein store hoti hain, `get_type_hints()` se read kar sakte hain.

---

## 1.2 TypeVar — Generic Type Placeholder

**TypeVar** = ek type variable jo "koi bhi type" represent karta hai — lekin consistent.

```
T = TypeVar("T")

def identity(x: T) -> T:    # jo bhi type aaye, wahi return karein
    return x

identity(42)       → return type: int
identity("hello")  → return type: str
identity([1,2,3])  → return type: list[int]
```

**Bound TypeVar** — type ko ek base class tak restrict karo:
```
T = TypeVar("T", bound=Comparable)
# Sirf Comparable subclasses allowed
```

**Constrained TypeVar** — sirf specific types:
```
AnyStr = TypeVar("AnyStr", str, bytes)
# Sirf str ya bytes — koi aur nahi
```

---

## 1.3 Generic Classes — `Generic[T]`

```
Generic[T] = ek class jo type parameter accept kare

Stack[int]    → stack mein sirf ints
Stack[str]    → stack mein sirf strings

Type checker Stack[int].push("hello") reject kar dega.
```

**Covariance vs Contravariance:**
```
Covariant (T_co):     Stack[Dog] Stack[Animal] ki jagah use ho sakti hai
                      — "readable containers" — Producer
Contravariant (T_contra): Processor[Animal] Processor[Dog] ki jagah
                      — "writable containers" — Consumer
Invariant (default T): sirf exact type — Stack[Dog] ≠ Stack[Animal]
```

---

## 1.4 Special Types — Kab Kya Use Karein

| Type | Meaning | Use Case |
|------|---------|----------|
| `Any` | Koi bhi type — no checking | Legacy code, truly dynamic |
| `Optional[T]` | `T \| None` | Value jo None ho sakti hai |
| `Union[A, B]` | A ya B — `A \| B` (3.10+) | Multiple types |
| `Literal["a", "b"]` | Sirf yeh specific values | Enum-like restrictions |
| `Final` | Reassign nahi ho sakta | Constants |
| `ClassVar[T]` | Class variable (not instance) | Class-level attributes |
| `TypedDict` | Dict with specific keys+types | JSON-like structures |
| `Protocol` | Structural subtyping | Duck typing + type safety |
| `Annotated[T, ...]` | Type + metadata | Pydantic validators, docs |

---

## 1.5 `Literal` — Specific Value Restriction

```
status: Literal["active", "inactive", "pending"]

→ "active"   ✅ allowed
→ "deleted"  ❌ type error
→ "ACTIVE"   ❌ type error (case sensitive)
```

**Use case:** Function parameters jo sirf kuch specific strings accept karein.

---

## 1.6 `TypedDict` — Typed Dictionaries

Normal dict: `dict[str, Any]` — koi guarantee nahi.  
TypedDict: specific keys + specific types — type checked.

```python
class UserData(TypedDict):
    id: int
    name: str
    email: str

# Type checker ensures correct keys and types
user: UserData = {"id": 1, "name": "Ashish", "email": "a@b.com"}  # ✅
user: UserData = {"id": "1", "name": "Ashish"}   # ❌ wrong id type, missing email
```

---

## 1.7 `Overload` — Multiple Signatures

```
def process(data: str) -> str: ...
def process(data: int) -> int: ...
def process(data: list) -> list: ...

# Runtime: sirf ek implementation
# Type checker: correct return type based on input
```

`@overload` = multiple type signatures declare karo — actual implementation `@overload` ke bina.

---

## 1.8 `ParamSpec` aur `Concatenate` — Advanced

```
TypeVar: return type ya parameter type generic banata hai
ParamSpec: entire parameter list generic banata hai

Use case: decorator likhna jo original function ka type preserve kare
```

---

## 1.9 `TYPE_CHECKING` — Circular Import Avoid

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mymodule import SomeClass   # runtime pe import NAHI hota
    # Sirf type checker ke liye

def func(x: "SomeClass") -> None: ...   # string annotation
```

---

# PART 2 — PRACTICAL (Working Code)

## 2.1 TypeVar — Generic Functions

```python
from typing import TypeVar, Sequence
from collections.abc import Callable

T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")

# --- Basic TypeVar ---
def first(items: list[T]) -> T | None:
    """Return first item, type-safe."""
    return items[0] if items else None

result1 = first([1, 2, 3])        # int | None
result2 = first(["a", "b"])       # str | None
result3 = first([{"k": "v"}])     # dict[str, str] | None

# --- Bound TypeVar ---
from typing import TypeVar

class Comparable:
    def __lt__(self, other) -> bool: ...
    def __gt__(self, other) -> bool: ...

Comp = TypeVar("Comp", bound="Comparable")

def max_item(items: list[Comp]) -> Comp:
    """Return max item — only works with comparable types."""
    return max(items)

# --- Constrained TypeVar ---
AnyStr = TypeVar("AnyStr", str, bytes)

def to_upper(s: AnyStr) -> AnyStr:
    """Works for str and bytes, nothing else."""
    if isinstance(s, bytes):
        return s.upper()   # type: ignore
    return s.upper()

result_str   = to_upper("hello")   # str
result_bytes = to_upper(b"hello")  # bytes

# --- Multiple TypeVars ---
def zip_with(func: Callable[[T, V], K],
             items1: list[T],
             items2: list[V]) -> list[K]:
    """Apply func to pairs, return results."""
    return [func(a, b) for a, b in zip(items1, items2)]

results = zip_with(lambda x, y: x + y, [1, 2, 3], [4, 5, 6])
# results: list[int] = [5, 7, 9]
```

---

## 2.2 Generic Classes

```python
from typing import TypeVar, Generic, Iterator
from dataclasses import dataclass, field

T = TypeVar("T")

# --- Generic Stack ---
class Stack(Generic[T]):
    def __init__(self) -> None:
        self._items: list[T] = []

    def push(self, item: T) -> None:
        self._items.append(item)

    def pop(self) -> T:
        if not self._items:
            raise IndexError("Stack is empty")
        return self._items.pop()

    def peek(self) -> T | None:
        return self._items[-1] if self._items else None

    def is_empty(self) -> bool:
        return not self._items

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[T]:
        yield from reversed(self._items)


# Type-safe usage
int_stack: Stack[int] = Stack()
int_stack.push(1)
int_stack.push(2)
int_stack.push(3)

value: int = int_stack.pop()   # type checker knows this is int
print(value)   # 3

str_stack: Stack[str] = Stack()
str_stack.push("hello")
str_stack.push("world")


# --- Generic Result Type (like Rust's Result) ---
from typing import Generic

T = TypeVar("T")
E = TypeVar("E", bound=Exception)

@dataclass
class Result(Generic[T, E]):
    """Type-safe result — either value or error."""
    _value: T | None = None
    _error: E | None = None

    @classmethod
    def ok(cls, value: T) -> "Result[T, E]":
        return cls(_value=value)

    @classmethod
    def err(cls, error: E) -> "Result[T, E]":
        return cls(_error=error)

    @property
    def is_ok(self) -> bool:
        return self._error is None

    def unwrap(self) -> T:
        if self._error is not None:
            raise self._error
        return self._value  # type: ignore

    def unwrap_or(self, default: T) -> T:
        return self._value if self.is_ok else default


# Usage
def divide(a: float, b: float) -> Result[float, ZeroDivisionError]:
    if b == 0:
        return Result.err(ZeroDivisionError("Cannot divide by zero"))
    return Result.ok(a / b)

r1 = divide(10, 2)
print(r1.unwrap())         # 5.0

r2 = divide(10, 0)
print(r2.unwrap_or(-1.0))  # -1.0
```

---

## 2.3 Literal, Final, ClassVar

```python
from typing import Literal, Final, ClassVar, get_args, get_origin

# --- Literal — exact value constraint ---
Status = Literal["pending", "processing", "completed", "failed"]
HttpMethod = Literal["GET", "POST", "PUT", "DELETE", "PATCH"]

def update_order(order_id: str, status: Status) -> dict:
    # Type checker ensures only valid statuses
    return {"order_id": order_id, "status": status}

update_order("ORD-001", "completed")   # ✅
# update_order("ORD-001", "unknown")  # ❌ type error

# Literal in function overloads
Direction = Literal["asc", "desc"]

def sort_users(by: str, direction: Direction = "asc") -> list:
    return []   # implementation

# --- Final — cannot be reassigned ---
MAX_RETRIES: Final = 3
API_VERSION: Final[str] = "v2"
DB_PORT: Final = 5432

# MAX_RETRIES = 5   # ❌ mypy: Cannot assign to final name "MAX_RETRIES"

# Final in class
class Config:
    MAX_CONNECTIONS: Final = 100    # class constant

    def __init__(self):
        self.name: Final = "config"   # instance constant

# --- ClassVar — class variable, not instance ---
class Counter:
    # ClassVar — belongs to class, not instances
    _count: ClassVar[int] = 0
    _instances: ClassVar[list["Counter"]] = []

    def __init__(self, name: str):
        self.name = name             # instance variable
        Counter._count += 1
        Counter._instances.append(self)

    @classmethod
    def total(cls) -> int:
        return cls._count

c1 = Counter("a")
c2 = Counter("b")
print(Counter.total())   # 2
```

---

## 2.4 TypedDict — Structured Dictionaries

```python
from typing import TypedDict, Required, NotRequired

# Basic TypedDict
class UserData(TypedDict):
    id: int
    name: str
    email: str

# TypedDict with optional fields (Python 3.11+)
class UserDataFull(TypedDict, total=False):
    """total=False: all fields optional"""
    id: int
    name: str
    email: str
    phone: str

# Mix required + optional (Python 3.11+)
class ApiResponse(TypedDict):
    status: int            # required
    data: dict             # required
    error: NotRequired[str]  # optional
    meta: NotRequired[dict]  # optional

# Usage
def process_user(user: UserData) -> str:
    return f"User {user['id']}: {user['name']}"

user: UserData = {"id": 1, "name": "Ashish", "email": "a@b.com"}
print(process_user(user))

# TypedDict inheritance
class AdminData(UserData):
    role: str
    permissions: list[str]

admin: AdminData = {
    "id": 1, "name": "Ashish", "email": "a@b.com",
    "role": "admin", "permissions": ["read", "write"]
}

# Real-world: API response typing
class PaginatedResponse(TypedDict):
    items: list[dict]
    total: int
    page: int
    per_page: int
    has_next: bool

def get_users(page: int) -> PaginatedResponse:
    return {
        "items": [{"id": 1, "name": "Ashish"}],
        "total": 100,
        "page": page,
        "per_page": 20,
        "has_next": True
    }
```

---

## 2.5 `@overload` — Multiple Signatures

```python
from typing import overload, Union

# --- Basic overload ---
@overload
def process(data: str) -> str: ...
@overload
def process(data: int) -> int: ...
@overload
def process(data: list) -> list: ...

def process(data):   # actual implementation — no type hints here
    if isinstance(data, str):
        return data.upper()
    elif isinstance(data, int):
        return data * 2
    elif isinstance(data, list):
        return sorted(data)
    raise TypeError(f"Unsupported type: {type(data)}")

# Type checker knows:
result1: str  = process("hello")   # str in → str out
result2: int  = process(42)        # int in → int out
result3: list = process([3, 1, 2]) # list in → list out

# --- Real-world: open() like overload ---
@overload
def read_file(path: str, binary: Literal[False]) -> str: ...
@overload
def read_file(path: str, binary: Literal[True]) -> bytes: ...
@overload
def read_file(path: str) -> str: ...

def read_file(path: str, binary: bool = False) -> str | bytes:
    mode = "rb" if binary else "r"
    with open(path, mode) as f:
        return f.read()

text: str   = read_file("file.txt")            # str
data: bytes = read_file("file.bin", binary=True)  # bytes
```

---

## 2.6 `ParamSpec` — Decorator Type Safety

```python
from typing import TypeVar, Callable
from typing import ParamSpec
import functools
import time

T = TypeVar("T")
P = ParamSpec("P")

# --- Type-safe decorator using ParamSpec ---
def timer(func: Callable[P, T]) -> Callable[P, T]:
    """Decorator jo function ka execution time measure kare.
    ParamSpec ensure karta hai original function ke params preserve hoin."""

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        print(f"{func.__name__} took {elapsed:.4f}s")
        return result

    return wrapper


def retry(times: int) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Retry decorator with type safety."""

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            for attempt in range(times):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == times - 1:
                        raise
                    print(f"Retry {attempt + 1}/{times}: {e}")
            raise RuntimeError("Should not reach here")
        return wrapper

    return decorator


@timer
@retry(times=3)
def fetch_data(url: str, timeout: int = 30) -> dict:
    # Type checker knows: fetch_data(url: str, timeout: int = 30) -> dict
    return {"data": "result"}


result = fetch_data("https://api.example.com", timeout=10)
# fetch_data took 0.0001s
```

---

## 2.7 `Annotated` — Type + Metadata

```python
from typing import Annotated, get_type_hints, get_args
from dataclasses import dataclass

# Annotated[type, metadata1, metadata2, ...]
# Type checker: sirf type consider karta hai
# Runtime: metadata available for libraries (Pydantic, FastAPI)

# Custom metadata classes
class Gt:
    def __init__(self, value): self.value = value

class MaxLen:
    def __init__(self, value): self.value = value

class Description:
    def __init__(self, text): self.text = text

# Type aliases with constraints
PositiveInt = Annotated[int, Gt(0), Description("Must be positive")]
ShortStr    = Annotated[str, MaxLen(100)]
UserAge     = Annotated[int, Gt(0), Gt(0)]

@dataclass
class Product:
    id: PositiveInt
    name: ShortStr
    price: Annotated[float, Gt(0), Description("Price in INR")]
    quantity: Annotated[int, Gt(-1)]

# Reading annotations at runtime
hints = get_type_hints(Product, include_extras=True)
for field_name, hint in hints.items():
    args = get_args(hint)
    print(f"{field_name}: {args}")

# FastAPI uses Annotated for query params:
# def endpoint(page: Annotated[int, Query(ge=1, le=100)] = 1): ...
# Pydantic uses for validators:
# name: Annotated[str, Field(min_length=1, max_length=100)]
```

---

## 2.8 `TYPE_CHECKING` — Circular Import Fix

```python
# models.py
from __future__ import annotations   # PEP 563 — all annotations as strings
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Only imported during type checking, NOT at runtime
    # Breaks circular import at runtime
    from services import UserService
    from repositories import UserRepository

class User:
    def __init__(self, id: int, name: str):
        self.id = id
        self.name = name

    # String annotation — works even without runtime import
    def get_service(self) -> "UserService":
        from services import UserService   # runtime import
        return UserService(self)

    def get_repo(self) -> "UserRepository":
        from repositories import UserRepository
        return UserRepository()
```

---

## 2.9 Interview Q&A

**Q1: TypeVar aur Generic kab use karein?**
> TypeVar: jab function ka return type input type pe depend kare — `first(list[T]) -> T`. Generic[T]: jab class type parameter accept kare — `Stack[int]`, `Repository[User]`. Benefit: type checker input se output infer kar sakta hai. Without TypeVar, `first([1,2,3])` ka return type `Any` hoga — type safety lost.

**Q2: `Literal` aur `Enum` mein kya fark hai?**
> `Literal["a","b","c"]`: sirf values restrict karo, ek naya type nahi. Light-weight, dict keys, function params ke liye. `Enum`: full class with values + methods + iteration. Use Literal jab sirf type checking chahiye. Use Enum jab behavior + values dono chahiye (e.g., `Status.PENDING.value`, `Status.__members__`).

**Q3: `TypedDict` vs `dataclass` vs `Pydantic` — kab kya?**
> TypedDict: plain dict jo type-checked ho — JSON serialization easy, runtime validation nahi. Dataclass: typed attributes, default values, methods — pure Python, no validation. Pydantic BaseModel: runtime validation + serialization + settings — most powerful but heaviest. API boundaries pe Pydantic, internal data structures pe dataclass, JSON-like dicts pe TypedDict.

**Q4: `@overload` kaise kaam karta hai runtime pe?**
> `@overload` decorated functions register hoti hain lekin directly call nahi hoti — type checker ke liye hain. Actual implementation `@overload` ke bina last mein hoti hai — wahi runtime pe call hoti hai. `typing.get_overloads(func)` se overloaded signatures dekh sakte hain (Python 3.11+).

**Q5: `ParamSpec` TypeVar se kaise different hai?**
> TypeVar: single return type ya parameter type generic banata hai. ParamSpec: entire `*args, **kwargs` parameter specification capture karta hai. Decorator likhte waqt zaroori hai — bina ParamSpec ke, wrapper function ka type original se different ho jata hai (args: Any, kwargs: Any). ParamSpec ensure karta hai decorated function ki signature exactly preserve hoe.
