# MySQL Replication Deep

## Why It Matters

MySQL replication = production HA + scaling:
- **Read replicas** → offload SELECTs
- **Failover** → primary crash, promote replica
- **Cross-region** → DR + low-latency reads
- **Analytics** → heavy queries on dedicated replica

Senior interview: "GTID vs binlog file/position — kya use karoge?" → GTID always for new setups (auto-managed positions).

---

## Replication Modes

### 1. Asynchronous (Default)

Primary commits + returns OK before replicas ack. Replicas lag possible.

```
Client → Primary (commit) → OK
           ↓ (later)
        Replica applies
```

**Pros:** Fast, no waiting.
**Cons:** Data loss on primary crash before replication.

### 2. Semi-Synchronous

Primary waits for at least one replica to receive (not apply) binlog.

```ini
[mysqld]
plugin-load = rpl_semi_sync_master=semisync_master.so;rpl_semi_sync_slave=semisync_slave.so
rpl_semi_sync_master_enabled = 1
rpl_semi_sync_slave_enabled = 1
rpl_semi_sync_master_timeout = 10000  # 10s fallback to async
```

**Trade-off:** Up to 1 RTT per commit. Guarantees at least one replica has the data.

### 3. Group Replication (Multi-Master)

```ini
plugin-load = group_replication.so
group_replication_group_name = "aaaaaaaa-..."
group_replication_local_address = "host1:33061"
group_replication_group_seeds = "host1:33061,host2:33061,host3:33061"
```

All members can write. Conflict resolution via certification (Paxos-based). 3+ members for quorum.

## GTID (Global Transaction ID)

```
Format: source-id:transaction-id
        UUID:1, UUID:2, UUID:3, ...
```

Each commit gets unique GTID. Replicas track applied set. Failover trivial — no need to know old binlog file/position.

```ini
gtid_mode = ON
enforce_gtid_consistency = ON
```

```sql
SHOW MASTER STATUS;
-- Executed_Gtid_Set: a1b2c3:1-1000

SELECT GTID_EXECUTED, GTID_PURGED;
```

### Setup New Replica with GTID

```sql
CHANGE REPLICATION SOURCE TO
    SOURCE_HOST = 'primary',
    SOURCE_USER = 'repl',
    SOURCE_PASSWORD = '...',
    SOURCE_AUTO_POSITION = 1;   -- GTID-based

START REPLICA;
```

No need for `MASTER_LOG_FILE` / `MASTER_LOG_POS`.

## Binlog Formats

```ini
binlog_format = ROW   # or STATEMENT, MIXED
```

| Format | Description | Pros | Cons |
|---|---|---|---|
| STATEMENT | Logs SQL | Compact | Non-deterministic SQL → inconsistency |
| ROW | Logs row changes | Deterministic | Larger binlog |
| MIXED | Both, chooses per stmt | Balanced | Sometimes confusing |

**Recommendation:** ROW (default 5.7+). MIXED if disk space critical.

## Replication Topologies

### Master-Slave (Replica)

```
Primary → Replica1
       → Replica2
       → Replica3
```

Most common. Reads from replicas, writes to primary.

### Master-Master (Active-Active — risky)

```
Primary1 ←→ Primary2
```

Both writeable. Conflict potential. Use Group Replication instead for modern setups.

### Chain

```
Primary → Intermediate → Replica
```

Intermediate offloads primary's replication burden. Each link adds latency.

### Multi-Source (One Replica from Many Masters)

```
Primary1 ↘
Primary2 → Replica (aggregates)
Primary3 ↗
```

For analytics — aggregate multiple shards.

## Replication Lag

```sql
SHOW REPLICA STATUS\G
-- Seconds_Behind_Source: 0  (or N)
-- Replica_IO_Running: Yes
-- Replica_SQL_Running: Yes
```

**Lag causes:**
- Slow SQL on replica (long-running query)
- Hardware difference (slower disk)
- Replica overloaded with reads
- Single-threaded apply (use parallel applier)

**Tune parallel applier:**

```ini
replica_parallel_workers = 8
replica_parallel_type = LOGICAL_CLOCK
replica_preserve_commit_order = ON   # for consistent reads
```

`LOGICAL_CLOCK` allows parallel apply of independent transactions.

## Crash-Safe Replication

```ini
relay_log_recovery = ON
master_info_repository = TABLE      # default 8.0
relay_log_info_repository = TABLE   # default 8.0
sync_binlog = 1
innodb_flush_log_at_trx_commit = 1
```

These ensure replica doesn't lose track of position on crash.

## Failover

### Manual

```sql
-- On replica (new primary):
STOP REPLICA;
RESET REPLICA ALL;

-- On other replicas, point to new primary:
CHANGE REPLICATION SOURCE TO SOURCE_HOST='new-primary', SOURCE_AUTO_POSITION=1;
START REPLICA;
```

### Orchestrator / MHA

Tools that automate failover + topology changes. Orchestrator (modern, GUI). MHA (older).

### MySQL Router + InnoDB Cluster

```sql
-- Set up via mysqlsh AdminAPI:
dba.createCluster('myCluster')
-- Auto-failover + read routing via MySQL Router
```

## Read-Write Splitting

### Application-Level

```python
# Two connection pools
master_conn = mysql.connector.connect(host='primary')
replica_conn = mysql.connector.connect(host='replica')


# Route by query type
def execute_write(sql):
    return master_conn.execute(sql)


def execute_read(sql):
    return replica_conn.execute(sql)
```

### ProxySQL

```
App → ProxySQL → Primary (writes)
              → Replicas (reads, load-balanced)
```

Routes by query pattern (regex on SQL).

```sql
-- ProxySQL admin
INSERT INTO mysql_query_rules (rule_id, active, match_digest, destination_hostgroup)
VALUES (1, 1, '^SELECT.*FOR UPDATE', 10);   -- send to primary
INSERT INTO mysql_query_rules (rule_id, active, match_digest, destination_hostgroup)
VALUES (2, 1, '^SELECT', 20);                -- send to replicas
```

---

## Common Pitfalls

### 1. Auto-Increment Conflicts in Multi-Master

```ini
# On master1
auto_increment_increment = 2
auto_increment_offset = 1   # 1, 3, 5, 7, ...

# On master2
auto_increment_increment = 2
auto_increment_offset = 2   # 2, 4, 6, 8, ...
```

For Group Replication, this is automatic.

### 2. STATEMENT Format + Non-Deterministic Functions

```sql
INSERT INTO logs VALUES (NOW(), UUID(), ...);
-- Replica gets different NOW()/UUID() → inconsistency
```

Use ROW format.

### 3. Replica Reads of Just-Written Data

```python
master.execute("INSERT INTO orders ...")
result = replica.execute("SELECT * FROM orders WHERE id = ...")
# May return empty due to lag
```

Solutions:
- Read from primary for read-after-write
- Use semi-sync replication
- Application-level "sticky primary" after writes

### 4. Replication Filtering Misuse

```ini
# On replica
replicate-do-db = appdb   # only replicate this DB
```

Easy to mess up. Use GTID-aware filtering (replicate-ignore-table) cautiously.

### 5. Binlog Disk Full

Binlog files grow forever unless purged:

```sql
-- Purge by file
PURGE BINARY LOGS TO 'mysql-bin.000020';

-- Purge by date
PURGE BINARY LOGS BEFORE NOW() - INTERVAL 7 DAY;
```

```ini
binlog_expire_logs_seconds = 604800   # 7 days
```

### 6. Replica Falls Behind Permanently

If lag exceeds binlog retention on primary, replica needs full rebuild (clone + restart). Mitigation: tune `binlog_expire_logs_seconds` higher, or set up failover before total loss.

---

## Interview Q&A

**Q1:** GTID vs file/position based replication?
**A:** GTID auto-tracks executed transactions per source. Failover trivial — replicas know what they've applied. File/position requires knowing exact binlog file + offset (manual + error-prone). Always use GTID for new setups.

**Q2:** Semi-sync vs full sync?
**A:** Semi-sync: primary waits for at least one replica to RECEIVE (not apply) binlog before commit returns. Full sync would require all replicas to apply — too slow. Semi-sync = 1 RTT cost, guarantees no data loss with one replica alive.

**Q3:** Binlog format STATEMENT vs ROW?
**A:** STATEMENT logs SQL (compact, but non-deterministic functions like NOW() cause drift). ROW logs actual row changes (deterministic, larger). MIXED switches per statement. Production: ROW for correctness, accept higher binlog size.

**Q4:** Replication lag detect + handle?
**A:** Detect: `SHOW REPLICA STATUS\G` → `Seconds_Behind_Source`. Or PMM/Datadog metric. Handle: read from primary for read-after-write, increase replica resources, use parallel applier (LOGICAL_CLOCK), reduce primary write load, switch to semi-sync for critical writes.

**Q5:** Group Replication kab use karoge?
**A:** When you need multi-primary writes + auto-failover + minimal data loss. All members can write; conflicts resolved via certification. Best for HA-critical apps. More complex than asynchronous replica. 3+ members required for quorum.

**Q6:** Crash-safe replication zaroori options?
**A:** `relay_log_recovery=ON`, `master_info_repository=TABLE`, `relay_log_info_repository=TABLE`, `sync_binlog=1`, `innodb_flush_log_at_trx_commit=1`. These ensure replica state durably tracked. Without, crash may lose position.

**Q7:** Read-write split implementation choices?
**A:** (1) App-level: two connection pools, route by query type (manual). (2) ProxySQL: regex-based query rules, transparent to app. (3) MySQL Router (InnoDB Cluster): auto-routing. (4) Cloud (RDS proxy, Aurora cluster endpoint): managed routing. ProxySQL most flexible.

**Q8:** Parallel applier benefits?
**A:** Default replica applies binlog single-threaded → bottleneck. `replica_parallel_workers=8` + `LOGICAL_CLOCK` type → independent transactions apply in parallel based on commit timestamps. Critical for replication keeping up with multi-core write workloads.

---

## Real-World Use Cases

### 1. E-commerce Read Scaling

1 primary (writes), 3 replicas (reads). ProxySQL distributes reads. Writes always to primary. Replica lag monitored, < 5s acceptable.

### 2. Cross-Region DR

Primary in us-east. Async replica in eu-west. On us-east outage: manually promote eu-west, update DNS. 24h+ RTO acceptable.

### 3. Analytics Replica

Primary + dedicated replica for heavy analytics queries. Replica isolated from production load. Long queries don't impact app.

### 4. InnoDB Cluster (Auto HA)

3+ MySQL members in Group Replication. MySQL Router routes traffic. Failover automatic. Used for SaaS apps where downtime expensive.

---

## References

- [MySQL Replication](https://dev.mysql.com/doc/refman/8.0/en/replication.html)
- [GTID](https://dev.mysql.com/doc/refman/8.0/en/replication-gtids.html)
- [Group Replication](https://dev.mysql.com/doc/refman/8.0/en/group-replication.html)
- [ProxySQL](https://proxysql.com/documentation/)
- "High Performance MySQL" 4th edition — Replication chapters
