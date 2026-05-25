"""
pgvector — Practical Examples
═══════════════════════════════════════════════════════════════
Run: python 03_pgvector_practical.py
Install: pip install asyncpg pgvector sqlalchemy[asyncio] openai numpy

Prerequisites:
  docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres pgvector/pgvector:pg16
  (or: CREATE EXTENSION vector; in your PostgreSQL)

Topics:
  - pgvector extension + column setup
  - Store embeddings (simulated — no OpenAI key needed)
  - Cosine similarity search (<=>)
  - L2 distance search (<->)
  - Hybrid search (FTS + vector)
  - HNSW + IVFFlat index creation
  - SQLAlchemy ORM with pgvector
  - Filtering + vector search combined

INTERVIEW QUICK REFERENCE at bottom.
"""

import asyncio
import asyncpg
import json
import math
import random
import time
from typing import List

DB_URL = "postgresql://postgres:postgres@localhost:5432/pgvector_demo"

# ─── Simulated embeddings (no OpenAI key needed) ───
# Real embeddings: openai.AsyncOpenAI().embeddings.create(model="text-embedding-ada-002", input=text)
# We simulate 128-dim embeddings for demo purposes

EMBEDDING_DIM = 128  # real: 1536 for ada-002, 768 for sentence-transformers


def make_embedding(seed: int, dim: int = EMBEDDING_DIM) -> List[float]:
    """Generate reproducible fake embedding for demo."""
    rng = random.Random(seed)
    vec = [rng.gauss(0, 1) for _ in range(dim)]
    # Normalize to unit length (like real embeddings)
    magnitude = math.sqrt(sum(x * x for x in vec))
    return [x / magnitude for x in vec]


def vec_to_str(vec: List[float]) -> str:
    """Format vector for pgvector."""
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


# Simulated "semantic" embeddings — docs about similar topics get similar seeds
DOCUMENTS = [
    {"content": "Django ORM select_related optimizes SQL JOIN queries",         "category": "django",    "seed": 10},
    {"content": "Django prefetch_related handles many-to-many relationships",   "category": "django",    "seed": 11},
    {"content": "FastAPI async endpoints using asyncio for high performance",   "category": "fastapi",   "seed": 20},
    {"content": "FastAPI dependency injection system for reusable components",  "category": "fastapi",   "seed": 21},
    {"content": "Redis sorted sets for leaderboard and rate limiting",          "category": "redis",     "seed": 30},
    {"content": "Redis streams with consumer groups for event processing",      "category": "redis",     "seed": 31},
    {"content": "PostgreSQL window functions for analytical queries",           "category": "postgres",  "seed": 40},
    {"content": "PostgreSQL EXPLAIN ANALYZE for query optimization",            "category": "postgres",  "seed": 41},
    {"content": "Python asyncio event loop and coroutines explained",           "category": "python",    "seed": 50},
    {"content": "Python type hints and Pydantic for data validation",           "category": "python",    "seed": 51},
    {"content": "LangChain agents for AI-powered applications",                 "category": "ai",        "seed": 60},
    {"content": "RAG pipeline with vector database for semantic search",        "category": "ai",        "seed": 61},
    {"content": "Docker containerization and Kubernetes orchestration",         "category": "devops",    "seed": 70},
    {"content": "CI/CD pipeline with GitHub Actions for automated deployment",  "category": "devops",    "seed": 71},
    {"content": "GraphQL schema design with mutations and subscriptions",       "category": "api",       "seed": 80},
]

SETUP_SQL = f"""
DROP TABLE IF EXISTS documents;
DROP TABLE IF EXISTS products;

-- ─── Documents table with vector embeddings ───
CREATE TABLE documents (
    id          SERIAL PRIMARY KEY,
    content     TEXT NOT NULL,
    category    VARCHAR(50),
    embedding   VECTOR({EMBEDDING_DIM}),
    search_vec  TSVECTOR,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Products table for combined search demo ───
CREATE TABLE products (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT,
    category    VARCHAR(50),
    price       DECIMAL(10, 2),
    in_stock    BOOLEAN DEFAULT TRUE,
    embedding   VECTOR({EMBEDDING_DIM}),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
"""

PRODUCTS = [
    {"name": "Python Advanced Course",      "description": "Deep dive into Python async, decorators, metaclasses", "category": "education", "price": 49.99,  "seed": 50},
    {"name": "FastAPI Masterclass",         "description": "Build production APIs with FastAPI and SQLAlchemy",     "category": "education", "price": 39.99,  "seed": 20},
    {"name": "Redis in Action",             "description": "Caching, rate limiting and messaging with Redis",       "category": "education", "price": 29.99,  "seed": 30},
    {"name": "AI Engineering Bootcamp",     "description": "LangChain, RAG, vector databases for AI apps",         "category": "education", "price": 99.99,  "seed": 60},
    {"name": "MacBook Pro 16\"",            "description": "Apple M3 Pro chip for developers",                     "category": "hardware",  "price": 2499.00,"seed": 90},
    {"name": "Mechanical Keyboard",         "description": "Cherry MX switches, TKL layout for coding",            "category": "hardware",  "price": 129.99, "seed": 91},
]


# ═══════════════════════════════════════════════════════════
# SECTION 1: Setup + Store Embeddings
# ═══════════════════════════════════════════════════════════

async def setup_database(conn):
    print("Setting up database...")
    # Enable pgvector extension
    await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    await conn.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    await conn.execute(SETUP_SQL)

    # Insert documents with embeddings
    for doc in DOCUMENTS:
        embedding = make_embedding(doc["seed"])
        embed_str = vec_to_str(embedding)
        search_vec = f"to_tsvector('english', $1)"

        await conn.execute("""
            INSERT INTO documents (content, category, embedding, search_vec)
            VALUES ($1, $2, $3::vector, to_tsvector('english', $1))
        """, doc["content"], doc["category"], embed_str)

    # Insert products with embeddings
    for prod in PRODUCTS:
        embedding = make_embedding(prod["seed"])
        embed_str = vec_to_str(embedding)
        await conn.execute("""
            INSERT INTO products (name, description, category, price, embedding)
            VALUES ($1, $2, $3, $4, $5::vector)
        """, prod["name"], prod["description"], prod["category"], prod["price"], embed_str)

    print(f"  ✓ Inserted {len(DOCUMENTS)} documents, {len(PRODUCTS)} products")


# ═══════════════════════════════════════════════════════════
# SECTION 2: Cosine Similarity Search
# ═══════════════════════════════════════════════════════════

async def demo_cosine_search(conn):
    print("\n--- COSINE SIMILARITY SEARCH (<=> operator) ---")
    """
    INTERVIEW: <=> kya hai?
    Cosine distance = 1 - cosine_similarity
    Range: 0 (identical) to 2 (opposite)
    Best for: text embeddings (semantic similarity)
    """

    # Simulate a query about "web framework async performance"
    # Using seed=20 which is close to FastAPI docs
    query_embedding = make_embedding(20)  # similar to FastAPI docs
    query_str = vec_to_str(query_embedding)

    rows = await conn.fetch("""
        SELECT
            id,
            content,
            category,
            1 - (embedding <=> $1::vector) AS cosine_similarity,
            embedding <=> $1::vector       AS cosine_distance
        FROM documents
        ORDER BY embedding <=> $1::vector   -- order by distance (lower = more similar)
        LIMIT 5
    """, query_str)

    print("  Top 5 results (query similar to FastAPI):")
    for row in rows:
        sim = row["cosine_similarity"]
        bar = "█" * int(sim * 20)
        print(f"  [{sim:.3f}] {bar:<20} {row['content'][:55]}... ({row['category']})")


# ═══════════════════════════════════════════════════════════
# SECTION 3: L2 Distance Search
# ═══════════════════════════════════════════════════════════

async def demo_l2_search(conn):
    print("\n--- L2 DISTANCE SEARCH (<-> operator) ---")
    """
    INTERVIEW: <-> kya hai?
    L2 = Euclidean distance
    Good for: non-normalized vectors
    For normalized vectors, cosine ≈ L2 but cosine is usually preferred for text
    """

    query_embedding = make_embedding(60)  # similar to AI docs
    query_str = vec_to_str(query_embedding)

    rows = await conn.fetch("""
        SELECT
            content,
            category,
            embedding <-> $1::vector AS l2_distance
        FROM documents
        ORDER BY embedding <-> $1::vector
        LIMIT 5
    """, query_str)

    print("  Top 5 results (query similar to AI/LangChain):")
    for row in rows:
        print(f"  [dist={row['l2_distance']:.4f}] {row['content'][:55]}... ({row['category']})")


# ═══════════════════════════════════════════════════════════
# SECTION 4: Similarity Threshold Filtering
# ═══════════════════════════════════════════════════════════

async def demo_similarity_threshold(conn):
    print("\n--- SIMILARITY THRESHOLD FILTERING ---")
    """
    INTERVIEW: Threshold kaise lagaate hain?
    Only return results above similarity threshold
    Common practice: 0.7+ for high similarity, 0.5+ for moderate
    """

    query_embedding = make_embedding(30)  # similar to Redis docs
    query_str = vec_to_str(query_embedding)

    threshold = 0.85  # only very similar docs

    rows = await conn.fetch("""
        SELECT
            content,
            category,
            1 - (embedding <=> $1::vector) AS similarity
        FROM documents
        WHERE 1 - (embedding <=> $1::vector) > $2
        ORDER BY embedding <=> $1::vector
        LIMIT 10
    """, query_str, threshold)

    print(f"  Results with similarity > {threshold} (query similar to Redis):")
    if rows:
        for row in rows:
            print(f"  [{row['similarity']:.3f}] {row['content'][:60]}...")
    else:
        print(f"  No results above threshold {threshold}")
        # Lower threshold for demo
        rows = await conn.fetch("""
            SELECT content, category, 1 - (embedding <=> $1::vector) AS similarity
            FROM documents ORDER BY embedding <=> $1::vector LIMIT 3
        """, query_str)
        print(f"  Top 3 regardless of threshold:")
        for row in rows:
            print(f"  [{row['similarity']:.3f}] {row['content'][:60]}...")


# ═══════════════════════════════════════════════════════════
# SECTION 5: Hybrid Search (FTS + Vector)
# ═══════════════════════════════════════════════════════════

async def demo_hybrid_search(conn):
    print("\n--- HYBRID SEARCH (Full-Text + Vector) ---")
    """
    INTERVIEW: Hybrid search kab use karte hain?
    Pure vector: semantic similarity but misses exact keywords
    Pure FTS:    exact keywords but misses semantic similarity
    Hybrid:      best of both — keyword + semantic match

    Technique: weighted sum of FTS rank + vector similarity
    """

    query_text = "python async programming"
    query_embedding = make_embedding(50)  # similar to Python docs
    query_str = vec_to_str(query_embedding)

    rows = await conn.fetch("""
        SELECT
            d.id,
            d.content,
            d.category,
            ts_rank(d.search_vec, to_tsquery('english', $2)) AS text_score,
            1 - (d.embedding <=> $3::vector)                  AS vector_score,
            -- Weighted combination: 30% text + 70% vector
            0.3 * ts_rank(d.search_vec, to_tsquery('english', $2))
            + 0.7 * (1 - (d.embedding <=> $3::vector))        AS combined_score
        FROM documents d
        WHERE
            d.search_vec @@ to_tsquery('english', $2)
            OR (d.embedding <=> $3::vector) < 0.5
        ORDER BY combined_score DESC
        LIMIT 5
    """, query_text, "python & async", query_str)

    print(f"  Hybrid search for: '{query_text}'")
    for row in rows:
        print(f"  [combined={row['combined_score']:.3f}] "
              f"text={row['text_score']:.3f} vec={row['vector_score']:.3f} "
              f"| {row['content'][:50]}...")


# ═══════════════════════════════════════════════════════════
# SECTION 6: Filter + Vector Search (Metadata Filtering)
# ═══════════════════════════════════════════════════════════

async def demo_filtered_vector_search(conn):
    print("\n--- FILTERED VECTOR SEARCH (Metadata + Vector) ---")
    """
    INTERVIEW: Metadata filtering kaise karte hain?
    WHERE clause + ORDER BY vector distance
    Important: Filter BEFORE vector scan for efficiency
    pgvector will use index + post-filter
    """

    query_embedding = make_embedding(20)
    query_str = vec_to_str(query_embedding)

    # Search only within 'fastapi' category
    rows = await conn.fetch("""
        SELECT content, category, 1 - (embedding <=> $1::vector) AS similarity
        FROM documents
        WHERE category = $2             -- metadata filter
        ORDER BY embedding <=> $1::vector
        LIMIT 3
    """, query_str, "fastapi")

    print("  Vector search filtered to category='fastapi':")
    for row in rows:
        print(f"  [{row['similarity']:.3f}] {row['content']}")

    # Price + vector search in products
    query_embedding2 = make_embedding(50)  # Python-related
    query_str2 = vec_to_str(query_embedding2)

    products = await conn.fetch("""
        SELECT name, price, category,
               1 - (embedding <=> $1::vector) AS similarity
        FROM products
        WHERE price < $2 AND in_stock = TRUE
        ORDER BY embedding <=> $1::vector
        LIMIT 3
    """, query_str2, 100.0)

    print("\n  Product search (price < $100, in stock, similar to Python):")
    for p in products:
        print(f"  [{p['similarity']:.3f}] ${p['price']:6.2f} | {p['name']}")


# ═══════════════════════════════════════════════════════════
# SECTION 7: Index Creation (HNSW + IVFFlat)
# ═══════════════════════════════════════════════════════════

async def demo_indexes(conn):
    print("\n--- INDEX CREATION (HNSW + IVFFlat) ---")
    """
    INTERVIEW: HNSW vs IVFFlat?

    IVFFlat:
      + Faster build time
      + Lower memory usage
      - Slightly lower recall
      lists = sqrt(row_count) recommended
      Needs: SELECT before index build (otherwise lists=1)

    HNSW:
      + Better recall (more accurate)
      + Better for concurrent inserts
      - Slower build, more memory
      m = 16 (connections), ef_construction = 64 (build quality)
      Production recommended for query performance
    """

    # Drop existing indexes if any
    await conn.execute("DROP INDEX IF EXISTS idx_docs_hnsw")
    await conn.execute("DROP INDEX IF EXISTS idx_docs_ivfflat")

    # IVFFlat index — cosine
    print("  Creating IVFFlat index (cosine)...")
    t0 = time.time()
    await conn.execute("""
        CREATE INDEX idx_docs_ivfflat ON documents
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 10)
    """)
    print(f"  ✓ IVFFlat created in {time.time()-t0:.3f}s")

    # HNSW index — cosine (better recall)
    print("  Creating HNSW index (cosine)...")
    t0 = time.time()
    await conn.execute("""
        CREATE INDEX idx_docs_hnsw ON documents
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)
    print(f"  ✓ HNSW created in {time.time()-t0:.3f}s")

    # Check index usage with EXPLAIN
    query_embedding = make_embedding(30)
    query_str = vec_to_str(query_embedding)

    plan = await conn.fetchval("""
        EXPLAIN (FORMAT TEXT)
        SELECT content, embedding <=> $1::vector AS dist
        FROM documents
        ORDER BY embedding <=> $1::vector
        LIMIT 5
    """, query_str)
    print("\n  EXPLAIN plan (with index):")
    for line in plan.split("\n")[:8]:
        print(f"    {line}")


# ═══════════════════════════════════════════════════════════
# SECTION 8: Bulk Embedding Update
# ═══════════════════════════════════════════════════════════

async def demo_bulk_update(conn):
    print("\n--- BULK EMBEDDING UPDATE ---")
    """
    INTERVIEW: Large table mein embeddings kaise update kare?
    Batch processing — don't update all at once (locks table)
    Real world: queue-based embedding generation
    """

    # Simulate updating embeddings in batches (re-embed with different dim model)
    batch_size = 5
    offset = 0
    updated = 0

    while True:
        rows = await conn.fetch("""
            SELECT id, content FROM documents
            ORDER BY id
            LIMIT $1 OFFSET $2
        """, batch_size, offset)

        if not rows:
            break

        # Simulate generating new embeddings
        for row in rows:
            new_embedding = make_embedding(row["id"] * 7 + 13)
            embed_str = vec_to_str(new_embedding)
            await conn.execute("""
                UPDATE documents SET embedding = $1::vector WHERE id = $2
            """, embed_str, row["id"])
            updated += 1

        offset += batch_size

    print(f"  ✓ Re-embedded {updated} documents in batches of {batch_size}")


# ═══════════════════════════════════════════════════════════
# SECTION 9: SQLAlchemy ORM with pgvector
# ═══════════════════════════════════════════════════════════

async def demo_sqlalchemy_pattern():
    """
    INTERVIEW: SQLAlchemy + pgvector kaise use karte hain?
    """
    print("\n--- SQLAlchemy ORM PATTERN (Code Only — no live run) ---")

    code = '''
# pip install pgvector sqlalchemy[asyncio] asyncpg

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Text, DateTime
from pgvector.sqlalchemy import Vector
from datetime import datetime

class Base(DeclarativeBase):
    pass

class Document(Base):
    __tablename__ = "documents"

    id        : Mapped[int]        = mapped_column(primary_key=True)
    content   : Mapped[str]        = mapped_column(Text)
    category  : Mapped[str | None] = mapped_column(String(50))
    embedding : Mapped[list[float]]= mapped_column(Vector(1536), nullable=True)
    created_at: Mapped[datetime]   = mapped_column(default=datetime.utcnow)

# ─── Store embedding ───
from sqlalchemy.ext.asyncio import AsyncSession

async def store_document(session: AsyncSession, content: str, category: str, embedding: list[float]):
    doc = Document(content=content, category=category, embedding=embedding)
    session.add(doc)
    await session.commit()
    return doc

# ─── Similarity search ───
from sqlalchemy import text

async def semantic_search(session: AsyncSession, query_embedding: list[float], top_k: int = 5):
    result = await session.execute(
        text("""
            SELECT id, content, category,
                   1 - (embedding <=> :embedding::vector) AS similarity
            FROM documents
            WHERE 1 - (embedding <=> :embedding::vector) > 0.7
            ORDER BY embedding <=> :embedding::vector
            LIMIT :top_k
        """),
        {"embedding": str(query_embedding), "top_k": top_k}
    )
    return result.mappings().all()

# ─── With metadata filter ───
async def search_by_category(session, query_embedding, category: str):
    result = await session.execute(
        text("""
            SELECT id, content,
                   1 - (embedding <=> :emb::vector) AS similarity
            FROM documents
            WHERE category = :cat
            ORDER BY embedding <=> :emb::vector
            LIMIT 10
        """),
        {"emb": str(query_embedding), "cat": category}
    )
    return result.mappings().all()
'''
    print(code)


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

async def main():
    print("Connecting to PostgreSQL (pgvector)...")
    try:
        conn = await asyncpg.connect(DB_URL)
    except Exception as e:
        print(f"Connection failed: {e}")
        print("Start with: docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres pgvector/pgvector:pg16")
        return

    print("✓ Connected")

    try:
        await setup_database(conn)
        await demo_cosine_search(conn)
        await demo_l2_search(conn)
        await demo_similarity_threshold(conn)
        await demo_hybrid_search(conn)
        await demo_filtered_vector_search(conn)
        await demo_indexes(conn)
        await demo_bulk_update(conn)
        await demo_sqlalchemy_pattern()

    finally:
        await conn.close()
        print("\n✓ All pgvector demos complete!")


# ═══════════════════════════════════════════════════════════
# INTERVIEW QUICK REFERENCE
# ═══════════════════════════════════════════════════════════
"""
Q: pgvector operators kaunse hain?
A: <=>  cosine distance  (best for text — normalized vectors)
   <->  L2/Euclidean     (exact vector distance)
   <#>  inner product    (multiply by -1 for similarity, for pre-normalized)

Q: HNSW vs IVFFlat?
A: IVFFlat:  faster build, less memory, slightly lower recall
             lists = sqrt(row_count)
             Good for: < 1M vectors, offline batch indexing
   HNSW:     better recall, slower build, more memory
             m=16, ef_construction=64 are good defaults
             Good for: production query performance, concurrent writes

Q: pgvector vs Pinecone/Qdrant?
A: pgvector:     existing PostgreSQL infra, ACID, SQL joins, < 10M vectors
   Dedicated DB: blazing fast at 100M+ vectors, advanced filtering, separate infra

Q: Hybrid search kaise karte hain?
A: combined_score = 0.3 * ts_rank(...) + 0.7 * (1 - cosine_distance)
   WHERE (fts_match) OR (cosine_distance < threshold)

Q: Embedding update large table mein?
A: Batch processing with OFFSET/LIMIT, add embedding column nullable first,
   fill in background worker, then enforce NOT NULL

Q: Dimensions kaise choose karte hain?
A: OpenAI ada-002:          1536 dims — gold standard text
   OpenAI 3-large:          3072 dims — highest quality (costly)
   sentence-transformers:   768  dims — free, good quality
   Your own model:          128-512 dims — fast, domain-specific

Q: Similarity threshold kya rakhna chahiye?
A: > 0.9  = near-duplicate
   > 0.7  = very similar (production RAG cutoff)
   > 0.5  = related topic
   < 0.3  = probably unrelated
"""

if __name__ == "__main__":
    asyncio.run(main())
