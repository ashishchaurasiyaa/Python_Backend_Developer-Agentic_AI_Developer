"""
============================================================
SNAPSHOT TESTING — Practical
============================================================
Install:
    pip install syrupy pytest

Run:
    pytest 02_snapshot_testing.py                   # check snapshots
    pytest 02_snapshot_testing.py --snapshot-update # regenerate
"""
import pytest
import json
import re
from datetime import datetime, timezone
from dataclasses import dataclass


# ============================================================
# 1. BASIC SNAPSHOT TEST
# ============================================================
def test_basic_dict(snapshot):
    data = {"id": 1, "name": "Alice", "age": 30}
    assert data == snapshot


def test_list_response(snapshot):
    response = [
        {"id": 1, "name": "Alice"},
        {"id": 2, "name": "Bob"},
        {"id": 3, "name": "Carol"},
    ]
    assert response == snapshot


# ============================================================
# 2. EXCLUDING DYNAMIC FIELDS
# ============================================================
def make_user_response():
    return {
        "id": 1,
        "name": "Alice",
        "email": "a@x.com",
        "created_at": datetime.now(timezone.utc).isoformat(),  # changes!
        "last_login": datetime.now(timezone.utc).isoformat(),
    }


def test_user_response_excludes_timestamps(snapshot):
    """Use syrupy's exclude filter for dynamic fields."""
    try:
        from syrupy.filters import props
        response = make_user_response()
        assert response == snapshot(exclude=props("created_at", "last_login"))
    except ImportError:
        pytest.skip("syrupy not installed")


# ============================================================
# 3. TYPE MATCHING (for non-deterministic structure)
# ============================================================
def test_user_with_dynamic_uuid(snapshot):
    """Check structure but not exact values for some fields."""
    try:
        from syrupy.matchers import path_type
        import uuid

        response = {
            "request_id": str(uuid.uuid4()),
            "user": {"id": 42, "name": "Alice"},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        matcher = path_type({
            "request_id": (str,),    # just check it's a string
            "timestamp": (str,),
        })
        assert response == snapshot(matcher=matcher)
    except ImportError:
        pytest.skip("syrupy not installed")


# ============================================================
# 4. NORMALIZE BEFORE SNAPSHOT
# ============================================================
TIMESTAMP_RE = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[+-]\d{2}:\d{2}|Z)?')
UUID_RE = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')


def normalize(text: str) -> str:
    """Replace dynamic patterns with placeholders."""
    text = TIMESTAMP_RE.sub("<TIMESTAMP>", text)
    text = UUID_RE.sub("<UUID>", text)
    return text


def test_log_output(snapshot):
    log_text = f"""
    [2024-05-24T10:30:45Z] INFO Request abc-123-def-456-7890-abcdef12345g started
    [2024-05-24T10:30:46Z] INFO Request abc-123-def-456-7890-abcdef12345g completed
    """
    assert normalize(log_text) == snapshot


# ============================================================
# 5. SQL QUERY SNAPSHOTS
# ============================================================
SQL_TEST = '''
def test_user_query_sql(snapshot):
    """Detect unintended ORM changes."""
    from sqlalchemy.dialects import postgresql
    from myapp.models import User

    query = User.query.filter(User.active == True).order_by(User.id).limit(10)
    sql = str(query.statement.compile(
        dialect=postgresql.dialect(),
        compile_kwargs={"literal_binds": True},
    ))
    assert sql == snapshot

# Snapshot:
# SELECT users.id, users.name FROM users WHERE users.active = true ORDER BY users.id LIMIT 10
'''


# ============================================================
# 6. HTML / TEMPLATE SNAPSHOTS
# ============================================================
HTML_TEST = '''
def test_email_template(snapshot):
    """Render template and snapshot output."""
    from jinja2 import Template

    template = Template("""
    <h1>Hello {{ name }}!</h1>
    <p>Welcome to {{ app_name }}.</p>
    """)
    html = template.render(name="Alice", app_name="MyApp")
    assert html == snapshot

# Snapshot stored as file, easy to review diff in PR
'''


# ============================================================
# 7. API RESPONSE SNAPSHOTS (FastAPI)
# ============================================================
FASTAPI_TEST = '''
from fastapi.testclient import TestClient
from myapp.main import app
from syrupy.filters import props

client = TestClient(app)

def test_get_user(snapshot):
    response = client.get("/users/1")
    assert response.json() == snapshot(
        exclude=props("created_at", "updated_at"),
    )

def test_list_users(snapshot):
    response = client.get("/users").json()
    # Just check structure of first item
    assert len(response) > 0
    assert response[0] == snapshot(exclude=props("created_at"))

def test_error_response(snapshot):
    response = client.get("/users/nonexistent")
    assert response.status_code == 404
    assert response.json() == snapshot
'''


# ============================================================
# 8. PARAMETRIZED SNAPSHOTS
# ============================================================
@pytest.mark.parametrize("user_role", ["admin", "user", "guest"])
def test_dashboard_by_role(user_role, snapshot):
    """Generates separate snapshot per role."""
    dashboard = {
        "user_role": user_role,
        "menu_items": {
            "admin": ["users", "settings", "billing", "logs"],
            "user": ["profile", "settings"],
            "guest": ["home"],
        }[user_role],
    }
    assert dashboard == snapshot


# ============================================================
# 9. STRUCTURED OUTPUT WITH CUSTOM SERIALIZER
# ============================================================
@dataclass
class Order:
    id: int
    items: list[str]
    total: float


def test_dataclass_snapshot(snapshot):
    order = Order(id=1, items=["apple", "banana"], total=10.50)
    assert order == snapshot


# ============================================================
# 10. JSON FORMAT SNAPSHOTS
# ============================================================
JSON_FORMAT = '''
from syrupy.extensions.json import JSONSnapshotExtension

@pytest.fixture
def json_snapshot(snapshot):
    return snapshot.with_defaults(extension_class=JSONSnapshotExtension)

def test_api_response_json(json_snapshot):
    """Snapshot stored as .json file (not .ambr)."""
    response = {"id": 1, "name": "Alice"}
    assert response == json_snapshot
'''


# ============================================================
# 11. PYTEST.INI CONFIG
# ============================================================
PYTEST_INI = """
# pytest.ini

[pytest]
testpaths = tests
addopts =
    --strict-markers
    --strict-config
    -ra

# Snapshot-related options
# In CI, add: --no-snapshot-update
"""


# ============================================================
# 12. CI WORKFLOW
# ============================================================
CI_WORKFLOW = """
# .github/workflows/test.yml

name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }

      - run: pip install -e ".[test]"

      # CRITICAL: --no-snapshot-update prevents auto-creating in CI
      - name: Run tests
        run: pytest --no-snapshot-update -v

      # If snapshot diff: fail with helpful message
      - name: Report snapshot diff
        if: failure()
        run: |
          echo "::warning::Snapshot test failed. Run 'pytest --snapshot-update' locally if intentional."
"""


# ============================================================
# 13. PRE-COMMIT HOOK
# ============================================================
PRE_COMMIT = """
# .pre-commit-config.yaml

repos:
  - repo: local
    hooks:
      - id: pytest-no-snapshot-update
        name: Block --snapshot-update in commits
        entry: |
          bash -c 'git diff --cached --name-only | xargs grep -l "snapshot-update" 2>/dev/null && exit 1 || exit 0'
        language: system
"""


# ============================================================
# 14. SNAPSHOT DIRECTORY STRUCTURE
# ============================================================
DIRECTORY_STRUCTURE = """
tests/
├── __snapshots__/                        # syrupy default
│   ├── test_users.ambr                    # amber format
│   └── test_api.json                      # JSON format
├── conftest.py
└── test_users.py

Or:
tests/
├── test_users.py
└── test_users/__snapshots__/
    └── test_user.ambr
"""


# ============================================================
# 15. UPDATE WORKFLOW
# ============================================================
UPDATE_WORKFLOW = """
# When making intentional output change:

# 1. Make code change
git checkout -b feat/add-email-to-user

# 2. Run tests → snapshots fail
pytest tests/test_users.py
# FAILED: test_get_user[snapshot]
# Expected: {"id": 1, "name": "Alice"}
# Actual:   {"id": 1, "name": "Alice", "email": "alice@example.com"}

# 3. Review diff CAREFULLY — is the new output correct?

# 4. If yes, regenerate snapshots
pytest tests/test_users.py --snapshot-update

# 5. Commit code + snapshot together
git add . __snapshots__/
git commit -m "Add email field to user response"
"""


# ============================================================
# 16. ALTERNATIVE: ApprovalTests
# ============================================================
APPROVAL_TESTS = '''
# pip install approvaltests

from approvaltests import verify
from approvaltests.reporters import ReporterByEnvironmentInTopFolder

def test_complex_report():
    """Save output to ./test_complex_report.received.txt
    First run: rename to .approved.txt to accept
    Future runs: compare to .approved.txt"""
    report = generate_complex_report()
    verify(str(report))
'''


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("SNAPSHOT TESTING — Practical")
    print("=" * 60)

    print("\nRun: pytest 02_snapshot_testing.py")
    print("To update: pytest 02_snapshot_testing.py --snapshot-update")

    print("\n--- SQL SNAPSHOT TEST ---")
    print(SQL_TEST)
    print("\n--- HTML SNAPSHOT ---")
    print(HTML_TEST)
    print("\n--- FASTAPI SNAPSHOTS ---")
    print(FASTAPI_TEST)
    print("\n--- JSON FORMAT ---")
    print(JSON_FORMAT)
    print("\n--- CI WORKFLOW ---")
    print(CI_WORKFLOW)
    print("\n--- UPDATE WORKFLOW ---")
    print(UPDATE_WORKFLOW)
    print("\n--- APPROVAL TESTS ALTERNATIVE ---")
    print(APPROVAL_TESTS)
