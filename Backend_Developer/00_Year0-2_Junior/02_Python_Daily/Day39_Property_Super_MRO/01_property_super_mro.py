"""
DAY 39 — @property, super(), MRO, inspect module
Architecture Level: Senior Python Backend + Agentic AI
"""

import inspect
from typing import Any


# ═══════════════════════════════════════════════════════
# PART A: @property — controlled attribute access
# ═══════════════════════════════════════════════════════

class LLMConfig:
    """
    @property provides getter/setter/deleter for attributes.
    Allows validation, computed values, and backward compatibility.
    """

    def __init__(self, model: str, temperature: float, max_tokens: int):
        # Store internally with underscore — convention for "private"
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens

    # ── Getter ────────────────────────────────
    @property
    def temperature(self) -> float:
        return self._temperature

    # ── Setter — with validation ───────────────
    @temperature.setter
    def temperature(self, value: float) -> None:
        if not isinstance(value, (int, float)):
            raise TypeError(f"temperature must be a number, got {type(value)}")
        if not 0.0 <= value <= 2.0:
            raise ValueError(f"temperature must be 0.0-2.0, got {value}")
        self._temperature = float(value)

    # ── Deleter ───────────────────────────────
    @temperature.deleter
    def temperature(self) -> None:
        self._temperature = 0.7  # reset to default

    # ── Computed property (read-only) ─────────
    @property
    def is_deterministic(self) -> bool:
        """No setter — read only."""
        return self._temperature == 0.0

    @property
    def cost_tier(self) -> str:
        """Derived from model name."""
        if "gpt-4" in self._model or "opus" in self._model:
            return "premium"
        elif "gpt-3.5" in self._model or "haiku" in self._model:
            return "economy"
        return "standard"

    # ── Property for backward compatibility ───
    @property
    def model(self) -> str:
        return self._model

    @model.setter
    def model(self, value: str) -> None:
        # Could add logging here when model changes
        valid_models = ["gpt-4", "gpt-3.5-turbo", "claude-3-opus", "claude-3-sonnet"]
        if value not in valid_models:
            raise ValueError(f"Unknown model: {value}. Valid: {valid_models}")
        self._model = value


config = LLMConfig("gpt-4", 0.7, 2000)
print(f"temp: {config.temperature}")
config.temperature = 0.9          # calls setter with validation
print(f"temp after set: {config.temperature}")
print(f"deterministic: {config.is_deterministic}")
print(f"cost tier: {config.cost_tier}")

del config.temperature            # resets to default
print(f"temp after del: {config.temperature}")

try:
    config.temperature = 5.0     # ValueError
except ValueError as e:
    print(f"Validation: {e}")


# ═══════════════════════════════════════════════════════
# PART B: super() and MRO — critical for frameworks
# ═══════════════════════════════════════════════════════

# MRO = Method Resolution Order
# Python uses C3 Linearization algorithm
# Order: class → left parent → right parent → grandparents → object

# ─────────────────────────────────────────────
# 1. Single inheritance — simple super()
# ─────────────────────────────────────────────

class BaseAgent:
    def __init__(self, name: str, model: str):
        self.name = name
        self.model = model
        self._history: list[dict] = []
        print(f"  [BaseAgent.__init__] name={name}")

    def run(self, task: str) -> str:
        result = self._execute(task)
        self._history.append({"task": task, "result": result})
        return result

    def _execute(self, task: str) -> str:
        return f"[Base] {task}"


class ResearchAgent(BaseAgent):
    def __init__(self, name: str, model: str, search_depth: int = 3):
        super().__init__(name, model)   # MUST call super().__init__
        self.search_depth = search_depth
        print(f"  [ResearchAgent.__init__] depth={search_depth}")

    def _execute(self, task: str) -> str:
        return f"[Research depth={self.search_depth}] {task}"


agent = ResearchAgent("researcher", "gpt-4", search_depth=5)
print(agent.run("Find Python trends"))
print(f"History: {agent._history}")


# ─────────────────────────────────────────────
# 2. Multiple inheritance — MRO is critical
# ─────────────────────────────────────────────

class Loggable:
    def __init__(self, **kwargs):
        super().__init__(**kwargs)    # MUST pass **kwargs in mixins!
        print(f"  [Loggable.__init__]")

    def log(self, message: str) -> None:
        print(f"  [LOG] {message}")


class Cacheable:
    def __init__(self, cache_ttl: int = 300, **kwargs):
        super().__init__(**kwargs)    # MUST pass **kwargs in mixins!
        self.cache_ttl = cache_ttl
        self._cache: dict = {}
        print(f"  [Cacheable.__init__] ttl={cache_ttl}")

    def cache_get(self, key: str) -> Any | None:
        return self._cache.get(key)

    def cache_set(self, key: str, value: Any) -> None:
        self._cache[key] = value


class SmartAgent(Loggable, Cacheable, BaseAgent):
    """
    Diamond inheritance — Python resolves with MRO.
    MRO: SmartAgent → Loggable → Cacheable → BaseAgent → object
    """
    def __init__(self, name: str, model: str, cache_ttl: int = 300):
        print(f"\n[SmartAgent.__init__] — MRO order:")
        super().__init__(name=name, model=model, cache_ttl=cache_ttl)

    def _execute(self, task: str) -> str:
        cached = self.cache_get(task)
        if cached:
            self.log(f"Cache HIT for: {task}")
            return cached

        self.log(f"Cache MISS — executing: {task}")
        result = f"[Smart] Result for: {task}"
        self.cache_set(task, result)
        return result


smart = SmartAgent("smart_agent", "gpt-4", cache_ttl=600)
print(f"\nMRO: {[cls.__name__ for cls in SmartAgent.__mro__]}")

result1 = smart.run("Analyze Python")
result2 = smart.run("Analyze Python")  # cached


# ─────────────────────────────────────────────
# 3. super() in class methods
# ─────────────────────────────────────────────

class BaseModel:
    _validators: list = []

    @classmethod
    def validate(cls, data: dict) -> bool:
        print(f"  [BaseModel.validate] running {len(cls._validators)} validators")
        return True


class UserModel(BaseModel):
    @classmethod
    def validate(cls, data: dict) -> bool:
        result = super().validate(data)  # calls BaseModel.validate
        if not data.get("email"):
            raise ValueError("Email required")
        return result


UserModel.validate({"email": "test@example.com"})


# ─────────────────────────────────────────────
# 4. MRO resolution
# ─────────────────────────────────────────────

class A:
    def method(self): print(f"A.method")

class B(A):
    def method(self): super().method(); print(f"B.method")

class C(A):
    def method(self): super().method(); print(f"C.method")

class D(B, C):  # MRO: D → B → C → A → object
    def method(self): super().method(); print(f"D.method")

print(f"\nMRO of D: {[cls.__name__ for cls in D.__mro__]}")
print("Calling D().method():")
D().method()  # A → C → B → D (cooperative multiple inheritance)


# ═══════════════════════════════════════════════════════
# PART C: inspect module — introspection
# ═══════════════════════════════════════════════════════

def process_task(
    task: str,
    model: str = "gpt-4",
    temperature: float = 0.7,
    *,
    stream: bool = False,
) -> dict:
    """Process an AI task."""
    return {"task": task, "model": model}


# Get function signature
sig = inspect.signature(process_task)
print(f"\nSignature: {sig}")

# Get parameters
for name, param in sig.parameters.items():
    print(f"  {name}: kind={param.kind.name}, default={param.default}")

# Check if a value is provided vs default
def call_with_defaults(func, **override):
    """Call function using its defaults unless overridden."""
    sig = inspect.signature(func)
    kwargs = {}
    for name, param in sig.parameters.items():
        if name in override:
            kwargs[name] = override[name]
        elif param.default is not inspect.Parameter.empty:
            kwargs[name] = param.default
    return func(**kwargs)

# result = call_with_defaults(process_task, task="Build API")  # uses defaults


# Get source code (useful in agent debugging)
class MyAgent:
    def run(self, task: str) -> str:
        return task.upper()

# print(inspect.getsource(MyAgent.run))  # prints the source

# Get class hierarchy
print(f"\nSuperclasses of SmartAgent:")
for cls in inspect.getmro(SmartAgent):
    print(f"  {cls.__name__}")

# Get all methods
print(f"\nMethods of AgentConfig (from BaseAgent):")
methods = inspect.getmembers(BaseAgent, predicate=inspect.isfunction)
for name, method in methods:
    print(f"  {name}: {inspect.signature(method)}")


# ─────────────────────────────────────────────
# INTERVIEW CHEAT SHEET
# ─────────────────────────────────────────────
# @property        — getter only (read-only computed attribute)
# @x.setter        — add setter to existing property
# @x.deleter       — add deleter to existing property
#
# super()          — delegates to next class in MRO
# super().__init__ — ALWAYS call in __init__ for proper MRO cooperation
# **kwargs         — MUST pass **kwargs in mixins for cooperative inheritance
#
# MRO algorithm (C3 linearization):
# D(B, C) where B(A), C(A): D → B → C → A → object
# Rule: left before right, child before parent
#
# inspect module:
# inspect.signature()     — get function signature
# inspect.getmembers()    — list all attributes/methods
# inspect.isfunction()    — check if callable
# inspect.getsource()     — get source code
# inspect.getmro()        — get MRO tuple
# inspect.Parameter.empty — sentinel for "no default"
