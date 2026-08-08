# Visitor

> Runnable version of this pattern: [`Design_Patterns_Code/19_visitor/`](../../../02_Year5+_Senior/01_System_Design/Design_Patterns_Code/19_visitor/) — standalone script, `python visitor.py`.

> The hardest GoF pattern, and the rarest in idiomatic Python. Still worth knowing for compilers, ASTs, and query analysers.

## 1. Intent

Represent an **operation** to be performed on the elements of an object structure. Visitor lets you define a new operation **without changing the classes** of the elements it operates on.

## 2. Problem

You have a stable hierarchy of element classes (AST nodes, document nodes, query tree nodes). You want to add many *operations* (pretty-print, type-check, optimise, evaluate, transpile). Adding each operation as a method on every node class:
- Forces every node to know every operation.
- Means every new operation edits every node class.

Visitor inverts the dependency: operations live in their own classes; nodes only know how to "accept" a visitor.

## 3. Solution (UML sketch)

```
   Element (e.g. ASTNode)          Visitor
   ┌──────────────────┐       ┌────────────────────┐
   │ +accept(visitor) │       │ +visit_int(node)   │
   └──────────────────┘       │ +visit_add(node)   │
        △                     │ +visit_mul(node)   │
        │                     └────────────────────┘
   ┌──────────────────┐                  △
   │ IntNode          │       ┌─────────────────────┐
   │ +accept(v):      │       │ PrintVisitor        │
   │   v.visit_int()  │       └─────────────────────┘
   └──────────────────┘       ┌─────────────────────┐
                              │ EvalVisitor         │
                              └─────────────────────┘
```

Each Element's `accept` calls the right `visit_X` method on the visitor — this is "double dispatch": dispatch by both Element type and Visitor type.

## 4. Participants

- **Element** — declares `accept(visitor)`.
- **ConcreteElement** — implements `accept` by calling `visitor.visit_xxx(self)`.
- **Visitor** — has one method per Element type.
- **ConcreteVisitor** — implements an operation across all Element types.
- **ObjectStructure** — the tree/list holding Elements.

## 5. Python implementations

### Classical Visitor

```python
from abc import ABC, abstractmethod

class Visitor(ABC):
    @abstractmethod
    def visit_int(self, n):  ...
    @abstractmethod
    def visit_add(self, n):  ...
    @abstractmethod
    def visit_mul(self, n):  ...

class Node(ABC):
    @abstractmethod
    def accept(self, v: Visitor): ...

class IntNode(Node):
    def __init__(self, val): self.val = val
    def accept(self, v):     return v.visit_int(self)

class AddNode(Node):
    def __init__(self, l, r): self.l, self.r = l, r
    def accept(self, v):      return v.visit_add(self)

class MulNode(Node):
    def __init__(self, l, r): self.l, self.r = l, r
    def accept(self, v):      return v.visit_mul(self)

# Operation 1: evaluate
class Eval(Visitor):
    def visit_int(self, n): return n.val
    def visit_add(self, n): return n.l.accept(self) + n.r.accept(self)
    def visit_mul(self, n): return n.l.accept(self) * n.r.accept(self)

# Operation 2: pretty-print
class Print(Visitor):
    def visit_int(self, n): return str(n.val)
    def visit_add(self, n): return f"({n.l.accept(self)} + {n.r.accept(self)})"
    def visit_mul(self, n): return f"({n.l.accept(self)} * {n.r.accept(self)})"

# 2 * (3 + 4)
expr = MulNode(IntNode(2), AddNode(IntNode(3), IntNode(4)))
print(expr.accept(Eval()))   # 14
print(expr.accept(Print()))  # (2 * (3 + 4))
```

Adding `Typecheck` = one new class. No node touched.

### Pythonic — `functools.singledispatch`

Python's `singledispatch` gives type-based dispatch without `accept` boilerplate:

```python
from functools import singledispatch

@singledispatch
def evaluate(node):
    raise NotImplementedError

@evaluate.register
def _(n: IntNode): return n.val
@evaluate.register
def _(n: AddNode): return evaluate(n.l) + evaluate(n.r)
@evaluate.register
def _(n: MulNode): return evaluate(n.l) * evaluate(n.r)
```

`singledispatch` dispatches on the **first argument's type** — half of the double-dispatch trick, done by the runtime. For most Python uses this is the right call.

### `ast.NodeVisitor` — stdlib Visitor

Python's own AST module ships a Visitor:

```python
import ast

class CountFuncs(ast.NodeVisitor):
    def __init__(self): self.n = 0
    def visit_FunctionDef(self, node):
        self.n += 1
        self.generic_visit(node)             # recurse into children

src = "def a():\n  def b(): pass\n"
v = CountFuncs(); v.visit(ast.parse(src))
print(v.n)                                   # 2
```

## 6. Backend examples

- **`ast.NodeVisitor` / `NodeTransformer`** — Visitor and a mutating variant.
- **SQLAlchemy expression compilation** — visitors traverse SQL clause trees to compile per-dialect SQL.
- **Django ORM SQL compilers** — visit nodes in the queryset tree.
- **Linters (`flake8`, `pylint`)** — walk the AST with Visitors.
- **Type checkers (`mypy`)** — visitors over typed AST.
- **GraphQL execution / validation** — visitors over the query AST.
- **Mongo aggregation pipeline compilers** — visit query trees.

## 7. Pros / Cons

**Pros**
- New operations without editing element classes (OCP for operations).
- Operations live in cohesive classes (SRP).
- Double dispatch lets behaviour vary by *pair* of types.

**Cons**
- New **element types** force editing every existing visitor (OCP backwards on that axis).
- Verbose; `accept` boilerplate everywhere.
- Visitors often need to peek at Element internals — encapsulation tension.

**Don't use when**
- Element hierarchy is unstable (new element types frequently).
- You only have one or two operations — methods on the elements are simpler.
- `singledispatch` solves it more cheaply.

## 8. Related patterns

- **Composite** — Visitor is almost always run over a Composite tree.
- **Iterator** — Visitor pairs with iteration.
- **Strategy** — both decouple algorithm from data; Visitor is type-aware (multi-dispatch), Strategy is type-agnostic.

## 9. Self-check

1. What does "double dispatch" mean in Visitor?
2. Why is `ast.NodeVisitor` an instance of Visitor?
3. State the OCP trade-off: easy for new ___, hard for new ___.
4. How does `functools.singledispatch` compare to classical Visitor?
5. Give a backend system where Visitor is genuinely the right tool.
