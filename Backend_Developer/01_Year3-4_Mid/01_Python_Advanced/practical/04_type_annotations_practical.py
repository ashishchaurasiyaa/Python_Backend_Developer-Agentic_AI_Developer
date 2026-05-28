"""
Type Annotations — Practical Runnable Examples
===============================================
Topics covered:
  - TypeVar (basic, bound, constrained)
  - Generic classes (Generic[T])
  - Protocol with TypeVar
  - Union, Optional, Literal, Final, ClassVar
  - TypedDict (basic, total=False, NotRequired, inheritance)
  - @overload decorator — multiple signatures
  - ParamSpec — type-safe decorators that preserve signatures
  - Annotated — type + metadata
  - TYPE_CHECKING — circular import prevention
  - Runtime type checking with get_type_hints + get_args
  - Callable types

How to run:
  python 04_type_annotations_practical.py

pip install:
  (none — standard library only)
"""

from __future__ import annotations   # PEP 563: all annotations as strings (lazy eval)

from typing import (
    TypeVar,
    Generic,
    Protocol,
    runtime_checkable,
    Union,
    Optional,
    Literal,
    Final,
    ClassVar,
    TypedDict,
    overload,
    Annotated,
    Callable,
    Iterator,
    NotRequired,
    TYPE_CHECKING,
    get_type_hints,
    get_args,
    get_origin,
)
from typing import ParamSpec
from dataclasses import dataclass, field
import functools
import time

if TYPE_CHECKING:
    # INTERVIEW: TYPE_CHECKING block — import only during static analysis, NOT at runtime
    # Breaks circular imports: module A needs B for type hints, B needs A at runtime
    pass   # placeholder — real usage shown in Section 8


# ─── Section 1: TypeVar — Generic Functions ───

print("=" * 60)
print("SECTION 1: TypeVar — Generic Functions")
print("=" * 60)

# INTERVIEW: TypeVar = type placeholder that stays consistent through a call
# Without TypeVar: first([1,2,3]) returns Any — type safety lost
T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")


def first(items: list[T]) -> T | None:
    """Return first element with type preserved. list[int] → int | None."""
    return items[0] if items else None


result_int = first([1, 2, 3])       # inferred: int | None
result_str = first(["a", "b"])      # inferred: str | None
result_none = first([])             # inferred: None

print(f"first([1,2,3]) = {result_int}")
print(f"first(['a','b']) = {result_str}")
print(f"first([]) = {result_none}")


def zip_with(
    func: Callable[[T, V], K],
    items1: list[T],
    items2: list[V],
) -> list[K]:
    """Apply func to pairs — multiple TypeVars for input/output independence."""
    return [func(a, b) for a, b in zip(items1, items2)]


sums = zip_with(lambda x, y: x + y, [1, 2, 3], [10, 20, 30])
print(f"\nzip_with add: {sums}")   # [11, 22, 33]

concat = zip_with(lambda s, n: f"{s}{n}", ["a", "b"], [1, 2])
print(f"zip_with concat: {concat}")   # ["a1", "b2"]


# INTERVIEW: Bound TypeVar — restrict to a base class or protocol
class Comparable(Protocol):
    def __lt__(self, other: object) -> bool: ...


Comp = TypeVar("Comp", bound="Comparable")


def sorted_first(items: list[Comp]) -> Comp:
    """Return smallest item — only works for comparable types."""
    return sorted(items)[0]


print(f"\nsorted_first([3,1,2]) = {sorted_first([3, 1, 2])}")
print(f"sorted_first(['c','a','b']) = {sorted_first(['c', 'a', 'b'])}")


# INTERVIEW: Constrained TypeVar — only specific types allowed (not subtypes)
AnyStr = TypeVar("AnyStr", str, bytes)


def to_upper(s: AnyStr) -> AnyStr:
    """Works for str and bytes only — nothing else."""
    return s.upper()  # type: ignore[return-value]


print(f"\nto_upper('hello') = {to_upper('hello')}")
print(f"to_upper(b'hello') = {to_upper(b'hello')}")


# ─── Section 2: Generic Classes ───

print("\n" + "=" * 60)
print("SECTION 2: Generic Classes")
print("=" * 60)


class Stack(Generic[T]):
    """Type-safe stack — Stack[int] only accepts ints."""

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
        return not bool(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[T]:
        yield from reversed(self._items)

    def __repr__(self) -> str:
        return f"Stack({self._items!r})"


int_stack: Stack[int] = Stack()
int_stack.push(1)
int_stack.push(2)
int_stack.push(3)

value: int = int_stack.pop()   # type checker: knows this is int
print(f"Stack pop: {value}")

str_stack: Stack[str] = Stack()
str_stack.push("hello")
str_stack.push("world")
print(f"str Stack peek: {str_stack.peek()}")


# INTERVIEW: Result[T, E] — Rust-style Result type for explicit error handling
E = TypeVar("E", bound=Exception)


@dataclass
class Result(Generic[T, E]):
    """Either a value (ok) or an error — no exceptions needed."""
    _value: T | None = None
    _error: E | None = None

    @classmethod
    def ok(cls, value: T) -> Result[T, E]:
        return cls(_value=value)

    @classmethod
    def err(cls, error: E) -> Result[T, E]:
        return cls(_error=error)

    @property
    def is_ok(self) -> bool:
        return self._error is None

    def unwrap(self) -> T:
        if self._error is not None:
            raise self._error
        return self._value  # type: ignore[return-value]

    def unwrap_or(self, default: T) -> T:
        return self._value if self.is_ok else default  # type: ignore[return-value]

    def __repr__(self) -> str:
        return f"Ok({self._value!r})" if self.is_ok else f"Err({self._error!r})"


def divide(a: float, b: float) -> Result[float, ZeroDivisionError]:
    if b == 0:
        return Result.err(ZeroDivisionError("Cannot divide by zero"))
    return Result.ok(a / b)


r1 = divide(10, 2)
print(f"\ndivide(10, 2) = {r1}, unwrap = {r1.unwrap()}")

r2 = divide(10, 0)
print(f"divide(10, 0) = {r2}, unwrap_or(-1) = {r2.unwrap_or(-1.0)}")


# ─── Section 3: Literal, Final, ClassVar ───

print("\n" + "=" * 60)
print("SECTION 3: Literal, Final, ClassVar")
print("=" * 60)

# INTERVIEW: Literal restricts a parameter to exact values
# Lighter than Enum when you just need type-checking, not methods
Status = Literal["pending", "processing", "completed", "failed"]
HttpMethod = Literal["GET", "POST", "PUT", "DELETE", "PATCH"]
Direction = Literal["asc", "desc"]


def update_order(order_id: str, status: Status) -> dict:
    # mypy errors if you pass "unknown_status"
    return {"order_id": order_id, "status": status}


print(f"update_order: {update_order('ORD-001', 'completed')}")
# update_order("ORD-001", "unknown")  # ← mypy error: Argument 2 has incompatible type

# INTERVIEW: Final — variable cannot be reassigned after definition
MAX_RETRIES: Final = 3
API_VERSION: Final[str] = "v2"
# MAX_RETRIES = 5  # ← mypy error: Cannot assign to final name

print(f"MAX_RETRIES = {MAX_RETRIES}")
print(f"API_VERSION = {API_VERSION}")


# INTERVIEW: ClassVar — belongs to the class, not instances
# type checker ensures you don't write self._count = ... in __init__ for ClassVar
class UserRegistry:
    _count: ClassVar[int] = 0
    _all: ClassVar[list[UserRegistry]] = []

    def __init__(self, name: str) -> None:
        self.name = name    # instance variable
        UserRegistry._count += 1
        UserRegistry._all.append(self)

    @classmethod
    def total(cls) -> int:
        return cls._count

    @classmethod
    def all_names(cls) -> list[str]:
        return [u.name for u in cls._all]


u1 = UserRegistry("Ashish")
u2 = UserRegistry("Bob")
print(f"\nUserRegistry.total() = {UserRegistry.total()}")
print(f"UserRegistry.all_names() = {UserRegistry.all_names()}")


# ─── Section 4: TypedDict ───

print("\n" + "=" * 60)
print("SECTION 4: TypedDict")
print("=" * 60)


# INTERVIEW: TypedDict = typed dict, not a class. No runtime validation.
# Use when: JSON-like data, API responses, config dicts — where a full class is overkill
class UserData(TypedDict):
    id: int
    name: str
    email: str


# Mix required + optional fields
class UserDataExtended(TypedDict):
    id: int                      # required
    name: str                    # required
    email: NotRequired[str]      # INTERVIEW: NotRequired = optional key
    phone: NotRequired[str]      # optional


# Inheritance — AdminData has all UserData fields plus more
class AdminData(UserData):
    role: str
    permissions: list[str]


# Real-world: paginated API response
class PaginatedResponse(TypedDict):
    items: list[dict]
    total: int
    page: int
    per_page: int
    has_next: bool


def process_user(user: UserData) -> str:
    return f"User {user['id']}: {user['name']}"


user: UserData = {"id": 1, "name": "Ashish", "email": "a@b.com"}
print(f"process_user: {process_user(user)}")

admin: AdminData = {
    "id": 1, "name": "Ashish", "email": "a@b.com",
    "role": "admin", "permissions": ["read", "write", "delete"],
}
print(f"admin role: {admin['role']}")

page: PaginatedResponse = {
    "items": [{"id": 1}],
    "total": 100,
    "page": 1,
    "per_page": 20,
    "has_next": True,
}
print(f"pagination has_next: {page['has_next']}")


# ─── Section 5: @overload — Multiple Signatures ───

print("\n" + "=" * 60)
print("SECTION 5: @overload")
print("=" * 60)


# INTERVIEW: @overload declares multiple signatures for type checker
# Only the implementation (without @overload) runs at runtime
@overload
def process(data: str) -> str: ...
@overload
def process(data: int) -> int: ...
@overload
def process(data: list) -> list: ...  # type: ignore[misc]


def process(data: str | int | list) -> str | int | list:
    if isinstance(data, str):
        return data.upper()
    elif isinstance(data, int):
        return data * 2
    elif isinstance(data, list):
        return sorted(data)  # type: ignore[type-var]
    raise TypeError(f"Unsupported type: {type(data)}")


result1: str  = process("hello")     # type checker: str in → str out
result2: int  = process(42)          # type checker: int in → int out
result3: list = process([3, 1, 2])   # type checker: list in → list out

print(f"process('hello') = {result1}")
print(f"process(42) = {result2}")
print(f"process([3,1,2]) = {result3}")


# Real-world overload: read_file with Literal binary flag
@overload
def read_text(path: str, binary: Literal[False] = ...) -> str: ...
@overload
def read_text(path: str, binary: Literal[True]) -> bytes: ...


def read_text(path: str, binary: bool = False) -> str | bytes:
    """Return str or bytes depending on binary flag."""
    mode = "rb" if binary else "r"
    try:
        with open(path, mode) as f:
            return f.read()
    except FileNotFoundError:
        return b"" if binary else ""


# Type checker knows: read_text("x.txt") → str, read_text("x.bin", True) → bytes
text_content: str   = read_text("nonexistent.txt")
bytes_content: bytes = read_text("nonexistent.bin", True)
print(f"\nread_text (str fallback) type: {type(text_content).__name__}")
print(f"read_text (bytes fallback) type: {type(bytes_content).__name__}")


# ─── Section 6: ParamSpec — Type-safe Decorators ───

print("\n" + "=" * 60)
print("SECTION 6: ParamSpec — Type-safe Decorators")
print("=" * 60)

# INTERVIEW: ParamSpec = capture the entire parameter specification of a function
# Needed for decorators so the wrapper has the SAME signature as the original
# Without ParamSpec: wrapper shows (*args: Any, **kwargs: Any) — type info lost
P = ParamSpec("P")


def timer(func: Callable[P, T]) -> Callable[P, T]:
    """Measures execution time — original signature preserved via ParamSpec."""
    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        print(f"  {func.__name__} took {elapsed:.4f}s")
        return result
    return wrapper


def retry(times: int = 3) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Retry on exception — parameterised decorator with type safety."""
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exc: Exception = RuntimeError("No attempts")
            for attempt in range(times):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc
                    print(f"  Retry {attempt + 1}/{times}: {exc}")
            raise last_exc
        return wrapper
    return decorator


@timer
def slow_add(a: int, b: int) -> int:
    time.sleep(0.01)
    return a + b


@timer
@retry(times=3)
def flaky_fetch(url: str, timeout: int = 30) -> dict:
    # Simulates a flaky operation
    return {"url": url, "data": "ok", "timeout": timeout}


print(f"slow_add(3, 4) = {slow_add(3, 4)}")
# Type checker: slow_add still shows (a: int, b: int) -> int  ← ParamSpec preserves it

result = flaky_fetch("https://api.example.com", timeout=10)
print(f"flaky_fetch result = {result}")


# ─── Section 7: Annotated — Type + Metadata ───

print("\n" + "=" * 60)
print("SECTION 7: Annotated — Type + Metadata")
print("=" * 60)


# INTERVIEW: Annotated[type, metadata...] — type for type checker, metadata for libraries
# Pydantic uses Annotated for validators, FastAPI uses it for Query/Path/Body params


class Gt:
    def __init__(self, value: float) -> None:
        self.value = value

    def __repr__(self) -> str:
        return f"Gt({self.value})"


class MaxLen:
    def __init__(self, value: int) -> None:
        self.value = value

    def __repr__(self) -> str:
        return f"MaxLen({self.value})"


class Description:
    def __init__(self, text: str) -> None:
        self.text = text


# Reusable annotated type aliases
PositiveInt = Annotated[int, Gt(0), Description("Must be positive integer")]
ShortStr    = Annotated[str, MaxLen(100)]
PriceINR    = Annotated[float, Gt(0), Description("Price in Indian Rupees")]


@dataclass
class Product:
    id: PositiveInt
    name: ShortStr
    price: PriceINR
    quantity: Annotated[int, Gt(-1)]


# Reading Annotated metadata at runtime
hints = get_type_hints(Product, include_extras=True)
print("Product field Annotated metadata:")
for fname, hint in hints.items():
    args = get_args(hint)
    if args:
        type_hint = args[0]
        metadata = args[1:]
        print(f"  {fname}: type={type_hint.__name__}, meta={metadata}")

# Pydantic integration (shows the pattern — actual validation in pydantic file)
print("\nFastAPI-style usage:")
print("  def create_product(")
print("      name: Annotated[str, Query(min_length=1, max_length=100)],")
print("      price: Annotated[float, Query(gt=0)],")
print("  ) -> dict: ...")


# ─── Section 8: TYPE_CHECKING — Circular Import Prevention ───

print("\n" + "=" * 60)
print("SECTION 8: TYPE_CHECKING — Circular Import Fix")
print("=" * 60)

# INTERVIEW: In large codebases, A imports B for type hints, B imports A for logic
# Circular import at runtime crashes with ImportError
# Solution: if TYPE_CHECKING block — runs only during mypy/pyright analysis, NOT runtime

# Simulated circular import scenario in comments:
print("""
# models.py
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services import UserService   # Import only when type-checking
    # At runtime: this block is SKIPPED — no circular import

class User:
    def get_service(self) -> UserService:  # Forward reference as string
        from services import UserService   # Real runtime import inside method
        return UserService(self)

# services.py
from models import User  # Fine — models.py doesn't import services at module level

class UserService:
    def __init__(self, user: User) -> None:
        self.user = user
""")

# get_type_hints() resolves forward references (string annotations)
# Requires all referenced names to be importable at the time of the call
class SampleClass:
    value: int
    name: str


hints = get_type_hints(SampleClass)
print(f"get_type_hints(SampleClass): {hints}")


# ─── Section 9: Callable Types + Runtime Annotation Inspection ───

print("\n" + "=" * 60)
print("SECTION 9: Callable Types + Runtime Inspection")
print("=" * 60)


# INTERVIEW: Callable[[ArgTypes], ReturnType] — type hint for functions/callables
Handler = Callable[[str, int], bool]
Transformer = Callable[[list[T]], list[T]]
Predicate = Callable[[T], bool]


def run_handler(data: str, code: int, handler: Handler) -> bool:
    """Accepts any callable that matches (str, int) -> bool."""
    return handler(data, code)


def validate_code(msg: str, code: int) -> bool:
    return code == 200


print(f"run_handler result: {run_handler('test', 200, validate_code)}")


# Runtime annotation inspection — useful for frameworks that read types
def inspect_function_types(func: Callable) -> None:
    hints = get_type_hints(func)
    print(f"\n{func.__name__} type hints:")
    for param, hint in hints.items():
        origin = get_origin(hint)
        args = get_args(hint)
        print(f"  {param}: {hint} (origin={origin}, args={args})")


inspect_function_types(run_handler)

print("\n--- SUMMARY ---")
print("TypeVar           : consistent type through function/class — enables generics")
print("Generic[T]        : parameterised class — Stack[int], Result[float, ValueError]")
print("Literal           : exact value constraint — lighter than Enum")
print("Final             : constant — cannot be reassigned")
print("ClassVar          : class-level attribute — not per-instance")
print("TypedDict         : typed dict — good for JSON/API response shapes")
print("@overload         : multiple signatures — type checker picks correct return type")
print("ParamSpec         : preserve original function signature through decorators")
print("Annotated         : type + metadata — used by Pydantic, FastAPI, etc.")
print("TYPE_CHECKING     : import only during static analysis — breaks circular imports")
