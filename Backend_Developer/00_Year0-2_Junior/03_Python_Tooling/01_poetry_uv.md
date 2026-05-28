# Poetry & uv — Modern Python Package Management

---

# PART 1 — THEORY (Deep Concepts & Internals)

---

## 1.1 Why Modern Package Management?

### The Problem with `pip` alone

```
pip install requests           # Installs latest — may break tomorrow
pip freeze > requirements.txt  # Manual, error-prone, includes transitive deps
pip install -r requirements.txt # Different machines → different behavior
```

**Core problems:**
| Problem | pip alone | Poetry / uv |
|---------|-----------|-------------|
| Dependency resolution | Greedy, no backtracking | SAT solver (Poetry: pubgrub algorithm) |
| Lock file | Manual `pip freeze` | Auto-generated, deterministic |
| Dev vs Prod deps | No separation | Dependency groups |
| Virtual env | Manual `venv` | Auto-managed |
| Publishing | Manual `twine` | Built-in `poetry publish` |
| Speed | Baseline | uv = 10–100x faster (Rust) |

---

## 1.2 Python Packaging Standards (PEP History)

```
PEP 517 (2015) — Build backend interface
  → Defines how build tools create packages (wheel, sdist)
  → Backends: setuptools, flit, hatchling, poetry-core

PEP 518 (2016) — pyproject.toml
  → Single config file replaces setup.py + setup.cfg + MANIFEST.in
  → [build-system] table specifies the backend

PEP 621 (2020) — Standard project metadata
  → [project] table: name, version, dependencies, authors, etc.
  → poetry uses [tool.poetry] instead (predates PEP 621)

PEP 660 (2021) — Editable installs via pyproject.toml
  → pip install -e . works with modern backends
```

---

## 1.3 Virtual Environments — Internals

### What is a virtualenv?

```
A virtualenv is a directory containing:
  bin/python   → symlink to system Python (or copy)
  bin/pip      → pip scoped to this env
  lib/python3.x/site-packages/  → installed packages (isolated)
  pyvenv.cfg   → metadata (home = system Python path)
```

### How Python finds packages

```python
import sys
print(sys.path)
# ['', '/usr/lib/python311.zip', '/usr/lib/python3.11',
#  '/home/user/.venv/lib/python3.11/site-packages']  ← virtualenv wins
```

When you activate a virtualenv:
1. `PATH` is prepended with `venv/bin/`
2. `python` now resolves to `venv/bin/python`
3. `sys.prefix` → venv directory
4. `sys.path` includes venv's `site-packages`

### Poetry's virtualenv management

```
~/.cache/pypoetry/virtualenvs/
  my-project-xK8d9Pqm-py3.11/   ← hash of project path + python version
    bin/python
    lib/python3.11/site-packages/
```

Poetry auto-creates and manages this — no manual activation needed for `poetry run`.

---

## 1.4 Dependency Resolution — How Poetry Solves It

### The Dependency Problem

```
Package A requires: requests>=2.28
Package B requires: requests<2.29

→ Poetry must find: requests==2.28.x (satisfies both)
```

### PubGrub Algorithm (Poetry's Resolver)

```
1. Start with root package requirements
2. Pick the next unsatisfied dependency
3. Try versions from newest to oldest
4. If conflict found → backtrack, add "incompatibility"
5. Propagate constraints (unit propagation)
6. Repeat until all satisfied or declare impossible
```

### Lock File — What it Contains

```toml
# poetry.lock (auto-generated, NEVER edit manually)

[[package]]
name = "fastapi"
version = "0.104.1"
description = "..."
category = "main"
optional = false
python-versions = ">=3.8"
files = [
    {file = "fastapi-0.104.1-py3-none-any.whl", hash = "sha256:abc..."},
    {file = "fastapi-0.104.1.tar.gz", hash = "sha256:def..."},
]

[package.dependencies]
pydantic = ">=1.7.4,<1.8 || >=1.8.1,<1.9 || >=1.9.2,<3.0.0"
starlette = ">=0.27.0,<0.28.0"
```

**Lock file guarantees:**
- Exact versions for every package (direct + transitive)
- SHA-256 hashes for security (tamper detection)
- `poetry install` → bit-for-bit identical env on any machine

---

## 1.5 pyproject.toml — Anatomy

### Complete Structure

```
pyproject.toml
├── [build-system]          ← Which backend builds the package
├── [tool.poetry]           ← Poetry-specific project metadata
│   ├── name, version, description, authors, license, readme
│   ├── packages            ← What to include in distribution
│   └── classifiers         ← PyPI classifiers
├── [tool.poetry.dependencies]      ← Runtime dependencies
├── [tool.poetry.group.dev.dependencies]   ← Dev-only
├── [tool.poetry.group.test.dependencies]  ← Test-only
├── [tool.ruff]             ← Ruff linter config
├── [tool.mypy]             ← Mypy type checker config
├── [tool.pytest.ini_options]       ← Pytest config
└── [tool.coverage.report]          ← Coverage config
```

---

## 1.6 uv — Architecture & Speed

### Why uv is Fast

```
pip (Python):
  Network I/O → Python parsing → pip's resolver → sequential install

uv (Rust):
  Parallel downloads (tokio async)
  → Compiled dependency resolver (same PubGrub, but Rust)
  → Parallel wheel extraction
  → Global cache (hardlinks, no re-download)

Result: 10–100x faster than pip
```

### uv Cache Architecture

```
~/.cache/uv/
  wheels/           ← Built wheels (keyed by (package, version, platform))
  archive/          ← Downloaded archives (tar.gz, zip)
  interpreter/      ← Python interpreter metadata cache
```

**Hardlink strategy:** Instead of copying files, uv creates hardlinks from cache to venv — installation is near-instant if already cached.

### uv vs pip vs Poetry Comparison

| Feature | pip | Poetry | uv |
|---------|-----|--------|-----|
| Speed | 1x | ~1x | 10-100x |
| Lockfile | No (manual) | Yes | Yes (uv.lock) |
| Dependency resolver | Basic | PubGrub | PubGrub (Rust) |
| Virtual env mgmt | No | Yes | Yes |
| Dependency groups | No | Yes | Yes |
| Publishing | No (twine) | Yes | Planned |
| Python version mgmt | No | No | Yes (`uv python`) |
| Workspace support | No | Limited | Yes |
| PEP 517/518 | Yes | Yes | Yes |

---

## 1.7 Dependency Groups — Dev/Test/Prod Separation

### Why Separate Groups?

```
Production Docker image:
  pip install . --only-main
  → No pytest, no black, no mypy → smaller image, faster deploy

CI/CD:
  pip install .[test]
  → Only what's needed for testing

Developer machine:
  poetry install (all groups)
  → Everything including formatters, debuggers, etc.
```

### Group Types

```
[tool.poetry.dependencies]        # main group = shipped with package
[tool.poetry.group.dev.dependencies]  # local dev tools
[tool.poetry.group.test.dependencies] # testing tools
[tool.poetry.group.docs.dependencies] # documentation tools
```

---

## 1.8 Semantic Versioning & Version Constraints

```
MAJOR.MINOR.PATCH  →  2.1.3

MAJOR: breaking changes
MINOR: new features (backward compatible)
PATCH: bug fixes (backward compatible)

Poetry constraint syntax:
  "^2.1.3"   → >=2.1.3, <3.0.0   (caret: minor/patch updates OK)
  "~2.1.3"   → >=2.1.3, <2.2.0   (tilde: patch updates only)
  ">=2.1,<3" → explicit range
  "*"         → any version (dangerous)
  "2.1.3"    → exact pin (very strict)
```

---

# PART 2 — PRACTICAL (Complete Working Code & Commands)

---

## 2.1 Complete Poetry Project Setup

```bash
# ===== INSTALL POETRY =====
curl -sSL https://install.python-poetry.org | python3 -
# Add to PATH (bash/zsh)
export PATH="$HOME/.local/bin:$PATH"

# Verify
poetry --version   # Poetry (version 1.8.x)

# ===== NEW PROJECT FROM SCRATCH =====
poetry new my-fastapi-service
cd my-fastapi-service

# Structure created:
# my-fastapi-service/
# ├── pyproject.toml
# ├── README.md
# ├── my_fastapi_service/
# │   └── __init__.py
# └── tests/
#     └── __init__.py

# ===== OR: INIT IN EXISTING DIRECTORY =====
mkdir my-project && cd my-project
poetry init   # Interactive wizard
# OR non-interactive:
poetry init \
  --name "my-fastapi-service" \
  --description "Production FastAPI service" \
  --author "Ashish Chaurasiya <chaurasiya1ashish@gmail.com>" \
  --python "^3.11" \
  --no-interaction
```

---

## 2.2 Complete pyproject.toml

```toml
[build-system]
requires = ["poetry-core>=1.0.0"]
build-backend = "poetry.core.masonry.api"

[tool.poetry]
name = "my-fastapi-service"
version = "1.0.0"
description = "Production-ready FastAPI microservice"
authors = ["Ashish Chaurasiya <chaurasiya1ashish@gmail.com>"]
license = "MIT"
readme = "README.md"
homepage = "https://github.com/ashish/my-fastapi-service"
repository = "https://github.com/ashish/my-fastapi-service"
documentation = "https://docs.my-fastapi-service.com"
keywords = ["fastapi", "microservice", "python"]
classifiers = [
    "Development Status :: 5 - Production/Stable",
    "Framework :: FastAPI",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.11",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
]
packages = [{include = "my_fastapi_service"}]
include = ["my_fastapi_service/py.typed"]  # PEP 561: typed package marker

# ===== RUNTIME DEPENDENCIES =====
[tool.poetry.dependencies]
python = "^3.11"
fastapi = "^0.104.0"
uvicorn = {version = "^0.24.0", extras = ["standard"]}  # with extras
pydantic = "^2.5.0"
pydantic-settings = "^2.1.0"
sqlalchemy = {version = "^2.0.0", extras = ["asyncio"]}
asyncpg = "^0.29.0"
redis = "^5.0.0"
httpx = "^0.25.0"              # async HTTP client
structlog = "^23.2.0"          # structured logging

# Optional dependency groups:
python-jose = {version = "^3.3.0", optional = true, extras = ["cryptography"]}
passlib = {version = "^1.7.4", optional = true, extras = ["bcrypt"]}

# ===== OPTIONAL EXTRAS =====
[tool.poetry.extras]
auth = ["python-jose", "passlib"]  # pip install my-pkg[auth]

# ===== DEV TOOLS =====
[tool.poetry.group.dev.dependencies]
ruff = "^0.1.0"
mypy = "^1.7.0"
pre-commit = "^3.5.0"
ipython = "^8.17.0"
rich = "^13.7.0"

# ===== TEST TOOLS =====
[tool.poetry.group.test.dependencies]
pytest = "^7.4.0"
pytest-asyncio = "^0.21.0"
pytest-cov = "^4.1.0"
pytest-mock = "^3.12.0"
httpx = "^0.25.0"              # TestClient
factory-boy = "^3.3.0"        # Test fixtures
faker = "^20.0.0"

# ===== DOCS TOOLS =====
[tool.poetry.group.docs.dependencies]
mkdocs = "^1.5.0"
mkdocs-material = "^9.4.0"
mkdocstrings = {version = "^0.24.0", extras = ["python"]}

# ===== SCRIPTS / ENTRY POINTS =====
[tool.poetry.scripts]
serve = "my_fastapi_service.main:run_server"
migrate = "my_fastapi_service.db.migrations:run"

# ===== RUFF CONFIG =====
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "C4", "SIM", "TCH"]
ignore = ["E501"]

# ===== MYPY CONFIG =====
[tool.mypy]
python_version = "3.11"
strict = true
ignore_missing_imports = true

# ===== PYTEST CONFIG =====
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "--cov=my_fastapi_service --cov-report=term-missing --cov-fail-under=80"

# ===== COVERAGE CONFIG =====
[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
]
```

---

## 2.3 Core Poetry Commands

```bash
# ===== DEPENDENCY MANAGEMENT =====
poetry add fastapi                         # Add to [tool.poetry.dependencies]
poetry add "fastapi^0.104"                 # With version constraint
poetry add "uvicorn[standard]"             # With extras
poetry add --group dev ruff mypy           # Add to dev group
poetry add --group test pytest pytest-cov  # Add to test group
poetry add --optional python-jose          # Optional dependency

poetry remove requests                     # Remove package
poetry update                             # Update all to latest (within constraints)
poetry update fastapi                     # Update specific package
poetry show                               # List installed packages
poetry show --tree                        # Dependency tree
poetry show --outdated                    # Packages with newer versions

# ===== VIRTUAL ENV =====
poetry env info                           # Show current venv info
poetry env list                           # All envs for this project
poetry env use python3.11                 # Use specific Python version
poetry env remove python3.11              # Delete venv

# ===== RUNNING COMMANDS =====
poetry install                            # Install all groups
poetry install --only main                # Only runtime deps (production)
poetry install --with test                # Main + test group
poetry install --without docs             # All except docs
poetry install --sync                     # Remove packages not in lock file

poetry run python app.py                  # Run in venv context
poetry run pytest                         # Run tests
poetry run uvicorn main:app --reload      # Run server
poetry shell                              # Activate venv in new shell

# ===== LOCK FILE =====
poetry lock                               # Regenerate poetry.lock
poetry lock --no-update                   # Re-lock without updating versions
poetry check                              # Validate pyproject.toml
poetry check --lock                       # Check lock file is up-to-date

# ===== BUILD & PUBLISH =====
poetry build                              # Creates dist/ with wheel + sdist
# dist/
#   my_fastapi_service-1.0.0-py3-none-any.whl
#   my_fastapi_service-1.0.0.tar.gz

poetry config pypi-token.pypi "pypi-xxxxx..."  # Set PyPI token
poetry publish                            # Upload to PyPI
poetry publish --dry-run                  # Simulate without publishing
poetry publish --repository testpypi      # Publish to TestPyPI first

# ===== VERSION MANAGEMENT =====
poetry version patch                      # 1.0.0 → 1.0.1
poetry version minor                      # 1.0.0 → 1.1.0
poetry version major                      # 1.0.0 → 2.0.0
poetry version 2.1.3                      # Set exact version
```

---

## 2.4 uv — Complete Command Reference

```bash
# ===== INSTALL uv =====
curl -LsSf https://astral.sh/uv/install.sh | sh
# OR
pip install uv
# OR (macOS)
brew install uv

uv --version   # uv 0.4.x

# ===== PYTHON VERSION MANAGEMENT =====
uv python list                            # Available Python versions
uv python install 3.11                    # Install Python 3.11
uv python install 3.11 3.12              # Install multiple
uv python pin 3.11                        # Create .python-version file

# ===== PROJECT INIT =====
uv init my-project                        # New project with pyproject.toml
uv init --lib my-library                  # Library project (src layout)
uv init --app my-app                      # Application project

# ===== VIRTUAL ENV =====
uv venv                                   # Create .venv in current dir
uv venv --python 3.11                     # Specific Python version
uv venv my-custom-venv                    # Custom location
source .venv/bin/activate                 # Activate (traditional)

# ===== PACKAGE MANAGEMENT =====
uv add fastapi                            # Add to dependencies
uv add "fastapi>=0.104"                   # With constraint
uv add "uvicorn[standard]"               # With extras
uv add --dev ruff mypy                    # Dev dependencies
uv add --group test pytest               # Custom group
uv add --optional auth python-jose        # Optional

uv remove requests                        # Remove package
uv sync                                   # Install from uv.lock
uv sync --frozen                          # Fail if lock out of date (CI)
uv sync --only-group main                 # Only main deps

uv pip install fastapi                    # pip-compatible interface
uv pip install -r requirements.txt        # From requirements.txt
uv pip compile requirements.in            # Lock dependencies → requirements.txt
uv pip freeze                             # List installed packages

# ===== RUNNING =====
uv run python script.py                   # Run in project venv
uv run pytest                             # Run tests
uv run --with httpx python -c "import httpx; print(httpx.__version__)"  # Temp dep

# ===== TOOLS (global CLI tools) =====
uv tool install ruff                      # Install ruff globally
uv tool install black                     # Install black globally
uv tool run ruff check .                  # Run without installing (like npx)
uvx ruff check .                          # Shorthand for uv tool run

# ===== LOCK FILE =====
uv lock                                   # Generate uv.lock
uv lock --check                           # Verify lock is up-to-date
```

---

## 2.5 Production Docker Pattern

```dockerfile
# ===== Dockerfile (multi-stage with Poetry) =====
FROM python:3.11-slim AS builder

# Install poetry
ENV POETRY_VERSION=1.8.0
ENV POETRY_HOME=/opt/poetry
ENV POETRY_VIRTUALENVS_IN_PROJECT=1       # Creates .venv in /app
ENV POETRY_NO_INTERACTION=1

RUN pip install poetry==$POETRY_VERSION

WORKDIR /app
COPY pyproject.toml poetry.lock ./

# Install only production deps
RUN poetry install --only main --no-root

# ===== Production stage =====
FROM python:3.11-slim AS production

WORKDIR /app

# Copy venv from builder
COPY --from=builder /app/.venv ./.venv

# Copy application code
COPY my_fastapi_service/ ./my_fastapi_service/

# Use venv Python directly
ENV PATH="/app/.venv/bin:$PATH"

CMD ["uvicorn", "my_fastapi_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```dockerfile
# ===== Dockerfile (multi-stage with uv) =====
FROM python:3.11-slim AS builder

# Install uv (much faster than pip)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./

# Install deps (frozen = fail if lock outdated)
RUN uv sync --frozen --no-dev --no-install-project

COPY my_fastapi_service/ ./my_fastapi_service/
RUN uv sync --frozen --no-dev

FROM python:3.11-slim AS production
WORKDIR /app
COPY --from=builder /app/.venv ./.venv
COPY --from=builder /app/my_fastapi_service ./my_fastapi_service
ENV PATH="/app/.venv/bin:$PATH"
CMD ["uvicorn", "my_fastapi_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 2.6 Package Structure — Library vs Application

```
# LIBRARY (publishable to PyPI)
my-library/
├── pyproject.toml
├── README.md
├── LICENSE
├── src/                          ← src layout (prevents accidental imports)
│   └── my_library/
│       ├── __init__.py           ← Public API
│       ├── py.typed              ← PEP 561: typed package marker
│       ├── core.py
│       └── utils.py
└── tests/
    ├── conftest.py
    └── test_core.py

# APPLICATION (deployed service)
my-service/
├── pyproject.toml
├── README.md
├── my_service/                   ← flat layout
│   ├── __init__.py
│   ├── main.py                   ← entrypoint
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes/
│   │   └── dependencies.py
│   ├── core/
│   │   ├── config.py
│   │   └── database.py
│   ├── models/
│   ├── services/
│   └── repositories/
├── tests/
│   ├── conftest.py
│   ├── unit/
│   └── integration/
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
└── Makefile
```

---

## 2.7 Makefile for Developer Workflow

```makefile
.PHONY: install dev test lint format type-check clean build publish

# ===== SETUP =====
install:
	poetry install --only main

dev:
	poetry install
	poetry run pre-commit install

# ===== QUALITY =====
lint:
	poetry run ruff check .

format:
	poetry run ruff format .
	poetry run ruff check --fix .

type-check:
	poetry run mypy my_fastapi_service/

check: lint type-check
	@echo "All checks passed!"

# ===== TESTING =====
test:
	poetry run pytest

test-cov:
	poetry run pytest --cov=my_fastapi_service --cov-report=html
	open htmlcov/index.html

test-unit:
	poetry run pytest tests/unit/ -v

test-integration:
	poetry run pytest tests/integration/ -v

# ===== BUILD =====
clean:
	rm -rf dist/ build/ *.egg-info htmlcov/ .coverage .pytest_cache __pycache__

build: clean
	poetry build

publish: build
	poetry publish

publish-test: build
	poetry publish --repository testpypi

# ===== DATABASE =====
migrate:
	poetry run alembic upgrade head

migrate-rollback:
	poetry run alembic downgrade -1

# ===== SERVER =====
serve:
	poetry run uvicorn my_fastapi_service.main:app --reload --port 8000

serve-prod:
	poetry run uvicorn my_fastapi_service.main:app --workers 4 --port 8000
```

---

## 2.8 GitHub Actions CI with Poetry & uv

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]

    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3
        with:
          version: "latest"

      - name: Set up Python ${{ matrix.python-version }}
        run: uv python install ${{ matrix.python-version }}

      - name: Install dependencies
        run: uv sync --frozen --all-groups

      - name: Lint with Ruff
        run: uv run ruff check .

      - name: Format check
        run: uv run ruff format --check .

      - name: Type check with mypy
        run: uv run mypy my_fastapi_service/

      - name: Run tests
        run: uv run pytest --cov=my_fastapi_service --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: coverage.xml

  build:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'

    steps:
      - uses: actions/checkout@v4

      - name: Install Poetry
        uses: snok/install-poetry@v1
        with:
          version: "1.8.0"

      - name: Build package
        run: poetry build

      - name: Publish to PyPI
        if: startsWith(github.ref, 'refs/tags/')
        run: poetry publish
        env:
          POETRY_PYPI_TOKEN_PYPI: ${{ secrets.PYPI_TOKEN }}
```

---

## 2.9 Interview Q&A

### Q1: Poetry aur pip mein fundamental difference kya hai?

**Answer:**
```
pip = package installer only
  - Dependency resolution: greedy (no backtracking) → conflicts possible
  - No lockfile: pip freeze is manual + includes transitive deps
  - No virtualenv management
  - No dev/prod separation
  - No publishing

Poetry = complete project management tool
  - PubGrub SAT solver: guaranteed conflict-free resolution or clear error
  - Lockfile: auto-generated, includes hashes for security
  - Auto-manages virtualenvs
  - Dependency groups: main/dev/test/docs
  - Built-in publish to PyPI

Real example:
  pip: requests>=2.28 + requests<2.29 → silent install of wrong version
  Poetry: exactly finds requests==2.28.x or gives clear conflict error
```

### Q2: poetry.lock file ko git mein commit karna chahiye ya nahi?

**Answer:**
```
LIBRARY (published to PyPI):
  → DO NOT commit poetry.lock
  → Users install your library into THEIR project → their lock file resolves
  → Add poetry.lock to .gitignore

APPLICATION (deployed service):
  → ALWAYS commit poetry.lock
  → Guarantees identical deps in dev/staging/production
  → CI fails if lock is out of date (poetry check --lock)
  → Security: hashes prevent tampered packages

Rule: If it runs (app/service) → commit lock. If it's used (library) → don't.
```

### Q3: uv itna fast kyun hai? Real numbers?

**Answer:**
```
Benchmark: Install Django + all deps

pip:         ~45 seconds (cold)
Poetry:      ~40 seconds (cold)
uv:          ~3 seconds  (cold)
uv (cached): ~0.5 seconds (hardlinks from ~/.cache/uv)

Why fast:
1. Written in Rust (compiled, no Python GIL overhead)
2. Parallel downloads: tokio async runtime, all packages concurrently
3. Global hardlink cache: files not copied, just linked (~instant if cached)
4. Compiled resolver: same PubGrub algorithm as Poetry but 100x faster compile

Use case: Docker builds — switching from pip to uv saves 30-60 seconds per build
```

### Q4: pyproject.toml ka [build-system] table kya karta hai?

**Answer:**
```toml
[build-system]
requires = ["poetry-core>=1.0.0"]
build-backend = "poetry.core.masonry.api"
```
```
When you run: pip install . OR poetry build

pip reads [build-system]:
  1. Creates isolated build env
  2. Installs "requires" packages (poetry-core here)
  3. Calls build-backend's API to build wheel/sdist
  4. Installs the built wheel

Without pyproject.toml: pip uses legacy setup.py (deprecated)
With pyproject.toml: pip uses PEP 517 build isolation

Alternative backends:
  hatchling → [build-system] requires = ["hatchling"]
  flit-core  → [build-system] requires = ["flit-core"]
  setuptools → [build-system] requires = ["setuptools>=61"]
```

### Q5: Production mein Poetry install kaise karte ho — sab kuch nahi, sirf main deps?

**Answer:**
```bash
# Option 1: Poetry (older style)
poetry install --only main

# Option 2: Poetry with --no-root (don't install the project itself as editable)
poetry install --only main --no-root

# Option 3: uv (newer, faster)
uv sync --frozen --no-dev

# Dockerfile best practice:
COPY pyproject.toml poetry.lock ./
RUN poetry install --only main --no-root  # Step cached if files unchanged
COPY my_service/ ./my_service/
RUN poetry install --only main           # Install the project itself

# Why --no-root first?
# Docker layer caching: if only code changes (not deps),
# "poetry install --only main" layer is CACHED → fast rebuild
# Only the COPY + second install runs → saves 30-60s per build
```
