# Pydantic v2 Advanced — Validators, Serializers, Computed Fields

## Why It Matters (Senior 5 YOE Context)

Pydantic v2 = **Rust-powered, 10x faster than v1**, redesigned API. FastAPI 0.100+ uses v2. Senior 5 YOE must know:

- `field_validator` vs `model_validator` (replaced v1's `validator`)
- `computed_field` for derived properties in response
- `AliasChoices` for input flexibility
- `Discriminated unions` for polymorphic models
- `model_config` (replaced inner `Config` class)
- `RootModel` for non-dict roots

v1 → v2 migration = real interview topic in 2024-2026.

---

## Core Concepts

### Basic Model — v2 Syntax

```python
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


class User(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        from_attributes=True,        # was orm_mode in v1
        populate_by_name=True,       # accept both field name + alias
        extra='forbid',              # reject unknown fields
    )

    id: int
    email: str = Field(..., min_length=5, pattern=r'.+@.+\..+')
    name: str = Field(default='Anonymous', max_length=100)
    age: int = Field(default=0, ge=0, le=150)
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

### `field_validator` (replaces `@validator`)

```python
from pydantic import field_validator, ValidationInfo


class User(BaseModel):
    email: str
    name: str

    @field_validator('email')
    @classmethod
    def email_lowercase(cls, v: str) -> str:
        return v.lower().strip()

    @field_validator('email', mode='before')  # before type coercion
    @classmethod
    def reject_disposable(cls, v: str) -> str:
        if any(domain in v.lower() for domain in ['mailinator.com', 'tempmail']):
            raise ValueError('Disposable emails not allowed')
        return v

    @field_validator('name', mode='after')   # after type coercion (default)
    @classmethod
    def validate_name(cls, v: str, info: ValidationInfo) -> str:
        if len(v.split()) < 1:
            raise ValueError('Name required')
        return v.title()
```

### `model_validator` (whole-object validation)

```python
from pydantic import model_validator
from typing_extensions import Self


class Order(BaseModel):
    items: list[str]
    discount: float = 0
    total: float

    @model_validator(mode='after')
    def check_discount(self) -> Self:
        if self.discount > 0.5:
            raise ValueError('Discount cannot exceed 50%')
        return self

    @model_validator(mode='before')
    @classmethod
    def parse_legacy_format(cls, data):
        # Transform legacy input shape
        if isinstance(data, dict) and 'amount' in data:
            data['total'] = data.pop('amount')
        return data
```

### `computed_field` (derived properties in response)

```python
from pydantic import computed_field


class Rectangle(BaseModel):
    width: float
    height: float

    @computed_field
    @property
    def area(self) -> float:
        return self.width * self.height

    @computed_field(repr=False)
    @property
    def perimeter(self) -> float:
        return 2 * (self.width + self.height)


r = Rectangle(width=4, height=5)
r.model_dump()
# {'width': 4.0, 'height': 5.0, 'area': 20.0, 'perimeter': 18.0}
```

### `Field` with `AliasChoices` (Multi-Source Input)

```python
from pydantic import AliasChoices


class User(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: int = Field(
        validation_alias=AliasChoices('user_id', 'userId', 'uid', 'id'),
    )
    full_name: str = Field(
        validation_alias=AliasChoices('full_name', 'fullName', 'name'),
        serialization_alias='fullName',  # output as camelCase
    )


# All these work
User(user_id=1, full_name='Alice')
User(userId=1, fullName='Alice')
User(uid=1, name='Alice')
```

### Discriminated Union (Polymorphic)

```python
from typing import Literal, Union
from pydantic import Field


class Cat(BaseModel):
    type: Literal['cat']
    meows: int


class Dog(BaseModel):
    type: Literal['dog']
    barks: int


class Bird(BaseModel):
    type: Literal['bird']
    tweets: int


Pet = Annotated[Union[Cat, Dog, Bird], Field(discriminator='type')]


class Owner(BaseModel):
    name: str
    pet: Pet


# Pydantic uses 'type' to pick correct class — fast
o = Owner(name='Alice', pet={'type': 'dog', 'barks': 5})
# o.pet is now a Dog instance
```

Performance: discriminator avoids trying each type. Critical for large unions.

### `RootModel` (Non-Dict Root)

```python
from pydantic import RootModel


class IntList(RootModel[list[int]]):
    pass


il = IntList([1, 2, 3])
il.root  # [1, 2, 3]
il.model_dump()  # [1, 2, 3]
```

Use when API takes a bare list/string/etc as input.

### Custom Serializers (`@field_serializer`, `@model_serializer`)

```python
from pydantic import field_serializer, model_serializer
from datetime import datetime


class Event(BaseModel):
    name: str
    when: datetime

    @field_serializer('when')
    def serialize_when(self, v: datetime) -> str:
        return v.isoformat()


class Money(BaseModel):
    amount_cents: int

    @model_serializer
    def to_dict(self) -> dict:
        return {
            'amount': self.amount_cents / 100,
            'cents': self.amount_cents,
        }


Money(amount_cents=1099).model_dump()
# {'amount': 10.99, 'cents': 1099}
```

### `model_dump()` vs `model_dump_json()` Modes

```python
class User(BaseModel):
    id: int
    name: str
    secret: str


u = User(id=1, name='Alice', secret='abc')

u.model_dump()                # dict
u.model_dump(exclude={'secret'})  # exclude fields
u.model_dump(include={'id', 'name'})
u.model_dump(exclude_unset=True)   # only fields explicitly set
u.model_dump(exclude_defaults=True)  # only non-default fields
u.model_dump(mode='json')          # JSON-safe (datetime → str)

u.model_dump_json()                # JSON string directly
u.model_dump_json(indent=2)
```

### Settings via `pydantic-settings`

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env',
        env_prefix='APP_',
        env_nested_delimiter='__',
    )

    debug: bool = False
    db_url: str
    redis_url: str = 'redis://localhost:6379/0'


# Reads from .env + os.environ (APP_DEBUG, APP_DB_URL, ...)
config = Config()
```

### Validation Mode (strict vs lax)

```python
from pydantic import BaseModel, Field, StrictInt


class StrictUser(BaseModel):
    model_config = ConfigDict(strict=True)
    age: int   # rejects "5" (string), only int


class LaxUser(BaseModel):
    age: int   # accepts "5", coerces to 5
```

Or per-field:

```python
class User(BaseModel):
    age: StrictInt   # this field only is strict
```

---

## How It Works Internally

### Rust Core

Pydantic v2 uses `pydantic-core` (Rust). 10-50x faster validation. Models compile to Rust validator schemas at import time.

### Validation Pipeline

```
input
  ↓
mode='before' validators (raw input)
  ↓
type coercion (Rust)
  ↓
mode='after' validators (typed values, default)
  ↓
model_validator (mode='after')
  ↓
instance
```

### Serialization Pipeline

```
instance
  ↓
field_serializer (per field)
  ↓
model_serializer (whole model, if defined — else default)
  ↓
output dict / JSON
```

---

## Common Pitfalls

### 1. v1 Syntax in v2

```python
# v1 — broken in v2
@validator('email')
def lower(cls, v): ...

# v2
@field_validator('email')
@classmethod
def lower(cls, v): ...
```

### 2. `from_attributes` Replaces `orm_mode`

```python
# v1
class Config:
    orm_mode = True

# v2
model_config = ConfigDict(from_attributes=True)
```

### 3. Mutable Defaults

```python
class Bad(BaseModel):
    tags: list = []  # SHARED across instances!

class Good(BaseModel):
    tags: list = Field(default_factory=list)
```

### 4. `Field(...)` for required

```python
# Both are required
class User(BaseModel):
    id: int                    # required by default
    name: str = Field(...)     # explicit required (ellipsis)
    age: int = Field(default=0)  # optional with default
```

### 5. JSON Schema Generation

```python
# Generate OpenAPI-compatible JSON schema
User.model_json_schema()
```

### 6. Model Copy

```python
# v2
u2 = u.model_copy(update={'name': 'Bob'})  # was .copy() in v1

# Deep copy
u2 = u.model_copy(deep=True)
```

### 7. Field Naming Conflicts

```python
class Item(BaseModel):
    # 'fields' is reserved in Pydantic — error
    fields: list[str]   # use 'items' or rename
```

### 8. Validation Doesn't Run on Direct Assignment

```python
class User(BaseModel):
    age: int = Field(ge=0)

u = User(age=10)
u.age = -5  # silent — no validation by default!


# Enable
class User(BaseModel):
    model_config = ConfigDict(validate_assignment=True)
    age: int = Field(ge=0)
```

---

## Interview Q&A

**Q1:** Pydantic v1 vs v2 — major changes?
**A:** (1) Rust core — 10-50x faster. (2) `@validator` → `@field_validator`. (3) `orm_mode` → `from_attributes`. (4) Inner `Config` class → `model_config = ConfigDict(...)`. (5) `.dict()` → `model_dump()`. (6) `.copy()` → `model_copy()`. (7) Better Union handling via discriminator. (8) New `computed_field`. (9) `RootModel` replaces `__root__`. (10) Strict mode.

**Q2:** `field_validator` vs `model_validator` kab use karoge?
**A:** `field_validator` — validate one field, can run before/after type coercion. `model_validator` — validate whole instance / multiple fields together / transform raw input. Use field for simple field-level rules, model for cross-field validation (e.g., end_date > start_date).

**Q3:** Discriminated union ka benefit kya?
**A:** Pydantic uses discriminator key to pick the right variant — single lookup. Without discriminator, tries each variant (slow for large unions). Also better error messages and OpenAPI schema (oneOf with mapping). Use `Annotated[Union[A, B, C], Field(discriminator='type')]`.

**Q4:** `computed_field` ka use case?
**A:** Derived properties that should appear in response. Example: User has `first_name` + `last_name`, computed `full_name` for output. Or `Rectangle` has `width`, `height`, computed `area`. Avoids storing redundant data; clients see all fields.

**Q5:** `model_dump(exclude_unset=True)` kya karta hai?
**A:** Returns only fields that were explicitly set by user (not defaults). Useful for PATCH endpoints — only send changed fields. Differentiates between "user didn't send this" vs "user sent default".

**Q6:** `AliasChoices` ka practical use?
**A:** Accept multiple input formats — e.g., legacy `user_id` + new `userId`. Or different external APIs with different naming. `validation_alias=AliasChoices('a', 'b', 'c')` tries each. Combined with `serialization_alias` for output naming.

**Q7:** `strict` mode kab enable karoge?
**A:** Public APIs where type coercion is dangerous (`"5"` → 5 might mask bugs). Internal services with controlled input. Performance: marginally slower (validates without coercion attempts). Default `strict=False` lax mode for JSON-from-HTTP.

**Q8:** Pydantic v2 mein migrating se kya benefits?
**A:** Performance — 10-50x speedup on validation-heavy endpoints. FastAPI 0.100+ requires v2. Better Union/discriminator support. Cleaner API (model_config vs Config). Better error messages. `computed_field` for response shaping.

---

## Real-World Use Cases

### 1. API Request/Response Models

```python
class ArticleCreateIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    body: str
    tags: list[str] = Field(default_factory=list, max_length=10)


class ArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    body: str
    author_name: str
    created_at: datetime

    @computed_field
    @property
    def excerpt(self) -> str:
        return self.body[:200]
```

### 2. Polymorphic Event Stream

```python
class UserCreated(BaseModel):
    type: Literal['user_created']
    user_id: int


class OrderPlaced(BaseModel):
    type: Literal['order_placed']
    order_id: int
    amount: float


Event = Annotated[Union[UserCreated, OrderPlaced], Field(discriminator='type')]


# Single endpoint handles all event types
@app.post("/events")
def handle(event: Event):
    if isinstance(event, UserCreated):
        ...
```

### 3. Config from Env

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env')

    database_url: PostgresDsn
    redis_url: RedisDsn
    secret_key: str = Field(min_length=32)
    debug: bool = False


settings = Settings()  # validates on startup
```

---

## References

- [Pydantic v2 docs](https://docs.pydantic.dev/latest/)
- [Migration guide v1 → v2](https://docs.pydantic.dev/latest/migration/)
- [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- Samuel Colvin (Pydantic creator) talks
