# Testing — Mutation Testing with mutmut & Cosmic Ray
**Testing · Year 0-2 | Senior Backend + Agentic AI**

## Quick Concepts
- **Mutation testing** = systematically introduce small bugs (mutants) into your code, run tests, check if tests catch them
- **Mutant** = a single-line change to source code (e.g., `>` → `>=`)
- **Killed mutant** = a test failed because of the mutation (good — tests work)
- **Surviving mutant** = no test failed (bad — your tests don't cover this case)
- **Mutation score** = % of mutants killed = test quality metric
- **mutmut** = Python's most popular mutation tester
- **Cosmic Ray** = alternative; distributed-friendly
- **Equivalent mutant** = mutation that doesn't change behavior (false positive, must skip)

---

## Why Mutation Testing?

```
COVERAGE TELLS YOU:                MUTATION TESTING TELLS YOU:
──────────────                     ────────────────────
"Tests touched 90% of lines."      "Tests would catch 70% of bugs."

100% coverage doesn't mean         70% mutation score means
tests detect bugs:                 30% of small code changes
                                   wouldn't be caught.

def divide(a, b):
    return a / b                   ← coverage 100%

def test():                        ← passes regardless of `divide` impl
    divide(10, 2)                  ← weak assertion

# Mutate `a / b` → `a * b`         Test STILL PASSES.
# Mutation reveals weak test.
```

---

## Real-World Impact

```
Service: payment-service
Coverage: 92% (looks great!)
Mutation score: 64% (alarming!)

Found:
• 23 surviving mutants in fee calculation
• 11 surviving mutants in retry logic
• 7 surviving mutants in idempotency check

Result: Added 18 new test assertions.
Mutation score: 64% → 89%.
Found 3 real bugs during process.
```

---

## Common Mutations

| Mutation | Original | Mutated |
|---|---|---|
| Arithmetic | `x + y` | `x - y` |
| Comparison | `x > y` | `x >= y` |
| Boolean | `and` | `or` |
| Constants | `True` | `False` |
| Return | `return x` | `return None` |
| Loop | `range(10)` | `range(11)` |
| Slice | `lst[1:]` | `lst[0:]` |
| Conditional | `if x:` | `if not x:` |
| Negation | `not x` | `x` |
| Off-by-one | `i < n` | `i <= n` |

---

## Interview Questions & Answers

### Q1: mutmut basic setup + first run?

**Answer:**
```bash
pip install mutmut

# Configure in pyproject.toml
cat >> pyproject.toml <<EOF
[tool.mutmut]
paths_to_mutate = "app/"
backup = false
runner = "python -m pytest -x -q"
tests_dir = "tests/"
EOF

# Run mutation testing (slow — minutes to hours)
mutmut run

# View results
mutmut results
mutmut html  # generates HTML report
```

**Sample output:**
```
Legend for output:
🎉 Killed mutants.   The goal is for everything to end up in this bucket.
⏰ Timeout.          Test ran too long (timeouts == killed).
🤔 Suspicious.       Tests pass but with warnings — check manually.
🙁 Survived.         A mutation passed all tests — your test suite has a gap.
🔇 Skipped.          A mutation that was skipped (config).

3201/3201  🎉 2143  ⏰ 12  🤔 4  🙁 1042  🔇 0
```

**Mutation score:** `2143 killed / (2143 + 1042 survived) = 67%`

---

### Q2: Inspect surviving mutants — fix tests?

**Answer:**
```bash
# List survived mutants
mutmut results | grep "survived"

# Inspect one
mutmut show 142

# Output:
--- app/calculator.py
+++ app/calculator.py
@@ -10,7 +10,7 @@
 def apply_discount(price: float, percent: float) -> float:
-    if percent < 0 or percent > 100:
+    if percent < 0 or percent >= 100:
         raise ValueError("Invalid percent")
     return price * (1 - percent / 100)
```

**The bug it introduced:** Now `100%` discount throws error, but original code allowed it.

**Question:** Why didn't tests catch this?

Look at the test:
```python
# tests/test_calculator.py
def test_apply_discount():
    assert apply_discount(100, 10) == 90  # only tests 10%
```

**Fix:**
```python
def test_apply_discount():
    assert apply_discount(100, 10) == 90
    assert apply_discount(100, 0) == 100      # 0% boundary
    assert apply_discount(100, 100) == 0      # 100% boundary
    with pytest.raises(ValueError):
        apply_discount(100, 101)               # invalid
    with pytest.raises(ValueError):
        apply_discount(100, -1)
```

Re-run `mutmut run` → mutant 142 should now die.

---

### Q3: mutmut configuration tuning?

**Answer:**
```toml
# pyproject.toml
[tool.mutmut]
paths_to_mutate = ["app/services/", "app/utils/"]  # focus on core logic
backup = false
runner = "python -m pytest -x -q --no-cov tests/unit/"  # fast unit tests only
tests_dir = "tests/"

# Don't mutate certain patterns
also_copy = ["alembic.ini"]

# Skip mutations matching regex
no_mutate_patterns = [
    "logger.*",
    "print\\(.*",
    "raise NotImplementedError",
]
```

**Per-line skip (in code):**
```python
def critical_function():
    # mutmut: disable
    pass  # avoid mutating this section
    # mutmut: enable
```

**Faster runs:**
```bash
# Use multiple processes
mutmut run --use-coverage  # only mutate covered lines

# Parallel execution (requires patches)
pip install mutmut[parallel]
mutmut run --processes 8
```

---

### Q4: Cosmic Ray — alternative for distributed runs?

**Answer:** Cosmic Ray supports distributed execution.

```bash
pip install cosmic-ray

# Initialize config
cat > cosmic-ray.toml <<EOF
[cosmic-ray]
module-path = "app"
timeout = 30
excluded-modules = []
test-command = "python -m pytest -x -q"

[cosmic-ray.distributor]
name = "local"  # or "celery4" for distributed
EOF

# Initialize session (1-time)
cosmic-ray init cosmic-ray.toml session.sqlite

# Run mutations
cosmic-ray exec cosmic-ray.toml session.sqlite

# Generate report
cr-report session.sqlite
cr-html session.sqlite > report.html

# JSON output for CI
cr-rate session.sqlite
# Returns mutation rate as float
```

**Distributed with Celery:**
```toml
[cosmic-ray.distributor]
name = "celery4"

[cosmic-ray.distributor.celery]
backend = "redis://localhost"
broker = "redis://localhost"
```

```bash
# Start workers on multiple machines
celery -A cosmic_ray.distribution.celery.app worker -l info

# Distribute load
cosmic-ray exec cosmic-ray.toml session.sqlite
```

---

### Q5: CI integration — gate on mutation score?

**Answer:** Run mutation testing nightly; fail if score drops.

```yaml
# .github/workflows/mutation.yml
name: Mutation Testing
on:
  schedule:
    - cron: '0 2 * * *'  # nightly at 2 AM
  workflow_dispatch:

jobs:
  mutation:
    runs-on: ubuntu-latest
    timeout-minutes: 120

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install mutmut

      - name: Restore cache
        uses: actions/cache@v4
        with:
          path: .mutmut-cache
          key: mutmut-${{ runner.os }}-${{ hashFiles('app/**/*.py') }}
          restore-keys: mutmut-${{ runner.os }}-

      - name: Run mutation testing
        run: mutmut run --use-coverage

      - name: Generate report
        if: always()
        run: |
          mutmut html
          mutmut junitxml > mutmut-results.xml

      - name: Check mutation score
        run: |
          SCORE=$(python -c "
          import re
          out = subprocess.check_output(['mutmut', 'results']).decode()
          killed = int(re.search(r'🎉 (\d+)', out).group(1))
          survived = int(re.search(r'🙁 (\d+)', out).group(1))
          score = killed / (killed + survived) * 100
          print(f'{score:.1f}')
          ")
          echo "Mutation score: $SCORE%"
          if (( $(echo "$SCORE < 75" | bc -l) )); then
            echo "FAIL: mutation score below 75%"
            exit 1
          fi

      - name: Upload report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: mutation-report
          path: html/
```

**Score thresholds (suggested):**
- Critical code (payments, auth): ≥ 90%
- Business logic: ≥ 80%
- Utilities: ≥ 70%
- DTOs / simple wrappers: 50%+ is fine

---

### Q6: Where to focus mutation testing (high ROI)?

**Answer:** Don't mutate everything — focus on critical code.

```python
# Mutate-worthy code:
# ✅ Pricing logic, discount calculations
# ✅ Auth checks, RBAC decisions
# ✅ State machines (order status transitions)
# ✅ Idempotency keys, deduplication
# ✅ Date/time arithmetic (timezones, recurrence)
# ✅ Crypto/HMAC verification
# ✅ Retry logic, backoff
# ✅ Validation logic

# Skip:
# ❌ Logging statements
# ❌ Simple getters/setters
# ❌ Auto-generated code (Pydantic, Alembic)
# ❌ ORM model definitions
# ❌ Configuration loading
```

**Selective mutation:**
```toml
[tool.mutmut]
paths_to_mutate = [
    "app/payments/",
    "app/auth/",
    "app/orders/state_machine.py",
    "app/billing/calculations.py",
]
```

---

### Q7: Handling equivalent mutants (false positives)?

**Answer:** Some mutants don't change behavior — must be documented.

```python
# Example: equivalent mutant
def get_user_age(birth_year: int) -> int:
    current_year = 2026
    return current_year - birth_year

# Mutant: current_year = 2026 → current_year = 2025
# This mutant won't be caught by:
#   assert get_user_age(2000) > 0  # both return positive
#
# But:
#   assert get_user_age(2000) == 26  # this catches it
```

**Equivalent mutant** = a mutation that produces semantically identical code:
```python
def is_positive(x: int) -> bool:
    return x > 0

# Mutant: `x > 0` → `0 < x`
# These are logically identical — equivalent mutant
# Tests CAN'T catch this; must be manually skipped
```

**Skip in mutmut:**
```python
# Mark equivalent mutant for skipping (manual review required)
def is_positive(x: int) -> bool:
    return x > 0  # mutmut: skip_mutation
```

**Goal:** Mutation score of 100% is unrealistic (5-15% are typically equivalent). Aim for high score with documented exceptions.

---

### Q8: Combining mutation testing with property-based testing?

**Answer:** Best combo — mutation reveals weak tests, property-based generates strong ones.

```python
# Original code
def merge_sorted(a: list[int], b: list[int]) -> list[int]:
    """Merge two sorted lists."""
    result = []
    i, j = 0, 0
    while i < len(a) and j < len(b):
        if a[i] < b[j]:
            result.append(a[i])
            i += 1
        else:
            result.append(b[j])
            j += 1
    result.extend(a[i:])
    result.extend(b[j:])
    return result

# Weak example test (mutmut would find gaps)
def test_merge():
    assert merge_sorted([1, 3], [2, 4]) == [1, 2, 3, 4]

# Strong property-based test (catches more mutations)
from hypothesis import given, strategies as st

@given(
    a=st.lists(st.integers()).map(sorted),
    b=st.lists(st.integers()).map(sorted),
)
def test_merge_properties(a, b):
    result = merge_sorted(a, b)
    # Property 1: length preserved
    assert len(result) == len(a) + len(b)
    # Property 2: sorted output
    assert result == sorted(result)
    # Property 3: all elements present (multiset equal)
    assert sorted(result) == sorted(a + b)
    # Property 4: no extra elements
    from collections import Counter
    assert Counter(result) == Counter(a) + Counter(b)
```

**Workflow:**
1. Write code
2. Write basic tests
3. Run mutation testing → find gaps
4. For each surviving mutant, write property test OR explicit edge case
5. Repeat until mutation score acceptable

---

## When NOT to Use Mutation Testing

- **Tight deadlines** — mutation runs are slow (minutes-hours)
- **Code stability is unclear** — focus on writing tests first, then mutate
- **Pure I/O / glue code** — low ROI
- **External SDK wrappers** — testing 3rd party isn't your job
- **Mocks-heavy code** — mutations on real code, mocks unchanged → false survivors

---

## Production Gotchas

| Gotcha | Fix |
|---|---|
| Runs take hours | `--use-coverage`; mutate only changed files in PR |
| Flaky tests cause survivors | Fix flakiness first; mutation reveals it |
| Mocks hide mutations | Avoid over-mocking; test real behavior |
| Timeout issues | Increase timeout per mutant; investigate slow tests |
| Equivalent mutants frustrate | Document; accept score 85-95% as ceiling |
| Mutation cache stale | Clear `.mutmut-cache` periodically |
| Output is overwhelming | Filter by file/module |
| Doesn't catch concurrency bugs | Combine with stress tests + chaos |

---

## Mutation Testing in PR vs Nightly

| Approach | Frequency | Scope |
|---|---|---|
| **PR check** | Every PR | Only changed files (mutmut + git diff) |
| **Nightly** | Once/night | Full codebase |
| **Weekly** | Once/week | Deep run, full coverage |

**Changed-files-only script:**
```bash
#!/bin/bash
# .ci/mutation-pr.sh
# Run mutation testing only on files changed in this PR

CHANGED=$(git diff --name-only origin/main..HEAD | grep "\.py$" | grep -v "test_" | grep -v "__")

if [ -z "$CHANGED" ]; then
    echo "No Python source files changed"
    exit 0
fi

echo "Running mutation testing on:"
echo "$CHANGED"

# Configure mutmut for just these files
cat > /tmp/mutmut.toml <<EOF
[tool.mutmut]
paths_to_mutate = $(echo "$CHANGED" | python -c 'import sys; print(str([l.strip() for l in sys.stdin]))')
runner = "python -m pytest -x -q tests/"
EOF

mutmut run --config /tmp/mutmut.toml
```

---

## Senior-level Checklist

- [ ] Mutation testing tool installed (mutmut or Cosmic Ray)
- [ ] Critical modules identified for high mutation score
- [ ] CI runs mutation tests (nightly minimum)
- [ ] PR-level mutation testing on changed files
- [ ] Mutation score baseline established + monitored
- [ ] Threshold gate enforced in CI (≥ 75% typical)
- [ ] Survived mutants triaged weekly
- [ ] Equivalent mutants documented + skipped
- [ ] Combined with property-based testing for max coverage
- [ ] Mock usage audited (over-mocking hides mutations)
- [ ] HTML reports archived
- [ ] Quarterly review of mutation score trends

---

## Tool Comparison

| Tool | Pros | Cons |
|---|---|---|
| **mutmut** | Most popular, easy setup | Single-process slow |
| **Cosmic Ray** | Distributed-friendly | More complex config |
| **MutPy** | Academic features | Smaller community |
| **PIT (Java)** | Industry standard | Java-only |

---

## Related Docs
- `contract_testing_pact.md` — external contract tests
- `property_based_testing_hypothesis.md` — input-driven (complementary)
- `load_testing_locust_k6.md` — performance testing
- `00_Year0-2_Junior/06_FastAPI/04_testing_sqlalchemy.md` — integration testing
- `01_Year3-4_Mid/03_Security/12_security_testing.md` — security-focused testing

## External References
- mutmut: https://mutmut.readthedocs.io
- Cosmic Ray: https://cosmic-ray.readthedocs.io
- Mutation Testing Survey: https://arxiv.org/abs/1606.05738
- "PIT" Java tool for inspiration: https://pitest.org
