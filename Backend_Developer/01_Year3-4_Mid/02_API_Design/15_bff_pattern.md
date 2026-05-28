# Backend for Frontend (BFF) Pattern

## Why It Matters

Single backend serving Web + Mobile + Smart TV → each client gets bloated/over-fetched data. BFF = per-client backend layer optimized for that client's needs.

Senior interview: "Mobile slow, drains battery. Backend optimization?" → BFF or GraphQL.

---

## Core Concept

```
                            [Microservices]
                                   ▲
                                   |
            +----------------------+----------------------+
            |                      |                      |
        [Web BFF]            [Mobile BFF]          [Partner BFF]
            ▲                      ▲                      ▲
            |                      |                      |
        [Web App]            [Mobile App]          [External Partner]
```

Each BFF:
- Owned by client team (web team owns Web BFF)
- Aggregates calls to backend services
- Shapes response for specific client
- Implements client-specific auth, caching, transformation

---

## BFF Responsibilities

### 1. Aggregation

```python
# Web BFF — single call to load dashboard
@app.get('/dashboard')
async def dashboard(user=Depends(get_user)):
    user_info, recent_orders, recommendations, notifications = await asyncio.gather(
        user_service.get(user.id),
        order_service.list_recent(user.id, limit=10),
        recommendation_service.for_user(user.id),
        notification_service.unread(user.id),
    )

    return {
        'user': user_info,
        'orders': recent_orders,
        'recommendations': recommendations,
        'notifications': notifications,
    }


# Without BFF: web app makes 4 API calls. With BFF: 1 call.
```

### 2. Transformation (Per-Client Shape)

```python
# Mobile BFF — minimal payload
@mobile_app.get('/me')
async def mobile_me(user=Depends(get_user)):
    full_user = await user_service.get(user.id)

    # Mobile only needs subset
    return {
        'id': full_user['id'],
        'name': full_user['name'],
        'avatar_thumb': resize_image(full_user['avatar'], (50, 50)),
    }


# Web BFF — richer data
@web_app.get('/me')
async def web_me(user=Depends(get_user)):
    full_user = await user_service.get(user.id)
    settings = await user_service.get_settings(user.id)
    return {
        **full_user,
        'settings': settings,
        'avatar_full': full_user['avatar'],
    }
```

### 3. Client-Specific Caching

```python
# Mobile: aggressive caching (battery)
@mobile_app.get('/feed')
@cache(expire=300)
async def mobile_feed():
    ...


# Web: shorter TTL (freshness)
@web_app.get('/feed')
@cache(expire=30)
async def web_feed():
    ...
```

### 4. Versioning Per Client

```
Mobile v1.0 → /mobile-bff/v1/...
Mobile v2.0 → /mobile-bff/v2/...
Web (continuous) → /web-bff/...
```

Mobile needs slower deprecation (users don't auto-upgrade).

### 5. Edge Optimization

```python
# Compress responses for mobile (slow network)
@mobile_app.middleware('http')
async def compress(request, call_next):
    response = await call_next(request)
    if 'gzip' in request.headers.get('accept-encoding', ''):
        response.body = gzip.compress(response.body, compresslevel=9)
        response.headers['Content-Encoding'] = 'gzip'
    return response
```

---

## When to Use BFF

### Use BFF When

- Multiple distinct clients (web, mobile, watch, voice)
- Client needs differ significantly
- Frontend + backend teams want autonomy
- Mobile bandwidth/battery matters
- Backend microservices proliferate (10+)
- Want per-client metrics + alerts

### Skip BFF When

- Single client (overhead not worth it)
- Backend already client-shaped
- Small team (extra layer = extra complexity)
- Latency budget tight (extra hop hurts)

---

## BFF vs GraphQL

| | BFF | GraphQL |
|---|---|---|
| Pattern | Per-client backend | Client-driven query |
| Flexibility | Server controls shape | Client requests fields |
| Per-client | Multiple deployments | One endpoint, multiple shapes |
| Code | Python/Node BFF code | Resolvers |
| Caching | HTTP cache friendly | Tricky (POST) |
| Use case | When clients very different | When clients want flexibility |

**Hybrid:** GraphQL BFF — single GraphQL endpoint per client (web/mobile each have their own GraphQL gateway).

---

## Architecture

### Each BFF Layer

```
┌──────────────────────────────┐
│       Mobile BFF             │
├──────────────────────────────┤
│  - Auth middleware            │
│  - Rate limiting (mobile)     │
│  - Aggregation logic          │
│  - Response transformation    │
│  - Mobile-optimized caching   │
│  - Compression / image resize │
└──────────────────────────────┘
              ↓
[User Svc] [Order Svc] [Notify Svc]
```

### Communication

BFF → Backend services usually:
- gRPC (fast, typed) — preferred
- Internal REST (simpler)
- GraphQL Federation (Apollo)

---

## Implementation Example

### Mobile BFF (FastAPI)

```python
from fastapi import FastAPI, Depends


app = FastAPI(title='Mobile BFF')


# Auth (validates JWT)
async def get_user(authorization: str = Header(...)) -> int:
    # ... validate, return user_id
    return 1


# Aggregating call
@app.get('/v1/home')
async def mobile_home(user_id: int = Depends(get_user)):
    """One call → all data needed for home screen."""
    user, feed, balance, notifications = await asyncio.gather(
        fetch_user(user_id),
        fetch_feed(user_id, limit=20),
        fetch_balance(user_id),
        fetch_notifications(user_id, unread_only=True),
    )

    # Mobile-optimized response
    return {
        'user': {
            'name': user['name'],
            'avatar_small': resize(user['avatar_url'], 100),
        },
        'feed': [
            {
                'id': f['id'],
                'thumb': resize(f['image_url'], 320),  # smaller for mobile
                'title': f['title'][:80],              # truncated
            }
            for f in feed
        ],
        'balance': balance,
        'notifications': {
            'unread_count': len(notifications),
            'latest': notifications[:5],
        },
    }
```

### Backend Services (gRPC)

```python
async def fetch_user(user_id):
    async with grpc.aio.insecure_channel('user-svc:50051') as channel:
        stub = user_pb2_grpc.UserServiceStub(channel)
        response = await stub.GetUser(user_pb2.GetUserRequest(id=user_id))
        return MessageToDict(response)
```

### Web BFF (different shape)

```python
@web_app.get('/v1/home')
async def web_home(user_id=Depends(get_user)):
    """Web home — richer data, multiple sections."""
    # ... aggregate more data, return larger response

    return {
        'user': {...},
        'feed': {
            'items': [...],
            'has_more': True,
            'cursor': '...',
        },
        'sidebar': {
            'trending': [...],
            'suggestions': [...],
            'ads': [...],
        },
        'modals': {
            'announcement': {...},
        },
    }
```

---

## Deployment

### Independent Deployments

Each BFF deploys independently:

```
mobile-bff.yaml
web-bff.yaml
partner-bff.yaml
```

Web team deploys web-bff without coordinating with mobile team.

### Per-Region Co-location

```
US: mobile-bff-us, user-svc-us, ...
EU: mobile-bff-eu, user-svc-eu, ...
```

BFF in same region as backend services → low latency aggregation.

### Sizing

BFF = thin layer. Lower resource requirements than backend services.

```yaml
mobile-bff:
  replicas: 10
  resources:
    cpu: 250m
    memory: 256Mi

user-svc:
  replicas: 5
  resources:
    cpu: 1
    memory: 2Gi
```

---

## Anti-Patterns

### 1. BFF Becomes Mini-Backend

BFF starts owning business logic instead of just shaping. Should call backend services, not duplicate.

### 2. Shared BFF Across Clients

Defeats purpose. Each client should have own BFF (or use GraphQL).

### 3. BFF Stores State

BFF should be stateless. State in backend services or external storage.

### 4. Cross-BFF Calls

Mobile BFF calling Web BFF → coupled, confusing. BFFs call backend services only.

### 5. Backend Logic Duplicated in BFFs

Business rules in BFF + backend = sync nightmare. BFF = transformation, backend = logic.

---

## Common Pitfalls

### 1. Extra Latency

```
Client → BFF (50ms) → Backend (50ms) = 100ms
```

vs direct:
```
Client → Backend (50ms) = 50ms
```

BFF adds 1 hop. Mitigate: parallel fetches in BFF, co-locate BFF + backend, cache aggressively.

### 2. Single Point of Failure

BFF down → all clients of that type broken. Multiple replicas, health checks, graceful degradation.

### 3. Auth Implementation Drift

Each BFF implements auth → inconsistent. Centralize auth library, share across BFFs.

### 4. Backend Service Coupling

BFF aggregates 5 services → backend service change breaks BFF. Contract testing (Pact) helps.

### 5. Mobile BFF Optimized for Web

Same backend code in mobile + web BFFs. Mobile-specific (image resize, compression, smaller payload) often forgotten.

---

## Interview Q&A

**Q1:** BFF pattern problem solve karta hai?
**A:** Different clients have different data needs. Single backend = over-fetching for mobile, multiple round-trips for web, etc. BFF = per-client backend that aggregates + transforms. Owned by frontend team. Reduces round-trips, optimizes payload.

**Q2:** BFF vs GraphQL?
**A:** BFF: server-side per-client backend, aggregates microservices. GraphQL: client-driven query language, single endpoint. BFF gives server control; GraphQL gives client flexibility. Hybrid common: GraphQL per BFF (per-client GraphQL endpoint).

**Q3:** BFF latency overhead?
**A:** Extra hop adds latency. Mitigate: parallel async calls in BFF (asyncio.gather), co-locate BFF + backend services, aggressive caching for read-heavy paths, consider edge BFF (Cloudflare Workers) for global users.

**Q4:** Mobile BFF specific optimizations?
**A:** (1) Image resizing — return smaller dimensions. (2) Compression (gzip/brotli). (3) Field reduction — strip what mobile doesn't show. (4) Aggressive caching — battery savings. (5) Conditional GET for unchanged data. (6) Versioning — slow deprecation (users update slowly).

**Q5:** Auth in BFF?
**A:** BFF validates JWT/session. Issues internal tokens for backend service calls (or forwards user context via headers). Centralize auth library across BFFs to prevent drift. Backend services trust BFF (mTLS for transport).

**Q6:** BFF deploy strategy?
**A:** Independent deployments per client team. Mobile BFF deployment doesn't require coordination with web. Each BFF in its own repo (or monorepo with clear ownership). Per-region deployment for latency.

**Q7:** When BFF becomes anti-pattern?
**A:** When BFF starts owning business logic (should be in backend services). When multiple BFFs share so much code that DRY violations make merge a feature. When extra hop adds unacceptable latency. When team too small to maintain N BFFs.

**Q8:** BFF + microservices best practices?
**A:** (1) BFF only aggregates + transforms, no business logic. (2) Backend services use gRPC (fast, typed). (3) Contract tests (Pact) prevent breakage. (4) Independent deployment + monitoring. (5) Shared library for common code (auth, logging). (6) Frontend team owns + deploys BFF.

---

## Real-World Examples

### Netflix

Pioneer of BFF pattern. Different BFFs for:
- TV apps
- Mobile (iOS, Android)
- Web
- Game consoles
- Smart TVs

Each BFF optimized for that device's constraints.

### SoundCloud

Originally one monolithic backend. Split into BFFs per platform:
- Mobile BFF
- Web BFF
- Embedded BFF

Each owned by its respective frontend team.

### Spotify

GraphQL BFFs per platform — single GraphQL endpoint per client. Flexible queries within client's GraphQL schema.

---

## References

- [Pattern: Backends For Frontends — Sam Newman](https://samnewman.io/patterns/architectural/bff/)
- [SoundCloud BFF journey](https://developers.soundcloud.com/blog/bff-soundcloud-mobile)
- [Netflix BFF](https://netflixtechblog.com/embracing-the-differences-inside-the-netflix-api-redesign-15fd8b3dc49d)
- "Building Microservices" by Sam Newman
