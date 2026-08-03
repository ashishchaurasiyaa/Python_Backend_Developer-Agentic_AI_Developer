# 📚 MongoDB: Aggregation Pipeline + Indexes + Schema Design
### Interview Prep Series — Python Backend Developer (5 YOE | 20 LPA Target)
> **Hinglish Format**: Theory Hindi mein samjhao, Code/Terms English mein likhte hain

---

## 🗂️ Table of Contents
1. [Aggregation Pipeline Kya Hai?](#1-aggregation-pipeline-kya-hai)
2. [Core Aggregation Stages](#2-core-aggregation-stages)
3. [Aggregation Expressions](#3-aggregation-expressions)
4. [Index Types in MongoDB](#4-index-types-in-mongodb)
5. [explain() Deep Dive](#5-explain-deep-dive)
6. [Schema Design Patterns](#6-schema-design-patterns)
7. [Schema Validation](#7-schema-validation)
8. [Write Concern & Read Preference](#8-write-concern--read-preference)
9. [Transactions (Multi-Document ACID)](#9-transactions-multi-document-acid)
10. [12 Interview Q&As](#10-12-interview-qas)

---

## 1. 🔄 Aggregation Pipeline Kya Hai?

### Simple Definition
MongoDB Aggregation Pipeline ek **document processing pipeline** hai — jaise assembly line mein ek ke baad ek stage hoti hai, waise hi documents ek stage se doosre stage mein pass hote hain aur transform hote rahte hain.

```
Documents → [$match] → [$group] → [$sort] → [$limit] → Final Result
```

### SQL GROUP BY se Analogy

| SQL | MongoDB Aggregation |
|-----|---------------------|
| `WHERE` | `$match` |
| `GROUP BY` | `$group` |
| `SELECT col, SUM(val)` | `$group` with `$sum` |
| `HAVING` | `$match` (after `$group`) |
| `ORDER BY` | `$sort` |
| `LIMIT / OFFSET` | `$limit / $skip` |
| `JOIN` | `$lookup` |
| `SELECT col AS alias` | `$project` |
| `CASE WHEN` | `$cond` |

### SQL vs MongoDB Example

**SQL:**
```sql
SELECT category, SUM(price * quantity) as revenue
FROM orders
WHERE status = 'completed'
GROUP BY category
ORDER BY revenue DESC
LIMIT 5;
```

**MongoDB Aggregation:**
```javascript
db.orders.aggregate([
  { $match: { status: "completed" } },           // WHERE clause
  { $group: {
      _id: "$category",                            // GROUP BY
      revenue: { $sum: { $multiply: ["$price", "$quantity"] } }
  }},
  { $sort: { revenue: -1 } },                     // ORDER BY
  { $limit: 5 }                                   // LIMIT
])
```

### ⚡ Performance Tips — Interview Mein Zaroor Poochha Jaata Hai!

1. **`$match` sabse pehle rakho** — Early filtering se sirf relevant documents aage jaate hain, baaki stages pe load kam hota hai. Agar `$match` index pe ho, toh IXSCAN use hoga.

2. **`$project` early rakho** — Unnecessary fields hatao jaldi, taaki baaki stages mein data size chhota rahe.

3. **`$sort` + `$limit` — "Top K" pattern** — Agar `$sort` ke baad turant `$limit` hai, MongoDB smart hai — limit ke baad ki memory waste nahi hoti (internal optimization).

4. **`$group` ke baad `$match` == HAVING** — `$group` ke baad aaya `$match` SQL ka HAVING clause hai. Ye index use nahi kar sakta, isliye pehle `$match` se data reduce karo.

5. **`allowDiskUse: true`** — Agar aggregation mein 100MB RAM limit exceed ho, ye option disk use karne deta hai. Production mein large datasets pe zaroori hai.

6. **Index use karo `$match` mein** — `$match` pe jo fields hain, unpe index hona chahiye. `explain()` se verify karo.

```python
# Python mein aggregation
pipeline = [
    {"$match": {"status": "completed", "created_at": {"$gte": start_date}}},
    {"$project": {"_id": 0, "category": 1, "price": 1, "quantity": 1}},
    {"$group": {"_id": "$category", "revenue": {"$sum": {"$multiply": ["$price", "$quantity"]}}}},
    {"$sort": {"revenue": -1}},
    {"$limit": 10}
]
results = list(db.orders.aggregate(pipeline, allowDiskUse=True))
```

---

## 2. 🧩 Core Aggregation Stages

### 📌 `$match` — Filter Stage

**Kab use karein**: Pipeline ke shuruaat mein documents filter karne ke liye. Index use karta hai.

```javascript
// Basic match
{ $match: { status: "active" } }

// Multiple conditions
{ $match: { 
    status: { $in: ["active", "pending"] },
    price: { $gte: 100, $lte: 1000 },
    category: "electronics"
}}

// After $group — HAVING clause jaisa
{ $match: { total_revenue: { $gt: 50000 } } }

// Date range
{ $match: {
    created_at: {
        $gte: ISODate("2024-01-01"),
        $lt: ISODate("2025-01-01")
    }
}}
```

**Python:**
```python
from datetime import datetime

pipeline = [
    {"$match": {
        "status": "completed",
        "order_date": {
            "$gte": datetime(2024, 1, 1),
            "$lt": datetime(2025, 1, 1)
        },
        "amount": {"$gte": 500}
    }}
]
```

---

### 📌 `$group` — Grouping + Aggregation

**Core concept**: `_id` field mein grouping key dete hain. Agar `_id: null` toh sab documents ek group.

```javascript
// Basic group
{ $group: {
    _id: "$category",
    count: { $sum: 1 },
    total: { $sum: "$price" },
    avg_price: { $avg: "$price" },
    min_price: { $min: "$price" },
    max_price: { $max: "$price" }
}}

// Compound _id — multiple fields pe group
{ $group: {
    _id: { category: "$category", region: "$region" },
    revenue: { $sum: { $multiply: ["$price", "$quantity"] } }
}}

// $push — collect all values in array
{ $group: {
    _id: "$category",
    products: { $push: "$name" }
}}

// $addToSet — unique values only (no duplicates)
{ $group: {
    _id: "$user_id",
    unique_categories: { $addToSet: "$category" }
}}

// $first / $last — first or last value in group (use with $sort before $group)
{ $group: {
    _id: "$user_id",
    latest_order: { $last: "$order_date" },
    first_order: { $first: "$order_date" }
}}
```

**Accumulators Table:**

| Accumulator | Description | Example |
|-------------|-------------|---------|
| `$sum` | Sum of values (or `1` to count) | `{ $sum: "$price" }` |
| `$avg` | Average value | `{ $avg: "$rating" }` |
| `$min` | Minimum value | `{ $min: "$price" }` |
| `$max` | Maximum value | `{ $max: "$price" }` |
| `$count` | Count docs (v5.0+) | `{ $count: {} }` |
| `$push` | Array of all values | `{ $push: "$name" }` |
| `$addToSet` | Array of unique values | `{ $addToSet: "$tag" }` |
| `$first` | First value in group | `{ $first: "$date" }` |
| `$last` | Last value in group | `{ $last: "$date" }` |

---

### 📌 `$project` — Shape Output

**Kab use karein**: Fields include/exclude karna, computed fields banana, field rename karna.

```javascript
// Include/exclude fields
{ $project: {
    name: 1,
    price: 1,
    _id: 0            // _id exclude karna padta hai explicitly
}}

// Computed field
{ $project: {
    name: 1,
    total_value: { $multiply: ["$price", "$quantity"] },
    name_upper: { $toUpper: "$name" },
    full_name: { $concat: ["$first_name", " ", "$last_name"] }
}}

// $substr — substring
{ $project: {
    short_name: { $substr: ["$name", 0, 10] }  // first 10 chars
}}

// $dateToString — date format karo
{ $project: {
    formatted_date: {
        $dateToString: { format: "%Y-%m-%d", date: "$created_at" }
    }
}}

// $cond — ternary operator
{ $project: {
    price: 1,
    discount_price: {
        $cond: {
            if: { $gt: ["$price", 500] },
            then: { $multiply: ["$price", 0.9] },   // 10% off
            else: "$price"
        }
    }
}}

// $ifNull — null check with default
{ $project: {
    region: { $ifNull: ["$region", "unknown"] }
}}
```

---

### 📌 `$sort` — Sorting

```javascript
{ $sort: { price: -1 } }              // descending
{ $sort: { category: 1, price: -1 } } // multi-field sort

// Text score sorting (with $text search)
{ $sort: { score: { $meta: "textScore" } } }
```

**Important**: `$sort` ke liye memory limit 100MB hai. Agar exceed ho toh `allowDiskUse: true` use karo ya pehle `$match`/`$limit` se data reduce karo.

---

### 📌 `$limit` / `$skip` — Pagination

```javascript
// Page 3, page size 20
{ $skip: 40 },   // (page-1) * pageSize
{ $limit: 20 }
```

**⚠️ Warning**: Deep pagination (high skip values) slow hoti hai kyunki MongoDB pehle `$skip` number of docs skip karta hai. Large datasets ke liye **cursor-based pagination** better hai.

```python
# Cursor-based pagination (better for large data)
# Use last seen _id as cursor
pipeline = [
    {"$match": {"_id": {"$gt": last_seen_id}}},
    {"$sort": {"_id": 1}},
    {"$limit": 20}
]
```

---

### 📌 `$unwind` — Array Flattening

**Concept**: Ek document jisme array hai, use `$unwind` multiple documents mein expand karta hai — ek doc per array element.

```javascript
// Basic unwind
{ $unwind: "$tags" }

// Input:  { _id: 1, name: "iPhone", tags: ["tech", "mobile", "apple"] }
// Output: { _id: 1, name: "iPhone", tags: "tech" }
//         { _id: 1, name: "iPhone", tags: "mobile" }
//         { _id: 1, name: "iPhone", tags: "apple" }

// Extended options
{ $unwind: {
    path: "$tags",
    preserveNullAndEmptyArrays: true,  // null/empty array docs bhi rakho
    includeArrayIndex: "tag_index"     // original array index bhi include karo
}}
```

**Use Case**: Array field pe analytics karna — jaise "kitne products mein 'sale' tag hai":

```javascript
db.products.aggregate([
    { $unwind: "$tags" },
    { $group: { _id: "$tags", count: { $sum: 1 } } },
    { $sort: { count: -1 } }
])
```

---

### 📌 `$lookup` — Left Outer Join

**Concept**: SQL ke LEFT OUTER JOIN jaisa. Ek collection ke documents mein doosri collection ke related documents embed karta hai.

```javascript
// Basic $lookup
{ $lookup: {
    from: "users",           // join karni wali collection
    localField: "user_id",   // current collection ka field
    foreignField: "_id",     // target collection ka field
    as: "user_info"          // result array field name
}}

// Result: user_info = [] agar match nahi, ya [{...user doc...}] agar match hai
```

**Pipeline $lookup** (more powerful — join ke saath filter/transform):

```javascript
{ $lookup: {
    from: "orders",
    let: { uid: "$_id" },      // local variable define karo
    pipeline: [
        { $match: {
            $expr: { $eq: ["$$uid", "$user_id"] },  // $$var = let variable
            status: "completed"
        }},
        { $project: { _id: 0, amount: 1, order_date: 1 } }
    ],
    as: "completed_orders"
}}
```

**Python:**
```python
pipeline = [
    {
        "$lookup": {
            "from": "users",
            "let": {"uid": "$user_id"},
            "pipeline": [
                {"$match": {"$expr": {"$eq": ["$$uid", "$_id"]}}},
                {"$project": {"name": 1, "email": 1, "_id": 0}}
            ],
            "as": "user_details"
        }
    },
    {"$unwind": "$user_details"}  # array → single object (assuming 1:1)
]
```

**⚠️ Performance Warning**: `$lookup` pe index hona chahiye `foreignField` pe. Bina index ke full collection scan hoga — very slow for large collections.

---

### 📌 `$addFields` / `$set` — Add Fields Without Removing Others

**Difference from `$project`**: `$project` mein explicitly sab fields include karne padte hain, jabki `$addFields` sirf naye fields add karta hai (existing sab rahte hain).

```javascript
{ $addFields: {
    total_value: { $multiply: ["$price", "$quantity"] },
    is_expensive: { $gt: ["$price", 1000] }
}}

// $set is alias for $addFields (MongoDB 4.2+)
{ $set: {
    updated_at: "$$NOW"
}}
```

---

### 📌 `$replaceRoot` — Document Root Replace Karo

```javascript
// Embedded doc ko root bana do
{ $replaceRoot: { newRoot: "$user_info" } }

// $mergeObjects ke saath
{ $replaceRoot: {
    newRoot: { $mergeObjects: ["$$ROOT", "$user_info"] }
}}
```

---

### 📌 `$count` — Just Count Karo

```javascript
{ $count: "total_documents" }
// Output: { "total_documents": 1523 }
```

---

### 📌 `$facet` — Multiple Pipelines Parallel Mein

**Concept**: Ek hi query se multiple analytics results simultaneously nikalo. E-commerce search results mein bahut useful — ek query mein items list + category breakdown + price ranges + total count.

```javascript
{ $facet: {
    "total": [
        { $count: "count" }
    ],
    "byCategory": [
        { $sortByCount: "$category" }
    ],
    "byPriceRange": [
        { $bucket: {
            groupBy: "$price",
            boundaries: [0, 100, 500, 1000, 5000],
            default: "5000+"
        }}
    ],
    "topRated": [
        { $sort: { rating: -1 } },
        { $limit: 5 },
        { $project: { name: 1, rating: 1 } }
    ]
}}
```

**Output is single document with one key per facet** — bahut efficient!

---

### 📌 `$bucket` / `$bucketAuto` — Range-Based Grouping

```javascript
// Manual bucket boundaries
{ $bucket: {
    groupBy: "$price",
    boundaries: [0, 100, 500, 1000, 5000],
    default: "Other",          // boundaries ke bahar values ke liye
    output: {
        count: { $sum: 1 },
        products: { $push: "$name" }
    }
}}

// Auto bucket — MongoDB khud boundaries decide karta hai
{ $bucketAuto: {
    groupBy: "$price",
    buckets: 4,                // N equal-ish buckets
    output: { count: { $sum: 1 } }
}}
```

---

### 📌 `$sortByCount` — Shorthand for Group + Sort

```javascript
// Ye do stages ke barabar hai:
{ $sortByCount: "$category" }

// Equivalent to:
{ $group: { _id: "$category", count: { $sum: 1 } } },
{ $sort: { count: -1 } }
```

---

### 📌 `$out` / `$merge` — Results Collection Mein Save Karo

```javascript
// $out — result ek nayi/existing collection mein save karo (replaces!)
{ $out: "monthly_revenue_report" }

// $merge — merge karo existing collection mein (upsert/replace/merge options)
{ $merge: {
    into: "product_stats",
    on: "_id",
    whenMatched: "merge",      // options: replace, keepExisting, merge, fail
    whenNotMatched: "insert"
}}
```

**Use Case**: Nightly batch jobs mein pre-computed analytics store karna (Computed Pattern).

---

## 3. 🔢 Aggregation Expressions

### Arithmetic Expressions

```javascript
{ $add: ["$price", 50] }                        // price + 50
{ $subtract: ["$original", "$discount"] }        // subtraction
{ $multiply: ["$price", "$quantity"] }           // multiplication
{ $divide: ["$total", "$count"] }               // division
{ $mod: ["$quantity", 3] }                      // modulo (remainder)
{ $round: ["$price", 2] }                       // round to 2 decimal places
{ $floor: "$price" }                             // floor
{ $ceil: "$price" }                              // ceiling
{ $abs: "$temperature" }                         // absolute value
{ $pow: ["$base", 2] }                          // power (base^2)
{ $sqrt: "$area" }                               // square root
```

### String Expressions

```javascript
{ $concat: ["$first_name", " ", "$last_name"] }  // string join
{ $toLower: "$name" }                             // lowercase
{ $toUpper: "$name" }                             // uppercase
{ $trim: { input: "$name" } }                     // trim whitespace
{ $ltrim: { input: "$name" } }                    // left trim
{ $rtrim: { input: "$name" } }                    // right trim
{ $split: ["$full_name", " "] }                  // split to array
{ $strLenCP: "$name" }                           // string length (code points)
{ $substr: ["$name", 0, 5] }                     // substring
{ $indexOfCP: ["$name", "abc"] }                 // find substring index
{ $replaceOne: { input: "$name", find: "old", replacement: "new" } }
{ $regexMatch: { input: "$email", regex: /^.+@.+\..+$/ } }  // regex test
```

### Date Expressions

```javascript
{ $year: "$created_at" }                          // year number
{ $month: "$created_at" }                         // month (1-12)
{ $dayOfMonth: "$created_at" }                   // day (1-31)
{ $dayOfWeek: "$created_at" }                    // day of week (1=Sun, 7=Sat)
{ $hour: "$created_at" }                          // hour (0-23)
{ $minute: "$created_at" }                        // minute
{ $second: "$created_at" }                        // second

{ $dateToString: {
    format: "%Y-%m-%d %H:%M",
    date: "$created_at",
    timezone: "Asia/Kolkata"   // timezone support!
}}

{ $dateTrunc: {
    date: "$created_at",
    unit: "month"             // truncate to month start
}}

{ $dateAdd: {
    startDate: "$created_at",
    unit: "day",
    amount: 30
}}
```

### Array Expressions

```javascript
{ $size: "$tags" }                               // array length
{ $slice: ["$tags", 3] }                         // first 3 elements
{ $slice: ["$tags", -2] }                        // last 2 elements
{ $arrayElemAt: ["$tags", 0] }                  // element at index 0
{ $first: "$tags" }                              // first element (v4.4+)
{ $last: "$tags" }                               // last element (v4.4+)
{ $in: ["electronics", "$tags"] }               // check if value in array
{ $concatArrays: ["$arr1", "$arr2"] }           // merge arrays

// $filter — array filter karo
{ $filter: {
    input: "$tags",
    as: "tag",
    cond: { $regexMatch: { input: "$$tag", regex: /^tech/ } }
}}

// $map — array transform karo (map function)
{ $map: {
    input: "$prices",
    as: "p",
    in: { $multiply: ["$$p", 1.18] }  // add 18% GST to each price
}}

// $reduce — array pe fold/reduce
{ $reduce: {
    input: "$quantities",
    initialValue: 0,
    in: { $add: ["$$value", "$$this"] }  // $$value = accumulator, $$this = current
}}
```

### Conditional Expressions

```javascript
// $cond — ternary
{ $cond: {
    if: { $gte: ["$rating", 4] },
    then: "good",
    else: "bad"
}}

// Short form
{ $cond: [{ $gte: ["$rating", 4] }, "good", "bad"] }

// $ifNull — null hone pe default
{ $ifNull: ["$discount", 0] }   // agar discount null hai, 0 use karo

// $switch — multi-way conditional (like switch-case)
{ $switch: {
    branches: [
        { case: { $gte: ["$score", 90] }, then: "A" },
        { case: { $gte: ["$score", 80] }, then: "B" },
        { case: { $gte: ["$score", 70] }, then: "C" }
    ],
    default: "F"
}}
```

---

## 4. 🗂️ Index Types in MongoDB

### Kya Hota Hai Index?

Index ek **sorted data structure** (B-Tree) hai jo MongoDB ko documents dhundhne mein help karta hai bina poori collection scan kiye. Without index = **COLLSCAN** (full scan) = slow. With index = **IXSCAN** = fast.

```python
# Python mein index banana
db.collection.create_index([("field_name", pymongo.ASCENDING)])
```

---

### 1. 📌 Single Field Index

```python
# Ascending
db.products.create_index([("price", pymongo.ASCENDING)])

# Descending (single field pe ascending/descending same performance deta hai)
db.products.create_index([("price", pymongo.DESCENDING)])

# _id pe default index already hota hai!
```

**Use Case**: Kisi ek field pe frequently filter ya sort karte ho.

---

### 2. 📌 Compound Index — Multiple Fields

```python
# Compound index — field order matters!
db.orders.create_index([
    ("category", pymongo.ASCENDING),
    ("price", pymongo.ASCENDING),
    ("status", pymongo.ASCENDING)
])
```

**ESR Rule (Equality → Sort → Range)** — Ye interview ka most important concept hai!

```
Compound index banate waqt fields ka order:
1. EQUALITY fields pehle  (exact match: status = "active")
2. SORT fields middle mein  (order by: sort on date)  
3. RANGE fields last mein  (range: price > 100)
```

**Example:**
```javascript
// Query: Find active orders, sort by date, price between 100-500
db.orders.find({ 
    status: "active",     // EQUALITY
    price: { $gte: 100, $lte: 500 }  // RANGE
}).sort({ order_date: 1 })  // SORT

// Correct index (ESR):
db.orders.create_index({ status: 1, order_date: 1, price: 1 })
// NOT: { price: 1, status: 1, order_date: 1 }  -- Wrong!
```

**Prefix Rule**: Compound index `{a, b, c}` se ye queries covered hain:
- `{a}` ✅
- `{a, b}` ✅
- `{a, b, c}` ✅
- `{b}` ❌ (prefix nahi hai)
- `{b, c}` ❌ (prefix nahi hai)

---

### 3. 📌 Multikey Index — Array Fields

**Automatically** create hota hai jab indexed field array ho. MongoDB array ke har element ke liye index entry banata hai.

```python
db.products.create_index([("tags", pymongo.ASCENDING)])
# tags = ["tech", "mobile", "sale"] -> 3 index entries banenge

# Query: products with tag "tech"
db.products.find({"tags": "tech"})  # Index use karega!
```

**Limitation**: Ek compound index mein sirf ek multikey (array) field ho sakta hai.

---

### 4. 📌 Text Index — Full-Text Search

```python
db.products.create_index([
    ("name", pymongo.TEXT),
    ("description", pymongo.TEXT)
], weights={"name": 10, "description": 5})  # name ko zyada weight
```

```python
# Text search query
db.products.find(
    {"$text": {"$search": "wireless bluetooth headphones"}},
    {"score": {"$meta": "textScore"}}   # relevance score
).sort([("score", {"$meta": "textScore"})])  # sort by relevance
```

**Limitations**:
- Ek collection mein sirf ek text index ho sakta hai
- Stop words ignore hote hain (a, an, the, etc.)
- Stemming hoti hai (running -> run)

---

### 5. 📌 Geospatial Index

```python
# 2dsphere index for GeoJSON coordinates
db.locations.create_index([("location", pymongo.GEOSPHERE)])

# Store location as GeoJSON
{
    "name": "Taj Mahal",
    "location": {
        "type": "Point",
        "coordinates": [78.0421, 27.1751]  # [longitude, latitude]
    }
}

# Near query
db.locations.find({
    "location": {
        "$near": {
            "$geometry": {"type": "Point", "coordinates": [77.2090, 28.6139]},
            "$maxDistance": 10000  # 10km in meters
        }
    }
})
```

---

### 6. 📌 Hashed Index — Sharding Ke Liye

```python
db.users.create_index([("user_id", pymongo.HASHED)])
# Hashed indexes support equality queries only, NOT range queries
# Sharding ke liye use hota hai even distribution ke liye
```

---

### 7. 📌 TTL Index — Auto-Deletion (Time-To-Live)

**Concept**: Documents automatically delete ho jaate hain ek certain time ke baad. Sessions, logs, OTP, cache ke liye perfect.

```python
# 1 hour (3600 seconds) baad delete ho jaayega
db.sessions.create_index(
    [("created_at", pymongo.ASCENDING)],
    expireAfterSeconds=3600
)

# Document mein created_at field zaroori hai (ISODate type)
db.sessions.insert_one({
    "session_id": "abc123",
    "user_id": ObjectId("..."),
    "created_at": datetime.utcnow()  # Ye datetime field pe TTL lagega
})
```

**Note**: TTL background thread har 60 seconds mein chalta hai — immediate deletion ki guarantee nahi.

---

### 8. 📌 Partial Index — Subset of Documents

**Concept**: Poori collection ko index mat karo — sirf relevant subset ko. Index size chhota = faster + less memory.

```python
# Sirf active products ko index karo
db.products.create_index(
    [("price", pymongo.ASCENDING)],
    partialFilterExpression={"status": "active"}
)

# Query must include filter expression to use partial index
db.products.find({"status": "active", "price": {"$gt": 100}})  # Uses index!
db.products.find({"price": {"$gt": 100}})  # Does NOT use partial index
```

**Use Case**: Soft-deleted records (deleted=False wale docs ko index karo), premium users only.

---

### 9. 📌 Sparse Index

**Concept**: Sirf wo documents index mein aate hain jinmein wo field exist karti hai. Null/missing field wale documents skip.

```python
db.users.create_index(
    [("phone", pymongo.ASCENDING)],
    sparse=True
)
# Users jinka phone field nahi hai, index mein nahi aayenge
```

**Note**: Partial index zyada flexible hai (custom filter). Sparse is effectively `{field: {$exists: true}}` partial index.

---

### 10. 📌 Wildcard Index

**Concept**: Unknown/dynamic fields ko index karo. Useful for schema-less data.

```python
# Sab fields ko index karo
db.logs.create_index([("$**", pymongo.ASCENDING)])

# Specific prefix ke sab fields
db.products.create_index([("attributes.$**", pymongo.ASCENDING)])
# attributes.color, attributes.size, attributes.weight — sab indexed!
```

---

### 11. 📌 Covered Query — No Document Fetch!

**Concept**: Agar query mein sirf indexed fields hain AND projection mein bhi sirf indexed fields hain — MongoDB sirf index se result de deta hai, actual document fetch karne ki zaroorat nahi. **Most Efficient!**

```python
# Index: {category: 1, price: 1}
db.products.create_index([("category", 1), ("price", 1)])

# Covered query — sirf index se served
db.products.find(
    {"category": "electronics"},        # Indexed field
    {"_id": 0, "category": 1, "price": 1}  # Only indexed fields in projection
)
# explain() mein stage = "PROJECTION_COVERED" ya totalDocsExamined = 0
```

**Agar `_id` exclude nahi kiya** → covered query nahi hogi! `_id` index mein nahi hai by default.

---

## 5. 🔍 explain() Deep Dive

### explain() Kaise Use Karein

```python
# explain() — query execution stats
result = db.orders.find({"status": "active"}).explain("executionStats")

# Aggregation pipeline explain
result = db.orders.aggregate(
    [{"$match": {"status": "active"}}],
    explain=True  # Python driver mein
)

# hint() — specific index force karo
result = db.orders.find({"status": "active"}).hint("status_1")
```

### explain() Output — Key Fields

```javascript
{
  "queryPlanner": {
    "winningPlan": {
      "stage": "FETCH",          // COLLSCAN / IXSCAN / FETCH / SORT / PROJECTION_COVERED
      "inputStage": {
        "stage": "IXSCAN",
        "indexName": "status_1"
      }
    },
    "rejectedPlans": [...]
  },
  "executionStats": {
    "nReturned": 150,             // Kitne docs return hue
    "totalKeysExamined": 150,     // Index entries scanned
    "totalDocsExamined": 150,     // Actual docs fetched
    "executionTimeMillis": 12,    // Execution time
    "stage": "FETCH"
  }
}
```

### Stage Types — Kya Matlab Hai

| Stage | Matlab | Good/Bad? |
|-------|--------|-----------|
| `COLLSCAN` | Full collection scan | ❌ Bad (no index) |
| `IXSCAN` | Index scan | ✅ Good |
| `FETCH` | Document fetch after index | ⚠️ OK (index + doc read) |
| `PROJECTION_COVERED` | No doc fetch (covered query) | ✅✅ Best |
| `SORT` | In-memory sort | ⚠️ Slow for large data |
| `SORT_MERGE` | Merge sort using index | ✅ Good |
| `LIMIT` | Limit applied | ✅ |

### Efficiency Check

```python
# Efficient query: totalDocsExamined ≈ nReturned
# Inefficient query: totalDocsExamined >> nReturned (many docs scanned, few returned)

def check_query_efficiency(explain_result):
    stats = explain_result.get("executionStats", {})
    n_returned = stats.get("nReturned", 0)
    docs_examined = stats.get("totalDocsExamined", 0)
    
    if docs_examined == 0:
        print("✅ Covered query — no docs fetched!")
    elif n_returned > 0 and docs_examined / n_returned < 2:
        print("✅ Efficient — low docs examined ratio")
    else:
        print(f"⚠️  Inefficient — examined {docs_examined}, returned {n_returned}")
```

---

## 6. 🏗️ Schema Design Patterns

### Embedded vs Reference — Basic Decision

```
Embed karo jab:
✅ Data hamesha saath access hota hai (e.g., address with user)
✅ 1:1 ya 1:few relationship
✅ Embedded data zyada nahi badhega
✅ Atomicity chahiye (single write)

Reference rakho jab:
✅ 1:many ya many:many relationship
✅ Embedded array bohot bada ho sakta hai (hundreds/thousands)
✅ Related data independently bhi access hota hai
✅ Data shared hai multiple documents se
```

---

### 1. 📌 Embedded Document Pattern

```javascript
// User ka address embed karo — always accessed together
{
    "_id": ObjectId("..."),
    "name": "Rahul Sharma",
    "email": "rahul@example.com",
    "address": {
        "street": "123 Main St",
        "city": "Delhi",
        "state": "DL",
        "pincode": "110001"
    },
    "preferences": {
        "theme": "dark",
        "language": "hindi"
    }
}
```

**Pros**: Single query, atomic updates, no joins.
**Cons**: Document size limit 16MB, if embedded data grows unbounded → problem.

---

### 2. 📌 Reference Pattern

```javascript
// Orders mein user_id reference
{
    "_id": ObjectId("order123"),
    "user_id": ObjectId("user456"),    // Reference
    "product_id": ObjectId("prod789"), // Reference
    "quantity": 2,
    "total_amount": 1500
}

// User document separate collection mein
{
    "_id": ObjectId("user456"),
    "name": "Priya Singh",
    "email": "priya@example.com"
}
```

**Pros**: No duplication, data update ek jagah.
**Cons**: `$lookup` (join) chahiye — extra query.

---

### 3. 📌 Bucket Pattern — Time-Series Data

**Problem**: IoT sensor, logs — har second ek document banao toh millions of tiny docs = bad performance.

**Solution**: N measurements ko ek bucket document mein group karo.

```javascript
// Bucket: 1 hour = 1 document, 3600 measurements
{
    "_id": ObjectId("..."),
    "sensor_id": "temp_sensor_01",
    "timestamp": ISODate("2024-01-15T10:00:00"),  // Bucket start
    "count": 3600,
    "measurements": [
        { "ts": ISODate("2024-01-15T10:00:01"), "temp": 23.5 },
        { "ts": ISODate("2024-01-15T10:00:02"), "temp": 23.6 },
        // ... 3598 more
    ],
    "summary": {
        "min": 22.1,
        "max": 25.3,
        "avg": 23.7
    }
}
```

**Pros**: Fewer documents, pre-computed summaries, efficient range queries.
**Cons**: Complex insert logic (upsert to add to bucket).

---

### 4. 📌 Outlier Pattern

**Problem**: Zyada popular celebrity ke followers = millions. Normal user ke followers = hundreds. Ek size ka solution dono ke liye nahi chalega.

```javascript
// Normal user — followers embed karo
{
    "_id": ObjectId("user1"),
    "name": "Normal User",
    "followers": [ObjectId("a"), ObjectId("b"), ...],  // Small array
    "has_extras": false
}

// Celebrity — overflow in separate collection
{
    "_id": ObjectId("celeb1"),
    "name": "Big Celebrity",
    "followers": [ObjectId("a"), ObjectId("b"), ...],  // First 1000 followers
    "has_extras": true                                  // Flag!
}

// Overflow collection
{ "user_id": ObjectId("celeb1"), "followers": [...] }
```

---

### 5. 📌 Computed Pattern — Pre-Compute Expensive Aggregations

**Problem**: Har request pe expensive aggregation = slow.

**Solution**: Results pre-compute karo, periodically refresh karo.

```javascript
// Products collection — actual data
{ "_id": ObjectId("p1"), "name": "iPhone", "category": "electronics", ... }

// Product stats — pre-computed, nightly job se update
{
    "_id": "electronics_daily_stats",
    "category": "electronics",
    "date": ISODate("2024-01-15"),
    "total_revenue": 2500000,
    "order_count": 450,
    "avg_rating": 4.3,
    "computed_at": ISODate("2024-01-15T23:00:00")
}
```

**Python with `$merge`:**
```python
pipeline = [
    {"$match": {"status": "completed"}},
    {"$group": {
        "_id": {"category": "$category", "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$order_date"}}},
        "revenue": {"$sum": "$amount"},
        "count": {"$sum": 1}
    }},
    {"$merge": {
        "into": "daily_stats",
        "on": "_id",
        "whenMatched": "replace",
        "whenNotMatched": "insert"
    }}
]
db.orders.aggregate(pipeline)
```

---

### 6. 📌 Schema Versioning Pattern

**Problem**: Application update hone pe schema change karna padta hai. Sab existing docs instantly migrate karna slow hai.

```javascript
// Version 1 document
{ "_id": ObjectId("u1"), "schema_version": 1, "name": "Rahul" }

// Version 2 document (new fields added)
{ "_id": ObjectId("u2"), "schema_version": 2, "first_name": "Priya", "last_name": "Singh" }

// Application code handles both versions
```

```python
def get_user_name(user_doc):
    version = user_doc.get("schema_version", 1)
    if version == 1:
        return user_doc["name"]
    elif version >= 2:
        return f"{user_doc['first_name']} {user_doc['last_name']}"
```

---

### 7. 📌 Polymorphic Pattern

**Concept**: Different "types" ke documents ek hi collection mein, with a discriminator field.

```javascript
// Same collection — different shapes
{ "_id": ObjectId("v1"), "type": "car", "brand": "Toyota", "num_wheels": 4, "engine_cc": 1500 }
{ "_id": ObjectId("v2"), "type": "bike", "brand": "Hero", "num_wheels": 2, "gear_count": 5 }
{ "_id": ObjectId("v3"), "type": "truck", "brand": "Tata", "num_wheels": 10, "load_capacity_tons": 20 }
```

**Use Case**: Product catalog with different attributes per category, content management system.

---

### 8. 📌 Extended Reference Pattern

**Problem**: `$lookup` expensive hai. Frequently accessed fields ke liye join avoid karo.

```javascript
// Order mein user ke frequently-needed fields embed karo
{
    "_id": ObjectId("order1"),
    "user_id": ObjectId("user456"),
    "user_name": "Rahul Sharma",     // Copied from user doc
    "user_email": "rahul@x.com",     // Copied from user doc
    // ^^^ These are "extended reference" — copies of rarely-changing data
    "total_amount": 1500,
    "order_date": ISODate("2024-01-15")
}
```

**Trade-off**: Data duplication hai, update pe user doc change karna padega. But bahut kam change hoti hai name/email.

---

## 7. ✅ Schema Validation

MongoDB mein documents pe validation enforce kar sakte ho `$jsonSchema` se.

```python
validator = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["name", "email", "status", "price"],
        "additionalProperties": False,  # Extra fields allow nahi
        "properties": {
            "_id": {"bsonType": "objectId"},
            "name": {
                "bsonType": "string",
                "minLength": 2,
                "maxLength": 100,
                "description": "Product name required"
            },
            "email": {
                "bsonType": "string",
                "pattern": "^.+@.+\\..+$",
                "description": "Valid email required"
            },
            "price": {
                "bsonType": ["double", "int"],
                "minimum": 0,
                "description": "Price must be non-negative"
            },
            "status": {
                "bsonType": "string",
                "enum": ["active", "inactive", "draft"],
                "description": "Status must be one of: active, inactive, draft"
            },
            "tags": {
                "bsonType": "array",
                "items": {"bsonType": "string"}
            }
        }
    }
}

# Collection banate waqt validator attach karo
db.create_collection("products", validator=validator)

# Ya existing collection pe modify karo
db.command("collMod", "products", validator=validator, validationLevel="strict")
```

### Validation Options

```python
# validationLevel
# "strict"    — sab inserts + updates validate hote hain (default)
# "moderate"  — sirf valid existing docs pe updates validate hote hain

# validationAction
# "error"   — invalid docs reject karo (default)
# "warn"    — allow karo but log warning (useful for migration)

db.command("collMod", "products",
    validator=validator,
    validationLevel="strict",
    validationAction="error"
)
```

```python
# Valid insert — pass
db.products.insert_one({
    "name": "iPhone 15",
    "email": "support@apple.com",
    "price": 89999.0,
    "status": "active"
})

# Invalid insert — OperationFailure raise hoga
try:
    db.products.insert_one({
        "name": "X",           # Too short!
        "price": -100,         # Negative!
        "status": "deleted"    # Not in enum!
    })
except pymongo.errors.OperationFailure as e:
    print(f"Validation failed: {e.details}")
```

---

## 8. ⚡ Write Concern & Read Preference

### Write Concern — Kitna "Safe" Write Chahiye?

```python
from pymongo import WriteConcern

# w=0: Fire and forget — no acknowledgment (fastest, least safe)
db.logs.with_options(write_concern=WriteConcern(w=0)).insert_one(log_doc)

# w=1: Primary acknowledge kare (default)
db.orders.with_options(write_concern=WriteConcern(w=1)).insert_one(order)

# w="majority": Majority of replica set acknowledge kare (safest)
db.payments.with_options(
    write_concern=WriteConcern(w="majority", j=True, wtimeout=5000)
).insert_one(payment)

# j=True: Journal pe likhne ke baad acknowledge (crash safe)
# wtimeout=5000: 5 seconds mein majority nahi mili toh error
```

| w value | Speed | Durability | Use Case |
|---------|-------|------------|----------|
| `0` | Fastest | None | Analytics, logs |
| `1` | Fast | Primary only | Default, most apps |
| `"majority"` | Slower | Replica majority | Financial transactions |

### Read Preference — Kaun Sa Node Se Read Karo?

```python
from pymongo.read_preferences import (
    Primary, PrimaryPreferred, Secondary, SecondaryPreferred, Nearest
)

# Primary: Hamesha primary se read (consistent, default)
db = client.get_database("mydb", read_preference=Primary())

# PrimaryPreferred: Primary prefer karo, unavailable ho toh secondary
db = client.get_database("mydb", read_preference=PrimaryPreferred())

# Secondary: Sirf secondary se (read scale-out, slightly stale data)
db = client.get_database("mydb", read_preference=Secondary())

# SecondaryPreferred: Secondary prefer karo (analytics, reporting)
db = client.get_database("mydb", read_preference=SecondaryPreferred())

# Nearest: Network latency ke hisaab se closest node
db = client.get_database("mydb", read_preference=Nearest())
```

### Read Concern — Consistency Level

| Read Concern | Matlab | Use Case |
|-------------|--------|----------|
| `local` | Jo primary pe hai (may not be committed) | Default, fast |
| `available` | Fastest (sharded cluster) | Logs, analytics |
| `majority` | Majority ne commit kiya | Consistent reads |
| `linearizable` | Latest committed value (single doc only) | Critical reads |
| `snapshot` | Transaction ke start pe snapshot | Multi-doc transactions |

---

## 9. 🔒 Transactions (Multi-Document ACID)

### Transactions Kab Chahiye?

MongoDB by default **single-document atomic** hai. Multiple documents atomically update karne ke liye transaction chahiye:
- Bank transfer: debit user A + credit user B
- Inventory update: order create + stock decrease
- Multi-collection writes

### Basic Transaction Pattern

```python
from pymongo import MongoClient
from pymongo.errors import OperationFailure

def transfer_funds(db, from_user_id, to_user_id, amount):
    with client.start_session() as session:
        with session.start_transaction():
            try:
                # Debit from sender
                result = db.users.update_one(
                    {"_id": from_user_id, "balance": {"$gte": amount}},
                    {"$inc": {"balance": -amount}},
                    session=session
                )
                if result.modified_count == 0:
                    raise ValueError("Insufficient balance or user not found")
                
                # Credit to receiver
                db.users.update_one(
                    {"_id": to_user_id},
                    {"$inc": {"balance": amount}},
                    session=session
                )
                
                # Log transaction
                db.transactions.insert_one({
                    "from": from_user_id,
                    "to": to_user_id,
                    "amount": amount,
                    "timestamp": datetime.utcnow()
                }, session=session)
                
                session.commit_transaction()
                print(f"Transfer of {amount} successful!")
                
            except Exception as e:
                session.abort_transaction()
                raise
```

### `with_transaction()` — Auto-Retry (Better Pattern)

```python
def run_transaction_with_retry(session, db, from_id, to_id, amount):
    def callback(session):
        db.accounts.update_one(
            {"_id": from_id},
            {"$inc": {"balance": -amount}},
            session=session
        )
        db.accounts.update_one(
            {"_id": to_id},
            {"$inc": {"balance": amount}},
            session=session
        )
    
    # with_transaction auto-retries on transient errors (network, write conflicts)
    session.with_transaction(callback)

with client.start_session() as session:
    run_transaction_with_retry(session, db, user1_id, user2_id, 500)
```

### Requirements & Performance Notes

```
✅ Requirements:
- Replica Set hona chahiye (minimum: single node replica set with --replSet rs0)
- MongoDB 4.0+ (replica sets), 4.2+ (sharded clusters)
- All collections in same/different databases OK (4.2+)

⚠️ Performance:
- Transactions much slower than single writes
- Lock time badhta hai — contention possible
- 60 second default transaction timeout
- Use SPARINGLY — sirf jab atomicity genuinely needed ho
```

---

## 10. ❓ 12 Interview Q&As

---

**Q1: Aggregation pipeline vs find() — kab kya use karein?**

**A**: `find()` use karo jab simple filtering, sorting, pagination chahiye — single collection se documents fetch karna ho. `aggregate()` use karo jab:
- Multiple stages mein data transform karna ho
- Grouping/aggregation (SUM, AVG, COUNT) chahiye
- Multiple collections join (`$lookup`) karna ho
- Computed fields, reshaping chahiye
- Complex analytics jo SQL ke GROUP BY + HAVING jaisi ho

`find()` internally bhi ek simple aggregation hai, lekin simpler syntax provide karta hai.

---

**Q2: `$lookup` performance slow kyun hoti hai? Optimize kaise karein?**

**A**: `$lookup` ke liye `foreignField` pe index hona MANDATORY hai. Bina index ke MongoDB target collection ka full scan karta hai — O(N*M) complexity.

Optimization steps:
1. `foreignField` pe index banana
2. `$match` pehle rakho `$lookup` se `$unwind` se pehle (reduce rows before join)
3. Pipeline `$lookup` mein sirf needed fields select karo
4. Frequently joined small collections ke liye **Extended Reference Pattern** use karo
5. Read-heavy analytics ke liye pre-join data ko denormalize karo

```python
# Index on foreignField first!
db.users.create_index([("_id", 1)])  # Already exists
db.orders.create_index([("user_id", 1)])  # Index for join performance
```

---

**Q3: Index intersection kya hai? MongoDB use karta hai kya?**

**A**: Index intersection matlab ek query mein **do alag indexes** ke results merge karna. MongoDB technically support karta hai, lekin **bahut kam use karta hai** kyunki iska overhead zyada hota hai.

**Better approach**: Compound index banana which serves the full query. Index intersection se dedicated compound index hamesha better performance deta hai.

```javascript
// Instead of relying on intersection of {status: 1} and {price: 1}
// Create compound index:
{ status: 1, price: 1 }  // Better!
```

---

**Q4: ESR Rule explain karo with example.**

**A**: ESR = **Equality → Sort → Range**. Compound index mein fields ka order:

1. **Equality** (exact match) fields pehle — `status = "active"`
2. **Sort** fields middle mein — `.sort({date: 1})`
3. **Range** fields last mein — `price > 100`

```javascript
// Query:
db.orders.find({
    status: "completed",     // E — Equality
    amount: {$gte: 100}      // R — Range
}).sort({order_date: -1})    // S — Sort

// Correct ESR index:
db.orders.createIndex({ status: 1, order_date: -1, amount: 1 })
//                        E ↑       S ↑              R ↑

// Why? 
// E first — max selectivity, reduces search space most
// S middle — allows index-based sort (no in-memory sort)
// R last — range scans always at end of compound traversal
```

---

**Q5: TTL Index real-world use case batao.**

**A**: Real-world use cases:

1. **User Sessions**: `{ session_id: ..., created_at: ISODate(...) }` — expire after 1 hour
2. **OTP/Verification Codes**: expire after 10 minutes
3. **Rate Limiting**: Track API calls, auto-delete after 1 minute
4. **Soft Delete Recycle Bin**: Items deleted_at pe TTL lagao — 30 days baad permanent delete
5. **Cache Collection**: Pre-computed results ka TTL — expired results auto-clean
6. **Temporary Uploads**: Unconfirmed file uploads 24 hours baad delete

```python
# OTP example
db.otps.create_index([("created_at", 1)], expireAfterSeconds=600)  # 10 min

db.otps.insert_one({
    "user_id": user_id,
    "otp": "123456",
    "created_at": datetime.utcnow()
})
```

---

**Q6: Covered query kya hai? Ensure kaise karein?**

**A**: Covered query = **index se query + projection dono serve ho jaaye — document fetch karne ki zaroorat na ho**. Fastest possible query.

Ensure karne ke liye:
1. Query ke sab filter fields index mein hone chahiye
2. Projection mein sirf indexed fields hone chahiye
3. `_id: 0` explicitly exclude karo (unless `_id` bhi indexed hai compound index mein)

```python
# Compound index
db.products.create_index([("category", 1), ("price", 1), ("name", 1)])

# Covered query
result = db.products.find(
    {"category": "electronics", "price": {"$lt": 1000}},  # All indexed
    {"_id": 0, "category": 1, "price": 1, "name": 1}      # Only indexed fields
)

# verify with explain()
explain = db.products.find(...).explain("executionStats")
# totalDocsExamined should be 0
```

---

**Q7: `$facet` stage ka use case kya hai? Real example do.**

**A**: `$facet` ek query mein multiple analytics simultaneously return karta hai — **single database round-trip mein**.

Real use case: **E-Commerce Product Search Page**
- Left sidebar: Category filter counts, Price range distribution
- Center: Product list (paginated)
- Top: Total results count

```python
pipeline = [
    {"$match": {"name": {"$regex": "phone", "$options": "i"}}},
    {"$facet": {
        "totalCount": [{"$count": "total"}],
        "byCategory": [{"$sortByCount": "$category"}],
        "byPriceRange": [{"$bucket": {
            "groupBy": "$price",
            "boundaries": [0, 5000, 15000, 50000, 200000],
            "default": "200000+"
        }}],
        "results": [
            {"$sort": {"rating": -1}},
            {"$skip": 0},
            {"$limit": 20},
            {"$project": {"name": 1, "price": 1, "rating": 1}}
        ]
    }}
]
```

Alternative: 4 separate queries = 4 round trips. `$facet` = 1 round trip. 4x faster!

---

**Q8: Write concern `w="majority"` kab use karein? `w=1` se kya difference hai?**

**A**:
- `w=1`: Primary pe likha gaya — acknowledge karta hai. Agar primary crash ho aur data secondary tak replicate nahi hua, **data loss possible**.
- `w="majority"`: Majority nodes (e.g., 2 out of 3) pe replicate hone ke baad acknowledge. Primary crash hone pe bhi data safe kyunki majority ne confirm kiya hai.

**Kab use karein**:
- `w="majority"` + `j=True`: Financial transactions, payments, critical data
- `w=1`: General application data, user profiles
- `w=0`: Non-critical logs, analytics events (speed priority)

**Performance cost**: `w="majority"` mein network round-trip + replication lag ka wait — latency zyada. Use only where durability > speed.

---

**Q9: MongoDB transactions kab zaroor chahiye? Single-document vs multi-document.**

**A**: MongoDB single-document operations **inherently atomic** hain — transaction ki zaroorat nahi.

**Transactions zaroor chahiye jab**:
1. Multiple documents atomically update karne hon (bank transfer)
2. Multiple collections mein changes ek saath karne hon (order + inventory)
3. Read-modify-write pattern jahan concurrent modification risky ho

**Transactions avoid karo jab**:
- Single document update (use `$inc`, `$set`, `$push` instead)
- Denormalized design kar sakte ho
- Performance critical ho

```python
# Transaction NOT needed — single doc, atomic
db.products.update_one(
    {"_id": product_id},
    {"$inc": {"stock": -1}, "$push": {"sales": order_id}}
)

# Transaction NEEDED — two docs, must be atomic
with session.start_transaction():
    db.accounts.update_one({"_id": from_id}, {"$inc": {"balance": -100}}, session=session)
    db.accounts.update_one({"_id": to_id}, {"$inc": {"balance": 100}}, session=session)
```

---

**Q10: `$unwind` kisi null/missing array pe kya karta hai?**

**A**: By default, `$unwind` **document ko drop kar deta hai** agar:
- Field null ho
- Field missing ho
- Field empty array ho

`preserveNullAndEmptyArrays: true` se ye documents rakhe jaate hain.

```javascript
// Data:
{ _id: 1, tags: ["a", "b"] }
{ _id: 2, tags: [] }          // Empty array
{ _id: 3, tags: null }         // Null
{ _id: 4 }                     // Missing field

// Without preserveNullAndEmptyArrays (default):
// Output: Only doc _id:1 (two docs with tag "a" and "b")

// With preserveNullAndEmptyArrays: true:
// Output: _id:1 (x2), _id:2 (tags=null), _id:3 (tags=null), _id:4 (tags missing — still included)
```

**Interview Tip**: Aggregation analytics mein missing data bhi count karna ho (e.g., "users without orders") toh `preserveNullAndEmptyArrays: true` + `$count` use karo.

---

**Q11: Partial index ka benefit batao vs full index.**

**A**: Partial index sirf **qualified subset of documents** ko index karta hai. Benefits:

1. **Smaller index size** — less RAM usage
2. **Faster writes** — fewer index entries to maintain
3. **Faster queries** — index traverse karna faster (smaller B-tree)
4. **Targeted filtering** — sirf relevant docs ko query karo

```python
# Scenario: 1 crore orders, 90% "completed", 10% "pending"
# Sirf pending orders ko track karna hai

# Full index pe 1cr entries
db.orders.create_index([("created_at", 1)])

# Partial index pe sirf 10 lakh entries (10x smaller!)
db.orders.create_index(
    [("created_at", 1)],
    partialFilterExpression={"status": "pending"}
)

# Query must include the partial filter to use partial index
db.orders.find({"status": "pending", "created_at": {"$gt": cutoff}})
```

**Interview mein add karo**: Partial index, Sparse index, TTL index — ye teen "special purpose" indexes hain. Partial index sabse flexible hai.

---

**Q12: E-commerce platform ke liye MongoDB schema design batao.**

**A**: E-commerce schema design (interview-quality answer):

```javascript
// Products Collection
{
    "_id": ObjectId(),
    "name": "iPhone 15 Pro",
    "slug": "iphone-15-pro",           // URL-friendly
    "category": "electronics",
    "subcategory": "smartphones",
    "price": 134900,
    "discounted_price": 119900,
    "stock": 50,
    "images": ["url1", "url2"],        // Embed (always accessed with product)
    "attributes": {                     // Polymorphic attributes (wildcard index!)
        "brand": "Apple",
        "color": "Titanium Black",
        "storage": "256GB",
        "ram": "8GB"
    },
    "tags": ["5g", "ios", "premium"],  // Multikey index
    "ratings": {
        "average": 4.7,
        "count": 2341
    },
    "created_at": ISODate()
}

// Users Collection  
{
    "_id": ObjectId(),
    "name": "Rahul Kumar",
    "email": "rahul@email.com",
    "phone": "+91-9876543210",
    "addresses": [                      // Embed (usually < 5 addresses)
        { "type": "home", "street": "...", "city": "Delhi", "default": true }
    ],
    "created_at": ISODate()
}

// Orders Collection (denormalized for read performance)
{
    "_id": ObjectId(),
    "order_number": "ORD-2024-001234",
    "user_id": ObjectId(),             // Reference
    "user_name": "Rahul Kumar",        // Extended reference (rarely changes)
    "user_email": "rahul@email.com",   // Extended reference
    "items": [
        {
            "product_id": ObjectId(),   // Reference
            "product_name": "iPhone 15", // Extended reference (snapshot at order time)
            "category": "electronics",
            "price_at_order": 134900,  // IMPORTANT: snapshot, not current price!
            "quantity": 1
        }
    ],
    "shipping_address": { ... },        // Embed (snapshot at order time)
    "status": "completed",
    "payment": {
        "method": "upi",
        "transaction_id": "TXN123",
        "paid_at": ISODate()
    },
    "total_amount": 134900,
    "created_at": ISODate()
}
```

**Indexes:**
```python
db.products.create_index([("category", 1), ("price", 1)])  # Browse by category
db.products.create_index([("slug", 1)], unique=True)       # URL lookup
db.products.create_index([("tags", 1)])                    # Tag search (multikey)
db.products.create_index([("name", "text"), ("tags", "text")])  # Search
db.orders.create_index([("user_id", 1), ("created_at", -1)])    # User order history
db.orders.create_index([("status", 1), ("created_at", -1)])     # Status filter
```

---

## 11. 🔤 Collation — Case/Locale-Aware Sorting & Indexes

Default comparison **binary** hota hai — `"Apple" < "banana"` (uppercase pehle), aur `"a" != "A"`. Collation locale-aware comparison deta hai:

```javascript
// Case-insensitive UNIQUE email — THE classic use case
db.users.createIndex(
  { email: 1 },
  { unique: true, collation: { locale: "en", strength: 2 } }
)
// strength: 1 = sirf base char (a=A=á), 2 = case-insensitive but accent-sensitive (a=A, a≠á)
// Ab "John@X.com" aur "john@x.com" dono insert = duplicate key error ✅

// Query ko SAME collation deni hogi warna index use nahi hoga:
db.users.find({ email: "JOHN@X.COM" }).collation({ locale: "en", strength: 2 })

// Locale-aware sort (Hindi/German/Turkish sorting rules):
db.products.find().sort({ name: 1 }).collation({ locale: "hi" })

// Numeric ordering of string numbers: "10" > "9" (binary me "10" < "9"!)
db.items.find().sort({ code: 1 }).collation({ locale: "en", numericOrdering: true })
```

```python
# PyMongo
from pymongo.collation import Collation
users.create_index([("email", 1)], unique=True,
                   collation=Collation(locale="en", strength=2))
users.find_one({"email": "JOHN@X.COM"},
               collation=Collation(locale="en", strength=2))
```

**Gotchas:** (1) index ki collation aur query ki collation **exactly match** honi chahiye, warna COLLSCAN; (2) collection-level default collation create ke time set hoti hai — baad me change nahi; (3) PostgreSQL equivalent = `CITEXT`/`LOWER()` functional index — interview me parallel bolna accha lagta hai.

---

## 📋 Quick Reference Cheatsheet

```
Aggregation Stage Order (Recommended):
$match → $project → $lookup → $unwind → $group → $sort → $limit/$skip

Index Selection (ESR Rule):
Equality first → Sort middle → Range last

explain() Key Fields:
stage: IXSCAN ✅, COLLSCAN ❌
totalDocsExamined ≈ nReturned = efficient
totalDocsExamined = 0 = covered query (best!)

Write Concern:
w=0: logs/analytics, w=1: general, w="majority": payments

Transactions:
Single doc = no transaction needed
Multi-doc atomic = use with_transaction() pattern
```

---
*Series: Python Backend + Agentic AI Interview Prep | 5 YOE | 20 LPA*
*File 2 of N: MongoDB Aggregation + Indexes + Schema Design*
