"""
============================================================
PROXYSQL + MYSQL PERFORMANCE SCHEMA — Practical
============================================================
Setup:
    docker-compose up   (see below for config)

ProxySQL admin: mysql -h 127.0.0.1 -P 6032 -uadmin -padmin
Client port:    mysql -h 127.0.0.1 -P 6033 -uapp   -ppassword
"""


# ============================================================
# 1. DOCKER COMPOSE
# ============================================================
DOCKER_COMPOSE = """
# docker-compose.yml

version: '3'
services:
  mysql-primary:
    image: mysql:8
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: mydb
    command: --server-id=1 --log-bin=mysql-bin --binlog-format=ROW
    ports: ["3306:3306"]

  mysql-replica-1:
    image: mysql:8
    environment:
      MYSQL_ROOT_PASSWORD: root
    command: --server-id=2 --relay-log=relay-bin --read-only=ON
    depends_on: [mysql-primary]

  mysql-replica-2:
    image: mysql:8
    environment:
      MYSQL_ROOT_PASSWORD: root
    command: --server-id=3 --relay-log=relay-bin --read-only=ON
    depends_on: [mysql-primary]

  proxysql:
    image: proxysql/proxysql:latest
    ports:
      - "6032:6032"   # admin
      - "6033:6033"   # client
    depends_on:
      - mysql-primary
      - mysql-replica-1
      - mysql-replica-2

# Setup replication manually after start (production: use orchestrator)
"""


# ============================================================
# 2. PROXYSQL CONFIGURATION
# ============================================================
PROXYSQL_CONFIG = """
-- Connect to admin: mysql -h 127.0.0.1 -P 6032 -uadmin -padmin

-- ===== ADD BACKEND SERVERS =====
INSERT INTO mysql_servers (hostgroup_id, hostname, port, weight, max_connections, max_replication_lag) VALUES
    (10, 'mysql-primary',   3306, 1000, 1000, 0),       -- writer
    (20, 'mysql-replica-1', 3306, 1000, 1000, 5),       -- reader, lag tolerance 5s
    (20, 'mysql-replica-2', 3306, 1000, 1000, 5);

-- Apply
LOAD MYSQL SERVERS TO RUNTIME;
SAVE MYSQL SERVERS TO DISK;

-- ===== ADD USER =====
INSERT INTO mysql_users (username, password, default_hostgroup, transaction_persistent, max_connections) VALUES
    ('app', 'password', 10, 1, 10000);

LOAD MYSQL USERS TO RUNTIME;
SAVE MYSQL USERS TO DISK;

-- ===== QUERY ROUTING RULES =====
-- SELECTs → read hostgroup (20)
INSERT INTO mysql_query_rules (rule_id, active, match_digest, destination_hostgroup, apply, cache_ttl) VALUES
    (10, 1, '^SELECT.*FOR UPDATE.*', 10, 1, 0),        -- SELECT FOR UPDATE → primary
    (20, 1, '^SELECT.*', 20, 1, 0);                    -- regular SELECT → replica

-- Writes → primary (default_hostgroup)
INSERT INTO mysql_query_rules (rule_id, active, match_digest, destination_hostgroup, apply) VALUES
    (30, 1, '^(INSERT|UPDATE|DELETE|REPLACE|CREATE|ALTER|DROP|TRUNCATE).*', 10, 1);

-- Apply rules
LOAD MYSQL QUERY RULES TO RUNTIME;
SAVE MYSQL QUERY RULES TO DISK;

-- ===== QUERY CACHING =====
-- Cache catalog queries for 60 seconds
INSERT INTO mysql_query_rules (rule_id, active, match_digest, cache_ttl, apply) VALUES
    (40, 1, '^SELECT \\* FROM catalog WHERE active = 1', 60000, 1);

LOAD MYSQL QUERY RULES TO RUNTIME;
SAVE MYSQL QUERY RULES TO DISK;

-- ===== REPLICATION-AWARE GROUPS =====
-- Set up master-slave replication awareness
INSERT INTO mysql_replication_hostgroups (writer_hostgroup, reader_hostgroup) VALUES
    (10, 20);

LOAD MYSQL SERVERS TO RUNTIME;
"""


# ============================================================
# 3. MONITORING QUERIES (ProxySQL Admin)
# ============================================================
PROXYSQL_MONITORING = """
-- ===== TOP QUERIES BY COUNT =====
SELECT
    digest_text,
    count_star AS execs,
    ROUND(sum_time / 1000000, 2) AS total_sec,
    ROUND(sum_time / count_star / 1000, 2) AS avg_ms
FROM stats_mysql_query_digest
ORDER BY count_star DESC
LIMIT 10;

-- ===== SLOWEST QUERIES =====
SELECT
    digest_text,
    count_star,
    ROUND(sum_time / count_star / 1000, 2) AS avg_ms
FROM stats_mysql_query_digest
ORDER BY avg_ms DESC
LIMIT 10;

-- ===== BACKEND HEALTH =====
SELECT * FROM mysql_servers;
-- status: ONLINE / SHUNNED / OFFLINE_SOFT / OFFLINE_HARD

-- ===== CONNECTION POOL =====
SELECT
    hostgroup,
    srv_host,
    status,
    ConnUsed,
    ConnFree,
    Queries,
    Bytes_data_sent,
    Latency_us
FROM stats_mysql_connection_pool;

-- ===== REPLICATION LAG STATUS =====
SELECT * FROM mysql_replication_hostgroups;

-- ===== ERROR LOG =====
SELECT * FROM stats_mysql_errors LIMIT 20;

-- ===== CACHE HIT RATE =====
SELECT
    Queries,
    QPS_Cache_Hits,
    QPS_Cache_Hits * 100 / Queries AS cache_hit_pct
FROM stats_mysql_global;

-- ===== USER STATS =====
SELECT * FROM stats_mysql_users;

-- ===== RESET STATS =====
SELECT * FROM stats_mysql_query_digest_reset;
"""


# ============================================================
# 4. MYSQL PERFORMANCE SCHEMA
# ============================================================
PERFORMANCE_SCHEMA = """
-- ===== ENABLE (in my.cnf) =====
-- performance_schema = ON
-- performance_schema_consumer_events_statements_history_long = ON
-- performance_schema_consumer_events_waits_history_long = ON

-- ===== TOP SLOW STATEMENTS =====
SELECT
    digest_text,
    count_star AS execs,
    ROUND(avg_timer_wait / 1000000000, 2) AS avg_ms,
    ROUND(max_timer_wait / 1000000000, 2) AS max_ms,
    sum_rows_examined,
    sum_rows_sent,
    ROUND(sum_rows_examined / count_star) AS avg_rows_examined
FROM performance_schema.events_statements_summary_by_digest
WHERE schema_name = 'mydb'
ORDER BY avg_timer_wait DESC
LIMIT 10;

-- ===== INDEX USAGE =====
SELECT
    object_schema,
    object_name AS table_name,
    index_name,
    count_read AS reads,
    count_write AS writes,
    count_fetch AS lookups
FROM performance_schema.table_io_waits_summary_by_index_usage
WHERE object_schema = 'mydb'
  AND index_name IS NOT NULL
ORDER BY count_read DESC;

-- ===== UNUSED INDEXES =====
SELECT
    object_schema,
    object_name,
    index_name
FROM performance_schema.table_io_waits_summary_by_index_usage
WHERE object_schema = 'mydb'
  AND index_name IS NOT NULL
  AND index_name != 'PRIMARY'
  AND count_star = 0;

-- ===== ACTIVE LONG-RUNNING QUERIES =====
SELECT
    pid,
    user,
    host,
    db,
    command,
    time AS seconds_running,
    state,
    info AS query
FROM information_schema.processlist
WHERE command != 'Sleep'
  AND time > 5
ORDER BY time DESC;

-- ===== LOCK CONTENTION =====
SELECT
    object_schema,
    object_name,
    lock_type,
    lock_status,
    owner_thread_id
FROM performance_schema.metadata_locks
WHERE owner_event_id IS NOT NULL;

-- ===== INNODB BUFFER POOL =====
SELECT
    POOL_ID,
    POOL_SIZE,
    FREE_BUFFERS,
    DATABASE_PAGES,
    PAGES_MADE_YOUNG,
    PAGES_MADE_NOT_YOUNG
FROM information_schema.INNODB_BUFFER_POOL_STATS;
"""


# ============================================================
# 5. SYS SCHEMA (easier views)
# ============================================================
SYS_SCHEMA = """
-- ===== STATEMENTS IN 95TH PERCENTILE =====
SELECT * FROM sys.statements_with_runtimes_in_95th_percentile;

-- ===== UNUSED INDEXES =====
SELECT * FROM sys.schema_unused_indexes;

-- ===== TABLE SIZES =====
SELECT
    table_schema, table_name,
    ROUND(data_length / 1024 / 1024, 2) AS data_mb,
    ROUND(index_length / 1024 / 1024, 2) AS index_mb
FROM information_schema.tables
WHERE table_schema = 'mydb'
ORDER BY data_length DESC;

-- ===== SLOW IO =====
SELECT * FROM sys.io_global_by_file_by_latency LIMIT 10;

-- ===== INDEX EFFICIENCY =====
SELECT * FROM sys.schema_index_statistics
WHERE table_schema = 'mydb'
ORDER BY rows_selected DESC;

-- ===== TOP HOSTS BY CONNECTIONS =====
SELECT * FROM sys.host_summary;

-- ===== TOP USERS =====
SELECT * FROM sys.user_summary;

-- ===== MEMORY USAGE =====
SELECT * FROM sys.memory_global_by_current_bytes
ORDER BY current_bytes DESC LIMIT 10;
"""


# ============================================================
# 6. EXPLAIN ANALYZE (MySQL 8+)
# ============================================================
EXPLAIN_ANALYZE = """
-- EXPLAIN ANALYZE — runs the query, shows actual times
EXPLAIN ANALYZE
SELECT u.name, COUNT(o.id) AS order_count
FROM users u
LEFT JOIN orders o ON u.id = o.user_id
WHERE u.created_at > '2024-01-01'
GROUP BY u.id
HAVING order_count > 5;

-- Output:
-- -> Filter: (count(o.id) > 5)
--    (actual time=0.123..0.456 rows=5 loops=1)
--   -> Aggregate using temporary table
--      (actual time=0.100..0.450 rows=10 loops=1)
--     -> Left hash join (no condition)
--        (actual time=0.05..0.40 rows=200 loops=1)
--       ...

-- Key things to look at:
-- 1. "Full table scan" → missing index
-- 2. "rows examined" >> "rows returned" → bad index
-- 3. "using temporary" → may indicate sort/group issue
-- 4. "using filesort" → ORDER BY without index
"""


# ============================================================
# 7. SLOW QUERY LOG + PT-QUERY-DIGEST
# ============================================================
SLOW_LOG_ANALYSIS = """
# Enable slow query log
mysql> SET GLOBAL slow_query_log = ON;
mysql> SET GLOBAL slow_query_log_file = '/var/log/mysql/slow.log';
mysql> SET GLOBAL long_query_time = 0.5;   -- 500ms
mysql> SET GLOBAL log_queries_not_using_indexes = ON;

# Analyze with pt-query-digest (Percona Toolkit)
pt-query-digest /var/log/mysql/slow.log > slow-report.txt

# Output sample:
# # Profile
# # Rank Query ID                            Response time   Calls
# #    1 0xABC...                            45.5%  120.5s  1500 queries
# #    2 0xDEF...                            22.3%  59.1s    300
# #    3 0x...                                ...

# Each query has:
# - Total/avg/min/max time
# - Sample query text
# - Histogram of execution times
# - EXPLAIN suggestion
"""


# ============================================================
# 8. PYTHON: USING PROXYSQL
# ============================================================
PYTHON_WITH_PROXYSQL = '''
import mysql.connector

# App connects to ProxySQL (port 6033), not directly to MySQL
conn = mysql.connector.connect(
    host="proxysql",       # ProxySQL endpoint
    port=6033,
    user="app",
    password="password",
    database="mydb",
    pool_name="app_pool",
    pool_size=20,
)

cursor = conn.cursor(dictionary=True)

# ===== WRITES routed to primary automatically =====
cursor.execute("INSERT INTO orders (user_id, amount) VALUES (%s, %s)", (42, 100))
conn.commit()

# ===== READS routed to replica =====
cursor.execute("SELECT * FROM orders WHERE user_id = %s", (42,))
results = cursor.fetchall()

# ===== FORCE READ FROM PRIMARY =====
# Useful right after write (read your own writes)
cursor.execute("/* hostgroup=10 */ SELECT * FROM orders WHERE user_id = %s", (42,))

# ===== TRANSACTION (always on primary) =====
conn.start_transaction()
try:
    cursor.execute("UPDATE accounts SET balance = balance - 100 WHERE id = 1")
    cursor.execute("UPDATE accounts SET balance = balance + 100 WHERE id = 2")
    conn.commit()
except:
    conn.rollback()
    raise


# ===== SQLALCHEMY =====
from sqlalchemy import create_engine
engine = create_engine(
    "mysql+pymysql://app:password@proxysql:6033/mydb",
    pool_size=20,
    pool_pre_ping=True,
)
'''


# ============================================================
# 9. PROXYSQL HA (CLUSTER MODE)
# ============================================================
HA_SETUP = """
-- ===== PROXYSQL CLUSTER (multiple ProxySQL nodes for HA) =====
-- On each ProxySQL node:

INSERT INTO proxysql_servers (hostname, port, weight) VALUES
    ('proxysql-1', 6032, 1),
    ('proxysql-2', 6032, 1),
    ('proxysql-3', 6032, 1);

LOAD PROXYSQL SERVERS TO RUNTIME;
SAVE PROXYSQL SERVERS TO DISK;

-- Set sync variables
SET admin-cluster_username = 'cluster_user';
SET admin-cluster_password = 'cluster_pass';
SET admin-cluster_check_interval_ms = 200;
LOAD ADMIN VARIABLES TO RUNTIME;
SAVE ADMIN VARIABLES TO DISK;

-- Each node syncs config from primary
-- Apps connect via keepalived VIP or load balancer
"""


# ============================================================
# 10. COMMON OPTIMIZATIONS
# ============================================================
OPTIMIZATIONS = """
-- ===== MYSQL CONFIG (my.cnf) for write-heavy =====
[mysqld]
innodb_buffer_pool_size = 16G       # 60-80% of RAM
innodb_log_file_size = 2G
innodb_flush_log_at_trx_commit = 2  # 1 = safest, 2 = faster
innodb_flush_method = O_DIRECT
innodb_io_capacity = 2000
innodb_io_capacity_max = 4000

max_connections = 200               # use ProxySQL beyond
table_open_cache = 4000
query_cache_size = 0                # disable (deprecated)

slow_query_log = ON
long_query_time = 1
log_queries_not_using_indexes = ON

-- For read-heavy with many concurrent
thread_cache_size = 100
thread_pool_size = 16

-- ===== INDEX OPTIMIZATION =====
-- Composite index for most common WHERE + ORDER BY
CREATE INDEX idx_user_status_date ON orders (user_id, status, created_at DESC);

-- Covering index (avoid table lookup)
CREATE INDEX idx_covering ON orders (user_id, status, amount, id);

-- Index hints (rarely needed)
SELECT * FROM orders USE INDEX (idx_user_id) WHERE user_id = 42;
"""


# ============================================================
# 11. FASTAPI + PROXYSQL
# ============================================================
FASTAPI_INTEGRATION = '''
from fastapi import FastAPI, Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

app = FastAPI()

# Single engine — ProxySQL handles routing
engine = create_engine(
    "mysql+pymysql://app:password@proxysql:6033/mydb",
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine)


@app.get("/users/{user_id}")
async def get_user(user_id: int):
    # ProxySQL routes SELECT to replica
    with SessionLocal() as session:
        return session.execute("SELECT * FROM users WHERE id = :id", {"id": user_id}).first()


@app.post("/users")
async def create_user(user: UserCreate):
    # ProxySQL routes INSERT to primary
    with SessionLocal() as session:
        session.execute(
            "INSERT INTO users (name, email) VALUES (:n, :e)",
            {"n": user.name, "e": user.email}
        )
        session.commit()


# Force primary read (after write — replication lag scenario)
@app.get("/users/{user_id}/me")
async def get_self(user_id: int):
    with SessionLocal() as session:
        # Hint: read from primary (hostgroup 10)
        return session.execute(
            "/* hostgroup=10 */ SELECT * FROM users WHERE id = :id",
            {"id": user_id}
        ).first()
'''


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("PROXYSQL + MYSQL PERFORMANCE SCHEMA")
    print("=" * 60)

    print("\n--- DOCKER COMPOSE ---")
    print(DOCKER_COMPOSE)
    print("\n--- PROXYSQL CONFIG ---")
    print(PROXYSQL_CONFIG)
    print("\n--- PROXYSQL MONITORING ---")
    print(PROXYSQL_MONITORING)
    print("\n--- MYSQL PERFORMANCE SCHEMA ---")
    print(PERFORMANCE_SCHEMA)
    print("\n--- SYS SCHEMA ---")
    print(SYS_SCHEMA)
    print("\n--- EXPLAIN ANALYZE ---")
    print(EXPLAIN_ANALYZE)
    print("\n--- SLOW LOG ANALYSIS ---")
    print(SLOW_LOG_ANALYSIS)
    print("\n--- PYTHON WITH PROXYSQL ---")
    print(PYTHON_WITH_PROXYSQL)
    print("\n--- HA SETUP ---")
    print(HA_SETUP)
    print("\n--- OPTIMIZATIONS ---")
    print(OPTIMIZATIONS)
    print("\n--- FASTAPI INTEGRATION ---")
    print(FASTAPI_INTEGRATION)
