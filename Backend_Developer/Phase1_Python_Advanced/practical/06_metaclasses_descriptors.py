"""
Metaclasses, Descriptors & Python Object Model — Practical
=============================================================
40 LPA Backend Python Developer Interview Prep
Theory: Hinglish | Code: English (Production-quality)

Usage:
    python 06_metaclasses_descriptors.py          # Run all sections
    python 06_metaclasses_descriptors.py 1        # Section 1 only
    python 06_metaclasses_descriptors.py 1 3 5    # Multiple sections
    python 06_metaclasses_descriptors.py all       # All sections

Sections:
    1  - Dynamic Class Creation (type() as class factory)
    2  - __new__ Patterns (Singleton, Immutable subclasses)
    3  - Custom Metaclass (Plugin registry, ORM fields)
    4  - __init_subclass__ (Auto-registration, validation)
    5  - Descriptors (Validated attributes, lazy loading)
    6  - property Internals (From-scratch implementation)
    7  - __slots__ Benchmark (Memory savings)
    8  - Generic[T] + Protocol (Type-safe generics)
"""

from __future__ import annotations

import sys
import functools
import threading
import tracemalloc
import time
import re
from typing import (
    TypeVar, Generic, Protocol, runtime_checkable,
    Optional, Any, Iterator
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def section_header(n: int, title: str) -> None:
    print(f"\n{'='*65}")
    print(f"  SECTION {n}: {title}")
    print(f"{'='*65}")


def sub_header(title: str) -> None:
    print(f"\n  --- {title} ---")


def demo(label: str, *exprs):
    """Print label and evaluate expressions."""
    print(f"  {label}")
    for expr in exprs:
        print(f"    {expr}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Dynamic Class Creation
# ─────────────────────────────────────────────────────────────────────────────

def run_section_1():
    section_header(1, "Dynamic Class Creation — type() as Class Factory")

    sub_header("1a: Everything is an object — type() introspection")
    for obj in [42, "hello", [1, 2], int, str, list, type]:
        print(f"    type({str(obj)!r:20}) = {type(obj)}")

    print()
    demo("type(type) → type is its own metaclass:",
         f"type(type) = {type(type)}")

    # ── 1b: type(name, bases, dict) — 3-argument form ──
    sub_header("1b: type(name, bases, dict) — create class at runtime")

    def person_init(self, name: str, age: int) -> None:
        self.name = name
        self.age = age

    def person_greet(self) -> str:
        return f"Namaste, mera naam {self.name} hai, umar {self.age} saal."

    def person_repr(self) -> str:
        return f"Person(name={self.name!r}, age={self.age})"

    # Identical to: class Person(object): ...
    Person = type('Person', (object,), {
        '__init__': person_init,
        '__repr__': person_repr,
        'greet': person_greet,
        'species': 'Homo sapiens',
    })

    p = Person("Rahul", 28)
    print(f"  Created: {p}")
    print(f"  Greet:   {p.greet()}")
    print(f"  Species: {Person.species}")
    print(f"  type(Person): {type(Person)}")
    print(f"  Person.__bases__: {Person.__bases__}")

    # ── 1c: Inheritance with type() ──
    sub_header("1c: Dynamic inheritance — Employee extends Person")

    def employee_repr(self) -> str:
        return f"Employee({self.name!r}, {self.company!r})"

    Employee = type('Employee', (Person,), {
        '__repr__': employee_repr,
        'company': 'TechCorp India',
        'get_ctc': lambda self, lpa: f"₹{lpa} LPA at {self.company}",
    })

    e = Employee("Priya", 30)
    print(f"  {e}")
    print(f"  {e.greet()}")  # Inherited from Person
    print(f"  {e.get_ctc(40)}")
    print(f"  Employee.__mro__: {[c.__name__ for c in Employee.__mro__]}")

    # ── 1d: Class creation tracing with metaclass ──
    sub_header("1d: Class creation lifecycle — __prepare__ → __new__ → __init__")

    class TracingMeta(type):
        @classmethod
        def __prepare__(mcs, name, bases):
            print(f"    __prepare__({name!r}) → returning namespace dict")
            return {}

        def __new__(mcs, name, bases, namespace):
            print(f"    __new__({name!r}) — keys: {[k for k in namespace if not k.startswith('__')]}")
            return super().__new__(mcs, name, bases, namespace)

        def __init__(cls, name, bases, namespace):
            print(f"    __init__({name!r}) — class object ready: {cls}")
            super().__init__(name, bases, namespace)

    print("  Defining 'Widget' with TracingMeta:")

    class Widget(metaclass=TracingMeta):
        color = "red"
        size = 10

        def draw(self) -> str:
            return f"Drawing {self.color} widget of size {self.size}"

    w = Widget()
    print(f"  Widget instance: {w.draw()}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: __new__ Patterns
# ─────────────────────────────────────────────────────────────────────────────

def run_section_2():
    section_header(2, "__new__ Patterns — Singleton, Immutable, Factory")

    # ── 2a: __new__ execution order ──
    sub_header("2a: Execution order — __new__ → __init__")

    class TracedObject:
        def __new__(cls, value):
            print(f"    __new__(cls={cls.__name__!r}, value={value})")
            instance = super().__new__(cls)
            instance._id = id(instance)
            return instance

        def __init__(self, value):
            print(f"    __init__(self.id={self._id}, value={value})")
            self.value = value

    print("  Creating TracedObject(99):")
    obj = TracedObject(99)
    print(f"  Result: obj.value={obj.value}, obj._id={obj._id}")

    # ── 2b: __new__ returns wrong type ──
    sub_header("2b: __new__ returns different type → __init__ NOT called")

    class MaybeInt:
        def __new__(cls, x):
            if x < 0:
                print(f"    __new__: x={x} < 0, returning str — __init__ will NOT run")
                return f"Negative({x})"
            print(f"    __new__: x={x} >= 0, creating MaybeInt — __init__ will run")
            return super().__new__(cls)

        def __init__(self, x):
            print(f"    __init__: x={x}")
            self.x = x

    print("  MaybeInt(5):")
    pos = MaybeInt(5)
    print(f"    type={type(pos).__name__}, pos.x={pos.x}")

    print("  MaybeInt(-3):")
    neg = MaybeInt(-3)
    print(f"    type={type(neg).__name__}, neg={neg!r}")

    # ── 2c: Singleton via __new__ ──
    sub_header("2c: Singleton pattern using __new__")

    class AppConfig:
        _instance: Optional[AppConfig] = None
        _initialized: bool = False

        def __new__(cls, *args, **kwargs):
            if cls._instance is None:
                print("    Creating new AppConfig instance...")
                cls._instance = super().__new__(cls)
            else:
                print("    Returning existing AppConfig instance.")
            return cls._instance

        def __init__(self, debug: bool = False, db_url: str = "sqlite:///app.db"):
            if self._initialized:
                return
            self.debug = debug
            self.db_url = db_url
            self._initialized = True
            print(f"    Initialized: debug={debug}, db_url={db_url!r}")

    print("  First call: AppConfig(debug=True, db_url='postgresql://prod')")
    c1 = AppConfig(debug=True, db_url="postgresql://prod")
    print("  Second call: AppConfig(debug=False, db_url='sqlite:///test')")
    c2 = AppConfig(debug=False, db_url="sqlite:///test")
    print(f"    c1 is c2: {c1 is c2}")
    print(f"    c1.debug: {c1.debug}  (not overwritten)")
    print(f"    c1.db_url: {c1.db_url!r}  (first initialization kept)")

    # ── 2d: Immutable int subclass ──
    sub_header("2d: Immutable int subclass — PositiveInt")

    class PositiveInt(int):
        """int subclass — must use __new__ because int is immutable."""

        def __new__(cls, value: int) -> PositiveInt:
            if value <= 0:
                raise ValueError(f"PositiveInt requires value > 0, got {value}")
            return super().__new__(cls, value)

        def __repr__(self) -> str:
            return f"PositiveInt({int(self)})"

        def safe_divide(self, other: int) -> float:
            return int(self) / other

    p = PositiveInt(42)
    print(f"  PositiveInt(42) = {p!r}")
    print(f"  p + 8 = {p + 8}, type = {type(p + 8).__name__}")  # returns int
    print(f"  isinstance(p, int): {isinstance(p, int)}")
    print(f"  p.safe_divide(6): {p.safe_divide(6)}")

    try:
        PositiveInt(-5)
    except ValueError as exc:
        print(f"  PositiveInt(-5) → ValueError: {exc}")

    # ── 2e: Immutable tuple subclass ──
    sub_header("2e: Immutable Point using tuple subclass")

    class ImmutablePoint(tuple):
        """Immutable (x, y) point — value set in __new__."""

        def __new__(cls, x: float, y: float) -> ImmutablePoint:
            return super().__new__(cls, (x, y))

        @property
        def x(self) -> float:
            return self[0]

        @property
        def y(self) -> float:
            return self[1]

        def distance_to(self, other: ImmutablePoint) -> float:
            return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2) ** 0.5

        def translate(self, dx: float, dy: float) -> ImmutablePoint:
            return ImmutablePoint(self.x + dx, self.y + dy)

        def __repr__(self) -> str:
            return f"Point({self.x}, {self.y})"

    origin = ImmutablePoint(0, 0)
    p1 = ImmutablePoint(3, 4)
    p2 = p1.translate(1, 1)
    print(f"  origin: {origin}")
    print(f"  p1: {p1}, p2: {p2}")
    print(f"  distance(p1, origin): {p1.distance_to(origin):.2f}")
    print(f"  Tuple operations: p1[0]={p1[0]}, len(p1)={len(p1)}")
    try:
        p1.x = 99  # type: ignore
    except AttributeError:
        print("  p1.x = 99 → AttributeError (immutable!)")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Custom Metaclass
# ─────────────────────────────────────────────────────────────────────────────

def run_section_3():
    section_header(3, "Custom Metaclass — Plugin Registry & ORM Fields")

    # ── 3a: Auto-registration plugin system ──
    sub_header("3a: Auto-registration metaclass — Plugin system")

    class PluginMeta(type):
        _registry: dict[str, type] = {}

        def __new__(mcs, name: str, bases: tuple, namespace: dict) -> type:
            cls = super().__new__(mcs, name, bases, namespace)
            if bases:  # Don't register the base class itself
                plugin_id = namespace.get('plugin_id', name.lower())
                mcs._registry[plugin_id] = cls
                print(f"    Registered plugin: {plugin_id!r} → {cls.__name__}")
            return cls

        @classmethod
        def get_plugin(mcs, plugin_id: str) -> Optional[type]:
            return mcs._registry.get(plugin_id)

        @classmethod
        def create(mcs, plugin_id: str, *args, **kwargs) -> Any:
            cls = mcs.get_plugin(plugin_id)
            if cls is None:
                available = list(mcs._registry.keys())
                raise ValueError(f"Unknown plugin {plugin_id!r}. Available: {available}")
            return cls(*args, **kwargs)

        @classmethod
        def list_plugins(mcs) -> list[str]:
            return list(mcs._registry.keys())

    class Notifier(metaclass=PluginMeta):
        """Base notifier — not registered."""
        plugin_id = None

        def notify(self, message: str) -> str:
            raise NotImplementedError

    class EmailNotifier(Notifier):
        plugin_id = "email"

        def __init__(self, smtp_host: str = "smtp.gmail.com"):
            self.smtp_host = smtp_host

        def notify(self, message: str) -> str:
            return f"[EMAIL via {self.smtp_host}] {message}"

    class SMSNotifier(Notifier):
        plugin_id = "sms"

        def __init__(self, provider: str = "Twilio"):
            self.provider = provider

        def notify(self, message: str) -> str:
            return f"[SMS via {self.provider}] {message}"

    class SlackNotifier(Notifier):
        plugin_id = "slack"

        def notify(self, message: str) -> str:
            return f"[SLACK] #{message}"

    print(f"\n  Available plugins: {PluginMeta.list_plugins()}")
    for pid in PluginMeta.list_plugins():
        notifier = PluginMeta.create(pid)
        print(f"  {notifier.notify('Deployment successful!')}")

    # ── 3b: Metaclass with __call__ — Singleton per class ──
    sub_header("3b: Metaclass __call__ — Thread-safe Singleton")

    class SingletonMeta(type):
        _instances: dict[type, Any] = {}
        _lock = threading.Lock()

        def __call__(cls, *args, **kwargs):
            if cls not in cls._instances:
                with cls._lock:
                    if cls not in cls._instances:
                        instance = super().__call__(*args, **kwargs)
                        cls._instances[cls] = instance
            return cls._instances[cls]

    class DatabasePool(metaclass=SingletonMeta):
        def __init__(self, max_conn: int = 10):
            self.max_conn = max_conn
            self._connections: list = []
            print(f"    DBPool created with max_conn={max_conn}")

    class CacheClient(metaclass=SingletonMeta):
        def __init__(self, host: str = "localhost"):
            self.host = host
            print(f"    CacheClient created, host={host!r}")

    print("  Creating DatabasePool twice:")
    db1 = DatabasePool(20)
    db2 = DatabasePool(5)
    print(f"  db1 is db2: {db1 is db2}, max_conn: {db1.max_conn}")

    print("  Creating CacheClient twice:")
    c1 = CacheClient("redis.prod.com")
    c2 = CacheClient("redis.test.com")
    print(f"  c1 is c2: {c1 is c2}, host: {c1.host!r}")

    # ── 3c: ORM-like metaclass ──
    sub_header("3c: ORM-like metaclass — Django-style field system")

    class ORMField:
        def __init__(self, col_type: str = "TEXT", nullable: bool = True,
                     default: Any = None, primary_key: bool = False):
            self.col_type = col_type
            self.nullable = nullable
            self.default = default
            self.primary_key = primary_key
            self.name: str = ""  # set by __set_name__

        def __set_name__(self, owner: type, name: str) -> None:
            self.name = name

        def __get__(self, obj: Any, objtype: type = None) -> Any:
            if obj is None:
                return self
            return obj.__dict__.get(self.name, self.default)

        def __set__(self, obj: Any, value: Any) -> None:
            if not self.nullable and value is None:
                raise ValueError(f"Column {self.name!r} cannot be NULL")
            obj.__dict__[self.name] = value

    class CharField(ORMField):
        def __init__(self, max_length: int = 255, **kwargs):
            super().__init__(f"VARCHAR({max_length})", **kwargs)
            self.max_length = max_length

        def __set__(self, obj: Any, value: Any) -> None:
            if value is not None and len(str(value)) > self.max_length:
                raise ValueError(f"{self.name!r}: max length {self.max_length} exceeded")
            super().__set__(obj, value)

    class IntegerField(ORMField):
        def __init__(self, **kwargs):
            super().__init__("INTEGER", **kwargs)

    class ModelMeta(type):
        def __new__(mcs, name: str, bases: tuple, namespace: dict) -> type:
            fields: dict[str, ORMField] = {}

            # Collect fields from bases (inheritance)
            for base in bases:
                if hasattr(base, '_meta_fields'):
                    fields.update(base._meta_fields)

            # Collect fields from current class
            for key, val in namespace.items():
                if isinstance(val, ORMField):
                    fields[key] = val

            cls = super().__new__(mcs, name, bases, namespace)
            cls._meta_fields = fields
            cls._meta_table = name.lower() + 's'
            return cls

    class BaseModel(metaclass=ModelMeta):
        id = IntegerField(primary_key=True, nullable=True)

        def __init__(self, **kwargs: Any) -> None:
            for name, field in self._meta_fields.items():
                value = kwargs.get(name, field.default)
                if not field.nullable and not field.primary_key and value is None:
                    raise ValueError(f"Field {name!r} is required (NOT NULL)")
                self.__dict__[name] = value

        def to_dict(self) -> dict:
            return {name: self.__dict__.get(name) for name in self._meta_fields}

        @classmethod
        def create_table_sql(cls) -> str:
            col_defs = []
            for name, field in cls._meta_fields.items():
                parts = [name, field.col_type]
                if field.primary_key:
                    parts.append("PRIMARY KEY AUTOINCREMENT")
                elif not field.nullable:
                    parts.append("NOT NULL")
                if field.default is not None and not field.primary_key:
                    default = f"'{field.default}'" if isinstance(field.default, str) else field.default
                    parts.append(f"DEFAULT {default}")
                col_defs.append(" ".join(parts))
            return f"CREATE TABLE {cls._meta_table} (\n  " + ",\n  ".join(col_defs) + "\n);"

        def insert_sql(self) -> tuple[str, list]:
            cols = [n for n, f in self._meta_fields.items() if not f.primary_key]
            vals = [self.__dict__.get(n) for n in cols]
            placeholders = ", ".join("?" * len(cols))
            sql = f"INSERT INTO {self._meta_table} ({', '.join(cols)}) VALUES ({placeholders})"
            return sql, vals

    class User(BaseModel):
        username = CharField(max_length=50, nullable=False)
        email = CharField(max_length=255, nullable=False)
        age = IntegerField(nullable=True, default=None)
        bio = CharField(max_length=500, nullable=True, default="")

    class Product(BaseModel):
        name = CharField(max_length=200, nullable=False)
        price = IntegerField(nullable=False)
        stock = IntegerField(nullable=False, default=0)

    print(f"\n  {User.create_table_sql()}")
    print(f"\n  {Product.create_table_sql()}")

    u = User(username="rahul_28", email="rahul@example.com", age=28)
    print(f"\n  User data: {u.to_dict()}")
    sql, params = u.insert_sql()
    print(f"  INSERT SQL: {sql}")
    print(f"  Params: {params}")

    try:
        u.username = "x" * 60  # Exceeds max_length=50
    except ValueError as exc:
        print(f"  Validation error: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: __init_subclass__
# ─────────────────────────────────────────────────────────────────────────────

def run_section_4():
    section_header(4, "__init_subclass__ — Auto-registration & Validation")

    # ── 4a: Basic __init_subclass__ ──
    sub_header("4a: Basic __init_subclass__ — subclass registration")

    class Event:
        _handlers: dict[str, type] = {}

        def __init_subclass__(cls, event_type: str = None, **kwargs) -> None:
            super().__init_subclass__(**kwargs)
            etype = event_type or cls.__name__.lower().replace('event', '')
            cls._event_type = etype
            Event._handlers[etype] = cls
            print(f"    Registered event handler: {etype!r} → {cls.__name__}")

        @classmethod
        def handle(cls, event_type: str, **data) -> str:
            handler_cls = cls._handlers.get(event_type)
            if handler_cls is None:
                return f"No handler for {event_type!r}"
            handler = handler_cls()
            return handler.process(**data)

        def process(self, **data) -> str:
            raise NotImplementedError

    class UserCreatedEvent(Event, event_type="user.created"):
        def process(self, user_id: int = 0, email: str = "") -> str:
            return f"Welcome email sent to {email!r} (user_id={user_id})"

    class OrderPlacedEvent(Event, event_type="order.placed"):
        def process(self, order_id: int = 0, total: float = 0.0) -> str:
            return f"Order #{order_id} confirmed, total=₹{total:,.2f}"

    class PaymentFailedEvent(Event, event_type="payment.failed"):
        def process(self, payment_id: str = "", reason: str = "") -> str:
            return f"Payment {payment_id!r} failed: {reason}"

    print(f"\n  Registered handlers: {list(Event._handlers.keys())}")
    print(f"\n  {Event.handle('user.created', user_id=42, email='priya@example.com')}")
    print(f"  {Event.handle('order.placed', order_id=1001, total=4999.99)}")
    print(f"  {Event.handle('payment.failed', payment_id='PAY_123', reason='Insufficient funds')}")

    # ── 4b: Enforce required attributes ──
    sub_header("4b: Enforce required attributes & methods at class definition time")

    class Repository:
        """Subclasses must define model_name and implement CRUD methods."""

        def __init_subclass__(cls, abstract: bool = False, **kwargs) -> None:
            super().__init_subclass__(**kwargs)
            if abstract:
                return  # Skip validation for intermediate abstract classes

            # Check required class attribute
            if not hasattr(cls, 'model_name'):
                raise TypeError(f"{cls.__name__} must define 'model_name' class attribute")

            # Check required methods
            required = ['get_by_id', 'save', 'delete', 'list_all']
            missing = [m for m in required if m not in cls.__dict__]
            if missing:
                raise TypeError(
                    f"{cls.__name__} must implement: {', '.join(missing)}"
                )

            print(f"    Repository validated: {cls.__name__} (model={cls.model_name!r})")

    class UserRepository(Repository):
        model_name = "User"

        def get_by_id(self, id: int) -> dict:
            return {"id": id, "name": "Mock User"}

        def save(self, obj: dict) -> bool:
            return True

        def delete(self, id: int) -> bool:
            return True

        def list_all(self) -> list:
            return [{"id": 1}, {"id": 2}]

    class ProductRepository(Repository):
        model_name = "Product"

        def get_by_id(self, id: int) -> dict:
            return {"id": id, "name": "Widget", "price": 999}

        def save(self, obj: dict) -> bool:
            return True

        def delete(self, id: int) -> bool:
            return True

        def list_all(self) -> list:
            return [{"id": 1, "name": "Widget"}]

    ur = UserRepository()
    print(f"\n  UserRepository.get_by_id(5): {ur.get_by_id(5)}")
    print(f"  ProductRepository.list_all(): {ProductRepository().list_all()}")

    # Try creating bad repo
    try:
        class BadRepository(Repository):
            model_name = "Bad"
            # Missing all required methods!
            pass
    except TypeError as exc:
        print(f"\n  BadRepository → TypeError: {exc}")

    # ── 4c: kwargs flow through inheritance ──
    sub_header("4c: kwargs through multi-level inheritance")

    class Serializable:
        def __init_subclass__(cls, format: str = "json", **kwargs) -> None:
            super().__init_subclass__(**kwargs)
            cls._format = format
            print(f"    Serializable: {cls.__name__} format={format!r}")

    class Cacheable:
        def __init_subclass__(cls, ttl: int = 60, **kwargs) -> None:
            super().__init_subclass__(**kwargs)
            cls._ttl = ttl
            print(f"    Cacheable: {cls.__name__} ttl={ttl}s")

    class Base(Serializable, Cacheable):
        pass

    class UserDTO(Base, format="msgpack", ttl=300):
        pass

    print(f"\n  UserDTO._format: {UserDTO._format!r}")
    print(f"  UserDTO._ttl:    {UserDTO._ttl}s")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Descriptors
# ─────────────────────────────────────────────────────────────────────────────

def run_section_5():
    section_header(5, "Descriptors — Data vs Non-Data, Validated Attributes")

    # ── 5a: Descriptor lookup priority ──
    sub_header("5a: Lookup order — data descriptor > instance __dict__ > non-data")

    class DataDesc:
        """Data descriptor: __get__ + __set__"""
        def __set_name__(self, owner, name):
            self.name = name

        def __get__(self, obj, objtype=None):
            if obj is None:
                return self
            return f"[DataDesc value for {self.name!r}]"

        def __set__(self, obj, value):
            pass  # Silently accept (data descriptor — has __set__)

    class NonDataDesc:
        """Non-data descriptor: only __get__"""
        def __set_name__(self, owner, name):
            self.name = name

        def __get__(self, obj, objtype=None):
            if obj is None:
                return self
            return f"[NonDataDesc value for {self.name!r}]"

    class Demo:
        data_attr = DataDesc()
        nondata_attr = NonDataDesc()

    d = Demo()
    # Directly inject into instance __dict__
    d.__dict__['data_attr'] = "INSTANCE DICT VALUE"
    d.__dict__['nondata_attr'] = "INSTANCE DICT VALUE"

    print(f"  d.data_attr    = {d.data_attr!r}  ← DataDesc wins!")
    print(f"  d.nondata_attr = {d.nondata_attr!r}  ← Instance __dict__ wins!")
    print(f"  d.__dict__['data_attr']    = {d.__dict__['data_attr']!r}  (stored but ignored)")
    print(f"  d.__dict__['nondata_attr'] = {d.__dict__['nondata_attr']!r}  (used directly)")

    # ── 5b: __get__ with obj is None ──
    sub_header("5b: __get__ with obj=None — class vs instance access")

    class SmartDescriptor:
        def __set_name__(self, owner, name):
            self.name = name
            self.owner = owner

        def __get__(self, obj, objtype=None):
            if obj is None:
                # Class-level access: MyClass.attr
                return f"<SmartDescriptor {self.name!r} of {self.owner.__name__}>"
            # Instance-level access: instance.attr
            return f"Value of {self.name!r} for {type(obj).__name__} instance"

    class MyClass:
        smart = SmartDescriptor()

    print(f"  MyClass.smart  = {MyClass.smart}")
    print(f"  MyClass().smart = {MyClass().smart}")

    # ── 5c: Production-grade validated field system ──
    sub_header("5c: Production validated field system")

    class BaseField:
        def __set_name__(self, owner: type, name: str) -> None:
            self.attr_name = name
            self.storage_name = f'__field_{name}'

        def __get__(self, obj: Any, objtype: type = None) -> Any:
            if obj is None:
                return self
            return getattr(obj, self.storage_name, None)

        def __set__(self, obj: Any, value: Any) -> None:
            value = self.coerce(value)
            self.validate(value)
            setattr(obj, self.storage_name, value)

        def coerce(self, value: Any) -> Any:
            return value

        def validate(self, value: Any) -> None:
            pass

    class TypedField(BaseField):
        def __init__(self, field_type: type, nullable: bool = False):
            self.field_type = field_type
            self.nullable = nullable

        def validate(self, value: Any) -> None:
            if value is None:
                if not self.nullable:
                    raise ValueError(f"Field {self.attr_name!r} cannot be None")
                return
            if not isinstance(value, self.field_type):
                raise TypeError(
                    f"Field {self.attr_name!r}: expected {self.field_type.__name__}, "
                    f"got {type(value).__name__}"
                )

    class BoundedIntField(BaseField):
        def __init__(self, min_val: int = None, max_val: int = None):
            self.min_val = min_val
            self.max_val = max_val

        def coerce(self, value: Any) -> int:
            return int(value)

        def validate(self, value: int) -> None:
            if self.min_val is not None and value < self.min_val:
                raise ValueError(f"Field {self.attr_name!r}: {value} < min {self.min_val}")
            if self.max_val is not None and value > self.max_val:
                raise ValueError(f"Field {self.attr_name!r}: {value} > max {self.max_val}")

    class RegexField(BaseField):
        def __init__(self, pattern: str, max_len: int = 255):
            self.pattern = re.compile(pattern)
            self.max_len = max_len

        def validate(self, value: Any) -> None:
            if not isinstance(value, str):
                raise TypeError(f"Field {self.attr_name!r} must be str")
            if len(value) > self.max_len:
                raise ValueError(f"Field {self.attr_name!r} too long")
            if not self.pattern.match(value):
                raise ValueError(
                    f"Field {self.attr_name!r}: {value!r} doesn't match "
                    f"pattern {self.pattern.pattern!r}"
                )

    class UserAccount:
        username = RegexField(r'^[a-zA-Z0-9_]{3,30}$')
        email = RegexField(r'^[\w.+-]+@[\w-]+\.[a-z]{2,}$', max_len=255)
        age = BoundedIntField(min_val=13, max_val=120)
        bio = TypedField(str, nullable=True)

        def __init__(self, username: str, email: str, age: int, bio: str = None):
            self.username = username
            self.email = email
            self.age = age
            self.bio = bio

        def __repr__(self) -> str:
            return f"UserAccount({self.username!r}, {self.email!r}, age={self.age})"

    u = UserAccount("rahul_28", "rahul@example.com", 28, "Python dev from Pune")
    print(f"\n  Valid user: {u}")
    print(f"  bio: {u.bio!r}")

    for bad, exc_cls in [
        (lambda: UserAccount("ab", "x@x.com", 25), ValueError),      # username too short
        (lambda: UserAccount("valid", "not-an-email", 25), ValueError),  # bad email
        (lambda: UserAccount("valid", "x@x.com", 10), ValueError),    # age < 13
    ]:
        try:
            bad()
        except (ValueError, TypeError) as exc:
            print(f"  Caught {exc_cls.__name__}: {exc}")

    # ── 5d: Lazy loading descriptor ──
    sub_header("5d: Lazy loading descriptor (compute once, cache forever)")

    class lazy_property:
        """Non-data descriptor: computes on first access, caches in __dict__."""

        def __init__(self, func):
            self.func = func
            self.__doc__ = func.__doc__
            self.attrname: Optional[str] = None

        def __set_name__(self, owner: type, name: str) -> None:
            self.attrname = name

        def __get__(self, obj: Any, objtype: type = None) -> Any:
            if obj is None:
                return self
            name = self.attrname
            value = self.func(obj)
            # Cache in instance __dict__ — next access uses __dict__ directly
            # (non-data descriptor loses to instance __dict__)
            obj.__dict__[name] = value
            return value

    class DataReport:
        def __init__(self, raw_data: list[float]):
            self.raw_data = raw_data
            self._compute_count = 0

        @lazy_property
        def mean(self) -> float:
            """Compute arithmetic mean."""
            self._compute_count += 1
            print(f"    [Computing mean... call #{self._compute_count}]")
            return sum(self.raw_data) / len(self.raw_data)

        @lazy_property
        def variance(self) -> float:
            """Compute variance (requires mean)."""
            self._compute_count += 1
            print(f"    [Computing variance... call #{self._compute_count}]")
            mean = self.mean  # Uses cached mean!
            return sum((x - mean) ** 2 for x in self.raw_data) / len(self.raw_data)

        @lazy_property
        def std_dev(self) -> float:
            """Standard deviation."""
            self._compute_count += 1
            print(f"    [Computing std_dev... call #{self._compute_count}]")
            return self.variance ** 0.5

    data = DataReport([2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0])
    print(f"  First access (computes):")
    print(f"    mean    = {data.mean:.4f}")
    print(f"    variance = {data.variance:.4f}")
    print(f"    std_dev  = {data.std_dev:.4f}")
    print(f"  Second access (cached — no computation):")
    print(f"    mean    = {data.mean:.4f}")
    print(f"    variance = {data.variance:.4f}")
    print(f"  Total compute calls: {data._compute_count}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: property Internals
# ─────────────────────────────────────────────────────────────────────────────

def run_section_6():
    section_header(6, "property Internals — From Scratch Implementation")

    # ── 6a: property from scratch ──
    sub_header("6a: Implementing property descriptor from scratch")

    class property_:
        """Pure Python reimplementation of built-in property."""

        def __init__(self, fget=None, fset=None, fdel=None, doc=None):
            self.fget = fget
            self.fset = fset
            self.fdel = fdel
            self.__doc__ = doc or (fget.__doc__ if fget else None)

        def __get__(self, obj: Any, objtype: type = None) -> Any:
            if obj is None:
                return self  # Class access → return descriptor itself
            if self.fget is None:
                raise AttributeError(f"unreadable attribute")
            return self.fget(obj)

        def __set__(self, obj: Any, value: Any) -> None:
            if self.fset is None:
                raise AttributeError("can't set attribute (no setter defined)")
            self.fset(obj, value)

        def __delete__(self, obj: Any) -> None:
            if self.fdel is None:
                raise AttributeError("can't delete attribute (no deleter defined)")
            self.fdel(obj)

        def getter(self, fget):
            return type(self)(fget, self.fset, self.fdel, self.__doc__)

        def setter(self, fset):
            return type(self)(self.fget, fset, self.fdel, self.__doc__)

        def deleter(self, fdel):
            return type(self)(self.fget, self.fset, fdel, self.__doc__)

    class Temperature:
        def __init__(self, celsius: float = 0.0):
            self._celsius = celsius

        @property_
        def celsius(self) -> float:
            """Temperature in Celsius."""
            return self._celsius

        @celsius.setter
        def celsius(self, value: float) -> None:
            if value < -273.15:
                raise ValueError(f"Temperature {value}°C is below absolute zero!")
            self._celsius = value

        @celsius.deleter
        def celsius(self) -> None:
            print("    Deleting temperature reading...")
            del self._celsius

        @property_
        def fahrenheit(self) -> float:
            """Read-only Fahrenheit conversion."""
            return self._celsius * 9 / 5 + 32

        @property_
        def kelvin(self) -> float:
            """Read-only Kelvin conversion."""
            return self._celsius + 273.15

    t = Temperature(25.0)
    print(f"  celsius:    {t.celsius}°C")
    print(f"  fahrenheit: {t.fahrenheit}°F")
    print(f"  kelvin:     {t.kelvin}K")

    t.celsius = 100
    print(f"  After setting to 100°C: {t.fahrenheit}°F")

    try:
        t.fahrenheit = 50  # No setter defined
    except AttributeError as exc:
        print(f"  t.fahrenheit = 50 → AttributeError: {exc}")

    try:
        t.celsius = -300  # Below absolute zero
    except ValueError as exc:
        print(f"  t.celsius = -300 → ValueError: {exc}")

    # Class access returns descriptor itself
    print(f"  Temperature.celsius is property_: {isinstance(Temperature.celsius, property_)}")

    # ── 6b: functools.cached_property ──
    sub_header("6b: functools.cached_property — lazy + cached via non-data descriptor")

    class Circle:
        def __init__(self, radius: float):
            self.radius = radius
            self._compute_count = 0

        @functools.cached_property
        def area(self) -> float:
            """Expensive area computation."""
            self._compute_count += 1
            print(f"    [Computing area, call #{self._compute_count}]")
            return 3.141592653589793 * self.radius ** 2

        @functools.cached_property
        def circumference(self) -> float:
            """Expensive circumference computation."""
            self._compute_count += 1
            print(f"    [Computing circumference, call #{self._compute_count}]")
            return 2 * 3.141592653589793 * self.radius

    c = Circle(5.0)
    print(f"  First access:")
    print(f"    area          = {c.area:.4f}")
    print(f"    circumference = {c.circumference:.4f}")
    print(f"  Second access (cached):")
    print(f"    area          = {c.area:.4f}")
    print(f"    circumference = {c.circumference:.4f}")
    print(f"  Total compute calls: {c._compute_count}")
    print(f"  Cached in __dict__: {list(c.__dict__.keys())}")

    # ── 6c: How methods work as non-data descriptors ──
    sub_header("6c: Methods are non-data descriptors — bound vs unbound")

    class Counter:
        count = 0

        def increment(self) -> int:
            self.count += 1
            return self.count

    ctr = Counter()
    # Unbound (class access)
    unbound = Counter.increment
    print(f"  Counter.increment: {unbound}")

    # Bound (instance access) — self already attached
    bound = ctr.increment
    print(f"  ctr.increment:     {bound}")
    print(f"  ctr.increment():   {ctr.increment()}")
    print(f"  Counter.increment(ctr): {Counter.increment(ctr)}")  # Same as bound call


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: __slots__ Benchmark
# ─────────────────────────────────────────────────────────────────────────────

def run_section_7():
    section_header(7, "__slots__ — Memory Savings Benchmark")

    # ── 7a: Size comparison ──
    sub_header("7a: Single object size comparison")

    class WithDict:
        def __init__(self, x: float, y: float, z: float):
            self.x = x
            self.y = y
            self.z = z

    class WithSlots:
        __slots__ = ('x', 'y', 'z')

        def __init__(self, x: float, y: float, z: float):
            self.x = x
            self.y = y
            self.z = z

    d_obj = WithDict(1.0, 2.0, 3.0)
    s_obj = WithSlots(1.0, 2.0, 3.0)

    d_size = sys.getsizeof(d_obj) + sys.getsizeof(d_obj.__dict__)
    s_size = sys.getsizeof(s_obj)

    print(f"  WithDict:  obj={sys.getsizeof(d_obj)}B + dict={sys.getsizeof(d_obj.__dict__)}B = {d_size}B total")
    print(f"  WithSlots: obj={s_size}B total")
    print(f"  Savings per object: {d_size - s_size}B ({(d_size - s_size) / d_size * 100:.1f}%)")

    # ── 7b: Large-scale benchmark ──
    sub_header("7b: 100,000 instances — tracemalloc benchmark")

    N = 100_000

    tracemalloc.start()
    objs_dict = [WithDict(float(i), float(i * 2), float(i * 3)) for i in range(N)]
    _, peak_dict = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    tracemalloc.start()
    objs_slots = [WithSlots(float(i), float(i * 2), float(i * 3)) for i in range(N)]
    _, peak_slots = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print(f"  N = {N:,} objects")
    print(f"  __dict__ peak memory: {peak_dict / 1024 / 1024:.2f} MB")
    print(f"  __slots__ peak memory: {peak_slots / 1024 / 1024:.2f} MB")
    print(f"  Memory saved: {(peak_dict - peak_slots) / 1024 / 1024:.2f} MB "
          f"({(peak_dict - peak_slots) / peak_dict * 100:.1f}%)")

    del objs_dict, objs_slots  # Free memory

    # ── 7c: __slots__ restrictions ──
    sub_header("7c: __slots__ restrictions and gotchas")

    class Point2D:
        __slots__ = ('x', 'y')

        def __init__(self, x: float, y: float):
            self.x = x
            self.y = y

        def __repr__(self) -> str:
            return f"Point2D({self.x}, {self.y})"

    p = Point2D(3.0, 4.0)
    print(f"  Point2D: {p}")

    try:
        p.z = 5.0  # Dynamic attribute not allowed
    except AttributeError as exc:
        print(f"  p.z = 5.0 → AttributeError: {exc}")

    try:
        p.__dict__  # No __dict__
    except AttributeError as exc:
        print(f"  p.__dict__ → AttributeError: {exc}")

    # ── 7d: Inheritance with __slots__ ──
    sub_header("7d: __slots__ inheritance")

    class Base3D(Point2D):
        __slots__ = ('z',)  # Only add NEW slots

        def __init__(self, x: float, y: float, z: float):
            super().__init__(x, y)
            self.z = z

        def __repr__(self) -> str:
            return f"Point3D({self.x}, {self.y}, {self.z})"

    class NamedPoint(Base3D):
        # No __slots__ defined → __dict__ comes back!
        def __init__(self, x: float, y: float, z: float, name: str):
            super().__init__(x, y, z)
            self.name = name  # Works — __dict__ is back

    p3 = Base3D(1.0, 2.0, 3.0)
    print(f"  Base3D: {p3}")

    np = NamedPoint(1.0, 2.0, 3.0, "origin_plus")
    np.extra = "dynamic!"  # Works because NamedPoint has __dict__
    print(f"  NamedPoint: {np.name!r}, extra={np.extra!r}")
    print(f"  NamedPoint.__dict__: {np.__dict__}")

    # ── 7e: Access speed benchmark ──
    sub_header("7e: Attribute access speed — __slots__ vs __dict__")

    N_ITER = 500_000

    d = WithDict(1.0, 2.0, 3.0)
    s = WithSlots(1.0, 2.0, 3.0)

    start = time.perf_counter()
    for _ in range(N_ITER):
        _ = d.x + d.y + d.z
    dict_time = time.perf_counter() - start

    start = time.perf_counter()
    for _ in range(N_ITER):
        _ = s.x + s.y + s.z
    slots_time = time.perf_counter() - start

    speedup = dict_time / slots_time
    print(f"  {N_ITER:,} attribute reads:")
    print(f"  __dict__:  {dict_time * 1000:.2f} ms")
    print(f"  __slots__: {slots_time * 1000:.2f} ms")
    print(f"  Speedup:   {speedup:.2f}x {'faster' if speedup > 1 else 'slower'}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8: Generic[T] + Protocol
# ─────────────────────────────────────────────────────────────────────────────

def run_section_8():
    section_header(8, "Generic[T] + Protocol — Type-safe Generics")

    # ── 8a: Generic Stack ──
    sub_header("8a: Generic Stack[T]")

    T = TypeVar('T')

    class Stack(Generic[T]):
        """Type-safe LIFO stack."""

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

        def is_empty(self) -> bool:
            return len(self._items) == 0

        def __len__(self) -> int:
            return len(self._items)

        def __repr__(self) -> str:
            return f"Stack({self._items})"

        def __iter__(self) -> Iterator[T]:
            yield from reversed(self._items)

    print("  int_stack: Stack[int]")
    int_stack: Stack[int] = Stack()
    for v in [1, 2, 3, 4, 5]:
        int_stack.push(v)
    print(f"    {int_stack}")
    print(f"    peek: {int_stack.peek()}, pop: {int_stack.pop()}")
    print(f"    After pop: {int_stack}")
    print(f"    Iterate: {list(int_stack)}")

    print("\n  str_stack: Stack[str]")
    str_stack: Stack[str] = Stack()
    for w in ["push", "commit", "deploy"]:
        str_stack.push(w)
    print(f"    {str_stack}")

    # ── 8b: Generic BiMap ──
    sub_header("8b: Generic BiMap[K, V] — two-way dictionary")

    K = TypeVar('K')
    V = TypeVar('V')

    class BiMap(Generic[K, V]):
        """Bidirectional mapping: lookup by key OR by value."""

        def __init__(self) -> None:
            self._fwd: dict[K, V] = {}
            self._rev: dict[V, K] = {}

        def put(self, key: K, value: V) -> None:
            # Remove old reverse mapping if key already exists
            if key in self._fwd:
                del self._rev[self._fwd[key]]
            self._fwd[key] = value
            self._rev[value] = key

        def get_by_key(self, key: K) -> V:
            return self._fwd[key]

        def get_by_value(self, value: V) -> K:
            return self._rev[value]

        def __len__(self) -> int:
            return len(self._fwd)

        def __repr__(self) -> str:
            return f"BiMap({self._fwd})"

    bm: BiMap[str, int] = BiMap()
    bm.put("one", 1)
    bm.put("two", 2)
    bm.put("three", 3)
    print(f"  {bm}")
    print(f"  get_by_key('two')  = {bm.get_by_key('two')}")
    print(f"  get_by_value(3)    = {bm.get_by_value(3)!r}")

    # ── 8c: @runtime_checkable Protocol ──
    sub_header("8c: Protocol — structural typing + runtime isinstance check")

    @runtime_checkable
    class Drawable(Protocol):
        def draw(self) -> str: ...
        def get_area(self) -> float: ...

    @runtime_checkable
    class Serializable(Protocol):
        def to_dict(self) -> dict: ...
        def from_dict(cls, data: dict) -> Any: ...

    class Circle:  # NO inheritance from Drawable!
        def __init__(self, r: float):
            self.r = r

        def draw(self) -> str:
            return f"○ Circle(r={self.r})"

        def get_area(self) -> float:
            return 3.14159 * self.r ** 2

    class Rectangle:  # NO inheritance from Drawable!
        def __init__(self, w: float, h: float):
            self.w = w
            self.h = h

        def draw(self) -> str:
            return f"□ Rectangle({self.w}×{self.h})"

        def get_area(self) -> float:
            return self.w * self.h

    class Triangle:
        def __init__(self, b: float, h: float):
            self.b = b
            self.h = h

        def draw(self) -> str:
            return f"△ Triangle(b={self.b}, h={self.h})"

        def get_area(self) -> float:
            return 0.5 * self.b * self.h

    class RandomClass:
        def random_method(self): pass

    shapes = [Circle(5), Rectangle(4, 6), Triangle(3, 8)]
    print("  isinstance(shape, Drawable) checks:")
    for shape in shapes + [RandomClass()]:
        is_drawable = isinstance(shape, Drawable)
        print(f"    {type(shape).__name__:15} → {is_drawable}")

    def render_all(shapes: list[Drawable]) -> None:
        total_area = 0.0
        for shape in shapes:
            area = shape.get_area()
            total_area += area
            print(f"    {shape.draw():35} area={area:.2f}")
        print(f"    {'Total area:':35} {total_area:.2f}")

    print("\n  render_all(shapes):")
    render_all(shapes)  # type: ignore

    # ── 8d: TypeVar with bound ──
    sub_header("8d: TypeVar bound= and constraints")

    # bound: T must be a Comparable (supports <)
    @runtime_checkable
    class SupportsLT(Protocol):
        def __lt__(self, other: Any) -> bool: ...

    ComparableT = TypeVar('ComparableT', bound=SupportsLT)

    def find_min_max(items: list[ComparableT]) -> tuple[ComparableT, ComparableT]:
        """Works with any type that supports comparison."""
        return min(items), max(items)

    int_min, int_max = find_min_max([3, 1, 4, 1, 5, 9, 2, 6])
    str_min, str_max = find_min_max(["banana", "apple", "cherry", "date"])

    print(f"  Ints: min={int_min}, max={int_max}")
    print(f"  Strs: min={str_min!r}, max={str_max!r}")

    # Constraints: EXACTLY str or bytes
    AnyStr = TypeVar('AnyStr', str, bytes)

    def normalize(text: AnyStr) -> AnyStr:
        """Works for str or bytes, preserves type."""
        if isinstance(text, str):
            return text.strip().lower()  # type: ignore
        return text.strip()  # bytes.strip() works too  # type: ignore

    print(f"\n  normalize('  Hello World  '): {normalize('  Hello World  ')!r}")
    print(f"  normalize(b'  bytes  '): {normalize(b'  bytes  ')!r}")

    # ── 8e: Protocol with __call__ ──
    sub_header("8e: Protocol with __call__ — callable type constraint")

    @runtime_checkable
    class Middleware(Protocol):
        def __call__(self, request: dict, next_handler) -> dict: ...

    def logging_middleware(request: dict, next_handler) -> dict:
        print(f"    [LOG] Request: {request.get('path', '/')!r}")
        response = next_handler(request)
        print(f"    [LOG] Response status: {response.get('status', 200)}")
        return response

    class AuthMiddleware:
        def __init__(self, token: str):
            self.token = token

        def __call__(self, request: dict, next_handler) -> dict:
            if request.get('token') != self.token:
                return {'status': 401, 'body': 'Unauthorized'}
            return next_handler(request)

    print(f"  isinstance(logging_middleware, Middleware): "
          f"{isinstance(logging_middleware, Middleware)}")
    print(f"  isinstance(AuthMiddleware('x'), Middleware): "
          f"{isinstance(AuthMiddleware('x'), Middleware)}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION REGISTRY & MAIN
# ─────────────────────────────────────────────────────────────────────────────

SECTIONS: dict[int, tuple[str, Any]] = {
    1: ("Dynamic Class Creation", run_section_1),
    2: ("__new__ Patterns", run_section_2),
    3: ("Custom Metaclass", run_section_3),
    4: ("__init_subclass__", run_section_4),
    5: ("Descriptors", run_section_5),
    6: ("property Internals", run_section_6),
    7: ("__slots__ Benchmark", run_section_7),
    8: ("Generic[T] + Protocol", run_section_8),
}


def print_usage() -> None:
    print(__doc__)
    print("Available sections:")
    for num, (name, _) in SECTIONS.items():
        print(f"  {num}  {name}")


def main() -> None:
    args = sys.argv[1:]

    if not args or "all" in args:
        sections_to_run = list(SECTIONS.keys())
    else:
        sections_to_run = []
        for arg in args:
            if arg == "--help" or arg == "-h":
                print_usage()
                return
            try:
                num = int(arg)
                if num in SECTIONS:
                    sections_to_run.append(num)
                else:
                    print(f"Unknown section: {num}. Valid: {list(SECTIONS.keys())}")
            except ValueError:
                print(f"Invalid argument: {arg!r}. Use section numbers or 'all'.")
                print_usage()
                return

    print("\n" + "=" * 65)
    print("  Python Metaclasses, Descriptors & Object Model")
    print("  40 LPA Backend Python Developer — Interview Prep")
    print("=" * 65)

    total_start = time.perf_counter()

    for section_num in sorted(set(sections_to_run)):
        name, func = SECTIONS[section_num]
        try:
            func()
        except Exception as exc:
            print(f"\n  [ERROR in Section {section_num}]: {exc}")
            import traceback
            traceback.print_exc()

    elapsed = time.perf_counter() - total_start
    print(f"\n{'='*65}")
    print(f"  Completed {len(set(sections_to_run))} section(s) in {elapsed:.2f}s")
    print(f"{'='*65}\n")


if __name__ == "__main__":
    main()
