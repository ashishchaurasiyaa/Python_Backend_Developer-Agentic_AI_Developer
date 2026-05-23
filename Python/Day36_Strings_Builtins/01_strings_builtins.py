"""
DAY 36 — String Methods + Advanced f-strings + Built-in Functions
Architecture Level: Senior Python Backend + Agentic AI
"""

# ═══════════════════════════════════════════════════════
# PART A: String Methods — production patterns
# ═══════════════════════════════════════════════════════

# ─────────────────────────────────────────────
# 1. Most important string methods
# ─────────────────────────────────────────────

s = "  Hello, World! Python Backend Developer  "

# strip / lstrip / rstrip
print(s.strip())                          # "Hello, World! Python Backend Developer"
print(s.lstrip())                         # remove left whitespace only
print("###data###".strip("#"))            # "data"

# split / rsplit / splitlines
words = "gpt-4, claude-3, gemini".split(", ")     # ['gpt-4', 'claude-3', 'gemini']
first_2 = "a:b:c:d".split(":", maxsplit=2)         # ['a', 'b', 'c:d']
lines = "line1\nline2\nline3".splitlines()          # ['line1', 'line2', 'line3']
print(first_2)

# join
models = ["gpt-4", "claude-3", "gemini"]
print(", ".join(models))                  # "gpt-4, claude-3, gemini"
print("\n".join(models))                  # each on new line

# find / index / rfind
text = "The quick brown fox"
print(text.find("fox"))                   # 16 (returns -1 if not found)
print(text.index("quick"))               # 4 (raises ValueError if not found)
print(text.rfind("o"))                   # 17 (right-to-left)

# replace
print("Hello World".replace("World", "Python"))
print("aababab".replace("ab", "X", 2))  # replaces first 2 occurrences

# startswith / endswith (accept tuples!)
endpoint = "/api/v2/users"
print(endpoint.startswith("/api"))        # True
print(endpoint.endswith((".json", "/users", ".xml")))  # True — tuple check!

# count
text = "python python python"
print(text.count("python"))              # 3

# center / ljust / rjust / zfill
print("42".zfill(5))                    # "00042" — pad with zeros
print("ERROR".center(20, "="))          # "=======ERROR========"


# ─────────────────────────────────────────────
# 2. partition — underused but powerful
# ─────────────────────────────────────────────

# partition returns (before, separator, after) — always 3-tuple
url = "postgresql://user:password@localhost:5432/mydb"
scheme, _, rest = url.partition("://")
print(f"Scheme: {scheme}, Rest: {rest[:20]}")

# Useful for parsing key=value pairs
key, _, value = "temperature=0.7".partition("=")
print(f"Key: {key}, Value: {value}")


# ─────────────────────────────────────────────
# 3. String operations used in AI
# ─────────────────────────────────────────────

def truncate_to_tokens(text: str, max_tokens: int, chars_per_token: int = 4) -> str:
    """Truncate text to approximate token limit."""
    max_chars = max_tokens * chars_per_token
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + "..."  # break at word boundary


def extract_code_blocks(text: str) -> list[str]:
    """Extract code blocks from LLM markdown responses."""
    blocks = []
    parts = text.split("```")
    for i in range(1, len(parts), 2):
        block = parts[i]
        if "\n" in block:
            block = block[block.index("\n") + 1:]  # remove language tag
        blocks.append(block.strip())
    return blocks


llm_response = """
Here is some code:
```python
def hello():
    return "world"
```
And another:
```bash
pip install fastapi
```
"""
print(extract_code_blocks(llm_response))


# ═══════════════════════════════════════════════════════
# PART B: Advanced f-strings (Python 3.12+)
# ═══════════════════════════════════════════════════════

import datetime

# ─────────────────────────────────────────────
# Format specs
# ─────────────────────────────────────────────

pi = 3.14159265
cost = 1234567.89
pct = 0.8734

print(f"Pi (2 dp): {pi:.2f}")            # 3.14
print(f"Pi (sci):  {pi:.2e}")            # 3.14e+00
print(f"Cost:      ${cost:,.2f}")        # $1,234,567.89
print(f"Percent:   {pct:.1%}")           # 87.3%
print(f"Hex:       {255:#x}")            # 0xff
print(f"Binary:    {10:#b}")             # 0b1010
print(f"Padded:    {'title':^20}")       # centered in 20 chars
print(f"Left:      {'title':<20}|")      # left-aligned
print(f"Right:     {'title':>20}|")      # right-aligned
print(f"Fill:      {'title':*^20}")      # fill with *

# datetime formatting
now = datetime.datetime(2025, 5, 20, 14, 30, 45)
print(f"Date: {now:%Y-%m-%d %H:%M:%S}")  # 2025-05-20 14:30:45
print(f"Day:  {now:%A, %B %d}")          # Tuesday, May 20

# Conditional expression in f-string
tokens = 450
print(f"Token usage: {tokens} ({'over' if tokens > 400 else 'under'} limit)")

# Nested f-strings (Python 3.12+)
width = 10
value = 3.14
print(f"{value:{width}.{3}f}")          # "      3.140"

# !r !s !a — conversion flags
name = "Alice\nBackend"
print(f"!r: {name!r}")                  # 'Alice\\nBackend' (repr)
print(f"!s: {name!s}")                  # Alice\nBackend (str)

# Debug mode = (Python 3.8+)
x = 42
temperature = 0.7
print(f"{x=}, {temperature=}")          # x=42, temperature=0.7


# ═══════════════════════════════════════════════════════
# PART C: Built-in Functions — Senior Level
# ═══════════════════════════════════════════════════════

# ─────────────────────────────────────────────
# map, filter, zip, enumerate — functional style
# ─────────────────────────────────────────────

# map — apply function to each element (lazy)
tokens = [100, 200, 150, 300, 250]
costs = list(map(lambda t: t * 0.002, tokens))
print(f"\ncosts: {costs}")

# With multiple iterables
a = [1, 2, 3]
b = [10, 20, 30]
sums = list(map(lambda x, y: x + y, a, b))  # [11, 22, 33]

# filter — keep elements where function returns True
active_tools = list(filter(lambda t: t["enabled"], [
    {"name": "web_search", "enabled": True},
    {"name": "calculator", "enabled": False},
    {"name": "code_runner", "enabled": True},
]))
print(f"Active tools: {[t['name'] for t in active_tools]}")

# zip — pair elements (stops at shortest)
names   = ["Alice", "Bob", "Charlie"]
scores  = [95, 87, 92]
roles   = ["admin", "user", "user"]

for name, score, role in zip(names, scores, roles):
    print(f"  {name} ({role}): {score}")

# enumerate — index + value
tools = ["web_search", "calculator", "file_reader"]
for i, tool in enumerate(tools, start=1):
    print(f"  {i}. {tool}")

# ─────────────────────────────────────────────
# sorted, min, max with key function
# ─────────────────────────────────────────────

agents = [
    {"name": "researcher", "tokens": 5000, "success_rate": 0.92},
    {"name": "coder", "tokens": 8000, "success_rate": 0.85},
    {"name": "reviewer", "tokens": 2000, "success_rate": 0.98},
]

# Sort by multiple keys
by_success = sorted(agents, key=lambda a: (-a["success_rate"], a["tokens"]))
print(f"\nBest agent: {by_success[0]['name']}")

# min/max with key
most_tokens = max(agents, key=lambda a: a["tokens"])
print(f"Most tokens: {most_tokens['name']}")

# ─────────────────────────────────────────────
# any, all — short-circuit boolean
# ─────────────────────────────────────────────

results = [True, True, False, True]
print(f"\nany: {any(results)}")   # True — at least one
print(f"all: {all(results)}")    # False — not all

# With generators (lazy — stops at first match)
tools = ["web_search", "calculator", "code_runner"]
has_search = any(t.startswith("web") for t in tools)
all_active  = all(len(t) > 3 for t in tools)
print(f"has_search: {has_search}, all_active: {all_active}")

# ─────────────────────────────────────────────
# vars, dir, getattr, setattr, hasattr, callable
# ─────────────────────────────────────────────

class ModelConfig:
    def __init__(self, model: str, temp: float):
        self.model = model
        self.temp = temp

    def validate(self) -> bool:
        return True

cfg = ModelConfig("gpt-4", 0.7)

print(f"\nvars:    {vars(cfg)}")                          # {'model': 'gpt-4', 'temp': 0.7}
print(f"hasattr: {hasattr(cfg, 'model')}")               # True
print(f"getattr: {getattr(cfg, 'model', 'default')}")    # 'gpt-4'
setattr(cfg, "model", "claude-3")
print(f"after setattr: {cfg.model}")
print(f"callable(cfg.validate): {callable(cfg.validate)}")  # True

# Dynamic attribute access — used in ORM-style code
for attr_name in ["model", "temp"]:
    print(f"  {attr_name} = {getattr(cfg, attr_name)}")
