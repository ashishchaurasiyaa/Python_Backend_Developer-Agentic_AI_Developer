"""
Custom Managers & QuerySets — Production Patterns

Run karne ke liye Django project ke andar `python manage.py shell` mein paste karo,
ya yeh patterns apne models mein adopt karo.
"""

# ==========================================================================
# PATTERN 1: Basic Custom Manager (filtering default queryset)
# ==========================================================================

from django.db import models
from django.utils import timezone
from datetime import timedelta


class PublishedManager(models.Manager):
    """Sirf published articles return karta hai."""

    def get_queryset(self):
        return super().get_queryset().filter(status='published')


# Usage:
# Article.objects.all()        -> sab articles (default manager)
# Article.published.all()      -> sirf published


# ==========================================================================
# PATTERN 2: Custom QuerySet with chainable methods (RECOMMENDED)
# ==========================================================================

class ArticleQuerySet(models.QuerySet):
    """Chainable business methods — readable code."""

    def published(self):
        return self.filter(status='published')

    def drafts(self):
        return self.filter(status='draft')

    def by_author(self, user):
        return self.filter(author=user)

    def recent(self, days=7):
        cutoff = timezone.now() - timedelta(days=days)
        return self.filter(created_at__gte=cutoff)

    def popular(self, min_views=1000):
        return self.filter(view_count__gte=min_views)

    def with_author_data(self):
        # Performance: avoid N+1
        return self.select_related('author').prefetch_related('tags')


# Pattern: as_manager() shortcut
class Article(models.Model):
    title = models.CharField(max_length=200)
    author = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    status = models.CharField(max_length=20, default='draft')
    view_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ArticleQuerySet.as_manager()

    class Meta:
        app_label = 'blog'  # adjust as needed


# Usage — fully chainable
# Article.objects.published().by_author(user).recent(30).popular()
# Article.objects.drafts().by_author(user).with_author_data()


# ==========================================================================
# PATTERN 3: Manager.from_queryset() — Manager + QuerySet methods both
# ==========================================================================

class OrderQuerySet(models.QuerySet):
    """Chainable filter methods."""

    def paid(self):
        return self.filter(status='paid')

    def pending(self):
        return self.filter(status='pending')

    def refundable(self):
        cutoff = timezone.now() - timedelta(days=30)
        return self.paid().filter(paid_at__gte=cutoff)

    def for_user(self, user):
        return self.filter(user=user)


class OrderManager(models.Manager):
    """Manager-only methods (creation, aggregation)."""

    def create_pending(self, user, amount):
        """Manager-level helper — not chainable."""
        return self.create(
            user=user,
            amount=amount,
            status='pending',
        )

    def total_revenue_today(self):
        """Aggregation method — Manager-level."""
        from django.db.models import Sum
        today = timezone.now().date()
        return self.filter(
            status='paid',
            paid_at__date=today,
        ).aggregate(total=Sum('amount'))['total'] or 0


class Order(models.Model):
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20)
    paid_at = models.DateTimeField(null=True, blank=True)

    # Combine: Manager methods + QuerySet methods
    objects = OrderManager.from_queryset(OrderQuerySet)()

    class Meta:
        app_label = 'blog'


# Usage
# Order.objects.create_pending(user, 99.99)        # Manager-only method
# Order.objects.paid().for_user(user).refundable() # chainable QS
# Order.objects.total_revenue_today()              # Manager aggregation


# ==========================================================================
# PATTERN 4: SOFT DELETE — Production-grade implementation
# ==========================================================================

class SoftDeleteQuerySet(models.QuerySet):
    """Override delete() to set timestamp instead."""

    def delete(self):
        # Bulk soft delete
        return super().update(deleted_at=timezone.now())

    def hard_delete(self):
        # Real DELETE — admin/cleanup use
        return super().delete()

    def alive(self):
        return self.filter(deleted_at__isnull=True)

    def dead(self):
        return self.filter(deleted_at__isnull=False)

    def restore(self):
        # Undelete
        return super().update(deleted_at=None)


class SoftDeleteManager(models.Manager):
    """Default manager — hides deleted rows."""

    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).alive()


class AllObjectsManager(models.Manager):
    """Admin/audit manager — includes deleted."""

    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db)


class SoftDeleteModel(models.Model):
    """Abstract base — inherit anywhere soft delete needed."""

    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    objects = SoftDeleteManager()         # default — hides deleted
    all_objects = AllObjectsManager()     # admin — includes deleted

    class Meta:
        abstract = True
        # CRITICAL: avoid cascade issues
        base_manager_name = 'all_objects'

    def delete(self, using=None, keep_parents=False):
        """Override instance delete."""
        self.deleted_at = timezone.now()
        self.save(using=using, update_fields=['deleted_at'])

    def hard_delete(self, using=None, keep_parents=False):
        """Actual DELETE — admin only."""
        return super().delete(using=using, keep_parents=keep_parents)

    def restore(self):
        self.deleted_at = None
        self.save(update_fields=['deleted_at'])


# Inherit anywhere
class Comment(SoftDeleteModel):
    body = models.TextField()
    author = models.ForeignKey('auth.User', on_delete=models.CASCADE)

    class Meta:
        app_label = 'blog'


# Usage
# Comment.objects.all()           -> alive only
# Comment.all_objects.all()       -> alive + deleted
# Comment.all_objects.dead()      -> only deleted
# comment.delete()                -> soft delete (sets deleted_at)
# comment.hard_delete()           -> real DELETE
# Comment.all_objects.dead().restore()  -> bulk restore


# ==========================================================================
# PATTERN 5: MULTI-TENANT Manager (with ContextVar)
# ==========================================================================

from contextvars import ContextVar

current_tenant_id: ContextVar[int | None] = ContextVar(
    'current_tenant_id',
    default=None,
)


class TenantQuerySet(models.QuerySet):
    def for_tenant(self, tenant_id):
        return self.filter(tenant_id=tenant_id)


class TenantManager(models.Manager):
    """Auto-filter by current tenant from context."""

    def get_queryset(self):
        qs = TenantQuerySet(self.model, using=self._db)
        tenant_id = current_tenant_id.get()
        if tenant_id is None:
            # Strict mode — raise rather than leak data
            raise RuntimeError(
                "Tenant context not set. "
                "Wrap request handler with tenant middleware."
            )
        return qs.filter(tenant_id=tenant_id)


class Project(models.Model):
    tenant_id = models.IntegerField(db_index=True)
    name = models.CharField(max_length=200)

    objects = TenantManager()
    all_tenants = models.Manager()  # admin override

    class Meta:
        app_label = 'blog'


# Middleware sets tenant context per-request
class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tenant_id = self._resolve_tenant(request)
        token = current_tenant_id.set(tenant_id)
        try:
            return self.get_response(request)
        finally:
            current_tenant_id.reset(token)

    def _resolve_tenant(self, request):
        # From subdomain / header / user.tenant
        return getattr(request.user, 'tenant_id', None)


# ==========================================================================
# PATTERN 6: Combine Soft Delete + Multi-Tenant
# ==========================================================================

class TenantSoftDeleteQuerySet(SoftDeleteQuerySet):
    def for_tenant(self, tenant_id):
        return self.filter(tenant_id=tenant_id)


class TenantSoftDeleteManager(models.Manager):
    def get_queryset(self):
        qs = TenantSoftDeleteQuerySet(self.model, using=self._db).alive()
        tenant_id = current_tenant_id.get()
        if tenant_id is None:
            raise RuntimeError("Tenant context required")
        return qs.filter(tenant_id=tenant_id)


# ==========================================================================
# PATTERN 7: Detecting Manager-related bugs in tests
# ==========================================================================

# tests/test_managers.py
"""
import pytest
from django.test import TestCase
from blog.models import Article


class ArticleManagerTests(TestCase):
    def test_published_excludes_drafts(self):
        Article.objects.create(title='Draft', status='draft')
        Article.objects.create(title='Live', status='published')

        published = Article.objects.published()

        assert published.count() == 1
        assert published.first().title == 'Live'

    def test_chained_queries(self):
        # Verify chain works
        Article.objects.published().by_author(user).recent().popular()

    def test_soft_delete_hides_from_default(self):
        c = Comment.objects.create(body='Hello')
        c.delete()  # soft delete

        assert Comment.objects.count() == 0
        assert Comment.all_objects.count() == 1
        assert Comment.all_objects.dead().count() == 1

    def test_restore(self):
        c = Comment.objects.create(body='Restore me')
        c.delete()
        c.restore()
        assert Comment.objects.filter(pk=c.pk).exists()
"""


# ==========================================================================
# DEBUGGING TIPS
# ==========================================================================
"""
1. `Article.objects.published().query` — print compiled SQL
2. `Article._meta.managers` — list all managers
3. `Article._meta.default_manager_name` — check default
4. `Article._meta.base_manager_name` — used for related lookups
5. Always test with `assertNumQueries()` to catch N+1 bugs

Common pitfall — admin doesn't show soft-deleted:
    # admin.py
    class CommentAdmin(admin.ModelAdmin):
        def get_queryset(self, request):
            return Comment.all_objects.get_queryset()  # NOT default!
"""
