"""
Conditional Requests — ETag, If-Match, If-Modified-Since
"""

import hashlib
import json
from datetime import datetime, timezone
from email.utils import format_datetime, parsedate_to_datetime

from fastapi import FastAPI, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel


app = FastAPI()


# Mock data
articles_db = {
    1: {
        'id': 1,
        'title': 'Hello',
        'body': 'World',
        'version': 5,
        'updated_at': datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
    },
}


# ==========================================================================
# 1. ETAG GENERATION
# ==========================================================================

def make_etag(article: dict) -> str:
    """Quick ETag based on version + timestamp."""
    return f'"{article["version"]}-{int(article["updated_at"].timestamp())}"'


def make_etag_content_hash(content: str | bytes) -> str:
    """Content-based ETag (more accurate but slower)."""
    if isinstance(content, str):
        content = content.encode()
    return f'"{hashlib.md5(content).hexdigest()}"'


def make_weak_etag(article: dict) -> str:
    """Weak ETag for semantic equivalence (whitespace-insensitive)."""
    return f'W/"{article["version"]}-{int(article["updated_at"].timestamp())}"'


# ==========================================================================
# 2. GET WITH ETAG + LAST-MODIFIED
# ==========================================================================

@app.get('/articles/{article_id}')
async def get_article(article_id: int, request: Request, response: Response):
    article = articles_db.get(article_id)
    if not article:
        raise HTTPException(404)

    etag = make_etag(article)
    last_modified_dt = article['updated_at']

    # Check If-None-Match (ETag takes precedence)
    if_none_match = request.headers.get('If-None-Match', '').strip()
    if if_none_match:
        # Strip W/ for comparison (weak comparison for cache validation)
        client_etags = [e.strip().removeprefix('W/') for e in if_none_match.split(',')]
        if etag.removeprefix('W/') in client_etags or '*' == if_none_match.strip():
            # Not modified — return 304 with headers but no body
            response.headers['ETag'] = etag
            response.headers['Last-Modified'] = format_datetime(last_modified_dt, usegmt=True)
            return Response(status_code=304, headers=response.headers)

    # Check If-Modified-Since (weaker fallback)
    if_modified_since = request.headers.get('If-Modified-Since')
    if if_modified_since and not if_none_match:
        try:
            client_time = parsedate_to_datetime(if_modified_since)
            # Compare truncated to seconds (HTTP date precision)
            if last_modified_dt.replace(microsecond=0) <= client_time:
                return Response(status_code=304)
        except (TypeError, ValueError):
            pass

    # Return full response with cache headers
    response.headers['ETag'] = etag
    response.headers['Last-Modified'] = format_datetime(last_modified_dt, usegmt=True)
    response.headers['Cache-Control'] = 'private, max-age=300, must-revalidate'
    response.headers['Vary'] = 'Authorization, Accept-Encoding'

    return {
        'id': article['id'],
        'title': article['title'],
        'body': article['body'],
        'version': article['version'],
    }


# ==========================================================================
# 3. PUT WITH If-Match (OPTIMISTIC CONCURRENCY)
# ==========================================================================

class ArticleUpdate(BaseModel):
    title: str | None = None
    body: str | None = None


@app.put('/articles/{article_id}')
async def update_article(
    article_id: int,
    payload: ArticleUpdate,
    if_match: str = Header(..., alias='If-Match'),
):
    article = articles_db.get(article_id)
    if not article:
        raise HTTPException(404)

    current_etag = make_etag(article)

    # Strict ETag match required for writes (no W/)
    client_etag = if_match.strip()
    if client_etag.startswith('W/'):
        raise HTTPException(412, 'Weak ETags not allowed for writes')

    if client_etag != current_etag:
        # Resource changed since client GET — return current state
        raise HTTPException(
            status_code=412,
            detail={
                'error': 'Precondition Failed',
                'message': 'Resource was modified by another user',
                'current_etag': current_etag,
                'your_etag': client_etag,
            },
        )

    # Atomic update — version bump
    article['version'] += 1
    article['updated_at'] = datetime.now(timezone.utc)
    if payload.title is not None:
        article['title'] = payload.title
    if payload.body is not None:
        article['body'] = payload.body

    new_etag = make_etag(article)

    return JSONResponse(
        content={
            'id': article['id'],
            'title': article['title'],
            'body': article['body'],
            'version': article['version'],
        },
        headers={'ETag': new_etag},
    )


# ==========================================================================
# 4. POST WITH If-None-Match (CREATE-IF-NOT-EXISTS)
# ==========================================================================

@app.put('/articles/{article_id}/idempotent')
async def upsert_article(
    article_id: int,
    payload: ArticleUpdate,
    if_none_match: str = Header(None, alias='If-None-Match'),
):
    """If-None-Match: * → create only if doesn't exist."""

    existing = articles_db.get(article_id)

    if if_none_match == '*':
        # Create only
        if existing:
            raise HTTPException(412, 'Resource already exists')
        # Create new
        articles_db[article_id] = {
            'id': article_id,
            'title': payload.title or 'Untitled',
            'body': payload.body or '',
            'version': 1,
            'updated_at': datetime.now(timezone.utc),
        }
        article = articles_db[article_id]
        return JSONResponse(
            content={'id': article['id']},
            status_code=201,
            headers={'ETag': make_etag(article)},
        )

    # Standard update / create
    if not existing:
        # Create
        articles_db[article_id] = {
            'id': article_id,
            'title': payload.title or 'Untitled',
            'body': payload.body or '',
            'version': 1,
            'updated_at': datetime.now(timezone.utc),
        }
        article = articles_db[article_id]
        return JSONResponse(
            content={'id': article['id']},
            status_code=201,
            headers={'ETag': make_etag(article)},
        )

    # Update
    existing['version'] += 1
    existing['updated_at'] = datetime.now(timezone.utc)
    if payload.title:
        existing['title'] = payload.title
    if payload.body:
        existing['body'] = payload.body

    return JSONResponse(
        content={'id': existing['id'], 'version': existing['version']},
        headers={'ETag': make_etag(existing)},
    )


# ==========================================================================
# 5. DELETE WITH If-Match
# ==========================================================================

@app.delete('/articles/{article_id}')
async def delete_article(
    article_id: int,
    if_match: str = Header(..., alias='If-Match'),
):
    article = articles_db.get(article_id)
    if not article:
        raise HTTPException(404)

    current_etag = make_etag(article)
    if if_match != current_etag:
        raise HTTPException(412, 'Resource modified')

    del articles_db[article_id]
    return Response(status_code=204)


# ==========================================================================
# 6. CONDITIONAL HEADERS HELPER (reusable)
# ==========================================================================

class ConditionalRequestMixin:
    """Reusable conditional request handling."""

    @staticmethod
    def check_not_modified(request: Request, etag: str, last_modified: datetime) -> bool:
        """Returns True if client has current version (return 304)."""

        if_none_match = request.headers.get('If-None-Match', '').strip()
        if if_none_match:
            if if_none_match == '*':
                return True
            client_etags = [
                e.strip().removeprefix('W/')
                for e in if_none_match.split(',')
            ]
            return etag.removeprefix('W/') in client_etags

        if_modified_since = request.headers.get('If-Modified-Since')
        if if_modified_since:
            try:
                client_time = parsedate_to_datetime(if_modified_since)
                return last_modified.replace(microsecond=0) <= client_time
            except (TypeError, ValueError):
                pass

        return False

    @staticmethod
    def check_precondition(request: Request, etag: str, required: bool = True) -> tuple[bool, str]:
        """For writes: returns (passed, error_message)."""

        if_match = request.headers.get('If-Match', '').strip()

        if not if_match:
            if required:
                return False, 'If-Match required (428 Precondition Required)'
            return True, ''

        if if_match.startswith('W/'):
            return False, 'Weak ETags not allowed for writes'

        if if_match == '*':
            return True, ''   # any current version

        return if_match == etag, 'Precondition Failed (412)' if if_match != etag else ''

    @staticmethod
    def set_conditional_headers(response: Response, etag: str, last_modified: datetime, max_age: int = 300):
        response.headers['ETag'] = etag
        response.headers['Last-Modified'] = format_datetime(last_modified, usegmt=True)
        response.headers['Cache-Control'] = f'private, max-age={max_age}, must-revalidate'


# ==========================================================================
# 7. USE THE MIXIN
# ==========================================================================

@app.get('/articles-v2/{article_id}')
async def get_article_v2(article_id: int, request: Request, response: Response):
    article = articles_db.get(article_id)
    if not article:
        raise HTTPException(404)

    etag = make_etag(article)

    if ConditionalRequestMixin.check_not_modified(request, etag, article['updated_at']):
        return Response(status_code=304, headers={'ETag': etag})

    ConditionalRequestMixin.set_conditional_headers(response, etag, article['updated_at'])
    return {
        'id': article['id'],
        'title': article['title'],
        'body': article['body'],
        'version': article['version'],
    }


# ==========================================================================
# 8. CONTENT-BASED ETag (slower but accurate)
# ==========================================================================

@app.get('/articles-v3/{article_id}')
async def get_article_v3(article_id: int, request: Request, response: Response):
    """Content-hash ETag — accurate even if updated_at doesn't change."""

    article = articles_db.get(article_id)
    if not article:
        raise HTTPException(404)

    # Hash the serialized response
    body = json.dumps(article, default=str, sort_keys=True)
    etag = make_etag_content_hash(body)

    if request.headers.get('If-None-Match', '') == etag:
        return Response(status_code=304, headers={'ETag': etag})

    response.headers['ETag'] = etag
    response.headers['Cache-Control'] = 'private, max-age=300'
    return json.loads(body)


# ==========================================================================
# 9. MIDDLEWARE — AUTO ETAG ON ALL GETS
# ==========================================================================

@app.middleware('http')
async def auto_etag_middleware(request: Request, call_next):
    """Auto-add ETag to GET responses based on body hash."""

    if request.method != 'GET':
        return await call_next(request)

    response = await call_next(request)

    # Only JSON 200 responses
    if response.status_code != 200:
        return response
    if 'application/json' not in response.headers.get('content-type', ''):
        return response

    # Read body (must reconstruct as response iterator consumed)
    body_chunks = []
    async for chunk in response.body_iterator:
        body_chunks.append(chunk)
    body = b''.join(body_chunks)

    etag = make_etag_content_hash(body)

    # Check If-None-Match
    if request.headers.get('If-None-Match', '') == etag:
        return Response(status_code=304, headers={'ETag': etag})

    # Add ETag header
    return Response(
        content=body,
        status_code=response.status_code,
        headers={**response.headers, 'ETag': etag},
        media_type=response.headers.get('content-type'),
    )


# ==========================================================================
# 10. DJANGO IMPLEMENTATION
# ==========================================================================

"""
# Django's @condition decorator

from django.views.decorators.http import condition
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404


def article_etag(request, article_id):
    article = Article.objects.filter(pk=article_id).values('version', 'updated_at').first()
    if not article:
        return None
    return f'"{article["version"]}-{int(article["updated_at"].timestamp())}"'


def article_last_modified(request, article_id):
    article = Article.objects.filter(pk=article_id).values('updated_at').first()
    return article['updated_at'] if article else None


@condition(etag_func=article_etag, last_modified_func=article_last_modified)
def get_article_django(request, article_id):
    article = get_object_or_404(Article, pk=article_id)
    return JsonResponse({
        'id': article.id,
        'title': article.title,
        'body': article.body,
        'version': article.version,
    })


# Django auto:
# - Returns 304 if If-None-Match matches
# - Adds ETag + Last-Modified headers
# - Returns 412 if If-Match doesn't match
"""


# ==========================================================================
# 11. DRF VIEWSET WITH CONDITIONAL
# ==========================================================================

"""
class ArticleViewSet(viewsets.ModelViewSet):
    queryset = Article.objects.all()
    serializer_class = ArticleSerializer

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        etag = f'"{instance.version}-{int(instance.updated_at.timestamp())}"'

        if request.headers.get('If-None-Match') == etag:
            return Response(status=304, headers={'ETag': etag})

        response = Response(self.get_serializer(instance).data)
        response['ETag'] = etag
        response['Last-Modified'] = format_datetime(instance.updated_at, usegmt=True)
        response['Cache-Control'] = 'private, max-age=300'
        return response

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        current_etag = f'"{instance.version}-{int(instance.updated_at.timestamp())}"'

        if_match = request.headers.get('If-Match')
        if not if_match:
            return Response({'error': 'If-Match required'}, status=428)

        # Atomic conditional UPDATE
        with transaction.atomic():
            updated = Article.objects.filter(
                pk=instance.pk,
                version=instance.version,
            ).update(
                version=F('version') + 1,
                updated_at=timezone.now(),
                **{k: v for k, v in serializer.validated_data.items() if v is not None},
            )

            if updated == 0:
                return Response({'error': 'Precondition Failed'}, status=412)

        instance.refresh_from_db()
        new_etag = f'"{instance.version}-{int(instance.updated_at.timestamp())}"'
        response = Response(self.get_serializer(instance).data)
        response['ETag'] = new_etag
        return response
"""


# ==========================================================================
# 12. CLIENT IMPLEMENTATION (Python)
# ==========================================================================

CLIENT_EXAMPLE = """
import httpx


client = httpx.Client(base_url='https://api.example.com')


# 1. GET with caching
class CachedClient:
    def __init__(self):
        self.cache = {}

    def get(self, url):
        cached = self.cache.get(url, {})

        headers = {}
        if cached.get('etag'):
            headers['If-None-Match'] = cached['etag']

        resp = client.get(url, headers=headers)

        if resp.status_code == 304:
            return cached['body']

        new_cache = {'body': resp.json(), 'etag': resp.headers.get('ETag', '')}
        self.cache[url] = new_cache
        return new_cache['body']


# 2. Optimistic update with retry
def update_article(article_id, updates, max_retries=3):
    for attempt in range(max_retries):
        # GET current state
        resp = client.get(f'/articles/{article_id}')
        article = resp.json()
        etag = resp.headers['ETag']

        # Modify
        updated_article = {**article, **updates}

        # PUT with If-Match
        put_resp = client.put(
            f'/articles/{article_id}',
            json=updates,
            headers={'If-Match': etag},
        )

        if put_resp.status_code == 200:
            return put_resp.json()
        elif put_resp.status_code == 412:
            # Conflict — refetch + retry
            print(f'Conflict on attempt {attempt + 1}, retrying...')
            continue
        else:
            put_resp.raise_for_status()

    raise Exception('Max retries exceeded')
"""


# ==========================================================================
# 13. PROD CHECKLIST
# ==========================================================================

PROD_CHECKLIST = """
[ ] ETag on every GET response (significant resources)
[ ] Last-Modified as backup for legacy clients
[ ] Cache-Control header alongside ETag
[ ] Vary header for user-specific responses
[ ] If-None-Match check on GET → 304 if match
[ ] If-Match required on PUT/PATCH for important resources
[ ] 412 Precondition Failed on If-Match mismatch
[ ] 428 Precondition Required if If-Match missing (when required)
[ ] Strong ETag (not weak) for write protection
[ ] Cheap ETag generation (version field, not content hash)
[ ] Quoted ETag values ("..." not ...)
[ ] Atomic UPDATE with WHERE version=X (DB-level check)
[ ] Client retry logic on 412 (refetch + retry)
[ ] CDN configured to honor conditional requests
[ ] Tested with browser cache + curl manually
"""
