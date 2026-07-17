# Txtai — All-in-One Embeddings Database & AI Workflows

**Agentic AI · Modern Topics | Senior AI Engineer**

> Frameworks row me LangChain/LlamaIndex/Haystack covered; **Txtai** missing tha. Yeh ek batteries-included semantic search engine hai jo chhoti/medium apps me pura RAG stack replace kar deta hai.

---

## Quick Concepts

**WHAT:** Ek library me — **embedding model + vector index + SQL metadata + ML pipelines + workflows**. Alag-alag 5 libs wire karne ki zaroorat nahi.

**WHY on the diagram:** LangChain/LlamaIndex "orchestration frameworks" hain (you bring the pieces). Txtai self-contained hai — search-first apps ke liye fastest path.

---

## Architecture

```
                    ┌──────────────── txtai ─────────────────┐
   documents  ─────►│  Embeddings  = vector index + SQL DB    │
                    │        │  (FAISS/HNSW + SQLite/DuckDB)   │
   query  ─────────►│  semantic search (+ hybrid + SQL WHERE) │
                    │        │                                │
                    │  Pipelines: summary, transcribe, OCR,   │
                    │             translate, extractor(QA),   │
                    │             LLM prompt                  │
                    │        │                                │
                    │  Workflows: chain pipelines (YAML/code) │
                    └────────┼────────────────────────────────┘
                             ▼
                       answer / results
```

- **Embeddings** = vector index **+** metadata DB → mix `similar('query')` with SQL `WHERE` in one call
- **Pipelines** = ready ML tasks (summarization, ASR, OCR, translation, QA, LLM)
- **Workflows** = declarative chaining of pipelines (no orchestration boilerplate)
- **Hybrid search** built-in (sparse BM25 + dense)

---

## Txtai vs LangChain (mental model)

| | Txtai | LangChain |
|---|-------|-----------|
| Philosophy | all-in-one engine | glue / orchestration |
| Vector DB | built-in | you bring one |
| Metadata filter | SQL over the index | external |
| Best for | search-first / lightweight RAG | complex agent flows |

---

## When to choose
```
Self-contained semantic search, few deps ..... txtai
Complex multi-tool agents, custom control ..... LangChain / LangGraph
Enterprise document pipelines ................. Haystack
Data-framework style RAG ...................... LlamaIndex
```

## Interview one-liners
- "txtai is an embeddings database — vector index plus a SQL metadata store in one object."
- "I reach for it when I want semantic search without wiring five separate libraries."
- "Its workflows let me chain OCR → translate → summarize declaratively."

See runnable example → [16_txtai_practical.py](16_txtai_practical.py)
