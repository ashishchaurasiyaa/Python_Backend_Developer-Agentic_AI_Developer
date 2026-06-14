"""
Level5 — Doc 7: Reranking (Cross-Encoder) Practical Lab
=========================================================

KYA SEEKHENGE (What we will learn):
  1. Bi-Encoder vs Cross-Encoder — difference aur kab use karein
  2. Manual reranking logic — pure Python, koi library nahi chahiye
  3. Cross-encoder simulate karna — cosine similarity + BM25 combined score
  4. Multi-stage pipeline build karna — top-20 retrieve → top-5 rerank
  5. Cohere Rerank API ka pattern (offline demo)
  6. Latency trade-off samajhna — fast vs accurate
  7. MRR (Mean Reciprocal Rank) metric se reranking evaluate karna
  8. Live LLM call with reranked context (GROQ free tier)

KAISE CHALANA (How to run):
  uv run --project /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/my-agentic-ai-project python /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/Level5_RAG_Vector_Databases/07_reranking_practical.py

NO KEY MODE (offline demo automatic):
  env -u GROQ_API_KEY uv run --project ... python 07_reranking_practical.py

HEAVY OPTIONAL LIBS (lazy-imported, fallback agar na ho):
  - sentence-transformers  (real cross-encoder)
  - chromadb               (vector store)
  - cohere                 (API-based reranker)

Theory grounding:
  /Level5_RAG_Vector_Databases/07_reranking.md
"""

import os
import math
import time
import random
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field

# ─────────────────────────────────────────────────────────────────────────────
# CLIENT SETUP — Groq free tier use karo, placeholder se crash nahi hoga
# INTERVIEW: OpenAI() None key pe crash karta hai, isliye get_client() pattern use karo
# ─────────────────────────────────────────────────────────────────────────────

def get_client():
    """
    Groq free client return karta hai.
    Agar GROQ_API_KEY nahi hai to placeholder use hoga — import hoga but call skip hoga.
    Production mein real key chahiye, yahan gracefully degrade karta hai.
    """
    from openai import OpenAI
    return OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=os.getenv("GROQ_API_KEY") or "placeholder",
    )

# Kya key hai? Iske basis pe LIVE_MODE decide hoga
GROQ_KEY = os.getenv("GROQ_API_KEY")
LIVE_MODE = bool(GROQ_KEY)

if not LIVE_MODE:
    print("[INFO] GROQ_API_KEY nahi mili — OFFLINE DEMO MODE, sab kuch fake data se chalega.")
    print("[INFO] Sab sections chalenge, koi crash nahi hoga.\n")

print("=" * 65)
print("RERANKING (CROSS-ENCODER) — Level 5 RAG Practical")
print("=" * 65)

# Concepts table — theory doc ke section 2 se grounded
RERANKING_CONCEPTS = {
    "Bi-Encoder":          "Query aur doc alag-alag encode karo, phir cosine similarity",
    "Cross-Encoder":       "Query + doc ek saath encode karo, direct relevance score milta hai",
    "Initial Retrieval":   "Fast bi-encoder se top-20 candidates nikalo (pre-computed embs)",
    "Reranking Pass":      "Slow cross-encoder se top-20 ko reorder karke top-5 nikalo",
    "Latency Trade-off":   "+500ms typical for open-source, +200ms for Cohere API",
    "When to Skip":        "Latency-tight (chat) ya cost-sensitive apps mein mat karo",
    "When to Use":         "Legal, medical, accuracy-critical apps mein hamesha karo",
    "Production Pipeline": "BM25(100) → Vector(100) → RRF(40) → CrossEncoder(5) → LLM",
    "MRR Metric":         "Mean Reciprocal Rank — relevant doc kitni jaldi aaya, higher better",
    "Best Open Source":    "BAAI/bge-reranker-v2-m3 (multilingual, best quality)",
    "Best API":            "Cohere rerank-english-v3.0 ($1/1000 calls)",
}
print("\nCONCEPTS (Theory se seedha grounded):")
for k, v in RERANKING_CONCEPTS.items():
    print(f"  {k:<22}: {v}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Fake Knowledge Base Setup
# INTERVIEW: Real system mein yeh chunks vector DB se aate hain
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 1: Knowledge Base Setup")
print("=" * 65)

# Yeh hamara fake corpus hai — ek RAG system ka knowledge base
# Har doc ka ek relevance_tier bhi hai: 1=highly relevant, 3=noise
KNOWLEDGE_BASE = [
    {
        "id": "doc_0",
        "text": "Cross-encoder models encode the query and document together in a single forward pass, producing a direct relevance score between 0 and 1.",
        "relevance_tier": 1,  # query ke liye sabse relevant
    },
    {
        "id": "doc_1",
        "text": "Vector databases like ChromaDB, Pinecone, and Weaviate store embedding vectors and support approximate nearest-neighbor search.",
        "relevance_tier": 3,  # noise — relevant nahi
    },
    {
        "id": "doc_2",
        "text": "Bi-encoder models encode the query and document separately. Pre-computed document embeddings make retrieval fast at query time.",
        "relevance_tier": 2,  # medium relevant
    },
    {
        "id": "doc_3",
        "text": "RAG pipeline: user query → retrieve relevant chunks → augment the prompt → generate final answer with LLM.",
        "relevance_tier": 3,
    },
    {
        "id": "doc_4",
        "text": "Reranking is a second-pass refinement step. After initial retrieval of top-20 candidates, a reranker re-scores and picks the best top-3 to top-5.",
        "relevance_tier": 1,  # very relevant
    },
    {
        "id": "doc_5",
        "text": "BM25 is a classical keyword-based retrieval algorithm. It matches exact terms but misses semantic meaning.",
        "relevance_tier": 3,
    },
    {
        "id": "doc_6",
        "text": "Cross-encoder quality is much higher than bi-encoder but much slower because document embeddings cannot be pre-computed.",
        "relevance_tier": 1,  # very relevant
    },
    {
        "id": "doc_7",
        "text": "Cohere Rerank API (rerank-english-v3.0) is the best off-the-shelf reranker, costing $1 per 1000 calls.",
        "relevance_tier": 2,
    },
    {
        "id": "doc_8",
        "text": "BAAI/bge-reranker-v2-m3 is the best open-source reranker model. It supports multiple languages including Hindi and Chinese.",
        "relevance_tier": 2,
    },
    {
        "id": "doc_9",
        "text": "Chunking strategies: fixed-size, semantic, sentence-aware. Overlap between chunks ensures context is not lost at boundaries.",
        "relevance_tier": 3,
    },
    {
        "id": "doc_10",
        "text": "In production RAG: BM25 retrieves top-100, vector search retrieves top-100, RRF fusion gives top-40, cross-encoder reranks to top-5.",
        "relevance_tier": 1,
    },
    {
        "id": "doc_11",
        "text": "Hybrid search combines BM25 (keyword) and dense vector retrieval using Reciprocal Rank Fusion (RRF) for better coverage.",
        "relevance_tier": 3,
    },
    {
        "id": "doc_12",
        "text": "MRR (Mean Reciprocal Rank) measures how early the first relevant document appears in the ranked list. Higher MRR means better reranking.",
        "relevance_tier": 2,
    },
    {
        "id": "doc_13",
        "text": "For latency-sensitive applications like chat, reranking may be skipped. For accuracy-critical apps like legal or medical, always rerank.",
        "relevance_tier": 1,
    },
    {
        "id": "doc_14",
        "text": "LangChain provides many document loaders for PDFs, web pages, CSVs, and Notion pages to feed into RAG pipelines.",
        "relevance_tier": 3,
    },
]

print(f"\n  Knowledge base mein {len(KNOWLEDGE_BASE)} documents hain.")
print("  Har doc ka relevance_tier: 1=best, 3=noise")
tier_counts = {1: 0, 2: 0, 3: 0}
for doc in KNOWLEDGE_BASE:
    tier_counts[doc["relevance_tier"]] += 1
for tier, cnt in tier_counts.items():
    label = {1: "Highly Relevant", 2: "Moderately Relevant", 3: "Noise/Off-topic"}[tier]
    print(f"  Tier {tier} ({label}): {cnt} docs")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Bi-Encoder Simulation (Fast Initial Retrieval)
# INTERVIEW: Yeh sirf cosine similarity hai — fast lekin "noisy"
# Theory doc Section 2: "Bi-encoder encodes query and doc SEPARATELY"
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 2: Bi-Encoder — Fast Initial Retrieval (Simulated)")
print("=" * 65)

BI_ENCODER_CODE = '''\
# Theory: Bi-encoder ka pattern
from sentence_transformers import SentenceTransformer
import numpy as np

model = SentenceTransformer("all-MiniLM-L6-v2")

# Document embeddings PRE-COMPUTE ho jaate hain — ek baar index banao
doc_embeddings = model.encode([doc["text"] for doc in corpus])  # offline ho sakta hai

# Query time pe sirf query encode karo (fast!)
query_emb = model.encode([query])

# Cosine similarity se top-k nikalo — O(N) lekin vectorized hai
similarities = np.dot(query_emb, doc_embeddings.T)[0]
top_k_idx = np.argsort(similarities)[::-1][:k]
'''
print("\n  Bi-Encoder Code Pattern (library needed):")
print("  " + "\n  ".join(BI_ENCODER_CODE.strip().split("\n")))


def simple_tfidf_score(query: str, doc_text: str) -> float:
    """
    Lightweight TF-IDF jaise score — sentence-transformers ke bina.
    INTERVIEW: Yeh bi-encoder simulate karta hai (fast, keyword-based proxy).
    Real system mein actual embedding model hota hai.
    """
    query_words = set(query.lower().split())
    doc_words = doc_text.lower().split()
    doc_word_set = set(doc_words)

    # Term frequency — kitne query words doc mein hain
    overlap = len(query_words & doc_word_set)
    if overlap == 0:
        return 0.0

    # IDF jaise boost — rare words zyada valuable hain
    tf = overlap / max(len(doc_words), 1)

    # Length normalization
    score = tf * math.log(1 + overlap)
    return round(score, 4)


def bi_encoder_retrieve(query: str, corpus: List[Dict], top_k: int = 10) -> List[Dict]:
    """
    Step 1 — Fast initial retrieval.
    INTERVIEW: Bi-encoder top-20 candidates return karta hai.
    Yahan hum keyword similarity use kar rahe hain (library nahi chahiye).
    """
    scored = []
    for doc in corpus:
        score = simple_tfidf_score(query, doc["text"])
        scored.append({**doc, "bi_encoder_score": score})

    # Sort by score descending, top_k lo
    scored.sort(key=lambda x: -x["bi_encoder_score"])
    return scored[:top_k]


# Test karo
QUERY = "How does cross-encoder reranking work and when should I use it?"
print(f"\n  Query: '{QUERY}'")

initial_candidates = bi_encoder_retrieve(QUERY, KNOWLEDGE_BASE, top_k=8)
print(f"\n  Bi-Encoder top-8 candidates (fast, noisy):")
print(f"  {'Rank':<5} {'Doc ID':<10} {'BiEnc Score':<14} {'Tier':<6} {'Text preview'}")
print("  " + "-" * 70)
for rank, doc in enumerate(initial_candidates, 1):
    preview = doc["text"][:55] + "..."
    print(f"  {rank:<5} {doc['id']:<10} {doc['bi_encoder_score']:<14} {doc['relevance_tier']:<6} {preview}")

# INTERVIEW: Dekhte hain kitne tier-1 docs initial retrieval mein aaye
tier1_in_initial = sum(1 for d in initial_candidates if d["relevance_tier"] == 1)
print(f"\n  Initial retrieval mein tier-1 (best) docs: {tier1_in_initial}/{tier_counts[1]}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Cross-Encoder Simulation (Accurate Reranking)
# INTERVIEW: Query + doc ek saath dekha jaata hai — zyada accurate lekin slow
# Theory doc Section 2: "[query, doc] → encoder → relevance_score (0-1)"
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 3: Cross-Encoder — Accurate Reranking (Simulated)")
print("=" * 65)

CROSS_ENCODER_CODE = '''\
# Theory: Cross-encoder ka real pattern
from sentence_transformers import CrossEncoder

reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

def rerank_with_cross_encoder(query, candidates, k_final=5):
    # Query + doc pairs ek saath — yahi cross-encoder ki khasiyat hai
    pairs = [[query, doc["text"]] for doc in candidates]

    # Har pair ke liye ek relevance score milta hai
    scores = reranker.predict(pairs)   # <-- slow, can\'t pre-compute

    # Sort by reranker score
    ranked = sorted(zip(candidates, scores), key=lambda x: -x[1])
    return ranked[:k_final]
'''
print("\n  Cross-Encoder Code Pattern (library needed):")
print("  " + "\n  ".join(CROSS_ENCODER_CODE.strip().split("\n")))


def cross_encoder_score(query: str, doc_text: str) -> float:
    """
    Cross-encoder simulate karta hai — query aur doc mein DEEP overlap dekhta hai.
    INTERVIEW: Real cross-encoder ek neural model hai jo [CLS, query, SEP, doc, SEP]
    input leta hai aur single relevance score deta hai.
    Yahan hum ek richer similarity calculate karte hain — bigram overlap bhi include.
    """
    query_lower = query.lower()
    doc_lower = doc_text.lower()

    # Unigram overlap
    q_words = set(query_lower.split())
    d_words = set(doc_lower.split())
    unigram_overlap = len(q_words & d_words)

    # Bigram overlap — phrase matching (cross-encoder yeh implicitly karta hai)
    q_bigrams = set(zip(query_lower.split(), query_lower.split()[1:]))
    d_bigrams = set(zip(doc_lower.split(), doc_lower.split()[1:]))
    bigram_overlap = len(q_bigrams & d_bigrams)

    # Key concept boosting — agar doc mein key technical terms hain
    key_terms = ["cross-encoder", "rerank", "cross encoder", "relevance score",
                 "reranking", "bi-encoder", "latency", "mrr", "production"]
    term_bonus = sum(1 for t in key_terms if t in doc_lower)

    # Combined score — cross-encoder ki "joint reasoning" simulate karta hai
    raw = (unigram_overlap * 1.0) + (bigram_overlap * 3.0) + (term_bonus * 2.0)

    # Normalize to 0-1 range (approx)
    doc_len = max(len(doc_lower.split()), 1)
    score = raw / (doc_len * 0.2 + 10)
    return round(min(score, 1.0), 4)


def cross_encoder_rerank(
    query: str,
    candidates: List[Dict],
    k_final: int = 5,
) -> List[Dict]:
    """
    Step 2 — Accurate reranking.
    INTERVIEW: Cross-encoder candidates ko re-score karta hai.
    Har (query, doc) pair ke liye alag call — isliye slow hai.
    Production mein: top-20 candidates pe 20 forward passes.
    """
    reranked = []
    for doc in candidates:
        ce_score = cross_encoder_score(query, doc["text"])
        reranked.append({**doc, "cross_encoder_score": ce_score})

    reranked.sort(key=lambda x: -x["cross_encoder_score"])
    return reranked[:k_final]


# INTERVIEW: Full pipeline — initial retrieve → rerank
reranked_results = cross_encoder_rerank(QUERY, initial_candidates, k_final=5)

print(f"\n  Cross-Encoder reranked top-5 (accurate):")
print(f"  {'Rank':<5} {'Doc ID':<10} {'CE Score':<12} {'BiEnc':<10} {'Tier':<6} {'Text preview'}")
print("  " + "-" * 70)
for rank, doc in enumerate(reranked_results, 1):
    preview = doc["text"][:50] + "..."
    print(f"  {rank:<5} {doc['id']:<10} {doc['cross_encoder_score']:<12} {doc['bi_encoder_score']:<10} {doc['relevance_tier']:<6} {preview}")

tier1_in_reranked = sum(1 for d in reranked_results if d["relevance_tier"] == 1)
print(f"\n  Reranked top-5 mein tier-1 (best) docs: {tier1_in_reranked}/{tier_counts[1]}")
print("  INTERVIEW: Cross-encoder ne noise reduce kiya aur best docs upar laaya.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Multi-Stage Production Pipeline
# Theory doc Section 7: "Query → BM25(100) → Vector(100) → RRF(40) → CrossEncoder(5)"
# INTERVIEW: Real production system mein yahi hota hai
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 4: Multi-Stage Production Pipeline")
print("=" * 65)

print("""
  Theory doc ka production pipeline (Section 7):
  ┌─────────────────────────────────────────────────────────┐
  │  Query                                                  │
  │    │                                                    │
  │    ├─► BM25 keyword search     → top 100, ~10ms        │
  │    ├─► Vector semantic search  → top 100, ~50ms        │
  │    │                                                    │
  │    ├─► RRF Fusion (merge both) → top  40,  ~5ms        │
  │    │                                                    │
  │    └─► Cross-Encoder rerank    → top   5, ~500ms       │
  │                                                         │
  │    └─► LLM generates answer with top-5 context         │
  └─────────────────────────────────────────────────────────┘
  Total latency before LLM: ~600ms
""")


@dataclass
class PipelineStage:
    name: str
    input_count: int
    output_count: int
    latency_ms: float
    method: str


def simulate_production_pipeline(query: str, corpus: List[Dict]) -> Dict:
    """
    Production-grade multi-stage pipeline simulate karta hai.
    INTERVIEW: Har stage agressively filter karta hai — quality improve hoti hai.
    """
    stages: List[PipelineStage] = []
    timings = {}

    print(f"  Pipeline for: '{query[:60]}'")

    # Stage 1: BM25 keyword retrieval (fast, keyword-based)
    t0 = time.time()
    bm25_candidates = bi_encoder_retrieve(query, corpus, top_k=min(len(corpus), 12))
    # Simulate BM25 being faster — yahan hum same function use kar rahe hain for demo
    t_bm25 = (time.time() - t0) * 1000 + 10  # add simulated overhead
    stages.append(PipelineStage("BM25", len(corpus), len(bm25_candidates), t_bm25, "keyword"))
    print(f"\n  Stage 1 — BM25: {len(corpus)} docs → {len(bm25_candidates)} candidates ({t_bm25:.1f}ms simulated)")

    # Stage 2: Vector search (semantic, slightly slower)
    t0 = time.time()
    vector_candidates = bi_encoder_retrieve(query, corpus, top_k=min(len(corpus), 12))
    t_vec = (time.time() - t0) * 1000 + 50
    stages.append(PipelineStage("Vector", len(corpus), len(vector_candidates), t_vec, "semantic"))
    print(f"  Stage 2 — Vector: {len(corpus)} docs → {len(vector_candidates)} candidates ({t_vec:.1f}ms simulated)")

    # Stage 3: RRF Fusion — BM25 aur vector results ko merge karo
    # RRF formula: sum(1 / (rank + k)) for each doc across all lists
    def rrf_fusion(lists: List[List[Dict]], k: int = 60) -> List[Dict]:
        scores: Dict[str, float] = {}
        doc_map: Dict[str, Dict] = {}
        for lst in lists:
            for rank, doc in enumerate(lst, 1):
                doc_id = doc["id"]
                scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (rank + k)
                doc_map[doc_id] = doc
        sorted_ids = sorted(scores, key=lambda x: -scores[x])
        return [{**doc_map[did], "rrf_score": round(scores[did], 6)} for did in sorted_ids]

    t0 = time.time()
    fused = rrf_fusion([bm25_candidates, vector_candidates])[:10]
    t_rrf = (time.time() - t0) * 1000 + 5
    stages.append(PipelineStage("RRF Fusion", len(bm25_candidates) + len(vector_candidates), len(fused), t_rrf, "fusion"))
    print(f"  Stage 3 — RRF Fusion: merge → {len(fused)} candidates ({t_rrf:.1f}ms simulated)")

    # Stage 4: Cross-encoder reranking — final quality pass
    t0 = time.time()
    final = cross_encoder_rerank(query, fused, k_final=5)
    t_ce = (time.time() - t0) * 1000 + 500  # simulate real cross-encoder latency
    stages.append(PipelineStage("Cross-Encoder", len(fused), len(final), t_ce, "reranking"))
    print(f"  Stage 4 — Cross-Encoder: {len(fused)} → {len(final)} final results ({t_ce:.1f}ms simulated)")

    total_latency = sum(s.latency_ms for s in stages)
    print(f"\n  Total pipeline latency: {total_latency:.0f}ms (before LLM call)")
    print(f"  Final top-5 results:")
    for i, doc in enumerate(final, 1):
        print(f"    {i}. [{doc['id']}] Tier={doc['relevance_tier']} CE={doc['cross_encoder_score']:.3f} — {doc['text'][:60]}...")

    return {"stages": stages, "final_results": final, "total_latency_ms": total_latency}


pipeline_result = simulate_production_pipeline(QUERY, KNOWLEDGE_BASE)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Latency Trade-off Analysis
# Theory doc Section 6: "Bi-encoder alone: ~50ms, +reranker: +500-2000ms"
# INTERVIEW: Kab reranking karo, kab skip karo
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 5: Latency Trade-off Analysis")
print("=" * 65)

@dataclass
class LatencyProfile:
    scenario: str
    retrieval_ms: float
    reranking_ms: float
    llm_ms: float
    use_reranking: bool
    use_case: str

profiles = [
    LatencyProfile("Chat (latency priority)",  50,    0,   800, False, "Reranking SKIP — user ko fast response chahiye"),
    LatencyProfile("Open-source reranker",     50, 1500,   800, True,  "Cohere-free — GPU chahiye, +1500ms"),
    LatencyProfile("Cohere API reranker",      50,  200,   800, True,  "Best quality — $1/1000 calls, +200ms"),
    LatencyProfile("Legal/Medical (accuracy)", 50, 1500,  1200, True,  "Accuracy critical — latency acceptable"),
]

print(f"\n  {'Scenario':<30} {'Retrieval':<12} {'Rerank':<10} {'LLM':<8} {'Total':<8} {'Decision'}")
print("  " + "-" * 85)
for p in profiles:
    total = p.retrieval_ms + p.reranking_ms + p.llm_ms
    decision = "USE" if p.use_reranking else "SKIP"
    print(f"  {p.scenario:<30} {p.retrieval_ms:<12.0f} {p.reranking_ms:<10.0f} {p.llm_ms:<8.0f} {total:<8.0f} {decision} — {p.use_case}")

print("""
  INTERVIEW ANSWER — Kab reranking use karo:
    USE:  Legal docs, medical records, code search, high-stakes decisions
    SKIP: Real-time chat, cost-sensitive bulk processing, when latency < 200ms required
    RULE: Quality vs Latency trade-off — business requirement decide karta hai
""")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Cohere Rerank API Pattern (Offline Demo)
# Theory doc Section 5: "co.rerank(model='rerank-english-v3.0', ...)"
# INTERVIEW: Production-ready API — best quality, easiest integration
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 65)
print("SECTION 6: Cohere Rerank API Pattern")
print("=" * 65)

COHERE_CODE = '''\
import cohere  # pip install cohere

co = cohere.Client(api_key=os.getenv("COHERE_API_KEY"))

def cohere_rerank(query: str, docs: List[str], top_n: int = 5):
    """
    Cohere ka API-based reranker — best off-the-shelf option.
    INTERVIEW: $1 per 1000 calls, +200ms latency, excellent quality.
    """
    response = co.rerank(
        model="rerank-english-v3.0",  # ya "rerank-multilingual-v3.0"
        query=query,
        documents=docs,
        top_n=top_n,
    )
    return [
        {"text": docs[r.index], "relevance_score": r.relevance_score}
        for r in response.results
    ]

# Usage:
# docs = [doc["text"] for doc in candidates]
# reranked = cohere_rerank(query, docs, top_n=5)
'''
print("\n  Cohere Rerank API code pattern:")
print("  " + "\n  ".join(COHERE_CODE.strip().split("\n")))

# Lazy import — cohere optional hai
print("\n  Cohere library check:")
try:
    import cohere  # type: ignore
    print("  [OK] cohere library installed — real API call possible")
except ImportError:
    print("  [INFO] cohere not installed — skipping. `pip install cohere` karein agar chahiye")
    print("  [INFO] Demo: offline simulation se same output dikhate hain")

    # Offline simulation — same interface
    def mock_cohere_rerank(query: str, docs: List[Dict], top_n: int = 5) -> List[Dict]:
        """Cohere API ka mock — offline demo ke liye."""
        # Cross-encoder simulation hi use karte hain
        scored = [
            {**doc, "relevance_score": cross_encoder_score(query, doc["text"])}
            for doc in docs
        ]
        scored.sort(key=lambda x: -x["relevance_score"])
        return scored[:top_n]

    mock_results = mock_cohere_rerank(QUERY, initial_candidates[:8], top_n=3)
    print("\n  Mock Cohere Rerank output (top-3):")
    for i, r in enumerate(mock_results, 1):
        print(f"    {i}. [{r['id']}] score={r['relevance_score']:.3f} — {r['text'][:60]}...")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: MRR Evaluation
# Theory doc Section 9: "MRR (Mean Reciprocal Rank)"
# INTERVIEW: Kitne achhe se reranker relevant doc ko top pe laaya
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 7: MRR Evaluation (Mean Reciprocal Rank)")
print("=" * 65)

def compute_mrr(ranked_docs: List[Dict], relevant_tier: int = 1) -> float:
    """
    MRR compute karo — cross-encoder ki quality measure karta hai.
    INTERVIEW:
      MRR = mean of (1/rank) for first relevant doc found.
      Agar rank=1 → 1.0, rank=2 → 0.5, rank=3 → 0.33, nahi mila → 0
      Higher MRR = better reranker.
    Theory doc Section 9 ka direct implementation.
    """
    for rank, doc in enumerate(ranked_docs, 1):
        if doc["relevance_tier"] <= relevant_tier:
            return 1.0 / rank
    return 0.0


# Multiple queries ke saath evaluate karo
eval_queries = [
    "How does cross-encoder reranking work and when should I use it?",
    "What is the difference between bi-encoder and cross-encoder?",
    "When should I skip reranking in production?",
    "What is the best open-source reranker model?",
]

print(f"\n  MRR Evaluation — {len(eval_queries)} queries pe:")
print(f"  {'Query':<55} {'BiEnc MRR':<12} {'CE MRR':<10} {'Improved?'}")
print("  " + "-" * 85)

mrr_scores = {"bi_encoder": [], "cross_encoder": []}

for q in eval_queries:
    # Bi-encoder results
    bi_results = bi_encoder_retrieve(q, KNOWLEDGE_BASE, top_k=8)
    bi_mrr = compute_mrr(bi_results)

    # Cross-encoder reranked results
    ce_results = cross_encoder_rerank(q, bi_results, k_final=5)
    ce_mrr = compute_mrr(ce_results)

    mrr_scores["bi_encoder"].append(bi_mrr)
    mrr_scores["cross_encoder"].append(ce_mrr)

    improved = "YES" if ce_mrr > bi_mrr else ("SAME" if ce_mrr == bi_mrr else "NO")
    q_preview = q[:52] + "..." if len(q) > 52 else q
    print(f"  {q_preview:<55} {bi_mrr:<12.3f} {ce_mrr:<10.3f} {improved}")

avg_bi_mrr = sum(mrr_scores["bi_encoder"]) / len(mrr_scores["bi_encoder"])
avg_ce_mrr = sum(mrr_scores["cross_encoder"]) / len(mrr_scores["cross_encoder"])

print(f"\n  Average MRR:")
print(f"    Bi-Encoder (initial retrieval): {avg_bi_mrr:.3f}")
print(f"    Cross-Encoder (reranked):       {avg_ce_mrr:.3f}")
improvement_pct = ((avg_ce_mrr - avg_bi_mrr) / max(avg_bi_mrr, 0.001)) * 100
print(f"    MRR improvement: {improvement_pct:+.1f}%")
print("  INTERVIEW: Higher MRR = relevant doc jaldi aaya = better reranker")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8: sentence-transformers Real CrossEncoder (Optional, Lazy Import)
# Theory doc Section 3: "from sentence_transformers import CrossEncoder"
# INTERVIEW: Production mein yahi use karte hain — library available ho to
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 8: Real CrossEncoder — sentence-transformers (Optional)")
print("=" * 65)

print("\n  sentence-transformers library check (lazy import):")
try:
    from sentence_transformers import CrossEncoder  # type: ignore
    print("  [OK] sentence-transformers installed!")
    print("  Real CrossEncoder available — downloading model would take ~50MB...")
    print("  Demo mein skip kar rahe hain (time/bandwidth bachane ke liye).")
    print("  Production code:")
    print("    reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')")
    print("    pairs = [[query, doc] for doc in candidates]")
    print("    scores = reranker.predict(pairs)  # actual neural scoring")
except ImportError:
    print("  [INFO] sentence-transformers not installed — graceful fallback.")
    print("  Install: pip install sentence-transformers")
    print("  Ya uv add sentence-transformers in your project.")
    print("  Simulated cross-encoder (Section 3) se kaam chala liya.")

# Popular models table — theory doc Section 4 se
print("""
  Popular CrossEncoder Models (Theory Section 4):
  ┌───────────────────────────────────────────────┬──────────┬─────────────┐
  │ Model                                         │ Size     │ Use Case    │
  ├───────────────────────────────────────────────┼──────────┼─────────────┤
  │ cross-encoder/ms-marco-MiniLM-L-6-v2          │ ~66MB    │ Lightweight │
  │ cross-encoder/ms-marco-MiniLM-L-12-v2         │ ~125MB   │ Better      │
  │ BAAI/bge-reranker-v2-m3 (BEST open-source)   │ ~570MB   │ Multilingual│
  │ BAAI/bge-reranker-large                       │ ~1.3GB   │ High quality│
  └───────────────────────────────────────────────┴──────────┴─────────────┘
  INTERVIEW: BAAI/bge-reranker-v2-m3 = best open-source choice (Hindi bhi!)
""")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 9: ChromaDB + Reranking Integration Pattern (Lazy Import)
# INTERVIEW: Real vector DB ke saath reranking kaise wire karte hain
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 65)
print("SECTION 9: ChromaDB + Reranking Integration (Optional)")
print("=" * 65)

CHROMA_RERANK_CODE = '''\
import chromadb
from sentence_transformers import CrossEncoder

# ChromaDB setup
client = chromadb.Client()
collection = client.create_collection("rag_docs")

# Documents add karo
collection.add(
    documents=[doc["text"] for doc in corpus],
    ids=[doc["id"] for doc in corpus],
)

# Step 1: ChromaDB se top-20 initial retrieval
results = collection.query(
    query_texts=[query],
    n_results=20,  # initial top-20
)
candidates = results["documents"][0]

# Step 2: Cross-encoder se rerank
reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
pairs = [[query, doc] for doc in candidates]
scores = reranker.predict(pairs)

# Step 3: Sort by cross-encoder score, top-5 lo
ranked = sorted(zip(candidates, scores), key=lambda x: -x[1])
top_5 = [doc for doc, _ in ranked[:5]]

# Step 4: LLM ko top-5 context de do
context = "\\n\\n".join(top_5)
'''

print("\n  ChromaDB + CrossEncoder integration code:")
print("  " + "\n  ".join(CHROMA_RERANK_CODE.strip().split("\n")))

print("\n  chromadb library check (lazy import):")
try:
    import chromadb  # type: ignore
    print("  [OK] chromadb installed — vector store ready")
    # Yahan real ChromaDB demo possible hai lekin skip kar rahe hain
    # (upar ka code pattern kaafi hai)
except ImportError:
    print("  [INFO] chromadb not installed — pattern code above dekho.")
    print("  Install: pip install chromadb  (ya uv add chromadb)")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 10: Live LLM Call with Reranked Context (GROQ)
# INTERVIEW: End-to-end RAG — retrieve → rerank → generate
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 10: Live LLM — Reranked Context se Answer Generate")
print("=" * 65)

def build_rag_prompt(query: str, top_docs: List[Dict]) -> str:
    """
    RAG prompt banao — top reranked docs context mein do.
    INTERVIEW: Reranked docs = higher quality context = better LLM answer.
    """
    context_parts = []
    for i, doc in enumerate(top_docs, 1):
        context_parts.append(f"[Doc {i}] {doc['text']}")
    context = "\n\n".join(context_parts)

    return f"""You are a helpful AI assistant. Answer the question using ONLY the provided context.

CONTEXT (top 5 reranked documents):
{context}

QUESTION: {query}

ANSWER:"""


# Final reranked docs use karo context ke liye
final_docs = pipeline_result["final_results"]
prompt = build_rag_prompt(QUERY, final_docs)

print(f"\n  Query: {QUERY}")
print(f"  Context: {len(final_docs)} reranked docs use ho rahe hain")

if LIVE_MODE:
    print("\n  [LIVE] GROQ API se answer generate ho raha hai...")
    try:
        client = get_client()
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",  # Groq free tier model
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.1,
        )
        answer = response.choices[0].message.content
        print(f"\n  LLM Answer (with reranked context):\n")
        # Answer ko wrap karke print karo
        words = answer.split()
        line = "  "
        for word in words:
            if len(line) + len(word) > 72:
                print(line)
                line = "  " + word + " "
            else:
                line += word + " "
        if line.strip():
            print(line)
    except Exception as e:
        print(f"  [WARN] LLM call fail hui: {e}")
        print("  [INFO] Offline mode mein switch ho rahe hain...")
        LIVE_MODE_ACTUAL = False
else:
    LIVE_MODE_ACTUAL = False

if not LIVE_MODE:
    print("\n  [OFFLINE] Fake LLM answer (key nahi hai):")
    fake_answer = (
        "Cross-encoder reranking works by encoding the query and document together "
        "in a single neural forward pass, producing a direct relevance score. "
        "You should use it for accuracy-critical applications (legal, medical) where "
        "the extra +500ms latency is acceptable. Skip it for real-time chat where "
        "speed is more important than perfect retrieval quality."
    )
    words = fake_answer.split()
    line = "  "
    for word in words:
        if len(line) + len(word) > 72:
            print(line)
            line = "  " + word + " "
        else:
            line += word + " "
    if line.strip():
        print(line)
    print("\n  Set GROQ_API_KEY for real LLM answer.")


# ─────────────────────────────────────────────────────────────────────────────
# FINAL SUMMARY — Theory ke key points recap
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("RERANKING INTERVIEW SUMMARY (Theory doc ke key takeaways):")
print("=" * 65)
print("""
  1. KYON RERANK?
     Initial retrieval (vector/BM25) fast hai lekin noisy.
     Top-20 mein sirf 5-7 truly relevant hote hain.
     Reranker un best 5 ko find karta hai.

  2. BI vs CROSS ENCODER:
     Bi-encoder:   query aur doc ALAG encode, cosine similarity
                   FAST (pre-computed), lekin less accurate
     Cross-encoder: query + doc SAATH encode, direct score
                   SLOW (can't pre-compute), zyada accurate

  3. PRODUCTION PATTERN:
     Bi-encoder → top 20 (fast)
     Cross-encoder → top 5 (slow but only 20 items)
     LLM gets only top-5 (quality context)

  4. MODELS:
     Open-source: BAAI/bge-reranker-v2-m3 (best, multilingual)
     API:         Cohere rerank-english-v3.0 ($1/1000 calls)

  5. LATENCY:
     Bi-encoder alone:         ~50ms
     + Open-source reranker:  +500-2000ms
     + Cohere API:             +200ms

  6. EVALUATION:
     MRR (Mean Reciprocal Rank) — higher = better reranking

  7. KAB USE KARO:
     USE:  Legal, medical, code search, accuracy-critical
     SKIP: Real-time chat, cost-sensitive, latency < 200ms
""")
print("=" * 65)
print("Lab complete! Exit 0.")
