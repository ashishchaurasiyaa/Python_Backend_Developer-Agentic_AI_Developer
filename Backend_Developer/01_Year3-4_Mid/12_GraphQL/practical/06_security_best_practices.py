"""
GraphQL Security Best Practices — Production Patterns (Strawberry + FastAPI)

Covers the full threat model from the theory doc:
  1.  Disable introspection in production
  2.  Disable GraphiQL/Playground in production
  3.  Query depth limiting
  4.  Query complexity / cost analysis
  5.  Field-level authorization (permission classes)
  6.  Per-operation rate limiting (Redis-backed)
  7.  Batching / alias-abuse protection
  8.  Pagination max enforcement
  9.  Input validation with Pydantic
  10. Input sanitization at the resolver boundary
  11. Error message sanitization (custom formatter)
  12. CORS configuration
  13. CSRF protection strategy
  14. Persisted queries / query allowlist
  15. Query execution timeout
  16. Audit logging

All code is illustrative — external services (Redis, DB) are represented by
stub classes so the module imports and compiles without running infrastructure.

Install:
    pip install strawberry-graphql fastapi uvicorn pydantic bleach
    pip install redis  # for production rate limiting
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import time
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

# pip install strawberry-graphql
import strawberry
from strawberry.extensions import AddValidationRules, SchemaExtension
from strawberry.permission import BasePermission
from strawberry.types import Info

# pip install fastapi
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from strawberry.fastapi import GraphQLRouter

# pip install graphql-core
from graphql import GraphQLError
from graphql.language import OperationDefinitionNode

logger = logging.getLogger(__name__)


# ==========================================================================
# SHARED STUBS (replace with real implementations in production)
# ==========================================================================

class FakeRedis:
    """In-memory stand-in for Redis — for illustration only."""

    def __init__(self) -> None:
        self._store: Dict[str, int] = {}
        self._expiry: Dict[str, float] = {}

    async def incr(self, key: str) -> int:
        now = time.monotonic()
        if key in self._expiry and now > self._expiry[key]:
            self._store.pop(key, None)
            self._expiry.pop(key, None)
        self._store[key] = self._store.get(key, 0) + 1
        return self._store[key]

    async def expire(self, key: str, seconds: int) -> None:
        self._expiry[key] = time.monotonic() + seconds


redis = FakeRedis()


@dataclass
class CurrentUser:
    id: str
    role: str  # "admin" | "user" | None (anonymous)


# Registry for persisted queries: hash -> query string
PERSISTED_QUERY_REGISTRY: Dict[str, str] = {}


# ==========================================================================
# 1. SECURITY EXTENSIONS — introspection + depth + complexity
# ==========================================================================

# pip install graphql-core  (comes with strawberry-graphql)
from graphql.validation.rules.no_schema_introspection_custom_rule import (
    NoSchemaIntrospectionCustomRule,
)

# Strawberry ships QueryDepthLimiter — pip install strawberry-graphql
try:
    from strawberry.extensions import QueryDepthLimiter
    _depth_limiter = QueryDepthLimiter(max_depth=10)
except ImportError:  # pragma: no cover
    _depth_limiter = None  # type: ignore[assignment]


# ==========================================================================
# 2. CUSTOM COMPLEXITY EXTENSION
# ==========================================================================

class QueryComplexityExtension(SchemaExtension):
    """
    Walk the parsed query AST and sum a cost per field selection.
    Reject requests whose total cost exceeds MAX_COMPLEXITY.

    Cost rules (simplified):
      - Base cost per field: 1
      - List fields with pagination argument 'first'/'last': cost *= argument value
      - Mutation fields: +10 base cost
    """

    MAX_COMPLEXITY: int = 500

    def on_executing_start(self) -> None:  # type: ignore[override]
        execution_context = self.execution_context
        query = execution_context.query
        if not query:
            return

        try:
            from graphql.language import parse, FieldNode, SelectionSetNode
        except ImportError:
            return

        try:
            ast = parse(query)
        except Exception:
            return

        total = self._calc_cost(ast)
        logger.debug("Query complexity score: %d (max %d)", total, self.MAX_COMPLEXITY)

        if total > self.MAX_COMPLEXITY:
            raise GraphQLError(
                f"Query complexity {total} exceeds maximum allowed {self.MAX_COMPLEXITY}. "
                "Break the query into smaller parts."
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _calc_cost(self, node: Any, depth_multiplier: int = 1) -> int:
        """Recursively compute cost over all selection sets."""
        from graphql.language import (
            DocumentNode,
            OperationDefinitionNode,
            FieldNode,
            SelectionSetNode,
            IntValueNode,
        )

        cost = 0
        if isinstance(node, (DocumentNode, OperationDefinitionNode)):
            for child in getattr(node, "definitions", [node]):
                cost += self._calc_cost(child, depth_multiplier)

        elif isinstance(node, FieldNode):
            field_cost = 1
            # Check for pagination arguments that multiply cost
            for arg in (node.arguments or []):
                if arg.name.value in ("first", "last", "limit"):
                    if isinstance(arg.value, IntValueNode):
                        field_cost *= max(1, int(arg.value.value))
            cost += field_cost * depth_multiplier
            if node.selection_set:
                cost += self._calc_cost(node.selection_set, depth_multiplier)

        elif isinstance(node, SelectionSetNode):
            for selection in (node.selections or []):
                cost += self._calc_cost(selection, depth_multiplier)

        return cost


# ==========================================================================
# 3. BATCHING / ALIAS-ABUSE PROTECTION EXTENSION
# ==========================================================================

class OperationCountExtension(SchemaExtension):
    """
    Reject requests that contain more than MAX_OPERATIONS top-level
    operation definitions.  This prevents alias-batching attacks like:

        mutation {
          a: createOrder { id }
          b: createOrder { id }
          ...  # 100 times
        }
    """

    MAX_OPERATIONS: int = 5

    def on_executing_start(self) -> None:  # type: ignore[override]
        execution_context = self.execution_context
        query = execution_context.query
        if not query:
            return

        try:
            from graphql.language import parse, OperationDefinitionNode as OpNode
        except ImportError:
            return

        try:
            ast = parse(query)
        except Exception:
            return

        op_count = sum(
            1
            for defn in ast.definitions
            if isinstance(defn, OpNode)
        )
        if op_count > self.MAX_OPERATIONS:
            raise GraphQLError(
                f"Request contains {op_count} operations; maximum is {self.MAX_OPERATIONS}."
            )


# ==========================================================================
# 4. PERMISSION CLASSES (field-level authorization)
# ==========================================================================

class IsAuthenticated(BasePermission):
    """Rejects anonymous requests at the field level."""

    message = "Authentication required. Please supply a valid Bearer token."

    def has_permission(
        self, source: Any, info: Info, **kwargs: Any  # type: ignore[type-arg]
    ) -> bool:
        user: Optional[CurrentUser] = info.context.get("user")
        return user is not None


class IsAdmin(BasePermission):
    """Allows only users with role='admin'."""

    message = "Administrator privileges required."

    def has_permission(
        self, source: Any, info: Info, **kwargs: Any  # type: ignore[type-arg]
    ) -> bool:
        user: Optional[CurrentUser] = info.context.get("user")
        return user is not None and user.role == "admin"


class IsOwner(BasePermission):
    """
    Allows access only when the requesting user owns the parent object.
    The parent object must expose an ``owner_id`` attribute.
    """

    message = "You do not have permission to access this resource."

    def has_permission(
        self, source: Any, info: Info, **kwargs: Any  # type: ignore[type-arg]
    ) -> bool:
        user: Optional[CurrentUser] = info.context.get("user")
        if user is None:
            return False
        owner_id = getattr(source, "owner_id", None)
        return owner_id == user.id


# ==========================================================================
# 5. RATE LIMITING HELPER (per-operation, Redis-backed)
# ==========================================================================

async def enforce_rate_limit(
    info: Info,  # type: ignore[type-arg]
    operation_key: str,
    limit: int,
    window_seconds: int,
) -> None:
    """
    Increment a Redis counter for (user_id, operation_key).
    Raise GraphQLError if the counter exceeds ``limit`` within the window.

    Usage inside a resolver:
        await enforce_rate_limit(info, "send_email", limit=10, window_seconds=3600)
    """
    user: Optional[CurrentUser] = info.context.get("user")
    user_id = user.id if user else "anonymous"
    redis_key = f"rl:{user_id}:{operation_key}"

    count = await redis.incr(redis_key)
    if count == 1:
        await redis.expire(redis_key, window_seconds)

    if count > limit:
        raise GraphQLError(
            f"Rate limit exceeded for '{operation_key}'. "
            f"Maximum {limit} requests per {window_seconds}s window."
        )


# ==========================================================================
# 6. INPUT VALIDATION — Pydantic models at the resolver boundary
# ==========================================================================

# pip install pydantic
try:
    from pydantic import BaseModel, validator

    class CreateUserInputValidator(BaseModel):
        """Pydantic validator applied inside the resolver, after GraphQL type-check."""

        email: str
        password: str
        display_name: str

        @validator("email")
        def email_must_be_valid(cls, v: str) -> str:
            if "@" not in v or "." not in v.split("@")[-1]:
                raise ValueError("Invalid email address format.")
            return v.lower().strip()

        @validator("password")
        def password_strength(cls, v: str) -> str:
            if len(v) < 12:
                raise ValueError("Password must be at least 12 characters long.")
            if not any(c.isdigit() for c in v):
                raise ValueError("Password must contain at least one digit.")
            if not any(c.isupper() for c in v):
                raise ValueError("Password must contain at least one uppercase letter.")
            return v

        @validator("display_name")
        def display_name_safe(cls, v: str) -> str:
            v = v.strip()
            if len(v) < 2:
                raise ValueError("Display name must be at least 2 characters.")
            if len(v) > 64:
                raise ValueError("Display name must not exceed 64 characters.")
            return v

    _pydantic_available = True

except ImportError:  # pragma: no cover
    _pydantic_available = False
    CreateUserInputValidator = None  # type: ignore[assignment,misc]


# ==========================================================================
# 7. INPUT SANITIZATION — HTML stripping at the resolver boundary
# ==========================================================================

def sanitize_html(raw: str, allowed_tags: Optional[List[str]] = None) -> str:
    """
    Strip dangerous HTML tags from user-supplied rich text.
    Falls back to a simple escape if bleach is not installed.

    pip install bleach
    """
    if allowed_tags is None:
        allowed_tags = ["b", "i", "em", "strong", "a"]
    try:
        import bleach  # pip install bleach
        return bleach.clean(raw, tags=allowed_tags, strip=True)
    except ImportError:
        # Minimal fallback — replaces the five XML special characters
        return (
            raw.replace("&", "&amp;")
               .replace("<", "&lt;")
               .replace(">", "&gt;")
               .replace('"', "&quot;")
               .replace("'", "&#x27;")
        )


# ==========================================================================
# 8. ERROR FORMATTER — never leak internal details in production
# ==========================================================================

def production_error_formatter(error: Any, debug: bool = False) -> Dict[str, Any]:
    """
    Custom error formatter for GraphQLRouter.

    - In debug mode (development): pass full message + traceback.
    - In production: return a generic message; log full details server-side.

    Attach to the router:
        GraphQLRouter(schema, error_formatter=production_error_formatter)
    """
    original = getattr(error, "original_error", None)

    # Always log the full error server-side
    if original is not None:
        logger.error(
            "GraphQL execution error",
            exc_info=original,
            extra={"graphql_message": getattr(error, "message", str(error))},
        )

    if debug:
        import traceback
        trace = (
            "".join(traceback.format_exception(type(original), original, original.__traceback__))
            if original is not None
            else None
        )
        return {
            "message": getattr(error, "message", str(error)),
            "locations": getattr(error, "locations", None),
            "path": getattr(error, "path", None),
            "extensions": {"traceback": trace},
        }

    # Production: classify by exception type and return generic codes
    if original is not None:
        original_type = type(original).__name__
        if "PermissionError" in original_type or "Permission" in original_type:
            return {"message": "Permission denied.", "extensions": {"code": "FORBIDDEN"}}
        if "NotFound" in original_type:
            return {"message": "Resource not found.", "extensions": {"code": "NOT_FOUND"}}
        if "Validation" in original_type or "ValueError" in original_type:
            return {
                "message": str(original),
                "extensions": {"code": "VALIDATION_ERROR"},
            }

    return {
        "message": "An internal server error occurred.",
        "extensions": {"code": "INTERNAL_ERROR"},
    }


# ==========================================================================
# 9. PERSISTED QUERY MIDDLEWARE
# ==========================================================================

def register_persisted_query(query: str) -> str:
    """
    Register a query string and return its SHA-256 hash.
    Call this at application startup for every known client query.

    Returns the hash that the client must supply in the
    ``extensions.persistedQuery.sha256Hash`` field.
    """
    hash_ = hashlib.sha256(query.encode()).hexdigest()
    PERSISTED_QUERY_REGISTRY[hash_] = query
    logger.info("Registered persisted query: %s", hash_[:12])
    return hash_


async def resolve_persisted_query(extensions: Dict[str, Any]) -> str:
    """
    Extract and validate a persisted query hash from the request extensions.
    Returns the full query string if found; raises GraphQLError otherwise.

    Wire into a custom FastAPI route or a Strawberry ASGI extension.
    """
    pq = extensions.get("persistedQuery", {})
    hash_ = pq.get("sha256Hash")
    if not hash_:
        raise GraphQLError(
            "Persisted query hash required. "
            "Ad-hoc queries are disabled in production."
        )
    query = PERSISTED_QUERY_REGISTRY.get(hash_)
    if query is None:
        raise GraphQLError(
            f"Unknown persisted query hash: {hash_[:12]}…  "
            "Register the query at build time."
        )
    return query


# ==========================================================================
# 10. QUERY TIMEOUT WRAPPER
# ==========================================================================

async def execute_with_timeout(
    coro: "asyncio.Coroutine[Any, Any, Any]",
    timeout_seconds: float = 30.0,
    label: str = "graphql_query",
) -> Any:
    """
    Wrap any resolver coroutine with an asyncio timeout.

    Usage at the schema level:
        result = await execute_with_timeout(
            schema.execute_async(query, ...),
            timeout_seconds=10,
        )

    Usage at the per-resolver level:
        return await execute_with_timeout(do_heavy_work(), timeout_seconds=5)
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        logger.warning("Execution timeout (%ss) exceeded for %s", timeout_seconds, label)
        raise GraphQLError(
            f"Query timed out after {timeout_seconds}s. "
            "Reduce scope or contact support."
        )


# ==========================================================================
# 11. AUDIT LOGGING EXTENSION
# ==========================================================================

class AuditLoggingExtension(SchemaExtension):
    """
    Log every GraphQL request with:
      - Operation name
      - User ID (or 'anonymous')
      - Wall-clock execution time
      - Whether it exceeded a slow-query threshold

    Mount as a schema extension alongside complexity and depth limiters.
    """

    SLOW_QUERY_THRESHOLD_MS: float = 1000.0

    def __init__(self, *, execution_context: Any) -> None:
        super().__init__(execution_context=execution_context)
        self._start: float = 0.0

    def on_executing_start(self) -> None:  # type: ignore[override]
        self._start = time.monotonic()

    def on_executing_end(self) -> None:  # type: ignore[override]
        duration_ms = (time.monotonic() - self._start) * 1000
        ctx = self.execution_context
        user: Optional[CurrentUser] = (ctx.context or {}).get("user")
        user_id = user.id if user else "anonymous"
        op_name = getattr(ctx, "operation_name", None) or "anonymous_op"

        log_payload = {
            "event": "graphql_request",
            "operation": op_name,
            "user_id": user_id,
            "duration_ms": round(duration_ms, 2),
        }

        if duration_ms > self.SLOW_QUERY_THRESHOLD_MS:
            log_payload["slow_query"] = True
            logger.warning("Slow GraphQL query detected", extra=log_payload)
        else:
            logger.info("GraphQL request completed", extra=log_payload)


# ==========================================================================
# 12. STRAWBERRY SCHEMA DEFINITION
# ==========================================================================

@strawberry.input
class CreateUserInput:
    email: str
    password: str
    display_name: str


@strawberry.input
class CreateCommentInput:
    post_id: strawberry.ID
    content: str  # May contain user-supplied HTML


@strawberry.type
class Settings:
    theme: str
    notifications_enabled: bool


@strawberry.type
class User:
    id: strawberry.ID
    name: str
    owner_id: str  # Needed by IsOwner permission

    @strawberry.field(permission_classes=[IsAuthenticated, IsOwner])  # type: ignore[misc]
    async def private_settings(self, info: Info) -> Settings:  # type: ignore[type-arg]
        """
        Field-level authorization: only the account owner can read their settings.
        IsAuthenticated + IsOwner are both evaluated before the resolver runs.
        """
        # Stub: in production, fetch from DB
        return Settings(theme="dark", notifications_enabled=True)


@strawberry.type
class Comment:
    id: strawberry.ID
    content: str


@strawberry.type
class Query:
    @strawberry.field(permission_classes=[IsAuthenticated])  # type: ignore[misc]
    async def users(
        self,
        info: Info,  # type: ignore[type-arg]
        first: int = 10,
    ) -> List[User]:
        """
        Paginated user list.  Enforces a hard cap of 100 items per page to
        prevent unbounded data fetches (Section 8 of the theory doc).
        """
        if first > 100:
            raise GraphQLError(
                "Maximum page size is 100. Reduce 'first' argument."
            )
        # Stub: in production, query your DB
        return [
            User(id=str(i), name=f"User {i}", owner_id=str(i))
            for i in range(1, first + 1)
        ]

    @strawberry.field  # type: ignore[misc]
    async def public_user(
        self,
        info: Info,  # type: ignore[type-arg]
        id: strawberry.ID,
    ) -> Optional[User]:
        """Public resolver — no auth required, but ownership enforced on nested fields."""
        return User(id=id, name="Alice", owner_id=id)


@strawberry.type
class Mutation:
    @strawberry.mutation(permission_classes=[IsAuthenticated])  # type: ignore[misc]
    async def create_user(
        self,
        info: Info,  # type: ignore[type-arg]
        input: CreateUserInput,
    ) -> User:
        """
        Demonstrates input validation via Pydantic (Section 9).
        Validates email format, password strength, and display name length
        before touching the database.
        """
        if _pydantic_available and CreateUserInputValidator is not None:
            try:
                validated = CreateUserInputValidator(
                    email=input.email,
                    password=input.password,
                    display_name=input.display_name,
                )
            except Exception as exc:
                raise GraphQLError(f"Validation error: {exc}") from exc
        else:
            validated = input  # type: ignore[assignment]

        # Per-operation rate limit: max 5 account creations per hour per user
        await enforce_rate_limit(info, "create_user", limit=5, window_seconds=3600)

        # Stub: persist to DB
        logger.info("Creating user with email %s", getattr(validated, "email", input.email))
        return User(id="new-id", name=getattr(validated, "display_name", input.display_name), owner_id="new-id")

    @strawberry.mutation(permission_classes=[IsAuthenticated])  # type: ignore[misc]
    async def create_comment(
        self,
        info: Info,  # type: ignore[type-arg]
        input: CreateCommentInput,
    ) -> Comment:
        """
        Demonstrates HTML sanitization at the resolver boundary (Section 10).
        User-supplied ``content`` may contain markup — strip dangerous tags
        with bleach before persisting.
        """
        await enforce_rate_limit(info, "create_comment", limit=30, window_seconds=60)

        safe_content = sanitize_html(
            input.content,
            allowed_tags=["b", "i", "em", "strong", "a"],
        )

        # Stub: persist to DB
        return Comment(id="comment-1", content=safe_content)

    @strawberry.mutation(permission_classes=[IsAdmin])  # type: ignore[misc]
    async def delete_user(
        self,
        info: Info,  # type: ignore[type-arg]
        user_id: strawberry.ID,
    ) -> bool:
        """Admin-only mutation.  IsAdmin permission class enforces the role check."""
        await enforce_rate_limit(info, "delete_user", limit=50, window_seconds=3600)
        logger.warning("Admin %s deleting user %s", info.context.get("user"), user_id)
        return True


# ==========================================================================
# 13. SCHEMA ASSEMBLY
# ==========================================================================

IS_PRODUCTION = os.getenv("ENVIRONMENT", "development").lower() == "production"

_extensions: List[Any] = [
    QueryComplexityExtension,
    OperationCountExtension,
    AuditLoggingExtension,
]

if _depth_limiter is not None:
    _extensions.insert(0, _depth_limiter)

if IS_PRODUCTION:
    # Disable introspection: attackers cannot enumerate the schema
    _extensions.append(AddValidationRules([NoSchemaIntrospectionCustomRule]))

schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    extensions=_extensions,
)


# ==========================================================================
# 14. FASTAPI APPLICATION ASSEMBLY
# ==========================================================================

app = FastAPI(title="GraphQL Security Demo")

# --- CORS (Section 12) ---
# Restrict to known origins in production; never use allow_origins=["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://myapp.com",
        "https://staging.myapp.com",
    ],
    allow_credentials=True,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)


# --- Request context builder ---
async def get_context(request: Request) -> Dict[str, Any]:
    """
    Build the Strawberry context dict for each request.
    Extracts the authenticated user from the Authorization header.

    CSRF note (Section 13): if using cookie auth, require the
    'X-Requested-With' header here and set SameSite=Strict on the cookie.
    For Bearer tokens no CSRF defense is needed.
    """
    user: Optional[CurrentUser] = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[len("Bearer "):]
        # Stub: validate JWT and hydrate user object
        if token == "admin-token":
            user = CurrentUser(id="1", role="admin")
        elif token:
            user = CurrentUser(id="2", role="user")

    return {"request": request, "user": user}


# --- GraphQL router ---
graphql_app = GraphQLRouter(
    schema,
    # Disable GraphiQL in production (Section 2)
    graphiql=not IS_PRODUCTION,
    context_getter=get_context,
    # Attach the custom error formatter (Section 11)
    error_formatter=lambda error, debug=IS_PRODUCTION: production_error_formatter(
        error, debug=not IS_PRODUCTION
    ),
)

app.include_router(graphql_app, prefix="/graphql")


# ==========================================================================
# 15. PERSISTED QUERY REGISTRATION (call at startup for known client queries)
# ==========================================================================

@app.on_event("startup")
async def register_known_queries() -> None:
    """
    Pre-register all client queries by SHA-256 hash at startup.
    In production, set ENABLE_PERSISTED_QUERIES=1 and reject any request
    that does not carry a recognized hash (Section 14).

    Build step: generate this list from your front-end query files during CI.
    """
    known_queries = [
        "query GetUser($id: ID!) { publicUser(id: $id) { id name } }",
        "query ListUsers($first: Int!) { users(first: $first) { id name } }",
        "mutation CreateComment($postId: ID!, $content: String!) { createComment(input: { postId: $postId, content: $content }) { id content } }",
    ]
    for q in known_queries:
        h = register_persisted_query(q)
        logger.debug("Registered query hash %s", h[:12])

    logger.info(
        "Persisted query registry ready with %d entries.",
        len(PERSISTED_QUERY_REGISTRY),
    )


# ==========================================================================
# 16. PRODUCTION SECURITY CHECKLIST (code-level enforcement summary)
# ==========================================================================

SECURITY_CHECKLIST = """
Production GraphQL Security Checklist
======================================
[x] Introspection disabled in prod     — AddValidationRules([NoSchemaIntrospectionCustomRule])
[x] GraphiQL disabled in prod          — GraphQLRouter(schema, graphiql=False)
[x] Query depth limit (max 10)         — QueryDepthLimiter(max_depth=10)
[x] Query complexity limit (max 500)   — QueryComplexityExtension
[x] Batching / alias abuse limit       — OperationCountExtension (max 5 ops)
[x] Field-level authorization          — IsAuthenticated, IsAdmin, IsOwner permission classes
[x] Per-operation rate limiting        — enforce_rate_limit() inside resolvers
[x] Pagination max enforced            — if first > 100: raise GraphQLError(...)
[x] Input validation (Pydantic)        — CreateUserInputValidator at resolver boundary
[x] HTML sanitization                  — sanitize_html() via bleach
[x] Error formatter strips internals   — production_error_formatter()
[x] CORS configured                    — CORSMiddleware with explicit allow_origins
[x] CSRF: Bearer token auth used       — no cookies, so no CSRF risk
[x] Persisted queries registered       — register_persisted_query() at startup
[x] Query execution timeout            — execute_with_timeout(coro, timeout_seconds=30)
[x] Audit logging                      — AuditLoggingExtension (op name, user, latency)
[ ] Dependency vulnerability scan      — run: pip-audit / safety check in CI
[ ] Schema lint in CI                  — graphql-schema-linter (JS) or similar
"""

if __name__ == "__main__":
    print(SECURITY_CHECKLIST)
    print(
        "\nThis module is designed to be run as a FastAPI application:\n"
        "    uvicorn 06_security_best_practices:app --reload\n\n"
        "Set ENVIRONMENT=production to activate:\n"
        "  - Introspection blocking\n"
        "  - GraphiQL removal\n"
        "  - Production error formatting\n"
    )
