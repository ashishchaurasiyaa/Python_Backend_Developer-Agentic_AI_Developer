# Python Packaging — pyproject.toml, Wheel, Entry Points
**Phase 1 Tooling | Senior Backend + Agentic AI**

## Why This Matters
- Senior devs are expected to build reusable packages, not just apps
- Interview question: "How would you package your agent toolkit for the team?"
- MCP servers, LangChain custom tools, and internal SDKs all require proper packaging

---

## 1. Modern Packaging Standard — pyproject.toml

`setup.py` is legacy. Modern Python uses `pyproject.toml` (PEP 517/518/621).

### Minimal pyproject.toml
```toml
[build-system]
requires = ["hatchling"]  # or "setuptools>=61", "flit_core>=3.4"
build-backend = "hatchling.build"

[project]
name = "my-agent-toolkit"
version = "0.1.0"
description = "Reusable tools for LangGraph agents"
readme = "README.md"
license = { file = "LICENSE" }
requires-python = ">=3.11"
authors = [
    { name = "Your Name", email = "you@example.com" }
]
keywords = ["langchain", "agents", "ai"]
classifiers = [
    "Programming Language :: Python :: 3.11",
    "License :: OSI Approved :: MIT License",
]
dependencies = [
    "langchain>=0.2.0",
    "pydantic>=2.0",
    "httpx>=0.27",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "ruff>=0.4",
    "mypy>=1.10",
]
openai = ["openai>=1.0"]
anthropic = ["anthropic>=0.25"]

[project.urls]
Homepage = "https://github.com/you/my-agent-toolkit"
Repository = "https://github.com/you/my-agent-toolkit"
```

---

## 2. Project Structure

```
my-agent-toolkit/
├── pyproject.toml
├── README.md
├── LICENSE
├── src/
│   └── agent_toolkit/
│       ├── __init__.py
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── search.py
│       │   └── database.py
│       ├── agents/
│       │   ├── __init__.py
│       │   └── research.py
│       └── py.typed          ← signals this package ships type stubs
└── tests/
    ├── conftest.py
    └── test_tools.py
```

> **src layout** is preferred over flat layout — prevents accidentally importing
> from the source directory during tests instead of the installed package.

---

## 3. Entry Points — CLI Commands

Entry points register CLI commands when the package is installed.

```toml
[project.scripts]
# After `pip install`, these commands are available in terminal:
agent-run  = "agent_toolkit.cli:run_agent"
agent-init = "agent_toolkit.cli:init_project"

[project.gui-scripts]
# Same but for GUI apps (Windows-safe, no console window)
agent-gui = "agent_toolkit.gui:main"
```

```python
# src/agent_toolkit/cli.py
import argparse

def run_agent():
    """Entrypoint for `agent-run` CLI command."""
    parser = argparse.ArgumentParser(description="Run an agent")
    parser.add_argument("task", help="Task description")
    parser.add_argument("--model", default="gpt-4o", help="LLM model")
    args = parser.parse_args()
    print(f"Running agent for: {args.task} with {args.model}")

def init_project():
    """Entrypoint for `agent-init` CLI command."""
    print("Initializing new agent project...")
```

---

## 4. Plugin Entry Points — Extensibility

Register discoverable plugins without modifying the host package.

```toml
# In a plugin package's pyproject.toml:
[project.entry-points."agent_toolkit.tools"]
my_custom_search = "my_plugin.search:CustomSearchTool"
my_db_reader     = "my_plugin.db:DatabaseReaderTool"
```

```python
# In the host package — discover all registered tools:
import importlib.metadata

def discover_tools() -> dict:
    """Load all tools registered via entry points."""
    tools = {}
    for ep in importlib.metadata.entry_points(group="agent_toolkit.tools"):
        tool_class = ep.load()
        tools[ep.name] = tool_class
    return tools
```

---

## 5. Building and Publishing

```bash
# Install build tools
pip install build twine

# Build wheel + sdist
python -m build
# Creates: dist/my_agent_toolkit-0.1.0-py3-none-any.whl
#          dist/my_agent_toolkit-0.1.0.tar.gz

# Check distribution
twine check dist/*

# Upload to PyPI (use API token, not password)
twine upload dist/*

# Upload to TestPyPI first (safe testing)
twine upload --repository testpypi dist/*
```

### Wheel types
| Wheel | Meaning |
|---|---|
| `my_pkg-0.1.0-py3-none-any.whl` | Pure Python, any platform |
| `my_pkg-0.1.0-cp311-cp311-linux_x86_64.whl` | CPython 3.11, Linux only (C extensions) |

---

## 6. Development Install

```bash
# Editable install — changes in src/ are immediately reflected
pip install -e ".[dev]"

# With extras
pip install -e ".[dev,openai,anthropic]"
```

---

## 7. Versioning — Semantic Versioning

```
MAJOR.MINOR.PATCH
  1.2.3
  │ │ └── Patch: bug fixes, no API change
  │ └──── Minor: new features, backwards compatible
  └────── Major: breaking changes
```

```toml
# Dynamic version from git tag (hatchling)
[project]
dynamic = ["version"]

[tool.hatch.version]
source = "vcs"  # reads from git tags

# Or from __version__ in __init__.py
[tool.hatch.version]
path = "src/agent_toolkit/__init__.py"
```

---

## 8. py.typed — Ship Type Information

To make your package type-safe for users:

```bash
touch src/agent_toolkit/py.typed   # empty marker file
```

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/agent_toolkit"]
include = ["py.typed"]
```

Users get full mypy/pyright type checking when using your package.

---

## 9. Configuring Tools in pyproject.toml

Everything in one file:

```toml
[tool.ruff]
line-length = 88
target-version = "py311"
select = ["E", "F", "I", "N", "UP"]

[tool.mypy]
python_version = "3.11"
strict = true
ignore_missing_imports = true

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[tool.coverage.run]
source = ["src"]
omit = ["tests/*"]
```

---

## 10. Interview Questions

**Q1: What is the difference between wheel and sdist?**
Wheel (`.whl`) is pre-built — fast install, no build step.
Sdist (`.tar.gz`) is source distribution — requires build on install.
Always ship both; PyPI prefers wheel.

**Q2: What is an editable install and when do you use it?**
`pip install -e .` installs the package in "development mode" — Python imports
directly from `src/`, so changes are live without reinstalling. Use during development.

**Q3: What is `src` layout and why is it preferred?**
Placing source under `src/` prevents accidental imports from the working directory
during tests. Without it, `import my_package` could load from the local folder
instead of the installed version, hiding bugs.

**Q4: What are entry points?**
Entry points register commands or plugin hooks in package metadata.
`[project.scripts]` creates CLI commands; `[project.entry-points."group"]`
enables plugin discovery without hardcoded imports.

**Q5: What is `py.typed`?**
An empty marker file (PEP 561) that tells mypy/pyright that your package
ships type annotations. Without it, type checkers ignore your package's types.
