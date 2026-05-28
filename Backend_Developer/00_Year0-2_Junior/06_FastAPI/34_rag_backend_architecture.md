# FastAPI — RAG Backend Architecture: End-to-End Production System
**FastAPI · Year 0-2 | Senior Backend + Agentic AI**

## Quick Concepts
- **RAG** = Retrieval-Augmented Generation — fetch relevant docs + feed to LLM for grounded answers
- **Chunking** = split docs into 200-1000 token pieces (with overlap)
- **Embedding** = convert text → vector (768-3072 dims) using OpenAI/Voyage/local model
- **Vector DB** = stores embeddings + supports similarity search (pgvector, Pinecone, Weaviate)
- **Retrieval** = find top-K similar chunks for a query
- **Reranking** = second-pass scoring with cross-encoder (Cohere Rerank, BGE)
- **Hybrid search** = vector + BM25 keyword search combined
- **Context injection** = put retrieved chunks in LLM prompt
- **Citations** = link answers to source chunks

---

## Architecture Diagram

```
INGESTION PIPELINE                    QUERY PIPELINE
─────────────────                     ──────────────────
Document upload                       User query
    ↓                                     ↓
Parse (PDF/HTML/MD)                   Query rewrite (optional)
    ↓                                     ↓
Chunk (overlapping)                   Embed query
    ↓                                     ↓
Embed (batch)                         Vector search (pgvector)
    ↓                                     ↓
Store (pgvector)                      Hybrid: + BM25 search
                                          ↓
                                      Rerank (Cohere/BGE)
                                          ↓
                                      Top-K chunks
                                          ↓
                                      LLM with context
                                          ↓
                                      Answer + citations
```

---

## Interview Questions & Answers

### Q1: Document ingestion pipeline (PDF → chunks → embeddings → DB)?

**Answer:** Robust ETL with chunking + batch embeddings.

```python
from typing import List
from uuid import UUID, uuid4
from pypdf import PdfReader
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
import openai
import tiktoken

# ─── Models ───
class Chunk(BaseModel):
    id: UUID
    document_id: UUID
    content: str
    chunk_index: int
    token_count: int
    metadata: dict

# ─── Tokenizer for accurate chunking ───
encoder = tiktoken.get_encoding("cl100k_base")  # GPT-4 tokenizer

def count_tokens(text: str) -> int:
    return len(encoder.encode(text))

# ─── Chunking strategies ───
def chunk_by_tokens(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50,
) -> List[str]:
    """Token-aware sliding window chunking."""
    tokens = encoder.encode(text)
    chunks = []
    start = 0
    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunk_tokens = tokens[start:end]
        chunks.append(encoder.decode(chunk_tokens))
        start += chunk_size - overlap
        if end == len(tokens):
            break
    return chunks

def chunk_by_paragraphs(text: str, max_tokens: int = 500) -> List[str]:
    """Respects paragraph boundaries — better semantic units."""
    paragraphs = text.split("\n\n")
    chunks, current, current_tokens = [], [], 0

    for para in paragraphs:
        para_tokens = count_tokens(para)
        if current_tokens + para_tokens > max_tokens and current:
            chunks.append("\n\n".join(current))
            current, current_tokens = [], 0
        current.append(para)
        current_tokens += para_tokens

    if current:
        chunks.append("\n\n".join(current))
    return chunks

# ─── PDF parsing ───
def parse_pdf(file_path: str) -> str:
    reader = PdfReader(file_path)
    pages = [page.extract_text() for page in reader.pages]
    return "\n\n".join(pages)

# ─── Batch embeddings (cost-efficient) ───
async def embed_batch(texts: List[str], model: str = "text-embedding-3-small") -> List[List[float]]:
    """OpenAI allows 2048 inputs per batch."""
    BATCH_SIZE = 100
    embeddings = []
    client = openai.AsyncOpenAI()

    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i:i + BATCH_SIZE]
        response = await client.embeddings.create(
            model=model,
            input=batch,
            dimensions=1536,  # configurable for text-embedding-3
        )
        embeddings.extend([e.embedding for e in response.data])
    return embeddings

# ─── Full ingestion ───
async def ingest_document(
    file_path: str,
    document_id: UUID,
    session: AsyncSession,
    metadata: dict = None,
):
    # 1. Parse
    text = parse_pdf(file_path)

    # 2. Chunk
    chunks = chunk_by_paragraphs(text, max_tokens=500)

    # 3. Embed (batch)
    embeddings = await embed_batch(chunks)

    # 4. Store
    for idx, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
        await session.execute(
            """
            INSERT INTO chunks (id, document_id, content, chunk_index, embedding, metadata, token_count)
            VALUES (:id, :doc_id, :content, :idx, :emb, :meta, :tokens)
            """,
            {
                "id": uuid4(),
                "doc_id": document_id,
                "content": chunk_text,
                "idx": idx,
                "emb": embedding,
                "meta": metadata or {},
                "tokens": count_tokens(chunk_text),
            },
        )
    await session.commit()
```

---

### Q2: pgvector schema + index setup?

**Answer:** pgvector for embeddings, HNSW index for fast search.

```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Documents table
CREATE TABLE documents (
    id UUID PRIMARY KEY,
    filename TEXT NOT NULL,
    source TEXT,  -- url, file, etc.
    uploaded_by INT REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Chunks table with embedding
CREATE TABLE chunks (
    id UUID PRIMARY KEY,
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    chunk_index INT NOT NULL,
    embedding vector(1536),  -- OpenAI text-embedding-3-small
    metadata JSONB DEFAULT '{}'::jsonb,
    token_count INT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- HNSW index for fast similarity search (recommended over IVFFlat)
CREATE INDEX chunks_embedding_hnsw_idx
ON chunks
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Full-text search index for hybrid retrieval
CREATE INDEX chunks_content_fts_idx
ON chunks
USING gin (to_tsvector('english', content));

-- Metadata filtering index
CREATE INDEX chunks_metadata_idx ON chunks USING gin (metadata);

-- Composite index for filtered searches
CREATE INDEX chunks_doc_id_idx ON chunks(document_id);
```

**Index tuning:**
- `m = 16` (default) — connections per layer; higher = better recall, slower insert
- `ef_construction = 64` — build-time accuracy; higher = better index quality
- Query-time: `SET hnsw.ef_search = 100;` — higher = better recall

---

### Q3: Vector similarity search with metadata filtering?

**Answer:** SQL combines vector search + WHERE filters.

```python
from sqlalchemy import text

async def vector_search(
    session: AsyncSession,
    query_embedding: List[float],
    top_k: int = 10,
    document_ids: List[UUID] = None,
    metadata_filter: dict = None,
) -> List[dict]:
    # Build WHERE clauses
    conditions = []
    params = {"emb": query_embedding, "k": top_k}

    if document_ids:
        conditions.append("document_id = ANY(:doc_ids)")
        params["doc_ids"] = document_ids

    if metadata_filter:
        for key, value in metadata_filter.items():
            param_name = f"meta_{key}"
            conditions.append(f"metadata->>'{key}' = :{param_name}")
            params[param_name] = str(value)

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    query = text(f"""
        SELECT
            id,
            document_id,
            content,
            chunk_index,
            metadata,
            1 - (embedding <=> :emb) AS similarity
        FROM chunks
        {where_clause}
        ORDER BY embedding <=> :emb
        LIMIT :k
    """)

    result = await session.execute(query, params)
    return [dict(r._mapping) for r in result.all()]
```

**Distance operators in pgvector:**
- `<=>` — cosine distance (most common for text)
- `<->` — L2 (Euclidean) distance
- `<#>` — inner product (negative)

**For cosine similarity** (0-1 scale): `1 - (embedding <=> query)`

---

### Q4: Hybrid search (vector + BM25 keyword)?

**Answer:** Combine semantic + lexical for best recall.

```python
async def hybrid_search(
    session: AsyncSession,
    query: str,
    query_embedding: List[float],
    top_k: int = 10,
    alpha: float = 0.7,  # 0=keyword only, 1=vector only
) -> List[dict]:
    """
    Reciprocal Rank Fusion (RRF) — industry standard for hybrid.
    """
    sql = text("""
        WITH vector_search AS (
            SELECT
                id,
                content,
                ROW_NUMBER() OVER (ORDER BY embedding <=> :emb) AS rank
            FROM chunks
            ORDER BY embedding <=> :emb
            LIMIT :k_per_method
        ),
        keyword_search AS (
            SELECT
                id,
                content,
                ROW_NUMBER() OVER (ORDER BY ts_rank_cd(to_tsvector('english', content), websearch_to_tsquery('english', :query)) DESC) AS rank
            FROM chunks
            WHERE to_tsvector('english', content) @@ websearch_to_tsquery('english', :query)
            LIMIT :k_per_method
        ),
        combined AS (
            SELECT
                COALESCE(v.id, k.id) AS id,
                COALESCE(v.content, k.content) AS content,
                COALESCE(1.0 / (60 + v.rank), 0) * :alpha
                  + COALESCE(1.0 / (60 + k.rank), 0) * (1 - :alpha) AS score
            FROM vector_search v
            FULL OUTER JOIN keyword_search k ON v.id = k.id
        )
        SELECT id, content, score
        FROM combined
        ORDER BY score DESC
        LIMIT :k;
    """)

    result = await session.execute(sql, {
        "emb": query_embedding,
        "query": query,
        "k": top_k,
        "k_per_method": top_k * 2,
        "alpha": alpha,
    })
    return [dict(r._mapping) for r in result.all()]
```

**Why hybrid:**
- Vector: catches semantic similarity ("car" ≈ "automobile")
- BM25: catches exact terms, names, IDs (vector embeddings often miss)
- RRF: combines without normalizing scores

---

### Q5: Reranking (second-pass with cross-encoder)?

**Answer:** Retrieve 20-50 candidates → rerank → keep top 5.

```python
import cohere

cohere_client = cohere.AsyncClient(api_key="...")

async def rerank_chunks(
    query: str,
    chunks: List[dict],
    top_n: int = 5,
) -> List[dict]:
    """Cohere Rerank — best off-the-shelf option."""
    documents = [c["content"] for c in chunks]

    response = await cohere_client.rerank(
        model="rerank-english-v3.0",
        query=query,
        documents=documents,
        top_n=top_n,
    )

    # Map back with rerank scores
    return [
        {**chunks[r.index], "rerank_score": r.relevance_score}
        for r in response.results
    ]

# Full retrieval pipeline
async def retrieve(query: str, session: AsyncSession, top_k: int = 5) -> List[dict]:
    # 1. Embed query
    query_emb = (await embed_batch([query]))[0]

    # 2. Hybrid search (over-fetch)
    candidates = await hybrid_search(session, query, query_emb, top_k=30)

    # 3. Rerank
    reranked = await rerank_chunks(query, candidates, top_n=top_k)

    return reranked
```

**Alternative: Local reranker** (BGE) — no API cost:
```python
from sentence_transformers import CrossEncoder

reranker = CrossEncoder("BAAI/bge-reranker-large")

def rerank_local(query: str, chunks: List[dict], top_n: int = 5) -> List[dict]:
    pairs = [[query, c["content"]] for c in chunks]
    scores = reranker.predict(pairs)
    scored = list(zip(chunks, scores))
    scored.sort(key=lambda x: x[1], reverse=True)
    return [{**c, "rerank_score": float(s)} for c, s in scored[:top_n]]
```

---

### Q6: FastAPI endpoints (ingest + query)?

**Answer:**
```python
from fastapi import FastAPI, UploadFile, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
import aiofiles
import tempfile

app = FastAPI()

# ─── Upload endpoint ───
@app.post("/documents/upload")
async def upload_document(
    file: UploadFile,
    background: BackgroundTasks,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    if not file.filename.lower().endswith((".pdf", ".txt", ".md")):
        raise HTTPException(400, "Unsupported file type")

    if file.size and file.size > 50 * 1024 * 1024:
        raise HTTPException(413, "File too large (max 50MB)")

    # Save temp file
    doc_id = uuid4()
    suffix = "." + file.filename.split(".")[-1]
    async with aiofiles.tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await file.read()
        await tmp.write(content)
        tmp_path = tmp.name

    # Create document record
    await session.execute(
        "INSERT INTO documents (id, filename, uploaded_by) VALUES (:id, :name, :uid)",
        {"id": doc_id, "name": file.filename, "uid": user_id},
    )
    await session.commit()

    # Background ingestion (heavy operation)
    background.add_task(_ingest_async, tmp_path, doc_id)

    return {"document_id": doc_id, "status": "processing"}

async def _ingest_async(file_path: str, doc_id: UUID):
    """Run in background — embed + store."""
    async with async_session() as session:
        try:
            await ingest_document(file_path, doc_id, session)
        finally:
            os.unlink(file_path)

# ─── Query endpoint with streaming ───
class RAGRequest(BaseModel):
    query: str
    document_ids: List[UUID] | None = None
    top_k: int = 5

@app.post("/rag/query")
async def rag_query(
    req: RAGRequest,
    session: AsyncSession = Depends(get_db),
):
    # 1. Retrieve
    chunks = await retrieve(req.query, session, top_k=req.top_k)

    if not chunks:
        return {"answer": "I couldn't find relevant information.", "citations": []}

    # 2. Build context with citations
    context = "\n\n".join([
        f"[Source {i+1}] (doc: {c['document_id']}, score: {c.get('rerank_score', 0):.3f})\n{c['content']}"
        for i, c in enumerate(chunks)
    ])

    # 3. LLM call
    system = """You are a helpful assistant. Answer the user's question using ONLY the provided sources.
- Cite sources using [Source N] notation.
- If the answer isn't in the sources, say "I don't have that information."
- Never invent facts beyond the sources."""

    async def stream():
        async with client.messages.stream(
            model="claude-opus-4-7",
            max_tokens=2048,
            system=system,
            messages=[{
                "role": "user",
                "content": f"<sources>\n{context}\n</sources>\n\n<question>{req.query}</question>",
            }],
        ) as response:
            async for text_chunk in response.text_stream:
                yield f"data: {json.dumps({'text': text_chunk})}\n\n"

            yield f"data: {json.dumps({'type':'done', 'citations': [{'id':str(c['id']),'doc_id':str(c['document_id']),'score':c.get('rerank_score',0)} for c in chunks]})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")
```

---

### Q7: Semantic caching (huge cost saver)?

**Answer:** Cache query embeddings + answers — serve duplicate queries from cache.

```python
import json
from hashlib import sha256

CACHE_SIMILARITY_THRESHOLD = 0.97  # very strict for safety

async def get_cached_answer(
    query: str,
    query_embedding: List[float],
    session: AsyncSession,
) -> dict | None:
    """Check semantic cache for similar past queries."""
    result = await session.execute(
        text("""
            SELECT id, query, answer, citations, 1 - (query_embedding <=> :emb) AS sim
            FROM rag_cache
            WHERE 1 - (query_embedding <=> :emb) > :threshold
              AND created_at > NOW() - INTERVAL '24 hours'
            ORDER BY query_embedding <=> :emb
            LIMIT 1
        """),
        {"emb": query_embedding, "threshold": CACHE_SIMILARITY_THRESHOLD},
    )
    row = result.first()
    if row:
        return {
            "answer": row.answer,
            "citations": row.citations,
            "cached": True,
            "cache_similarity": float(row.sim),
        }
    return None

async def save_to_cache(query: str, embedding: List[float], answer: str, citations: list, session: AsyncSession):
    await session.execute(
        text("""
            INSERT INTO rag_cache (id, query, query_embedding, answer, citations, created_at)
            VALUES (:id, :q, :emb, :ans, :cit, NOW())
        """),
        {"id": uuid4(), "q": query, "emb": embedding, "ans": answer, "cit": json.dumps(citations)},
    )
    await session.commit()
```

**Schema:**
```sql
CREATE TABLE rag_cache (
    id UUID PRIMARY KEY,
    query TEXT,
    query_embedding vector(1536),
    answer TEXT,
    citations JSONB,
    created_at TIMESTAMPTZ
);
CREATE INDEX rag_cache_emb_idx ON rag_cache USING hnsw (query_embedding vector_cosine_ops);
```

---

### Q8: Evaluation (RAGAS) — how do you measure RAG quality?

**Answer:** Automated eval metrics — context relevance, answer faithfulness, answer correctness.

```python
# pip install ragas
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
)
from datasets import Dataset

async def evaluate_rag(test_questions: List[dict]):
    """
    test_questions: [{"question": "...", "ground_truth": "..."}]
    """
    rows = []
    for q in test_questions:
        chunks = await retrieve(q["question"], session)
        contexts = [c["content"] for c in chunks]

        # Get LLM answer
        answer = await rag_query_sync(q["question"], chunks)

        rows.append({
            "question": q["question"],
            "answer": answer,
            "contexts": contexts,
            "ground_truth": q["ground_truth"],
        })

    dataset = Dataset.from_list(rows)
    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
    )
    return result.to_pandas()
```

**Targets:**
- Faithfulness > 0.85 (answer matches sources)
- Answer relevancy > 0.80 (answer addresses question)
- Context precision > 0.75 (retrieved chunks are useful)
- Context recall > 0.70 (ground truth present in chunks)

---

## Production Gotchas

| Gotcha | Fix |
|---|---|
| Chunks too small | Lose context — use 300-800 tokens |
| Chunks too big | Dilutes signal — exceeds LLM context efficiency |
| No overlap | Boundary info lost — 10-20% overlap |
| Wrong embedding model | Use same model for ingest + query (always) |
| No reranking | Top-10 from vector ≠ top-5 most relevant |
| Metadata not indexed | GIN index on JSONB for filters |
| HNSW build slow | Use IVFFlat for >10M rows, then HNSW |
| Stale embeddings | Re-embed when chunks updated; track version |
| No citations | Users can't verify; hallucination feels real |
| Indexing blocks queries | Build HNSW concurrently: `CREATE INDEX CONCURRENTLY` |

---

## Cost Optimization

| Strategy | Saving |
|---|---|
| Use `text-embedding-3-small` (1536 dims vs 3072) | 50% embed cost |
| Batch embeddings (100 at a time) | Up to 50% via batching |
| Semantic cache (24h TTL) | 30-70% LLM cost on repeat queries |
| Cohere Rerank cheaper than running Opus | Use Haiku/cheap model with better context |
| Anthropic prompt caching (system + context) | Up to 90% on input tokens |
| Truncate context to top-5 instead of top-20 | Direct token reduction |

---

## Senior-level Checklist

- [ ] Token-aware chunking (300-800 tokens, 10-20% overlap)
- [ ] Batch embeddings (cost saving)
- [ ] pgvector with HNSW index
- [ ] Hybrid search (vector + BM25)
- [ ] Reranking (Cohere or BGE)
- [ ] Metadata filtering (JSONB + GIN)
- [ ] Background ingestion (Celery or BackgroundTasks)
- [ ] Streaming answers (SSE)
- [ ] Citations in responses
- [ ] Semantic caching layer
- [ ] RAGAS evaluation pipeline
- [ ] Re-indexing strategy when chunks update
- [ ] Prompt caching for system + large context
- [ ] Indirect injection protection (Sanitize external content — see doc 33)

---

## Related Docs
- `31_llm_integration_fastapi.md` — base LLM
- `32_function_calling_endpoints.md` — RAG as a tool
- `33_prompt_injection_security.md` — sanitize retrieved content
- `00_Year0-2_Junior/04_Database_SQL/06_pgvector_schema_design.md` — pgvector deep
- `00_Year0-2_Junior/04_Database_SQL/18_pgvector_ai_workloads.md` — production tuning
- `00_Year0-2_Junior/09_Caching/06_semantic_caching_llm.md` — cache patterns
