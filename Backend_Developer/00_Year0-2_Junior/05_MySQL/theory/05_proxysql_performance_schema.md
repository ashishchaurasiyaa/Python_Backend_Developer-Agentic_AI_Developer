# MySQL ProxySQL + Performance Schema

> **Interview angle:** "MySQL ke saath read/write split + monitoring kaise?"

---

## 1. ProxySQL — What & Why

**ProxySQL** = high-performance SQL proxy for MySQL/MariaDB.

### Use cases
- **Read/write splitting** (writes to primary, reads to replicas)
- **Connection pooling** (1M client conns → few DB conns)
- **Query routing** (slow analytics → analytics replica)
- **Query caching** (cache SELECT results)
- **Failover** (auto-detect primary, route accordingly)
- **Query rewriting** (rewrite N+1 in legacy apps)
- **Multi-tenancy** (per-tenant DB routing)

Similar to PgBouncer for Postgres but MySQL-native + smarter.

---

## 2. Architecture

```
App → ProxySQL → MySQL Primary  (writes)
              ├→ MySQL Replica 1 (reads)
              ├→ MySQL Replica 2 (reads)
              └→ MySQL Analytics (heavy queries)
```

ProxySQL parses SQL → routes based on rules.

---

## 3. Setup

```bash
# Docker
docker run -d -p 6033:6033 -p 6032:6032 \
    -e MYSQL_ROOT_PASSWORD=root \
    proxysql/proxysql

# Admin port: 6032
# Client port: 6033
```

```bash
# Connect to admin
mysql -h 127.0.0.1 -P 6032 -uadmin -padmin

# Add backend MySQL servers
INSERT INTO mysql_servers(hostgroup_id, hostname, port) VALUES
    (10, 'mysql-primary', 3306),         -- write hostgroup
    (20, 'mysql-replica-1', 3306),       -- read hostgroup
    (20, 'mysql-replica-2', 3306);

-- Add users
INSERT INTO mysql_users(username, password, default_hostgroup) VALUES
    ('app', 'password', 10);

-- Save + apply
LOAD MYSQL SERVERS TO RUNTIME;
SAVE MYSQL SERVERS TO DISK;
LOAD MYSQL USERS TO RUNTIME;
SAVE MYSQL USERS TO DISK;
```

---

## 4. Read/Write Splitting

```sql
-- Query rules — route based on SQL pattern

-- SELECTs → reader hostgroup (20)
INSERT INTO mysql_query_rules
    (rule_id, active, match_digest, destination_hostgroup, apply)
VALUES
    (1, 1, '^SELECT.*', 20, 1);

-- INSERT/UPDATE/DELETE → writer hostgroup (10) — default
INSERT INTO mysql_query_rules
    (rule_id, active, match_digest, destination_hostgroup, apply)
VALUES
    (2, 1, '^(INSERT|UPDATE|DELETE).*', 10, 1);

-- Apply
LOAD MYSQL QUERY RULES TO RUNTIME;
SAVE MYSQL QUERY RULES TO DISK;
```

Now app code unchanged — proxy splits automatically.

### Manual override
```python
# Force write to read replica (rarely needed)
cursor.execute("/* hostgroup=20 */ SELECT ...")

# Bypass cache
cursor.execute("/* hostgroup=10 */ SELECT * FROM users WHERE id = ?", (user_id,))
```

---

## 5. Connection Pooling

```sql
-- Inspect pool
SELECT * FROM stats_mysql_connection_pool;

-- Settings (mysql_servers)
UPDATE mysql_servers SET
    max_connections = 1000,        -- to backend MySQL
    max_replication_lag = 5         -- exclude lagging replicas
WHERE hostgroup_id = 20;

LOAD MYSQL SERVERS TO RUNTIME;
```

### Why pooling matters
- App opens 10K client conns → ProxySQL multiplexes → only 100 backend MySQL conns
- Saves MySQL memory (each conn = ~10MB)

---

## 6. Query Caching

```sql
-- Cache SELECTs for 60s
UPDATE mysql_query_rules
    SET cache_ttl = 60000
WHERE rule_id = 1;

LOAD MYSQL QUERY RULES TO RUNTIME;

-- Stats
SELECT * FROM stats_mysql_query_digest
ORDER BY count_star DESC;
```

Trade-off: stale data possible. Best for slow-changing data (catalogs, configs).

---

## 7. Replication Lag Awareness

```sql
-- Auto-exclude replicas lagging > 5 sec
UPDATE mysql_servers SET max_replication_lag = 5;
LOAD MYSQL SERVERS TO RUNTIME;

-- ProxySQL polls SHOW SLAVE STATUS every monitor_read_only_interval
```

App reads from replica → if replica lags 10s → ProxySQL routes elsewhere.

---

## 8. Failover

ProxySQL detects backend failures:
```sql
SELECT * FROM mysql_servers;
-- status: ONLINE, OFFLINE_SOFT, OFFLINE_HARD, SHUNNED

-- Shunned = unreachable, traffic stops
-- Auto-recovery when reachable again
```

### Group replication / async replication
ProxySQL native support for:
- MySQL Group Replication
- MySQL InnoDB Cluster
- Galera Cluster
- Async master-slave

---

## 9. Monitoring & Stats

```sql
-- Top queries by count
SELECT digest_text, count_star, sum_time, avg_time
FROM stats_mysql_query_digest
ORDER BY count_star DESC LIMIT 10;

-- Top slow queries
SELECT digest_text, sum_time / 1000000 AS total_sec
FROM stats_mysql_query_digest
ORDER BY sum_time DESC LIMIT 10;

-- Connection pool
SELECT * FROM stats_mysql_connection_pool;

-- Backend health
SELECT * FROM mysql_servers;

-- Errors
SELECT * FROM stats_mysql_errors LIMIT 20;
```

### Prometheus exporter
```bash
docker run -d -p 9433:9433 \
    -e DATA_SOURCE_NAME='admin:admin@(proxysql:6032)/' \
    percona/proxysql_exporter
```

---

## 10. MySQL Performance Schema

Built-in MySQL feature for monitoring (must be enabled).

### Enable
```sql
-- In my.cnf
performance_schema = ON
performance_schema_consumer_events_statements_history_long = ON

-- Or runtime (not persistent)
SET GLOBAL performance_schema = ON;
```

### Useful views

```sql
-- Slow query analysis
SELECT
    digest_text,
    count_star AS execs,
    avg_timer_wait/1e9 AS avg_ms,
    max_timer_wait/1e9 AS max_ms,
    sum_rows_examined AS rows_examined,
    sum_rows_sent AS rows_returned
FROM performance_schema.events_statements_summary_by_digest
ORDER BY avg_timer_wait DESC
LIMIT 10;

-- Index usage
SELECT
    object_schema, object_name, index_name,
    count_read, count_write, count_insert
FROM performance_schema.table_io_waits_summary_by_index_usage
WHERE object_schema = 'mydb'
ORDER BY count_read DESC;

-- Connection state
SELECT
    user, host, db, command, time, state, info
FROM information_schema.processlist
WHERE command != 'Sleep';

-- Lock waits
SELECT
    object_schema, object_name, lock_type, lock_status,
    blocking_pid, blocked_pid
FROM performance_schema.data_locks;

-- Wait events
SELECT event_name, count_star, sum_timer_wait/1e9 AS total_ms
FROM performance_schema.events_waits_summary_global_by_event_name
WHERE event_name LIKE 'wait/io/%'
ORDER BY total_ms DESC LIMIT 10;
```

---

## 11. sys Schema (built on Performance Schema)

Easier-to-use views:

```sql
-- Slowest queries
SELECT * FROM sys.statements_with_runtimes_in_95th_percentile;

-- Unused indexes
SELECT * FROM sys.schema_unused_indexes;

-- Indexes with high fragmentation
SELECT * FROM sys.schema_index_statistics;

-- Slow IO
SELECT * FROM sys.io_global_by_file_by_latency;

-- Memory usage by user
SELECT * FROM sys.memory_by_user_by_current_bytes;
```

---

## 12. EXPLAIN ANALYZE (MySQL 8+)

```sql
EXPLAIN ANALYZE
SELECT * FROM orders WHERE user_id = 42;

-- Output shows actual execution:
-- -> Index lookup on orders using idx_user_id (user_id=42)
--    (actual time=0.012..0.045 rows=8 loops=1)
```

vs old `EXPLAIN` shows estimates only.

---

## 13. Optimization Workflow

```
1. Enable slow query log
   SET GLOBAL slow_query_log = ON;
   SET GLOBAL long_query_time = 1;  -- log queries > 1s

2. Analyze via pt-query-digest
   pt-query-digest /var/log/mysql/slow.log

3. EXPLAIN ANALYZE each slow query
   - Full table scan? → add index
   - Wrong index? → composite index
   - Hash join? → consider denormalization

4. Performance Schema for live diagnostics
   - sys.statements_with_runtimes_in_95th_percentile
   - sys.schema_index_statistics

5. Verify with benchmark
```

---

## 14. ProxySQL Query Rewriting

Useful for legacy code:
```sql
-- Rewrite N+1 query pattern
INSERT INTO mysql_query_rules
    (rule_id, active, match_pattern, replace_pattern, apply)
VALUES
    (10, 1, 'SELECT \* FROM orders WHERE user_id = (\d+)',
            'SELECT * FROM orders WHERE user_id IN (SELECT id FROM users WHERE id = \\1)',
            1);

LOAD MYSQL QUERY RULES TO RUNTIME;
```

Or block dangerous queries:
```sql
-- Block DELETE without WHERE
INSERT INTO mysql_query_rules
    (rule_id, match_pattern, error_msg, apply)
VALUES
    (20, '^DELETE FROM \w+ ;', 'DELETE without WHERE blocked', 1);
```

---

## 15. SSL/TLS

```sql
-- Client → ProxySQL SSL
SET mysql-have_ssl = 'true';
SET mysql-ssl_p2s_ca = '/path/to/ca.pem';
SET mysql-ssl_p2s_cert = '/path/to/cert.pem';
SET mysql-ssl_p2s_key = '/path/to/key.pem';
LOAD MYSQL VARIABLES TO RUNTIME;
SAVE MYSQL VARIABLES TO DISK;

-- ProxySQL → MySQL SSL (in mysql_servers)
UPDATE mysql_servers SET use_ssl = 1;
LOAD MYSQL SERVERS TO RUNTIME;
```

---

## 16. Python Integration

```python
import mysql.connector

# Just point at ProxySQL — app unchanged
conn = mysql.connector.connect(
    host="proxysql",      # not direct MySQL!
    port=6033,
    user="app",
    password="password",
    database="mydb",
)

cursor = conn.cursor()

# Normal queries — ProxySQL routes automatically
cursor.execute("SELECT * FROM users WHERE id = %s", (42,))   # → replica
cursor.execute("INSERT INTO orders VALUES (%s, %s)", (1, 100))  # → primary

# Manual hint (force read from primary, e.g., after just-written data)
cursor.execute("/* hostgroup=10 */ SELECT * FROM users WHERE id = %s", (42,))
```

---

## 17. SQLAlchemy + ProxySQL

```python
from sqlalchemy import create_engine

# Single engine — ProxySQL handles routing
engine = create_engine(
    "mysql+pymysql://app:password@proxysql:6033/mydb",
    pool_size=20,
    pool_pre_ping=True,
)

# Or separate engines for explicit control
write_engine = create_engine("mysql+pymysql://app:password@proxysql:6033/mydb"
                              "?hostgroup=10")
read_engine = create_engine("mysql+pymysql://app:password@proxysql:6033/mydb"
                             "?hostgroup=20")
```

---

## 18. Best Practices

1. **ProxySQL for any multi-replica setup**
2. **Connection pool sized for backend MySQL capacity**
3. **Query rules tested in staging first**
4. **Enable replication lag check** (max_replication_lag)
5. **Monitor stats_mysql_query_digest** for slow queries
6. **Performance Schema in production** (low overhead)
7. **sys schema** for quick diagnostics
8. **pt-query-digest** for slow log analysis
9. **EXPLAIN ANALYZE** every slow query
10. **High availability** for ProxySQL itself (cluster mode)

---

## 19. Interview Questions

**Q1: ProxySQL kya?**
SQL-aware proxy for MySQL. Connection pool, read/write split, query routing, caching, failover.

**Q2: Read/write split kaise?**
Query rules with regex on SQL → hostgroup. SELECTs → readers, writes → primary.

**Q3: vs HAProxy?**
HAProxy = generic TCP proxy. ProxySQL = SQL-aware (parses queries, routes intelligently, caches).

**Q4: Replication lag handle?**
ProxySQL polls replicas. If lag > max_replication_lag, excludes from read pool.

**Q5: Performance Schema vs Slow Query Log?**
PS = real-time, sampled. SQL = log all slow queries. Both useful.

**Q6: Performance Schema overhead?**
~5-10% in production. Selective consumers if too heavy.

**Q7: ProxySQL HA?**
Cluster mode (2+ ProxySQL nodes), or active-passive with keepalived.

---

## 20. Related
- [[01_basics_installation_crud]]
- [[02_joins_indexes_transactions]]
- [[03_advanced_optimization]]
- [[../../00_Year0-2_Junior/04_Database_SQL/11_pgbouncer_connection_pooling]]
