# DRF API Versioning

## Why It Matters

Public APIs need backward compatibility:
- Mobile apps deployed to thousands of users (can't force upgrade)
- Third-party integrations
- Gradual rollouts

Senior interview: "Old mobile clients break after schema change — how do you prevent?" → versioning.

---

## Core Concepts

### Versioning Schemes

| Scheme | URL Example |
|---|---|
| URL Path | `/api/v1/users/` |
| Accept Header | `Accept: application/json; version=1.0` |
| Query Param | `/api/users/?version=1` |
| Namespace | `/api/users/` (resolved by URLconf module) |
| Host | `v1.api.example.com` |

### URL Path Versioning (Most Common)

```python
# settings.py
REST_FRAMEWORK = {
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.URLPathVersioning',
    'DEFAULT_VERSION': 'v1',
    'ALLOWED_VERSIONS': ['v1', 'v2'],
    'VERSION_PARAM': 'version',
}


# urls.py
from django.urls import path, include


urlpatterns = [
    path('api/<version>/users/', UserViewSet.as_view(...)),
]


# Or via router
router = DefaultRouter()
router.register('users', UserViewSet)
urlpatterns = [
    path('api/<version>/', include(router.urls)),
]


# In view
class UserViewSet(viewsets.ModelViewSet):
    def get_serializer_class(self):
        if self.request.version == 'v2':
            return UserSerializerV2
        return UserSerializerV1
```

### Accept Header Versioning

```python
REST_FRAMEWORK = {
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.AcceptHeaderVersioning',
    'DEFAULT_VERSION': '1.0',
}


# Client request
GET /api/users/
Accept: application/json; version=2.0


# View
class UserView(APIView):
    def get(self, request):
        if request.version == '2.0':
            ...
```

### Namespace Versioning

```python
# urls.py
v1_patterns = [path('users/', UserViewSetV1.as_view(...))]
v2_patterns = [path('users/', UserViewSetV2.as_view(...))]

urlpatterns = [
    path('api/v1/', include((v1_patterns, 'v1'))),
    path('api/v2/', include((v2_patterns, 'v2'))),
]


REST_FRAMEWORK = {
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.NamespaceVersioning',
}


# View can use namespace for reverse
reverse('v2:user-detail', request=request)
```

### Multiple Serializer Versions

```python
class UserSerializerV1(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']


class UserSerializerV2(serializers.ModelSerializer):
    profile = ProfileSerializer(read_only=True)   # added in v2

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'profile']
```

### Version-Aware ViewSet

```python
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()

    def get_serializer_class(self):
        if self.request.version == 'v2':
            return UserSerializerV2
        return UserSerializerV1

    def get_queryset(self):
        qs = User.objects.all()
        if self.request.version == 'v2':
            # v2 adds prefetch (new field)
            qs = qs.prefetch_related('profile')
        return qs
```

### Deprecation Headers

```python
class DeprecatedV1Mixin:
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        if request.version == 'v1':
            response['Deprecation'] = 'true'
            response['Sunset'] = 'Sat, 31 Dec 2026 23:59:59 GMT'
            response['Link'] = '<https://docs.example.com/api-v2-migration>; rel="successor-version"'
        return response


class UserViewSet(DeprecatedV1Mixin, viewsets.ModelViewSet):
    ...
```

### Custom Versioning Logic

```python
from rest_framework.versioning import BaseVersioning


class CustomVersioning(BaseVersioning):
    """Version from X-API-Version header, fallback to query param."""

    default_version = '1.0'
    allowed_versions = ['1.0', '2.0', '2.1']
    version_param = 'X-API-Version'

    def determine_version(self, request, *args, **kwargs):
        version = request.headers.get(self.version_param)
        if not version:
            version = request.query_params.get('version', self.default_version)
        if version not in self.allowed_versions:
            from rest_framework.exceptions import NotFound
            raise NotFound(f"Unsupported version: {version}")
        return version
```

### Deprecation Workflow

1. **Add new version** (v2). Keep v1 working.
2. **Document migration**. Update docs.
3. **Add deprecation header** on v1.
4. **Set sunset date** (3-12 months out).
5. **Monitor v1 usage** (track via metrics, contact heavy users).
6. **At sunset**: remove v1, return 410 Gone for old endpoints.

```python
class GoneView(APIView):
    def get(self, request):
        from rest_framework.response import Response
        return Response(
            {'error': 'This API version has been removed. Use /api/v2/'},
            status=410,
        )
```

---

## Common Pitfalls

### 1. Versioning Without Strategy

Adding `v2/` for every breaking change → 20 versions = maintenance nightmare. Plan deprecation cycle (1-2 active versions).

### 2. Breaking Changes Without Version Bump

Changing field type in v1 → existing clients break. Always bump version for breaking changes.

### 3. Same URL Pattern Without Version

```
/api/users/   (v1, no version)
/api/v2/users/
```

Hard to track who's on what. Always include version explicitly.

### 4. Database-Level Versioning

```python
# WRONG — same model, different shapes per version
# Maintain serializer-level versioning, single model
```

### 5. Forgetting Deprecation Headers

Clients don't know they're using deprecated API → surprise breakage at sunset.

### 6. No Sunset Plan

v1 + v2 + v3 + v4 forever. Each costs maintenance. Sunset oldest within 12 months.

---

## Interview Q&A

**Q1:** DRF mein versioning schemes konsi?
**A:** URL path (most common — `/api/v1/`), Accept header (RESTful — `Accept: ...; version=2`), Query param (`?version=2`), Namespace (URLconf-based), Host (subdomain). URL path most discoverable + cacheable. Accept header purist but harder to test/debug.

**Q2:** Backward-incompatible change kaise handle karoge?
**A:** (1) Bump major version (v1 → v2). (2) Keep v1 working with new code paths. (3) Document migration. (4) Add deprecation headers on v1. (5) Monitor v1 usage. (6) Sunset after grace period (typically 6-12 months).

**Q3:** Multiple serializer versions kaise manage?
**A:** Separate `UserSerializerV1`, `UserSerializerV2` classes. ViewSet's `get_serializer_class` returns based on `request.version`. Share common logic via base class or mixins. Don't try to make one serializer handle all versions with conditionals — complex + bug-prone.

**Q4:** Mobile app legacy support strategy?
**A:** Critical — can't force upgrade. Strategy: long deprecation cycles (12+ months), in-app warnings before sunset, fallback gracefully on 410 Gone (show "update app" screen), analytics on which versions in use.

**Q5:** Deprecation header HTTP standard?
**A:** RFC 8594 standardizes `Sunset` header (when removed). `Deprecation: true` (informal). `Link: <new-url>; rel="successor-version"` for migration target. Clients can warn users / log usage.

**Q6:** API gateway pe versioning karein?
**A:** Pros: routing logic at edge, backend services unaware. Cons: more layer. Common pattern: gateway routes `/v1/*` to old service, `/v2/*` to new. Or single service handles both. Choose based on team structure.

**Q7:** REST versioning vs GraphQL evolution?
**A:** REST: explicit versions. GraphQL: deprecate fields via `@deprecated(reason: ...)`, add new ones. Clients query only what they use. No version bump needed for additive changes. Removing requires deprecation cycle.

**Q8:** Internal vs external APIs versioning?
**A:** Internal: looser — can coordinate releases, even break changes with notice. External (public, partners): strict — version everything, long deprecation. Mobile: longest cycles (multi-year sometimes).

---

## Real-World Use Cases

### 1. Public REST API

URL path versioning. v1 frozen, v2 active. Sunset v1 12 months after v2 launch. Deprecation header on v1.

### 2. Stripe-Style Date-Based Versioning

Header `Stripe-Version: 2023-10-16`. Each version = snapshot of behavior. New users get default; old users on their original.

### 3. Mobile App Min-Version Enforcement

```python
@api_view
def some_endpoint(request):
    if request.headers.get('X-App-Version', '0') < '2.5':
        return Response(
            {'error': 'Update app to continue'},
            status=426,  # Upgrade Required
        )
```

---

## References

- [DRF Versioning](https://www.django-rest-framework.org/api-guide/versioning/)
- [RFC 8594 — Sunset HTTP Header](https://datatracker.ietf.org/doc/html/rfc8594)
- Stripe API versioning blog
