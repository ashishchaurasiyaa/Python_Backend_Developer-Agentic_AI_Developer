# 🌐 API Architecture Patterns — REST, GraphQL, gRPC

> **Target:** 3-5 YOE | **Goal:** API styles deep — when which, trade-offs, design patterns.

---

## Part 1: WHAT — API Styles Kya Hai?

### Three Main Styles

1. **REST** — Resource-based, HTTP standard
2. **GraphQL** — Query language, single endpoint
3. **gRPC** — RPC over HTTP/2, binary

### Real-Life Analogy 🍽️

#### REST = Buffet
- Items laid out (resources)
- Take what you want
- Standard format

#### GraphQL = Custom Order
- Specify exactly what you want
- Server makes it
- Tailored response

#### gRPC = Drive-Through
- Quick, efficient
- Predefined options
- Fast transactions

---

## Part 2: WHY — API Style Critical?

### Reason 1: Performance

Different styles = different performance.

### Reason 2: Developer Experience

Some easier for frontend, some for backend.

### Reason 3: Use Case Fit

Public API ≠ internal microservices.

### Reason 4: Ecosystem

Tooling, libraries, support differ.

---

## Part 3: REST DEEP

### Principles

#### 1. Stateless
> Each request independent. Server stores no client state.

#### 2. Client-Server
> Separation of concerns.

#### 3. Cacheable
> Responses can be cached.

#### 4. Layered
> Client doesn't know layers (proxy, LB).

#### 5. Uniform Interface
> Same patterns everywhere.

#### 6. Code on Demand (Optional)
> Server can send code (rarely used).

### Resources

> Everything is a resource.

```
/users          ← collection
/users/123      ← specific user
/users/123/orders  ← user's orders
```

### HTTP Methods

| Method | Use | Idempotent |
|--------|-----|-----------|
| GET | Read | Yes |
| POST | Create | No |
| PUT | Replace | Yes |
| PATCH | Update partial | No (debated) |
| DELETE | Remove | Yes |
| HEAD | Metadata only | Yes |
| OPTIONS | What's allowed | Yes |

### Status Codes

```
2xx Success:
- 200 OK
- 201 Created
- 204 No Content

3xx Redirect:
- 301 Moved Permanently
- 304 Not Modified

4xx Client Error:
- 400 Bad Request
- 401 Unauthorized
- 403 Forbidden
- 404 Not Found
- 429 Too Many Requests

5xx Server Error:
- 500 Internal Server Error
- 502 Bad Gateway
- 503 Service Unavailable
```

### Headers

```
Content-Type: application/json
Accept: application/json
Authorization: Bearer <token>
Cache-Control: max-age=3600
X-RateLimit-Remaining: 95
```

### URL Design

#### Good
```
GET    /users           → list
POST   /users           → create
GET    /users/123       → get
PATCH  /users/123       → update
DELETE /users/123       → delete

GET /users/123/orders   → user's orders
POST /users/123/orders  → create order
```

#### Bad
```
GET /getUsers           → verb in URL ❌
POST /createUser        → method already says ❌
GET /users?action=delete → use HTTP method ❌
```

### Versioning

#### URL
```
/v1/users
/v2/users
```

#### Header
```
Accept: application/vnd.api+json; version=2
```

#### Query
```
/users?version=2
```

URL versioning most common.

### Pagination

#### Offset
```
/users?page=2&per_page=20
/users?offset=20&limit=20
```

#### Cursor
```
/users?cursor=abc123&limit=20
```

Cursor better for large data.

### Filtering, Sorting

```
GET /users?status=active&role=admin
GET /products?sort=price&order=asc
GET /orders?from=2024-01-01&to=2024-12-31
```

### REST Pros

- Industry standard
- Wide tool support
- Simple to understand
- Cacheable
- Browser-friendly

### REST Cons

- Over-fetching (get more than needed)
- Under-fetching (multiple requests needed)
- Schema not strict
- Versioning complex

---

## Part 4: GRAPHQL DEEP

### What's Different

> **One endpoint.** Client specifies exactly what data wanted.

```
POST /graphql

Query: {
  user(id: 123) {
    name
    email
    orders {
      total
      date
    }
  }
}

Response: {
  "user": {
    "name": "Bhai",
    "email": "bhai@x.com",
    "orders": [
      {"total": 100, "date": "2024-01-01"},
      {"total": 200, "date": "2024-02-01"}
    ]
  }
}
```

### Core Concepts

#### Schema
> Defines types, queries, mutations.

```
type User {
  id: ID!
  name: String!
  email: String
  orders: [Order!]!
}

type Query {
  user(id: ID!): User
  users: [User!]!
}

type Mutation {
  createUser(name: String!, email: String!): User!
}
```

#### Queries
> Read data.

#### Mutations
> Write data.

#### Subscriptions
> Real-time updates (WebSocket).

#### Resolvers
> Functions that fetch data.

### Advantages

#### No Over-Fetching
> Get exactly fields needed.

#### No Under-Fetching
> One request for nested data.

#### Strong Typing
> Schema enforced.

#### Auto-Documentation
> Schema = documentation.

#### Versioning Built-In
> Deprecate fields, add new.

### Disadvantages

#### Complexity
> Steeper learning curve.

#### Caching Harder
> Single endpoint, varying queries.

#### N+1 Problem
> Naive resolvers query DB many times.

#### Over-Fetching at DB Level
> If not careful.

### N+1 Problem

```
Query: 10 users with orders

Naive:
- 1 query: get 10 users
- 10 queries: get orders for each
Total: 11 queries

DataLoader Solution:
- 1 query: get 10 users
- 1 query: get all orders (batched)
Total: 2 queries
```

### Tools

- **Apollo** (popular)
- **Hasura** (auto-generated)
- **Graphene** (Python)
- **Strawberry** (Python, modern)

### When to Use

- Multiple clients (web, mobile, etc.)
- Complex data needs
- Backend already has data model
- Want self-documenting

### When NOT

- Simple CRUD
- Heavy caching needs
- File uploads
- Streaming

---

## Part 5: GRPC DEEP

### What Is gRPC

> **Google's RPC framework.** Uses HTTP/2 + Protocol Buffers.

### Concepts

#### Service Definition (Proto)

```
syntax = "proto3";

service UserService {
  rpc GetUser (GetUserRequest) returns (User);
  rpc ListUsers (ListUsersRequest) returns (stream User);
}

message User {
  int32 id = 1;
  string name = 2;
  string email = 3;
}
```

#### Generated Code

Proto → automatically generates client + server code in any language.

### Features

#### Strong Typing
> Compile-time checks.

#### Binary Format
> Protocol Buffers (smaller, faster than JSON).

#### HTTP/2
> Multiplexing, header compression.

#### Streaming
> Server, client, bidirectional.

#### Multi-Language
> Generate code for 10+ languages.

### Streaming Types

#### Unary
> Request → Response.

#### Server Streaming
> Request → Stream of responses.

#### Client Streaming
> Stream of requests → Response.

#### Bidirectional
> Both stream.

### Performance

> **5-10x faster** than REST/JSON typically.

#### Why
- Binary serialization
- HTTP/2 multiplexing
- Compact
- Less parsing

### Use Cases

- Microservices communication
- Real-time streaming
- Polyglot environments
- Low-latency needs

### Drawbacks

- Not browser-friendly (need proxy)
- Steeper learning
- Tooling needs
- Binary debugging harder

---

## Part 6: COMPARISON

### REST vs GraphQL vs gRPC

| Aspect | REST | GraphQL | gRPC |
|--------|------|---------|------|
| Protocol | HTTP | HTTP | HTTP/2 |
| Format | JSON typically | JSON | Protobuf (binary) |
| Schema | Optional | Required | Required |
| Caching | Easy | Hard | Hard |
| Browser | Native | Native | Via proxy |
| Performance | Medium | Medium | Fast |
| Tooling | Massive | Growing | Strong |
| Learning | Easy | Medium | Hard |
| Use case | Public APIs | Frontend-flexible | Microservices |

---

## Part 7: WHEN TO USE WHAT

### REST When

✅ Public APIs (browser, third party)
✅ Simple CRUD
✅ Need browser caching
✅ Wide compatibility needed
✅ Team familiar
✅ Mobile app (with care for over-fetch)

### GraphQL When

✅ Multiple clients with different needs
✅ Complex data relationships
✅ Want to reduce roundtrips
✅ Backend-for-frontend pattern
✅ Active mobile development
✅ Self-documentation valued

### gRPC When

✅ Microservice-to-microservice
✅ Low latency needed
✅ Polyglot environment
✅ Streaming requirements
✅ Internal APIs
✅ Performance critical

### Hybrid (Common)

```
Public APIs: REST
Mobile/Web Backend: GraphQL
Internal Microservices: gRPC
```

---

## Part 8: API DESIGN PRINCIPLES

### 1. Consistency

Same pattern throughout API.

### 2. Predictability

Developer can guess endpoints.

### 3. Backwards Compatibility

Don't break old clients.

### 4. Versioning

Plan for changes.

### 5. Documentation

Always document.

### 6. Errors

Consistent error format.

### 7. Security

Auth, HTTPS, rate limiting.

### 8. Performance

Pagination, filtering, caching.

---

## Part 9: ERROR HANDLING

### Good Error Response

```json
{
  "error": {
    "code": "INSUFFICIENT_FUNDS",
    "message": "Account balance insufficient",
    "details": {
      "balance": 100,
      "requested": 500
    },
    "request_id": "abc123"
  }
}
```

### Components

- **Code**: machine-readable
- **Message**: human-readable
- **Details**: context
- **Request ID**: for support

### Status Codes

Use HTTP standards:
- 400 = client wrong data
- 401 = need auth
- 403 = forbidden
- 404 = not found
- 422 = validation error
- 500 = server bug

---

## Part 10: API SECURITY

### Authentication

#### API Keys
> Simple, easy.
> For server-to-server.

#### JWT
> Stateless tokens.
> Common for web.

#### OAuth 2.0
> Delegation.
> "Login with Google."

### Authorization

#### RBAC (Role-Based)
> User has roles → roles have permissions.

#### ABAC (Attribute-Based)
> Decisions based on attributes.

### Rate Limiting

#### Token Bucket
> X tokens, each request consumes 1.

#### Sliding Window
> Time-based.

```
HTTP 429 Too Many Requests
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1640000000
```

### Input Validation

> Always validate.

- Type checking
- Range checking
- Format checking
- Sanitization

### HTTPS Only

Never plain HTTP.

### CORS

For browser apps:
- Same-origin allowed
- Other origins explicit

---

## Part 11: VERSIONING STRATEGIES

### URL Versioning

```
/v1/users
/v2/users
```

Pros: Clear, simple
Cons: URL changes

### Header Versioning

```
Accept: application/vnd.myapi.v1+json
```

Pros: URL stable
Cons: Headers hidden

### Query Parameter

```
/users?version=1
```

Less common.

### Content Negotiation

Different formats for different versions.

### Deprecation Strategy

```
1. Announce in advance
2. Add Deprecation header
3. Maintain old for N months
4. Sunset old version
```

---

## Part 12: PAGINATION PATTERNS

### Offset Pagination

```
GET /users?page=1&size=20
GET /users?page=2&size=20

Response:
{
  "data": [...],
  "total": 1000,
  "page": 1,
  "total_pages": 50
}
```

Pros: Easy
Cons: Slow for large offsets, duplicates if data changes

### Cursor Pagination

```
GET /users?cursor=abc123&limit=20

Response:
{
  "data": [...],
  "next_cursor": "xyz789"
}
```

Pros: Stable, fast
Cons: Can't skip pages

### Best Practice

Cursor for large data.
Offset for small, stable.

---

## Part 13: REST API BEST PRACTICES

### Naming

- Plural resources: `/users` not `/user`
- Lowercase: `/users` not `/Users`
- Hyphens: `/user-profiles` not `/user_profiles`

### HTTP Methods

- Use them correctly
- Idempotent where applicable
- Safe (GET) doesn't modify

### Response

- JSON typically
- Consistent format
- Include metadata

### Statelessness

- No session on server
- Token-based auth

### Caching

- ETag headers
- Cache-Control
- Last-Modified

---

## Part 14: BACKEND FOR FRONTEND (BFF) PATTERN

### Concept

> **Each frontend has its own backend.**

```
Web App ← BFF for Web (GraphQL)
Mobile  ← BFF for Mobile (REST or GraphQL)
TV App  ← BFF for TV (REST)
        ↓
   Microservices (gRPC)
```

### Why

- Each frontend has different needs
- Tailored data shapes
- Reduce over-fetching
- Frontend autonomy

---

## Part 15: API GATEWAY

### Role

> Single entry point for clients.

```
Client → API Gateway → Microservices
```

### Responsibilities

- Authentication
- Rate limiting
- Routing
- Caching
- Logging
- Monitoring
- Transformation

### Tools

- Kong
- AWS API Gateway
- Apigee
- Nginx
- Envoy

---

## Part 16: API DOCUMENTATION

### Tools

#### OpenAPI/Swagger
> REST documentation standard.

Auto-generated from code.
Interactive docs.

#### GraphQL Schema
> Self-documenting.

GraphiQL playground.

#### gRPC + protoc
> Proto files = documentation.

### Best Practices

- Examples
- Error responses
- Auth instructions
- Rate limits
- Changelog

---

## Part 17: TESTING

### Unit Tests

Test individual functions.

### Integration Tests

Test API endpoints.

### Contract Tests

Verify API contract (Pact, etc.).

### Load Tests

Performance under load (Locust, k6).

### Security Tests

OWASP top 10.

---

## Part 18: MONITORING

### Metrics

- Request count
- Error rate
- Latency (p50, p95, p99)
- Throughput

### Logging

- Request/response (sample)
- Errors with context
- Slow queries

### Tracing

- Distributed tracing
- Request flow
- Bottleneck identification

---

## Part 19: REAL-WORLD EXAMPLES

### Twitter API
- REST primarily
- v1.1, v2
- OAuth 2.0
- Rate limits

### GitHub API
- REST + GraphQL
- v3 REST + v4 GraphQL
- Excellent docs

### Stripe API
- REST
- Excellent design
- Versioning by date
- Detailed errors

### Slack API
- REST + WebSocket
- Comprehensive

---

## Part 20: Q&A

### Q: REST or GraphQL for public API?
**A**: REST usually. GraphQL if complex queries.

### Q: gRPC for public?
**A**: Rarely. Browser support poor.

### Q: When to version?
**A**: Always have versioning strategy. Use it before breaking changes.

### Q: Best auth?
**A**: OAuth 2.0 for users. API keys for servers. JWT for tokens.

### Q: Rate limit strategy?
**A**: Token bucket. Per IP, user, key.

### Q: REST vs GraphQL learning curve?
**A**: REST easier. GraphQL needs more learning.

### Q: gRPC performance benefit worth it?
**A**: For internal services, yes. For public, complexity not worth.

---

## 🎯 Bhai's Final Words

> **API design is craft. Bad APIs frustrate developers. Good APIs delight. Senior engineers design APIs others love to use.**

3 Mantras:
1. **Consistency** (predictable patterns)
2. **Documentation** (users need to understand)
3. **Versioning** (plan for change)

After mastering API design, your services become a pleasure to integrate with. 🚀
