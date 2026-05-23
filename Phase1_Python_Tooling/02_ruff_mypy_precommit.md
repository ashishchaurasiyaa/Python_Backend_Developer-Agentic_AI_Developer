# Ruff, Mypy & Pre-commit — Code Quality Tools

---

# PART 1 — THEORY (Deep Concepts & Internals)

---

## 1.1 Why Code Quality Tools?

### The Problem Without Tooling

```python
# Without tools — this ships to production:
def calculate(x,y,z):
    import os           # unused import
    result=x+y         # missing spaces
    if result == None: # should use `is None`
    	return z        # mixed tabs/spaces
    return result

# Type error caught only at runtime:
calculate("10", 20, 30)  # TypeError: can only concatenate str
```

**What each tool catches:**

| Tool | Category | What it catches |
|------|----------|----------------|
| Ruff (linter) | Style + bugs | unused imports, undefined names, style violations, anti-patterns |
| Ruff (formatter) | Style | indentation, line length, quotes, trailing commas |
| mypy | Types | type mismatches, missing returns, wrong arg types |
| pre-commit | Process | runs all checks before git commit |

---

## 1.2 Ruff — Architecture & Internals

### What is Ruff?

```
Ruff = Python linter + formatter written in Rust
     = Replaces: flake8 + black + isort + pyupgrade + many plugins
     = 10-100x faster than Python-based equivalents

Why Rust?
  - Compiled, no Python overhead
  - Parallel file processing
  - Efficient AST traversal with custom Rust parser
  - No subprocess calls for each file
```

### Ruff's Rule System — Categories

```
Rule codes and what they check:

E / W  → pycodestyle (PEP 8 style)
         E501: line too long, E302: expected 2 blank lines, W291: trailing whitespace

F      → pyflakes (logic errors)
         F401: unused import, F811: redefined unused name, F841: local variable assigned never used

I      → isort (import ordering)
         I001: import block unsorted

N      → pep8-naming (naming conventions)
         N801: class names should use CapWords, N802: function names should be lowercase

UP     → pyupgrade (modern Python syntax)
         UP006: use list instead of List (Python 3.9+)
         UP007: use X | Y instead of Optional[X] (Python 3.10+)

B      → flake8-bugbear (likely bugs)
         B006: mutable default argument, B007: loop variable overrides, B023: function in loop

C4     → flake8-comprehensions (simpler comprehensions)
         C401: rewrite as set comprehension, C411: unnecessary list call

SIM    → flake8-simplify
         SIM102: use single if instead of nested, SIM117: merge with statement

TCH    → flake8-type-checking
         TCH001: move import into TYPE_CHECKING block

ANN    → flake8-annotations (type annotations required)
         ANN001: missing type annotation for function argument

S      → flake8-bandit (security)
         S101: use of assert, S105: hardcoded password, S608: SQL injection risk

D      → pydocstyle (docstring conventions)
         D100: missing docstring in public module

RUF    → Ruff-specific rules
         RUF100: unused noqa directive
```

### Ruff vs Black vs flake8

```
Before Ruff (old setup):
  flake8 → linting (runs python subprocess per file)
  black  → formatting (separate tool, slow)
  isort  → import sorting (yet another tool)
  pyupgrade → modernize syntax (another pass)
  
  CI time: 4 tools × Python overhead × 1000 files = 2-5 minutes

With Ruff:
  ruff check --fix .   → lint + fix (all 4 tools combined)
  ruff format .        → format (replaces black)
  
  CI time: 1 tool × Rust speed × 1000 files = 2-5 seconds
```

### Ruff's Two Modes

```
ruff check   → Linter mode
  - Reads AST (Abstract Syntax Tree)
  - Applies rule checks
  - Reports violations with file:line:col codes
  - --fix flag: auto-fixes fixable violations

ruff format  → Formatter mode
  - Like black: opinionated, minimal config
  - Reads tokens + CST (Concrete Syntax Tree)
  - Rewrites whitespace, quotes, trailing commas
  - Idempotent: format(format(x)) == format(x)
```

---

## 1.3 mypy — Type Checking Internals

### How mypy Works

```
Source code (.py)
    ↓
mypy parser → AST
    ↓
Type inference engine
  - Infers types from assignments, return types, function signatures
  - Reads .pyi stub files (type stubs) for C extensions
  - Checks generic types (List[int], Dict[str, User])
    ↓
Type checker
  - Unifies types (Hindley-Milner algorithm subset)
  - Checks compatibility (is str assignable to int? No.)
  - Reports errors with file:line
```

### mypy Strictness Levels

```
Level 1: Default (lenient)
  mypy app/
  → Only checks explicitly annotated code
  → Unannotated functions: Any type (no checking)

Level 2: Moderate
  mypy --disallow-untyped-defs app/
  → Requires annotations on all function args + return types

Level 3: Strict (recommended for production)
  mypy --strict app/
  Enables all of:
    --disallow-untyped-defs        → All functions must have annotations
    --disallow-any-generics        → No bare List, Dict (must be List[str])
    --disallow-subclassing-any     → No subclassing Any
    --warn-return-any              → Warn when returning Any
    --warn-unused-ignores          → Warn on unnecessary # type: ignore
    --no-implicit-reexport         → Explicit re-exports needed
    --strict-equality              → Stricter comparison checks
```

### Type Stubs — How mypy Handles Third-party Libs

```
Problem: requests, SQLAlchemy written in Python but no annotations
Solution: .pyi stub files (type stubs)

Where mypy looks:
  1. Inline types in .py files (PEP 561: py.typed marker)
  2. .pyi stub files bundled with package
  3. typeshed (built-in stubs for stdlib + popular libs)
  4. types-* packages (stubs distributed separately)

Install stubs:
  pip install types-requests          # requests stubs
  pip install types-redis             # redis stubs
  pip install sqlalchemy[mypy]        # SQLAlchemy plugin

With ignore_missing_imports = true:
  → No error for packages without stubs
  → Those imports treated as Any
```

### mypy Plugins — SQLAlchemy, Pydantic

```python
# mypy.ini or pyproject.toml
[mypy]
plugins = ["sqlalchemy.ext.mypy.plugin", "pydantic.mypy"]

# Without pydantic plugin:
class User(BaseModel):
    name: str

user = User(name="Ashish")
reveal_type(user.name)  # Any  ← wrong!

# With pydantic plugin:
reveal_type(user.name)  # str  ← correct!
```

---

## 1.4 pre-commit — Hook Lifecycle

### How Git Hooks Work

```
git commit -m "fix bug"
    ↓
Git reads: .git/hooks/pre-commit  (if exists, executable)
    ↓
Runs the hook script
    ↓
Exit code 0 → commit proceeds
Exit code != 0 → commit BLOCKED, message shown
```

### pre-commit Framework Architecture

```
pre-commit install
    ↓
Creates: .git/hooks/pre-commit  (script that calls pre-commit run)

git commit
    ↓
.git/hooks/pre-commit runs
    ↓
pre-commit reads: .pre-commit-config.yaml
    ↓
For each hook:
  1. Downloads/caches the hook repo (in ~/.cache/pre-commit/)
  2. Creates isolated virtualenv for the hook
  3. Runs hook only on staged files (git diff --staged)
  4. If hook modifies files → re-stage + FAIL (user must re-commit)
  5. If hook exits non-zero → FAIL, show output

All hooks pass → git commit succeeds
```

### Hook Types

```
pre-commit  → Before commit message (most common: lint, format, type-check)
commit-msg  → Validate commit message format (conventional commits)
pre-push    → Before git push (run tests, expensive checks)
post-checkout → After git checkout (clean up, notify)
```

### pre-commit Caching

```
~/.cache/pre-commit/
  repo_hash_1/   ← Cloned hook repo + installed env (first run)
  repo_hash_2/
  ...

First run: slow (downloads + installs each hook)
Subsequent runs: fast (cache hit, just executes)
Update cache: pre-commit autoupdate (updates rev: sha)
```

---

## 1.5 CI Pipeline — Quality Gates

### Pipeline Stages for Python Projects

```
Push to PR
    ↓
Stage 1: FAST checks (2-5 seconds, Ruff)
  ruff check --no-fix .    → lint errors? fail
  ruff format --check .    → format drift? fail

Stage 2: TYPE CHECK (30s-2min, mypy)
  mypy --strict app/       → type errors? fail

Stage 3: TESTS (1-10min, pytest)
  pytest --cov=app --cov-fail-under=80  → tests fail or coverage too low? fail

Stage 4: SECURITY (optional, bandit)
  bandit -r app/           → security issues? warn or fail

Stage 5: BUILD (1-5min, Docker)
  docker build .           → build fails? fail

All pass → PR can be merged
```

### Fail Fast Principle

```
Ordered by speed: fastest checks first
  Ruff (2s) → mypy (30s) → pytest (5m) → Docker (3m)

If Ruff fails in 2s → skip mypy + pytest → fast feedback
If Ruff passes but mypy fails → skip pytest → save 5 minutes

Principle: short-circuit on first failure, ordered cheap→expensive
```

---

## 1.6 Configuration Hierarchy

```
Each tool reads config from pyproject.toml first, then own config file:

Ruff:   pyproject.toml [tool.ruff] → ruff.toml → .ruff.toml
mypy:   pyproject.toml [tool.mypy] → mypy.ini → setup.cfg
pytest: pyproject.toml [tool.pytest.ini_options] → pytest.ini → setup.cfg

Best practice: Put everything in pyproject.toml → single source of truth
```

---

# PART 2 — PRACTICAL (Complete Working Code & Commands)

---

## 2.1 Ruff — Complete Setup & Commands

```bash
# ===== INSTALL =====
pip install ruff
# OR with uv:
uv add --dev ruff
# OR with poetry:
poetry add --group dev ruff

# ===== LINTING =====
ruff check .                       # Check all Python files
ruff check app/ tests/             # Specific directories
ruff check --fix .                 # Auto-fix fixable issues
ruff check --fix --unsafe-fixes .  # Also apply "unsafe" fixes
ruff check --no-fix .              # CI mode: report only, never fix
ruff check --select F401 .         # Check only unused imports
ruff check --ignore E501 .         # Ignore specific rule
ruff check --output-format=json .  # Machine-readable output

# ===== FORMATTING =====
ruff format .                      # Format all files (like black)
ruff format --check .              # Check without modifying (CI)
ruff format --diff .               # Show what would change
ruff format app/main.py            # Format single file

# ===== COMBINED WORKFLOW =====
ruff check --fix . && ruff format .  # Fix issues + format
ruff check --no-fix . && ruff format --check .  # CI: check only

# ===== WATCH MODE =====
ruff check --watch .               # Re-run on file changes
```

---

## 2.2 Complete ruff.toml / pyproject.toml Config

```toml
# pyproject.toml → [tool.ruff] section
# OR: ruff.toml (standalone file)

[tool.ruff]
# Targets
line-length = 100
target-version = "py311"
src = ["src", "tests"]             # Source directories for import resolution
exclude = [
    ".git", ".venv", "__pycache__",
    "migrations/", "alembic/",
    "*.pyi",
]

[tool.ruff.lint]
# ===== ENABLED RULE SETS =====
select = [
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings
    "F",    # pyflakes (unused imports, undefined names)
    "I",    # isort (import ordering)
    "N",    # pep8-naming
    "UP",   # pyupgrade (modern Python)
    "B",    # flake8-bugbear (likely bugs)
    "C4",   # flake8-comprehensions
    "SIM",  # flake8-simplify
    "TCH",  # flake8-type-checking
    "ANN",  # flake8-annotations (require type hints)
    "S",    # flake8-bandit (security)
    "RUF",  # Ruff-specific rules
]

# ===== IGNORED RULES =====
ignore = [
    "E501",    # Line too long (handled by formatter)
    "ANN101",  # Missing type annotation for `self`
    "ANN102",  # Missing type annotation for `cls`
    "ANN401",  # Dynamically typed expressions (Any) ok
    "S101",    # assert OK in tests (see per-file below)
    "B008",    # FastAPI: function calls in default arguments
]

# ===== FIX BEHAVIOUR =====
fixable = ["ALL"]                  # Allow fixing all fixable rules
unfixable = ["F841"]               # Never auto-fix (assigned but never used — might be intentional)

# ===== PER-FILE OVERRIDES =====
[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = [
    "S101",    # assert is fine in pytest
    "ANN",     # Type annotations optional in tests
]
"migrations/**/*.py" = [
    "N999",    # Module names can be non-conventional in migrations
]
"__init__.py" = [
    "F401",    # Unused imports OK in __init__ (re-exports)
]

# ===== ISORT SETTINGS =====
[tool.ruff.lint.isort]
known-first-party = ["my_fastapi_service"]
known-third-party = ["fastapi", "pydantic", "sqlalchemy"]
force-sort-within-sections = true
split-on-trailing-comma = true

# ===== PYDOCSTYLE =====
[tool.ruff.lint.pydocstyle]
convention = "google"              # google / numpy / pep257

# ===== MCCABE COMPLEXITY =====
[tool.ruff.lint.mccabe]
max-complexity = 10                # Cyclomatic complexity limit

# ===== FORMATTER SETTINGS =====
[tool.ruff.format]
quote-style = "double"            # double / single
indent-style = "space"            # space / tab
skip-magic-trailing-comma = false # Respect trailing commas in collections
line-ending = "auto"              # auto / lf / crlf / cr
```

---

## 2.3 mypy — Complete Setup & Commands

```bash
# ===== INSTALL =====
pip install mypy
uv add --dev mypy
# With stubs for common packages:
pip install types-requests types-redis types-PyYAML

# ===== BASIC USAGE =====
mypy app/                          # Check all files in app/
mypy app/main.py                   # Single file
mypy --strict app/                 # Strict mode
mypy --ignore-missing-imports app/ # Ignore untyped packages

# ===== USEFUL FLAGS =====
mypy --show-error-codes app/       # Show rule codes (e.g., [return-value])
mypy --pretty app/                 # Formatted output with context
mypy --html-report htmlreport/ app/ # HTML report
mypy --no-error-summary app/       # No summary line at end

# ===== INCREMENTAL (FAST) MODE =====
mypy app/                          # First run: full analysis, creates .mypy_cache/
mypy app/                          # Second run: incremental (only changed files)
mypy --cache-dir /tmp/mypy app/   # Custom cache location
```

---

## 2.4 Complete mypy.ini / pyproject.toml Config

```toml
# pyproject.toml → [tool.mypy] section

[tool.mypy]
# ===== PYTHON VERSION =====
python_version = "3.11"

# ===== STRICTNESS =====
strict = true                      # Enables all strict checks below
# OR manually:
# disallow_untyped_defs = true     # All functions must have annotations
# disallow_any_generics = true     # No bare List, Dict
# warn_return_any = true           # Warn when returning Any
# warn_unused_ignores = true       # Warn on # type: ignore that aren't needed

# ===== IMPORTS =====
ignore_missing_imports = true      # Don't error on untyped packages
follow_imports = "normal"          # normal / silent / skip / error

# ===== PLUGINS =====
plugins = [
    "pydantic.mypy",               # Better Pydantic model checking
    "sqlalchemy.ext.mypy.plugin",  # SQLAlchemy column type inference
]

# ===== OUTPUT =====
pretty = true
show_error_codes = true            # [return-value], [arg-type], etc.
show_column_numbers = true
error_summary = false

# ===== CACHING =====
cache_dir = ".mypy_cache"

# ===== PER-MODULE OVERRIDES =====
[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false      # Tests don't need full annotations

[[tool.mypy.overrides]]
module = [
    "celery.*",
    "kombu.*",
    "aioredis.*",
]
ignore_missing_imports = true      # These packages have no stubs

[[tool.mypy.overrides]]
module = "migrations.*"
ignore_errors = true               # Skip alembic migration files

# ===== PYDANTIC PLUGIN CONFIG =====
[tool.pydantic-mypy]
init_forbid_extra = true
init_typed = true
warn_required_dynamic_aliases = true
```

---

## 2.5 Real mypy Patterns — Common Errors & Fixes

```python
from typing import Optional, Union
from collections.abc import Sequence

# ===== ERROR 1: Missing return type =====
# mypy: error: Function is missing a return type annotation
def get_user(user_id: int):          # WRONG
    return {"id": user_id}

def get_user(user_id: int) -> dict[str, int]:  # CORRECT
    return {"id": user_id}

# ===== ERROR 2: Incompatible types =====
def process(items: list[str]) -> None:
    items.append(42)                 # error: Argument 1 to "append" has incompatible type "int"

# ===== ERROR 3: Optional not handled =====
def get_name(user: dict[str, str]) -> str:
    return user.get("name")         # error: Return value expected "str" but got "str | None"

def get_name(user: dict[str, str]) -> str:
    name = user.get("name")
    if name is None:
        raise ValueError("No name")
    return name                     # CORRECT: narrowed to str

# ===== ERROR 4: TypeVar usage =====
from typing import TypeVar
T = TypeVar("T")

def first(items: list[T]) -> T:     # CORRECT: generic
    return items[0]

# ===== ERROR 5: TYPE_CHECKING for circular imports =====
from __future__ import annotations  # Lazy evaluation of annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from my_service.models import User  # Import only during type checking

def create_user(data: "User") -> None:  # Forward reference (or use from __future__)
    pass

# ===== SILENCING mypy =====
result = legacy_function()          # type: ignore[return-value]
x: int = value                      # type: ignore  # noqa: PGH003
```

---

## 2.6 pre-commit — Complete Setup

```bash
# ===== INSTALL =====
pip install pre-commit
uv add --dev pre-commit

# ===== SETUP =====
pre-commit install                 # Install git hook
pre-commit install --hook-type commit-msg  # Also install commit-msg hook

# ===== MANUAL RUN =====
pre-commit run --all-files         # Run on all files (not just staged)
pre-commit run ruff                # Run specific hook only
pre-commit run --files app/main.py # Run on specific file

# ===== MAINTENANCE =====
pre-commit autoupdate              # Update all hook revisions to latest
pre-commit gc                      # Clean up unused cached envs
pre-commit clean                   # Remove all cached envs (nuke)

# ===== SKIP HOOKS =====
git commit --no-verify -m "wip"    # Skip all hooks (emergency only)
SKIP=mypy git commit -m "fix"      # Skip specific hook
```

---

## 2.7 Complete .pre-commit-config.yaml

```yaml
# .pre-commit-config.yaml
default_language_version:
  python: python3.11

repos:
  # ===== GENERAL FILE HYGIENE =====
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace         # Remove trailing whitespace
      - id: end-of-file-fixer           # Ensure files end with newline
      - id: check-yaml                  # Validate YAML syntax
      - id: check-toml                  # Validate TOML syntax
      - id: check-json                  # Validate JSON syntax
      - id: check-merge-conflict        # Detect merge conflict markers
      - id: check-added-large-files     # Block large files (>500KB default)
        args: ["--maxkb=500"]
      - id: check-case-conflict         # Case-insensitive filesystem issues
      - id: debug-statements            # Detect leftover pdb/breakpoint()
      - id: no-commit-to-branch         # Block commits to main/master
        args: ["--branch", "main", "--branch", "master"]

  # ===== SECRETS DETECTION =====
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
        args: ["--baseline", ".secrets.baseline"]
        exclude: "tests/fixtures/"

  # ===== RUFF: LINT + FORMAT =====
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.9
    hooks:
      - id: ruff                        # Lint + fix
        args: ["--fix", "--exit-non-zero-on-fix"]
      - id: ruff-format                 # Format

  # ===== MYPY: TYPE CHECK =====
  - repo: local
    hooks:
      - id: mypy
        name: mypy
        entry: mypy
        language: system                # Use project's venv mypy
        types: [python]
        args: ["--strict", "--ignore-missing-imports"]
        pass_filenames: false           # Run on whole package, not per-file
        additional_dependencies: []

  # ===== COMMIT MESSAGE FORMAT =====
  - repo: https://github.com/commitizen-tools/commitizen
    rev: v3.13.0
    hooks:
      - id: commitizen                  # Enforce conventional commits
        stages: [commit-msg]

  # ===== PYTEST (pre-push only — slow) =====
  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: pytest
        language: system
        types: [python]
        pass_filenames: false
        args: ["tests/unit/", "-x", "--tb=short"]  # Fast unit tests only
        stages: [pre-push]             # Only on push, not every commit
```

---

## 2.8 Conventional Commits (commitizen)

```bash
# Install commitizen
pip install commitizen
cz init                              # Initialize config

# ===== COMMIT WITH WIZARD =====
cz commit                            # Interactive commit message builder
# Select: feat / fix / docs / style / refactor / perf / test / chore
# Scope: api / auth / db / models
# Subject: short description
# Body: longer description (optional)
# Breaking change? (y/n)

# ===== CONVENTIONAL COMMIT FORMAT =====
# type(scope): subject
#
# feat(api): add user registration endpoint
# fix(auth): resolve JWT expiry validation bug
# docs(readme): update installation instructions
# refactor(db): extract connection pooling to separate module
# perf(search): add Redis caching for user lookup
# test(auth): add unit tests for token refresh
# chore(deps): bump pydantic from 2.4 to 2.5

# ===== AUTO CHANGELOG =====
cz changelog                         # Generate CHANGELOG.md from commits
cz bump                              # Auto-bump version based on commits
#   feat → minor bump (1.0.0 → 1.1.0)
#   fix  → patch bump (1.0.0 → 1.0.1)
#   feat with BREAKING CHANGE → major (1.0.0 → 2.0.0)
```

---

## 2.9 GitHub Actions — Full CI Pipeline

```yaml
# .github/workflows/quality.yml
name: Code Quality & Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  # ===== STAGE 1: FAST CHECKS =====
  lint:
    name: Lint & Format
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: astral-sh/setup-uv@v3

      - name: Set up Python
        run: uv python install 3.11

      - name: Install dev dependencies
        run: uv sync --frozen --group dev

      - name: Ruff lint
        run: uv run ruff check --no-fix --output-format=github .
        # --output-format=github → GitHub Actions annotations on PR

      - name: Ruff format check
        run: uv run ruff format --check .

  # ===== STAGE 2: TYPE CHECKING =====
  typecheck:
    name: Type Check
    runs-on: ubuntu-latest
    needs: lint                        # Only run if lint passes
    steps:
      - uses: actions/checkout@v4

      - uses: astral-sh/setup-uv@v3

      - name: Set up Python
        run: uv python install 3.11

      - name: Install all dependencies
        run: uv sync --frozen --all-groups

      - name: mypy
        run: uv run mypy --strict my_fastapi_service/

  # ===== STAGE 3: TESTS =====
  test:
    name: Tests (Python ${{ matrix.python-version }})
    runs-on: ubuntu-latest
    needs: lint
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.11", "3.12"]

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_DB: testdb
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

      redis:
        image: redis:7
        ports:
          - 6379:6379

    steps:
      - uses: actions/checkout@v4

      - uses: astral-sh/setup-uv@v3

      - name: Set up Python ${{ matrix.python-version }}
        run: uv python install ${{ matrix.python-version }}

      - name: Install dependencies
        run: uv sync --frozen --group test

      - name: Run tests
        env:
          DATABASE_URL: postgresql+asyncpg://test:test@localhost:5432/testdb
          REDIS_URL: redis://localhost:6379
        run: |
          uv run pytest \
            --cov=my_fastapi_service \
            --cov-report=xml \
            --cov-report=term-missing \
            --cov-fail-under=80 \
            -v

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v4
        with:
          file: coverage.xml
          flags: python-${{ matrix.python-version }}

  # ===== STAGE 4: SECURITY =====
  security:
    name: Security Scan
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: astral-sh/setup-uv@v3

      - name: Install dependencies
        run: uv sync --frozen --group dev

      - name: Bandit security scan
        run: uv run bandit -r my_fastapi_service/ -x tests/ -ll

      - name: Check for known vulnerabilities
        run: uv pip audit                # Check installed packages for CVEs
```

---

## 2.10 Makefile — Developer Commands

```makefile
.PHONY: install dev lint format type-check test test-cov pre-commit-setup ci

# ===== SETUP =====
install:
	uv sync --frozen --only-group main

dev:
	uv sync --frozen --all-groups
	uv run pre-commit install
	uv run pre-commit install --hook-type commit-msg

# ===== CODE QUALITY =====
lint:
	uv run ruff check .

lint-fix:
	uv run ruff check --fix .
	uv run ruff format .

format:
	uv run ruff format .

format-check:
	uv run ruff format --check .

type-check:
	uv run mypy --strict my_fastapi_service/

# ===== RUN ALL QUALITY CHECKS =====
check: lint-fix format type-check
	@echo "==============================="
	@echo "All quality checks passed!"
	@echo "==============================="

# ===== PRE-COMMIT =====
pre-commit-run:
	uv run pre-commit run --all-files

pre-commit-update:
	uv run pre-commit autoupdate

# ===== TESTING =====
test:
	uv run pytest tests/ -v

test-unit:
	uv run pytest tests/unit/ -v -x

test-integration:
	uv run pytest tests/integration/ -v

test-cov:
	uv run pytest --cov=my_fastapi_service --cov-report=html --cov-report=term
	open htmlcov/index.html

test-watch:
	uv run ptw tests/ -- -x  # pytest-watch

# ===== CI SIMULATION =====
ci: format-check lint type-check test
	@echo "CI simulation complete!"

# ===== CLEANUP =====
clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .mypy_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	rm -rf htmlcov/ .coverage coverage.xml
```

---

## 2.11 Interview Q&A

### Q1: Ruff kyun use karte ho? flake8 + black se kya better hai?

**Answer:**
```
Speed:
  flake8 + black + isort = 3 separate Python processes
  → 1000 files: 2-3 minutes CI time
  
  Ruff = 1 Rust binary, all in one pass
  → 1000 files: 2-3 seconds CI time

Feature parity:
  Ruff replaces: flake8 + 50+ plugins + black + isort + pyupgrade
  Single config in pyproject.toml [tool.ruff]
  
In production CI:
  Old: lint job = 3 min → blocks PRs
  New: lint job = 5 sec → instant feedback

I use:
  ruff check --fix .   # auto-fix what's safe
  ruff format .        # format like black
  
  In CI (no auto-fix):
  ruff check --no-fix . && ruff format --check .
```

### Q2: mypy strict mode mein kya enable hota hai?

**Answer:**
```
--strict enables all of:

1. --disallow-untyped-defs
   Every function must have arg + return type annotations

2. --disallow-any-generics
   list, dict not allowed → must be list[str], dict[str, int]

3. --disallow-subclassing-any
   Can't subclass untyped classes from third-party

4. --warn-return-any
   def foo() -> str: return untyped_func()  → error

5. --warn-unused-ignores
   # type: ignore that's no longer needed → error
   (keeps codebase clean)

6. --no-implicit-reexport
   from mymodule import X  # X not in __all__
   → other modules can't import X from here

Practical approach:
  Start with: mypy app/  (no flags, just catch obvious errors)
  Then:       mypy --disallow-untyped-defs app/  (require annotations)
  Finally:    mypy --strict app/  (full strictness, production-ready)
```

### Q3: pre-commit mein ek hook fail ho jaye toh kya hota hai?

**Answer:**
```
Scenario: ruff modifies a file (finds formatting issue)

1. ruff-format hook runs → finds issue → modifies file → exits non-zero
2. pre-commit catches exit code != 0
3. pre-commit FAILS the commit
4. Message: "ruff-format...Failed — files were modified by this hook"
5. Modified files are now in working directory (not staged)

What you do:
  git add .                          # Stage the auto-fixed files
  git commit -m "your message"       # Try again → now passes

For hooks that only report (no auto-fix like mypy):
  1. mypy runs → finds type error → exits non-zero
  2. Commit blocked
  3. You see the error, fix the code
  4. git add fixed_file.py
  5. git commit again

Emergency bypass (NEVER on main):
  git commit --no-verify -m "wip: temporary"
  # Or skip specific hook:
  SKIP=mypy git commit -m "fix: update logic"
```

### Q4: Type stub kya hai aur kab install karna padta hai?

**Answer:**
```
Python packages can be:
  1. Typed (has annotations + py.typed): pydantic, fastapi, httpx
     → mypy uses inline types directly ✓

  2. Untyped (no annotations): requests, boto3, redis (older versions)
     → mypy doesn't know types → treats as Any
     → With ignore_missing_imports=true: no error but no type checking

Solution for untyped packages: install type stubs
  pip install types-requests     # stubs for requests
  pip install types-redis        # stubs for redis
  pip install boto3-stubs        # stubs for boto3

Stubs are .pyi files:
  # requests.pyi (simplified)
  def get(url: str, **kwargs: Any) -> Response: ...
  class Response:
      status_code: int
      text: str
      def json(self) -> Any: ...

typeshed = built-in stubs for stdlib (os, sys, json, etc.)
  → Already included in mypy, no install needed

Check what stubs exist:
  mypy --install-types  # mypy suggests missing stubs
```

### Q5: CI mein pre-commit run kaise karte ho?

**Answer:**
```yaml
# Option 1: Use pre-commit directly in CI
- name: Run pre-commit
  uses: pre-commit/action@v3.0.0
  # Runs all hooks on changed files only (fast)

# Option 2: Run hooks individually (more control)
- name: Ruff lint
  run: ruff check --no-fix .

- name: Ruff format
  run: ruff format --check .

- name: mypy
  run: mypy --strict app/

# Difference:
# pre-commit in CI: runs same hooks as local → consistency guaranteed
# Individual commands: more flexible, parallel stages possible

# Best practice for large repos:
# - pre-commit for fast hooks (ruff, trailing-whitespace)
# - Separate jobs for slow checks (mypy, pytest)
# - Parallel jobs → faster overall pipeline

# Pro tip: cache pre-commit envs in CI
- uses: actions/cache@v4
  with:
    path: ~/.cache/pre-commit
    key: pre-commit-${{ hashFiles('.pre-commit-config.yaml') }}
```
