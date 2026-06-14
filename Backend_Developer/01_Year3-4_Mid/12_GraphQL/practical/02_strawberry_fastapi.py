"""
Strawberry + FastAPI — Production GraphQL Patterns

Covers every major building block taught in 02_strawberry_fastapi.md:

  * Minimal schema wiring (Query, Mutation, schema, GraphQLRouter)
  * Types, optional fields, enums, interfaces, unions
  * Custom scalars (DateTime)
  * Async resolvers
  * Mutations with @strawberry.input
  * Context injection (auth + fake DB)
  * JWT-based auth middleware (get_current_user via FastAPI Depends)
  * Field-level permissions (BasePermission subclasses)
  * Relay-style cursor pagination
  * File upload pattern (strawberry.Upload)
  * Structured GraphQL error handling + custom error formatter
  * Pydantic v2 integration (strawberry.experimental.pydantic)
  * Schema extensions: QueryDepthLimiter, ParserCache, ValidationCache,
    AddValidationRules (introspection disabled in prod)
  * Inline pytest-style schema execution tests (no HTTP layer needed)

Run (dev):
    uvicorn 02_strawberry_fastapi:app --reload

GraphiQL UI:  http://localhost:8000/graphql   (dev only; disabled in prod app)
Prod app:     http://localhost:8001/graphql

Install:
    pip install strawberry-graphql[fastapi] fastapi uvicorn pyjwt pydantic
"""

# pip install strawberry-graphql[fastapi] fastapi uvicorn pyjwt pydantic

import asyncio
import base64
import enum
import logging
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

import strawberry
from fastapi import Depends, FastAPI, Header
from graphql import GraphQLError
from graphql.validation import NoSchemaIntrospectionCustomRule
from pydantic import BaseModel as PydanticBaseModel
from strawberry.extensions import (
    AddValidationRules,
    ParserCache,
    QueryDepthLimiter,
    ValidationCache,
)
from strawberry.fastapi import GraphQLRouter
from strawberry.permission import BasePermission
from strawberry.schema.config import StrawberryConfig
from strawberry.types import Info

log = logging.getLogger(__name__)

# ==========================================================================
# 1. CUSTOM SCALAR — DateTime (ISO 8601)
# ==========================================================================

DateTimeScalar = strawberry.scalar(
    datetime,
    name="DateTime",
    description="ISO 8601 datetime string (UTC).",
    serialize=lambda v: v.isoformat(),
    parse_value=lambda v: datetime.fromisoformat(v),
)


# ==========================================================================
# 2. ENUMS
# ==========================================================================

@strawberry.enum
class UserRole(enum.Enum):
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"


@strawberry.enum
class PostStatus(enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


# ==========================================================================
# 3. INTERFACES
# ==========================================================================

@strawberry.interface
class Node:
    """Relay-compatible Node interface — every entity exposes a global ID."""
    id: strawberry.ID


# ==========================================================================
# 4. CORE TYPES
# ==========================================================================

@strawberry.type
class User(Node):
    id: strawberry.ID
    name: str
    email: str
    role: UserRole
    created_at: DateTimeScalar  # type: ignore[valid-type]


@strawberry.type
class Post(Node):
    id: strawberry.ID
    title: str
    content: Optional[str]       # optional field — may be None
    status: PostStatus
    created_at: DateTimeScalar   # type: ignore[valid-type]
    author_id: strawberry.ID


@strawberry.type
class Comment(Node):
    id: strawberry.ID
    text: str
    author_id: strawberry.ID


# ==========================================================================
# 5. UNION — SearchResult
# ==========================================================================

SearchResult = strawberry.union(
    "SearchResult",
    types=(User, Post, Comment),
    description="Union of all searchable entity types.",
)


# ==========================================================================
# 6. RELAY-STYLE PAGINATION TYPES
# ==========================================================================

@strawberry.type
class PostEdge:
    cursor: str
    node: Post


@strawberry.type
class PageInfo:
    has_next_page: bool
    has_previous_page: bool
    start_cursor: Optional[str]
    end_cursor: Optional[str]


@strawberry.type
class PostConnection:
    edges: list[PostEdge]
    page_info: PageInfo
    total_count: int


# ==========================================================================
# 7. INPUT TYPES (mutations)
# ==========================================================================

@strawberry.input
class CreateUserInput:
    name: str
    email: str
    role: UserRole = UserRole.VIEWER


@strawberry.input
class CreatePostInput:
    title: str
    content: Optional[str] = None
    status: PostStatus = PostStatus.DRAFT


@strawberry.input
class UpdatePostInput:
    title: Optional[str] = None
    content: Optional[str] = None
    status: Optional[PostStatus] = None


# ==========================================================================
# 8. PYDANTIC INTEGRATION
#    Re-use existing Pydantic models; strawberry.auto maps fields
# ==========================================================================

class UserPydanticModel(PydanticBaseModel):
    id: int
    name: str
    email: str


# Experimental pydantic integration — auto-maps matching field names
@strawberry.experimental.pydantic.type(model=UserPydanticModel, all_fields=True)
class UserPydanticGQL:
    """GraphQL type backed by UserPydanticModel — fields auto-derived."""


# ==========================================================================
# 9. FAKE IN-MEMORY DATABASE (replaces real async DB for illustration)
# ==========================================================================

_users_db: dict[str, dict[str, Any]] = {
    "1": {
        "id": "1",
        "name": "Alice",
        "email": "alice@example.com",
        "role": UserRole.ADMIN,
        "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
    },
    "2": {
        "id": "2",
        "name": "Bob",
        "email": "bob@example.com",
        "role": UserRole.EDITOR,
        "created_at": datetime(2024, 3, 15, tzinfo=timezone.utc),
    },
}

_posts_db: dict[str, dict[str, Any]] = {
    "101": {
        "id": "101",
        "title": "Intro to GraphQL",
        "content": "GraphQL is a query language...",
        "status": PostStatus.PUBLISHED,
        "created_at": datetime(2024, 6, 1, tzinfo=timezone.utc),
        "author_id": "1",
    },
    "102": {
        "id": "102",
        "title": "Advanced Strawberry",
        "content": None,
        "status": PostStatus.DRAFT,
        "created_at": datetime(2024, 7, 10, tzinfo=timezone.utc),
        "author_id": "2",
    },
}

_comments_db: dict[str, dict[str, Any]] = {
    "201": {"id": "201", "text": "Great post!", "author_id": "2"},
}


def _row_to_user(row: dict[str, Any]) -> User:
    return User(
        id=row["id"],
        name=row["name"],
        email=row["email"],
        role=row["role"],
        created_at=row["created_at"],
    )


def _row_to_post(row: dict[str, Any]) -> Post:
    return Post(
        id=row["id"],
        title=row["title"],
        content=row["content"],
        status=row["status"],
        created_at=row["created_at"],
        author_id=row["author_id"],
    )


# ==========================================================================
# 10. CURSOR HELPERS (Relay pagination)
# ==========================================================================

def _encode_cursor(entity_id: str) -> str:
    return base64.b64encode(f"cursor:{entity_id}".encode()).decode()


def _decode_cursor(cursor: str) -> str:
    return base64.b64decode(cursor.encode()).decode().replace("cursor:", "")


# ==========================================================================
# 11. CONTEXT — auth + fake DB injection
# ==========================================================================

# Shared fake secret; in production load from environment variable
_JWT_SECRET = "dev-secret-change-in-production"


async def _get_current_user(authorization: Optional[str] = Header(default=None)) -> Optional[User]:
    """
    Extract Bearer token from Authorization header, validate it, and return
    the matching User.  Returns None when the token is absent or invalid.

    In production: use python-jose or PyJWT with RS256 + JWKS endpoint.
    """
    if not authorization:
        return None
    token = authorization.replace("Bearer ", "").strip()
    try:
        # pip install pyjwt
        import jwt  # noqa: PLC0415
        payload = jwt.decode(token, _JWT_SECRET, algorithms=["HS256"])
        user_id: str = payload["sub"]
    except Exception:
        return None

    row = _users_db.get(user_id)
    return _row_to_user(row) if row else None


async def get_context(current_user: Optional[User] = Depends(_get_current_user)) -> dict[str, Any]:
    """
    Build the request-scoped context dict injected into every resolver via
    ``info.context``.  Attach the authenticated user and fake DB handle.
    """
    return {
        "user": current_user,
        "db_users": _users_db,
        "db_posts": _posts_db,
        "db_comments": _comments_db,
    }


# ==========================================================================
# 12. FIELD-LEVEL PERMISSIONS
# ==========================================================================

class IsAuthenticated(BasePermission):
    """Rejects resolvers when no authenticated user is present in context."""
    message = "Authentication required."

    def has_permission(self, source: Any, info: Info, **kwargs: Any) -> bool:  # type: ignore[override]
        return info.context["user"] is not None


class IsAdmin(BasePermission):
    """Restricts resolvers to users with the ADMIN role."""
    message = "Admin access required."

    def has_permission(self, source: Any, info: Info, **kwargs: Any) -> bool:  # type: ignore[override]
        user: Optional[User] = info.context["user"]
        return user is not None and user.role == UserRole.ADMIN


# ==========================================================================
# 13. QUERY TYPE
# ==========================================================================

@strawberry.type
class Query:
    """Root query type — all read operations live here."""

    # ------------------------------------------------------------------
    # Public fields — no authentication required
    # ------------------------------------------------------------------

    @strawberry.field(description="Fetch a single user by ID.")
    async def user(self, info: Info, id: strawberry.ID) -> User:
        """Raise a structured GraphQLError when the user is not found."""
        await asyncio.sleep(0)  # yield to event loop — illustrates async pattern
        row = info.context["db_users"].get(str(id))
        if not row:
            raise GraphQLError(
                "User not found",
                extensions={"code": "NOT_FOUND", "user_id": str(id)},
            )
        return _row_to_user(row)

    @strawberry.field(description="List all published posts with Relay cursor pagination.")
    async def posts(
        self,
        info: Info,
        first: int = 10,
        after: Optional[str] = None,
    ) -> PostConnection:
        """
        Relay-style cursor pagination.

        ``after`` is a base64-encoded cursor referencing the last seen post ID.
        ``first`` limits the number of returned edges.
        """
        await asyncio.sleep(0)
        all_posts = sorted(
            info.context["db_posts"].values(),
            key=lambda p: p["id"],
        )

        # Slice from cursor position
        if after:
            after_id = _decode_cursor(after)
            all_posts = [p for p in all_posts if p["id"] > after_id]

        # Fetch one extra to determine has_next_page
        paged = all_posts[: first + 1]
        has_next = len(paged) > first
        nodes = paged[:first]

        edges = [
            PostEdge(
                cursor=_encode_cursor(p["id"]),
                node=_row_to_post(p),
            )
            for p in nodes
        ]

        return PostConnection(
            edges=edges,
            page_info=PageInfo(
                has_next_page=has_next,
                has_previous_page=after is not None,
                start_cursor=edges[0].cursor if edges else None,
                end_cursor=edges[-1].cursor if edges else None,
            ),
            total_count=len(info.context["db_posts"]),
        )

    @strawberry.field(description="Full-text search across users, posts, and comments.")
    async def search(self, info: Info, q: str) -> list[SearchResult]:  # type: ignore[valid-type]
        """Returns a heterogeneous list of User | Post | Comment matching ``q``."""
        await asyncio.sleep(0)
        results: list[Any] = []
        q_lower = q.lower()

        for row in info.context["db_users"].values():
            if q_lower in row["name"].lower() or q_lower in row["email"].lower():
                results.append(_row_to_user(row))

        for row in info.context["db_posts"].values():
            if q_lower in row["title"].lower():
                results.append(_row_to_post(row))

        for row in info.context["db_comments"].values():
            if q_lower in row["text"].lower():
                results.append(
                    Comment(id=row["id"], text=row["text"], author_id=row["author_id"])
                )

        return results

    # ------------------------------------------------------------------
    # Protected fields — require authentication
    # ------------------------------------------------------------------

    @strawberry.field(
        permission_classes=[IsAuthenticated],
        description="Return the currently authenticated user.",
    )
    async def me(self, info: Info) -> User:
        return info.context["user"]

    # ------------------------------------------------------------------
    # Admin-only fields
    # ------------------------------------------------------------------

    @strawberry.field(
        permission_classes=[IsAdmin],
        description="List all users — admin only.",
    )
    async def all_users(self, info: Info) -> list[User]:
        await asyncio.sleep(0)
        return [_row_to_user(row) for row in info.context["db_users"].values()]

    # ------------------------------------------------------------------
    # Async illustrative field
    # ------------------------------------------------------------------

    @strawberry.field(description="Simulate a slow async resolver (illustrative).")
    async def slow_field(self) -> str:
        """Non-blocking sleep; the event loop remains responsive throughout."""
        await asyncio.sleep(0.1)
        return "resolved after async wait"


# ==========================================================================
# 14. MUTATION TYPE
# ==========================================================================

@strawberry.type
class Mutation:
    """Root mutation type — all write operations live here."""

    @strawberry.mutation(description="Create a new user account.")
    async def create_user(self, input: CreateUserInput) -> User:
        await asyncio.sleep(0)
        new_id = str(len(_users_db) + 1)
        row: dict[str, Any] = {
            "id": new_id,
            "name": input.name,
            "email": input.email,
            "role": input.role,
            "created_at": datetime.now(tz=timezone.utc),
        }
        _users_db[new_id] = row
        log.info("Created user id=%s email=%s", new_id, input.email)
        return _row_to_user(row)

    @strawberry.mutation(description="Create a new blog post.")
    async def create_post(
        self,
        info: Info,
        input: CreatePostInput,
    ) -> Post:
        """
        Requires an authenticated user — the author_id is derived from context.
        In a public demo context (no auth), falls back to user ID "1".
        """
        await asyncio.sleep(0)
        current_user: Optional[User] = info.context["user"]
        author_id = current_user.id if current_user else strawberry.ID("1")

        new_id = str(100 + len(_posts_db) + 1)
        row: dict[str, Any] = {
            "id": new_id,
            "title": input.title,
            "content": input.content,
            "status": input.status,
            "created_at": datetime.now(tz=timezone.utc),
            "author_id": str(author_id),
        }
        _posts_db[new_id] = row
        log.info("Created post id=%s title=%r", new_id, input.title)
        return _row_to_post(row)

    @strawberry.mutation(description="Update an existing post (partial update).")
    async def update_post(
        self,
        info: Info,
        id: strawberry.ID,
        input: UpdatePostInput,
    ) -> Post:
        await asyncio.sleep(0)
        row = info.context["db_posts"].get(str(id))
        if not row:
            raise GraphQLError(
                "Post not found",
                extensions={"code": "NOT_FOUND", "post_id": str(id)},
            )
        if input.title is not None:
            row["title"] = input.title
        if input.content is not None:
            row["content"] = input.content
        if input.status is not None:
            row["status"] = input.status
        return _row_to_post(row)

    @strawberry.mutation(description="Upload a user avatar (multipart/form-data).")
    async def upload_avatar(self, file: strawberry.Upload) -> str:  # type: ignore[type-arg]
        """
        Client sends multipart/form-data following the GraphQL multipart spec.
        Returns the URL where the uploaded file was stored.

        In production: stream to S3 / GCS instead of reading into memory.
        Alternative (preferred for large files): REST PUT /avatars/{user_id},
        then reference the returned URL in a separate GraphQL mutation.
        """
        data = await file.read()
        # Fake storage — in production: await s3_client.upload(data, key=...)
        fake_url = f"https://cdn.example.com/avatars/{uuid4()}.bin"
        log.info("Received avatar upload: %d bytes → %s", len(data), fake_url)
        return fake_url


# ==========================================================================
# 15. CUSTOM ERROR FORMATTER
# ==========================================================================

def custom_error_formatter(error: GraphQLError, debug: bool) -> dict[str, Any]:
    """
    Normalise all GraphQL errors into a consistent shape:
      { message, code, path }

    Attach stack traces only when debug=True to avoid leaking internals.
    """
    formatted: dict[str, Any] = {
        "message": error.message,
        "code": (
            error.extensions.get("code", "INTERNAL_ERROR")
            if error.extensions
            else "INTERNAL_ERROR"
        ),
        "path": error.path,
    }
    if debug and error.original_error:
        import traceback  # noqa: PLC0415
        formatted["trace"] = traceback.format_exception(
            type(error.original_error),
            error.original_error,
            error.original_error.__traceback__,
        )
    return formatted


# ==========================================================================
# 16. SCHEMA — DEV (with GraphiQL + introspection)
# ==========================================================================

dev_schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    scalar_overrides={datetime: DateTimeScalar},
    extensions=[
        QueryDepthLimiter(max_depth=10),   # block deeply nested queries
        ParserCache(maxsize=128),           # cache parsed query documents
        ValidationCache(maxsize=128),       # cache validation results
    ],
)

# ------------------------------------------------------------------
# DEV APPLICATION — GraphiQL UI enabled, introspection enabled
# ------------------------------------------------------------------

app = FastAPI(title="Strawberry GraphQL — Dev")

dev_graphql_router = GraphQLRouter(
    dev_schema,
    context_getter=get_context,
    graphiql=True,                          # UI available at /graphql
)
app.include_router(dev_graphql_router, prefix="/graphql")


# ==========================================================================
# 17. SCHEMA — PRODUCTION (introspection + GraphiQL disabled)
# ==========================================================================

prod_schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    scalar_overrides={datetime: DateTimeScalar},
    extensions=[
        QueryDepthLimiter(max_depth=10),
        ParserCache(maxsize=256),
        ValidationCache(maxsize=256),
        AddValidationRules([NoSchemaIntrospectionCustomRule]),  # disable introspection
    ],
)

# ------------------------------------------------------------------
# PROD APPLICATION — no GraphiQL, no introspection, custom error format
# ------------------------------------------------------------------

prod_app = FastAPI(title="Strawberry GraphQL — Production")

prod_graphql_router = GraphQLRouter(
    prod_schema,
    context_getter=get_context,
    graphiql=False,                         # never expose IDE in production
)
prod_app.include_router(prod_graphql_router, prefix="/graphql")


# ==========================================================================
# 18. STARTUP EVENT — basic environment checks
# ==========================================================================

@app.on_event("startup")
async def _startup_checks() -> None:
    """Warn if optional performance dependencies are absent."""
    try:
        import uvloop  # noqa: F401, PLC0415
    except ImportError:
        log.warning("uvloop not installed — event loop throughput will be lower.")

    try:
        import jwt  # noqa: F401, PLC0415
    except ImportError:
        log.warning("PyJWT not installed — JWT auth middleware will not function.")


# ==========================================================================
# 19. SCHEMA SDL EXPORT (reference)
# ==========================================================================

# Generate the SDL string at import time — useful for contract testing and
# sharing with frontend teams without spinning up the server.
#
#     from 02_strawberry_fastapi import SDL
#     print(SDL)
#
# From the CLI:
#     strawberry export-schema 02_strawberry_fastapi:dev_schema

SDL: str = dev_schema.as_str()


# ==========================================================================
# 20. INLINE TESTS — execute queries directly against the schema
#     (no HTTP, no pytest required — run: python 02_strawberry_fastapi.py)
# ==========================================================================

async def _run_inline_tests() -> None:
    """
    Execute a suite of queries and mutations directly against dev_schema.
    No HTTP server is needed; this mirrors the pytest pattern from the theory doc.
    """

    fake_context: dict[str, Any] = {
        "user": None,
        "db_users": _users_db,
        "db_posts": _posts_db,
        "db_comments": _comments_db,
    }

    # --- Test 1: fetch existing user ---
    result = await dev_schema.execute(
        'query { user(id: "1") { id name email role } }',
        context_value=fake_context,
    )
    assert result.errors is None, f"Test 1 errors: {result.errors}"
    assert result.data["user"]["name"] == "Alice"
    print("[PASS] Test 1 — user query returns Alice")

    # --- Test 2: fetch non-existent user raises NOT_FOUND ---
    result = await dev_schema.execute(
        'query { user(id: "999") { id name } }',
        context_value=fake_context,
    )
    assert result.errors is not None
    assert result.errors[0].extensions["code"] == "NOT_FOUND"  # type: ignore[index]
    print("[PASS] Test 2 — NOT_FOUND error raised for missing user")

    # --- Test 3: posts pagination (first page) ---
    result = await dev_schema.execute(
        "query { posts(first: 1) { edges { cursor node { title } } pageInfo { hasNextPage } } }",
        context_value=fake_context,
    )
    assert result.errors is None, f"Test 3 errors: {result.errors}"
    assert result.data["posts"]["pageInfo"]["hasNextPage"] is True
    print("[PASS] Test 3 — posts pagination returns first page with hasNextPage=True")

    # --- Test 4: create user mutation ---
    result = await dev_schema.execute(
        """
        mutation {
            createUser(input: { name: "Carol", email: "carol@example.com", role: EDITOR }) {
                id name email role
            }
        }
        """,
        context_value=fake_context,
    )
    assert result.errors is None, f"Test 4 errors: {result.errors}"
    assert result.data["createUser"]["name"] == "Carol"
    print("[PASS] Test 4 — createUser mutation succeeded")

    # --- Test 5: create post mutation ---
    result = await dev_schema.execute(
        """
        mutation {
            createPost(input: { title: "Test Post", status: DRAFT }) {
                id title status
            }
        }
        """,
        context_value=fake_context,
    )
    assert result.errors is None, f"Test 5 errors: {result.errors}"
    assert result.data["createPost"]["title"] == "Test Post"
    print("[PASS] Test 5 — createPost mutation succeeded")

    # --- Test 6: me query rejects unauthenticated request ---
    result = await dev_schema.execute(
        "query { me { id name } }",
        context_value=fake_context,  # user=None → IsAuthenticated fails
    )
    assert result.errors is not None
    print("[PASS] Test 6 — me query rejected for unauthenticated user")

    # --- Test 7: search returns heterogeneous results ---
    result = await dev_schema.execute(
        'query { search(q: "Alice") { ... on User { name } } }',
        context_value=fake_context,
    )
    assert result.errors is None, f"Test 7 errors: {result.errors}"
    user_results = [r for r in result.data["search"] if r.get("name")]
    assert any(r["name"] == "Alice" for r in user_results)
    print("[PASS] Test 7 — search union query returns Alice")

    # --- Test 8: allUsers rejects non-admin ---
    result = await dev_schema.execute(
        "query { allUsers { id name } }",
        context_value=fake_context,
    )
    assert result.errors is not None
    print("[PASS] Test 8 — allUsers rejected for non-admin user")

    # --- Test 9: allUsers succeeds for admin ---
    admin_context = {**fake_context, "user": _row_to_user(_users_db["1"])}
    result = await dev_schema.execute(
        "query { allUsers { id name role } }",
        context_value=admin_context,
    )
    assert result.errors is None, f"Test 9 errors: {result.errors}"
    assert any(u["name"] == "Alice" for u in result.data["allUsers"])
    print("[PASS] Test 9 — allUsers accessible for admin user")

    # --- Test 10: SDL export is non-empty ---
    assert SDL and "type Query" in SDL
    print("[PASS] Test 10 — SDL export contains 'type Query'")

    print("\nAll inline tests passed.")


if __name__ == "__main__":
    asyncio.run(_run_inline_tests())
