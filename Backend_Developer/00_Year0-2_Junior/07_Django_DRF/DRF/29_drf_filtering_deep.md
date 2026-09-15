# DRF Filtering Deep — django-filter, Search, Ordering

## Why It Matters

Listing APIs need filtering: `/api/articles/?status=published&author=5&search=python`. DRF's basic filtering = limited. Production needs:
- **django-filter** for query-param mapping
- **SearchFilter** for full-text search
- **OrderingFilter** for sorting
- **Custom filter backends** for complex logic

Senior interview: "Build a flexible article search API." → FilterSet + SearchFilter + custom filters.

---

## Core Concepts

### django-filter Setup

```python
# pip install django-filter
INSTALLED_APPS += ['django_filters']


# settings.py
REST_FRAMEWORK = {
    'DEFAULT_FILTER_BACKENDS': ['django_filters.rest_framework.DjangoFilterBackend'],
}
```

### Basic FilterSet

```python
# filters.py
import django_filters
from blog.models import Article


class ArticleFilter(django_filters.FilterSet):
    class Meta:
        model = Article
        fields = {
            'status': ['exact', 'in'],
            'author': ['exact'],
            'created_at': ['gte', 'lte', 'date'],
            'view_count': ['gte', 'lte'],
        }


# views.py
class ArticleListView(generics.ListAPIView):
    queryset = Article.objects.all()
    serializer_class = ArticleSerializer
    filterset_class = ArticleFilter


# URL params
# ?status=published
# ?status__in=published,draft
# ?author=5
# ?created_at__gte=2026-01-01&created_at__lte=2026-06-01
# ?view_count__gte=1000
```

### Custom Filter Fields

```python
class ArticleFilter(django_filters.FilterSet):
    # Custom field
    q = django_filters.CharFilter(method='filter_search')
    tags = django_filters.CharFilter(method='filter_tags')
    min_words = django_filters.NumberFilter(field_name='word_count', lookup_expr='gte')

    # Range
    published_between = django_filters.DateFromToRangeFilter(field_name='published_at')

    # Choice (constrain values)
    status = django_filters.ChoiceFilter(choices=[
        ('draft', 'Draft'), ('published', 'Published'), ('archived', 'Archived')
    ])

    # Boolean
    has_comments = django_filters.BooleanFilter(method='filter_has_comments')

    # Multiple
    author = django_filters.NumberFilter(field_name='author_id')
    author_in = django_filters.BaseInFilter(field_name='author_id')

    class Meta:
        model = Article
        fields = ['status', 'author', 'tags']

    def filter_search(self, queryset, name, value):
        from django.db.models import Q
        return queryset.filter(
            Q(title__icontains=value) |
            Q(body__icontains=value) |
            Q(tags__name__icontains=value)
        ).distinct()

    def filter_tags(self, queryset, name, value):
        # Comma-separated tags — match ALL (AND)
        tags = [t.strip() for t in value.split(',') if t.strip()]
        for tag in tags:
            queryset = queryset.filter(tags__name__iexact=tag)
        return queryset.distinct()

    def filter_has_comments(self, queryset, name, value):
        if value:
            return queryset.annotate(c=Count('comments')).filter(c__gt=0)
        return queryset.annotate(c=Count('comments')).filter(c=0)
```

URLs:
- `?q=python` — full-text search
- `?tags=python,django` — articles with BOTH tags
- `?min_words=500` — at least 500 words
- `?published_between_after=2026-01-01&published_between_before=2026-06-01`
- `?has_comments=true`
- `?author_in=1,2,3` — multiple authors

### SearchFilter

```python
from rest_framework.filters import SearchFilter


class ArticleListView(generics.ListAPIView):
    queryset = Article.objects.all()
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_class = ArticleFilter
    search_fields = ['title', 'body', '@title']  # @ = PostgreSQL full-text
    # Modifiers:
    # ^ — starts-with
    # = — exact
    # @ — full-text (PostgreSQL)
    # $ — regex
```

`?search=python` — searches all `search_fields`.

### OrderingFilter

```python
from rest_framework.filters import OrderingFilter


class ArticleListView(generics.ListAPIView):
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering_fields = ['created_at', 'view_count', 'title']
    ordering = ['-created_at']    # default ordering
```

`?ordering=-view_count` — descending by view count.

### Combined Backends Pattern

```python
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend


class ArticleListView(generics.ListAPIView):
    queryset = Article.objects.select_related('author').prefetch_related('tags')
    serializer_class = ArticleSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]

    filterset_class = ArticleFilter
    search_fields = ['title', 'body']
    ordering_fields = ['created_at', 'view_count', 'title']
    ordering = ['-created_at']
```

### Custom FilterBackend (advanced)

```python
from rest_framework.filters import BaseFilterBackend


class TenantFilterBackend(BaseFilterBackend):
    """Auto-filter all queries by current tenant."""

    def filter_queryset(self, request, queryset, view):
        if hasattr(request, 'tenant') and request.tenant:
            return queryset.filter(tenant=request.tenant)
        return queryset


# settings.py
REST_FRAMEWORK = {
    'DEFAULT_FILTER_BACKENDS': [
        'myapp.filters.TenantFilterBackend',
        'django_filters.rest_framework.DjangoFilterBackend',
    ],
}
```

### Filter with Annotations

```python
class ArticleFilter(django_filters.FilterSet):
    min_comments = django_filters.NumberFilter(method='filter_min_comments')

    def filter_min_comments(self, queryset, name, value):
        from django.db.models import Count
        return queryset.annotate(
            comment_count=Count('comments')
        ).filter(comment_count__gte=value)


# ?min_comments=10 → articles with >= 10 comments
```

### PostgreSQL Full-Text Search

```python
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank


class ArticleFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method='filter_full_text')

    def filter_full_text(self, queryset, name, value):
        query = SearchQuery(value, search_type='websearch')
        return queryset.annotate(
            search=SearchVector('title', weight='A') + SearchVector('body', weight='B'),
            rank=SearchRank(F('search'), query),
        ).filter(search=query).order_by('-rank')
```

For best performance, store `search` as `SearchVectorField` + GIN index.

### Pagination + Filtering

```python
from rest_framework.pagination import CursorPagination


class ArticleCursorPagination(CursorPagination):
    ordering = '-created_at'
    page_size = 20
    max_page_size = 100


class ArticleListView(generics.ListAPIView):
    pagination_class = ArticleCursorPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]
    # ... etc
```

Cursor pagination = consistent for infinite scroll, doesn't slow on deep pages.

### Filter UI in Browsable API

django-filter auto-renders form for filtering in DRF browsable API. Helpful for development.

### OpenAPI Schema with Filters

`drf-spectacular` auto-includes filter params in OpenAPI:

```python
INSTALLED_APPS += ['drf_spectacular']
REST_FRAMEWORK['DEFAULT_SCHEMA_CLASS'] = 'drf_spectacular.openapi.AutoSchema'
```

Filter params appear in /api/schema/ + Swagger UI.

---

## Common Pitfalls

### 1. N+1 from Filter Methods

```python
def filter_has_tag(self, queryset, name, value):
    return queryset.filter(tags__name=value)
```

`tags__name` JOIN may cause duplicates → use `.distinct()`.

### 2. SQL Injection via Custom Filter

```python
def filter_search(self, queryset, name, value):
    return queryset.extra(where=[f"title LIKE '%{value}%'"])  # DANGER
```

Use ORM-safe `__icontains` or parameterized raw.

### 3. Unbounded Pagination

```python
class MyPagination(PageNumberPagination):
    page_size_query_param = 'page_size'   # ?page_size=100000
```

Set `max_page_size`. Else attacker can request huge pages → OOM.

### 4. Filter on Non-Indexed Column

```python
ArticleFilter.fields = ['body']   # body has no index
```

Slow on large tables. Either index it (`text_search` field) or restrict filterable fields.

### 5. SearchFilter on Text Without Full-Text Index

```python
search_fields = ['body']   # uses ILIKE %x% → seq scan
```

For real search, use PostgreSQL `@` prefix + GIN index on tsvector.

### 6. Default Ordering Inconsistent

Without explicit `ordering = ['-id']`, pagination may show same item twice across pages.

---

## Interview Q&A

**Q1:** django-filter setup + usage?
**A:** Install `django-filter`, add `DjangoFilterBackend` to DEFAULT_FILTER_BACKENDS. Define `FilterSet` class with model + fields. Attach to view via `filterset_class`. URL params map to filters: `?status=published&author=5`. Supports lookup expressions (`__gte`, `__in`, `__icontains`).

**Q2:** Search across multiple fields?
**A:** `SearchFilter` with `search_fields = ['title', 'body']` → `?search=X` does ILIKE %X% across both. For PostgreSQL full-text, prefix `@` (e.g., `@title`) — uses tsvector. For real performance, dedicated SearchVectorField + GIN index.

**Q3:** Custom filter method example?
**A:**
```python
q = django_filters.CharFilter(method='filter_full')

def filter_full(self, qs, name, value):
    return qs.filter(Q(title__icontains=value) | Q(body__icontains=value)).distinct()
```
`method` references a method on FilterSet that returns filtered queryset.

**Q4:** Pagination + ordering combo issue?
**A:** Without explicit consistent ordering (e.g., `ordering = ['-created_at', 'pk']`), pagination is unreliable — page 2 may overlap page 1. Always include unique field (PK) in ordering chain.

**Q5:** Cursor vs page pagination?
**A:** PageNumberPagination: `?page=42` — slow on deep pages (OFFSET). CursorPagination: opaque cursor based on ordering field — fast at any depth. Cursor better for infinite scroll, page for "go to page 5" UX. Cursor pagination requires consistent strict ordering.

**Q6:** Tenant filtering globally?
**A:** Custom `BaseFilterBackend` — applies `queryset.filter(tenant=request.tenant)` automatically. Add to `DEFAULT_FILTER_BACKENDS`. Or override `get_queryset()` per view. Backend approach = DRY across all views.

**Q7:** OpenAPI docs reflect filters automatically?
**A:** Yes — `drf-spectacular` + django-filter integration auto-includes filter params in schema. Visible in Swagger UI. For custom filter methods, add `help_text` or use `@extend_schema_field` for type info.

**Q8:** Filter performance — slow API endpoint debug?
**A:** Check: (1) Indexes on filtered columns. (2) `select_related`/`prefetch_related` for serializer fields. (3) `EXPLAIN ANALYZE` the generated SQL (`print(queryset.query)`). (4) Pagination — using cursor not OFFSET. (5) Filter on annotations forces aggregation per request — cache or denormalize.

---

## Real-World Use Cases

### 1. E-commerce Product Listing

```python
class ProductFilter(django_filters.FilterSet):
    category = django_filters.CharFilter(field_name='category__slug')
    min_price = django_filters.NumberFilter(field_name='price', lookup_expr='gte')
    max_price = django_filters.NumberFilter(field_name='price', lookup_expr='lte')
    on_sale = django_filters.BooleanFilter(method='filter_on_sale')
    in_stock = django_filters.BooleanFilter(method='filter_in_stock')

    def filter_on_sale(self, qs, name, value):
        return qs.filter(discount__gt=0) if value else qs.filter(discount=0)


# ?category=electronics&min_price=100&max_price=500&on_sale=true
```

### 2. Multi-Tenant Admin Search

```python
filter_backends = [TenantFilterBackend, SearchFilter, OrderingFilter]
search_fields = ['email', 'name']
ordering_fields = ['created_at', 'last_login']
```

### 3. Date Range Reports

```python
class OrderFilter(django_filters.FilterSet):
    date_range = django_filters.DateFromToRangeFilter(field_name='created_at')


# ?date_range_after=2026-01-01&date_range_before=2026-01-31
```

---

## References

- [django-filter docs](https://django-filter.readthedocs.io/)
- [DRF filtering](https://www.django-rest-framework.org/api-guide/filtering/)
- [PostgreSQL full-text search Django](https://docs.djangoproject.com/en/5.0/ref/contrib/postgres/search/)
- drf-spectacular for OpenAPI
