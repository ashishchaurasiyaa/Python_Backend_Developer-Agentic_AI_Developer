"""
╔══════════════════════════════════════════════════════════════╗
║  PYTHON COMPLETE PRACTICAL — Section 03                      ║
║  Topic: Typing System — Complete Advanced Reference          ║
╚══════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

from typing import (
    Optional, Union, Literal, Final, Annotated, ClassVar,
    TypeVar, Generic, Protocol, TypedDict, overload,
    runtime_checkable, Any, Never, Self, TypeGuard,
    Callable, Awaitable, Coroutine, Generator, AsyncGenerator,
    NamedTuple, TYPE_CHECKING,
)
from dataclasses import dataclass
import sys

if TYPE_CHECKING:
    from collections.abc import Sequence

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)       # producer
T_contra = TypeVar("T_contra", contravariant=True)  # consumer
KT = TypeVar("KT")
VT = TypeVar("VT")


# ══════════════════════════════════════════════════════════════
# PART A: BASIC TYPES
# ══════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────
# 1. Optional, Union, Literal
# ─────────────────────────────────────────────────────────────

# Optional[X] == X | None
def get_user(user_id: int) -> Optional[dict]:
    return {"id": user_id} if user_id > 0 else None

# Union — multiple types
def process(value: str | int | float | None) -> str:
    if value is None:
        return "none"
    return str(value)

# Literal — restrict to specific values
Model = Literal["gpt-4", "gpt-3.5-turbo", "claude-3-opus", "claude-3-sonnet"]
HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
StatusCode = Literal[200, 201, 400, 401, 403, 404, 422, 429, 500]

def call_model(model: Model, prompt: str) -> str:
    return f"[{model}] {prompt}"

def make_request(method: HttpMethod, path: str) -> dict:
    return {"method": method, "path": path}

# mypy error: call_model("gpt-5", "hello")  # "gpt-5" not assignable


# ─────────────────────────────────────────────────────────────
# 2. Final, ClassVar, Annotated
# ─────────────────────────────────────────────────────────────

MAX_TOKENS: Final[int] = 8192
DEFAULT_MODEL: Final[str] = "gpt-4"
API_VERSION: Final = "v2"

class AppConfig:
    # ClassVar — class-level, not instance
    _instances: ClassVar[dict[str, AppConfig]] = {}
    DEFAULT_TIMEOUT: ClassVar[int] = 30

    def __init__(self, model: str):
        self.model: Final[str] = model   # instance-level Final

# Annotated — type + metadata (Pydantic, FastAPI use this heavily)
from typing import get_type_hints

PositiveInt    = Annotated[int, "must be > 0"]
MaxTokensType  = Annotated[int, "between 1 and 8192"]
Temperature    = Annotated[float, "between 0.0 and 2.0"]
NonEmptyStr    = Annotated[str, "cannot be empty"]
EmailStr       = Annotated[str, "valid email format"]

# Pydantic v2 style (conceptual):
# from pydantic import Field
# MaxTokens = Annotated[int, Field(ge=1, le=8192, description="Max response tokens")]
# Temp      = Annotated[float, Field(ge=0.0, le=2.0)]


# ─────────────────────────────────────────────────────────────
# 3. TypedDict — typed dict structure
# ─────────────────────────────────────────────────────────────

class ChatMessage(TypedDict):
    role: Literal["user", "assistant", "system"]
    content: str

class ChatMessageFull(TypedDict, total=False):   # total=False = all optional
    role: Literal["user", "assistant", "system"]
    content: str
    name: str         # optional
    tool_call_id: str # optional

class LLMResponse(TypedDict):
    id: str
    model: str
    content: str
    input_tokens: int
    output_tokens: int
    finish_reason: Literal["stop", "length", "tool_calls", "content_filter"]


messages: list[ChatMessage] = [
    {"role": "system", "content": "You are helpful."},
    {"role": "user", "content": "Hello!"},
]

def send_messages(msgs: list[ChatMessage]) -> LLMResponse:
    return {
        "id": "resp_123",
        "model": "gpt-4",
        "content": "Hi!",
        "input_tokens": 10,
        "output_tokens": 5,
        "finish_reason": "stop",
    }


# ══════════════════════════════════════════════════════════════
# PART B: GENERICS
# ══════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────
# 4. TypeVar and Generic classes
# ─────────────────────────────────────────────────────────────

class Stack(Generic[T]):
    """Type-safe stack."""

    def __init__(self) -> None:
        self._items: list[T] = []

    def push(self, item: T) -> None:
        self._items.append(item)

    def pop(self) -> T:
        if not self._items:
            raise IndexError("Stack is empty")
        return self._items.pop()

    def peek(self) -> T:
        return self._items[-1]

    def __len__(self) -> int:
        return len(self._items)

    def __bool__(self) -> bool:
        return bool(self._items)


int_stack: Stack[int] = Stack()
int_stack.push(1)
int_stack.push(2)
print(int_stack.pop())   # 2

str_stack: Stack[str] = Stack()
str_stack.push("hello")


# Generic with multiple TypeVars
class Pair(Generic[KT, VT]):
    def __init__(self, key: KT, value: VT) -> None:
        self.key = key
        self.value = value

    def swap(self) -> Pair[VT, KT]:
        return Pair(self.value, self.key)

p = Pair("model", 42)
swapped = p.swap()   # Pair[int, str]


# Generic function
def first(items: list[T]) -> T:
    return items[0]

def zip_two(a: list[T], b: list[T]) -> list[tuple[T, T]]:
    return list(zip(a, b))

result = zip_two([1, 2, 3], [4, 5, 6])


# ─────────────────────────────────────────────────────────────
# 5. Generic Repository pattern — production architecture
# ─────────────────────────────────────────────────────────────

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

@dataclass
class Entity:
    id: int

@dataclass
class UserEntity(Entity):
    email: str
    role: str = "user"

@dataclass
class AgentEntity(Entity):
    name: str
    model: str


class Repository(ABC, Generic[T]):
    """Generic repository — works with any entity type."""

    @abstractmethod
    def find_by_id(self, id: int) -> T | None: ...

    @abstractmethod
    def find_all(self) -> list[T]: ...

    @abstractmethod
    def save(self, entity: T) -> T: ...

    @abstractmethod
    def delete(self, id: int) -> bool: ...


class InMemoryRepository(Repository[T]):
    """Generic in-memory implementation."""

    def __init__(self) -> None:
        self._store: dict[int, T] = {}

    def find_by_id(self, id: int) -> T | None:
        return self._store.get(id)

    def find_all(self) -> list[T]:
        return list(self._store.values())

    def save(self, entity: T) -> T:
        self._store[entity.id] = entity   # type: ignore[attr-defined]
        return entity

    def delete(self, id: int) -> bool:
        if id in self._store:
            del self._store[id]
            return True
        return False


user_repo: InMemoryRepository[UserEntity] = InMemoryRepository()
user_repo.save(UserEntity(1, "alice@example.com", "admin"))
user_repo.save(UserEntity(2, "bob@example.com"))

agent_repo: InMemoryRepository[AgentEntity] = InMemoryRepository()
agent_repo.save(AgentEntity(1, "researcher", "gpt-4"))

user = user_repo.find_by_id(1)
print(f"\nUser: {user}")
print(f"All users: {user_repo.find_all()}")


# ══════════════════════════════════════════════════════════════
# PART C: PROTOCOLS (structural typing)
# ══════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────
# 6. Protocol — duck typing + type safety
# ─────────────────────────────────────────────────────────────

@runtime_checkable
class Embeddable(Protocol):
    """Any class with these methods satisfies this Protocol."""
    def embed(self, text: str) -> list[float]: ...
    def similarity(self, a: list[float], b: list[float]) -> float: ...


@runtime_checkable
class LLMProvider(Protocol):
    def complete(self, prompt: str, **kwargs) -> str: ...
    def stream(self, prompt: str) -> Generator[str, None, None]: ...


# Classes that satisfy LLMProvider WITHOUT inheriting from it
class OpenAIClient:
    def complete(self, prompt: str, **kwargs) -> str:
        return f"OpenAI: {prompt}"

    def stream(self, prompt: str) -> Generator[str, None, None]:
        yield from prompt.split()


class AnthropicClient:
    def complete(self, prompt: str, **kwargs) -> str:
        return f"Anthropic: {prompt}"

    def stream(self, prompt: str) -> Generator[str, None, None]:
        yield from prompt.split()


def run_with_provider(provider: LLMProvider, prompt: str) -> str:
    """Accepts any LLMProvider — no inheritance required."""
    return provider.complete(prompt)


openai_client = OpenAIClient()
anthropic_client = AnthropicClient()

print(f"\n{run_with_provider(openai_client, 'Hello')}")
print(f"{run_with_provider(anthropic_client, 'Hello')}")
print(f"isinstance check: {isinstance(openai_client, LLMProvider)}")


# ─────────────────────────────────────────────────────────────
# 7. Callable type hints
# ─────────────────────────────────────────────────────────────

from collections.abc import Callable

# Callable[[arg_types], return_type]
Transform = Callable[[str], str]
Validator = Callable[[Any], bool]
EventHandler = Callable[[str, dict], None]
LLMCall = Callable[[str, int, float], str]   # prompt, max_tokens, temp -> response

def apply_transform(text: str, transform: Transform) -> str:
    return transform(text)

def pipe(value: str, *transforms: Transform) -> str:
    """Apply transforms in sequence."""
    for t in transforms:
        value = t(value)
    return value

result = pipe(
    "  Hello World  ",
    str.strip,
    str.lower,
    lambda s: s.replace(" ", "_"),
)
print(f"\nPipe result: {result}")   # hello_world


# ─────────────────────────────────────────────────────────────
# 8. overload — multiple type signatures
# ─────────────────────────────────────────────────────────────

@overload
def parse_response(data: str) -> dict: ...
@overload
def parse_response(data: bytes) -> dict: ...
@overload
def parse_response(data: dict) -> dict: ...

def parse_response(data: str | bytes | dict) -> dict:
    import json
    if isinstance(data, bytes):
        return json.loads(data.decode())
    if isinstance(data, str):
        return json.loads(data)
    return data

r1 = parse_response('{"model": "gpt-4"}')
r2 = parse_response(b'{"model": "gpt-4"}')
r3 = parse_response({"model": "gpt-4"})


# ─────────────────────────────────────────────────────────────
# 9. TypeGuard — narrow type in conditionals
# ─────────────────────────────────────────────────────────────

def is_chat_message(data: dict) -> TypeGuard[ChatMessage]:
    """Type guard — tells mypy this returns True only for ChatMessage."""
    return (
        isinstance(data, dict)
        and "role" in data
        and "content" in data
        and data["role"] in ("user", "assistant", "system")
    )

def process_message(data: dict) -> str:
    if is_chat_message(data):
        # mypy knows data: ChatMessage here
        return f"[{data['role']}] {data['content']}"
    return f"Unknown message: {data}"


# ─────────────────────────────────────────────────────────────
# 10. Self — method chaining
# ─────────────────────────────────────────────────────────────

class QueryBuilder:
    def __init__(self):
        self._table = ""
        self._conditions: list[str] = []
        self._limit: int = 100
        self._order: str = ""

    def from_table(self, table: str) -> Self:
        self._table = table
        return self

    def where(self, condition: str) -> Self:
        self._conditions.append(condition)
        return self

    def order_by(self, field: str, desc: bool = False) -> Self:
        self._order = f"{field} {'DESC' if desc else 'ASC'}"
        return self

    def limit(self, n: int) -> Self:
        self._limit = n
        return self

    def build(self) -> str:
        q = f"SELECT * FROM {self._table}"
        if self._conditions:
            q += " WHERE " + " AND ".join(self._conditions)
        if self._order:
            q += f" ORDER BY {self._order}"
        q += f" LIMIT {self._limit}"
        return q


query = (
    QueryBuilder()
    .from_table("users")
    .where("active = true")
    .where("role = 'admin'")
    .order_by("created_at", desc=True)
    .limit(10)
    .build()
)
print(f"\nSQL: {query}")


# ─────────────────────────────────────────────────────────────
# 11. Never — function that never returns
# ─────────────────────────────────────────────────────────────

def abort(message: str) -> Never:
    """Function that always raises — return type is Never."""
    raise SystemExit(f"Fatal: {message}")

def assert_never(value: Never) -> Never:
    """Exhaustiveness check in match-case."""
    raise AssertionError(f"Unexpected value: {value!r}")


# ─────────────────────────────────────────────────────────────
# INTERVIEW QUESTIONS
# ─────────────────────────────────────────────────────────────
"""
Q: What's the difference between Protocol and ABC?
A: ABC uses inheritance (explicit: class MyClass(MyABC)).
   Protocol uses structural subtyping (implicit: if it has the methods, it qualifies).
   Protocol is better for third-party types you don't control.
   ABCs are better when you own the type hierarchy and want enforcement.

Q: What is covariant vs contravariant TypeVar?
A: Covariant (T_co): if Dog is a subtype of Animal,
   Container[Dog] is a subtype of Container[Animal]. (Producer)
   Contravariant (T_contra): opposite direction. (Consumer)
   Invariant (default): exact type match required.

Q: What does TypeGuard do?
A: Tells the type checker that when this function returns True,
   the argument is narrowed to the TypeGuard type.
   Used to create type-safe isinstance-like checks for complex types.

Q: What's the difference between TypedDict and dataclass?
A: TypedDict: just type hints, no runtime behavior, is-a dict.
   dataclass: creates class with __init__, __repr__, etc., not a dict.
   TypedDict is for typing existing dict structures (JSON, APIs).
   dataclass is for creating new typed objects.

Q: When would you use Generic[T]?
A: When a class's behavior is the same regardless of the element type.
   Stack[int], Stack[str] — same code, different element types.
   Repository[User], Repository[Agent] — same CRUD, different entities.
"""
