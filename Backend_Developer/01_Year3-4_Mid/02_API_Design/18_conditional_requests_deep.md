# Conditional Requests Deep — ETag, If-Match, Optimistic Concurrency

## Why It Matters

HTTP conditional requests = bandwidth saving + concurrent update safety:
- `If-None-Match` → 304 Not Modified (save bandwidth)
- `If-Match` → 412 Precondition Failed (prevent lost updates)
- `If-Modified-Since` → time-based variant
- `If-Unmodified-Since` → write protection

Senior interview: "Two users edit same article simultaneously — prevent lost updates?" → If-Match with ETag.

---

## ETag (Entity Tag)

Fingerprint of resource version.

### Strong vs Weak

```http
ETag: "abc123"          # strong (byte-identical)
ETag: W/"abc123"        # weak (semantically equivalent — minor diff OK)
```

Strong: any byte change = different ETag.
Weak: ignore minor differences (whitespace, comments, dates).

### Generating ETags

```python
# Option 1: Content hash
import hashlib


etag = hashlib.md5(json.dumps(article).encode()).hexdigest()


# Option 2: Version + updated_at (cheaper)
etag = f'{article.version}-{article.updated_at.timestamp()}'


# Option 3: From DB row version
etag = str(article.updated_at.timestamp())
```

---

## If-None-Match (Cache Validation)

```
Client → GET /articles/1
Server → 200 OK
         ETag: "v1-abc"
         Body: {...}

[Client caches body + ETag]

Client → GET /articles/1
         If-None-Match: "v1-abc"
Server → 304 Not Modified (no body!)

Client uses cached body.
```

**Saves bandwidth** — server doesn't send unchanged content.

### Implementation

```python
@app.get('/articles/{article_id}')
async def get_article(
    article_id: int,
    request: Request,
    response: Response,
):
    article = await fetch_article(article_id)
    if not article:
        raise HTTPException(404)

    # Generate ETag
    etag = f'"{article["version"]}-{article["updated_at"]}"'

    # Check If-None-Match
    if_none_match = request.headers.get('If-None-Match', '')
    if etag == if_none_match:
        return Response(status_code=304)

    response.headers['ETag'] = etag
    response.headers['Cache-Control'] = 'private, max-age=300'
    return article
```

---

## If-Match (Optimistic Concurrency)

Prevent lost updates when multiple users edit same resource.

```
User A: GET /articles/1
        → 200 + ETag: "v1-abc"
        → A starts editing

User B: GET /articles/1
        → 200 + ETag: "v1-abc"
        → B starts editing

User B: PUT /articles/1
        If-Match: "v1-abc"
        → 200 OK (B's update succeeds, ETag now "v2-def")

User A: PUT /articles/1
        If-Match: "v1-abc"
        → 412 Precondition Failed (B already updated)
        → A's UI shows: "Article changed since you started editing. Reload?"
```

### Implementation

```python
@app.put('/articles/{article_id}')
async def update_article(
    article_id: int,
    payload: ArticleUpdate,
    request: Request,
    response: Response,
):
    article = await fetch_article(article_id)
    if not article:
        raise HTTPException(404)

    current_etag = f'"{article["version"]}-{article["updated_at"]}"'

    # If-Match check
    if_match = request.headers.get('If-Match', '')
    if not if_match:
        raise HTTPException(428, 'Precondition Required: provide If-Match header')

    if if_match != current_etag:
        raise HTTPException(412, 'Precondition Failed: resource modified')

    # Atomic update with optimistic lock
    updated = await db.update(
        article_id,
        version=article['version'] + 1,
        **payload.model_dump(),
    )

    response.headers['ETag'] = f'"{updated["version"]}-{updated["updated_at"]}"'
    return updated
```

---

## Last-Modified / If-Modified-Since (Weaker Alternative)

```
Server → 200 OK
         Last-Modified: Sat, 15 Jan 2026 10:00:00 GMT

Client → GET /articles/1
         If-Modified-Since: Sat, 15 Jan 2026 10:00:00 GMT

Server → 304 Not Modified (if not modified after that time)
```

**Limitations:**
- Second precision only
- Less reliable than ETag
- Multiple changes within 1 second = missed

ETag preferred. Last-Modified for legacy clients.

### Implementation

```python
from email.utils import format_datetime, parsedate_to_datetime


@app.get('/articles/{article_id}')
async def get_article_last_modified(
    article_id: int,
    request: Request,
    response: Response,
):
    article = await fetch_article(article_id)

    if_modified_since = request.headers.get('If-Modified-Since')
    if if_modified_since:
        try:
            client_time = parsedate_to_datetime(if_modified_since)
            if article['updated_at'] <= client_time:
                return Response(status_code=304)
        except (TypeError, ValueError):
            pass

    response.headers['Last-Modified'] = format_datetime(article['updated_at'], usegmt=True)
    return article
```

---

## Combining ETag + Last-Modified

```http
HTTP/1.1 200 OK
ETag: "v1-abc"
Last-Modified: Sat, 15 Jan 2026 10:00:00 GMT
Cache-Control: private, max-age=300

Body...
```

Client uses whichever supported. Server checks both:

```python
def is_unchanged(request, etag, last_modified):
    if_none_match = request.headers.get('If-None-Match', '')
    if etag and etag == if_none_match:
        return True

    if_modified_since = request.headers.get('If-Modified-Since')
    if if_modified_since and last_modified:
        try:
            client_time = parsedate_to_datetime(if_modified_since)
            if last_modified <= client_time:
                return True
        except (TypeError, ValueError):
            pass

    return False
```

---

## If-Unmodified-Since (Write Protection)

```
Client → PUT /articles/1
         If-Unmodified-Since: Sat, 15 Jan 2026 10:00:00 GMT

Server → 412 Precondition Failed (if modified after that time)
```

Weaker variant of If-Match. Use If-Match (ETag) preferred.

---

## Vary Header (Cache Differentiation)

```http
HTTP/1.1 200 OK
ETag: "v1-abc"
Vary: Accept-Encoding, Authorization
```

Browser/CDN: cache different versions per varying header value.

**Common varies:**
- `Accept-Encoding` (gzip vs uncompressed)
- `Accept-Language` (i18n)
- `Authorization` (per-user content)
- `User-Agent` (mobile vs desktop)

---

## CDN-Level Conditional

CloudFront, Cloudflare honor ETag/Last-Modified:

```
Client → CDN: GET /article
CDN → Origin: GET /article + If-None-Match: "v1-abc"
Origin → CDN: 304 Not Modified
CDN → Client: 200 OK (cached version)
```

CDN avoids fetching unchanged content. Origin saves bandwidth.

---

## Optimistic vs Pessimistic Concurrency

| | Optimistic (ETag) | Pessimistic (Lock) |
|---|---|---|
| When | Low contention | High contention |
| Performance | Fast (no lock) | Slower (lock held) |
| Failures | Retry on conflict | Wait + maybe deadlock |
| Implementation | ETag + If-Match | SELECT FOR UPDATE |
| Trade-off | Wasted work on conflict | Reduced throughput |

For web APIs: optimistic via ETag (most users don't conflict).
For inventory deduction: pessimistic (high contention).

---

## DRF / Django Implementation

### View with ETag

```python
import hashlib

from django.views.decorators.http import etag
from django.views.decorators.http import condition


def article_etag(request, article_id):
    article = Article.objects.filter(pk=article_id).values('version', 'updated_at').first()
    if not article:
        return None
    return f'"{article["version"]}-{article["updated_at"].timestamp()}"'


def article_last_modified(request, article_id):
    article = Article.objects.filter(pk=article_id).values('updated_at').first()
    return article['updated_at'] if article else None


@condition(etag_func=article_etag, last_modified_func=article_last_modified)
def get_article(request, article_id):
    article = get_object_or_404(Article, pk=article_id)
    return JsonResponse({'id': article.id, 'title': article.title})
```

Django automatically returns 304 if conditional matches.

### DRF Custom

```python
class ArticleViewSet(viewsets.ModelViewSet):
    queryset = Article.objects.all()
    serializer_class = ArticleSerializer

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        etag = f'"{instance.version}-{instance.updated_at.timestamp()}"'

        if_none_match = request.headers.get('If-None-Match', '')
        if etag == if_none_match:
            return Response(status=304)

        response = Response(self.get_serializer(instance).data)
        response['ETag'] = etag
        response['Cache-Control'] = 'private, max-age=300'
        return response

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        current_etag = f'"{instance.version}-{instance.updated_at.timestamp()}"'

        if_match = request.headers.get('If-Match', '')
        if not if_match:
            return Response({'error': 'If-Match required'}, status=428)
        if if_match != current_etag:
            return Response({'error': 'Resource modified'}, status=412)

        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)

        # Atomic update with version check
        updated = Article.objects.filter(
            pk=instance.pk,
            version=instance.version,
        ).update(
            version=F('version') + 1,
            **serializer.validated_data,
        )

        if updated == 0:
            return Response({'error': 'Concurrent modification'}, status=412)

        instance.refresh_from_db()
        new_etag = f'"{instance.version}-{instance.updated_at.timestamp()}"'

        response = Response(self.get_serializer(instance).data)
        response['ETag'] = new_etag
        return response
```

---

## Common Pitfalls

### 1. ETag Per-Request Generation Expensive

```python
def etag(request, pk):
    article = Article.objects.get(pk=pk)   # full row fetch
    return hashlib.md5(serialize(article).encode()).hexdigest()   # heavy
```

Use cheap version field (version number, updated_at timestamp).

### 2. Weak ETag Misused

```python
ETag: W/"v1"
```

Weak allowed for cache validation but NOT for If-Match (RFC 9110). Use strong for write protection.

### 3. No If-Match Required

Allowing PUT without If-Match → silent lost updates. Either require always (428) or document mutual agreement.

### 4. ETag Without `Vary`

Per-user content cached at CDN → wrong user gets data. Add `Vary: Authorization` or use ETag tied to user_id.

### 5. Mixing ETag + Last-Modified Wrong

```python
ETag matches → 304
Last-Modified doesn't match → still 304 (ETag takes precedence)
```

Spec: ETag takes precedence over Last-Modified.

### 6. ETag Without `Cache-Control`

```http
ETag: "abc"
# No Cache-Control → browser may not cache at all
```

Always pair with `Cache-Control: private, max-age=N`.

### 7. Quoted vs Unquoted

```http
ETag: abc      # WRONG (must be quoted)
ETag: "abc"    # RIGHT
```

Always quote.

---

## Interview Q&A

**Q1:** ETag use cases?
**A:** (1) Cache validation — `If-None-Match` → 304 saves bandwidth. (2) Optimistic concurrency — `If-Match` prevents lost updates. (3) CDN efficiency — origin returns 304 to CDN. (4) Conditional GET in browsers. Combine with Cache-Control headers.

**Q2:** Strong vs weak ETag?
**A:** Strong: byte-identical response. Weak: `W/"..."` semantically equivalent (minor diff OK). Strong for cache validation. Weak useful for gzip vs uncompressed responses. RFC 9110: If-Match accepts only strong (writes need exactness).

**Q3:** ETag vs Last-Modified?
**A:** ETag: any precision, includes content fingerprint, reliable. Last-Modified: timestamp-based, second precision, may miss rapid changes. ETag preferred. Provide both for compat — clients use whichever they support.

**Q4:** Optimistic locking via ETag?
**A:** Client GETs resource with ETag. PUT with `If-Match: <etag>`. Server checks: if current ETag matches → update + new ETag. Else → 412 Precondition Failed. Client refetches, retries. Prevents lost updates without server-side locks.

**Q5:** If-Match required vs optional?
**A:** Optional (lenient): allows PUT without check — risk lost updates. Required (strict): missing header → 428 Precondition Required. Production: REQUIRED for important resources (orders, inventory, settings). Optional for low-stakes (drafts, comments).

**Q6:** CDN + ETag?
**A:** CDN caches response with ETag. On subsequent requests, CDN forwards to origin with `If-None-Match`. Origin returns 304. CDN serves cached. Saves origin bandwidth + processing. Works with CloudFront, Cloudflare, Fastly.

**Q7:** ETag for paginated lists?
**A:** Tricky — list contents change frequently. Options: (1) ETag based on max(updated_at) of items in list. (2) ETag for individual items, not list. (3) Cache-Control max-age only (no conditional). Generally: don't ETag mutable lists; ETag individual resources.

**Q8:** Implementing in FastAPI?
**A:**
```python
@app.get('/article/{id}')
async def get_article(id: int, request: Request, response: Response):
    article = await fetch(id)
    etag = f'"{article.version}-{article.updated_at.timestamp()}"'
    if request.headers.get('If-None-Match') == etag:
        return Response(status_code=304)
    response.headers['ETag'] = etag
    return article
```

---

## Real-World Examples

### Google Docs

Collaborative editing — operational transform avoids most conflicts. ETag on document version for save operations. 412 on conflict triggers re-merge.

### GitHub API

Returns ETag on every resource. Recommends conditional requests:
```http
GET /repos/owner/repo
If-None-Match: "abc123"
```
Saves API rate limit on unchanged responses.

### S3 Object Versioning

Each object has ETag (MD5 hash). Multi-part uploads have synthesized ETag. Used for PUT-if-match conditional updates.

---

## References

- [RFC 9110 — HTTP Semantics (Conditional Requests)](https://datatracker.ietf.org/doc/html/rfc9110#section-13)
- [MDN HTTP conditional requests](https://developer.mozilla.org/en-US/docs/Web/HTTP/Conditional_requests)
- [GitHub API conditional requests](https://docs.github.com/en/rest/overview/resources-in-the-rest-api#conditional-requests)
- [Optimistic concurrency Wikipedia](https://en.wikipedia.org/wiki/Optimistic_concurrency_control)
