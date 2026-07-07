# 08 — GraphQL Error Handling Conventions

> GraphQL's biggest REST-habit trap: there's no HTTP status code to lean on. A "failed" request often still returns 200 OK, with errors described inside the response body instead.

---

## The Core Difference from REST

```
REST:  HTTP status code IS the error signal
       404 = not found, 500 = server error, 200 = success

GraphQL: HTTP status is ALMOST ALWAYS 200, even when something failed.
         The `errors` array in the response BODY is the real signal.
```

```json
// A GraphQL response with a PARTIAL failure — HTTP status is still 200
{
  "data": {
    "user": { "name": "Ashish", "email": null },
    "posts": null
  },
  "errors": [
    {
      "message": "Cannot access email field",
      "path": ["user", "email"],
      "extensions": { "code": "FORBIDDEN" }
    },
    {
      "message": "Failed to fetch posts",
      "path": ["posts"],
      "extensions": { "code": "INTERNAL_SERVER_ERROR" }
    }
  ]
}
```

**The interview-critical point:** a client that only checks `response.status
=== 200` and assumes success will silently treat this as a good response —
GraphQL clients MUST check the `errors` array independently of HTTP status.
This is the single most common GraphQL integration bug for teams coming from REST.

---

## Partial Success — GraphQL's key semantic REST doesn't have

```
GraphQL resolves each field of the query INDEPENDENTLY. One field failing
does NOT fail the whole request — `data` can be partially populated
alongside a non-empty `errors` array, in the SAME response.

query {
  user { name }      ← succeeds
  posts { title }    ← fails (DB timeout)
}

Result: user.name IS returned, posts is null, errors array explains why
posts failed. This is CORRECT, EXPECTED GraphQL behavior — not a bug.
```

This is fundamentally different from REST, where one failing piece of data
usually means the whole endpoint returns an error response. Client code must
be written expecting **field-level partial failure**, not all-or-nothing.

---

## Strawberry (Python) — raising structured errors

```python
import strawberry
from strawberry.types import Info

class NotFoundError(Exception):
    pass

@strawberry.type
class Query:
    @strawberry.field
    def user(self, info: Info, id: strawberry.ID) -> "User":
        user = get_user(id)
        if user is None:
            # Raising inside a resolver becomes an entry in the `errors` array;
            # sibling fields in the SAME query still resolve normally
            raise NotFoundError(f"User {id} not found")
        return user
```

```python
# Custom error extensions (error codes clients can branch on programmatically,
# instead of parsing the human-readable `message` string)
from graphql import GraphQLError

def resolve_user(root, info, id):
    user = get_user(id)
    if user is None:
        raise GraphQLError(
            f"User {id} not found",
            extensions={"code": "USER_NOT_FOUND", "user_id": id},
        )
    return user
```

```python
# Formatting errors before they leave the server — hide internal details
# in production (same principle as REST's custom exception handler,
# see 28_drf_exception_handler.md)
def format_error(error: GraphQLError):
    original_error = error.original_error
    if isinstance(original_error, NotFoundError):
        return {"message": str(error), "extensions": {"code": "NOT_FOUND"}}
    # Don't leak stack traces / internal exception messages to clients
    return {"message": "Internal server error", "extensions": {"code": "INTERNAL_ERROR"}}
```

---

## Standard Error Codes (the convention worth memorizing)

| Code | Meaning |
|---|---|
| `UNAUTHENTICATED` | No/invalid auth token |
| `FORBIDDEN` | Authenticated, but lacks permission for this field/operation |
| `BAD_USER_INPUT` | Invalid arguments (equivalent to REST's 400) |
| `NOT_FOUND` | Requested entity doesn't exist |
| `INTERNAL_SERVER_ERROR` | Unhandled server-side failure |

These aren't part of the GraphQL spec itself (the spec only defines the
`errors` array shape) — `extensions.code` is a **convention** (popularized by
Apollo), not an enforced standard. Still, using consistent codes is exactly
what lets frontend clients branch on error type programmatically instead of
string-matching `message` text, which is fragile.

---

## When to fail the WHOLE request vs a partial field

```python
# Nullable field failing → partial success (most common case)
@strawberry.field
def posts(self) -> list["Post"]:
    # if this raises, `posts` becomes null, OTHER fields in the query
    # still resolve — GraphQL's default per-field error isolation
    ...

# NON-NULLABLE field failing → propagates the null up until it finds
# a nullable ancestor, potentially nulling out the ENTIRE `data` object
@strawberry.type
class Query:
    @strawberry.field
    def user(self) -> "User":          # non-null return type
        ...
```

```graphql
type User {
  name: String!    # non-null — if resolving this fails, GraphQL nulls
                    # the PARENT object (user) instead of just this field,
                    # since it can't return `null` for a `String!` field
}
```

**Interview point:** nullability in your schema design directly controls
blast radius of a single field failure — over-using `!` (non-null) makes a
single flaky field failure cascade into nulling out much larger parts of the
response than necessary. This is a real schema-design tradeoff, not just a
type-safety preference.

---

## Interview Q&A

**Q: A GraphQL API returns HTTP 200 but the request "failed" — how does the client know?**
A: Check the response body's `errors` array, independent of HTTP status —
GraphQL almost always returns 200 even on failure, unlike REST where the
status code itself signals success/failure.

**Q: What is "partial success" in GraphQL, and why doesn't REST have this concept?**
A: Each field in a GraphQL query resolves independently — one field failing
returns `null` for just that field (or its nearest nullable ancestor) plus an
entry in `errors`, while sibling fields still return their data in the same
response. REST typically has one resource per endpoint, so there's no
equivalent notion of "half the response succeeded."

**Q: How does field nullability affect error blast radius?**
A: A non-null (`!`) field that fails to resolve can't return `null` for
itself, so GraphQL nulls out its nearest nullable ancestor instead — a single
failing non-null field deep in the schema can null out a much larger part of
the response than a nullable field would. Schema designers should default to
nullable unless a field's absence is truly unacceptable to the client.

---

Related: `03_n_plus_one_dataloader.md` (DataLoader failures also flow through
this same per-field error mechanism), [28_drf_exception_handler.md](../../00_Year0-2_Junior/07_Django_DRF/28_drf_exception_handler.md)
(same "don't leak internal errors to clients" principle, REST equivalent).
