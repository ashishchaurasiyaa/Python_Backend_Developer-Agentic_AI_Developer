"""
╔══════════════════════════════════════════════════════════════╗
║  PYTHON COMPLETE PRACTICAL — Section 01                      ║
║  Topic: Variables, Data Types, Type Hints                    ║
║  Level: Basic → Production                                   ║
╚══════════════════════════════════════════════════════════════╝
"""

# ─────────────────────────────────────────────────────────────
# 1. VARIABLES — assignment, naming, multiple assignment
# ─────────────────────────────────────────────────────────────

# Basic assignment
name = "Alice"
age  = 30
score = 98.5
is_active = True

# Multiple assignment
x = y = z = 0

# Tuple unpacking
a, b, c = 1, 2, 3
first, *rest = [10, 20, 30, 40, 50]   # star unpacking
*head, last  = [10, 20, 30, 40, 50]

print(f"first={first}, rest={rest}")   # 10, [20,30,40,50]
print(f"head={head}, last={last}")     # [10,20,30,40], 50

# Swap without temp variable
a, b = 10, 20
a, b = b, a
print(f"After swap: a={a}, b={b}")

# Constants — UPPER_CASE by convention (no true constant in Python)
MAX_TOKENS: int = 4096
DEFAULT_MODEL: str = "gpt-4"
API_TIMEOUT: float = 30.0


# ─────────────────────────────────────────────────────────────
# 2. ALL DATA TYPES
# ─────────────────────────────────────────────────────────────

# ── Numeric ──────────────────────────────────────────────────
i: int   = 42
f: float = 3.14
c: complex = 2 + 3j

# int operations
print(10 // 3)     # 3  — floor division
print(10 % 3)      # 1  — modulo
print(2 ** 10)     # 1024 — exponentiation
print(abs(-7))     # 7
print(divmod(10, 3))  # (3, 1) — quotient and remainder

# float precision issue — critical for money/AI cost
print(0.1 + 0.2)           # 0.30000000000000004 — WRONG!
from decimal import Decimal
print(Decimal("0.1") + Decimal("0.2"))  # 0.3 — CORRECT for money

# Large integers — Python handles them natively
big = 2 ** 100
print(big)

# Numeric literals with underscores (readability)
million = 1_000_000
rate    = 0.001_5

# ── String ───────────────────────────────────────────────────
s1: str = "single quotes"
s2: str = 'double quotes'
s3: str = """triple
quoted
string"""

# String is immutable — operations return new string
name = "python"
print(name.upper())          # PYTHON
print(name.capitalize())     # Python
print(name[0])               # p (indexing)
print(name[-1])              # n (negative indexing)
print(name[1:4])             # yth (slicing)
print(name[::-1])            # nohtyp (reverse)

# Raw string — backslash treated literally
path = r"C:\Users\dev\projects"
regex = r"\d+\.\d+"

# ── Boolean ──────────────────────────────────────────────────
t: bool = True
f_val: bool = False

# Truthy / Falsy — CRITICAL to know
falsy_values = [False, None, 0, 0.0, "", [], {}, set(), ()]
truthy_examples = [True, 1, -1, "a", [0], {"k": "v"}]

# bool is a subclass of int
print(True + True)    # 2
print(True * 5)       # 5
print(int(True))      # 1

# ── None ─────────────────────────────────────────────────────
result = None
# Always check None with 'is', never '=='
if result is None:
    print("No result yet")

# ── Bytes ────────────────────────────────────────────────────
raw: bytes = b"hello"
raw2: bytes = bytes([72, 101, 108, 108, 111])
print(raw)
print(raw.decode("utf-8"))   # "hello"
text = "hello"
print(text.encode("utf-8"))  # b'hello'


# ─────────────────────────────────────────────────────────────
# 3. TYPE CHECKING — type(), isinstance(), issubclass()
# ─────────────────────────────────────────────────────────────

value = 42
print(type(value))             # <class 'int'>
print(type(value).__name__)    # int

# isinstance — checks including subclasses (PREFERRED)
print(isinstance(True, int))       # True — bool IS int
print(isinstance(True, bool))      # True
print(isinstance(42, (int, float))) # True — tuple of types

# issubclass
print(issubclass(bool, int))       # True
print(issubclass(int, object))     # True — everything inherits object


# ─────────────────────────────────────────────────────────────
# 4. TYPE CONVERSION (CASTING)
# ─────────────────────────────────────────────────────────────

# Explicit conversion
print(int("42"))         # 42
print(int(3.9))          # 3 — truncates (not rounds!)
print(float("3.14"))     # 3.14
print(str(100))          # "100"
print(bool(0))           # False
print(bool(""))          # False
print(list("abc"))       # ['a', 'b', 'c']
print(tuple([1, 2, 3]))  # (1, 2, 3)
print(set([1, 1, 2, 3])) # {1, 2, 3}

# int with base
print(int("ff", 16))    # 255 — hex to int
print(int("1010", 2))   # 10  — binary to int
print(int("52", 8))     # 42  — octal to int

# Number to other bases
print(bin(10))    # 0b1010
print(oct(42))    # 0o52
print(hex(255))   # 0xff


# ─────────────────────────────────────────────────────────────
# 5. TYPE HINTS — from basic to production
# ─────────────────────────────────────────────────────────────

from typing import Optional, Union, Any, Final

# Basic type hints (Python 3.9+ style — preferred)
def greet(name: str, age: int = 0) -> str:
    return f"Hello {name}, age {age}"

# Complex type hints
def process(
    items: list[str],
    config: dict[str, int],
    callback: Optional[callable] = None,
) -> tuple[bool, str]:
    return True, "done"

# Union — multiple types (Python 3.10+ style)
def parse(value: str | int | None) -> str:
    return str(value)

# Final — constant
MAX_SIZE: Final[int] = 100

# Variable annotation without assignment (declare intent)
user_id: int
session_token: str | None

# Type alias
JsonDict = dict[str, Any]
TokenList = list[int]
ModelName = str

def call_model(model: ModelName, tokens: TokenList) -> JsonDict:
    return {"model": model, "tokens": tokens}


# ─────────────────────────────────────────────────────────────
# 6. IDENTITY vs EQUALITY vs COMPARISON
# ─────────────────────────────────────────────────────────────

# == checks VALUE equality
# is checks IDENTITY (same object in memory)

a = [1, 2, 3]
b = [1, 2, 3]
c = a

print(a == b)    # True  — same values
print(a is b)    # False — different objects
print(a is c)    # True  — same object

# Integer caching — CPython caches -5 to 256
x = 256
y = 256
print(x is y)   # True — cached

x = 257
y = 257
print(x is y)   # False — NOT cached (implementation detail!)

# RULE: use 'is' only for None, True, False
# RULE: use '==' for value comparisons


# ─────────────────────────────────────────────────────────────
# 7. GLOBAL vs LOCAL vs NONLOCAL scope
# ─────────────────────────────────────────────────────────────

total = 0  # global

def add_to_total(value: int) -> None:
    global total           # declare intent to modify global
    total += value

add_to_total(10)
add_to_total(20)
print(f"Global total: {total}")   # 30


def outer():
    count = 0

    def inner():
        nonlocal count     # access outer's variable
        count += 1
        return count

    return inner

counter = outer()
print(counter())   # 1
print(counter())   # 2
print(counter())   # 3


# ─────────────────────────────────────────────────────────────
# 8. PRODUCTION PATTERNS — named constants, config class
# ─────────────────────────────────────────────────────────────

from dataclasses import dataclass
from typing import ClassVar

@dataclass(frozen=True)
class ModelConstants:
    """Immutable model configuration constants."""
    GPT4: ClassVar[str]          = "gpt-4"
    GPT35: ClassVar[str]         = "gpt-3.5-turbo"
    CLAUDE_OPUS: ClassVar[str]   = "claude-3-opus-20240229"
    CLAUDE_SONNET: ClassVar[str] = "claude-3-5-sonnet-20241022"

    MAX_TOKENS_GPT4: ClassVar[int]   = 8192
    MAX_TOKENS_CLAUDE: ClassVar[int] = 200000
    DEFAULT_TEMPERATURE: ClassVar[float] = 0.7


print(f"\nDefault model: {ModelConstants.GPT4}")
print(f"Claude context: {ModelConstants.MAX_TOKENS_CLAUDE:,} tokens")


# ─────────────────────────────────────────────────────────────
# INTERVIEW QUESTIONS
# ─────────────────────────────────────────────────────────────
"""
Q: What is the difference between == and is?
A: == checks value equality. 'is' checks identity (same memory address).
   Use 'is' only for None, True, False comparisons.

Q: What are truthy/falsy values in Python?
A: Falsy: False, None, 0, 0.0, "", [], {}, set(), ()
   Everything else is truthy.

Q: Why should you use Decimal instead of float for money?
A: Floating point arithmetic has precision errors (0.1 + 0.2 = 0.300...04).
   Decimal provides exact decimal arithmetic.

Q: What is the difference between global and nonlocal?
A: global modifies a module-level variable from inside a function.
   nonlocal modifies an enclosing (outer) function's variable.

Q: What does type hinting do at runtime?
A: Nothing — type hints are purely informational at runtime.
   They are used by mypy, IDEs, and Pydantic for static analysis.
"""
