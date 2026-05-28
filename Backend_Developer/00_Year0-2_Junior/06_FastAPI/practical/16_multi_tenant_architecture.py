"""
============================================================
MULTI-TENANT ARCHITECTURE — Practical
============================================================
Demonstrates all 3 models:
  1. Row-level isolation (most common)
  2. Schema-per-tenant (Postgres SET search_path)
  3. Database-per-tenant (connection pool router)

Plus:
  - Tenant context via contextvars
  - JWT-based tenant resolution
  - Postgres Row-Level Security (RLS) example
  - Cross-tenant safety with background jobs
"""
from __future__ import annotations
import asyncio
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import wraps
from typing import Optional


# ============================================================
# 1. TENANT CONTEXT (request-scoped via ContextVar)
# ============================================================
current_tenant: ContextVar[Optional[str]] = ContextVar("current_tenant", default=None)


class TenantContext:
    """Context manager / decorator to set tenant."""
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.token = None

    def __enter__(self):
        self.token = current_tenant.set(self.tenant_id)
        return self.tenant_id

    def __exit__(self, *exc):
        current_tenant.reset(self.token)


def require_tenant() -> str:
    tid = current_tenant.get()
    if not tid:
        raise PermissionError("No tenant context set")
    return tid


# ============================================================
# 2. MODEL A: ROW-LEVEL ISOLATION
# ============================================================
class RowLevelStore:
    """In-memory store demonstrating row-level multi-tenancy.
    Production: SQLAlchemy with event listener auto-adding WHERE tenant_id=X"""

    def __init__(self):
        self._rows: list[dict] = []

    def insert(self, **fields):
        tid = require_tenant()
        row = {"tenant_id": tid, **fields, "id": len(self._rows) + 1}
        self._rows.append(row)
        return row

    def get(self, row_id: int) -> dict | None:
        tid = require_tenant()
        for row in self._rows:
            if row["id"] == row_id and row["tenant_id"] == tid:
                return row
        return None

    def list_all(self) -> list[dict]:
        tid = require_tenant()
        return [r for r in self._rows if r["tenant_id"] == tid]

    def admin_list_all(self) -> list[dict]:
        """Bypass — for admin/analytics only."""
        return list(self._rows)


def demo_row_level():
    print("=" * 60)
    print("MODEL A: Row-level isolation")
    print("=" * 60)
    store = RowLevelStore()

    with TenantContext("acme"):
        store.insert(name="Alice", email="a@acme.com")
        store.insert(name="Bob", email="b@acme.com")

    with TenantContext("globex"):
        store.insert(name="Charlie", email="c@globex.com")

    with TenantContext("acme"):
        print(f"  acme users  : {store.list_all()}")

    with TenantContext("globex"):
        print(f"  globex users: {store.list_all()}")

    # Try to access acme's user 1 from globex context
    with TenantContext("globex"):
        leaked = store.get(1)
        print(f"  globex tries to access user 1: {leaked} (should be None ✅)")

    print(f"\n  Admin sees all: {len(store.admin_list_all())} rows")


# ============================================================
# 3. SQLALCHEMY EVENT LISTENER (auto-filter pattern)
# ============================================================
SQLALCHEMY_AUTO_FILTER = """
from sqlalchemy import event, Column, String, Integer
from sqlalchemy.orm import Session

class TenantBase:
    tenant_id = Column(String, nullable=False, index=True)

class User(Base, TenantBase):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String)

# Auto-inject tenant_id filter on every SELECT
@event.listens_for(Session, "do_orm_execute")
def add_tenant_filter(execute_state):
    if not execute_state.is_select:
        return
    if execute_state.execution_options.get("skip_tenant_filter"):
        return    # explicit opt-out for admin queries
    tenant_id = current_tenant.get()
    if tenant_id is None:
        raise RuntimeError("No tenant context — possible leak!")
    # Add WHERE tenant_id = :tid to the statement
    execute_state.statement = execute_state.statement.where(
        getattr(execute_state.bind_mapper.class_, "tenant_id") == tenant_id
    )

# Auto-set tenant_id on INSERT
@event.listens_for(Session, "before_insert")
def set_tenant_on_insert(mapper, conn, target):
    if hasattr(target, "tenant_id") and target.tenant_id is None:
        target.tenant_id = require_tenant()
"""


# ============================================================
# 4. POSTGRES ROW-LEVEL SECURITY (DEFENSE IN DEPTH)
# ============================================================
POSTGRES_RLS = """
-- Enable RLS on table
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

-- Policy: only see rows matching current setting
CREATE POLICY tenant_isolation ON users
    USING (tenant_id = current_setting('app.current_tenant')::text);

-- (Optional) for INSERTs too
CREATE POLICY tenant_isolation_insert ON users
    FOR INSERT
    WITH CHECK (tenant_id = current_setting('app.current_tenant')::text);

-- App sets this on every connection (or per-transaction with SET LOCAL):
SET app.current_tenant = 'acme';

-- Now even SELECT * FROM users returns only acme's rows
-- Even if app forgets WHERE tenant_id, DB enforces.
"""


# ============================================================
# 5. MODEL B: SCHEMA-PER-TENANT
# ============================================================
class SchemaPerTenantStore:
    """Each tenant has separate schema. We simulate with nested dicts."""
    def __init__(self):
        self.schemas: dict[str, list[dict]] = {}

    def provision_tenant(self, tenant_id: str):
        if tenant_id not in self.schemas:
            self.schemas[tenant_id] = []
            print(f"    Provisioned schema tenant_{tenant_id}")

    def insert(self, **fields):
        tid = require_tenant()
        if tid not in self.schemas:
            raise RuntimeError(f"Schema not provisioned for {tid}")
        row = {**fields, "id": len(self.schemas[tid]) + 1}
        self.schemas[tid].append(row)
        return row

    def list_all(self) -> list[dict]:
        tid = require_tenant()
        return self.schemas.get(tid, [])


SCHEMA_SQL_TEMPLATE = """
-- Onboard new tenant:
CREATE SCHEMA tenant_acme;
GRANT ALL ON SCHEMA tenant_acme TO app_user;

-- Run migrations targeting this schema
SET search_path TO tenant_acme;
CREATE TABLE users (id SERIAL PRIMARY KEY, email TEXT);

-- Per-request: switch schema
SET search_path TO tenant_acme, public;
SELECT * FROM users;   -- queries tenant_acme.users
"""


def demo_schema_per_tenant():
    print("\n" + "=" * 60)
    print("MODEL B: Schema-per-tenant")
    print("=" * 60)
    store = SchemaPerTenantStore()
    store.provision_tenant("acme")
    store.provision_tenant("globex")

    with TenantContext("acme"):
        store.insert(name="Alice")
        store.insert(name="Bob")

    with TenantContext("globex"):
        store.insert(name="Charlie")

    with TenantContext("acme"):
        print(f"  acme schema  : {store.list_all()}")
    with TenantContext("globex"):
        print(f"  globex schema: {store.list_all()}")


# ============================================================
# 6. MODEL C: DATABASE-PER-TENANT (LRU pool router)
# ============================================================
class DatabasePerTenantRouter:
    """Router managing connection pools per tenant.
    Production: use LRU cache to limit open pools."""

    def __init__(self, max_pools: int = 100):
        self.max_pools = max_pools
        self._pools: dict[str, list] = {}    # tenant_id → "pool" (list of rows here)

    def get_pool(self, tenant_id: str):
        if tenant_id not in self._pools:
            if len(self._pools) >= self.max_pools:
                # LRU eviction in production
                oldest = next(iter(self._pools))
                del self._pools[oldest]
                print(f"    Evicted pool for {oldest}")
            self._pools[tenant_id] = []
            print(f"    Created pool for {tenant_id}")
        return self._pools[tenant_id]

    def insert(self, **fields):
        tid = require_tenant()
        pool = self.get_pool(tid)
        row = {**fields, "id": len(pool) + 1}
        pool.append(row)
        return row

    def list_all(self):
        tid = require_tenant()
        return self.get_pool(tid)


DB_PER_TENANT_CONFIG = """
# Database URLs by tenant (production: store in central config DB)
TENANT_DBS = {
    "acme":   "postgresql://acme:pwd@db-acme.internal:5432/acme",
    "globex": "postgresql://glx:pwd@db-globex.internal:5432/globex",
}

class TenantEngineRouter:
    def __init__(self):
        self._engines = {}
    @lru_cache(maxsize=100)
    def get_engine(self, tenant_id: str) -> AsyncEngine:
        url = TENANT_DBS[tenant_id]
        return create_async_engine(url, pool_size=5, max_overflow=10)
"""


def demo_db_per_tenant():
    print("\n" + "=" * 60)
    print("MODEL C: Database-per-tenant")
    print("=" * 60)
    router = DatabasePerTenantRouter(max_pools=3)

    for tenant in ["t1", "t2", "t3", "t4"]:   # 4 tenants, only 3 pool slots
        with TenantContext(tenant):
            router.insert(name=f"user-of-{tenant}")
            print(f"  {tenant} data: {router.list_all()}")
    # LRU evicted t1 when t4 came in


# ============================================================
# 7. JWT TENANT RESOLUTION
# ============================================================
JWT_TENANT_MIDDLEWARE = """
from fastapi import FastAPI, Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import jwt

class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Skip for public endpoints
        if request.url.path.startswith("/public"):
            return await call_next(request)

        auth = request.headers.get("authorization", "")
        if not auth.startswith("Bearer "):
            return JSONResponse({"error": "missing token"}, 401)

        try:
            payload = jwt.decode(auth[7:], SECRET, algorithms=["HS256"])
            tenant_id = payload["tenant_id"]
        except jwt.InvalidTokenError:
            return JSONResponse({"error": "invalid token"}, 401)

        token = current_tenant.set(tenant_id)
        try:
            response = await call_next(request)
            response.headers["X-Tenant-ID"] = tenant_id   # optional debug
            return response
        finally:
            current_tenant.reset(token)

app = FastAPI()
app.add_middleware(TenantMiddleware)
"""


# ============================================================
# 8. BACKGROUND JOB SAFETY
# ============================================================
@dataclass
class CeleryTaskBase:
    """Decorator pattern for tenant-safe background jobs."""

    def __call__(self, func):
        @wraps(func)
        def wrapper(tenant_id: str, *args, **kwargs):
            with TenantContext(tenant_id):
                return func(*args, **kwargs)
        return wrapper


tenant_task = CeleryTaskBase()


@tenant_task
def send_welcome_email(user_id: int):
    tid = require_tenant()
    print(f"    Sending welcome email for user {user_id} in tenant {tid}")
    # Now safe — queries inside auto-filter


def demo_background_job():
    print("\n" + "=" * 60)
    print("BACKGROUND JOB SAFETY")
    print("=" * 60)
    # In Celery: send_welcome_email.delay("acme", 42)
    print("  Job for tenant acme, user 42:")
    send_welcome_email("acme", 42)
    print("  Job for tenant globex, user 99:")
    send_welcome_email("globex", 99)


# ============================================================
# 9. CACHE KEY SAFETY
# ============================================================
def tenant_cache_key(*parts) -> str:
    """Always include tenant_id in cache key — prevents cross-tenant leaks."""
    tid = require_tenant()
    return f"t:{tid}:" + ":".join(str(p) for p in parts)


def demo_cache_safety():
    print("\n" + "=" * 60)
    print("CACHE KEY SAFETY")
    print("=" * 60)
    with TenantContext("acme"):
        print(f"  acme user 42 key  : {tenant_cache_key('user', 42)}")
    with TenantContext("globex"):
        print(f"  globex user 42 key: {tenant_cache_key('user', 42)}")
    print("  ↑ Different keys — no cache collision")


# ============================================================
# 10. CROSS-TENANT ENUMERATION DEFENSE
# ============================================================
def get_user_safe(user_id, all_users):
    """Defense: even if user_id valid, verify tenant ownership."""
    tid = require_tenant()
    for u in all_users:
        if u["id"] == user_id:
            if u["tenant_id"] != tid:
                raise PermissionError(f"User {user_id} not in your tenant")
            return u
    raise LookupError("not found")


def demo_enumeration_attack():
    print("\n" + "=" * 60)
    print("ENUMERATION ATTACK DEFENSE")
    print("=" * 60)
    all_users = [
        {"id": 1, "tenant_id": "acme", "email": "a@acme.com"},
        {"id": 2, "tenant_id": "globex", "email": "b@globex.com"},
    ]
    with TenantContext("globex"):
        try:
            get_user_safe(1, all_users)   # try to grab acme's user
        except PermissionError as e:
            print(f"  ✅ Blocked: {e}")


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    demo_row_level()
    demo_schema_per_tenant()
    demo_db_per_tenant()
    demo_background_job()
    demo_cache_safety()
    demo_enumeration_attack()

    print("\n" + "=" * 60)
    print("PRODUCTION TEMPLATES")
    print("=" * 60)
    print("\n--- SQLAlchemy auto-filter ---")
    print(SQLALCHEMY_AUTO_FILTER)
    print("\n--- Postgres Row-Level Security ---")
    print(POSTGRES_RLS)
    print("\n--- Schema-per-tenant SQL ---")
    print(SCHEMA_SQL_TEMPLATE)
    print("\n--- DB-per-tenant config ---")
    print(DB_PER_TENANT_CONFIG)
    print("\n--- JWT tenant middleware ---")
    print(JWT_TENANT_MIDDLEWARE)

    print("\n" + "=" * 60)
    print("KEY TAKEAWAYS")
    print("=" * 60)
    print("""
1. Pick model based on tenant count + isolation needs
2. Use ContextVar for request-scoped tenant context
3. Defense in depth: app filter + Postgres RLS
4. Tenant ID in cache keys, log lines, background jobs
5. Verify ownership on every record fetch (no enumeration)
6. Test isolation in CI — automated cross-tenant tests
""")
