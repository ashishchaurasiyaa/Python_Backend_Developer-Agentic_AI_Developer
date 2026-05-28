# API Versioning Strategies Deep

## Why It Matters

Public APIs evolve. Breaking changes harm users. Strategy = balance flexibility (ship new features) with stability (clients don't break).

Senior interview: "How does Stripe handle API evolution without breaking 10k integrations?" → date-based versioning per customer.

---

## Versioning Strategies

### 1. URL Path Versioning

```
GET /api/v1/users/123
GET /api/v2/users/123
```

**Pros:** Discoverable, explicit, easy to route. Logs show version. CDN-cacheable per version.
**Cons:** URL changes break links/bookmarks. Multiple versions = code duplication.

**Used by:** Most public APIs (GitHub v3, Twitter v2, Twilio).

### 2. Header Versioning

```http
GET /api/users/123
Accept: application/json; version=2
# OR
X-API-Version: 2
```

**Pros:** URLs stay stable. Cleaner.
**Cons:** Hidden in headers (harder to debug). Less discoverable. Caching trickier (Vary header needed).

**Used by:** Some Microsoft APIs.

### 3. Accept Header (Content Negotiation)

```http
GET /api/users/123
Accept: application/vnd.example.v2+json
```

**Pros:** "Pure REST" — content type defines version.
**Cons:** Verbose, complex media types, browser-unfriendly.

**Used by:** GitHub historically (`application/vnd.github.v3+json`).

### 4. Query Parameter

```
GET /api/users/123?version=2
```

**Pros:** Easy to test.
**Cons:** Conflates resource selection with version. Mixed with filters confusing.

**Used by:** Rarely (anti-pattern usually).

### 5. Date-Based (Stripe Model)

```http
GET /api/users/123
Stripe-Version: 2024-06-30
```

Customer fixed on date at signup. Server interprets request based on their version. New versions opt-in.

**Pros:** Clients never break without explicit upgrade. Minor changes don't bump version.
**Cons:** Server complexity (handle all historical versions).

**Used by:** Stripe (gold standard for evolving APIs).

### 6. Schema-In-Payload Versioning

```json
POST /api/events
{
    "schema_version": "2.0",
    "event_type": "purchase",
    "data": {...}
}
```

**Pros:** Self-describing. Easy schema migration.
**Cons:** Mixed with data. Cumbersome.

**Used by:** Event-driven APIs (webhooks, message queues).

---

## Compatibility Rules

### Backward-Compatible (Non-Breaking)

- Add new fields (optional)
- Add new endpoints
- Add new optional query params
- Loosen validation (accept more)
- Add new error codes (clients ignore unknown)

### Backward-Incompatible (Breaking)

- Remove field
- Rename field
- Change field type
- Change validation (now stricter)
- Change required fields
- Change response shape
- Change error meanings
- Change HTTP method semantics

### Trick: "Additive Forever"

Stripe's secret: **never rename/remove**, only **add**. Old behavior preserved indefinitely. New behavior opt-in via version.

```
v1: { name: "Alice" }
v2: { name: "Alice", first_name: "Alice", last_name: "" }
   (added first_name + last_name, kept name)
```

Old clients still get `name`. New clients use `first_name`/`last_name`.

---

## Deprecation Lifecycle

```
Phase 1: ANNOUNCE
  - Blog post / email to users
  - Mark deprecated in docs
  - Add Deprecation header on responses
  - Set Sunset date 6-12 months out

Phase 2: WARN
  - Per-request deprecation warnings
  - Monitor v1 traffic
  - Reach out to top users

Phase 3: SUNSET
  - At sunset date, return 410 Gone
  - Document migration path
  - Provide tools/scripts

Phase 4: REMOVE
  - Remove v1 code from codebase
  - Clean up DB schemas
```

### Deprecation Headers (RFC 9745, RFC 8594)

```http
HTTP/1.1 200 OK
Deprecation: @1709125200          ; unix timestamp when deprecated
Sunset: Sat, 31 Dec 2026 23:59:59 GMT
Link: <https://docs.example.com/api-v2-migration>; rel="successor-version"
Warning: 299 - "API v1 deprecated, will be removed 2026-12-31"
```

---

## Versioning Per Resource vs Whole API

### Whole API Version

```
/v1/users
/v1/orders
/v2/users
/v2/orders
```

All resources move together. Simpler routing.

### Per-Resource Version

```
/users/v3/123
/orders/v1/123
```

Each resource evolves independently. Complex routing.

Most teams: whole API version (simpler).

---

## Versioning Internal vs External

### External (Public)

Strict versioning, long deprecation (12+ months). Customers depend on stability.

### Internal (Microservices)

Looser. Coordinate releases. Often direct breaking changes with team alignment.

For inter-service comms: contract testing (Pact) catches breakage in CI.

---

## Implementation: FastAPI URL Versioning

```python
from fastapi import FastAPI, APIRouter


app = FastAPI()

v1_router = APIRouter(prefix='/api/v1')
v2_router = APIRouter(prefix='/api/v2')


@v1_router.get('/users/{user_id}')
def get_user_v1(user_id: int):
    return {'id': user_id, 'name': 'Alice'}


@v2_router.get('/users/{user_id}')
def get_user_v2(user_id: int):
    # New shape: split name
    return {
        'id': user_id,
        'first_name': 'Alice',
        'last_name': 'Smith',
    }


app.include_router(v1_router)
app.include_router(v2_router)
```

### Deprecation Middleware

```python
from datetime import datetime


DEPRECATED_VERSIONS = {
    'v1': datetime(2026, 12, 31, 23, 59, 59),
}


@app.middleware('http')
async def deprecation_warning(request: Request, call_next):
    response = await call_next(request)

    for version, sunset_at in DEPRECATED_VERSIONS.items():
        if f'/api/{version}/' in request.url.path:
            response.headers['Deprecation'] = 'true'
            response.headers['Sunset'] = sunset_at.strftime('%a, %d %b %Y %H:%M:%S GMT')
            response.headers['Link'] = '<https://docs.example.com/migration>; rel="successor-version"'
            response.headers['Warning'] = f'299 - "API {version} deprecated, will be removed {sunset_at.date()}"'

            # If past sunset
            if datetime.utcnow() > sunset_at:
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    {'error': f'API {version} has been removed', 'migration_url': 'https://docs.example.com/migration'},
                    status_code=410,
                    headers=dict(response.headers),
                )

    return response
```

## Stripe-Style Date Versioning

```python
ALLOWED_VERSIONS = [
    '2023-01-01',
    '2023-06-15',
    '2024-01-01',
    '2024-06-30',
]

DEFAULT_VERSION = '2024-06-30'


def get_api_version(request: Request) -> str:
    version = request.headers.get('X-API-Version', DEFAULT_VERSION)
    if version not in ALLOWED_VERSIONS:
        # Either reject or fall back to default
        return DEFAULT_VERSION
    return version


@app.get('/api/users/{user_id}')
async def get_user(user_id: int, request: Request):
    version = get_api_version(request)
    user = await fetch_user(user_id)

    # Transform based on version
    if version >= '2024-01-01':
        return {
            'id': user.id,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
        }
    elif version >= '2023-06-15':
        return {
            'id': user.id,
            'name': f'{user.first_name} {user.last_name}',
            'email': user.email,
        }
    else:
        # Original v1
        return {
            'id': user.id,
            'name': user.first_name,   # initial shape
        }
```

---

## Schema Migration Tools

### OpenAPI Diff

```bash
# Compare two OpenAPI specs
openapi-diff old-spec.yaml new-spec.yaml

# Detects breaking changes
# Useful in CI to prevent accidental breakage
```

### Contract Tests

```python
# Pact CI step
pact-broker can-i-deploy --pacticipant mobile-bff --version 1.2.3 --to-environment production
# Fails if BFF v1.2.3 incompatible with services in prod
```

---

## Common Pitfalls

### 1. Versioning Without Strategy

Adding `v2/` reactively for every change → 20 versions in 2 years. Plan version cadence (max 2 active).

### 2. Breaking Changes Without Bump

Changing field type in v1 → existing clients break. Always version on breaking change.

### 3. No Deprecation Window

Removing v1 with 1 month notice → angry customers. Industry minimum 6 months for public APIs.

### 4. Database-Coupled Versions

Schema changes break v1 because v1 reads/writes DB directly. Decouple via service layer → transform per version.

### 5. Version in Query Param

`?version=2` mixed with filters confusing + cacheability suffers.

### 6. Forgetting Mobile Updates

Mobile users update slowly. Sunset v1 used by 5% mobile users = 5% locked out. Consider longer mobile-specific lifecycles.

### 7. No Migration Guide

Tell users "v2 available!" without explaining changes. Provide diff doc, examples, automated migration tools where possible.

### 8. Internal Version Drift

Microservices each have own version. Coordinating change across 10 services = nightmare. Use API gateway to abstract.

---

## Interview Q&A

**Q1:** Versioning strategies kya hain?
**A:** Five common: (1) URL path (`/v1/`) — most popular. (2) Header (`X-API-Version`) — cleaner URLs. (3) Accept header (`application/vnd.example.v2+json`) — REST-pure. (4) Query param (`?version=1`) — anti-pattern usually. (5) Date-based per customer (Stripe).

**Q2:** Stripe versioning model explain karo.
**A:** Each customer fixed on API version at signup (date string like `2024-06-30`). Server handles all historical versions. New customers default to latest. Existing customers opt-in upgrade. Backend has version-specific transformers. Pros: never break clients. Cons: complex backend.

**Q3:** Backward-compatible vs breaking changes?
**A:** Compatible: add field, add endpoint, loosen validation, add error codes. Breaking: remove field, rename, change type, change required-ness, change response shape, change HTTP method semantics. Stripe pattern: NEVER rename/remove, only ADD.

**Q4:** Deprecation lifecycle?
**A:** (1) Announce — blog, email, docs. (2) Add Deprecation + Sunset headers. (3) Warn period (6-12 months for public). (4) Sunset date — return 410 Gone. (5) Remove code. Track usage during deprecation; reach out to heavy users individually.

**Q5:** Mobile API versioning concerns?
**A:** Users update slowly. Mobile-specific longer lifecycle (12-24 months). Force update mechanism (`426 Upgrade Required`). In-app warnings before sunset. Backwards compat for at least 2-3 major mobile releases.

**Q6:** Microservices versioning?
**A:** Internal looser than external. Coordinate releases via service mesh. Contract testing (Pact) catches breakage in CI before deploy. API gateway can translate v1 → v2 transparently. Avoid versioning per-service — coordinate within service group.

**Q7:** When v1 → v2?
**A:** Breaking changes accumulate justifying version bump. Or major rewrite/new architecture. Don't bump for single small change (additive instead). Aim for 12-24 months between major versions. Stripe rarely bumps major (uses date versions).

**Q8:** Versioning + cache?
**A:** URL versioning naturally cacheable (different URLs = different cache keys). Header versioning needs `Vary: X-API-Version` for correct CDN behavior. Date versioning per customer can't be CDN-cached without persisted-query-like mechanism.

---

## Real-World Examples

### Stripe

Date-based versioning. Customer fixed on version at signup. Backend handles all historical. New customers default to latest. Customer can request upgrade via dashboard.

### GitHub

URL versioning. v3 = REST (mature). v4 = GraphQL (new). Both active. Deprecation handled with long warning + transition guides.

### Twitter (now X)

Multiple breaking versions (v1, v1.1, v2). Each major version 5+ years lifecycle. Sunset old versions painful but eventual.

### Twilio

URL versioning (`/2010-04-01/`). Each major version date-prefixed. Stable for years.

---

## References

- [Stripe API versioning](https://stripe.com/blog/api-versioning)
- [API versioning best practices (Microsoft)](https://github.com/microsoft/api-guidelines/blob/vNext/Guidelines.md#versioning)
- [RFC 9745 Deprecation HTTP Header](https://datatracker.ietf.org/doc/html/rfc9745)
- [RFC 8594 Sunset HTTP Header](https://datatracker.ietf.org/doc/html/rfc8594)
- [Apigee guide to API versioning](https://cloud.google.com/apigee/api-management)
