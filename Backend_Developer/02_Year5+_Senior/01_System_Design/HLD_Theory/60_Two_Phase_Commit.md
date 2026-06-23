# Two-Phase Commit (2PC)

## Problem
How do you ensure all nodes in a distributed system either ALL commit or ALL rollback a transaction?

---

## What is 2PC?
A distributed consensus protocol with a **Coordinator** and multiple **Participants**.
Guarantees atomicity across distributed nodes.

---

## Two Phases

### Phase 1 — Prepare (Voting)
```
Coordinator ──► Participant A: "Can you commit?"
Coordinator ──► Participant B: "Can you commit?"
Coordinator ──► Participant C: "Can you commit?"

Participant A ──► "Yes (vote commit)"
Participant B ──► "Yes (vote commit)"
Participant C ──► "No (vote abort)"    ← one no = everyone aborts
```

Each participant:
- Acquires locks
- Writes to WAL (write-ahead log)
- Replies YES or NO

### Phase 2 — Commit / Abort
```
If ALL voted YES:
  Coordinator ──► all: "COMMIT"
  All participants commit + release locks

If ANY voted NO:
  Coordinator ──► all: "ABORT"
  All participants rollback + release locks
```

---

## Timeline Diagram

```
Coordinator        Part A        Part B
    │                │              │
    │── Prepare ────►│── Prepare ──►│
    │◄── Yes ────────│◄── Yes ──────│
    │                │              │
    │── Commit ──────►── Commit ───►│
    │◄── Ack ─────────◄── Ack ──────│
    │                │              │
   Done
```

---

## Problems with 2PC

### 1. Blocking Protocol
If coordinator crashes after Phase 1, participants hold locks forever waiting.

### 2. Single Point of Failure
Coordinator going down = system stuck.

### 3. High Latency
2 round trips for every transaction. Bad for high throughput systems.

---

## Write-Ahead Log (WAL)
Before any participant votes YES, it writes the transaction to WAL.
This ensures it can recover and commit/rollback even after a crash.

```
WAL entry: [txn_id=123, state=PREPARED, data=...]
On recovery: check WAL → finish the transaction
```

---

## 2PC vs 3PC

| | 2PC | 3PC |
|--|-----|-----|
| Phases | 2 | 3 |
| Blocking | Yes | No (timeout-based) |
| Complexity | Medium | High |
| Used in practice | Yes | Rarely |

---

## When is 2PC Used?

✅ Single database cluster with distributed nodes
✅ XA transactions (Java EE, .NET distributed TX)
✅ When strong consistency is non-negotiable

❌ Not suitable for microservices across different DBs → use Saga instead
❌ Not for high-throughput systems → too slow

---

## Real World
- **PostgreSQL / MySQL:** Supports XA (2PC) within a DB cluster
- **Google Spanner:** Uses 2PC internally with Paxos for consensus
- **Banks:** Core banking systems use 2PC for ledger consistency

---

## Interview Tip
> "2PC gives strong consistency but is blocking — if the coordinator fails, participants hold locks. In microservices we prefer Saga with compensating transactions for better availability. 2PC is fine within a single DB cluster."
