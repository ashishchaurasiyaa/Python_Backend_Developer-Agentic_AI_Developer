"""
Pydantic V2 — Practical Runnable Examples
==========================================
Topics covered:
  - BaseModel with Field constraints and ConfigDict
  - field_validator (mode="before" / "after")
  - model_validator (mode="before" / "after")
  - computed_field
  - Pydantic Settings (BaseSettings) with SecretStr
  - model_dump() / model_dump_json() / serialization customization
  - Custom Annotated types (AfterValidator)
  - TypeAdapter — validate without a model
  - Discriminated unions
  - FastAPI-style request/response demo

How to run:
  python 01_pydantic_v2_practical.py

pip install:
  pip install pydantic>=2.5 pydantic-settings>=2.1 email-validator
"""

# ─── Section 1: BaseModel Basics — Field constraints, ConfigDict ───

from pydantic import (
    BaseModel,
    Field,
    ConfigDict,
    field_validator,
    model_validator,
    computed_field,
    field_serializer,
    TypeAdapter,
    ValidationError,
    SecretStr,
)
from pydantic.functional_validators import AfterValidator
from typing import Annotated, Literal, Optional, Union
from datetime import datetime
from decimal import Decimal
import re

print("=" * 60)
print("SECTION 1: BaseModel Basics")
print("=" * 60)


class UserModel(BaseModel):
    # INTERVIEW: model_config replaces V1's inner `class Config:`
    model_config = ConfigDict(
        str_strip_whitespace=True,   # auto-strip all str fields
        validate_assignment=True,    # obj.field = value also validated
        populate_by_name=True,       # accept both alias and field name
        extra="forbid",              # unknown fields raise ValidationError
    )

    id: int

    # INTERVIEW: Field(...) = required. ge/le/min_length/max_length = constraints
    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_]+$",
        description="Alphanumeric + underscore only",
    )

    # Optional field with None default
    email: Optional[str] = Field(default=None)

    # INTERVIEW: alias — JSON uses "fullName", Python uses full_name
    full_name: str = Field(alias="fullName", default="")

    # INTERVIEW: Literal restricts to exact values — like Enum but lighter
    role: Literal["admin", "user", "moderator"] = "user"

    age: int = Field(default=18, ge=0, le=150)

    # default_factory runs per-instance, not once at class definition
    created_at: datetime = Field(default_factory=datetime.now)

    # INTERVIEW: exclude=True means field not in model_dump() / model_dump_json()
    password_hash: str = Field(default="", exclude=True)


# Create instance — fullName alias works for construction
user = UserModel(
    id=1,
    username="ashish_99",
    email="ashish@example.com",
    fullName="Ashish Kumar",   # alias accepted
    age=25,
    password_hash="bcrypt_hash_here",
)

print(f"user.full_name = {user.full_name}")          # Python name works too
print(f"model_dump() = {user.model_dump()}")         # password_hash excluded
print(f"by_alias=True: {user.model_dump(by_alias=True)}")  # fullName in output

# Validate from dict
user2 = UserModel.model_validate({"id": 2, "username": "bob", "fullName": "Bob"})
print(f"\nmodel_validate: {user2.username}")

# Validate from JSON string
user3 = UserModel.model_validate_json('{"id": 3, "username": "charlie", "fullName": "C"}')
print(f"model_validate_json: {user3.id}")

# Validation error demo
try:
    UserModel(id=1, username="x")  # too short
except ValidationError as e:
    print(f"\nValidationError ({e.error_count()} errors):")
    for err in e.errors():
        loc = ".".join(str(x) for x in err["loc"])
        print(f"  {loc}: {err['msg']}")


# ─── Section 2: field_validator and model_validator ───

print("\n" + "=" * 60)
print("SECTION 2: Validators")
print("=" * 60)


class ProductModel(BaseModel):
    name: str
    price: float = Field(gt=0)
    discount_percent: float = Field(default=0.0, ge=0, le=100)
    stock: int = Field(ge=0)
    sku: str
    final_price: float = 0.0

    # INTERVIEW: mode="before" — raw input (before type coercion)
    # Good for: cleaning strings, removing commas, type casting from form data
    @field_validator("price", "discount_percent", mode="before")
    @classmethod
    def clean_number(cls, v: object) -> object:
        if isinstance(v, str):
            return float(v.replace(",", "").strip())
        return v

    # INTERVIEW: mode="after" — typed Python value (after coercion)
    # Good for: business logic, format validation on the correct type
    @field_validator("name", mode="after")
    @classmethod
    def clean_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Name cannot be empty")
        return v.title()

    @field_validator("sku", mode="after")
    @classmethod
    def validate_sku(cls, v: str) -> str:
        v = v.upper().strip()
        if not re.match(r"^[A-Z]{2}-\d{4}$", v):
            raise ValueError("SKU must match pattern AB-1234")
        return v

    # INTERVIEW: model_validator(mode="before") — raw dict, before any field parsing
    # Good for: cross-field presence checks, normalising keys
    @model_validator(mode="before")
    @classmethod
    def check_required_fields(cls, data: dict) -> dict:
        if not data.get("name") and not data.get("sku"):
            raise ValueError("At least one of name or sku is required")
        return data

    # INTERVIEW: model_validator(mode="after") — full model instance
    # Good for: derived fields, cross-field logic using typed values
    @model_validator(mode="after")
    def compute_final_price(self) -> "ProductModel":
        discount = self.price * (self.discount_percent / 100)
        self.final_price = round(self.price - discount, 2)
        return self


product = ProductModel(
    name="  blue t-shirt  ",
    price="1,299",          # string — cleaned by mode="before"
    discount_percent=10,
    stock=50,
    sku="ts-0042",          # lowercase — uppercased by validator
)

print(f"name = {product.name}")               # "Blue T-Shirt"
print(f"price = {product.price}")             # 1299.0
print(f"sku = {product.sku}")                 # "TS-0042"
print(f"final_price = {product.final_price}") # 1169.1


# ─── Section 3: computed_field + Custom Annotated Types ───

print("\n" + "=" * 60)
print("SECTION 3: computed_field + Annotated Types")
print("=" * 60)


# INTERVIEW: Annotated[type, validator] = reusable inline custom types
# AfterValidator runs after type coercion — value is already the right type
def _validate_indian_phone(v: str) -> str:
    digits = re.sub(r"\D", "", v)
    if len(digits) == 10:
        return f"+91{digits}"
    elif len(digits) == 12 and digits.startswith("91"):
        return f"+{digits}"
    raise ValueError(f"Invalid Indian phone number: {v!r}")


def _validate_pincode(v: str) -> str:
    if not re.match(r"^\d{6}$", str(v)):
        raise ValueError("Pincode must be exactly 6 digits")
    return str(v)


# Reusable type aliases — use anywhere in any model
IndianPhone = Annotated[str, AfterValidator(_validate_indian_phone)]
Pincode = Annotated[str, AfterValidator(_validate_pincode)]


class CustomerProfile(BaseModel):
    first_name: str
    last_name: str
    email: str
    phone: IndianPhone
    pincode: Pincode
    orders_count: int = 0
    total_spent: float = 0.0

    # INTERVIEW: @computed_field — appears in model_dump() + model_dump_json()
    # Normal @property is NOT included in serialization — computed_field IS
    @computed_field
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @computed_field
    @property
    def email_domain(self) -> str:
        return self.email.split("@")[-1]

    @computed_field
    @property
    def is_loyal_customer(self) -> bool:
        return self.orders_count >= 10 or self.total_spent >= 50000

    @computed_field(repr=False)
    @property
    def tier(self) -> str:
        if self.total_spent >= 100_000:
            return "platinum"
        if self.total_spent >= 50_000:
            return "gold"
        if self.total_spent >= 10_000:
            return "silver"
        return "bronze"


customer = CustomerProfile(
    first_name="Ashish",
    last_name="Kumar",
    email="ashish@gmail.com",
    phone="9876543210",   # → "+919876543210"
    pincode="400001",
    orders_count=15,
    total_spent=75_000,
)

print(f"full_name = {customer.full_name}")
print(f"phone = {customer.phone}")             # normalized
print(f"tier = {customer.tier}")               # gold
print(f"is_loyal = {customer.is_loyal_customer}")

dump = customer.model_dump()
# computed_field keys appear in the dict
print(f"dump keys: {list(dump.keys())}")


# ─── Section 4: Serialization Customization — field_serializer ───

print("\n" + "=" * 60)
print("SECTION 4: field_serializer")
print("=" * 60)


class InvoiceModel(BaseModel):
    invoice_id: str
    amount: Decimal
    created_at: datetime
    tags: list[str] = []

    # INTERVIEW: field_serializer lets you control how a field appears in output
    # Useful for Decimal → float, datetime → custom string, list → CSV
    @field_serializer("created_at")
    def serialize_dt(self, v: datetime) -> str:
        return v.strftime("%d %b %Y %H:%M")

    @field_serializer("amount")
    def serialize_amount(self, v: Decimal) -> float:
        return float(v)

    @field_serializer("tags")
    def serialize_tags(self, v: list[str]) -> str:
        return ", ".join(v)


invoice = InvoiceModel(
    invoice_id="INV-001",
    amount=Decimal("1299.50"),
    created_at=datetime(2026, 5, 22, 14, 30),
    tags=["urgent", "b2b", "gst"],
)
print(f"model_dump() = {invoice.model_dump()}")
print(f"model_dump_json() = {invoice.model_dump_json()}")


# ─── Section 5: Discriminated Unions ───

print("\n" + "=" * 60)
print("SECTION 5: Discriminated Unions")
print("=" * 60)


# INTERVIEW: Discriminated union = type field se correct model choose karo
# Faster than plain Union[A, B, C] which tries each model in order
class EmailNotification(BaseModel):
    type: Literal["email"] = "email"
    to: str
    subject: str
    body: str


class SMSNotification(BaseModel):
    type: Literal["sms"] = "sms"
    phone: str
    message: str


class PushNotification(BaseModel):
    type: Literal["push"] = "push"
    device_token: str
    title: str
    body: str


Notification = Annotated[
    Union[EmailNotification, SMSNotification, PushNotification],
    Field(discriminator="type"),  # pydantic uses "type" field to pick model
]


class NotificationRequest(BaseModel):
    user_id: str
    notification: Notification


req = NotificationRequest.model_validate({
    "user_id": "user123",
    "notification": {
        "type": "email",
        "to": "ashish@example.com",
        "subject": "Order placed!",
        "body": "Your order #1234 is confirmed.",
    },
})
print(f"notification type: {type(req.notification).__name__}")  # EmailNotification
print(f"subject: {req.notification.subject}")  # type: ignore[union-attr]

sms_req = NotificationRequest.model_validate({
    "user_id": "user456",
    "notification": {"type": "sms", "phone": "+919876543210", "message": "OTP: 123456"},
})
print(f"sms type: {type(sms_req.notification).__name__}")  # SMSNotification


# ─── Section 6: TypeAdapter — validate without a BaseModel ───

print("\n" + "=" * 60)
print("SECTION 6: TypeAdapter")
print("=" * 60)

# INTERVIEW: TypeAdapter validates raw Python types without wrapping in BaseModel
# Useful for validating list[int], dict[str, float], etc. from external sources
int_adapter = TypeAdapter(int)
print(f"str '42' → int: {int_adapter.validate_python('42')}")

list_adapter = TypeAdapter(list[int])
print(f"list str→int: {list_adapter.validate_python(['1', '2', '3'])}")

dict_adapter = TypeAdapter(dict[str, float])
print(f"dict coercion: {dict_adapter.validate_python({'a': '1.5', 'b': 2})}")

# Validate from JSON string directly
print(f"from JSON: {list_adapter.validate_json('[4, 5, 6]')}")

# JSON schema generation
print(f"JSON schema: {list_adapter.json_schema()}")


# ─── Section 7: Pydantic Settings (BaseSettings) ───

print("\n" + "=" * 60)
print("SECTION 7: BaseSettings — Config Management")
print("=" * 60)

# INTERVIEW: BaseSettings loads from env vars, .env files, defaults — in priority order
# Priority: init kwargs > env vars > .env file > defaults
# pip install pydantic-settings

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
    from functools import lru_cache

    class AppSettings(BaseSettings):
        # INTERVIEW: SettingsConfigDict replaces V1's inner class Config
        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            env_prefix="APP_",   # reads APP_DEBUG, APP_SECRET_KEY, etc.
            case_sensitive=False,
            extra="ignore",       # unknown env vars silently ignored
        )

        app_name: str = "My Backend Service"
        debug: bool = False
        environment: Literal["dev", "staging", "prod"] = "dev"

        # INTERVIEW: SecretStr masks value in repr/logs — call .get_secret_value() to read
        secret_key: SecretStr = SecretStr("dev-secret-key-change-in-prod")

        db_pool_size: int = Field(default=5, ge=1, le=50)
        allowed_hosts: list[str] = ["localhost", "127.0.0.1"]

        @property
        def is_prod(self) -> bool:
            return self.environment == "prod"

    # INTERVIEW: @lru_cache singleton — settings loaded once, reused everywhere
    @lru_cache
    def get_settings() -> AppSettings:
        return AppSettings()

    settings = get_settings()
    print(f"app_name = {settings.app_name}")
    print(f"debug = {settings.debug}")
    print(f"secret_key (masked) = {settings.secret_key}")       # SecretStr('**********')
    print(f"secret_key (real) = {settings.secret_key.get_secret_value()}")

except ImportError:
    print("pydantic-settings not installed. Run: pip install pydantic-settings")


# ─── Section 8: Pydantic vs dataclasses — Quick Comparison ───

print("\n" + "=" * 60)
print("SECTION 8: Pydantic vs dataclasses Comparison")
print("=" * 60)

from dataclasses import dataclass

# INTERVIEW: Key differences:
# dataclass = no runtime validation, fast, stdlib
# Pydantic BaseModel = runtime validation, coercion, serialization

@dataclass
class DataclassUser:
    id: int
    name: str
    age: int = 18


class PydanticUser(BaseModel):
    id: int
    name: str
    age: int = Field(default=18, ge=0, le=150)


# dataclass: NO validation — wrong type silently accepted
dc_user = DataclassUser(id="not_an_int", name="Ashish", age=-5)  # type: ignore
print(f"dataclass id type: {type(dc_user.id)}")   # str — no coercion, no error

# Pydantic: validates and coerces
try:
    pyd_user = PydanticUser(id="42", name="Ashish", age=-5)  # age=-5 fails ge=0
except ValidationError as e:
    print(f"Pydantic ValidationError: {e.errors()[0]['msg']}")

pyd_user_ok = PydanticUser(id="42", name="Ashish")  # id coerced str→int
print(f"pydantic id type: {type(pyd_user_ok.id)}, value: {pyd_user_ok.id}")

# INTERVIEW decision table:
# Use dataclass when: internal Python objects, no external input, speed matters
# Use Pydantic when:  API input/output, config, user-provided data, need JSON

print("\n--- SUMMARY ---")
print("field_validator mode='before' : raw input cleanup (str commas, whitespace)")
print("field_validator mode='after'  : business logic on typed value")
print("model_validator mode='before' : cross-field presence checks on raw dict")
print("model_validator mode='after'  : derived fields, cross-field logic on model")
print("computed_field                : property that appears in model_dump()")
print("SecretStr                     : masks value in logs/repr")
print("TypeAdapter                   : validate plain types without BaseModel")
print("Discriminated union           : O(1) model selection by 'type' field")
