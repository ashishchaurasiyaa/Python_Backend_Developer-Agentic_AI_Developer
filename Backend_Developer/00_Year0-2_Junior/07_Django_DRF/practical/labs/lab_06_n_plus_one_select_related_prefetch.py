"""
Lab 06 — N+1 Problem, select_related, prefetch_related, only/defer
═══════════════════════════════════════════════════════════════════════════════

ARCHITECTURE — Query Execution Model:

    Django ORM is LAZY — queryset sirf evaluate hoti hai jab:
      list(), for loop, len(), repr(), slicing, [n], bool()

    N+1 Problem:
      posts = Post.objects.all()[:10]      ← 1 query (SELECT posts)
      for p in posts:
          print(p.author.email)            ← 1 query PER post (SELECT user WHERE id=?)
      Total: 1 + N = N+1 queries  ← KILLS performance on large datasets

    SELECT_RELATED (SQL JOIN — ForeignKey / OneToOne):
      Post.objects.select_related('author', 'category')[:10]
      → 1 query: SELECT posts JOIN users JOIN categories
      → post.author.email  ← no extra query (already fetched)

    PREFETCH_RELATED (separate query + Python join — ManyToMany / reverse FK):
      Post.objects.prefetch_related('tags')[:10]
      → 2 queries: SELECT posts; SELECT tags WHERE post_id IN (1,2,3...)
      → post.tags.all()    ← no extra query (Python-side cache hit)

    ONLY / DEFER (column-level optimization):
      Post.objects.only('id', 'title', 'author_id')  ← fetch only these cols
      Post.objects.defer('content')                   ← fetch all EXCEPT content
      Use when: fetching posts for list view (don't need 50kb content field)

    ITERATOR (streaming — memory optimization):
      Post.objects.iterator(chunk_size=2000)
      → Fetches in chunks, never loads full dataset into RAM
      → WARNING: disables queryset cache — cannot iterate twice!
      Use for: large exports, ETL, management commands

CONTEXT: Blog API — list view that shows 20 posts with author + tags + comment_count.
         Without optimization: 1 + 20 + 20 + 20 = 61 queries per request!
         With optimization: 4 queries regardless of post count.

RUN:
    cd practical/
    pytest labs/lab_06_n_plus_one_select_related_prefetch.py -v -p no:odoo

SOCH — Answer ALOUD after completing each TODO:
  Q1: select_related vs prefetch_related kab kaunsa? Kyon JOIN ForeignKey ke liye
      better hai but ManyToMany ke liye nahi?
  Q2: Post.objects.only('title') ke baad post.content access karo — kya hoga?
      (Extra query! Defer/only sirf column skip karte hain, deferred access triggers SELECT)
  Q3: prefetch_related ke baad post.tags.filter(name='python') likhne se kya hoga?
      (New query! prefetch cache bypass ho jaata hai. Use Prefetch(queryset=...) instead)
  Q4: iterator() ke saath paginate karna kyon mushkil hai?
  Q5: select_for_update() aur select_related() ek saath kab use karo? Order matters?
"""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.db.models import Count, Prefetch

import factory
from factory.django import DjangoModelFactory
from django.contrib.auth import get_user_model
from django.utils import timezone

from blog.models import Post, Category, Tag, Comment

User = get_user_model()


# ════════════════════════════════════════════════════════════════════════════
# FACTORIES
# ════════════════════════════════════════════════════════════════════════════

class L6UserFactory(DjangoModelFactory):
    class Meta:
        model = User
    email    = factory.Sequence(lambda n: f"l6user{n}@test.com")
    username = factory.Sequence(lambda n: f"l6user{n}")
    password = factory.PostGenerationMethodCall('set_password', 'pass123')

class L6CategoryFactory(DjangoModelFactory):
    class Meta:
        model = Category
    name = factory.Sequence(lambda n: f"L6Cat{n}")

class L6TagFactory(DjangoModelFactory):
    class Meta:
        model = Tag
    name = factory.Sequence(lambda n: f"l6tag{n}")

class L6PostFactory(DjangoModelFactory):
    class Meta:
        model = Post
    title        = factory.Sequence(lambda n: f"L6 Post {n}")
    content      = "Content word " * 60
    excerpt      = "Excerpt."
    author       = factory.SubFactory(L6UserFactory)
    category     = factory.SubFactory(L6CategoryFactory)
    status       = 'published'
    likes_count  = 0
    published_at = factory.LazyFunction(timezone.now)


# ════════════════════════════════════════════════════════════════════════════
# TODO 1 — get_posts_without_optimization()
# ════════════════════════════════════════════════════════════════════════════
"""
Fetch `n` published posts WITHOUT any optimization.
Pattern: Post.objects.filter(status='published')[:n]
This demonstrates N+1 — each author/category/tag access fires extra queries.

Do NOT add select_related / prefetch_related / only / defer.
"""

def get_posts_without_optimization(n: int = 5):
    raise NotImplementedError(
        "TODO 1: Return Post.objects.filter(status='published')[:n] — plain, no optimization"
    )


# ════════════════════════════════════════════════════════════════════════════
# TODO 2 — get_posts_select_related()
# ════════════════════════════════════════════════════════════════════════════
"""
Fetch `n` published posts WITH select_related for FK fields.
Fields to join: 'author', 'category'

select_related('author', 'category') produces ONE SQL with JOINs:
  SELECT posts.*, users.*, categories.*
  FROM blog_posts
  JOIN users ON blog_posts.author_id = users.id
  JOIN blog_categories ON blog_posts.category_id = blog_categories.id
  WHERE blog_posts.status = 'published'
  LIMIT n

After this: post.author.email = NO extra query (fetched via JOIN)
"""

def get_posts_select_related(n: int = 5):
    raise NotImplementedError(
        "TODO 2: Post.objects.filter(...).select_related('author', 'category')[:n]"
    )


# ════════════════════════════════════════════════════════════════════════════
# TODO 3 — get_posts_prefetch_tags()
# ════════════════════════════════════════════════════════════════════════════
"""
Fetch `n` published posts WITH prefetch_related for M2M tags.

prefetch_related produces TWO queries:
  Query 1: SELECT * FROM blog_posts WHERE status='published' LIMIT n
  Query 2: SELECT tags.*, post_tags.post_id
           FROM blog_tags JOIN blog_post_tags ON ...
           WHERE blog_post_tags.post_id IN (1, 2, 3, ...)

After this: post.tags.all() = NO extra query (Python-side cache)
"""

def get_posts_prefetch_tags(n: int = 5):
    raise NotImplementedError(
        "TODO 3: Post.objects.filter(...).prefetch_related('tags')[:n]"
    )


# ════════════════════════════════════════════════════════════════════════════
# TODO 4 — get_posts_fully_optimized()
# ════════════════════════════════════════════════════════════════════════════
"""
Production-ready: all optimizations combined for a list API endpoint.

Requirements:
  1. select_related('author', 'category')     ← FK joins (1 query total)
  2. prefetch_related('tags')                  ← M2M prefetch (1 extra query)
  3. Prefetch('comments', queryset=Comment.objects.filter(is_approved=True))
     ← Prefetch with custom queryset (1 extra query, not N)
  4. annotate(comment_count=Count('comments', distinct=True))
     ← comment count via SQL (not Python loop)
  5. only('id', 'title', 'slug', 'excerpt', 'status', 'published_at',
          'likes_count', 'author_id', 'category_id')
     ← Only fetch columns needed for list view (skip heavy 'content' field)
  6. filter(status='published').order_by('-published_at')[:n]

After this: accessing author.email, category.name, tags.all(), comment_count
            ZERO extra queries beyond the initial ~3-4.
"""

def get_posts_fully_optimized(n: int = 5):
    raise NotImplementedError(
        "TODO 4: Combine select_related + prefetch_related(Prefetch) + annotate + only"
    )


# ════════════════════════════════════════════════════════════════════════════
# TODO 5 — get_posts_iterator()
# ════════════════════════════════════════════════════════════════════════════
"""
For large exports (e.g., CSV of 100k posts) — use iterator() to stream.

Requirements:
  1. Post.objects.filter(status='published').only('id', 'title', 'published_at')
  2. .iterator(chunk_size=1000)    ← yields in chunks, no full RAM load
  3. Return a list (for testing — in production you'd yield/write directly)

NOTE: iterator() disables queryset cache. Cannot call list() twice on same iterator.
"""

def get_posts_iterator(chunk_size: int = 1000) -> list:
    raise NotImplementedError(
        "TODO 5: Post.objects.filter(...).only(...).iterator(chunk_size=chunk_size)"
        " — return list(queryset)"
    )


# ════════════════════════════════════════════════════════════════════════════
# TESTS
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_without_optimization_accesses_author_causes_n_plus_1():
    """Each post.author access fires a separate query — classic N+1."""
    for _ in range(5):
        L6PostFactory()

    with CaptureQueriesContext(connection) as ctx:
        posts = get_posts_without_optimization(5)
        _ = [p.author.email for p in posts]    # Triggers N+1
        _ = [p.category.name for p in posts]   # Another N more queries

    n_queries = len(ctx.captured_queries)
    assert n_queries >= 6, (
        f"FAIL: Expected >= 6 queries (N+1 not demonstrated). Got {n_queries}. "
        "Make sure TODO 1 does NOT use select_related."
    )


@pytest.mark.django_db
def test_select_related_reduces_to_single_query():
    """select_related produces exactly 1 SQL JOIN query."""
    for _ in range(5):
        L6PostFactory()

    with CaptureQueriesContext(connection) as ctx:
        posts = get_posts_select_related(5)
        _ = [p.author.email for p in posts]    # No extra queries!
        _ = [p.category.name for p in posts]   # No extra queries!

    n_queries = len(ctx.captured_queries)
    assert n_queries == 1, (
        f"FAIL: select_related should produce 1 query (SQL JOIN). Got {n_queries}. "
        "Check TODO 2 — are you using select_related('author', 'category')?"
    )


@pytest.mark.django_db
def test_select_related_queries_less_than_unoptimized():
    """Proof: optimized uses far fewer queries than unoptimized for same data."""
    for _ in range(5):
        p = L6PostFactory()
        p.tags.add(L6TagFactory(), L6TagFactory())

    with CaptureQueriesContext(connection) as ctx_bad:
        posts = get_posts_without_optimization(5)
        _ = [p.author.email for p in posts]

    with CaptureQueriesContext(connection) as ctx_good:
        posts = get_posts_select_related(5)
        _ = [p.author.email for p in posts]

    assert len(ctx_good.captured_queries) < len(ctx_bad.captured_queries), (
        f"FAIL: Optimized ({len(ctx_good.captured_queries)}) should use fewer queries "
        f"than unoptimized ({len(ctx_bad.captured_queries)})"
    )


@pytest.mark.django_db
def test_prefetch_tags_uses_two_queries():
    """prefetch_related fires 2 queries total: 1 for posts, 1 for all tags."""
    for _ in range(5):
        p = L6PostFactory()
        p.tags.add(L6TagFactory(), L6TagFactory(), L6TagFactory())

    with CaptureQueriesContext(connection) as ctx:
        posts = get_posts_prefetch_tags(5)
        _ = [list(p.tags.all()) for p in posts]   # No N queries!

    n_queries = len(ctx.captured_queries)
    assert n_queries == 2, (
        f"FAIL: prefetch_related should produce exactly 2 queries. Got {n_queries}. "
        "Check TODO 3 — use .prefetch_related('tags')"
    )


@pytest.mark.django_db
def test_prefetch_all_tags_fetched_correctly():
    """Each post gets its own tags, not mixed."""
    p1 = L6PostFactory()
    p2 = L6PostFactory()
    tag_a = L6TagFactory(name="python")
    tag_b = L6TagFactory(name="django")
    p1.tags.add(tag_a)
    p2.tags.add(tag_b)

    posts = get_posts_prefetch_tags(10)
    post_map = {p.id: list(p.tags.all()) for p in posts}

    assert any(tag_a in tags for tags in post_map.values()), (
        "FAIL: tag 'python' not found in any prefetched post"
    )
    assert any(tag_b in tags for tags in post_map.values()), (
        "FAIL: tag 'django' not found in any prefetched post"
    )


@pytest.mark.django_db
def test_fully_optimized_min_queries():
    """Production pattern: all optimizations → <= 4 queries regardless of N."""
    for _ in range(8):
        p = L6PostFactory()
        p.tags.add(L6TagFactory())
        Comment.objects.create(
            post=p, author=L6UserFactory(), content="Test comment", is_approved=True
        )

    with CaptureQueriesContext(connection) as ctx:
        posts = get_posts_fully_optimized(8)
        # Access everything — should not cause extra queries
        for p in posts:
            _ = p.author.email
            _ = p.category.name
            _ = list(p.tags.all())
            _ = getattr(p, 'comment_count', None)

    n_queries = len(ctx.captured_queries)
    assert n_queries <= 5, (
        f"FAIL: Fully optimized should use <= 5 queries. Got {n_queries}. "
        "Check TODO 4 — combine select_related + prefetch_related + annotate + only"
    )


@pytest.mark.django_db
def test_fully_optimized_data_correct():
    """Optimization must not break data correctness."""
    author = L6UserFactory()
    cat    = L6CategoryFactory(name="Tech")
    tag    = L6TagFactory(name="python")
    post   = L6PostFactory(author=author, category=cat, title="Optimized Post")
    post.tags.add(tag)

    posts = get_posts_fully_optimized(10)
    found = next((p for p in posts if p.title == "Optimized Post"), None)

    assert found is not None, "FAIL: Post not found in optimized queryset"
    assert found.author.email == author.email, "FAIL: author.email wrong after select_related"
    assert found.category.name == "Tech", "FAIL: category.name wrong after select_related"
    assert tag in list(found.tags.all()), "FAIL: tag not in tags after prefetch_related"


@pytest.mark.django_db
def test_iterator_returns_posts():
    """iterator() streams posts without loading all into RAM."""
    for _ in range(10):
        L6PostFactory()

    result = get_posts_iterator(chunk_size=3)
    assert isinstance(result, list), "FAIL: iterator() result should be converted to list"
    assert len(result) > 0, "FAIL: iterator() returned empty — are there published posts?"
    assert hasattr(result[0], 'title'), "FAIL: items should be Post instances"


@pytest.mark.django_db
def test_only_skips_content_column():
    """only() fetches fewer columns — content not loaded initially."""
    L6PostFactory(content="A very long blog post content " * 100)

    with CaptureQueriesContext(connection) as ctx:
        # only() in fully optimized means content NOT fetched in main query
        posts = get_posts_fully_optimized(5)
        titles = [p.title for p in posts]   # No extra query (title in only())

    # If only() is working, accessing title should not cause deferred loading
    assert all(isinstance(t, str) for t in titles), (
        "FAIL: titles should be strings — only('title', ...) must include title"
    )


# ════════════════════════════════════════════════════════════════════════════
# BONUS DEMO (no TODO — shows the gotcha interviewers ask about)
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_prefetch_bypass_gotcha():
    """
    GOTCHA: prefetch_related cache is BYPASSED by .filter() calls.
    post.tags.filter(name='python') fires a NEW query even after prefetch!
    Fix: use Prefetch(queryset=Tag.objects.filter(name='python')) at queryset level.
    """
    p = L6PostFactory()
    t1 = L6TagFactory(name="python")
    t2 = L6TagFactory(name="django")
    p.tags.add(t1, t2)

    posts = Post.objects.prefetch_related('tags').filter(id=p.id)

    with CaptureQueriesContext(connection) as ctx_bypass:
        _ = posts[0].tags.filter(name='python')   # Bypasses prefetch cache!

    with CaptureQueriesContext(connection) as ctx_cache:
        _ = list(posts[0].tags.all())              # Uses prefetch cache

    assert len(ctx_bypass.captured_queries) > 0, (
        "FAIL: .filter() after prefetch should bypass cache and fire a query"
    )
    # ctx_cache might have 0 queries (already evaluated) or 1 — both fine
    # The point: filter() = new query; all() = cache hit (after first eval)


# ════════════════════════════════════════════════════════════════════════════
# SOCH
# ════════════════════════════════════════════════════════════════════════════

"""
SOCH (Answer ALOUD before next lab):

Q1: N+1 problem mein "N" kya hai? Agar 100 posts list karo bina select_related ke
    aur har post.author.email access karo — total kitne queries jaayenge?

Q2: select_related('author__profile') kya karta hai?
    (Double underscore = JOIN through relationship: posts JOIN users JOIN user_profiles)

Q3: prefetch_related ke baad mein post.tags.filter(active=True) karna kyon galat hai?
    Correct solution kya hai? (Hint: Prefetch object with queryset parameter)

Q4: only('title') ke baad post.content access karne par kya hoga?
    (Deferred field access — extra SELECT query per object!)

Q5: Production mein yeh pattern kab use karo?
    select_related: _______
    prefetch_related: _______
    only: _______
    defer: _______
    iterator: _______
"""
