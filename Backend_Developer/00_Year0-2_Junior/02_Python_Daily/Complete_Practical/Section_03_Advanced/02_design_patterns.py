"""
╔══════════════════════════════════════════════════════════════╗
║  PYTHON COMPLETE PRACTICAL — Section 03                      ║
║  Topic: Design Patterns — Production Python                  ║
╚══════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, ClassVar, Callable, TypeVar
from dataclasses import dataclass, field
import functools
import threading

T = TypeVar("T")


# ══════════════════════════════════════════════════════════════
# CREATIONAL PATTERNS
# ══════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────
# 1. SINGLETON — one instance per application
# ─────────────────────────────────────────────────────────────

class SingletonMeta(type):
    """Thread-safe Singleton metaclass."""
    _instances: ClassVar[dict] = {}
    _lock: ClassVar[threading.Lock] = threading.Lock()

    def __call__(cls, *args, **kwargs):
        with cls._lock:
            if cls not in cls._instances:
                cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class AppConfig(metaclass=SingletonMeta):
    """Application-wide configuration — only one instance."""

    def __init__(self):
        self.model: str = "gpt-4"
        self.debug: bool = False
        self.max_tokens: int = 2000
        self.temperature: float = 0.7
        print("  [Config] Initialized")

    def update(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)


# Always same instance
config1 = AppConfig()
config2 = AppConfig()
config1.model = "claude-3"
print(f"Singleton: {config1 is config2}")    # True
print(f"Model via config2: {config2.model}") # claude-3


# ─────────────────────────────────────────────────────────────
# 2. FACTORY METHOD — delegate creation to subclasses
# ─────────────────────────────────────────────────────────────

class Agent(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def execute(self, task: str) -> str: ...

    def __repr__(self) -> str:
        return f"{type(self).__name__}(name={self.name!r})"


class ResearchAgent(Agent):
    def execute(self, task: str) -> str:
        return f"[Research] {task}"

class CodingAgent(Agent):
    def execute(self, task: str) -> str:
        return f"[Code] {task}"

class ReviewAgent(Agent):
    def execute(self, task: str) -> str:
        return f"[Review] {task}"


class AgentFactory:
    """Factory with registration pattern."""

    _registry: ClassVar[dict[str, type[Agent]]] = {}

    @classmethod
    def register(cls, agent_type: str) -> Callable:
        """Decorator to register agent types."""
        def decorator(agent_cls: type[Agent]) -> type[Agent]:
            cls._registry[agent_type] = agent_cls
            return agent_cls
        return decorator

    @classmethod
    def create(cls, agent_type: str, name: str) -> Agent:
        agent_cls = cls._registry.get(agent_type)
        if not agent_cls:
            raise ValueError(f"Unknown agent: {agent_type}. Available: {list(cls._registry)}")
        return agent_cls(name)

    @classmethod
    def types(cls) -> list[str]:
        return list(cls._registry)


AgentFactory.register("research")(ResearchAgent)
AgentFactory.register("coding")(CodingAgent)
AgentFactory.register("review")(ReviewAgent)

print(f"\nAvailable agents: {AgentFactory.types()}")
agent = AgentFactory.create("research", "r1")
print(f"Created: {agent}")
print(f"Result:  {agent.execute('Find Python trends')}")


# ─────────────────────────────────────────────────────────────
# 3. BUILDER — construct complex objects step by step
# ─────────────────────────────────────────────────────────────

@dataclass
class LLMRequest:
    model: str
    prompt: str
    system_prompt: str = ""
    temperature: float = 0.7
    max_tokens: int = 1000
    stream: bool = False
    tools: list[dict] = field(default_factory=list)
    tool_choice: str = "auto"
    response_format: str = "text"
    stop_sequences: list[str] = field(default_factory=list)


class LLMRequestBuilder:
    """
    Builder pattern — construct LLMRequest step by step.
    Provides fluent interface, validation, sensible defaults.
    """

    def __init__(self, model: str, prompt: str):
        self._model = model
        self._prompt = prompt
        self._system = ""
        self._temperature = 0.7
        self._max_tokens = 1000
        self._stream = False
        self._tools: list[dict] = []
        self._tool_choice = "auto"
        self._format = "text"
        self._stop: list[str] = []

    def system(self, prompt: str) -> LLMRequestBuilder:
        self._system = prompt
        return self

    def temperature(self, value: float) -> LLMRequestBuilder:
        if not 0.0 <= value <= 2.0:
            raise ValueError(f"Temperature must be 0-2, got {value}")
        self._temperature = value
        return self

    def max_tokens(self, n: int) -> LLMRequestBuilder:
        self._max_tokens = n
        return self

    def stream(self) -> LLMRequestBuilder:
        self._stream = True
        return self

    def with_tool(self, name: str, description: str, parameters: dict) -> LLMRequestBuilder:
        self._tools.append({"name": name, "description": description, "parameters": parameters})
        return self

    def json_output(self) -> LLMRequestBuilder:
        self._format = "json_object"
        return self

    def stop_at(self, *sequences: str) -> LLMRequestBuilder:
        self._stop.extend(sequences)
        return self

    def build(self) -> LLMRequest:
        if not self._prompt.strip():
            raise ValueError("Prompt cannot be empty")
        return LLMRequest(
            model=self._model,
            prompt=self._prompt,
            system_prompt=self._system,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            stream=self._stream,
            tools=self._tools,
            tool_choice=self._tool_choice,
            response_format=self._format,
            stop_sequences=self._stop,
        )


request = (
    LLMRequestBuilder("gpt-4", "Analyze this codebase")
    .system("You are a senior Python engineer.")
    .temperature(0.3)
    .max_tokens(2000)
    .with_tool("search", "Search the web", {"query": {"type": "string"}})
    .json_output()
    .build()
)
print(f"\nBuilt request: model={request.model}, tools={len(request.tools)}")


# ══════════════════════════════════════════════════════════════
# STRUCTURAL PATTERNS
# ══════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────
# 4. ADAPTER — make incompatible interfaces work together
# ─────────────────────────────────────────────────────────────

# Legacy interface
class LegacyTranslator:
    def translate_text(self, text: str, from_lang: str, to_lang: str) -> str:
        return f"[Legacy] {text} ({from_lang}→{to_lang})"

# New interface your app expects
class TranslationService(ABC):
    @abstractmethod
    def translate(self, text: str, source: str, target: str) -> str: ...

# Adapter — wraps legacy, exposes new interface
class LegacyTranslatorAdapter(TranslationService):
    def __init__(self, legacy: LegacyTranslator):
        self._legacy = legacy

    def translate(self, text: str, source: str, target: str) -> str:
        return self._legacy.translate_text(text, source, target)

legacy = LegacyTranslator()
adapter = LegacyTranslatorAdapter(legacy)
print(f"\nAdapter: {adapter.translate('Hello', 'en', 'es')}")


# ─────────────────────────────────────────────────────────────
# 5. DECORATOR PATTERN (different from Python @decorator)
# ─────────────────────────────────────────────────────────────

class LLMService(ABC):
    @abstractmethod
    def complete(self, prompt: str) -> str: ...


class BaseLLMService(LLMService):
    def complete(self, prompt: str) -> str:
        return f"Response to: {prompt}"


class LoggingDecorator(LLMService):
    """Adds logging without modifying BaseLLMService."""
    def __init__(self, service: LLMService):
        self._service = service

    def complete(self, prompt: str) -> str:
        print(f"  [LOG] Calling LLM with: {prompt[:30]}")
        result = self._service.complete(prompt)
        print(f"  [LOG] Got response: {result[:30]}")
        return result


class CachingDecorator(LLMService):
    """Adds caching without modifying BaseLLMService."""
    def __init__(self, service: LLMService):
        self._service = service
        self._cache: dict[str, str] = {}

    def complete(self, prompt: str) -> str:
        if prompt in self._cache:
            print(f"  [CACHE] HIT for: {prompt[:30]}")
            return self._cache[prompt]
        result = self._service.complete(prompt)
        self._cache[prompt] = result
        print(f"  [CACHE] MISS — stored result")
        return result


# Stack decorators — composable
service = CachingDecorator(LoggingDecorator(BaseLLMService()))
print("\nDecorator pattern:")
service.complete("What is Python?")
service.complete("What is Python?")   # cache hit


# ─────────────────────────────────────────────────────────────
# 6. PROXY PATTERN
# ─────────────────────────────────────────────────────────────

class ExpensiveLLMService:
    def complete(self, prompt: str) -> str:
        import time; time.sleep(0.1)
        return f"Expensive response: {prompt}"


class LazyProxy:
    """Delays creation of expensive object until first use."""
    def __init__(self, factory: Callable):
        self._factory = factory
        self._instance = None

    def __getattr__(self, name: str):
        if self._instance is None:
            print("  [PROXY] Creating expensive service...")
            self._instance = self._factory()
        return getattr(self._instance, name)

proxy = LazyProxy(ExpensiveLLMService)
print("\nProxy (lazy creation):")
print("  Proxy created — service NOT yet instantiated")
result = proxy.complete("Hello")   # service created here
print(f"  Result: {result[:30]}")


# ══════════════════════════════════════════════════════════════
# BEHAVIORAL PATTERNS
# ══════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────
# 7. STRATEGY — swap algorithms at runtime
# ─────────────────────────────────────────────────────────────

class RoutingStrategy(ABC):
    @abstractmethod
    def select_model(self, prompt: str, context: dict) -> str: ...


class CheapestFirst(RoutingStrategy):
    def select_model(self, prompt: str, context: dict) -> str:
        return "gpt-3.5-turbo"   # cheapest always


class SmartRouter(RoutingStrategy):
    def select_model(self, prompt: str, context: dict) -> str:
        # Complex prompts → powerful model
        if len(prompt.split()) > 100 or context.get("requires_reasoning"):
            return "gpt-4"
        return "gpt-3.5-turbo"


class ModelRouter:
    """Context that uses a routing strategy."""
    def __init__(self, strategy: RoutingStrategy):
        self._strategy = strategy

    def set_strategy(self, strategy: RoutingStrategy) -> None:
        self._strategy = strategy

    def route(self, prompt: str, context: dict = {}) -> str:
        model = self._strategy.select_model(prompt, context)
        return f"[{model}] Response to: {prompt[:30]}"


router = ModelRouter(SmartRouter())
print(f"\nStrategy: {router.route('Hello')}")
print(f"Strategy: {router.route('Hello ' * 150)}")  # long → gpt-4

router.set_strategy(CheapestFirst())
print(f"Strategy changed: {router.route('Hello')}")


# ─────────────────────────────────────────────────────────────
# 8. OBSERVER — event/notification system
# ─────────────────────────────────────────────────────────────

from typing import Callable

class EventBus:
    """Simple pub/sub event system."""

    def __init__(self):
        self._handlers: dict[str, list[Callable]] = {}

    def subscribe(self, event: str, handler: Callable) -> None:
        self._handlers.setdefault(event, []).append(handler)

    def unsubscribe(self, event: str, handler: Callable) -> None:
        if event in self._handlers:
            self._handlers[event].remove(handler)

    def publish(self, event: str, data: Any = None) -> None:
        for handler in self._handlers.get(event, []):
            handler(data)


bus = EventBus()

def on_token_used(data: dict) -> None:
    print(f"  [METRICS] Token used: {data}")

def on_error(data: dict) -> None:
    print(f"  [ALERT] Error: {data}")

bus.subscribe("token_used", on_token_used)
bus.subscribe("error", on_error)

print("\nObserver pattern:")
bus.publish("token_used", {"model": "gpt-4", "tokens": 500})
bus.publish("error", {"code": "TIMEOUT", "message": "API timeout"})


# ─────────────────────────────────────────────────────────────
# 9. COMMAND — encapsulate requests as objects
# ─────────────────────────────────────────────────────────────

class Command(ABC):
    @abstractmethod
    def execute(self) -> Any: ...

    @abstractmethod
    def undo(self) -> None: ...


class AddMessageCommand(Command):
    def __init__(self, history: list[dict], message: dict):
        self._history = history
        self._message = message

    def execute(self) -> dict:
        self._history.append(self._message)
        return self._message

    def undo(self) -> None:
        if self._history and self._history[-1] == self._message:
            self._history.pop()


class CommandHistory:
    """Maintains command history for undo/redo."""
    def __init__(self):
        self._done: list[Command] = []

    def execute(self, command: Command) -> Any:
        result = command.execute()
        self._done.append(command)
        return result

    def undo(self) -> None:
        if self._done:
            self._done.pop().undo()


history: list[dict] = []
cmd_history = CommandHistory()
cmd1 = AddMessageCommand(history, {"role": "user", "content": "Hello"})
cmd2 = AddMessageCommand(history, {"role": "assistant", "content": "Hi!"})

cmd_history.execute(cmd1)
cmd_history.execute(cmd2)
print(f"\nCommand history: {history}")

cmd_history.undo()
print(f"After undo: {history}")


# ─────────────────────────────────────────────────────────────
# 10. CHAIN OF RESPONSIBILITY — pipeline processing
# ─────────────────────────────────────────────────────────────

class PromptHandler(ABC):
    def __init__(self):
        self._next: PromptHandler | None = None

    def set_next(self, handler: PromptHandler) -> PromptHandler:
        self._next = handler
        return handler

    def handle(self, prompt: str) -> str | None:
        if self._next:
            return self._next.handle(prompt)
        return None   # end of chain

    @abstractmethod
    def process(self, prompt: str) -> str | None: ...


class SanitizeHandler(PromptHandler):
    def process(self, prompt: str) -> str | None:
        prompt = prompt.strip()
        if not prompt:
            return "Error: empty prompt"
        return self._next.handle(prompt) if self._next else prompt

    def handle(self, prompt: str) -> str | None:
        cleaned = prompt.strip()
        if not cleaned:
            return "Error: empty prompt"
        return super().handle(cleaned)


class LengthCheckHandler(PromptHandler):
    def __init__(self, max_len: int = 1000):
        super().__init__()
        self._max_len = max_len

    def handle(self, prompt: str) -> str | None:
        if len(prompt) > self._max_len:
            return f"Error: prompt too long ({len(prompt)} > {self._max_len})"
        return super().handle(prompt)


class ContentFilterHandler(PromptHandler):
    BLOCKED = ["spam", "junk"]

    def handle(self, prompt: str) -> str | None:
        if any(b in prompt.lower() for b in self.BLOCKED):
            return "Error: blocked content"
        return super().handle(prompt)


class LLMCallHandler(PromptHandler):
    def handle(self, prompt: str) -> str | None:
        return f"LLM Response to: {prompt[:50]}"


# Build the chain
sanitizer     = SanitizeHandler()
length_check  = LengthCheckHandler(max_len=100)
content_filter= ContentFilterHandler()
llm_call      = LLMCallHandler()

sanitizer.set_next(length_check).set_next(content_filter).set_next(llm_call)

prompts = [
    "  Hello, World!  ",
    "",
    "This is spam content",
    "A" * 200,
    "Valid prompt about Python",
]

print("\nChain of Responsibility:")
for p in prompts:
    result = sanitizer.handle(p)
    print(f"  '{p[:30]}...' → {result}")


# ─────────────────────────────────────────────────────────────
# INTERVIEW QUESTIONS
# ─────────────────────────────────────────────────────────────
"""
Q: When would you use the Builder pattern instead of a dataclass?
A: Builder when: many optional fields, validation during construction,
   need method chaining for readability, complex combinations of settings.
   Dataclass when: simple data container, all fields known upfront.

Q: What is the difference between Decorator pattern and Python @decorator?
A: Python @decorator is syntax sugar for function wrapping.
   The Decorator design pattern wraps objects implementing the same interface,
   adding behavior without modifying the original class.
   They're related concepts but different levels of abstraction.

Q: When would you use Strategy vs Factory?
A: Factory: which TYPE of object to create.
   Strategy: which ALGORITHM to use (same interface, different behavior).

Q: What is the Repository pattern and why use it?
A: Abstracts data access behind an interface.
   Your domain code uses UserRepository.find_by_id() — doesn't care if
   it's PostgreSQL, Redis, or an in-memory mock.
   Enables testing without a real database.
"""
