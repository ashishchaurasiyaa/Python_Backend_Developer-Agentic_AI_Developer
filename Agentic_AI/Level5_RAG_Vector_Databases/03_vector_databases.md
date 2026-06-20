# Vector Databases — pgvector, Pinecone, Qdrant, HNSW, Index Types

## Quick Concepts
- **Vector DB** = embeddings store aur search karo — semantic similarity ke liye
- **HNSW** = Hierarchical Navigable Small World — fast approximate nearest neighbor algorithm
- **IVFFlat** = Inverted File Index — cluster-based search, memory efficient
- **pgvector** = PostgreSQL extension — existing DB mein vector search add karo
- **Qdrant/Pinecone** = dedicated vector DBs — scale, filtering, namespaces

---

## Interview Questions & Answers

### Q1: pgvector — PostgreSQL mein vector search kaise karte hain?
**Answer:**
```python
# pip install asyncpg pgvector sqlalchemy[asyncio]

import asyncpg
import numpy as np
from openai import OpenAI

openai_client = OpenAI()

# ===== SETUP =====
async def setup_pgvector(conn):
    await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id SERIAL PRIMARY KEY,
            content TEXT NOT NULL,
            embedding vector(1536),       -- text-embedding-3-small = 1536 dims
            metadata JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    
    # HNSW index — fast search, high memory
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS documents_hnsw_idx
        ON documents USING hnsw(embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)
    
    # IVFFlat index — lower memory, slightly less accurate
    # await conn.execute("""
    #     CREATE INDEX IF NOT EXISTS documents_ivfflat_idx
    #     ON documents USING ivfflat(embedding vector_cosine_ops)
    #     WITH (lists = 100)
    # """)

# ===== UPSERT DOCUMENTS =====
def get_embedding(text: str) -> list[float]:
    response = openai_client.embeddings.create(
        input=text, model="text-embedding-3-small"
    )
    return response.data[0].embedding

async def upsert_document(conn, content: str, metadata: dict = None):
    embedding = get_embedding(content)
    await conn.execute("""
        INSERT INTO documents (content, embedding, metadata)
        VALUES ($1, $2::vector, $3)
    """, content, embedding, metadata or {})

async def bulk_upsert(conn, documents: list[dict]):
    """Efficient bulk insert"""
    embeddings = []
    texts = [d["content"] for d in documents]
    
    # Batch embeddings (one API call)
    response = openai_client.embeddings.create(
        input=texts, model="text-embedding-3-small"
    )
    embeddings = [item.embedding for item in sorted(response.data, key=lambda x: x.index)]
    
    await conn.executemany("""
        INSERT INTO documents (content, embedding, metadata)
        VALUES ($1, $2::vector, $3)
    """, [(doc["content"], emb, doc.get("metadata", {}))
          for doc, emb in zip(documents, embeddings)])

# ===== SIMILARITY SEARCH =====
async def semantic_search(conn, query: str, limit: int = 5) -> list[dict]:
    query_embedding = get_embedding(query)
    
    rows = await conn.fetch("""
        SELECT
            id,
            content,
            metadata,
            1 - (embedding <=> $1::vector) AS similarity
        FROM documents
        ORDER BY embedding <=> $1::vector   -- <=> = cosine distance
        LIMIT $2
    """, query_embedding, limit)
    
    return [dict(r) for r in rows]

# DISTANCE OPERATORS:
# <=>  cosine distance        (direction-based; magnitude pgvector khud handle karta hai —
#                              embeddings ke liye MOST COMMON, pehle se normalize karna ZAROORI NAHI)
# <->  L2/Euclidean distance
# <#>  NEGATIVE inner product (ORDER BY ascending hota hai, isliye pgvector negative deta hai —
#                              ascending sort = asli dot product maximize. Normalized vectors pe dot == cosine)

# ===== FILTERED SEARCH =====
async def filtered_search(
    conn, query: str,
    metadata_filter: dict = None,
    limit: int = 5,
) -> list[dict]:
    query_embedding = get_embedding(query)
    
    # Build WHERE clause from metadata filter
    where_conditions = ["1=1"]
    params = [query_embedding, limit]
    
    if metadata_filter:
        for key, value in metadata_filter.items():
            params.append(value)
            where_conditions.append(f"metadata->>'${key}' = ${len(params)}")
    
    # Simpler JSONB filtering
    rows = await conn.fetch("""
        SELECT id, content, metadata,
               1 - (embedding <=> $1::vector) AS similarity
        FROM documents
        WHERE metadata @> $3::jsonb        -- JSONB contains filter
        ORDER BY embedding <=> $1::vector
        LIMIT $2
    """, query_embedding, limit, metadata_filter or {})
    
    return [dict(r) for r in rows]

# ===== HYBRID SEARCH (Dense + Sparse) =====
async def hybrid_search(conn, query: str, limit: int = 5) -> list[dict]:
    query_embedding = get_embedding(query)
    
    rows = await conn.fetch("""
        WITH dense AS (
            SELECT id, content, metadata,
                   ROW_NUMBER() OVER (ORDER BY embedding <=> $1::vector) AS dense_rank
            FROM documents
            LIMIT 20
        ),
        sparse AS (
            SELECT id, content, metadata,
                   ROW_NUMBER() OVER (
                       ORDER BY ts_rank(to_tsvector('english', content),
                                        plainto_tsquery('english', $2)) DESC
                   ) AS sparse_rank
            FROM documents
            WHERE to_tsvector('english', content) @@ plainto_tsquery('english', $2)
            LIMIT 20
        ),
        combined AS (
            SELECT
                COALESCE(d.id, s.id) AS id,
                COALESCE(d.content, s.content) AS content,
                COALESCE(d.metadata, s.metadata) AS metadata,
                COALESCE(1.0 / (60 + d.dense_rank), 0) * 0.7 +
                COALESCE(1.0 / (60 + s.sparse_rank), 0) * 0.3 AS rrf_score
            FROM dense d FULL OUTER JOIN sparse s ON d.id = s.id
        )
        SELECT * FROM combined ORDER BY rrf_score DESC LIMIT $3
    """, query_embedding, query, limit)
    
    return [dict(r) for r in rows]

# Usage
import asyncio

async def main():
    conn = await asyncpg.connect("postgresql://user:pass@localhost/mydb")
    await setup_pgvector(conn)
    
    await upsert_document(conn, "Python generators use yield for lazy evaluation", {"topic": "python"})
    await upsert_document(conn, "FastAPI is a modern async web framework", {"topic": "fastapi"})
    
    results = await semantic_search(conn, "How do generators work?")
    for r in results:
        print(f"[{r['similarity']:.3f}] {r['content']}")

asyncio.run(main())
```

---

### Q2: Qdrant — dedicated vector DB kaise use karte hain?
**Answer:**
```python
# pip install qdrant-client
# docker run -p 6333:6333 qdrant/qdrant

from qdrant_client import QdrantClient, AsyncQdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    Filter, FieldCondition, MatchValue, Range,
    HnswConfigDiff, OptimizersConfigDiff,
    SearchRequest, ScoredPoint,
)
import uuid

# Client
client = QdrantClient(host="localhost", port=6333)
async_client = AsyncQdrantClient(host="localhost", port=6333)

# Cloud
# client = QdrantClient(url="https://xyz.qdrant.io", api_key="your-api-key")

COLLECTION = "documents"

# ===== CREATE COLLECTION =====
client.create_collection(
    collection_name=COLLECTION,
    vectors_config=VectorParams(
        size=1536,                   # embedding dimension
        distance=Distance.COSINE,    # COSINE, EUCLID, DOT
    ),
    hnsw_config=HnswConfigDiff(
        m=16,                        # connections per node (higher = more accurate, more memory)
        ef_construct=100,            # build-time search depth
        full_scan_threshold=10000,   # below this, full scan used
    ),
    optimizers_config=OptimizersConfigDiff(
        default_segment_number=2,
        memmap_threshold=20000,       # switch to mmap for large collections
    ),
)

# ===== UPSERT POINTS =====
def upsert_documents(documents: list[dict]):
    embeddings = get_batch_embeddings([d["content"] for d in documents])
    
    points = [
        PointStruct(
            id=str(uuid.uuid4()),    # string or int
            vector=embedding,
            payload={                # metadata
                "content": doc["content"],
                "source": doc.get("source", ""),
                "topic": doc.get("topic", ""),
                "year": doc.get("year", 2025),
            }
        )
        for doc, embedding in zip(documents, embeddings)
    ]
    
    client.upsert(
        collection_name=COLLECTION,
        points=points,
        wait=True,  # wait for indexing
    )

# ===== SEARCH =====
def search_documents(query: str, limit: int = 5) -> list[dict]:
    query_embedding = get_embedding(query)
    
    results = client.search(
        collection_name=COLLECTION,
        query_vector=query_embedding,
        limit=limit,
        with_payload=True,   # include metadata
        score_threshold=0.7, # minimum similarity
    )
    
    return [
        {
            "content": hit.payload["content"],
            "score": hit.score,
            "id": hit.id,
        }
        for hit in results
    ]

# ===== FILTERED SEARCH =====
def filtered_search_qdrant(query: str, topic: str = None, year_min: int = None) -> list[dict]:
    query_embedding = get_embedding(query)
    
    # Build filter
    conditions = []
    if topic:
        conditions.append(FieldCondition(key="topic", match=MatchValue(value=topic)))
    if year_min:
        conditions.append(FieldCondition(key="year", range=Range(gte=year_min)))
    
    search_filter = Filter(must=conditions) if conditions else None
    
    results = client.search(
        collection_name=COLLECTION,
        query_vector=query_embedding,
        query_filter=search_filter,
        limit=5,
        with_payload=True,
    )
    
    return [{"content": hit.payload["content"], "score": hit.score} for hit in results]

# ===== NAMESPACES (for multi-tenant) =====
# Qdrant: separate collections per tenant
# OR: use payload field "user_id" + filter

# ===== ASYNC BATCH SEARCH =====
async def parallel_searches(queries: list[str]) -> list[list[dict]]:
    import asyncio
    embeddings = [get_embedding(q) for q in queries]
    
    tasks = [
        async_client.search(
            collection_name=COLLECTION,
            query_vector=emb,
            limit=5,
        )
        for emb in embeddings
    ]
    
    all_results = await asyncio.gather(*tasks)
    return [[{"content": h.payload["content"], "score": h.score} for h in results]
            for results in all_results]
```

---

### Q3: Pinecone — managed cloud vector DB?
**Answer:**
```python
# pip install pinecone-client

from pinecone import Pinecone, ServerlessSpec
import os

pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))

INDEX_NAME = "my-documents"

# ===== CREATE INDEX =====
if INDEX_NAME not in pc.list_indexes().names():
    pc.create_index(
        name=INDEX_NAME,
        dimension=1536,
        metric="cosine",          # cosine, euclidean, dotproduct
        spec=ServerlessSpec(
            cloud="aws",
            region="us-east-1",
        )
    )

index = pc.Index(INDEX_NAME)

# ===== UPSERT =====
def upsert_to_pinecone(documents: list[dict]):
    embeddings = get_batch_embeddings([d["content"] for d in documents])
    
    vectors = [
        {
            "id": f"doc-{i}",
            "values": embedding,
            "metadata": {         # filterable metadata
                "content": doc["content"],
                "source": doc.get("source", ""),
                "topic": doc.get("topic", ""),
            }
        }
        for i, (doc, embedding) in enumerate(zip(documents, embeddings))
    ]
    
    # Batch upsert (max 100 vectors per request)
    batch_size = 100
    for i in range(0, len(vectors), batch_size):
        index.upsert(vectors=vectors[i:i+batch_size])

# ===== QUERY =====
def query_pinecone(query: str, filter: dict = None, top_k: int = 5) -> list[dict]:
    query_embedding = get_embedding(query)
    
    results = index.query(
        vector=query_embedding,
        top_k=top_k,
        include_metadata=True,
        filter=filter,            # {"topic": {"$eq": "python"}}
    )
    
    return [
        {
            "content": match.metadata["content"],
            "score": match.score,
            "id": match.id,
        }
        for match in results.matches
    ]

# Pinecone filter syntax:
# {"topic": {"$eq": "python"}}
# {"year": {"$gte": 2023}}
# {"$and": [{"topic": {"$eq": "python"}}, {"year": {"$gte": 2023}}]}

# ===== NAMESPACES (multi-tenant) =====
# Each user/tenant gets their own namespace
index.upsert(vectors=vectors, namespace="user-123")
results = index.query(vector=query_embedding, namespace="user-123", top_k=5)
```

---

### Q4: HNSW vs IVFFlat — index comparison?
**Answer:**
```
INDEX ALGORITHM COMPARISON:

┌─────────────────┬─────────────────────────┬──────────────────────────┐
│ Feature         │ HNSW                    │ IVFFlat                  │
├─────────────────┼─────────────────────────┼──────────────────────────┤
│ Speed (query)   │ Very fast               │ Fast                     │
│ Speed (build)   │ Slow                    │ Fast                     │
│ Memory          │ High (graph stored)     │ Lower                    │
│ Accuracy        │ High (>99% recall)      │ Good (~95% recall)       │
│ Dynamic adds    │ Yes (add without rebuild)│ Add OK; rebuild advised  │
│ Small datasets  │ Full scan better        │ Full scan better         │
└─────────────────┴─────────────────────────┴──────────────────────────┘

HNSW Parameters (pgvector):
  m = 16              # connections per layer (higher = better recall, more RAM)
  ef_construction=64  # build-time candidates (higher = better index, slower build)
  ef_search=40        # query-time candidates (set via SET hnsw.ef_search=40)

IVFFlat Parameters (pgvector):
  lists = 100         # number of clusters (sqrt(total_rows) is a good default)
  probes = 10         # lists to check at query time (SET ivfflat.probes=10)
                      # higher probes = better recall, slower query

WHEN TO USE:
  HNSW:    Production, read-heavy, accuracy critical, <10M vectors
  IVFFlat: Memory constrained, large dataset, frequent bulk inserts

pgvector example:
```

```python
# HNSW — default for most cases
await conn.execute("""
    CREATE INDEX ON documents
    USING hnsw(embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64)
""")

# Query-time ef_search set karo for better recall
await conn.execute("SET hnsw.ef_search = 100")

# IVFFlat — for larger datasets
await conn.execute("""
    CREATE INDEX ON documents
    USING ivfflat(embedding vector_cosine_ops)
    WITH (lists = 100)
""")
await conn.execute("SET ivfflat.probes = 10")

# Check index usage
rows = await conn.fetch("""
    EXPLAIN (ANALYZE, BUFFERS)
    SELECT id, content, embedding <=> $1::vector AS dist
    FROM documents
    ORDER BY embedding <=> $1::vector
    LIMIT 5
""", query_embedding)
# Look for "Index Scan using documents_hnsw_idx"
```

---

### Q5: Vector DB comparison — kaunsa choose karo production mein?
**Answer:**
```
VECTOR DB DECISION MATRIX:

pgvector (PostgreSQL extension):
  ✓ Existing PostgreSQL mein integrate karo
  ✓ ACID transactions — consistency guaranteed
  ✓ SQL joins with other tables
  ✓ No additional infra
  ✓ Best for: <5M vectors, existing Postgres users
  ✗ Slower than dedicated DBs at scale
  ✗ HNSW memory hungry

Qdrant (open-source, self-host ya cloud):
  ✓ Best performance per cost
  ✓ Rich filtering (payload-based)
  ✓ Quantization support (compress vectors)
  ✓ On-disk indexing (large datasets)
  ✓ Best for: 1M-100M vectors, complex filtering
  ✓ Free self-hosted option

Pinecone (managed SaaS):
  ✓ Zero ops — fully managed
  ✓ Namespaces for multi-tenancy
  ✓ Auto-scaling
  ✗ Expensive at scale
  ✗ No self-host option
  ✓ Best for: startups, quick MVP

Weaviate:
  ✓ GraphQL API
  ✓ Built-in text vectorization
  ✓ Multi-modal support

Chroma (dev/testing):
  ✓ Easiest setup (in-memory or local)
  ✓ LangChain default integration
  ✗ Not production-ready for scale
  Use: local development, testing

MY RECOMMENDATION:
  Dev/testing  → Chroma (zero setup)
  Small prod   → pgvector (if already using Postgres)
  Medium prod  → Qdrant self-hosted
  Large/SaaS   → Pinecone or Qdrant Cloud
```
