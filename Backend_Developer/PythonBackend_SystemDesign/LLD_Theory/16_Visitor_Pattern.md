# Visitor Pattern

> **Category:** Behavioral Design Pattern
> **Intent:** Define a new **operation** on a group of objects **without changing the objects' classes**.

---

## 1. Problem Statement

You have a class hierarchy (e.g., AST nodes, file types, shapes). You need to add **operations**:
- Calculate tax for different product types
- Render different shapes
- Compile / interpret / type-check AST nodes
- Export documents to PDF / HTML / Markdown

**Naive approach:** Add method to every class.
**Problem:** Every new operation = touch every class. Violates **Open-Closed Principle**.

**Visitor solution:** Externalize operations into "visitor" classes. Classes only expose an `accept(visitor)` method.

---

## 2. Real-World Analogies

- **Tax inspector** visits different businesses (shop, factory, restaurant) — each calculated differently, inspector code is one place
- **Compiler passes** — same AST, different visitors: type checker, optimizer, codegen
- **Insurance claims adjuster** — visits home, car, business — different evaluation rules

---

## 3. Structure (UML)

```
Visitor                    Element
─────────────              ──────────
+ visit_a(A)               + accept(v)
+ visit_b(B)
       ▲                        ▲
       │                ┌───────┴───────┐
   ConcreteVisitor      A               B
    (e.g., PDFExporter) accept(v):      accept(v):
                          v.visit_a(self) v.visit_b(self)
```

**Double dispatch:** Element decides which visit method to call.

---

## 4. Python Implementation Approaches

### Approach 1: Classic OOP (double dispatch)
```python
from abc import ABC, abstractmethod

class Shape(ABC):
    @abstractmethod
    def accept(self, visitor): ...

class Circle(Shape):
    def __init__(self, r): self.r = r
    def accept(self, visitor): return visitor.visit_circle(self)

class Square(Shape):
    def __init__(self, side): self.side = side
    def accept(self, visitor): return visitor.visit_square(self)

class AreaVisitor:
    def visit_circle(self, c): return 3.14 * c.r * c.r
    def visit_square(self, s): return s.side ** 2
```

### Approach 2: `functools.singledispatch` (Pythonic)
```python
from functools import singledispatch

@singledispatch
def area(shape):
    raise NotImplementedError

@area.register
def _(shape: Circle):
    return 3.14 * shape.r ** 2

@area.register
def _(shape: Square):
    return shape.side ** 2
```

### Approach 3: `singledispatchmethod` (per-class)
```python
from functools import singledispatchmethod

class AreaVisitor:
    @singledispatchmethod
    def visit(self, shape): raise NotImplementedError
    @visit.register
    def _(self, shape: Circle): return 3.14 * shape.r ** 2
    @visit.register
    def _(self, shape: Square): return shape.side ** 2
```

---

## 5. When to Use

✅ **Use when:**
- Many unrelated operations on stable class hierarchy
- Class hierarchy rarely changes; operations grow
- Want to keep operations separate from data (SRP)
- AST processing, compiler passes
- Document export to multiple formats

❌ **Don't use when:**
- Classes change often (every visitor must update)
- Only one operation
- Simple cases — singledispatch is enough
- Languages without double dispatch (Python handles it OK)

---

## 6. Real Production Examples

### Example 1: AST in compilers / linters
```python
class TypeChecker(Visitor):
    def visit_binop(self, node): ...
    def visit_call(self, node): ...

class Optimizer(Visitor):
    def visit_binop(self, node): ...   # constant folding
```
Python's `ast` module uses visitor: `ast.NodeVisitor`.

### Example 2: Document export
```python
class PDFExporter:
    def visit_heading(self, h): ...
    def visit_paragraph(self, p): ...

class HTMLExporter:
    def visit_heading(self, h): ...
    def visit_paragraph(self, p): ...

class MarkdownExporter: ...
```

### Example 3: Tax calculation
```python
class TaxCalculator:
    def visit_book(self, b): return b.price * 0.05
    def visit_electronics(self, e): return e.price * 0.18
    def visit_food(self, f): return 0
```

### Example 4: File system operations
```python
class SizeCalculator:
    def visit_file(self, f): return f.size
    def visit_dir(self, d): return sum(c.accept(self) for c in d.children)

class Indexer:
    def visit_file(self, f): db.index(f.path, f.content)
    def visit_dir(self, d): [c.accept(self) for c in d.children]
```

---

## 7. Visitor + Composite Pattern (common combo)

Composite hierarchy (tree of files/dirs, AST, etc.) + Visitor for operations.

```python
class FSNode:
    def accept(self, v): ...

class File(FSNode):
    def accept(self, v): return v.visit_file(self)

class Directory(FSNode):
    def accept(self, v): return v.visit_dir(self)
```

---

## 8. Pitfalls

### Pitfall 1: Adding new element type = update all visitors
This is the **fundamental trade-off**. Visitor optimizes for adding operations, not new types.

### Pitfall 2: Breaking encapsulation
Visitor needs internal data — exposes object fields. Use getters or trusted-friend pattern.

### Pitfall 3: Pythonic alternative ignored
For simple cases, `singledispatch` is much cleaner than full visitor scaffolding.

### Pitfall 4: Stateful visitor
Visitor can hold accumulator state. Be careful with concurrent use — not thread-safe by default.

### Pitfall 5: Cyclic structures
Visitor on cyclic graph can loop forever. Track visited set.

---

## 9. Interview Questions

**Q1: Visitor vs Strategy?**
- Strategy: swap one algorithm
- Visitor: apply different ops across multiple types

**Q2: Why double dispatch?**
Single dispatch picks based on receiver type. Double dispatch picks based on TWO types (element + visitor). Visitor simulates this.

**Q3: Python ka native visitor?**
- `ast.NodeVisitor` — for syntax trees
- `functools.singledispatch` — type-based dispatch

**Q4: Drawback of visitor pattern?**
Adding new element type = update every visitor. Locked into stable hierarchy.

**Q5: When use vs singledispatch?**
- singledispatch: simple, one-off operations
- Visitor class: stateful, complex, multiple related operations grouped

**Q6: Real-world use?**
- Compilers (Python `ast`, LLVM IR passes)
- Linters (ruff, mypy)
- Document conversion (Pandoc)
- Game engines (entity systems)

---

## 10. Best Practices

1. **Use when class hierarchy is stable**
2. **Combine with Composite** for trees
3. **Use `functools.singledispatch`** for simple cases
4. **Group related ops** in one visitor (e.g., all AST optimizations)
5. **Keep visitor stateless** when possible
6. **Track visited set** for cyclic structures
7. **Document interface** — visitor needs to know all element types

---

## 11. Key Takeaways

1. **Visitor adds operations** without modifying classes
2. Uses **double dispatch** (`element.accept(visitor)`)
3. Python alternatives: `singledispatch`, `singledispatchmethod`, `ast.NodeVisitor`
4. Best for **stable hierarchies + growing operations**
5. Trade-off: add op easy, add type hard
6. Real uses: compilers, AST, document export, file system ops

---

## Related
- [[Command_Composite_Proxy_Flyweight_Patterns]] — Composite combo
- [[07_Strategy_Pattern]] — single algorithm swap
- [[14_Iterator_Pattern]] — traversal pattern
