# Redis Replication Fundamentals

## Why It Matters

Sentinel automates failover, Cluster automates sharding — but both are built ON TOP of one primitive: async master → replica replication. Interviewer usually asks Sentinel/Cluster questions FIRST (they're the "cooler" topics), but a senior candidate should be able to answer the layer underneath without hesitation.

Senior interview: "Sentinel se pehle — Redis replication actually kaam kaise karta hai under the hood?" → agar sirf "replica copies master ka data" bol diya, that's junior-level. Senior answer covers: full vs partial resync, replication backlog, async ack semantics, aur consistency tradeoffs — because THIS is what breaks in production (stale reads, data loss on failover, resync storms), not the Sentinel/Cluster orchestration on top.

Also directly relevant: read scaling (replicas for reporting/analytics) is one of the most common Redis production patterns, and it only makes sense once you understand replication lag.

---

## Core Concepts

### Architecture

```
        writes                 async replication stream
Client ────────→ ┌────────┐ ──────────────────────────→ ┌──────────┐
                  │ Master │                              │ Replica 1│
                  └────────┘ ──────────────────────────→ └──────────┘
                       │                                  ┌──────────┐
                       └────────────────────────────────→ │ Replica 2│
                              reads (optional)             └──────────┘
```

One master accepts writes. N replicas connect to it, receive a continuous stream of write commands, and (by default) serve read-only traffic. This is exactly the layer Sentinel monitors and automates failover for (`07_sentinel_ha.md`), and it's also the mechanism each shard in Cluster mode uses internally for its own replicas (`06_cluster_mode.md`).

### Attaching a Replica — REPLICAOF / SLAVEOF

Runtime (no restart needed):

```bash
redis-cli -p 6380 REPLICAOF 127.0.0.1 6379
# old name (still works, deprecated alias): SLAVEOF 127.0.0.1 6379
```

Config file (applied on startup):

```conf
# redis.conf on the replica
replicaof 127.0.0.1 6379
# masterauth <password>     # if master has requirepass
```

Detach / promote to standalone master:

```bash
redis-cli -p 6380 REPLICAOF NO ONE
```

Sentinel issues exactly this command during automated failover (promote the chosen replica, then `REPLICAOF` the others to the new master).

### Full Resync vs Partial Resync

Jab replica pehli baar attach hoti hai (or reconnects after too long a gap), handshake roughly:

```
1. Replica → Master: PING
2. Replica → Master: REPLCONF listening-port <port>
3. Replica → Master: PSYNC <replid> <offset>
4. Master decides: FULLRESYNC or CONTINUE
```

**Full resync** (first attach, or replid mismatch, or offset too old):
- Master does `BGSAVE` (or diskless — see below), sends the RDB snapshot to the replica.
- Meanwhile new writes are buffered.
- After RDB load, master streams the buffered + subsequent write commands.
- Expensive: full dataset transfer + fork overhead on master.

**Partial resync** (brief disconnect, e.g. network blip):
- Replica remembers the master's replication ID + the offset it last successfully applied.
- On reconnect, it sends `PSYNC <replid> <offset>`.
- Master checks: is that offset still inside its **replication backlog** (a bounded in-memory ring buffer holding recent write stream)?
  - Yes → master replies `+CONTINUE` and streams only the missing commands. Cheap, fast.
  - No (backlog wrapped around, offset fell out) → master falls back to full resync.

This is why `repl-backlog-size` matters — bigger backlog = replica can survive a longer disconnect before needing a full resync, at the cost of RAM on the master (allocated once, shared across all replicas of that master).

### Async Replication & Consistency Implications

Redis replication is **asynchronous by default**: master applies the write, replies to the client, and streams the command to replicas without waiting for their ACK. This means:

- Write latency to the client is NOT affected by replica speed/distance.
- BUT: if the master crashes right after replying to the client and before the replica received that command, the write is lost on failover. That window = **replication lag**.

`WAIT numreplicas timeout` exists to opt into stronger guarantees:

```python
r.set('critical:key', 'value')
acked = r.execute_command('WAIT', 1, 1000)   # wait up to 1000ms for 1 replica to ack
```

`WAIT` blocks until N replicas have acknowledged the offset the write landed at, OR the timeout expires — whichever first. It's a best-effort assurance, NOT a hard synchronous-replication guarantee (Redis isn't Raft/Paxos — no quorum commit protocol, no rollback on failure).

This is the CAP-theorem-adjacent tradeoff senior interviewers probe: between master and replicas, Redis defaults to **availability + performance over consistency**. You can dial toward consistency (`WAIT`, `min-replicas-to-write`) but never get a hard guarantee without giving up Redis's core performance model.

### Reading from Replicas

```conf
replica-read-only yes    # default — replica rejects direct writes
```

Read scaling on replicas is a very common pattern — offload heavy/reporting reads from the master, reduce its load. But it comes with staleness risk: a replica read can return data older than the master's current state by however many milliseconds/seconds of lag exist.

**Client routing is manual.** redis-py does NOT auto-load-balance reads across replicas — a plain `redis.Redis(host=master_ip)` only ever talks to whatever host you gave it. To actually read from replicas, the app has to:

```python
master = redis.Redis(host='master-host', port=6379, decode_responses=True)
replica = redis.Redis(host='replica-host', port=6379, decode_responses=True)

master.set('key', 'value')     # writes → master
val = replica.get('key')       # reads → replica (may be stale)
```

...or use something that manages this for you: `redis.sentinel.Sentinel` (`master_for` / `slave_for`, see `07_sentinel_ha.py`), `RedisCluster(read_from_replicas=True)`, or a proxy in front (HAProxy/Envoy/twemproxy) that routes reads and writes separately.

### Diskless Replication

```conf
repl-diskless-sync yes
repl-diskless-sync-delay 5    # wait up to 5s to batch multiple replica requests
```

Instead of `BGSAVE`-to-disk-then-transfer-the-file, the master forks and streams the RDB payload directly over the replica's socket as it's generated — never touches disk. Useful when local disk is slow (spinning disks) or expensive/throttled (cloud block storage, e.g. burst-credit-limited EBS volumes). Tradeoff: if the socket transfer fails partway, it has to restart from scratch (no reusable file sitting on disk to resume from), and multiple replicas attaching at once can't share one written file the way disk-based sync can — hence `repl-diskless-sync-delay` batches near-simultaneous replica connections into one shared transfer.

### Chained Replication (Sub-Replicas)

A replica can itself have replicas — just point another instance's `replicaof` at the replica instead of the top-level master:

```conf
# redis.conf on a sub-replica
replicaof <replica-1-ip> <replica-1-port>
```

```
Master ──→ Replica 1 ──→ Sub-Replica 1a
                     └──→ Sub-Replica 1b
```

Replica 1 forwards the same replication stream it receives (same `replid`/offset lineage) down to its own sub-replicas. This fans out load: instead of the master directly serving 10 replicas' worth of replication traffic, it serves 2-3 "layer 1" replicas, and they each fan out further. Cost: an extra hop of lag per layer — chain depth directly adds to worst-case staleness.

### Sentinel/Cluster Are Built on This

- **Sentinel** (`07_sentinel_ha.md`) monitors this exact master→replica link via `INFO REPLICATION`, and its failover procedure IS `REPLICAOF NO ONE` on the chosen replica + `REPLICAOF <new-master>` on the rest.
- **Cluster** (`06_cluster_mode.md`) — each shard/master in a cluster has its own replica(s), replicating via this identical mechanism; cluster-level failover promotes a shard's replica the same way Sentinel does for a single master.

---

## How It Works Internally

### Replication ID + Offset

Every master tracks:
- `master_replid` — a 40-char pseudo-random ID identifying "this replication history/lineage."
- `master_replid2` — kept around briefly after a failover so a newly-promoted master can still serve partial resyncs to replicas that were following the OLD master (continuity across promotion).
- `master_repl_offset` — a monotonically increasing byte counter. Every write command propagated to replicas advances this offset by the byte length of that command.

A replica tracks `slave_repl_offset` — how many of those bytes it has applied. `master_repl_offset - slave_repl_offset` (roughly) is the lag, in bytes/commands (not directly seconds, but `master_last_io_seconds_ago` and `slave_repl_offset` deltas over time approximate it).

### Replication Backlog

```conf
repl-backlog-size 1mb     # default; tune up for write-heavy masters / flaky networks
```

A fixed-size in-memory ring buffer holding the most recent slice of the replication stream. On reconnect, the master checks whether the replica's requested offset is still inside this window:
- Inside → partial resync (`+CONTINUE`), cheap.
- Fell out (too much write volume happened during the disconnect, or disconnect too long) → full resync.

Sizing rule of thumb: `repl-backlog-size ≥ expected_disconnect_duration_seconds × peak_write_bytes_per_second`. Bigger buffer survives longer network blips before forcing a full resync, but costs RAM (allocated once per master when the first replica connects, freed after replicas have been gone for a while — no per-replica multiplication).

### PSYNC Handshake (Full Detail)

```
Replica: PING
Master:  PONG
Replica: REPLCONF listening-port <replica-port>
Master:  +OK
Replica: REPLCONF capa eof capa psync2
Master:  +OK
Replica: PSYNC <replid-or-?> <offset-or--1>
Master:  +FULLRESYNC <replid> <offset>   OR   +CONTINUE [<replid>]
```

### Useful INFO Fields

```bash
INFO replication
```

On master: `role:master`, `connected_slaves`, `slave0:ip=...,port=...,state=online,offset=...,lag=...`, `master_replid`, `master_repl_offset`.

On replica: `role:slave`, `master_host`, `master_port`, `master_link_status:up|down`, `master_last_io_seconds_ago`, `slave_repl_offset`, `master_repl_offset` (replica also mirrors this once synced).

---

## Common Pitfalls

### 1. Assuming Read-After-Write Consistency on Replica Reads

```python
master.set('order:5001:status', 'paid')
status = replica.get('order:5001:status')   # might still return old value!
```

Async replication means the write may not have propagated yet. If the app logic needs read-your-own-write, read from master (or use `WAIT`), not the replica.

### 2. "Thundering Resync" — Full Resync Spike on Master

Adding a new replica (or one reconnecting after a long gap) to a master with a large dataset triggers `BGSAVE`/diskless RDB generation + a full data transfer. On a big dataset this is a real one-time CPU (fork + serialize) and network (multi-GB transfer) spike on the master, potentially affecting write latency for live traffic. Mitigate: add replicas one at a time (not all at once), use `repl-diskless-sync` on fast networks, do it during low-traffic windows, and watch `rdb_bgsave_in_progress` / network graphs during the operation.

### 3. `min-replicas-to-write` / `min-replicas-max-lag` Misconfiguration

```conf
min-replicas-to-write 1
min-replicas-max-lag 10
```

Left unset (both default 0): master keeps accepting writes even with zero healthy replicas — silent risk during a partition, exactly what Sentinel's split-brain protection depends on being configured (see `07_sentinel_ha.md` pitfall #4). Set too strict (e.g. requiring 3 replicas within 1s lag on a flaky network) and normal blips halt ALL writes on the master — an availability outage you inflicted on yourself chasing consistency.

### 4. Manual Promotion Without Checking Offset First

```bash
redis-cli -p 6380 REPLICAOF NO ONE   # promoting replica manually, no checks
```

If you promote a replica that's behind (lagging, or was disconnected and doing a resync), you lose whatever writes it never received — and if the old master comes back and clients haven't repointed, you can get divergent data on both sides. This is EXACTLY the manual version of what Sentinel automates safely: Sentinel's failover picks the replica with lowest `replica-priority`, then highest replication offset (most up-to-date), then lowest run_id as tiebreaker — never blind. Manual promotion should always check `INFO replication` → `slave_repl_offset` against the master's last known `master_repl_offset` first.

### 5. `repl-backlog-size` Too Small for Write Volume

A high-write-throughput master with the default 1mb backlog can wrap the ring buffer in well under a second of peak traffic. Any replica disconnect longer than "instant" then forces full resync every time — constant expensive resyncs instead of cheap partial ones. Size the backlog to your realistic network-blip duration × write throughput.

### 6. Writing Directly to a Replica

```conf
replica-read-only no    # dangerous, rarely justified
```

Turning this off lets clients write directly to a replica. Those writes are NOT propagated back to the master or to sibling replicas — the replica silently diverges from the rest of the topology, and the divergent data is wiped on the next full resync from master. Leave `replica-read-only yes` (the default) unless you have a very specific, well-understood reason not to.

---

## Interview Q&A

**Q1: Replica master se attach kaise hoti hai?**
A: `REPLICAOF <host> <port>` command runtime pe (no restart), ya `replicaof` directive redis.conf mein (applied on startup). Detach/promote karne ke liye `REPLICAOF NO ONE`. Old alias `SLAVEOF` still works but deprecated in naming.

**Q2: Full resync aur partial resync mein difference?**
A: Full resync = master RDB snapshot banata hai (disk-based BGSAVE ya diskless streaming), poora dataset replica ko bhejta hai, phir buffered writes stream karta hai — expensive, first attach pe ya bahut lambi disconnect ke baad hota hai. Partial resync = replica apna last-seen replication ID + offset bhejta hai (`PSYNC replid offset`), agar wo offset ab bhi master ke replication backlog (bounded ring buffer) mein hai to master sirf missing commands stream karta hai — cheap. Backlog se offset fall out ho gaya (bahut der disconnect ya bahut zyada write volume) to full resync pe fallback.

**Q3: Redis replication synchronous hai ya asynchronous? Consistency implications?**
A: Asynchronous by default — master client ko reply karta hai bina kisi replica ke ACK ka wait kiye. Fast writes, lekin agar master crash ho jaye reply ke turant baad aur replica ne wo write receive na kiya ho, wo data failover pe lost ho sakta hai (replication lag window). `WAIT numreplicas timeout` command se opt-in stronger guarantee mil sakti hai (N replicas ka ack wait karo, timeout tak) — lekin ye hard synchronous guarantee nahi hai, best-effort hai. Redis CAP tradeoff mein availability+performance ko consistency se upar rakhta hai between master-replica.

**Q4: Replica se read karna safe hai kya? Client routing kaise hoti hai?**
A: `replica-read-only yes` default — replica writes reject karta hai, reads allow karta hai. Read scaling ke liye common pattern (reporting/analytics offload) lekin staleness risk hai — replica master se kuch ms/sec peeche ho sakta hai. redis-py khud replicas ke beech reads load-balance nahi karta — app ko explicitly do connections maintain karne padte hain (master aur replica alag `redis.Redis()` instances), ya Sentinel client (`slave_for`), ya Cluster ka `read_from_replicas=True`, ya ek proxy layer use karo.

**Q5: Diskless replication kya hai aur kab use karoge?**
A: `repl-diskless-sync yes` — master RDB snapshot ko disk pe likhne ke bajaye directly socket pe stream karta hai replica ko. Slow disks (spinning) ya throttled cloud storage (EBS burst credits) pe useful — disk I/O bottleneck avoid karta hai. Tradeoff: transfer beech mein fail ho to poora restart karna padta hai (koi reusable file disk pe nahi hai), isliye `repl-diskless-sync-delay` multiple near-simultaneous replica requests ko batch karta hai ek hi transfer mein.

**Q6: Chained replication (sub-replicas) kyun use karte hain?**
A: Ek replica khud kisi aur replica ka replica ban sakta hai (`replicaof` doosri replica ko point karo, master ko nahi). Isse master ka fan-out load kam hota hai — master sirf top-layer replicas ko serve karta hai, wo aage apne sub-replicas ko forward karte hain. Tradeoff: har extra layer worst-case lag mein add hota hai, chain depth monitor karni padti hai.

**Q7: Replica ko manually promote karna vs Sentinel automated failover — difference?**
A: Manual `REPLICAOF NO ONE` blind hai agar pehle `INFO replication` check nahi kiya — lagging replica promote ho gaya to un writes ka data loss ho jayega jo usne receive hi nahi kiye the. Sentinel automated failover mein selection criteria hai: sabse pehle `replica-priority` (lower better, 0 = never promote), phir sabse recent replication offset, phir run_id tiebreaker — kabhi blind promote nahi karta. Production mein manual promotion sirf emergency mein aur offset check karke.

---

## Real-World Use Cases

### 1. Reporting/Analytics Read Offload

```python
master = redis.Redis(host='redis-master', decode_responses=True)
replica = redis.Redis(host='redis-replica-analytics', decode_responses=True)

def record_event(event):
    master.xadd('events:stream', event)          # writes → master

def run_nightly_aggregation():
    return replica.xrange('events:stream', '-', '+')  # heavy scan → replica
```

Heavy/slow reporting queries hit a dedicated replica instead of competing with production write traffic on the master.

### 2. Geo-Distributed Read Replicas

Replicas placed in each region (US, EU, APAC) serve local read traffic with low latency, while all writes still funnel back to a single master region. Read latency improves for users near a replica; write latency stays bound by distance to the single master — a deliberate tradeoff, not free geo-replication.

### 3. The Foundation Under Sentinel and Cluster

Every HA and sharding pattern in this repo sits on top of exactly what's described here: Sentinel (`07_sentinel_ha.md`) automates the `REPLICAOF` failover dance; Cluster (`06_cluster_mode.md`) runs this same master→replica link per-shard. Debugging a "Sentinel failover picked a stale replica" or "Cluster shard replica won't catch up" incident always comes back to these fundamentals — replication ID/offset, backlog size, and async lag.

---

## References

- [Redis Replication docs](https://redis.io/docs/management/replication/)
- [PSYNC / replication internals](https://redis.io/docs/management/replication/#how-redis-replication-works)
- `07_sentinel_ha.md` — automated failover built on this layer
- `06_cluster_mode.md` — per-shard replication in Cluster mode
