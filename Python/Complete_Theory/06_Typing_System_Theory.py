"""
╔══════════════════════════════════════════════════════════════════════════════╗
║   PYTHON COMPLETE THEORY — File 06                                           ║
║   Topic: Python Type System (typing module)                                  ║
║   Format: WHAT → WHY → HOW → REAL LIFE → PRODUCTION CODE → Q&A              ║
╚══════════════════════════════════════════════════════════════════════════════╝

Topics Covered:
  A. Why Type Hints? — The problem they solve
  B. Basic Type Hints — int, str, list, dict, Optional, Union
  C. Literal — restrict to specific values
  D. Final — constants
  E. ClassVar — class-level attributes
  F. Annotated — type + metadata
  G. TypedDict — structured dictionaries
  H. TypeVar and Generic[T] — generic types
  I. Protocol — structural typing (duck typing, formalized)
  J. Callable — typing function objects
  K. overload — multiple signatures for same function
  L. TypeGuard — type narrowing in conditionals
  M. Self — fluent interfaces / method chaining
  N. Never — functions that always raise / exhaustive checking
"""

from typing import (
    Optional, Union, Literal, Final, ClassVar, Annotated,
    TypedDict, TypeVar, Generic, Protocol, Callable,
    overload, TYPE_CHECKING, Any
)
import sys


# ══════════════════════════════════════════════════════════════════════════════
# PART A: WHY TYPE HINTS?
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS THE PROBLEM?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Python is DYNAMICALLY TYPED — variables can hold any type at any time.
This is flexible but causes bugs that only appear AT RUNTIME.

WITHOUT TYPE HINTS:
  def process(data):
      return data["name"].upper()  # What type is 'data'? dict? object? None?
      # If data is None → AttributeError at runtime (in production!)
      # If data is a list → TypeError at runtime

  You need to READ THE DOCS or TRACE THE CODE to understand what 'data' must be.

WITH TYPE HINTS:
  def process(data: dict[str, str]) -> str:  # instantly clear!
      return data["name"].upper()

BENEFITS:
  1. IDE autocomplete — editor knows what methods are available
  2. Static analysis — mypy, pyright catch bugs BEFORE you run the code
  3. Documentation — code IS the documentation (no "see docstring")
  4. Refactoring safety — changing a type shows where breaks will occur
  5. FastAPI, Pydantic — use type hints at RUNTIME for validation

IMPORTANT:
  Type hints are NOT enforced at runtime by default.
  Python just stores them as metadata (function.__annotations__).
  Enforcement requires: mypy, pyright, pydantic, or runtime_checkable Protocol.

REAL LIFE ANALOGY:
  Type hints = Labels on jars in a kitchen:
  Without labels: you open a jar hoping it's sugar, but it might be salt.
  (Bug discovered when food is ruined — at "runtime"!)
  With labels: you KNOW before opening. IDE/mypy catches it before cooking.
"""

# Basic type hint syntax progression
def no_hints(model, prompt, temperature):  # zero info
    pass

def with_hints(model: str, prompt: str, temperature: float = 0.7) -> str:
    """Full type info — IDE can autocomplete, mypy can check."""
    return f"[{model}] {prompt}"

# Python 3.10+ — Union with | instead of Union[]
def modern_hints(model: str, data: str | dict | None = None) -> str | None:
    if data is None:
        return None
    return f"processed"


# ══════════════════════════════════════════════════════════════════════════════
# PART B: BASIC TYPE HINTS
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COMMON TYPE ANNOTATIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Basic:
    int, float, str, bool, bytes, None

  Collections (Python 3.9+):
    list[int]           # list of ints
    dict[str, int]      # dict with str keys, int values
    tuple[int, str]     # fixed-length tuple
    tuple[int, ...]     # variable-length tuple of ints
    set[str]            # set of strings
    frozenset[str]      # frozenset of strings

  Optional (value can be None):
    Optional[str]       = Union[str, None]  = str | None  (3.10+)

  Union (can be multiple types):
    Union[str, int]     = str | int  (3.10+)

  Any:
    Any                 # opt-out of type checking (use sparingly)

  Callable:
    Callable[[int, str], bool]  # takes int + str, returns bool

  Forward references:
    "ClassName"         # string — avoids circular import
    from __future__ import annotations  # makes ALL annotations strings

MODERN SYNTAX (Python 3.10+):
    list[int]        # instead of List[int] from typing
    dict[str, int]   # instead of Dict[str, int]
    str | int | None # instead of Union[str, int, None] or Optional[str | int]

HOW TYPE NARROWING WORKS:
  def process(value: str | None) -> str:
      if value is None:       # narrowing check
          return ""
      return value.upper()    # now mypy KNOWS value is str here (not None)
"""

from typing import get_type_hints


class LLMRequest:
    """Demonstrates comprehensive type hints."""

    def __init__(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,         # None = let model decide
        stop_sequences: list[str] | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> None:
        self.model = model
        self.messages = messages
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.stop_sequences = stop_sequences or []
        self.tools = tools or []

    def add_message(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "messages": self.messages,
            "temperature": self.temperature,
            **({"max_tokens": self.max_tokens} if self.max_tokens else {}),
        }


req = LLMRequest(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello"}],
)
print(f"LLMRequest type hints: {get_type_hints(LLMRequest.__init__)}")


# ══════════════════════════════════════════════════════════════════════════════
# PART C: Literal — RESTRICT TO SPECIFIC VALUES
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS Literal?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Literal[v1, v2, v3]: this parameter must be EXACTLY one of these values.
Type-level enum — enforced by mypy/pyright at STATIC ANALYSIS time.

WHY?
  str is too broad: role: str allows "banana", "admin", "HACK" — any string!
  Literal["user", "assistant", "system"] restricts to only valid values.

WHEN TO USE:
  - HTTP methods: Literal["GET", "POST", "PUT", "DELETE", "PATCH"]
  - Log levels:   Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
  - Roles:        Literal["user", "assistant", "system", "tool"]
  - Model names:  Literal["gpt-4", "gpt-3.5-turbo", "claude-3-sonnet"]

REAL LIFE ANALOGY:
  Literal = Traffic sign enum:
  "Turn" type is not just any string — only:
    Literal["left", "right", "U-turn"]
  If you pass "backwards" → mypy catches it before car crashes!
"""

# Type aliases for readability
Role = Literal["system", "user", "assistant", "tool"]
FinishReason = Literal["stop", "length", "tool_calls", "content_filter"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
ModelName = Literal["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo", "claude-3-opus", "claude-3-sonnet"]


def create_message(role: Role, content: str) -> dict[str, str]:
    """Only accepts valid role strings — mypy catches 'banana' at dev time!"""
    return {"role": role, "content": content}

def log(level: LogLevel, message: str) -> None:
    print(f"[{level}] {message}")

def make_request(method: HttpMethod, url: str) -> None:
    print(f"  {method} {url}")


print(f"\n=== Literal ===")
msg = create_message("user", "Hello")
print(f"Message: {msg}")
log("INFO", "Application started")
make_request("GET", "/api/users")

# These would be caught by mypy:
# create_message("admin", "test")  # mypy error: 'admin' not in Literal["system","user","assistant","tool"]
# log("VERBOSE", "test")           # mypy error: 'VERBOSE' not in LogLevel


# ══════════════════════════════════════════════════════════════════════════════
# PART D: Final — CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS Final?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Final[T]: this variable/attribute must NOT be reassigned after initialization.
Type-level CONSTANT — enforced by mypy/pyright.

WHY?
  Python has no built-in constant enforcement.
  ALL_CAPS is just a naming convention — nothing prevents reassignment.
  Final makes the contract explicit and statically checkable.

LEVELS:
  Module-level:  MAX_TOKENS: Final[int] = 4096
  Class-level:   API_VERSION: ClassVar[Final[str]] = "v1"
  Instance-level: self.created_at: Final = datetime.now()
                  (set in __init__, can't be changed after)
"""

MAX_RETRY_ATTEMPTS: Final[int] = 3
DEFAULT_MODEL: Final[str] = "gpt-4"
API_BASE_URL: Final[str] = "https://api.openai.com/v1"

# These would be mypy errors:
# MAX_RETRY_ATTEMPTS = 5  # Cannot assign to final name "MAX_RETRY_ATTEMPTS"

from datetime import datetime


class AgentSession:
    VERSION: ClassVar[Final[str]] = "1.0.0"  # class-level constant

    def __init__(self, session_id: str):
        self.session_id: Final[str] = session_id       # instance-level final
        self.created_at: Final[datetime] = datetime.now()

    def info(self) -> str:
        return f"Session {self.session_id} (v{self.VERSION}) created {self.created_at}"


sess = AgentSession("sess_001")
print(f"\n=== Final ===")
print(sess.info())
print(f"MAX_RETRY_ATTEMPTS: {MAX_RETRY_ATTEMPTS}")

# This would be mypy error:
# sess.session_id = "changed"  # Cannot assign to final attribute


# ══════════════════════════════════════════════════════════════════════════════
# PART E: ClassVar — CLASS-LEVEL ATTRIBUTES
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS ClassVar?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ClassVar[T]: explicitly marks a variable as a CLASS attribute (not per-instance).
Prevents mypy from complaining when you access it via instance.
Prevents accidental use as instance variable in dataclasses.

WHY?
  Without ClassVar: ambiguous — mypy might assume it's an instance var
  With ClassVar: explicit contract — "this is shared by all instances"

HOW:
  class Config:
      instances: ClassVar[int] = 0          # shared counter
      registry: ClassVar[dict] = {}         # shared registry
      DEFAULT_MODEL: ClassVar[str] = "gpt-4" # shared constant

  In @dataclass: ClassVar prevents the field from being in __init__
"""

from typing import ClassVar


class ModelRegistry:
    _models: ClassVar[dict[str, type]] = {}       # class-wide registry
    _instance_count: ClassVar[int] = 0             # shared counter

    def __init__(self, name: str):
        self.name = name
        ModelRegistry._instance_count += 1

    @classmethod
    def register(cls, model_name: str):
        def decorator(model_class: type) -> type:
            cls._models[model_name] = model_class
            return model_class
        return decorator

    @classmethod
    def total_instances(cls) -> int:
        return cls._instance_count


print(f"\n=== ClassVar ===")
r = ModelRegistry("test")
print(f"Instance count: {ModelRegistry._instance_count}")
print(f"Models: {ModelRegistry._models}")


# ══════════════════════════════════════════════════════════════════════════════
# PART F: Annotated — TYPE + METADATA
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS Annotated?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Annotated[T, metadata, ...]: attach EXTRA INFORMATION to a type hint.
The type is still T, but with additional metadata for tools/libraries.

WHY?
  Pydantic uses Annotated to attach validators:
    Annotated[int, Field(gt=0, lt=100)]  → int that must be 0-100

  FastAPI uses Annotated for dependency injection:
    Annotated[str, Depends(get_api_key)]  → str from dependency

  You can add your own metadata for documentation or custom validators.

HOW:
  Annotated[type, *metadata]
  First arg = the actual type
  Rest = arbitrary metadata (ignored by Python runtime, used by tools)

REAL LIFE ANALOGY:
  Annotated = A typed box with a label + safety instructions:
  type     = what's in the box (the type)
  metadata = special handling instructions ("fragile", "keep upright")
  The BOX is still the same — metadata is for the HANDLER to read.
"""

from typing import Annotated, get_type_hints
from dataclasses import dataclass


# Custom metadata classes
class Min:
    def __init__(self, value: float): self.value = value

class Max:
    def __init__(self, value: float): self.value = value

class Description:
    def __init__(self, text: str): self.text = text


# Using Annotated with custom metadata
Temperature = Annotated[float, Min(0.0), Max(2.0), Description("LLM sampling temperature")]
MaxTokens   = Annotated[int, Min(1), Max(128_000), Description("Maximum tokens to generate")]
ModelName   = Annotated[str, Description("LLM model identifier")]


def create_llm_call(
    model: ModelName,
    temperature: Temperature = 0.7,
    max_tokens: MaxTokens = 2048,
) -> dict:
    """The type hints now carry semantic metadata for documentation/validation tools."""
    return {"model": model, "temperature": temperature, "max_tokens": max_tokens}


print(f"\n=== Annotated ===")
result = create_llm_call("gpt-4", temperature=0.5)
print(f"Config: {result}")

# Access the metadata at runtime
hints = get_type_hints(create_llm_call, include_extras=True)
print(f"Type hints with extras: {hints}")


# ══════════════════════════════════════════════════════════════════════════════
# PART G: TypedDict — STRUCTURED DICTIONARIES
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS TypedDict?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TypedDict: defines the EXPECTED STRUCTURE of a dictionary.
Each key has a specific type. mypy checks that you don't add unknown keys
or use wrong types for known keys.

WHY?
  Problem: dict[str, Any] is too loose — no key checks, no type checks.
  TypedDict: specific key names + specific types for each key.

  Perfect for: API request/response structures, JSON payloads, config dicts.

HOW:
  class ChatMessage(TypedDict):
      role: str        # required key
      content: str     # required key

  class LLMConfig(TypedDict, total=False):  # total=False → all keys optional
      model: str
      temperature: float

TYPED DICT vs DATACLASS:
  TypedDict: STILL a regular dict at runtime (dict operations work)
             No methods, just structure annotation for type checkers
  Dataclass: A CLASS — has methods, __init__, __repr__, etc.
             NOT a dict (can't do dict operations)

USE TypedDict WHEN:
  - Working with JSON APIs (data is already a dict)
  - Interoperating with code that expects dict
  - No methods needed — just structured data
"""

from typing import TypedDict, Required, NotRequired


class ChatMessage(TypedDict):
    """Structure of a single message in a conversation."""
    role: Literal["system", "user", "assistant", "tool"]
    content: str


class LLMRequest(TypedDict):
    """Full LLM API request structure."""
    model: str
    messages: list[ChatMessage]
    temperature: NotRequired[float]    # optional key (Python 3.11+)
    max_tokens: NotRequired[int]
    stream: NotRequired[bool]


class LLMResponse(TypedDict):
    """LLM API response structure."""
    id: str
    model: str
    choices: list[dict[str, Any]]
    usage: "UsageStats"


class UsageStats(TypedDict):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


def process_llm_response(response: LLMResponse) -> str:
    """mypy knows EXACTLY what keys are available and their types."""
    usage = response["usage"]
    total = usage["total_tokens"]
    model = response["model"]
    return f"[{model}] Used {total} tokens"


print(f"\n=== TypedDict ===")

# This is still a regular dict — TypedDict is just for type checking
message: ChatMessage = {"role": "user", "content": "Hello!"}
request: LLMRequest = {
    "model": "gpt-4",
    "messages": [message],
    "temperature": 0.7,
}

print(f"Message type: {type(message)}")   # <class 'dict'>
print(f"Request: {request}")


# ══════════════════════════════════════════════════════════════════════════════
# PART H: TypeVar and Generic[T]
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT ARE TypeVar AND Generic?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TypeVar = A TYPE VARIABLE — a placeholder for "whatever type you pass in."
Generic[T] = A class or function that WORKS WITH ANY TYPE T.

WHY?
  Problem:
    def first(items: list[Any]) -> Any:  # useless — loses type info
        return items[0]

    result = first([1, 2, 3])   # mypy thinks result is Any — no autocomple!

  Solution with TypeVar:
    T = TypeVar("T")
    def first(items: list[T]) -> T:  # preserves type!
        return items[0]

    result = first([1, 2, 3])   # mypy knows result is int!
    result = first(["a", "b"])  # mypy knows result is str!

HOW:
  T = TypeVar("T")                    # unconstrained — any type
  T = TypeVar("T", int, float)        # constrained — only int or float
  T = TypeVar("T", bound=Comparable)  # bound — must be Comparable or subclass

  class Stack(Generic[T]):            # generic class
      def push(self, item: T) -> None: ...
      def pop(self) -> T: ...

  int_stack: Stack[int] = Stack()    # mypy knows pop() returns int
  str_stack: Stack[str] = Stack()    # mypy knows pop() returns str

REAL LIFE ANALOGY:
  TypeVar = Template mold:
  Generic[T] = "Make me a box that holds <T>"
  Stack[int]  = "Make me a box that holds integers"
  Stack[str]  = "Make me a box that holds strings"
  Same blueprint, different content type — type-safe!
"""

T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")


class Stack(Generic[T]):
    """Type-safe stack — pop() returns same type as what was push()ed."""

    def __init__(self) -> None:
        self._items: list[T] = []

    def push(self, item: T) -> None:
        self._items.append(item)

    def pop(self) -> T:
        if not self._items:
            raise IndexError("Stack is empty")
        return self._items.pop()

    def peek(self) -> T:
        if not self._items:
            raise IndexError("Stack is empty")
        return self._items[-1]

    def __len__(self) -> int:
        return len(self._items)

    def __bool__(self) -> bool:
        return bool(self._items)

    def __repr__(self) -> str:
        return f"Stack({self._items!r})"


class Repository(Generic[T]):
    """Generic repository — same CRUD, different entity type."""

    def __init__(self) -> None:
        self._items: dict[str, T] = {}

    def save(self, key: str, item: T) -> None:
        self._items[key] = item

    def get(self, key: str) -> T | None:
        return self._items.get(key)

    def all(self) -> list[T]:
        return list(self._items.values())

    def delete(self, key: str) -> bool:
        if key in self._items:
            del self._items[key]
            return True
        return False


print(f"\n=== TypeVar / Generic ===")

# Type-safe stacks
int_stack: Stack[int] = Stack()
int_stack.push(1); int_stack.push(2); int_stack.push(3)
print(f"int_stack.pop() → {int_stack.pop()}")  # mypy knows this is int

str_stack: Stack[str] = Stack()
str_stack.push("hello"); str_stack.push("world")
print(f"str_stack.pop() → {str_stack.pop()!r}")  # mypy knows this is str

# Generic repository
from dataclasses import dataclass

@dataclass
class User:
    name: str
    email: str

@dataclass
class Product:
    title: str
    price: float


user_repo: Repository[User] = Repository()
user_repo.save("u1", User("Alice", "alice@example.com"))
user_repo.save("u2", User("Bob", "bob@example.com"))

product_repo: Repository[Product] = Repository()
product_repo.save("p1", Product("Python Book", 29.99))

print(f"Users: {user_repo.all()}")
print(f"Products: {product_repo.all()}")


# Generic function
def first(items: list[T]) -> T:
    """Returns first item with preserved type."""
    return items[0]


first_int: int = first([1, 2, 3])         # mypy: int
first_str: str = first(["a", "b", "c"])   # mypy: str
print(f"first int: {first_int}, first str: {first_str!r}")


# ══════════════════════════════════════════════════════════════════════════════
# PART I: Protocol — STRUCTURAL TYPING
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS Protocol?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Protocol: defines an INTERFACE based on STRUCTURE (what methods/attributes exist),
not on inheritance (what class you inherit from).

Also called "structural typing" or "duck typing — but statically typed."

"If it has .complete() and .count_tokens(), it's an LLMProvider."
You DON'T need to explicitly inherit from LLMProvider.

WHY?
  ABC (Abstract Base Class): NOMINAL typing — must explicitly inherit
    class OpenAI(LLMProviderABC):   # must inherit!

  Protocol: STRUCTURAL typing — just have the right methods
    class OpenAI:               # doesn't inherit anything
        def complete(self): ... # just has the method

  Protocol works with EXISTING classes you can't modify!
  (Third-party libraries, legacy code)

HOW:
  class LLMProvider(Protocol):
      def complete(self, prompt: str) -> str: ...
      def count_tokens(self, text: str) -> int: ...

  @runtime_checkable  →  allows isinstance() checks at runtime

REAL LIFE ANALOGY:
  Protocol = USB standard:
  "Any device with a USB-C port that can transfer data = USB-C device"
  Doesn't matter who made it — if it has the port, it works.
  ABC = "Official Apple devices only"
  Protocol = "Any device with the right port" (duck typing)
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    """Any class with these methods qualifies — no inheritance needed."""

    def complete(self, prompt: str, max_tokens: int = 1000) -> str:
        ...

    def count_tokens(self, text: str) -> int:
        ...

    def get_model_name(self) -> str:
        ...


# These classes DON'T inherit from LLMProvider — they just have the right methods
class OpenAIClient:
    """Third-party-style class — can't modify it."""

    def complete(self, prompt: str, max_tokens: int = 1000) -> str:
        return f"[OpenAI] {prompt}"

    def count_tokens(self, text: str) -> int:
        return len(text.split()) * 4 // 3

    def get_model_name(self) -> str:
        return "gpt-4"


class AnthropicClient:
    """Another third-party class."""

    def complete(self, prompt: str, max_tokens: int = 1000) -> str:
        return f"[Anthropic] {prompt}"

    def count_tokens(self, text: str) -> int:
        return len(text.encode()) // 4

    def get_model_name(self) -> str:
        return "claude-3-sonnet"


class LocalModel:
    """Doesn't have count_tokens — NOT a valid LLMProvider!"""

    def complete(self, prompt: str, max_tokens: int = 1000) -> str:
        return f"[Local] {prompt}"

    def get_model_name(self) -> str:
        return "llama-3"
    # Missing count_tokens → NOT a structural LLMProvider


def call_provider(provider: LLMProvider, prompt: str) -> str:
    """Works with ANY object that has the right methods."""
    tokens = provider.count_tokens(prompt)
    return provider.complete(prompt) + f" [{tokens} tokens]"


print(f"\n=== Protocol (structural typing) ===")
openai = OpenAIClient()
anthropic = AnthropicClient()

print(f"OpenAI is LLMProvider: {isinstance(openai, LLMProvider)}")       # True!
print(f"Anthropic is LLMProvider: {isinstance(anthropic, LLMProvider)}") # True!

for provider in [openai, anthropic]:
    result = call_provider(provider, "What is Python?")
    print(f"  {provider.get_model_name()}: {result}")

# ABC vs Protocol
print(f"\nProtocol vs ABC:")
print("  ABC:      class OpenAI(LLMProviderABC) — must INHERIT")
print("  Protocol: class OpenAI — just needs the RIGHT METHODS (duck typing)")


# ══════════════════════════════════════════════════════════════════════════════
# PART J: Callable — TYPING FUNCTION OBJECTS
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS Callable?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Callable[[arg_types], return_type]: type hint for functions/callables passed as arguments.

HOW:
  Callable[[int, str], bool]   # takes int and str, returns bool
  Callable[..., str]           # any args, returns str
  Callable[[], None]           # no args, no return

WHY?
  When passing functions as arguments (callbacks, strategies, handlers),
  Callable tells mypy the expected function signature.
"""

from typing import Callable

# Function that takes a function as argument
def retry(
    func: Callable[..., T],
    max_attempts: int = 3,
    on_error: Callable[[Exception, int], None] | None = None,
) -> Callable[..., T]:
    """Retry decorator — type-safe."""
    import functools

    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> T:
        for attempt in range(max_attempts):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if on_error:
                    on_error(e, attempt)
                if attempt == max_attempts - 1:
                    raise
        raise RuntimeError("Should not reach here")
    return wrapper  # type: ignore

# Middleware/pipeline
def create_pipeline(*steps: Callable[[str], str]) -> Callable[[str], str]:
    """Compose multiple string transformers."""
    def pipeline(text: str) -> str:
        result = text
        for step in steps:
            result = step(result)
        return result
    return pipeline


print(f"\n=== Callable ===")
pipeline = create_pipeline(
    str.strip,
    str.lower,
    lambda s: s.replace(" ", "_"),
)

result = pipeline("  Hello World  ")
print(f"Pipeline result: '{result}'")


# ══════════════════════════════════════════════════════════════════════════════
# PART K: @overload — MULTIPLE SIGNATURES
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS @overload?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@overload allows a function to have MULTIPLE TYPE SIGNATURES
for different argument combinations — each combination returns a different type.

WHY?
  Problem:
    def process(data: str | dict) -> str | dict:  # too loose!
    # If str in → str out, if dict in → dict out
    # But return type is str | dict for all cases — not precise

  Solution with @overload:
    @overload
    def process(data: str) -> str: ...
    @overload
    def process(data: dict) -> dict: ...
    def process(data): ...  # actual implementation

  Now mypy knows: str in → str out, dict in → dict out.

HOW:
  @overload defines the TYPE-ONLY signatures (body = ...)
  The LAST definition (no @overload) is the ACTUAL implementation
  The actual implementation is NOT seen by mypy — only overload variants are.
"""

from typing import overload


@overload
def parse_response(data: str) -> dict[str, Any]: ...
@overload
def parse_response(data: dict) -> dict[str, Any]: ...
@overload
def parse_response(data: list) -> list[dict[str, Any]]: ...


def parse_response(data: str | dict | list) -> dict[str, Any] | list[dict[str, Any]]:
    """Actual implementation — handles all types."""
    import json
    if isinstance(data, str):
        return json.loads(data)
    elif isinstance(data, dict):
        return data
    elif isinstance(data, list):
        return [item if isinstance(item, dict) else {"value": item} for item in data]
    raise TypeError(f"Unsupported type: {type(data)}")


print(f"\n=== @overload ===")
r1 = parse_response('{"model": "gpt-4", "tokens": 100}')
r2 = parse_response({"model": "claude-3", "tokens": 200})
r3 = parse_response([1, 2, {"key": "val"}])
print(f"from str:  {r1}")
print(f"from dict: {r2}")
print(f"from list: {r3}")


# ══════════════════════════════════════════════════════════════════════════════
# PART L: TypeGuard — TYPE NARROWING
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS TypeGuard?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TypeGuard[T]: when a function returns True, mypy NARROWS the type of the checked
value to T in the if block.

WHY?
  Problem:
    def process(items: list[str | int]) -> None:
        for item in items:
            if isinstance(item, str):
                item.upper()   # mypy knows: str here
            else:
                item + 1       # mypy knows: int here
    # isinstance works inline, but what about custom checkers?

  With TypeGuard for custom validation functions:
    def is_valid_message(data: dict) -> TypeGuard[ChatMessage]: ...
    if is_valid_message(data):
        data["role"]  # mypy knows: data is ChatMessage here
"""

from typing import TypeGuard


def is_chat_message(data: Any) -> TypeGuard[ChatMessage]:
    """Custom type guard — validates AND narrows type."""
    return (
        isinstance(data, dict)
        and "role" in data
        and "content" in data
        and isinstance(data["role"], str)
        and isinstance(data["content"], str)
        and data["role"] in ("system", "user", "assistant", "tool")
    )


def process_messages(items: list[Any]) -> list[ChatMessage]:
    """Filter and type-narrow using TypeGuard."""
    valid = []
    for item in items:
        if is_chat_message(item):  # ← TypeGuard narrows type here
            valid.append(item)     # mypy knows item is ChatMessage
        else:
            print(f"  Skipping invalid: {item}")
    return valid


print(f"\n=== TypeGuard ===")
raw_data = [
    {"role": "user", "content": "Hello"},
    {"role": "invalid_role", "content": "test"},
    {"only_key": "no role or content"},
    {"role": "assistant", "content": "World"},
    "not a dict at all",
]

valid_messages = process_messages(raw_data)
print(f"Valid messages: {valid_messages}")


# ══════════════════════════════════════════════════════════════════════════════
# PART M: Self — FLUENT INTERFACES
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS Self?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Self (Python 3.11+, or from typing_extensions for older):
Return type that means "returns the same type as self."

WHY?
  Problem with method chaining:
    class Base:
        def set_x(self) -> "Base":  # returns Base, not subclass!
            return self

    class Child(Base):
        pass

    c = Child().set_x()   # mypy thinks c is Base, not Child!
                          # c.child_only_method()  → mypy error (Base has no such method)

  Self fixes this:
    class Base:
        def set_x(self) -> Self:  # returns SAME TYPE as self
            return self

    c = Child().set_x()   # mypy knows c is Child! ✅

USE CASES:
  - Fluent builder pattern: builder.with_x().with_y().build()
  - @classmethod factory: returns instance of the actual subclass, not Base
"""

from typing import Self


class QueryBuilder:
    """Fluent interface with Self — method chaining."""

    def __init__(self) -> None:
        self._table: str = ""
        self._conditions: list[str] = []
        self._limit: int | None = None
        self._columns: list[str] = ["*"]

    def from_table(self, table: str) -> Self:
        self._table = table
        return self

    def select(self, *columns: str) -> Self:
        self._columns = list(columns)
        return self

    def where(self, condition: str) -> Self:
        self._conditions.append(condition)
        return self

    def limit(self, n: int) -> Self:
        self._limit = n
        return self

    def build(self) -> str:
        cols = ", ".join(self._columns)
        query = f"SELECT {cols} FROM {self._table}"
        if self._conditions:
            query += " WHERE " + " AND ".join(self._conditions)
        if self._limit:
            query += f" LIMIT {self._limit}"
        return query


print(f"\n=== Self — QueryBuilder ===")
query = (
    QueryBuilder()
    .from_table("conversations")
    .select("id", "model", "created_at")
    .where("model = 'gpt-4'")
    .where("tokens > 100")
    .limit(10)
    .build()
)
print(f"Query: {query}")


# ══════════════════════════════════════════════════════════════════════════════
# PART N: Never — EXHAUSTIVE CHECKING
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS Never?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Never (or NoReturn): return type of functions that NEVER return normally.
They always raise an exception or run infinitely.

WHY TWO USES?

  1. Functions that always raise:
     def fail(msg: str) -> Never:
         raise RuntimeError(msg)

  2. Exhaustive check (assert_never):
     If all cases of a Union are handled, the remaining branch should be Never.
     If mypy says "error: argument is X not Never" → you forgot to handle X!

HOW (assert_never pattern):
  def handle_event(event: ClickEvent | KeyEvent) -> str:
      if isinstance(event, ClickEvent):
          return "click"
      elif isinstance(event, KeyEvent):
          return "key"
      else:
          assert_never(event)  # if you add HoverEvent, mypy ERROR here!
                               # because HoverEvent is not Never
"""

from typing import Never, NoReturn


def assert_never(value: Never) -> Never:
    """Called in 'impossible' branches — mypy uses this for exhaustiveness."""
    raise AssertionError(f"Unhandled case: {value!r}")


def fail(message: str) -> Never:
    """Always raises — Never returns normally."""
    raise RuntimeError(message)


Event = Literal["click", "keypress", "scroll"]


def handle_event(event: Event) -> str:
    if event == "click":
        return "handling click"
    elif event == "keypress":
        return "handling keypress"
    elif event == "scroll":
        return "handling scroll"
    else:
        # If you add "hover" to Event Literal but forget this function →
        # mypy error: "hover" is not Never → you're missing a case!
        assert_never(event)


print(f"\n=== Never ===")
print(handle_event("click"))
print(handle_event("scroll"))


"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Q&A — Complete Typing System
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q1: Are type hints enforced at runtime in Python?
A:  NO — by default, Python ignores type hints at runtime.
    They are stored in __annotations__ but NOT validated.
    Enforcement requires: mypy/pyright (static analysis), or
    Pydantic (runtime validation using type hints), or
    FastAPI (uses Pydantic + type hints for request/response validation).

Q2: What is the difference between Protocol and ABC?
A:  ABC (nominal typing): class MUST INHERIT from the ABC to be compatible.
    Protocol (structural typing): class just needs the RIGHT METHODS/ATTRIBUTES.
    Protocol works with third-party code you can't modify.
    ABC requires you to modify the class to add the inheritance.

    Use Protocol when: working with existing classes, third-party libs, duck typing.
    Use ABC when: you control all subclasses, want explicit enforcement of hierarchy.

Q3: When should you use TypedDict vs dataclass vs NamedTuple?
A:  TypedDict: when the data IS a dict (JSON APIs, interop with dict-expecting code)
              no methods, just structure annotation, still dict at runtime
    NamedTuple: immutable, lightweight record, tuple-compatible, hashable
                add simple methods, good for value objects
    dataclass: mutable by default, rich features (__post_init__, field()),
               best for complex objects that need methods and validation

Q4: What does TypeVar "bound" do?
A:  T = TypeVar("T", bound=SomeClass) means T must be SomeClass or a SUBCLASS.
    Like a constraint: "any type as long as it IS-A SomeClass."
    Without bound: T can be any type at all.
    Constrained T = TypeVar("T", int, float) means T must be exactly int OR float (not subclasses).

Q5: What is the difference between Optional[T] and T | None?
A:  They are IDENTICAL — Optional[T] is shorthand for Union[T, None].
    Optional[str] = Union[str, None] = str | None (Python 3.10+)
    Prefer str | None in modern Python (3.10+) for clarity.
    Optional is sometimes confusing because people think "optional parameter"
    but it actually means "can be None."
"""

print("\n✅ 06_Typing_System_Theory.py complete — all sections covered.")
