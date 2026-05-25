"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ABSTRACT BASE CLASSES (ABC) AND PROTOCOLS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ARCHITECTURE UNDERSTANDING:
  ABC (Abstract Base Class):
  → Define INTERFACE — what methods subclasses MUST implement
  → Cannot instantiate ABC itself
  → @abstractmethod = must override in subclass
  → Runtime error if subclass doesn't implement abstract methods

  Protocol (typing.Protocol):
  → Structural subtyping — "duck typing with types"
  → Class doesn't need to explicitly inherit
  → Just needs the right methods/attributes
  → Used with @runtime_checkable for isinstance() checks

  ABC vs Protocol:
  ABC      = explicit inheritance required, nominal typing
  Protocol = no inheritance needed, structural typing
  Use ABC when you want forced inheritance + shared code.
  Use Protocol for type hints with duck typing.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from abc import ABC, abstractmethod, ABCMeta
from typing import Protocol, runtime_checkable
import math

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. BASIC ABC
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

class Shape(ABC):
    """Abstract base — all shapes must implement area() and perimeter()."""

    @abstractmethod
    def area(self) -> float:
        """Calculate area — MUST be implemented by subclass."""
        ...

    @abstractmethod
    def perimeter(self) -> float:
        """Calculate perimeter — MUST be implemented by subclass."""
        ...

    # Concrete method — shared by all subclasses (CAN override)
    def describe(self) -> str:
        return f"{self.__class__.__name__}: area={self.area():.2f}, perimeter={self.perimeter():.2f}"

    # Class method in ABC
    @classmethod
    def validate_positive(cls, value: float, name: str) -> float:
        if value <= 0:
            raise ValueError(f"{name} must be positive, got {value}")
        return value


# Can't instantiate ABC directly:
# s = Shape()   → TypeError: Can't instantiate abstract class Shape


class Circle(Shape):
    def __init__(self, radius: float):
        self.radius = self.validate_positive(radius, "radius")

    def area(self) -> float:
        return math.pi * self.radius ** 2

    def perimeter(self) -> float:
        return 2 * math.pi * self.radius


class Rectangle(Shape):
    def __init__(self, width: float, height: float):
        self.width  = self.validate_positive(width, "width")
        self.height = self.validate_positive(height, "height")

    def area(self) -> float:
        return self.width * self.height

    def perimeter(self) -> float:
        return 2 * (self.width + self.height)


class Triangle(Shape):
    def __init__(self, a: float, b: float, c: float):
        self.a, self.b, self.c = a, b, c

    def area(self) -> float:
        s = (self.a + self.b + self.c) / 2
        return math.sqrt(s * (s-self.a) * (s-self.b) * (s-self.c))

    def perimeter(self) -> float:
        return self.a + self.b + self.c


shapes: list[Shape] = [Circle(5), Rectangle(4, 6), Triangle(3, 4, 5)]
for shape in shapes:
    print(shape.describe())


# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. ABSTRACT PROPERTY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

class Vehicle(ABC):

    @property
    @abstractmethod
    def max_speed(self) -> float:
        """Subclass must implement this property."""
        ...

    @abstractmethod
    def fuel_type(self) -> str:
        ...

    def info(self) -> str:
        return f"{self.__class__.__name__}: max_speed={self.max_speed}km/h, fuel={self.fuel_type()}"


class Car(Vehicle):
    @property
    def max_speed(self) -> float:
        return 200.0

    def fuel_type(self) -> str:
        return "Petrol"


class ElectricCar(Vehicle):
    @property
    def max_speed(self) -> float:
        return 250.0

    def fuel_type(self) -> str:
        return "Electric"


print(Car().info())
print(ElectricCar().info())

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. REAL-WORLD: REPOSITORY PATTERN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
INTERVIEW Q: ABC ka real use in backend?
A: Repository pattern — define interface for data access.
   Multiple implementations: PostgreSQL, SQLite, In-Memory (for tests).
   Application code depends on interface, not implementation.
"""

from typing import TypeVar, Generic, Optional

T = TypeVar("T")

class BaseRepository(ABC, Generic[T]):
    """Abstract repository interface — data access contract."""

    @abstractmethod
    async def get_by_id(self, id: int) -> Optional[T]:
        ...

    @abstractmethod
    async def get_all(self, limit: int = 100, offset: int = 0) -> list[T]:
        ...

    @abstractmethod
    async def create(self, data: dict) -> T:
        ...

    @abstractmethod
    async def update(self, id: int, data: dict) -> Optional[T]:
        ...

    @abstractmethod
    async def delete(self, id: int) -> bool:
        ...


class InMemoryUserRepository(BaseRepository):
    """In-memory implementation — for testing."""

    def __init__(self):
        self._store: dict[int, dict] = {}
        self._next_id = 1

    async def get_by_id(self, id: int) -> Optional[dict]:
        return self._store.get(id)

    async def get_all(self, limit: int = 100, offset: int = 0) -> list[dict]:
        items = list(self._store.values())
        return items[offset:offset + limit]

    async def create(self, data: dict) -> dict:
        user = {"id": self._next_id, **data}
        self._store[self._next_id] = user
        self._next_id += 1
        return user

    async def update(self, id: int, data: dict) -> Optional[dict]:
        if id not in self._store:
            return None
        self._store[id].update(data)
        return self._store[id]

    async def delete(self, id: int) -> bool:
        return self._store.pop(id, None) is not None


# Application service doesn't know which implementation it uses
class UserService:
    def __init__(self, repo: BaseRepository):  # depends on abstraction
        self.repo = repo

    async def register(self, name: str, email: str) -> dict:
        return await self.repo.create({"name": name, "email": email})

# In production: PostgresUserRepository
# In tests:      InMemoryUserRepository
import asyncio
service = UserService(InMemoryUserRepository())
user = asyncio.run(service.register("Ashish", "ashish@email.com"))
print(user)     # {'id': 1, 'name': 'Ashish', 'email': 'ashish@email.com'}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. PROTOCOL — STRUCTURAL TYPING
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
Protocol = structural subtyping (duck typing + type hints)
Class doesn't need to inherit — just needs the right methods.
"""

@runtime_checkable
class Drawable(Protocol):
    def draw(self) -> str:
        ...

    def get_color(self) -> str:
        ...


# These classes don't inherit from Drawable!
class Dot:
    def draw(self) -> str:
        return "• "

    def get_color(self) -> str:
        return "black"


class Star:
    def draw(self) -> str:
        return "★ "

    def get_color(self) -> str:
        return "yellow"


class NotDrawable:
    pass


def render(item: Drawable) -> str:
    return f"{item.draw()} ({item.get_color()})"


# Works! Structural typing
print(render(Dot()))    # •  (black)
print(render(Star()))   # ★  (yellow)

# isinstance check (because @runtime_checkable)
print(isinstance(Dot(), Drawable))           # True
print(isinstance(NotDrawable(), Drawable))   # False

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. ABC vs PROTOCOL COMPARISON
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
ABC (explicit inheritance):
  ✓ Subclass MUST implement abstract methods (runtime error if not)
  ✓ Can provide default implementations (concrete methods)
  ✓ Can have __init__ with shared setup
  ✓ isinstance() works naturally
  ✗ Must import and inherit — coupling

Protocol (structural):
  ✓ No inheritance needed — just have the right methods
  ✓ Works with third-party classes you can't modify
  ✓ Type checker validates at check time, not runtime
  ✗ No shared implementation
  ✗ @runtime_checkable needed for isinstance()

RULE:
  ABC     → Internal hierarchy, shared code, clear parent-child
  Protocol → Interface for type hints, third-party integration
"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 6. MIXINS WITH ABC
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

class SerializableMixin:
    """Mixin — adds serialization capability to any class."""

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}

    def to_json(self) -> str:
        import json
        return json.dumps(self.to_dict())


class LoggableMixin:
    """Mixin — adds logging to any class."""

    def log(self, message: str):
        print(f"[{self.__class__.__name__}] {message}")


class Product(SerializableMixin, LoggableMixin):
    """Inherits from multiple mixins — no ABC needed here."""

    def __init__(self, name: str, price: float):
        self.name = name
        self.price = price

    def apply_discount(self, percent: float):
        self.price *= (1 - percent / 100)
        self.log(f"Discount {percent}% applied. New price: {self.price}")


p = Product("Laptop", 50000)
p.apply_discount(10)
print(p.to_json())

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INTERVIEW Q&A:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q: ABC kab use karein?
A: Jab aap ek interface define karna chahte ho aur ensure karna chahte ho
   ki saare subclasses specific methods implement karein.
   Example: Shape, Repository, Serializer, Plugin system.

Q: @abstractmethod ke bina bhi ABC kaam karta hai?
A: Haan. ABC without @abstractmethod = instantiable ABC.
   Useful for mixin base classes or when you just want ABC registration.

Q: Protocol vs ABC — dono interface define karte hain, difference?
A: ABC → nominal typing (must inherit), runtime enforcement
   Protocol → structural typing (just have right methods), type-checker enforcement
   Protocol is more flexible but less strict at runtime.

Q: Mixin kya hota hai?
A: Class jo sirf methods add karta hai, independent use ke liye nahi.
   Multiple inheritance se add karte hain.
   No __init__ usually. No state usually.
   Example: SerializableMixin, LoggableMixin, TimestampMixin.
"""
