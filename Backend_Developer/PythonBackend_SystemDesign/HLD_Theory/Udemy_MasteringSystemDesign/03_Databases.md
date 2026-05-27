# 03 — Databases

## SQL vs NoSQL — the core distinction

| Aspect | SQL (Relational) | NoSQL |
|--------|------------------|-------|
| **Schema** | Strict, predefined | Flexible / schemaless |
| **Joins** | First-class | Often unavailable or expensive |
| **Transactions** | ACID (full) | Often limited (single-doc, single-partition) |
| **Scaling** | Vertical first; sharding hard | Horizontal-native |
| **Query language** | SQL (declarative) | Varied (key lookups, MQL, CQL, etc.) |
| **Best for** | Complex relationships, strong consistency | High write throughput, flexible schema, huge scale |
| **Examples** | Postgres, MySQL, Oracle, SQL Server | MongoDB, Cassandra, DynamoDB, Redis, HBase |

### NoSQL sub-types

1. **Key-value** — Redis, DynamoDB, Riak. O(1) lookup by key. Use for: caches, sessions, leaderboards.
2. **Document** — MongoDB, Couchbase. JSON-like nested docs. Use for: catalogs, profiles, CMS.
3. **Column-family / wide-column** — Cassandra, HBase, ScyllaDB. Rows with sparse columns, partitioned by key. Use for: time-series, event logs, analytics.
4. **Graph** — Neo4j, Neptune, ArangoDB. Nodes + edges with properties. Use for: social graph, recommendations, fraud detection.
5. **Search** — Elasticsearch, OpenSearch, Solr. Inverted indexes for full-text. Use for: search, log analytics.
6. **Time-series** — InfluxDB, TimescaleDB, Prometheus. Optimized append-mostly time-indexed data. Use for: metrics, IoT.

## ACID vs BASE

**ACID** (traditional RDBMS):
- **A**tomicity — transaction is all-or-nothing
- **C**onsistency — invariants preserved (FK, CHECK, etc.)
- **I**solation — concurrent transactions don't observe each other's partial state
- **D**urability — committed data survives crashes

**BASE** (NoSQL/distributed):
- **B**asically **A**vailable — always responds, even if degraded
- **S**oft state — data may change without input (replication, TTL)
- **E**ventual consistency — converges over time

Most modern systems pick mixed: ACID locally (within a shard) + BASE across shards/replicas.

## Isolation Levels

From weakest to strongest (anomalies prevented in parens):

1. **Read Uncommitted** — sees uncommitted changes. Allows dirty reads.
2. **Read Committed** — only committed data visible. *Default for Postgres, Oracle, SQL Server.* Allows non-repeatable reads.
3. **Repeatable Read** — same row read returns same value within a txn. *Default for MySQL.* Allows phantom reads.
4. **Snapshot Isolation** — txn sees a consistent snapshot as of start. (MVCC-based; prevents most anomalies but allows write skew.)
5. **Serializable** — equivalent to running txns one at a time. Prevents all anomalies; slowest.

**Common interview trap:** "MySQL default is REPEATABLE READ but Postgres default is READ COMMITTED — applications written for one may misbehave on the other."

## Indexes

### B-tree indexes (default in RDBMS)

- Balanced tree, O(log N) lookup.
- Great for equality and range queries (`WHERE x = 5`, `WHERE x BETWEEN 1 AND 10`).
- Maintains sort order — useful for `ORDER BY`.
- Update cost: O(log N) per insert/delete.

### LSM-tree indexes (Cassandra, RocksDB, LevelDB)

- Writes buffered in-memory (memtable), flushed to immutable sorted files (SSTables).
- Background compaction merges files.
- Excellent write throughput, slower reads (must check multiple SSTables; mitigated by Bloom filters).
- Used in: Cassandra, HBase, RocksDB, Kafka log compaction.

### Hash indexes

- O(1) average lookup by exact key.
- No range queries, no ordering.
- Used in: Redis, in-memory caches, some Postgres extensions.

### Inverted indexes

- Maps terms → list of documents containing them.
- Backbone of Elasticsearch, Solr, full-text search.
- Built using techniques like tokenization, stemming, TF-IDF.

### Composite indexes

`CREATE INDEX idx ON users(country, age);`

Order matters! Index supports queries on `country` alone or `(country, age)` but NOT `age` alone. Always lead with the most selective column that's used in filters.

### Covering indexes

Include all columns needed by a query, so the query is satisfied from the index alone (no table read). Trades index size for query speed.

## Replication

### Leader-Follower (master-slave)

- One leader accepts writes, followers replicate.
- Reads can go to followers (scales reads).
- **Async replication:** fast, but followers lag. Risk of stale reads, data loss on leader failure.
- **Sync replication:** safer but slower; usually one sync follower + several async.
- **Failover:** promote a follower if leader dies. Hard to do correctly (split-brain, lost writes).

Used in: Postgres streaming replication, MySQL binlog replication, MongoDB replica sets.

### Multi-Leader

- Multiple leaders accept writes, replicate to each other.
- Useful for multi-region writes (each region has its own leader).
- **Hard problem:** conflict resolution when same row updated in two leaders concurrently.
  - Strategies: last-write-wins (LWW), application-level merge, CRDTs.

Used in: CouchDB, Cassandra (effectively), some MySQL setups with Tungsten.

### Leaderless

- Every node accepts writes. Client writes to W nodes, reads from R nodes.
- If `W + R > N` (replica count), reads see latest write.
- Quorum-based; "Dynamo-style."
- Conflicts resolved via vector clocks, version vectors, or LWW.

Used in: DynamoDB, Cassandra, Riak.

## Sharding (Partitioning)

Splitting data across multiple servers, each holding a subset.

### Strategies

| Strategy | How | Pros | Cons |
|----------|-----|------|------|
| **Range-based** | shard by ranges of key (A-M, N-Z) | Range queries efficient | Hotspots if traffic uneven |
| **Hash-based** | shard = hash(key) % N | Even distribution | Range queries hit all shards |
| **Consistent hashing** | Map keys + nodes onto a ring | Adding/removing node moves O(K/N) keys | More complex; slight skew |
| **Directory / lookup** | Service maps key → shard | Flexible rebalancing | Lookup service is bottleneck |
| **Geographic** | shard by user region | Data locality, regulatory | Cross-region queries slow |

### Choosing the shard key

The most consequential decision. A good shard key:

- Has **high cardinality** (many distinct values)
- Distributes writes and reads evenly (no hotspots)
- Matches access patterns (queries filter by the shard key when possible)
- Doesn't change (immutable)

Common choices: user_id, tenant_id, geo region. **Bad:** date (everyone hits "today" shard).

### Resharding pain

When you outgrow N shards, moving to N' shards requires migrating data. Consistent hashing minimizes movement, but it's still operationally hard. Plan headroom (start with more virtual shards than physical nodes).

## Transactions in distributed systems

### Two-phase commit (2PC)

1. **Prepare:** coordinator asks all participants to "prepare." Each writes data + ready-to-commit log entry.
2. **Commit:** if all replied OK, coordinator says "commit." Otherwise "abort."

**Problems:** blocking (if coordinator dies after prepare, participants wait), slow (sync coordination), partial failures are messy.

### Saga pattern

For long-running multi-service transactions. Decompose into a sequence of local transactions; each has a compensating action for rollback.

Two flavors:
- **Choreography:** services publish events, others react. Decentralized.
- **Orchestration:** central service tells each step what to do.

Used heavily in microservices (e.g., order → reserve inventory → charge card → notify warehouse; if any step fails, undo prior steps).

## Choosing a Database — decision tree

```
1. Strong consistency required for the whole workload?
   YES → SQL (Postgres / MySQL) or Spanner / CockroachDB
   NO  → continue

2. Will you store > 1 TB or run > 100K QPS?
   NO  → Postgres is usually enough
   YES → continue

3. Access pattern primarily key-lookup?
   YES → DynamoDB / Redis / Cassandra
   NO  → continue

4. Full-text search central?
   YES → Elasticsearch (as secondary, not primary store)

5. Highly relational (joins everywhere)?
   YES → Postgres / MySQL with read replicas, eventually sharded

6. Graph traversals (n-hops)?
   YES → Neo4j or graph layer on top of KV store
```

## Interview Q&A

**Q1: When would you choose Cassandra over Postgres?**
*A:* When you need horizontal write scale (Postgres maxes ~100K writes/sec on one box), tolerate eventual consistency, have a key-based access pattern, and don't need joins. Classic fits: time-series, event logs, IoT, large-scale messaging history. Don't pick Cassandra for relational workloads or low-write-volume apps.

**Q2: How do you design indexes for a query `WHERE status = 'active' AND created_at > now() - 7d ORDER BY created_at DESC`?**
*A:* Composite index `(status, created_at DESC)`. Status first (equality), then created_at (range + sort). Postgres can use it for both filter and order. Verify with EXPLAIN.

**Q3: Master DB is at CPU limit. What are your options?**
*A:* (1) Move reads to replicas. (2) Add caching (Redis/Memcached) for hot data. (3) Optimize slow queries (indexes, denorm). (4) Vertical scale (bigger instance). (5) Connection pooling (pgbouncer). (6) Move write-heavy domains to separate DBs (functional sharding). (7) Last resort — horizontal sharding.

**Q4: Explain the difference between optimistic and pessimistic locking.**
*A:* **Pessimistic** acquires a lock before reading (`SELECT FOR UPDATE`). Prevents conflicts but reduces concurrency. **Optimistic** reads without locking, checks version/timestamp on write; if changed, retry. Better throughput when conflicts are rare. Use pessimistic for hotly contested rows (inventory), optimistic for low-contention edits.

**Q5: What's a write skew? Give an example.**
*A:* Two txns each read a set of rows, then update *different* rows based on the read, but the combined effect violates an invariant. Classic example: on-call rotation requires ≥1 doctor on duty. Two doctors simultaneously read "2 on duty" then each set themselves off-duty. Both txns commit; now 0 on duty. Snapshot isolation allows this; serializable prevents it.

**Q6: How would you design schema for a social network feed?**
*A:* Two main entities: User (id, name, ...) and Post (id, author_id, content, created_at). Followers is many-to-many: `follows(follower_id, followee_id)`. For feed: either pull (query posts from people I follow on demand) or push (precomputed fan-out into a per-user timeline table/cache). Push for celebrities is expensive — hybrid: fan-out for normal users, pull for celebs at read time.

## Further reading

- *DDIA* — Ch 2 (Data Models), Ch 3 (Storage), Ch 5 (Replication), Ch 6 (Partitioning), Ch 7 (Transactions)
- Existing notes: `../11_SQL.md` and `../12_NoSQL.md` if present
- "Designing for Scale with Amazon DynamoDB" — AWS re:Invent talks
