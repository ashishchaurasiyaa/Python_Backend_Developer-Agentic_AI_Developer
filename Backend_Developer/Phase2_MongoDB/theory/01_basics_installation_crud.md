# 🍃 MongoDB Basics — Installation, Core Concepts & CRUD
### Python Backend Developer Interview Prep | 5 YOE | 20 LPA Target
> **Hinglish format** — Theory Hindi mein, Code/Terms English mein

---

## 📚 Table of Contents
1. [MongoDB Kya Hai?](#1-mongodb-kya-hai)
2. [Core Concepts](#2-core-concepts)
3. [Docker Setup](#3-docker-setup)
4. [Python Setup](#4-python-setup)
5. [PyMongo Connection](#5-pymongo-connection)
6. [CRUD Operations](#6-crud-operations)
7. [Query Operators](#7-query-operators)
8. [bulk_write()](#8-bulk_write)
9. [Schema Design Basics](#9-schema-design-basics)
10. [ObjectId Deep Dive](#10-objectid-deep-dive)
11. [Connection Pool Configuration](#11-connection-pool-configuration)
12. [Interview Q&A — 15 Questions](#12-interview-qa)

---

## 1. MongoDB Kya Hai?

MongoDB ek **NoSQL document database** hai. Matlab data ko **JSON-like documents** mein store kiya jaata hai — rows aur columns ki jagah. Yeh 2009 mein MongoDB Inc. ne banaya tha aur aaj yeh world ka most popular NoSQL database hai.

### Ek Simple Example Samjho:

**SQL (PostgreSQL) mein:**
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    email VARCHAR(100) UNIQUE,
    age INT
);
INSERT INTO users (name, email, age) VALUES ('Rahul', 'rahul@example.com', 25);
```

**MongoDB mein:**
```javascript
// Schema define karne ki zaroorat nahi!
db.users.insertOne({
    name: "Rahul",
    email: "rahul@example.com",
    age: 25,
    address: {           // Nested object — SQL mein alag table hoti
        city: "Mumbai",
        state: "Maharashtra"
    },
    hobbies: ["coding", "cricket"]  // Array — SQL mein junction table chahiye
})
```

### 🔄 MongoDB vs Relational Database — Complete Comparison Table

| Feature | MongoDB (NoSQL) | PostgreSQL/MySQL (SQL) |
|---|---|---|
| **Data Model** | JSON-like Documents (BSON) | Tables with Rows & Columns |
| **Schema** | Schema-less / Flexible | Strict Schema (DDL required) |
| **Relationships** | Embed or Reference (manual) | Foreign Keys + JOINs |
| **Joins** | No native JOIN (use `$lookup` in aggregation) | Full JOIN support (INNER, LEFT, RIGHT, FULL) |
| **Scaling** | Horizontal Scaling (Sharding) — easy | Vertical Scaling (bigger server) — default |
| **ACID** | Document-level ACID; Multi-doc transactions MongoDB 4.0+ se | Full ACID (transactions always) |
| **Query Language** | MongoDB Query Language (MQL) | SQL (Structured Query Language) |
| **Indexes** | B-tree, Text, Geo, Hashed, TTL, Wildcard | B-tree, Hash, GiST, GIN, BRIN |
| **Replication** | Replica Set (built-in, easy) | Streaming Replication (manual setup) |
| **CAP Theorem** | CP by default (Consistency + Partition Tolerance) | CA (Consistency + Availability) |
| **Performance** | Fast reads/writes for document-centric data | Fast for complex queries with JOINs |
| **Use Cases** | CMS, Catalogs, Real-time Analytics, IoT, Mobile Apps | ERP, Banking, Complex Reporting, Legacy Systems |
| **Transactions** | Available but avoid if possible (overhead) | First-class support |
| **Aggregation** | Aggregation Pipeline (powerful) | SQL GROUP BY + window functions |
| **Full-Text Search** | Atlas Search (Lucene-based) or basic $text | Full-text indexes (limited) |
| **JSON Support** | Native (BSON is superset of JSON) | JSONB column type |

### Kab MongoDB Use Karo?
✅ **MongoDB choose karo jab:**
- Data structure frequently change hoti ho (agile development)
- Hierarchical/nested data ho (product catalog, user profiles)
- Read-heavy workload ho
- Horizontal scaling chahiye ho (microservices, high traffic)
- Real-time analytics, IoT, event logging
- Content management systems

❌ **SQL choose karo jab:**
- Complex multi-table transactions hों (banking, finance)
- Strong referential integrity chahiye
- Complex reporting/analytics with many JOINs
- Strict compliance requirements (HIPAA, SOX)

---

## 2. Core Concepts

### 🗂️ Terminology Mapping — SQL vs MongoDB

| SQL Term | MongoDB Equivalent | Description |
|---|---|---|
| Database | Database | Same — ek ya zyada collections ka container |
| Table | Collection | Documents ka group |
| Row / Record | Document | Ek JSON object |
| Column | Field | Document ka ek key-value pair |
| Primary Key | `_id` (ObjectId) | Auto-generated unique identifier |
| Foreign Key | Reference (DBRef ya ObjectId) | Manual relationship |
| Index | Index | Same concept |
| JOIN | `$lookup` (aggregation) | Collection ke beech join |
| Stored Procedure | JavaScript Functions / Atlas Functions | Server-side code |
| View | View (MongoDB 3.4+) | Read-only aggregation result |

### 📄 Document

Document ek **BSON object** hai — key-value pairs ka collection. Maximum size **16MB** per document.

```javascript
{
    "_id": ObjectId("64a1b2c3d4e5f6a7b8c9d0e1"),  // Auto-generated
    "name": "iPhone 15 Pro",                          // String
    "price": 129999,                                   // Int32/Int64
    "rating": 4.8,                                     // Double
    "in_stock": true,                                  // Boolean
    "created_at": ISODate("2024-01-15T10:30:00Z"),    // Date
    "tags": ["smartphone", "apple", "5g"],             // Array
    "specs": {                                          // Embedded Document
        "ram": "8GB",
        "storage": "256GB",
        "processor": "A17 Pro"
    },
    "images": [                                        // Array of Objects
        {"url": "img1.jpg", "alt": "front view"},
        {"url": "img2.jpg", "alt": "back view"}
    ]
}
```

### 🗃️ Collection
- Table ka equivalent
- Schema enforce nahi karti — different documents alag structure rakh sakte hain (though bad practice)
- **Capped Collections** — fixed size, circular buffer behavior (logs ke liye)

### 🏠 Database
- Collections ka container
- `show dbs` command se list dekh sako
- Special databases: `admin`, `local`, `config` (system use)

### 🔑 ObjectId — _id Field

Agar `_id` specify nahi kiya, MongoDB automatically **ObjectId** generate karta hai.

```
ObjectId("64a1b2c3d4e5f6a7b8c9d0e1")
           ^^^^^^^^ ^^^^^^ ^^^^^^
           4 bytes  3 bytes 3 bytes  2 bytes
           Unix     Machine Random   Counter
           timestamp ID     value
```

**Structure breakdown:**
- **Bytes 0-3:** Unix timestamp (seconds) — creation time pata chalta hai
- **Bytes 4-8:** Machine identifier / process ID
- **Bytes 9-11:** Random value
- **Bytes 12:** Incrementing counter

**Size:** 12 bytes = 24 hex characters

### 📦 BSON Types — Complete Table

BSON = Binary JSON. JSON ka binary encoded superset hai. Extra types provide karta hai.

| BSON Type | Type Number | Python Equivalent | Example |
|---|---|---|---|
| Double | 1 | `float` | `4.99`, `3.14` |
| String | 2 | `str` | `"hello world"` |
| Object (Embedded Doc) | 3 | `dict` | `{"key": "val"}` |
| Array | 4 | `list` | `[1, 2, 3]` |
| Binary Data | 5 | `bytes` | File content, images |
| ObjectId | 7 | `bson.ObjectId` | `ObjectId("...")` |
| Boolean | 8 | `bool` | `True`, `False` |
| Date | 9 | `datetime.datetime` | `datetime(2024, 1, 1)` |
| Null | 10 | `None` | `None` |
| Regular Expression | 11 | `re` object | `/pattern/flags` |
| 32-bit Integer | 16 | `int` (small) | `42` |
| 64-bit Integer | 18 | `int` (large) | `9007199254740992` |
| Decimal128 | 19 | `bson.Decimal128` | `Decimal128("3.14159265")` |
| Timestamp | 17 | `bson.Timestamp` | Internal MongoDB use |
| Min Key | -1 | N/A | Comparison purposes |
| Max Key | 127 | N/A | Comparison purposes |

> **Interview Tip:** BSON vs JSON difference — BSON has ObjectId, Date, Binary, Int32/Int64/Decimal128. JSON sirf String, Number, Boolean, Null, Array, Object support karta hai. BSON binary encoded hai isliye faster parse/traverse hota hai compared to text-based JSON.

---

## 3. Docker Setup

### 🐳 MongoDB Docker Container Run Karo

```bash
# MongoDB 7.0 run karo with authentication
docker run -d \
  --name mongodb \
  -p 27017:27017 \
  -e MONGO_INITDB_ROOT_USERNAME=admin \
  -e MONGO_INITDB_ROOT_PASSWORD=secret \
  -e MONGO_INITDB_DATABASE=practice_db \
  -v mongodb_data:/data/db \
  mongo:7.0

# Check if running
docker ps | grep mongodb

# Logs dekho
docker logs mongodb

# Container ke andar jao (mongo shell)
docker exec -it mongodb mongosh -u admin -p secret --authenticationDatabase admin
```

### 📡 Connection String Formats

```
# Basic format
mongodb://username:password@host:port/database?authSource=admin

# Hamara connection string
mongodb://admin:secret@localhost:27017/practice_db?authSource=admin

# Replica Set ke saath
mongodb://admin:secret@host1:27017,host2:27017,host3:27017/mydb?replicaSet=rs0&authSource=admin

# Atlas (Cloud) format
mongodb+srv://username:password@cluster0.abc123.mongodb.net/mydb?retryWrites=true&w=majority

# URL Encoding — special chars mein
# @ = %40, : = %3A, / = %2F, # = %23, ? = %3F, & = %26
```

### 🛑 Container Management

```bash
# Stop
docker stop mongodb

# Start again
docker start mongodb

# Remove (data bhi jaayega agar volume nahi hai)
docker rm -f mongodb

# Persistent volume ke saath
docker volume create mongodb_data
docker run -d --name mongodb -p 27017:27017 \
  -e MONGO_INITDB_ROOT_USERNAME=admin \
  -e MONGO_INITDB_ROOT_PASSWORD=secret \
  -v mongodb_data:/data/db \
  mongo:7.0
```

### mongosh — MongoDB Shell Commands

```javascript
// Database select karo
use practice_db

// Collections list karo
show collections

// Stats dekho
db.stats()

// Collection stats
db.products.stats()

// Current database
db.getName()

// Admin commands
db.adminCommand({ping: 1})   // {ok: 1} aana chahiye
db.serverStatus()             // Detailed server info
```

---

## 4. Python Setup

### 📦 Required Packages

```bash
# Core packages install karo
pip install pymongo motor beanie dnspython

# Optional but recommended
pip install python-dotenv   # .env file management
pip install pydantic        # Data validation (beanie ke saath)

# Ya requirements.txt se
cat > requirements.txt << EOF
pymongo==4.7.1
motor==3.4.0
beanie==1.25.0
dnspython==2.6.1
python-dotenv==1.0.1
pydantic==2.7.1
EOF
pip install -r requirements.txt
```

### Package Roles Samjho:
| Package | Purpose | Use When |
|---|---|---|
| `pymongo` | Synchronous MongoDB driver (official) | Flask, FastAPI sync routes, scripts |
| `motor` | Async MongoDB driver (built on pymongo) | FastAPI async routes, async apps |
| `beanie` | ODM (Object Document Mapper) | Type-safe models, FastAPI + Pydantic integration |
| `dnspython` | DNS resolution for `mongodb+srv://` URLs | MongoDB Atlas connection |

---

## 5. PyMongo Connection

### 🔌 Basic Connection Setup

```python
import os
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

# Environment variable se URI lo
MONGO_URI = os.getenv(
    "MONGO_URI",
    "mongodb://admin:secret@localhost:27017/practice_db?authSource=admin"
)

def get_client() -> MongoClient:
    """
    MongoDB client create karo with proper configuration.
    Connection pool automatically manage hota hai.
    """
    client = MongoClient(
        MONGO_URI,
        serverSelectionTimeoutMS=5000,   # 5 sec mein server nahi mila to error
        connectTimeoutMS=10000,           # Initial connection timeout
        socketTimeoutMS=45000,            # Query timeout
        maxPoolSize=50,                   # Max connections in pool
        minPoolSize=5,                    # Min connections maintain karo
        retryWrites=True,                 # Transient write errors pe retry
        retryReads=True,                  # Transient read errors pe retry
    )
    return client

def check_connection(client: MongoClient) -> bool:
    """Ping karke check karo ki connection alive hai."""
    try:
        # ping command — agar ok: 1 aaya to connected
        result = client.admin.command("ping")
        print(f"✅ MongoDB connected! Ping result: {result}")
        return True
    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        print(f"❌ MongoDB connection failed: {e}")
        return False

# Client create aur check karo
client = get_client()
if not check_connection(client):
    print("\n📋 Instructions:")
    print("1. Docker: docker run -d --name mongodb -p 27017:27017 \\")
    print("           -e MONGO_INITDB_ROOT_USERNAME=admin \\")
    print("           -e MONGO_INITDB_ROOT_PASSWORD=secret mongo:7.0")
    print("2. Or set MONGO_URI environment variable")
    exit(1)
```

### 🗄️ Database aur Collection Access

```python
# Method 1: Attribute access (readable)
db = client.practice_db
collection = db.products

# Method 2: Dictionary-style (dynamic names ke liye)
db = client["practice_db"]
collection = db["products"]

# Method 3: get_database() / get_collection()
db = client.get_database("practice_db")
collection = db.get_collection("products")

# Useful info
print(f"Database: {db.name}")
print(f"Collection: {collection.name}")
print(f"All databases: {client.list_database_names()}")
print(f"All collections: {db.list_collection_names()}")

# Server info
server_info = client.server_info()
print(f"MongoDB version: {server_info['version']}")
```

### ⚠️ Important: MongoClient is Thread-Safe

```python
# SAHI — Ek client, multiple threads share karo
client = MongoClient(MONGO_URI)  # Application start mein ek baar

def handle_request():
    db = client.practice_db          # Thread safe hai!
    result = db.products.find_one()  # OK
    return result

# GALAT — Har request mein naya client mat banao
def bad_practice():
    client = MongoClient(MONGO_URI)  # ❌ Connection pool waste hoga
    db = client.practice_db
    return db.products.find_one()
```

---

## 6. CRUD Operations

### ➕ INSERT Operations

#### insert_one()

```python
from datetime import datetime
from bson import ObjectId

db = client.practice_db
products = db.products

# Single document insert
result = products.insert_one({
    "name": "Laptop Pro X1",
    "brand": "TechBrand",
    "price": 85000,
    "category": "electronics",
    "in_stock": True,
    "rating": 4.5,
    "created_at": datetime.utcnow(),
    "tags": ["laptop", "gaming", "portable"],
    "specs": {
        "ram": "16GB",
        "storage": "512GB SSD",
        "display": "15.6 inch FHD"
    }
})

print(f"Inserted ID: {result.inserted_id}")         # ObjectId
print(f"Type: {type(result.inserted_id)}")          # <class 'bson.objectid.ObjectId'>
print(f"As string: {str(result.inserted_id)}")       # "64a1b2c3..."
print(f"Acknowledged: {result.acknowledged}")        # True
```

#### insert_many()

```python
# Multiple documents ek saath
products_list = [
    {"name": "Mouse", "price": 500, "category": "electronics", "stock": 100},
    {"name": "Keyboard", "price": 1200, "category": "electronics", "stock": 50},
    {"name": "T-Shirt", "price": 299, "category": "clothing", "stock": 200},
    {"name": "Python Book", "price": 799, "category": "books", "stock": 75},
]

result = products.insert_many(products_list)

print(f"Inserted count: {len(result.inserted_ids)}")
print(f"Inserted IDs: {result.inserted_ids}")    # List of ObjectIds
print(f"Acknowledged: {result.acknowledged}")

# ordered=False — Error pe bhi baaki documents insert karta hai
# By default ordered=True — first error pe ruk jaata hai
result = products.insert_many(products_list, ordered=False)
```

### 🔍 FIND Operations

#### find_one()

```python
# By _id (string ko ObjectId mein convert karo!)
doc = products.find_one({"_id": ObjectId("64a1b2c3d4e5f6a7b8c9d0e1")})

# By field value
doc = products.find_one({"name": "Mouse"})

# By multiple conditions (implicit AND)
doc = products.find_one({"category": "electronics", "in_stock": True})

# Agar nahi mila to None return karta hai
if doc is None:
    print("Document not found!")
else:
    print(doc)
```

#### find() — Multiple Documents

```python
# Sab documents
cursor = products.find()            # Cursor object milta hai (lazy)
all_docs = list(cursor)             # List mein convert karo

# Filter ke saath
electronics = products.find({"category": "electronics"})

# Cursor ko loop karo (memory efficient — full result load nahi hota)
for doc in products.find({"category": "books"}):
    print(doc["name"], doc["price"])

# Projection — sirf kuch fields chahiye
# 1 = include, 0 = exclude
# _id by default include hota hai
docs = products.find(
    {"category": "electronics"},
    {"name": 1, "price": 1, "_id": 0}  # sirf name aur price, no _id
)

# Sort — price descending
from pymongo import ASCENDING, DESCENDING
docs = products.find().sort("price", DESCENDING)

# Multiple sort keys
docs = products.find().sort([
    ("category", ASCENDING),
    ("price", DESCENDING)
])

# Limit aur Skip — Pagination ke liye
page = 2
page_size = 10
docs = products.find().skip((page - 1) * page_size).limit(page_size)

# Count
total = products.count_documents({"category": "electronics"})
print(f"Total electronics: {total}")

# Estimated count (faster but approximate)
approx = products.estimated_document_count()
```

### ✏️ UPDATE Operations

#### update_one() — Pehla matching document update karo

```python
# $set — fields update karo / naye fields add karo
result = products.update_one(
    {"name": "Mouse"},                      # Filter
    {"$set": {"price": 599, "updated_at": datetime.utcnow()}}  # Update
)
print(f"Matched: {result.matched_count}")
print(f"Modified: {result.modified_count}")

# $unset — field remove karo
result = products.update_one(
    {"name": "Mouse"},
    {"$unset": {"old_field": ""}}           # Value kuch bhi ho, field delete hogi

# $inc — number field increment/decrement karo
result = products.update_one(
    {"name": "Mouse"},
    {"$inc": {"stock": -1, "views": 1}}     # stock ghata, views badha

# $push — array mein element add karo (duplicates allowed)
result = products.update_one(
    {"name": "Laptop Pro X1"},
    {"$push": {"tags": "bestseller"}}

# $pull — array se element remove karo
result = products.update_one(
    {"name": "Laptop Pro X1"},
    {"$pull": {"tags": "old_tag"}}

# $addToSet — array mein add karo, but only if unique (Set behaviour)
result = products.update_one(
    {"name": "Laptop Pro X1"},
    {"$addToSet": {"tags": "gaming"}}       # Already exists? Nothing happens

# Upsert — agar document nahi mila to insert karo
result = products.update_one(
    {"name": "New Product"},
    {"$set": {"price": 999, "category": "misc"}},
    upsert=True
)
print(f"Upserted ID: {result.upserted_id}")  # None if updated, ObjectId if inserted
```

#### update_many() — Sab matching documents update karo

```python
# Sab electronics ko featured mark karo
result = products.update_many(
    {"category": "electronics"},
    {"$set": {"featured": True, "updated_at": datetime.utcnow()}}
)
print(f"Modified {result.modified_count} documents")

# Price 10% increase karo sab products ke liye
# Note: $mul operator hai multiply ke liye
result = products.update_many(
    {},  # Empty filter = sab documents
    {"$mul": {"price": 1.10}}
)
```

#### find_one_and_update() — Update karo aur updated doc return karo

```python
from pymongo import ReturnDocument

# Default: original document return karta hai (before update)
old_doc = products.find_one_and_update(
    {"name": "Mouse"},
    {"$inc": {"stock": -1}}
)

# Updated document return karo
new_doc = products.find_one_and_update(
    {"name": "Mouse"},
    {"$inc": {"stock": -1}},
    return_document=ReturnDocument.AFTER
)

# Projection ke saath
new_doc = products.find_one_and_update(
    {"name": "Mouse"},
    {"$set": {"status": "updated"}},
    projection={"name": 1, "status": 1},
    return_document=ReturnDocument.AFTER
)
```

#### replace_one() — Poora document replace karo

```python
# _id same rahega, baaki sab replace hoga
result = products.replace_one(
    {"name": "Old Product"},
    {
        "name": "New Product",
        "price": 1500,
        "category": "electronics",
        "replaced_at": datetime.utcnow()
    }
)
print(f"Matched: {result.matched_count}, Modified: {result.modified_count}")
```

### 🗑️ DELETE Operations

```python
# delete_one() — Pehla matching document delete karo
result = products.delete_one({"name": "Old Item"})
print(f"Deleted: {result.deleted_count}")     # 0 ya 1

# delete_many() — Sab matching documents delete karo
result = products.delete_many({"category": "discontinued"})
print(f"Deleted: {result.deleted_count}")

# Sab documents delete karo (collection empty karo)
result = products.delete_many({})
print(f"Deleted all: {result.deleted_count}")

# find_one_and_delete() — Delete karo aur deleted doc return karo
deleted_doc = products.find_one_and_delete(
    {"price": {"$lt": 100}},
    projection={"name": 1, "price": 1}
)
print(f"Deleted document: {deleted_doc}")

# Collection drop karo (collection + indexes bhi delete)
db.drop_collection("temp_collection")
# ya
db.temp_collection.drop()
```

---

## 7. Query Operators

### 🔢 Comparison Operators

| Operator | Meaning | SQL Equivalent | Example |
|---|---|---|---|
| `$eq` | Equal to | `=` | `{"price": {"$eq": 500}}` |
| `$ne` | Not equal to | `!=` or `<>` | `{"status": {"$ne": "deleted"}}` |
| `$gt` | Greater than | `>` | `{"price": {"$gt": 1000}}` |
| `$gte` | Greater than or equal | `>=` | `{"rating": {"$gte": 4.0}}` |
| `$lt` | Less than | `<` | `{"stock": {"$lt": 10}}` |
| `$lte` | Less than or equal | `<=` | `{"price": {"$lte": 5000}}` |
| `$in` | In a list | `IN (...)` | `{"category": {"$in": ["books", "electronics"]}}` |
| `$nin` | Not in a list | `NOT IN (...)` | `{"status": {"$nin": ["deleted", "archived"]}}` |

```python
# Examples
# Price between 500 and 2000
docs = products.find({"price": {"$gte": 500, "$lte": 2000}})

# Multiple categories
docs = products.find({"category": {"$in": ["electronics", "books"]}})

# Not in discontinued categories
docs = products.find({"category": {"$nin": ["discontinued", "archived"]}})

# Rating 4 se zyada
docs = products.find({"rating": {"$gt": 4.0}})
```

### 🔗 Logical Operators

| Operator | Meaning | SQL Equivalent |
|---|---|---|
| `$and` | Both conditions true | `AND` |
| `$or` | Any condition true | `OR` |
| `$not` | Condition false | `NOT` |
| `$nor` | None of the conditions true | `NOT (A OR B)` |

```python
# $and — Electronics jo 10000 se zyada expensive hain
docs = products.find({
    "$and": [
        {"category": "electronics"},
        {"price": {"$gt": 10000}}
    ]
})
# Shorthand — implicit AND
docs = products.find({"category": "electronics", "price": {"$gt": 10000}})

# $or — Books ya 500 se sasta
docs = products.find({
    "$or": [
        {"category": "books"},
        {"price": {"$lt": 500}}
    ]
})

# $not — 1000 se zyada nahi (same as $lte 1000)
docs = products.find({"price": {"$not": {"$gt": 1000}}})

# $nor — na books na electronics
docs = products.find({
    "$nor": [
        {"category": "books"},
        {"category": "electronics"}
    ]
})

# Complex combination
docs = products.find({
    "$and": [
        {"$or": [{"category": "electronics"}, {"category": "books"}]},
        {"price": {"$lt": 5000}},
        {"in_stock": True}
    ]
})
```

### 🧩 Element Operators

| Operator | Meaning | Example |
|---|---|---|
| `$exists` | Field exist karta hai ya nahi | `{"discount": {"$exists": True}}` |
| `$type` | Field ka BSON type check karo | `{"price": {"$type": "double"}}` |

```python
# Discount field wale products
docs = products.find({"discount": {"$exists": True}})

# Discount field nahi wale
docs = products.find({"discount": {"$exists": False}})

# Price jo string hai (data quality check)
docs = products.find({"price": {"$type": "string"}})

# Multiple types (price int32 ya double dono)
docs = products.find({"price": {"$type": ["int", "double"]}})

# Type numbers bhi use ho sakte
# 1=double, 2=string, 7=objectId, 8=bool, 9=date, 10=null, 16=int, 18=long
docs = products.find({"price": {"$type": 16}})  # int32
```

### 📋 Array Operators

| Operator | Meaning | Example |
|---|---|---|
| `$all` | Array mein ye sab elements hone chahiye | `{"tags": {"$all": ["gaming", "laptop"]}}` |
| `$elemMatch` | Array ka koi element ye conditions satisfy kare | `{"scores": {"$elemMatch": {"$gt": 80, "$lt": 95}}}` |
| `$size` | Array ka size exact match | `{"tags": {"$size": 3}}` |

```python
# Products jo gaming aur laptop dono tags have karein
docs = products.find({"tags": {"$all": ["gaming", "laptop"]}})

# Reviews array mein koi review jiska rating > 4 aur comment "good" ho
docs = db.reviews.find({
    "reviews": {
        "$elemMatch": {
            "rating": {"$gte": 4},
            "verified": True
        }
    }
})

# Exactly 3 tags wale products
docs = products.find({"tags": {"$size": 3}})

# Simple array element match (exact value)
docs = products.find({"tags": "gaming"})   # tags array mein "gaming" ho

# Dot notation for nested array
docs = products.find({"specs.features": "fast-charging"})
```

### 🔍 Evaluation Operators

| Operator | Meaning | Use Case |
|---|---|---|
| `$regex` | Regular expression match | Text search, pattern matching |
| `$expr` | Aggregation expressions in find | Field-to-field comparison |
| `$where` | JavaScript expression (AVOID!) | Complex logic (slow, insecure) |
| `$text` | Full-text search (needs text index) | Search functionality |
| `$mod` | Modulo operation | Even/odd numbers |

```python
import re

# $regex — case insensitive name search
docs = products.find({"name": {"$regex": "laptop", "$options": "i"}})

# Python re object bhi use kar sakte ho
docs = products.find({"name": re.compile("laptop", re.IGNORECASE)})

# Start with "Pro"
docs = products.find({"name": {"$regex": "^Pro"}})

# $expr — ek field ka dusre se comparison
# Sold quantity > stock remaining
docs = db.inventory.find({
    "$expr": {"$gt": ["$sold", "$remaining_stock"]}
})

# $text search (pehle text index banana hoga)
db.products.create_index([("name", "text"), ("description", "text")])
docs = products.find({"$text": {"$search": "gaming laptop"}})

# $mod — even stock wale products
docs = products.find({"stock": {"$mod": [2, 0]}})  # stock % 2 == 0
```

---

## 8. bulk_write()

Bulk write performance ke liye use hota hai. **Multiple operations ek single network roundtrip mein** bhejte hain.

### 🚀 Why bulk_write?

```python
# SLOW — N network calls
for i in range(1000):
    products.insert_one({"name": f"Product {i}", "price": i * 100})

# FAST — 1 network call (batched internally)
from pymongo import InsertOne, UpdateOne, UpdateMany, DeleteOne, DeleteMany, ReplaceOne
from pymongo.errors import BulkWriteError

operations = [InsertOne({"name": f"Product {i}", "price": i * 100}) for i in range(1000)]
result = products.bulk_write(operations)
```

### 📝 All Bulk Write Operations

```python
operations = [
    # InsertOne — naya document insert karo
    InsertOne({"name": "Bulk Product 1", "price": 100, "category": "test"}),
    InsertOne({"name": "Bulk Product 2", "price": 200, "category": "test"}),

    # UpdateOne — pehla matching update karo
    UpdateOne(
        {"name": "Existing Product"},          # Filter
        {"$set": {"updated": True}},            # Update
        upsert=True                             # Insert if not found
    ),

    # UpdateMany — sab matching update karo
    UpdateMany(
        {"category": "test"},
        {"$set": {"bulk_processed": True}}
    ),

    # DeleteOne — pehla matching delete karo
    DeleteOne({"name": "Old Product"}),

    # DeleteMany — sab matching delete karo
    DeleteMany({"status": "expired"}),

    # ReplaceOne — pura document replace karo
    ReplaceOne(
        {"sku": "ABC123"},
        {"sku": "ABC123", "name": "Replaced", "price": 999},
        upsert=True
    ),
]

try:
    # ordered=True (default) — Error pe ruk jaata hai
    # ordered=False — Error pe continue karta hai (BETTER PERFORMANCE)
    result = products.bulk_write(operations, ordered=False)

    print(f"Inserted: {result.inserted_count}")
    print(f"Matched: {result.matched_count}")
    print(f"Modified: {result.modified_count}")
    print(f"Deleted: {result.deleted_count}")
    print(f"Upserted: {result.upserted_count}")
    print(f"Upserted IDs: {result.upserted_ids}")

except BulkWriteError as e:
    print(f"Bulk write had errors: {e.details}")
    # e.details['writeErrors'] mein error list hai
    # e.details['nInserted'], e.details['nModified'] etc.
    # Partially successful operations bhi complete ho jaate hain (ordered=False)
```

### ⚡ Performance Tips

```python
# Tip 1: ordered=False for maximum performance
# Error pe bhi baaki operations continue hoti hain
result = products.bulk_write(operations, ordered=False)

# Tip 2: Large datasets ko chunks mein bhejo
def bulk_insert_chunked(collection, documents, chunk_size=1000):
    """Large document list ko chunked bulk insert karo."""
    total_inserted = 0
    for i in range(0, len(documents), chunk_size):
        chunk = documents[i:i + chunk_size]
        ops = [InsertOne(doc) for doc in chunk]
        result = collection.bulk_write(ops, ordered=False)
        total_inserted += result.inserted_count
        print(f"Progress: {min(i + chunk_size, len(documents))}/{len(documents)}")
    return total_inserted

# Tip 3: Bypass document validation for speed (if you trust your data)
result = products.bulk_write(operations, bypass_document_validation=True)
```

---

## 9. Schema Design Basics

### 🏗️ Embed vs Reference — Decision Table

MongoDB mein relationships ke liye do approaches hain:
1. **Embedding** — Related data ko same document mein rakh do
2. **Referencing** — Alag collection mein rakh do, ObjectId se link karo

| Scenario | Approach | Example |
|---|---|---|
| **1:1 relationship** | **Embed** (always) | User ka address, Profile settings |
| **1:Few (< 10-20 items)** | **Embed** | Blog post ke comments (few), Order items |
| **1:Many (unbounded growth)** | **Reference** | Customer ke orders, Author ke books |
| **Many:Many** | **Reference** (with junction OR array of refs) | Products aur Categories, Students aur Courses |
| **Data frequently updated independently** | **Reference** | Product price, User profile |
| **Data always read together** | **Embed** | Invoice aur its line items |
| **Related data is large (>16MB risk)** | **Reference** | Blog post comments (thousands) |
| **Need to query related data independently** | **Reference** | Orders (query without loading user) |

### Embedding Example (1:1)

```python
# GOOD — User ke saath address embed karo
{
    "_id": ObjectId("..."),
    "name": "Rahul Sharma",
    "email": "rahul@example.com",
    "address": {              # Embedded — always together
        "street": "123 MG Road",
        "city": "Mumbai",
        "state": "Maharashtra",
        "pincode": "400001"
    }
}
```

### Embedding Example (1:Few)

```python
# GOOD — Order ke saath items embed karo (order delete = items delete)
{
    "_id": ObjectId("..."),
    "order_number": "ORD-2024-001",
    "customer_id": ObjectId("..."),  # Reference to user
    "items": [                        # Embedded — finite list
        {"product_id": ObjectId("..."), "name": "Laptop", "qty": 1, "price": 85000},
        {"product_id": ObjectId("..."), "name": "Mouse", "qty": 2, "price": 500},
    ],
    "total": 86000,
    "status": "delivered"
}
```

### Referencing Example (1:Many)

```python
# GOOD — Customer ke orders alag collection mein
# Customer document:
{
    "_id": ObjectId("customer_id"),
    "name": "Priya Patel",
    "email": "priya@example.com"
    # Orders yahan nahi — bahut zyada ho sakte hain!
}

# Order document (alag collection):
{
    "_id": ObjectId("order_id"),
    "customer_id": ObjectId("customer_id"),   # Reference
    "total": 15000,
    "status": "shipped"
}

# Customer ke sab orders find karo:
orders = db.orders.find({"customer_id": customer["_id"]})
```

### Anti-Patterns (Avoid Karo)

```python
# ❌ GALAT — Unbounded array (never grow arrays without limit)
{
    "_id": ObjectId("..."),
    "name": "Popular Blog Post",
    "comments": [   # Yeh thousands tak badh sakta hai → 16MB limit!
        {"text": "...", "author": "..."},
        # ... hazaaron comments
    ]
}

# ✅ SAHI — Comments alag collection mein
# comments collection:
{
    "_id": ObjectId("..."),
    "post_id": ObjectId("..."),   # Reference to post
    "text": "Great post!",
    "author": "user123",
    "created_at": datetime.utcnow()
}
```

---

## 10. ObjectId Deep Dive

### 🔑 ObjectId Structure

```python
from bson import ObjectId
from datetime import datetime, timezone

# New ObjectId generate karo
oid = ObjectId()
print(f"ObjectId: {oid}")                    # ObjectId('64a1b2c3d4e5f6a7b8c9d0e1')
print(f"String: {str(oid)}")                 # '64a1b2c3d4e5f6a7b8c9d0e1'
print(f"Bytes: {oid.binary}")                # 12 bytes binary
print(f"Generation time: {oid.generation_time}")  # datetime object (UTC)

# String se ObjectId banao (most common use case)
oid_str = "64a1b2c3d4e5f6a7b8c9d0e1"
oid = ObjectId(oid_str)

# Invalid string se banane pe error
try:
    bad_oid = ObjectId("invalid_string")
except Exception as e:
    print(f"Error: {e}")  # bson.errors.InvalidId

# Creation time extract karo
creation_time = oid.generation_time
print(f"Document created at: {creation_time}")

# ObjectId sort by time karo (ObjectId mein timestamp hai!)
# Matlab: ObjectId sort karna = chronological sort
recent_docs = products.find().sort("_id", DESCENDING).limit(10)

# Date range query using ObjectId (no date field needed!)
from bson import ObjectId
import calendar

def date_to_objectid(dt: datetime) -> ObjectId:
    """Datetime ko ObjectId mein convert karo (range queries ke liye)."""
    timestamp = int(dt.timestamp())
    hex_timestamp = format(timestamp, '08x')
    return ObjectId(hex_timestamp + "0000000000000000")

start = date_to_objectid(datetime(2024, 1, 1))
end = date_to_objectid(datetime(2024, 12, 31))

# January 2024 ke documents
docs = products.find({"_id": {"$gte": start, "$lte": end}})

# Validation utility
def is_valid_objectid(oid_str: str) -> bool:
    """String valid ObjectId hai ya nahi check karo."""
    try:
        ObjectId(oid_str)
        return True
    except Exception:
        return False
```

---

## 11. Connection Pool Configuration

### 🔧 Pool Parameters Explained

```python
client = MongoClient(
    MONGO_URI,

    # ── POOL SIZE ──
    maxPoolSize=100,            # Max connections in pool (default: 100)
    minPoolSize=10,             # Min connections keep alive (default: 0)

    # ── TIMEOUTS ──
    serverSelectionTimeoutMS=5000,    # Server select karne ka max time (default: 30s)
    connectTimeoutMS=10000,           # Initial TCP connection timeout (default: 20s)
    socketTimeoutMS=45000,            # Read/write socket timeout (default: none)

    # ── RELIABILITY ──
    retryWrites=True,           # Transient errors pe writes retry (default: True in Atlas)
    retryReads=True,            # Transient errors pe reads retry

    # ── WRITE CONCERN ──
    w=1,                        # Acknowledged by 1 node (default)
    # w="majority"              # Majority nodes acknowledge (safer)
    # w=0                       # Fire and forget (fastest, no guarantee)
    journal=True,               # Journal (disk) pe likhne ke baad acknowledge

    # ── READ PREFERENCE ──
    # readPreference="primary"          # Default — primary se read
    # readPreference="primaryPreferred" # Primary prefer, secondary fallback
    # readPreference="secondary"        # Secondary se read (stale data possible)
    # readPreference="secondaryPreferred"
    # readPreference="nearest"          # Lowest latency

    # ── COMPRESSION ──
    compressors=["zstd", "zlib", "snappy"],  # Network compression
)
```

### Write Concern aur Read Preference — Interview Critical Concepts

**Write Concern** — MongoDB ko batao ki "write successful" kab maano:
```
w=0  → "Fire and forget" — acknowledgment nahi chahiye (fastest, risky)
w=1  → Primary node ne confirm kiya (default)
w=2  → Primary + 1 secondary ne confirm kiya
w="majority" → Majority nodes ne confirm kiya (safest for replica set)
```

**Read Preference** — Replica set mein kahan se read karo:
```
primary           → Sirf primary se (fresh data, default)
primaryPreferred  → Primary prefer, secondary fallback
secondary         → Sirf secondary se (possibly stale, reduces primary load)
secondaryPreferred → Secondary prefer, primary fallback
nearest           → Lowest network latency wala node
```

### 🏭 Production-Ready Client (Flask/FastAPI ke liye)

```python
import os
from pymongo import MongoClient
from pymongo.errors import ConfigurationError
import threading

class MongoDB:
    """Thread-safe MongoDB singleton."""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def initialize(self, uri: str = None):
        if self._initialized:
            return
        self._client = MongoClient(
            uri or os.getenv("MONGO_URI"),
            maxPoolSize=100,
            minPoolSize=10,
            serverSelectionTimeoutMS=5000,
            retryWrites=True,
        )
        self._initialized = True

    @property
    def client(self) -> MongoClient:
        if not self._initialized:
            raise RuntimeError("MongoDB not initialized. Call initialize() first.")
        return self._client

    def get_db(self, db_name: str):
        return self.client[db_name]

    def close(self):
        if self._initialized:
            self._client.close()
            self._initialized = False

# Usage
db_manager = MongoDB()
db_manager.initialize()

# FastAPI lifespan mein:
# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     db_manager.initialize()
#     yield
#     db_manager.close()
```

---

## 12. Interview Q&A

### 📋 15 Most-Asked MongoDB Interview Questions

---

**Q1: MongoDB aur SQL databases mein fundamental difference kya hai?**

**Answer:**
MongoDB ek document-oriented NoSQL database hai jabki SQL (PostgreSQL/MySQL) relational databases hain.

Key differences:
- **Data Model:** MongoDB JSON-like BSON documents mein store karta hai; SQL rows/columns mein
- **Schema:** MongoDB schema-less hai (flexible), SQL strict schema follow karta hai (DDL required)
- **Relationships:** SQL mein native JOINs hain; MongoDB mein embedding ya `$lookup` use karte hain
- **Scaling:** MongoDB horizontally scale karta hai (sharding); SQL primary vertical scaling
- **ACID:** MongoDB 4.0+ se multi-document transactions support karta hai lekin overhead zyada hai; SQL full ACID by default
- **Use case:** MongoDB catalog, CMS, real-time apps ke liye better; SQL financial systems, complex reporting ke liye

---

**Q2: ObjectId ka structure kya hota hai?**

**Answer:**
ObjectId 12 bytes (24 hex chars) ka hota hai:
- Bytes 0-3: Unix timestamp (seconds) — yeh batata hai document kab create hua
- Bytes 4-8: Machine identifier / random value
- Bytes 9-11: Incrementing counter

Iska fayda yeh hai ki ObjectId sort karna = chronological sort karna. Aur creation time seedha ObjectId se extract ki ja sakti hai bina alag `created_at` field ke.

---

**Q3: BSON aur JSON mein kya difference hai?**

**Answer:**
| Feature | JSON | BSON |
|---|---|---|
| Encoding | Text (UTF-8) | Binary |
| Size | Larger | Compact |
| Parse Speed | Slower | Faster |
| Data Types | 6 types | 20+ types |
| Extra Types | None | ObjectId, Date, Int32, Int64, Decimal128, Binary |

MongoDB internally BSON store karta hai. Network pe bhi BSON travel karta hai. JSON ke barabar semantics hain but binary encoded hone se performance better hai.

---

**Q4: Embed kab karo aur Reference kab karo?**

**Answer:**
**Embed karo jab:**
- Data hamesha saath access hota ho (1:1 ya 1:few)
- Related data independent queries nahi hoti
- List bounded ho (10-20 items max)
- Example: User ka address, Order ke line items

**Reference karo jab:**
- Data independently query hota ho
- Many-to-many relationship ho
- Array unbounded grow ho sakta ho
- Data frequently update hota ho independently
- Example: Orders ke customers, Products ke categories

---

**Q5: Cursor kya hota hai aur kyun use karte hain?**

**Answer:**
`find()` method ek **Cursor object** return karta hai — results ka lazy iterator. Poora result set ek saath memory mein load nahi hota.

```python
cursor = db.collection.find()  # Yahan query nahi chali abhi

for doc in cursor:             # Yahan server se batch-by-batch documents fetch hote hain
    process(doc)

# list() se sab ek saath load hoga — careful with large datasets!
all_docs = list(db.collection.find())  # Memory issue if millions of docs
```

MongoDB cursor internally **batch size 101 documents** (first batch) aur phir **4MB batches** use karta hai. `cursor.batch_size(n)` se change kar sakte ho.

---

**Q6: explain() kab use karte hain?**

**Answer:**
`explain()` query execution plan batata hai — MongoDB query kaise execute kar raha hai:

```python
# executionStats verbosity mode
plan = db.products.find({"price": {"$gt": 1000}}).explain("executionStats")

# Key cheezein dekhni hain:
# winningPlan.stage: "COLLSCAN" (bad) ya "IXSCAN" (good)
# executionStats.nReturned: kitne docs return hue
# executionStats.totalDocsExamined: kitne docs scan hue
# executionStats.totalKeysExamined: kitne index keys scan hue
# executionStats.executionTimeMillis: time in ms
```

**COLLSCAN** = Collection Scan (poori collection scan ki) — slow for large collections
**IXSCAN** = Index Scan — index use hua, fast

Ratio check karo: `nReturned / totalDocsExamined` — 1:1 perfect, 1:100 bad (add index)

---

**Q7: CAP Theorem kya hai? MongoDB kahan stand karta hai?**

**Answer:**
CAP Theorem kehta hai ki distributed system mein teeno ek saath nahi ho sakta:
- **C**onsistency — Every read gets the most recent write
- **A**vailability — Every request gets a response (success or failure)
- **P**artition Tolerance — System works even if network partition ho jaye

**MongoDB = CP (Consistency + Partition Tolerance) by default**

Kyunki:
- Replica set mein primary se read by default (Consistency)
- Network partition hone pe primary election hoti hai (partition tolerant)
- Lekin election ke dauran (10-30 seconds) writes fail ho sakte hain (Availability sacrifice)

`readPreference: "secondary"` set karne pe AP ho jaata hai (stale reads possible but always available).

---

**Q8: Write Concern kya hota hai? Production mein kya use karo?**

**Answer:**
Write Concern MongoDB ko batata hai ki write "successful" kab considered ho:

- `w=0`: Fire and forget (no ack) — fastest, data loss possible
- `w=1`: Primary acknowledged — default, reasonable
- `w="majority"`: Majority nodes acknowledged — safest for replica set
- `j=true`: Journal flush hone ke baad acknowledge — persistence guarantee

**Production recommendation:**
- Financial/critical data: `w="majority", j=True`
- High-throughput, less critical: `w=1`
- Logs/analytics: `w=0` acceptable

```python
# Collection level set karo
db = client.get_database("mydb", write_concern=WriteConcern("majority", j=True))
```

---

**Q9: Read Preference kya hota hai aur kab secondary reads use karo?**

**Answer:**
Read Preference define karta hai ki replica set mein read kahan se hoga.

`secondary` reads kab use karo:
- Analytics/reporting queries jo stale data allow karti hain
- Heavy read workload ko primary se distribute karna ho
- Backup/archiving operations

`secondary` reads kab mat karo:
- User ke apne data read karne pe (profile, order status) — stale ho sakta hai
- Just wrote kuch — read-your-own-writes needed

**Monotonic Read Concern** — Ensure karta hai ki reads degrade na karen (hamesha atleast same state ya newer)

---

**Q10: pymongo thread-safe hai?**

**Answer:**
Haan, `MongoClient` thread-safe hai. Yeh internally **connection pool** maintain karta hai. Multiple threads ek hi MongoClient share kar sakti hain — yeh recommended practice bhi hai.

```python
# CORRECT — Ek client, application-wide share karo
client = MongoClient(MONGO_URI)  # Once at startup

# Thread 1
db = client.mydb
result1 = db.col.find_one({"id": 1})  # Uses pool

# Thread 2 (concurrently)
result2 = db.col.find_one({"id": 2})  # Uses pool
```

Par `Database` aur `Collection` objects bhi thread-safe hain. Har operation ke liye pool se connection liya jaata hai, use hota hai, aur wapas rakh diya jaata hai.

---

**Q11: Indexing ke types kya hain MongoDB mein?**

**Answer:**
- **Single Field:** `db.col.create_index("price")` — Ek field pe
- **Compound:** `db.col.create_index([("category", 1), ("price", -1)])` — Multiple fields
- **Multikey:** Array field pe automatically — `tags: ["gaming", "laptop"]`
- **Text:** `db.col.create_index([("name", "text")])` — Full-text search
- **Geospatial:** 2dsphere ya 2d — Location-based queries
- **Hashed:** `db.col.create_index("user_id", hashing=True)` — Sharding ke liye
- **TTL:** `db.col.create_index("expires_at", expireAfterSeconds=0)` — Auto-delete
- **Wildcard:** `db.col.create_index({"$**": 1})` — Dynamic fields
- **Sparse:** Only documents jo field rakhte hain

---

**Q12: $lookup aggregation kya karta hai?**

**Answer:**
`$lookup` MongoDB ka JOIN equivalent hai. Two collections ko join karta hai aggregation pipeline mein.

```python
pipeline = [
    {
        "$lookup": {
            "from": "orders",          # Join karne wali collection
            "localField": "_id",       # Current collection ka field
            "foreignField": "user_id", # orders collection ka field
            "as": "user_orders"        # Result array field name
        }
    }
]
users_with_orders = list(db.users.aggregate(pipeline))
```

SQL `LEFT OUTER JOIN` ke equivalent hai — matching documents nahi mila to empty array aata hai.

---

**Q13: Aggregation Pipeline kya hai?**

**Answer:**
Aggregation Pipeline ek series of stages hain jo documents process karte hain, ek stage ka output dusre ka input banta hai (Unix pipe jaisa):

Common Stages:
- `$match` — Filter (WHERE clause)
- `$group` — Group + aggregate (GROUP BY)
- `$sort` — Sort karo
- `$limit` / `$skip` — Pagination
- `$project` — Field select/transform
- `$lookup` — JOIN
- `$unwind` — Array ko individual documents mein expand
- `$addFields` — Naye fields add karo
- `$facet` — Multiple pipelines ek saath

```python
pipeline = [
    {"$match": {"category": "electronics"}},
    {"$group": {"_id": "$brand", "avg_price": {"$avg": "$price"}, "count": {"$sum": 1}}},
    {"$sort": {"avg_price": -1}},
    {"$limit": 5}
]
result = list(db.products.aggregate(pipeline))
```

---

**Q14: MongoDB transactions kab use karo?**

**Answer:**
MongoDB 4.0+ se multi-document ACID transactions available hain (replica set pe), 4.2+ se sharded clusters pe bhi.

**Use transactions jab:**
- Multiple documents atomically update karne hों
- Financial operations (transfer money between accounts)
- Inventory update + order creation saath

**Avoid transactions jab:**
- Single document update (already atomic)
- Performance critical path pe (transactions ~2-3x slower)
- Schema redesign se avoid ho sakta ho (embed karo)

```python
with client.start_session() as session:
    with session.start_transaction():
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
        # Automatic commit/rollback
```

---

**Q15: MongoDB mein data consistency ensure kaise karte hain distributed environment mein?**

**Answer:**
MongoDB consistency ensure karta hai through:

1. **Write Concern (`w="majority"`)**: Write majority nodes pe acknowledge hone ke baad hi success — node failure pe data loss nahi
2. **Read Concern (`"majority"`)**: Sirf majority-acknowledged data read karo — stale reads nahi
3. **Sessions aur Causally Consistent Reads**: Ek session mein writes ke baad reads latest data dekhte hain
4. **Replica Set Elections**: Primary fail hone pe automatic election (10-30 sec) — high availability
5. **Transactions**: Multi-document atomicity (4.0+)
6. **Retryable Writes/Reads**: Network blip pe automatic retry

```python
# Maximum consistency ke liye
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern
from pymongo.read_preferences import ReadPreference

db = client.get_database(
    "mydb",
    write_concern=WriteConcern("majority"),
    read_concern=ReadConcern("majority"),
    read_preference=ReadPreference.PRIMARY
)
```

**Trade-off:** Consistency badhaane se latency badhti hai. Production mein use-case ke hisaab se tune karo.

---

## 🎯 Quick Revision Cheatsheet

```
MongoDB = Document DB (BSON documents)
Collection = Table, Document = Row, Field = Column
_id = ObjectId (12 bytes: timestamp + machine + counter)
BSON superset of JSON: adds ObjectId, Date, Int32/64, Decimal128, Binary

CRUD:
  INSERT: insert_one(doc), insert_many([docs])
  READ:   find_one(filter), find(filter, projection).sort().limit().skip()
  UPDATE: update_one(filter, {"$set": {}}), update_many(), upsert=True
  DELETE: delete_one(filter), delete_many(filter)

Update Operators: $set, $unset, $inc, $mul, $push, $pull, $addToSet
Query Operators:  $eq, $ne, $gt, $gte, $lt, $lte, $in, $nin
Logical:          $and, $or, $not, $nor
Array:            $all, $elemMatch, $size
Evaluation:       $regex, $expr, $text

Performance:
  bulk_write() = multiple ops, 1 network call, ordered=False for speed
  explain("executionStats") = query plan, COLLSCAN bad / IXSCAN good
  Connection Pool: maxPoolSize=100, shared across threads

CAP: MongoDB = CP (Consistency + Partition Tolerance) by default
Write Concern: w=0 (fast) → w=1 (default) → w="majority" (safe)
Read Preference: primary (fresh) → secondary (stale but scales reads)
```

---

*Last Updated: 2026-05 | Target: 5 YOE Python Backend + Agentic AI | 20 LPA*
