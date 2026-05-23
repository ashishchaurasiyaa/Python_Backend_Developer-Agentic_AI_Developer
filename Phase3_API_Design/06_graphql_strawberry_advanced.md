# GraphQL + Strawberry Advanced — Python Backend Developer Interview Prep (40 LPA)

> **Hinglish Note**: Theory explanations Hindi mein hain, code aur technical terms English mein. Ye series 40 LPA level ke liye hai — depth important hai.

---

## Table of Contents

1. [GraphQL Fundamentals Recap](#1-graphql-fundamentals-recap)
2. [Strawberry Basics](#2-strawberry-basics)
3. [Resolvers + Context](#3-resolvers--context)
4. [Queries](#4-queries)
5. [Mutations](#5-mutations)
6. [Subscriptions](#6-subscriptions)
7. [N+1 Problem + DataLoader](#7-n1-problem--dataloader)
8. [Authorization + Permissions](#8-authorization--permissions)
9. [Error Handling](#9-error-handling)
10. [File Uploads](#10-file-uploads)
11. [Schema Directives + Extensions](#11-schema-directives--extensions)
12. [Testing GraphQL](#12-testing-graphql)
13. [Performance Optimization](#13-performance-optimization)
14. [GraphQL vs REST Comparison](#14-graphql-vs-rest-comparison)
15. [10 Interview Q&As](#15-10-interview-qas)

---

## 1. GraphQL Fundamentals Recap

### GraphQL kya hai?

**GraphQL** ek query language hai API ke liye — Facebook ne 2012 mein banaya, 2015 mein open-source kiya. REST ka ek powerful alternative hai jisme **client decide karta hai** ki usse kaunsa data chahiye, server nahi.

**Core Idea**: "Ek endpoint, alag-alag queries" — REST mein `/users`, `/users/1`, `/users/1/posts` alag-alag endpoints hote hain. GraphQL mein sab kuch `/graphql` se hota hai.

### Schema — The Contract

GraphQL mein **schema** hi sab kuch hai. Ye client aur server ke beech ka contract hai.

```graphql
# GraphQL Schema Definition Language (SDL)
type User {
  id: ID!              # ! matlab non-nullable (required)
  name: String!
  email: String!
  age: Int             # nullable field
  posts: [Post!]!      # list of non-null Posts, list itself non-null
}

type Post {
  id: ID!
  title: String!
  content: String!
  author: User!
  published: Boolean!
  createdAt: String!
}
```

**Type system rules:**
- `String!` → non-nullable String (always present)
- `String` → nullable String (can be null)
- `[Post!]!` → non-nullable list of non-nullable Posts
- `[Post]` → nullable list, Post items can also be null

### Query Type — Data Padhna

```graphql
type Query {
  user(id: ID!): User          # single user, nullable return
  users: [User!]!               # list of users, never null
  posts(published: Boolean): [Post!]!
}
```

**Client query (kaise data maangega):**

```graphql
# Client sirf jo chahiye wo maange — over-fetching nahi
query GetUserWithPosts {
  user(id: "123") {
    name
    email
    posts {
      title
      published
    }
  }
}
```

### Mutation Type — Data Likhna

```graphql
type Mutation {
  createUser(name: String!, email: String!): User!
  updateUser(id: ID!, name: String): User
  deleteUser(id: ID!): Boolean!
}
```

**Client mutation:**

```graphql
mutation CreateNewUser {
  createUser(name: "Ashish", email: "ashish@example.com") {
    id
    name
    email
  }
}
```

### Subscription Type — Real-time Data

```graphql
type Subscription {
  userCreated: User!
  postPublished(authorId: ID): Post!
  messageReceived(roomId: ID!): Message!
}
```

**Client subscription:**

```graphql
subscription WatchNewPosts {
  postPublished {
    id
    title
    author {
      name
    }
  }
}
```

### Resolvers — Actual Logic

Har field ka ek **resolver** hota hai — ye function data return karta hai.

```python
# Conceptual resolver structure
resolvers = {
    "Query": {
        "user": lambda parent, args, context, info: db.get_user(args["id"]),
        "users": lambda parent, args, context, info: db.get_all_users(),
    },
    "User": {
        # Default resolver: parent.name — automatically works
        "posts": lambda parent, args, context, info: db.get_posts_by_user(parent["id"]),
    }
}
```

**4 resolver arguments (classic GraphQL):**
1. `parent` / `root` — parent object ka data
2. `args` — field ke arguments
3. `context` — request-level shared data (DB, auth user)
4. `info` — schema metadata, field name, etc.

### Introspection — Schema ko Query Karna

GraphQL ka special feature — aap schema ko query kar sakte ho!

```graphql
# Schema ke saare types dekho
query IntrospectionQuery {
  __schema {
    types {
      name
      kind
      fields {
        name
        type {
          name
        }
      }
    }
  }
}

# Specific type ki details
query {
  __type(name: "User") {
    fields {
      name
      type {
        name
        kind
      }
    }
  }
}
```

**Production mein introspection disable karo** — attacker schema ka full map bana sakta hai.

```python
# Strawberry mein introspection disable karna
schema = strawberry.Schema(
    query=Query,
    introspection=False  # Production mein ye karo
)
```

---

## 2. Strawberry Basics

### Strawberry kya hai?

**Strawberry** ek modern Python GraphQL library hai jo **type annotations** use karti hai schema define karne ke liye. Graphene ka successor/alternative hai — much cleaner, Pythonic code.

```
pip install strawberry-graphql[fastapi]
```

### `@strawberry.type` — GraphQL Object Type

```python
import strawberry
from typing import Optional
from datetime import datetime

@strawberry.type
class User:
    """GraphQL type User — yahi schema mein User type banega"""
    id: strawberry.ID           # ID scalar
    name: str                   # String!
    email: str                  # String!
    bio: Optional[str] = None   # String (nullable)
    age: Optional[int] = None   # Int (nullable)
    is_active: bool = True      # Boolean!
    created_at: datetime        # DateTime scalar
```

**Python type → GraphQL type mapping:**

| Python Type | GraphQL Type | Notes |
|-------------|-------------|-------|
| `str` | `String!` | non-null |
| `Optional[str]` | `String` | nullable |
| `int` | `Int!` | non-null |
| `float` | `Float!` | non-null |
| `bool` | `Boolean!` | non-null |
| `strawberry.ID` | `ID!` | ID scalar |
| `datetime` | `DateTime!` | custom scalar |
| `list[str]` | `[String!]!` | non-null list |
| `Optional[list[str]]` | `[String!]` | nullable list |
| `UUID` | `UUID!` | custom scalar |
| `JSON` | `JSON` | custom scalar |

### `@strawberry.input` — Input Types

Mutations ke liye complex arguments:

```python
@strawberry.input
class CreateUserInput:
    name: str
    email: str
    bio: Optional[str] = None
    role: str = "user"

@strawberry.input
class UpdateUserInput:
    name: Optional[str] = strawberry.UNSET   # UNSET = not provided
    email: Optional[str] = strawberry.UNSET
    bio: Optional[str] = strawberry.UNSET

# UNSET vs None:
# None = explicitly set to null
# UNSET = not provided at all (skip update)
```

### `@strawberry.enum` — Enum Types

```python
import strawberry
from enum import Enum

@strawberry.enum
class UserRole(Enum):
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"

@strawberry.enum
class PostStatus(Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"

@strawberry.type
class User:
    id: strawberry.ID
    name: str
    role: UserRole = UserRole.VIEWER  # default value
```

### `@strawberry.field` — Custom Resolver

Jab field ke liye custom logic chahiye:

```python
@strawberry.type
class User:
    id: strawberry.ID
    first_name: str
    last_name: str
    
    # Method-based resolver
    @strawberry.field
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
    
    # Lambda resolver (for simple cases)
    posts: list["Post"] = strawberry.field(
        resolver=lambda self, info: get_posts_by_user(self.id)
    )
    
    # With description for documentation
    @strawberry.field(description="Total post count for this user")
    def post_count(self, info: "strawberry.types.Info") -> int:
        # info se context access kar sakte ho
        return len(info.context["post_store"].get(str(self.id), []))
```

### `strawberry.Schema` — Schema Assembly

```python
@strawberry.type
class Query:
    @strawberry.field
    def hello(self) -> str:
        return "Hello World"

@strawberry.type
class Mutation:
    @strawberry.mutation
    def create_user(self, name: str) -> User:
        ...

@strawberry.type
class Subscription:
    @strawberry.subscription
    async def count(self) -> AsyncGenerator[int, None]:
        for i in range(10):
            yield i
            await asyncio.sleep(1)

# Schema banao
schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,       # optional
    subscription=Subscription,  # optional
    types=[UserRole, PostStatus],  # extra types explicitly register karo
    extensions=[...],        # extensions add karo
    scalar_overrides={...},  # custom scalars
)
```

### `strawberry.fastapi.GraphQLRouter` — FastAPI Mount

```python
from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter

app = FastAPI(title="My GraphQL API")

# GraphQL router
graphql_router = GraphQLRouter(
    schema,
    context_getter=get_context,  # function jo context return kare
    graphiql=True,               # GraphiQL playground enable (development)
    # graphiql=False  # production mein disable karo ya restrict karo
)

# Mount on /graphql
app.include_router(graphql_router, prefix="/graphql")

# Ab available hoga:
# POST /graphql — GraphQL queries/mutations
# GET  /graphql — GraphiQL playground (browser mein)
# WS   /graphql — WebSocket for subscriptions
```

### Custom Scalars

```python
from strawberry.scalars import JSON
import strawberry
from datetime import datetime
import uuid

# Built-in scalars (strawberry provides)
# strawberry.ID, str, int, float, bool

# DateTime — automatically handled
@strawberry.type
class Event:
    created_at: datetime        # → DateTime! in GraphQL

# UUID scalar
from uuid import UUID
@strawberry.type
class Resource:
    id: UUID                    # → UUID! in GraphQL

# JSON scalar — arbitrary data
from strawberry.scalars import JSON
@strawberry.type
class Config:
    metadata: JSON              # → JSON in GraphQL (any JSON value)
    settings: Optional[JSON] = None

# Custom scalar banana
MyCustomScalar = strawberry.scalar(
    str,  # underlying Python type
    name="MyCustom",
    description="Custom scalar for special data",
    serialize=lambda v: v.upper(),       # Python → JSON
    parse_value=lambda v: v.lower(),     # JSON → Python
    parse_literal=lambda ast, **kw: ast.value.lower(),
)
```

---

## 3. Resolvers + Context

### Strawberry Mein Resolver Kaise Call Hota Hai

Strawberry **method-based** resolvers use karta hai — Python class methods hi resolvers hain.

```python
@strawberry.type
class Query:
    # Ye Query.authors resolver hai
    @strawberry.field
    def authors(self) -> list["Author"]:
        # self = Query type instance (usually empty/unused)
        return list(AUTHORS_DB.values())
    
    # Arguments ke saath
    @strawberry.field
    def author(self, id: strawberry.ID) -> Optional["Author"]:
        return AUTHORS_DB.get(str(id))
    
    # info parameter ke saath (context access)
    @strawberry.field
    def me(self, info: strawberry.types.Info) -> Optional["User"]:
        user = info.context.get("current_user")
        return user
```

### `info: strawberry.types.Info` Parameter

`info` ek special parameter hai jo har resolver mein available hai:

```python
import strawberry
from strawberry.types import Info

@strawberry.type
class Query:
    @strawberry.field
    def my_field(self, info: Info) -> str:
        # info.context — dict jo context_getter ne return kiya
        db = info.context["db"]
        user = info.context["current_user"]
        
        # info.field_name — current field ka naam
        print(f"Resolving field: {info.field_name}")
        
        # info.path — full path to this field
        print(f"Field path: {info.path}")
        
        # info.selected_fields — client ne kya select kiya
        for field in info.selected_fields:
            print(f"Requested: {field.name}")
        
        # info.schema — complete schema object
        schema = info.schema
        
        # info.variable_values — query variables
        vars = info.variable_values
        
        return "data"
```

### Context Injection — `get_context` Function

Context ek **request-level shared object** hai. Har request ke liye naya context banao.

```python
from fastapi import Request, Depends
from strawberry.fastapi import BaseContext

# Simple dict context
async def get_context(request: Request) -> dict:
    return {
        "db": get_db_session(),          # DB session
        "current_user": await get_current_user(request),  # Auth user
        "redis": redis_client,            # Cache
        "author_loader": DataLoader(...), # Per-request DataLoader
    }

# Custom context class (type-safe approach)
class MyContext(BaseContext):
    def __init__(self, db: AsyncSession, user: Optional[User]):
        self.db = db
        self.user = user
        self.author_loader = DataLoader(load_fn=batch_load_authors)

async def get_context(request: Request) -> MyContext:
    # JWT token se user extract karo
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    user = await verify_token(token) if token else None
    
    async with AsyncSessionLocal() as db:
        return MyContext(db=db, user=user)

# GraphQLRouter mein pass karo
graphql_router = GraphQLRouter(schema, context_getter=get_context)
```

### DB Session via Context

```python
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, AsyncSessionLocal
from contextlib import asynccontextmanager

engine = create_async_engine("sqlite+aiosqlite:///blog.db")
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_context(request: Request) -> dict:
    async with AsyncSessionLocal() as session:
        yield {
            "db": session,
            "user": await authenticate(request),
        }
    # session automatically close ho jayega yield ke baad

# Resolver mein use karo
@strawberry.type
class Query:
    @strawberry.field
    async def users(self, info: Info) -> list[User]:
        db: AsyncSession = info.context["db"]
        result = await db.execute(select(UserModel))
        return [User.from_orm(u) for u in result.scalars().all()]
```

### Auth User in Context

```python
import jwt
from fastapi import Request

SECRET_KEY = "your-secret-key"

async def get_current_user_from_request(request: Request) -> Optional[dict]:
    """JWT token verify karo aur user return karo"""
    auth_header = request.headers.get("Authorization", "")
    
    if not auth_header.startswith("Bearer "):
        return None
    
    token = auth_header.split(" ")[1]
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("sub")
        return {"id": user_id, "role": payload.get("role", "viewer")}
    except jwt.ExpiredSignatureError:
        return None  # Token expire ho gaya
    except jwt.InvalidTokenError:
        return None  # Invalid token

async def get_context(request: Request) -> dict:
    user = await get_current_user_from_request(request)
    return {
        "current_user": user,
        "is_authenticated": user is not None,
        "is_admin": user is not None and user.get("role") == "admin",
    }
```

---

## 4. Queries

### Simple Field Queries

```python
@strawberry.type
class Query:
    # No args — list return karo
    @strawberry.field
    def all_users(self) -> list[User]:
        return list(USERS_DB.values())
    
    # Single item by ID
    @strawberry.field
    def user(self, id: strawberry.ID) -> Optional[User]:
        return USERS_DB.get(str(id))
    
    # With description
    @strawberry.field(description="Get all published posts")
    def published_posts(self) -> list[Post]:
        return [p for p in POSTS_DB.values() if p.published]
```

### Nested Objects / Relationships

```python
@strawberry.type
class Post:
    id: strawberry.ID
    title: str
    author_id: strawberry.ID
    
    # Nested resolver — author object return karo
    @strawberry.field
    def author(self, info: Info) -> Optional["Author"]:
        # self.author_id use karo related object laane ke liye
        return AUTHORS_DB.get(str(self.author_id))
    
    @strawberry.field
    def comments(self, info: Info) -> list["Comment"]:
        return [c for c in COMMENTS_DB.values() if str(c.post_id) == str(self.id)]
    
    @strawberry.field
    def comment_count(self) -> int:
        return len([c for c in COMMENTS_DB.values() if str(c.post_id) == str(self.id)])

# Client query:
# query {
#   posts {
#     title
#     author { name email }      ← nested
#     comments { text }           ← nested list
#     commentCount                ← computed field
#   }
# }
```

### Filtering Arguments

```python
@strawberry.type
class Query:
    @strawberry.field
    def posts(
        self,
        published_only: bool = False,
        author_id: Optional[strawberry.ID] = None,
        search: Optional[str] = None,
        min_comments: Optional[int] = None,
    ) -> list[Post]:
        results = list(POSTS_DB.values())
        
        if published_only:
            results = [p for p in results if p.published]
        
        if author_id:
            results = [p for p in results if str(p.author_id) == str(author_id)]
        
        if search:
            query_lower = search.lower()
            results = [
                p for p in results
                if query_lower in p.title.lower() or query_lower in p.content.lower()
            ]
        
        return results

# Client query:
# query {
#   posts(publishedOnly: true, search: "Python") {
#     id title
#   }
# }
# Note: Python snake_case → GraphQL camelCase automatic conversion
```

### Pagination — Offset-based

```python
@strawberry.type
class PostPage:
    items: list[Post]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_prev: bool

@strawberry.type
class Query:
    @strawberry.field
    def paginated_posts(
        self,
        page: int = 1,
        page_size: int = 10,
        published_only: bool = False,
    ) -> PostPage:
        all_posts = list(POSTS_DB.values())
        
        if published_only:
            all_posts = [p for p in all_posts if p.published]
        
        total = len(all_posts)
        start = (page - 1) * page_size
        end = start + page_size
        items = all_posts[start:end]
        
        return PostPage(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            has_next=end < total,
            has_prev=page > 1,
        )
```

### Pagination — Cursor-based (Production Standard)

```python
import base64
from typing import Optional

def encode_cursor(id: str) -> str:
    """ID ko opaque cursor mein convert karo"""
    return base64.b64encode(f"post:{id}".encode()).decode()

def decode_cursor(cursor: str) -> str:
    """Cursor se ID extract karo"""
    decoded = base64.b64decode(cursor.encode()).decode()
    return decoded.split(":", 1)[1]  # "post:123" → "123"

@strawberry.type
class PostEdge:
    node: Post
    cursor: str

@strawberry.type
class PageInfo:
    has_next_page: bool
    has_prev_page: bool
    start_cursor: Optional[str]
    end_cursor: Optional[str]

@strawberry.type
class PostConnection:
    edges: list[PostEdge]
    page_info: PageInfo
    total_count: int

@strawberry.type
class Query:
    @strawberry.field
    def posts_connection(
        self,
        first: Optional[int] = 10,   # next N items
        after: Optional[str] = None, # cursor ke baad
        last: Optional[int] = None,  # prev N items
        before: Optional[str] = None,
    ) -> PostConnection:
        all_posts = sorted(POSTS_DB.values(), key=lambda p: p.id)
        
        # after cursor se filter
        if after:
            after_id = decode_cursor(after)
            all_posts = [p for p in all_posts if str(p.id) > after_id]
        
        total = len(all_posts)
        posts = all_posts[:first] if first else all_posts
        
        edges = [
            PostEdge(node=p, cursor=encode_cursor(str(p.id)))
            for p in posts
        ]
        
        return PostConnection(
            edges=edges,
            page_info=PageInfo(
                has_next_page=len(all_posts) > (first or 0),
                has_prev_page=after is not None,
                start_cursor=edges[0].cursor if edges else None,
                end_cursor=edges[-1].cursor if edges else None,
            ),
            total_count=total,
        )

# Client query (Relay-style):
# query {
#   postsConnection(first: 5, after: "cG9zdDox") {
#     edges {
#       cursor
#       node { id title }
#     }
#     pageInfo { hasNextPage endCursor }
#   }
# }
```

### Query Complexity Limiting

```python
from strawberry.extensions import QueryDepthLimiter

# Depth limiting — zyada nested queries block karo
schema = strawberry.Schema(
    query=Query,
    extensions=[QueryDepthLimiter(max_depth=5)]
)

# Custom complexity limiter
from strawberry.extensions import SchemaExtension

class ComplexityLimiter(SchemaExtension):
    MAX_COMPLEXITY = 100
    
    def on_executing_start(self):
        query = self.execution_context.query
        # complexity calculate karo fields count se
        complexity = query.count("{")  # simplified
        
        if complexity > self.MAX_COMPLEXITY:
            raise Exception(f"Query too complex: {complexity} > {self.MAX_COMPLEXITY}")
```

---

## 5. Mutations

### Basic Mutation

```python
@strawberry.type
class Mutation:
    @strawberry.mutation
    def create_user(self, name: str, email: str) -> User:
        user_id = str(len(USERS_DB) + 1)
        user = User(id=user_id, name=name, email=email, created_at=datetime.now())
        USERS_DB[user_id] = user
        return user
    
    @strawberry.mutation
    def delete_user(self, id: strawberry.ID) -> bool:
        user_id = str(id)
        if user_id in USERS_DB:
            del USERS_DB[user_id]
            return True
        return False
```

### Input Types for Complex Arguments

```python
@strawberry.input
class CreatePostInput:
    title: str
    content: str
    author_id: strawberry.ID
    published: bool = False
    tags: list[str] = strawberry.field(default_factory=list)

@strawberry.input
class UpdatePostInput:
    title: Optional[str] = strawberry.UNSET
    content: Optional[str] = strawberry.UNSET
    published: Optional[bool] = strawberry.UNSET

@strawberry.type
class Mutation:
    @strawberry.mutation
    def create_post(self, input: CreatePostInput, info: Info) -> Post:
        # input.title, input.content, etc.
        user = info.context.get("current_user")
        post_id = str(len(POSTS_DB) + 1)
        
        post = Post(
            id=post_id,
            title=input.title,
            content=input.content,
            author_id=input.author_id,
            published=input.published,
            created_at=datetime.now(),
        )
        POSTS_DB[post_id] = post
        return post
    
    @strawberry.mutation
    def update_post(self, id: strawberry.ID, input: UpdatePostInput) -> Optional[Post]:
        post = POSTS_DB.get(str(id))
        if not post:
            return None
        
        # UNSET check — sirf provided fields update karo
        if input.title is not strawberry.UNSET:
            post.title = input.title
        if input.content is not strawberry.UNSET:
            post.content = input.content
        if input.published is not strawberry.UNSET:
            post.published = input.published
        
        POSTS_DB[str(id)] = post
        return post
```

### Error Handling in Mutations — Result Union Types

**Best practice**: Mutations ko sirf exception throw nahi karna chahiye — instead, typed error return karo.

```python
# Error types define karo
@strawberry.type
class UserNotFound:
    message: str = "User not found"
    user_id: strawberry.ID

@strawberry.type
class PostNotFound:
    message: str = "Post not found"
    post_id: strawberry.ID

@strawberry.type
class PermissionDenied:
    message: str = "You don't have permission to perform this action"
    required_role: Optional[str] = None

@strawberry.type
class ValidationError:
    message: str
    field: str

# Union types
PostResult = strawberry.union("PostResult", [Post, PostNotFound])
CreatePostResult = strawberry.union("CreatePostResult", [Post, ValidationError, PermissionDenied])
UpdatePostResult = strawberry.union("UpdatePostResult", [Post, PostNotFound, PermissionDenied])

@strawberry.type
class Mutation:
    @strawberry.mutation
    def get_post_for_edit(self, id: strawberry.ID, info: Info) -> PostResult:
        # Type annotation mein union use karo
        post = POSTS_DB.get(str(id))
        
        if not post:
            return PostNotFound(post_id=id)  # Error type return karo
        
        return post  # Success
    
    @strawberry.mutation
    def update_post_safe(
        self, id: strawberry.ID, input: UpdatePostInput, info: Info
    ) -> UpdatePostResult:
        user = info.context.get("current_user")
        
        if not user:
            return PermissionDenied(required_role="any")
        
        post = POSTS_DB.get(str(id))
        if not post:
            return PostNotFound(post_id=id)
        
        # Only author ya admin update kar sakta hai
        if str(post.author_id) != str(user["id"]) and user.get("role") != "admin":
            return PermissionDenied(required_role="admin or post author")
        
        # Update karo
        if input.title is not strawberry.UNSET:
            post.title = input.title
        
        return post

# Client mutation:
# mutation {
#   updatePostSafe(id: "1", input: {title: "New Title"}) {
#     ... on Post { id title }
#     ... on PostNotFound { message postId }
#     ... on PermissionDenied { message requiredRole }
#   }
# }
```

---

## 6. Subscriptions

### Basic Subscription — Async Generator

```python
import asyncio
from typing import AsyncGenerator

@strawberry.type
class Subscription:
    @strawberry.subscription
    async def count_down(self, from_number: int = 10) -> AsyncGenerator[int, None]:
        """Simple countdown subscription"""
        for i in range(from_number, 0, -1):
            yield i
            await asyncio.sleep(1)
    
    @strawberry.subscription
    async def post_added(self) -> AsyncGenerator["Post", None]:
        """New post add hone pe notify karo"""
        # Production mein: Redis pub/sub ya asyncio.Queue use karo
        # Demo: simulate karo
        for i in range(5):
            await asyncio.sleep(2)
            new_post = Post(
                id=f"live-{i}",
                title=f"Live Post {i}",
                content="Just published!",
                author_id="1",
                published=True,
                created_at=datetime.now(),
            )
            yield new_post
```

### Real-time Event System — asyncio.Queue

```python
import asyncio
from typing import AsyncGenerator

# Global event queues (production mein Redis use karo)
_post_queues: list[asyncio.Queue] = []

async def publish_post_event(post: Post):
    """Naya post publish karo — saare subscribers ko notify karo"""
    for queue in _post_queues:
        await queue.put(post)

@strawberry.type
class Subscription:
    @strawberry.subscription
    async def post_added(self, info: Info) -> AsyncGenerator[Post, None]:
        """New posts ki real-time stream"""
        queue = asyncio.Queue()
        _post_queues.append(queue)
        
        try:
            while True:
                post = await queue.get()
                yield post
        finally:
            # Cleanup when client disconnects
            _post_queues.remove(queue)
    
    @strawberry.subscription
    async def comment_added(
        self, post_id: strawberry.ID
    ) -> AsyncGenerator["Comment", None]:
        """Specific post ke comments watch karo"""
        queue = asyncio.Queue()
        _comment_queues[str(post_id)].append(queue)
        
        try:
            while True:
                comment = await queue.get()
                yield comment
        finally:
            _comment_queues[str(post_id)].remove(queue)
```

### WebSocket Protocol — graphql-ws

GraphQL subscriptions **WebSocket** use karte hain HTTP ke jagah.

**Protocol flow:**
```
Client → Server: WebSocket upgrade request
Server → Client: 101 Switching Protocols
Client → Server: connection_init (optional auth params)
Server → Client: connection_ack
Client → Server: subscribe { id: "1", query: "subscription { ... }" }
Server → Client: next { id: "1", data: { ... } }  ← repeated
Server → Client: next { id: "1", data: { ... } }
...
Client → Server: complete { id: "1" }  ← unsubscribe
```

**Two protocols:**
1. `graphql-ws` — newer, recommended (npm: `graphql-ws`)
2. `subscriptions-transport-ws` — older (deprecated)

```python
# Strawberry automatically handles WebSocket
# FastAPI + Strawberry = built-in WebSocket support

from strawberry.fastapi import GraphQLRouter

graphql_router = GraphQLRouter(
    schema,
    context_getter=get_context,
    # WebSocket automatically handled
)

app.include_router(graphql_router, prefix="/graphql")

# Client (JavaScript):
# import { createClient } from 'graphql-ws';
# const client = createClient({ url: 'ws://localhost:8000/graphql' });
# client.subscribe({ query: 'subscription { postAdded { title } }' }, {
#   next: (data) => console.log(data),
# });
```

### Strawberry + FastAPI WebSocket Full Setup

```python
from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter
import strawberry

app = FastAPI()

# Subscription ke liye lifespan event
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: background tasks, connections
    yield
    # Shutdown: cleanup

schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    subscription=Subscription,
)

graphql_router = GraphQLRouter(
    schema,
    context_getter=get_context,
    subscription_protocols=[
        "graphql-transport-ws",  # newer protocol
        "graphql-ws",             # legacy support
    ],
)

app.include_router(graphql_router, prefix="/graphql")
```

---

## 7. N+1 Problem + DataLoader

### N+1 Problem — Interview Mein Zaroor Poochha Jaata Hai

**N+1 problem**: List query mein har item ke liye ek alag DB query fire hoti hai.

```
# GraphQL query:
query {
  posts {          ← 1 query: SELECT * FROM posts (returns 100 posts)
    title
    author {       ← 100 queries: SELECT * FROM users WHERE id = ?
      name         ← N+1 = 1 + 100 = 101 queries!
    }
  }
}
```

**Bina DataLoader ke:**

```python
@strawberry.type
class Post:
    author_id: strawberry.ID
    
    @strawberry.field
    def author(self, info: Info) -> Optional[Author]:
        # Har post ke liye ye resolver call hoga separately!
        # 100 posts → 100 DB queries
        return db.query(User).filter(User.id == self.author_id).first()
        # ^^^ YE N+1 PROBLEM HAI!
```

**Timing example:**
```
Without DataLoader:
- Get 100 posts: 5ms
- Get author for post 1: 2ms
- Get author for post 2: 2ms
- ... (x100)
- Total: 5 + (100 * 2) = 205ms

With DataLoader:
- Get 100 posts: 5ms
- Batch get 100 authors: 8ms
- Total: 13ms
```

### DataLoader Pattern

**Key concepts:**
1. **Batching**: Multiple individual requests ko ek batch mein combine karo
2. **Caching**: Same request pe cache return karo (per-request scope)
3. **Scheduling**: Event loop ke next tick mein execute karo

```python
from strawberry.dataloader import DataLoader
from typing import Sequence

# Batch function — ye ek baar mein saare keys load karta hai
async def batch_load_authors(
    author_ids: Sequence[strawberry.ID]
) -> list[Optional[Author]]:
    """
    Keys: [1, 2, 3, 5, 8]  ← sirf unique IDs jinhe post.author ne maanga
    Return: [Author(1), Author(2), Author(3), None, Author(8)]
    ↑ Same order maintain karo! None for missing
    """
    print(f"[DataLoader] Batch loading authors: {author_ids}")
    # Ek query mein saare authors
    all_ids = [str(id) for id in author_ids]
    
    # DB se ek query mein laao
    authors_map = {
        str(a.id): a
        for a in [AUTHORS_DB.get(id) for id in all_ids]
        if a is not None
    }
    
    # Same order mein return karo (None for missing)
    return [authors_map.get(str(id)) for id in author_ids]

# Per-request DataLoader create karo
def get_context() -> dict:
    return {
        # Har request ke liye naya DataLoader — fresh cache
        "author_loader": DataLoader(load_fn=batch_load_authors),
        "comment_loader": DataLoader(load_fn=batch_load_comments),
    }
```

### DataLoader Usage in Resolvers

```python
@strawberry.type
class Post:
    author_id: strawberry.ID
    
    @strawberry.field
    async def author(self, info: Info) -> Optional[Author]:
        # DataLoader use karo direct DB call ki jagah
        loader = info.context["author_loader"]
        
        # load() — async, batches multiple calls
        author = await loader.load(self.author_id)
        return author
    
    @strawberry.field
    async def comments(self, info: Info) -> list[Comment]:
        loader = info.context["comment_loader"]
        comments = await loader.load(self.id)  # post_id se comments load
        return comments or []
```

### `load` vs `load_many`

```python
# Single key load
author = await loader.load("user-123")

# Multiple keys at once
authors = await loader.load_many(["user-1", "user-2", "user-3"])
# Returns: [Author1, Author2, Author3]
```

### DataLoader ka Advanced Usage — Nested Relations

```python
# Complex DataLoader — multiple levels
async def batch_load_comments_by_post(
    post_ids: Sequence[strawberry.ID]
) -> list[list[Comment]]:
    """Each post ke liye comments list return karo"""
    all_comments = list(COMMENTS_DB.values())
    
    # Group by post_id
    comments_by_post: dict[str, list[Comment]] = {}
    for comment in all_comments:
        post_key = str(comment.post_id)
        if post_key not in comments_by_post:
            comments_by_post[post_key] = []
        comments_by_post[post_key].append(comment)
    
    # Same order mein return karo
    return [comments_by_post.get(str(post_id), []) for post_id in post_ids]

# Context mein add karo
async def get_context() -> dict:
    return {
        "author_loader": DataLoader(load_fn=batch_load_authors),
        "comments_loader": DataLoader(load_fn=batch_load_comments_by_post),
        "post_count_loader": DataLoader(load_fn=batch_load_post_counts),
    }
```

---

## 8. Authorization + Permissions

### `BasePermission` — Permission Classes

```python
import strawberry
from strawberry.permission import BasePermission
from strawberry.types import Info
from typing import Any

class IsAuthenticated(BasePermission):
    message = "User is not authenticated. Please provide valid token."
    
    def has_permission(
        self, source: Any, info: Info, **kwargs: Any
    ) -> bool:
        user = info.context.get("current_user")
        return user is not None

class IsAdmin(BasePermission):
    message = "Admin role required for this operation."
    
    def has_permission(
        self, source: Any, info: Info, **kwargs: Any
    ) -> bool:
        user = info.context.get("current_user")
        if not user:
            return False
        return user.get("role") == "admin"

class IsPostAuthor(BasePermission):
    message = "Only the post author can perform this action."
    
    def has_permission(
        self, source: Any, info: Info, **kwargs: Any
    ) -> bool:
        user = info.context.get("current_user")
        if not user:
            return False
        
        # `source` object pe check karo
        if hasattr(source, "author_id"):
            return str(source.author_id) == str(user["id"])
        
        # kwargs mein post_id ho sakta hai
        post_id = kwargs.get("id") or kwargs.get("post_id")
        if post_id:
            post = POSTS_DB.get(str(post_id))
            return post and str(post.author_id) == str(user["id"])
        
        return False
```

### Field-level Permissions

```python
@strawberry.type
class Query:
    # Public field — koi bhi access kar sakta hai
    @strawberry.field
    def public_posts(self) -> list[Post]:
        return [p for p in POSTS_DB.values() if p.published]
    
    # Authenticated field
    @strawberry.field(permission_classes=[IsAuthenticated])
    def my_drafts(self, info: Info) -> list[Post]:
        user = info.context["current_user"]
        return [
            p for p in POSTS_DB.values()
            if str(p.author_id) == str(user["id"]) and not p.published
        ]
    
    # Admin-only field
    @strawberry.field(permission_classes=[IsAdmin])
    def all_users(self, info: Info) -> list[User]:
        return list(USERS_DB.values())
    
    # Multiple permissions (AND logic — saare pass hone chahiye)
    @strawberry.field(permission_classes=[IsAuthenticated, IsAdmin])
    def admin_dashboard(self) -> dict:
        return {"stats": "..."}

@strawberry.type
class Mutation:
    @strawberry.mutation(permission_classes=[IsAuthenticated])
    def create_post(self, input: CreatePostInput, info: Info) -> Post:
        user = info.context["current_user"]
        ...
    
    @strawberry.mutation(permission_classes=[IsAdmin])
    def delete_user(self, user_id: strawberry.ID) -> bool:
        ...
```

### JWT Token Validation — Production Pattern

```python
from datetime import datetime, timedelta
import jwt
from typing import Optional

SECRET_KEY = "super-secret-key-change-in-production"
ALGORITHM = "HS256"

def create_token(user_id: str, role: str) -> str:
    """JWT token create karo"""
    payload = {
        "sub": user_id,
        "role": role,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=24),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str) -> Optional[dict]:
    """Token verify karo aur user data return karo"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {
            "id": payload["sub"],
            "role": payload.get("role", "viewer"),
        }
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

async def get_context(request: Request) -> dict:
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    user = verify_token(token) if token else None
    
    return {
        "current_user": user,
        "author_loader": DataLoader(load_fn=batch_load_authors),
    }

# Mutation query:
# mutation {
#   createPost(input: {title: "...", content: "...", authorId: "1"}) {
#     id title
#   }
# }
# Headers: { "Authorization": "Bearer eyJ..." }
```

---

## 9. Error Handling

### Default GraphQL Error Format

Jab exception throw hota hai, GraphQL is format mein response deta hai:

```json
{
  "data": {
    "post": null
  },
  "errors": [
    {
      "message": "Post not found",
      "locations": [{ "line": 2, "column": 3 }],
      "path": ["post"],
      "extensions": {
        "code": "NOT_FOUND"
      }
    }
  ]
}
```

**Issue**: `data` partial hota hai, errors alag hote hain — client ko dono handle karne padte hain.

### Better Pattern: Union Result Types

```python
# === Error Types ===
@strawberry.type
class NotFoundError:
    message: str
    resource_type: str
    resource_id: str
    
    @classmethod
    def for_post(cls, post_id: str) -> "NotFoundError":
        return cls(
            message=f"Post with id '{post_id}' not found",
            resource_type="Post",
            resource_id=post_id,
        )

@strawberry.type
class PermissionError:
    message: str
    required_permission: str

@strawberry.type
class ValidationError:
    message: str
    field: str
    code: str

# === Union Types ===
PostQueryResult = strawberry.union(
    "PostQueryResult",
    [Post, NotFoundError]
)

CreatePostResult = strawberry.union(
    "CreatePostResult",
    [Post, ValidationError, PermissionError]
)

# === Resolver with Union Return ===
@strawberry.type
class Query:
    @strawberry.field
    def post(self, id: strawberry.ID) -> PostQueryResult:
        post = POSTS_DB.get(str(id))
        
        if not post:
            return NotFoundError.for_post(str(id))
        
        return post  # Actual post return karo

@strawberry.type
class Mutation:
    @strawberry.mutation(permission_classes=[IsAuthenticated])
    def create_post(
        self, input: CreatePostInput, info: Info
    ) -> CreatePostResult:
        # Validation
        if len(input.title) < 3:
            return ValidationError(
                message="Title must be at least 3 characters",
                field="title",
                code="TOO_SHORT",
            )
        
        if len(input.title) > 200:
            return ValidationError(
                message="Title cannot exceed 200 characters",
                field="title",
                code="TOO_LONG",
            )
        
        # Permission check
        user = info.context["current_user"]
        if str(input.author_id) != str(user["id"]):
            return PermissionError(
                message="You can only create posts as yourself",
                required_permission="own_author_id",
            )
        
        # Create post
        post = Post(...)
        return post

# Client query with inline fragments:
# query {
#   post(id: "99") {
#     ... on Post {
#       id title content
#     }
#     ... on NotFoundError {
#       message resourceType resourceId
#     }
#   }
# }
```

### Extensions for Error Tracking

```python
from strawberry.extensions import SchemaExtension
import traceback
import logging

logger = logging.getLogger(__name__)

class ErrorTrackingExtension(SchemaExtension):
    """Errors ko Sentry/logging system mein track karo"""
    
    def on_executing_end(self):
        result = self.execution_context.result
        
        if result and result.errors:
            for error in result.errors:
                # Log karo
                logger.error(
                    "GraphQL error",
                    extra={
                        "error": str(error),
                        "query": self.execution_context.query,
                        "variables": self.execution_context.variables,
                    }
                )
                # Sentry mein bhejo
                # sentry_sdk.capture_exception(error.original_error)

schema = strawberry.Schema(
    query=Query,
    extensions=[ErrorTrackingExtension]
)
```

---

## 10. File Uploads

### Strawberry Upload Scalar

```python
from strawberry.file_uploads import Upload
import strawberry
from typing import Optional

@strawberry.type
class UploadedFile:
    filename: str
    content_type: str
    size: int
    url: str  # Stored path/URL

@strawberry.type
class Mutation:
    @strawberry.mutation
    async def upload_avatar(
        self,
        file: Upload,  # Upload scalar — special multipart handling
        user_id: strawberry.ID,
    ) -> UploadedFile:
        # file is a UploadFile object (FastAPI/Starlette)
        content = await file.read()
        filename = file.filename
        content_type = file.content_type
        
        # File save karo (local ya S3)
        save_path = f"/uploads/avatars/{user_id}_{filename}"
        with open(save_path, "wb") as f:
            f.write(content)
        
        return UploadedFile(
            filename=filename,
            content_type=content_type,
            size=len(content),
            url=f"/static/avatars/{user_id}_{filename}",
        )
    
    @strawberry.mutation
    async def upload_multiple(
        self,
        files: list[Upload],
    ) -> list[UploadedFile]:
        results = []
        for file in files:
            content = await file.read()
            results.append(UploadedFile(
                filename=file.filename,
                content_type=file.content_type,
                size=len(content),
                url=f"/uploads/{file.filename}",
            ))
        return results
```

### Multipart Upload Spec

```
# HTTP Request format (multipart/form-data):
POST /graphql
Content-Type: multipart/form-data; boundary=----FormBoundary

------FormBoundary
Content-Disposition: form-data; name="operations"

{"query": "mutation Upload($file: Upload!) { uploadAvatar(file: $file, userId: \"1\") { url } }", "variables": {"file": null}}
------FormBoundary
Content-Disposition: form-data; name="map"

{"0": ["variables.file"]}
------FormBoundary
Content-Disposition: form-data; name="0"; filename="avatar.jpg"
Content-Type: image/jpeg

<binary data>
------FormBoundary--
```

---

## 11. Schema Directives + Extensions

### Built-in Directives

```python
@strawberry.type
class User:
    id: strawberry.ID
    name: str
    
    # @deprecated directive
    old_username: Optional[str] = strawberry.field(
        deprecation_reason="Use 'name' field instead. Will be removed in v3."
    )

# Schema mein deprecated field dikhega with reason
# GraphiQL mein strikethrough show hoga
```

### Custom Schema Directives

```python
from strawberry.schema_directives import SchemaDirective, Location
from strawberry.types import DirectiveLocation

@strawberry.schema_directive(
    locations=[DirectiveLocation.FIELD_DEFINITION],
    description="Mark field as requiring specific permission"
)
class RequiresPermission:
    permission: str

@strawberry.type
class User:
    id: strawberry.ID
    
    @strawberry.field(
        directives=[RequiresPermission(permission="read:secrets")]
    )
    def secret_data(self) -> str:
        return "classified"
```

### Query Extensions — Timing, Complexity

```python
from strawberry.extensions import SchemaExtension
import time

class TimingExtension(SchemaExtension):
    """Har query ka execution time track karo"""
    
    def on_executing_start(self):
        self.start_time = time.perf_counter()
    
    def on_executing_end(self):
        elapsed = time.perf_counter() - self.start_time
        result = self.execution_context.result
        
        if result:
            if result.extensions is None:
                result.extensions = {}
            result.extensions["timing"] = {
                "execution_ms": round(elapsed * 1000, 2)
            }

class QueryComplexityExtension(SchemaExtension):
    """Query ki complexity score track karo"""
    
    MAX_COMPLEXITY = 100
    
    def on_parsing_end(self):
        # Parse karo aur complexity count karo
        query = self.execution_context.query
        # Simple heuristic: count fields
        complexity = query.count(":") + query.count("{") // 2
        
        if complexity > self.MAX_COMPLEXITY:
            from graphql import GraphQLError
            self.execution_context.errors = [
                GraphQLError(f"Query complexity {complexity} exceeds limit {self.MAX_COMPLEXITY}")
            ]

schema = strawberry.Schema(
    query=Query,
    extensions=[
        QueryDepthLimiter(max_depth=5),
        TimingExtension,
        QueryComplexityExtension,
    ]
)
```

### `AddTracingExtension`

```python
from strawberry.extensions.tracing import ApolloTracingExtension

schema = strawberry.Schema(
    query=Query,
    extensions=[ApolloTracingExtension]  # Apollo Studio tracing format
)

# Response mein extra data add hoga:
# {
#   "data": {...},
#   "extensions": {
#     "tracing": {
#       "version": 1,
#       "startTime": "...",
#       "endTime": "...",
#       "duration": 12345,
#       "execution": { "resolvers": [...] }
#     }
#   }
# }
```

---

## 12. Testing GraphQL

### `schema.execute()` — Synchronous Tests

```python
import strawberry
import asyncio

# Schema directly execute karo (no HTTP needed)
def test_query_basic():
    result = schema.execute_sync(
        """
        query {
            authors {
                id
                name
            }
        }
        """
    )
    assert not result.errors
    assert len(result.data["authors"]) > 0
```

### `await schema.execute_async()` — Async Tests

```python
import pytest
import asyncio

@pytest.mark.asyncio
async def test_posts_query():
    result = await schema.execute_async(
        """
        query GetPosts($publishedOnly: Boolean) {
            posts(publishedOnly: $publishedOnly) {
                id
                title
                published
            }
        }
        """,
        variable_values={"publishedOnly": True},
        context_value=get_context(),  # Mock context pass karo
    )
    
    assert not result.errors, f"Errors: {result.errors}"
    posts = result.data["posts"]
    assert all(p["published"] for p in posts)

@pytest.mark.asyncio
async def test_mutation_create_post():
    context = get_context()
    context["current_user"] = {"id": "1", "role": "editor"}
    
    result = await schema.execute_async(
        """
        mutation CreatePost($input: CreatePostInput!) {
            createPost(input: $input) {
                id
                title
                content
            }
        }
        """,
        variable_values={
            "input": {
                "title": "Test Post",
                "content": "Test content",
                "authorId": "1",
                "published": False,
            }
        },
        context_value=context,
    )
    
    assert not result.errors
    assert result.data["createPost"]["title"] == "Test Post"

@pytest.mark.asyncio
async def test_union_result():
    """Union type test karo"""
    result = await schema.execute_async(
        """
        query {
            post(id: "nonexistent-id-12345") {
                ... on Post {
                    id
                    title
                }
                ... on PostNotFound {
                    message
                    postId
                }
            }
        }
        """,
        context_value=get_context(),
    )
    
    assert not result.errors
    post_result = result.data["post"]
    # PostNotFound hona chahiye
    assert "message" in post_result
    assert "postId" in post_result
```

### `GraphQLTestClient` — HTTP Level Testing

```python
from strawberry.test import GraphQLTestClient
from fastapi.testclient import TestClient

# FastAPI TestClient use karo
def test_via_http():
    client = TestClient(app)
    
    response = client.post(
        "/graphql",
        json={
            "query": """
                query {
                    authors {
                        id name
                    }
                }
            """
        },
        headers={"Authorization": "Bearer valid-token-here"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "errors" not in data
```

### Mocking DataLoaders in Tests

```python
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_with_mock_dataloader():
    """DataLoader mock karo test mein"""
    
    mock_author = Author(id="1", name="Ashish", email="ashish@test.com")
    
    # Mock DataLoader
    mock_author_loader = MagicMock()
    mock_author_loader.load = AsyncMock(return_value=mock_author)
    mock_author_loader.load_many = AsyncMock(return_value=[mock_author])
    
    context = {
        "current_user": {"id": "1", "role": "admin"},
        "author_loader": mock_author_loader,
    }
    
    result = await schema.execute_async(
        """
        query {
            posts {
                title
                author { name }
            }
        }
        """,
        context_value=context,
    )
    
    assert not result.errors
    # Verify DataLoader was called
    mock_author_loader.load.assert_called()

@pytest.fixture
def test_context():
    """Reusable test context fixture"""
    return {
        "current_user": {"id": "1", "role": "admin"},
        "author_loader": DataLoader(load_fn=batch_load_authors),
    }

@pytest.fixture(autouse=True)
def reset_db():
    """Har test se pehle fresh data"""
    seed_data()
    yield
    # Cleanup
    POSTS_DB.clear()
    AUTHORS_DB.clear()
    COMMENTS_DB.clear()
```

---

## 13. Performance Optimization

### Query Depth Limiting

```python
from strawberry.extensions import QueryDepthLimiter

schema = strawberry.Schema(
    query=Query,
    extensions=[QueryDepthLimiter(max_depth=5)]
)

# Ye query block ho jayegi (depth = 6):
# query {
#   posts {                    # depth 1
#     author {                 # depth 2
#       posts {                # depth 3
#         comments {           # depth 4
#           author {           # depth 5
#             posts { title }  # depth 6 — BLOCKED!
#           }
#         }
#       }
#     }
#   }
# }
```

### Query Complexity Scoring

```python
# Har field ko cost assign karo
# Simple fields: 1 point
# Lists: multiplier lagao (estimated items * field cost)

field_costs = {
    "Query.posts": 10,      # Expensive — full list
    "Query.users": 10,
    "Post.comments": 5,     # Also expensive
    "Post.author": 1,       # Single object — cheap
    "Author.posts": 10,     # Expensive
}

class ComplexityExtension(SchemaExtension):
    FIELD_COSTS = field_costs
    MAX_COMPLEXITY = 100
    
    def calculate_complexity(self, query: str) -> int:
        # Simplified: count expensive fields
        total = 0
        for field, cost in self.FIELD_COSTS.items():
            field_name = field.split(".")[-1]
            # camelCase convert karo
            camel = ''.join(w.capitalize() if i else w for i, w in enumerate(field_name.split('_')))
            if camel in query or field_name in query:
                total += cost
        return max(total, 1)
```

### Persisted Queries

```python
# Client-side: query hash store karo
# Server-side: hash se query retrieve karo (bandwidth save)

QUERY_STORE: dict[str, str] = {}

@app.post("/graphql/persist")
async def persist_query(query: str, hash: str):
    """Query ko persist karo"""
    QUERY_STORE[hash] = query
    return {"status": "persisted", "hash": hash}

# Automatic persisted queries (APQ):
# Client first sirf hash bhejta hai
# Server: hash mein query mili? → execute karo
# Server: nahi mili? → 404 return karo
# Client: query bhi bhejta hai
# Server: query execute karo aur persist karo
```

### Field-level Caching

```python
import functools
from datetime import datetime, timedelta

_field_cache: dict = {}

def cached_field(ttl_seconds: int = 60):
    """Field result cache karo"""
    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            cache_key = f"{fn.__name__}:{args}:{kwargs}"
            
            if cache_key in _field_cache:
                value, expiry = _field_cache[cache_key]
                if datetime.now() < expiry:
                    return value
            
            result = await fn(*args, **kwargs)
            _field_cache[cache_key] = (result, datetime.now() + timedelta(seconds=ttl_seconds))
            return result
        return wrapper
    return decorator

@strawberry.type
class Query:
    @strawberry.field
    @cached_field(ttl_seconds=300)  # 5 minutes cache
    async def popular_posts(self) -> list[Post]:
        # Expensive computation — cache karo
        return sorted(POSTS_DB.values(), key=lambda p: p.view_count, reverse=True)[:10]
```

### Projections — Over-fetching Avoid Karna

```python
@strawberry.type
class Query:
    @strawberry.field
    async def posts(self, info: Info) -> list[Post]:
        # Client ne kaunse fields maange — ye check karo
        requested_fields = {
            field.name
            for selection in info.selected_fields
            for field in (selection.selections or [])
        }
        
        # Agar author nahi maanga, join mat karo
        if "author" not in requested_fields:
            # Simple query without JOIN
            return await db.execute("SELECT id, title, content FROM posts")
        else:
            # JOIN query
            return await db.execute(
                "SELECT p.*, u.name as author_name FROM posts p JOIN users u ON p.author_id = u.id"
            )
```

---

## 14. GraphQL vs REST Comparison

| Aspect | REST | GraphQL |
|--------|------|---------|
| **Data Fetching** | Fixed endpoints, fixed response | Client specifies exact fields needed |
| **Over-fetching** | Common — server decides response shape | Eliminated — client asks only what it needs |
| **Under-fetching** | Multiple requests needed (waterfall) | Single query, nested data |
| **Versioning** | URL versioning (`/v1/`, `/v2/`) | Schema evolution, `@deprecated` directive |
| **Caching** | HTTP cache (GET requests), CDN friendly | More complex, persisted queries needed |
| **Learning Curve** | Low — familiar HTTP concepts | Medium — new query language |
| **Tooling** | Swagger/OpenAPI, Postman | GraphiQL, Apollo Studio, GraphQL Playground |
| **Type Safety** | Optional (OpenAPI schema) | Built-in — schema is the contract |
| **Real-time** | Polling or WebSocket (custom) | Subscriptions (built-in) |
| **Error Handling** | HTTP status codes (200, 400, 404, 500) | Always 200, errors in response body |
| **File Upload** | Multipart form data | Multipart spec (more complex) |
| **Batch Requests** | Multiple HTTP calls | Single query with multiple fields |
| **Introspection** | OpenAPI spec (manual) | Built-in runtime introspection |
| **Performance** | Predictable, HTTP cache works | N+1 problem, DataLoader needed |
| **Mobile Friendly** | OK | Better — less data transfer |
| **Team Contracts** | API docs | Schema as living documentation |
| **Monitoring** | Standard HTTP metrics | Field-level analytics possible |
| **When to Choose** | Simple CRUD, public API, CDN needed | Complex data graphs, mobile apps, rapid iteration |

**Kab GraphQL choose karo:**
- Frontend teams independent honi chahiye (backend change without redeployment)
- Mobile apps (limited bandwidth, precise data fetching)
- Complex relationships (social networks, e-commerce)
- Rapid product iteration (schema evolution without versioning)

**Kab REST choose karo:**
- Simple CRUD operations
- Public APIs (developer experience better)
- Heavy caching needed (CDN, HTTP cache)
- File uploads heavy hain
- Team GraphQL se unfamiliar hai

---

## 15. 10 Interview Q&As

### Q1: N+1 Problem kya hai aur DataLoader kaise solve karta hai?

**Answer:**

N+1 problem tab hota hai jab ek parent query return karti hai N items, aur phir har item ke liye ek alag DB query fire hoti hai related data ke liye. Total = 1 + N queries.

**Example:** 100 posts query karo, phir har post ke `author` field resolve hone pe 100 separate `SELECT * FROM users WHERE id = ?` queries.

**DataLoader solution:**
- Request ke dauraan saare `author.load(id)` calls collect karta hai
- Event loop ke next tick mein ek batch call karta hai: `batch_load_authors([id1, id2, ..., id100])`
- Ek DB query mein 100 users laata hai
- Result cache karta hai (same request mein same id dobara maange toh DB nahi jaata)

**Result:** 101 queries → 2 queries (1 for posts, 1 batch for authors)

---

### Q2: DataLoader ka main benefit batao

**Answer:**

1. **Batching**: Multiple individual requests ko ek DB query mein combine karo
2. **Caching**: Same request ke scope mein same key dobara load nahi hoti — cache se return hoti hai
3. **Transparent**: Resolver code nahi badalta — sirf `loader.load(id)` call karo
4. **Per-request scope**: Har HTTP request ka naya DataLoader — stale cache ki problem nahi

---

### Q3: Subscription vs Polling — kab kya use karo?

**Answer:**

| | Subscription | Polling |
|--|--|--|
| Protocol | WebSocket | HTTP |
| Updates | Push (server side) | Pull (client side) |
| Latency | ~real-time | Polling interval |
| Server load | Connection per client | N requests per minute per client |
| Infrastructure | WebSocket support needed | Simple HTTP |
| Use case | Chat, live scores, notifications | Dashboard refresh, order status |

**Subscription kab:** True real-time chahiye, users ka connection stable ho (web/mobile app)
**Polling kab:** Simple dashboard, WebSocket infrastructure nahi, reconnection logic avoid karna ho

---

### Q4: Union type mutations mein kyo use karte hain?

**Answer:**

Exceptions throw karne ki jagah typed errors return karne se:
1. **Type safety**: Client knows exactly kaunsi errors possible hain
2. **Partial success**: Error aur data dono return kar sakte ho
3. **No HTTP 200 with error confusion**: Error type clearly documented hai schema mein
4. **Client-side handling**: `... on ValidationError { field message }` — structured handling

```graphql
# Better than exceptions:
mutation {
  createPost(input: {...}) {
    ... on Post { id title }
    ... on ValidationError { field message code }
    ... on PermissionDenied { message }
  }
}
```

---

### Q5: Permission class pattern kaise kaam karta hai Strawberry mein?

**Answer:**

`BasePermission` inherit karo, `has_permission` method implement karo:

```python
class IsAuthenticated(BasePermission):
    message = "Not authenticated"
    
    def has_permission(self, source, info, **kwargs) -> bool:
        return info.context.get("current_user") is not None
```

`@strawberry.field(permission_classes=[IsAuthenticated])` se field pe laga do.

Jab resolver execute hone se pehle permission check fail hoti hai, Strawberry `PermissionError` raise karta hai `message` ke saath. Multiple permission classes AND logic use karti hain.

---

### Q6: Strawberry vs Graphene — kyo Strawberry choose karo?

**Answer:**

| | Strawberry | Graphene |
|--|--|--|
| Python version | 3.9+ modern | Older style |
| Schema definition | Type annotations (Pythonic) | Class-based (verbose) |
| IDE support | Excellent (type hints) | Limited |
| Async support | First-class | Bolted on |
| FastAPI integration | Native | Manual setup |
| Active development | Active | Slower updates |
| Code style | `@strawberry.type class User:` | `class User(graphene.ObjectType):` |

Strawberry modern Python idioms use karta hai — type hints, dataclasses — jo code cleaner aur maintainable banata hai.

---

### Q7: Subscription ka WebSocket protocol kya hota hai?

**Answer:**

`graphql-transport-ws` (newer, recommended):
1. Client WebSocket connection open karta hai
2. `connection_init` message bhejta hai (optional auth payload ke saath)
3. Server `connection_ack` bhejta hai
4. Client `subscribe` message bhejta hai `{id, query, variables}`
5. Server `next` messages stream karta hai `{id, data}`
6. Client `complete` bhejta hai unsubscribe ke liye

Legacy: `subscriptions-transport-ws` (deprecated, avoid karo naye projects mein)

Strawberry dono protocols support karta hai via `subscription_protocols` parameter.

---

### Q8: Introspection production mein disable kyo karna chahiye?

**Answer:**

Introspection se attacker:
1. **Complete schema map** bana sakta hai — saare types, fields, mutations
2. **Attack surface identify** kar sakta hai — admin mutations, hidden fields
3. **Automated exploitation** easy ho jaata hai
4. **Business logic expose** ho sakta hai — internal field names se implementation guess ho sakta hai

```python
# Production mein:
schema = strawberry.Schema(
    query=Query,
    introspection=False,  # Disable karo
)

# Ya environment-based:
is_production = os.getenv("ENV") == "production"
schema = strawberry.Schema(
    query=Query,
    introspection=not is_production,
)
```

Development mein ON rakho (GraphiQL ke liye), production mein OFF.

---

### Q9: Query complexity attack kya hota hai?

**Answer:**

Attacker deeply nested malicious query bhejta hai jo server ko overwhelm kar de:

```graphql
# Malicious query — exponential complexity
query MaliciousQuery {
  users {
    friends {
      friends {
        friends {
          friends {
            friends {
              name  # Depth 6, could be millions of DB queries
            }
          }
        }
      }
    }
  }
}
```

**Mitigations:**
1. **Depth limiting**: `QueryDepthLimiter(max_depth=5)`
2. **Complexity scoring**: Max complexity points assign karo
3. **Rate limiting**: Per-IP/user request limits
4. **Timeout**: Query execution time limit
5. **Persisted queries only**: Only pre-approved queries allow karo (production)

---

### Q10: REST vs GraphQL — interview mein kaise choose karo?

**Answer:**

**GraphQL choose karo jab:**
- Multiple clients (web, mobile, third-party) with different data needs
- Rapid product iteration — schema evolve karna frequent hai
- Complex relational data (social network, e-commerce catalog)
- Frontend team independent honi chahiye
- Real-time features chahiye (subscriptions)
- Bandwidth constraints (mobile, IoT)

**REST choose karo jab:**
- Simple CRUD API
- Public API (wider developer familiarity)
- Heavy caching needed (CDN, HTTP cache)
- Team unfamiliar with GraphQL
- File upload heavy workflow
- Microservices internal communication

**Safe answer for interview:** "GraphQL for complex, multi-client scenarios with frequent data model changes; REST for simpler, cacheable, public-facing APIs. Hybrid bhi possible hai — core data GraphQL, file uploads/webhooks REST."

---

*This completes the GraphQL + Strawberry Advanced theory guide for 40 LPA interview preparation.*

*Next file: `03_graphql_strawberry_app.py` — complete runnable application*
