"""
Hybrid search — pgvector cosine + Postgres BM25 fused with Reciprocal Rank
Fusion (RRF), then Cohere rerank. Implemented Week 2 (D1-D3).

The reference SQL below is the target shape; the Python wrapper is a stub for now.
"""

# Reference SQL (Week 2 D3). Bound params: :query_embedding, :tenant_id, :query, :top_k
HYBRID_SEARCH_SQL = """
WITH vector_search AS (
    SELECT id, content, metadata,
           1 - (embedding <=> :query_embedding) AS vector_score
    FROM chunks
    WHERE tenant_id = :tenant_id
      AND embedding <=> :query_embedding < 0.4
    ORDER BY embedding <=> :query_embedding
    LIMIT 20
),
text_search AS (
    SELECT id, content, metadata,
           ts_rank(to_tsvector('english', content), plainto_tsquery(:query)) AS text_score
    FROM chunks
    WHERE tenant_id = :tenant_id
      AND to_tsvector('english', content) @@ plainto_tsquery(:query)
    LIMIT 20
),
rrf AS (
    SELECT
        COALESCE(v.id, t.id) AS id,
        COALESCE(v.content, t.content) AS content,
        COALESCE(v.metadata, t.metadata) AS metadata,
        COALESCE(1.0 / (60 + ROW_NUMBER() OVER (ORDER BY v.vector_score DESC NULLS LAST)), 0)
        + COALESCE(1.0 / (60 + ROW_NUMBER() OVER (ORDER BY t.text_score DESC NULLS LAST)), 0)
        AS rrf_score
    FROM vector_search v
    FULL OUTER JOIN text_search t ON v.id = t.id
)
SELECT id, content, metadata, rrf_score
FROM rrf
ORDER BY rrf_score DESC
LIMIT :top_k;
"""


async def hybrid_search(tenant_id: str, query_embedding, query: str, top_k: int = 5):
    """
    TODO (Week 2):
      1. run HYBRID_SEARCH_SQL to fetch ~20 RRF candidates
      2. Cohere rerank candidates -> keep top_k
      3. return [{id, content, metadata, score}]
    """
    raise NotImplementedError("hybrid_search lands Week 2 D1-D3")
