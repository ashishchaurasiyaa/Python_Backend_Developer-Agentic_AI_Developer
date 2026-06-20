# Memento

## 1. Intent

Capture and externalise an object's internal state — without violating encapsulation — so it can be restored later.

## 2. Problem

You need undo, snapshotting, checkpoints, or "save game". The naive approach (let callers grab fields directly) leaks internals and breaks when the object's shape changes.

## 3. Solution (UML sketch)

```
┌──────────────┐                       ┌──────────────┐
│  Originator  │── creates ───────────>│   Memento    │
├──────────────┤  +save(): Memento     ├──────────────┤
│ state        │                       │ state (opaque)│
│ +save()      │                       └──────────────┘
│ +restore(m)  │                              ▲
└──────────────┘                              │
                  ┌──────────────┐            │
                  │  Caretaker   │────────────┘
                  └──────────────┘  holds Mementos, doesn't peek
```

The **Caretaker** stores Mementos but treats them as opaque tokens.

## 4. Participants

- **Originator** — the object whose state to save/restore.
- **Memento** — opaque snapshot. Only the Originator knows its layout.
- **Caretaker** — keeps Mementos (stack for undo, list for checkpoints).

## 5. Python implementation

```python
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

# --- Originator ---
class Editor:
    def __init__(self):
        self._text = ""
        self._cursor = 0

    def type(self, s: str):
        self._text = self._text[:self._cursor] + s + self._text[self._cursor:]
        self._cursor += len(s)

    def save(self) -> "EditorMemento":
        return EditorMemento(deepcopy(self._text), self._cursor)

    def restore(self, m: "EditorMemento"):
        self._text   = m._text
        self._cursor = m._cursor

    def __repr__(self): return f"Editor({self._text!r}, cur={self._cursor})"

# --- Memento (opaque; only Editor reads its fields) ---
@dataclass(frozen=True)
class EditorMemento:
    _text: str
    _cursor: int

# --- Caretaker ---
class History:
    def __init__(self): self._stack: list[EditorMemento] = []
    def push(self, m): self._stack.append(m)
    def pop(self):     return self._stack.pop() if self._stack else None

# --- Use ---
ed, hist = Editor(), History()
hist.push(ed.save())
ed.type("Hello ")
hist.push(ed.save())
ed.type("world")
print(ed)                            # Editor('Hello world', cur=11)
ed.restore(hist.pop())               # back to 'Hello '
print(ed)
ed.restore(hist.pop())               # back to ''
print(ed)
```

### Pythonic shortcuts

- `copy.deepcopy(obj)` — snapshot whole objects.
- `pickle.dumps(obj) / pickle.loads(...)` — serialisable Memento.
- `dataclasses.replace(obj, **changes)` — immutable update; equivalent to "restore with delta".

## 6. Backend examples

- **Database transactions / savepoints** — `SAVEPOINT s; ROLLBACK TO s` is Memento.
- **Git** — every commit is a Memento of the working tree.
- **Django ORM `revisions` (django-reversion)** — explicit Memento per save.
- **Event sourcing** — replayable log of state changes; checkpoints = Mementos.
- **Redis `RDB` snapshots** — periodic Memento of the in-memory state.
- **Stripe `idempotency_key` storage** — store request+response Memento to replay.

## 7. Pros / Cons

**Pros**
- Encapsulation preserved (caretaker doesn't see internals).
- Enables undo/redo and checkpointing cleanly.

**Cons**
- Memory cost: deep copies add up for big state.
- Restore logic must keep up with state schema changes.
- For mutable shared references inside state, shallow copies will leak mutations.

**Don't use when**
- State is small and you can re-derive it.
- A database transaction or VCS already gives you what you need.

## 8. Related patterns

- **Command** — Commands often hold a Memento to implement undo.
- **Prototype** — Prototype also clones state; intent differs (make a new instance vs restore the old one).
- **Iterator** — A Caretaker's history can be iterated for undo/redo.

## 9. Self-check

1. Who knows the Memento's internals — and who must not?
2. Why is `pickle` a Pythonic Memento?
3. How is `SAVEPOINT` in SQL a Memento?
4. What's the memory trap with naive Mementos?
5. How do Command and Memento collaborate for undo?
