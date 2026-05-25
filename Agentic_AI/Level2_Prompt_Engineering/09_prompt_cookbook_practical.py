"""
Level 2 — Doc 9: Prompt Cookbook (PRACTICAL)
==============================================
Copy-paste-adapt patterns for common tasks. Each function = production-ready prompt.

Install: pip install openai python-dotenv
Run: python 09_prompt_cookbook_practical.py
"""

import os
import json
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


def llm(prompt: str, temperature: float = 0.3, max_tokens: int = 500, json_mode: bool = False) -> str:
    if not os.getenv("OPENAI_API_KEY"):
        return "[NO_API_KEY]"
    try:
        from openai import OpenAI
        client = OpenAI()
        kwargs = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"[Error: {e}]"


# ─────────────────────────────────────────────────────────────────────────────
# COOKBOOK 1: Summarization
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("COOKBOOK 1: SUMMARIZATION")
print("=" * 70)


def summarize_bullets(text: str, n: int = 5) -> str:
    prompt = f"""Summarize as {n} bullet points. Each bullet under 15 words.

Text:
{text}

Bullets:"""
    return llm(prompt)


def summarize_targeted(text: str, focus: list[str]) -> str:
    focus_str = ", ".join(focus)
    prompt = f"""Summarize focusing on: {focus_str}. Ignore other details.

Text:
{text}

Targeted summary:"""
    return llm(prompt)


article = """Python is a high-level programming language created by Guido van Rossum in 1991.
It supports multiple programming paradigms including OOP, functional, and procedural.
Python is widely used in data science, AI, and web development. Major frameworks include
Django, Flask, and FastAPI. Python's syntax emphasizes readability with significant indentation.
The Python Software Foundation maintains the language and runs PyCon annually."""

print("\n[Bullet summary]")
print(summarize_bullets(article, n=3))

print("\n[Targeted summary — focus on technical info only]")
print(summarize_targeted(article, focus=["frameworks", "year created", "paradigms"]))


# ─────────────────────────────────────────────────────────────────────────────
# COOKBOOK 2: Extraction
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("COOKBOOK 2: EXTRACTION")
print("=" * 70)


def extract_entities(text: str) -> dict:
    prompt = f"""Extract entities as JSON with keys: people, organizations, locations, dates, money.
Use empty arrays for missing types. JSON only, no preamble.

Text: {text}

JSON:"""
    raw = llm(prompt, json_mode=True)
    try:
        return json.loads(raw)
    except Exception:
        return {"raw": raw, "error": "parse_failed"}


sample = "Elon Musk visited Mumbai on 2024-03-15 with Tesla and SpaceX executives. Investment: $5 billion."
print(f"\nInput: {sample}")
print(f"Entities: {extract_entities(sample)}")


# ─────────────────────────────────────────────────────────────────────────────
# COOKBOOK 3: Classification
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("COOKBOOK 3: CLASSIFICATION")
print("=" * 70)


def classify_with_confidence(text: str, categories: list[str]) -> dict:
    cats = "\n".join(f"- {c}" for c in categories)
    prompt = f"""Classify the text. Output JSON:
{{"category": "...", "confidence": 0.X, "reasoning": "..."}}

If confidence < 0.6, also include "alternative_category".

Categories:
{cats}

Text: "{text}"

JSON:"""
    raw = llm(prompt, json_mode=True)
    try:
        return json.loads(raw)
    except Exception:
        return {"raw": raw}


categories = ["urgent_bug", "feature_request", "question", "spam"]
test = "App crashes when I click login button on iPhone 15. This is blocking my entire team."
print(f"\nInput: {test}")
print(f"Result: {classify_with_confidence(test, categories)}")


# ─────────────────────────────────────────────────────────────────────────────
# COOKBOOK 4: Translation with Glossary
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("COOKBOOK 4: TRANSLATION WITH GLOSSARY")
print("=" * 70)


def translate_with_glossary(text: str, target_lang: str, glossary: dict) -> str:
    glossary_str = "\n".join(f'- "{k}" → "{v}"' for k, v in glossary.items())
    prompt = f"""Translate to {target_lang} using this exact glossary:
{glossary_str}

Preserve tone. Don't translate names.

Text: {text}

Translation:"""
    return llm(prompt)


glossary = {"API": "एपीआई", "database": "डेटाबेस", "user": "उपयोगकर्ता"}
text = "The API connects the user interface to the database."
print(f"\nInput: {text}")
print(f"Hindi: {translate_with_glossary(text, 'Hindi', glossary)}")


# ─────────────────────────────────────────────────────────────────────────────
# COOKBOOK 5: Code Review
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("COOKBOOK 5: CODE REVIEW")
print("=" * 70)


def code_review(code: str) -> str:
    prompt = f"""Review this code as a senior developer.

Format:
1. [Line X] [SEVERITY: HIGH/MEDIUM/LOW] [Issue description]
2. ...

Categories to check:
- Correctness (bugs)
- Security (vulnerabilities)
- Performance
- Readability
- Maintainability

If no issues: "No issues found."

Code:
```python
{code}
```

Review:"""
    return llm(prompt, max_tokens=800)


buggy_code = """
def divide(a, b):
    return a / b

def get_user(user_id):
    query = f"SELECT * FROM users WHERE id = {user_id}"
    return db.execute(query)

def password_check(pw):
    return pw == "admin123"
"""

print("\nCode review of buggy code:")
print(code_review(buggy_code))


# ─────────────────────────────────────────────────────────────────────────────
# COOKBOOK 6: Q&A with Context (RAG-style)
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("COOKBOOK 6: Q&A WITH CONTEXT (RAG Pattern)")
print("=" * 70)


def closed_qa(question: str, context: str) -> str:
    prompt = f"""Answer ONLY using info from the context. If not in context: say "Not in context."

Context:
{context}

Question: {question}

Answer:"""
    return llm(prompt)


context = """FreshMart was founded in 2018 in Mumbai. It delivers groceries to 5 cities.
The CEO is Priya Sharma. Annual revenue is ₹500 crores."""

questions = [
    "When was FreshMart founded?",
    "Who is the CEO?",
    "What is the CTO's name?",  # Not in context
    "How many cities does it serve?",
]

for q in questions:
    print(f"\nQ: {q}")
    print(f"A: {closed_qa(q, context)}")


# ─────────────────────────────────────────────────────────────────────────────
# COOKBOOK 7: Email Draft
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("COOKBOOK 7: EMAIL DRAFT")
print("=" * 70)


def draft_email(from_name: str, to_name: str, topic: str, tone: str = "professional", max_words: int = 100) -> str:
    prompt = f"""Draft an email:
- From: {from_name}
- To: {to_name}
- Topic: {topic}
- Tone: {tone}
- Length: under {max_words} words

Include: Subject line, greeting, body, sign-off.
Format:
Subject: ...
[Body]"""
    return llm(prompt)


print(draft_email(
    from_name="Ashish",
    to_name="Priya (Manager)",
    topic="Requesting 3 days leave for personal work next week",
    tone="professional but warm",
    max_words=80
))


# ─────────────────────────────────────────────────────────────────────────────
# COOKBOOK 8: Pro-Con Decision
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("COOKBOOK 8: PRO-CON DECISION")
print("=" * 70)


def pros_cons(decision: str) -> str:
    prompt = f"""Should I {decision}?

Provide:
- 3 PROS with brief reasoning
- 3 CONS with brief reasoning
- Recommendation (yes/no/depends) with confidence

Format:
PROS:
1. ...
CONS:
1. ...

RECOMMENDATION: ... (confidence: X/10)"""
    return llm(prompt, max_tokens=500)


print(pros_cons("learn Rust as a 4-year Python backend developer"))


# ─────────────────────────────────────────────────────────────────────────────
# Exercises
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("EXERCISES")
print("=" * 70)
print("""
EASY:
1. Build your own cookbook with 5 patterns specific to your domain.
2. Add error handling + retries to each function above.

MEDIUM:
3. Combine patterns: extract → classify → route → respond (multi-step pipeline).
4. Test each pattern on 10 inputs. Measure consistency.

HARD:
5. Build a "prompt CLI" — pick pattern from menu, fill in variables, see output.
6. Add caching: same input → same output, avoid re-calling LLM.

PRO:
7. Build a meta-prompt: "Given this task, generate the best prompt for it."
   Use it to bootstrap your cookbook automatically.
""")

if __name__ == "__main__":
    print("\n✅ Save patterns that work for you. Build your personal cookbook!")
