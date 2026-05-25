"""
Level 2 — Doc 7: Structured Outputs (PRACTICAL)
================================================
Topics:
  1. Prompt-only JSON (unreliable)
  2. OpenAI JSON mode
  3. OpenAI structured outputs (strict schema)
  4. Instructor + Pydantic (best)
  5. Complex nested schemas
  6. Validation with custom validators
  7. Retry on validation failure

Install: pip install openai instructor pydantic python-dotenv
Run: python 07_structured_outputs_practical.py
"""

import os
import json
from typing import List, Optional
from enum import Enum
from dotenv import load_dotenv

load_dotenv()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Approach A — Prompt Only (Brittle)
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 1: Prompt-Only JSON (Brittle)")
print("=" * 70)


def prompt_only_json(text: str) -> dict:
    """Just ask for JSON in prompt — unreliable."""
    if not os.getenv("OPENAI_API_KEY"):
        return {"error": "no_api_key"}
    from openai import OpenAI
    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "user",
            "content": f'Extract: name, age, email from "{text}". Output JSON only.'
        }]
    )
    raw = response.choices[0].message.content
    try:
        return {"ok": True, "data": json.loads(raw), "raw": raw}
    except json.JSONDecodeError as e:
        return {"ok": False, "error": str(e), "raw": raw}


print("[1.1 Try parsing prompt-only]")
print(prompt_only_json("John Smith, 30, john@example.com"))


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Approach B — OpenAI JSON Mode
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 2: OpenAI JSON Mode (Valid JSON Guaranteed)")
print("=" * 70)


def openai_json_mode(text: str) -> dict:
    if not os.getenv("OPENAI_API_KEY"):
        return {"error": "no_api_key"}
    from openai import OpenAI
    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Output JSON only with keys: name, age, email."},
            {"role": "user", "content": text}
        ],
        response_format={"type": "json_object"}  # ← Forces JSON
    )
    return json.loads(response.choices[0].message.content)


print("[2.1 JSON mode result]")
print(openai_json_mode("John Smith, 30 years old, contact: john@example.com"))


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Approach C — Strict Structured Outputs
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 3: Strict Structured Outputs (Schema Guaranteed)")
print("=" * 70)


def openai_strict_schema(text: str) -> dict:
    if not os.getenv("OPENAI_API_KEY"):
        return {"error": "no_api_key"}
    from openai import OpenAI
    client = OpenAI()
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
    response = client.chat.completions.create(
        model="gpt-4o-2024-08-06",  # Need new model for strict mode
        messages=[{"role": "user", "content": text}],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "user_info",
                "schema": schema,
                "strict": True
            }
        }
    )
    return json.loads(response.choices[0].message.content)


try:
    print("[3.1 Strict schema result]")
    print(openai_strict_schema("John Smith, 30, john@example.com"))
except Exception as e:
    print(f"  Note: Strict mode needs gpt-4o-2024-08-06+. Error: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Approach D — Instructor + Pydantic (BEST)
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 4: Instructor + Pydantic (Best Practice)")
print("=" * 70)


def instructor_pydantic_demo():
    if not os.getenv("OPENAI_API_KEY"):
        print("Skipped (no API key)")
        return
    try:
        import instructor
        from openai import OpenAI
        from pydantic import BaseModel, Field

        class UserInfo(BaseModel):
            name: str = Field(description="Full name")
            age: int = Field(ge=0, le=150, description="Age in years")
            email: str = Field(pattern=r"^\S+@\S+\.\S+$", description="Email address")

        client = instructor.from_openai(OpenAI())
        user = client.chat.completions.create(
            model="gpt-4o-mini",
            response_model=UserInfo,
            messages=[{"role": "user", "content": "John Smith is 30 years old, email: john@example.com"}],
            max_retries=3
        )
        print(f"[4.1 Typed result]")
        print(f"  name:  {user.name!r} (type: {type(user.name).__name__})")
        print(f"  age:   {user.age!r} (type: {type(user.age).__name__})")
        print(f"  email: {user.email!r} (type: {type(user.email).__name__})")
    except ImportError:
        print("Install: pip install instructor")
    except Exception as e:
        print(f"Error: {e}")


instructor_pydantic_demo()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Complex Nested Schema
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 5: Complex Nested Schema (Project → Tasks)")
print("=" * 70)


def nested_schema_demo():
    if not os.getenv("OPENAI_API_KEY"):
        print("Skipped (no API key)")
        return
    try:
        import instructor
        from openai import OpenAI
        from pydantic import BaseModel, Field

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
            description: str = Field(description="Brief project description")
            tasks: List[Task]

        client = instructor.from_openai(OpenAI())
        text = """Project 'Website Redesign':
        - Design mockups (HIGH priority, due 2024-12-01, assigned to John and Sarah)
        - Implement backend (medium, due 2024-12-15, Mike)
        - QA testing (low, due 2024-12-20, whole team)"""

        project = client.chat.completions.create(
            model="gpt-4o-mini",
            response_model=Project,
            messages=[{"role": "user", "content": text}]
        )
        print(f"[5.1 Extracted project]")
        print(f"  Name: {project.name}")
        print(f"  Description: {project.description}")
        for task in project.tasks:
            print(f"  • {task.title} [{task.priority.value}] due {task.due_date}, assigned: {task.assignees}")
    except Exception as e:
        print(f"Error: {e}")


nested_schema_demo()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Custom Validators
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 6: Custom Validators (Catch + Retry)")
print("=" * 70)


def custom_validator_demo():
    if not os.getenv("OPENAI_API_KEY"):
        print("Skipped (no API key)")
        return
    try:
        import instructor
        from openai import OpenAI
        from pydantic import BaseModel, Field, field_validator

        class Invoice(BaseModel):
            invoice_id: str
            total: float = Field(description="Total amount")
            items_count: int

            @field_validator("total")
            @classmethod
            def total_positive(cls, v):
                if v < 0:
                    raise ValueError("Total cannot be negative")
                return v

            @field_validator("items_count")
            @classmethod
            def at_least_one_item(cls, v):
                if v < 1:
                    raise ValueError("Invoice must have at least 1 item")
                return v

        client = instructor.from_openai(OpenAI())
        invoice = client.chat.completions.create(
            model="gpt-4o-mini",
            response_model=Invoice,
            messages=[{"role": "user", "content": "Invoice INV-001, $250 total, 5 items"}],
            max_retries=3
        )
        print(f"[6.1 Valid invoice]")
        print(f"  ID: {invoice.invoice_id}, Total: ${invoice.total}, Items: {invoice.items_count}")
    except Exception as e:
        print(f"Error: {e}")


custom_validator_demo()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: Retry Demonstration
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 7: Retry on Validation Failure")
print("=" * 70)


def retry_demo():
    """Force a strict constraint LLM might violate, watch retries kick in."""
    if not os.getenv("OPENAI_API_KEY"):
        print("Skipped (no API key)")
        return
    try:
        import instructor
        from openai import OpenAI
        from pydantic import BaseModel, Field

        class StrictSummary(BaseModel):
            # Force a very specific format LLM might initially miss
            summary: str = Field(min_length=10, max_length=50, description="EXACTLY 10-50 characters")
            keyword_count: int = Field(ge=1, le=5)

        client = instructor.from_openai(OpenAI())
        result = client.chat.completions.create(
            model="gpt-4o-mini",
            response_model=StrictSummary,
            messages=[{"role": "user", "content": "Summarize 'Python is a great language for AI and ML' in a tweet"}],
            max_retries=3
        )
        print(f"  Summary: {result.summary} (len={len(result.summary)})")
        print(f"  Keywords: {result.keyword_count}")
    except Exception as e:
        print(f"After 3 retries, gave up: {e}")


retry_demo()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8: Exercises
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 8: EXERCISES")
print("=" * 70)
print("""
EASY:
1. Define Pydantic model for "Recipe": name, ingredients (list[str]), steps (list[str]).
   Extract from cooking blog text.

2. Use enum for restaurant cuisine type. Force LLM to pick from list.

MEDIUM:
3. Nested schema: Company → list[Department] → list[Employee] → list[Skill]
4. Add validators: salary > 0, joining_date >= 2000-01-01, skills count between 1-10.

HARD:
5. Robust extractor: Try detailed schema, fall back to simpler if fails.
6. Streaming partial Pydantic — show progressive UI updates as LLM generates.

PRO:
7. Build a "structured logger": every LLM call returns a Pydantic model with:
   - input/output
   - latency
   - cost
   - validation_attempts
   Log to JSON, analyze patterns.
""")

if __name__ == "__main__":
    print("\n✅ Structured outputs = production-grade reliability. Always use them!")
