"""
API Versioning — Production Patterns
"""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel


app = FastAPI()


# ==========================================================================
# 1. URL PATH VERSIONING (most common)
# ==========================================================================

# Separate routers per version
v1_router = APIRouter(prefix='/api/v1', tags=['v1'])
v2_router = APIRouter(prefix='/api/v2', tags=['v2'])


@v1_router.get('/users/{user_id}')
def get_user_v1(user_id: int):
    """v1: single 'name' field."""
    return {
        'id': user_id,
        'name': 'Alice Smith',
        'email': 'alice@example.com',
    }


@v2_router.get('/users/{user_id}')
def get_user_v2(user_id: int):
    """v2: split name; preserves backward fields."""
    return {
        'id': user_id,
        'name': 'Alice Smith',          # kept for backward compat
        'first_name': 'Alice',           # new
        'last_name': 'Smith',            # new
        'email': 'alice@example.com',
    }


app.include_router(v1_router)
app.include_router(v2_router)


# ==========================================================================
# 2. DEPRECATION MIDDLEWARE
# ==========================================================================

DEPRECATED_VERSIONS = {
    'v1': {
        'sunset_at': datetime(2026, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
        'migration_url': 'https://docs.example.com/api-v2-migration',
        'message': 'API v1 will be removed on 2026-12-31. Migrate to v2.',
    },
}


@app.middleware('http')
async def deprecation_headers(request: Request, call_next):
    response = await call_next(request)

    for version, info in DEPRECATED_VERSIONS.items():
        if f'/api/{version}/' in request.url.path:
            now = datetime.now(timezone.utc)

            # Past sunset — return 410 Gone
            if now > info['sunset_at']:
                return JSONResponse(
                    {
                        'error': f'API {version} has been removed',
                        'migration_url': info['migration_url'],
                    },
                    status_code=410,
                )

            # Add deprecation headers
            response.headers['Deprecation'] = 'true'
            response.headers['Sunset'] = info['sunset_at'].strftime('%a, %d %b %Y %H:%M:%S GMT')
            response.headers['Link'] = f'<{info["migration_url"]}>; rel="successor-version"'
            response.headers['Warning'] = f'299 - "{info["message"]}"'

            # Track deprecated usage
            # DEPRECATED_USAGE.labels(version=version).inc()

    return response


# ==========================================================================
# 3. HEADER VERSIONING
# ==========================================================================

@app.get('/api/users/{user_id}')
async def get_user_header(
    user_id: int,
    x_api_version: str = Header('2024-06-30', alias='X-API-Version'),
):
    """Same URL, different versions via header."""
    # Validate version
    if x_api_version not in ALLOWED_VERSIONS:
        raise HTTPException(
            400,
            f'Unsupported version. Allowed: {ALLOWED_VERSIONS}',
        )

    return transform_user_for_version(
        fetch_user(user_id),
        x_api_version,
    )


# ==========================================================================
# 4. ACCEPT HEADER VERSIONING (content negotiation)
# ==========================================================================

@app.get('/api/articles/{article_id}')
async def get_article(article_id: int, accept: str = Header('application/json')):
    """Parse version from Accept header."""

    version = parse_version_from_accept(accept)

    article = fetch_article(article_id)
    return transform_article_for_version(article, version)


def parse_version_from_accept(accept_header: str) -> str:
    """
    Parse Accept like 'application/vnd.example.v2+json'.
    Returns version like '2' or default '1'.
    """
    if 'vnd.example.v' in accept_header:
        # Extract version
        try:
            v_part = accept_header.split('vnd.example.v')[1]
            version = v_part.split('+')[0]
            return version
        except (IndexError, ValueError):
            pass
    return '1'


# ==========================================================================
# 5. STRIPE-STYLE DATE VERSIONING
# ==========================================================================

# Frozen set — order matters (newest last)
ALLOWED_VERSIONS = [
    '2023-01-01',     # initial
    '2023-06-15',     # added email_verified
    '2024-01-01',     # split name → first/last
    '2024-06-30',     # added settings nested
]

DEFAULT_VERSION = '2024-06-30'


def determine_version(request: Request) -> str:
    """Customer fixed on version. Default to latest."""
    # In real app: lookup customer's account version
    # account = get_account(request.user.id)
    # return account.api_version

    # Header for ad-hoc override (testing)
    header_version = request.headers.get('X-API-Version')
    if header_version and header_version in ALLOWED_VERSIONS:
        return header_version

    return DEFAULT_VERSION


def transform_user_for_version(user: dict, version: str) -> dict:
    """Transform user response based on requested version."""

    # Start with original v1 shape
    result = {
        'id': user.get('id'),
        'name': f"{user.get('first_name', '')} {user.get('last_name', '')}".strip(),
        'email': user.get('email'),
    }

    if version >= '2023-06-15':
        result['email_verified'] = user.get('email_verified', False)

    if version >= '2024-01-01':
        result['first_name'] = user.get('first_name')
        result['last_name'] = user.get('last_name')

    if version >= '2024-06-30':
        result['settings'] = {
            'notifications': user.get('notifications_enabled', True),
            'theme': user.get('theme', 'light'),
        }

    return result


def fetch_user(user_id: int) -> dict:
    """Mock — always returns latest internal shape."""
    return {
        'id': user_id,
        'first_name': 'Alice',
        'last_name': 'Smith',
        'email': 'alice@example.com',
        'email_verified': True,
        'notifications_enabled': True,
        'theme': 'dark',
    }


@app.get('/api/v3/users/{user_id}')
async def stripe_style_endpoint(user_id: int, request: Request):
    version = determine_version(request)
    user = fetch_user(user_id)
    return transform_user_for_version(user, version)


# ==========================================================================
# 6. NAMESPACE VERSIONING (Django-style)
# ==========================================================================

"""
# Django urls.py
v1_urls = [
    path('users/', UserViewSetV1.as_view({'get': 'list'})),
]


v2_urls = [
    path('users/', UserViewSetV2.as_view({'get': 'list'})),
]


urlpatterns = [
    path('api/v1/', include((v1_urls, 'api'), namespace='v1')),
    path('api/v2/', include((v2_urls, 'api'), namespace='v2')),
]


# Reverse with namespace
reverse('v2:user-detail', kwargs={'pk': 1})
"""


# ==========================================================================
# 7. ARTICLE TRANSFORMATION EXAMPLE
# ==========================================================================

def transform_article_for_version(article: dict, version: str) -> dict:
    """Show version-aware transformations."""

    if version == '1':
        return {
            'id': article['id'],
            'title': article['title'],
            'body': article['body'],
            'author_id': article['author_id'],
        }
    elif version == '2':
        return {
            'id': article['id'],
            'title': article['title'],
            'body': article['body'],
            'author': {
                'id': article['author_id'],
                'name': article.get('author_name', ''),
            },
        }
    else:
        # Latest
        return {
            **article,
        }


def fetch_article(article_id: int) -> dict:
    return {
        'id': article_id,
        'title': 'Test',
        'body': '...',
        'author_id': 5,
        'author_name': 'Alice',
        'metadata': {'tags': ['python']},
    }


# ==========================================================================
# 8. SUNSET RESPONSE FORMAT (after removal)
# ==========================================================================

@app.api_route('/api/v0/{path:path}', methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'])
async def sunsetted_v0(path: str):
    """All v0 endpoints return 410."""
    return JSONResponse(
        {
            'error': 'sunset',
            'message': 'API v0 was sunset on 2024-06-01',
            'migration_url': 'https://docs.example.com/api-v1-migration',
            'sunset_date': '2024-06-01',
        },
        status_code=410,
        headers={
            'Sunset': 'Sun, 01 Jun 2024 00:00:00 GMT',
            'Link': '<https://docs.example.com/api-v1-migration>; rel="successor-version"',
        },
    )


# ==========================================================================
# 9. VERSION USAGE METRICS
# ==========================================================================

"""
from prometheus_client import Counter


API_VERSION_USAGE = Counter(
    'api_version_requests_total',
    'Requests per API version',
    labelnames=['version', 'endpoint'],
)


@app.middleware('http')
async def track_version_usage(request: Request, call_next):
    response = await call_next(request)

    # Extract version from URL or header
    path = request.url.path
    if path.startswith('/api/v1/'):
        version = 'v1'
    elif path.startswith('/api/v2/'):
        version = 'v2'
    elif path.startswith('/api/v3/'):
        version = request.headers.get('X-API-Version', '2024-06-30')
    else:
        version = 'unversioned'

    API_VERSION_USAGE.labels(version=version, endpoint=path).inc()
    return response


# Dashboard query:
# Top versions by usage:
#   topk(10, sum by (version) (rate(api_version_requests_total[24h])))
#
# Deprecated version usage:
#   sum by (endpoint) (rate(api_version_requests_total{version="v1"}[24h]))
"""


# ==========================================================================
# 10. OPENAPI DIFF (detect breaking changes in CI)
# ==========================================================================

OPENAPI_DIFF_CI = """
# .github/workflows/api-compatibility.yml

name: API Compatibility Check

on: [pull_request]

jobs:
  diff:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Generate current OpenAPI
        run: python scripts/generate_openapi.py > current.yaml

      - name: Get main branch OpenAPI
        run: |
          git show main:openapi.yaml > main.yaml || cp current.yaml main.yaml

      - name: Run openapi-diff
        uses: oasdiff/oasdiff-action/breaking@main
        with:
          base: main.yaml
          revision: current.yaml
          fail-on-diff: true   # fail CI if breaking changes

      - name: Comment PR
        if: failure()
        uses: actions/github-script@v6
        with:
          script: |
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: 'Breaking API changes detected. Either: (1) Make backward-compatible, (2) Bump version, or (3) Override with `breaking-change-ok` label.'
            })
"""


# ==========================================================================
# 11. CONTRACT TESTING (Pact)
# ==========================================================================

PACT_TESTING = """
# pip install pact-python


# Consumer side (BFF) — defines expectation
import pact


pact_obj = pact.Consumer('mobile-bff').has_pact_with(
    pact.Provider('user-svc'),
    host_name='localhost',
    port=1234,
)


def test_get_user():
    (
        pact_obj
        .given('user 1 exists')
        .upon_receiving('a request for user 1')
        .with_request('get', '/users/1', headers={'Accept': 'application/json'})
        .will_respond_with(
            200,
            headers={'Content-Type': 'application/json'},
            body={'id': pact.Like(1), 'name': pact.Like('Alice')},
        )
    )

    with pact_obj:
        response = httpx.get('http://localhost:1234/users/1')
        assert response.json()['id'] == 1


# Pact records expected contract → publishes to Pact Broker
# Provider (user-svc) verifies it can fulfill contracts in CI

# Before deploy:
# pact-broker can-i-deploy --pacticipant user-svc --version v2.3.0 --to-environment production
# Fails if v2.3.0 incompatible with mobile-bff in production
"""


# ==========================================================================
# 12. DECISION FRAMEWORK
# ==========================================================================

DECISION_GUIDE = """
Choose URL versioning when:
  ✓ Public API for diverse consumers
  ✓ Want clear, discoverable versions
  ✓ Cacheability matters (each version = different URL)
  ✓ Most use cases

Choose Header versioning when:
  ✓ URLs should stay stable (REST purist)
  ✓ Frontend won't expose version in URLs
  ✓ Vary header CDN config acceptable

Choose Accept header (vnd.example.v2+json) when:
  ✓ Pure REST / HATEOAS architecture
  ✓ Content type defines representation

Choose Date-based (Stripe) when:
  ✓ Long-lived public API (multi-year stability)
  ✓ Can invest in backend transformation layer
  ✓ Want customers fixed on signup version
  ✓ Mature engineering team

AVOID query param versioning unless prototyping.


Deprecation timeline:
  - Public APIs: 6-12 months minimum
  - Mobile APIs: 12-24 months (slow updates)
  - Internal APIs: weeks (coordinate releases)


Number of active versions:
  - 2 (current + previous) is ideal
  - 3+ adds maintenance burden
  - Stripe handles unlimited via transformations
"""
