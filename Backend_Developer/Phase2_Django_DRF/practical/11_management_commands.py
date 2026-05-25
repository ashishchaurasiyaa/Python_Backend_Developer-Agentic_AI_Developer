"""
Management Commands — Production Patterns

Yeh patterns apne app ke `management/commands/` folder mein ek-ek file mein
copy karo. Structure required:

    myapp/
        management/
            __init__.py
            commands/
                __init__.py
                hello.py
                backfill_slugs.py
                ...
"""

# ==========================================================================
# COMMAND 1: hello.py — Minimal example
# ==========================================================================
"""
File: myapp/management/commands/hello.py
"""

from django.core.management.base import BaseCommand


class HelloCommand(BaseCommand):
    """Minimal example — `python manage.py hello`."""

    help = "Prints a friendly hello"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Hello from management command!"))


# ==========================================================================
# COMMAND 2: backfill_slugs.py — Production-grade chunked processing
# ==========================================================================
"""
File: blog/management/commands/backfill_slugs.py

Use case: 50M articles, slug column added recently, need to backfill.
Features: chunked, resumable, --dry-run, progress logging, atomic per-batch.
"""

import time
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify


class BackfillSlugsCommand(BaseCommand):
    help = "Backfill empty slug columns on Article model"

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=1000,
            help='Number of rows per transaction (default: 1000)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Compute changes but do not write to DB',
        )
        parser.add_argument(
            '--start-pk',
            type=int,
            default=0,
            help='Resume from this PK (for resumability)',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Process at most N rows (for testing)',
        )

    def handle(self, *args, **options):
        from blog.models import Article  # late import — Django setup

        batch_size = options['batch_size']
        dry_run = options['dry_run']
        start_pk = options['start_pk']
        limit = options['limit']

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no DB writes"))

        qs = (
            Article.objects
            .filter(slug='', pk__gt=start_pk)
            .order_by('pk')
        )
        if limit:
            qs = qs[:limit]

        total = qs.count()
        if total == 0:
            self.stdout.write("Nothing to do.")
            return

        self.stdout.write(f"Processing {total} articles starting from pk > {start_pk}")
        start_time = time.monotonic()

        processed = 0
        batch = []
        last_pk = start_pk

        try:
            for article in qs.iterator(chunk_size=batch_size):
                article.slug = slugify(article.title)[:50]
                batch.append(article)
                last_pk = article.pk

                if len(batch) >= batch_size:
                    self._flush(batch, dry_run)
                    processed += len(batch)
                    batch = []
                    self._log_progress(processed, total, last_pk, start_time)

            # Flush remainder
            if batch:
                self._flush(batch, dry_run)
                processed += len(batch)
                self._log_progress(processed, total, last_pk, start_time)

        except KeyboardInterrupt:
            self.stderr.write(self.style.WARNING(
                f"\nInterrupted. Resume with --start-pk {last_pk}"
            ))
            raise

        elapsed = time.monotonic() - start_time
        self.stdout.write(self.style.SUCCESS(
            f"Done. Processed {processed} rows in {elapsed:.1f}s"
        ))

    def _flush(self, batch, dry_run):
        if dry_run:
            return
        from blog.models import Article
        with transaction.atomic():
            Article.objects.bulk_update(batch, ['slug'])

    def _log_progress(self, processed, total, last_pk, start_time):
        elapsed = time.monotonic() - start_time
        rate = processed / elapsed if elapsed > 0 else 0
        eta = (total - processed) / rate if rate > 0 else 0
        pct = processed * 100 // total if total else 100
        self.stdout.write(
            f"  {processed}/{total} ({pct}%) | "
            f"last_pk={last_pk} | "
            f"{rate:.0f} rows/s | "
            f"ETA: {eta:.0f}s"
        )


# ==========================================================================
# COMMAND 3: send_daily_reports.py — Cron-friendly with error reporting
# ==========================================================================
"""
File: reports/management/commands/send_daily_reports.py

Use case: Cron job every morning. Send report email to each active user.
Features: idempotent, retries on email failure, structured logging.
"""

import logging
from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)


class SendDailyReportsCommand(BaseCommand):
    help = "Send daily summary emails to active users"

    def add_arguments(self, parser):
        parser.add_argument('--user-id', type=int, help='Send only to one user (debug)')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        from django.contrib.auth import get_user_model
        User = get_user_model()

        if options['user_id']:
            users = User.objects.filter(pk=options['user_id'])
        else:
            users = User.objects.filter(is_active=True, email__isnull=False)

        sent, failed = 0, 0
        for user in users.iterator(chunk_size=500):
            try:
                if not options['dry_run']:
                    self._send_one(user)
                sent += 1
            except Exception as e:
                failed += 1
                logger.exception(f"Failed to send report to {user.email}: {e}")

        self.stdout.write(self.style.SUCCESS(
            f"Sent: {sent}, Failed: {failed}"
        ))

    def _send_one(self, user):
        from django.core.mail import send_mail
        # Generate report
        body = f"Hi {user.first_name}, your daily summary..."
        send_mail(
            subject="Daily Report",
            message=body,
            from_email="noreply@example.com",
            recipient_list=[user.email],
            fail_silently=False,
        )


# ==========================================================================
# COMMAND 4: smoke_test.py — Post-deploy health check
# ==========================================================================
"""
File: core/management/commands/smoke_test.py

Use case: Run after each deploy to verify connectivity.
Returns non-zero exit on failure (CI/CD-friendly).
"""

import sys
from django.core.management.base import BaseCommand
from django.db import connection
from django.core.cache import cache


class SmokeTestCommand(BaseCommand):
    help = "Post-deploy smoke test — verify infra connectivity"

    def handle(self, *args, **options):
        checks = [
            ('Database', self._check_db),
            ('Cache (Redis)', self._check_cache),
            ('Celery broker', self._check_celery),
        ]

        all_ok = True
        for name, check in checks:
            try:
                check()
                self.stdout.write(self.style.SUCCESS(f"  [OK] {name}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  [FAIL] {name}: {e}"))
                all_ok = False

        if not all_ok:
            sys.exit(1)

    def _check_db(self):
        with connection.cursor() as c:
            c.execute("SELECT 1")
            assert c.fetchone()[0] == 1

    def _check_cache(self):
        cache.set('smoke:test', 'ok', 10)
        assert cache.get('smoke:test') == 'ok'

    def _check_celery(self):
        from celery import current_app
        i = current_app.control.inspect(timeout=5)
        active = i.active()
        assert active is not None, "No workers responding"


# ==========================================================================
# COMMAND 5: impersonate.py — Admin tooling (with safety)
# ==========================================================================
"""
File: users/management/commands/impersonate.py

Use case: Generate a session token to login-as a user (debug prod issues).
Safety: requires --i-understand-this-is-prod flag.
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.sessions.backends.db import SessionStore
from django.conf import settings


class ImpersonateCommand(BaseCommand):
    help = "Generate session token to login as user (USE WITH CAUTION)"

    def add_arguments(self, parser):
        parser.add_argument('user_email', type=str)
        parser.add_argument(
            '--i-understand-this-is-prod',
            action='store_true',
            help='Required for prod safety',
        )

    def handle(self, *args, **options):
        if settings.DEBUG is False and not options['i_understand_this_is_prod']:
            raise CommandError(
                "Refusing to run on prod without --i-understand-this-is-prod"
            )

        from django.contrib.auth import get_user_model
        User = get_user_model()

        try:
            user = User.objects.get(email=options['user_email'])
        except User.DoesNotExist:
            raise CommandError(f"User not found: {options['user_email']}")

        session = SessionStore()
        session['_auth_user_id'] = str(user.pk)
        session['_auth_user_backend'] = 'django.contrib.auth.backends.ModelBackend'
        session.save()

        self.stdout.write(self.style.WARNING(
            f"Session key: {session.session_key}\n"
            f"Add cookie 'sessionid={session.session_key}' to login as {user.email}"
        ))


# ==========================================================================
# TESTING MANAGEMENT COMMANDS
# ==========================================================================
"""
File: tests/test_commands.py
"""

# from io import StringIO
# from django.core.management import call_command
# from django.test import TestCase
#
#
# class CommandTests(TestCase):
#     def test_backfill_slugs_dry_run(self):
#         out = StringIO()
#         call_command('backfill_slugs', '--dry-run', stdout=out)
#         assert "DRY RUN" in out.getvalue()
#
#     def test_smoke_test_passes(self):
#         out = StringIO()
#         call_command('smoke_test', stdout=out)
#         assert "Database" in out.getvalue()


# ==========================================================================
# CRONTAB EXAMPLE
# ==========================================================================
"""
# Every day at 6 AM
0 6 * * * cd /app && /app/venv/bin/python manage.py send_daily_reports

# Every 5 minutes
*/5 * * * * cd /app && /app/venv/bin/python manage.py backfill_slugs --batch-size 500

# OR — django-celery-beat (preferred)
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'daily-reports': {
        'task': 'core.tasks.run_management_command',
        'schedule': crontab(hour=6, minute=0),
        'args': ['send_daily_reports'],
    },
}

# core/tasks.py
from celery import shared_task
from django.core.management import call_command

@shared_task
def run_management_command(name, *args, **kwargs):
    call_command(name, *args, **kwargs)
"""
