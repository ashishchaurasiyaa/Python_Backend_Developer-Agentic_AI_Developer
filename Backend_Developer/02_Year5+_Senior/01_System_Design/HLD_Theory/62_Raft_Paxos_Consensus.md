# Raft & Paxos — Distributed Consensus

## What is Consensus?
In a distributed system, multiple nodes must agree on a single value (who is leader, what value to commit) even when some nodes fail.

---

## Why Consensus is Hard
- Nodes can crash at any time
- Network can drop or delay messages
- Can't distinguish "node is slow" from "node is dead"
- FLP Impossibility: no deterministic algorithm can guarantee consensus in async network with even 1 faulty node

Both Raft and Paxos solve this with: **majority quorum** (need > N/2 nodes to agree)

---

# PAXOS

The original consensus algorithm (Leslie Lamport, 1989). Powerful but complex to understand and implement.

## Roles
- **Proposer:** Proposes a value
- **Acceptor:** Votes on proposals
- **Learner:** Learns the final decided value

## Two Phases

### Phase 1 — Prepare
```
Proposer ──► all Acceptors: "Prepare(n)" [n = proposal number]
Acceptors ──► "Promise not to accept any proposal < n"
           + "Here is the highest proposal I already accepted"
```

### Phase 2 — Accept
```
Proposer ──► all Acceptors: "Accept(n, value)"
Acceptors ──► accept if n >= their promised n
Proposer waits for majority → value is chosen
```

## Problem with Paxos
- Hard to implement correctly
- Multi-Paxos (for log replication) is even more complex
- No clear leader = livelock possible (two proposers keep outbidding each other)

---

# RAFT

Raft (Diego Ongaro, 2014) — designed to be understandable. Same guarantees as Paxos, much cleaner.

## Roles
- **Leader:** Handles all writes, sends heartbeats
- **Follower:** Responds to leader
- **Candidate:** Trying to become leader (during election)

## Key Concepts

### 1. Leader Election
```
All nodes start as Followers
If no heartbeat from leader within timeout → become Candidate
Candidate votes for itself → sends RequestVote to all
If majority votes → becomes Leader
Leader sends heartbeats to maintain authority
```

```
Node A (Leader)  ──heartbeat──► Node B (Follower)
                 ──heartbeat──► Node C (Follower)

Node A crashes →
Node B timeout → becomes Candidate → votes for itself
                 RequestVote ──► Node C → Node C votes Yes
Node B wins majority (2/3) → becomes new Leader
```

### 2. Log Replication
```
Client ──► Leader: "set x=5"
Leader ──► appends to its log: [index=42, term=3, cmd="set x=5"]
Leader ──► AppendEntries ──► Follower B, Follower C
Followers append to their logs → reply OK
Leader gets majority ACK → commits entry
Leader ──► notifies Followers: "commit index 42"
Followers commit
```

### 3. Terms
Each election = new term number. Terms are like logical clocks.
Node with stale term immediately reverts to Follower.

## Safety Guarantee
- At most one leader per term
- Committed entries never lost (leader always has most up-to-date log)
- Majority (quorum) required for any decision

---

## Raft vs Paxos

| | Raft | Paxos |
|--|------|-------|
| Understandability | High | Low |
| Performance | Similar | Similar |
| Leader | Explicit | Not required |
| Used in | etcd, CockroachDB, TiKV | Google Chubby, Zookeeper (ZAB) |

---

## Real World Usage

| System | Algorithm |
|--------|-----------|
| etcd (Kubernetes backbone) | Raft |
| CockroachDB | Raft |
| TiKV | Raft |
| Google Chubby | Paxos |
| Apache Zookeeper | ZAB (Paxos variant) |
| Google Spanner | Paxos |

---

## When Does This Come Up in Interviews?

Usually for senior roles at Google, Uber, Stripe, or when designing:
- Distributed lock service
- Leader election in your system design
- "How does your system handle split-brain?"

---

## Interview Tip
> "For leader election we use Raft — it requires a majority quorum so in a 5-node cluster we can tolerate 2 failures. Each term has exactly one leader. etcd uses Raft and we use etcd for distributed locking and config management in our cluster."
