# Redis — Basics, Installation, CLI Commands & Key Naming
**Basic Level | What, Why, How**

---

## Quick Concepts
- **Redis** = **Re**mote **Di**ctionary **S**erver — in-memory key-value store
- **In-memory** = RAM mein data — microsecond response time
- **Single-threaded** = ek thread sab kuch handle karta hai — race conditions nahi
- **Persistent** = RDB snapshot ya AOF log se disk pe save
- **Data Structures** = Sirf strings nahi — Hash, List, Set, SortedSet, Stream bhi
- **TTL** = Time To Live — key automatic expire hoti hai

---

## What is Redis? Why use it?

```
Without Redis:
  Request → Python → PostgreSQL (disk) → Response
  Time: 50-200ms per query ❌ slow

With Redis:
  Request → Python → Redis (RAM) → Response      [cache hit]
  Time: 0.1-1ms ✅ 100-1000x faster

  Cache miss: Redis → PostgreSQL → store in Redis → Response

Redis ke 6 main use cases:
  1. Cache          → DB queries cache karo
  2. Session Store  → User sessions Redis mein
  3. Rate Limiting  → API calls count karo
  4. Pub/Sub        → Real-time messaging
  5. Queue          → Task queue (Lists + BLPOP)
  6. Leaderboard    → Sorted Sets
```

---

## Interview Questions & Answers

---

### Q1: Redis kaise install karo? Docker se kaise run karo?

**Answer:**
```bash
# ─── Docker (recommended — no install needed) ───
docker run -d \
  --name redis \
  -p 6379:6379 \
  redis:7-alpine

# Persistence ke saath (data save karo)
docker run -d \
  --name redis \
  -p 6379:6379 \
  -v redis_data:/data \
  redis:7-alpine redis-server --appendonly yes

# Docker Compose (production setup)
# docker-compose.yml:
# services:
#   redis:
#     image: redis:7-alpine
#     ports: ["6379:6379"]
#     volumes: ["redis_data:/data"]
#     command: redis-server --appendonly yes --requirepass yourpassword
#     healthcheck:
#       test: ["CMD", "redis-cli", "ping"]

# ─── Mac (Homebrew) ───
brew install redis
brew services start redis

# ─── Ubuntu/Debian ───
sudo apt install redis-server
sudo systemctl start redis

# ─── Python client install ───
pip install redis[hiredis]    # hiredis = C extension — faster parsing
pip install redis              # without hiredis
```

---

### Q2: Redis CLI — sabse important commands kya hain?

**Answer:**
```bash
# ─── Connect ───
redis-cli                          # localhost:6379
redis-cli -h myhost -p 6380        # custom host/port
redis-cli -a password              # with password
redis-cli -n 1                     # database 1 select (0-15)

# ─── Basic CRUD ───
SET name "Alice"                   # set key
GET name                           # get key → "Alice"
DEL name                           # delete key → 1 (deleted count)
EXISTS name                        # 1 = exists, 0 = nahi
TYPE name                          # string / hash / list / set / zset / stream

# ─── TTL Commands ───
EXPIRE key 3600                    # 3600 seconds baad expire
EXPIREAT key 1735689600            # Unix timestamp pe expire
TTL key                            # seconds remaining (-1 = no TTL, -2 = gone)
PTTL key                           # milliseconds remaining
PERSIST key                        # TTL remove karo (permanent banao)

# ─── Key Management ───
KEYS "user:*"                      # pattern match (❌ production pe KABHI nahi — blocks!)
SCAN 0 MATCH "user:*" COUNT 100    # ✅ non-blocking iteration
RENAME oldkey newkey               # rename
RANDOMKEY                          # random key return
DBSIZE                             # total keys count
FLUSHDB                            # current DB saaf karo (❌ production KABHI nahi)
FLUSHALL                           # sab DBs saaf karo (❌ NEVER)

# ─── Server Info ───
INFO                               # server stats sab
INFO memory                        # memory usage
INFO replication                   # master/replica status
INFO keyspace                      # databases aur key counts
MONITOR                            # real-time command stream (debug only)
SLOWLOG GET 10                     # last 10 slow commands
MEMORY USAGE key                   # specific key memory bytes
DEBUG OBJECT key                   # encoding, serialized length
CONFIG GET maxmemory               # config value dekho
CONFIG SET maxmemory 2gb           # config runtime change

# ─── Useful Patterns ───
OBJECT ENCODING key                # how Redis stores internally
# string → int / embstr / raw
# list   → listpack / quicklist
# hash   → listpack / hashtable
# set    → listpack / hashtable / intset
# zset   → listpack / skiplist

# ─── Multiple Operations ───
MSET key1 val1 key2 val2           # set multiple
MGET key1 key2 key3                # get multiple
```

---

### Q3: Key Naming Convention kya hoti hai? Best practices?

**Answer:**
```bash
# ─── Pattern: object:id:field ───
user:1001:profile          # user ID 1001 ka profile
user:1001:sessions         # user ke sessions
order:uuid:status          # order UUID ka status
product:42:inventory       # product 42 ki inventory
rate_limit:user:1001:api   # user 1001 ke API calls

# ─── Real examples ───
# Cache
cache:product:42           # product 42 cached data
cache:search:laptops:page1 # search results cache

# Sessions
session:abc123def456       # session token
session:user:1001          # user session

# Locks
lock:order:processing:101  # order 101 lock
lock:job:email:weekly      # weekly email job lock

# Queues
queue:emails:welcome       # welcome email queue
queue:notifications:push   # push notifications

# Counters
counter:page_views:2024-01-15   # daily page views
counter:api_calls:user:1001     # user API call count
counter:login_attempts:user:1001

# Real-time
online:users               # currently online users set
leaderboard:game:chess     # chess leaderboard
trending:products:1h       # last 1 hour trending

# Rules:
# ✅ lowercase use karo
# ✅ colon (:) as separator
# ✅ meaningful hierarchy
# ❌ spaces mat use karo
# ❌ too long keys avoid karo (memory waste)
# ❌ generic names (key1, temp) avoid karo
```

---

### Q4: Redis databases kya hain? Kab use karo?

**Answer:**
```bash
# Redis mein 16 databases hain (0-15) by default
# Default: database 0

# Switch database
SELECT 1    # database 1 use karo

# Python mein
import redis
r0 = redis.Redis(db=0)   # production data
r1 = redis.Redis(db=1)   # test/staging data
r2 = redis.Redis(db=2)   # cache only

# ⚠️ Important: 
# Redis Cluster mein multiple DBs NAHI hote — sirf DB 0
# Production Redis Cluster use karte ho → separate Redis instances use karo
# Isliye best practice: ALWAYS db=0, keys se segregate karo
```

---

### Q5: Redis mein data types ka internal encoding kya hai?

**Answer:**
```bash
# Redis internally different encodings use karta hai based on size

# String
SET small "Hi"
OBJECT ENCODING small    # → "embstr" (≤44 chars)
SET num 12345
OBJECT ENCODING num      # → "int"
SET large "very long string more than 44 chars..."
OBJECT ENCODING large    # → "raw"

# Hash
HSET small_hash f1 v1 f2 v2   # 2 fields only
OBJECT ENCODING small_hash    # → "listpack" (≤128 fields, values ≤64 bytes)
# Many fields → "hashtable" (O(1) access)

# List
RPUSH small_list a b c         # 3 elements
OBJECT ENCODING small_list    # → "listpack" (≤128 items, ≤64 bytes each)
# Big list → "quicklist" (linked list of listpacks)

# Set
SADD int_set 1 2 3 4 5
OBJECT ENCODING int_set       # → "intset" (only integers, ≤512)
# Strings → "listpack" or "hashtable"

# Sorted Set  
ZADD small_zset 1.0 "a" 2.0 "b"
OBJECT ENCODING small_zset    # → "listpack" (≤128 members)
# Big zset → "skiplist"

# Why matters?
# listpack = memory efficient (compact, no pointers)
# hashtable/skiplist = faster O(1)/O(log n) access
# Redis auto-converts when threshold exceeded
```

---

### Q6: Redis mein CONFIG kaise manage karo?

**Answer:**
```bash
# ─── Important config parameters ───
CONFIG GET maxmemory                    # max memory limit
CONFIG SET maxmemory 2gb               # 2GB limit set

CONFIG GET maxmemory-policy             # eviction policy
CONFIG SET maxmemory-policy allkeys-lru # LRU eviction

# ─── Eviction policies ───
# noeviction      → error return (default) — bad for cache
# allkeys-lru     → LRU all keys — BEST for pure cache
# volatile-lru    → LRU only TTL-set keys
# allkeys-lfu     → LFU all keys (Redis 4+)
# volatile-ttl    → closest to expire first
# allkeys-random  → random eviction
# volatile-random → random TTL keys

CONFIG GET save                         # RDB save intervals
CONFIG SET save "3600 1 300 100 60 10000"

CONFIG GET bind                         # network binding
CONFIG GET requirepass                  # password
CONFIG SET requirepass "strongpassword"

CONFIG REWRITE                          # config changes file mein save karo
CONFIG RESETSTAT                        # statistics reset

# ─── redis.conf important settings ───
# maxmemory 2gb
# maxmemory-policy allkeys-lru
# bind 127.0.0.1
# requirepass yourpassword
# appendonly yes
# appendfsync everysec
```

---

### Q7: KEYS vs SCAN — kya fark hai? Production mein kaunsa?

**Answer:**
```bash
# KEYS — NEVER use in production!
KEYS "user:*"
# Problem: O(N) — sab keys scan karta hai
# 10M keys → 10 second block → server freeze ❌
# Single-threaded Redis → sabka request ruk jaata hai

# SCAN — Production safe ✅
SCAN 0 MATCH "user:*" COUNT 100
# Returns: [next_cursor, [key1, key2, ...]]
# Non-blocking — cursor based iteration
# COUNT = hint (not exact) — approximately kitne return kare
# cursor=0 → first call, returns cursor → call again until cursor=0

# Python mein SCAN use karo
import redis
r = redis.Redis()

# Method 1: scan_iter (recommended — auto handles cursor)
for key in r.scan_iter("user:*", count=100):
    print(key)

# Method 2: Manual SCAN with cursor
cursor = 0
while True:
    cursor, keys = r.scan(cursor=cursor, match="user:*", count=100)
    for key in keys:
        print(key)
    if cursor == 0:   # done
        break
```

---

## Redis CLI Quick Reference Card

```
┌─────────────────────────────────────────────────────────────────┐
│ Command           │ Description                │ Complexity     │
├─────────────────────────────────────────────────────────────────┤
│ SET key val       │ String set                 │ O(1)           │
│ GET key           │ String get                 │ O(1)           │
│ DEL key [key...]  │ Delete keys                │ O(N)           │
│ EXISTS key        │ Key exists check           │ O(1)           │
│ EXPIRE key sec    │ Set TTL seconds            │ O(1)           │
│ TTL key           │ Remaining TTL              │ O(1)           │
│ TYPE key          │ Data type                  │ O(1)           │
│ KEYS pattern      │ Pattern match (⚠️ prod)    │ O(N) BLOCKING  │
│ SCAN cursor       │ Safe iteration             │ O(1) per call  │
│ DBSIZE            │ Total key count            │ O(1)           │
│ INFO section      │ Server info                │ O(1)           │
│ MONITOR           │ Real-time commands         │ Debug only     │
│ SLOWLOG GET N     │ Slow query log             │ O(N)           │
│ SELECT db         │ Switch database            │ O(1)           │
│ PING              │ Connection test            │ O(1)           │
│ QUIT              │ Close connection           │ -              │
└─────────────────────────────────────────────────────────────────┘
```
