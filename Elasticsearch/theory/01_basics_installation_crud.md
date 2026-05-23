# Elasticsearch — Basics, Installation & CRUD Operations
**Basic Level | What, Why, How**

---

## Quick Concepts
- **Elasticsearch** = Distributed, RESTful search & analytics engine — Apache Lucene pe built
- **Index** = Database ki tarah — documents ka collection (SQL table jaisa socho)
- **Document** = JSON object — stored, indexed, searchable unit (SQL row jaisa)
- **Shard** = Index ka piece — horizontal scaling ke liye
- **Replica** = Shard ki copy — high availability ke liye
- **Node** = Ek Elasticsearch server instance
- **Cluster** = Multiple nodes ka group — ek naam se identify hota hai
- **Inverted Index** = Word → document IDs mapping — blazing fast full-text search ka secret
- **Mapping** = Document ka schema — field types define karta hai

---

## What is Elasticsearch? Why use it?

```
Problem: SQL mein LIKE '%laptop%' karo →
  SELECT * FROM products WHERE description LIKE '%gaming laptop%'
  Time: 2-5 seconds on 10M rows ❌ (full table scan)
  Relevance? Zero — sorting by relevance possible nahi ❌
  Typos? "laotop" → zero results ❌

Elasticsearch ke saath:
  es.search(index="products", query={"match": {"description": "gaming laptop"}})
  Time: 10-50ms on 10M documents ✅ (inverted index)
  Relevance score → best match pehle ✅
  Fuzzy search → typos handle ✅

Elasticsearch ke main use cases:
  1. Full-text search     → E-commerce search, blog search
  2. Log analytics        → ELK Stack (Elasticsearch + Logstash + Kibana)
  3. APM / Observability  → Application performance monitoring
  4. Autocomplete         → Search suggestions
  5. Geospatial search    → "restaurants near me"
  6. Business analytics   → Aggregations, dashboards
```

### Elasticsearch vs SQL vs Redis

```
┌──────────────────┬──────────────────┬──────────────────┬──────────────────┐
│ Feature          │ Elasticsearch    │ SQL (PostgreSQL)  │ Redis            │
├──────────────────┼──────────────────┼──────────────────┼──────────────────┤
│ Data model       │ JSON documents   │ Tables/rows       │ Key-value        │
│ Full-text search │ ✅ Excellent      │ ❌ Limited        │ ❌ No            │
│ Exact match      │ ✅ Good           │ ✅ Excellent      │ ✅ Excellent     │
│ Speed (search)   │ ✅ ~10-50ms       │ ❌ Slow on large  │ ✅ <1ms          │
│ Aggregations     │ ✅ Powerful       │ ✅ Good           │ ⚠️ Limited       │
│ Persistence      │ ✅ Disk           │ ✅ Disk           │ ⚠️ RAM primary   │
│ Transactions     │ ❌ No ACID        │ ✅ Full ACID      │ ❌ Limited       │
│ Schema           │ Flexible/dynamic │ Strict            │ Schema-less      │
│ Best for         │ Search/Analytics │ Transactional     │ Cache/Sessions   │
└──────────────────┴──────────────────┴──────────────────┴──────────────────┘

Rule of thumb:
  - Primary DB → SQL
  - Cache/Rate limiting → Redis  
  - Search/Analytics → Elasticsearch
```

---

## Core Architecture Concepts

```
Cluster "my-cluster"
├── Node 1 (master + data)
│   ├── Index "products"
│   │   ├── Primary Shard 0  ← actual data
│   │   └── Primary Shard 1
│   └── Index "orders"
│       └── Replica Shard 0  ← Node 2 ke Shard 0 ki copy
└── Node 2 (data)
    ├── Primary Shard 2
    └── Replica Shard 1      ← Node 1 ke Shard 1 ki copy

Index banate waqt settings:
  "number_of_shards": 3      → 3 parts mein split (scale reads/writes)
  "number_of_replicas": 1    → har shard ki 1 copy (HA ke liye)

Note: Same node pe primary aur uski replica KABHI nahi hoti ✅
```

---

## Docker Install + Python Client Setup

```bash
# ─── Elasticsearch Docker ───
docker run -d \
  --name es \
  -p 9200:9200 \
  -e "discovery.type=single-node" \
  -e "xpack.security.enabled=false" \
  elasticsearch:8.11.0

# Check kar ki chal raha hai
curl http://localhost:9200
# Response:
# { "name": "...", "cluster_name": "docker-cluster", "version": {...} }

# ─── Python client install ───
pip install elasticsearch

# Optional but recommended:
pip install elasticsearch[async]   # asyncio support ke liye
```

```python
# ─── Python Connection ───
from elasticsearch import Elasticsearch

# Basic connection
es = Elasticsearch("http://localhost:9200")

# Connection check
print(es.ping())        # True
print(es.info())        # cluster info

# Multiple nodes (production)
es = Elasticsearch([
    "http://node1:9200",
    "http://node2:9200",
    "http://node3:9200",
])

# With auth (security enabled ho toh)
es = Elasticsearch(
    "https://localhost:9200",
    basic_auth=("elastic", "password"),
    verify_certs=False,   # development only
)
```

---

## Index CRUD Operations

```python
from elasticsearch import Elasticsearch

es = Elasticsearch("http://localhost:9200")

# ════════════════════════════════════════════
# 1. INDEX CREATE — explicit mapping ke saath
# ════════════════════════════════════════════
mapping = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,   # single node pe 0
        "analysis": {
            "analyzer": {
                "my_analyzer": {
                    "type": "standard",
                    "stopwords": "_english_"
                }
            }
        }
    },
    "mappings": {
        "properties": {
            "title":       {"type": "text", "analyzer": "standard"},
            "brand":       {"type": "keyword"},          # exact match
            "price":       {"type": "float"},
            "in_stock":    {"type": "boolean"},
            "created_at":  {"type": "date"},
            "tags":        {"type": "keyword"},           # array of keywords
            "description": {"type": "text", "index": False},  # search nahi karni
            "location":    {"type": "geo_point"},
            "specs": {                                    # object type
                "type": "object",
                "properties": {
                    "ram":   {"type": "keyword"},
                    "storage": {"type": "keyword"}
                }
            },
            "reviews": {                                 # nested type
                "type": "nested",
                "properties": {
                    "user":   {"type": "keyword"},
                    "rating": {"type": "integer"},
                    "text":   {"type": "text"}
                }
            }
        }
    }
}

response = es.indices.create(index="products", body=mapping)
print(response)   # {'acknowledged': True, 'index': 'products'}

# ════════════════════════════════════════
# 2. INDEX GET — mapping aur settings dekho
# ════════════════════════════════════════
# Mapping dekho
mapping = es.indices.get_mapping(index="products")
print(mapping)

# Settings dekho
settings = es.indices.get_settings(index="products")
print(settings)

# Both ek saath
info = es.indices.get(index="products")
print(info)

# ════════════════════════════════════════
# 3. INDEX EXISTS
# ════════════════════════════════════════
exists = es.indices.exists(index="products")
print(exists)   # True ya False

# ════════════════════════════════════════
# 4. INDEX DELETE
# ════════════════════════════════════════
response = es.indices.delete(index="products")
print(response)   # {'acknowledged': True}

# ════════════════════════════════════════
# 5. INDEX REFRESH — naya data turant searchable
# ════════════════════════════════════════
es.indices.refresh(index="products")
# By default: 1 second mein auto-refresh
# Testing mein manually refresh karo

# ════════════════════════════════════════
# 6. ALL INDICES LIST
# ════════════════════════════════════════
indices = es.cat.indices(v=True, format="json")
for idx in indices:
    print(idx['index'], idx['docs.count'], idx['store.size'])
```

---

## Document CRUD Operations

```python
from elasticsearch import Elasticsearch
from datetime import datetime

es = Elasticsearch("http://localhost:9200")
INDEX = "products"

# ════════════════════════════════════════
# 1. DOCUMENT CREATE (Index karna)
# ════════════════════════════════════════

# Method A: Apna ID specify karo
doc = {
    "title": "MacBook Pro 16-inch",
    "brand": "Apple",
    "price": 199999.00,
    "in_stock": True,
    "created_at": datetime.now().isoformat(),
    "tags": ["laptop", "apple", "macos"],
    "specs": {
        "ram": "32GB",
        "storage": "1TB SSD"
    }
}

response = es.index(index=INDEX, id="prod-001", document=doc)
print(response['result'])     # 'created'
print(response['_id'])        # 'prod-001'
print(response['_version'])   # 1

# Method B: Auto-generate ID
response = es.index(index=INDEX, document=doc)
print(response['_id'])   # 'abc123xyz...' — auto generated

# ════════════════════════════════════════
# 2. DOCUMENT GET
# ════════════════════════════════════════
response = es.get(index=INDEX, id="prod-001")
print(response['_source'])     # actual document
print(response['_id'])         # 'prod-001'
print(response['_index'])      # 'products'
print(response['_version'])    # version number
print(response['found'])       # True

# Sirf kuch fields chahiye
response = es.get(
    index=INDEX, 
    id="prod-001",
    source_includes=["title", "price"]   # sirf yahi fields
)
print(response['_source'])   # {'title': ..., 'price': ...}

# ════════════════════════════════════════
# 3. DOCUMENT EXISTS
# ════════════════════════════════════════
exists = es.exists(index=INDEX, id="prod-001")
print(exists)   # True

# ════════════════════════════════════════
# 4. DOCUMENT UPDATE (Partial update)
# ════════════════════════════════════════

# Partial update — sirf specified fields update honge
response = es.update(
    index=INDEX,
    id="prod-001",
    doc={"price": 189999.00, "in_stock": False}
)
print(response['result'])     # 'updated'
print(response['_version'])   # 2 (version increment)

# Script se update (compute karo)
response = es.update(
    index=INDEX,
    id="prod-001",
    script={
        "source": "ctx._source.price -= params.discount",
        "params": {"discount": 10000}
    }
)
print(response['result'])   # 'updated'

# Upsert — exists toh update, nahi toh create
response = es.update(
    index=INDEX,
    id="prod-999",
    doc={"price": 5000},
    upsert={"title": "New Product", "price": 5000, "brand": "Generic"}
)
print(response['result'])   # 'created' (pehli baar)

# ════════════════════════════════════════
# 5. DOCUMENT DELETE
# ════════════════════════════════════════
response = es.delete(index=INDEX, id="prod-001")
print(response['result'])   # 'deleted'

# Query se delete (delete_by_query)
response = es.delete_by_query(
    index=INDEX,
    body={
        "query": {
            "term": {"in_stock": False}
        }
    }
)
print(response['deleted'])   # kitne documents delete hue

# ════════════════════════════════════════
# 6. DOCUMENT COUNT
# ════════════════════════════════════════
count = es.count(index=INDEX)
print(count['count'])   # total documents

# With query
count = es.count(
    index=INDEX,
    body={"query": {"term": {"brand": "Apple"}}}
)
print(count['count'])   # Apple ke kitne products
```

---

## Bulk Operations — helpers.bulk()

```python
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk, parallel_bulk, streaming_bulk

es = Elasticsearch("http://localhost:9200")

# ════════════════════════════════════════
# Method 1: helpers.bulk() — recommended
# ════════════════════════════════════════

# Bulk index karo
actions = [
    {
        "_index": "products",
        "_id": f"prod-{i}",
        "_source": {
            "title": f"Product {i}",
            "brand": "Samsung" if i % 2 == 0 else "Apple",
            "price": 10000 + i * 100,
            "in_stock": True,
        }
    }
    for i in range(1, 101)   # 100 documents
]

success, failed = bulk(es, actions)
print(f"Success: {success}, Failed: {len(failed)}")

# Bulk update
update_actions = [
    {
        "_op_type": "update",   # 'index', 'create', 'update', 'delete'
        "_index": "products",
        "_id": "prod-1",
        "doc": {"price": 15000}
    },
    {
        "_op_type": "delete",
        "_index": "products",
        "_id": "prod-2"
    }
]
success, failed = bulk(es, update_actions)

# ════════════════════════════════════════
# Method 2: Generator use karo — memory efficient
# ════════════════════════════════════════
import csv

def generate_actions(filepath):
    """CSV se documents generate karo — ek waqt ek row"""
    with open(filepath) as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield {
                "_index": "products",
                "_source": {
                    "title": row["title"],
                    "price": float(row["price"]),
                    "brand": row["brand"],
                }
            }

# Generator pass karo — sab memory mein nahi aata
success, failed = bulk(es, generate_actions("products.csv"), chunk_size=500)

# ════════════════════════════════════════
# Method 3: parallel_bulk — fastest
# ════════════════════════════════════════
actions = [
    {"_index": "products", "_id": str(i), "_source": {"title": f"Item {i}", "price": i * 10}}
    for i in range(10000)
]

# Thread pool se parallel index karo
for ok, response in parallel_bulk(
    es,
    actions,
    thread_count=4,    # 4 threads
    chunk_size=1000,   # 1000 docs per chunk
    raise_on_error=False
):
    if not ok:
        print(f"Error: {response}")

# ════════════════════════════════════════
# Method 4: es.bulk() low-level API
# ════════════════════════════════════════
body = [
    {"index": {"_index": "products", "_id": "p1"}},
    {"title": "Direct Bulk Product 1", "price": 999},
    {"index": {"_index": "products", "_id": "p2"}},
    {"title": "Direct Bulk Product 2", "price": 1999},
]
response = es.bulk(operations=body)
print(response['errors'])   # False if all ok
```

---

## Field Data Types

```python
# ════════════════════════════════════════
# Sab important data types with examples
# ════════════════════════════════════════

complete_mapping = {
    "mappings": {
        "properties": {
            # ─── String Types ───
            "title": {
                "type": "text",              # Full-text search ke liye
                "analyzer": "standard",      # tokenize + lowercase
                "fields": {
                    "keyword": {             # Exact match bhi chahiye?
                        "type": "keyword",   # Multi-field trick!
                        "ignore_above": 256
                    }
                }
            },
            "sku": {
                "type": "keyword"            # Exact match only — no analysis
            },
            "category": {
                "type": "keyword"            # Filter, sort, aggregation ke liye
            },

            # ─── Numeric Types ───
            "price": {"type": "float"},      # 32-bit float
            "cost":  {"type": "double"},     # 64-bit double
            "qty":   {"type": "integer"},    # 32-bit int
            "views": {"type": "long"},       # 64-bit int
            "rating": {"type": "scaled_float", "scaling_factor": 10},  # 4.5 → stored as 45

            # ─── Boolean ───
            "in_stock":  {"type": "boolean"},

            # ─── Date ───
            "created_at": {
                "type": "date",
                "format": "yyyy-MM-dd HH:mm:ss||yyyy-MM-dd||epoch_millis"
            },

            # ─── Binary ───
            "thumbnail": {"type": "binary"},  # Base64 encoded

            # ─── Geo Types ───
            "location": {"type": "geo_point"},   # lat/lon — "near me" queries
            "region":   {"type": "geo_shape"},   # polygons, lines

            # ─── Object Type — flat JSON object ───
            "specs": {
                "type": "object",
                "properties": {
                    "ram": {"type": "keyword"},
                    "cpu": {"type": "keyword"},
                    "screen_size": {"type": "float"}
                }
            },

            # ─── Nested Type — array of objects ───
            # Object array mein individual object queries ke liye nested zaroori hai
            "reviews": {
                "type": "nested",            # Each review independently queryable
                "properties": {
                    "user_id": {"type": "keyword"},
                    "stars":   {"type": "integer"},
                    "comment": {"type": "text"},
                    "date":    {"type": "date"}
                }
            },

            # ─── Array ─── (special type nahi — just multiple values)
            "tags": {"type": "keyword"},     # ["laptop", "gaming"] → keyword array

            # ─── index: false ─── (store karo but search nahi)
            "raw_description": {
                "type": "text",
                "index": False    # Searchable nahi — sirf _source mein hoga
            },

            # ─── IP Type ───
            "client_ip": {"type": "ip"},
        }
    }
}
```

---

## Mapping: Explicit vs Dynamic

```python
from elasticsearch import Elasticsearch

es = Elasticsearch("http://localhost:9200")

# ════════════════════════════════════════
# Dynamic Mapping — Elasticsearch khud decide karta hai
# ════════════════════════════════════════

# Bina mapping ke index karo
es.index(index="auto_index", id="1", document={
    "name": "Test",        # → text + keyword (multi-field)
    "age": 25,             # → long
    "score": 9.5,          # → float
    "active": True,        # → boolean
    "joined": "2024-01-15" # → date (agar format match kare)
})

# Dekhte hain kya hua
mapping = es.indices.get_mapping(index="auto_index")
print(mapping)
# Elasticsearch ne automatically types assign kiye

# ⚠️ Dynamic mapping ka problem:
# "price": "1999"  → text ban jaata hai (number chahiye tha!) ❌
# Production mein: explicit mapping ALWAYS better

# ════════════════════════════════════════
# Dynamic Mapping Control
# ════════════════════════════════════════

# dynamic: true  (default) — naye fields accept
# dynamic: false — naye fields ignore (index nahi), stored in _source
# dynamic: strict — naye fields pe ERROR throw

es.indices.create(index="strict_index", body={
    "mappings": {
        "dynamic": "strict",
        "properties": {
            "name": {"type": "keyword"},
            "age":  {"type": "integer"}
        }
    }
})

# Ab ye fail hoga:
try:
    es.index(index="strict_index", document={"name": "Alice", "unknown_field": "oops"})
except Exception as e:
    print(e)   # mapping set to strict, dynamic introduction of [unknown_field] disallowed

# ════════════════════════════════════════
# keyword vs text — main difference
# ════════════════════════════════════════

# text:
#   - Analyzed (tokenized + lowercased + stopwords removed)
#   - "Gaming Laptop Pro" → ["gaming", "laptop", "pro"]
#   - Full-text search ke liye ✅
#   - Sort/aggregate ke liye ❌ (too many terms)

# keyword:
#   - NOT analyzed — exact value stored as-is
#   - "Gaming Laptop Pro" → ["Gaming Laptop Pro"]
#   - Exact match, filter, sort, aggregate ke liye ✅
#   - Full-text search ke liye ❌

# Multi-field trick — dono chahiye?
es.indices.create(index="multi_field_demo", body={
    "mappings": {
        "properties": {
            "title": {
                "type": "text",         # Full-text search
                "fields": {
                    "raw": {
                        "type": "keyword"   # title.raw → exact match
                    }
                }
            }
        }
    }
})

# Usage:
# match query → "title"     (full-text)
# term query  → "title.raw" (exact)
# sort        → "title.raw" (sort by exact value)
```

---

## _source, _id, _index Fields

```python
from elasticsearch import Elasticsearch

es = Elasticsearch("http://localhost:9200")

# ════════════════════════════════════════
# Meta fields — har document mein automatically
# ════════════════════════════════════════

# _index  → index ka naam
# _id     → document ID (string)
# _source → original JSON document
# _version → kitni baar update hua
# _score  → search relevance score

# Document index karo
es.index(index="products", id="p1", document={
    "title": "iPhone 15",
    "price": 79999
})

# Get response mein ye sab hota hai:
resp = es.get(index="products", id="p1")
print(resp['_index'])    # 'products'
print(resp['_id'])       # 'p1'
print(resp['_version'])  # 1
print(resp['_source'])   # {'title': 'iPhone 15', 'price': 79999}
print(resp['found'])     # True

# _source control — kya return karo?
resp = es.get(
    index="products", 
    id="p1",
    source_includes=["title"],        # sirf title chahiye
    source_excludes=["description"]   # description nahi chahiye
)

# _source completely disable karo (space save karo)
es.indices.create(index="no_source_index", body={
    "mappings": {
        "_source": {"enabled": False}   # ⚠️ reindex possible nahi hoga baad mein
    }
})

# ID pe query karo — _ids query
resp = es.search(index="products", body={
    "query": {
        "ids": {"values": ["p1", "p2", "p3"]}
    }
})
```

---

## Interview Questions & Answers

---

### Q1: Elasticsearch aur SQL database mein kya fundamental fark hai?

**Answer:**
```
SQL Database:
  - Tabular data — rows aur columns
  - Structured schema — pehle define karo
  - ACID transactions — data integrity guaranteed
  - Joins — multiple tables relate karo
  - Best for: transactional apps, normalized data

Elasticsearch:
  - JSON documents — flexible structure
  - Dynamic/flexible schema
  - NO transactions (eventual consistency)
  - NO joins (denormalized data prefer karo)
  - Inverted index — text search blazing fast
  - Best for: search, analytics, logs

Real example:
  SQL: "Find all products named laptop" 
    → LIKE '%laptop%' → full table scan → 2-5 sec on 10M rows ❌
  
  ES: same query 
    → inverted index lookup → 10-50ms on 10M docs ✅
    + relevance score (best match pehle) ✅
    + fuzzy matching (typos handle) ✅
```

---

### Q2: Shard aur Replica kya hai? Kitne rakhne chahiye?

**Answer:**
```python
# Shard = Index ka horizontal partition
# - Write operations distribute hoti hain
# - Default: 1 primary shard (ES 7.x+), pehle 5 tha
# - Once set → CHANGE NAHI HO SAKTA (reindex zaroori)

# Replica = Primary shard ki copy
# - Read operations scale hoti hain  
# - Node failure pe data safe rehta hai
# - Runtime pe change ho sakta hai ✅

# Example: 3 shards, 1 replica, 3 nodes
es.indices.create(index="big_index", body={
    "settings": {
        "number_of_shards": 3,       # 3 primary shards
        "number_of_replicas": 1      # har primary ka 1 replica
    }
})
# Total shards = 3 primary + 3 replicas = 6 shards
# Node 1: Primary 0, Replica 1
# Node 2: Primary 1, Replica 2
# Node 3: Primary 2, Replica 0

# Rules:
# Single node development → replicas: 0 (replica ke liye doosra node chahiye)
# Production (3 nodes) → shards: 3, replicas: 1
# Ek shard ka ideal size: 10-50GB
# Overcount mat karo → too many shards = overhead

# Replicas runtime pe change karo:
es.indices.put_settings(index="big_index", body={
    "number_of_replicas": 2   # 1 se 2 kar diya
})
```

---

### Q3: Dynamic mapping ka kya problem hai? Explicit mapping kab zaroori hai?

**Answer:**
```python
# ─── Dynamic mapping ka problem ───
es.index(index="orders", document={
    "order_id": "ORD-001",
    "amount": "1999.99",    # ⚠️ String hai! ES → text type karega
    "zip_code": "110001"    # ⚠️ ES → long type karega
})

# Ab range query fail hogi:
es.search(index="orders", body={
    "query": {"range": {"amount": {"gte": 1000}}}
})
# Error! amount text hai, range query numeric pe kaam karti hai

# ─── Explicit mapping solution ───
es.indices.create(index="orders_v2", body={
    "mappings": {
        "dynamic": "strict",
        "properties": {
            "order_id": {"type": "keyword"},
            "amount":   {"type": "float"},    # Explicitly float
            "zip_code": {"type": "keyword"},  # Zip code → keyword (exact match)
        }
    }
})

# Production rules:
# 1. Hamesha explicit mapping use karo
# 2. dynamic: "strict" taaki unexpected fields na aayein
# 3. Text fields pe keyword sub-field rakhho (sort/agg ke liye)
# 4. date format explicitly define karo
```

---

### Q4: text aur keyword type mein kya fark hai? Kab kaunsa?

**Answer:**
```
text field:
  Input: "Apple MacBook Pro"
  After analysis: ["apple", "macbook", "pro"]
  
  ✅ match query: "macbook" milega → document return hoga
  ✅ Typo handling (fuzzy)
  ❌ exact match: "Apple MacBook Pro" exact term query se nahi milega
  ❌ Sorting / Aggregations: work nahi karta (too many tokens)

keyword field:
  Input: "Apple MacBook Pro"
  Stored as-is: "Apple MacBook Pro"
  
  ✅ exact term query: "Apple MacBook Pro" → milega
  ✅ Sorting (alphabetical), Aggregations (group by brand)
  ❌ partial text search: "macbook" → nahi milega

Real use cases:
  title       → text    (search karo "best laptop")
  brand       → keyword (filter karo brand="Apple")
  email       → keyword (exact match)
  description → text    (full-text search)
  status      → keyword (filter: status="active")
  
  Pro tip — dono chahiye? Multi-field use karo:
  "brand": {
      "type": "text",          # brand pe text search bhi ho sake
      "fields": {
          "raw": {"type": "keyword"}  # brand.raw pe exact/sort/agg
      }
  }
```

---

### Q5: helpers.bulk() directly es.bulk() se better kyun hai?

**Answer:**
```python
from elasticsearch.helpers import bulk

# es.bulk() — low level:
# - Manually body construct karo
# - Error handling manually
# - Memory: sab ek baar bhejo

# helpers.bulk() — high level:
# - Generator support → memory efficient ✅
# - Auto retry on failure ✅
# - Automatic chunking ✅
# - Error collection ✅

# Generator example — 1M documents, low memory:
def gen_docs():
    for i in range(1_000_000):
        yield {
            "_index": "logs",
            "_source": {
                "event": f"Event {i}",
                "ts": i
            }
        }

# Sirf chunk_size (500) documents ek baar memory mein
success, errors = bulk(
    es,
    gen_docs(),
    chunk_size=500,          # 500 per batch
    raise_on_error=False,    # errors collect karo, raise mat
    max_retries=3,           # failure pe retry
    request_timeout=60
)
print(f"Indexed: {success}, Errors: {len(errors)}")

# Performance comparison (10K documents):
# es.bulk() manually: ~3 seconds
# helpers.bulk():     ~1.5 seconds (optimized chunking)
# parallel_bulk():    ~0.5 seconds (multi-thread)
```

---

### Q6: index: false kab use karo? _source mein hoga lekin search nahi?

**Answer:**
```python
# index: false = field store karo _source mein, par inverted index mein nahi
# Matlab: retrieve kar sakte ho, search nahi kar sakte

# Use cases:
# 1. Large text jo search nahi karna (raw HTML, binary-like data)
# 2. Internal metadata (app use karta hai, search nahi)
# 3. Disk/memory save karna

es.indices.create(index="articles", body={
    "mappings": {
        "properties": {
            "title":       {"type": "text"},      # Searchable ✅
            "summary":     {"type": "text"},      # Searchable ✅
            "raw_html":    {
                "type": "text",
                "index": False    # Store only, not searchable
            },
            "internal_id": {
                "type": "keyword",
                "index": False    # App ke liye retrieve, search nahi
            }
        }
    }
})

# raw_html pe query fail hogi:
try:
    es.search(index="articles", body={
        "query": {"match": {"raw_html": "some text"}}
    })
except Exception as e:
    print(e)   # Cannot search on field [raw_html] since it is not indexed

# Lekin get karo toh milega:
resp = es.get(index="articles", id="a1")
print(resp['_source']['raw_html'])   # Full HTML content ✅

# ─── store: true (alag concept) ───
# By default: _source mein sab hota hai
# store: true → field ko alag se bhi store karo (rarely needed)
```

---

### Q7: Elasticsearch mein data kaise store hota hai internally? Inverted index kya hai?

**Answer:**
```
Normal Index (Book):
  Page 1 → "apple banana cherry"
  Page 2 → "banana date elderberry"
  Page 3 → "apple cherry fig"

Search "cherry" → Sab pages scan karo → O(N) ❌

Inverted Index (ES ka secret):
  "apple"       → [Page 1, Page 3]
  "banana"      → [Page 1, Page 2]
  "cherry"      → [Page 1, Page 3]   ← directly page numbers!
  "date"        → [Page 2]
  "elderberry"  → [Page 2]

Search "cherry" → inverted index lookup → [Page 1, Page 3] → O(1) ✅

Elasticsearch mein:
  Document 1: {"title": "Gaming Laptop Dell"}
  Document 2: {"title": "Apple MacBook Laptop"}
  Document 3: {"title": "Dell Desktop Computer"}

  Inverted index (title field):
    "gaming"   → [doc1]
    "laptop"   → [doc1, doc2]
    "dell"     → [doc1, doc3]
    "apple"    → [doc2]
    "macbook"  → [doc2]
    "desktop"  → [doc3]
    "computer" → [doc3]

  Search "laptop" → [doc1, doc2] → both results instantly!
  
  Plus frequency information → relevance scoring (TF-IDF/BM25)
```

---

## Summary Table

```
┌──────────────────────────┬────────────────────────────────┬──────────────────────────┐
│ Operation                │ Python Code                    │ Notes                    │
├──────────────────────────┼────────────────────────────────┼──────────────────────────┤
│ Index create             │ es.indices.create(...)         │ Mapping pehle define karo│
│ Index exists             │ es.indices.exists(index=)      │ True/False               │
│ Index delete             │ es.indices.delete(index=)      │ Sab data gone!           │
│ Index mapping get        │ es.indices.get_mapping(...)    │ Schema dekho             │
│ Index refresh            │ es.indices.refresh(index=)     │ Data turant searchable   │
├──────────────────────────┼────────────────────────────────┼──────────────────────────┤
│ Document index (create)  │ es.index(index=, id=, doc=)    │ id nahi → auto generate  │
│ Document get             │ es.get(index=, id=)            │ _source mein data        │
│ Document exists          │ es.exists(index=, id=)         │ True/False               │
│ Document update          │ es.update(index=, id=, doc=)   │ Partial update           │
│ Document delete          │ es.delete(index=, id=)         │ Ek document              │
│ Delete by query          │ es.delete_by_query(...)        │ Multiple documents       │
│ Count                    │ es.count(index=)               │ Document count           │
├──────────────────────────┼────────────────────────────────┼──────────────────────────┤
│ Bulk index               │ helpers.bulk(es, actions)      │ Memory efficient         │
│ Parallel bulk            │ parallel_bulk(es, actions)     │ Fastest option           │
├──────────────────────────┼────────────────────────────────┼──────────────────────────┤
│ text type                │ Full-text search               │ Analyzed/tokenized       │
│ keyword type             │ Exact match, sort, agg         │ Not analyzed             │
│ nested type              │ Array of objects               │ Independent queries      │
│ geo_point type           │ lat/lon coordinates            │ "Near me" queries        │
│ index: false             │ Store only, not searchable     │ Disk space save          │
└──────────────────────────┴────────────────────────────────┴──────────────────────────┘

Docker Command:
  docker run -d --name es -p 9200:9200 \
    -e "discovery.type=single-node" \
    -e "xpack.security.enabled=false" \
    elasticsearch:8.11.0

Python setup:
  pip install elasticsearch
  es = Elasticsearch("http://localhost:9200")
```
