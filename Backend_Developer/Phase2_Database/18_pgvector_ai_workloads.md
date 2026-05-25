# pgvector — Vector Search in PostgreSQL

> **Interview angle:** "Pinecone $$$$. Can Postgres do RAG/semantic search? Yes — pgvector."

---

## 1. What is pgvector?

PostgreSQL extension for **vector similarity search**:
- Store embeddings (1536-dim vectors from OpenAI, etc.)
- Index with HNSW or IVFFlat
- Query by similarity (cosine, L2, inner product)
- Combine with SQL filters, joins

**Used by:** Supabase, Neon, AWS Aurora — replaces Pinecone/Weaviate for many use cases.

---

## 2. Why pgvector vs Pinecone?

| Aspect | pgvector | Pinecone |
|---|---|---|
| Cost | Free with Postgres | $70+/mo minimum |
| Setup | `CREATE EXTENSION` | Separate service |
| Joins with relational data | ✅ Native SQL | ❌ |
| Filtering | ✅ Standard WHERE | Limited |
| ACID | ✅ | Eventual |
| Scale | 10-100M vectors | 1B+ |
| Latency | 1-50ms | 5-50ms |

**Choose pgvector:**
- Already on Postgres
- < 100M vectors
- Need SQL joins (most RAG apps)

**Choose Pinecone/Weaviate:**
- > 1B vectors
- Want zero ops
- Specialized features (hybrid, sparse)

---

## 3. Setup

```bash
# Docker
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=password \
    pgvector/pgvector:pg16

# Or manually install
# https://github.com/pgvector/pgvector
```

```sql
CREATE EXTENSION vector;
SELECT extversion FROM pg_extension WHERE extname = 'vector';
```

---

## 4. Schema

```sql
CREATE TABLE documents (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT,
    metadata JSONB DEFAULT '{}',
    -- Vector column with dimension (must specify!)
    embedding VECTOR(1536),    -- OpenAI ada-002 dim
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Other common dims:
-- 384  — all-MiniLM-L6-v2 (small/fast)
-- 768  — BERT-base
-- 1024 — Cohere
-- 1536 — OpenAI ada-002, text-embedding-3-small
-- 3072 — text-embedding-3-large
```

---

## 5. Distance Operators

```sql
-- L2 distance (Euclidean)
embedding <-> '[1, 2, 3]'::vector

-- Inner product (dot product, negated)
embedding <#> '[1, 2, 3]'::vector

-- Cosine distance (1 - cosine similarity)
embedding <=> '[1, 2, 3]'::vector
```

**Choose:**
- **Cosine** — text embeddings (most common)
- **L2** — normalized vectors
- **Inner product** — when vectors normalized; fastest

---

## 6. Basic Search

```sql
-- Find 5 most similar documents
SELECT id, title, embedding <=> '[0.1, 0.2, ...]'::vector AS distance
FROM documents
ORDER BY embedding <=> '[0.1, 0.2, ...]'::vector
LIMIT 5;

-- Within similarity threshold (cosine distance < 0.3)
SELECT id, title
FROM documents
WHERE embedding <=> query_embedding < 0.3
ORDER BY embedding <=> query_embedding
LIMIT 10;
```

---

## 7. Indexes — HNSW vs IVFFlat

### HNSW (Hierarchical Navigable Small World) — RECOMMENDED
- Faster queries
- Better recall
- More memory
- Slower build

```sql
-- Cosine distance (most common for text)
CREATE INDEX ON documents
    USING hnsw (embedding vector_cosine_ops);

-- L2
CREATE INDEX ON documents
    USING hnsw (embedding vector_l2_ops);

-- Inner product
CREATE INDEX ON documents
    USING hnsw (embedding vector_ip_ops);

-- Tunable parameters
CREATE INDEX ON documents
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- m: connections per node (default 16)
-- ef_construction: build-time accuracy (default 64)
```

### IVFFlat (Inverted File Flat)
- Faster build
- Less memory
- Lower recall
- Need to set lists parameter

```sql
CREATE INDEX ON documents
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
-- Rule: lists = sqrt(rows). 1M rows → lists ≈ 1000

-- Query needs probes setting
SET ivfflat.probes = 10;   -- higher = more accurate, slower
```

### Recommendation
**HNSW** for most use cases (better quality). IVFFlat only if disk-space-limited.

---

## 8. Combining Filters

```sql
-- Vector + metadata filter
SELECT id, title
FROM documents
WHERE
    metadata->>'category' = 'tech'      -- SQL filter
    AND created_at > NOW() - INTERVAL '30 days'
    AND embedding <=> query_embedding < 0.3
ORDER BY embedding <=> query_embedding
LIMIT 10;
```

**Important:** Vector index used only when ORDER BY is on vector distance.

### Hybrid: BM25 + vector
```sql
-- Combine full-text + semantic search
WITH semantic AS (
    SELECT id, embedding <=> query AS score
    FROM documents
    ORDER BY score
    LIMIT 50
),
keyword AS (
    SELECT id, ts_rank(search_vector, ts_query) AS score
    FROM documents
    WHERE search_vector @@ ts_query
)
SELECT
    COALESCE(s.id, k.id) AS id,
    -- Reciprocal Rank Fusion
    COALESCE(1.0 / (60 + s.row_num), 0) + COALESCE(1.0 / (60 + k.row_num), 0) AS rrf_score
FROM semantic s FULL JOIN keyword k USING (id)
ORDER BY rrf_score DESC
LIMIT 10;
```

---

## 9. Real-World: RAG (Retrieval-Augmented Generation)

```sql
-- Chunks table
CREATE TABLE doc_chunks (
    id BIGSERIAL PRIMARY KEY,
    doc_id BIGINT REFERENCES documents(id),
    chunk_index INT,
    content TEXT NOT NULL,
    embedding VECTOR(1536),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX ON doc_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ON doc_chunks (doc_id);

-- RAG search
SELECT
    c.content,
    d.title,
    c.embedding <=> :query AS distance
FROM doc_chunks c
JOIN documents d ON c.doc_id = d.id
WHERE
    -- Optional filters
    d.metadata->>'company' = 'acme'
    AND d.created_at > NOW() - INTERVAL '90 days'
ORDER BY c.embedding <=> :query
LIMIT 5;

-- Pass these 5 chunks to LLM as context
```

---

## 10. Python: Generate + Store Embeddings

```bash
pip install psycopg pgvector openai numpy
```

```python
from openai import OpenAI
from pgvector.psycopg import register_vector
import psycopg

client = OpenAI()

def get_embedding(text: str) -> list[float]:
    """OpenAI text-embedding-3-small (1536-dim)."""
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )
    return response.data[0].embedding


# Setup
conn = psycopg.connect("postgresql://localhost/mydb")
register_vector(conn)   # important: registers vector type

# Insert
with conn.cursor() as cur:
    embedding = get_embedding("Python is a programming language")
    cur.execute(
        "INSERT INTO documents (title, content, embedding) VALUES (%s, %s, %s)",
        ("About Python", "Python is...", embedding),
    )
conn.commit()


# Search
query_emb = get_embedding("What is Python?")

with conn.cursor() as cur:
    cur.execute("""
        SELECT id, title, embedding <=> %s::vector AS distance
        FROM documents
        ORDER BY embedding <=> %s::vector
        LIMIT 5
    """, (query_emb, query_emb))
    for row in cur:
        print(f"{row[0]}: {row[1]} (distance: {row[2]:.4f})")
```

---

## 11. SQLAlchemy Integration

```python
from sqlalchemy import Column, BigInteger, String, Text
from sqlalchemy.ext.declarative import declarative_base
from pgvector.sqlalchemy import Vector

Base = declarative_base()


class Document(Base):
    __tablename__ = "documents"
    id = Column(BigInteger, primary_key=True)
    title = Column(String, nullable=False)
    content = Column(Text)
    embedding = Column(Vector(1536))


# Insert
doc = Document(
    title="Python Intro",
    content="Python is a programming language",
    embedding=get_embedding("Python is a programming language"),
)
session.add(doc)
session.commit()


# Search — cosine distance
from sqlalchemy import func

query = get_embedding("What is Python?")

results = (
    session.query(Document)
    .order_by(Document.embedding.cosine_distance(query))
    .limit(5)
    .all()
)

# With distance score
results = session.query(
    Document,
    Document.embedding.cosine_distance(query).label("distance"),
).order_by("distance").limit(5).all()

for doc, dist in results:
    print(f"{doc.title}: {dist:.4f}")


# Filtered search
results = (
    session.query(Document)
    .filter(Document.metadata["category"].astext == "tech")
    .order_by(Document.embedding.cosine_distance(query))
    .limit(10)
    .all()
)
```

---

## 12. FastAPI RAG Endpoint

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    filters: dict = {}


@app.post("/search")
async def semantic_search(req: SearchRequest):
    # 1. Embed query
    query_embedding = await get_embedding_async(req.query)

    # 2. Vector search with filters
    sql = """
        SELECT id, title, content,
               embedding <=> :emb::vector AS distance
        FROM documents
        WHERE 1=1
    """
    params = {"emb": query_embedding}

    if req.filters.get("category"):
        sql += " AND metadata->>'category' = :cat"
        params["cat"] = req.filters["category"]

    sql += " ORDER BY embedding <=> :emb::vector LIMIT :k"
    params["k"] = req.top_k

    result = await db.execute(text(sql), params)
    return [dict(r._mapping) for r in result]


@app.post("/rag")
async def rag_endpoint(req: SearchRequest):
    # 1. Vector search (retrieval)
    chunks = await semantic_search(req)

    # 2. Build context
    context = "\\n\\n".join([c["content"] for c in chunks])

    # 3. LLM (generation)
    answer = await openai_chat(
        f"Context:\\n{context}\\n\\nQuestion: {req.query}\\nAnswer:"
    )

    return {
        "answer": answer,
        "sources": [c["id"] for c in chunks],
    }
```

---

## 13. Chunking Strategy

For RAG, split documents into chunks before embedding:

```python
def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Simple character-based chunking."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


# Better: sentence-based chunking
from langchain.text_splitter import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
    separators=["\\n\\n", "\\n", ". ", " "],
)
chunks = splitter.split_text(text)


# Even better: semantic chunking
from langchain_experimental.text_splitter import SemanticChunker
splitter = SemanticChunker(embeddings_model)
```

---

## 14. Performance Tuning

### Index parameters
```sql
-- HNSW build-time
CREATE INDEX ON documents USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
-- m=16: better recall, more memory
-- ef_construction=64: build accuracy

-- HNSW query-time
SET hnsw.ef_search = 100;   -- higher = more accurate, slower
```

### IVFFlat
```sql
-- Lists count = sqrt(row_count)
CREATE INDEX ON documents USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 1000);

-- Probe count = sqrt(lists)
SET ivfflat.probes = 32;
```

### Memory
```sql
-- Increase maintenance_work_mem for index builds
SET maintenance_work_mem = '2GB';
```

### Pre-filter optimization
HNSW + filter can be slow if filter selective.
```sql
-- ❌ Slow if filter removes 99% of rows
WHERE category = 'rare' ORDER BY emb <=> q LIMIT 10

-- ✅ Use partial index
CREATE INDEX ON docs USING hnsw (embedding vector_cosine_ops)
WHERE category = 'tech';
```

---

## 15. Common Pitfalls

### Pitfall 1: Wrong dimension
```sql
embedding VECTOR(1536)
-- Insert 384-dim vector → error

-- Use correct dim for your model:
-- OpenAI text-embedding-3-small: 1536
-- all-MiniLM-L6-v2: 384
-- text-embedding-3-large: 3072
```

### Pitfall 2: No index → slow
```sql
-- 1M rows without index = 5+ second query
-- With HNSW = 5-20ms
```

### Pitfall 3: Wrong distance operator
```sql
-- Text embeddings (OpenAI): use cosine <=>
-- Normalized vectors with inner product: <#>
```

### Pitfall 4: Updating vectors invalidates index
HNSW degrades over time with many updates. Periodic REINDEX needed.

### Pitfall 5: Storing full text instead of chunks
Document → 1 embedding for 100K chars = poor search quality.
Chunk first, embed each chunk.

---

## 16. Operations

```sql
-- Index size
SELECT pg_size_pretty(pg_relation_size('documents_embedding_idx'));

-- Rebuild index if degraded
REINDEX INDEX CONCURRENTLY documents_embedding_idx;

-- Vacuum after bulk updates
VACUUM ANALYZE documents;
```

---

## 17. Interview Questions

**Q1: pgvector vs Pinecone?**
pgvector: Postgres extension, SQL joins, ACID, cheaper, smaller scale. Pinecone: managed, billions scale, vendor lock-in.

**Q2: HNSW vs IVFFlat?**
HNSW = faster query, better recall, more memory. IVFFlat = lighter, lower recall. Choose HNSW.

**Q3: Distance operators?**
`<->` L2, `<#>` inner product (negated), `<=>` cosine distance. Cosine for text embeddings.

**Q4: Dimension matters?**
Yes — must match model exactly (1536 for OpenAI ada-002).

**Q5: Pre-filter problem?**
WHERE clause + vector ORDER BY: index used only if pre-filter selective. Partial indexes help.

**Q6: RAG flow?**
1. Chunk docs
2. Embed each chunk
3. Store in pgvector
4. Query: embed question → search → return top-K
5. Pass to LLM as context

**Q7: Scale limit?**
~10-100M vectors per Postgres. Beyond: Pinecone/Weaviate or sharded pgvector.

---

## 18. Best Practices

1. **HNSW index always** (better quality)
2. **Cosine distance** for text embeddings
3. **Chunk before embed** (500-1000 chars typical)
4. **Match dimension exactly** to model
5. **Pre-compute embeddings** at write time (not query)
6. **Combine with SQL filters** for hybrid search
7. **Partial indexes** when filtering heavily
8. **REINDEX periodically** if many updates
9. **Hybrid search** (vector + BM25) often better
10. **Monitor recall** — sample queries with ground truth

---

## Related
- [[06_pgvector_schema_design]]
- [[15_postgresql_fulltext_search]]
- [[16_jsonb_queries_indexes]]
- [[../../Phase6_Vector_Databases/]]
- [[../../Phase5_RAG/]]
