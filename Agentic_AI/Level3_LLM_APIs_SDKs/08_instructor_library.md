# Instructor Library — Structured LLM Outputs with Pydantic

## Quick Concepts
- **Instructor** = LLM se directly Pydantic objects lo — JSON parse manually nahi karna
- **Retry on validation** = validation fail ho toh automatically LLM se retry karo
- **Partial streaming** = incomplete Pydantic object stream karo
- Works with OpenAI, Claude, Gemini, Mistral, Groq — sab ke saath

---

## Andar kya hota hai — Yehi PydanticAI Wala Validate-Retry Loop Hai, Client-Patch Ki Tarah

### `instructor.from_openai(client)` — client ko PATCH karta hai

```python
client = instructor.from_openai(OpenAI())
user = client.chat.completions.create(
    model="gpt-4o", response_model=User, messages=[...]
)
```

Yeh naya client type NAHI hai — `instructor` tumhare EXISTING client object ko
patch karta hai taaki `response_model=` ek naya accepted parameter ban jaaye.
Andar se:

```
1. User (Pydantic model) ki JSON schema nikalta hai (model_json_schema())
2. Us schema ko ya to provider ke NATIVE structured-output param se, ya
   ek forced function-calling TOOL definition se model ko bhejta hai
   (provider capability ke hisaab se dono raaste hain)
3. Model ka response leta hai, User.model_validate_json() try karta hai
4. VALIDATION FAIL → automatically ek NAYA message turn banata hai:
   "yeh tumhara output tha, yeh validation error hai, fix karo" —
   model ko WAPAS bhejta hai, max_retries tak
5. VALIDATION PASS → validated Pydantic instance return
```

Yeh **EXACT wahi validate → fail → auto-retry-with-model loop** hai jo
`08_pydantic_ai.md` mein PydanticAI's `result_retries` ke naam se already
documented hai — bas yahan ek agent-framework ke andar nahi, ek CLIENT-PATCHING
decorator ki tarah implement hua hai. Concept identical, delivery mechanism
alag.

### Partial streaming — incomplete JSON ko PARTIAL object mein parse karna

`Partial[User]` mode mein instructor ek lenient JSON parser use karta hai jo
TRUNCATED/incomplete JSON string ko bhi parse kar sakta hai (missing closing
braces tolerate karta hai) — har naye stream chunk ke saath yeh partial
parse dobara chalta hai, Pydantic model ke fields jo abhi complete nahi hue
unhe `Optional`/`None` treat karke ek PROGRESSIVELY-FILLING object return
karta hai — UI mein "typing" jaisa live-update effect isi se milta hai.

---

## Interview Questions & Answers

### Q1: Instructor kya hai? Basic usage?
**Answer:**
```python
# pip install instructor

import instructor
import anthropic
import openai
from pydantic import BaseModel, Field
from typing import Optional

# OpenAI ke saath
oai_client = instructor.from_openai(openai.OpenAI())

# Claude ke saath
ant_client = instructor.from_anthropic(anthropic.Anthropic())

# Basic extraction
class UserInfo(BaseModel):
    name: str
    age: int
    email: Optional[str] = None
    occupation: str

# OpenAI
user = oai_client.chat.completions.create(
    model="gpt-4o-mini",
    response_model=UserInfo,    # magic — directly Pydantic object milega
    messages=[{
        "role": "user",
        "content": "Ashish is a 28 year old Python developer at YAM. Email: ashish@yam.com"
    }]
)

print(type(user))    # <class 'UserInfo'> — not string!
print(user.name)     # "Ashish"
print(user.age)      # 28
print(user.email)    # "ashish@yam.com"

# Claude ke saath
user = ant_client.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=1024,
    response_model=UserInfo,
    messages=[{
        "role": "user",
        "content": "Extract info: Priya is 25, software engineer, priya@tech.com"
    }]
)
```

---

### Q2: Complex nested models kaise extract karte hain?
**Answer:**
```python
from pydantic import BaseModel, Field, validator
from typing import Optional, Literal
from enum import Enum

class Address(BaseModel):
    street: str
    city: str
    state: str
    pincode: str

class ContactInfo(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin: Optional[str] = None

class JobExperience(BaseModel):
    company: str
    role: str
    years: float
    skills: list[str]

class CandidateProfile(BaseModel):
    name: str
    age: Optional[int] = None
    address: Optional[Address] = None
    contact: ContactInfo
    experience: list[JobExperience]
    total_experience_years: float
    skills: list[str]
    salary_expectation: Optional[int] = Field(None, description="In LPA")
    ready_to_relocate: bool

# Extract from resume text
resume_text = """
Name: Ashish Kumar Chaurasiya
Age: 28
Address: 123 MG Road, Mumbai, Maharashtra - 400001
Email: ashish@email.com, Phone: 9876543210

Experience:
- YAM Industries (2021-Present): Python Backend Developer, 3 years
  Skills: FastAPI, Django, PostgreSQL, Redis, Docker

- TechCorp (2019-2021): Junior Developer, 2 years
  Skills: Python, Django, MySQL

Total: 5 years experience
Salary: 15 LPA expected
Open to relocation: Yes
"""

profile = ant_client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=2000,
    response_model=CandidateProfile,
    messages=[
        {"role": "user", "content": f"Extract complete candidate profile:\n\n{resume_text}"}
    ]
)

print(f"Name: {profile.name}")
print(f"Experience: {profile.total_experience_years} years")
print(f"Skills: {', '.join(profile.skills)}")
for exp in profile.experience:
    print(f"  {exp.company}: {exp.role} ({exp.years}y)")
```

---

### Q3: Validation aur retry logic kaise kaam karta hai?
**Answer:**
```python
from pydantic import BaseModel, field_validator, model_validator
import instructor

client = instructor.from_anthropic(anthropic.Anthropic(), max_retries=3)

class ProductReview(BaseModel):
    product_name: str
    rating: int = Field(ge=1, le=5, description="1-5 rating")
    sentiment: Literal["positive", "negative", "neutral", "mixed"]
    pros: list[str] = Field(min_length=1, max_length=5)
    cons: list[str] = Field(max_length=5)
    would_recommend: bool
    summary: str = Field(min_length=20, max_length=200)

    @field_validator("product_name")
    @classmethod
    def product_name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Product name cannot be empty")
        return v.strip()

    @model_validator(mode="after")
    def validate_consistency(self) -> "ProductReview":
        if self.rating >= 4 and self.sentiment == "negative":
            raise ValueError("High rating should not have negative sentiment")
        if self.rating <= 2 and self.sentiment == "positive":
            raise ValueError("Low rating should not have positive sentiment")
        return self

# Instructor automatically retries when validation fails!
# Retry message: "Validation failed: High rating should not have negative sentiment.
#                Please fix and return valid JSON."

review_text = """
The laptop is excellent! Fast processor, great display. Battery could be better.
Rating: 4.5/5. I recommend it.
"""

review = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1000,
    response_model=ProductReview,
    messages=[{
        "role": "user",
        "content": f"Extract structured review:\n\n{review_text}"
    }]
)

print(f"Rating: {review.rating}/5")
print(f"Sentiment: {review.sentiment}")
print(f"Pros: {review.pros}")
print(f"Recommend: {review.would_recommend}")
```

---

### Q4: Partial streaming — large objects stream kaise karte hain?
**Answer:**
```python
import instructor
from instructor import Partial
from pydantic import BaseModel

client = instructor.from_openai(openai.OpenAI())

class BlogPost(BaseModel):
    title: str
    introduction: str
    sections: list[str]
    conclusion: str
    tags: list[str]
    estimated_read_time: int

# Stream partial object — as sections complete hoti hain
for partial_post in client.chat.completions.create_partial(
    model="gpt-4o",
    response_model=BlogPost,
    messages=[{
        "role": "user",
        "content": "Write a blog post about FastAPI async programming"
    }],
    stream=True,
):
    # partial_post mein jo complete hua woh available hai
    if partial_post.title:
        print(f"Title: {partial_post.title}")
    if partial_post.introduction:
        print(f"Intro written ({len(partial_post.introduction)} chars)")
    if partial_post.sections:
        print(f"Sections so far: {len(partial_post.sections)}")

# Final complete object
print(f"\nFinal post: {partial_post.title}")
print(f"Sections: {len(partial_post.sections)}")
```

---

### Q5: Multiple extractions aur classification?
**Answer:**
```python
from typing import Union
import instructor

client = instructor.from_openai(openai.OpenAI())

# Classification
class ClassificationResult(BaseModel):
    category: Literal["technical", "billing", "general", "complaint", "feature_request"]
    priority: Literal["low", "medium", "high", "urgent"]
    sentiment: Literal["positive", "negative", "neutral"]
    requires_human: bool
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str

def classify_support_ticket(ticket: str) -> ClassificationResult:
    return client.chat.completions.create(
        model="gpt-4o-mini",   # classification ke liye mini enough
        response_model=ClassificationResult,
        messages=[
            {"role": "system", "content": "Classify this customer support ticket accurately."},
            {"role": "user", "content": ticket}
        ]
    )

# Batch extraction
def extract_multiple(texts: list[str]) -> list[UserInfo]:
    results = []
    for text in texts:
        result = oai_client.chat.completions.create(
            model="gpt-4o-mini",
            response_model=UserInfo,
            messages=[{"role": "user", "content": text}]
        )
        results.append(result)
    return results

# Union types — multiple possible outputs
class SuccessResponse(BaseModel):
    data: dict
    message: str

class ErrorResponse(BaseModel):
    error_code: str
    description: str

# Instructor handles Union intelligently
response = client.chat.completions.create(
    model="gpt-4o",
    response_model=Union[SuccessResponse, ErrorResponse],
    messages=[{"role": "user", "content": "Process: order_id=123"}]
)

if isinstance(response, SuccessResponse):
    print(f"Success: {response.data}")
else:
    print(f"Error: {response.error_code}")
```

---

### Q6: Instructor vs raw JSON parsing — kya fark hai?
**Answer:**
```python
# WITHOUT Instructor — manual, brittle
import json

def extract_without_instructor(text: str) -> dict:
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Return JSON with name and age"},
            {"role": "user", "content": text}
        ],
        response_format={"type": "json_object"}
    )
    raw = response.choices[0].message.content
    try:
        data = json.loads(raw)
        # Manual validation
        if "name" not in data:
            raise ValueError("Missing name")
        if not isinstance(data.get("age"), int):
            raise ValueError("Age must be int")
        return data
    except (json.JSONDecodeError, ValueError) as e:
        # No automatic retry!
        raise

# WITH Instructor — clean, reliable, auto-retry
def extract_with_instructor(text: str) -> UserInfo:
    return oai_client.chat.completions.create(
        model="gpt-4o",
        response_model=UserInfo,
        messages=[{"role": "user", "content": text}]
    )
    # Auto validation, auto retry, Pydantic object directly!

# Comparison:
# Manual: 20+ lines, fragile, no retry, string parsing
# Instructor: 5 lines, robust, auto-retry, typed object
```
