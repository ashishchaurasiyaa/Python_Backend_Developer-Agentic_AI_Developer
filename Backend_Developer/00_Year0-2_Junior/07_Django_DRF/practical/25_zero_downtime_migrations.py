"""
Zero-Downtime Migrations — Production Patterns
"""

# ==========================================================================
# 1. ADD COLUMN — Safe Pattern (Expand-Contract)
# ==========================================================================

# Step 1 migration: add nullable column
"""
# 0042_add_email_verified_at.py
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('myapp', '0041_previous')]

    operations = [
        migrations.AddField(
            model_name='user',
            name='email_verified_at',
            field=models.DateTimeField(null=True, blank=True),
        ),
    ]
"""


# Step 2 migration: backfill via mgmt command (separate deploy)
"""
# ops/management/commands/backfill_email_verified_at.py
from django.core.management.base import BaseCommand
from django.db.models import F
import time


class Command(BaseCommand):
    help = "Backfill email_verified_at from is_email_verified + updated_at"

    def add_arguments(self, parser):
        parser.add_argument('--batch-size', type=int, default=1000)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        from users.models import User

        batch_size = options['batch_size']
        dry_run = options['dry_run']

        last_pk = 0
        while True:
            ids = list(
                User.objects
                .filter(is_email_verified=True, email_verified_at__isnull=True, pk__gt=last_pk)
                .order_by('pk')
                .values_list('pk', flat=True)[:batch_size]
            )
            if not ids:
                break

            if not dry_run:
                updated = User.objects.filter(pk__in=ids).update(
                    email_verified_at=F('updated_at'),
                )
                self.stdout.write(f'Updated {updated} (up to pk={ids[-1]})')
            else:
                self.stdout.write(f'Would update {len(ids)} (up to pk={ids[-1]})')

            last_pk = ids[-1]
            time.sleep(0.1)   # rate limit to reduce DB load
"""


# Step 3 migration: make NOT NULL + remove old field
"""
# 0044_finalize_email_verified.py
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('myapp', '0043_backfill_done')]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='email_verified_at',
            field=models.DateTimeField(),   # null=False now
        ),
        migrations.RemoveField(
            model_name='user',
            name='is_email_verified',
        ),
    ]
"""


# ==========================================================================
# 2. RUNPYTHON WITH HISTORICAL MODELS
# ==========================================================================

"""
# 0050_normalize_emails.py
from django.db import migrations


def normalize_emails(apps, schema_editor):
    User = apps.get_model('users', 'User')   # HISTORICAL model
    for user in User.objects.iterator(chunk_size=1000):
        original = user.email
        normalized = original.lower().strip()
        if original != normalized:
            user.email = normalized
            user.save(update_fields=['email'])


def reverse(apps, schema_editor):
    # Document why no reverse possible
    pass


class Migration(migrations.Migration):
    atomic = False   # long-running

    dependencies = [('users', '0049_previous')]

    operations = [
        migrations.RunPython(normalize_emails, reverse),
    ]
"""


# ==========================================================================
# 3. CONCURRENT INDEX CREATION (PostgreSQL)
# ==========================================================================

"""
# 0060_add_index_concurrently.py
from django.db import migrations


class Migration(migrations.Migration):
    atomic = False   # CONCURRENTLY incompatible with transaction

    dependencies = [('orders', '0059_previous')]

    operations = [
        # Use SeparateDatabaseAndState so Django state stays correct
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddIndex(
                    model_name='order',
                    index=migrations.management.AddIndex.deconstruct_index(...)
                    # Actually use models.Index:
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql='CREATE INDEX CONCURRENTLY orders_status_idx ON orders (status);',
                    reverse_sql='DROP INDEX CONCURRENTLY orders_status_idx;',
                ),
            ],
        ),
    ]


# Simpler — just RunSQL (Django state slightly out of sync but fine for indexes)
class Migration(migrations.Migration):
    atomic = False

    operations = [
        migrations.RunSQL(
            'CREATE INDEX CONCURRENTLY orders_status_created_idx ON orders (status, created_at DESC);',
            reverse_sql='DROP INDEX CONCURRENTLY orders_status_created_idx;',
        ),
    ]
"""


# ==========================================================================
# 4. CHUNKED DATA MIGRATION (PROD-SAFE)
# ==========================================================================

"""
# 0070_backfill_chunked.py
import time
from django.db import migrations


def backfill(apps, schema_editor):
    Order = apps.get_model('orders', 'Order')
    batch_size = 1000
    last_pk = 0

    while True:
        ids = list(
            Order.objects
            .filter(slug='', pk__gt=last_pk)
            .order_by('pk')
            .values_list('pk', flat=True)[:batch_size]
        )
        if not ids:
            break

        batch = Order.objects.filter(pk__in=ids)
        for order in batch:
            order.slug = order.compute_slug()

        # Bulk update is faster
        Order.objects.bulk_update(list(batch), ['slug'])
        last_pk = ids[-1]

        # Reduce load
        time.sleep(0.05)


class Migration(migrations.Migration):
    atomic = False
    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
"""


# ==========================================================================
# 5. ADD FK SAFELY (avoid AccessExclusiveLock)
# ==========================================================================

"""
# Adding FK with constraint blocks reads + writes briefly
# Safer two-step:

# Step 1: Add column without constraint
class Migration(migrations.Migration):
    operations = [
        migrations.RunSQL(
            'ALTER TABLE orders ADD COLUMN customer_id INTEGER NULL;',
            reverse_sql='ALTER TABLE orders DROP COLUMN customer_id;',
        ),
    ]

# Step 2: Add constraint as NOT VALID (fast, no lock for validation)
class Migration(migrations.Migration):
    atomic = False
    operations = [
        migrations.RunSQL(
            '''ALTER TABLE orders
               ADD CONSTRAINT orders_customer_id_fk FOREIGN KEY (customer_id)
               REFERENCES customers(id) NOT VALID;''',
            reverse_sql='ALTER TABLE orders DROP CONSTRAINT orders_customer_id_fk;',
        ),
    ]

# Step 3: Validate constraint in background (no lock)
class Migration(migrations.Migration):
    atomic = False
    operations = [
        migrations.RunSQL(
            'ALTER TABLE orders VALIDATE CONSTRAINT orders_customer_id_fk;',
            reverse_sql='',  # no reverse needed
        ),
    ]

# Step 4: Sync Django state — pretend FK was added normally
class Migration(migrations.Migration):
    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='order',
                    name='customer',
                    field=models.ForeignKey('customers.Customer', on_delete=models.CASCADE),
                ),
            ],
            database_operations=[],  # already done
        ),
    ]
"""


# ==========================================================================
# 6. RENAME FIELD ZERO-DOWNTIME
# ==========================================================================

"""
# Step 1: Add new field
migrations.AddField(model_name='user', name='full_name', field=models.CharField(max_length=200, null=True))


# Step 2: Backfill in mgmt command — copy old to new
User.objects.update(full_name=F('name'))


# Step 3: Code writes to both
def save(self, *args, **kwargs):
    self.full_name = self.full_name or self.name
    super().save(*args, **kwargs)


# Step 4: Make new NOT NULL
migrations.AlterField(model_name='user', name='full_name', field=models.CharField(max_length=200))


# Step 5: App reads from new only


# Step 6: Drop old
migrations.RemoveField(model_name='user', name='name')


# (Faster alternative if you can tolerate brief lock):
migrations.RenameField(model_name='user', old_name='name', new_name='full_name')
# Caveat: app must handle BOTH names during deploy window
"""


# ==========================================================================
# 7. SQUASH MIGRATIONS
# ==========================================================================

SQUASH_GUIDE = """
# Combine 0001..0042 into 0001_squashed_0042.py
python manage.py squashmigrations myapp 0001 0042

# Review generated file
# Note: 'replaces = [...]' field tracks original migrations

# Deploy
# - On each env, after migrating to 0042+ at least once, can safely delete old files
# - Django auto-detects squashed migration replacing originals

# After ALL envs at squashed migration, remove `replaces` list + delete old files
# Generated will become standalone 0001 migration
"""


# ==========================================================================
# 8. MIGRATION TESTING
# ==========================================================================

"""
# tests/test_migrations.py

from django.test import TestCase
from django.db.migrations.executor import MigrationExecutor
from django.db import connection


class TestEmailNormalizationMigration(TestCase):
    app = 'users'
    migrate_from = '0049_previous'
    migrate_to = '0050_normalize_emails'

    def setUp(self):
        executor = MigrationExecutor(connection)

        # Migrate to before-state
        executor.migrate([(self.app, self.migrate_from)])

        # Create test data with old shape
        old_apps = executor.loader.project_state([(self.app, self.migrate_from)]).apps
        OldUser = old_apps.get_model(self.app, 'User')
        self.user1 = OldUser.objects.create(email='Alice@Example.com  ')
        self.user2 = OldUser.objects.create(email='bob@Example.com')

        # Apply migration
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate([(self.app, self.migrate_to)])

    def test_emails_normalized(self):
        new_apps = MigrationExecutor(connection).loader.project_state(
            [(self.app, self.migrate_to)]
        ).apps
        User = new_apps.get_model(self.app, 'User')

        u1 = User.objects.get(pk=self.user1.pk)
        u2 = User.objects.get(pk=self.user2.pk)

        self.assertEqual(u1.email, 'alice@example.com')
        self.assertEqual(u2.email, 'bob@example.com')
"""


# ==========================================================================
# 9. FAKE MIGRATIONS
# ==========================================================================

FAKE_COMMANDS = """
# Adopting Django on existing DB
python manage.py migrate --fake-initial

# Specific app/migration faked (when DB schema already matches)
python manage.py migrate myapp 0042 --fake

# Mark as unapplied (rare — manual recovery)
python manage.py migrate myapp 0041 --fake

# Show migration state
python manage.py showmigrations
python manage.py showmigrations --plan
"""


# ==========================================================================
# 10. PROD MIGRATION CHECKLIST
# ==========================================================================

PROD_CHECKLIST = """
Before applying migration to prod:

[ ] Tested on staging with prod-like data size
[ ] Measured ALTER TABLE lock duration on similar table
[ ] No ALTER COLUMN TYPE that rewrites table (use new column + backfill)
[ ] CREATE INDEX uses CONCURRENTLY (atomic = False)
[ ] NOT NULL changes are multi-step (add nullable + backfill + alter)
[ ] RunPython has reverse_func or noop
[ ] RunPython uses historical models (apps.get_model)
[ ] RunPython chunked (1000 rows × sleep) for huge tables
[ ] atomic = False if migration > 30s
[ ] No FK constraint added with VALIDATE in single step on large table
[ ] Tested rollback path (migrate to previous)
[ ] Deploy plan with rollback documented
[ ] Monitor disk space (column adds may require temp space)
[ ] Off-hours deployment for risky migrations
[ ] Lock_timeout set: SET lock_timeout = '30s' (avoid hanging)
"""


# ==========================================================================
# 11. LOCK TIMEOUT IN MIGRATIONS
# ==========================================================================

"""
# Prevent migration from hanging on lock — fail fast instead
class Migration(migrations.Migration):
    operations = [
        migrations.RunSQL("SET lock_timeout = '30s'"),
        migrations.AlterField(...),
        migrations.RunSQL("RESET lock_timeout"),
    ]


# Or globally in settings:
DATABASES = {
    'default': {
        'OPTIONS': {
            'options': '-c lock_timeout=30000',  # 30s for all statements
        },
    },
}
"""
