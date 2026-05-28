"""
============================================================
PGBOUNCER + CONNECTION POOLING — Practical
============================================================
Templates + working SQLAlchemy/asyncpg patterns for PgBouncer.

Topics:
1. pgbouncer.ini config template
2. Docker compose setup
3. SQLAlchemy with PgBouncer (transaction mode)
4. Monitor pool stats via SHOW POOLS
5. HAProxy in front of multiple PgBouncers
"""


# ============================================================
# 1. PGBOUNCER.INI — Production template
# ============================================================
PGBOUNCER_INI = """
[databases]
mydb = host=postgres-primary port=5432 dbname=mydb pool_size=50
mydb_replica = host=postgres-replica port=5432 dbname=mydb pool_size=100

# Wildcard for multiple databases
* = host=postgres-primary port=5432

[pgbouncer]
listen_port = 6432
listen_addr = *

# Auth
auth_type = scram-sha-256
auth_file = /etc/pgbouncer/userlist.txt
admin_users = pgbouncer_admin

# Pool mode — TRANSACTION for max multiplexing
pool_mode = transaction

# Sizing
max_client_conn = 10000           # max clients connecting to pgbouncer
default_pool_size = 50            # backend conns per (user, db) pair
min_pool_size = 5                 # warm pool size
reserve_pool_size = 5             # extra for emergencies
reserve_pool_timeout = 3          # client waits this long before reserve activates

# Per-database limits
max_db_connections = 100          # cap total backend conns
max_user_connections = 50         # per-user limit

# Timeouts
server_idle_timeout = 60          # close idle backend after 60s
server_lifetime = 3600            # recycle backend hourly
client_idle_timeout = 0           # 0 = don't kill idle clients
client_login_timeout = 60         # auth handshake timeout
query_timeout = 0                 # 0 = no limit
query_wait_timeout = 120          # max wait for free backend

# Stats
stats_period = 60                 # SHOW STATS resolution
log_connections = 0               # 1 = log every connect (noisy)
log_disconnections = 0
log_pooler_errors = 1

# TLS to backend
server_tls_sslmode = require
server_tls_ca_file = /etc/ssl/certs/ca.crt

# Application name visible in pg_stat_activity
application_name_add_host = 1
"""

USERLIST_TXT = """
# /etc/pgbouncer/userlist.txt
# Format: "username" "password_hash"
"app_user" "SCRAM-SHA-256$4096:..."
"pgbouncer_admin" "SCRAM-SHA-256$4096:..."

# To generate hash:
# psql -At -c "SELECT rolpassword FROM pg_authid WHERE rolname='app_user'"
"""


# ============================================================
# 2. DOCKER COMPOSE — PgBouncer + Postgres + HAProxy
# ============================================================
DOCKER_COMPOSE = """
version: '3.8'

services:
  postgres-primary:
    image: postgres:16
    environment:
      POSTGRES_PASSWORD: secret
      POSTGRES_DB: mydb
    ports: ["5432:5432"]
    command: >
      postgres -c max_connections=200
               -c shared_buffers=512MB
               -c effective_cache_size=1500MB

  pgbouncer-1:
    image: edoburu/pgbouncer:latest
    environment:
      DB_HOST: postgres-primary
      DB_PORT: 5432
      DB_USER: app_user
      DB_PASSWORD: secret
      POOL_MODE: transaction
      MAX_CLIENT_CONN: 10000
      DEFAULT_POOL_SIZE: 50
      ADMIN_USERS: pgbouncer_admin
    ports: ["6432:6432"]
    depends_on: [postgres-primary]

  pgbouncer-2:
    image: edoburu/pgbouncer:latest
    environment:
      DB_HOST: postgres-primary
      POOL_MODE: transaction
      DEFAULT_POOL_SIZE: 50
    ports: ["6433:6432"]

  haproxy:
    image: haproxy:latest
    ports: ["5000:5000"]
    volumes:
      - ./haproxy.cfg:/usr/local/etc/haproxy/haproxy.cfg
    depends_on: [pgbouncer-1, pgbouncer-2]

# haproxy.cfg
# global
#     maxconn 10000
# frontend pgbouncer
#     bind *:5000
#     default_backend pgbouncers
# backend pgbouncers
#     mode tcp
#     balance leastconn
#     option tcp-check
#     server pgb1 pgbouncer-1:6432 check
#     server pgb2 pgbouncer-2:6432 check
"""


# ============================================================
# 3. SQLALCHEMY + PGBOUNCER (TRANSACTION MODE)
# ============================================================
SQLALCHEMY_CONFIG = """
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool, QueuePool

# IMPORTANT: With PgBouncer transaction mode, disable prepared statements!

# Option A: NullPool (PgBouncer handles ALL pooling)
engine = create_async_engine(
    "postgresql+asyncpg://app_user:secret@pgbouncer:6432/mydb",
    poolclass=NullPool,
    connect_args={
        # asyncpg-specific: disable prepared statement cache
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
        "server_settings": {
            "application_name": "my-api",
            "jit": "off",          # JIT compilation can hurt OLTP
        },
    },
)

# Option B: Small SQLAlchemy pool + PgBouncer (best of both)
engine = create_async_engine(
    "postgresql+asyncpg://app_user:secret@pgbouncer:6432/mydb",
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,          # detect dead conns (PgBouncer may recycle)
    pool_recycle=300,            # recycle every 5 min
    connect_args={
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    },
)
"""


# ============================================================
# 4. PSYCOPG2 + PGBOUNCER
# ============================================================
PSYCOPG_CONFIG = """
# psycopg2 (sync)
import psycopg2.pool

pool = psycopg2.pool.ThreadedConnectionPool(
    minconn=1, maxconn=20,
    host="pgbouncer", port=6432,
    user="app_user", password="secret", database="mydb",
)

# psycopg3 (modern, sync+async)
import psycopg_pool

pool = psycopg_pool.AsyncConnectionPool(
    "postgresql://app_user:secret@pgbouncer:6432/mydb",
    min_size=2, max_size=10,
    kwargs={"prepare_threshold": None},   # disable prepared stmts
)
"""


# ============================================================
# 5. MONITORING POOL STATS
# ============================================================
POOL_MONITORING = """
import psycopg2

# Connect to PgBouncer's special 'pgbouncer' database
conn = psycopg2.connect(
    "postgresql://pgbouncer_admin@pgbouncer:6432/pgbouncer"
)
cur = conn.cursor()

# 1. Pool health
cur.execute("SHOW POOLS")
for row in cur.fetchall():
    db, user, cl_active, cl_waiting, cl_active_cancel, cl_waiting_cancel, sv_active, sv_active_cancel, sv_being_canceled, sv_idle, sv_used, sv_tested, sv_login, maxwait, maxwait_us, pool_mode = row
    if cl_waiting > 0:
        print(f"⚠️  Pool {db}/{user}: {cl_waiting} clients waiting!")
    if maxwait > 1:
        print(f"⚠️  Pool {db}/{user}: max wait {maxwait}s")

# 2. Throughput
cur.execute("SHOW STATS")
# Returns: database, total_xact_count, total_query_count, total_received,
# total_sent, total_xact_time, total_query_time, total_wait_time, avg_*...

# 3. Active clients
cur.execute("SHOW CLIENTS")
# Returns each client connection state

# 4. Backend Postgres connections
cur.execute("SHOW SERVERS")
"""


# ============================================================
# 6. PROMETHEUS EXPORTER SETUP
# ============================================================
PROMETHEUS_EXPORTER = """
# Run pgbouncer_exporter
docker run -d --name pgbouncer-exporter \\
  -p 9127:9127 \\
  -e PGBOUNCER_EXPORTER_HOST=pgbouncer \\
  -e PGBOUNCER_EXPORTER_USER=pgbouncer_admin \\
  -e PGBOUNCER_EXPORTER_PASS=secret \\
  prometheuscommunity/pgbouncer-exporter

# prometheus.yml
scrape_configs:
  - job_name: pgbouncer
    static_configs:
      - targets: ['pgbouncer-exporter:9127']

# Key metrics:
# - pgbouncer_pools_client_waiting_connections
# - pgbouncer_pools_server_active_connections
# - pgbouncer_pools_max_wait_seconds
# - pgbouncer_stats_total_query_time
# - pgbouncer_stats_avg_query_time
"""


# ============================================================
# 7. PGCAT — Modern multi-threaded alternative
# ============================================================
PGCAT_CONFIG = """
# pgcat.toml (Rust-based, multi-threaded, HA)

[general]
host = "0.0.0.0"
port = 6432
worker_threads = 4
admin_username = "pgcat_admin"
admin_password = "secret"

[pools.mydb]
pool_mode = "transaction"
max_pool_size = 100

[pools.mydb.users.0]
username = "app_user"
password = "secret"

# Shard / Replica configuration
[pools.mydb.shards.0]
servers = [
    [ "primary.db", 5432, "primary" ],
    [ "replica1.db", 5432, "replica" ],
    [ "replica2.db", 5432, "replica" ],
]
database = "mydb"

# PgCat auto-routes SELECTs to replicas if you set:
# query_parser_enabled = true
"""


# ============================================================
# 8. TROUBLESHOOTING
# ============================================================
TROUBLESHOOTING = """
PROBLEM: "prepared statement 's1' does not exist"
CAUSE: TRANSACTION mode + ORM using prepared statements
FIX: Disable in driver:
  - asyncpg: statement_cache_size=0
  - psycopg3: prepare_threshold=None
  - psycopg2: doesn't use prepared by default ✓

PROBLEM: SQLAlchemy `session.connection().execution_options()` not persisting
CAUSE: TRANSACTION pool — different backend per tx
FIX: Use SET LOCAL inside transaction, not SET

PROBLEM: Advisory locks not working
CAUSE: Same conn not guaranteed across statements
FIX: Use row-level locks (SELECT ... FOR UPDATE) instead

PROBLEM: cl_waiting > 0 consistently
DIAGNOSE: SHOW POOLS → check sv_active vs default_pool_size
FIX:
  - Increase default_pool_size (if Postgres has capacity)
  - Add more PgBouncer instances + HAProxy
  - Optimize slow queries (free up backends faster)

PROBLEM: Postgres "too many connections"
DIAGNOSE: SELECT count(*) FROM pg_stat_activity
FIX:
  - Reduce default_pool_size
  - Make sure ALL apps go through PgBouncer
  - Set max_db_connections in PgBouncer

PROBLEM: Stale connections after PgBouncer restart
FIX:
  - Use pool_pre_ping=True in SQLAlchemy
  - Or set pool_recycle to lower value (e.g., 60s)
"""


# ============================================================
# 9. SIZING CALCULATOR
# ============================================================
def calculate_pool_sizing(
    app_pods: int,
    app_pool_size: int,
    avg_query_ms: int = 5,
    target_qps_per_pod: int = 1000,
):
    """Help calculate PgBouncer pool sizing."""
    total_client_conns = app_pods * app_pool_size
    # Little's Law: concurrent queries = qps × duration
    avg_concurrent_queries = (target_qps_per_pod * app_pods * avg_query_ms) / 1000
    pgbouncer_pool_size = int(avg_concurrent_queries * 1.5)  # 50% headroom

    print("=" * 60)
    print("PGBOUNCER SIZING CALCULATOR")
    print("=" * 60)
    print(f"  App pods                : {app_pods}")
    print(f"  Pool per app pod        : {app_pool_size}")
    print(f"  Total client conns      : {total_client_conns}")
    print(f"  Target QPS per pod      : {target_qps_per_pod}")
    print(f"  Avg query duration      : {avg_query_ms}ms")
    print(f"  Avg concurrent queries  : {avg_concurrent_queries:.0f}")
    print(f"  Recommended pool_size   : {pgbouncer_pool_size}")
    print(f"  Postgres max_connections: {pgbouncer_pool_size + 20}")
    print(f"  Multiplexing ratio      : {total_client_conns/pgbouncer_pool_size:.1f}x")


# ============================================================
# 10. FASTAPI APP HEALTH CHECK FOR PGBOUNCER
# ============================================================
FASTAPI_HEALTH = """
@app.get("/health/db")
async def db_health():
    try:
        async with engine.begin() as conn:
            # Test via PgBouncer
            r = await conn.execute(text("SELECT 1"))
            assert r.scalar() == 1
        # Optionally check PgBouncer admin
        async with admin_engine.begin() as conn:
            r = await conn.execute(text("SHOW POOLS"))
            pools = r.fetchall()
            issues = [p for p in pools if p.cl_waiting > 5 or p.maxwait > 1]
            if issues:
                return JSONResponse(
                    {"status": "degraded", "issues": str(issues)},
                    status_code=200
                )
        return {"status": "healthy"}
    except Exception as e:
        return JSONResponse({"status": "down", "error": str(e)}, 503)
"""


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("PGBOUNCER PRODUCTION SETUP")
    print("=" * 60)
    print("\n--- pgbouncer.ini ---")
    print(PGBOUNCER_INI)
    print("\n--- userlist.txt ---")
    print(USERLIST_TXT)
    print("\n--- docker-compose ---")
    print(DOCKER_COMPOSE)
    print("\n--- SQLAlchemy config ---")
    print(SQLALCHEMY_CONFIG)
    print("\n--- Monitoring ---")
    print(POOL_MONITORING)
    print("\n--- Prometheus ---")
    print(PROMETHEUS_EXPORTER)
    print("\n--- Troubleshooting ---")
    print(TROUBLESHOOTING)

    print()
    calculate_pool_sizing(app_pods=10, app_pool_size=20, avg_query_ms=5, target_qps_per_pod=500)
