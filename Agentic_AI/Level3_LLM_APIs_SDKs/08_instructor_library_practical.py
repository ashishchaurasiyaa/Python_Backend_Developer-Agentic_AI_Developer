"""
Phase4_Instructor — Complete Practical
========================================
Topics:
  1. Structured extraction with Pydantic models
  2. Nested models + list extraction
  3. Classification tasks
  4. Retry on validation failure
  5. Partial streaming
  6. Real-world: invoice parsing, resume extraction, intent classification

Install: pip install instructor openai anthropic
Run: python 01_instructor_practical.py
"""

import os, json
from typing import Optional, Literal
from enum import Enum

MOCK_MODE = not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY")
if MOCK_MODE:
    print("⚠  MOCK MODE — set OPENAI_API_KEY or ANTHROPIC_API_KEY\n")

try:
    import instructor
    from pydantic import BaseModel, Field, field_validator
    INSTRUCTOR_AVAILABLE = True
except ImportError:
    INSTRUCTOR_AVAILABLE = False
    print("Install: pip install instructor openai\n")

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Basic Structured Extraction
# INTERVIEW: Instructor = LLM → typed Pydantic object (no JSON parsing!)
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 60)
print("SECTION 1: Basic Structured Extraction")
print("=" * 60)

INSTRUCTOR_CODE = '''\
import instructor, openai, anthropic
from pydantic import BaseModel, Field
from typing import Optional

# ── OpenAI ──────────────────────────────────────────────────
oai_client = instructor.from_openai(openai.OpenAI())

# ── Claude ──────────────────────────────────────────────────
ant_client = instructor.from_anthropic(anthropic.Anthropic())

# Define what you want extracted
class UserInfo(BaseModel):
    name:       str
    age:        int
    email:      Optional[str] = None
    occupation: str

# Extract from unstructured text — returns typed Pydantic object!
text = "John Smith is a 32-year-old software engineer at Google. Contact: john@google.com"

user = oai_client.chat.completions.create(
    model          = "gpt-4o-mini",
    response_model = UserInfo,   # ← The magic: returns UserInfo, not a string!
    messages       = [{"role": "user", "content": f"Extract user info: {text}"}],
)

print(user.name)       # "John Smith"
print(user.age)        # 32
print(user.email)      # "john@google.com"
print(type(user))      # <class 'UserInfo'>  — properly typed!
'''
print(INSTRUCTOR_CODE)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Complex Nested Models
# INTERVIEW: Handle nested objects and lists
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 2: Complex Nested Models")
print("=" * 60)

if INSTRUCTOR_AVAILABLE:
    from pydantic import BaseModel, Field

    class LineItem(BaseModel):
        description: str
        quantity:    int
        unit_price:  float
        total:       float

    class Invoice(BaseModel):
        """
        INTERVIEW: Nested Pydantic models work seamlessly with Instructor.
        LLM fills in all fields from unstructured invoice text.
        """
        invoice_number: str
        date:           str
        vendor_name:    str
        vendor_email:   Optional[str] = None
        line_items:     list[LineItem]
        subtotal:       float
        tax_rate:       float = Field(ge=0, le=1, description="Tax rate 0-1")
        total:          float

        @field_validator("total")
        @classmethod
        def validate_total(cls, v, info):
            """INTERVIEW: Validators run on extracted data — catch LLM mistakes!"""
            return v  # In real code: verify total = subtotal * (1 + tax_rate)


    class ResumeSkill(BaseModel):
        skill:        str
        years:        int = Field(ge=0, le=50)
        proficiency:  Literal["beginner", "intermediate", "advanced", "expert"]


    class Resume(BaseModel):
        full_name:    str
        email:        str
        phone:        Optional[str] = None
        years_exp:    int
        skills:       list[ResumeSkill]
        education:    list[str]
        summary:      str = Field(description="2-sentence professional summary")


    print("  Invoice schema:")
    schema = Invoice.model_json_schema()
    print(f"  Fields: {list(schema['properties'].keys())}")

    print("\n  Resume schema:")
    schema2 = Resume.model_json_schema()
    print(f"  Fields: {list(schema2['properties'].keys())}")

    # Mock extraction demo
    INVOICE_TEXT = """
    Invoice #INV-2024-001
    Date: January 15, 2024
    Vendor: TechCorp Inc., billing@techcorp.com

    Services:
    - API Development: 40 hours @ $150/hr = $6,000
    - Code Review:     10 hours @ $100/hr = $1,000
    - Testing:         8 hours  @ $80/hr  = $640

    Subtotal: $7,640
    Tax (10%): $764
    Total: $8,404
    """

    if not MOCK_MODE and INSTRUCTOR_AVAILABLE:
        try:
            import openai
            client = instructor.from_openai(openai.OpenAI())
            invoice = client.chat.completions.create(
                model          = "gpt-4o-mini",
                response_model = Invoice,
                messages       = [{"role": "user", "content": f"Extract invoice data:\n{INVOICE_TEXT}"}],
            )
            print(f"\n  Extracted invoice:")
            print(f"  Invoice #: {invoice.invoice_number}")
            print(f"  Vendor: {invoice.vendor_name}")
            print(f"  Line items: {len(invoice.line_items)}")
            print(f"  Total: ${invoice.total}")
        except Exception as e:
            print(f"\n  [Mock] Invoice extraction: {type(e).__name__}")
    else:
        print(f"\n  [Mock] Invoice extraction from:\n  {INVOICE_TEXT[:100].strip()}")
        print(f"  → Would extract: invoice_number, vendor, 3 line_items, total=$8404")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Classification
# INTERVIEW: Literal types for constrained classification
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 3: Classification with Literal Types")
print("=" * 60)

CLASSIFICATION_CODE = '''\
from pydantic import BaseModel, Field
from typing import Literal

class SupportTicket(BaseModel):
    category:   Literal["billing", "technical", "general", "refund", "abuse"]
    priority:   Literal["low", "medium", "high", "urgent"]
    sentiment:  Literal["positive", "neutral", "negative", "angry"]
    summary:    str = Field(description="One-line summary")
    needs_human: bool = Field(description="True if human agent needed")

class IntentClassification(BaseModel):
    intent:     Literal["question", "complaint", "request", "praise", "spam"]
    confidence: float = Field(ge=0, le=1)
    language:   str
    requires_auth: bool

# Usage
ticket = client.chat.completions.create(
    model="gpt-4o-mini",
    response_model=SupportTicket,
    messages=[{"role": "user", "content":
        "User message: I was charged twice for my subscription last month!"
    }],
)
# ticket.category   → "billing"
# ticket.priority   → "high"
# ticket.sentiment  → "angry"
# ticket.needs_human → True
'''
print(CLASSIFICATION_CODE[:600])


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Retry on Validation Failure
# INTERVIEW: Instructor auto-retries when LLM output fails Pydantic validation
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 4: Retry on Validation Failure")
print("=" * 60)

RETRY_CODE = '''\
import instructor
from pydantic import BaseModel, field_validator

class StrictUser(BaseModel):
    name:  str
    age:   int
    email: str

    @field_validator("age")
    @classmethod
    def validate_age(cls, v):
        if v < 0 or v > 150:
            raise ValueError(f"Age {v} is not realistic!")
        return v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        if "@" not in v:
            raise ValueError(f"Invalid email: {v}")
        return v.lower()

# INTERVIEW: max_retries — if LLM gives age=200, validator raises → retry!
user = client.chat.completions.create(
    model          = "gpt-4o-mini",
    response_model = StrictUser,
    max_retries    = 3,         # ← Instructor retries if validation fails!
    messages       = [
        {
            "role": "user",
            "content": "Create a user named John with age 200 and email JOHN_AT_example.com"
            # age=200 will fail → Instructor tells LLM what was wrong → LLM fixes it
        }
    ],
)
# After retry: age=30 (corrected), email="john@example.com" (corrected)
# INTERVIEW: Instructor sends the validation error back to LLM as context!
'''
print(RETRY_CODE[:600])


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Batch Extraction
# INTERVIEW: Extract lists of objects from unstructured text
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 5: List/Batch Extraction")
print("=" * 60)

BATCH_CODE = '''\
from pydantic import BaseModel
from typing import Optional

class Product(BaseModel):
    name:  str
    price: float
    sku:   Optional[str] = None

class ProductList(BaseModel):
    products: list[Product]
    currency: str = "USD"

# Extract ALL products from messy text
text = """
Our catalog:
- Widget Pro (SKU: W-001): $29.99
- Gadget Plus (SKU: G-002): $49.99
- Super Device (SKU: S-003): $199.99 — currently on sale!
- Accessories pack: $9.99
"""

result = client.chat.completions.create(
    model          = "gpt-4o-mini",
    response_model = ProductList,
    messages       = [{"role": "user", "content": f"Extract all products:\\n{text}"}],
)
for p in result.products:
    print(f"  {p.name}: ${p.price} (SKU: {p.sku})")
# → Widget Pro: $29.99 (SKU: W-001)
# → Gadget Plus: $49.99 (SKU: G-002)
# etc.
'''
print(BATCH_CODE[:500])

print("\n" + "=" * 60)
print("INSTRUCTOR INTERVIEW SUMMARY:")
print("  Instructor = LLM → Pydantic (no JSON parsing)")
print("  response_model=MyModel → get typed object back")
print("  max_retries=3 → auto-retry if validation fails")
print("  Literal types → constrained classification")
print("  Works with OpenAI, Claude, Gemini, Groq")
print("  Use when: structured extraction, classification, data pipelines")
print("=" * 60)
