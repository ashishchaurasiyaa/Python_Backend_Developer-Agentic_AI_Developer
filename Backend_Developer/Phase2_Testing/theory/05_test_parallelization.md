# Test Parallelization

> **Interview angle:** "1500 tests take 8 minutes. CI slow. Parallelize?"

---

## 1. Why Parallelize?

Test suite growth:
- 100 tests: 30 sec, no problem
- 1000 tests: 5 min, annoying
- 10000 tests: 50 min, **CI bottleneck**

PR feedback loop matters. Slow tests = developers skip CI, batch commits, lose velocity.

**Parallelization:** Split tests across N processes/workers.

---

## 2. pytest-xdist — The Tool

```bash
pip install pytest-xdist
```

### Basic usage
```bash
pytest -n 4              # 4 parallel workers
pytest -n auto           # = CPU count
pytest -n logical        # logical CPU cores
```

**Each worker = separate Python process** (avoids GIL).

### Strategies
```bash
pytest -n 4 --dist=load          # default — distribute by file
pytest -n 4 --dist=loadscope     # by class (good for shared fixtures)
pytest -n 4 --dist=loadfile      # by file (very granular)
pytest -n 4 --dist=loadgroup     # by @pytest.mark.xdist_group
pytest -n 4 --dist=worksteal     # work-stealing (best balance)
```

### Recommended: `worksteal`
```bash
pytest -n auto --dist=worksteal
# Workers pull tests from queue as they finish — best CPU utilization
```

---

## 3. The Isolation Problem

Parallel tests can interfere if they share:
- **Database** — same row, same table
- **Files** — same `/tmp/output.txt`
- **Network ports** — port 8000 already bound
- **Mocked globals** — `patch.object(...)` not thread-safe across processes? (each process has own state, but shared resources problematic)
- **Order-dependent state**

**Symptom:** Tests pass in isolation, fail in parallel (or randomly).

---

## 4. Database Isolation Strategies

### Strategy 1: One DB per worker
Each worker gets its own DB schema.

```python
# conftest.py
import os
import pytest

@pytest.fixture(scope="session")
def database_url():
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "master")
    return f"postgresql://user:pass@localhost/testdb_{worker_id}"

@pytest.fixture(scope="session", autouse=True)
def setup_db(database_url):
    create_database(database_url)
    yield
    drop_database(database_url)
```

### Strategy 2: One schema per worker
```python
@pytest.fixture(scope="session", autouse=True)
def db_schema():
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "default")
    schema = f"test_{worker_id}"
    await conn.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    await conn.execute(f"SET search_path TO {schema}")
    yield schema
    await conn.execute(f"DROP SCHEMA {schema} CASCADE")
```

### Strategy 3: Transactional rollback (single DB, fastest)
```python
@pytest.fixture
def db_session():
    """Each test runs in transaction, rolled back at end."""
    connection = engine.connect()
    trans = connection.begin()
    session = Session(bind=connection)
    yield session
    session.close()
    trans.rollback()
    connection.close()
```

⚠️ Doesn't work if test code uses its own transactions.

### Strategy 4: Random table names
```python
@pytest.fixture
def temp_table():
    name = f"tmp_{uuid.uuid4().hex[:8]}"
    db.execute(f"CREATE TABLE {name} (...)")
    yield name
    db.execute(f"DROP TABLE {name}")
```

---

## 5. Port Conflicts

```python
# ❌ Bad — hardcoded port, parallel tests conflict
def test_server():
    app.run(port=8000)

# ✅ Good — pick free port
import socket
def free_port():
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]

@pytest.fixture
def server_port():
    return free_port()
```

---

## 6. File Conflicts

```python
# ❌ Bad
def test_writes_to_file():
    with open("/tmp/output.txt", "w") as f:
        f.write("test")

# ✅ Use tmp_path fixture (per-test temp dir)
def test_writes_to_file(tmp_path):
    output = tmp_path / "output.txt"
    output.write_text("test")
```

### Worker-scoped temp dir
```python
@pytest.fixture(scope="session")
def worker_tmp_path(tmpdir_factory):
    return tmpdir_factory.mktemp("worker_data")
```

---

## 7. Grouping Tests (loadgroup)

Run related tests on same worker (share expensive setup):

```python
@pytest.mark.xdist_group(name="heavy_setup")
def test_a():
    ...

@pytest.mark.xdist_group(name="heavy_setup")
def test_b():
    ...
# Run together on same worker

pytest -n 4 --dist=loadgroup
```

---

## 8. Test Ordering

Parallel = random order. Watch for:

### Order-dependent tests (BAD)
```python
def test_step1():
    create_user()    # mutates global state

def test_step2():
    delete_user()    # depends on step1
```

**Fix:** Use fixtures to set up state per test. Don't depend on order.

### Find order issues
```bash
pytest --tb=short -v -p no:randomly       # check sequential
pip install pytest-randomly
pytest -p randomly                          # randomize order
```

If tests pass sequential but fail random → order dependency.

---

## 9. Coverage with Parallelization

```bash
pip install pytest-cov coverage

# Parallel coverage collection
pytest -n auto --cov=myapp --cov-report=html

# coverage merges from all workers automatically
```

### `.coveragerc`
```ini
[run]
parallel = true
branch = true
concurrency = multiprocessing
```

---

## 10. CI Configuration

### GitHub Actions
```yaml
test:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with: { python-version: '3.12' }

    - run: pip install -e ".[test]"

    - name: Test in parallel
      run: pytest -n auto --dist=worksteal -v

    - name: Coverage
      run: pytest -n auto --cov=myapp --cov-report=xml
```

### Matrix strategy (split across runners)
```yaml
test:
  strategy:
    matrix:
      group: [1, 2, 3, 4]   # 4 parallel runners
  steps:
    - run: pytest tests/ --num-shards=4 --shard-id=${{ matrix.group }}
```

For very large suites, combine: xdist + matrix.

---

## 11. Test Sharding (different from parallel)

`pytest-split` divides tests across CI runners:
```bash
pip install pytest-split

# Each runner: pytest --splits=4 --group=$N
pytest --splits=4 --group=1   # runner 1
pytest --splits=4 --group=2   # runner 2
# ...

# Better: based on timing data
pytest --splits=4 --group=1 --durations-path=.test_durations
```

`pytest-split` balances by past test duration.

---

## 12. Optimizing Test Speed (before parallelizing)

Parallelize last. First, eliminate slow tests:

### 1. Mark slow tests
```python
@pytest.mark.slow
def test_full_e2e():
    ...

# Run fast tests in PR, slow tests nightly
pytest -m "not slow"
```

### 2. Use mocks for expensive operations
```python
# ❌ Real HTTP call (1-5s each test)
def test_api():
    response = requests.get("https://example.com")

# ✅ Mock (microseconds)
def test_api(mocker):
    mocker.patch("requests.get").return_value.json.return_value = {"ok": True}
```

### 3. Session-scoped fixtures
```python
# ❌ DB created per test (slow)
@pytest.fixture
def db():
    return create_db()

# ✅ Once per test session
@pytest.fixture(scope="session")
def db():
    return create_db()
```

### 4. SQLite for test DB
SQLite in-memory = very fast. Even faster: `:memory:`.

```python
DATABASE_URL = "sqlite:///:memory:"
```

(Only if your queries are SQLite-compatible.)

### 5. Skip imports / heavy modules
```python
# Skip importing huge ML lib in unit tests
def test_simple():
    import myapp.simple_module      # only what's needed
```

---

## 13. Debugging Parallel Tests

```bash
# Run single failing test sequentially
pytest -p no:xdist -v -s tests/test_failing.py::test_specific

# Check workers
pytest -n 4 --verbose
# [gw0] worker started
# [gw1] worker started
# ...

# See worker assignments
pytest -n 4 --tb=short -v
# tests/test_a.py::test_x PASSED [gw0]
# tests/test_b.py::test_y PASSED [gw1]
```

---

## 14. Common Pitfalls

### Pitfall 1: Shared mutable state
Module-level dicts, class attributes shared via patching break parallel.

### Pitfall 2: Random seed not isolated
```python
import random
random.seed(42)         # global state, affects other tests

# ✅ per-test
def test_x():
    rng = random.Random(42)
    rng.choice(...)
```

### Pitfall 3: Order-dependent tests
Cleanup not happening → polluted state for next test.

### Pitfall 4: Too many workers
`-n 32` on 4-core machine = thrashing, slower than `-n 4`.

### Pitfall 5: Forgot DB isolation
Tests trample each other's data, intermittent failures.

---

## 15. Real Performance Numbers

| Suite size | Sequential | -n 4 | -n auto |
|---|---|---|---|
| 100 tests | 10s | 4s | 3s |
| 1000 tests | 5min | 1.5min | 50s |
| 10000 tests | 50min | 15min | 8min |

**Diminishing returns above CPU count.**

---

## 16. Interview Questions

**Q1: pytest tests slow — kya karoge?**
1. Mark slow tests, skip in PR
2. Mock external calls
3. Use session-scoped fixtures
4. Parallelize with pytest-xdist

**Q2: pytest-xdist isolation problem?**
Shared DB, files, ports cause failures. Per-worker schema + tmp_path + dynamic ports.

**Q3: --dist strategies?**
load (file-based), worksteal (work-stealing, best), loadgroup (custom grouping), loadscope (class-based).

**Q4: Test sharding vs parallel?**
- Parallel (xdist): within single runner, multiple processes
- Sharding (pytest-split): across multiple CI runners
- Combine for best speed

**Q5: Order-dependent test detect?**
`pytest -p randomly` — if tests fail randomly, you have order dependency.

**Q6: Coverage with parallelization?**
`pytest-cov` + `concurrency = multiprocessing` in .coveragerc. Auto-merges.

**Q7: One-DB vs per-worker DB?**
Transactional rollback (fast, single DB) if all tests run in transaction. Otherwise per-worker schema for safety.

---

## 17. Best Practices

1. **Parallelize as last optimization** — fix slow tests first
2. **`pytest -n auto --dist=worksteal`** is the default
3. **Per-worker DB schema** for true isolation
4. **`tmp_path` fixture** for files
5. **Dynamic ports** for servers
6. **Mark slow tests** — run them less often
7. **Session-scoped fixtures** for expensive setup
8. **Detect order issues** with pytest-randomly
9. **Test sharding** across CI runners for large suites
10. **Monitor flaky tests** — likely parallelism issue

---

## Related
- [[01_pytest_advanced]]
- [[02_snapshot_testing]]
- [[03_mutation_testing]]
