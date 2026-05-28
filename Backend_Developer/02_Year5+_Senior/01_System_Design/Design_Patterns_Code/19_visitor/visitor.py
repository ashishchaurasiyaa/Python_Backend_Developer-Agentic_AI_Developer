"""
============================================================
VISITOR PATTERN — Practical Implementation
============================================================
Run:  python visitor.py
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import singledispatch, singledispatchmethod
import ast


# ============================================================
# 1. CLASSIC VISITOR — Shape area / perimeter calculations
# ============================================================
class Shape(ABC):
    @abstractmethod
    def accept(self, visitor): ...


@dataclass
class Circle(Shape):
    radius: float
    def accept(self, visitor): return visitor.visit_circle(self)


@dataclass
class Square(Shape):
    side: float
    def accept(self, visitor): return visitor.visit_square(self)


@dataclass
class Triangle(Shape):
    base: float
    height: float
    def accept(self, visitor): return visitor.visit_triangle(self)


class ShapeVisitor(ABC):
    @abstractmethod
    def visit_circle(self, c: Circle): ...
    @abstractmethod
    def visit_square(self, s: Square): ...
    @abstractmethod
    def visit_triangle(self, t: Triangle): ...


class AreaVisitor(ShapeVisitor):
    def visit_circle(self, c): return 3.14159 * c.radius ** 2
    def visit_square(self, s): return s.side ** 2
    def visit_triangle(self, t): return 0.5 * t.base * t.height


class PerimeterVisitor(ShapeVisitor):
    def visit_circle(self, c): return 2 * 3.14159 * c.radius
    def visit_square(self, s): return 4 * s.side
    def visit_triangle(self, t):
        # Simplified: isoceles
        side = (t.base ** 2 / 4 + t.height ** 2) ** 0.5
        return t.base + 2 * side


class DrawVisitor(ShapeVisitor):
    def visit_circle(self, c): return f"○ Circle(r={c.radius})"
    def visit_square(self, s): return f"□ Square(s={s.side})"
    def visit_triangle(self, t): return f"△ Triangle(b={t.base},h={t.height})"


def demo_shapes():
    print("=" * 60)
    print("DEMO 1: Classic Visitor — Shape operations")
    print("=" * 60)
    shapes = [Circle(5), Square(4), Triangle(3, 4)]
    visitors = [("Area", AreaVisitor()), ("Perimeter", PerimeterVisitor()), ("Draw", DrawVisitor())]
    for shape in shapes:
        print(f"\n  {shape}:")
        for name, v in visitors:
            print(f"    {name}: {shape.accept(v)}")


# ============================================================
# 2. PYTHONIC — functools.singledispatch
# ============================================================
@singledispatch
def area(shape):
    raise NotImplementedError(f"No area for {type(shape).__name__}")


@area.register
def _(shape: Circle):
    return 3.14159 * shape.radius ** 2


@area.register
def _(shape: Square):
    return shape.side ** 2


@area.register
def _(shape: Triangle):
    return 0.5 * shape.base * shape.height


def demo_singledispatch():
    print("\n" + "=" * 60)
    print("DEMO 2: Pythonic visitor via singledispatch")
    print("=" * 60)
    for s in [Circle(3), Square(5), Triangle(4, 6)]:
        print(f"  area({s}) = {area(s)}")


# ============================================================
# 3. AST VISITOR — using Python's built-in ast.NodeVisitor
# ============================================================
class FunctionCallCounter(ast.NodeVisitor):
    """Counts function calls in source code."""
    def __init__(self):
        self.calls: dict[str, int] = {}

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            name = node.func.id
            self.calls[name] = self.calls.get(name, 0) + 1
        elif isinstance(node.func, ast.Attribute):
            name = node.func.attr
            self.calls[name] = self.calls.get(name, 0) + 1
        self.generic_visit(node)


def demo_ast_visitor():
    print("\n" + "=" * 60)
    print("DEMO 3: AST Visitor (Python builtin)")
    print("=" * 60)
    source = """
import os
print("hello")
print("world")
x = len([1,2,3])
data = sorted([3,1,2])
os.path.join("a", "b")
"""
    tree = ast.parse(source)
    visitor = FunctionCallCounter()
    visitor.visit(tree)
    print(f"  Call counts: {visitor.calls}")


# ============================================================
# 4. COMPOSITE + VISITOR — File system
# ============================================================
class FSNode(ABC):
    @abstractmethod
    def accept(self, visitor): ...


@dataclass
class File(FSNode):
    name: str
    size: int
    def accept(self, visitor): return visitor.visit_file(self)


class Directory(FSNode):
    def __init__(self, name, children=None):
        self.name = name
        self.children = children or []
    def accept(self, visitor): return visitor.visit_directory(self)
    def __repr__(self):
        return f"Dir({self.name}, {len(self.children)} children)"


class SizeCalculator:
    def visit_file(self, f: File): return f.size
    def visit_directory(self, d: Directory):
        return sum(c.accept(self) for c in d.children)


class Indexer:
    def __init__(self): self.index = []
    def visit_file(self, f: File):
        self.index.append((f.name, f.size))
    def visit_directory(self, d: Directory):
        for c in d.children:
            c.accept(self)


class ASCIITree:
    def __init__(self): self.lines = []; self.depth = 0
    def visit_file(self, f: File):
        self.lines.append("  " * self.depth + f"📄 {f.name} ({f.size}B)")
    def visit_directory(self, d: Directory):
        self.lines.append("  " * self.depth + f"📁 {d.name}/")
        self.depth += 1
        for c in d.children:
            c.accept(self)
        self.depth -= 1


def demo_fs():
    print("\n" + "=" * 60)
    print("DEMO 4: Composite + Visitor — File system")
    print("=" * 60)
    root = Directory("root", [
        File("readme.md", 1024),
        Directory("src", [
            File("main.py", 2048),
            File("utils.py", 512),
            Directory("tests", [
                File("test_main.py", 1500),
            ]),
        ]),
        File("LICENSE", 256),
    ])

    print("--- Tree view ---")
    drawer = ASCIITree()
    root.accept(drawer)
    print("\n".join(drawer.lines))

    print(f"\n--- Total size ---")
    sz = SizeCalculator()
    print(f"  {root.accept(sz)} bytes")

    print(f"\n--- Index of all files ---")
    idx = Indexer()
    root.accept(idx)
    for name, size in idx.index:
        print(f"  {name}: {size}B")


# ============================================================
# 5. PRODUCT TAX CALCULATOR — domain example
# ============================================================
@dataclass
class Book:
    title: str
    price: float
    def accept(self, v): return v.visit_book(self)


@dataclass
class Electronics:
    name: str
    price: float
    def accept(self, v): return v.visit_electronics(self)


@dataclass
class Food:
    name: str
    price: float
    is_luxury: bool = False
    def accept(self, v): return v.visit_food(self)


class IndianTaxVisitor:
    def visit_book(self, b): return b.price * 0.05    # 5% GST
    def visit_electronics(self, e): return e.price * 0.18   # 18% GST
    def visit_food(self, f): return f.price * (0.12 if f.is_luxury else 0)


class USStateTaxVisitor:
    def visit_book(self, b): return 0  # no tax on books in many states
    def visit_electronics(self, e): return e.price * 0.0825
    def visit_food(self, f): return f.price * 0.05 if f.is_luxury else 0


def demo_tax():
    print("\n" + "=" * 60)
    print("DEMO 5: Tax Calculator Visitor")
    print("=" * 60)
    cart = [
        Book("Clean Code", 500),
        Electronics("iPhone", 80000),
        Food("Rice", 50),
        Food("Caviar", 5000, is_luxury=True),
    ]
    for visitor, label in [(IndianTaxVisitor(), "India"), (USStateTaxVisitor(), "US")]:
        print(f"\n  Tax in {label}:")
        total = 0
        for item in cart:
            tax = item.accept(visitor)
            print(f"    {type(item).__name__:12s} {item.__dict__.get('title') or item.__dict__.get('name'):15s} -> ₹{tax:.2f}")
            total += tax
        print(f"    Total tax: ₹{total:.2f}")


# ============================================================
# 6. SINGLEDISPATCHMETHOD — per-class polymorphism
# ============================================================
class JSONExporter:
    @singledispatchmethod
    def export(self, obj):
        raise NotImplementedError

    @export.register
    def _(self, obj: Circle):
        return {"type": "circle", "radius": obj.radius}

    @export.register
    def _(self, obj: Square):
        return {"type": "square", "side": obj.side}


def demo_singledispatchmethod():
    print("\n" + "=" * 60)
    print("DEMO 6: singledispatchmethod")
    print("=" * 60)
    exporter = JSONExporter()
    for shape in [Circle(5), Square(3)]:
        print(f"  {exporter.export(shape)}")


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    demo_shapes()
    demo_singledispatch()
    demo_ast_visitor()
    demo_fs()
    demo_tax()
    demo_singledispatchmethod()

    print("\n" + "=" * 60)
    print("KEY TAKEAWAYS")
    print("=" * 60)
    print("""
1. Visitor decouples operations from data structures
2. Use double dispatch: element.accept(visitor) → visitor.visit_X(element)
3. Pythonic alternatives: singledispatch, singledispatchmethod
4. Python's ast.NodeVisitor is built-in
5. Trade-off: add op = easy, add type = update all visitors
6. Pairs well with Composite (trees, AST, file system)
""")
