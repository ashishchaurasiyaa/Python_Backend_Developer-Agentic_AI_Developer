"""
FastAPI Lab 06 — Pydantic v2 Validators
============================================================
ARCHITECTURE — Pydantic v2 Validation Pipeline:

    INPUT DATA (dict / ORM / JSON)
           │
           ▼
    ┌─────────────────────────────────────────────────────┐
    │  field_validator(mode='before')   ← runs FIRST      │
    │    Transforms raw input before type coercion        │
    │    e.g. "  hello  ".strip()  →  "hello"             │
    ├─────────────────────────────────────────────────────┤
    │  Type coercion + built-in constraints               │
    │    str, int, EmailStr, min_length, ge/le ...        │
    ├─────────────────────────────────────────────────────┤
    │  field_validator(mode='after')    ← runs AFTER      │
    │    Validates already-coerced value                  │
    │    e.g. check username not a reserved word          │
    ├─────────────────────────────────────────────────────┤
    │  model_validator(mode='before')   ← whole dict      │
    │    Runs before ANY field processing                 │
    │    e.g. decrypt an envelope, restructure keys       │
    ├─────────────────────────────────────────────────────┤
    │  model_validator(mode='after')    ← whole model     │
    │    Cross-field validation: password == confirm      │
    └─────────────────────────────────────────────────────┘
           │
           ▼
    VALIDATED MODEL INSTANCE

KEY CONCEPTS:
  field_validator   — per-field transform/validate; decorator on classmethods
  model_validator   — whole-model; receives dict (before) or self (after)
  ConfigDict        — replaces class Config; controls strict, from_attributes, etc.
  computed_field    — read-only property included in model.model_dump()
  Annotated         — attach validators/metadata to a type without subclassing
  strict=True       — int("5") raises ValidationError (no implicit coercion)

INTERVIEW ANSWER:
  "Pydantic v2 mein field_validator mode='before' raw dict value ko type
   conversion se PEHLE transform karta hai — strip whitespace, lowercase email.
   mode='after' already-coerced value pe business rules check karta hai.
   model_validator(mode='after') cross-field checks ke liye hai — jaise
   password == confirm_password. ConfigDict(strict=True) mein '42' → int
   fail ho jaata hai, implicit coercion band ho jaati hai."

TASK:
  1. TODO 1: UserCreateRequest — field_validator on email (lowercase + strip),
             field_validator on username (strip, check not in RESERVED_WORDS),
             model_validator(mode='after') — confirm password match
  2. TODO 2: ProductSchema — ConfigDict(strict=True, from_attributes=True),
             computed_field for discounted_price
  3. TODO 3: CustomTypes — Annotated + BeforeValidator for PositiveStrippedStr,
             use it in AddressSchema
  4. Run: python 06_pydantic_v2_validators.py

Prereq: pip install fastapi httpx pydantic[email]
"""

from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import FastAPI, status
from httpx import ASGITransport, AsyncClient
from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    ValidationError,
    computed_field,
    field_validator,
    model_validator,
)
from pydantic.functional_validators import BeforeValidator

app = FastAPI(title="Lab 06 — Pydantic v2 Validators")

RESERVED_WORDS = {"admin", "root", "system", "superuser"}


# ════════════════════════════════════════════════════════════════════════════
# TODO 1 — UserCreateRequest: field validators + cross-field model validator
# ════════════════════════════════════════════════════════════════════════════
"""
Implement UserCreateRequest(BaseModel):

  Fields:
    email:            EmailStr
    username:         str  (min_length=3, max_length=30)
    password:         str  (min_length=8)
    confirm_password: str

  field_validator('email', mode='before'):
    → strip whitespace, lowercase
    → return cleaned value

  field_validator('username', mode='after'):
    → strip whitespace (already done by 'before' + coercion, but double-check)
    → raise ValueError if username.lower() in RESERVED_WORDS
    → return value

  model_validator(mode='after'):
    → if self.password != self.confirm_password: raise ValueError
    → return self

  Hint:
    @field_validator('email', mode='before')
    @classmethod
    def clean_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator('username', mode='after')
    @classmethod
    def check_username(cls, v: str) -> str:
        if v.lower() in RESERVED_WORDS:
            raise ValueError(f"'{v}' is a reserved username")
        return v

    @model_validator(mode='after')
    def passwords_match(self) -> 'UserCreateRequest':
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self
"""

class UserCreateRequest(BaseModel):
    email: EmailStr
    username: str
    password: str
    confirm_password: str

    # TODO 1a: field_validator on 'email' mode='before' — strip + lowercase
    # TODO 1b: field_validator on 'username' mode='after' — check RESERVED_WORDS
    # TODO 1c: model_validator mode='after' — password == confirm_password


@app.post("/users/", status_code=status.HTTP_201_CREATED)
async def create_user(body: UserCreateRequest):
    return {"email": body.email, "username": body.username}


# ════════════════════════════════════════════════════════════════════════════
# TODO 2 — ProductSchema: ConfigDict(strict=True) + computed_field
# ════════════════════════════════════════════════════════════════════════════
"""
Implement ProductSchema(BaseModel):

  ConfigDict:
    strict=True          ← "10" passed as price should FAIL (no str→float coercion)
    from_attributes=True ← can construct from ORM object (model.id etc.)

  Fields:
    id:             int
    name:           str
    price:          float  (must be > 0, use gt=0 in Field())
    discount_pct:   float  (default=0.0, must be 0.0–1.0, ge=0, le=1)

  computed_field:
    discounted_price: float
      → price * (1 - discount_pct)
      → round to 2 decimal places

  Hint:
    model_config = ConfigDict(strict=True, from_attributes=True)

    @computed_field
    @property
    def discounted_price(self) -> float:
        return round(self.price * (1 - self.discount_pct), 2)
"""

class ProductSchema(BaseModel):
    id: int
    name: str
    price: float
    discount_pct: float = 0.0

    # TODO 2a: add model_config = ConfigDict(strict=True, from_attributes=True)
    # TODO 2b: add @computed_field discounted_price property


@app.post("/products/")
async def create_product(body: ProductSchema):
    return body.model_dump()


# ════════════════════════════════════════════════════════════════════════════
# TODO 3 — Annotated custom type: PositiveStrippedStr
# ════════════════════════════════════════════════════════════════════════════
"""
Implement a custom Annotated type: PositiveStrippedStr

  It should:
    1. Strip leading/trailing whitespace from input (use BeforeValidator)
    2. Raise ValueError if the result is empty string

  Usage:
    PositiveStrippedStr = Annotated[str, BeforeValidator(lambda v: ...)]

  Then define AddressSchema(BaseModel):
    street:  PositiveStrippedStr
    city:    PositiveStrippedStr
    country: PositiveStrippedStr

  Hint:
    def _strip_and_check(v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Field cannot be empty or whitespace-only")
        return v

    PositiveStrippedStr = Annotated[str, BeforeValidator(_strip_and_check)]
"""

# TODO 3a: define _strip_and_check function
# TODO 3b: define PositiveStrippedStr = Annotated[str, BeforeValidator(...)]
# TODO 3c: define AddressSchema with street, city, country as PositiveStrippedStr

# Placeholder so the lab file loads before TODO 3 is complete
class AddressSchema(BaseModel):
    street: str
    city: str
    country: str


@app.post("/addresses/")
async def create_address(body: AddressSchema):
    return body.model_dump()


# ════════════════════════════════════════════════════════════════════════════
# TESTS
# ════════════════════════════════════════════════════════════════════════════

async def run_tests():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        passed = 0
        failed = 0

        # ── TODO 1 tests ──────────────────────────────────────────────────

        print("\n── TODO 1: UserCreateRequest validators ──")

        # 1a. Valid user — email whitespace + uppercase trimmed
        resp = await client.post("/users/", json={
            "email": "  Alice@Example.COM  ",
            "username": "alice99",
            "password": "secret123",
            "confirm_password": "secret123",
        })
        if resp.status_code == 201 and resp.json()["email"] == "alice@example.com":
            print("✅ 1a. email stripped + lowercased")
            passed += 1
        else:
            print(f"❌ 1a. FAIL: email should be 'alice@example.com'. Got: {resp.json()}")
            failed += 1

        # 1b. Reserved username → 422
        resp = await client.post("/users/", json={
            "email": "admin@test.com",
            "username": "admin",
            "password": "secret123",
            "confirm_password": "secret123",
        })
        if resp.status_code == 422:
            print("✅ 1b. 'admin' username rejected with 422")
            passed += 1
        else:
            print(f"❌ 1b. FAIL: 'admin' username should return 422. Got {resp.status_code}")
            failed += 1

        # 1c. Password mismatch → 422
        resp = await client.post("/users/", json={
            "email": "bob@test.com",
            "username": "bobsmith",
            "password": "secret123",
            "confirm_password": "different456",
        })
        if resp.status_code == 422:
            print("✅ 1c. password mismatch rejected with 422")
            passed += 1
        else:
            print(f"❌ 1c. FAIL: password mismatch should return 422. Got {resp.status_code}")
            failed += 1

        # 1d. Invalid email → 422
        resp = await client.post("/users/", json={
            "email": "not-an-email",
            "username": "bobsmith",
            "password": "secret123",
            "confirm_password": "secret123",
        })
        if resp.status_code == 422:
            print("✅ 1d. invalid email rejected with 422")
            passed += 1
        else:
            print(f"❌ 1d. FAIL: invalid email should return 422. Got {resp.status_code}")
            failed += 1

        # ── TODO 2 tests ──────────────────────────────────────────────────

        print("\n── TODO 2: ProductSchema — strict + computed_field ──")

        # 2a. Valid product — computed discounted_price present
        resp = await client.post("/products/", json={
            "id": 1, "name": "Widget", "price": 100.0, "discount_pct": 0.2
        })
        body = resp.json()
        if resp.status_code == 200 and "discounted_price" in body:
            price = body["discounted_price"]
            if abs(price - 80.0) < 0.01:
                print("✅ 2a. computed_field discounted_price = 80.0")
                passed += 1
            else:
                print(f"❌ 2a. FAIL: discounted_price should be 80.0. Got {price}")
                failed += 1
        else:
            print(f"❌ 2a. FAIL: 'discounted_price' not in response. Got: {body}")
            failed += 1

        # 2b. strict=True — price as string "100" should fail
        try:
            ProductSchema(id=1, name="Widget", price="100", discount_pct=0.0)  # type: ignore
            print("❌ 2b. FAIL: strict=True should reject price='100' (str → float coercion)")
            failed += 1
        except ValidationError:
            print("✅ 2b. strict=True: price='100' (string) raises ValidationError")
            passed += 1

        # 2c. from_attributes=True — construct from ORM-like object
        class FakeProductORM:
            id = 5
            name = "ORM Product"
            price = 49.99
            discount_pct = 0.1

        try:
            p = ProductSchema.model_validate(FakeProductORM(), from_attributes=True)
            if abs(p.discounted_price - 44.99) < 0.01:
                print(f"✅ 2c. from_attributes=True + discounted_price={p.discounted_price}")
                passed += 1
            else:
                print(f"❌ 2c. FAIL: discounted_price should be 44.99. Got {p.discounted_price}")
                failed += 1
        except Exception as e:
            print(f"❌ 2c. FAIL: from_attributes validation failed: {e}")
            failed += 1

        # ── TODO 3 tests ──────────────────────────────────────────────────

        print("\n── TODO 3: PositiveStrippedStr Annotated type ──")

        # 3a. Leading/trailing whitespace stripped
        resp = await client.post("/addresses/", json={
            "street": "  123 Main St  ",
            "city": "  London  ",
            "country": "  UK  ",
        })
        body = resp.json()
        if resp.status_code == 200 and body.get("street") == "123 Main St":
            print("✅ 3a. whitespace stripped from PositiveStrippedStr fields")
            passed += 1
        else:
            print(f"❌ 3a. FAIL: street should be '123 Main St'. Got: {body}")
            failed += 1

        # 3b. Whitespace-only string → 422
        resp = await client.post("/addresses/", json={
            "street": "   ",
            "city": "London",
            "country": "UK",
        })
        if resp.status_code == 422:
            print("✅ 3b. whitespace-only street rejected with 422")
            passed += 1
        else:
            print(f"❌ 3b. FAIL: whitespace-only should return 422. Got {resp.status_code}: {resp.json()}")
            failed += 1

        # ── Summary ───────────────────────────────────────────────────────
        print(f"\n{'═'*50}")
        print(f"  {passed} passed  |  {failed} failed")
        if failed == 0:
            print("  ✅ ALL PASS — Lab 06 complete!")
        else:
            print("  ❌ Fix the failing TODOs above and rerun.")
        print('═'*50)


# ════════════════════════════════════════════════════════════════════════════
# SOCH (Answer ALOUD before moving to Lab 07)
# ════════════════════════════════════════════════════════════════════════════
"""
SOCH:

Q1: field_validator mode='before' aur mode='after' mein kya fark hai?
    Kab 'before' use karna chahiye aur kab 'after'?

Q2: model_validator(mode='after') kyon use kiya password match ke liye?
    Kya hoga agar field_validator se karna chahen password match?

Q3: ConfigDict(strict=True) production mein kab use karna chahiye?
    Kya side effects ho sakte hain agar strict=True suddenly lagao?

Q4: computed_field aur regular @property mein kya fark hai?
    model_dump() mein computed_field kyun include hota hai, property nahi?

Q5: Annotated type aur field_validator mein kya fark hai?
    Kab Annotated type banana better decision hai?
"""

if __name__ == "__main__":
    asyncio.run(run_tests())
