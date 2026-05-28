# GraphQL with FastAPI + Strawberry

## Why It Matters

GraphQL = single endpoint for all data, client requests exactly what it needs:
- **Mobile clients** → reduce over-fetching (bandwidth)
- **BFF pattern** → frontend asks specific shape
- **Schema-driven** → strong typing, auto docs
- **N+1 mitigation** → DataLoaders batch queries

Senior interview: "REST vs GraphQL kab choose karoge?" → GraphQL for client-driven varying needs, REST for predictable simple CRUD.

---

## Core Concepts

### Strawberry Basics

```python
# pip install strawberry-graphql[fastapi]
import strawberry
from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter


@strawberry.type
class User:
    id: int
    name: str
    email: str


@strawberry.type
class Article:
    id: int
    title: str
    body: str

    @strawberry.field
    def author(self) -> User:
        # Resolver
        return User(id=1, name="Alice", email="a@b.com")


@strawberry.type
class Query:
    @strawberry.field
    def article(self, id: int) -> Article | None:
        # DB lookup
        return Article(id=id, title="Sample", body="...")

    @strawberry.field
    def articles(self, limit: int = 20) -> list[Article]:
        return []


schema = strawberry.Schema(query=Query)

app = FastAPI()
graphql_app = GraphQLRouter(schema)
app.include_router(graphql_app, prefix="/graphql")
```

Query:
```graphql
{
  article(id: 1) {
    title
    author {
      name
    }
  }
}
```

### Mutations

```python
@strawberry.input
class ArticleInput:
    title: str
    body: str


@strawberry.type
class Mutation:
    @strawberry.field
    async def create_article(self, input: ArticleInput) -> Article:
        # Save to DB
        return Article(id=99, title=input.title, body=input.body)

    @strawberry.field
    async def delete_article(self, id: int) -> bool:
        # Delete
        return True


schema = strawberry.Schema(query=Query, mutation=Mutation)
```

Mutation:
```graphql
mutation {
  createArticle(input: {title: "New", body: "..."}) {
    id
    title
  }
}
```

### Subscriptions (WebSocket)

```python
import asyncio


@strawberry.type
class Subscription:
    @strawberry.subscription
    async def article_created(self) -> AsyncIterator[Article]:
        while True:
            # Listen to Redis pub/sub etc.
            await asyncio.sleep(1)
            yield Article(id=1, title="Live", body="...")


schema = strawberry.Schema(query=Query, mutation=Mutation, subscription=Subscription)
```

### DataLoader (N+1 Mitigation)

```python
from strawberry.dataloader import DataLoader


async def load_users(keys: list[int]) -> list[User]:
    # Single query for all keys
    users = await db.fetch_all(
        "SELECT id, name, email FROM users WHERE id = ANY($1)",
        keys,
    )
    by_id = {u['id']: User(**u) for u in users}
    return [by_id.get(k) for k in keys]


class Context:
    def __init__(self):
        self.user_loader = DataLoader(load_users)


async def get_context() -> Context:
    return Context()


graphql_app = GraphQLRouter(schema, context_getter=get_context)


# In resolver
@strawberry.type
class Article:
    id: int
    title: str
    author_id: int

    @strawberry.field
    async def author(self, info) -> User:
        return await info.context.user_loader.load(self.author_id)
```

100 articles asking for author = 1 query instead of 100.

### Authentication / Context

```python
from fastapi import Request


async def get_context(request: Request):
    user = await authenticate(request)
    return {
        'request': request,
        'user': user,
        'user_loader': DataLoader(load_users),
    }


@strawberry.type
class Query:
    @strawberry.field
    def me(self, info) -> User:
        if not info.context['user']:
            raise PermissionError("Not authenticated")
        return info.context['user']
```

### Permissions

```python
import typing
from strawberry.permission import BasePermission


class IsAuthenticated(BasePermission):
    message = "Not authenticated"

    def has_permission(self, source, info, **kwargs) -> bool:
        return info.context.get('user') is not None


class IsOwner(BasePermission):
    message = "Not owner"

    def has_permission(self, source, info, **kwargs) -> bool:
        user = info.context.get('user')
        return user and source.author_id == user.id


@strawberry.type
class Query:
    @strawberry.field(permission_classes=[IsAuthenticated])
    def my_articles(self) -> list[Article]:
        return []
```

---

## How It Works Internally

### Schema Introspection

```graphql
{
  __schema {
    types {
      name
      fields { name }
    }
  }
}
```

Frontend tools (GraphQL Playground, Apollo Studio) use this to auto-generate types.

### Query Plan

1. Parse query into AST
2. Validate against schema
3. Resolve fields → call resolvers
4. Aggregate results into response

### Subscriptions Transport

Strawberry uses WebSocket (graphql-ws or graphql-transport-ws protocols).

---

## Common Pitfalls

### 1. N+1 Without DataLoader

```python
# 100 articles × 1 query each = 100 queries
```

Always use DataLoader for nested resolvers.

### 2. Authorization Per-Field

REST: middleware checks. GraphQL: each field resolver may need permission check. Use directives or permission_classes consistently.

### 3. Query Complexity Attacks

Client requests deeply nested data → DoS:

```graphql
{
  articles {
    comments {
      replies {
        replies { ... }
      }
    }
  }
}
```

Mitigate: max depth limit, query cost analysis.

### 4. Schema Versioning

REST: /v1, /v2. GraphQL: schema evolves with `@deprecated` directive. Don't break — add new fields.

### 5. File Uploads

GraphQL multipart spec needed for file uploads. Often easier to use REST endpoint alongside.

### 6. Caching

REST GET = HTTP cacheable. GraphQL POST = no HTTP cache. Use persisted queries + GET for cacheability.

---

## Interview Q&A

**Q1:** REST vs GraphQL — kab use karoge?
**A:** REST: predictable resources, simple CRUD, CDN cacheability, public APIs. GraphQL: client-driven shape (mobile, BFF), avoiding over-fetching, evolving schema, complex graph relationships. Not "GraphQL is better" — different tools.

**Q2:** N+1 GraphQL mein kaise solve karte ho?
**A:** DataLoader pattern — batch + cache loads within request. `loader.load(key)` returns Future. Loader collects all keys requested in same tick, fires single batched query. Per-request DataLoader instance (no cross-request leak).

**Q3:** GraphQL security concerns?
**A:** (1) Query depth limit — prevent deep recursion DoS. (2) Query cost analysis — assign cost per field, reject expensive. (3) Persisted queries — server only accepts pre-registered query IDs. (4) Auth per-field via permission classes. (5) Rate limit at query level.

**Q4:** Subscriptions scale kaise karte ho?
**A:** WebSocket connections distributed across pods. Backend pub/sub (Redis, Kafka) for fan-out. Each subscription handler subscribes to relevant channel + forwards. State in Redis, not in-memory.

**Q5:** GraphQL schema versioning?
**A:** Don't break — add new fields, mark old as `@deprecated(reason: "Use newField")`. Track deprecated usage via Apollo Studio metrics. Remove after grace period when usage = 0.

**Q6:** Caching strategy for GraphQL?
**A:** (1) Client-side cache (Apollo, urql) — normalize responses by ID. (2) Persisted queries — GraphQL POST → GET with query hash → CDN cacheable. (3) Field-level cache hints (`@cacheControl(maxAge: 60)`). (4) Server-side resolver cache (Redis).

**Q7:** GraphQL Federation kya hai?
**A:** Multiple GraphQL services compose into one schema. Each service owns its types. Apollo Federation (Gateway aggregates). Useful for microservices — frontend sees unified API. Strawberry supports Federation v2.

**Q8:** When to NOT use GraphQL?
**A:** (1) Simple CRUD — REST is simpler. (2) Public APIs (rate limiting harder per-field). (3) File uploads (REST easier). (4) When caching matters (REST + HTTP cache wins). (5) Small team — REST has lower learning curve.

---

## Real-World Use Cases

### 1. Mobile App BFF

Mobile fetches user + recent orders + recommendations in ONE query. Web fetches different shape from same endpoint.

### 2. Admin Dashboard

Dashboard explores arbitrary relationships — GraphQL playground = built-in admin tool.

### 3. Public API with Schema Evolution

GitHub's API v4 = GraphQL. Allows adding fields without versioning headaches.

---

## References

- [Strawberry GraphQL docs](https://strawberry.rocks/)
- [GraphQL spec](https://spec.graphql.org/)
- Apollo Federation
- Production GraphQL by Marc-André Giroux
