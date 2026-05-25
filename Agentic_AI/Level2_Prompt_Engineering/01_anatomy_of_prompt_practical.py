"""
Level 2 — Doc 1: Anatomy of a Prompt (PRACTICAL)
=================================================
Topics covered:
  1. Basic message structure (system, user, assistant)
  2. Multi-turn conversation with history
  3. OpenAI vs Anthropic message format
  4. Sliding window for long conversations
  5. Persona setting (role-based prompting)
  6. 5-section system prompt framework
  7. Common mistakes — before/after fix

Install: pip install openai anthropic python-dotenv
Run: python 01_anatomy_of_prompt_practical.py

Note: Real API calls need OPENAI_API_KEY / ANTHROPIC_API_KEY in .env
"""

import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Message Structure Basics
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 1: Message Structure — system, user, assistant")
print("=" * 70)

# Basic 3-message structure
messages_basic = [
    {"role": "system", "content": "You are a Python tutor."},
    {"role": "user", "content": "What is a list comprehension?"},
    {"role": "assistant", "content": "A list comprehension is a concise way to create lists in Python."},
    {"role": "user", "content": "Show me an example"}
]

print("Sample 4-message conversation:")
for i, msg in enumerate(messages_basic):
    print(f"  [{i}] {msg['role']:10s} | {msg['content'][:60]}")
print()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: OpenAI vs Anthropic Format Difference
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 2: OpenAI vs Anthropic Format")
print("=" * 70)

# OpenAI format — system inside messages list
openai_request = {
    "model": "gpt-4o-mini",
    "messages": [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hi"}
    ]
}

# Anthropic format — system as separate parameter
anthropic_request = {
    "model": "claude-3-5-sonnet-20241022",
    "system": "You are helpful.",  # ← Separate from messages
    "messages": [
        {"role": "user", "content": "Hi"}
    ],
    "max_tokens": 1024
}

print("OpenAI: system goes INSIDE messages list")
print(f"  messages[0].role = {openai_request['messages'][0]['role']}")
print()
print("Anthropic: system is SEPARATE parameter")
print(f"  system = {anthropic_request['system']!r}")
print(f"  messages[0].role = {anthropic_request['messages'][0]['role']}")
print()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Stateless Demo — Without History
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 3: Stateless LLM — Without History (Wrong Way)")
print("=" * 70)

# WRONG: No history kept, LLM forgets
def stateless_chat_wrong(user_msg: str):
    """This is wrong — LLM has no memory of previous messages."""
    return [
        {"role": "system", "content": "You are a math tutor."},
        {"role": "user", "content": user_msg}  # Only current message
    ]

print("Turn 1 prompt:")
print(stateless_chat_wrong("What is 5 + 3?"))
print()
print("Turn 2 prompt (LLM has NO IDEA what 'that' refers to):")
print(stateless_chat_wrong("Multiply that by 2"))
print("☝️  Problem: 'that' has no context — LLM will guess wrong")
print()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Stateful Chat with History (Right Way)
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 4: Stateful Chat — With History (Right Way)")
print("=" * 70)


class ChatSession:
    """Maintains conversation history across turns."""

    def __init__(self, system_prompt: str, model: str = "gpt-4o-mini"):
        self.history = [{"role": "system", "content": system_prompt}]
        self.model = model

    def add_user(self, message: str):
        self.history.append({"role": "user", "content": message})

    def add_assistant(self, message: str):
        self.history.append({"role": "assistant", "content": message})

    def get_messages(self) -> list:
        return self.history.copy()

    def turn_count(self) -> int:
        return sum(1 for m in self.history if m["role"] == "user")


session = ChatSession("You are a math tutor.")
session.add_user("What is 5 + 3?")
session.add_assistant("5 + 3 = 8")
session.add_user("Multiply that by 2")
session.add_assistant("8 * 2 = 16")

print(f"Total messages in history: {len(session.history)}")
print(f"Total user turns: {session.turn_count()}")
print("Full message history:")
for msg in session.history:
    print(f"  {msg['role']:10s} | {msg['content']}")
print()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Sliding Window — Handle Long Conversations
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 5: Sliding Window — Context Window Management")
print("=" * 70)


class SlidingChatSession:
    """Keeps system prompt + last N message pairs only."""

    def __init__(self, system_prompt: str, window_size: int = 5):
        self.system = {"role": "system", "content": system_prompt}
        self.history = []  # user/assistant pairs
        self.window_size = window_size  # max pairs to keep

    def add_user(self, message: str):
        self.history.append({"role": "user", "content": message})
        self._trim()

    def add_assistant(self, message: str):
        self.history.append({"role": "assistant", "content": message})
        self._trim()

    def _trim(self):
        # Keep only last (window_size * 2) messages = window_size pairs
        max_msgs = self.window_size * 2
        if len(self.history) > max_msgs:
            self.history = self.history[-max_msgs:]

    def get_messages(self) -> list:
        return [self.system] + self.history


# Demo: Add 10 turns, only last 5 pairs kept
sliding = SlidingChatSession("You are helpful.", window_size=3)
for i in range(1, 8):
    sliding.add_user(f"Question {i}")
    sliding.add_assistant(f"Answer {i}")

print(f"Total turns added: 7")
print(f"Messages in active context: {len(sliding.get_messages())}")
print(f"Window size (pairs): {sliding.window_size}")
print("Active messages (system + last 3 pairs):")
for msg in sliding.get_messages():
    print(f"  {msg['role']:10s} | {msg['content']}")
print()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Persona Setting — Role-Based Prompting
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 6: Persona Setting — Same Question, Different Personas")
print("=" * 70)

PERSONAS = {
    "junior_dev": "You are a junior developer who just learned Python last month. You explain in simple terms with lots of comments.",
    "senior_dev": "You are a senior staff engineer at Google with 15 years of Python experience. You write idiomatic, production-ready code.",
    "professor": "You are a CS professor at MIT. You explain with academic rigor, mentioning time complexity and theoretical considerations.",
    "child_friendly": "You are explaining to a 10-year-old. Use simple words and fun analogies."
}

question = "How do I reverse a string in Python?"

print(f"Question: {question}\n")
for persona_name, persona_prompt in PERSONAS.items():
    print(f"  Persona: {persona_name}")
    print(f"  System: {persona_prompt[:80]}...")
    print(f"  → Output would be DIFFERENT in style/depth")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: 5-Section Framework — Production System Prompt
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 7: 5-Section Framework (ROLE + CONTEXT + TASK + RULES + EXAMPLES)")
print("=" * 70)


def build_system_prompt(
    role: str,
    context: str,
    task: str,
    rules: list[str],
    examples: list[dict] = None,
    output_format: str = None
) -> str:
    """Build a structured system prompt using 5-section framework."""
    parts = [f"ROLE: {role}", "", f"CONTEXT:\n{context}", "", f"TASK: {task}", ""]

    if rules:
        parts.append("RULES:")
        for r in rules:
            parts.append(f"- {r}")
        parts.append("")

    if output_format:
        parts.append(f"OUTPUT FORMAT:\n{output_format}")
        parts.append("")

    if examples:
        parts.append("EXAMPLES:")
        for ex in examples:
            parts.append(f"Q: {ex['q']}")
            parts.append(f"A: {ex['a']}")
            parts.append("")

    return "\n".join(parts)


# Build a production system prompt
sql_generator_prompt = build_system_prompt(
    role="You are a SQL query generator for an e-commerce platform.",
    context="Database tables: users, orders, products, reviews. Users are non-technical PMs.",
    task="Convert natural language questions to PostgreSQL queries.",
    rules=[
        "Always use parameterized queries (prevent SQL injection)",
        "Limit results to 1000 rows by default",
        "Use JOIN over subqueries when possible",
        "Never include DROP/DELETE/UPDATE — read-only access",
    ],
    output_format="```sql\nSELECT ...\n```\nExplanation: 1-line description.",
    examples=[
        {
            "q": "Top 10 customers by total spend",
            "a": "```sql\nSELECT u.id, u.name, SUM(o.total) AS spend\nFROM users u JOIN orders o ON u.id = o.user_id\nGROUP BY u.id, u.name ORDER BY spend DESC LIMIT 10;\n```\nExplanation: Joins users + orders, ranks by spend."
        }
    ]
)

print("Generated production system prompt:\n")
print(sql_generator_prompt)
print()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8: Common Mistakes — Before / After
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 8: Common Mistakes — Before / After")
print("=" * 70)

# Mistake 1: No system message
bad_1 = [{"role": "user", "content": "Write a function"}]
good_1 = [
    {"role": "system", "content": "You are a Python expert. Write idiomatic, typed code."},
    {"role": "user", "content": "Write a function"}
]
print("Mistake 1: Missing system message")
print(f"  BAD:  {bad_1}")
print(f"  GOOD: includes system → consistent, predictable output\n")

# Mistake 2: Mixed role + task in user
bad_2 = [{"role": "user", "content": "You are a Python expert. Write fibonacci."}]
good_2 = [
    {"role": "system", "content": "You are a Python expert."},
    {"role": "user", "content": "Write fibonacci."}
]
print("Mistake 2: Mixing role into user message")
print(f"  BAD:  role mixed into user → harder to debug, may leak in some models")
print(f"  GOOD: role goes in system, task in user\n")

# Mistake 3: Conflicting rules
bad_3_system = """
- Be concise
- Provide detailed explanations
- Output JSON
- Output markdown
"""
print("Mistake 3: Conflicting rules in system")
print(f"  BAD: Multiple contradicting rules → unpredictable output")
print(f"  GOOD: Pick one stance and commit. If conditional, explain WHEN")
print()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 9: REAL API CALLS (Uncomment after adding API keys)
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 9: Real API Calls (requires API keys)")
print("=" * 70)


def real_openai_call(system: str, user: str, model: str = "gpt-4o-mini") -> Optional[str]:
    """Make a real OpenAI API call. Returns None if no key."""
    if not os.getenv("OPENAI_API_KEY"):
        return None
    try:
        from openai import OpenAI
        client = OpenAI()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ],
            temperature=0.3,
            max_tokens=200
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"[Error: {e}]"


def real_anthropic_call(system: str, user: str, model: str = "claude-3-5-sonnet-20241022") -> Optional[str]:
    """Make a real Anthropic API call. Returns None if no key."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None
    try:
        from anthropic import Anthropic
        client = Anthropic()
        response = client.messages.create(
            model=model,
            system=system,                    # ← Note: separate parameter
            messages=[{"role": "user", "content": user}],
            max_tokens=200
        )
        return response.content[0].text
    except Exception as e:
        return f"[Error: {e}]"


# Try calling both if keys are set
system = "You are a haiku poet. Always respond in haiku format (5-7-5 syllables)."
user = "Topic: Python programming"

print(f"System: {system}")
print(f"User: {user}\n")

openai_result = real_openai_call(system, user)
if openai_result:
    print(f"OpenAI response:\n{openai_result}\n")
else:
    print("OpenAI: skipped (no OPENAI_API_KEY)\n")

anthropic_result = real_anthropic_call(system, user)
if anthropic_result:
    print(f"Anthropic response:\n{anthropic_result}\n")
else:
    print("Anthropic: skipped (no ANTHROPIC_API_KEY)\n")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 10: Exercises (try these yourself)
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 10: EXERCISES — Try These")
print("=" * 70)

EXERCISES = """
EASY:
1. Write a system prompt for a haiku generator. Test with 3 topics.
2. Build a multi-turn ChatSession class — verify it remembers context across 3 turns.

MEDIUM:
3. Implement summarization-based memory: When history > 10 messages,
   replace old messages with an LLM-generated summary.
4. Compare 4 different personas on the same question. Which gives best output?

HARD:
5. Design a system prompt for a legal contract summarizer:
   - Use the 5-section framework
   - Include 2 few-shot examples
   - Add safety rules (no legal advice, escalate ambiguity)
   - Test with 3 sample contracts and measure consistency

PRO:
6. Build a "prompt linter" that checks for common mistakes:
   - Missing system message
   - Conflicting rules
   - Vague language
   - No output format specified
"""
print(EXERCISES)


if __name__ == "__main__":
    print("\n✅ All sections demonstrated. Now experiment with the code above!")
