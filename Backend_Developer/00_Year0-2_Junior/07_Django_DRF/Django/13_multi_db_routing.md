# Django Multi-DB Routing — Read Replicas & Sharding

## Why It Matters (Senior 5 YOE Context)

Multi-DB routing = **scale path for read-heavy Django apps**:

- **Read replicas** → offload SELECTs to followers, primary handles writes
- **Sharding** → split data by tenant/region across multiple DBs
- **Hot-cold split** → archive old data to cheap DB
- **Analytics isolation** → heavy OLAP queries to dedicated replica

Senior interview: "DB getting CPU-bound on reads. How do you scale Django?" — DATABASE_ROUTERS + read replicas.

---

## Core Concepts

### Configuring Multiple Databases

```python
# settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'app',
        'HOST': 'primary.db.internal',
        'PORT': 5432,
    },
    'replica1': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'app',
        'HOST': 'replica1.db.internal',
        'PORT': 5432,
        'TEST': {'MIRROR': 'default'},  # tests share schema
    },
    'replica2': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'app',
        'HOST': 'replica2.db.internal',
        'PORT': 5432,
        'TEST': {'MIRROR': 'default'},
    },
    'analytics': {  # separate DB
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'analytics',
        'HOST': 'analytics.db.internal',
    },
}

DATABASE_ROUTERS = ['myapp.routers.PrimaryReplicaRouter']
```

### Router Interface

```python
# myapp/routers.py
import random


class PrimaryReplicaRouter:
    """
    Reads go to random replica.
    Writes go to primary.
    No cross-DB relations.
    """
    replicas = ['replica1', 'replica2']

    def db_for_read(self, model, **hints):
        return random.choice(self.replicas)

    def db_for_write(self, model, **hints):
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        # Allow if both objects are from primary/replicas (same data)
        db_set = {'default', *self.replicas}
        if obj1._state.db in db_set and obj2._state.db in db_set:
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        # Migrations only on primary
        return db == 'default'
```

### Manual DB Selection (`using()`)

```python
# Force read from replica
Order.objects.using('replica1').filter(user=user)

# Force write to primary
order.save(using='default')

# Atomic transaction on specific DB
from django.db import transaction
with transaction.atomic(using='default'):
    order.save()
```

### Analytics DB (separate models)

```python
# myapp/routers.py
class AnalyticsRouter:
    """Analytics models go to analytics DB."""

    analytics_apps = {'analytics', 'reports'}

    def db_for_read(self, model, **hints):
        if model._meta.app_label in self.analytics_apps:
            return 'analytics'
        return None

    def db_for_write(self, model, **hints):
        if model._meta.app_label in self.analytics_apps:
            return 'analytics'
        return None

    def allow_relation(self, obj1, obj2, **hints):
        # No FK across primary <-> analytics
        if self._is_analytics(obj1) != self._is_analytics(obj2):
            return False
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label in self.analytics_apps:
            return db == 'analytics'
        return db == 'default'

    def _is_analytics(self, obj):
        return obj._meta.app_label in self.analytics_apps
```

### Sharding by Tenant

```python
class TenantShardRouter:
    """Shards based on tenant_id from thread-local context."""
    shards = ['shard1', 'shard2', 'shard3', 'shard4']

    def _shard_for(self, hints):
        from .context import current_tenant_id
        tid = current_tenant_id.get()
        if tid is None:
            return None
        # Consistent hashing — change carefully
        return self.shards[tid % len(self.shards)]

    def db_for_read(self, model, **hints):
        return self._shard_for(hints)

    def db_for_write(self, model, **hints):
        return self._shard_for(hints)

    def allow_relation(self, obj1, obj2, **hints):
        # Allow only within same shard
        return obj1._state.db == obj2._state.db

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        # Migrate to all shards
        return db in self.shards
```

---

## How It Works Internally

### Router Resolution Order

Django evaluates routers in `DATABASE_ROUTERS` order:

```python
# Django: db.utils.ConnectionRouter
for router in self.routers:
    method = getattr(router, action, None)
    if method is None:
        continue
    chosen_db = method(model, **hints)
    if chosen_db is not None:
        return chosen_db
return 'default'
```

First non-`None` return wins. Returning `None` = abstain.

### Replica Lag Pitfall

Replica is asynchronously updated → **read-after-write returns stale data**:

```python
order = Order.objects.create(...)  # default (primary)
# Immediately:
Order.objects.get(pk=order.pk)  # may hit replica → DoesNotExist
```

**Fix:** Force read from primary after write within same request:

```python
# Pattern 1: force using
order = Order.objects.create(...)
fresh = Order.objects.using('default').get(pk=order.pk)

# Pattern 2: middleware to mark "writes happened" → all reads in same request go to primary
```

### `allow_relation()` for Cross-DB Joins

Django ORM doesn't do cross-DB joins. If `allow_relation` returns `False`, the ORM raises:

```
ValueError: Cannot assign "<Order: 1>": the current database
router prevents this relation.
```

For replicas (same data), allow. For separate DBs (analytics), deny.

---

## Common Pitfalls

### 1. Replica Lag in Forms / Wizard Flows

```python
# Submit form, redirect to detail page
def create_order(request):
    order = Order.objects.create(...)
    return redirect('order-detail', pk=order.pk)

# Detail view hits replica → 404 (lag)
def order_detail(request, pk):
    return get_object_or_404(Order, pk=pk)
```

**Fix:** Middleware that marks "POST happened" → next read uses primary. Or explicit `using('default')` for fresh data.

### 2. `migrate` Tries All DBs

If `allow_migrate()` returns `True` for all, migrations run on each → conflicting state. Always restrict to primary.

### 3. Cross-DB Models in Same Query

```python
# Order on primary, AnalyticsEvent on analytics
Order.objects.filter(events__type='view')  # cross-DB JOIN — fails
```

**Fix:** Denormalize or do app-level join (two queries + Python merge).

### 4. Connection Pool Exhaustion

Multi-DB = N pools. Tune `CONN_MAX_AGE` and pool size per DB. Use pgBouncer in front.

### 5. Test Setup with Replicas

```python
# Tests need TEST: {'MIRROR': 'default'} else Django creates separate test DB per replica
DATABASES['replica1']['TEST'] = {'MIRROR': 'default'}
```

### 6. Sticky Reads Not Implemented Out-of-Box

Django doesn't auto-stick "read your own writes" — you build it (middleware, decorators).

---

## Interview Q&A

**Q1:** Read replicas Django mein kaise add karte ho?
**A:** (1) Add replicas to `DATABASES`. (2) Write `DATABASE_ROUTERS` class with `db_for_read` → random replica, `db_for_write` → 'default'. (3) `allow_migrate` only on 'default'. (4) Handle replica lag (read-after-write) via `using('default')` or sticky-primary middleware.

**Q2:** Replica lag se kaise deal karoge?
**A:** Three approaches: (1) Middleware that flags request as "write happened" → all subsequent reads in same request go to primary. (2) `using('default')` explicitly after writes. (3) Synchronous replication (rare, perf cost) or stronger read concerns. Best is to design APIs that don't require immediate read-after-write.

**Q3:** Sharding kab implement karoge Django mein?
**A:** Vertical (split tables to different DBs) when CPU/IO bound on one DB. Horizontal (same table sharded by tenant/region) when single DB can't hold all data. Django doesn't natively do query splitting — use `using()` with context-aware routers. `django-pgshard` library exists.

**Q4:** Migration multi-DB pe kaise handle hota hai?
**A:** `allow_migrate(db, app_label, ...)` returns True/False. Default: migrate on primary only. For sharded setup: migrate on each shard. Watch out: Django runs migrations sequentially — long migration on each shard = downtime.

**Q5:** `using('replica1')` vs router-based selection?
**A:** Router = automatic, transparent, set-once. `using()` = manual, explicit, useful for one-off ("this query MUST hit primary"). Best practice: routers for default behavior, `using()` for exceptions.

**Q6:** Cross-DB foreign keys kaise handle karoge?
**A:** Django doesn't support cross-DB joins. Options: (1) Denormalize (duplicate data), (2) Use `IntegerField` instead of `ForeignKey` for cross-DB relations + manual join in Python, (3) Use materialized views, (4) Keep related data on same shard.

**Q7:** PostgreSQL streaming replication setup Django ke saath kaise verify karoge?
**A:** On replica: `SELECT pg_is_in_recovery();` → True. Check lag: `SELECT now() - pg_last_xact_replay_timestamp();`. Django connection: `SELECT pg_is_in_recovery()` per-query to verify routing. Monitoring: `pg_stat_replication` on primary.

**Q8:** Analytics queries on primary se kaise migrate karoge?
**A:** Mark analytics models in separate app (`reports/`). Add `AnalyticsRouter` that routes those models to dedicated DB. Backfill via Celery + `bulk_create(using='analytics')`. CDC (Change Data Capture) via Debezium for real-time sync.

---

## Real-World Use Cases

### 1. Read Scaling for E-commerce

```python
# Routers configured: 3 replicas + 1 primary
# Heavy reads (product listing, search) auto-routed to replicas
# Writes (add to cart, checkout) go to primary
# pgBouncer in front of each DB for connection pooling
```

### 2. Multi-Tenant SaaS Sharding

```python
# Tenants 1-1000 → shard1
# Tenants 1001-2000 → shard2
# Schema-per-tenant via django-tenants OR DB-per-tenant via custom router
```

### 3. Hot-Cold Archive

```python
class ArchiveRouter:
    """Old orders (>1 year) on cheaper 'archive' DB."""

    def db_for_read(self, model, **hints):
        if model.__name__ == 'Order':
            # Check hints for date filter
            if hints.get('archive'):
                return 'archive'
        return None
```

---

## References

- [Django multi-DB docs](https://docs.djangoproject.com/en/5.0/topics/db/multi-db/)
- [PostgreSQL streaming replication](https://www.postgresql.org/docs/current/warm-standby.html)
- `django-multidb-router` package
- Heap Inc. blog — "How Heap Sharded Postgres"
