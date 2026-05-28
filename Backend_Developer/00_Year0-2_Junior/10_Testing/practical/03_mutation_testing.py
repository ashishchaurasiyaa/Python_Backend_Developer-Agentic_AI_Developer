"""
============================================================
MUTATION TESTING — Practical
============================================================
Install:
    pip install mutmut pytest

Run:
    mutmut run --paths-to-mutate=03_mutation_testing.py
    mutmut results
    mutmut html
"""


# ============================================================
# 1. EXAMPLE FUNCTION — has many mutation points
# ============================================================
def calculate_discount(price: float, code: str) -> float:
    """Apply discount code to price. Multiple mutation points."""
    if price <= 0:
        return 0
    if code == "PROMO10":
        return price * 0.10
    elif code == "PROMO20":
        return price * 0.20
    elif code == "VIP":
        return price * 0.30
    return 0


def is_adult(age: int) -> bool:
    return age >= 18


def divide(a: float, b: float) -> float:
    if b == 0:
        raise ValueError("Division by zero")
    return a / b


# ============================================================
# 2. WEAK TESTS (low mutation score)
# ============================================================
def test_promo10_weak():
    """Tests just one path — many mutations survive."""
    assert calculate_discount(100, "PROMO10") == 10


def test_adult_weak():
    """Doesn't test boundary."""
    assert is_adult(25) is True


# ============================================================
# 3. STRONG TESTS (high mutation score)
# ============================================================
import pytest


# Discount tests — covers all branches + edge cases
def test_discount_promo10():
    assert calculate_discount(100, "PROMO10") == 10


def test_discount_promo20():
    assert calculate_discount(100, "PROMO20") == 20


def test_discount_vip():
    assert calculate_discount(100, "VIP") == 30


def test_discount_unknown():
    assert calculate_discount(100, "INVALID") == 0


def test_discount_no_code():
    assert calculate_discount(100, "") == 0


def test_discount_zero_price():
    assert calculate_discount(0, "PROMO10") == 0


def test_discount_negative_price():
    assert calculate_discount(-100, "PROMO10") == 0


# Adult tests — boundary
@pytest.mark.parametrize("age,expected", [
    (17, False),
    (18, True),     # boundary
    (19, True),
    (0, False),
    (100, True),
])
def test_is_adult_boundaries(age, expected):
    assert is_adult(age) is expected


# Division tests — both paths
def test_divide_normal():
    assert divide(10, 2) == 5.0


def test_divide_zero():
    with pytest.raises(ValueError, match="Division by zero"):
        divide(10, 0)


def test_divide_negatives():
    assert divide(-10, -2) == 5.0
    assert divide(-10, 2) == -5.0
    assert divide(10, -2) == -5.0


def test_divide_floats():
    assert divide(1.0, 3.0) == pytest.approx(0.333, rel=0.01)


# ============================================================
# 4. PROPERTY-BASED TESTS (Hypothesis)
# ============================================================
PROPERTY_BASED_TESTS = '''
from hypothesis import given, strategies as st, assume

@given(
    a=st.floats(min_value=-1e6, max_value=1e6, allow_nan=False),
    b=st.floats(allow_nan=False).filter(lambda x: abs(x) > 1e-9),
)
def test_divide_property(a, b):
    result = divide(a, b)
    # Mathematical invariant
    assert result * b == pytest.approx(a, rel=1e-9, abs=1e-9)


@given(
    price=st.floats(min_value=0, max_value=1e6),
    code=st.sampled_from(["PROMO10", "PROMO20", "VIP", "INVALID", ""]),
)
def test_discount_property(price, code):
    discount = calculate_discount(price, code)
    # Discount never exceeds price
    assert 0 <= discount <= price * 0.5
    # Zero price → zero discount
    if price <= 0:
        assert discount == 0


@given(age=st.integers(min_value=0, max_value=120))
def test_is_adult_property(age):
    result = is_adult(age)
    # Discrete check
    if age >= 18:
        assert result is True
    else:
        assert result is False
'''


# ============================================================
# 5. PYPROJECT.TOML CONFIG
# ============================================================
PYPROJECT_CONFIG = """
# pyproject.toml

[tool.mutmut]
paths_to_mutate = ["myapp/"]
tests_dir = ["tests/"]

# Test runner (use -x for speed — stop at first failure)
runner = "python -m pytest -x --tb=no -q --no-header -p no:cacheprovider"

# Don't backup files (faster)
backup = false

# Synonyms for class names
dict_synonyms = ["Struct", "NamedStruct"]

# Exclude patterns
exclude = [
    "*/migrations/*",
    "*/tests/*",
    "*/conftest.py",
    "*/__init__.py",
]
"""


# ============================================================
# 6. MUTMUT WORKFLOW
# ============================================================
MUTMUT_WORKFLOW = """
# 1. RUN MUTATION TESTING
mutmut run --paths-to-mutate myapp/

# Output (live):
# 12345/15000  🎉 11000  ⏰ 200  🤔 3145
# 🎉 = killed by tests (good)
# ⏰ = test timed out (counts as killed)
# 🤔 = mutation survived (BAD)

# 2. SEE RESULTS
mutmut results

# Output:
# To apply a mutant on disk:
#     mutmut apply <id>
# To show a mutant:
#     mutmut show <id>
# Survived 🤔 (3145)
# ---- myapp/discount.py (45) ----
# 12, 14, 27, 28, 34...

# 3. INSPECT SPECIFIC MUTATION
mutmut show 12

# Output:
# def calculate_discount(price, code):
# -    if price <= 0:
# +    if price < 0:        ← mutation: <= changed to <
#         return 0

# 4. FIX TEST OR ACCEPT EQUIVALENT
# Either add test that catches this:
def test_price_zero():
    assert calculate_discount(0, "PROMO10") == 0

# Or mark as equivalent in code:
def calculate_discount(price, code):
    if price <= 0:        # pragma: no mutate
        return 0

# 5. RE-RUN
mutmut run

# 6. HTML REPORT
mutmut html
open html/index.html

# 7. JSON OUTPUT (for CI parsing)
mutmut junitxml > mutation-results.xml
"""


# ============================================================
# 7. COSMIC-RAY (alternative, more features)
# ============================================================
COSMIC_RAY_USAGE = """
# pip install cosmic-ray

# 1. Init session config
cat > config.toml <<EOF
[cosmic-ray]
module-path = "myapp"
timeout = 10
exclude-modules = []
test-command = "pytest -x"

[cosmic-ray.distributor]
name = "local"

[cosmic-ray.distributor.local]
num-workers = 4    # parallelization!
EOF

# 2. Create session
cosmic-ray init config.toml my_session.sqlite

# 3. Execute (this takes time)
cosmic-ray exec my_session.sqlite

# 4. Report
cosmic-ray dump my_session.sqlite | cr-report

# Output:
# total jobs: 1234
# complete: 1234 (100.00%)
# surviving mutants: 145 (11.75%)
# mutation score: 88.25%

# 5. HTML report
cr-html my_session.sqlite > report.html
"""


# ============================================================
# 8. CI WORKFLOW (weekly, not per-PR)
# ============================================================
CI_WORKFLOW = """
# .github/workflows/mutation.yml

name: Mutation Testing
on:
  schedule:
    - cron: '0 0 * * 0'    # Weekly Sunday
  workflow_dispatch:        # Manual trigger

jobs:
  mutation:
    runs-on: ubuntu-latest
    timeout-minutes: 360    # 6 hours max
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }

      - run: |
          pip install -e ".[test]"
          pip install mutmut

      - name: Run mutation tests
        run: mutmut run --paths-to-mutate=myapp/

      - name: Generate HTML report
        if: always()
        run: mutmut html

      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: mutation-report
          path: html/

      - name: Check mutation score
        run: |
          mutmut results > results.txt
          KILLED=$(grep -c "🎉" results.txt || echo 0)
          SURVIVED=$(grep -c "🤔" results.txt || echo 0)
          TOTAL=$((KILLED + SURVIVED))
          SCORE=$((KILLED * 100 / TOTAL))
          echo "Killed: $KILLED, Survived: $SURVIVED, Score: $SCORE%"
          if [ $SCORE -lt 80 ]; then
            echo "::error::Mutation score $SCORE% below 80% threshold"
            exit 1
          fi

      - name: Comment on Slack if score dropped
        if: failure()
        run: |
          curl -X POST -H "Content-Type: application/json" \\
            -d '{"text": "Mutation score dropped below 80%! Check report."}' \\
            ${{ secrets.SLACK_WEBHOOK }}
"""


# ============================================================
# 9. INCREMENTAL MUTATION TESTING
# ============================================================
INCREMENTAL = """
# Only mutate files changed in this PR

CHANGED_FILES=$(git diff --name-only origin/main...HEAD -- '*.py' | tr '\\n' ',')

if [ -z "$CHANGED_FILES" ]; then
    echo "No Python files changed"
    exit 0
fi

mutmut run --paths-to-mutate="$CHANGED_FILES"

# Or run incrementally — only newly added mutations
mutmut run --rerun-all-survived  # retest survivors after improvements
"""


# ============================================================
# 10. EXCLUDING CODE FROM MUTATION
# ============================================================
EXCLUSION_PATTERNS = '''
# Inline:
def main():
    # pragma: no mutate
    print("CLI entry, tested via integration tests")

# Whole function:
def __repr__(self):
    # pragma: no mutate
    return f"<User {self.id}>"

# Config file (pyproject.toml):
[tool.mutmut]
exclude = [
    "*/migrations/*",
    "*/models.py",            # too many false positives
    "*/admin.py",
    "*/wsgi.py",
    "*/asgi.py",
]
'''


# ============================================================
# 11. MUTATION SCORE INTERPRETATION
# ============================================================
SCORE_GUIDE = """
================================================================
MUTATION SCORE INTERPRETATION
================================================================

< 60%   — Critical: tests barely catch bugs
60-70%  — Weak: significant gaps
70-80%  — OK: room to improve
80-90%  — Good: solid test suite
> 90%   — Excellent: top tier
100%    — Likely impossible (equivalent mutations exist)

PRACTICAL TARGETS:
- New codebase:     start at 60%, improve over time
- Mature codebase:  80%+ expected
- Critical (finance, healthcare): 90%+
================================================================

WHY NOT 100%?
- Equivalent mutations (semantically same code)
  Example: `i < 10` → `i <= 9` in `range(10)` loop
- Compiler optimizations make some mutations dead code
- Branches that can never execute given constraints
================================================================
"""


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("MUTATION TESTING — Practical")
    print("=" * 60)

    print("\nQuick start:")
    print("  pip install mutmut")
    print("  mutmut run --paths-to-mutate=03_mutation_testing.py")
    print("  mutmut results")
    print("  mutmut html")

    print("\n--- PYPROJECT CONFIG ---")
    print(PYPROJECT_CONFIG)
    print("\n--- WORKFLOW ---")
    print(MUTMUT_WORKFLOW)
    print("\n--- COSMIC-RAY (alternative) ---")
    print(COSMIC_RAY_USAGE)
    print("\n--- CI WORKFLOW ---")
    print(CI_WORKFLOW)
    print("\n--- INCREMENTAL ---")
    print(INCREMENTAL)
    print("\n--- EXCLUSION ---")
    print(EXCLUSION_PATTERNS)
    print("\n--- PROPERTY-BASED TESTS ---")
    print(PROPERTY_BASED_TESTS)
    print(SCORE_GUIDE)
