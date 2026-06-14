"""
Level5 — Doc 6: Hybrid Search Practical (BM25 + Vector)
=========================================================
KYA SEEKHENGE:
  1. BM25 algorithm scratch se likhna — TF, IDF, length normalization
  2. Pure vector search (cosine similarity) — manual implementation
  3. Weighted score fusion  (alpha parameter ke saath)
  4. Reciprocal Rank Fusion (RRF) — rank-based better fusion
  5. Alpha tuning — e-commerce vs knowledge base vs conversational
  6. Hybrid vs pure vector comparison — kahan hybrid better hota hai
  7. Groq LLM ke saath live RAG demo (key ho toh)
  8. Production setup samajhna (Elasticsearch / Qdrant / Weaviate)

KAISE CHALANA:
  uv run python Level5_RAG_Vector_Databases/06_hybrid_search_practical.py

  Ya seedha /tmp se (no keys needed, offline demo):
  cd /tmp && uv run --project /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/my-agentic-ai-project \
      python "/Users/youngmanindia/Documents/PythonRevision/Agentic_AI/Level5_RAG_Vector_Databases/06_hybrid_search_practical.py"

THEORY GROUNDING:
  Theory file: Level5_RAG_Vector_Databases/06_hybrid_search.md
  - Pure vector search 70% accurate; hybrid (vector + BM25) = 85%+
  - BM25 = improved TF-IDF with length normalization
  - Reciprocal Rank Fusion (k=60) > weighted score fusion
  - Alpha = 0 (pure BM25), 0.5 (balanced), 1.0 (pure vector)

DEPENDENCIES:
  - numpy  (core project mein hai, hamesha available)
  - math, collections (stdlib — koi install nahi chahiye)
  - openai (groq compatible client — project mein hai)
  - rank_bm25 (optional — agar nahi mila toh scratch implementation use hogi)
  - chromadb, sentence-transformers (optional heavy libs — graceful fallback)
"""

import os
import sys
import math
import time
import random
from typing import List, Dict, Tuple, Any, Optional
from collections import defaultdict
from dataclasses import dataclass, field

# ─────────────────────────────────────────────────────────────────────────────
# GROQ CLIENT SETUP
# Theory: OpenAI-compatible API use karte hain groq ke saath
# Key nahi hai toh MOCK_MODE mein chalega — EXIT 0 guaranteed
# ─────────────────────────────────────────────────────────────────────────────

# Groq ka base URL — OpenAI client se kaam karta hai
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_MODEL = "llama3-8b-8192"  # free tier model on groq

# Key check — None pe OpenAI() crash karta hai isliye placeholder use karte hain
GROQ_KEY = os.getenv("GROQ_API_KEY") or "placeholder"
MOCK_MODE = (os.getenv("GROQ_API_KEY") is None)


def get_client():
    """
    Groq LLM client banata hai — OpenAI-compatible interface ke saath.
    Agar key nahi hai, toh bhi crash nahi karega (placeholder use karta hai).
    Actual call karne se pehle MOCK_MODE check karo.
    """
    from openai import OpenAI
    return OpenAI(api_key=GROQ_KEY, base_url=GROQ_BASE_URL)


# ─────────────────────────────────────────────────────────────────────────────
# OPTIONAL HEAVY LIBS — lazy import with fallback
# Theory: Production mein rank_bm25 ya vector DB use karte hain
# ─────────────────────────────────────────────────────────────────────────────

# rank_bm25 — agar hai toh use karo, warna scratch implementation
try:
    from rank_bm25 import BM25Okapi as _RankBM25
    RANK_BM25_AVAILABLE = True
except ImportError:
    RANK_BM25_AVAILABLE = False

# chromadb — optional vector DB
try:
    import chromadb  # type: ignore
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

# sentence-transformers — optional embedding model
try:
    from sentence_transformers import SentenceTransformer  # type: ignore
    SBERT_AVAILABLE = True
except ImportError:
    SBERT_AVAILABLE = False

# numpy — core project mein hamesha available hona chahiye
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False


# ─────────────────────────────────────────────────────────────────────────────
# HEADER PRINT
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 65)
print("HYBRID SEARCH — BM25 + VECTOR FUSION")
print("Theory: 06_hybrid_search.md | Level 5 — Doc 6")
print("=" * 65)

if MOCK_MODE:
    print("NOTE: GROQ_API_KEY nahi mila — MOCK MODE (offline demo)")
    print("      LLM calls skip honge, sabhi sections EXIT 0 ke saath chalenge\n")
else:
    print("GROQ_API_KEY mila — live LLM calls honge\n")

# Library status dikhao
print("Library availability:")
print(f"  numpy            : {'OK' if NUMPY_AVAILABLE else 'MISSING - install numpy'}")
print(f"  rank_bm25        : {'OK (using library)' if RANK_BM25_AVAILABLE else 'Not installed — scratch BM25 use hogi'}")
print(f"  chromadb         : {'OK' if CHROMADB_AVAILABLE else 'Not installed — in-memory fallback'}")
print(f"  sentence-transf. : {'OK' if SBERT_AVAILABLE else 'Not installed — mock embeddings'}")

# ─────────────────────────────────────────────────────────────────────────────
# SAMPLE CORPUS — ye documents hai jinme hum search karenge
# Mix of exact-term queries aur semantic queries dono ko demonstrate karne ke liye
# Theory doc se: proper nouns, code identifiers, exact terms — BM25 better hai
# ─────────────────────────────────────────────────────────────────────────────

CORPUS = [
    "Python 3.12 was released in October 2023 with significant performance improvements.",
    "Order #ABC-123 has been shipped and will arrive in 3-5 business days.",
    "FastAPI is a modern Python web framework for building REST APIs quickly.",
    "CEO of OpenAI is Sam Altman who returned in November 2023 after a brief removal.",
    "Machine learning models require large amounts of training data to generalize well.",
    "The function def calculate_total(items) sums up all item prices with tax.",
    "Q4 2024 revenue exceeded expectations reaching $2.3 billion total.",
    "Docker containers provide isolated environments for running applications consistently.",
    "Natural language processing helps computers understand and generate human text.",
    "PostgreSQL supports full-text search using tsvector and tsquery data types.",
    "LangChain provides abstractions for building LLM-powered applications easily.",
    "Vector databases like Pinecone and Qdrant store high-dimensional embeddings.",
    "RAG combines retrieval from knowledge base with generative AI for accurate answers.",
    "Transformer architecture uses attention mechanism to process sequences in parallel.",
    "Redis is an in-memory data store used for caching, sessions, and pub/sub messaging.",
]

print(f"\nCorpus mein {len(CORPUS)} documents hain")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: BM25 ALGORITHM — SCRATCH IMPLEMENTATION
# Theory: BM25 = improved TF-IDF with k1 (term saturation) aur b (length norm)
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 1: BM25 Algorithm — Scratch Implementation")
print("=" * 65)

# BM25 formula theory se:
# score(q, d) = sum over terms t in q:
#   IDF(t) * [TF(t,d) * (k1 + 1)] / [TF(t,d) + k1 * (1 - b + b * |d| / avgdl)]
#
# Parameters:
#   k1 = 1.5  — term frequency saturation (zyada repetition = diminishing returns)
#   b  = 0.75 — length normalization (long docs ko penalty)

BM25_K1 = 1.5   # term frequency saturation parameter
BM25_B  = 0.75  # document length normalization parameter


class ScratchBM25:
    """
    BM25 Okapi — scratch implementation, koi library nahi chahiye.
    Theory doc ki formula ko exactly follow karta hai.
    Interview mein: ye steps explain kar paana chahiye.
    """

    def __init__(self, corpus: List[str], k1: float = BM25_K1, b: float = BM25_B):
        # Documents ko tokenize karo (simple whitespace split, lowercase)
        self.k1 = k1
        self.b = b
        self.corpus = corpus
        self.n = len(corpus)

        # Tokenize — production mein NLTK/spacy use karte hain
        self.tokenized = [self._tokenize(doc) for doc in corpus]

        # Average document length calculate karo
        doc_lengths = [len(tokens) for tokens in self.tokenized]
        self.avgdl = sum(doc_lengths) / self.n if self.n > 0 else 1.0

        # Document frequency (DF) build karo — har term kitne docs mein hai
        self.df: Dict[str, int] = defaultdict(int)
        for tokens in self.tokenized:
            for term in set(tokens):  # set se duplicate count nahi hoga
                self.df[term] += 1

        # IDF precompute karo — rare terms ko zyada weight
        # Robertson formula (theory doc se): log((N - df + 0.5) / (df + 0.5))
        self.idf: Dict[str, float] = {}
        for term, df in self.df.items():
            self.idf[term] = math.log((self.n - df + 0.5) / (df + 0.5) + 1)

    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenizer — lowercase, split by whitespace + punctuation remove."""
        import re
        return re.sub(r'[^\w\s]', '', text.lower()).split()

    def get_scores(self, query: str) -> List[float]:
        """
        Query ke liye sabhi documents ka BM25 score calculate karo.
        Return: list of float scores (corpus ke same order mein)
        """
        query_tokens = self._tokenize(query)
        scores = []

        for doc_idx, doc_tokens in enumerate(self.tokenized):
            doc_len = len(doc_tokens)

            # Term frequency count karo is document mein
            tf_dict: Dict[str, int] = defaultdict(int)
            for token in doc_tokens:
                tf_dict[token] += 1

            doc_score = 0.0
            for term in query_tokens:
                if term not in self.idf:
                    continue  # Corpus mein nahi hai, skip

                tf = tf_dict.get(term, 0)
                idf = self.idf[term]

                # BM25 Okapi formula — theory doc se exactly
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / self.avgdl)
                doc_score += idf * numerator / denominator

            scores.append(doc_score)

        return scores

    def get_top_k(self, query: str, k: int = 5) -> List[Tuple[str, float]]:
        """Top K documents with BM25 scores."""
        scores = self.get_scores(query)
        indexed = sorted(enumerate(scores), key=lambda x: -x[1])[:k]
        return [(self.corpus[i], s) for i, s in indexed]


# BM25 demo
print("\nBM25 Parameters:")
print(f"  k1 = {BM25_K1}  (term frequency saturation — value badhane se repetition effect kam)")
print(f"  b  = {BM25_B}  (length normalization — 0=no norm, 1=full norm)")

# Library vs scratch selection
if RANK_BM25_AVAILABLE:
    print("\nrank_bm25 library available — library version use ho rahi hai")

    class LibraryBM25:
        """rank_bm25 library wrapper — same interface as ScratchBM25."""

        def __init__(self, corpus: List[str]):
            import re
            self.corpus = corpus
            tokenized = [re.sub(r'[^\w\s]', '', doc.lower()).split() for doc in corpus]
            self._bm25 = _RankBM25(tokenized)

        def get_scores(self, query: str) -> List[float]:
            import re
            tokens = re.sub(r'[^\w\s]', '', query.lower()).split()
            return list(self._bm25.get_scores(tokens))

        def get_top_k(self, query: str, k: int = 5) -> List[Tuple[str, float]]:
            scores = self.get_scores(query)
            indexed = sorted(enumerate(scores), key=lambda x: -x[1])[:k]
            return [(self.corpus[i], s) for i, s in indexed]

    bm25_engine = LibraryBM25(CORPUS)
else:
    print("\nrank_bm25 nahi mila — scratch BM25 use ho rahi hai (same results)")
    bm25_engine = ScratchBM25(CORPUS)

# BM25 test karo exact terms ke saath
print("\nBM25 Search Demo — exact terms pe best hota hai:")

bm25_test_queries = [
    ("Python 3.12 release date", "exact version mention"),
    ("Order #ABC-123 shipping", "exact order number"),
    ("CEO OpenAI Sam Altman", "proper noun match"),
    ("def calculate_total function", "code identifier"),
    ("Q4 2024 revenue", "exact numeric terms"),
]

for query, reason in bm25_test_queries:
    results = bm25_engine.get_top_k(query, k=2)
    print(f"\n  Query: '{query}' ({reason})")
    for doc, score in results:
        print(f"    Score {score:.3f}: {doc[:65]}...")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: VECTOR SEARCH — MOCK EMBEDDINGS (numpy cosine similarity)
# Theory: Vector search semantic similarity dhundta hai
# Note: Real embeddings ke liye sentence-transformers ya OpenAI API chahiye
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 2: Vector Search — Cosine Similarity")
print("=" * 65)


def mock_embed(text: str, dim: int = 64) -> List[float]:
    """
    Mock embedding — production mein sentence-transformers ya OpenAI use karo.
    Yahan hum deterministic random vector banate hain hash se.
    Note: Ye real semantics capture nahi karta — sirf demo ke liye.
    """
    rng = random.Random(hash(text.lower()[:30]))
    # Kuch seed words ke basis pe embedding ko shift karte hain
    # Taki semantically related words thoda similar ho jaye
    base = [rng.gauss(0, 1) for _ in range(dim)]

    # Crude semantic grouping — related topics pe similar bias
    topic_words = {
        "python": [1, 0, 0], "api": [0, 1, 0], "database": [0, 0, 1],
        "llm": [1, 1, 0], "vector": [0, 1, 1], "search": [1, 0, 1],
    }
    for word, bias in topic_words.items():
        if word in text.lower():
            for i, b in enumerate(bias):
                if i < dim:
                    base[i] += b * 2.0

    # Normalize to unit vector
    norm = math.sqrt(sum(x * x for x in base))
    return [x / norm for x in base] if norm > 0 else base


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """
    Cosine similarity — theory doc se: dot(a,b) / (|a| * |b|)
    Range: -1 to 1. Higher = more similar.
    Unit vectors ke liye = just dot product.
    """
    if NUMPY_AVAILABLE:
        va = np.array(a)
        vb = np.array(b)
        norm_a = np.linalg.norm(va)
        norm_b = np.linalg.norm(vb)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(va, vb) / (norm_a * norm_b))
    else:
        # Pure Python fallback
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


class VectorSearcher:
    """
    Simple in-memory vector search.
    Production mein: FAISS / Pinecone / Qdrant / pgvector use karte hain.
    """

    def __init__(self, corpus: List[str]):
        self.corpus = corpus
        print("  Documents ko embed kar rahe hain...")

        # Real embeddings ke liye sentence-transformers check karo
        if SBERT_AVAILABLE:
            print("  sentence-transformers available — real SBERT embeddings use ho rahi hain")
            model = SentenceTransformer("all-MiniLM-L6-v2")
            self.embeddings = model.encode(corpus).tolist()
        else:
            print("  sentence-transformers nahi mila — mock embeddings use ho rahi hain")
            print("  (Install karne ke liye: pip install sentence-transformers)")
            self.embeddings = [mock_embed(doc) for doc in corpus]

    def get_scores(self, query: str) -> List[float]:
        """Cosine similarity scores return karo query ke saath."""
        if SBERT_AVAILABLE:
            model = SentenceTransformer("all-MiniLM-L6-v2")
            q_emb = model.encode([query])[0].tolist()
        else:
            q_emb = mock_embed(query)
        return [cosine_similarity(q_emb, doc_emb) for doc_emb in self.embeddings]

    def get_top_k(self, query: str, k: int = 5) -> List[Tuple[str, float]]:
        """Top K documents with cosine similarity scores."""
        scores = self.get_scores(query)
        indexed = sorted(enumerate(scores), key=lambda x: -x[1])[:k]
        return [(self.corpus[i], s) for i, s in indexed]


vector_engine = VectorSearcher(CORPUS)

print("\nVector Search Demo — semantic queries pe best hota hai:")

vector_test_queries = [
    ("how to improve model performance", "concept-based query"),
    ("fast and quick framework", "synonym-rich query"),
    ("storing and indexing embeddings", "semantic meaning"),
]

for query, reason in vector_test_queries:
    results = vector_engine.get_top_k(query, k=2)
    print(f"\n  Query: '{query}' ({reason})")
    for doc, score in results:
        print(f"    Score {score:.4f}: {doc[:65]}...")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: SCORE NORMALIZATION
# Theory: BM25 aur vector scores ke ranges alag hote hain — normalize karna padta hai
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 3: Score Normalization")
print("=" * 65)


def normalize_scores(scores: List[float]) -> List[float]:
    """
    Min-Max normalization — scores ko 0-1 range mein laata hai.
    Theory: BM25 scores (e.g., 0-15) aur vector scores (0-1) ko
    combine karne se pehle normalize karna zaroori hai.
    Formula: (x - min) / (max - min)
    """
    if not scores:
        return []
    min_s = min(scores)
    max_s = max(scores)
    if max_s == min_s:
        # Sabhi scores same hain — zero vector return karo
        return [0.0] * len(scores)
    return [(s - min_s) / (max_s - min_s) for s in scores]


# Normalization visualize karo
demo_bm25_scores = [0.0, 3.2, 8.7, 1.5, 12.4, 0.3]
demo_vec_scores  = [0.41, 0.73, 0.55, 0.89, 0.62, 0.48]

print("\nNormalization demo:")
print(f"  BM25 raw scores:       {[f'{s:.2f}' for s in demo_bm25_scores]}")
print(f"  BM25 normalized (0-1): {[f'{s:.2f}' for s in normalize_scores(demo_bm25_scores)]}")
print(f"\n  Vector raw scores:     {[f'{s:.2f}' for s in demo_vec_scores]}")
print(f"  Vector norm. (0-1):    {[f'{s:.2f}' for s in normalize_scores(demo_vec_scores)]}")
print("\n  NOTE: Dono ko normalize karne ke baad hi combine kar sakte hain!")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: HYBRID SEARCH — WEIGHTED SCORE FUSION
# Theory: combined = alpha * vector_score + (1-alpha) * bm25_score
# alpha=0 → pure BM25, alpha=1 → pure vector, alpha=0.5 → balanced
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 4: Hybrid Search — Weighted Score Fusion")
print("=" * 65)


class HybridSearcher:
    """
    Theory doc ka main class — BM25 + Vector = Hybrid Search.
    alpha parameter se balance control karo:
      alpha = 0.0 → pure BM25 (keyword dominant)
      alpha = 0.5 → balanced (default)
      alpha = 1.0 → pure vector (semantic dominant)

    Use cases (theory doc se):
      E-commerce:    alpha = 0.3 (product names matter — keyword important)
      Knowledge base: alpha = 0.5 (balanced)
      Conversational: alpha = 0.7 (semantic dominant)
    """

    def __init__(
        self,
        corpus: List[str],
        bm25_engine: Any,
        vector_engine: VectorSearcher,
    ):
        self.corpus = corpus
        self.bm25 = bm25_engine
        self.vector = vector_engine

    def search(
        self,
        query: str,
        k: int = 5,
        alpha: float = 0.5,
    ) -> List[Tuple[str, float, float, float]]:
        """
        Hybrid search perform karo.
        Returns: list of (doc, combined_score, bm25_score_norm, vector_score_norm)
        alpha = vector ka weight (0 to 1)
        """
        # Step 1: Dono se scores lo
        bm25_raw   = self.bm25.get_scores(query)
        vector_raw = self.vector.get_scores(query)

        # Step 2: Normalize karo (0-1 range)
        bm25_norm   = normalize_scores(bm25_raw)
        vector_norm = normalize_scores(vector_raw)

        # Step 3: Weighted combine karo — theory formula
        # combined = alpha * vector + (1-alpha) * bm25
        combined = [
            alpha * v + (1 - alpha) * b
            for b, v in zip(bm25_norm, vector_norm)
        ]

        # Step 4: Top K
        indexed = sorted(enumerate(combined), key=lambda x: -x[1])[:k]
        return [
            (
                self.corpus[i],
                combined[i],
                bm25_norm[i],
                vector_norm[i],
            )
            for i, _ in indexed
        ]


hybrid = HybridSearcher(CORPUS, bm25_engine, vector_engine)

print("\nHybrid Search — alpha=0.5 (default balanced):")
HYBRID_QUERIES = [
    ("Python 3.12 release performance", 0.5),
    ("Order #ABC-123 delivery", 0.3),  # E-commerce alpha — keyword zyada
    ("how machine learning works concepts", 0.7),  # Conversational — semantic zyada
]

for query, alpha in HYBRID_QUERIES:
    print(f"\n  Query: '{query}' | alpha={alpha}")
    results = hybrid.search(query, k=3, alpha=alpha)
    for doc, combined, bm25_n, vec_n in results:
        print(f"    Combined={combined:.3f} | BM25={bm25_n:.3f} | Vec={vec_n:.3f}")
        print(f"    Doc: {doc[:60]}...")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: RECIPROCAL RANK FUSION (RRF)
# Theory: Rank positions use karo, normalized scores nahi
# RRF formula: score(d) = sum over ranked lists: 1 / (k + rank(d))
# k=60 standard parameter — top ranks ko boost karta hai
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 5: Reciprocal Rank Fusion (RRF) — Better Fusion")
print("=" * 65)

print("""
RRF Kyun Better Hai? (Theory Doc Se):
  - Score normalization ki zaroorat nahi (BM25 range vs vector range mismatch solve)
  - Rank positions use karta hai — stable aur robust
  - k=60 standard parameter — iske upar ke ranks ko mild boost milta hai
  - Formula: RRF_score(d) = sum_i [ 1 / (k + rank_i(d)) ]

Example:
  Document A: BM25 mein rank 1, Vector mein rank 3
    RRF = 1/(60+1) + 1/(60+3) = 0.01639 + 0.01587 = 0.03226

  Document B: BM25 mein rank 5, Vector mein rank 1
    RRF = 1/(60+5) + 1/(60+1) = 0.01538 + 0.01639 = 0.03177

  Document A slightly better — BM25 rank 1 ka zyada faayda
""")


def reciprocal_rank_fusion(
    ranked_lists: List[List[str]],
    k: int = 60,
) -> List[Tuple[str, float]]:
    """
    Theory doc ki RRF implementation.
    Input:  list of ranked document lists (best se worst order mein)
    Output: fused ranking with RRF scores

    k=60 standard parameter (Cormack et al., 2009 paper se)
    """
    rrf_scores: Dict[str, float] = defaultdict(float)

    for ranked_list in ranked_lists:
        for rank, doc in enumerate(ranked_list, start=1):
            # RRF formula: 1 / (k + rank)
            # rank=1 (best) → 1/61 = 0.0164 (max contribution)
            # rank=60      → 1/120 = 0.0083 (halved contribution)
            rrf_scores[doc] += 1.0 / (k + rank)

    return sorted(rrf_scores.items(), key=lambda x: -x[1])


# RRF demo karo
print("RRF Demo — two ranked lists fuse karna:")

query = "Python 3.12 performance improvements"

# BM25 ranked list
bm25_results = bm25_engine.get_top_k(query, k=8)
bm25_ranked = [doc for doc, _ in bm25_results]

# Vector ranked list
vec_results = vector_engine.get_top_k(query, k=8)
vec_ranked = [doc for doc, _ in vec_results]

# RRF fusion
fused = reciprocal_rank_fusion([bm25_ranked, vec_ranked], k=60)

print(f"\n  BM25 top 3:")
for i, doc in enumerate(bm25_ranked[:3], 1):
    print(f"    Rank {i}: {doc[:62]}...")

print(f"\n  Vector top 3:")
for i, doc in enumerate(vec_ranked[:3], 1):
    print(f"    Rank {i}: {doc[:62]}...")

print(f"\n  RRF fused top 5:")
for i, (doc, score) in enumerate(fused[:5], 1):
    print(f"    Rank {i} (score={score:.5f}): {doc[:55]}...")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: ALPHA TUNING COMPARISON
# Theory: Alpha ko domain ke hisaab se tune karo
# Evaluate different alpha values on test queries
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 6: Alpha Tuning — Domain-wise Comparison")
print("=" * 65)

print("""
Alpha Tuning Theory:
  alpha = 0.0 → pure BM25  (exact keywords pe focus)
  alpha = 0.3 → e-commerce (product names, SKUs, order numbers important)
  alpha = 0.5 → knowledge base (default, balanced)
  alpha = 0.7 → conversational Q&A (semantic understanding dominant)
  alpha = 1.0 → pure vector (only semantic meaning, no keyword matching)
""")

# Theory doc se: exact terms, proper nouns, code — BM25 better
# Concept-based, synonym-rich — vector better
ALPHA_TEST_CASES = [
    # (query, type, preferred_alpha_range)
    ("Python 3.12 release date",          "exact-term",    "0.0-0.3"),
    ("Order #ABC-123 status",             "proper-noun",   "0.0-0.3"),
    ("how to speed up model training",    "conceptual",    "0.5-1.0"),
    ("fast quick efficient performance",  "synonym-rich",  "0.5-1.0"),
    ("CEO OpenAI leadership",             "proper-noun",   "0.0-0.3"),
    ("understanding deep learning ideas", "conceptual",    "0.5-1.0"),
]

alphas = [0.0, 0.3, 0.5, 0.7, 1.0]

print(f"{'Query':<38} {'Best-alpha?':<12} " + " ".join(f"a={a:.1f}" for a in alphas))
print("-" * 95)

for query, qtype, preferred in ALPHA_TEST_CASES:
    # Top-1 document ka rank check karo different alphas ke liye
    rank_at_alpha = []
    for alpha in alphas:
        results = hybrid.search(query, k=len(CORPUS), alpha=alpha)
        # Best result ka score
        top_score = results[0][1] if results else 0.0
        rank_at_alpha.append(f"{top_score:.3f}")

    scores_str = " ".join(f"{s:>6}" for s in rank_at_alpha)
    q_display = query[:37]
    print(f"{q_display:<38} [{preferred:<10}] {scores_str}")

print("\n(Score = combined score of top-1 result. Higher = better retrieval at that alpha.)")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: HYBRID VS PURE VECTOR — DIRECT COMPARISON
# Theory: Hybrid = 10-20% better than vector alone on exact term queries
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 7: Hybrid vs Pure Vector — Where Hybrid Wins")
print("=" * 65)

print("""
Theory Doc Se — Hybrid Kab Better Hai:
  WIN cases (keyword terms important):
    - Exact version numbers ("Python 3.12", "Q4 2024")
    - Order/ID numbers ("#ABC-123", "order #12345")
    - Proper nouns (people, companies, places)
    - Code identifiers ("def calculate_x()")
    - Acronyms and abbreviations

  NEUTRAL/VECTOR FINE cases:
    - Concept-based queries ("how to improve performance")
    - Synonym-rich queries ("fast" vs "quick" vs "speedy")
    - Paraphrased questions
""")

# Comparison test
COMPARISON_TESTS = [
    ("Python 3.12 release date", True,  "exact version — hybrid should win"),
    ("Order #ABC-123",           True,  "order ID — hybrid should win"),
    ("how to make models faster", False, "concept — vector might be fine"),
    ("Sam Altman CEO",            True,  "proper noun — hybrid should win"),
    ("database performance tuning", False, "concept — vector should be ok"),
]

print(f"{'Query':<35} {'Vector Top1':<30} {'Hybrid Top1':<30}")
print("-" * 95)

for query, hybrid_should_win, reason in COMPARISON_TESTS:
    pure_vector = vector_engine.get_top_k(query, k=1)
    hybrid_res  = hybrid.search(query, k=1, alpha=0.5)

    v_doc = pure_vector[0][0][:28] + "..." if pure_vector else "N/A"
    h_doc = hybrid_res[0][0][:28] + "..." if hybrid_res else "N/A"

    tag = "[HYB WINS]" if hybrid_should_win else "[VEC OK]  "
    print(f"{tag} {query[:33]:<33}")
    print(f"         Vector:  {v_doc}")
    print(f"         Hybrid:  {h_doc}")
    print(f"         Reason:  {reason}")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8: PRODUCTION RAG PIPELINE WITH HYBRID SEARCH
# Theory: Query → Hybrid retrieve → LLM generate answer
# Full pipeline: chunking → indexing → hybrid retrieval → generation
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 65)
print("SECTION 8: Production RAG Pipeline (Hybrid Search + LLM)")
print("=" * 65)


def hybrid_rag_pipeline(
    question: str,
    corpus: List[str],
    bm25_eng: Any,
    vec_eng: VectorSearcher,
    alpha: float = 0.5,
    top_k: int = 3,
) -> str:
    """
    Complete RAG pipeline:
      1. Hybrid search se relevant docs retrieve karo
      2. Context banao (retrieved docs ko join karo)
      3. LLM ko prompt karo context ke saath
      4. Answer return karo

    MOCK_MODE mein: LLM call skip, context return karo
    """
    hybrid_searcher = HybridSearcher(corpus, bm25_eng, vec_eng)

    # Step 1: Hybrid retrieval
    results = hybrid_searcher.search(question, k=top_k, alpha=alpha)
    retrieved_docs = [doc for doc, _, _, _ in results]
    context = "\n\n".join(
        f"[Doc {i+1}]: {doc}" for i, doc in enumerate(retrieved_docs)
    )

    if MOCK_MODE:
        # Key nahi hai — context return kar do (graceful degradation)
        print(f"  [MOCK] LLM call skip — context dikhate hain:")
        print(f"  Context ({len(retrieved_docs)} docs retrieved):")
        for i, doc in enumerate(retrieved_docs, 1):
            print(f"    {i}. {doc[:72]}...")
        return f"[MOCK ANSWER] Retrieved {len(retrieved_docs)} docs. Set GROQ_API_KEY for live answer."

    # Step 2: LLM call (Groq ke saath)
    client = get_client()
    prompt = f"""You are a helpful assistant. Answer the question using ONLY the provided context.
If the answer is not in the context, say "Context mein answer nahi mila."

Context:
{context}

Question: {question}

Answer concisely in 2-3 sentences:"""

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.1,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"[LLM Error]: {e}"


# RAG pipeline demo
rag_questions = [
    ("What is RAG and how does it work?",    0.5),
    ("When was Python 3.12 released?",        0.3),  # keyword query — lower alpha
    ("What are vector databases used for?",   0.7),  # semantic — higher alpha
]

print("\nHybrid RAG Pipeline Demo:")
for question, alpha in rag_questions:
    print(f"\n  Q: '{question}'")
    print(f"  Alpha: {alpha}")
    answer = hybrid_rag_pipeline(
        question, CORPUS, bm25_engine, vector_engine, alpha=alpha, top_k=3
    )
    print(f"  A: {answer}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 9: PRODUCTION TOOLS REFERENCE
# Theory: Real-world mein kaise implement karte hain
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 9: Production Tools Reference")
print("=" * 65)

PRODUCTION_TOOLS = {
    "Elasticsearch": (
        "Built-in hybrid search support. BM25 (match query) + kNN vector search. "
        "Use 'hybrid' query type. Great for enterprise."
    ),
    "Qdrant": (
        "Vector DB with sparse vector support (BM25-compatible). "
        "Hybrid search natively supported. Fast aur open-source."
    ),
    "Weaviate": (
        "Built-in alpha parameter for hybrid search. "
        "weaviate.query.hybrid(query, alpha=0.5). Easy API."
    ),
    "pgvector": (
        "PostgreSQL extension. tsvector (BM25-like) + pgvector. "
        "Custom RRF fusion with SQL. Good if already using Postgres."
    ),
    "LangChain": (
        "EnsembleRetriever = BM25Retriever + vector retriever. "
        "weights=[0.5, 0.5] parameter. Easy integration."
    ),
    "rank_bm25": (
        "pip install rank_bm25. BM25Okapi class. In-memory. "
        "Good for small corpus (<100k docs). No server needed."
    ),
}

for tool, desc in PRODUCTION_TOOLS.items():
    print(f"\n  {tool}:")
    print(f"    {desc}")

# LangChain EnsembleRetriever code example
LANGCHAIN_CODE = '''\
# LangChain EnsembleRetriever — Theory Doc Implementation
from langchain_community.retrievers import BM25Retriever
from langchain.retrievers import EnsembleRetriever
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings

# BM25 retriever
bm25_retriever = BM25Retriever.from_texts(documents)
bm25_retriever.k = 5

# Vector retriever
vectorstore = Chroma.from_texts(documents, OpenAIEmbeddings())
vector_retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

# Ensemble (hybrid) — weights = [bm25_weight, vector_weight]
ensemble = EnsembleRetriever(
    retrievers=[bm25_retriever, vector_retriever],
    weights=[0.5, 0.5],  # alpha=0.5 equivalent
)

# RRF fusion automatically hota hai andar se
results = ensemble.invoke("Python 3.12 performance")
'''

print(f"\n\nLangChain EnsembleRetriever Example:\n{LANGCHAIN_CODE}")

# Qdrant hybrid search example
QDRANT_CODE = '''\
# Qdrant Native Hybrid Search (Theory Doc Se)
from qdrant_client import QdrantClient
from qdrant_client.models import NamedVector, NamedSparseVector

client = QdrantClient(":memory:")

results = client.query_points(
    collection_name="my_collection",
    prefetch=[
        Prefetch(query=dense_vector, using="dense", limit=20),  # vector
        Prefetch(query=sparse_vector, using="sparse", limit=20), # BM25
    ],
    query=FusionQuery(fusion=Fusion.RRF),  # RRF fusion!
    limit=5
)
# RRF k=60 internally use karta hai Qdrant
'''
print(f"\nQdrant Hybrid Search Example:\n{QDRANT_CODE}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 10: INTERVIEW SUMMARY — KEY POINTS YAAD KARO
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 10: Interview Summary — Key Points")
print("=" * 65)

INTERVIEW_POINTS = {
    "Hybrid Search Kya Hai": (
        "BM25 (keyword) + vector (semantic) = hybrid. "
        "70% accurate (vector alone) → 85%+ (hybrid)."
    ),
    "BM25 Kya Hai": (
        "Improved TF-IDF. k1=1.5 (TF saturation), b=0.75 (length norm). "
        "Exact terms aur rare terms ko better score karta hai."
    ),
    "Alpha Parameter": (
        "combined = alpha*vector + (1-alpha)*bm25. "
        "E-comm=0.3, Knowledge=0.5, Chat=0.7. Default=0.5."
    ),
    "RRF Kab Use Karo": (
        "Score normalization nahi kar sakte toh RRF use karo. "
        "Formula: 1/(k+rank), k=60 standard."
    ),
    "Hybrid Kab Better": (
        "Exact terms, proper nouns, code IDs, order numbers, version numbers. "
        "Concept queries ke liye vector alone kaafi hai."
    ),
    "Production Setup": (
        "Ingest: chunk → embed → vector DB + BM25 index. "
        "Query: vector top20 + BM25 top20 → RRF → top5."
    ),
    "Tools": (
        "rank_bm25 (in-memory), Elasticsearch (enterprise), "
        "Qdrant (vector DB native hybrid), Weaviate (alpha param), LangChain EnsembleRetriever."
    ),
    "Evaluation": (
        "Test on domain-specific queries. Tune alpha. "
        "RAGAS: faithfulness + answer_relevancy + context_precision."
    ),
}

for point, explanation in INTERVIEW_POINTS.items():
    print(f"\n  Q: {point}?")
    print(f"  A: {explanation}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 11: OPTIONAL — chromadb integration demo
# Heavy lib hai isliye try/except se gracefully handle karo
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 11: Optional — ChromaDB Integration")
print("=" * 65)

if CHROMADB_AVAILABLE:
    print("  chromadb available — offline demo (pre-computed embeddings use karte hain)")
    print("  NOTE: chromadb.query(query_texts=...) ONNX model download karta hai (network needed).")
    print("        Isliye hum pre-computed embeddings explicitly pass karte hain — offline safe.")
    try:
        # EphemeralClient = purely in-memory, no disk writes
        client_chroma = chromadb.EphemeralClient()

        # Embedding function SKIP karte hain — apne mock embeddings explicitly dete hain
        # Agar query_texts use karo toh chromadb ONNX model download karta hai (slow!)
        collection = client_chroma.create_collection(
            name="hybrid_demo",
            # No embedding_function = chromadb default use karta, jo network call karta hai
            # Isliye hum embeddings explicitly pass karenge
        )

        # Pehle se compute kiye hue mock embeddings use karo (64-dim)
        subset_docs  = CORPUS[:5]
        subset_embs  = [mock_embed(doc, dim=64) for doc in subset_docs]
        subset_ids   = [f"doc_{i}" for i in range(5)]

        # Embeddings explicitly pass karo — network call avoid karo
        collection.add(
            documents=subset_docs,
            embeddings=subset_embs,
            ids=subset_ids,
        )

        # Query bhi pre-computed embedding se karo
        query_emb = mock_embed("Python framework", dim=64)
        results = collection.query(
            query_embeddings=[query_emb],
            n_results=2,
        )
        print("  ChromaDB query results (mock embeddings ke saath):")
        for doc in results["documents"][0]:
            print(f"    - {doc[:65]}...")
    except Exception as e:
        print(f"  ChromaDB error (graceful skip): {e}")
else:
    print("  chromadb nahi mila — install karo: pip install chromadb")
    print("  Yahan production mein ye flow hota hai:")
    print("    1. chromadb.EphemeralClient() ya PersistentClient(path)")
    print("    2. collection.add(documents=..., embeddings=..., ids=...)")
    print("    3. collection.query(query_embeddings=[vec], n_results=k)")
    print("  ChromaDB khud BM25 support nahi karta — EnsembleRetriever ke saath use karo")


# ─────────────────────────────────────────────────────────────────────────────
# FINAL SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("LAB COMPLETE!")
print("=" * 65)
print("""
Aaj seekha:
  1. BM25 scratch implementation (k1=1.5, b=0.75)
  2. Vector search (cosine similarity)
  3. Weighted score fusion (alpha parameter)
  4. RRF — Reciprocal Rank Fusion (k=60)
  5. Alpha tuning per domain
  6. Hybrid vs pure vector comparison
  7. Full RAG pipeline with hybrid retrieval
  8. Production tools (Qdrant, Elasticsearch, LangChain)

Agle step:
  - 07_reranking.md — Cross-encoder reranking (top5 → top3)
  - GROQ_API_KEY set karo live demo ke liye
  - rank_bm25 install karo: pip install rank_bm25
""")

# Script hamesha EXIT 0 ke saath khatam hona chahiye
sys.exit(0)
