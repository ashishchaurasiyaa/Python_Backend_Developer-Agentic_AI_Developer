"""
============================================================
SEMANTIC CACHING FOR LLMs — Practical
============================================================
Builds a semantic cache from scratch:
1. Embedding (real OpenAI or fake/random)
2. Cosine similarity
3. In-memory + Redis-backed implementations
4. Threshold tuning
5. Hybrid (exact + semantic)
6. Integration with FastAPI / LangChain reference
"""
from __future__ import annotations
import hashlib
import math
import time
from dataclasses import dataclass, field


# ============================================================
# 1. EMBEDDING (real or mocked)
# ============================================================
def fake_embed(text: str, dim: int = 64) -> list[float]:
    """Simple bag-of-words style embedding for demo.
    Production: use OpenAI ada-002, sentence-transformers, etc."""
    import random
    rng = random.Random(hashlib.md5(text.lower().encode()).digest())
    # Add some signal: words contribute to dimensions
    vec = [rng.gauss(0, 1) for _ in range(dim)]
    for word in text.lower().split():
        h = int(hashlib.md5(word.encode()).hexdigest(), 16)
        vec[h % dim] += 1.0
    # Normalize
    norm = math.sqrt(sum(v * v for v in vec))
    return [v / norm for v in vec] if norm > 0 else vec


REAL_OPENAI_EMBED = """
from openai import OpenAI
client = OpenAI()

def embed(text: str) -> list[float]:
    resp = client.embeddings.create(
        model="text-embedding-3-small",   # 1536-dim, $0.02/1M tokens
        input=text,
    )
    return resp.data[0].embedding
"""


# ============================================================
# 2. COSINE SIMILARITY
# ============================================================
def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    return dot / (norm_a * norm_b) if norm_a * norm_b > 0 else 0


# ============================================================
# 3. IN-MEMORY SEMANTIC CACHE
# ============================================================
@dataclass
class CacheEntry:
    prompt: str
    response: str
    embedding: list[float]
    created_at: float = field(default_factory=time.time)
    hit_count: int = 0


class SemanticCache:
    def __init__(self, threshold: float = 0.95, ttl: float = 86400):
        self.threshold = threshold
        self.ttl = ttl
        self.entries: list[CacheEntry] = []
        self.hits = 0
        self.misses = 0

    def get(self, prompt: str) -> tuple[str | None, float, str | None]:
        """Returns (response, similarity, matched_prompt)."""
        emb = fake_embed(prompt)
        best_sim = 0
        best_entry = None
        now = time.time()

        for entry in self.entries:
            if now - entry.created_at > self.ttl:
                continue
            sim = cosine_similarity(emb, entry.embedding)
            if sim > best_sim:
                best_sim = sim
                best_entry = entry

        if best_entry and best_sim >= self.threshold:
            best_entry.hit_count += 1
            self.hits += 1
            return best_entry.response, best_sim, best_entry.prompt

        self.misses += 1
        return None, best_sim, None

    def put(self, prompt: str, response: str):
        self.entries.append(CacheEntry(
            prompt=prompt,
            response=response,
            embedding=fake_embed(prompt),
        ))

    def stats(self) -> dict:
        total = self.hits + self.misses
        return {
            "total_queries": total,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": f"{self.hits / total * 100:.1f}%" if total else "N/A",
            "entries": len(self.entries),
        }


# ============================================================
# 4. HYBRID — exact match + semantic fallback
# ============================================================
class HybridCache:
    def __init__(self, semantic_threshold: float = 0.95):
        self.exact = {}   # hash(prompt) -> response
        self.semantic = SemanticCache(threshold=semantic_threshold)

    def get(self, prompt: str) -> tuple[str | None, str]:
        # 1. Exact match (fastest)
        key = hashlib.md5(prompt.encode()).hexdigest()
        if key in self.exact:
            return self.exact[key], "exact"

        # 2. Semantic match
        response, sim, matched = self.semantic.get(prompt)
        if response is not None:
            return response, f"semantic (sim={sim:.3f})"

        return None, "miss"

    def put(self, prompt: str, response: str):
        self.exact[hashlib.md5(prompt.encode()).hexdigest()] = response
        self.semantic.put(prompt, response)


# ============================================================
# 5. REDIS + REDISEARCH (production-grade) — reference
# ============================================================
REDIS_SEMANTIC_CACHE = """
import numpy as np
from redis import Redis
from redis.commands.search.field import VectorField, TextField, NumericField
from redis.commands.search.indexDefinition import IndexDefinition

r = Redis(decode_responses=False)

# Create vector index (one-time setup)
try:
    r.ft("llm_cache").create_index(
        fields=[
            TextField("prompt"),
            TextField("response"),
            NumericField("created_at"),
            VectorField(
                "embedding",
                "HNSW",                       # algorithm
                {
                    "TYPE": "FLOAT32",
                    "DIM": 1536,              # OpenAI ada-002 dim
                    "DISTANCE_METRIC": "COSINE",
                }
            ),
        ],
        definition=IndexDefinition(prefix=["llm_cache:"]),
    )
except Exception:
    pass  # already exists

def cache_put(prompt: str, response: str, embedding: list[float]):
    vec = np.array(embedding, dtype=np.float32).tobytes()
    key = f"llm_cache:{hashlib.md5(prompt.encode()).hexdigest()}"
    r.hset(key, mapping={
        "prompt": prompt,
        "response": response,
        "embedding": vec,
        "created_at": int(time.time()),
    })
    r.expire(key, 86400)   # 24h TTL

def cache_get(query_embedding: list[float], threshold: float = 0.05):
    \"\"\"threshold = max cosine distance (0=identical, lower=stricter).\"\"\"
    vec = np.array(query_embedding, dtype=np.float32).tobytes()

    query = (
        "*=>[KNN 1 @embedding $vec AS score]"
    )
    result = r.ft("llm_cache").search(
        query,
        query_params={"vec": vec},
    )

    if result.docs:
        doc = result.docs[0]
        distance = float(doc.score)
        if distance <= threshold:
            return doc.response.decode(), 1 - distance
    return None, 0
"""


# ============================================================
# 6. FASTAPI INTEGRATION
# ============================================================
FASTAPI_INTEGRATION = """
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()
cache = HybridCache(semantic_threshold=0.95)

class ChatRequest(BaseModel):
    prompt: str
    temperature: float = 0
    use_cache: bool = True

@app.post("/chat")
async def chat(req: ChatRequest):
    # Skip cache if randomness desired
    if req.temperature > 0 or not req.use_cache:
        response = await call_llm(req.prompt)
        return {"response": response, "cached": False}

    # Try cache
    cached, source = cache.get(req.prompt)
    if cached is not None:
        return {"response": cached, "cached": True, "source": source}

    # Miss — call LLM
    response = await call_llm(req.prompt)
    cache.put(req.prompt, response)
    return {"response": response, "cached": False}

@app.get("/cache/stats")
async def cache_stats():
    return cache.semantic.stats()
"""


# ============================================================
# 7. LANGCHAIN INTEGRATION
# ============================================================
LANGCHAIN_INTEGRATION = """
# pip install langchain-community redis

from langchain_community.cache import RedisSemanticCache
from langchain.embeddings import OpenAIEmbeddings
import langchain

langchain.llm_cache = RedisSemanticCache(
    redis_url="redis://localhost:6379",
    embedding=OpenAIEmbeddings(),
    score_threshold=0.2,    # distance (1 - cosine), lower = stricter
)

# Now all LLM calls auto-checked against semantic cache
from langchain_openai import ChatOpenAI
llm = ChatOpenAI()
llm.invoke("What is Python?")        # MISS — calls API
llm.invoke("Tell me about Python")    # likely HIT — semantic match
"""


# ============================================================
# 8. GPTCACHE — drop-in semantic cache
# ============================================================
GPTCACHE_INTEGRATION = """
# pip install gptcache

from gptcache import cache, Config
from gptcache.adapter.openai import openai
from gptcache.embedding import OpenAI as OpenAIEmbedding
from gptcache.manager import CacheBase, VectorBase, get_data_manager
from gptcache.similarity_evaluation.distance import SearchDistanceEvaluation

cache.init(
    embedding_func=OpenAIEmbedding().to_embeddings,
    data_manager=get_data_manager(
        CacheBase("sqlite"),
        VectorBase("redis", dimension=1536),
    ),
    similarity_evaluation=SearchDistanceEvaluation(),
    config=Config(similarity_threshold=0.85),
)
cache.set_openai_key()

# Use as drop-in
response = openai.ChatCompletion.create(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "What is Python?"}],
)
# Auto-cached + auto-checked semantically
"""


# ============================================================
# 9. DEMO
# ============================================================
def demo_semantic_cache():
    print("=" * 60)
    print("SEMANTIC CACHE DEMO")
    print("=" * 60)

    cache = SemanticCache(threshold=0.85)   # using fake embeddings, lower threshold

    # Pre-populate
    cache.put("What is Python?", "Python is a high-level programming language.")
    cache.put("How does Docker work?", "Docker uses Linux containers...")
    cache.put("What is REST API?", "REST is an architectural style for APIs...")

    test_queries = [
        ("What is Python?", "should hit exact"),
        ("Tell me about Python", "should hit semantically"),
        ("Explain Python language", "should hit semantically"),
        ("What is Docker?", "should hit semantically"),
        ("Explain REST architecture", "should hit semantically"),
        ("What is quantum mechanics?", "should miss"),
    ]

    for query, expected in test_queries:
        response, sim, matched = cache.get(query)
        if response:
            print(f"\n  '{query}'")
            print(f"    HIT (sim={sim:.3f}) → matched '{matched}'")
            print(f"    Response: {response[:60]}...")
        else:
            print(f"\n  '{query}'")
            print(f"    MISS (best sim={sim:.3f})  ({expected})")

    print(f"\n  STATS: {cache.stats()}")


def demo_threshold_tuning():
    print("\n" + "=" * 60)
    print("THRESHOLD TUNING")
    print("=" * 60)

    pairs = [
        ("What is Python?", "Tell me about Python"),
        ("How to deploy on AWS?", "AWS deployment guide"),
        ("Best Python web framework?", "Recommended Python web framework"),
        ("What is Python?", "What is JavaScript?"),    # different
        ("How to make pizza?", "Pizza recipe"),         # similar but unrelated to code
    ]

    print("  query1 vs query2 → similarity")
    for q1, q2 in pairs:
        sim = cosine_similarity(fake_embed(q1), fake_embed(q2))
        print(f"    {sim:.3f}  '{q1}' vs '{q2}'")


# ============================================================
# 10. COST CALCULATOR
# ============================================================
def cost_calculator():
    print("\n" + "=" * 60)
    print("COST SAVINGS CALCULATOR")
    print("=" * 60)

    monthly_calls = 1_000_000
    cost_per_llm_call = 0.03           # GPT-4
    cost_per_embedding = 0.00002       # ada-002
    cache_infra_per_month = 200
    hit_rate = 0.4                     # 40%

    llm_cost = monthly_calls * cost_per_llm_call
    embedding_cost = monthly_calls * cost_per_embedding
    savings = (monthly_calls * hit_rate * cost_per_llm_call) - cache_infra_per_month - embedding_cost

    print(f"  Monthly LLM calls    : {monthly_calls:,}")
    print(f"  Cost per LLM call    : ${cost_per_llm_call}")
    print(f"  Without cache        : ${llm_cost:,.0f}")
    print(f"  Cache hit rate       : {hit_rate*100:.0f}%")
    print(f"  Embedding cost       : ${embedding_cost:.0f}")
    print(f"  Cache infra          : ${cache_infra_per_month}")
    print(f"  Net monthly savings  : ${savings:,.0f}")
    print(f"  Annual savings       : ${savings * 12:,.0f}")


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    demo_semantic_cache()
    demo_threshold_tuning()
    cost_calculator()

    print("\n" + "=" * 60)
    print("PRODUCTION INTEGRATION TEMPLATES")
    print("=" * 60)
    print("\n--- Real OpenAI embedding ---")
    print(REAL_OPENAI_EMBED)
    print("\n--- Redis + RediSearch ---")
    print(REDIS_SEMANTIC_CACHE)
    print("\n--- FastAPI ---")
    print(FASTAPI_INTEGRATION)
    print("\n--- LangChain ---")
    print(LANGCHAIN_INTEGRATION)
    print("\n--- GPTCache ---")
    print(GPTCACHE_INTEGRATION)
