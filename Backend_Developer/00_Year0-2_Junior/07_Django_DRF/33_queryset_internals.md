# Django QuerySet Internals

## Why It Matters

QuerySets = lazy. Misunderstanding lazy evaluation = perf bugs:
- Same query executed N times
- "Already in DB" assumption wrong
- Cache invalidation bugs

Senior interview: "Yeh code SQL kab fire karega?" → understand lazy evaluation rules.

---

## Core Concepts

### Lazy Evaluation

```python
qs = Article.objects.filter(status='published')  # NO SQL yet
qs = qs.filter(author=user)                       # NO SQL yet
qs = qs.order_by('-created_at')                   # NO SQL yet

for article in qs:                                 # SQL fires HERE
    print(article.title)
```

Operations that DON'T execute:
- `.filter()`, `.exclude()`, `.order_by()`, `.annotate()`, `.values()`, `.values_list()`, `.distinct()`, `.select_related()`, `.prefetch_related()`, `.using()`

Operations that DO execute:
- Iteration (`for x in qs`)
- `list(qs)`, `bool(qs)`, `len(qs)`, `pickle(qs)`
- `qs[0]`, `qs[5:10]` — slicing with index access
- `.first()`, `.last()`, `.get()`, `.count()`, `.exists()`, `.aggregate()`, `.update()`, `.delete()`

### Caching

```python
qs = Article.objects.filter(status='published')

list(qs)         # SQL fires, results cached on qs
list(qs)         # No SQL — cached results

for a in qs:     # No SQL — cached
    print(a.title)
```

**Caching applies to one QuerySet object.** New QuerySet (even identical) = fresh query.

### When Cache Is Bypassed

```python
qs = Article.objects.all()
list(qs)              # caches
qs.exists()           # may use cache via len(qs) > 0
qs.count()            # NEVER cached — separate COUNT query
```

**`count()` doesn't use cache** — always fresh COUNT query.

### Slicing

```python
qs = Article.objects.all()

# Slice WITHOUT step → returns lazy QuerySet
limited = qs[0:10]    # LIMIT 10 added to SQL when evaluated

# Slice WITH index → evaluates immediately
first = qs[0]         # SQL fires (single record)

# Step → evaluates
every_other = qs[::2]  # SQL fires
```

### Boolean Evaluation

```python
if Article.objects.filter(status='draft'):    # SQL fires (SELECT ... LIMIT 1 or eval all)
    ...


# More efficient
if Article.objects.filter(status='draft').exists():
    ...   # SELECT 1 FROM ... LIMIT 1
```

`exists()` is much cheaper than truthiness check on large qs.

### `.values()` vs `.values_list()` vs ORM instances

```python
# Model instances (memory-heavy)
articles = list(Article.objects.all())         # Article objects


# Dicts (faster, no model overhead)
articles = list(Article.objects.values('id', 'title'))   # [{id: 1, title: '...'}]


# Tuples
articles = list(Article.objects.values_list('id', 'title'))   # [(1, '...'), ...]


# Single column as list
ids = list(Article.objects.values_list('id', flat=True))   # [1, 2, 3]
```

For read-only/aggregation: prefer `values()`/`values_list()` — saves memory + skips model init.

### `iterator()` for Memory Efficiency

```python
# Loads all into memory
for a in Article.objects.all():    # 1M articles → 1M Python objects in RAM
    process(a)


# Streams in chunks
for a in Article.objects.iterator(chunk_size=1000):
    process(a)
```

`iterator()` doesn't cache results — each iteration processes fresh.

### `select_related()` Internals (JOIN)

```python
# Without — N+1
for a in Article.objects.all()[:10]:
    print(a.author.username)   # 11 queries (1 + 10)


# With select_related — 1 query (JOIN)
for a in Article.objects.select_related('author')[:10]:
    print(a.author.username)


# Multi-level
Article.objects.select_related('author__profile')
# JOIN article ON author ON profile
```

Generates SQL:
```sql
SELECT article.*, author.*, profile.*
FROM article
INNER JOIN auth_user author ON article.author_id = author.id
INNER JOIN profile ON author.profile_id = profile.id
```

### `prefetch_related()` Internals (separate query + Python join)

```python
# 2 queries: 1 for articles, 1 for tags (with WHERE article_id IN [...])
for a in Article.objects.prefetch_related('tags'):
    for t in a.tags.all():
        ...
```

Generates:
```sql
SELECT * FROM article;
SELECT * FROM article_tags WHERE article_id IN (1, 2, 3, ...);
SELECT * FROM tag WHERE id IN (...);
```

Python joins in memory.

### `Prefetch` Object (filtered prefetch)

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
    for c in a.top_comments:    # already filtered + limited, no extra query
        ...
```

### `defer()` and `only()`

```python
# Only load specific fields
articles = Article.objects.only('id', 'title')
# SELECT id, title FROM article


for a in articles:
    print(a.title)        # OK
    print(a.body)         # Triggers EXTRA query to load body


# Exclude specific fields
articles = Article.objects.defer('body')   # Load all except body
```

Use when reading large tables but only need few columns.

### F Expressions (database-side operations)

```python
from django.db.models import F


# Increment in DB (atomic, no race)
Article.objects.filter(pk=1).update(view_count=F('view_count') + 1)


# Compare fields
Article.objects.filter(updated_at__gt=F('created_at'))    # updated after created


# Annotations
Article.objects.annotate(score=F('likes') * 2 + F('comments_count'))
```

### Q Objects (complex queries)

```python
from django.db.models import Q


# OR
Article.objects.filter(Q(status='published') | Q(featured=True))


# NOT
Article.objects.filter(~Q(status='draft'))


# Combined
Article.objects.filter(
    Q(status='published') &
    (Q(category='tech') | Q(category='science'))
)
```

### Aggregation

```python
from django.db.models import Count, Sum, Avg, Max, Min


# Single aggregate
total = Order.objects.aggregate(Sum('amount'))
# {'amount__sum': 99999}


# Multiple
stats = Order.objects.aggregate(
    total=Sum('amount'),
    count=Count('id'),
    avg=Avg('amount'),
)


# Per-group via annotate
Article.objects.values('author').annotate(
    article_count=Count('id'),
    total_views=Sum('view_count'),
)
```

### Subquery + OuterRef

```python
from django.db.models import Subquery, OuterRef


# Articles with their latest comment
latest_comment = Comment.objects.filter(
    article=OuterRef('pk')
).order_by('-created_at').values('body')[:1]


Article.objects.annotate(
    latest_comment=Subquery(latest_comment)
)
```

### Window Functions (Django 4+)

```python
from django.db.models import Window, F
from django.db.models.functions import Rank, RowNumber


# Rank articles by views within each category
Article.objects.annotate(
    rank=Window(
        expression=Rank(),
        partition_by=[F('category')],
        order_by=F('view_count').desc(),
    )
)


# Top 3 per category
qs = Article.objects.annotate(
    row=Window(expression=RowNumber(), partition_by=[F('category')], order_by=F('view_count').desc())
)
# Filter via subquery wrapper (window functions can't be in WHERE directly)
```

### Bulk Operations

```python
# bulk_create — single INSERT
articles = [Article(title=f'T{i}', body='...') for i in range(1000)]
Article.objects.bulk_create(articles, batch_size=500)


# bulk_update
articles = Article.objects.filter(status='draft')
for a in articles:
    a.status = 'pending'
Article.objects.bulk_update(articles, ['status'], batch_size=500)


# update (set multiple rows directly)
Article.objects.filter(status='draft').update(status='published')


# delete (single DELETE)
Article.objects.filter(created_at__lt=cutoff).delete()
```

`bulk_*` skips signals + save() override. Faster but watch for side effects.

---

## Common Pitfalls

### 1. Repeated Query in Loop

```python
for article_id in ids:
    Article.objects.get(pk=article_id)  # N queries
```

Use `in_bulk()`:

```python
articles = Article.objects.in_bulk(ids)   # 1 query, dict by pk
```

### 2. `.count()` Slow

```python
Article.objects.count()   # SELECT COUNT(*) on huge table — slow
```

For approximate count (PostgreSQL):
```python
from django.db import connection
with connection.cursor() as c:
    c.execute("SELECT reltuples::bigint AS estimate FROM pg_class WHERE relname='blog_article'")
    estimate = c.fetchone()[0]
```

### 3. `.exists()` vs Truthy Check

```python
if qs:    # may evaluate full queryset
    ...
if qs.exists():    # SELECT 1 ... LIMIT 1
    ...
```

### 4. Filter After Slice Mistake

```python
qs = Article.objects.all()[:10]
qs.filter(status='published')   # ERROR — can't filter after slice
```

Filter first, slice last.

### 5. Cached QuerySet Reuse

```python
qs = Article.objects.all()
list(qs)
# Add new article to DB
new = Article.objects.create(...)
list(qs)   # WON'T include new — using cache
```

Recreate qs to refetch.

### 6. `prefetch_related` + Custom Manager

```python
class PublishedManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(status='published')


Article.objects.prefetch_related('comments')   # comments may include unpublished
```

Use `Prefetch` to specify queryset.

### 7. Forgetting `.distinct()` with JOIN

```python
Article.objects.filter(tags__name='python')   # may return duplicates if multi-tag match
```

Add `.distinct()`.

### 8. annotate + Count with JOIN Fanout

```python
Article.objects.annotate(
    cm=Count('comments'),
    rxn=Count('reactions'),
)
# May multiply counts — JOIN fanout
```

Use Subquery for accurate.

---

## Interview Q&A

**Q1:** QuerySet lazy hai — kya matlab?
**A:** `.filter()`, `.order_by()`, `.values()` etc. don't execute SQL. They return new QuerySet. SQL fires on: iteration, list(), bool() (smartly), slicing with index, `.first()`, `.get()`, `.count()`, `.exists()`, `.aggregate()`. Lazy lets you compose queries.

**Q2:** select_related vs prefetch_related?
**A:** `select_related`: SQL JOIN, single query. Works for forward FK + OneToOne (single related row). `prefetch_related`: separate query + Python join. Works for M2M + reverse FK (many related rows). Rule: forward single → select; many → prefetch.

**Q3:** Cached QuerySet ka behavior?
**A:** First evaluation caches results on QuerySet instance. Subsequent iterations use cache. But: `.count()` always fresh, `.exists()` may use cache, new QuerySet (even identical filter) = fresh fetch. To force refresh, recreate qs.

**Q4:** iterator() kab use karte ho?
**A:** Large querysets where you can process row-by-row without holding all in memory. `Article.objects.iterator(chunk_size=1000)` — server cursor (or chunked), no result caching. Critical for migrations, exports, batch ops on millions of rows.

**Q5:** values() vs values_list() vs model instances — performance?
**A:** Model instances: slowest, full Python object. `values()`: dicts, no model init. `values_list()`: tuples, even less overhead. For reads only: `values_list(..., flat=True)` for single column = fastest. Memory: instances > dicts > tuples.

**Q6:** Subquery vs JOIN — kab kya?
**A:** JOIN (via `select_related` or annotate with `Count`/`Sum`): may cause row multiplication (fanout) leading to wrong counts. Subquery: isolated, exact, often faster on indexed columns. For "find latest comment per article": Subquery + OuterRef preferred.

**Q7:** Django ORM SQL kaise dekho?
**A:** `print(queryset.query)` — compiled SQL. `from django.db import connection; print(connection.queries)` after evaluation. Or `EXPLAIN`: `queryset.explain(analyze=True)`. django-debug-toolbar shows all queries in dev. django-silk in staging.

**Q8:** F-expressions ka use case?
**A:** Atomic DB-side ops + cross-field references. `Article.objects.update(views=F('views') + 1)` is race-condition-free (single SQL UPDATE). Without F: read views, increment, save → lost update under concurrency. Also for queries: `filter(updated_at__gt=F('created_at'))`.

---

## Real-World Use Cases

### 1. Memory-Efficient Export

```python
def export_articles(filename):
    with open(filename, 'w') as f:
        writer = csv.writer(f)
        for a in Article.objects.values_list('id', 'title', 'created_at').iterator(chunk_size=1000):
            writer.writerow(a)
```

### 2. Atomic Counter

```python
def increment_view(article_id):
    Article.objects.filter(pk=article_id).update(view_count=F('view_count') + 1)
```

### 3. Top N Per Group

```python
qs = Article.objects.annotate(
    row=Window(expression=RowNumber(), partition_by=[F('category')], order_by=F('view_count').desc())
)

top_3 = Article.objects.filter(pk__in=[a.pk for a in qs if a.row <= 3])
```

---

## References

- [QuerySet API](https://docs.djangoproject.com/en/5.0/ref/models/querysets/)
- [Database optimization](https://docs.djangoproject.com/en/5.0/topics/db/optimization/)
- [Query Expressions](https://docs.djangoproject.com/en/5.0/ref/models/expressions/)
- Use The Index, Luke! (book)
