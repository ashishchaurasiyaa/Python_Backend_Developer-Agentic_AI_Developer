# Level 5 — Doc 6: Hybrid Search (BM25 + Vector) ⭐

> **Goal:** Pure vector search 70% accurate. Hybrid (vector + keyword) = 85%+. **Senior interview must-know.**

---

## 1. The Problem with Pure Vector Search

Vector search finds **semantically similar** content. But:
- "Python 3.12 release date" — needs **exact terms**
- "Order #ABC-123" — needs **keyword match**
- "CEO of OpenAI" — needs proper noun match

Vectors fuzzy-match. Sometimes miss exact terms.

---

## 2. The Solution: Hybrid Search

**Combine:**
1. **Vector search** (semantic): finds meaning-similar docs
2. **Keyword search** (BM25): finds exact-term matches
3. **Fusion**: combine scores

```
Query → Vector search → 10 results
     → BM25 search    → 10 results
     → Fuse scores    → final top 10
```

---

## 3. BM25 Algorithm (Keyword Search)

BM25 = improved TF-IDF. Scores by:
- **Term frequency** (TF): how often query terms appear in doc
- **Document length** (normalized)
- **Inverse document frequency** (IDF): rare terms weighted more

```python
def bm25_score(query, doc, corpus):
    score = 0
    for term in query.split():
        tf = doc.count(term) / len(doc.split())
        df = sum(1 for d in corpus if term in d)
        idf = log((len(corpus) - df + 0.5) / (df + 0.5))
        score += idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * len(doc) / avg_doc_length))
    return score
```

In production: use `rank-bm25` library.

---

## 4. Implementation

```python
from rank_bm25 import BM25Okapi
import numpy as np


class HybridSearcher:
    def __init__(self, documents: list[str]):
        self.documents = documents
        
        # Build BM25 index
        tokenized = [doc.split() for doc in documents]
        self.bm25 = BM25Okapi(tokenized)
        
        # Compute embeddings
        self.embeddings = [self.embed(doc) for doc in documents]
    
    def embed(self, text):
        # Use OpenAI text-embedding-3-small
        return openai.embeddings.create(
            input=text, model="text-embedding-3-small"
        ).data[0].embedding
    
    def search(self, query: str, k: int = 5, alpha: float = 0.5):
        """alpha controls weight: 0=pure BM25, 1=pure vector."""
        # BM25 scores
        bm25_scores = np.array(self.bm25.get_scores(query.split()))
        
        # Vector similarities
        query_emb = self.embed(query)
        vector_scores = np.array([
            self.cosine_sim(query_emb, doc_emb)
            for doc_emb in self.embeddings
        ])
        
        # Normalize each (0-1)
        bm25_scores = self.normalize(bm25_scores)
        vector_scores = self.normalize(vector_scores)
        
        # Combine
        combined = alpha * vector_scores + (1 - alpha) * bm25_scores
        
        # Top K
        top_k_idx = np.argsort(combined)[-k:][::-1]
        return [(self.documents[i], combined[i]) for i in top_k_idx]
    
    @staticmethod
    def cosine_sim(a, b):
        a, b = np.array(a), np.array(b)
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    
    @staticmethod
    def normalize(scores):
        if scores.max() == scores.min():
            return np.zeros_like(scores)
        return (scores - scores.min()) / (scores.max() - scores.min())
```

---

## 5. Reciprocal Rank Fusion (RRF) — Better Fusion

Instead of normalized scores, use rank positions:

```python
def rrf_fuse(bm25_results, vector_results, k=60):
    """Reciprocal Rank Fusion."""
    scores = defaultdict(float)
    
    for rank, doc in enumerate(bm25_results, start=1):
        scores[doc] += 1 / (k + rank)
    
    for rank, doc in enumerate(vector_results, start=1):
        scores[doc] += 1 / (k + rank)
    
    return sorted(scores.items(), key=lambda x: -x[1])
```

`k=60` is standard parameter.

**Why RRF wins:** Doesn't require normalizing scores from different systems. Just uses ranks.

---

## 6. Production Setup

```
1. Ingestion:
   - Chunk documents
   - Compute embeddings → store in vector DB (Pinecone/Qdrant/pgvector)
   - Build BM25 index (Elasticsearch/lokal in-memory)

2. Query:
   - Vector search: top 20 candidates
   - BM25 search: top 20 candidates
   - RRF fusion: final top 5

3. Reranking (next doc): top 5 → reranked → top 3
```

---

## 7. When Hybrid > Pure Vector

Test cases where hybrid wins:
- Exact terms ("Python 3.12", "Q4 2024", "order #12345")
- Proper nouns (people, places)
- Code identifiers ("def calculate_x()")
- Numeric values
- Acronyms

When vector alone is fine:
- Concept-based queries ("how to improve performance")
- Synonym-rich queries ("fast" vs "quick")

---

## 8. Alpha Tuning

`alpha = 0.5` is good default. But tune per use case:
- E-commerce search: `alpha=0.3` (keywords matter — product names)
- Knowledge base: `alpha=0.5` (balanced)
- Conversational Q&A: `alpha=0.7` (semantic dominant)

Run evals with different alphas. Pick best.

---

## 9. Production Tools

### Elasticsearch + Vector
Built-in hybrid search:
```python
es.search(body={
    "query": {
        "hybrid": {
            "queries": [
                {"match": {"content": "python 3.12"}},  # BM25
                {"knn": {"field": "embedding", "query_vector": qv}}  # Vector
            ]
        }
    }
})
```

### Qdrant
Supports BM25 alongside vectors natively.

### Weaviate
Built-in hybrid search with alpha parameter.

### pgvector
Use PostgreSQL `tsvector` + pgvector + custom fusion.

---

## 10. Key Takeaways

✅ Hybrid = vector + BM25 → 10-20% better than vector alone
✅ BM25 = improved TF-IDF (keyword scoring)
✅ Reciprocal Rank Fusion (RRF) > weighted score fusion
✅ Alpha=0.5 is good default
✅ Use libraries: `rank-bm25` or vector DB's built-in
✅ Always evaluate on your domain — tune alpha

**Next:** [07_reranking.md](07_reranking.md) — Reranking with cross-encoder
