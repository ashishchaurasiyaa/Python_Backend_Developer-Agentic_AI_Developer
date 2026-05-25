"""
GraphQL with Strawberry + FastAPI — Production Patterns
"""

import asyncio
from typing import AsyncIterator
from datetime import datetime

import strawberry
from fastapi import FastAPI, Request, Depends
from strawberry.fastapi import GraphQLRouter
from strawberry.dataloader import DataLoader
from strawberry.permission import BasePermission


# ==========================================================================
# 1. SCHEMA TYPES
# ==========================================================================

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
    author_id: int
    created_at: datetime

    @strawberry.field
    async def author(self, info) -> User:
        """Use DataLoader to avoid N+1."""
        return await info.context['user_loader'].load(self.author_id)

    @strawberry.field
    async def comments(self, info, limit: int = 10) -> list['Comment']:
        return await info.context['comments_loader'].load((self.id, limit))


@strawberry.type
class Comment:
    id: int
    body: str
    article_id: int
    author_id: int


# ==========================================================================
# 2. INPUT TYPES (for mutations)
# ==========================================================================

@strawberry.input
class ArticleInput:
    title: str
    body: str
    tags: list[str] = strawberry.field(default_factory=list)


@strawberry.input
class ArticleUpdateInput:
    title: str | None = None
    body: str | None = None


# ==========================================================================
# 3. DATALOADERS (avoid N+1)
# ==========================================================================

# Mock DB
_users_db = {
    1: {'id': 1, 'name': 'Alice', 'email': 'a@b.com'},
    2: {'id': 2, 'name': 'Bob', 'email': 'b@b.com'},
}

_articles_db = {
    1: {'id': 1, 'title': 'GraphQL Intro', 'body': '...', 'author_id': 1, 'created_at': datetime.utcnow()},
    2: {'id': 2, 'title': 'FastAPI + Strawberry', 'body': '...', 'author_id': 2, 'created_at': datetime.utcnow()},
}


async def load_users(keys: list[int]) -> list[User | None]:
    """Batched user loader — single query for all keys."""
    # In real app: SELECT * FROM users WHERE id = ANY(keys)
    results = []
    for k in keys:
        u = _users_db.get(k)
        results.append(User(**u) if u else None)
    return results


async def load_comments(keys: list[tuple[int, int]]) -> list[list[Comment]]:
    """Batched comment loader. Keys = (article_id, limit)."""
    # Real: batch SELECT WHERE article_id IN (...)
    return [[] for _ in keys]


# ==========================================================================
# 4. PERMISSION CLASSES
# ==========================================================================

class IsAuthenticated(BasePermission):
    message = "Authentication required"

    def has_permission(self, source, info, **kwargs) -> bool:
        return info.context.get('user') is not None


class IsAuthor(BasePermission):
    message = "Must be author of article"

    def has_permission(self, source, info, **kwargs) -> bool:
        user = info.context.get('user')
        if not user:
            return False
        # source is the Article being accessed
        return source.author_id == user.id if hasattr(source, 'author_id') else False


# ==========================================================================
# 5. QUERY
# ==========================================================================

@strawberry.type
class Query:
    @strawberry.field
    async def article(self, id: int) -> Article | None:
        data = _articles_db.get(id)
        if not data:
            return None
        return Article(**data)

    @strawberry.field
    async def articles(self, limit: int = 20, offset: int = 0) -> list[Article]:
        items = list(_articles_db.values())[offset:offset + limit]
        return [Article(**d) for d in items]

    @strawberry.field(permission_classes=[IsAuthenticated])
    async def me(self, info) -> User:
        user_dict = info.context['user']
        return User(**user_dict)

    @strawberry.field(permission_classes=[IsAuthenticated])
    async def my_articles(self, info) -> list[Article]:
        user = info.context['user']
        items = [a for a in _articles_db.values() if a['author_id'] == user['id']]
        return [Article(**d) for d in items]


# ==========================================================================
# 6. MUTATION
# ==========================================================================

@strawberry.type
class Mutation:
    @strawberry.field(permission_classes=[IsAuthenticated])
    async def create_article(self, info, input: ArticleInput) -> Article:
        user = info.context['user']
        new_id = max(_articles_db.keys(), default=0) + 1
        article_data = {
            'id': new_id,
            'title': input.title,
            'body': input.body,
            'author_id': user['id'],
            'created_at': datetime.utcnow(),
        }
        _articles_db[new_id] = article_data
        return Article(**article_data)

    @strawberry.field(permission_classes=[IsAuthenticated])
    async def update_article(
        self,
        info,
        id: int,
        input: ArticleUpdateInput,
    ) -> Article | None:
        data = _articles_db.get(id)
        if not data:
            return None
        user = info.context['user']
        if data['author_id'] != user['id']:
            raise PermissionError("Not author")

        if input.title is not None:
            data['title'] = input.title
        if input.body is not None:
            data['body'] = input.body

        return Article(**data)

    @strawberry.field(permission_classes=[IsAuthenticated])
    async def delete_article(self, info, id: int) -> bool:
        data = _articles_db.get(id)
        if not data:
            return False
        user = info.context['user']
        if data['author_id'] != user['id']:
            raise PermissionError("Not author")
        del _articles_db[id]
        return True


# ==========================================================================
# 7. SUBSCRIPTION (WebSocket)
# ==========================================================================

@strawberry.type
class Subscription:
    @strawberry.subscription
    async def article_created(self) -> AsyncIterator[Article]:
        """Stream new articles as they're created."""
        # In real app: subscribe to Redis pub/sub
        last_id = 0
        while True:
            await asyncio.sleep(1)
            current_ids = list(_articles_db.keys())
            new_ids = [i for i in current_ids if i > last_id]
            for new_id in new_ids:
                yield Article(**_articles_db[new_id])
                last_id = max(last_id, new_id)


# ==========================================================================
# 8. SCHEMA + CONTEXT
# ==========================================================================

schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    subscription=Subscription,
)


async def get_context(request: Request) -> dict:
    # Extract user from Authorization header (mock)
    user = None
    auth = request.headers.get('authorization', '')
    if auth.startswith('Bearer '):
        # ... validate JWT
        token = auth[7:]
        if token == 'user1-token':
            user = {'id': 1, 'name': 'Alice', 'email': 'a@b.com'}
        elif token == 'user2-token':
            user = {'id': 2, 'name': 'Bob', 'email': 'b@b.com'}

    return {
        'request': request,
        'user': user,
        'user_loader': DataLoader(load_users),
        'comments_loader': DataLoader(load_comments),
    }


graphql_app = GraphQLRouter(
    schema,
    context_getter=get_context,
    graphiql=True,   # built-in playground at /graphql
)


# ==========================================================================
# 9. MOUNT IN FASTAPI
# ==========================================================================

app = FastAPI()
app.include_router(graphql_app, prefix="/graphql")


@app.get("/")
async def root():
    return {"graphql_endpoint": "/graphql"}


# ==========================================================================
# 10. QUERY COMPLEXITY LIMIT
# ==========================================================================

from strawberry.extensions import QueryDepthLimiter, MaxAliasesLimiter, MaxTokensLimiter


schema_with_limits = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    extensions=[
        QueryDepthLimiter(max_depth=10),
        MaxAliasesLimiter(max_alias_count=15),
        MaxTokensLimiter(max_token_count=1000),
    ],
)


# ==========================================================================
# 11. SAMPLE QUERIES (try in /graphql playground)
# ==========================================================================

EXAMPLE_QUERIES = """
# Query
query {
  articles(limit: 5) {
    id
    title
    author {
      name
    }
  }
}

# Mutation
mutation {
  createArticle(input: { title: "New post", body: "..." }) {
    id
    title
    createdAt
  }
}

# Subscription (WebSocket)
subscription {
  articleCreated {
    id
    title
  }
}

# With variables
query GetArticle($id: Int!) {
  article(id: $id) {
    title
    author { name email }
  }
}
# Variables: { "id": 1 }
"""
