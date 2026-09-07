"""
Level 1 — Doc 2: Tokens & Embeddings (PRACTICAL)
==================================================
Topics covered:
  1. Tokenization — see exactly how text splits into tokens
  2. The "strawberry" trick and foreign-language token penalty, reproduced
  3. Tokens = cost — real cost math on real text
  4. Tokens = context window — how much of a doc actually fits
  5. Embeddings — turn text into vectors, measure similarity with cosine
  6. Embedding space intuition — cluster related sentences by hand

Install:
  pip install tiktoken openai numpy python-dotenv

Run: python 02_tokens_embeddings_practical.py
"""

import os
from dotenv import load_dotenv

load_dotenv()
HAS_KEY = bool(os.getenv("OPENAI_API_KEY"))


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Tokenization, Made Visible
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 1: What Does Tokenization Actually Do?")
print("=" * 70)


_WARNED_NO_TIKTOKEN = False


def tokenize(text: str):
    try:
        import tiktoken
        enc = tiktoken.get_encoding("o200k_base")
        ids = enc.encode(text)
        pieces = [enc.decode([i]) for i in ids]
        return ids, pieces
    except ImportError:
        global _WARNED_NO_TIKTOKEN
        if not _WARNED_NO_TIKTOKEN:
            print("  [tiktoken not installed — falling back to a crude whitespace/punctuation")
            print("   split below. Counts will NOT match real token counts. `pip install tiktoken`")
            print("   to see this section for real.]")
            _WARNED_NO_TIKTOKEN = True
        import re
        pieces = re.findall(r"\w+|[^\w\s]", text)
        ids = list(range(len(pieces)))  # fake ids, just so len()/slicing below still works
        return ids, pieces


samples = [
    "Hello world",
    "unbelievable",
    "supercalifragilisticexpialidocious",
    "def add(a, b): return a + b",
]

for s in samples:
    ids, pieces = tokenize(s)
    print(f"\n  '{s}'")
    print(f"  -> {len(ids)} tokens: {pieces}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: The Strawberry Trick + Foreign Language Penalty
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 2: Tricky Tokenization Cases")
print("=" * 70)

word = "strawberry"
ids, pieces = tokenize(word)
print(f"\n  '{word}' splits into: {pieces}")
print(f"  The model never sees individual LETTERS — it sees these {len(ids)} chunks.")
print(f"  That's why 'how many r's in strawberry' used to trip models up: counting")
print(f"  letters requires reasoning ACROSS token boundaries, not just reading them.")

pairs = [
    ("English", "The weather is nice today."),
    ("Hindi", "आज मौसम अच्छा है।"),
]
print("\n  Foreign-language token penalty (same meaning, different cost):")
for lang, text in pairs:
    ids, _ = tokenize(text)
    print(f"    {lang:10s}: {len(ids)} tokens  — '{text}'")
print("  Non-Latin scripts often cost MORE tokens for the same meaning —")
print("  a real, often-overlooked cost/latency factor for non-English products.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Tokens = Real Cost
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 3: Tokens = Cost (real math, not hand-waving)")
print("=" * 70)

PRICING_PER_1M = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
}

document = "This is a placeholder for a support ticket. " * 200  # simulate a ~1600-word doc
doc_tokens, _ = tokenize(document)
print(f"\n  Sample support ticket: {len(document)} chars -> {len(doc_tokens)} tokens")
for model, p in PRICING_PER_1M.items():
    cost = (len(doc_tokens) * p["input"]) / 1_000_000
    print(f"    {model:30s}: ${cost:.5f} to send this once as input")
print(f"\n  Now imagine 10,000 support tickets/day through this prompt.")
for model, p in PRICING_PER_1M.items():
    daily_cost = (len(doc_tokens) * p["input"] * 10_000) / 1_000_000
    print(f"    {model:30s}: ${daily_cost:.2f}/day just on input tokens")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Tokens = Context Window
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 4: How Much of a Real Document Fits?")
print("=" * 70)

CONTEXT_WINDOWS = {"gpt-4o-mini": 128_000, "gpt-4o": 128_000, "claude-3-5-sonnet-20241022": 200_000}
avg_tokens_per_page = 500  # rough real-world estimate for a text-dense page

for model, window in CONTEXT_WINDOWS.items():
    pages = window // avg_tokens_per_page
    print(f"  {model:30s}: {window:,} tokens ≈ {pages} pages of text fit in ONE context window")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Embeddings — Turning Text Into Vectors
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 5: Embeddings + Cosine Similarity")
print("=" * 70)


def get_embedding(text: str):
    if not HAS_KEY:
        # Deterministic mock embedding so the demo still runs without a key —
        # NOT a real embedding, just enough to demonstrate the cosine-similarity math.
        import hashlib
        h = hashlib.sha256(text.encode()).digest()
        return [b / 255.0 for b in h[:16]]
    from openai import OpenAI
    client = OpenAI()
    resp = client.embeddings.create(model="text-embedding-3-small", input=text)
    return resp.data[0].embedding


def cosine_similarity(a, b):
    import math
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0


sentences = [
    "The cat sat on the mat.",
    "A feline rested on the rug.",
    "The stock market crashed today.",
]

if not HAS_KEY:
    print("\n  [NO_API_KEY — using a deterministic mock embedding so the math still runs.")
    print("   Mock similarities will NOT reflect real semantic meaning — set")
    print("   OPENAI_API_KEY to see sentence 1 & 2 score much higher than 1 & 3.]")

embeddings = {s: get_embedding(s) for s in sentences}
print(f"\n  Embedding dimension: {len(embeddings[sentences[0]])}")
print("\n  Pairwise similarity (1.0 = identical meaning, 0 = unrelated):")
for i in range(len(sentences)):
    for j in range(i + 1, len(sentences)):
        sim = cosine_similarity(embeddings[sentences[i]], embeddings[sentences[j]])
        print(f"    '{sentences[i][:30]}...' <-> '{sentences[j][:30]}...'  =  {sim:.3f}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Exercises
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 6: EXERCISES")
print("=" * 70)
print("""
EASY:
1. Tokenize your own name and 3 technical terms from your resume. Any surprises?

MEDIUM:
2. Take a real error log line from a project and count its tokens. Estimate
   the cost of sending 1000 of these to an LLM for classification.

HARD:
3. Build a tiny semantic search: embed 10 sentences, embed a query, return
   the top-3 by cosine similarity. (This IS the retrieval half of RAG — Level 5.)

PRO:
4. Compare tiktoken's o200k_base against cl100k_base on the same 20 sentences.
   Which model family tokenizes more efficiently for your domain's vocabulary?
""")

if __name__ == "__main__":
    print("\nDone. Next: 03_history_of_llms_practical.py")
