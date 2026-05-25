# 21 — Interpreter Pattern

> Behavioral pattern. Defines a representation of a grammar for a language and an interpreter that uses the representation to interpret sentences in the language.

> In plain English: when you need to evaluate expressions / mini-languages / rule engines, define each grammar rule as a class.

---

## When to use

- You have a simple "domain-specific language" (DSL) — rule engine, filter expressions, search queries.
- The grammar is small and stable.
- You evaluate expressions repeatedly.

Examples in the wild:
- Regular expression engines.
- SQL WHERE clause parsers.
- Filter expressions like `(status=active AND age>18)`.
- Boolean logic evaluators.
- Configuration languages.

---

## The Core Idea

Each grammar rule becomes a class. Each class knows how to interpret itself given a context.

```
Expression                              "(5 + 3) × 2"
   │
   ▼
Multiply(                                ┌── Multiply
  Add(Number(5), Number(3)),             │     ├── Add
  Number(2)                              │     │     ├── Number(5)
)                                        │     │     └── Number(3)
   │                                     │     └── Number(2)
   ▼                                     │
.interpret() → 16
```

---

## Structure

```
┌──────────────┐
│ AbstractExpr │  + interpret(context)
└──────┬───────┘
       │
   ┌───┼─────┬─────────┐
   │       │           │
┌──▼───┐ ┌──▼────┐ ┌───▼──────┐
│Termi-│ │Non-   │ │Non-      │
│nal   │ │Termi  │ │Terminal  │
│(leaf)│ │(unary)│ │(binary)  │
└──────┘ └───────┘ └──────────┘
```

- **Terminal Expression**: leaves (e.g., literals, variables).
- **Non-terminal Expression**: composite (e.g., AND, OR, +, ×).

---

## Implementation — Arithmetic Expression

```python
from abc import ABC, abstractmethod

class Expr(ABC):
    @abstractmethod
    def interpret(self) -> float: pass


# Terminal
class Number(Expr):
    def __init__(self, value: float):
        self.value = value

    def interpret(self) -> float:
        return self.value


# Non-terminals
class Add(Expr):
    def __init__(self, left: Expr, right: Expr):
        self.left = left
        self.right = right

    def interpret(self) -> float:
        return self.left.interpret() + self.right.interpret()


class Multiply(Expr):
    def __init__(self, left: Expr, right: Expr):
        self.left = left
        self.right = right

    def interpret(self) -> float:
        return self.left.interpret() * self.right.interpret()


# Usage: (5 + 3) * 2
expr = Multiply(
    Add(Number(5), Number(3)),
    Number(2)
)
print(expr.interpret())  # 16.0
```

---

## With Context (Variables)

When expressions have variables that resolve at evaluation time:

```python
class Context:
    def __init__(self, variables: dict):
        self.variables = variables

class Variable(Expr):
    def __init__(self, name: str):
        self.name = name

    def interpret(self, ctx: Context) -> float:
        return ctx.variables[self.name]

class Add(Expr):
    def __init__(self, l, r):
        self.l, self.r = l, r
    def interpret(self, ctx: Context) -> float:
        return self.l.interpret(ctx) + self.r.interpret(ctx)


# Usage: salary + bonus
expr = Add(Variable("salary"), Variable("bonus"))
ctx = Context({"salary": 5000, "bonus": 1500})
print(expr.interpret(ctx))  # 6500
```

---

## Real Example — Filter Expression for Search

Build a filter language: `status=active AND age>18`.

```python
from dataclasses import dataclass

class FilterExpr(ABC):
    @abstractmethod
    def matches(self, record: dict) -> bool: pass


@dataclass
class Equals(FilterExpr):
    field: str
    value: object
    def matches(self, record):
        return record.get(self.field) == self.value


@dataclass
class GreaterThan(FilterExpr):
    field: str
    value: int
    def matches(self, record):
        return record.get(self.field, 0) > self.value


@dataclass
class And(FilterExpr):
    expressions: list[FilterExpr]
    def matches(self, record):
        return all(e.matches(record) for e in self.expressions)


@dataclass
class Or(FilterExpr):
    expressions: list[FilterExpr]
    def matches(self, record):
        return any(e.matches(record) for e in self.expressions)


@dataclass
class Not(FilterExpr):
    expression: FilterExpr
    def matches(self, record):
        return not self.expression.matches(record)


# Filter: status=active AND age>18 AND NOT banned=True
f = And([
    Equals("status", "active"),
    GreaterThan("age", 18),
    Not(Equals("banned", True))
])

users = [
    {"name": "alice", "status": "active", "age": 25, "banned": False},
    {"name": "bob",   "status": "active", "age": 15, "banned": False},
    {"name": "carol", "status": "active", "age": 30, "banned": True},
]

matching = [u for u in users if f.matches(u)]
# [alice]
```

This is the **rule engine** pattern under the hood.

---

## Real Example — Boolean Logic Engine

```python
class True_(Expr):
    def interpret(self, ctx): return True

class False_(Expr):
    def interpret(self, ctx): return False

class And(Expr):
    def __init__(self, *args): self.args = args
    def interpret(self, ctx): return all(a.interpret(ctx) for a in self.args)

class Or(Expr):
    def __init__(self, *args): self.args = args
    def interpret(self, ctx): return any(a.interpret(ctx) for a in self.args)

class Var(Expr):
    def __init__(self, name): self.name = name
    def interpret(self, ctx): return ctx[self.name]

# Expression: A AND (B OR NOT C)
e = And(Var("A"), Or(Var("B"), Not(Var("C"))))
```

---

## Parsing Expressions

Interpreter pattern needs the AST first. To go from text to AST, you need a parser.

### Simple shunting-yard for arithmetic

```python
def parse_arithmetic(tokens):
    """Returns AST root."""
    # Implement a simple recursive-descent parser
    ...
```

For real grammars, use:
- **PLY** (Python Lex Yacc).
- **pyparsing** (declarative).
- **lark** (modern, fast).
- **ANTLR** (industry-standard for non-trivial grammars).

```python
# Using lark
from lark import Lark, Transformer

grammar = """
    expr: term ("+" term)*
    term: factor ("*" factor)*
    factor: NUMBER | "(" expr ")"
    NUMBER: /\d+/
    %ignore " "
"""

class Eval(Transformer):
    def expr(self, items):
        result = items[0]
        for op in items[1:]:
            result += op
        return result
    def NUMBER(self, n):
        return int(n)

parser = Lark(grammar, start='expr')
tree = parser.parse("1 + 2 * 3")
print(Eval().transform(tree))   # 7
```

---

## Visitor Pattern Often Pairs

If you have many operations on the AST (evaluate, optimize, pretty-print, serialize), use **Visitor**:

```python
class ExprVisitor(ABC):
    @abstractmethod
    def visit_number(self, e): pass
    @abstractmethod
    def visit_add(self, e):    pass

class Eval(ExprVisitor):
    def visit_number(self, e): return e.value
    def visit_add(self, e):    return e.l.accept(self) + e.r.accept(self)

class Print(ExprVisitor):
    def visit_number(self, e): return str(e.value)
    def visit_add(self, e):    return f"({e.l.accept(self)} + {e.r.accept(self)})"

class Number(Expr):
    def __init__(self, v): self.value = v
    def accept(self, v): return v.visit_number(self)

class Add(Expr):
    def __init__(self, l, r): self.l, self.r = l, r
    def accept(self, v): return v.visit_add(self)
```

Different visitors for different operations — clean separation.

---

## Real-World Examples

### SQL WHERE Clauses
Database engines parse SQL into AST, then interpret/optimize.

### Regular Expressions
Regex engines parse pattern → AST → match.

### Configuration Languages
HCL (Terraform), JSON Schema, Jsonnet — all interpret expressions.

### Search Filters
Elasticsearch DSL, GraphQL filter expressions.

### Templating Engines
Jinja2, Mustache parse template → execute against context.

### Feature Flag Rules
LaunchDarkly, GrowthBook: `country IN ('US') AND user_age > 18`.

### Rule Engines
Drools (Java), pyke, business rule managers.

### Build Systems
Make, Bazel parse rules and dependencies as ASTs.

---

## When NOT to Use

- Grammar is complex / changing rapidly (use proper parser tools).
- Performance critical (interpreters slower than compiled code — use compilation).
- Existing library exists (use it!).

For complex use cases:
- Use a parser library (lark, ANTLR).
- Consider transpilation to native code.
- Consider sandboxed JS/Python evaluation for max flexibility.

---

## Trade-offs

### Pros
- ✓ Clean separation: each rule is a class.
- ✓ Easy to extend grammar with new operators.
- ✓ ASTs are easy to manipulate (optimize, transform).

### Cons
- ✗ Many small classes for complex grammars.
- ✗ Slow execution (object dispatch overhead).
- ✗ Maintenance burden as grammar grows.

---

## Performance Optimization

For hot interpreters:
1. **Cache the AST** instead of re-parsing.
2. **Bytecode**: compile AST to a bytecode list, run with a single loop.
3. **JIT**: compile hot paths to machine code (Numba, PyPy).
4. **Compile to Python source**: generate Python and `exec` it (still safer than `eval`).

```python
# Compile filter to Python lambda
def compile_filter(expr):
    if isinstance(expr, Equals):
        return lambda r: r.get(expr.field) == expr.value
    if isinstance(expr, And):
        subs = [compile_filter(e) for e in expr.expressions]
        return lambda r: all(s(r) for s in subs)
    # ...
```

Now matching is a direct lambda call. No class dispatch.

---

## Security Note

Interpreting user-provided expressions = potential RCE risk.

### Don't use `eval()` for user input
```python
eval("__import__('os').system('rm -rf /')")  # disaster
```

### Use AST-based interpreter
Only support whitelisted operations:
```python
ALLOWED_OPS = {ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Num}

def safe_eval(expr_str):
    tree = ast.parse(expr_str, mode="eval")
    for node in ast.walk(tree):
        if type(node) not in ALLOWED_OPS and not isinstance(node, ast.Expression):
            raise ValueError(f"Disallowed: {type(node).__name__}")
    return eval(compile(tree, "<safe>", "eval"))
```

### Or sandbox in WASM / V8 isolate
For untrusted code execution, use proper isolation.

---

## Interpreter vs Visitor

| Interpreter | Visitor |
|---|---|
| Defines grammar nodes | Defines operations on nodes |
| Adding new grammar rule: easy | Adding new node type: hard |
| Adding new operation: hard | Adding new operation: easy |
| Use when grammar varies | Use when operations vary |

**Often combined:** Interpreter for structure + Visitor for operations.

---

## Pythonic Alternatives

Sometimes a simple function suffices:

```python
def evaluate(expr, ctx):
    """expr is a dict like {'op': 'add', 'left': ..., 'right': ...}"""
    if expr["op"] == "number":
        return expr["value"]
    if expr["op"] == "var":
        return ctx[expr["name"]]
    if expr["op"] == "add":
        return evaluate(expr["left"], ctx) + evaluate(expr["right"], ctx)
    ...
```

Dict-based AST + switch function. No classes. Pythonic for small DSLs.

---

## Testing Interpreters

```python
def test_simple_add():
    expr = Add(Number(2), Number(3))
    assert expr.interpret() == 5

def test_complex():
    # (1 + 2) * (3 + 4)
    expr = Multiply(Add(Number(1), Number(2)), Add(Number(3), Number(4)))
    assert expr.interpret() == 21

def test_variable_lookup():
    ctx = Context({"x": 10, "y": 5})
    expr = Multiply(Variable("x"), Variable("y"))
    assert expr.interpret(ctx) == 50
```

---

## TL;DR

- Interpreter = each grammar rule = a class with `interpret()`.
- Best for: small stable DSLs, rule engines, filter expressions.
- Often paired with Visitor (separate operations from structure).
- For complex grammars: use parser libraries (lark, ANTLR).
- For hot paths: compile to bytecode or lambdas.
- For untrusted input: NEVER `eval()` — use AST whitelisting or sandbox.
- **Use when:** filter language, math expressions, rule conditions, query parsing.
- **Skip when:** grammar large/changing, performance critical, library exists.

---

## Putting Phase D in Context

This is the final pattern in the LLD pack. You've now covered:
- **Creational** (Singleton, Factory, Abstract Factory, Builder, Prototype).
- **Structural** (Adapter, Decorator, Facade, Composite, Proxy, Flyweight, **Bridge**).
- **Behavioral** (Strategy, Observer, Template, Iterator, Mediator, Visitor, Chain of Responsibility, Command, **State**, **Memento**, **Interpreter**).

22 patterns total. Most code uses 5-7 of these regularly; the rest are situational.
