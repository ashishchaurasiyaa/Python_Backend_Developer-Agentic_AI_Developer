# HATEOAS / JSON:API / Hypermedia

## Why It Matters

REST Maturity Model (Richardson):
- **Level 0:** RPC over HTTP (one URL, all methods POST)
- **Level 1:** Resources (multiple URLs)
- **Level 2:** HTTP verbs (GET, POST, etc.) — most APIs stop here
- **Level 3:** HATEOAS — responses include hyperlinks to navigate

HATEOAS allows API discovery without out-of-band docs. JSON:API spec standardizes REST structure.

Senior interview: "Discoverable API design?" → HATEOAS links + JSON:API or HAL format.

---

## HATEOAS Basics

### Plain REST (Level 2)

```json
{
    "id": 1,
    "title": "Article",
    "author_id": 5,
    "status": "draft"
}
```

Client must know:
- How to publish (POST `/articles/1/publish`?)
- How to fetch author (`/users/5`?)
- All actions hardcoded in client.

### HATEOAS (Level 3)

```json
{
    "id": 1,
    "title": "Article",
    "status": "draft",
    "_links": {
        "self": { "href": "/articles/1" },
        "author": { "href": "/users/5" },
        "publish": {
            "href": "/articles/1/publish",
            "method": "POST"
        },
        "archive": {
            "href": "/articles/1/archive",
            "method": "POST"
        }
    }
}
```

Server tells client what's possible.

---

## HAL (Hypertext Application Language)

Simple format for HATEOAS:

```json
{
    "id": 1,
    "title": "Article",
    "_links": {
        "self": { "href": "/articles/1" },
        "author": { "href": "/users/5" }
    },
    "_embedded": {
        "comments": [
            {
                "id": 1,
                "body": "...",
                "_links": { "self": { "href": "/comments/1" } }
            }
        ]
    }
}
```

`_embedded` = include related resources inline (saves N+1 client requests).

---

## JSON:API Specification

Structured REST format. Stricter than HAL.

### Standard Response

```json
{
    "data": {
        "type": "articles",
        "id": "1",
        "attributes": {
            "title": "Article",
            "body": "...",
            "created-at": "2026-01-15T10:00:00Z"
        },
        "relationships": {
            "author": {
                "data": { "type": "users", "id": "5" },
                "links": {
                    "related": "/articles/1/author"
                }
            },
            "comments": {
                "data": [
                    { "type": "comments", "id": "10" },
                    { "type": "comments", "id": "11" }
                ],
                "links": {
                    "related": "/articles/1/comments"
                }
            }
        },
        "links": {
            "self": "/articles/1"
        }
    },
    "included": [
        {
            "type": "users",
            "id": "5",
            "attributes": { "name": "Alice", "email": "a@example.com" }
        },
        {
            "type": "comments",
            "id": "10",
            "attributes": { "body": "Nice article" }
        }
    ],
    "links": {
        "self": "/articles/1",
        "next": "/articles/2"
    }
}
```

### Sparse Fieldsets

Request specific fields only:

```
GET /articles/1?fields[articles]=title,status
```

```json
{
    "data": {
        "type": "articles",
        "id": "1",
        "attributes": {
            "title": "Article",
            "status": "published"
        }
    }
}
```

### Include Related (avoid N+1)

```
GET /articles/1?include=author,comments
```

Server returns related resources in `included`.

### Pagination

```json
{
    "data": [...],
    "links": {
        "first": "/articles?page[number]=1",
        "prev": "/articles?page[number]=4",
        "self": "/articles?page[number]=5",
        "next": "/articles?page[number]=6",
        "last": "/articles?page[number]=20"
    },
    "meta": {
        "total-pages": 20,
        "total-count": 200
    }
}
```

### Errors

```json
{
    "errors": [
        {
            "status": "422",
            "source": { "pointer": "/data/attributes/email" },
            "title": "Invalid Attribute",
            "detail": "Email must be a valid format."
        }
    ]
}
```

### CRUD

```
POST /articles
Content-Type: application/vnd.api+json

{
    "data": {
        "type": "articles",
        "attributes": {
            "title": "New",
            "body": "..."
        },
        "relationships": {
            "author": {
                "data": { "type": "users", "id": "5" }
            }
        }
    }
}
```

---

## Trade-offs

### HATEOAS Pros

- **Discoverability** — clients explore without docs
- **Looser coupling** — client doesn't hardcode URLs
- **State machine** — server controls available actions per state
- **Versioning easier** — link changes hidden from client

### HATEOAS Cons

- **Verbose responses** — more bytes per request
- **Client complexity** — must parse links + follow them
- **Most clients hardcode URLs anyway** — benefits unused
- **Caching harder** — links not stable

### When to Use

**Yes:**
- Internal APIs with workflow state machines
- HAL/JSON:API for standardized REST
- Mobile apps where reducing requests matters (_embedded)

**No:**
- Simple CRUD with known client (overhead not worth it)
- Public APIs with diverse clients (most won't follow links)
- High-traffic APIs (verbose payload = bandwidth cost)

---

## Implementation (FastAPI)

### Simple HATEOAS

```python
from fastapi import FastAPI, Request
from pydantic import BaseModel


class Link(BaseModel):
    href: str
    method: str = 'GET'


class ArticleResponse(BaseModel):
    id: int
    title: str
    status: str
    links: dict[str, Link]


@app.get('/articles/{article_id}')
def get_article(article_id: int, request: Request):
    article = db.get_article(article_id)
    base = str(request.base_url).rstrip('/')

    links = {
        'self': Link(href=f'{base}/articles/{article_id}'),
        'author': Link(href=f'{base}/users/{article.author_id}'),
    }

    if article.status == 'draft':
        links['publish'] = Link(
            href=f'{base}/articles/{article_id}/publish',
            method='POST',
        )
    elif article.status == 'published':
        links['archive'] = Link(
            href=f'{base}/articles/{article_id}/archive',
            method='POST',
        )

    return ArticleResponse(
        id=article.id,
        title=article.title,
        status=article.status,
        links=links,
    )
```

### JSON:API Helper

```python
def jsonapi_resource(obj, resource_type, request, included=None):
    base = str(request.base_url).rstrip('/')
    return {
        'data': {
            'type': resource_type,
            'id': str(obj.id),
            'attributes': obj.attributes_dict(),
            'relationships': obj.relationships_dict(),
            'links': {'self': f'{base}/{resource_type}/{obj.id}'},
        },
        'included': included or [],
        'links': {
            'self': str(request.url),
        },
    }


@app.get('/articles/{article_id}')
def get_article(article_id, request: Request, include: str = ''):
    article = db.get_article(article_id)
    included = []

    if 'author' in include.split(','):
        included.append({
            'type': 'users',
            'id': str(article.author_id),
            'attributes': {
                'name': article.author.name,
                'email': article.author.email,
            },
        })

    return jsonapi_resource(article, 'articles', request, included)
```

### Libraries

- `pyjsonapi` — Python JSON:API toolkit
- `flask-rest-jsonapi` — Flask integration
- `django-rest-framework-json-api` — DRF JSON:API renderer

---

## REST Maturity Decision Framework

| Need | Level |
|---|---|
| RPC over HTTP | 0 |
| Resource-based URLs | 1 |
| HTTP verbs + status codes | 2 (most APIs) |
| Hypermedia controls | 3 (specialized) |

Most teams aim for L2 (sufficient for most apps). L3 valuable for:
- Workflow-heavy APIs (orders, approvals)
- Internal APIs where discoverability matters
- API mesh / Gateway routing

---

## Common Pitfalls

### 1. Adding Links Nobody Follows

Clients hardcode URLs anyway → links wasted bytes. Survey actual clients first.

### 2. JSON:API Boilerplate

Strict spec = lots of wrapping. For small APIs, overhead exceeds benefit. Use library.

### 3. Inconsistent Link Conventions

Some endpoints have `_links`, some `links`, some `_meta`. Standardize across API.

### 4. Embedded Doc Explosion

```json
{
    "_embedded": {
        "comments": [
            {
                "_embedded": {
                    "author": {
                        "_embedded": { "posts": [...] }
                    }
                }
            }
        ]
    }
}
```

Deep nesting = huge payload. Limit depth + use `include` query param.

### 5. Versioning Inside HATEOAS

`/v1/articles/1` links to `/v1/users/5`. When v2 launches, all stale links. Use version-neutral links + content negotiation.

### 6. Caching Broken by Links

If links include user-specific tokens, response can't be CDN-cached. Use opaque resource identifiers.

---

## Interview Q&A

**Q1:** HATEOAS practically use hota hai?
**A:** Less than spec promises. Public APIs (GitHub, Stripe, Twitter): mostly L2 with limited HATEOAS (pagination links). Internal/workflow APIs: more value (state machines). Worth implementing when: workflow-heavy, multi-state resources, or discoverability matters more than bandwidth.

**Q2:** JSON:API vs HAL?
**A:** JSON:API: strict spec, includes relationships, sparse fieldsets, pagination, errors format. Library ecosystem. HAL: simpler, just adds `_links` + `_embedded`. Less standardized. Choose JSON:API for complex APIs needing standards. HAL for lightweight HATEOAS.

**Q3:** Sparse fieldsets benefits?
**A:** Client requests `?fields[articles]=title,id` → server sends only those. Reduces payload size, bandwidth costs, parse time. Mobile-friendly. Without: send everything, client filters. JSON:API standardizes this.

**Q4:** Include vs embedded?
**A:** JSON:API `?include=author` → server adds related in top-level `included` array (deduplicated). HAL `_embedded` → inline nested. Include cleaner for deduplication (same author for many articles loaded once). Embedded simpler for one-off.

**Q5:** Versioning HATEOAS?
**A:** Two approaches: (1) URLs version-neutral (`/articles/1` resolves based on Accept header); links don't change. (2) Each version has own URLs; clients follow links within version. Approach 1 cleaner but requires content negotiation discipline.

**Q6:** REST L3 vs GraphQL?
**A:** Both solve "client specifies what they need". GraphQL: explicit query language, single endpoint, strong types. L3 REST: HATEOAS links, sparse fieldsets, includes. GraphQL more mature ecosystem; HATEOAS REST simpler for partial adoption. Use GraphQL for new builds needing flexibility; HATEOAS for incremental.

**Q7:** Performance impact of HATEOAS?
**A:** Larger payloads (links add 10-30% size). Server overhead to build links. Caching trickier (some links per-user). For high-traffic public APIs, weigh vs simpler L2. Use gzip; modern HTTP/2 reduces verbosity cost.

**Q8:** Self-documenting API via HATEOAS?
**A:** In theory yes; in practice clients need OpenAPI docs anyway. HATEOAS helps with discovery but doesn't replace docs. Combine: OpenAPI for static docs, HATEOAS for runtime navigation, content type for format discovery.

---

## Real-World Examples

### GitHub API (Partial HATEOAS)

```json
{
    "id": 1,
    "url": "https://api.github.com/repos/octocat/Hello-World",
    "html_url": "https://github.com/octocat/Hello-World",
    "commits_url": "https://api.github.com/repos/octocat/Hello-World/commits{/sha}",
    "compare_url": "...",
    "...": "many _url fields"
}
```

GitHub uses links extensively. Client SDK navigates via URLs from server.

### Stripe (Minimal HATEOAS)

Stripe API: L2 mostly. Pagination only uses HATEOAS (cursor links). Otherwise hardcoded URLs in SDKs. Pragmatic — fast adoption matters more.

### JSON:API Implementations

- Drupal 8+ API uses JSON:API
- Some Ember apps default to JSON:API
- ember-data has built-in JSON:API adapter

---

## References

- [JSON:API specification](https://jsonapi.org/)
- [HAL specification](https://stateless.co/hal_specification.html)
- [Richardson REST Maturity Model](https://martinfowler.com/articles/richardsonMaturityModel.html)
- [GitHub API design](https://docs.github.com/en/rest)
- [Mike Amundsen's "RESTful Web APIs" book](https://www.oreilly.com/library/view/restful-web-apis/9781449358063/)
