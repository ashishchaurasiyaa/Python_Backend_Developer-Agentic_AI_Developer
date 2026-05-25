"""
Level 2 — Doc 2: Zero-Shot Prompting (PRACTICAL)
=================================================
Topics covered:
  1. Basic zero-shot tasks (translation, sentiment, summarization)
  2. Where zero-shot fails (custom domains)
  3. Improving zero-shot with constraints
  4. Zero-shot CoT magic phrase
  5. Production ticket classifier
  6. Output format enforcement
  7. Consistency measurement (run N times, check variance)

Install: pip install openai python-dotenv
Run: python 02_zero_shot_practical.py
"""

import os
import json
from typing import Optional
from collections import Counter
from dotenv import load_dotenv

load_dotenv()


def llm_call(prompt: str, temperature: float = 0, max_tokens: int = 200, system: Optional[str] = None) -> str:
    """Helper to call OpenAI. Returns empty string if no key."""
    if not os.getenv("OPENAI_API_KEY"):
        return "[NO_API_KEY — set OPENAI_API_KEY to run]"
    try:
        from openai import OpenAI
        client = OpenAI()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"[Error: {e}]"


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Basic Zero-Shot Tasks That Work
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 1: Basic Zero-Shot — Common Tasks (Usually Work)")
print("=" * 70)

# 1.1 Translation
print("\n[1.1 Translation]")
prompt = "Translate to Hindi: 'I love programming'"
print(f"Prompt: {prompt}")
print(f"Output: {llm_call(prompt)}")

# 1.2 Sentiment
print("\n[1.2 Sentiment Classification]")
prompt = """Classify sentiment as positive, negative, or neutral. Output ONLY the label.

Review: "The product is okay, nothing special."

Sentiment:"""
print(f"Output: {llm_call(prompt)}")

# 1.3 Summarization
print("\n[1.3 Summarization]")
article = """
Python is a high-level, interpreted programming language created by Guido van Rossum
and first released in 1991. It emphasizes code readability with significant indentation.
Python is dynamically typed and garbage-collected. It supports multiple paradigms:
procedural, object-oriented, and functional. It has a large standard library and a
massive ecosystem of third-party packages.
"""
prompt = f"Summarize in 1 sentence:\n\n{article}"
print(f"Output: {llm_call(prompt)}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Where Zero-Shot FAILS — Custom Categories
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 2: Where Zero-Shot Fails (Without Constraints)")
print("=" * 70)

# Bad: vague instruction
print("\n[2.1 BAD: Vague output format]")
bad_prompt = "Extract user info: 'Name: John Smith, age 30, email john@example.com'"
print(f"Prompt: {bad_prompt}")
print(f"Output: {llm_call(bad_prompt)}")
print("☝️ Output format is unpredictable — could be JSON, markdown, plain text")

# Good: specified format
print("\n[2.2 GOOD: Strict format constraint]")
good_prompt = """Extract user info as JSON. Return ONLY valid JSON, no other text.

Format: {"name": "string", "age": number, "email": "string"}

Input: "Name: John Smith, age 30, email john@example.com"

JSON:"""
print(f"Output: {llm_call(good_prompt)}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Improving Zero-Shot with Constraints
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 3: Improving Zero-Shot with Constraints")
print("=" * 70)

# Without constraints
print("\n[3.1 WITHOUT constraints]")
weak = "Summarize Python's history"
print(f"Prompt: {weak}")
print(f"Output: {llm_call(weak, max_tokens=300)[:200]}...")

# With constraints
print("\n[3.2 WITH constraints]")
strong = """Summarize Python's history in EXACTLY 3 bullet points.
Each bullet must be under 15 words.
Start each bullet with a year.
No preamble, no conclusion."""
print(f"Prompt: {strong}")
print(f"Output:\n{llm_call(strong, max_tokens=200)}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: The Magic Phrase — Zero-Shot Chain-of-Thought
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 4: Zero-Shot CoT — 'Let's think step by step'")
print("=" * 70)

# Classic bat-and-ball problem
problem = "A bat and ball cost $1.10. The bat costs $1 more than the ball. How much is the ball?"

# Without CoT
print(f"\n[4.1 Problem: {problem}]")
print("\nWITHOUT CoT (often wrong):")
no_cot = f"{problem}\nAnswer:"
print(f"  Output: {llm_call(no_cot, max_tokens=50)}")

# With CoT
print("\nWITH CoT magic phrase (usually correct):")
with_cot = f"{problem}\nLet's think step by step."
print(f"  Output: {llm_call(with_cot, max_tokens=300)}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Production Ticket Classifier (Zero-Shot)
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 5: Production Pattern — Ticket Classifier")
print("=" * 70)

CATEGORIES = ["billing", "technical", "shipping", "account", "other"]


def classify_ticket(ticket: str) -> str:
    """Zero-shot ticket classifier — production-grade."""
    prompt = f"""You are a customer support classifier.

Classify this ticket into EXACTLY ONE of these categories:
- billing       (payment, refund, invoice, subscription)
- technical     (bugs, errors, can't login, broken feature)
- shipping      (delivery, tracking, returns)
- account       (password reset, email change, profile)
- other         (everything else)

Rules:
- Output ONLY the category name (lowercase, single word)
- No explanation, no preamble

Ticket: "{ticket}"

Category:"""
    result = llm_call(prompt, temperature=0, max_tokens=10)
    result = result.strip().lower()
    # Validation — fall back to "other" if invalid
    return result if result in CATEGORIES else "other"


test_tickets = [
    "I want a refund for order #12345",
    "Can't log in to my account, getting 500 error",
    "Where is my package? It's been 2 weeks",
    "How do I change my email address?",
    "Do you have a discount for students?"
]

for t in test_tickets:
    category = classify_ticket(t)
    print(f"  [{category:10s}] {t}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Output Format Enforcement (JSON)
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 6: Strict JSON Output (Zero-Shot)")
print("=" * 70)


def extract_entities(text: str) -> dict:
    """Extract people, orgs, locations as JSON."""
    prompt = f"""Extract entities from the text.

Return ONLY valid JSON in this exact format:
{{
  "people": ["name1", "name2"],
  "organizations": ["org1", "org2"],
  "locations": ["place1", "place2"]
}}

If no entities of a type, use empty array [].
NO other text, NO markdown code blocks, JUST the JSON.

Text: "{text}"

JSON:"""
    result = llm_call(prompt, temperature=0)
    try:
        return json.loads(result)
    except json.JSONDecodeError:
        return {"error": "invalid_json", "raw": result}


sample = "Elon Musk announced that Tesla and SpaceX will collaborate at the Austin headquarters."
print(f"\nInput: {sample}")
print(f"Extracted: {extract_entities(sample)}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: Consistency Measurement
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 7: Consistency — Run N times, Check Variance")
print("=" * 70)


def measure_consistency(prompt: str, n_runs: int = 5, temperature: float = 0) -> dict:
    """Run the same prompt N times, measure output consistency."""
    outputs = [llm_call(prompt, temperature=temperature, max_tokens=20) for _ in range(n_runs)]
    counter = Counter(outputs)
    most_common = counter.most_common(1)[0]
    consistency_rate = most_common[1] / n_runs
    return {
        "runs": n_runs,
        "unique_outputs": len(counter),
        "most_common": most_common[0],
        "consistency_rate": consistency_rate,
        "all_outputs": list(counter.items())
    }


test_prompt = """Classify sentiment as POSITIVE, NEGATIVE, or NEUTRAL.
Output ONE word only.

Review: "It's fine, I guess."

Sentiment:"""

print("\n[7.1 With temperature=0 (deterministic)]")
result_low_t = measure_consistency(test_prompt, n_runs=5, temperature=0)
print(f"  Consistency: {result_low_t['consistency_rate'] * 100:.0f}%")
print(f"  Outputs: {result_low_t['all_outputs']}")

print("\n[7.2 With temperature=1.0 (high creativity)]")
result_high_t = measure_consistency(test_prompt, n_runs=5, temperature=1.0)
print(f"  Consistency: {result_high_t['consistency_rate'] * 100:.0f}%")
print(f"  Outputs: {result_high_t['all_outputs']}")

print("\n  ☝️ Temperature=0 gives more consistent classifications")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8: Exercises
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 8: EXERCISES")
print("=" * 70)
print("""
EASY:
1. Write a zero-shot prompt to detect language of input text. Test with 5 languages.
2. Write zero-shot translator for English → 3 languages.

MEDIUM:
3. Build a profanity filter — return CLEAN, MILD, or PROFANE.
4. Add CoT to a math word problem — measure accuracy improvement on 10 problems.

HARD:
5. Build a ticket classifier with 10 categories. Measure accuracy on 50 labeled tickets.
6. Compare zero-shot vs few-shot (coming in next doc) on the same classification task.

PRO:
7. Build a JSON schema validator: prompt LLM to extract data,
   validate against Pydantic, retry up to 3 times on validation failure.
""")

if __name__ == "__main__":
    print("\n✅ Run this file — modify prompts, observe outputs!")
