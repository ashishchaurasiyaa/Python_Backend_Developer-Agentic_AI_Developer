"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OOP ADVANCED — Descriptors, Metaclass, __new__, Async CM, Builder
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Topics Covered:
  1. Descriptor Protocol
  2. Metaclass
  3. __call__ method
  4. __new__ vs __init__
  5. Async Context Manager
  6. Thread-safe Singleton
  7. Builder Pattern + Fluent Interface
  8. __slots__ deep dive

Python Version: 3.10+
"""

import sys
import threading
import asyncio
import time
from contextlib import asynccontextmanager
from typing import Any, Optional


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 1: DESCRIPTOR PROTOCOL
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# ┌─────────────────────────────────────────────────┐
# │  WHY DESCRIPTORS?                               │
# │                                                 │
# │  Python's attribute lookup is NOT trivial.      │
# │  When you write obj.attr, Python calls          │
# │  type(obj).__mro__ and checks each class for    │
# │  a descriptor. Descriptors let you intercept    │
# │  get/set/delete on attributes at CLASS level,   │
# │  not instance level.                            │
# │                                                 │
# │  This is the engine behind:                     │
# │    - @property                                  │
# │    - @classmethod                               │
# │    - @staticmethod                              │
# │    - ORM fields (Django models, SQLAlchemy)     │
# │                                                 │
# │  DATA descriptor:     defines __set__ or        │
# │                        __delete__               │
# │    → takes priority over instance __dict__      │
# │                                                 │
# │  NON-DATA descriptor: defines only __get__      │
# │    → instance __dict__ takes priority over it   │
# └─────────────────────────────────────────────────┘

class ValidatedDescriptor:
    """
    Data descriptor that validates a numeric range.
    Stores value in the INSTANCE __dict__ via a private mangled key
    to avoid infinite recursion (can't store under same public name).
    """

    def __set_name__(self, owner, name):
        # Called by type.__new__ when class is created.
        # owner = the class that owns this descriptor
        # name  = the attribute name assigned on that class
        self.public_name = name
        self.private_name = f"_validated_{name}"  # storage key in instance __dict__

    def __get__(self, obj, objtype=None):
        # obj      = instance (None if accessed on the class itself)
        # objtype  = the class (always available)
        if obj is None:
            # Descriptor accessed on the class → return the descriptor itself
            return self
        return getattr(obj, self.private_name, None)

    def __set__(self, obj, value):
        # Called when instance.attr = value
        if not isinstance(value, (int, float)):
            raise TypeError(f"{self.public_name} must be numeric, got {type(value).__name__}")
        if not (self.min_val <= value <= self.max_val):
            raise ValueError(
                f"{self.public_name} must be between {self.min_val} and {self.max_val}, got {value}"
            )
        setattr(obj, self.private_name, value)

    def __delete__(self, obj):
        # Called when del instance.attr
        delattr(obj, self.private_name)

    def __init__(self, min_val, max_val):
        self.min_val = min_val
        self.max_val = max_val


class Temperature:
    celsius    = ValidatedDescriptor(-273.15, 1_000_000)
    humidity   = ValidatedDescriptor(0, 100)

    def __init__(self, celsius, humidity):
        self.celsius  = celsius    # triggers __set__
        self.humidity = humidity   # triggers __set__

    def __repr__(self):
        return f"Temperature(celsius={self.celsius}, humidity={self.humidity}%)"


# ── How @property is implemented using descriptors ──────────────────────────

class PropertyLike:
    """
    Minimal re-implementation of the built-in @property
    to show it is just a descriptor.
    """
    def __init__(self, fget=None, fset=None, fdel=None):
        self.fget = fget
        self.fset = fset
        self.fdel = fdel

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        if self.fget is None:
            raise AttributeError("unreadable attribute")
        return self.fget(obj)

    def __set__(self, obj, value):
        if self.fset is None:
            raise AttributeError("can't set attribute")
        self.fset(obj, value)

    def __delete__(self, obj):
        if self.fdel is None:
            raise AttributeError("can't delete attribute")
        self.fdel(obj)

    def setter(self, fset):
        return PropertyLike(self.fget, fset, self.fdel)

    def deleter(self, fdel):
        return PropertyLike(self.fget, self.fset, fdel)


class Circle:
    def __init__(self, radius):
        self._radius = radius

    @PropertyLike                   # our custom property-like descriptor
    def radius(self):
        return self._radius

    @radius.setter
    def radius(self, value):
        if value < 0:
            raise ValueError("radius cannot be negative")
        self._radius = value

    @radius.deleter
    def radius(self):
        del self._radius


def demo_descriptors():
    print("\n" + "=" * 55)
    print("SECTION 1: DESCRIPTOR PROTOCOL")
    print("=" * 55)

    t = Temperature(25.0, 60)
    print(f"Created: {t}")

    try:
        t.celsius = -300         # below absolute zero
    except ValueError as e:
        print(f"Validation error caught: {e}")

    try:
        t.humidity = "high"      # wrong type
    except TypeError as e:
        print(f"Type error caught: {e}")

    # Accessing descriptor on the class returns the descriptor object itself
    print(f"Class-level access returns descriptor: {type(Temperature.celsius).__name__}")

    c = Circle(5)
    print(f"Circle radius: {c.radius}")
    c.radius = 10
    print(f"After set: {c.radius}")

    # Non-data vs data descriptor priority
    print("\n--- Non-data vs Data Descriptor Priority ---")
    print("Data descriptor (has __set__) > instance __dict__ > non-data descriptor")


# ── Interview Q&A ────────────────────────────────────────────────────────────
DESCRIPTOR_QA = """
INTERVIEW Q&A — Descriptors
─────────────────────────────────────────────────────────────────────────────
Q1: What is a descriptor?
A:  Any object that defines __get__, __set__, or __delete__ and is set as a
    class attribute. Python's attribute lookup protocol delegates to it.

Q2: Data descriptor vs non-data descriptor?
A:  Data descriptor defines __set__ or __delete__ → has higher priority than
    the instance __dict__. Non-data descriptor defines only __get__ → instance
    __dict__ wins if the key exists there.

Q3: How does @property work internally?
A:  property() is a built-in data descriptor. When you write @property, Python
    creates a property object (descriptor) assigned to the class. __get__ calls
    fget, __set__ calls fset, __delete__ calls fdel.

Q4: What does __set_name__ do?
A:  Introduced in Python 3.6. Called automatically by type.__new__ when the
    class is created, passing the owner class and the attribute name. Saves
    writing a separate registration step.

Q5: Where are descriptors used in the standard library?
A:  property, classmethod, staticmethod, functions (methods are non-data
    descriptors), slots, Django ORM fields, SQLAlchemy Column objects.

Q6: Why store the value on the instance using a mangled name?
A:  If __set__ does setattr(obj, self.public_name, value) it calls __set__
    again → infinite recursion. Use a different key (private or mangled) to
    break the cycle.
"""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 2: METACLASS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# ┌─────────────────────────────────────────────────┐
# │  WHY METACLASS?                                 │
# │                                                 │
# │  Everything in Python is an object.             │
# │  Classes themselves are objects whose type      │
# │  is a metaclass.                                │
# │                                                 │
# │  type is the default metaclass of every class.  │
# │                                                 │
# │  class MyClass:      ≡    MyClass = type(       │
# │      pass                     "MyClass",        │
# │                                (object,),       │
# │                                {}               │
# │                            )                    │
# │                                                 │
# │  Use metaclass when you need to:                │
# │    - Automatically register subclasses          │
# │    - Enforce class-level constraints            │
# │    - Singleton pattern at the class level       │
# │    - Add methods/attributes to every subclass   │
# │    - Implement ORMs, plugin systems             │
# └─────────────────────────────────────────────────┘

# ── type() as metaclass ──────────────────────────────────────────────────────

# Dynamically create a class using type():
DynamicPoint = type(
    "DynamicPoint",                    # class name
    (object,),                         # base classes
    {                                  # class namespace / attributes
        "__init__": lambda self, x, y: setattr(self, "x", x) or setattr(self, "y", y),
        "__repr__": lambda self: f"DynamicPoint({self.x}, {self.y})",
    }
)


# ── SingletonMeta ────────────────────────────────────────────────────────────

class SingletonMeta(type):
    """
    Metaclass-based Singleton.
    __call__ on the metaclass controls what happens when you do ClassName().
    """
    _instances: dict = {}

    def __call__(cls, *args, **kwargs):
        # cls is the class being instantiated (not the metaclass itself)
        if cls not in cls._instances:
            # type.__call__ → __new__ → __init__
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class AppConfig(metaclass=SingletonMeta):
    def __init__(self, debug=False):
        self.debug = debug
        self.version = "1.0.0"

    def __repr__(self):
        return f"AppConfig(debug={self.debug}, version={self.version})"


# ── RegistryMeta: auto-register subclasses ───────────────────────────────────

class RegistryMeta(type):
    """
    Any class whose metaclass is RegistryMeta will have its subclasses
    automatically added to a registry dict keyed by class name.
    Useful for plugin systems, command dispatchers, codec registries.
    """
    registry: dict = {}

    def __init_subclass__(mcs, **kwargs):
        # This is the metaclass's own hook — not commonly needed here.
        super().__init_subclass__(**kwargs)

    def __new__(mcs, name, bases, namespace, **kwargs):
        cls = super().__new__(mcs, name, bases, namespace)
        # Register every class except the base class itself
        if bases:  # skip the root class (it has no bases in registry context)
            mcs.registry[name] = cls
            print(f"  [RegistryMeta] Registered class: {name}")
        return cls


class BaseHandler(metaclass=RegistryMeta):
    def handle(self, request):
        raise NotImplementedError


class JSONHandler(BaseHandler):
    def handle(self, request):
        return f"JSON handling: {request}"


class XMLHandler(BaseHandler):
    def handle(self, request):
        return f"XML handling: {request}"


class CSVHandler(BaseHandler):
    def handle(self, request):
        return f"CSV handling: {request}"


# ── __init_subclass__: simpler alternative to metaclass ─────────────────────

class Plugin:
    """
    __init_subclass__ is called on the BASE class every time a subclass
    is created. Much simpler than a full metaclass for registration.
    Available since Python 3.6.
    """
    _plugins: dict = {}

    def __init_subclass__(cls, plugin_name: str = "", **kwargs):
        super().__init_subclass__(**kwargs)
        name = plugin_name or cls.__name__
        Plugin._plugins[name] = cls
        print(f"  [Plugin] Registered plugin: {name} → {cls.__name__}")


class AudioPlugin(Plugin, plugin_name="audio"):
    def run(self): return "playing audio"


class VideoPlugin(Plugin, plugin_name="video"):
    def run(self): return "playing video"


def demo_metaclass():
    print("\n" + "=" * 55)
    print("SECTION 2: METACLASS")
    print("=" * 55)

    # type() dynamic class
    dp = DynamicPoint(3, 7)
    print(f"Dynamic class instance: {dp}")

    # Singleton
    cfg1 = AppConfig(debug=True)
    cfg2 = AppConfig(debug=False)  # returns same instance
    print(f"\nSingleton — same object? {cfg1 is cfg2}")
    print(f"AppConfig: {cfg1}")

    # Registry
    print("\n[RegistryMeta] Registry contents:")
    for name, cls in RegistryMeta.registry.items():
        print(f"  {name}: {cls}")

    handler = RegistryMeta.registry["JSONHandler"]()
    print(handler.handle({"key": "val"}))

    # Plugin system via __init_subclass__
    print("\n[Plugin] Registry:", Plugin._plugins)


# ── Interview Q&A ────────────────────────────────────────────────────────────
METACLASS_QA = """
INTERVIEW Q&A — Metaclass
─────────────────────────────────────────────────────────────────────────────
Q1: What is a metaclass?
A:  A metaclass is the class of a class. Just as objects are instances of
    classes, classes are instances of metaclasses. `type` is the default
    metaclass for all new-style classes.

Q2: What is the class creation sequence?
A:  1. Python sees `class Foo(Bar): ...`
    2. Determines metaclass (from keyword, base, or default type)
    3. Calls metaclass.__prepare__() → namespace dict
    4. Executes class body in that namespace
    5. Calls metaclass(name, bases, namespace) →
         metaclass.__new__() → creates the class object
         metaclass.__init__() → initialises it

Q3: When should you use a metaclass vs __init_subclass__?
A:  __init_subclass__ (Python 3.6+) covers most registration/enforcement
    use cases and is far simpler. Use a full metaclass when you need to
    modify the class namespace BEFORE the class body executes
    (__prepare__), or when you need to override __call__ on the class
    (e.g., Singleton), or when you need complete control over __new__.

Q4: Explain type(name, bases, dict).
A:  Dynamically creates a new class. Equivalent to writing the class
    statement. name → __name__, bases → __bases__, dict → namespace.

Q5: Can a class have multiple metaclasses?
A:  No. If two bases have conflicting metaclasses Python raises
    TypeError. The metaclass of the subclass must be a subclass of
    all base metaclasses (the "most derived" metaclass wins).

Q6: What is __prepare__ in a metaclass?
A:  A classmethod on the metaclass called before the class body is
    executed. Returns the namespace dict. Used by ordered namespaces
    (e.g., Python's enum uses an OrderedDict to preserve declaration
    order before 3.7 dict ordering guarantees).
"""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 3: __call__ METHOD
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# ┌─────────────────────────────────────────────────┐
# │  WHY __call__?                                  │
# │                                                 │
# │  When you write obj(), Python looks up          │
# │  type(obj).__call__(obj, ...).                  │
# │                                                 │
# │  Defining __call__ on a class makes its         │
# │  instances callable — they behave like          │
# │  functions but can carry state.                 │
# │                                                 │
# │  Key use cases:                                 │
# │    - Stateful function objects (counters,       │
# │      memoizers, rate limiters)                  │
# │    - Decorator classes (cleaner than closures   │
# │      when state is involved)                    │
# │    - Strategy pattern objects                   │
# │    - Partial application                        │
# └─────────────────────────────────────────────────┘

class CallCounter:
    """Callable class that counts how many times it is called."""

    def __init__(self, func):
        self.func    = func
        self.count   = 0
        self.__doc__ = func.__doc__
        self.__name__ = func.__name__

    def __call__(self, *args, **kwargs):
        self.count += 1
        print(f"  [{self.__name__}] call #{self.count}")
        return self.func(*args, **kwargs)

    def reset(self):
        self.count = 0


class Memoize:
    """Callable decorator class for caching results (memoization)."""

    def __init__(self, func):
        self.func  = func
        self.cache: dict = {}
        self.__name__ = func.__name__

    def __call__(self, *args):
        if args not in self.cache:
            self.cache[args] = self.func(*args)
            print(f"  [Memoize] Cache MISS for {self.__name__}{args}")
        else:
            print(f"  [Memoize] Cache HIT  for {self.__name__}{args}")
        return self.cache[args]


@Memoize
def fibonacci(n: int) -> int:
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)


class RateLimiter:
    """Callable that enforces a minimum interval between calls."""

    def __init__(self, func, min_interval: float = 1.0):
        self.func         = func
        self.min_interval = min_interval
        self._last_called = 0.0

    def __call__(self, *args, **kwargs):
        now     = time.monotonic()
        elapsed = now - self._last_called
        if elapsed < self.min_interval:
            raise RuntimeError(
                f"Rate limit: must wait {self.min_interval - elapsed:.2f}s before calling again"
            )
        self._last_called = now
        return self.func(*args, **kwargs)


def demo_call():
    print("\n" + "=" * 55)
    print("SECTION 3: __call__ METHOD")
    print("=" * 55)

    @CallCounter
    def greet(name):
        return f"Hello, {name}!"

    print(greet("Alice"))
    print(greet("Bob"))
    print(f"  Total calls: {greet.count}")

    print()
    # Memoize with fibonacci
    val = fibonacci(6)
    print(f"  fibonacci(6) = {val}")
    val = fibonacci(6)   # cached

    # RateLimiter
    def fetch_data(url):
        return f"data from {url}"

    limited_fetch = RateLimiter(fetch_data, min_interval=1.0)
    print(f"\n  {limited_fetch('http://api.example.com')}")
    try:
        limited_fetch("http://api.example.com")  # too soon
    except RuntimeError as e:
        print(f"  Rate limit error: {e}")


# ── Interview Q&A ────────────────────────────────────────────────────────────
CALL_QA = """
INTERVIEW Q&A — __call__
─────────────────────────────────────────────────────────────────────────────
Q1: What happens when you write obj()?
A:  Python evaluates type(obj).__call__(obj, ...). If __call__ is defined
    on the class, the instance becomes callable.

Q2: What is callable(obj)?
A:  Returns True if type(obj) defines __call__. Note: callable(obj) does
    NOT call obj(); it just checks.

Q3: How is __call__ used in the decorator pattern?
A:  A decorator class implements __call__ to wrap the decorated function.
    The class carries state (call count, cache) across invocations, which
    is cleaner than nested closures when state grows complex.

Q4: Difference between a callable instance and a closure?
A:  Both encapsulate state. A closure is a function + captured variables
    in its enclosing scope. A callable instance is a class instance with
    __call__, giving you all OOP features (inheritance, repr, multiple
    methods for introspection/reset). Use callable classes when state is
    non-trivial.

Q5: How does metaclass use __call__?
A:  When you write ClassName(), Python calls type(ClassName).__call__,
    which is the metaclass's __call__. This is how SingletonMeta intercepts
    class instantiation — it overrides __call__ on the metaclass level.
"""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 4: __new__ vs __init__
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# ┌─────────────────────────────────────────────────┐
# │  OBJECT CREATION FLOW                           │
# │                                                 │
# │  When you write MyClass(args):                  │
# │                                                 │
# │  1. type.__call__(MyClass, args) is invoked     │
# │  2. obj = MyClass.__new__(MyClass, args)        │
# │       → allocates memory, returns raw object   │
# │  3. if isinstance(obj, MyClass):                │
# │         MyClass.__init__(obj, args)             │
# │       → initialises the already-created obj    │
# │  4. Returns obj                                 │
# │                                                 │
# │  __new__ controls WHAT is created.             │
# │  __init__ controls HOW it is initialised.       │
# │                                                 │
# │  Use __new__ when:                              │
# │    - Subclassing immutable types (int, str,     │
# │      tuple, frozenset) — you must set the       │
# │      value in __new__ since immutables can't    │
# │      be changed after creation.                │
# │    - Singleton (return existing instance)       │
# │    - Metaclass __new__ to customise class       │
# │      creation.                                  │
# └─────────────────────────────────────────────────┘

# ── Singleton using __new__ ──────────────────────────────────────────────────

class SingletonNew:
    """Singleton implemented entirely with __new__."""
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            print(f"  [SingletonNew] Creating first instance of {cls.__name__}")
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, value: int = 0):
        # __init__ is called every time, even when __new__ returns the old instance.
        # Guard initialisation to prevent resetting state on subsequent calls.
        if not hasattr(self, "_initialised"):
            self.value       = value
            self._initialised = True
            print(f"  [SingletonNew] Initialised with value={value}")
        else:
            print(f"  [SingletonNew] __init__ called again but state preserved")


# ── Immutable subclass of tuple using __new__ ────────────────────────────────

class Vector(tuple):
    """
    Immutable 2D vector built on top of tuple.
    tuple is immutable — data must be set in __new__, not __init__.
    """

    def __new__(cls, x: float, y: float):
        # Pass the tuple data to tuple.__new__
        instance = super().__new__(cls, (x, y))
        return instance

    def __init__(self, x: float, y: float):
        # tuple.__init__ takes no extra args; x, y already stored via __new__
        # We CAN set additional attributes here (they go in instance __dict__)
        self._label = f"Vector({x}, {y})"
        super().__init__()

    @property
    def x(self): return self[0]

    @property
    def y(self): return self[1]

    def __add__(self, other):
        return Vector(self.x + other.x, self.y + other.y)

    def magnitude(self):
        return (self.x ** 2 + self.y ** 2) ** 0.5

    def __repr__(self):
        return self._label


# ── Tracing __new__ and __init__ call order ──────────────────────────────────

class CreationTrace:
    def __new__(cls, name):
        print(f"  [CreationTrace.__new__] cls={cls.__name__}, name={name!r}")
        obj = super().__new__(cls)   # object.__new__(cls)
        print(f"  [CreationTrace.__new__] raw object id={id(obj)}")
        return obj

    def __init__(self, name):
        print(f"  [CreationTrace.__init__] self={id(self)}, name={name!r}")
        self.name = name


def demo_new_vs_init():
    print("\n" + "=" * 55)
    print("SECTION 4: __new__ vs __init__")
    print("=" * 55)

    print("\n--- Creation trace ---")
    obj = CreationTrace("test")

    print("\n--- Singleton via __new__ ---")
    s1 = SingletonNew(42)
    s2 = SingletonNew(99)   # __init__ called again but state preserved
    print(f"  Same instance? {s1 is s2}")
    print(f"  Value: {s1.value}")

    print("\n--- Immutable Vector subclass ---")
    v1 = Vector(3.0, 4.0)
    v2 = Vector(1.0, 2.0)
    v3 = v1 + v2
    print(f"  v1={v1}, magnitude={v1.magnitude()}")
    print(f"  v1 + v2 = {v3}")
    print(f"  Is immutable tuple? {isinstance(v1, tuple)}")
    try:
        v1[0] = 99   # type: ignore
    except TypeError as e:
        print(f"  Immutability confirmed: {e}")


# ── Interview Q&A ────────────────────────────────────────────────────────────
NEW_INIT_QA = """
INTERVIEW Q&A — __new__ vs __init__
─────────────────────────────────────────────────────────────────────────────
Q1: What is the complete object creation flow?
A:  type.__call__(cls, *args) →
      obj = cls.__new__(cls, *args)   # allocate
      if isinstance(obj, cls):
          obj.__init__(*args)         # initialise
      return obj

Q2: When must you use __new__ instead of __init__?
A:  When subclassing IMMUTABLE types (int, str, bytes, tuple, frozenset).
    Their value is fixed at allocation time (in C); __init__ runs after
    creation when it's too late to change the value.

Q3: What does object.__new__ do?
A:  Allocates a new, blank instance of the class. It calls the C-level
    allocator and sets __class__. Does NOT initialise attributes.

Q4: If __new__ returns an object of a different type, does __init__ run?
A:  No. Python only calls __init__ if the object returned by __new__ is
    an instance of the class being created (isinstance check).

Q5: Singleton via __new__ vs metaclass — tradeoffs?
A:  __new__: simple, lives in the class itself, but __init__ still runs
    on every call (need a guard). Metaclass SingletonMeta: __init__ is
    called only once (metaclass controls the whole flow), cleaner
    semantics, but adds metaclass complexity.

Q6: Can you call __new__ without __init__ being called?
A:  Yes. object.__new__(cls) allocates but __init__ won't be called
    unless you call it explicitly. This is used in object.__reduce__
    (pickle), copy.copy, and some deserialization patterns.
"""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 5: ASYNC CONTEXT MANAGER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# ┌─────────────────────────────────────────────────┐
# │  WHY ASYNC CONTEXT MANAGER?                     │
# │                                                 │
# │  The regular context manager protocol           │
# │  (__enter__/__exit__) is synchronous.           │
# │  If acquisition/release of a resource is        │
# │  async (network, DB, file over async IO),       │
# │  you need __aenter__/__aexit__.                 │
# │                                                 │
# │  Used with:  async with obj as x:               │
# │                                                 │
# │  async def __aenter__(self) → resource          │
# │  async def __aexit__(self, exc_type, exc, tb)   │
# │              → bool (suppress exception or not) │
# │                                                 │
# │  @asynccontextmanager (from contextlib) gives   │
# │  generator-based shortcut (like @contextmanager │
# │  for sync CM).                                  │
# └─────────────────────────────────────────────────┘

class AsyncDBConnection:
    """
    Simulated async database connection.
    In production this wraps aiopg, asyncpg, motor, etc.
    """

    def __init__(self, dsn: str):
        self.dsn        = dsn
        self.connection = None
        self._closed    = True

    async def _connect(self):
        # Simulate async connection setup (network I/O)
        await asyncio.sleep(0.01)
        self.connection = {"dsn": self.dsn, "id": id(self)}
        self._closed    = False
        print(f"  [DB] Connected to {self.dsn}")

    async def _disconnect(self):
        await asyncio.sleep(0.01)
        self.connection = None
        self._closed    = True
        print(f"  [DB] Disconnected from {self.dsn}")

    async def execute(self, query: str):
        if self._closed:
            raise RuntimeError("Not connected")
        await asyncio.sleep(0.005)
        return f"result of: {query}"

    async def __aenter__(self):
        await self._connect()
        return self          # `as conn` gets the connection object

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._disconnect()
        if exc_type is not None:
            print(f"  [DB] Exception during context: {exc_type.__name__}: {exc_val}")
        return False         # do NOT suppress exceptions


# ── DB Connection Pool ───────────────────────────────────────────────────────

class AsyncDBPool:
    """
    Minimal async connection pool using asyncio.Semaphore to cap concurrency.
    In production: use asyncpg.create_pool() or aiopg.create_pool().
    """

    def __init__(self, dsn: str, max_connections: int = 5):
        self.dsn             = dsn
        self._semaphore      = asyncio.Semaphore(max_connections)
        self._pool: list     = []
        self._max            = max_connections

    async def __aenter__(self):
        await self._semaphore.acquire()
        conn = AsyncDBConnection(self.dsn)
        await conn._connect()
        self._pool.append(conn)
        return conn

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._pool:
            conn = self._pool.pop()
            await conn._disconnect()
        self._semaphore.release()
        return False


# ── @asynccontextmanager shortcut ────────────────────────────────────────────

@asynccontextmanager
async def managed_transaction(dsn: str):
    """
    Generator-based async CM via @asynccontextmanager.
    Code before yield = __aenter__.
    Code after yield  = __aexit__.
    """
    conn = AsyncDBConnection(dsn)
    await conn._connect()
    try:
        print("  [Transaction] BEGIN")
        yield conn
        print("  [Transaction] COMMIT")
    except Exception as e:
        print(f"  [Transaction] ROLLBACK due to: {e}")
        raise
    finally:
        await conn._disconnect()


async def demo_async_cm():
    print("\n" + "=" * 55)
    print("SECTION 5: ASYNC CONTEXT MANAGER")
    print("=" * 55)

    print("\n--- Direct __aenter__/__aexit__ ---")
    async with AsyncDBConnection("postgresql://localhost/mydb") as conn:
        result = await conn.execute("SELECT * FROM users LIMIT 10")
        print(f"  Query result: {result}")

    print("\n--- @asynccontextmanager ---")
    async with managed_transaction("postgresql://localhost/mydb") as conn:
        result = await conn.execute("INSERT INTO orders VALUES (1, 'pending')")
        print(f"  {result}")

    print("\n--- Connection pool (simulated concurrent access) ---")
    pool = AsyncDBPool("postgresql://localhost/mydb", max_connections=2)

    async def worker(task_id: int):
        async with pool as conn:
            result = await conn.execute(f"SELECT task {task_id}")
            print(f"  Worker-{task_id}: {result}")

    await asyncio.gather(worker(1), worker(2), worker(3))


# ── Interview Q&A ────────────────────────────────────────────────────────────
ASYNC_CM_QA = """
INTERVIEW Q&A — Async Context Manager
─────────────────────────────────────────────────────────────────────────────
Q1: What are __aenter__ and __aexit__?
A:  The async counterparts of __enter__/__exit__. __aenter__ is awaited
    at the start of `async with`, __aexit__ is awaited on exit (normal or
    exceptional).

Q2: What does __aexit__ return value mean?
A:  If it returns a truthy value, the exception (if any) is suppressed.
    Return False (or None) to let exceptions propagate.

Q3: When would you use @asynccontextmanager?
A:  When the setup/teardown logic is straightforward and you don't want to
    write a full class. It turns an async generator function (with exactly
    one yield) into an async context manager.

Q4: How does asyncio.Semaphore limit connection pool concurrency?
A:  Semaphore(n) allows at most n concurrent acquires. Coroutines beyond
    n await until a slot is released, naturally throttling DB connections.

Q5: Can you use a synchronous context manager inside an async function?
A:  Yes. `async with` requires __aenter__/__aexit__. Plain `with` inside
    an async function works fine for sync CMs (file open, threading.Lock,
    etc.) — it just blocks the event loop if the I/O takes time.

Q6: How is async with different from try/finally?
A:  Both guarantee cleanup. `async with` is more expressive, reusable,
    nestable, and separates resource management from business logic. It
    also works with `contextlib.AsyncExitStack` for dynamic composition.
"""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 6: THREAD-SAFE SINGLETON PATTERN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# ┌─────────────────────────────────────────────────┐
# │  WHY THREAD-SAFETY MATTERS FOR SINGLETON?       │
# │                                                 │
# │  Without a lock, two threads can both check     │
# │  `if _instance is None` concurrently, both      │
# │  find it None, and both create an instance —    │
# │  violating the singleton contract.              │
# │                                                 │
# │  Three standard Python approaches:              │
# │                                                 │
# │  1. threading.Lock (double-checked locking)     │
# │  2. Metaclass with Lock                         │
# │  3. Module-level singleton (simplest — Python   │
# │     imports are thread-safe due to the GIL +    │
# │     importlib lock)                             │
# └─────────────────────────────────────────────────┘

# ── Approach 1: threading.Lock with double-checked locking ───────────────────

class ThreadSafeSingletonLock:
    _instance   = None
    _lock       = threading.Lock()

    def __new__(cls):
        # First check (no lock) avoids lock overhead once instance exists
        if cls._instance is None:
            with cls._lock:
                # Second check (with lock) prevents double creation
                if cls._instance is None:
                    print("  [Lock Singleton] Creating instance")
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_ready"):
            self._ready = True
            self.data   = {}


# ── Approach 2: Metaclass with Lock ─────────────────────────────────────────

class ThreadSafeSingletonMeta(type):
    _instances: dict     = {}
    _lock:      threading.Lock = threading.Lock()

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            with cls._lock:
                if cls not in cls._instances:
                    print(f"  [Meta Singleton] Creating {cls.__name__}")
                    cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class DatabaseService(metaclass=ThreadSafeSingletonMeta):
    def __init__(self, host="localhost"):
        self.host        = host
        self.connections = 0

    def connect(self):
        self.connections += 1
        return f"Connection #{self.connections} to {self.host}"


# ── Approach 3: Module-level singleton (simplest) ────────────────────────────

class _ModuleSingleton:
    """
    Private class — consumers import the module-level instance.
    Python's import system guarantees a module is loaded once.
    All imports of this module share the same _config_instance.
    """
    def __init__(self):
        self.settings: dict = {}
        print("  [Module Singleton] Instance created at import time")

    def get(self, key, default=None):
        return self.settings.get(key, default)

    def set(self, key, value):
        self.settings[key] = value


# Module-level instance — created once when this module is first imported
_config_instance = _ModuleSingleton()

def get_config() -> _ModuleSingleton:
    """Public accessor for the module-level singleton."""
    return _config_instance


def demo_thread_safe_singleton():
    print("\n" + "=" * 55)
    print("SECTION 6: THREAD-SAFE SINGLETON")
    print("=" * 55)

    # Approach 1: Lock
    results = []
    def create_lock_singleton():
        results.append(ThreadSafeSingletonLock())

    threads = [threading.Thread(target=create_lock_singleton) for _ in range(5)]
    for t in threads: t.start()
    for t in threads: t.join()
    ids = {id(r) for r in results}
    print(f"\n  Approach 1 (Lock): unique instances = {len(ids)} (should be 1)")

    # Approach 2: Metaclass
    results2 = []
    def create_meta_singleton():
        results2.append(DatabaseService("db.prod.internal"))

    threads2 = [threading.Thread(target=create_meta_singleton) for _ in range(5)]
    for t in threads2: t.start()
    for t in threads2: t.join()
    ids2 = {id(r) for r in results2}
    print(f"  Approach 2 (Meta): unique instances = {len(ids2)} (should be 1)")

    # Approach 3: Module-level
    cfg = get_config()
    cfg.set("env", "production")
    cfg2 = get_config()
    print(f"  Approach 3 (Module): same object? {cfg is cfg2}")
    print(f"  Config env: {cfg2.get('env')}")


# ── Interview Q&A ────────────────────────────────────────────────────────────
SINGLETON_QA = """
INTERVIEW Q&A — Thread-Safe Singleton
─────────────────────────────────────────────────────────────────────────────
Q1: What is double-checked locking and why is it used?
A:  Check if instance exists WITHOUT a lock first (fast path). Only acquire
    the lock if the first check shows None. Check AGAIN inside the lock
    (because another thread may have created it between the first check and
    lock acquisition). Reduces lock contention after the instance is created.

Q2: Is the GIL enough to make Python singletons thread-safe?
A:  No. The GIL prevents true parallel execution of bytecode but does NOT
    make compound operations (check-then-create) atomic. Two threads can
    interleave at the bytecode level. Use threading.Lock.

Q3: Why is the module-level singleton approach thread-safe?
A:  CPython's import system uses an importlib lock — a module is executed
    at most once, even if imported concurrently. The module-level instance
    is created during module loading, which is protected by this lock.

Q4: When would you NOT want a Singleton?
A:  When testing (shared state bleeds between tests), when multiple configs
    are needed (e.g., test vs prod DB), in highly concurrent async code
    where you prefer connection pools. Singleton = global state = coupling.

Q5: How does Borg pattern differ from Singleton?
A:  Borg (a.k.a. Monostate) allows multiple instances but they share the
    same __dict__. Done by setting
        self.__dict__ = cls._shared_state
    in __init__. All instances see the same attributes. Easier to test
    (can create fresh instances) but behaves like a singleton for state.
"""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 7: BUILDER PATTERN + FLUENT INTERFACE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# ┌─────────────────────────────────────────────────┐
# │  WHY BUILDER + FLUENT INTERFACE?                │
# │                                                 │
# │  Builder separates CONSTRUCTION of a complex    │
# │  object from its REPRESENTATION. Fluent         │
# │  interface (method chaining) makes client code  │
# │  read like a DSL.                               │
# │                                                 │
# │  Each method returns `self` → next method       │
# │  can be chained immediately.                    │
# │                                                 │
# │  Used in:                                       │
# │    - ORM query builders (SQLAlchemy, Django ORM)│
# │    - Test assertion libraries (assertpy, etc.)  │
# │    - HTTP client builders                       │
# │    - Configuration DSLs                         │
# └─────────────────────────────────────────────────┘

class QueryBuilder:
    """
    Fluent SQL query builder.
    Demonstrates Builder pattern with method chaining.
    """

    def __init__(self):
        self._table:   str       = ""
        self._columns: list[str] = ["*"]
        self._where:   list[str] = []
        self._order:   str       = ""
        self._limit:   Optional[int] = None
        self._offset:  Optional[int] = None
        self._joins:   list[str] = []
        self._params:  list      = []

    def from_table(self, table: str) -> "QueryBuilder":
        self._table = table
        return self   # <- key: return self for chaining

    def select(self, *columns: str) -> "QueryBuilder":
        self._columns = list(columns)
        return self

    def where(self, condition: str, *params) -> "QueryBuilder":
        self._where.append(condition)
        self._params.extend(params)
        return self

    def join(self, table: str, on: str, join_type: str = "INNER") -> "QueryBuilder":
        self._joins.append(f"{join_type} JOIN {table} ON {on}")
        return self

    def order_by(self, column: str, direction: str = "ASC") -> "QueryBuilder":
        self._order = f"{column} {direction}"
        return self

    def limit(self, n: int) -> "QueryBuilder":
        self._limit = n
        return self

    def offset(self, n: int) -> "QueryBuilder":
        self._offset = n
        return self

    def build(self) -> tuple[str, list]:
        """
        Terminal operation — consumes the builder and returns the
        final SQL string and parameter list.
        """
        if not self._table:
            raise ValueError("Table name is required (.from_table())")

        parts = [f"SELECT {', '.join(self._columns)}"]
        parts.append(f"FROM {self._table}")

        for join in self._joins:
            parts.append(join)

        if self._where:
            parts.append("WHERE " + " AND ".join(self._where))

        if self._order:
            parts.append(f"ORDER BY {self._order}")

        if self._limit is not None:
            parts.append(f"LIMIT {self._limit}")

        if self._offset is not None:
            parts.append(f"OFFSET {self._offset}")

        sql = "\n  ".join(parts)
        return sql, self._params

    def __repr__(self) -> str:
        sql, params = self.build()
        return f"QueryBuilder(\n  {sql}\n  params={params}\n)"


class HttpRequestBuilder:
    """Another fluent builder — for constructing HTTP requests."""

    def __init__(self, base_url: str = ""):
        self._base_url = base_url
        self._path     = ""
        self._method   = "GET"
        self._headers: dict = {}
        self._body:    Any  = None
        self._timeout: float = 30.0

    def method(self, m: str) -> "HttpRequestBuilder":
        self._method = m.upper()
        return self

    def path(self, p: str) -> "HttpRequestBuilder":
        self._path = p
        return self

    def header(self, key: str, value: str) -> "HttpRequestBuilder":
        self._headers[key] = value
        return self

    def json_body(self, data: dict) -> "HttpRequestBuilder":
        self._body = data
        self._headers["Content-Type"] = "application/json"
        return self

    def timeout(self, seconds: float) -> "HttpRequestBuilder":
        self._timeout = seconds
        return self

    def build(self) -> dict:
        return {
            "method":  self._method,
            "url":     self._base_url + self._path,
            "headers": self._headers,
            "body":    self._body,
            "timeout": self._timeout,
        }


def demo_builder():
    print("\n" + "=" * 55)
    print("SECTION 7: BUILDER PATTERN + FLUENT INTERFACE")
    print("=" * 55)

    sql, params = (
        QueryBuilder()
        .from_table("orders o")
        .select("o.id", "o.created_at", "c.name AS customer_name", "SUM(oi.amount) AS total")
        .join("customers c", "c.id = o.customer_id")
        .join("order_items oi", "oi.order_id = o.id", join_type="LEFT")
        .where("o.status = %s", "pending")
        .where("o.created_at >= %s", "2024-01-01")
        .order_by("o.created_at", "DESC")
        .limit(25)
        .offset(0)
        .build()
    )
    print(f"\nGenerated SQL:\n  {sql}")
    print(f"Params: {params}")

    request = (
        HttpRequestBuilder("https://api.example.com")
        .method("POST")
        .path("/v1/orders")
        .header("Authorization", "Bearer token123")
        .header("Accept", "application/json")
        .json_body({"item": "widget", "qty": 5})
        .timeout(15.0)
        .build()
    )
    print(f"\nHTTP Request: {request}")


# ── Interview Q&A ────────────────────────────────────────────────────────────
BUILDER_QA = """
INTERVIEW Q&A — Builder Pattern + Fluent Interface
─────────────────────────────────────────────────────────────────────────────
Q1: What problem does the Builder pattern solve?
A:  Constructors with many optional parameters become unwieldy (telescoping
    constructor anti-pattern). Builder separates step-by-step construction
    from the final object, and fluent interface makes the steps readable.

Q2: How do you implement method chaining in Python?
A:  Each method modifies internal state and returns `self`. The caller can
    immediately invoke the next method on the returned reference.

Q3: What is the difference between Builder and Factory pattern?
A:  Factory creates an object in one step, hiding the concrete type.
    Builder constructs complex objects step-by-step, accumulating
    configuration before a terminal `.build()` call produces the result.

Q4: How does Python's ORM (Django/SQLAlchemy) use the fluent interface?
A:  Django's QuerySet: Model.objects.filter(...).exclude(...).order_by(...)
    .values(...) — each call returns a new (lazy) QuerySet.
    SQLAlchemy: session.query(Model).filter(...).limit(n).all()
    Both are lazy — SQL is only emitted when the terminal call (.all(),
    iteration, .build()) is made.

Q5: Is method chaining the same as fluent interface?
A:  Method chaining is the MECHANISM (return self). Fluent interface is the
    DESIGN GOAL — making the API read like a natural language sentence.
    Fluent interfaces usually use method chaining, but not every chain
    is a fluent interface (e.g., list.append returns None intentionally).
"""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 8: __slots__ DEEP DIVE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# ┌─────────────────────────────────────────────────┐
# │  WHY __slots__?                                 │
# │                                                 │
# │  By default every Python instance has a         │
# │  __dict__ — a hash map of attribute names to    │
# │  values. This is flexible but wastes memory     │
# │  when you have millions of instances.           │
# │                                                 │
# │  __slots__ replaces __dict__ with a fixed,      │
# │  C-level array of slot descriptors. Benefits:  │
# │                                                 │
# │    - Lower memory per instance (~40-60 bytes    │
# │      saved per slot in CPython)                 │
# │    - Faster attribute access (array index       │
# │      vs hash lookup)                            │
# │    - Prevents accidental attribute creation     │
# │      (strict interface)                         │
# │                                                 │
# │  Drawbacks:                                     │
# │    - Can't add new attributes at runtime        │
# │    - Inheritance requires care                  │
# │    - Breaks pickle if __reduce__/               │
# │      __getstate__/__setstate__ not defined      │
# │    - Mixins/multiple inheritance gets tricky    │
# └─────────────────────────────────────────────────┘

class PointWithDict:
    """Regular class — has __dict__."""
    def __init__(self, x: float, y: float, z: float):
        self.x = x
        self.y = y
        self.z = z


class PointWithSlots:
    """Slots class — no __dict__, fixed attributes only."""
    __slots__ = ("x", "y", "z")

    def __init__(self, x: float, y: float, z: float):
        self.x = x
        self.y = y
        self.z = z


# ── Slots with inheritance ────────────────────────────────────────────────────

class Base:
    __slots__ = ("base_attr",)

    def __init__(self):
        self.base_attr = "I am from Base"


class ChildWithSlots(Base):
    """
    IMPORTANT: If child does NOT define __slots__, it gets __dict__
    AND inherits the parent's slots. This somewhat defeats the purpose.
    To keep full slot benefits, EVERY class in the hierarchy must
    define __slots__.
    """
    __slots__ = ("child_attr",)   # only NEW slots here; base_attr is inherited

    def __init__(self):
        super().__init__()
        self.child_attr = "I am from Child"


class ChildWithoutSlots(Base):
    """This child gets __dict__ + inherits base_attr slot."""
    def __init__(self):
        super().__init__()
        self.extra = "added dynamically — allowed because __dict__ exists"


# ── Slots with __weakref__ ────────────────────────────────────────────────────

class WeakRefSafe:
    """
    Slots classes don't support weak references by default.
    Add '__weakref__' to __slots__ explicitly to enable them.
    """
    __slots__ = ("value", "__weakref__")

    def __init__(self, value):
        self.value = value


def demo_slots():
    print("\n" + "=" * 55)
    print("SECTION 8: __slots__ DEEP DIVE")
    print("=" * 55)

    # Memory comparison
    pd = PointWithDict(1.0, 2.0, 3.0)
    ps = PointWithSlots(1.0, 2.0, 3.0)

    size_dict  = sys.getsizeof(pd) + sys.getsizeof(pd.__dict__)
    size_slots = sys.getsizeof(ps)

    print(f"\n  PointWithDict  size: {size_dict} bytes (object + __dict__)")
    print(f"  PointWithSlots size: {size_slots} bytes (no __dict__)")
    print(f"  Savings per instance: ~{size_dict - size_slots} bytes")

    # Has __dict__?
    print(f"\n  PointWithDict  has __dict__: {hasattr(pd, '__dict__')}")
    print(f"  PointWithSlots has __dict__: {hasattr(ps, '__dict__')}")

    # Can't add new attributes to slotted class
    pd.new_attr = "dynamic"   # works fine
    print(f"\n  Added dynamic attr to dict class: {pd.new_attr}")
    try:
        ps.new_attr = "dynamic"   # type: ignore
    except AttributeError as e:
        print(f"  Can't add attr to slots class: {e}")

    # Inheritance
    c = ChildWithSlots()
    print(f"\n  ChildWithSlots: base_attr={c.base_attr}, child_attr={c.child_attr}")
    print(f"  Has __dict__? {hasattr(c, '__dict__')}")   # False — both use slots

    c2 = ChildWithoutSlots()
    print(f"\n  ChildWithoutSlots: base_attr={c2.base_attr}, extra={c2.extra}")
    print(f"  Has __dict__? {hasattr(c2, '__dict__')}")  # True

    # Large-scale memory simulation
    N = 100_000
    import tracemalloc
    tracemalloc.start()
    dict_list = [PointWithDict(i, i, i) for i in range(N)]
    snap1 = tracemalloc.take_snapshot()

    tracemalloc.clear_traces()
    slot_list = [PointWithSlots(i, i, i) for i in range(N)]
    snap2 = tracemalloc.take_snapshot()
    tracemalloc.stop()

    stats1 = snap1.statistics("lineno")
    stats2 = snap2.statistics("lineno")
    total1 = sum(s.size for s in stats1) / 1024
    total2 = sum(s.size for s in stats2) / 1024
    print(f"\n  {N:,} PointWithDict  instances: ~{total1:.1f} KB")
    print(f"  {N:,} PointWithSlots instances: ~{total2:.1f} KB")
    del dict_list, slot_list


# ── Interview Q&A ────────────────────────────────────────────────────────────
SLOTS_QA = """
INTERVIEW Q&A — __slots__
─────────────────────────────────────────────────────────────────────────────
Q1: What does __slots__ do?
A:  Replaces the per-instance __dict__ with a fixed set of slot descriptors
    defined at the class level. Reduces memory and speeds attribute access.

Q2: How much memory does __slots__ save?
A:  A typical empty __dict__ is ~200 bytes in CPython. Each slot descriptor
    is ~56 bytes. For a class with 3 attributes: __dict__ approach ≈ 264 bytes
    per instance vs slots ≈ 56 * 3 = 168 bytes. Savings compound with N.

Q3: Can you mix __slots__ and __dict__?
A:  Yes — add '__dict__' to __slots__. This gives you a fixed set of fast
    slots AND a dynamic __dict__. Rarely done; used when you want fast
    access for known attrs but still need dynamic flexibility.

Q4: What happens with inheritance and __slots__?
A:  If ANY class in the MRO lacks __slots__, instances get __dict__. To
    fully benefit, every class in the hierarchy must declare __slots__
    (using empty __slots__ = () for classes that add no new slots).

Q5: Why do slots break pickle by default?
A:  pickle uses __dict__ to capture state. Slotted instances have no
    __dict__. Add __getstate__/__setstate__ or __reduce__ to support pickle.

Q6: Do slots affect class variables?
A:  No. Slots only affect INSTANCE attributes. Class-level variables are
    still stored in the class __dict__ (class has its own __dict__ always).

Q7: Can descriptors and __slots__ conflict?
A:  Yes — you cannot have a slot and a descriptor with the same name on
    the same class, because __slots__ itself creates a data descriptor for
    each slot name.
"""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COMBINED INTERVIEW Q&A — CROSS-TOPIC QUESTIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

COMBINED_QA = """
╔═════════════════════════════════════════════════════════════════════════════╗
║          COMBINED INTERVIEW Q&A — OOP ADVANCED (ALL TOPICS)                ║
╚═════════════════════════════════════════════════════════════════════════════╝

CROSS-TOPIC & SYSTEM DESIGN QUESTIONS
──────────────────────────────────────────────────────────────────────────────

Q1: Walk through the FULL lifecycle of `obj = MyClass(42)`.
A:
    1. Python evaluates MyClass → a class object (instance of a metaclass)
    2. type(MyClass).__call__(MyClass, 42) is invoked
       (if SingletonMeta, its __call__ runs first)
    3. obj = MyClass.__new__(MyClass, 42)
         → allocates raw object, sets __class__
         → if __slots__ defined, slot array allocated instead of __dict__
    4. if isinstance(obj, MyClass):
           MyClass.__init__(obj, 42)
         → initialises attributes
         → if @property is set here, its descriptor __set__ is called
    5. obj returned to caller

Q2: How would you implement an ORM field (like Django's IntegerField)?
A:  Use a descriptor. IntegerField is a data descriptor (defines __get__,
    __set__, __delete__). It validates types, stores the value in the
    instance's __dict__ under a private key, and uses __set_name__ to
    know which attribute name it's assigned to. The metaclass (ModelBase
    in Django) collects all field descriptors and builds migration schemas.

Q3: How do @property, @classmethod, @staticmethod relate to descriptors?
A:  All three are data descriptors implemented in C:
    - property.__get__(obj, type): if obj is None → return self (the property);
      else → call fget(obj).
    - classmethod.__get__(obj, type): returns a bound method where the first
      arg is always the class, not the instance.
    - staticmethod.__get__(obj, type): returns the plain function, no binding.

Q4: Design a plugin system that supports both sync and async plugins.
A:  Use __init_subclass__ for auto-registration. Each plugin declares
    `is_async = False` (or True). The dispatcher checks the flag and
    either calls plugin.run() directly or `await plugin.run_async()`.
    An AsyncContextManager can manage plugin lifecycle (startup/shutdown).

Q5: How does Python's MRO interact with descriptors?
A:  Attribute lookup walks the MRO for EACH class and checks its __dict__
    for a data descriptor FIRST (before instance __dict__), then falls back
    to instance __dict__, then non-data descriptors in the MRO.
    MRO order (C3 linearization) determines which class's descriptor wins
    in multiple inheritance.

Q6: When would you combine metaclass + descriptor + __slots__?
A:  In a high-performance ORM or dataclass-like library. The metaclass
    processes the class body to find declared fields (descriptors), and
    sets __slots__ to the list of field names, giving you automatic
    validation + minimal memory footprint. Example: attrs library does
    exactly this.

Q7: What is the `__init_subclass__` execution order?
A:  When Python creates a subclass:
    1. Metaclass.__new__ creates the class
    2. Metaclass.__init__ initialises it
    3. For each base class (in MRO order) that defines __init_subclass__,
       it is called with the new subclass as the first argument.
    This happens AFTER the class is created, so the class is fully formed.

Q8: Explain the GIL's impact on thread-safe singleton.
A:  The GIL ensures only one thread executes Python bytecode at a time,
    but does NOT make multi-step operations atomic. Between
    `if instance is None` and `instance = cls()` the GIL can be released
    (e.g., on I/O or after N bytecodes). Therefore a threading.Lock is
    still necessary for correct singleton behaviour in multi-threaded code.

Q9: Async context manager vs regular context manager — when to choose?
A:  Use async CM when the enter/exit operations involve I/O-bound work
    (network, DB, file via async IO). Using a sync CM with blocking I/O
    inside an async function blocks the event loop, degrading concurrency.
    Use regular CM for pure CPU/memory operations (locks, tempfiles, etc.)
    even inside async functions.

Q10: How would you make QueryBuilder immutable (each chain returns new instance)?
A:  Instead of mutating `self`, copy the builder state (e.g., `import copy;
    new = copy.copy(self)`) and modify the copy before returning it.
    This makes each intermediate builder a value object — safe to store,
    branch, and reuse. Django's QuerySet is lazy + immutable in this way.
"""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MAIN — RUN ALL DEMOS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def print_qa(section_qa: str):
    print("\n" + section_qa)


def main():
    print("\n")
    print("━" * 55)
    print("  OOP ADVANCED — Day 19 Demos")
    print("━" * 55)

    # Section 1
    demo_descriptors()
    print_qa(DESCRIPTOR_QA)

    # Section 2
    print("\n[Registering subclasses during class definition...]")
    demo_metaclass()
    print_qa(METACLASS_QA)

    # Section 3
    demo_call()
    print_qa(CALL_QA)

    # Section 4
    demo_new_vs_init()
    print_qa(NEW_INIT_QA)

    # Section 5 — async
    print("\n" + "=" * 55)
    print("SECTION 5: ASYNC CONTEXT MANAGER")
    print("=" * 55)
    print("  [Running async demo via asyncio.run()]")
    asyncio.run(demo_async_cm())
    print_qa(ASYNC_CM_QA)

    # Section 6
    demo_thread_safe_singleton()
    print_qa(SINGLETON_QA)

    # Section 7
    demo_builder()
    print_qa(BUILDER_QA)

    # Section 8
    demo_slots()
    print_qa(SLOTS_QA)

    # Combined Q&A
    print_qa(COMBINED_QA)

    print("\n" + "━" * 55)
    print("  All demos complete.")
    print("━" * 55 + "\n")


if __name__ == "__main__":
    main()
