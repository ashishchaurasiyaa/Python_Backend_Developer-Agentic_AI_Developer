# 🗄️ Database Scaling — Sharding, Replication, Architecture

> **Target:** 3-5 YOE | **Goal:** Database ko massive scale tak kaise le jaaye — replication, sharding, partitioning.

---

## Part 1: WHAT — Database Scaling Kya Hai?

### Definition

> Database ko **more data, more users, more queries** handle karne layak banana — without compromising performance.

### Real-Life Analogy 🏢

Soch ek **library**:
- 1 librarian: 100 students/day OK
- 1000 students/day: bottleneck
- Need: more librarians (replication), more libraries (sharding)

---

## Part 2: WHY — Scaling Critical?

### Reason 1: Growth

Users grow, data grows.
Day 1: 100 users.
Year 5: 10 million users.

### Reason 2: Performance

Slow DB = slow app = lost users.

### Reason 3: Reliability

Single DB = single point of failure.

### Reason 4: Cost

Scaling smartly = cheaper than throwing hardware.

---

## Part 3: TYPES OF SCALING

### Vertical Scaling (Scale Up)

> **Bigger machine** — more CPU, RAM, disk.

#### Pros
- Simple
- No app changes
- Same data, same queries

#### Cons
- Expensive
- Hardware limits
- Downtime to upgrade

#### Limit
- AWS biggest RDS: 96 vCPU, 768 GB RAM
- Eventually hit ceiling

### Horizontal Scaling (Scale Out)

> **More machines** — distribute load.

#### Pros
- Theoretically unlimited
- Cheaper (commodity hardware)
- HA built-in

#### Cons
- Complex
- App changes needed
- Distributed challenges

#### Most apps use both eventually

---

## Part 4: READ REPLICATION

### Concept

> **One master (writes), multiple replicas (reads).**

```
WRITES → MASTER
READS  → REPLICA 1, REPLICA 2, REPLICA 3

Master replicates writes to replicas.
```

### Benefits

#### Read Scaling
- 1 master: 1000 reads/sec
- + 3 replicas: 4000 reads/sec

#### High Availability
- Master down → promote replica
- Failover

#### Geographic Distribution
- Replica in each region
- Local reads faster

### Drawbacks

#### Replication Lag
- Replica may be slightly behind
- Read-your-writes issue

#### Complexity
- Failover logic
- Consistency models

#### Cost
- More servers

---

## Part 5: REPLICATION MODES

### Synchronous

> **Master waits for replica acknowledgment.**

Pros: No data loss
Cons: Slow writes

### Asynchronous

> **Master doesn't wait.**

Pros: Fast writes
Cons: Data loss possible on master failure

### Semi-Sync

> **Wait for at least one replica.**

Balance between safety and speed.

---

## Part 6: MASTER-MASTER REPLICATION

### Concept

> **Multiple masters, all accept writes.**

```
Master 1 ←→ Master 2
Both write. Both replicate to each other.
```

### Issues

#### Conflicts
- User updates same row on both masters
- How to resolve?

#### Solutions
- Last write wins
- Application-level resolution
- Vector clocks

### When OK
- Geographically distributed
- Tolerate some conflicts
- Can resolve them

### When NOT
- Strict consistency needed
- High conflict rate

---

## Part 7: SHARDING (Horizontal Partitioning)

### Concept

> **Split data across multiple databases.** Each shard has subset.

```
Without sharding:
  ONE DB: users 1-10,000,000

With sharding:
  DB 1: users 1-2,500,000
  DB 2: users 2,500,001-5,000,000
  DB 3: users 5,000,001-7,500,000
  DB 4: users 7,500,001-10,000,000
```

### Benefits

- Unlimited storage
- Unlimited write throughput
- Independent scaling

### Drawbacks

- Application complexity
- Cross-shard queries hard
- Re-sharding painful

---

## Part 8: SHARDING STRATEGIES

### Strategy 1: Range-Based

> **User ID 1-1M → Shard 1, etc.**

#### Pros
- Simple
- Range queries fast

#### Cons
- Hot spots (new users on one shard)
- Uneven distribution

### Strategy 2: Hash-Based

> **hash(user_id) % num_shards = shard_index**

#### Pros
- Even distribution
- No hot spots

#### Cons
- Range queries hard
- Re-sharding harder

### Strategy 3: Consistent Hashing

> **Hash ring** — adding/removing shards moves minimum data.

#### Pros
- Minimal data movement
- Used by Cassandra, DynamoDB

#### Cons
- Complex

### Strategy 4: Directory-Based

> **Lookup table** maps key to shard.

#### Pros
- Flexible
- Can rebalance

#### Cons
- Lookup overhead
- Lookup service can fail

### Strategy 5: Geographic

> **Users in India → India shard.**

#### Pros
- Low latency
- Compliance

#### Cons
- Uneven sizes
- Cross-region queries

---

## Part 9: CHOOSING SHARD KEY

### Critical Decision

> **Bad shard key = nightmare to fix.**

### Good Shard Keys

- Evenly distributes data
- Aligns with queries
- Stable (doesn't change)

### Common Choices

- User ID (most common)
- Geographic region
- Time (rolling)
- Tenant ID (multi-tenant)

### Bad Shard Keys

- Auto-increment ID (sequential = hot spots)
- Date (last shard hot)
- Mutable values

---

## Part 10: VERTICAL PARTITIONING

### Concept

> **Split columns across databases.**

```
User table:
- Basic: id, name, email → DB1
- Profile: bio, photo, preferences → DB2
- Activity: last_seen, post_count → DB3
```

### When Useful

- Different access patterns
- Large columns (photos)
- Compliance (PII separate)

### Drawbacks

- Joins across DBs (slow)
- Coordination overhead

---

## Part 11: DATABASE-LEVEL PARTITIONING

### PostgreSQL Partitioning

> Table split into partitions by criteria.

```
orders table:
- orders_2024 (partition)
- orders_2025 (partition)
- orders_2026 (partition)
```

Queries automatically use right partition.

### Benefits

- Better query performance
- Easier archival
- Independent maintenance

### Use Cases

- Time-series data
- Logs
- Large tables

---

## Part 12: CACHING (Database Side)

### Application-Level Cache

> Cache query results in Redis/Memcached.

Covered separately.

### Database Query Cache

> DB caches recent query results.

Built into PostgreSQL, MySQL.
Limited use.

### Materialized Views

> **Pre-computed query results stored.**

```
CREATE MATERIALIZED VIEW daily_sales AS
  SELECT date, SUM(amount) FROM orders GROUP BY date;
```

Refresh periodically.

#### Pros
- Fast queries (no compute)
- For analytical workloads

#### Cons
- Stale data
- Refresh cost

---

## Part 13: INDEXING DEEP

### What Index Does

> **Speed up specific queries.**

Without index: scan all rows.
With index: jump directly.

### B-Tree Index (Default)

Most common.
Good for:
- Equality (`=`)
- Range queries (`<`, `>`, `BETWEEN`)
- Sorting

### Hash Index

Good for: equality only.
Not for: ranges.

### Bitmap Index

Good for: low-cardinality data.

### Full-Text Index

For: text search.

### Spatial Index

For: geographic data.

### Composite Index

> Index on multiple columns.

```
INDEX (city, age, gender)
```

Useful when:
- Queries on combinations
- Order matters

### Covering Index

> Index includes all queried columns.

Query never hits table.

### Trade-offs

#### Indexes Cost
- Storage
- Slower writes (each write updates indexes)
- Memory

#### Don't Index
- Rarely queried columns
- Heavily updated tables
- Small tables

---

## Part 14: QUERY OPTIMIZATION

### EXPLAIN

> See query plan.

Shows:
- Indexes used
- Join order
- Estimated cost
- Actual time

### Common Issues

#### Missing Index
- Sequential scan
- Add index

#### Bad Join Order
- DB chose wrong order
- Rewrite query

#### N+1 Queries
- 1 query + N follow-ups
- Use JOIN or batch fetch

---

## Part 15: CONNECTION POOLING

### Why Needed

> Opening DB connection = expensive (10-50ms).

### Pool

> Maintain reusable connections.

Pool size:
- Too small: queue, slow
- Too big: DB overwhelmed

Typical: 10-50 per app instance.

### Tools

- PgBouncer (PostgreSQL)
- ProxySQL (MySQL)
- Application-level (SQLAlchemy)

---

## Part 16: HIGH AVAILABILITY (HA)

### Single DB

- Backup: daily
- Restore: hours
- Data loss: up to 24 hours
- Downtime: significant

### Master + Standby

- Standby ready to take over
- Failover: minutes
- Data loss: minimal (sync replication)

### Cluster (3+ Nodes)

- Auto-failover
- Failover: seconds
- High availability
- No data loss (with quorum)

---

## Part 17: BACKUPS

### Full Backup

> Complete copy of database.

Slow. Done weekly typically.

### Incremental Backup

> Only changes since last backup.

Fast. Done daily.

### Point-in-Time Recovery

> Restore to any moment.

Done via:
- Continuous archiving
- Transaction logs

### Off-Site

> **Different region.**

Disaster recovery.

### Test Restores

> Backup useless if can't restore.

Test quarterly.

---

## Part 18: NoSQL SCALING

### MongoDB

#### Replica Set
- 3-5 nodes
- One primary, rest secondary
- Automatic failover

#### Sharded Cluster
- Multiple replica sets (shards)
- Config servers (metadata)
- Routers (mongos)

### Cassandra

#### Built-In Distribution
- All nodes equal
- Consistent hashing
- Tunable consistency

#### Scale
- Add nodes → automatic rebalance
- Geographic distribution

### DynamoDB

#### Auto-Scaling
- Managed by AWS
- Provisioned or on-demand

#### Partition Keys
- Hash-based sharding
- Hot partitions = problem

---

## Part 19: DATA WAREHOUSING

### OLTP vs OLAP

#### OLTP (Online Transaction Processing)
- Small queries
- High concurrency
- Real-time
- PostgreSQL, MySQL

#### OLAP (Online Analytical Processing)
- Big aggregations
- Low concurrency
- Reports
- Snowflake, BigQuery, Redshift

### Separation

> Transactional DB for app.
> Analytics DB for reports.

ETL pipelines sync.

---

## Part 20: SCALING JOURNEY

### Stage 1: Single DB

```
USER → APP → DB
```

Works for: < 1k users typically.

### Stage 2: Read Replicas

```
USER → APP → DB Master (writes)
                ↓
            DB Replicas (reads)
```

Works for: 10k+ users.

### Stage 3: Caching

```
USER → APP → CACHE → DB
              ↓
           Backend
```

Works for: 100k+ users.

### Stage 4: Sharding

```
USER → APP → Shard Router → DB Shards
```

Works for: 1M+ users.

### Stage 5: Microservices + Separate DBs

```
USER → API GATEWAY → Multiple Services → Multiple DBs
```

Each service own DB.

### Stage 6: Multi-Region

```
USER → Region 1 OR Region 2 → Replicated DBs
```

Global scale.

---

## Part 21: WHEN TO SCALE

### Signs

- Slow queries
- Connection pool exhausted
- Disk full
- CPU pegged
- Response time degrading

### Order of Optimization

1. **Index queries** (cheap)
2. **Add cache** (medium)
3. **Read replicas** (medium)
4. **Vertical scale** (medium)
5. **Sharding** (expensive)
6. **Microservices** (very expensive)

---

## Part 22: COMMON PITFALLS

### Pitfall 1: Premature Sharding

> Shard before needed.

Complex without benefit.

### Pitfall 2: Wrong Shard Key

> Hard to change.

Choose carefully.

### Pitfall 3: No Indexes

> Or wrong indexes.

Performance disaster.

### Pitfall 4: Ignoring Replication Lag

> Read-your-writes broken.

Need awareness.

### Pitfall 5: No Backups

> Or untested backups.

Disaster waiting.

### Pitfall 6: Storage Surprises

> Disk fills up unexpectedly.

Monitor.

---

## Part 23: DATABASE PER SERVICE (Microservices)

### Pattern

> Each microservice owns its DB.

### Pros

- Independent scaling
- Tech choice freedom
- Loose coupling

### Cons

- Cross-service queries hard
- Distributed transactions
- Data duplication

### Solutions

- Event-driven sync
- API composition
- Materialized views

---

## Part 24: Q&A

### Q: When to add read replicas?
**A**: When reads > 5x writes, or read load high.

### Q: Sharding worth it?
**A**: Above ~1TB or ~10k QPS. Otherwise vertical first.

### Q: SQL or NoSQL for scale?
**A**: Both can scale. Choose for use case, not scale alone.

### Q: How much replication lag is OK?
**A**: < 1 second typically. < 100ms ideal.

### Q: Single DB max scale?
**A**: Can hit 100k QPS with optimization. After, must scale out.

### Q: Cost of database scaling?
**A**: Grows fast. Optimize before scaling out.

### Q: NoSQL vs SQL scaling?
**A**: NoSQL more native to horizontal. SQL needs more work.

---

## 🎯 Bhai's Final Words

> **Database scaling is gradual. Start simple. Add complexity only when needed. Premature optimization = engineering disaster.**

3 Mantras:
1. **Index first** (cheapest win)
2. **Cache second** (huge impact)
3. **Shard last** (expensive)

After mastering DB scaling, you can handle any system at scale. Senior interview gold. 🚀
