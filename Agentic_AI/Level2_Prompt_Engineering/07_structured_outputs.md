# Level 2 — Doc 7: Structured Outputs

> **Goal:** LLM se **guaranteed structured data** lo. JSON mode, function calling, Pydantic + Instructor — production grade techniques.

---

## 1. Problem: Plain Text Outputs Suck for Code

Imagine you want to extract user info:

```
LLM output:
"Sure! Here's the user info:
Name is John Smith, he's 30 years old. 
You can reach him at john@example.com."
```

Tum kya karoge? **Regex parse** karne ki koshish? `split(",")`? Brittle, breaks easily.

**Solution:** Force LLM to output **structured data** — JSON, validated.

---

## 2. Three Approaches to Structured Outputs

| Approach | Reliability | When to use |
|---|---|---|
| **A. Prompt instruction only** | 70-90% | Quick prototypes |
| **B. JSON mode** | 95% | Production basic |
| **C. Structured outputs / Function calling** | 99%+ | Production critical |
| **D. Pydantic + Instructor** | 99% + validation + retry | **Best practice** |

---

## 3. Approach A: Prompt Instruction (Simplest)

Just tell LLM to output JSON:

```python
prompt = """Extract user info as JSON:
{"name": "string", "age": number, "email": "string"}

Input: "John Smith, 30, john@example.com"

Output (JSON only):"""

response = openai.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": prompt}]
)
# Hope for the best: LLM might add markdown, extra text, etc.
import json
try:
    data = json.loads(response.choices[0].message.content)
except json.JSONDecodeError:
    # Failed — common
    pass
```

**Problem:** ~5-30% of the time, LLM adds preamble ("Here's the JSON:"), markdown fences (```json), or breaks format. Brittle.

---

## 4. Approach B: JSON Mode (OpenAI)

OpenAI's `response_format={"type": "json_object"}` guarantees **valid JSON** (any valid JSON, not specific schema).

```python
response = openai.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": "Output JSON only."},
        {"role": "user", "content": prompt}
    ],
    response_format={"type": "json_object"}  # ← Forces JSON
)
data = json.loads(response.choices[0].message.content)  # Always works
```

**Catch:** JSON valid hoga, but schema match nahi guaranteed. LLM `{"x": 1}` return kar sakta hai jab tumhe `{"name": ..., "age": ...}` chahiye.

---

## 5. Approach C: Structured Outputs (OpenAI's Strict Mode)

**Game changer (2024):** OpenAI ka `response_format={"type": "json_schema", ...}` with `strict: true` — **guaranteed schema match**.

```python
schema = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer"},
        "email": {"type": "string"}
    },
    "required": ["name", "age", "email"],
    "additionalProperties": False
}

response = openai.chat.completions.create(
    model="gpt-4o-2024-08-06",  # Need new enough model
    messages=[{"role": "user", "content": "John, 30, john@example.com"}],
    response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "user_info",
            "schema": schema,
            "strict": True
        }
    }
)
# Output is GUARANTEED to match schema. No retries needed.
```

**Anthropic equivalent:** Use tool use with strict schema (covered in Level 4).

---

## 6. Approach D: Pydantic + Instructor (BEST)

**Why everyone loves Instructor:**
- Define Pydantic model → use as response schema
- Automatic validation
- **Retries on validation failure** (huge win)
- Works with OpenAI, Anthropic, Gemini, local models

```python
import instructor
from openai import OpenAI
from pydantic import BaseModel, Field

class UserInfo(BaseModel):
    name: str
    age: int = Field(ge=0, le=150)
    email: str = Field(pattern=r"^\S+@\S+\.\S+$")

client = instructor.from_openai(OpenAI())

user = client.chat.completions.create(
    model="gpt-4o-mini",
    response_model=UserInfo,
    messages=[{"role": "user", "content": "John Smith, 30, john@example.com"}],
    max_retries=3  # ← Retry if validation fails
)

print(user.name)   # John Smith (typed!)
print(user.age)    # 30 (typed as int!)
print(user.email)  # validated email
```

**What Instructor does behind the scenes:**
1. Converts Pydantic model → JSON schema
2. Calls LLM with structured output mode
3. Parses response → Pydantic instance
4. **If validation fails** (e.g., age=200, email malformed):
   - Retries with the validation error in prompt
   - LLM corrects itself
5. Returns typed Python object

---

## 7. Complex Schemas (Nested, Lists)

```python
from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum

class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class Task(BaseModel):
    title: str
    priority: Priority
    due_date: Optional[str] = None
    assignees: List[str] = Field(default_factory=list)

class Project(BaseModel):
    name: str
    description: str
    tasks: List[Task]
    
client.chat.completions.create(
    model="gpt-4o-mini",
    response_model=Project,
    messages=[{"role": "user", "content": """
        Project 'Website Redesign':
        - Design mockups (high, due 2024-12-01, John, Sarah)
        - Implement backend (medium, due 2024-12-15, Mike)
        - QA testing (low, due 2024-12-20, team)
    """}]
)
```

LLM extracts and returns:
```python
Project(
    name='Website Redesign',
    description='...',
    tasks=[
        Task(title='Design mockups', priority='high', due_date='2024-12-01', assignees=['John', 'Sarah']),
        Task(title='Implement backend', priority='medium', due_date='2024-12-15', assignees=['Mike']),
        Task(title='QA testing', priority='low', due_date='2024-12-20', assignees=['team']),
    ]
)
```

---

## 8. Field Descriptions Guide the LLM

Pydantic `Field` descriptions become part of the schema sent to LLM:

```python
class CustomerReview(BaseModel):
    summary: str = Field(description="A 1-2 sentence summary of the review")
    sentiment: str = Field(description="positive, negative, or neutral")
    rating: int = Field(ge=1, le=5, description="Star rating 1-5")
    issues: List[str] = Field(description="Specific problems mentioned (empty list if none)")
    
client.chat.completions.create(
    model="gpt-4o-mini",
    response_model=CustomerReview,
    messages=[{"role": "user", "content": "I waited 2 hours for delivery. The food was cold and the chicken was undercooked. 1 star."}]
)
```

The `description=...` text guides what each field should contain.

---

## 9. Streaming Structured Outputs

For long outputs, you can stream **partial** structured data:

```python
client.chat.completions.create(
    model="gpt-4o-mini",
    response_model=instructor.Partial[Project],  # ← Partial!
    stream=True,
    messages=[...]
)

# As stream comes in, you get progressively more complete object:
# Iteration 1: Project(name="Web", description=None, tasks=[])
# Iteration 2: Project(name="Website", description=None, tasks=[])
# Iteration 3: Project(name="Website Redesign", description="...", tasks=[Task(...)])
# ...
```

Great for UIs showing progressive updates.

---

## 10. Validation Patterns

### Pattern 1: Validate ranges
```python
age: int = Field(ge=0, le=150)
score: float = Field(ge=0.0, le=1.0)
```

### Pattern 2: Validate enums
```python
class Status(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

status: Status  # LLM MUST output one of these
```

### Pattern 3: Validate patterns
```python
email: str = Field(pattern=r"^\S+@\S+\.\S+$")
phone: str = Field(pattern=r"^\+?\d{10,15}$")
```

### Pattern 4: Custom validators
```python
from pydantic import field_validator

class Order(BaseModel):
    total: float
    items_count: int
    
    @field_validator('total')
    def total_positive(cls, v):
        if v < 0:
            raise ValueError("Total can't be negative")
        return v
```

When LLM violates these, Instructor catches the error and **retries** with the message included.

---

## 11. Production Patterns

### Pattern A: Validate then process
```python
def extract_invoice(text: str) -> Invoice | None:
    try:
        return client.chat.completions.create(
            response_model=Invoice,
            max_retries=3,
            messages=[{"role": "user", "content": text}]
        )
    except ValidationError as e:
        logger.error(f"Failed after retries: {e}")
        return None
```

### Pattern B: Fallback to simpler schema
```python
def extract_robust(text):
    try:
        return extract_detailed_invoice(text)
    except:
        return extract_minimal_invoice(text)  # Simpler, more lenient
```

### Pattern C: Multi-step extraction
For complex docs, extract in steps:
```python
# Step 1: Classify document type
doc_type = extract_doc_type(text)

# Step 2: Use schema for that type
if doc_type == "invoice":
    return extract_invoice(text)
elif doc_type == "receipt":
    return extract_receipt(text)
```

---

## 12. Anti-Patterns

### ❌ Too-Strict Schema for Variable Data
```python
class Address(BaseModel):
    street: str  # ← required
    city: str
    state: str   # ← but US-only, fails for India
    zipcode: str
```
**Fix:** Make optional or use union types for international.

### ❌ Forcing Numeric When Often Missing
```python
class Phone(BaseModel):
    number: int  # ← Strict int → fails for "+1-555-1234"
```
**Fix:** Use `str` with pattern validation.

### ❌ Ignoring Retries
```python
# Bad — no retries, fails 5% of time
response = client.chat.completions.create(...)

# Good — retries on failure
response = client.chat.completions.create(..., max_retries=3)
```

---

## 13. Cost Considerations

- Structured outputs add slightly more cost (schema in prompt)
- Validation retries = N× LLM calls if fails
- **Trade-off:** More cost vs more reliability

**Recommendation:** Always use structured outputs in production. Cost increase << reliability gain.

---

## 14. Interview Questions

1. **Q: Why use Instructor over raw JSON mode?**
   - Pydantic validation + automatic retries on failure. Type-safe Python objects.

2. **Q: What's the difference between JSON mode and structured outputs?**
   - JSON mode: any valid JSON. Structured outputs: must match schema (strict).

3. **Q: When does structured output fail?**
   - Schema too strict for input data, conflicting constraints, model not new enough.

4. **Q: How does Instructor retry?**
   - Re-prompts with validation error message → LLM corrects itself.

---

## 15. Exercises

1. **Easy:** Define Pydantic model for "Recipe" — name, ingredients (list of strings), steps. Extract from text.
2. **Medium:** Build complex nested schema (Company → Departments → Employees → Skills).
3. **Hard:** Robust invoice extractor — handle 5 different invoice formats with fallback chain.
4. **Pro:** Streaming structured output for a long-form report. Progressively show sections as they generate.

---

## 16. Key Takeaways

✅ Structured outputs = guaranteed schema, no regex parsing
✅ **4 approaches:** prompt, JSON mode, structured outputs (strict), Pydantic + Instructor
✅ **Instructor + Pydantic** = best practice (validation + retries + typed objects)
✅ Use `Field(description=...)` to guide LLM
✅ Combine with enums, patterns, custom validators for strict types
✅ Streaming partial structured outputs for long generations
✅ Always set `max_retries=3` in production

**Next:** [08_prompt_templates.md](08_prompt_templates.md) — Prompt templates and versioning
