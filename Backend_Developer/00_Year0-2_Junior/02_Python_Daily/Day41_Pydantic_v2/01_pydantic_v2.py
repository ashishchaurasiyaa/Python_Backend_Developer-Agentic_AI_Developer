"""
=============================================================================
DAY 47 — PYDANTIC v2 DEEP DIVE
=============================================================================
Topics:
  1.  Basics v2               — BaseModel, ConfigDict, from_attributes
  2.  Field                   — default, description, gt/lt, pattern, aliases
  3.  Validators              — @field_validator, @model_validator, modes
  4.  Computed Fields         — @computed_field, @property
  5.  Types                   — Annotated, constr/conint, EmailStr, SecretStr
  6.  Nested Models           — model_validate, model_dump, model_dump_json
  7.  Serialization           — field_serializer, model_serializer, excludes
  8.  Generic Models          — Generic[T] with BaseModel
  9.  Discriminated Unions    — Literal + Annotated polymorphic models
  10. Settings                — BaseSettings, env_file, env_prefix, nested
  11. Performance             — Rust core, benchmark notes
  12. Migration               — v1 → v2 key changes cheatsheet
  13. Interview Q&A           — 15 questions
=============================================================================
Install:
    pip install "pydantic[email]>=2.0" pydantic-settings
=============================================================================
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1 — BASICS v2
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("SECTION 1 — BASICS v2")
print("=" * 60)

from pydantic import BaseModel, ConfigDict


# ConfigDict replaces the inner `class Config:` from v1
class UserBasic(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,   # auto-strip strings
        str_to_lower=False,          # don't lowercase
        frozen=False,                # mutable (set True for hashable)
        populate_by_name=True,       # accept both alias and field name
        from_attributes=True,        # replaces orm_mode=True (v1)
        validate_default=True,       # validate default values too
        extra="forbid",              # reject extra fields
    )

    id: int
    name: str
    email: str
    is_active: bool = True


u = UserBasic(id=1, name="  Alice  ", email="alice@example.com")
print(u)
print("name auto-stripped:", repr(u.name))   # "Alice" — no spaces
print("model_fields:", list(UserBasic.model_fields.keys()))

# from_attributes — reading from ORM-like objects
class FakeORMUser:
    def __init__(self):
        self.id = 99
        self.name = "Bob"
        self.email = "bob@example.com"
        self.is_active = False

orm_obj = FakeORMUser()
user_from_orm = UserBasic.model_validate(orm_obj)  # v2 replaces .from_orm()
print("from_attributes:", user_from_orm)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2 — FIELD
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("SECTION 2 — FIELD")
print("=" * 60)

from pydantic import BaseModel, Field
from typing import Optional


class Product(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    # Basic defaults
    id: int = Field(..., description="Primary key — required (... means no default)")
    name: str = Field(..., min_length=2, max_length=100, description="Product name")

    # Numeric constraints
    price: float = Field(..., gt=0, lt=1_000_000, description="Price must be > 0")
    stock: int = Field(default=0, ge=0, le=10_000)

    # String pattern
    sku: str = Field(
        ...,
        pattern=r"^[A-Z]{3}-\d{4}$",
        description="Format: ABC-1234",
    )

    # Alias: the JSON key differs from the Python attribute name
    # alias          — used for both input and output
    # validation_alias — input only  (what Pydantic reads from)
    # serialization_alias — output only (what .model_dump() produces)
    category_id: int = Field(..., alias="categoryId")
    internal_code: str = Field(
        ...,
        validation_alias="internalCode",
        serialization_alias="internal_code_export",
    )

    tags: list[str] = Field(default_factory=list)
    discount: Optional[float] = Field(None, ge=0.0, le=1.0)


p = Product(
    id=1,
    name="Widget",
    price=29.99,
    stock=100,
    sku="WDG-0001",
    categoryId=5,        # using alias
    internalCode="IC-X", # using validation_alias
)
print(p)
print("dump (field names):", p.model_dump())
print("dump (by alias):", p.model_dump(by_alias=True))


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3 — VALIDATORS
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("SECTION 3 — VALIDATORS")
print("=" * 60)

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Any


class SignupForm(BaseModel):
    username: str
    password: str
    confirm_password: str
    age: int

    # --- @field_validator ---
    # mode='before': runs BEFORE Pydantic's own type coercion
    @field_validator("username", mode="before")
    @classmethod
    def strip_username(cls, v: Any) -> str:
        """Strip whitespace before type validation."""
        if isinstance(v, str):
            return v.strip()
        return v

    # mode='after': runs AFTER type coercion — v is already the final type
    @field_validator("username", mode="after")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not v.isalnum():
            raise ValueError("username must be alphanumeric")
        return v.lower()

    @field_validator("age", mode="after")
    @classmethod
    def validate_age(cls, v: int) -> int:
        if v < 13:
            raise ValueError("must be at least 13 years old")
        return v

    # mode='wrap': you control calling the next validator in the chain
    @field_validator("password", mode="wrap")
    @classmethod
    def validate_password(cls, v: Any, handler) -> str:
        result = handler(v)   # call next validator
        if len(result) < 8:
            raise ValueError("password must be at least 8 characters")
        if not any(c.isupper() for c in result):
            raise ValueError("password must contain an uppercase letter")
        return result

    # --- @model_validator ---
    # mode='before': receives raw input dict — before ANY field validation
    @model_validator(mode="before")
    @classmethod
    def pre_process(cls, data: Any) -> Any:
        """Normalize keys to lowercase before any field processing."""
        if isinstance(data, dict):
            return {k.lower(): v for k, v in data.items()}
        return data

    # mode='after': instance is fully validated — access self.field
    @model_validator(mode="after")
    def check_passwords_match(self) -> "SignupForm":
        if self.password != self.confirm_password:
            raise ValueError("passwords do not match")
        return self


try:
    form = SignupForm(
        Username="  Alice123  ",   # note: uppercase key, extra spaces
        password="Secret1234",
        confirm_password="Secret1234",
        age=25,
    )
    print("Valid signup:", form)
except Exception as e:
    print("Validation error:", e)

try:
    bad = SignupForm(
        username="alice",
        password="weak",
        confirm_password="weak",
        age=25,
    )
except Exception as e:
    print("Expected error (weak password):", e)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4 — COMPUTED FIELDS
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("SECTION 4 — COMPUTED FIELDS")
print("=" * 60)

from pydantic import BaseModel, computed_field


class Rectangle(BaseModel):
    width: float
    height: float

    # @computed_field — included in model_dump() and model_dump_json()
    @computed_field
    @property
    def area(self) -> float:
        return self.width * self.height

    @computed_field
    @property
    def perimeter(self) -> float:
        return 2 * (self.width + self.height)

    @computed_field(alias="diagonal_length", repr=True)
    @property
    def diagonal(self) -> float:
        return (self.width ** 2 + self.height ** 2) ** 0.5


r = Rectangle(width=3.0, height=4.0)
print("Rectangle:", r)
print("area:", r.area)
print("dump:", r.model_dump())
print("dump (by_alias):", r.model_dump(by_alias=True))


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5 — TYPES
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("SECTION 5 — SPECIAL TYPES")
print("=" * 60)

from typing import Annotated
from pydantic import (
    BaseModel,
    EmailStr,
    AnyHttpUrl,
    SecretStr,
    Json,
    constr,
    conint,
    confloat,
    Field,
)

# Annotated[] — attach metadata / constraints to any type
PositiveInt = Annotated[int, Field(gt=0)]
Username = Annotated[str, Field(min_length=3, max_length=50, pattern=r"^\w+$")]
Percentage = Annotated[float, Field(ge=0.0, le=100.0)]

# constr / conint / confloat — shorthand constraint factories (still valid in v2)
StrictName = constr(strip_whitespace=True, min_length=1, max_length=100)
SmallInt = conint(ge=0, le=255)
BoundedFloat = confloat(ge=0.0, le=1.0)


class UserProfile(BaseModel):
    user_id: PositiveInt
    username: Username
    email: EmailStr               # validates email format (requires email-validator)
    website: AnyHttpUrl           # validates URL including scheme
    password: SecretStr           # won't appear in repr/logs
    score: Percentage
    metadata: Json[dict]          # parses a JSON string into dict
    age: SmallInt
    level: BoundedFloat


profile = UserProfile(
    user_id=1,
    username="alice_dev",
    email="alice@example.com",
    website="https://alice.dev",
    password="supersecret",
    score=95.5,
    metadata='{"theme": "dark", "lang": "en"}',  # JSON string → dict
    age=28,
    level=0.75,
)
print("UserProfile repr (password hidden):", profile)
print("password get_secret_value():", profile.password.get_secret_value())
print("metadata parsed:", profile.metadata)
print("website type:", type(profile.website))


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6 — NESTED MODELS
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("SECTION 6 — NESTED MODELS")
print("=" * 60)

from pydantic import BaseModel
from typing import Optional


class Address(BaseModel):
    street: str
    city: str
    country: str = "India"
    pincode: str


class Company(BaseModel):
    name: str
    address: Address


class Employee(BaseModel):
    id: int
    name: str
    company: Company
    skills: list[str] = []
    manager: Optional["Employee"] = None  # self-referential


Employee.model_rebuild()  # needed for self-referential models

raw_data = {
    "id": 1,
    "name": "Alice",
    "company": {
        "name": "TechCorp",
        "address": {
            "street": "123 MG Road",
            "city": "Bangalore",
            "pincode": "560001",
        },
    },
    "skills": ["Python", "FastAPI", "Docker"],
}

emp = Employee.model_validate(raw_data)   # v2 replaces .parse_obj()
print("Employee:", emp)
print("\nmodel_dump():", emp.model_dump())
print("\nmodel_dump_json():", emp.model_dump_json(indent=2))

# model_copy — shallow copy with overrides
emp2 = emp.model_copy(update={"name": "Bob"})
print("\nCopied employee:", emp2.name)

# model_validate_json — parse directly from JSON string
import json
json_str = json.dumps(raw_data)
emp3 = Employee.model_validate_json(json_str)
print("From JSON string:", emp3.id, emp3.name)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7 — SERIALIZATION
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("SECTION 7 — SERIALIZATION")
print("=" * 60)

from pydantic import BaseModel, field_serializer, model_serializer
from datetime import datetime
from decimal import Decimal
from typing import Any


class OrderItem(BaseModel):
    product: str
    quantity: int
    unit_price: Decimal
    created_at: datetime | None = None

    def model_post_init(self, __context: Any) -> None:
        if self.created_at is None:
            object.__setattr__(self, "created_at", datetime.now())

    # field_serializer — controls how a single field is serialized
    @field_serializer("unit_price")
    def serialize_price(self, v: Decimal) -> float:
        return float(v)

    @field_serializer("created_at")
    def serialize_datetime(self, v: datetime) -> str:
        return v.strftime("%Y-%m-%dT%H:%M:%S")


item = OrderItem(product="Widget", quantity=3, unit_price=Decimal("29.99"))
print("dump:", item.model_dump())
print("dump_json:", item.model_dump_json())


class ReportModel(BaseModel):
    title: str
    author: str
    content: str
    internal_notes: str = ""
    draft: bool = True

    # model_serializer — fully control the entire output dict
    @model_serializer(mode="plain")
    def custom_serialize(self) -> dict:
        return {
            "report_title": self.title,
            "written_by": self.author,
            "body": self.content,
            # internal_notes and draft are excluded
        }


report = ReportModel(
    title="Q1 Report",
    author="Alice",
    content="Revenue grew 20%",
    internal_notes="confidential",
)
print("\nCustom serialized report:", report.model_dump())

# exclude_none, exclude_unset
class SparseModel(BaseModel):
    a: int
    b: Optional[str] = None
    c: Optional[float] = None


s = SparseModel(a=1)
print("\nAll fields:", s.model_dump())
print("exclude_none:", s.model_dump(exclude_none=True))
print("exclude_unset:", s.model_dump(exclude_unset=True))


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8 — GENERIC MODELS
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("SECTION 8 — GENERIC MODELS")
print("=" * 60)

from typing import Generic, TypeVar, Optional
from pydantic import BaseModel

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """Generic API response wrapper."""
    success: bool
    message: str
    data: Optional[T] = None
    errors: list[str] = []


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    has_next: bool

    @property
    def total_pages(self) -> int:
        return (self.total + self.page_size - 1) // self.page_size


class UserSummary(BaseModel):
    id: int
    name: str


# Concrete instantiations
ok_response = APIResponse[UserSummary](
    success=True,
    message="User fetched",
    data=UserSummary(id=1, name="Alice"),
)
print("Generic response:", ok_response)
print("Data type:", type(ok_response.data))

paginated = PaginatedResponse[UserSummary](
    items=[UserSummary(id=1, name="Alice"), UserSummary(id=2, name="Bob")],
    total=50,
    page=1,
    page_size=2,
    has_next=True,
)
print("Paginated:", paginated)
print("Total pages:", paginated.total_pages)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 9 — DISCRIMINATED UNIONS
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("SECTION 9 — DISCRIMINATED UNIONS")
print("=" * 60)

from typing import Literal, Annotated, Union
from pydantic import BaseModel, Field


class CatPayload(BaseModel):
    animal_type: Literal["cat"]
    name: str
    indoor: bool = True


class DogPayload(BaseModel):
    animal_type: Literal["dog"]
    name: str
    breed: str


class BirdPayload(BaseModel):
    animal_type: Literal["bird"]
    name: str
    can_fly: bool = True


# Discriminated union — Pydantic uses the 'animal_type' field
# to pick the correct model WITHOUT trying all of them
Animal = Annotated[
    Union[CatPayload, DogPayload, BirdPayload],
    Field(discriminator="animal_type"),
]


class AnimalRequest(BaseModel):
    animal: Animal
    owner: str


req1 = AnimalRequest(
    animal={"animal_type": "dog", "name": "Rex", "breed": "Labrador"},
    owner="Bob",
)
req2 = AnimalRequest(
    animal={"animal_type": "cat", "name": "Whiskers"},
    owner="Alice",
)
print("Dog request:", req1)
print("Cat request:", req2)
print("Type of animal:", type(req1.animal).__name__)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 10 — SETTINGS (pydantic-settings)
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("SECTION 10 — SETTINGS")
print("=" * 60)

# pip install pydantic-settings
try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
    from pydantic import Field, SecretStr

    class DatabaseSettings(BaseSettings):
        host: str = "localhost"
        port: int = 5432
        name: str = "mydb"
        user: str = "postgres"
        password: SecretStr = "secret"

    class RedisSettings(BaseSettings):
        host: str = "localhost"
        port: int = 6379
        db: int = 0

    class AppSettings(BaseSettings):
        """
        Reads from environment variables and .env file.
        Variables prefixed with APP_ in environment.
        Nested settings use double underscore as separator:
            APP_DATABASE__HOST=db.prod.local
            APP_REDIS__PORT=6380
        """
        model_config = SettingsConfigDict(
            env_file=".env",            # load from .env file
            env_file_encoding="utf-8",
            env_prefix="APP_",          # all env vars start with APP_
            env_nested_delimiter="__",  # APP_DATABASE__HOST → database.host
            case_sensitive=False,
            extra="ignore",
        )

        app_name: str = Field("MyApp", description="Application name")
        debug: bool = False
        secret_key: SecretStr = "changeme"
        database: DatabaseSettings = DatabaseSettings()
        redis: RedisSettings = RedisSettings()
        allowed_hosts: list[str] = ["localhost", "127.0.0.1"]
        max_workers: int = Field(4, ge=1, le=32)

    # In real usage, these come from environment or .env file
    # Here we demo instantiation with defaults
    settings = AppSettings()
    print("App name:", settings.app_name)
    print("Debug:", settings.debug)
    print("DB host:", settings.database.host)
    print("DB port:", settings.database.port)
    print("Redis port:", settings.redis.port)
    print("Allowed hosts:", settings.allowed_hosts)

    # Demonstrate env override via dict (simulating env vars)
    import os
    os.environ["APP_DEBUG"] = "true"
    os.environ["APP_MAX_WORKERS"] = "8"
    settings2 = AppSettings()
    print("\nWith env overrides — debug:", settings2.debug, "workers:", settings2.max_workers)

except ImportError:
    print("pydantic-settings not installed. Run: pip install pydantic-settings")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 11 — PERFORMANCE
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("SECTION 11 — PERFORMANCE NOTES")
print("=" * 60)

PERFORMANCE_NOTES = """
Pydantic v2 is rewritten in Rust (pydantic-core):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Benchmark (approximate, varies by model complexity):
  Validation:    v2 is ~5-50x faster than v1
  Serialization: v2 is ~2-10x faster than v1
  Import time:   v2 is slightly faster (less Python overhead)

Key Performance Tips:
  1. Use model_validate() with from_attributes=True over manual dict construction
  2. Prefer Annotated[] types — they compile once at class definition time
  3. Use model_dump(mode='json') instead of json.loads(model.model_dump_json())
  4. For hot paths: use TypeAdapter instead of a full BaseModel for scalar types
  5. frozen=True models are hashable and can be used as dict keys / set members
  6. Avoid @model_validator(mode='before') when @field_validator suffices
     (model-level validators run for every instantiation)

TypeAdapter — ultra-fast validation without a full model:
"""
print(PERFORMANCE_NOTES)

from pydantic import TypeAdapter

int_list_adapter = TypeAdapter(list[int])
result = int_list_adapter.validate_python(["1", "2", "3"])  # coerces strs
print("TypeAdapter result:", result)

email_adapter = TypeAdapter(EmailStr)
try:
    valid_email = email_adapter.validate_python("user@example.com")
    print("Valid email:", valid_email)
except Exception as e:
    print("Email error:", e)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 12 — MIGRATION v1 → v2
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("SECTION 12 — MIGRATION v1 → v2 CHEATSHEET")
print("=" * 60)

MIGRATION_CHEATSHEET = """
┌─────────────────────────────────────┬─────────────────────────────────────────┐
│ Pydantic v1                         │ Pydantic v2                             │
├─────────────────────────────────────┼─────────────────────────────────────────┤
│ class Config:                       │ model_config = ConfigDict(...)          │
│     orm_mode = True                 │     from_attributes=True                │
│     allow_population_by_field_name  │     populate_by_name=True               │
│     underscore_attrs_are_private    │     (use PrivateAttr() instead)         │
├─────────────────────────────────────┼─────────────────────────────────────────┤
│ @validator("field")                 │ @field_validator("field", mode="after") │
│ @validator("field", pre=True)       │ @field_validator("field", mode="before")│
│ @root_validator(pre=True)           │ @model_validator(mode="before")         │
│ @root_validator(pre=False)          │ @model_validator(mode="after")          │
├─────────────────────────────────────┼─────────────────────────────────────────┤
│ Model.parse_obj(data)               │ Model.model_validate(data)              │
│ Model.parse_raw(json_str)           │ Model.model_validate_json(json_str)     │
│ Model.from_orm(obj)                 │ Model.model_validate(obj)               │
│ model.dict()                        │ model.model_dump()                      │
│ model.json()                        │ model.model_dump_json()                 │
│ model.copy(update=...)              │ model.model_copy(update=...)            │
│ Model.schema()                      │ Model.model_json_schema()               │
│ Model.__fields__                    │ Model.model_fields                      │
├─────────────────────────────────────┼─────────────────────────────────────────┤
│ from pydantic import BaseSettings   │ from pydantic_settings import           │
│                                     │     BaseSettings (separate package)     │
├─────────────────────────────────────┼─────────────────────────────────────────┤
│ @validator returns value            │ @field_validator returns value          │
│ cls method, first arg = cls         │ must be @classmethod explicitly         │
├─────────────────────────────────────┼─────────────────────────────────────────┤
│ constr(regex=...)                   │ constr(pattern=...)                     │
│ validator(each_item=True)           │ @field_validator on list, iterate self  │
│ Schema(...)                         │ Field(...)                              │
└─────────────────────────────────────┴─────────────────────────────────────────┘

Breaking Changes Summary:
  - Validators MUST be @classmethod in v2 (auto-enforced)
  - Field(..., regex=) → Field(..., pattern=)
  - Required fields no longer accept None by default
  - .dict() and .json() still work but are DEPRECATED (use model_dump)
  - StrictInt, StrictStr, etc. still available but Annotated[] preferred
  - GenericModel no longer needed — just use Generic[T] directly on BaseModel
"""
print(MIGRATION_CHEATSHEET)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 13 — INTERVIEW Q&A
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("SECTION 13 — INTERVIEW Q&A (15 Questions)")
print("=" * 60)

QA = """
Q1. What is the biggest architectural change in Pydantic v2?
A1. The validation/serialization core was rewritten in Rust (pydantic-core),
    making v2 5–50x faster than v1 for validation. The Python API also changed
    significantly (validators, ORM mode, schema access).

Q2. How do you replace orm_mode = True from Pydantic v1?
A2. Use model_config = ConfigDict(from_attributes=True). Call
    Model.model_validate(orm_obj) instead of Model.from_orm(orm_obj).

Q3. What is the difference between validation_alias and serialization_alias?
A3. validation_alias: the name used when READING/validating input.
    serialization_alias: the name used when WRITING/dumping output.
    alias: applies to both directions simultaneously.

Q4. Explain @field_validator modes: before, after, wrap.
A4. before — runs before Pydantic type coercion; receives raw input.
    after  — runs after type coercion; receives the final typed value.
    wrap   — you call `handler(v)` yourself to invoke the next step,
             giving full control (e.g., catch exceptions, transform).

Q5. What is @model_validator(mode='before') vs mode='after'?
A5. mode='before': receives raw dict/data before any fields are processed.
                   Good for renaming keys or restructuring the whole input.
    mode='after':  receives the fully validated model instance (self).
                   Good for cross-field validation (e.g., passwords match).

Q6. What is a discriminated union and why is it faster?
A6. A discriminated union uses a Literal field (discriminator) to identify
    which model to use. Pydantic looks at one field value and picks the
    correct model directly — O(1) — instead of trying each model in order.

Q7. How do computed_fields differ from @property in plain Python?
A7. @computed_field includes the property in model_dump() and
    model_dump_json() output, making it part of the serialized form.
    A plain @property exists only in Python memory and won't appear
    in JSON or dict output.

Q8. What is TypeAdapter and when would you use it?
A8. TypeAdapter allows validating/serializing arbitrary types (not just
    BaseModel subclasses) with Pydantic's engine. Use it for validating
    plain types like list[int] or EmailStr without a full model overhead.
    Ideal for validating function arguments or query parameters.

Q9. How does pydantic-settings read configuration?
A9. It inherits from BaseSettings and reads from (in priority order):
    environment variables > .env file > default values.
    env_prefix adds a namespace (APP_). env_nested_delimiter (__) maps
    APP_DATABASE__HOST to settings.database.host.

Q10. What is model_post_init and when is it called?
A10. model_post_init(self, context) is called AFTER __init__ and all
     validators. It's the safe place to set computed default values on
     fields (using object.__setattr__ if the model is frozen).

Q11. How do you make a Pydantic model hashable?
A11. Set model_config = ConfigDict(frozen=True). This makes instances
     immutable and generates __hash__ based on field values. Frozen
     models can be used as dict keys or in sets.

Q12. What is the difference between exclude_none and exclude_unset?
A12. exclude_none: removes fields whose value IS None.
     exclude_unset: removes fields that were never explicitly set
                    (i.e., still at their default value) — even if
                    the default itself is not None.

Q13. How do Generic models work in Pydantic v2?
A13. Simply inherit from both BaseModel and Generic[T]. No need for
     the special GenericModel class from v1. Concrete types are created
     via MyModel[ConcreteType] syntax.

Q14. How do you validate a list of models from JSON in one call?
A14. Use TypeAdapter:
         adapter = TypeAdapter(list[MyModel])
         items = adapter.validate_json(json_string)
     Or on Python data: adapter.validate_python(list_of_dicts)

Q15. What is model_rebuild() and when is it required?
A15. model_rebuild() recomputes the model's schema. It's required for:
     - Self-referential models (forward references)
     - Models that reference types defined AFTER the model class
     - After monkey-patching a model's fields at runtime
     Usually called once at module level after all models are defined.
"""
print(QA)
