# GraphQL — Apollo Federation v2 + Persisted Queries (Production Deep Dive)
**Phase 2 GraphQL | Senior Backend + Agentic AI**

## Quick Concepts
- **Federation** = compose multiple GraphQL services (subgraphs) into one unified API (supergraph)
- **Apollo Federation v2** = current standard (v1 deprecated)
- **Subgraph** = individual GraphQL service owning specific types
- **Supergraph** = gateway-composed schema across all subgraphs
- **Router/Gateway** = single entry point that routes to subgraphs
- **Entity** = shared type across subgraphs (e.g., User in users-service + orders-service)
- **`@key`** = directive declaring entity primary key for federation
- **`@external` / `@requires` / `@provides`** = field-level federation directives
- **Persisted queries** = pre-registered queries by ID — security + performance
- **APQ** = Automatic Persisted Queries — Apollo's auto-registration variant

---

## Why Federation?

```
WITHOUT FEDERATION (monolithic GraphQL):
─────────────────
Single team owns 200K LOC schema
Deploy = all-or-nothing
Schema conflicts between teams

WITH FEDERATION:
────────────
Each team owns a subgraph
Independent deploys
Gateway composes at runtime
Client sees single API
```

**Use when:**
- 3+ teams owning different domains
- Microservices already exist
- Single GraphQL API for frontend, multiple data sources

---

## Architecture

```
                  ┌─────────────────────┐
                  │  Apollo Router       │
                  │  (supergraph entry)  │
                  └──────────┬───────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
  ┌─────▼─────┐        ┌─────▼─────┐        ┌─────▼─────┐
  │ users     │        │ orders    │        │ products  │
  │ subgraph  │        │ subgraph  │        │ subgraph  │
  │           │        │           │        │           │
  │ User(id)  │  ←───  │ Order ─→  │  ←───  │ Product   │
  │           │        │   user    │        │           │
  │           │        │   items   │        │           │
  └───────────┘        └───────────┘        └───────────┘
```

---

## Interview Questions & Answers

### Q1: Federation v2 subgraph with Strawberry (Python)?

**Answer:** Strawberry has first-class federation support.

```bash
pip install 'strawberry-graphql[fastapi]' strawberry-graphql[federation]
```

```python
# users_service/schema.py
import strawberry
from strawberry.federation import Schema
from strawberry.fastapi import GraphQLRouter
from fastapi import FastAPI

@strawberry.federation.type(keys=["id"])
class User:
    id: strawberry.ID
    email: str
    name: str
    created_at: str

    @classmethod
    async def resolve_reference(cls, id: strawberry.ID):
        """Federation entity resolver — called by gateway."""
        async with db_session() as session:
            user = await session.get(UserModel, int(id))
            if not user:
                return None
            return cls(
                id=str(user.id),
                email=user.email,
                name=user.name,
                created_at=user.created_at.isoformat(),
            )

@strawberry.type
class Query:
    @strawberry.field
    async def user(self, id: strawberry.ID) -> User | None:
        return await User.resolve_reference(id)

    @strawberry.field
    async def users(self, limit: int = 20) -> list[User]:
        async with db_session() as session:
            result = await session.execute(
                "SELECT id, email, name, created_at FROM users LIMIT :lim",
                {"lim": limit},
            )
            return [User(**dict(r._mapping)) for r in result.all()]

schema = Schema(query=Query, enable_federation_2=True)

app = FastAPI()
app.include_router(GraphQLRouter(schema), prefix="/graphql")
```

**Subgraph SDL (auto-generated):**
```graphql
extend schema
  @link(url: "https://specs.apollo.dev/federation/v2.3",
        import: ["@key", "@shareable", "@external", "@requires", "@provides"])

type User @key(fields: "id") {
  id: ID!
  email: String!
  name: String!
  createdAt: String!
}

type Query {
  user(id: ID!): User
  users(limit: Int = 20): [User!]!
}
```

---

### Q2: Cross-subgraph types — orders extending users?

**Answer:** Extend `User` from orders subgraph using `@key`.

```python
# orders_service/schema.py
import strawberry
from strawberry.federation import Schema

@strawberry.federation.type(keys=["id"], extend=True)
class User:
    """Reference to User from users subgraph."""
    id: strawberry.ID = strawberry.federation.field(external=True)  # external

    @strawberry.field
    async def orders(self, limit: int = 10) -> list["Order"]:
        """Each user has orders — owned by THIS subgraph."""
        async with db_session() as session:
            result = await session.execute(
                "SELECT id, total, status, created_at FROM orders WHERE user_id = :uid LIMIT :lim",
                {"uid": int(self.id), "lim": limit},
            )
            return [Order(**dict(r._mapping)) for r in result.all()]

    @strawberry.field
    async def total_spent(self) -> float:
        async with db_session() as session:
            result = await session.execute(
                "SELECT COALESCE(SUM(total), 0) FROM orders WHERE user_id = :uid",
                {"uid": int(self.id)},
            )
            return float(result.scalar())

@strawberry.federation.type(keys=["id"])
class Order:
    id: strawberry.ID
    total: float
    status: str
    created_at: str

    @strawberry.field
    async def user(self) -> User | None:
        # Return reference; gateway will fetch User fields from users subgraph
        async with db_session() as session:
            row = await session.execute(
                "SELECT user_id FROM orders WHERE id = :oid",
                {"oid": int(self.id)},
            )
            user_id = row.scalar()
            return User(id=strawberry.ID(str(user_id))) if user_id else None

@strawberry.type
class Query:
    @strawberry.field
    async def order(self, id: strawberry.ID) -> Order | None:
        # ...
        pass

schema = Schema(query=Query, types=[User, Order], enable_federation_2=True)
```

**Client query (gateway composes):**
```graphql
query {
  user(id: "42") {
    id          # from users subgraph
    email       # from users subgraph
    orders {    # from orders subgraph
      id
      total
    }
    totalSpent  # from orders subgraph
  }
}
```

Gateway:
1. Calls users subgraph for `User(id: 42)` → gets id, email
2. Calls orders subgraph with `_Any` reference `{id: "42"}` → gets orders, totalSpent

---

### Q3: Apollo Router setup + supergraph composition?

**Answer:** Use Rover CLI to compose; Router runs the supergraph.

```bash
# Install Rover (Apollo's CLI)
curl -sSL https://rover.apollo.dev/nix/latest | sh

# Compose supergraph from subgraphs
cat > supergraph.yaml <<EOF
federation_version: =2.3.0
subgraphs:
  users:
    routing_url: http://users-service:8001/graphql
    schema:
      subgraph_url: http://users-service:8001/graphql
  orders:
    routing_url: http://orders-service:8002/graphql
    schema:
      subgraph_url: http://orders-service:8002/graphql
  products:
    routing_url: http://products-service:8003/graphql
    schema:
      subgraph_url: http://products-service:8003/graphql
EOF

rover supergraph compose --config supergraph.yaml > supergraph.graphql
```

**Router config:**
```yaml
# router.yaml
supergraph:
  introspection: false  # disable in prod (security)
  query_planning:
    cache:
      in_memory:
        limit: 512

cors:
  origins:
    - https://app.acme.com
  allow_credentials: true

headers:
  all:
    request:
      - propagate:
          named: "authorization"

telemetry:
  metrics:
    prometheus:
      enabled: true
      listen: 0.0.0.0:9090
  tracing:
    propagation:
      trace_context: true

# Rate limiting
traffic_shaping:
  router:
    global_rate_limit:
      capacity: 10000
      interval: 1s
```

**Run router:**
```bash
docker run -p 4000:4000 \
  -v "$PWD/supergraph.graphql:/app/supergraph.graphql" \
  -v "$PWD/router.yaml:/app/router.yaml" \
  ghcr.io/apollographql/router \
  --supergraph /app/supergraph.graphql \
  --config /app/router.yaml
```

---

### Q4: Schema registry + managed federation?

**Answer:** Apollo Studio (or GraphOS) — schema registry + CI checks.

```bash
# Publish subgraph schema to registry
rover subgraph publish my-graph@production \
  --schema ./schema.graphql \
  --name users \
  --routing-url http://users.acme.com/graphql \
  --convert  # if upgrading from federation v1

# Check schema changes before merge
rover subgraph check my-graph@production \
  --schema ./schema.graphql \
  --name users
```

**CI check** (catches breaking changes):
```yaml
# .github/workflows/graphql.yml
name: GraphQL Schema Check
on: [pull_request]

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install Rover
        run: curl -sSL https://rover.apollo.dev/nix/latest | sh

      - name: Schema diff against production
        env:
          APOLLO_KEY: ${{ secrets.APOLLO_KEY }}
        run: |
          rover subgraph check my-graph@production \
            --schema ./schema.graphql \
            --name users
```

Output catches:
- Removed fields (breaking)
- Type changes (breaking)
- Added required arguments (breaking)
- Added fields (safe)

---

### Q5: Persisted queries (APQ) — what + why?

**Answer:** Send query hash instead of full query — security, perf, bandwidth.

**Without APQ:**
```http
POST /graphql
{"query": "query { user(id: \"42\") { name email orders { total } } }"}
# Full query (200+ bytes) every request
```

**With APQ:**
```http
# First request — send query + hash
POST /graphql
{
  "extensions": {
    "persistedQuery": {
      "version": 1,
      "sha256Hash": "abc123..."
    }
  },
  "query": "query { user(id: \"42\") { ... } }"
}
# Server caches: hash → query

# Subsequent requests — hash only
POST /graphql
{
  "extensions": {
    "persistedQuery": {
      "version": 1,
      "sha256Hash": "abc123..."
    }
  }
}
# Server resolves hash → query → executes
```

**Benefits:**
- **Security**: Block unknown queries → prevent malicious ad-hoc queries
- **Performance**: Smaller request payloads (CDN caching possible with GET)
- **Bandwidth**: 90%+ reduction for repeat queries
- **Validation**: Pre-validated queries at registration time

**Strawberry + Apollo Server APQ:**
```python
# Strawberry doesn't have built-in APQ — use middleware
import hashlib
from typing import Optional
import redis.asyncio as aioredis

redis = aioredis.from_url("redis://localhost")
QUERY_CACHE_TTL = 86400  # 24 hours

async def apq_middleware(request: dict) -> dict:
    """Handle APQ in request before strawberry processing."""
    extensions = request.get("extensions", {})
    persisted = extensions.get("persistedQuery")

    if not persisted:
        return request

    pq_hash = persisted["sha256Hash"]
    query = request.get("query")

    if query:
        # Client sending full query — verify hash + cache
        actual_hash = hashlib.sha256(query.encode()).hexdigest()
        if actual_hash != pq_hash:
            raise ValueError("PersistedQueryHashMismatch")
        await redis.setex(f"apq:{pq_hash}", QUERY_CACHE_TTL, query)
        return request

    # Client only sent hash — look it up
    cached = await redis.get(f"apq:{pq_hash}")
    if not cached:
        # Return special response asking client to send full query
        return {"errors": [{"message": "PersistedQueryNotFound", "extensions": {"code": "PERSISTED_QUERY_NOT_FOUND"}}]}

    request["query"] = cached.decode()
    return request
```

---

### Q6: Safelisted persisted queries (production security)?

**Answer:** Build-time registration — block ANY query not in safelist.

**Build process:**
```bash
# Frontend build step: extract all queries → hash → upload
npx graphql-codegen
npx persisted-query-list extract \
  --documents='src/**/*.graphql' \
  --output=persisted-queries.json

# Output: { "abc123": "query { ... }", "def456": "mutation { ... }" }

# Upload to GraphOS / your registry
rover persisted-queries publish my-graph@prod \
  --manifest persisted-queries.json
```

**Server enforces safelist:**
```yaml
# router.yaml
persisted_queries:
  enabled: true
  safelist:
    enabled: true   # reject queries not in list
    require_id: true  # client MUST send hash, not query
  log_unknown: true
```

**Effect:**
- ✅ Frontend uses approved queries by hash
- ❌ Attacker can't craft arbitrary queries
- ✅ DoS via expensive queries impossible (unknown query rejected)

---

### Q7: N+1 problem in federation — DataLoader?

**Answer:** Federation amplifies N+1; use DataLoader within each subgraph.

```python
import strawberry
from strawberry.dataloader import DataLoader

async def load_users_by_ids(user_ids: list[int]) -> list[User]:
    """Batch load — one query for all IDs."""
    async with db_session() as session:
        result = await session.execute(
            "SELECT id, email, name FROM users WHERE id = ANY(:ids)",
            {"ids": user_ids},
        )
        rows = {r.id: r for r in result.all()}
    # Return in same order as requested IDs
    return [rows.get(uid) for uid in user_ids]

@strawberry.type
class Order:
    id: strawberry.ID
    user_id: int

    @strawberry.field
    async def user(self, info) -> User | None:
        # Uses dataloader from context — batched across all Orders in query
        loader: DataLoader = info.context["user_loader"]
        return await loader.load(self.user_id)

# Mount with per-request DataLoaders
async def context_getter():
    return {
        "user_loader": DataLoader(load_fn=load_users_by_ids),
    }

router = GraphQLRouter(schema, context_getter=context_getter)
```

**Without DataLoader:**
```
Query: 100 orders + user for each
→ 1 query for orders + 100 queries for users (101 total!)
```

**With DataLoader:**
```
Query: 100 orders + user for each
→ 1 query for orders + 1 query for all 100 users (2 total)
```

---

### Q8: Query complexity + depth limiting (DoS protection)?

**Answer:** Reject expensive queries before execution.

```python
from strawberry.extensions import QueryDepthLimiter, MaxAliasesLimiter
from strawberry.extensions.tracing import OpenTelemetryExtension

# Strawberry built-in limiters
schema = Schema(
    query=Query,
    extensions=[
        QueryDepthLimiter(max_depth=10),         # block deeply-nested queries
        MaxAliasesLimiter(max_alias_count=15),   # block alias-bombing
        OpenTelemetryExtension(),
    ],
    enable_federation_2=True,
)
```

**Custom complexity calculation:**
```python
from graphql import validate, parse
from graphql.validation import ValidationRule

class ComplexityLimit(ValidationRule):
    def __init__(self, context, max_complexity=1000):
        super().__init__(context)
        self.complexity = 0
        self.max_complexity = max_complexity

    def enter_field(self, node, *args):
        # Each field = 1 point; multipliers for lists
        self.complexity += self._field_cost(node)
        if self.complexity > self.max_complexity:
            self.context.report_error(
                f"Query complexity {self.complexity} exceeds max {self.max_complexity}"
            )

    def _field_cost(self, node):
        # Look up @cost directive or default
        # Field with `first: 100` → cost ×100
        for arg in node.arguments:
            if arg.name.value in ("first", "limit"):
                return int(arg.value.value)
        return 1
```

**Schema-level cost annotations:**
```graphql
type Query {
  users(first: Int!): [User!]! @cost(complexity: 5, multipliers: ["first"])
  expensiveReport: Report @cost(complexity: 100)
}
```

---

## Production Stack — Full Example

```yaml
# docker-compose.yml
version: '3'
services:
  users-service:
    build: ./services/users
    environment:
      DATABASE_URL: postgres://postgres:postgres@postgres-users/users

  orders-service:
    build: ./services/orders
    environment:
      DATABASE_URL: postgres://postgres:postgres@postgres-orders/orders

  products-service:
    build: ./services/products
    environment:
      DATABASE_URL: postgres://postgres:postgres@postgres-products/products

  router:
    image: ghcr.io/apollographql/router:v1.50
    ports: ["4000:4000"]
    volumes:
      - ./supergraph.graphql:/app/supergraph.graphql
      - ./router.yaml:/app/router.yaml
    environment:
      APOLLO_TELEMETRY_DISABLED: "true"
    command:
      - --supergraph=/app/supergraph.graphql
      - --config=/app/router.yaml
    depends_on:
      - users-service
      - orders-service
      - products-service

  redis:
    image: redis:7
```

---

## Federation v1 vs v2 (migration)

| Feature | v1 | v2 |
|---|---|---|
| `@key` | Single field | Multiple fields possible |
| `@shareable` | Not needed | Required for shared types |
| `@inaccessible` | Not available | Hide fields from supergraph |
| `@override` | Not available | Move ownership of field |
| Composition | Build-time | Build-time (faster) |
| `extend type` | Common | Use `@key(resolvable: false)` instead |

---

## Production Gotchas

| Gotcha | Fix |
|---|---|
| Subgraph schema changes break supergraph | CI checks with `rover subgraph check` |
| Slow subgraph slows entire query | Per-subgraph timeouts + circuit breakers |
| N+1 across subgraphs | DataLoader per subgraph + entity batching |
| Auth context lost between subgraphs | Propagate headers via Router config |
| Cyclic dependencies between subgraphs | Use `@external` carefully; avoid cycles |
| Persisted queries cache fills up | TTL or LRU eviction |
| Hash collision (theoretical) | SHA-256 prevents practical collisions |
| Schema introspection enabled in prod | Disable; use registry instead |
| Router single point of failure | Run multiple Router replicas behind LB |
| Federation v1 entity errors | Migrate to v2 (`enable_federation_2=True`) |

---

## When NOT to Use Federation

- Single team / monolithic app
- Less than 3 distinct domains
- Can't run gateway (regulatory / network)
- Team unfamiliar with GraphQL operationally

**Alternative:** Single GraphQL with logical separation by module.

---

## Senior-level Checklist

- [ ] Apollo Federation v2 (not v1)
- [ ] Each subgraph independently deployable
- [ ] Schema registry (GraphOS or self-hosted)
- [ ] CI `rover subgraph check` on every PR
- [ ] DataLoader per subgraph (N+1 prevention)
- [ ] Query depth + complexity limits
- [ ] Persisted queries enabled (APQ at minimum)
- [ ] Safelisted persisted queries in production (no ad-hoc)
- [ ] Introspection DISABLED in production
- [ ] Router replicas behind LB (no SPOF)
- [ ] Per-subgraph timeouts in Router
- [ ] Header propagation (auth context)
- [ ] Distributed tracing across subgraphs (OpenTelemetry)
- [ ] Rate limiting at Router
- [ ] Schema docs published to consumers

---

## Related Docs
- `01_graphql_fundamentals.md` — GraphQL basics
- `02_strawberry_fastapi.md` — Strawberry framework
- `03_n_plus_one_dataloader.md` — DataLoader pattern
- `05_federation_gateway.md` — basic federation
- `06_security_best_practices.md` — GraphQL security
- `Phase3_API_Design/19_asyncapi_event_driven_spec.md` — async API specs
- `Phase3_Microservices/02_api_gateway_service_comm.md` — gateways

## External References
- Apollo Federation v2: https://www.apollographql.com/docs/federation
- Strawberry federation: https://strawberry.rocks/docs/guides/federation
- Apollo Router: https://www.apollographql.com/docs/router
- Persisted Queries: https://www.apollographql.com/docs/router/configuration/persisted-queries
