# PgBouncer + Connection Pooling Deep Dive

> **Interview angle:** "Postgres me max_connections=200 hai. App ka pool_size=50 hai. 10 app instances run karte → 500 connections. Kya hoga?"
>
> Answer: Postgres crash. Solution: PgBouncer.

---

## 1. The Connection Problem

PostgreSQL is **expensive to connect to**:
- Each connection = separate Postgres process
- ~10 MB memory per process
- Forking overhead per new connection
- Default `max_connections = 100` (and increasing hurts)

### Math
- 10 app pods × 50 connection pool = 500 connections needed
- But Postgres allows max ~200 efficiently
- Most connections **idle** most of the time
- Wasted memory + CPU

**Solution: Connection pooler in front of Postgres.**

---

## 2. PgBouncer Architecture

```
App Instance 1 ┐
App Instance 2 ├──── PgBouncer ──── PostgreSQL
App Instance 3 │   (100s of conns)  (~50 actual)
App Instance N ┘
```

PgBouncer:
- Lightweight (single-threaded, written in C)
- Each PgBouncer can handle 10,000+ client connections
- Maps many client connections → few real Postgres connections
- Multiplexes queries

---

## 3. Three Pooling Modes

### Mode 1: SESSION Pooling (default, safest)
- Client gets a Postgres backend connection for **entire session**
- Returned to pool when client disconnects
- **No advantage over direct connections** beyond connection reuse
- Use for: ORMs that rely on prepared statements, session settings

### Mode 2: TRANSACTION Pooling (most common in production)
- Client gets a backend connection for **one transaction**
- Connection returned to pool on COMMIT/ROLLBACK
- High multiplexing — 1000s of clients on 50 backend conns
- **Limitations:**
  - No prepared statements (across transactions)
  - No session variables persisting
  - No advisory locks across transactions
  - No LISTEN/NOTIFY
  - No WITH HOLD cursors

### Mode 3: STATEMENT Pooling
- Connection returned after **every statement**
- Highest multiplexing
- Cannot do transactions! (only single-statement queries)
- Rarely used — for read-only analytics

### Decision Tree

| Need | Mode |
|---|---|
| Prepared statements | SESSION |
| ORM with session features | SESSION |
| High concurrency + simple queries | TRANSACTION |
| Read-only analytics | STATEMENT |

**Most apps: TRANSACTION pooling.**

---

## 4. Installation & Setup

### Install
```bash
sudo apt install pgbouncer
# OR docker
docker run -d -p 6432:6432 \
  -e POOL_MODE=transaction \
  -e DATABASES_HOST=postgres \
  edoburu/pgbouncer
```

### Config: `pgbouncer.ini`
```ini
[databases]
mydb = host=postgres-primary port=5432 dbname=mydb

[pgbouncer]
listen_port = 6432
listen_addr = *
auth_type = scram-sha-256
auth_file = /etc/pgbouncer/userlist.txt

# Pool config
pool_mode = transaction
max_client_conn = 10000        # max app connections
default_pool_size = 50         # backend conns per (user, db) pair
reserve_pool_size = 5          # extra for emergencies
reserve_pool_timeout = 3

# Timeouts
server_idle_timeout = 60       # close idle backend after 60s
server_lifetime = 3600         # recycle backend every hour
client_idle_timeout = 0        # 0 = no client timeout
query_timeout = 0              # query max duration

# Limits
max_db_connections = 100       # total connections to Postgres
max_user_connections = 50      # per-user limit

# Stats
stats_period = 60              # SHOW STATS resolution

# TLS
server_tls_sslmode = require
```

### `userlist.txt`
```
"app_user" "scram-sha-256$..."
```

Generate with:
```bash
psql -c "SELECT rolname, rolpassword FROM pg_authid WHERE rolname='app_user'"
```

---

## 5. App Configuration

App connects to **PgBouncer port (6432)** instead of Postgres directly (5432):

```python
# SQLAlchemy
engine = create_async_engine(
    "postgresql+asyncpg://user:pass@pgbouncer:6432/mydb",
    pool_size=20,        # SQLAlchemy's own pool (small)
    max_overflow=10,
    pool_timeout=30,
    pool_pre_ping=True,  # important with PgBouncer!
)
```

**Key insight:** SQLAlchemy pool is now redundant for most reqs but helps with overhead.

### Pool size math
- App pods × app_pool_size ≤ PgBouncer max_client_conn
- PgBouncer default_pool_size ≤ Postgres max_connections - reserved

---

## 6. PgBouncer Admin Interface

Connect to special `pgbouncer` database:
```bash
psql -h pgbouncer -p 6432 -U pgbouncer pgbouncer
```

```sql
SHOW POOLS;          -- per-database/user stats
SHOW DATABASES;      -- configured DBs
SHOW CLIENTS;        -- connected app clients
SHOW SERVERS;        -- backend Postgres connections
SHOW STATS;          -- throughput, latency
SHOW MEM;            -- memory usage
SHOW CONFIG;         -- current settings

RELOAD;              -- reload config
PAUSE mydb;          -- pause connections (maintenance)
RESUME mydb;
SHUTDOWN;
```

### SHOW POOLS output
```
 database | user     | cl_active | cl_waiting | sv_active | sv_idle | maxwait
----------+----------+-----------+------------+-----------+---------+--------
 mydb     | app_user |        45 |          2 |        48 |       2 |   0.05
```

- `cl_active` — clients with active query
- `cl_waiting` — clients waiting for backend (BAD if persistent)
- `sv_active` — backend conns running queries
- `sv_idle` — backend conns idle
- `maxwait` — longest client wait (alert if > 1s)

---

## 7. Common Issues + Fixes

### Issue 1: `cl_waiting > 0` consistently
Backend pool exhausted. Fix:
- Increase `default_pool_size`
- Reduce slow queries
- Add more PgBouncer instances

### Issue 2: Prepared statement error in transaction mode
```
ERROR: prepared statement "s1" does not exist
```
Asyncpg / psycopg uses prepared statements by default. Disable:
```python
engine = create_async_engine(
    url,
    connect_args={
        "statement_cache_size": 0,        # asyncpg
        "prepared_statement_cache_size": 0,
    }
)
```

### Issue 3: SET LOCAL not persisting
In TRANSACTION mode, `SET LOCAL` works (per-tx). `SET` (session-wide) doesn't.

### Issue 4: Advisory locks lost
Same connection not guaranteed across statements in TRANSACTION mode. Use row-level locks (`FOR UPDATE`) instead.

### Issue 5: LISTEN/NOTIFY doesn't work
Need persistent connection. Use SESSION mode or bypass PgBouncer for LISTEN.

### Issue 6: SSL handshake overhead
PgBouncer pools backend connections — handshake amortized. Use TLS to PgBouncer AND PgBouncer to Postgres.

---

## 8. Sizing PgBouncer

### Formula
- Each app pod: pool_size ~ 10-20
- App pods × pool_size = total client conns (e.g., 10 × 20 = 200)
- PgBouncer `default_pool_size`: 5-50 per (user, db) pair
- Postgres `max_connections`: PgBouncer pool × num_pgbouncers + buffer

### Example: 1000 req/s app
- 5 app pods × 20 pool = 100 client conns to PgBouncer
- PgBouncer transaction-mode → 30 backend conns sufficient
- Postgres max_connections = 50 (with buffer)

### Result
- Without PgBouncer: 100 Postgres connections (lots of overhead)
- With PgBouncer: 30 Postgres connections, app sees 100 — 70% reduction

---

## 9. PgBouncer HA

### Single PgBouncer = single point of failure!

### Solution: PgBouncer behind HAProxy
```
App → HAProxy → PgBouncer-1 ┐
              → PgBouncer-2 ├─ Postgres
              → PgBouncer-3 ┘
```

Or DNS round-robin if HAProxy too heavy.

### Modern alternative: PgCat
Rust-based, multi-threaded PgBouncer rewrite. Built-in HA + read/write split.

```toml
# pgcat.toml
[pools.mydb]
pool_mode = "transaction"

[pools.mydb.shards.0]
servers = [
    [ "primary.db", 5432, "primary" ],
    [ "replica.db", 5432, "replica" ],
]
```

---

## 10. Monitoring PgBouncer

### Prometheus exporter
```bash
docker run prometheuscommunity/pgbouncer-exporter
# Scrapes SHOW STATS / SHOW POOLS
```

### Key metrics
- `pgbouncer_show_pools_cl_waiting` — alert > 5
- `pgbouncer_show_stats_total_query_time` — slow queries
- `pgbouncer_show_pools_maxwait` — alert > 1s
- `pgbouncer_show_databases_pool_size` — pool capacity

---

## 11. SQLAlchemy + PgBouncer Best Practices

```python
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine(
    "postgresql+asyncpg://user:pass@pgbouncer:6432/mydb",

    # IMPORTANT: With TRANSACTION pool mode
    poolclass=NullPool,           # let PgBouncer handle pooling
    # OR small pool with pre-ping
    pool_size=5,
    pool_pre_ping=True,
    pool_recycle=300,

    # asyncpg: disable prepared statements
    connect_args={
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
        "server_settings": {
            "application_name": "my-api",
            "jit": "off",
        },
    },
)
```

### Why NullPool with PgBouncer?
- PgBouncer already pools connections
- SQLAlchemy pool just adds latency
- Each request gets fresh PgBouncer conn → high multiplexing
- Trade-off: more PgBouncer requests, less app memory

---

## 12. Alternatives to PgBouncer

| Tool | Pros | Cons |
|---|---|---|
| **PgBouncer** | Lightweight, battle-tested | Single-threaded |
| **PgCat** | Multi-threaded, HA built-in, read/write split | Newer, less mature |
| **Pgpool-II** | Load balancing, replication, parallel queries | Heavier, more complex |
| **Odyssey** | Multi-threaded, by Yandex | Less community |
| **Built-in (Postgres 14+)** | No extra hop | Limited features |
| **AWS RDS Proxy** | Managed, auto-failover | Cost, vendor lock-in |

**Default: PgBouncer transaction mode.** If you need multi-threaded → PgCat.

---

## 13. Cloud-Managed Pooling

### AWS RDS Proxy
```yaml
RDSProxy:
  Type: AWS::RDS::DBProxy
  Properties:
    DBProxyName: my-app-proxy
    EngineFamily: POSTGRESQL
    Auth:
      - AuthScheme: SECRETS
        SecretArn: !Ref DbSecret
    RoleArn: !Ref RDSProxyRole
    VpcSubnetIds: [...]
    MaxConnectionsPercent: 90
    MaxIdleConnectionsPercent: 50
```
- Auto-failover
- IAM auth
- TLS termination
- Cost: ~$0.015/hour per vCPU equivalent

### GCP CloudSQL Proxy
- Local auth proxy → no need to whitelist IPs
- TLS encryption automatic
- Use with PgBouncer for full pooling

---

## 14. Interview Questions

**Q1: PgBouncer kyu zaroori?**
Postgres connections expensive (process per conn, ~10MB RAM each). PgBouncer multiplexes 1000s of app conns → few Postgres conns. Saves memory + setup overhead.

**Q2: Three pool modes?**
- Session: conn per session (default, no multiplexing benefit)
- Transaction: conn per tx (most common, high multiplex)
- Statement: conn per query (no transactions, analytics-only)

**Q3: Transaction mode mein prepared statements kyu fail?**
Different connection per transaction. Prepared statement cached on old conn, gone when new tx starts.

**Q4: cl_waiting kya hai?**
Clients waiting for available backend conn. Persistent waiting = pool exhausted. Increase pool_size or reduce slow queries.

**Q5: PgBouncer HA?**
HAProxy in front, OR PgCat (built-in multi-instance), OR use AWS RDS Proxy.

**Q6: pool_size kaise calculate?**
- Postgres max_connections = N
- N - reserved (for admin) = available
- divided across PgBouncer instances
- ~50 backend conns can serve 1000 client conns at 1ms queries

**Q7: SQLAlchemy + PgBouncer with NullPool kyu?**
PgBouncer already pools. SQLAlchemy pool redundant. NullPool = direct connect to PgBouncer each request.

---

## 15. Best Practices

1. **Use TRANSACTION mode** unless prepared statements critical
2. **Disable SQLAlchemy/asyncpg prepared statements**
3. **Use NullPool in app** with PgBouncer
4. **Monitor cl_waiting + maxwait** — alert if persistent
5. **PgBouncer behind HAProxy** for HA
6. **server_idle_timeout=60** — release idle backends
7. **server_lifetime=3600** — recycle to avoid memory bloat
8. **Use SCRAM auth** not MD5 (Postgres 14+ default)
9. **TLS end-to-end** (app→PgBouncer→Postgres)
10. **Test failover** of PgBouncer regularly

---

## Related
- [[09_postgresql_ha_read_replicas]]
- [[13_postgresql_performance_tuning]]
- [[07_postgresql_internals]]
