# Django Management Commands — Production CLI Patterns

## Why It Matters (Senior 5 YOE Context)

Management commands = Django ka **production swiss-army knife**:

- **Cron jobs** → daily reports, cleanup, ETL
- **Data migrations** → one-time backfills, schema-aware transformations
- **Admin tools** → user impersonation, cache invalidation, debug helpers
- **Deployment scripts** → post-deploy hooks, smoke tests

Senior interviews mein common: "How do you run a one-time data migration on 50M rows safely?" — answer is mgmt command + chunked processing + `--dry-run`.

---

## Core Concepts

### Level 1: Basic Command

File: `myapp/management/commands/hello.py`

```python
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Prints hello — minimal example"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Hello!"))
```

Run: `python manage.py hello`

**Directory structure required:**
```
myapp/
    management/
        __init__.py
        commands/
            __init__.py
            hello.py
```

### Level 2: Arguments + Options

```python
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Recalculate user statistics"

    def add_arguments(self, parser):
        # Positional
        parser.add_argument('user_ids', nargs='+', type=int)
        # Optional flag
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print changes without writing to DB',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=1000,
            help='Rows per batch',
        )

    def handle(self, *args, **options):
        user_ids = options['user_ids']
        dry_run = options['dry_run']
        batch_size = options['batch_size']

        if not user_ids:
            raise CommandError("At least one user_id required")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no DB writes"))

        # ... actual work
```

Run: `python manage.py recalc_stats 1 2 3 --dry-run --batch-size 500`

### Level 3: Output Styling

```python
self.stdout.write(self.style.SUCCESS("Done!"))    # green
self.stdout.write(self.style.WARNING("Be careful")) # yellow
self.stdout.write(self.style.ERROR("Failed"))     # red
self.stdout.write(self.style.NOTICE("Heads up"))  # purple

# Verbosity-aware
verbosity = options['verbosity']  # 0, 1, 2, 3
if verbosity >= 2:
    self.stdout.write("Detailed log...")
```

### Level 4: Atomic Transactions + Error Handling

```python
from django.db import transaction


class Command(BaseCommand):
    help = "Migrate user emails to lowercase"

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            self._migrate(options)
        except Exception as e:
            # transaction.atomic auto-rolls back
            self.stderr.write(self.style.ERROR(f"Failed: {e}"))
            raise CommandError(str(e)) from e

    def _migrate(self, options):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        updated = User.objects.exclude(
            email=models.F('email__lower'),
        ).update(email=Lower('email'))
        self.stdout.write(f"Updated {updated} users")
```

### Level 5: Chunked Processing (large datasets)

Production critical — never load 50M rows into memory:

```python
from django.core.paginator import Paginator
from django.db import transaction


class Command(BaseCommand):
    help = "Backfill 'slug' column on 50M articles"

    def add_arguments(self, parser):
        parser.add_argument('--batch-size', type=int, default=1000)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        from blog.models import Article
        from django.utils.text import slugify

        qs = Article.objects.filter(slug='').order_by('pk')
        total = qs.count()
        self.stdout.write(f"Processing {total} articles")

        batch_size = options['batch_size']
        dry_run = options['dry_run']

        # iterator() — don't cache results, low memory
        processed = 0
        batch = []
        for article in qs.iterator(chunk_size=batch_size):
            article.slug = slugify(article.title)
            batch.append(article)
            if len(batch) >= batch_size:
                if not dry_run:
                    with transaction.atomic():
                        Article.objects.bulk_update(batch, ['slug'])
                processed += len(batch)
                batch = []
                self.stdout.write(
                    f"Processed {processed}/{total} ({processed * 100 // total}%)"
                )

        if batch and not dry_run:
            with transaction.atomic():
                Article.objects.bulk_update(batch, ['slug'])

        self.stdout.write(self.style.SUCCESS(f"Done: {processed}"))
```

### Level 6: Idempotent + Resumable Commands

```python
class Command(BaseCommand):
    help = "Sync users to external CRM — idempotent"

    def add_arguments(self, parser):
        parser.add_argument('--since', type=str, help='ISO date')

    def handle(self, *args, **options):
        # Resumable via timestamp checkpoint
        last_sync = self._get_last_sync(options.get('since'))

        users = User.objects.filter(updated_at__gte=last_sync)
        for user in users.iterator():
            self._sync_one(user)
            self._update_checkpoint(user.updated_at)

    def _get_last_sync(self, since):
        if since:
            from django.utils.dateparse import parse_datetime
            return parse_datetime(since)
        # From DB checkpoint or default
        return get_last_checkpoint() or timezone.now() - timedelta(days=7)
```

---

## How It Works Internally

### Discovery Mechanism

Django scans `INSTALLED_APPS` for `management/commands/*.py`:

```python
# django/core/management/__init__.py
def find_commands(management_dir):
    command_dir = os.path.join(management_dir, "commands")
    return [
        name for _, name, is_pkg in pkgutil.iter_modules([command_dir])
        if not is_pkg and not name.startswith("_")
    ]
```

**Pitfall:** Command file naam underscore se start hua to discover nahi hoga.

### `BaseCommand` Hierarchy

```
BaseCommand
├── AppCommand          # operates on apps
├── LabelCommand        # takes labels as args
└── NoArgsCommand       # deprecated, use BaseCommand
```

Always use `BaseCommand` unless specific need.

### `call_command()` — Programmatic Invocation

```python
from django.core.management import call_command

# From views, tasks, tests
call_command('recalc_stats', '1', '2', dry_run=True, batch_size=500)
```

Useful for Celery beat + management commands.

---

## Common Pitfalls

### 1. Memory Blowup with `.all()`

```python
# BAD — loads all rows
for u in User.objects.all():
    process(u)

# GOOD — streaming
for u in User.objects.iterator(chunk_size=1000):
    process(u)
```

### 2. Missing `--dry-run`

Production rule: **every destructive command MUST have `--dry-run`**. PRs without it get blocked.

### 3. Long-Running + No Logging

Add timestamps + progress:

```python
import time
start = time.monotonic()
# ... work
elapsed = time.monotonic() - start
self.stdout.write(f"Done in {elapsed:.1f}s")
```

### 4. Forgetting `app_label` in Standalone Scripts

If running `python -c "..."` instead of `manage.py`, `django.setup()` zaroori hai before importing models.

### 5. Catching `BaseException`

```python
# BAD — swallows Ctrl+C
try:
    work()
except Exception:
    pass

# GOOD — let KeyboardInterrupt propagate
try:
    work()
except CommandError:
    raise
except Exception as e:
    self.stderr.write(str(e))
    raise CommandError("Failed") from e
```

### 6. Transactional Scope Pitfalls

```python
# BAD — one giant transaction = lock contention, slow
@transaction.atomic
def handle(self, *args, **options):
    for u in User.objects.iterator():
        process(u)

# GOOD — per-batch transactions
def handle(self, *args, **options):
    for batch in chunked(User.objects.iterator(), 1000):
        with transaction.atomic():
            for u in batch:
                process(u)
```

---

## Interview Q&A

**Q1:** Management command bana ke 50M rows pe backfill kaise karoge safely?
**A:** `iterator(chunk_size=N)` + `bulk_update()` per-batch + per-batch `transaction.atomic()` + `--dry-run` flag + progress logging + idempotent design (resume from checkpoint). Optionally `Paginator` for indexed pagination over `iterator()`.

**Q2:** `call_command()` kab use karte ho?
**A:** Programmatic invocation — Celery tasks se, tests mein, views se. Argument passing kwargs ke through. Useful for reusing CLI logic in async workers without duplicating code.

**Q3:** `--dry-run` ka pattern explain karo.
**A:** Boolean flag jo destructive ops skip karta hai but SAME compute karta hai aur same output deta hai. Allows safe preview. Implementation: `if not options['dry_run']: save()`.

**Q4:** Management command vs Celery task — kab kya?
**A:** Mgmt command = sync, CLI-triggered, ops/devops use, blocking. Celery = async, queued, web-triggered, multiple workers. Mgmt commands for one-time/cron/admin work. Celery for per-request async work.

**Q5:** Cron mein mgmt command kaise schedule karoge?
**A:** Two options: (1) System cron → `0 2 * * * /path/python manage.py daily_report`. (2) `django-celery-beat` periodic task calling `call_command('daily_report')`. Beat is preferred — centralized, monitorable via Flower, retryable.

**Q6:** Memory blowup avoid kaise karoge?
**A:** `qs.iterator(chunk_size=1000)` instead of `qs.all()`. Avoid `len()` (forces eval) — use `count()`. Avoid building lists; stream and process. For complex aggregations, use raw SQL with server-side cursor.

**Q7:** Management command testable kaise banaoge?
**A:** Use `call_command()` in tests, capture stdout via `StringIO`:
```python
from io import StringIO
out = StringIO()
call_command('recalc_stats', '1', stdout=out, dry_run=True)
assert "Done" in out.getvalue()
```

**Q8:** Production mein mgmt command fail ho jaye to debug kaise?
**A:** Verbose flag (`-v 3`) for max output. Run with `--dry-run` first. Use `logging` module instead of `self.stdout.write` for structured logs. Add `--user-id 123 --debug` flags for single-row reproduction.

---

## Real-World Use Cases

### 1. Daily Cleanup

```bash
# crontab
0 3 * * * /app/venv/bin/python /app/manage.py cleanup_expired_sessions --days 7
```

### 2. Data Migration with Resume

```python
class Command(BaseCommand):
    def handle(self, *args, **options):
        checkpoint = Checkpoint.objects.get_or_create(name='email_migrate')[0]
        qs = User.objects.filter(pk__gt=checkpoint.last_pk).order_by('pk')

        for batch in chunked(qs.iterator(), 1000):
            with transaction.atomic():
                for user in batch:
                    user.email = user.email.lower()
                user.bulk_update(batch, ['email'])
                checkpoint.last_pk = batch[-1].pk
                checkpoint.save()
```

### 3. Health Check / Smoke Test

```python
class Command(BaseCommand):
    help = "Post-deploy smoke test"

    def handle(self, *args, **options):
        # DB check
        assert User.objects.count() > 0
        # Cache check
        cache.set('smoke', 1, 10)
        assert cache.get('smoke') == 1
        # External API check
        assert requests.get(STRIPE_HEALTH).status_code == 200
        self.stdout.write(self.style.SUCCESS("All systems green"))
```

---

## References

- [Django docs — Writing custom commands](https://docs.djangoproject.com/en/5.0/howto/custom-management-commands/)
- [Django source — BaseCommand](https://github.com/django/django/blob/main/django/core/management/base.py)
- Real-world: Instagram's `django-mass-mailer` mgmt commands (chunked, resumable)
- `django-extensions` package — 30+ useful commands as reference
