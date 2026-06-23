# GraphQL vs REST vs gRPC

---

## Quick Comparison

| | REST | GraphQL | gRPC |
|--|------|---------|------|
| Protocol | HTTP/1.1 | HTTP/1.1 | HTTP/2 |
| Data format | JSON | JSON | Protobuf (binary) |
| Schema | OpenAPI (optional) | Strongly typed schema | Proto file (required) |
| Versioning | URL versioning (/v1, /v2) | Schema evolution | Proto evolution |
| Fetching | Fixed response shape | Client specifies shape | Fixed RPC methods |
| Over-fetching | Common | Eliminated | No (methods are specific) |
| Streaming | Limited | Subscriptions | Full bidirectional streaming |
| Performance | Medium | Medium | High |
| Browser support | Full | Full | Limited (needs grpc-web) |
| Learning curve | Low | Medium | Medium-High |
| Best for | Public APIs, CRUD | Frontend-heavy apps | Internal microservices |

---

# REST

## How it works
```
GET    /users/123          → get user
POST   /users              → create user
PUT    /users/123          → update user
DELETE /users/123          → delete user
```

## Pros
- Universal support — every language, browser, tool works with REST
- Easy to cache (GET requests are cacheable by default)
- Stateless — easy to scale horizontally
- Great for public APIs

## Cons
- Over-fetching: `/users/123` returns full user object even if you only need the name
- Under-fetching: need multiple calls to get related data
  ```
  GET /users/123          → get user
  GET /users/123/posts    → get their posts  (2nd call)
  GET /posts/45/comments  → get comments     (3rd call)
  ```
- No real-time support (need to add WebSockets separately)

---

# GraphQL

## How it works
Single endpoint `/graphql`. Client specifies exactly what it needs.

```graphql
# Query — get only name and email, plus their last 3 posts
query {
  user(id: "123") {
    name
    email
    posts(last: 3) {
      title
      createdAt
    }
  }
}

# Mutation — create data
mutation {
  createPost(title: "Hello", content: "World") {
    id
    title
  }
}

# Subscription — real-time
subscription {
  messageAdded(chatId: "456") {
    text
    sender
  }
}
```

## Pros
- No over-fetching or under-fetching
- One endpoint for everything
- Strongly typed schema = self-documenting API
- Great for mobile apps (save bandwidth)
- Subscriptions for real-time

## Cons
- Complex queries can hit DB hard (N+1 problem) — need DataLoader
- Caching is hard (POST requests, dynamic queries)
- File uploads awkward
- Harder to rate limit (one endpoint, variable cost queries)

## N+1 Problem & DataLoader
```
# This query causes N+1 DB calls without DataLoader
query {
  posts {           # 1 query to get posts
    author {        # N queries, one per post to get author
      name
    }
  }
}

# DataLoader batches the N author queries into 1:
SELECT * FROM users WHERE id IN (1, 2, 3, 4, 5)
```

---

# gRPC

## How it works
Define service in `.proto` file. Generate client/server code. Call like a local function.

```proto
// user.proto
service UserService {
  rpc GetUser (GetUserRequest) returns (User);
  rpc CreateUser (CreateUserRequest) returns (User);
  rpc StreamUsers (Empty) returns (stream User);      // server streaming
  rpc Chat (stream Message) returns (stream Message); // bidirectional streaming
}

message User {
  string id = 1;
  string name = 2;
  string email = 3;
}
```

```python
# Client calls it like a local function
stub = UserServiceStub(channel)
user = stub.GetUser(GetUserRequest(id="123"))
print(user.name)
```

## Pros
- Fastest — Protobuf binary is 3-10x smaller than JSON
- Strongly typed — compile-time errors
- Built-in streaming (server, client, bidirectional)
- Code generation for all languages
- HTTP/2 multiplexing = multiple requests over one connection

## Cons
- Not browser-native (need grpc-web proxy)
- Binary format = not human-readable (harder to debug)
- Requires proto file setup
- Harder to test manually (no curl/Postman without plugins)

---

## When to Use What

| Scenario | Use |
|----------|-----|
| Public API for third parties | REST |
| Mobile app, need to minimize data | GraphQL |
| Internal microservice communication | gRPC |
| Real-time data (chat, notifications) | GraphQL Subscriptions or WebSocket |
| File upload/download | REST |
| High-throughput internal RPC | gRPC |
| Dashboard with complex data requirements | GraphQL |
| Simple CRUD service | REST |

---

## Real World

| Company | What they use |
|---------|--------------|
| GitHub | REST (public) + GraphQL (v4 API) |
| Facebook | GraphQL (invented it) |
| Netflix | gRPC (internal), REST (external) |
| Google | gRPC everywhere internally |
| Shopify | GraphQL |
| Twitter/X | REST |

---

## Interview Tip
> "For our public API we use REST — it's easy to consume and cache. For our mobile app we use GraphQL to avoid over-fetching on slow connections. For internal service-to-service calls we use gRPC — Protobuf is faster and the generated clients reduce integration errors."
