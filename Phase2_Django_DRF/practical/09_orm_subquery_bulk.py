"""
Django Advanced ORM — Subquery, Exists, Raw SQL, Bulk Ops
Run as Django management command or standalone with django.setup()

This file contains standalone code snippets + demo functions.
Copy-paste these into your Django project.

Setup: These examples use models from the blog app in this project.

Run from project root:
    python manage.py shell
    exec(open('practical/09_orm_subquery_bulk.py').read())
    main()

Or as script:
    python practical/09_orm_subquery_bulk.py
"""

import os
import sys
import time


# ─── Django setup (standalone mode ke liye) ───────────────────────────────────
def setup_django():
    """Django setup for running this file as standalone script."""
    # Project root find karo (manage.py wali directory)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, project_root)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

    import django
    django.setup()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION A: Subquery & OuterRef
# ─────────────────────────────────────────────────────────────────────────────

def demo_subquery_outerref():
    """
    INTERVIEW TOPIC: Subquery + OuterRef
    ─────────────────────────────────────
    OuterRef = outer query ka field reference inner subquery mein karo.
    Subquery = nested SELECT — ek single value return karta hai.

    Rule: Subquery mein .values('field')[:1] zaroori hai — ek column, ek row.
    """
    from django.db.models import OuterRef, Subquery, Count, Max
    from blog.models import Post, Comment
    from django.contrib.auth import get_user_model

    User = get_user_model()

    print("=" * 60)
    print("DEMO: Subquery + OuterRef")
    print("=" * 60)

    # ─── Example 1: Har user ka latest post title ─────────────
    print("\n[1] Har user ka latest post title (Subquery):")

    latest_post_sq = Post.objects.filter(
        author=OuterRef('pk'),          # outer User query ka pk
        status='published',
        deleted_at__isnull=True,
    ).order_by('-published_at').values('title')[:1]

    users = User.objects.annotate(
        latest_post_title=Subquery(latest_post_sq)
    )[:5]

    try:
        for user in users:
            title = user.latest_post_title or "(no posts)"
            print(f"  {user.email[:30]}: {title[:50]}")
        print(f"\n  Generated SQL snippet:")
        # SQL print karo — actual Subquery part
        print(f"  {str(users.query)[:300]}...")
    except Exception as e:
        print(f"  [DB not available — showing SQL pattern only]")
        print(f"  SQL would be:")
        print("""
  SELECT auth_user.id, auth_user.email,
    (SELECT title FROM blog_posts
     WHERE author_id = auth_user.id
       AND status = 'published'
       AND deleted_at IS NULL
     ORDER BY published_at DESC
     LIMIT 1) AS latest_post_title
  FROM auth_user
        """)

    # ─── Example 2: Har post ka latest comment date ───────────
    print("\n[2] Har post ka latest approved comment date:")

    latest_comment_sq = Comment.objects.filter(
        post=OuterRef('pk'),
        is_approved=True,
    ).order_by('-created_at').values('created_at')[:1]

    posts = Post.objects.filter(
        status='published',
        deleted_at__isnull=True,
    ).annotate(
        latest_comment_at=Subquery(latest_comment_sq)
    ).order_by('-latest_comment_at')[:5]

    try:
        for post in posts:
            lat = post.latest_comment_at or "no comments"
            print(f"  {post.title[:40]}: last comment={lat}")
    except Exception as e:
        print(f"  [DB not available] Error: {e}")

    # ─── Example 3: Multiple Subqueries ek annotate mein ──────
    print("\n[3] Multiple Subqueries ek annotate mein:")

    latest_title_sq = Post.objects.filter(
        author=OuterRef('pk'), deleted_at__isnull=True,
    ).order_by('-created_at').values('title')[:1]

    latest_publish_sq = Post.objects.filter(
        author=OuterRef('pk'), status='published', deleted_at__isnull=True,
    ).order_by('-published_at').values('published_at')[:1]

    users_annotated = User.objects.annotate(
        latest_post_title=Subquery(latest_title_sq),
        latest_published_at=Subquery(latest_publish_sq),
    )[:3]

    try:
        for user in users_annotated:
            print(f"  {user.email}: title='{user.latest_post_title}', "
                  f"published={user.latest_published_at}")
    except Exception as e:
        print(f"  [DB not available] Error: {e}")

    print("\n[PATTERN] Subquery best use cases:")
    print("  - Single correlated value (latest, max, min of related)")
    print("  - When JOIN would cause duplicate rows")
    print("  - EXISTS checks (use Exists() class for boolean)")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION B: Exists()
# ─────────────────────────────────────────────────────────────────────────────

def demo_exists():
    """
    INTERVIEW TOPIC: Exists()
    ─────────────────────────
    EXISTS = pehli matching row mile aur ruk jao (short circuit).
    COUNT(*) = poori scan karta hai.
    Exists() is always better than .count() > 0 for boolean checks.
    """
    from django.db.models import Exists, OuterRef, Count, Q
    from blog.models import Post, Comment

    print("\n" + "=" * 60)
    print("DEMO: Exists()")
    print("=" * 60)

    # ─── Example 1: Annotate with boolean ─────────────────────
    print("\n[1] Posts ko annotate karo — has approved comments?")

    has_approved_comments = Comment.objects.filter(
        post=OuterRef('pk'),
        is_approved=True,
    )

    posts = Post.objects.filter(
        status='published',
        deleted_at__isnull=True,
    ).annotate(
        has_comments=Exists(has_approved_comments)
    )[:5]

    try:
        for post in posts:
            print(f"  {post.title[:40]}: has_comments={post.has_comments}")

        # SQL show karo
        print(f"\n  Total posts checked: {posts.count()}")
        print(f"  With comments: {posts.filter(has_comments=True).count()}")
    except Exception as e:
        print(f"  [DB not available] SQL pattern:")
        print("""
  SELECT *, EXISTS(
    SELECT 1 FROM blog_comments
    WHERE post_id = blog_posts.id AND is_approved = TRUE
  ) AS has_comments
  FROM blog_posts WHERE status = 'published'
        """)

    # ─── Example 2: Filter with Exists ────────────────────────
    print("\n[2] Filter: sirf wahi posts jinhein approved comments hain:")

    posts_with_comments = Post.objects.filter(
        status='published',
        deleted_at__isnull=True,
    ).filter(
        Exists(
            Comment.objects.filter(
                post=OuterRef('pk'),
                is_approved=True
            )
        )
    )

    try:
        count = posts_with_comments.count()
        print(f"  Posts with approved comments: {count}")
        print(f"  SQL: {str(posts_with_comments.query)[:200]}...")
    except Exception as e:
        print(f"  [DB not available] Error: {e}")

    # ─── Example 3: NOT Exists — ~ operator ───────────────────
    print("\n[3] NOT Exists — posts jinmein koi bhi comment nahi:")

    posts_no_comments = Post.objects.filter(
        status='published',
        deleted_at__isnull=True,
    ).filter(
        ~Exists(
            Comment.objects.filter(post=OuterRef('pk'))
        )
    )

    try:
        count = posts_no_comments.count()
        print(f"  Posts with NO comments: {count}")
    except Exception as e:
        print(f"  [DB not available] Error: {e}")

    # ─── Performance comparison ────────────────────────────────
    print("\n[4] Performance comparison — Exists vs Count > 0:")
    print("  EXISTS:      pehli match pe ruk jata hai (O(1) best case)")
    print("  COUNT(*) > 0: poora table scan (O(n) always)")
    print("  RULE: boolean check ke liye hamesha Exists() use karo")

    print("\n[PATTERN] Exists use cases:")
    print("  - Filter: 'wahi records jo related records rakhte hain'")
    print("  - Annotate: 'has_X' boolean column add karo")
    print("  - ~Exists: 'wahi records jo related records NAHI rakhte'")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION C: Raw SQL
# ─────────────────────────────────────────────────────────────────────────────

def demo_raw_sql():
    """
    INTERVIEW TOPIC: Raw SQL — objects.raw() vs connection.cursor()
    ─────────────────────────────────────────────────────────────────
    objects.raw()      → Model instances milte hain (ORM-like)
    connection.cursor() → Pure tuples / dict — full control

    GOLDEN RULE: KABHI bhi f-string/format se SQL mat banao — ALWAYS parameterized!
    """
    from django.db import connection
    from blog.models import Post

    print("\n" + "=" * 60)
    print("DEMO: Raw SQL")
    print("=" * 60)

    # ─── Helper: cursor results → list of dicts ───────────────
    def dictfetchall(cursor):
        """Cursor results ko list of dicts mein convert karo."""
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def dictfetchone(cursor):
        """Single row dict."""
        columns = [col[0] for col in cursor.description]
        row = cursor.fetchone()
        return dict(zip(columns, row)) if row else None

    # ─── Example 1: objects.raw() ─────────────────────────────
    print("\n[1] objects.raw() — model instances:")
    try:
        posts = Post.objects.raw(
            """
            SELECT p.id, p.title, p.views_count,
                   COUNT(c.id) AS comment_count
            FROM blog_posts p
            LEFT JOIN blog_comments c ON c.post_id = p.id AND c.is_approved = TRUE
            WHERE p.status = %s AND p.deleted_at IS NULL
            GROUP BY p.id
            ORDER BY p.views_count DESC
            LIMIT %s
            """,
            ['published', 5]
        )
        for post in posts:
            # Extra columns (comment_count) bhi accessible hain
            print(f"  {post.title[:40]}: {post.comment_count} comments, "
                  f"{post.views_count} views")
    except Exception as e:
        print(f"  [DB not available] Error: {e}")
        print("  SQL: SELECT id, title, views_count, COUNT(c.id) AS comment_count")
        print("       FROM blog_posts p LEFT JOIN blog_comments c ...")
        print("       WHERE p.status = %s GROUP BY p.id ORDER BY views_count DESC")

    # ─── Example 2: connection.cursor() ───────────────────────
    print("\n[2] connection.cursor() — raw query, dict results:")
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    bc.name AS category_name,
                    COUNT(DISTINCT p.id) AS post_count,
                    COALESCE(SUM(p.views_count), 0) AS total_views,
                    COALESCE(MAX(p.views_count), 0) AS max_views
                FROM blog_categories bc
                LEFT JOIN blog_posts p ON p.category_id = bc.id
                    AND p.status = %s
                    AND p.deleted_at IS NULL
                GROUP BY bc.id, bc.name
                ORDER BY total_views DESC
            """, ['published'])

            results = dictfetchall(cursor)

        for row in results[:5]:
            print(f"  {row['category_name']}: {row['post_count']} posts, "
                  f"{row['total_views']} views (max: {row['max_views']})")
    except Exception as e:
        print(f"  [DB not available] Error: {e}")
        print("  SQL: SELECT bc.name, COUNT(p.id), SUM(views_count), MAX(views_count)")
        print("       FROM blog_categories bc LEFT JOIN blog_posts p ...")

    # ─── Example 3: fetchone vs fetchmany vs fetchall ─────────
    print("\n[3] fetchone / fetchmany / fetchall:")
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, title FROM blog_posts WHERE status = %s AND deleted_at IS NULL LIMIT 20",
                ['published']
            )
            first_row   = cursor.fetchone()         # ek tuple ya None
            next_5_rows = cursor.fetchmany(5)       # list of tuples (memory efficient)
            rest        = cursor.fetchall()          # baaki saare

        print(f"  fetchone:  {first_row}")
        print(f"  fetchmany(5): {len(next_5_rows)} rows")
        print(f"  fetchall (rest): {len(rest)} rows")
    except Exception as e:
        print(f"  [DB not available] Error: {e}")

    # ─── Example 4: Transactions with raw SQL ─────────────────
    print("\n[4] Transaction with raw SQL:")
    print("  [Showing pattern — not executing to avoid data modification]")
    print("""
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
      # Dono queries ek saath commit ya rollback
    """)

    # ─── SQL Injection warning ─────────────────────────────────
    print("[WARNING] SQL Injection Prevention:")
    print("  NEVER: cursor.execute(f\"WHERE id = {user_input}\")")
    print("  ALWAYS: cursor.execute(\"WHERE id = %s\", [user_input])")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION D: Bulk Create
# ─────────────────────────────────────────────────────────────────────────────

def demo_bulk_create():
    """
    INTERVIEW TOPIC: bulk_create performance comparison
    ─────────────────────────────────────────────────────
    Loop .save()  = N queries → slow
    bulk_create() = ceil(N/batch_size) queries → fast (100x+)

    Caveats:
    - save() signals (pre_save, post_save) nahi chalti
    - auto_now fields set nahi honge (manually set karo)
    - update_conflicts PostgreSQL-only
    """
    from blog.models import Tag
    from django.db import connection, reset_queries
    from django.conf import settings

    print("\n" + "=" * 60)
    print("DEMO: bulk_create — Performance Comparison")
    print("=" * 60)

    # Cleanup first
    try:
        Tag.objects.filter(name__startswith="PerfTest").delete()
    except Exception:
        pass

    # ─── Method 1: Loop .save() ───────────────────────────────
    print("\n[1] Loop .save() — N queries:")
    try:
        settings.DEBUG = True
        reset_queries()

        start = time.time()
        for i in range(50):   # 50 se test karo (100 too slow in demo)
            Tag.objects.create(
                name=f"PerfTest Loop {i:03d}",
                slug=f"perftest-loop-{i:03d}",
                color="#FF0000"
            )
        loop_time = time.time() - start
        loop_queries = len(connection.queries)

        print(f"  Rows: 50")
        print(f"  Time: {loop_time:.3f}s")
        print(f"  Queries: {loop_queries}")

        # Cleanup
        Tag.objects.filter(name__startswith="PerfTest Loop").delete()
    except Exception as e:
        print(f"  [DB not available] Error: {e}")
        loop_time = 1.0
        loop_queries = 50

    # ─── Method 2: bulk_create ────────────────────────────────
    print("\n[2] bulk_create — ceil(N/batch_size) queries:")
    try:
        reset_queries()

        tags_to_create = [
            Tag(
                name=f"PerfTest Bulk {i:03d}",
                slug=f"perftest-bulk-{i:03d}",
                color="#00FF00"
            )
            for i in range(50)
        ]

        start = time.time()
        created = Tag.objects.bulk_create(
            tags_to_create,
            batch_size=20,           # 50 / 20 = 3 queries
            ignore_conflicts=True,   # duplicate slug? skip
        )
        bulk_time = time.time() - start
        bulk_queries = len(connection.queries)

        print(f"  Rows: 50")
        print(f"  Time: {bulk_time:.3f}s")
        print(f"  Queries: {bulk_queries}")
        if loop_time and bulk_time:
            speedup = loop_time / bulk_time if bulk_time > 0 else 0
            print(f"  Speedup: ~{speedup:.1f}x faster")

        # Cleanup
        Tag.objects.filter(name__startswith="PerfTest Bulk").delete()
    except Exception as e:
        print(f"  [DB not available] Error: {e}")

    # ─── Example: update_conflicts (PostgreSQL) ───────────────
    print("\n[3] update_conflicts — upsert pattern (PostgreSQL only):")
    print("""
  tags = [
      Tag(name="Python",  slug="python",  color="#3572A5"),
      Tag(name="Django",  slug="django",  color="#0C4B33"),
      Tag(name="REST",    slug="rest",    color="#FF6B35"),
  ]

  # ON CONFLICT (slug) DO UPDATE SET name=..., color=...
  Tag.objects.bulk_create(
      tags,
      update_conflicts=True,
      unique_fields=['slug'],           # conflict detect karne ke liye
      update_fields=['name', 'color'],  # update karne wale fields
  )
    """)

    # ─── Performance table ────────────────────────────────────
    print("[SUMMARY] Performance Comparison (1000 rows estimate):")
    print("  Loop .save()    : ~1000 queries, ~2000ms")
    print("  bulk_create(200): ~5 queries,    ~20ms   (~100x faster)")
    print("  queryset.update(): 1 query,       ~5ms   (uniform change ke liye)")

    print("\n[GOTCHAS] bulk_create caveats:")
    print("  - pre_save / post_save signals nahi chalti")
    print("  - Model.save() bypass hota hai")
    print("  - auto_now (updated_at) fields update nahi honge")
    print("  - update_conflicts: PostgreSQL 9.5+ only")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION E: Bulk Update
# ─────────────────────────────────────────────────────────────────────────────

def demo_bulk_update():
    """
    INTERVIEW TOPIC: bulk_update
    ─────────────────────────────
    Specific fields ko batch mein update karo — much faster than loop .save().
    Sirf specified fields update honge — full save nahi.
    """
    from blog.models import Tag
    from django.utils import timezone

    print("\n" + "=" * 60)
    print("DEMO: bulk_update")
    print("=" * 60)

    # ─── Example 1: Bulk update specific fields ───────────────
    print("\n[1] Tags ke colors batch update karo:")
    try:
        # Setup: kuch tags create karo
        Tag.objects.filter(name__startswith="BulkUpdateTest").delete()
        test_tags = Tag.objects.bulk_create([
            Tag(name=f"BulkUpdateTest {i}", slug=f"bulk-update-test-{i}", color="#000000")
            for i in range(10)
        ], ignore_conflicts=True)

        # Fetch, modify, bulk_update
        tags = list(Tag.objects.filter(name__startswith="BulkUpdateTest"))
        new_colors = ["#FF0000", "#00FF00", "#0000FF", "#FFFF00", "#FF00FF",
                      "#00FFFF", "#FF8800", "#8800FF", "#00FF88", "#FF0088"]

        for i, tag in enumerate(tags):
            tag.color = new_colors[i % len(new_colors)]

        from django.db import connection, reset_queries
        from django.conf import settings
        settings.DEBUG = True
        reset_queries()

        start = time.time()
        updated = Tag.objects.bulk_update(
            tags,
            fields=['color'],   # sirf color update karo
            batch_size=5        # 10 / 5 = 2 queries
        )
        elapsed = time.time() - start

        print(f"  Updated {updated} tags in {elapsed:.3f}s")
        print(f"  Queries used: {len(connection.queries)} (batch_size=5 → 2 UPDATE queries)")

        # Verify
        updated_tags = Tag.objects.filter(name__startswith="BulkUpdateTest")
        for tag in updated_tags[:3]:
            print(f"  {tag.name}: {tag.color}")

        # Cleanup
        Tag.objects.filter(name__startswith="BulkUpdateTest").delete()
    except Exception as e:
        print(f"  [DB not available] Error: {e}")

    # ─── Example 2: bulk_update with auto_now fix ─────────────
    print("\n[2] bulk_update + updated_at manual set:")
    print("""
  # PROBLEM: bulk_update does NOT trigger auto_now
  # SOLUTION: manually set updated_at aur ushe fields mein daalo

  posts = list(Post.objects.filter(status='draft')[:100])
  now = timezone.now()

  for post in posts:
      post.status = 'archived'
      post.updated_at = now      # manually set karo

  Post.objects.bulk_update(
      posts,
      fields=['status', 'updated_at'],   # updated_at bhi include
      batch_size=50
  )
    """)

    # ─── Example 3: bulk_update vs queryset.update() ──────────
    print("\n[3] bulk_update vs queryset.update() — kab kya?")
    print("  bulk_update:      per-object different values (e.g., each tag different color)")
    print("  queryset.update(): sab rows ko ek hi value (e.g., all drafts → archived)")
    print()
    print("  # queryset.update() — fastest for uniform change:")
    print("  Post.objects.filter(status='draft').update(status='archived')")
    print("  # → 1 query: UPDATE blog_posts SET status='archived' WHERE status='draft'")
    print()
    print("  # bulk_update — per-object different value:")
    print("  Post.objects.bulk_update(posts, ['title', 'content'], batch_size=100)")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION F: get_or_create & update_or_create
# ─────────────────────────────────────────────────────────────────────────────

def demo_get_or_create():
    """
    INTERVIEW TOPIC: get_or_create, update_or_create
    ──────────────────────────────────────────────────
    get_or_create    = fetch or insert (lookup fields ki unique constraint chahiye)
    update_or_create = upsert (insert ya update)
    Thread safety: race condition possible — use IntegrityError handling
    """
    from blog.models import Category, Tag
    from django.db import IntegrityError, transaction

    print("\n" + "=" * 60)
    print("DEMO: get_or_create & update_or_create")
    print("=" * 60)

    # ─── Example 1: get_or_create ─────────────────────────────
    print("\n[1] get_or_create — fetch existing ya create new:")
    try:
        category, created = Category.objects.get_or_create(
            name="Demo Technology",         # lookup fields → WHERE clause
            defaults={                       # sirf create hone pe use hoga
                "slug": "demo-technology",
                "description": "Demo category for testing"
            }
        )
        status = "CREATED" if created else "FOUND"
        print(f"  {status}: {category.name} (id={category.id})")

        # Dobara call karo — same object milega
        category2, created2 = Category.objects.get_or_create(
            name="Demo Technology",
            defaults={"slug": "demo-technology-2"}  # defaults ignore honge
        )
        print(f"  Second call: {'CREATED' if created2 else 'FOUND'} (id={category2.id})")
        print(f"  Same object? {category.id == category2.id}")
    except Exception as e:
        print(f"  [DB not available] Error: {e}")

    # ─── Thread Safety Note ───────────────────────────────────
    print("\n[2] Thread Safety — IntegrityError handling:")
    print("""
  # Race condition scenario:
  # Thread 1: SELECT → not found
  # Thread 2: SELECT → not found (same time)
  # Thread 1: INSERT → success
  # Thread 2: INSERT → IntegrityError (slug unique constraint!)

  # SAFE pattern:
  from django.db import IntegrityError

  try:
      obj, created = Category.objects.get_or_create(
          slug="tech",
          defaults={"name": "Technology"}
      )
  except IntegrityError:
      # Race condition — kisi aur ne already create kar diya
      obj = Category.objects.get(slug="tech")
      created = False
    """)

    # ─── Example 2: update_or_create ──────────────────────────
    print("\n[3] update_or_create — upsert pattern:")
    try:
        # First call: create
        tag, created = Tag.objects.update_or_create(
            slug="demo-django",                    # lookup
            defaults={                             # create ya update dono mein
                "name": "Demo Django",
                "color": "#0C4B33"
            }
        )
        print(f"  First call: {'CREATED' if created else 'UPDATED'} — "
              f"'{tag.name}' color={tag.color}")

        # Second call: update
        tag2, created2 = Tag.objects.update_or_create(
            slug="demo-django",
            defaults={"name": "Demo Django Framework", "color": "#1A6B4A"}
        )
        print(f"  Second call: {'CREATED' if created2 else 'UPDATED'} — "
              f"'{tag2.name}' color={tag2.color}")

        # Cleanup
        Tag.objects.filter(slug="demo-django").delete()
    except Exception as e:
        print(f"  [DB not available] Error: {e}")

    # ─── Example 3: PostgreSQL native upsert ──────────────────
    print("\n[4] PostgreSQL native upsert (bulk_create + update_conflicts):")
    print("""
  # Atomic upsert — no race condition, fastest approach
  tags = [
      Tag(name="Python",  slug="python",  color="#3572A5"),
      Tag(name="Django",  slug="django",  color="#0C4B33"),
  ]

  Tag.objects.bulk_create(
      tags,
      update_conflicts=True,
      unique_fields=['slug'],           # ON CONFLICT (slug)
      update_fields=['name', 'color'],  # DO UPDATE SET ...
  )
  # SQL: INSERT INTO ... ON CONFLICT (slug) DO UPDATE SET name=..., color=...
    """)

    # Cleanup
    try:
        Category.objects.filter(name="Demo Technology").delete()
    except Exception:
        pass

    print("\n[SUMMARY] get_or_create vs update_or_create:")
    print("  get_or_create:    existing mila → return as-is (no update)")
    print("  update_or_create: existing mila → defaults se update karo")
    print("  bulk_create(update_conflicts): PostgreSQL native, fastest, atomic")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION G: Case/When Annotations
# ─────────────────────────────────────────────────────────────────────────────

def demo_case_when():
    """
    INTERVIEW TOPIC: Case/When — conditional annotations
    ──────────────────────────────────────────────────────
    SQL CASE WHEN THEN ELSE END ka ORM representation.
    Use karo jab: conditional string label, conditional count/sum,
    conditional numeric calculation needed ho.
    """
    from django.db.models import Case, When, Value, CharField, IntegerField, Sum, F, Q
    from blog.models import Post
    from django.contrib.auth import get_user_model

    User = get_user_model()

    print("\n" + "=" * 60)
    print("DEMO: Case/When — Conditional Annotations")
    print("=" * 60)

    # ─── Example 1: Conditional string label ──────────────────
    print("\n[1] Conditional engagement level annotation:")
    try:
        posts = Post.objects.filter(
            status='published',
            deleted_at__isnull=True,
        ).annotate(
            engagement_level=Case(
                When(views_count__lt=100,   then=Value("low")),
                When(views_count__lt=1000,  then=Value("medium")),
                When(views_count__lt=10000, then=Value("high")),
                default=Value("viral"),
                output_field=CharField()
            )
        ).order_by('-views_count')[:8]

        for post in posts:
            print(f"  [{post.engagement_level:8s}] {post.title[:35]} ({post.views_count} views)")
    except Exception as e:
        print(f"  [DB not available] Error: {e}")
        print("""
  SQL equivalent:
  SELECT *,
    CASE
      WHEN views_count < 100   THEN 'low'
      WHEN views_count < 1000  THEN 'medium'
      WHEN views_count < 10000 THEN 'high'
      ELSE 'viral'
    END AS engagement_level
  FROM blog_posts WHERE status = 'published'
        """)

    # ─── Example 2: Conditional COUNT per author ──────────────
    print("\n[2] Author stats — conditional count:")
    try:
        authors = User.objects.annotate(
            published_count=Sum(
                Case(
                    When(posts__status='published', posts__deleted_at__isnull=True, then=1),
                    default=0,
                    output_field=IntegerField()
                )
            ),
            draft_count=Sum(
                Case(
                    When(posts__status='draft', posts__deleted_at__isnull=True, then=1),
                    default=0,
                    output_field=IntegerField()
                )
            ),
            featured_count=Sum(
                Case(
                    When(posts__is_featured=True, posts__deleted_at__isnull=True, then=1),
                    default=0,
                    output_field=IntegerField()
                )
            ),
        ).filter(
            Q(published_count__gt=0) | Q(draft_count__gt=0)
        )[:5]

        for author in authors:
            print(f"  {author.email[:30]}: "
                  f"published={author.published_count}, "
                  f"draft={author.draft_count}, "
                  f"featured={author.featured_count}")
    except Exception as e:
        print(f"  [DB not available] Error: {e}")

    # ─── Example 3: Case/When with F() ────────────────────────
    print("\n[3] Conditional weighted score with F():")
    try:
        posts = Post.objects.filter(
            status='published',
            deleted_at__isnull=True,
        ).annotate(
            weighted_score=Case(
                When(is_featured=True, then=F('views_count') * 2 + F('likes_count') * 5),
                default=F('views_count') + F('likes_count') * 3,
                output_field=IntegerField()
            )
        ).order_by('-weighted_score')[:5]

        for post in posts:
            featured_mark = "★" if post.is_featured else " "
            print(f"  {featured_mark} {post.title[:35]}: score={post.weighted_score}")
    except Exception as e:
        print(f"  [DB not available] Error: {e}")

    print("\n[PATTERN] Case/When use cases:")
    print("  - Conditional label/category: 'low/medium/high'")
    print("  - Conditional count: 'count only where condition'")
    print("  - Conditional calculation: 'featured posts ko 2x weight'")
    print("  - Can be combined with Sum, Count, Avg for complex aggregations")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION H: Window Functions
# ─────────────────────────────────────────────────────────────────────────────

def demo_window_functions():
    """
    INTERVIEW TOPIC: Window Functions
    ───────────────────────────────────
    SQL OVER clause — GROUP BY ki tarah hai but rows eliminate nahi hoti.
    Requires Django 2.0+ and PostgreSQL/MySQL 8+/SQLite 3.25+.

    Common functions:
    - RowNumber(): 1,2,3,4... (no ties)
    - Rank():      1,2,2,4   (ties allowed, gap after)
    - DenseRank(): 1,2,2,3   (ties allowed, no gap)
    - Lag(n):      n rows peeche ka value
    - Lead(n):     n rows aage ka value
    - Sum():       running total (with ORDER BY in window)
    """
    from django.db.models import Window, F, Sum, Avg
    from django.db.models.functions import RowNumber, Rank, DenseRank, Lag, Lead
    from blog.models import Post

    print("\n" + "=" * 60)
    print("DEMO: Window Functions")
    print("=" * 60)

    # ─── Example 1: Row Number per category ───────────────────
    print("\n[1] RowNumber per category (by views):")
    try:
        posts = Post.objects.filter(
            status='published',
            deleted_at__isnull=True,
            category__isnull=False,
        ).annotate(
            row_num=Window(
                expression=RowNumber(),
                partition_by=[F('category_id')],    # PARTITION BY
                order_by=F('views_count').desc()    # ORDER BY inside window
            )
        ).order_by('category_id', 'row_num')[:12]

        current_cat = None
        for post in posts:
            if post.category_id != current_cat:
                current_cat = post.category_id
                print(f"\n  Category {current_cat}:")
            print(f"    #{post.row_num} {post.title[:35]} ({post.views_count} views)")
    except Exception as e:
        print(f"  [DB not available] Error: {e}")
        print("""
  SQL:
  SELECT *, ROW_NUMBER() OVER (PARTITION BY category_id ORDER BY views_count DESC)
         AS row_num
  FROM blog_posts WHERE status = 'published'
        """)

    # ─── Example 2: Rank vs DenseRank ─────────────────────────
    print("\n[2] Rank vs DenseRank — tie handling fark:")
    print("""
  posts = Post.objects.annotate(
      rank=Window(
          expression=Rank(),
          order_by=F('views_count').desc()
      ),
      dense_rank=Window(
          expression=DenseRank(),
          order_by=F('views_count').desc()
      )
  )

  # Views: 1000, 800, 800, 600
  # Rank:       1,   2,   2,   4   ← tie ke baad gap (3 skip hua)
  # DenseRank:  1,   2,   2,   3   ← no gap
    """)

    # ─── Example 3: Running Total ──────────────────────────────
    print("\n[3] Running total views (cumulative):")
    try:
        posts = Post.objects.filter(
            status='published',
            deleted_at__isnull=True,
        ).annotate(
            running_views=Window(
                expression=Sum('views_count'),
                order_by=F('published_at').asc()
                # partition_by nahi → sab posts ek hi window mein
            )
        ).order_by('published_at')[:6]

        for post in posts:
            date_str = post.published_at.strftime('%Y-%m-%d') if post.published_at else 'N/A'
            print(f"  {date_str} | {post.title[:30]:30s} | "
                  f"views={post.views_count:5d} | running={post.running_views}")
    except Exception as e:
        print(f"  [DB not available] Error: {e}")

    # ─── Example 4: Lag — previous row comparison ─────────────
    print("\n[4] Lag — previous post ke saath comparison:")
    try:
        posts = Post.objects.filter(
            status='published',
            deleted_at__isnull=True,
        ).annotate(
            prev_views=Window(
                expression=Lag('views_count', offset=1, default=0),
                order_by=F('published_at').asc()
            ),
        ).annotate(
            views_delta=F('views_count') - F('prev_views')
        ).order_by('published_at')[:6]

        for post in posts:
            delta_str = f"+{post.views_delta}" if post.views_delta >= 0 else str(post.views_delta)
            print(f"  {post.title[:35]:35s}: {post.views_count:5d} views (delta: {delta_str})")
    except Exception as e:
        print(f"  [DB not available] Error: {e}")

    # ─── Window function filter limitation ────────────────────
    print("\n[5] Window function filter limitation — workaround:")
    print("""
  # PROBLEM: Window function ko directly WHERE mein nahi daal sakte
  # ERROR: Post.objects.annotate(rn=Window(...)).filter(rn=1)  ← SQL error on some DBs

  # SOLUTION A: Python level filter (small datasets)
  posts = Post.objects.annotate(row_num=Window(...))
  top_per_cat = [p for p in posts if p.row_num == 1]

  # SOLUTION B: Subquery approach (more efficient)
  from django.db.models import OuterRef, Subquery
  top_post_per_cat = Post.objects.filter(
      status='published',
  ).filter(
      id=Subquery(
          Post.objects.filter(
              category_id=OuterRef('category_id'),
              status='published',
          ).order_by('-views_count').values('id')[:1]
      )
  )
    """)

    print("\n[SUMMARY] Window Functions use cases:")
    print("  - Ranking per group (top-N per category)")
    print("  - Running totals / cumulative sum")
    print("  - Compare with adjacent rows (Lag/Lead)")
    print("  - Percentile calculations")
    print("  AVOID: Simple aggregations (Count/Sum in annotate faster hai)")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION I: Query Inspection
# ─────────────────────────────────────────────────────────────────────────────

def demo_query_inspection():
    """
    INTERVIEW TOPIC: Generated SQL inspect karna
    ─────────────────────────────────────────────
    Production mein N+1 detect karne ke liye.
    Development mein query optimization ke liye.
    """
    from django.db import connection, reset_queries
    from django.conf import settings
    from django.db.models import Count, Exists, OuterRef
    from blog.models import Post, Comment

    print("\n" + "=" * 60)
    print("DEMO: Query Inspection — SQL dekhna")
    print("=" * 60)

    # ─── Method 1: str(qs.query) ──────────────────────────────
    print("\n[1] str(queryset.query) — generated SQL:")
    try:
        qs = Post.objects.filter(
            status='published',
            deleted_at__isnull=True,
        ).select_related('author', 'category').order_by('-views_count')

        print("  Query (first 300 chars):")
        print(f"  {str(qs.query)[:300]}")
    except Exception as e:
        print(f"  [DB not available] Showing example:")
        print("  qs = Post.objects.filter(status='published').select_related('author')")
        print("  print(str(qs.query))")
        print("  # Output: SELECT blog_posts.id, blog_posts.title, ...")
        print("  #         INNER JOIN auth_user ON (blog_posts.author_id = auth_user.id)")
        print("  #         WHERE blog_posts.status = 'published'")

    # ─── Method 2: connection.queries ─────────────────────────
    print("\n[2] connection.queries — sab queries log karo:")
    try:
        settings.DEBUG = True
        reset_queries()   # query log clear karo

        # Queries execute karo
        posts = list(Post.objects.filter(
            status='published',
            deleted_at__isnull=True
        )[:10])

        # N+1 simulate karo
        for post in posts:
            _ = post.author_id   # ye extra query nahi karta (FK id already loaded)

        print(f"  Query count: {len(connection.queries)}")
        for i, q in enumerate(connection.queries[:3], 1):
            print(f"  [{i}] {q['time']}s: {q['sql'][:100]}...")
    except Exception as e:
        print(f"  [DB not available] Error: {e}")

    # ─── Method 3: N+1 detection demo ─────────────────────────
    print("\n[3] N+1 detection — before vs after fix:")
    try:
        settings.DEBUG = True

        # BEFORE fix (N+1)
        reset_queries()
        posts = list(Post.objects.filter(
            status='published',
            deleted_at__isnull=True
        )[:5])
        for post in posts:
            _ = post.author.email   # N+1: har post ke liye ek author query!
        before_count = len(connection.queries)

        # AFTER fix (select_related)
        reset_queries()
        posts = list(Post.objects.filter(
            status='published',
            deleted_at__isnull=True
        ).select_related('author')[:5])
        for post in posts:
            _ = post.author.email   # No extra query — JOIN mein already loaded
        after_count = len(connection.queries)

        print(f"  Without select_related: {before_count} queries (N+1!)")
        print(f"  With select_related:    {after_count} queries (fixed!)")
    except Exception as e:
        print(f"  [DB not available] Error: {e}")
        print("  Example output:")
        print("    Without select_related: 6 queries (N+1!)")
        print("    With select_related:    1 queries (fixed!)")

    # ─── Method 4: EXPLAIN ANALYZE ────────────────────────────
    print("\n[4] EXPLAIN ANALYZE — query execution plan:")
    print("""
  # PostgreSQL mein query plan dekho
  from django.db import connection

  with connection.cursor() as cursor:
      cursor.execute(
          "EXPLAIN ANALYZE SELECT * FROM blog_posts WHERE status = %s AND deleted_at IS NULL",
          ['published']
      )
      plan = cursor.fetchall()
      for line in plan:
          print(line[0])

  # Output example:
  # Seq Scan on blog_posts  (cost=0.00..15.50 rows=100)
  # → Index Scan karna better hai — add index on (status, deleted_at)
    """)

    # ─── Method 5: django-debug-toolbar ───────────────────────
    print("\n[5] django-debug-toolbar (development best practice):")
    print("  pip install django-debug-toolbar")
    print("  Browser mein har request ke:")
    print("  - Total query count")
    print("  - Har query ka SQL + time")
    print("  - Duplicate queries highlight (N+1 detection)")
    print("  - Query timeline visualization")

    print("\n[SUMMARY] Query inspection tools:")
    print("  str(qs.query)           → quick SQL preview (no params substituted)")
    print("  connection.queries      → actual executed SQL + time (DEBUG=True needed)")
    print("  EXPLAIN ANALYZE         → PostgreSQL execution plan")
    print("  django-debug-toolbar    → best for development (visual)")
    print("  nplusone library        → automatic N+1 detection in tests")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN — sab demos run karo
# ─────────────────────────────────────────────────────────────────────────────

def main():
    """
    Sab demos run karo.
    DB available nahi hai toh SQL patterns dikhao.
    """
    print("\n" + "=" * 70)
    print("  Django Advanced ORM — Subquery, Exists, Raw SQL, Bulk Ops")
    print("  Running all demos...")
    print("=" * 70)

    demos = [
        ("Subquery & OuterRef",          demo_subquery_outerref),
        ("Exists()",                      demo_exists),
        ("Raw SQL",                       demo_raw_sql),
        ("bulk_create Performance",       demo_bulk_create),
        ("bulk_update",                   demo_bulk_update),
        ("get_or_create / update_or_create", demo_get_or_create),
        ("Case/When Annotations",         demo_case_when),
        ("Window Functions",              demo_window_functions),
        ("Query Inspection",              demo_query_inspection),
    ]

    failed = []
    for name, demo_fn in demos:
        try:
            demo_fn()
        except Exception as e:
            print(f"\n[DEMO FAILED: {name}] {type(e).__name__}: {e}")
            failed.append(name)

    print("\n" + "=" * 70)
    print("  DEMO COMPLETE")
    if failed:
        print(f"  Failed demos: {', '.join(failed)}")
        print("  (Expected if DB models not migrated — SQL patterns still shown)")
    else:
        print("  All demos ran successfully!")
    print("=" * 70)


# ─────────────────────────────────────────────────────────────────────────────
# Standalone execution
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        setup_django()
    except Exception as e:
        print(f"[Django setup failed: {e}]")
        print("[Tip: Run from manage.py shell instead:")
        print("      python manage.py shell")
        print("      exec(open('practical/09_orm_subquery_bulk.py').read())")
        print("      main()")
        print("]")
        sys.exit(1)

    main()
