# OpenSearch as a Vector Store (k-NN)

**Agentic AI · Modern Topics | Senior AI Engineer**

> OpenSearch pehle sirf name-drop tha. Yeh file = jab tumhe **full-text search + vector search + analytics ek hi engine me** chahiye (true hybrid).

---

## Quick Concepts

**WHAT:** OpenSearch (Elasticsearch ka open-source fork) me native **k-NN vector search** hai — `knn_vector` field + HNSW/Faiss/Lucene engine.

**WHY on the diagram:** ELK-style logging/search already chala rahe ho? Usi cluster me dense vectors daalke **BM25 (keyword) + kNN (semantic) hybrid** ek query me kar sakte ho — dedicated vector DB add kiye bina.

---

## Architecture

```
        ┌──────────────── OpenSearch Cluster ────────────────┐
   doc ►│  index: { text (BM25) , embedding: knn_vector[768] }│
        │                    │                                │
        │  k-NN plugin ── engines: Lucene | nmslib | Faiss    │
        │                    │  (HNSW graph)                  │
        │                    ▼                                │
        │  HYBRID query:                                      │
        │    should: [ match(text) ,  knn(embedding) ]        │
        │    → normalized + combined score (search pipeline)  │
        └─────────────────────────────────────────────────────┘
```

- **`knn_vector` field** stores the dense embedding; ANN via HNSW
- **Engines:** Lucene (native, easy), nmslib, **Faiss** (fast, large-scale, GPU)
- **True hybrid:** BM25 sparse + kNN dense combined via a **search pipeline** with score normalization
- **Bonus:** aggregations, filters, RBAC, geo — full search-engine features around your vectors

---

## OpenSearch vs pure vector DBs

| | Milvus/Qdrant | **OpenSearch** |
|---|--------------|----------------|
| Primary job | vectors only | full-text + vectors + analytics |
| Hybrid search | add-on | native, first-class |
| Ops | vector cluster | you likely already run one |
| Best when | vectors dominate | keyword + semantic + logs together |

---

## When to choose
```
Vectors are the whole workload ....... Milvus / Qdrant
Already run ELK / need BM25+kNN ....... OpenSearch
Simple local RAG ..................... Chroma
```

## Interview one-liners
- "OpenSearch gives me BM25 and kNN in one index, combined through a hybrid search pipeline with score normalization."
- "The knn_vector field runs HNSW; I pick the Faiss engine for large-scale."
- "I choose it when the team already runs OpenSearch for logs/search and doesn't want a second datastore."

See runnable example → [20_opensearch_vector_practical.py](20_opensearch_vector_practical.py)
