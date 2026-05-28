# TDD / BDD Practices

> **Interview angle:** "Aap TDD follow karte ho? Practical implementation kaise?"

---

## 1. TDD — Test-Driven Development

**Cycle: RED → GREEN → REFACTOR**

1. **RED:** Write failing test for desired behavior
2. **GREEN:** Write minimum code to pass
3. **REFACTOR:** Clean up code while keeping tests green

```python
# 1. RED — write failing test
def test_calculate_discount():
    assert calculate_discount(100, "PROMO10") == 10

# Run: fails (function doesn't exist)

# 2. GREEN — minimal code
def calculate_discount(price, code):
    return 10

# Run: passes ✅

# 3. REFACTOR — more cases, generalize
def test_discount_no_code():
    assert calculate_discount(100, "") == 0

def calculate_discount(price, code):
    if code == "PROMO10":
        return price * 0.10
    return 0
```

---

## 2. Why TDD?

✅ **Pros:**
- Tests written by definition
- Forces small, testable units
- Catches bugs early
- Documentation via tests
- Refactoring safety net

❌ **Cons:**
- Slower upfront
- Hard for exploratory code
- Discipline required
- Hard with complex external dependencies

**Reality:** Most teams don't strict TDD, but write tests before merging.

---

## 3. TDD Anti-Patterns

### Anti-pattern 1: Test the implementation, not behavior
```python
# ❌ BAD — couples test to internals
def test_calculate_uses_specific_method():
    calc = Calculator()
    spy = mocker.spy(calc, "_internal_method")
    calc.add(1, 2)
    assert spy.called

# ✅ GOOD — tests behavior
def test_calculator_adds_numbers():
    assert Calculator().add(1, 2) == 3
```

### Anti-pattern 2: Excessive mocking
Mock all dependencies → test tells you nothing real.

### Anti-pattern 3: "Test for the sake of test"
```python
# Useless
def test_init():
    obj = MyClass()
    assert obj is not None
```

### Anti-pattern 4: Brittle tests
Test breaks on every refactor → developers disable them.

---

## 4. BDD — Behavior-Driven Development

BDD = TDD + business-readable specifications.

### Gherkin syntax
```gherkin
Feature: User Login

  Scenario: Successful login with valid credentials
    Given a user with email "alice@example.com" exists
    When they submit login form with password "Test@123"
    Then they receive an auth token
    And they are redirected to dashboard

  Scenario: Failed login with wrong password
    Given a user with email "alice@example.com" exists
    When they submit login form with password "wrong"
    Then they see error "Invalid credentials"
```

### Python: `pytest-bdd`
```bash
pip install pytest-bdd
```

```python
# test_login.py
from pytest_bdd import scenarios, given, when, then, parsers

scenarios("features/login.feature")

@given(parsers.parse('a user with email "{email}" exists'))
def existing_user(email, db):
    db.create_user(email=email, password_hash=hash_pw("Test@123"))
    return email

@when(parsers.parse('they submit login form with password "{password}"'))
def submit_login(client, email, password):
    return client.post("/login", json={"email": email, "password": password})

@then("they receive an auth token")
def check_token(response):
    assert "access_token" in response.json()
```

---

## 5. BDD Tools

| Tool | Language | Notes |
|---|---|---|
| **pytest-bdd** | Python | pytest-integrated |
| **behave** | Python | Standalone |
| **Cucumber** | Multi | Industry standard |
| **Robot Framework** | Python | Keyword-driven |

---

## 6. When TDD/BDD Works Best

### TDD shines for
- Pure logic (calculations, parsing, transformations)
- Algorithms
- Library code
- Refactoring (existing tests = safety)

### BDD shines for
- User-facing features
- Cross-team communication (PM/QA/dev)
- Regulatory compliance (auditable specs)
- Integration tests / E2E

### Doesn't fit well
- Exploratory UI work
- Spike/PoC code
- Glue/configuration code

---

## 7. Practical TDD Example

```python
# Goal: implement Rate Limiter

# RED — write test FIRST
def test_rate_limit_allows_under_threshold():
    rl = RateLimit(max_per_minute=5)
    for _ in range(5):
        assert rl.allow("user_1") is True

def test_rate_limit_blocks_over_threshold():
    rl = RateLimit(max_per_minute=5)
    for _ in range(5):
        rl.allow("user_1")
    assert rl.allow("user_1") is False

# Tests FAIL (no implementation)

# GREEN — minimal
class RateLimit:
    def __init__(self, max_per_minute):
        self.max = max_per_minute
        self.counts = {}

    def allow(self, key):
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key] <= self.max

# Tests PASS ✅

# REFACTOR — add window logic
def test_rate_limit_resets_after_window():
    rl = RateLimit(max_per_minute=5, window_seconds=60)
    for _ in range(5):
        rl.allow("user_1")
    assert rl.allow("user_1") is False

    # Mock time
    time.sleep(61)
    assert rl.allow("user_1") is True

# Update implementation accordingly
```

---

## 8. TDD Patterns

### Pattern: "Triangulation"
Multiple tests force generalization.
```python
def test_1plus1():    assert add(1, 1) == 2
def test_2plus2():    assert add(2, 2) == 4
# Can't `return 2` anymore — must implement real logic
```

### Pattern: "Fake it till you make it"
```python
# RED
def test_factorial_3():
    assert factorial(3) == 6

# GREEN — just return 6 first
def factorial(n):
    return 6

# Add more tests
def test_factorial_4():    assert factorial(4) == 24

# Now must implement properly
def factorial(n):
    if n <= 1: return 1
    return n * factorial(n - 1)
```

### Pattern: "Test list"
Before coding, write list of test cases:
```
- factorial(0) = 1
- factorial(1) = 1
- factorial(5) = 120
- factorial(-1) raises ValueError
- factorial(very large) - performance
```

---

## 9. Outside-In vs Inside-Out TDD

### Outside-in (London school)
Start with high-level test (UI/API), mock dependencies, drill down.
- Useful for: features, user stories
- Faster feature delivery
- More mocks

### Inside-out (Detroit school)
Start with smallest unit, build up.
- Useful for: algorithms, libraries
- Real implementations (less mocking)
- Bottom-up

**Hybrid in practice.**

---

## 10. BDD Three Amigos

**Roles in writing scenarios:**
- **PM/Business:** what's the requirement?
- **Developer:** can we implement?
- **QA/Tester:** what edge cases?

All three review feature files BEFORE coding.

---

## 11. Living Documentation

BDD feature files = always-current docs.

```bash
# Generate HTML report from features
behave --format html --outfile docs.html

# Allure reports
pytest --alluredir=reports
allure serve reports
```

---

## 12. Sample Feature File (Complete)

```gherkin
# features/checkout.feature
Feature: Checkout Process
  As a customer
  I want to complete checkout
  So that I can purchase items

  Background:
    Given a logged-in user "alice@example.com"

  Scenario: Successful checkout with sufficient stock
    Given product "iPhone" with stock 10 and price 1000
    When user adds 1 of "iPhone" to cart
    And user proceeds to checkout
    And user enters valid payment "card-1234"
    Then order is created with total 1000
    And stock of "iPhone" is reduced to 9
    And user receives confirmation email

  Scenario: Checkout fails when stock insufficient
    Given product "iPhone" with stock 0
    When user adds 1 of "iPhone" to cart
    And user proceeds to checkout
    Then user sees error "Out of stock"
    And no order is created

  Scenario Outline: Discount codes
    Given product "Book" with price <price>
    When user applies code "<code>"
    Then total becomes <expected>

    Examples:
      | price | code     | expected |
      | 100   | PROMO10  | 90       |
      | 100   | PROMO20  | 80       |
      | 100   | INVALID  | 100      |
```

---

## 13. Step Definitions

```python
# tests/steps/test_checkout.py
from pytest_bdd import scenarios, given, when, then, parsers

scenarios("../features/checkout.feature")


@given(parsers.parse('a logged-in user "{email}"'))
def logged_in_user(email, client):
    client.post("/login", json={"email": email, "password": "test"})
    return email


@given(parsers.parse('product "{name}" with stock {stock:d} and price {price:d}'))
def product(name, stock, price, db):
    return db.create_product(name=name, stock=stock, price=price)


@when(parsers.parse('user adds {qty:d} of "{name}" to cart'))
def add_to_cart(qty, name, client, product):
    client.post("/cart/add", json={"product_id": product.id, "quantity": qty})


@when("user proceeds to checkout")
def proceed_to_checkout(client):
    pytest.checkout_response = client.post("/checkout")


@then(parsers.parse('order is created with total {total:d}'))
def order_created(total, db):
    order = db.last_order()
    assert order.total == total


@then(parsers.parse('stock of "{name}" is reduced to {stock:d}'))
def stock_reduced(name, stock, db):
    assert db.get_product(name).stock == stock
```

---

## 14. CI Integration

```yaml
test:
  steps:
    - run: pytest tests/        # unit + integration
    - run: pytest tests/bdd/     # BDD scenarios
    - run: |
        # Generate report
        pytest tests/bdd/ \\
          --cucumberjson=reports/cucumber.json \\
          --cucumberxml=reports/cucumber.xml

    - uses: actions/upload-artifact@v4
      with:
        name: bdd-report
        path: reports/
```

---

## 15. Common Pitfalls

### Pitfall 1: Treating BDD as documentation, not tests
Scenarios written by PM, never run by devs. Tests rot.

### Pitfall 2: Translating dev jargon to Gherkin
"When the system receives an HTTP POST..." — too technical. Use business language.

### Pitfall 3: Too many steps
50-step scenarios = brittle, slow. Break into smaller scenarios.

### Pitfall 4: Imperative Gherkin
```gherkin
# ❌ BAD
When I click button with id "submit-btn"
And I wait 2 seconds
And I check the URL contains "success"

# ✅ GOOD
When I submit the form
Then I am taken to the success page
```

### Pitfall 5: TDD without thinking design
Just writing tests doesn't guarantee good design. Think before testing.

---

## 16. Interview Questions

**Q1: TDD cycle?**
RED (failing test) → GREEN (minimal code) → REFACTOR.

**Q2: TDD always useful?**
No. Best for pure logic + libraries. Hard for exploratory UI, complex external systems.

**Q3: BDD vs TDD?**
TDD = developer-facing tests. BDD = business-readable scenarios bridging PM/dev/QA.

**Q4: pytest-bdd vs behave?**
pytest-bdd = leverages pytest fixtures (recommended). behave = standalone but isolated.

**Q5: Outside-in TDD?**
Start with high-level test (API), mock collaborators, drill down. Useful for features.

**Q6: TDD anti-patterns?**
Testing implementation (not behavior), excessive mocking, brittle tests, useless tests.

**Q7: When to skip TDD?**
Spike/PoC, exploratory UI, throwaway scripts. Add tests if code becomes permanent.

---

## 17. Best Practices

1. **TDD for new logic** — write test first
2. **Test behavior, not implementation**
3. **Small, focused tests** — one assertion per test ideal
4. **Refactor under green** — never refactor with failing tests
5. **BDD for cross-team features** — bridges roles
6. **Gherkin in business language** — not dev jargon
7. **Run BDD in CI** — keep specs alive
8. **Mock external systems only** — not your own code
9. **Test list before coding** — plan first
10. **TDD as habit, not religion** — pragmatic

---

## Related
- [[01_pytest_advanced]]
- [[03_mutation_testing]]
- [[08_fastapi_testing_patterns]]
