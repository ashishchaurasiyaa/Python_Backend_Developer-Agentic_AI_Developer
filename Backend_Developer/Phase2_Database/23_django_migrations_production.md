# 23 — Django Migrations in Production

> Django's migrations framework is excellent — but defaults bite at scale. Production patterns matter.

---

## Refresher

```bash
python manage.py makemigrations
python manage.py migrate
```

Auto-generated files in `app/migrations/`.

```python
# 0002_add_field.py
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("myapp", "0001_initial")]
    operations = [
        migrations.AddField(
            model_name="user",
            name="phone",
            field=models.CharField(max_length=20, blank=True),
        ),
    ]
```

---

## Auto-Detection Limits

Django detects most schema changes, but:
- Doesn't see renames (drop + add). Use `--name` interactively when prompted.
- Some custom field changes invisible.
- Choices changes invisible (just regenerates field).

Always run `makemigrations --check --dry-run` in CI.

---

## Migration Best Practices

### 1. Small migrations
Don't batch many changes into one migration. Harder to debug, harder to revert.

### 2. Separate schema and data migrations
```python
# 0010_add_full_name.py — schema only
operations = [
    migrations.AddField(model_name="user", name="full_name", field=...),
]

# 0011_populate_full_name.py — data only
def forwards(apps, schema_editor):
    User = apps.get_model("myapp", "User")
    for u in User.objects.all():
        u.full_name = f"{u.first_name} {u.last_name}"
        u.save()

operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
```

Why separate: schema migrations can run zero-downtime; data migrations may take hours.

### 3. Use `apps.get_model()` in RunPython
```python
def forwards(apps, schema_editor):
    User = apps.get_model("myapp", "User")  # historical model
```

Don't import `from myapp.models import User`. That uses current model definition; breaks if model changes later.

---

## Reversible Migrations

```python
def forwards(apps, schema_editor):
    User = apps.get_model("myapp", "User")
    User.objects.filter(role="user").update(role="member")

def backwards(apps, schema_editor):
    User = apps.get_model("myapp", "User")
    User.objects.filter(role="member").update(role="user")

operations = [migrations.RunPython(forwards, backwards)]
```

Use `migrations.RunPython.noop` if no-op is OK.

---

## Atomicity

By default, each migration runs in a transaction. To split:

```python
class Migration(migrations.Migration):
    atomic = False
    operations = [...]
```

Useful for:
- CREATE INDEX CONCURRENTLY (Postgres).
- Adding ENUM values.
- Multiple large data updates.

---

## CONCURRENTLY Indexes (Postgres)

Default Django: locks the table.

```python
from django.contrib.postgres.operations import AddIndexConcurrently
from django.db.models.indexes import Index

class Migration(migrations.Migration):
    atomic = False

    operations = [
        AddIndexConcurrently(
            model_name="user",
            index=Index(fields=["email"], name="user_email_idx"),
        ),
    ]
```

Or raw SQL:
```python
operations = [
    migrations.RunSQL(
        "CREATE INDEX CONCURRENTLY ix_users_email ON users(email)",
        reverse_sql="DROP INDEX CONCURRENTLY ix_users_email",
    ),
]
```

---

## Adding NOT NULL Column to Large Table

```python
# BAD: requires lock + scan + write default value
models.CharField(max_length=20, null=False, default="")

# Better: three steps
# Step 1: add nullable
operations = [
    migrations.AddField(
        model_name="user", name="phone",
        field=models.CharField(max_length=20, null=True),
    ),
]

# Step 2: backfill with batch updates
def backfill(apps, schema_editor):
    User = apps.get_model("myapp", "User")
    batch_size = 1000
    while User.objects.filter(phone__isnull=True).exists():
        ids = User.objects.filter(phone__isnull=True).values_list("id", flat=True)[:batch_size]
        User.objects.filter(id__in=ids).update(phone="")

operations = [migrations.RunPython(backfill)]

# Step 3: change to NOT NULL
operations = [
    migrations.AlterField(
        model_name="user", name="phone",
        field=models.CharField(max_length=20, null=False, default=""),
    ),
]
```

Three deploys vs one. Safer at scale.

---

## Renaming Fields

Django detects ambiguously. Use `makemigrations` interactively or write manually:

```python
operations = [
    migrations.RenameField(
        model_name="user",
        old_name="email_addr",
        new_name="email",
    ),
]
```

But: while migration runs and old code reads `email_addr` → AttributeError.

For zero-downtime: expand-contract pattern (file 24).

---

## Custom SQL Migration

```python
from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [("myapp", "0010")]

    operations = [
        migrations.RunSQL(
            sql=[
                "CREATE TABLE IF NOT EXISTS audit_log (...)",
                "CREATE INDEX ix_audit_log_ts ON audit_log(ts)",
            ],
            reverse_sql=[
                "DROP TABLE audit_log",
            ],
        ),
    ]
```

For things Django ORM doesn't support: stored procedures, triggers, partitions.

---

## Multi-Database Migrations

```python
# settings.py
DATABASES = {
    "default": {...},
    "analytics": {...},
}

DATABASE_ROUTERS = ["myapp.routers.AnalyticsRouter"]
```

Run for specific DB:
```bash
python manage.py migrate --database=analytics
```

Models routed via `allow_migrate`:
```python
class AnalyticsRouter:
    def allow_migrate(self, db, app_label, **hints):
        if app_label == "analytics_app":
            return db == "analytics"
        return db == "default"
```

---

## Squashing Migrations

Old project = 100s of migrations → slow to apply.

```bash
python manage.py squashmigrations myapp 0001 0050
```

Generates `0001_squashed_0050.py` combining them. Apply on fresh installs.

After all environments past 0050, delete old migrations.

---

## Squashing Pitfalls

- Squashing destroys history of how schema evolved.
- Production must be at >= 0050 before squashed migration is safe.
- Data migrations can't always be squashed.

Generally: squash once per year max.

---

## Faking Migrations

If schema already exists (manual changes):
```bash
python manage.py migrate myapp 0010 --fake
```

Marks migration as applied without running. Use carefully.

```bash
python manage.py migrate --fake-initial
```

Useful for adopting Django on existing DB.

---

## Migration Testing

### Unit test
```python
from django.test.utils import setup_test_environment
from django.core.management import call_command

def test_migrations():
    call_command("migrate", verbosity=0)
    # Assert tables/columns exist
```

### Test rollback
```python
call_command("migrate", "myapp", "0020")
# Run backwards
call_command("migrate", "myapp", "0019")
# Verify schema state
```

### django-migration-linter
Detects breaking changes in migrations:
```bash
pip install django-migration-linter
python manage.py lintmigrations
```

Catches: removing column with old code still deployed, etc.

---

## Running Migrations in Production

### Approach 1: On deploy
```bash
# In deployment script
python manage.py migrate
gunicorn myapp.wsgi
```

Risk: long migration blocks deploy.

### Approach 2: Separate migration job (preferred)
```yaml
# K8s Job
apiVersion: batch/v1
kind: Job
metadata:
  name: migrate-{{ build_id }}
spec:
  template:
    spec:
      containers:
      - name: migrate
        command: ["python", "manage.py", "migrate"]
```

Run before rolling out new pods.

### Approach 3: Background worker triggers migrations
For SaaS with tenant-specific schemas, run async per tenant.

---

## Locking Migrations

`django_migrations` table; rows added per applied migration. Concurrent runs:

```python
# manage.py migrate uses advisory lock (Postgres)
# But you can add explicit lock:
from django.db import transaction

class Migration(migrations.Migration):
    operations = [
        migrations.RunSQL("SELECT pg_advisory_lock(123456)"),
        ...
        migrations.RunSQL("SELECT pg_advisory_unlock(123456)"),
    ]
```

---

## Migration Performance Tips

### Disable signals during data migration
```python
def forwards(apps, schema_editor):
    # Don't trigger post_save signals
    User = apps.get_model("myapp", "User")
    User.objects.bulk_update(users, ["field"])
```

### Use bulk_create / bulk_update
1000 individual saves = slow. Bulk = fast.

```python
User.objects.bulk_create([User(...) for _ in range(1000)], batch_size=500)
```

### Disable indexes during bulk insert
```python
operations = [
    migrations.RunSQL("DROP INDEX ix_..."),
    migrations.RunPython(insert_lots_of_data),
    migrations.RunSQL("CREATE INDEX CONCURRENTLY ix_..."),
]
```

---

## Common Pitfalls

### 1. Using current models in RunPython
Breaks when models change later. Use `apps.get_model()`.

### 2. AlterField with type change locking table
ALTER COLUMN TYPE re-writes whole column → table lock. Use expand-contract.

### 3. Adding non-null column without default
Locks table while filling.

### 4. Forgot to commit RunPython
Default is autocommit per operation. Should be fine, but explicit transactions safer.

### 5. Migration that requires app code
```python
def forwards(apps, schema_editor):
    from myapp.utils import expensive_compute   # may not exist later
```

### 6. Different migration histories across environments
Stamping inconsistencies.

### 7. `--fake` to skip a broken migration
Loses the schema change. Fix the migration, don't fake.

---

## Inspecting State

```bash
# List migrations + status
python manage.py showmigrations

# See SQL for unapplied migration
python manage.py sqlmigrate myapp 0010

# Plan migration order
python manage.py migrate --plan
```

---

## Real-World Patterns

### Pattern 1: Rename without downtime
```
v1: add new column, dual-write code (writes both)
v2: backfill old → new
v3: switch reads to new
v4: drop old column
```

### Pattern 2: Add table + populate
```
v1: schema migration adds table
v2: data migration backfills
v3: code starts using table
```

### Pattern 3: Schema-per-tenant migration
```python
def migrate_all_tenants():
    for tenant in Tenant.objects.all():
        with schema_context(tenant.schema_name):
            call_command("migrate", tenant=False)
```

---

## TL;DR

- Small migrations; one logical change each.
- Separate schema and data migrations.
- Use `apps.get_model()` in RunPython.
- CONCURRENTLY indexes; `atomic=False`.
- Add NOT NULL in 3 steps for large tables.
- Test upgrade + downgrade in CI.
- Run migrations in separate job, before code deploy.
- Lint migrations for breaking changes.
- Squash sparingly; don't fake.
