# NoSQL Types — Document, Key-Value, Column-Family, Graph

## Quick Reference Card
```
Key-Value    → Redis, DynamoDB — simple get/set by key, fastest, cache/session
Document     → MongoDB, CouchDB — JSON documents, flexible schema
Column-Family→ Cassandra, HBase — wide rows, time-series, analytics
Graph        → Neo4j, Neptune — relationships as first-class, social networks
Common factor→ No fixed schema, horizontal scale, eventual consistency (usually)
Interview hook → "Redis = key-value for cache/sessions | Typesense = document for search"
```

---

## PART 1: HINGLISH — Samjhne ke liye

### 1.1 NoSQL Kya Hai?

**Analogy: 4 alag tarah ke dukaan**

- **Key-Value** = Locker room — har locker ka number (key) hai, andar kuch bhi rakh do (value). Sirf number se access.
- **Document** = Filing cabinet — folders mein documents hain, har document ka apna structure. "Marketing folder" mein mix of presentations, notes, images.
- **Column-Family** = Spreadsheet jisme har row ka apna set of columns hai — ek row mein 2 columns, doosri row mein 50 columns.
- **Graph** = Social network map — nodes (log) aur unke beech connections (friendships, follows).

```
Why NoSQL?
  RDBMS: Fixed schema (ALTER TABLE = migration = risk)
         Joins = complex, slow at scale
         Vertical scaling preference
         
  NoSQL: Flexible schema (add new field anytime)
         No joins needed (denormalized)
         Horizontal scaling built-in
         Eventual consistency (trade-off)
         
  When NoSQL WINS:
  - Unstructured/semi-structured data
  - Massive horizontal scale needed
  - Schema evolves rapidly
  - Simple access patterns (no complex joins)
  - Specific data models (graphs, time-series)
  
  When RDBMS still WINS:
  - Complex relationships with JOINs
  - ACID transactions (payment, bookings)
  - Reporting and analytics (SQL flexibility)
  - Data integrity (foreign keys, constraints)
```

---

### 1.2 Key-Value Stores

```
MODEL: Simple dictionary/hashmap
  key: string
  value: anything (string, JSON, binary, list)
  
  Operations: GET(key), SET(key, value), DELETE(key)

STRUCTURE:
  "user:session:abc123" → {"user_id": 5, "expires": "2024-01-01"}
  "sap:token"          → "Bearer eyJhbGc..."
  "rate_limit:user:5"  → 142 (count)
  "package:cache:pk1"  → {"name": "Tour A", "price": 25000}

USE CASES:
  ✓ Session storage (random key → user data)
  ✓ Cache (expensive query result)
  ✓ Rate limiting (counter per key)
  ✓ Token storage (API tokens, OTP)
  ✓ Feature flags
  ✓ Leaderboards (Redis Sorted Sets)
  ✓ Queue (Redis Lists → LPUSH/RPOP)

NOT GOOD FOR:
  ✗ Complex queries (can't query by value, only by key)
  ✗ Relationships (no foreign key concept)
  ✗ Analytics (no aggregations)

EXAMPLES:
  Redis: In-memory, ultra-fast (<1ms), supports Lists, Sets, Sorted Sets, Hashes
  DynamoDB: AWS managed, persistent, massive scale
  Memcached: Pure cache, simpler than Redis
  etcd: Consistent key-value for distributed config

REDIS OPERATIONS:
  # Simple key-value
  redis.set("sap:token", token_value, ex=18000)  # 5hr TTL
  redis.get("sap:token")
  
  # Counter (atomic!)
  redis.incr("rate:user:5")     # Atomic increment
  redis.expire("rate:user:5", 60)
  
  # Hash (nested key-value)
  redis.hset("user:5", "name", "Ashish")
  redis.hset("user:5", "email", "a@b.com")
  redis.hgetall("user:5")  # Returns full dict
  
  # Sorted Set (leaderboard)
  redis.zadd("leaderboard", {"player1": 1000, "player2": 850})
  redis.zrevrange("leaderboard", 0, 9)  # Top 10
```

---

### 1.3 Document Stores

```
MODEL: JSON/BSON documents stored in collections
  No fixed schema — each document can have different fields
  Documents can nest (embedded objects, arrays)

STRUCTURE:
  Collection: "packages"
  
  Document 1:
  {
    "_id": "pkg_001",
    "name": "Kerala Backwaters Tour",
    "price": 25000,
    "destinations": ["Alleppey", "Munnar", "Kochi"],
    "inclusions": {
      "meals": true,
      "transport": "AC Bus",
      "hotels": [
        {"name": "Houseboat", "nights": 2},
        {"name": "Resort", "nights": 3}
      ]
    },
    "available_dates": ["2024-01-15", "2024-01-22"]
  }
  
  Document 2 (different structure — OK!):
  {
    "_id": "pkg_002",
    "name": "Himachal Adventure",
    "type": "adventure",
    "difficulty": "high",
    "gear_required": ["jacket", "boots"],
    "price_per_person": 18000
  }

QUERIES:
  db.packages.find({
    "price": {"$lt": 30000},
    "destinations": {"$in": ["Kerala"]},
    "inclusions.meals": true
  })

USE CASES:
  ✓ Product catalogs (e-commerce, tour packages) — flexible attributes
  ✓ User profiles (different users have different fields)
  ✓ Content management (blogs, articles)
  ✓ Event logs (each event has different payload)
  ✓ Mobile app backend (schema evolves with app versions)
  ✓ Nested/hierarchical data

NOT GOOD FOR:
  ✗ Many-to-many relationships (no real JOIN)
  ✗ Financial transactions (ACID needed)
  ✗ Highly normalized data (redundant data everywhere)

EXAMPLES:
  MongoDB: Most popular, BSON format
  CouchDB: HTTP-based, offline sync
  Elasticsearch: Document store + full-text search
  Typesense: Document store optimized for search (Niroskos uses this!)
  Firestore: Google managed, mobile-first
```

---

### 1.4 Column-Family Stores (Wide Column)

```
MODEL: Table with rows, but each row can have DIFFERENT columns
  Different from RDBMS (all rows have same columns)
  "Wide rows" — a single row can have millions of columns

STRUCTURE:
  Cassandra "sensor_readings" table:
  
  Row key (partition key) → Columns (can vary per row)
  
  "sensor:temp:room1" → {
    "2024-01-01 10:00": 22.5,
    "2024-01-01 10:01": 22.6,
    "2024-01-01 10:02": 22.4,
    ... (millions of readings as columns)
  }
  
  "sensor:humidity:room2" → {
    "2024-01-01 10:00": 65,
    "2024-01-01 10:01": 67,
    ...
  }

REAL-WORLD EXAMPLE (Twitter-like):
  Row key: user_id
  Columns: each tweet_id (timestamp-based)
  
  user:123 → {tweet:1705000001: "Hello!", tweet:1705000050: "World!"}
  
  Get all tweets by user: O(1) row lookup, then scan columns
  No need to query multiple rows!

USE CASES:
  ✓ Time-series data (IoT sensors, metrics, logs)
  ✓ Event tracking (user activity, analytics)
  ✓ High write throughput (Cassandra: millions writes/sec)
  ✓ Data with natural partition key (user_id, device_id)
  ✓ Append-only data (logs, events)
  ✓ Multi-datacenter replication

NOT GOOD FOR:
  ✗ Ad-hoc queries (design for specific access patterns)
  ✗ Joins (not supported)
  ✗ Aggregations across partitions (very slow)
  ✗ Rapidly changing schema

EXAMPLES:
  Apache Cassandra: Masterless, AP system (no SPOF), linear scale
  HBase: Built on HDFS, strong consistency, Hadoop ecosystem
  Google Bigtable: Managed, powers Google Search/Analytics
  ScyllaDB: Cassandra-compatible, C++ (10x faster)

CASSANDRA DATA MODEL:
  CREATE TABLE bookings_by_user (
    user_id uuid,
    booking_date date,
    booking_id uuid,
    destination text,
    status text,
    PRIMARY KEY (user_id, booking_date, booking_id)
    -- user_id = partition key (which node)
    -- booking_date, booking_id = clustering columns (sort order within partition)
  );
  
  -- Query optimized for: "All bookings for user X"
  SELECT * FROM bookings_by_user WHERE user_id = ? ORDER BY booking_date DESC;
  
  -- Can't efficiently: "All bookings to destination Y" (requires full table scan!)
  -- Solution: Create ANOTHER table denormalized by destination
  -- (Cassandra design principle: one table per query pattern)
```

---

### 1.5 Graph Databases

```
MODEL: Nodes (entities) + Edges (relationships)
  Both nodes and edges can have properties
  
  STRUCTURE:
  Node: Person {name: "Ashish", age: 30}
  Node: Company {name: "Youngman"}
  Edge: (Ashish) -[WORKS_AT]-> (Company)
  Edge: (Ashish) -[KNOWS]-> (Priya)
  Edge: (Priya) -[KNOWS]-> (Ravi)

QUERY EXAMPLE (Cypher — Neo4j):
  "Find all companies where Ashish's friends work"
  
  MATCH (me:Person {name: "Ashish"})
        -[:KNOWS]->(friend)
        -[:WORKS_AT]->(company)
  RETURN company.name
  
  In SQL:
  SELECT DISTINCT c.name
  FROM persons p1
  JOIN person_friends pf ON p1.id = pf.person_id
  JOIN persons p2 ON pf.friend_id = p2.id
  JOIN employments e ON p2.id = e.person_id
  JOIN companies c ON e.company_id = c.id
  WHERE p1.name = 'Ashish'
  
  Graph query = intuitive | SQL query = complex joins

USE CASES:
  ✓ Social networks (Facebook, LinkedIn friends/connections)
  ✓ Recommendation engines ("People like you also bought...")
  ✓ Fraud detection (unusual connection patterns)
  ✓ Knowledge graphs (Google Knowledge Graph)
  ✓ Permission systems (RBAC — role hierarchies)
  ✓ Network topology (IT infrastructure maps)

NOT GOOD FOR:
  ✗ Bulk data operations (not optimized for large scans)
  ✗ Simple CRUD without relationships
  ✗ Time-series data
  ✗ Heavy analytics

EXAMPLES:
  Neo4j: Most popular, Cypher query language
  Amazon Neptune: Managed graph DB
  ArangoDB: Multi-model (document + graph)
  TigerGraph: Analytics-focused graph
```

---

### 1.6 NoSQL Comparison

```
                KEY-VALUE    DOCUMENT    COLUMN-FAMILY   GRAPH
                ─────────────────────────────────────────────
Data model      k:v pairs    JSON docs   Wide rows       Nodes+Edges
Schema          None         Flexible    Semi-flexible   None
Query by        Key only     Any field   Partition key   Relationships
Horizontal      ✓✓✓          ✓✓          ✓✓✓             Limited
scale
Joins           No           No          No              Core feature
Write speed     Fastest      Fast        Very fast       Medium
Complex queries No           Limited     Limited         Best for graphs
Use case        Cache,       CMS,        IoT, logs,      Social, fraud,
                sessions     catalog     analytics       recommendations
Examples        Redis        MongoDB     Cassandra       Neo4j
                DynamoDB     Typesense   HBase           Neptune
```

---

### 1.7 Ashish ke projects mein

```
Youngman + Niroskos:
  Key-Value (Redis):
    - Django sessions (24hr TTL)
    - SAP OAuth tokens (5hr TTL)
    - Package listing cache (5min TTL)
    - Rate limiting counters
    - Celery task broker (LPUSH/RPOP as queue)
  
  Document (Typesense):
    - Package search index
    - Each package = document with all searchable fields
    - Faceted search (filter by price, destination, duration)
    - Full-text search across package descriptions
    
    # Typesense schema
    schema = {
      'name': 'packages',
      'fields': [
        {'name': 'name', 'type': 'string'},
        {'name': 'price', 'type': 'int32'},
        {'name': 'destination', 'type': 'string', 'facet': True},
        {'name': 'description', 'type': 'string'},
        {'name': 'duration_days', 'type': 'int32', 'facet': True},
      ]
    }
    
    # Search
    results = typesense.collections['packages'].documents.search({
      'q': 'backwater',
      'query_by': 'name,description',
      'filter_by': 'price:<30000 && destination:Kerala',
      'sort_by': 'price:asc'
    })
  
  Graph: Not used (would be useful for destination → attractions → packages linking)
  Column-Family: Not used (no time-series data at our scale)
  
  Primary data store: PostgreSQL (RDBMS) — all transactional data
  NoSQL as specialized supplement, not replacement
```

---

## PART 2: ENGLISH — Interviewer ko bolne ke liye

### 2.1 Definitions

> **Key-Value Store**: Simplest NoSQL type — stores arbitrary values indexed by a unique string key. No schema, no query language beyond GET/SET/DELETE. Extremely fast. Examples: Redis, DynamoDB, Memcached.

> **Document Store**: Stores semi-structured JSON/BSON documents in collections. Schema-free — documents in same collection can have different fields. Supports rich queries on document fields. Examples: MongoDB, Elasticsearch, Firestore.

> **Column-Family Store**: Stores data in rows with dynamic, sparse columns. Optimized for write-heavy workloads and time-series data. Each query pattern typically requires a dedicated table. Examples: Cassandra, HBase, Bigtable.

> **Graph Database**: Models data as nodes (entities) and edges (relationships). Optimized for traversing relationships. Unique for querying connection patterns, recommendations, fraud. Examples: Neo4j, Amazon Neptune.

---

### 2.2 SQL vs NoSQL Decision Framework

| Need | Use SQL | Use NoSQL |
|------|---------|-----------|
| Complex JOINs | Yes | No |
| ACID transactions | Yes | No (or limited) |
| Schema enforcement | Yes | No |
| Horizontal scale needed | Maybe | Yes |
| Flexible schema | No | Yes |
| Simple key lookup | No | Yes (Key-Value) |
| Full-text search | Limited | Yes (Document) |
| Time-series data | Limited | Yes (Column-Family) |
| Relationship traversal | Difficult | Yes (Graph) |

---

### 2.3 CAP in NoSQL Context

```
Key-Value (Redis): CA (single node) → CP (cluster mode)
Document (MongoDB): CP (with write concern = majority)
                    AP (with write concern = 1)
Column-Family (Cassandra): AP by default
                            Tunable: QUORUM = CP-like
                            ONE = AP
Graph (Neo4j): CP (single node or HA with RAFT)

NoSQL systems typically let you tune consistency per operation:
  Cassandra ConsistencyLevel.ONE → AP
  Cassandra ConsistencyLevel.QUORUM → CP-like
  
  Choose based on business requirements!
```

---

### 2.4 Real Project Answer

> "In our stack, we use NoSQL as specialized supplements to PostgreSQL, not as replacements. Redis (key-value) handles sessions, caching, and rate limiting — anything that needs sub-millisecond access. Typesense (document store) powers package search — it's optimized for full-text search with faceting, something PostgreSQL's full-text search doesn't handle as elegantly. All transactional data — bookings, payments, invoices — stays in PostgreSQL because we need ACID guarantees and complex JOINs. The key principle is polyglot persistence: use the right tool for each access pattern rather than forcing all data into one database."

---

### 2.5 Common Follow-up Q&A

**Q1: When would you choose MongoDB over PostgreSQL?**
> "When your data is genuinely document-oriented and schema evolves rapidly — like a product catalog with different attribute sets per product category, or a CMS where articles have varying metadata. MongoDB's strength is when you're frequently adding new fields to documents and you don't want ALTER TABLE migrations. However, for relationships (booking → user → payment), PostgreSQL's JOINs are more natural. MongoDB 4.0+ added multi-document ACID transactions, but they're slower than PostgreSQL's native transactions. My rule: if I need strong consistency, JOINs, or transactions — PostgreSQL. If I need schema flexibility and horizontal scale for document data — MongoDB."

**Q2: What makes Cassandra different from a standard relational DB?**
> "Three key differences: (1) Masterless — no single primary; any node accepts writes. This gives true high availability with no single point of failure. (2) Denormalized data model — you design tables for specific query patterns, not for normalization. Often same data exists in multiple tables. (3) Tunable consistency — you choose per-query whether to prioritize consistency (QUORUM) or availability (ONE). The mental model shift: design your data around what queries you'll run, not around normalized entities. This is why Cassandra requires up-front access pattern analysis before schema design."

**Q3: Can you use multiple database types in one application?**
> "Yes — this is called polyglot persistence, and it's standard at scale. Each database type excels at different access patterns. In practice: PostgreSQL for transactional data, Redis for caching/sessions, Elasticsearch/Typesense for search, Cassandra for time-series/logs. The key is keeping the database boundaries clean — each service or domain owns its data store. The challenge is distributed transactions across databases — generally avoided by designing service boundaries to minimize cross-database operations."

---

## Interview Cheat Sheet

```
4 NoSQL Types:

KEY-VALUE (Redis, DynamoDB):
  Model: key → any value
  Query: By key only
  Use: Cache, sessions, rate limiting, queues
  Speed: Fastest (<1ms Redis)

DOCUMENT (MongoDB, Typesense, Elasticsearch):
  Model: JSON documents in collections
  Query: By any field
  Use: CMS, product catalog, search, user profiles
  Strength: Schema flexibility, rich queries

COLUMN-FAMILY (Cassandra, HBase):
  Model: Rows with dynamic columns (sparse)
  Query: By partition key (row key)
  Use: IoT, logs, analytics, write-heavy
  Strength: Massive write throughput, linear scale

GRAPH (Neo4j, Amazon Neptune):
  Model: Nodes + Edges with properties
  Query: Relationship traversal (Cypher)
  Use: Social networks, recommendations, fraud
  Strength: Relationship queries impossible to do efficiently in SQL

SQL vs NoSQL:
  SQL → JOINs, ACID, schema enforcement, reporting
  NoSQL → Horizontal scale, flexible schema, specialized access

My stack:
  PostgreSQL: All transactional data (bookings, payments, invoices)
  Redis: Cache, sessions, rate limiting, Celery broker
  Typesense: Package search index (document model)
  
  Rule: Right tool for access pattern, not one DB for everything
```
