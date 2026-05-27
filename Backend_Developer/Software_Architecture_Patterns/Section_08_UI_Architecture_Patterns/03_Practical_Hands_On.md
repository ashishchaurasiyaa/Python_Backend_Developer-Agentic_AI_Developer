# Lecture 3 — Practical Hands-On: Offline-First & Sync

> **Theory file:** [03_Offline_First_Sync.md](03_Offline_First_Sync.md)

---

## 🎯 Is Practical Mein Kya Banayenge?

1. ✅ **Local SQLite cache** with versioning
2. ✅ **Outbox sync queue** with retries + exponential backoff
3. ✅ **Mock server** to simulate network failures
4. ✅ **Conflict detection + resolution** (LWW + merge + manual)
5. ✅ **Idempotency keys** for safe retries
6. ✅ **Background sync worker** (asyncio)
7. ✅ **End-to-end offline chat-like demo**

By end: aap ek offline-capable client banao jo network drops survive kare bina data loss ke.

---

## 1. Project Structure

```
offline_first_demo/
├── client/
│   ├── db.py              # SQLite cache with versions
│   ├── outbox.py          # Sync queue
│   ├── sync_worker.py     # Background sync
│   └── conflict.py        # Resolution strategies
├── server/
│   ├── mock_server.py     # Flaky server simulation
│   └── idempotency.py
├── tests/
│   └── test_sync_flow.py
└── demo.py
```

---

## 2. 🗄 Local Cache with Versioning

### `client/db.py`

```python
import sqlite3
import time
import uuid


SCHEMA = """
CREATE TABLE IF NOT EXISTS todos (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    done INTEGER NOT NULL DEFAULT 0,
    version INTEGER NOT NULL DEFAULT 1,
    updated_at REAL NOT NULL,
    synced INTEGER NOT NULL DEFAULT 0
);
"""


class LocalDB:
    def __init__(self, path: str = "client.db"):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def upsert(self, todo: dict):
        now = time.time()
        self.conn.execute(
            """
            INSERT INTO todos (id, title, done, version, updated_at, synced)
            VALUES (?, ?, ?, ?, ?, 0)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                done = excluded.done,
                version = todos.version + 1,
                updated_at = excluded.updated_at,
                synced = 0
            """,
            (
                todo["id"],
                todo["title"],
                int(todo["done"]),
                todo.get("version", 1),
                now,
            ),
        )
        self.conn.commit()

    def create(self, title: str) -> dict:
        todo = {
            "id": str(uuid.uuid4()),
            "title": title,
            "done": False,
            "version": 1,
        }
        self.upsert(todo)
        return todo

    def all(self) -> list[dict]:
        cur = self.conn.execute("SELECT * FROM todos ORDER BY updated_at")
        return [dict(r) for r in cur]

    def get(self, id: str) -> dict | None:
        cur = self.conn.execute("SELECT * FROM todos WHERE id = ?", (id,))
        row = cur.fetchone()
        return dict(row) if row else None

    def mark_synced(self, id: str, server_version: int):
        self.conn.execute(
            "UPDATE todos SET synced = 1, version = ? WHERE id = ?",
            (server_version, id),
        )
        self.conn.commit()

    def unsynced(self) -> list[dict]:
        cur = self.conn.execute("SELECT * FROM todos WHERE synced = 0")
        return [dict(r) for r in cur]
```

---

## 3. 📬 Outbox Sync Queue

### `client/outbox.py`

```python
import sqlite3
import json
import time
import uuid


SCHEMA = """
CREATE TABLE IF NOT EXISTS outbox (
    id TEXT PRIMARY KEY,
    op TEXT NOT NULL,
    entity TEXT NOT NULL,
    payload TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    created_at REAL NOT NULL,
    retries INTEGER NOT NULL DEFAULT 0,
    last_error TEXT
);
"""


class Outbox:
    def __init__(self, path: str = "outbox.db"):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def enqueue(self, op: str, entity: str, payload: dict) -> str:
        item_id = str(uuid.uuid4())
        self.conn.execute(
            """
            INSERT INTO outbox (id, op, entity, payload, idempotency_key, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                item_id,
                op,
                entity,
                json.dumps(payload),
                str(uuid.uuid4()),  # idempotency key
                time.time(),
            ),
        )
        self.conn.commit()
        return item_id

    def pending(self) -> list[dict]:
        cur = self.conn.execute(
            "SELECT * FROM outbox ORDER BY created_at"
        )
        return [
            {**dict(r), "payload": json.loads(r["payload"])}
            for r in cur
        ]

    def mark_done(self, id: str):
        self.conn.execute("DELETE FROM outbox WHERE id = ?", (id,))
        self.conn.commit()

    def mark_failed(self, id: str, error: str):
        self.conn.execute(
            "UPDATE outbox SET retries = retries + 1, last_error = ? WHERE id = ?",
            (error, id),
        )
        self.conn.commit()
```

---

## 4. 🌐 Mock Server (Flaky)

### `server/mock_server.py`

```python
import random
import time
from collections import defaultdict


class FlakyServer:
    """Simulates network failures + idempotency."""

    def __init__(self, fail_rate: float = 0.4):
        self.store: dict = {}           # id → todo
        self.versions: dict = defaultdict(int)
        self.seen_idempotency_keys: set = set()
        self.fail_rate = fail_rate

    def _maybe_fail(self):
        if random.random() < self.fail_rate:
            raise ConnectionError("Network blip")
        time.sleep(0.01)  # simulate latency

    def upsert_todo(self, payload: dict, idempotency_key: str) -> dict:
        self._maybe_fail()

        # idempotency check — return same result if seen
        if idempotency_key in self.seen_idempotency_keys:
            id_ = payload["id"]
            return {
                "id": id_,
                **self.store.get(id_, payload),
                "version": self.versions[id_],
                "duplicate": True,
            }

        self.seen_idempotency_keys.add(idempotency_key)
        id_ = payload["id"]
        client_version = payload.get("version", 1)
        server_version = self.versions[id_]

        # Conflict detection: server has newer version
        if server_version > client_version:
            return {
                "conflict": True,
                "server": {**self.store[id_], "version": server_version},
                "client": payload,
            }

        new_version = max(server_version, client_version) + 1
        self.store[id_] = {**payload, "version": new_version}
        self.versions[id_] = new_version
        return {**self.store[id_], "version": new_version}
```

---

## 5. ⚖️ Conflict Resolution

### `client/conflict.py`

```python
def last_write_wins(client: dict, server: dict) -> dict:
    """Pick the one with the higher updated_at."""
    if client.get("updated_at", 0) >= server.get("updated_at", 0):
        return client
    return server


def merge_fields(client: dict, server: dict) -> dict:
    """Merge non-overlapping fields. Server wins on shared fields."""
    merged = dict(server)
    for k, v in client.items():
        if k not in server or server[k] in (None, ""):
            merged[k] = v
    return merged


def manual_prompt(client: dict, server: dict) -> dict:
    """Stub for UI prompt — here we just print and pick client."""
    print(f"⚠ CONFLICT:\n  client: {client}\n  server: {server}")
    print("  → user picks CLIENT (in real app, UI would ask)")
    return client
```

---

## 6. 🔄 Background Sync Worker

### `client/sync_worker.py`

```python
import asyncio
import random
from .db import LocalDB
from .outbox import Outbox
from .conflict import last_write_wins


class SyncWorker:
    def __init__(self, db: LocalDB, outbox: Outbox, server):
        self.db = db
        self.outbox = outbox
        self.server = server
        self.running = False

    async def run(self):
        self.running = True
        while self.running:
            await self._sync_once()
            await asyncio.sleep(2)

    async def _sync_once(self):
        for item in self.outbox.pending():
            backoff = min(2 ** item["retries"], 30)  # capped exponential
            if item["retries"] > 0:
                await asyncio.sleep(backoff + random.uniform(0, 1))

            try:
                result = self.server.upsert_todo(
                    item["payload"], item["idempotency_key"]
                )

                if result.get("conflict"):
                    resolved = last_write_wins(result["client"], result["server"])
                    # write resolved version back
                    self.db.upsert(resolved)
                    # try sync again with merged version (new idem key would be needed in prod)
                    self.outbox.mark_failed(item["id"], "conflict resolved, retrying")
                    continue

                self.db.mark_synced(item["payload"]["id"], result["version"])
                self.outbox.mark_done(item["id"])
                print(f"✓ synced {item['payload']['id'][:8]} (v{result['version']})")

            except ConnectionError as e:
                self.outbox.mark_failed(item["id"], str(e))
                print(f"✗ retry later: {item['payload']['id'][:8]} ({e})")

    def stop(self):
        self.running = False
```

---

## 7. 🎬 End-to-End Demo

### `demo.py`

```python
import asyncio
import os
import time

from client.db import LocalDB
from client.outbox import Outbox
from client.sync_worker import SyncWorker
from server.mock_server import FlakyServer


async def user_actions(db: LocalDB, outbox: Outbox):
    """Simulate user creating todos offline."""
    titles = ["Buy milk", "Call mom", "Finish report", "Go run"]
    for t in titles:
        todo = db.create(t)
        outbox.enqueue("upsert", "todo", todo)
        print(f"📝 created locally: {t}")
        await asyncio.sleep(1)


async def main():
    # clean slate
    for f in ("client.db", "outbox.db"):
        if os.path.exists(f):
            os.remove(f)

    db = LocalDB("client.db")
    outbox = Outbox("outbox.db")
    server = FlakyServer(fail_rate=0.5)
    worker = SyncWorker(db, outbox, server)

    # run user actions + sync worker concurrently
    sync_task = asyncio.create_task(worker.run())
    await user_actions(db, outbox)

    # Let sync catch up
    print("\n⏳ Letting sync catch up for 30s...")
    await asyncio.sleep(30)

    worker.stop()
    sync_task.cancel()

    print("\n=== Final state ===")
    for t in db.all():
        synced = "✓" if t["synced"] else "✗"
        print(f"  {synced} {t['title']} (v{t['version']})")

    pending = outbox.pending()
    if pending:
        print(f"\n⚠ {len(pending)} items still pending in outbox")


if __name__ == "__main__":
    asyncio.run(main())
```

### Run

```bash
cd offline_first_demo
python demo.py
```

### What You Should See

```
📝 created locally: Buy milk
✗ retry later: a1b2c3d4 (Network blip)
📝 created locally: Call mom
✓ synced a1b2c3d4 (v1)
✗ retry later: e5f6g7h8 (Network blip)
...
=== Final state ===
  ✓ Buy milk (v1)
  ✓ Call mom (v1)
  ✓ Finish report (v1)
  ✓ Go run (v1)
```

---

## 8. 🧪 Tests

### `tests/test_sync_flow.py`

```python
import os
import pytest
import asyncio

from client.db import LocalDB
from client.outbox import Outbox
from client.sync_worker import SyncWorker
from server.mock_server import FlakyServer


@pytest.fixture
def fresh_env(tmp_path):
    db = LocalDB(str(tmp_path / "test.db"))
    outbox = Outbox(str(tmp_path / "outbox.db"))
    return db, outbox


def test_local_write_is_instant(fresh_env):
    db, outbox = fresh_env
    todo = db.create("Test")
    assert db.get(todo["id"]) is not None  # immediately readable
    assert todo["id"] in [t["id"] for t in db.all()]


def test_outbox_persists_changes(fresh_env):
    db, outbox = fresh_env
    todo = db.create("X")
    outbox.enqueue("upsert", "todo", todo)
    assert len(outbox.pending()) == 1


def test_idempotency_on_retry():
    server = FlakyServer(fail_rate=0.0)
    payload = {"id": "abc", "title": "Hi", "done": False, "version": 1}
    key = "fixed-key"
    r1 = server.upsert_todo(payload, key)
    r2 = server.upsert_todo(payload, key)
    # Second call is recognized as duplicate
    assert r2.get("duplicate") is True
    # Version did NOT increment from the duplicate
    assert r1["version"] == r2["version"]


@pytest.mark.asyncio
async def test_sync_eventually_succeeds(fresh_env, tmp_path):
    db, outbox = fresh_env
    server = FlakyServer(fail_rate=0.3)  # 30% failure
    worker = SyncWorker(db, outbox, server)

    for t in ("A", "B", "C"):
        todo = db.create(t)
        outbox.enqueue("upsert", "todo", todo)

    task = asyncio.create_task(worker.run())
    await asyncio.sleep(20)
    worker.stop()
    task.cancel()

    assert len(outbox.pending()) == 0  # all eventually synced
    assert all(t["synced"] for t in db.all())
```

---

## 9. ✅ Hands-On Checklist

```
□ Local SQLite cache with versioning works
□ Outbox queue persists changes across restarts
□ Mock server returns failures + recovers
□ Idempotency key prevents duplicate writes
□ Exponential backoff actually backs off (no log spam)
□ Conflict resolution triggers on version mismatch
□ Final state: all items synced, outbox empty
```

---

## 🔗 Next

- Next: [04_Selecting_UI_Patterns_By_Platform.md](04_Selecting_UI_Patterns_By_Platform.md)
