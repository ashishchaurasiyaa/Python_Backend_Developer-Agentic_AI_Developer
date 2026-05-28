# Snapshot Testing

> **Interview angle:** "API ka response shape change ho gaya — 50 tests update karne padenge. Behtar tareeqa?"

---

## 1. The Problem

Traditional test:
```python
def test_user_response():
    response = client.get("/users/1")
    assert response.json() == {
        "id": 1,
        "name": "Alice",
        "email": "a@x.com",
        "created_at": "2024-01-01T00:00:00",
        "preferences": {...},      # 20+ more fields
    }
```

Adding 1 field → must update every test that asserts shape.

**Snapshot testing:** Capture output once, compare future runs against that snapshot.

---

## 2. How It Works

```python
def test_user_response(snapshot):
    response = client.get("/users/1").json()
    assert response == snapshot
```

1. **First run:** Snapshot doesn't exist → creates file with current output.
2. **Subsequent runs:** Compare new output to stored snapshot.
3. **If different:** Test fails, shows diff.
4. **Intentional change:** Run `pytest --snapshot-update` to regenerate.

---

## 3. When to Use

✅ **Use snapshot tests for:**
- API response shapes (JSON, XML)
- HTML rendering
- Generated SQL queries
- Code generation output
- CLI output
- Log line formats

❌ **DON'T use for:**
- Dynamic values (timestamps, random IDs) — needs filters
- Critical business logic — explicit assertions better
- Anything that changes frequently (PR friction)

---

## 4. Python Tools

### `syrupy` (recommended)
```bash
pip install syrupy
```

```python
import pytest

def test_api_response(snapshot):
    response = {"id": 1, "name": "Alice"}
    assert response == snapshot
```

### `pytest-snapshot`
```python
def test_html(snapshot):
    snapshot.assert_match(rendered_html, "output.html")
```

### `ApprovalTests`
```python
from approvaltests import verify

def test_report():
    verify(generate_report())
```

---

## 5. syrupy Examples

### Basic
```python
def test_user_dict(snapshot):
    data = {"id": 1, "name": "Alice", "age": 30}
    assert data == snapshot
```

After first run, generates:
```ambr
# tests/__snapshots__/test_users.ambr
# serializer version: 1
# name: test_user_dict
  dict({
    'age': 30,
    'id': 1,
    'name': 'Alice',
  })
# ---
```

### Per-fixture customization
```python
@pytest.fixture
def snapshot(snapshot):
    return snapshot.with_defaults(extension_class=JSONSnapshotExtension)
```

### Multi-format
```python
from syrupy.extensions.json import JSONSnapshotExtension
from syrupy.extensions.amber import AmberSnapshotExtension

def test_json(snapshot):
    snapshot = snapshot.with_defaults(extension_class=JSONSnapshotExtension)
    assert {"a": 1} == snapshot
```

---

## 6. Filtering Dynamic Data

```python
import re
from syrupy.matchers import path_type
from syrupy.filters import props

def test_user_with_timestamp(snapshot):
    response = {
        "id": 1,
        "name": "Alice",
        "created_at": datetime.now().isoformat(),  # changes each run!
    }
    # Exclude timestamp from snapshot
    assert response == snapshot(exclude=props("created_at"))
```

### Match by type instead of value
```python
def test_with_uuid(snapshot):
    response = {"id": str(uuid.uuid4()), "name": "Alice"}
    matcher = path_type({
        "id": (str,),    # only check it's a string, not exact value
    })
    assert response == snapshot(matcher=matcher)
```

### Regex replacement
```python
TIMESTAMP_PATTERN = r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}'

def normalize(text):
    return re.sub(TIMESTAMP_PATTERN, "<TIMESTAMP>", text)

def test_log_output(snapshot):
    assert normalize(log_text) == snapshot
```

---

## 7. Updating Snapshots

```bash
# Update all (CI: NEVER do this; local only)
pytest --snapshot-update

# Update specific test
pytest --snapshot-update tests/test_users.py::test_user_dict

# See what would change without updating
pytest --snapshot-diff
```

**Workflow:**
1. Make code change
2. Run tests → snapshot fails
3. Review diff carefully
4. If intended, run `--snapshot-update`
5. Commit updated snapshots WITH code change

---

## 8. CI/Code Review Strategy

### Snapshot files committed to git
- Easy to review in PR
- Diff shows exactly what response changed

### Reviewers
- Eyes-on every snapshot change
- If snapshot diff is huge and unexplained → suspicious

### Strict mode in CI
```bash
pytest --no-snapshot-update    # fail if snapshots don't exist
```

This prevents committing without ever running tests.

---

## 9. HTML Rendering Snapshots

```python
def test_email_template_renders(snapshot):
    html = render_template("welcome.html", name="Alice")
    assert html == snapshot
```

If you change the template, diff shows exactly what HTML changed.

---

## 10. SQL Query Snapshots

```python
def test_user_query(snapshot):
    from sqlalchemy.dialects import postgresql
    query = User.query.filter(User.active == True).order_by(User.id)
    sql = query.statement.compile(dialect=postgresql.dialect())
    assert str(sql) == snapshot
```

Detects unintended ORM changes that alter query.

---

## 11. Multi-Tier Snapshots

```python
@pytest.mark.parametrize("user_type", ["admin", "user", "guest"])
def test_response_by_role(user_type, snapshot):
    response = client.get(f"/dashboard?role={user_type}").json()
    assert response == snapshot
    # Stores separate snapshot per role
```

---

## 12. Common Pitfalls

### Pitfall 1: Mindless updates
PR breaks 50 snapshots → run `--update-all` → ship without review.

**Fix:** Force eyes-on every snapshot diff. Update only intended ones.

### Pitfall 2: Snapshots with dynamic data
Snapshot changes every run → useless. Use filters.

### Pitfall 3: Huge snapshots
1000-line snapshot = unreadable diff. Break into smaller assertions.

### Pitfall 4: Replacing logical tests
```python
# ❌ Don't replace business logic test with snapshot
def test_discount_calculation(snapshot):
    assert calculate_discount(100, "PROMO") == snapshot
# Snapshot might be wrong, you wouldn't know!

# ✅ Explicit assertion for business logic
def test_discount():
    assert calculate_discount(100, "PROMO") == 10
```

### Pitfall 5: Not committing snapshot files
PR runs CI → snapshot doesn't exist → test "passes" (creates it). Reviewer never sees it.

**Fix:** Add snapshots to git, use `--no-snapshot-update` in CI.

---

## 13. Snapshot vs Other Test Types

| Test Type | Use For |
|---|---|
| **Unit test** | Specific behavior, edge cases |
| **Integration test** | Component interactions |
| **Snapshot test** | Output structure stability |
| **Property-based** | Invariants over many inputs |
| **E2E test** | Full user flow |

**Snapshot complements, doesn't replace.**

---

## 14. Real Use Cases

### Use case 1: API response shape
Catches accidental field removal/rename.

### Use case 2: Email templates
Designer changes template → snapshot fails → reviewer sees diff.

### Use case 3: CLI output
```python
def test_cli_help(snapshot):
    result = run_cli(["--help"])
    assert result.stdout == snapshot
```

### Use case 4: Generated migration files
```python
def test_migration_sql(snapshot):
    migration = alembic_generate_migration()
    assert migration.sql == snapshot
```

### Use case 5: Compiled assets
JSON config built from sources — snapshot the output.

---

## 15. Interview Questions

**Q1: Snapshot testing kya hai?**
Capture expected output once. Future runs compare against stored snapshot. Auto-update via flag.

**Q2: When to use?**
Output shape (API JSON, HTML, SQL, CLI). NOT for business logic correctness.

**Q3: Dynamic data problem?**
Timestamps, UUIDs change each run. Use filters (exclude paths, type matchers, regex normalization).

**Q4: Risk of snapshot tests?**
Mindless updates miss bugs. Mitigation: review every snapshot diff carefully.

**Q5: CI strategy?**
- Snapshots committed to git
- `--no-snapshot-update` in CI (fail if missing)
- Force re-run + commit locally if intentional change

**Q6: syrupy vs ApprovalTests?**
syrupy = pytest-integrated, modern, recommended. ApprovalTests = older, language-agnostic.

**Q7: Snapshot anti-pattern?**
Using for business logic where explicit assertion would catch real bugs.

---

## 16. Best Practices

1. **Commit snapshots to git** — review like code
2. **Filter dynamic data** (timestamps, IDs)
3. **Small, focused snapshots** — readable diffs
4. **Explicit assertions for business logic**
5. **`--no-snapshot-update` in CI**
6. **Review every snapshot change**
7. **Don't snapshot huge outputs** — break down
8. **Parametrize for variants**
9. **Use type matchers** for non-deterministic structure
10. **Combine with explicit tests** — defense in depth

---

## Related
- [[01_pytest_advanced]]
- [[03_mutation_testing]]
- [[08_fastapi_testing_patterns]]
