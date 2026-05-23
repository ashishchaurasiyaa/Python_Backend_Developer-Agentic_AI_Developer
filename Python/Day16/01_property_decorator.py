"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@PROPERTY DECORATOR — Getter, Setter, Deleter
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ARCHITECTURE UNDERSTANDING:
  @property converts a method into an attribute-like access.
  Used with @name.setter and @name.deleter for full control.

  WHY USE @property?
  → Clean API: user writes obj.name = "Alice" instead of obj.set_name("Alice")
  → Validation on assignment (setter controls what's allowed)
  → Computed/derived attributes (property calculates on-the-fly)
  → Backward compatibility: start with plain attribute, add validation later

  HOW IT WORKS (descriptor protocol internally):
  @property creates a descriptor object.
  When you access obj.attr → calls __get__
  When you set obj.attr  → calls __set__  (only if setter defined)
  When you del obj.attr  → calls __delete__ (only if deleter defined)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. BASIC @property
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

class Circle:
    def __init__(self, radius):
        self._radius = radius       # private by convention (_radius)

    @property
    def radius(self):
        """Getter: called when you read circle.radius"""
        return self._radius

    @radius.setter
    def radius(self, value):
        """Setter: called when you write circle.radius = value"""
        if value < 0:
            raise ValueError(f"Radius cannot be negative: {value}")
        self._radius = value

    @radius.deleter
    def radius(self):
        """Deleter: called when you write del circle.radius"""
        print("Deleting radius!")
        del self._radius

    @property
    def area(self):
        """Computed property — no setter needed, read-only."""
        import math
        return math.pi * self._radius ** 2

    @property
    def circumference(self):
        import math
        return 2 * math.pi * self._radius


c = Circle(5)
print(c.radius)         # 5  ← calls getter
print(c.area)           # 78.53...
print(c.circumference)  # 31.41...

c.radius = 10           # calls setter
print(c.radius)         # 10

try:
    c.radius = -5       # setter raises ValueError
except ValueError as e:
    print(e)            # Radius cannot be negative: -5

del c.radius            # calls deleter

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. REAL-WORLD: USER MODEL
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

import re
import hashlib

class User:
    def __init__(self, name: str, email: str, password: str):
        self.name = name            # uses setter via @property
        self.email = email          # uses setter via @property
        self.password = password    # uses setter — stores hashed

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value: str):
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Name must be at least 2 characters")
        self._name = value.title()  # auto-capitalize

    @property
    def email(self):
        return self._email

    @email.setter
    def email(self, value: str):
        value = value.lower().strip()
        if not re.match(r"[^@]+@[^@]+\.[^@]+", value):
            raise ValueError(f"Invalid email: {value}")
        self._email = value

    @property
    def password(self):
        raise AttributeError("Password is write-only — cannot read it")

    @password.setter
    def password(self, raw: str):
        if len(raw) < 8:
            raise ValueError("Password must be at least 8 characters")
        self._password_hash = hashlib.sha256(raw.encode()).hexdigest()

    def verify_password(self, raw: str) -> bool:
        return self._password_hash == hashlib.sha256(raw.encode()).hexdigest()

    @property
    def display_name(self):
        """Computed from existing data — no storage."""
        return f"{self._name} <{self._email}>"

    def __repr__(self):
        return f"User(name={self._name!r}, email={self._email!r})"


u = User("  ashish  ", "ASHISH@GMAIL.COM", "securepass123")
print(u.name)           # Ashish (stripped + titled)
print(u.email)          # ashish@gmail.com (lowercased)
print(u.display_name)   # Ashish <ashish@gmail.com>
print(u.verify_password("securepass123"))   # True

try:
    print(u.password)   # AttributeError — write-only
except AttributeError as e:
    print(e)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. TEMPERATURE CONVERTER — Classic Example
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

class Temperature:
    """Store in Celsius internally, expose in multiple units."""

    def __init__(self, celsius: float = 0):
        self.celsius = celsius      # uses setter

    @property
    def celsius(self):
        return self._celsius

    @celsius.setter
    def celsius(self, value: float):
        if value < -273.15:
            raise ValueError(f"Temperature below absolute zero: {value}")
        self._celsius = float(value)

    @property
    def fahrenheit(self):
        return self._celsius * 9/5 + 32

    @fahrenheit.setter
    def fahrenheit(self, value: float):
        self.celsius = (value - 32) * 5/9   # convert + validate via celsius setter

    @property
    def kelvin(self):
        return self._celsius + 273.15

    @kelvin.setter
    def kelvin(self, value: float):
        self.celsius = value - 273.15

    def __repr__(self):
        return f"Temperature({self._celsius}°C / {self.fahrenheit}°F / {self.kelvin}K)"


t = Temperature(100)
print(t)                # Temperature(100.0°C / 212.0°F / 373.15K)

t.fahrenheit = 32
print(t.celsius)        # 0.0

t.kelvin = 0
print(t.celsius)        # -273.15

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. CACHED PROPERTY (Python 3.8+)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
@functools.cached_property:
  Like @property but computed only ONCE, then cached on instance.
  Use for expensive computations that don't change.
"""

import functools
import time

class DataProcessor:
    def __init__(self, data: list[int]):
        self.data = data

    @functools.cached_property
    def statistics(self):
        """Expensive computation — cached after first call."""
        time.sleep(0.1)     # simulate heavy processing
        return {
            "mean":   sum(self.data) / len(self.data),
            "min":    min(self.data),
            "max":    max(self.data),
            "count":  len(self.data),
        }

    @property
    def is_sorted(self):
        """Not cached — depends on mutable data."""
        return self.data == sorted(self.data)


processor = DataProcessor([3, 1, 4, 1, 5, 9, 2, 6])
print(processor.statistics)    # slow first time (0.1s)
print(processor.statistics)    # instant — cached in instance dict

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INTERVIEW Q&A:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q: @property vs plain attribute vs method — kab kya use karein?
A: Plain attr:  simple data, no validation, public
   @property:   need validation, computed value, or controlled access
   method:      when it DOES something (verb) → obj.calculate_tax()
                when it has parameters → obj.get_price(currency="USD")

Q: @property read-only kaise banate hain?
A: Sirf getter define karo, setter mat likhho.
   If user assigns → AttributeError: can't set attribute

Q: __slots__ ke saath @property?
A: @property works with __slots__ — just don't include the property
   name in __slots__, include the backing store (_name) instead.

Q: @cached_property vs @property with manual cache?
A: cached_property is simpler, thread-safe from Python 3.12+.
   Manual cache needed if you want cache invalidation on update.
"""
