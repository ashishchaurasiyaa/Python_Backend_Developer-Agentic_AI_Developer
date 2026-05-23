"""
╔══════════════════════════════════════════════════════════════╗
║  PYTHON COMPLETE PRACTICAL — Section 02                      ║
║  Topic: OOP — Classes, Inheritance, Polymorphism, Dunder     ║
╚══════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import ClassVar, Any
import functools


# ══════════════════════════════════════════════════════════════
# PART A: CLASS FUNDAMENTALS
# ══════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────
# 1. CLASS ANATOMY
# ─────────────────────────────────────────────────────────────

class LLMModel:
    """
    Demonstrates all class components.
    A complete model class with validation and rich interface.
    """

    # Class variable — shared across ALL instances
    _registry: ClassVar[dict[str, LLMModel]] = {}
    _instance_count: ClassVar[int] = 0

    # Class-level constants
    SUPPORTED_PROVIDERS: ClassVar[frozenset[str]] = frozenset({
        "openai", "anthropic", "google", "meta"
    })

    def __init__(self, name: str, provider: str, context_window: int):
        # Validate
        if provider not in self.SUPPORTED_PROVIDERS:
            raise ValueError(f"Unknown provider: {provider}. Use: {self.SUPPORTED_PROVIDERS}")
        if context_window < 1:
            raise ValueError("context_window must be positive")

        # Instance variables
        self.name = name
        self.provider = provider
        self.context_window = context_window
        self._call_count: int = 0         # "private" by convention
        self.__secret: str = "hidden"     # name-mangled → _LLMModel__secret

        # Register
        LLMModel._registry[name] = self
        LLMModel._instance_count += 1

    # ── Instance method ───────────────────────────────────────
    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate API cost in USD."""
        rates = {
            "openai": (0.003, 0.015),
            "anthropic": (0.003, 0.015),
            "google": (0.001, 0.002),
            "meta": (0.0, 0.0),  # open source
        }
        in_rate, out_rate = rates[self.provider]
        return (input_tokens * in_rate + output_tokens * out_rate) / 1000

    def call(self, prompt: str) -> str:
        self._call_count += 1
        return f"[{self.name}] Response to: {prompt[:30]}..."

    # ── Property ──────────────────────────────────────────────
    @property
    def call_count(self) -> int:
        """Read-only access to call counter."""
        return self._call_count

    @property
    def is_large_context(self) -> bool:
        return self.context_window >= 100_000

    # ── Class method ──────────────────────────────────────────
    @classmethod
    def get(cls, name: str) -> LLMModel | None:
        """Factory: get from registry."""
        return cls._registry.get(name)

    @classmethod
    def get_all(cls) -> dict[str, LLMModel]:
        return cls._registry.copy()

    @classmethod
    def count(cls) -> int:
        return cls._instance_count

    # ── Static method ─────────────────────────────────────────
    @staticmethod
    def is_valid_provider(provider: str) -> bool:
        """Utility — no access to cls or self."""
        return provider in LLMModel.SUPPORTED_PROVIDERS

    @staticmethod
    def tokens_to_cost(tokens: int, rate_per_1k: float) -> float:
        return tokens * rate_per_1k / 1000

    # ── Dunder methods ────────────────────────────────────────
    def __repr__(self) -> str:
        return f"LLMModel(name={self.name!r}, provider={self.provider!r}, ctx={self.context_window:,})"

    def __str__(self) -> str:
        return f"{self.name} ({self.provider})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, LLMModel):
            return NotImplemented
        return self.name == other.name and self.provider == other.provider

    def __hash__(self) -> int:
        return hash((self.name, self.provider))

    def __lt__(self, other: LLMModel) -> bool:
        return self.context_window < other.context_window

    def __bool__(self) -> bool:
        return True  # always truthy (exists = valid)

    def __len__(self) -> int:
        return self.context_window

    def __contains__(self, word: str) -> bool:
        """word in model — check if model name contains word."""
        return word.lower() in self.name.lower()


# Demo
gpt4     = LLMModel("gpt-4",     "openai",    8_192)
claude   = LLMModel("claude-3",  "anthropic", 200_000)
gemini   = LLMModel("gemini",    "google",    1_000_000)

print(gpt4)           # gpt-4 (openai)
print(repr(gpt4))     # LLMModel(name='gpt-4', ...)
print(gpt4 < claude)  # True (smaller context window)
print("gpt" in gpt4)  # True (__contains__)
print(len(claude))    # 200000 (__len__)

# Set operations use __hash__ and __eq__
model_set = {gpt4, claude, gemini}
print(f"Unique models: {len(model_set)}")

# Sorted uses __lt__
sorted_models = sorted([claude, gemini, gpt4])
print([m.name for m in sorted_models])   # gpt-4, claude-3, gemini

print(f"\nEstimated cost: ${gpt4.estimate_cost(1000, 500):.4f}")
gpt4.call("What is Python?")
print(f"Call count: {gpt4.call_count}")
print(f"Total models: {LLMModel.count()}")


# ══════════════════════════════════════════════════════════════
# PART B: INHERITANCE
# ══════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────
# 2. SINGLE INHERITANCE
# ─────────────────────────────────────────────────────────────

class BaseAgent:
    """Abstract-like base agent (without ABC)."""

    def __init__(self, name: str, model: LLMModel):
        self.name = name
        self.model = model
        self._history: list[dict] = []

    def run(self, task: str) -> str:
        result = self._execute(task)
        self._history.append({"task": task, "result": result})
        return result

    def _execute(self, task: str) -> str:
        raise NotImplementedError(f"{type(self).__name__} must implement _execute()")

    def history(self) -> list[dict]:
        return self._history.copy()

    def __repr__(self) -> str:
        return f"{type(self).__name__}(name={self.name!r}, model={self.model.name!r})"


class ResearchAgent(BaseAgent):
    def __init__(self, name: str, model: LLMModel, search_depth: int = 3):
        super().__init__(name, model)   # MUST call super().__init__
        self.search_depth = search_depth

    def _execute(self, task: str) -> str:
        return f"[Research|depth={self.search_depth}] {task} → found 10 sources"


class CodingAgent(BaseAgent):
    def __init__(self, name: str, model: LLMModel, language: str = "python"):
        super().__init__(name, model)
        self.language = language

    def _execute(self, task: str) -> str:
        return f"[Code|{self.language}] {task} → generated function"

    def review(self, code: str) -> str:
        return f"Code review complete: {len(code.splitlines())} lines"


researcher = ResearchAgent("r1", gpt4, search_depth=5)
coder      = CodingAgent("c1", claude, language="python")

print(f"\n{researcher.run('Find asyncio docs')}")
print(f"{coder.run('Write FastAPI endpoint')}")
print(f"History: {researcher.history()}")

# isinstance — check with inheritance
print(isinstance(researcher, BaseAgent))    # True
print(isinstance(researcher, ResearchAgent))# True
print(isinstance(researcher, CodingAgent))  # False

# type() — exact class only
print(type(researcher) == BaseAgent)        # False
print(type(researcher) == ResearchAgent)    # True


# ─────────────────────────────────────────────────────────────
# 3. ABSTRACT BASE CLASSES (ABC)
# ─────────────────────────────────────────────────────────────

class LLMProvider(ABC):
    """
    Abstract base class — enforces interface.
    Cannot instantiate directly.
    """

    @abstractmethod
    def complete(self, prompt: str, **kwargs) -> str:
        """All providers MUST implement this."""
        ...

    @abstractmethod
    def stream(self, prompt: str):
        """All providers MUST implement this."""
        ...

    # Concrete method — inherited by all subclasses
    def count_tokens(self, text: str) -> int:
        return len(text.split()) * 4 // 3  # rough estimate

    # Abstract property
    @property
    @abstractmethod
    def max_tokens(self) -> int:
        ...


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key

    def complete(self, prompt: str, **kwargs) -> str:
        return f"OpenAI response to: {prompt}"

    def stream(self, prompt: str):
        for word in prompt.split():
            yield word

    @property
    def max_tokens(self) -> int:
        return 8192


class AnthropicProvider(LLMProvider):
    def complete(self, prompt: str, **kwargs) -> str:
        return f"Anthropic response to: {prompt}"

    def stream(self, prompt: str):
        yield from prompt.split()

    @property
    def max_tokens(self) -> int:
        return 200_000


# try:
#     p = LLMProvider()   # TypeError: Can't instantiate abstract class
# except TypeError as e:
#     print(e)

openai_prov = OpenAIProvider("sk-xxx")
print(f"\nOpenAI: {openai_prov.complete('Hello')}")
print(f"Tokens: {openai_prov.count_tokens('Hello world Python')}")


# ─────────────────────────────────────────────────────────────
# 4. MULTIPLE INHERITANCE + MIXINS
# ─────────────────────────────────────────────────────────────

class LogMixin:
    """Mixin — adds logging to any class."""

    def log(self, level: str, msg: str, **extra) -> None:
        print(f"  [{level}] [{type(self).__name__}] {msg} {extra}")

    def log_info(self, msg: str, **extra):
        self.log("INFO", msg, **extra)

    def log_error(self, msg: str, **extra):
        self.log("ERROR", msg, **extra)


class CacheMixin:
    """Mixin — adds in-memory caching to any class."""

    def __init__(self, *args, cache_size: int = 100, **kwargs):
        super().__init__(*args, **kwargs)   # MUST pass kwargs
        self._cache: dict = {}
        self._cache_size = cache_size

    def cache_get(self, key: str) -> Any | None:
        return self._cache.get(key)

    def cache_set(self, key: str, value: Any) -> None:
        if len(self._cache) >= self._cache_size:
            oldest = next(iter(self._cache))
            del self._cache[oldest]
        self._cache[key] = value

    def cache_clear(self) -> None:
        self._cache.clear()


class RetryMixin:
    """Mixin — adds retry logic to any class."""

    def retry(self, func, max_attempts: int = 3, *args, **kwargs):
        for attempt in range(1, max_attempts + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt == max_attempts:
                    raise
                print(f"  Retry {attempt}/{max_attempts}: {e}")


class ProductionAgent(LogMixin, CacheMixin, RetryMixin, BaseAgent):
    """
    Full-featured agent using mixins.
    MRO: ProductionAgent → LogMixin → CacheMixin → RetryMixin → BaseAgent → object
    """

    def __init__(self, name: str, model: LLMModel):
        super().__init__(name=name, model=model, cache_size=200)

    def _execute(self, task: str) -> str:
        cached = self.cache_get(task)
        if cached:
            self.log_info("Cache hit", task=task[:30])
            return cached

        self.log_info("Executing task", task=task[:30])
        result = f"[Production] {task} → completed"
        self.cache_set(task, result)
        return result


print(f"\nMRO: {[cls.__name__ for cls in ProductionAgent.__mro__]}")

agent = ProductionAgent("prod_agent", gpt4)
r1 = agent.run("Analyze Python performance")
r2 = agent.run("Analyze Python performance")  # cached
agent.log_info("Done", results=2)


# ══════════════════════════════════════════════════════════════
# PART C: DESIGN PATTERNS IN OOP
# ══════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────
# 5. SINGLETON PATTERN
# ─────────────────────────────────────────────────────────────

class Config:
    _instance: Config | None = None

    def __new__(cls) -> Config:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.model = "gpt-4"
        self.debug = False
        self._initialized = True

c1 = Config()
c2 = Config()
c1.model = "claude-3"
print(f"Singleton: {c1 is c2}")       # True
print(f"c2.model: {c2.model}")        # claude-3 (same instance!)


# ─────────────────────────────────────────────────────────────
# 6. FACTORY PATTERN
# ─────────────────────────────────────────────────────────────

class AgentFactory:
    """Creates agents by type string — decouples creation from use."""

    _creators: ClassVar[dict[str, type]] = {}

    @classmethod
    def register(cls, agent_type: str):
        """Decorator to register agent classes."""
        def decorator(agent_cls: type) -> type:
            cls._creators[agent_type] = agent_cls
            return agent_cls
        return decorator

    @classmethod
    def create(cls, agent_type: str, *args, **kwargs) -> BaseAgent:
        creator = cls._creators.get(agent_type)
        if creator is None:
            raise ValueError(f"Unknown agent type: {agent_type}")
        return creator(*args, **kwargs)

@AgentFactory.register("research")
class FactoryResearcher(BaseAgent):
    def _execute(self, task): return f"Research: {task}"

@AgentFactory.register("coding")
class FactoryCoder(BaseAgent):
    def _execute(self, task): return f"Code: {task}"


agent = AgentFactory.create("research", "r2", gpt4)
print(f"\nFactory created: {agent.run('Find Python docs')}")


# ─────────────────────────────────────────────────────────────
# 7. REPOSITORY PATTERN (common in FastAPI/backend)
# ─────────────────────────────────────────────────────────────

from dataclasses import dataclass, field

@dataclass
class User:
    id: int
    email: str
    role: str = "user"
    is_active: bool = True


class UserRepository:
    """Abstracts data access layer — easy to swap DB backend."""

    def __init__(self):
        self._store: dict[int, User] = {}

    def save(self, user: User) -> User:
        self._store[user.id] = user
        return user

    def find_by_id(self, user_id: int) -> User | None:
        return self._store.get(user_id)

    def find_by_email(self, email: str) -> User | None:
        return next((u for u in self._store.values() if u.email == email), None)

    def find_all(self, *, active_only: bool = False) -> list[User]:
        users = list(self._store.values())
        if active_only:
            users = [u for u in users if u.is_active]
        return users

    def delete(self, user_id: int) -> bool:
        if user_id in self._store:
            del self._store[user_id]
            return True
        return False


repo = UserRepository()
repo.save(User(1, "alice@example.com", "admin"))
repo.save(User(2, "bob@example.com", "user"))

user = repo.find_by_email("alice@example.com")
print(f"\nFound user: {user}")
print(f"All active: {repo.find_all(active_only=True)}")


# ─────────────────────────────────────────────────────────────
# INTERVIEW QUESTIONS
# ─────────────────────────────────────────────────────────────
"""
Q: What's the difference between @classmethod and @staticmethod?
A: @classmethod receives the class (cls) as first arg — can create instances,
   access class variables, be inherited with proper cls binding.
   @staticmethod receives nothing — pure utility, no class/instance access.

Q: What is name mangling?
A: Double underscore prefix (__name) gets mangled to _ClassName__name.
   Prevents accidental overriding in subclasses. NOT truly private.

Q: What's the difference between __repr__ and __str__?
A: __repr__ — unambiguous, developer-facing, should be eval()-able if possible.
   __str__  — human-friendly, user-facing.
   print() uses __str__. repr() uses __repr__. REPL uses __repr__.
   If only __repr__ is defined, __str__ falls back to it.

Q: What is the MRO and why does it matter?
A: Method Resolution Order — order Python searches for methods in inheritance.
   Computed by C3 linearization algorithm.
   Prevents issues in multiple/diamond inheritance.
   Check with: MyClass.__mro__ or inspect.getmro(MyClass).

Q: What are mixins?
A: Small classes with specific functionality meant to be "mixed in" via
   multiple inheritance. They don't stand alone (no meaningful __init__).
   Must use super() and **kwargs for cooperative inheritance.
   Examples: LogMixin, CacheMixin, SerializeMixin.
"""
