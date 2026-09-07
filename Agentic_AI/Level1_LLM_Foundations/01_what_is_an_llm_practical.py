"""
Level 1 — Doc 1: What is an LLM? (PRACTICAL)
==============================================
Topics covered:
  1. The core loop — prompt -> tokenize -> generate -> detokenize, made visible
  2. Task categories an LLM can do (text gen, code gen, extraction, classification,
     translation, summarization, Q&A, reasoning) — one call per category
  3. The hallucination problem, reproduced on purpose
  4. Closed-source vs open-source landscape — a runnable comparison table

Install:
  pip install openai python-dotenv tiktoken

Run: python 01_what_is_an_llm_practical.py
"""

import os
from dotenv import load_dotenv

load_dotenv()

HAS_KEY = bool(os.getenv("OPENAI_API_KEY"))


def call(prompt: str, system: str = "You are concise.", max_tokens: int = 150) -> str:
    """Thin wrapper — every section below calls this one function."""
    if not HAS_KEY:
        return "[NO_API_KEY — set OPENAI_API_KEY in .env to run live]"
    from openai import OpenAI
    client = OpenAI()
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: The Core Loop, Made Visible
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 1: The Core Loop")
print("=" * 70)

prompt = "Complete this sentence with exactly 5 words: The sun rises in the"


def show_core_loop(prompt: str):
    if HAS_KEY:
        import tiktoken
        enc = tiktoken.get_encoding("o200k_base")
        token_ids = enc.encode(prompt)
        print(f"  1. TOKENIZE  : {len(token_ids)} tokens -> {token_ids[:8]}...")
    else:
        print("  1. TOKENIZE  : [needs tiktoken/key — this step happens regardless of API access]")
    print(f"  2. INPUT     : '{prompt}'")
    output = call(prompt, system="Complete sentences exactly as asked.", max_tokens=20)
    print(f"  3. GENERATE  : model predicts next tokens one at a time, autoregressively")
    print(f"  4. OUTPUT    : '{output}'")
    print("\n  This 4-step loop is ALL an LLM ever does — every 'capability' below")
    print("  is this same loop, just with a different prompt shape.")


show_core_loop(prompt)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Task Categories — Same Loop, Different Prompt
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 2: One Model, Many Task Shapes")
print("=" * 70)

TASKS = {
    "text generation": "Write a 2-line poem about debugging code.",
    "code generation": "Write a Python one-liner that reverses a string.",
    "extraction": "Extract the name and age: 'Ashish is a 28-year-old backend engineer.' Return as 'name, age'.",
    "classification": "Classify sentiment (positive/negative/neutral): 'This API is surprisingly fast.'",
    "translation": "Translate to Hindi: 'The server is down.'",
    "summarization": "Summarize in one sentence: 'The team deployed the new caching layer on Friday, which cut p95 latency by 40% but introduced a stale-data bug that was fixed the following Monday.'",
    "q&a": "What does HTTP status 429 mean?",
    "reasoning (sort of)": "If a train leaves at 3pm and travels 60km/h for 2.5 hours, what time does it arrive and how far did it go?",
}

for task, task_prompt in TASKS.items():
    output = call(task_prompt, max_tokens=80)
    print(f"\n  [{task}]")
    print(f"  -> {output}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Reproduce a Hallucination on Purpose
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 3: The Hallucination Problem")
print("=" * 70)

print("""
  An LLM predicts the statistically likely next token — it has no built-in
  fact-checker. Asking about something obscure/fake tends to produce a
  confident, plausible-sounding, WRONG answer rather than "I don't know".
""")

hallucination_prompt = "What were the exact attendance numbers at the 2019 International Conference on Backend Latency Optimization held in Pune?"
output = call(hallucination_prompt, max_tokens=100)
print(f"  Prompt: {hallucination_prompt}")
print(f"  Model : {output}")
print("\n  (That conference doesn't exist. Watch whether the model says so,")
print("   invents a plausible number, or hedges — this is the core reliability")
print("   problem RAG (Level 5) and grounding exist to solve.)")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Closed vs Open Source — a Runnable Comparison
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 4: The Modern Landscape (structured, not prose)")
print("=" * 70)

LANDSCAPE = [
    {"category": "Closed-source commercial", "examples": "GPT-4o, Claude, Gemini", "you_pay": "per token, API only", "control": "low — provider controls weights/updates"},
    {"category": "Open-source (self-host)", "examples": "Llama, Mistral, Qwen, DeepSeek", "you_pay": "compute only, model is free", "control": "high — you own the weights"},
    {"category": "Specialized", "examples": "Codestral (code), Whisper (speech)", "you_pay": "varies", "control": "task-specific, not general-purpose"},
]

for row in LANDSCAPE:
    print(f"\n  {row['category']}")
    for k, v in row.items():
        if k != "category":
            print(f"    {k:10s}: {v}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Exercises
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 5: EXERCISES")
print("=" * 70)
print("""
EASY:
1. Add a "code review" task category to TASKS. Feed it a buggy 5-line function.

MEDIUM:
2. Write a second hallucination prompt about a fake historical event in your
   own domain (fintech, healthcare, etc). Does the model hedge more or less?

HARD:
3. Ask the SAME question 5 times with temperature=0 vs temperature=1.
   Compare determinism. This is the "core loop" being probabilistic, made visible.

PRO:
4. Build a tiny "hallucination detector": ask the model the same factual
   question 3 times, and flag it as suspicious if the 3 answers disagree.
""")

if __name__ == "__main__":
    print("\nDone. Next: 02_tokens_embeddings_practical.py")
