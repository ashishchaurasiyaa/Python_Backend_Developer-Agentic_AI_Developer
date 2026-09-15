"""
DAY 38 — Modern Python: walrus operator, match-case, __slots__, lambda
Architecture Level: Senior Python Backend + Agentic AI
Python 3.10+ features used in production backend and AI code.
"""


# ═══════════════════════════════════════════════════════
# PART A: Walrus Operator := (Python 3.8+)
# ═══════════════════════════════════════════════════════

# Assigns AND returns value in one expression
# Named after a walrus (:= looks like walrus eyes)

# ─────────────────────────────────────────────
# 1. In while loops — cleaner reads
# ─────────────────────────────────────────────

import re

# OLD:
# chunk = file.read(8192)
# while chunk:
#     process(chunk)
#     chunk = file.read(8192)

# NEW with walrus:
data = iter([b"chunk1", b"chunk2", b"chunk3", b""])
while chunk := next(data):
    print(f"Processing: {chunk}")


# ─────────────────────────────────────────────
# 2. In list comprehensions — compute once, use twice
# ─────────────────────────────────────────────

responses = [
    "Here is your answer: Python is great",
    "Short answer",
    "A detailed response about machine learning and neural networks",
    "OK",
]

# OLD — calls len() twice:
# long_responses = [r for r in responses if len(r) > 20]

# NEW — compute once:
long_responses = [r for r in responses if (n := len(r)) > 20]
print(f"\nLong responses: {len(long_responses)}")

# Even better — include the length in output:
with_lengths = [(r[:30], n) for r in responses if (n := len(r)) > 20]
print(f"With lengths: {with_lengths}")


# ─────────────────────────────────────────────
# 3. BACKEND USE CASE — parse and validate
# ─────────────────────────────────────────────

def extract_json_from_llm(text: str) -> dict | None:
    """Extract and parse JSON from LLM response in one pass."""
    import json
    import re

    if match := re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL):
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None
    elif match := re.search(r"\{.*\}", text, re.DOTALL):
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            return None
    return None


llm_output = """
Here's the result:
```json
{"status": "success", "model": "gpt-4", "tokens": 500}
```
"""
result = extract_json_from_llm(llm_output)
print(f"\nExtracted JSON: {result}")


# ─────────────────────────────────────────────
# 4. AGENTIC AI — streaming token accumulation
# ─────────────────────────────────────────────

def stream_tokens():
    """Simulate LLM streaming."""
    for token in ["Hello", " World", " from", " Claude", None]:
        yield token

accumulated = ""
for token in stream_tokens():
    if token is None:
        break
    accumulated += (chunk := token)
    if len(accumulated) > 10:
        print(f"Threshold reached at: '{chunk}'")
        break


# ═══════════════════════════════════════════════════════
# PART B: match-case (Python 3.10+) — structural pattern matching
# ═══════════════════════════════════════════════════════

# NOT just a switch statement — it's STRUCTURAL PATTERN MATCHING
# Can match on types, structure, values, and bind variables

# ─────────────────────────────────────────────
# 1. Basic value matching
# ─────────────────────────────────────────────

def handle_http_status(status: int) -> str:
    match status:
        case 200 | 201:
            return "Success"
        case 400:
            return "Bad Request"
        case 401 | 403:
            return "Auth Error"
        case 404:
            return "Not Found"
        case 500 | 502 | 503:
            return "Server Error"
        case _:
            return f"Unknown: {status}"

print(f"\nHTTP 404: {handle_http_status(404)}")
print(f"HTTP 201: {handle_http_status(201)}")


# ─────────────────────────────────────────────
# 2. Structural pattern matching — POWERFUL
# ─────────────────────────────────────────────

def process_llm_event(event: dict) -> str:
    """Process streaming events from LLM APIs."""
    match event:
        case {"type": "message_start", "model": model}:
            return f"Started: {model}"

        case {"type": "content_block_delta", "delta": {"type": "text_delta", "text": text}}:
            return f"Token: {text}"

        case {"type": "message_delta", "usage": {"output_tokens": n}}:
            return f"Output tokens: {n}"

        case {"type": "error", "error": {"message": msg}}:
            return f"Error: {msg}"

        case {"type": str(event_type)}:
            return f"Unknown event: {event_type}"

        case _:
            return "Invalid event"


events = [
    {"type": "message_start", "model": "claude-3"},
    {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Hello"}},
    {"type": "message_delta", "usage": {"output_tokens": 42}},
    {"type": "unknown_event"},
]

for e in events:
    print(f"  {process_llm_event(e)}")


# ─────────────────────────────────────────────
# 3. Class pattern matching
# ─────────────────────────────────────────────

from dataclasses import dataclass

@dataclass
class WebSearchResult:
    query: str
    results: list[str]

@dataclass
class CodeResult:
    code: str
    output: str
    success: bool

@dataclass
class ErrorResult:
    message: str
    retryable: bool

ToolOutput = WebSearchResult | CodeResult | ErrorResult


def handle_tool_output(output: ToolOutput) -> str:
    match output:
        case WebSearchResult(query=q, results=[first, *rest]):
            return f"Search '{q}': {first} (+{len(rest)} more)"

        case WebSearchResult(results=[]):
            return "Search returned no results"

        case CodeResult(success=True, output=out):
            return f"Code OK: {out[:50]}"

        case CodeResult(success=False, code=c):
            return f"Code failed: {c[:30]}..."

        case ErrorResult(retryable=True, message=msg):
            return f"Retryable error: {msg}"

        case ErrorResult(retryable=False, message=msg):
            return f"Fatal error: {msg}"


outputs = [
    WebSearchResult("Python", ["Python docs", "Tutorial", "GitHub"]),
    WebSearchResult("obscure_query", []),
    CodeResult("print(42)", "42\n", True),
    CodeResult("1/0", "", False),
    ErrorResult("Rate limit exceeded", retryable=True),
]

for out in outputs:
    print(f"  {handle_tool_output(out)}")


# ─────────────────────────────────────────────
# 4. Guard clauses (when)
# ─────────────────────────────────────────────

def classify_token_count(tokens: int, model: str) -> str:
    match tokens:
        case n if n < 0:
            return "invalid"
        case n if n == 0:
            return "empty"
        case n if model == "gpt-4" and n > 8192:
            return "exceeds gpt-4 limit"
        case n if n > 4096:
            return "long"
        case n if n > 1000:
            return "medium"
        case _:
            return "short"

print(f"\nToken classify: {classify_token_count(5000, 'gpt-4')}")


# ═══════════════════════════════════════════════════════
# PART C: lambda — concise anonymous functions
# ═══════════════════════════════════════════════════════

# Use lambda for SHORT, simple functions (1 expression only)
# Use def for anything complex

double    = lambda x: x * 2
add       = lambda x, y: x + y
safe_div  = lambda x, y: x / y if y != 0 else 0.0

# Most common uses:
items = [{"name": "Bob", "score": 85}, {"name": "Alice", "score": 95}]
sorted_items = sorted(items, key=lambda x: x["score"], reverse=True)

# Conditional lambda
process = lambda text, upper=False: text.upper() if upper else text.lower()

# lambda in dict — dispatch table (alternative to if-elif chains)
operations = {
    "add": lambda a, b: a + b,
    "sub": lambda a, b: a - b,
    "mul": lambda a, b: a * b,
    "div": lambda a, b: a / b if b != 0 else None,
}

print(f"\nDispatch: {operations['add'](5, 3)}")


# ─────────────────────────────────────────────
# INTERVIEW — when NOT to use lambda
# ─────────────────────────────────────────────
# 1. Complex logic — use def
# 2. Multi-line operations — use def
# 3. When you need a name for debugging — use def
# 4. When assigning to a variable — use def (PEP8 says so)

# BAD:  get_name = lambda obj: obj.name  # just use def
# GOOD: sorted(items, key=lambda x: x["name"])  # inline usage OK
