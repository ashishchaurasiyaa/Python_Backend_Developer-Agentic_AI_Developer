"""
QuerySet Internals — Production Patterns
"""

from django.db.models import F, Q, Subquery, OuterRef, Count, Sum, Avg, Window
from django.db.models.functions import Rank, RowNumber, DenseRank, Lag, Lead
from django.db import connection
from django.test.utils import CaptureQueriesContext


# ==========================================================================
# 1. LAZY EVALUATION DEMO
# ==========================================================================

"""
from blog.models import Article


# These chain WITHOUT SQL
qs = Article.objects.filter(status='published')
qs = qs.filter(author_id=1)
qs = qs.order_by('-created_at')

# SQL fires here
articles = list(qs)
"""


# ==========================================================================
# 2. INSPECT GENERATED SQL
# ==========================================================================

def show_query(queryset):
    print(queryset.query)


def show_explain(queryset):
    print(queryset.explain(analyze=True, buffers=True))


def show_queries_for_block():
    """Capture SQL fired in a block."""
    with CaptureQueriesContext(connection) as ctx:
        # Your code
        # qs = Article.objects.filter(...)
        # list(qs)
        pass
    for q in ctx.captured_queries:
        print(f"[{q['time']}s] {q['sql'][:200]}")


# ==========================================================================
# 3. CACHE BEHAVIOR
# ==========================================================================

"""
qs = Article.objects.filter(status='published')

# First iteration — SQL fires + caches
articles = list(qs)

# Second — cache used, no SQL
articles_again = list(qs)


# count() bypasses cache
qs.count()   # ALWAYS new SQL


# Recreate to refresh
qs = Article.objects.filter(status='published')   # new qs, will refetch
"""


# ==========================================================================
# 4. EFFICIENT EXISTS CHECK
# ==========================================================================

"""
# BAD — may eval full queryset
if Article.objects.filter(...):
    ...

# GOOD — SELECT 1 LIMIT 1
if Article.objects.filter(...).exists():
    ...

# For counting
qs.count()      # SELECT COUNT(*)
len(list(qs))   # full materialization — bad

# For "any matching?"
qs.exists()     # SELECT 1 LIMIT 1 — fastest
"""


# ==========================================================================
# 5. STREAMING LARGE QUERIES (iterator)
# ==========================================================================

"""
# Memory-efficient — server-side cursor on PostgreSQL
for article in Article.objects.iterator(chunk_size=1000):
    process(article)
    # Each chunk fetched lazily; no caching


# values_list with iterator = ultra-light
for pk, title in Article.objects.values_list('id', 'title').iterator(chunk_size=5000):
    write_to_csv(pk, title)


# Cursor pagination pattern
def paginate_all(model, batch_size=1000):
    last_pk = 0
    while True:
        batch = list(
            model.objects
            .filter(pk__gt=last_pk)
            .order_by('pk')
            .values_list('pk', flat=True)[:batch_size]
        )
        if not batch:
            break
        yield from model.objects.filter(pk__in=batch).iterator()
        last_pk = batch[-1]
"""


# ==========================================================================
# 6. select_related + prefetch_related
# ==========================================================================

"""
# Forward FK / OneToOne — JOIN
qs = Article.objects.select_related('author', 'category')


# Multi-level
qs = Article.objects.select_related('author__profile')


# M2M / reverse FK — separate query
qs = Article.objects.prefetch_related('tags', 'comments')


# Combined
qs = (
    Article.objects
    .select_related('author', 'category')
    .prefetch_related('tags', 'comments')
)


# Filtered prefetch
from django.db.models import Prefetch


qs = Article.objects.prefetch_related(
    Prefetch(
        'comments',
        queryset=Comment.objects.filter(approved=True).order_by('-created_at')[:5],
        to_attr='top_comments',
    )
)


# Multiple prefetches with different filters
qs = Article.objects.prefetch_related(
    Prefetch('comments', queryset=Comment.objects.filter(approved=True), to_attr='approved_comments'),
    Prefetch('comments', queryset=Comment.objects.filter(approved=False), to_attr='pending_comments'),
)
"""


# ==========================================================================
# 7. DEFER / ONLY (column selection)
# ==========================================================================

"""
# Load only specific fields
articles = Article.objects.only('id', 'title', 'author_id').select_related('author')


# Exclude heavy column
articles = Article.objects.defer('body')


# Pitfall: accessing deferred field triggers extra query
for a in Article.objects.only('id', 'title'):
    print(a.title)   # OK
    print(a.body)    # Extra query per article (N+1!)
"""


# ==========================================================================
# 8. F EXPRESSIONS (atomic DB ops)
# ==========================================================================

"""
# Atomic increment (race-free)
Article.objects.filter(pk=1).update(view_count=F('view_count') + 1)


# Compare fields
Article.objects.filter(updated_at__gt=F('created_at'))


# Annotate computed
Article.objects.annotate(
    score=F('likes') * 2 + F('comments_count') - F('downvotes')
)


# Update with reference to other field
Order.objects.filter(...).update(
    total=F('subtotal') + F('tax') - F('discount'),
)


# F in filter
from django.db.models import ExpressionWrapper, FloatField


qs = Order.objects.annotate(
    discount_pct=ExpressionWrapper(
        F('discount') * 100.0 / F('subtotal'),
        output_field=FloatField(),
    )
).filter(discount_pct__gte=10)
"""


# ==========================================================================
# 9. Q OBJECTS (complex queries)
# ==========================================================================

"""
# OR
Article.objects.filter(Q(status='published') | Q(featured=True))


# AND (default for chained filters)
Article.objects.filter(Q(status='published') & Q(author=user))


# NOT
Article.objects.filter(~Q(status='draft'))


# Nested
Article.objects.filter(
    Q(status='published') &
    (Q(category='tech') | Q(category='science')) &
    ~Q(is_draft=True)
)


# Dynamic Q building
from functools import reduce
import operator


search_terms = ['python', 'django', 'web']
q = reduce(operator.or_, (Q(title__icontains=t) for t in search_terms))
Article.objects.filter(q)
"""


# ==========================================================================
# 10. AGGREGATION + ANNOTATION
# ==========================================================================

"""
# Aggregate over whole queryset (returns dict)
stats = Order.objects.aggregate(
    total=Sum('amount'),
    count=Count('id'),
    avg=Avg('amount'),
)
# {'total': Decimal('99999.99'), 'count': 1234, 'avg': Decimal('81.04')}


# Annotate per-row
Article.objects.annotate(
    comment_count=Count('comments'),
    total_views=Sum('view_count'),    # only makes sense in group_by
)


# GROUP BY (via values + annotate)
Article.objects.values('category').annotate(
    count=Count('id'),
    total_views=Sum('view_count'),
)
# [{category: 'tech', count: 100, total_views: 10000}, ...]


# Conditional aggregation
Article.objects.aggregate(
    published_count=Count('id', filter=Q(status='published')),
    draft_count=Count('id', filter=Q(status='draft')),
)
"""


# ==========================================================================
# 11. SUBQUERY + OUTERREF
# ==========================================================================

"""
# Each article with body of latest comment
latest_comment = Comment.objects.filter(
    article=OuterRef('pk')
).order_by('-created_at').values('body')[:1]


Article.objects.annotate(
    latest_comment=Subquery(latest_comment)
)


# Count via subquery (avoid JOIN fanout)
comment_count = Comment.objects.filter(
    article=OuterRef('pk'),
    approved=True,
).values('article').annotate(c=Count('*')).values('c')


Article.objects.annotate(comment_count=Subquery(comment_count))


# Exists() subquery
from django.db.models import Exists


Article.objects.annotate(
    has_comments=Exists(
        Comment.objects.filter(article=OuterRef('pk'))
    )
).filter(has_comments=True)
"""


# ==========================================================================
# 12. WINDOW FUNCTIONS (Django 4+)
# ==========================================================================

"""
# Rank articles by views within each category
Article.objects.annotate(
    rank_in_category=Window(
        expression=Rank(),
        partition_by=[F('category')],
        order_by=F('view_count').desc(),
    )
)


# Row number
Article.objects.annotate(
    row=Window(expression=RowNumber(), partition_by=[F('category')], order_by=F('view_count').desc())
)


# Lag (compare to previous row)
qs = Order.objects.annotate(
    prev_amount=Window(
        expression=Lag('amount'),
        partition_by=[F('user_id')],
        order_by=F('created_at'),
    )
)
# Now qs has each order with previous order's amount for same user


# Top N per group (window in subquery)
top_3_per_cat = (
    Article.objects
    .annotate(rn=Window(
        expression=RowNumber(),
        partition_by=[F('category')],
        order_by=F('view_count').desc(),
    ))
)
# Filter via outer query (Django doesn't support filter on window directly)
"""


# ==========================================================================
# 13. BULK OPERATIONS
# ==========================================================================

"""
# bulk_create — single INSERT
new_articles = [Article(title=f'T{i}') for i in range(1000)]
Article.objects.bulk_create(new_articles, batch_size=500)


# With conflict handling (Django 4.1+)
Article.objects.bulk_create(
    new_articles,
    batch_size=500,
    update_conflicts=True,
    update_fields=['title'],
    unique_fields=['slug'],
)


# bulk_update — multiple UPDATEs
articles = list(Article.objects.filter(status='draft'))
for a in articles:
    a.status = 'pending'
Article.objects.bulk_update(articles, ['status'], batch_size=500)


# Direct update (single UPDATE)
Article.objects.filter(status='draft').update(status='pending')


# update() vs save() — update doesn't fire signals + no save() override
"""


# ==========================================================================
# 14. in_bulk (efficient lookup by PKs)
# ==========================================================================

"""
# BAD — N queries
for pk in ids:
    article = Article.objects.get(pk=pk)
    process(article)


# GOOD — 1 query, returns dict
articles = Article.objects.in_bulk(ids)
# {1: <Article 1>, 2: <Article 2>, ...}


for pk in ids:
    article = articles.get(pk)
    if article:
        process(article)


# in_bulk on non-PK field
articles = Article.objects.in_bulk(['slug-1', 'slug-2'], field_name='slug')
"""


# ==========================================================================
# 15. RAW SQL escape hatch
# ==========================================================================

"""
# When ORM not expressive enough
articles = Article.objects.raw(
    "SELECT * FROM blog_article WHERE complex_logic = %s",
    [param_value],
)
for a in articles:
    print(a.title)


# Lower level
from django.db import connection


with connection.cursor() as c:
    c.execute("SELECT id, title FROM blog_article WHERE views > %s", [1000])
    for row in c.fetchall():
        print(row)


# Dictfetchall
def dictfetchall(cursor):
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


with connection.cursor() as c:
    c.execute("SELECT id, title FROM blog_article LIMIT 10")
    rows = dictfetchall(c)
"""


# ==========================================================================
# 16. APPROXIMATE COUNT for large tables
# ==========================================================================

def fast_approximate_count(table_name):
    """PostgreSQL approximate count via pg_class.reltuples."""
    with connection.cursor() as c:
        c.execute(
            "SELECT reltuples::bigint AS estimate FROM pg_class WHERE relname=%s",
            [table_name],
        )
        return c.fetchone()[0]


# Use:
# total = fast_approximate_count('blog_article')   # instant, approximate
# Use for pagination "X of millions" displays


# ==========================================================================
# 17. ASSERT NUM QUERIES (test for N+1)
# ==========================================================================

"""
from django.test import TestCase


class N1Tests(TestCase):
    def test_list_uses_expected_queries(self):
        with self.assertNumQueries(2):  # 1 main + 1 prefetch
            articles = list(
                Article.objects.select_related('author').prefetch_related('tags')
            )
            for a in articles:
                _ = a.author.username
                _ = list(a.tags.all())


    def test_endpoint_query_count(self):
        with self.assertNumQueries(5):  # auth + articles + ...
            response = self.client.get('/api/articles/')
"""


# ==========================================================================
# 18. EXTRA / Custom WHERE (last resort)
# ==========================================================================

# Use sparingly — prefer ORM
# Article.objects.extra(
#     where=["title ~ %s"],
#     params=[r'^\w+'],
# )

# Better with annotations:
# from django.db.models import F, Func, Value
# Article.objects.annotate(matches=Func(F('title'), Value(r'^\w+'), function='regexp_match'))
