"""
DAY 34 — Metaclasses, Descriptors, __init_subclass__
Architecture Level: Senior Python Backend + Agentic AI

Metaclasses are classes of classes — they control HOW classes are created.
Used in: Django ORM, SQLAlchemy, Pydantic, dataclasses, ABC.
"""


# ═══════════════════════════════════════════════════════
# PART A: Metaclasses — what they are
# ═══════════════════════════════════════════════════════

# Everything in Python is an object, including classes.
# type is the metaclass of all classes.

print(type(int))       # <class 'type'>
print(type(str))       # <class 'type'>
print(type(list))      # <class 'type'>

# type() can CREATE classes dynamically:
MyClass = type("MyClass", (object,), {"x": 10, "greet": lambda self: "hello"})
obj = MyClass()
print(MyClass.x, obj.greet())  # 10  hello


# ─────────────────────────────────────────────
# 1. Custom metaclass
# ─────────────────────────────────────────────

class SingletonMeta(type):
    """
    Metaclass that makes any class a singleton.
    Only one instance exists per class.
    Used for: DB connections, config, logging, registries.
    """
    _instances: dict = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class DatabasePool(metaclass=SingletonMeta):
    def __init__(self):
        self.connections = []
        print("  [DB] Pool created")

    def add_connection(self, conn: str):
        self.connections.append(conn)


class RedisPool(metaclass=SingletonMeta):
    def __init__(self):
        self.host = "localhost"
        print("  [Redis] Pool created")


print("\nSingleton demo:")
db1 = DatabasePool()
db2 = DatabasePool()    # returns same instance
db1.add_connection("conn_1")
print(f"db1 is db2: {db1 is db2}")           # True
print(f"db2.connections: {db2.connections}")  # ['conn_1'] — same object


# ─────────────────────────────────────────────
# 2. Metaclass for auto-registration (Plugin pattern)
# ─────────────────────────────────────────────

class ToolMeta(type):
    """
    Metaclass that registers all subclasses automatically.
    This is how LangChain tools and similar frameworks work.
    """
    _registry: dict[str, type] = {}

    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)
        # Don't register the base class itself
        if bases:
            tool_name = namespace.get("tool_name", name.lower())
            mcs._registry[tool_name] = cls
            print(f"  [Registry] Registered tool: {tool_name}")
        return cls

    @classmethod
    def get_tool(mcs, name: str) -> type | None:
        return mcs._registry.get(name)

    @classmethod
    def list_tools(mcs) -> list[str]:
        return list(mcs._registry.keys())


class BaseTool(metaclass=ToolMeta):
    tool_name = "base"

    def execute(self, **kwargs) -> str:
        raise NotImplementedError


class WebSearchTool(BaseTool):
    tool_name = "web_search"

    def execute(self, query: str = "") -> str:
        return f"Search results for: {query}"


class CalculatorTool(BaseTool):
    tool_name = "calculator"

    def execute(self, expression: str = "") -> str:
        return f"Result: {eval(expression)}"  # noqa


print(f"\nRegistered tools: {ToolMeta.list_tools()}")
tool_cls = ToolMeta.get_tool("web_search")
if tool_cls:
    tool = tool_cls()
    print(tool.execute(query="Python metaclasses"))


# ═══════════════════════════════════════════════════════
# PART B: __init_subclass__ — lighter than metaclasses
# ═══════════════════════════════════════════════════════

class Agent:
    """
    __init_subclass__ is called when a class is subclassed.
    Cleaner than metaclasses for most registration/validation use cases.
    Available since Python 3.6.
    """
    _agent_registry: dict[str, type] = {}

    def __init_subclass__(cls, agent_type: str = "", **kwargs):
        super().__init_subclass__(**kwargs)
        if agent_type:
            Agent._agent_registry[agent_type] = cls
            print(f"  [Agent] Registered: {agent_type} → {cls.__name__}")

    @classmethod
    def create(cls, agent_type: str) -> "Agent":
        agent_cls = cls._agent_registry.get(agent_type)
        if not agent_cls:
            raise ValueError(f"Unknown agent type: {agent_type}")
        return agent_cls()

    def run(self, task: str) -> str:
        raise NotImplementedError


class ResearchAgent(Agent, agent_type="researcher"):
    def run(self, task: str) -> str:
        return f"[Research] {task}"


class CodingAgent(Agent, agent_type="coder"):
    def run(self, task: str) -> str:
        return f"[Code] {task}"


class ReviewAgent(Agent, agent_type="reviewer"):
    def run(self, task: str) -> str:
        return f"[Review] {task}"


print(f"\nAgent registry: {list(Agent._agent_registry.keys())}")
agent = Agent.create("researcher")
print(agent.run("Analyze Python trends 2025"))


# ═══════════════════════════════════════════════════════
# PART C: Descriptors — how @property works internally
# ═══════════════════════════════════════════════════════

class Validated:
    """
    Non-data descriptor with validation.
    Descriptors: objects whose __get__/__set__/__delete__ control attribute access.
    """

    def __set_name__(self, owner, name):
        """Called when descriptor is assigned to a class attribute."""
        self.name = name
        self.private_name = f"_{name}"

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self  # accessed on class, not instance
        return getattr(obj, self.private_name, None)

    def __set__(self, obj, value):
        self.validate(value)
        setattr(obj, self.private_name, value)

    def validate(self, value):
        pass  # override in subclasses


class PositiveNumber(Validated):
    def validate(self, value):
        if not isinstance(value, (int, float)) or value <= 0:
            raise ValueError(f"{self.name} must be a positive number, got {value!r}")


class Range(Validated):
    def __init__(self, min_val, max_val):
        self.min_val = min_val
        self.max_val = max_val

    def validate(self, value):
        if not self.min_val <= value <= self.max_val:
            raise ValueError(
                f"{self.name} must be between {self.min_val} and {self.max_val}, got {value}"
            )


class LLMSettings:
    """Class using descriptors for validation — Pydantic does this internally."""
    temperature: float = Range(0.0, 2.0)
    max_tokens: int    = PositiveNumber()
    top_p: float       = Range(0.0, 1.0)

    def __init__(self, temperature: float, max_tokens: int, top_p: float = 1.0):
        self.temperature = temperature  # calls Range.__set__
        self.max_tokens = max_tokens    # calls PositiveNumber.__set__
        self.top_p = top_p


settings = LLMSettings(temperature=0.7, max_tokens=1000)
print(f"\nSettings: temp={settings.temperature}, tokens={settings.max_tokens}")

try:
    bad = LLMSettings(temperature=3.0, max_tokens=100)
except ValueError as e:
    print(f"Validation: {e}")

try:
    settings.max_tokens = -5
except ValueError as e:
    print(f"Validation: {e}")


# ─────────────────────────────────────────────
# INTERVIEW CHEAT SHEET
# ─────────────────────────────────────────────
# Metaclass        → controls class CREATION (Django ORM, SQLAlchemy)
# __init_subclass__→ hook when class is SUBCLASSED (lighter than metaclass)
# Descriptor       → controls ATTRIBUTE ACCESS (__get__, __set__, __delete__)
# @property        → descriptor that calls a function on access
#
# Data descriptor      has __set__ or __delete__ (property, Validated above)
# Non-data descriptor  only has __get__ (functions/methods)
#
# Lookup order:
# 1. Data descriptors from class/MRO
# 2. Instance __dict__
# 3. Non-data descriptors from class/MRO
#
# REAL WORLD:
# Metaclass    → SQLAlchemy Base, Django Model, Pydantic BaseModel (internals)
# __init_subclass__ → Plugin systems, framework extension points
# Descriptors  → Django fields (CharField, IntegerField), SQLAlchemy Column
