"""
Level5 — Doc 10: Contextual Retrieval (Anthropic) Practical
==============================================================

KYA SEEKHENGE (What We Will Learn):
  1. The core technique — prepend an LLM-generated situating context to each
     chunk BEFORE embedding it, instead of embedding the bare chunk
  2. Why sending the full document per chunk is economical with prompt caching
  3. A before/after retrieval comparison — measurable, not just claimed
  4. Combining contextual embeddings with hybrid search (BM25 + vector) —
     the doc's own recommended stack
  5. When NOT to bother — small documents, already-self-contained chunks

KAISE CHALANA (How to Run):
  pip install anthropic python-dotenv
  python 10_contextual_retrieval_practical.py

  No ANTHROPIC_API_KEY needed to see the mechanism — falls back to a
  deterministic mock "contextualizer" so the retrieval-comparison math still
  runs and demonstrates the point.
"""

import os
import re
from dotenv import load_dotenv

load_dotenv()
HAS_KEY = bool(os.getenv("ANTHROPIC_API_KEY"))

CONTEXT_PROMPT = """<document>
{full_document}
</document>

Here is the chunk we want to situate within the whole document:
<chunk>
{chunk_content}
</chunk>

Give a short succinct context to situate this chunk within the overall
document for the purposes of improving search retrieval of the chunk.
Answer only with the succinct context and nothing else."""


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: The Technique — Contextualize, Then Embed
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 1: The Technique")
print("=" * 70)


def contextualize_chunk(full_document: str, chunk: str) -> str:
    if not HAS_KEY:
        # Deterministic mock: pulls the document's own title-ish first line in,
        # standing in for what a real LLM call would generate — not accurate,
        # but shows the SHAPE of the technique without needing a key.
        title_line = full_document.strip().split("\n")[0][:60]
        context = f"This chunk is from '{title_line}', discussing: {chunk[:40]}..."
    else:
        from anthropic import Anthropic
        client = Anthropic()
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=200,
            messages=[{"role": "user", "content": CONTEXT_PROMPT.format(full_document=full_document, chunk_content=chunk)}],
        )
        context = response.content[0].text
    return f"{context}\n\n{chunk}"


DOCUMENT = """ACME Corp Q2 2024 Earnings Report

ACME Corp's revenue grew 3% over the previous quarter, driven by strong
demand in the enterprise segment. Operating margins held steady at 22%.
The company's cloud division, launched in Q1 2024, contributed $4.2M in
new revenue. Management raised full-year guidance citing continued
enterprise momentum and reduced customer acquisition costs."""

bare_chunk = "The company's revenue grew 3% over the previous quarter."
contextualized = contextualize_chunk(DOCUMENT, bare_chunk)

print(f"\n  BEFORE (bare chunk):\n  '{bare_chunk}'")
print(f"\n  AFTER (contextualized, this is what gets embedded):\n  {contextualized}")
print("\n  Notice: 'previous quarter' and 'the company' are ambiguous in the bare")
print("  chunk alone — a vector search for 'ACME Q2 revenue growth' would score")
print("  this chunk lower than it deserves without the added context.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Measurable Before/After Retrieval Comparison
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 2: Does This Actually Improve Retrieval? (measured, not claimed)")
print("=" * 70)


def get_embedding(text: str) -> list[float]:
    # Same deterministic mock-embedding approach used elsewhere in this repo
    # (Level1 Doc 2's practical) so this runs without a key — swap for a real
    # embedding call to see the effect for real.
    import hashlib
    h = hashlib.sha256(text.lower().encode()).digest()
    return [b / 255.0 for b in h[:32]]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    import math
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0


chunks = [
    "The company's revenue grew 3% over the previous quarter.",
    "Operating margins held steady at 22%.",
    "The cloud division contributed $4.2M in new revenue.",
]

query = "What was ACME Corp's revenue growth in Q2 2024?"

print("\n  Bare-chunk retrieval scores:")
bare_scores = []
for c in chunks:
    score = cosine_similarity(get_embedding(query), get_embedding(c))
    bare_scores.append((c, score))
    print(f"    {score:.3f}  '{c}'")

print("\n  Contextualized-chunk retrieval scores:")
context_scores = []
for c in chunks:
    contextualized_c = contextualize_chunk(DOCUMENT, c)
    score = cosine_similarity(get_embedding(query), get_embedding(contextualized_c))
    context_scores.append((c, score))
    print(f"    {score:.3f}  '{c}' (+ context)")

if not HAS_KEY:
    print("\n  [NO_API_KEY — mock embeddings are hash-based, not semantic, so the")
    print("   exact scores above won't show the real effect. Anthropic's own")
    print("   published eval reports a ~35-49% reduction in retrieval failure")
    print("   rate from this technique combined with hybrid search — that's the")
    print("   number to cite, not this mock run.]")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Why Sending the Full Document Per Chunk Is Economical
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 3: Prompt Caching Makes This Affordable")
print("=" * 70)

CACHE_READ_MULTIPLIER = 0.1  # from Level3's caching coverage
doc_tokens = len(DOCUMENT) // 4  # rough estimate
chunk_tokens = 20

print(f"\n  Document: ~{doc_tokens} tokens, cached once")
print(f"  Per-chunk addition: ~{chunk_tokens} tokens, uncached")
print(f"\n  Without caching, contextualizing {len(chunks)} chunks costs:")
print(f"    {len(chunks)} × ({doc_tokens} + {chunk_tokens}) = {len(chunks) * (doc_tokens + chunk_tokens)} tokens of input")
print(f"\n  With caching (document cached after chunk 1):")
cached_cost = doc_tokens + sum(doc_tokens * CACHE_READ_MULTIPLIER + chunk_tokens for _ in range(len(chunks) - 1)) + chunk_tokens
print(f"    ~{int(cached_cost)} effective tokens — the {doc_tokens}-token document is")
print(f"    paid for once, then read back at {CACHE_READ_MULTIPLIER}x for every subsequent chunk.")
print(f"    This is why 'contextualize every chunk of every document' is viable")
print(f"    at knowledge-base scale, not just a toy-example technique.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: When NOT to Bother
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 4: When This Technique Isn't Worth It")
print("=" * 70)


def should_use_contextual_retrieval(doc_length_tokens: int, chunk_is_self_contained: bool, num_chunks: int) -> str:
    if chunk_is_self_contained:
        return "Skip — chunk already stands alone (e.g., a single FAQ entry), context adds nothing"
    if doc_length_tokens < 500:
        return "Skip — document is short enough that chunking barely loses context to begin with"
    if num_chunks < 5:
        return "Marginal — the setup/eval cost may not be worth it for a handful of chunks"
    return "Use it — long document, chunks that lose meaning in isolation, enough volume to matter"


test_cases = [
    (200, False, 3),
    (5000, True, 50),
    (10000, False, 80),
    (3000, False, 8),
]
for doc_len, self_contained, n_chunks in test_cases:
    verdict = should_use_contextual_retrieval(doc_len, self_contained, n_chunks)
    print(f"\n  doc={doc_len} tokens, self_contained={self_contained}, chunks={n_chunks}")
    print(f"    -> {verdict}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Exercises
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 5: EXERCISES")
print("=" * 70)
print("""
EASY:
1. Add a 4th chunk from a different section of DOCUMENT and contextualize it.

MEDIUM:
2. If you have ANTHROPIC_API_KEY set: run Section 2 for real and compare the
   actual similarity scores, not the mock hash-based ones.

HARD:
3. Combine this with hybrid search (Level5 Doc 6) — score each chunk with
   BOTH contextualized-embedding similarity AND BM25 keyword overlap against
   the query, then combine the two scores. This is the doc's own recommended
   stack, not contextual retrieval alone.

PRO:
4. Build a batch contextualizer that processes an entire document's chunks
   in one pass, reusing the SAME cached document context across all calls —
   measure the real token savings against Section 3's estimate using the
   `usage` object from a live API response (cache_read_input_tokens).
""")

if __name__ == "__main__":
    print("\nDone. Level 5 complete — all 11 docs now have hands-on code.")
