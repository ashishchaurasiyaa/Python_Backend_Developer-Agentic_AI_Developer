"""
GraphQL Federation & Schema Stitching — Production Patterns

Demonstrates Apollo Federation v2 concepts using Strawberry-GraphQL:
  - Federated entity types with @key directives (User, Post, Order subgraphs)
  - Entity reference resolution (_entities query under the hood)
  - Extending entities across subgraph boundaries
  - BFF (Backend-for-Frontend) pattern aggregating multiple downstream services
  - Schema stitching (legacy) illustrated side-by-side
  - In-process gateway simulation (no external Apollo Router required)
  - Observability: per-subgraph timing and structured logging

Architecture being modelled:
    Client
      |
    Gateway (this file simulates it in-process)
      |-- User Service   (port 4001) — owns User, Profile
      |-- Post Service   (port 4002) — owns Post, Comment; extends User
      `-- Order Service  (port 4003) — owns Order, Payment; extends User

Run:
    pip install strawberry-graphql fastapi uvicorn httpx structlog
    uvicorn 05_federation_gateway:app --reload --port 8000
"""

# pip install strawberry-graphql fastapi uvicorn httpx structlog

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import strawberry
from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter

import structlog

# ==========================================================================
# 1. STRUCTURED LOGGING
# ==========================================================================

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)

log = structlog.get_logger()


# ==========================================================================
# 2. IN-MEMORY DATA STORES  (stand-in for real databases)
# ==========================================================================

USERS_DB: dict[str, dict] = {
    "1": {"id": "1", "name": "Alice Nguyen", "email": "alice@example.com"},
    "2": {"id": "2", "name": "Bob Patel",    "email": "bob@example.com"},
    "3": {"id": "3", "name": "Carol Smith",  "email": "carol@example.com"},
}

POSTS_DB: dict[str, dict] = {
    "p1": {"id": "p1", "title": "Intro to Federation", "body": "...", "author_id": "1"},
    "p2": {"id": "p2", "title": "Strawberry Tips",      "body": "...", "author_id": "1"},
    "p3": {"id": "p3", "title": "BFF Pattern",          "body": "...", "author_id": "2"},
}

ORDERS_DB: dict[str, dict] = {
    "o1": {"id": "o1", "user_id": "1", "amount": 99.99,  "status": "SHIPPED"},
    "o2": {"id": "o2", "user_id": "1", "amount": 149.00, "status": "DELIVERED"},
    "o3": {"id": "o3", "user_id": "2", "amount": 29.99,  "status": "PENDING"},
}

COMMENTS_DB: list[dict] = [
    {"id": "c1", "post_id": "p1", "body": "Great post!",  "author_id": "2"},
    {"id": "c2", "post_id": "p1", "body": "Very helpful", "author_id": "3"},
    {"id": "c3", "post_id": "p2", "body": "Nice tips",    "author_id": "3"},
]


# ==========================================================================
# 3. USER SUBGRAPH  — owns User entity
#
#    @strawberry.federation.type(keys=["id"]) declares User as a federated
#    entity keyed by 'id'.  Apollo Router uses this key to route entity
#    resolution queries (_entities) to the correct subgraph.
# ==========================================================================

@strawberry.federation.type(keys=["id"])
class User:
    """Federated entity: owned by the User subgraph.

    Other subgraphs extend this type to attach their own fields (posts, orders).
    The 'id' field acts as the primary key for cross-service joins.
    """

    id: strawberry.ID
    name: str
    email: str

    @classmethod
    async def resolve_reference(cls, id: strawberry.ID) -> "User":
        """Called by the gateway when it needs to hydrate a User stub.

        Apollo Router sends:
            _entities(representations: [{__typename: "User", id: "1"}])
        This method reconstructs the full User from just the key.
        """
        start = time.monotonic()
        row = USERS_DB.get(str(id))
        elapsed_ms = int((time.monotonic() - start) * 1000)
        log.info("user_subgraph.resolve_reference", user_id=id, latency_ms=elapsed_ms)
        if row is None:
            raise ValueError(f"User {id!r} not found")
        return cls(id=row["id"], name=row["name"], email=row["email"])


@strawberry.type
class UserQuery:
    """Root queries served by the User subgraph."""

    @strawberry.field
    async def user(self, id: strawberry.ID) -> Optional[User]:
        """Fetch a single user by ID."""
        row = USERS_DB.get(str(id))
        if row is None:
            return None
        return User(id=row["id"], name=row["name"], email=row["email"])

    @strawberry.field
    async def users(self) -> list[User]:
        """Return all users."""
        return [
            User(id=r["id"], name=r["name"], email=r["email"])
            for r in USERS_DB.values()
        ]


user_subgraph_schema = strawberry.federation.Schema(query=UserQuery, enable_federation_2=True)


# ==========================================================================
# 4. POST SUBGRAPH  — owns Post entity, extends User to add 'posts' field
#
#    The Post subgraph knows nothing about User internals; it only holds the
#    User's id (declared external=True).  The gateway orchestrates hydration.
# ==========================================================================

@strawberry.type
class Comment:
    """Comment belongs entirely to the Post subgraph."""

    id: strawberry.ID
    body: str
    author_id: strawberry.ID


@strawberry.federation.type(keys=["id"])
class Post:
    """Federated entity owned by the Post subgraph."""

    id: strawberry.ID
    title: str
    body: str
    author_id: strawberry.ID

    @strawberry.field
    async def comments(self) -> list[Comment]:
        """Resolve comments for this post (owned by Post subgraph)."""
        rows = [c for c in COMMENTS_DB if c["post_id"] == str(self.id)]
        return [Comment(id=c["id"], body=c["body"], author_id=c["author_id"]) for c in rows]

    @classmethod
    async def resolve_reference(cls, id: strawberry.ID) -> "Post":
        """Hydrate a Post stub from its key — called by the gateway."""
        row = POSTS_DB.get(str(id))
        if row is None:
            raise ValueError(f"Post {id!r} not found")
        return cls(
            id=row["id"],
            title=row["title"],
            body=row["body"],
            author_id=row["author_id"],
        )


@strawberry.federation.type(keys=["id"], extend=True)
class UserExtendedByPosts:
    """User stub inside the Post subgraph.

    extend=True means this subgraph does NOT own User; it only adds 'posts'.
    external=True on 'id' tells the gateway this field comes from User subgraph.

    Apollo Router will:
      1. Resolve User.name from User subgraph.
      2. Pass representation {__typename:"User", id:"1"} to Post subgraph.
      3. Post subgraph resolves User.posts via this class.
    """

    id: strawberry.ID = strawberry.federation.field(external=True)

    @strawberry.field
    async def posts(self) -> list[Post]:
        """Return all posts written by this user."""
        rows = [p for p in POSTS_DB.values() if p["author_id"] == str(self.id)]
        return [
            Post(id=r["id"], title=r["title"], body=r["body"], author_id=r["author_id"])
            for r in rows
        ]

    @classmethod
    async def resolve_reference(cls, id: strawberry.ID) -> "UserExtendedByPosts":
        """Reconstruct the user stub so the gateway can then resolve 'posts'."""
        return cls(id=id)


@strawberry.type
class PostQuery:
    """Root queries served by the Post subgraph."""

    @strawberry.field
    async def post(self, id: strawberry.ID) -> Optional[Post]:
        row = POSTS_DB.get(str(id))
        if row is None:
            return None
        return Post(id=row["id"], title=row["title"], body=row["body"], author_id=row["author_id"])

    @strawberry.field
    async def posts(self) -> list[Post]:
        return [
            Post(id=r["id"], title=r["title"], body=r["body"], author_id=r["author_id"])
            for r in POSTS_DB.values()
        ]


post_subgraph_schema = strawberry.federation.Schema(
    query=PostQuery,
    types=[UserExtendedByPosts],
    enable_federation_2=True,
)


# ==========================================================================
# 5. ORDER SUBGRAPH  — owns Order entity, extends User to add 'orders' field
# ==========================================================================

@strawberry.federation.type(keys=["id"])
class Order:
    """Federated entity owned by the Order subgraph."""

    id: strawberry.ID
    user_id: strawberry.ID
    amount: float
    status: str

    @classmethod
    async def resolve_reference(cls, id: strawberry.ID) -> "Order":
        row = ORDERS_DB.get(str(id))
        if row is None:
            raise ValueError(f"Order {id!r} not found")
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            amount=row["amount"],
            status=row["status"],
        )


@strawberry.federation.type(keys=["id"], extend=True)
class UserExtendedByOrders:
    """User stub inside the Order subgraph — adds 'orders' field to User."""

    id: strawberry.ID = strawberry.federation.field(external=True)

    @strawberry.field
    async def orders(self) -> list[Order]:
        """Return all orders placed by this user."""
        rows = [o for o in ORDERS_DB.values() if o["user_id"] == str(self.id)]
        return [
            Order(id=r["id"], user_id=r["user_id"], amount=r["amount"], status=r["status"])
            for r in rows
        ]

    @classmethod
    async def resolve_reference(cls, id: strawberry.ID) -> "UserExtendedByOrders":
        return cls(id=id)


@strawberry.type
class OrderQuery:
    """Root queries served by the Order subgraph."""

    @strawberry.field
    async def order(self, id: strawberry.ID) -> Optional[Order]:
        row = ORDERS_DB.get(str(id))
        if row is None:
            return None
        return Order(id=row["id"], user_id=row["user_id"], amount=row["amount"], status=row["status"])

    @strawberry.field
    async def orders_by_user(self, user_id: strawberry.ID) -> list[Order]:
        rows = [o for o in ORDERS_DB.values() if o["user_id"] == str(user_id)]
        return [
            Order(id=r["id"], user_id=r["user_id"], amount=r["amount"], status=r["status"])
            for r in rows
        ]


order_subgraph_schema = strawberry.federation.Schema(
    query=OrderQuery,
    types=[UserExtendedByOrders],
    enable_federation_2=True,
)


# ==========================================================================
# 6. IN-PROCESS GATEWAY SIMULATION
#
#    In production, Apollo Router (Rust binary) composes the supergraph and
#    routes queries.  Here we simulate the gateway logic in Python so the
#    module can run standalone without external infrastructure.
#
#    Gateway query plan for:
#        { user(id:"1") { name posts { title } orders { amount } } }
#    Step 1: Fetch User.name from User subgraph.
#    Step 2: Parallel fan-out to Post + Order subgraphs with
#            representation {__typename:"User", id:"1"}.
#    Step 3: Merge results and return to client.
# ==========================================================================

@dataclass
class UserWithRelations:
    """Merged view returned by the simulated gateway query."""

    id: str
    name: str
    email: str
    posts: list[dict] = field(default_factory=list)
    orders: list[dict] = field(default_factory=list)


async def _fetch_user(user_id: str) -> dict:
    """User subgraph: resolve User by id."""
    row = USERS_DB.get(user_id)
    if row is None:
        raise ValueError(f"User {user_id!r} not found")
    return row


async def _fetch_posts_for_user(user_id: str) -> list[dict]:
    """Post subgraph: resolve User.posts via entity representation."""
    # Simulates _entities(representations:[{__typename:"User", id:user_id}])
    return [
        {"id": p["id"], "title": p["title"]}
        for p in POSTS_DB.values()
        if p["author_id"] == user_id
    ]


async def _fetch_orders_for_user(user_id: str) -> list[dict]:
    """Order subgraph: resolve User.orders via entity representation."""
    return [
        {"id": o["id"], "amount": o["amount"], "status": o["status"]}
        for o in ORDERS_DB.values()
        if o["user_id"] == user_id
    ]


async def gateway_user_query(user_id: str) -> Optional[UserWithRelations]:
    """Simulate gateway orchestration for a cross-subgraph User query.

    Mirrors what Apollo Router does under the hood:
      1. Execute initial plan against the owning subgraph.
      2. Fan-out parallel _entities queries to extending subgraphs.
      3. Merge and return.
    """
    start = time.monotonic()

    # Step 1 — fetch base entity from User subgraph
    user_row = await _fetch_user(user_id)

    # Step 2 — parallel fan-out to Post and Order subgraphs
    posts_task = asyncio.create_task(_fetch_posts_for_user(user_id))
    orders_task = asyncio.create_task(_fetch_orders_for_user(user_id))
    posts, orders = await asyncio.gather(posts_task, orders_task)

    elapsed_ms = int((time.monotonic() - start) * 1000)
    log.info(
        "gateway.user_query",
        user_id=user_id,
        post_count=len(posts),
        order_count=len(orders),
        total_latency_ms=elapsed_ms,
    )

    return UserWithRelations(
        id=user_row["id"],
        name=user_row["name"],
        email=user_row["email"],
        posts=posts,
        orders=orders,
    )


# ==========================================================================
# 7. BFF (BACKEND-FOR-FRONTEND) PATTERN
#
#    A single GraphQL service aggregates multiple non-GraphQL downstream
#    services (REST, gRPC, etc.) via asyncio.gather.  No federation needed.
#    Common when you own all services or are wrapping legacy REST APIs.
# ==========================================================================

@dataclass
class DashboardData:
    """Aggregated view for the client dashboard — produced by the BFF."""

    user_name: str
    total_posts: int
    total_orders: int
    pending_orders: int
    total_spend: float


async def _bff_get_user(user_id: str) -> dict:
    """Simulate a REST GET /users/{id} call."""
    await asyncio.sleep(0)          # yield to event loop (simulate I/O)
    return USERS_DB.get(user_id, {})


async def _bff_get_posts(user_id: str) -> list[dict]:
    """Simulate a REST GET /posts?author={id} call."""
    await asyncio.sleep(0)
    return [p for p in POSTS_DB.values() if p["author_id"] == user_id]


async def _bff_get_orders(user_id: str) -> list[dict]:
    """Simulate a REST GET /orders?user={id} call."""
    await asyncio.sleep(0)
    return [o for o in ORDERS_DB.values() if o["user_id"] == user_id]


async def bff_dashboard(user_id: str) -> Optional[DashboardData]:
    """BFF resolver: fan-out to three downstream services concurrently.

    This pattern is used when the client needs an aggregated view and all
    downstream services are non-GraphQL.  A single round-trip replaces three.
    """
    user, posts, orders = await asyncio.gather(
        _bff_get_user(user_id),
        _bff_get_posts(user_id),
        _bff_get_orders(user_id),
    )

    if not user:
        return None

    pending = [o for o in orders if o["status"] == "PENDING"]
    spend = sum(o["amount"] for o in orders)

    return DashboardData(
        user_name=user["name"],
        total_posts=len(posts),
        total_orders=len(orders),
        pending_orders=len(pending),
        total_spend=round(spend, 2),
    )


# ==========================================================================
# 8. SCHEMA STITCHING — LEGACY APPROACH (illustrative, not production)
#
#    Before federation, gateways manually stitched schemas by reading each
#    remote schema and attaching delegate resolvers.  More flexible, but
#    entirely manual.  Apollo Federation v2 is now preferred.
# ==========================================================================

SCHEMA_STITCHING_PSEUDOCODE = """
# Pseudo-Python illustrating schema stitching (as done in JS with graphql-tools).
# In Python you would use ariadne + httpx to replicate this pattern.

async def stitch_schemas(subgraph_urls: list[str]) -> CombinedSchema:
    remote_schemas = []
    for url in subgraph_urls:
        sdl = await fetch_sdl(url)
        remote_schemas.append(build_remote_schema(sdl, url))

    combined = merge_schemas(remote_schemas)

    # Manually extend User to include posts (stitching step)
    combined.extend_type(
        type_name="User",
        field_name="posts",
        selection_set="{ id }",
        resolve=lambda parent, info: fetch_posts_by_user(parent["id"]),
    )

    return combined
"""


# ==========================================================================
# 9. FASTAPI APPLICATION — mounts all three subgraph schemas + gateway routes
# ==========================================================================

app = FastAPI(
    title="GraphQL Federation Demo",
    description="Illustrates Apollo Federation v2, BFF pattern, and schema stitching",
    version="1.0.0",
)

# Mount each subgraph at its canonical path
# In a real deployment each of these would be a separate microservice process.
app.include_router(
    GraphQLRouter(user_subgraph_schema),
    prefix="/graphql/users",
)
app.include_router(
    GraphQLRouter(post_subgraph_schema),
    prefix="/graphql/posts",
)
app.include_router(
    GraphQLRouter(order_subgraph_schema),
    prefix="/graphql/orders",
)


@app.get("/gateway/user/{user_id}", tags=["Gateway"])
async def gateway_user(user_id: str):
    """Simulates a federated gateway query for a User with posts and orders.

    Equivalent to sending this GraphQL query to Apollo Router:
        { user(id: "<user_id>") { name email posts { title } orders { amount status } } }
    """
    result = await gateway_user_query(user_id)
    if result is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"User {user_id!r} not found")
    return {
        "id": result.id,
        "name": result.name,
        "email": result.email,
        "posts": result.posts,
        "orders": result.orders,
    }


@app.get("/bff/dashboard/{user_id}", tags=["BFF"])
async def bff_dashboard_endpoint(user_id: str):
    """BFF endpoint: aggregates User, Post, and Order data in one response.

    Demonstrates asyncio.gather-based fan-out to multiple downstream services.
    """
    data = await bff_dashboard(user_id)
    if data is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"User {user_id!r} not found")
    return {
        "user_name": data.user_name,
        "total_posts": data.total_posts,
        "total_orders": data.total_orders,
        "pending_orders": data.pending_orders,
        "total_spend": data.total_spend,
    }


@app.get("/health", tags=["Ops"])
async def health():
    """Liveness probe — confirms all subgraph schemas are initialised."""
    return {
        "status": "ok",
        "subgraphs": {
            "users": "/graphql/users",
            "posts": "/graphql/posts",
            "orders": "/graphql/orders",
        },
    }


# ==========================================================================
# 10. FEDERATION COMPOSITION RULES — documented as constants for reference
#
#     Apollo Federation v2 enforces these at schema-compose time.
#     Violating them causes composition to fail before any service starts.
# ==========================================================================

COMPOSITION_RULES = {
    "entity_must_have_key": (
        "Every federated type must declare at least one @key. "
        "If a subgraph defines a type without @key it cannot be resolved "
        "across subgraph boundaries."
    ),
    "no_conflicting_definitions": (
        "Two subgraphs cannot define the same field on a shared entity "
        "unless one uses @override to take ownership."
    ),
    "extend_requires_external_keys": (
        "When a subgraph extends an entity it must mark the key field(s) "
        "as external=True — they are provided by the owning subgraph."
    ),
    "resolve_reference_required_for_extends": (
        "Every subgraph that extends an entity must implement "
        "resolve_reference(cls, **kwargs) so the gateway can hydrate stubs."
    ),
    "validate_with_rover": (
        "Run: rover subgraph check <graph-ref> --schema schema.graphql "
        "--name <subgraph-name>   to validate before deploying."
    ),
}


# ==========================================================================
# 11. OBSERVABILITY NOTES — how to instrument a real federated deployment
# ==========================================================================

OBSERVABILITY_NOTES = """
Federated observability checklist:

1. Trace propagation
   Inject W3C traceparent header at the gateway and forward it to every
   subgraph.  Use opentelemetry-sdk + opentelemetry-instrumentation-fastapi.

2. Per-subgraph latency
   Each subgraph should expose a Prometheus /metrics endpoint.
   Apollo Router exports per-subgraph histograms out of the box.

3. Query plan inspection
   Apollo Router can log the full query plan (what it sends to each
   subgraph) via:
       telemetry:
         exporters:
           tracing:
             stdout:
               enabled: true

4. Composition health
   Use Apollo Studio (or Hive) schema registry to detect composition errors
   before they reach production.  Each subgraph CI pipeline calls:
       rover subgraph publish ...

5. Structured per-request logs
   Include: user_id, operation_name, subgraph_name, latency_ms, error.
   Centralise in Datadog / Loki / Elasticsearch.
"""


# ==========================================================================
# 12. GATEWAY ROUTER CONFIG REFERENCE  (YAML — not executed by Python)
# ==========================================================================

APOLLO_ROUTER_CONFIG_YAML = """
# router.yaml — drop this next to the Apollo Router binary
federation_version: 2

subgraphs:
  users:
    routing_url: http://user-svc:4001/graphql
  posts:
    routing_url: http://post-svc:4002/graphql
  orders:
    routing_url: http://order-svc:4003/graphql

cors:
  origins:
    - https://app.example.com
  allow_credentials: true

telemetry:
  instrumentation:
    spans:
      default_attribute_requirement_level: recommended
"""


# ==========================================================================
# 13. STANDALONE DEMO  — runs without external services
# ==========================================================================

async def _demo() -> None:
    """Exercise the in-process gateway and BFF layer."""
    print("\n" + "=" * 60)
    print("GraphQL Federation — In-Process Demo")
    print("=" * 60)

    # Gateway: cross-subgraph user query
    print("\n[Gateway] Federated query for user '1' (name + posts + orders)")
    user_data = await gateway_user_query("1")
    if user_data:
        print(f"  User   : {user_data.name} <{user_data.email}>")
        print(f"  Posts  : {[p['title'] for p in user_data.posts]}")
        print(f"  Orders : {[(o['amount'], o['status']) for o in user_data.orders]}")

    # Gateway: user with no orders
    print("\n[Gateway] Federated query for user '3' (no orders)")
    user_data_3 = await gateway_user_query("3")
    if user_data_3:
        print(f"  User   : {user_data_3.name}")
        print(f"  Orders : {user_data_3.orders}")

    # BFF dashboard
    print("\n[BFF] Dashboard for user '1'")
    dashboard = await bff_dashboard("1")
    if dashboard:
        print(f"  Name           : {dashboard.user_name}")
        print(f"  Total posts    : {dashboard.total_posts}")
        print(f"  Total orders   : {dashboard.total_orders}")
        print(f"  Pending orders : {dashboard.pending_orders}")
        print(f"  Total spend    : ${dashboard.total_spend:.2f}")

    # Composition rules summary
    print("\n[Composition Rules]")
    for rule, description in COMPOSITION_RULES.items():
        print(f"  {rule}: {description[:80]}...")

    print("\n[Subgraph Routes] (start uvicorn to explore)")
    print("  User  subgraph  : http://localhost:8000/graphql/users")
    print("  Post  subgraph  : http://localhost:8000/graphql/posts")
    print("  Order subgraph  : http://localhost:8000/graphql/orders")
    print("  Gateway REST    : http://localhost:8000/gateway/user/1")
    print("  BFF REST        : http://localhost:8000/bff/dashboard/1")
    print()


if __name__ == "__main__":
    asyncio.run(_demo())
