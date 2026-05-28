# 03 — N+1 Problem & DataLoader

> GraphQL's biggest performance pitfall. Solving it is non-negotiable in production.

---

## The N+1 Problem

### Setup

```graphql
query {
  posts {       # 1 query: fetch 10 posts
    title
    author {    # N queries: fetch each post's author
      name
    }
  }
}
```

Naive resolver:
```python
async def resolve_posts(self):
    return await db.fetch_all("SELECT * FROM posts LIMIT 10")  # 1 query

async def resolve_author(post):
    return await db.fetch_one("SELECT * FROM users WHERE id = $1", post.author_id)
    # ↑ Called 10 times — N additional queries
```

**Total queries:** 1 + N = 11. For 100 posts → 101 queries. Disaster at scale.

---

## REST Equivalent

REST handles this via `JOIN` or eager-loading:
```sql
SELECT p.*, u.name AS author_name
FROM posts p
JOIN users u ON p.author_id = u.id
LIMIT 10;
```

But GraphQL resolvers don't know in advance what fields will be requested → can't pre-JOIN.

---

## Solution: DataLoader (Batching)

DataLoader collects all keys requested in one "tick" of the event loop, batches them into a single query.

```python
# Without DataLoader: 10 individual queries
fetch_user(1), fetch_user(2), ..., fetch_user(10)

# With DataLoader: 1 batched query
fetch_users([1, 2, ..., 10]) → returns 10 users
```

### How

1. All resolver calls in the same tick that ask `user_loader.load(id)` are queued.
2. At next event loop tick, DataLoader fires single query for all queued IDs.
3. Resolves each promise with its corresponding user.

---

## Implementation (Strawberry)

```python
from strawberry.dataloader import DataLoader

async def load_users_batch(keys: list[int]) -> list[User]:
    """Called once per tick with all queued IDs."""
    rows = await db.fetch_all(
        "SELECT * FROM users WHERE id = ANY($1)",
        keys
    )
    by_id = {r.id: r for r in rows}
    # MUST return same order as keys (DataLoader contract)
    return [by_id.get(k) for k in keys]


user_loader = DataLoader(load_fn=load_users_batch)


@strawberry.type
class Post:
    id: strawberry.ID
    author_id: int

    @strawberry.field
    async def author(self) -> User:
        return await user_loader.load(self.author_id)
```

Now:
```graphql
query { posts { author { name } } }
```

Triggers:
- 1 query for posts.
- 1 batched query for all authors.

**Total: 2 queries** regardless of number of posts.

---

## Per-Request DataLoader (Critical!)

A single DataLoader at module level **caches across requests** — bad! User A sees User B's data.

**Right pattern:** New DataLoader per request, stored in context.

```python
async def get_context():
    return {
        "user_loader": DataLoader(load_fn=load_users_batch),
        "post_loader": DataLoader(load_fn=load_posts_batch),
        "db": db_pool,
    }

@strawberry.type
class Post:
    @strawberry.field
    async def author(self, info) -> User:
        return await info.context["user_loader"].load(self.author_id)
```

Loader instance lives for one request, then discarded.

---

## DataLoader Internals

```python
class DataLoader:
    def __init__(self, load_fn):
        self.load_fn = load_fn
        self.queue = []          # keys awaiting batch
        self.cache = {}          # per-request cache

    async def load(self, key):
        if key in self.cache:
            return self.cache[key]

        # Schedule batch if not already scheduled
        future = asyncio.Future()
        self.queue.append((key, future))

        if len(self.queue) == 1:
            asyncio.create_task(self._dispatch())

        return await future

    async def _dispatch(self):
        await asyncio.sleep(0)   # wait for current tick to drain

        batch = self.queue[:]
        self.queue = []
        keys = [k for k, _ in batch]
        results = await self.load_fn(keys)

        for (k, future), result in zip(batch, results):
            self.cache[k] = result
            future.set_result(result)
```

Key insight: `asyncio.sleep(0)` lets the event loop run all queued resolvers first; by the time dispatch runs, all keys are collected.

---

## Multi-Field N+1

Posts have author AND comments AND likes — multiple DataLoaders.

```python
async def get_context():
    return {
        "user_loader": DataLoader(load_fn=batch_users),
        "comments_loader": DataLoader(load_fn=batch_comments_by_post),
        "likes_loader": DataLoader(load_fn=batch_likes_by_post),
    }
```

For 10 posts: 1 (posts) + 1 (authors) + 1 (comments) + 1 (likes) = 4 queries instead of 31.

---

## Load Many (1-to-Many)

`comments_loader.load(post_id)` returns multiple comments — needs different batching.

```python
async def batch_comments_by_post(post_ids):
    rows = await db.fetch_all(
        "SELECT * FROM comments WHERE post_id = ANY($1)", post_ids
    )
    by_post = defaultdict(list)
    for row in rows:
        by_post[row.post_id].append(row)
    return [by_post[pid] for pid in post_ids]
```

Returns list of lists.

---

## Cache Control

```python
loader = DataLoader(
    load_fn=batch_users,
    cache=True,   # default True — cache hits within same request
    max_batch_size=100  # split large batches
)
```

For mutations that change data, clear loaders:
```python
@strawberry.mutation
async def update_user(self, info, id: ID, name: str) -> User:
    user = await db.update_user(id, name)
    info.context["user_loader"].clear(id)  # invalidate cache
    return user
```

---

## Why Same Order?

DataLoader contract: `load_fn(keys)` must return results in **same order** as keys.

Wrong:
```python
async def batch_users(keys):
    return await db.fetch_all("SELECT * FROM users WHERE id = ANY($1)", keys)
    # ↑ DB returns in physical order, NOT same as keys!
```

Right:
```python
async def batch_users(keys):
    rows = await db.fetch_all("SELECT * FROM users WHERE id = ANY($1)", keys)
    by_id = {r.id: r for r in rows}
    return [by_id.get(k) for k in keys]
```

---

## Handling Missing Keys

If a key doesn't exist:
```python
# Return None — DataLoader handles
return [by_id.get(k) for k in keys]   # None for missing
```

Resolver caller checks:
```python
@strawberry.field
async def author(self, info) -> User | None:
    return await info.context["user_loader"].load(self.author_id)
```

---

## Prefetch Strategy (Alternative)

Some libraries (graphene-django, strawberry-django) auto-prefetch based on requested fields by parsing query AST.

```python
# Strawberry-Django example
@strawberry_django.type(User)
class User:
    posts: list[Post]   # auto select_related/prefetch_related
```

Looks at GraphQL query, generates optimal ORM `.select_related()` / `.prefetch_related()` calls.

**Pros:** No manual DataLoader.
**Cons:** Tied to ORM; less control.

---

## When NOT to use DataLoader

- Simple field with no DB lookup (just attribute on parent).
- Single-key lookup not repeated (one user load per request).
- When eager-loading via ORM is simpler (joins via Django select_related, SQLAlchemy joinedload).

---

## Monitoring N+1 in Production

### Detect
- Log all DB queries per request, alert if count > threshold.
- APM tools (DataDog, NewRelic) show N+1 patterns.
- Django: `django-debug-toolbar`, `nplusone`.
- SQLAlchemy: `echo=True` in dev.

### Test
```python
@pytest.mark.asyncio
async def test_no_n_plus_one(monkeypatch):
    query_count = 0
    original = db.fetch_all
    async def counting_fetch(*args, **kwargs):
        nonlocal query_count
        query_count += 1
        return await original(*args, **kwargs)
    monkeypatch.setattr(db, "fetch_all", counting_fetch)

    result = await schema.execute(query, context=ctx)
    assert query_count <= 3, f"Got {query_count} queries (expected ≤3)"
```

---

## Real-World Patterns

### Per-tenant batching (multi-tenant)
```python
async def batch_users(keys, tenant_id):
    return await db.fetch_all(
        "SELECT * FROM users WHERE tenant_id = $1 AND id = ANY($2)",
        tenant_id, keys
    )
```

Tenant scoping critical — don't leak across tenants.

### Caching across requests
For mostly-static data (categories, configs), use Redis cache *inside* the loader.

```python
async def batch_categories(keys):
    # Try Redis first
    redis_keys = [f"cat:{k}" for k in keys]
    cached = await redis.mget(redis_keys)
    misses = [(i, k) for i, (k, v) in enumerate(zip(keys, cached)) if v is None]

    if misses:
        miss_keys = [k for _, k in misses]
        from_db = await db.fetch_all("SELECT * FROM categories WHERE id = ANY($1)", miss_keys)
        # Update Redis + result
        for (idx, k), row in zip(misses, from_db):
            cached[idx] = row
            await redis.set(f"cat:{k}", pickle.dumps(row), ex=3600)

    return cached
```

---

## TL;DR

- N+1 = 1 query for parent + N for children. Standard GraphQL trap.
- DataLoader = batch queue per request.
- Always create per-request, never global.
- Must return results in same order as input keys.
- Use a loader per relationship (user_loader, comments_loader, etc.).
- Monitor query count in tests + APM.
- Combine with caching for static data.
