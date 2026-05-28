"""
MySQL Replication — Production Monitoring + Setup Patterns
"""

import mysql.connector


# ==========================================================================
# 1. CHECK REPLICATION STATUS
# ==========================================================================

def replication_status(conn):
    """Run on replica."""
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SHOW REPLICA STATUS")
    row = cursor.fetchone()
    if not row:
        print("Not a replica")
        return

    print(f"Source: {row['Source_Host']}:{row['Source_Port']}")
    print(f"IO running: {row['Replica_IO_Running']}")
    print(f"SQL running: {row['Replica_SQL_Running']}")
    print(f"Seconds behind: {row['Seconds_Behind_Source']}")
    print(f"GTID executed: {row.get('Executed_Gtid_Set', 'N/A')[:100]}")

    if row['Replica_IO_Running'] != 'Yes' or row['Replica_SQL_Running'] != 'Yes':
        print(f"ALERT: replication broken — Last error: {row['Last_Error']}")

    lag = row['Seconds_Behind_Source']
    if lag is not None and lag > 60:
        print(f"ALERT: lag {lag}s exceeds threshold")


# ==========================================================================
# 2. CHECK GTID STATE
# ==========================================================================

def gtid_status(conn):
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SHOW VARIABLES LIKE 'gtid_mode'")
    print(cursor.fetchone())

    cursor.execute("SELECT @@global.gtid_executed AS executed, @@global.gtid_purged AS purged")
    print(cursor.fetchone())


# ==========================================================================
# 3. CONFIGURE REPLICA (GTID-based)
# ==========================================================================

REPLICA_SETUP_SQL = """
-- On primary: create replication user
CREATE USER 'repl'@'%' IDENTIFIED BY 'strong-password';
GRANT REPLICATION SLAVE ON *.* TO 'repl'@'%';
FLUSH PRIVILEGES;


-- Take consistent backup of primary (or use clone plugin)
-- mysqldump --all-databases --triggers --routines --events --master-data=2 --single-transaction > backup.sql


-- On replica: restore data
-- mysql < backup.sql


-- On replica: configure replication
CHANGE REPLICATION SOURCE TO
    SOURCE_HOST = 'primary-host',
    SOURCE_PORT = 3306,
    SOURCE_USER = 'repl',
    SOURCE_PASSWORD = 'strong-password',
    SOURCE_AUTO_POSITION = 1,         -- GTID-based
    SOURCE_SSL = 1,
    GET_SOURCE_PUBLIC_KEY = 1;


-- Start
START REPLICA;

-- Verify
SHOW REPLICA STATUS\\G
"""


# ==========================================================================
# 4. CLONE PLUGIN (modern way to set up replica)
# ==========================================================================

CLONE_SETUP_SQL = """
-- On primary
INSTALL PLUGIN clone SONAME 'mysql_clone.so';
CREATE USER 'clone_user'@'%' IDENTIFIED BY 'strong-password';
GRANT BACKUP_ADMIN ON *.* TO 'clone_user'@'%';
FLUSH PRIVILEGES;


-- On replica
INSTALL PLUGIN clone SONAME 'mysql_clone.so';
CREATE USER 'clone_user'@'%' IDENTIFIED BY 'strong-password';
GRANT CLONE_ADMIN ON *.* TO 'clone_user'@'%';

SET GLOBAL clone_valid_donor_list = 'primary-host:3306';

CLONE INSTANCE FROM 'clone_user'@'primary-host':3306
IDENTIFIED BY 'strong-password';
-- Replica restarts after clone completes

-- After restart, set up replication (GTID auto-positioned)
CHANGE REPLICATION SOURCE TO
    SOURCE_HOST = 'primary-host',
    SOURCE_USER = 'repl',
    SOURCE_PASSWORD = '...',
    SOURCE_AUTO_POSITION = 1;
START REPLICA;
"""


# ==========================================================================
# 5. PARALLEL APPLIER CONFIG
# ==========================================================================

PARALLEL_APPLIER_CONFIG = """
# my.cnf on replica

# Parallel replication
replica_parallel_workers = 8
replica_parallel_type = LOGICAL_CLOCK
replica_preserve_commit_order = ON

# Crash-safe
relay_log_recovery = ON
master_info_repository = TABLE        # default in 8.0
relay_log_info_repository = TABLE     # default in 8.0
sync_binlog = 1
innodb_flush_log_at_trx_commit = 1

# Semi-sync (optional)
plugin-load-add = semisync_replica.so
rpl_semi_sync_replica_enabled = 1
"""


# ==========================================================================
# 6. SEMI-SYNCHRONOUS REPLICATION
# ==========================================================================

SEMI_SYNC_SETUP = """
-- On primary
INSTALL PLUGIN rpl_semi_sync_source SONAME 'semisync_source.so';
SET GLOBAL rpl_semi_sync_source_enabled = 1;
SET GLOBAL rpl_semi_sync_source_timeout = 10000;  -- 10s

-- On replica
INSTALL PLUGIN rpl_semi_sync_replica SONAME 'semisync_replica.so';
SET GLOBAL rpl_semi_sync_replica_enabled = 1;
STOP REPLICA IO_THREAD;
START REPLICA IO_THREAD;

-- Verify
SHOW STATUS LIKE 'Rpl_semi_sync%';
"""


# ==========================================================================
# 7. APP-LEVEL READ/WRITE SPLIT
# ==========================================================================

class ReadWriteSplit:
    """Application-level routing."""

    def __init__(self, primary_config, replica_configs):
        self.primary = mysql.connector.connect(**primary_config)
        self.replicas = [mysql.connector.connect(**c) for c in replica_configs]
        self._replica_idx = 0

    def _next_replica(self):
        """Round-robin replica selection."""
        r = self.replicas[self._replica_idx]
        self._replica_idx = (self._replica_idx + 1) % len(self.replicas)
        return r

    def execute_write(self, sql, params=None):
        cursor = self.primary.cursor()
        cursor.execute(sql, params)
        return cursor

    def execute_read(self, sql, params=None):
        cursor = self._next_replica().cursor()
        cursor.execute(sql, params)
        return cursor

    def execute_read_consistent(self, sql, params=None):
        """For read-after-write — use primary."""
        cursor = self.primary.cursor()
        cursor.execute(sql, params)
        return cursor


# ==========================================================================
# 8. STICKY PRIMARY AFTER WRITES (read-your-own-writes)
# ==========================================================================

import threading


_recent_write = threading.local()


def mark_write_done():
    _recent_write.until = time.monotonic() + 5  # 5 sec sticky window


def should_use_primary():
    until = getattr(_recent_write, 'until', 0)
    return time.monotonic() < until


# Middleware sets sticky after POST/PUT/DELETE
# All reads in next 5 sec from primary


# ==========================================================================
# 9. FAILOVER ORCHESTRATION
# ==========================================================================

MANUAL_FAILOVER_STEPS = """
-- Scenario: Primary down. Promote replica1 to primary.

-- On all other replicas (replica2, replica3):
STOP REPLICA;

-- On replica1 (about to become primary):
STOP REPLICA;
RESET REPLICA ALL;
-- Replica1 now standalone

-- On replica1: ensure it's writeable
SET GLOBAL read_only = OFF;
SET GLOBAL super_read_only = OFF;

-- Update application config to point to new primary (replica1)


-- On replica2, replica3: point to new primary
CHANGE REPLICATION SOURCE TO
    SOURCE_HOST = 'replica1-host',
    SOURCE_USER = 'repl',
    SOURCE_PASSWORD = '...',
    SOURCE_AUTO_POSITION = 1;
START REPLICA;


-- (Old primary, if it comes back online):
STOP REPLICA;  -- in case
RESET REPLICA ALL;
CHANGE REPLICATION SOURCE TO
    SOURCE_HOST = 'replica1-host',
    SOURCE_USER = 'repl',
    SOURCE_PASSWORD = '...',
    SOURCE_AUTO_POSITION = 1;
START REPLICA;

-- Old primary is now a replica
"""


# ==========================================================================
# 10. BINLOG MANAGEMENT
# ==========================================================================

def binlog_management(conn):
    cursor = conn.cursor()

    # List binlogs + sizes
    cursor.execute("SHOW BINARY LOGS")
    for row in cursor.fetchall():
        print(row)

    # Total binlog size
    cursor.execute("""
        SELECT SUM(File_size) / 1024 / 1024 / 1024 AS gb
        FROM information_schema.processlist
        WHERE 1=0  -- placeholder
    """)
    # Actually:
    cursor.execute("SHOW BINARY LOGS")
    rows = cursor.fetchall()
    total_gb = sum(r[1] for r in rows) / 1024 / 1024 / 1024
    print(f"Total binlog: {total_gb:.1f} GB")


def purge_old_binlogs(conn, days=7):
    cursor = conn.cursor()
    cursor.execute(f"PURGE BINARY LOGS BEFORE NOW() - INTERVAL {days} DAY")


# Or set retention config
# SET GLOBAL binlog_expire_logs_seconds = 604800  -- 7 days


# ==========================================================================
# 11. GROUP REPLICATION SETUP
# ==========================================================================

GROUP_REPLICATION_CONFIG = """
# my.cnf on each member

server_id = <unique>
gtid_mode = ON
enforce_gtid_consistency = ON

binlog_checksum = NONE
log_bin = mysql-bin
log_replica_updates = ON
binlog_format = ROW

# Group Replication
plugin_load_add = 'group_replication.so'
transaction_write_set_extraction = XXHASH64

group_replication_group_name = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
group_replication_start_on_boot = OFF
group_replication_local_address = "host-1:33061"
group_replication_group_seeds = "host-1:33061,host-2:33061,host-3:33061"
group_replication_bootstrap_group = OFF

# Single-primary or multi-primary
group_replication_single_primary_mode = ON


-- On first member (bootstrap)
SET GLOBAL group_replication_bootstrap_group = ON;
START GROUP_REPLICATION;
SET GLOBAL group_replication_bootstrap_group = OFF;


-- On subsequent members
START GROUP_REPLICATION;


-- Check status
SELECT * FROM performance_schema.replication_group_members;
"""


# ==========================================================================
# 12. PROXYSQL ROUTING (read-write split)
# ==========================================================================

PROXYSQL_CONFIG = """
-- ProxySQL admin commands

-- Define backend servers
INSERT INTO mysql_servers (hostgroup_id, hostname, port) VALUES
    (10, 'primary-host', 3306),   -- writer group
    (20, 'replica-1', 3306),       -- reader group
    (20, 'replica-2', 3306),
    (20, 'replica-3', 3306);


-- Users
INSERT INTO mysql_users (username, password, default_hostgroup) VALUES
    ('appuser', 'pass', 10);   -- defaults to writer


-- Query routing rules
INSERT INTO mysql_query_rules (rule_id, active, match_digest, destination_hostgroup, apply)
VALUES
    (1, 1, '^SELECT.*FOR UPDATE$', 10, 1),    -- SELECT FOR UPDATE → writer
    (2, 1, '^SELECT', 20, 1);                  -- other SELECTs → readers


-- Replication hostgroups (for auto-detection of primary)
INSERT INTO mysql_replication_hostgroups (writer_hostgroup, reader_hostgroup)
VALUES (10, 20);


LOAD MYSQL SERVERS TO RUNTIME;
LOAD MYSQL USERS TO RUNTIME;
LOAD MYSQL QUERY RULES TO RUNTIME;
SAVE MYSQL SERVERS TO DISK;
SAVE MYSQL USERS TO DISK;
SAVE MYSQL QUERY RULES TO DISK;
"""


# ==========================================================================
# 13. MONITORING METRICS
# ==========================================================================

REPLICATION_METRICS = """
Critical metrics:

mysql_replica_seconds_behind_source    -- lag
mysql_replica_io_running               -- 0 if broken
mysql_replica_sql_running              -- 0 if broken

mysql_binlog_size_bytes                -- total binlog disk usage

mysql_semi_sync_master_ack_clients     -- # of replicas semi-sync acking
mysql_semi_sync_master_tx_avg_wait_time -- semi-sync overhead

mysql_group_replication_members        -- # of group members ONLINE


Alerts:
- Lag > 60s
- Replication not running > 1 minute
- Binlog disk > 80%
- GTID gap detected
- Semi-sync replicas < 1 (lost durability)
- Group Replication member count < quorum
"""
