"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  DAY 40 — re Module: Regular Expressions (COMPLETE)                          ║
║  Level: Basic → Advanced → Production AI Patterns                            ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT IS REGEX?
  Regular Expression = a PATTERN used to search, match, and manipulate strings.
  One regex pattern can match millions of different strings.

WHY?
  - Validate inputs (email, phone, URL, API keys)
  - Extract structured data from unstructured text (scraping, log parsing)
  - Find and replace text (cleanup, transformation)
  - Tokenize text for NLP/LLM pipelines
  - Parse LLM outputs (extract JSON, code blocks, citations)

TOPICS:
  Part A: Basic patterns — literals, character classes, quantifiers
  Part B: re functions — search, match, findall, finditer, sub, split
  Part C: Groups — capturing, non-capturing, named groups
  Part D: Flags — re.IGNORECASE, MULTILINE, DOTALL, VERBOSE
  Part E: Lookahead / Lookbehind — zero-width assertions
  Part F: Compiled patterns — re.compile() for performance
  Part G: Production patterns — LLM output parsing, log extraction
  Part H: Interview Q&A
"""

import re
from typing import Optional


# ══════════════════════════════════════════════════════════════════════════════
# PART A: REGEX SYNTAX CHEATSHEET
# ══════════════════════════════════════════════════════════════════════════════
"""
METACHARACTERS:
  .       → any character except newline
  ^       → start of string (or line with MULTILINE)
  $       → end of string (or line with MULTILINE)
  *       → 0 or more (greedy)
  +       → 1 or more (greedy)
  ?       → 0 or 1 (makes quantifier optional, or lazy)
  {n}     → exactly n times
  {n,m}   → between n and m times
  {n,}    → n or more times
  \       → escape metacharacter OR special sequence
  []      → character class — match any one character inside
  |       → OR (alternation)
  ()      → group

CHARACTER CLASSES:
  [abc]   → a or b or c
  [^abc]  → NOT a, b, or c
  [a-z]   → any lowercase letter
  [A-Z]   → any uppercase letter
  [0-9]   → any digit
  [a-zA-Z0-9] → alphanumeric

SHORTHAND CLASSES:
  \d      → digit            [0-9]
  \D      → non-digit        [^0-9]
  \w      → word char        [a-zA-Z0-9_]
  \W      → non-word char    [^a-zA-Z0-9_]
  \s      → whitespace       [ \t\n\r\f\v]
  \S      → non-whitespace   [^ \t\n\r\f\v]
  \b      → word boundary
  \B      → non-word boundary

GREEDY vs LAZY:
  *       → greedy (match as MUCH as possible)
  *?      → lazy  (match as LITTLE as possible)
  +       → greedy
  +?      → lazy
  {n,m}   → greedy
  {n,m}?  → lazy
"""

print("=" * 60)
print("PART A: BASIC PATTERNS")
print("=" * 60)

text = "Python 3.11 is great! Python 3.12 is even better."

# Literal match
print(re.findall(r"Python", text))               # ['Python', 'Python']

# . (any char)
print(re.findall(r"3\.\d+", text))              # ['3.11', '3.12']

# + quantifier (1 or more)
print(re.findall(r"\d+", text))                 # ['3', '11', '3', '12']

# Greedy vs Lazy
html = "<b>bold</b> and <i>italic</i>"
print(re.findall(r"<.+>", html))               # greedy: ['<b>bold</b> and <i>italic</i>']
print(re.findall(r"<.+?>", html))              # lazy:   ['<b>', '</b>', '<i>', '</i>']

# Character classes
print(re.findall(r"[A-Z][a-z]+", "Hello World Python"))  # ['Hello', 'World', 'Python']
print(re.findall(r"[^aeiou\s]+", "hello world"))         # consonant clusters: ['h', 'll', 'w', 'rld']

# Anchors
lines = "start middle end\nSTART second line"
print(re.findall(r"^\w+", lines, re.MULTILINE))  # ['start', 'START']
print(re.findall(r"\w+$", lines, re.MULTILINE))  # ['end', 'line']


# ══════════════════════════════════════════════════════════════════════════════
# PART B: re FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════
"""
MAIN FUNCTIONS:
  re.search(pattern, string)   → first match anywhere in string (Match obj or None)
  re.match(pattern, string)    → match only at START of string
  re.fullmatch(pattern, str)   → match ENTIRE string
  re.findall(pattern, string)  → all non-overlapping matches (list of strings)
  re.finditer(pattern, string) → all matches as ITERATOR of Match objects
  re.sub(pattern, repl, str)   → replace matches with repl
  re.subn(pattern, repl, str)  → same + count of replacements
  re.split(pattern, string)    → split by pattern
  re.compile(pattern)          → compile pattern into Pattern object (reuse)

Match Object methods:
  m.group()    → entire match
  m.group(1)   → first capturing group
  m.groups()   → all groups as tuple
  m.start()    → start index
  m.end()      → end index
  m.span()     → (start, end) tuple
"""

print("\n" + "=" * 60)
print("PART B: re FUNCTIONS")
print("=" * 60)

text = "Contact us at support@company.com or sales@business.org"

# search — first match
m = re.search(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", text)
if m:
    print(f"search: {m.group()} at {m.span()}")

# findall — all matches (returns list of strings)
emails = re.findall(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", text)
print(f"findall: {emails}")

# finditer — iterator of Match objects (memory efficient)
for m in re.finditer(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", text):
    print(f"  finditer: {m.group()} @ position {m.start()}")

# sub — replace
clean = re.sub(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", "[EMAIL]", text)
print(f"sub: {clean}")

# sub with function
def mask_email(m: re.Match) -> str:
    email = m.group()
    parts = email.split("@")
    return f"{parts[0][0]}***@{parts[1]}"

masked = re.sub(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", mask_email, text)
print(f"sub+func: {masked}")

# subn — returns (new_string, count)
result, count = re.subn(r"\d+", "NUM", "Phone: 123-456-7890")
print(f"subn: {result}, replaced {count} times")

# split
csv_line = "Alice,  Bob, Charlie ,  Dave"
parts = re.split(r"\s*,\s*", csv_line)
print(f"split: {parts}")

# match vs search
print(f"\nmatch vs search:")
print(f"  match 'hello' in 'say hello': {re.match('hello', 'say hello')}")   # None
print(f"  search 'hello' in 'say hello': {re.search('hello', 'say hello')}") # Match


# ══════════════════════════════════════════════════════════════════════════════
# PART C: GROUPS — CAPTURING, NON-CAPTURING, NAMED
# ══════════════════════════════════════════════════════════════════════════════
"""
GROUPS:
  (abc)         → capturing group — m.group(1), m.groups()
  (?:abc)       → non-capturing group — used for grouping without capture
  (?P<name>abc) → named group — m.group('name'), m.groupdict()
  (?P=name)     → backreference to named group (must match same text)

BACKREFERENCES:
  \1, \2        → match same text as group 1, 2 captured earlier
"""

print("\n" + "=" * 60)
print("PART C: GROUPS")
print("=" * 60)

# Capturing groups
log = "2024-01-15 14:30:22 ERROR user_id=12345 action=login"

m = re.search(r"(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})", log)
if m:
    print(f"Full match: {m.group()}")
    print(f"Date: {m.group(1)}-{m.group(2)}-{m.group(3)}")
    print(f"Time: {m.group(4)}:{m.group(5)}:{m.group(6)}")
    print(f"All groups: {m.groups()}")

# Named groups — much cleaner!
pattern = r"(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2}) (?P<hour>\d{2}):(?P<min>\d{2}):(?P<sec>\d{2})"
m = re.search(pattern, log)
if m:
    d = m.groupdict()
    print(f"\nNamed groups: {d}")
    print(f"Date: {d['year']}-{d['month']}-{d['day']}")

# Non-capturing group (?:) — for alternation without capturing
text = "I have a cat and a dog"
animals = re.findall(r"(?:cat|dog)", text)
print(f"\nNon-capturing alternation: {animals}")

# Capturing group with findall
text = "model=gpt-4 tokens=450 latency=1250ms"
pairs = re.findall(r"(\w+)=(\S+)", text)
print(f"Captured key=value pairs: {pairs}")

# Groups in sub — backreference
text = "2024-01-15"
# Reformat: YYYY-MM-DD → DD/MM/YYYY
reformatted = re.sub(r"(\d{4})-(\d{2})-(\d{2})", r"\3/\2/\1", text)
print(f"Date reformatted: {reformatted}")

# Named group in sub
reformatted2 = re.sub(
    r"(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})",
    r"\g<day>/\g<month>/\g<year>",
    text,
)
print(f"Named group in sub: {reformatted2}")

# Real-world: parse LLM log line
llm_log = "[2024-01-15 14:30:22] agent=researcher model=gpt-4 tokens=1250 cost=0.0375"
pattern = r"\[(?P<ts>[^\]]+)\] agent=(?P<agent>\w+) model=(?P<model>[\w.-]+) tokens=(?P<tokens>\d+) cost=(?P<cost>[\d.]+)"
m = re.search(pattern, llm_log)
if m:
    print(f"\nParsed LLM log: {m.groupdict()}")


# ══════════════════════════════════════════════════════════════════════════════
# PART D: FLAGS
# ══════════════════════════════════════════════════════════════════════════════
"""
FLAGS:
  re.IGNORECASE (re.I)    → case-insensitive matching
  re.MULTILINE  (re.M)    → ^ and $ match start/end of EACH LINE
  re.DOTALL     (re.S)    → . matches newline too
  re.VERBOSE    (re.X)    → allow whitespace and comments in pattern
  re.ASCII      (re.A)    → make \w, \d, \s match ASCII only
  re.UNICODE    (re.U)    → Unicode matching (default in Python 3)

Inline flags: (?i), (?m), (?s), (?x) — inside pattern string itself

Combine flags:
  re.IGNORECASE | re.MULTILINE
  re.I | re.M
"""

print("\n" + "=" * 60)
print("PART D: FLAGS")
print("=" * 60)

# IGNORECASE
text = "Python PYTHON python"
print(f"IGNORECASE: {re.findall(r'python', text, re.IGNORECASE)}")

# MULTILINE
multi_line = """Error: file not found
WARNING: disk usage high
ERROR: connection timeout
info: task complete"""

errors = re.findall(r"^error:.*", multi_line, re.IGNORECASE | re.MULTILINE)
print(f"MULTILINE errors: {errors}")

# DOTALL — . matches newline
html_block = """<div>
  Hello World
</div>"""

# Without DOTALL — . doesn't match newline — no match
m1 = re.search(r"<div>(.+)</div>", html_block)
print(f"Without DOTALL: {m1}")

# With DOTALL
m2 = re.search(r"<div>(.+)</div>", html_block, re.DOTALL)
if m2:
    print(f"With DOTALL: {m2.group(1).strip()!r}")

# VERBOSE — write readable patterns with comments
email_pattern = re.compile(r"""
    [\w.+-]+        # local part (before @)
    @               # literal @
    [\w-]+          # domain name
    \.              # dot
    [a-zA-Z]{2,}    # TLD (2+ letters)
""", re.VERBOSE)

print(f"VERBOSE pattern: {email_pattern.findall('user@example.com, bad@, test@mail.org')}")


# ══════════════════════════════════════════════════════════════════════════════
# PART E: LOOKAHEAD & LOOKBEHIND
# ══════════════════════════════════════════════════════════════════════════════
"""
ZERO-WIDTH ASSERTIONS — match position, not characters:
  (?=pattern)    → Positive lookahead:  what comes AFTER must match
  (?!pattern)    → Negative lookahead:  what comes AFTER must NOT match
  (?<=pattern)   → Positive lookbehind: what comes BEFORE must match
  (?<!pattern)   → Negative lookbehind: what comes BEFORE must NOT match

"Zero-width" = these don't consume characters (not included in match)

Example:
  r"\d+(?= dollars)"  → match digits only if followed by " dollars"
  "100 dollars and 50 euros" → ['100'] (not 50, not followed by dollars)
"""

print("\n" + "=" * 60)
print("PART E: LOOKAHEAD / LOOKBEHIND")
print("=" * 60)

text = "price: $100, cost: 50 euros, budget: $250"

# Positive lookahead — find numbers followed by " euros"
euros = re.findall(r"\d+(?= euros)", text)
print(f"Lookahead (before 'euros'): {euros}")

# Positive lookbehind — find numbers preceded by "$"
dollars = re.findall(r"(?<=\$)\d+", text)
print(f"Lookbehind (after '$'): {dollars}")

# Negative lookahead — find numbers NOT followed by " euros"
not_euros = re.findall(r"\d+(?! euros)", text)
print(f"Negative lookahead (not euros): {not_euros}")

# Real-world: extract token count from LLM output
llm_output = """
Usage: prompt_tokens=150 completion_tokens=300 total_tokens=450
Previous: prompt_tokens=200 completion_tokens=150 total_tokens=350
"""

# Extract ONLY completion_tokens values
completion = re.findall(r"(?<=completion_tokens=)\d+", llm_output)
print(f"\nCompletion tokens: {completion}")

# Extract model names after "model=" but not in JSON context
response = 'Using model="gpt-4" for task. Fallback model=gpt-3.5-turbo available.'
# Find model values WITHOUT quotes (no lookbehind for quote)
models = re.findall(r'(?<=model=)(?!")[\w.-]+', response)
print(f"Model names (no quotes): {models}")


# ══════════════════════════════════════════════════════════════════════════════
# PART F: re.compile() — PERFORMANCE & REUSE
# ══════════════════════════════════════════════════════════════════════════════
"""
re.compile(pattern, flags):
  Pre-compiles pattern into a Pattern object.
  Use when: same pattern used MANY TIMES in a loop.
  Avoids re-compiling pattern on every call.
  Pattern object has same methods: .search(), .match(), .findall(), .sub()

PERFORMANCE TIP:
  Module-level compiled patterns = compiled once, reused forever.
  Function-level re.search() = compiled on first call (cached internally by Python)
  For hot paths: explicit compile() is clearest and fastest.
"""

print("\n" + "=" * 60)
print("PART F: re.compile() — PERFORMANCE")
print("=" * 60)

import time

# Module-level compiled patterns (best practice)
EMAIL_RE    = re.compile(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", re.IGNORECASE)
URL_RE      = re.compile(r"https?://[\w/:%#\$&\?\(\)~\.=\+\-]+")
IP_RE       = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
PHONE_RE    = re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b")
LOG_LINE_RE = re.compile(
    r"(?P<level>ERROR|WARNING|INFO|DEBUG)\s+(?P<msg>.+)",
    re.IGNORECASE
)

texts = [
    "Email me at hello@world.com or call 555-123-4567",
    "Server at 192.168.1.100 URL: https://api.openai.com/v1/chat",
    "ERROR Something went wrong in production",
]

for t in texts:
    emails = EMAIL_RE.findall(t)
    urls   = URL_RE.findall(t)
    ips    = IP_RE.findall(t)
    phones = PHONE_RE.findall(t)
    m      = LOG_LINE_RE.search(t)

    print(f"Text: {t[:50]}...")
    if emails:  print(f"  emails: {emails}")
    if urls:    print(f"  urls:   {urls}")
    if ips:     print(f"  ips:    {ips}")
    if phones:  print(f"  phones: {phones}")
    if m:       print(f"  log:    level={m.group('level')}, msg={m.group('msg')[:30]}")

# Timing: compile once vs per call
n = 10_000
pattern = r"[\w.+-]+@[\w-]+\.[a-z]{2,}"
test_text = "user@example.com"

start = time.perf_counter()
for _ in range(n):
    re.findall(pattern, test_text)
inline_time = time.perf_counter() - start

compiled = re.compile(pattern)
start = time.perf_counter()
for _ in range(n):
    compiled.findall(test_text)
compiled_time = time.perf_counter() - start

print(f"\nPerformance ({n} iterations):")
print(f"  re.findall inline:   {inline_time*1000:.1f}ms")
print(f"  compiled.findall:    {compiled_time*1000:.1f}ms")


# ══════════════════════════════════════════════════════════════════════════════
# PART G: PRODUCTION PATTERNS — LLM OUTPUT PARSING
# ══════════════════════════════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("PART G: PRODUCTION PATTERNS")
print("=" * 60)


# ── 1. Extract code blocks from LLM Markdown output ──
def extract_code_blocks(llm_output: str) -> list[dict]:
    """Extract all ```language ... ``` blocks from LLM response."""
    pattern = re.compile(
        r"```(?P<lang>\w*)\n(?P<code>.*?)```",
        re.DOTALL
    )
    blocks = []
    for m in pattern.finditer(llm_output):
        blocks.append({
            "language": m.group("lang") or "plaintext",
            "code": m.group("code").strip(),
            "start": m.start(),
            "end": m.end(),
        })
    return blocks


llm_response = """
Here's the solution:

```python
async def fetch_data(url: str) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            return await resp.json()
```

And the config:

```json
{
  "model": "gpt-4",
  "temperature": 0.7
}
```
"""

blocks = extract_code_blocks(llm_response)
for b in blocks:
    print(f"Code block [{b['language']}]: {b['code'][:60]}...")


# ── 2. Extract structured data from LLM output ──
def parse_agent_response(text: str) -> dict:
    """Parse structured XML-like tags from LLM output."""
    patterns = {
        "thought":    re.compile(r"<thinking>(.*?)</thinking>", re.DOTALL | re.IGNORECASE),
        "answer":     re.compile(r"<answer>(.*?)</answer>", re.DOTALL | re.IGNORECASE),
        "tool_calls": re.compile(r"<tool_call>(.*?)</tool_call>", re.DOTALL | re.IGNORECASE),
        "citations":  re.compile(r"\[(\d+)\]", re.DOTALL),
    }

    result = {}
    for key, pattern in patterns.items():
        matches = pattern.findall(text)
        if matches:
            result[key] = [m.strip() for m in matches] if len(matches) > 1 else matches[0].strip()
    return result


agent_output = """
<thinking>
The user wants to know about Python async.
I should explain event loops and coroutines.
</thinking>

Python's asyncio uses an event loop [1] to manage coroutines [2].

<answer>
Use `async def` for coroutines and `await` for I/O operations.
</answer>
"""

parsed = parse_agent_response(agent_output)
print(f"\nParsed agent output: {parsed}")


# ── 3. Validate inputs ──
class InputValidator:
    """Regex-based input validation."""

    PATTERNS = {
        "email":    re.compile(r"^[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}$"),
        "phone":    re.compile(r"^\+?1?\s*[-.]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}$"),
        "url":      re.compile(r"^https?://[\w/:%#\$&\?\(\)~\.=\+\-]+$"),
        "ip":       re.compile(r"^(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)$"),
        "slug":     re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$"),
        "uuid":     re.compile(r"^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$", re.IGNORECASE),
        "api_key":  re.compile(r"^sk-[A-Za-z0-9]{48}$"),
    }

    @classmethod
    def validate(cls, value: str, rule: str) -> bool:
        pattern = cls.PATTERNS.get(rule)
        if not pattern:
            raise ValueError(f"Unknown validation rule: {rule}")
        return bool(pattern.fullmatch(value))

    @classmethod
    def validate_all(cls, value: str, *rules: str) -> dict[str, bool]:
        return {rule: cls.validate(value, rule) for rule in rules}


print("\nInput validation:")
tests = [
    ("user@example.com",  "email"),
    ("not-an-email",      "email"),
    ("555-123-4567",      "phone"),
    ("https://api.com/v1","url"),
    ("192.168.1.100",     "ip"),
    ("my-agent-v2",       "slug"),
]
for value, rule in tests:
    result = InputValidator.validate(value, rule)
    icon = "✅" if result else "❌"
    print(f"  {icon} {rule:8}: {value!r}")


# ── 4. Log line parser ──
LOG_PATTERN = re.compile(
    r"(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})"
    r"\s+(?P<level>DEBUG|INFO|WARNING|ERROR|CRITICAL)"
    r"\s+(?P<logger>[\w.]+)"
    r"\s+(?P<message>.+)"
)

logs = [
    "2024-01-15T14:30:22 ERROR agents.researcher Failed to call web_search: timeout",
    "2024-01-15T14:30:23 INFO  agents.researcher Retrying with backoff=2s",
    "2024-01-15T14:30:25 INFO  agents.researcher web_search completed: 15 results",
    "2024-01-15T14:30:26 WARNING budget.tracker Token usage at 85% of limit",
]

print("\nStructured log parsing:")
for line in logs:
    m = LOG_PATTERN.match(line)
    if m:
        d = m.groupdict()
        icon = {"ERROR": "❌", "WARNING": "⚠️", "INFO": "ℹ️", "DEBUG": "🔍"}.get(d["level"], "")
        print(f"  {icon} [{d['level']}] {d['logger']}: {d['message'][:50]}")


# ── 5. Token/prompt cleaning ──
def clean_prompt(text: str) -> str:
    """Clean user input before sending to LLM."""
    # Remove multiple spaces
    text = re.sub(r" {2,}", " ", text)
    # Normalize newlines
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Remove trailing whitespace per line
    text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)
    # Remove zero-width characters
    text = re.sub(r"[​-‍﻿]", "", text)
    return text.strip()


dirty = "Hello   World\n\n\n\nThis has   extra spaces.  \n  "
print(f"\nCleaned prompt: {clean_prompt(dirty)!r}")


# ══════════════════════════════════════════════════════════════════════════════
# PART H: INTERVIEW Q&A
# ══════════════════════════════════════════════════════════════════════════════
"""
Q1: What is the difference between re.match() and re.search()?
A:  re.match():  only matches at the BEGINNING of the string
    re.search(): matches ANYWHERE in the string
    re.fullmatch(): matches the ENTIRE string

    re.match("hello", "say hello") → None
    re.search("hello", "say hello") → Match

Q2: What is greedy vs lazy matching?
A:  Greedy (*,+,{n,m}): match as MUCH as possible
    Lazy (*?,+?,{n,m}?): match as LITTLE as possible

    "<.+>"  with "a<b>c<d>e" → "<b>c<d>" (greedy, takes most)
    "<.+?>" with "a<b>c<d>e" → "<b>"     (lazy, takes least)

Q3: When should you use re.compile()?
A:  Use compile() when:
    - Same pattern used in a loop (thousands of times)
    - Module-level constants (compile once, reuse forever)
    - Complex patterns with flags (more readable)
    Python internally caches last 512 patterns anyway, but explicit
    compile() is clearest for frequently used production patterns.

Q4: What is a non-capturing group (?:)?
A:  (?:pattern) groups without creating a captured group.
    Used for: alternation without needing the captured value
    r"(?:cat|dog)s?" matches "cats", "dogs", "cat", "dog"
    findall() returns the full match, not the group contents.
    vs r"(cat|dog)s?" → findall() returns ["cat", "dog"]

Q5: What are lookahead and lookbehind?
A:  Zero-width assertions — match a position, not characters.
    (?=x) : the text AFTER must match x  (positive lookahead)
    (?!x) : the text AFTER must NOT match x  (negative lookahead)
    (?<=x): the text BEFORE must match x  (positive lookbehind)
    (?<!x): the text BEFORE must NOT match x (negative lookbehind)
    The matched position is NOT included in the result.

    r"\d+(?= dollars)" matches numbers before " dollars"
    "100 dollars 50 euros" → ['100']  (50 not matched — no " dollars" after)

Q6: How do you handle special characters in patterns?
A:  Use re.escape(string) to escape all special regex metacharacters.
    Useful when user input is part of the pattern.

    user_input = "3.14 (pi)"
    safe_pattern = re.escape(user_input)  → r"3\.14\ \(pi\)"
    re.search(safe_pattern, text)  → now safe!

Q7: What is the difference between \b and ^ for word boundaries?
A:  \b : word boundary (transition between \w and \W)
        r"\bcat\b" matches "cat" in "the cat sat" but not "catch"
    ^ : start of string (or line with MULTILINE)
        r"^cat" matches "cat" only at line start

Q8: What causes catastrophic backtracking?
A:  Nested quantifiers on overlapping patterns: r"(a+)+"
    On non-matching input, regex engine tries exponential combinations.
    Solution: be specific, use atomic groups, or possessive quantifiers.
    Avoid: r"(\w+)+" for validating large strings.
"""

print("\n✅ Day40 — re module COMPLETE")
print(f"Topics: Basic patterns, Functions, Groups, Flags, Lookahead/Lookbehind, compile(), Production patterns")
