"""
Backend for Frontend (BFF) — Production Patterns
"""

import asyncio
import gzip
from typing import Any

import httpx
from fastapi import FastAPI, Depends, Header, HTTPException, Request, Response


# ==========================================================================
# 1. MOBILE BFF (lightweight, mobile-optimized)
# ==========================================================================

mobile_app = FastAPI(title='Mobile BFF')


# Backend service URLs (gRPC or REST internal)
USER_SVC = 'http://user-svc:8000'
ORDER_SVC = 'http://order-svc:8000'
FEED_SVC = 'http://feed-svc:8000'
NOTIFY_SVC = 'http://notify-svc:8000'


async def get_user(authorization: str = Header(...)) -> dict:
    """Mobile auth — validates JWT."""
    # ... validate
    return {'id': 1, 'tenant_id': 5}


# Helper for downstream calls
_http_client = None


async def get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=5.0)
    return _http_client


async def call_service(url: str) -> dict:
    """Call internal microservice."""
    client = await get_http_client()
    try:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError:
        return {}


def resize_image_url(url: str, size: int) -> str:
    """Return CDN URL with size param (e.g., Cloudinary)."""
    if not url:
        return ''
    return f'{url}?w={size}&q=85&f=auto'


# Mobile home — single endpoint aggregating multiple services
@mobile_app.get('/v1/home')
async def mobile_home(user=Depends(get_user)):
    user_id = user['id']

    # PARALLEL fetches — critical for BFF latency
    user_info, feed, balance, notifications = await asyncio.gather(
        call_service(f'{USER_SVC}/users/{user_id}'),
        call_service(f'{FEED_SVC}/feed?user_id={user_id}&limit=20'),
        call_service(f'{USER_SVC}/users/{user_id}/balance'),
        call_service(f'{NOTIFY_SVC}/unread?user_id={user_id}'),
        return_exceptions=False,
    )

    # MOBILE-OPTIMIZED response
    return {
        'user': {
            'name': user_info.get('name'),
            'avatar': resize_image_url(user_info.get('avatar_url'), 100),
        },
        'feed': [
            {
                'id': f['id'],
                'title': f['title'][:80],   # truncated
                'thumb': resize_image_url(f.get('image_url', ''), 320),
                'created_at': f.get('created_at'),
            }
            for f in (feed.get('items', []) if isinstance(feed, dict) else feed)[:20]
        ],
        'balance': balance.get('amount', 0),
        'notifications': {
            'unread_count': notifications.get('count', 0),
            'latest': [
                {'id': n['id'], 'title': n['title'][:60]}
                for n in (notifications.get('items', [])[:5])
            ],
        },
    }


# Mobile profile — small payload
@mobile_app.get('/v1/me')
async def mobile_me(user=Depends(get_user)):
    full = await call_service(f"{USER_SVC}/users/{user['id']}")

    return {
        'id': full.get('id'),
        'name': full.get('name'),
        'avatar': resize_image_url(full.get('avatar_url', ''), 200),
        # Mobile doesn't need: full email, address, settings, etc.
    }


# Compression for mobile (slow networks)
@mobile_app.middleware('http')
async def gzip_compress(request: Request, call_next):
    response = await call_next(request)

    if 'gzip' not in request.headers.get('accept-encoding', ''):
        return response

    # Compress responses > 1KB
    if hasattr(response, 'body') and len(response.body) > 1024:
        compressed = gzip.compress(response.body, compresslevel=6)
        response.body = compressed
        response.headers['Content-Encoding'] = 'gzip'
        response.headers['Content-Length'] = str(len(compressed))

    return response


# ==========================================================================
# 2. WEB BFF (rich data, multiple sections)
# ==========================================================================

web_app = FastAPI(title='Web BFF')


@web_app.get('/v1/home')
async def web_home(user=Depends(get_user)):
    user_id = user['id']

    # Web wants more data
    user_info, feed, trending, suggestions, ads, recent_orders = await asyncio.gather(
        call_service(f'{USER_SVC}/users/{user_id}'),
        call_service(f'{FEED_SVC}/feed?user_id={user_id}&limit=50'),
        call_service(f'{FEED_SVC}/trending'),
        call_service(f'{USER_SVC}/users/{user_id}/suggestions'),
        call_service(f'{USER_SVC}/users/{user_id}/ads'),
        call_service(f'{ORDER_SVC}/orders?user_id={user_id}&limit=10'),
    )

    return {
        'user': user_info,   # full user data
        'main': {
            'feed': {
                'items': feed.get('items', []),
                'has_more': feed.get('has_more', False),
                'cursor': feed.get('cursor'),
            },
            'orders': recent_orders.get('items', []),
        },
        'sidebar': {
            'trending': trending.get('items', [])[:10],
            'suggestions': suggestions.get('items', []),
            'ads': ads.get('items', []),
        },
        'meta': {
            'feed_count': feed.get('total', 0),
            'orders_count': recent_orders.get('total', 0),
        },
    }


@web_app.get('/v1/me')
async def web_me(user=Depends(get_user)):
    user_id = user['id']

    full, settings, billing = await asyncio.gather(
        call_service(f'{USER_SVC}/users/{user_id}'),
        call_service(f'{USER_SVC}/users/{user_id}/settings'),
        call_service(f'{USER_SVC}/users/{user_id}/billing'),
    )

    return {
        **full,
        'settings': settings,
        'billing': billing,
    }


# ==========================================================================
# 3. PARTNER BFF (third-party integrations)
# ==========================================================================

partner_app = FastAPI(title='Partner BFF')


async def authenticate_partner(api_key: str = Header(..., alias='X-API-Key')) -> dict:
    """Partner auth — API key instead of JWT."""
    # validate key, return partner info
    return {'partner_id': 'partner_abc', 'scopes': ['read:orders']}


@partner_app.get('/v1/orders')
async def partner_orders(
    partner=Depends(authenticate_partner),
    customer_id: str = None,
    limit: int = 100,
):
    if 'read:orders' not in partner['scopes']:
        raise HTTPException(403)

    # Fetch + transform
    orders = await call_service(f'{ORDER_SVC}/orders?customer_id={customer_id}&limit={limit}')

    # Partner-specific format (no internal IDs leaked)
    return {
        'orders': [
            {
                'external_id': o.get('reference_id'),   # not internal id
                'amount_cents': int(o.get('amount', 0) * 100),
                'status': o.get('status'),
                'created_at': o.get('created_at'),
            }
            for o in orders.get('items', [])
        ],
    }


# ==========================================================================
# 4. GRAPHQL BFF (single endpoint, flexible queries)
# ==========================================================================

"""
import strawberry
from strawberry.fastapi import GraphQLRouter
from strawberry.dataloader import DataLoader


# Each BFF has its own GraphQL schema
@strawberry.type
class MobileUser:
    id: int
    name: str
    avatar: str   # mobile-sized

    @classmethod
    async def from_backend(cls, data):
        return cls(
            id=data['id'],
            name=data['name'],
            avatar=resize_image_url(data['avatar_url'], 100),
        )


@strawberry.type
class MobileQuery:
    @strawberry.field
    async def me(self, info) -> MobileUser:
        user_id = info.context['user']['id']
        data = await call_service(f'{USER_SVC}/users/{user_id}')
        return await MobileUser.from_backend(data)

    @strawberry.field
    async def feed(self, info, limit: int = 20) -> list[FeedItem]:
        ...


mobile_schema = strawberry.Schema(query=MobileQuery)
mobile_app.include_router(
    GraphQLRouter(mobile_schema, context_getter=lambda req: {'user': req.user}),
    prefix='/graphql',
)


# Mobile client query
'''
query {
    me { name avatar }
    feed(limit: 20) { id title thumb }
}
'''
# Single request, mobile-shaped response
"""


# ==========================================================================
# 5. GRPC TO BACKEND SERVICES (preferred for BFF → internal)
# ==========================================================================

"""
import grpc
from gen import user_pb2, user_pb2_grpc, feed_pb2, feed_pb2_grpc


# Cached gRPC stubs (reuse connections)
_user_channel = None
_user_stub = None


def get_user_stub():
    global _user_channel, _user_stub
    if _user_stub is None:
        _user_channel = grpc.aio.insecure_channel('user-svc:50051')
        _user_stub = user_pb2_grpc.UserServiceStub(_user_channel)
    return _user_stub


async def fetch_user_grpc(user_id: int) -> dict:
    stub = get_user_stub()
    response = await stub.GetUser(user_pb2.GetUserRequest(id=user_id))
    return MessageToDict(response)


# Use in BFF
@mobile_app.get('/v1/me-grpc')
async def me_grpc(user=Depends(get_user)):
    data = await fetch_user_grpc(user['id'])
    return {
        'name': data.get('name'),
        'avatar': resize_image_url(data.get('avatarUrl', ''), 100),
    }
"""


# ==========================================================================
# 6. CONDITIONAL CACHING per BFF
# ==========================================================================

from fastapi_cache import FastAPICache
from fastapi_cache.decorator import cache


# Mobile: aggressive caching (battery)
@mobile_app.get('/v1/feed')
@cache(expire=300)   # 5 min
async def mobile_feed(user=Depends(get_user)):
    return await call_service(f"{FEED_SVC}/feed?user_id={user['id']}")


# Web: short TTL (freshness matters)
@web_app.get('/v1/feed')
@cache(expire=30)
async def web_feed(user=Depends(get_user)):
    return await call_service(f"{FEED_SVC}/feed?user_id={user['id']}")


# Partner: longer TTL (rate-limited)
@partner_app.get('/v1/feed')
@cache(expire=3600)
async def partner_feed(partner=Depends(authenticate_partner)):
    return await call_service(f"{FEED_SVC}/feed/public")


# ==========================================================================
# 7. GRACEFUL DEGRADATION (one service down)
# ==========================================================================

@mobile_app.get('/v1/home-resilient')
async def home_resilient(user=Depends(get_user)):
    user_id = user['id']

    # return_exceptions=True — don't fail on one service down
    results = await asyncio.gather(
        call_service(f'{USER_SVC}/users/{user_id}'),
        call_service(f'{FEED_SVC}/feed?user_id={user_id}'),
        call_service(f'{NOTIFY_SVC}/unread?user_id={user_id}'),
        return_exceptions=True,
    )

    response = {}

    user_info = results[0]
    if not isinstance(user_info, Exception):
        response['user'] = user_info
    else:
        # Fallback
        response['user'] = {'id': user_id, 'name': 'User'}

    feed = results[1]
    if not isinstance(feed, Exception):
        response['feed'] = feed.get('items', [])
    else:
        response['feed'] = []
        response['_warnings'] = ['feed_unavailable']

    notifications = results[2]
    if not isinstance(notifications, Exception):
        response['notifications'] = notifications
    else:
        response['notifications'] = {'unread_count': 0}

    return response


# ==========================================================================
# 8. CIRCUIT BREAKER for unreliable downstream
# ==========================================================================

"""
# pip install circuitbreaker
from circuitbreaker import circuit


@circuit(failure_threshold=5, recovery_timeout=60)
async def call_unreliable_service(url):
    return await call_service(url)


# After 5 failures, circuit opens — next 60s all calls fail fast
# (not hitting downstream service while it's broken)
"""


# ==========================================================================
# 9. AUTH PROPAGATION TO BACKEND SERVICES
# ==========================================================================

async def call_backend_with_user_context(url: str, user: dict):
    """Pass user context to backend services (microservices trust BFF)."""
    client = await get_http_client()
    resp = await client.get(
        url,
        headers={
            'X-User-Id': str(user['id']),
            'X-Tenant-Id': str(user.get('tenant_id', '')),
            'X-Request-Id': str(uuid.uuid4()),
        },
    )
    return resp.json()


# Backend services trust X-User-Id from BFF (via mTLS / internal network)
# BFF is the auth boundary


# ==========================================================================
# 10. PROD DEPLOYMENT (Kubernetes)
# ==========================================================================

K8S_DEPLOYMENT = """
# Mobile BFF — thin, many replicas
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mobile-bff
spec:
  replicas: 10
  selector:
    matchLabels:
      app: mobile-bff
  template:
    metadata:
      labels:
        app: mobile-bff
    spec:
      containers:
      - name: app
        image: mobile-bff:v1.0
        ports: [{containerPort: 8000}]
        resources:
          requests: {cpu: 250m, memory: 256Mi}
          limits: {cpu: 1, memory: 512Mi}
        env:
        - name: USER_SVC_URL
          value: 'http://user-svc.default.svc.cluster.local:8000'
        - name: FEED_SVC_URL
          value: 'http://feed-svc.default.svc.cluster.local:8000'
        livenessProbe:
          httpGet: {path: /health/live, port: 8000}
        readinessProbe:
          httpGet: {path: /health/ready, port: 8000}


---
apiVersion: v1
kind: Service
metadata:
  name: mobile-bff
spec:
  type: LoadBalancer
  selector:
    app: mobile-bff
  ports:
  - port: 443
    targetPort: 8000


# Separate deployment for web-bff, partner-bff
# Backend services are ClusterIP only (BFF talks to them, not exposed)
"""


# ==========================================================================
# 11. METRICS per BFF
# ==========================================================================

"""
# Track each BFF separately to see per-client perf
from prometheus_client import Counter, Histogram


MOBILE_REQUESTS = Counter('mobile_bff_requests_total', 'Mobile BFF requests', ['route', 'status'])
MOBILE_LATENCY = Histogram('mobile_bff_duration_seconds', 'Mobile BFF latency', ['route'])

WEB_REQUESTS = Counter('web_bff_requests_total', 'Web BFF requests', ['route', 'status'])
WEB_LATENCY = Histogram('web_bff_duration_seconds', 'Web BFF latency', ['route'])

PARTNER_REQUESTS = Counter('partner_bff_requests_total', 'Partner BFF requests', ['route', 'status'])

# Backend service call latency tracked separately
BACKEND_CALL_LATENCY = Histogram(
    'bff_backend_call_duration_seconds',
    'Time per backend service call',
    ['bff', 'backend_service', 'status'],
)
"""


# ==========================================================================
# 12. CONTRACT TESTING (Pact)
# ==========================================================================

CONTRACT_TESTING_GUIDE = """
# BFF as consumer of backend service contracts
# Backend service as provider

# pip install pact-python


# Consumer test (in BFF repo)
from pact import Consumer, Provider


pact = Consumer('mobile-bff').has_pact_with(Provider('user-svc'))
pact.start()

pact.given('user 1 exists').upon_receiving(
    'a request for user 1'
).with_request(
    'get', '/users/1'
).will_respond_with(200, body={'id': 1, 'name': 'Alice'})


# When BFF tests run, Pact records expected contract
# Provider (user-svc) verifies it can deliver the contract

# This catches breakage before deploy
"""


# ==========================================================================
# 13. DECISION FRAMEWORK
# ==========================================================================

DECISION_GUIDE = """
Use BFF when:
  ✓ 2+ distinct clients (mobile, web, watch, voice)
  ✓ Client needs differ significantly
  ✓ Mobile bandwidth/battery matters
  ✓ Frontend teams want autonomy
  ✓ Backend microservices proliferate (5+)
  ✓ Per-client metrics/alerts needed

Use GraphQL instead of BFF when:
  ✓ Client wants flexibility (not just one shape)
  ✓ One client (no per-client variations)
  ✓ Team comfortable with GraphQL

Use GraphQL BFF (best of both) when:
  ✓ Multiple clients + each wants flexibility within their shape
  ✓ Strong client team

Skip BFF when:
  ✗ Single client (overhead not worth it)
  ✗ Backend already client-shaped
  ✗ Small team (1-3 engineers)
  ✗ Latency budget extremely tight
"""
