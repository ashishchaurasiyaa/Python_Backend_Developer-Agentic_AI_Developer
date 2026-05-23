"""
Advanced Django ORM — Prefetch(), Raw SQL, Annotations
═══════════════════════════════════════════════════════════════
INTERVIEW: Prefetch() vs prefetch_related() fark?
  prefetch_related("comments"):
    - ALL related comments load karta hai
    - Default queryset — no filters/ordering customization

  Prefetch("comments", queryset=..., to_attr="..."):
    - Custom queryset — filter, order, limit
    - to_attr — Python attribute mein store (list, not queryset)
    - Multiple Prefetch for same relation possible (different to_attr)

Run this file:
  python manage.py shell
  from blog.orm_advanced import *
  demo_prefetch_advanced()
"""

from django.db.models import (
    Count, Sum, Avg, Max, Min, F, Q,
    Prefetch, ExpressionWrapper, FloatField,
    Window, Subquery, OuterRef,
)
from django.db import connection


def demo_prefetch_advanced():
    """
    INTERVIEW: Prefetch() with custom queryset.
    Show approved top comments per post in ONE extra query.
    """
    from .models import Post, Comment

    # ─── BAD: loads ALL comments (could be thousands per post) ───
    bad_posts = Post.objects.published().prefetch_related("comments")
    for post in bad_posts[:3]:
        all_comments = list(post.comments.all())  # ALL approved + unapproved

    # ─── GOOD: Prefetch with filtered + limited queryset ───
    top_comments_qs = (
        Comment.objects
        .filter(is_approved=True, parent__isnull=True)  # only top-level approved
        .select_related("author")
        .order_by("-created_at")
    )

    good_posts = Post.objects.published().prefetch_related(
        Prefetch(
            lookup="comments",
            queryset=top_comments_qs,
            to_attr="top_comments",  # stores as Python list, not queryset
        )
    )

    for post in good_posts[:3]:
        # post.top_comments is a list — slicing here adds NO extra query
        for comment in post.top_comments[:3]:
            print(f"  [{post.title[:30]}] {comment.author.email}: {comment.content[:50]}")

    print(f"\nTotal queries: {len(connection.queries)}")


def demo_multiple_prefetch():
    """
    INTERVIEW: Same relation, different to_attr.
    One extra query per Prefetch (2 queries total for 2 Prefetch).
    """
    from .models import Post, Comment

    recent_comments = Comment.objects.filter(
        is_approved=True, parent__isnull=True
    ).order_by("-created_at")[:5]

    featured_comments = Comment.objects.filter(
        is_approved=True, likes_count__gte=10  # hypothetical field
    ) if hasattr(Comment, 'likes_count') else Comment.objects.none()

    posts = Post.objects.published().prefetch_related(
        Prefetch("comments", queryset=recent_comments,  to_attr="recent_comments"),
        "tags",  # simple prefetch for tags
    ).select_related("author", "category")

    return posts


def demo_annotation_advanced():
    """
    INTERVIEW: Complex annotations — conditional counts, window functions.
    """
    from .models import Post, Comment
    from django.db.models import Case, When, IntegerField

    # ─── Conditional annotation ───
    posts = Post.objects.annotate(
        # Count only approved top-level comments
        approved_top_comment_count=Count(
            "comments",
            filter=Q(comments__is_approved=True, comments__parent__isnull=True),
            distinct=True,
        ),
        # Engagement score — computed in DB
        engagement_score=ExpressionWrapper(
            (F("likes_count") * 2 + F("views_count")) / 100.0,
            output_field=FloatField(),
        ),
    ).order_by("-engagement_score")

    return posts


def demo_subquery():
    """
    INTERVIEW: Subquery + OuterRef — correlated subquery.
    Get the latest comment date for each post.
    """
    from .models import Post, Comment
    from django.db.models import OuterRef, Subquery

    # Latest comment date per post — correlated subquery
    latest_comment = Comment.objects.filter(
        post=OuterRef("pk"),      # OuterRef references outer Post queryset
        is_approved=True,
    ).order_by("-created_at").values("created_at")[:1]

    posts = Post.objects.published().annotate(
        latest_comment_at=Subquery(latest_comment),
    ).order_by("-latest_comment_at")

    return posts


def demo_raw_sql():
    """
    INTERVIEW: Kab raw SQL use karte hain?
      - Complex queries that ORM can't express
      - Database-specific functions (PostgreSQL full-text, JSON ops)
      - Performance-critical queries after profiling
      - ALWAYS use parameterized queries — never string formatting!

    INTERVIEW: SQL injection se kaise bachte hain Django mein?
      - ORM automatically parameterizes
      - objects.raw(): use %s placeholders
      - cursor.execute(): use %s placeholders
      - NEVER: f"WHERE id = {user_id}" → SQL injection!
    """
    from .models import Post

    # ─── objects.raw() ───
    # Returns model instances (queryset-like)
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
        ["published", 10],  # parameterized — safe from SQL injection
    )

    for post in posts:
        print(f"{post.title}: {post.comment_count} comments, {post.views_count} views")

    # ─── connection.cursor() ───
    # For non-SELECT or complex queries returning raw data
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE blog_posts
            SET views_count = views_count + 1
            WHERE id = %s
            """,
            [1]  # parameterized
        )

        cursor.execute(
            "SELECT AVG(views_count), MAX(views_count) FROM blog_posts WHERE status = %s",
            ["published"],
        )
        avg_views, max_views = cursor.fetchone()
        print(f"Avg views: {avg_views:.1f}, Max: {max_views}")


def demo_select_related_depth():
    """
    INTERVIEW: select_related depth?
      select_related follows FK chains.
      "author__profile" → JOIN users, JOIN user_profiles
    """
    from .models import Post

    # Nested select_related — 1 query with multiple JOINs
    posts = Post.objects.published().select_related(
        "author",           # JOIN users
        "author__profile",  # JOIN user_profiles
        "category",         # JOIN blog_categories
    )

    for post in posts[:5]:
        print(f"{post.title} by {post.author.email} ({post.author.profile.location})")
        # No extra queries — all JOINed in one SQL


def print_query_count():
    """Utility — count DB queries in a block."""
    from django.test.utils import override_settings
    print(f"Total DB queries so far: {len(connection.queries)}")
    for i, q in enumerate(connection.queries[-5:], 1):
        print(f"  [{i}] {q['time']}s: {q['sql'][:100]}")
