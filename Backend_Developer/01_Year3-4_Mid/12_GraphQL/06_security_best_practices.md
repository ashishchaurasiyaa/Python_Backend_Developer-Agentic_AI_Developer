# 06 — GraphQL Security Best Practices

> GraphQL's flexibility is also its attack surface. These protections are mandatory in production.

---

## Threat Model

GraphQL-specific attacks:
1. **Resource exhaustion** — deeply nested or complex queries.
2. **Authorization bypass** — field-level access not enforced.
3. **Information leak** — introspection exposes internals.
4. **Injection** — same as SQL injection, via resolvers.
5. **Batching attacks** — N parallel mutations bypass rate limits.
6. **DDoS via expensive queries** — single query consumes server CPU.

---

## 1. Disable Introspection in Production

Introspection exposes your entire schema.

```graphql
{
  __schema {
    types { name fields { name type { name } } }
  }
}
```

Attackers map all available queries/mutations → easier to find weak spots.

### Strawberry config

```python
from graphql.validation import NoSchemaIntrospectionCustomRule
from strawberry.extensions import AddValidationRules

schema = strawberry.Schema(
    query=Query,
    extensions=[
        AddValidationRules([NoSchemaIntrospectionCustomRule])
    ]
)
```

Enable only in dev/staging.

---

## 2. Disable GraphiQL/Playground in Production

```python
graphql_app = GraphQLRouter(schema, graphiql=False)
```

Even if introspection blocked, GraphiQL leaks attack surface.

---

## 3. Query Depth Limit

```graphql
# Malicious deeply nested query
{
  user {
    friends {
      friends {
        friends {
          friends {
            ...  # 100 levels
          }
        }
      }
    }
  }
}
```

Exponential growth — kills server.

### Strawberry depth limit

```python
from strawberry.extensions import QueryDepthLimiter

schema = strawberry.Schema(
    query=Query,
    extensions=[QueryDepthLimiter(max_depth=10)]
)
```

Reasonable depth: 5-10. Reject anything deeper.

---

## 4. Query Complexity Analysis

Depth limit alone insufficient. A flat but wide query is also expensive:

```graphql
{
  users(first: 10000) { name email }   # depth=1, but expensive!
}
```

### Complexity scoring

Assign cost per field, sum total. Reject if over budget.

```python
# Pseudo-pattern (custom implementation)
def calculate_complexity(query):
    cost = 0
    for field in walk(query):
        cost += field.cost or 1
        if field.has_pagination_arg("first"):
            cost *= field.args.get("first", 10)
    return cost

if calculate_complexity(query) > 1000:
    raise QueryTooComplex()
```

Libraries: `graphql-cost-analysis` (JS), or custom validators in Python.

---

## 5. Field-Level Authorization

Every field needs auth check, especially nested ones.

```python
@strawberry.type
class User:
    id: strawberry.ID
    name: str
    email: str

    @strawberry.field
    async def private_settings(self, info) -> Settings:
        current_user = info.context["user"]
        if current_user.id != self.id:
            raise PermissionError("Forbidden")
        return await db.fetch_settings(self.id)
```

### Reusable permission classes

```python
from strawberry.permission import BasePermission

class IsAuthenticated(BasePermission):
    message = "Authentication required"
    def has_permission(self, source, info, **kwargs):
        return info.context["user"] is not None

class IsOwner(BasePermission):
    message = "You don't own this resource"
    def has_permission(self, source, info, **kwargs):
        return source.owner_id == info.context["user"].id

@strawberry.type
class Document:
    @strawberry.field(permission_classes=[IsAuthenticated, IsOwner])
    async def content(self) -> str: ...
```

---

## 6. Rate Limiting

Standard HTTP rate limit (Nginx, Cloudflare) blocks per-request only. GraphQL queries can be far more expensive than HTTP rate limit anticipates.

### Per-operation rate limit
```python
async def rate_limit(info, key: str, limit: int, window: int):
    redis_key = f"rl:{info.context['user'].id}:{key}"
    count = await redis.incr(redis_key)
    if count == 1:
        await redis.expire(redis_key, window)
    if count > limit:
        raise GraphQLError("Rate limit exceeded")

@strawberry.mutation
async def send_email(self, info, ...) -> bool:
    await rate_limit(info, "send_email", limit=10, window=3600)
    ...
```

### Cost-based rate limit
Each query consumes "tokens" based on complexity. User has a token budget.

---

## 7. Prevent Batching Attacks

GraphQL allows multiple operations per request:

```json
{"query": "mutation { a: createOrder { id } b: createOrder { id } c: createOrder { id } ... }"}
```

A single HTTP request could fire 100 mutations.

### Defense
- Limit operations per request (extension).
- Reject batched (apollo-engine batch protocol) in sensitive endpoints.

```python
# Custom validator: reject queries with > 5 operations
def operation_count_validator(query_ast, max_ops=5):
    op_count = sum(1 for op in query_ast.definitions if op.kind == "operation_definition")
    if op_count > max_ops:
        raise GraphQLError("Too many operations")
```

---

## 8. Pagination Limits

Don't let clients fetch unbounded data.

```python
@strawberry.field
async def users(self, first: int = 10) -> list[User]:
    if first > 100:
        raise GraphQLError("Max 100 per page")
    return await db.fetch_users(limit=first)
```

Always have a default and a max.

---

## 9. Input Validation

GraphQL only validates types. Use additional validation:

```python
from pydantic import BaseModel, validator

class CreateUserInput(BaseModel):
    email: str
    password: str

    @validator("email")
    def email_format(cls, v):
        if "@" not in v: raise ValueError("Invalid email")
        return v

    @validator("password")
    def password_strength(cls, v):
        if len(v) < 12: raise ValueError("Password too short")
        return v

@strawberry.mutation
async def create_user(self, input: CreateUserInputType) -> User:
    validated = CreateUserInput(**vars(input))
    ...
```

---

## 10. Sanitize Inputs at Resolver Boundary

Same as REST — never trust client input.

```python
import bleach

@strawberry.mutation
async def create_comment(self, content: str) -> Comment:
    safe_content = bleach.clean(content, tags=["b", "i", "a"], strip=True)
    return await db.insert_comment(safe_content)
```

For HTML/Markdown rendering, sanitize. For SQL — use parameterized queries (asyncpg, SQLAlchemy do this automatically).

---

## 11. Error Message Sanitization

Don't leak internal errors:

```python
def error_formatter(error, debug=False):
    if isinstance(error.original_error, db.exceptions.QueryError):
        return {"message": "Database error", "code": "DB_ERROR"}
    if debug:
        return {"message": error.message, "trace": format_exception(error.original_error)}
    return {"message": "Internal error", "code": "UNKNOWN"}

graphql_app = GraphQLRouter(schema, error_formatter=error_formatter)
```

Production: return generic error. Log full details server-side.

---

## 12. CORS

GraphQL endpoint is just HTTP — same CORS rules apply.

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://myapp.com"],
    allow_credentials=True,
    allow_methods=["POST", "GET"],
)
```

---

## 13. CSRF Protection

If using cookie-based auth:
- Set `SameSite=Strict` cookies.
- Require custom header (`X-Requested-With`) — browsers forbid setting it cross-origin.

If using `Authorization: Bearer ...` token:
- No CSRF risk (tokens aren't auto-sent).

---

## 14. Persisted Queries

Whitelist known queries by hash. Reject ad-hoc queries in production.

### How
1. Client computes SHA-256 of query string.
2. Client sends only hash + variables.
3. Server looks up query by hash from a pre-registered list.
4. Server executes if found, rejects if not.

```javascript
// Client
const query = `query GetUser($id: ID!) { user(id: $id) { name } }`;
const hash = sha256(query);

fetch('/graphql', {
  body: JSON.stringify({
    extensions: { persistedQuery: { sha256Hash: hash } },
    variables: { id: '1' }
  })
});
```

```python
# Server
async def execute(extensions, variables):
    hash_ = extensions["persistedQuery"]["sha256Hash"]
    query = await persisted_queries.get(hash_)
    if not query:
        raise GraphQLError("Query not allowed")
    return await schema.execute(query, variable_values=variables)
```

**Benefits:**
- Smaller request bodies.
- Pre-validated queries.
- Prevents arbitrary query execution.
- Caches faster.

**Trade-offs:**
- Build step required to register queries.
- Harder iteration during dev.

Used by: GitHub, Shopify, Facebook.

---

## 15. Query Timeout

Long-running queries lock up resources.

```python
import asyncio

async def execute_with_timeout(query, timeout=30):
    return await asyncio.wait_for(
        schema.execute(query, ...),
        timeout=timeout
    )
```

Or per-resolver timeout:
```python
@strawberry.field
async def slow_query(self) -> Result:
    return await asyncio.wait_for(do_work(), timeout=5)
```

---

## 16. Logging & Monitoring

Log:
- Query hash + execution time.
- Slow queries (> 1s).
- Auth failures.
- Rate limit hits.
- Complexity overflows.

Alert on:
- Spike in errors.
- Spike in slow queries.
- Unusual query patterns (potential attack).

---

## 17. Schema Linting

Tools like `graphql-schema-linter` enforce:
- Required descriptions.
- Naming conventions.
- Forbidden patterns (e.g., no `String!` IDs — use `ID!`).
- Required deprecation reasons.

CI step before deploy.

---

## 18. Dependency Updates

GraphQL libs have CVEs occasionally. Keep `strawberry-graphql`, `graphql-core`, transport libs updated.

```bash
pip-audit
safety check
```

---

## Production Security Checklist

```
☐ Introspection disabled in prod
☐ GraphiQL disabled in prod
☐ Query depth limit (max 10)
☐ Query complexity limit
☐ Field-level authorization
☐ Per-resolver rate limiting
☐ Pagination max enforced
☐ Input validation (Pydantic)
☐ HTML/SQL sanitization
☐ Error formatter strips internals
☐ CORS configured
☐ Persisted queries (or query allowlist)
☐ Query timeout
☐ Audit logging
☐ Dependency vulnerability scan
☐ Schema lint in CI
```

---

## Common Real-World Mistakes

### 1. Forgot to disable introspection
Attacker reads schema → tailors attacks.

### 2. Field-level auth only on top-level resolvers
Nested fields skip checks because parent already authorized.

**Fix:** Authorize at every field that returns sensitive data.

### 3. Allowed unbounded list
`users { ... }` returns 50M users. OOM.

### 4. Trusted client-provided ID
`updateUser(id: $id, name: $name)` — without checking that current_user can edit user $id.

### 5. Returned password hashes in responses
Schema includes a `password_hash` field. Easy to expose.

---

## TL;DR

- Introspection + GraphiQL → off in prod.
- Depth + complexity limits → mandatory.
- Field-level auth → never skip.
- Persisted queries → ideal for production.
- Rate limit per operation, not just per HTTP request.
- Sanitize errors; log internally.
- Audit all of the above in security review.

**GraphQL security ≠ REST security.** The flexibility that makes GraphQL powerful also makes it vulnerable. Defense in depth required.
