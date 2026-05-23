"""
Redis Practical 04 — Vector Search & Semantic Cache
Run: python 04_vector_search_semantic_cache.py [index|search|semantic|rag|all]

Prerequisites:
  pip install redis[hiredis] sentence-transformers numpy
  docker run -d --name redis-stack -p 6379:6379 redis/redis-stack-server:latest
  (redis-stack required for RediSearch + Vector Search)

Note: First run will download sentence-transformers model (~90MB)
"""

import hashlib
import json
import sys
import time
import numpy as np
import redis

from redis.commands.search.field import (
    TextField, NumericField, VectorField, TagField
)
from redis.commands.search.indexDefinition import IndexDefinition, IndexType
from redis.commands.search.query import Query

# ─── Connection ───
r = redis.Redis(host='localhost', port=6379, decode_responses=False)
r_str = redis.Redis(host='localhost', port=6379, decode_responses=True)

# ─── Model ───
try:
    from sentence_transformers import SentenceTransformer
    print("⏳ Loading sentence-transformers model (all-MiniLM-L6-v2)...")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    VECTOR_DIM = 384
    print("✅ Model loaded!")
except ImportError:
    print("❌ sentence-transformers not installed!")
    print("   Run: pip install sentence-transformers numpy")
    sys.exit(1)


# ════════════════════════════════════════════
# SECTION 1: CREATE VECTOR SEARCH INDEX
# ════════════════════════════════════════════
def create_search_index(index_name: str = "docs_index", drop_if_exists: bool = True):
    """FT.CREATE — Vector Search index create karo"""
    if drop_if_exists:
        try:
            r.ft(index_name).dropindex()
            print(f"  Dropped existing index: {index_name}")
        except Exception:
            pass

    schema = [
        TextField("title"),                       # searchable title
        TextField("content"),                     # searchable content
        TagField("category"),                     # filter by category
        TagField("tags"),                         # filter by tags
        NumericField("created_at"),               # filter by date
        NumericField("view_count"),               # numeric filter
        VectorField(
            "embedding",
            "HNSW",                               # HNSW = fast approximate KNN
            {
                "TYPE":            "FLOAT32",
                "DIM":             VECTOR_DIM,
                "DISTANCE_METRIC": "COSINE",      # COSINE / L2 / IP
                "M":               16,            # HNSW: edges per node (higher = better quality)
                "EF_CONSTRUCTION": 200,           # HNSW: build accuracy (higher = slower build)
                "EF_RUNTIME":      10,            # HNSW: search accuracy
            }
        )
    ]

    r.ft(index_name).create_index(
        schema,
        definition=IndexDefinition(
            prefix=["doc:"],              # "doc:" se shuru hone wale keys index karo
            index_type=IndexType.HASH    # HASH ya JSON
        )
    )
    print(f"  ✅ Index '{index_name}' created (HNSW, COSINE, dim={VECTOR_DIM})")
    return index_name


def create_flat_index(index_name: str = "docs_flat_index"):
    """FLAT index — exact KNN (small datasets ke liye)"""
    try:
        r.ft(index_name).dropindex()
    except Exception:
        pass

    schema = [
        TextField("title"),
        TextField("content"),
        TagField("category"),
        VectorField(
            "embedding",
            "FLAT",                               # FLAT = exact (slower, accurate)
            {
                "TYPE":            "FLOAT32",
                "DIM":             VECTOR_DIM,
                "DISTANCE_METRIC": "COSINE",
            }
        )
    ]

    r.ft(index_name).create_index(
        schema,
        definition=IndexDefinition(prefix=["flat:"], index_type=IndexType.HASH)
    )
    print(f"  ✅ Flat index '{index_name}' created (exact KNN)")
    return index_name


# ════════════════════════════════════════════
# SECTION 2: STORE DOCUMENTS WITH EMBEDDINGS
# ════════════════════════════════════════════
def store_documents():
    """Documents + embeddings store karo"""
    documents = [
        {
            "id": "1", "title": "Python FastAPI Guide",
            "content": "FastAPI is a modern Python web framework for building REST APIs with automatic validation and docs",
            "category": "backend", "tags": "python|api|web", "view_count": 1500
        },
        {
            "id": "2", "title": "Redis Caching Patterns",
            "content": "Redis is an in-memory data store used for caching, session management and real-time features",
            "category": "database", "tags": "cache|redis|performance", "view_count": 1200
        },
        {
            "id": "3", "title": "LangChain RAG System",
            "content": "RAG combines document retrieval with language models for context-aware question answering",
            "category": "ai", "tags": "llm|rag|langchain|ai", "view_count": 2100
        },
        {
            "id": "4", "title": "Docker Container Guide",
            "content": "Docker containers provide isolated environments for deploying microservices applications",
            "category": "devops", "tags": "docker|container|deployment", "view_count": 900
        },
        {
            "id": "5", "title": "RabbitMQ Message Queue",
            "content": "RabbitMQ is a message broker enabling async communication between microservices",
            "category": "backend", "tags": "queue|messaging|async", "view_count": 800
        },
        {
            "id": "6", "title": "PostgreSQL Advanced Queries",
            "content": "PostgreSQL advanced features include CTEs, window functions, JSONB and full-text search",
            "category": "database", "tags": "sql|postgresql|database", "view_count": 1100
        },
        {
            "id": "7", "title": "Vector Embeddings for NLP",
            "content": "Word embeddings convert text to numerical vectors for machine learning and semantic similarity",
            "category": "ai", "tags": "nlp|embeddings|ml|ai", "view_count": 1800
        },
        {
            "id": "8", "title": "Kubernetes Orchestration",
            "content": "Kubernetes orchestrates containers across clusters for scalable and reliable deployments",
            "category": "devops", "tags": "k8s|kubernetes|orchestration", "view_count": 1400
        },
        {
            "id": "9", "title": "React Frontend Framework",
            "content": "React is a JavaScript library for building interactive user interfaces with component architecture",
            "category": "frontend", "tags": "react|javascript|ui", "view_count": 2500
        },
        {
            "id": "10", "title": "OpenAI GPT API Integration",
            "content": "GPT models from OpenAI can generate text, answer questions and perform reasoning tasks",
            "category": "ai", "tags": "gpt|openai|llm|ai", "view_count": 3000
        },
    ]

    print(f"\n📝 Storing {len(documents)} documents with embeddings...")

    # Batch embed (faster)
    contents = [doc["content"] for doc in documents]
    embeddings = model.encode(contents, batch_size=8, show_progress_bar=False)

    for doc, embedding in zip(documents, embeddings):
        r.hset(
            f"doc:{doc['id']}",
            mapping={
                "title":      doc["title"].encode(),
                "content":    doc["content"].encode(),
                "category":   doc["category"].encode(),
                "tags":       doc["tags"].encode(),
                "view_count": doc["view_count"],
                "created_at": int(time.time()),
                "embedding":  embedding.astype(np.float32).tobytes(),
            }
        )

    print(f"✅ {len(documents)} documents stored!")
    return documents


# ════════════════════════════════════════════
# SECTION 3: VECTOR SEARCH
# ════════════════════════════════════════════
def search_similar(
    query_text: str,
    top_k: int = 3,
    index_name: str = "docs_index",
    category_filter: str = None,
    min_views: int = None,
) -> list:
    """KNN Vector Search — most similar documents"""

    query_embedding = model.encode(query_text).astype(np.float32)

    # ─── Query build ───
    if category_filter and min_views:
        base_q = f"(@category:{{{category_filter}}} @view_count:[{min_views} +inf])=>[KNN {top_k} @embedding $vec AS score]"
    elif category_filter:
        base_q = f"(@category:{{{category_filter}}})=>[KNN {top_k} @embedding $vec AS score]"
    elif min_views:
        base_q = f"(@view_count:[{min_views} +inf])=>[KNN {top_k} @embedding $vec AS score]"
    else:
        base_q = f"*=>[KNN {top_k} @embedding $vec AS score]"

    query = (
        Query(base_q)
        .sort_by("score")                                         # ASC = most similar first (COSINE distance)
        .return_fields("title", "content", "category", "tags", "view_count", "score")
        .dialect(2)
    )

    results = r.ft(index_name).search(
        query,
        query_params={"vec": query_embedding.tobytes()}
    )

    return [
        {
            "id":         doc.id.decode() if isinstance(doc.id, bytes) else doc.id,
            "title":      doc.title.decode() if isinstance(doc.title, bytes) else doc.title,
            "content":    doc.content.decode() if isinstance(doc.content, bytes) else doc.content,
            "category":   doc.category.decode() if isinstance(doc.category, bytes) else doc.category,
            "score":      float(doc.score),        # COSINE distance: 0=identical, 1=opposite
            "similarity": round(1 - float(doc.score), 4)  # 1=identical, 0=opposite
        }
        for doc in results.docs
    ]


def demo_vector_search():
    print("\n" + "="*50)
    print("  SECTION 3: VECTOR SEARCH")
    print("="*50)

    # Index create + documents store
    create_search_index("docs_index")
    store_documents()
    time.sleep(0.2)  # Index build ke liye wait

    # ─── Basic searches ───
    searches = [
        ("how to build REST API with Python", None),
        ("machine learning and neural networks", None),
        ("message queue async microservices", None),
        ("database caching performance optimization", None),
        ("AI text generation language model", None),
    ]

    print("\n🔍 Vector Search Results:")
    for query, category in searches:
        print(f"\n  Query: '{query}'")
        results = search_similar(query, top_k=3, category_filter=category)
        for i, doc in enumerate(results, 1):
            bar = "█" * int(doc["similarity"] * 20)
            print(f"    {i}. [{bar:<20}] {doc['similarity']:.4f} | {doc['title']} [{doc['category']}]")

    # ─── Filtered search ───
    print("\n🔍 Filtered Search (category=ai only):")
    ai_results = search_similar("question answering", top_k=3, category_filter="ai")
    for doc in ai_results:
        print(f"  [{doc['similarity']:.4f}] {doc['title']} [{doc['category']}]")

    # ─── High view count filter ───
    print("\n🔍 Popular Articles (view_count >= 1500) + AI query:")
    popular_results = search_similar("artificial intelligence", top_k=5, min_views=1500)
    for doc in popular_results:
        print(f"  [{doc['similarity']:.4f}] {doc['title']} (views: check DB)")

    # ─── FLAT index comparison ───
    print("\n📊 HNSW vs FLAT comparison:")

    # Seed flat index
    create_flat_index()
    documents = store_documents()  # Already embedded above, just restoring

    # Actually store in flat: prefix
    contents = [doc["content"] for doc in documents]
    embeddings = model.encode(contents, batch_size=8, show_progress_bar=False)
    for doc, emb in zip(documents, embeddings):
        r.hset(f"flat:{doc['id']}", mapping={
            "title":    doc["title"].encode(),
            "content":  doc["content"].encode(),
            "category": doc["category"].encode(),
            "embedding": emb.astype(np.float32).tobytes(),
        })

    query_text = "web framework API development"
    query_vec = model.encode(query_text).astype(np.float32)

    # HNSW search time
    start = time.time()
    for _ in range(10):
        search_similar(query_text, top_k=3, index_name="docs_index")
    hnsw_time = (time.time() - start) / 10

    # FLAT search time
    flat_q = Query(f"*=>[KNN 3 @embedding $vec AS score]").sort_by("score").return_fields("title", "score").dialect(2)
    start = time.time()
    for _ in range(10):
        r.ft("docs_flat_index").search(flat_q, query_params={"vec": query_vec.tobytes()})
    flat_time = (time.time() - start) / 10

    print(f"  HNSW (approx, 10 runs avg): {hnsw_time*1000:.2f}ms")
    print(f"  FLAT (exact, 10 runs avg):  {flat_time*1000:.2f}ms")
    print(f"  HNSW is faster on large datasets, FLAT more accurate on small ones")

    print("\n✅ Vector Search demo complete!")


# ════════════════════════════════════════════
# SECTION 4: SEMANTIC CACHE
# ════════════════════════════════════════════
SEMANTIC_CACHE_INDEX = "semantic_cache"
SIMILARITY_THRESHOLD = 0.15    # < 0.15 COSINE distance = similar queries


def setup_semantic_cache():
    """Semantic cache index create karo"""
    try:
        r.ft(SEMANTIC_CACHE_INDEX).dropindex()
    except Exception:
        pass

    r.ft(SEMANTIC_CACHE_INDEX).create_index(
        [
            VectorField("embedding", "HNSW", {
                "TYPE":            "FLOAT32",
                "DIM":             VECTOR_DIM,
                "DISTANCE_METRIC": "COSINE"
            })
        ],
        definition=IndexDefinition(prefix=["scache:"], index_type=IndexType.HASH)
    )
    print("  ✅ Semantic cache index created")


def semantic_cache_get(query: str) -> str | None:
    """Cache mein similar query dhundo"""
    embedding = model.encode(query).astype(np.float32)

    search_q = (
        Query("*=>[KNN 1 @embedding $vec AS score]")
        .return_fields("response", "original_query", "score")
        .dialect(2)
    )

    results = r.ft(SEMANTIC_CACHE_INDEX).search(
        search_q,
        query_params={"vec": embedding.tobytes()}
    )

    if results.total > 0:
        top = results.docs[0]
        dist = float(top.score)

        if dist < SIMILARITY_THRESHOLD:
            orig = top.original_query
            if isinstance(orig, bytes):
                orig = orig.decode()
            resp = top.response
            if isinstance(resp, bytes):
                resp = resp.decode()
            return resp, orig, dist

    return None, None, None


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
            "created_at":     str(int(time.time())).encode(),
        }
    )
    r.expire(f"scache:{cache_id}", ttl)


class LLMWithSemanticCache:
    """LLM simulator with semantic caching"""

    def __init__(self):
        self.call_count = 0
        self.cache_hits = 0
        self.total_cost = 0.0

    def call_llm(self, query: str) -> str:
        """LLM API call (simulate)"""
        self.call_count += 1
        time.sleep(0.05)   # API latency simulate

        # Simulated responses
        responses = {
            "python": "Python is a high-level programming language known for simplicity and readability.",
            "fastapi": "FastAPI is a modern Python web framework for building APIs with high performance.",
            "redis": "Redis is an in-memory data structure store used as database, cache, and message broker.",
            "docker": "Docker is a platform for developing, shipping and running applications in containers.",
            "default": f"AI-generated response for: {query}"
        }

        for keyword, response in responses.items():
            if keyword in query.lower():
                return response
        return responses["default"]

    def query(self, user_query: str) -> dict:
        """Query with semantic cache check"""
        # Step 1: Cache check
        cached_response, original_query, distance = semantic_cache_get(user_query)

        if cached_response:
            self.cache_hits += 1
            return {
                "response":       cached_response,
                "source":         "cache",
                "distance":       round(distance, 4),
                "original_query": original_query,
                "cost":           0.0,
            }

        # Step 2: LLM call
        response = self.call_llm(user_query)
        self.total_cost += 0.01  # $0.01 per call

        # Step 3: Cache store
        semantic_cache_set(user_query, response)

        return {
            "response": response,
            "source":   "llm",
            "cost":     0.01,
        }

    def stats(self) -> dict:
        return {
            "total_queries": self.call_count + self.cache_hits,
            "llm_calls":     self.call_count,
            "cache_hits":    self.cache_hits,
            "cache_rate":    f"{self.cache_hits / (self.call_count + self.cache_hits) * 100:.0f}%",
            "total_cost":    f"${self.total_cost:.2f}",
            "saved_cost":    f"${self.cache_hits * 0.01:.2f}",
        }


def demo_semantic_cache():
    print("\n" + "="*50)
    print("  SECTION 4: SEMANTIC CACHE")
    print("="*50)

    setup_semantic_cache()
    llm = LLMWithSemanticCache()

    queries = [
        # Group 1: Python related (similar)
        "What is Python programming?",
        "Tell me about Python language",        # Should hit cache
        "Explain Python programming language",  # Should hit cache
        "Describe Python",                      # Should hit cache

        # Group 2: FastAPI related (similar)
        "What is FastAPI?",
        "Explain FastAPI framework",            # Should hit cache
        "How does FastAPI work?",               # Should hit cache

        # Group 3: Redis related (different group)
        "What is Redis database?",
        "Tell me about Redis caching",          # Should hit cache

        # Group 4: Completely different
        "What is Docker container?",
        "How to use Kubernetes?",               # Different enough → miss
    ]

    print(f"\n🤖 Querying LLM with Semantic Cache (threshold={SIMILARITY_THRESHOLD}):")
    print(f"{'Query':<45} {'Source':<8} {'Cost':<8} {'Distance':<10} {'Matched'}")
    print("-" * 90)

    for query in queries:
        result = llm.query(query)
        source  = result["source"]
        cost    = f"${result['cost']:.2f}"
        dist    = f"{result.get('distance', '-')}"
        matched = result.get("original_query", "")[:30] if source == "cache" else ""
        icon    = "🎯" if source == "cache" else "📡"
        print(f"  {icon} {query[:43]:<43} {source:<8} {cost:<8} {dist:<10} {matched}")

    print("\n📊 Cache Statistics:")
    stats = llm.stats()
    for k, v in stats.items():
        print(f"  {k}: {v}")

    # ─── Threshold demo ───
    print("\n🎚️  Similarity Threshold Impact:")
    test_pairs = [
        ("What is Python?", "What is Python?"),          # Identical
        ("What is Python?", "Explain Python language"),  # Very similar
        ("What is Python?", "Tell me about FastAPI"),    # Different
        ("What is Python?", "What is Java?"),            # Close but different
    ]

    for q1, q2 in test_pairs:
        emb1 = model.encode(q1).astype(np.float32)
        emb2 = model.encode(q2).astype(np.float32)

        # Cosine distance
        cos_sim = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
        cos_dist = 1 - cos_sim

        would_hit = cos_dist < SIMILARITY_THRESHOLD
        print(f"  [{cos_dist:.4f}] {'✅ HIT ' if would_hit else '❌ MISS'} | '{q1[:25]}' vs '{q2[:25]}'")

    print("\n✅ Semantic Cache demo complete!")


# ════════════════════════════════════════════
# SECTION 5: MINI RAG PIPELINE
# ════════════════════════════════════════════
def demo_mini_rag():
    print("\n" + "="*50)
    print("  SECTION 5: MINI RAG PIPELINE")
    print("="*50)

    print("""
  RAG Architecture:
  ┌─────────┐    ┌──────────┐    ┌─────────────┐    ┌─────────┐
  │ Question │───▶│  Embed   │───▶│ Redis Vector│───▶│ Context │
  └─────────┘    └──────────┘    │   Search    │    └────┬────┘
                                  └─────────────┘         │
  ┌──────────┐                                      ┌─────▼────┐
  │  Answer  │◀──────────────────────────────────── │   LLM    │
  └──────────┘                                      └──────────┘
    """)

    # Ensure index exists
    try:
        r.ft("docs_index").info()
    except Exception:
        create_search_index("docs_index")
        store_documents()
        time.sleep(0.2)

    def retrieve_context(question: str, top_k: int = 3) -> list:
        """Step 1: Question ke relevant documents retrieve karo"""
        results = search_similar(question, top_k=top_k)
        return results

    def generate_answer(question: str, context: list) -> str:
        """Step 2: Context + question → LLM answer (simulated)"""
        context_text = "\n".join([f"- {doc['title']}: {doc['content'][:100]}" for doc in context])
        # Real mein: OpenAI/Claude API call
        return f"Based on retrieved docs:\n{context_text}\n→ Answer to '{question}'"

    def rag_query(question: str, use_cache: bool = True) -> dict:
        """Full RAG pipeline with semantic cache"""

        # Check semantic cache first
        if use_cache:
            cached, original, dist = semantic_cache_get(question)
            if cached:
                return {
                    "answer":  cached,
                    "source":  "semantic_cache",
                    "distance": dist,
                    "cost":    0.0
                }

        # Retrieve relevant documents
        docs = retrieve_context(question, top_k=3)

        # Generate answer (LLM call)
        answer = generate_answer(question, docs)

        # Cache the result
        if use_cache:
            semantic_cache_set(question, answer, ttl=3600)

        return {
            "answer":   answer,
            "source":   "llm",
            "docs":     [{"title": d["title"], "similarity": d["similarity"]} for d in docs],
            "cost":     0.01,
        }

    # ─── RAG queries ───
    rag_questions = [
        "How do I build a REST API in Python?",
        "What tools can I use for AI question answering?",
        "How to cache API responses for performance?",
        "How do I build a REST API?",       # Cache hit!
        "What's good for AI chatbot systems?",  # Cache hit (similar to Q2)!
    ]

    print("🔍 RAG Queries:")
    for q in rag_questions:
        result = rag_query(q)
        source = result["source"]
        icon = "🎯" if source == "semantic_cache" else "📡"
        print(f"\n  {icon} Q: {q}")
        print(f"     Source: {source} | Cost: ${result['cost']:.2f}", end="")
        if source == "semantic_cache":
            print(f" | Distance: {result.get('distance', 0):.4f}")
        else:
            print()
            if "docs" in result:
                print(f"     Retrieved: {[d['title'] for d in result['docs']]}")

    # Cleanup
    for key in r_str.scan_iter("doc:*"):
        r_str.delete(key)
    for key in r_str.scan_iter("flat:*"):
        r_str.delete(key)
    for key in r_str.scan_iter("scache:*"):
        r_str.delete(key)
    try:
        r.ft("docs_index").dropindex()
        r.ft("docs_flat_index").dropindex()
        r.ft(SEMANTIC_CACHE_INDEX).dropindex()
    except Exception:
        pass

    print("\n✅ Mini RAG demo complete!")


# ════════════════════════════════════════════
# MAIN RUNNER
# ════════════════════════════════════════════
def main():
    try:
        r.ping()
        print("✅ Redis connected!")
    except redis.ConnectionError:
        print("❌ Redis not running!")
        print("   Run: docker run -d -p 6379:6379 redis/redis-stack-server:latest")
        sys.exit(1)

    # Check redis-stack (RediSearch needed)
    try:
        r.execute_command("FT._LIST")
    except Exception:
        print("⚠️  RediSearch module not found!")
        print("   Run: docker run -d -p 6379:6379 redis/redis-stack-server:latest")
        sys.exit(1)

    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"

    demos = {
        "index":    lambda: (create_search_index(), store_documents()),
        "search":   demo_vector_search,
        "semantic": demo_semantic_cache,
        "rag":      demo_mini_rag,
    }

    if cmd == "all":
        demo_vector_search()
        demo_semantic_cache()
        demo_mini_rag()
    elif cmd in demos:
        demos[cmd]()
    else:
        print(f"Usage: python {sys.argv[0]} [{'|'.join(demos.keys())}|all]")


if __name__ == "__main__":
    main()
