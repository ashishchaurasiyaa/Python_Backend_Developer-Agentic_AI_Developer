# MongoDB Data Modeling Patterns

## Why It Matters

MongoDB schema design = critical for performance. Wrong model = slow queries, wasted RAM, complex updates. Right model = blazingly fast.

Senior interview: "Design schema for Instagram-like app." → embedded vs referenced based on access patterns.

---

## Core Patterns

### Embedded vs Referenced (1:1, 1:few, 1:many, M:N)

**Rule of thumb:**
- **Embed** when data accessed together AND child data fits in 16MB
- **Reference** when child data huge, shared, or independently queried

```javascript
// Embedded (1:1)
{
  _id: 'user_1',
  name: 'Alice',
  address: {
    street: '...',
    city: '...',
  }
}


// Referenced (1:many or M:N)
{ _id: 'user_1', name: 'Alice' }
{ _id: 'post_1', user_id: 'user_1', body: '...' }
```

### Bucket Pattern (Time-Series)

Group time-series points into buckets:

```javascript
// BAD — 1 doc per reading = millions of docs
{ device: 'sensor1', ts: 1700000000, temp: 22.5 }
{ device: 'sensor1', ts: 1700000001, temp: 22.6 }


// GOOD — bucket per hour
{
  device: 'sensor1',
  bucket_hour: ISODate('2026-01-15T14:00:00Z'),
  count: 3600,
  measurements: [
    { ts: 1700000000, temp: 22.5 },
    { ts: 1700000001, temp: 22.6 },
    ...
  ]
}
```

MongoDB 5.0+ Time-Series Collections do this automatically.

### Subset Pattern (Avoid Loading Huge Embedded)

```javascript
// BAD — embed ALL reviews; doc grows unbounded
{
  product: 'X',
  reviews: [...10000 reviews...]
}


// GOOD — embed top 5 most recent, store all in separate collection
{
  product: 'X',
  top_reviews: [...5 most recent...],
  total_review_count: 10000
}

// Separate collection
{
  product_id: 'X',
  reviews: [...all 10000...]
}
```

### Computed Pattern (Precompute Aggregates)

```javascript
// BAD — count reviews every page load
$lookup ... $count ...


// GOOD — denormalize counter, update on insert
{
  product: 'X',
  review_count: 1234,
  avg_rating: 4.2
}

// On new review:
db.products.update_one(
  { _id: 'X' },
  {
    $inc: { review_count: 1, total_rating: 5 },
    $set: { avg_rating: ... } // computed from total / count
  }
)
```

### Extended Reference Pattern (Cached Reference)

```javascript
// Don't denormalize EVERYTHING from author, just a few common fields
{
  post_id: 1,
  body: '...',
  author: {
    id: 'user_1',
    name: 'Alice',         // duplicated
    avatar_url: '...',     // duplicated
  }
}

// Update propagation: when user changes name, update all their posts
// OR accept stale (cron-based reconciliation)
```

### Tree Structures

#### Parent Reference

```javascript
{ _id: 'category-1', name: 'Electronics' }
{ _id: 'category-2', parent: 'category-1', name: 'Laptops' }
{ _id: 'category-3', parent: 'category-2', name: 'Gaming Laptops' }
```

Simple but ancestor queries need recursive lookups.

#### Child References

```javascript
{ _id: 'category-1', children: ['category-2', 'category-4'] }
```

Easy to find children, hard ancestor queries.

#### Array of Ancestors

```javascript
{ _id: 'category-3', name: 'Gaming Laptops', ancestors: ['category-1', 'category-2'] }
```

Easy ancestor + descendant queries. Update on tree restructure.

#### Materialized Path

```javascript
{ _id: 'category-3', path: ',category-1,category-2,', name: '...' }

// Find all under category-1
db.cats.find({ path: { $regex: ',category-1,' } })
```

### Polymorphic Schema

Multiple types in same collection:

```javascript
// All "events" in one collection with different shapes
{ type: 'click', element: 'btn-buy', user_id: 1 }
{ type: 'pageview', url: '/home', user_id: 1 }
{ type: 'purchase', order_id: 'X', amount: 99 }


// Or polymorphic users
{ type: 'employee', salary: 50000, department: '...' }
{ type: 'customer', credit_limit: 5000 }
```

Mongoose discriminators or app-level handling.

### Outlier Pattern

Most users have < 100 followers, some celebrities have millions:

```javascript
// Normal user — embed followers
{
  _id: 'alice',
  followers: ['bob', 'charlie', ...]  // up to 100
}


// Celebrity — has_extras flag, followers in separate collection
{
  _id: 'celeb',
  followers: ['top100...'],
  has_extras: true,
}

// Separate collection for extras
{ celeb_id: 'celeb', followers: [...millions...] }
```

### Attribute Pattern (Sparse Fields)

Products with varying attributes:

```javascript
// BAD — many sparse fields
{ name: 'Laptop', cpu: 'i7', ram: '16GB', screen_size: '15"', ... }
{ name: 'TV', screen_size: '55"', resolution: '4K', ... }


// GOOD — array of attribute key-value pairs
{
  name: 'Laptop',
  attributes: [
    { k: 'cpu', v: 'i7' },
    { k: 'ram', v: '16GB' },
    { k: 'screen_size', v: '15"' }
  ]
}

// Index on attributes.k + attributes.v
db.products.createIndex({ 'attributes.k': 1, 'attributes.v': 1 })

// Find all 16GB RAM products
db.products.find({ attributes: { $elemMatch: { k: 'ram', v: '16GB' } } })
```

### Approximation Pattern

For counters that don't need exact precision (page views, "saw this" counters):

```javascript
// On each view, only increment 1% of the time × 100
if random() < 0.01:
    db.posts.update_one({_id: X}, {$inc: {view_count: 100}})
```

Or use Redis HyperLogLog for unique counts.

### Schema Versioning

Add `schema_version` field for migrations:

```javascript
{ _id: 1, schema_version: 1, name: 'Alice', addr: 'X' }
{ _id: 2, schema_version: 2, name: 'Bob', address: { street: 'X', city: 'Y' } }
```

App handles both. Migration script over time.

---

## Decision Framework

```
Should I embed or reference?

1. Is the data accessed together?
   YES → embed
   NO → reference

2. Does embedding cause doc > 16MB?
   YES → reference
   NO → continue

3. Is the data shared across many parents?
   YES → reference
   NO → embed

4. Does the child have its own lifecycle (independently queried/updated)?
   YES → reference
   NO → embed

5. Does the child grow unboundedly?
   YES → reference + subset (top N embedded)
   NO → embed
```

---

## Common Pitfalls

### 1. Unbounded Array Growth

```javascript
{ user: 'X', actions: [...growing forever...] }
```

Doc grows past 16MB. Use subset pattern or separate collection.

### 2. Deeply Nested Embeds

```javascript
{
  comments: [
    { replies: [
      { replies: [...] }  // 100 levels deep
    ]}
  ]
}
```

Querying deep nested is hard. Use flat structure + parent_id.

### 3. Embed Sharded Reference

If user data is on shard A but their orders on shard B, can't $lookup efficiently. Pre-design shard key around access pattern.

### 4. Schema Per Query Anti-Pattern

Don't optimize ONE query at the cost of all others. Pick patterns that fit most queries.

### 5. Premature Denormalization

```javascript
// 5 levels of caching/denormalization for "performance"
```

Start with embed-or-reference per access pattern. Denormalize when you see slow queries.

### 6. Single Collection vs Many

Trend: "one big collection" with polymorphic docs. Pros: less code. Cons: slower aggregations, mixed index utility. Decide based on access pattern.

---

## Interview Q&A

**Q1:** Embed vs reference — kab kya?
**A:** Embed when accessed together + doc < 16MB + child not shared. Reference when child has own lifecycle, shared across parents, or unbounded. Mix when needed — embed common fields (extended reference), reference full record.

**Q2:** Time-series data in MongoDB?
**A:** Bucket pattern — group N measurements per bucket doc (per hour/day). Or use MongoDB 5+ Time-Series Collections (automatic bucketing). Indexes on bucket boundary fields. Compresses well due to delta encoding.

**Q3:** Tree structures kaise represent karoge?
**A:** Depends on queries. Parent ref: simple, slow ancestor lookups. Array of ancestors: fast queries, hard restructure. Materialized path: regex queries, mid complexity. For Mongo: array of ancestors most common for category trees with rare restructures.

**Q4:** 1 lakh comments par post — schema?
**A:** Subset pattern — embed top N (recent or relevant) in post, separate `comments` collection for full set. Post doc: `{ post_id, top_5_comments: [...], comment_count: 10000 }`. Avoids 16MB doc limit + fast post listing.

**Q5:** Polymorphic events collection — pros/cons?
**A:** Pros: one collection for all events, simpler ingest. Cons: each event type sparse fields → less index efficient, harder aggregation per type. Use when types share most fields; separate collections when shapes very different.

**Q6:** Aggregation pipeline performance — design rules?
**A:** (1) `$match` early (filter rows). (2) `$project` early (reduce fields). (3) Index on $match/$sort fields. (4) Avoid `$lookup` when possible (denormalize). (5) Use `allowDiskUse: true` for big sorts. (6) Pipeline stages happen one at a time — design accordingly.

**Q7:** Outlier pattern explain karo.
**A:** Most docs follow one schema, few outliers need different. E.g., 99% users < 100 followers (embed), 1% celebrities millions (separate collection + has_extras flag). App reads flag → fetches extras if needed. Optimizes for common case.

**Q8:** Schema migration MongoDB mein?
**A:** Add schema_version field. New docs use new schema. Background script migrates old docs over time. App handles both versions during transition (read both shapes). After migration complete, simplify app code.

---

## Real-World Use Cases

### 1. E-commerce Product

```javascript
{
  _id: 'product_1',
  name: 'Gaming Laptop',
  price: 1500,
  category_path: 'electronics/laptops',
  attributes: [
    { k: 'cpu', v: 'i9-13900' },
    { k: 'ram_gb', v: 32 },
    { k: 'screen_inches', v: 17 },
  ],
  top_reviews: [...5 most helpful...],
  review_count: 1234,
  avg_rating: 4.5,
  stock_by_warehouse: {
    'wh-1': 12,
    'wh-2': 5,
  },
  schema_version: 2
}
```

### 2. Social Feed

```javascript
// Post embeds author info (extended reference)
{
  _id: 'post_1',
  author: {
    id: 'user_1',
    name: 'Alice',         // cached
    avatar: '...',         // cached
  },
  body: '...',
  reactions: { like: 42, love: 5 },
  comment_count: 12,
  // Comments in separate collection
}


// User has follower count, top followers
{
  _id: 'user_1',
  follower_count: 1500,
  top_followers: ['bob', 'charlie'],   // most engaged 100
  has_full_followers: true,            // overflow collection
}
```

### 3. IoT Time-Series

```javascript
// Bucket per device per hour
{
  device_id: 'sensor_1',
  bucket_start: ISODate('2026-01-15T14:00Z'),
  count: 3600,
  readings: [
    { ts: ..., temp: 22.5, humidity: 45 },
    ...
  ],
  agg: {
    temp_avg: 22.4,
    temp_min: 21.8,
    temp_max: 23.1,
  }
}
```

---

## References

- [MongoDB Schema Design Patterns](https://www.mongodb.com/blog/post/building-with-patterns-a-summary)
- "MongoDB Applied Design Patterns" book
- Time-Series Collections docs
- Aggregation Pipeline guide
