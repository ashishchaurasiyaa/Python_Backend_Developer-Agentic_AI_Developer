"""
DAY 27 — functools: lru_cache, cache, cached_property
Architecture Level: Senior Python Backend + Agentic AI
"""

import functools
import time
import asyncio
from typing import Callable, TypeVar

F = TypeVar("F", bound=Callable)


# ─────────────────────────────────────────────
# 1. lru_cache — memoization with LRU eviction
# ─────────────────────────────────────────────

@functools.lru_cache(maxsize=128)
def fibonacci(n: int) -> int:
    """Classic memoization example."""
    if n < 2:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)

start = time.perf_counter()
print(fibonacci(50))         # instant after first call
print(f"Cache info: {fibonacci.cache_info()}")
# CacheInfo(hits=48, misses=51, maxsize=128, currsize=51)

fibonacci.cache_clear()      # clear the cache


# ─────────────────────────────────────────────
# 2. functools.cache — unbounded cache (Python 3.9+)
# ─────────────────────────────────────────────

@functools.cache
def get_model_config(model_name: str) -> dict:
    """Simulate fetching model config from DB/API (expensive)."""
    print(f"  [DB HIT] Fetching config for {model_name}")
    time.sleep(0.01)  # simulate latency
    return {"model": model_name, "max_tokens": 4096, "temperature": 0.7}

# First call — hits DB
cfg1 = get_model_config("gpt-4")
# Second call — from cache
cfg2 = get_model_config("gpt-4")
print(f"\nSame object? {cfg1 is cfg2}")  # True — same cached object


# ─────────────────────────────────────────────
# 3. cached_property — compute once, store on instance
# ─────────────────────────────────────────────

class AgentConfig:
    """
    cached_property computes the value once and caches it on the instance.
    Unlike @property, it does NOT call the getter every time.
    Perfect for expensive computed properties.
    """

    def __init__(self, model: str, system_prompt: str):
        self.model = model
        self.system_prompt = system_prompt

    @functools.cached_property
    def token_count(self) -> int:
        """Expensive operation — compute once."""
        print("  [Computing token count...]")
        return len(self.system_prompt.split()) * 4  # rough estimate

    @functools.cached_property
    def prompt_hash(self) -> str:
        """Used for caching prompts in vector DB."""
        import hashlib
        print("  [Computing hash...]")
        return hashlib.md5(self.system_prompt.encode()).hexdigest()


agent = AgentConfig("gpt-4", "You are a helpful assistant that specializes in Python.")
print(f"\nToken count (1st): {agent.token_count}")   # computes
print(f"Token count (2nd): {agent.token_count}")     # from cache — no print
print(f"Hash: {agent.prompt_hash}")


# ─────────────────────────────────────────────
# 4. BACKEND USE CASE — Cache DB lookup results
# ─────────────────────────────────────────────

class UserService:
    """
    Pattern used in FastAPI with dependency injection.
    lru_cache on methods requires a workaround since 'self' must be hashable.
    Solution: cache at module level or use instance-level dict cache.
    """

    def __init__(self):
        self._cache: dict[int, dict] = {}

    def get_user(self, user_id: int) -> dict | None:
        if user_id not in self._cache:
            print(f"  [DB] Fetching user {user_id}")
            # Simulate DB call
            self._cache[user_id] = {"id": user_id, "name": f"User_{user_id}"}
        return self._cache[user_id]


# Module-level lru_cache for stateless functions (most common pattern):
@functools.lru_cache(maxsize=256)
def get_permission_set(role: str) -> frozenset[str]:
    """
    Cache permission lookups — called on EVERY request.
    frozenset is hashable, so it can be returned and cached properly.
    """
    permissions = {
        "admin": frozenset({"read", "write", "delete", "admin"}),
        "user": frozenset({"read", "write"}),
        "guest": frozenset({"read"}),
    }
    return permissions.get(role, frozenset())

print(f"\nAdmin perms: {get_permission_set('admin')}")
print(f"Cache info: {get_permission_set.cache_info()}")


# ─────────────────────────────────────────────
# 5. AGENTIC AI — Cache expensive embedding calls
# ─────────────────────────────────────────────

@functools.lru_cache(maxsize=1000)
def get_embedding(text: str, model: str = "text-embedding-3-small") -> tuple[float, ...]:
    """
    Cache embeddings — calling OpenAI/Claude for same text is wasteful.
    Returns tuple (not list) because tuples are hashable and cacheable.
    In production, use Redis for distributed caching.
    """
    print(f"  [API CALL] Getting embedding for: {text[:30]}...")
    # Simulate embedding (normally returns list[float] of 1536 dims)
    import hashlib
    h = int(hashlib.md5(text.encode()).hexdigest(), 16)
    return tuple([((h >> i) & 0xFF) / 255.0 for i in range(10)])


text = "What is the capital of France?"
emb1 = get_embedding(text)
emb2 = get_embedding(text)  # from cache — no API call
print(f"\nEmbedding cached: {emb1 is emb2}")
print(f"Embedding cache stats: {get_embedding.cache_info()}")


# ─────────────────────────────────────────────
# INTERVIEW — When NOT to use lru_cache
# ─────────────────────────────────────────────
# 1. Functions with mutable arguments (list, dict) — not hashable
# 2. Methods on mutable objects — 'self' changes between calls
# 3. Functions returning mutable objects — cached object can be mutated
# 4. Very large return values — fills memory
# 5. Functions with side effects — cache hides them
#
# SOLUTION for mutable args: convert to immutable first
# @lru_cache(maxsize=128)
# def process(items: tuple) -> ...:  # call as process(tuple(my_list))
