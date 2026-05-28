# Redis — Vector Search (AI) & FastAPI Production Patterns
**Advanced Level | What, Why, How**

---

## Quick Concepts
- **Redis Vector Search** = Embeddings store + similarity search — RAG ke liye
- **FT.CREATE** = Search index create karo (text + vector fields)
- **KNN** = K-Nearest Neighbors — most similar vectors find karo
- **HNSW** = Hierarchical Navigable Small World — approximate KNN (fast)
- **FLAT** = Exact KNN search (slow but accurate — small datasets)
- **Semantic Caching** = Same meaning ke queries → cache hit
- **Vector Distance** = COSINE / L2 / IP (Inner Product)

---

## Interview Questions & Answers

---

### Q1: Redis Vector Search kya hai? RAG mein kaise use karo?

**Answer:**
```
RAG Pipeline:
  Document → Chunk → Embed (OpenAI/HuggingFace) → Store in Vector DB
  Query → Embed → Search similar vectors → Context → LLM → Answer

Redis as Vector DB:
  ✅ Already Redis use kar rahe ho → extra DB nahi
  ✅ Sub-millisecond search
  ✅ Filter + Vector search combine karo
  ✅ JSON fields ke saath store karo
  ✅ Production-ready scaling

When Redis Vector vs Pinecone/Qdrant:
  Redis  → Already in stack, < 1M vectors, simple queries
  Pinecone → Managed, very large scale, no Redis
  Qdrant → Open-source, rich filtering, large scale
```

```python
# pip install redis[hiredis] sentence-transformers numpy
# Docker: docker run -d -p 6379:6379 redis/redis-stack-server:latest

import redis
import numpy as np
import json
from typing import List

r = redis.Redis(host='localhost', port=6379, decode_responses=False)  # bytes for vectors

# ─── Step 1: Search Index Create karo ───
from redis.commands.search.field import (
    TextField, NumericField, VectorField, TagField
)
from redis.commands.search.indexDefinition import IndexDefinition, IndexType

VECTOR_DIM = 384   # sentence-transformers all-MiniLM-L6-v2 dimension

try:
    r.ft("docs_index").dropindex()  # old index delete
except Exception:
    pass

# Index schema define karo
schema = [
    TextField("content"),                      # full-text searchable
    TextField("title"),                        # document title
    TagField("category"),                      # filter by category
    NumericField("created_at"),                # filter by date
    VectorField(
        "embedding",
        "HNSW",                                # algorithm: HNSW (fast) or FLAT (exact)
        {
            "TYPE":            "FLOAT32",
            "DIM":             VECTOR_DIM,
            "DISTANCE_METRIC": "COSINE",       # COSINE / L2 / IP
            "M":               16,             # HNSW: neighbors per node
            "EF_CONSTRUCTION": 200,            # HNSW: build accuracy
        }
    )
]

r.ft("docs_index").create_index(
    schema,
    definition=IndexDefinition(
        prefix=["doc:"],                       # "doc:" prefix wale keys index karo
        index_type=IndexType.HASH
    )
)
print("✅ Vector index created!")


# ─── Step 2: Documents + Embeddings store karo ───
from sentence_transformers import SentenceTransformer  # pip install sentence-transformers

model = SentenceTransformer("all-MiniLM-L6-v2")

documents = [
    {"id": "1", "title": "Python FastAPI Guide",
     "content": "FastAPI is a modern Python web framework for building APIs",
     "category": "backend"},
    {"id": "2", "title": "Redis Caching Tutorial",
     "content": "Redis is an in-memory data store used for caching and messaging",
     "category": "database"},
    {"id": "3", "title": "LangChain RAG System",
     "content": "RAG combines retrieval with language models for better responses",
     "category": "ai"},
    {"id": "4", "title": "Docker Container Guide",
     "content": "Docker containers provide isolated environments for applications",
     "category": "devops"},
    {"id": "5", "title": "RabbitMQ Message Queue",
     "content": "RabbitMQ is a message broker for async communication between services",
     "category": "backend"},
]

# Embeddings generate karo aur store karo
for doc in documents:
    embedding = model.encode(doc["content"]).astype(np.float32)

    r.hset(
        f"doc:{doc['id']}",
        mapping={
            "title":     doc["title"],
            "content":   doc["content"],
            "category":  doc["category"],
            "embedding": embedding.tobytes(),  # bytes format
            "created_at": 1705000000
        }
    )
print(f"✅ {len(documents)} documents stored with embeddings!")


# ─── Step 3: Vector Search karo ───
from redis.commands.search.query import Query

def search_similar(query_text: str, top_k: int = 3, category_filter: str = None):
    """Semantic search — most similar documents find karo"""
    # Query embed karo
    query_embedding = model.encode(query_text).astype(np.float32)

    # Search query build karo
    if category_filter:
        # Filter + Vector search combine
        base_query = f"(@category:{{{category_filter}}})=>[KNN {top_k} @embedding $vec AS score]"
    else:
        base_query = f"*=>[KNN {top_k} @embedding $vec AS score]"

    query = (
        Query(base_query)
        .sort_by("score")           # score ASC = most similar pehle (COSINE distance)
        .return_fields("title", "content", "category", "score")
        .dialect(2)
    )

    results = r.ft("docs_index").search(
        query,
        query_params={"vec": query_embedding.tobytes()}
    )

    return [
        {
            "id":       doc.id,
            "title":    doc.title,
            "content":  doc.content,
            "category": doc.category,
            "score":    float(doc.score)  # lower = more similar (cosine distance)
        }
        for doc in results.docs
    ]

# Test searches
print("\n--- Search: 'how to build REST API' ---")
results = search_similar("how to build REST API", top_k=3)
for r_item in results:
    print(f"  [{r_item['score']:.4f}] {r_item['title']}")

print("\n--- Search: 'caching for performance' ---")
results = search_similar("caching for performance", top_k=3)
for r_item in results:
    print(f"  [{r_item['score']:.4f}] {r_item['title']}")

print("\n--- Search: 'AI systems' (backend only) ---")
results = search_similar("AI systems", top_k=3, category_filter="backend")
for r_item in results:
    print(f"  [{r_item['score']:.4f}] {r_item['title']} [{r_item['category']}]")
```

---

### Q2: Semantic Caching — LLM costs kaise kam karo?

**Answer:**
```
Problem:
  User asks: "What is Python?"
  LLM call → $0.01 cost

  User asks: "Explain Python programming language"
  Similar question! Lekin exact match nahi → another LLM call → $0.01

Semantic Cache:
  Similar questions → same vector space → cache hit!
  Cost saved: ~40-60% on similar queries
```

```python
import redis
import numpy as np
from sentence_transformers import SentenceTransformer
import hashlib, json, time

r = redis.Redis(host='localhost', port=6379, decode_responses=False)
model = SentenceTransformer("all-MiniLM-L6-v2")

# Semantic cache index create karo
from redis.commands.search.field import VectorField
from redis.commands.search.indexDefinition import IndexDefinition, IndexType

try:
    r.ft("semantic_cache").dropindex()
except Exception:
    pass

r.ft("semantic_cache").create_index(
    [VectorField("embedding", "HNSW", {
        "TYPE": "FLOAT32", "DIM": 384, "DISTANCE_METRIC": "COSINE"
    })],
    definition=IndexDefinition(prefix=["scache:"], index_type=IndexType.HASH)
)

SIMILARITY_THRESHOLD = 0.15   # 0 = exact, 1 = completely different
                               # < 0.15 = similar enough to use cache

def semantic_cache_get(query: str) -> str | None:
    """Cache mein similar query dhundo"""
    embedding = model.encode(query).astype(np.float32)

    from redis.commands.search.query import Query
    search_query = (
        Query("*=>[KNN 1 @embedding $vec AS score]")
        .return_fields("response", "original_query", "score")
        .dialect(2)
    )
    results = r.ft("semantic_cache").search(
        search_query,
        query_params={"vec": embedding.tobytes()}
    )

    if results.total > 0:
        top = results.docs[0]
        similarity_distance = float(top.score)
        if similarity_distance < SIMILARITY_THRESHOLD:
            original = top.original_query.decode() if isinstance(top.original_query, bytes) else top.original_query
            response = top.response.decode() if isinstance(top.response, bytes) else top.response
            print(f"  🎯 Cache HIT! (distance={similarity_distance:.4f})")
            print(f"     Original: '{original}'")
            return response

    print(f"  ❌ Cache MISS")
    return None


def semantic_cache_set(query: str, response: str, ttl: int = 3600):
    """Cache mein store karo"""
    embedding = model.encode(query).astype(np.float32)
    cache_id = hashlib.md5(query.encode()).hexdigest()[:16]

    r.hset(
        f"scache:{cache_id}",
        mapping={
            "original_query": query.encode(),
            "response":       response.encode(),
            "embedding":      embedding.tobytes(),
            "created_at":     str(int(time.time()))
        }
    )
    r.expire(f"scache:{cache_id}", ttl)


def llm_with_semantic_cache(query: str) -> dict:
    """LLM call + semantic cache"""
    # Cache check
    cached = semantic_cache_get(query)
    if cached:
        return {"response": cached, "source": "cache", "cost": 0}

    # LLM call simulate (real mein OpenAI/Claude)
    print(f"  📡 LLM call for: '{query}'")
    time.sleep(0.1)  # simulate API latency
    response = f"AI response for: {query}"

    # Cache store
    semantic_cache_set(query, response)
    return {"response": response, "source": "llm", "cost": 0.01}


# Test
queries = [
    "What is Python?",
    "Tell me about Python programming",    # Similar → cache hit
    "Explain Python language",             # Similar → cache hit
    "How does FastAPI work?",              # Different → cache miss
    "What is FastAPI framework?",          # Similar → cache hit
]

print("=== Semantic Cache Demo ===\n")
total_cost = 0
for q in queries:
    print(f"Query: '{q}'")
    result = llm_with_semantic_cache(q)
    total_cost += result["cost"]
    print(f"  Source: {result['source']}, Cost: ${result['cost']}")
    print()

print(f"Total cost: ${total_cost:.2f} (vs ${len(queries) * 0.01:.2f} without cache)")
```

---

### Q3: Redis FastAPI — Complete Production Pattern

**Answer:**
```python
# Complete production-ready FastAPI + Redis setup

import asyncio
import json
import hashlib
from contextlib import asynccontextmanager
from functools import wraps
from typing import Any, Callable, Optional
import redis.asyncio as aioredis
from fastapi import FastAPI, Depends, Request, HTTPException
from pydantic import BaseModel


# ─── Redis Manager ───
class RedisManager:
    def __init__(self, url: str = "redis://localhost:6379"):
        self.url = url
        self.pool: Optional[aioredis.ConnectionPool] = None
        self.client: Optional[aioredis.Redis] = None

    async def connect(self):
        self.pool = aioredis.ConnectionPool.from_url(
            self.url,
            max_connections=50,
            decode_responses=True
        )
        self.client = aioredis.Redis(connection_pool=self.pool)
        await self.client.ping()

    async def disconnect(self):
        if self.client:
            await self.client.aclose()
        if self.pool:
            await self.pool.aclose()

    async def get(self, key: str) -> Any:
        val = await self.client.get(key)
        if val:
            try:
                return json.loads(val)
            except Exception:
                return val

    async def set(self, key: str, value: Any, ttl: int = 3600):
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        await self.client.setex(key, ttl, value)

    async def delete(self, *keys: str):
        if keys:
            await self.client.delete(*keys)

    async def delete_pattern(self, pattern: str):
        async for key in self.client.scan_iter(pattern):
            await self.client.delete(key)


redis_manager = RedisManager()


# ─── Cache Decorator ───
def cache(key_prefix: str, ttl: int = 300):
    """Endpoint result cache karo"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Cache key build karo
            cache_key = f"{key_prefix}:{hashlib.md5(str(kwargs).encode()).hexdigest()[:8]}"

            # Cache check
            cached = await redis_manager.get(cache_key)
            if cached:
                return {**cached, "_cached": True}

            # Function call karo
            result = await func(*args, **kwargs)

            # Cache store karo
            await redis_manager.set(cache_key, result, ttl)
            return result
        return wrapper
    return decorator


# ─── Rate Limiter ───
async def rate_limit(user_id: str, limit: int = 100, window: int = 60) -> bool:
    key = f"rate:{user_id}:{int(asyncio.get_event_loop().time() // window)}"
    count = await redis_manager.client.incr(key)
    if count == 1:
        await redis_manager.client.expire(key, window)
    return count <= limit


# ─── FastAPI App ───
@asynccontextmanager
async def lifespan(app: FastAPI):
    await redis_manager.connect()
    app.state.redis = redis_manager
    yield
    await redis_manager.disconnect()


app = FastAPI(lifespan=lifespan)


class Product(BaseModel):
    name: str
    price: float
    category: str


async def get_redis(request: Request) -> RedisManager:
    return request.app.state.redis


@app.get("/products/{product_id}")
@cache(key_prefix="product", ttl=600)
async def get_product(product_id: int, redis: RedisManager = Depends(get_redis)):
    """Product fetch + cache"""
    # Simulate DB call
    await asyncio.sleep(0.05)
    return {"id": product_id, "name": f"Product {product_id}", "price": 999.0}


@app.post("/products/{product_id}")
async def update_product(
    product_id: int,
    product: Product,
    redis: RedisManager = Depends(get_redis)
):
    """Product update + cache invalidate"""
    # DB update (simulate)
    await asyncio.sleep(0.05)

    # Cache invalidate karo
    await redis.delete_pattern(f"product:*")
    return {"id": product_id, **product.model_dump(), "updated": True}


@app.get("/search")
async def search_products(q: str, redis: RedisManager = Depends(get_redis)):
    """Search with rate limiting"""
    user_id = "anonymous"   # real mein auth se lo

    if not await rate_limit(user_id, limit=20, window=60):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    # Search logic (DB ya Elasticsearch)
    results = [{"id": i, "name": f"{q} result {i}"} for i in range(3)]
    return {"query": q, "results": results}
```

---

## Summary Table

```
┌───────────────────────────────────────────────────────────────────┐
│ Topic            │ Module       │ Commands / Pattern               │
├───────────────────────────────────────────────────────────────────┤
│ Vector Search    │ redis-stack  │ FT.CREATE, FT.SEARCH + KNN       │
│ Semantic Cache   │ redis-stack  │ Vector + threshold check          │
│ Connection Pool  │ redis-py     │ ConnectionPool, max_connections   │
│ Pipeline         │ redis-py     │ pipe = r.pipeline(), pipe.execute │
│ Cache Decorator  │ redis-py     │ @cache(key_prefix, ttl)           │
│ Rate Limiting    │ redis-py     │ INCR + EXPIRE per window          │
│ Session Store    │ redis-py     │ SETEX session:id + cookie         │
└───────────────────────────────────────────────────────────────────┘
```
