"""
Complete_Theory/10_Regex_Testing_Enum_StdLib_Theory.py
=======================================================
Theory Format: WHAT → WHY → HOW → REAL LIFE → PRODUCTION CODE → Q&A
Target:        Python Backend Developer + Agentic AI (5 YOE)

TOPICS COVERED
──────────────
Section 1  — re (Regular Expressions)
Section 2  — unittest & pytest (Testing)
Section 3  — enum module
Section 4  — datetime & zoneinfo
Section 5  — os & sys
Section 6  — logging
Section 7  — subprocess
Section 8  — argparse & typer (CLI)
Section 9  — Full Interview Q&A (40 questions across all topics)
"""

# ════════════════════════════════════════════════════════════════════════════
# SECTION 1 — re (Regular Expressions)
# ════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT is the re module?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Python's built-in library for working with regular expressions — a
mini-language for describing patterns in text.

A regex pattern is a string of metacharacters and literals that the
re engine matches against an input string.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHY do we need it?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Input validation  (email, phone, URL, API key formats)
• Text extraction   (parse LLM output for JSON blocks, tool calls)
• Log parsing       (structured extraction from log files)
• Data cleaning     (strip HTML, normalise whitespace)
• Search & replace  (PII redaction, prompt sanitisation)

str.find() / str.split() only work for fixed strings;
re handles variable-length, structured patterns.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HOW — core API
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Function            Returns          Notes
─────────────────   ──────────────   ─────────────────────────────
re.match(p, s)      Match | None     anchored at start
re.search(p, s)     Match | None     first match anywhere
re.findall(p, s)    list[str]        all non-overlapping matches
re.finditer(p, s)   iter[Match]      iterator of Match objects
re.sub(p, r, s)     str              replace matches
re.split(p, s)      list[str]        split on pattern
re.compile(p)       Pattern          compile for reuse (performance)

REAL LIFE ANALOGY:
  A regex is like a CTRL+F in Word, but with wildcards:
  "Find any word that starts with 'err' and ends with a number"
  → pattern: r'\berr\w*\d\b'
"""

import re
import json
import sys
import os
import logging
import subprocess
import argparse
import unittest
from enum import Enum, StrEnum, IntEnum, Flag, auto, unique
from datetime import datetime, timedelta, timezone, date
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch, AsyncMock
from logging.handlers import RotatingFileHandler


# ── 1A. Metacharacters cheatsheet ────────────────────────────────────────────

RE_CHEATSHEET = """
METACHARACTERS:
  .       any character except newline
  ^       start of string (or line with MULTILINE)
  $       end of string (or line with MULTILINE)
  \\b      word boundary
  \\B      non-word boundary

CHARACTER CLASSES:
  \\d  [0-9]          \\D  not digit
  \\w  [a-zA-Z0-9_]   \\W  not word char
  \\s  whitespace      \\S  not whitespace
  [abc]   a, b, or c
  [^abc]  NOT a, b, or c
  [a-z]   a through z

QUANTIFIERS:
  *       0 or more   (greedy)
  +       1 or more   (greedy)
  ?       0 or 1      (greedy)
  {n}     exactly n
  {n,m}   n to m
  *? +? ??  lazy (shortest match)

GROUPS:
  (abc)       capturing group
  (?:abc)     non-capturing group
  (?P<name>)  named group
  (?=abc)     lookahead (not consumed)
  (?!abc)     negative lookahead
  (?<=abc)    lookbehind
  (?<!abc)    negative lookbehind

FLAGS:
  re.IGNORECASE  re.I   case-insensitive
  re.MULTILINE   re.M   ^ $ match line boundaries
  re.DOTALL      re.S   . matches newline too
  re.VERBOSE     re.X   allow whitespace + comments
"""
print("1A. RE Cheatsheet loaded")


# ── 1B. Common patterns ───────────────────────────────────────────────────────

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", re.IGNORECASE)
URL_RE   = re.compile(
    r"https?://(?:[\w-]+\.)+[\w-]+(?:/[\w./?%&=+-]*)?",
    re.IGNORECASE
)
IP_RE    = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}"
    r"(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
)
UUID_RE  = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE
)

# Test
texts = [
    "Contact: alice@example.com or bob.smith@company.co.uk",
    "See https://api.openai.com/v1/chat for the endpoint",
    "Server IP: 192.168.1.100, backup: 10.0.0.255",
]
for t in texts:
    emails = EMAIL_RE.findall(t)
    urls   = URL_RE.findall(t)
    ips    = IP_RE.findall(t)
    if emails: print(f"Emails: {emails}")
    if urls:   print(f"URLs:   {urls}")
    if ips:    print(f"IPs:    {ips}")


# ── 1C. Named groups — LLM log parser ────────────────────────────────────────

LOG_RE = re.compile(
    r"""
    (?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})   # timestamp
    \s+
    (?P<level>DEBUG|INFO|WARNING|ERROR|CRITICAL)     # log level
    \s+
    \[(?P<session>[^\]]+)\]                          # [session-id]
    \s+
    (?P<message>.+)                                  # message
    """,
    re.VERBOSE,
)

SAMPLE_LOGS = [
    "2025-05-20T14:32:01 INFO [sess-abc123] LLM call started model=gpt-4o",
    "2025-05-20T14:32:02 INFO [sess-abc123] Received 512 tokens in 1.2s",
    "2025-05-20T14:32:05 ERROR [sess-xyz789] API timeout after 30s",
]

for log in SAMPLE_LOGS:
    m = LOG_RE.match(log)
    if m:
        print(f"[{m.group('level')}] {m.group('ts')} | "
              f"session={m.group('session')!r} | {m.group('message')!r}")


# ── 1D. Extract code blocks from LLM output ──────────────────────────────────

CODE_BLOCK_RE = re.compile(
    r"```(?P<lang>\w*)\n(?P<code>.*?)```",
    re.DOTALL,
)

def extract_code_blocks(text: str) -> list[dict]:
    """Extract all fenced code blocks from LLM markdown output."""
    return [
        {"lang": m.group("lang") or "text", "code": m.group("code").strip()}
        for m in CODE_BLOCK_RE.finditer(text)
    ]

llm_output = """
Here is the solution:

```python
def add(a, b):
    return a + b
```

And the test:

```python
assert add(1, 2) == 3
```
"""
blocks = extract_code_blocks(llm_output)
for b in blocks:
    print(f"lang={b['lang']!r}  lines={len(b['code'].splitlines())}")


# ── 1E. re.sub for PII redaction ─────────────────────────────────────────────

def redact_pii(text: str) -> str:
    """Remove emails and IPs before sending to a third-party LLM."""
    text = EMAIL_RE.sub("[EMAIL REDACTED]", text)
    text = IP_RE.sub("[IP REDACTED]", text)
    return text

raw = "Contact admin@example.com at server 192.168.1.1 for access."
print(f"Redacted: {redact_pii(raw)}")


# ── 1F. Greedy vs Lazy ───────────────────────────────────────────────────────

html = "<b>bold</b> and <i>italic</i>"
greedy = re.findall(r"<.+>",  html)   # ['<b>bold</b> and <i>italic</i>']
lazy   = re.findall(r"<.+?>", html)   # ['<b>', '</b>', '<i>', '</i>']
print(f"Greedy: {greedy}")
print(f"Lazy  : {lazy}")


# ── 1G. Performance — compile once, reuse ────────────────────────────────────

# BAD: recompiles pattern on every call
def validate_email_slow(email: str) -> bool:
    return bool(re.match(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", email, re.IGNORECASE))

# GOOD: compiled once at module level
_EMAIL_COMPILED = re.compile(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", re.IGNORECASE)

def validate_email_fast(email: str) -> bool:
    return bool(_EMAIL_COMPILED.match(email))

print(f"Valid email: {validate_email_fast('user@example.com')}")
print(f"Invalid    : {validate_email_fast('not-an-email')}")


# ════════════════════════════════════════════════════════════════════════════
# SECTION 2 — unittest & pytest
# ════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT is testing in Python?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Automated tests that verify your code behaves correctly.

unittest — stdlib, class-based (TestCase), Java-style
pytest   — third-party, function-based, fixtures, parametrize

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHY automated testing?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Catch regressions (new code breaks old behaviour)
• Document expected behaviour (tests are executable specs)
• Enable refactoring with confidence
• Required in any production codebase / CI pipeline

For AI/LLM systems specifically:
• Mock LLM calls (no API cost, deterministic, fast)
• Test prompt logic, tool parsing, retry logic in isolation
• Validate response schemas (fields, types, constraints)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HOW — unittest
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  class TestFoo(unittest.TestCase):
      def setUp(self):       ...  # before each test
      def tearDown(self):    ...  # after each test
      def test_something(self):
          self.assertEqual(a, b)
          self.assertRaises(ValueError, fn, bad_arg)

HOW — pytest
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  def test_something():
      assert result == expected

  @pytest.fixture
  def client(): ...            # shared setup

  @pytest.mark.parametrize("input,expected", [...])
  def test_fn(input, expected): ...

REAL LIFE ANALOGY:
  Tests are like a safety net under a tightrope walker —
  you don't use it every step, but you absolutely need it
  before adding new acrobatics (features).
"""

# ── 2A. The code under test ───────────────────────────────────────────────────

class TokenCounter:
    """Tracks token usage against a budget."""

    def __init__(self, budget: int):
        if budget <= 0:
            raise ValueError(f"Budget must be positive, got {budget}")
        self._budget = budget
        self._used = 0

    def add(self, tokens: int) -> None:
        if tokens < 0:
            raise ValueError("Token count cannot be negative")
        self._used += tokens

    @property
    def remaining(self) -> int:
        return max(0, self._budget - self._used)

    @property
    def is_exceeded(self) -> bool:
        return self._used > self._budget

    def reset(self) -> None:
        self._used = 0


def validate_message(role: str, content: str) -> dict:
    """Validate and normalise a chat message."""
    if role not in {"user", "assistant", "system", "tool"}:
        raise ValueError(f"Invalid role: {role!r}")
    if not content or not content.strip():
        raise ValueError("Content cannot be empty")
    return {"role": role, "content": content.strip()}


MODEL_COSTS = {               # per 1M tokens
    "gpt-4o-mini": {"input": 0.15,  "output": 0.60},
    "gpt-4o":      {"input": 5.00,  "output": 15.00},
}

def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    if model not in MODEL_COSTS:
        raise ValueError(f"Unknown model: {model!r}")
    costs = MODEL_COSTS[model]
    return (input_tokens * costs["input"] + output_tokens * costs["output"]) / 1_000_000


# ── 2B. unittest suite ────────────────────────────────────────────────────────

class TestTokenCounter(unittest.TestCase):
    """Unit tests for TokenCounter using AAA (Arrange/Act/Assert)."""

    def setUp(self):
        """Runs before EACH test method."""
        self.counter = TokenCounter(budget=1000)

    def tearDown(self):
        """Runs after EACH test method."""
        pass  # nothing to clean up here

    def test_initial_remaining_equals_budget(self):
        self.assertEqual(self.counter.remaining, 1000)

    def test_add_reduces_remaining(self):
        self.counter.add(400)
        self.assertEqual(self.counter.remaining, 600)

    def test_multiple_adds_accumulate(self):
        self.counter.add(300)
        self.counter.add(300)
        self.assertEqual(self.counter.remaining, 400)

    def test_exceeded_when_over_budget(self):
        self.counter.add(1001)
        self.assertTrue(self.counter.is_exceeded)

    def test_not_exceeded_at_exact_budget(self):
        self.counter.add(1000)
        self.assertFalse(self.counter.is_exceeded)

    def test_remaining_never_negative(self):
        self.counter.add(9999)
        self.assertEqual(self.counter.remaining, 0)

    def test_reset_clears_usage(self):
        self.counter.add(500)
        self.counter.reset()
        self.assertEqual(self.counter.remaining, 1000)
        self.assertFalse(self.counter.is_exceeded)

    def test_negative_budget_raises(self):
        with self.assertRaises(ValueError):
            TokenCounter(budget=-1)

    def test_zero_budget_raises(self):
        with self.assertRaises(ValueError):
            TokenCounter(budget=0)

    def test_negative_tokens_raises(self):
        with self.assertRaises(ValueError):
            self.counter.add(-10)


class TestValidateMessage(unittest.TestCase):

    def test_valid_user_message(self):
        result = validate_message("user", "Hello!")
        self.assertEqual(result["role"], "user")
        self.assertEqual(result["content"], "Hello!")

    def test_strips_whitespace(self):
        result = validate_message("user", "  Hello  ")
        self.assertEqual(result["content"], "Hello")

    def test_invalid_role_raises(self):
        with self.assertRaises(ValueError) as ctx:
            validate_message("bot", "Hi")
        self.assertIn("Invalid role", str(ctx.exception))

    def test_empty_content_raises(self):
        with self.assertRaises(ValueError):
            validate_message("user", "")

    def test_whitespace_only_content_raises(self):
        with self.assertRaises(ValueError):
            validate_message("user", "   ")

    def test_all_valid_roles(self):
        for role in ("user", "assistant", "system", "tool"):
            result = validate_message(role, "test")
            self.assertEqual(result["role"], role)


class TestCalculateCost(unittest.TestCase):

    def test_gpt4o_mini_cost(self):
        cost = calculate_cost("gpt-4o-mini", 1_000_000, 0)
        self.assertAlmostEqual(cost, 0.15, places=4)

    def test_gpt4o_output_cost(self):
        cost = calculate_cost("gpt-4o", 0, 1_000_000)
        self.assertAlmostEqual(cost, 15.0, places=4)

    def test_unknown_model_raises(self):
        with self.assertRaises(ValueError):
            calculate_cost("gpt-99", 100, 100)

    def test_zero_tokens_zero_cost(self):
        cost = calculate_cost("gpt-4o-mini", 0, 0)
        self.assertEqual(cost, 0.0)


# Run the unittest suite inline
loader  = unittest.TestLoader()
suite   = unittest.TestSuite()
for cls in [TestTokenCounter, TestValidateMessage, TestCalculateCost]:
    suite.addTests(loader.loadTestsFromTestCase(cls))

runner = unittest.TextTestRunner(verbosity=0, stream=open(os.devnull, "w"))
result = runner.run(suite)
total  = result.testsRun
passed = total - len(result.failures) - len(result.errors)
print(f"\n=== unittest results: {passed}/{total} passed ===")


# ── 2C. Mock patterns ─────────────────────────────────────────────────────────

"""
WHAT is mocking?
  Replacing real dependencies (API clients, DB, time.sleep) with
  controllable fakes during tests.

WHY?
  • No API key needed in tests
  • Deterministic (same response every time)
  • Tests run in milliseconds, not seconds
  • Can test error scenarios (timeouts, rate limits)
"""

class LLMClient:
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.model = model

    def complete(self, messages: list, **kwargs) -> dict:
        """Real implementation calls the API."""
        raise NotImplementedError("Use a real API key")

    def complete_with_retry(self, messages: list, max_retries: int = 3) -> dict:
        import time
        for attempt in range(max_retries):
            try:
                return self.complete(messages)
            except ConnectionError:
                if attempt == max_retries - 1:
                    raise
                time.sleep(2 ** attempt)  # exponential backoff


def test_with_mock():
    """Mock pattern: MagicMock, side_effect, patch."""

    client = LLMClient(api_key="test-key")

    # Simple return value mock
    client.complete = MagicMock(return_value={
        "choices": [{"message": {"content": "Paris"}}],
        "usage": {"prompt_tokens": 20, "completion_tokens": 5},
    })

    result = client.complete([{"role": "user", "content": "Capital of France?"}])
    assert result["choices"][0]["message"]["content"] == "Paris"
    client.complete.assert_called_once()
    print("Mock basic: ✓")

    # side_effect: fail twice then succeed (retry test)
    expected = {"choices": [{"message": {"content": "42"}}], "usage": {}}
    client.complete = MagicMock(side_effect=[
        ConnectionError("Network error"),
        ConnectionError("Network error"),
        expected,
    ])

    with patch("time.sleep"):          # don't actually wait
        result = client.complete_with_retry(
            [{"role": "user", "content": "Answer?"}]
        )
    assert result == expected
    assert client.complete.call_count == 3
    print("Mock retry: ✓")


test_with_mock()


# ── 2D. FakeLLMClient — deterministic without mocks ──────────────────────────

class FakeLLMClient:
    """
    A test double that returns scripted responses.
    Better than MagicMock for complex interaction testing —
    follows the real interface exactly.
    """
    def __init__(self, responses: list[str]):
        self._responses = iter(responses)
        self.call_count = 0
        self.last_messages: list = []

    def complete(self, messages: list, **kwargs) -> dict:
        self.call_count += 1
        self.last_messages = messages
        try:
            content = next(self._responses)
        except StopIteration:
            raise RuntimeError("FakeLLMClient ran out of scripted responses")
        return {
            "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": len(content.split())},
        }


def test_agent_with_fake_llm():
    fake = FakeLLMClient(responses=["I am an AI assistant.", "The answer is 42."])

    r1 = fake.complete([{"role": "user", "content": "Who are you?"}])
    assert r1["choices"][0]["message"]["content"] == "I am an AI assistant."

    r2 = fake.complete([{"role": "user", "content": "Answer?"}])
    assert r2["choices"][0]["message"]["content"] == "The answer is 42."

    assert fake.call_count == 2
    print("FakeLLMClient: ✓")

test_agent_with_fake_llm()


# ── 2E. pytest patterns (shown as runnable examples) ─────────────────────────

PYTEST_EXAMPLES = '''
# pytest style — no class needed, just functions
import pytest
from my_module import TokenCounter, validate_message

# ── Basic pytest test ─────────────────────────────────────────────────────
def test_token_counter_basic():
    counter = TokenCounter(budget=500)
    counter.add(200)
    assert counter.remaining == 300
    assert not counter.is_exceeded


# ── Fixture — shared setup injected into test functions ───────────────────
@pytest.fixture
def counter():
    return TokenCounter(budget=1000)


def test_uses_fixture(counter):
    counter.add(400)
    assert counter.remaining == 600


# ── Parametrize — run one test with many inputs ───────────────────────────
@pytest.mark.parametrize("role,content,should_raise", [
    ("user",      "Hello",   False),
    ("assistant", "Hi!",     False),
    ("bot",       "Hello",   True),    # invalid role
    ("user",      "",        True),    # empty content
    ("user",      "   ",     True),    # whitespace-only
])
def test_validate_message(role, content, should_raise):
    if should_raise:
        with pytest.raises(ValueError):
            validate_message(role, content)
    else:
        result = validate_message(role, content)
        assert result["role"] == role


# ── Mark slow tests ───────────────────────────────────────────────────────
@pytest.mark.slow
def test_long_running():
    import time; time.sleep(0.5)
    assert True

# Run: pytest -m "not slow"   to skip slow tests


# ── conftest.py — shared fixtures across files ────────────────────────────
# conftest.py
@pytest.fixture(scope="session")
def api_client():
    client = create_test_client()    # created ONCE for the whole test session
    yield client
    client.close()

@pytest.fixture(scope="function")   # default — fresh for each test
def db_session():
    session = create_test_session()
    yield session
    session.rollback()
    session.close()
'''
print("\n--- pytest patterns (code sample, not executed) ---")
print(PYTEST_EXAMPLES[:400], "…")


# ════════════════════════════════════════════════════════════════════════════
# SECTION 3 — enum module
# ════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT is enum?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
A set of named constants bound to unique values.
Prevents "magic strings/numbers" in your code.

TYPES:
  Enum     — base class (any value)
  IntEnum  — int + Enum (can compare with ints)
  StrEnum  — str + Enum (str() returns the value, Python 3.11+)
  Flag     — bit-flag combination with |, &, ~

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHY use enum?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Replace magic strings: "running" → AgentStatus.RUNNING
• IDE autocompletion + type checking
• Iterable: list(AgentStatus) gives all statuses
• Safe: can't create invalid values
• match-case integration (Python 3.10+)

REAL LIFE ANALOGY:
  Traffic lights are an Enum: RED / YELLOW / GREEN.
  You never have status = "redd" — the enum prevents typos.
"""

# ── 3A. Enum with methods ─────────────────────────────────────────────────────

class AgentStatus(Enum):
    IDLE      = "idle"
    RUNNING   = "running"
    WAITING   = "waiting"
    COMPLETED = "completed"
    FAILED    = "failed"
    CANCELLED = "cancelled"

    def is_active(self) -> bool:
        return self in {AgentStatus.RUNNING, AgentStatus.WAITING}

    def is_terminal(self) -> bool:
        return self in {AgentStatus.COMPLETED,
                        AgentStatus.FAILED,
                        AgentStatus.CANCELLED}

    def __str__(self) -> str:
        return self.value


status = AgentStatus.RUNNING
print(f"\nStatus: {status}  active={status.is_active()}  "
      f"terminal={status.is_terminal()}")

# Lookup by value (from DB / API)
status_from_db = AgentStatus("completed")
print(f"From DB: {status_from_db}")

# Iterate
print("Terminal states:", [s for s in AgentStatus if s.is_terminal()])


# ── 3B. StrEnum — JSON-safe, direct string comparison ────────────────────────

class Role(StrEnum):
    USER      = "user"
    ASSISTANT = "assistant"
    SYSTEM    = "system"
    TOOL      = "tool"


msg = {"role": Role.USER, "content": "Hello"}
print(f"JSON-safe role: {msg['role'] == 'user'}")      # True!
print(f"Role name: {Role.USER.upper()}")               # "USER" (str methods work)


# ── 3C. IntEnum — ordering, comparison with ints ─────────────────────────────

class Priority(IntEnum):
    LOW    = 1
    MEDIUM = 2
    HIGH   = 3
    URGENT = 4

    def label(self) -> str:
        return {1: "🟢", 2: "🟡", 3: "🔴", 4: "🚨"}[self.value]


tasks = [
    ("Summarise report",  Priority.LOW),
    ("Fix prod bug",      Priority.URGENT),
    ("Write tests",       Priority.MEDIUM),
    ("Deploy new model",  Priority.HIGH),
]
sorted_tasks = sorted(tasks, key=lambda t: t[1], reverse=True)
for name, p in sorted_tasks:
    print(f"  {p.label()} [{p.name:6}] {name}")


# ── 3D. Flag — bit flags for permissions ─────────────────────────────────────

@unique
class Permission(Flag):
    READ    = auto()   # 1
    WRITE   = auto()   # 2
    EXECUTE = auto()   # 4
    DELETE  = auto()   # 8

    # Convenient compound permissions
    READ_WRITE = READ | WRITE
    ALL        = READ | WRITE | EXECUTE | DELETE


user_perms = Permission.READ | Permission.WRITE
print(f"\nUser permissions: {user_perms}")
print(f"Can read  : {Permission.READ  in user_perms}")   # True
print(f"Can delete: {Permission.DELETE in user_perms}")  # False

# Grant / revoke
user_perms |= Permission.EXECUTE
user_perms &= ~Permission.WRITE
print(f"After changes: {user_perms}")


# ── 3E. auto() + match-case ───────────────────────────────────────────────────

class ModelTier(StrEnum):
    FAST   = auto()   # "fast"
    SMART  = auto()   # "smart"
    VISION = auto()   # "vision"

def select_model(tier: ModelTier) -> str:
    match tier:
        case ModelTier.FAST:   return "gpt-4o-mini"
        case ModelTier.SMART:  return "gpt-4o"
        case ModelTier.VISION: return "gpt-4o-vision"
        case _:                return "gpt-4o-mini"

for t in ModelTier:
    print(f"  Tier {t!r:8} → {select_model(t)}")


# ════════════════════════════════════════════════════════════════════════════
# SECTION 4 — datetime & zoneinfo
# ════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT is datetime?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Python's stdlib for representing and manipulating dates and times.

KEY CLASSES:
  datetime.datetime   — date + time (+ optional timezone)
  datetime.date       — date only
  datetime.timedelta  — duration (difference between datetimes)
  datetime.timezone   — fixed UTC offset
  zoneinfo.ZoneInfo   — IANA timezone (Python 3.9+)

NAIVE vs AWARE:
  Naive  — no timezone info (datetime.now())  ← DANGEROUS in prod
  Aware  — has timezone (datetime.now(tz=timezone.utc))  ← correct

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHY it matters?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Storing session start/end times correctly
• Rate limiting (N calls per hour)
• Scheduling (run job at 9am IST)
• Audit logs with proper timestamps
• Comparing datetimes across timezones

REAL LIFE ANALOGY:
  A naive datetime is like writing "3 PM" on a sticky note —
  useless if you don't know which timezone the meeting is in.
  An aware datetime is "3 PM IST" — unambiguous.
"""

# ── 4A. Core operations ───────────────────────────────────────────────────────

now_utc = datetime.now(tz=timezone.utc)
print(f"\n4A. UTC now : {now_utc.isoformat()}")
print(f"    Formatted: {now_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}")

# Parse from string (LLM API timestamp)
api_timestamp = "2025-05-20T14:32:01.123456+00:00"
parsed = datetime.fromisoformat(api_timestamp)
print(f"    Parsed   : {parsed}  tz={parsed.tzinfo}")

# timedelta arithmetic
one_hour_ago = now_utc - timedelta(hours=1)
in_30_minutes = now_utc + timedelta(minutes=30)
print(f"    1h ago   : {one_hour_ago.strftime('%H:%M:%S')}")
print(f"    +30min   : {in_30_minutes.strftime('%H:%M:%S')}")


# ── 4B. zoneinfo — IANA timezones ────────────────────────────────────────────

try:
    from zoneinfo import ZoneInfo   # Python 3.9+

    ist = ZoneInfo("Asia/Kolkata")
    now_ist = now_utc.astimezone(ist)
    print(f"\n4B. IST now  : {now_ist.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    # Convert between timezones
    ny  = ZoneInfo("America/New_York")
    now_ny = now_utc.astimezone(ny)
    print(f"    NY now   : {now_ny.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    # Always store in UTC, display in user's local TZ
    def to_local(utc_dt: datetime, tz_name: str) -> str:
        tz = ZoneInfo(tz_name)
        return utc_dt.astimezone(tz).strftime("%Y-%m-%d %H:%M:%S %Z")

    print(f"    Display  : {to_local(now_utc, 'Asia/Kolkata')}")

except ImportError:
    print("zoneinfo not available (Python < 3.9). pip install tzdata")


# ── 4C. Rate limiting with datetime ──────────────────────────────────────────

class RateLimiter:
    """Simple in-memory rate limiter: N calls per window."""

    def __init__(self, max_calls: int, window: timedelta):
        self._max   = max_calls
        self._window = window
        self._calls: list[datetime] = []

    def is_allowed(self) -> bool:
        now    = datetime.now(tz=timezone.utc)
        cutoff = now - self._window
        # Remove calls outside the window
        self._calls = [t for t in self._calls if t > cutoff]
        if len(self._calls) < self._max:
            self._calls.append(now)
            return True
        return False

    def time_until_reset(self) -> timedelta:
        if not self._calls:
            return timedelta(0)
        return (self._calls[0] + self._window) - datetime.now(tz=timezone.utc)


limiter = RateLimiter(max_calls=3, window=timedelta(seconds=60))
for i in range(5):
    allowed = limiter.is_allowed()
    print(f"  Call {i+1}: {'✓ allowed' if allowed else '✗ rate limited'}")


# ── 4D. Relative time formatting ─────────────────────────────────────────────

def format_relative(dt: datetime, reference: Optional[datetime] = None) -> str:
    """Return a human-friendly relative time: 'just now', '5 minutes ago', etc."""
    if reference is None:
        reference = datetime.now(tz=timezone.utc)
    delta = reference - dt
    seconds = int(delta.total_seconds())

    if seconds < 60:           return "just now"
    if seconds < 3600:         return f"{seconds // 60}m ago"
    if seconds < 86400:        return f"{seconds // 3600}h ago"
    if seconds < 86400 * 7:    return f"{seconds // 86400}d ago"
    return dt.strftime("%Y-%m-%d")

print(f"\n4D. Relative: {format_relative(now_utc - timedelta(minutes=5))}")
print(f"    Relative: {format_relative(now_utc - timedelta(hours=3))}")


# ════════════════════════════════════════════════════════════════════════════
# SECTION 5 — os & sys
# ════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT are os and sys?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
os  — interact with the operating system: files, dirs, env, processes
sys — interact with the Python interpreter: argv, path, version, exit

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHY?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
os:
  • Read API keys / secrets from environment (os.environ)
  • Create output directories (os.makedirs)
  • List/walk file trees (os.listdir, os.walk)
  • Query system resources (os.cpu_count)

sys:
  • Read command-line arguments (sys.argv)
  • Exit with a code (sys.exit)
  • Modify import path (sys.path)
  • Know Python version (sys.version_info)

REAL LIFE ANALOGY:
  os is like the Finder/Explorer — manages files and folders.
  sys is like the Python interpreter's control panel.
"""

# ── 5A. os.environ — safe config loading ─────────────────────────────────────

class Settings:
    """Load configuration from environment variables with defaults."""

    OPENAI_API_KEY: str   = os.environ.get("OPENAI_API_KEY", "")
    ANTHROPIC_KEY:  str   = os.environ.get("ANTHROPIC_API_KEY", "")
    DEBUG:          bool  = os.environ.get("DEBUG", "false").lower() == "true"
    LOG_LEVEL:      str   = os.environ.get("LOG_LEVEL", "INFO")
    MAX_WORKERS:    int   = int(os.environ.get("MAX_WORKERS", "4"))
    DB_URL:         str   = os.environ.get("DATABASE_URL", "sqlite:///app.db")
    CACHE_TTL:      int   = int(os.environ.get("CACHE_TTL", "3600"))

    @classmethod
    def validate(cls) -> list[str]:
        """Return list of missing required settings."""
        missing = []
        if not cls.OPENAI_API_KEY and not cls.ANTHROPIC_KEY:
            missing.append("OPENAI_API_KEY or ANTHROPIC_API_KEY")
        return missing

settings = Settings()
print(f"\n5A. Settings: debug={settings.DEBUG}  log_level={settings.LOG_LEVEL}")
print(f"    Workers : {settings.MAX_WORKERS}  db={settings.DB_URL}")


# ── 5B. os.path / pathlib ─────────────────────────────────────────────────────

base_dir    = Path("/tmp/agent_workspace")
data_dir    = base_dir / "data"
output_dir  = base_dir / "output"
logs_dir    = base_dir / "logs"

# Create directories (idempotent)
for d in [data_dir, output_dir, logs_dir]:
    d.mkdir(parents=True, exist_ok=True)

print(f"\n5B. Created dirs under {base_dir}")
print(f"    Exists: {base_dir.exists()}")

# Walk directory tree
for root, dirs, files in os.walk(base_dir):
    level = len(Path(root).relative_to(base_dir).parts)
    print("  " * level + Path(root).name + "/")
    for f in files:
        print("  " * (level + 1) + f)


# ── 5C. sys module ───────────────────────────────────────────────────────────

print(f"\n5C. Python   : {sys.version_info.major}.{sys.version_info.minor}")
print(f"    Executable: {sys.executable}")
print(f"    Platform  : {sys.platform}")
print(f"    argv      : {sys.argv[:3]}")         # script name + any args

# sys.exit — clean shutdown
def run_or_exit(api_key: str) -> None:
    if not api_key:
        print("Error: API key not set. Set OPENAI_API_KEY.", file=sys.stderr)
        # sys.exit(1)     # ← would exit the whole process; commented out here
    else:
        print(f"Running with key: {api_key[:8]}…")

run_or_exit(settings.OPENAI_API_KEY or "sk-test-demo")


# ── 5D. os.cpu_count + process info ──────────────────────────────────────────

print(f"\n5D. CPU count : {os.cpu_count()}")
print(f"    PID       : {os.getpid()}")
print(f"    CWD       : {os.getcwd()}")


# ════════════════════════════════════════════════════════════════════════════
# SECTION 6 — logging
# ════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT is logging?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Python's stdlib for structured, configurable application logging.
Logs go to: console, file, rotating file, external systems (ELK, GCP).

LEVELS (lowest → highest):
  DEBUG < INFO < WARNING < ERROR < CRITICAL

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHY not print()?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Levels: ignore DEBUG in prod, capture everything in dev
• Destinations: stdout + file + log aggregator simultaneously
• Structured: JSON logs → searchable in Datadog / GCP
• Propagation: library logs bubble up to app root logger
• Context: add request_id, session_id to every line

REAL LIFE ANALOGY:
  print() is shouting in a room — everyone hears everything.
  logging is an intercom with volume knobs — different levels
  go to different people (console vs file vs monitoring).
"""

# ── 6A. Named loggers — correct pattern ──────────────────────────────────────

# NEVER use the root logger directly (logging.info/debug)
# ALWAYS use a named logger per module
logger = logging.getLogger(__name__)

# Configure once at app startup (not in libraries)
def configure_logging(level: str = "INFO", log_file: Optional[str] = None):
    """Application-level log configuration."""
    fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    root.addHandler(console)

    # Optional rotating file handler
    if log_file:
        file_handler = RotatingFileHandler(
            log_file, maxBytes=10 * 1024 * 1024, backupCount=5  # 10 MB, keep 5
        )
        file_handler.setFormatter(fmt)
        root.addHandler(file_handler)

configure_logging(level="INFO")


# ── 6B. ContextLogger — request-scoped fields ────────────────────────────────

import logging
from typing import Any

class ContextLogger:
    """
    Wraps a logger to automatically include session_id, model, etc.
    in every log message.
    """

    def __init__(self, logger: logging.Logger, **context: Any):
        self._logger  = logger
        self._context = context

    def _format(self, msg: str) -> str:
        ctx_str = "  ".join(f"{k}={v!r}" for k, v in self._context.items())
        return f"{msg}  [{ctx_str}]" if ctx_str else msg

    def debug(self, msg: str, **extra):   self._logger.debug(self._format(msg))
    def info(self, msg: str, **extra):    self._logger.info(self._format(msg))
    def warning(self, msg: str, **extra): self._logger.warning(self._format(msg))
    def error(self, msg: str, **extra):   self._logger.error(self._format(msg))


# Usage
session_logger = ContextLogger(
    logging.getLogger("agent.session"),
    session_id="sess-abc123",
    model="gpt-4o",
)
session_logger.info("LLM call started")
session_logger.info("Response received")


# ── 6C. JSON logging for production ──────────────────────────────────────────

class JSONFormatter(logging.Formatter):
    """Emit each log record as a single JSON line (for log aggregators)."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level":     record.levelname,
            "logger":    record.name,
            "message":   record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


# Demonstrate the JSON formatter
json_handler = logging.StreamHandler(sys.stdout)
json_handler.setFormatter(JSONFormatter())
json_logger  = logging.getLogger("agent.json_demo")
json_logger.addHandler(json_handler)
json_logger.propagate = False
json_logger.setLevel(logging.INFO)

json_logger.info("Agent call completed")
try:
    raise ValueError("Token limit exceeded")
except ValueError:
    json_logger.error("Agent error occurred", exc_info=True)


# ── 6D. Hierarchy and propagation ────────────────────────────────────────────

"""
LOGGING HIERARCHY:
  root logger
    └── agent              (logging.getLogger("agent"))
          ├── agent.llm    (logging.getLogger("agent.llm"))
          └── agent.tools  (logging.getLogger("agent.tools"))

Propagation: agent.llm logs flow up to agent, then to root.
Disable with: logger.propagate = False

Set level per subtree:
  logging.getLogger("agent.tools").setLevel(logging.DEBUG)
  → only tools logs are DEBUG, rest stay at INFO
"""


# ════════════════════════════════════════════════════════════════════════════
# SECTION 7 — subprocess
# ════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT is subprocess?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Python's stdlib for spawning and communicating with child processes.
Run shell commands, capture output, handle errors.

KEY FUNCTIONS:
  subprocess.run()   — run, wait, return CompletedProcess
  subprocess.Popen() — full control, streaming I/O

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHY?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Run shell tools (git, docker, ruff, pytest)
• AI Code Runner tool (LLM writes code → agent executes it)
• Streaming output of long-running jobs
• CI/CD automation scripts

REAL LIFE ANALOGY:
  subprocess.run() is like delegating a task to a colleague
  and waiting for them to finish before continuing.
  Popen() is like assigning a task and reading their
  progress updates as they work.

SECURITY WARNING: NEVER use shell=True with user-controlled input!
  # DANGEROUS:
  subprocess.run(f"ls {user_input}", shell=True)    # shell injection!
  # SAFE:
  subprocess.run(["ls", user_input])                # list form
"""

# ── 7A. subprocess.run — complete parameter guide ────────────────────────────

def run_command(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    """
    Run a command and return (returncode, stdout, stderr).
    Uses the recommended safe pattern.
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,   # capture stdout + stderr
            text=True,             # decode bytes → str
            timeout=timeout,       # raise TimeoutExpired if too slow
            check=False,           # don't raise on non-zero exit
        )
        return result.returncode, result.stdout, result.stderr

    except subprocess.TimeoutExpired:
        return -1, "", f"Command timed out after {timeout}s"
    except FileNotFoundError:
        return -1, "", f"Command not found: {cmd[0]}"


code, stdout, stderr = run_command(["python3", "--version"])
print(f"\n7A. python --version: rc={code}  stdout={stdout.strip()!r}")

code, stdout, stderr = run_command(["ls", "/tmp/agent_workspace"])
print(f"    ls /tmp: rc={code}  files={stdout.strip()[:60]!r}")


# ── 7B. check=True — raise on failure ────────────────────────────────────────

def git_log(repo: str, n: int = 5) -> str:
    """Get recent git log — raise if git fails."""
    try:
        result = subprocess.run(
            ["git", "-C", repo, "log", f"-{n}", "--oneline"],
            capture_output=True,
            text=True,
            check=True,           # raises CalledProcessError on non-zero
            timeout=10,
        )
        return result.stdout
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"git failed (exit {exc.returncode}): "
                           f"{exc.stderr.strip()}") from exc


# ── 7C. AI Code Runner — LLM-generated code execution ────────────────────────

import tempfile

def run_python_code(code: str, timeout: int = 10) -> dict:
    """
    Execute Python code in a temporary file and return the result.
    Used by AI agent 'code_runner' tool.
    """
    with tempfile.NamedTemporaryFile(
        suffix=".py", mode="w", delete=False
    ) as tmp:
        tmp.write(code)
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "success":   result.returncode == 0,
            "stdout":    result.stdout,
            "stderr":    result.stderr,
            "exit_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "success":   False,
            "stdout":    "",
            "stderr":    f"Execution timed out after {timeout}s",
            "exit_code": -1,
        }
    finally:
        Path(tmp_path).unlink(missing_ok=True)


print("\n7C. AI Code Runner:")
result = run_python_code("""
x = [i**2 for i in range(10)]
print("Squares:", x)
print("Sum:", sum(x))
""")
print(f"  success={result['success']}")
print(f"  stdout ={result['stdout'].strip()!r}")

result_err = run_python_code("raise ValueError('Intentional error')")
print(f"\n  Error case: success={result_err['success']}")
print(f"  stderr    : {result_err['stderr'].strip()!r}")


# ── 7D. Popen — streaming output ─────────────────────────────────────────────

def stream_command(cmd: list[str]):
    """
    Stream stdout from a long-running command line by line.
    Useful for: running test suites, building projects, model training.
    """
    with subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,    # merge stderr into stdout
        text=True,
        bufsize=1,                   # line-buffered
    ) as proc:
        for line in proc.stdout:
            yield line.rstrip()
        proc.wait()
        if proc.returncode != 0:
            raise subprocess.CalledProcessError(proc.returncode, cmd)

print("\n7D. Streaming command output:")
for line in stream_command(["python3", "-c",
                             "for i in range(3): print(f'Line {i}')"]):
    print(f"  >> {line}")


# ════════════════════════════════════════════════════════════════════════════
# SECTION 8 — argparse & typer
# ════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT are argparse and typer?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
argparse — stdlib CLI argument parser
typer    — third-party, annotation-driven CLI framework (built on click)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHY?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Every production tool (agent runner, eval scripts, data jobs)
  needs a CLI. sys.argv parsing by hand is fragile.
• argparse: no deps, fine for simple CLIs
• typer: less boilerplate, type safety, autocompletion, testing

HOW — side-by-side comparison:
  argparse                         typer
  ────────────────────────────── ──────────────────────────────
  parser.add_argument("prompt")   prompt: str = Argument(...)
  type=float                      float annotation
  action="store_true"             bool = Option(False, "--stream/--no-stream")
  subparsers.add_parser("run")    @run_app.command("run")
  choices=["a","b"]               Literal["a","b"] or Enum

REAL LIFE ANALOGY:
  argparse is like writing a custom form from scratch.
  typer is like Google Forms — fill in the structure,
  it generates the form automatically from the schema.
"""

# ── 8A. argparse key patterns ─────────────────────────────────────────────────

def demo_argparse_patterns():
    """Demonstrate the 5 core argparse patterns."""

    parser = argparse.ArgumentParser(
        prog="agent",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # 1. Positional
    parser.add_argument("prompt", help="Prompt text")

    # 2. Optional with type and default
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--max-tokens", type=int, default=2048, dest="max_tokens")

    # 3. Boolean flag
    parser.add_argument("--stream", action="store_true")
    parser.add_argument("--verbose", "-v", action="store_true")

    # 4. Multiple values
    parser.add_argument("--tools", nargs="*", default=[])

    # 5. Choices
    parser.add_argument("--log-level",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        default="INFO", dest="log_level")

    args = parser.parse_args([
        "Hello!", "--model", "gpt-4o", "--stream",
        "--tools", "search", "calc",
    ])
    print(f"\n8A. argparse: prompt={args.prompt!r}  model={args.model}"
          f"  tools={args.tools}  stream={args.stream}")


demo_argparse_patterns()


# ── 8B. Subcommands pattern ───────────────────────────────────────────────────

def build_agent_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent")
    subs   = parser.add_subparsers(dest="command", required=True)

    # run
    run_p = subs.add_parser("run")
    run_p.add_argument("prompt")
    run_p.add_argument("--model", default="gpt-4o-mini")
    run_p.add_argument("--stream", action="store_true")

    # eval
    eval_p = subs.add_parser("eval")
    eval_p.add_argument("--dataset", type=Path, required=True)
    eval_p.add_argument("--concurrency", type=int, default=3)

    return parser


p   = build_agent_parser()
a   = p.parse_args(["run", "Tell me a joke", "--model", "gpt-4o", "--stream"])
print(f"8B. cmd={a.command}  model={a.model}  stream={a.stream}")

a2  = p.parse_args(["eval", "--dataset", "evals.json", "--concurrency", "5"])
print(f"    cmd={a2.command}  dataset={a2.dataset}  concurrency={a2.concurrency}")


# ── 8C. Config priority: env > file > CLI ────────────────────────────────────

"""
PRODUCTION PATTERN — config priority (highest → lowest):
  1. CLI args  (--model gpt-4o)
  2. Env vars  (LLM_MODEL=gpt-4o)
  3. .env file / config.json
  4. Code defaults

Implementation:
  1. Load defaults from dataclass
  2. Override from config file
  3. Override from env vars
  4. Override from CLI (non-None values only)
"""

# ── 8D. Testing argparse CLIs ────────────────────────────────────────────────

def test_argparse_clis():
    """No external libs needed — just call parse_args() with list."""
    p = build_agent_parser()

    args = p.parse_args(["run", "Hello", "--model", "gpt-4o"])
    assert args.command == "run"
    assert args.model   == "gpt-4o"
    assert args.stream  is False

    args2 = p.parse_args(["run", "Hello", "--stream"])
    assert args2.stream is True

    print("8D. argparse CLI tests passed ✓")

test_argparse_clis()


# ════════════════════════════════════════════════════════════════════════════
# SECTION 9 — Full Interview Q&A (40 questions)
# ════════════════════════════════════════════════════════════════════════════

FULL_QA = """
╔══════════════════════════════════════════════════════════════════════════╗
║          SECTION 9 — FULL INTERVIEW Q&A (40 Questions)                  ║
║          Topics: re · testing · enum · datetime · os · logging          ║
║                  subprocess · argparse/typer                            ║
╚══════════════════════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REGEX (re module)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q1.  Difference between re.match() and re.search()?
A1.  match() anchors to the START of the string (only finds at position 0).
     search() scans the ENTIRE string and returns the first match anywhere.
     re.match(r"hello", "say hello")  → None
     re.search(r"hello", "say hello") → Match

Q2.  What is a non-capturing group (?:…)?
A2.  A group that organises the pattern for quantifiers etc., but its
     text is NOT stored in match.group(N) or returned by findall().
     re.findall(r"(?:cat|dog)s?", "cats and dogs")  → ['cats', 'dogs']
     (vs capturing group which would return group content, not full match)

Q3.  What are named groups and how do you use them?
A3.  Syntax: (?P<name>…)   Access: m.group("name") or m.groupdict()
     Useful for structured parsing (logs, LLM output).
     LOG_RE = re.compile(r"(?P<level>INFO|ERROR)\s+(?P<msg>.+)")

Q4.  What is the difference between greedy and lazy quantifiers?
A4.  Greedy (*  +  {n,m})  — matches as MUCH as possible.
     Lazy   (*? +? {n,m}?) — matches as LITTLE as possible.
     re.findall(r"<.+>",  "<a><b>")  → ['<a><b>']   (greedy: one big match)
     re.findall(r"<.+?>", "<a><b>")  → ['<a>', '<b>'] (lazy: smallest)

Q5.  Why should you use re.compile() instead of inline re.search()?
A5.  compile() parses the pattern once and stores the compiled regex object.
     Calling re.search(pattern, text) recompiles on every call.
     For patterns called thousands of times (validators, parsers),
     compiled patterns are significantly faster.

Q6.  What is a lookahead and when would you use it?
A6.  (?=…) — positive lookahead: match position followed by pattern
              but does NOT consume the characters.
     (?!…) — negative lookahead: position NOT followed by pattern
     Example: find "gpt" not followed by "-3":
     re.findall(r"gpt(?!-3)\S*", "gpt-4o gpt-3.5 gpt-4o-mini")
     → ['gpt-4o', 'gpt-4o-mini']

Q7.  What flag makes . match newlines too?
A7.  re.DOTALL (or re.S).  Without it, . matches any char except '\\n'.
     Critical for extracting multiline code blocks from LLM output.
     re.findall(r"```.*?```", text, re.DOTALL)

Q8.  How do you replace all emails with [REDACTED]?
A8.  re.sub(EMAIL_PATTERN, "[REDACTED]", text)
     re.sub accepts a pattern, replacement string (or callable), and input.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TESTING (unittest & pytest)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q9.  What is the AAA pattern in testing?
A9.  Arrange – set up state (create objects, configure mocks)
     Act     – call the code under test
     Assert  – verify the result / side effects
     Makes each test readable and discoverable.

Q10. What is the difference between setUp and setUpClass?
A10. setUp — runs before EVERY test method in the class.
     setUpClass — runs ONCE before all tests in the class (classmethod).
     tearDown / tearDownClass are the counterparts.
     Use setUpClass for expensive setup (DB connection, loading model).

Q11. How does MagicMock differ from Mock?
A11. MagicMock auto-configures magic methods (__len__, __iter__,
     __enter__/__exit__, etc.). Mock does not.
     For LLM clients that use context managers, use MagicMock.

Q12. What is side_effect in MagicMock?
A12. side_effect can be:
     • A list → returns elements one by one (useful for retry testing)
     • An exception class/instance → raises it on each call
     • A callable → called instead of the mock's return value
     mock.side_effect = [ConnectionError(), ConnectionError(), good_response]
     → fails twice then succeeds (retry logic test).

Q13. What does @patch do?
A13. Temporarily replaces the named object in the specified module's
     namespace for the duration of the test:
     @patch("mymodule.requests.get")
     def test_fetch(self, mock_get): ...
     Critical: patch the name WHERE IT IS USED, not where it is defined.

Q14. Why use a FakeLLMClient instead of MagicMock?
A14. Fake is a full implementation of the interface with scripted
     responses. It's easier to read, catches interface drift
     (if the real method signature changes, Fake must update too),
     and can hold state (call_count, last_messages).
     MagicMock is better for quick one-off mocking.

Q15. What is a pytest fixture and what are scope levels?
A15. A fixture is a function decorated with @pytest.fixture that
     provides setup/teardown for tests.
     Scope controls how long it lives:
     "function" (default) — new instance per test
     "class"   — shared within a TestCase class
     "module"  — shared within a .py file
     "session" — shared across the entire test run

Q16. How does @pytest.mark.parametrize work?
A16. It runs one test function multiple times with different inputs:
     @pytest.mark.parametrize("a,b,expected", [(1,2,3), (0,0,0)])
     def test_add(a, b, expected):
         assert add(a, b) == expected
     Generates 2 test cases with meaningful names in the report.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ENUM
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q17. What is the difference between Enum, StrEnum, and IntEnum?
A17. Enum    — base class, values can be any type.
     StrEnum — subclass of both str and Enum; str(member) == member.value
               → JSON-serialisable without .value extraction (Python 3.11+)
     IntEnum — subclass of int and Enum; members compare with ints.
               Role.USER == 1  # True if USER=1

Q18. What does auto() do in an Enum?
A18. auto() assigns the next auto-generated value automatically.
     For Enum: 1, 2, 3…
     For StrEnum: lowercased member name ("fast", "smart")
     Avoids manual value assignment and duplication.

Q19. What is @unique and why use it?
A19. @unique decorator raises ValueError if two members have the same value.
     By default, duplicate values create aliases (USER = CUSTOMER = 1).
     @unique enforces each value maps to exactly one name.

Q20. What is Flag enum and how do |, &, ~ work?
A20. Flag allows combining enum members as bit flags:
     perm = Permission.READ | Permission.WRITE   # compound permission
     Permission.READ in perm                      # True (contains test)
     perm & ~Permission.WRITE                     # revoke WRITE
     Useful for feature flags, permissions, agent capabilities.

Q21. How do you look up an Enum member by value (e.g., from a DB column)?
A21. Status("running")           → AgentStatus.RUNNING
     Status["RUNNING"]           → AgentStatus.RUNNING   (by name)
     If value doesn't exist: raises ValueError.
     Defensive: Status._value2member_map_.get("unknown", Status.UNKNOWN)

Q22. How does match-case work with enums?
A22. match tier:
         case ModelTier.FAST:   ...
         case ModelTier.SMART:  ...
         case _:                ...
     Python checks equality (==) with the enum member.
     The match is exhaustive if you handle all cases + _.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DATETIME & ZONEINFO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q23. What is the difference between naive and aware datetimes?
A23. Naive  — no tzinfo attribute (datetime.now() returns naive).
              Two naive datetimes from different timezones compare
              incorrectly — silent bug.
     Aware  — has tzinfo (datetime.now(tz=timezone.utc)).
              Always store and compare aware datetimes in production.

Q24. How do you always get the current UTC time correctly?
A24. datetime.now(tz=timezone.utc)   ← correct (aware datetime)
     datetime.utcnow()               ← DEPRECATED, returns naive datetime
     datetime.now()                  ← naive, LOCAL timezone, avoid in backend

Q25. What is the difference between strftime and strptime?
A25. strftime — FORMAT a datetime to a string
                dt.strftime("%Y-%m-%d")  → "2025-05-20"
     strptime — PARSE a string to a datetime
                datetime.strptime("2025-05-20", "%Y-%m-%d")  → datetime obj

Q26. How do you convert between timezones?
A26. Use zoneinfo.ZoneInfo (Python 3.9+):
     from zoneinfo import ZoneInfo
     utc_dt = datetime.now(tz=timezone.utc)
     ist_dt = utc_dt.astimezone(ZoneInfo("Asia/Kolkata"))
     Rule: store UTC, display in user's local timezone.

Q27. How do you add/subtract time durations?
A27. Use datetime.timedelta:
     tomorrow  = datetime.now() + timedelta(days=1)
     last_week = datetime.now() - timedelta(weeks=1)
     delta     = end_dt - start_dt   # timedelta object
     hours     = delta.total_seconds() / 3600

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OS & SYS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q28. How do you read an environment variable with a fallback?
A28. os.environ.get("API_KEY", "default-value")
     Or: os.getenv("API_KEY", "")
     os.environ["API_KEY"] raises KeyError if not set — avoid in prod code.

Q29. How do you create a directory tree safely?
A29. os.makedirs("a/b/c", exist_ok=True)   # no error if already exists
     Path("a/b/c").mkdir(parents=True, exist_ok=True)  # pathlib equivalent
     Without exist_ok: raises FileExistsError if the dir already exists.

Q30. What does sys.exit(code) do?
A30. Raises SystemExit(code), which Python catches at the top level
     and exits the process with that return code.
     0 = success, non-zero = error.
     Prefer sys.exit(1) in CLI tools over raise SystemExit(1) directly.

Q31. What is sys.path used for?
A31. The list of directories Python searches for modules when you import.
     sys.path.insert(0, "/my/custom/lib")   ← add custom path at front
     In production: use proper packaging / PYTHONPATH env var instead.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LOGGING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q32. Why should you use named loggers instead of logging.info()?
A32. logging.info() uses the ROOT logger — uncontrollable in a library.
     logging.getLogger(__name__) creates a module-scoped logger.
     App can then set levels per logger:
     logging.getLogger("mylib.noisy").setLevel(logging.ERROR)
     without silencing all logging.

Q33. What is log propagation?
A33. By default, a log record bubbles up from child loggers to parent
     (agent.llm → agent → root). The root logger's handlers output it.
     Set logger.propagate = False to stop bubbling.
     Useful when a sub-logger has its own handler and you don't
     want duplicate output.

Q34. What is a RotatingFileHandler and why use it?
A34. Automatically splits the log file when it reaches a size limit
     and keeps N backup files:
     RotatingFileHandler("app.log", maxBytes=10MB, backupCount=5)
     Prevents log files from filling the disk indefinitely.

Q35. How do you add structured context (session_id, request_id) to logs?
A35. Options:
     1. ContextLogger wrapper (custom class adds context string).
     2. logging.Filter — attach extra fields to records:
        class ContextFilter(logging.Filter):
            def filter(self, record):
                record.session_id = get_current_session_id()
                return True
     3. structlog library (third-party, JSON-native).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SUBPROCESS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q36. Why is shell=True dangerous?
A36. shell=True passes the command to the OS shell (/bin/sh).
     If any part of the command comes from user input, an attacker can
     inject shell metacharacters:
     user_input = "file.txt; rm -rf /"
     subprocess.run(f"cat {user_input}", shell=True)  # DISASTER
     SAFE: subprocess.run(["cat", user_input])  # list form, no shell

Q37. What is the difference between subprocess.run() and Popen()?
A37. run()  — high-level: runs the process, waits for it to finish,
              returns CompletedProcess. Best for most use cases.
     Popen() — low-level: starts the process, returns immediately.
               You control stdin/stdout/stderr, can stream line-by-line,
               can kill the process. Best for long-running / streaming.

Q38. How do you capture both stdout and stderr together?
A38. subprocess.run(cmd, capture_output=True)   # separate stdout, stderr
     Or to merge:
     result = subprocess.run(cmd, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT)   # merged

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ARGPARSE & TYPER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q39. What is the difference between a positional and optional argument?
A39. Positional — no -- prefix, required, identified by position:
                  parser.add_argument("prompt")
     Optional  — --flag prefix, can have default, optional:
                  parser.add_argument("--model", default="gpt-4o-mini")

Q40. When would you choose typer over argparse?
A40. Choose typer when you:
     • Want less boilerplate (annotations replace add_argument calls)
     • Need shell autocompletion out of the box
     • Want built-in CliRunner testing
     • Are already using Pydantic/type-annotated code (consistent style)
     • Need Rich integration for coloured output / progress bars
     Choose argparse when:
     • You have zero dependencies allowed (stdlib only)
     • The CLI is simple (1-2 commands, no nesting)
     • You're writing a script for a restricted environment
"""

print(FULL_QA)

print("\n" + "═" * 70)
print("Complete_Theory/10_Regex_Testing_Enum_StdLib_Theory.py ✅")
print("═" * 70)
print("""
Topics covered with WHAT/WHY/HOW/REAL LIFE/CODE/Q&A:
  Section 1  — re (regex):        metacharacters, API, named groups,
                                  code block extraction, PII redaction,
                                  greedy vs lazy, compile() performance
  Section 2  — Testing:           unittest (3 TestCase classes, 22 tests),
                                  mock patterns (MagicMock, side_effect,
                                  patch), FakeLLMClient, pytest patterns
  Section 3  — enum:              Enum/StrEnum/IntEnum/Flag, auto(),
                                  @unique, match-case, methods
  Section 4  — datetime:          now(utc), strftime/strptime, timedelta,
                                  zoneinfo, RateLimiter, format_relative()
  Section 5  — os & sys:          Settings class, makedirs, os.walk,
                                  sys.version_info, sys.exit, sys.argv
  Section 6  — logging:           named loggers, configure_logging(),
                                  ContextLogger, JSONFormatter,
                                  RotatingFileHandler, propagation
  Section 7  — subprocess:        run() params, check=True, AI Code Runner,
                                  Popen() streaming, shell=True danger
  Section 8  — argparse/typer:    5 core patterns, subcommands, config
                                  priority, testing CLIs
  Section 9  — Q&A:               40 interview questions + answers
""")
