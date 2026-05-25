# 19 — Memento Pattern

> Behavioral pattern. Captures an object's internal state so it can be restored later, without violating encapsulation.

---

## When to use

- You need undo/redo functionality.
- You need to snapshot state for rollback (transactions, checkpoints).
- You want to save/restore game state, document drafts, configuration changes.
- You need to externalize state without breaking encapsulation.

---

## Structure

```
┌─────────────┐    creates    ┌──────────────┐
│  Originator │ ────────────► │   Memento    │
│             │               │              │
│ + save()    │ ◄─restores──  │ (private    │
│ + restore() │               │  state)      │
└─────────────┘               └──────────────┘
       ▲
       │ uses
       │
┌──────┴──────┐
│  Caretaker  │
│             │
│ + history[] │
│ + undo()    │
└─────────────┘
```

- **Originator**: object whose state we save/restore.
- **Memento**: opaque snapshot of state.
- **Caretaker**: keeps mementos, decides when to restore.

The Caretaker never inspects the Memento's contents — that would break encapsulation.

---

## Implementation — Text Editor with Undo

```python
from copy import deepcopy

class EditorMemento:
    """Snapshot of editor state. Opaque to outside."""
    def __init__(self, content: str, cursor_pos: int):
        self._content = content
        self._cursor_pos = cursor_pos

    # No public getters — only Originator should read this.
    # In Python, we trust convention. In Java, package-private.


class Editor:
    """Originator: the thing we want to undo/redo."""
    def __init__(self):
        self.content = ""
        self.cursor_pos = 0

    def write(self, text: str):
        self.content = (
            self.content[:self.cursor_pos] + text + self.content[self.cursor_pos:]
        )
        self.cursor_pos += len(text)

    def move_cursor(self, pos: int):
        self.cursor_pos = max(0, min(pos, len(self.content)))

    def save(self) -> EditorMemento:
        return EditorMemento(self.content, self.cursor_pos)

    def restore(self, memento: EditorMemento):
        self.content = memento._content
        self.cursor_pos = memento._cursor_pos

    def __repr__(self):
        return f"Editor(content={self.content!r}, cursor={self.cursor_pos})"


class History:
    """Caretaker: holds the snapshots."""
    def __init__(self, editor: Editor, max_size: int = 50):
        self.editor = editor
        self.snapshots: list[EditorMemento] = []
        self.max_size = max_size

    def backup(self):
        self.snapshots.append(self.editor.save())
        if len(self.snapshots) > self.max_size:
            self.snapshots.pop(0)

    def undo(self):
        if not self.snapshots:
            return
        memento = self.snapshots.pop()
        self.editor.restore(memento)


# Usage
editor = Editor()
history = History(editor)

history.backup()
editor.write("Hello")        # "Hello"

history.backup()
editor.write(" World")       # "Hello World"

history.backup()
editor.write("!")            # "Hello World!"

history.undo()               # "Hello World"
history.undo()               # "Hello"
history.undo()               # ""
```

---

## Variants

### Memento with redo support

```python
class History:
    def __init__(self, editor):
        self.editor = editor
        self.undo_stack: list[EditorMemento] = []
        self.redo_stack: list[EditorMemento] = []

    def backup(self):
        self.undo_stack.append(self.editor.save())
        self.redo_stack.clear()    # new branch invalidates redo

    def undo(self):
        if not self.undo_stack: return
        self.redo_stack.append(self.editor.save())
        self.editor.restore(self.undo_stack.pop())

    def redo(self):
        if not self.redo_stack: return
        self.undo_stack.append(self.editor.save())
        self.editor.restore(self.redo_stack.pop())
```

### Memento with command pattern (sketch)
Often combined: each command creates a memento; undo restores it.

---

## Memory Optimization

### Snapshotting full state is expensive

If state is large (e.g., 1MB document):
- 50 undos × 1MB = 50MB just for history.

### Solutions

**1. Store diffs, not full state**
```python
class EditMemento:
    def __init__(self, op_type, position, content):
        self.op_type = op_type   # 'insert', 'delete'
        self.position = position
        self.content = content   # what was inserted/deleted

class Editor:
    def undo(self, memento):
        if memento.op_type == 'insert':
            # Reverse: delete what was inserted
            self.content = self.content[:memento.position] + self.content[memento.position + len(memento.content):]
        elif memento.op_type == 'delete':
            # Reverse: re-insert
            self.content = self.content[:memento.position] + memento.content + self.content[memento.position:]
```

**2. Use immutable structures with structural sharing (e.g., persistent data structures)**
- Functional languages (Clojure) use this natively.
- Python: `pyrsistent` library.

**3. Compress old snapshots**
```python
import gzip, pickle
def compress(memento):
    return gzip.compress(pickle.dumps(memento))
```

---

## Memento vs Pickle/Serialization

Python's pickle / serialization can save objects too. Differences:

| Pickle | Memento |
|---|---|
| Generic | Domain-specific |
| Inspects internals | Encapsulated |
| Versioning fragile | Designed for evolution |
| File / network use | In-memory typically |

**Memento** isn't about persistence — it's about runtime save/restore with encapsulation.

---

## Real-World Examples

### Text Editors
VS Code, Word — undo/redo stack.

### Image Editors
Photoshop has "history palette" of mementos.

### Game Save Files
Each save = memento of game state (player position, inventory, world state).

### Database Transactions
Postgres internal: undo log = essentially memento-style snapshots.

### Configuration Rollback
Kubernetes deployment rollback: stores previous ReplicaSet specs (mementos).

### Browser Back Button
Each page navigation snapshot.

### Spreadsheet Apps
Undo cell changes — Excel stores delta-style mementos.

---

## Memento with Persistence

For very long undo history, persist mementos to disk:

```python
class PersistentHistory:
    def __init__(self, editor, db):
        self.editor = editor
        self.db = db

    async def backup(self):
        m = self.editor.save()
        await self.db.execute(
            "INSERT INTO history (timestamp, snapshot) VALUES (now(), $1)",
            pickle.dumps(m)
        )

    async def undo_n(self, n=1):
        row = await self.db.fetchrow(
            "SELECT snapshot FROM history ORDER BY timestamp DESC LIMIT 1 OFFSET $1",
            n - 1
        )
        if row:
            m = pickle.loads(row['snapshot'])
            self.editor.restore(m)
```

---

## Trade-offs

### Pros
- ✓ Clean separation of state from logic.
- ✓ Enables undo/redo.
- ✓ Encapsulation preserved.

### Cons
- ✗ Memory: full snapshots can be expensive.
- ✗ Caretaker must know when to backup (or hook every mutation).
- ✗ Hard to apply to objects with external resources (file handles, sockets).

---

## When NOT to use

- State is trivial (e.g., one int) — overkill.
- State changes are very frequent + state is large — memory issue.
- Object has uncopyable resources (open files, sockets, DB connections).

---

## Memento + Command Pattern

Common combination: each command knows how to undo itself, storing pre-state as memento.

```python
class Command:
    def execute(self): pass
    def undo(self): pass

class InsertTextCommand(Command):
    def __init__(self, editor, text):
        self.editor = editor
        self.text = text
        self.memento_before = None

    def execute(self):
        self.memento_before = self.editor.save()
        self.editor.write(self.text)

    def undo(self):
        self.editor.restore(self.memento_before)

class CommandHistory:
    def __init__(self):
        self.history = []

    def execute(self, cmd):
        cmd.execute()
        self.history.append(cmd)

    def undo(self):
        if self.history:
            self.history.pop().undo()
```

---

## Memento with Snapshot Diff

For "git-like" version control of an object:

```python
class VersionedDoc:
    def __init__(self, content=""):
        self.content = content
        self.versions = []

    def commit(self, message: str):
        self.versions.append({
            "id": uuid.uuid4(),
            "parent": self.versions[-1]["id"] if self.versions else None,
            "snapshot": self.content,
            "message": message,
            "ts": time.time()
        })

    def checkout(self, version_id):
        for v in self.versions:
            if v["id"] == version_id:
                self.content = v["snapshot"]
                return
        raise NotFound()
```

---

## Concurrency Considerations

If multiple threads modify the originator:
- Memento creation must be atomic (lock during snapshot).
- Better: use immutable data so snapshot is just a reference.

```python
import copy
from threading import Lock

class ThreadSafeEditor:
    def __init__(self):
        self.content = ""
        self.lock = Lock()

    def save(self):
        with self.lock:
            return EditorMemento(copy.deepcopy(self.content), self.cursor_pos)
```

---

## Testing

```python
def test_undo_restores_state():
    e = Editor()
    e.write("Hello")
    m = e.save()
    e.write(" World")
    e.restore(m)
    assert e.content == "Hello"
    assert e.cursor_pos == 5
```

Easy to test — memento is just a value object.

---

## TL;DR

- Memento = state snapshot, opaque from outside.
- Originator creates + restores from memento.
- Caretaker stores list of mementos for undo/redo.
- For large state: store diffs, not full snapshots.
- Combine with Command pattern for industrial-strength undo.
- **Use in:** editors, games, transactions, config systems.
