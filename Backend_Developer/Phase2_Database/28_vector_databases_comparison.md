# Database — Vector Databases Comparison (Pinecone, Qdrant, Weaviate, Milvus, pgvector)
**Phase 2 Database | Senior Backend + Agentic AI**

## Quick Concepts

- **Vector** = list of floats (embedding from OpenAI, Cohere, BAAI, etc.) — typically 384, 768, 1536, 3072 dims
- **ANN** = Approximate Nearest Neighbor — finds closest vectors fast (vs exact NN)
- **HNSW** = Hierarchical Navigable Small World — graph index, fast + accurate, RAM-hungry
- **IVF** = Inverted File index — cluster-based, less memory, slightly less accurate
- **PQ** = Product Quantization — compress vectors, lower RAM, less accurate
- **Cosine / L2 / Dot product** = similarity metrics (cosine most common for normalized vectors)
- **Hybrid search** = combine vector similarity + keyword (BM25) search
- **Metadata filter** = restrict search by attributes (e.g., `user_id = 42 AND category = 'tech'`)
- **Pre-filter vs Post-filter** = apply filter BEFORE or AFTER ANN search (huge performance implications)

---

## Why Backend Devs Need This in 2026

```
Use cases:
─────────────────────────────────
✓ RAG (Retrieval-Augmented Generation) — most common
✓ Semantic search (better than keyword)
✓ Recommendation systems
✓ Image / audio / video similarity
✓ Duplicate detection
✓ Anomaly detection
✓ Multi-modal search (text + image)

Senior interview Q (2026):
   "Design a vector search for 1B documents
    with metadata filters."

Answer involves picking the right vector DB.
```

---

## The Five Players — At a Glance

| DB | Type | Strength | Weakness | Best For |
|---|---|---|---|---|
| **pgvector** | Postgres extension | Already have Postgres, ACID, joins | RAM-heavy at scale, slower writes | < 100M vectors, OLTP-coupled |
| **Pinecone** | Managed SaaS | Zero ops, scales effortlessly | Expensive, vendor lock-in | Quick MVP, no ops team |
| **Qdrant** | Open-source DB (Rust) | Filtered search excellent, fast, Pythonic | Smaller community | Strong filter requirements |
| **Weaviate** | Open-source DB (Go) | Multi-modal, modules ecosystem | Complex config | Hybrid search + multi-modal |
| **Milvus / Zilliz** | Open-source / managed | Massive scale, billion+ vectors | Operational complexity | > 100M vectors at scale |

---

## Detailed Comparison

### Scale Limits (Real-World)

```
                  10M vectors    100M vectors    1B vectors
                  ─────────────  ──────────────  ──────────────
pgvector:         ✓ comfortable  🟡 tuning needed ✗ painful
Pinecone:         ✓ fine         ✓ fine           ✓ fine (expensive)
Qdrant:           ✓ fast         ✓ fast           🟡 shard wisely
Weaviate:         ✓ fine         ✓ fine           🟡 shard wisely
Milvus:           ✓ overkill     ✓ excellent      ✓ best in class
```

### Indexing Algorithms

| DB | HNSW | IVF | PQ | DiskANN |
|---|---|---|---|---|
| pgvector | ✓ (default 0.5+) | ✓ (IVFFlat) | ✗ | ✗ |
| Pinecone | ✓ (managed) | proprietary | proprietary | ✓ |
| Qdrant | ✓ | ✗ | ✓ (scalar/product) | ✗ |
| Weaviate | ✓ | ✓ (limited) | ✓ | ✗ |
| Milvus | ✓ | ✓ | ✓ | ✓ |

### Filter Performance (Filter While Searching)

```
Critical Q: "Find similar docs WHERE category='AI' AND user_id IN (...)"

pgvector:   ✓ Full SQL filtering, JOIN-friendly, but slow if filter
            is highly selective (post-filter problem)
Pinecone:   ✓ Metadata filtering optimized, but pre-filter on
            large filter sets can be slow
Qdrant:     ✓★ EXCELLENT — payload index + filter-while-search,
            handles selective filters best
Weaviate:   ✓ Filter+vector via "where" — good performance
Milvus:     ✓ Scalar+vector with partition keys, good at scale
```

### Hybrid Search (Vector + BM25)

```
pgvector:   🟡 Manual — combine with Postgres FTS
            DIY but flexible
Pinecone:   ✗ Vector-only (need separate Elasticsearch for BM25)
Qdrant:     ✓ Native — set up sparse vector + dense, fuse scores
Weaviate:   ✓★ Native hybrid (BM25 + vector + reranker)
Milvus:     ✓ Hybrid via sparse vectors (since v2.4)
```

### Operational Complexity

```
Easiest → Hardest:
   Pinecone (managed)
   → pgvector (just Postgres)
   → Qdrant (single binary, simple)
   → Weaviate (more knobs)
   → Milvus (multiple components, K8s recommended)
```

---

## Decision Tree

```
                   ┌─────────────────────────┐
                   │  How many vectors?       │
                   └──────────┬───────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
          < 10M           10M - 100M       > 100M
              │               │               │
              ▼               ▼               ▼
   ┌────────────────┐ ┌────────────────┐ ┌────────────────┐
   │ pgvector       │ │ Already on PG? │ │ Self-host OK?  │
   │ (simplest)     │ └───┬────────────┘ └───┬────────────┘
   └────────────────┘     │                  │
                       Yes│ No            Yes│ No
                          ▼  ▼               ▼  ▼
                  ┌───────┐ ┌────────┐  ┌───────┐ ┌───────────┐
                  │pgvec  │ │Qdrant /│  │Milvus │ │Pinecone   │
                  │tuned  │ │Weaviate│  │Qdrant │ │managed    │
                  └───────┘ └────────┘  └───────┘ └───────────┘

Operational team available?
   No team / startup → Pinecone (managed) or pgvector
   Have DevOps → Qdrant / Weaviate self-hosted
   Strong infra team → Milvus

Filter complexity?
   Simple (no filters)              → any
   Moderate (1-3 metadata fields)   → any
   Heavy (complex filter trees)     → Qdrant
   Need joins with relational data  → pgvector

Hybrid search needed?
   Yes — vendor-managed         → Weaviate
   Yes — DIY OK                 → Qdrant (sparse + dense)
   Yes — already on Postgres    → pgvector + pg_trgm/FTS
   No (vector only)             → any
```

---

## pgvector — The Default Choice for Most

### Schema

```sql
CREATE EXTENSION vector;

CREATE TABLE documents (
    id BIGSERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    embedding vector(1536),       -- OpenAI ada / 3-small
    category TEXT,
    user_id BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- HNSW index (preferred since pgvector 0.5)
CREATE INDEX ON documents USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Or IVFFlat for lower memory
CREATE INDEX ON documents USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 1000);
```

### Query

```sql
-- Top-k similar
SELECT id, content, 1 - (embedding <=> query_embedding) AS similarity
FROM documents
ORDER BY embedding <=> query_embedding
LIMIT 10;

-- With filter (pre-filter in WHERE)
SELECT id, content
FROM documents
WHERE category = 'AI' AND user_id = 42
ORDER BY embedding <=> query_embedding
LIMIT 10;

-- Hybrid (vector + FTS) using RRF
WITH vector_results AS (
    SELECT id, ROW_NUMBER() OVER (ORDER BY embedding <=> $1) AS rank
    FROM documents ORDER BY embedding <=> $1 LIMIT 100
),
bm25_results AS (
    SELECT id, ROW_NUMBER() OVER (ORDER BY ts_rank(tsv, $2) DESC) AS rank
    FROM documents WHERE tsv @@ $2 ORDER BY ts_rank(tsv, $2) DESC LIMIT 100
)
SELECT d.id, d.content,
       (COALESCE(1.0/(60+v.rank), 0) + COALESCE(1.0/(60+b.rank), 0)) AS rrf_score
FROM documents d
LEFT JOIN vector_results v ON d.id = v.id
LEFT JOIN bm25_results b ON d.id = b.id
WHERE v.rank IS NOT NULL OR b.rank IS NOT NULL
ORDER BY rrf_score DESC
LIMIT 10;
```

### When pgvector Hits Limits

```
Symptom: queries > 500ms on > 50M vectors
   ✓ Tune hnsw params: m=32, ef_construction=128
   ✓ Lower dimension if possible (3-small 1536 → use 512 with MRL)
   ✓ Increase shared_buffers (RAM)
   ✓ Move to dedicated read replica

Symptom: HNSW index fits in RAM only
   ✓ Use IVFFlat (less memory)
   ✓ Switch to Qdrant / Milvus

Symptom: filter+vector slow
   ✓ Use partial indexes
   ✓ Use hierarchical pre-filter via separate join
```

---

## Qdrant — Best Filter Performance

### Why Qdrant Stands Out

```
✓ Payload (metadata) indexes — built specifically for vector + filter
✓ Filter-while-search — doesn't post-filter HNSW results
✓ Rust = predictable performance
✓ Python client is excellent
✓ Self-host = single binary, no dependencies
```

### Python Client

```python
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    Filter, FieldCondition, MatchValue
)

client = QdrantClient(host="localhost", port=6333)

# Create collection
client.recreate_collection(
    collection_name="docs",
    vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
)

# Payload index for fast filtering
client.create_payload_index("docs", field_name="category", field_schema="keyword")
client.create_payload_index("docs", field_name="user_id", field_schema="integer")

# Upsert
client.upsert(
    collection_name="docs",
    points=[
        PointStruct(
            id=1,
            vector=embedding,
            payload={"content": "...", "category": "AI", "user_id": 42},
        ),
        # batch of 100-1000
    ],
)

# Search with filter
results = client.search(
    collection_name="docs",
    query_vector=query_embedding,
    query_filter=Filter(
        must=[
            FieldCondition(key="category", match=MatchValue(value="AI")),
            FieldCondition(key="user_id", match=MatchValue(value=42)),
        ]
    ),
    limit=10,
)
```

### Hybrid Search in Qdrant

```python
# Sparse + dense fusion (Qdrant 1.10+)
client.search_batch(
    collection_name="docs",
    requests=[
        # dense vector
        SearchRequest(vector=("dense", dense_vec), limit=20),
        # sparse vector (BM25-like)
        SearchRequest(vector=("sparse", sparse_vec), limit=20),
    ],
)
# Then fuse with Reciprocal Rank Fusion (RRF)
```

---

## Weaviate — Hybrid Search Champion

### Why Weaviate

```
✓ Native hybrid (BM25 + vector + cross-encoder reranking)
✓ Multi-modal modules (CLIP for images, etc.)
✓ Built-in ML modules for embedding (no need to embed yourself)
✓ GraphQL API for complex queries
```

### Python Client

```python
import weaviate
from weaviate.classes.query import MetadataQuery, Filter

client = weaviate.connect_to_local()

collection = client.collections.get("Documents")

# Hybrid search — vector + BM25 in one call
results = collection.query.hybrid(
    query="explain transformers",
    alpha=0.5,  # 0 = pure BM25, 1 = pure vector
    filters=Filter.by_property("category").equal("AI"),
    limit=10,
    return_metadata=MetadataQuery(score=True),
)

for obj in results.objects:
    print(obj.properties, obj.metadata.score)
```

---

## Pinecone — Zero-Ops Choice

### Why Pinecone

```
✓ Managed — no servers, no scaling worries
✓ Excellent docs and SDK
✓ Reliable for prod (well-tested)
✓ Serverless pricing (since 2024)

✗ Vendor lock-in
✗ Cost scales hard at billion+ vectors
✗ No hybrid (need Elasticsearch on side)
✗ No joins with relational data
```

### Python Client

```python
from pinecone import Pinecone, ServerlessSpec

pc = Pinecone(api_key="...")
pc.create_index(
    name="docs",
    dimension=1536,
    metric="cosine",
    spec=ServerlessSpec(cloud="aws", region="us-east-1"),
)
index = pc.Index("docs")

# Upsert
index.upsert(vectors=[
    {"id": "1", "values": embedding, "metadata": {"category": "AI", "user_id": 42}},
])

# Search with filter
result = index.query(
    vector=query_embedding,
    top_k=10,
    filter={"category": {"$eq": "AI"}, "user_id": {"$eq": 42}},
    include_metadata=True,
)
```

---

## Milvus — For Billion+ Vectors

### When You'd Pick Milvus

```
✓ > 100M vectors
✓ Need to scale to billions
✓ Have K8s + ops team
✓ Need GPU acceleration

✗ Operational complexity (multiple components: proxy, query, data, etc.)
✗ Overkill for < 10M vectors
```

### Quick API

```python
from pymilvus import (
    Collection, FieldSchema, CollectionSchema, DataType, connections
)

connections.connect(host="localhost", port="19530")

fields = [
    FieldSchema(name="id", dtype=DataType.INT64, is_primary=True),
    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=1536),
    FieldSchema(name="category", dtype=DataType.VARCHAR, max_length=64),
]
schema = CollectionSchema(fields)
collection = Collection("docs", schema)

collection.create_index(
    field_name="embedding",
    index_params={"index_type": "HNSW", "metric_type": "COSINE", "params": {"M": 16, "efConstruction": 64}},
)

# Filter + search
collection.load()
results = collection.search(
    data=[query_embedding],
    anns_field="embedding",
    param={"metric_type": "COSINE", "params": {"ef": 64}},
    limit=10,
    expr='category == "AI"',
)
```

---

## Cost Comparison (Rough, 2026)

```
Workload: 10M vectors @ 1536 dims, 100 QPS, < 100ms p95

Pinecone serverless:     ~$150-300/month (small)
                         ~$1500-3000/month (scaled)

Self-hosted Qdrant:      ~$200-500/month (1-3 servers)
                         + DevOps time

Self-hosted pgvector:    Already paying for Postgres
                         (maybe larger instance)

Weaviate Cloud:          ~$200-1000/month
Milvus Cloud (Zilliz):   ~$300-1500/month

Self-hosted Milvus:      ~$500-2000/month (3-5 nodes)
                         + significant DevOps
```

→ Cost varies hugely by region, optimization, support tier.

---

## Common Patterns in Production

### Pattern 1: Hybrid pgvector + Qdrant

```
Postgres → source of truth (documents table)
pgvector → for queries that need JOIN with relational data
Qdrant   → for high-QPS pure vector search

Sync via Postgres trigger → outbox → Qdrant ingest worker
```

### Pattern 2: Multi-Tenant via Collections

```python
# Per-tenant collection (isolation, easier billing/quotas)
collection_name = f"tenant_{tenant_id}_docs"

# vs shared collection with filter (cheaper, harder to evict)
collection_name = "all_docs"
filter = {"tenant_id": tenant_id}

Rule of thumb:
   < 1000 tenants → per-tenant collection
   > 1000 tenants → shared with filter + payload index
```

### Pattern 3: Embedding Pipeline

```
Document → embed (OpenAI/Cohere/BAAI) → chunk → store

Best practices:
   ✓ Chunk size: 256-512 tokens
   ✓ Overlap: 20-50 tokens
   ✓ Store chunk_id + parent_id (for retrieval grouping)
   ✓ Idempotent: hash(content) → id (re-runs don't duplicate)
   ✓ Async via Celery/queue (embedding is slow + costly)
```

### Pattern 4: Re-ranking

```
ANN search → top 50 candidates
   ↓
Cross-encoder (BGE-reranker, Cohere rerank) → top 10
   ↓
LLM context

Why: ANN is fast but imprecise.
Re-ranker is slow but accurate.
Two-stage = best of both.
```

---

## Interview Questions & Answers

### Q1: Why is HNSW the default vector index?

**Answer:**

HNSW (Hierarchical Navigable Small World) builds a multi-layer graph where higher layers have fewer, longer-distance connections. Search starts at the top, navigates greedily down. Gives O(log N) search with high recall (95%+ for typical params). The main downside is RAM — entire index must fit in memory.

Alternatives:
- **IVF** (cluster + scan): less RAM, slower, lower recall
- **DiskANN**: handles billion+ on disk, slower

HNSW wins for 99% of < 1B vector workloads.

### Q2: How do you choose between pgvector and a dedicated vector DB?

**Answer:**

```
Stay on pgvector if:
   ✓ < 50M vectors
   ✓ Postgres expertise on team
   ✓ Need joins with relational data
   ✓ Want one DB to operate

Move to dedicated (Qdrant/Weaviate) if:
   ✓ > 50M vectors, sub-100ms p99
   ✓ Heavy filter operations
   ✓ Need hybrid search natively
   ✓ Multi-modal (images, audio)

Move to Pinecone if:
   ✓ No DevOps capacity
   ✓ Need to launch in days, not weeks

Move to Milvus if:
   ✓ Billion+ vectors, strong infra team
```

### Q3: What's the pre-filter vs post-filter problem?

**Answer:**

```
Vector DBs face: filter + ANN search.

Post-filter (naive):
   1. ANN finds 10 nearest by vector
   2. Apply filter on those 10
   ✗ If filter is selective (5% match), most results discarded
   ✗ User gets 0 results when filtered

Pre-filter (better but tricky):
   1. Find IDs matching filter
   2. ANN search restricted to those IDs
   ✗ ANN graphs don't naturally restrict to subset
   ✗ Need integrated index

Solution differs by DB:
   ✓ Qdrant: payload index + filterable HNSW
   ✓ Weaviate: filtered HNSW search
   ✓ pgvector: Postgres can't pre-filter HNSW well
                → workaround: lower vector candidate count
                  with WHERE then JOIN with vector results

Senior insight: this is THE differentiator for filter-heavy workloads.
```

### Q4: How do you handle vector DB schema evolution?

**Answer:**

```
Vectors are tied to the embedding model.

If you change embedding model:
   ✗ ALL existing vectors are now incompatible
   ✓ Re-embed entire corpus
   ✓ Run two indexes in parallel during migration
   ✓ Cut over reads after backfill

Best practices:
   ✓ Store model_version with each vector
   ✓ Query: WHERE model_version = current_version
   ✓ Async re-embedding job for old vectors
   ✓ Set TTL on old version vectors
```

### Q5: How do you scale vector search to 100M+ vectors?

**Answer:**

```
Strategies in priority order:

1. Reduce dimensions (MRL — Matryoshka)
   ✓ OpenAI 3-large can be truncated to 256/512/1024 dims
   ✓ Half-precision (float16) — 2x less RAM
   ✓ Product quantization (PQ) — 8-16x compression

2. Shard by domain
   ✓ Per-tenant collection
   ✓ Per-category collection
   ✓ Search subset, not entire 100M

3. Two-stage retrieval
   ✓ ANN finds 100 candidates (fast)
   ✓ Re-rank top 10 (slower but accurate)

4. Approximation knobs
   ✓ ef_search lower = faster but less recall
   ✓ Trade-off appropriate for use case

5. Caching
   ✓ Hot queries → semantic cache (Redis + similarity)
   ✓ Pre-compute embeddings for popular queries
```

### Q6: What's hybrid search and why is it important?

**Answer:**

Pure vector search misses keyword matches (e.g., product SKUs, person names). Pure BM25 misses semantic equivalents (e.g., "car" vs "automobile").

Hybrid combines both with score fusion:

```
RRF (Reciprocal Rank Fusion):
   score(doc) = 1/(60 + bm25_rank) + 1/(60 + vector_rank)

Other methods:
   ✓ Weighted sum (alpha × vector + (1-alpha) × bm25)
   ✓ Cross-encoder re-rank top-K of both
```

Native support: Weaviate, Qdrant 1.10+, Milvus 2.4+. DIY in pgvector.

### Q7: How do you secure vector data for multi-tenant?

**Answer:**

```
Option 1: Collection per tenant (best isolation)
   ✓ Easy to enforce, audit, quota, delete
   ✗ Scales poorly past ~10k tenants

Option 2: Shared collection + tenant_id payload + payload index
   ✓ Scales to millions of tenants
   ✓ Must add ALWAYS-applied filter: WHERE tenant_id = X
   ✗ Risk: one buggy code path → cross-tenant leak

Mitigations:
   ✓ Wrap client in TenantScopedClient that auto-adds filter
   ✓ Add row-level security analog (per-query token)
   ✓ Audit log every search with tenant context
```

### Q8: How do you debug a "search results are bad" complaint?

**Answer:**

Systematic checklist:

```
1. Embedding quality
   - Same model for query + corpus?
   - Truncation cutting query?
   - Model trained for the domain?

2. Chunking
   - Too big → too generic
   - Too small → loss of context
   - Try 256, 512, 1024 token chunks

3. Recall vs Precision
   - Increase ef_search / nprobe
   - Check recall@10 vs ground truth

4. Hybrid?
   - Pure vector failing on exact terms?
   - Add BM25 component

5. Re-ranking
   - Add cross-encoder for top 50 → 10
   - Often biggest single quality win

6. Distance metric
   - Cosine vs L2 vs dot product
   - Normalize vectors if using dot product

7. Filter interfering?
   - Selective filter + ANN can return junk
   - Increase candidate count before filter
```

---

## Production Pitfalls

```
1. ✗ Using cosine on unnormalized vectors
   → Wrong results
   ✓ Always normalize OR use proper metric

2. ✗ Embedding model mismatch
   → Search returns random results
   ✓ Pin model version, re-embed on change

3. ✗ Forgetting metadata indexes
   → Filtered search slow as full scan
   ✓ Index every filterable field

4. ✗ Single huge collection vs sharding
   → > 50M in one collection = pain
   ✓ Shard by tenant/domain/time

5. ✗ No re-ranking
   → Quality plateaus
   ✓ Cross-encoder for top 50

6. ✗ Synchronous embedding in API endpoint
   → Slow + costly
   ✓ Async via queue/worker

7. ✗ No semantic caching
   → Embedding same query 1000x
   ✓ Cache by query hash + similarity

8. ✗ Storing full text in vector DB
   → DB bloats
   ✓ Vector DB stores embedding + id only
   ✓ Postgres/S3 stores original text
```

---

## Operational Concerns

### Backups

```
pgvector:  pg_dump (everything in Postgres)
Pinecone:  index snapshots (managed)
Qdrant:    snapshot API → S3
Weaviate:  backup module → S3/GCS/Azure
Milvus:    backup tool (milvus-backup) → S3
```

### Monitoring Metrics

```
✓ Search QPS + latency p50/p95/p99
✓ Index size (RAM + disk)
✓ Recall@K (offline eval against ground truth)
✓ Insert throughput
✓ Replication lag (multi-node)
✓ Query timeouts / errors
```

### Schema Migrations

```
Adding fields:
   ✓ Most DBs support adding new payload/metadata online

Changing vector dim:
   ✗ Almost always means full re-index
   ✓ Run old + new in parallel, cut over reads

Changing distance metric:
   ✗ Requires full re-index
```

---

## Senior Mantras

```
1. Start with pgvector. Move only when it hurts.

2. Choose dedicated vector DB by FILTER complexity, not just scale.

3. Hybrid search beats pure vector for most real-world queries.

4. Re-ranking on top 50 candidates is the biggest single quality win.

5. Pin embedding model version. Changing it = full re-index.

6. Chunk size matters more than you think. Test 256/512/1024.

7. Normalize vectors. Always. (Unless explicitly using L2.)

8. Build semantic cache. Don't embed the same query 1000 times.

9. Two-stage retrieval is the standard pattern: ANN → re-rank.

10. Multi-tenant: collection-per-tenant for < 1k tenants.
    Filter + index for > 1k.
```

---

## Resources

```
✓ https://github.com/pgvector/pgvector
✓ https://qdrant.tech/documentation/
✓ https://weaviate.io/developers/weaviate
✓ https://docs.pinecone.io/
✓ https://milvus.io/docs
✓ https://github.com/run-llama/llama_index (high-level abstraction)
✓ https://www.pinecone.io/learn/ (best free vector DB tutorials)
✓ Cohere reranker — https://docs.cohere.com/docs/rerank
✓ BGE reranker — https://huggingface.co/BAAI/bge-reranker-v2-m3
```

---

## Related Topics

- [06_pgvector_schema_design.md](06_pgvector_schema_design.md) — pgvector deep
- [18_pgvector_ai_workloads.md](18_pgvector_ai_workloads.md) — production patterns
- [27_clickhouse_olap.md](27_clickhouse_olap.md) — analytics alternative
- [../Phase2_Caching/06_semantic_caching_llm.md](../Phase2_Caching/06_semantic_caching_llm.md) — semantic cache
- [../Phase2_FastAPI/34_rag_backend_architecture.md](../Phase2_FastAPI/34_rag_backend_architecture.md) — RAG impl
- [../Projects/08_FastAPI_OpenAI_RAG_Backend.md](../Projects/08_FastAPI_OpenAI_RAG_Backend.md) — full project
