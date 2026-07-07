# MySQL Clustering — Galera & NDB Cluster

## Why It Matters

You already know single-primary replication (covered in
`07_replication_deep.md`). Clustering is the follow-up question when the
interviewer asks "what if you need multi-primary — writes accepted on any
node, not just one?" This is lower-frequency than replication itself (most
shops run single-primary + read replicas), but knowing the tradeoffs signals
you understand *why* most shops don't reach for clustering by default.

Senior interview: "Why not just run Galera everywhere for high
availability instead of primary-replica?" → synchronous multi-primary
sounds ideal, but write latency and conflict handling make it the wrong
default choice for most workloads.

---

## Galera Cluster — synchronous multi-primary replication

```
       ┌─────────┐       ┌─────────┐       ┌─────────┐
       │ Node A   │◄─────►│ Node B   │◄─────►│ Node C   │
       │ (primary)│       │ (primary)│       │ (primary)│
       └─────────┘       └─────────┘       └─────────┘
              All nodes accept writes.
       A write on ANY node synchronously replicates
       to ALL nodes before the client gets a COMMIT.
```

- **Synchronous** — a `COMMIT` doesn't return until the write is certified
  (conflict-checked) on every node. This is the key difference from standard
  MySQL replication, which is asynchronous by default.
- **Certification-based replication** — Galera doesn't lock rows across
  nodes upfront; it optimistically commits locally, then certifies against
  other nodes' pending writes. A conflicting concurrent write on another node
  causes one of the two transactions to abort with a deadlock-like error.

```sql
-- Application-level implication: Galera can abort a transaction that would
-- have succeeded fine on plain MySQL, purely due to cross-node conflict certification.
-- Your application MUST have retry logic for this:
START TRANSACTION;
UPDATE accounts SET balance = balance - 100 WHERE id = 1;
COMMIT;
-- ERROR 1213 (40001): Deadlock found when trying to get lock;
-- try restarting transaction   ← THIS is a normal, expected Galera behavior
```

### Tradeoffs

| Pros | Cons |
|---|---|
| No single point of failure for writes | Write latency = slowest node in the cluster (synchronous) |
| True multi-primary — write to any node | Certification conflicts under high write concurrency to the same rows |
| Automatic node provisioning/rejoin | Hot-spot tables (e.g., a global counter) perform *worse* than single-primary |
| No replication lag for reads | Requires the app to retry on certification-conflict errors |

**When Galera makes sense:** multi-region active-active writes are a hard
requirement, and write conflict rate on the same rows is genuinely low.
**When it doesn't:** the common case — one write region is fine, and
async primary-replica is simpler and faster.

---

## NDB Cluster (MySQL Cluster) — the other clustering option

```
Different architecture entirely — in-memory, shared-nothing, designed
for telecom-grade sub-millisecond lookups and 99.999% uptime, not
general-purpose OLTP web apps.

Data Nodes (store data, in-memory + disk) ← NDB API → SQL Nodes (mysqld)
                                                           ↑
                                                    Management Node
                                                    (config, arbitration)
```

- Storage engine is **NDB**, not InnoDB — different feature set (historically
  weaker foreign-key/transaction support than InnoDB, though modern versions
  closed most gaps).
- Auto-sharding of data across data nodes built in.
- Used in **telecom (HLR/HSS systems), real-time bidding, session stores** —
  places needing extreme write throughput + 5-nines uptime, not typical
  CRUD web backends.

**Interview-correct positioning:** you won't reach for NDB Cluster in a
normal Python/Django/FastAPI backend — it's mentioned here so you can say
"NDB exists, it's for telecom-grade in-memory workloads, not what we'd pick
for a typical web app" rather than drawing a blank if asked.

---

## Decision table (the actual interview answer)

| Need | Choice |
|---|---|
| Standard web app, read-heavy | **Primary + read replicas** (async) — simplest, what most teams should default to |
| Need HA with automatic failover, single-writer semantics preserved | **Primary-replica + orchestrator/Group Replication** (single-primary, auto-failover) |
| True multi-region active-active writes required | **Galera** — accept the latency/conflict-retry tradeoff |
| Telecom-grade in-memory, sub-ms, 99.999% uptime | **NDB Cluster** — rare outside that niche |

---

## Interview Q&A

**Q: Why doesn't every high-availability MySQL setup just use Galera?**
A: Synchronous replication means every write waits for the slowest node —
this adds latency proportional to your worst network hop, and under
high write concurrency to the same rows, certification conflicts cause
transaction aborts the application must retry. Most systems don't need true
multi-primary and get better latency from async primary-replica.

**Q: What error should your app expect and handle when using Galera?**
A: A deadlock-style error (`ERROR 1213`) on `COMMIT` due to certification
conflict — this is normal, expected behavior, not a bug. The app must retry
the transaction.

**Q: NDB vs Galera — what's the fundamental difference?**
A: NDB is a different storage engine with its own shared-nothing, in-memory
architecture, sharding data across nodes. Galera is a replication mechanism
sitting on top of standard InnoDB — every node has the full dataset, not a
shard of it.

---

Related: `07_replication_deep.md` (async primary-replica, the default
choice this compares against), [10_postgresql_ha_read_replicas.md](../../04_Database_SQL/10_postgresql_ha_read_replicas.md).
