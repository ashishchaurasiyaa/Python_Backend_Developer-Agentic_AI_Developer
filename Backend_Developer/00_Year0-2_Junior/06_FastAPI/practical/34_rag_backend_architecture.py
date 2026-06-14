"""
FastAPI RAG Backend Architecture — End-to-End Production System

Covers the full Retrieval-Augmented Generation (RAG) stack:

  INGESTION PIPELINE              QUERY PIPELINE
  ──────────────────              ──────────────
  Document upload (PDF/TXT/MD)    User query
      ↓                               ↓
  Parse text                      Embed query
      ↓                               ↓
  Token-aware chunking            Hybrid search (vector + BM25)
      ↓                               ↓
  Batch embed                     Rerank (Cohere / local BGE)
      ↓                               ↓
  Store in pgvector               Top-K chunks → LLM
                                      ↓
                                  Streaming answer + citations

Sections:
  1.  Shared Pydantic models
  2.  Tokenizer & chunking strategies
  3.  PDF / plain-text parsing
  4.  Batch embedding (OpenAI)
  5.  Full document ingestion
  6.  pgvector similarity search
  7.  Hybrid search (vector + BM25 via RRF)
  8.  Reranking (Cohere + local cross-encoder)
  9.  Full retrieval pipeline
  10. Semantic caching layer (pgvector)
  11. FastAPI application (upload + streaming query endpoints)
  12. RAGAS evaluation harness
  13. SQL schema reference (as a string constant)
  14. Production notes & cost-optimisation cheatsheet

External dependencies (install as needed):
  pip install fastapi uvicorn[standard] sqlalchemy[asyncio] asyncpg
  pip install openai tiktoken pypdf aiofiles
  pip install cohere sentence-transformers
  pip install ragas datasets
  pip install structlog
"""

# ==========================================================================
# 0. STANDARD-LIBRARY IMPORTS
# ==========================================================================

import asyncio
import json
import logging
import os
import warnings
from functools import wraps
from hashlib import sha256
from io import BytesIO
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

# ==========================================================================
# 1. PYDANTIC MODELS
# ==========================================================================

# pip install pydantic (bundled with fastapi)
from pydantic import BaseModel, Field


class Chunk(BaseModel):
    """A single text chunk extracted from a parent document."""

    id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    content: str
    chunk_index: int
    token_count: int
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Document(BaseModel):
    """Metadata record for an ingested document."""

    id: UUID = Field(default_factory=uuid4)
    filename: str
    source: Optional[str] = None        # "upload" | URL | file path
    uploaded_by: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RAGRequest(BaseModel):
    """Body for POST /rag/query."""

    query: str = Field(..., min_length=1, max_length=2000)
    document_ids: Optional[List[UUID]] = None   # optional scope filter
    top_k: int = Field(default=5, ge=1, le=20)
    use_cache: bool = True


class ChunkResult(BaseModel):
    """A retrieved chunk enriched with similarity/rerank score."""

    id: UUID
    document_id: UUID
    content: str
    chunk_index: int
    metadata: Dict[str, Any]
    similarity: float = 0.0
    rerank_score: Optional[float] = None


class RAGResponse(BaseModel):
    """Non-streaming RAG answer (used in evaluation harness)."""

    answer: str
    citations: List[Dict[str, Any]]
    cached: bool = False
    cache_similarity: Optional[float] = None


# ==========================================================================
# 2. TOKENIZER & CHUNKING STRATEGIES
# ==========================================================================

# pip install tiktoken
try:
    import tiktoken

    _encoder = tiktoken.get_encoding("cl100k_base")   # GPT-4 / text-embedding-3 tokenizer

    def count_tokens(text: str) -> int:
        """Return the number of cl100k_base tokens in *text*."""
        return len(_encoder.encode(text))

    def _encode(text: str) -> List[int]:
        return _encoder.encode(text)

    def _decode(tokens: List[int]) -> str:
        return _encoder.decode(tokens)

except ImportError:
    # Graceful fallback: approximate 1 token ≈ 4 characters
    def count_tokens(text: str) -> int:  # type: ignore[misc]
        return max(1, len(text) // 4)

    def _encode(text: str) -> List[int]:  # type: ignore[misc]
        # Character-level approximation (never used at runtime without tiktoken)
        return list(text.encode())

    def _decode(tokens: List[int]) -> str:  # type: ignore[misc]
        return bytes(tokens).decode(errors="replace")


def chunk_by_tokens(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50,
) -> List[str]:
    """
    Sliding-window token-aware chunking.

    Production recommendation: chunk_size 300–800, overlap 10–20%.
    Uses tiktoken to stay within model context limits precisely.
    """
    tokens = _encode(text)
    chunks: List[str] = []
    start = 0

    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunks.append(_decode(tokens[start:end]))
        if end == len(tokens):
            break
        start += chunk_size - overlap   # advance by (size - overlap) for continuity

    return chunks


def chunk_by_paragraphs(text: str, max_tokens: int = 500) -> List[str]:
    """
    Paragraph-boundary chunking — preserves semantic units better than
    raw sliding-window for prose / documentation content.

    Paragraphs are merged greedily up to *max_tokens*; a paragraph that
    exceeds the limit on its own is emitted as a single oversized chunk
    (caller should be aware).
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: List[str] = []
    current: List[str] = []
    current_tokens = 0

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


# ==========================================================================
# 3. DOCUMENT PARSING  (PDF / plain-text / Markdown)
# ==========================================================================

# pip install pypdf
def parse_pdf(file_bytes: bytes) -> str:
    """
    Extract plain text from a PDF given its raw bytes.
    Pages are joined with double newlines to preserve paragraph structure.
    """
    try:
        from pypdf import PdfReader  # type: ignore[import]

        reader = PdfReader(BytesIO(file_bytes))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n\n".join(pages)
    except ImportError:
        raise RuntimeError("pypdf is required for PDF parsing — pip install pypdf")


def parse_text(file_bytes: bytes, encoding: str = "utf-8") -> str:
    """Decode a plain-text or Markdown file."""
    return file_bytes.decode(encoding, errors="replace")


def parse_document(filename: str, file_bytes: bytes) -> str:
    """Route to the appropriate parser based on file extension."""
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext == "pdf":
        return parse_pdf(file_bytes)
    elif ext in ("txt", "md", "rst"):
        return parse_text(file_bytes)
    else:
        raise ValueError(f"Unsupported file type: .{ext}  (accepted: pdf, txt, md, rst)")


# ==========================================================================
# 4. BATCH EMBEDDING  (OpenAI)
# ==========================================================================

# pip install openai
EMBEDDING_MODEL = "text-embedding-3-small"   # 1536 dims — best cost/quality ratio
EMBEDDING_BATCH_SIZE = 100                    # OpenAI allows up to 2048 inputs per call


async def embed_batch(
    texts: List[str],
    model: str = EMBEDDING_MODEL,
    dimensions: int = 1536,
) -> List[List[float]]:
    """
    Embed a list of texts in batches of EMBEDDING_BATCH_SIZE.

    Cost optimisation:
    - text-embedding-3-small at 1536 dims ≈ 50% cost of 3072-dim variant.
    - Batching reduces per-call overhead; up to 50% saving vs. per-chunk calls.

    Always use the SAME model for ingestion and query — mismatched embedding
    spaces produce meaningless similarity scores.
    """
    import openai  # pip install openai

    client = openai.AsyncOpenAI()
    embeddings: List[List[float]] = []

    for i in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = texts[i : i + EMBEDDING_BATCH_SIZE]
        response = await client.embeddings.create(
            model=model,
            input=batch,
            dimensions=dimensions,
        )
        embeddings.extend([e.embedding for e in response.data])

    return embeddings


# ==========================================================================
# 5. DOCUMENT INGESTION PIPELINE
# ==========================================================================

async def ingest_document(
    filename: str,
    file_bytes: bytes,
    document_id: UUID,
    session: Any,                          # sqlalchemy AsyncSession
    metadata: Optional[Dict[str, Any]] = None,
    chunk_size: int = 500,
    overlap: int = 50,
) -> int:
    """
    Full ingestion pipeline: parse → chunk → embed (batch) → store in pgvector.

    Returns the number of chunks written.

    Design notes:
    - Paragraph-boundary chunking is preferred; falls back to token-window.
    - Embeddings are requested in a single batched API call (cost-efficient).
    - All chunks are flushed in one commit (atomic document ingestion).
    """
    from sqlalchemy import text  # pip install sqlalchemy[asyncio]

    # 1. Parse
    raw_text = parse_document(filename, file_bytes)

    # 2. Chunk  (prefer paragraph boundaries; they form better semantic units)
    text_chunks = chunk_by_paragraphs(raw_text, max_tokens=chunk_size)
    if not text_chunks:
        raise ValueError(f"No text could be extracted from '{filename}'")

    # 3. Embed all chunks in one batched call
    embeddings = await embed_batch(text_chunks)

    # 4. Store — INSERT chunks with their vector embeddings
    for idx, (chunk_text, embedding) in enumerate(zip(text_chunks, embeddings)):
        await session.execute(
            text(
                """
                INSERT INTO chunks
                    (id, document_id, content, chunk_index, embedding, metadata, token_count)
                VALUES
                    (:id, :doc_id, :content, :idx, :emb, :meta, :tokens)
                """
            ),
            {
                "id": str(uuid4()),
                "doc_id": str(document_id),
                "content": chunk_text,
                "idx": idx,
                "emb": embedding,
                "meta": json.dumps(metadata or {}),
                "tokens": count_tokens(chunk_text),
            },
        )

    await session.commit()
    return len(text_chunks)


# ==========================================================================
# 6. VECTOR SIMILARITY SEARCH  (pgvector)
# ==========================================================================

async def vector_search(
    session: Any,
    query_embedding: List[float],
    top_k: int = 10,
    document_ids: Optional[List[UUID]] = None,
    metadata_filter: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """
    Cosine-similarity search via pgvector's <=> operator.

    Supports:
    - document_ids: scope retrieval to a subset of documents.
    - metadata_filter: exact JSONB key-value predicates (GIN-indexed).

    pgvector distance operators:
    - <=>  cosine distance (most useful for text; 0 = identical, 2 = opposite)
    - <->  L2 (Euclidean) distance
    - <#>  negative inner product

    Cosine similarity = 1 - cosine_distance, so we use `1 - (embedding <=> :emb)`
    as the similarity score returned to callers.
    """
    from sqlalchemy import text  # noqa: F811

    conditions: List[str] = []
    params: Dict[str, Any] = {"emb": query_embedding, "k": top_k}

    if document_ids:
        conditions.append("document_id = ANY(:doc_ids)")
        params["doc_ids"] = [str(d) for d in document_ids]

    if metadata_filter:
        for key, value in metadata_filter.items():
            param_name = f"meta_{key}"
            conditions.append(f"metadata->>'{key}' = :{param_name}")
            params[param_name] = str(value)

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    sql = text(
        f"""
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
        """
    )

    result = await session.execute(sql, params)
    return [dict(r._mapping) for r in result.all()]


# ==========================================================================
# 7. HYBRID SEARCH  (vector + BM25 via Reciprocal Rank Fusion)
# ==========================================================================

async def hybrid_search(
    session: Any,
    query: str,
    query_embedding: List[float],
    top_k: int = 20,
    alpha: float = 0.7,
) -> List[Dict[str, Any]]:
    """
    Reciprocal Rank Fusion (RRF) combining vector and BM25 keyword scores.

    alpha = 1.0 → pure vector search
    alpha = 0.0 → pure keyword (BM25) search
    alpha = 0.7 → recommended default (semantic-leaning hybrid)

    Why hybrid?
    - Vector catches semantic equivalence ("car" ≈ "automobile").
    - BM25 catches exact terms, proper nouns, codes, and IDs that
      vector embeddings frequently miss.
    - RRF merges without requiring score normalisation across spaces.

    The constant 60 in `1.0 / (60 + rank)` is the standard RRF smoothing
    factor that dampens rank differences at the top and prevents any single
    method from dominating.
    """
    from sqlalchemy import text  # noqa: F811

    sql = text(
        """
        WITH vector_ranks AS (
            SELECT
                id,
                content,
                document_id,
                chunk_index,
                metadata,
                ROW_NUMBER() OVER (ORDER BY embedding <=> :emb) AS rank
            FROM chunks
            ORDER BY embedding <=> :emb
            LIMIT :k_cand
        ),
        keyword_ranks AS (
            SELECT
                id,
                content,
                document_id,
                chunk_index,
                metadata,
                ROW_NUMBER() OVER (
                    ORDER BY
                        ts_rank_cd(
                            to_tsvector('english', content),
                            websearch_to_tsquery('english', :query)
                        ) DESC
                ) AS rank
            FROM chunks
            WHERE to_tsvector('english', content)
                  @@ websearch_to_tsquery('english', :query)
            LIMIT :k_cand
        ),
        fused AS (
            SELECT
                COALESCE(v.id, k.id)                            AS id,
                COALESCE(v.content, k.content)                  AS content,
                COALESCE(v.document_id, k.document_id)          AS document_id,
                COALESCE(v.chunk_index, k.chunk_index)          AS chunk_index,
                COALESCE(v.metadata, k.metadata)                AS metadata,
                COALESCE(1.0 / (60 + v.rank), 0) * :alpha
                    + COALESCE(1.0 / (60 + k.rank), 0) * (1.0 - :alpha) AS score
            FROM vector_ranks v
            FULL OUTER JOIN keyword_ranks k ON v.id = k.id
        )
        SELECT id, content, document_id, chunk_index, metadata, score
        FROM fused
        ORDER BY score DESC
        LIMIT :k
        """
    )

    result = await session.execute(
        sql,
        {
            "emb": query_embedding,
            "query": query,
            "k": top_k,
            "k_cand": top_k * 3,   # over-fetch candidates before fusion
            "alpha": alpha,
        },
    )
    return [dict(r._mapping) for r in result.all()]


# ==========================================================================
# 8. RERANKING  (Cohere + local BGE cross-encoder)
# ==========================================================================

async def rerank_cohere(
    query: str,
    chunks: List[Dict[str, Any]],
    top_n: int = 5,
    model: str = "rerank-english-v3.0",
) -> List[Dict[str, Any]]:
    """
    Second-pass reranking with Cohere's cross-encoder API.

    Cross-encoders score each (query, chunk) pair jointly — far more accurate
    than bi-encoder similarity but too expensive to run over all chunks.
    Pattern: retrieve 20–50 candidates → rerank → keep top 5.

    Requires: pip install cohere  and COHERE_API_KEY env var.
    """
    import cohere  # pip install cohere

    client = cohere.AsyncClient(api_key=os.environ.get("COHERE_API_KEY", ""))
    documents = [c["content"] for c in chunks]

    response = await client.rerank(
        model=model,
        query=query,
        documents=documents,
        top_n=top_n,
    )

    return [
        {**chunks[r.index], "rerank_score": r.relevance_score}
        for r in response.results
    ]


def rerank_local(
    query: str,
    chunks: List[Dict[str, Any]],
    top_n: int = 5,
    model_name: str = "BAAI/bge-reranker-large",
) -> List[Dict[str, Any]]:
    """
    Local cross-encoder reranking — no API cost, requires GPU for speed.

    Uses sentence-transformers CrossEncoder.
    Requires: pip install sentence-transformers

    Trade-off vs. Cohere Rerank:
    - Pro: free, private, no latency to external API.
    - Con: requires GPU for acceptable throughput; model download ~1 GB.
    """
    from sentence_transformers import CrossEncoder  # pip install sentence-transformers

    reranker = CrossEncoder(model_name)
    pairs = [[query, c["content"]] for c in chunks]
    scores: List[float] = reranker.predict(pairs)

    scored = sorted(zip(chunks, scores), key=lambda x: x[1], reverse=True)
    return [{**c, "rerank_score": float(s)} for c, s in scored[:top_n]]


# ==========================================================================
# 9. FULL RETRIEVAL PIPELINE
# ==========================================================================

async def retrieve(
    query: str,
    session: Any,
    top_k: int = 5,
    use_cohere_rerank: bool = True,
    alpha: float = 0.7,
) -> List[Dict[str, Any]]:
    """
    Orchestrate the complete retrieval pipeline:

        embed query → hybrid search (over-fetch) → rerank → top-K

    Over-fetch factor: retrieve 30 candidates before reranking to top_k.
    This compensates for the recall loss inherent in approximate nearest-
    neighbour indexes (HNSW) and BM25 scoring.
    """
    # 1. Embed the query (single item — reuse batch embed for simplicity)
    query_embedding = (await embed_batch([query]))[0]

    # 2. Hybrid search — retrieve 6× candidates so reranker has headroom
    candidates = await hybrid_search(
        session,
        query,
        query_embedding,
        top_k=max(30, top_k * 6),
        alpha=alpha,
    )

    if not candidates:
        return []

    # 3. Rerank — second-pass cross-encoder scoring
    if use_cohere_rerank:
        reranked = await rerank_cohere(query, candidates, top_n=top_k)
    else:
        reranked = rerank_local(query, candidates, top_n=top_k)

    return reranked


# ==========================================================================
# 10. SEMANTIC CACHING LAYER
# ==========================================================================

CACHE_SIMILARITY_THRESHOLD = 0.97   # strict — only serve cache on near-identical queries
CACHE_TTL_HOURS = 24                 # cached answers expire after 24 hours


async def get_cached_answer(
    query_embedding: List[float],
    session: Any,
) -> Optional[Dict[str, Any]]:
    """
    Look up the semantic cache (rag_cache table in pgvector).

    Returns a cached answer dict if a sufficiently similar past query exists
    within the TTL window, otherwise returns None.

    Cost impact: 30–70% reduction in LLM calls on workloads with repeated or
    paraphrased questions (e.g. FAQ-style chatbots).
    """
    from sqlalchemy import text  # noqa: F811

    result = await session.execute(
        text(
            """
            SELECT id, query, answer, citations,
                   1 - (query_embedding <=> :emb) AS sim
            FROM rag_cache
            WHERE 1 - (query_embedding <=> :emb) > :threshold
              AND created_at > NOW() - INTERVAL ':ttl hours'
            ORDER BY query_embedding <=> :emb
            LIMIT 1
            """
        ),
        {
            "emb": query_embedding,
            "threshold": CACHE_SIMILARITY_THRESHOLD,
            "ttl": CACHE_TTL_HOURS,
        },
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


async def save_to_cache(
    query: str,
    embedding: List[float],
    answer: str,
    citations: List[Dict[str, Any]],
    session: Any,
) -> None:
    """Persist a successful RAG answer to the semantic cache."""
    from sqlalchemy import text  # noqa: F811

    await session.execute(
        text(
            """
            INSERT INTO rag_cache (id, query, query_embedding, answer, citations, created_at)
            VALUES (:id, :q, :emb, :ans, :cit, NOW())
            """
        ),
        {
            "id": str(uuid4()),
            "q": query,
            "emb": embedding,
            "ans": answer,
            "cit": json.dumps(citations),
        },
    )
    await session.commit()


# ==========================================================================
# 11. FASTAPI APPLICATION  (upload + streaming RAG query)
# ==========================================================================

# pip install fastapi uvicorn[standard] aiofiles python-multipart


ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".rst"}
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024   # 50 MB

RAG_SYSTEM_PROMPT = """You are a precise, helpful assistant.
Answer the user's question using ONLY the provided source chunks.
- Cite sources with [Source N] notation inline.
- If the answer is not in the sources, say "I don't have that information."
- Never invent facts beyond what the sources contain."""


def create_app() -> "FastAPI":  # type: ignore[name-defined]
    """
    Application factory — call this to obtain the FastAPI instance.

    Using a factory rather than a module-level `app = FastAPI()` has two
    benefits:
    1. The module can be imported without triggering FastAPI route
       registration (and the python-multipart dependency check).
    2. Tests can call `create_app()` in isolation with fresh state.

    Usage:
        # production entry-point (pass to uvicorn)
        app = create_app()

        # uvicorn 34_rag_backend_architecture:app --reload
        # (or use: uvicorn "34_rag_backend_architecture:create_app()" --factory)
    """
    # Deferred imports so the module is importable without fastapi installed
    from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, UploadFile  # noqa: F401
    from fastapi.responses import StreamingResponse  # noqa: F401

    _app = FastAPI(
        title="RAG Backend",
        description="Production-grade Retrieval-Augmented Generation API",
        version="1.0.0",
    )

    # ─── Dependency stubs ──────────────────────────────────────────────────
    # In a real application these would connect to a real PostgreSQL + pgvector
    # database.  They are stubs here so the module is importable without a live DB.

    async def get_db():  # pragma: no cover
        """
        Yield an async SQLAlchemy session.
        Replace this with a real engine / session factory.
        """
        raise NotImplementedError(
            "get_db must be replaced with a real AsyncSession dependency."
        )
        yield  # type: ignore[misc]  # makes this a generator for Depends()

    async def get_current_user_id(request: Request) -> int:  # pragma: no cover
        """Extract authenticated user ID from request (JWT / session)."""
        raise NotImplementedError("Authentication dependency not wired.")

    # ─── Background ingestion helper ───────────────────────────────────────

    async def _ingest_background(
        filename: str,
        file_bytes: bytes,
        doc_id: UUID,
    ) -> None:
        """
        Run full ingestion in the background (after the HTTP response is sent).
        Uses a fresh DB session so it does not share the request session.
        """
        # In production: import async_session_factory from your DB module.
        logging.getLogger(__name__).info(
            "background ingestion started",
            extra={"document_id": str(doc_id), "filename": filename},
        )
        # async with async_session() as session:
        #     await ingest_document(filename, file_bytes, doc_id, session)

    # ─── Upload endpoint ────────────────────────────────────────────────────

    @_app.post("/documents/upload", summary="Upload and ingest a document")
    async def upload_document(
        file: UploadFile,
        background: BackgroundTasks,
        session: Any = Depends(get_db),
    ):
        """
        Accept a PDF / TXT / MD file, create a document record, and schedule
        the heavy parse + embed + store pipeline as a background task.

        Ingestion is asynchronous — the endpoint returns immediately with
        { document_id, status: "processing" } so the client is not blocked
        while embeddings are being computed.
        """
        from sqlalchemy import text as sa_text  # noqa: F811

        # Validate extension
        suffix = "." + (file.filename or "").rsplit(".", 1)[-1].lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type '{suffix}'. Accepted: {ALLOWED_EXTENSIONS}",
            )

        # Read content before streaming ends
        raw_bytes = await file.read()

        # Validate size (UploadFile.size is not always populated — check raw bytes)
        if len(raw_bytes) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File exceeds 50 MB limit ({len(raw_bytes) / 1024 / 1024:.1f} MB)",
            )

        # Create document metadata record
        doc_id = uuid4()
        await session.execute(
            sa_text(
                "INSERT INTO documents (id, filename, source) VALUES (:id, :name, 'upload')"
            ),
            {"id": str(doc_id), "name": file.filename},
        )
        await session.commit()

        # Schedule heavy ingestion to run after response is sent
        background.add_task(_ingest_background, file.filename, raw_bytes, doc_id)

        return {"document_id": str(doc_id), "status": "processing"}

    # ─── RAG query endpoint (streaming SSE) ────────────────────────────────

    @_app.post("/rag/query", summary="RAG query with streaming answer")
    async def rag_query(
        req: RAGRequest,
        session: Any = Depends(get_db),
    ):
        """
        Full RAG query pipeline with Server-Sent Events streaming:

        1. Check semantic cache (skip LLM if near-identical query seen recently).
        2. Embed query.
        3. Hybrid search → rerank → top-K chunks.
        4. Build context with [Source N] labels.
        5. Stream answer from Claude (Anthropic) with citations in final event.

        Response format: text/event-stream
          data: {"text": "..."}           # partial token
          data: {"type":"done", "citations":[...]}  # final event
        """
        import anthropic  # pip install anthropic

        # 1. Embed query first — needed for both cache check and retrieval
        query_embedding = (await embed_batch([req.query]))[0]

        # 2. Check semantic cache
        if req.use_cache:
            cached = await get_cached_answer(query_embedding, session)
            if cached:
                # Return instantly — no LLM call, no retrieval cost
                async def _cached_stream():
                    yield f"data: {json.dumps({'text': cached['answer']})}\n\n"
                    yield (
                        "data: "
                        + json.dumps(
                            {
                                "type": "done",
                                "citations": cached["citations"],
                                "cached": True,
                                "cache_similarity": cached["cache_similarity"],
                            }
                        )
                        + "\n\n"
                    )

                return StreamingResponse(_cached_stream(), media_type="text/event-stream")

        # 3. Retrieve relevant chunks
        retr_chunks = await retrieve(req.query, session, top_k=req.top_k)
        if not retr_chunks:
            async def _empty_stream():
                yield "data: " + json.dumps({"text": "I could not find relevant information."}) + "\n\n"
                yield "data: " + json.dumps({"type": "done", "citations": []}) + "\n\n"

            return StreamingResponse(_empty_stream(), media_type="text/event-stream")

        # 4. Build context block with citation labels
        context_parts: List[str] = []
        for i, c in enumerate(retr_chunks):
            score = c.get("rerank_score") or c.get("score") or c.get("similarity") or 0.0
            header = (
                f"[Source {i + 1}]"
                f" (doc: {c.get('document_id', 'unknown')}, score: {score:.3f})"
            )
            context_parts.append(f"{header}\n{c['content']}")

        context = "\n\n---\n\n".join(context_parts)
        user_message = (
            f"<sources>\n{context}\n</sources>\n\n"
            f"<question>{req.query}</question>"
        )

        # 5. Stream answer from Claude
        llm_client = anthropic.AsyncAnthropic()
        collected_text: List[str] = []

        async def _stream():
            async with llm_client.messages.stream(
                model="claude-opus-4-5",
                max_tokens=2048,
                system=RAG_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            ) as response:
                async for text_chunk in response.text_stream:
                    collected_text.append(text_chunk)
                    yield f"data: {json.dumps({'text': text_chunk})}\n\n"

            # Build citations list for the final event
            citations = [
                {
                    "id": str(c.get("id", "")),
                    "document_id": str(c.get("document_id", "")),
                    "chunk_index": c.get("chunk_index", 0),
                    "score": round(
                        float(
                            c.get("rerank_score")
                            or c.get("score")
                            or c.get("similarity")
                            or 0.0
                        ),
                        4,
                    ),
                }
                for c in retr_chunks
            ]
            yield f"data: {json.dumps({'type': 'done', 'citations': citations})}\n\n"

            # Persist to cache asynchronously (fire-and-forget)
            full_answer = "".join(collected_text)
            asyncio.create_task(
                save_to_cache(req.query, query_embedding, full_answer, citations, session)
            )

        return StreamingResponse(_stream(), media_type="text/event-stream")

    return _app


# Convenience module-level `app` for uvicorn / gunicorn discovery.
# This line is commented out intentionally — uncomment when deploying so that
# `uvicorn 34_rag_backend_architecture:app` works without python-multipart
# being required at import time in study/test environments.
#
# app = create_app()


# ==========================================================================
# 12. RAGAS EVALUATION HARNESS
# ==========================================================================

async def evaluate_rag_pipeline(
    test_questions: List[Dict[str, str]],
    session: Any,
) -> Any:
    """
    Automated RAG quality evaluation using the RAGAS framework.

    test_questions format:
        [{"question": "What is X?", "ground_truth": "X is ..."}]

    Targets (senior-level benchmarks):
        faithfulness     > 0.85   (answer sticks to sources)
        answer_relevancy > 0.80   (answer addresses the question)
        context_precision > 0.75  (retrieved chunks are useful)
        context_recall   > 0.70   (ground truth present in retrieved chunks)

    Requires: pip install ragas datasets
    """
    # pip install ragas datasets
    from datasets import Dataset  # type: ignore[import]
    from ragas import evaluate  # type: ignore[import]
    from ragas.metrics import (  # type: ignore[import]
        answer_relevancy,
        context_precision,
        context_recall,
        faithfulness,
    )
    import anthropic  # noqa: F811

    client = anthropic.AsyncAnthropic()

    async def _get_answer(question: str, context_chunks: List[Dict[str, Any]]) -> str:
        """Run a single non-streaming RAG call for evaluation purposes."""
        context = "\n\n".join(c["content"] for c in context_chunks)
        msg = await client.messages.create(
            model="claude-haiku-4-5",   # cheaper model for eval runs
            max_tokens=1024,
            system=RAG_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"<sources>\n{context}\n</sources>\n\n"
                        f"<question>{question}</question>"
                    ),
                }
            ],
        )
        return msg.content[0].text  # type: ignore[attr-defined]

    rows: List[Dict[str, Any]] = []
    for q in test_questions:
        chunks = await retrieve(q["question"], session, top_k=5)
        contexts = [c["content"] for c in chunks]
        answer = await _get_answer(q["question"], chunks)
        rows.append(
            {
                "question": q["question"],
                "answer": answer,
                "contexts": contexts,
                "ground_truth": q["ground_truth"],
            }
        )

    dataset = Dataset.from_list(rows)
    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
    )
    return result.to_pandas()


# ==========================================================================
# 13. SQL SCHEMA  (reference — run once against your PostgreSQL + pgvector)
# ==========================================================================

SQL_SCHEMA = """
-- ── Prerequisites ──────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS vector;

-- ── documents ──────────────────────────────────────────────────────────────
CREATE TABLE documents (
    id          UUID PRIMARY KEY,
    filename    TEXT NOT NULL,
    source      TEXT,                                  -- 'upload' | url | path
    uploaded_by INT,                                   -- FK → users.id
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    metadata    JSONB DEFAULT '{}'::jsonb
);

-- ── chunks (with pgvector embedding column) ────────────────────────────────
CREATE TABLE chunks (
    id           UUID PRIMARY KEY,
    document_id  UUID REFERENCES documents(id) ON DELETE CASCADE,
    content      TEXT NOT NULL,
    chunk_index  INT  NOT NULL,
    embedding    vector(1536),                         -- text-embedding-3-small
    metadata     JSONB DEFAULT '{}'::jsonb,
    token_count  INT,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- HNSW index for fast approximate nearest-neighbour search.
-- Recommended over IVFFlat for <10 M rows (better recall at same speed).
-- Build CONCURRENTLY in production to avoid blocking reads.
CREATE INDEX CONCURRENTLY chunks_embedding_hnsw_idx
    ON chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Full-text search index for BM25/keyword side of hybrid retrieval.
CREATE INDEX chunks_content_fts_idx
    ON chunks
    USING gin (to_tsvector('english', content));

-- GIN index on metadata JSONB for fast filtered vector searches.
CREATE INDEX chunks_metadata_idx ON chunks USING gin (metadata);
CREATE INDEX chunks_doc_id_idx   ON chunks (document_id);

-- ── rag_cache (semantic caching layer) ────────────────────────────────────
CREATE TABLE rag_cache (
    id              UUID PRIMARY KEY,
    query           TEXT,
    query_embedding vector(1536),
    answer          TEXT,
    citations       JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX rag_cache_emb_hnsw_idx
    ON rag_cache
    USING hnsw (query_embedding vector_cosine_ops);

-- ── Tuning knobs (set per session or in postgresql.conf) ──────────────────
-- SET hnsw.ef_search = 100;   -- higher = better recall, slower query
-- HNSW m / ef_construction trade-off:
--   m = 16 (default) → 16 neighbours per layer; raise to 32 for >1 M rows
--   ef_construction = 64 → index build accuracy; raise to 128 for production
"""


# ==========================================================================
# 14. PRODUCTION NOTES  (as constants — grep-able reference)
# ==========================================================================

CHUNKING_BEST_PRACTICES = """
CHUNKING BEST PRACTICES
───────────────────────
- Target 300-800 tokens per chunk (too small → no context; too big → diluted signal).
- Use 10-20 % overlap (chunk_size * 0.1 – 0.2) to avoid losing info at boundaries.
- Prefer paragraph-boundary chunking for prose; token-window for code/tables.
- Always use the SAME embedding model at ingest time and query time.
- Re-embed and update chunk rows whenever source documents are edited; track
  an 'embedding_version' column to identify stale rows.
"""

COST_OPTIMISATION = """
COST OPTIMISATION STRATEGIES
─────────────────────────────
Strategy                              Estimated Saving
─────────────────────────────────────────────────────
text-embedding-3-small (1536 dims)    50 % vs 3072-dim variant
Batch embeddings (100/call)           Up to 50 % via reduced per-call overhead
Semantic cache (24 h TTL)             30–70 % LLM cost on repeat queries
Cohere Rerank + cheap LLM (Haiku)     Better context → higher accuracy at lower cost
Anthropic prompt caching              Up to 90 % on repeated system + large context
Truncate context to top-5 chunks      Direct input-token reduction
BUILD INDEX CONCURRENTLY              Zero downtime during index creation
"""

PRODUCTION_GOTCHAS = """
PRODUCTION GOTCHAS
──────────────────
Gotcha                    Fix
────────────────────────────────────────────────────────────────────────────
Chunks too small          Lose context — target 300-800 tokens
Chunks too big            Dilutes retrieval signal; hits LLM context limits
Missing overlap           Boundary sentences split across chunks — use 10-20%
Wrong embedding model     Ingest/query mismatch → meaningless cosine scores
No reranking              Vector top-10 ≠ most relevant top-5
Metadata not GIN-indexed  Slow metadata filter scans
HNSW build blocks reads   CREATE INDEX CONCURRENTLY in production
Stale embeddings          Track version column; re-embed on doc update
No citations              Users cannot verify; hallucination feels real
No semantic cache         Pay full LLM cost on every duplicate question
No prompt injection guard Sanitize retrieved content (see doc 33)
"""


# ==========================================================================
# DEMO ENTRY POINT  (no external infra required — illustrates the flow)
# ==========================================================================

if __name__ == "__main__":
    import textwrap

    banner = "=" * 70

    print(banner)
    print("  RAG Backend Architecture — module overview")
    print(banner)

    # ── Show chunking behaviour locally (no API key needed) ──────────────
    sample_text = textwrap.dedent(
        """\
        Retrieval-Augmented Generation (RAG) grounds LLM answers in external
        knowledge retrieved at query time, reducing hallucinations and keeping
        responses up-to-date without retraining.

        The ingestion pipeline converts raw documents into overlapping text
        chunks, computes dense vector embeddings, and stores them in a vector
        database such as pgvector for fast approximate nearest-neighbour search.

        At query time the system embeds the user question, retrieves the top-K
        most similar chunks via hybrid search (vector + BM25), reranks them
        with a cross-encoder, and feeds the final context to the LLM.

        Semantic caching further reduces cost by serving cached answers for
        near-duplicate queries within a configurable time-to-live window.
        """
    )

    print("\n[1] Token-window chunks (size=100, overlap=15):")
    token_chunks = chunk_by_tokens(sample_text, chunk_size=100, overlap=15)
    for i, ch in enumerate(token_chunks):
        tok = count_tokens(ch)
        print(f"  Chunk {i}: {tok} tokens — {ch[:80].replace(chr(10),' ')}…")

    print("\n[2] Paragraph-boundary chunks (max_tokens=120):")
    para_chunks = chunk_by_paragraphs(sample_text, max_tokens=120)
    for i, ch in enumerate(para_chunks):
        tok = count_tokens(ch)
        print(f"  Chunk {i}: {tok} tokens — {ch[:80].replace(chr(10),' ')}…")

    print("\n[3] SQL schema excerpt:")
    for line in SQL_SCHEMA.strip().splitlines()[:15]:
        print(" ", line)
    print("  ... (see SQL_SCHEMA constant for full DDL)")

    print("\n[4] Key production notes:")
    print(COST_OPTIMISATION.strip())

    print(banner)
    print("  Start the API:  uvicorn 34_rag_backend_architecture:app --reload")
    print("  Endpoints:      POST /documents/upload   POST /rag/query")
    print(banner)
