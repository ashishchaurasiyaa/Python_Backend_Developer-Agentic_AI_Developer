# N+1 Detection — Django Performance Diagnostic

## Why It Matters (Senior 5 YOE Context)

N+1 = **the most common Django perf bug**. ORM makes it stupidly easy to write:

```python
for article in Article.objects.all():
    print(article.author.username)  # 1 query per article — BOOM
```

100 articles = 101 queries instead of 1 or 2. P99 latency explodes.

Senior interviewers love this question because **detection** = real skill, not just knowing `select_related`. You need to:

- Detect N+1 **in CI** (assertNumQueries)
- Detect N+1 **in dev** (debug-toolbar, silk)
- Detect N+1 **in prod** (APM traces, slow query logs)
- Detect N+1 **in code review** (read the loops)

---

## Core Concepts

### Detecting in Tests — `assertNumQueries`

```python
from django.test import TestCase


class ArticleListTests(TestCase):
    def test_list_does_not_n_plus_one(self):
        # Setup
        for i in range(10):
            user = User.objects.create(username=f'u{i}')
            Article.objects.create(title=f'T{i}', author=user)

        # Assert exact query count
        with self.assertNumQueries(2):  # 1 for articles + 1 prefetch
            articles = list(Article.objects.select_related('author'))
            for a in articles:
                _ = a.author.username
```

`assertNumQueries(2)` will fail if queries change. Best practice: lock down view-level query counts.

### `CaptureQueriesContext` for Debugging

```python
from django.test.utils import CaptureQueriesContext
from django.db import connection


def test_what_queries_run():
    with CaptureQueriesContext(connection) as ctx:
        Article.objects.first().author.username

    for q in ctx.captured_queries:
        print(q['sql'])
        print(f'  time: {q["time"]}s')
```

### `django-debug-toolbar` (Dev)

```python
# settings/dev.py
INSTALLED_APPS += ['debug_toolbar']
MIDDLEWARE = ['debug_toolbar.middleware.DebugToolbarMiddleware'] + MIDDLEWARE
INTERNAL_IPS = ['127.0.0.1']

# urls.py
urlpatterns += [path('__debug__/', include('debug_toolbar.urls'))]
```

**Look for:** "SQL" panel showing 50+ queries on one page = red flag. Click query to see traceback to the offending code line.

### `django-silk` (Profiling)

More detailed than debug-toolbar — works in staging:

```python
INSTALLED_APPS += ['silk']
MIDDLEWARE = ['silk.middleware.SilkyMiddleware'] + MIDDLEWARE
```

Visit `/silk/` → per-request query profile, time spent per query, request tracebacks.

### `nplusone` middleware (Auto-Detect)

```python
# pip install nplusone
INSTALLED_APPS += ['nplusone.ext.django']
MIDDLEWARE = ['nplusone.ext.django.NPlusOneMiddleware'] + MIDDLEWARE

NPLUSONE_RAISE = True       # raise exception on N+1
NPLUSONE_LOGGER = logging.getLogger('nplusone')
NPLUSONE_LOG_LEVEL = logging.WARNING
```

Detects missing `select_related`/`prefetch_related` automatically. Use `NPLUSONE_RAISE = True` in tests to fail CI on N+1.

### Production Detection — APM + Slow Query Log

```python
# DataDog / New Relic / Sentry Performance
# Look for traces with high SQL query count

# PostgreSQL slow query log
# postgresql.conf:
#   log_min_duration_statement = 100   # log queries > 100ms
#   log_line_prefix = '%t [%p] %u@%d '

# Connection-level logging in Django (last resort)
LOGGING = {
    'loggers': {
        'django.db.backends': {
            'level': 'DEBUG',
            'handlers': ['console'],
        },
    },
}
```

### Manual Inspection — `.query` and `.explain()`

```python
qs = Article.objects.select_related('author').filter(status='published')

print(qs.query)         # compiled SQL
print(qs.explain())     # PostgreSQL EXPLAIN
print(qs.explain(analyze=True, buffers=True))  # actual run + buffer hits
```

---

## Fixing N+1

### `select_related` — for ForeignKey / OneToOne (JOIN)

```python
# BAD (1 + N queries)
for a in Article.objects.all():
    a.author.username

# GOOD (1 query)
for a in Article.objects.select_related('author'):
    a.author.username

# Multi-level
Article.objects.select_related('author__profile', 'category')
```

### `prefetch_related` — for ManyToMany / Reverse FK (separate query)

```python
# BAD
for a in Article.objects.all():
    for t in a.tags.all():  # N queries
        ...

# GOOD (2 queries — 1 for articles, 1 for tags)
for a in Article.objects.prefetch_related('tags'):
    for t in a.tags.all():
        ...
```

### `Prefetch` Object — for Filtered/Ordered Prefetches

```python
from django.db.models import Prefetch

articles = Article.objects.prefetch_related(
    Prefetch(
        'comments',
        queryset=Comment.objects.filter(approved=True).order_by('-created_at')[:5],
        to_attr='top_comments',
    )
)

for a in articles:
    for c in a.top_comments:  # already filtered + limited
        ...
```

### `only()` and `defer()` — load only needed columns

```python
# Don't load body column (huge text)
Article.objects.only('id', 'title', 'author_id')

# Same goal — exclude body
Article.objects.defer('body')
```

### `values()` / `values_list()` — for read-only data

```python
# No model instantiation — fast dict result
articles = Article.objects.values('id', 'title', 'author__username')

# Single column
ids = Article.objects.values_list('id', flat=True)
```

---

## Common Pitfalls

### 1. DRF Serializers Hidden N+1

```python
class ArticleSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.username')

    class Meta:
        model = Article
        fields = ('id', 'title', 'author_name')


# View
class ArticleListView(generics.ListAPIView):
    queryset = Article.objects.all()  # MISSING select_related
    serializer_class = ArticleSerializer
```

**Fix:** Override `get_queryset`:

```python
def get_queryset(self):
    return Article.objects.select_related('author')
```

### 2. Property Methods on Models

```python
class Article(models.Model):
    @property
    def comment_count(self):
        return self.comments.count()  # 1 query per article


# In view
[a.comment_count for a in Article.objects.all()]  # N queries
```

**Fix:** Annotate:

```python
from django.db.models import Count
Article.objects.annotate(comment_count=Count('comments'))
```

### 3. Conditional Prefetch (need `Prefetch`)

```python
# WRONG — applies filter AFTER prefetch (still loads all)
Article.objects.prefetch_related('comments').filter(comments__approved=True)

# RIGHT
from django.db.models import Prefetch
Article.objects.prefetch_related(
    Prefetch('comments', queryset=Comment.objects.filter(approved=True))
)
```

### 4. `Count` with Filter

```python
# WRONG — double-counts due to JOIN
Article.objects.annotate(
    approved_comments=Count('comments', filter=Q(comments__approved=True))
)

# Subquery is sometimes safer (avoids JOIN fanout)
from django.db.models import Subquery, OuterRef
Article.objects.annotate(
    approved_comments=Subquery(
        Comment.objects.filter(article=OuterRef('pk'), approved=True)
        .values('article').annotate(c=Count('*')).values('c')
    )
)
```

### 5. Django Template `{% for %}` Hidden N+1

Templates have no syntax for prefetch. Always prefetch in view, never in template.

### 6. `len()` vs `.count()`

```python
len(Article.objects.all())     # loads all into memory
Article.objects.all().count()  # SQL COUNT(*) — fast
```

---

## Interview Q&A

**Q1:** N+1 detect kaise karoge — three different ways batao.
**A:** (1) Tests: `assertNumQueries(N)` + `CaptureQueriesContext`. (2) Dev: django-debug-toolbar SQL panel. (3) Auto: nplusone middleware with `NPLUSONE_RAISE = True`. (4) Prod: APM (DataDog) traces with query count, PostgreSQL `pg_stat_statements`. (5) Code review: spot for-loops accessing relations without prefetch.

**Q2:** `select_related` vs `prefetch_related` — kab kya?
**A:** `select_related` = SQL JOIN, works for ForeignKey/OneToOne (single related row). `prefetch_related` = separate query + Python join, works for ManyToMany and reverse FK (many related rows). Rule: forward single → select_related; many → prefetch_related.

**Q3:** Prefetch ke andar filter/order kaise karoge?
**A:** `Prefetch('comments', queryset=Comment.objects.filter(approved=True).order_by('-created_at')[:5], to_attr='top_comments')`. `to_attr` separates from default reverse manager — accessing as `article.top_comments` returns the filtered list without re-querying.

**Q4:** DRF list API mein N+1 chhupa hua kaise milta hai?
**A:** Serializer fields like `author_name = CharField(source='author.username')` trigger per-row FK access. ListView's `get_queryset()` must include `select_related('author')`. Always test API views with `assertNumQueries(expected)`.

**Q5:** `annotate(Count())` se subquery kab choose karoge?
**A:** Annotate with JOIN fanout: if you Count across multiple related tables, JOINs multiply rows → wrong counts. Subquery isolates each count: `Subquery(...).annotate(c=Count('*'))`. Also faster sometimes — DB plans subquery as hash-aggregate.

**Q6:** `only()` aur `values()` ka difference?
**A:** `only('field')` = model instance with limited fields loaded (others lazily). `values('field')` = dict, no model overhead. `values` is faster (no instance creation) but you lose model methods.

**Q7:** Production mein N+1 detect karne ka strategy?
**A:** (1) APM (Sentry Performance, DataDog) auto-detects high-query traces. (2) `pg_stat_statements` extension shows top frequent queries. (3) Slow query log threshold = 100ms. (4) Synthetic monitoring — periodic test hitting key endpoints with `assertNumQueries`. (5) `django-silk` in staging for full request traces.

**Q8:** Template mein for-loop pe N+1 kaise prevent karoge?
**A:** Templates can't prefetch — fix in view. Pass already-prefetched queryset to template. Generic mistake: `{% for a in articles %}{{ a.author.name }}{% endfor %}` without `articles = Article.objects.select_related('author')` in view = N+1.

---

## Real-World Use Cases

### 1. CI Gate for N+1

```python
# tests/test_n_plus_one.py
class CriticalEndpointN1Tests(TestCase):
    """Lock down query counts on key endpoints."""

    fixtures = ['articles_100.json']

    def test_article_list_query_count(self):
        with self.assertNumQueries(3):  # auth + articles + prefetch
            response = self.client.get('/api/articles/')
        assert response.status_code == 200

    def test_article_detail_query_count(self):
        with self.assertNumQueries(4):
            self.client.get('/api/articles/1/')
```

### 2. Auto-Fail PR via nplusone in CI

```python
# settings/test.py
INSTALLED_APPS += ['nplusone.ext.django']
MIDDLEWARE = ['nplusone.ext.django.NPlusOneMiddleware'] + MIDDLEWARE
NPLUSONE_RAISE = True  # any N+1 = test failure
```

### 3. Real-Time Detection in Prod

```python
# Sentry Performance — set alert: query_count > 50 on /api/articles/
# Slack notification when triggered → investigate within hours
```

---

## References

- [Django docs — Database access optimization](https://docs.djangoproject.com/en/5.0/topics/db/optimization/)
- [django-debug-toolbar](https://github.com/jazzband/django-debug-toolbar)
- [django-silk](https://github.com/jazzband/django-silk)
- [nplusone](https://github.com/jmcarp/nplusone)
- Henrique Bastos talk: "Django ORM Performance"
