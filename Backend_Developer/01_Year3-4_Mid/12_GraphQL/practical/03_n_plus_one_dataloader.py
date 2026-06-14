"""
GraphQL N+1 Problem & DataLoader — Production Patterns
=======================================================

Covers:
  - What the N+1 problem is and why GraphQL triggers it
  - A standalone DataLoader implementation (no external deps) that mirrors
    the Strawberry / facebook/dataloader contract exactly
  - Per-request DataLoader context (critical for correctness)
  - 1-to-1 batching (users by ID)
  - 1-to-many batching (comments by post ID, likes by post ID)
  - Cache control and manual cache invalidation after mutations
  - Multi-field N+1 (multiple loaders per request)
  - Redis-backed cross-request caching pattern (illustrative)
  - Query-count test helper that asserts <= N queries
  - Strawberry + FastAPI wiring (illustrative — requires external packages)

Usage (no external infra required — runs in-process demo):
    python 03_n_plus_one_dataloader.py

External deps (illustrative):
    pip install strawberry-graphql fastapi uvicorn asyncpg aioredis
"""

from __future__ import annotations

import asyncio
import logging
import pickle
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Generic, Optional, TypeVar

# ==========================================================================
# 1. DATA MODELS (plain dataclasses, no ORM dependency)
# ==========================================================================

@dataclass
class User:
    id: int
    name: str
    email: str


@dataclass
class Post:
    id: int
    title: str
    author_id: int


@dataclass
class Comment:
    id: int
    post_id: int
    body: str


@dataclass
class Like:
    id: int
    post_id: int
    user_id: int


# ==========================================================================
# 2. FAKE IN-MEMORY DATABASE (replaces asyncpg / DB pool in examples)
# ==========================================================================

_USERS: dict[int, User] = {
    1: User(id=1, name="Alice", email="alice@example.com"),
    2: User(id=2, name="Bob",   email="bob@example.com"),
    3: User(id=3, name="Carol", email="carol@example.com"),
}

_POSTS: list[Post] = [
    Post(id=1, title="Post A", author_id=1),
    Post(id=2, title="Post B", author_id=2),
    Post(id=3, title="Post C", author_id=1),
    Post(id=4, title="Post D", author_id=3),
    Post(id=5, title="Post E", author_id=2),
]

_COMMENTS: list[Comment] = [
    Comment(id=1,  post_id=1, body="Great!"),
    Comment(id=2,  post_id=1, body="Thanks!"),
    Comment(id=3,  post_id=2, body="Nice one."),
    Comment(id=4,  post_id=3, body="Interesting."),
    Comment(id=5,  post_id=3, body="Agreed."),
    Comment(id=6,  post_id=4, body="Cool."),
]

_LIKES: list[Like] = [
    Like(id=1, post_id=1, user_id=2),
    Like(id=2, post_id=1, user_id=3),
    Like(id=3, post_id=2, user_id=1),
    Like(id=4, post_id=3, user_id=2),
    Like(id=5, post_id=5, user_id=3),
]

# Query counter — simulates APM / test assertions
_query_log: list[str] = []


async def db_fetch_all_posts() -> list[Post]:
    """Simulate: SELECT * FROM posts LIMIT 10."""
    _query_log.append("SELECT * FROM posts")
    await asyncio.sleep(0)          # simulate async I/O
    return list(_POSTS)


async def db_fetch_users_by_ids(user_ids: list[int]) -> list[User | None]:
    """
    Simulate: SELECT * FROM users WHERE id = ANY($1).

    IMPORTANT: Must return results in the SAME ORDER as the input keys.
    The DB may return rows in physical order — always re-map by id.
    """
    _query_log.append(f"SELECT * FROM users WHERE id IN {tuple(user_ids)}")
    await asyncio.sleep(0)
    by_id = {uid: _USERS.get(uid) for uid in user_ids}
    return [by_id.get(k) for k in user_ids]     # same-order contract


async def db_fetch_comments_by_post_ids(post_ids: list[int]) -> list[list[Comment]]:
    """
    Simulate: SELECT * FROM comments WHERE post_id = ANY($1).

    Returns a list-of-lists (1-to-many): one inner list per post_id.
    """
    _query_log.append(f"SELECT * FROM comments WHERE post_id IN {tuple(post_ids)}")
    await asyncio.sleep(0)
    by_post: dict[int, list[Comment]] = defaultdict(list)
    for c in _COMMENTS:
        if c.post_id in set(post_ids):
            by_post[c.post_id].append(c)
    return [by_post[pid] for pid in post_ids]    # same-order contract


async def db_fetch_likes_by_post_ids(post_ids: list[int]) -> list[list[Like]]:
    """Simulate: SELECT * FROM likes WHERE post_id = ANY($1)."""
    _query_log.append(f"SELECT * FROM likes WHERE post_id IN {tuple(post_ids)}")
    await asyncio.sleep(0)
    by_post: dict[int, list[Like]] = defaultdict(list)
    for lk in _LIKES:
        if lk.post_id in set(post_ids):
            by_post[lk.post_id].append(lk)
    return [by_post[pid] for pid in post_ids]


# ==========================================================================
# 3. DATALOADER IMPLEMENTATION
# ==========================================================================
#
# Mirrors the strawberry.dataloader.DataLoader / facebook/dataloader contract:
#   - load(key)  → awaitable; queues key and returns a Future
#   - _dispatch  → fires once per event-loop tick; collects all queued keys
#                  and calls load_fn(keys) in a single batch
#   - cache      → per-loader (per-request) in-memory result cache
#   - max_batch_size → splits oversized batches to avoid huge IN-clauses
#
# Key insight: asyncio.sleep(0) yields control back to the event loop so that
# ALL concurrent resolver coroutines can call load() before _dispatch runs.

K = TypeVar("K")   # key type   (e.g. int)
V = TypeVar("V")   # value type (e.g. User | None, list[Comment])


class DataLoader(Generic[K, V]):
    """
    Standalone async DataLoader — no external dependencies.

    Parameters
    ----------
    load_fn:
        Async function that accepts a list of keys and returns a list of
        results in exactly the same order.  Must be ``async``.
    cache:
        Enable per-request in-memory cache (default True).
    max_batch_size:
        Cap on keys sent per batch; large sets are split automatically.
    """

    def __init__(
        self,
        load_fn: Callable[[list[K]], "asyncio.Future[list[V]]"],
        *,
        cache: bool = True,
        max_batch_size: int = 1000,
    ) -> None:
        self.load_fn = load_fn
        self._cache_enabled = cache
        self.max_batch_size = max_batch_size

        self._queue: list[tuple[K, asyncio.Future[V]]] = []
        self._cache: dict[K, V] = {}
        self._dispatch_scheduled = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def load(self, key: K) -> V:
        """Enqueue a single key and return its result (awaitable)."""
        if self._cache_enabled and key in self._cache:
            return self._cache[key]

        loop = asyncio.get_event_loop()
        future: asyncio.Future[V] = loop.create_future()
        self._queue.append((key, future))

        # Schedule a single dispatch per tick — only on the first enqueue.
        if not self._dispatch_scheduled:
            self._dispatch_scheduled = True
            asyncio.create_task(self._dispatch())

        return await future

    async def load_many(self, keys: list[K]) -> list[V]:
        """Convenience wrapper that batches multiple keys in one call."""
        return list(await asyncio.gather(*[self.load(k) for k in keys]))

    def clear(self, key: K) -> None:
        """Invalidate a single cache entry (use after mutations)."""
        self._cache.pop(key, None)

    def clear_all(self) -> None:
        """Invalidate the entire per-request cache."""
        self._cache.clear()

    def prime(self, key: K, value: V) -> None:
        """Pre-seed the cache — useful when you already have the object."""
        self._cache[key] = value

    # ------------------------------------------------------------------
    # Internal dispatch
    # ------------------------------------------------------------------

    async def _dispatch(self) -> None:
        """
        Called once per event-loop tick.

        asyncio.sleep(0) yields so every concurrent resolver can call load()
        before the batch fires.  By the time we resume, the queue is full.
        """
        await asyncio.sleep(0)           # drain current tick
        self._dispatch_scheduled = False

        batch = self._queue[:]
        self._queue.clear()

        if not batch:
            return

        # Split into chunks to respect max_batch_size
        for chunk_start in range(0, len(batch), self.max_batch_size):
            chunk = batch[chunk_start: chunk_start + self.max_batch_size]
            keys = [k for k, _ in chunk]

            try:
                results = await self.load_fn(keys)
            except Exception as exc:
                # Propagate exceptions to each waiting coroutine
                for _, future in chunk:
                    if not future.done():
                        future.set_exception(exc)
                continue

            for (key, future), result in zip(chunk, results):
                if self._cache_enabled:
                    self._cache[key] = result
                if not future.done():
                    future.set_result(result)


# ==========================================================================
# 4. BATCH LOAD FUNCTIONS  (the actual DB calls)
# ==========================================================================

async def batch_load_users(keys: list[int]) -> list[User | None]:
    """Batch function for the user DataLoader — 1-to-1 (user per ID)."""
    return await db_fetch_users_by_ids(keys)


async def batch_load_comments(post_ids: list[int]) -> list[list[Comment]]:
    """Batch function for comments DataLoader — 1-to-many (comments per post)."""
    return await db_fetch_comments_by_post_ids(post_ids)


async def batch_load_likes(post_ids: list[int]) -> list[list[Like]]:
    """Batch function for likes DataLoader — 1-to-many (likes per post)."""
    return await db_fetch_likes_by_post_ids(post_ids)


# ==========================================================================
# 5. PER-REQUEST CONTEXT FACTORY  (critical — never share loaders across
#    requests; a module-level loader caches across requests → data leaks)
# ==========================================================================

def build_request_context() -> dict[str, Any]:
    """
    Create a fresh set of DataLoaders for each incoming GraphQL request.

    In Strawberry + FastAPI this becomes:

        async def get_context(request: Request) -> dict:
            return build_request_context()

        schema = strawberry.Schema(query=Query)
        app.add_route(
            "/graphql",
            GraphQLRouter(schema=schema, context_getter=get_context),
        )
    """
    return {
        "user_loader":     DataLoader(load_fn=batch_load_users),
        "comments_loader": DataLoader(load_fn=batch_load_comments),
        "likes_loader":    DataLoader(load_fn=batch_load_likes),
    }


# ==========================================================================
# 6. RESOLVER LAYER  (illustrates what Strawberry @strawberry.field does)
# ==========================================================================

async def resolve_posts() -> list[Post]:
    """Root resolver — 1 query regardless of how many posts."""
    return await db_fetch_all_posts()


async def resolve_author(post: Post, context: dict) -> User | None:
    """
    Field resolver for Post.author.

    Without DataLoader: called N times → N separate DB round-trips.
    With DataLoader:    all author_id values are batched → 1 query.
    """
    return await context["user_loader"].load(post.author_id)


async def resolve_comments(post: Post, context: dict) -> list[Comment]:
    """Field resolver for Post.comments — 1-to-many via DataLoader."""
    return await context["comments_loader"].load(post.id)


async def resolve_likes(post: Post, context: dict) -> list[Like]:
    """Field resolver for Post.likes — 1-to-many via DataLoader."""
    return await context["likes_loader"].load(post.id)


# ==========================================================================
# 7. STRAWBERRY SCHEMA — ILLUSTRATIVE (requires: pip install strawberry-graphql)
# ==========================================================================
#
# The block below is a string so the module compiles without strawberry
# installed.  In a real project, un-comment and import strawberry at top.

STRAWBERRY_SCHEMA_EXAMPLE = """
import strawberry
from strawberry.types import Info

@strawberry.type
class CommentGQL:
    id: strawberry.ID
    body: str

@strawberry.type
class LikeGQL:
    id: strawberry.ID
    user_id: int

@strawberry.type
class UserGQL:
    id: strawberry.ID
    name: str
    email: str

@strawberry.type
class PostGQL:
    id: strawberry.ID
    title: str
    author_id: int          # internal field — not exposed directly

    @strawberry.field
    async def author(self, info: Info) -> UserGQL | None:
        user = await info.context["user_loader"].load(self.author_id)
        if user is None:
            return None
        return UserGQL(id=user.id, name=user.name, email=user.email)

    @strawberry.field
    async def comments(self, info: Info) -> list[CommentGQL]:
        rows = await info.context["comments_loader"].load(self.id)
        return [CommentGQL(id=c.id, body=c.body) for c in rows]

    @strawberry.field
    async def likes(self, info: Info) -> list[LikeGQL]:
        rows = await info.context["likes_loader"].load(self.id)
        return [LikeGQL(id=lk.id, user_id=lk.user_id) for lk in rows]

@strawberry.type
class Query:
    @strawberry.field
    async def posts(self, info: Info) -> list[PostGQL]:
        rows = await info.context["db"].fetch_all_posts()
        return [PostGQL(id=p.id, title=p.title, author_id=p.author_id) for p in rows]

@strawberry.mutation
class Mutation:
    @strawberry.field
    async def update_user_name(
        self, info: Info, id: strawberry.ID, name: str
    ) -> UserGQL:
        user = await info.context["db"].update_user(int(id), name)
        # Invalidate loader cache after mutation so stale data is not served
        info.context["user_loader"].clear(int(id))
        return UserGQL(id=user.id, name=user.name, email=user.email)

schema = strawberry.Schema(query=Query, mutation=Mutation)
"""


# ==========================================================================
# 8. REDIS-BACKED CROSS-REQUEST CACHING  (illustrative pattern)
# ==========================================================================
#
# For mostly-static data (categories, config values) you can back the batch
# load function with Redis so hot keys survive across requests.
#
# Requires: pip install aioredis

async def batch_load_categories_with_redis(
    keys: list[int],
    *,
    redis=None,          # aioredis.Redis instance injected by caller
    db=None,             # asyncpg pool injected by caller
) -> list[Any]:
    """
    Try Redis first; fall back to DB for misses; populate Redis on miss.

    TTL of 3600 s means category data updates propagate within an hour.
    Combine with explicit cache.clear() after admin mutations for instant
    invalidation.
    """
    if redis is None or db is None:
        # Without infra, return empty stubs so the module stays importable
        return [None] * len(keys)

    redis_keys = [f"cat:{k}" for k in keys]
    cached: list[Any] = await redis.mget(redis_keys)          # type: ignore[assignment]
    misses = [(i, k) for i, (k, v) in enumerate(zip(keys, cached)) if v is None]

    if misses:
        miss_keys = [k for _, k in misses]
        # Assume db.fetch_all returns rows ordered by insertion, NOT by keys
        rows = await db.fetch_all(                             # type: ignore[union-attr]
            "SELECT * FROM categories WHERE id = ANY($1)", miss_keys
        )
        by_id = {r["id"]: r for r in rows}
        for idx, k in misses:
            row = by_id.get(k)
            cached[idx] = row
            if row is not None:
                await redis.set(                               # type: ignore[union-attr]
                    f"cat:{k}", pickle.dumps(row), ex=3600
                )

    return cached


# ==========================================================================
# 9. QUERY-COUNT TEST HELPER
# ==========================================================================

class QueryCounter:
    """
    Context manager that tracks how many DB queries were issued.

    Usage in tests::

        async with QueryCounter() as qc:
            result = await run_graphql_query(schema, QUERY_STRING, ctx)
        assert qc.count <= 3, f"N+1 detected — got {qc.count} queries"
    """

    def __init__(self) -> None:
        self.count = 0
        self._original_log: list[str] = []

    async def __aenter__(self) -> "QueryCounter":
        global _query_log
        self._original_log = _query_log
        _query_log = []
        return self

    async def __aexit__(self, *_: Any) -> None:
        global _query_log
        self.count = len(_query_log)
        self.queries = list(_query_log)
        _query_log = self._original_log


# ==========================================================================
# 10. NAIVE (N+1) vs DATALOADER COMPARISON DEMO
# ==========================================================================

async def _naive_fetch_posts_with_authors() -> list[dict[str, Any]]:
    """
    Classic N+1 pattern — one author query per post.

    For 5 posts this fires 1 + 5 = 6 queries.
    For 100 posts this fires 101 queries.
    """
    posts = await db_fetch_all_posts()

    result = []
    for post in posts:
        # Each iteration issues a separate SELECT — the N+1 trap
        users = await db_fetch_users_by_ids([post.author_id])
        author = users[0]
        result.append({"post": post.title, "author": author.name if author else None})
    return result


async def _dataloader_fetch_posts_with_authors() -> list[dict[str, Any]]:
    """
    DataLoader pattern — batches all author IDs into a single query.

    Regardless of post count, this fires exactly 2 queries.
    """
    context = build_request_context()
    posts = await db_fetch_all_posts()

    # Fire all load() calls concurrently — they all queue before _dispatch runs
    async def enrich(post: Post) -> dict[str, Any]:
        author = await resolve_author(post, context)
        return {"post": post.title, "author": author.name if author else None}

    return list(await asyncio.gather(*[enrich(p) for p in posts]))


async def _multi_loader_demo() -> list[dict[str, Any]]:
    """
    Multi-field N+1 — uses three DataLoaders simultaneously.

    For 5 posts this fires exactly 4 queries:
      1 (posts) + 1 (authors) + 1 (comments) + 1 (likes)
    Naive approach would fire: 1 + 5 + 5 + 5 = 16 queries.
    """
    context = build_request_context()
    posts = await db_fetch_all_posts()

    async def enrich(post: Post) -> dict[str, Any]:
        author, comments, likes = await asyncio.gather(
            resolve_author(post, context),
            resolve_comments(post, context),
            resolve_likes(post, context),
        )
        return {
            "post":     post.title,
            "author":   author.name if author else None,
            "comments": [c.body for c in comments],
            "likes":    len(likes),
        }

    return list(await asyncio.gather(*[enrich(p) for p in posts]))


# ==========================================================================
# 11. MAIN — RUNNABLE DEMO (no external infra required)
# ==========================================================================

async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    log = logging.getLogger(__name__)

    separator = "-" * 60

    # --- Naive N+1 ---
    log.info("\n%s", separator)
    log.info("NAIVE N+1 PATTERN")
    log.info(separator)
    global _query_log
    _query_log.clear()
    naive_result = await _naive_fetch_posts_with_authors()
    log.info("Results: %s", naive_result)
    log.info("Queries issued: %d  (expected: 1 + N = %d)", len(_query_log), 1 + len(_POSTS))
    log.info("SQL log: %s", _query_log)

    # --- DataLoader (1 relationship) ---
    log.info("\n%s", separator)
    log.info("DATALOADER — POSTS + AUTHORS (2 queries expected)")
    log.info(separator)
    _query_log.clear()
    dl_result = await _dataloader_fetch_posts_with_authors()
    log.info("Results: %s", dl_result)
    log.info("Queries issued: %d  (expected: 2)", len(_query_log))
    log.info("SQL log: %s", _query_log)
    assert len(_query_log) == 2, f"N+1 still present: {len(_query_log)} queries"

    # --- Multi-field DataLoader (3 relationships) ---
    log.info("\n%s", separator)
    log.info("MULTI-LOADER — POSTS + AUTHORS + COMMENTS + LIKES (4 queries expected)")
    log.info(separator)
    _query_log.clear()
    multi_result = await _multi_loader_demo()
    for row in multi_result:
        log.info(
            "  Post='%s'  author=%s  comments=%s  likes=%d",
            row["post"], row["author"], row["comments"], row["likes"],
        )
    log.info("Queries issued: %d  (expected: 4)", len(_query_log))
    log.info("SQL log: %s", _query_log)
    assert len(_query_log) == 4, f"Expected 4 queries, got {len(_query_log)}"

    # --- Cache priming and invalidation ---
    log.info("\n%s", separator)
    log.info("CACHE PRIMING & INVALIDATION")
    log.info(separator)
    loader: DataLoader[int, User | None] = DataLoader(load_fn=batch_load_users)
    # Prime the cache — no DB query needed
    loader.prime(1, _USERS[1])
    _query_log.clear()
    user_from_cache = await loader.load(1)
    log.info("Loaded from cache (no DB hit): %s", user_from_cache)
    log.info("DB queries fired: %d  (expected: 0)", len(_query_log))
    # Invalidate after a hypothetical mutation
    loader.clear(1)
    _query_log.clear()
    user_after_clear = await loader.load(1)
    log.info("Loaded after cache clear (DB hit): %s", user_after_clear)
    log.info("DB queries fired: %d  (expected: 1)", len(_query_log))

    # --- Query-count guard (mirrors test assertions) ---
    log.info("\n%s", separator)
    log.info("QUERY-COUNT GUARD (test helper demo)")
    log.info(separator)
    async with QueryCounter() as qc:
        await _dataloader_fetch_posts_with_authors()
    log.info("QueryCounter detected %d queries", qc.count)
    assert qc.count <= 2, f"N+1 regression — {qc.count} queries"
    log.info("Assertion passed: <= 2 queries")

    log.info("\n%s", separator)
    log.info("All demos completed successfully.")
    log.info(separator)


if __name__ == "__main__":
    asyncio.run(main())
