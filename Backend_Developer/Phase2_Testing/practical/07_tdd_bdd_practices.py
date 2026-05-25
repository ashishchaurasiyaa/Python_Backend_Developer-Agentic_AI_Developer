"""
============================================================
TDD / BDD PRACTICES — Practical
============================================================
Install:
    pip install pytest pytest-bdd

Demonstrates:
1. TDD cycle (RED→GREEN→REFACTOR) with rate limiter
2. BDD with pytest-bdd
3. Outside-in vs inside-out
4. Anti-patterns
"""
import pytest


# ============================================================
# 1. TDD EXAMPLE: Build Rate Limiter step by step
# ============================================================

# ---- STEP 1: RED (failing test) ----
def test_rate_limit_initial_requests_allowed_TDD():
    rl = RateLimiter(max_requests=5, window_seconds=60)
    for _ in range(5):
        assert rl.allow("user_1") is True


# Implementation (start minimal — GREEN)
class RateLimiter:
    def __init__(self, max_requests=5, window_seconds=60):
        self.max = max_requests
        self.window = window_seconds
        self.counts = {}

    def allow(self, key):
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key] <= self.max


# ---- STEP 2: Add more tests, drive design ----
def test_rate_limit_blocks_over_threshold():
    rl = RateLimiter(max_requests=5)
    for _ in range(5):
        rl.allow("user_1")
    assert rl.allow("user_1") is False


def test_rate_limit_separate_per_user():
    rl = RateLimiter(max_requests=2)
    rl.allow("user_1")
    rl.allow("user_1")
    assert rl.allow("user_1") is False
    # Different user not affected
    assert rl.allow("user_2") is True


# ---- STEP 3: REFACTOR for window logic ----
import time


class WindowedRateLimiter:
    def __init__(self, max_requests=5, window_seconds=60):
        self.max = max_requests
        self.window = window_seconds
        self.records = {}    # key -> list of timestamps

    def allow(self, key):
        now = time.monotonic()
        cutoff = now - self.window
        # Drop expired timestamps
        ts = self.records.get(key, [])
        ts = [t for t in ts if t > cutoff]
        if len(ts) >= self.max:
            self.records[key] = ts
            return False
        ts.append(now)
        self.records[key] = ts
        return True


def test_rate_limit_resets_after_window(monkeypatch):
    # Use small window for fast test
    rl = WindowedRateLimiter(max_requests=2, window_seconds=0.1)
    rl.allow("u1")
    rl.allow("u1")
    assert rl.allow("u1") is False
    time.sleep(0.15)
    assert rl.allow("u1") is True   # window reset


# ============================================================
# 2. BDD WITH PYTEST-BDD
# ============================================================
FEATURE_FILE = '''
# features/discount.feature

Feature: Discount Application
  As a customer
  I want to apply discount codes
  So that I save money

  Background:
    Given a shopping cart with total 100

  Scenario: Apply valid 10% discount
    When I apply code "PROMO10"
    Then total becomes 90

  Scenario: Apply 20% discount
    When I apply code "PROMO20"
    Then total becomes 80

  Scenario: Invalid code does nothing
    When I apply code "INVALID"
    Then total becomes 100

  Scenario Outline: Discount table
    When I apply code "<code>"
    Then total becomes <total>

    Examples:
      | code     | total |
      | PROMO10  | 90    |
      | PROMO20  | 80    |
      | INVALID  | 100   |
      | VIP30    | 70    |
'''


PYTEST_BDD_TEST = '''
# tests/test_discount_bdd.py

from pytest_bdd import scenarios, given, when, then, parsers
import pytest

scenarios("features/discount.feature")


class Cart:
    def __init__(self, total):
        self.total = total

    def apply_discount(self, code):
        discounts = {"PROMO10": 0.1, "PROMO20": 0.2, "VIP30": 0.3}
        rate = discounts.get(code, 0)
        self.total = int(self.total * (1 - rate))


@pytest.fixture
def context():
    """Shared state across BDD steps."""
    return {}


@given(parsers.parse("a shopping cart with total {total:d}"), target_fixture="cart")
def cart_with_total(total):
    return Cart(total=total)


@when(parsers.parse('I apply code "{code}"'))
def apply_code(cart, code):
    cart.apply_discount(code)


@then(parsers.parse("total becomes {expected:d}"))
def check_total(cart, expected):
    assert cart.total == expected
'''


# ============================================================
# 3. OUTSIDE-IN TDD (London school)
# ============================================================
OUTSIDE_IN_EXAMPLE = '''
# Start with high-level test (API), mock dependencies, drill down

# Test 1: API endpoint behavior
def test_signup_endpoint_creates_user(client, mocker):
    # Mock all dependencies
    mock_user_service = mocker.patch("myapp.routes.user_service")
    mock_user_service.create.return_value = {"id": 1, "email": "a@x.com"}

    response = client.post("/signup", json={"email": "a@x.com", "password": "test"})

    assert response.status_code == 201
    assert response.json() == {"id": 1, "email": "a@x.com"}
    mock_user_service.create.assert_called_once_with(email="a@x.com", password="test")


# Test 2: Now drill into UserService
def test_user_service_creates_with_hashed_password(mocker):
    mock_repo = mocker.MagicMock()
    mock_repo.save.return_value = User(id=1)
    service = UserService(repo=mock_repo)

    service.create(email="a@x.com", password="test")

    saved_user = mock_repo.save.call_args[0][0]
    assert saved_user.email == "a@x.com"
    assert saved_user.password_hash != "test"    # hashed!


# Test 3: Drill into UserRepo
def test_user_repo_saves_to_db(db):
    repo = UserRepo(db=db)
    user = User(email="a@x.com")
    saved = repo.save(user)
    assert saved.id is not None
    assert db.query(User).filter_by(email="a@x.com").first() is not None
'''


# ============================================================
# 4. INSIDE-OUT TDD (Detroit school)
# ============================================================
INSIDE_OUT_EXAMPLE = '''
# Start with smallest unit, build up

# Test 1: Password hasher (smallest unit)
def test_password_hasher():
    hasher = PasswordHasher()
    h1 = hasher.hash("test")
    assert hasher.verify("test", h1) is True
    assert hasher.verify("wrong", h1) is False


# Test 2: User model
def test_user_model_creation():
    u = User(email="a@x.com")
    assert u.email == "a@x.com"


# Test 3: Repo (uses User + DB)
def test_user_repo_save(db):
    repo = UserRepo(db)
    user = User(email="a@x.com")
    saved = repo.save(user)
    assert saved.id is not None


# Test 4: Service (uses Repo + Hasher)
def test_user_service_create_user():
    repo = InMemoryUserRepo()
    hasher = PasswordHasher()
    service = UserService(repo, hasher)
    user = service.create(email="a@x.com", password="test")
    assert user.email == "a@x.com"
    assert hasher.verify("test", user.password_hash)


# Test 5: Endpoint (uses Service)
def test_signup_endpoint(client):
    response = client.post("/signup", json={"email": "a@x.com", "password": "test"})
    assert response.status_code == 201
'''


# ============================================================
# 5. ANTI-PATTERN: Testing implementation
# ============================================================
BAD_TEST_EXAMPLES = '''
# ❌ BAD — testing internal method calls
def test_calculator_uses_specific_method():
    calc = Calculator()
    spy = mocker.spy(calc, "_internal_add_logic")
    calc.add(1, 2)
    assert spy.called
# When you refactor _internal_add_logic away, test breaks but code is fine

# ❌ BAD — testing property setters
def test_user_email_setter():
    u = User()
    u.email = "test"
    assert u.email == "test"
# This tests Python, not your code

# ❌ BAD — useless init test
def test_user_init():
    u = User()
    assert u is not None    # always passes
'''

GOOD_TEST_EXAMPLES = '''
# ✅ GOOD — testing behavior
def test_calculator_adds_numbers():
    assert Calculator().add(1, 2) == 3

def test_calculator_handles_negative():
    assert Calculator().add(-1, -1) == -2

# ✅ GOOD — testing constraint
def test_user_email_validated():
    with pytest.raises(ValueError):
        User(email="invalid")
'''


# ============================================================
# 6. TEST LIST BEFORE CODING
# ============================================================
TEST_LIST_EXAMPLE = """
# Before implementing 'factorial', write test list:

# - factorial(0) = 1            (base case)
# - factorial(1) = 1            (base case)
# - factorial(5) = 120          (typical)
# - factorial(10) = 3628800     (larger)
# - factorial(-1) raises        (invalid input)
# - factorial("a") raises       (type error)
# - factorial(1000) — recursion limit?

# Then write tests for each, drive implementation

def test_factorial_zero():    assert factorial(0) == 1
def test_factorial_one():     assert factorial(1) == 1
def test_factorial_five():    assert factorial(5) == 120
def test_factorial_negative():
    with pytest.raises(ValueError):
        factorial(-1)
def test_factorial_string():
    with pytest.raises(TypeError):
        factorial("a")
"""


# ============================================================
# 7. PROPERTY-BASED TESTING (Hypothesis)
# ============================================================
HYPOTHESIS_EXAMPLE = '''
# Beyond TDD examples: property-based testing
from hypothesis import given, strategies as st


# Instead of specific cases, define invariants
@given(price=st.integers(min_value=0, max_value=10000))
def test_discount_never_negative(price):
    """Discount should never make total negative."""
    result = apply_discount(price, "PROMO10")
    assert result >= 0


@given(
    a=st.integers(min_value=-1000, max_value=1000),
    b=st.integers(min_value=-1000, max_value=1000),
)
def test_addition_commutative(a, b):
    """a + b == b + a (mathematical property)."""
    assert add(a, b) == add(b, a)


@given(text=st.text())
def test_serialize_roundtrip(text):
    """Serialize then deserialize gets back the same string."""
    assert deserialize(serialize(text)) == text

# Hypothesis tries hundreds of inputs, including edge cases
# Faster than enumerating cases manually
'''


# ============================================================
# 8. FIXTURE-DRIVEN TDD
# ============================================================
FIXTURE_DRIVEN = '''
@pytest.fixture
def empty_cart():
    return Cart()

@pytest.fixture
def cart_with_items(empty_cart):
    empty_cart.add("apple", price=10)
    empty_cart.add("banana", price=5)
    return empty_cart


# Tests use specific scenarios
def test_empty_cart_total(empty_cart):
    assert empty_cart.total == 0

def test_cart_total_with_items(cart_with_items):
    assert cart_with_items.total == 15

def test_apply_discount(cart_with_items):
    cart_with_items.apply_discount("PROMO10")
    assert cart_with_items.total == 13   # 15 - 10% = 13.5 → 13
'''


# ============================================================
# 9. BDD COMPLETE EXAMPLE
# ============================================================
COMPLETE_BDD = '''
# features/order.feature

Feature: Order Processing

  Background:
    Given a user "alice@example.com" with balance 1000

  Scenario: Successful order
    Given product "Book" with stock 5 and price 200
    When user "alice@example.com" orders 2 of "Book"
    Then order is created with total 400
    And user balance is 600
    And "Book" stock is 3

  Scenario: Insufficient balance
    Given product "Laptop" with stock 1 and price 2000
    When user "alice@example.com" orders 1 of "Laptop"
    Then order fails with error "Insufficient balance"
    And user balance is 1000
    And "Laptop" stock is 1

  Scenario: Out of stock
    Given product "Phone" with stock 0
    When user "alice@example.com" orders 1 of "Phone"
    Then order fails with error "Out of stock"


# tests/test_order_bdd.py
from pytest_bdd import scenarios, given, when, then, parsers

scenarios("features/order.feature")

state = {}

@given(parsers.parse('a user "{email}" with balance {balance:d}'))
def setup_user(email, balance, db):
    db.create_user(email=email, balance=balance)
    state["email"] = email

@given(parsers.parse('product "{name}" with stock {stock:d} and price {price:d}'))
def setup_product(name, stock, price, db):
    db.create_product(name=name, stock=stock, price=price)

@when(parsers.parse('user "{email}" orders {qty:d} of "{name}"'))
def place_order(email, qty, name, client):
    state["response"] = client.post("/orders",
                                     json={"product": name, "quantity": qty},
                                     headers={"X-User-Email": email})

@then(parsers.parse("order is created with total {total:d}"))
def check_order(total, db):
    assert state["response"].status_code == 201
    order = db.last_order()
    assert order.total == total

@then(parsers.parse('order fails with error "{error}"'))
def check_failure(error):
    assert state["response"].status_code in (400, 409)
    assert state["response"].json()["error"] == error

@then(parsers.parse("user balance is {balance:d}"))
def check_balance(balance, db):
    assert db.get_user(state["email"]).balance == balance

@then(parsers.parse('"{name}" stock is {stock:d}'))
def check_stock(name, stock, db):
    assert db.get_product(name).stock == stock
'''


# ============================================================
# 10. CI INTEGRATION
# ============================================================
CI_CONFIG = """
# .github/workflows/test.yml

jobs:
  unit-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install -e ".[test]"

      # TDD tests
      - run: pytest tests/unit/

      # BDD tests
      - run: pytest tests/bdd/ -v

      # Generate BDD report
      - run: |
          pytest tests/bdd/ \\
            --cucumberjson=reports/cucumber.json
          # Or with allure
          pytest --alluredir=allure-results

      - uses: actions/upload-artifact@v4
        with:
          name: bdd-report
          path: reports/
"""


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("TDD / BDD PRACTICES")
    print("=" * 60)

    # Run TDD examples
    print("\n--- TDD Example: Rate Limiter ---")
    rl = RateLimiter(max_requests=5)
    for i in range(7):
        ok = rl.allow("user_1")
        print(f"  Request {i+1}: {'✅' if ok else '❌ BLOCKED'}")

    print("\n--- FEATURE FILE ---")
    print(FEATURE_FILE)
    print("\n--- PYTEST-BDD ---")
    print(PYTEST_BDD_TEST)
    print("\n--- OUTSIDE-IN TDD ---")
    print(OUTSIDE_IN_EXAMPLE)
    print("\n--- INSIDE-OUT TDD ---")
    print(INSIDE_OUT_EXAMPLE)
    print("\n--- BAD TEST EXAMPLES ---")
    print(BAD_TEST_EXAMPLES)
    print("\n--- GOOD TEST EXAMPLES ---")
    print(GOOD_TEST_EXAMPLES)
    print("\n--- TEST LIST APPROACH ---")
    print(TEST_LIST_EXAMPLE)
    print("\n--- PROPERTY-BASED ---")
    print(HYPOTHESIS_EXAMPLE)
    print("\n--- FIXTURE-DRIVEN ---")
    print(FIXTURE_DRIVEN)
    print("\n--- COMPLETE BDD EXAMPLE ---")
    print(COMPLETE_BDD)
    print("\n--- CI INTEGRATION ---")
    print(CI_CONFIG)
