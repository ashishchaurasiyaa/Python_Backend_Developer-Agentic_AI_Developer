"""
╔══════════════════════════════════════════════════════════════════════════════╗
║   PYTHON COMPLETE THEORY — File 08                                           ║
║   Topic: Design Patterns (Creational, Structural, Behavioral)                ║
║   Format: WHAT → WHY → HOW → REAL LIFE → PRODUCTION CODE → Q&A              ║
╚══════════════════════════════════════════════════════════════════════════════╝

Topics Covered:

CREATIONAL (how objects are created):
  A. Singleton   — one instance only
  B. Factory     — create objects without specifying exact class
  C. Builder     — step-by-step construction of complex objects

STRUCTURAL (how objects are composed):
  D. Adapter     — make incompatible interfaces work together
  E. Decorator   — add behavior without modifying class
  F. Proxy       — control access to another object

BEHAVIORAL (how objects communicate):
  G. Strategy    — swap algorithms at runtime
  H. Observer    — event notification (pub/sub)
  I. Command     — encapsulate actions as objects (undo/redo)
  J. Chain of Responsibility — pipeline of handlers
"""

from __future__ import annotations
from typing import Protocol, Callable, Any
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import threading
import time


# ══════════════════════════════════════════════════════════════════════════════
# PATTERN A: SINGLETON
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS SINGLETON?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Ensures a class has ONLY ONE INSTANCE and provides a GLOBAL ACCESS POINT to it.

WHY?
  Some resources must be shared and unique:
  - Database connection pool (one pool for all)
  - Application configuration (one config throughout app)
  - Logger (one logger for whole application)
  - Rate limiter (one per API endpoint)

  Creating multiple instances would:
  - Waste resources (multiple DB pools)
  - Cause inconsistency (different configs)
  - Break state (multiple rate limiters not aware of each other)

HOW (Thread-safe Metaclass approach):
  class SingletonMeta(type):
      _instances = {}
      _lock = threading.Lock()

      def __call__(cls, *args, **kwargs):
          with cls._lock:       # thread-safe
              if cls not in cls._instances:
                  cls._instances[cls] = super().__call__(*args, **kwargs)
          return cls._instances[cls]

  class Config(metaclass=SingletonMeta):
      pass

OTHER APPROACHES:
  1. Module-level variable (simplest in Python — modules are singletons!)
  2. __new__ override
  3. Class decorator
  4. Metaclass (most robust, thread-safe)

REAL LIFE ANALOGY:
  Singleton = President of a country:
  Only ONE president at a time. Everyone refers to THE SAME president.
  Creating a "new President()" doesn't create a second president —
  it returns THE EXISTING one.

DISADVANTAGES:
  - Global state → hard to test (tests affect each other)
  - Hidden dependency (code secretly depends on the singleton)
  - Thread safety needed in concurrent code
  - Considered an anti-pattern when overused
"""

print("=== SINGLETON ===")


class SingletonMeta(type):
    """Thread-safe Singleton metaclass."""
    _instances: dict = {}
    _lock: threading.Lock = threading.Lock()

    def __call__(cls, *args, **kwargs):
        with cls._lock:
            if cls not in cls._instances:
                instance = super().__call__(*args, **kwargs)
                cls._instances[cls] = instance
        return cls._instances[cls]


class AppConfig(metaclass=SingletonMeta):
    """Application configuration — only one should exist."""

    def __init__(self, env: str = "production", debug: bool = False):
        self.env = env
        self.debug = debug
        self.settings: dict = {
            "max_tokens": 4096,
            "default_model": "gpt-4",
            "rate_limit": 100,
        }
        print(f"  [AppConfig] Initialized with env={env}")

    def get(self, key: str, default: Any = None) -> Any:
        return self.settings.get(key, default)


# Test singleton behavior
cfg1 = AppConfig("development", debug=True)
cfg2 = AppConfig("production")   # __init__ NOT called again — same object returned!
cfg3 = AppConfig()

print(f"cfg1 is cfg2: {cfg1 is cfg2}")  # True — same instance
print(f"cfg1 is cfg3: {cfg1 is cfg3}")  # True — same instance
print(f"cfg2.env: {cfg2.env}")          # "development" — first init wins


"""
Q&A — Singleton

Q1: Is Singleton bad practice?
A:  Singleton is often called an "anti-pattern" because:
    - It introduces global mutable state → makes testing hard
    - Hidden dependencies (functions secretly use the singleton)
    - Hard to replace with different implementation

    When it's fine: Logger, Config, AppContext, DB connection pool.
    Prefer: Dependency Injection (pass config explicitly) when testability matters.

Q2: How is a Python module similar to Singleton?
A:  Python modules are cached after first import — always the same object.
    import config; x = config.SETTING
    Everyone who imports config gets THE SAME module object.
    This is the simplest Python Singleton pattern.
"""


# ══════════════════════════════════════════════════════════════════════════════
# PATTERN B: FACTORY
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS FACTORY PATTERN?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Factory: a METHOD or CLASS that creates objects without specifying the exact class.
Client asks for "a dog" — factory decides which Dog subclass to create.

WHY?
  Problem:
    if model == "gpt-4":
        agent = GPT4Agent(...)
    elif model == "claude":
        agent = ClaudeAgent(...)
    elif model == "llama":
        agent = LlamaAgent(...)
    # This if/elif grows EVERY time you add a new model → not extensible!

  Solution: Factory pattern centralizes object creation.
  Adding new model = add one line to registry. NO touching existing code.

TYPES:
  1. Factory Method: method in class that creates instances
  2. Abstract Factory: interface for creating families of related objects
  3. Simple Factory: a function or class with create() method + registry

HOW (Registration pattern):
  class AgentFactory:
      _registry = {}

      @classmethod
      def register(cls, name):           # decorator
          def decorator(agent_class):
              cls._registry[name] = agent_class
              return agent_class
          return decorator

      @classmethod
      def create(cls, name, **kwargs):
          return cls._registry[name](**kwargs)

  @AgentFactory.register("gpt4")
  class GPT4Agent(BaseAgent): ...

REAL LIFE ANALOGY:
  Factory = Car dealership:
  You say "I want a sedan". Dealership decides which exact model.
  You don't assemble the car — the factory does.
  New car type? Update the factory, not the customer.

OPEN/CLOSED PRINCIPLE:
  Open for extension (add new agents), Closed for modification (don't change factory core).
"""

print("\n=== FACTORY ===")


class BaseAgent(ABC):
    """Abstract base for all agents."""

    def __init__(self, model: str, system_prompt: str = ""):
        self.model = model
        self.system_prompt = system_prompt

    @abstractmethod
    def run(self, task: str) -> str: ...

    @abstractmethod
    def get_capabilities(self) -> list[str]: ...

    def __repr__(self) -> str:
        return f"{type(self).__name__}(model={self.model!r})"


class AgentFactory:
    """Registration-based factory for AI agents."""
    _registry: dict[str, type[BaseAgent]] = {}

    @classmethod
    def register(cls, name: str) -> Callable:
        """Decorator: register an agent class under a name."""
        def decorator(agent_class: type[BaseAgent]) -> type[BaseAgent]:
            cls._registry[name] = agent_class
            print(f"  [Factory] Registered: {name!r} → {agent_class.__name__}")
            return agent_class
        return decorator

    @classmethod
    def create(cls, name: str, **kwargs) -> BaseAgent:
        """Create agent by registered name."""
        if name not in cls._registry:
            available = list(cls._registry.keys())
            raise ValueError(f"Unknown agent {name!r}. Available: {available}")
        return cls._registry[name](**kwargs)

    @classmethod
    def available(cls) -> list[str]:
        return list(cls._registry.keys())


@AgentFactory.register("research")
class ResearchAgent(BaseAgent):
    def run(self, task: str) -> str:
        return f"[Research] Searching for: {task}"

    def get_capabilities(self) -> list[str]:
        return ["web_search", "document_analysis", "summarization"]


@AgentFactory.register("coding")
class CodingAgent(BaseAgent):
    def run(self, task: str) -> str:
        return f"[Coding] Implementing: {task}"

    def get_capabilities(self) -> list[str]:
        return ["code_generation", "debugging", "code_review"]


@AgentFactory.register("writing")
class WritingAgent(BaseAgent):
    def run(self, task: str) -> str:
        return f"[Writing] Composing: {task}"

    def get_capabilities(self) -> list[str]:
        return ["copywriting", "editing", "translation"]


print(f"Available agents: {AgentFactory.available()}")

agent = AgentFactory.create("research", model="gpt-4", system_prompt="You are a researcher.")
print(f"Created: {agent}")
print(f"Result: {agent.run('Python async patterns')}")
print(f"Capabilities: {agent.get_capabilities()}")


# ══════════════════════════════════════════════════════════════════════════════
# PATTERN C: BUILDER
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS BUILDER PATTERN?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Builder: Construct a COMPLEX OBJECT step by step, separating construction from representation.

WHY?
  Problem:
    config = LLMRequest("gpt-4", messages, 0.7, 2048, True, ["stop"], None, ...)
    # 12 args — unreadable! Which is temperature? Which is max_tokens?

  Problem with keyword args: too many optional combinations
    LLMRequest(model=..., messages=..., temperature=..., max_tokens=..., stop=..., tools=...)

  Solution: Fluent builder interface
    config = (LLMRequestBuilder("gpt-4")
              .with_temperature(0.7)
              .with_max_tokens(2048)
              .with_streaming(True)
              .with_tool("web_search")
              .build())

WHY FLUENT BUILDER?
  - Self-documenting: each .with_X() is clear what it sets
  - Optional: only set what you need
  - Readable: reads like English
  - Validation: can validate in .build() before creating object

HOW:
  class Builder:
      def __init__(self): ...
      def with_x(self, value) -> Self:
          self._x = value
          return self      # ← return self for method chaining!
      def build(self) -> Product:
          # validate + create product
          return Product(self._x, self._y, ...)

REAL LIFE ANALOGY:
  Builder = Custom pizza order:
  Step 1: choose_base("thin crust")
  Step 2: add_sauce("marinara")
  Step 3: add_topping("cheese")
  Step 4: add_topping("pepperoni")
  Step 5: bake()   → creates the final pizza
  Each step is optional, readable, composable.
"""

print("\n=== BUILDER ===")


@dataclass
class LLMRequest:
    """The product — complex object built by the Builder."""
    model: str
    messages: list[dict]
    temperature: float = 0.7
    max_tokens: int = 2048
    stream: bool = False
    stop_sequences: list[str] = field(default_factory=list)
    tools: list[dict] = field(default_factory=list)
    response_format: dict | None = None
    presence_penalty: float = 0.0
    frequency_penalty: float = 0.0


class LLMRequestBuilder:
    """Fluent builder for LLMRequest — readable step-by-step construction."""

    def __init__(self, model: str = "gpt-4"):
        self._model = model
        self._messages: list[dict] = []
        self._temperature = 0.7
        self._max_tokens = 2048
        self._stream = False
        self._stop_sequences: list[str] = []
        self._tools: list[dict] = []
        self._response_format: dict | None = None
        self._presence_penalty = 0.0
        self._frequency_penalty = 0.0

    def with_model(self, model: str) -> LLMRequestBuilder:
        self._model = model
        return self

    def with_system(self, content: str) -> LLMRequestBuilder:
        self._messages.insert(0, {"role": "system", "content": content})
        return self

    def with_user_message(self, content: str) -> LLMRequestBuilder:
        self._messages.append({"role": "user", "content": content})
        return self

    def with_temperature(self, temperature: float) -> LLMRequestBuilder:
        if not 0.0 <= temperature <= 2.0:
            raise ValueError(f"Temperature must be 0.0-2.0, got {temperature}")
        self._temperature = temperature
        return self

    def with_max_tokens(self, max_tokens: int) -> LLMRequestBuilder:
        if max_tokens < 1:
            raise ValueError(f"max_tokens must be >= 1")
        self._max_tokens = max_tokens
        return self

    def with_streaming(self, stream: bool = True) -> LLMRequestBuilder:
        self._stream = stream
        return self

    def with_stop(self, *sequences: str) -> LLMRequestBuilder:
        self._stop_sequences.extend(sequences)
        return self

    def with_tool(self, name: str, description: str = "") -> LLMRequestBuilder:
        self._tools.append({"name": name, "description": description})
        return self

    def as_json(self) -> LLMRequestBuilder:
        self._response_format = {"type": "json_object"}
        return self

    def build(self) -> LLMRequest:
        """Validate and create the product."""
        if not self._messages:
            raise ValueError("Request must have at least one message")
        if not self._model:
            raise ValueError("Model is required")
        return LLMRequest(
            model=self._model,
            messages=self._messages.copy(),
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            stream=self._stream,
            stop_sequences=self._stop_sequences.copy(),
            tools=self._tools.copy(),
            response_format=self._response_format,
            presence_penalty=self._presence_penalty,
            frequency_penalty=self._frequency_penalty,
        )


# Fluent construction — reads like configuration
request = (
    LLMRequestBuilder("gpt-4")
    .with_system("You are a senior Python developer.")
    .with_user_message("Write async code to fetch 10 URLs concurrently.")
    .with_temperature(0.2)          # precise, not creative
    .with_max_tokens(4096)
    .with_streaming(True)
    .with_tool("code_executor", "Run Python code")
    .with_stop("```", "---END---")
    .as_json()
    .build()
)

print(f"Built request: model={request.model}, temp={request.temperature}")
print(f"  Messages: {len(request.messages)}")
print(f"  Stream: {request.stream}")
print(f"  Tools: {request.tools}")
print(f"  Stop: {request.stop_sequences}")


# ══════════════════════════════════════════════════════════════════════════════
# PATTERN D: ADAPTER
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS ADAPTER PATTERN?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Adapter: makes an INCOMPATIBLE INTERFACE compatible with what your code expects.
Wraps an existing class and translates method calls.

WHY?
  You have existing code that uses interface A.
  New library only has interface B.
  Don't want to rewrite all existing code.
  Solution: Adapter wraps B and presents interface A.

HOW:
  Client → [expects Interface A] → Adapter → [translates to Interface B] → LegacySystem

REAL LIFE ANALOGY:
  Physical power adapter:
  Your laptop needs EU plug → power adapter → US wall socket
  The adapter converts, the laptop and wall socket are unchanged.

  Audio jack adapter:
  New phone: USB-C audio → adapter → 3.5mm headphone jack
"""

print("\n=== ADAPTER ===")


class OpenAIStyle:
    """Your existing code's expected interface."""

    def chat_complete(self, messages: list[dict], model: str) -> dict:
        raise NotImplementedError


class LegacyAnthropicSDK:
    """Old-style SDK with different interface — can't modify it."""

    def complete_text(
        self,
        prompt: str,           # single string, not list of messages!
        max_tokens_to_sample: int = 1000,
        model: str = "claude-instant-1",
    ) -> dict:
        """Different method name, different signature."""
        return {
            "completion": f"[Legacy Anthropic] Response to: {prompt[:50]}",
            "stop_reason": "max_tokens",
            "model": model,
        }


class AnthropicAdapter(OpenAIStyle):
    """Adapter: wraps LegacyAnthropicSDK, presents OpenAI-style interface."""

    def __init__(self, legacy_sdk: LegacyAnthropicSDK):
        self._sdk = legacy_sdk

    def chat_complete(self, messages: list[dict], model: str = "claude-instant-1") -> dict:
        """Translate OpenAI-style call to legacy Anthropic call."""
        # Convert messages list to prompt string (legacy format)
        prompt = "\n".join(f"{m['role'].capitalize()}: {m['content']}" for m in messages)
        prompt += "\nAssistant:"

        # Call legacy SDK with translated args
        legacy_response = self._sdk.complete_text(
            prompt=prompt,
            max_tokens_to_sample=2048,
            model=model,
        )

        # Translate legacy response to OpenAI-style response
        return {
            "choices": [{"message": {"role": "assistant", "content": legacy_response["completion"]}}],
            "model": legacy_response["model"],
            "usage": {"total_tokens": len(prompt.split()) * 2},
        }


def call_llm(client: OpenAIStyle, messages: list[dict]) -> str:
    """Your existing code — expects OpenAI-style interface."""
    response = client.chat_complete(messages, model="claude-instant-1")
    return response["choices"][0]["message"]["content"]


# Works transparently — call_llm doesn't know it's using legacy SDK
legacy_sdk = LegacyAnthropicSDK()
adapter = AnthropicAdapter(legacy_sdk)

messages = [
    {"role": "system", "content": "You are helpful."},
    {"role": "user", "content": "What is Python?"},
]

result = call_llm(adapter, messages)
print(f"Adapter result: {result}")


# ══════════════════════════════════════════════════════════════════════════════
# PATTERN E: DECORATOR (Pattern — not the Python @decorator syntax)
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS DECORATOR PATTERN?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Decorator Pattern (GoF): WRAP an object to add new behavior without modifying its class.
Implements the same interface as the wrapped object.

NOTE: Python's @decorator syntax is a language feature INSPIRED by this pattern,
but they are different things!
  @decorator syntax = function wrapping
  Decorator Pattern = object wrapping with same interface

WHY?
  - Add logging without modifying the original class
  - Add caching without modifying the original class
  - Compose multiple behaviors freely (LoggingDecorator + CachingDecorator)
  - OCP: Open for extension, Closed for modification

HOW:
  Component interface → ConcreteComponent
                      → Decorator (wraps component, same interface)
                          → LoggingDecorator (extends Decorator)
                          → CachingDecorator (extends Decorator)

  You can STACK decorators: CachingDecorator(LoggingDecorator(component))

REAL LIFE ANALOGY:
  Decorator = Coffee toppings at Starbucks:
  Base: Coffee (component)
  + Milk:  MilkDecorator (same interface as coffee, adds milk)
  + Sugar: SugarDecorator (same interface, adds sugar)
  Final: SugarDecorator(MilkDecorator(Coffee))
  Still tastes like coffee — just enhanced.
"""

print("\n=== DECORATOR PATTERN ===")


class LLMService(Protocol):
    """The interface — component and decorator both implement this."""
    def complete(self, prompt: str) -> str: ...


class OpenAIService:
    """Concrete component — the original."""

    def __init__(self, model: str = "gpt-4"):
        self.model = model
        self._call_count = 0

    def complete(self, prompt: str) -> str:
        self._call_count += 1
        return f"[{self.model}] Response to: {prompt[:40]}"


class LoggingDecorator:
    """Adds logging around any LLMService — same interface."""

    def __init__(self, service: LLMService):
        self._service = service   # wrapped service

    def complete(self, prompt: str) -> str:
        print(f"  [LOG] Calling service with: {prompt[:30]}...")
        start = time.perf_counter()
        result = self._service.complete(prompt)  # delegate to wrapped service
        elapsed = (time.perf_counter() - start) * 1000
        print(f"  [LOG] Completed in {elapsed:.2f}ms: {result[:40]}")
        return result


class CachingDecorator:
    """Adds caching around any LLMService — same interface."""

    def __init__(self, service: LLMService, max_size: int = 100):
        self._service = service
        self._cache: dict[str, str] = {}
        self._max_size = max_size
        self._hits = 0
        self._misses = 0

    def complete(self, prompt: str) -> str:
        key = hash(prompt)
        if key in self._cache:
            self._hits += 1
            print(f"  [CACHE] HIT for: {prompt[:30]}...")
            return self._cache[key]

        self._misses += 1
        result = self._service.complete(prompt)
        if len(self._cache) < self._max_size:
            self._cache[key] = result
        return result

    @property
    def stats(self) -> dict:
        return {"hits": self._hits, "misses": self._misses}


class RetryDecorator:
    """Adds retry logic around any LLMService."""

    def __init__(self, service: LLMService, max_retries: int = 3, delay: float = 1.0):
        self._service = service
        self._max_retries = max_retries
        self._delay = delay

    def complete(self, prompt: str) -> str:
        for attempt in range(self._max_retries):
            try:
                return self._service.complete(prompt)
            except Exception as e:
                if attempt == self._max_retries - 1:
                    raise
                print(f"  [RETRY] Attempt {attempt+1} failed: {e}")
        return ""


# Stack decorators — composable!
service = OpenAIService("gpt-4")
with_logging = LoggingDecorator(service)
with_cache   = CachingDecorator(with_logging)  # cache → logging → service
# with_retry = RetryDecorator(with_cache)      # retry → cache → logging → service

print(f"First call:")
r1 = with_cache.complete("What is Python?")
print(f"Second call (same prompt):")
r2 = with_cache.complete("What is Python?")    # hits cache
print(f"Third call (different prompt):")
r3 = with_cache.complete("Explain async/await")
print(f"Cache stats: {with_cache.stats}")


# ══════════════════════════════════════════════════════════════════════════════
# PATTERN F: PROXY
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS PROXY PATTERN?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Proxy: provides a SUBSTITUTE/PLACEHOLDER for another object.
Controls access to the original object.

TYPES:
  Virtual Proxy:  Delays expensive creation until actually needed (lazy init)
  Protection Proxy: Controls access based on permissions
  Remote Proxy:   Represents an object in another process/machine
  Caching Proxy:  Caches results (similar to Decorator with caching)

WHY?
  Lazy initialization: don't load a 100MB model until someone actually calls it
  Access control: only admin can call certain methods
  Logging: transparently log all method calls

HOW:
  Proxy implements same interface as real subject.
  Client talks to Proxy (thinking it's the real thing).
  Proxy decides when/how to delegate to real subject.

REAL LIFE ANALOGY:
  Proxy = PA (Personal Assistant) to a CEO:
  You don't call CEO directly — you call PA.
  PA decides: can I handle this? Or does CEO need to deal with it?
  PA shields CEO from unnecessary work (lazy loading, access control).
"""

print("\n=== PROXY ===")


class ExpensiveLLMModel:
    """Expensive to initialize — takes time and memory."""

    def __init__(self, model_path: str):
        print(f"  [Model] Loading model from {model_path} (expensive!)...")
        time.sleep(0.2)  # simulate model loading
        self.model_path = model_path
        self._loaded = True
        print(f"  [Model] Model loaded!")

    def predict(self, text: str) -> str:
        return f"[{self.model_path}] Prediction for: {text}"

    def embed(self, text: str) -> list[float]:
        return [0.1, 0.2, 0.3, 0.4]


class LazyModelProxy:
    """Virtual proxy — delays model loading until first use."""

    def __init__(self, model_path: str):
        self._model_path = model_path
        self._model: ExpensiveLLMModel | None = None
        print(f"  [Proxy] Created (model NOT loaded yet)")

    def _ensure_loaded(self) -> ExpensiveLLMModel:
        if self._model is None:
            self._model = ExpensiveLLMModel(self._model_path)
        return self._model

    def predict(self, text: str) -> str:
        """Delegate to real model — loads on first call."""
        return self._ensure_loaded().predict(text)

    def embed(self, text: str) -> list[float]:
        """Delegate to real model."""
        return self._ensure_loaded().embed(text)


print(f"Creating proxy (no loading yet):")
proxy = LazyModelProxy("./models/llama-3-8b")

print(f"\nFirst prediction (triggers loading):")
result = proxy.predict("What is Python?")  # NOW model loads
print(f"Result: {result}")

print(f"\nSecond prediction (model already loaded):")
result2 = proxy.predict("What is async?")  # no loading — reuses
print(f"Result: {result2}")


# ══════════════════════════════════════════════════════════════════════════════
# PATTERN G: STRATEGY
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS STRATEGY PATTERN?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Strategy: define a FAMILY OF ALGORITHMS, encapsulate each one, make them
INTERCHANGEABLE at runtime.

WHY?
  Problem: Same task, multiple algorithms, and the choice changes at runtime.
  if complexity == "low": use_basic_algorithm()
  elif complexity == "medium": use_intermediate_algorithm()
  elif complexity == "high": use_advanced_algorithm()
  → Massive if/elif that grows with each new algorithm.

  Strategy: extract each algorithm into its own class.
  Client picks strategy at runtime without knowing the internal implementation.

HOW:
  Strategy interface → ConcreteStrategyA
                    → ConcreteStrategyB
                    → ConcreteStrategyC

  Context uses whichever strategy is set.

REAL LIFE ANALOGY:
  GPS navigation = Strategy pattern:
  "Route from A to B" — same goal, multiple strategies:
  - FastestRoute strategy (uses highways)
  - ShortestRoute strategy (fewest kilometers)
  - ScenicRoute strategy (most beautiful)
  You pick the strategy — GPS executes it.
"""

print("\n=== STRATEGY ===")


class RoutingStrategy(Protocol):
    """Strategy interface."""
    def route(self, task: str, available_models: list[str]) -> str: ...


class CheapestModelStrategy:
    """Always routes to cheapest model."""
    COSTS = {"gpt-3.5-turbo": 0.001, "claude-instant": 0.002, "gpt-4": 0.03, "claude-3-opus": 0.04}

    def route(self, task: str, available_models: list[str]) -> str:
        cheapest = min(available_models, key=lambda m: self.COSTS.get(m, 999))
        print(f"  [Cheapest] Selected: {cheapest}")
        return cheapest


class FastestModelStrategy:
    """Routes to fastest model (lowest latency)."""
    LATENCY = {"gpt-3.5-turbo": 300, "claude-instant": 400, "gpt-4": 1200, "claude-3-opus": 1800}

    def route(self, task: str, available_models: list[str]) -> str:
        fastest = min(available_models, key=lambda m: self.LATENCY.get(m, 9999))
        print(f"  [Fastest] Selected: {fastest}")
        return fastest


class TaskComplexityStrategy:
    """Routes based on task complexity."""
    SIMPLE_TASKS = {"summarize", "translate", "classify"}

    def route(self, task: str, available_models: list[str]) -> str:
        is_complex = len(task.split()) > 50 or any(kw in task.lower() for kw in ["analyze", "research", "design"])
        model = "gpt-4" if is_complex and "gpt-4" in available_models else "gpt-3.5-turbo"
        print(f"  [Complexity] Task complex: {is_complex}, selected: {model}")
        return model


class ModelRouter:
    """Context — uses whichever strategy is set."""

    def __init__(self, strategy: RoutingStrategy):
        self._strategy = strategy
        self._available = ["gpt-3.5-turbo", "gpt-4", "claude-instant", "claude-3-opus"]

    def set_strategy(self, strategy: RoutingStrategy) -> None:
        """Change strategy at runtime."""
        self._strategy = strategy

    def route_task(self, task: str) -> str:
        return self._strategy.route(task, self._available)


router = ModelRouter(CheapestModelStrategy())

print("Using CheapestStrategy:")
model = router.route_task("Summarize this text")

print("Switching to FastestStrategy:")
router.set_strategy(FastestModelStrategy())
model = router.route_task("Summarize this text")

print("Switching to ComplexityStrategy:")
router.set_strategy(TaskComplexityStrategy())
model = router.route_task("Analyze and research the entire history of Python async patterns in detail")


# ══════════════════════════════════════════════════════════════════════════════
# PATTERN H: OBSERVER
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS OBSERVER PATTERN?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Observer (also called Pub/Sub): Define a one-to-many dependency between objects.
When subject changes, ALL registered observers are notified automatically.

WHY?
  Problem: Many parts of a system need to react to events.
  Without Observer: event source calls each listener directly — tight coupling!
  With Observer: event source doesn't know who's listening — loose coupling!

HOW:
  Subject/Publisher: maintains list of observers, notifies them on change
  Observer/Subscriber: registers with subject, handles notification

REAL LIFE ANALOGY:
  Observer = Newsletter subscription:
  Publisher (company): has a mailing list of subscribers
  When new blog post: notifies ALL subscribers automatically
  Subscribers don't poll — they get PUSHED notifications
  Subscribers can subscribe or unsubscribe anytime
"""

print("\n=== OBSERVER ===")

from typing import TypeVar
EventType = TypeVar("EventType")


class EventBus:
    """Simple in-process event bus / pub-sub system."""

    def __init__(self):
        self._handlers: dict[str, list[Callable]] = {}

    def on(self, event: str, handler: Callable) -> None:
        """Subscribe handler to event."""
        if event not in self._handlers:
            self._handlers[event] = []
        self._handlers[event].append(handler)
        print(f"  [EventBus] Subscribed {handler.__name__!r} to {event!r}")

    def off(self, event: str, handler: Callable) -> None:
        """Unsubscribe handler from event."""
        if event in self._handlers:
            self._handlers[event] = [h for h in self._handlers[event] if h is not handler]

    def emit(self, event: str, **payload) -> None:
        """Publish event — notify all subscribers."""
        handlers = self._handlers.get(event, [])
        print(f"  [EventBus] emit {event!r} → {len(handlers)} handler(s)")
        for handler in handlers:
            handler(**payload)


# Create bus
bus = EventBus()

# Multiple handlers for the same event
def on_agent_start(agent_id: str, model: str, **kwargs) -> None:
    print(f"    → Logger: Agent {agent_id!r} started with {model}")

def on_agent_start_metrics(agent_id: str, **kwargs) -> None:
    print(f"    → Metrics: Recording start for agent {agent_id!r}")

def on_token_used(agent_id: str, tokens: int, **kwargs) -> None:
    print(f"    → Budget: Deducting {tokens} tokens for {agent_id!r}")

def on_token_used_rate_limit(agent_id: str, tokens: int, **kwargs) -> None:
    print(f"    → RateLimit: Checking rate limit for {agent_id!r} ({tokens} tokens)")

bus.on("agent.start",  on_agent_start)
bus.on("agent.start",  on_agent_start_metrics)
bus.on("token.used",   on_token_used)
bus.on("token.used",   on_token_used_rate_limit)

print("\nEmitting events:")
bus.emit("agent.start",  agent_id="agent_001", model="gpt-4", task="research")
bus.emit("token.used",   agent_id="agent_001", tokens=450)
bus.emit("agent.finish", agent_id="agent_001", result="success")  # no handlers — ignored


# ══════════════════════════════════════════════════════════════════════════════
# PATTERN I: COMMAND
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS COMMAND PATTERN?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Command: encapsulate an ACTION as an OBJECT.
Allows: queuing actions, undo/redo, action history, logging, delayed execution.

WHY?
  Plain function call: action happens immediately, can't be undone, queued, or stored.
  Command object: action can be stored, queued, undone, redone, logged.

HOW:
  Command interface: execute(), undo()
  ConcreteCommand: knows HOW to execute and undo a specific action
  Invoker: calls execute() — doesn't know WHAT the command does
  Receiver: the object the command operates on

REAL LIFE ANALOGY:
  Command = Restaurant order slip:
  Waiter writes your order on a slip (command object).
  Gives it to kitchen (invoker).
  Kitchen executes when ready.
  If you cancel: waiter brings back the slip (undo).
  Slips can be queued, replayed, logged.
"""

print("\n=== COMMAND ===")


class ConversationHistory:
    """Receiver — the object commands operate on."""

    def __init__(self):
        self.messages: list[dict] = []

    def add(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})

    def remove_last(self) -> dict | None:
        return self.messages.pop() if self.messages else None

    def show(self) -> None:
        for m in self.messages:
            print(f"    [{m['role']}]: {m['content'][:50]}")


class Command(ABC):
    @abstractmethod
    def execute(self) -> None: ...
    @abstractmethod
    def undo(self) -> None: ...


class AddMessageCommand(Command):
    """Command: add a message to conversation."""

    def __init__(self, history: ConversationHistory, role: str, content: str):
        self._history = history
        self._role = role
        self._content = content

    def execute(self) -> None:
        self._history.add(self._role, self._content)
        print(f"  [CMD] Added [{self._role}]: {self._content[:40]}")

    def undo(self) -> None:
        removed = self._history.remove_last()
        if removed:
            print(f"  [UNDO] Removed [{removed['role']}]: {removed['content'][:40]}")


class CommandInvoker:
    """Invoker — executes commands and maintains undo history."""

    def __init__(self):
        self._history: list[Command] = []

    def execute(self, command: Command) -> None:
        command.execute()
        self._history.append(command)

    def undo(self) -> None:
        if self._history:
            cmd = self._history.pop()
            cmd.undo()
        else:
            print("  Nothing to undo")

    def undo_all(self) -> None:
        while self._history:
            self.undo()


# Usage
history = ConversationHistory()
invoker = CommandInvoker()

invoker.execute(AddMessageCommand(history, "system", "You are a helpful Python expert."))
invoker.execute(AddMessageCommand(history, "user", "What is Python?"))
invoker.execute(AddMessageCommand(history, "assistant", "Python is a programming language."))
invoker.execute(AddMessageCommand(history, "user", "Oops, wrong message"))

print("\nHistory after 4 commands:")
history.show()

print("\nUndo last command:")
invoker.undo()

print("\nHistory after undo:")
history.show()


# ══════════════════════════════════════════════════════════════════════════════
# PATTERN J: CHAIN OF RESPONSIBILITY
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS CHAIN OF RESPONSIBILITY?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Chain of Responsibility: Pass a request along a CHAIN OF HANDLERS.
Each handler either HANDLES the request or PASSES it to the next handler.

WHY?
  Multiple checks/transformations need to happen in sequence.
  Each check is independent — can be added/removed/reordered.
  Client doesn't need to know which handler will ultimately handle the request.

EXAMPLES:
  - Prompt validation pipeline (safety check → length check → format check)
  - Middleware (auth → rate limit → logging → handler)
  - HTTP request handlers (Django/Flask middleware)
  - Exception handling chain
  - Support ticket escalation (L1 → L2 → L3 support)

HOW:
  Handler: handle(request) → process OR forward to next handler
  Chain: Handler1 → Handler2 → Handler3 → null (end)

REAL LIFE ANALOGY:
  Customer service call:
  You call support → automated system (handles? no → passes)
  → L1 support agent (handles? no → passes)
  → L2 technical specialist (handles? yes → resolved)
"""

print("\n=== CHAIN OF RESPONSIBILITY ===")


@dataclass
class PromptRequest:
    """Request object passed through the chain."""
    prompt: str
    user_id: str
    model: str = "gpt-4"
    approved: bool = False
    rejection_reason: str = ""
    modified_prompt: str = ""

    def __post_init__(self):
        self.modified_prompt = self.prompt


class PromptHandler(ABC):
    """Handler base class."""

    def __init__(self):
        self._next: PromptHandler | None = None

    def set_next(self, handler: PromptHandler) -> PromptHandler:
        self._next = handler
        return handler  # return handler so we can chain: h1.set_next(h2).set_next(h3)

    @abstractmethod
    def handle(self, request: PromptRequest) -> PromptRequest: ...

    def pass_to_next(self, request: PromptRequest) -> PromptRequest:
        if self._next:
            return self._next.handle(request)
        request.approved = True
        return request


class SafetyCheckHandler(PromptHandler):
    """Checks for harmful content."""
    BLOCKED = ["hack", "exploit", "malware", "illegal"]

    def handle(self, request: PromptRequest) -> PromptRequest:
        for word in self.BLOCKED:
            if word in request.prompt.lower():
                request.rejection_reason = f"Safety violation: '{word}'"
                print(f"  [Safety] ❌ BLOCKED: {request.rejection_reason}")
                return request
        print(f"  [Safety] ✅ Passed")
        return self.pass_to_next(request)


class LengthCheckHandler(PromptHandler):
    """Enforces prompt length limits."""

    def __init__(self, max_tokens: int = 1000):
        super().__init__()
        self.max_tokens = max_tokens

    def handle(self, request: PromptRequest) -> PromptRequest:
        token_count = len(request.prompt.split()) * 4 // 3
        if token_count > self.max_tokens:
            truncated = " ".join(request.prompt.split()[:self.max_tokens * 3 // 4])
            request.modified_prompt = truncated
            print(f"  [Length] ⚠️  Truncated ({token_count} > {self.max_tokens} tokens)")
        else:
            print(f"  [Length] ✅ OK ({token_count} tokens)")
        return self.pass_to_next(request)


class PIIRedactionHandler(PromptHandler):
    """Redacts personal information."""
    import re as _re
    EMAIL_PATTERN = _re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
    PHONE_PATTERN = _re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b')

    def handle(self, request: PromptRequest) -> PromptRequest:
        original = request.modified_prompt
        redacted = self.EMAIL_PATTERN.sub("[EMAIL]", request.modified_prompt)
        redacted = self.PHONE_PATTERN.sub("[PHONE]", redacted)
        if redacted != original:
            request.modified_prompt = redacted
            print(f"  [PII]    ⚠️  Redacted PII from prompt")
        else:
            print(f"  [PII]    ✅ No PII found")
        return self.pass_to_next(request)


class RateLimitHandler(PromptHandler):
    """Rate limiting per user."""
    _calls: dict[str, int] = {}
    LIMIT = 5

    def handle(self, request: PromptRequest) -> PromptRequest:
        count = self._calls.get(request.user_id, 0) + 1
        self._calls[request.user_id] = count
        if count > self.LIMIT:
            request.rejection_reason = f"Rate limit exceeded ({count}/{self.LIMIT})"
            print(f"  [RateLimit] ❌ BLOCKED: {request.rejection_reason}")
            return request
        print(f"  [RateLimit] ✅ Call {count}/{self.LIMIT}")
        return self.pass_to_next(request)


# Build the chain
safety = SafetyCheckHandler()
length = LengthCheckHandler(max_tokens=500)
pii    = PIIRedactionHandler()
rate   = RateLimitHandler()

# Chain: safety → length → pii → rate
safety.set_next(length).set_next(pii).set_next(rate)

print("Processing prompt 1 (clean):")
req1 = PromptRequest(
    prompt="Explain Python decorators with examples.",
    user_id="user_001",
)
result = safety.handle(req1)
print(f"  → Approved: {result.approved}, Reason: {result.rejection_reason or 'OK'}")

print("\nProcessing prompt 2 (with PII):")
req2 = PromptRequest(
    prompt="My email is user@example.com, phone is 555-123-4567. Help me.",
    user_id="user_002",
)
result = safety.handle(req2)
print(f"  → Modified: {result.modified_prompt}")

print("\nProcessing prompt 3 (harmful content):")
req3 = PromptRequest(
    prompt="How do I hack into a system?",
    user_id="user_003",
)
result = safety.handle(req3)
print(f"  → Approved: {result.approved}, Reason: {result.rejection_reason}")


"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Q&A — Design Patterns
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q1: What is the difference between Strategy and Template Method?
A:  Strategy: algorithm is in a SEPARATE class, swapped via composition.
              Client holds a reference to the strategy object.
    Template Method: algorithm structure is in BASE CLASS with abstract steps.
              Subclasses override specific steps (inheritance).
    Strategy is more flexible (swap at runtime), Template Method is simpler.

Q2: What is the difference between Decorator pattern and Python @decorator?
A:  GoF Decorator Pattern: OOP pattern — wraps an OBJECT of same interface.
                           Both wrapper and wrapped implement same interface.
    Python @decorator:    Language syntax — wraps a FUNCTION.
                          Does NOT require same interface — can change signature.
    They are inspired by the same idea but are different things.

Q3: When is Observer too much overhead?
A:  When event chains are too long → hard to trace execution (debug nightmare).
    When events trigger other events → infinite loops possible.
    When tight coupling is actually fine → use direct method calls instead.
    Simple rule: if only 1-2 things react to an event, direct call is cleaner.

Q4: What is the difference between Command and Strategy?
A:  Both encapsulate actions in objects, but:
    Strategy: different algorithms for the SAME goal (sort by different criteria)
              no state — fresh execution each time
    Command:  specific, one-time actions with UNDO capability
              has state (remembers what it did for undo)
              can be queued, delayed, stored in history

Q5: When should you use Builder vs just using keyword arguments?
A:  Use Builder when:
    - Many optional parameters (> 5-6) — builder reads more clearly
    - Construction has VALIDATION logic in .build()
    - Construction has multiple PHASES (e.g., different optional sections)
    - Object is immutable (builder assembles, product is frozen)
    Regular kwargs work fine for simpler cases (< 5 params, simple objects).
"""

print("\n✅ 08_Design_Patterns_Theory.py complete — all sections covered.")
