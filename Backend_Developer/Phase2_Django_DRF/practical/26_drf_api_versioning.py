"""
DRF API Versioning — Production Patterns
"""

# ==========================================================================
# 1. SETTINGS — URL Path Versioning (most common)
# ==========================================================================

REST_FRAMEWORK_VERSIONING = """
# settings.py

REST_FRAMEWORK = {
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.URLPathVersioning',
    'DEFAULT_VERSION': 'v1',
    'ALLOWED_VERSIONS': ['v1', 'v2'],
    'VERSION_PARAM': 'version',
}
"""


# ==========================================================================
# 2. URLS with VERSION PARAM
# ==========================================================================

"""
# urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views


router = DefaultRouter()
router.register('users', views.UserViewSet, basename='user')
router.register('orders', views.OrderViewSet, basename='order')


urlpatterns = [
    path('api/<version>/', include(router.urls)),
]
"""


# ==========================================================================
# 3. MULTIPLE SERIALIZER VERSIONS
# ==========================================================================

from rest_framework import serializers
from rest_framework import viewsets


class UserSerializerV1(serializers.ModelSerializer):
    """V1: basic fields."""

    class Meta:
        # model = User
        fields = ['id', 'username', 'email']


class UserSerializerV2(serializers.ModelSerializer):
    """V2: adds profile + email_verified."""

    profile = serializers.SerializerMethodField()
    email_verified = serializers.BooleanField(source='is_email_verified')

    class Meta:
        # model = User
        fields = ['id', 'username', 'email', 'email_verified', 'profile']

    def get_profile(self, obj):
        if hasattr(obj, 'profile'):
            return {'bio': obj.profile.bio, 'avatar': obj.profile.avatar_url}
        return None


# ==========================================================================
# 4. VERSION-AWARE VIEWSET
# ==========================================================================

class UserViewSet(viewsets.ModelViewSet):
    """Version determines serializer + queryset optimizations."""

    permission_classes = []   # configure as needed

    def get_queryset(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()

        qs = User.objects.all()

        # V2 includes profile in response → prefetch
        if self.request.version == 'v2':
            qs = qs.select_related('profile')

        return qs

    def get_serializer_class(self):
        if self.request.version == 'v2':
            return UserSerializerV2
        return UserSerializerV1


# ==========================================================================
# 5. DEPRECATION HEADERS MIXIN
# ==========================================================================

class DeprecatedV1Mixin:
    """Add deprecation headers when client uses v1."""

    DEPRECATION_DATE = 'Sat, 31 Dec 2026 23:59:59 GMT'
    MIGRATION_URL = 'https://docs.example.com/api-v2-migration'

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        if request.version == 'v1':
            response['Deprecation'] = 'true'
            response['Sunset'] = self.DEPRECATION_DATE
            response['Link'] = f'<{self.MIGRATION_URL}>; rel="successor-version"'
            response['Warning'] = '299 - "v1 API is deprecated. Migrate to v2 by 2026-12-31"'
        return response


class UserViewSetVersioned(DeprecatedV1Mixin, UserViewSet):
    pass


# ==========================================================================
# 6. ACCEPT HEADER VERSIONING
# ==========================================================================

"""
# settings.py — alternative scheme
REST_FRAMEWORK = {
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.AcceptHeaderVersioning',
    'DEFAULT_VERSION': '1.0',
    'ALLOWED_VERSIONS': ['1.0', '2.0', '2.1'],
}


# Client sends:
# GET /api/users/
# Accept: application/json; version=2.0
"""


# ==========================================================================
# 7. NAMESPACE VERSIONING
# ==========================================================================

"""
# urls.py
v1_urlpatterns = [
    path('users/', UserViewSetV1.as_view({'get': 'list'})),
]


v2_urlpatterns = [
    path('users/', UserViewSetV2.as_view({'get': 'list'})),
]


urlpatterns = [
    path('api/v1/', include((v1_urlpatterns, 'api'), namespace='v1')),
    path('api/v2/', include((v2_urlpatterns, 'api'), namespace='v2')),
]


# settings.py
REST_FRAMEWORK = {
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.NamespaceVersioning',
}


# Reverse URL with namespace
# reverse('v2:user-detail', kwargs={'pk': 1})
"""


# ==========================================================================
# 8. CUSTOM VERSIONING (Stripe-like date-based)
# ==========================================================================

from rest_framework.versioning import BaseVersioning
from rest_framework.exceptions import NotFound


class DateVersioning(BaseVersioning):
    """Stripe-style: client sends X-API-Version: 2023-10-16."""

    default_version = '2024-01-01'
    allowed_versions = [
        '2023-01-01',
        '2023-06-15',
        '2024-01-01',
        '2024-06-30',
    ]
    version_param = 'X-API-Version'

    def determine_version(self, request, *args, **kwargs):
        version = request.headers.get(self.version_param, self.default_version)
        if version not in self.allowed_versions:
            raise NotFound(f"Unsupported version: {version}. Allowed: {self.allowed_versions}")
        return version

    def is_allowed_version(self, version):
        return version in self.allowed_versions


# Use in settings:
# 'DEFAULT_VERSIONING_CLASS': 'myapp.versioning.DateVersioning',


# ==========================================================================
# 9. CONDITIONAL FIELDS / BEHAVIOR
# ==========================================================================

class UserSerializerAdaptive(serializers.ModelSerializer):
    """Single serializer with version-aware fields."""

    class Meta:
        # model = User
        fields = ['id', 'username', 'email']  # default

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and request.version >= '2.0':
            # Add v2 fields dynamically
            self.fields['email_verified'] = serializers.BooleanField(source='is_email_verified')
            self.fields['profile'] = ProfileSerializer(read_only=True)


class ProfileSerializer(serializers.Serializer):
    bio = serializers.CharField()
    avatar_url = serializers.URLField()


# ==========================================================================
# 10. SUNSET (returning 410 Gone)
# ==========================================================================

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status


class SunsettedV1View(APIView):
    """Returned for endpoints removed in v2+."""

    def dispatch(self, request, *args, **kwargs):
        return Response(
            {
                'error': 'API version v1 is no longer supported',
                'migration_url': 'https://docs.example.com/api-v2-migration',
            },
            status=410,   # Gone
            headers={
                'Sunset': 'Sat, 31 Dec 2026 23:59:59 GMT',
                'Link': '<https://api.example.com/api/v2/>; rel="successor-version"',
            },
        )


# urls.py
# urlpatterns += [
#     path('api/v1/<path:any_path>', SunsettedV1View.as_view()),  # catch-all
# ]


# ==========================================================================
# 11. METRICS / TRACKING VERSION USAGE
# ==========================================================================

# Middleware to count version usage
class VersionMetricsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Increment metric per version
        version = getattr(request, 'version', None)
        if version and request.path.startswith('/api/'):
            # from prometheus_client import Counter
            # API_VERSION_USAGE.labels(version=version, endpoint=request.path).inc()
            pass

        return response


# ==========================================================================
# 12. MINIMUM CLIENT VERSION ENFORCEMENT
# ==========================================================================

from packaging.version import parse as parse_version


class MinClientVersionMixin:
    """Enforce minimum app version via X-App-Version header."""

    MIN_APP_VERSION = '2.5.0'

    def dispatch(self, request, *args, **kwargs):
        app_version = request.headers.get('X-App-Version', '0.0.0')
        try:
            if parse_version(app_version) < parse_version(self.MIN_APP_VERSION):
                from rest_framework.response import Response
                return Response(
                    {
                        'error': 'App version too old',
                        'min_version': self.MIN_APP_VERSION,
                        'download_url': 'https://apps.example.com',
                    },
                    status=426,   # Upgrade Required
                )
        except Exception:
            pass
        return super().dispatch(request, *args, **kwargs)


# ==========================================================================
# 13. TESTING VERSIONED ENDPOINTS
# ==========================================================================

"""
# tests/test_versioning.py

from rest_framework.test import APITestCase


class VersionedAPITests(APITestCase):
    def test_v1_serializer_fields(self):
        response = self.client.get('/api/v1/users/1/')
        self.assertEqual(set(response.data.keys()), {'id', 'username', 'email'})

    def test_v2_includes_profile(self):
        response = self.client.get('/api/v2/users/1/')
        self.assertIn('profile', response.data)
        self.assertIn('email_verified', response.data)

    def test_v1_deprecation_header(self):
        response = self.client.get('/api/v1/users/')
        self.assertEqual(response['Deprecation'], 'true')
        self.assertIn('Sunset', response)

    def test_unknown_version_404(self):
        response = self.client.get('/api/v99/users/')
        self.assertEqual(response.status_code, 404)
"""


# ==========================================================================
# 14. DEPRECATION ROLLOUT PLAN
# ==========================================================================

ROLLOUT_PLAN = """
Sample timeline for v1 → v2 migration:

T+0   : Release v2 alongside v1. Both serve traffic.
T+1m  : Begin monitoring v1 vs v2 usage per endpoint.
T+2m  : Add Deprecation header on v1 responses.
T+3m  : Email partners using v1, share migration docs.
T+6m  : Reduce v1 rate limits to discourage continued use.
T+9m  : Final warning email to remaining v1 users.
T+12m : Sunset v1 — return 410 Gone for v1 endpoints.
T+13m : Remove v1 code from codebase.

Sunset header MUST be set N months before actual removal.
"""
