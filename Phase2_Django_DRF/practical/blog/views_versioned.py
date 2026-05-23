"""
API Versioning — Practical Examples
═══════════════════════════════════════════════════════════════
Setup in settings.py:

    REST_FRAMEWORK = {
        "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.URLPathVersioning",
        "DEFAULT_VERSION": "v1",
        "ALLOWED_VERSIONS": ["v1", "v2"],
    }

URL setup in config/urls.py:

    urlpatterns = [
        path("api/<str:version>/blog/", include("blog.urls")),
    ]

INTERVIEW: API Versioning kyu zaruri hai?
  - Breaking changes without breaking existing clients
  - Different response shapes for different client versions
  - Deprecate old API gracefully
  - Mobile apps update slowly — v1 must work for months after v2 ships

INTERVIEW: Kab version bump karte hain?
  - Field rename, field removal (BREAKING)
  - Response structure change (BREAKING)
  - New required field (BREAKING)
  - Adding optional field = NOT breaking (backwards compatible)
"""

from rest_framework import viewsets, serializers, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly

from .models import Post
from .serializers import PostListSerializer


# ─── V2 Serializer (new fields, different structure) ──────

class PostListSerializerV2(PostListSerializer):
    """
    V2: Added reading_time_label, removed deprecated views_count,
    restructured author as {id, name, avatar_url}.
    """
    reading_time_label = serializers.SerializerMethodField()
    engagement_score   = serializers.SerializerMethodField()

    class Meta(PostListSerializer.Meta):
        # V2 adds new fields, restructures some
        fields = [
            "id", "title", "slug", "excerpt",
            "author", "category", "tags",
            "status", "is_featured", "published_at",
            "likes_count", "read_time_minutes",   # views_count REMOVED in v2
            "reading_time_label", "engagement_score",
            "comment_count", "created_at",
        ]

    def get_reading_time_label(self, obj) -> str:
        return f"{obj.read_time_minutes} min read"

    def get_engagement_score(self, obj) -> float:
        """New computed metric in v2."""
        return round(
            (obj.likes_count * 2 + getattr(obj, "comment_count", 0)) /
            max(obj.views_count, 1) * 100, 2
        )


# ─── Versioned ViewSet ────────────────────────────────────

class VersionedPostViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Demonstrates version-aware ViewSet.

    GET /api/v1/blog/posts/ → PostListSerializer (v1 format)
    GET /api/v2/blog/posts/ → PostListSerializerV2 (v2 format, new fields)

    INTERVIEW: Versioning strategies:
      1. Single ViewSet, different serializer per version (this example)
      2. Separate ViewSet classes per version (clean, more files)
      3. Separate app/module per version (full isolation, most work)
    """
    permission_classes = [IsAuthenticatedOrReadOnly]
    search_fields      = ["title", "excerpt"]

    def get_queryset(self):
        return Post.objects.published().with_all_relations().with_comment_count()

    def get_serializer_class(self):
        """
        INTERVIEW: request.version kahan se aata hai?
          URLPathVersioning: URL pattern mein <str:version> se
          AcceptHeaderVersioning: Accept header se
          NamespaceVersioning: URL namespace se
        """
        version = self.request.version
        if version == "v2":
            return PostListSerializerV2
        return PostListSerializer  # v1 (default)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)

        # V2 wraps differently
        if request.version == "v2":
            return Response({
                "version": "v2",
                "count":   queryset.count(),
                "posts":   serializer.data,   # "posts" key in v2, "results" in v1
            })

        return Response({"success": True, "data": serializer.data})

    def retrieve(self, request, *args, **kwargs):
        instance   = self.get_object()
        serializer = self.get_serializer(instance)

        if request.version == "v2":
            # V2 adds deprecation warning if accessing old endpoint
            response = Response({
                "version": "v2",
                "post": serializer.data,
            })
            response["Sunset"] = "2025-12-31"  # deprecation date
            response["Deprecation"] = "true"
            return response

        return Response({"success": True, "data": serializer.data})


# ─── Deprecation Header Helper ────────────────────────────

class DeprecationMixin:
    """
    Mixin to add deprecation headers to old API versions.
    Warns clients that they should upgrade.
    """
    deprecated_versions: dict[str, str] = {}  # {"v1": "2025-12-31"}

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        sunset_date = self.deprecated_versions.get(request.version)
        if sunset_date:
            response["Deprecation"] = "true"
            response["Sunset"]      = sunset_date
            response["Link"]        = '<https://api.myapp.com/docs/migration>; rel="deprecation"'
        return response
