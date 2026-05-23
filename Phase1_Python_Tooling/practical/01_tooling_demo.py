"""
Phase1_Python_Tooling — Tooling Demo
======================================
Topics covered:
  1. pyproject.toml structure (PEP 518/517)
  2. Poetry commands reference
  3. uv — ultra-fast package manager
  4. Ruff lint rules (before/after examples)
  5. mypy type checking patterns
  6. pre-commit hooks configuration
  7. Python packaging structure

Run:
  python 01_tooling_demo.py
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: pyproject.toml
# INTERVIEW: Single config file replacing setup.py + setup.cfg + requirements.txt
# ─────────────────────────────────────────────────────────────────────────────

PYPROJECT_TOML = """\
# pyproject.toml — Modern Python project config (PEP 518/621)
# INTERVIEW: Replaces setup.py + setup.cfg + requirements.txt

[build-system]
requires      = ["poetry-core>=1.0.0"]   # or "hatchling", "flit_core"
build-backend = "poetry.core.masonry.api"

[tool.poetry]
name        = "my-fastapi-app"
version     = "0.1.0"
description = "Production FastAPI application"
authors     = ["Alice <alice@example.com>"]
readme      = "README.md"
packages    = [{include = "app"}]

[tool.poetry.dependencies]
python      = "^3.12"
fastapi     = "^0.115.0"
uvicorn     = {extras = ["standard"], version = "^0.32.0"}
sqlalchemy  = {extras = ["asyncio"], version = "^2.0"}
pydantic    = "^2.10"
redis       = "^5.2"

# INTERVIEW: Dependency groups = dev vs prod separation
[tool.poetry.group.dev.dependencies]
pytest       = "^8.0"
pytest-asyncio = "^0.24"
httpx        = "^0.28"   # for TestClient
ruff         = "^0.8"
mypy         = "^1.13"
pre-commit   = "^4.0"

[tool.poetry.group.test.dependencies]
pytest-cov   = "^6.0"
factory-boy  = "^3.3"

# ─────────────────────────────────────────────────────────────────
# Ruff Configuration
# INTERVIEW: Ruff = linter + formatter (replaces flake8+isort+black)
# ─────────────────────────────────────────────────────────────────
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes
    "I",   # isort
    "B",   # flake8-bugbear (common bugs)
    "C4",  # flake8-comprehensions
    "UP",  # pyupgrade (modernize syntax)
    "S",   # bandit security checks
    "ANN", # type annotations
]
ignore = [
    "ANN101",  # missing self annotation
    "S101",    # allow assert in tests
]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101", "ANN"]   # ignore assert + annotations in tests

[tool.ruff.format]
quote-style = "double"
indent-style = "space"

# ─────────────────────────────────────────────────────────────────
# mypy Configuration
# INTERVIEW: Static type checking
# ─────────────────────────────────────────────────────────────────
[tool.mypy]
python_version         = "3.12"
strict                 = true     # enables all strict checks
warn_return_any        = true
warn_unused_ignores    = true
disallow_untyped_defs  = true
ignore_missing_imports = true     # for packages without stubs

# Per-module overrides
[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false

# ─────────────────────────────────────────────────────────────────
# pytest Configuration
# ─────────────────────────────────────────────────────────────────
[tool.pytest.ini_options]
asyncio_mode    = "auto"
testpaths       = ["tests"]
addopts         = "-v --cov=app --cov-report=term-missing"
filterwarnings  = ["error", "ignore::DeprecationWarning"]
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Poetry vs uv Commands
# INTERVIEW: uv = 10-100x faster than pip/poetry (written in Rust)
# ─────────────────────────────────────────────────────────────────────────────

COMMANDS = {
    "Poetry": {
        "Init project":          "poetry new myproject  OR  poetry init",
        "Install all deps":      "poetry install",
        "Install prod only":     "poetry install --only main",
        "Add dependency":        "poetry add fastapi",
        "Add dev dependency":    "poetry add --group dev pytest",
        "Remove dependency":     "poetry remove requests",
        "Update deps":           "poetry update",
        "Run in venv":           "poetry run python app.py",
        "Shell into venv":       "poetry shell",
        "Export requirements":   "poetry export -f requirements.txt > requirements.txt",
        "Publish to PyPI":       "poetry publish --build",
        "Show dep tree":         "poetry show --tree",
        "Lock file":             "poetry.lock  (commit to git!)",
    },
    "uv (ultra-fast)": {
        "Init project":          "uv init myproject",
        "Create venv":           "uv venv",
        "Install deps":          "uv sync",
        "Add dependency":        "uv add fastapi",
        "Add dev dependency":    "uv add --dev pytest",
        "Remove dependency":     "uv remove requests",
        "Run script":            "uv run python app.py",
        "Run tool (no install)": "uvx ruff check .",
        "Lock file":             "uv.lock",
        "Why uv is fast":        "Written in Rust, parallel downloads, no subprocess",
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Ruff Lint Rules — Before/After Examples
# INTERVIEW: Common issues Ruff catches
# ─────────────────────────────────────────────────────────────────────────────

RUFF_EXAMPLES = [
    {
        "rule": "F401 — Unused import",
        "bad":  "import os\nimport sys\n\ndef foo(): return 42   # os not used",
        "good": "import sys\n\ndef foo(): return 42",
    },
    {
        "rule": "B006 — Mutable default argument",
        "bad":  "def add_item(item, lst=[]):\n    lst.append(item)\n    return lst",
        "good": "def add_item(item, lst=None):\n    if lst is None: lst = []\n    lst.append(item)\n    return lst",
    },
    {
        "rule": "UP006 — Use list/dict instead of List/Dict (Python 3.9+)",
        "bad":  "from typing import List, Dict\ndef foo(x: List[str]) -> Dict[str, int]: ...",
        "good": "def foo(x: list[str]) -> dict[str, int]: ...",
    },
    {
        "rule": "C401 — Use set() comprehension",
        "bad":  "result = set([x for x in items if x > 0])",
        "good": "result = {x for x in items if x > 0}",
    },
    {
        "rule": "S105 — Hardcoded password",
        "bad":  'password = "mysecret123"',
        "good": 'password = os.environ["DB_PASSWORD"]',
    },
    {
        "rule": "E501 — Line too long",
        "bad":  "result = some_very_long_function_name(argument_one, argument_two, argument_three, argument_four)",
        "good": "result = some_very_long_function_name(\n    argument_one, argument_two,\n    argument_three, argument_four\n)",
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: mypy — Type Checking Examples
# INTERVIEW: Common mypy errors and fixes
# ─────────────────────────────────────────────────────────────────────────────

MYPY_EXAMPLES = [
    {
        "issue": "Function missing return type",
        "bad":   "def greet(name):           # mypy: missing return type\n    return f'Hello {name}'",
        "good":  "def greet(name: str) -> str:\n    return f'Hello {name}'",
    },
    {
        "issue": "Optional not handled",
        "bad":   "def get_user(id: int) -> str:\n    user = db.get(id)  # could be None!\n    return user.name   # mypy error: None has no attr 'name'",
        "good":  "def get_user(id: int) -> str | None:\n    user = db.get(id)\n    return user.name if user else None",
    },
    {
        "issue": "Any type suppresses checking",
        "bad":   "from typing import Any\ndef process(data: Any) -> Any:  # loses type safety",
        "good":  "from typing import TypeVar\nT = TypeVar('T')\ndef process(data: T) -> T:  # generic, type-safe",
    },
    {
        "issue": "# type: ignore — use sparingly",
        "bad":   "result = third_party_lib.do_thing()  # type: ignore  (suppresses all checks)",
        "good":  "result: str = third_party_lib.do_thing()  # type: ignore[no-untyped-call]  (specific ignore)",
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: pre-commit Configuration
# INTERVIEW: Auto-run checks before every git commit
# ─────────────────────────────────────────────────────────────────────────────

PRE_COMMIT_CONFIG = """\
# .pre-commit-config.yaml
# Setup: pip install pre-commit && pre-commit install
# Run all: pre-commit run --all-files

repos:
  # Ruff: lint + format
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.0
    hooks:
      - id: ruff
        args: [--fix]         # auto-fix fixable issues
      - id: ruff-format       # black-compatible formatting

  # mypy: type checking
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.13.0
    hooks:
      - id: mypy
        additional_dependencies: [pydantic, fastapi]

  # Standard checks
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-toml
      - id: debug-statements     # no breakpoint() in commits
      - id: check-merge-conflict
      - id: detect-private-key   # CRITICAL: no keys in code!

  # Bandit: security checks
  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.10
    hooks:
      - id: bandit
        args: ["-c", "pyproject.toml"]
        exclude: tests/
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Python Package Structure
# INTERVIEW: Library vs Application layout
# ─────────────────────────────────────────────────────────────────────────────

PACKAGE_STRUCTURE = """\
# ── FastAPI Application Layout ──────────────────────────────────
myapp/
├── pyproject.toml           # Project config + deps
├── README.md
├── .pre-commit-config.yaml
├── .gitignore               # .env, .venv, __pycache__, *.pyc
├── Dockerfile
├── docker-compose.yml
│
├── app/                     # Main application package
│   ├── __init__.py
│   ├── main.py              # FastAPI app, lifespan, middleware
│   ├── config.py            # pydantic-settings Settings
│   │
│   ├── api/                 # Route handlers
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── users.py
│   │   └── deps.py          # Shared dependencies (get_db, get_current_user)
│   │
│   ├── models/              # SQLAlchemy models
│   │   ├── __init__.py
│   │   └── user.py
│   │
│   ├── schemas/             # Pydantic request/response schemas
│   │   └── user.py
│   │
│   ├── services/            # Business logic layer
│   │   └── user_service.py
│   │
│   └── db/
│       ├── session.py       # AsyncSession setup
│       └── migrations/      # Alembic migrations
│
└── tests/
    ├── conftest.py          # Fixtures: test db, client
    ├── test_users.py
    └── test_auth.py

# ── Reusable Library Layout ─────────────────────────────────────
mylib/
├── pyproject.toml
├── src/
│   └── mylib/              # src layout (PEP 517 recommended)
│       ├── __init__.py
│       └── core.py
├── tests/
└── docs/
"""


# ─────────────────────────────────────────────────────────────────────────────
# Main Demo
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("PYTHON TOOLING REFERENCE")
    print("=" * 60)

    print("\n[1] pyproject.toml — Key Sections:")
    sections = {
        "[build-system]":           "Specifies build backend (poetry-core/hatchling)",
        "[tool.poetry.dependencies]": "Production deps with version constraints",
        "[tool.poetry.group.dev]":   "Dev-only deps (pytest, ruff, mypy)",
        "[tool.ruff.lint]":          "Lint rules: E,W,F,I,B,C4,UP,S,ANN",
        "[tool.mypy]":               "strict=true enables all strict type checks",
        "[tool.pytest.ini_options]": "asyncio_mode=auto, coverage config",
    }
    for section, desc in sections.items():
        print(f"  {section:<40}: {desc}")

    print("\n[2] Poetry vs uv Quick Reference:")
    for tool, cmds in COMMANDS.items():
        print(f"\n  {tool}:")
        for action, cmd in list(cmds.items())[:5]:
            print(f"    {action:<25}: {cmd}")

    print("\n[3] Ruff Lint Examples:")
    for ex in RUFF_EXAMPLES[:3]:
        print(f"\n  Rule: {ex['rule']}")
        print(f"  BAD:  {ex['bad'].splitlines()[0]}")
        print(f"  GOOD: {ex['good'].splitlines()[0]}")

    print("\n[4] mypy Common Issues:")
    for ex in MYPY_EXAMPLES[:2]:
        print(f"\n  Issue: {ex['issue']}")
        print(f"  BAD:   {ex['bad'].splitlines()[0]}")
        print(f"  GOOD:  {ex['good'].splitlines()[0]}")

    print("\n[5] pre-commit Hooks Running Order:")
    hooks = ["trailing-whitespace", "detect-private-key", "check-merge-conflict",
             "debug-statements", "ruff (lint + fix)", "ruff-format", "mypy", "bandit"]
    for i, h in enumerate(hooks, 1):
        print(f"  {i}. {h}")

    print("\n" + "=" * 60)
    print("INTERVIEW QUICK ANSWERS:")
    print("  Q: Poetry vs pip?")
    print("     Poetry = lock file + dep groups + virtual env + publish")
    print("  Q: uv vs Poetry?")
    print("     uv = 10-100x faster (Rust), pip-compatible, drop-in")
    print("  Q: Ruff vs flake8+black+isort?")
    print("     Ruff replaces all 3 in one tool, 100x faster (Rust)")
    print("  Q: Why pre-commit?")
    print("     Never commit bad code — runs checks before every git commit")
    print("  Q: strict=true in mypy?")
    print("     Enables: disallow_untyped_defs, warn_return_any, check_untyped_defs")
    print("=" * 60)


if __name__ == "__main__":
    main()
