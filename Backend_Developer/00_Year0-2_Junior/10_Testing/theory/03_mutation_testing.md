# Mutation Testing

> **Interview angle:** "100% code coverage hai. Tests achhe hain?" → NO. Coverage measures lines hit, not bug-catching power.

---

## 1. The Problem with Coverage

```python
def divide(a, b):
    return a / b      # line covered, but...

def test_divide():
    divide(10, 2)      # 100% coverage, no assertion!
```

100% coverage with **zero assertions** = useless tests. Coverage misses:
- Whether tests actually catch bugs
- Edge cases not tested
- Logic flaws

---

## 2. What is Mutation Testing?

**Tool deliberately introduces bugs (mutations) into your code, then runs your tests.**

- Test catches mutation → "killed" (good)
- Test doesn't catch → "survived" (BAD — tests don't notice the bug)

**Mutation score** = killed / total mutations.

### Example
Original:
```python
def is_positive(x):
    return x > 0

def test_positive():
    assert is_positive(5) is True
```

Mutator changes `> 0` to `>= 0`:
```python
def is_positive(x):
    return x >= 0     # mutation
```

Test still passes (5 >= 0 = True). **Mutation survived = bad test!**

Add stronger test:
```python
def test_zero():
    assert is_positive(0) is False   # now catches mutation
```

---

## 3. Common Mutation Operators

| Original | Mutated | Mutation type |
|---|---|---|
| `x > 0` | `x >= 0`, `x < 0` | Relational |
| `a + b` | `a - b`, `a * b` | Arithmetic |
| `True` | `False` | Constant |
| `and` | `or` | Boolean |
| `return x` | `return None` | Return |
| `for i in items:` | `for i in []:` | Loop |
| `if x:` | `if not x:` | Condition |
| `x = 0` | `x = 1`, `x = -1` | Number boundary |

---

## 4. Python Tools

### `mutmut` (most popular)
```bash
pip install mutmut

mutmut run --paths-to-mutate myapp/
mutmut results
mutmut show 42         # see specific mutation
mutmut html            # generate HTML report
```

### `cosmic-ray`
```bash
pip install cosmic-ray

cosmic-ray init config.toml my_session
cosmic-ray exec my_session
cosmic-ray dump my_session | cr-report
```

### `mutpy`
- Older, less actively maintained.

**Recommended: mutmut for ease, cosmic-ray for flexibility.**

---

## 5. Workflow

```
1. Run mutation testing → mutmut creates mutations, runs tests
2. Check survived mutations → write missing tests
3. Aim for >= 80% mutation score
4. Run periodically (CI or weekly)
```

---

## 6. mutmut Setup

```ini
# pyproject.toml or setup.cfg
[tool.mutmut]
paths_to_mutate = ["myapp/"]
runner = "pytest -x --tb=no"   # -x = stop after first failure (fast)
tests_dir = ["tests/"]
backup = false
dict_synonyms = ["Struct", "NamedStruct"]
```

### Running
```bash
# Run all mutations
mutmut run

# Output (live):
# 12345/15000  🎉 11000  ⏰ 200  🤔 3145

# 🎉 = killed (test caught mutation)
# ⏰ = timeout (test ran too slow — also counts as killed)
# 🤔 = survived (BAD — fix this!)

# Show survivors
mutmut results

# Inspect specific
mutmut show 1234   # shows diff of mutation 1234

# Get HTML report
mutmut html
open html/index.html
```

---

## 7. Mutation Score Targets

- **< 60%:** weak test suite — needs major improvement
- **60-80%:** OK, room to grow
- **80-90%:** good
- **> 90%:** excellent
- **100%:** unrealistic; some mutations equivalent (semantically same code)

---

## 8. Equivalent Mutations

Some mutations don't change behavior:
```python
# Original
i = 0
while i < 10:
    i += 1

# Mutation: i < 10 → i <= 9
# Semantically identical! Tests can't catch this.
```

Document these as "equivalent" — won't be killed but acceptable.

---

## 9. CI Integration

```yaml
# .github/workflows/mutation.yml

# Run weekly, not on every PR (slow)
on:
  schedule:
    - cron: "0 0 * * 0"   # weekly Sunday midnight
  workflow_dispatch:

jobs:
  mutation:
    runs-on: ubuntu-latest
    timeout-minutes: 360       # mutation testing is slow
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }

      - run: pip install -e ".[test]" mutmut

      - name: Run mutation tests
        run: mutmut run --paths-to-mutate=myapp/

      - name: Generate report
        run: mutmut html

      - uses: actions/upload-artifact@v4
        with:
          name: mutation-report
          path: html/

      - name: Check mutation score
        run: |
          KILLED=$(mutmut results | grep -c "killed")
          TOTAL=$(mutmut results | grep -c "mutant")
          SCORE=$((KILLED * 100 / TOTAL))
          echo "Mutation score: $SCORE%"
          if [ $SCORE -lt 80 ]; then
            exit 1
          fi
```

---

## 10. When NOT to Mutation Test

- **Too slow for every PR** (mutation testing is N × test time)
- **Code with side effects** (DB writes, HTTP calls) — flaky mutations
- **Code that calls external services**
- **Already 100% coverage of branches** — diminishing returns

**Run weekly + on demand, not every commit.**

---

## 11. Optimizing Performance

### 1. Run incrementally
```bash
# Only mutate changed files
mutmut run --paths-to-mutate=$(git diff --name-only HEAD~5 -- '*.py')
```

### 2. Parallelize
```bash
# mutmut doesn't parallelize natively, but cosmic-ray does
cosmic-ray exec --num-workers 4 session.toml
```

### 3. Fast test runner
```ini
[tool.mutmut]
runner = "pytest -x --tb=no -q -p no:cacheprovider"
```

### 4. Stop at first failure
`pytest -x` stops on first failure → faster per-mutation.

### 5. Exclude untestable code
```python
def main():           # pragma: no mutate
    print("CLI entry — covered by integration tests")
```

---

## 12. Strategies to Improve Score

### Strategy 1: Write boundary tests
```python
# Original
def is_adult(age):
    return age >= 18

# Tests catching: age = 17, 18, 19
def test_under():    assert not is_adult(17)
def test_exact():    assert is_adult(18)
def test_over():     assert is_adult(19)
# Now mutation `>= 18` → `> 18` is caught by test_exact
```

### Strategy 2: Test error paths
```python
def divide(a, b):
    if b == 0:
        raise ValueError("zero divisor")
    return a / b

# Test BOTH paths
def test_normal():    assert divide(10, 2) == 5
def test_zero():
    with pytest.raises(ValueError):
        divide(10, 0)
```

### Strategy 3: Property-based testing (with Hypothesis)
```python
from hypothesis import given, strategies as st

@given(a=st.integers(), b=st.integers().filter(lambda x: x != 0))
def test_divide_property(a, b):
    result = divide(a, b)
    assert result * b == a   # mathematical invariant
```

Property tests often catch mutations that example tests miss.

---

## 13. Real Example

```python
# myapp/discount.py
def calculate_discount(price, code):
    if code == "PROMO10":
        return price * 0.10
    elif code == "PROMO20":
        return price * 0.20
    return 0

# Existing test
def test_promo10():
    assert calculate_discount(100, "PROMO10") == 10

# Mutations that SURVIVE this test:
# - 0.10 → 0.20  → no PROMO20 test, can't catch
# - 0.10 → 0.0   → discount = 0, test wants 10, IS caught
# - elif code == "PROMO20" → if False:  → no test for PROMO20
# - return 0 → return 1 → no test for unknown code

# Better tests:
def test_promo10():    assert calculate_discount(100, "PROMO10") == 10
def test_promo20():    assert calculate_discount(100, "PROMO20") == 20
def test_no_code():    assert calculate_discount(100, "INVALID") == 0
```

---

## 14. Comparison: Coverage vs Mutation

| Aspect | Coverage | Mutation |
|---|---|---|
| Measures | Lines executed | Bug-catching power |
| False positive | Lines hit ≠ tested | Almost none |
| Speed | Fast | Slow (10-100x) |
| Industry standard | Yes | Growing |
| Cost | Cheap | Compute-heavy |

**Use both:**
- Coverage for daily feedback
- Mutation for periodic deep audit

---

## 15. Common Pitfalls

### Pitfall 1: 100% mutation score chase
Diminishing returns. Equivalent mutations + complex code. 85% is great.

### Pitfall 2: Running on every PR
Way too slow. Schedule weekly.

### Pitfall 3: Ignoring timeouts
Some mutations cause infinite loops. Set per-test timeout.

### Pitfall 4: Not actioning results
Generate report but never improve tests. Schedule "mutation review" sessions.

### Pitfall 5: Mutating UI / boilerplate
Don't mutate Django settings, Flask app init, etc. Use config to exclude.

---

## 16. Interview Questions

**Q1: Coverage 100% par tests achhe hain?**
Not necessarily. Coverage = lines hit. Mutation testing measures whether tests CATCH bugs.

**Q2: Mutation testing kya?**
Tool introduces bugs (mutations). If test catches → killed (good). Survives → tests are weak.

**Q3: Tools?**
mutmut, cosmic-ray. mutmut popular for Python.

**Q4: Mutation score target?**
80%+ good. 90%+ excellent. 100% unrealistic (equivalent mutations).

**Q5: Why slow?**
Each mutation = run entire test suite. 10K mutations × 5min tests = days.

**Q6: When to run?**
Weekly schedule, not every PR. Investigate survivors during code review.

**Q7: Improve mutation score how?**
Boundary tests, error path tests, property-based testing (Hypothesis).

---

## 17. Best Practices

1. **Run weekly**, not every commit
2. **80%+ mutation score** target
3. **Investigate survivors** — they're real test gaps
4. **Combine with Hypothesis** for property-based tests
5. **Exclude untestable code** (`# pragma: no mutate`)
6. **HTML reports** for code review
7. **Tighten boundary conditions** (`>`, `>=`)
8. **Test error paths** (raised exceptions)
9. **Use coverage AND mutation** — different signals
10. **Document equivalent mutations**

---

## Related
- [[01_pytest_advanced]]
- [[02_snapshot_testing]]
- [[05_test_parallelization]]
