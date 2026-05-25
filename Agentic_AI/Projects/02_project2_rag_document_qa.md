# Project 2: RAG Document Q&A System

## Overview
Demonstrates deep RAG expertise — a common interview ask.
**Stack:** FastAPI + pgvector + Hybrid Search + RAGAS + Langfuse

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                  Upload Pipeline                      │
│  PDF/DOCX/Excel/URL → Chunk → Embed → pgvector       │
└──────────────────────────────────────────────────────┘
                          │
┌──────────────────────────────────────────────────────┐
│                  Query Pipeline                       │
│  Query → Embed + BM25 → Hybrid Merge → Rerank →      │
│  LLM Generate → Stream → User                        │
└──────────────────────────────────────────────────────┘
                          │
┌──────────────────────────────────────────────────────┐
│                  Evaluation Layer                     │
│  RAGAS Dashboard: Faithfulness, Relevancy, Recall    │
│  User Feedback: thumbs up/down → golden dataset      │
│  Cost tracking: per query token usage                │
└──────────────────────────────────────────────────────┘
```

---

## Core Implementation

### 1. Multi-format Document Ingestion

```python
# app/ingestion/loaders.py
from pathlib import Path
from langchain_community.document_loaders import (
    PyPDFLoader,
    UnstructuredWordDocumentLoader,
    UnstructuredExcelLoader,
    WebBaseLoader,
    UnstructuredHTMLLoader,
)
from langchain_core.documents import Document

LOADERS = {
    ".pdf":  PyPDFLoader,
    ".docx": UnstructuredWordDocumentLoader,
    ".doc":  UnstructuredWordDocumentLoader,
    ".xlsx": UnstructuredExcelLoader,
    ".xls":  UnstructuredExcelLoader,
    ".html": UnstructuredHTMLLoader,
}

async def load_document(source: str) -> list[Document]:
    """Load document from file path or URL."""
    if source.startswith("http"):
        loader = WebBaseLoader(source)
        return loader.load()

    ext = Path(source).suffix.lower()
    loader_class = LOADERS.get(ext)
    if not loader_class:
        raise ValueError(f"Unsupported file type: {ext}")

    loader = loader_class(source)
    return loader.load()
```

```python
# app/ingestion/chunker.py
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_experimental.text_splitter import SemanticChunker
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document

def chunk_documents(
    docs: list[Document],
    strategy: str = "recursive",
) -> list[Document]:
    if strategy == "recursive":
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ". ", " "],
        )
    elif strategy == "semantic":
        embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        splitter = SemanticChunker(
            embeddings,
            breakpoint_threshold_type="percentile",
            breakpoint_threshold_amount=95,
        )

    return splitter.split_documents(docs)
```

### 2. Hybrid Search (BM25 + Vector)

```python
# app/retrieval/hybrid_search.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from langchain_openai import OpenAIEmbeddings
from rank_bm25 import BM25Okapi
import numpy as np

embedder = OpenAIEmbeddings(model="text-embedding-3-small")

async def hybrid_search(
    query: str,
    user_id: str,
    db: AsyncSession,
    top_k: int = 10,
    alpha: float = 0.5,        # 0=pure BM25, 1=pure vector
) -> list[dict]:

    # 1. Dense retrieval (vector similarity)
    query_embedding = await embedder.aembed_query(query)

    vector_results = await db.execute(text("""
        SELECT id, content, metadata,
               1 - (embedding <=> :embedding) AS vector_score
        FROM document_chunks
        WHERE user_id = :user_id
        ORDER BY embedding <=> :embedding
        LIMIT :top_k
    """), {
        "embedding": str(query_embedding),
        "user_id": user_id,
        "top_k": top_k,
    })
    vector_docs = vector_results.fetchall()

    # 2. Sparse retrieval (BM25 full-text)
    bm25_results = await db.execute(text("""
        SELECT id, content, metadata,
               ts_rank(to_tsvector('english', content),
                       plainto_tsquery('english', :query)) AS bm25_score
        FROM document_chunks
        WHERE user_id = :user_id
          AND to_tsvector('english', content) @@ plainto_tsquery('english', :query)
        ORDER BY bm25_score DESC
        LIMIT :top_k
    """), {"query": query, "user_id": user_id, "top_k": top_k})
    bm25_docs = bm25_results.fetchall()

    # 3. Reciprocal Rank Fusion (RRF)
    scores = {}
    k = 60  # RRF constant

    for rank, doc in enumerate(vector_docs):
        scores[doc.id] = scores.get(doc.id, 0) + (1 - alpha) * (1 / (k + rank + 1))

    for rank, doc in enumerate(bm25_docs):
        scores[doc.id] = scores.get(doc.id, 0) + alpha * (1 / (k + rank + 1))

    # 4. Merge and sort
    all_docs = {doc.id: doc for doc in vector_docs + bm25_docs}
    sorted_ids = sorted(scores, key=scores.get, reverse=True)[:top_k]

    return [
        {"id": doc_id, "content": all_docs[doc_id].content, "score": scores[doc_id]}
        for doc_id in sorted_ids
        if doc_id in all_docs
    ]
```

### 3. Reranking Pipeline

```python
# app/retrieval/reranker.py
from sentence_transformers import CrossEncoder
from langchain_cohere import CohereRerank

# Option 1: Local CrossEncoder (free, slower)
_cross_encoder = None

def get_cross_encoder():
    global _cross_encoder
    if _cross_encoder is None:
        _cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    return _cross_encoder

def rerank_local(query: str, documents: list[dict], top_n: int = 3) -> list[dict]:
    model = get_cross_encoder()
    pairs = [(query, doc["content"]) for doc in documents]
    scores = model.predict(pairs)

    for doc, score in zip(documents, scores):
        doc["rerank_score"] = float(score)

    return sorted(documents, key=lambda x: x["rerank_score"], reverse=True)[:top_n]

# Option 2: Cohere Rerank (better quality, $2/1000 calls)
async def rerank_cohere(query: str, documents: list[dict], top_n: int = 3) -> list[dict]:
    from cohere import AsyncClient
    import os

    co = AsyncClient(api_key=os.getenv("COHERE_API_KEY"))
    results = await co.rerank(
        query=query,
        documents=[doc["content"] for doc in documents],
        top_n=top_n,
        model="rerank-english-v3.0",
    )

    reranked = []
    for result in results.results:
        doc = documents[result.index].copy()
        doc["rerank_score"] = result.relevance_score
        reranked.append(doc)
    return reranked
```

### 4. RAGAS Evaluation Dashboard

```python
# app/evaluation/ragas_eval.py
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
)
from datasets import Dataset
from langfuse import Langfuse
import pandas as pd

langfuse = Langfuse()

async def evaluate_rag_quality(
    questions: list[str],
    answers: list[str],
    contexts: list[list[str]],
    ground_truths: list[str],
) -> dict:
    """Run RAGAS evaluation on a batch of Q&A pairs."""

    dataset = Dataset.from_dict({
        "question": questions,
        "answer": answers,
        "contexts": contexts,
        "ground_truth": ground_truths,
    })

    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
    )

    scores = {
        "faithfulness": result["faithfulness"],
        "answer_relevancy": result["answer_relevancy"],
        "context_precision": result["context_precision"],
        "context_recall": result["context_recall"],
        "overall": sum(result.values()) / len(result),
    }

    # Log to Langfuse
    langfuse.score(
        trace_id="ragas_weekly_eval",
        name="ragas_overall",
        value=scores["overall"],
        comment=f"Faithfulness: {scores['faithfulness']:.2f}",
    )

    return scores

# Weekly evaluation job (Celery beat)
@celery_app.task
def weekly_ragas_eval():
    """Run RAGAS on golden dataset weekly."""
    golden_data = load_golden_dataset()
    scores = asyncio.run(evaluate_rag_quality(**golden_data))

    if scores["faithfulness"] < 0.7:
        send_slack_alert(f"RAG faithfulness dropped to {scores['faithfulness']:.2f}")

    return scores
```

### 5. User Feedback Loop

```python
# app/api/feedback.py
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class FeedbackRequest(BaseModel):
    message_id: str
    rating: int       # 1 (thumbs up) or -1 (thumbs down)
    comment: str | None = None

@router.post("/feedback")
async def submit_feedback(req: FeedbackRequest, db = Depends(get_db)):
    await db.execute("""
        INSERT INTO user_feedback (message_id, rating, comment, created_at)
        VALUES (:message_id, :rating, :comment, NOW())
    """, req.model_dump())
    await db.commit()

    # If negative feedback on high-quality answer → add to golden dataset
    if req.rating == -1:
        message = await get_message(req.message_id, db)
        await add_to_review_queue(message)

    return {"status": "recorded"}

@router.get("/feedback/stats")
async def feedback_stats(days: int = 30, db = Depends(get_db)):
    result = await db.execute("""
        SELECT
            COUNT(*) FILTER (WHERE rating = 1) as thumbs_up,
            COUNT(*) FILTER (WHERE rating = -1) as thumbs_down,
            COUNT(*) as total,
            ROUND(AVG(rating::decimal)::decimal, 2) as avg_rating
        FROM user_feedback
        WHERE created_at > NOW() - INTERVAL ':days days'
    """, {"days": days})
    return dict(result.fetchone())
```

### 6. Cost Tracking Per Query

```python
# app/middleware/cost_tracking.py
from anthropic import AsyncAnthropic
import tiktoken

CLAUDE_PRICING = {
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},  # per 1M tokens
    "claude-haiku-4-5-20251001": {"input": 0.25, "output": 1.25},
}

async def generate_with_cost_tracking(
    query: str,
    context: str,
    model: str,
    db,
    user_id: str,
) -> tuple[str, float]:
    client = AsyncAnthropic()

    response = await client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": f"Context:\n{context}\n\nQuestion: {query}\n\nAnswer based on context only."
        }]
    )

    answer = response.content[0].text
    usage = response.usage

    # Calculate cost
    pricing = CLAUDE_PRICING[model]
    cost = (usage.input_tokens * pricing["input"] + usage.output_tokens * pricing["output"]) / 1_000_000

    # Log cost
    await db.execute("""
        INSERT INTO query_costs (user_id, model, input_tokens, output_tokens, cost_usd, created_at)
        VALUES (:user_id, :model, :input, :output, :cost, NOW())
    """, {"user_id": user_id, "model": model, "input": usage.input_tokens,
          "output": usage.output_tokens, "cost": cost})

    return answer, cost
```

---

## Interview Talking Points

```
KEY DESIGN DECISIONS:

1. Hybrid Search (BM25 + Vector):
   - Pure vector: misses exact keyword matches ("invoice #12345")
   - Pure BM25: misses semantic similarity
   - Hybrid with RRF: best of both, no hyperparameter tuning
   - Alpha=0.5: equal weight, adjust based on domain

2. Chunking Strategy:
   - Recursive: good default for most documents
   - Semantic: better quality but 3x slower (needs embeddings)
   - Chunk size 1000/overlap 200: sweet spot for context

3. Reranking:
   - CrossEncoder: free, good quality, 100ms/batch latency
   - Cohere: better quality, $2/1000, add when scale justifies
   - Rerank top-10 → return top-3: reduces LLM context cost

4. RAGAS Evaluation:
   - Run weekly on golden dataset (50-100 manually verified Q&A)
   - Alert if faithfulness < 0.7 (hallucination risk)
   - User thumbs down → review queue → improves golden dataset

5. Cost Optimization:
   - Route simple factual queries → Claude Haiku ($0.25 vs $3/1M)
   - Semantic cache (same question → cached answer)
   - Log every query cost → identify expensive patterns
```
