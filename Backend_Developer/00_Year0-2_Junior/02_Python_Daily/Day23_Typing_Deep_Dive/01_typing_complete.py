"""
DAY 29 — typing module: Complete Senior-Level Guide
Architecture Level: Senior Python Backend + Agentic AI

Your roadmap covers TypeVar, Generic, Protocol — this fills the gaps.
"""

from __future__ import annotations  # enables forward references everywhere

from typing import (
    Optional, Union, Literal, Final, Annotated, ClassVar,
    TypeVar, Generic, Protocol, TypedDict, overload,
    get_type_hints, TYPE_CHECKING, Any, Never, Self,
)
import sys


# ═══════════════════════════════════════════════════════
# PART A: Optional and Union
# ═══════════════════════════════════════════════════════

# Optional[X] is exactly Union[X, None]
def get_user(user_id: int) -> Optional[dict]:   # same as dict | None
    if user_id == 0:
        return None
    return {"id": user_id, "name": "Alice"}


# Python 3.10+ union syntax (preferred in modern code)
def process(value: int | str | None) -> str:
    match value:  # Python 3.10+ match-case
        case None:
            return "none"
        case int(n):
            return f"int: {n}"
        case str(s):
            return f"str: {s}"


# ─────────────────────────────────────────────
# CRITICAL: Always narrow Optional before use
# ─────────────────────────────────────────────

user = get_user(1)
# WRONG: user["name"]  — mypy error: Optional is not subscriptable
# RIGHT:
if user is not None:
    print(user["name"])  # mypy knows it's dict here


# ═══════════════════════════════════════════════════════
# PART B: Literal — restrict to specific values
# ═══════════════════════════════════════════════════════

LLMModel = Literal["gpt-4", "gpt-3.5-turbo", "claude-3-opus", "claude-3-sonnet"]
HttpMethod = Literal["GET", "POST", "PUT", "DELETE", "PATCH"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def call_llm(model: LLMModel, prompt: str) -> str:
    """mypy will error if you pass an invalid model name."""
    return f"Response from {model}"


def log(level: LogLevel, message: str) -> None:
    print(f"[{level}] {message}")


# call_llm("gpt-5", "hello")  # mypy ERROR: "gpt-5" not assignable to LLMModel
call_llm("gpt-4", "hello")   # OK


# ═══════════════════════════════════════════════════════
# PART C: Final — constants that cannot be reassigned
# ═══════════════════════════════════════════════════════

MAX_RETRIES: Final[int] = 3
DEFAULT_MODEL: Final[str] = "gpt-4"
API_VERSION: Final = "v2"

# MAX_RETRIES = 5  # mypy ERROR: Cannot assign to final variable


class Config:
    DEBUG: Final[bool] = False
    MAX_CONNECTIONS: Final[int] = 100

    def __init__(self, model: str):
        self.model: Final[str] = model  # instance-level Final

    # def change_model(self):
    #     self.model = "other"  # mypy ERROR


# ═══════════════════════════════════════════════════════
# PART D: ClassVar — class-level vs instance-level
# ═══════════════════════════════════════════════════════

class Agent:
    # ClassVar — belongs to the CLASS, not instances
    _registry: ClassVar[dict[str, "Agent"]] = {}
    _instance_count: ClassVar[int] = 0

    def __init__(self, name: str, model: LLMModel):
        self.name = name          # instance variable
        self.model = model        # instance variable
        Agent._instance_count += 1
        Agent._registry[name] = self

    @classmethod
    def get_all(cls) -> dict[str, "Agent"]:
        return cls._registry

    @classmethod
    def count(cls) -> int:
        return cls._instance_count


a1 = Agent("researcher", "gpt-4")
a2 = Agent("coder", "claude-3-opus")
print(f"\nAgent count: {Agent.count()}")         # 2
print(f"Registry: {list(Agent.get_all().keys())}")


# ═══════════════════════════════════════════════════════
# PART E: Annotated — attach metadata to types
# ═══════════════════════════════════════════════════════

# Annotated[type, metadata...] — metadata is used by Pydantic, FastAPI, etc.
from dataclasses import dataclass

PositiveInt = Annotated[int, "must be > 0"]
MaxTokens = Annotated[int, "between 1 and 8192"]
Temperature = Annotated[float, "between 0.0 and 2.0"]


@dataclass
class LLMRequest:
    prompt: str
    model: LLMModel
    max_tokens: MaxTokens = 1000
    temperature: Temperature = 0.7

# In FastAPI + Pydantic v2, Annotated carries validation constraints:
# from pydantic import Field
# MaxTokens = Annotated[int, Field(ge=1, le=8192)]
# Temperature = Annotated[float, Field(ge=0.0, le=2.0)]


# ═══════════════════════════════════════════════════════
# PART F: TypedDict — typed dict structure
# ═══════════════════════════════════════════════════════

class ChatMessage(TypedDict):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatMessageWithMetadata(TypedDict, total=False):  # total=False = all keys optional
    role: Literal["user", "assistant", "system"]
    content: str
    tokens: int      # optional
    model: str       # optional


messages: list[ChatMessage] = [
    {"role": "system", "content": "You are helpful."},
    {"role": "user", "content": "Hello!"},
    {"role": "assistant", "content": "Hi there!"},
]

# TypedDict vs dataclass vs Pydantic:
# TypedDict   — just type hints, no runtime validation, compatible with dict
# dataclass   — runtime object, validation via __post_init__
# Pydantic    — runtime validation + serialization, ideal for APIs


# ═══════════════════════════════════════════════════════
# PART G: Protocol — structural subtyping (duck typing + types)
# ═══════════════════════════════════════════════════════

from typing import runtime_checkable

@runtime_checkable
class LLMProvider(Protocol):
    """Any class with these methods satisfies this Protocol."""

    def complete(self, prompt: str, **kwargs) -> str: ...
    def stream(self, prompt: str) -> Iterator[str]: ...  # type: ignore


class OpenAIProvider:
    """Does NOT inherit from LLMProvider — but satisfies the protocol."""

    def complete(self, prompt: str, **kwargs) -> str:
        return f"OpenAI: {prompt}"

    def stream(self, prompt: str):
        for word in prompt.split():
            yield word


class AnthropicProvider:
    def complete(self, prompt: str, **kwargs) -> str:
        return f"Anthropic: {prompt}"

    def stream(self, prompt: str):
        yield from prompt.split()


def run_agent(provider: LLMProvider, task: str) -> str:
    """Accepts ANY object that satisfies LLMProvider protocol."""
    return provider.complete(task)


# Both work without inheritance
openai = OpenAIProvider()
anthropic = AnthropicProvider()

print(run_agent(openai, "Explain Python"))
print(run_agent(anthropic, "Explain Python"))
print(isinstance(openai, LLMProvider))  # True (runtime_checkable)


# ═══════════════════════════════════════════════════════
# PART H: overload — multiple signatures for same function
# ═══════════════════════════════════════════════════════

@overload
def parse_response(data: str) -> dict: ...
@overload
def parse_response(data: bytes) -> dict: ...
@overload
def parse_response(data: dict) -> dict: ...

def parse_response(data: str | bytes | dict) -> dict:
    """mypy knows the return type based on input type."""
    import json
    if isinstance(data, bytes):
        return json.loads(data.decode())
    elif isinstance(data, str):
        return json.loads(data)
    return data


# ═══════════════════════════════════════════════════════
# PART I: Self type — for method chaining
# ═══════════════════════════════════════════════════════

class QueryBuilder:
    """Builder pattern — each method returns Self for chaining."""

    def __init__(self):
        self._filters: list[str] = []
        self._limit: int = 100

    def filter(self, condition: str) -> Self:
        self._filters.append(condition)
        return self

    def limit(self, n: int) -> Self:
        self._limit = n
        return self

    def build(self) -> str:
        where = " AND ".join(self._filters) if self._filters else "1=1"
        return f"SELECT * FROM table WHERE {where} LIMIT {self._limit}"


query = QueryBuilder().filter("active=true").filter("role='admin'").limit(10).build()
print(f"\nQuery: {query}")


# ─────────────────────────────────────────────
# INTERVIEW CHEAT SHEET
# ─────────────────────────────────────────────
# Optional[X]     = X | None
# Literal[...]    = restrict to specific values
# Final[X]        = constant, cannot reassign
# ClassVar[X]     = class attribute, not instance
# Annotated[X, m] = X with metadata (Pydantic uses this)
# TypedDict       = typed dict, no runtime validation
# Protocol        = structural typing (duck typing with type safety)
# Self            = return type for method chaining
# Never           = function never returns (raises/loops forever)
# Any             = opt out of type checking (avoid!)
