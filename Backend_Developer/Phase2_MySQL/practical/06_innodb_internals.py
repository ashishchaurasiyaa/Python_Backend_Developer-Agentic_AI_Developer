"""
InnoDB Internals — Monitoring + Tuning Patterns
"""

import mysql.connector


# ==========================================================================
# 1. BUFFER POOL MONITORING
# ==========================================================================

def buffer_pool_stats(conn):
    cursor = conn.cursor(dictionary=True)

    # Hit ratio
    cursor.execute("""
        SELECT
            (1 - reads.value / read_req.value) * 100 AS hit_ratio_pct,
            reads.value AS disk_reads,
            read_req.value AS read_requests
        FROM information_schema.global_status reads
        JOIN information_schema.global_status read_req
        ON reads.variable_name = 'Innodb_buffer_pool_reads'
        AND read_req.variable_name = 'Innodb_buffer_pool_read_requests'
    """)
    print(cursor.fetchone())

    # Buffer pool size + usage
    cursor.execute("""
        SELECT variable_name, variable_value
        FROM information_schema.global_status
        WHERE variable_name IN (
            'Innodb_buffer_pool_pages_total',
            'Innodb_buffer_pool_pages_data',
            'Innodb_buffer_pool_pages_dirty',
            'Innodb_buffer_pool_pages_free',
            'Innodb_buffer_pool_bytes_data',
            'Innodb_buffer_pool_bytes_dirty'
        )
    """)
    for row in cursor.fetchall():
        print(row)


# ==========================================================================
# 2. INNODB STATUS
# ==========================================================================

def innodb_status(conn):
    cursor = conn.cursor()
    cursor.execute("SHOW ENGINE INNODB STATUS")
    status = cursor.fetchone()[2]
    # Parse interesting sections
    sections = status.split('-' * 70)
    for s in sections:
        if 'LATEST DETECTED DEADLOCK' in s:
            print("DEADLOCK INFO:")
            print(s)
        elif 'TRANSACTIONS' in s:
            print("TRANSACTIONS:")
            # ... parse history list length, active transactions
        elif 'BUFFER POOL' in s:
            print("BUFFER POOL:")
            # ... parse hit rates


# ==========================================================================
# 3. LONG-RUNNING TRANSACTIONS
# ==========================================================================

def long_running_transactions(conn, threshold_seconds=60):
    cursor = conn.cursor(dictionary=True)
    cursor.execute(f"""
        SELECT
            trx_id,
            trx_started,
            TIMESTAMPDIFF(SECOND, trx_started, NOW()) AS age_seconds,
            trx_query,
            trx_isolation_level,
            trx_rows_modified,
            trx_mysql_thread_id
        FROM information_schema.innodb_trx
        WHERE TIMESTAMPDIFF(SECOND, trx_started, NOW()) > %s
        ORDER BY trx_started ASC
    """, (threshold_seconds,))

    for row in cursor.fetchall():
        print(f"Txn {row['trx_id']}: {row['age_seconds']}s old, query: {row['trx_query'][:200]}")
        if row['age_seconds'] > 3600:
            print(f"  ALERT: 1+ hour old txn — consider killing thread {row['trx_mysql_thread_id']}")


def kill_long_transaction(conn, thread_id):
    cursor = conn.cursor()
    cursor.execute(f"KILL {thread_id}")


# ==========================================================================
# 4. UNDO + PURGE STATUS
# ==========================================================================

def undo_status(conn):
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            variable_name, variable_value
        FROM performance_schema.global_status
        WHERE variable_name IN (
            'Innodb_history_list_length',
            'Innodb_undo_log_segments',
            'Innodb_pages_dirty'
        )
    """)
    for row in cursor.fetchall():
        print(row)

    # History list length > 1M = purge falling behind
    cursor.execute("""
        SELECT variable_value
        FROM performance_schema.global_status
        WHERE variable_name = 'Innodb_history_list_length'
    """)
    history = int(cursor.fetchone()['variable_value'])
    if history > 1_000_000:
        print(f"ALERT: history list = {history:,} — purge falling behind")


# ==========================================================================
# 5. LOCK CONTENTION
# ==========================================================================

def show_waiting_locks(conn):
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT
            waiting.trx_id AS waiting_trx,
            waiting.trx_query AS waiting_query,
            waiting.trx_started AS waiting_started,
            blocking.trx_id AS blocking_trx,
            blocking.trx_query AS blocking_query,
            blocking.trx_started AS blocking_started
        FROM performance_schema.data_lock_waits dl
        JOIN information_schema.innodb_trx waiting
            ON waiting.trx_id = dl.REQUESTING_ENGINE_TRANSACTION_ID
        JOIN information_schema.innodb_trx blocking
            ON blocking.trx_id = dl.BLOCKING_ENGINE_TRANSACTION_ID
    """)
    for row in cursor.fetchall():
        print(row)


# ==========================================================================
# 6. ENGINE / PERFORMANCE SCHEMA QUERIES
# ==========================================================================

PERF_SCHEMA_QUERIES = """
-- Top 10 slowest queries (need performance_schema enabled)
SELECT
    schema_name,
    DIGEST_TEXT,
    COUNT_STAR AS exec_count,
    AVG_TIMER_WAIT / 1e9 AS avg_ms,
    SUM_TIMER_WAIT / 1e9 AS total_ms,
    SUM_ROWS_EXAMINED,
    SUM_ROWS_SENT
FROM performance_schema.events_statements_summary_by_digest
ORDER BY SUM_TIMER_WAIT DESC
LIMIT 10;


-- Tables with most lock waits
SELECT
    object_schema,
    object_name,
    count_read_with_shared_locks,
    count_write_with_exclusive_locks,
    count_read_lock_no_wait,
    count_write_lock_no_wait
FROM performance_schema.table_lock_waits_summary_by_table
ORDER BY count_write_with_exclusive_locks DESC
LIMIT 20;


-- Index usage stats
SELECT
    object_schema,
    object_name,
    index_name,
    count_read,
    count_write
FROM performance_schema.table_io_waits_summary_by_index_usage
ORDER BY count_read DESC
LIMIT 20;


-- Unused indexes (count_read = 0)
SELECT
    object_schema, object_name, index_name
FROM performance_schema.table_io_waits_summary_by_index_usage
WHERE count_read = 0 AND index_name IS NOT NULL AND index_name <> 'PRIMARY';
"""


# ==========================================================================
# 7. TABLE-LEVEL INSPECTION
# ==========================================================================

def table_info(conn, schema, table):
    cursor = conn.cursor(dictionary=True)
    cursor.execute(f"""
        SELECT
            TABLE_NAME, ENGINE, ROW_FORMAT,
            TABLE_ROWS, AVG_ROW_LENGTH,
            DATA_LENGTH, INDEX_LENGTH,
            DATA_FREE
        FROM information_schema.tables
        WHERE table_schema = '{schema}' AND table_name = '{table}'
    """)
    print(cursor.fetchone())


def check_table_fragmentation(conn, schema):
    """High DATA_FREE relative to DATA_LENGTH = fragmented."""
    cursor = conn.cursor(dictionary=True)
    cursor.execute(f"""
        SELECT
            TABLE_NAME,
            ENGINE,
            DATA_LENGTH,
            DATA_FREE,
            DATA_FREE / NULLIF(DATA_LENGTH, 0) * 100 AS frag_pct
        FROM information_schema.tables
        WHERE table_schema = '{schema}'
          AND DATA_FREE > 100 * 1024 * 1024  -- > 100MB free
        ORDER BY DATA_FREE DESC
        LIMIT 20
    """)
    for row in cursor.fetchall():
        if row['frag_pct'] and row['frag_pct'] > 30:
            print(f"{row['TABLE_NAME']}: {row['frag_pct']:.1f}% fragmented")


def defrag_table(conn, schema, table):
    """OPTIMIZE TABLE — defragment + recover space."""
    cursor = conn.cursor()
    cursor.execute(f"OPTIMIZE TABLE {schema}.{table}")
    for r in cursor.fetchall():
        print(r)


# ==========================================================================
# 8. CONFIGURATION TUNING
# ==========================================================================

PROD_INNODB_CONFIG = """
# my.cnf

[mysqld]

# Buffer pool — 50-70% of RAM
innodb_buffer_pool_size = 24G
innodb_buffer_pool_instances = 8
innodb_old_blocks_pct = 37
innodb_old_blocks_time = 1000

# Redo log
innodb_log_file_size = 4G
innodb_log_files_in_group = 2
innodb_log_buffer_size = 128M
innodb_flush_log_at_trx_commit = 1    # ACID; 2 for ~1s loss tolerance

# I/O for SSD
innodb_io_capacity = 2000
innodb_io_capacity_max = 4000
innodb_flush_neighbors = 0
innodb_random_read_ahead = OFF
innodb_read_ahead_threshold = 56

# Concurrency
innodb_thread_concurrency = 0   # let InnoDB manage
innodb_read_io_threads = 8
innodb_write_io_threads = 8
innodb_purge_threads = 4

# Locking
innodb_lock_wait_timeout = 30
innodb_deadlock_detect = ON
innodb_print_all_deadlocks = ON   # log to error log

# Row format
innodb_default_row_format = DYNAMIC

# Page size (set at initialization, can't change later)
innodb_page_size = 16K

# Doublewrite buffer
innodb_doublewrite = ON

# Stats
innodb_stats_persistent = ON
innodb_stats_auto_recalc = ON

# Other
innodb_strict_mode = ON
innodb_file_per_table = ON
innodb_open_files = 4096
"""


# ==========================================================================
# 9. PRIMARY KEY DESIGN
# ==========================================================================

PRIMARY_KEY_GUIDE = """
GOOD:
  PRIMARY KEY (id BIGINT AUTO_INCREMENT)
  → sequential inserts at B+ tree end
  → no page splits
  → minimal index size

  PRIMARY KEY (uuid_v7)
  → time-ordered UUID
  → mostly sequential
  → acceptable for sharded systems

  PRIMARY KEY (tenant_id, id)
  → composite for tenant locality
  → all tenant data clustered together


BAD:
  PRIMARY KEY (uuid_v4)
  → random ordering
  → page splits everywhere
  → bigger tree, slower inserts, more disk I/O

  PRIMARY KEY (email VARCHAR(255))
  → big keys propagated to secondary indexes
  → fragmentation
  → use INT PK + UNIQUE on email instead
"""


# ==========================================================================
# 10. DEADLOCK ANALYSIS
# ==========================================================================

def configure_deadlock_logging(conn):
    cursor = conn.cursor()
    cursor.execute("SET GLOBAL innodb_print_all_deadlocks = ON")
    # Now all deadlocks logged to error log


# ==========================================================================
# 11. ROW-LEVEL READ EXAMPLES
# ==========================================================================

SQL_EXAMPLES = """
-- Locking reads
SELECT * FROM accounts WHERE id = 5 FOR UPDATE;       -- X lock
SELECT * FROM accounts WHERE id = 5 LOCK IN SHARE MODE; -- S lock (deprecated 8.0+)
SELECT * FROM accounts WHERE id = 5 FOR SHARE;        -- S lock (8.0+)
SELECT * FROM accounts WHERE id = 5 FOR UPDATE NOWAIT;
SELECT * FROM accounts WHERE id = 5 FOR UPDATE SKIP LOCKED;

-- Set isolation per transaction
START TRANSACTION READ ONLY;   -- optimization hint
SELECT ...;
COMMIT;

SET TRANSACTION ISOLATION LEVEL READ COMMITTED;
START TRANSACTION;
-- ...
COMMIT;

-- Engine-aware queries
SHOW ENGINE INNODB STATUS\\G

-- Force index hint
SELECT * FROM users FORCE INDEX (idx_email) WHERE email LIKE 'a%';
"""
