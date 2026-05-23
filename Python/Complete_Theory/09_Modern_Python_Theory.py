"""
╔══════════════════════════════════════════════════════════════════════════════╗
║   PYTHON COMPLETE THEORY — File 09                                           ║
║   Topic: Modern Python Features (3.8 - 3.12+)                               ║
║   Format: WHAT → WHY → HOW → REAL LIFE → PRODUCTION CODE → Q&A              ║
╚══════════════════════════════════════════════════════════════════════════════╝

Topics Covered:
  A. Walrus Operator (:=) — assign-and-return in expressions
  B. match-case (3.10+) — structural pattern matching
  C. dataclasses — zero-boilerplate data classes
  D. dataclasses advanced — field(), __post_init__, frozen, slots, KW_ONLY
  E. f-string improvements — debugging with =, nested specs (3.8+, 3.12+)
  F. Positional-only parameters (/) — 3.8+
  G. Exception groups and except* — 3.11+
  H. tomllib (TOML support) — 3.11+
  I. Self type — 3.11+
  J. typing.override — 3.12+
  K. pathlib — modern file handling
  L. contextlib tools — suppress, ExitStack, redirect_stdout
"""

import sys
print(f"Python version: {sys.version}")


# ══════════════════════════════════════════════════════════════════════════════
# PART A: WALRUS OPERATOR := (Python 3.8+)
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS THE WALRUS OPERATOR?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

:= (walrus/assignment expression): ASSIGNS a value AND RETURNS it in one expression.
Named "walrus" because := looks like a walrus with tusks 🦭

WHY?
  Eliminates the pattern of: compute → check → use again.

  BEFORE (Python 3.7 and earlier):
    data = read_data()           # compute
    if data:                     # check
        process(data)            # use again — computed twice or stored as extra var

  WITH walrus (Python 3.8+):
    if data := read_data():      # assign AND check in one line
        process(data)            # data already bound

  Especially useful in: while loops, comprehensions, repeated function calls.

HOW:
  Syntax: (name := expression)
  - The parentheses are usually needed to avoid ambiguity
  - name is bound to expression's value in the enclosing scope
  - The expression evaluates to the ASSIGNED VALUE

WHEN TO USE:
  ✅ while loops: while chunk := f.read(8192): process(chunk)
  ✅ Avoid recomputing: if m := re.search(pattern, text): use m.group()
  ✅ Comprehensions with complex computation: [y for x in data if (y := expensive(x)) > 0]
  ❌ Overuse in complex expressions makes code harder to read
  ❌ Don't use just to save a line if it hurts readability

REAL LIFE ANALOGY:
  Walrus = Taking a number at a bakery AND immediately sitting down:
  Old way: take_number() → check if called → if called: use_number()
  Walrus:  if (number := take_number()) is ready: sit_down_with(number)
"""

import re
import time

print("=== WALRUS OPERATOR :=  ===")

# Example 1: while loop — read in chunks
def process_stream(data: str, chunk_size: int = 10):
    """Process data in chunks — classic walrus use case."""
    import io
    stream = io.StringIO(data)
    results = []
    while chunk := stream.read(chunk_size):  # assign AND check
        results.append(chunk.upper())
    return results

text = "Hello World, Python 3.8 is awesome!"
chunks = process_stream(text)
print(f"Chunks: {chunks}")


# Example 2: regex match — avoid calling match twice
def extract_model_info(log_line: str) -> dict | None:
    """Parse log line if it matches expected format."""
    pattern = r"model=(\w+-[\w.-]+)\s+tokens=(\d+)\s+latency=(\d+)ms"
    if m := re.search(pattern, log_line):
        return {
            "model": m.group(1),
            "tokens": int(m.group(2)),
            "latency_ms": int(m.group(3)),
        }
    return None

log1 = "INFO model=gpt-4 tokens=450 latency=1250ms user=u001"
log2 = "DEBUG some other log line without model info"

if info := extract_model_info(log1):
    print(f"Model info: {info}")
else:
    print("No model info found")

if info := extract_model_info(log2):
    print(f"Model info: {info}")
else:
    print(f"No model info in: {log2[:30]}...")


# Example 3: comprehension with computation
def tokenize(text: str) -> list[str]:
    return text.lower().split()

documents = [
    "Python is awesome for AI development",
    "x",  # too short
    "asyncio enables concurrent I/O operations",
    "hi",  # too short
    "Agentic AI uses tools like web search and code execution",
]

# Filter + compute in one comprehension (without double tokenization)
useful_docs = [
    tokens
    for doc in documents
    if len(tokens := tokenize(doc)) > 3  # tokenize ONCE, check length, keep tokens
]

print(f"\nUseful token lists: {len(useful_docs)} documents")
for tokens in useful_docs:
    print(f"  {tokens[:4]}...")


# Example 4: Environment setup pattern
import os

def get_config() -> dict:
    """Walrus for environment variable with fallback."""
    config = {}
    if api_key := os.environ.get("OPENAI_API_KEY"):
        config["api_key"] = api_key
        print(f"  ✅ API key found ({len(api_key)} chars)")
    else:
        print(f"  ⚠️  No API key — using development mode")
        config["api_key"] = "dev_key"

    if model := os.environ.get("LLM_MODEL", ""):
        config["model"] = model
    else:
        config["model"] = "gpt-4"

    return config

cfg = get_config()
print(f"Config: {cfg}")


"""
Q&A — Walrus Operator

Q1: Can the walrus operator replace regular assignment?
A:  NO — walrus is for EXPRESSIONS (inside conditions, comprehensions, while).
    You can't use := at statement level:
    x := 5   # SyntaxError! Use x = 5 instead.
    It's specifically for "assign as part of a larger expression."

Q2: What is the scope of a walrus-assigned variable?
A:  The variable leaks into the ENCLOSING scope (not just the expression).
    In a comprehension: variable is available AFTER the comprehension.
    In a while condition: variable is available after the loop exits.

    [y for x in range(5) if (y := x*2) > 4]
    print(y)  # 8 — last assigned value is accessible after!
"""


# ══════════════════════════════════════════════════════════════════════════════
# PART B: match-case — STRUCTURAL PATTERN MATCHING (Python 3.10+)
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS match-case?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

match-case (Python 3.10+): STRUCTURAL PATTERN MATCHING.
More powerful than switch/case in other languages.
Matches on STRUCTURE (type + shape), not just equality.

WHY?
  if/elif chains for type/structure checks are verbose and hard to read.
  match-case provides cleaner syntax AND more powerful matching:
    - Match by type
    - Match by structure (dict shape, list shape)
    - Capture variables from matched structure
    - Guard conditions (if clauses)
    - OR patterns (A | B)

PATTERN TYPES:
  Literal:   case 42:, case "hello":
  Variable:  case x:     (captures any value into x)
  Wildcard:  case _:     (matches anything, doesn't capture)
  Sequence:  case [a, b]:  (matches list/tuple with exactly 2 items)
  Mapping:   case {"role": "user", "content": content}:  (matches dict)
  Class:     case Point(x=x, y=y):  (matches class instance)
  OR:        case 400 | 401 | 403:  (matches any of these)
  Guard:     case x if x > 0:  (matches AND checks condition)
  AS:        case [first, *rest] as full:  (capture whole and parts)

REAL LIFE ANALOGY:
  match-case = Post office sorting machine:
  Package arrives → machine checks:
  - Is it small + "fragile" sticker? → gentle conveyor
  - Is it large + "liquid" label?   → special handling
  - Has "priority mail" marking?    → express lane
  - Anything else?                  → standard lane
  Each check is on the STRUCTURE/CONTENT, not just a number.
"""

print("\n=== match-case (Structural Pattern Matching) ===")

# Example 1: LLM event handling (most realistic AI use case)
def handle_llm_event(event: dict) -> str:
    match event:
        case {"type": "token", "content": token, "model": model}:
            return f"[Stream] {model}: '{token}'"

        case {"type": "tool_call", "name": name, "args": args}:
            return f"[Tool] Calling {name!r} with args: {args}"

        case {"type": "error", "code": 429, "message": msg}:
            return f"[RateLimit] {msg}"

        case {"type": "error", "code": code, "message": msg} if code >= 500:
            return f"[ServerError {code}] {msg}"

        case {"type": "error", "code": code}:
            return f"[Error {code}] Unknown error"

        case {"type": "finish", "reason": "stop"}:
            return "[Done] Completed normally"

        case {"type": "finish", "reason": "length"}:
            return "[Done] Hit token limit"

        case {"type": str(event_type), **rest}:
            return f"[Unknown event] type={event_type!r}"

        case _:
            return f"[Invalid] Not an event dict"


events = [
    {"type": "token", "content": "Hello", "model": "gpt-4"},
    {"type": "tool_call", "name": "web_search", "args": {"query": "Python async"}},
    {"type": "error", "code": 429, "message": "Rate limit exceeded"},
    {"type": "error", "code": 503, "message": "Server overloaded"},
    {"type": "finish", "reason": "stop"},
    {"type": "finish", "reason": "length"},
    {"type": "custom_event", "data": [1, 2, 3]},
    "not a dict",
]

print("LLM event handling:")
for evt in events:
    result = handle_llm_event(evt)
    print(f"  {result}")


# Example 2: HTTP status pattern matching
def describe_http_status(status: int) -> str:
    match status:
        case 200 | 201 | 202:
            return "✅ Success"
        case 301 | 302 | 307 | 308:
            return "↩️  Redirect"
        case 400:
            return "❌ Bad Request"
        case 401 | 403:
            return "🔒 Auth Error"
        case 404:
            return "🔍 Not Found"
        case 429:
            return "⏱️  Rate Limited"
        case code if 400 <= code < 500:
            return f"❌ Client Error ({code})"
        case code if 500 <= code < 600:
            return f"💥 Server Error ({code})"
        case _:
            return f"❓ Unknown ({status})"


print(f"\nHTTP status handling:")
for code in [200, 201, 301, 401, 404, 429, 422, 503, 100]:
    print(f"  {code}: {describe_http_status(code)}")


# Example 3: Sequence matching — command parsing
def parse_command(tokens: list[str]) -> str:
    match tokens:
        case []:
            return "Empty command"
        case ["quit"] | ["exit"] | ["q"]:
            return "Goodbye!"
        case ["help"] | ["help", *_]:
            return "Showing help..."
        case ["agent", "create", name, model]:
            return f"Creating agent {name!r} with model {model!r}"
        case ["agent", "create", name]:
            return f"Creating agent {name!r} with default model"
        case ["agent", action, name, *args]:
            return f"Agent action {action!r} on {name!r} with args: {args}"
        case ["model", "switch", new_model]:
            return f"Switching to model {new_model!r}"
        case [cmd, *args]:
            return f"Unknown command {cmd!r}, args: {args}"


print(f"\nCommand parsing:")
commands = [
    [],
    ["quit"],
    ["help", "agents"],
    ["agent", "create", "researcher", "gpt-4"],
    ["agent", "create", "writer"],
    ["agent", "run", "researcher", "--verbose", "--timeout=30"],
    ["model", "switch", "claude-3-sonnet"],
    ["unknown", "arg1", "arg2"],
]
for cmd in commands:
    print(f"  {cmd} → {parse_command(cmd)}")


# Example 4: Class pattern matching (dataclass)
from dataclasses import dataclass
from typing import Union


@dataclass
class UserMessage:
    content: str
    user_id: str

@dataclass
class SystemMessage:
    content: str

@dataclass
class ToolResult:
    tool_name: str
    result: str
    error: str | None = None


def process_message(msg: Union[UserMessage, SystemMessage, ToolResult]) -> str:
    match msg:
        case UserMessage(content=content, user_id=uid) if len(content) > 100:
            return f"[User {uid}] Long message ({len(content)} chars): {content[:50]}..."
        case UserMessage(content=content, user_id=uid):
            return f"[User {uid}]: {content}"
        case SystemMessage(content=content):
            return f"[System]: {content}"
        case ToolResult(tool_name=name, error=str(err)):
            return f"[Tool {name}] ERROR: {err}"
        case ToolResult(tool_name=name, result=result):
            return f"[Tool {name}] OK: {result}"


print(f"\nClass pattern matching:")
messages: list[Union[UserMessage, SystemMessage, ToolResult]] = [
    UserMessage("Hello!", "user_001"),
    UserMessage("This is a very long message that exceeds our threshold. " * 3, "user_002"),
    SystemMessage("You are a helpful assistant."),
    ToolResult("web_search", "Python was created in 1991"),
    ToolResult("db_query", "", "Connection timeout"),
]
for msg in messages:
    print(f"  {process_message(msg)}")


"""
Q&A — match-case

Q1: Is match-case the same as switch/case in C/Java?
A:  No — much more powerful:
    - switch/case: equality check against literal values
    - match-case: structural matching (type, shape, nested structure, capture)
    - Can destructure and bind variables from the matched structure
    - Guard conditions (if) on top of pattern matching
    - OR patterns (A | B)
    - Wildcard (_) and capture variables (name)

Q2: Does match-case use == or is for comparison?
A:  For literals: uses == (value equality)
    For types: isinstance() check
    For sequences/mappings: structural matching (not identity)
    Exception: None, True, False — use identity (is) in matching.

Q3: What is the difference between case x and case _?
A:  case x:  captures the value and binds it to name x (can use x in body)
    case _:  wildcard — matches anything but does NOT bind to any name
    Use _ when you don't need the value, x when you do.
"""


# ══════════════════════════════════════════════════════════════════════════════
# PART C: DATACLASSES — ZERO-BOILERPLATE DATA CLASSES
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT ARE DATACLASSES?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass: decorator that AUTO-GENERATES boilerplate methods from type annotations:
  __init__, __repr__, __eq__ (optionally: __hash__, __lt__, __le__, __gt__, __ge__)

WHY?
  BEFORE dataclasses (manual boilerplate):
    class Point:
        def __init__(self, x: float, y: float):
            self.x = x
            self.y = y
        def __repr__(self):
            return f"Point(x={self.x!r}, y={self.y!r})"
        def __eq__(self, other):
            if type(other) is type(self):
                return (self.x, self.y) == (other.x, other.y)
            return NotImplemented
    # 15 lines for a simple data holder!

  WITH @dataclass:
    @dataclass
    class Point:
        x: float
        y: float
    # 3 lines — same functionality!

@dataclass PARAMETERS:
  @dataclass(
      init=True,       # generate __init__
      repr=True,       # generate __repr__
      eq=True,         # generate __eq__
      order=False,     # generate __lt__, __le__, __gt__, __ge__
      frozen=False,    # if True: immutable (no setattr after init)
      slots=False,     # if True: use __slots__ (Python 3.10+)
      kw_only=False,   # if True: all fields are keyword-only (Python 3.10+)
  )

REAL LIFE ANALOGY:
  @dataclass = Standardized form template:
  Without it: you draw a new form from scratch each time (manual boilerplate)
  With it: fill in field names, the template auto-generates all standard sections
"""

from dataclasses import dataclass, field, KW_ONLY
from datetime import datetime
from typing import ClassVar

print("\n=== DATACLASSES ===")


# Basic dataclass
@dataclass
class LLMMessage:
    role: str
    content: str
    created_at: datetime = field(default_factory=datetime.now)


# All features
@dataclass(order=True)    # enables __lt__ etc. for sorting
class TokenUsage:
    prompt_tokens: int
    completion_tokens: int
    model: str = "gpt-4"
    cached: bool = False

    # Computed field — not in __init__ (init=False)
    total_tokens: int = field(init=False, repr=True)

    def __post_init__(self):
        """Called after __init__ — for validation and computed fields."""
        if self.prompt_tokens < 0:
            raise ValueError(f"prompt_tokens must be >= 0")
        if self.completion_tokens < 0:
            raise ValueError(f"completion_tokens must be >= 0")
        self.total_tokens = self.prompt_tokens + self.completion_tokens  # computed

    def cost(self, price_per_1k: float = 0.03) -> float:
        return self.total_tokens / 1000 * price_per_1k


# Production: agent state
@dataclass
class AgentState:
    agent_id: str
    model: str
    task: str
    messages: list[dict] = field(default_factory=list)   # mutable default!
    metadata: dict = field(default_factory=dict)
    is_running: bool = field(default=False, repr=False)  # excluded from repr
    _internal_counter: int = field(default=0, init=False, repr=False, compare=False)

    # Class variable (not a field)
    VERSION: ClassVar[str] = "1.0"

    def add_message(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})
        self._internal_counter += 1

    def message_count(self) -> int:
        return len(self.messages)


# Demonstration
print(f"Basic dataclass:")
msg = LLMMessage(role="user", content="Hello!")
print(f"  {msg}")          # auto __repr__
print(f"  {msg == LLMMessage('user', 'Hello!', msg.created_at)}")  # auto __eq__

print(f"\nTokenUsage with __post_init__:")
usage = TokenUsage(prompt_tokens=150, completion_tokens=300, model="gpt-4")
print(f"  {usage}")
print(f"  total_tokens: {usage.total_tokens}")   # computed in __post_init__
print(f"  cost: ${usage.cost():.4f}")

print(f"\nTokenUsage ordering (sorted by total_tokens):")
usages = [
    TokenUsage(100, 200),
    TokenUsage(50, 100),
    TokenUsage(500, 1000),
    TokenUsage(10, 20),
]
sorted_usages = sorted(usages)   # uses __lt__ from order=True
for u in sorted_usages:
    print(f"  total={u.total_tokens}")

print(f"\nAgentState:")
state = AgentState(agent_id="agent_001", model="gpt-4", task="research")
state.add_message("user", "What is Python?")
state.add_message("assistant", "Python is a programming language.")
print(f"  {state}")
print(f"  Messages: {state.message_count()}")

# Validation in __post_init__
try:
    bad_usage = TokenUsage(prompt_tokens=-10, completion_tokens=100)
except ValueError as e:
    print(f"\n  Validation caught: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# PART D: DATACLASS ADVANCED — frozen, slots, KW_ONLY
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ADVANCED DATACLASS FEATURES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

frozen=True:
  Immutable dataclass — after __init__, no attribute can be changed.
  Also auto-generates __hash__ (because eq=True + frozen=True → hashable).
  Use for: value objects, dict keys, set members, config snapshots.

slots=True (Python 3.10+):
  Uses __slots__ for memory efficiency.
  Gives ~30-50% memory reduction for many instances.
  Combines well with frozen=True.

KW_ONLY (Python 3.10+):
  Fields after KW_ONLY sentinel MUST be passed as keyword arguments.
  Prevents accidental positional order confusion.

field() options:
  default=          → default value
  default_factory=  → callable that returns default (for mutable defaults)
  init=False        → not in __init__ (computed or set in __post_init__)
  repr=False        → excluded from __repr__
  compare=False     → excluded from __eq__ and ordering
  hash=None         → excluded from __hash__ (if separately defined)
"""

print("\n=== DATACLASS ADVANCED ===")


# frozen=True — immutable, hashable
@dataclass(frozen=True, order=True)
class ModelConfig:
    """Immutable model configuration — can be dict key or set member."""
    model: str
    temperature: float = 0.7
    max_tokens: int = 2048

    def with_temperature(self, t: float) -> "ModelConfig":
        """Return modified copy — can't mutate, so create new."""
        from dataclasses import replace
        return replace(self, temperature=t)


cfg1 = ModelConfig("gpt-4", temperature=0.5)
cfg2 = ModelConfig("gpt-4", temperature=0.5)
cfg3 = ModelConfig("claude-3", temperature=0.7)

print(f"frozen: {cfg1}")
print(f"cfg1 == cfg2: {cfg1 == cfg2}")
print(f"cfg1 is cfg2: {cfg1 is cfg2}")  # False — different objects
print(f"hash(cfg1) == hash(cfg2): {hash(cfg1) == hash(cfg2)}")  # True — same hash

# Use as dict key (hashable because frozen)
config_cache: dict[ModelConfig, str] = {}
config_cache[cfg1] = "cached response"
print(f"Used as dict key: {config_cache[cfg2]}")  # cfg2 == cfg1, same hash

try:
    cfg1.temperature = 1.0  # frozen — cannot modify
except Exception as e:
    print(f"Cannot modify frozen: {e}")

# Modified copy via dataclasses.replace()
cfg4 = cfg1.with_temperature(1.5)
print(f"Modified copy: {cfg4}")


# slots=True for memory efficiency (Python 3.10+)
if sys.version_info >= (3, 10):
    @dataclass(slots=True)
    class EmbeddingVector:
        """High-frequency object — use slots for memory."""
        document_id: str
        embedding: tuple[float, ...]
        model: str = "text-embedding-ada-002"

    vec = EmbeddingVector("doc_001", (0.1, 0.2, 0.3, 0.4))
    print(f"\nslots=True: {vec}")
    print(f"Has __slots__: {'__slots__' in EmbeddingVector.__dict__}")
    print(f"No __dict__: {'__dict__' not in dir(vec)}")


# KW_ONLY — prevent argument order confusion (Python 3.10+)
if sys.version_info >= (3, 10):
    @dataclass
    class AgentRequest:
        agent_type: str              # positional OK
        task: str                    # positional OK
        _: KW_ONLY                   # sentinel: all following must be keyword
        model: str = "gpt-4"        # keyword only!
        timeout: float = 30.0       # keyword only!
        max_retries: int = 3        # keyword only!

    # Must use keyword args for fields after KW_ONLY
    req = AgentRequest("research", "Find Python tutorials", model="claude-3", timeout=60.0)
    print(f"\nKW_ONLY: {req}")

    try:
        # This would fail — model is positional? No, KW_ONLY enforces keyword!
        req2 = AgentRequest("coding", "Write a FastAPI app", "claude-3")  # SyntaxError!
    except TypeError as e:
        print(f"  KW_ONLY enforced: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# PART E: f-STRING IMPROVEMENTS
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
F-STRING FEATURES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

f-string (3.6): f"{expression}"
f-string {=} (3.8): f"{expression=}" → prints "expression=value"
Nested format specs: f"{value:{width}.{precision}f}"
Backslash in f-string (3.12): f"{'\n'.join(items)}"

FORMAT SPEC CHEATSHEET:
  f"{3.14159:.2f}"       → "3.14"     (2 decimal places)
  f"{1234567:,}"         → "1,234,567" (thousands separator)
  f"{0.156:.1%}"         → "15.6%"    (percentage)
  f"{255:#x}"            → "0xff"     (hex with prefix)
  f"{255:#b}"            → "0b11111111" (binary with prefix)
  f"{'hi':>10}"          → "        hi" (right align, width 10)
  f"{'hi':<10}"          → "hi        " (left align)
  f"{'hi':^10}"          → "    hi    " (center align)
  f"{'hi':*^10}"         → "****hi****" (center with fill char)
  f"{42:05d}"            → "00042"    (zero-padded)
  f"{3.14!r}"            → "3.14"     (!r = repr, !s = str, !a = ascii)

DEBUGGING WITH = (3.8+):
  x = 42
  f"{x=}"    → "x=42"      (prints name AND value — great for debugging)
  f"{x=:.2f}" → "x=42.00"  (with format spec)
"""

print("\n=== f-string features ===")

# Debugging with =
temperature = 0.7312
tokens = 1_234_567
model = "gpt-4"
latency = 1234.567

print(f"{temperature=}")     # temperature=0.7312
print(f"{tokens=:,}")        # tokens=1,234,567
print(f"{model=!r}")         # model='gpt-4'

# Number formatting
price = 42.5678
rate = 0.95123

print(f"\nFormatting:")
print(f"  Price: ${price:.2f}")        # $42.57
print(f"  Big:   {tokens:,}")          # 1,234,567
print(f"  Rate:  {rate:.1%}")          # 95.1%
print(f"  Hex:   {255:#x}")            # 0xff
print(f"  Bin:   {10:#b}")             # 0b1010
print(f"  Lat:   {latency:,.0f}ms")   # 1,235ms

# Alignment
for model_name, score in [("gpt-4", 0.9524), ("claude-3", 0.9821), ("llama-3", 0.8712)]:
    print(f"  {model_name:<15} {score:.4f} {'█' * int(score * 20)}")

# Nested format specs (dynamic width/precision)
width = 15
precision = 3
value = 3.14159265
print(f"\nDynamic format: {value:{width}.{precision}f}")

# Python 3.12: backslash inside f-string
items = ["Python", "asyncio", "dataclasses"]
if sys.version_info >= (3, 12):
    formatted = f"Topics:\n{'\n'.join(f'  • {item}' for item in items)}"
else:
    items_str = "\n".join(f"  • {item}" for item in items)
    formatted = f"Topics:\n{items_str}"
print(formatted)


# ══════════════════════════════════════════════════════════════════════════════
# PART F: POSITIONAL-ONLY PARAMETERS (Python 3.8+)
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT ARE POSITIONAL-ONLY PARAMETERS?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

/ separator: parameters BEFORE / must be passed POSITIONALLY only.
* separator: parameters AFTER * must be passed as KEYWORDS only.

WHY?
  Positional-only: parameter name is an implementation detail (you can rename without breaking API)
  Keyword-only: force callers to be explicit, no accidental positional argument order bugs

HOW:
  def func(pos1, pos2, /, normal, *, kw1, kw2):
    #        ^^^          ^^^^^^     ^^^
    # positional  positional OR kw   keyword-only
    #   only                        only

  Python builtins already do this:
    len(x) — x is positional only (you can't do len(obj=x))
    sorted(iterable, /, *, key, reverse) — same
"""

print("\n=== Positional-only and Keyword-only Parameters ===")


def create_agent(
    agent_id: str,    # positional only — implementation detail
    model: str,       # positional only
    /,                # ← / separator
    task: str,        # positional OR keyword
    *,                # ← * separator
    temperature: float = 0.7,  # keyword only
    max_tokens: int = 2048,    # keyword only
) -> dict:
    return {
        "id": agent_id,
        "model": model,
        "task": task,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }


# Valid calls
r1 = create_agent("a1", "gpt-4", "research", temperature=0.5)     # positional + keyword
r2 = create_agent("a2", "claude-3", task="coding", max_tokens=4096)  # task as keyword

print(f"r1: {r1}")
print(f"r2: {r2}")

# Invalid — positional-only as keyword
try:
    create_agent(agent_id="a3", model="gpt-4", task="test")  # error: agent_id is positional-only
except TypeError as e:
    print(f"Positional-only error: {e}")

# Invalid — keyword-only as positional
try:
    create_agent("a4", "gpt-4", "task", 0.5, 1000)  # error: too many positional args
except TypeError as e:
    print(f"Keyword-only error: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# PART G: EXCEPTION GROUPS (Python 3.11+)
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT ARE EXCEPTION GROUPS?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Python 3.11+ introduces ExceptionGroup and except* syntax.

WHY?
  In async code with TaskGroup: MULTIPLE tasks might fail simultaneously.
  Old Python: only first exception was raised, others lost.
  ExceptionGroup: collect ALL exceptions, propagate ALL together.

HOW:
  Raise:   raise ExceptionGroup("description", [exc1, exc2, exc3])

  Catch:   try:
               ...
           except* ValueError as eg:  # catches ONLY ValueErrors from the group
               for e in eg.exceptions:
                   handle(e)
           except* TypeError as eg:   # catches ONLY TypeErrors from the group
               ...

REAL LIFE ANALOGY:
  ExceptionGroup = Medical report with multiple diagnoses:
  "Patient has: Diabetes, Hypertension, AND High Cholesterol"
  Not "Patient has Diabetes (others ignored)."
  Each can be treated separately (except*).
"""

print("\n=== Exception Groups (Python 3.11+) ===")

if sys.version_info >= (3, 11):
    # Creating an ExceptionGroup
    eg = ExceptionGroup("Multiple LLM errors", [
        ValueError("Invalid temperature: 3.5"),
        TypeError("model must be str"),
        ConnectionError("API timeout"),
    ])

    # Handling with except*
    try:
        raise ExceptionGroup("Agent errors", [
            ValueError("temperature out of range"),
            ConnectionError("network timeout"),
            ValueError("max_tokens is negative"),
        ])
    except* ValueError as eg:
        print(f"Validation errors ({len(eg.exceptions)}):")
        for e in eg.exceptions:
            print(f"  ❌ {e}")
    except* ConnectionError as eg:
        print(f"Network errors ({len(eg.exceptions)}):")
        for e in eg.exceptions:
            print(f"  🌐 {e}")
else:
    print(f"  (ExceptionGroup requires Python 3.11+ — current: {sys.version_info.major}.{sys.version_info.minor})")


# ══════════════════════════════════════════════════════════════════════════════
# PART H: pathlib — MODERN FILE HANDLING
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS pathlib?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

pathlib.Path: object-oriented file system paths.
Cleaner than os.path — method-chained, cross-platform.

WHY?
  os.path (old):
    path = os.path.join(base, "data", "file.json")
    parent = os.path.dirname(path)
    name = os.path.basename(path)
    with open(path, "r") as f: data = f.read()
    # Verbose, not composable, easy to mix separators

  pathlib (modern):
    path = Path(base) / "data" / "file.json"
    parent = path.parent
    name = path.name
    data = path.read_text()
    # Clean, composable, works on Windows/Linux/Mac
"""

from pathlib import Path

print("\n=== pathlib ===")

# Current directory
cwd = Path.cwd()
home = Path.home()
print(f"cwd: {cwd}")
print(f"home: {home}")

# Path construction — / operator!
project = Path("/tmp/my_project")
data_dir = project / "data"
config_file = project / "config" / "settings.json"

print(f"\nPath operations:")
print(f"  parent: {config_file.parent}")
print(f"  name:   {config_file.name}")
print(f"  stem:   {config_file.stem}")     # settings (without extension)
print(f"  suffix: {config_file.suffix}")   # .json
print(f"  parts:  {config_file.parts}")

# Path predicates
print(f"\n  exists: {config_file.exists()}")
print(f"  is_file: {config_file.is_file()}")
print(f"  is_dir: {config_file.parent.is_dir()}")

# Glob — pattern matching
print(f"\n  Python files in /tmp: ", end="")
py_files = list(Path("/tmp").glob("*.py"))
print(f"{len(py_files)} files")

# Recursive glob
all_py = list(Path(".").rglob("*.py"))
print(f"  Python files (recursive from .): {len(all_py)} files")

# Read/write (no need for open())
import tempfile, json

with tempfile.TemporaryDirectory() as tmpdir:
    config_path = Path(tmpdir) / "config.json"

    # Write
    config_data = {"model": "gpt-4", "temperature": 0.7}
    config_path.write_text(json.dumps(config_data, indent=2))

    # Read
    loaded = json.loads(config_path.read_text())
    print(f"\n  Write+Read via pathlib: {loaded}")

    # Create directories
    (Path(tmpdir) / "data" / "outputs").mkdir(parents=True, exist_ok=True)
    print(f"  Created nested dirs: {(Path(tmpdir) / 'data' / 'outputs').exists()}")


# ══════════════════════════════════════════════════════════════════════════════
# PART I: contextlib TOOLS
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS contextlib?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

contextlib: standard library for creating and working with context managers.

KEY TOOLS:
  @contextmanager    → create CM from generator (no need to write __enter__/__exit__)
  suppress(*excs)    → suppress specified exceptions silently
  ExitStack          → dynamically combine context managers
  redirect_stdout    → redirect print output to a file/buffer
  redirect_stderr    → redirect error output
  nullcontext        → placeholder CM that does nothing (for optional CM)
  chdir              → cd into directory, restore on exit (Python 3.11+)
"""

import contextlib
import io

print("\n=== contextlib ===")

# @contextmanager — create CM from generator
from contextlib import contextmanager


@contextmanager
def timer(label: str):
    """Context manager that times a block of code."""
    start = time.perf_counter()
    try:
        yield  # enter block
    finally:
        elapsed = (time.perf_counter() - start) * 1000
        print(f"  [{label}] {elapsed:.2f}ms")


with timer("List creation"):
    data = [i * 2 for i in range(100_000)]

with timer("Sort"):
    data.sort(reverse=True)


# contextlib.suppress — clean error suppression (no try/except)
print(f"\nsuppress:")
with contextlib.suppress(FileNotFoundError):
    content = Path("/nonexistent/file.txt").read_text()
    print(f"  Loaded: {content[:20]}")
print(f"  (FileNotFoundError suppressed silently)")

# Multiple suppressions
with contextlib.suppress(ValueError, TypeError):
    x = int("not a number")  # ValueError suppressed
    print(f"  This won't print")
print(f"  Code continues after suppressed error")


# ExitStack — dynamically combine context managers
print(f"\nExitStack:")

def get_file_managers(paths: list[str]) -> list:
    """Return context managers for multiple files."""
    return [contextlib.suppress(FileNotFoundError) for _ in paths]


with contextlib.ExitStack() as stack:
    # Open multiple resources dynamically
    files = []
    for i in range(3):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(f"File {i} content")
            files.append(f.name)

    # Now open all temp files
    handles = [stack.enter_context(open(f)) for f in files]
    contents = [h.read() for h in handles]
    print(f"  Read {len(contents)} files: {contents}")
    # All files auto-closed when ExitStack exits


# redirect_stdout — capture print output
print(f"\nredirect_stdout:")
buffer = io.StringIO()
with contextlib.redirect_stdout(buffer):
    print("This goes to buffer, not console!")
    print("And this too!")

output = buffer.getvalue()
print(f"  Captured: {output.strip()!r}")


# nullcontext — optional context manager
def get_tracer(enabled: bool):
    """Return real tracer or nullcontext depending on config."""
    if enabled:
        return timer("Optional block")
    return contextlib.nullcontext()

print(f"\nnullcontext (disabled):")
with get_tracer(False):
    time.sleep(0.01)
print(f"  Block executed without timing")

print(f"\nnullcontext (enabled):")
with get_tracer(True):
    time.sleep(0.01)


# ══════════════════════════════════════════════════════════════════════════════
# COMPLETE MODERN PYTHON SUMMARY
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PYTHON VERSION FEATURE MATRIX
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Python 3.8:
  ✅ Walrus operator :=
  ✅ f-string {=} for debugging
  ✅ Positional-only parameters /
  ✅ TypedDict (typing module)
  ✅ Protocol (typing module)
  ✅ Final (typing module)
  ✅ Literal (typing module)

Python 3.9:
  ✅ list[int] instead of List[int] (built-in generics)
  ✅ dict | other_dict (union/merge)
  ✅ str.removeprefix() and str.removesuffix()

Python 3.10:
  ✅ match-case structural pattern matching
  ✅ str | int instead of Union[str, int]
  ✅ dataclass(slots=True, kw_only=True)
  ✅ ParamSpec in typing

Python 3.11:
  ✅ asyncio.TaskGroup (structured concurrency)
  ✅ asyncio.timeout context manager
  ✅ ExceptionGroup and except*
  ✅ tomllib (TOML parsing built-in)
  ✅ Self type in typing
  ✅ StrEnum (enum.StrEnum)
  ✅ Faster startup (15% improvement)

Python 3.12:
  ✅ @override decorator in typing
  ✅ f-string: backslashes allowed inside {}
  ✅ PEP 695: type statement (type Vector = list[float])
  ✅ type Parameter Syntax (T[int] instead of TypeVar)
  ✅ Faster Python (perf improvements)

Python 3.13:
  ✅ JIT compiler (experimental)
  ✅ Free-threaded mode — optional no-GIL (experimental)
  ✅ Improved REPL with colors and multiline editing
"""

print("\n=== Modern Python Version Feature Matrix ===")
print(f"Your Python version: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")

features = {
    (3, 8): [":= walrus operator", "f-string {=}", "positional-only /", "TypedDict, Protocol, Final, Literal"],
    (3, 9): ["list[int] generics", "dict | merge", "str.removeprefix()"],
    (3, 10): ["match-case", "str | int union", "dataclass slots+kw_only"],
    (3, 11): ["TaskGroup", "asyncio.timeout", "ExceptionGroup+except*", "tomllib", "Self type"],
    (3, 12): ["@override", "f-string backslash", "type statement PEP695"],
    (3, 13): ["JIT compiler (exp)", "No-GIL mode (exp)", "Better REPL"],
}

for (major, minor), feature_list in features.items():
    available = "✅" if sys.version_info >= (major, minor) else "⬜"
    print(f"  {available} Python {major}.{minor}: {', '.join(feature_list[:2])}...")


"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Q&A — Modern Python
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q1: When should I use @dataclass vs NamedTuple vs TypedDict?
A:  TypedDict:   When data IS a dict (JSON APIs, interop with dict-expecting code)
                 Still a dict at runtime, no __init__, no methods
    NamedTuple:  When data should be IMMUTABLE, lightweight, tuple-compatible
                 Hashable — can be dict key or set member
                 Small, focused data with simple methods
    @dataclass:  Most general — mutable by default, rich features
                 __post_init__ for validation, computed fields, frozen option
                 Best for complex data objects with methods

Q2: What is the advantage of match-case over if/elif chains?
A:  Readability for complex structural checks.
    Can destructure and capture variables from structure in one step.
    Exhaustiveness checking with _: case — clear all cases handled.
    Pattern combinations (OR patterns, guards) are cleaner than nested conditions.
    Performance: Python optimizes some patterns better than if/elif.

Q3: Is walrus operator := always better than separating assignment?
A:  No — use walrus when it eliminates duplicate evaluation or repetition.
    Avoid when it makes the line hard to read or understand.
    PEP 572 guideline: use := to CLARIFY, not to show off.
    if (n := len(items)) > 10:  # clear: compute length once, name it, check it
    vs.
    if len(items) > 10:         # if you don't need the value later, just use this!

Q4: What are the most important Modern Python features for AI/backend development?
A:  1. match-case: parse LLM events, route API responses, handle webhook payloads
    2. asyncio.TaskGroup (3.11): structured concurrent LLM calls
    3. dataclasses: clean data models for requests/responses/agent state
    4. TypedDict + Literal: type-safe API request/response structures
    5. pathlib: clean file handling for configs, prompt templates, data files
    6. asyncio.timeout (3.11): deadline management for all external API calls
"""

print("\n✅ 09_Modern_Python_Theory.py complete — all sections covered.")
print("\n" + "="*70)
print("🎉 COMPLETE THEORY SERIES FINISHED!")
print("="*70)
print("""
Files Created:
  01_Core_Python_Theory.py             ← Variables, Types, Strings, Lists, Dicts, Sets, Tuples
  02_Functions_Closures_Decorators_Theory.py ← Functions, Closures, Decorators, Generators
  03_OOP_Theory.py                     ← Classes, Inheritance, ABC, Mixins, Descriptors, Metaclasses
  04_Async_Concurrency_Theory.py       ← asyncio, GIL, Threading, Multiprocessing
  05_Collections_Functools_Itertools_Theory.py ← Standard Library Power Tools
  06_Typing_System_Theory.py           ← Complete Type System
  07_Memory_Performance_Theory.py      ← GC, Profiling, Optimization
  08_Design_Patterns_Theory.py         ← All 10 GOF Patterns with AI context
  09_Modern_Python_Theory.py           ← Python 3.8-3.13 Features

Format in EVERY file:
  WHAT → WHY → HOW → REAL LIFE ANALOGY → PRODUCTION CODE → Q&A
""")
