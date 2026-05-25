"""
DRF Filtering Deep — Production Patterns
"""

import django_filters
from django.db.models import Q, Count, F
from rest_framework import generics, serializers
from rest_framework.filters import SearchFilter, OrderingFilter, BaseFilterBackend
from django_filters.rest_framework import DjangoFilterBackend


# ==========================================================================
# 1. BASIC FILTERSET
# ==========================================================================

# from blog.models import Article


class ArticleBasicFilter(django_filters.FilterSet):
    """Auto-generated filters from Meta.fields dict."""

    class Meta:
        # model = Article
        fields = {
            'status': ['exact', 'in'],
            'author': ['exact'],
            'created_at': ['gte', 'lte', 'date'],
            'view_count': ['gte', 'lte', 'exact'],
            'title': ['exact', 'icontains'],
        }


# URLs supported:
# ?status=published
# ?status__in=published,draft
# ?created_at__gte=2026-01-01&created_at__lte=2026-12-31
# ?view_count__gte=1000
# ?title__icontains=python


# ==========================================================================
# 2. CUSTOM FILTER FIELDS
# ==========================================================================

class ArticleAdvancedFilter(django_filters.FilterSet):
    # Search across multiple fields
    q = django_filters.CharFilter(method='filter_search')

    # Tags (CSV → AND match)
    tags = django_filters.CharFilter(method='filter_tags_all')

    # Tags (CSV → OR match)
    tags_any = django_filters.CharFilter(method='filter_tags_any')

    # Range
    min_words = django_filters.NumberFilter(field_name='word_count', lookup_expr='gte')
    max_words = django_filters.NumberFilter(field_name='word_count', lookup_expr='lte')
    published_between = django_filters.DateFromToRangeFilter(field_name='published_at')

    # Choice (constrain)
    status = django_filters.ChoiceFilter(choices=[
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    ])

    # Boolean from computed field
    has_comments = django_filters.BooleanFilter(method='filter_has_comments')
    is_popular = django_filters.BooleanFilter(method='filter_popular')

    # Multiple (IN)
    author_in = django_filters.BaseInFilter(field_name='author_id')
    category_in = django_filters.BaseInFilter(field_name='category__slug')

    # Annotations-based filter
    min_comments = django_filters.NumberFilter(method='filter_min_comments')
    min_reactions = django_filters.NumberFilter(method='filter_min_reactions')

    class Meta:
        # model = Article
        fields = ['status', 'author']

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(title__icontains=value) |
            Q(body__icontains=value) |
            Q(author__username__icontains=value)
        ).distinct()

    def filter_tags_all(self, queryset, name, value):
        tags = [t.strip() for t in value.split(',') if t.strip()]
        for tag in tags:
            queryset = queryset.filter(tags__name__iexact=tag)
        return queryset.distinct()

    def filter_tags_any(self, queryset, name, value):
        tags = [t.strip() for t in value.split(',') if t.strip()]
        return queryset.filter(tags__name__iexact__in=tags).distinct()

    def filter_has_comments(self, queryset, name, value):
        queryset = queryset.annotate(cnt=Count('comments'))
        return queryset.filter(cnt__gt=0) if value else queryset.filter(cnt=0)

    def filter_popular(self, queryset, name, value):
        if value:
            return queryset.filter(view_count__gte=1000)
        return queryset.filter(view_count__lt=1000)

    def filter_min_comments(self, queryset, name, value):
        return queryset.annotate(cnt=Count('comments')).filter(cnt__gte=value)

    def filter_min_reactions(self, queryset, name, value):
        return queryset.annotate(rxn=Count('reactions')).filter(rxn__gte=value)


# ==========================================================================
# 3. VIEW WITH ALL BACKENDS
# ==========================================================================

# class ArticleListView(generics.ListAPIView):
#     queryset = (
#         Article.objects
#         .select_related('author', 'category')
#         .prefetch_related('tags', 'comments')
#     )
#     serializer_class = ArticleSerializer
#
#     filter_backends = [
#         DjangoFilterBackend,
#         SearchFilter,
#         OrderingFilter,
#     ]
#     filterset_class = ArticleAdvancedFilter
#     search_fields = ['title', 'body', 'author__username']
#     ordering_fields = ['created_at', 'view_count', 'title', 'word_count']
#     ordering = ['-created_at']    # default


# ==========================================================================
# 4. TENANT FILTER BACKEND (auto-applied globally)
# ==========================================================================

class TenantFilterBackend(BaseFilterBackend):
    """Filter all queries by current tenant from request."""

    def filter_queryset(self, request, queryset, view):
        tenant = getattr(request, 'tenant', None) or getattr(request.user, 'tenant', None)
        if tenant is None:
            return queryset.none()   # safe default
        if hasattr(queryset.model, 'tenant_id'):
            return queryset.filter(tenant=tenant)
        return queryset


# settings.py
# REST_FRAMEWORK = {
#     'DEFAULT_FILTER_BACKENDS': [
#         'myapp.filters.TenantFilterBackend',
#         'django_filters.rest_framework.DjangoFilterBackend',
#         'rest_framework.filters.SearchFilter',
#         'rest_framework.filters.OrderingFilter',
#     ],
# }


# ==========================================================================
# 5. SOFT-DELETE FILTER BACKEND
# ==========================================================================

class SoftDeleteFilterBackend(BaseFilterBackend):
    """Exclude soft-deleted by default. Admin can opt-in via ?include_deleted=1"""

    def filter_queryset(self, request, queryset, view):
        if not hasattr(queryset.model, 'deleted_at'):
            return queryset

        include_deleted = request.query_params.get('include_deleted') == '1'
        is_staff = getattr(request.user, 'is_staff', False)

        if include_deleted and is_staff:
            return queryset
        return queryset.filter(deleted_at__isnull=True)


# ==========================================================================
# 6. POSTGRESQL FULL-TEXT SEARCH FILTER
# ==========================================================================

from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank


class FullTextSearchFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method='filter_fts')

    class Meta:
        # model = Article
        fields = []

    def filter_fts(self, queryset, name, value):
        """Full-text search using PostgreSQL tsvector + ranking."""
        query = SearchQuery(value, search_type='websearch')
        return queryset.annotate(
            search=SearchVector('title', weight='A') + SearchVector('body', weight='B'),
            rank=SearchRank(F('search'), query),
        ).filter(search=query).order_by('-rank')


# Recommended: persistent SearchVectorField (faster — no annotation per query)
"""
class Article(models.Model):
    title = models.CharField(max_length=200)
    body = models.TextField()
    search_vector = SearchVectorField(null=True)

    class Meta:
        indexes = [
            GinIndex(fields=['search_vector']),
        ]


# Update via signal
@receiver(post_save, sender=Article)
def update_search_vector(sender, instance, **kwargs):
    Article.objects.filter(pk=instance.pk).update(
        search_vector=(
            SearchVector('title', weight='A') +
            SearchVector('body', weight='B')
        )
    )
"""


# ==========================================================================
# 7. CURSOR PAGINATION (consistent for infinite scroll)
# ==========================================================================

from rest_framework.pagination import CursorPagination, PageNumberPagination


class ArticleCursorPagination(CursorPagination):
    ordering = '-created_at'    # must be consistent + unique-ish
    page_size = 20
    max_page_size = 100
    page_size_query_param = 'page_size'
    cursor_query_param = 'cursor'


class ArticlePagePagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100   # ALWAYS set


# ==========================================================================
# 8. ORDERING WITH MULTIPLE FIELDS
# ==========================================================================

# Frontend can request multi-field ordering
# /api/articles/?ordering=-view_count,-created_at

"""
class ArticleListView(generics.ListAPIView):
    filter_backends = [OrderingFilter]
    ordering_fields = ['view_count', 'created_at', 'title']
    ordering = ['-created_at', 'pk']   # default with PK tiebreaker
"""


# ==========================================================================
# 9. CONDITIONAL DEFAULTS
# ==========================================================================

class ArticleFilterWithDefaults(django_filters.FilterSet):
    status = django_filters.CharFilter(method='filter_status')

    def filter_status(self, queryset, name, value):
        # Default to 'published' if not provided
        return queryset.filter(status=value or 'published')

    @property
    def qs(self):
        # Apply default filter for unauthenticated users
        queryset = super().qs
        request = self.request
        if not request.user.is_authenticated:
            queryset = queryset.filter(is_public=True)
        return queryset

    class Meta:
        # model = Article
        fields = ['status']


# ==========================================================================
# 10. FILTERSET FORM CUSTOMIZATION
# ==========================================================================

class CustomArticleFilter(django_filters.FilterSet):
    """Add help text + custom widgets."""

    q = django_filters.CharFilter(
        method='filter_search',
        label='Search',
        help_text='Search in title and body',
    )

    created_at = django_filters.DateFromToRangeFilter(
        label='Created between',
        help_text='Date range (YYYY-MM-DD)',
    )

    class Meta:
        # model = Article
        fields = ['status', 'author']


# ==========================================================================
# 11. CONDITIONAL FILTER (admin sees more options)
# ==========================================================================

class AdminAwareFilter(django_filters.FilterSet):
    class Meta:
        # model = Article
        fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add admin-only filters
        request = getattr(self, 'request', None)
        if request and request.user.is_staff:
            self.filters['author'] = django_filters.NumberFilter(field_name='author_id')
            self.filters['internal_note'] = django_filters.CharFilter(field_name='internal_note', lookup_expr='icontains')


# ==========================================================================
# 12. TESTING FILTERS
# ==========================================================================

"""
# tests/test_filters.py

from rest_framework.test import APITestCase


class ArticleFilterTests(APITestCase):
    def test_filter_by_status(self):
        Article.objects.create(title='X', status='published')
        Article.objects.create(title='Y', status='draft')

        resp = self.client.get('/api/articles/?status=published')
        self.assertEqual(len(resp.data['results']), 1)

    def test_search(self):
        Article.objects.create(title='Python tutorial', body='...')
        Article.objects.create(title='Django guide', body='...')

        resp = self.client.get('/api/articles/?search=python')
        self.assertEqual(len(resp.data['results']), 1)

    def test_ordering(self):
        Article.objects.create(title='A', view_count=100)
        Article.objects.create(title='B', view_count=200)

        resp = self.client.get('/api/articles/?ordering=-view_count')
        self.assertEqual(resp.data['results'][0]['title'], 'B')

    def test_combined(self):
        # Multiple filters + search + ordering
        resp = self.client.get(
            '/api/articles/?status=published&min_words=500&ordering=-created_at'
        )
        # ... assertions
"""
