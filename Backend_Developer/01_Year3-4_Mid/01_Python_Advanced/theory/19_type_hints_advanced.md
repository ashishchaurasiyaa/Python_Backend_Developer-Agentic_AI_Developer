# Type Hints Advanced — Protocol, TypedDict, Generics Deep

## Quick Concepts

**WHAT:**
- **Type hints** = Optional static types (PEP 484, 3.5+)
- **Protocol** = Structural subtyping (duck typing with types)
- **TypedDict** = Dict with fixed keys + types
- **Generics** = Parameterized types (List[T], Dict[K, V])
- **TypeVar** = Type variable for generics
- **ParamSpec** = Type variable for callable signatures
- **Literal** = Fixed value types
- **Final** = Immutable (don't reassign)
- **mypy** = Static type checker

**WHY type hints matter:**
- Catch bugs at design time (not runtime)
- IDE autocomplete + refactor
- Self-documenting code
- Required by Pydantic, FastAPI
- Senior Python = strong typing

**HOW typing module evolved:**
```
Python 3.5  → typing module introduced
Python 3.9  → Use built-ins (list[X] vs List[X])
Python 3.10 → X | Y syntax for Union
Python 3.11 → Self, NotRequired, TypeVarTuple
Python 3.12 → PEP 695 generic syntax
```

---

## Interview Questions & Answers

### Q1: Protocol vs ABC — kab kya?

**Answer:**

**WHAT:**
- **ABC (Abstract Base Class)** = Nominal typing (must inherit)
- **Protocol** = Structural typing (must implement methods, no inheritance)

**WHY both:**
- ABC: Force inheritance hierarchy
- Protocol: Duck typing with types

**HOW — ABC:**

```python
from abc import ABC, abstractmethod

class Drawable(ABC):
    @abstractmethod
    def draw(self) -> None:
        ...

class Circle(Drawable):  # ⭐ MUST inherit
    def draw(self) -> None:
        print("Drawing circle")

# class Square:  # ❌ Doesn't inherit → mypy/runtime error
#     def draw(self) -> None: ...
```

**HOW — Protocol:**

```python
from typing import Protocol

class Drawable(Protocol):
    def draw(self) -> None: ...

# ⭐ NO inheritance needed!
class Circle:
    def draw(self) -> None:
        print("Drawing circle")

class Square:
    def draw(self) -> None:
        print("Drawing square")

# Both are Drawable (structural matching)
def render(item: Drawable) -> None:
    item.draw()

render(Circle())   # ✅
render(Square())   # ✅ (no inheritance!)


# ⭐ Use case: third-party class adoption
import json
class CustomJSON:  # Can't inherit from JSONEncoder
    def encode(self) -> str:
        return json.dumps({"custom": True})

class JSONEncoder(Protocol):
    def encode(self) -> str: ...

# CustomJSON automatically satisfies JSONEncoder!
def serialize(obj: JSONEncoder) -> str:
    return obj.encode()
```

**HOW — Runtime check (@runtime_checkable):**

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class Drawable(Protocol):
    def draw(self) -> None: ...

class Circle:
    def draw(self) -> None: ...

# ⭐ isinstance check works at runtime
print(isinstance(Circle(), Drawable))  # True
print(isinstance("string", Drawable))  # False
```

**Decision matrix:**

| Use ABC when | Use Protocol when |
|---|---|
| Force hierarchy | Duck typing |
| Need shared base impl | Only interface needed |
| Class IS-A relationship | Class BEHAVES-AS |
| Library author | Library consumer |

---

### Q2: TypedDict — fixed-shape dicts?

**Answer:**

**WHAT:** Dict with specific keys + their types.

**WHY:**
- Type-safe dict (catches typos)
- Better than `dict[str, Any]`
- Works with JSON-like data
- Pydantic alternative for simple cases

**HOW — Basic TypedDict:**

```python
from typing import TypedDict

class User(TypedDict):
    id: int
    name: str
    email: str
    is_active: bool


# Use it
user: User = {
    "id": 1,
    "name": "Alice",
    "email": "alice@x.com",
    "is_active": True,
}

# mypy catches errors:
# user["id"] = "string"  # ❌ Error: int expected
# user["unknown_field"] = "x"  # ❌ Error: extra key
# user = {"id": 1}  # ❌ Error: missing keys
```

**HOW — Optional fields (3.11+):**

```python
from typing import TypedDict, NotRequired, Required

class UserCreate(TypedDict):
    name: Required[str]
    email: Required[str]
    age: NotRequired[int]  # ⭐ Optional
    bio: NotRequired[str]  # ⭐ Optional


# All valid
user1: UserCreate = {"name": "Alice", "email": "a@x.com"}
user2: UserCreate = {"name": "Bob", "email": "b@x.com", "age": 30}
```

**HOW — Inheritance:**

```python
class BaseUser(TypedDict):
    id: int
    email: str

class AdminUser(BaseUser):  # ⭐ Inherits
    admin_level: int
    permissions: list[str]


admin: AdminUser = {
    "id": 1,
    "email": "admin@x.com",
    "admin_level": 5,
    "permissions": ["all"],
}
```

**HOW — Total vs Partial (legacy):**

```python
# total=False makes ALL fields optional
class UserUpdate(TypedDict, total=False):
    name: str
    email: str
    age: int


# Now all optional
update: UserUpdate = {"name": "Alice"}  # ✅
update: UserUpdate = {}  # ✅
```

**HOW — TypedDict vs dataclass vs Pydantic:**

| Feature | TypedDict | dataclass | Pydantic |
|---|---|---|---|
| Static type check | ✅ | ✅ | ✅ |
| Runtime validation | ❌ | ❌ | ✅ |
| JSON parse | ✅ (just dict) | ❌ | ✅ |
| Methods | ❌ | ✅ | ✅ |
| Default values | ❌ (with total=False) | ✅ | ✅ |
| Use case | Stub for dict | Internal data | API + validation |

---

### Q3: Generic classes — TypeVar deep?

**Answer:**

**WHAT:** Classes/functions parameterized by type.

**WHY:**
- Reusable code (Stack[int], Stack[str])
- Type safety (Stack[int].push("str") = error)
- Container types

**HOW — Basic generic:**

```python
from typing import TypeVar, Generic

T = TypeVar("T")  # ⭐ Type variable

class Stack(Generic[T]):
    def __init__(self) -> None:
        self.items: list[T] = []

    def push(self, item: T) -> None:
        self.items.append(item)

    def pop(self) -> T:
        return self.items.pop()

    def peek(self) -> T:
        return self.items[-1]


# Type-safe usage
int_stack: Stack[int] = Stack()
int_stack.push(1)
int_stack.push(2)
# int_stack.push("string")  # ❌ mypy error

str_stack: Stack[str] = Stack()
str_stack.push("hello")
```

**HOW — Bounded TypeVar:**

```python
from typing import TypeVar
from numbers import Number

# ⭐ T must be Number subclass
NumberT = TypeVar("NumberT", bound=Number)

def double(x: NumberT) -> NumberT:
    return x + x

# Works
double(5)        # ✅ int
double(3.14)     # ✅ float

# Fails
# double("hello")  # ❌ str is not Number
```

**HOW — Constrained TypeVar (specific types):**

```python
# ⭐ T must be EXACTLY one of these
StrOrBytes = TypeVar("StrOrBytes", str, bytes)

def process(data: StrOrBytes) -> StrOrBytes:
    if isinstance(data, bytes):
        return data.upper()
    return data.upper()


process("hello")   # ✅ str
process(b"hello")  # ✅ bytes
# process([1, 2])   # ❌ Not str or bytes
```

**HOW — Multiple TypeVars:**

```python
K = TypeVar("K")
V = TypeVar("V")

class Cache(Generic[K, V]):
    def __init__(self) -> None:
        self._data: dict[K, V] = {}

    def set(self, key: K, value: V) -> None:
        self._data[key] = value

    def get(self, key: K) -> V | None:
        return self._data.get(key)


# Type-safe
user_cache: Cache[int, str] = Cache()
user_cache.set(1, "Alice")
# user_cache.set("str", 1)  # ❌ Wrong types
```

**HOW — Covariance + Contravariance:**

```python
from typing import TypeVar, Generic

# Default: invariant
T = TypeVar("T")

# Covariant: List[Dog] is List[Animal] if Dog is Animal
T_co = TypeVar("T_co", covariant=True)

# Contravariant: Callable that takes Animal is Callable that takes Dog
T_contra = TypeVar("T_contra", contravariant=True)


class Producer(Generic[T_co]):  # Covariant
    def get(self) -> T_co: ...


class Consumer(Generic[T_contra]):  # Contravariant
    def put(self, item: T_contra) -> None: ...
```

---

### Q4: ParamSpec — decorator types?

**Answer:**

**WHAT:** Type variable for callable signatures (3.10+).

**WHY:**
- Type-preserving decorators
- Higher-order functions
- Before: lost type info

**HOW — Type-preserving decorator:**

```python
from typing import ParamSpec, TypeVar, Callable
from functools import wraps

P = ParamSpec("P")  # ⭐ Captures callable params
R = TypeVar("R")

def log_call(func: Callable[P, R]) -> Callable[P, R]:
    """Decorator that preserves function signature."""
    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        print(f"Calling {func.__name__}")
        result = func(*args, **kwargs)
        print(f"Returned: {result}")
        return result
    return wrapper


@log_call
def add(x: int, y: int) -> int:
    return x + y


# ⭐ Type-safe — mypy knows signature is preserved
result: int = add(1, 2)  # ✅
# add("a", "b")  # ❌ mypy error
# add(1)  # ❌ missing argument
```

**HOW — Compare with old approach:**

```python
# OLD (no ParamSpec — loses types)
def log_call_old(func):
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper


@log_call_old
def add(x: int, y: int) -> int:
    return x + y

# mypy treats `add` as Callable[..., Any] — loses types!
result = add("wrong", "types")  # ⚠️ No error caught


# NEW (with ParamSpec — preserves types)
@log_call  # Uses ParamSpec
def add2(x: int, y: int) -> int:
    return x + y

# result = add2("wrong", "types")  # ❌ Caught by mypy
```

**HOW — Concatenate (add params):**

```python
from typing import ParamSpec, TypeVar, Concatenate, Callable

P = ParamSpec("P")
R = TypeVar("R")

# ⭐ Wrapper adds "request" as first param
def with_request(
    handler: Callable[Concatenate[Request, P], R]
) -> Callable[P, R]:
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        request = get_current_request()
        return handler(request, *args, **kwargs)
    return wrapper


@with_request
def get_user(request: Request, user_id: int) -> User:
    ...

# Caller doesn't need to pass request
user = get_user(user_id=123)  # ✅
```

---

### Q5: Literal + Final + ClassVar — special types?

**Answer:**

**Literal — Fixed values:**

```python
from typing import Literal

# ⭐ Only specific string values
def set_mode(mode: Literal["read", "write", "append"]) -> None:
    ...

set_mode("read")    # ✅
set_mode("write")   # ✅
# set_mode("rwx")   # ❌ mypy error


# Numeric literals
def http_status(code: Literal[200, 201, 204, 400, 404, 500]) -> str:
    ...


# Literal True/False
def set_verbose(verbose: Literal[True]) -> None:
    """Only accepts True (forced)."""
    ...
```

**Final — Immutable:**

```python
from typing import Final

# ⭐ Don't reassign
MAX_RETRIES: Final = 3
API_URL: Final[str] = "https://api.example.com"

# MAX_RETRIES = 5  # ❌ mypy error

class Config:
    DATABASE_URL: Final[str] = "postgresql://..."


# Final methods (don't override)
from typing import final

class Base:
    @final  # ⭐ Subclasses can't override
    def critical_method(self) -> None: ...


class Sub(Base):
    # def critical_method(self) -> None: ...  # ❌ mypy error
    pass
```

**ClassVar — class variable (not instance):**

```python
from typing import ClassVar
from dataclasses import dataclass

@dataclass
class Counter:
    name: str                       # Instance var
    count: int = 0                  # Instance var
    total_counters: ClassVar[int] = 0  # ⭐ Class var (shared)

    def __post_init__(self):
        Counter.total_counters += 1
```

---

### Q6: @overload — multiple signatures?

**Answer:**

**WHAT:** Define multiple type signatures for one function.

**WHY:**
- Different return types based on inputs
- Common in stdlib (e.g., max())
- Better than `Union[X, Y]` return

**HOW:**

```python
from typing import overload

# ⭐ Stubs (no implementation)
@overload
def process(x: int) -> int: ...
@overload
def process(x: str) -> str: ...
@overload
def process(x: list) -> list: ...

# ⭐ Actual implementation (no @overload)
def process(x):
    if isinstance(x, int):
        return x * 2
    elif isinstance(x, str):
        return x.upper()
    elif isinstance(x, list):
        return [i * 2 for i in x]


# Type-safe usage
result1: int = process(5)        # ✅ mypy knows: int
result2: str = process("hello")  # ✅ mypy knows: str
result3: list = process([1, 2])  # ✅ mypy knows: list
```

**HOW — Real example (parse JSON):**

```python
from typing import overload, Literal, Any

@overload
def parse_json(data: str, raw: Literal[True]) -> str: ...
@overload
def parse_json(data: str, raw: Literal[False] = False) -> dict: ...

def parse_json(data: str, raw: bool = False) -> Any:
    if raw:
        return data
    return json.loads(data)


# Type checker knows return type based on `raw`
data: dict = parse_json('{"x": 1}')
data: dict = parse_json('{"x": 1}', raw=False)
raw_data: str = parse_json('{"x": 1}', raw=True)
```

---

### Q7: TypeGuard + TypeIs — narrow types?

**Answer:**

**WHAT:** Custom functions that narrow types for mypy.

**WHY:**
- isinstance/issubclass aren't always enough
- Custom validation logic
- Type narrowing in if branches

**HOW — TypeGuard (3.10+):**

```python
from typing import TypeGuard

def is_string_list(items: list[object]) -> TypeGuard[list[str]]:
    """Custom type guard."""
    return all(isinstance(item, str) for item in items)


def process(items: list[object]) -> None:
    if is_string_list(items):
        # ⭐ mypy knows items is list[str] here
        for item in items:
            print(item.upper())  # ✅ No error
```

**HOW — TypeIs (3.13+, better):**

```python
from typing import TypeIs

def is_string_list(items: list[object]) -> TypeIs[list[str]]:
    return all(isinstance(item, str) for item in items)


def process(items: list[object]) -> None:
    if is_string_list(items):
        # mypy narrows to list[str]
        for item in items:
            print(item.upper())
    else:
        # ⭐ TypeIs (not TypeGuard) narrows in else too
        # items is NOT list[str] here
        print("Not a string list")
```

---

### Q8: Self type (3.11+) — fluent APIs?

**Answer:**

**WHAT:** Type representing "the class itself" (no need for TypeVar).

**WHY:**
- Builder patterns
- Fluent APIs
- Method chaining

**HOW — Before Self:**

```python
from typing import TypeVar

# ❌ OLD WAY
T = TypeVar("T", bound="QueryBuilder")

class QueryBuilder:
    def filter(self: T, **kwargs) -> T:
        return self
    def order_by(self: T, field: str) -> T:
        return self


class SQLQueryBuilder(QueryBuilder):
    def limit(self, n: int) -> "SQLQueryBuilder":
        return self


# Chain works
sql = SQLQueryBuilder().filter(age=25).order_by("name").limit(10)
```

**HOW — With Self (3.11+):**

```python
from typing import Self

# ✅ NEW WAY
class QueryBuilder:
    def filter(self, **kwargs) -> Self:  # ⭐ Self refers to actual class
        return self

    def order_by(self, field: str) -> Self:
        return self


class SQLQueryBuilder(QueryBuilder):
    def limit(self, n: int) -> Self:
        return self


# Chain works — and subclass Self correctly inferred
sql: SQLQueryBuilder = SQLQueryBuilder().filter(age=25).order_by("name").limit(10)
```

---

### Q9: Built-in vs typing module (3.9+)?

**Answer:**

**WHAT:** Use built-in types instead of typing.* (PEP 585).

**WHY:**
- Cleaner syntax
- No imports needed
- Future-proof (typing.X are deprecated)

**HOW — Comparison:**

```python
# ❌ OLD WAY (still works but verbose)
from typing import List, Dict, Tuple, Set, FrozenSet, Type, Optional, Union

def func(
    items: List[int],
    mapping: Dict[str, int],
    pair: Tuple[int, str],
    unique: Set[int],
    frozen: FrozenSet[str],
    cls: Type[int],
    maybe: Optional[str],
    either: Union[int, str],
) -> List[Dict[str, int]]:
    ...


# ✅ NEW WAY (Python 3.9+)
def func(
    items: list[int],          # ⭐ list not List
    mapping: dict[str, int],   # ⭐ dict not Dict
    pair: tuple[int, str],     # ⭐ tuple not Tuple
    unique: set[int],
    frozen: frozenset[str],
    cls: type[int],
    maybe: str | None,         # ⭐ X | None (3.10+)
    either: int | str,         # ⭐ X | Y (3.10+)
) -> list[dict[str, int]]:
    ...
```

**Built-in support since:**
- Python 3.9: list, dict, tuple, set, type
- Python 3.10: `X | Y` syntax (PEP 604)

---

### Q10: Runtime type validation — typeguard, pydantic?

**Answer:**

**WHAT:** Type hints are STATIC by default — not enforced at runtime.

**HOW — Runtime validation:**

**Option 1: typeguard (decorator)**

```python
# pip install typeguard

from typeguard import typechecked

@typechecked  # ⭐ Validates at runtime
def add(x: int, y: int) -> int:
    return x + y

add(1, 2)        # ✅
# add("a", "b")  # ⚠️ Raises TypeCheckError at runtime
```

**Option 2: Pydantic (more powerful)**

```python
from pydantic import BaseModel, validate_call

# Class validation
class User(BaseModel):
    id: int
    name: str
    email: str

user = User(id=1, name="Alice", email="a@x.com")
# User(id="not-int")  # ⚠️ ValidationError


# Function validation
@validate_call
def add(x: int, y: int) -> int:
    return x + y

add(1, 2)              # ✅
# add("string", 2)    # ⚠️ ValidationError
add("5", 2)            # ✅ "5" → 5 (auto coerce)
```

**Option 3: beartype (fast runtime check)**

```python
# pip install beartype

from beartype import beartype

@beartype
def process(items: list[int]) -> int:
    return sum(items)


process([1, 2, 3])           # ✅
# process(["a", "b"])        # ⚠️ Raises at runtime
```

---

### Q11: Mypy configuration — production setup?

**Answer:**

**HOW — pyproject.toml:**

```toml
# pyproject.toml
[tool.mypy]
python_version = "3.12"

# Strictness (start permissive, tighten over time)
strict = true                          # ⭐ Enable all strict checks
disallow_untyped_defs = true           # All functions need types
disallow_incomplete_defs = true
check_untyped_defs = true
disallow_untyped_decorators = true
no_implicit_optional = true            # Optional must be explicit
warn_redundant_casts = true
warn_unused_ignores = true
warn_return_any = true
warn_unreachable = true

# Errors as warnings during migration
# strict = false
# warn_return_any = true
# warn_unused_ignores = true

# Per-module overrides
[[tool.mypy.overrides]]
module = "third_party_lib.*"
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = "legacy.code.*"
ignore_errors = true    # Temporarily skip
```

**HOW — Run mypy:**

```bash
mypy app/                   # Check entire dir
mypy --strict app/          # Override config
mypy --no-incremental app/  # No cache
mypy app/main.py            # Single file
```

**HOW — Pre-commit hook:**

```yaml
# .pre-commit-config.yaml
- repo: https://github.com/pre-commit/mirrors-mypy
  rev: v1.7.0
  hooks:
    - id: mypy
      additional_dependencies: [types-requests, types-redis]
```

---

### Q12: Type stubs (.pyi files) — what + why?

**Answer:**

**WHAT:** Type-only files for libraries without types.

**WHY:**
- 3rd party lib has no types
- Stub files only contain signatures
- mypy reads them

**HOW:**

```python
# legacy_lib/__init__.py (no types)
def fetch_data(url):
    return requests.get(url).json()


# legacy_lib/__init__.pyi (stub)
import requests

def fetch_data(url: str) -> dict: ...
```

**HOW — Use types-* packages:**

```bash
# Install pre-made stubs
pip install types-requests        # For requests library
pip install types-redis           # For redis-py
pip install types-PyYAML          # For PyYAML
pip install types-python-dateutil
```

**HOW — Create stubs for own lib:**

```bash
# Auto-generate stubs
pip install mypy
stubgen -p mymodule -o stubs/

# Result: stubs/mymodule/__init__.pyi
```

---

## Type Hints Checklist

```markdown
### Coverage
- [ ] All functions have parameter types
- [ ] All functions have return types
- [ ] Class attributes annotated
- [ ] Type variables for generics
- [ ] Protocol for duck typing

### Quality
- [ ] Use built-ins (list not List)
- [ ] Use `X | Y` (not Union[X, Y])
- [ ] Use `X | None` (not Optional[X])
- [ ] Self type for fluent APIs
- [ ] Literal for fixed values
- [ ] Final for constants

### Strictness
- [ ] mypy --strict passes
- [ ] No `Any` types (where avoidable)
- [ ] No `# type: ignore` (without comment)
- [ ] CI fails on mypy errors

### Runtime
- [ ] Pydantic for API validation
- [ ] typeguard for critical paths
- [ ] No Pydantic v1 (use v2)

### Documentation
- [ ] Docstrings for public APIs
- [ ] Type stubs for distributed packages
- [ ] py.typed marker for typed packages
```

---

## Common Patterns

```python
# 1. Generic function
def first[T](items: list[T]) -> T:  # Python 3.12+
    return items[0]


# 2. Protocol for duck typing
class Stringable(Protocol):
    def __str__(self) -> str: ...

def show(x: Stringable) -> None:
    print(str(x))


# 3. Type guard
def is_admin(user: User) -> TypeGuard[AdminUser]:
    return user.role == "admin"


# 4. Discriminated union
class CreateEvent(BaseModel):
    type: Literal["create"]
    data: dict

class UpdateEvent(BaseModel):
    type: Literal["update"]
    id: int
    data: dict

Event = CreateEvent | UpdateEvent

def handle(event: Event) -> None:
    if event.type == "create":
        # mypy knows: CreateEvent
        print(event.data)
    elif event.type == "update":
        # mypy knows: UpdateEvent
        print(event.id)


# 5. Decorator with ParamSpec
P = ParamSpec("P")
R = TypeVar("R")

def cache[P, R](func: Callable[P, R]) -> Callable[P, R]:
    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        return func(*args, **kwargs)
    return wrapper
```
