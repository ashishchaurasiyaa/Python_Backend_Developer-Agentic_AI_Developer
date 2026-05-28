# 22 — Alembic Advanced

> SQLAlchemy's migration tool. The production patterns most tutorials skip.

---

## Setup Recap

```bash
pip install alembic sqlalchemy
alembic init alembic
```

`alembic.ini` + `alembic/env.py` configured.

---

## Auto-generating Migrations

```python
# env.py
from myapp.models import Base
target_metadata = Base.metadata
```

```bash
alembic revision --autogenerate -m "add user table"
```

Alembic compares model definitions to DB → generates migration.

**Warning:** auto-generate misses:
- Server defaults vs Python defaults.
- Some constraint changes.
- ENUM modifications in Postgres.
- Renamed columns/tables (sees as drop + add).

**Always review** the generated migration.

---

## Migration File Anatomy

```python
"""add user table

Revision ID: a1b2c3d4
Revises: previous_id
Create Date: 2024-01-01 12:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4'
down_revision = 'previous_id'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

def downgrade() -> None:
    op.drop_index('ix_users_email')
    op.drop_table('users')
```

`upgrade()`: applied forward.
`downgrade()`: applied backward (rollback).

---

## Multi-Database Migrations

For schema-per-tenant or multi-DB apps:

```python
# env.py
def run_migrations_online():
    connectable = engine_from_config(...)
    with connectable.connect() as connection:
        for tenant in get_all_tenants():
            connection.execute(f'SET search_path = tenant_{tenant.id}')
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()
```

Or use Alembic branches (file 23 below).

---

## Branches & Merging

When two PRs each add a migration in parallel, you get diverging histories.

```bash
# Two devs both branched from rev abc:
# Dev A: abc → def (their migration)
# Dev B: abc → ghi (their migration)

# Now main branch has both.
alembic merge def ghi -m "merge two branches"
# Creates a merge revision joining both.
```

### Branch labels
```python
# env.py
branch_labels = "users_branch"
```

Run only one branch:
```bash
alembic upgrade users_branch@head
```

Use sparingly. Most apps shouldn't branch migrations.

---

## Data Migrations

Schema migrations modify structure; data migrations modify rows.

### Bad: ORM in migration
```python
def upgrade():
    from myapp.models import User
    for user in User.query.all():       # uses current model
        user.full_name = user.first + " " + user.last
```

Problem: if the model changes later, this migration breaks when re-run.

### Good: Raw SQL or table inspection
```python
def upgrade():
    op.execute("""
        UPDATE users SET full_name = first_name || ' ' || last_name
        WHERE full_name IS NULL
    """)
```

Or define a local table for migration:
```python
from sqlalchemy.sql import table, column

users_t = table(
    "users",
    column("id", sa.Integer),
    column("first_name", sa.String),
    column("last_name", sa.String),
    column("full_name", sa.String)
)

def upgrade():
    connection = op.get_bind()
    for row in connection.execute(users_t.select()):
        connection.execute(
            users_t.update().where(users_t.c.id == row.id).values(
                full_name=f"{row.first_name} {row.last_name}"
            )
        )
```

Migration is self-contained — survives future model changes.

---

## Large Data Migrations

For tables with millions of rows:

### Batch updates
```python
def upgrade():
    conn = op.get_bind()
    batch_size = 10000
    while True:
        result = conn.execute(text("""
            UPDATE users SET full_name = first_name || ' ' || last_name
            WHERE id IN (
                SELECT id FROM users
                WHERE full_name IS NULL
                LIMIT :n
            )
            RETURNING id
        """), {"n": batch_size})
        if result.rowcount == 0:
            break
```

### Why?
- Single huge UPDATE locks table.
- Long transaction → WAL bloat.
- If killed, no progress saved.

### Out-of-band data migration
Often, run data backfill as a separate script after schema migration:
```python
# Migration: add new column with default NULL
# Backfill script: populate it (run via worker, can resume)
# Later migration: alter column to NOT NULL
```

---

## Renaming Tables / Columns

Default autogenerate misses renames — sees as drop + add (data loss!).

### Manual:
```python
def upgrade():
    op.rename_table("user", "users")
    op.alter_column("users", "email_addr", new_column_name="email")
```

### Configure autogenerate to detect renames
```python
# env.py
context.configure(
    compare_type=True,
    compare_server_default=True,
    render_as_batch=True,    # for SQLite
)
```

But autogenerate still doesn't actually detect renames. Always edit manually.

---

## SQLite Limitations

SQLite can't `ALTER TABLE` for many things. Alembic offers batch mode:

```python
def upgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("name", new_column_name="full_name")
        batch_op.add_column(sa.Column("phone", sa.String(20)))
```

Behind the scenes: creates new table, copies data, swaps. Avoid SQLite for production.

---

## Custom Types & ENUMs

### Postgres ENUM
```python
def upgrade():
    op.execute("CREATE TYPE order_status AS ENUM ('pending', 'paid', 'cancelled')")
    op.add_column("orders", sa.Column(
        "status",
        sa.Enum("pending", "paid", "cancelled", name="order_status"),
        nullable=False
    ))

def downgrade():
    op.drop_column("orders", "status")
    op.execute("DROP TYPE order_status")
```

### Adding to existing ENUM
```python
def upgrade():
    op.execute("ALTER TYPE order_status ADD VALUE 'refunded'")
```

This must be outside transaction in some Postgres versions:
```python
def upgrade():
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE order_status ADD VALUE 'refunded'")
```

---

## CONCURRENTLY Indexes (Postgres)

`CREATE INDEX CONCURRENTLY` doesn't lock; safe in production.

But Alembic transactions block it. Workaround:

```python
from alembic import op

def upgrade():
    with op.get_context().autocommit_block():
        op.create_index(
            "ix_users_email",
            "users",
            ["email"],
            postgresql_concurrently=True
        )
```

---

## Reversible Migrations Best Practice

### Easy reversals
```python
def downgrade():
    op.drop_table("users")
```

### Hard / impossible reversals
```python
def downgrade():
    raise NotImplementedError("Data loss is irreversible")
```

Always implement downgrade where possible — needed for rollback.

---

## Stamping (Mark DB as Migrated)

When migrating an existing production DB to Alembic:

```bash
# Mark current state as latest revision (no actual changes)
alembic stamp head
```

Then continue normal migration workflow.

---

## Environment-Specific Migrations

Sometimes test/dev/prod need different behavior:

```python
# env.py
import os

def run_migrations_online():
    context.configure(
        connection=connection,
        compare_type=True,
        include_object=include_object,
    )

def include_object(object, name, type_, reflected, compare_to):
    # Skip certain tables in test env
    if os.getenv("ENV") == "test" and name == "audit_log":
        return False
    return True
```

---

## Locking & Concurrent Migrations

Multiple instances of your app starting up at the same time → all want to run migrations.

### Use advisory locks (Postgres)
```python
def upgrade():
    op.execute("SELECT pg_advisory_lock(123456)")
    try:
        # Do migration work
        ...
    finally:
        op.execute("SELECT pg_advisory_unlock(123456)")
```

Or run migration as a separate one-time job before deploying.

---

## CI/CD Integration

### Run migrations on deploy
```yaml
# GitHub Actions
- name: Run migrations
  run: |
    pip install -r requirements.txt
    alembic upgrade head
```

Run **before** the new code is live (it expects the new schema).

### Pre-deploy validation
```bash
# Generate migration locally
alembic revision --autogenerate -m "..."

# Verify it
alembic upgrade --sql head > migration.sql
# Review the SQL

# Test locally
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

---

## Common Pitfalls

### 1. Auto-generate doesn't see your models
Check `target_metadata` in `env.py`. Make sure all models imported.

### 2. Migrations break in production but pass locally
DB state differs. Migrate staging from latest prod backup first.

### 3. Long-running migration kills deploy
Move heavy data ops to background workers.

### 4. Dropping a column still referenced by old code
See file 24 (zero-downtime patterns).

### 5. ENUM modifications outside transaction
Postgres requires autocommit for some changes.

### 6. Server-side defaults in models vs migrations
Default in model (Python-side) vs DB default (SQL-side) — pick one and be consistent.

### 7. Forgetting `op.create_index` after `op.create_table`
Index not created; queries slow.

---

## Production Workflow

```
1. Dev writes migration locally
2. Auto-generated → manually reviewed + edited
3. PR includes migration file
4. CI runs migration in test DB → validates upgrade + downgrade
5. Merge to main
6. Deploy pipeline:
   a. Run `alembic upgrade head` against prod DB
   b. Deploy new code that expects new schema
7. Monitor for errors
```

For risky migrations: feature flag the new code path; backfill data; migrate column rename in next deploy.

---

## TL;DR

- Always review auto-generated migrations.
- Data migrations: use raw SQL or local table reflection, not models.
- CONCURRENTLY for prod indexes.
- Batch huge data updates.
- SQLite needs batch_alter_table; avoid for prod.
- Reversible migrations where possible.
- Stamp existing DBs before adopting.
- Run migrations before deploying new code.
- Test upgrade + downgrade in CI.
