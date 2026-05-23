"""
╔══════════════════════════════════════════════════════════════╗
║  PYTHON COMPLETE PRACTICAL — Section 01                      ║
║  Topic: Strings — Complete Reference                         ║
╚══════════════════════════════════════════════════════════════╝
"""

import re
import textwrap

# ─────────────────────────────────────────────────────────────
# 1. STRING CREATION
# ─────────────────────────────────────────────────────────────

s1 = 'single'
s2 = "double"
s3 = """multi
line"""
s4 = r"raw\nno_escape"           # r-string: backslash is literal
s5 = b"bytes"                    # bytes literal
s6 = f"hello {'world'}"          # f-string
s7 = "line1\n" "line2\n"        # implicit concatenation (same line)

print(repr(s4))   # 'raw\\nno_escape'
print(s4)         # raw\nno_escape


# ─────────────────────────────────────────────────────────────
# 2. INDEXING AND SLICING
# ─────────────────────────────────────────────────────────────

s = "Python Backend AI"
#    0123456789...

print(s[0])        # P
print(s[-1])       # I
print(s[7:14])     # Backend
print(s[::2])      # Pto akn I (every 2nd char)
print(s[::-1])     # IA dnekcaB nohtyP (reversed)
print(s[7:])       # Backend AI
print(s[:6])       # Python
print(s[-2:])      # AI

# Strings are immutable — no item assignment
# s[0] = "J"  → TypeError


# ─────────────────────────────────────────────────────────────
# 3. STRING METHODS — complete
# ─────────────────────────────────────────────────────────────

text = "  Hello, World! Python is Amazing.  "

# ── Case ──────────────────────────────────────────────────────
print(text.upper())           # HELLO, WORLD! PYTHON IS AMAZING.
print(text.lower())           # hello, world! python is amazing.
print(text.title())           # Hello, World! Python Is Amazing.
print(text.capitalize())      # Hello, world! python is amazing.
print(text.swapcase())        # hELLO, wORLD! pYTHON IS aMAZING.

# ── Strip ─────────────────────────────────────────────────────
print(text.strip())           # "Hello, World! Python is Amazing."
print(text.lstrip())          # leading whitespace removed
print(text.rstrip())          # trailing whitespace removed
print("###data###".strip("#"))  # data

# ── Search ────────────────────────────────────────────────────
s = "Python is great. Python is fast."
print(s.find("Python"))       # 0  — first occurrence (-1 if not found)
print(s.rfind("Python"))      # 17 — last occurrence
print(s.index("is"))          # 7  — like find but raises ValueError
print(s.count("Python"))      # 2
print(s.startswith("Python")) # True
print(s.endswith("."))        # True
print(s.startswith(("Py", "Ja")))  # True — accepts tuple!
print("is" in s)              # True — membership test

# ── Split and Join ────────────────────────────────────────────
parts = "gpt-4,claude-3,gemini".split(",")
print(parts)                  # ['gpt-4', 'claude-3', 'gemini']

first2 = "a:b:c:d".split(":", maxsplit=2)
print(first2)                 # ['a', 'b', 'c:d']

lines = "line1\nline2\nline3".splitlines()
print(lines)                  # ['line1', 'line2', 'line3']

print(", ".join(parts))       # gpt-4, claude-3, gemini
print(" | ".join(["a", "b"])) # a | b

# ── Replace ───────────────────────────────────────────────────
print("hello world".replace("world", "Python"))
print("aababab".replace("ab", "X", 2))  # aXXab (max 2 replacements)

# ── Alignment and Padding ─────────────────────────────────────
print("42".zfill(8))              # 00000042
print("hello".center(20))         # "       hello        "
print("hello".center(20, "-"))    # -------hello--------
print("hello".ljust(10, "."))     # hello.....
print("hello".rjust(10, "."))     # .....hello

# ── Check methods ─────────────────────────────────────────────
print("abc123".isalnum())   # True
print("abc".isalpha())      # True
print("123".isdigit())      # True
print("  ".isspace())       # True
print("HELLO".isupper())    # True
print("hello".islower())    # True
print("Hello World".istitle()) # True

# ── Partition ─────────────────────────────────────────────────
# Returns (before, separator, after) — always 3 items
before, sep, after = "user:password@host".partition(":")
print(before, sep, after)   # user : password@host

key, _, value = "temperature=0.7".partition("=")
print(f"key={key}, value={value}")

# ── encode/decode ─────────────────────────────────────────────
s = "Hello 🌍"
encoded = s.encode("utf-8")   # bytes
decoded = encoded.decode("utf-8")  # str
print(f"Encoded: {encoded}")
print(f"Decoded: {decoded}")


# ─────────────────────────────────────────────────────────────
# 4. F-STRINGS — complete guide
# ─────────────────────────────────────────────────────────────

name    = "Alice"
score   = 98.567
cost    = 1_234_567.89
ratio   = 0.8756
tokens  = 4096
model   = "gpt-4"

# Basic
print(f"Name: {name}, Score: {score}")

# Format specs
print(f"Score:   {score:.2f}")        # 98.57 (2 decimal places)
print(f"Score:   {score:.0f}")        # 99    (0 decimal places)
print(f"Cost:    ${cost:,.2f}")       # $1,234,567.89
print(f"Ratio:   {ratio:.1%}")        # 87.6%
print(f"Tokens:  {tokens:,}")         # 4,096
print(f"Hex:     {255:#x}")           # 0xff
print(f"Binary:  {10:#b}")            # 0b1010
print(f"Sci:     {0.000123:.2e}")     # 1.23e-04

# Alignment
print(f"{'Left':<15}|")              # Left-aligned in 15 chars
print(f"{'Right':>15}|")             # Right-aligned
print(f"{'Center':^15}|")            # Centered
print(f"{'Fill':*^15}|")             # Fill with *
print(f"{'Fill':-^15}|")             # Fill with -

# Conditional expression
status = "PASS" if score > 90 else "FAIL"
print(f"Status: {status}")

# Expression
print(f"Pi ≈ {22/7:.4f}")
print(f"Tokens left: {4096 - tokens:+d}")  # +/- sign

# repr vs str
data = ["a", "b"]
print(f"str:  {data!s}")    # ['a', 'b']
print(f"repr: {data!r}")    # ['a', 'b'] with quotes

# Debug mode (Python 3.8+) — prints name and value
x = 42
temperature = 0.7
print(f"{x=}")               # x=42
print(f"{temperature=:.2f}") # temperature=0.70

# Nested (Python 3.12+)
width = 10
print(f"{score:{width}.{2}f}")   # "     98.57"

# Datetime
from datetime import datetime
now = datetime(2025, 5, 20, 14, 30, 45)
print(f"Date: {now:%Y-%m-%d}")           # 2025-05-20
print(f"Time: {now:%H:%M:%S}")           # 14:30:45
print(f"Full: {now:%A, %B %d, %Y}")      # Tuesday, May 20, 2025


# ─────────────────────────────────────────────────────────────
# 5. STRING FORMATTING METHODS (older styles — know for legacy code)
# ─────────────────────────────────────────────────────────────

# .format() method
print("Hello, {}! Score: {:.2f}".format("Bob", 95.5))
print("Hello, {name}! Model: {model}".format(name="Alice", model="gpt-4"))
print("{0} {1} {0}".format("aba", "bab"))   # positional

# % formatting (oldest — avoid in new code)
print("Hello, %s! Score: %.2f" % ("Charlie", 88.0))


# ─────────────────────────────────────────────────────────────
# 6. MULTILINE STRINGS — textwrap
# ─────────────────────────────────────────────────────────────

long_text = """
    This is a long paragraph that has leading indentation
    because it's inside a function or class body.
    We need to remove that indentation cleanly.
"""

# textwrap.dedent — removes common leading whitespace
clean = textwrap.dedent(long_text).strip()
print(repr(clean[:50]))

# textwrap.fill — wrap text to width
paragraph = "Python is a high-level, general-purpose programming language."
wrapped = textwrap.fill(paragraph, width=30)
print(wrapped)

# textwrap.shorten — truncate cleanly
short = textwrap.shorten("This is a very long sentence that needs to be shortened.", width=30)
print(short)  # "This is a very long [...]"


# ─────────────────────────────────────────────────────────────
# 7. PRODUCTION PATTERNS — real AI/backend use cases
# ─────────────────────────────────────────────────────────────

# ── Pattern 1: Prompt template builder ───────────────────────
class PromptTemplate:
    """Build LLM prompts cleanly without string concatenation."""

    def __init__(self, template: str):
        self._template = textwrap.dedent(template).strip()

    def render(self, **kwargs) -> str:
        return self._template.format(**kwargs)

    def __len__(self) -> int:
        return len(self._template)


system_prompt = PromptTemplate("""
    You are a {role} specialized in {domain}.
    Current task: {task}
    Respond in {language}.
""")

rendered = system_prompt.render(
    role="Python expert",
    domain="backend development",
    task="code review",
    language="English",
)
print(f"\nPrompt:\n{rendered}")


# ── Pattern 2: Parse LLM structured output ───────────────────
def extract_between_tags(text: str, tag: str) -> str | None:
    """Extract content between XML-style tags in LLM output."""
    start_tag = f"<{tag}>"
    end_tag   = f"</{tag}>"
    start = text.find(start_tag)
    end   = text.find(end_tag)
    if start == -1 or end == -1:
        return None
    return text[start + len(start_tag):end].strip()

llm_output = """
<thinking>
Let me analyze the problem step by step.
</thinking>
<answer>
The solution is to use asyncio.gather() for parallel execution.
</answer>
"""

thinking = extract_between_tags(llm_output, "thinking")
answer   = extract_between_tags(llm_output, "answer")
print(f"\nThinking: {thinking}")
print(f"Answer: {answer}")


# ── Pattern 3: Slug generator ────────────────────────────────
import re

def to_slug(text: str) -> str:
    """Convert text to URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)    # remove special chars
    text = re.sub(r"[\s_-]+", "-", text)    # spaces to hyphens
    text = re.sub(r"^-+|-+$", "", text)     # strip leading/trailing hyphens
    return text

print(to_slug("  Hello World! Python 3.12  "))  # hello-world-python-312
print(to_slug("My Backend AI Project #1"))       # my-backend-ai-project-1


# ── Pattern 4: Token estimation ──────────────────────────────
def estimate_tokens(text: str, chars_per_token: int = 4) -> int:
    """Rough token estimation (GPT uses ~4 chars per token)."""
    return max(1, len(text) // chars_per_token)

def truncate_to_token_limit(text: str, max_tokens: int, chars_per_token: int = 4) -> str:
    """Truncate text to approximate token limit at word boundary."""
    max_chars = max_tokens * chars_per_token
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    # break at last word boundary
    last_space = truncated.rfind(" ")
    if last_space > max_chars * 0.8:
        truncated = truncated[:last_space]
    return truncated + "..."

long_prompt = "Python " * 500
print(f"Tokens: {estimate_tokens(long_prompt)}")
short = truncate_to_token_limit(long_prompt, max_tokens=10)
print(f"Truncated: '{short}'")


# ─────────────────────────────────────────────────────────────
# INTERVIEW QUESTIONS
# ─────────────────────────────────────────────────────────────
"""
Q: Are strings mutable in Python?
A: No. Strings are immutable. Operations return new string objects.

Q: What is the difference between find() and index()?
A: find() returns -1 if not found. index() raises ValueError.
   Use find() when absence is expected, index() when absence is a bug.

Q: When would you use str.partition() instead of str.split()?
A: partition() always returns exactly 3 parts (before, sep, after).
   Ideal for key=value or scheme://rest parsing where structure is fixed.

Q: What's the difference between r"string" and "string"?
A: r-string treats backslash as literal. "string" processes escape sequences.
   Use r-strings for regex patterns and Windows file paths.

Q: How do you efficiently build a large string?
A: Use "".join(list_of_strings) instead of repeated += concatenation.
   += is O(n²) due to string immutability. join() is O(n).
"""

# Performance: string building
parts = [f"item_{i}" for i in range(1000)]
result = "".join(parts)   # O(n) — correct
# result = ""
# for p in parts:
#     result += p           # O(n²) — avoid!
