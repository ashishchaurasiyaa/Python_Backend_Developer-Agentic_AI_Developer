# Testing — Property-Based Testing with Hypothesis
**Phase 2 Testing | Senior Backend + Agentic AI**

## Quick Concepts
- **Property-based testing (PBT)** = describe properties code should satisfy → framework generates random inputs to find counterexamples
- **Example-based testing** = you pick inputs; PBT generates them
- **Hypothesis** = Python's gold-standard PBT library
- **Strategies** = recipes for generating inputs (`integers()`, `text()`, `lists()`, `composite()`)
- **Shrinking** = when failure found, Hypothesis shrinks input to minimal reproducer
- **Stateful testing** = generates sequences of operations to find state-machine bugs
- **Database** = Hypothesis remembers past failures to retry

---

## Why Property-Based?

```
EXAMPLE-BASED TEST:                    PROPERTY-BASED TEST:
─────────────────                      ────────────────────
def test_sort():                       @given(lists(integers()))
    assert sort([3,1,2]) == [1,2,3]   def test_sort_idempotent(lst):
                                           assert sort(sort(lst)) == sort(lst)

Tests ONE case.                        Tests 100s of generated lists.
Misses edge cases:                     Finds:
- empty list                           - empty list ✓
- duplicates                           - [INT_MAX, INT_MIN] ✓
- single item                          - duplicates ✓
- already sorted                       - unicode in strings ✓
- reverse sorted
- huge numbers
```

---

## Real Bug Examples Hypothesis Found

1. **Pytest** — Hypothesis found 30+ bugs in pytest itself
2. **NumPy** — float precision edge cases
3. **Django** — URL routing with unicode
4. **SQLAlchemy** — connection pool race conditions

---

## Interview Questions & Answers

### Q1: Basic Hypothesis test for a function?

**Answer:**
```bash
pip install hypothesis pytest
```

```python
# tests/test_email_validator.py
from hypothesis import given, strategies as st, settings, example
import re

def is_valid_email(email: str) -> bool:
    """Production code being tested."""
    if not email or "@" not in email:
        return False
    local, _, domain = email.rpartition("@")
    if not local or not domain:
        return False
    return "." in domain

# ─── Property: valid email roundtrip ───
@given(
    local=st.from_regex(r"[a-zA-Z0-9._%+-]{1,32}", fullmatch=True),
    domain=st.from_regex(r"[a-zA-Z0-9.-]{1,30}\.[a-zA-Z]{2,6}", fullmatch=True),
)
def test_valid_emails_pass(local, domain):
    email = f"{local}@{domain}"
    assert is_valid_email(email), f"Failed: {email!r}"

# ─── Property: invalid emails rejected ───
@given(st.text())
@example("")                              # always test edge cases
@example("plainstring")
@example("@nobody.com")
@example("nodomain@")
def test_invalid_emails_rejected(email):
    if "@" not in email or email.count("@") > 1:
        assert not is_valid_email(email)
```

**Run:**
```bash
pytest tests/test_email_validator.py -v --hypothesis-show-statistics
```

If a bug exists, Hypothesis prints **minimal reproducer**:
```
Falsifying example: test_valid_emails_pass(local='a', domain='b.cc')
```

---

### Q2: Strategies for common Python types?

**Answer:** Hypothesis has rich built-in strategies.

```python
from hypothesis import given, strategies as st
from datetime import datetime, timedelta

@given(st.integers())
def test_int(x): pass

@given(st.integers(min_value=0, max_value=100))
def test_bounded_int(x): pass

@given(st.floats(allow_nan=False, allow_infinity=False))  # finite floats
def test_float(x): pass

@given(st.text(min_size=1, max_size=100))
def test_text(s): pass

@given(st.text(alphabet=st.characters(whitelist_categories=("L", "N"))))  # letters + numbers
def test_alphanum(s): pass

@given(st.lists(st.integers(), min_size=1, max_size=10))
def test_list(lst): pass

@given(st.dictionaries(keys=st.text(), values=st.integers()))
def test_dict(d): pass

@given(st.datetimes(min_value=datetime(2000, 1, 1), max_value=datetime(2030, 12, 31)))
def test_datetime(dt): pass

@given(st.uuids())
def test_uuid(u): pass

@given(st.emails())  # actual valid emails
def test_emails(e): pass

@given(st.from_regex(r"\d{10}", fullmatch=True))
def test_phone(p): pass

@given(st.ip_addresses(v=4))
def test_ipv4(ip): pass

@given(st.one_of(st.integers(), st.floats(), st.text()))  # union type
def test_union(x): pass

@given(st.fixed_dictionaries({
    "user_id": st.integers(min_value=1),
    "email": st.emails(),
    "age": st.integers(min_value=0, max_value=150),
}))
def test_user_dict(user): pass
```

---

### Q3: Pydantic models with Hypothesis?

**Answer:** Use `hypothesis-jsonschema` or custom composite strategies.

```python
from pydantic import BaseModel, Field
from hypothesis import given, strategies as st

class Order(BaseModel):
    order_id: int = Field(..., ge=1)
    user_id: int = Field(..., ge=1)
    total: float = Field(..., ge=0.0, le=1_000_000)
    items: list[str] = Field(..., min_length=1, max_length=50)

# ─── Composite strategy for Order ───
@st.composite
def orders(draw):
    return Order(
        order_id=draw(st.integers(min_value=1)),
        user_id=draw(st.integers(min_value=1)),
        total=draw(st.floats(min_value=0, max_value=1_000_000, allow_nan=False)),
        items=draw(st.lists(st.text(min_size=1, max_size=50), min_size=1, max_size=50)),
    )

@given(orders())
def test_order_serialization_roundtrip(order):
    """Property: JSON serialize/deserialize doesn't change data."""
    json_data = order.model_dump_json()
    restored = Order.model_validate_json(json_data)
    assert order == restored

@given(orders())
def test_order_total_in_range(order):
    """Property: total is always valid per schema."""
    assert 0 <= order.total <= 1_000_000
```

**Auto-generate from JSON Schema** (alternative):
```bash
pip install hypothesis-jsonschema
```

```python
from hypothesis_jsonschema import from_schema

@given(from_schema(Order.model_json_schema()))
def test_any_valid_order(data):
    order = Order.model_validate(data)
    assert order.total >= 0
```

---

### Q4: Testing FastAPI endpoints with Hypothesis?

**Answer:** Combine `httpx.AsyncClient` + Hypothesis strategies.

```python
import pytest
from hypothesis import given, strategies as st, settings
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
@given(
    name=st.text(min_size=1, max_size=100),
    age=st.integers(min_value=0, max_value=150),
)
@settings(max_examples=50, deadline=2000)  # 2s per case
async def test_create_user_endpoint(name, age):
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/users", json={"name": name, "age": age})

        # Property 1: valid inputs → 201
        assert response.status_code in (201, 422)

        if response.status_code == 201:
            data = response.json()
            # Property 2: response echoes input
            assert data["name"] == name
            assert data["age"] == age
            # Property 3: server assigns ID
            assert isinstance(data["id"], int) and data["id"] > 0
```

**Invariants to test:**
- POST + GET → same data
- POST + DELETE + GET → 404
- Pagination: total = sum of page sizes
- Filtering: filtered ⊆ full results

---

### Q5: Stateful testing (simulate sequences of operations)?

**Answer:** `RuleBasedStateMachine` — Hypothesis generates op sequences.

```python
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant, initialize
from hypothesis import strategies as st

class ShoppingCart:
    """Production code."""
    def __init__(self):
        self.items: dict[str, int] = {}

    def add(self, product: str, quantity: int):
        self.items[product] = self.items.get(product, 0) + quantity

    def remove(self, product: str, quantity: int):
        if product in self.items:
            self.items[product] -= quantity
            if self.items[product] <= 0:
                del self.items[product]

    def total_items(self) -> int:
        return sum(self.items.values())

# ─── State machine ───
class CartStateMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.cart = ShoppingCart()
        self.model_total = 0  # our independent tracker

    @rule(product=st.text(min_size=1, max_size=10), qty=st.integers(min_value=1, max_value=10))
    def add_item(self, product, qty):
        self.cart.add(product, qty)
        self.model_total += qty

    @rule(product=st.text(min_size=1, max_size=10), qty=st.integers(min_value=1, max_value=10))
    def remove_item(self, product, qty):
        before = self.cart.items.get(product, 0)
        actually_removed = min(qty, before)
        self.cart.remove(product, qty)
        self.model_total -= actually_removed

    @invariant()
    def total_matches(self):
        """Property: cart total always matches our model."""
        assert self.cart.total_items() == self.model_total, \
            f"Drift: cart={self.cart.total_items()}, model={self.model_total}"

    @invariant()
    def no_negative_quantities(self):
        for product, qty in self.cart.items.items():
            assert qty > 0, f"Negative qty for {product}: {qty}"

# Run as pytest
TestCart = CartStateMachine.TestCase
```

Hypothesis runs hundreds of generated sequences:
```
add("apple", 5)
add("banana", 3)
remove("apple", 2)
add("apple", 1)
remove("banana", 5)
...
```

Will find bugs like double-counting, off-by-one, sync drift.

---

### Q6: Database operations with Hypothesis?

**Answer:** Generate test data + assert invariants.

```python
import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from sqlalchemy.ext.asyncio import AsyncSession

@pytest.mark.asyncio
@given(
    users=st.lists(
        st.fixed_dictionaries({
            "name": st.text(min_size=1, max_size=50),
            "email": st.emails(),
            "age": st.integers(min_value=0, max_value=150),
        }),
        min_size=1, max_size=20,
        unique_by=lambda u: u["email"],  # unique emails
    )
)
@settings(
    max_examples=20,
    deadline=5000,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
async def test_bulk_insert_property(session: AsyncSession, users):
    """Property: bulk insert preserves all rows + uniqueness."""
    # Insert
    for user in users:
        await session.execute(
            "INSERT INTO users (name, email, age) VALUES (:n, :e, :a)",
            user,
        )
    await session.commit()

    # Property 1: row count matches
    result = await session.execute("SELECT COUNT(*) FROM users")
    assert result.scalar() == len(users)

    # Property 2: all emails preserved
    result = await session.execute("SELECT email FROM users")
    db_emails = {row[0] for row in result.all()}
    assert db_emails == {u["email"] for u in users}

    # Cleanup
    await session.execute("DELETE FROM users")
    await session.commit()
```

⚠️ **Hypothesis + databases**: each test should be self-contained (use transactions or cleanup).

---

### Q7: Common properties to test (cheatsheet)?

**Answer:** "Properties" not obvious — here are reusable patterns.

| Pattern | Example |
|---|---|
| **Roundtrip** | `decode(encode(x)) == x` |
| **Idempotence** | `f(f(x)) == f(x)` |
| **Inverse** | `decrypt(encrypt(x)) == x` |
| **Commutativity** | `f(a, b) == f(b, a)` |
| **Associativity** | `f(f(a, b), c) == f(a, f(b, c))` |
| **Identity** | `merge(x, empty) == x` |
| **Length preservation** | `len(map(f, lst)) == len(lst)` |
| **Subset relation** | `filter(p, lst) ⊆ lst` |
| **Ordering** | `sorted(x)[i] <= sorted(x)[i+1]` |
| **Conservation** | `sum(after_op) == sum(before_op)` |

```python
# Roundtrip example
from app.serializers import to_json, from_json

@given(orders())
def test_json_roundtrip(order):
    assert from_json(to_json(order)) == order

# Idempotence example
@given(st.text())
def test_strip_idempotent(s):
    assert s.strip().strip() == s.strip()

# Inverse example
from app.crypto import encrypt, decrypt

@given(st.text(min_size=1), st.binary(min_size=32, max_size=32))
def test_encrypt_decrypt_inverse(plaintext, key):
    ciphertext = encrypt(plaintext, key)
    assert decrypt(ciphertext, key) == plaintext
```

---

### Q8: Configuration + best practices?

**Answer:**
```python
from hypothesis import settings, Verbosity, HealthCheck

# ─── Profile configurations ───
settings.register_profile("ci", max_examples=1000, deadline=None)
settings.register_profile("dev", max_examples=10)
settings.register_profile("debug", max_examples=10, verbosity=Verbosity.verbose)

# Activate based on env
import os
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))

# ─── Per-test override ───
@given(st.integers())
@settings(
    max_examples=200,
    deadline=500,  # 500ms per case
    suppress_health_check=[HealthCheck.too_slow],
    derandomize=False,  # True for reproducible CI
)
def test_with_overrides(x):
    ...
```

**Reproduce a past failure:**
```python
# Hypothesis prints this after failure:
# @reproduce_failure('6.0.0', b'AXicY2BgYGBgZGBkAAAAAQACQ=')

from hypothesis import reproduce_failure

@reproduce_failure('6.0.0', b'AXicY2BgYGBgZGBkAAAAAQACQ=')
@given(st.integers())
def test_my_func(x):
    ...
```

---

## Production Gotchas

| Gotcha | Fix |
|---|---|
| Tests are slow (1000 cases × DB) | Use `max_examples=20`, separate slow tests |
| Flaky tests (timing-dependent) | `derandomize=True` + `deadline=None` |
| Database leaks between tests | Wrap each test in transaction rollback |
| `HealthCheck.function_scoped_fixture` fails | Use module-scoped fixtures or suppress |
| Hard to debug failures | `--hypothesis-show-statistics` + Verbosity.verbose |
| External APIs called many times | Mock at boundary; use Hypothesis on logic only |
| Floats with NaN/inf | `st.floats(allow_nan=False, allow_infinity=False)` |
| Unicode breaks regex | `st.from_regex(..., fullmatch=True)` |

---

## When NOT to Use PBT

- Code with strict examples (e.g., "factorial(5) = 120")
- UI tests (deterministic interactions matter)
- Pure I/O code with no logic
- Solo project, simple CRUD app

**Use PBT for:**
- Parsers/serializers
- Math/algorithms
- State machines
- Encryption/encoding
- Data transformations
- Sort/filter/aggregate operations

---

## Senior-level Checklist

- [ ] Hypothesis added to dev dependencies
- [ ] Critical pure functions have at least one property test
- [ ] CI profile with `max_examples=1000`
- [ ] State machines for complex stateful code (carts, queues, caches)
- [ ] Composite strategies for domain models (Pydantic)
- [ ] Common properties (roundtrip, idempotence, inverse) identified
- [ ] Database cleanup between test runs
- [ ] Reproducible failures saved (`@reproduce_failure`)
- [ ] `--hypothesis-show-statistics` reviewed periodically
- [ ] Settings tuned per test class (deadline, max_examples)

---

## Related Docs
- `contract_testing_pact.md` — complementary external-contract tests
- `load_testing_locust_k6.md` — performance side
- `Phase2_FastAPI/04_testing_sqlalchemy.md` — fixtures + DB testing
- `Phase1_Python_Daily/Day41_Testing/` — pytest basics

## External References
- Hypothesis docs: https://hypothesis.readthedocs.io
- John Hughes (PBT inventor) talks: https://www.youtube.com/results?search_query=john+hughes+property+based
- hypothesis-jsonschema: https://github.com/python-jsonschema/hypothesis-jsonschema
