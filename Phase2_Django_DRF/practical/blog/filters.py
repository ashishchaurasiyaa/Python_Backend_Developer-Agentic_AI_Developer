"""
django-filter FilterSet for Blog Posts
══════════════════════════════════════════
INTERVIEW: DRF ka SearchFilter vs django-filter fark?
  SearchFilter:
    ?search=keyword — simple text search across defined fields
    Uses ILIKE/LIKE — all `search_fields` mein check karta hai

  OrderingFilter:
    ?ordering=-created_at,title — column-based sorting
    Only allowed fields se sort hoga (ordering_fields)

  DjangoFilterBackend (django-filter):
    ?status=published&category=python&author=5
    Exact field matching, range filters, custom lookups
    FilterSet class mein define karo — most flexible

INTERVIEW: CharFilter vs NumberFilter vs DateFilter?
  CharField, IntegerField, DateField wali filtering ke liye respectively.
  lookup_expr:
    'exact'      → WHERE status = 'published'
    'icontains'  → WHERE title ILIKE '%django%'
    'gte'        → WHERE views >= 100
    'date'       → WHERE DATE(created_at) = '2024-01-15'
"""

import django_filters
from django.db.models import Q
from .models import Post, Category, Tag


class PostFilter(django_filters.FilterSet):
    """
    Filter posts with multiple criteria.

    Usage:
      GET /api/v1/blog/posts/?status=published&category_slug=python&min_views=100
      GET /api/v1/blog/posts/?search=django&tags=python,web&ordering=-created_at
    """

    # Status filter
    status = django_filters.ChoiceFilter(choices=Post.Status.choices)

    # Category — by slug or id
    category_slug = django_filters.CharFilter(
        field_name="category__slug", lookup_expr="exact"
    )
    category_id = django_filters.NumberFilter(field_name="category__id")

    # Tag filter — multiple tags (OR)
    tags = django_filters.ModelMultipleChoiceFilter(
        field_name="tags__slug",
        to_field_name="slug",
        queryset=Tag.objects.all(),
        conjoined=False,  # OR logic (any of these tags)
    )

    # Author
    author_id = django_filters.NumberFilter(field_name="author__id")

    # View count range
    min_views = django_filters.NumberFilter(field_name="views_count", lookup_expr="gte")
    max_views = django_filters.NumberFilter(field_name="views_count", lookup_expr="lte")

    # Date range
    published_after  = django_filters.DateTimeFilter(
        field_name="published_at", lookup_expr="gte"
    )
    published_before = django_filters.DateTimeFilter(
        field_name="published_at", lookup_expr="lte"
    )

    # Featured filter
    is_featured = django_filters.BooleanFilter()

    # Full-text search across title + content + excerpt
    q = django_filters.CharFilter(method="filter_search", label="Full-text search")

    def filter_search(self, queryset, name, value):
        """Custom multi-field search."""
        return queryset.filter(
            Q(title__icontains=value) |
            Q(content__icontains=value) |
            Q(excerpt__icontains=value)
        ).distinct()

    class Meta:
        model  = Post
        fields = ["status", "is_featured", "author_id"]
