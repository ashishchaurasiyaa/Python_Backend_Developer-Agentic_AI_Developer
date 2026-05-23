"""
Django Signals — Users App
═══════════════════════════════════════
INTERVIEW: Signals kab use karte hain?
  - User create → profile auto-create
  - Order placed → send email (loose coupling)
  - File deleted → cleanup storage
  - Audit log on model save/delete

INTERVIEW: Signals ke alternatives?
  - Service layer method call (more explicit, easier to test)
  - Celery tasks (for heavy async work)
  - Model's save() override (simpler for same-model changes)

INTERVIEW: pre_save vs post_save?
  pre_save:  before DB write — good for calculating values, validation
  post_save: after DB write  — good for side effects (email, cache invalidation)
             `created=True` only on first save (INSERT, not UPDATE)

INTERVIEW: Signal mein transaction ka dhyan rakho!
  post_save runs inside the SAME transaction.
  If you send Celery task in post_save and transaction rolls back,
  task still runs → use transaction.on_commit() instead!
"""

import logging
from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver, Signal
from django.db import transaction

log = logging.getLogger(__name__)

# Custom signals — loose coupling between apps
user_email_verified  = Signal()  # sender: User instance
user_plan_upgraded   = Signal()  # sender: User, kwargs: old_plan, new_plan


# ─── Auto-create UserProfile ─────────────────────────────
@receiver(post_save, sender="users.User")
def create_user_profile(sender, instance, created: bool, **kwargs):
    """
    Automatically create UserProfile when a new User is created.
    Uses transaction.on_commit to avoid issues with rollbacks.
    """
    if not created:
        return

    def _create():
        from users.models import UserProfile
        UserProfile.objects.get_or_create(user=instance)
        log.info("User profile created: %s", instance.email)

    # on_commit — only runs if the outer transaction commits successfully
    # INTERVIEW: Why on_commit? Because if user creation rolls back,
    # we don't want orphaned profile records.
    transaction.on_commit(_create)


# ─── Track plan upgrades ──────────────────────────────────
@receiver(pre_save, sender="users.User")
def track_plan_change(sender, instance, **kwargs):
    """
    Detect plan change before save.
    Fire custom signal after successful save.
    """
    if not instance.pk:
        return  # new user — no previous state

    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    if old.plan != instance.plan:
        # Store on instance so post_save can access it
        instance._plan_changed_from = old.plan


@receiver(post_save, sender="users.User")
def fire_plan_upgrade_signal(sender, instance, created: bool, **kwargs):
    if created:
        return
    old_plan = getattr(instance, "_plan_changed_from", None)
    if old_plan and old_plan != instance.plan:
        transaction.on_commit(
            lambda: user_plan_upgraded.send(
                sender=sender,
                instance=instance,
                old_plan=old_plan,
                new_plan=instance.plan,
            )
        )
        log.info("Plan changed: %s → %s for %s", old_plan, instance.plan, instance.email)


# ─── Listen to custom signals ─────────────────────────────
@receiver(user_plan_upgraded)
def on_plan_upgraded(sender, instance, old_plan: str, new_plan: str, **kwargs):
    """Send upgrade confirmation email when user upgrades plan."""
    log.info("🎉 Plan upgrade email queued: %s → %s for %s",
             old_plan, new_plan, instance.email)
    # In real app: send_upgrade_email.delay(instance.id, old_plan, new_plan)


@receiver(user_email_verified)
def on_email_verified(sender, instance, **kwargs):
    """Grant welcome bonus when user verifies email."""
    log.info("📧 Email verified: %s — granting welcome bonus", instance.email)
    # In real app: grant_welcome_credits.delay(instance.id)


# ─── Cleanup on user delete ───────────────────────────────
@receiver(post_delete, sender="users.User")
def cleanup_user_data(sender, instance, **kwargs):
    """Clean up avatar file when user is deleted."""
    if instance.avatar:
        try:
            instance.avatar.delete(save=False)
        except Exception:
            log.exception("Failed to delete avatar for %s", instance.email)
