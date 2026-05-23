# Prompt Engineering — Zero-shot, Few-shot, Chain-of-Thought, Structured Outputs

## Quick Concepts
- **Zero-shot** = example diye bina task karo
- **Few-shot** = 2-5 examples do → pattern follow karta hai
- **Chain-of-Thought (CoT)** = "step by step sochne" bolao → accuracy badhti hai
- **System prompt** = model ka behavior define karo — role, tone, constraints
- **Structured output** = JSON format mein response lo — parse karna easy

---

## Interview Questions & Answers

### Q1: Zero-shot vs Few-shot vs Chain-of-Thought — kab kya use karo?
**Answer:**
```python
import anthropic

client = anthropic.Anthropic()

# ZERO-SHOT — simple tasks ke liye
def classify_sentiment_zero_shot(text: str) -> str:
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=10,
        messages=[{
            "role": "user",
            "content": f"Classify sentiment as POSITIVE, NEGATIVE, or NEUTRAL: '{text}'"
        }]
    )
    return response.content[0].text.strip()

# FEW-SHOT — pattern dikhao, accuracy better
def classify_with_few_shot(text: str) -> str:
    examples = """
Examples:
Text: "The food was amazing!" → POSITIVE
Text: "Terrible service, never coming back" → NEGATIVE
Text: "The weather is cloudy today" → NEUTRAL
Text: "I love this product but shipping was slow" → MIXED
"""
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=10,
        messages=[{
            "role": "user",
            "content": f"{examples}\nText: '{text}' →"
        }]
    )
    return response.content[0].text.strip()

# CHAIN-OF-THOUGHT — complex reasoning ke liye
def solve_with_cot(problem: str) -> str:
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        messages=[{
            "role": "user",
            "content": f"""Solve this step by step, showing your reasoning:

Problem: {problem}

Think through this carefully:
1. First, identify what we know
2. What approach should we use?
3. Work through the solution step by step
4. Verify the answer

Solution:"""
        }]
    )
    return response.content[0].text

# WHEN TO USE WHICH:
# Zero-shot:  Simple, clear tasks (classification, translation, extraction)
# Few-shot:   When zero-shot inconsistent, format-specific output
# CoT:        Math, logic, multi-step reasoning, debugging
```

---

### Q2: System prompts best practices kya hain?
**Answer:**
```python
# GOOD system prompt structure
SYSTEM_PROMPT = """You are a senior Python backend developer assistant.

## Role
Expert in FastAPI, Django, PostgreSQL, Redis, and Agentic AI systems.

## Behavior Rules
- Always provide working, production-ready code
- Explain WHY not just HOW
- Point out security issues proactively
- Use Python type hints in all code
- Prefer async code for I/O operations

## Response Format
- Start with a brief explanation
- Provide code with comments
- End with potential gotchas/edge cases

## Constraints
- Do NOT use deprecated libraries
- Do NOT provide insecure code (SQL injection, etc.)
- Keep responses focused on Python backend
"""

# BAD system prompt
BAD_SYSTEM = "You are a helpful assistant."  # too vague

# Anthropic specific tips:
# 1. System prompt mein role clearly define karo
# 2. Constraints negative mein mat likho — positive mein likho
#    BAD: "Do not give wrong answers"
#    GOOD: "Always verify your answers before responding"
# 3. Output format specify karo
# 4. Tone define karo (formal/informal, brief/detailed)

# Role-based prompting
def get_code_reviewer_prompt() -> str:
    return """You are a strict code reviewer focused on:
1. Security vulnerabilities (OWASP Top 10)
2. Performance issues (N+1, missing indexes)
3. Python best practices (PEP 8, type hints)
4. Missing error handling

For each issue found, provide:
- Severity: CRITICAL / HIGH / MEDIUM / LOW
- Location: file:line
- Issue description
- Fix with code example"""

def get_sql_expert_prompt() -> str:
    return """You are a PostgreSQL expert.
When given a slow query:
1. Analyze the execution plan
2. Identify bottlenecks
3. Suggest specific indexes
4. Rewrite the query if needed
Always show EXPLAIN ANALYZE output interpretation."""
```

---

### Q3: Structured outputs — JSON response kaise enforce karte hain?
**Answer:**
```python
from pydantic import BaseModel, Field
from typing import Optional
import openai
import anthropic
import json

# --- OpenAI Structured Outputs (JSON Schema enforcement) ---
client_oai = openai.OpenAI()

class UserExtraction(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None

def extract_user_info_openai(text: str) -> UserExtraction:
    response = client_oai.beta.chat.completions.parse(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Extract user information from the text."},
            {"role": "user", "content": text},
        ],
        response_format=UserExtraction,  # Pydantic model directly!
    )
    return response.choices[0].message.parsed  # Already UserExtraction object

# Usage
info = extract_user_info_openai(
    "Hi, I'm Ashish Chaurasiya from YAM company. Email: ashish@yam.com, Ph: 9876543210"
)
print(info.name)   # "Ashish Chaurasiya"
print(info.email)  # "ashish@yam.com"

# --- Anthropic Structured Output (JSON mode) ---
client_ant = anthropic.Anthropic()

def extract_user_info_claude(text: str) -> UserExtraction:
    response = client_ant.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        system="""Extract user information and return ONLY valid JSON matching this schema:
{
  "name": "string (required)",
  "email": "string or null",
  "phone": "string or null",
  "company": "string or null"
}
Return ONLY the JSON, no explanation.""",
        messages=[{"role": "user", "content": text}]
    )

    raw_json = response.content[0].text.strip()
    # Remove markdown code blocks if present
    if raw_json.startswith("```"):
        raw_json = raw_json.split("```")[1]
        if raw_json.startswith("json"):
            raw_json = raw_json[4:]

    data = json.loads(raw_json)
    return UserExtraction(**data)

# --- Complex structured extraction ---
class OrderDetails(BaseModel):
    order_id: str
    items: list[dict] = Field(description="List of {name, qty, price}")
    total: float
    shipping_address: str
    priority: str = Field(description="normal/express/overnight")

def extract_order(email_text: str) -> OrderDetails:
    response = client_oai.beta.chat.completions.parse(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Extract order details from customer email."},
            {"role": "user", "content": email_text},
        ],
        response_format=OrderDetails,
    )
    return response.choices[0].message.parsed
```

---

### Q4: Extended Thinking / Reasoning models kya hain?
**Answer:**
```python
# Claude Extended Thinking — model "socha" dikhata hai
# Complex reasoning, math, coding challenges ke liye
import anthropic

client = anthropic.Anthropic()

def solve_complex_problem(problem: str) -> dict:
    response = client.messages.create(
        model="claude-sonnet-4-6",  # thinking support karta hai
        max_tokens=16000,
        thinking={
            "type": "enabled",
            "budget_tokens": 10000  # kitna "socha" allowed (tokens)
        },
        messages=[{"role": "user", "content": problem}]
    )

    thinking_text = ""
    answer_text = ""

    for block in response.content:
        if block.type == "thinking":
            thinking_text = block.thinking   # model ka reasoning
        elif block.type == "text":
            answer_text = block.text         # final answer

    return {
        "thinking": thinking_text,
        "answer": answer_text,
        "thinking_tokens": sum(
            1 for b in response.content if b.type == "thinking"
        )
    }

# Use extended thinking ke liye:
# - Math/physics problems
# - Algorithm design
# - Complex debugging
# - Multi-step reasoning tasks
# - Logical puzzles

# OpenAI o1/o3 models (reasoning)
response = client_oai.chat.completions.create(
    model="o1-preview",    # reasoning model
    messages=[{"role": "user", "content": "Solve this complex algorithm..."}],
    # temperature/system prompt nahi hota o1 mein
)
```

---

### Q5: Multimodal — Image + Text inputs kaise bhejte hain?
**Answer:**
```python
import base64
import httpx

# OpenAI Vision (GPT-4V / GPT-4o)
def analyze_image_url(image_url: str, question: str) -> str:
    response = client_oai.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": question},
                {"type": "image_url", "image_url": {"url": image_url, "detail": "high"}}
            ]
        }],
        max_tokens=1000,
    )
    return response.choices[0].message.content

def analyze_local_image(image_path: str, question: str) -> str:
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode()

    response = client_oai.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": question},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}
                }
            ]
        }],
    )
    return response.choices[0].message.content

# Claude Vision
def analyze_image_claude(image_path: str, question: str) -> str:
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode()

    response = client_ant.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": image_data,
                    }
                },
                {"type": "text", "text": question}
            ]
        }]
    )
    return response.content[0].text

# Use cases:
# - Invoice/receipt data extraction
# - Screenshot → code generation
# - Product image → description
# - Chart/graph analysis
# - OCR (text from image)
```
