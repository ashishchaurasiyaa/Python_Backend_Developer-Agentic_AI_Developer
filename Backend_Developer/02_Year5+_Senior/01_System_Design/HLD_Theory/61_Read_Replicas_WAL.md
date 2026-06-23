# Read Replicas + Write-Ahead Log (WAL)

---

## Why Read Replicas?
A single DB becomes a bottleneck when read traffic is high.
Solution: Add read replicas — copies of the primary DB that serve read queries.

```
         Writes ──► Primary DB ──► replicates to ──► Replica 1
                                                  └──► Replica 2
         Reads  ──► Replica 1 or Replica 2
```

---

## How Replication Works (via WAL)

### Write-Ahead Log (WAL)
Every change to the primary DB is first written to the WAL (also called redo log / binlog).
WAL is an append-only sequential log.

```
WAL entry format:
[LSN=1001, txn_id=55, operation=INSERT, table=users, data={id:1, name:"Ashish"}]
[LSN=1002, txn_id=55, operation=UPDATE, table=orders, data={status:"paid"}]
```

### Replication Flow
```
Primary DB
   │
   │── writes change to WAL ──► WAL Log
   │                               │
   │                               ├──► Replica 1 (streams WAL, applies changes)
   │                               └──► Replica 2 (streams WAL, applies changes)
```

Replicas continuously stream WAL from primary and replay changes → stay in sync.

---

## Types of Replication

### 1. Synchronous Replication
Primary waits for at least one replica to acknowledge before confirming write to client.

```
Client ──► Primary ──► Write to disk + WAL
                   ──► Send to Replica ──► Replica ACKs
                   ──► Return success to client
```
✅ No data loss (strong durability)
❌ Higher write latency

### 2. Asynchronous Replication
Primary confirms write immediately. Replica catches up in background.

```
Client ──► Primary ──► Return success immediately
                   ──► (async) Send WAL to Replica
```
✅ Low write latency
❌ Replica may lag = replication lag = stale reads

---

## Replication Lag
Time difference between primary and replica state.

**Causes:** Network delay, heavy write load, slow replica
**Impact:** Users may read stale data right after a write

**Solutions:**
- Read your own writes: route user's own reads to primary
- Sticky sessions: same user always reads from same replica
- Use synchronous replication for critical data
- Monitor replica lag → alert if > threshold (e.g. > 1 second)

---

## WAL for Crash Recovery (not just replication)

If DB crashes mid-transaction:
1. On restart, DB reads WAL
2. Replays committed transactions (redo)
3. Rolls back uncommitted transactions (undo)

This ensures durability (the D in ACID).

---

## Read Replica Architecture in Practice

```
Application
    │
    ├── Writes ──────────────────► Primary DB
    │                                  │
    └── Reads (via load balancer) ─► Replica 1
                                   ► Replica 2
                                   ► Replica 3
```

**Read load balancer strategies:**
- Round robin
- Least connections
- Geography-based (route to nearest replica)

---

## When to Use Read Replicas

✅ Read:write ratio is high (e.g. 10:1)
✅ Analytics / reporting queries (don't slow down primary)
✅ Geo-distributed reads (replica in each region)
✅ Failover — promote replica to primary if primary goes down

❌ Don't use for writes (replicas are read-only)
❌ Don't use when strong consistency required for reads (use primary)

---

## Real World
- **PostgreSQL:** Streaming replication via WAL
- **MySQL:** Binlog-based replication
- **Amazon RDS:** Up to 15 read replicas per instance
- **Instagram:** Used read replicas to scale PostgreSQL reads

---

## Interview Tip
> "We add read replicas to scale read-heavy workloads. Replication happens via WAL streaming — the replica continuously replays WAL entries from the primary. We accept eventual consistency for most reads, but route writes and user's own reads to the primary to avoid stale data issues."
