# 05 — Federation & Schema Stitching

> Combine multiple GraphQL services into one unified graph. Each service owns part of the schema; a gateway resolves cross-service queries.

---

## Problem

Microservices each expose their own GraphQL schema:
- User Service: `User`, `Profile`.
- Post Service: `Post`, `Comment`.
- Order Service: `Order`, `Payment`.

Client wants:
```graphql
{
  user(id: "1") {
    name           # from User Service
    posts {        # from Post Service
      title
    }
    orders {       # from Order Service
      amount
    }
  }
}
```

Without federation: client makes 3 separate requests. With federation: client makes 1 request to the gateway.

---

## Two Approaches

### Schema Stitching (older)
Gateway merges schemas by inspecting + delegating. Often manual config.

### Apollo Federation (modern standard)
Each subgraph declares its part of the schema using federation directives. Gateway auto-composes the supergraph.

Federation v2 (current) is the standard. Apollo + Strawberry + Ariadne all support it.

---

## Federation Basics

Each subgraph owns "entities" — types with a unique key.

### User Subgraph

```python
import strawberry

@strawberry.federation.type(keys=["id"])
class User:
    id: strawberry.ID
    name: str
    email: str

@strawberry.type
class Query:
    @strawberry.field
    async def user(self, id: strawberry.ID) -> User: ...

schema = strawberry.federation.Schema(query=Query)
```

`@strawberry.federation.type(keys=["id"])` declares `User` as a federated entity keyed by `id`.

### Post Subgraph

```python
@strawberry.federation.type(keys=["id"])
class Post:
    id: strawberry.ID
    title: str
    author_id: strawberry.ID

    @strawberry.field
    async def author(self) -> "User":   # references User from another subgraph!
        return User(id=self.author_id)

@strawberry.federation.type(keys=["id"], extend=True)
class User:
    id: strawberry.ID = strawberry.federation.field(external=True)

    @strawberry.field
    async def posts(self) -> list[Post]:
        return await db.fetch_posts(self.id)

@strawberry.type
class Query:
    @strawberry.field
    async def post(self, id: strawberry.ID) -> Post: ...

schema = strawberry.federation.Schema(query=Query)
```

Post subgraph **extends** User to add a `posts` field.

### Gateway (Apollo Router or Hive Gateway)

Gateway is typically a separate service (Apollo Router in Rust, or Cosmo Router).

```yaml
# router config
federation:
  subgraphs:
    - name: users
      url: http://user-svc:4001/graphql
    - name: posts
      url: http://post-svc:4002/graphql
    - name: orders
      url: http://order-svc:4003/graphql
```

Client query:
```graphql
{ user(id: "1") { name posts { title } } }
```

Router:
1. Fetches `name` from User Service.
2. Sees `posts` needs Post Service.
3. Sends representation `{__typename: "User", id: "1"}` to Post Service.
4. Post Service resolves `posts` for that User.
5. Router merges and returns.

---

## Entity Reference Resolution

Each subgraph that "extends" an entity must implement a reference resolver:

```python
@strawberry.federation.type(keys=["id"], extend=True)
class User:
    id: strawberry.ID = strawberry.federation.field(external=True)

    @strawberry.field
    async def posts(self) -> list[Post]: ...

    @classmethod
    async def resolve_reference(cls, id: strawberry.ID) -> "User":
        # Reconstruct minimal User from key
        return User(id=id)
```

Apollo Router sends `_entities` query under the hood:
```graphql
{
  _entities(representations: [{__typename: "User", id: "1"}]) {
    ... on User { posts { title } }
  }
}
```

---

## When to Use Federation

✅ Good fit:
- Already running microservices.
- Different teams own different domains.
- Want a unified API surface for clients.
- Schema-driven contracts.

❌ Bad fit:
- Single team, single deployment.
- Service boundaries are unclear (frequent cross-service joins → indicates wrong split).
- Too few services (< 3) → overhead not worth it.

---

## Composition Errors

Federation v2 has strict composition rules. Common errors:

### Conflicting type definitions
Two subgraphs define `User` differently → composition fails.

### Missing keys
Entity declared but no `@key` → composition fails.

### Override conflicts
Two subgraphs both define same field on shared entity without `@override`.

Use `rover` CLI or Apollo Studio to validate composition.

---

## Schema Stitching (Legacy)

Older approach. Gateway calls each subgraph, stitches results.

```python
# Pseudo
schema = stitchSchemas([
    {
        schema: user_remote_schema,
    },
    {
        schema: post_remote_schema,
    },
    {
        # Stitch the User.posts field
        typeDefs: 'extend type User { posts: [Post!]! }',
        resolvers: {
            User: {
                posts: {
                    selectionSet: '{ id }',
                    resolve: async (parent) => fetchPostsByUser(parent.id)
                }
            }
        }
    }
])
```

More flexibility, more manual work. Federation v2 is preferred.

---

## BFF (Backend-for-Frontend) Pattern

GraphQL itself acts as a BFF, aggregating multiple downstream REST/gRPC services.

```python
@strawberry.field
async def dashboard(self, info, user_id: ID) -> Dashboard:
    user, orders, recommendations = await asyncio.gather(
        user_svc.get(user_id),
        order_svc.list(user_id),
        rec_svc.get(user_id)
    )
    return Dashboard(user=user, orders=orders, recommendations=recommendations)
```

No federation needed for this — single GraphQL service over multiple non-GraphQL services.

---

## Federation vs BFF vs Stitching

| | Federation | BFF (single GQL) | Stitching |
|---|---|---|---|
| Use case | Multi-team microservices | Single client team aggregating | Legacy / flexible |
| Schema ownership | Distributed | Centralized | Hybrid |
| Composition | Auto (gateway) | Manual code | Manual config |
| Tooling | Strong (Apollo Router) | Standard GraphQL | Less common |

---

## Apollo Router vs Cosmo vs Mercurius Gateway

| Gateway | Lang | Notes |
|---|---|---|
| Apollo Router | Rust | Industry-leading, fast |
| Cosmo Router | Go | Open source, growing |
| Mercurius Gateway | Node | For Fastify-based services |
| Hive Gateway | Node | The Guild's offering |

Most teams: Apollo Router for prod federation.

---

## Versioning Federated Schemas

### Schema registry (Apollo Studio / Hive)
Each subgraph publishes its schema. Registry validates composition before deploy.

### Contract tests
Producer publishes schema; consumers test against it.

### Schema deprecation
```graphql
type User {
  oldName: String! @deprecated(reason: "Use 'name' instead")
  name: String!
}
```

Clients warned, can migrate.

---

## Observability for Federation

- Trace ID propagation across subgraphs (OpenTelemetry).
- Per-subgraph latency dashboards.
- Composition health monitoring.
- Query plan inspection (Apollo Router exposes).

---

## Real-World Examples

### GitHub GraphQL API
Single monolithic schema (no federation), but lots of teams.

### Netflix
Federation across hundreds of subgraphs.

### Shopify
Federated GraphQL across stores, products, orders.

### Atlassian
Federated across Jira, Confluence, Bitbucket.

---

## Migration Path

If you have:
- **Many REST services + new GraphQL**: BFF first.
- **Existing GraphQL services**: federate them.
- **One monolith**: split when team boundaries demand.

Don't federate prematurely — start with a single GraphQL service.

---

## TL;DR

- Federation = multiple GraphQL services, one unified graph via gateway.
- Each subgraph declares entities with `@key`.
- Cross-service queries auto-resolved by the gateway.
- Apollo Router is the standard.
- Use when you have multiple teams + services that need unified API.
- Avoid for simple cases — BFF or single GraphQL service is enough.
