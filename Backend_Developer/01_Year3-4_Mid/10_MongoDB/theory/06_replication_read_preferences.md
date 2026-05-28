# MongoDB Replication & Read Preferences

## Why It Matters

Production MongoDB = replica set (3+ nodes). Understanding replication critical for:
- **HA** → primary fails, secondary promoted
- **Read scaling** → offload reads to secondaries
- **Geographic distribution** → read from nearest
- **Disaster recovery** → backup replica

Senior interview: "Primary node fails — what happens to writes?" → secondary elected, brief downtime, app reconnects.

---

## Core Concepts

### Replica Set Architecture

```
                  Client
                    │
              ┌─────┴─────┐
              │  Primary  │  ← writes
              └─────┬─────┘
                    │ replication via oplog
        ┌───────────┼───────────┐
   Secondary 1   Secondary 2   Secondary 3
        │             │             │
      Reads         Reads        Reads
                                (depending on read pref)
```

3+ data-bearing nodes for HA. Plus optional:
- **Arbiter** — votes only, no data (deprecated for new setups)
- **Hidden** — replica not visible to clients (backups)
- **Delayed** — applies oplog after delay (disaster recovery)
- **Priority 0** — never elected primary

### Oplog (Operations Log)

Capped collection `local.oplog.rs` on each node. Primary writes ops, secondaries tail it and apply.

```javascript
db.oplog.rs.find().sort({ts: -1}).limit(5).pretty()
```

Oplog size: default ~5% of disk. Tune via `--oplogSize`. Larger = longer lag tolerance.

### Election Process

1. Secondary loses connection to primary
2. Detects via heartbeat (every 2s)
3. After `electionTimeoutMillis` (default 10s), starts election
4. Members vote
5. Majority wins → new primary
6. Election typically 12-15s

Election priority:
1. Higher `priority` config value
2. More up-to-date oplog
3. Better network connectivity

### Read Preferences

```python
from pymongo import ReadPreference


PRIMARY = ReadPreference.PRIMARY              # default, only primary
PRIMARY_PREFERRED = ReadPreference.PRIMARY_PREFERRED  # primary, fallback secondary
SECONDARY = ReadPreference.SECONDARY          # only secondaries
SECONDARY_PREFERRED = ReadPreference.SECONDARY_PREFERRED  # secondary, fallback primary
NEAREST = ReadPreference.NEAREST              # lowest latency, any node
```

```python
client = MongoClient("mongodb://...", readPreference='secondaryPreferred')

# Or per-collection
collection = db.get_collection('users', read_preference=ReadPreference.SECONDARY)


# Or per-operation
db.users.find({}, ...).hint(...)  # most modern client APIs
```

### Read Concerns

```python
ReadConcern('local')        # default — fast, may include uncommitted
ReadConcern('available')    # sharded specific
ReadConcern('majority')     # majority-committed only — safer
ReadConcern('linearizable') # most recent ack-ed write — slow
ReadConcern('snapshot')     # transaction-only — point-in-time
```

**Trade-off:** local = fast but may rollback if primary changes. majority = guaranteed durable.

### Write Concerns

```python
from pymongo import WriteConcern


WriteConcern(w=1)            # primary only — fast, less safe
WriteConcern(w='majority')   # majority of replicas — recommended
WriteConcern(w=3)            # 3 specific replicas
WriteConcern(w='all')        # all replicas
WriteConcern(j=True)         # journal commit
WriteConcern(wtimeout=10000) # timeout in ms
```

```python
result = db.users.with_options(
    write_concern=WriteConcern('majority', j=True, wtimeout=10000),
).insert_one({...})
```

### Causal Consistency Sessions

```python
with client.start_session(causal_consistency=True) as session:
    db.col1.insert_one({...}, session=session)
    # This read on a secondary will see the above write
    db.col1.find_one({...}, session=session)
```

Ensures read-your-own-writes even across primary/secondary.

### Replication Lag

```javascript
rs.printSlaveReplicationInfo()
// secondary: ... 0 secs behind primary

db.printReplicationInfo()
// oplog size, log length...
```

Lag > 10s = problem (slow disk, network, or load).

### Setup (3-Member RS)

```bash
mongod --replSet rs0 --port 27017 --dbpath /data/rs0 &
mongod --replSet rs0 --port 27018 --dbpath /data/rs1 &
mongod --replSet rs0 --port 27019 --dbpath /data/rs2 &
```

```javascript
// In one shell
rs.initiate({
    _id: "rs0",
    members: [
        { _id: 0, host: "host1:27017", priority: 2 },
        { _id: 1, host: "host2:27017", priority: 1 },
        { _id: 2, host: "host3:27017", priority: 1 }
    ]
})
```

---

## How It Works Internally

### Heartbeat

Members ping each other every `heartbeatIntervalMillis` (default 2s). Failure = mark down after `electionTimeoutMillis` (10s).

### Optime + Timestamps

Each oplog entry has timestamp. Replicas track applied timestamp. "Lag" = primary timestamp - secondary timestamp.

### Election Algorithm

Raft-inspired. Higher-priority candidate with most up-to-date oplog wins. Quorum required (majority of voting members).

### Read Preference Routing

Client driver maintains member list + ping latency. Routes reads based on read preference + latency window (`localThresholdMs`, default 15ms).

---

## Common Pitfalls

### 1. Reading from Secondary with Stale Data

```python
# Just wrote — read might not see it
db.users.insert_one({'name': 'X'})
user = db.users.with_options(
    read_preference=ReadPreference.SECONDARY,
).find_one({'name': 'X'})
# May return None due to replication lag
```

Solutions: (1) Use causal consistency sessions. (2) Read from primary for read-after-write.

### 2. Replication Lag Cascading

```
Slow disk on secondary → lag grows → falls off oplog → resync from scratch (hours)
```

Monitor lag actively. Alert at > 30s.

### 3. Arbiter in Production

Arbiter votes but has no data. Recommended only for cost savings on small setups. For HA: prefer 3 data-bearing members over 2 + arbiter.

### 4. Even Number of Members

3, 5, 7 = good (clear majority). 4, 6 = bad (tie = no election).

### 5. write_concern=1 in Critical Systems

Primary acks → fails → write lost. Use `'majority'` for important data.

### 6. localThresholdMs Too Low

Excludes most secondaries from "nearest" read. Default 15ms is fine for LAN; bump for cross-region.

---

## Interview Q&A

**Q1:** MongoDB replication kaise work karta hai?
**A:** Primary writes to oplog (capped collection). Secondaries continuously tail oplog and apply ops. Asynchronous by default. Can be made synchronous via `w='majority'` write concern — primary waits for majority ack before returning.

**Q2:** Read preferences ke trade-offs?
**A:** Primary: consistent (read-your-own-writes), but no scaling. Secondary: scales reads, but lag risk (stale data). Nearest: lowest latency, mixed primary/secondary. For most apps: primary or primaryPreferred. For analytics: secondary.

**Q3:** Election process explain karo.
**A:** (1) Secondary loses primary heartbeat. (2) After 10s (electionTimeoutMillis), starts election. (3) Asks majority of voting members. (4) Most up-to-date secondary with highest priority wins. (5) Becomes primary, starts serving writes. Election takes ~12-15s typically.

**Q4:** Write concern majority benefit?
**A:** Write isn't acknowledged until majority of replicas have it. Survives primary failover — promoted secondary already has the write. Without `'majority'`, write could be lost on stepdown.

**Q5:** Replication lag detect aur handle?
**A:** `rs.printSecondaryReplicationInfo()` shows lag per secondary. Alert on > 10s. Causes: slow disk, network, write storm, secondary doing background tasks. Fix: scale disk, dedicate secondary to reads only, add more replicas.

**Q6:** Hidden vs delayed secondary?
**A:** Hidden: data-bearing but not visible to clients. Use for backups (run mongodump on it without affecting clients). Delayed: applies oplog after delay (e.g., 1 hour). Use for "oh no" recovery — accidentally deleted collection, fail over to delayed before delay elapses.

**Q7:** Causal consistency kya hai?
**A:** Session option that ensures "read your own writes" + "monotonic reads" + "monotonic writes". Useful when reading from secondary after write. Client tracks operation timestamps; ensures reads see at least those.

**Q8:** Oplog full ho gaya — kya hota hai?
**A:** Oplog is capped — old entries overwritten. If secondary's lag exceeds oplog window, can't catch up incrementally → full resync needed (copy entire dataset). Avoid by: sizing oplog generously (rs.printReplicationInfo() shows window), monitoring lag.

---

## Real-World Use Cases

### 1. Read-Heavy App with Eventual Consistency OK

```python
client = MongoClient(
    "mongodb://host1,host2,host3/?replicaSet=rs0",
    readPreference='secondaryPreferred',
)
# 70% reads → distributed across secondaries
# Writes → primary
```

### 2. Analytics on Hidden Replica

```javascript
// On primary
rs.add({host: "analytics:27017", priority: 0, hidden: true, votes: 0})

// Then run heavy aggregations against analytics node directly
// Doesn't affect normal traffic
```

### 3. Multi-Region

```javascript
rs.initiate({
    _id: "rs0",
    members: [
        { _id: 0, host: "us-east:27017", priority: 2 },     // primary
        { _id: 1, host: "us-west:27017", priority: 1, tags: { region: "us-west" } },
        { _id: 2, host: "eu:27017", priority: 1, tags: { region: "eu" } },
    ]
})

// Read from specific region
client.read_preference = ReadPreference.NEAREST  # auto picks lowest latency
```

---

## References

- [MongoDB Replication](https://www.mongodb.com/docs/manual/replication/)
- [Read Preferences](https://www.mongodb.com/docs/manual/core/read-preference/)
- [Write Concerns](https://www.mongodb.com/docs/manual/reference/write-concern/)
- Aphyr's MongoDB Jepsen analysis
