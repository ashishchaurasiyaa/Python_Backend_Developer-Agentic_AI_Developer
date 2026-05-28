# REST vs GraphQL vs gRPC — Decision Framework

## Why It Matters

Choosing wrong protocol = months of pain. Each has sweet spots:
- **REST** — public APIs, browser-friendly, cacheable
- **GraphQL** — client-driven queries, mobile, BFF
- **gRPC** — service-to-service, high throughput, strong types

Senior interview: "Microservice A→B comm — REST or gRPC?" → gRPC for internal, REST for external.

---

## Comparison Matrix

| Aspect | REST | GraphQL | gRPC |
|---|---|---|---|
| Protocol | HTTP/1.1 or 2 | HTTP/1.1 or 2 | HTTP/2 |
| Format | JSON (usually) | JSON | Protobuf (binary) |
| Schema | OpenAPI (optional) | SDL (mandatory) | .proto (mandatory) |
| Browser support | Native | Native | Needs proxy (grpc-web) |
| Streaming | SSE/WS extras | Subscriptions | Native (4 modes) |
| Cacheability | HTTP cache | Manual | No HTTP cache |
| Discoverability | OpenAPI docs | Introspection | Reflection |
| Type safety | Optional | Strong | Strong |
| Verbosity | Medium | Low (over-fetch solved) | Lowest (binary) |
| Tooling | Best | Good | Specialized |
| Learning curve | Lowest | Medium | Highest |

---

## REST

### Strengths

- **Universal** — works everywhere, browser-friendly
- **Cacheable** — HTTP cache, CDN-friendly
- **Stateless** — easy horizontal scale
- **Tooling** — Postman, curl, every language has client
- **Documented** — OpenAPI / Swagger standards
- **Discoverable** — HATEOAS (optional)
- **Stable** — 20+ years of conventions

### Weaknesses

- **Over-fetching** — endpoint returns everything, client uses 10%
- **Under-fetching** — N round-trips for related data
- **Versioning** — URL changes break clients
- **No native streaming** — needs SSE/WS

### Best For

- Public APIs (GitHub, Stripe, Twilio)
- CRUD operations
- Browser-facing apps
- Wide client diversity (unknown consumers)
- Cache-heavy reads (CDN benefits)

### Example

```http
GET /api/v1/articles/123
Authorization: Bearer xyz

200 OK
{
    "id": 123,
    "title": "Hello",
    "body": "...",
    "author_id": 5
}
```

---

## GraphQL

### Strengths

- **Client-driven** — ask only for fields needed
- **Single endpoint** — no URL proliferation
- **Strong types** — schema enforced
- **Introspection** — clients can discover schema
- **Real-time** — subscriptions for live data
- **Evolves additively** — add fields without versioning
- **BFF-friendly** — different clients query different shapes

### Weaknesses

- **Caching harder** — POST not cacheable; need persisted queries
- **N+1 risk** — without DataLoader
- **Complexity attacks** — deep nested queries → DoS
- **Tooling** — fewer than REST
- **Error semantics** — non-standard (errors in 200 response)
- **Learning curve** — for both server + client
- **File uploads** — needs multipart spec

### Best For

- Mobile apps (bandwidth-constrained)
- BFF (Backend for Frontend)
- Complex/evolving data graphs
- Multiple clients with different needs (web, mobile, watch)
- Internal APIs where flexibility matters

### Example

```graphql
query {
    article(id: 123) {
        title
        body
        author {
            name
            email
        }
        comments(first: 5) {
            body
            author { name }
        }
    }
}
```

```json
{
    "data": {
        "article": {
            "title": "Hello",
            "body": "...",
            "author": {"name": "Alice", "email": "..."},
            "comments": [...]
        }
    }
}
```

---

## gRPC

### Strengths

- **Performance** — Protobuf binary, HTTP/2 multiplexing
- **Bidirectional streaming** — native (no WebSocket needed)
- **Strong contracts** — .proto generates code in all languages
- **Type safety** — compile-time checks
- **Code generation** — clients auto-generated
- **Inter-service** — designed for microservices

### Weaknesses

- **Browser support** — not direct (needs grpc-web + envoy)
- **Debugging** — binary not human-readable
- **Caching** — no HTTP cache
- **Firewalls** — HTTP/2 issues with old proxies
- **Schema discipline** — required (can be barrier)
- **Tool ecosystem** — Postman-equivalent (BloomRPC, Insomnia) less mature

### Best For

- **Internal microservices** (Kubernetes mesh)
- **Streaming** (telemetry, real-time data)
- **Multi-language services** (Python ↔ Go ↔ Java)
- **High throughput** (10x faster than JSON)
- **Mobile** (Android/iOS, not browser)

### Example

```protobuf
service ArticleService {
    rpc GetArticle(GetArticleRequest) returns (Article);
    rpc ListArticles(ListRequest) returns (stream Article);
}

message Article {
    int32 id = 1;
    string title = 2;
    string body = 3;
}
```

```python
# Client
response = stub.GetArticle(GetArticleRequest(id=123))
print(response.title)
```

---

## Hybrid Architectures

### REST + gRPC

```
[Browser/Public] → REST API Gateway → gRPC internal services
                                    → gRPC internal services
```

External world sees REST (cacheable, browser-friendly). Internal mesh = gRPC (fast, typed).

### GraphQL + REST

```
[Frontend] → GraphQL gateway → REST microservices
                             → REST microservices
```

GraphQL as BFF over existing REST services. Apollo Federation for distributed GraphQL.

### All Three (Netflix, Uber pattern)

```
Public: REST (legacy, simple)
Mobile: GraphQL (flexibility, bandwidth)
Internal: gRPC (speed, contracts)
```

---

## Decision Framework

```
Is the client a browser AND no advanced features needed?
    → REST

Is this internal service-to-service?
    Need streaming?
        → gRPC
    Same-team monorepo, low traffic?
        → REST (simpler)
    Multi-team, high throughput, polyglot?
        → gRPC

Multiple clients (web + mobile + SDK) needing flexibility?
    → GraphQL (BFF pattern)

Public API for unknown consumers?
    → REST (universal, cacheable)

Real-time bidirectional?
    Client-server simple?
        → SSE (REST + extras)
    Bidirectional?
        → WebSocket (with REST) or gRPC streaming

CDN caching critical (static content)?
    → REST (HTTP cache)

Need file uploads commonly?
    → REST (multipart) or gRPC (chunked stream)
```

---

## Migration Strategies

### REST → GraphQL

1. Build GraphQL layer that calls existing REST endpoints
2. Gradually move logic to GraphQL resolvers
3. Deprecate REST endpoints by usage

### REST → gRPC

1. Define .proto for new endpoints
2. Build gRPC services alongside REST
3. Internal callers migrate to gRPC
4. Keep REST for external

### Adding GraphQL to REST

```python
# Strawberry GraphQL on top of existing REST infra
@strawberry.type
class Article:
    @strawberry.field
    async def author(self) -> 'User':
        # Internally calls REST endpoint or DB
        return await fetch_user(self.author_id)
```

---

## Common Pitfalls

### REST Misuse

- Verb in URL (`/getUser/1`) — should be `GET /users/1`
- Status codes wrong (200 for errors)
- Versioning chaos (10 active versions)
- Over-fetching ignored (mobile drains battery)

### GraphQL Misuse

- N+1 without DataLoader
- No query complexity limit (DoS)
- Auth in resolver (slow, repeated)
- Mutations not idempotent
- Errors in 200 (clients miss them)

### gRPC Misuse

- Schema bloat (every field optional → useless)
- Wrong streaming mode (4 options, pick wrong = pain)
- No deadline (calls hang forever)
- Returning errors without status codes
- Not handling client disconnect

---

## Interview Q&A

**Q1:** REST vs GraphQL — design framework?
**A:** REST: simple CRUD, public APIs, cacheable. GraphQL: client-driven, BFF, mobile with bandwidth concern. Not "GraphQL is better" — different tools. Examples: GitHub uses both (REST v3, GraphQL v4). Stripe uses REST (simple). Facebook uses GraphQL (graph data).

**Q2:** When NOT to use GraphQL?
**A:** Simple CRUD (REST simpler). Heavy file uploads (REST multipart easier). Cache-heavy reads (HTTP cache wins). Pubic API for diverse consumers (REST universal). Small team without GraphQL expertise (learning curve).

**Q3:** gRPC vs REST internal services?
**A:** gRPC: ~10x faster (binary + HTTP/2 multiplexing). Strong types via .proto. Streaming native. Cons: browser-unfriendly, harder debugging. For service mesh with polyglot teams + high throughput, gRPC. For monorepo with small team + standard CRUD, REST is fine.

**Q4:** GraphQL caching strategies?
**A:** Persisted queries — server registers queries by hash. Client sends hash → GET with hash → cacheable URL. Apollo Client normalizes cache by ID. CDN: only works with persisted queries via GET. POST GraphQL can't be CDN-cached.

**Q5:** GraphQL N+1 prevention?
**A:** DataLoader pattern — batches + caches loads per request. Each resolver calls `loader.load(key)`, returns Future. Loader collects all keys in tick, fires single batched query. New DataLoader per request (no cross-request leak).

**Q6:** gRPC streaming use cases?
**A:** Server streaming: list endpoint returning many items (vs paginated REST). Client streaming: file upload chunks. Bidirectional: real-time chat, collaborative editing, telemetry. REST equivalents: SSE for server-streaming, WebSocket for bidirectional.

**Q7:** Hybrid: REST + GraphQL?
**A:** GraphQL gateway over existing REST microservices. Client sends GraphQL query → gateway calls multiple REST endpoints, composes response. BFF pattern. Reduces client round-trips. Keep existing REST infrastructure.

**Q8:** Versioning compared?
**A:** REST: URL (`/v1/`), header, or accept type. Big bang versions. GraphQL: additive evolution (add fields, deprecate old). No version bumps for most changes. gRPC: protobuf field numbers preserved (never reuse). Backward-compatible by default if rules followed.

---

## Real-World Examples

### GitHub: All Three

- REST API v3 (legacy, simple)
- GraphQL API v4 (preferred for new)
- gRPC internal (microservices)

### Netflix

- Public: REST + GraphQL
- Internal: gRPC (Falcor for some)

### Uber

- gRPC heavily internal (1000+ services)
- REST + GraphQL for mobile + web

### Stripe

- Public REST API (simpler for customers)
- Internal mix

---

## References

- [GraphQL spec](https://spec.graphql.org/)
- [gRPC docs](https://grpc.io/docs/)
- [REST API design (Microsoft)](https://github.com/microsoft/api-guidelines)
- [GraphQL vs REST](https://www.howtographql.com/basics/1-graphql-is-the-better-rest/)
- [Designing Data-Intensive Applications](https://dataintensive.net/) — Ch 4 (Encoding/Evolution)
