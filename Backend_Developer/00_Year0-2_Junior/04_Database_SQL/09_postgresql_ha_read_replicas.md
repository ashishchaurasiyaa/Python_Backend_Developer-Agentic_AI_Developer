# PostgreSQL HA + Read Replicas

> **Interview angle:** "Database fail ho gaya — kitne minutes mein recover hoga? Read traffic kahan jata hai?"

---

## 1. The Problem: Single Postgres = Single Point of Failure

If your single Postgres dies:
- App returns 500s
- Manual restore from backup = hours of downtime
- Data loss possible (since last backup)

**Production needs:**
- **HA (High Availability)** — automatic failover in seconds
- **Read replicas** — offload read traffic, geo-distribute
- **Backups** — last-resort recovery

---

## 2. Replication Types

### Streaming Replication (Physical)
- Replica replays WAL (Write-Ahead Log) from primary
- Byte-level copy → exact replica
- **Synchronous** or **asynchronous**
- Primary writes WAL, replica reads it (over network or shipped files)

### Logical Replication
- Replicates SQL operations (not bytes)
- Can replicate **specific tables**, not whole DB
- Can replicate between **different Postgres versions**
- Used for: zero-downtime upgrades, multi-master, ETL

### Comparison

| Aspect | Streaming (Physical) | Logical |
|---|---|---|
| Granularity | Whole cluster | Per-table |
| Cross-version | ❌ | ✅ |
| Cross-platform | ❌ | ✅ |
| Replica writable | No (until promoted) | Yes |
| Performance | Faster | Slower |
| Use case | HA, read replicas | Selective sync, upgrades |

---

## 3. Synchronous vs Asynchronous Replication

### Async (default)
- Primary commits → replies to client → THEN sends to replica
- **Risk:** Few seconds of data loss if primary crashes before sync
- Fast (no waiting on replica)
- **99% of setups use async**

### Sync
- Primary commits → waits for at least 1 replica to confirm → replies
- **Zero data loss** for committed transactions
- Slower (RTT to replica adds latency)
- Use for: financial data, audit logs

### Sync Standby Levels
```conf
synchronous_commit = on              # default — sync to local WAL
synchronous_commit = remote_apply    # wait for replica APPLY (slow)
synchronous_commit = remote_write    # wait for replica WRITE (medium)
synchronous_standby_names = 'ANY 1 (replica1, replica2)'
```

---

## 4. Read Replicas — Offloading Reads

```
        ┌─────────────────────┐
        │  App / API          │
        └──────────┬──────────┘
                   │
          ┌────────┴────────┐
          │ Smart router    │
          │ (read/write)    │
          └─┬──────────────┬┘
            │              │
   Writes ──┘              └── Reads
   (always)                    (load-balanced)
            ▼                       ▼
       ┌────────┐               ┌────────┐
       │Primary │ ── WAL ──────▶│Replica1│
       └────────┘               └────────┘
                ── WAL ──────▶  ┌────────┐
                                │Replica2│
                                └────────┘
```

### Use Cases
- Analytics queries (won't slow OLTP)
- Reporting dashboards
- Backup source (don't burden primary)
- Geo-distributed reads (replica close to users)

### Replication Lag
- Replica is **always behind** primary by ~ms to seconds
- Monitor: `SELECT pg_last_wal_replay_lsn() vs pg_current_wal_lsn()`
- Lag matters: order placed on primary, view on replica may show "not found"

---

## 5. Read/Write Split in App

### Option A: Manual routing
```python
# Use separate engines
write_engine = create_engine("postgresql://primary/db")
read_engine = create_engine("postgresql://replica-lb/db")

@app.get("/users/{id}")
async def get_user(id: int):
    async with AsyncSession(read_engine) as s:    # replica
        return await s.get(User, id)

@app.post("/users")
async def create_user(data):
    async with AsyncSession(write_engine) as s:   # primary
        user = User(**data)
        s.add(user)
        await s.commit()
```

### Option B: SQLAlchemy session binding
```python
from sqlalchemy.orm import Session

class RoutedSession(Session):
    def get_bind(self, mapper=None, clause=None, **kw):
        if self._flushing or isinstance(clause, (Insert, Update, Delete)):
            return write_engine
        return read_engine
```

### Option C: Connection-level proxy (PgBouncer, PgPool, Citus)
App connects to proxy → proxy routes based on query type.

---

## 6. Read-After-Write Consistency

**Problem:** Create user on primary → read from replica immediately → not found (replication lag).

### Solution 1: Read-Your-Writes on primary
```python
session_just_wrote = request.session.get("just_wrote", False)
if session_just_wrote:
    engine = write_engine    # use primary for this read
else:
    engine = read_engine
```

### Solution 2: LSN tracking
After write, get LSN. On replica, wait until replica caught up to that LSN.

### Solution 3: Sticky sessions
User's session pinned to primary for N seconds after write.

---

## 7. Failover — When Primary Dies

### Manual failover
1. Detect primary down (timeouts, monitoring)
2. Pick best replica (most up-to-date)
3. Promote replica: `pg_ctl promote` or `SELECT pg_promote()`
4. Repoint DNS/connection string
5. Old primary needs reset or rebuild

**Manual = minutes to hours of downtime.**

### Automatic failover with Patroni
Open-source HA framework using etcd/Consul/ZooKeeper for consensus.

```
┌──────────────┐
│   Patroni    │ ←─── monitors all nodes
└──┬────────┬──┘
   │        │
┌──▼──┐  ┌─▼──┐
│Prim │  │Repl│  ←── etcd holds leader election
└─────┘  └────┘
```

- Patroni runs on each node
- Etcd: distributed key-value, picks leader
- Auto-promote replica when primary fails
- **Failover in ~30 seconds** (typical)

### Cloud-managed HA
- **AWS RDS**: Multi-AZ — auto-failover in ~60s
- **Aurora**: failover in ~30s (shared storage)
- **GCP Cloud SQL**: regional HA
- **Azure DB**: zone-redundant HA

**Strong recommendation:** Use managed HA in cloud. Patroni only if self-hosting.

---

## 8. Patroni Setup (Conceptual)

```yaml
# patroni.yml on each node
name: pg-node-1
scope: postgres-cluster
restapi:
  listen: 0.0.0.0:8008
  connect_address: 10.0.1.10:8008

etcd:
  hosts: etcd1:2379,etcd2:2379,etcd3:2379

bootstrap:
  dcs:
    ttl: 30
    loop_wait: 10
    retry_timeout: 30
    maximum_lag_on_failover: 1048576
    postgresql:
      parameters:
        wal_level: replica
        hot_standby: "on"
        max_wal_senders: 10
        max_replication_slots: 10

postgresql:
  listen: 0.0.0.0:5432
  data_dir: /var/lib/postgresql/data
  authentication:
    superuser:
      username: postgres
      password: secret
    replication:
      username: replicator
      password: replicator
```

---

## 9. Connection String Strategies

### Strategy 1: HAProxy / PgBouncer in front
```
app → haproxy:5432 → routes to current primary
app → haproxy:5433 → routes to a replica
```

### Strategy 2: DNS + low TTL
```
db.primary.example.com → DNS A record
On failover: update DNS to new IP (TTL=30s)
```

### Strategy 3: Multi-host connection string (Postgres 10+)
```python
"postgresql://user:pass@host1,host2,host3/db?target_session_attrs=read-write"
```
- Client tries each host
- `read-write` = picks primary
- `prefer-standby` = picks replica

### Strategy 4: Service discovery
Consul/etcd → app queries for current primary IP.

---

## 10. Monitoring HA Cluster

### Critical metrics
```sql
-- Replication lag in bytes
SELECT pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) AS lag_bytes
FROM pg_stat_replication;

-- Replication lag in seconds
SELECT extract(EPOCH FROM now() - pg_last_xact_replay_timestamp());

-- Active replication slots
SELECT * FROM pg_replication_slots;

-- Standby state
SELECT * FROM pg_stat_replication;

-- Is this server in recovery mode (i.e., a replica)?
SELECT pg_is_in_recovery();
```

### Alerts
- Replication lag > 60 seconds
- Replica disconnected
- Primary load > 80% CPU
- WAL backlog > 5 GB
- Replication slot orphaned (replica gone but slot remains)

---

## 11. Common HA Failure Modes

### Failure 1: Split brain
Both nodes think they're primary (network partition). Apps write to both. Data divergence.
**Fix:** Use consensus (etcd/Consul). Fencing (kill the loser).

### Failure 2: Cascading failures
Primary fails → traffic to replica → replica fails under load.
**Fix:** Load test failover. Auto-scale replicas. Circuit breakers in app.

### Failure 3: Stuck replication
Replica falls behind → never catches up → eventually disconnects.
**Fix:** Monitor lag. Have replacement procedure (re-clone replica).

### Failure 4: Orphaned replication slots
Replica deleted but slot remains → WAL accumulates on primary → disk fills.
**Fix:** Drop unused slots: `SELECT pg_drop_replication_slot('slot_name')`.

### Failure 5: Failover during transaction
In-flight transactions rolled back. App must retry.
**Fix:** Idempotent operations + retry logic in app.

---

## 12. Failover Drill (Practice!)

Run regularly in staging:
```bash
# Simulate primary failure
docker kill postgres-primary

# Verify failover < 60s
while true; do
  curl -s http://app/health | jq .db
  sleep 1
done

# Bring back as new replica
docker run postgres-replica-new
patronictl reinit cluster-name new-node
```

---

## 13. Real-World Architecture

### Small (< 1K req/s)
- 1 primary + 1 sync replica + 1 async replica
- Managed RDS / Cloud SQL Multi-AZ
- Backup to S3 daily

### Medium (1K-100K req/s)
- 1 primary + 2 replicas in same AZ + 1 replica in another region (DR)
- Patroni for self-hosted, Aurora for cloud
- pgBouncer for connection pooling
- WAL archiving to S3

### Large (100K+ req/s)
- Sharded primary (Citus, Vitess)
- Read replicas per shard
- Cross-region replication
- 24/7 oncall + automated runbook

---

## 14. Interview Questions

**Q1: Streaming vs logical replication?**
Streaming = byte-level WAL replay, all or nothing. Logical = SQL-level, per-table, cross-version.

**Q2: Sync vs async replication?**
Sync = zero data loss but slower. Async = fast but few seconds risk. Default: async.

**Q3: Failover kaise hota hai automatic?**
Patroni + etcd. Patroni monitors. If primary unreachable, picks most-caught-up replica, promotes via `pg_promote`. Updates etcd. Apps reconnect.

**Q4: Replication lag kya hai?**
Time between primary commit and replica apply. Measured in bytes (WAL bytes behind) or seconds. Monitor + alert.

**Q5: Read-after-write inconsistency?**
Write to primary, read from replica = lag. Fix: read own writes from primary, use LSN tracking, sticky sessions.

**Q6: Split brain kya?**
Network partition → both nodes claim primary. Both accept writes → diverge. Fix: consensus (etcd) + fencing.

**Q7: RDS Multi-AZ vs Read Replica?**
Multi-AZ = HA standby (not readable). Read replica = readable but separate. Combine for full setup.

---

## 15. Best Practices

1. **Always use managed HA in cloud** (RDS Multi-AZ, Aurora)
2. **Self-hosted: Patroni + etcd**
3. **Multi-host connection strings** with target_session_attrs
4. **Async replication is fine** for most apps
5. **Test failover quarterly** in staging
6. **Monitor lag in seconds AND bytes**
7. **Use pgBouncer** between app and DB cluster
8. **Cross-region replica** for disaster recovery
9. **Failover < 60s** is achievable target
10. **Document runbook** for manual interventions

---

## Related
- [[10_postgresql_partitioning_sharding]]
- [[11_pgbouncer_connection_pooling]]
- [[12_backup_disaster_recovery]]
- [[07_postgresql_internals]] — WAL deep dive
