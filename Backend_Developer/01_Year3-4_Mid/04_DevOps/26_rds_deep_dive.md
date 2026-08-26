# RDS — Managed Database Deep Dive

## What RDS Manages for You

```
Self-managed PostgreSQL on EC2:
  OS patching, PostgreSQL version upgrades, backups, replication setup,
  failover scripting, monitoring — sab tumhe karna hai

RDS PostgreSQL:
  AWS manages ↑ all of that
  You manage: schema, queries, indexes, connections, parameter groups
```

---

## THE Most Important Distinction (Interview Trap)

```
Multi-AZ              ≠              Read Replica

HIGH AVAILABILITY          READ SCALING / REPORTING
      ↑                              ↑
Automatic Failover           Manual DNS change needed
Synchronous replication      Asynchronous replication
Standby = NOT readable       Replica = readable
Same region (2 AZs)          Same or cross-region
```

### Multi-AZ — Failover (HA)

```
AZ-1a: RDS Primary (active, read+write)
           ↓ synchronous replication
AZ-1b: RDS Standby (passive, NOT accessible)

Primary fails → AWS auto-promotes Standby → new Primary
DNS endpoint same rehta hai (mydb.xxx.rds.amazonaws.com)
Failover time: ~60-120 seconds
```

**Key:** Standby ko directly query NAHI kar sakte. Sirf failover ke liye hai.

### Read Replica — Read Scaling

```
RDS Primary (read+write)
    ↓ asynchronous replication (small lag possible)
Read Replica 1 (read-only)   ← reports, analytics
Read Replica 2 (read-only)   ← BI dashboard
Read Replica 3 (cross-region, read-only)   ← DR + local reads
```

**Key:** Application ne explicitly Read Replica ka endpoint use karna hoga. Auto-failover nahi hoti (unless promoted manually).

### Can You Have Both?
```
Multi-AZ Primary + Read Replicas ← BOTH together common hai production mein
```

---

## Connection Architecture

### The Problem: Connection Exhaustion
```
RDS db.t3.medium: max_connections ≈ 170

8 EC2 × 4 Gunicorn workers × Django CONN_MAX_AGE × 5 pool_size
= 8 × 4 × 5 = 160 connections... close to limit

Scale to 20 EC2? → 20 × 4 × 5 = 400 → exceeds max_connections ❌
```

### Solution: PgBouncer (Connection Pooling)

```
EC2 instances → PgBouncer (port 6432) → RDS (port 5432)

PgBouncer modes:
  Session pooling:     1 DB connection per client session   (safest)
  Transaction pooling: 1 DB connection per transaction      (most efficient)
  Statement pooling:   1 DB connection per statement        (risky with Django)
```

**Django settings with RDS:**
```python
DATABASES = {
    "default": {
        "ENGINE":   "django.db.backends.postgresql",
        "HOST":     "mydb.xxx.ap-south-1.rds.amazonaws.com",
        "PORT":     "5432",
        "NAME":     "myapp",
        "USER":     "myapp_user",
        "PASSWORD": get_secret("prod/myapp/db")["password"],
        "OPTIONS":  {"connect_timeout": 10},
        "CONN_MAX_AGE": 60,   # connection reuse (not pool — use pgBouncer for real pooling)
        "CONN_HEALTH_CHECKS": True,  # Django 4.1+
    }
}
```

### RDS Proxy (AWS Managed Pooler)
- AWS ka managed PgBouncer equivalent
- IAM authentication support
- Useful for Lambda (new connection per invocation problem solve karta hai)

---

## Backups & Recovery

### Automated Backups
```
RDS setting:
  Backup retention: 7-35 days (0 = disable, don't do this in prod)
  Backup window: 03:00-04:00 UTC (low traffic time)

Gives you: Point-in-time recovery (PITR)
  → Restore to ANY second within retention period
  → RTO: ~minutes to hours depending on DB size
```

### Manual Snapshots
```
Manual snap = indefinite retention (until you delete)
Use case:
  - Major migration ke pehle
  - Quarter-end archival
  - Cross-region copy for DR
```

### Point-in-Time Recovery (PITR)
```
Bug deployed 14:30 UTC → bad data written
Restore to 14:29 UTC → clean state recovered

aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier prod-db \
  --target-db-instance-identifier prod-db-recovery \
  --restore-time 2026-08-17T14:29:00Z
```
Note: Restores to a NEW instance. Old instance remains. You switch app endpoint.

---

## Parameter Groups

Custom DB settings jo RDS pe apply karte hain:

```sql
-- Common PostgreSQL parameters to tune:
max_connections         = 200    -- connection limit (instance size se tied)
shared_buffers          = 256MB  -- buffer cache (RAM ka 25%)
work_mem                = 4MB    -- per-sort memory (careful: per operation)
maintenance_work_mem    = 64MB   -- VACUUM, CREATE INDEX
log_min_duration_statement = 1000  -- log queries > 1 second (slow query log)
log_connections         = on     -- who connects
log_disconnections      = on
```

**Slow query log enable karo always — queries optimize karne ke liye essential.**

---

## Monitoring (CloudWatch Metrics)

```
Key metrics to watch + alert on:

CPUUtilization          > 80%  → query optimization needed
FreeStorageSpace        < 20%  → storage increase karo
DatabaseConnections     > 80%  → connection pooling tune karo
ReadLatency             > 20ms → read replica ya caching needed
WriteLatency            > 10ms → write bottleneck
FreeableMemory          low    → shared_buffers tune karo
ReadIOPS / WriteIOPS    → storage type check (gp3 better than gp2 ab)
ReplicaLag              > 1s   → replica sync pe lag hai
```

Enhanced Monitoring: OS-level metrics (per-process CPU, memory) — enable in RDS settings.

---

## Storage Types

| Type | Use case | Max IOPS |
|---|---|---|
| gp3 (General Purpose) | Most workloads | 16,000 |
| io1/io2 (Provisioned IOPS) | High perf, low latency | 64,000 |
| magnetic | Legacy, avoid | 1,000 |

**gp3 preferred** — IOPS aur throughput alag configure kar sakte ho (gp2 pe linked tha).

---

## Security

```
1. Private Subnet mein rakho — no public accessibility
2. Security Group: sirf EC2-SG se 5432 allow
3. Encryption at rest: AWS KMS (enable at creation)
4. Encryption in transit: SSL/TLS (enforce with parameter rds.force_ssl=1)
5. IAM Authentication: password ke bajaye IAM token (Lambda ke liye useful)
6. Credentials: Secrets Manager mein store karo, rotate auto

# Django: SSL enforce karo
DATABASES["default"]["OPTIONS"]["sslmode"] = "require"
```

---

## RDS vs Aurora PostgreSQL

| | RDS PostgreSQL | Aurora PostgreSQL |
|---|---|---|
| Storage | Per-instance | Shared distributed (6 copies across 3 AZs) |
| Failover | ~60-120s | ~30s |
| Read replicas | Up to 5 | Up to 15 |
| Cost | Lower | ~20% higher |
| Performance | Standard | Up to 3× faster (Aurora claim) |
| Backtrack | No | Yes (rewind DB seconds) |

**For SDE-2 interview:** RDS PostgreSQL is fine to discuss. Aurora = more advanced.

---

## Interview Q&A

**Q: Multi-AZ aur Read Replica mein kya fark hai?**
A: Multi-AZ = HA/failover, synchronous replication, standby readable nahi. Read Replica = read scaling, asynchronous, separate readable endpoint. Production mein dono saath use karte hain.

**Q: EC2 scale karo 5 se 50 tak → RDS crash hoga kya?**
A: Haan, connection exhaustion ho sakta hai. 50 instances × 4 workers × 5 pool = 1000 connections, RDS ka max usually 200-500. Solution: PgBouncer ya RDS Proxy — pool of actual DB connections share karo.

**Q: Database restore karna ho toh kya karte hain?**
A: PITR se restore karo → nayi instance banti hai → endpoint switch karo. Restore time depends on DB size. Backup retention period ke andar kisi bhi second pe restore kar sakte hain.

**Q: RDS slow queries kaise diagnose karte hain?**
A: Parameter group mein `log_min_duration_statement=1000` set karo → slow queries CloudWatch Logs mein aati hain. Performance Insights (RDS feature) se top SQL queries by wait time dekho. `EXPLAIN ANALYZE` run karo suspicious queries pe.

**Q: Read Replica lag kya hai aur kab problem hoti hai?**
A: Async replication = primary write ke baad replica mein thodi der se data aata hai (seconds to minutes under load). Problem: user writes data → immediately reads from replica → sees stale data. Fix: critical reads primary se karo, sirf reporting/analytics ke liye replica use karo.
