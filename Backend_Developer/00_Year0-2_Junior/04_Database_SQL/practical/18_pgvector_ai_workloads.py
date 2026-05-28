"""
============================================================
PGVECTOR — Practical
============================================================
Setup:
    docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=password \\
        pgvector/pgvector:pg16

    pip install pgvector psycopg openai sentence-transformers numpy
"""


# ============================================================
# 1. SETUP
# ============================================================
SETUP_SQL = """
-- Enable extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Check installed
SELECT extversion FROM pg_extension WHERE extname = 'vector';

-- Schema for RAG
CREATE TABLE documents (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE doc_chunks (
    id BIGSERIAL PRIMARY KEY,
    doc_id BIGINT REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR(1536),    -- OpenAI text-embedding-3-small
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_chunks_doc_id ON doc_chunks(doc_id);

-- HNSW index for vector search (recommended)
CREATE INDEX idx_chunks_embedding ON doc_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Alternative: IVFFlat (lower memory, slower query)
-- CREATE INDEX idx_chunks_embedding ON doc_chunks
--     USING ivfflat (embedding vector_cosine_ops)
--     WITH (lists = 100);
"""


# ============================================================
# 2. INGESTION PIPELINE
# ============================================================
INGESTION_PIPELINE = '''
# Full RAG ingestion: chunk → embed → store

import psycopg
from pgvector.psycopg import register_vector
from openai import OpenAI

client = OpenAI()


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Simple sliding window chunking."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        # Try to break at sentence boundary
        if end < len(text):
            last_period = text.rfind(". ", start, end)
            if last_period > start:
                end = last_period + 1
        chunks.append(text[start:end].strip())
        start = end - overlap
    return [c for c in chunks if c]


def get_embedding(text: str) -> list[float]:
    """OpenAI embedding."""
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )
    return response.data[0].embedding


def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Batch embeddings (faster + cheaper)."""
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=texts,
    )
    return [d.embedding for d in response.data]


def ingest_document(conn, title: str, content: str, metadata: dict = None):
    """Full ingestion pipeline."""
    register_vector(conn)
    with conn.cursor() as cur:
        # 1. Insert document
        cur.execute(
            "INSERT INTO documents (title, metadata) VALUES (%s, %s) RETURNING id",
            (title, metadata or {}),
        )
        doc_id = cur.fetchone()[0]

        # 2. Chunk
        chunks = chunk_text(content)

        # 3. Embed in batch
        embeddings = get_embeddings_batch(chunks)

        # 4. Insert chunks
        values = [
            (doc_id, i, chunk, embedding)
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings))
        ]
        cur.executemany(
            """INSERT INTO doc_chunks (doc_id, chunk_index, content, embedding)
               VALUES (%s, %s, %s, %s)""",
            values,
        )
    conn.commit()
    return doc_id


# Usage
conn = psycopg.connect("postgresql://localhost/mydb")
ingest_document(
    conn,
    title="Python Programming Guide",
    content="Python is a high-level programming language..."  * 100,
    metadata={"category": "tech", "language": "english"},
)
'''


# ============================================================
# 3. SEMANTIC SEARCH
# ============================================================
SEMANTIC_SEARCH = '''
def semantic_search(conn, query: str, top_k: int = 5, filters: dict = None):
    """Vector search with optional filters."""
    query_emb = get_embedding(query)

    sql = """
        SELECT
            c.id,
            c.content,
            d.title,
            d.metadata,
            c.embedding <=> %s::vector AS distance
        FROM doc_chunks c
        JOIN documents d ON c.doc_id = d.id
        WHERE 1=1
    """
    params = [query_emb]

    if filters:
        if "category" in filters:
            sql += " AND d.metadata->>'category' = %s"
            params.append(filters["category"])
        if "after_date" in filters:
            sql += " AND d.created_at > %s"
            params.append(filters["after_date"])

    sql += " ORDER BY c.embedding <=> %s::vector LIMIT %s"
    params.extend([query_emb, top_k])

    with conn.cursor() as cur:
        cur.execute(sql, params)
        return [
            {
                "id": row[0],
                "content": row[1],
                "title": row[2],
                "metadata": row[3],
                "distance": float(row[4]),
            }
            for row in cur
        ]


# Usage
results = semantic_search(
    conn,
    query="How does Python handle memory?",
    top_k=5,
    filters={"category": "tech"},
)

for r in results:
    print(f"[{r['distance']:.3f}] {r['title']}")
    print(f"  {r['content'][:100]}...")
'''


# ============================================================
# 4. HYBRID SEARCH (vector + full-text)
# ============================================================
HYBRID_SEARCH = """
-- ===== SETUP — add search_vector column =====
ALTER TABLE doc_chunks ADD COLUMN search_vector TSVECTOR
    GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;

CREATE INDEX idx_chunks_fts ON doc_chunks USING GIN (search_vector);

-- ===== RECIPROCAL RANK FUSION (RRF) =====
-- Combines vector + keyword search optimally

WITH semantic AS (
    SELECT id, ROW_NUMBER() OVER (ORDER BY embedding <=> :query_emb::vector) AS rank
    FROM doc_chunks
    ORDER BY embedding <=> :query_emb::vector
    LIMIT 50
),
keyword AS (
    SELECT id, ROW_NUMBER() OVER (ORDER BY ts_rank(search_vector, q) DESC) AS rank
    FROM doc_chunks, plainto_tsquery('english', :query_text) q
    WHERE search_vector @@ q
    LIMIT 50
)
SELECT
    COALESCE(s.id, k.id) AS id,
    -- RRF formula: 1 / (k + rank) where k = constant (typically 60)
    COALESCE(1.0 / (60 + s.rank), 0) +
    COALESCE(1.0 / (60 + k.rank), 0) AS rrf_score
FROM semantic s
FULL OUTER JOIN keyword k ON s.id = k.id
ORDER BY rrf_score DESC
LIMIT 10;

-- ===== WEIGHTED HYBRID =====
WITH semantic AS (
    SELECT id, 1 - (embedding <=> :emb::vector) AS sem_score
    FROM doc_chunks
    ORDER BY embedding <=> :emb::vector
    LIMIT 100
),
keyword AS (
    SELECT id, ts_rank(search_vector, q) AS kw_score
    FROM doc_chunks, plainto_tsquery('english', :q) q
    WHERE search_vector @@ q
)
SELECT
    COALESCE(s.id, k.id) AS id,
    (0.7 * COALESCE(s.sem_score, 0)) +    -- 70% semantic
    (0.3 * COALESCE(k.kw_score, 0))       -- 30% keyword
    AS final_score
FROM semantic s
FULL OUTER JOIN keyword k ON s.id = k.id
ORDER BY final_score DESC
LIMIT 10;
"""


# ============================================================
# 5. SQLALCHEMY INTEGRATION
# ============================================================
SQLALCHEMY_INTEGRATION = '''
from sqlalchemy import Column, BigInteger, String, Text, ForeignKey, Integer, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector

Base = declarative_base()


class Document(Base):
    __tablename__ = "documents"
    id = Column(BigInteger, primary_key=True)
    title = Column(String, nullable=False)
    metadata = Column(JSONB, default=dict)


class DocChunk(Base):
    __tablename__ = "doc_chunks"
    id = Column(BigInteger, primary_key=True)
    doc_id = Column(BigInteger, ForeignKey("documents.id"))
    chunk_index = Column(Integer)
    content = Column(Text)
    embedding = Column(Vector(1536))


# ===== INSERT =====
def add_chunk(session, doc_id: int, index: int, content: str):
    embedding = get_embedding(content)
    chunk = DocChunk(
        doc_id=doc_id,
        chunk_index=index,
        content=content,
        embedding=embedding,
    )
    session.add(chunk)
    session.commit()


# ===== COSINE SEARCH =====
def search(session, query: str, top_k: int = 5):
    query_emb = get_embedding(query)
    return (
        session.query(
            DocChunk,
            DocChunk.embedding.cosine_distance(query_emb).label("distance"),
        )
        .order_by(DocChunk.embedding.cosine_distance(query_emb))
        .limit(top_k)
        .all()
    )


# ===== L2 SEARCH =====
def search_l2(session, query_emb, top_k=5):
    return session.query(DocChunk).order_by(
        DocChunk.embedding.l2_distance(query_emb)
    ).limit(top_k).all()


# ===== INNER PRODUCT SEARCH =====
def search_ip(session, query_emb, top_k=5):
    return session.query(DocChunk).order_by(
        DocChunk.embedding.max_inner_product(query_emb)
    ).limit(top_k).all()


# ===== WITH FILTERS =====
def filtered_search(session, query: str, category: str, top_k=5):
    query_emb = get_embedding(query)
    return (
        session.query(DocChunk, Document)
        .join(Document, Document.id == DocChunk.doc_id)
        .filter(Document.metadata["category"].astext == category)
        .order_by(DocChunk.embedding.cosine_distance(query_emb))
        .limit(top_k)
        .all()
    )
'''


# ============================================================
# 6. FASTAPI RAG ENDPOINT
# ============================================================
FASTAPI_RAG = '''
from fastapi import FastAPI, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

app = FastAPI()


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    category: str | None = None


class RAGResponse(BaseModel):
    answer: str
    sources: list[dict]


@app.post("/search")
async def semantic_search_endpoint(
    req: SearchRequest,
    db: AsyncSession = Depends(get_db),
):
    """Semantic search with optional filters."""
    query_embedding = await get_embedding_async(req.query)

    sql = """
        SELECT
            c.id, c.content, d.title, d.metadata,
            c.embedding <=> :emb::vector AS distance
        FROM doc_chunks c
        JOIN documents d ON c.doc_id = d.id
    """
    params = {"emb": query_embedding, "k": req.top_k}

    if req.category:
        sql += " WHERE d.metadata->>'category' = :cat"
        params["cat"] = req.category

    sql += " ORDER BY c.embedding <=> :emb::vector LIMIT :k"

    result = await db.execute(text(sql), params)
    return [dict(r._mapping) for r in result]


@app.post("/rag", response_model=RAGResponse)
async def rag_endpoint(
    req: SearchRequest,
    db: AsyncSession = Depends(get_db),
):
    """Full RAG: retrieve + generate."""
    # 1. Retrieve relevant chunks
    chunks = await semantic_search_endpoint(req, db)

    # 2. Build context
    context = "\\n\\n---\\n\\n".join([c["content"] for c in chunks])

    # 3. Call LLM with context
    answer = await openai_chat(
        messages=[
            {"role": "system",
             "content": "Answer based ONLY on the provided context. Say 'I don't know' if not in context."},
            {"role": "user",
             "content": f"Context:\\n{context}\\n\\nQuestion: {req.query}"},
        ]
    )

    return RAGResponse(
        answer=answer,
        sources=[
            {"id": c["id"], "title": c["title"], "distance": c["distance"]}
            for c in chunks
        ],
    )


@app.post("/documents")
async def upload_document(
    title: str,
    content: str,
    metadata: dict = {},
    db: AsyncSession = Depends(get_db),
):
    """Upload + chunk + embed + store."""
    # 1. Insert doc
    result = await db.execute(text(
        "INSERT INTO documents (title, metadata) VALUES (:t, :m) RETURNING id"
    ), {"t": title, "m": metadata})
    doc_id = result.scalar()

    # 2. Chunk
    chunks = chunk_text(content)

    # 3. Batch embed
    embeddings = await get_embeddings_batch_async(chunks)

    # 4. Insert chunks
    for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
        await db.execute(text("""
            INSERT INTO doc_chunks (doc_id, chunk_index, content, embedding)
            VALUES (:d, :i, :c, :e::vector)
        """), {"d": doc_id, "i": i, "c": chunk, "e": emb})

    await db.commit()
    return {"doc_id": doc_id, "chunks": len(chunks)}
'''


# ============================================================
# 7. INDEX TUNING
# ============================================================
INDEX_TUNING = """
-- ===== HNSW PARAMETERS =====
CREATE INDEX ON doc_chunks USING hnsw (embedding vector_cosine_ops)
WITH (
    m = 16,                  -- connections per node (default 16)
    ef_construction = 64     -- build-time search width (default 64)
);

-- Query-time accuracy
SET hnsw.ef_search = 100;    -- higher = better recall, slower

-- Tuning guide:
-- m=8,  ef_construction=32:  fast build, smaller index, lower recall
-- m=16, ef_construction=64:  balanced (default)
-- m=32, ef_construction=128: best recall, slower build, larger index

-- ===== IVFFLAT PARAMETERS =====
CREATE INDEX ON doc_chunks USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);    -- ~sqrt(rows)

SET ivfflat.probes = 10;   -- higher = better recall, slower

-- Tuning:
-- 1K rows:   lists = 1
-- 10K rows:  lists = 100
-- 100K rows: lists = 316
-- 1M rows:   lists = 1000

-- Probes typically: sqrt(lists)

-- ===== PARTIAL INDEX =====
-- When filter is selective
CREATE INDEX idx_recent_chunks ON doc_chunks USING hnsw (embedding vector_cosine_ops)
WHERE created_at > NOW() - INTERVAL '90 days';

-- ===== INDEX BUILD SPEED =====
SET maintenance_work_mem = '4GB';   -- increase for faster builds
SET max_parallel_maintenance_workers = 4;
"""


# ============================================================
# 8. MONITORING & OPTIMIZATION
# ============================================================
MONITORING = """
-- Index size
SELECT
    indexname,
    pg_size_pretty(pg_relation_size(indexrelid)) AS size
FROM pg_stat_user_indexes
WHERE tablename = 'doc_chunks';

-- Query latency (with auto_explain enabled)
SHOW auto_explain.log_min_duration;

-- Test query
EXPLAIN ANALYZE
SELECT id, embedding <=> '[0.1, 0.2, ...]'::vector AS distance
FROM doc_chunks
ORDER BY embedding <=> '[0.1, 0.2, ...]'::vector
LIMIT 10;

-- Expected:
-- Limit  (cost=...)
--   ->  Index Scan using idx_chunks_embedding (cost=...)
-- HNSW should appear in plan

-- ===== TUNE recall vs speed =====
-- Run test queries with known ground truth, measure recall

WITH ground_truth AS (
    SELECT id FROM doc_chunks
    ORDER BY embedding <=> 'expected_emb'::vector
    LIMIT 100
),
results AS (
    SELECT id FROM doc_chunks
    ORDER BY embedding <=> 'expected_emb'::vector
    LIMIT 100   -- with HNSW index
)
SELECT
    COUNT(DISTINCT r.id) AS recall_at_100,
    COUNT(DISTINCT g.id) AS ground_truth_count,
    ROUND(COUNT(DISTINCT r.id)::numeric / COUNT(DISTINCT g.id) * 100, 2) AS recall_pct
FROM ground_truth g LEFT JOIN results r USING (id);
"""


# ============================================================
# 9. ALTERNATIVE: USE SENTENCE-TRANSFORMERS (local, free)
# ============================================================
LOCAL_EMBEDDINGS = '''
# pip install sentence-transformers

from sentence_transformers import SentenceTransformer

# Small + fast model (384 dim)
model = SentenceTransformer("all-MiniLM-L6-v2")

# Or larger model (768 dim)
# model = SentenceTransformer("all-mpnet-base-v2")

# Generate embedding
embedding = model.encode("Python is a programming language").tolist()
# Returns list of 384 floats (for MiniLM-L6-v2)

# Schema update — match dimension
# embedding VECTOR(384)   not VECTOR(1536)


# Batch embeddings (much faster)
sentences = ["text 1", "text 2", "text 3"]
embeddings = model.encode(sentences, batch_size=32).tolist()
# Returns list[list[float]]


# Multilingual
# model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

# Comparison: OpenAI vs local
# OpenAI 1536-dim: best quality, $$/per request, network
# MiniLM 384-dim:  good quality, free, fast, local
# Cohere 1024-dim: good quality, $/per request
# Instructor 768-dim: tunable per task, free, local
'''


# ============================================================
# 10. SCALE LIMITS
# ============================================================
SCALE_GUIDE = """
================================================================
PGVECTOR SCALE GUIDE
================================================================

VECTOR COUNT       | RECOMMENDED SETUP
-------------------|---------------------------------------------
< 100K             | Default config, HNSW, ~10ms queries
100K - 1M          | HNSW m=16, ef_construction=64, ~20ms
1M - 10M           | HNSW + partial indexes, tune maintenance_work_mem
10M - 100M         | Sharded pgvector or dedicated DB
> 100M             | Consider Pinecone, Weaviate, Milvus, Qdrant

================================================================
HARDWARE
================================================================
- Memory: vector index fits in RAM ideally
  1M vectors × 1536 dim × 4 bytes = ~6GB
  10M = ~60GB

- CPU: vector ops are CPU-bound
  Use SIMD-capable CPUs (modern Intel/AMD/ARM)

- Disk: SSD for fast index loading
================================================================
"""


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("PGVECTOR — Practical")
    print("=" * 60)

    print("\n--- SETUP ---")
    print(SETUP_SQL)
    print("\n--- INGESTION PIPELINE ---")
    print(INGESTION_PIPELINE)
    print("\n--- SEMANTIC SEARCH ---")
    print(SEMANTIC_SEARCH)
    print("\n--- HYBRID SEARCH ---")
    print(HYBRID_SEARCH)
    print("\n--- SQLALCHEMY ---")
    print(SQLALCHEMY_INTEGRATION)
    print("\n--- FASTAPI RAG ---")
    print(FASTAPI_RAG)
    print("\n--- INDEX TUNING ---")
    print(INDEX_TUNING)
    print("\n--- MONITORING ---")
    print(MONITORING)
    print("\n--- LOCAL EMBEDDINGS ---")
    print(LOCAL_EMBEDDINGS)
    print(SCALE_GUIDE)
