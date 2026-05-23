"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  DAY 41 — Testing: unittest + pytest (COMPLETE)                              ║
║  Level: Basic → Advanced → Production AI Agent Testing                       ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHY TESTING?
  - Catch bugs BEFORE production (not after customer complains)
  - Refactor code with confidence (tests tell you if you broke something)
  - Documentation: tests show HOW to use the code
  - Required in every Python backend/AI job

TOPICS:
  Part A: unittest — built-in, class-based
  Part B: pytest — modern, function-based (industry standard)
  Part C: Fixtures — setup/teardown reusable
  Part D: Parametrize — test multiple inputs
  Part E: Mocking — replace real dependencies with fakes
  Part F: Testing async code
  Part G: Coverage — measure how much code is tested
  Part H: Production AI agent testing patterns
  Part I: Interview Q&A

RUN TESTS:
  python -m pytest Day41_Testing/01_unittest_pytest.py -v
  python -m pytest Day41_Testing/ -v --tb=short
  python -m pytest -v -k "test_email"        # filter by name
  python -m pytest --cov=. --cov-report=html  # with coverage
"""

import unittest
from unittest.mock import MagicMock, patch, AsyncMock, call
import asyncio
import time
from typing import Optional
from dataclasses import dataclass


# ══════════════════════════════════════════════════════════════════════════════
# CODE UNDER TEST — The actual functions/classes we'll test
# ══════════════════════════════════════════════════════════════════════════════

class TokenCounter:
    """Simple token counter."""

    def __init__(self, model: str = "gpt-4", limit: int = 8192):
        self.model = model
        self.limit = limit
        self._used = 0

    def add(self, tokens: int) -> None:
        if tokens < 0:
            raise ValueError(f"tokens must be >= 0, got {tokens}")
        self._used += tokens

    def remaining(self) -> int:
        return self.limit - self._used

    def is_exceeded(self) -> bool:
        return self._used > self.limit

    def reset(self) -> None:
        self._used = 0

    @property
    def used(self) -> int:
        return self._used

    def __repr__(self) -> str:
        return f"TokenCounter(model={self.model!r}, used={self._used}, limit={self.limit})"


def validate_message(role: str, content: str) -> dict:
    """Validate and build a chat message."""
    VALID_ROLES = {"system", "user", "assistant", "tool"}
    if role not in VALID_ROLES:
        raise ValueError(f"Invalid role {role!r}. Must be one of {VALID_ROLES}")
    if not content or not content.strip():
        raise ValueError("content cannot be empty")
    if len(content) > 10_000:
        raise ValueError(f"content too long ({len(content)} > 10000 chars)")
    return {"role": role, "content": content.strip()}


def calculate_cost(prompt_tokens: int, completion_tokens: int, model: str = "gpt-4") -> float:
    """Calculate LLM API cost."""
    PRICES = {
        "gpt-4":        (0.03, 0.06),   # (prompt_per_1k, completion_per_1k)
        "gpt-3.5-turbo":(0.001, 0.002),
        "claude-3-opus": (0.015, 0.075),
    }
    if model not in PRICES:
        raise ValueError(f"Unknown model: {model}")
    prompt_price, completion_price = PRICES[model]
    return (prompt_tokens / 1000 * prompt_price) + (completion_tokens / 1000 * completion_price)


class LLMClient:
    """LLM client with external API call — good for mock testing."""

    def __init__(self, api_key: str, model: str = "gpt-4"):
        self.api_key = api_key
        self.model = model
        self._call_count = 0

    def complete(self, prompt: str) -> dict:
        """Makes real API call — we'll mock this in tests."""
        # In production: calls real OpenAI API
        raise NotImplementedError("Use mock in tests!")

    def complete_with_retry(self, prompt: str, max_retries: int = 3) -> dict:
        """Retries on failure."""
        for attempt in range(max_retries):
            try:
                return self.complete(prompt)
            except ConnectionError as e:
                if attempt == max_retries - 1:
                    raise
                time.sleep(0.01)  # short delay in tests
        return {}


async def async_fetch_all(prompts: list[str], client: LLMClient) -> list[dict]:
    """Async function — fetch all prompts concurrently."""
    tasks = [asyncio.to_thread(client.complete, p) for p in prompts]
    return await asyncio.gather(*tasks, return_exceptions=True)


# ══════════════════════════════════════════════════════════════════════════════
# PART A: unittest — BUILT-IN CLASS-BASED TESTING
# ══════════════════════════════════════════════════════════════════════════════
"""
UNITTEST STRUCTURE:
  class TestSomething(unittest.TestCase):
      def setUp(self):          # runs BEFORE each test method
          ...
      def tearDown(self):       # runs AFTER each test method
          ...
      def test_something(self): # test method — MUST start with "test_"
          self.assertEqual(a, b)
          self.assertRaises(ValueError, func, arg)

ASSERTION METHODS:
  assertEqual(a, b)         a == b
  assertNotEqual(a, b)      a != b
  assertTrue(x)             bool(x) is True
  assertFalse(x)            bool(x) is False
  assertIsNone(x)           x is None
  assertIsNotNone(x)        x is not None
  assertIn(a, b)            a in b
  assertNotIn(a, b)         a not in b
  assertRaises(ExcType)     raises ExcType
  assertAlmostEqual(a, b, places=7)
  assertGreater(a, b)       a > b
  assertLess(a, b)          a < b
  assertIsInstance(a, T)    isinstance(a, T)
"""

print("=" * 60)
print("PART A: unittest")
print("=" * 60)


class TestTokenCounter(unittest.TestCase):
    """Test suite for TokenCounter class."""

    def setUp(self) -> None:
        """Called before EACH test — fresh counter every time."""
        self.counter = TokenCounter(model="gpt-4", limit=1000)

    def tearDown(self) -> None:
        """Called after EACH test — cleanup if needed."""
        pass   # nothing to clean up here

    # ── Basic tests ──
    def test_initial_state(self) -> None:
        self.assertEqual(self.counter.used, 0)
        self.assertEqual(self.counter.remaining(), 1000)
        self.assertFalse(self.counter.is_exceeded())

    def test_add_tokens(self) -> None:
        self.counter.add(300)
        self.assertEqual(self.counter.used, 300)
        self.assertEqual(self.counter.remaining(), 700)

    def test_add_multiple_times(self) -> None:
        self.counter.add(100)
        self.counter.add(200)
        self.counter.add(50)
        self.assertEqual(self.counter.used, 350)

    def test_exceed_limit(self) -> None:
        self.counter.add(1001)
        self.assertTrue(self.counter.is_exceeded())

    def test_reset(self) -> None:
        self.counter.add(500)
        self.counter.reset()
        self.assertEqual(self.counter.used, 0)

    # ── Edge cases ──
    def test_add_zero(self) -> None:
        self.counter.add(0)
        self.assertEqual(self.counter.used, 0)  # no change

    def test_add_exactly_at_limit(self) -> None:
        self.counter.add(1000)
        self.assertFalse(self.counter.is_exceeded())  # equal = not exceeded
        self.assertEqual(self.counter.remaining(), 0)

    # ── Error cases ──
    def test_add_negative_raises(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            self.counter.add(-50)
        self.assertIn(">= 0", str(ctx.exception))

    def test_repr(self) -> None:
        self.counter.add(200)
        self.assertIn("gpt-4", repr(self.counter))
        self.assertIn("200", repr(self.counter))


class TestValidateMessage(unittest.TestCase):
    """Test suite for validate_message function."""

    def test_valid_user_message(self) -> None:
        result = validate_message("user", "Hello world")
        self.assertEqual(result["role"], "user")
        self.assertEqual(result["content"], "Hello world")

    def test_valid_system_message(self) -> None:
        result = validate_message("system", "You are a helpful assistant.")
        self.assertIsInstance(result, dict)
        self.assertIn("role", result)
        self.assertIn("content", result)

    def test_all_valid_roles(self) -> None:
        for role in ["system", "user", "assistant", "tool"]:
            result = validate_message(role, "test content")
            self.assertEqual(result["role"], role)

    def test_invalid_role(self) -> None:
        with self.assertRaises(ValueError):
            validate_message("admin", "content")

    def test_empty_content(self) -> None:
        with self.assertRaises(ValueError):
            validate_message("user", "")

    def test_whitespace_only_content(self) -> None:
        with self.assertRaises(ValueError):
            validate_message("user", "   \n\t  ")

    def test_content_trimmed(self) -> None:
        result = validate_message("user", "  hello  ")
        self.assertEqual(result["content"], "hello")  # stripped

    def test_too_long_content(self) -> None:
        with self.assertRaises(ValueError):
            validate_message("user", "x" * 10_001)


class TestCalculateCost(unittest.TestCase):
    """Test cost calculation."""

    def test_gpt4_cost(self) -> None:
        # 1000 prompt tokens + 500 completion tokens at gpt-4 rates
        cost = calculate_cost(1000, 500, "gpt-4")
        expected = (1000 / 1000 * 0.03) + (500 / 1000 * 0.06)  # 0.03 + 0.03
        self.assertAlmostEqual(cost, expected, places=6)

    def test_zero_tokens(self) -> None:
        cost = calculate_cost(0, 0, "gpt-4")
        self.assertEqual(cost, 0.0)

    def test_unknown_model(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            calculate_cost(100, 100, "unknown-model")
        self.assertIn("Unknown model", str(ctx.exception))

    def test_cheaper_model(self) -> None:
        gpt4_cost   = calculate_cost(1000, 1000, "gpt-4")
        gpt35_cost  = calculate_cost(1000, 1000, "gpt-3.5-turbo")
        self.assertGreater(gpt4_cost, gpt35_cost)


# Run unittest directly
print("Running unittest...")
loader = unittest.TestLoader()
suite = unittest.TestSuite()
for cls in [TestTokenCounter, TestValidateMessage, TestCalculateCost]:
    suite.addTests(loader.loadTestsFromTestCase(cls))

runner = unittest.TextTestRunner(verbosity=1)
result = runner.run(suite)
print(f"Tests run: {result.testsRun}, Failures: {len(result.failures)}, Errors: {len(result.errors)}")


# ══════════════════════════════════════════════════════════════════════════════
# PART B: pytest — MODERN FUNCTION-BASED (Industry Standard)
# ══════════════════════════════════════════════════════════════════════════════
"""
pytest ADVANTAGES over unittest:
  1. No class required — plain functions work
  2. assert statement — no assertEqual/assertTrue needed (pytest rewrites them)
  3. Better failure messages — shows exact values
  4. Fixtures — more powerful than setUp/tearDown
  5. Parametrize — run same test with many inputs
  6. Plugins — pytest-cov, pytest-asyncio, pytest-mock, etc.

PYTEST SYNTAX:
  def test_something():       # no class needed
      result = my_func()
      assert result == expected  # plain assert — pytest rewrites for better messages

  assert result == 42          → shows: assert 41 == 42 (actual vs expected)
  assert "hello" in text       → shows: assert 'hello' in 'goodbye'
  assert isinstance(x, str)   → shows: assert isinstance(42, str)

CONVENTIONS:
  File names:   test_*.py or *_test.py
  Function names: test_*
  Class names:  Test* (no inheritance needed)
"""

print("\n" + "=" * 60)
print("PART B: pytest-style tests (run with: pytest this_file.py -v)")
print("=" * 60)

# These functions work with both pytest runner and can be called manually


def test_token_counter_basic():
    """pytest: basic token counter test."""
    counter = TokenCounter("gpt-4", 1000)
    counter.add(300)
    assert counter.used == 300
    assert counter.remaining() == 700
    assert not counter.is_exceeded()


def test_token_counter_exceed():
    """pytest: exceeding limit."""
    counter = TokenCounter("gpt-4", 100)
    counter.add(101)
    assert counter.is_exceeded()


def test_validate_message_success():
    """pytest: valid message."""
    msg = validate_message("user", "Hello!")
    assert msg["role"] == "user"
    assert msg["content"] == "Hello!"


def test_validate_message_strips_whitespace():
    """pytest: content is stripped."""
    msg = validate_message("user", "  hello  ")
    assert msg["content"] == "hello"


def test_validate_message_invalid_role():
    """pytest: invalid role raises ValueError."""
    import pytest
    try:
        with pytest.raises(ValueError, match="Invalid role"):
            validate_message("admin", "test")
    except ImportError:
        # Fallback if pytest not installed
        try:
            validate_message("admin", "test")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Invalid role" in str(e)


def test_cost_calculation():
    """pytest: cost calculation."""
    cost = calculate_cost(1000, 500, "gpt-4")
    assert cost == pytest_approx(0.06, abs=1e-6)


def pytest_approx(expected, abs=1e-6):
    """Tiny approximation helper for non-pytest environments."""
    class _Approx:
        def __eq__(self, other):
            return abs(other - expected) <= abs
    return _Approx()


# Run pytest-style tests manually
print("Running pytest-style tests manually:")
tests = [
    test_token_counter_basic,
    test_token_counter_exceed,
    test_validate_message_success,
    test_validate_message_strips_whitespace,
    test_cost_calculation,
]
passed = failed = 0
for test_fn in tests:
    try:
        test_fn()
        print(f"  ✅ {test_fn.__name__}")
        passed += 1
    except Exception as e:
        print(f"  ❌ {test_fn.__name__}: {e}")
        failed += 1
print(f"pytest-style: {passed} passed, {failed} failed")


# ══════════════════════════════════════════════════════════════════════════════
# PART C: FIXTURES — SETUP/TEARDOWN (pytest style)
# ══════════════════════════════════════════════════════════════════════════════
"""
FIXTURES replace setUp/tearDown — more flexible, composable:

  @pytest.fixture
  def counter():
      """Setup"""
      c = TokenCounter("gpt-4", 1000)
      yield c          # ← test runs here
      # Teardown (optional, after yield)
      c.reset()

  def test_uses_fixture(counter):  # pytest injects it!
      counter.add(100)
      assert counter.remaining() == 900

FIXTURE SCOPES:
  @pytest.fixture(scope="function")  # default: new for EACH test
  @pytest.fixture(scope="class")     # shared within a test class
  @pytest.fixture(scope="module")    # shared within a test file
  @pytest.fixture(scope="session")   # shared for entire test run

CONFTEST.PY:
  Put shared fixtures in conftest.py — auto-discovered by pytest.
"""

print("\n" + "=" * 60)
print("PART C: Fixtures demonstration")
print("=" * 60)

# Simulating fixture behavior without pytest
class FixtureSimulator:
    """Demonstrates what pytest fixtures do internally."""

    @staticmethod
    def make_counter() -> TokenCounter:
        """Fixture: fresh counter for each test."""
        return TokenCounter("gpt-4", 1000)

    @staticmethod
    def make_llm_client() -> LLMClient:
        """Fixture: LLM client with mock API key."""
        return LLMClient(api_key="sk-test-key", model="gpt-4")


# How you'd write this in real pytest:
"""
# conftest.py
import pytest
from your_module import TokenCounter, LLMClient

@pytest.fixture
def counter():
    return TokenCounter("gpt-4", 1000)

@pytest.fixture
def llm_client():
    return LLMClient(api_key="sk-test-key")

# test_token.py
def test_add_tokens(counter):       # pytest injects counter fixture
    counter.add(300)
    assert counter.remaining() == 700

def test_client_model(llm_client):  # pytest injects llm_client fixture
    assert llm_client.model == "gpt-4"
"""

# Simulate
counter = FixtureSimulator.make_counter()
counter.add(300)
assert counter.remaining() == 700
print(f"  ✅ Fixture simulation: remaining={counter.remaining()}")


# ══════════════════════════════════════════════════════════════════════════════
# PART D: PARAMETRIZE — TEST MULTIPLE INPUTS
# ══════════════════════════════════════════════════════════════════════════════
"""
@pytest.mark.parametrize runs the same test with multiple input sets.
Instead of writing 5 separate tests, write ONE with 5 parameter sets.

  @pytest.mark.parametrize("role,expected", [
      ("user",      True),
      ("assistant", True),
      ("system",    True),
      ("admin",     False),
      ("",          False),
  ])
  def test_role_validation(role, expected):
      if expected:
          result = validate_message(role, "test")
          assert result["role"] == role
      else:
          with pytest.raises(ValueError):
              validate_message(role, "test")
"""

print("\n" + "=" * 60)
print("PART D: Parametrize demonstration")
print("=" * 60)


def run_parametrize_test():
    """Simulate parametrize behavior."""

    # Test data: (role, content, should_succeed, expected_error_msg)
    test_cases = [
        ("user",       "Hello",         True,  None),
        ("assistant",  "Hi there",      True,  None),
        ("system",     "Be helpful",    True,  None),
        ("tool",       "Tool result",   True,  None),
        ("admin",      "Admin msg",     False, "Invalid role"),
        ("USER",       "Case test",     False, "Invalid role"),  # case-sensitive
        ("user",       "",              False, "empty"),
        ("user",       "   ",           False, "empty"),
        ("user",       "x" * 10_001,   False, "too long"),
    ]

    passed = failed = 0
    for role, content, should_succeed, error_msg in test_cases:
        try:
            result = validate_message(role, content)
            if should_succeed:
                assert result["role"] == role
                print(f"  ✅ ({role!r}, {content[:20]!r}) → success")
                passed += 1
            else:
                print(f"  ❌ ({role!r}, ...) should have failed!")
                failed += 1
        except ValueError as e:
            if not should_succeed and (error_msg is None or error_msg in str(e)):
                print(f"  ✅ ({role!r}, ...) → correctly raised ValueError: {str(e)[:40]}")
                passed += 1
            else:
                print(f"  ❌ Unexpected error for ({role!r}, ...): {e}")
                failed += 1

    print(f"  Parametrize: {passed} passed, {failed} failed")


run_parametrize_test()


# Cost parametrize example
cost_test_cases = [
    (1000, 500,  "gpt-4",        0.06),
    (1000, 1000, "gpt-3.5-turbo", 0.003),
    (0,    0,    "gpt-4",        0.0),
    (2000, 1000, "claude-3-opus", 0.105),
]

print(f"\nCost calculation parametrize:")
for prompt, completion, model, expected in cost_test_cases:
    actual = calculate_cost(prompt, completion, model)
    passed = abs(actual - expected) < 1e-6
    icon = "✅" if passed else "❌"
    print(f"  {icon} model={model}, P={prompt}, C={completion} → ${actual:.4f} (expected ${expected})")


# ══════════════════════════════════════════════════════════════════════════════
# PART E: MOCKING — REPLACE REAL DEPENDENCIES
# ══════════════════════════════════════════════════════════════════════════════
"""
MOCKING: replace real objects (API calls, DB, file system) with FAKES.

WHY MOCK?
  - Unit tests should be FAST and ISOLATED
  - Don't want real OpenAI API calls in tests (costs money, slow, flaky)
  - Don't want real DB in unit tests
  - Test error handling (force API to fail)

unittest.mock tools:
  MagicMock()   → creates a mock that auto-creates attributes
  patch()       → temporarily replaces real object with mock
  AsyncMock()   → mock for async functions/methods
  Mock()        → simpler mock without magic methods

Key concepts:
  mock.return_value = x    → mock() returns x
  mock.side_effect = [a,b] → first call returns a, second returns b
  mock.side_effect = exc   → mock() raises exc
  mock.assert_called_once_with(args) → verify it was called correctly
  mock.call_count          → how many times called
"""

print("\n" + "=" * 60)
print("PART E: MOCKING")
print("=" * 60)


# Example 1: Mock LLM API call
def test_complete_with_mock():
    """Test LLM client without making real API calls."""
    client = LLMClient(api_key="fake-key", model="gpt-4")

    # Replace client.complete with a mock
    client.complete = MagicMock(return_value={
        "choices": [{"message": {"content": "Paris"}}],
        "usage": {"total_tokens": 15},
    })

    result = client.complete("What is the capital of France?")

    # Verify the response
    assert result["choices"][0]["message"]["content"] == "Paris"
    assert result["usage"]["total_tokens"] == 15

    # Verify the mock was called correctly
    client.complete.assert_called_once_with("What is the capital of France?")
    assert client.complete.call_count == 1
    print(f"  ✅ Mock basic: API called once with correct args")


# Example 2: Test retry logic with mock side_effect
def test_retry_on_connection_error():
    """Test that retry logic works — mock fails twice then succeeds."""
    client = LLMClient(api_key="fake-key", model="gpt-4")

    expected_response = {"choices": [{"message": {"content": "Success"}}]}

    # First 2 calls fail, 3rd succeeds
    client.complete = MagicMock(side_effect=[
        ConnectionError("timeout"),       # 1st call: fails
        ConnectionError("timeout"),       # 2nd call: fails
        expected_response,                # 3rd call: succeeds
    ])

    result = client.complete_with_retry("test prompt", max_retries=3)

    assert result == expected_response
    assert client.complete.call_count == 3  # called 3 times total
    print(f"  ✅ Retry mock: called {client.complete.call_count} times, finally succeeded")


# Example 3: Test that function raises on all retries exhausted
def test_retry_exhausted():
    """Test that ConnectionError propagates after all retries fail."""
    client = LLMClient(api_key="fake-key", model="gpt-4")

    client.complete = MagicMock(side_effect=ConnectionError("always fails"))

    try:
        client.complete_with_retry("test", max_retries=3)
        assert False, "Should have raised ConnectionError"
    except ConnectionError:
        assert client.complete.call_count == 3
        print(f"  ✅ Exhausted retries: raised after {client.complete.call_count} attempts")


# Example 4: patch() — replace module-level function
def test_patch_context_manager():
    """Use patch() to replace a function in the module it's used in."""

    with patch("time.sleep") as mock_sleep:
        # Now time.sleep() won't actually sleep — instant!
        client = LLMClient("fake-key")
        client.complete = MagicMock(side_effect=[ConnectionError(), {"result": "ok"}])
        result = client.complete_with_retry("test", max_retries=2)
        assert result == {"result": "ok"}

    print(f"  ✅ patch(time.sleep): test ran instantly, sleep was called {mock_sleep.call_count} time(s)")


# Example 5: MagicMock for complex objects
def test_magic_mock_auto_attributes():
    """MagicMock auto-creates any attribute you access."""
    mock = MagicMock()

    # Access any attribute — auto-created
    mock.model = "gpt-4"
    mock.complete.return_value = {"text": "hello"}
    mock.token_counter.used = 150

    result = mock.complete("test")
    assert result == {"text": "hello"}
    assert mock.model == "gpt-4"
    assert mock.token_counter.used == 150
    print(f"  ✅ MagicMock auto-attributes work")


test_complete_with_mock()
test_retry_on_connection_error()
test_retry_exhausted()
test_patch_context_manager()
test_magic_mock_auto_attributes()


# ══════════════════════════════════════════════════════════════════════════════
# PART F: TESTING ASYNC CODE
# ══════════════════════════════════════════════════════════════════════════════
"""
ASYNC TESTING:
  pytest-asyncio (install: pip install pytest-asyncio):
    @pytest.mark.asyncio
    async def test_async_func():
        result = await my_async_func()
        assert result == expected

  asyncio.run() in regular tests:
    def test_async_with_run():
        result = asyncio.run(my_async_func())
        assert result == expected

  AsyncMock:
    mock = AsyncMock(return_value={"result": "ok"})
    result = await mock("args")  # works like regular await
"""

print("\n" + "=" * 60)
print("PART F: ASYNC TESTING")
print("=" * 60)


async def _test_async_llm():
    """Test async LLM function with AsyncMock."""
    client = LLMClient("fake-key")

    # AsyncMock for async functions
    async_complete = AsyncMock(return_value={"choices": [{"message": {"content": "ok"}}]})
    client.complete = async_complete

    prompts = ["Q1", "Q2", "Q3"]
    results = await asyncio.gather(*[asyncio.to_thread(client.complete, p) for p in prompts])

    assert len(results) == 3
    return results


async def _test_async_timeout():
    """Test that async operations respect timeouts."""

    async def slow_operation():
        await asyncio.sleep(0.5)
        return "done"

    # Should timeout
    try:
        await asyncio.wait_for(slow_operation(), timeout=0.1)
        assert False, "Should have timed out"
    except asyncio.TimeoutError:
        return True


async def run_async_tests():
    print("  Running async tests...")
    results = await _test_async_llm()
    print(f"  ✅ async gather: {len(results)} results")

    timed_out = await _test_async_timeout()
    print(f"  ✅ async timeout: correctly raised TimeoutError = {timed_out}")


asyncio.run(run_async_tests())


# ══════════════════════════════════════════════════════════════════════════════
# PART G: TEST ORGANIZATION & BEST PRACTICES
# ══════════════════════════════════════════════════════════════════════════════
"""
TEST STRUCTURE: AAA Pattern (Arrange, Act, Assert)
  def test_something():
      # Arrange: set up test data
      counter = TokenCounter("gpt-4", 1000)

      # Act: call the code under test
      counter.add(300)

      # Assert: verify the result
      assert counter.remaining() == 700

NAMING CONVENTIONS:
  test_<what>_<condition>_<expected>
  test_add_negative_raises_valueerror()
  test_validate_empty_content_raises()
  test_calculate_cost_unknown_model_raises()

GOOD TESTS:
  ✅ Fast (no real I/O, no sleep)
  ✅ Independent (no shared state between tests)
  ✅ Repeatable (same result every run)
  ✅ Single concept per test (one assertion ideally)
  ✅ Clear name (describes what and why)

COVERAGE TYPES:
  Line coverage: % of lines executed
  Branch coverage: % of if/else branches taken
  Target: 80%+ for production code

COVERAGE COMMAND:
  pip install pytest-cov
  pytest --cov=mymodule --cov-report=html
  open htmlcov/index.html
"""

print("\n" + "=" * 60)
print("PART G: TEST ORGANIZATION")
print("=" * 60)


# Demonstrate proper test class organization
class TestTokenCounterComplete(unittest.TestCase):
    """
    Complete test suite showing AAA pattern and proper organization.
    """

    # ── Fixtures ──
    def setUp(self):
        self.counter = TokenCounter(model="gpt-4", limit=1000)

    # ── Happy path tests ──
    def test_add_tokens_updates_used(self):
        # Arrange
        initial_used = self.counter.used  # 0

        # Act
        self.counter.add(300)

        # Assert
        self.assertEqual(self.counter.used, initial_used + 300)

    def test_remaining_decreases_after_add(self):
        self.counter.add(400)
        self.assertEqual(self.counter.remaining(), 600)

    def test_reset_clears_usage(self):
        self.counter.add(500)
        self.counter.reset()
        self.assertEqual(self.counter.used, 0)
        self.assertEqual(self.counter.remaining(), self.counter.limit)

    # ── Boundary tests ──
    def test_exactly_at_limit_not_exceeded(self):
        self.counter.add(1000)
        self.assertFalse(self.counter.is_exceeded())

    def test_one_over_limit_is_exceeded(self):
        self.counter.add(1001)
        self.assertTrue(self.counter.is_exceeded())

    # ── Error tests ──
    def test_negative_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.counter.add(-1)

    def test_negative_raises_with_message(self):
        with self.assertRaises(ValueError) as ctx:
            self.counter.add(-50)
        self.assertIn("0", str(ctx.exception))  # error mentions 0 threshold


runner = unittest.TextTestRunner(verbosity=1)
runner.run(unittest.TestLoader().loadTestsFromTestCase(TestTokenCounterComplete))


# ══════════════════════════════════════════════════════════════════════════════
# PART H: PRODUCTION AI AGENT TESTING PATTERNS
# ══════════════════════════════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("PART H: AI AGENT TESTING PATTERNS")
print("=" * 60)


# Pattern 1: Test with fake LLM that returns predictable responses
class FakeLLMClient:
    """Test double — predictable, fast, no API calls."""

    def __init__(self, responses: list[str]):
        self._responses = iter(responses)
        self.calls: list[str] = []

    def complete(self, prompt: str) -> dict:
        self.calls.append(prompt)
        try:
            content = next(self._responses)
        except StopIteration:
            content = "Default response"
        return {
            "choices": [{"message": {"content": content}}],
            "usage": {"total_tokens": len(prompt.split()) * 2},
        }


def test_agent_with_fake_llm():
    """Test agent logic using a fake LLM — no API calls."""
    fake_llm = FakeLLMClient(responses=[
        "The capital of France is Paris.",
        "Python was created in 1991.",
    ])

    # Simulate agent behavior
    q1 = fake_llm.complete("What is the capital of France?")
    q2 = fake_llm.complete("When was Python created?")

    assert "Paris" in q1["choices"][0]["message"]["content"]
    assert "1991" in q2["choices"][0]["message"]["content"]
    assert len(fake_llm.calls) == 2
    print(f"  ✅ FakeLLM test: {len(fake_llm.calls)} calls, responses correct")


# Pattern 2: Contract testing — verify output format matches expected schema
def validate_llm_response_schema(response: dict) -> bool:
    """Check LLM response has all required fields."""
    required_keys = {"choices", "usage"}
    if not all(k in response for k in required_keys):
        return False
    if not response["choices"]:
        return False
    if "message" not in response["choices"][0]:
        return False
    if "content" not in response["choices"][0]["message"]:
        return False
    return True


def test_response_schema_validation():
    """Test that responses match expected schema."""
    fake_llm = FakeLLMClient(["Hello world"])
    response = fake_llm.complete("test")

    assert validate_llm_response_schema(response)
    print(f"  ✅ Schema validation: response structure is correct")


# Pattern 3: Test token budget enforcement
def test_token_budget_enforcement():
    """Test that agent respects token budget."""
    budget = TokenCounter("gpt-4", limit=100)

    # Simulate 3 calls each using 40 tokens
    for i in range(2):
        budget.add(40)

    # 3rd call would exceed — agent should refuse
    would_exceed = (budget.used + 40) > budget.limit
    assert would_exceed, "Budget should detect it would be exceeded"
    assert budget.remaining() == 20
    print(f"  ✅ Token budget: correctly detects overage, remaining={budget.remaining()}")


test_agent_with_fake_llm()
test_response_schema_validation()
test_token_budget_enforcement()


# ══════════════════════════════════════════════════════════════════════════════
# PART I: INTERVIEW Q&A
# ══════════════════════════════════════════════════════════════════════════════
"""
Q1: What is the difference between unittest and pytest?
A:  unittest: built-in, class-based (TestCase), Java-style assertions (assertEqual)
              verbose, but no extra install needed
    pytest:   third-party (pip install pytest), function-based, plain assert
              better messages, fixtures, parametrize, plugins
              Industry standard — most companies use pytest

Q2: What is mocking and when do you use it?
A:  Mocking replaces real dependencies with fake objects for tests.
    Use when:
    - Function calls external API (LLM, database, file system)
    - Real call is slow, expensive, or non-deterministic
    - Testing error handling (force the mock to raise an exception)
    Tools: unittest.mock.MagicMock, patch(), AsyncMock

Q3: What is the difference between a Mock and a Fake?
A:  Mock: auto-generated, verifiable (assert_called_once_with, call_count)
           doesn't actually do anything — just records calls
    Fake: real working implementation, simpler than production version
          (e.g., in-memory DB instead of real DB, FakeLLMClient with canned responses)
    Stub: returns preset values, no behavior verification

Q4: What is pytest fixture scope?
A:  Scope controls how often the fixture is created:
    function (default): new for each test — guaranteed isolation
    class:  shared across methods in a class
    module: shared across the whole test file
    session: shared across entire test run (expensive setup done once)
    Use session scope for: DB connections, model loading, external service setup

Q5: How do you test a function that calls time.sleep()?
A:  Use patch() to mock time.sleep — tests run instantly, no actual waiting.

    with patch("time.sleep") as mock_sleep:
        my_function_that_sleeps()
        mock_sleep.assert_called_once_with(5)  # verify it tried to sleep 5s

Q6: What is code coverage and what is a good target?
A:  Coverage = % of your code that is executed during tests.
    Line coverage: lines executed
    Branch coverage: if/else branches taken
    Good target: 80%+ for production code
    100% is ideal but often impractical (some error paths hard to test)
    Use: pytest --cov=mymodule --cov-report=html

Q7: What is TDD (Test-Driven Development)?
A:  Write the TEST before writing the CODE:
    1. Write failing test (RED)
    2. Write minimal code to pass it (GREEN)
    3. Refactor while keeping tests green (REFACTOR)
    Benefits: guarantees testability, better design, no forgotten tests.
"""

print("\n✅ Day41 — unittest + pytest COMPLETE")
print("Topics: unittest, pytest, fixtures, parametrize, mocking, async testing, AI patterns")
print("\nRun with: python -m pytest Day41_Testing/01_unittest_pytest.py -v")
