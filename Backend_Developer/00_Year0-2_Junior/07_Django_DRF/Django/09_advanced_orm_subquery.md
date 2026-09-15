# Django Advanced ORM — Subquery, Exists, Raw SQL, Bulk Ops, Window Functions

## Quick Concepts
- **Subquery** = nested SELECT inside outer query — correlated ya independent
- **OuterRef** = outer query ka field reference karo inner subquery mein
- **Exists()** = efficient "koi record hai?" check — full COUNT se better
- **Raw SQL** = ORM bypass karke direct SQL — last resort, lekin powerful
- **bulk_create/update** = 1000 rows ek query mein — loop `.save()` se 100x faster
- **Case/When** = SQL CASE WHEN — conditional computed columns
- **Window Functions** = OVER clause — row_number, running total, lag/lead

---

## Section A — Subquery & OuterRef

### OuterRef kya hai?

Inner subquery mein outer query ka field reference karna ho toh `OuterRef` use karte hain.
Simple analogy: outer query har Author ke liye loop kar rahi hai — `OuterRef('pk')` matlab
"is wale Author ka pk use karo inner query mein".

```python
# ─── Models (reference) ───────────────────────────────────────
# class Author(models.Model):
#     name = models.CharField(max_length=100)
#
# class Post(models.Model):
#     author     = models.ForeignKey(Author, related_name='posts', on_delete=models.CASCADE)
#     title      = models.CharField(max_length=200)
#     created_at = models.DateTimeField(auto_now_add=True)

from django.db.models import OuterRef, Subquery

# ─── Classic Example: har author ka latest post title ─────────
latest_post = Post.objects.filter(
    author=OuterRef('pk')          # outer Author ka pk reference
).order_by('-created_at').values('title')[:1]   # SIRF ek value chahiye

authors = Author.objects.annotate(
    latest_post_title=Subquery(latest_post)
)

for author in authors:
    print(f"{author.name}: {author.latest_post_title or 'No posts'}")

# Generated SQL (roughly):
# SELECT author.id, author.name,
#   (SELECT title FROM blog_post
#    WHERE author_id = author.id
#    ORDER BY created_at DESC LIMIT 1) AS latest_post_title
# FROM blog_author
```

### Subquery return type — values()[:1] kyun zaroori hai?

```python
# WRONG — ValueError: Subquery must return 1 column
bad = Post.objects.filter(author=OuterRef('pk')).order_by('-created_at')[:1]
# Error: Subquery select ambiguous — multiple columns return ho rahi hain

# CORRECT — .values('field')[:1]
good = Post.objects.filter(
    author=OuterRef('pk')
).order_by('-created_at').values('created_at')[:1]  # ek column, ek row

# Multiple fields chahiye? values_list use karo ya alag Subquery
```

### Multiple Subqueries ek annotate mein

```python
from django.db.models import OuterRef, Subquery, IntegerField

# Latest post title
latest_title_sq = Post.objects.filter(
    author=OuterRef('pk')
).order_by('-created_at').values('title')[:1]

# Total post count (ya Count use karo — but Subquery bhi valid hai)
published_count_sq = Post.objects.filter(
    author=OuterRef('pk'),
    status='published'
).order_by().values('author').annotate(
    cnt=Count('id')
).values('cnt')[:1]

# Latest comment date on author's any post
latest_comment_sq = Comment.objects.filter(
    post__author=OuterRef('pk'),  # nested OuterRef chain
    is_approved=True
).order_by('-created_at').values('created_at')[:1]

authors = Author.objects.annotate(
    latest_post_title=Subquery(latest_title_sq),
    latest_comment_at=Subquery(latest_comment_sq),
)
```

### Correlated Subquery vs JOIN — performance comparison

```python
# ─── Subquery approach ────────────────────────────────────────
# Har outer row ke liye ek inner query execute hoti hai
# 1 outer query + N inner executions (DB engine optimizes this)
# Better when: result set chhota ho, selective join nahi chahiye

authors_subq = Author.objects.annotate(
    latest_post_title=Subquery(latest_post)
)

# ─── JOIN approach ────────────────────────────────────────────
# Sab rows ek saath join hoti hain — zyada rows = zyada memory
# Better when: large result set, multiple aggregations, index available

from django.db.models import Max
authors_join = Author.objects.annotate(
    latest_post_date=Max('posts__created_at')
)

# RULE OF THUMB:
# - Single correlated value fetch  → Subquery (cleaner, usually fast)
# - Aggregation (COUNT, SUM, AVG)  → annotate with Count/Sum (JOIN under hood)
# - Complex multi-step logic        → Raw SQL or intermediate model
```

---

## Section B — Exists()

### Exists() kya hai?

`Exists()` SQL ka `EXISTS (SELECT 1 ...)` generate karta hai. Boolean result deta hai —
koi bhi matching row mili toh `True`. `count() > 0` se isliye better hai kyunki:

- `COUNT(*)` = poori table scan karta hai, count karta hai
- `EXISTS` = pehli matching row mili aur ruk jaata hai — **short circuit**

```python
from django.db.models import Exists, OuterRef

# ─── Annotate with boolean ────────────────────────────────────
has_comments_sq = Comment.objects.filter(
    post=OuterRef('pk'),
    is_approved=True
)

posts = Post.objects.annotate(
    has_approved_comments=Exists(has_comments_sq)
)

for post in posts:
    print(f"{post.title}: comments={post.has_approved_comments}")

# Generated SQL:
# SELECT *, EXISTS(
#   SELECT 1 FROM blog_comments
#   WHERE post_id = blog_posts.id AND is_approved = TRUE
# ) AS has_approved_comments
# FROM blog_posts
```

### Filter with Exists — efficient "has any" filter

```python
# Posts jinmein koi approved comment hai — EFFICIENT
posts_with_comments = Post.objects.filter(
    Exists(
        Comment.objects.filter(
            post=OuterRef('pk'),
            is_approved=True
        )
    )
)

# Vs BAD approach (N+1 ya slow COUNT):
# BAD: [p for p in Post.objects.all() if p.comments.filter(is_approved=True).count() > 0]
# BAD: Post.objects.annotate(c=Count('comments')).filter(c__gt=0)  # full join + count

# ─── NOT Exists: ~ operator ───────────────────────────────────
posts_without_comments = Post.objects.filter(
    ~Exists(
        Comment.objects.filter(post=OuterRef('pk'))
    )
)
# SQL: WHERE NOT EXISTS (SELECT 1 FROM blog_comments WHERE post_id = blog_posts.id)
```

### Exists vs filter with related managers

```python
# ─── 3 approaches comparison ──────────────────────────────────

# Method 1: Python level (BAD — N+1)
posts = Post.objects.all()
result = []
for post in posts:
    if post.comments.filter(is_approved=True).exists():  # N queries!
        result.append(post)

# Method 2: annotate + filter (OK — single query but heavy JOIN)
from django.db.models import Count
posts = Post.objects.annotate(
    c=Count('comments', filter=Q(comments__is_approved=True))
).filter(c__gt=0)

# Method 3: Exists() subquery (BEST — no full scan, short circuit)
posts = Post.objects.filter(
    Exists(Comment.objects.filter(post=OuterRef('pk'), is_approved=True))
)
```

---

## Section C — Raw SQL

### Method 1: Manager.raw() — Model instances milte hain

```python
from blog.models import Post

# ─── Basic raw() ──────────────────────────────────────────────
posts = Post.objects.raw(
    "SELECT id, title, views_count FROM blog_posts WHERE status = %s ORDER BY views_count DESC",
    ['published']   # parameterized — SQL injection safe!
)

# RawQuerySet iterate karo
for post in posts:
    print(post.title, post.views_count)  # model instance milta hai
    # IMPORTANT: id field zaroori hai raw() mein — primary key must be in SELECT

# ─── Extra computed columns ───────────────────────────────────
posts_with_rank = Post.objects.raw(
    """
    SELECT p.id, p.title, p.views_count,
           COUNT(c.id) AS comment_count,
           RANK() OVER (ORDER BY p.views_count DESC) AS view_rank
    FROM blog_posts p
    LEFT JOIN blog_comments c ON c.post_id = p.id AND c.is_approved = TRUE
    WHERE p.status = %s AND p.deleted_at IS NULL
    GROUP BY p.id
    ORDER BY p.views_count DESC
    LIMIT %s
    """,
    ['published', 20]
)

for post in posts_with_rank:
    # Extra columns attribute ke roop mein accessible hain
    print(f"#{post.view_rank} {post.title}: {post.comment_count} comments")
```

### Method 2: connection.cursor() — Full control

```python
from django.db import connection

# ─── dictfetchall helper ───────────────────────────────────────
def dictfetchall(cursor):
    """cursor results ko list of dicts mein convert karo."""
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]

def dictfetchone(cursor):
    """Single row dict."""
    columns = [col[0] for col in cursor.description]
    row = cursor.fetchone()
    return dict(zip(columns, row)) if row else None

# ─── Complex aggregation example ──────────────────────────────
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT
            c.name AS category_name,
            COUNT(p.id) AS post_count,
            SUM(p.views_count) AS total_views,
            AVG(p.views_count)::NUMERIC(10,2) AS avg_views,
            MAX(p.published_at) AS latest_post_date
        FROM blog_categories c
        LEFT JOIN blog_posts p ON p.category_id = c.id
            AND p.status = 'published'
            AND p.deleted_at IS NULL
        GROUP BY c.id, c.name
        ORDER BY total_views DESC NULLS LAST
    """)
    results = dictfetchall(cursor)

for row in results:
    print(f"{row['category_name']}: {row['post_count']} posts, {row['total_views']} views")

# ─── fetchone vs fetchmany vs fetchall ────────────────────────
with connection.cursor() as cursor:
    cursor.execute("SELECT id, title FROM blog_posts WHERE status = 'published'")

    first_row = cursor.fetchone()        # ek row — tuple
    next_10   = cursor.fetchmany(10)     # list of tuples (memory efficient)
    rest      = cursor.fetchall()        # baaki saare — list of tuples

# ─── Transactions with raw SQL ─────────────────────────────────
from django.db import transaction

with transaction.atomic():
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE blog_posts SET views_count = views_count + %s WHERE id = %s",
            [1, post_id]
        )
        cursor.execute(
            "INSERT INTO blog_view_log (post_id, viewed_at) VALUES (%s, NOW())",
            [post_id]
        )
    # Dono queries ek saath commit ya rollback hongi
```

### SQL Injection Prevention

```python
# ─── NEVER DO THIS — SQL Injection ───────────────────────────
user_input = "'; DROP TABLE blog_posts; --"

# DANGEROUS:
Post.objects.raw(f"SELECT * FROM blog_posts WHERE title = '{user_input}'")
# Ye run hoga: SELECT * FROM blog_posts WHERE title = ''; DROP TABLE blog_posts; --'

# DANGEROUS:
with connection.cursor() as cursor:
    cursor.execute(f"SELECT * FROM blog_posts WHERE title = '{user_input}'")

# ─── ALWAYS DO THIS — Parameterized ──────────────────────────
# Safe:
Post.objects.raw("SELECT * FROM blog_posts WHERE title = %s", [user_input])

# Safe:
with connection.cursor() as cursor:
    cursor.execute("SELECT * FROM blog_posts WHERE title = %s", [user_input])

# Django ORM automatically handles this:
Post.objects.filter(title=user_input)  # always safe
```

---

## Section D — Bulk Operations

### bulk_create — single INSERT query

```python
from blog.models import Post
from django.contrib.auth import get_user_model
import time

User = get_user_model()

# ─── Loop .save() — SLOW (N queries) ─────────────────────────
author = User.objects.first()
start = time.time()
for i in range(100):
    Post.objects.create(
        title=f"Post {i}",
        content="Sample content",
        author=author,
        status="draft"
    )
loop_time = time.time() - start
print(f"Loop save (100 rows): {loop_time:.2f}s, ~100 queries")

# ─── bulk_create — FAST (1-5 queries) ────────────────────────
posts_to_create = [
    Post(
        title=f"Bulk Post {i}",
        content="Sample content",
        author=author,
        status="draft"
    )
    for i in range(1000)
]

start = time.time()
created = Post.objects.bulk_create(
    posts_to_create,
    batch_size=200,           # 1000 rows / 200 = 5 INSERT queries
    ignore_conflicts=True,    # duplicate slug? skip karo (no error)
)
bulk_time = time.time() - start
print(f"bulk_create (1000 rows): {bulk_time:.2f}s, ~5 queries")
print(f"Speedup: {loop_time / bulk_time:.0f}x faster (approx)")

# ─── update_conflicts (PostgreSQL 9.5+ only) ─────────────────
# ignore_conflicts=True  → conflict pe row skip
# update_conflicts=True  → conflict pe update karo

posts_with_sku = [
    Post(title="Existing Post", slug="existing-post", content="Updated content", author=author)
]

Post.objects.bulk_create(
    posts_with_sku,
    update_conflicts=True,
    unique_fields=['slug'],          # conflict detect karne ke liye
    update_fields=['content'],       # kon se fields update karein
)
```

### bulk_update — single UPDATE query per batch

```python
# ─── Scenario: 10% price hike (like views_count update) ──────
posts = list(Post.objects.filter(status='published')[:500])

# Mark all as archived + add suffix
for post in posts:
    post.status = 'archived'
    post.title = post.title + " [Archived]"

# SINGLE UPDATE query (per batch)
updated_count = Post.objects.bulk_update(
    posts,
    fields=['status', 'title'],   # sirf ye fields update honge
    batch_size=200                # 500 / 200 = 3 queries
)
print(f"Updated: {updated_count} posts")

# ─── IMPORTANT GOTCHAS ────────────────────────────────────────
# 1. bulk_create does NOT call save() signals nahi fire hoti
# 2. bulk_update does NOT call save() — model's save() bypass
# 3. pre_save / post_save signals nahi chalti
# 4. auto_now fields (updated_at) UPDATE nahi honge bulk_update mein
#    Solution: manually set updated_at in loop, then bulk_update with it

from django.utils import timezone
for post in posts:
    post.updated_at = timezone.now()  # manually set

Post.objects.bulk_update(posts, ['status', 'title', 'updated_at'], batch_size=200)
```

### Performance Comparison Summary

```
Operation         | 1000 rows   | Queries | Approx Time
------------------|-------------|---------|------------
Loop .save()      | 1000 INSERTs| 1000    | ~2000ms
bulk_create()     | 5 INSERTs   | 5       | ~20ms   (100x faster)
bulk_update()     | 5 UPDATEs   | 5       | ~30ms   (60x faster)
update()          | 1 UPDATE    | 1       | ~5ms    (best for uniform change)
```

---

## Section E — update_or_create & get_or_create

### get_or_create — race condition safe

```python
from blog.models import Category

# ─── Basic usage ──────────────────────────────────────────────
category, created = Category.objects.get_or_create(
    name="Technology",          # lookup fields (WHERE clause)
    defaults={                  # sirf create hone pe use hoga
        "slug": "technology",
        "description": "Tech articles"
    }
)

if created:
    print(f"New category created: {category.name}")
else:
    print(f"Existing category found: {category.name}")

# ─── Thread Safety ────────────────────────────────────────────
# get_or_create internally karta hai:
# 1. SELECT karo — mila toh return
# 2. Nahi mila toh INSERT karo
# 3. Agar dono threads simultaneously INSERT karein → IntegrityError possible
# Solution: unique constraint + try/except ya SELECT ... FOR UPDATE

from django.db import IntegrityError
try:
    obj, created = Category.objects.get_or_create(
        name="Technology",
        defaults={"slug": "technology"}
    )
except IntegrityError:
    # Race condition — kisi aur ne already create kar diya
    obj = Category.objects.get(name="Technology")
    created = False
```

### update_or_create — upsert pattern

```python
# ─── update_or_create ─────────────────────────────────────────
# Agar record mila → defaults se UPDATE karo
# Nahi mila → nayi entry CREATE karo

from blog.models import Tag

tag, created = Tag.objects.update_or_create(
    slug="django",                          # lookup
    defaults={                              # create ya update dono mein
        "name": "Django",
        "color": "#0C4B33"
    }
)
# Internally: SELECT → found? UPDATE with defaults : INSERT with name+defaults

# ─── PostgreSQL native upsert (bulk) ──────────────────────────
# bulk_create with update_conflicts — true upsert (atomic, faster)
tags = [
    Tag(name="Python", slug="python", color="#3572A5"),
    Tag(name="Django", slug="django", color="#0C4B33"),
    Tag(name="DRF",    slug="drf",    color="#A41E22"),
]

Tag.objects.bulk_create(
    tags,
    update_conflicts=True,
    unique_fields=['slug'],          # ON CONFLICT (slug)
    update_fields=['name', 'color']  # DO UPDATE SET name=..., color=...
)
# Single SQL: INSERT INTO ... ON CONFLICT (slug) DO UPDATE SET ...
```

---

## Section F — Complex Annotations with Case/When

### Conditional field — CASE WHEN in annotate

```python
from django.db.models import Case, When, Value, CharField, IntegerField, Sum, F, Q
from blog.models import Post

# ─── Conditional string annotation ───────────────────────────
posts = Post.objects.annotate(
    engagement_level=Case(
        When(views_count__lt=100,   then=Value("low")),
        When(views_count__lt=1000,  then=Value("medium")),
        When(views_count__lt=10000, then=Value("high")),
        default=Value("viral"),
        output_field=CharField()
    )
)

for post in posts[:5]:
    print(f"{post.title[:40]}: {post.engagement_level} ({post.views_count} views)")

# ─── Conditional COUNT ────────────────────────────────────────
# Posts ka stats: published vs draft count per author
from django.contrib.auth import get_user_model
User = get_user_model()

authors = User.objects.annotate(
    published_posts=Sum(
        Case(
            When(posts__status='published', then=1),
            default=0,
            output_field=IntegerField()
        )
    ),
    draft_posts=Sum(
        Case(
            When(posts__status='draft', then=1),
            default=0,
            output_field=IntegerField()
        )
    )
)

for author in authors:
    print(f"{author.email}: {author.published_posts} published, {author.draft_posts} drafts")

# ─── Case/When with F() expressions ──────────────────────────
# Discounted price calculate karo condition based
from django.db.models import FloatField, ExpressionWrapper

posts = Post.objects.annotate(
    # Featured posts ko zyada weight
    weighted_score=Case(
        When(is_featured=True,  then=F('views_count') * 2),
        When(is_featured=False, then=F('views_count') * 1),
        output_field=IntegerField()
    )
).order_by('-weighted_score')
```

---

## Section G — Window Functions

### Window Functions kya hain?

Window functions SQL OVER clause use karti hain — GROUP BY ki tarah hai but rows eliminate nahi hoti.
Har row apni value rakhti hai + window calculation ka result bhi milta hai.

```python
from django.db.models import Window, F, Sum, Avg
from django.db.models.functions import RowNumber, Rank, DenseRank, Lead, Lag, FirstValue
from blog.models import Post

# ─── Row Number per category ──────────────────────────────────
# Har category mein posts ko views se rank karo
posts = Post.objects.filter(
    status='published'
).annotate(
    row_num=Window(
        expression=RowNumber(),
        partition_by=[F('category_id')],  # PARTITION BY category
        order_by=F('views_count').desc()  # ORDER BY views_count DESC
    )
)

# SQL: SELECT *, ROW_NUMBER() OVER (PARTITION BY category_id ORDER BY views_count DESC)
for post in posts[:10]:
    print(f"Cat {post.category_id} Rank #{post.row_num}: {post.title}")

# ─── Rank vs DenseRank ────────────────────────────────────────
# Rank:      1, 2, 2, 4  (tie ke baad gap)
# DenseRank: 1, 2, 2, 3  (tie ke baad gap nahi)
posts = Post.objects.annotate(
    rank=Window(
        expression=Rank(),
        partition_by=[F('category_id')],
        order_by=F('views_count').desc()
    ),
    dense_rank=Window(
        expression=DenseRank(),
        partition_by=[F('category_id')],
        order_by=F('views_count').desc()
    )
)

# ─── Running Total ────────────────────────────────────────────
# All time cumulative views — chronological
posts = Post.objects.filter(status='published').annotate(
    running_views=Window(
        expression=Sum('views_count'),
        order_by=F('published_at').asc()
        # partition_by nahi → sab posts ek window mein
    )
).order_by('published_at')

for post in posts:
    print(f"{post.published_at.date()} | {post.title[:30]} | Running total: {post.running_views}")

# ─── Lag — previous row value (compare with previous) ─────────
posts = Post.objects.filter(status='published').annotate(
    prev_views=Window(
        expression=Lag('views_count', offset=1, default=0),
        order_by=F('published_at').asc()
    ),
    # Views growth = current - previous
).annotate(
    views_growth=F('views_count') - F('prev_views')
).order_by('published_at')

for post in posts[:5]:
    print(f"{post.title[:30]}: {post.views_count} views (growth: +{post.views_growth})")

# ─── Lead — next row value ────────────────────────────────────
posts = Post.objects.filter(status='published').annotate(
    next_post_title=Window(
        expression=Lead('title', offset=1, default='[Last Post]'),
        order_by=F('published_at').asc()
    )
).order_by('published_at')

# ─── Filter on window functions — MUST use subquery ──────────
# Window function directly filter nahi ho sakti (SQL limitation)
# Use subquery ya Subquery wrapper

from django.db.models import Subquery, OuterRef

# Top-1 post per category
subq = Post.objects.filter(
    category_id=OuterRef('category_id'),
    status='published'
).order_by('-views_count').values('id')[:1]

top_posts = Post.objects.filter(
    id=Subquery(subq),
    status='published'
)
```

---

## Interview Questions & Answers

### Q1: Subquery vs JOIN — kab kya better hai?

**Answer:**

```python
# Subquery better hai jab:
# 1. Single correlated value fetch karna ho (latest, max, etc.)
# 2. Optional relation ho (LEFT JOIN produces NULLs + duplicates)
# 3. EXISTS check karna ho (boolean result chahiye)

# Example: har author ka latest post — Subquery clean hai
latest_post = Post.objects.filter(
    author=OuterRef('pk')
).order_by('-created_at').values('title')[:1]

authors = Author.objects.annotate(latest_post_title=Subquery(latest_post))

# JOIN better hai jab:
# 1. Multiple aggregations ek saath chahiye (COUNT + SUM + AVG)
# 2. Both sides ke fields chahiye result mein
# 3. Large datasets ke saath multiple filters

# Example: har author ka total posts + total views — JOIN efficient
authors = Author.objects.annotate(
    post_count=Count('posts'),
    total_views=Sum('posts__views_count')
)

# Rule: EXPLAIN ANALYZE karo production mein, theory se blindly mat choose karo
```

### Q2: bulk_create mein ignore_conflicts vs update_conflicts?

**Answer:**

```python
# ignore_conflicts=True:
# - Duplicate aayi toh silently skip karo
# - No error, no update
# - Use case: "naya data insert karo, existing touch mat karo"
# - PostgreSQL: INSERT ... ON CONFLICT DO NOTHING
# - Note: created list mein skipped rows bhi ho sakti hain (pk None)

Post.objects.bulk_create(posts, ignore_conflicts=True)

# update_conflicts=True (PostgreSQL 9.5+):
# - Duplicate aayi toh update karo
# - unique_fields + update_fields required
# - Use case: "sync data — nayi insert, purani update"
# - PostgreSQL: INSERT ... ON CONFLICT (slug) DO UPDATE SET ...

Post.objects.bulk_create(
    posts,
    update_conflicts=True,
    unique_fields=['slug'],
    update_fields=['title', 'content', 'views_count']
)

# IMPORTANT:
# - update_conflicts=True SQLite par kaam nahi karta
# - ignore_conflicts=True MySQL/PostgreSQL/SQLite sab par kaam karta hai
# - bulk_create mein save() nahi chalta — signals bypass hoti hain
```

### Q3: N+1 problem production mein kaise detect karein?

**Answer:**

```python
# ─── Method 1: Django Debug Toolbar ──────────────────────────
# Browser mein har request ke queries dikhti hain
# Install: pip install django-debug-toolbar
# settings.py mein add karo INSTALLED_APPS + MIDDLEWARE

# ─── Method 2: connection.queries ───────────────────────────
from django.db import connection, reset_queries
from django.conf import settings

settings.DEBUG = True
reset_queries()

# Code run karo
posts = list(Post.objects.all())
for post in posts:
    _ = post.author.name  # N+1 here!

print(f"Queries: {len(connection.queries)}")
# Output: Queries: 101 (1 posts + 100 author queries)

# Fix karo:
reset_queries()
posts = list(Post.objects.select_related('author').all())
for post in posts:
    _ = post.author.name
print(f"Queries after fix: {len(connection.queries)}")
# Output: Queries after fix: 1

# ─── Method 3: Logging ────────────────────────────────────────
# settings.py mein:
LOGGING = {
    'version': 1,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'loggers': {
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'DEBUG',  # production mein OFF rakhna!
        }
    }
}

# ─── Method 4: nplusone library ──────────────────────────────
# pip install nplusone
# Automatically detect karta hai N+1 aur raise karta hai error
```

### Q4: Window functions kab use karein?

**Answer:**

```python
# Window functions use karo jab:

# 1. RANKING chahiye per group (top N per category)
posts = Post.objects.annotate(
    rank=Window(
        expression=Rank(),
        partition_by=[F('category_id')],
        order_by=F('views_count').desc()
    )
)
# Filter top-1 per category: Python mein ya subquery approach

# 2. RUNNING TOTALS / CUMULATIVE SUM
# Revenue report: daily total aur cumulative total

# 3. COMPARISON WITH ADJACENT ROWS (Lag/Lead)
# "Previous order se kitna zyada tha?"

# 4. PERCENTILE / RELATIVE POSITION
# "Ye post top kitne % mein hai?"

# AVOID karo:
# - GROUP BY replace karne ke liye (window + aggregate mix tricky hai)
# - Simple aggregations ke liye (Count, Sum in annotate faster hai)
# - SQLite par (limited window function support)
# - Django < 2.0 (Window support Django 2.0+ mein aaya)

# REMEMBER: Window functions WHERE clause mein directly nahi aate
# Pehle subquery mein wrap karo, phir filter karo
```

### Q5: Raw SQL injection se kaise bachein?

**Answer:**

```python
# RULE: KABHI bhi user input ko string format mein SQL mein mat daalo

# WRONG (SQL injection vulnerable):
user_status = request.GET.get('status', 'published')
Post.objects.raw(f"SELECT * FROM blog_posts WHERE status = '{user_status}'")
# Attacker de sakta hai: ' OR '1'='1 → sab rows expose

# CORRECT (parameterized):
Post.objects.raw(
    "SELECT * FROM blog_posts WHERE status = %s",
    [user_status]   # Django/DB driver automatically escape karta hai
)

# Django ORM hamesha safe hai:
Post.objects.filter(status=user_status)  # automatically parameterized

# connection.cursor() ke saath:
with connection.cursor() as cursor:
    cursor.execute(
        "SELECT * FROM blog_posts WHERE status = %s AND author_id = %s",
        [user_status, user_id]   # list/tuple, never f-string
    )
```

### Q6: get_or_create race condition kab hoti hai aur fix?

**Answer:**

```python
# Race condition scenario:
# Thread 1: SELECT → record nahi mila
# Thread 2: SELECT → record nahi mila (same time)
# Thread 1: INSERT → success
# Thread 2: INSERT → IntegrityError (duplicate key)

# Fix 1: try/except (simple)
from django.db import IntegrityError

try:
    obj, created = Category.objects.get_or_create(
        slug="tech",
        defaults={"name": "Technology"}
    )
except IntegrityError:
    obj = Category.objects.get(slug="tech")
    created = False

# Fix 2: select_for_update (pessimistic locking)
from django.db import transaction

with transaction.atomic():
    # Lock the row if exists
    obj = Category.objects.select_for_update().filter(slug="tech").first()
    if obj is None:
        obj = Category.objects.create(slug="tech", name="Technology")
        created = True
    else:
        created = False

# Fix 3: PostgreSQL upsert (atomic, no race condition)
Category.objects.bulk_create(
    [Category(slug="tech", name="Technology")],
    update_conflicts=True,
    unique_fields=['slug'],
    update_fields=['name']
)
```

### Q7: Subquery mein OuterRef ki depth — nested OuterRef kaise kaam karta hai?

**Answer:**

```python
# Single level OuterRef: outer query ka field reference
latest_comment = Comment.objects.filter(
    post=OuterRef('pk'),   # outer Post queryset ka pk
).order_by('-created_at').values('created_at')[:1]

# Nested OuterRef: 2 levels deep
# (Outer query → Subquery → Sub-Subquery)
from django.db.models import OuterRef

# Author ke kisi bhi post ka latest approved comment
latest_comment_on_author_posts = Comment.objects.filter(
    post__author=OuterRef(OuterRef('pk')),  # OuterRef(OuterRef(...)) = 2 levels up
    is_approved=True
).order_by('-created_at').values('created_at')[:1]

# Ye use hoga jab subquery ke andar aur ek subquery ho
author_has_recent_comments = Exists(
    Post.objects.filter(
        author=OuterRef('pk'),
        # Aur ek Exists inside
        **{'comments__created_at__isnull': False}
    )
)

# Practical note:
# - Zyada levels deep → complex aur slow SQL
# - Aisa code dekha toh refactor karo — intermediate annotation ya raw SQL better hai
```

---

## Quick Reference — When to Use What

| Situation | Recommended Approach |
|-----------|---------------------|
| Related field value fetch (latest/max) | `Subquery + OuterRef` |
| "Koi record hai?" boolean check | `Exists()` |
| Multiple aggregations (count, sum, avg) | `annotate(Count(), Sum())` |
| Bulk insert 100+ rows | `bulk_create(batch_size=200)` |
| Bulk update existing rows | `bulk_update(fields=[...])` |
| Upsert (insert or update) | `update_or_create` ya `bulk_create(update_conflicts=True)` |
| Conditional column values | `Case/When` |
| Ranking / running total / lag-lead | `Window functions` |
| DB-specific functions / complex joins | `Raw SQL (cursor)` |
| Simple filter + update all matching | `queryset.update(field=value)` |

---

## Common Pitfalls

```python
# Pitfall 1: Subquery bina values()[:1] ke — error aayega
bad = Post.objects.filter(author=OuterRef('pk')).order_by('-created_at')[:1]
# Fix: .values('title')[:1]

# Pitfall 2: bulk_create mein save() signals nahi chaltein
# Fix: explicitly call signals ya post_bulk_create signal use karo (Django 4.1+)

# Pitfall 3: bulk_update mein auto_now fields update nahi honge
# Fix: manually set updated_at field aur ushe update_fields mein daalo

# Pitfall 4: Window function ko WHERE mein directly filter — SQL error
# Fix: Subquery wrap ya Python level filter karo

# Pitfall 5: Raw SQL mein PK nahi diya
# Fix: objects.raw() mein id field zaroori hai

# Pitfall 6: connection.cursor() result ke baad cursor close — data lost
# Fix: with connection.cursor() as cursor: use karo (auto-close)
```
