# 02 — Strawberry + FastAPI Integration

> Strawberry is the modern Python GraphQL library. Type-hint-based schema, async-native, integrates cleanly with FastAPI.

---

## Setup

```bash
pip install strawberry-graphql[fastapi]
```

## Minimal App

```python
import strawberry
from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter

@strawberry.type
class User:
    id: strawberry.ID
    name: str
    email: str

@strawberry.type
class Query:
    @strawberry.field
    def user(self, id: strawberry.ID) -> User:
        return User(id=id, name="Alice", email="alice@x.com")

schema = strawberry.Schema(query=Query)

app = FastAPI()
graphql_app = GraphQLRouter(schema)
app.include_router(graphql_app, prefix="/graphql")
```

Access: `http://localhost:8000/graphql` opens GraphiQL UI.

---

## Schema as Code

Types defined via Python classes with `@strawberry.type`.

```python
@strawberry.type
class Post:
    id: strawberry.ID
    title: str
    content: str | None
    created_at: datetime
```

Optional fields: use `| None` or `Optional[X]`.

### Auto-generated SDL
```bash
strawberry export-schema myapp.schema:schema
```

Useful for sharing with frontend / contract testing.

---

## Resolvers

Use `@strawberry.field` for custom logic.

```python
@strawberry.type
class User:
    id: strawberry.ID
    name: str

    @strawberry.field
    async def posts(self) -> list["Post"]:
        return await db.fetch_posts(user_id=self.id)
```

Forward references: use string for self-referential types.

---

## Mutations

```python
@strawberry.input
class CreatePostInput:
    title: str
    content: str

@strawberry.type
class Mutation:
    @strawberry.mutation
    async def create_post(self, input: CreatePostInput) -> Post:
        post = await db.insert_post(input.title, input.content)
        return post

schema = strawberry.Schema(query=Query, mutation=Mutation)
```

---

## Async Resolvers

Async-first. Use `async def` for any IO-bound resolver.

```python
@strawberry.field
async def slow_field(self) -> str:
    await asyncio.sleep(1)
    return "done"
```

---

## Context (Auth, DB, etc.)

```python
from strawberry.types import Info

async def get_context():
    return {
        "db": db_pool,
        "user": None  # filled by middleware
    }

graphql_app = GraphQLRouter(schema, context_getter=get_context)

@strawberry.type
class Query:
    @strawberry.field
    async def me(self, info: Info) -> User:
        user = info.context["user"]
        if not user:
            raise PermissionError("Not logged in")
        return user
```

---

## Auth Middleware (extracting user)

```python
from fastapi import Depends, Header

async def get_current_user(authorization: str = Header(None)):
    if not authorization: return None
    token = authorization.replace("Bearer ", "")
    try:
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        return await db.fetch_user(payload["sub"])
    except: return None

async def get_context(user=Depends(get_current_user)):
    return {"user": user, "db": db_pool}

graphql_app = GraphQLRouter(schema, context_getter=get_context)
```

---

## Permissions (Field-level)

```python
from strawberry.permission import BasePermission

class IsAuthenticated(BasePermission):
    message = "User is not authenticated"

    def has_permission(self, source, info, **kwargs):
        return info.context["user"] is not None


class IsAdmin(BasePermission):
    message = "Admin access required"

    def has_permission(self, source, info, **kwargs):
        user = info.context["user"]
        return user and user.role == "admin"


@strawberry.type
class Query:
    @strawberry.field(permission_classes=[IsAuthenticated])
    async def me(self, info) -> User: ...

    @strawberry.field(permission_classes=[IsAdmin])
    async def all_users(self, info) -> list[User]: ...
```

---

## Pagination — Relay-style

```python
@strawberry.type
class PostEdge:
    cursor: str
    node: Post

@strawberry.type
class PageInfo:
    has_next_page: bool
    end_cursor: str | None

@strawberry.type
class PostConnection:
    edges: list[PostEdge]
    page_info: PageInfo

@strawberry.type
class Query:
    @strawberry.field
    async def posts(
        self,
        first: int = 10,
        after: str | None = None
    ) -> PostConnection:
        cursor_id = decode_cursor(after) if after else 0
        rows = await db.fetch(
            "SELECT * FROM posts WHERE id > $1 ORDER BY id LIMIT $2",
            cursor_id, first + 1
        )
        has_next = len(rows) > first
        nodes = rows[:first]
        edges = [PostEdge(cursor=encode_cursor(p.id), node=p) for p in nodes]
        return PostConnection(
            edges=edges,
            page_info=PageInfo(
                has_next_page=has_next,
                end_cursor=edges[-1].cursor if edges else None
            )
        )
```

---

## File Uploads

GraphQL doesn't natively support binary. Use multipart spec.

```python
@strawberry.type
class Mutation:
    @strawberry.mutation
    async def upload_avatar(self, file: strawberry.Upload) -> str:
        data = await file.read()
        url = await s3.upload(data, key=f"avatars/{uuid4()}")
        return url
```

Client sends multipart/form-data with operations + map + files.

**Alternative (cleaner):** Use REST endpoint for upload, return URL, then GraphQL mutation refs the URL.

---

## Error Handling

```python
from graphql import GraphQLError

@strawberry.field
async def user(self, id: strawberry.ID) -> User:
    user = await db.fetch_user(id)
    if not user:
        raise GraphQLError(
            "User not found",
            extensions={"code": "NOT_FOUND", "user_id": id}
        )
    return user
```

Custom error formatter:
```python
from strawberry.fastapi import GraphQLRouter
from strawberry.schema.config import StrawberryConfig

def custom_error_formatter(error, debug):
    return {
        "message": error.message,
        "code": error.extensions.get("code", "UNKNOWN") if error.extensions else "UNKNOWN",
        "path": error.path,
    }

graphql_app = GraphQLRouter(schema, error_formatter=custom_error_formatter)
```

---

## Custom Scalars

```python
import strawberry
from datetime import datetime

DateTimeScalar = strawberry.scalar(
    datetime,
    name="DateTime",
    description="ISO 8601 datetime",
    serialize=lambda v: v.isoformat(),
    parse_value=lambda v: datetime.fromisoformat(v),
)

@strawberry.type
class Post:
    created_at: DateTimeScalar
```

---

## Enums

```python
import enum

@strawberry.enum
class Status(enum.Enum):
    ACTIVE = "active"
    PENDING = "pending"
    DISABLED = "disabled"

@strawberry.type
class User:
    status: Status
```

---

## Interfaces

```python
@strawberry.interface
class Node:
    id: strawberry.ID

@strawberry.type
class User(Node):
    name: str

@strawberry.type
class Post(Node):
    title: str
```

---

## Unions

```python
@strawberry.type
class Comment:
    text: str

SearchResult = strawberry.union(
    "SearchResult",
    types=(User, Post, Comment)
)

@strawberry.type
class Query:
    @strawberry.field
    async def search(self, q: str) -> list[SearchResult]:
        ...
```

---

## Testing

```python
import pytest
from myapp.schema import schema

@pytest.mark.asyncio
async def test_user_query():
    query = """
        query GetUser($id: ID!) {
            user(id: $id) { name email }
        }
    """
    result = await schema.execute(
        query,
        variable_values={"id": "1"},
        context_value={"user": fake_user, "db": fake_db}
    )
    assert result.errors is None
    assert result.data["user"]["name"] == "Alice"
```

No HTTP layer needed — execute against schema directly.

---

## Performance Tips

### 1. Async resolvers everywhere
Blocking calls in resolvers kill the event loop.

### 2. Use DataLoader for N+1
(See file 03.)

### 3. Limit query depth
```python
from strawberry.schema.config import StrawberryConfig
from graphql import validate

# Custom validator
def depth_limit_validator(max_depth=10):
    ...
```

### 4. Persisted queries
Whitelist queries by hash for production:
```python
# Client sends hash → server looks up query
```

### 5. Disable introspection in prod
```python
schema = strawberry.Schema(
    query=Query,
    config=StrawberryConfig(disable_introspection=True)
)
```

---

## Schema Stitching vs Federation

If you have multiple services with their own schemas:
- **Schema Stitching** (older): combine schemas at gateway.
- **Federation** (modern): each service owns part of the graph; gateway resolves.

Both covered in file 05.

---

## Pydantic Integration

Strawberry has first-class Pydantic support:

```python
from pydantic import BaseModel

class UserModel(BaseModel):
    id: int
    name: str
    email: str

@strawberry.experimental.pydantic.type(model=UserModel)
class User:
    id: strawberry.auto
    name: strawberry.auto
    email: strawberry.auto
```

Re-uses your existing Pydantic models.

---

## Comparison: Strawberry vs Ariadne vs Graphene

| | Strawberry | Ariadne | Graphene |
|---|---|---|---|
| Schema style | Code-first | Schema-first (SDL) | Code-first |
| Async support | Native | Native | Plugin |
| Type hints | First-class | Required | Decorators |
| Modern? | ✓ Most active | ✓ | Legacy |
| FastAPI integration | Excellent | Good | OK |
| Pick if... | Modern Python team | SDL-first workflow | Maintaining legacy |

---

## Common Production Setup

```python
from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter
from strawberry.tools import create_type
import strawberry
from strawberry.extensions import (
    QueryDepthLimiter,
    ParserCache,
    ValidationCache,
    AddValidationRules
)
from graphql.validation import NoSchemaIntrospectionCustomRule

schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    extensions=[
        QueryDepthLimiter(max_depth=10),
        ParserCache(maxsize=100),
        ValidationCache(maxsize=100),
        AddValidationRules([NoSchemaIntrospectionCustomRule]),  # disable introspection
    ]
)

app = FastAPI()
graphql_app = GraphQLRouter(
    schema,
    context_getter=get_context,
    graphiql=False,  # disable UI in prod
)
app.include_router(graphql_app, prefix="/graphql")
```

---

## TL;DR

- Strawberry = modern Python-typed GraphQL.
- `@strawberry.type` + `@strawberry.field` is the core.
- Context passes auth/DB.
- Permissions = `BasePermission` classes.
- Async-native; pair with FastAPI seamlessly.
- Production: disable introspection + GraphiQL, add depth limits, persisted queries.
