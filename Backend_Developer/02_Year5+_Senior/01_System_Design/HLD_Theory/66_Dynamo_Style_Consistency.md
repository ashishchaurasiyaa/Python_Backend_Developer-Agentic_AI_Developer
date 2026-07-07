# 66 — Dynamo-Style Consistency: Gossip, Quorum, Hinted Handoff, Anti-Entropy

> How leaderless distributed databases (Cassandra, DynamoDB, Riak) stay available and eventually consistent without a single point of coordination.

---

## Why We Need This

Every distributed-data-store design question eventually splits into two
families: **leader-based** (Raft/Paxos, already covered in file 62 — one node
coordinates writes, strong consistency, but that leader is a bottleneck/SPOF)
and **leaderless** (Dynamo-style — ANY node can accept a write, no single
coordinator, trading strict consistency for availability). This file covers
the leaderless family's core mechanisms — the ones a "design Cassandra" or
"design a highly-available key-value store" question actually probes.

Senior interview: "Design a globally-distributed key-value store that must
NEVER reject a write, even during a network partition." → leaderless
architecture (Dynamo-style), not Raft — accepting availability over
consistency during partitions (the AP side of CAP, file 08).

---

## 1. Gossip Protocol — how nodes learn about each other without a coordinator

```
Every node periodically picks a few RANDOM other nodes and exchanges
"what I currently know" (cluster membership, node health, which nodes
own which data ranges).

Node A ──gossip──► Node B (random pick)
Node B ──gossip──► Node C (random pick, next round)
Node C ──gossip──► Node A (random pick, next round)

Information spreads EXPONENTIALLY across the cluster — after O(log N)
rounds, all N nodes have converged on the same view, with NO central
registry any node needs to query.
```

```python
# Simplified gossip round (conceptual — real implementations like
# Cassandra's use more sophisticated anti-entropy-aware gossip)
import random

class GossipNode:
    def __init__(self, node_id, peers):
        self.node_id = node_id
        self.peers = peers
        self.membership_view = {node_id: "alive"}

    def gossip_round(self):
        target = random.choice(self.peers)
        # Exchange membership views — merge, keeping the MOST RECENT
        # state per node (like a mini vector-clock comparison per entry)
        merged = {**self.membership_view, **target.membership_view}
        self.membership_view = merged
        target.membership_view = merged
```

**Why gossip instead of a central registry (like a ZooKeeper-style
coordinator)?** No single point of failure, and it scales to thousands of
nodes without the coordinator itself becoming a bottleneck — the tradeoff is
it takes O(log N) rounds to converge, so membership info is EVENTUALLY
consistent, not instant, across the whole cluster.

---

## 2. Quorum Reads/Writes — the `W + R > N` formula

```
N = total replicas of a piece of data
W = number of replicas that must ACK a write before it's considered successful
R = number of replicas queried on a read

RULE: if W + R > N, every read is GUARANTEED to overlap with at least
one replica that has the LATEST write — strong-ish consistency without
needing ALL N replicas to respond every time.
```

```
Example: N=3 replicas of a key.

W=2, R=2  → W+R=4 > N=3 ✅ Read always overlaps latest write (strong consistency)
W=1, R=1  → W+R=2 < N=3 ❌ Read might miss the latest write (fast, but stale reads possible)
W=3, R=1  → W+R=4 > N=3 ✅ Slow writes (must reach all 3), fast reads
W=1, R=3  → W+R=4 > N=3 ✅ Fast writes, slow reads (must query all 3)
```

```python
# Conceptual write path with W=2, N=3
def write(key, value, replicas, W=2):
    acks = 0
    for replica in replicas:
        if replica.write(key, value):   # async, in parallel in practice
            acks += 1
        if acks >= W:
            return "SUCCESS"   # don't need to wait for the 3rd replica
    return "FAILED"

# Conceptual read path with R=2 — read from 2 replicas, resolve conflicts
# by timestamp/vector clock (file 46) if they disagree
def read(key, replicas, R=2):
    responses = [r.read(key) for r in replicas[:R]]
    return resolve_latest(responses)   # vector clock / last-write-wins
```

**This is the tunable knob senior interviews want you to reason about
out loud:** `W`/`R`/`N` let you trade off consistency, latency, and
availability PER OPERATION — not a fixed system-wide choice. A shopping
cart write might use W=1 (fast, some staleness OK); a payment write might
use W=N (every replica must confirm, slower, but no data loss risk).

---

## 3. Hinted Handoff — surviving a temporarily-down replica

```
Write for key K should go to replicas {A, B, C}. Node C is temporarily
down (network blip, restart, etc).

WITHOUT hinted handoff: write to C fails outright, or the whole write
                        blocks waiting for C to come back.

WITH hinted handoff: another node (say A) TEMPORARILY stores C's copy
                      of the write PLUS a "hint" (a note: "this belongs
                      to C, forward it once C is back").
                      When C recovers, A detects it and forwards the
                      stored write to C, then discards its temporary copy.
```

```python
def write_with_hinted_handoff(key, value, target_replica, fallback_node):
    if target_replica.is_available():
        target_replica.write(key, value)
    else:
        # fallback_node stores it WITH a hint pointing back at the real owner
        fallback_node.store_hint(
            hint_for=target_replica.node_id,
            key=key,
            value=value,
        )

def on_node_recovery(recovered_node, cluster):
    for node in cluster:
        hints = node.get_hints_for(recovered_node.node_id)
        for hint in hints:
            recovered_node.write(hint.key, hint.value)
        node.clear_hints_for(recovered_node.node_id)
```

**Why this matters:** it lets the write path stay available (`W` can still
be satisfied) even when a replica is briefly unreachable, instead of
failing the write or blocking indefinitely — a direct expression of
choosing Availability over immediate per-replica consistency (AP side of CAP).

---

## 4. Anti-Entropy — reconciling replicas that drifted apart

```
Hinted handoff covers SHORT outages. What if a node was down for HOURS,
missed many writes, and hints expired/were lost? Replicas can end up
with genuinely DIFFERENT data for the same keys.

Anti-entropy = a BACKGROUND process that periodically compares replicas
and repairs differences — the "eventually" in "eventually consistent."
```

```
Merkle trees are the standard mechanism:
1. Each replica builds a Merkle tree over its data (hash of hash of hash...)
2. Two replicas compare their tree ROOT hashes first
3. If roots match → data is identical, done, no further comparison needed
4. If roots differ → recurse down the tree, comparing child hashes,
   until you isolate the SPECIFIC keys that actually differ
5. Only THOSE specific differing keys need their data transferred/repaired
   — not a full table scan/comparison
```

```python
# Conceptual Merkle-tree comparison (simplified)
def find_differing_keys(tree_a, tree_b):
    if tree_a.root_hash == tree_b.root_hash:
        return []   # identical — no repair needed, cheap early exit
    if tree_a.is_leaf():
        return [tree_a.key] if tree_a.value != tree_b.value else []
    differing = []
    for child_a, child_b in zip(tree_a.children, tree_b.children):
        differing += find_differing_keys(child_a, child_b)
    return differing
```

Cassandra's `nodetool repair` and DynamoDB's internal anti-entropy both use
this Merkle-tree comparison approach — it's efficient specifically because
most of the tree matches (most data hasn't drifted), so comparison is
usually O(log N) hash comparisons, not a full data transfer.

---

## Putting it together — the full leaderless write/read/repair lifecycle

```
1. Client writes key K → coordinator node forwards to N replicas
2. Quorum (W of N) ACK → write considered successful, client gets response
3. If a target replica is briefly down → HINTED HANDOFF stores it
   temporarily elsewhere, forwards once that replica recovers
4. Client reads key K → coordinator queries R replicas, resolves any
   conflicting versions via vector clocks (file 46) or last-write-wins
5. In the BACKGROUND, continuously: GOSSIP spreads cluster membership/health,
   and ANTI-ENTROPY (Merkle tree comparison) catches + repairs any
   replicas that drifted despite steps 1-4
```

---

## Interview Q&A

**Q: How does a Dynamo-style database stay available during a network partition, unlike a Raft-based system?**
A: It has no single leader requiring majority agreement — ANY replica can
accept a write (quorum-based, `W` out of `N`), and hinted handoff lets writes
succeed even when a specific replica is temporarily unreachable. This
sacrifices immediate consistency (AP over CP in CAP terms) for availability.

**Q: What does `W + R > N` actually guarantee, and what doesn't it guarantee?**
A: It guarantees any read set and any write set share at least one common
replica, so a read is guaranteed to SEE the latest acknowledged write
(assuming correct conflict resolution via timestamps/vector clocks). It does
NOT guarantee linearizability/strict ordering across concurrent writes —
just that stale data isn't silently returned when W+R>N holds.

**Q: A replica was down for 6 hours — hinted handoff wasn't enough. What repairs it?**
A: Anti-entropy — a background process comparing Merkle tree hashes between
replicas, isolating exactly which keys differ (not a full data scan), and
repairing just those. This is what makes "eventually consistent" systems
eventually actually converge, beyond what hinted handoff alone covers for
short outages.

---

Related: [08_CAP_Theorem.md](08_CAP_Theorem.md) (the AP tradeoff this whole
family embodies), [46_Vector_Clocks_CRDTs.md](46_Vector_Clocks_CRDTs.md)
(conflict resolution during quorum reads), [62_Raft_Paxos_Consensus.md](62_Raft_Paxos_Consensus.md)
(the leader-based alternative family this contrasts with).
