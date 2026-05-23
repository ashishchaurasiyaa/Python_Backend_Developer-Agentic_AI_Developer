"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DATACLASSES — Modern Python Data Containers
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ARCHITECTURE UNDERSTANDING:
  @dataclass = decorator that auto-generates:
  __init__, __repr__, __eq__ based on class annotations.

  WHY DATACLASSES?
  → Eliminates boilerplate (no manual __init__ writing)
  → Self-documenting via type annotations
  → Multiple variants: mutable, frozen (immutable), slotted

  DATACLASS vs PYDANTIC:
  dataclass = Python stdlib, lightweight, no runtime validation
  Pydantic  = third-party, runtime validation, used in FastAPI
  Use dataclass for internal data structures.
  Use Pydantic for API input/output validation.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from dataclasses import dataclass, field, asdict, astuple, replace, fields
from typing import ClassVar
import json

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. BASIC DATACLASS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class Point:
    x: float
    y: float

p1 = Point(1.0, 2.0)
p2 = Point(1.0, 2.0)
p3 = Point(3.0, 4.0)

print(p1)           # Point(x=1.0, y=2.0)  ← __repr__ auto-generated
print(p1 == p2)     # True  ← __eq__ auto-generated (compares all fields)
print(p1 == p3)     # False

# This replaces writing:
class PointManual:
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y
    def __repr__(self):
        return f"Point(x={self.x}, y={self.y})"
    def __eq__(self, other):
        return self.x == other.x and self.y == other.y

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. FIELD OPTIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class Employee:
    name: str
    age: int
    department: str = "Engineering"                  # default value
    skills: list[str] = field(default_factory=list)  # mutable default — MUST use field()
    _id: int = field(default=0, repr=False)          # hidden from repr
    salary: float = field(default=0.0, compare=False)# excluded from __eq__

    # Class variable (shared, not instance field)
    company: ClassVar[str] = "TechCorp"

e1 = Employee("Ashish", 28)
e2 = Employee("Ashish", 28, skills=["Python", "FastAPI"])

print(e1)               # Employee(name='Ashish', age=28, department='Engineering')
print(e1 == e2)         # True (salary excluded from compare)
print(Employee.company) # TechCorp

# Mutable default gotcha — MUST use field(default_factory=...)
# @dataclass
# class Bad:
#     tags: list = []  # ValueError: mutable default not allowed

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. __POST_INIT__ — POST-CREATION PROCESSING
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class Rectangle:
    width: float
    height: float
    area: float = field(init=False)         # not in __init__, computed in __post_init__

    def __post_init__(self):
        """Called after __init__ automatically."""
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Dimensions must be positive")
        self.area = self.width * self.height    # computed from other fields

r = Rectangle(5.0, 3.0)
print(r)        # Rectangle(width=5.0, height=3.0, area=15.0)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. FROZEN DATACLASS — IMMUTABLE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass(frozen=True)
class Color:
    """Immutable color — can be used as dict key or in set."""
    r: int
    g: int
    b: int

    @property
    def hex(self) -> str:
        return f"#{self.r:02x}{self.g:02x}{self.b:02x}"

RED   = Color(255, 0, 0)
GREEN = Color(0, 255, 0)
BLUE  = Color(0, 0, 255)

print(RED.hex)          # #ff0000
print(hash(RED))        # hashable because frozen=True

# Can use as dict key or in set
palette = {RED, GREEN, BLUE}
color_names = {RED: "Red", GREEN: "Green", BLUE: "Blue"}

# try:
#     RED.r = 100     # FrozenInstanceError — can't modify
# except Exception as e:
#     print(e)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. ORDERING — @dataclass(order=True)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass(order=True)
class Student:
    gpa: float
    name: str

    # order=True generates __lt__, __le__, __gt__, __ge__
    # compares fields IN ORDER: first gpa, then name

students = [Student(3.5, "Ashish"), Student(3.8, "Priya"), Student(3.5, "Rahul")]
print(sorted(students))  # sorted by gpa first, then name

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 6. UTILITY FUNCTIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class Config:
    host: str = "localhost"
    port: int = 5432
    database: str = "myapp"
    debug: bool = False

config = Config(host="db.prod.com", port=5432)

# Convert to dict (for JSON serialization, logging)
config_dict = asdict(config)
print(config_dict)      # {'host': 'db.prod.com', 'port': 5432, ...}
print(json.dumps(config_dict))  # JSON serializable

# Convert to tuple
config_tuple = astuple(config)
print(config_tuple)     # ('db.prod.com', 5432, 'myapp', False)

# Create modified copy (like a spread/copy with changes)
prod_config = replace(config, debug=False, database="myapp_prod")
print(prod_config)

# Introspect fields
for f in fields(Config):
    print(f"Field: {f.name}, Type: {f.type}, Default: {f.default}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 7. SLOTS FOR MEMORY EFFICIENCY (Python 3.10+)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass(slots=True)      # Python 3.10+
class Coordinate:
    """slots=True: faster attribute access, less memory per instance."""
    lat: float
    lon: float
    alt: float = 0.0

import sys
c = Coordinate(28.6, 77.2)
print(sys.getsizeof(c))     # smaller than non-slotted equivalent

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 8. REAL-WORLD: API RESPONSE MODELS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

from datetime import datetime

@dataclass
class APIResponse:
    """Standard API response wrapper."""
    success: bool
    data: dict | list | None = None
    error: str | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    request_id: str = field(default="", repr=False)

    def to_json(self) -> str:
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        return json.dumps(d)


success_response = APIResponse(success=True, data={"user_id": 42})
error_response   = APIResponse(success=False, error="User not found")

print(success_response)
print(error_response.to_json())

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INTERVIEW Q&A:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q: dataclass vs NamedTuple vs plain class?
A: plain class      → full control, verbose, use for behavior-heavy objects
   dataclass        → data + some behavior, mutable, stdlib
   NamedTuple       → immutable, tuple-compatible, lightweight
   frozen dataclass → immutable + hashable, use as dict key

Q: Mutable default value kyun field() chahiye?
A: Without field(default_factory=list):
   ALL instances share THE SAME list object.
   Mutating one changes all — classic Python gotcha.

Q: dataclass vs Pydantic?
A: dataclass = lightweight, no runtime validation, stdlib
   Pydantic  = runtime validation, coercion, JSON schema, FastAPI uses it
   For API inputs → Pydantic. For internal data → dataclass.

Q: frozen=True kab use karte hain?
A: Dict keys, set elements (need hashable)
   Config objects that shouldn't change after creation
   Thread-safe data sharing (immutable = no race conditions)
"""
