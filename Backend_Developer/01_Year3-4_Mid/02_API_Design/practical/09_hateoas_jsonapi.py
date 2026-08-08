"""
HATEOAS / JSON:API — Production Patterns
"""

from fastapi import FastAPI, Request, Query, HTTPException
from pydantic import BaseModel, Field
from typing import Any


app = FastAPI(title='HATEOAS Example')


# ==========================================================================
# 1. SIMPLE HATEOAS — Links per Resource
# ==========================================================================

class Link(BaseModel):
    href: str
    method: str = 'GET'
    title: str | None = None


class ArticleResponse(BaseModel):
    id: int
    title: str
    body: str
    status: str
    author_id: int
    links: dict[str, Link] = Field(alias='_links')


# Mock DB
articles_db = {
    1: {
        'id': 1,
        'title': 'Hello',
        'body': 'World',
        'status': 'draft',
        'author_id': 5,
    },
}


def build_article_links(article: dict, request: Request) -> dict[str, Link]:
    base = str(request.base_url).rstrip('/')
    article_id = article['id']

    links = {
        'self': Link(href=f'{base}/articles/{article_id}'),
        'author': Link(href=f'{base}/users/{article["author_id"]}'),
        'comments': Link(href=f'{base}/articles/{article_id}/comments'),
    }

    # State-dependent actions
    status = article['status']
    if status == 'draft':
        links['publish'] = Link(
            href=f'{base}/articles/{article_id}/publish',
            method='POST',
            title='Publish article',
        )
        links['delete'] = Link(
            href=f'{base}/articles/{article_id}',
            method='DELETE',
            title='Delete draft',
        )
    elif status == 'published':
        links['archive'] = Link(
            href=f'{base}/articles/{article_id}/archive',
            method='POST',
            title='Archive article',
        )
    elif status == 'archived':
        links['restore'] = Link(
            href=f'{base}/articles/{article_id}/restore',
            method='POST',
        )

    return links


@app.get('/articles/{article_id}', response_model=ArticleResponse)
def get_article(article_id: int, request: Request):
    article = articles_db.get(article_id)
    if not article:
        raise HTTPException(404)

    return ArticleResponse(
        **article,
        _links=build_article_links(article, request),
    )


# ==========================================================================
# 2. JSON:API STRUCTURE
# ==========================================================================

class JsonApiResource(BaseModel):
    type: str
    id: str
    attributes: dict[str, Any] = {}
    relationships: dict[str, Any] | None = None
    links: dict[str, str] | None = None


class JsonApiResponse(BaseModel):
    data: JsonApiResource | list[JsonApiResource]
    included: list[JsonApiResource] | None = None
    links: dict[str, str] | None = None
    meta: dict[str, Any] | None = None
    errors: list[dict] | None = None


def article_to_jsonapi(article: dict, request: Request) -> JsonApiResource:
    base = str(request.base_url).rstrip('/')
    article_id = str(article['id'])

    return JsonApiResource(
        type='articles',
        id=article_id,
        attributes={
            'title': article['title'],
            'body': article['body'],
            'status': article['status'],
        },
        relationships={
            'author': {
                'data': {'type': 'users', 'id': str(article['author_id'])},
                'links': {
                    'related': f'{base}/articles/{article_id}/author',
                },
            },
            'comments': {
                'links': {
                    'related': f'{base}/articles/{article_id}/comments',
                },
            },
        },
        links={
            'self': f'{base}/articles/{article_id}',
        },
    )


@app.get('/jsonapi/articles/{article_id}', response_model=JsonApiResponse)
def get_article_jsonapi(
    article_id: int,
    request: Request,
    include: str = Query('', description='Comma-separated: author,comments'),
    fields: dict[str, str] = None,
):
    article = articles_db.get(article_id)
    if not article:
        raise HTTPException(404)

    resource = article_to_jsonapi(article, request)
    included = []

    # Handle ?include=author
    include_list = [i.strip() for i in include.split(',') if i.strip()]
    if 'author' in include_list:
        # Fetch author (mock)
        author = {'id': article['author_id'], 'name': 'Alice', 'email': 'a@example.com'}
        included.append(JsonApiResource(
            type='users',
            id=str(author['id']),
            attributes={'name': author['name'], 'email': author['email']},
        ))

    if 'comments' in include_list:
        # Fetch comments (mock)
        for c in [{'id': 1, 'body': 'Nice!'}, {'id': 2, 'body': 'Cool'}]:
            included.append(JsonApiResource(
                type='comments',
                id=str(c['id']),
                attributes={'body': c['body']},
            ))

    return JsonApiResponse(
        data=resource,
        included=included or None,
        links={'self': str(request.url)},
    )


# ==========================================================================
# 3. JSON:API LIST WITH PAGINATION
# ==========================================================================

@app.get('/jsonapi/articles')
def list_articles_jsonapi(
    request: Request,
    page_number: int = Query(1, ge=1, alias='page[number]'),
    page_size: int = Query(20, ge=1, le=100, alias='page[size]'),
    sort: str = '-created_at',
):
    # Mock data
    total_count = 200
    items = [
        {'id': i, 'title': f'Article {i}', 'body': '...', 'status': 'published', 'author_id': 5}
        for i in range((page_number - 1) * page_size, page_number * page_size)
        if i < total_count
    ]

    base = str(request.base_url).rstrip('/')
    resources = [article_to_jsonapi(a, request) for a in items]

    total_pages = (total_count + page_size - 1) // page_size

    return JsonApiResponse(
        data=resources,
        links={
            'self': f'{base}/jsonapi/articles?page[number]={page_number}&page[size]={page_size}',
            'first': f'{base}/jsonapi/articles?page[number]=1&page[size]={page_size}',
            'last': f'{base}/jsonapi/articles?page[number]={total_pages}&page[size]={page_size}',
            'prev': (
                f'{base}/jsonapi/articles?page[number]={page_number - 1}&page[size]={page_size}'
                if page_number > 1 else None
            ),
            'next': (
                f'{base}/jsonapi/articles?page[number]={page_number + 1}&page[size]={page_size}'
                if page_number < total_pages else None
            ),
        },
        meta={
            'total-pages': total_pages,
            'total-count': total_count,
        },
    )


# ==========================================================================
# 4. JSON:API ERROR FORMAT
# ==========================================================================

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


@app.exception_handler(RequestValidationError)
async def jsonapi_validation_error(request: Request, exc: RequestValidationError):
    """Convert Pydantic errors to JSON:API format."""
    errors = []
    for e in exc.errors():
        path = '/data/attributes/' + '/'.join(str(p) for p in e['loc'][1:])
        errors.append({
            'status': '422',
            'title': 'Validation Error',
            'detail': e['msg'],
            'source': {'pointer': path},
            'code': e['type'],
        })

    return JSONResponse(
        {'errors': errors},
        status_code=422,
        media_type='application/vnd.api+json',
    )


@app.exception_handler(HTTPException)
async def jsonapi_http_error(request: Request, exc: HTTPException):
    return JSONResponse(
        {
            'errors': [{
                'status': str(exc.status_code),
                'title': exc.detail if isinstance(exc.detail, str) else 'Error',
                'detail': str(exc.detail) if not isinstance(exc.detail, str) else None,
            }],
        },
        status_code=exc.status_code,
        media_type='application/vnd.api+json',
    )


# ==========================================================================
# 5. SPARSE FIELDSETS
# ==========================================================================

@app.get('/jsonapi/v2/articles/{article_id}')
def get_article_sparse(
    article_id: int,
    request: Request,
    fields_articles: str = Query(None, alias='fields[articles]'),
    fields_users: str = Query(None, alias='fields[users]'),
):
    """Sparse fieldset: client requests only specific fields."""

    article = articles_db.get(article_id)
    if not article:
        raise HTTPException(404)

    full_attrs = {
        'title': article['title'],
        'body': article['body'],
        'status': article['status'],
    }

    # Filter attributes
    if fields_articles:
        wanted = set(fields_articles.split(','))
        full_attrs = {k: v for k, v in full_attrs.items() if k in wanted}

    return {
        'data': {
            'type': 'articles',
            'id': str(article_id),
            'attributes': full_attrs,
        },
    }


# Test: GET /jsonapi/v2/articles/1?fields[articles]=title,status
# Returns only title + status


# ==========================================================================
# 6. CREATE WITH JSON:API
# ==========================================================================

class JsonApiCreateRequest(BaseModel):
    data: dict


@app.post('/jsonapi/articles', status_code=201)
def create_article_jsonapi(payload: JsonApiCreateRequest, request: Request):
    """
    POST /jsonapi/articles
    Content-Type: application/vnd.api+json

    {
        "data": {
            "type": "articles",
            "attributes": {"title": "New", "body": "..."},
            "relationships": {
                "author": {"data": {"type": "users", "id": "5"}}
            }
        }
    }
    """
    data = payload.data

    if data.get('type') != 'articles':
        raise HTTPException(409, "Type must be 'articles'")

    # Extract attributes + relationships
    attrs = data.get('attributes', {})
    relationships = data.get('relationships', {})
    author_data = relationships.get('author', {}).get('data', {})

    new_article = {
        'id': max(articles_db.keys(), default=0) + 1,
        'title': attrs.get('title'),
        'body': attrs.get('body'),
        'status': 'draft',
        'author_id': int(author_data.get('id', 0)) if author_data else None,
    }
    articles_db[new_article['id']] = new_article

    return JsonApiResponse(data=article_to_jsonapi(new_article, request))


# ==========================================================================
# 7. CONTENT TYPE NEGOTIATION
# ==========================================================================

JSONAPI_MEDIA_TYPE = 'application/vnd.api+json'


@app.middleware('http')
async def jsonapi_content_type(request: Request, call_next):
    if request.url.path.startswith('/jsonapi'):
        # Enforce JSON:API content-type
        if request.method in {'POST', 'PUT', 'PATCH'}:
            if request.headers.get('content-type') != JSONAPI_MEDIA_TYPE:
                return JSONResponse(
                    {'errors': [{'title': 'Unsupported Media Type'}]},
                    status_code=415,
                )

    response = await call_next(request)

    if request.url.path.startswith('/jsonapi'):
        response.headers['Content-Type'] = JSONAPI_MEDIA_TYPE
    return response


# ==========================================================================
# 8. HAL (alternative to JSON:API)
# ==========================================================================

class HALResource(BaseModel):
    """HAL: simpler than JSON:API."""

    # All attributes inline
    # Plus _links and optional _embedded


def article_to_hal(article: dict, request: Request):
    base = str(request.base_url).rstrip('/')
    return {
        **{k: v for k, v in article.items() if k not in {'author_id'}},
        '_links': {
            'self': {'href': f'{base}/hal/articles/{article["id"]}'},
            'author': {'href': f'{base}/hal/users/{article["author_id"]}'},
        },
    }


@app.get('/hal/articles/{article_id}')
def get_article_hal(article_id: int, request: Request, embed: bool = False):
    article = articles_db.get(article_id)
    if not article:
        raise HTTPException(404)

    response = article_to_hal(article, request)

    if embed:
        # _embedded — inline related
        response['_embedded'] = {
            'author': {
                'id': article['author_id'],
                'name': 'Alice',
                'email': 'a@example.com',
                '_links': {
                    'self': {'href': f'{request.base_url}users/{article["author_id"]}'},
                },
            },
        }

    return response


# ==========================================================================
# 9. DJANGO-REST-FRAMEWORK-JSON-API EXAMPLE
# ==========================================================================

"""
# pip install djangorestframework-jsonapi

# settings.py
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework_json_api.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework_json_api.parsers.JSONParser',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'rest_framework_json_api.filters.QueryParameterValidationFilter',
        'rest_framework_json_api.filters.OrderingFilter',
        'rest_framework_json_api.django_filters.DjangoFilterBackend',
    ],
}


# Serializer
from rest_framework_json_api import serializers


class ArticleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Article
        fields = ['id', 'title', 'body', 'status', 'author']

    # Define resource type
    class JSONAPIMeta:
        resource_name = 'articles'


# Auto-generates JSON:API responses
"""


# ==========================================================================
# 10. DECISION FRAMEWORK
# ==========================================================================

DECISION_GUIDE = """
Use HATEOAS (Level 3) when:
  ✓ Workflow-heavy API (orders, approvals with state transitions)
  ✓ Internal API where discoverability matters
  ✓ State machine resources (status determines available actions)
  ✓ Want loose coupling between client and server URLs

Skip HATEOAS when:
  ✗ Simple CRUD APIs
  ✗ Public API (most clients hardcode URLs)
  ✗ High-traffic (verbose payload = bandwidth cost)
  ✗ Tight coupling acceptable (single team owns both)


Use JSON:API when:
  ✓ Need standardized REST format
  ✓ Multiple clients with different needs (sparse fieldsets)
  ✓ Ember.js / similar frameworks with JSON:API support
  ✓ Want includes/relationships/pagination spec done for you

Skip JSON:API when:
  ✗ Simple API (overhead exceeds benefit)
  ✗ Custom shape required by frontend
  ✗ GraphQL is option (likely better fit)


HAL when:
  ✓ Want minimal HATEOAS without full JSON:API
  ✓ Embedded resources useful (avoid N+1)
"""


# ==========================================================================
# RUNNABLE LAB — Pagination _links (self/first/last/prev/next), Docker-free
# ==========================================================================
"""
LAB OBJECTIVE: Section 3 (list_articles_jsonapi) builds pagination links
inline, straight in the endpoint body. This lab pulls that exact logic out
into a standalone, testable function — no FastAPI Request, no DB — so you
can verify the links actually point at the right page, every edge included
(first page has no prev, last page has no next).

TASK:
  1. TODO: `build_pagination_links()` — self/first/last always present;
     prev/next are None exactly when there's no such page.
  2. Run: python3 09_hateoas_jsonapi.py
"""


def build_pagination_links(base: str, path: str, page_number: int, page_size: int, total_count: int) -> dict:
    """Same link shape Section 3's list_articles_jsonapi returns inline."""
    total_pages = (total_count + page_size - 1) // page_size

    def url(p: int) -> str:
        return f'{base}{path}?page[number]={p}&page[size]={page_size}'

    # ─────────────────────────────────────────────────────
    # TODO: self/first/last hamesha hote hain. prev/next sirf tab jab wo
    #   range me ho:
    #     prev = url(page_number - 1) if page_number > 1 else None
    #     next = url(page_number + 1) if page_number < total_pages else None
    #   Hint: Section 3 (list_articles_jsonapi) me yehi pattern already hai —
    #   yahan usko ek standalone function me likhna hai.
    #
    # WRONG placeholder below: prev/next both just point at the current
    # page (self) — client would "page forward" and get the same page
    # forever, and never know when to stop showing a "next" button.
    return {
        'self': url(page_number),
        'first': url(1),
        'last': url(total_pages),
        'prev': url(page_number - 1) if page_number > 1 else None,
        'next': url(page_number + 1) if page_number < total_pages else None,
    }
    # ─────────────────────────────────────────────────────


def main() -> None:
    base, path = 'https://api.example.com', '/jsonapi/articles'
    total_count, page_size = 47, 20   # → 3 pages (20, 20, 7)

    print("\n[setup] total_count=47, page_size=20 → 3 pages")

    pages = {}
    for page in (1, 2, 3):
        links = build_pagination_links(base, path, page, page_size, total_count)
        pages[page] = links
        print(f"\n  page {page}: {links}")

    print("\n" + "─" * 55)
    page1_ok = pages[1]['prev'] is None and 'page[number]=2' in (pages[1]['next'] or '')
    page2_ok = ('page[number]=1' in (pages[2]['prev'] or '')
                and 'page[number]=3' in (pages[2]['next'] or ''))
    page3_ok = pages[3]['next'] is None and 'page[number]=2' in (pages[3]['prev'] or '')
    self_ok = all(f'page[number]={p}' in pages[p]['self'] for p in (1, 2, 3))
    first_last_ok = all(
        'page[number]=1' in pages[p]['first'] and 'page[number]=3' in pages[p]['last']
        for p in (1, 2, 3)
    )

    if page1_ok and page2_ok and page3_ok and self_ok and first_last_ok:
        print("✅ PASS — self/first/last always correct; prev=None on page 1, "
              "next=None on last page, prev/next point to the right adjacent page")
    else:
        print("❌ FAIL — pagination links galat hain:")
        if not page1_ok:
            print(f"   page 1: prev should be None, next should point to page 2. Got: {pages[1]}")
        if not page2_ok:
            print(f"   page 2: prev→page1, next→page3 expected. Got: {pages[2]}")
        if not page3_ok:
            print(f"   page 3 (last): next should be None, prev should point to page 2. Got: {pages[3]}")
        print("   TODO block bharo — prev/next hardcoded url(page_number) (self) return kar rahe.")

    print("""
SOCH:
  1. prev=None kyu return karte hain (kisi bhi URL ki jagah)? Client is
     field ko kaise use karega (if links.prev: show button, else hide)?
  2. self link me current query params hone chahiye (page[size] bhi) —
     agar client ne page[size]=5 bheja tha to self me bhi 5 hona chahiye,
     hardcoded 20 nahi. Is function me yeh sahi hai?
  3. HATEOAS ka poora point: client ko URL construct NAHI karna padta,
     bas link follow karta hai. Agar backend pagination scheme badal de
     (offset → cursor) to client code todhna padega agar usne hardcoded
     URLs banaye the?
""")


if __name__ == "__main__":
    main()
