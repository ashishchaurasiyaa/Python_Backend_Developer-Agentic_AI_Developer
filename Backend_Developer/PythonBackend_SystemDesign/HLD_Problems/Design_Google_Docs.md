# Design Google Docs (Real-time Collaborative Editor)

---

## 1. Requirements

### Functional
- Create, read, update, delete documents
- Real-time collaborative editing (multiple simultaneous editors)
- Cursor/selection sync across editors
- Version history (named snapshots, restore any version)
- Comments and suggestions
- Offline editing with sync on reconnect
- Sharing (view/comment/edit permissions)

### Non-Functional
- 1B+ users, 10M concurrent documents
- < 50ms operation sync latency between editors
- 99.99% uptime
- Infinite version history
- Conflict-free convergence (all editors see same final state)

---

## 2. Scale Estimation

| Metric | Calculation | Result |
|--------|-------------|--------|
| Concurrent editors/doc | Average 3, peak 100+ | 3–100 |
| Ops/sec system-wide | 10M docs × 3 editors × 5 ops/sec | ~150M ops/sec |
| Operation size | ~50 bytes JSON | 7.5 GB/sec raw |
| Storage (ops log) | Cassandra, compressed | ~50 TB/day |
| Snapshot storage (S3) | Every 1000 ops, avg 10KB | ~15 GB/day |

---

## 3. Architecture Diagram

```
  Clients (Browser/App)
       │  WebSocket
       ▼
┌─────────────────────────────────────────────────┐
│              WebSocket Gateway                   │
│         (sticky sessions, Redis pub/sub)         │
└──────────────────────┬──────────────────────────┘
                       │
          ┌────────────▼────────────┐
          │    Collaboration        │
          │    Service              │
          │  (OT Server, per-doc)   │
          └────────────┬────────────┘
               ┌───────┴────────┐
               │                │
       ┌───────▼──────┐  ┌──────▼──────────┐
       │  Op Log       │  │   Snapshot       │
       │  (Cassandra)  │  │   Service (S3)   │
       └───────────────┘  └─────────────────┘
                                │
                    ┌───────────▼──────────┐
                    │   Version History     │
                    │   (PostgreSQL)        │
                    └──────────────────────┘
```

---

## 4. Core Algorithm: Operational Transformation (OT)

### Why OT?
When two users edit simultaneously, their operations conflict. OT transforms operations so that applying them in any order produces the same result.

```
User A (pos 5): INSERT 'X'
User B (pos 3): INSERT 'Y'

Without OT:
  A applies B's op → INSERT 'Y' at 3 → correct
  B applies A's op → INSERT 'X' at 5 → correct
  ✅ No conflict here

With conflict:
User A (pos 3): INSERT 'X'
User B (pos 3): DELETE 1 char

B applied first → A's INSERT 'X' at 3 still correct
A applied first → B's DELETE must shift: DELETE at 4 (after X was inserted)
OT handles this shift automatically.
```

### Operation Model

```python
from dataclasses import dataclass, field
from typing import Literal, Optional
from enum import Enum

class OpType(str, Enum):
    INSERT = "insert"
    DELETE = "delete"
    RETAIN = "retain"

@dataclass
class Op:
    """Atomic operation on document."""
    type: OpType
    position: int         # 0-indexed position in document
    char: str = ""        # for INSERT
    length: int = 1       # for DELETE (how many chars to remove)
    author_id: str = ""
    timestamp: float = 0.0

@dataclass
class ChangeSet:
    """A list of ops representing one edit (like a diff)."""
    ops: list[Op] = field(default_factory=list)
    revision: int = 0     # server revision this was based on
    client_id: str = ""
```

### OT Transform Functions

```python
def transform(op1: Op, op2: Op) -> Optional[Op]:
    """
    Transform op1 assuming op2 was already applied.
    Returns adjusted op1 (or None if op1 is now a no-op).
    """
    if op1.type == OpType.INSERT and op2.type == OpType.INSERT:
        if op2.position < op1.position:
            return Op(op1.type, op1.position + 1, op1.char, author_id=op1.author_id)
        if op2.position == op1.position and op2.author_id < op1.author_id:
            # Tie-break by author_id for determinism
            return Op(op1.type, op1.position + 1, op1.char, author_id=op1.author_id)
        return op1

    if op1.type == OpType.INSERT and op2.type == OpType.DELETE:
        if op2.position < op1.position:
            return Op(op1.type, op1.position - 1, op1.char, author_id=op1.author_id)
        return op1

    if op1.type == OpType.DELETE and op2.type == OpType.INSERT:
        if op2.position <= op1.position:
            return Op(op1.type, op1.position + 1, author_id=op1.author_id)
        return op1

    if op1.type == OpType.DELETE and op2.type == OpType.DELETE:
        if op2.position < op1.position:
            return Op(op1.type, op1.position - 1, author_id=op1.author_id)
        if op2.position == op1.position:
            return None  # already deleted by op2
        return op1

    return op1
```

### OT Server (Central Authority)

```python
import asyncio
from typing import Optional

class OTServer:
    """
    Single source of truth for operation ordering.
    All clients send ops here; server transforms and broadcasts.
    One OTServer instance per document.
    """
    def __init__(self, doc_id: str):
        self.doc_id = doc_id
        self.history: list[Op] = []        # ordered list of all applied ops
        self.document: list[str] = []      # current document state
        self.lock = asyncio.Lock()

    async def submit_op(self, op: Op, client_revision: int) -> Optional[Op]:
        """
        Client submits an op based on their known revision.
        Server transforms against ops since that revision, applies, broadcasts.
        """
        async with self.lock:  # serialize all op submissions
            server_revision = len(self.history)
            transformed = op

            # Transform against all ops that happened since client's revision
            for server_op in self.history[client_revision:]:
                transformed = transform(transformed, server_op)
                if transformed is None:
                    return None   # op was neutralized

            # Apply to document
            self._apply(transformed)
            self.history.append(transformed)

            return transformed   # return for broadcasting

    def _apply(self, op: Op) -> None:
        if op.type == OpType.INSERT:
            self.document.insert(op.position, op.char)
        elif op.type == OpType.DELETE:
            if op.position < len(self.document):
                del self.document[op.position:op.position + op.length]

    def get_content(self) -> str:
        return "".join(self.document)

    def get_revision(self) -> int:
        return len(self.history)

    async def get_ops_since(self, revision: int) -> list[Op]:
        return self.history[revision:]
```

---

## 5. OT vs CRDT Comparison

| | Operational Transformation | CRDT |
|---|---|---|
| **Approach** | Transform conflicting ops centrally | Data structure guarantees convergence |
| **Convergence** | Via central server ordering | Via algebraic properties |
| **Complexity** | Complex transform functions, correctness hard to prove | Complex data structure, simpler reasoning |
| **Used by** | Google Docs, Etherpad | Notion, Figma, Apple Notes |
| **Offline support** | Difficult (need server to order) | Natural (merge anytime) |
| **Performance** | O(n) transform per op | O(log n) typical for tree CRDTs |
| **Implementation** | Well-understood for text | LSEQ/Logoot are complex |

---

## 6. WebSocket Collaboration Layer

```python
from fastapi import WebSocket, WebSocketDisconnect
from typing import dict
import json, asyncio

class DocumentSession:
    """
    Manages all WebSocket connections for one document.
    One instance per active document.
    """
    def __init__(self, doc_id: str, ot_server: OTServer):
        self.doc_id = doc_id
        self.ot_server = ot_server
        self.clients: dict[str, WebSocket] = {}       # user_id → ws
        self.cursors: dict[str, dict] = {}             # user_id → cursor_pos

    async def connect(self, user_id: str, ws: WebSocket):
        await ws.accept()
        self.clients[user_id] = ws
        # Send current state to new client
        await ws.send_json({
            "type": "init",
            "content": self.ot_server.get_content(),
            "revision": self.ot_server.get_revision(),
            "cursors": self.cursors,
            "online_users": list(self.clients.keys())
        })
        # Notify others of new user
        await self.broadcast({
            "type": "user_joined",
            "user_id": user_id
        }, exclude=user_id)

    async def disconnect(self, user_id: str):
        self.clients.pop(user_id, None)
        self.cursors.pop(user_id, None)
        await self.broadcast({"type": "user_left", "user_id": user_id})

    async def handle_message(self, user_id: str, data: dict):
        msg_type = data.get("type")

        if msg_type == "op":
            op = Op(
                type=OpType(data["op"]["type"]),
                position=data["op"]["position"],
                char=data["op"].get("char", ""),
                length=data["op"].get("length", 1),
                author_id=user_id
            )
            client_revision = data["revision"]
            transformed = await self.ot_server.submit_op(op, client_revision)

            if transformed:
                # Broadcast transformed op to all OTHER clients
                await self.broadcast({
                    "type": "op",
                    "op": {
                        "type": transformed.type,
                        "position": transformed.position,
                        "char": transformed.char,
                        "length": transformed.length,
                    },
                    "revision": self.ot_server.get_revision(),
                    "author": user_id
                }, exclude=user_id)

        elif msg_type == "cursor":
            self.cursors[user_id] = data["cursor"]
            await self.broadcast({
                "type": "cursor",
                "user_id": user_id,
                "cursor": data["cursor"]
            }, exclude=user_id)

    async def broadcast(self, msg: dict, exclude: str = None):
        dead = []
        for uid, ws in self.clients.items():
            if uid == exclude: continue
            try:
                await ws.send_json(msg)
            except Exception:
                dead.append(uid)
        for uid in dead:
            await self.disconnect(uid)

# FastAPI WebSocket endpoint
doc_sessions: dict[str, DocumentSession] = {}

async def websocket_endpoint(ws: WebSocket, doc_id: str, user_id: str):
    if doc_id not in doc_sessions:
        ot_server = await load_or_create_ot_server(doc_id)
        doc_sessions[doc_id] = DocumentSession(doc_id, ot_server)

    session = doc_sessions[doc_id]
    await session.connect(user_id, ws)
    try:
        while True:
            data = await ws.receive_json()
            await session.handle_message(user_id, data)
    except WebSocketDisconnect:
        await session.disconnect(user_id)
        if not session.clients:
            await save_ot_server(doc_id, session.ot_server)
            del doc_sessions[doc_id]
```

---

## 7. Storage Architecture

### Operations Log (Cassandra)

```sql
CREATE TABLE document_ops (
    doc_id      TEXT,
    revision    BIGINT,
    op_type     TEXT,
    position    INT,
    char        TEXT,
    length      INT,
    author_id   TEXT,
    created_at  TIMESTAMP,
    PRIMARY KEY ((doc_id), revision)
) WITH CLUSTERING ORDER BY (revision ASC);
```

### Snapshots (S3)
- Every 1000 operations → serialize document state → upload to S3
- `s3://docs-snapshots/{doc_id}/{snapshot_revision}.json.gz`
- On load: find latest snapshot + replay ops since that snapshot

### Version History (PostgreSQL)

```sql
CREATE TABLE document_versions (
    id          BIGSERIAL PRIMARY KEY,
    doc_id      TEXT NOT NULL,
    revision    BIGINT NOT NULL,
    name        TEXT,              -- user-named version (optional)
    snapshot_s3 TEXT,             -- S3 key of snapshot at this revision
    created_by  TEXT,
    created_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE (doc_id, revision)
);
```

### Snapshot Service

```python
import json, gzip
import boto3

s3 = boto3.client('s3')
BUCKET = "docs-snapshots"

class SnapshotService:
    SNAPSHOT_INTERVAL = 1000  # ops

    async def maybe_snapshot(self, doc_id: str, ot_server: OTServer):
        revision = ot_server.get_revision()
        if revision % self.SNAPSHOT_INTERVAL == 0:
            await self.save_snapshot(doc_id, revision, ot_server.get_content())

    async def save_snapshot(self, doc_id: str, revision: int, content: str):
        key = f"{doc_id}/{revision}.json.gz"
        data = json.dumps({"content": content, "revision": revision}).encode()
        compressed = gzip.compress(data)
        s3.put_object(Bucket=BUCKET, Key=key, Body=compressed)

    async def load_document(self, doc_id: str) -> tuple[str, int]:
        """Load latest snapshot and return (content, revision)."""
        # List snapshots, find latest
        resp = s3.list_objects_v2(Bucket=BUCKET, Prefix=f"{doc_id}/")
        if not resp.get('Contents'):
            return "", 0
        latest = max(resp['Contents'], key=lambda x: int(x['Key'].split('/')[-1].split('.')[0]))
        obj = s3.get_object(Bucket=BUCKET, Key=latest['Key'])
        data = json.loads(gzip.decompress(obj['Body'].read()))
        return data['content'], data['revision']
```

---

## 8. Offline Support

```
Client flow when offline:
1. User types → ops queued in IndexedDB (browser local storage)
2. WebSocket disconnected → queue grows locally
3. User reconnects → WebSocket reconnects
4. Client sends all queued ops with last known server revision
5. Server transforms each op against its history since that revision
6. Server sends back transformed ops + current revision
7. Client rebases local state: apply server's transformed ops

Conflict example:
  Client offline at revision 50
  Client: INSERT 'X' at 5 (based on rev 50)
  Server: DELETE at 3 (rev 51), INSERT 'Y' at 7 (rev 52)
  
  On reconnect:
  Server transforms client's INSERT against rev 51, 52
  Result: INSERT 'X' at 4 (after DELETE shifted it)
  Both client and server converge to same state ✅
```

---

## 9. Multi-Node Scaling

```
Challenge: OTServer is stateful (holds history, document state).
           Multiple WebSocket servers need to coordinate.

Solution:
- Consistent hashing: each doc_id → fixed collaboration node
- Sticky WebSocket: all clients for doc X → same collaboration node
- If node dies: reload OT state from Cassandra ops log + S3 snapshot
- Redis pub/sub: broadcast ops between nodes for geo-distributed docs
- CRDT alternative: for simpler ops (presence, cursors) use Redis CRDT structures
```

---

## 10. Interview Questions

**Q1: What is Operational Transformation (OT)?**
> OT is an algorithm that transforms conflicting concurrent operations so they can be applied in any order and produce the same result. When User A inserts at position 5 and User B inserts at position 3 simultaneously, applying B's op first means A's position must shift to 6. OT computes this shift automatically.

**Q2: Why does OT need a central server?**
> OT requires a total ordering of operations. Without a central authority, two clients could receive ops in different orders and diverge. The server serializes all ops, assigns them revision numbers, and transforms incoming ops against the ops that occurred since the client's revision.

**Q3: What is CRDT and how does it differ from OT?**
> CRDT (Conflict-free Replicated Data Type) uses special data structures where concurrent updates automatically converge without a central server. Examples: LSEQ (assigns unique positions to characters), RGA (replicated growable array). CRDTs work naturally offline and in P2P settings but are more complex to implement correctly.

**Q4: How does Google Docs handle network partitions?**
> Client queues ops locally (IndexedDB). On reconnect, sends queued ops with the last known server revision. Server transforms them against everything that happened since, sends the transformed ops back. Client rebases its local state. This is the "three-way merge" concept.

**Q5: How to implement version history without storing full snapshots every time?**
> Store the operations log (Cassandra). Any version = replay ops from the beginning (or from nearest snapshot). Take periodic snapshots every N ops (S3). To restore version V: load snapshot at V₀ ≤ V, replay ops from V₀ to V.

**Q6: How to scale to millions of concurrent documents?**
> Stateless-ish: each collaboration server handles a set of docs via consistent hashing. Doc state is the Cassandra ops log. If a server dies, another loads the doc state from Cassandra. No single server holds all docs in memory simultaneously.

**Q7: How are cursor positions synced?**
> WebSocket messages with type "cursor" containing position data. When a user's cursor moves, it broadcasts to all other editors. Cursor positions must also be transformed when other ops are applied (same transform rules as INSERT ops shift positions).

**Q8: What happens when 100 users edit the same paragraph simultaneously?**
> Each op is transformed against all concurrent ops at the server. With 100 users × 5 ops/sec = 500 ops/sec per doc. Each op transformation is O(k) where k = ops since client's revision. Under high contention, clients accumulate transform debt. Mitigation: snapshot frequently, reject ops older than X revisions.

**Q9: How to implement "Suggesting" mode (like Google Docs track changes)?**
> Suggestions are a special op type that doesn't directly modify the document. They're stored separately and shown with highlighting. Author of suggestion can see it applied; others see the suggestion overlay. Accepting = apply the underlying ops. Rejecting = discard suggestion ops.

**Q10: Why use WebSockets instead of HTTP polling?**
> WebSocket: persistent connection, server pushes ops immediately (~10ms latency). HTTP polling: client asks every 100ms → 100ms latency + 10× unnecessary requests. For real-time collaboration, WebSocket is the only viable option. SSE (Server-Sent Events) works for push but can't receive client ops — would need hybrid with REST for sending ops.
