"""
RAG Advanced — Practical Demos
================================
Python Backend Developer + Agentic AI Interview Prep | Target: 40 LPA

Demos:
  chunking   — Chunking strategy comparison
  hybrid     — BM25 + Vector + RRF hybrid search
  reranking  — Cross-encoder reranking pipeline
  multiquery — Multi-query retrieval + MMR
  crag       — Corrective RAG pattern
  evaluation — RAGAS-style mock evaluation
  production — End-to-end production RAG pipeline

Usage:
  python 02_rag_advanced.py demo chunking
  python 02_rag_advanced.py demo hybrid
  python 02_rag_advanced.py demo all
  python 02_rag_advanced.py all
"""

import os
import sys
import time
import hashlib
import math
import numpy as np
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass, field

# ─── API Key Detection ────────────────────────────────────────────────────────
USE_OPENAI = os.getenv("OPENAI_API_KEY") is not None
USE_COHERE = os.getenv("COHERE_API_KEY") is not None
USE_SENTENCE_TRANSFORMERS = False  # Will be set after import check

try:
    from sentence_transformers import SentenceTransformer, CrossEncoder
    USE_SENTENCE_TRANSFORMERS = True
except ImportError:
    pass

print("=" * 70)
print("RAG Advanced — Practical Demos")
print("=" * 70)
print(f"  OpenAI API:            {'✓ Available' if USE_OPENAI else '✗ Mock mode'}")
print(f"  Cohere API:            {'✓ Available' if USE_COHERE else '✗ Mock mode'}")
print(f"  sentence-transformers: {'✓ Available' if USE_SENTENCE_TRANSFORMERS else '✗ Mock mode'}")
print("=" * 70)
print()

# ─── Sample Documents (20+ documents) ─────────────────────────────────────────
DOCUMENTS = [
    "Python asyncio event loop efficiently handles concurrent I/O operations using coroutines and tasks",
    "FastAPI framework uses Starlette under the hood for asynchronous HTTP request handling",
    "Redis sorted sets are ideal data structures for implementing real-time leaderboards and rankings",
    "PostgreSQL MVCC (Multi-Version Concurrency Control) allows concurrent readers without blocking writers",
    "Docker containers share the host OS kernel but provide isolated namespaces and resource limits",
    "Kubernetes orchestrates containerized applications with automatic scaling, healing, and load balancing",
    "Python GIL (Global Interpreter Lock) prevents true CPU parallelism in threads but not in processes",
    "SQLAlchemy ORM provides Python-level database abstraction with connection pooling and lazy loading",
    "JWT tokens encode user claims in base64, signed with HMAC-SHA256 or RSA for authentication",
    "Elasticsearch inverted index enables sub-second full-text search across millions of documents",
    "gRPC uses Protocol Buffers for serialization, offering 5-10x faster than REST JSON communication",
    "Python multiprocessing bypasses the GIL by creating separate OS processes with their own memory",
    "Celery distributed task queue uses Redis or RabbitMQ as message broker for background job processing",
    "Pydantic v2 uses Rust-based validator for 5-50x performance improvement over v1 pure Python",
    "FAISS (Facebook AI Similarity Search) enables billion-scale approximate nearest neighbor search",
    "ChromaDB is an open-source embedding database optimized for AI application development",
    "LangChain provides composable primitives for building LLM-powered applications and pipelines",
    "Vector embeddings represent semantic meaning as high-dimensional floating point arrays",
    "Transformer attention mechanism enables context-aware token representations via self-attention",
    "RAG (Retrieval Augmented Generation) grounds LLM responses in retrieved factual context",
    "BM25 algorithm ranks documents using term frequency and inverse document frequency with saturation",
    "Semantic search finds conceptually similar content even when exact keywords don't match",
    "Python type hints with mypy provide static analysis catching bugs before runtime execution",
    "WebSockets enable full-duplex persistent connections between browser and server for real-time apps",
    "Apache Kafka handles millions of messages per second as a distributed event streaming platform",
]

# ─── Long Document for Chunking Demo ──────────────────────────────────────────
LONG_DOCUMENT = """
# Understanding Modern Python Backend Development

## Introduction to Asynchronous Programming

Python has evolved significantly in its approach to handling concurrent operations.
The introduction of asyncio in Python 3.4 marked a paradigm shift from traditional
thread-based concurrency to coroutine-based cooperative multitasking.

The event loop is the heart of asyncio. It continuously monitors I/O operations,
scheduled callbacks, and coroutine execution. When a coroutine awaits an I/O
operation, control returns to the event loop, which can then run other coroutines.

## FastAPI and Modern Web Development

FastAPI has become the de facto standard for building high-performance Python APIs.
Built on Starlette and Pydantic, it provides automatic OpenAPI documentation,
request validation, and excellent async support out of the box.

A key feature of FastAPI is its dependency injection system. Dependencies can be
declared as function parameters, and FastAPI will automatically resolve and inject
them. This enables clean separation of concerns and makes testing straightforward.

Authentication in FastAPI typically uses OAuth2 with JWT tokens. The HTTPBearer
security scheme extracts tokens from the Authorization header, while custom
dependencies handle token validation and user extraction from the database.

## Database Patterns for Scale

PostgreSQL remains the most popular relational database for Python backends.
SQLAlchemy provides both ORM and Core interfaces for database interaction.
For high-traffic applications, connection pooling is critical — each database
connection is expensive to establish, so pools of pre-established connections
are maintained and reused.

MVCC (Multi-Version Concurrency Control) is PostgreSQL's secret weapon for
concurrent applications. Instead of locking rows for reads, PostgreSQL maintains
multiple versions of each row. Readers see a consistent snapshot without blocking
writers, and writers don't block readers. This enables high throughput for
mixed read-write workloads.

## Caching Strategies

Redis serves multiple roles in modern backends: caching layer, session store,
message broker, and real-time data structure server. Its data structures —
strings, hashes, lists, sets, sorted sets, and streams — map well to common
application patterns.

Cache invalidation remains one of computer science's hardest problems. Common
strategies include TTL-based expiration, event-driven invalidation, and
write-through caching. Choosing the right strategy depends on data freshness
requirements and consistency guarantees needed.

## Containerization and Deployment

Docker changed how we think about application deployment. By packaging application
code, runtime, libraries, and configuration into a single container image, we
achieve environment consistency from development to production.

Kubernetes extends Docker's benefits to cluster management. Pod scheduling,
service discovery, horizontal pod autoscaling, and rolling updates are handled
automatically. The declarative configuration model means infrastructure state
is version-controlled and reproducible.

## Search and Retrieval Systems

Elasticsearch is the industry standard for full-text search at scale. Its
inverted index structure enables sub-second queries across millions of documents.
The query DSL provides powerful filtering, aggregation, and ranking capabilities.

For semantic search, vector databases like Pinecone, Weaviate, and ChromaDB
store embedding vectors and enable similarity search using approximate nearest
neighbor algorithms. FAISS, developed by Facebook AI Research, provides
efficient similarity search even at billion-vector scale.

## Machine Learning Integration

Integrating ML models into production backends requires careful consideration
of latency, throughput, and reliability. ONNX Runtime provides optimized
inference for models exported from PyTorch or TensorFlow.

Feature stores like Feast centralize feature computation and serving, ensuring
training-serving consistency and enabling feature reuse across multiple models.
Online feature serving must meet strict latency SLAs, typically under 10ms.

## Monitoring and Observability

Production systems require comprehensive observability: metrics, logs, and traces.
Prometheus collects metrics with a pull-based model, while Grafana provides
visualization. Distributed tracing with OpenTelemetry tracks requests across
microservices, identifying latency bottlenecks and failures.

Structured logging in JSON format enables easy parsing and querying in log
aggregation systems like Elasticsearch or CloudWatch. Every log entry should
include correlation IDs to trace related events across services.
"""

# ─── Utility Functions ─────────────────────────────────────────────────────────

def print_section(title: str):
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")

def print_subsection(title: str):
    print(f"\n  [{title}]")

def timer(func):
    """Decorator to measure execution time"""
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = (time.perf_counter() - start) * 1000
        print(f"  ⏱  {func.__name__} completed in {elapsed:.1f}ms")
        return result
    return wrapper

# ─────────────────────────────────────────────────────────────────────────────
# DEMO 1 — Chunking Strategies Comparison
# ─────────────────────────────────────────────────────────────────────────────

def demo_chunking():
    print_section("DEMO 1 — Chunking Strategies Comparison")

    # ── Strategy 1: Fixed-size chunking ───────────────────────────────────────
    print_subsection("Strategy 1: Fixed-Size Chunking (char-based)")

    def fixed_size_chunk(text: str, chunk_size: int = 300, overlap: int = 50) -> List[str]:
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            start += chunk_size - overlap
        return chunks

    fixed_chunks = fixed_size_chunk(LONG_DOCUMENT, chunk_size=300, overlap=50)
    avg_fixed = sum(len(c) for c in fixed_chunks) // len(fixed_chunks)
    print(f"  chunk_size=300, overlap=50")
    print(f"  Total chunks: {len(fixed_chunks)}")
    print(f"  Average chunk size: {avg_fixed} chars")
    print(f"  First chunk preview:\n    '{fixed_chunks[0][:120]}...'")

    # ── Strategy 2: Recursive Text Splitter (manual implementation) ───────────
    print_subsection("Strategy 2: Recursive Text Splitter")

    def recursive_split(text: str, chunk_size: int = 400, overlap: int = 40,
                        separators: List[str] = None) -> List[str]:
        if separators is None:
            separators = ["\n\n", "\n", ". ", " ", ""]

        def _split(text: str, separators: List[str]) -> List[str]:
            if not separators or len(text) <= chunk_size:
                return [text] if text.strip() else []

            sep = separators[0]
            remaining_seps = separators[1:]

            if sep not in text:
                return _split(text, remaining_seps)

            parts = text.split(sep)
            chunks = []
            current = ""

            for part in parts:
                test = (current + sep + part).strip() if current else part.strip()
                if len(test) <= chunk_size:
                    current = test
                else:
                    if current:
                        chunks.append(current)
                    if len(part) > chunk_size:
                        sub_chunks = _split(part, remaining_seps)
                        chunks.extend(sub_chunks[:-1])
                        current = sub_chunks[-1] if sub_chunks else ""
                    else:
                        current = part.strip()

            if current:
                chunks.append(current)

            return chunks

        raw_chunks = _split(text, separators)

        # Apply overlap
        result = []
        for i, chunk in enumerate(raw_chunks):
            if i > 0 and overlap > 0:
                prev = raw_chunks[i - 1]
                # Take last `overlap` chars from previous chunk
                prefix = prev[-overlap:] if len(prev) > overlap else prev
                chunk = prefix + " " + chunk
            result.append(chunk)

        return result

    recursive_chunks = recursive_split(LONG_DOCUMENT, chunk_size=400, overlap=40)
    avg_recursive = sum(len(c) for c in recursive_chunks) // max(len(recursive_chunks), 1)
    print(f"  chunk_size=400, overlap=40, separators=[\\n\\n, \\n, '. ', ' ', '']")
    print(f"  Total chunks: {len(recursive_chunks)}")
    print(f"  Average chunk size: {avg_recursive} chars")
    print(f"  First chunk ends naturally at paragraph: {recursive_chunks[0][-30:]!r}")

    # ── Strategy 3: Markdown-aware chunking ───────────────────────────────────
    print_subsection("Strategy 3: Markdown-Header Splitting")

    def markdown_split(text: str) -> List[Dict[str, Any]]:
        """Split on ## headers, preserve hierarchy"""
        lines = text.split('\n')
        chunks = []
        current_chunk = {"content": "", "headers": {}}
        current_h1 = ""
        current_h2 = ""

        for line in lines:
            if line.startswith("# ") and not line.startswith("## "):
                if current_chunk["content"].strip():
                    chunks.append(current_chunk.copy())
                current_h1 = line[2:].strip()
                current_chunk = {"content": "", "headers": {"h1": current_h1}}
            elif line.startswith("## "):
                if current_chunk["content"].strip():
                    chunks.append(current_chunk.copy())
                current_h2 = line[3:].strip()
                current_chunk = {
                    "content": "",
                    "headers": {"h1": current_h1, "h2": current_h2}
                }
            else:
                current_chunk["content"] += line + "\n"

        if current_chunk["content"].strip():
            chunks.append(current_chunk)

        return chunks

    md_chunks = markdown_split(LONG_DOCUMENT)
    print(f"  Total sections: {len(md_chunks)}")
    for i, chunk in enumerate(md_chunks[:4]):
        h = chunk['headers']
        preview = chunk['content'].strip()[:60].replace('\n', ' ')
        header_str = f"{h.get('h1', '')} > {h.get('h2', '')}".strip(" >")
        print(f"  [{i+1}] {header_str}")
        print(f"       Content: '{preview}...'")
        print(f"       Size: {len(chunk['content'])} chars")

    # ── Strategy 4: Semantic Chunking (mock) ─────────────────────────────────
    print_subsection("Strategy 4: Semantic Chunking (Mock)")

    def mock_semantic_embed(sentence: str) -> np.ndarray:
        """Mock embedding: topic-aware using keywords"""
        topic_keywords = {
            "async": ["async", "asyncio", "coroutine", "await", "event", "loop"],
            "web": ["fastapi", "http", "api", "endpoint", "request", "authentication"],
            "database": ["postgresql", "sql", "query", "mvcc", "connection", "pool"],
            "cache": ["redis", "cache", "ttl", "invalidation", "memory"],
            "container": ["docker", "kubernetes", "container", "pod", "image"],
            "search": ["elasticsearch", "faiss", "vector", "embedding", "index", "search"],
            "ml": ["model", "inference", "feature", "training", "onnx", "ml"],
            "monitor": ["prometheus", "grafana", "logging", "trace", "metrics"],
        }
        vec = np.zeros(len(topic_keywords))
        words = sentence.lower().split()
        for i, (topic, keywords) in enumerate(topic_keywords.items()):
            vec[i] = sum(1 for w in words if any(k in w for k in keywords))
        norm = np.linalg.norm(vec)
        return vec / norm if norm > 0 else vec

    def cosine_sim(v1: np.ndarray, v2: np.ndarray) -> float:
        denom = np.linalg.norm(v1) * np.linalg.norm(v2)
        return float(np.dot(v1, v2) / denom) if denom > 0 else 0.0

    def semantic_chunk(text: str, threshold: float = 0.4) -> List[str]:
        sentences = [s.strip() for s in text.replace('\n', ' ').split('.') if len(s.strip()) > 20]
        if not sentences:
            return [text]

        embeddings = [mock_semantic_embed(s) for s in sentences]
        chunks = []
        current_sents = [sentences[0]]

        for i in range(1, len(sentences)):
            sim = cosine_sim(embeddings[i - 1], embeddings[i])
            if sim < threshold:  # Topic change detected
                chunks.append('. '.join(current_sents) + '.')
                current_sents = [sentences[i]]
            else:
                current_sents.append(sentences[i])

        if current_sents:
            chunks.append('. '.join(current_sents) + '.')

        return chunks

    semantic_chunks = semantic_chunk(LONG_DOCUMENT, threshold=0.3)
    avg_semantic = sum(len(c) for c in semantic_chunks) // max(len(semantic_chunks), 1)
    print(f"  threshold=0.3 (splits when topic similarity drops below this)")
    print(f"  Total chunks: {len(semantic_chunks)}")
    print(f"  Average chunk size: {avg_semantic} chars")
    print(f"  Chunk size range: {min(len(c) for c in semantic_chunks)} - {max(len(c) for c in semantic_chunks)} chars")

    # ── LangChain demo (if installed) ─────────────────────────────────────────
    print_subsection("LangChain Splitters (if installed)")
    try:
        from langchain.text_splitter import RecursiveCharacterTextSplitter, MarkdownHeaderTextSplitter

        lc_splitter = RecursiveCharacterTextSplitter(chunk_size=400, chunk_overlap=40)
        lc_chunks = lc_splitter.split_text(LONG_DOCUMENT)
        print(f"  LangChain RecursiveCharacterTextSplitter: {len(lc_chunks)} chunks")

        headers = [("#", "H1"), ("##", "H2"), ("###", "H3")]
        md_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers)
        md_lc_chunks = md_splitter.split_text(LONG_DOCUMENT)
        print(f"  LangChain MarkdownHeaderTextSplitter: {len(md_lc_chunks)} chunks with metadata")
        for chunk in md_lc_chunks[:2]:
            print(f"    metadata={chunk.metadata}, preview='{chunk.page_content[:50]}...'")
    except ImportError:
        print("  langchain not installed — install with: pip install langchain")

    # ── Comparison table ──────────────────────────────────────────────────────
    print_subsection("Chunking Strategy Comparison")
    headers_row = f"  {'Strategy':<28} {'Chunks':>6} {'Avg Size':>9} {'Preserves Structure':>20}"
    print(headers_row)
    print(f"  {'-' * 68}")
    strategies = [
        ("Fixed-size (300/50)", len(fixed_chunks), avg_fixed, "No"),
        ("Recursive (400/40)", len(recursive_chunks), avg_recursive, "Partial"),
        ("Markdown-aware", len(md_chunks), sum(len(c['content']) for c in md_chunks)//len(md_chunks), "Yes"),
        ("Semantic (threshold=0.3)", len(semantic_chunks), avg_semantic, "Yes"),
    ]
    for name, n, avg, struct in strategies:
        print(f"  {name:<28} {n:>6} {avg:>9} {struct:>20}")


# ─────────────────────────────────────────────────────────────────────────────
# DEMO 2 — Hybrid Search (BM25 + Vector + RRF)
# ─────────────────────────────────────────────────────────────────────────────

def demo_hybrid():
    print_section("DEMO 2 — Hybrid Search (BM25 + Vector + RRF)")

    docs = DOCUMENTS

    # ── BM25 Implementation ───────────────────────────────────────────────────
    print_subsection("BM25 Algorithm Implementation")

    class BM25:
        def __init__(self, documents: List[str], k1: float = 1.5, b: float = 0.75):
            self.k1 = k1
            self.b = b
            self.docs = documents
            self.tokenized = [doc.lower().split() for doc in documents]
            self.N = len(documents)
            self.avgdl = sum(len(d) for d in self.tokenized) / self.N

            # Build term → document frequency index
            self.df: Dict[str, int] = {}
            for doc_tokens in self.tokenized:
                for term in set(doc_tokens):
                    self.df[term] = self.df.get(term, 0) + 1

        def idf(self, term: str) -> float:
            df = self.df.get(term, 0)
            return math.log((self.N - df + 0.5) / (df + 0.5) + 1)

        def score(self, query: str, doc_idx: int) -> float:
            query_terms = query.lower().split()
            doc_tokens = self.tokenized[doc_idx]
            doc_len = len(doc_tokens)
            total = 0.0
            tf_counter: Dict[str, int] = {}
            for t in doc_tokens:
                tf_counter[t] = tf_counter.get(t, 0) + 1

            for term in query_terms:
                if term not in tf_counter:
                    continue
                tf = tf_counter[term]
                idf_val = self.idf(term)
                tf_norm = (tf * (self.k1 + 1)) / (
                    tf + self.k1 * (1 - self.b + self.b * doc_len / self.avgdl)
                )
                total += idf_val * tf_norm
            return total

        def search(self, query: str, top_k: int = 5) -> List[Tuple[str, float, int]]:
            scores = [(self.docs[i], self.score(query, i), i) for i in range(self.N)]
            scores.sort(key=lambda x: x[1], reverse=True)
            return scores[:top_k]

    bm25 = BM25(docs)
    print(f"  BM25 index built: {len(docs)} documents, k1=1.5, b=0.75")

    # ── Vector Search with Mock Embeddings ────────────────────────────────────
    print_subsection("Vector Search (mock embeddings)")

    def build_tfidf_embedding(texts: List[str], dim: int = 64) -> np.ndarray:
        """
        Mock embedding using TF-IDF like sparse representation
        projected to dense via consistent hashing
        """
        def embed(text: str) -> np.ndarray:
            words = text.lower().split()
            vec = np.zeros(dim)
            for w in words:
                idx = hash(w) % dim
                vec[idx] += 1.0 / math.sqrt(max(words.count(w), 1))
            norm = np.linalg.norm(vec)
            return vec / norm if norm > 0 else vec

        return np.array([embed(t) for t in texts])

    doc_embeddings = build_tfidf_embedding(docs, dim=64)
    print(f"  Mock embeddings built: shape={doc_embeddings.shape}")

    def vector_search(query: str, doc_embs: np.ndarray,
                      top_k: int = 5) -> List[Tuple[str, float, int]]:
        query_emb = build_tfidf_embedding([query])[0]
        scores = doc_embs @ query_emb  # Dot product (vectors are normalized)
        top_indices = np.argsort(scores)[::-1][:top_k]
        return [(docs[i], float(scores[i]), i) for i in top_indices]

    # ── RRF Implementation ────────────────────────────────────────────────────
    print_subsection("Reciprocal Rank Fusion (RRF)")

    def reciprocal_rank_fusion(
        result_lists: List[List[Tuple[str, float, int]]],
        k: int = 60,
        top_k: int = 5
    ) -> List[Tuple[str, float]]:
        """
        RRF formula: score(d) = sum over rankers: 1 / (k + rank(d))
        k=60 is standard — reduces impact of high ranks, rank-insensitive
        """
        scores: Dict[int, float] = {}
        for result_list in result_lists:
            for rank, (doc, raw_score, idx) in enumerate(result_list):
                scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank + 1)

        sorted_indices = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
        return [(docs[idx], scores[idx]) for idx in sorted_indices[:top_k]]

    def relative_score_fusion(
        bm25_results: List[Tuple[str, float, int]],
        vec_results: List[Tuple[str, float, int]],
        bm25_weight: float = 0.5,
        vec_weight: float = 0.5,
        top_k: int = 5
    ) -> List[Tuple[str, float]]:
        """Normalize scores to [0,1] then weighted average"""
        def normalize(results):
            scores = [(idx, score) for _, score, idx in results]
            if not scores:
                return {}
            values = [s for _, s in scores]
            mn, mx = min(values), max(values)
            denom = mx - mn if mx != mn else 1.0
            return {idx: (score - mn) / denom for idx, score in scores}

        norm_bm25 = normalize(bm25_results)
        norm_vec = normalize(vec_results)
        all_idx = set(norm_bm25) | set(norm_vec)
        combined = {
            idx: norm_bm25.get(idx, 0) * bm25_weight + norm_vec.get(idx, 0) * vec_weight
            for idx in all_idx
        }
        sorted_idx = sorted(combined.keys(), key=lambda x: combined[x], reverse=True)
        return [(docs[idx], combined[idx]) for idx in sorted_idx[:top_k]]

    # ── Run and Compare ───────────────────────────────────────────────────────
    print_subsection("Search Comparison")

    test_queries = [
        "async Python web framework",
        "database concurrency",
        "container orchestration Kubernetes",
        "BM25 term frequency search",
    ]

    for query in test_queries:
        print(f"\n  Query: '{query}'")
        bm25_res = bm25.search(query, top_k=5)
        vec_res = vector_search(query, doc_embeddings, top_k=5)
        rrf_res = reciprocal_rank_fusion([bm25_res, vec_res], k=60)
        rsf_res = relative_score_fusion(bm25_res, vec_res, bm25_weight=0.4, vec_weight=0.6)

        print(f"  {'Method':<10} {'Score':>7}   Document (first 55 chars)")
        print(f"  {'-'*75}")

        def show(method, results, score_fmt=".3f"):
            for doc, score in results[:2]:
                fmt = f"{score:{score_fmt}}" if isinstance(score, float) else str(score)
                print(f"  {method:<10} {fmt:>7}   {doc[:55]}")

        show("BM25", [(d, s) for d, s, _ in bm25_res])
        show("Vector", [(d, s) for d, s, _ in vec_res])
        show("RRF", rrf_res, ".5f")
        show("RSF", rsf_res)

    # ── LangChain EnsembleRetriever (if available) ────────────────────────────
    print_subsection("LangChain EnsembleRetriever (if installed)")
    try:
        from langchain.retrievers import BM25Retriever
        from langchain_core.documents import Document as LCDoc

        lc_docs = [LCDoc(page_content=d) for d in docs[:10]]
        bm25_retriever = BM25Retriever.from_documents(lc_docs, k=3)
        results = bm25_retriever.get_relevant_documents("async Python")
        print(f"  BM25Retriever returned {len(results)} docs for 'async Python'")
        for r in results:
            print(f"    - {r.page_content[:60]}")
    except ImportError:
        print("  langchain/rank_bm25 not installed — install with: pip install langchain rank-bm25")


# ─────────────────────────────────────────────────────────────────────────────
# DEMO 3 — Reranking Pipeline
# ─────────────────────────────────────────────────────────────────────────────

def demo_reranking():
    print_section("DEMO 3 — Reranking Pipeline")

    # ── Mock Cross-Encoder ────────────────────────────────────────────────────
    print_subsection("Cross-Encoder Reranking")

    def mock_cross_encoder_score(query: str, document: str) -> float:
        """
        Mock cross-encoder: joint query-document relevance score
        Real: CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2').predict([[query, doc]])
        """
        query_words = set(query.lower().split())
        doc_words = document.lower().split()

        # Direct term overlap
        overlap = sum(1 for w in doc_words if w in query_words)
        term_score = overlap / max(len(query_words), 1)

        # Proximity bonus: query words appearing close together in doc
        positions = {w: [] for w in query_words}
        for i, w in enumerate(doc_words):
            if w in positions:
                positions[w].append(i)

        proximity_score = 0.0
        matched_positions = [pos for positions_list in positions.values()
                             for pos in positions_list]
        if len(matched_positions) >= 2:
            matched_positions.sort()
            span = matched_positions[-1] - matched_positions[0] + 1
            density = len(matched_positions) / span
            proximity_score = density * 0.3

        # Length normalization
        length_penalty = 1.0 / (1.0 + math.log1p(len(doc_words) / 20))

        return min(term_score * 0.6 + proximity_score + length_penalty * 0.1, 1.0)

    def cross_encoder_rerank(
        query: str,
        candidates: List[str],
        top_k: int = 3,
        use_real: bool = USE_SENTENCE_TRANSFORMERS
    ) -> List[Tuple[str, float]]:
        if use_real:
            try:
                model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
                pairs = [[query, doc] for doc in candidates]
                scores = model.predict(pairs)
                ranked = sorted(zip(candidates, scores.tolist()), key=lambda x: x[1], reverse=True)
                return ranked[:top_k]
            except Exception as e:
                print(f"  Real cross-encoder failed: {e}. Using mock.")

        # Mock scoring
        scored = [(doc, mock_cross_encoder_score(query, doc)) for doc in candidates]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    # ── Run reranking demo ────────────────────────────────────────────────────
    test_cases = [
        {
            "query": "How does Python handle concurrent requests?",
            "initial_retrieve_size": 12
        },
        {
            "query": "database indexing and query performance",
            "initial_retrieve_size": 15
        },
        {
            "query": "container deployment orchestration",
            "initial_retrieve_size": 10
        },
    ]

    for case in test_cases:
        query = case["query"]
        k = case["initial_retrieve_size"]
        candidates = DOCUMENTS[:k]  # Simulate initial retrieval

        print(f"\n  Query: '{query}'")
        print(f"  Initial pool: {k} candidates")

        # Before reranking
        print(f"\n  Top-3 before reranking (first retrieved):")
        for i, doc in enumerate(candidates[:3]):
            print(f"    {i+1}. {doc[:65]}")

        # After reranking
        start = time.perf_counter()
        reranked = cross_encoder_rerank(query, candidates, top_k=3)
        elapsed_ms = (time.perf_counter() - start) * 1000

        print(f"\n  Top-3 after reranking ({elapsed_ms:.1f}ms):")
        for i, (doc, score) in enumerate(reranked):
            print(f"    {i+1}. score={score:.3f}  {doc[:65]}")

    # ── Lost-in-the-Middle Fix ────────────────────────────────────────────────
    print_subsection("Lost-in-the-Middle Reordering")

    def reorder_for_lost_in_middle(chunks: List[str]) -> List[str]:
        """
        Best chunks at positions 0 and -1 (start and end)
        Liu et al. 2023: LLMs attend best to beginning and end of context
        """
        if len(chunks) <= 2:
            return chunks

        result = [None] * len(chunks)
        left, right = 0, len(chunks) - 1

        for i, chunk in enumerate(chunks):
            if i % 2 == 0:
                result[left] = chunk
                left += 1
            else:
                result[right] = chunk
                right -= 1

        return [r for r in result if r is not None]

    original_order = [f"Chunk{i+1}: {DOCUMENTS[i][:40]}..." for i in range(6)]
    reordered = reorder_for_lost_in_middle(original_order)

    print(f"  Original order (most relevant first from reranker):")
    for i, c in enumerate(original_order):
        print(f"    pos[{i}] {c}")

    print(f"\n  Reordered (most relevant at start/end):")
    for i, c in enumerate(reordered):
        relevance = "★★★" if i in (0, len(reordered)-1) else "  ★" if i in (1, len(reordered)-2) else "   "
        print(f"    pos[{i}] {relevance} {c}")

    # ── Cohere Rerank (if available) ──────────────────────────────────────────
    print_subsection("Cohere Rerank API (if available)")
    if USE_COHERE:
        try:
            import cohere
            co = cohere.Client(os.getenv("COHERE_API_KEY"))
            query = "async database operations Python"
            results = co.rerank(
                model="rerank-english-v3.0",
                query=query,
                documents=DOCUMENTS[:10],
                top_n=3
            )
            print(f"  Cohere Rerank for: '{query}'")
            for r in results.results:
                print(f"    score={r.relevance_score:.4f}  {DOCUMENTS[r.index][:60]}")
        except Exception as e:
            print(f"  Cohere rerank failed: {e}")
    else:
        print("  Set COHERE_API_KEY env var to use real Cohere reranking")
        print("  Mock pipeline demonstrated above is API-equivalent")


# ─────────────────────────────────────────────────────────────────────────────
# DEMO 4 — Multi-Query Retrieval + MMR
# ─────────────────────────────────────────────────────────────────────────────

def demo_multiquery():
    print_section("DEMO 4 — Multi-Query Retrieval + MMR")

    docs = DOCUMENTS

    # ── Query Generation ──────────────────────────────────────────────────────
    print_subsection("Multi-Query Generation (mock LLM)")

    def generate_query_variants_mock(original_query: str, n: int = 4) -> List[str]:
        """
        Production mein: LLM se generate karo
        Mock: rule-based transformations
        """
        # Extract key terms
        stop_words = {"how", "what", "is", "are", "the", "a", "an", "to", "in", "for", "of"}
        key_terms = [w for w in original_query.lower().split() if w not in stop_words]

        variants = [
            original_query,
            " ".join(key_terms),  # Keywords only
            f"explain {original_query}",
            f"{original_query} implementation example",
            f"best practices {' '.join(key_terms[:3])}",
        ]
        return variants[:n]

    def generate_query_variants_llm(original_query: str, n: int = 4) -> List[str]:
        """Real LLM-based query generation"""
        if not USE_OPENAI:
            return generate_query_variants_mock(original_query, n)

        from openai import OpenAI
        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{
                "role": "user",
                "content": f"Generate {n} different search queries to retrieve documents "
                           f"relevant to: '{original_query}'\nOutput each query on a new line."
            }],
            max_tokens=200
        )
        lines = response.choices[0].message.content.strip().split('\n')
        return [l.strip().lstrip('1234567890.-) ') for l in lines if l.strip()][:n]

    # ── BM25 for retrieval ────────────────────────────────────────────────────
    from typing import Set

    class SimpleBM25:
        """Simplified BM25 for multi-query demo"""
        def __init__(self, documents):
            self.docs = documents
            self.tokenized = [d.lower().split() for d in documents]
            self.N = len(documents)
            self.avgdl = sum(len(t) for t in self.tokenized) / self.N
            self.df: Dict[str, int] = {}
            for doc in self.tokenized:
                for term in set(doc):
                    self.df[term] = self.df.get(term, 0) + 1

        def search(self, query: str, top_k: int = 5) -> List[Tuple[int, float]]:
            query_terms = query.lower().split()
            scores = []
            for i, doc in enumerate(self.tokenized):
                score = 0.0
                tf_count = {t: doc.count(t) for t in set(doc)}
                for term in query_terms:
                    if term in tf_count:
                        tf = tf_count[term]
                        df = self.df.get(term, 0)
                        idf = math.log((self.N - df + 0.5) / (df + 0.5) + 1)
                        tf_norm = (tf * 2.5) / (tf + 1.5 * (1 - 0.75 + 0.75 * len(doc) / self.avgdl))
                        score += idf * tf_norm
                scores.append((i, score))
            scores.sort(key=lambda x: x[1], reverse=True)
            return scores[:top_k]

    bm25_idx = SimpleBM25(docs)

    def multi_query_retrieve(
        original_query: str,
        documents: List[str],
        n_queries: int = 4,
        top_k: int = 5
    ) -> List[Tuple[str, float]]:
        variants = generate_query_variants_llm(original_query, n=n_queries)

        print(f"\n  Generated {len(variants)} query variants:")
        for v in variants:
            print(f"    - {v}")

        # Aggregate results from all variants
        doc_scores: Dict[int, float] = {}
        for variant in variants:
            results = bm25_idx.search(variant, top_k=top_k)
            for idx, score in results:
                # Take max score across queries (could also sum or RRF)
                doc_scores[idx] = max(doc_scores.get(idx, 0.0), score)

        sorted_results = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)
        return [(documents[idx], score) for idx, score in sorted_results[:top_k]]

    # ── MMR Implementation ────────────────────────────────────────────────────
    print_subsection("Maximal Marginal Relevance (MMR)")

    def build_embedding(text: str, dim: int = 32) -> np.ndarray:
        words = text.lower().split()
        vec = np.zeros(dim)
        for w in words:
            vec[hash(w) % dim] += 1.0
        norm = np.linalg.norm(vec)
        return vec / norm if norm > 0 else vec

    def cosine_similarity_np(a: np.ndarray, b: np.ndarray) -> float:
        return float(np.dot(a, b))  # Normalized vectors

    def mmr_select(
        query: str,
        candidates: List[str],
        k: int = 5,
        lambda_mult: float = 0.5
    ) -> List[Tuple[str, float]]:
        """
        MMR: balance relevance to query and diversity among selected docs
        score = lambda * sim(query, doc) - (1-lambda) * max_sim(doc, selected)
        lambda=0 → max diversity, lambda=1 → max relevance
        """
        query_emb = build_embedding(query)
        doc_embs = [build_embedding(c) for c in candidates]
        query_sims = [cosine_similarity_np(query_emb, e) for e in doc_embs]

        selected_indices = []
        remaining = list(range(len(candidates)))
        mmr_scores = []

        for _ in range(min(k, len(candidates))):
            best_score = -float('inf')
            best_idx_in_remaining = -1

            for rem_idx in remaining:
                relevance = query_sims[rem_idx]
                if selected_indices:
                    redundancy = max(
                        cosine_similarity_np(doc_embs[rem_idx], doc_embs[sel])
                        for sel in selected_indices
                    )
                else:
                    redundancy = 0.0

                mmr_score = lambda_mult * relevance - (1 - lambda_mult) * redundancy
                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx_in_remaining = rem_idx

            selected_indices.append(best_idx_in_remaining)
            mmr_scores.append(best_score)
            remaining.remove(best_idx_in_remaining)

        return [(candidates[i], s) for i, s in zip(selected_indices, mmr_scores)]

    # ── Run Demos ─────────────────────────────────────────────────────────────
    queries = [
        "Python performance optimization techniques",
        "distributed systems messaging and queuing",
    ]

    for query in queries:
        print(f"\n  {'─' * 55}")
        print(f"  Query: '{query}'")

        # Multi-query results
        mq_results = multi_query_retrieve(query, docs, n_queries=4, top_k=5)

        print(f"\n  Multi-Query Top-5 (merged from all variants):")
        for i, (doc, score) in enumerate(mq_results):
            print(f"    {i+1}. score={score:.3f}  {doc[:60]}")

        # MMR on multi-query results
        candidates = [doc for doc, _ in mq_results]
        print(f"\n  MMR Top-3 (lambda=0.5, balance relevance+diversity):")
        mmr_res = mmr_select(query, candidates, k=3, lambda_mult=0.5)
        for i, (doc, score) in enumerate(mmr_res):
            print(f"    {i+1}. mmr={score:.3f}  {doc[:60]}")

        # Compare: without MMR vs with MMR
        print(f"\n  λ=1.0 (max relevance, may have redundancy):")
        rel_only = mmr_select(query, candidates, k=3, lambda_mult=1.0)
        for doc, s in rel_only:
            print(f"    {s:.3f}  {doc[:60]}")

        print(f"\n  λ=0.0 (max diversity, may miss relevance):")
        div_only = mmr_select(query, candidates, k=3, lambda_mult=0.0)
        for doc, s in div_only:
            print(f"    {s:.3f}  {doc[:60]}")


# ─────────────────────────────────────────────────────────────────────────────
# DEMO 5 — Corrective RAG (CRAG) Pattern
# ─────────────────────────────────────────────────────────────────────────────

def demo_crag():
    print_section("DEMO 5 — Corrective RAG (CRAG) Pattern")

    def grade_document_relevance(query: str, document: str) -> Tuple[str, float]:
        """
        Grade document relevance to query
        Production: use LLM judge
        Mock: keyword overlap scoring
        """
        query_words = set(query.lower().split())
        # Remove stop words
        stops = {"how", "what", "is", "are", "the", "a", "an", "to", "in", "for",
                 "of", "does", "do", "can", "will", "with", "by", "from", "this"}
        query_keywords = query_words - stops

        doc_words = set(document.lower().split())
        if not query_keywords:
            return "ambiguous", 0.5

        overlap = len(query_keywords & doc_words) / len(query_keywords)

        if overlap >= 0.4:
            return "relevant", overlap
        elif overlap >= 0.15:
            return "ambiguous", overlap
        else:
            return "irrelevant", overlap

    def web_search_fallback(query: str) -> List[str]:
        """
        Mock web search results
        Production: Tavily, SerpAPI, Google Custom Search
        """
        return [
            f"[WEB RESULT 1] Comprehensive guide to '{query}': "
            f"Industry best practices and latest developments from web search.",
            f"[WEB RESULT 2] Technical documentation for '{query}': "
            f"Official documentation with examples and API references.",
        ]

    def knowledge_refinement(question: str, documents: List[str]) -> str:
        """
        Extract and refine relevant knowledge from documents
        Production: LLM-based extraction
        Mock: keyword-based sentence selection
        """
        query_words = set(question.lower().split())
        all_sentences = []
        for doc in documents:
            sentences = doc.split('. ')
            for sent in sentences:
                score = sum(1 for w in sent.lower().split() if w in query_words)
                all_sentences.append((sent, score))

        # Select top sentences by relevance
        all_sentences.sort(key=lambda x: x[1], reverse=True)
        refined = '. '.join(s for s, _ in all_sentences[:3] if s.strip())
        return refined if refined else "No relevant information found."

    def mock_llm_generate(question: str, context: List[str]) -> str:
        """Mock LLM generation — production: use OpenAI/Anthropic"""
        if USE_OPENAI:
            from openai import OpenAI
            client = OpenAI()
            context_text = "\n\n".join(context[:3])
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Answer based on the provided context."},
                    {"role": "user", "content": f"Context:\n{context_text}\n\nQuestion: {question}"}
                ],
                max_tokens=200
            )
            return response.choices[0].message.content
        else:
            return (f"[Mock Answer] Based on {len(context)} source(s): "
                    f"The answer to '{question[:50]}...' involves the concepts discussed in the provided context.")

    def crag_pipeline(
        query: str,
        retrieved_docs: List[str],
        relevance_threshold: float = 0.15
    ) -> Dict[str, Any]:
        print(f"\n  Query: '{query}'")
        print(f"  Retrieved {len(retrieved_docs)} documents")

        # Step 1: Grade each document
        print(f"\n  Step 1 — Grading retrieved documents:")
        graded = []
        for doc in retrieved_docs:
            grade, score = grade_document_relevance(query, doc)
            graded.append((doc, grade, score))
            symbol = "✓" if grade == "relevant" else "~" if grade == "ambiguous" else "✗"
            print(f"    {symbol} {grade:<12} ({score:.2f})  {doc[:50]}...")

        relevant = [d for d, g, _ in graded if g == "relevant"]
        ambiguous = [d for d, g, _ in graded if g == "ambiguous"]
        irrelevant = [d for d, g, _ in graded if g == "irrelevant"]

        print(f"\n  Grading summary: {len(relevant)} relevant, "
              f"{len(ambiguous)} ambiguous, {len(irrelevant)} irrelevant")

        # Step 2: Decision
        if len(irrelevant) > len(relevant) + len(ambiguous):
            print(f"\n  Step 2 — Decision: FALLBACK to web search (too many irrelevant docs)")
            web_docs = web_search_fallback(query)
            final_context = web_docs
            source = "web_search"
        elif len(relevant) == 0 and len(ambiguous) == 0:
            print(f"\n  Step 2 — Decision: ALL IRRELEVANT → web search")
            web_docs = web_search_fallback(query)
            final_context = web_docs
            source = "web_search"
        else:
            print(f"\n  Step 2 — Decision: USE retrieved docs (sufficient relevance)")
            # Knowledge refinement for ambiguous docs
            if ambiguous:
                print(f"  Step 2b — Refining {len(ambiguous)} ambiguous documents...")
                refined = knowledge_refinement(query, [d for d, _, _ in graded if d in ambiguous])
                final_context = relevant + [refined]
            else:
                final_context = relevant
            source = "knowledge_base"

        # Step 3: Generate
        print(f"\n  Step 3 — Generating answer from {len(final_context)} source(s) [{source}]:")
        answer = mock_llm_generate(query, final_context)
        print(f"  Answer: {answer[:120]}...")

        return {
            "query": query,
            "source": source,
            "relevant_docs": len(relevant),
            "final_context_size": len(final_context),
            "answer": answer
        }

    # ── Test CRAG with different scenarios ────────────────────────────────────
    scenarios = [
        {
            "query": "Python async concurrent programming",
            "docs": DOCUMENTS[:6],  # Mix of relevant and irrelevant
            "desc": "Scenario A: Mixed relevance"
        },
        {
            "query": "quantum computing applications in finance",  # Not in our corpus
            "docs": DOCUMENTS[:5],
            "desc": "Scenario B: Irrelevant corpus → web fallback"
        },
        {
            "query": "Redis caching strategies",
            "docs": [DOCUMENTS[2], DOCUMENTS[14], DOCUMENTS[5], DOCUMENTS[7]],
            "desc": "Scenario C: High relevance"
        },
    ]

    for scenario in scenarios:
        print(f"\n  {'=' * 55}")
        print(f"  {scenario['desc']}")
        result = crag_pipeline(scenario["query"], scenario["docs"])


# ─────────────────────────────────────────────────────────────────────────────
# DEMO 6 — RAGAS-style Evaluation
# ─────────────────────────────────────────────────────────────────────────────

def demo_evaluation():
    print_section("DEMO 6 — RAGAS-style RAG Evaluation")

    print("""
  RAGAS metrics:
    Faithfulness      — Answer claims supported by context?  (0-1, higher=less hallucination)
    Answer Relevancy  — Answer addresses the question?       (0-1, higher=more on-topic)
    Context Precision — Retrieved chunks are relevant?       (0-1, higher=less noise)
    Context Recall    — All needed info was retrieved?       (0-1, higher=nothing missed)
    Answer Correctness— Factual match with ground truth?     (0-1)
    """)

    # ── Mock metric implementations ───────────────────────────────────────────

    def calculate_faithfulness(answer: str, context: str) -> float:
        """
        Real RAGAS: LLM extracts claims from answer, checks each in context
        Mock: sentence-level overlap
        """
        answer_sentences = [s.strip() for s in answer.split('.') if len(s.strip()) > 10]
        if not answer_sentences:
            return 1.0

        supported = 0
        for sentence in answer_sentences:
            sent_words = set(sentence.lower().split())
            content_words = {w for w in sent_words if len(w) > 4}  # Skip short words
            if not content_words:
                supported += 1
                continue
            context_lower = context.lower()
            matched = sum(1 for w in content_words if w in context_lower)
            if matched / len(content_words) >= 0.4:
                supported += 1

        return supported / len(answer_sentences)

    def calculate_answer_relevancy(question: str, answer: str) -> float:
        """
        Real RAGAS: LLM generates questions from answer, measures similarity to original
        Mock: bidirectional keyword overlap
        """
        q_words = set(question.lower().split())
        a_words = set(answer.lower().split())
        stops = {"how", "what", "is", "are", "the", "a", "an", "to", "in", "for",
                 "of", "does", "do", "can", "will"}
        q_keywords = q_words - stops
        a_keywords = a_words - stops

        if not q_keywords:
            return 0.5

        overlap = len(q_keywords & a_keywords) / len(q_keywords)
        # Penalize very short answers (not comprehensive)
        length_factor = min(len(answer.split()) / 20, 1.0)
        return min(overlap * 1.5 * length_factor, 1.0)

    def calculate_context_precision(
        question: str,
        contexts: List[str],
        relevant_threshold: float = 0.2
    ) -> float:
        """
        What fraction of retrieved chunks are relevant to the question?
        """
        q_words = set(question.lower().split())
        stops = {"how", "what", "is", "are", "the", "a", "an", "to", "in", "for", "of"}
        q_keywords = q_words - stops

        if not q_keywords or not contexts:
            return 1.0

        relevant_count = 0
        for ctx in contexts:
            ctx_words = set(ctx.lower().split())
            overlap = len(q_keywords & ctx_words) / len(q_keywords)
            if overlap >= relevant_threshold:
                relevant_count += 1

        return relevant_count / len(contexts)

    def calculate_context_recall(
        ground_truth: str,
        contexts: List[str]
    ) -> float:
        """
        What fraction of ground truth facts are present in the retrieved context?
        """
        gt_sentences = [s.strip() for s in ground_truth.split('.') if len(s.strip()) > 15]
        if not gt_sentences:
            return 1.0

        full_context = ' '.join(contexts).lower()
        recalled = 0
        for sentence in gt_sentences:
            key_words = [w for w in sentence.lower().split() if len(w) > 4]
            if not key_words:
                recalled += 1
                continue
            matched = sum(1 for w in key_words if w in full_context)
            if matched / len(key_words) >= 0.4:
                recalled += 1

        return recalled / len(gt_sentences)

    def calculate_answer_correctness(answer: str, ground_truth: str) -> float:
        """F1 score between answer claims and ground truth facts"""
        def extract_key_terms(text: str) -> set:
            stops = {"the", "a", "an", "is", "are", "was", "were", "to", "of",
                     "and", "or", "but", "in", "on", "at", "by", "for", "with"}
            return {w.lower() for w in text.split() if w.lower() not in stops and len(w) > 3}

        answer_terms = extract_key_terms(answer)
        gt_terms = extract_key_terms(ground_truth)

        if not answer_terms or not gt_terms:
            return 0.0

        intersection = answer_terms & gt_terms
        precision = len(intersection) / len(answer_terms)
        recall = len(intersection) / len(gt_terms)

        if precision + recall == 0:
            return 0.0
        return 2 * precision * recall / (precision + recall)

    # ── Test dataset ──────────────────────────────────────────────────────────
    test_cases = [
        {
            "question": "What is Python's GIL and why does it exist?",
            "answer": "Python's GIL is the Global Interpreter Lock, a mutex that prevents multiple threads from executing Python bytecode simultaneously. It exists because CPython's memory management is not thread-safe, so the GIL ensures only one thread runs at a time. This simplifies memory management but limits CPU parallelism.",
            "contexts": [
                "Python GIL (Global Interpreter Lock) prevents true CPU parallelism in threads but not in processes",
                "Python multiprocessing bypasses the GIL by creating separate OS processes with their own memory",
                "FastAPI uses Starlette under the hood for asynchronous HTTP request handling"
            ],
            "ground_truth": "The GIL is a mutex in CPython that allows only one thread to execute Python bytecode at a time. It prevents true parallelism in threads but processes are unaffected. Python multiprocessing can bypass the GIL."
        },
        {
            "question": "How does FastAPI handle authentication?",
            "answer": "FastAPI handles authentication using JWT tokens with OAuth2. The HTTPBearer security scheme extracts tokens from Authorization headers. Dependencies validate tokens and extract user information.",
            "contexts": [
                "JWT tokens encode user claims in base64, signed with HMAC-SHA256 or RSA for authentication",
                "FastAPI framework uses Starlette under the hood for asynchronous HTTP request handling",
                "Redis sorted sets are ideal data structures for implementing real-time leaderboards"
            ],
            "ground_truth": "FastAPI authentication uses JWT tokens with the HTTPBearer security scheme. Tokens are validated through dependency injection. OAuth2 password flow is the recommended approach."
        },
        {
            "question": "What is vector similarity search used for?",
            "answer": "Vector similarity search finds semantically similar content by comparing embedding vectors. It's used in RAG systems for retrieving relevant documents, recommendation systems, and semantic search applications. FAISS enables billion-scale approximate nearest neighbor search.",
            "contexts": [
                "FAISS (Facebook AI Similarity Search) enables billion-scale approximate nearest neighbor search",
                "Vector embeddings represent semantic meaning as high-dimensional floating point arrays",
                "RAG (Retrieval Augmented Generation) grounds LLM responses in retrieved factual context",
                "Semantic search finds conceptually similar content even when exact keywords don't match"
            ],
            "ground_truth": "Vector similarity search compares embedding vectors to find semantically similar content. FAISS enables efficient large-scale search. Used in RAG, recommendations, and semantic search systems."
        },
        {
            "question": "How does PostgreSQL handle concurrent reads and writes?",
            "answer": "PostgreSQL uses MVCC (Multi-Version Concurrency Control) to handle concurrency. Multiple versions of each row are maintained. Readers see consistent snapshots without blocking writers, and writers don't block readers. This allows high throughput for mixed workloads.",
            "contexts": [
                "PostgreSQL MVCC (Multi-Version Concurrency Control) allows concurrent readers without blocking writers",
                "SQLAlchemy ORM provides Python-level database abstraction with connection pooling and lazy loading",
            ],
            "ground_truth": "PostgreSQL uses MVCC (Multi-Version Concurrency Control). Readers see a consistent snapshot without blocking writers. This enables high concurrency for mixed read-write workloads."
        },
        {
            "question": "What message brokers does Celery support?",
            "answer": "Celery is a distributed task queue that uses Redis or RabbitMQ as message brokers for processing background jobs. These brokers handle message routing and persistence.",
            "contexts": [
                "Celery distributed task queue uses Redis or RabbitMQ as message broker for background job processing",
                "Apache Kafka handles millions of messages per second as a distributed event streaming platform",
            ],
            "ground_truth": "Celery supports Redis and RabbitMQ as message brokers. It enables background job processing and distributed task execution."
        },
    ]

    # ── Evaluate all test cases ───────────────────────────────────────────────
    print_subsection("Running Evaluation on 5 Test Cases")
    results = []
    for case in test_cases:
        full_context = ' '.join(case["contexts"])
        metrics = {
            "question": case["question"][:45],
            "faithfulness": calculate_faithfulness(case["answer"], full_context),
            "answer_relevancy": calculate_answer_relevancy(case["question"], case["answer"]),
            "context_precision": calculate_context_precision(case["question"], case["contexts"]),
            "context_recall": calculate_context_recall(case["ground_truth"], case["contexts"]),
            "answer_correctness": calculate_answer_correctness(case["answer"], case["ground_truth"]),
        }
        results.append(metrics)

    # Print table
    cols = ["Question", "Faith", "Relev", "C.Prec", "C.Rec", "Correct", "Avg"]
    print(f"\n  {cols[0]:<47} {cols[1]:>6} {cols[2]:>6} {cols[3]:>7} {cols[4]:>6} {cols[5]:>8} {cols[6]:>5}")
    print(f"  {'-' * 90}")

    for r in results:
        avg = np.mean([r["faithfulness"], r["answer_relevancy"],
                       r["context_precision"], r["context_recall"],
                       r["answer_correctness"]])
        print(f"  {r['question']:<47} "
              f"{r['faithfulness']:>6.3f} "
              f"{r['answer_relevancy']:>6.3f} "
              f"{r['context_precision']:>7.3f} "
              f"{r['context_recall']:>6.3f} "
              f"{r['answer_correctness']:>8.3f} "
              f"{avg:>5.3f}")

    # Aggregate
    print(f"\n  {'─' * 90}")
    agg = {
        "faithfulness": np.mean([r["faithfulness"] for r in results]),
        "answer_relevancy": np.mean([r["answer_relevancy"] for r in results]),
        "context_precision": np.mean([r["context_precision"] for r in results]),
        "context_recall": np.mean([r["context_recall"] for r in results]),
        "answer_correctness": np.mean([r["answer_correctness"] for r in results]),
    }
    overall_avg = np.mean(list(agg.values()))
    print(f"  {'AVERAGE':<47} "
          f"{agg['faithfulness']:>6.3f} "
          f"{agg['answer_relevancy']:>6.3f} "
          f"{agg['context_precision']:>7.3f} "
          f"{agg['context_recall']:>6.3f} "
          f"{agg['answer_correctness']:>8.3f} "
          f"{overall_avg:>5.3f}")

    print(f"""
  Interpretation:
    Faithfulness {agg['faithfulness']:.2f}      → {'Good (low hallucination)' if agg['faithfulness'] > 0.7 else 'Needs improvement'}
    Answer Relevancy {agg['answer_relevancy']:.2f}  → {'Answers are on-topic' if agg['answer_relevancy'] > 0.6 else 'Off-topic answers'}
    Context Precision {agg['context_precision']:.2f}  → {'Retrieval is clean' if agg['context_precision'] > 0.6 else 'Too much noise in context'}
    Context Recall {agg['context_recall']:.2f}     → {'Good coverage' if agg['context_recall'] > 0.6 else 'Missing relevant chunks'}
    """)

    # ── Real RAGAS integration note ───────────────────────────────────────────
    print_subsection("Real RAGAS Usage (requires: pip install ragas)")
    print("""
  from ragas import evaluate
  from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
  from datasets import Dataset

  dataset = Dataset.from_dict({
      "question": [...],
      "answer": [...],
      "contexts": [[...], ...],
      "ground_truth": [...]
  })

  results = evaluate(
      dataset,
      metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
      llm=your_llm,
      embeddings=your_embeddings
  )
  print(results.to_pandas())
  """)


# ─────────────────────────────────────────────────────────────────────────────
# DEMO 7 — Production RAG Pipeline (End-to-End)
# ─────────────────────────────────────────────────────────────────────────────

def demo_production():
    print_section("DEMO 7 — Production RAG Pipeline (End-to-End)")

    # ─── Data Structures ──────────────────────────────────────────────────────

    @dataclass
    class Chunk:
        content: str
        doc_id: str
        chunk_idx: int
        metadata: Dict[str, Any] = field(default_factory=dict)
        embedding: Optional[np.ndarray] = None

    @dataclass
    class SearchResult:
        chunk: Chunk
        score: float
        method: str

    # ─── Stage 1: Ingestion Pipeline ─────────────────────────────────────────
    print_subsection("Stage 1 — Ingestion Pipeline")

    class DocumentEmbedder:
        """Mock embedder — real: OpenAIEmbeddings or SentenceTransformer"""
        def __init__(self, dim: int = 64, use_real: bool = USE_OPENAI):
            self.dim = dim
            self.use_real = use_real
            self._model = None

        def _get_real_model(self):
            if USE_OPENAI:
                from openai import OpenAI
                return OpenAI()
            elif USE_SENTENCE_TRANSFORMERS:
                return SentenceTransformer("all-MiniLM-L6-v2")
            return None

        def embed(self, texts: List[str]) -> np.ndarray:
            if self.use_real:
                try:
                    if USE_OPENAI:
                        client = self._get_real_model()
                        response = client.embeddings.create(
                            model="text-embedding-3-small", input=texts
                        )
                        return np.array([r.embedding for r in response.data])
                    elif USE_SENTENCE_TRANSFORMERS:
                        model = SentenceTransformer("all-MiniLM-L6-v2")
                        return model.encode(texts)
                except Exception:
                    pass  # Fall through to mock

            # Mock embedding
            result = []
            for text in texts:
                words = text.lower().split()
                vec = np.zeros(self.dim)
                for w in words:
                    vec[hash(w) % self.dim] += 1.0 / math.sqrt(max(words.count(w), 1))
                norm = np.linalg.norm(vec)
                vec = vec / norm if norm > 0 else vec
                result.append(vec)
            return np.array(result)

    class ProductionIngestionPipeline:
        def __init__(self, chunk_size: int = 200, chunk_overlap: int = 30):
            self.chunk_size = chunk_size
            self.chunk_overlap = chunk_overlap
            self.embedder = DocumentEmbedder()
            self.chunks: List[Chunk] = []
            self.doc_hashes: Dict[str, str] = {}

        def _compute_hash(self, content: str) -> str:
            return hashlib.md5(content.encode()).hexdigest()[:8]

        def _chunk_text(self, text: str, doc_id: str) -> List[Chunk]:
            """Fixed-size chunking with overlap"""
            chunks = []
            words = text.split()
            words_per_chunk = self.chunk_size // 5  # Approx word count
            step = max(1, words_per_chunk - self.chunk_overlap // 5)

            for i in range(0, len(words), step):
                chunk_words = words[i:i + words_per_chunk]
                content = ' '.join(chunk_words)
                if len(content) < 20:
                    continue
                chunks.append(Chunk(
                    content=content,
                    doc_id=doc_id,
                    chunk_idx=len(chunks),
                    metadata={"word_start": i, "word_count": len(chunk_words)}
                ))
                if i + words_per_chunk >= len(words):
                    break
            return chunks

        def ingest(self, documents: Dict[str, str]) -> Dict[str, Any]:
            """
            documents: {doc_id: content}
            Returns: ingestion stats
            """
            t_start = time.perf_counter()
            new_count = 0
            skip_count = 0
            all_new_chunks: List[Chunk] = []

            for doc_id, content in documents.items():
                doc_hash = self._compute_hash(content)

                # Incremental update check
                if doc_id in self.doc_hashes and self.doc_hashes[doc_id] == doc_hash:
                    skip_count += 1
                    continue

                if doc_id in self.doc_hashes:
                    # Remove old chunks
                    self.chunks = [c for c in self.chunks if c.doc_id != doc_id]

                new_chunks = self._chunk_text(content, doc_id)
                all_new_chunks.extend(new_chunks)
                self.doc_hashes[doc_id] = doc_hash
                new_count += 1

            # Batch embed all new chunks
            if all_new_chunks:
                texts = [c.content for c in all_new_chunks]
                embeddings = self.embedder.embed(texts)
                for chunk, emb in zip(all_new_chunks, embeddings):
                    chunk.embedding = emb
                self.chunks.extend(all_new_chunks)

            t_elapsed = (time.perf_counter() - t_start) * 1000
            return {
                "docs_indexed": new_count,
                "docs_skipped": skip_count,
                "total_chunks": len(self.chunks),
                "new_chunks": len(all_new_chunks),
                "time_ms": t_elapsed
            }

    # ─── Stage 2: Query Pipeline ──────────────────────────────────────────────

    class SemanticCache:
        def __init__(self, threshold: float = 0.92):
            self.threshold = threshold
            self.cache: List[Tuple[np.ndarray, str, str]] = []  # (emb, query, answer)
            self.hits = 0
            self.misses = 0

        def get(self, query_embedding: np.ndarray, query: str) -> Optional[str]:
            for cached_emb, cached_query, answer in self.cache:
                sim = float(np.dot(query_embedding, cached_emb))
                if sim > self.threshold:
                    self.hits += 1
                    return answer
            self.misses += 1
            return None

        def set(self, query_embedding: np.ndarray, query: str, answer: str):
            self.cache.append((query_embedding, query, answer))

        @property
        def hit_rate(self) -> float:
            total = self.hits + self.misses
            return self.hits / total if total > 0 else 0.0

    class ProductionRAGPipeline:
        def __init__(self, ingestion_pipeline: ProductionIngestionPipeline):
            self.ingestion = ingestion_pipeline
            self.embedder = ingestion_pipeline.embedder
            self.cache = SemanticCache(threshold=0.92)
            self.query_count = 0
            self.total_latency_ms = 0.0

        def _vector_search(self, query_emb: np.ndarray, top_k: int = 10) -> List[SearchResult]:
            chunks = [c for c in self.ingestion.chunks if c.embedding is not None]
            if not chunks:
                return []
            embeddings = np.array([c.embedding for c in chunks])
            scores = embeddings @ query_emb
            top_indices = np.argsort(scores)[::-1][:top_k]
            return [SearchResult(chunks[i], float(scores[i]), "vector") for i in top_indices]

        def _bm25_search(self, query: str, top_k: int = 10) -> List[SearchResult]:
            query_terms = set(query.lower().split())
            chunks = self.ingestion.chunks
            scored = []
            for chunk in chunks:
                doc_words = chunk.content.lower().split()
                tf = sum(doc_words.count(t) for t in query_terms)
                score = tf / max(len(doc_words), 1) * 10
                scored.append((chunk, score))
            scored.sort(key=lambda x: x[1], reverse=True)
            return [SearchResult(c, s, "bm25") for c, s in scored[:top_k]]

        def _rrf_merge(
            self,
            result_lists: List[List[SearchResult]],
            k: int = 60,
            top_k: int = 5
        ) -> List[SearchResult]:
            scores: Dict[int, float] = {}
            chunk_map: Dict[int, Chunk] = {}
            for results in result_lists:
                for rank, sr in enumerate(results):
                    cid = id(sr.chunk)
                    scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
                    chunk_map[cid] = sr.chunk
            sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
            return [SearchResult(chunk_map[cid], scores[cid], "hybrid_rrf")
                    for cid in sorted_ids[:top_k]]

        def _mock_rerank(self, query: str, results: List[SearchResult]) -> List[SearchResult]:
            """Mock cross-encoder reranking"""
            query_words = set(query.lower().split())
            for sr in results:
                doc_words = set(sr.chunk.content.lower().split())
                overlap = len(query_words & doc_words) / max(len(query_words), 1)
                sr.score = overlap * 0.7 + sr.score * 0.3
            results.sort(key=lambda x: x.score, reverse=True)
            return results

        def _reorder_lost_in_middle(self, results: List[SearchResult]) -> List[SearchResult]:
            if len(results) <= 2:
                return results
            reordered = [None] * len(results)
            left, right = 0, len(results) - 1
            for i, sr in enumerate(results):
                if i % 2 == 0:
                    reordered[left] = sr
                    left += 1
                else:
                    reordered[right] = sr
                    right -= 1
            return [r for r in reordered if r is not None]

        def _mock_generate(self, query: str, context_chunks: List[SearchResult]) -> str:
            if USE_OPENAI:
                from openai import OpenAI
                client = OpenAI()
                context = "\n\n".join([f"[Source {i+1}] {sr.chunk.content}"
                                       for i, sr in enumerate(context_chunks)])
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "Answer based on provided context. Be concise."},
                        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"}
                    ],
                    max_tokens=150
                )
                return response.choices[0].message.content
            return (f"[Generated Answer] Query: '{query[:40]}' | "
                    f"Sources: {len(context_chunks)} chunks from "
                    f"{len(set(sr.chunk.doc_id for sr in context_chunks))} documents.")

        def query(self, user_query: str, verbose: bool = True) -> Dict[str, Any]:
            t_start = time.perf_counter()
            timings: Dict[str, float] = {}
            self.query_count += 1

            if verbose:
                print(f"\n  Query #{self.query_count}: '{user_query}'")

            # Stage 1: Embed query
            t0 = time.perf_counter()
            query_emb = self.embedder.embed([user_query])[0]
            timings["embed_query"] = (time.perf_counter() - t0) * 1000

            # Stage 2: Check semantic cache
            t0 = time.perf_counter()
            cached = self.cache.get(query_emb, user_query)
            timings["cache_check"] = (time.perf_counter() - t0) * 1000
            if cached:
                if verbose:
                    print(f"  CACHE HIT ({self.cache.hit_rate:.0%} hit rate) → {cached[:60]}...")
                return {"answer": cached, "source": "cache", "timings": timings}

            # Stage 3: Hybrid retrieval
            t0 = time.perf_counter()
            vec_results = self._vector_search(query_emb, top_k=10)
            bm25_results = self._bm25_search(user_query, top_k=10)
            hybrid_results = self._rrf_merge([vec_results, bm25_results], top_k=8)
            timings["retrieval"] = (time.perf_counter() - t0) * 1000

            if verbose:
                print(f"  Retrieved: {len(vec_results)} vector + {len(bm25_results)} BM25 → "
                      f"{len(hybrid_results)} hybrid ({timings['retrieval']:.1f}ms)")

            # Stage 4: Rerank
            t0 = time.perf_counter()
            reranked = self._mock_rerank(user_query, hybrid_results)
            top_k_results = reranked[:5]
            timings["rerank"] = (time.perf_counter() - t0) * 1000

            # Stage 5: Lost-in-middle fix
            final_context = self._reorder_lost_in_middle(top_k_results)

            if verbose:
                print(f"  Top-5 after rerank:")
                for i, sr in enumerate(final_context):
                    pos_label = "START" if i == 0 else "END" if i == len(final_context)-1 else f"MID{i}"
                    print(f"    [{pos_label}] score={sr.score:.3f}  {sr.chunk.content[:50]}...")

            # Stage 6: Generate
            t0 = time.perf_counter()
            answer = self._mock_generate(user_query, final_context)
            timings["generate"] = (time.perf_counter() - t0) * 1000

            # Stage 7: Cache the answer
            self.cache.set(query_emb, user_query, answer)

            total_ms = (time.perf_counter() - t_start) * 1000
            self.total_latency_ms += total_ms
            timings["total"] = total_ms

            if verbose:
                print(f"\n  Answer: {answer[:100]}...")
                print(f"  Timings: embed={timings['embed_query']:.1f}ms | "
                      f"retrieve={timings['retrieval']:.1f}ms | "
                      f"rerank={timings['rerank']:.1f}ms | "
                      f"generate={timings['generate']:.1f}ms | "
                      f"TOTAL={timings['total']:.1f}ms")

            return {
                "answer": answer,
                "source": "pipeline",
                "timings": timings,
                "context_used": len(final_context),
            }

        def stats(self) -> Dict[str, Any]:
            return {
                "total_queries": self.query_count,
                "cache_hit_rate": f"{self.cache.hit_rate:.1%}",
                "avg_latency_ms": f"{self.total_latency_ms / max(self.query_count, 1):.1f}ms",
                "total_chunks": len(self.ingestion.chunks),
                "indexed_docs": len(self.ingestion.doc_hashes),
            }

    # ─── Build and Test ───────────────────────────────────────────────────────
    print_subsection("Building Production RAG System")

    # Create ingestion pipeline
    ingestion = ProductionIngestionPipeline(chunk_size=250, chunk_overlap=30)

    # Sample documents to ingest (simulating real docs)
    docs_to_ingest = {
        "doc_python_async": LONG_DOCUMENT[:800],
        "doc_fastapi": LONG_DOCUMENT[800:1500],
        "doc_database": LONG_DOCUMENT[1500:2200],
        "doc_caching": LONG_DOCUMENT[2200:2900],
        "doc_containers": LONG_DOCUMENT[2900:3600],
        "doc_search": LONG_DOCUMENT[3600:],
    }

    stats = ingestion.ingest(docs_to_ingest)
    print(f"  Initial ingestion:")
    print(f"    Documents indexed: {stats['docs_indexed']}")
    print(f"    Total chunks:      {stats['total_chunks']}")
    print(f"    New chunks:        {stats['new_chunks']}")
    print(f"    Time:              {stats['time_ms']:.1f}ms")

    # Test incremental update
    updated_docs = {
        "doc_python_async": LONG_DOCUMENT[:800],  # Same — should skip
        "doc_new_topic": "gRPC uses protocol buffers for high-performance RPC between microservices. "
                        "It supports streaming, bidirectional communication, and strong typing through .proto files.",
    }
    stats2 = ingestion.ingest(updated_docs)
    print(f"\n  Incremental update:")
    print(f"    New docs: {stats2['docs_indexed']}, Skipped (unchanged): {stats2['docs_skipped']}")
    print(f"    Total chunks now: {stats2['total_chunks']}")

    # Create query pipeline
    rag = ProductionRAGPipeline(ingestion)

    print_subsection("Running Queries")
    test_queries = [
        "How does Python asyncio event loop work?",
        "How does FastAPI handle authentication and dependencies?",
        "What is MVCC in PostgreSQL?",
        "How does Docker containerization work?",
        "How does Python asyncio event loop work?",  # Repeat — should hit cache
    ]

    for query in test_queries:
        rag.query(query, verbose=True)
        print()

    # Final stats
    print_subsection("Pipeline Statistics")
    final_stats = rag.stats()
    print(f"  Total queries:    {final_stats['total_queries']}")
    print(f"  Cache hit rate:   {final_stats['cache_hit_rate']}")
    print(f"  Avg latency:      {final_stats['avg_latency_ms']}")
    print(f"  Indexed docs:     {final_stats['indexed_docs']}")
    print(f"  Total chunks:     {final_stats['total_chunks']}")

    # ─── Multi-tenant illustration ────────────────────────────────────────────
    print_subsection("Multi-Tenant RAG Pattern")
    print("""
  Production mein har tenant ka alag namespace:

  # Pinecone namespace:
  index.upsert(vectors=embeddings, namespace=f"tenant_{tenant_id}")
  results = index.query(vector=query_emb, namespace=f"tenant_{tenant_id}")

  # ChromaDB collection:
  collection = chroma_client.get_or_create_collection(f"tenant_{tenant_id}")
  collection.add(documents=docs, embeddings=embs, ids=ids)

  # Weaviate tenant:
  client.schema.create_class({
      "class": "Document",
      "multiTenancyConfig": {"enabled": True}
  })
  """)


# ─────────────────────────────────────────────────────────────────────────────
# Main — CLI Entry Point
# ─────────────────────────────────────────────────────────────────────────────

DEMO_MAP = {
    "chunking": demo_chunking,
    "hybrid": demo_hybrid,
    "reranking": demo_reranking,
    "multiquery": demo_multiquery,
    "crag": demo_crag,
    "evaluation": demo_evaluation,
    "production": demo_production,
}

def run_demo(name: str):
    if name not in DEMO_MAP:
        print(f"Unknown demo: '{name}'. Available: {', '.join(DEMO_MAP.keys())}")
        return
    print(f"\n{'█' * 70}")
    print(f"  RUNNING: {name.upper()}")
    print(f"{'█' * 70}")
    DEMO_MAP[name]()

def main():
    args = sys.argv[1:]

    if not args or args[0] == "all":
        # Run all demos
        for name in DEMO_MAP:
            run_demo(name)
        return

    if args[0] == "demo" and len(args) >= 2:
        name = args[1]
        if name == "all":
            for n in DEMO_MAP:
                run_demo(n)
        else:
            run_demo(name)
        return

    # Direct demo name
    if args[0] in DEMO_MAP:
        run_demo(args[0])
        return

    print(f"""
Usage:
  python 02_rag_advanced.py                    # Run all demos
  python 02_rag_advanced.py all                # Run all demos
  python 02_rag_advanced.py demo chunking      # Run specific demo
  python 02_rag_advanced.py chunking           # Same

Available demos:
  chunking   — Fixed, Recursive, Semantic, Markdown chunking comparison
  hybrid     — BM25 + Vector + RRF/RSF fusion
  reranking  — Cross-encoder reranking + lost-in-middle fix
  multiquery — Multi-query retrieval + MMR diversity
  crag       — Corrective RAG with document grading + web fallback
  evaluation — RAGAS-style: Faithfulness, Relevancy, Precision, Recall
  production — End-to-end pipeline with caching, ingestion, multi-tenant
    """)


if __name__ == "__main__":
    main()
