"""
Level 1 — Doc 3: History of LLMs (PRACTICAL)
==============================================
This doc is a timeline, not an API — so the "practical" here is making the
timeline something you can query and be quizzed on, instead of just read once
and forget. No API key needed for any of this.

Topics covered:
  1. A queryable timeline data structure (era -> milestone -> why it mattered)
  2. "What came first?" ordering checks
  3. A self-quiz mode — tests recall of the milestones that actually get asked
     about in interviews (BERT vs GPT-1, the ChatGPT moment, reasoning models)

Run: python 03_history_of_llms_practical.py
"""

import random

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: The Timeline as Data (not prose)
# ─────────────────────────────────────────────────────────────────────────────

TIMELINE = [
    {"year": "1960s-2000s", "era": "Pre-transformer", "milestone": "Rule-based NLP", "why": "Hand-written grammar rules — brittle, didn't generalize."},
    {"year": "2000s", "era": "Pre-transformer", "milestone": "Statistical NLP", "why": "N-gram probabilities — better, still no real 'understanding'."},
    {"year": "2010s", "era": "Pre-transformer", "milestone": "RNN / LSTM", "why": "First neural sequence models — but process one token at a time (slow, forgets long context)."},
    {"year": "2017", "era": "Transformer Revolution", "milestone": "'Attention Is All You Need' paper", "why": "Introduced self-attention — processes the whole sequence in parallel, remembers long-range context. Everything below builds on this."},
    {"year": "2018", "era": "Pretraining Era", "milestone": "BERT (Google)", "why": "Bidirectional — great at UNDERSTANDING text (classification, search). Not a generator."},
    {"year": "2018-2019", "era": "Pretraining Era", "milestone": "GPT-1, GPT-2 (OpenAI)", "why": "Autoregressive — great at GENERATING text. GPT-2 was withheld initially over misuse concerns."},
    {"year": "2020", "era": "Pretraining Era", "milestone": "GPT-3 (OpenAI)", "why": "175B params — first model where scale alone produced surprising general capability (few-shot learning)."},
    {"year": "Nov 2022", "era": "The ChatGPT Moment", "milestone": "ChatGPT launch", "why": "Not a new model — RLHF (human feedback fine-tuning) made GPT-3.5 usable as a CONVERSATIONAL product. This is what took LLMs mainstream."},
    {"year": "2023", "era": "The Race Begins", "milestone": "GPT-4, Claude, Gemini, Llama 2", "why": "Every major lab shipped a frontier model. Open-source (Llama) became genuinely competitive."},
    {"year": "2024", "era": "Multi-Modal & Agents", "milestone": "GPT-4o, Claude 3, function calling matures", "why": "Models handle text+image+audio natively. Tool-calling becomes reliable enough for real agents."},
    {"year": "2024-2025", "era": "Reasoning Models", "milestone": "OpenAI o1/o3, DeepSeek R1", "why": "Models trained to 'think before answering' (extended chain-of-thought) — big jump on hard reasoning/math/code, at the cost of latency."},
    {"year": "2024-2026", "era": "Agentic AI Era", "milestone": "MCP, multi-agent frameworks, computer use", "why": "The shift from 'answer a question' to 'complete a multi-step task autonomously' — this is where YOU are studying right now (Level 6+)."},
]


def print_timeline():
    print("=" * 70)
    print("SECTION 1: The Timeline")
    print("=" * 70)
    current_era = None
    for row in TIMELINE:
        if row["era"] != current_era:
            current_era = row["era"]
            print(f"\n  ── {current_era} ──")
        print(f"    {row['year']:14s} {row['milestone']}")
        print(f"    {'':14s} why: {row['why']}")


print_timeline()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: "What Came First?" — Ordering Checks
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 2: Ordering Sanity Checks")
print("=" * 70)

pairs_to_check = [
    ("BERT", "GPT-3"),
    ("ChatGPT launch", "GPT-4"),
    ("Attention Is All You Need", "BERT"),
]


def find_index(needle: str) -> int:
    """Substring match against milestone text — 'GPT-4' matches the row
    'GPT-4, Claude, Gemini, Llama 2' without needing the exact full string."""
    return next(i for i, r in enumerate(TIMELINE) if needle in r["milestone"])


for a, b in pairs_to_check:
    idx_a, idx_b = find_index(a), find_index(b)
    first, second = (a, b) if idx_a < idx_b else (b, a)
    print(f"  {first}  came BEFORE  {second}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Self-Quiz Mode
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 3: Self-Quiz — the questions that actually get asked")
print("=" * 70)

QUIZ = [
    {"q": "What's the single biggest architectural difference between BERT and GPT?", "a": "BERT is bidirectional (understanding-focused); GPT is autoregressive/unidirectional (generation-focused)."},
    {"q": "Was ChatGPT (Nov 2022) a new model architecture?", "a": "No — it was GPT-3.5 fine-tuned with RLHF into a conversational product. The breakthrough was UX + alignment, not a new architecture."},
    {"q": "What paper introduced the transformer, and what problem did it solve vs RNN/LSTM?", "a": "'Attention Is All You Need' (2017) — solved the sequential bottleneck: RNNs process one token at a time, transformers process the whole sequence in parallel via self-attention."},
    {"q": "What's the key trade-off reasoning models (o1/o3, DeepSeek R1) introduced?", "a": "Better accuracy on hard reasoning/math/code tasks, at the cost of higher latency and cost (they 'think' with extra generated tokens before answering)."},
    {"q": "Why does 'history' matter for a working engineer, not just trivia?", "a": "It tells you WHY each model family is good at what it's good at — e.g. don't reach for a reasoning model for a low-latency chat UI, don't reach for BERT to generate text."},
]


def run_quiz(shuffle: bool = True):
    items = QUIZ.copy()
    if shuffle:
        random.shuffle(items)
    print("\n  Read each question, say your answer OUT LOUD, then check below.\n")
    for i, item in enumerate(items, 1):
        print(f"  Q{i}. {item['q']}")
    print("\n  --- Answers ---")
    for i, item in enumerate(items, 1):
        print(f"  A{i}. {item['a']}")


run_quiz()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Exercises
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 4: EXERCISES")
print("=" * 70)
print("""
EASY:
1. Cover the "why" column and try to reconstruct it from memory, era by era.

MEDIUM:
2. Add 2-3 rows to TIMELINE for events after this file was written — what
   shipped since, and where does it fit (multi-modal? agentic? reasoning?)

HARD:
3. Explain the arc in 90 seconds, out loud, as if to an interviewer who asked
   "walk me through how we got from GPT-1 to today." Record yourself.

PRO:
4. For each era, name ONE thing an agent built TODAY still can't reliably do
   that this doc's "9. Where We Are" section calls out. Turn that into your
   own honest talking point for "what are the current limits of LLMs?"
""")

if __name__ == "__main__":
    print("\nDone. Next: 04_attention_transformers_practical.py")
