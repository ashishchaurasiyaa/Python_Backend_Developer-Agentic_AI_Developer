"""
Multi-DB Routing — Production Patterns

Covers: read replicas, sharding, analytics DB isolation, replica lag handling.
"""

# ==========================================================================
# 1. SETTINGS — Multiple databases
# ==========================================================================
"""
# settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'app',
        'HOST': os.environ['DB_PRIMARY_HOST'],
        'USER': os.environ['DB_USER'],
        'PASSWORD': os.environ['DB_PASSWORD'],
        'CONN_MAX_AGE': 60,
    },
    'replica1': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'app',
        'HOST': os.environ['DB_REPLICA1_HOST'],
        'USER': os.environ['DB_USER'],
        'PASSWORD': os.environ['DB_PASSWORD'],
        'TEST': {'MIRROR': 'default'},
        'CONN_MAX_AGE': 60,
    },
    'replica2': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'app',
        'HOST': os.environ['DB_REPLICA2_HOST'],
        'TEST': {'MIRROR': 'default'},
    },
    'analytics': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'analytics',
        'HOST': os.environ['DB_ANALYTICS_HOST'],
    },
}

DATABASE_ROUTERS = [
    'myapp.routers.AnalyticsRouter',       # most specific first
    'myapp.routers.PrimaryReplicaRouter',
]
"""


# ==========================================================================
# 2. PRIMARY/REPLICA ROUTER
# ==========================================================================

import random


class PrimaryReplicaRouter:
    """
    Reads → random replica.
    Writes → primary ('default').
    """
    replicas = ['replica1', 'replica2']
    primary_dbs = {'default'}

    def db_for_read(self, model, **hints):
        # Skip routing for analytics models — AnalyticsRouter handles those
        if model._meta.app_label in {'analytics', 'reports'}:
            return None
        return random.choice(self.replicas)

    def db_for_write(self, model, **hints):
        if model._meta.app_label in {'analytics', 'reports'}:
            return None
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        # All replica/primary share data — allow relations between them
        db_set = self.primary_dbs | set(self.replicas)
        if obj1._state.db in db_set and obj2._state.db in db_set:
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label in {'analytics', 'reports'}:
            return None  # AnalyticsRouter decides
        # Migrate to primary only
        return db == 'default'


# ==========================================================================
# 3. ANALYTICS ROUTER (separate DB)
# ==========================================================================

class AnalyticsRouter:
    """Analytics app routes to dedicated 'analytics' DB."""

    analytics_apps = {'analytics', 'reports'}
    analytics_db = 'analytics'

    def db_for_read(self, model, **hints):
        if model._meta.app_label in self.analytics_apps:
            return self.analytics_db
        return None

    def db_for_write(self, model, **hints):
        if model._meta.app_label in self.analytics_apps:
            return self.analytics_db
        return None

    def allow_relation(self, obj1, obj2, **hints):
        # Cross-DB FK disallowed
        labels = {obj1._meta.app_label, obj2._meta.app_label}
        # Both analytics or both non-analytics → OK
        is_both_analytics = labels.issubset(self.analytics_apps)
        is_neither_analytics = not labels.intersection(self.analytics_apps)
        if is_both_analytics or is_neither_analytics:
            return True
        return False

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label in self.analytics_apps:
            return db == self.analytics_db
        return db != self.analytics_db


# ==========================================================================
# 4. SHARDED ROUTER (tenant-based)
# ==========================================================================

from contextvars import ContextVar


current_tenant_id: ContextVar[int | None] = ContextVar(
    'current_tenant_id',
    default=None,
)


class TenantShardRouter:
    """Shards based on current tenant_id."""

    shards = ['shard1', 'shard2', 'shard3', 'shard4']

    def _shard_for_tenant(self):
        tid = current_tenant_id.get()
        if tid is None:
            return None
        return self.shards[tid % len(self.shards)]

    def db_for_read(self, model, **hints):
        return self._shard_for_tenant()

    def db_for_write(self, model, **hints):
        return self._shard_for_tenant()

    def allow_relation(self, obj1, obj2, **hints):
        # Only relations within same shard
        return obj1._state.db == obj2._state.db

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        return db in self.shards


# ==========================================================================
# 5. STICKY-PRIMARY MIDDLEWARE (read-after-write consistency)
# ==========================================================================

import threading


_request_local = threading.local()


def is_sticky():
    return getattr(_request_local, 'force_primary', False)


def mark_sticky():
    _request_local.force_primary = True


def clear_sticky():
    _request_local.force_primary = False


class StickyPrimaryRouter:
    """If request did a write, route subsequent reads to primary."""
    replicas = ['replica1', 'replica2']

    def db_for_read(self, model, **hints):
        if is_sticky():
            return 'default'
        return random.choice(self.replicas)

    def db_for_write(self, model, **hints):
        mark_sticky()  # next reads in this request → primary
        return 'default'


class StickyPrimaryMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        clear_sticky()
        # Force primary for POST/PUT/PATCH/DELETE
        if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
            mark_sticky()
        try:
            response = self.get_response(request)
        finally:
            clear_sticky()
        return response


# ==========================================================================
# 6. EXPLICIT using() CALLS
# ==========================================================================

# from blog.models import Order
# # Read from specific replica
# Order.objects.using('replica1').filter(status='paid')
#
# # Force read from primary (fresh data)
# Order.objects.using('default').get(pk=123)
#
# # Save to specific shard
# order.save(using='shard2')
#
# # Atomic transaction on specific DB
# from django.db import transaction
# with transaction.atomic(using='default'):
#     order = Order.objects.create(...)
#     payment = Payment.objects.create(order=order)


# ==========================================================================
# 7. MANAGEMENT COMMAND — Verify Replica Lag
# ==========================================================================
"""
File: ops/management/commands/check_replica_lag.py
"""

from django.core.management.base import BaseCommand
from django.db import connections


class CheckReplicaLagCommand(BaseCommand):
    help = "Check replication lag for each replica"

    def add_arguments(self, parser):
        parser.add_argument('--max-lag-seconds', type=int, default=5)

    def handle(self, *args, **options):
        max_lag = options['max_lag_seconds']
        replicas = ['replica1', 'replica2']

        for replica in replicas:
            conn = connections[replica]
            with conn.cursor() as c:
                c.execute("""
                    SELECT EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp()))
                """)
                lag = c.fetchone()[0]

            if lag is None:
                self.stdout.write(self.style.WARNING(f"{replica}: no replay (idle)"))
            elif lag > max_lag:
                self.stdout.write(self.style.ERROR(
                    f"{replica}: LAG {lag:.1f}s (over threshold {max_lag}s)"
                ))
            else:
                self.stdout.write(self.style.SUCCESS(f"{replica}: lag {lag:.2f}s"))


# ==========================================================================
# 8. TESTING WITH MULTIPLE DBs
# ==========================================================================
"""
# tests/test_routing.py

from django.test import TestCase, override_settings
from blog.models import Order


class RoutingTests(TestCase):
    databases = {'default', 'replica1', 'replica2'}  # all DBs available in test

    def test_write_goes_to_primary(self):
        order = Order.objects.create(amount=100)
        self.assertEqual(order._state.db, 'default')

    def test_read_goes_to_replica(self):
        Order.objects.create(amount=100)
        order = Order.objects.first()
        self.assertIn(order._state.db, {'replica1', 'replica2'})


# pytest-django:
# @pytest.mark.django_db(databases=['default', 'replica1', 'replica2'])
"""


# ==========================================================================
# 9. CONNECTION POOLING WITH PGBOUNCER
# ==========================================================================
"""
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'app',
        'HOST': 'pgbouncer-primary.svc',  # pgBouncer in front
        'PORT': 6432,
        'CONN_MAX_AGE': 0,  # IMPORTANT: with pgBouncer transaction-pooling, set 0
        'OPTIONS': {
            'application_name': 'django-app',
        },
    },
}
"""
