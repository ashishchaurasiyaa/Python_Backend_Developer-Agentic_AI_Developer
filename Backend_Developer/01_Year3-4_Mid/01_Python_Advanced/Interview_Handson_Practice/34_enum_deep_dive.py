"""
================================================================================
TOPIC: Enum — IntEnum, StrEnum, Flag, auto(), _missing_, Functional API
================================================================================

KYA HOTA HAI:
    Enum (Enumeration) = named constants ka set, ek type-safe container mein.
    Ordinary constants (DRAFT = 1, PUBLISHED = 2) ke problems:
      - Type check nahi — koi bhi int pass kar sakta hai
      - str(1) = "1", not "DRAFT"
      - No iteration, no membership test, no comparison safety

    from enum import Enum, IntEnum, StrEnum, Flag, auto

KYO ZAROORI HAI:
    1. Django model: status = models.CharField(choices=PostStatus.choices)
    2. FastAPI: response mein string enum return karo (StrEnum auto-serializes)
    3. Bit flags: permission = Permission.READ | Permission.WRITE
    4. State machines: ek legal state se dusre pe transition enforce karo
    5. match/case: pattern matching ke saath enum perfectly fits

KAISE KAAM KARTA HAI (architecture):

    class Color(Enum):
        RED = 1
        GREEN = 2

    Color.RED         → <Color.RED: 1>     (the member)
    Color.RED.name    → 'RED'              (str)
    Color.RED.value   → 1                  (int)
    Color(1)          → Color.RED          (lookup by value)
    Color['RED']      → Color.RED          (lookup by name)
    list(Color)       → [Color.RED, Color.GREEN]

    Enum members are SINGLETONS — Color.RED is Color.RED always True.

KAHAN USE HOTA HAI:
    - Django: TextChoices/IntegerChoices (built on StrEnum/IntEnum)
    - FastAPI: Enum subclass → OpenAPI schema auto-generates dropdown
    - Celery: task state (PENDING, STARTED, RETRY, FAILURE, SUCCESS)
    - Database: status columns — stored as int/str, loaded as enum

INTERVIEW ANSWER (English — recite this):
    "Python's Enum module provides type-safe named constants. IntEnum members
    behave as ints so they work with DB integer columns and comparisons; StrEnum
    members behave as strings so FastAPI serializes them to JSON automatically.
    Flag enums support bitwise OR/AND for permission systems. auto() generates
    values so you don't hardcode numbers. _missing_() lets you handle unknown
    values gracefully — useful when reading legacy DB data."
================================================================================
"""

from enum import Enum, IntEnum, StrEnum, Flag, auto, unique

# ============================================================================
# SECTION 1 — BASIC Enum: Identity, Lookup, Iteration
# ============================================================================
print("=" * 65)
print("SECTION 1 — Basic Enum")
print("=" * 65)

class Color(Enum):
    RED   = 1
    GREEN = 2
    BLUE  = 3

# Member access
print(f"Color.RED         = {Color.RED}")
print(f"Color.RED.name    = {Color.RED.name}")
print(f"Color.RED.value   = {Color.RED.value}")

# Lookup by value and name
print(f"\nColor(1)          = {Color(1)}")      # By value
print(f"Color['GREEN']    = {Color['GREEN']}")  # By name

# Iteration
print(f"\nAll members: {list(Color)}")
print(f"Names:       {[c.name for c in Color]}")
print(f"Values:      {[c.value for c in Color]}")

# Comparison — identity only (==), no < > by default
print(f"\nColor.RED == Color.RED: {Color.RED == Color.RED}")   # True
print(f"Color.RED is Color.RED: {Color.RED is Color.RED}")    # True — singletons!
print(f"Color.RED == 1:         {Color.RED == 1}")            # False (not IntEnum)

# Membership test
print(f"\nColor.RED in Color:     {Color.RED in Color}")
print(f"isinstance(Color.RED, Color): {isinstance(Color.RED, Color)}")


# ============================================================================
# SECTION 2 — IntEnum: Works Like int
# ============================================================================
print("\n" + "=" * 65)
print("SECTION 2 — IntEnum — Behaves as int (DB storage, comparison)")
print("=" * 65)

class Priority(IntEnum):
    LOW    = 1
    MEDIUM = 2
    HIGH   = 3
    URGENT = 4

p = Priority.HIGH
print(f"Priority.HIGH         = {Priority.HIGH}")
print(f"Priority.HIGH == 3    = {Priority.HIGH == 3}")    # True (IntEnum)
print(f"Priority.HIGH > Priority.LOW: {Priority.HIGH > Priority.LOW}")  # True
print(f"int(Priority.HIGH)    = {int(Priority.HIGH)}")    # 3 — can use as int
print(f"Priority.HIGH + 1     = {Priority.HIGH + 1}")     # 4 — arithmetic works

# Real use: sort tasks by priority
tasks = [
    ("Write tests", Priority.MEDIUM),
    ("Deploy", Priority.URGENT),
    ("Code review", Priority.LOW),
    ("Fix bug", Priority.HIGH),
]
sorted_tasks = sorted(tasks, key=lambda t: t[1], reverse=True)
print(f"\nSorted by priority:")
for name, pri in sorted_tasks:
    print(f"  {pri.name:8} — {name}")

# Django-style: store as int in DB
db_value = int(Priority.HIGH)  # 3 — stored in DB
loaded = Priority(db_value)    # Priority.HIGH — loaded back
print(f"\nDB round-trip: stored={db_value}, loaded={loaded}")


# ============================================================================
# SECTION 3 — StrEnum: Works Like str (FastAPI/JSON serialization)
# ============================================================================
print("\n" + "=" * 65)
print("SECTION 3 — StrEnum — Behaves as str (FastAPI, JSON, Django TextChoices)")
print("=" * 65)

class PostStatus(StrEnum):
    DRAFT     = "draft"
    PUBLISHED = "published"
    ARCHIVED  = "archived"

s = PostStatus.PUBLISHED
print(f"PostStatus.PUBLISHED      = {PostStatus.PUBLISHED}")
print(f"PostStatus.PUBLISHED == 'published': {PostStatus.PUBLISHED == 'published'}")  # True
print(f"str(PostStatus.PUBLISHED) = {str(PostStatus.PUBLISHED)}")   # 'published'
print(f"f'Status: {PostStatus.DRAFT}' = f'Status: {PostStatus.DRAFT}'")  # 'Status: draft'

# FastAPI / JSON: StrEnum serializes directly without .value
import json
response = {"id": 1, "title": "Hello", "status": PostStatus.PUBLISHED}
print(f"\njson.dumps(response) = {json.dumps(response)}")  # "published" not <PostStatus...>

# Django TextChoices equivalent
class OrderStatus(StrEnum):
    PENDING   = "pending"
    CONFIRMED = "confirmed"
    SHIPPED   = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"

# choices() pattern (Django uses this internally)
choices = [(s.value, s.name.title()) for s in OrderStatus]
print(f"\nDjango choices: {choices}")

# Lookup from DB string value
db_str = "shipped"
status = OrderStatus(db_str)
print(f"OrderStatus('shipped') = {status}")


# ============================================================================
# SECTION 4 — auto(): Auto-Generated Values
# ============================================================================
print("\n" + "=" * 65)
print("SECTION 4 — auto() — No Hardcoded Values")
print("=" * 65)

class Direction(Enum):
    NORTH = auto()
    SOUTH = auto()
    EAST  = auto()
    WEST  = auto()

print(f"Direction values: {[(d.name, d.value) for d in Direction]}")
# Values: 1, 2, 3, 4 — auto-incremented

# Custom auto() for StrEnum — value = lowercased name
class AutoStrEnum(StrEnum):
    @staticmethod
    def _generate_next_value_(name, start, count, last_values):
        return name.lower()

class HttpMethod(AutoStrEnum):
    GET    = auto()
    POST   = auto()
    PUT    = auto()
    DELETE = auto()
    PATCH  = auto()

print(f"\nHttpMethod.GET    = {HttpMethod.GET!r}")     # 'get'
print(f"HttpMethod.POST   = {HttpMethod.POST!r}")     # 'post'
print(f"HttpMethod.DELETE = {HttpMethod.DELETE!r}")   # 'delete'
print(f"'get' == HttpMethod.GET: {'get' == HttpMethod.GET}")  # True (StrEnum)


# ============================================================================
# SECTION 5 — Flag: Bitwise Permissions
# ============================================================================
print("\n" + "=" * 65)
print("SECTION 5 — Flag — Bitwise Permissions (READ | WRITE | EXECUTE)")
print("=" * 65)

class Permission(Flag):
    NONE    = 0
    READ    = auto()  # 1
    WRITE   = auto()  # 2
    EXECUTE = auto()  # 4
    DELETE  = auto()  # 8

    # Composite aliases
    READ_WRITE = READ | WRITE
    ADMIN      = READ | WRITE | EXECUTE | DELETE

# Combine with |
user_perms = Permission.READ | Permission.WRITE
print(f"user_perms = {user_perms}")
print(f"user_perms.value = {user_perms.value}")   # 3 (1 | 2)

# Check with 'in'
print(f"\nPermission.READ in user_perms:    {Permission.READ in user_perms}")     # True
print(f"Permission.EXECUTE in user_perms: {Permission.EXECUTE in user_perms}")   # False
print(f"Permission.DELETE in user_perms:  {Permission.DELETE in user_perms}")    # False

# Remove permission with & ~
user_perms &= ~Permission.WRITE
print(f"\nAfter removing WRITE: {user_perms}")  # Only READ left

# Admin check pattern
def can_delete(user_permission: Permission) -> bool:
    return Permission.DELETE in user_permission

admin_perms = Permission.ADMIN
guest_perms = Permission.READ

print(f"\nAdmin can delete: {can_delete(admin_perms)}")  # True
print(f"Guest can delete: {can_delete(guest_perms)}")   # False

# Store as int in DB (Flag uses .value — no int() inheritance unlike IntFlag)
db_val = Permission.READ_WRITE.value  # 3
loaded = Permission(db_val)           # Permission.READ|WRITE
print(f"\nDB round-trip: stored={db_val}, loaded={loaded}")


# ============================================================================
# SECTION 6 — _missing_: Handle Unknown Values Gracefully
# ============================================================================
print("\n" + "=" * 65)
print("SECTION 6 — _missing_() — Handle Legacy / Unknown DB Values")
print("=" * 65)

class LegacyStatus(IntEnum):
    ACTIVE    = 1
    INACTIVE  = 2
    SUSPENDED = 3
    UNKNOWN   = -1  # Fallback for unrecognized values

    @classmethod
    def _missing_(cls, value):
        # Called when value not found — return UNKNOWN instead of raising ValueError
        print(f"  [_missing_] Unknown status value: {value!r} → returning UNKNOWN")
        return cls.UNKNOWN

# Normal lookup
print(f"LegacyStatus(1) = {LegacyStatus(1)}")
print(f"LegacyStatus(3) = {LegacyStatus(3)}")

# Unknown value from legacy DB — graceful fallback
print(f"LegacyStatus(99) = {LegacyStatus(99)}")   # Calls _missing_
print(f"LegacyStatus(0)  = {LegacyStatus(0)}")    # Calls _missing_


# ============================================================================
# SECTION 7 — Functional API + @unique + Aliases
# ============================================================================
print("\n" + "=" * 65)
print("SECTION 7 — Functional API, @unique, Aliases")
print("=" * 65)

# Functional API — create enum from sequence (useful for config-driven enums)
Environment = Enum("Environment", ["DEVELOPMENT", "STAGING", "PRODUCTION"])
print(f"Functional API: {list(Environment)}")
print(f"Environment.PRODUCTION.value = {Environment.PRODUCTION.value}")

# Functional API from dict (custom values)
TaskState = Enum("TaskState", {
    "PENDING":  "pending",
    "RUNNING":  "running",
    "SUCCESS":  "success",
    "FAILURE":  "failure",
    "REVOKED":  "revoked",
})
print(f"\nCelery-style states: {[(s.name, s.value) for s in TaskState]}")

# @unique — prevent accidental duplicate values
try:
    @unique
    class BadEnum(Enum):
        A = 1
        B = 2
        C = 1  # Duplicate of A!
except ValueError as e:
    print(f"\n@unique prevents duplicates: {e}")

# Aliases (without @unique): same value = alias, not new member
class Shade(Enum):
    RED    = 1
    ROUGE  = 1  # Alias for RED (same value)
    GREEN  = 2

print(f"\nShade.ROUGE is Shade.RED: {Shade.ROUGE is Shade.RED}")  # True — alias!
print(f"List(Shade): {list(Shade)}")  # Only RED, GREEN (aliases excluded)


# ============================================================================
# BREAK-IT — Common Enum Mistakes
# ============================================================================
print("\n" + "=" * 65)
print("BREAK-IT — Common Enum Mistakes")
print("=" * 65)

# BUG 1: Comparing Enum to raw value (non-IntEnum)
class Status(Enum):
    ACTIVE = 1

val = 1
print(f"Bug 1 — Status.ACTIVE == 1: {Status.ACTIVE == 1}")  # False (not IntEnum!)
print(f"  Fix: Status.ACTIVE.value == 1: {Status.ACTIVE.value == 1}")
print(f"  Or:  Use IntEnum if you need int comparison")

# BUG 2: Trying to set enum member value
try:
    Status.ACTIVE = 99
except AttributeError as e:
    print(f"\nBug 2 — Enum members are immutable: {e}")

# BUG 3: Wrong lookup direction
class Code(Enum):
    OK    = 200
    NOT_FOUND = 404

try:
    Code["200"]   # KeyError — name lookup, not value
except KeyError as e:
    print(f"\nBug 3 — Code['200'] → KeyError: {e}")
    print(f"  Fix: Code(200) → value lookup: {Code(200)}")

# BUG 4: Forgetting StrEnum for JSON serialization
class BadStatus(Enum):
    ACTIVE = "active"

try:
    result = json.dumps({"status": BadStatus.ACTIVE})
except TypeError as e:
    print(f"\nBug 4 — Plain Enum not JSON serializable: {e}")
    print(f"  Fix: Use StrEnum or add .value in serializer")


# ============================================================================
# TODO — FastAPI + Django status endpoint
# ============================================================================
"""
Ek order management system hai:

Implement:
  1. OrderStatus(StrEnum) — pending, confirmed, processing, shipped, delivered, cancelled
  2. PaymentMethod(StrEnum) — cod, upi, card, netbanking
  3. OrderPriority(IntEnum) — NORMAL=1, EXPRESS=2, SAME_DAY=3

  4. valid_transitions: dict jo define kare ki kaunse status se kaunse status pe
     jaaya ja sakta hai:
       pending → {confirmed, cancelled}
       confirmed → {processing, cancelled}
       processing → {shipped}
       shipped → {delivered}
       cancelled → {}
       delivered → {}

  5. transition(current: OrderStatus, new: OrderStatus) → OrderStatus:
       Valid transition → new status return karo
       Invalid transition → ValueError raise karo with clear message

Verify:
  - transition(PENDING, CONFIRMED) → CONFIRMED
  - transition(PENDING, SHIPPED)   → ValueError "Cannot go from pending to shipped"
  - transition(DELIVERED, PENDING) → ValueError
  - JSON serialize: json.dumps({"status": OrderStatus.PENDING}) → '{"status": "pending"}'
"""

if __name__ == "__main__":
    print("\n" + "=" * 65)
    print("RUN: python 34_enum_deep_dive.py")
    print("Sab sections automatically run hote hain above.")
    print("TODO: Implement OrderStatus state machine at the bottom.")
    print("=" * 65)
