"""
Django Migrations in Production — Production Patterns
======================================================
Covers every major pattern from the theory doc:

  - Migration anatomy and auto-detection limits
  - Small migrations vs. batched changes
  - Separating schema migrations from data migrations
  - Reversible RunPython (forwards / backwards)
  - Atomic vs. non-atomic migrations
  - CONCURRENTLY indexes for Postgres (zero downtime)
  - Adding NOT NULL columns to large tables in three steps
  - Renaming fields safely
  - Custom SQL migrations (DDL outside Django ORM)
  - Multi-database routing
  - Advisory locks to prevent concurrent migration runs
  - Bulk operations and signal suppression inside RunPython
  - Migration linting (django-migration-linter)
  - Squashing migrations — when and how
  - Faking migrations — when it is safe
  - Migration testing patterns
  - Running migrations in production (deploy-job vs. rolling deploy)

This module is intentionally structured as importable production code.
Django must be configured before any ORM calls; the __main__ block
demonstrates standalone usage via a minimal in-memory SQLite setup.

pip install django django-migration-linter
"""

from __future__ import annotations

import logging
import os
import sys
from functools import wraps
from io import StringIO
from typing import Any

# ==========================================================================
# 1. MINIMAL DJANGO SETUP (SQLite — no external infra required)
# ==========================================================================

# Configure Django before importing any django.* symbols.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "__main__")

import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        INSTALLED_APPS=[
            "django.contrib.contenttypes",
            "django.contrib.auth",
            # In a real project you would list your own apps here.
            # "myapp",
        ],
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": ":memory:",
            },
            # Example second database — requires DATABASE_ROUTERS in settings.
            # "analytics": {
            #     "ENGINE": "django.db.backends.sqlite3",
            #     "NAME": "/tmp/analytics.db",
            # },
        },
        DATABASE_ROUTERS=[],
        DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
    )

    django.setup()

from django.db import migrations, models, transaction, connection

log = logging.getLogger(__name__)


# ==========================================================================
# 2. MIGRATION ANATOMY — reference examples
# ==========================================================================

# A minimal auto-generated migration file looks like this.  It is shown as
# a string here because Django discovers migrations on disk; you would never
# define them as runtime objects.

EXAMPLE_SCHEMA_MIGRATION = '''
# myapp/migrations/0002_add_phone.py
from django.db import migrations, models


class Migration(migrations.Migration):
    """Schema-only migration: add nullable phone column."""

    dependencies = [("myapp", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="user",
            name="phone",
            field=models.CharField(max_length=20, blank=True, null=True),
        ),
    ]
'''

EXAMPLE_DATA_MIGRATION = '''
# myapp/migrations/0003_populate_phone.py
#
# Data migrations are always kept SEPARATE from schema migrations.
# Schema migrations can be applied with zero downtime; data migrations
# can take hours on large tables and must never hold a DDL lock.

from django.db import migrations


def forwards(apps, schema_editor):
    # Use apps.get_model(), never "from myapp.models import User".
    # apps.get_model() returns the *historical* model definition that
    # matches this exact migration — safe if the model changes later.
    User = apps.get_model("myapp", "User")
    User.objects.filter(phone__isnull=True).update(phone="")


def backwards(apps, schema_editor):
    User = apps.get_model("myapp", "User")
    User.objects.update(phone=None)


class Migration(migrations.Migration):
    dependencies = [("myapp", "0002_add_phone")]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
'''


# ==========================================================================
# 3. REVERSIBLE RunPython PATTERN
# ==========================================================================

def make_reversible_data_migration(
    app_label: str,
    model_name: str,
    old_value: str,
    new_value: str,
) -> dict[str, Any]:
    """
    Return a dict representing a reversible data-migration operation.

    In a real project you would embed 'forwards' and 'backwards' directly
    in the migration file.  This factory makes the pattern testable in
    isolation.

    Parameters
    ----------
    app_label:  Django app label (e.g. "myapp").
    model_name: Model name as a string (e.g. "User").
    old_value:  Value to migrate FROM in the ``role`` column.
    new_value:  Value to migrate TO in the ``role`` column.
    """

    def forwards(apps, schema_editor):
        Model = apps.get_model(app_label, model_name)
        Model.objects.filter(role=old_value).update(role=new_value)

    def backwards(apps, schema_editor):
        Model = apps.get_model(app_label, model_name)
        Model.objects.filter(role=new_value).update(role=old_value)

    return {
        "operation": migrations.RunPython(forwards, backwards),
        "description": f"Rename role '{old_value}' → '{new_value}' (reversible)",
    }


# ==========================================================================
# 4. NON-ATOMIC MIGRATION — CONCURRENTLY INDEXES (Postgres)
# ==========================================================================

# Default Django migrations run inside a transaction.  Postgres CANNOT run
# CREATE INDEX CONCURRENTLY inside a transaction.  Setting atomic=False is
# mandatory for this pattern.

EXAMPLE_CONCURRENT_INDEX_MIGRATION = '''
# myapp/migrations/0004_email_index.py
#
# pip install psycopg2-binary  (or psycopg2)
# pip install django  (django.contrib.postgres required)

from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations
from django.db.models import Index


class Migration(migrations.Migration):
    """Add email index without locking the users table."""

    atomic = False   # Required for CONCURRENTLY

    dependencies = [("myapp", "0003_populate_phone")]

    operations = [
        AddIndexConcurrently(
            model_name="user",
            index=Index(fields=["email"], name="user_email_idx"),
        ),
    ]
'''

# The raw-SQL equivalent (useful when django.contrib.postgres is unavailable):
EXAMPLE_CONCURRENT_INDEX_RAW_SQL = '''
class Migration(migrations.Migration):
    atomic = False

    operations = [
        migrations.RunSQL(
            sql="CREATE INDEX CONCURRENTLY ix_users_email ON users_user(email)",
            reverse_sql="DROP INDEX CONCURRENTLY ix_users_email",
        ),
    ]
'''


# ==========================================================================
# 5. ADDING A NOT NULL COLUMN TO A LARGE TABLE — THREE-STEP PATTERN
# ==========================================================================

# Adding a NOT NULL column with a default in one step rewrites every row
# and holds a full table lock.  At scale (millions of rows) this means
# minutes of downtime.  The safe pattern splits the change across three
# separate deploys.

THREE_STEP_NOT_NULL = '''
# ---------- Deploy 1: add nullable column (fast — no row rewrite) ----------
# myapp/migrations/0010_add_phone_nullable.py

class Migration(migrations.Migration):
    operations = [
        migrations.AddField(
            model_name="user", name="phone",
            field=models.CharField(max_length=20, null=True),
        ),
    ]


# ---------- Deploy 2: backfill in batches (runs without DDL lock) ----------
# myapp/migrations/0011_backfill_phone.py

def backfill_phone(apps, schema_editor):
    User = apps.get_model("myapp", "User")
    batch_size = 1_000
    # Process in batches to keep transactions short and avoid lock escalation.
    while True:
        ids = list(
            User.objects.filter(phone__isnull=True)
            .values_list("id", flat=True)[:batch_size]
        )
        if not ids:
            break
        User.objects.filter(id__in=ids).update(phone="")

class Migration(migrations.Migration):
    operations = [migrations.RunPython(backfill_phone, migrations.RunPython.noop)]


# ---------- Deploy 3: tighten to NOT NULL (fast — all rows already filled) -
# myapp/migrations/0012_phone_not_null.py

class Migration(migrations.Migration):
    operations = [
        migrations.AlterField(
            model_name="user", name="phone",
            field=models.CharField(max_length=20, null=False, default=""),
        ),
    ]
'''


# ==========================================================================
# 6. BATCH BACKFILL HELPER (usable in RunPython functions)
# ==========================================================================

def batch_update(queryset_factory, update_kwargs: dict, batch_size: int = 1_000) -> int:
    """
    Apply ``update_kwargs`` to all rows returned by ``queryset_factory`` in
    batches.  Returns total number of rows updated.

    ``queryset_factory`` must be a callable that returns a fresh queryset each
    call (important — Django re-evaluates the WHERE clause per batch).

    Usage inside a RunPython function::

        def forwards(apps, schema_editor):
            User = apps.get_model("myapp", "User")
            total = batch_update(
                queryset_factory=lambda: User.objects.filter(phone__isnull=True),
                update_kwargs={"phone": ""},
                batch_size=500,
            )
            print(f"Backfilled {total} rows.")
    """
    total_updated = 0
    while True:
        ids = list(
            queryset_factory()
            .values_list("pk", flat=True)[:batch_size]
        )
        if not ids:
            break
        # Fetch the underlying model from the queryset and update by PK list.
        count = queryset_factory().model.objects.filter(pk__in=ids).update(**update_kwargs)
        total_updated += count
    return total_updated


# ==========================================================================
# 7. FIELD RENAME — SAFE PATTERN
# ==========================================================================

# A naive RenameField migration causes an AttributeError in any app code
# that still references the old name while the migration is running or
# before the code is redeployed.  The expand-contract pattern avoids this.

RENAME_FIELD_SAFE_STEPS = """
Expand-Contract rename (zero downtime):

Step 1 (Schema):  Add new column ``email`` alongside old ``email_addr``.
Step 2 (Code):    Deploy code that dual-writes both columns on every write.
Step 3 (Data):    Backfill migration copies email_addr → email for all rows.
Step 4 (Code):    Switch all reads to ``email``; keep writing both.
Step 5 (Code):    Stop writing to ``email_addr``.
Step 6 (Schema):  Drop old column ``email_addr``.

This pattern requires 4–6 deploys.  It guarantees zero downtime because no
single migration step invalidates live application code.
"""

EXAMPLE_RENAME_MIGRATION = '''
# The simple (downtime-acceptable) alternative:
class Migration(migrations.Migration):
    operations = [
        migrations.RenameField(
            model_name="user",
            old_name="email_addr",
            new_name="email",
        ),
    ]
'''


# ==========================================================================
# 8. CUSTOM SQL MIGRATION — DDL NOT SUPPORTED BY DJANGO ORM
# ==========================================================================

EXAMPLE_CUSTOM_SQL_MIGRATION = '''
# myapp/migrations/0015_audit_log_table.py
#
# Use RunSQL for: partitioned tables, triggers, stored procedures, VIEWs,
# materialized views — anything the Django ORM cannot express.

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("myapp", "0014_previous")]

    operations = [
        migrations.RunSQL(
            sql=[
                """
                CREATE TABLE IF NOT EXISTS myapp_audit_log (
                    id          BIGSERIAL PRIMARY KEY,
                    table_name  TEXT        NOT NULL,
                    row_id      BIGINT      NOT NULL,
                    action      TEXT        NOT NULL,
                    changed_by  BIGINT,
                    ts          TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """,
                "CREATE INDEX ix_audit_log_ts ON myapp_audit_log(ts)",
                "CREATE INDEX ix_audit_log_row ON myapp_audit_log(table_name, row_id)",
            ],
            reverse_sql=[
                "DROP TABLE IF EXISTS myapp_audit_log",
            ],
        ),
    ]
'''


# ==========================================================================
# 9. MULTI-DATABASE ROUTER
# ==========================================================================

class AnalyticsRouter:
    """
    Route models in ``analytics_app`` to the ``analytics`` database.
    All other apps use the ``default`` database.

    Register in settings::

        DATABASE_ROUTERS = ["myapp.routers.AnalyticsRouter"]
    """

    _analytics_app = "analytics_app"
    _analytics_db = "analytics"
    _default_db = "default"

    def db_for_read(self, model, **hints):
        if model._meta.app_label == self._analytics_app:
            return self._analytics_db
        return self._default_db

    def db_for_write(self, model, **hints):
        if model._meta.app_label == self._analytics_app:
            return self._analytics_db
        return self._default_db

    def allow_relation(self, obj1, obj2, **hints):
        # Cross-database foreign keys are not allowed.
        db_set = {self._analytics_db, self._default_db}
        if (
            obj1._state.db in db_set
            and obj2._state.db in db_set
        ):
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label == self._analytics_app:
            return db == self._analytics_db
        return db == self._default_db


# ==========================================================================
# 10. POSTGRES ADVISORY LOCK IN A MIGRATION
# ==========================================================================

EXAMPLE_ADVISORY_LOCK_MIGRATION = '''
# Use pg_advisory_lock to prevent two migration processes running the same
# long data migration concurrently (e.g. in a multi-pod Kubernetes rollout
# where the migration Job may be retried).

from django.db import migrations


MIGRATION_LOCK_KEY = 123_456_789  # Project-unique integer


class Migration(migrations.Migration):
    atomic = False   # Advisory locks must not be wrapped in a transaction.

    operations = [
        migrations.RunSQL(f"SELECT pg_advisory_lock({MIGRATION_LOCK_KEY})"),

        # --- your expensive operations here ---
        migrations.RunPython(lambda apps, se: None),   # placeholder

        migrations.RunSQL(f"SELECT pg_advisory_unlock({MIGRATION_LOCK_KEY})"),
    ]
'''


# ==========================================================================
# 11. BULK OPERATIONS INSIDE RunPython
# ==========================================================================

def bulk_create_example(apps, schema_editor):
    """
    Illustrates bulk_create and bulk_update inside a RunPython function.

    bulk_create and bulk_update dramatically reduce the number of database
    round-trips.  1 000 individual .save() calls issue 1 000 INSERT
    statements; bulk_create issues 1 with 1 000 rows.

    Notes
    -----
    - Signals (post_save, pre_save) are NOT fired by bulk_create /
      bulk_update.  This is usually desirable in migrations — you do not
      want side-effect code running during schema changes.
    - Avoid importing the live model (``from myapp.models import User``).
      Always use ``apps.get_model()``.
    """
    User = apps.get_model("auth", "User")

    # Bulk-create example (illustrative — no real rows created here).
    new_users = [
        User(username=f"seed_user_{i}", email=f"seed_{i}@example.com")
        for i in range(100)
    ]
    User.objects.bulk_create(new_users, batch_size=500, ignore_conflicts=True)

    # Bulk-update example.
    users_to_update = list(User.objects.filter(is_active=None))
    for u in users_to_update:
        u.is_active = True
    User.objects.bulk_update(users_to_update, ["is_active"], batch_size=500)


# ==========================================================================
# 12. MIGRATION LINTING (CI gate)
# ==========================================================================

# pip install django-migration-linter

MIGRATION_LINTER_USAGE = """
# Run in CI to catch breaking changes before they reach production:
#
#   pip install django-migration-linter
#   python manage.py lintmigrations
#
# Catches:
#   - Removing a column while old code is still deployed
#   - Adding a NOT NULL column without a default (table lock)
#   - Renaming a column referenced by app code
#   - Changing column types (table rewrite)
#   - Adding a unique constraint (implicit index scan)
#
# Integrate with --include-deployment-checks for extra Postgres checks.
#
# CI snippet (GitHub Actions):
#
#   - name: Lint migrations
#     run: |
#       pip install django-migration-linter
#       python manage.py lintmigrations --no-cache
"""


# ==========================================================================
# 13. SQUASHING MIGRATIONS
# ==========================================================================

SQUASHING_GUIDE = """
Squashing reduces 100s of migration files into a single consolidated file.

When to squash
--------------
- Application has been running for >= 1 year and accumulated >= 50 migrations.
- Fresh environment setup is slow because migrations replay the entire history.
- Squash at most once per year — squashing destroys changelog history.

How to squash
-------------
  python manage.py squashmigrations myapp 0001 0050
  # Produces: myapp/migrations/0001_squashed_0050_<name>.py

Prerequisites before deleting old migrations
--------------------------------------------
1. All production environments must have applied migrations through 0050.
2. All staging / dev environments must have applied 0050.
3. The squashed migration must have been applied on every environment.

Only after these conditions are met can you delete 0001 – 0050 and keep
only the squashed file.

Pitfalls
--------
- Data migrations often cannot be squashed (RunPython state depends on
  model history).  You may need to inline or skip them manually.
- Squashing removes the dependency chain history.  Cross-app migration
  dependencies must be updated to point to the squashed migration.
"""


# ==========================================================================
# 14. FAKING MIGRATIONS
# ==========================================================================

FAKING_GUIDE = """
--fake marks a migration as applied WITHOUT running the SQL.

Legitimate uses
---------------
  # Schema already exists (manual change or restore from backup):
  python manage.py migrate myapp 0010 --fake

  # Adopting Django migrations on an existing database:
  python manage.py migrate --fake-initial

Dangers
-------
- If you fake a migration that creates a column, the column is missing.
  Application code expecting the column will error immediately.
- Never use --fake to skip a broken migration.  Fix the migration instead.
- After faking, always run showmigrations to verify the expected state.

Diagnosis commands
------------------
  python manage.py showmigrations          # list all migrations + applied status
  python manage.py sqlmigrate myapp 0010  # show SQL for a specific migration
  python manage.py migrate --plan          # print execution order without running
"""


# ==========================================================================
# 15. MIGRATION TESTING PATTERNS
# ==========================================================================

MIGRATION_TEST_PATTERNS = """
# 1. Smoke test — ensure all migrations apply cleanly on a fresh database:
#
#    from django.core.management import call_command
#
#    def test_migrations_apply():
#        call_command("migrate", verbosity=0)
#        # If this does not raise, all migrations applied successfully.


# 2. Rollback test — verify a migration is reversible:
#
#    def test_migration_rollback():
#        call_command("migrate", "myapp", "0020", verbosity=0)
#        call_command("migrate", "myapp", "0019", verbosity=0)
#        # Assert the schema is back to the pre-0020 state.


# 3. State test — assert specific tables / columns exist after migration:
#
#    from django.db import connection
#
#    def test_phone_column_exists():
#        call_command("migrate", verbosity=0)
#        with connection.cursor() as cursor:
#            cursor.execute(
#                "SELECT column_name FROM information_schema.columns "
#                "WHERE table_name = 'myapp_user' AND column_name = 'phone'"
#            )
#            assert cursor.fetchone() is not None, "phone column missing"


# 4. Lint in CI (see section 12 above):
#
#    python manage.py lintmigrations --no-cache
"""


# ==========================================================================
# 16. PRODUCTION DEPLOYMENT STRATEGIES
# ==========================================================================

DEPLOYMENT_STRATEGIES = """
Strategy 1 — Run migrations on deploy (simple, higher risk)
------------------------------------------------------------
  # deployment_script.sh
  python manage.py migrate
  gunicorn myapp.wsgi:application --workers 4

Risk: a long migration blocks the deploy pipeline.  Rolling restarts may
start new pods before the schema is ready.

Strategy 2 — Separate migration Job (recommended for Kubernetes)
----------------------------------------------------------------
  # k8s/migration-job.yaml (abbreviated)
  apiVersion: batch/v1
  kind: Job
  metadata:
    name: migrate-{{ build_id }}
  spec:
    template:
      spec:
        restartPolicy: Never
        containers:
        - name: migrate
          image: myapp:{{ build_id }}
          command: ["python", "manage.py", "migrate", "--no-input"]

Run the Job BEFORE rolling out new Deployment pods.  If the Job fails,
the rollout does not proceed and the old code continues serving traffic.

Strategy 3 — Per-tenant migrations (SaaS / schema-per-tenant)
--------------------------------------------------------------
  def migrate_all_tenants():
      for tenant in Tenant.objects.all():
          with schema_context(tenant.schema_name):   # django-tenants
              call_command("migrate", tenant=False, verbosity=0)
"""


# ==========================================================================
# 17. INSPECTION CHEAT-SHEET
# ==========================================================================

INSPECTION_COMMANDS = """
# List all migrations and their applied status:
python manage.py showmigrations

# Show the SQL that a migration will execute (dry run):
python manage.py sqlmigrate myapp 0010

# Show the planned migration order without executing:
python manage.py migrate --plan

# Dry run makemigrations (CI check — exit 1 if migrations are missing):
python manage.py makemigrations --check --dry-run

# Apply migrations to a named database:
python manage.py migrate --database=analytics
"""


# ==========================================================================
# 18. COMMON PITFALLS QUICK REFERENCE
# ==========================================================================

COMMON_PITFALLS = {
    "Using live model in RunPython": (
        "Never `from myapp.models import User` inside RunPython.  "
        "Always use `apps.get_model('myapp', 'User')` to get the historical model."
    ),
    "AlterField with type change": (
        "ALTER COLUMN TYPE rewrites the entire column and holds a table lock.  "
        "Use expand-contract (add new column, dual-write, backfill, switch reads, "
        "drop old) for zero-downtime type changes."
    ),
    "Adding NOT NULL without default on large table": (
        "Locks the table while Django fills every row with the default.  "
        "Use the three-step pattern: add nullable → backfill → tighten to NOT NULL."
    ),
    "Migration that imports from app code": (
        "Importing `from myapp.utils import helper` in a RunPython function "
        "breaks the migration if `helper` is later renamed or deleted.  "
        "Keep RunPython functions fully self-contained."
    ),
    "Using --fake to skip a broken migration": (
        "Faking a migration marks it applied without running the SQL.  "
        "The schema change does not happen, leading to immediate runtime errors.  "
        "Fix the migration; do not fake it."
    ),
    "Concurrent migration runs without locking": (
        "Two pods running `migrate` simultaneously can interleave operations "
        "and corrupt schema state.  Use a Kubernetes Job (not Deployment) and "
        "pg_advisory_lock for extra safety."
    ),
    "Batching too many changes in one migration": (
        "Large migrations are hard to debug and impossible to partially revert.  "
        "One logical change per migration file."
    ),
}


# ==========================================================================
# 19. DEMO — inspect the live (SQLite) database state
# ==========================================================================

def _demo_inspect_applied_migrations() -> None:
    """
    Demonstrate inspecting the django_migrations table that Django maintains
    to track which migrations have been applied.

    This works against the in-memory SQLite database configured in the module
    setup block — no external infrastructure required.
    """
    try:
        with connection.cursor() as cursor:
            # Check whether the django_migrations table has been created yet.
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='django_migrations'"
            )
            if not cursor.fetchone():
                print("  django_migrations table does not exist yet (no migrate run).")
                return

            cursor.execute(
                "SELECT app, name, applied FROM django_migrations ORDER BY applied"
            )
            rows = cursor.fetchall()

        if not rows:
            print("  No migrations have been applied.")
            return

        print(f"  {'App':<20} {'Migration':<40} Applied")
        print(f"  {'-'*20} {'-'*40} {'-'*19}")
        for app, name, applied in rows:
            print(f"  {app:<20} {name:<40} {applied}")
    except Exception as exc:
        print(f"  Could not query django_migrations: {exc}")


def _demo_batch_backfill_simulation() -> None:
    """
    Simulate the batch backfill helper without touching a real application
    model.  Uses Django's built-in auth_user table.
    """
    from django.contrib.auth.models import User as AuthUser

    # Create a small batch of test users.
    for i in range(5):
        AuthUser.objects.get_or_create(
            username=f"demo_user_{i}",
            defaults={"email": f"demo_{i}@example.com"},
        )

    total = AuthUser.objects.count()
    print(f"  Auth users in DB: {total}")
    print(
        "  In a real migration, batch_update() would process rows in "
        "chunks to avoid long-held locks."
    )


def _demo_common_pitfalls() -> None:
    print("\n  Common Migration Pitfalls:")
    for idx, (pitfall, explanation) in enumerate(COMMON_PITFALLS.items(), start=1):
        print(f"\n  [{idx}] {pitfall}")
        # Wrap explanation at 72 chars for readability.
        words = explanation.split()
        line = "      "
        for word in words:
            if len(line) + len(word) + 1 > 76:
                print(line)
                line = "      " + word
            else:
                line = line + (" " if line.strip() else "") + word
        if line.strip():
            print(line)


def _demo_analytics_router() -> None:
    """Demonstrate the AnalyticsRouter logic without a real second database."""
    router = AnalyticsRouter()

    class FakeState:
        def __init__(self, db):
            self.db = db

    class FakeMeta:
        def __init__(self, label):
            self.app_label = label

    class FakeModel:
        def __init__(self, label, db):
            self._meta = FakeMeta(label)
            self._state = FakeState(db)

    analytics_model = FakeModel("analytics_app", "analytics")
    default_model = FakeModel("myapp", "default")

    print(
        f"  analytics_app → db_for_read: "
        f"{router.db_for_read(analytics_model)}"
    )
    print(
        f"  myapp         → db_for_read: "
        f"{router.db_for_read(default_model)}"
    )
    print(
        f"  allow_migrate('analytics', 'analytics_app'): "
        f"{router.allow_migrate('analytics', 'analytics_app')}"
    )
    print(
        f"  allow_migrate('default', 'analytics_app'):   "
        f"{router.allow_migrate('default', 'analytics_app')}"
    )


# ==========================================================================
# 20. __main__ ENTRY POINT
# ==========================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    print("=" * 70)
    print("Django Migrations in Production — Demonstration")
    print("=" * 70)

    # --- Run Django migrations so the schema tables exist ---
    from django.core.management import call_command

    print("\n[1] Applying built-in Django migrations (in-memory SQLite) ...")
    buf = StringIO()
    call_command("migrate", "--run-syncdb", verbosity=1, stdout=buf)
    print(buf.getvalue().strip() or "  (no output)")

    print("\n[2] Inspecting django_migrations table ...")
    _demo_inspect_applied_migrations()

    print("\n[3] Batch backfill simulation ...")
    _demo_batch_backfill_simulation()

    print("\n[4] Analytics database router demonstration ...")
    _demo_analytics_router()

    _demo_common_pitfalls()

    print("\n[5] Key patterns reference (see module-level constants):")
    for name in [
        "THREE_STEP_NOT_NULL",
        "RENAME_FIELD_SAFE_STEPS",
        "SQUASHING_GUIDE",
        "FAKING_GUIDE",
        "DEPLOYMENT_STRATEGIES",
        "INSPECTION_COMMANDS",
    ]:
        print(f"  - {name}")

    print("\n[6] CI / production commands:")
    print("  python manage.py makemigrations --check --dry-run")
    print("  python manage.py lintmigrations --no-cache  # requires django-migration-linter")
    print("  python manage.py migrate --plan")
    print("  python manage.py showmigrations")

    print("\nDone. All patterns are importable from this module.")
    print("=" * 70)
