"""
Core Base Models — Mixins reused across all apps
═══════════════════════════════════════════════════
INTERVIEW TOPICS:
  - Abstract models vs concrete models
  - SoftDelete pattern (deleted_at instead of DELETE)
  - TimestampMixin — auto-set created_at / updated_at
  - Why use Abstract models? — DRY, no join overhead
"""

from django.db import models
from django.utils import timezone


# ─── Timestamp Mixin ──────────────────────────────────────
class TimestampMixin(models.Model):
    """Add created_at + updated_at to any model."""
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # abstract=True: no DB table created for this model
        # Child models get these fields in their own table
        abstract = True


# ─── SoftDelete Mixin ─────────────────────────────────────
class SoftDeleteQuerySet(models.QuerySet):
    """QuerySet that excludes soft-deleted records by default."""

    def active(self):
        """Return only non-deleted records."""
        return self.filter(deleted_at__isnull=True)

    def deleted(self):
        """Return only soft-deleted records."""
        return self.filter(deleted_at__isnull=False)

    def delete(self):
        """Override bulk delete → set deleted_at."""
        return self.update(deleted_at=timezone.now())

    def hard_delete(self):
        """Actual DB deletion."""
        return super().delete()

    def restore(self):
        """Restore soft-deleted records."""
        return self.update(deleted_at=None)


class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        # Default manager only shows active (non-deleted) records
        return SoftDeleteQuerySet(self.model, using=self._db).active()

    def all_with_deleted(self):
        """Returns ALL records including soft-deleted."""
        return SoftDeleteQuerySet(self.model, using=self._db)

    def only_deleted(self):
        return SoftDeleteQuerySet(self.model, using=self._db).deleted()


class SoftDeleteMixin(models.Model):
    """
    Soft delete pattern — never physically delete rows.

    INTERVIEW: Why soft delete?
    - Audit trail / compliance (GDPR right to delete ≠ immediately wipe)
    - Restore accidentally deleted records
    - FK integrity (related records still point to valid row)
    - Analytics on historical data

    INTERVIEW: Downsides?
    - DB rows grow forever → need archival/cleanup job
    - All queries must filter deleted_at IS NULL → index needed
    - UNIQUE constraints break (email can't be reused after soft delete)
      Fix: composite unique (email, deleted_at) or use uuid as soft-delete marker
    """
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    # Replace default manager
    objects = SoftDeleteManager()

    def delete(self, using=None, keep_parents=False):
        """Soft delete — set deleted_at instead of DELETE."""
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at"])

    def restore(self):
        """Restore a soft-deleted record."""
        self.deleted_at = None
        self.save(update_fields=["deleted_at"])

    def hard_delete(self, using=None, keep_parents=False):
        """Force actual deletion."""
        super().delete(using=using, keep_parents=keep_parents)

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    class Meta:
        abstract = True


# ─── Base Model (TimestampMixin + SoftDelete) ─────────────
class BaseModel(SoftDeleteMixin, TimestampMixin):
    """
    Standard base for all models in this project.
    Provides: id, created_at, updated_at, deleted_at
    """
    class Meta:
        abstract = True
        ordering = ["-created_at"]  # newest first by default
