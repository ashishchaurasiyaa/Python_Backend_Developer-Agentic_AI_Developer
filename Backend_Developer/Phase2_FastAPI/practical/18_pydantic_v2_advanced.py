"""
Pydantic v2 Advanced — Production Patterns

field_validator, model_validator, computed_field, discriminated unions,
AliasChoices, custom serializers.
"""

from datetime import datetime
from typing import Annotated, Literal, Union
from pydantic import (
    BaseModel,
    Field,
    ConfigDict,
    AliasChoices,
    field_validator,
    model_validator,
    field_serializer,
    model_serializer,
    computed_field,
    RootModel,
    ValidationError,
    ValidationInfo,
)
from typing_extensions import Self


# ==========================================================================
# 1. BASIC MODEL with full config
# ==========================================================================

class User(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        str_to_lower=False,
        from_attributes=True,       # was orm_mode in v1
        populate_by_name=True,
        extra='forbid',
        validate_assignment=True,   # re-validate on attribute set
        frozen=False,
    )

    id: int
    email: str = Field(..., min_length=5, max_length=200, pattern=r'.+@.+\..+')
    name: str = Field(default='Anonymous', max_length=100)
    age: int = Field(default=0, ge=0, le=150)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ==========================================================================
# 2. FIELD VALIDATORS (replaces @validator from v1)
# ==========================================================================

class Account(BaseModel):
    email: str
    username: str
    age: int

    @field_validator('email')
    @classmethod
    def lowercase_email(cls, v: str) -> str:
        """Default mode='after' — runs after type coercion."""
        return v.lower().strip()

    @field_validator('email', mode='before')
    @classmethod
    def reject_disposable(cls, v):
        """mode='before' — runs on raw input before type validation."""
        if not isinstance(v, str):
            return v
        DISPOSABLE = {'mailinator.com', 'tempmail.com', '10minutemail.com'}
        for domain in DISPOSABLE:
            if domain in v.lower():
                raise ValueError(f'Disposable email domain: {domain}')
        return v

    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str, info: ValidationInfo) -> str:
        # info gives access to other already-validated fields
        if len(v) < 3:
            raise ValueError('Username too short')
        if not v.isalnum():
            raise ValueError('Alphanumeric only')
        return v.lower()


# ==========================================================================
# 3. MODEL VALIDATOR (cross-field validation)
# ==========================================================================

class DateRange(BaseModel):
    start: datetime
    end: datetime

    @model_validator(mode='after')
    def check_dates(self) -> Self:
        """After all fields validated."""
        if self.end < self.start:
            raise ValueError('end must be after start')
        return self


class Order(BaseModel):
    items: list[str]
    discount: float = 0.0
    subtotal: float
    total: float

    @model_validator(mode='before')
    @classmethod
    def parse_legacy(cls, data):
        """Transform legacy/external format before validation."""
        if isinstance(data, dict):
            # Legacy 'amount' field → modern 'subtotal'
            if 'amount' in data and 'subtotal' not in data:
                data['subtotal'] = data.pop('amount')
        return data

    @model_validator(mode='after')
    def compute_and_check(self) -> Self:
        expected_total = self.subtotal * (1 - self.discount)
        if abs(self.total - expected_total) > 0.01:
            raise ValueError(
                f'Total mismatch: {self.total} != {expected_total}'
            )
        if self.discount > 0.5:
            raise ValueError('Discount too high')
        return self


# ==========================================================================
# 4. COMPUTED FIELD (derived property in response)
# ==========================================================================

class Rectangle(BaseModel):
    width: float = Field(gt=0)
    height: float = Field(gt=0)

    @computed_field
    @property
    def area(self) -> float:
        return self.width * self.height

    @computed_field(repr=False)
    @property
    def perimeter(self) -> float:
        return 2 * (self.width + self.height)

    @computed_field
    @property
    def aspect_ratio(self) -> float:
        return round(self.width / self.height, 2)


# Usage
# r = Rectangle(width=10, height=5)
# r.model_dump()
# {'width': 10.0, 'height': 5.0, 'area': 50.0, 'perimeter': 30.0, 'aspect_ratio': 2.0}


# ==========================================================================
# 5. ALIASCHOICES (accept multiple input field names)
# ==========================================================================

class UserFromMultipleAPIs(BaseModel):
    """Accepts input from old API (user_id) or new API (userId) or third-party (id)."""

    model_config = ConfigDict(populate_by_name=True)

    user_id: int = Field(
        validation_alias=AliasChoices('user_id', 'userId', 'uid', 'id'),
    )
    full_name: str = Field(
        validation_alias=AliasChoices('full_name', 'fullName', 'name'),
        serialization_alias='fullName',  # output as camelCase
    )
    email_address: str = Field(
        validation_alias=AliasChoices('email_address', 'emailAddress', 'email'),
        serialization_alias='emailAddress',
    )


# All of these work
# UserFromMultipleAPIs(user_id=1, full_name='Alice', email_address='a@b.com')
# UserFromMultipleAPIs(userId=1, fullName='Alice', emailAddress='a@b.com')
# UserFromMultipleAPIs(id=1, name='Alice', email='a@b.com')


# ==========================================================================
# 6. DISCRIMINATED UNION (polymorphic)
# ==========================================================================

class Cat(BaseModel):
    type: Literal['cat']
    meows_per_day: int
    indoor: bool = True


class Dog(BaseModel):
    type: Literal['dog']
    barks_per_day: int
    breed: str


class Bird(BaseModel):
    type: Literal['bird']
    tweets_per_day: int
    can_fly: bool = True


Pet = Annotated[Union[Cat, Dog, Bird], Field(discriminator='type')]


class Owner(BaseModel):
    name: str
    pet: Pet


# Usage
# o = Owner(name='Alice', pet={'type': 'dog', 'barks_per_day': 10, 'breed': 'Lab'})
# o.pet is now a Dog instance — fast lookup, no try-each


# ==========================================================================
# 7. ROOT MODEL (non-dict root)
# ==========================================================================

class IntList(RootModel[list[int]]):
    """Model whose root is a list, not a dict."""

    def __iter__(self):
        return iter(self.root)

    def __getitem__(self, idx):
        return self.root[idx]


# Usage
# il = IntList([1, 2, 3])
# il.model_dump()  # [1, 2, 3]


class Tags(RootModel[set[str]]):
    """Set of tags as root."""
    pass


# ==========================================================================
# 8. CUSTOM SERIALIZERS
# ==========================================================================

class Event(BaseModel):
    name: str
    when: datetime
    secret: str

    @field_serializer('when')
    def serialize_when(self, v: datetime) -> str:
        """Custom datetime format."""
        return v.strftime('%Y-%m-%dT%H:%M:%SZ')

    @field_serializer('secret', when_used='json')
    def hide_secret(self, v: str) -> str:
        """Only hide when serializing to JSON, not internal dump."""
        return '***'


class Money(BaseModel):
    amount_cents: int
    currency: str = 'USD'

    @model_serializer
    def to_dict(self) -> dict:
        """Override whole-model serialization."""
        return {
            'amount': self.amount_cents / 100,
            'cents': self.amount_cents,
            'currency': self.currency,
            'display': f'{self.currency} {self.amount_cents / 100:.2f}',
        }


# ==========================================================================
# 9. STRICT vs LAX MODE
# ==========================================================================

class StrictAge(BaseModel):
    model_config = ConfigDict(strict=True)
    age: int   # rejects "5", only accepts int


class LaxAge(BaseModel):
    age: int   # accepts "5", coerces to 5


# Per-field strict
from pydantic import StrictInt, StrictStr


class MixedStrict(BaseModel):
    age: StrictInt        # strict
    name: str             # lax (default)


# ==========================================================================
# 10. SERIALIZATION OPTIONS
# ==========================================================================

# u = User(id=1, email='a@b.com', name='Alice')

# Different dump options:
# u.model_dump()                          # dict
# u.model_dump(mode='json')               # JSON-safe (datetime → str)
# u.model_dump(exclude={'email'})         # exclude fields
# u.model_dump(include={'id', 'name'})    # include only
# u.model_dump(exclude_unset=True)        # only set fields (great for PATCH)
# u.model_dump(exclude_defaults=True)     # only non-default fields
# u.model_dump(exclude_none=True)         # skip None values
# u.model_dump(by_alias=True)             # use serialization_alias
# u.model_dump_json(indent=2)             # JSON string


# ==========================================================================
# 11. PATCH PATTERN (PATCH endpoint)
# ==========================================================================

class UserPatch(BaseModel):
    """All fields optional — for partial updates."""

    name: str | None = None
    email: str | None = None
    age: int | None = None


# Usage in FastAPI:
# @app.patch('/users/{user_id}')
# def patch_user(user_id: int, patch: UserPatch):
#     user = db.get_user(user_id)
#     for k, v in patch.model_dump(exclude_unset=True).items():
#         setattr(user, k, v)
#     db.save(user)


# ==========================================================================
# 12. JSON SCHEMA EXPORT
# ==========================================================================

# schema = User.model_json_schema()
# OpenAPI-compatible JSON schema — same as what FastAPI puts in /openapi.json


# ==========================================================================
# 13. MODEL COPY
# ==========================================================================

# u1 = User(id=1, email='a@b.com', name='Alice')
# u2 = u1.model_copy(update={'name': 'Bob'})       # shallow copy with update
# u3 = u1.model_copy(deep=True, update={'name': 'Carol'})


# ==========================================================================
# 14. CUSTOM ERROR HANDLING
# ==========================================================================

# try:
#     User(id='not-an-int', email='bad')
# except ValidationError as e:
#     errors = e.errors()
#     # [{'type': 'int_parsing', 'loc': ('id',), 'msg': '...', 'input': 'not-an-int'},
#     #  {'type': 'string_pattern_mismatch', 'loc': ('email',), ...}]
#     for err in errors:
#         print(f"  {'.'.join(map(str, err['loc']))}: {err['msg']}")


# ==========================================================================
# 15. PYDANTIC SETTINGS
# ==========================================================================

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        env_prefix='APP_',
        env_nested_delimiter='__',
        case_sensitive=False,
        extra='ignore',
    )

    debug: bool = False
    db_url: str
    redis_url: str = 'redis://localhost:6379/0'
    log_level: str = 'INFO'


# Reads from APP_DEBUG, APP_DB_URL, APP_REDIS_URL etc env vars
# settings = AppSettings()
