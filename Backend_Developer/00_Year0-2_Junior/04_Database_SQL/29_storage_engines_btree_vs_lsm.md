# Database — Storage Engines: B-tree vs LSM-tree
**Database · Year 0-2 | Senior Backend + Agentic AI**

## Quick Concepts

- **Storage engine** = the layer that decides HOW rows/keys hit disk — indexing, on-disk layout, write path
- **B-tree / B+tree** = balanced tree, **in-place updates**, read-optimized — PostgreSQL, MySQL InnoDB, SQLite, LMDB, BoltDB
- **LSM-tree** = Log-Structured Merge tree, **append-only + background merge**, write-optimized — Cassandra, ScyllaDB, RocksDB, LevelDB, HBase
- **Page** = fixed-size disk block (Postgres 8KB, InnoDB 16KB) — the unit B-trees read/write
- **memtable** = in-memory sorted buffer (skiplist/RB-tree) where LSM writes land first
- **SSTable** = Sorted String Table — immutable on-disk file an LSM flushes the memtable into
- **Compaction** = background job that merges SSTables, drops obsolete versions + tombstones
- **WAL** = Write-Ahead Log — both engines write it first for durability (see [07_postgresql_internals.md](07_postgresql_internals.md))
- **Write/Read/Space amplification** = the three taxes; RUM conjecture says you optimize 2 of 3
- **Bloom filter** = probabilistic "is this key definitely NOT here?" — saves LSM from useless disk reads

---

## Why This Topic Matters

```
Same question on every system-design interview:
─────────────────────────────────────────────────
"Why is Postgres slower than Cassandra on writes?"
"Why does Cassandra need 'compaction' but Postgres doesn't?"
"You're building an IoT ingest pipeline — which DB?"

The answer is almost NEVER the query language or the API.
It's the STORAGE ENGINE underneath:

   PostgreSQL / MySQL InnoDB  → B-tree     → read-optimized
   Cassandra / RocksDB / HBase → LSM-tree   → write-optimized
   ClickHouse MergeTree        → LSM-like   → write + scan optimized

Pick the wrong one and you fight the engine forever.
```

Yeh ek foundational topic hai. Index ka data structure (B-tree vs LSM) decide karta hai ki database write-heavy load pe survive karega ya read-heavy pe. Galat choice = production me compaction storms ya write amplification se disk jal jaata hai.

---

## Part 1 — B-tree / B+tree

### WHAT — the structure

A **B+tree** is a balanced, multi-way search tree. Every leaf is at the **same depth**, so every lookup costs the same `O(log_b n)` page reads (`b` = branching factor, typically hundreds).

```
                    ┌─────────────────────────┐
   Root (internal)  │   [ 30 | 60 | 90 ]      │   keys = routing only
                    └────┬─────┬─────┬─────┬───┘
            ┌────────────┘     │     │     └────────────┐
            ▼                  ▼     ▼                  ▼
   ┌──────────────┐   ┌──────────────┐         ┌──────────────┐
   │ [10|20]      │   │ [40|50]      │   ...   │ [90|95|99]   │  internal
   └──┬────┬──────┘   └──────────────┘         └──────────────┘
      ▼    ▼
   ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐
   │ 10→row │→ │ 20→row │→ │ 30→row │→ │ 40→row │→ ...   LEAF nodes
   └────────┘  └────────┘  └────────┘  └────────┘
        (leaves hold data/row-pointers + are linked → fast range scans)

   B-tree:  data can live in ANY node (internal or leaf)
   B+tree:  data/pointers ONLY in leaves; internals are pure routing
            leaves form a linked list → range scan = walk the chain
   Real RDBMS (Postgres, InnoDB) use the B+tree variant.
```

- **Internal nodes** store only keys + child pointers → they act as a routing table.
- **Leaf nodes** store the actual data (or a pointer/tuple-id to the heap row) and are **linked left-to-right** → range scans (`WHERE x BETWEEN a AND b`, `ORDER BY`) just walk the leaf chain. This is the killer feature for OLTP.
- **High fan-out**: with 8KB pages and ~16-byte entries, one internal page routes to ~500 children. So a tree only **3-4 levels deep indexes billions of rows** → a point lookup is 3-4 page reads (and the top levels stay cached in RAM).

### HOW — the write path (in-place update)

```
INSERT / UPDATE into a B-tree:
─────────────────────────────────
1. Walk root → leaf to find the target PAGE         (O(log n) reads)
2. Write the change to the WAL first                (durability)
3. Modify the page IN PLACE in the buffer pool      (mutate existing bytes)
4. Mark page dirty → flushed later at checkpoint     (random write to disk)

If the target leaf is FULL → PAGE SPLIT:
   - allocate a new page
   - move ~half the entries over
   - insert a separator key into the parent
   - parent full too? split propagates UP (can reach the root → tree grows a level)
```

Key consequences:

- **In-place update** = the row's bytes are overwritten where they already live (logically). Great for reads (data is where the index says), but each write is a **random page write** scattered across the disk.
- **Write amplification**: to durably change one row you write (a) the WAL record AND (b) the whole 8KB page later — even if you touched 20 bytes. Page splits write multiple pages.
- **fill factor** = how full a page is packed on creation (Postgres default 90%). Leave slack (e.g. `fillfactor = 70`) so future inserts/HOT-updates fit **without splitting** the page → less fragmentation. Pack to 100% (`fillfactor=100`) only for append-only/read-only tables.
- **Fragmentation / bloat**: over time, splits + Postgres MVCC dead tuples leave pages half-empty → wasted space (a form of **space amplification**). Fixed by `VACUUM` / `REINDEX` (see [07_postgresql_internals.md](07_postgresql_internals.md)).

```sql
-- Postgres: leave room in pages for a high-churn indexed table
ALTER TABLE orders SET (fillfactor = 80);
CREATE INDEX idx_orders_user ON orders (user_id) WITH (fillfactor = 90);
-- B-tree is the DEFAULT index in Postgres/MySQL — you use it every day:
CREATE INDEX idx_users_email ON users (email);   -- → B+tree under the hood
```

### WHO uses B-trees

```
PostgreSQL          → heap tables + B-tree indexes (default)
MySQL InnoDB        → CLUSTERED B+tree (table IS the primary-key B+tree;
                      leaf node literally holds the full row)
SQLite              → B-tree pages
Oracle / SQL Server → B-tree indexes
LMDB                → memory-mapped B+tree (copy-on-write pages)
BoltDB / etcd's bbolt → pure B+tree key-value store (single-writer, mmap)
```

> Note: InnoDB's *clustered* index means the row data lives **inside** the PK B+tree leaf, while a Postgres B-tree index leaf holds a *pointer* (tuple id) into a separate heap file. Both are B+trees; the difference is where the row body sits.

---

## Part 2 — LSM-tree (Log-Structured Merge)

### WHAT + WHY — flip the write path

A B-tree mutates pages in place → **random I/O**. An LSM-tree's bet: **never update in place**. Buffer writes in RAM, dump them to disk as **sorted immutable files** via large **sequential writes**, and fix up the mess later with background merges. Sequential writes are 100-1000x faster than random ones on both HDD and SSD → LSM wins write throughput.

### HOW — the full write path

```
WRITE PATH (e.g. Cassandra / RocksDB):
──────────────────────────────────────────────────────────────────
   write(key, val)
        │
        ├──► 1. append to WAL (commit log) on disk   ── durability, sequential
        │
        └──► 2. insert into MEMTABLE (in RAM)         ── sorted: skiplist / RB-tree
                                                          UPDATE = just another insert
                                                          DELETE = insert a TOMBSTONE
        when memtable hits size limit (e.g. 64MB):
                │
                ▼  (memtable becomes immutable, a new one takes writes)
        3. FLUSH → write a new SSTable to disk        ── ONE big sequential write
                                                          already sorted → no seeking
```

```
ON-DISK SSTable (Sorted String Table) — immutable:
┌──────────────────────────────────────────────────────────────┐
│  Data blocks (KEY-SORTED key/value pairs, block-compressed)  │
│  ┌──────────┬──────────┬──────────┬──────────┐               │
│  │ a01..a99 │ b01..b80 │ c10..c90 │   ...     │               │
│  └──────────┴──────────┴──────────┴──────────┘               │
│  Sparse index / FENCE POINTERS  → "block 2 starts at key b01"│
│  BLOOM FILTER                   → "key 'k42'? definitely NOT" │
└──────────────────────────────────────────────────────────────┘
   Immutable = never modified after write → safe to read lock-free,
   cache aggressively, and ship to replicas byte-for-byte.
```

### HOW — the read path (this is the expensive side)

```
READ PATH for get(key):
──────────────────────────────────────────────────────────────────
   1. Check the active MEMTABLE (RAM)              → found? return (newest wins)
   2. Check immutable memtables being flushed
   3. Check SSTables NEWEST → OLDEST:
        for each SSTable:
          a. ask its BLOOM FILTER  → "no" ⇒ skip this file entirely (no disk read!)
          b. "maybe" ⇒ binary-search the SPARSE INDEX / fence pointers
                       → seek to the one data block that could hold the key
          c. read + decompress that block, scan for the key
   4. First match wins (newest version); a TOMBSTONE means "deleted, stop"

Without Bloom filters: a get() for a missing key would touch EVERY SSTable.
With Bloom filters:    ~1 disk seek even across dozens of SSTables.
```

That "newest-to-oldest across many files" is exactly the **read amplification** an LSM pays — one logical read can probe several files. Bloom filters + sparse indexes (fence pointers) are what keep it from being catastrophic.

### HOW — compaction (the background janitor)

```
WHY compaction?
   Every flush creates a new SSTable. Without merging:
     - the same key has 5 versions across 5 files  → reads get slower
     - deleted keys linger as tombstones            → space wasted
     - more files → more Bloom/index probes per read

Compaction = read N SSTables, MERGE-SORT them, write fewer/bigger ones,
             keep only the NEWEST value per key, drop tombstoned keys.

   SSTable A: [a:1, c:9, e:7]                merge-sort, newest-wins
   SSTable B: [a:5, b:2, c:DEL]   ───────►   [a:5, b:2, e:7]
   (B is newer)                              (c deleted, a updated to 5)
```

Compaction is what trades **write amplification** (rewriting data you already wrote) for lower read + space amplification. Tune it wrong and you get a **compaction storm**: background merges saturate disk I/O and stall foreground writes.

### WHO uses LSM-trees

```
Cassandra / ScyllaDB → LSM per node (Scylla = C++ rewrite, shard-per-core)
RocksDB / LevelDB    → embeddable LSM KV (RocksDB powers Kafka Streams state,
                       CockroachDB, TiKV, MyRocks, Flink, ...)
HBase                → LSM on HDFS
ClickHouse MergeTree → LSM-LIKE: parts (≈SSTables) merged in background,
                       columnar not key-value (see [27_clickhouse_olap.md](27_clickhouse_olap.md))
```

> ClickHouse caveat: MergeTree is LSM-*inspired* (immutable sorted "parts" + background merges + no in-place update), but it is **columnar** and uses a *sparse primary index*, not a Bloom-filtered key/value store. Same family, different beast — that's why it's "LSM-like", not "an LSM".

---

## Part 3 — The Three Amplifications + RUM Conjecture

Every storage engine pays three "taxes". You cannot zero out all three — improving one usually worsens another.

```
┌─────────────────────┬──────────────────────────────────────────────────┐
│ Amplification       │ Definition + who pays it                          │
├─────────────────────┼──────────────────────────────────────────────────┤
│ WRITE               │ bytes written to disk ÷ bytes the app actually    │
│ amplification       │ wrote.                                            │
│                     │  • B-tree:  page rewrites + WAL + page splits     │
│                     │  • LSM:     compaction rewrites data many times   │
│                     │             (leveled can be 10-30x)               │
├─────────────────────┼──────────────────────────────────────────────────┤
│ READ                │ disk reads (or blocks) per logical lookup.        │
│ amplification       │  • B-tree:  LOW — ~tree height (3-4) page reads   │
│                     │  • LSM:     HIGHER — probe memtable + N SSTables  │
│                     │             (Bloom filters knock it back down)    │
├─────────────────────┼──────────────────────────────────────────────────┤
│ SPACE               │ disk used ÷ live data size.                       │
│ amplification       │  • B-tree:  fragmentation, half-empty pages,      │
│                     │             MVCC dead tuples (bloat)              │
│                     │  • LSM:     obsolete versions + tombstones live   │
│                     │             until compaction reclaims them        │
└─────────────────────┴──────────────────────────────────────────────────┘
```

```
RUM CONJECTURE (Athanassoulis et al., 2016)
─────────────────────────────────────────────
  R = Read overhead
  U = Update overhead
  M = Memory/space overhead

  "You can optimize for at most TWO of Read, Update, Memory —
   the third one suffers."

         Read (R)
            /\
           /  \
          /    \           B-tree      → optimizes R + M  (sacrifices U: random writes)
         /      \          LSM-tree     → optimizes U + M  (sacrifices R: multi-file reads)
        /________\         Hash index   → optimizes R + U  (sacrifices M: keys in RAM)
   Update(U)   Memory(M)

  This is the storage-layer cousin of the CAP theorem
  (pick-2 tradeoff) — see [08_cap_theorem_db_selection.md](08_cap_theorem_db_selection.md).
```

The big inversion to remember:

```
                 │ Write path        │ Read path         │ Disk I/O pattern
─────────────────┼───────────────────┼───────────────────┼──────────────────
  B-tree         │ slower (random)   │ FAST (~3-4 reads) │ random writes
  LSM-tree       │ FAST (sequential) │ slower (N files)  │ sequential writes
```

---

## Part 4 — Compaction Strategies (LSM only)

The compaction strategy is the single biggest LSM tuning knob. It directly sets where you land on the write-vs-space tradeoff.

```
┌───────────────────────┬───────────────────────────────────────────────┐
│ LEVELED compaction    │ SIZE-TIERED compaction (STCS)                  │
│ (RocksDB default,     │ (Cassandra default,                           │
│  Cassandra LCS)       │  HBase-style)                                  │
├───────────────────────┼───────────────────────────────────────────────┤
│ L0: fresh flushes     │ Group SSTables of SIMILAR SIZE.               │
│ L1..Ln: each level    │ When ~4 same-size files exist → merge them    │
│  is ~10x bigger;      │ into one bigger file (next tier up).          │
│  WITHIN a level,      │                                               │
│  key ranges DON'T     │   [s][s][s][s] → [ M ]                        │
│  overlap.             │   [M][M][M][M] → [  L  ]                      │
│                       │                                               │
│ A key lives in ≤1     │ A key may sit in several tiers at once.       │
│ SSTable per level →   │                                               │
│ read hits few files.  │                                               │
├───────────────────────┼───────────────────────────────────────────────┤
│ ↑ WRITE amplification │ ↓ WRITE amplification (merge less often)       │
│   (rewrites a lot)    │                                               │
│ ↓ READ amplification  │ ↑ READ amplification (key in many tiers)      │
│ ↓ SPACE amplification │ ↑ SPACE amplification (during merge needs ~2x;│
│   (~10% overhead)     │   duplicate/obsolete data lingers)            │
├───────────────────────┼───────────────────────────────────────────────┤
│ USE: read-heavy,      │ USE: write-heavy, append-mostly,              │
│ space-constrained,    │ ingest pipelines where reads are rare         │
│ predictable latency   │ and disk is cheap                             │
└───────────────────────┴───────────────────────────────────────────────┘

Hybrids worth naming:
  • Tiered+Leveled / "Universal" (RocksDB)         → middle ground
  • TimeWindowCompactionStrategy (TWCS, Cassandra) → for time-series:
       compact within a time window, then DROP whole window via TTL
       (mirrors ClickHouse PARTITION-drop lifecycle)
```

### Tombstones — how LSMs delete

```
DELETE in an LSM ≠ erase. It WRITES a TOMBSTONE marker:

   delete(k)  →  append (k, <TOMBSTONE>) to memtable → flushes to an SSTable

  • A read sees the tombstone (newest) → returns "not found", even though
    older SSTables still physically hold k's old value.
  • The real bytes are reclaimed only when COMPACTION merges past the
    tombstone AND enough time passed (gc_grace_seconds in Cassandra, so a
    deleted value can't "resurrect" from a replica that missed the delete).

⚠ Tombstone hazards (classic Cassandra prod incident):
   - Deleting many rows in a range, then range-scanning it = the read must
     walk THOUSANDS of tombstones before returning → query timeout.
   - Queue/inbox tables (insert then delete) are an LSM anti-pattern for
     exactly this reason. (Postgres B-tree + autovacuum handles it far better.)
```

---

## Part 5 — Decision Table

```
┌──────────────────────────────────────────┬──────────────┬───────────────┐
│ Workload                                  │ Pick         │ Why           │
├──────────────────────────────────────────┼──────────────┼───────────────┤
│ Time-series / metrics / IoT sensor floods │ LSM          │ append-mostly,│
│                                           │ (TWCS)       │ huge write rate│
│ Event logs / audit / clickstream ingest   │ LSM          │ write-heavy,   │
│                                           │              │ rare random rd │
│ Append-heavy write-mostly KV at scale     │ LSM          │ seq writes win │
│ (Cassandra/Scylla/RocksDB)                │              │                │
│ Message queue persisted in a DB           │ LSM? NO →    │ tombstone hell │
│                                           │ B-tree       │ on delete+scan │
├──────────────────────────────────────────┼──────────────┼───────────────┤
│ OLTP: random point UPDATEs + reads        │ B-tree       │ in-place upd,  │
│ (orders, users, accounts, inventory)      │              │ fast reads     │
│ Range scans / ORDER BY / pagination       │ B-tree       │ linked leaves  │
│ Read-heavy, latency-sensitive             │ B-tree       │ ~3-4 page reads│
│ Strong secondary-index + JOIN needs       │ B-tree (RDBMS)│ mature planner│
├──────────────────────────────────────────┼──────────────┼───────────────┤
│ OLAP: aggregations over billions of rows  │ LSM-like     │ ClickHouse     │
│                                           │ columnar     │ MergeTree      │
└──────────────────────────────────────────┴──────────────┴───────────────┘

One-liner: write-heavy/append → LSM.  read-heavy OLTP w/ updates+scans → B-tree.
```

---

## Part 6 — Benchmark Intuition

> Order-of-magnitude mental model, NOT a guarantee — real numbers depend on hardware (NVMe vs HDD), value size, key distribution, cache, and compaction tuning. Use it to reason, then benchmark your own workload.

```
┌──────────────────────────┬─────────────────────┬─────────────────────┐
│ Dimension                │ B-tree (Postgres)   │ LSM (RocksDB/Cass.) │
├──────────────────────────┼─────────────────────┼─────────────────────┤
│ Random write throughput  │ baseline (1x)       │ ~5-20x higher       │
│ Sequential ingest        │ good                │ excellent           │
│ Point read (hot key)     │ very fast           │ fast (memtable/cache)│
│ Point read (cold, exists)│ ~3-4 page reads     │ Bloom + 1 block read│
│ Point read (MISSING key) │ ~3-4 page reads     │ ~0 disk (Bloom says no)│
│ Range scan / ORDER BY    │ excellent (leaves)  │ OK→good (merge iter)│
│ Write amplification      │ low-moderate        │ high (compaction)   │
│ Read amplification       │ low                 │ moderate            │
│ Space amplification      │ low-moderate (bloat)│ moderate (versions) │
│ Latency predictability   │ steady              │ spiky (compaction)  │
└──────────────────────────┴─────────────────────┴─────────────────────┘
```

---

## Interview Questions & Answers

### Q1: Why is Cassandra faster at writes than PostgreSQL?

**Answer:**

```
Storage engine difference, not the query layer.

PostgreSQL (B-tree):
  - write walks root→leaf, mutates a page IN PLACE
  - the page lands at a RANDOM disk location → random I/O
  - WAL + later page flush = write amplification per row

Cassandra (LSM-tree):
  - write = append to commit log + insert into in-RAM memtable (sorted)
  - returns immediately; no disk seek on the hot path
  - memtable flushes to an SSTable as ONE big SEQUENTIAL write
  - sequential writes are ~orders of magnitude faster than random

Cost of that speed: compaction (write amplification later) and
multi-SSTable reads (read amplification). LSM moves the work
off the write path and onto the background + read path.
```

### Q2: What are the three amplifications, and what's the RUM conjecture?

**Answer:**

```
Write amplification  = bytes written to disk ÷ bytes app wrote
                       (LSM: compaction; B-tree: page rewrites + splits)
Read amplification   = disk reads per logical lookup
                       (LSM: many SSTables; B-tree: ~tree height)
Space amplification  = disk used ÷ live data
                       (LSM: obsolete versions/tombstones; B-tree: bloat)

RUM conjecture: optimize at most 2 of { Read, Update, Memory } — the 3rd suffers.
  • B-tree → Read + Memory  (Update suffers: random writes)
  • LSM    → Update + Memory (Read suffers: multi-file reads)
  • Hash   → Read + Update   (Memory suffers: all keys in RAM)
It's the storage-layer analogue of CAP's pick-2.
```

### Q3: How does an LSM read avoid touching every SSTable?

**Answer:**

```
Two structures per SSTable:

1. BLOOM FILTER — probabilistic set membership.
   "Is key k in this file?" → "definitely NOT" or "maybe".
   A "definitely not" means SKIP the file with ZERO disk reads.
   So a get() for a missing key can avoid all SSTables → ~0 disk seeks.
   (False positives possible → occasional wasted block read; never false negatives.)

2. SPARSE INDEX / FENCE POINTERS — "block N starts at key X".
   On a Bloom "maybe", binary-search the fences → seek the ONE block
   that could contain the key, read + decompress just that block.

Reads still go memtable → SSTables newest-to-oldest (newest value wins,
tombstone = deleted), but Bloom + fences keep it to ~1 seek in practice.
```

### Q4: Leveled vs size-tiered compaction — when each?

**Answer:**

```
Size-tiered (STCS): merge ~4 similarly-sized SSTables into a bigger one.
  ↓ write amplification, ↑ read + ↑ space amplification (needs ~2x disk
  during a big merge, key sits in multiple tiers).
  → write-heavy, append-mostly, disk-is-cheap, reads rare.

Leveled (LCS): levels grow ~10x; within a level key ranges DON'T overlap,
  so a key is in ≤1 SSTable per level.
  ↓ read + ↓ space amplification (~10% overhead), ↑ write amplification.
  → read-heavy, space-constrained, want predictable latency.

Time-series special case: TWCS — compact within a time window then DROP the
whole window via TTL (like ClickHouse partition drop). Avoids tombstone scans.
```

### Q5: Why would you NOT put a job queue / inbox in Cassandra?

**Answer:**

```
Queue pattern = insert a row, process it, DELETE it. Repeat millions of times.

In an LSM, DELETE writes a TOMBSTONE (not an erase). The dead rows + their
tombstones physically remain until compaction (and gc_grace_seconds) clear them.
Range-scanning "give me pending jobs" must then walk past THOUSANDS of
tombstones before returning live rows → latency spikes, read timeouts.
Classic Cassandra production footgun.

Better: Postgres B-tree table + autovacuum (in-place delete, space reused),
or a purpose-built broker (Kafka/SQS). Use SELECT ... FOR UPDATE SKIP LOCKED
for the worker pattern (see [07_postgresql_internals.md](07_postgresql_internals.md)).
```

### Q6: Is ClickHouse's MergeTree a B-tree or an LSM-tree?

**Answer:**

```
Neither exactly — it's LSM-LIKE.

Shares with LSM:
  ✓ immutable on-disk "parts" (≈ SSTables)
  ✓ background MERGES of parts
  ✓ no in-place UPDATE (mutations rewrite parts; UPDATE/DELETE are costly)
  ✓ append/insert-optimized

Differs from a classic LSM:
  ✗ COLUMNAR, not key/value rows
  ✗ uses a SPARSE PRIMARY INDEX (1 mark per 8192 rows), not a Bloom-filtered KV store
  ✗ primary key is the SORT key, not unique

So: same family (immutable + merge), different machine. Hence "LSM-like".
See [27_clickhouse_olap.md](27_clickhouse_olap.md).
```

### Q7: B+tree vs B-tree — what's the actual difference?

**Answer:**

```
B-tree:  data/values can live in ANY node (internal or leaf).
B+tree:  values live ONLY in leaves; internal nodes are pure routing keys,
         and leaves are LINKED in a list.

Why every real RDBMS uses B+tree:
  1. Higher fan-out — internals hold only keys (no row bodies) → more keys
     per page → shallower tree → fewer reads per lookup.
  2. Linked leaves → range scans / ORDER BY / pagination walk the leaf chain
     sequentially instead of re-traversing the tree.
That second point is why B+trees crush LSMs on range scans.
```

### Q8: How do page splits and fillfactor affect a B-tree in production?

**Answer:**

```
Insert into a FULL leaf → PAGE SPLIT: allocate a page, move ~half the entries,
push a separator key to the parent. If the parent is full, the split propagates
up — can reach the root and add a level. Splits = extra random writes + temporary
fragmentation, and they happen under your write lock.

fillfactor controls how full pages are packed at build time (Postgres default 90%):
  - High-churn table → fillfactor 70-80 leaves slack so inserts/HOT-updates fit
    WITHOUT splitting → fewer splits, less bloat.
  - Append-only / read-only table → fillfactor 100 to pack tight and save space.
Over time, splits + MVCC dead tuples bloat the index → REINDEX / VACUUM to reclaim.
```

---

## Senior Mantras

```
1. Storage engine — not the query language — sets write vs read performance.

2. B-tree = in-place updates, random writes, fast reads + range scans (OLTP).

3. LSM = append to memtable, flush sequential SSTables, compact later (write-heavy).

4. You pay 3 taxes: write, read, space amplification. RUM: optimize 2 of 3.

5. LSM reads survive via Bloom filters (skip files) + sparse fence pointers (seek 1 block).

6. Leveled compaction = read+space optimized, more write amp.
   Size-tiered = write optimized, more space + read amp.

7. LSM deletes are TOMBSTONES — never erase. Delete-heavy + range-scan = pain.

8. Time-series → LSM (TWCS / partition-drop). Random-update OLTP → B-tree.

9. ClickHouse MergeTree is LSM-LIKE + columnar, not a classic key/value LSM.

10. When unsure: B-tree for reads & updates, LSM for write floods. Then benchmark.
```

---

## Related Topics

- [07_postgresql_internals.md](07_postgresql_internals.md) — WAL, MVCC, VACUUM (the B-tree engine in practice)
- [08_cap_theorem_db_selection.md](08_cap_theorem_db_selection.md) — pick-2 tradeoffs, choosing a database
- [17_timescaledb_timeseries.md](17_timescaledb_timeseries.md) — time-series on a B-tree (Postgres) engine
- [20_advanced_indexing.md](20_advanced_indexing.md) — B-tree vs GIN/BRIN/Hash index types in Postgres
- [27_clickhouse_olap.md](27_clickhouse_olap.md) — MergeTree (LSM-like) columnar OLAP engine
- [28_vector_databases_comparison.md](28_vector_databases_comparison.md) — HNSW/IVF index structures for vectors
