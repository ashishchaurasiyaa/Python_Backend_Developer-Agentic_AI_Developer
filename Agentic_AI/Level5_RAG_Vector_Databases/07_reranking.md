# Level 5 — Doc 7: Reranking (Cross-Encoder) ⭐

> **Goal:** Initial retrieval gets 20 candidates. **Reranking** picks best 3-5. Quality boost massive.

---

## 1. Why Rerank?

Initial retrieval (vector + BM25) is **fast** but **noisy**:
- Top 20 candidates: maybe 5 truly relevant
- Top 3 (without reranking): often miss best ones

**Reranker** = second-pass, more accurate, slower model.

```
Query → Initial retrieve top 20 → Rerank → top 3-5 to LLM
```

---

## 2. Bi-Encoder vs Cross-Encoder

### Bi-encoder (initial retrieval)
- Encode query and doc SEPARATELY
- Compare embeddings via cosine similarity
- Fast (pre-compute doc embeddings)

```
[query] → encoder → q_emb
[doc]   → encoder → d_emb  (pre-computed)

similarity = cosine(q_emb, d_emb)
```

### Cross-encoder (reranker)
- Encode query AND doc TOGETHER
- Output single relevance score
- Slow (can't pre-compute, must run per query)

```
[query, doc] → encoder → relevance_score (0-1)
```

**Quality:** Cross-encoder >> Bi-encoder
**Speed:** Bi-encoder >> Cross-encoder

**Production pattern:**
1. Bi-encoder retrieves top 20 (fast)
2. Cross-encoder reranks 20 → top 3 (slow but only 20 items)

---

## 3. Code Example

```python
from sentence_transformers import CrossEncoder

reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')

def search_with_rerank(query, docs, k_initial=20, k_final=5):
    # Step 1: Initial retrieval (e.g., from vector DB)
    candidates = vector_search(query, top_k=k_initial)
    
    # Step 2: Rerank with cross-encoder
    pairs = [[query, doc.text] for doc in candidates]
    scores = reranker.predict(pairs)
    
    # Step 3: Sort by reranker scores
    ranked = sorted(zip(candidates, scores), key=lambda x: -x[1])
    return ranked[:k_final]
```

---

## 4. Popular Rerankers

### Open Source
- `cross-encoder/ms-marco-MiniLM-L-6-v2` (lightweight, fast)
- `cross-encoder/ms-marco-MiniLM-L-12-v2` (better, slower)
- `BAAI/bge-reranker-v2-m3` (best open-source, multilingual)
- `BAAI/bge-reranker-large` (high quality)

### API-based
- **Cohere Rerank** — `rerank-english-v3.0` (excellent)
- **Voyage AI Rerank**
- **Jina AI Reranker**

### Cost comparison
- Open-source (self-host): GPU compute cost
- Cohere Rerank: $1/1000 calls
- Worth it for quality-critical RAG

---

## 5. Cohere Rerank API (Production-Ready)

```python
import cohere

co = cohere.Client(api_key="...")

def cohere_rerank(query, docs, top_n=5):
    response = co.rerank(
        model="rerank-english-v3.0",
        query=query,
        documents=docs,
        top_n=top_n
    )
    return [(docs[r.index], r.relevance_score) for r in response.results]
```

Best quality among off-the-shelf options.

---

## 6. Latency Trade-off

For 20 candidates:
- Bi-encoder alone: ~50ms total
- Adding open-source reranker: +500-2000ms
- Adding Cohere API: +200ms

For latency-sensitive apps (chat), might skip reranking.
For accuracy-critical (legal, medical), always rerank.

---

## 7. Multi-Stage Pipeline (Production)

```
Query → BM25 (top 100, ~10ms)
     → Vector (top 100, ~50ms)
     → RRF fusion (top 40, ~5ms)
     → Cross-encoder rerank (top 5, ~500ms)
     → LLM with top 5 chunks
```

Each stage filters more aggressively. Total: ~600ms before LLM call.

---

## 8. When NOT to Rerank

- Single retrieval result good enough
- Latency budget tight
- Cost-sensitive at scale
- Domain where initial retrieval already excellent

---

## 9. Evaluating Reranker

```python
def eval_reranking(queries_with_relevant_docs, retriever, reranker):
    results = []
    for query, relevant_doc_ids in queries_with_relevant_docs:
        # Initial top 20
        initial = retriever.search(query, k=20)
        # Reranked top 5
        reranked = reranker.rerank(query, initial)[:5]
        
        # MRR (Mean Reciprocal Rank)
        for rank, doc in enumerate(reranked, 1):
            if doc.id in relevant_doc_ids:
                results.append(1 / rank)
                break
        else:
            results.append(0)
    
    return mean(results)  # Higher = better
```

---

## 10. Key Takeaways

✅ Reranking = second pass for better ordering
✅ Cross-encoder >> Bi-encoder in quality
✅ Trade-off: quality vs latency (+500ms typical)
✅ Production: top-20 initial → top-5 reranked → LLM
✅ Best off-the-shelf: Cohere Rerank (API)
✅ Best open-source: BGE reranker
✅ Skip for latency-critical, use for accuracy-critical

**Next:** [09_ragas_evaluation.md](09_ragas_evaluation.md) — How to measure RAG quality
