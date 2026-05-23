# pgvector + Database Schema Design

## Quick Concepts
- **pgvector** = PostgreSQL extension for vector embeddings — AI/RAG ke liye
- **Vector embedding** = text/image → float array (e.g., 1536 dimensions for OpenAI)
- **Cosine similarity** = vectors ka angle — semantic similarity
- **L2 distance** = Euclidean distance — exact match
- **HNSW index** = fast approximate nearest neighbor search
- **IVFFlat index** = inverted file index — faster build, slightly less accurate
- **Normalization** = 1NF-3NF — redundancy remove karo
- **Denormalization** = performance ke liye redundancy add karo (read-heavy)
- **Indexing strategy** = composite, partial, covering indexes

---

## Interview Questions & Answers

### Q1: pgvector kya hai? RAG pipeline mein kaise use karte hain?

**Answer:**
```sql
-- Extension install
CREATE EXTENSION IF NOT EXISTS vector;

-- ─── Column definition ───
ALTER TABLE documents ADD COLUMN embedding vector(1536);
-- 1536 = OpenAI text-embedding-ada-002 dimensions
-- 768  = sentence-transformers, BERT
-- 3072 = OpenAI text-embedding-3-large

-- ─── Index types ───

-- IVFFlat: faster build, slightly less recall
-- lists = sqrt(rows) recommended
CREATE INDEX ON documents USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- HNSW: better recall, slower build, more memory
-- Best for production query performance
CREATE INDEX ON documents USING hnsw (embedding vector_l2_ops)
    WITH (m = 16, ef_construction = 64);

-- ─── Similarity search queries ───

-- Cosine similarity (best for text embeddings)
SELECT id, content, 1 - (embedding <=> '[0.1, 0.2, ...]'::vector) AS similarity
FROM documents
ORDER BY embedding <=> '[0.1, 0.2, ...]'::vector  -- cosine distance
LIMIT 10;

-- L2 distance (Euclidean)
SELECT id, content, embedding <-> '[0.1, 0.2, ...]'::vector AS distance
FROM documents
ORDER BY embedding <-> '[0.1, 0.2, ...]'::vector
LIMIT 10;

-- Inner product (for normalized vectors)
SELECT id, content, (embedding <#> '[0.1, 0.2, ...]'::vector) * -1 AS score
FROM documents
ORDER BY embedding <#> '[0.1, 0.2, ...]'::vector
LIMIT 10;

-- ─── Hybrid search — FTS + vector ───
SELECT
    d.id,
    d.content,
    ts_rank(d.search_vector, to_tsquery('english', 'django orm')) AS text_score,
    1 - (d.embedding <=> :query_embedding) AS vector_score,
    -- Weighted combination
    0.3 * ts_rank(d.search_vector, to_tsquery('english', 'django orm'))
    + 0.7 * (1 - (d.embedding <=> :query_embedding)) AS combined_score
FROM documents d
WHERE
    d.search_vector @@ to_tsquery('english', 'django orm')
    OR (d.embedding <=> :query_embedding) < 0.3  -- similarity threshold
ORDER BY combined_score DESC
LIMIT 20;
```

```python
# ─── Python: Store + Search embeddings ───
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector
import openai

class Document(Base):
    __tablename__ = "documents"
    id        : Mapped[int] = mapped_column(primary_key=True)
    content   : Mapped[str]
    source    : Mapped[str]
    embedding : Mapped[list[float]] = mapped_column(Vector(1536), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

async def embed_and_store(session: AsyncSession, content: str, source: str):
    """Embed text and store in PostgreSQL."""
    response = await openai.AsyncOpenAI().embeddings.create(
        model="text-embedding-ada-002",
        input=content,
    )
    embedding = response.data[0].embedding  # list of 1536 floats

    doc = Document(content=content, source=source, embedding=embedding)
    session.add(doc)
    await session.commit()
    return doc

async def semantic_search(session: AsyncSession, query: str, top_k: int = 5):
    """Find semantically similar documents."""
    # Embed the query
    response = await openai.AsyncOpenAI().embeddings.create(
        model="text-embedding-ada-002",
        input=query,
    )
    query_embedding = response.data[0].embedding

    # Vector similarity search
    from sqlalchemy import text
    result = await session.execute(
        text("""
            SELECT id, content, source,
                   1 - (embedding <=> :embedding::vector) AS similarity
            FROM documents
            WHERE 1 - (embedding <=> :embedding::vector) > 0.7
            ORDER BY embedding <=> :embedding::vector
            LIMIT :top_k
        """),
        {"embedding": str(query_embedding), "top_k": top_k}
    )
    return result.mappings().all()

# ─── INTERVIEW: pgvector vs dedicated vector DB (Pinecone, Qdrant, Weaviate)? ───
# pgvector:
#   + Already have PostgreSQL — no new infra
#   + ACID transactions — embeddings + metadata consistent
#   + SQL joins (filter by metadata)
#   - Slower for very large scale (1B+ vectors)
#   Use: < 10M vectors, need SQL + vector in same query

# Pinecone / Qdrant / Weaviate:
#   + Purpose-built — blazing fast at scale
#   + Advanced filtering
#   - Separate infra, separate data sync
#   Use: 100M+ vectors, pure vector search workload
```

---

### Q2: Database schema design — normalization vs denormalization kab?

**Answer:**
```sql
-- ─── 1NF: Atomic values, no repeating groups ───
-- BAD (violates 1NF):
CREATE TABLE orders (
    id INT,
    items TEXT  -- "apple,banana,cherry" — not atomic!
);

-- GOOD (1NF):
CREATE TABLE order_items (
    order_id INT REFERENCES orders(id),
    product_id INT,
    quantity INT
);

-- ─── 2NF: No partial dependencies (composite PK only) ───
-- BAD: price depends only on product_id, not on (order_id, product_id)
CREATE TABLE order_items (
    order_id INT,
    product_id INT,
    quantity INT,
    product_price DECIMAL,  -- depends on product_id only — partial dependency!
    PRIMARY KEY (order_id, product_id)
);

-- GOOD: price in products table
CREATE TABLE products (id INT PRIMARY KEY, price DECIMAL);
CREATE TABLE order_items (order_id INT, product_id INT REFERENCES products, quantity INT);

-- ─── 3NF: No transitive dependencies ───
-- BAD: city depends on zip_code, not on user_id
CREATE TABLE users (
    id INT PRIMARY KEY,
    zip_code VARCHAR(10),
    city VARCHAR(100),  -- city depends on zip_code, not user — transitive!
    state VARCHAR(50)
);

-- GOOD:
CREATE TABLE zip_codes (zip_code VARCHAR(10) PRIMARY KEY, city VARCHAR(100), state VARCHAR(50));
CREATE TABLE users (id INT PRIMARY KEY, zip_code VARCHAR(10) REFERENCES zip_codes);

-- ─── Denormalization — when performance > purity ───
-- Use when: read-heavy, JOIN cost too high, analytics

-- Example: Post likes_count
-- Normalized: COUNT(*) FROM likes WHERE post_id = X — slow at scale
-- Denormalized: posts.likes_count — fast, but must keep in sync

-- Keeping denormalized data consistent:
-- Option 1: Application code updates counter
-- Option 2: DB trigger
CREATE OR REPLACE FUNCTION update_likes_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE posts SET likes_count = likes_count + 1 WHERE id = NEW.post_id;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE posts SET likes_count = likes_count - 1 WHERE id = OLD.post_id;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER likes_count_trigger
AFTER INSERT OR DELETE ON post_likes
FOR EACH ROW EXECUTE FUNCTION update_likes_count();

-- Option 3: F() expression (SQLAlchemy/Django) — atomic in application
-- Option 4: Periodic recalculation job
```

---

### Q3: Index strategy — composite, partial, covering indexes?

**Answer:**
```sql
-- ─── Composite Index — column ORDER matters ───
-- Rule: equality first, range last, ORDER BY matches index order

-- Query: WHERE status = 'published' AND created_at > '2024-01-01' ORDER BY created_at
CREATE INDEX idx_posts_status_created ON posts (status, created_at DESC);
-- Correct order: equality (status) → range (created_at)

-- ─── Partial Index — index only subset of rows ───
-- Use: most queries filter same condition (WHERE is_active = TRUE)
CREATE INDEX idx_users_active_email ON users (email)
    WHERE is_active = TRUE AND deleted_at IS NULL;
-- Smaller index — only active users indexed — faster + less storage

-- ─── Covering Index (INCLUDE) — index-only scan ───
-- All needed columns in index → no table access
CREATE INDEX idx_posts_covering ON posts (status, created_at DESC)
    INCLUDE (id, title, author_id);
-- Query: SELECT id, title, author_id WHERE status='published' ORDER BY created_at
-- → Index-only scan! Never touches main table

-- ─── Index usage rules ───
-- DO index: columns in WHERE, JOIN ON, ORDER BY, GROUP BY
-- DO index: FK columns (always index foreign keys)
-- DON'T index: low cardinality (boolean, status with 2-3 values) — unless partial
-- DON'T index: small tables (< 1000 rows) — seq scan faster
-- DON'T over-index: each index slows INSERT/UPDATE/DELETE

-- ─── Find unused indexes ───
SELECT
    schemaname, tablename, indexname, idx_scan AS scans
FROM pg_stat_user_indexes
WHERE idx_scan = 0
  AND indexname NOT LIKE '%pkey%'
ORDER BY schemaname, tablename;

-- ─── Find missing indexes (high seq scans) ───
SELECT
    relname AS table,
    seq_scan, idx_scan,
    seq_scan - idx_scan AS diff
FROM pg_stat_user_tables
WHERE seq_scan > 100
ORDER BY diff DESC;
```

---

### Q4: Zero-downtime migrations — large table mein kaise?

**Answer:**
```sql
-- ─── Problem: ALTER TABLE on 50M row table ───
-- ALTER TABLE users ADD COLUMN metadata JSONB NOT NULL DEFAULT '{}'
-- → Table lock! Production down for minutes/hours

-- ─── Solution: 3-step zero-downtime ───

-- Step 1: Add column NULLABLE (instant — no lock, no default fill)
ALTER TABLE users ADD COLUMN metadata JSONB;
-- Deploy app code that handles null metadata

-- Step 2: Backfill in small batches (no lock)
DO $$
DECLARE
    batch_size INT := 10000;
    offset_val BIGINT := 0;
    affected INT;
BEGIN
    LOOP
        UPDATE users SET metadata = '{}'
        WHERE id IN (
            SELECT id FROM users
            WHERE metadata IS NULL
            LIMIT batch_size
        );
        GET DIAGNOSTICS affected = ROW_COUNT;
        EXIT WHEN affected = 0;
        PERFORM pg_sleep(0.1);  -- throttle — don't overwhelm DB
    END LOOP;
END $$;

-- Step 3: Add NOT NULL constraint (separate migration, after backfill done)
ALTER TABLE users ALTER COLUMN metadata SET NOT NULL;
ALTER TABLE users ALTER COLUMN metadata SET DEFAULT '{}';

-- ─── Adding index to large table — CONCURRENTLY ───
-- Regular CREATE INDEX locks table
-- CONCURRENTLY = no lock (slower build, but safe for production)
CREATE INDEX CONCURRENTLY idx_users_metadata ON users USING gin(metadata);
-- Warning: CONCURRENTLY cannot run inside a transaction block

-- ─── Renaming a column safely ───
-- Step 1: Add new column
ALTER TABLE users ADD COLUMN full_name VARCHAR(200);
-- Step 2: Backfill
UPDATE users SET full_name = first_name || ' ' || last_name;
-- Step 3: Deploy app to write to BOTH old + new
-- Step 4: Deploy app to read from new
-- Step 5: Remove old column
ALTER TABLE users DROP COLUMN first_name, DROP COLUMN last_name;
```

---

## Summary

| pgvector operator | Metric | Use For |
|------------------|--------|---------|
| `<=>` | Cosine distance | Text/image similarity (normalized) |
| `<->` | L2 distance | Exact vector distance |
| `<#>` | Inner product | Pre-normalized vectors |

| Normalization Form | Eliminates |
|-------------------|-----------|
| 1NF | Repeating groups, non-atomic |
| 2NF | Partial dependencies |
| 3NF | Transitive dependencies |
| Denormalize | Join overhead (counts, aggregates) |

| Migration Type | Command | Lock? |
|---------------|---------|-------|
| Add nullable column | `ALTER TABLE ADD COLUMN` | No |
| Add NOT NULL column | 3-step nullable→backfill→notnull | No |
| Create index | `CREATE INDEX` | Yes (table lock!) |
| Create index safely | `CREATE INDEX CONCURRENTLY` | No (slow build) |
