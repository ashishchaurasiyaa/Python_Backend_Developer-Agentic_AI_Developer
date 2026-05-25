# `mypy` + `ruff` — Production-Grade Python Tooling

> **Interview angle:** "Aapki team mein code quality kaise enforce karte ho?"

---

## 1. Why Tooling Matters (5 YOE Engineer Perspective)

Production code mein **bugs catch karna runtime se pehle** critical hai:
- Type errors compile-time pe catch → 30-40% bugs prevented
- Style + lint = consistent codebase = faster reviews
- Auto-format = no bikeshed arguments

**Modern Python stack:**
- **`mypy`** — Static type checker
- **`ruff`** — Fast linter + formatter (replaces flake8, isort, black, pylint, etc.)
- **`pre-commit`** — Hook before git commit
- **`pyright`** — Alternative to mypy (faster, Microsoft, used by VS Code Pylance)

---

## 2. `mypy` — Static Type Checker

### Install
```bash
pip install mypy
```

### Basic usage
```bash
mypy app/
mypy --strict app/   # all strict checks
```

### Sample code
```python
def add(a: int, b: int) -> int:
    return a + b

add("1", "2")   # mypy error: incompatible type
```

### Strictness levels

```toml
# pyproject.toml
[tool.mypy]
python_version = "3.12"
strict = true                      # turns on EVERYTHING below

# Or pick individual flags:
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true       # every function must have types
disallow_incomplete_defs = true
check_untyped_defs = true
disallow_untyped_decorators = true
no_implicit_optional = true        # Optional[X] must be explicit
warn_redundant_casts = true
warn_unused_ignores = true
warn_no_return = true
warn_unreachable = true
strict_equality = true
extra_checks = true
```

### Common patterns

#### a) Generic types
```python
from typing import TypeVar, Generic

T = TypeVar("T")

class Repository(Generic[T]):
    def get(self, id: int) -> T | None: ...
```

#### b) Protocol (structural subtyping — duck typing with types)
```python
from typing import Protocol

class Saveable(Protocol):
    def save(self) -> None: ...

def persist(obj: Saveable) -> None:
    obj.save()
```

#### c) `Literal` for restricted values
```python
from typing import Literal

def set_log_level(level: Literal["DEBUG", "INFO", "WARN", "ERROR"]) -> None:
    ...
```

#### d) `TypedDict` for dict shapes
```python
from typing import TypedDict

class UserDict(TypedDict):
    id: int
    name: str
    email: str | None

def process(u: UserDict) -> str:
    return u["name"]
```

#### e) `Annotated` for FastAPI-style metadata
```python
from typing import Annotated
from fastapi import Query

def search(q: Annotated[str, Query(min_length=3)]) -> list[str]: ...
```

#### f) `ParamSpec` for decorator-aware typing
```python
from typing import ParamSpec, TypeVar, Callable
P = ParamSpec("P")
R = TypeVar("R")

def log(func: Callable[P, R]) -> Callable[P, R]:
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        print(f"Calling {func.__name__}")
        return func(*args, **kwargs)
    return wrapper
```

#### g) `Self` (Python 3.11+)
```python
from typing import Self

class Builder:
    def with_name(self, name: str) -> Self:
        self.name = name
        return self     # type checker knows this is Builder (or subclass)
```

### Ignoring lines
```python
result: int = "string"   # type: ignore[assignment]
```

### Migrating gradually
```toml
[[tool.mypy.overrides]]
module = "legacy_module.*"
ignore_errors = true
```

---

## 3. `ruff` — All-in-One Linter + Formatter

### Why ruff?
- **10-100x faster** than flake8/pylint (written in Rust)
- Replaces: flake8, isort, black, pyupgrade, pylint (most rules), bandit basics
- Single config file
- Auto-fix support

### Install
```bash
pip install ruff
```

### Usage
```bash
ruff check .          # lint
ruff check --fix .    # auto-fix
ruff format .         # format (replaces black)
ruff format --check . # CI check, no changes
```

### Config (`pyproject.toml`)

```toml
[tool.ruff]
line-length = 100
target-version = "py312"
fix = true              # auto-fix on save

[tool.ruff.lint]
# Enable rule groups
select = [
    "E",       # pycodestyle errors
    "W",       # pycodestyle warnings
    "F",       # pyflakes
    "I",       # isort
    "B",       # flake8-bugbear (likely bugs)
    "C4",      # flake8-comprehensions
    "UP",      # pyupgrade (modernize syntax)
    "N",       # pep8-naming
    "SIM",     # flake8-simplify
    "TID",     # flake8-tidy-imports
    "ARG",     # unused arguments
    "PTH",     # use pathlib
    "RUF",     # ruff-specific
    "S",       # bandit (security)
    "ASYNC",   # async/await issues
    "PERF",    # performance anti-patterns
]
ignore = [
    "E501",    # line too long (we use formatter)
    "S101",    # use of assert (allowed in tests)
]

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["S101", "ARG"]    # allow asserts and unused args in tests

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
docstring-code-format = true
```

### Common rules to know

| Rule | Catches |
|---|---|
| `E501` | Line too long |
| `F401` | Unused import |
| `F811` | Redefined name |
| `B008` | Mutable default argument |
| `C401` | Unnecessary generator |
| `UP007` | Use `X \| Y` instead of `Union[X, Y]` |
| `SIM118` | `key in dict.keys()` → `key in dict` |
| `S105` | Possible hardcoded password |
| `ASYNC100` | Async function without await |

---

## 4. `pre-commit` — Git Hook Integration

### Install
```bash
pip install pre-commit
pre-commit install
```

### Config (`.pre-commit-config.yaml`)

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.9
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.11.2
    hooks:
      - id: mypy
        additional_dependencies:
          - pydantic
          - sqlalchemy
          - types-redis
        args: [--strict, --ignore-missing-imports]

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-merge-conflict
      - id: detect-private-key
      - id: check-added-large-files
        args: [--maxkb=500]

  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.10
    hooks:
      - id: bandit
        args: [-c, pyproject.toml]
```

Run manually:
```bash
pre-commit run --all-files
```

---

## 5. CI/CD Integration

### GitHub Actions

```yaml
# .github/workflows/lint.yml
name: Lint
on: [push, pull_request]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install
        run: |
          pip install ruff mypy
          pip install -r requirements.txt

      - name: Ruff lint
        run: ruff check .

      - name: Ruff format check
        run: ruff format --check .

      - name: Mypy
        run: mypy app/ --strict
```

### Pre-merge gate
Configure branch protection → require lint workflow to pass.

---

## 6. `pyright` — Alternative to mypy

Microsoft's checker. Faster than mypy, used by Pylance (VS Code).

```bash
pip install pyright
pyright app/
```

### Config (`pyrightconfig.json` or pyproject.toml)
```toml
[tool.pyright]
include = ["app", "tests"]
typeCheckingMode = "strict"
pythonVersion = "3.12"
reportMissingImports = "error"
reportUnusedVariable = "warning"
```

### mypy vs pyright

| Feature | mypy | pyright |
|---|---|---|
| Speed | Slow | 3-5x faster |
| Inference | Conservative | Aggressive |
| Editor | LSP available | Built into Pylance |
| Plugins | Many (django, pydantic) | Limited |
| Best for | CI/CD strict mode | Editor experience |

Many teams use **pyright in IDE + mypy in CI**.

---

## 7. Complete `pyproject.toml` Template

```toml
[project]
name = "myapp"
version = "0.1.0"
requires-python = ">=3.12"

# --- Ruff ---
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "C4", "UP", "N", "SIM", "RUF", "S", "ASYNC"]
ignore = ["E501"]

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["S101", "ARG"]

[tool.ruff.format]
quote-style = "double"

# --- Mypy ---
[tool.mypy]
python_version = "3.12"
strict = true
plugins = ["pydantic.mypy", "sqlalchemy.ext.mypy.plugin"]

[[tool.mypy.overrides]]
module = ["legacy.*"]
ignore_errors = true

# --- Pytest ---
[tool.pytest.ini_options]
addopts = "-ra --strict-markers --strict-config"
testpaths = ["tests"]
markers = ["slow", "integration"]

# --- Coverage ---
[tool.coverage.run]
source = ["app"]
branch = true

[tool.coverage.report]
exclude_lines = ["pragma: no cover", "if TYPE_CHECKING:"]
```

---

## 8. Common Gotchas

### Gotcha 1: `Any` defeats the purpose
```python
from typing import Any
def handle(data: Any) -> Any: ...    # ❌ no checking
# Prefer: TypedDict, Protocol, generics
```

### Gotcha 2: Forgetting `TYPE_CHECKING`
```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from heavy_module import HeavyClass    # only imported during type-check

def foo(h: "HeavyClass") -> None: ...
```

### Gotcha 3: Mypy slow on big repos
- Use `mypy --cache-dir=.mypy_cache`
- Run incrementally
- Or switch to pyright

### Gotcha 4: Third-party libs without stubs
```bash
pip install types-requests types-redis types-PyYAML
# Search PyPI for "types-<libname>"
```

### Gotcha 5: Ruff doesn't catch type errors
Ruff is a linter, not a type checker. Use ruff + mypy together.

---

## 9. Interview Questions

**Q1: ruff vs flake8 difference?**
Ruff is 10-100x faster (Rust), replaces flake8 + isort + black + many plugins. Single config.

**Q2: mypy strict mode kya catch karta?**
- Missing type annotations
- `Any` usage warnings
- Implicit Optional
- Unused ignores
- Unreachable code
- Type narrowing failures

**Q3: pre-commit kyu use karte?**
Auto-runs checks before commit — catches issues before push. Saves CI cycles, faster feedback.

**Q4: Type hints runtime pe useful hote?**
- Pydantic: runtime validation
- FastAPI: routing + OpenAPI
- dataclasses: `field` defaults
- Functools singledispatch: based on type

**Q5: mypy errors ignore kaise?**
```python
x: int = "wrong"  # type: ignore[assignment]
```
Use specific code, not bare `# type: ignore` (catches more bugs).

**Q6: Why structural typing (Protocol)?**
Duck typing + type safety. No need to inherit explicitly — if class has matching methods, it's compatible.

---

## 10. Quick Reference Commands

```bash
# Format + lint + fix
ruff format . && ruff check --fix .

# Strict type check
mypy --strict app/

# Run all pre-commit hooks
pre-commit run --all-files

# Update hooks
pre-commit autoupdate

# Profile mypy
mypy --pretty --show-error-codes app/

# Check only changed files (CI)
ruff check $(git diff --name-only HEAD~1 -- '*.py')
```

---

## 11. Best Practices

1. **Adopt strict mode from day 1** on new projects
2. **Enable autofix** in editor (saves cycles)
3. **Run pre-commit on every commit** — no exceptions
4. **CI gates** — block merges on lint failures
5. **Type third-party APIs** — write protocols for external services
6. **Don't `# noqa` without reason** — comment why
7. **Use pyright in IDE, mypy in CI** for best DX
8. **Pin tool versions** — avoid surprise updates breaking CI

---

## Related
- [[../../Phase1_Python_Tooling/01_poetry_uv]] — package management
- [[../../Phase1_Python_Tooling/02_ruff_mypy_precommit]] — basics
- [[04_type_annotations]] — typing details
