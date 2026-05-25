"""
Audit Logging — Production Patterns
"""

# ==========================================================================
# 1. SETTINGS for django-simple-history
# ==========================================================================
"""
# pip install django-simple-history
INSTALLED_APPS += ['simple_history']
MIDDLEWARE += ['simple_history.middleware.HistoryRequestMiddleware']

# Optional: model name for the user model that history can reference
SIMPLE_HISTORY_REVERT_DISABLED = False
"""


# ==========================================================================
# 2. MODEL WITH HISTORY
# ==========================================================================

from django.db import models
from simple_history.models import HistoricalRecords


class Article(models.Model):
    title = models.CharField(max_length=200)
    body = models.TextField()
    status = models.CharField(max_length=20, default='draft')
    author = models.ForeignKey('auth.User', on_delete=models.CASCADE)

    history = HistoricalRecords(
        excluded_fields=['view_count'],
        cascade_delete_history=True,
    )

    class Meta:
        app_label = 'blog'


# ==========================================================================
# 3. QUERYING HISTORY
# ==========================================================================

def show_article_history(article_id):
    article = Article.objects.get(pk=article_id)

    # All historical versions
    for h in article.history.all():
        print(f"{h.history_date} | {h.history_type} | by {h.history_user}")
        print(f"  title: {h.title}")

    # Diff between latest two versions
    new = article.history.first()
    old = new.prev_record
    if old:
        delta = new.diff_against(old)
        for change in delta.changes:
            print(f"  {change.field}: {change.old!r} → {change.new!r}")


def get_article_state_at(article_id, when):
    """What did the article look like at a specific time?"""
    article = Article.objects.get(pk=article_id)
    historical = article.history.as_of(when)
    return historical


def revert_article(article_id, history_id):
    article = Article.objects.get(pk=article_id)
    target_version = article.history.get(history_id=history_id)
    # Apply old values
    for f in Article._meta.fields:
        setattr(article, f.name, getattr(target_version, f.name))
    article.save()


# ==========================================================================
# 4. CUSTOM AUDIT VIA SIGNALS (no library)
# ==========================================================================

from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType


class AuditEntry(models.Model):
    actor = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)
    verb = models.CharField(max_length=20)  # create/update/delete
    target_ct = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    target_id = models.PositiveIntegerField()
    changes = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = 'blog'
        indexes = [
            models.Index(fields=['target_ct', 'target_id', '-created_at']),
            models.Index(fields=['actor', '-created_at']),
        ]


AUDITED_MODELS_NAMES = {'Article', 'Order', 'Payment'}


def _serialize_value(v):
    """Convert value to JSON-safe representation."""
    if v is None:
        return None
    if isinstance(v, (str, int, float, bool)):
        return v
    if hasattr(v, 'pk'):  # FK
        return v.pk
    return str(v)


@receiver(pre_save)
def capture_old_values(sender, instance, **kwargs):
    if sender.__name__ not in AUDITED_MODELS_NAMES:
        return
    if not instance.pk:
        instance._audit_old = {}
        return
    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        instance._audit_old = {}
        return

    sensitive = {'password', 'ssn', 'api_key', 'secret'}
    instance._audit_old = {
        f.name: _serialize_value(getattr(old, f.name))
        for f in sender._meta.fields
        if f.name not in sensitive
    }


@receiver(post_save)
def log_changes(sender, instance, created, **kwargs):
    if sender.__name__ not in AUDITED_MODELS_NAMES:
        return

    old = getattr(instance, '_audit_old', {})
    sensitive = {'password', 'ssn', 'api_key', 'secret'}

    changes = {}
    for f in sender._meta.fields:
        if f.name in sensitive:
            continue
        new_val = _serialize_value(getattr(instance, f.name))
        old_val = old.get(f.name) if not created else None
        if created or old_val != new_val:
            changes[f.name] = {'old': old_val, 'new': new_val}

    if changes or created:
        AuditEntry.objects.create(
            actor=getattr(instance, '_audit_actor', None),
            verb='create' if created else 'update',
            target_ct=ContentType.objects.get_for_model(sender),
            target_id=instance.pk,
            changes=changes,
        )


@receiver(post_delete)
def log_delete(sender, instance, **kwargs):
    if sender.__name__ not in AUDITED_MODELS_NAMES:
        return
    AuditEntry.objects.create(
        actor=getattr(instance, '_audit_actor', None),
        verb='delete',
        target_ct=ContentType.objects.get_for_model(sender),
        target_id=instance.pk,
    )


# ==========================================================================
# 5. CURRENT USER VIA CONTEXTVAR (async-safe)
# ==========================================================================

from contextvars import ContextVar


current_user: ContextVar = ContextVar('current_user', default=None)
current_request_id: ContextVar = ContextVar('current_request_id', default=None)


class AuditUserMiddleware:
    """Sets current_user contextvar for downstream signal handlers."""

    sync_capable = True
    async_capable = True

    def __init__(self, get_response):
        self.get_response = get_response
        import asyncio
        self._is_async = asyncio.iscoroutinefunction(get_response)

    def __call__(self, request):
        if self._is_async:
            return self.__acall__(request)
        return self._do(request)

    async def __acall__(self, request):
        token_user = current_user.set(
            request.user if request.user.is_authenticated else None
        )
        token_req = current_request_id.set(getattr(request, 'request_id', None))
        try:
            return await self.get_response(request)
        finally:
            current_user.reset(token_user)
            current_request_id.reset(token_req)

    def _do(self, request):
        token_user = current_user.set(
            request.user if request.user.is_authenticated else None
        )
        token_req = current_request_id.set(getattr(request, 'request_id', None))
        try:
            return self.get_response(request)
        finally:
            current_user.reset(token_user)
            current_request_id.reset(token_req)


# Use in signals:
@receiver(pre_save)
def inject_current_user(sender, instance, **kwargs):
    if sender.__name__ not in AUDITED_MODELS_NAMES:
        return
    if not hasattr(instance, '_audit_actor'):
        instance._audit_actor = current_user.get()


# ==========================================================================
# 6. AUDITABLE MIXIN PATTERN
# ==========================================================================

class AuditableModel(models.Model):
    """Add created_at, updated_at, created_by, updated_by to any model."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    updated_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        user = current_user.get()
        if user:
            if not self.pk:
                self.created_by = user
            self.updated_by = user
        super().save(*args, **kwargs)


# Usage
# class MyModel(AuditableModel):
#     name = models.CharField(max_length=200)


# ==========================================================================
# 7. CELERY TASK — pass actor explicitly
# ==========================================================================

from celery import shared_task


@shared_task
def update_article_async(article_id, new_title, actor_user_id):
    """Audit-aware async update."""
    article = Article.objects.get(pk=article_id)

    if actor_user_id:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            actor = User.objects.get(pk=actor_user_id)
            article._audit_actor = actor
        except User.DoesNotExist:
            pass

    article.title = new_title
    article.save()


# ==========================================================================
# 8. HMAC-SIGNED AUDIT ENTRIES (tamper detection)
# ==========================================================================

import hmac
import hashlib
from django.conf import settings


class TamperProofAudit(models.Model):
    actor = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)
    verb = models.CharField(max_length=20)
    target_ct = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    target_id = models.PositiveIntegerField()
    changes = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    signature = models.CharField(max_length=64)

    class Meta:
        app_label = 'blog'

    def _compute_signature(self):
        import json
        payload = '|'.join([
            str(self.actor_id) if self.actor_id else '',
            self.verb,
            str(self.target_ct_id),
            str(self.target_id),
            json.dumps(self.changes, sort_keys=True),
            self.created_at.isoformat() if self.created_at else '',
        ])
        key = getattr(settings, 'AUDIT_HMAC_KEY', settings.SECRET_KEY).encode()
        return hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Set signature after save so created_at is populated
        if not self.signature:
            self.signature = self._compute_signature()
            super().save(update_fields=['signature'])

    def verify(self):
        return hmac.compare_digest(self.signature, self._compute_signature())


# ==========================================================================
# 9. MGMT COMMAND — Audit Retention (compliance cleanup)
# ==========================================================================
"""
File: ops/management/commands/audit_retention.py
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta


class AuditRetentionCommand(BaseCommand):
    help = "Delete audit entries older than retention period"

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=730)  # 2 years
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=options['days'])
        # from blog.models import AuditEntry

        qs = AuditEntry.objects.filter(created_at__lt=cutoff)
        count = qs.count()
        self.stdout.write(f"Found {count} entries older than {options['days']} days")

        if options['dry_run']:
            return

        # Chunked delete for huge tables
        while True:
            ids = list(qs.values_list('pk', flat=True)[:10000])
            if not ids:
                break
            AuditEntry.objects.filter(pk__in=ids).delete()
            self.stdout.write(f"  deleted {len(ids)}")


# ==========================================================================
# 10. ADMIN INTEGRATION (read-only audit viewer)
# ==========================================================================

from django.contrib import admin


# @admin.register(AuditEntry)
class AuditEntryAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'actor', 'verb', 'target_label', 'changes_preview')
    list_select_related = ('actor', 'target_ct')
    list_filter = ('verb', 'target_ct', 'created_at')
    search_fields = ('actor__username', 'target_id')
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser  # only superuser can purge

    @admin.display(description='Target')
    def target_label(self, obj):
        return f'{obj.target_ct.model}#{obj.target_id}'

    @admin.display(description='Changes')
    def changes_preview(self, obj):
        if not obj.changes:
            return '-'
        keys = list(obj.changes.keys())[:3]
        return ', '.join(keys) + ('...' if len(obj.changes) > 3 else '')
