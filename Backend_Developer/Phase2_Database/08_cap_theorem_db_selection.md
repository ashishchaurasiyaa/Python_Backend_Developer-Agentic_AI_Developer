# CAP Theorem, Consistency Models & Database Selection Guide

## Quick Concepts
- **CAP theorem** = Consistency, Availability, Partition tolerance — pick 2 of 3
- **Consistency** = every read returns latest write (not eventual)
- **Availability** = every request gets a response (not error)
- **Partition tolerance** = system works even if network splits nodes
- **PACELC** = extension of CAP — latency vs consistency tradeoff
- **Eventual consistency** = all nodes will converge — but not immediately
- **Strong consistency** = read always returns latest committed write
- **BASE** = Basically Available, Soft state, Eventually consistent (NoSQL)
- **ACID** = Atomicity, Consistency, Isolation, Durability (RDBMS)

---

## Interview Questions & Answers

### Q1: CAP Theorem explain karo. Real databases kahan fit hote hain?

**Answer:**
```
─── CAP Theorem ───
In a distributed system, you can guarantee only 2 of 3:

  C — Consistency:     Every read sees the most recent write
  A — Availability:    Every request gets a non-error response
  P — Partition tol.:  System works despite network partition

REALITY: Partition tolerance is NON-NEGOTIABLE in distributed systems
(networks DO fail). So real choice is: CP or AP.

─── Where real databases sit ───

  CP (Consistent + Partition tolerant):
    PostgreSQL (cluster mode), HBase, MongoDB (default w/ write concern)
    → On partition: refuse writes to maintain consistency
    → Bank transactions, inventory, anything where stale data = disaster

  AP (Available + Partition tolerant):
    Cassandra, DynamoDB, CouchDB, Redis (cluster)
    → On partition: still serve reads/writes (may be stale)
    → Shopping carts, user preferences, analytics, anything where
      brief inconsistency is acceptable

  CA (Consistent + Available) — NOT truly distributed:
    Single-node PostgreSQL, MySQL (single node)
    → No partition tolerance → fails in distributed setup

─── PACELC (more practical than CAP) ───
  If Partition:  choose C (consistency) vs A (availability)
  Else (normal): choose L (latency) vs C (consistency)

  DynamoDB: PA/EL  — available on partition, low latency over consistency
  PostgreSQL: PC/EC — consistent on partition, consistent over latency
  Cassandra: PA/EL  — available, eventual consistency, low latency
```

---

### Q2: Database selection guide — kaunsa kab use karo?

**Answer:**
```
─── PostgreSQL ───
Best for: primary application database
  ✓ ACID transactions
  ✓ Complex queries, JOINs, aggregations
  ✓ JSON/JSONB (semi-structured data)
  ✓ Full-text search (tsvector)
  ✓ Vector similarity (pgvector)
  ✓ Time-series (TimescaleDB extension)
  ✓ < 10TB data, complex business logic
Use: e-commerce, fintech, SaaS apps, anything needing transactions

─── MongoDB ───
Best for: flexible schema, document-oriented
  ✓ Nested documents (no JOIN overhead)
  ✓ Schema-less / frequent schema changes
  ✓ Horizontal scaling (sharding built-in)
  ✓ Geospatial queries
  ✗ No real multi-document ACID (pre-4.0)
  ✗ Complex aggregations awkward
Use: CMS, product catalogs, real-time analytics, IoT events

─── Redis ───
Best for: in-memory speed, secondary store
  ✓ Cache (session, API responses, computed values)
  ✓ Rate limiting (sorted sets, Lua)
  ✓ Leaderboards (sorted sets)
  ✓ Pub/Sub (real-time notifications)
  ✓ Distributed locks
  ✓ Task queues (lists)
  ✗ Not primary DB — data too valuable for volatile store
Use: alongside PostgreSQL, never as sole DB

─── Cassandra ───
Best for: massive write throughput, time-series, append-only
  ✓ 1M+ writes/second (distributed)
  ✓ Linear horizontal scaling
  ✓ No single point of failure
  ✓ Time-series, event logs, activity feeds
  ✗ No JOINs (denormalize everything)
  ✗ Eventual consistency (not for financial data)
  ✗ Query pattern must be known upfront
Use: IoT sensor data, activity feeds, Netflix-style event logs

─── Elasticsearch ───
Best for: full-text search, log analytics
  ✓ Full-text search with relevance ranking
  ✓ Aggregations on log data
  ✓ Near real-time search (1 second)
  ✓ Horizontal scaling
  ✗ Not a primary DB — use as search index
  ✗ No transactions
Use: search (e-commerce, docs), log analysis (ELK stack)

─── ClickHouse ───
Best for: OLAP, analytics, large aggregations
  ✓ 100x faster than PostgreSQL for analytics queries
  ✓ Column-oriented storage — skip unused columns
  ✓ Massive compression
  ✗ Poor for OLTP (updates/deletes expensive)
Use: dashboards, business intelligence, analytics over billions of rows

─── Pinecone / Qdrant / Weaviate ───
Best for: vector search at scale
  ✓ 100M+ vectors — ANN at <10ms
  ✓ Advanced filtering
  ✗ Separate infra — sync with primary DB
Use: when pgvector is too slow (> 10M vectors)

─── DynamoDB ───
Best for: serverless, predictable high-throughput, key-value
  ✓ Auto-scaling, serverless
  ✓ Single-digit millisecond latency at any scale
  ✓ Global tables (multi-region)
  ✗ No complex queries — access pattern must be pre-designed
  ✗ Expensive at high read units
Use: AWS-native apps, gaming leaderboards, shopping carts
```

---

### Q3: Consistency models — Strong, Eventual, Causal kya hain?

**Answer:**
```
─── Strong Consistency ───
  Every read sees the latest write — guaranteed.
  How: single leader writes, synchronous replication to majority
  Cost: higher latency, lower availability on partition

  Examples: PostgreSQL (single node), Spanner (TrueTime)
  Use: bank transfers, inventory, anything where stale data = loss

─── Eventual Consistency ───
  All replicas will converge eventually — but not immediately.
  Reads may return stale data for seconds/milliseconds.
  
  Examples: Cassandra, DynamoDB (default), DNS
  Use: user profiles, product views, social feeds

  ─── Variants ───
  Read-your-writes:  you always see your own writes (others may not)
  Monotonic reads:   you never see older data than you saw before
  Causal:            causally related writes seen in order

─── Linearizability ───
  Strongest consistency — single-copy semantics.
  Once write returns, all subsequent reads see it.
  Cost: high latency, requires consensus (Raft/Paxos)
  Examples: etcd, ZooKeeper, Spanner

─── Practical Python example ───

  # Strong consistency (PostgreSQL):
  async with session.begin():
      user = await session.get(User, user_id)  # always latest
      user.credits -= 100
      # commit → immediately visible to all

  # Eventual consistency (DynamoDB/boto3):
  dynamodb.put_item(TableName="users", Item={...})
  # Another server may read stale credits for ~100ms

─── Redis replication consistency ───
  Redis replica is ASYNCHRONOUS by default:
    WAIT 1 100   -- wait for 1 replica to ack, timeout 100ms
  For strong consistency: WAIT numreplicas timeout before reading from replica
```

---

### Q4: Sharding strategies — horizontal scaling kaise?

**Answer:**
```
─── Sharding = horizontal partitioning across multiple DB servers ───

  ─── Range sharding ───
  users with id 1-1M      → shard 1
  users with id 1M-2M     → shard 2
  
  Pros:  simple, range queries efficient
  Cons:  hotspots (new users go to last shard — write imbalance)

  ─── Hash sharding ───
  shard = hash(user_id) % num_shards
  
  Pros:  even distribution
  Cons:  range queries need all shards, resharding is painful

  ─── Directory sharding ───
  Lookup table: user_id → shard mapping
  
  Pros:  flexible, easy rebalancing
  Cons:  lookup table is bottleneck / single point of failure

  ─── Geo sharding ───
  US users → US shard
  EU users → EU shard (GDPR compliance too)
  
  Pros:  low latency, compliance
  Cons:  cross-region queries expensive

─── When to shard? ───
  DO NOT shard prematurely:
    1. Read replicas first (read-heavy)
    2. Caching layer (Redis)
    3. Vertical scaling (bigger server)
    4. Partitioning (PostgreSQL PARTITION BY)
    5. Only THEN shard if still insufficient

  Shard when:
    - Single node can't handle write throughput
    - Data > 10TB (even with SSDs)
    - Specific compliance requires data locality

─── PostgreSQL sharding options ───
  Citus:          extension — distributed PostgreSQL
  pg_partman:     automated partitioning (not true sharding, but helps)
  Application:    route by shard key in code (most control)
  PgPool-II:      middleware with partition routing
```

---

### Q5: ACID vs BASE — kya choose karo?

**Answer:**
```
─── ACID (Relational DBs) ───
  Atomicity:    all or nothing
  Consistency:  DB invariants maintained
  Isolation:    concurrent transactions don't interfere
  Durability:   committed = persisted

  Use ACID when:
    - Money, inventory, bookings — data loss = business loss
    - Complex business rules with constraints
    - Regulatory compliance (audit trail)

─── BASE (NoSQL) ───
  Basically Available:   system stays up (may return stale data)
  Soft state:            data may change over time (convergence)
  Eventually consistent: replicas converge

  Use BASE when:
    - High availability > perfect consistency
    - Massive scale, simple key-value access
    - Temporary inconsistency acceptable (social feeds, analytics)

─── Hybrid approach (common in production) ───
  PostgreSQL:   source of truth (ACID) — orders, users, payments
  Redis:        cache layer (BASE) — sessions, counters, rate limits
  Elasticsearch: search index (eventual) — search, analytics
  Cassandra:    event log (AP) — activity feeds, audit events

  Rule: "Strong consistency where money moves, eventual where it doesn't"
```

---

## Summary

| Database | Type | Consistency | Best Use Case |
|----------|------|-------------|---------------|
| PostgreSQL | RDBMS | Strong (CP) | Primary app DB, ACID transactions |
| MongoDB | Document | Configurable | Flexible schema, nested docs |
| Redis | In-memory | Eventual (AP) | Cache, queues, leaderboards |
| Cassandra | Wide-column | Eventual (AP) | Massive writes, time-series |
| Elasticsearch | Search | Eventual | Full-text search, log analytics |
| ClickHouse | Columnar | Strong | OLAP, analytics |
| DynamoDB | Key-value | Configurable | Serverless, AWS-native |
| Pinecone/Qdrant | Vector | Eventual | Semantic search at scale |

| Consistency Level | Latency | Use When |
|-------------------|---------|----------|
| Strong / Linearizable | High | Financial data, inventory |
| Read-your-writes | Medium | User profile, settings |
| Eventual | Low | Feeds, analytics, counters |
| Causal | Medium | Collaborative apps, chat |
