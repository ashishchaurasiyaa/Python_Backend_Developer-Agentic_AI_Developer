# Packaging + Distribution — pyproject.toml, wheels, PyPI Publishing

## Quick Concepts

**WHAT:**
- **pyproject.toml** = Modern Python project config (PEP 518/621)
- **Wheel (.whl)** = Pre-built binary distribution
- **sdist (.tar.gz)** = Source distribution
- **Build backend** = Tool that builds package (hatchling, setuptools, pdm)
- **PyPI** = Python Package Index (public repository)
- **Twine** = Tool for uploading to PyPI
- **uv** = Modern Python package manager (Rust-based, fast)
- **Hatch** = Modern project manager
- **Poetry** = Dependency manager + packaging

**WHY packaging matters:**
- Distribute your code
- Reproducible installs
- Version management
- Open-source contributions

**HOW modern Python packaging stack:**
```
┌──────────────────────────────────────────┐
│ pyproject.toml (config)                  │
├──────────────────────────────────────────┤
│ Build Backend (hatchling, setuptools)    │
├──────────────────────────────────────────┤
│ build tool (python -m build, uv build)   │
├──────────────────────────────────────────┤
│ Artifacts: .whl (wheel) + .tar.gz (sdist)│
├──────────────────────────────────────────┤
│ Twine / uv publish                       │
├──────────────────────────────────────────┤
│ PyPI / Private repo                      │
└──────────────────────────────────────────┘
```

---

## Interview Questions & Answers

### Q1: pyproject.toml — modern standard?

**Answer:**

**WHAT:** Single config file replacing setup.py, setup.cfg, requirements.txt.

**WHY:**
- Single source of truth
- Tool-agnostic format (TOML)
- PEP standardized
- Replaces setup.py (no more code in config)

**HOW — Minimal pyproject.toml:**

```toml
# pyproject.toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"


[project]
name = "myapp"
version = "1.0.0"
description = "My awesome app"
readme = "README.md"
authors = [{name = "Alice", email = "alice@example.com"}]
license = {text = "MIT"}
requires-python = ">=3.10"

dependencies = [
    "fastapi>=0.100.0",
    "pydantic>=2.0",
    "httpx>=0.25.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "ruff>=0.1.0",
    "mypy>=1.5.0",
]

[project.urls]
Homepage = "https://github.com/me/myapp"
Documentation = "https://myapp.readthedocs.io"
Repository = "https://github.com/me/myapp"
Issues = "https://github.com/me/myapp/issues"


[project.scripts]
myapp = "myapp.cli:main"  # CLI command


[tool.hatch.build.targets.wheel]
packages = ["src/myapp"]
```

**HOW — Install dev mode:**

```bash
# Editable install (development)
pip install -e .

# With extras
pip install -e ".[dev]"
```

---

### Q2: src/ layout vs flat layout?

**Answer:**

**WHAT:** Two ways to organize Python packages.

**HOW — Flat layout:**

```
myapp/
├── myapp/
│   ├── __init__.py
│   ├── main.py
│   └── utils.py
├── tests/
│   └── test_main.py
├── pyproject.toml
└── README.md
```

**HOW — src/ layout (RECOMMENDED):**

```
myapp/
├── src/
│   └── myapp/
│       ├── __init__.py
│       ├── main.py
│       └── utils.py
├── tests/
│   └── test_main.py
├── pyproject.toml
└── README.md
```

**WHY src/ layout better:**

```
1. Forces proper install (can't import from CWD)
   → Catches issues earlier
   → Tests use INSTALLED package

2. Prevents accidental imports
   - Flat: tests/test_main.py can import myapp/main.py from sibling
   - src/: must install first → realistic

3. Clearer separation
   - src/ = code
   - Other dirs = supporting files (tests, docs)

4. Recommended by Python Packaging Authority (PyPA)
```

**HOW — pyproject.toml for src/ layout:**

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/myapp"]


# Or with setuptools
[tool.setuptools.packages.find]
where = ["src"]


# Or with hatch
[tool.hatch.build.targets.sdist]
include = ["src/myapp"]
```

---

### Q3: Build backends — which to choose?

**Answer:**

**WHAT:** Tool that converts source to wheel/sdist.

**HOW — Comparison:**

| Backend | Pros | Cons | Best for |
|---|---|---|---|
| **hatchling** | Modern, fast, no setup.py | Newer | New projects |
| **setuptools** | Battle-tested, flexible | Complex config | Legacy migration |
| **pdm-backend** | Plugin ecosystem | PDM-specific | PDM users |
| **flit-core** | Minimal | Limited features | Simple pure-Python |
| **maturin** | Built for Rust extensions | Rust-specific | PyO3 projects |

**HOW — hatchling (recommended for new):**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"


[tool.hatch.version]
path = "src/myapp/__init__.py"  # ⭐ Version from file


[tool.hatch.build.targets.wheel]
packages = ["src/myapp"]


# Include extra files
[tool.hatch.build.targets.sdist]
include = [
    "src/myapp",
    "tests",
    "README.md",
    "LICENSE",
]
```

**HOW — setuptools (legacy compat):**

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"


[tool.setuptools.packages.find]
where = ["src"]


[tool.setuptools.dynamic]
version = {attr = "myapp.__version__"}
```

---

### Q4: Building wheels?

**Answer:**

**WHAT:** Wheel = pre-built distribution (faster install than sdist).

**WHY:**
- No build step on install
- Smaller download
- Faster pip install
- Required for PyPI

**HOW — Build with stdlib:**

```bash
# Install build tool
pip install build

# Build both wheel and sdist
python -m build

# Output in dist/
# - myapp-1.0.0-py3-none-any.whl
# - myapp-1.0.0.tar.gz
```

**HOW — Build with uv (faster):**

```bash
# Install uv (Rust-based, very fast)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Build
uv build

# 5-10x faster than python -m build
```

**HOW — Build with hatch:**

```bash
pip install hatch
hatch build
```

---

### Q5: Wheel formats — platform-specific?

**Answer:**

**WHAT:** Wheel filenames encode compatibility.

**HOW — Wheel naming:**

```
myapp-1.0.0-py3-none-any.whl
│     │     │   │    │
│     │     │   │    └── Platform tag (any = all platforms)
│     │     │   └────── ABI tag (none = no C extensions)
│     │     └────────── Python tag (py3 = any Python 3)
│     └──────────────── Version
└────────────────────── Package name
```

**Examples:**

```
# Pure Python (works everywhere)
myapp-1.0.0-py3-none-any.whl

# C extension (Linux x86_64, Python 3.11)
myapp-1.0.0-cp311-cp311-manylinux2014_x86_64.whl

# C extension (macOS arm64, Python 3.12)
myapp-1.0.0-cp312-cp312-macosx_11_0_arm64.whl

# C extension (Windows x64, Python 3.10)
myapp-1.0.0-cp310-cp310-win_amd64.whl
```

**HOW — Build for multiple platforms:**

```bash
# cibuildwheel (CI-friendly, builds for all platforms)
pip install cibuildwheel

# Builds for: Linux x86_64, macOS arm64, Windows x64, etc.
cibuildwheel --output-dir dist

# Or via GitHub Actions
```

**HOW — manylinux (Linux portability):**

```dockerfile
# Use manylinux Docker image
FROM quay.io/pypa/manylinux2014_x86_64

WORKDIR /app
COPY . .

RUN /opt/python/cp311-cp311/bin/pip wheel . -w dist/
RUN auditwheel repair dist/myapp-*.whl
```

---

### Q6: PyPI publishing flow?

**Answer:**

**HOW — Step-by-step:**

```bash
# Step 1: Create PyPI account
# https://pypi.org/account/register/

# Step 2: Get API token
# https://pypi.org/manage/account/token/

# Step 3: Save token (use .pypirc or keyring)
cat ~/.pypirc
# [pypi]
# username = __token__
# password = pypi-AgEIcHlwaS5vcmcCJG...


# Step 4: Build distribution
python -m build

# Step 5: Check
twine check dist/*
# ✓ Distribution looks good

# Step 6: Upload to TestPyPI first
twine upload --repository testpypi dist/*

# Step 7: Test install from TestPyPI
pip install -i https://test.pypi.org/simple/ myapp

# Step 8: Upload to real PyPI
twine upload dist/*

# Step 9: Verify
pip install myapp
```

**HOW — Modern: uv publish:**

```bash
# uv has built-in publish
uv publish

# Reads from env: UV_PUBLISH_TOKEN
```

**HOW — Automated (GitHub Actions):**

```yaml
# .github/workflows/publish.yml
name: Publish to PyPI

on:
  release:
    types: [published]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Build
        run: |
          pip install build
          python -m build

      - name: Publish
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          password: ${{ secrets.PYPI_API_TOKEN }}
```

---

### Q7: Versioning strategies?

**Answer:**

**HOW — SemVer (most common):**

```
Version: MAJOR.MINOR.PATCH

1.0.0 → 1.0.1  (PATCH = bug fix)
1.0.1 → 1.1.0  (MINOR = new feature, backward compat)
1.1.0 → 2.0.0  (MAJOR = breaking change)


Pre-release:
1.0.0a1   = alpha
1.0.0b1   = beta
1.0.0rc1  = release candidate
1.0.0     = stable
```

**HOW — CalVer (date-based):**

```
Format: YYYY.MM.MICRO

2024.01.0
2024.02.0  (next month)
2024.02.1  (patch)


Examples: pip uses CalVer (23.3.1 = Oct 2023)
```

**HOW — Manage version:**

```toml
# pyproject.toml — static version
[project]
version = "1.2.0"


# Or read from __init__.py
[tool.hatch.version]
path = "src/myapp/__init__.py"
```

```python
# src/myapp/__init__.py
__version__ = "1.2.0"
```

**HOW — Auto-bump with bumpversion:**

```bash
pip install bump2version

# Configure
cat .bumpversion.cfg
# [bumpversion]
# current_version = 1.0.0
# files = src/myapp/__init__.py

# Bump
bump2version patch  # 1.0.0 → 1.0.1
bump2version minor  # 1.0.1 → 1.1.0
bump2version major  # 1.1.0 → 2.0.0
```

**HOW — Auto from git tags:**

```bash
# setuptools_scm
pip install setuptools_scm

# pyproject.toml
[build-system]
requires = ["setuptools>=61.0", "setuptools_scm[toml]>=6.2"]

[tool.setuptools_scm]
write_to = "src/myapp/_version.py"

# Version auto-derived from git tags
git tag v1.0.0
python -m build  # Version = 1.0.0
```

---

### Q8: Dependency management — uv vs Poetry vs PDM?

**Answer:**

**HOW — Comparison:**

| Tool | Speed | Lockfile | venv | Build |
|---|---|---|---|---|
| **pip + requirements** | Slow | No (manual) | Manual | Manual |
| **pip-tools** | Slow | requirements.txt | Manual | Manual |
| **Poetry** | Slow | poetry.lock | Built-in | Built-in |
| **PDM** | Medium | pdm.lock | Built-in | Built-in |
| **uv** | ⭐ Fastest (Rust) | uv.lock | Built-in | Built-in |
| **Hatch** | Medium | None | Built-in | Built-in |

**HOW — uv (modern, recommended 2024+):**

```bash
# Install
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create new project
uv init myapp
cd myapp

# Add dependency
uv add fastapi pydantic

# Add dev dependency
uv add --dev pytest ruff

# Sync (install + create venv)
uv sync

# Run
uv run python app.py

# Lockfile: uv.lock (committed)
```

**HOW — Poetry:**

```bash
# Install
curl -sSL https://install.python-poetry.org | python3

# Create
poetry new myapp
cd myapp

# Add
poetry add fastapi
poetry add --group dev pytest

# Install
poetry install

# Run
poetry run python app.py

# Lockfile: poetry.lock (committed)
```

**HOW — pip-tools (lightweight):**

```bash
pip install pip-tools

# Write requirements.in
echo "fastapi" > requirements.in

# Compile to requirements.txt (with pinned versions)
pip-compile requirements.in

# Sync
pip-sync requirements.txt
```

---

### Q9: Private package repositories?

**Answer:**

**WHAT:** Host packages internally (proprietary code).

**WHY:**
- Don't want public release
- Internal company libraries
- Air-gapped environments

**HOW — Options:**

```
1. AWS CodeArtifact   - AWS managed
2. JFrog Artifactory  - Enterprise (paid)
3. Azure Artifacts    - Azure managed
4. devpi              - Self-hosted (free)
5. pypiserver         - Self-hosted minimal
6. GitHub Packages    - GitHub Enterprise
7. GitLab Package Registry - GitLab
```

**HOW — AWS CodeArtifact:**

```bash
# Login (gets temporary credentials)
aws codeartifact login --tool pip --domain mycompany \
  --repository myrepo

# Publish
twine upload --repository-url \
  https://mycompany-123456789.d.codeartifact.us-east-1.amazonaws.com/pypi/myrepo/ \
  dist/*

# Install
pip install mypackage  # ⭐ Auto from configured repo
```

**HOW — Private GitHub:**

```bash
# Install from GitHub (no PyPI)
pip install git+https://github.com/myorg/myrepo.git

# Specific tag
pip install git+https://github.com/myorg/myrepo.git@v1.0.0

# With token
pip install git+https://${GITHUB_TOKEN}@github.com/myorg/myrepo.git
```

```toml
# pyproject.toml dependency from Git
[project]
dependencies = [
    "mypackage @ git+https://github.com/myorg/myrepo.git@v1.0.0"
]
```

---

### Q10: Distributing C extensions?

**Answer:**

**WHAT:** Packages with Cython/Rust/C code.

**WHY harder:**
- Must compile for each platform
- Linux: manylinux compatibility
- macOS: x86_64 + arm64
- Windows: MSVC compiler

**HOW — Build for all platforms:**

```yaml
# .github/workflows/wheels.yml
name: Build wheels

on:
  push:
    tags: ['v*']

jobs:
  build_wheels:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
    steps:
      - uses: actions/checkout@v4

      - name: Build wheels
        uses: pypa/cibuildwheel@v2.16.0
        env:
          CIBW_SKIP: "pp* *-musllinux_*"  # Skip PyPy, musllinux

      - uses: actions/upload-artifact@v4
        with:
          name: wheels-${{ matrix.os }}
          path: wheelhouse/*.whl
```

**HOW — Maturin (Rust extensions):**

```bash
# Install
pip install maturin

# Build
maturin build --release

# Build wheels for all platforms
maturin build --release --strip --out dist
```

```toml
# pyproject.toml for Rust extension
[build-system]
requires = ["maturin>=1.0,<2.0"]
build-backend = "maturin"


[project]
name = "fastlib"
version = "1.0.0"


[tool.maturin]
features = ["pyo3/extension-module"]
```

---

## Packaging Checklist

```markdown
### Project Setup
- [ ] pyproject.toml (not setup.py)
- [ ] src/ layout
- [ ] README.md
- [ ] LICENSE
- [ ] .gitignore
- [ ] Tests in tests/ folder

### pyproject.toml
- [ ] Build backend specified
- [ ] Dependencies listed
- [ ] Dev dependencies in optional-dependencies
- [ ] Python version constraint
- [ ] Project URLs

### Build
- [ ] python -m build succeeds
- [ ] Both wheel and sdist created
- [ ] twine check passes

### Pre-release
- [ ] Version bumped
- [ ] CHANGELOG updated
- [ ] README has examples
- [ ] Tests pass on multiple Python versions

### Publish
- [ ] TestPyPI first
- [ ] Real PyPI after validation
- [ ] Git tag matches version
- [ ] GitHub release created

### Documentation
- [ ] API documentation (Sphinx or mkdocs)
- [ ] README has install + usage
- [ ] Examples folder
- [ ] CONTRIBUTING.md
```

---

## Sample Production pyproject.toml

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"


[project]
name = "my-awesome-package"
version = "1.0.0"
description = "Awesome Python package"
readme = "README.md"
authors = [{name = "Alice Smith", email = "alice@example.com"}]
license = {text = "MIT"}
requires-python = ">=3.10"
classifiers = [
    "Development Status :: 4 - Beta",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
    "Typing :: Typed",
]
keywords = ["web", "api", "fastapi"]


dependencies = [
    "fastapi>=0.100.0",
    "pydantic>=2.0",
    "httpx>=0.25.0",
]


[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-asyncio>=0.21",
    "pytest-cov>=4.0",
    "ruff>=0.1.0",
    "mypy>=1.5.0",
]
docs = [
    "mkdocs>=1.5",
    "mkdocs-material>=9.0",
]
all = ["my-awesome-package[dev,docs]"]


[project.urls]
Homepage = "https://github.com/alice/my-awesome-package"
Documentation = "https://my-awesome-package.readthedocs.io"
Repository = "https://github.com/alice/my-awesome-package"
"Bug Tracker" = "https://github.com/alice/my-awesome-package/issues"


[project.scripts]
myapp = "my_awesome_package.cli:main"


[tool.hatch.build.targets.wheel]
packages = ["src/my_awesome_package"]


[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "-v --cov=src --cov-report=term-missing"


[tool.ruff]
line-length = 100
target-version = "py310"
select = ["E", "F", "I", "B", "UP"]


[tool.mypy]
python_version = "3.10"
strict = true
warn_return_any = true
warn_unused_configs = true
```
