# Python Metaclasses, Descriptors & Object Model — Deep Dive
## Target: Backend Python Developer | 40 LPA Interview Prep
### Theory in Hinglish — Code/Terms in English

---

> **Yeh file kyun padho?** Senior Python roles mein — Django internals, SQLAlchemy ORM, FastAPI dependency injection, Pydantic field validation — sab jagah metaclass aur descriptors kaam karte hain. "How does Django's `CharField` work?" — yeh ek question hi distinguish karta hai 20 LPA se 40 LPA candidate ko.

---

## Table of Contents

1. Python Object Model Deep Dive
2. `__new__` vs `__init__`
3. Metaclasses
4. `__init_subclass__`
5. `__class_getitem__`
6. Descriptors
7. `property` Internals
8. `__set_name__`
9. `__slots__`
10. `TypeVar`, `Generic[T]`
11. `Protocol` — Structural Typing
12. Real-World Patterns
13. 12 Interview Q&As

---

## Section 1: Python Object Model Deep Dive

### "Everything is an object" — Matlab kya hai?

Python mein har cheez — numbers, strings, functions, classes, modules — sab **objects** hain. Har object ka ek **type** hota hai, aur woh type bhi ek object hai.

```python
print(type(42))          # <class 'int'>
print(type("hello"))     # <class 'str'>
print(type(int))         # <class 'type'>
print(type(type))        # <class 'type'>  ← type khud apna type hai!
```

Ek simple diagram dimag mein rakho:

```
42 (instance)  →  int (class)  →  type (metaclass)  →  type (itself)
"hi" (instance) → str (class)  →  type (metaclass)
MyClass (class) → type (metaclass) → type (metaclass)
```

**Key insight**: `type` is a metaclass — yeh `class` ka `class` hai.

### `type()` — Dual Personality

`type()` ke **do use** hain:

**1. Single argument — type check karo:**
```python
x = [1, 2, 3]
print(type(x))          # <class 'list'>
print(type(x) is list)  # True
```

**2. Three arguments — dynamically class banao:**
```python
# type(name, bases, dict)
Dog = type('Dog', (object,), {
    'species': 'Canis lupus familiaris',
    'bark': lambda self: "Woof!"
})
d = Dog()
print(d.bark())   # Woof!
print(Dog.species)  # Canis lupus familiaris
```

Yeh bilkul same hai:
```python
class Dog(object):
    species = 'Canis lupus familiaris'
    def bark(self): return "Woof!"
```

Python internally `type(name, bases, dict)` hi call karta hai jab `class` statement execute hota hai.

### Class Creation Process — Step by Step

Jab Python `class` statement encounter karta hai, exactly yeh hota hai:

```
1. Metaclass dhundho
   → class definition mein `metaclass=` hai?
   → koi base class ka metaclass use karo
   → default: `type`

2. metaclass.__prepare__(name, bases) call karo
   → returns a dict-like namespace (usually empty dict)
   → OrderedDict ya kuch custom return kar sakte ho

3. Class body execute karo
   → namespace mein attributes populate hote hain
   → `__prepare__` ka returned namespace fill hota hai

4. metaclass.__new__(mcs, name, bases, namespace) call karo
   → actual class object create hota hai
   → return karta hai class object

5. metaclass.__init__(cls, name, bases, namespace) call karo
   → class ko initialize karo
   → generally `__new__` ke baad
```

Code se samjho:

```python
class TracingMeta(type):
    @classmethod
    def __prepare__(mcs, name, bases):
        print(f"  __prepare__ called for: {name}")
        return {}  # ya koi custom dict
    
    def __new__(mcs, name, bases, namespace):
        print(f"  __new__ called for: {name}")
        print(f"  namespace keys: {list(namespace.keys())}")
        return super().__new__(mcs, name, bases, namespace)
    
    def __init__(cls, name, bases, namespace):
        print(f"  __init__ called for: {name}")
        super().__init__(name, bases, namespace)

class MyClass(metaclass=TracingMeta):
    x = 10
    def method(self): pass

# Output:
#   __prepare__ called for: MyClass
#   __new__ called for: MyClass
#   namespace keys: ['__module__', '__qualname__', 'x', 'method']
#   __init__ called for: MyClass
```

### `__class__` Attribute

```python
class Animal:
    def who_am_i(self):
        return self.__class__.__name__  # instance ka class name

class Dog(Animal):
    pass

d = Dog()
print(d.who_am_i())        # Dog  (not Animal!)
print(d.__class__)         # <class '__main__.Dog'>
print(d.__class__.__mro__) # Method Resolution Order
```

**`__class__` vs `type()`:**
```python
# Generally same hain, but descriptors mein difference aa sakta hai
print(d.__class__ is type(d))  # True (almost always)
```

---

## Section 2: `__new__` vs `__init__`

Yeh Python ka **most misunderstood concept** hai. Bahut log `__init__` ko constructor samajhte hain — technically `__new__` hai.

### `__new__` — Object Creator

```python
def __new__(cls, *args, **kwargs):
    # cls = class jiska instance ban raha hai
    # return karna ZAROORI hai — ek instance
    instance = super().__new__(cls)
    return instance
```

- **Class method** hai (implicitly — `classmethod` decorator nahi lagta)
- **First argument**: `cls` — class jiska instance banana hai
- **Return**: naya instance (typically `super().__new__(cls)` se)
- **Jab return karta hai**: tab `__init__` call hota hai us instance par

### `__init__` — Object Initializer

```python
def __init__(self, *args, **kwargs):
    # self = already created instance (__new__ ne banaya)
    # kuch return mat karo (None implicit hai)
    self.name = "something"
```

- **Instance method** hai
- **First argument**: `self` — already created object
- **Return**: `None` only (kuch aur return kiya to `TypeError`)
- **Purpose**: attributes set karna

### Order of Execution

```python
class Traced:
    def __new__(cls, value):
        print(f"  __new__({cls.__name__}, {value})")
        instance = super().__new__(cls)
        print(f"  __new__ returning: {id(instance)}")
        return instance
    
    def __init__(self, value):
        print(f"  __init__(self={id(self)}, {value})")
        self.value = value

t = Traced(42)
# Output:
#   __new__(Traced, 42)
#   __new__ returning: 140234567890
#   __init__(self=140234567890, 42)
# Note: same id! __new__ ne banaya, __init__ ne initialize kiya
```

### Critical: Jab `__new__` Different Type Return Kare

```python
class Weird:
    def __new__(cls, x):
        if x < 0:
            # Different type return kar rahe hain!
            return f"Negative: {x}"  # str return
        return super().__new__(cls)  # normal
    
    def __init__(self, x):
        print(f"  __init__ called with {x}")  # only if __new__ returns Weird instance
        self.x = x

w1 = Weird(5)
print(type(w1), w1.x)  # <class 'Weird'> 5  — __init__ called

w2 = Weird(-3)
print(type(w2), w2)    # <class 'str'> Negative: -3  — __init__ NOT called!
```

**Rule**: `__init__` tabhi call hota hai jab `__new__` ka return value `cls` ka instance ho.

### Pattern 1: Singleton using `__new__`

```python
class DatabaseConnection:
    _instance = None
    _initialized = False
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            print("  Creating new DB connection...")
            cls._instance = super().__new__(cls)
        else:
            print("  Returning existing connection.")
        return cls._instance
    
    def __init__(self, host="localhost", port=5432):
        if self._initialized:
            return  # Already initialized, skip
        self.host = host
        self.port = port
        self._initialized = True
        print(f"  Initialized connection to {host}:{port}")

db1 = DatabaseConnection("prod.server.com", 5432)
db2 = DatabaseConnection("other.server.com", 3306)
print(db1 is db2)   # True — same object!
print(db1.host)     # prod.server.com (not overwritten)
```

### Pattern 2: Immutable Objects using `__new__`

Jab `int`, `str`, `tuple` ko subclass karo — immutable hain to `__new__` mein hi value set karni padti hai:

```python
class PositiveInt(int):
    """int subclass jo sirf positive values allow kare"""
    
    def __new__(cls, value):
        if value <= 0:
            raise ValueError(f"PositiveInt must be > 0, got {value}")
        # int.__new__ mein value pass karo
        instance = super().__new__(cls, value)
        return instance
    
    def __repr__(self):
        return f"PositiveInt({int(self)})"

p = PositiveInt(42)
print(p + 8)        # 50 (int operations work!)
print(type(p + 8))  # <class 'int'>  (arithmetic returns int, not PositiveInt)

try:
    PositiveInt(-5)
except ValueError as e:
    print(e)  # PositiveInt must be > 0, got -5


class FrozenPoint(tuple):
    """Immutable (x, y) point — tuple subclass"""
    
    def __new__(cls, x, y):
        # tuple values __new__ mein hi set karni hain
        return super().__new__(cls, (x, y))
    
    @property
    def x(self): return self[0]
    
    @property
    def y(self): return self[1]
    
    def distance_from_origin(self):
        return (self.x**2 + self.y**2) ** 0.5
    
    def __repr__(self):
        return f"Point({self.x}, {self.y})"

p = FrozenPoint(3, 4)
print(p.x, p.y)                  # 3 4
print(p.distance_from_origin())  # 5.0
# p.x = 10  # AttributeError — immutable!
```

---

## Section 3: Metaclasses

### "Class ka Class" — Concept Clear Karo

```
Normal objects:    instance  ←(created by)→  class
Metaclass concept: class     ←(created by)→  metaclass
```

```python
print(type(int))    # <class 'type'>
print(type(str))    # <class 'type'>
print(type(list))   # <class 'type'>
print(type(type))   # <class 'type'>  ← type is its own metaclass
```

`type` itself Python ka built-in metaclass hai. Jab bhi tum `class MyClass:` likhte ho, Python internally `type.__call__(type, 'MyClass', bases, namespace)` call karta hai.

### Custom Metaclass Banana

```python
class MyMeta(type):
    # mcs = metaclass itself (like cls in classmethod)
    def __new__(mcs, name, bases, namespace):
        print(f"Creating class: {name}")
        cls = super().__new__(mcs, name, bases, namespace)
        return cls

class MyClass(metaclass=MyMeta):
    pass
# Output: Creating class: MyClass
```

### `__new__` in Metaclass — Class Creation Intercept

```python
class ValidatingMeta(type):
    """Ensure all public methods have docstrings"""
    
    def __new__(mcs, name, bases, namespace):
        # namespace = class body ka dict
        for attr_name, attr_value in namespace.items():
            if callable(attr_value) and not attr_name.startswith('_'):
                if not attr_value.__doc__:
                    raise TypeError(
                        f"Method '{name}.{attr_name}' must have a docstring!"
                    )
        return super().__new__(mcs, name, bases, namespace)

class WellDocumented(metaclass=ValidatingMeta):
    def process(self):
        """Process the data."""  # OK
        pass

# class BadClass(metaclass=ValidatingMeta):
#     def process(self):  # No docstring → TypeError!
#         pass
```

### `__init__` in Metaclass — After Class Created

```python
class RegistryMeta(type):
    _all_classes = {}
    
    def __init__(cls, name, bases, namespace):
        super().__init__(name, bases, namespace)
        # cls abhi fully created hai
        RegistryMeta._all_classes[name] = cls
        print(f"  Registered: {name}")

class Base(metaclass=RegistryMeta): pass
class A(Base): pass
class B(Base): pass

print(RegistryMeta._all_classes)
# {'Base': <class 'Base'>, 'A': <class 'A'>, 'B': <class 'B'>}
```

### `__call__` in Metaclass — Instance Creation Intercept

Yeh **most powerful** part hai. Jab `MyClass(args)` likhte ho, actually `type.__call__(MyClass, args)` hota hai.

```python
class SingletonMeta(type):
    _instances = {}
    
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            # super().__call__ internally __new__ + __init__ call karta hai
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]

class AppConfig(metaclass=SingletonMeta):
    def __init__(self, debug=False):
        self.debug = debug
        print(f"  AppConfig created, debug={debug}")

c1 = AppConfig(debug=True)
c2 = AppConfig(debug=False)
print(c1 is c2)      # True
print(c1.debug)      # True  (first creation ki value)
```

**Call chain visualization:**
```
MyClass(42)
  → type.__call__(MyClass, 42)        [metaclass __call__]
    → MyClass.__new__(MyClass, 42)    [create instance]
    → MyClass.__init__(instance, 42)  [initialize instance]
    → return instance
```

### Use Case 1: Auto-Registration Plugin System

```python
class PluginMeta(type):
    _plugins = {}
    
    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)
        if bases:  # Base class khud register mat karo
            plugin_id = namespace.get('plugin_id', name.lower())
            mcs._plugins[plugin_id] = cls
        return cls
    
    @classmethod
    def get(mcs, plugin_id):
        return mcs._plugins.get(plugin_id)
    
    @classmethod
    def all_plugins(mcs):
        return dict(mcs._plugins)

class Processor(metaclass=PluginMeta):
    """Base processor"""
    plugin_id = None
    def process(self, data): raise NotImplementedError

class JsonProcessor(Processor):
    plugin_id = "json"
    def process(self, data): return f"JSON: {data}"

class CsvProcessor(Processor):
    plugin_id = "csv"
    def process(self, data): return f"CSV: {data}"

# Usage:
proc = PluginMeta.get("json")()
print(proc.process({"key": "value"}))  # JSON: {'key': 'value'}
```

### Use Case 2: Enforcing Interface (Abstract-like)

```python
class InterfaceMeta(type):
    """Ensure subclasses implement required methods"""
    
    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)
        
        if bases:  # Only check subclasses
            required = set()
            for base in bases:
                required.update(getattr(base, '_required_methods', set()))
            
            missing = [m for m in required if m not in namespace]
            if missing:
                raise TypeError(
                    f"{name} must implement: {', '.join(missing)}"
                )
        return cls

class Repository(metaclass=InterfaceMeta):
    _required_methods = {'get', 'save', 'delete'}
    
    def get(self, id): raise NotImplementedError
    def save(self, obj): raise NotImplementedError
    def delete(self, id): raise NotImplementedError

class UserRepository(Repository):
    def get(self, id): return f"User({id})"
    def save(self, obj): return f"Saved {obj}"
    def delete(self, id): return f"Deleted {id}"
    # Agar koi bhi method missing hota to TypeError!
```

### Use Case 3: ORM-like Field Declaration (Django Model Internals)

Django ka `Model` exactly isi pattern se kaam karta hai:

```python
class Field:
    """Base ORM field"""
    def __init__(self, field_type, required=True, default=None):
        self.field_type = field_type
        self.required = required
        self.default = default
        self.name = None  # __set_name__ se milega

class CharField(Field):
    def __init__(self, max_length=255, **kwargs):
        super().__init__(str, **kwargs)
        self.max_length = max_length

class IntField(Field):
    def __init__(self, **kwargs):
        super().__init__(int, **kwargs)

class ModelMeta(type):
    def __new__(mcs, name, bases, namespace):
        fields = {}
        
        # Fields collect karo
        for key, value in namespace.items():
            if isinstance(value, Field):
                value.name = key  # Field ko apna naam pata chalega
                fields[key] = value
        
        cls = super().__new__(mcs, name, bases, namespace)
        cls._fields = fields
        cls._table = name.lower() + 's'
        return cls

class Model(metaclass=ModelMeta):
    def __init__(self, **kwargs):
        for name, field in self._fields.items():
            value = kwargs.get(name, field.default)
            if field.required and value is None:
                raise ValueError(f"Field '{name}' is required")
            setattr(self, f'_{name}', value)
    
    def to_dict(self):
        return {name: getattr(self, f'_{name}') 
                for name in self._fields}
    
    @classmethod
    def schema(cls):
        return {name: f.__class__.__name__ 
                for name, f in cls._fields.items()}

class User(Model):
    name = CharField(max_length=100)
    age = IntField()
    email = CharField(max_length=255, required=False, default="")

u = User(name="Rahul", age=28)
print(u.to_dict())       # {'name': 'Rahul', 'age': 28, 'email': ''}
print(User.schema())     # {'name': 'CharField', 'age': 'IntField', 'email': 'CharField'}
print(User._table)       # users
```

### `abc.ABCMeta` — Built-in Metaclass

`abc.ABCMeta` is a metaclass jo abstract methods track karta hai:

```python
from abc import ABCMeta, abstractmethod

class Shape(metaclass=ABCMeta):
    @abstractmethod
    def area(self) -> float: ...
    
    @abstractmethod
    def perimeter(self) -> float: ...

# Shape()  # TypeError: Can't instantiate abstract class

class Circle(Shape):
    def __init__(self, r): self.r = r
    def area(self): return 3.14 * self.r**2
    def perimeter(self): return 2 * 3.14 * self.r

# Abstract base classes using `abc.ABC` (convenience class):
from abc import ABC
class Animal(ABC):  # ABC ka metaclass ABCMeta hai
    @abstractmethod
    def speak(self): ...
```

### Metaclass Conflict — Multiple Inheritance

```python
class MetaA(type): pass
class MetaB(type): pass

class A(metaclass=MetaA): pass
class B(metaclass=MetaB): pass

# class C(A, B): pass  # TypeError: metaclass conflict!
# MetaA and MetaB dono hain, Python confuse ho jaata hai

# Solution: Combined metaclass
class MetaC(MetaA, MetaB): pass  # MRO se resolve

class C(A, B, metaclass=MetaC): pass  # Works!
```

**Important**: Python automatically MetaA aur MetaB check karta hai aur agar ek dusre ka subtype hai to automatically use karta hai.

---

## Section 4: `__init_subclass__`

Python 3.6+ mein aaya. **Most metaclass use cases ko replace karta hai** — simpler, cleaner.

### Basic Concept

```python
class Base:
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        print(f"  New subclass: {cls.__name__}")

class Child(Base): pass       # prints: New subclass: Child
class GrandChild(Child): pass # prints: New subclass: GrandChild
```

`__init_subclass__` tab call hota hai jab **koi class** us class ko subclass kare. `cls` = naya subclass.

### Kwargs Through Inheritance Chain

```python
class Plugin:
    _registry = {}
    
    def __init_subclass__(cls, plugin_name=None, version="1.0", **kwargs):
        super().__init_subclass__(**kwargs)  # ALWAYS call this!
        
        name = plugin_name or cls.__name__.lower()
        cls._plugin_name = name
        cls._version = version
        Plugin._registry[name] = cls
        print(f"  Registered: {name} v{version}")

class BasePlugin(Plugin, plugin_name="base", version="0.0"):
    pass

class EmailPlugin(Plugin, plugin_name="email", version="2.1"):
    def send(self, msg): return f"Email: {msg}"

class SMSPlugin(Plugin, plugin_name="sms", version="1.5"):
    def send(self, msg): return f"SMS: {msg}"

print(Plugin._registry)
# {'base': <class 'BasePlugin'>, 'email': <class 'EmailPlugin'>, 'sms': <class 'SMSPlugin'>}
```

### Enforce Required Attributes/Methods

```python
class Repository:
    """Every repository must define `model_class` and implement CRUD"""
    
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        
        # model_class attribute check
        if not hasattr(cls, 'model_class'):
            raise TypeError(f"{cls.__name__} must define 'model_class'")
        
        # Required methods check
        required_methods = ['get_by_id', 'save', 'delete']
        for method in required_methods:
            if method not in cls.__dict__:
                raise TypeError(f"{cls.__name__} must implement '{method}'")

class UserRepo(Repository):
    model_class = "User"  # Required!
    
    def get_by_id(self, id): return f"User({id})"
    def save(self, obj): return f"Saved"
    def delete(self, id): return f"Deleted"

# class BadRepo(Repository):
#     model_class = "Bad"
#     # Missing methods → TypeError at class definition time!
```

### Auto-Inject Class Variables

```python
class TimestampMixin:
    """Auto-inject created_at, updated_at fields"""
    
    def __init_subclass__(cls, track_timestamps=True, **kwargs):
        super().__init_subclass__(**kwargs)
        if track_timestamps:
            cls._track_timestamps = True
            cls._timestamp_fields = ['created_at', 'updated_at']
            print(f"  Timestamp tracking enabled for {cls.__name__}")

class UserModel(TimestampMixin, track_timestamps=True):
    pass

class LogModel(TimestampMixin, track_timestamps=False):
    pass
```

### `__init_subclass__` vs Metaclass — Kab Kya Use Karo?

| Feature | `__init_subclass__` | Metaclass |
|---------|-------------------|-----------|
| Simplicity | Simple, clean | Complex |
| Intercept class creation | Partial (after `__new__`) | Full control |
| Modify namespace before exec | No | Yes (`__prepare__`) |
| Override `__call__` | No | Yes |
| Multiple inheritance | Works naturally | Conflict possible |
| Use case | Registration, validation | ORM, singleton, full control |

**Rule of thumb**: Pehle `__init_subclass__` try karo. Agar kafi nahi hai tab metaclass use karo.

---

## Section 5: `__class_getitem__`

Python 3.7+ mein aaya. `MyClass[int]` syntax ke liye.

### Basic Usage

```python
class MyContainer:
    def __class_getitem__(cls, item):
        print(f"  __class_getitem__ called with: {item}")
        return f"MyContainer[{item.__name__}]"

x = MyContainer[int]    # __class_getitem__ called with: <class 'int'>
print(x)                # MyContainer[int]
```

### How `List[int]` Works Internally

```python
from typing import List
# List[int] internally calls List.__class_getitem__(int)
# Returns _GenericAlias object — type hint ke liye, runtime pe kuch nahi karta
```

### Building Your Own Generic Class

```python
from typing import Generic, TypeVar, get_args, get_origin

T = TypeVar('T')

class TypedList(Generic[T]):
    """Runtime type checking with generics"""
    
    def __class_getitem__(cls, item):
        # Generic.__class_getitem__ call karo
        alias = super().__class_getitem__(item)
        return alias
    
    def __init__(self):
        self._items = []
        # Runtime pe T ka pata nahi chalta (type erasure)
        # For runtime type info, pass type explicitly
    
    def append(self, item: T) -> None:
        self._items.append(item)
    
    def __repr__(self):
        return f"TypedList({self._items})"

# Type hints ke liye:
def process(items: TypedList[int]) -> None:
    pass

# Runtime generic info:
from typing import get_args
hint = TypedList[int]
print(get_args(hint))   # (<class 'int'>,)
```

### `ClassVar` and `Optional` Internals

```python
from typing import ClassVar, Optional

# ClassVar[int] → _GenericAlias(ClassVar, int)
# Optional[str] → Union[str, None]

class Config:
    max_connections: ClassVar[int] = 100  # Class variable
    name: Optional[str] = None            # Instance variable, can be None
```

---

## Section 6: Descriptors

Yeh Python ka **most powerful** feature hai — `property`, `classmethod`, `staticmethod`, Django fields, SQLAlchemy columns sab descriptors hain.

### Definition: Descriptor Protocol

Koi bhi object jo in mein se ek ya zyada dunder methods implement kare:

```python
class Descriptor:
    def __get__(self, obj, objtype=None):
        """Attribute access: instance.attr ya Class.attr"""
        pass
    
    def __set__(self, obj, value):
        """Assignment: instance.attr = value"""
        pass
    
    def __delete__(self, obj):
        """Deletion: del instance.attr"""
        pass
```

### Data vs Non-Data Descriptors

**Non-Data Descriptor**: Sirf `__get__`
```python
class NonDataDesc:
    def __get__(self, obj, objtype=None):
        return "non-data"

# Functions non-data descriptors hain!
# obj.__dict__ override kar sakta hai non-data descriptor ko
```

**Data Descriptor**: `__get__` + `__set__` (ya `__delete__`)
```python
class DataDesc:
    def __get__(self, obj, objtype=None):
        return "data"
    
    def __set__(self, obj, value):
        pass  # Even empty __set__ makes it a data descriptor!

# Data descriptor ALWAYS wins over instance __dict__
```

### Attribute Lookup Order (Critical for Interviews!)

```
1. Data Descriptors (type.__mro__ se — class hierarchy mein)
2. Instance __dict__
3. Non-Data Descriptors + other class attributes
```

```python
class MyDesc:
    def __get__(self, obj, objtype=None):
        if obj is None: return self
        return "from descriptor"
    
    def __set__(self, obj, value):  # Data descriptor!
        pass

class MyClass:
    attr = MyDesc()  # Data descriptor

obj = MyClass()
obj.__dict__['attr'] = "from instance dict"  # Directly set, bypass descriptor

print(obj.attr)  # "from descriptor" ← Data descriptor wins!

# Non-data descriptor hota to:
class NonDataDesc:
    def __get__(self, obj, objtype=None):
        return "from non-data descriptor"

class MyClass2:
    attr = NonDataDesc()

obj2 = MyClass2()
obj2.__dict__['attr'] = "from instance dict"
print(obj2.attr)  # "from instance dict" ← Instance dict wins!
```

### `__get__` — `obj is None` Pattern

```python
class MyDescriptor:
    def __get__(self, obj, objtype=None):
        if obj is None:
            # Class level access: MyClass.attr
            # `self` descriptor object return karo
            return self
        # Instance level access: instance.attr
        return "instance value"

class MyClass:
    attr = MyDescriptor()

print(MyClass.attr)       # <MyDescriptor object>  ← descriptor itself
print(MyClass().attr)     # "instance value"
```

Yeh important hai kyunki `@classmethod`, `@staticmethod` bhi isi pattern se kaam karte hain.

### Complete Descriptor Example — Validated Attribute

```python
class Validator:
    """Base data descriptor for attribute validation"""
    
    def __set_name__(self, owner, name):
        # owner = class jis mein descriptor assign hua
        # name = attribute ka naam
        self.public_name = name
        self.private_name = '_validated_' + name
    
    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return getattr(obj, self.private_name, None)
    
    def __set__(self, obj, value):
        self.validate(value)
        setattr(obj, self.private_name, value)
    
    def validate(self, value):
        pass  # Override in subclasses

class Integer(Validator):
    def __init__(self, min_value=None, max_value=None):
        self.min_value = min_value
        self.max_value = max_value
    
    def validate(self, value):
        if not isinstance(value, int):
            raise TypeError(f"'{self.public_name}' must be int, got {type(value).__name__}")
        if self.min_value is not None and value < self.min_value:
            raise ValueError(f"'{self.public_name}' must be >= {self.min_value}")
        if self.max_value is not None and value > self.max_value:
            raise ValueError(f"'{self.public_name}' must be <= {self.max_value}")

class String(Validator):
    def __init__(self, min_len=0, max_len=None):
        self.min_len = min_len
        self.max_len = max_len
    
    def validate(self, value):
        if not isinstance(value, str):
            raise TypeError(f"'{self.public_name}' must be str")
        if len(value) < self.min_len:
            raise ValueError(f"'{self.public_name}' too short (min {self.min_len})")
        if self.max_len and len(value) > self.max_len:
            raise ValueError(f"'{self.public_name}' too long (max {self.max_len})")

class Employee:
    name = String(min_len=2, max_len=50)
    age = Integer(min_value=18, max_value=65)
    salary = Integer(min_value=0)
    
    def __init__(self, name, age, salary):
        self.name = name     # String.__set__ called
        self.age = age       # Integer.__set__ called
        self.salary = salary # Integer.__set__ called
    
    def __repr__(self):
        return f"Employee({self.name}, {self.age}, ₹{self.salary:,})"

e = Employee("Rahul Kumar", 28, 1200000)
print(e)
# e.age = 17  # ValueError!
# e.name = "A"  # ValueError: too short!
```

### How Functions are Non-Data Descriptors

Yeh Python ka **most elegant** implementation hai:

```python
class Function:
    """Conceptually how Python functions work as descriptors"""
    
    def __init__(self, func):
        self.func = func
    
    def __get__(self, obj, objtype=None):
        if obj is None:
            return self.func  # Class access → unbound function
        # Instance access → bound method (obj already bound)
        from functools import partial
        return partial(self.func, obj)

# Python internally does this:
def greet(self):
    return f"Hello, {self.name}!"

class Person:
    name = "Alice"
    greet = greet  # Function is a non-data descriptor

p = Person()
print(p.greet())          # "Hello, Alice!" — bound method
print(Person.greet)       # <function greet> — unbound
print(Person.greet(p))    # "Hello, Alice!" — manually bound
```

---

## Section 7: `property` Internals

`property` ek built-in **data descriptor** class hai.

### Standard Usage

```python
class Temperature:
    def __init__(self, celsius=0):
        self._celsius = celsius
    
    @property
    def celsius(self):
        """Celsius mein temperature."""
        return self._celsius
    
    @celsius.setter
    def celsius(self, value):
        if value < -273.15:
            raise ValueError("Temperature below absolute zero!")
        self._celsius = value
    
    @celsius.deleter
    def celsius(self):
        del self._celsius
    
    @property
    def fahrenheit(self):
        """Read-only Fahrenheit conversion."""
        return self._celsius * 9/5 + 32

t = Temperature(25)
print(t.celsius)     # 25
print(t.fahrenheit)  # 77.0
t.celsius = 100      # setter called
# t.fahrenheit = 50  # AttributeError — no setter!
```

### `property` Internals — From Scratch Implementation

```python
class property_:
    """property ka pure Python implementation"""
    
    def __init__(self, fget=None, fset=None, fdel=None, doc=None):
        self.fget = fget
        self.fset = fset
        self.fdel = fdel
        self.__doc__ = doc or (fget.__doc__ if fget else None)
    
    def __get__(self, obj, objtype=None):
        if obj is None:
            return self  # Class access → property object itself
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
    
    def getter(self, fget):
        """New property with updated getter"""
        return type(self)(fget, self.fset, self.fdel, self.__doc__)
    
    def setter(self, fset):
        """New property with updated setter"""
        return type(self)(self.fget, fset, self.fdel, self.__doc__)
    
    def deleter(self, fdel):
        """New property with updated deleter"""
        return type(self)(self.fget, self.fset, fdel, self.__doc__)

# Usage (identical to built-in property):
class Circle_:
    def __init__(self, radius):
        self._radius = radius
    
    @property_
    def radius(self):
        """Circle radius."""
        return self._radius
    
    @radius.setter
    def radius(self, value):
        if value < 0:
            raise ValueError("Radius cannot be negative")
        self._radius = value
```

### `functools.cached_property`

Python 3.8+ mein built-in:

```python
import functools
import time

class DataAnalyzer:
    def __init__(self, data):
        self.data = data
    
    @functools.cached_property
    def statistics(self):
        """Expensive computation — only once!"""
        print("  Computing statistics (slow operation)...")
        time.sleep(0.1)  # Simulate slow computation
        return {
            'mean': sum(self.data) / len(self.data),
            'max': max(self.data),
            'min': min(self.data),
        }

da = DataAnalyzer([1, 2, 3, 4, 5])
print(da.statistics)  # Computing... (first call)
print(da.statistics)  # No "Computing..." (cached in instance __dict__)

# Internals: cached_property is a NON-DATA descriptor
# First call: __get__ computes, stores in obj.__dict__['statistics']
# Second call: instance __dict__ wins (non-data descriptor loses to __dict__)
```

**Why non-data?** Caching is intentional — instance `__dict__` override kare descriptor ko.

### `classproperty` Pattern (Python mein natively nahi hai)

```python
class classproperty:
    """Property that works on class, not instance"""
    
    def __init__(self, func):
        self.func = func
    
    def __get__(self, obj, objtype=None):
        if objtype is None:
            objtype = type(obj)
        return self.func(objtype)

class MyConfig:
    _debug = False
    
    @classproperty
    def debug(cls):
        return cls._debug
    
    @classproperty
    def name(cls):
        return cls.__name__

print(MyConfig.debug)  # False
print(MyConfig.name)   # MyConfig
```

---

## Section 8: `__set_name__`

Python 3.6+ mein aaya. Descriptor ko **apna naam** automatically pata chalata hai.

### Problem Without `__set_name__`

```python
# OLD WAY — verbose aur error-prone
class OldDescriptor:
    def __init__(self, name):  # Manually naam pass karna padta tha
        self.name = name
        self.private = '_' + name

class OldStyle:
    x = OldDescriptor('x')  # Naam duplicate karna padta tha!
    y = OldDescriptor('y')  # Typo prone!
```

### With `__set_name__`

```python
class SmartDescriptor:
    def __set_name__(self, owner, name):
        # Python automatically call karta hai class creation ke time
        # owner = class jis mein assign hua
        # name = attribute ka naam
        self.name = name
        self.private = '_' + name
        print(f"  __set_name__: {owner.__name__}.{name}")
    
    def __get__(self, obj, objtype=None):
        if obj is None: return self
        return getattr(obj, self.private, None)
    
    def __set__(self, obj, value):
        setattr(obj, self.private, value)

class MyModel:
    username = SmartDescriptor()  # __set_name__(MyModel, 'username') called
    email = SmartDescriptor()     # __set_name__(MyModel, 'email') called

m = MyModel()
m.username = "rahul123"
print(m.username)    # rahul123
print(m.__dict__)    # {'_username': 'rahul123'}
```

### `__set_name__` with Type Information

```python
class TypedAttribute:
    def __init__(self, expected_type, doc=""):
        self.expected_type = expected_type
        self.__doc__ = doc
        self.name = None  # Will be set by __set_name__
    
    def __set_name__(self, owner, name):
        self.name = name
        self.private = f'_typed_{name}'
        # Class mein attribute documentation inject karo
        if self.__doc__:
            owner.__annotations__[name] = self.expected_type
    
    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return getattr(obj, self.private, None)
    
    def __set__(self, obj, value):
        if not isinstance(value, self.expected_type):
            raise TypeError(
                f"{obj.__class__.__name__}.{self.name}: "
                f"Expected {self.expected_type.__name__}, "
                f"got {type(value).__name__}"
            )
        setattr(obj, self.private, value)

class Config:
    host = TypedAttribute(str, "Server hostname")
    port = TypedAttribute(int, "Server port")
    debug = TypedAttribute(bool, "Debug mode")

c = Config()
c.host = "localhost"
c.port = 8080
c.debug = False
print(f"{c.host}:{c.port}, debug={c.debug}")
# c.port = "8080"  # TypeError!
```

---

## Section 9: `__slots__`

Memory optimization ke liye **most important** Python feature for production systems.

### Default Behavior: `__dict__`

Normally, har Python object ek `__dict__` (dictionary) carry karta hai:

```python
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

p = Point(1, 2)
print(p.__dict__)        # {'x': 1, 'y': 2}
print(type(p.__dict__))  # <class 'dict'>

# Dict overhead bahut bada hai:
import sys
print(sys.getsizeof(p))           # ~48 bytes (object header)
print(sys.getsizeof(p.__dict__))  # ~296 bytes on CPython 3.12 — instance __dict__, version-dependent
```

### `__slots__` — Dict Replace karo Array Se

```python
class PointSlots:
    __slots__ = ['x', 'y']  # Ya tuple: ('x', 'y')
    
    def __init__(self, x, y):
        self.x = x
        self.y = y

ps = PointSlots(1, 2)
# ps.__dict__  # AttributeError — no __dict__!
print(sys.getsizeof(ps))  # ~56 bytes — ~4x smaller!
```

### Memory Savings — Real Numbers

```python
import sys
import tracemalloc

class WithDict:
    def __init__(self, x, y, z):
        self.x = x; self.y = y; self.z = z

class WithSlots:
    __slots__ = ('x', 'y', 'z')
    def __init__(self, x, y, z):
        self.x = x; self.y = y; self.z = z

# Single object size:
d = WithDict(1, 2, 3)
s = WithSlots(1, 2, 3)
print(f"WithDict:  {sys.getsizeof(d) + sys.getsizeof(d.__dict__)} bytes")
print(f"WithSlots: {sys.getsizeof(s)} bytes")
# WithDict:  ~280 bytes
# WithSlots: ~56 bytes  ← ~5x savings!

# 1 million objects mein:
# WithDict:  ~280 MB
# WithSlots: ~56 MB
```

### Restrictions aur Gotchas

```python
# 1. Dynamic attributes nahi ban sakte
class Rigid:
    __slots__ = ['x', 'y']

r = Rigid()
r.x = 1     # OK
# r.z = 3   # AttributeError: 'Rigid' object has no attribute 'z'

# 2. Inheritance gotcha — parent ke slots inaccessible nahi hote
class Base:
    __slots__ = ['x']

class Child(Base):
    __slots__ = ['y']  # x bhi available rahega (inherited)
    # Agar __slots__ define nahi kiya to __dict__ wapis aa jaata hai!

class ChildNoSlots(Base):
    pass  # No __slots__ → __dict__ wapis aa gaya!

cn = ChildNoSlots()
cn.anything = "dynamic!"  # Works — __dict__ wapis aa gaya

# 3. Multiple inheritance mein conflict
class A:
    __slots__ = ['x']
class B:
    __slots__ = ['x']

class C(A, B):
    pass  # Works but duplicate 'x' slot — warning
```

### `__slots__` with `__dict__` — Best of Both Worlds

```python
class FlexibleSlots:
    __slots__ = ['x', 'y', '__dict__']  # __dict__ explicitly add karo
    
    def __init__(self, x, y, **extra):
        self.x = x
        self.y = y
        self.__dict__.update(extra)  # Extra attrs dict mein

fs = FlexibleSlots(1, 2, name="point", color="red")
print(fs.x, fs.name)  # 1 point — slots + dict
```

### When to Use `__slots__`

- **Use karo**: Millions of instances (geospatial points, game entities, data records)
- **Use karo**: Memory-critical applications (embedded, mobile)
- **Use karo**: Final, sealed classes
- **Avoid**: Small number of instances
- **Avoid**: Dynamic attribute pattern
- **Avoid**: Multiple inheritance with other `__slots__` classes (complex)

---

## Section 10: `TypeVar`, `Generic[T]`

Python's type system extension ke liye.

### `TypeVar` — Placeholder Type

```python
from typing import TypeVar, Generic, List

T = TypeVar('T')  # Any type
S = TypeVar('S', str, bytes)  # Only str or bytes (constrained)
N = TypeVar('N', bound=int)   # Must be int or subclass (bound)
```

### `Generic[T]` — Parameterized Class

```python
T = TypeVar('T')

class Stack(Generic[T]):
    def __init__(self) -> None:
        self._items: List[T] = []
    
    def push(self, item: T) -> None:
        self._items.append(item)
    
    def pop(self) -> T:
        if not self._items:
            raise IndexError("Stack is empty")
        return self._items.pop()
    
    def peek(self) -> T:
        return self._items[-1]
    
    def __len__(self) -> int:
        return len(self._items)
    
    def __repr__(self) -> str:
        return f"Stack({self._items})"

# Type checker samjhega:
int_stack: Stack[int] = Stack()
int_stack.push(1)
int_stack.push(2)
print(int_stack.pop())  # 2

str_stack: Stack[str] = Stack()
str_stack.push("hello")
# str_stack.push(42)  # mypy/pyright error!
```

### `bound=` vs Constraints

```python
from typing import TypeVar

# bound: T must be Comparable subtype
Comparable = TypeVar('T', bound='SupportsLessThan')

# Constraints: T can ONLY be one of these specific types
AnyStr = TypeVar('AnyStr', str, bytes)

def process_text(text: AnyStr) -> AnyStr:
    # text must be EXACTLY str or bytes, nothing else
    if isinstance(text, str):
        return text.upper()
    return text.upper()

# bound: more flexible — any subtype works
class Animal:
    def __lt__(self, other): ...

AnimalT = TypeVar('AnimalT', bound=Animal)

def smallest(a: AnimalT, b: AnimalT) -> AnimalT:
    return a if a < b else b
```

### `ParamSpec` — Capture Function Signatures (Python 3.10+)

```python
from typing import ParamSpec, Callable, TypeVar

P = ParamSpec('P')
T = TypeVar('T')

def decorator(func: Callable[P, T]) -> Callable[P, T]:
    """Decorator jo function signature preserve kare"""
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        print(f"Calling {func.__name__}")
        return func(*args, **kwargs)
    return wrapper

@decorator
def add(x: int, y: int) -> int:
    return x + y

# Type checker jaanta hai add(x: int, y: int) → int
result = add(1, 2)
```

### Multiple TypeVars

```python
K = TypeVar('K')
V = TypeVar('V')

class BiMap(Generic[K, V]):
    """Two-way mapping"""
    
    def __init__(self):
        self._forward: dict[K, V] = {}
        self._reverse: dict[V, K] = {}
    
    def put(self, key: K, value: V) -> None:
        self._forward[key] = value
        self._reverse[value] = key
    
    def get_by_key(self, key: K) -> V:
        return self._forward[key]
    
    def get_by_value(self, value: V) -> K:
        return self._reverse[value]

bm: BiMap[str, int] = BiMap()
bm.put("one", 1)
print(bm.get_by_key("one"))   # 1
print(bm.get_by_value(1))     # "one"
```

---

## Section 11: `Protocol` — Structural Typing

Duck typing ko **type-safe** banana.

### `Protocol` vs `ABC`

```python
# ABC — Nominal Subtyping (inheritance required)
from abc import ABC, abstractmethod

class Drawable(ABC):
    @abstractmethod
    def draw(self) -> str: ...

class Circle(Drawable):  # Explicit inheritance REQUIRED
    def draw(self): return "○"

# Protocol — Structural Subtyping (duck typing + type safety)
from typing import Protocol

class DrawableProto(Protocol):
    def draw(self) -> str: ...

class Square:  # NO inheritance needed!
    def draw(self): return "□"

def render(shape: DrawableProto) -> None:
    print(shape.draw())

render(Square())  # Works! Square matches DrawableProto structurally
render(Circle())  # Works too!
```

### `@runtime_checkable` — `isinstance()` Enable Karo

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class Serializable(Protocol):
    def to_json(self) -> str: ...
    def to_dict(self) -> dict: ...

class User:
    def to_json(self): return '{"name": "Rahul"}'
    def to_dict(self): return {'name': 'Rahul'}

class Config:
    def to_json(self): return '{}'
    def to_dict(self): return {}

class Random:
    pass

u = User()
print(isinstance(u, Serializable))      # True
print(isinstance(Config(), Serializable))  # True
print(isinstance(Random(), Serializable))  # False

# Warning: @runtime_checkable only method names check karta hai
# Signature check nahi karta (method arity/types)
```

### Protocol with Attributes

```python
@runtime_checkable
class HasName(Protocol):
    name: str  # Attribute bhi protocol mein

class Product:
    name: str = "Widget"

class Anonymous:
    pass

print(isinstance(Product(), HasName))    # True
print(isinstance(Anonymous(), HasName))  # False
```

### Protocol with `__call__`

```python
from typing import Protocol

class Callback(Protocol):
    def __call__(self, event: str, data: dict) -> None: ...

def register_handler(handler: Callback) -> None:
    handler("click", {"x": 10, "y": 20})

def my_handler(event: str, data: dict) -> None:
    print(f"Event: {event}, Data: {data}")

class MyHandler:
    def __call__(self, event: str, data: dict) -> None:
        print(f"Handling {event}")

register_handler(my_handler)     # Function works
register_handler(MyHandler())    # Callable class works
```

### Protocol in Generics

```python
from typing import Protocol, TypeVar, runtime_checkable

@runtime_checkable
class Comparable(Protocol):
    def __lt__(self, other) -> bool: ...
    def __le__(self, other) -> bool: ...

T = TypeVar('T', bound=Comparable)

def find_minimum(items: list[T]) -> T:
    """Works with any type that implements comparison"""
    return min(items)

print(find_minimum([3, 1, 4, 1, 5]))          # 1
print(find_minimum(["banana", "apple", "cherry"]))  # apple
```

---

## Section 12: Real-World Patterns

### Pattern 1: Validated Attribute System (Production-Ready)

```python
from typing import Any, Optional, Type
import re

class Field:
    """Production-grade validated attribute descriptor"""
    
    def __set_name__(self, owner, name):
        self.name = name
        self.private = f'__field_{name}'
    
    def __get__(self, obj, objtype=None):
        if obj is None: return self
        return getattr(obj, self.private, self.get_default())
    
    def __set__(self, obj, value):
        value = self.coerce(value)
        self.validate(value)
        setattr(obj, self.private, value)
    
    def get_default(self): return None
    def coerce(self, value): return value
    def validate(self, value): pass

class StringField(Field):
    def __init__(self, min_len=0, max_len=255, pattern=None, nullable=False):
        self.min_len = min_len
        self.max_len = max_len
        self.pattern = re.compile(pattern) if pattern else None
        self.nullable = nullable
    
    def validate(self, value):
        if value is None:
            if not self.nullable:
                raise ValueError(f"'{self.name}' cannot be None")
            return
        if not isinstance(value, str):
            raise TypeError(f"'{self.name}' must be str")
        if len(value) < self.min_len:
            raise ValueError(f"'{self.name}' too short")
        if len(value) > self.max_len:
            raise ValueError(f"'{self.name}' too long")
        if self.pattern and not self.pattern.match(value):
            raise ValueError(f"'{self.name}' doesn't match pattern")

class EmailField(StringField):
    def __init__(self, **kwargs):
        super().__init__(
            pattern=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
            max_len=255,
            **kwargs
        )

class IntField(Field):
    def __init__(self, min_val=None, max_val=None):
        self.min_val = min_val
        self.max_val = max_val
    
    def coerce(self, value):
        return int(value)  # Auto-coerce
    
    def validate(self, value):
        if self.min_val is not None and value < self.min_val:
            raise ValueError(f"'{self.name}' must be >= {self.min_val}")
        if self.max_val is not None and value > self.max_val:
            raise ValueError(f"'{self.name}' must be <= {self.max_val}")

# Usage:
class UserProfile:
    username = StringField(min_len=3, max_len=30, pattern=r'^[a-zA-Z0-9_]+$')
    email = EmailField()
    age = IntField(min_val=13, max_val=120)
    bio = StringField(max_len=500, nullable=True)
```

### Pattern 2: Lazy Loading Descriptor

```python
class LazyLoader:
    """Compute once, cache forever — lazy evaluation descriptor"""
    
    def __init__(self, func):
        self.func = func
        self.__doc__ = func.__doc__
    
    def __set_name__(self, owner, name):
        self.name = name
    
    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        # Cache in instance __dict__ with same name
        # Next access → instance __dict__ wins (non-data descriptor!)
        value = self.func(obj)
        obj.__dict__[self.name] = value  # Cache it!
        return value

class HeavyReport:
    def __init__(self, data):
        self.data = data
    
    @LazyLoader
    def summary(self):
        """Expensive report generation."""
        print("  [Computing summary...]")
        return {'total': sum(self.data), 'count': len(self.data)}
    
    @LazyLoader
    def statistics(self):
        """Statistical analysis."""
        print("  [Computing statistics...]")
        mean = sum(self.data) / len(self.data)
        return {'mean': mean, 'max': max(self.data), 'min': min(self.data)}

r = HeavyReport([1, 2, 3, 4, 5])
print(r.summary)     # [Computing...] → {'total': 15, 'count': 5}
print(r.summary)     # No [Computing...] → cached!
print(r.statistics)  # [Computing...] → {'mean': 3.0, ...}
```

### Pattern 3: Auto-Register Metaclass (Plugin System)

```python
class PluginBase:
    """
    Production plugin system.
    Koi bhi class subclass kare → automatically registered.
    """
    _registry: dict[str, type] = {}
    
    def __init_subclass__(cls, plugin_name: str = None, **kwargs):
        super().__init_subclass__(**kwargs)
        name = plugin_name or cls.__name__
        PluginBase._registry[name] = cls
    
    @classmethod
    def get_plugin(cls, name: str) -> Optional[type]:
        return cls._registry.get(name)
    
    @classmethod
    def create(cls, name: str, *args, **kwargs):
        plugin_cls = cls.get_plugin(name)
        if not plugin_cls:
            available = list(cls._registry.keys())
            raise ValueError(f"Unknown plugin '{name}'. Available: {available}")
        return plugin_cls(*args, **kwargs)

class StoragePlugin(PluginBase):
    """Base class for storage plugins"""
    def save(self, key, value): raise NotImplementedError
    def load(self, key): raise NotImplementedError

class S3Storage(StoragePlugin, plugin_name="s3"):
    def __init__(self, bucket): self.bucket = bucket
    def save(self, key, value): return f"S3({self.bucket})/{key} = {value}"
    def load(self, key): return f"Loading from S3/{key}"

class LocalStorage(StoragePlugin, plugin_name="local"):
    def __init__(self, path="/tmp"): self.path = path
    def save(self, key, value): return f"local:{self.path}/{key} = {value}"
    def load(self, key): return f"Loading from {self.path}/{key}"

# Usage:
storage = PluginBase.create("s3", bucket="my-app-data")
print(storage.save("users/1", {"name": "Rahul"}))
```

### Pattern 4: ORM-like System

```python
class ORMField:
    """ORM field descriptor — Django CharField jaisa"""
    
    def __init__(self, column_type="TEXT", nullable=True, default=None):
        self.column_type = column_type
        self.nullable = nullable
        self.default = default
        self.column_name = None
    
    def __set_name__(self, owner, name):
        self.attr_name = name
        self.column_name = name  # Database column name
    
    def __get__(self, obj, objtype=None):
        if obj is None: return self
        return obj.__dict__.get(self.attr_name, self.default)
    
    def __set__(self, obj, value):
        if not self.nullable and value is None:
            raise ValueError(f"Column '{self.column_name}' cannot be NULL")
        obj.__dict__[self.attr_name] = value

class ORMMeta(type):
    def __new__(mcs, name, bases, namespace):
        fields = {k: v for k, v in namespace.items() if isinstance(v, ORMField)}
        cls = super().__new__(mcs, name, bases, namespace)
        cls._meta_fields = fields
        cls._meta_table = name.lower() + 's'
        return cls

class ORMModel(metaclass=ORMMeta):
    def save(self):
        cols = list(self._meta_fields.keys())
        vals = [getattr(self, c) for c in cols]
        sql = f"INSERT INTO {self._meta_table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})"
        return sql, vals
    
    @classmethod
    def create_table_sql(cls):
        col_defs = [f"{name} {field.column_type}" 
                   for name, field in cls._meta_fields.items()]
        return f"CREATE TABLE {cls._meta_table} ({', '.join(col_defs)});"

class Article(ORMModel):
    title = ORMField("VARCHAR(200)", nullable=False)
    body = ORMField("TEXT")
    views = ORMField("INTEGER", default=0)

print(Article.create_table_sql())
# CREATE TABLE articles (title VARCHAR(200), body TEXT, views INTEGER);

a = Article()
a.title = "Python Metaclasses"
a.body = "Deep dive into metaclasses..."
sql, params = a.save()
print(sql)     # INSERT INTO articles (title, body, views) VALUES (?, ?, ?)
print(params)  # ['Python Metaclasses', 'Deep dive...', 0]
```

### Pattern 5: Thread-Safe Singleton with Metaclass

```python
import threading
from typing import Any

class ThreadSafeSingletonMeta(type):
    """Production-grade thread-safe singleton metaclass"""
    
    _instances: dict = {}
    _lock: threading.Lock = threading.Lock()
    
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            with cls._lock:
                # Double-checked locking pattern
                if cls not in cls._instances:
                    instance = super().__call__(*args, **kwargs)
                    cls._instances[cls] = instance
        return cls._instances[cls]

class DatabasePool(metaclass=ThreadSafeSingletonMeta):
    def __init__(self, max_connections=10):
        self.max_connections = max_connections
        self.pool = []
        print(f"  DB Pool created with {max_connections} connections")
    
    def get_connection(self):
        return f"Connection from pool (size: {self.max_connections})"

# Thread-safe test:
results = []
def create_pool():
    results.append(DatabasePool(10))

threads = [threading.Thread(target=create_pool) for _ in range(5)]
for t in threads: t.start()
for t in threads: t.join()

print(all(r is results[0] for r in results))  # True — same instance!
```

---

## Section 13: 12 Interview Questions & Answers

### Q1: `__new__` vs `__init__` mein kya fark hai?

**Answer:**

`__new__` object **create** karta hai — yeh class method hai jo class object receive karta hai (`cls`) aur ek naya instance return karta hai. `__init__` object **initialize** karta hai — yeh instance method hai jo already-created instance receive karta hai (`self`) aur kuch return nahi karta (None).

Critical difference: Agar `__new__` kisi aur type ka instance return kare, to `__init__` **call nahi hoga**. Practical use: Immutable types (`int`, `str`, `tuple`) ko subclass karna ho to `__new__` mein hi value set karni padti hai.

```python
class PositiveInt(int):
    def __new__(cls, value):
        if value <= 0: raise ValueError
        return super().__new__(cls, value)  # __init__ not needed!
```

---

### Q2: Metaclass ka real use case kya hai? Real code mein kahan use hota hai?

**Answer:**

Metaclass 4 jagah genuinely useful hai:

1. **ORM field declaration** — Django ka `Model`, SQLAlchemy ka `Base` — `ModelBase` metaclass sab fields scan karta hai aur `_meta` object banata hai.

2. **Auto-registration** — Plugin systems jahan subclasses automatically register hon without manual code.

3. **Singleton pattern** — Thread-safe singleton metaclass se multiple classes singleton ban sakti hain (code reuse).

4. **Interface enforcement** — Compile time pe check karo ki required methods implement hain ya nahi.

**Modern alternative**: Python 3.6+ mein `__init_subclass__` most metaclass use cases handle karta hai without the complexity.

---

### Q3: Django ORM mein metaclass kaise kaam karta hai?

**Answer:**

Django ka `ModelBase` metaclass (`django.db.models.base.ModelBase`) kaam karta hai:

1. Class creation pe `__new__` call hota hai
2. Class namespace mein jo bhi `Field` instances hain (`CharField`, `IntegerField`, etc.) scan karta hai
3. `Options` object (`_meta`) banata hai with field metadata
4. Fields ko actual Python attributes mein convert karta hai (descriptors)
5. `DoesNotExist` exception class inject karta hai
6. App registry mein model register karta hai

Conceptually:
```python
class ModelBase(type):
    def __new__(mcs, name, bases, attrs):
        fields = {k: v for k, v in attrs.items() if isinstance(v, Field)}
        cls = super().__new__(mcs, name, bases, attrs)
        cls._meta = Options(fields)
        return cls
```

---

### Q4: Descriptor lookup order kya hai?

**Answer:**

Python attribute access exactly is order mein check karta hai:

1. **Data Descriptor** (`__get__` + `__set__`/`__delete__`) — class hierarchy mein
2. **Instance `__dict__`** — object ka personal dictionary
3. **Non-Data Descriptor** (`__get__` only) + other class attributes

Is order ka matlab:
- `property` (data descriptor) instance `__dict__` ko override karta hai
- `functools.cached_property` (non-data descriptor) instance `__dict__` se override **ho jaata hai** — yahi caching mechanism hai!

---

### Q5: Data vs Non-Data Descriptor mein kya fark hai?

**Answer:**

**Data Descriptor**: `__get__` aur `__set__` (ya `__delete__`) dono implement karta hai.
- Instance `__dict__` se **zyada priority** hoti hai
- Example: `property`, custom validators

**Non-Data Descriptor**: Sirf `__get__` implement karta hai.
- Instance `__dict__` se **kam priority** hoti hai
- Example: Functions/methods, `classmethod`, `staticmethod`, `cached_property`

Why does it matter? `cached_property` deliberately non-data hai — first call pe value compute karke instance `__dict__` mein store karta hai; next call pe instance `__dict__` descriptor ko override karta hai → automatic caching!

---

### Q6: `__slots__` kitna memory save karta hai?

**Answer:**

Real numbers:
- Without `__slots__`: Object header (~48B) + `__dict__` (~232B) = **~280 bytes** per instance
- With `__slots__`: Object header + slot array = **~56 bytes** per instance (3 slots)
- **~5x memory reduction**

1 million objects:
- `__dict__`: ~280 MB
- `__slots__`: ~56 MB
- Saving: ~224 MB

`__slots__` `__dict__` ko C-level fixed-size array se replace karta hai. Tradeoff: dynamic attributes nahi ban sakte, complex inheritance issues aa sakte hain.

---

### Q7: `__set_name__` ka purpose kya hai?

**Answer:**

`__set_name__(self, owner, name)` Python 3.6+ mein descriptor ko **apna attribute name** automatically bata deta hai — bina manually naam pass kiye.

Before `__set_name__`:
```python
class OldStyle:
    x = TypedAttr('x')  # Name duplicate — error prone!
```

After `__set_name__`:
```python
class NewStyle:
    x = TypedAttr()  # Python automatically calls TypedAttr.__set_name__(NewStyle, 'x')
```

Django/SQLAlchemy type ORMs mein bahut useful hai — field automatically jaanti hai uska column name kya hai.

---

### Q8: `__init_subclass__` vs Metaclass — Kab Kya Choose Karo?

**Answer:**

**`__init_subclass__` use karo** jab:
- Subclass registration chahiye
- Subclass attributes/methods validate karne hain
- Simple class-level configuration inject karni hai
- Multiple inheritance se bachna hai

**Metaclass use karo** jab:
- Class creation ka **full control** chahiye (`__prepare__`, `__new__`, `__call__`)
- Instance creation intercept karna hai (`__call__`)
- Namespace ko class body execute **hone se pehle** modify karna hai
- Singleton, thread-safety at class level chahiye
- ORM-like complex field processing

Rule: Pehle `__init_subclass__` try karo. Sirf tab metaclass use karo jab genuinely `__prepare__` ya `__call__` ki zaroorat ho.

---

### Q9: `property` ek descriptor hai — explain karo.

**Answer:**

`property` ek **data descriptor** class hai (C mein implement). Iske paas:
- `__get__`: getter function call karta hai (ya `AttributeError` agar getter nahi)
- `__set__`: setter function call karta hai (ya `AttributeError` agar setter nahi)
- `__delete__`: deleter function call karta hai

```python
# @property decorator is just:
class Foo:
    def _get_x(self): return self._x
    x = property(_get_x)  # property descriptor assigned

# @x.setter is just:
# x = x.setter(new_setter_func)  # Returns new property with setter
```

Data descriptor hone ki wajah se `property` hamesha instance `__dict__` se **zyada priority** rakhti hai — isliye agar `obj.__dict__['name'] = 'hack'` karo to bhi `obj.name` property se hi milega.

---

### Q10: `Protocol` vs `ABC` — Kab Kya Use Karo?

**Answer:**

**ABC (Abstract Base Classes)** — **Nominal subtyping**:
- Explicitly inherit karna padta hai
- `isinstance()` check reliable hai
- Use karo: Library internals, tightly coupled hierarchies

**Protocol** — **Structural subtyping (duck typing + types)**:
- Inheritance required nahi
- Jo class protocol ke methods implement kare, compatible hai
- `@runtime_checkable` se `isinstance()` work karta hai (method names only check)
- Use karo: Function parameters, loose coupling, third-party classes integrate karna

**Guideline**:
- **Protocol** is better for function parameters: `def render(shape: DrawableProto)`
- **ABC** is better for defining a hierarchy: `class Animal(ABC)`
- **Protocol** third-party libraries ke saath better kaam karta hai

---

### Q11: `TypeVar` mein `bound` vs `constraints` — fark kya hai?

**Answer:**

**`bound`**: `T` must be **subtype of** the bound.
```python
T = TypeVar('T', bound=int)
# T can be: int, bool, PositiveInt — any subclass of int
# T CANNOT be: str, float
```

**Constraints**: `T` must be **exactly** one of the listed types.
```python
T = TypeVar('T', str, bytes)
# T can be: str OR bytes — nothing else
# T CANNOT be: bytearray (even though bytes-like)
```

Key difference: With `bound`, you can use any method of the bound class. With constraints, the type is narrowed to exactly one of the options at each call site.

```python
AnyStr = TypeVar('AnyStr', str, bytes)
def upper(x: AnyStr) -> AnyStr:
    return x.upper()  # Works — str and bytes both have upper()
```

---

### Q12: Kab Metaclass use **nahi** karna chahiye?

**Answer:**

Metaclass **avoid karo** jab:

1. `__init_subclass__` ya decorators kaam kar sakte hain — simpler options pehle try karo
2. Codebase mein multiple frameworks use ho rahe hain jinka metaclass conflict kar sakta hai (Django + custom = `TypeError: metaclass conflict`)
3. Team mein sabko metaclass samajh mein nahi aata — maintainability suffers
4. Simple validation ke liye — `__post_init__` ya Pydantic better hai
5. Python 3.6+ mein — `__init_subclass__` 80% cases handle karta hai

**Golden rule**: "If you think you need a metaclass, you probably don't. If you know you need one, you might be right." — Tim Peters (paraphrased)

Real production code mein metaclass typically sirf frameworks mein (Django ORM, SQLAlchemy, FastAPI router) aur plugin systems mein use hote hain.

---

## Quick Reference Card

```
Object Model:
  instance → class → metaclass → type → type (self-referential)

Class Creation Order:
  metaclass.__prepare__ → body execution → __new__ → __init__

Instance Creation Order:
  metaclass.__call__ → class.__new__ → class.__init__ → instance

Descriptor Priority:
  data descriptor > instance __dict__ > non-data descriptor

__slots__ Memory:
  With __dict__: ~280B per instance
  With __slots__: ~56B per instance (5x savings)

When to Use:
  metaclass → ORM, singleton, plugin system
  __init_subclass__ → registration, validation (simpler)
  descriptor → validated attrs, lazy loading, ORM fields
  __slots__ → millions of instances, memory-critical
  Protocol → duck typing + type safety
  ABC → strict inheritance hierarchy
```

---

*Series: Python Backend Developer Interview Prep | 40 LPA Track*
*Prev: 05_async_concurrency_deep_dive.md | Next: 07_cpython_internals.md*
