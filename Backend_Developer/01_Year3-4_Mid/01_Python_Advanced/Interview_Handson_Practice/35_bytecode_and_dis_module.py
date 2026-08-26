"""
================================================================================
TOPIC: CPython Bytecode — dis module, Code Objects, Compilation Pipeline
================================================================================

KYA HOTA HAI:
    Python source (.py) → CPython compiler → bytecode (.pyc) → PVM execute karta hai

    Pipeline:
    .py source
       ↓ tokenize (lexer)
    Token stream
       ↓ parse
    AST (Abstract Syntax Tree)
       ↓ compile
    Code Object (bytecode + metadata)
       ↓ marshal → .pyc file (cache)
       ↓ PVM (Python Virtual Machine) — bytecode interpreter
    Result

    `dis` module = disassembler: bytecode ko human-readable instructions mein dikhata hai

KYO ZAROORI HAI:
    1. Performance debugging: LOAD_FAST vs LOAD_GLOBAL — kyon local variables faster hain
    2. Understanding closures: LOAD_DEREF — cell objects kaise kaam karte hain
    3. Peephole optimizer: Python compile-time kya optimize karta hai
    4. Interview: "Python mein function call overhead kyon hai?" → bytecode se explain karo
    5. Security: .pyc files ko decompile karke code recover ho sakta hai

KAISE KAAM KARTA HAI (architecture):

    Code Object (PyCodeObject in CPython):
    ┌──────────────────────────────────────────────────────────┐
    │ co_name      : function name                             │
    │ co_filename  : source file                               │
    │ co_firstlineno: line number in source                    │
    │ co_consts    : (None, 42, 'hello', ...)  ← literal pool  │
    │ co_varnames  : ('x', 'y', 'result')      ← local vars    │
    │ co_freevars  : ('n',)                    ← closure vars   │
    │ co_code      : b'\x97\x00d\x01...'       ← raw bytecode  │
    │ co_stacksize : max stack depth needed                    │
    └──────────────────────────────────────────────────────────┘

    Bytecode = sequence of 2-byte instructions (opcode, arg) in Python 3.6+
    Stack machine — operands pushed/popped from a stack

KAHAN USE HOTA HAI:
    - Performance profiling: `dis.dis(hot_function)` — see what CPython actually does
    - Security audit: check if sensitive data appears in co_consts
    - Compiler optimization: understand why `x in {1,2,3}` faster than `x in [1,2,3]`
    - Teaching: explain scoping rules via LOAD_FAST/LOAD_GLOBAL/LOAD_DEREF difference

INTERVIEW ANSWER (English — recite this):
    "CPython compiles Python source to bytecode — a sequence of instructions for a
    stack-based virtual machine. dis.dis() shows these instructions in human-readable
    form. Local variable access uses LOAD_FAST (array index lookup, O(1), very fast),
    global variable access uses LOAD_GLOBAL (dict lookup, slightly slower). Closures
    use LOAD_DEREF via cell objects. The peephole optimizer folds constant expressions
    and replaces mutable literals in membership tests — {1,2,3} becomes a frozenset
    at compile time."
================================================================================
"""

import dis
import sys
import py_compile
import ast

# ============================================================================
# SECTION 1 — dis.dis(): Your First Disassembly
# ============================================================================
print("=" * 65)
print("SECTION 1 — dis.dis(): Disassembling a Simple Function")
print("=" * 65)

def add(x, y):
    result = x + y
    return result

print("Source:")
print("  def add(x, y):")
print("      result = x + y")
print("      return result")
print("\nBytecode (dis.dis(add)):")
dis.dis(add)

# Reading the output:
# Column 1: Line number in source
# Column 2: '>>' marks jump targets, '>>' for exception handlers
# Column 3: Byte offset in co_code
# Column 4: Opcode name
# Column 5: Argument (numeric)
# Column 6: (human-readable hint for the argument)


# ============================================================================
# SECTION 2 — Code Objects: co_consts, co_varnames, co_code
# ============================================================================
print("\n" + "=" * 65)
print("SECTION 2 — Code Objects (co_* attributes)")
print("=" * 65)

def greet(name: str, times: int = 3) -> str:
    greeting = f"Hello, {name}!"
    return " ".join([greeting] * times)

code = greet.__code__
print(f"co_name       = {code.co_name!r}")
print(f"co_filename   = {code.co_filename!r}")
print(f"co_firstlineno= {code.co_firstlineno}")
print(f"co_argcount   = {code.co_argcount}")
print(f"co_varnames   = {code.co_varnames}")   # Local variables (args first)
print(f"co_consts     = {code.co_consts}")     # Literal constants
print(f"co_stacksize  = {code.co_stacksize}")  # Max stack depth needed

# Nested functions have nested code objects
def outer(n):
    def inner(x):
        return x * n  # n is a closure variable
    return inner

outer_code = outer.__code__
print(f"\nouter co_varnames  = {outer_code.co_varnames}")
print(f"outer co_cellvars  = {outer_code.co_cellvars}")   # n: passed to inner via cell

inner_fn = outer(5)
inner_code = inner_fn.__code__
print(f"inner co_freevars  = {inner_code.co_freevars}")   # n: received from outer


# ============================================================================
# SECTION 3 — LOAD_FAST vs LOAD_GLOBAL vs LOAD_DEREF
# ============================================================================
print("\n" + "=" * 65)
print("SECTION 3 — LOAD_FAST vs LOAD_GLOBAL vs LOAD_DEREF")
print("=" * 65)

MODULE_CONST = 42  # Module-level (global)

def show_load_difference():
    local_var = 10            # LOAD_FAST — array index, fastest
    x = local_var             # LOAD_FAST
    y = MODULE_CONST          # LOAD_GLOBAL — dict lookup (slightly slower)
    return x + y

print("Function with local + global variable:")
dis.dis(show_load_difference)

def make_closure(n):
    def inner():
        return n * 2          # LOAD_DEREF — cell object lookup
    return inner

print("\nClosure (inner function accessing outer 'n'):")
dis.dis(make_closure(3))

# Performance explanation in plain terms
print("""
LOAD_FAST  : co_varnames[i] → direct array index → O(1), no hash
LOAD_GLOBAL: globals()['name'] → dict lookup → slightly slower
LOAD_DEREF : cell.cell_contents → indirect pointer → used for closures
""")

# Benchmark: local vs global access
import time

GLOBAL_VAL = 100

def access_global_many():
    total = 0
    for _ in range(1_000_000):
        total += GLOBAL_VAL   # LOAD_GLOBAL each iteration
    return total

def access_local_many():
    local_val = GLOBAL_VAL   # One LOAD_GLOBAL, then only LOAD_FAST
    total = 0
    for _ in range(1_000_000):
        total += local_val   # LOAD_FAST — faster loop body
    return total

t1 = time.perf_counter(); access_global_many(); t_global = time.perf_counter() - t1
t1 = time.perf_counter(); access_local_many();  t_local  = time.perf_counter() - t1
print(f"Global access 1M times: {t_global*1000:.1f}ms")
print(f"Local  access 1M times: {t_local*1000:.1f}ms")
print(f"Speedup: {t_global/t_local:.2f}x (local vars are faster)")


# ============================================================================
# SECTION 4 — PEEPHOLE OPTIMIZER: Constant Folding
# ============================================================================
print("\n" + "=" * 65)
print("SECTION 4 — CPython Peephole Optimizer (Constant Folding)")
print("=" * 65)

# Constant expressions are computed at compile time, not runtime
def constant_expressions():
    x = 2 * 3 * 7        # Folded to 42 at compile time
    y = "Hello " + "World"  # Folded to "Hello World"
    z = (1, 2) + (3, 4)  # Folded to (1, 2, 3, 4)
    return x, y, z

code = constant_expressions.__code__
print(f"co_consts = {code.co_consts}")  # Should show 42, 'Hello World', (1,2,3,4)
print("\nBytecode for constant_expressions:")
dis.dis(constant_expressions)
# You'll see LOAD_CONST 42 — no BINARY_MULTIPLY!


# ============================================================================
# SECTION 5 — MEMBERSHIP TEST OPTIMIZATION: set vs list
# ============================================================================
print("\n" + "=" * 65)
print("SECTION 5 — {1,2,3} vs [1,2,3] in Membership Tests")
print("=" * 65)

def check_with_set(x):
    return x in {1, 2, 3, 4, 5}  # Frozenset at compile time!

def check_with_list(x):
    return x in [1, 2, 3, 4, 5]  # New list created every call

print("Set membership bytecode (constants are frozenset):")
dis.dis(check_with_set)
print("\nList membership bytecode (BUILD_LIST each time):")
dis.dis(check_with_list)

# Performance proof
import timeit
t_set  = timeit.timeit("99 in {1,2,3,4,5}", number=2_000_000)
t_list = timeit.timeit("99 in [1,2,3,4,5]", number=2_000_000)
print(f"\nSet  membership 2M times: {t_set:.3f}s")
print(f"List membership 2M times: {t_list:.3f}s")
print(f"Set is {t_list/t_set:.1f}x faster (frozenset constant, not rebuilt each time)")


# ============================================================================
# SECTION 6 — AST: One Level Above Bytecode
# ============================================================================
print("\n" + "=" * 65)
print("SECTION 6 — AST (Abstract Syntax Tree)")
print("=" * 65)

source = "x * 2 + y"   # eval mode needs a single expression (no assignment)
tree = ast.parse(source, mode="eval")
print(f"AST for '{source}':")
print(ast.dump(tree, indent=2))

# Simple AST use: count function calls
source2 = """
def process(data):
    items = sorted(data)
    result = list(map(str, items))
    return result
"""
tree2 = ast.parse(source2)

class CallCounter(ast.NodeVisitor):
    def __init__(self):
        self.calls = []

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            self.calls.append(node.func.id)
        self.generic_visit(node)

counter = CallCounter()
counter.visit(tree2)
print(f"\nFunction calls in process(): {counter.calls}")  # ['sorted', 'list', 'map', 'str']


# ============================================================================
# SECTION 7 — .pyc FILES: Cached Bytecode
# ============================================================================
print("\n" + "=" * 65)
print("SECTION 7 — .pyc Files and importlib.util")
print("=" * 65)

import importlib.util
import os
import tempfile

# Check where .pyc would be cached for this file
source_path = __file__ if __file__.endswith(".py") else __file__ + ".py"
try:
    cache_path = importlib.util.cache_from_source(source_path)
    print(f"Source:     {os.path.basename(source_path)}")
    print(f"Cache (.pyc): {os.path.basename(cache_path)}")
    print(f"Cache dir:  {os.path.dirname(cache_path)}")
    print(f".pyc exists: {os.path.exists(cache_path)}")
except Exception as e:
    print(f"(Cache path: {e})")

# Python version encoding in .pyc path
print(f"\nPython {sys.version_info.major}.{sys.version_info.minor}: .pyc stored in __pycache__/")
print("Magic number in .pyc header links pyc to specific Python version.")
print("If Python upgrades → old .pyc invalid → recompiled automatically.")

# dis.code_info: human summary of a code object
print("\ndis.code_info(add):")
print(dis.code_info(add))


# ============================================================================
# BREAK-IT — Bytecode Gotchas
# ============================================================================
print("\n" + "=" * 65)
print("BREAK-IT — Common Bytecode/Compilation Gotchas")
print("=" * 65)

# BUG 1: UnboundLocalError — Python scans WHOLE function body at compile time
x = "global"
def gotcha_unbound():
    # Python sees `x = ...` below → marks x as LOCAL at compile time
    # But at runtime, LOAD_FAST x BEFORE assignment → UnboundLocalError
    try:
        print(x)   # UnboundLocalError — not global access!
        x = "local"
    except UnboundLocalError as e:
        print(f"Bug 1 — UnboundLocalError: {e}")
        print("  Python compile-time marked 'x' as local — LOAD_FAST before assignment")

gotcha_unbound()

# Fix: use `global x` or `nonlocal x`
def gotcha_fixed():
    global x
    print(x)   # LOAD_GLOBAL x — works
    x = "modified global"

gotcha_fixed()
x = "global"  # Reset

# BUG 2: Sensitive data in co_consts (security!)
def check_password(user_input):
    SECRET = "hunter2"     # THIS IS IN co_consts!
    return user_input == SECRET

print(f"\nBug 2 — Secrets in bytecode: {check_password.__code__.co_consts}")
print("  'hunter2' visible in co_consts — never hardcode secrets in source!")
print("  Fix: load from env var / vault at runtime")

# BUG 3: Expecting constant folding for non-literals
def not_folded(n):
    x = n * 2   # n is a variable — NOT folded at compile time
    return x

print(f"\nBug 3 — n * 2 not folded (n is variable):")
dis.dis(not_folded)
# You'll see BINARY_OP — no fold because n is runtime value


# ============================================================================
# TODO — Bytecode profiler
# ============================================================================
"""
Implement a simple function that:
  1. Takes any callable as input
  2. Disassembles it (use dis.get_instructions())
  3. Counts occurrences of each opcode name
  4. Returns a dict: {opcode_name: count} sorted by count descending
  5. Prints a summary showing the 5 most common opcodes

Use dis.get_instructions(func) — returns an iterator of Instruction namedtuples
  Each Instruction has: .opname (str), .opcode (int), .argval, .offset, etc.

Verify with `add` function:
  opcode_profile(add)
  → should show LOAD_FAST, BINARY_OP, STORE_FAST, RETURN_VALUE, RESUME etc.

Bonus: add a flag `show_constants: bool` that also prints co_consts when True
"""

if __name__ == "__main__":
    print("\n" + "=" * 65)
    print("RUN: python 35_bytecode_and_dis_module.py")
    print("Sab sections automatically run hote hain above.")
    print("TODO: Implement opcode_profile() at the bottom.")
    print("=" * 65)
