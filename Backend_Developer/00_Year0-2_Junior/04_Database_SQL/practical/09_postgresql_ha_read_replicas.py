"""
============================================================
POSTGRESQL HA + READ REPLICAS — Practical
============================================================
Demonstrates:
1. Read/write splitting in SQLAlchemy
2. Multi-host connection string (Postgres 10+)
3. Replication lag monitoring
4. Read-after-write consistency strategies
5. Failover detection + reconnect

Setup local replication for testing:
    # docker-compose.yml shown below
"""
from __future__ import annotations
import asyncio
import time
import random
from contextvars import ContextVar
from dataclasses import dataclass


# ============================================================
# 1. DOCKER-COMPOSE for local primary + replica
# ============================================================
DOCKER_COMPOSE = """
version: '3'
services:
  pg-primary:
    image: postgres:16
    environment:
      POSTGRES_PASSWORD: secret
      POSTGRES_DB: app
    ports: ["5432:5432"]
    command: >
      postgres -c wal_level=replica
               -c max_wal_senders=10
               -c max_replication_slots=10
               -c hot_standby=on
    volumes:
      - ./primary-init.sql:/docker-entrypoint-initdb.d/init.sql

  pg-replica:
    image: postgres:16
    depends_on: [pg-primary]
    ports: ["5433:5432"]
    environment:
      POSTGRES_PASSWORD: secret
    command: >
      bash -c "
        until pg_basebackup -h pg-primary -U postgres -D /var/lib/postgresql/data -Fp -Xs -R -w; do
          sleep 1
        done
        postgres -c hot_standby=on
      "
"""

PRIMARY_INIT_SQL = """
CREATE USER replicator REPLICATION LOGIN PASSWORD 'replicator';
SELECT pg_create_physical_replication_slot('replica_1');
"""


# ============================================================
# 2. SQLALCHEMY READ/WRITE SPLITTING
# ============================================================
RW_SPLIT_SQLALCHEMY = """
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

write_engine = create_async_engine(
    "postgresql+asyncpg://app:secret@pg-primary:5432/app",
    pool_size=20, max_overflow=10,
)

read_engine = create_async_engine(
    "postgresql+asyncpg://app:secret@pg-replica-lb:5432/app",
    pool_size=50, max_overflow=20,   # more capacity for reads
)

WriteSession = sessionmaker(write_engine, class_=AsyncSession, expire_on_commit=False)
ReadSession  = sessionmaker(read_engine,  class_=AsyncSession, expire_on_commit=False)

# In FastAPI dependency
async def get_db(read_only: bool = False):
    Session = ReadSession if read_only else WriteSession
    async with Session() as session:
        yield session

# Endpoint usage
@app.get("/users/{id}")
async def get_user(id: int, db = Depends(lambda: get_db(read_only=True))):
    return await db.get(User, id)

@app.post("/users")
async def create_user(data, db = Depends(get_db)):
    user = User(**data)
    db.add(user)
    await db.commit()
"""


# ============================================================
# 3. ROUTING SESSION (auto-detects intent)
# ============================================================
AUTO_ROUTING_SESSION = """
from sqlalchemy.orm import Session
from sqlalchemy.sql import Insert, Update, Delete

class RoutedSession(Session):
    \"\"\"Routes writes to primary, reads to replica automatically.\"\"\"
    def __init__(self, write_engine, read_engine, **kwargs):
        self.write_engine = write_engine
        self.read_engine = read_engine
        super().__init__(**kwargs)

    def get_bind(self, mapper=None, clause=None, **kw):
        if self._flushing or isinstance(clause, (Insert, Update, Delete)):
            return self.write_engine
        if self.in_transaction() and self.info.get('forced_write'):
            return self.write_engine
        return self.read_engine
"""


# ============================================================
# 4. READ-YOUR-OWN-WRITES PATTERN
# ============================================================
class ReadYourWrites:
    """Tracks recent writes per session/user.
    If user wrote recently, force reads to primary."""

    def __init__(self, sticky_seconds: float = 5.0):
        self.sticky_seconds = sticky_seconds
        self._last_writes: dict[str, float] = {}

    def mark_wrote(self, session_id: str):
        self._last_writes[session_id] = time.time()

    def needs_primary(self, session_id: str) -> bool:
        last = self._last_writes.get(session_id)
        if last is None:
            return False
        return time.time() - last < self.sticky_seconds


def demo_read_your_writes():
    print("=" * 60)
    print("READ-YOUR-OWN-WRITES")
    print("=" * 60)
    ryw = ReadYourWrites(sticky_seconds=2)
    session_id = "user-42-session"

    print(f"  Initial: needs primary? {ryw.needs_primary(session_id)}")
    ryw.mark_wrote(session_id)
    print(f"  After write: needs primary? {ryw.needs_primary(session_id)} ← TRUE")
    time.sleep(2.1)
    print(f"  After 2s wait: needs primary? {ryw.needs_primary(session_id)} ← false (lag tolerable)")


# ============================================================
# 5. REPLICATION LAG MONITORING
# ============================================================
LAG_MONITORING_SQL = """
-- On primary: bytes ahead of each replica
SELECT
    application_name,
    pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), sent_lsn)) AS sent_lag,
    pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), write_lsn)) AS write_lag,
    pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), flush_lsn)) AS flush_lag,
    pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn)) AS replay_lag,
    state, sync_state
FROM pg_stat_replication;

-- On replica: seconds behind primary
SELECT
    pg_is_in_recovery(),
    pg_last_wal_receive_lsn(),
    pg_last_wal_replay_lsn(),
    EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp())) AS seconds_behind;

-- Replication slots
SELECT slot_name, active, restart_lsn, confirmed_flush_lsn
FROM pg_replication_slots;
"""


async def monitor_replication_lag(write_engine, threshold_seconds: float = 5):
    """Background task: alert if replication lag exceeds threshold."""
    from sqlalchemy import text
    async with write_engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT
                application_name,
                EXTRACT(EPOCH FROM (now() - replay_lsn::pg_lsn::text::timestamp)) AS lag
            FROM pg_stat_replication
        """))
        for row in result:
            if row.lag and row.lag > threshold_seconds:
                # Alert via PagerDuty / Slack
                print(f"  ⚠️  Replica {row.application_name} lag: {row.lag:.1f}s")


# ============================================================
# 6. FAILOVER-AWARE CONNECTION POOL
# ============================================================
class HAEngineRouter:
    """Routes to current primary, falls back if primary unreachable."""

    def __init__(self, primary_hosts: list[str], replica_hosts: list[str]):
        self.primary_hosts = primary_hosts
        self.replica_hosts = replica_hosts
        self._current_primary = primary_hosts[0]
        self._last_check = 0.0
        self._unhealthy: set[str] = set()

    def get_primary_url(self) -> str:
        # Refresh every 30s
        if time.time() - self._last_check > 30:
            self._discover_primary()
        return self._current_primary

    def get_replica_url(self) -> str:
        healthy_replicas = [h for h in self.replica_hosts if h not in self._unhealthy]
        if not healthy_replicas:
            return self.get_primary_url()    # fallback to primary
        return random.choice(healthy_replicas)

    def _discover_primary(self):
        """Probe each host to find current primary (pg_is_in_recovery() = false)."""
        # In real code: connect, run SELECT pg_is_in_recovery(), pick the one returning false
        self._last_check = time.time()
        # Simplified


# ============================================================
# 7. MULTI-HOST CONNECTION STRING (Postgres 10+)
# ============================================================
MULTI_HOST_CONNECTION = """
# Postgres native client supports multi-host strings.
# Driver tries each host in order, uses first that matches criteria.

# target_session_attrs options:
#   - any         : any host (default)
#   - read-write  : only primary (writes accepted)
#   - read-only   : only standby (no writes)
#   - primary     : alias for read-write
#   - standby     : alias for read-only
#   - prefer-standby : prefer standby, fall back to any

write_url = "postgresql://user:pass@host1,host2,host3:5432/db?target_session_attrs=read-write"
read_url  = "postgresql://user:pass@host1,host2,host3:5432/db?target_session_attrs=prefer-standby"

# When primary fails:
# - Old connection breaks
# - New connection attempt picks next host in list
# - target_session_attrs=read-write skips replicas
# - Failover discovered automatically
"""


# ============================================================
# 8. RECONNECT-ON-FAILURE PATTERN
# ============================================================
ASYNC_RECONNECT_PATTERN = """
import backoff
from sqlalchemy.exc import OperationalError, DBAPIError

@backoff.on_exception(
    backoff.expo,
    (OperationalError, DBAPIError),
    max_tries=5,
    max_time=30,
)
async def safe_query(session, query):
    return await session.execute(query)

# In SQLAlchemy engine config
engine = create_async_engine(
    url,
    pool_pre_ping=True,        # Test connection before use (handles failover)
    pool_recycle=3600,         # Recycle connections hourly
    connect_args={
        "server_settings": {"application_name": "my-app"},
    },
)
"""


# ============================================================
# 9. FASTAPI INTEGRATION
# ============================================================
FASTAPI_DI = """
from fastapi import Depends, FastAPI, HTTPException

app = FastAPI()

async def get_read_db():
    async with ReadSession() as session:
        yield session

async def get_write_db():
    async with WriteSession() as session:
        yield session

@app.get("/users/{id}")
async def get_user(id: int, db: AsyncSession = Depends(get_read_db)):
    user = await db.get(User, id)
    if not user:
        raise HTTPException(404)
    return user

@app.post("/users")
async def create(data, db: AsyncSession = Depends(get_write_db)):
    user = User(**data.dict())
    db.add(user)
    await db.commit()
    await db.refresh(user)
    # Mark this session as recently-written for ryw
    return user

# For read-your-writes: middleware that checks session_id + recent writes
@app.middleware("http")
async def ryw_routing(request, call_next):
    # If user recently wrote, attach hint to use primary
    session_id = request.cookies.get("session_id")
    if session_id and ryw.needs_primary(session_id):
        request.state.force_primary = True
    return await call_next(request)
"""


# ============================================================
# 10. HEALTH CHECK ENDPOINT
# ============================================================
HEALTH_CHECK = """
@app.get("/health/db")
async def db_health():
    health = {"primary": False, "replicas": []}
    try:
        async with WriteSession() as s:
            r = await s.execute(text("SELECT pg_is_in_recovery()"))
            health["primary"] = not r.scalar()
    except Exception as e:
        health["primary_error"] = str(e)

    for url in REPLICA_URLS:
        try:
            engine = create_async_engine(url)
            async with engine.begin() as conn:
                lag = await conn.execute(text(
                    "SELECT EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp()))"
                ))
                health["replicas"].append({"url": url, "lag_seconds": lag.scalar()})
        except Exception as e:
            health["replicas"].append({"url": url, "error": str(e)})

    status = 200 if health["primary"] else 503
    return JSONResponse(health, status_code=status)
"""


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    demo_read_your_writes()

    print("\n" + "=" * 60)
    print("DOCKER COMPOSE — Local primary + replica")
    print("=" * 60)
    print(DOCKER_COMPOSE)

    print("\n" + "=" * 60)
    print("REPLICATION LAG MONITORING SQL")
    print("=" * 60)
    print(LAG_MONITORING_SQL)

    print("\n" + "=" * 60)
    print("MULTI-HOST CONNECTION STRING")
    print("=" * 60)
    print(MULTI_HOST_CONNECTION)

    print("\n" + "=" * 60)
    print("SQLALCHEMY READ/WRITE SPLIT")
    print("=" * 60)
    print(RW_SPLIT_SQLALCHEMY)

    print("\n" + "=" * 60)
    print("FASTAPI INTEGRATION")
    print("=" * 60)
    print(FASTAPI_DI)
