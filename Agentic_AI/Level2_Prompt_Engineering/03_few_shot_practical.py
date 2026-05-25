"""
Level 2 — Doc 3: Few-Shot Prompting (PRACTICAL)
================================================
Topics covered:
  1. Basic few-shot prompt
  2. Few-shot via chat-style messages
  3. XML-tag format (Anthropic-friendly)
  4. Choosing good examples — balanced vs biased
  5. Comparing N shots (0, 1, 3, 5)
  6. Dynamic few-shot (semantic retrieval)
  7. Few-shot for tool selection

Install: pip install openai sentence-transformers numpy python-dotenv
Run: python 03_few_shot_practical.py
"""

import os
import json
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


def llm_call(prompt: str, system: Optional[str] = None, temperature: float = 0,
             max_tokens: int = 200, messages: Optional[list] = None) -> str:
    """Helper to call OpenAI."""
    if not os.getenv("OPENAI_API_KEY"):
        return "[NO_API_KEY]"
    try:
        from openai import OpenAI
        client = OpenAI()
        if messages is None:
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
# SECTION 1: Basic Few-Shot — String Format
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 1: Basic Few-Shot (String Format)")
print("=" * 70)

few_shot_prompt = """Classify sentiment as POSITIVE, NEGATIVE, or NEUTRAL.

Examples:
"I love this!" → POSITIVE
"Worst purchase ever." → NEGATIVE
"It's okay, nothing special." → NEUTRAL
"Absolutely fantastic experience!" → POSITIVE
"Total waste of money." → NEGATIVE

Now classify (output ONLY the label):
"It works as expected." →"""

print(few_shot_prompt)
print(f"\nOutput: {llm_call(few_shot_prompt, max_tokens=10)}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Chat-Style Few-Shot (Best for Multi-turn)
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 2: Chat-Style Few-Shot — Best Practice")
print("=" * 70)

chat_few_shot = [
    {"role": "system", "content": "You translate English to Hindi. Output ONLY the Hindi translation."},
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "नमस्ते"},
    {"role": "user", "content": "Good night"},
    {"role": "assistant", "content": "शुभ रात्रि"},
    {"role": "user", "content": "Thank you"},
    {"role": "assistant", "content": "धन्यवाद"},
    {"role": "user", "content": "I love programming"}  # Real query
]

print("Conversation structure with 3 few-shot examples + 1 real query:")
for msg in chat_few_shot:
    print(f"  {msg['role']:10s} | {msg['content']}")

print(f"\nOutput: {llm_call('', messages=chat_few_shot, max_tokens=50)}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: XML-Tag Format (Anthropic-Friendly)
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 3: XML-Tag Format (Recommended for Claude)")
print("=" * 70)

xml_prompt = """Convert natural language to product JSON.

<example>
<input>iPhone 15 Pro 256GB Space Black for $1,199</input>
<output>{"product": "iPhone 15 Pro", "storage": "256GB", "color": "Space Black", "price": 1199}</output>
</example>

<example>
<input>Samsung Galaxy S24 Ultra 512GB Titanium Gray ₹1,29,999</input>
<output>{"product": "Samsung Galaxy S24 Ultra", "storage": "512GB", "color": "Titanium Gray", "price": 129999}</output>
</example>

<query>
<input>Pixel 8 Pro 128GB Obsidian — $999</input>
<output>
</query>"""

print(xml_prompt)
result = llm_call(xml_prompt, max_tokens=200)
print(f"\nOutput: {result}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Biased vs Balanced Examples
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 4: Biased vs Balanced Examples")
print("=" * 70)

biased = """Classify sentiment.

"Great!" → POSITIVE
"Amazing!" → POSITIVE
"Loved it!" → POSITIVE
"Best ever!" → POSITIVE

Classify: "It sucks"
Output:"""

balanced = """Classify sentiment.

"Great!" → POSITIVE
"It sucks" → NEGATIVE
"It's okay" → NEUTRAL
"Loved it!" → POSITIVE
"Hate it" → NEGATIVE

Classify: "It sucks"
Output:"""

print("[4.1 BIASED (all examples POSITIVE)]")
print(f"Output: {llm_call(biased, max_tokens=10)}")
print("☝️ May incorrectly output POSITIVE due to bias\n")

print("[4.2 BALANCED (mix of all categories)]")
print(f"Output: {llm_call(balanced, max_tokens=10)}")
print("☝️ Correctly outputs NEGATIVE")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Comparing N Shots (0, 1, 3, 5)
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 5: 0 vs 1 vs 3 vs 5 Shots — Same Task")
print("=" * 70)

# Domain-specific task — language detection for code
def build_n_shot_prompt(n_shots: int, query: str) -> str:
    examples = [
        ("print('hello')", "Python"),
        ("System.out.println('hello');", "Java"),
        ("console.log('hello')", "JavaScript"),
        ("fmt.Println(\"hello\")", "Go"),
        ("puts 'hello'", "Ruby"),
    ]
    selected = examples[:n_shots]
    prompt = "Identify the programming language of the snippet. Output ONLY the language name.\n\n"
    if selected:
        prompt += "Examples:\n"
        for code, lang in selected:
            prompt += f"{code} → {lang}\n"
        prompt += "\n"
    prompt += f"Now identify:\n{query} → "
    return prompt


test_query = "echo 'hello'"  # Shell — tricky, similar to print

for n in [0, 1, 3, 5]:
    p = build_n_shot_prompt(n, test_query)
    result = llm_call(p, max_tokens=20)
    print(f"  {n}-shot: '{result}'")

print("\n☝️ As examples increase, LLM gets better at picking up your format style")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Dynamic Few-Shot (Semantic Retrieval) — Simulated
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 6: Dynamic Few-Shot — Retrieve Best Examples for Each Query")
print("=" * 70)

# Simulated example DB (in production, this would be ChromaDB/Pinecone with embeddings)
EXAMPLE_DB = [
    {"input": "Refund my last order", "output": "billing"},
    {"input": "Can't log in", "output": "technical"},
    {"input": "Where's my package?", "output": "shipping"},
    {"input": "Change email address", "output": "account"},
    {"input": "Wrong item delivered", "output": "shipping"},
    {"input": "Charged twice", "output": "billing"},
    {"input": "App keeps crashing", "output": "technical"},
    {"input": "Reset my password", "output": "account"},
    {"input": "Tracking number wrong", "output": "shipping"},
    {"input": "Subscription renewal failed", "output": "billing"},
]


def simple_similarity(a: str, b: str) -> float:
    """Naive word-overlap similarity. Real code uses embeddings."""
    aw, bw = set(a.lower().split()), set(b.lower().split())
    if not aw or not bw:
        return 0.0
    return len(aw & bw) / len(aw | bw)


def dynamic_few_shot(query: str, k: int = 3) -> str:
    """Retrieve top-k most similar examples from DB."""
    scored = [(simple_similarity(query, ex["input"]), ex) for ex in EXAMPLE_DB]
    scored.sort(reverse=True)
    top_k = [ex for _, ex in scored[:k]]

    prompt = "Classify support tickets into: billing, technical, shipping, account.\n\nExamples:\n"
    for ex in top_k:
        prompt += f"Input: {ex['input']}\nCategory: {ex['output']}\n\n"
    prompt += f"Input: {query}\nCategory:"
    return prompt


test_queries = [
    "I want my money back",       # → billing-related examples
    "Login button doesn't work",  # → technical examples
    "My package never arrived",   # → shipping examples
]

for q in test_queries:
    p = dynamic_few_shot(q, k=3)
    print(f"\nQuery: {q}")
    print(f"  Top-3 retrieved examples (from word overlap):")
    # Show what examples were chosen
    scored = sorted([(simple_similarity(q, ex["input"]), ex) for ex in EXAMPLE_DB], reverse=True)
    for score, ex in scored[:3]:
        print(f"    ({score:.2f}) {ex['input']} → {ex['output']}")
    result = llm_call(p, max_tokens=10)
    print(f"  Classification: {result}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: Few-Shot for Tool Selection
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 7: Few-Shot for Tool/Function Selection")
print("=" * 70)

tool_prompt = """Given a user query, select the right tool. Output ONLY the tool name.

Available tools: search_web, calculator, send_email, get_weather, query_database

Examples:
Query: "What's 2+2?" → calculator
Query: "Latest Tesla news?" → search_web
Query: "Email John about meeting tomorrow" → send_email
Query: "Is it raining in Mumbai?" → get_weather
Query: "Top 10 customers by spend" → query_database
Query: "Compute 15% tip on $80" → calculator
Query: "Send report to team" → send_email

Now select:
Query: "Find users who signed up last week"
Tool:"""

print(f"Output: {llm_call(tool_prompt, max_tokens=10)}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8: Brand Voice Few-Shot
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 8: Brand Voice — Hinglish Casual Tone")
print("=" * 70)

brand_voice_prompt = """Rewrite customer support replies in our brand voice (casual, witty, Hinglish).

Example 1:
Original: "We are sorry to hear about the delay in your order."
Our voice: "Arre yaar, sorry for the wait! Let me track that order right now 🚀"

Example 2:
Original: "Please follow these steps to reset your password."
Our voice: "No worries! Password reset is easy-peasy: Settings → Security → Reset. Bas done!"

Example 3:
Original: "Thank you for your positive feedback."
Our voice: "YESSS! Thank you so much 🎉 Reviews like this banate hain humara din!"

Now rewrite:
Original: "Your refund has been processed. It will reflect in 3-5 business days."
Our voice:"""

print(llm_call(brand_voice_prompt, max_tokens=100))


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 9: Exercises
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 9: EXERCISES")
print("=" * 70)
print("""
EASY:
1. Convert SECTION 1's sentiment classifier to chat-style few-shot. Compare accuracy.
2. Build XML-tag few-shot for date extraction (multiple formats).

MEDIUM:
3. Plot accuracy: 0/1/3/5/10 shots on same task. Find diminishing returns point.
4. Build a brand-tone rewriter with 10 examples of YOUR favorite product's voice.

HARD:
5. Implement REAL dynamic few-shot:
   - Embed example DB with sentence-transformers
   - Use cosine similarity for retrieval
   - Test on 100 queries, compare to static 3-shot

6. Build a "few-shot test set" with edge cases. Iterate examples until 95% accuracy.

PRO:
7. Implement "best example selection" using:
   a. Random
   b. Most similar (semantic)
   c. Most diverse (covers categories)
   d. Hardest examples (low confidence on)
   Compare results.
""")

if __name__ == "__main__":
    print("\n✅ Modify prompts, observe how examples shape output!")
