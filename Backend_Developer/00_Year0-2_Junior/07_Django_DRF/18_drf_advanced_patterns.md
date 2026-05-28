# DRF Advanced Patterns — Throttling, Nested Writable, Dynamic Fields

## Why It Matters (Senior 5 YOE Context)

DRF basics (ViewSets, Serializers) sab seniors jaante hain. Senior interviews differentiate via:

- **Custom throttling** → per-tier rate limits, abuse prevention
- **Nested writable** → atomic create/update of related models
- **Dynamic fields** → API supports `?fields=id,name` for bandwidth control
- **Response envelopes** → consistent `{data, meta, errors}` structure
- **Polymorphic serialization** → one endpoint, multiple shapes
- **Action-specific serializers** → list vs detail with different fields

These = the difference between junior DRF and "I scaled DRF to 10K RPS".

---

## Core Concepts

### Custom Throttle Classes

```python
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle, SimpleRateThrottle


class BurstUserThrottle(UserRateThrottle):
    scope = 'burst'    # links to DRF_THROTTLE_RATES['burst']


class SustainedUserThrottle(UserRateThrottle):
    scope = 'sustained'


# Per-tier throttle
class TieredUserThrottle(SimpleRateThrottle):
    scope = 'tiered'

    def get_cache_key(self, request, view):
        if request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)
        return f'throttle_{self.scope}_{ident}'

    def allow_request(self, request, view):
        # Dynamic rate by user tier
        if request.user.is_authenticated:
            tier = getattr(request.user, 'tier', 'free')
            rates = {'free': '100/hour', 'pro': '1000/hour', 'enterprise': '10000/hour'}
            self.rate = rates.get(tier, '100/hour')
        else:
            self.rate = '20/hour'
        self.num_requests, self.duration = self.parse_rate(self.rate)
        return super().allow_request(request, view)


# settings.py
REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_CLASSES': [
        'core.throttles.BurstUserThrottle',
        'core.throttles.SustainedUserThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'burst': '60/minute',
        'sustained': '1000/day',
        'tiered': '100/hour',
    },
}
```

### ScopedRateThrottle (per-action)

```python
from rest_framework.throttling import ScopedRateThrottle


class ArticleViewSet(viewsets.ModelViewSet):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'articles'

    @action(detail=False)
    def export(self, request):
        # Different scope for expensive endpoint
        self.throttle_scope = 'articles_export'
        return Response(...)


# settings
DEFAULT_THROTTLE_RATES = {
    'articles': '1000/hour',
    'articles_export': '10/hour',
}
```

### Nested Writable Serializers

```python
class CommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = ['id', 'body', 'author']


class ArticleSerializer(serializers.ModelSerializer):
    comments = CommentSerializer(many=True)   # nested

    class Meta:
        model = Article
        fields = ['id', 'title', 'body', 'comments']

    def create(self, validated_data):
        comments_data = validated_data.pop('comments', [])
        article = Article.objects.create(**validated_data)
        for comment_data in comments_data:
            Comment.objects.create(article=article, **comment_data)
        return article

    def update(self, instance, validated_data):
        comments_data = validated_data.pop('comments', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if comments_data is not None:
            # Strategy: delete all + recreate (simple but lossy)
            instance.comments.all().delete()
            for comment_data in comments_data:
                Comment.objects.create(article=instance, **comment_data)

            # OR strategy 2: match by id (preserves existing)
            # existing = {c.id: c for c in instance.comments.all()}
            # for cd in comments_data:
            #     cid = cd.get('id')
            #     if cid and cid in existing:
            #         for k, v in cd.items():
            #             setattr(existing[cid], k, v)
            #         existing[cid].save()
            #     else:
            #         Comment.objects.create(article=instance, **cd)
        return instance
```

### Dynamic Fields Serializer

```python
class DynamicFieldsModelSerializer(serializers.ModelSerializer):
    """
    Pass `fields=` query param to limit returned fields.
    GET /articles/?fields=id,title  →  only id + title
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        request = self.context.get('request')
        if request is None:
            return

        fields_param = request.query_params.get('fields')
        if fields_param:
            allowed = set(fields_param.split(','))
            existing = set(self.fields)
            for field_name in existing - allowed:
                self.fields.pop(field_name)


class ArticleSerializer(DynamicFieldsModelSerializer):
    class Meta:
        model = Article
        fields = ['id', 'title', 'body', 'author', 'created_at']
```

### Response Envelope (Consistent API Shape)

```python
from rest_framework.renderers import JSONRenderer
from rest_framework import status


class EnvelopeJSONRenderer(JSONRenderer):
    """Wrap response in {data, meta, errors}."""

    def render(self, data, accepted_media_type=None, renderer_context=None):
        response = renderer_context.get('response') if renderer_context else None
        status_code = response.status_code if response else 200

        if status.is_client_error(status_code) or status.is_server_error(status_code):
            envelope = {'data': None, 'errors': data, 'meta': {'status': status_code}}
        else:
            # Detect pagination
            if isinstance(data, dict) and 'results' in data and 'count' in data:
                envelope = {
                    'data': data['results'],
                    'meta': {
                        'status': status_code,
                        'count': data['count'],
                        'next': data.get('next'),
                        'previous': data.get('previous'),
                    },
                    'errors': None,
                }
            else:
                envelope = {'data': data, 'meta': {'status': status_code}, 'errors': None}
        return super().render(envelope, accepted_media_type, renderer_context)


# settings
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': ['core.renderers.EnvelopeJSONRenderer'],
}
```

### Action-Specific Serializers

```python
class ArticleViewSet(viewsets.ModelViewSet):
    queryset = Article.objects.select_related('author').all()

    def get_serializer_class(self):
        if self.action == 'list':
            return ArticleListSerializer       # minimal fields
        if self.action == 'retrieve':
            return ArticleDetailSerializer     # full + nested comments
        if self.action in ('create', 'update', 'partial_update'):
            return ArticleWriteSerializer      # write-specific (no computed fields)
        return ArticleListSerializer
```

### Polymorphic Serialization

```python
class NotificationSerializer(serializers.Serializer):
    """Returns different shape based on type."""

    @classmethod
    def serialize(cls, obj):
        if obj.type == 'comment':
            return CommentNotifSerializer(obj).data
        if obj.type == 'mention':
            return MentionNotifSerializer(obj).data
        if obj.type == 'system':
            return SystemNotifSerializer(obj).data
        return BaseNotifSerializer(obj).data


# Or use rest-polymorphic library for cleaner code
```

### Conditional Field Display

```python
class ArticleSerializer(serializers.ModelSerializer):
    private_notes = serializers.CharField()

    class Meta:
        model = Article
        fields = ['id', 'title', 'private_notes']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        if not (request and request.user == instance.author):
            data.pop('private_notes', None)
        return data
```

---

## How It Works Internally

### Throttle Cache Key

```python
# DRF's UserRateThrottle.get_cache_key:
def get_cache_key(self, request, view):
    if request.user.is_authenticated:
        ident = request.user.pk
    else:
        ident = self.get_ident(request)  # IP address
    return self.cache_format % {'scope': self.scope, 'ident': ident}
# → 'throttle_burst_<user_id>'
```

### Throttle Storage

Default backend: Django's cache. With Redis, throttling scales across multi-instance deployments.

### Nested Write Atomicity

```python
def create(self, validated_data):
    # WRONG — no transaction → partial create on error
    article = Article.objects.create(...)
    for c in comments:
        Comment.objects.create(article=article, **c)

# RIGHT — atomic
from django.db import transaction

def create(self, validated_data):
    with transaction.atomic():
        article = Article.objects.create(...)
        for c in comments:
            Comment.objects.create(article=article, **c)
    return article
```

---

## Common Pitfalls

### 1. Throttle in Memory (no Redis)

`LocMemCache` throttle = per-process, useless behind load balancer. Use Redis.

### 2. Nested Write Race Conditions

Multiple inline writes without transaction = orphaned children. Always `transaction.atomic()`.

### 3. Dynamic Fields + Permissions

```python
# User passes ?fields=secret_field → exposed
```

**Fix:** allowlist fields per role:

```python
def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    request = self.context.get('request')
    user = request.user if request else None
    if not user or not user.is_staff:
        sensitive_fields = ['email', 'phone', 'internal_notes']
        for f in sensitive_fields:
            self.fields.pop(f, None)
```

### 4. Envelope Breaks Pagination Detection

If you wrap everything, OpenAPI/Swagger schema generation breaks. Use response envelope renderer only for non-schema endpoints OR generate custom schema.

### 5. M2M in Nested Writable

```python
# Tags (M2M) — different from FK reverse
class ArticleSerializer:
    tags = TagSerializer(many=True)

    def create(self, validated_data):
        tags_data = validated_data.pop('tags')
        article = Article.objects.create(**validated_data)
        tag_objs = []
        for t in tags_data:
            tag, _ = Tag.objects.get_or_create(name=t['name'])
            tag_objs.append(tag)
        article.tags.set(tag_objs)
        return article
```

### 6. Custom Throttle Without `wait()`

If `allow_request` returns False, DRF calls `wait()` for Retry-After header. Implement it:

```python
def wait(self):
    return int(self.duration / self.num_requests)  # rough estimate
```

---

## Interview Q&A

**Q1:** DRF mein per-tier rate limit kaise implement karoge?
**A:** Subclass `SimpleRateThrottle`. Override `allow_request` to set `self.rate` based on `request.user.tier` before calling super. Use Redis cache backend so multi-instance throttling works. Return Retry-After via `wait()`.

**Q2:** Nested writable serializer ke trade-offs?
**A:** Pros: single API call, atomic semantics, less round-trips. Cons: complex update logic (match by id vs replace-all), N+1 if not careful, harder to validate, harder to do partial updates. Alternative: separate endpoints + transaction in view.

**Q3:** Dynamic fields ka security risk kya hai?
**A:** User can request fields like `password_hash` or `private_notes`. Mitigate: maintain allowlist per role, never auto-expose serializer fields. Better: define explicit "shapes" (e.g., `?shape=summary|detail`) instead of arbitrary field selection.

**Q4:** Response envelope kab use karoge?
**A:** When API has consistent client expectations — mobile apps, SDKs that wrap errors uniformly. Skip for public REST APIs (breaks REST conventions). Don't apply to OpenAPI schema endpoint or static docs.

**Q5:** Action-specific serializer kab zaroori hai?
**A:** When list vs detail differ a lot — list shows summary fields (avoid heavy fields like full body), detail shows everything + nested. Also write vs read — read includes computed fields, write doesn't.

**Q6:** Polymorphic serialization patterns?
**A:** (1) Manual: serializer factory by type field. (2) `to_representation` switch. (3) `rest-polymorphic` library. Trade-off: explicit factory = simple but verbose; library = magic but learning curve.

**Q7:** Throttle by IP behind load balancer?
**A:** DRF's default uses `request.META['REMOTE_ADDR']` = LB's IP. Configure `NUM_PROXIES` setting or use `X-Forwarded-For`. Better — custom `get_ident()` parsing trusted forwarded header.

**Q8:** DRF mein consistent error response kaise enforce karoge?
**A:** Custom exception handler in `EXCEPTION_HANDLER` setting. Catch all exceptions, transform to RFC 7807 Problem+JSON or custom envelope `{code, message, details}`. Apply to validation errors too via `format_serializer_errors` helper.

---

## Real-World Use Cases

### 1. Tiered SaaS API

Free 100/hour, Pro 1000/hour, Enterprise unlimited. `TieredUserThrottle` reads `user.subscription_tier` from DB.

### 2. Public + Admin Endpoint Same Resource

```python
class ArticleViewSet(viewsets.ModelViewSet):
    def get_serializer_class(self):
        if self.request.user.is_staff:
            return AdminArticleSerializer  # all fields
        return PublicArticleSerializer     # filtered fields
```

### 3. Bandwidth-Optimized Mobile API

```
GET /articles/?fields=id,title  →  3 KB
GET /articles/                  →  50 KB (full)
```

Saves mobile data, faster on slow networks.

---

## References

- [DRF docs — Throttling](https://www.django-rest-framework.org/api-guide/throttling/)
- [DRF docs — Serializer relations](https://www.django-rest-framework.org/api-guide/relations/)
- `drf-flex-fields`, `drf-dynamic-fields` libraries
- `rest-polymorphic` for polymorphic models
