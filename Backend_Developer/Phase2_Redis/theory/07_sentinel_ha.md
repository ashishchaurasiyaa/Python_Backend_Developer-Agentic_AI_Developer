# Redis Sentinel — High Availability

## Why It Matters

Sentinel = automatic failover without sharding. Best for:
- HA on smaller datasets (single master sufficient)
- No data partitioning needed
- Simpler ops than Cluster

vs Cluster: Sentinel has 1 master (single shard), Cluster has N masters.

Senior interview: "Redis master crashes — how does app continue without manual intervention?" → Sentinel monitors + auto-promotes replica.

---

## Core Concepts

### Architecture

```
                ┌──────────┐
                │ Sentinel 1│──┐
                └──────────┘  │
        ┌──────┐               │ monitor
Client ←┤App   ├─→ Master ←────┤
        └──────┘     ↑          │
                ┌────┴──┐       │
                │Replica1│       │
                └───────┘       │
                ┌──────────┐    │
                │ Sentinel 2│──┘
                └──────────┘
                ┌──────────┐
                │ Sentinel 3│
                └──────────┘
```

3+ Sentinels for quorum. Each monitors master + replicas.

### Sentinel Configuration

```conf
# sentinel.conf
port 26379

# Watch master named 'mymaster'
sentinel monitor mymaster 127.0.0.1 6379 2
# Quorum = 2 (min Sentinels to agree on failure)

sentinel down-after-milliseconds mymaster 5000
sentinel failover-timeout mymaster 30000
sentinel parallel-syncs mymaster 1

# Optional auth
sentinel auth-pass mymaster secret
```

Run 3+ Sentinels:
```bash
redis-sentinel sentinel-1.conf
redis-sentinel sentinel-2.conf
redis-sentinel sentinel-3.conf
```

### Python Client (Sentinel-aware)

```python
from redis.sentinel import Sentinel


sentinel = Sentinel(
    [
        ('sentinel-1', 26379),
        ('sentinel-2', 26379),
        ('sentinel-3', 26379),
    ],
    socket_timeout=0.5,
)


# Get current master
master = sentinel.master_for('mymaster', socket_timeout=0.5)
master.set('key', 'value')


# Read from replica
slave = sentinel.slave_for('mymaster', socket_timeout=0.5)
val = slave.get('key')
```

Client auto-handles failover — reconnects to new master after promotion.

### Failover Process

```
1. Master unreachable for `down-after-milliseconds`
2. Sentinel marks master SDOWN (subjectively down)
3. Sentinels exchange opinions — if quorum agrees: ODOWN (objectively down)
4. Sentinels elect leader (Raft-like)
5. Leader picks best replica (priority + offset + run_id)
6. Promote replica: SLAVEOF NO ONE
7. Reconfigure other replicas: SLAVEOF new-master
8. Notify clients via Pub/Sub
```

Old master rejoins → becomes replica.

### Split-Brain Protection

```conf
# Old master refuses writes if alone (not connected to enough replicas)
min-replicas-to-write 1
min-replicas-max-lag 10
```

Prevents two masters serving conflicting writes during network partition.

### Sentinel vs Cluster Decision

| Scenario | Use |
|---|---|
| < 100 GB data + HA | Sentinel |
| > 100 GB data | Cluster |
| Need sharding | Cluster |
| Want simpler ops | Sentinel |
| Single key transactions/Lua | Sentinel (multi-key works) |

---

## How It Works Internally

### Sentinel Discovery

Sentinel discovers replicas by `INFO REPLICATION` on master. Sentinel discovers other Sentinels via Pub/Sub on `__sentinel__:hello` channel.

### Election

Inter-Sentinel agreement uses Raft-like consensus. Sentinel with most votes from others in current epoch becomes leader, performs failover.

### Pub/Sub Events

Sentinels publish: `+sdown`, `+odown`, `+failover-state-...`, `+switch-master`. Clients subscribe for instant notification.

---

## Common Pitfalls

### 1. Less Than 3 Sentinels

Quorum impossible with 2 (network partition deadlock). Always 3 or 5.

### 2. Sentinels on Same Host as Redis

Single-host failure = lose all Sentinels too. Put Sentinels on independent machines.

### 3. Direct Connection to Master

```python
r = redis.Redis(host='current-master-ip', port=6379)  # breaks on failover
```

Use Sentinel client — `sentinel.master_for('mymaster')`.

### 4. Long Lock-Holding Replicas Promoted

Old replica with replication lag promoted → data loss. Configure `min-replicas-max-lag` + `min-replicas-to-write` on master.

### 5. Two-Sentinel Setup

Quorum = 2 means BOTH must agree. If one fails, no failover possible (and other can't quorum-check). 3 Sentinels = tolerates 1 failure.

### 6. Application Restart on Failover

Some clients cache master IP. Library should re-resolve via Sentinel on `CONNECTION_REFUSED`.

---

## Interview Q&A

**Q1:** Sentinel kya kaam karta hai?
**A:** Monitors Redis master + replicas. On master failure: (1) Detects via PING timeout. (2) Quorum check across Sentinels. (3) Elects leader Sentinel. (4) Promotes best replica to master. (5) Reconfigures other replicas to follow new master. (6) Notifies clients. All automated; no manual intervention.

**Q2:** Quorum kya hota hai Sentinel mein?
**A:** Min number of Sentinels that must agree master is down. `sentinel monitor mymaster IP PORT 2` = quorum=2. For 3 Sentinels, quorum=2 (tolerates 1 failure). For 5, quorum=3. Don't run < 3 Sentinels (split brain risk).

**Q3:** Best replica kaise pick hoti hai promotion ke liye?
**A:** Order: (1) Replica priority (config, lower = better; 0 = never promote). (2) Replication offset (most recent first). (3) Run ID (deterministic tiebreaker). So configure `replica-priority` on replicas — keep "preferred" replica with lower priority value.

**Q4:** Split-brain Sentinel mein kaise prevent?
**A:** `min-replicas-to-write N` on master: master refuses writes if < N replicas connected. Combined with `min-replicas-max-lag` — replicas must be < N seconds behind. During partition, old master (alone) stops writing → no data divergence.

**Q5:** Failover ke baad client kaise discover karta hai new master?
**A:** Sentinel-aware client (`redis.sentinel`) — on connection error or reconnect, queries Sentinels for current master. Some clients use `__sentinel__:hello` Pub/Sub for instant notification. Always reconnect via Sentinel, never cache IP.

**Q6:** Sentinel vs Cluster — choose karne ka criteria?
**A:** Data size: < 100 GB → Sentinel; > 100 GB → Cluster. Sharding: not needed → Sentinel; needed → Cluster. Operational complexity: less → Sentinel; willing to deal with hash tags + cross-shard limits → Cluster. Most production apps: Sentinel adequate.

**Q7:** Failover time tune kaise?
**A:** `down-after-milliseconds` (default 30s) — lower = faster detection but more false positives on network blip. Production: 5-10 sec. `failover-timeout` for entire process (default 3 min). With `parallel-syncs 1` — only one replica resyncs at a time (less write traffic spike).

**Q8:** Old master jab rejoin karta hai, kya hota hai?
**A:** Sentinel reconfigures it as replica of new master. It syncs from new master (may need full resync if too behind). During sync, it's writeable=false. Data on old master conflicting with new is lost.

---

## Real-World Use Cases

### 1. Session Store HA

```python
sentinel = Sentinel([('s1', 26379), ('s2', 26379), ('s3', 26379)])


def get_session(session_id):
    r = sentinel.slave_for('sessions')  # read from replica
    return r.get(f'session:{session_id}')


def set_session(session_id, data):
    r = sentinel.master_for('sessions')  # writes to master
    r.setex(f'session:{session_id}', 3600, data)
```

### 2. Cache with Failover

App reads from replica (fast, cheap), writes to master (durable). Auto-failover during master crash.

### 3. Job Queue with HA

Celery/RQ backed by Redis with Sentinel = no broker downtime during failover.

---

## References

- [Redis Sentinel docs](https://redis.io/docs/management/sentinel/)
- [HA architecture patterns](https://redis.io/topics/sentinel)
- redis-py Sentinel client
