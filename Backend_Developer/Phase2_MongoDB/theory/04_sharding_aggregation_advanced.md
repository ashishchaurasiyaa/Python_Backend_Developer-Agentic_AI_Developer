# MongoDB Sharding + Advanced Aggregation

> **Interview angle:** "10TB MongoDB collection — sharding kaise design karoge?"

---

## 1. When to Shard

| Data | Action |
|---|---|
| < 100GB | Single replica set, no shard |
| 100GB - 1TB | Sharding optional (capacity planning) |
| 1TB+ | Shard required |
| > 100k writes/sec | Consider sharding |
| Read-heavy + replica set sufficient | Stay un-sharded |

**Shard too early:** ops complexity, hot shards.
**Shard too late:** painful migration.

---

## 2. MongoDB Sharding Architecture

```
            ┌───────────────┐
   Client → │  mongos       │ ← router (multiple for HA)
            └───────┬───────┘
                    │
        ┌───────────┼───────────┐
        ↓           ↓           ↓
   ┌────────┐ ┌────────┐ ┌────────┐
   │Shard 1 │ │Shard 2 │ │Shard 3 │   ← each is a replica set
   │primary │ │primary │ │primary │
   │  ↕     │ │  ↕     │ │  ↕     │
   │secs    │ │secs    │ │secs    │
   └────────┘ └────────┘ └────────┘

         ┌──────────────────┐
         │ Config servers   │ ← stores metadata
         │ (3-node RS)      │
         └──────────────────┘
```

**Components:**
- **mongos**: stateless router, exposed to apps
- **Shards**: each holds subset of data
- **Config servers**: shard metadata, chunk locations

---

## 3. Shard Key Design — Most Important Decision

### Good shard key
- **High cardinality** (many unique values)
- **Low frequency** (no hot keys)
- **Monotonically changing not recommended**
- **Aligns with query pattern**

### Bad shard keys
- `created_at` (monotonic — all writes to one shard)
- `user_type` (low cardinality)
- `boolean field` (only 2 values)

### Compound shard keys (preferred)
```javascript
sh.shardCollection("mydb.orders", {
    user_id: "hashed",      // distribute by user
    created_at: 1            // sub-sort within user
})
```

### Hashed vs Ranged

| | Hashed | Ranged |
|---|---|---|
| Distribution | Random/even | Based on value ranges |
| Sequential writes | Distributed | Hot last shard |
| Range queries | Multi-shard scatter | One shard |
| Use | High write rate | Queries with ranges |

```javascript
// Hashed (even distribution)
sh.shardCollection("mydb.events", { user_id: "hashed" })

// Ranged (good for time-bucketed queries)
sh.shardCollection("mydb.events", { region: 1, user_id: 1 })
```

---

## 4. Shard Key Anti-Patterns

### Anti-pattern 1: Monotonically increasing key
```javascript
sh.shardCollection("mydb.logs", { _id: 1 })   // ObjectIds increase!
```
All new docs → last shard → hot shard.
**Fix:** Use hashed `_id` or compound key.

### Anti-pattern 2: Low cardinality
```javascript
sh.shardCollection("mydb.users", { country: 1 })   // ~200 countries
```
Some countries have millions of users → uneven distribution.

### Anti-pattern 3: Unrelated to queries
Shard by `user_id`, but queries filter by `email` → scatter-gather across all shards.

---

## 5. Chunk Management

```
Collection → split into "chunks" by shard key range
Each chunk: 128MB-1GB target size
Balancer auto-redistributes chunks between shards
```

```javascript
// Check chunk distribution
sh.status()

// Force split
sh.splitAt("mydb.orders", { user_id: 1000 })

// Move chunk manually
sh.moveChunk("mydb.orders", { user_id: 500 }, "shard2")

// Balancer control
sh.startBalancer()
sh.stopBalancer()
```

---

## 6. Targeted vs Scatter-Gather Queries

```javascript
// ✅ TARGETED — uses shard key
db.orders.find({ user_id: 42 })
// Goes to one shard → fast

// ❌ SCATTER-GATHER — all shards
db.orders.find({ email: "a@x.com" })
// Hits ALL shards → slow

// ✅ Compound shard key allows targeted prefix queries
sh.shardCollection("mydb.orders", { region: 1, user_id: 1 })

db.orders.find({ region: "US", user_id: 42 })  // targeted
db.orders.find({ region: "US" })                // targeted (prefix)
db.orders.find({ user_id: 42 })                 // scatter — region not specified
```

**Rule:** Common queries MUST include shard key.

---

## 7. Advanced Aggregation Pipeline

```javascript
db.orders.aggregate([
    // Stage 1: filter (uses indexes)
    { $match: {
        status: "completed",
        created_at: { $gte: ISODate("2024-01-01") }
    }},

    // Stage 2: join with users
    { $lookup: {
        from: "users",
        localField: "user_id",
        foreignField: "_id",
        as: "user"
    }},
    { $unwind: "$user" },

    // Stage 3: project shape
    { $project: {
        order_id: "$_id",
        amount: 1,
        user_name: "$user.name",
        user_email: "$user.email",
        is_premium: { $eq: ["$user.tier", "premium"] }
    }},

    // Stage 4: group + aggregate
    { $group: {
        _id: "$is_premium",
        total_revenue: { $sum: "$amount" },
        order_count: { $sum: 1 },
        avg_order: { $avg: "$amount" }
    }},

    // Stage 5: sort
    { $sort: { total_revenue: -1 } },

    // Output
    { $out: "premium_analytics_2024" }   // save to collection
])
```

---

## 8. Aggregation Stages Reference

| Stage | Purpose |
|---|---|
| `$match` | Filter docs (push early!) |
| `$project` | Reshape (include/exclude fields) |
| `$group` | Aggregate by key |
| `$lookup` | JOIN with another collection |
| `$unwind` | Expand array into multiple docs |
| `$sort` | Order results |
| `$limit` | Cap results |
| `$skip` | Pagination (slow at scale) |
| `$addFields` | Add computed fields |
| `$facet` | Multiple parallel pipelines |
| `$bucket` | Group by ranges |
| `$out` | Save to collection |
| `$merge` | Upsert to collection |
| `$geoNear` | Geo proximity |
| `$graphLookup` | Recursive lookup |

---

## 9. Powerful Patterns

### Pattern 1: Daily Stats
```javascript
db.events.aggregate([
    { $match: { time: { $gte: lastWeek } } },
    {
        $group: {
            _id: {
                day: { $dateToString: { format: "%Y-%m-%d", date: "$time" } },
                event_type: "$type"
            },
            count: { $sum: 1 },
            unique_users: { $addToSet: "$user_id" }
        }
    },
    { $project: {
        day: "$_id.day",
        event_type: "$_id.event_type",
        count: 1,
        unique_user_count: { $size: "$unique_users" }
    }}
])
```

### Pattern 2: Top-N per group
```javascript
// Top 3 products per category
db.products.aggregate([
    { $sort: { category: 1, sales: -1 } },
    {
        $group: {
            _id: "$category",
            top_products: { $push: { name: "$name", sales: "$sales" } }
        }
    },
    {
        $project: {
            category: "$_id",
            top3: { $slice: ["$top_products", 3] }
        }
    }
])
```

### Pattern 3: $facet for multi-aggregation
```javascript
// Get multiple metrics in one query
db.orders.aggregate([
    {
        $facet: {
            "total_revenue": [
                { $group: { _id: null, sum: { $sum: "$amount" } } }
            ],
            "by_status": [
                { $group: { _id: "$status", count: { $sum: 1 } } }
            ],
            "top_users": [
                { $group: { _id: "$user_id", spent: { $sum: "$amount" } } },
                { $sort: { spent: -1 } },
                { $limit: 10 }
            ]
        }
    }
])
```

### Pattern 4: Bucket for histograms
```javascript
db.orders.aggregate([
    {
        $bucket: {
            groupBy: "$amount",
            boundaries: [0, 100, 500, 1000, 5000, Infinity],
            default: "Other",
            output: {
                count: { $sum: 1 },
                avg: { $avg: "$amount" }
            }
        }
    }
])
// Output: { _id: 0, count: 100, avg: 50 }, { _id: 100, count: 200, avg: 250 } ...
```

### Pattern 5: $graphLookup (recursive)
```javascript
// Find all employees under a manager (org tree)
db.employees.aggregate([
    { $match: { _id: managerId } },
    {
        $graphLookup: {
            from: "employees",
            startWith: "$_id",
            connectFromField: "_id",
            connectToField: "manager_id",
            as: "reports",
            maxDepth: 5
        }
    }
])
```

---

## 10. Aggregation Performance

### 1. `$match` early
```javascript
// ✅ Filter first, then lookup
[
    { $match: { status: "active" } },
    { $lookup: { from: "users", ... } }
]

// ❌ Lookup all, filter later
[
    { $lookup: { from: "users", ... } },
    { $match: { status: "active" } }
]
```

### 2. Index for `$match` + `$sort`
Compound index aligned with pipeline order.

### 3. `$project` early to reduce doc size
```javascript
[
    { $match: {...} },
    { $project: { name: 1, total: 1 } },   // remove unused fields
    { $group: {...} }
]
```

### 4. `allowDiskUse`
For large aggregations:
```javascript
db.orders.aggregate([...], { allowDiskUse: true })
```

### 5. `$out` / `$merge` for materialized views
Pre-compute heavy aggregations.

---

## 11. Aggregation on Sharded Collections

Two phases:
1. Each shard runs aggregation locally
2. Results merged on primary shard (or random)

### Best practices
- **Include shard key in `$match`** when possible
- **Use `$lookup` only with secondary collection on same shard**
- **`$merge` requires shard key in output**

### Slow aggregation symptoms
- `$lookup` causing cross-shard query
- `$group` requiring all-shards merge

---

## 12. Python: Motor (async)

```bash
pip install motor pymongo
```

```python
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio

client = AsyncIOMotorClient("mongodb://localhost:27017")
db = client.mydb


# Find with shard key
async def find_user_orders(user_id: int):
    cursor = db.orders.find({"user_id": user_id})    # targeted
    return await cursor.to_list(length=100)


# Aggregation
async def revenue_by_category():
    pipeline = [
        {"$match": {"status": "completed"}},
        {"$group": {
            "_id": "$category",
            "revenue": {"$sum": "$amount"},
            "count": {"$sum": 1}
        }},
        {"$sort": {"revenue": -1}}
    ]
    return await db.orders.aggregate(pipeline).to_list(length=None)


# Bulk operations
from pymongo import InsertOne, UpdateOne

async def bulk_update(updates):
    ops = [UpdateOne({"_id": u["id"]}, {"$set": u["fields"]}) for u in updates]
    return await db.orders.bulk_write(ops, ordered=False)
```

---

## 13. Transactions

```python
async def transfer(from_id, to_id, amount):
    async with await client.start_session() as session:
        async with session.start_transaction():
            await db.accounts.update_one(
                {"_id": from_id},
                {"$inc": {"balance": -amount}},
                session=session,
            )
            await db.accounts.update_one(
                {"_id": to_id},
                {"$inc": {"balance": amount}},
                session=session,
            )
            await db.transactions.insert_one(
                {"from": from_id, "to": to_id, "amount": amount},
                session=session,
            )
```

**Note:** Multi-document transactions work but slower than single-doc atomic operations.
Prefer schema design that needs single-doc operations.

---

## 14. Change Streams (Real-time)

```python
async def watch_orders():
    pipeline = [{"$match": {"operationType": "insert"}}]
    async with db.orders.watch(pipeline) as stream:
        async for change in stream:
            print(f"New order: {change['fullDocument']}")
            # Real-time processing: send to Kafka, update cache, etc.
```

Useful for: real-time dashboards, CDC, cache invalidation.

---

## 15. Atlas Search (Lucene-powered)

```javascript
// On MongoDB Atlas — full-text search via $search
db.products.aggregate([
    {
        $search: {
            index: "products_search",
            text: {
                query: "iphone",
                path: ["name", "description"],
                fuzzy: { maxEdits: 1 }
            }
        }
    },
    { $project: { name: 1, score: { $meta: "searchScore" } } },
    { $limit: 10 }
])
```

Atlas Search = Elasticsearch alternative without separate cluster.

---

## 16. Schema Design Tips

### Embed vs Reference
```javascript
// ✅ Embed when accessed together always
{
    _id: "user_42",
    name: "Alice",
    addresses: [
        { type: "home", street: "..." },
        { type: "work", street: "..." }
    ]
}

// ✅ Reference when accessed separately
{
    _id: "user_42",
    address_ids: ["addr_1", "addr_2"]
}
// And separate addresses collection

// Combine: extended reference (denormalized for read speed)
{
    _id: "order_1",
    user_id: "user_42",
    user_email: "a@x.com",   // duplicated for fast access
    user_name: "Alice"
}
```

### Schema patterns
- **Polymorphic**: different fields per type
- **Bucket**: group time-series in arrays
- **Outlier**: separate huge docs
- **Computed**: pre-compute aggregations
- **Subset**: store frequently accessed subset in main doc

---

## 17. Interview Questions

**Q1: Shard key kaise choose?**
High cardinality, low frequency, aligned with query patterns. Compound key often best.

**Q2: Monotonic shard key kya problem?**
All writes go to last shard → hot shard. Use hashed or compound key.

**Q3: Aggregation pipeline?**
Stages: $match → $project → $lookup → $group → $sort. Push $match early.

**Q4: Targeted vs scatter-gather?**
Targeted = uses shard key, hits one shard. Scatter-gather = all shards (slow).

**Q5: $lookup vs separate query?**
$lookup is server-side JOIN. Slower than embedded data but needed for normalized data.

**Q6: Multi-doc transaction?**
Supported via sessions. Slower than single-doc. Prefer single-doc design.

**Q7: When to use Atlas Search?**
Full-text + faceted search without Elasticsearch. On MongoDB Atlas.

---

## 18. Best Practices

1. **Plan shard key carefully** — hard to change later
2. **Compound shard keys** for query flexibility
3. **`$match` early** in aggregation pipeline
4. **Indexes** matching pipeline stages
5. **Embed for 1:1, reference for 1:N**
6. **Atlas Search** for full-text needs
7. **Change Streams** for real-time
8. **Avoid scatter-gather** queries in sharded
9. **Monitor balancer** + chunk distribution
10. **Schema validation** via JSON Schema constraint

---

## Related
- [[01_basics_installation_crud]]
- [[02_aggregation_indexes]]
- [[03_advanced_motor_fastapi]]
- [[../../Phase2_Database/10_postgresql_partitioning_sharding]]
