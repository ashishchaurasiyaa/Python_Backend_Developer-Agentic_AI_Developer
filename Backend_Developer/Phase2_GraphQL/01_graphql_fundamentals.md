# 01 — GraphQL Fundamentals

> Single endpoint, typed schema, client-defined queries. Eliminates over-fetching and under-fetching.

---

## Why GraphQL Exists

**REST problems:**
- Over-fetching: `/users/123` returns 50 fields, client needs 3.
- Under-fetching: To render a screen, client makes 5 requests.
- Versioning churn: `/v1`, `/v2` proliferation.

**GraphQL fixes:**
- Client says exactly what fields it wants.
- One round-trip can fetch nested data from multiple resources.
- Schema is typed and self-documenting.

---

## Core Concepts

### Schema (SDL — Schema Definition Language)

```graphql
type User {
  id: ID!
  name: String!
  email: String!
  posts: [Post!]!
}

type Post {
  id: ID!
  title: String!
  content: String
  author: User!
}

type Query {
  user(id: ID!): User
  posts(limit: Int = 10): [Post!]!
}

type Mutation {
  createPost(input: CreatePostInput!): Post!
}

input CreatePostInput {
  title: String!
  content: String
}
```

- `!` = non-null.
- `[Post!]!` = non-null list of non-null Posts.
- Three root operation types: `Query`, `Mutation`, `Subscription`.

### Query

Client sends a query string. Server returns matching shape.

```graphql
query {
  user(id: "123") {
    name
    posts {
      title
      content
    }
  }
}
```

Response:
```json
{
  "data": {
    "user": {
      "name": "Alice",
      "posts": [
        {"title": "Hello", "content": "World"},
        {"title": "GraphQL", "content": "Rocks"}
      ]
    }
  }
}
```

Server returns exactly what was asked. No more, no less.

### Mutation

For writes. Same syntax, different intent. Conventional separation.

```graphql
mutation {
  createPost(input: {title: "New post", content: "..."}) {
    id
    title
  }
}
```

### Subscription

Server-pushed events over WebSocket.

```graphql
subscription {
  newPost {
    id
    title
    author { name }
  }
}
```

Client gets pushed every time a new post is created.

---

## How GraphQL Resolves Queries

Each field has a **resolver function**: given parent + args + context, return value.

```python
# Pseudo-resolver tree for above query
def resolve_user(parent, args, ctx):
    return db.fetch_user(args["id"])

def resolve_posts(user, args, ctx):  # parent = User
    return db.fetch_posts_by_user(user.id)

# Walked depth-first:
# 1. resolve_user(None, {"id": "123"}, ctx) → User
# 2. resolve_posts(user, {}, ctx) → list of Post
# 3. for each post: extract title, content (auto-resolved from object)
```

---

## Types of Resolvers

### Trivial (auto-resolve)
If the parent object already has the field as an attribute, no resolver needed.

```python
user = User(id=1, name="Alice")
# Field 'name' on User → returns user.name automatically
```

### Custom
Needed for derived fields or relationships requiring lookup.

```python
def resolve_post_count(user, args, ctx):
    return db.count_posts(user.id)
```

---

## Scalars

Built-in: `Int`, `Float`, `String`, `Boolean`, `ID`.

Custom scalars:
```graphql
scalar DateTime
scalar JSON
scalar UUID
```

You provide:
- Parse function (input string → Python value).
- Serialize function (Python value → output).

---

## Enums

```graphql
enum Status {
  ACTIVE
  PENDING
  DISABLED
}

type User {
  status: Status!
}
```

Type-safe alternative to strings.

---

## Interfaces & Unions

### Interface
Shared fields across types.

```graphql
interface Node {
  id: ID!
}

type User implements Node {
  id: ID!
  name: String!
}

type Post implements Node {
  id: ID!
  title: String!
}
```

### Union
"Either A or B" relationship.

```graphql
union SearchResult = User | Post | Comment

type Query {
  search(q: String!): [SearchResult!]!
}
```

Client uses inline fragments to discriminate:
```graphql
{
  search(q: "alice") {
    ... on User { name email }
    ... on Post { title }
  }
}
```

---

## Fragments

Reusable query fragments. DRY for client-side queries.

```graphql
fragment UserSummary on User {
  id
  name
  avatar
}

query {
  user(id: "1") { ...UserSummary email }
  posts { author { ...UserSummary } }
}
```

---

## Directives

Modify query behavior.

### Built-in
```graphql
query GetUser($includeEmail: Boolean!) {
  user(id: "1") {
    name
    email @include(if: $includeEmail)
    posts @skip(if: false) { title }
  }
}
```

### Custom (server-defined)
```graphql
directive @auth(role: String!) on FIELD_DEFINITION

type Query {
  adminPanel: AdminData @auth(role: "ADMIN")
}
```

---

## Variables

Don't string-interpolate queries; use variables.

```graphql
query GetUser($id: ID!) {
  user(id: $id) { name }
}
```

```json
{
  "query": "...",
  "variables": {"id": "123"}
}
```

Reasons:
- Caching: same query string, different variables.
- Security: prevents injection.
- Type safety: variables typed.

---

## Errors

GraphQL returns 200 OK even on errors. Errors are in the response body.

```json
{
  "data": null,
  "errors": [
    {
      "message": "User not found",
      "locations": [{"line": 2, "column": 3}],
      "path": ["user"],
      "extensions": {"code": "NOT_FOUND"}
    }
  ]
}
```

Partial data is possible: some fields succeed, others fail.

```json
{
  "data": {
    "user": {"name": "Alice", "posts": null}
  },
  "errors": [{"message": "DB timeout", "path": ["user", "posts"]}]
}
```

---

## Pagination

Two patterns:

### Offset-based
```graphql
type Query {
  posts(limit: Int = 10, offset: Int = 0): [Post!]!
}
```
Simple, but bad at scale.

### Cursor-based (Relay-style)
```graphql
type PostConnection {
  edges: [PostEdge!]!
  pageInfo: PageInfo!
}

type PostEdge {
  cursor: String!
  node: Post!
}

type PageInfo {
  hasNextPage: Boolean!
  endCursor: String
}

type Query {
  posts(first: Int = 10, after: String): PostConnection!
}
```
Industry standard. Stable under inserts.

---

## REST vs GraphQL Comparison

| | REST | GraphQL |
|---|---|---|
| Endpoints | Many | One |
| Versioning | URL path | Schema evolution (deprecation) |
| Over-fetch | Common | Eliminated |
| Caching | HTTP cache | App-level (DataLoader) |
| Discoverability | OpenAPI | Built-in introspection |
| File upload | Native | Workaround (multipart) |
| Browser support | Native | Native |
| Type system | Optional | Mandatory |

---

## When to use GraphQL

✅ Good fit:
- Mobile clients (bandwidth-sensitive, varied screens).
- BFF (Backend-for-Frontend) pattern.
- Multiple frontends consuming same data.
- Rapidly evolving schemas without versioning headache.

❌ Bad fit:
- Simple CRUD APIs (REST is simpler).
- File-heavy operations.
- Public APIs with caching needs (REST + CDN better).
- When team unfamiliar (steep learning curve).

---

## Common Beginner Mistakes

### 1. Treating GraphQL like REST
Mapping each REST endpoint to a separate query. Misses the point.

### 2. Exposing the entire DB
Not every column needs to be a field. Design for client needs.

### 3. Ignoring N+1
GraphQL's biggest performance trap. (See file 03 — DataLoader.)

### 4. No authorization
Field-level auth essential. (See file 06 — Security.)

### 5. Subscriptions everywhere
WebSocket overhead. Use only when real-time matters.

---

## Tooling Ecosystem

- **Python servers:** Strawberry, Ariadne, Graphene (older).
- **JS servers:** Apollo Server, GraphQL Yoga, Mercurius.
- **Clients:** Apollo Client, urql, Relay.
- **Tools:** GraphQL Playground (deprecated), GraphiQL, Insomnia, Altair.
- **Schema management:** Apollo Studio, Hasura, GraphQL Hive.

---

## TL;DR

- One endpoint, typed schema, client picks fields.
- Resolvers run per-field, recursively.
- Mutations for writes, Subscriptions for real-time.
- N+1 is the killer pitfall — use DataLoader.
- Field-level auth required.
- Best for mobile + BFF, not for simple CRUD.
