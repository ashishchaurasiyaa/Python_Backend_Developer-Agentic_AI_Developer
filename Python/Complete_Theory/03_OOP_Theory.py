"""
╔══════════════════════════════════════════════════════════════════════════════╗
║   PYTHON COMPLETE THEORY — File 03                                           ║
║   Topic: Object-Oriented Programming (OOP)                                   ║
║   Format: WHAT → WHY → HOW → REAL LIFE → PRODUCTION CODE → Q&A              ║
╚══════════════════════════════════════════════════════════════════════════════╝

Topics Covered:
  A. Classes & Objects — blueprints and instances
  B. __init__, Instance Variables, Class Variables
  C. @property — computed/validated attributes
  D. @classmethod and @staticmethod
  E. Dunder (Magic) Methods — __repr__, __eq__, __hash__, __call__, etc.
  F. Inheritance & super()
  G. MRO — Method Resolution Order (C3 Linearization)
  H. Abstract Base Classes (ABC)
  I. Mixins — reusable behavior injection
  J. Descriptors — attribute access control at class level
  K. Metaclasses — classes of classes
"""


# ══════════════════════════════════════════════════════════════════════════════
# PART A: CLASSES & OBJECTS
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS A CLASS?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

A class is a BLUEPRINT / TEMPLATE for creating objects.
An object (instance) is a concrete thing made from that blueprint.

Simple terms:
  - Class  = Cookie cutter (shape)
  - Object = Cookie (actual thing made from it)
  - Class  = Car design on paper
  - Object = Actual car manufactured from that design

INTERNAL STRUCTURE:
Every class in Python is itself an object — an instance of `type`.

  class Dog:              ┌─────────────────────────┐
      name = "unknown"    │     Dog CLASS OBJECT     │
      def bark(self):     │  ─────────────────────── │
          pass            │  __dict__:               │
                          │    'name': 'unknown'     │
                          │    'bark': <function>    │
  d = Dog()               │  __bases__: (object,)    │
                          │  __mro__: [Dog, object]  │
                          └─────────────────────────┘
                                      │
                          ┌─────────────────────────┐
                          │   Dog INSTANCE d         │
                          │  ─────────────────────── │
                          │  __dict__:               │
                          │    (empty unless set)    │
                          │  __class__: Dog          │
                          └─────────────────────────┘

ATTRIBUTE LOOKUP ORDER (for instance d):
  1. d.__dict__               (instance dictionary)
  2. Dog.__dict__             (class dictionary)
  3. Parent classes (via MRO)
  4. AttributeError

WHY USE CLASSES?
  - Group related data + behavior together (cohesion)
  - Avoid global variables (encapsulation)
  - Reuse code via inheritance
  - Model real-world entities (User, Order, LLMAgent)

HOW:
  class ClassName(ParentClass):
      class_var = value          # shared by all instances

      def __init__(self, ...):   # called when object is created
          self.instance_var = value  # unique per instance

      def method(self):          # behavior
          ...

REAL LIFE ANALOGY:
  Think of a Hospital:
    - Patient class = registration form template
    - Each patient object = filled form for one person
    - 'name', 'age', 'disease' = instance variables (different per patient)
    - Hospital name = class variable (same for all patients)
"""

from typing import ClassVar, Optional
import sys


class LLMModel:
    """Production example: LLM model configuration class."""

    # Class variable — shared across ALL instances
    provider: ClassVar[str] = "openai"
    _registry: ClassVar[dict] = {}        # tracks all created models
    instance_count: ClassVar[int] = 0

    def __init__(self, name: str, max_tokens: int = 4096, temperature: float = 0.7):
        # Instance variables — unique per object
        self.name = name
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._call_count = 0              # private by convention (_prefix)

        # Update class variable
        LLMModel.instance_count += 1
        LLMModel._registry[name] = self

    def __repr__(self) -> str:
        return f"LLMModel(name={self.name!r}, max_tokens={self.max_tokens}, temp={self.temperature})"

    def call(self, prompt: str) -> str:
        self._call_count += 1
        return f"[{self.name}] Response to: {prompt[:30]}..."


# Demonstration
gpt4 = LLMModel("gpt-4", max_tokens=8192, temperature=0.2)
claude = LLMModel("claude-3-sonnet", max_tokens=100_000, temperature=0.5)

print(f"Provider (class var): {LLMModel.provider}")
print(f"Instance count: {LLMModel.instance_count}")
print(f"Registry: {list(LLMModel._registry.keys())}")
print(f"gpt4 repr: {gpt4}")

# Class var accessed via instance OR class
print(f"Via instance: {gpt4.provider}")   # "openai"
print(f"Via class:    {LLMModel.provider}")  # "openai"

# Instance var — unique
print(f"gpt4 max_tokens: {gpt4.max_tokens}")      # 8192
print(f"claude max_tokens: {claude.max_tokens}")  # 100000


"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Q&A — Classes & Objects
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q1: Class variable vs instance variable — what is the difference?
A:  Class variable: defined inside class but outside __init__; SHARED by all instances.
    Instance variable: defined in __init__ with self.; UNIQUE per instance.

    DANGER: Mutable class vars (like lists/dicts) are shared by accident.

    class Bad:
        items = []        # shared! BUG
        def add(self, x):
            self.items.append(x)  # mutates THE SAME list

    class Good:
        def __init__(self):
            self.items = []   # each instance gets its own list

Q2: What is `self` in Python?
A:  `self` is a reference to the current instance. Python passes it automatically
    as the first argument to every instance method.

    dog.bark() is equivalent to Dog.bark(dog)

    It's a convention — you could name it anything, but ALWAYS name it `self`.

Q3: What happens when you set an instance attribute with the same name as a class attribute?
A:  Instance attribute SHADOWS the class attribute for that instance only.

    class A:
        x = 10
    a = A()
    a.x = 99   # adds to a.__dict__, shadows A.x
    print(a.x)   # 99  (instance dict)
    print(A.x)   # 10  (class dict unchanged)

Q4: What is ClassVar from typing?
A:  An annotation that explicitly marks a variable as a class-level variable,
    not an instance variable. Type checkers (mypy) use this to catch bugs where
    you accidentally assign a class var in __init__ as self.x.
"""


# ══════════════════════════════════════════════════════════════════════════════
# PART B: @property — COMPUTED & VALIDATED ATTRIBUTES
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS @property?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@property turns a METHOD into an ATTRIBUTE — so you can access it like
obj.attribute instead of obj.method().

WHY?
  Problem 1: You need to add validation but already have users doing obj.age = x
  Problem 2: Computed values that should look like plain attributes (obj.full_name)
  Problem 3: Read-only attributes (raise AttributeError on set)

HOW IT WORKS INTERNALLY:
  @property creates a DESCRIPTOR object with __get__, __set__, __delete__ methods.

  class Circle:          Python transforms:
      @property          obj.radius      → Circle.radius.__get__(obj, Circle)
      def radius(self):  obj.radius = 5  → Circle.radius.__set__(obj, 5)
          return self._radius

  Three decorators:
    @property          → getter (must have)
    @x.setter          → setter (optional)
    @x.deleter         → deleter (optional)

  WITHOUT @property (old style — bad):
    circle.get_radius()   # ugly, not Pythonic
    circle.set_radius(5)  # Java-style

  WITH @property (Pythonic):
    circle.radius         # clean!
    circle.radius = 5     # with validation!

REAL LIFE ANALOGY:
  A smart thermostat:
    - You set temperature: thermostat.temp = 25
    - But internally: validates (not below 10°C, not above 40°C)
    - And converts (stores as Celsius internally)
    - You read it: thermostat.temp → returns current value
    All this happens transparently — you just use .temp
"""

class Temperature:
    """Demonstrates @property with validation and unit conversion."""

    def __init__(self, celsius: float = 0.0):
        self._celsius = celsius  # private storage with underscore

    @property
    def celsius(self) -> float:
        """Getter — just return stored value."""
        return self._celsius

    @celsius.setter
    def celsius(self, value: float) -> None:
        """Setter — validate before storing."""
        if value < -273.15:
            raise ValueError(f"Temperature {value}°C below absolute zero!")
        self._celsius = value

    @property
    def fahrenheit(self) -> float:
        """Computed property — no setter needed, computed from celsius."""
        return self._celsius * 9/5 + 32

    @property
    def kelvin(self) -> float:
        return self._celsius + 273.15

    @celsius.deleter
    def celsius(self) -> None:
        print("Resetting temperature to 0°C")
        self._celsius = 0.0

    def __repr__(self) -> str:
        return f"Temperature({self._celsius}°C / {self.fahrenheit}°F / {self.kelvin}K)"


t = Temperature(25)
print(f"\n@property demo:")
print(f"celsius: {t.celsius}")         # getter
print(f"fahrenheit: {t.fahrenheit}")   # computed
print(f"kelvin: {t.kelvin}")           # computed
t.celsius = 100                        # setter with validation
print(f"After setting to 100: {t}")

try:
    t.celsius = -300  # below absolute zero
except ValueError as e:
    print(f"Caught: {e}")

del t.celsius    # deleter


class AgentConfig:
    """Production: @property for AI agent configuration with validation."""

    def __init__(self, model: str, temperature: float = 0.7, max_tokens: int = 2048):
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens

    @property
    def model(self) -> str:
        return self._model

    @model.setter
    def model(self, value: str) -> None:
        allowed = {"gpt-4", "gpt-3.5-turbo", "claude-3-sonnet", "claude-3-opus"}
        if value not in allowed:
            raise ValueError(f"Unknown model: {value}. Allowed: {allowed}")
        self._model = value

    @property
    def temperature(self) -> float:
        return self._temperature

    @temperature.setter
    def temperature(self, value: float) -> None:
        if not 0.0 <= value <= 2.0:
            raise ValueError(f"Temperature must be 0.0–2.0, got {value}")
        self._temperature = value

    @property
    def is_creative(self) -> bool:
        """Read-only computed property — no setter."""
        return self._temperature > 0.8

    @property
    def config_summary(self) -> dict:
        """Read-only computed dict."""
        return {
            "model": self._model,
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
            "mode": "creative" if self.is_creative else "precise",
        }


cfg = AgentConfig("gpt-4", temperature=0.2)
print(f"\nAgentConfig summary: {cfg.config_summary}")
cfg.temperature = 1.2
print(f"After temp=1.2, creative mode: {cfg.is_creative}")

try:
    cfg.is_creative = True  # read-only property — no setter
except AttributeError as e:
    print(f"Caught: {e}")


"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Q&A — @property
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q1: Why use @property instead of direct attribute access?
A:  To add validation, conversion, or computed logic WITHOUT changing the
    public interface. Users keep writing obj.attr = value instead of obj.set_attr(value).
    This is the "Uniform Access Principle" — no need to know if it's a plain attr or method.

Q2: What is the difference between _x and __x in Python?
A:  _x  → Convention for "private" — still accessible but "don't touch unless you know what you're doing"
    __x → Name mangling — Python renames it to _ClassName__x, making accidental
          access harder (but not impossible). Not true private.

Q3: Can a property have only a getter (no setter)?
A:  Yes — if you only define @property without @x.setter, trying to set it raises:
    AttributeError: can't set attribute
    This creates effectively read-only attributes.

Q4: When does a property NOT work?
A:  On class variables accessed at the class level (not via instance).
    Also, performance: every access goes through a function call. For very
    hot paths (millions of times per second), direct attribute access is faster.
"""


# ══════════════════════════════════════════════════════════════════════════════
# PART C: @classmethod AND @staticmethod
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT ARE @classmethod AND @staticmethod?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

THREE TYPES OF METHODS in Python:

  1. Instance method  → first arg is `self` (the instance)
                        can access instance + class data
                        most common

  2. Class method     → @classmethod, first arg is `cls` (the class itself)
                        can access class data but NOT instance data
                        mainly used for: alternative constructors (factory methods)

  3. Static method    → @staticmethod, NO first arg
                        cannot access instance OR class data
                        just a regular function that logically belongs to the class

VISUAL COMPARISON:
  ┌─────────────────┬──────────────────┬─────────────────────────────┐
  │ Method Type     │ First Arg        │ Access To                   │
  ├─────────────────┼──────────────────┼─────────────────────────────┤
  │ instance method │ self (instance)  │ self.x, self.method(), cls  │
  │ @classmethod    │ cls  (class)     │ cls.var, cls() — not self   │
  │ @staticmethod   │ none             │ only args passed explicitly  │
  └─────────────────┴──────────────────┴─────────────────────────────┘

WHY @classmethod?
  Problem: You want multiple ways to CREATE an object, but __init__ can only have
  one signature.
  Solution: Alternative constructors as @classmethod

  Example:
    User.from_dict({"name": "Alice", "age": 30})
    User.from_json('{"name": "Bob", "age": 25}')
    User.from_csv("Charlie,28")

  All create a User but from different input formats.

WHY @staticmethod?
  For utility/helper functions that logically belong with a class but don't
  need any class or instance data.

  Examples:
    - DateUtils.is_leap_year(2024)
    - MathUtils.clamp(value, min_val, max_val)
    - PasswordUtils.hash_password(plain_text)

REAL LIFE ANALOGY:
  Think of a Car Factory:
  - Instance method: THIS car's engine (this specific car's behavior)
  - @classmethod:    Create a new car from parts list (factory method — produces new instances)
  - @staticmethod:   Calculate fuel efficiency formula (utility — doesn't need a car instance)
"""

import json
from datetime import datetime


class Conversation:
    """Production: Conversation with multiple constructors via @classmethod."""

    _id_counter: ClassVar[int] = 0

    def __init__(self, messages: list[dict], model: str = "gpt-4", session_id: str = ""):
        self.messages = messages
        self.model = model
        self.session_id = session_id or self._generate_id()
        self.created_at = datetime.now()

    @classmethod
    def _generate_id(cls) -> str:
        cls._id_counter += 1
        return f"conv_{cls._id_counter:04d}"

    # ── Alternative Constructors (factory methods) ──
    @classmethod
    def from_dict(cls, data: dict) -> "Conversation":
        """Create from dictionary (API response)."""
        return cls(
            messages=data.get("messages", []),
            model=data.get("model", "gpt-4"),
            session_id=data.get("session_id", ""),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "Conversation":
        """Create from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)

    @classmethod
    def empty(cls, model: str = "gpt-4") -> "Conversation":
        """Create empty conversation — convenience constructor."""
        return cls(messages=[], model=model)

    @classmethod
    def with_system_prompt(cls, system_prompt: str, model: str = "gpt-4") -> "Conversation":
        """Start conversation with a system message."""
        return cls(
            messages=[{"role": "system", "content": system_prompt}],
            model=model,
        )

    # ── Static Methods (utilities) ──
    @staticmethod
    def count_tokens(text: str) -> int:
        """Rough token estimation — doesn't need instance or class."""
        return len(text.split()) * 4 // 3

    @staticmethod
    def is_valid_role(role: str) -> bool:
        """Validate message role — pure utility."""
        return role in {"system", "user", "assistant", "tool"}

    @staticmethod
    def truncate_message(content: str, max_chars: int = 100) -> str:
        """Truncate for display — pure utility."""
        return content[:max_chars] + "..." if len(content) > max_chars else content

    def add_message(self, role: str, content: str) -> None:
        if not self.is_valid_role(role):  # calling @staticmethod via instance
            raise ValueError(f"Invalid role: {role}")
        self.messages.append({"role": role, "content": content})

    def __repr__(self) -> str:
        return f"Conversation(id={self.session_id}, model={self.model}, msgs={len(self.messages)})"


# Using different constructors
conv1 = Conversation.empty("claude-3-sonnet")
conv2 = Conversation.with_system_prompt("You are a helpful AI assistant.")
conv3 = Conversation.from_dict({
    "messages": [{"role": "user", "content": "Hello"}],
    "model": "gpt-4",
    "session_id": "test_001",
})
conv4 = Conversation.from_json('{"messages": [], "model": "gpt-3.5-turbo"}')

print(f"\n@classmethod constructors:")
print(f"conv1: {conv1}")
print(f"conv2: {conv2}")
print(f"conv3: {conv3}")

# Using @staticmethod
print(f"\n@staticmethod utilities:")
print(f"Token count: {Conversation.count_tokens('Hello, how are you today?')}")
print(f"Valid role 'user': {Conversation.is_valid_role('user')}")
print(f"Valid role 'bot': {Conversation.is_valid_role('bot')}")


# ══════════════════════════════════════════════════════════════════════════════
# PART D: DUNDER METHODS (Magic Methods)
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT ARE DUNDER METHODS?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Dunder = Double UNDERscore — methods like __init__, __repr__, __eq__

They are called IMPLICITLY by Python operations:
  str(obj)    → obj.__str__()
  repr(obj)   → obj.__repr__()
  len(obj)    → obj.__len__()
  obj[0]      → obj.__getitem__(0)
  obj + other → obj.__add__(other)
  obj == other → obj.__eq__(other)
  with obj:   → obj.__enter__() / obj.__exit__()
  for x in obj → obj.__iter__()

COMPLETE DUNDER CHEATSHEET:
  ┌─────────────────┬──────────────────────────────────────────────────┐
  │ Dunder          │ Called when...                                   │
  ├─────────────────┼──────────────────────────────────────────────────┤
  │ __init__        │ obj = MyClass()                                  │
  │ __repr__        │ repr(obj) — unambiguous, for debugging           │
  │ __str__         │ str(obj), print(obj) — human-readable            │
  │ __eq__          │ obj == other                                     │
  │ __lt__          │ obj < other (enables sorting)                    │
  │ __hash__        │ hash(obj) — required for dict key / set member   │
  │ __bool__        │ bool(obj), if obj:                               │
  │ __len__         │ len(obj)                                         │
  │ __contains__    │ x in obj                                         │
  │ __getitem__     │ obj[key]                                         │
  │ __setitem__     │ obj[key] = value                                 │
  │ __delitem__     │ del obj[key]                                     │
  │ __iter__        │ for x in obj: / iter(obj)                       │
  │ __next__        │ next(obj)                                        │
  │ __call__        │ obj() — makes instance callable                  │
  │ __add__         │ obj + other                                      │
  │ __iadd__        │ obj += other (in-place)                          │
  │ __enter__       │ with obj as x:                                   │
  │ __exit__        │ exiting with block                               │
  │ __del__         │ when GC collects object                          │
  │ __getattr__     │ attribute not found normally                     │
  │ __setattr__     │ obj.attr = value                                 │
  └─────────────────┴──────────────────────────────────────────────────┘

NOTE: __repr__ should return a string that could recreate the object.
      __str__ is for human display. If only __repr__ defined, Python uses it for both.

REAL LIFE ANALOGY:
  Dunders are like PROTOCOLS in real life:
  - "+" sign → addition protocol → Python calls __add__
  - "print()" → display protocol → Python calls __str__
  - "in"  → membership protocol → Python calls __contains__
  You IMPLEMENT the protocol by defining these methods.
"""

from functools import total_ordering


@total_ordering  # auto-generates __le__, __ge__, __gt__ from __eq__ and __lt__
class TokenBudget:
    """Production: Track LLM token usage with full operator support."""

    def __init__(self, used: int, limit: int):
        self.used = used
        self.limit = limit

    def __repr__(self) -> str:
        # repr — unambiguous, can recreate object
        return f"TokenBudget(used={self.used}, limit={self.limit})"

    def __str__(self) -> str:
        # str — human readable
        pct = self.used / self.limit * 100
        bar = "█" * int(pct / 10) + "░" * (10 - int(pct / 10))
        return f"[{bar}] {self.used}/{self.limit} tokens ({pct:.1f}%)"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TokenBudget):
            return NotImplemented
        return self.used == other.used and self.limit == other.limit

    def __lt__(self, other: "TokenBudget") -> bool:
        # Compare by remaining budget
        return (self.limit - self.used) < (other.limit - other.used)

    def __hash__(self) -> int:
        # Required if you define __eq__ and want to use in sets/dict keys
        return hash((self.used, self.limit))

    def __bool__(self) -> bool:
        # Truthy if still has budget remaining
        return self.used < self.limit

    def __len__(self) -> int:
        # Return remaining tokens
        return self.limit - self.used

    def __add__(self, tokens: int) -> "TokenBudget":
        # budget + 100 → new budget with more usage
        return TokenBudget(self.used + tokens, self.limit)

    def __iadd__(self, tokens: int) -> "TokenBudget":
        # budget += 100
        self.used += tokens
        return self

    def __contains__(self, tokens: int) -> bool:
        # 100 in budget → "can we afford 100 tokens?"
        return self.used + tokens <= self.limit

    def __call__(self, tokens: int) -> "TokenBudget":
        # budget(500) → consume tokens, return self
        self.used += tokens
        return self


# Demonstration
budget = TokenBudget(used=3000, limit=8192)

print(f"\nDunder methods demo:")
print(f"repr: {repr(budget)}")
print(f"str:  {str(budget)}")
print(f"bool: {bool(budget)}")   # still has budget
print(f"len:  {len(budget)}")    # remaining tokens
print(f"500 in budget: {500 in budget}")    # can afford 500 more?
print(f"6000 in budget: {6000 in budget}")  # can afford 6000 more?

budget += 1000   # __iadd__
print(f"After += 1000: {budget}")

budget(500)      # __call__ — consume 500 tokens
print(f"After budget(500): {budget}")

b1 = TokenBudget(1000, 8000)
b2 = TokenBudget(2000, 8000)
budgets = [b2, b1]
budgets.sort()   # uses __lt__ via @total_ordering
print(f"Sorted by remaining: {budgets}")

# Hash — can use as dict key or in sets
budget_set = {b1, b2}
print(f"Can use in set: {len(budget_set)} items")


# ══════════════════════════════════════════════════════════════════════════════
# PART E: INHERITANCE & super()
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS INHERITANCE?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Inheritance = A child class gets ALL attributes and methods from parent class.
It expresses an IS-A relationship.

  Dog IS-A Animal  (Dog inherits from Animal)
  LLMAgent IS-A Agent (LLMAgent inherits from Agent)

WHY?
  Code reuse: Don't repeat common logic in every subclass.
  Polymorphism: Different subclasses, same interface.
  Extension: Add or override behavior without modifying parent.

HOW super() WORKS:
  super() returns a PROXY object that delegates method calls to the NEXT class
  in the MRO (Method Resolution Order).

  It does NOT mean "parent class" in simple cases — in multiple inheritance,
  it follows the full MRO chain (see Part F).

  class Animal:
      def __init__(self, name):
          self.name = name        ← super().__init__() calls THIS

  class Dog(Animal):
      def __init__(self, name, breed):
          super().__init__(name)  ← delegates to Animal.__init__
          self.breed = breed      ← then Dog adds its own

REAL LIFE ANALOGY:
  Employee hierarchy:
    Employee (base): has name, id, salary
    Manager (inherits Employee): has name, id, salary + department, team
    CEO (inherits Manager): has all of Manager's + equity, board_seat

  Each level EXTENDS the previous — doesn't repeat common fields.

TYPES:
  1. Single inheritance: class B(A)
  2. Multi-level: class C(B), class B(A)  → C inherits from B which inherits from A
  3. Multiple:    class C(A, B)            → C inherits from both A and B
  4. Hierarchical: class B(A), class C(A) → multiple children of same parent
"""


class BaseAgent:
    """Base class for all AI agents."""

    def __init__(self, agent_id: str, model: str):
        self.agent_id = agent_id
        self.model = model
        self._logs: list[str] = []
        print(f"  [BaseAgent.__init__] id={agent_id}")

    def log(self, message: str) -> None:
        entry = f"[{self.agent_id}] {message}"
        self._logs.append(entry)
        print(f"  LOG: {entry}")

    def run(self, task: str) -> str:
        raise NotImplementedError("Subclasses must implement run()")

    def get_logs(self) -> list[str]:
        return self._logs.copy()


class LLMAgent(BaseAgent):
    """LLM-based agent — extends BaseAgent with model-specific logic."""

    def __init__(self, agent_id: str, model: str, system_prompt: str):
        super().__init__(agent_id, model)  # delegates to BaseAgent
        self.system_prompt = system_prompt
        self.message_history: list[dict] = []
        print(f"  [LLMAgent.__init__] system_prompt={system_prompt[:30]}...")

    def add_message(self, role: str, content: str) -> None:
        self.message_history.append({"role": role, "content": content})

    def run(self, task: str) -> str:
        self.log(f"Running task: {task}")
        self.add_message("user", task)
        response = f"[{self.model}] Processed: {task}"
        self.add_message("assistant", response)
        return response

    def __repr__(self) -> str:
        return f"LLMAgent(id={self.agent_id!r}, model={self.model!r})"


class ToolAgent(LLMAgent):
    """Tool-using agent — extends LLMAgent with tool calling."""

    def __init__(self, agent_id: str, model: str, system_prompt: str, tools: list[str]):
        super().__init__(agent_id, model, system_prompt)  # → LLMAgent → BaseAgent
        self.tools = tools
        self.tool_calls: list[dict] = []
        print(f"  [ToolAgent.__init__] tools={tools}")

    def call_tool(self, tool_name: str, **kwargs) -> dict:
        if tool_name not in self.tools:
            raise ValueError(f"Tool {tool_name!r} not available")
        result = {"tool": tool_name, "args": kwargs, "result": f"Tool result for {tool_name}"}
        self.tool_calls.append(result)
        self.log(f"Called tool: {tool_name}")
        return result

    def run(self, task: str) -> str:
        self.log(f"ToolAgent running: {task}")
        # Override — different behavior for tool agents
        self.call_tool(self.tools[0], task=task)
        return super().run(task)  # still calls LLMAgent.run after tool use


print(f"\nInheritance demo:")
agent = ToolAgent(
    agent_id="agent_001",
    model="gpt-4",
    system_prompt="You are a helpful research assistant.",
    tools=["web_search", "code_execute"],
)

result = agent.run("Research Python async patterns")
print(f"Result: {result}")
print(f"Is BaseAgent: {isinstance(agent, BaseAgent)}")
print(f"Is LLMAgent: {isinstance(agent, LLMAgent)}")
print(f"Is ToolAgent: {isinstance(agent, ToolAgent)}")


# ══════════════════════════════════════════════════════════════════════════════
# PART F: MRO — Method Resolution Order
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS MRO?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

MRO = Method Resolution Order — the ORDER in which Python looks up methods
when you have multiple inheritance.

Python uses the C3 Linearization algorithm to compute MRO.
Rule: "Left to right, depth-first, no class appears before its parents."

THE DIAMOND PROBLEM:
  Without MRO rules, multiple inheritance creates ambiguity:

        A
       / \
      B   C
       \ /
        D

  D inherits from B and C.
  B and C both inherit from A.
  If you call D().method(), which method() runs?

C3 ALGORITHM:
  D.__mro__ = [D, B, C, A, object]

  Python searches LEFT TO RIGHT through MRO until it finds the method.
  super() follows the SAME MRO chain — not just "the parent".

WHY THIS MATTERS FOR MIXINS:
  With Mixins (Part H), you compose behavior:
    class SmartAgent(LogMixin, CacheMixin, BaseAgent):
        pass

  MRO = [SmartAgent, LogMixin, CacheMixin, BaseAgent, object]
  Each super() call follows this chain — cooperative multiple inheritance.

REAL LIFE ANALOGY:
  Imagine a legal inheritance dispute:
  "My father says X, but my grandfather says Y — whose rule wins?"
  MRO establishes a clear, unambiguous precedence order.
"""

class LogMixin:
    def describe(self) -> str:
        print(f"  LogMixin.describe called")
        result = super().describe() if hasattr(super(), "describe") else ""
        return f"[LOGGED] {result}"

class CacheMixin:
    def describe(self) -> str:
        print(f"  CacheMixin.describe called")
        result = super().describe() if hasattr(super(), "describe") else ""
        return f"[CACHED] {result}"

class Component:
    def describe(self) -> str:
        print(f"  Component.describe called")
        return "Component"

class SmartComponent(LogMixin, CacheMixin, Component):
    def describe(self) -> str:
        print(f"  SmartComponent.describe called")
        return super().describe()  # follows MRO chain

print(f"\nMRO demonstration:")
print(f"MRO: {[c.__name__ for c in SmartComponent.__mro__]}")
# Output: [SmartComponent, LogMixin, CacheMixin, Component, object]

sc = SmartComponent()
result = sc.describe()
print(f"Final result: {result}")
# Each class in MRO calls super(), creating a CHAIN:
# SmartComponent → LogMixin → CacheMixin → Component → (no more describe)


"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Q&A — Inheritance & MRO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q1: What does super() actually do?
A:  super() returns a proxy that delegates attribute lookups to the NEXT class
    in the MRO, not necessarily the direct parent.

    In single inheritance it's always the parent. In multiple inheritance,
    it follows the full MRO chain, which enables cooperative multiple inheritance.

Q2: What is the difference between IS-A and HAS-A relationships?
A:  IS-A → Use inheritance. Dog IS-A Animal.
    HAS-A → Use composition. Car HAS-A Engine (not "Car IS-A Engine").

    Favor COMPOSITION over inheritance for flexible, testable code.
    Inheritance: "I am a type of X"
    Composition: "I contain/use an X"

Q3: How does Python avoid the diamond problem?
A:  Via C3 linearization MRO. Each class appears exactly once in the MRO,
    and Python searches left-to-right. There's no ambiguity.

Q4: What is cooperative multiple inheritance?
A:  When ALL classes in a hierarchy call super(), they form a CHAIN where
    each class cooperatively passes control to the next in the MRO.
    This is how Mixins work effectively in Python.
    If any class in the chain doesn't call super(), the chain breaks.
"""


# ══════════════════════════════════════════════════════════════════════════════
# PART G: ABSTRACT BASE CLASSES (ABC)
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS ABC?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ABC = Abstract Base Class — a class that CANNOT be instantiated directly.
It defines an INTERFACE (contract) that subclasses MUST implement.

WHY?
  Problem: You want to ensure ALL agents have a `run()` and `stop()` method.
  Without ABC: Subclass forgets to implement run() → only discovered at runtime.
  With ABC:    Subclass forgets to implement run() → error at class CREATION time.

HOW:
  from abc import ABC, abstractmethod

  class AbstractAgent(ABC):          # inherits ABC
      @abstractmethod
      def run(self) -> str: ...      # MUST be implemented in subclass
      @abstractmethod
      def stop(self) -> None: ...    # MUST be implemented in subclass

  class MyAgent(AbstractAgent):
      def run(self) -> str:          # ← MUST implement or TypeError
          return "running"
      def stop(self) -> None:        # ← MUST implement or TypeError
          pass

  AbstractAgent()  # TypeError: Can't instantiate abstract class

ABC vs PROTOCOL (Python 3.8+):
  ABC:      Nominal typing — class must INHERIT from ABC to count.
  Protocol: Structural typing — class just needs the RIGHT METHODS/ATTRS.
            (Covered in Typing Theory)

REAL LIFE ANALOGY:
  An ABC is like a JOB CONTRACT / INTERFACE AGREEMENT:
  "If you want to work here as a Driver, you MUST be able to:
    - drive()
    - park()
    - navigate()
  You don't get hired (instantiated) until you prove you can do all three."
"""

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Abstract interface for any LLM provider (OpenAI, Anthropic, Cohere, etc.)"""

    @abstractmethod
    def complete(self, prompt: str, max_tokens: int = 1000) -> str:
        """Complete a prompt. Must be implemented by all providers."""
        ...

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Count tokens for a given text."""
        ...

    @abstractmethod
    def get_model_name(self) -> str:
        """Return the model identifier."""
        ...

    # Concrete method on ABC — shared implementation
    def complete_with_retry(self, prompt: str, retries: int = 3) -> str:
        """Template method pattern — uses abstract methods."""
        for attempt in range(retries):
            try:
                return self.complete(prompt)
            except Exception as e:
                if attempt == retries - 1:
                    raise
                print(f"Retry {attempt + 1}: {e}")
        return ""

    def __repr__(self) -> str:
        return f"{type(self).__name__}(model={self.get_model_name()!r})"


class OpenAIProvider(LLMProvider):
    """Concrete implementation for OpenAI."""

    def __init__(self, model: str = "gpt-4", api_key: str = ""):
        self._model = model
        self._api_key = api_key

    def complete(self, prompt: str, max_tokens: int = 1000) -> str:
        # In reality: calls OpenAI API
        return f"[OpenAI/{self._model}] {prompt[:50]}..."

    def count_tokens(self, text: str) -> int:
        return len(text.split()) * 4 // 3

    def get_model_name(self) -> str:
        return self._model


class AnthropicProvider(LLMProvider):
    """Concrete implementation for Anthropic (Claude)."""

    def __init__(self, model: str = "claude-3-sonnet"):
        self._model = model

    def complete(self, prompt: str, max_tokens: int = 1000) -> str:
        return f"[Anthropic/{self._model}] {prompt[:50]}..."

    def count_tokens(self, text: str) -> int:
        # Claude uses different tokenizer
        return len(text.encode("utf-8")) // 4

    def get_model_name(self) -> str:
        return self._model


print(f"\nABC demonstration:")

# Cannot instantiate abstract class
try:
    provider = LLMProvider()  # TypeError!
except TypeError as e:
    print(f"Cannot instantiate ABC: {e}")

# Can instantiate concrete subclasses
openai = OpenAIProvider("gpt-4")
anthropic = AnthropicProvider("claude-3-opus")

print(f"OpenAI: {openai}")
print(f"Anthropic: {anthropic}")

# Polymorphism — both work with same interface
providers: list[LLMProvider] = [openai, anthropic]
for p in providers:
    result = p.complete("What is Python?")
    tokens = p.count_tokens("What is Python?")
    print(f"  {p.get_model_name()}: {result}, tokens={tokens}")


# ══════════════════════════════════════════════════════════════════════════════
# PART H: MIXINS
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT ARE MIXINS?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Mixin = A class that provides specific, reusable BEHAVIOR to be added to other
classes through multiple inheritance. Mixins don't stand alone — they are
designed to be MIXED IN to other classes.

WHY?
  Problem: Multiple unrelated classes need the same behavior (logging, caching, retry).
  Solution: Instead of duplicating code, write it once as a Mixin.

  Without Mixin: Every agent class has its own logging code (DRY violation).
  With Mixin:    LogMixin once, add to any class that needs logging.

HOW:
  class LogMixin:              # no __init__ or with minimal
      def log(self, msg):      # just behavior
          print(f"[LOG] {msg}")

  class Agent(LogMixin, BaseAgent):
      def run(self):
          self.log("Starting")  # from LogMixin!
          ...

RULES FOR GOOD MIXINS:
  1. No __init__ (or minimal — only for mixin-specific state)
  2. No direct instantiation — never used alone
  3. Specific, focused behavior (Single Responsibility)
  4. Always call super() to be cooperative

REAL LIFE ANALOGY:
  Mixins are like POWER STRIPS / USB ADAPTERS:
  - Your device (base class) has core functionality
  - You ADD capabilities by plugging in adapters:
    + LoggingAdapter  → now logs everything
    + CachingAdapter  → now caches results
    + RetryAdapter    → now retries on failure
  - Each adapter is small, focused, reusable across any device
"""

import functools
import time as _time


class LoggingMixin:
    """Mixin: adds structured logging to any class."""

    def log_info(self, message: str) -> None:
        print(f"  ℹ️  [{type(self).__name__}] {message}")

    def log_error(self, message: str) -> None:
        print(f"  ❌ [{type(self).__name__}] ERROR: {message}")

    def log_debug(self, message: str) -> None:
        print(f"  🔍 [{type(self).__name__}] DEBUG: {message}")


class CachingMixin:
    """Mixin: adds simple in-memory caching."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)   # cooperative!
        self._cache: dict = {}

    def cache_get(self, key: str):
        return self._cache.get(key)

    def cache_set(self, key: str, value) -> None:
        self._cache[key] = value

    def cache_clear(self) -> None:
        self._cache.clear()

    @property
    def cache_size(self) -> int:
        return len(self._cache)


class RetryMixin:
    """Mixin: adds retry-with-backoff to any class method."""

    def with_retry(self, func, max_attempts: int = 3, *args, **kwargs):
        for attempt in range(max_attempts):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt == max_attempts - 1:
                    raise
                wait = 2 ** attempt
                print(f"  ⟳  Retry {attempt + 1}/{max_attempts} after {wait}s: {e}")
                _time.sleep(wait)


class SmartLLMAgent(LoggingMixin, CachingMixin, RetryMixin, LLMProvider):
    """Full-featured agent: Logging + Caching + Retry + LLM interface."""

    def __init__(self, model: str = "gpt-4"):
        super().__init__()   # cooperative: hits CachingMixin, then others
        self._model = model

    def complete(self, prompt: str, max_tokens: int = 1000) -> str:
        cache_key = f"{prompt[:50]}:{max_tokens}"

        # Check cache first
        cached = self.cache_get(cache_key)
        if cached:
            self.log_info(f"Cache HIT for: {prompt[:30]}...")
            return cached

        # Log the call
        self.log_info(f"Calling LLM: {prompt[:30]}...")

        # Simulate LLM call
        result = f"[{self._model}] Response to: {prompt}"

        # Cache result
        self.cache_set(cache_key, result)
        return result

    def count_tokens(self, text: str) -> int:
        return len(text.split()) * 4 // 3

    def get_model_name(self) -> str:
        return self._model


print(f"\nMixin demonstration:")
print(f"SmartLLMAgent MRO: {[c.__name__ for c in SmartLLMAgent.__mro__]}")

agent = SmartLLMAgent("gpt-4")
r1 = agent.complete("What is Python?")
r2 = agent.complete("What is Python?")   # should hit cache
print(f"Cache size: {agent.cache_size}")
print(f"Is LLMProvider: {isinstance(agent, LLMProvider)}")
print(f"Has logging: {hasattr(agent, 'log_info')}")
print(f"Has caching: {hasattr(agent, 'cache_get')}")


# ══════════════════════════════════════════════════════════════════════════════
# PART I: DESCRIPTORS
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS A DESCRIPTOR?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

A Descriptor is an object that CONTROLS how an ATTRIBUTE is accessed on another class.

@property is built on descriptors — it's a descriptor factory.

DESCRIPTOR PROTOCOL (three methods):
  __get__(self, obj, objtype=None) → called on obj.attr GET
  __set__(self, obj, value)        → called on obj.attr = value SET
  __delete__(self, obj)            → called on del obj.attr DELETE

If an object defines __set__ or __delete__, it's a DATA descriptor.
If only __get__, it's a NON-DATA descriptor.

WHY USE DESCRIPTORS DIRECTLY (instead of @property)?
  @property is for ONE attribute on ONE class.
  Descriptor: REUSABLE validator that works on ANY class.

  Example: ValidatedInteger that ensures value is between min and max.
  You can use it for age, temperature, port_number, score — same code.

HOW:
  class ValidatedInteger:              # Descriptor class
      def __set_name__(self, owner, name):    # called when class is defined
          self.name = f"_{name}"              # where to store value
      def __get__(self, obj, objtype=None):
          return getattr(obj, self.name, None)
      def __set__(self, obj, value):
          if not isinstance(value, int):
              raise TypeError(f"{self.name} must be int")
          setattr(obj, self.name, value)

  class Config:
      port = ValidatedInteger()  # REUSED — no @property needed
      timeout = ValidatedInteger()

REAL LIFE ANALOGY:
  A Descriptor is like a FORM FIELD VALIDATOR in a web form:
  - You define the validator once (e.g., "must be a number between 1 and 100")
  - You can apply it to any field in any form (score, age, temperature)
  - Same validation logic, different field names
"""


class TypedAttribute:
    """Reusable type-checking descriptor."""

    def __init__(self, expected_type: type, nullable: bool = False):
        self.expected_type = expected_type
        self.nullable = nullable
        self.name: str = ""  # set by __set_name__

    def __set_name__(self, owner: type, name: str) -> None:
        # Called automatically when class is defined
        self.name = f"_{name}_value"

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self  # accessed on class, return descriptor
        return getattr(obj, self.name, None)

    def __set__(self, obj, value) -> None:
        if value is None and self.nullable:
            setattr(obj, self.name, value)
            return
        if not isinstance(value, self.expected_type):
            raise TypeError(
                f"{self.name!r} must be {self.expected_type.__name__}, "
                f"got {type(value).__name__}"
            )
        setattr(obj, self.name, value)


class RangeAttribute:
    """Reusable range-checking descriptor."""

    def __init__(self, min_val: float, max_val: float):
        self.min_val = min_val
        self.max_val = max_val
        self.name: str = ""

    def __set_name__(self, owner: type, name: str) -> None:
        self.name = f"_{name}_value"

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return getattr(obj, self.name, None)

    def __set__(self, obj, value) -> None:
        if not (self.min_val <= value <= self.max_val):
            raise ValueError(
                f"{self.name!r} must be {self.min_val}–{self.max_val}, got {value}"
            )
        setattr(obj, self.name, value)


class AgentSettings:
    """Uses descriptors for validated config — cleaner than @property for each field."""

    # Each of these uses the descriptor — same code, different attributes
    model_name  = TypedAttribute(str)
    max_tokens  = TypedAttribute(int)
    temperature = RangeAttribute(0.0, 2.0)
    top_p       = RangeAttribute(0.0, 1.0)
    max_retries = TypedAttribute(int)

    def __init__(
        self,
        model_name: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        top_p: float = 1.0,
        max_retries: int = 3,
    ):
        self.model_name = model_name      # → TypedAttribute.__set__
        self.max_tokens = max_tokens      # → TypedAttribute.__set__
        self.temperature = temperature    # → RangeAttribute.__set__
        self.top_p = top_p                # → RangeAttribute.__set__
        self.max_retries = max_retries    # → TypedAttribute.__set__

    def __repr__(self) -> str:
        return (
            f"AgentSettings(model={self.model_name!r}, "
            f"temp={self.temperature}, top_p={self.top_p})"
        )


print(f"\nDescriptor demonstration:")
settings = AgentSettings("gpt-4", temperature=0.5)
print(f"Settings: {settings}")

try:
    settings.temperature = 3.0  # out of range → RangeAttribute.__set__
except ValueError as e:
    print(f"Caught: {e}")

try:
    settings.model_name = 42    # wrong type → TypedAttribute.__set__
except TypeError as e:
    print(f"Caught: {e}")

settings.temperature = 1.2
print(f"After valid change: {settings}")


# ══════════════════════════════════════════════════════════════════════════════
# PART J: METACLASSES
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS A METACLASS?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EVERYTHING in Python is an object — including classes themselves.
The "class of a class" is called a METACLASS.

  object      → is an instance of → type
  int         → is an instance of → type
  str         → is an instance of → type
  YourClass   → is an instance of → type  (by default)

  type is the default metaclass. It creates class objects.

  Class creation process:
    class Dog(Animal):    Python calls:
        name = "Buddy"    type("Dog", (Animal,), {"name": "Buddy", ...})

  When you define a metaclass, YOU control how the class is created.

METACLASS HOOKS:
  __new__(mcs, name, bases, namespace)  → called when class is CREATED
                                          return the new class
  __init__(cls, name, bases, namespace) → called after class is CREATED
                                          can modify class
  __call__(cls, *args, **kwargs)        → called when class is INSTANTIATED
                                          cls(*args) → metaclass.__call__

WHY USE METACLASSES?
  - Singleton pattern (only one instance allowed)
  - Auto-register subclasses (plugin system, agent registry)
  - Enforce that subclasses implement required methods
  - Add class-level behavior without touching the class code

WARNING: Metaclasses are COMPLEX. Prefer:
  1. __init_subclass__  (simpler, Python 3.6+)
  2. Class decorators
  3. Metaclasses as last resort

REAL LIFE ANALOGY:
  Metaclass is like the FACTORY MACHINE that MAKES car factories.
  - type     = machine that makes factories (class factories)
  - Metaclass = custom machine with special rules (e.g., "all factories
                must have a safety inspector")
  - class    = factory made by that machine
  - object   = car made by the factory
"""


# ── 1. Metaclass for Singleton ──
class SingletonMeta(type):
    """Metaclass that ensures only ONE instance per class."""
    _instances: dict = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            # First time — create and store
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class AppConfig(metaclass=SingletonMeta):
    """Application-wide config — only one should exist."""

    def __init__(self, env: str = "production", debug: bool = False):
        self.env = env
        self.debug = debug
        print(f"  [AppConfig] Created with env={env}")


print(f"\nSingleton Metaclass:")
cfg1 = AppConfig("development", debug=True)
cfg2 = AppConfig("production")   # returns same instance!
print(f"Same instance: {cfg1 is cfg2}")   # True
print(f"cfg1.env: {cfg1.env}")            # development (first one wins)
print(f"cfg2.env: {cfg2.env}")            # development (same object)


# ── 2. __init_subclass__ (simpler alternative to metaclass for registration) ──
class AgentBase:
    """Uses __init_subclass__ to auto-register all agent types."""
    _registry: ClassVar[dict[str, type]] = {}

    def __init_subclass__(cls, agent_type: str = "", **kwargs):
        """Called automatically when a subclass is defined."""
        super().__init_subclass__(**kwargs)
        if agent_type:
            AgentBase._registry[agent_type] = cls
            print(f"  [Registry] Registered: {agent_type!r} → {cls.__name__}")

    @classmethod
    def create(cls, agent_type: str, **kwargs) -> "AgentBase":
        """Factory: create agent by type string."""
        if agent_type not in cls._registry:
            raise ValueError(f"Unknown agent type: {agent_type!r}. Known: {list(cls._registry)}")
        return cls._registry[agent_type](**kwargs)


class ResearchAgent(AgentBase, agent_type="research"):
    def run(self) -> str:
        return "Research result"

class CodingAgent(AgentBase, agent_type="coding"):
    def run(self) -> str:
        return "Code result"

class WritingAgent(AgentBase, agent_type="writing"):
    def run(self) -> str:
        return "Written content"


print(f"\n__init_subclass__ registration:")
print(f"Registry: {list(AgentBase._registry.keys())}")

agent = AgentBase.create("research")
print(f"Created: {type(agent).__name__}, result: {agent.run()}")

agent2 = AgentBase.create("coding")
print(f"Created: {type(agent2).__name__}, result: {agent2.run()}")


"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Q&A — Metaclasses, Descriptors, ABC
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q1: What is the difference between a metaclass and a class decorator?
A:  Both can modify class behavior, but:
    - Metaclass: affects class at CREATION TIME, affects ALL subclasses
    - Class decorator: applied after class is created, must be explicit on each class

    Use class decorator for simple one-class modifications.
    Use metaclass when you need automatic inheritance of behavior.

Q2: What is the difference between @abstractmethod in ABC vs just raising NotImplementedError?
A:  @abstractmethod: Python PREVENTS you from instantiating the class if the method
    isn't implemented. Error at class DEFINITION time (on first instantiation).

    raise NotImplementedError: Allows instantiation but fails at RUNTIME when called.

    @abstractmethod is better — fails early, clear error message.

Q3: What is a data descriptor vs non-data descriptor?
A:  Data descriptor: has both __get__ AND __set__ (or __delete__)
                     takes priority over instance __dict__
    Non-data descriptor: only __get__
                         instance __dict__ takes priority

    @property is a data descriptor (has __get__ + __set__ + __delete__).

Q4: When would you use __init_subclass__ vs a metaclass?
A:  __init_subclass__ (Python 3.6+): simpler, for auto-registering subclasses
                                      or enforcing requirements on subclasses
    Metaclass: for controlling the class CREATION PROCESS itself
               (e.g., Singleton, modifying class dict before class is created)

    Prefer __init_subclass__ unless you truly need metaclass power.

Q5: What is the difference between Mixin and Abstract Base Class?
A:  Mixin: provides CONCRETE BEHAVIOR (working methods). Usually small, focused.
           Not meant to be instantiated alone.
    ABC:   provides a CONTRACT/INTERFACE (abstract methods). Forces subclasses
           to implement specific methods. CAN have concrete methods too (template method).

    Often used together:
      class FullAgent(LogMixin, CacheMixin, AgentABC):
          def run(self): ...  # required by AgentABC
          # log_info() comes from LogMixin
          # cache_get() comes from CacheMixin
"""

print("\n✅ 03_OOP_Theory.py complete — all sections covered.")
