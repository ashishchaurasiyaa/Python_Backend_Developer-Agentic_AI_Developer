# Pydantic V2 — Complete Guide

---

# PART 1 — THEORY (Deep Concepts)

## 1.1 Pydantic V2 Kya Hai?

Pydantic ek **data validation library** hai Python ke liye.  
V2 mein Rust mein rewrite kiya gaya — isliye **5–50x faster** than V1.

```
Input Data (dict/JSON/raw)
        │
        ▼
  ┌─────────────┐
  │  Pydantic   │  ← validates, coerces, transforms
  │  BaseModel  │
  └─────────────┘
        │
        ▼
  Typed Python Object (validated, safe to use)
```

**Pydantic use karte hain:**
- FastAPI request/response validation
- Config management (BaseSettings)
- Data serialization (dict ↔ JSON ↔ object)
- Type-safe data pipelines

---

## 1.2 Validation Pipeline — Internally Kaise Kaam Karta Hai

Jab tum `Model.model_validate(data)` call karte ho, yeh hota hai:

```
Step 1: mode="before" model_validator  ← raw dict milta hai
Step 2: Each field ka type coercion    ← "123" → 123, "true" → True
Step 3: mode="before" field_validator  ← raw field value milta hai
Step 4: Type validation                ← is it actually an int?
Step 5: mode="after" field_validator   ← typed value milta hai
Step 6: mode="after" model_validator   ← full model instance milta hai
Step 7: computed_field calculate hote hain
```

**Lax mode (default):** coercion hoti hai — `"123"` → `123`  
**Strict mode:** coercion nahi — `"123"` integer nahi maana jayega

---

## 1.3 Field Types — Kya Kya Store Kar Sakte Ho

```
BaseModel field types:
├── Python built-ins: int, str, float, bool, list, dict, set, tuple
├── typing: Optional, Union, List, Dict, Literal, Any
├── datetime: date, time, datetime, timedelta
├── Pydantic special: EmailStr, HttpUrl, PostgresDsn, SecretStr, UUID
├── Annotated types: custom validators inline mein
├── Nested models: dusra BaseModel as field
└── Discriminated unions: type field se decide karo kaunsa model
```

---

## 1.4 Validator Types — Teeno Ka Fark

| Validator | Decorator | `mode` | Input | Use Case |
|-----------|-----------|--------|-------|----------|
| `field_validator` | `@field_validator("field")` | `before` / `after` / `wrap` | raw or typed value | Single field validate/transform |
| `model_validator` | `@model_validator` | `before` / `after` | raw dict or model instance | Cross-field logic |
| `Annotated` + `AfterValidator` | inline in type | after | typed value | Reusable custom types |

**`mode="before"`** → raw input milta hai (string, dict) — type check se pehle  
**`mode="after"`** → typed Python value milta hai — type check ke baad  
**`mode="wrap"`** → tum khud decide karte ho call karna hai ya nahi

---

## 1.5 Computed Fields — Property Jo Serialize Hoti Hai

Normal `@property` model_dump() mein include nahi hoti.  
`@computed_field` use karo jab property ko JSON/dict mein chahiye.

```
Without computed_field:   model.full_name works BUT not in model_dump()
With @computed_field:     model.full_name works AND appears in model_dump()
```

---

## 1.6 BaseSettings — Config Loading Order

```
Priority (highest to lowest):
1. init_settings     ← directly pass kiya: Settings(debug=True)
2. env_settings      ← environment variables: export APP_DEBUG=true
3. dotenv_settings   ← .env file: APP_DEBUG=true
4. default_settings  ← field default: debug: bool = False
```

Iska matlab: environment variable, .env file ko override karta hai.

---

## 1.7 V1 vs V2 — Breaking Changes Summary

| V1 | V2 |
|----|----|
| `@validator` | `@field_validator` + `@classmethod` |
| `@root_validator(pre=True)` | `@model_validator(mode="before")` |
| `.dict()` | `.model_dump()` |
| `.json()` | `.model_dump_json()` |
| `.parse_obj()` | `.model_validate()` |
| `.parse_raw()` | `.model_validate_json()` |
| `.schema()` | `.model_json_schema()` |
| `class Config:` | `model_config = ConfigDict(...)` |
| `validator(always=True)` | `@field_validator(..., always=True)` removed — use `model_validator` |

---

## 1.8 ConfigDict Options — Important Ones

```python
model_config = ConfigDict(
    str_strip_whitespace=True,   # auto strip all string fields
    str_min_length=1,            # all strings must be non-empty
    validate_assignment=True,    # obj.name = "x" bhi validate hoga
    populate_by_name=True,       # alias + original name dono kaam karein
    frozen=True,                 # immutable (hashable) — like frozen dataclass
    extra="forbid",              # unknown fields = error ("allow"/"ignore"/"forbid")
    use_enum_values=True,        # enum field → enum.value store karo
    arbitrary_types_allowed=True,# custom non-pydantic types allow karo
)
```

---

# PART 2 — PRACTICAL (Working Code)

## 2.1 Complete BaseModel — Saari Features Ek Jagah

```python
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Annotated, Literal
from datetime import datetime
import re

class UserModel(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        populate_by_name=True,
        extra="forbid",
    )

    # Required field
    id: int

    # String with constraints
    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        pattern=r'^[a-zA-Z0-9_]+$',
        description="Alphanumeric + underscore only"
    )

    # Optional with default
    email: Optional[str] = Field(default=None, examples=["user@example.com"])

    # Alias — JSON key different from Python attr
    full_name: str = Field(alias="fullName", default="")

    # Literal — sirf yahi values allowed
    role: Literal["admin", "user", "moderator"] = "user"

    # Ge/le constraints
    age: int = Field(default=18, ge=0, le=150)

    # Auto default
    created_at: datetime = Field(default_factory=datetime.now)

    # Exclude from serialization
    password_hash: str = Field(default="", exclude=True)

# Create
user = UserModel(
    id=1,
    username="ashish_99",
    email="ashish@example.com",
    fullName="Ashish Kumar",  # alias works
    age=25,
    password_hash="hashed_password"
)

print(user.full_name)          # "Ashish Kumar"
print(user.model_dump())       # password_hash excluded
print(user.model_dump(by_alias=True))   # fullName instead of full_name
print(user.model_dump_json())  # JSON string

# Validate from dict
user2 = UserModel.model_validate({"id": 2, "username": "bob", "fullName": "Bob"})

# Validate from JSON
user3 = UserModel.model_validate_json('{"id": 3, "username": "charlie", "fullName": "C"}')
```

---

## 2.2 All Validator Patterns — Real Examples

```python
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Self
import re

class ProductModel(BaseModel):
    name: str
    price: float = Field(gt=0)
    discount_percent: float = Field(default=0.0, ge=0, le=100)
    stock: int = Field(ge=0)
    sku: str
    final_price: float = 0.0

    # --- field_validator mode="before" ---
    # Raw input pe — string "1,000" → float 1000.0
    @field_validator("price", "discount_percent", mode="before")
    @classmethod
    def clean_number(cls, v):
        if isinstance(v, str):
            return float(v.replace(",", "").strip())
        return v

    # --- field_validator mode="after" ---
    # Typed value pe — str already string hai
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
        if not re.match(r'^[A-Z]{2}-\d{4}$', v):
            raise ValueError("SKU must be like AB-1234")
        return v

    # --- model_validator mode="before" ---
    # Raw dict milta hai — field exist karta hai check karo
    @model_validator(mode="before")
    @classmethod
    def check_name_or_sku(cls, data: dict) -> dict:
        if not data.get("name") and not data.get("sku"):
            raise ValueError("name ya sku dono mein se ek zaroori hai")
        return data

    # --- model_validator mode="after" ---
    # Self milta hai — cross-field calculation
    @model_validator(mode="after")
    def compute_final_price(self) -> Self:
        discount = self.price * (self.discount_percent / 100)
        self.final_price = round(self.price - discount, 2)
        return self


# Testing all validators
product = ProductModel(
    name="  blue shirt  ",
    price="1,299",           # string cleaned by mode="before"
    discount_percent=10,
    stock=50,
    sku="ts-0042",           # lowercased — validator uppercases
)
print(product.name)          # "Blue Shirt"
print(product.price)         # 1299.0
print(product.sku)           # "TS-0042"
print(product.final_price)   # 1169.1

# Validation errors
from pydantic import ValidationError
try:
    ProductModel(name="", price=-10, discount_percent=110, stock=-1, sku="bad")
except ValidationError as e:
    print(f"{e.error_count()} errors:")
    for err in e.errors():
        print(f"  {'.'.join(str(x) for x in err['loc'])}: {err['msg']}")
```

---

## 2.3 Computed Fields + Custom Annotated Types

```python
from pydantic import BaseModel, Field, computed_field
from pydantic.functional_validators import AfterValidator
from typing import Annotated
import re

# --- Reusable custom types with Annotated ---

def validate_indian_phone(v: str) -> str:
    digits = re.sub(r'\D', '', v)
    if len(digits) == 10:
        return f"+91{digits}"
    elif len(digits) == 12 and digits.startswith("91"):
        return f"+{digits}"
    raise ValueError(f"Invalid Indian phone: {v}")

def validate_pincode(v: str) -> str:
    if not re.match(r'^\d{6}$', str(v)):
        raise ValueError("Pincode must be 6 digits")
    return str(v)

# Custom types — reuse anywhere
IndianPhone = Annotated[str, AfterValidator(validate_indian_phone)]
Pincode     = Annotated[str, AfterValidator(validate_pincode)]

# --- Model with computed_field ---
class CustomerProfile(BaseModel):
    first_name: str
    last_name: str
    email: str
    phone: IndianPhone
    pincode: Pincode
    orders_count: int = 0
    total_spent: float = 0.0

    @computed_field
    @property
    def full_name(self) -> str:
        """In model_dump() and JSON automatically"""
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
        if self.total_spent >= 100000: return "platinum"
        if self.total_spent >= 50000:  return "gold"
        if self.total_spent >= 10000:  return "silver"
        return "bronze"


customer = CustomerProfile(
    first_name="Ashish", last_name="Kumar",
    email="ashish@gmail.com",
    phone="9876543210",    # → "+919876543210"
    pincode="400001",
    orders_count=15, total_spent=75000
)

print(customer.full_name)         # "Ashish Kumar"
print(customer.phone)             # "+919876543210"
print(customer.tier)              # "gold"
print(customer.is_loyal_customer) # True

dump = customer.model_dump()
# full_name, email_domain, is_loyal_customer, tier — sab included!
print(dump.keys())
```

---

## 2.4 Discriminated Unions — Multiple Model Types

```python
from pydantic import BaseModel, Field
from typing import Literal, Union, Annotated

# Alag alag notification types
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
    type: Literal["push"] = "sms"
    device_token: str
    title: str
    body: str

# Discriminated union — "type" field se decide hoga kaunsa model
Notification = Annotated[
    Union[EmailNotification, SMSNotification, PushNotification],
    Field(discriminator="type")
]

class NotificationRequest(BaseModel):
    user_id: str
    notification: Notification   # auto-detect based on "type"

# Pydantic automatically correct model choose karta hai
req = NotificationRequest.model_validate({
    "user_id": "user123",
    "notification": {
        "type": "email",
        "to": "ashish@example.com",
        "subject": "Order placed!",
        "body": "Your order #1234 is confirmed."
    }
})

print(type(req.notification))  # <class 'EmailNotification'>
print(req.notification.subject)  # "Order placed!"

# SMS
sms_req = NotificationRequest.model_validate({
    "user_id": "user456",
    "notification": {"type": "sms", "phone": "+919876543210", "message": "OTP: 123456"}
})
print(type(sms_req.notification))  # <class 'SMSNotification'>
```

---

## 2.5 BaseSettings — Production Config Management

```python
# pip install pydantic-settings

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, SecretStr, PostgresDsn, RedisDsn
from functools import lru_cache
from typing import Literal

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="APP_",     # env var: APP_DEBUG=true
        case_sensitive=False,
        extra="ignore",
    )

    # App settings
    app_name: str = "My Backend"
    debug: bool = False
    environment: Literal["dev", "staging", "prod"] = "dev"
    secret_key: SecretStr    # required — no default

    # Database
    database_url: PostgresDsn = "postgresql://user:pass@localhost:5432/mydb"
    db_pool_size: int = Field(default=5, ge=1, le=50)

    # Redis
    redis_url: RedisDsn = "redis://localhost:6379/0"

    # API keys — SecretStr never printed in logs
    stripe_key: SecretStr = ""

    @property
    def is_prod(self) -> bool:
        return self.environment == "prod"

    @property
    def db_url_str(self) -> str:
        return str(self.database_url)


# Singleton — ek baar load, baar baar reuse
@lru_cache
def get_settings() -> Settings:
    return Settings()

# FastAPI mein use
# def some_endpoint(settings: Settings = Depends(get_settings)): ...

# .env file:
"""
APP_APP_NAME=YAM Backend
APP_DEBUG=false
APP_ENVIRONMENT=prod
APP_SECRET_KEY=my-super-secret-key
APP_DATABASE_URL=postgresql://prod_user:prod_pass@db:5432/prod_db
APP_REDIS_URL=redis://redis:6379/0
APP_STRIPE_KEY=sk_live_...
"""
```

---

## 2.6 Serialization Customization

```python
from pydantic import BaseModel, field_serializer
from datetime import datetime
from decimal import Decimal

class InvoiceModel(BaseModel):
    invoice_id: str
    amount: Decimal
    created_at: datetime
    tags: list[str] = []

    # Customize how datetime serializes
    @field_serializer("created_at")
    def serialize_dt(self, v: datetime) -> str:
        return v.strftime("%d %b %Y, %H:%M")

    # Customize Decimal → float
    @field_serializer("amount")
    def serialize_amount(self, v: Decimal) -> float:
        return float(v)

    # Customize list → comma string
    @field_serializer("tags")
    def serialize_tags(self, v: list[str]) -> str:
        return ", ".join(v)


invoice = InvoiceModel(
    invoice_id="INV-001",
    amount=Decimal("1299.50"),
    created_at=datetime.now(),
    tags=["urgent", "b2b", "gst"]
)

print(invoice.model_dump())
# amount: 1299.5 (float, not Decimal)
# created_at: "21 May 2026, 14:30"
# tags: "urgent, b2b, gst"

print(invoice.model_dump_json())  # JSON string with same customizations
```

---

## 2.7 TypeAdapter — Validate Without BaseModel

```python
from pydantic import TypeAdapter
from typing import list

# Simple types validate karo
int_adapter = TypeAdapter(int)
print(int_adapter.validate_python("42"))   # 42
print(int_adapter.validate_python(3.7))   # 3 (truncated)

# List validate karo
list_adapter = TypeAdapter(list[int])
print(list_adapter.validate_python(["1", "2", "3"]))  # [1, 2, 3]

# Dict validate karo
dict_adapter = TypeAdapter(dict[str, float])
print(dict_adapter.validate_python({"a": "1.5", "b": 2}))  # {"a": 1.5, "b": 2.0}

# JSON string directly validate karo
print(list_adapter.validate_json("[1, 2, 3]"))  # [1, 2, 3]

# Generate JSON schema
print(list_adapter.json_schema())
# {"items": {"type": "integer"}, "type": "array"}
```

---

## 2.8 Interview Q&A

**Q1: Pydantic v2 v1 se kyun faster hai?**
> V2 core Rust mein likha hai (pydantic-core package). Validation, coercion, serialization sab Rust level pe hoti hai. Python overhead minimal hai. 10K objects validate karne mein v1 = ~100ms, v2 = ~10ms. FastAPI ke liye huge difference — har request pe validation hoti hai.

**Q2: `field_validator` mode="before" vs mode="after" — kab kya use karein?**
> `mode="before"`: raw input cleanup karo — string se commas remove karo, trim karo, type convert karo. Input ka type guarantee nahi hoti. `mode="after"`: business logic — typed value milta hai, type guaranteed. Email format check, range validation karo. `mode="wrap"`: advanced — tum khud decide karo call chain aage bhejna hai ya nahi.

**Q3: `computed_field` aur normal `@property` mein fark?**
> Normal `@property` model_dump() aur model_dump_json() mein include nahi hoti — sirf Python access ke liye. `@computed_field` decorator lagao toh automatically serialization mein include hoti hai. Use case: `full_name = first_name + last_name` jo API response mein bhejna ho.

**Q4: `SecretStr` kyu use karein?**
> `SecretStr` value ko `str(obj)` ya `repr(obj)` mein mask karta hai — `SecretStr('**********')` dikhata hai. Logs mein accidentally password/API key print hone se bachata hai. Actual value chahiye toh `.get_secret_value()` explicitly call karo.

**Q5: Discriminated union normal Union se better kyu hai?**
> Normal `Union[A, B, C]`: pydantic teeno models try karta hai ek ek karke — slow aur ambiguous. Discriminated union: `type` field dekh ke direct correct model choose karta hai — O(1) lookup. Error messages bhi clearer hote hain.
