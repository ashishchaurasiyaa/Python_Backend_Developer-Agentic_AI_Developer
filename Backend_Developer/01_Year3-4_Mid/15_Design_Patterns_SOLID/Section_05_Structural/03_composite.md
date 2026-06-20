# Composite

## 1. Intent

Compose objects into **tree structures** so clients can treat individual objects and compositions **uniformly**.

## 2. Problem

You have nested structures where "container" and "leaf" should behave the same from the caller's perspective. Without Composite, every traversal needs `if isinstance(x, Container): … else: …`.

Examples:
- File system: a file or a folder both have `size`.
- HTML/DOM: a `<div>` and a `<span>` both render.
- Permission groups: a group contains users *or* sub-groups.
- Org chart: an employee or a department both report headcount.

## 3. Solution (UML sketch)

```
       ┌─────────────────┐
       │  <<Component>>  │
       ├─────────────────┤
       │ +operation()    │
       └─────────────────┘
              △
   ┌──────────┴────────────┐
   │                       │
┌────────┐          ┌─────────────┐
│  Leaf  │          │  Composite  │◇──┐
└────────┘          ├─────────────┤   │ children: list[Component]
                    │ +operation()│   │
                    │ +add(c)     │<──┘
                    │ +remove(c)  │
                    └─────────────┘
```

## 4. Participants

- **Component** — interface for both leaves and composites.
- **Leaf** — atomic element, no children.
- **Composite** — holds children (Components, recursively), delegates work to them.

## 5. Python implementation

### File system size example

```python
from __future__ import annotations
from typing import Protocol

class FSNode(Protocol):
    name: str
    def size(self) -> int: ...

class File:
    def __init__(self, name: str, bytes_: int):
        self.name = name
        self._bytes = bytes_
    def size(self) -> int:
        return self._bytes

class Folder:
    def __init__(self, name: str):
        self.name = name
        self._children: list[FSNode] = []
    def add(self, node: FSNode) -> None:
        self._children.append(node)
    def size(self) -> int:
        return sum(c.size() for c in self._children)

# Build a tree
root = Folder("root")
root.add(File("a.txt", 100))
sub = Folder("sub")
sub.add(File("b.txt", 50))
sub.add(File("c.txt", 75))
root.add(sub)

print(root.size())   # 225 — caller doesn't care about the tree shape
```

The client calls `.size()` on root; recursion is built into the Composite.

### Recursive permission group example

```python
class Principal(Protocol):
    def has_permission(self, perm: str) -> bool: ...

class User:
    def __init__(self, name, perms): self.name, self.perms = name, set(perms)
    def has_permission(self, perm): return perm in self.perms

class Group:
    def __init__(self, name): self.name = name; self.members: list[Principal] = []
    def add(self, m: Principal): self.members.append(m)
    def has_permission(self, perm):
        return any(m.has_permission(perm) for m in self.members)
```

## 6. Backend examples

- **Django form widgets** — `MultiWidget` contains sub-widgets and renders uniformly.
- **SQLAlchemy clause elements** — `and_`, `or_`, comparison expressions form a tree, all `ClauseElement`s.
- **Pydantic v2 / dataclasses** — nested models traversed for validation and serialization the same way at every level.
- **AST** — `ast.Module`, `ast.FunctionDef`, `ast.Call`, `ast.Name` all share the visitor entry shape.
- **HTML/template engines** — Jinja `Node`s, BeautifulSoup `Tag` and `NavigableString` both respond to `.get_text()`.

## 7. Pros / Cons

**Pros**
- Treat leaves and trees the same → simpler client code.
- Tree grows without changing callers.
- Naturally recursive operations (`size`, `render`, `evaluate`).

**Cons**
- Type system can struggle ("can the leaf accept `add()`?"). Two solutions: separate `Leaf` / `Composite` interfaces, or raise `NotImplementedError` on leaves.
- Tempting to over-generalise: not every nested-thing is a Composite.

**Don't use when**
- The structure isn't actually recursive.
- Leaf and Composite share so little behaviour that uniform treatment is awkward.

## 8. Related patterns

- **Iterator** — Composite trees are usually traversed via iterators.
- **Visitor** — common companion to add operations on Composite trees without bloating the node classes.
- **Decorator** — has a similar wrapper shape but isn't a tree; one wrapee, not many children.

## 9. Self-check

1. What's the core promise Composite makes to the client?
2. Sketch the participants.
3. Why is the file-system `size()` a textbook Composite?
4. When does Composite become awkward?
5. How does Composite team up with Visitor and Iterator?
