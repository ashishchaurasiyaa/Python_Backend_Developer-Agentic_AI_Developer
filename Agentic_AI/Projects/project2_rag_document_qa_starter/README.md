# Project 2 Starter — RAG Document Q&A System

Spec file: [../02_project2_rag_document_qa.md](../02_project2_rag_document_qa.md)

## How to Run

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set env vars (optional — runs in placeholder mode without them)
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...        # for embeddings
export DATABASE_URL=postgresql+asyncpg://...
export COHERE_API_KEY=...           # optional, for reranking

# 3. Run the skeleton
python main.py
```

## Milestones

| # | Milestone | Key Files |
|---|-----------|-----------|
| 1 | Multi-format document loaders (PDF/DOCX/XLSX/URL) | `app/ingestion/loaders.py` |
| 2 | Chunking strategies (recursive + semantic) | `app/ingestion/chunker.py` |
| 3 | Hybrid search: BM25 + pgvector + RRF fusion | `app/retrieval/hybrid_search.py` |
| 4 | Reranking (local CrossEncoder or Cohere) | `app/retrieval/reranker.py` |
| 5 | FastAPI endpoints: `/upload`, `/query`, `/feedback` | `app/api/` |
| 6 | RAGAS evaluation dashboard + weekly Celery job | `app/evaluation/ragas_eval.py` |
| 7 | Langfuse cost tracking per query | `app/middleware/cost_tracking.py` |

## Stack

FastAPI + pgvector + Hybrid Search (BM25 + vector) + RAGAS + Langfuse + Anthropic Claude
