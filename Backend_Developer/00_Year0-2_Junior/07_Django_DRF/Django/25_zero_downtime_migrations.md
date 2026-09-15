# Zero-Downtime Migrations — Production Schema Changes

## Why It Matters (Senior 5 YOE Context)

Migrations on huge tables in prod = potential outage. Senior must know:
- **Expand-contract pattern** → backward-compatible changes
- **Locking implications** → ALTER TABLE locks
- **Long-running migrations** → batched RunPython
- **Faking, squashing** → migration management
- **Multi-app dependencies** → migration order

Interview: "Add NOT NULL column to 100M row table without downtime?" → expand-contract + backfill + contract.

---

## Core Concepts

### Migration Lifecycle

```
makemigrations → creates 0001_initial.py
migrate → applies to DB

# History stored in django_migrations table:
SELECT * FROM django_migrations;
```

### Migration Operations

```python
# myapp/migrations/0042_add_field.py
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('myapp', '0041_previous')]

    operations = [
        migrations.AddField(
            model_name='order',
            name='discount',
            field=models.DecimalField(default=0, max_digits=5, decimal_places=2),
        ),
    ]
```

### `atomic = False` for Long Migrations

```python
class Migration(migrations.Migration):
    atomic = False   # don't wrap entire migration in transaction

    operations = [...]
```

Required when:
- Long-running RunPython
- PostgreSQL CONCURRENTLY index creation
- Multiple DML changes that shouldn't all rollback together

### Expand-Contract Pattern (Backward Compatible)

**Step 1 — Expand:** Add new column (nullable) + dual-write in code

```python
# Migration: add column nullable
migrations.AddField(
    model_name='user',
    name='email_verified_at',
    field=models.DateTimeField(null=True, blank=True),
)
```

```python
# App code: write to both old + new
user.is_email_verified = True              # old field
user.email_verified_at = timezone.now()    # new field
```

**Step 2 — Backfill** (background task):

```python
# Mgmt command — chunked
from django.core.management.base import BaseCommand
from django.db.models import F


class Command(BaseCommand):
    def handle(self, *args, **options):
        batch_size = 1000
        qs = User.objects.filter(
            is_email_verified=True,
            email_verified_at__isnull=True,
        ).order_by('pk')

        last_pk = 0
        while True:
            batch = list(qs.filter(pk__gt=last_pk).values_list('pk', flat=True)[:batch_size])
            if not batch:
                break
            User.objects.filter(pk__in=batch).update(
                email_verified_at=F('updated_at'),
            )
            last_pk = batch[-1]
            self.stdout.write(f'Updated up to {last_pk}')
```

**Step 3 — Read from new:** App code reads new column

**Step 4 — Contract:** Make new NOT NULL, remove old field

```python
# Migration 1: make NOT NULL
migrations.AlterField(
    model_name='user',
    name='email_verified_at',
    field=models.DateTimeField(),   # null=False
)


# Migration 2: remove old
migrations.RemoveField(
    model_name='user',
    name='is_email_verified',
)
```

Deploy each step separately, verify in between.

### Adding NOT NULL Column Safely

```python
# WRONG — locks table to backfill
migrations.AddField(
    model_name='user',
    name='status',
    field=models.CharField(max_length=20, default='active'),  # requires rewrite
)


# RIGHT — multi-step
# Step 1: add nullable + default
migrations.AddField(
    model_name='user',
    name='status',
    field=models.CharField(max_length=20, null=True),
)

# Step 2: backfill (RunPython)
def backfill(apps, schema_editor):
    User = apps.get_model('myapp', 'User')
    # Chunked
    while User.objects.filter(status__isnull=True).exists():
        ids = User.objects.filter(status__isnull=True).values_list('pk', flat=True)[:1000]
        User.objects.filter(pk__in=list(ids)).update(status='active')

migrations.RunPython(backfill, migrations.RunPython.noop)

# Step 3: NOT NULL (separate migration)
migrations.AlterField(
    model_name='user',
    name='status',
    field=models.CharField(max_length=20, default='active'),
)
```

### PostgreSQL `ALTER TABLE` Locking

Operations that take **AccessExclusiveLock** (block reads + writes):
- ADD CONSTRAINT (NOT NULL, FK, CHECK without NOT VALID)
- ALTER COLUMN TYPE (with rewrite)
- ADD COLUMN with non-NULL default (< PG 11 always; PG 11+ for constant default is fast)

Operations that are fast (metadata only):
- ADD COLUMN (nullable, no default)
- ADD COLUMN with constant default (PG 11+)
- DROP COLUMN (metadata, real cleanup later)

### Adding Index Concurrently

```python
class Migration(migrations.Migration):
    atomic = False   # required for CONCURRENTLY

    operations = [
        migrations.RunSQL(
            sql="CREATE INDEX CONCURRENTLY idx_orders_status ON orders (status);",
            reverse_sql="DROP INDEX CONCURRENTLY idx_orders_status;",
        ),
    ]


# Or via AddIndex with separate database operation
migrations.SeparateDatabaseAndState(
    state_operations=[
        migrations.AddIndex(model_name='order', index=models.Index(fields=['status'])),
    ],
    database_operations=[
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY ...",
            reverse_sql="DROP INDEX CONCURRENTLY ...",
        ),
    ],
)
```

### Faking Migrations

```bash
# Mark migration as applied without running SQL (when DB already has the schema)
python manage.py migrate myapp 0042 --fake

# Fake initial (when adopting Django on existing DB)
python manage.py migrate --fake-initial
```

### Squashing Migrations

After many migrations, squash for cleaner history:

```bash
python manage.py squashmigrations myapp 0001 0042
# Creates 0001_squashed_0042.py replacing all migrations in range
```

Old files can be deleted later (after all servers migrated).

### Multi-Database Migrations

```python
class Migration(migrations.Migration):
    dependencies = [...]
    operations = [...]


# DATABASE_ROUTERS.allow_migrate determines which DB runs each migration
# Or explicit:
python manage.py migrate --database=replica1
```

### Reverse Migrations

```bash
# Roll back to specific migration
python manage.py migrate myapp 0040
```

Each migration has reverse operation (auto for most, manual for RunPython).

### Migration Testing

```python
from django.test import TestCase
from django.db.migrations.executor import MigrationExecutor
from django.db import connection


class MigrationTest(TestCase):
    @property
    def app(self):
        return 'myapp'

    migrate_from = '0041_previous'
    migrate_to = '0042_add_field'

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate([(self.app, self.migrate_from)])
        # ... setup data with old model

        old_apps = executor.loader.project_state([(self.app, self.migrate_from)]).apps
        OldUser = old_apps.get_model(self.app, 'User')
        OldUser.objects.create(...)

        # Migrate forward
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate([(self.app, self.migrate_to)])

    def test_data_migrated(self):
        # Verify after migration
        ...
```

### Common ALTER Patterns

```python
# Add NOT NULL with default — single migration (PG 11+ fast)
migrations.AddField(model_name='X', name='Y', field=models.IntegerField(default=0))


# Rename column (Django supports with state-aware rename)
migrations.RenameField(model_name='X', old_name='old', new_name='new')
# Note: app must support both names during deploy (use property if needed)


# Change column type
# Risk: TYPE change rewrites table → use SeparateDatabaseAndState + manual SQL
migrations.SeparateDatabaseAndState(
    state_operations=[migrations.AlterField(...)],
    database_operations=[migrations.RunSQL("ALTER TABLE X ALTER COLUMN Y TYPE ...")],
)


# Drop column safely
# Step 1: stop reading/writing in code
# Step 2: migration to drop
migrations.RemoveField(model_name='X', name='Y')
```

---

## Common Pitfalls

### 1. Migration with Default on Huge Table

```python
migrations.AddField(field=models.CharField(default='active'))
```

PG < 11: rewrites entire table. Use nullable + backfill + alter.

### 2. NOT NULL Without Backfill

```python
migrations.AddField(field=models.IntegerField(null=False, default=0))
```

Locks table during rewrite. Multi-step expand-contract.

### 3. Index Creation Without CONCURRENTLY

```python
migrations.AddIndex(...)   # locks table
```

Use RunSQL with CONCURRENTLY for prod indexes.

### 4. RunPython in Atomic Migration

```python
class Migration(migrations.Migration):
    # atomic = True (default)
    operations = [
        migrations.RunPython(big_data_migration),  # 1 hour → lock everything
    ]
```

Set `atomic = False` for long-running RunPython.

### 5. Forgetting Reverse Operation

```python
migrations.RunPython(forward_func)  # no reverse → can't unmigrate
```

Provide `reverse_func` or `migrations.RunPython.noop`.

### 6. Schema-Aware vs Data-Aware

```python
# WRONG — uses current Django model (may be post-migration shape)
from myapp.models import User
User.objects.all().update(status='active')

# RIGHT — historical model
def forward(apps, schema_editor):
    User = apps.get_model('myapp', 'User')
    User.objects.all().update(status='active')

migrations.RunPython(forward)
```

### 7. Foreign Key Cascade Migrations

```python
# Removing FK doesn't delete dependent table by default
migrations.RemoveField(model_name='Order', name='customer')
# Order rows remain; customer_id column dropped
```

Be careful with on_delete behavior changes.

---

## Interview Q&A

**Q1:** 100M row table mein NOT NULL column kaise add karoge?
**A:** Expand-contract pattern: (1) Migration to add column nullable. (2) Deploy app that writes to both old + new. (3) Background mgmt command chunks backfill (1000 rows × N batches with sleep between). (4) Verify backfill complete. (5) Migration to set NOT NULL + remove old column. Each step deployable independently.

**Q2:** Migration ne table lock kar diya — debug?
**A:** Check `pg_locks` for AccessExclusiveLock. Common causes: ALTER COLUMN TYPE, ADD COLUMN with non-constant default (< PG 11), CREATE INDEX without CONCURRENTLY, ADD FK without NOT VALID. Cancel migration, plan multi-step rollout.

**Q3:** CONCURRENTLY index Django mein?
**A:** Use `RunSQL` with `atomic = False`. Set `state_operations` + `database_operations` via `SeparateDatabaseAndState` so Django's state stays correct. Or simpler: just RunSQL with reverse_sql.

**Q4:** Squash migrations kab karte ho?
**A:** Long projects accumulate 100s of migrations → slow Django startup, hard to read. Squash periodically (e.g., after major releases). `squashmigrations` combines into one. Old files stay until all envs migrated, then delete.

**Q5:** Migration test kaise karte ho?
**A:** `MigrationExecutor` to apply migrations programmatically up to point N, set up data with historical model, apply next migration, verify outcome. Critical for data migrations (RunPython) — ensures transformation correct.

**Q6:** Faking migrations zaroori kab?
**A:** (1) Adopting Django on existing DB — `--fake-initial`. (2) Manually applied schema change matches migration → `--fake` that migration. (3) Recovery from broken migration state. Risky — DB state must EXACTLY match.

**Q7:** Multi-app dependencies migrations mein?
**A:** `dependencies = [('app1', '0042'), ('app2', '0010')]` in Migration class. Django builds DAG, applies in order. For circular: refactor to avoid. For data dependencies (need users created before products), use RunPython with apps.get_model.

**Q8:** Migration revert kaise karoge production mein?
**A:** `python manage.py migrate myapp 0041` rolls back to 0041 (un-applies 0042+). Risk: reverse_sql may not exist or data-loss. Always test reverse in staging. Most prod issues: forward + new fix migration, not reverse.

---

## Real-World Use Cases

### 1. Rename Table (Online)

```python
# Multi-step:
# Step 1: copy data via trigger (PG-specific)
# Step 2: switch app to new table
# Step 3: drop old


# Simpler if downtime OK: AlterModelTable
migrations.AlterModelTable(name='OldName', table='new_name')
```

### 2. Migrate to Larger Column Type

```python
# Change VARCHAR(50) → VARCHAR(200) — fast in PG
migrations.AlterField(field=models.CharField(max_length=200))


# Change INT → BIGINT — slow, rewrites
# Use ALTER COLUMN TYPE with USING clause
```

### 3. Data Migration with Validation

```python
def forward(apps, schema_editor):
    User = apps.get_model('myapp', 'User')
    errors = []
    for user in User.objects.iterator(chunk_size=1000):
        try:
            user.normalized_email = user.email.lower().strip()
            user.save(update_fields=['normalized_email'])
        except Exception as e:
            errors.append((user.pk, str(e)))
    if errors:
        # Log + decide: continue or abort?
        ...
```

---

## References

- [Django Migrations](https://docs.djangoproject.com/en/5.0/topics/migrations/)
- [Django Migration Operations](https://docs.djangoproject.com/en/5.0/ref/migration-operations/)
- "Postgres Zero Downtime Migrations" — Braintree blog
- `django-pg-zero-downtime-migrations` package
