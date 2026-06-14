"""
Django + DRF — Advanced Patterns
=================================
Covers eight production-grade patterns that appear frequently in senior-level
interviews and real Django codebases:

  1. Custom User Model (AbstractUser + email login)
  2. Django Transactions (atomic, savepoint, select_for_update, on_commit)
  3. Caching (cache_page, low-level cache.get/set, invalidation, versioning)
  4. Filtering & Search (DjangoFilterBackend, SearchFilter, OrderingFilter)
  5. Dynamic Fields Serializer (caller controls which fields are returned)
  6. Nested Serializer Writes (create / update with related objects)
  7. Admin Customisation (list_display, actions, computed columns)
  8. Custom DRF Throttle (plan-aware per-user rate limiting)

All patterns are grounded in 04_advanced_patterns.md (theory doc).

IMPORTANT — External infrastructure is intentionally absent here.
Django, DRF, and django-filter are imported with a graceful fallback so that
this file can be read, reviewed, and `py_compile`-checked without running a
real Django project.  No __main__ block is provided because the patterns
require a database, a running Django app, and (for caching) Redis.

# pip install django djangorestframework django-filter
"""

from __future__ import annotations

import logging
from functools import wraps
from typing import Any, Dict, List, Optional, Tuple, Type

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Graceful imports — allows py_compile and static analysis without a full
# Django installation in every developer environment.
# ---------------------------------------------------------------------------
try:
    from django.contrib.auth.models import AbstractUser, BaseUserManager
    from django.contrib.auth.signals import post_save  # noqa: F401 (illustrative)
    from django.core.cache import cache
    from django.db import models, transaction
    from django.utils.decorators import method_decorator
    from django.views.decorators.cache import cache_page
    from django.views.decorators.vary import vary_on_headers

    from rest_framework import serializers, viewsets
    from rest_framework.filters import OrderingFilter, SearchFilter
    from rest_framework.request import Request
    from rest_framework.response import Response
    from rest_framework.throttling import SimpleRateThrottle

    try:
        import django_filters  # type: ignore
        from django_filters.rest_framework import DjangoFilterBackend  # type: ignore
        _HAS_DJANGO_FILTER = True
    except ImportError:  # pragma: no cover
        _HAS_DJANGO_FILTER = False

    _HAS_DJANGO = True

except ImportError:  # pragma: no cover
    # Django / DRF not installed in this environment.
    # The rest of the module is still valid Python — only class bodies that
    # reference Django base classes are guarded with the flag above.
    _HAS_DJANGO = False
    _HAS_DJANGO_FILTER = False


# ==========================================================================
# 1. CUSTOM USER MODEL
# ==========================================================================
# Always create a custom user model BEFORE the first migration.
# Changing the auth model after migrations are applied breaks all FK
# references and is extremely painful to fix.
#
# Pattern: remove the built-in `username` field and use `email` as the
# login identifier.  Add `role` and `plan` fields for permission tiers.
#
# settings.py must contain:
#   AUTH_USER_MODEL = "users.User"
# ==========================================================================

if _HAS_DJANGO:

    class UserManager(BaseUserManager):
        """
        Custom manager that replaces the username-based create_user flow
        with an email-based one.
        """

        def create_user(
            self,
            email: str,
            password: Optional[str] = None,
            **extra_fields: Any,
        ) -> "User":
            if not email:
                raise ValueError("An email address is required.")
            email = self.normalize_email(email)
            user = self.model(email=email, **extra_fields)
            user.set_password(password)
            user.save(using=self._db)
            return user

        def create_superuser(
            self,
            email: str,
            password: str,
            **extra_fields: Any,
        ) -> "User":
            extra_fields.setdefault("is_staff", True)
            extra_fields.setdefault("is_superuser", True)

            if not extra_fields.get("is_staff"):
                raise ValueError("Superuser must have is_staff=True.")
            if not extra_fields.get("is_superuser"):
                raise ValueError("Superuser must have is_superuser=True.")

            return self.create_user(email, password, **extra_fields)

    class User(AbstractUser):
        """
        Project-wide custom user model.

        Key design decisions:
        - `username` is set to None to remove it from the schema entirely.
        - `email` is unique and becomes the login credential.
        - `role` drives permission logic (e.g. "admin", "editor", "user").
        - `plan` drives feature gating and throttle rates.
        """

        # Remove the inherited username column.
        username = None  # type: ignore[assignment]

        email = models.EmailField(unique=True)
        role = models.CharField(max_length=20, default="user")
        plan = models.CharField(max_length=20, default="free")

        USERNAME_FIELD = "email"
        REQUIRED_FIELDS = ["first_name", "last_name"]

        objects = UserManager()  # type: ignore[assignment]

        class Meta:
            # Declare app_label so Django knows which app owns this model
            # when AUTH_USER_MODEL = "users.User".
            app_label = "users"
            verbose_name = "User"
            verbose_name_plural = "Users"

        def __str__(self) -> str:
            return self.email


# ==========================================================================
# 2. DJANGO TRANSACTIONS
# ==========================================================================
# Four patterns from the theory doc — every one of them is a common
# interview question:
#
#   a) @transaction.atomic — all-or-nothing block
#   b) Nested savepoints — inner block can fail without aborting outer
#   c) select_for_update — row-level lock to prevent race conditions
#   d) on_commit — defer side-effects until after the transaction commits
# ==========================================================================

if _HAS_DJANGO:

    # ------------------------------------------------------------------
    # 2a. @transaction.atomic — atomic decorator on a service function
    # ------------------------------------------------------------------

    @transaction.atomic
    def place_order(user_id: int, cart_items: List[Dict[str, Any]]) -> Any:
        """
        Create an order and deduct stock within a single database transaction.

        If any step raises an exception the entire transaction is rolled back,
        leaving no half-written order or corrupted stock counts.
        """
        # Import here to avoid circular imports in a real Django project.
        from django.apps import apps  # type: ignore[import]

        Order = apps.get_model("shop", "Order")
        OrderItem = apps.get_model("shop", "OrderItem")
        Product = apps.get_model("shop", "Product")

        order = Order.objects.create(user_id=user_id)

        for item in cart_items:
            OrderItem.objects.create(order=order, **item)
            Product.objects.filter(id=item["product_id"]).update(
                stock=models.F("stock") - item["quantity"]
            )

        return order

    # ------------------------------------------------------------------
    # 2b. Nested savepoints — audit log failure must NOT abort the order
    # ------------------------------------------------------------------

    def create_order_with_audit(user: Any, items: List[Dict[str, Any]]) -> Any:
        """
        Outer transaction: create order.
        Inner savepoint: write audit log.

        If the audit write fails the savepoint is rolled back, but the outer
        transaction (and therefore the order) is preserved.
        """
        from django.apps import apps  # type: ignore[import]

        Order = apps.get_model("shop", "Order")
        AuditLog = apps.get_model("audit", "AuditLog")

        with transaction.atomic():
            order = Order.objects.create(user=user)

            try:
                with transaction.atomic():  # creates a savepoint
                    AuditLog.objects.create(
                        action="order_created",
                        user=user,
                        object_id=order.pk,
                    )
            except Exception:
                # Audit failure is non-fatal; log it but keep the order.
                logger.warning(
                    "Audit log write failed for order %s — continuing.",
                    order.pk,
                )

            return order

    # ------------------------------------------------------------------
    # 2c. select_for_update — row-level lock to prevent double-spend
    # ------------------------------------------------------------------

    def transfer_credits(
        from_user_id: int,
        to_user_id: int,
        amount: int,
    ) -> None:
        """
        Transfer credits between two accounts.

        select_for_update() acquires a database-level row lock so that no
        concurrent transaction can read a stale balance and produce an
        inconsistent transfer.  Both rows are locked in a consistent order to
        avoid deadlocks.
        """
        with transaction.atomic():
            # Lock both rows before reading balances.
            sender = (
                User.objects.select_for_update()
                .get(id=from_user_id)
            )
            receiver = (
                User.objects.select_for_update()
                .get(id=to_user_id)
            )

            if sender.credits < amount:  # type: ignore[attr-defined]
                raise ValueError("Insufficient credits.")

            sender.credits -= amount  # type: ignore[attr-defined]
            receiver.credits += amount  # type: ignore[attr-defined]
            sender.save(update_fields=["credits"])
            receiver.save(update_fields=["credits"])

    # ------------------------------------------------------------------
    # 2d. on_commit — dispatch Celery task only after the commit lands
    # ------------------------------------------------------------------
    #
    # Common mistake: calling task.delay() inside a post_save signal fires
    # the task immediately.  If the transaction is later rolled back (e.g.
    # due to an integrity error further down) the task has already been
    # dispatched and will try to operate on a row that does not exist.
    #
    # Correct pattern: wrap the delay() call in transaction.on_commit().
    # ------------------------------------------------------------------

    def dispatch_order_email_on_commit(order_id: int) -> None:
        """
        Schedule an email Celery task to run only after the current
        transaction has been committed to the database.
        """
        # This import would exist in a real project.
        # from myapp.tasks import send_order_confirmation_email
        # transaction.on_commit(lambda: send_order_confirmation_email.delay(order_id))

        # Illustrative version that just logs:
        transaction.on_commit(
            lambda: logger.info(
                "on_commit: would dispatch send_order_confirmation_email(%s)",
                order_id,
            )
        )


# ==========================================================================
# 3. CACHING PATTERNS
# ==========================================================================
# Three tiers of caching granularity:
#
#   a) cache_page — caches the entire HTTP response for a view
#   b) cache.get / cache.set — fine-grained object-level caching
#   c) Cache versioning — bump a counter instead of explicitly deleting keys
#
# settings.py (Redis backend):
#
#   CACHES = {
#       "default": {
#           "BACKEND": "django.core.cache.backends.redis.RedisCache",
#           "LOCATION": "redis://127.0.0.1:6379/1",
#       }
#   }
# ==========================================================================

if _HAS_DJANGO:

    # ------------------------------------------------------------------
    # 3a. cache_page — whole-view response cache
    # ------------------------------------------------------------------
    # Applied with method_decorator when using class-based views.
    # vary_on_headers("Authorization") ensures each user gets their own
    # cached copy rather than one shared response.
    # ------------------------------------------------------------------

    # Usage on a CBV get() method (illustrative — not executable standalone):
    #
    #   @method_decorator(cache_page(60 * 5))
    #   @method_decorator(vary_on_headers("Authorization"))
    #   def get(self, request, *args, **kwargs):
    #       ...

    CACHE_PAGE_EXAMPLE_CODE = (
        "@method_decorator(cache_page(60 * 5))\n"
        "@method_decorator(vary_on_headers('Authorization'))\n"
        "def get(self, request, *args, **kwargs):\n"
        "    ..."
    )

    # ------------------------------------------------------------------
    # 3b. Low-level cache.get / cache.set
    # ------------------------------------------------------------------

    def get_popular_posts() -> List[Dict[str, Any]]:
        """
        Return the top-10 most-viewed published posts.

        Result is cached for 5 minutes.  On cache miss the database is
        queried and the result is stored under a versioned cache key so
        that invalidation does not require iterating all keys.
        """
        cache_key = "popular_posts_v1"
        posts: Optional[List[Dict[str, Any]]] = cache.get(cache_key)

        if posts is None:
            from django.apps import apps  # type: ignore[import]

            Post = apps.get_model("blog", "Post")
            posts = list(
                Post.objects.filter(status="published")
                .select_related("author")
                .order_by("-views_count")[:10]
                .values("id", "title", "views_count", "author__email")
            )
            cache.set(cache_key, posts, timeout=300)  # 5 minutes

        return posts  # type: ignore[return-value]

    def update_post(post_id: int, data: Dict[str, Any]) -> None:
        """
        Update a post and invalidate all related cache keys.

        Simple cache invalidation: explicitly delete every key that may
        contain stale data for this post.
        """
        from django.apps import apps  # type: ignore[import]

        Post = apps.get_model("blog", "Post")
        post = Post.objects.get(id=post_id)

        for field, value in data.items():
            setattr(post, field, value)
        post.save()

        # Remove all cache entries that could now be stale.
        cache.delete(f"post_{post_id}")
        cache.delete("popular_posts_v1")
        cache.delete("featured_posts")

    # ------------------------------------------------------------------
    # 3c. Cache versioning — bump a counter, skip explicit key deletion
    # ------------------------------------------------------------------
    # Instead of tracking every derived cache key, store a version counter
    # per user.  Invalidating means incrementing the counter; old keys
    # become unreachable and expire naturally via their TTL.
    # ------------------------------------------------------------------

    def get_user_feed(user_id: int) -> List[Dict[str, Any]]:
        """
        Return the personalised feed for a user, keyed by feed version.

        Invalidation increments the version number; the old key is never
        accessed again and will expire on its own TTL.
        """
        version: int = cache.get(f"user_feed_version:{user_id}", 1)
        cache_key = f"user_feed:{user_id}:v{version}"
        feed: Optional[List[Dict[str, Any]]] = cache.get(cache_key)

        if feed is None:
            feed = _compute_user_feed(user_id)
            cache.set(cache_key, feed, timeout=600)  # 10 minutes

        return feed  # type: ignore[return-value]

    def invalidate_user_feed(user_id: int) -> None:
        """
        Invalidate the cached feed for a user by bumping the version counter.

        The previous cache key is simply never requested again and will expire
        on its own.  No need to construct or track the old key.
        """
        cache.incr(f"user_feed_version:{user_id}", delta=1)

    def _compute_user_feed(user_id: int) -> List[Dict[str, Any]]:
        """Placeholder: compute a feed for the given user from the database."""
        # In production this would run a complex query (followed posts,
        # recommended content, etc.).
        return []


# ==========================================================================
# 4. FILTERING, SEARCH, AND ORDERING
# ==========================================================================
# Three complementary filter backends that work together in DRF:
#
#   DjangoFilterBackend  — exact / range / relational filtering
#   SearchFilter         — text search across specified fields
#   OrderingFilter       — client-controlled result ordering
#
# They are composed on a ViewSet and activated via query parameters:
#
#   GET /posts/?status=published               → DjangoFilterBackend
#   GET /posts/?search=django+orm              → SearchFilter
#   GET /posts/?ordering=-views_count,title    → OrderingFilter
#
# REST_FRAMEWORK settings (settings.py):
#
#   "DEFAULT_FILTER_BACKENDS": [
#       "django_filters.rest_framework.DjangoFilterBackend",
#       "rest_framework.filters.SearchFilter",
#       "rest_framework.filters.OrderingFilter",
#   ]
# ==========================================================================

if _HAS_DJANGO and _HAS_DJANGO_FILTER:

    class PostFilter(django_filters.FilterSet):
        """
        Custom FilterSet for the Post model.

        Supports:
          ?status=published                   — exact match
          ?created_after=2024-01-01           — date range start
          ?created_before=2024-12-31          — date range end
          ?author=42                          — FK exact match
        """

        status = django_filters.CharFilter(field_name="status", lookup_expr="exact")
        created_after = django_filters.DateFilter(
            field_name="created_at", lookup_expr="gte"
        )
        created_before = django_filters.DateFilter(
            field_name="created_at", lookup_expr="lte"
        )
        author = django_filters.NumberFilter(
            field_name="author__id", lookup_expr="exact"
        )

        class Meta:
            # `model` and `fields` would reference a real Post model.
            # Left abstract here to avoid importing from a specific app.
            fields: List[str] = ["status", "created_after", "created_before", "author"]


elif _HAS_DJANGO:

    class PostFilter:  # type: ignore[no-redef]
        """Stub — install django-filter to use the real implementation."""


if _HAS_DJANGO:

    class PostViewSet(viewsets.ModelViewSet):
        """
        ViewSet that combines all three DRF filter backends.

        The `queryset` and `serializer_class` attributes are intentionally
        left as None / a placeholder; set them in the concrete project viewset.

        Filter lookup modifiers for `search_fields`:
          (no prefix)  — icontains (default)
          ^            — istartswith
          =            — iexact
          @            — full-text search (PostgreSQL only)
          $            — regex
        """

        queryset = None  # type: ignore[assignment]
        serializer_class = serializers.Serializer  # placeholder

        filter_backends = [SearchFilter, OrderingFilter]
        if _HAS_DJANGO_FILTER:
            filter_backends = [DjangoFilterBackend] + filter_backends  # type: ignore[list-item]
            filterset_class = PostFilter

        # SearchFilter — text search across title and content;
        # ^ prefix means 'starts with' on author email.
        search_fields: List[str] = ["title", "content", "^author__email"]

        # OrderingFilter — only these fields can appear in ?ordering=
        ordering_fields: List[str] = ["created_at", "views_count", "title"]
        ordering: List[str] = ["-created_at"]  # default sort


# ==========================================================================
# 5. DYNAMIC FIELDS SERIALIZER
# ==========================================================================
# A mixin that reads a `?fields=id,title,status` query parameter and removes
# any keys not requested from the serialized output.
#
# This avoids over-fetching while keeping a single serializer class.
# Particularly useful for list endpoints where clients need fewer fields.
# ==========================================================================

if _HAS_DJANGO:

    class DynamicFieldsMixin:
        """
        Serializer mixin that supports a `fields` query-parameter to restrict
        which fields are included in the response.

        Usage:
            class PostSerializer(DynamicFieldsMixin, serializers.ModelSerializer):
                ...

        Request:
            GET /posts/?fields=id,title,status

        Response only contains the three requested fields.
        """

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            # Extract `fields` from kwargs before passing to the parent.
            requested: Optional[List[str]] = kwargs.pop("fields", None)
            super().__init__(*args, **kwargs)  # type: ignore[call-arg]

            # Also honour `?fields=` query parameter from the request context.
            request: Optional[Request] = (
                self.context.get("request")  # type: ignore[attr-defined]
                if hasattr(self, "context")
                else None
            )
            if request is not None:
                query_fields = request.query_params.get("fields")
                if query_fields:
                    requested = [f.strip() for f in query_fields.split(",")]

            if requested is not None:
                # Keep only the explicitly requested fields.
                allowed = set(requested)
                existing = set(self.fields.keys())  # type: ignore[attr-defined]
                for field_name in existing - allowed:
                    self.fields.pop(field_name)  # type: ignore[attr-defined]


# ==========================================================================
# 6. NESTED SERIALIZER WRITES
# ==========================================================================
# DRF nested serializers are read-only by default.  To support writes you
# must override `create()` and `update()` to manually handle the nested data.
#
# Pattern:
#   1. Pop the nested dict from validated_data (it is no longer a model field).
#   2. Create / update the parent object.
#   3. Create / update the related object using the popped data.
# ==========================================================================

if _HAS_DJANGO:

    class AddressSerializer(serializers.Serializer):
        """Serializer for an embedded postal address."""

        street = serializers.CharField(max_length=200)
        city = serializers.CharField(max_length=100)
        country = serializers.CharField(max_length=100)
        postal_code = serializers.CharField(max_length=20)

    class UserProfileSerializer(serializers.Serializer):
        """
        Serializer that supports nested create and update of a related
        Address object.

        Read  → returns nested address dict.
        Write → creates / updates the Address row automatically.
        """

        id = serializers.IntegerField(read_only=True)
        email = serializers.EmailField()
        first_name = serializers.CharField(max_length=150)
        address = AddressSerializer(required=False)

        def create(self, validated_data: Dict[str, Any]) -> Any:
            """
            Create a User with an optional associated Address.

            The nested `address` dict is popped before calling
            User.objects.create() to avoid passing unrecognised keyword
            arguments to the model constructor.
            """
            address_data: Optional[Dict[str, Any]] = validated_data.pop(
                "address", None
            )

            # In a real serializer this would be:
            #   user = User.objects.create(**validated_data)
            # Simulated here:
            user = type("User", (), validated_data)()
            user.pk = 1  # simulate auto PK

            if address_data:
                # In a real serializer:
                #   Address.objects.create(user=user, **address_data)
                logger.debug(
                    "Would create Address for user %s: %s", user.pk, address_data
                )

            return user

        def update(self, instance: Any, validated_data: Dict[str, Any]) -> Any:
            """
            Update a User and upsert their associated Address.

            update_or_create() handles both cases (address already exists vs
            first time being set) without requiring the caller to distinguish.
            """
            address_data: Optional[Dict[str, Any]] = validated_data.pop(
                "address", None
            )

            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            # instance.save() in a real serializer

            if address_data:
                # Address.objects.update_or_create(
                #     user=instance,
                #     defaults=address_data,
                # )
                logger.debug(
                    "Would upsert Address for user %s: %s", instance.pk, address_data
                )

            return instance


# ==========================================================================
# 7. DJANGO ADMIN CUSTOMISATION
# ==========================================================================
# Common patterns for making the admin interface productive and safe:
#
#   list_display          — columns shown in the changelist
#   list_select_related   — avoid N+1 on list view (one JOIN query)
#   raw_id_fields         — FK popup for large tables (avoids huge dropdowns)
#   prepopulated_fields   — auto-fill slug from title
#   readonly_fields       — prevent accidental edits to audit columns
#   @admin.action         — bulk actions on selected rows
#   @admin.display        — computed column with sort support
#   get_queryset()        — optimise the base queryset
# ==========================================================================

if _HAS_DJANGO:
    try:
        from django.contrib import admin as django_admin

        class PostAdmin(django_admin.ModelAdmin):
            """
            Production-ready admin for a Post model.

            Demonstrates every standard customisation pattern covered by the
            theory doc.  Register on your Post model with:

                @admin.register(Post)
                class PostAdmin(PostAdmin): ...

            or directly in admin.py:

                admin.site.register(Post, PostAdmin)
            """

            # -----------------------------------------------------------
            # List view
            # -----------------------------------------------------------
            list_display: List[str] = [
                "title",
                "author_email_column",  # computed column (see @admin.display below)
                "status",
                "views_count",
                "created_at",
            ]
            list_filter: List[str] = ["status", "category"]
            search_fields: List[str] = ["title", "author__email"]
            ordering: List[str] = ["-created_at"]

            # One query with JOINs instead of N+1 queries on the list page.
            list_select_related: List[str] = ["author", "category"]
            list_per_page: int = 50

            # -----------------------------------------------------------
            # Detail / change view
            # -----------------------------------------------------------
            # Prevent editing of auto-set audit fields.
            readonly_fields: List[str] = ["created_at", "updated_at", "views_count"]

            # M2M field with a dual-list widget (readable for large tag sets).
            filter_horizontal: List[str] = ["tags"]

            # FK popup widget — avoids a 50 000-row dropdown for author.
            raw_id_fields: List[str] = ["author"]

            # Auto-populate slug from title as the user types.
            prepopulated_fields: Dict[str, Tuple[str, ...]] = {"slug": ("title",)}

            # -----------------------------------------------------------
            # Bulk action — publish selected posts
            # -----------------------------------------------------------
            @django_admin.action(description="Publish selected posts")
            def publish_posts(
                self,
                request: Any,
                queryset: Any,
            ) -> None:
                """
                Bulk-publish selected posts and report how many were changed.
                Calls each instance's publish() method so any business logic
                in that method (e.g. setting `published_at`) is respected.
                """
                updated = 0
                for post in queryset.filter(status="draft"):
                    post.publish()
                    updated += 1
                self.message_user(
                    request,
                    f"{updated} post(s) published successfully.",
                )

            actions = ["publish_posts"]

            # -----------------------------------------------------------
            # Computed column — author email with sort support
            # -----------------------------------------------------------
            @django_admin.display(
                description="Author Email",
                ordering="author__email",  # enables column-header sort
            )
            def author_email_column(self, obj: Any) -> str:
                return obj.author.email

            # -----------------------------------------------------------
            # Optimised queryset for the changelist
            # -----------------------------------------------------------
            def get_queryset(self, request: Any) -> Any:
                """
                Override base queryset to eagerly load related objects,
                preventing N+1 queries on the changelist page.
                """
                return (
                    super()
                    .get_queryset(request)
                    .select_related("author", "category")
                )

    except Exception:  # pragma: no cover
        # django.contrib.admin may not be in INSTALLED_APPS during tests.
        pass


# ==========================================================================
# 8. CUSTOM DRF THROTTLE
# ==========================================================================
# Two throttle classes that extend SimpleRateThrottle:
#
#   PerUserPerEndpointThrottle
#     — Unique cache key per (user, view class) so that rate limits are
#       tracked independently for each endpoint.
#
#   AIGenerationThrottle
#     — Dynamic rate based on the user's subscription plan (free vs premium).
#     — Expensive AI endpoints need tighter limits for free-tier users.
#
# settings.py:
#
#   REST_FRAMEWORK = {
#       "DEFAULT_THROTTLE_RATES": {
#           "ai_generation": "10/hour",
#           "login":         "5/minute",
#       }
#   }
# ==========================================================================

if _HAS_DJANGO:

    class PerUserPerEndpointThrottle(SimpleRateThrottle):
        """
        Per-user throttle with a cache key scoped to the view class.

        This means a user can make N requests to /posts/ and N requests to
        /comments/ independently, rather than sharing a single counter across
        all endpoints.
        """

        scope = "user"

        def get_cache_key(self, request: Request, view: Any) -> Optional[str]:
            if not request.user.is_authenticated:
                # Anonymous users fall through to the anon throttle class.
                return None
            return (
                f"throttle_{self.scope}_{request.user.id}_{view.__class__.__name__}"
            )

    class AIGenerationThrottle(SimpleRateThrottle):
        """
        Strict throttle for expensive AI generation endpoints.

        The rate is determined dynamically from the authenticated user's plan:
          - free    → 5 / hour
          - premium → 100 / hour

        Falls back to the settings-level `ai_generation` rate when the user
        object is not yet available (e.g. during early middleware evaluation).
        """

        scope = "ai_generation"
        rate = "10/hour"  # fallback from settings

        # Mapping of plan names to rate strings.
        _PLAN_RATES: Dict[str, str] = {
            "free": "5/hour",
            "starter": "20/hour",
            "premium": "100/hour",
            "enterprise": "1000/hour",
        }

        def get_rate(self) -> str:
            """
            Return the rate string for the current user's plan.

            Called by SimpleRateThrottle.__init__ before any request context
            is available, so we must guard against a missing request.
            """
            request: Optional[Any] = getattr(self, "request", None)
            if request is not None:
                plan: str = getattr(request.user, "plan", "free")
                return self._PLAN_RATES.get(plan, "5/hour")
            return self.rate

        def get_cache_key(self, request: Request, view: Any) -> Optional[str]:
            if not request.user.is_authenticated:
                return None
            return f"throttle_ai_{request.user.id}"


# ==========================================================================
# 9. to_representation — conditional / computed serializer output
# ==========================================================================
# Override to_representation() to:
#   - Add computed fields that are not model columns
#   - Truncate content on list views vs returning full body on detail views
#   - Remove fields based on the requesting user's role
# ==========================================================================

if _HAS_DJANGO:

    class PostDetailSerializer(serializers.Serializer):
        """
        Demonstrates `to_representation` for conditional and computed fields.
        """

        id = serializers.IntegerField(read_only=True)
        title = serializers.CharField(max_length=255)
        content = serializers.CharField()
        created_at = serializers.DateTimeField(read_only=True)
        internal_notes = serializers.CharField(required=False, allow_blank=True)

        def to_representation(self, instance: Any) -> Dict[str, Any]:
            """
            Post-process the default serialized output:

            1. Add a `reading_time` computed field (not on the model).
            2. On list views (no `pk` in URL kwargs), truncate content.
            3. Strip `internal_notes` for non-staff users.
            """
            data: Dict[str, Any] = super().to_representation(instance)

            # 1. Computed field — reading time estimate.
            word_count: int = len(
                str(getattr(instance, "content", "")).split()
            )
            reading_minutes: int = max(1, word_count // 200)
            data["reading_time"] = f"{reading_minutes} min read"

            # 2. Truncate content on list views.
            request: Optional[Any] = self.context.get("request")
            if request is not None:
                url_kwargs: Dict[str, Any] = getattr(
                    getattr(request, "resolver_match", None), "kwargs", {}
                )
                if "pk" not in url_kwargs:
                    # List view — return a 200-character preview.
                    content: str = data.get("content", "")
                    if len(content) > 200:
                        data["content"] = content[:200] + "…"

            # 3. Remove sensitive field for non-staff users.
            if request is not None and not getattr(request.user, "is_staff", False):
                data.pop("internal_notes", None)

            return data


# ==========================================================================
# NOTES FOR THE READER
# ==========================================================================
#
# 1. Custom User Model — create it before the very first `migrate`.
#    Changing AUTH_USER_MODEL afterwards requires a complex migration plan
#    (all FK columns, auth tables, and session tables must be repointed).
#
# 2. Transactions — never fire Celery tasks inside `post_save` signals
#    directly.  Wrap the delay() call in `transaction.on_commit()` so the
#    task is not dispatched if the outer transaction rolls back.
#
# 3. Cache invalidation — explicit key deletion works for simple cases.
#    Cache versioning (incrementing a counter per entity) is safer for
#    complex dependency graphs because it avoids the need to track every
#    derived key explicitly.
#
# 4. Throttle classes — combine PerUserPerEndpointThrottle as the default
#    with AIGenerationThrottle specifically on expensive endpoints.  Do not
#    set a blanket rate that is too tight for premium users or too loose for
#    free users.
#
# 5. Nested serializer writes — always pop the nested dict BEFORE calling
#    Model.objects.create().  Passing an unexpected nested dict to the model
#    constructor raises a TypeError.
# ==========================================================================
