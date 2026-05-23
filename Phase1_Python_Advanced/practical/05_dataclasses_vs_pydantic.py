"""
PHASE 1 ADVANCED — 05: Dataclasses vs Pydantic
Architecture Level: Senior Python Backend + Agentic AI

THE RULE:
  dataclass → internal DTOs, domain objects, no external input
  Pydantic  → API boundaries, external data, user input, LLM output parsing

WHY THIS MATTERS IN INTERVIEWS:
  "When do you use dataclass vs Pydantic?" is a standard senior-level question.
  Wrong answer: "I always use Pydantic" or "I always use dataclass"
  Right answer: understand their purpose and choose by context.
"""

from __future__ import annotations

import dataclasses
import json
import time
from typing import Annotated, Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ═══════════════════════════════════════════════════════
# PART A: Core Difference — Validation Philosophy
# ═══════════════════════════════════════════════════════

# ─────────────────────────────────────────────
# 1. Dataclass — NO validation, just structure
# ─────────────────────────────────────────────

@dataclasses.dataclass
class UserDTO:
    id: int
    name: str
    email: str
    age: int = 0


# Dataclass trusts you — no type checking at runtime
u1 = UserDTO(id="not-an-int", name=123, email=None)  # type: ignore
print(f"Dataclass accepts wrong types: id={u1.id!r}, name={u1.name!r}")
# Output: id='not-an-int', name=123  — no error!


# ─────────────────────────────────────────────
# 2. Pydantic — validates and coerces on construction
# ─────────────────────────────────────────────

class UserModel(BaseModel):
    id: int
    name: str
    email: str
    age: int = 0


try:
    # Pydantic coerces "42" → 42 (int)
    u2 = UserModel(id="42", name="Alice", email="alice@example.com")
    print(f"\nPydantic coerced id: {u2.id!r} (type: {type(u2.id).__name__})")
except Exception as e:
    print(f"Pydantic error: {e}")

try:
    # Pydantic raises on truly invalid data
    u3 = UserModel(id="not-an-int", name="Bob", email="bob@example.com")
except Exception as e:
    print(f"Pydantic catches invalid: {type(e).__name__}")


# ═══════════════════════════════════════════════════════
# PART B: frozen=True vs Pydantic frozen model
# ═══════════════════════════════════════════════════════

# ─────────────────────────────────────────────
# 1. frozen dataclass — immutable, hashable
# ─────────────────────────────────────────────

@dataclasses.dataclass(frozen=True)
class Point:
    x: float
    y: float

    def distance_to(self, other: Point) -> float:
        return ((self.x - other.x)**2 + (self.y - other.y)**2) ** 0.5


p1 = Point(1.0, 2.0)
p2 = Point(4.0, 6.0)

# Hashable — can use in sets/dict keys
points_visited: set[Point] = {p1, p2}
print(f"\nfrozen dataclass distance: {p1.distance_to(p2):.2f}")

try:
    p1.x = 99.0  # type: ignore
except dataclasses.FrozenInstanceError as e:
    print(f"frozen dataclass immutable: {e}")


# ─────────────────────────────────────────────
# 2. Pydantic frozen model — immutable with validation
# ─────────────────────────────────────────────

class FrozenPoint(BaseModel):
    model_config = ConfigDict(frozen=True)
    x: float
    y: float

fp = FrozenPoint(x=1.0, y=2.0)
try:
    fp.x = 99.0  # type: ignore
except Exception as e:
    print(f"Pydantic frozen immutable: {type(e).__name__}")

# Pydantic frozen models are also hashable
frozen_set: set[FrozenPoint] = {fp, FrozenPoint(x=3.0, y=4.0)}
print(f"Pydantic frozen hashable: {len(frozen_set)} items")


# ═══════════════════════════════════════════════════════
# PART C: __post_init__ vs Pydantic Validators
# ═══════════════════════════════════════════════════════

# ─────────────────────────────────────────────
# 1. Dataclass __post_init__ — run logic after init
# ─────────────────────────────────────────────

@dataclasses.dataclass
class DateRange:
    start: str   # "YYYY-MM-DD"
    end: str
    days: int = dataclasses.field(init=False)  # computed, not passed in

    def __post_init__(self):
        from datetime import date
        s = date.fromisoformat(self.start)
        e = date.fromisoformat(self.end)
        if e <= s:
            raise ValueError(f"end must be after start")
        self.days = (e - s).days


dr = DateRange("2024-01-01", "2024-01-15")
print(f"\nDateRange days: {dr.days}")

try:
    DateRange("2024-01-15", "2024-01-01")
except ValueError as e:
    print(f"DateRange validation: {e}")


# ─────────────────────────────────────────────
# 2. Pydantic field_validator — with type coercion
# ─────────────────────────────────────────────

class OrderRequest(BaseModel):
    product_id: str
    quantity: int
    price: float
    discount: float = 0.0

    @field_validator("quantity")
    @classmethod
    def qty_must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("quantity must be > 0")
        return v

    @field_validator("discount")
    @classmethod
    def discount_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("discount must be between 0.0 and 1.0")
        return v

    @model_validator(mode="after")
    def final_price_check(self) -> OrderRequest:
        final = self.price * self.quantity * (1 - self.discount)
        if final > 10_000:
            raise ValueError(f"Order total {final:.2f} exceeds limit 10,000")
        return self


order = OrderRequest(product_id="SKU-001", quantity=5, price=100.0, discount=0.1)
print(f"\nOrder total: {order.price * order.quantity * (1 - order.discount):.2f}")

try:
    OrderRequest(product_id="SKU-002", quantity=-1, price=50.0)
except Exception as e:
    print(f"Pydantic validator caught: {e.errors()[0]['msg']}")


# ═══════════════════════════════════════════════════════
# PART D: Performance Comparison
# ═══════════════════════════════════════════════════════

N = 100_000

@dataclasses.dataclass
class FastItem:
    id: int
    name: str
    value: float

class PydanticItem(BaseModel):
    id: int
    name: str
    value: float


start = time.perf_counter()
for i in range(N):
    FastItem(id=i, name=f"item_{i}", value=float(i))
dc_time = time.perf_counter() - start

start = time.perf_counter()
for i in range(N):
    PydanticItem(id=i, name=f"item_{i}", value=float(i))
pd_time = time.perf_counter() - start

print(f"\nPerformance ({N:,} objects):")
print(f"  dataclass:  {dc_time*1000:.1f}ms")
print(f"  pydantic:   {pd_time*1000:.1f}ms")
print(f"  ratio:      Pydantic is ~{pd_time/dc_time:.1f}x slower (validation overhead)")
# Typical: Pydantic is 3-8x slower — acceptable at API boundaries, avoid in hot loops


# ═══════════════════════════════════════════════════════
# PART E: When to Use Which — Decision Framework
# ═══════════════════════════════════════════════════════

# ─────────────────────────────────────────────
# USE DATACLASS when:
# ─────────────────────────────────────────────

# 1. Internal domain objects — trust your own code
@dataclasses.dataclass
class AgentState:
    """State passed between agent nodes — internal, no external input."""
    messages: list[dict]
    iteration: int = 0
    tool_results: list[Any] = dataclasses.field(default_factory=list)
    is_complete: bool = False

# 2. Value objects — immutable, semantic equality
@dataclasses.dataclass(frozen=True)
class Money:
    amount: float
    currency: str = "USD"

# 3. Simple data containers with computed fields
@dataclasses.dataclass
class BoundingBox:
    x1: float
    y1: float
    x2: float
    y2: float
    area: float = dataclasses.field(init=False)

    def __post_init__(self):
        self.area = (self.x2 - self.x1) * (self.y2 - self.y1)


# ─────────────────────────────────────────────
# USE PYDANTIC when:
# ─────────────────────────────────────────────

# 1. FastAPI request/response models — external input from users/clients
class CreateUserRequest(BaseModel):
    name: str = Field(min_length=2, max_length=50)
    email: str = Field(pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$')
    age: Optional[int] = Field(None, ge=0, le=150)

# 2. Parsing LLM structured output (Instructor library)
class ExtractedTask(BaseModel):
    """Pydantic model for structured LLM output."""
    title: str = Field(description="Short task title")
    priority: Annotated[int, Field(ge=1, le=5)] = 3
    assignee: Optional[str] = None
    tags: list[str] = Field(default_factory=list)

# 3. Config files / environment variables
class AppConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    database_url: str
    redis_url: str = "redis://localhost:6379"
    max_connections: int = Field(default=10, ge=1, le=100)
    debug: bool = False

# 4. Serialization — .model_dump() and .model_validate()
sample_user = CreateUserRequest(name="Alice", email="alice@example.com", age=30)
user_dict = sample_user.model_dump()
user_json = sample_user.model_dump_json()
restored  = CreateUserRequest.model_validate(user_dict)
print(f"\nPydantic serialization: {user_json}")


# ═══════════════════════════════════════════════════════
# PART F: Practical Patterns in a Backend Service
# ═══════════════════════════════════════════════════════

# ─────────────────────────────────────────────
# Layered approach: Pydantic at boundary, dataclass internally
# ─────────────────────────────────────────────

# API layer — Pydantic validates external input
class CreateOrderRequest(BaseModel):
    product_id: str = Field(min_length=1)
    quantity: int = Field(ge=1)
    user_id: str


# Domain layer — dataclass for business logic
@dataclasses.dataclass
class Order:
    """Internal domain object. Created from validated request."""
    id: str
    product_id: str
    quantity: int
    user_id: str
    status: str = "pending"
    total_price: float = 0.0

    def confirm(self, unit_price: float) -> None:
        self.total_price = unit_price * self.quantity
        self.status = "confirmed"


# Mapping function — boundary to domain
def create_order_from_request(req: CreateOrderRequest, order_id: str) -> Order:
    return Order(
        id=order_id,
        product_id=req.product_id,
        quantity=req.quantity,
        user_id=req.user_id,
    )


req = CreateOrderRequest(product_id="SKU-001", quantity=3, user_id="user-42")
order = create_order_from_request(req, order_id="ord-001")
order.confirm(unit_price=25.0)
print(f"\nOrder: {order.id}, total={order.total_price:.2f}, status={order.status}")


# ═══════════════════════════════════════════════════════
# PART G: Interview Questions
# ═══════════════════════════════════════════════════════

"""
Q1: What is the main difference between dataclass and Pydantic?
    dataclass: structure only, no runtime type validation, faster
    Pydantic: validates + coerces types on creation, slower, use at API/data boundaries

Q2: When would you choose dataclass over Pydantic?
    Internal domain objects, LangGraph agent state, hot loops, value objects,
    computed fields (__post_init__), immutable records (frozen=True)

Q3: When would you choose Pydantic over dataclass?
    FastAPI request/response models, config from env vars, parsing external JSON,
    parsing LLM structured output (with Instructor), any untrusted external input

Q4: Are Pydantic models immutable?
    Not by default. Use model_config = ConfigDict(frozen=True) to make them
    immutable AND hashable.

Q5: What is field(default_factory=list) in dataclasses?
    Prevents the mutable default argument bug. Never use field(default=[]) —
    the list is shared across instances. default_factory creates a new list
    for each instance.

Q6: How do you validate related fields in Pydantic?
    Use @model_validator(mode="after") — runs after all fields are set,
    so you can check cross-field constraints.

Q7: Can you use both in the same project?
    Yes — this is the recommended pattern. Pydantic at the API/config boundary,
    dataclasses for internal domain logic.
"""
