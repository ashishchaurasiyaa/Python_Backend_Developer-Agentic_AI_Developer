"""
============================================================
TEST PARALLELIZATION — Practical
============================================================
Install:
    pip install pytest-xdist pytest-randomly pytest-cov pytest-split

Run:
    pytest -n auto --dist=worksteal       # parallel
    pytest -p randomly                    # randomize order
    pytest --splits=4 --group=1           # sharding
"""


# ============================================================
# 1. CONFTEST.PY — per-worker setup
# ============================================================
CONFTEST = '''
# tests/conftest.py

import os
import socket
import pytest
import uuid
from pathlib import Path


def get_worker_id() -> str:
    """Returns unique worker ID under xdist, else 'master'."""
    return os.environ.get("PYTEST_XDIST_WORKER", "master")


def get_worker_count() -> int:
    return int(os.environ.get("PYTEST_XDIST_WORKER_COUNT", "1"))


def is_xdist_master() -> bool:
    """True if running under xdist coordinator (no actual tests run here)."""
    return os.environ.get("PYTEST_XDIST_WORKER") is None and \\
           os.environ.get("PYTEST_XDIST_TESTRUNUID") is not None


@pytest.fixture(scope="session")
def worker_id():
    return get_worker_id()


@pytest.fixture(scope="session")
def database_url(worker_id):
    """Per-worker test database URL."""
    base_url = os.environ.get("TEST_DATABASE_URL",
                              "postgresql://postgres:postgres@localhost:5432")
    return f"{base_url}/testdb_{worker_id}"


@pytest.fixture(scope="session", autouse=True)
def setup_database(database_url, worker_id):
    """Create per-worker test database."""
    import psycopg2
    from urllib.parse import urlparse

    parsed = urlparse(database_url)
    db_name = parsed.path.lstrip("/")
    admin_url = f"{parsed.scheme}://{parsed.netloc}/postgres"

    # Create
    conn = psycopg2.connect(admin_url)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(f"DROP DATABASE IF EXISTS {db_name}")
    cur.execute(f"CREATE DATABASE {db_name}")
    cur.close()
    conn.close()

    # Run migrations
    run_alembic_migrations(database_url)

    yield

    # Teardown
    conn = psycopg2.connect(admin_url)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(f"DROP DATABASE {db_name}")
    cur.close()
    conn.close()
'''


# ============================================================
# 2. PORT ISOLATION
# ============================================================
PORT_ISOLATION = '''
import socket

def free_port() -> int:
    """Get an unused TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


@pytest.fixture
def http_server():
    """Spin up test HTTP server on dynamic port."""
    port = free_port()
    from threading import Thread
    from http.server import HTTPServer, BaseHTTPRequestHandler

    server = HTTPServer(("", port), BaseHTTPRequestHandler)
    Thread(target=server.serve_forever, daemon=True).start()
    yield port
    server.shutdown()


def test_app_responds(http_server):
    import requests
    r = requests.get(f"http://localhost:{http_server}")
    assert r.status_code == 200
'''


# ============================================================
# 3. FILE / TMP_PATH ISOLATION
# ============================================================
FILE_ISOLATION = '''
def test_writes_file(tmp_path):
    """tmp_path is unique per test — safe in parallel."""
    output = tmp_path / "result.txt"
    output.write_text("hello")
    assert output.read_text() == "hello"


@pytest.fixture(scope="session")
def session_tmp_path(tmp_path_factory):
    """Shared temp dir for an entire test session (per worker)."""
    return tmp_path_factory.mktemp("session_data")
'''


# ============================================================
# 4. TRANSACTIONAL DB FIXTURE (single DB, rolled back)
# ============================================================
TRANSACTIONAL_DB = '''
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

@pytest.fixture(scope="session")
async def engine():
    engine = create_async_engine("postgresql+asyncpg://localhost/testdb")
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(engine):
    """Per-test transaction, rolled back after."""
    async with engine.connect() as conn:
        trans = await conn.begin()
        Session = sessionmaker(bind=conn, class_=AsyncSession, expire_on_commit=False)
        async with Session() as session:
            yield session
        await trans.rollback()
'''


# ============================================================
# 5. RANDOMIZATION SETUP
# ============================================================
RANDOMIZATION = '''
# pytest.ini

[pytest]
addopts =
    -p randomly       # randomize test order
    --tb=short
    --strict-markers

# Or via pyproject.toml
[tool.pytest.ini_options]
addopts = "-p randomly"

# Run with fixed seed for reproducibility
# pytest -p randomly --randomly-seed=42

# Find seed of failing run
# pytest -p randomly --randomly-seed=last
'''


# ============================================================
# 6. SHARED FIXTURES IN PARALLEL
# ============================================================
SHARED_FIXTURES = '''
# pytest-xdist provides "tmp_path_factory" that's session-scoped per worker
# But what if you need ONE setup across all workers?

# Option A: Run setup outside pytest
# In CI: alembic upgrade head BEFORE pytest -n auto

# Option B: Use file lock
import filelock

@pytest.fixture(scope="session")
def setup_once(tmp_path_factory):
    """Ensure setup runs exactly once across all workers."""
    root_tmp_dir = tmp_path_factory.getbasetemp().parent
    lock_file = root_tmp_dir / "setup.lock"

    with filelock.FileLock(str(lock_file)):
        flag_file = root_tmp_dir / "setup.done"
        if not flag_file.exists():
            # First worker — do the setup
            expensive_setup()
            flag_file.touch()
'''


# ============================================================
# 7. GROUPING TESTS (loadgroup)
# ============================================================
TEST_GROUPING = '''
# Tests that share expensive setup → put on same worker

@pytest.mark.xdist_group(name="ml_models")
class TestModelA:
    @pytest.fixture(scope="class")
    def model(self):
        return load_huge_model()    # 10s setup

    def test_predict_a(self, model):
        ...

    def test_predict_b(self, model):
        ...


@pytest.mark.xdist_group(name="ml_models")
class TestModelB:
    # Same group → same worker → reuses cache
    ...

# Run
# pytest -n 4 --dist=loadgroup
'''


# ============================================================
# 8. CI WITH XDIST + SHARDING
# ============================================================
CI_WORKFLOW = """
# .github/workflows/test.yml

name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        # 4 parallel CI runners, each runs 1/4 of tests
        shard: [1, 2, 3, 4]
    services:
      postgres:
        image: postgres:16
        env: { POSTGRES_PASSWORD: postgres }
        ports: ["5432:5432"]

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }

      - run: pip install -e ".[test]"

      - name: Cache test durations
        uses: actions/cache@v4
        with:
          path: .test_durations
          key: test-durations-${{ github.ref }}

      - name: Run tests (sharded + parallel within shard)
        run: |
          pytest \\
            --splits=4 \\
            --group=${{ matrix.shard }} \\
            -n auto \\
            --dist=worksteal \\
            --durations-path=.test_durations \\
            --cov=myapp \\
            --cov-report=xml

      - uses: codecov/codecov-action@v4

# 4 CI runners × N CPU each = ~16x parallelism
"""


# ============================================================
# 9. PYTEST-SPLIT (sharding by past durations)
# ============================================================
PYTEST_SPLIT = """
# pip install pytest-split

# Initial run: measure durations
pytest --store-durations
# Stores .test_durations file

# Subsequent runs: split based on duration
pytest --splits=4 --group=1   # 25% of tests, balanced by time
pytest --splits=4 --group=2
pytest --splits=4 --group=3
pytest --splits=4 --group=4

# This gives much better balance than naive splitting
"""


# ============================================================
# 10. COVERAGE WITH PARALLELIZATION
# ============================================================
COVERAGE_CONFIG = """
# .coveragerc

[run]
parallel = true
branch = true
source = myapp
concurrency =
    thread
    multiprocessing

[report]
exclude_lines =
    pragma: no cover
    if TYPE_CHECKING:
    raise NotImplementedError
fail_under = 80
show_missing = true


# Run:
pytest -n auto --cov=myapp --cov-report=html --cov-report=xml
# Auto-merges coverage from all workers
"""


# ============================================================
# 11. DEBUGGING PARALLEL FAILURES
# ============================================================
DEBUG_PATTERNS = """
# 1. Reproduce in isolation
pytest -p no:xdist -v -s tests/test_failing.py::test_specific

# 2. Try with random order disabled
pytest -p no:randomly -n auto

# 3. Single worker — is it parallelism or order?
pytest -n 1 tests/

# 4. Show worker ID per test
pytest -n 4 --tb=short -v
# tests/test_a.py::test_x PASSED [gw0]
# tests/test_b.py::test_y PASSED [gw1]

# 5. Set seed for reproducibility
pytest -p randomly --randomly-seed=42

# 6. Bisect — find conflicting tests
# Group A passes, Group B passes, A+B together fails → conflict between them
pytest tests/group_a/
pytest tests/group_b/
pytest tests/group_a/ tests/group_b/    # if fails → find which tests conflict
"""


# ============================================================
# 12. PERFORMANCE COMPARISON
# ============================================================
PERFORMANCE_DEMO = '''
import time
import subprocess

def benchmark(args):
    start = time.time()
    subprocess.run(["pytest", "tests/"] + args, check=True)
    return time.time() - start

results = {
    "sequential":   benchmark([]),
    "n=2":          benchmark(["-n", "2"]),
    "n=4":          benchmark(["-n", "4"]),
    "n=auto":       benchmark(["-n", "auto"]),
    "worksteal":    benchmark(["-n", "auto", "--dist=worksteal"]),
}

for name, t in results.items():
    speedup = results["sequential"] / t
    print(f"{name:12s}: {t:.1f}s  ({speedup:.1f}x speedup)")

# Typical output:
# sequential:  120.0s  (1.0x)
# n=2:          65.0s  (1.8x)
# n=4:          35.0s  (3.4x)
# n=auto:       28.0s  (4.3x)   on 8 CPU
# worksteal:    25.0s  (4.8x)   best balance
'''


# ============================================================
# 13. ANTI-PATTERNS
# ============================================================
ANTI_PATTERNS = """
================================================================
TESTS THAT BREAK PARALLEL
================================================================

# ❌ 1. Global state mutation
counter = 0
def test_one(): global counter; counter += 1
def test_two(): assert counter == 1   # depends on test_one running first

# ❌ 2. Singleton pattern with caching
class Registry:
    _instance = None
    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
# Across processes: each worker has own instance — fine
# Within process with threads: race condition

# ❌ 3. Shared file
def test_log():
    with open("test.log", "a") as f:
        f.write("test ran")
# Multiple workers append → garbled

# ❌ 4. Hardcoded ports/paths
def test_server():
    server.bind(("", 8000))    # port conflict

# ❌ 5. Order-dependent setup
@pytest.fixture(scope="module")
def shared_state():
    return {"counter": 0}

def test_a(shared_state):
    shared_state["counter"] += 1   # mutates

def test_b(shared_state):
    assert shared_state["counter"] == 1   # depends on test_a
================================================================
"""


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("TEST PARALLELIZATION")
    print("=" * 60)

    print("\nQuick start:")
    print("  pip install pytest-xdist pytest-randomly")
    print("  pytest -n auto --dist=worksteal")

    print("\n--- CONFTEST FOR PARALLELIZATION ---")
    print(CONFTEST)
    print("\n--- PORT ISOLATION ---")
    print(PORT_ISOLATION)
    print("\n--- FILE ISOLATION ---")
    print(FILE_ISOLATION)
    print("\n--- TRANSACTIONAL DB ---")
    print(TRANSACTIONAL_DB)
    print("\n--- RANDOMIZATION ---")
    print(RANDOMIZATION)
    print("\n--- SHARED FIXTURES ---")
    print(SHARED_FIXTURES)
    print("\n--- TEST GROUPING ---")
    print(TEST_GROUPING)
    print("\n--- CI WORKFLOW ---")
    print(CI_WORKFLOW)
    print("\n--- PYTEST-SPLIT ---")
    print(PYTEST_SPLIT)
    print("\n--- COVERAGE CONFIG ---")
    print(COVERAGE_CONFIG)
    print("\n--- DEBUG PATTERNS ---")
    print(DEBUG_PATTERNS)
    print(ANTI_PATTERNS)
