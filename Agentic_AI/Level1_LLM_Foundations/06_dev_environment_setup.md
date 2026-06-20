# Level 1 — Doc 6: Dev Environment Setup

> **Goal:** Production-grade Python + AI dev env. 30 mins setup, save days later.

---

## 1. Python Version

Use **Python 3.10+** (3.11 or 3.12 ideal).

```bash
python3 --version  # Should be 3.10+
```

If older: install latest via pyenv:
```bash
brew install pyenv
pyenv install 3.12.5
pyenv global 3.12.5
```

---

## 2. Package Manager: uv (Recommended)

**uv** is the modern Python package manager — 10-100x faster than pip.

```bash
# Install
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create project
mkdir my_ai_project && cd my_ai_project
uv init

# Add dependencies
uv add openai anthropic litellm instructor pydantic python-dotenv
```

### Alternative: Poetry
```bash
brew install poetry
poetry init
poetry add openai anthropic ...
```

### Old way: pip + venv
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install openai anthropic ...
```

---

## 3. Recommended Project Structure

```
my_ai_project/
├── .venv/                    # Virtual env (gitignored)
├── .env                      # API keys (gitignored)
├── .env.example              # Template (committed)
├── .gitignore
├── pyproject.toml            # Dependencies
├── README.md
├── src/
│   ├── __init__.py
│   ├── agents/               # Your agents
│   ├── tools/                # Tool functions
│   ├── prompts/              # Prompt templates
│   └── config.py             # Configuration
├── tests/
│   ├── test_agents.py
│   └── test_tools.py
└── scripts/
    └── run_agent.py
```

---

## 4. API Keys Setup

### Step 1: Get API keys

| Provider | Where |
|---|---|
| OpenAI | https://platform.openai.com → API keys |
| Anthropic | https://console.anthropic.com → API keys |
| Google AI | https://aistudio.google.com → API keys (free) |
| Tavily (search) | https://tavily.com (1K calls free) |

### Step 2: Create `.env` file

```bash
# .env (NEVER commit this!)
OPENAI_API_KEY=sk-proj-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=...
TAVILY_API_KEY=tvly-...

# Optional but useful
LANGCHAIN_API_KEY=ls__...    # LangSmith tracing
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=my-agent
```

### Step 3: Create `.gitignore`

```gitignore
# .gitignore
.env
.venv/
__pycache__/
*.pyc
.pytest_cache/
*.log
.DS_Store
```

### Step 4: Load env in code

```python
from dotenv import load_dotenv
import os

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("Missing OPENAI_API_KEY in .env")
```

---

## 5. Essential Packages

### Core (always)
```bash
uv add openai anthropic litellm instructor pydantic python-dotenv tiktoken
```

### LLM Frameworks
```bash
uv add langchain langgraph langchain-openai langchain-anthropic
```

### RAG / Vector DBs
```bash
uv add chromadb pinecone-client pgvector psycopg2-binary sentence-transformers
```

### Backend
```bash
uv add fastapi uvicorn[standard] sqlalchemy alembic
```

### Search Tools
```bash
uv add tavily-python duckduckgo-search
```

### Observability
```bash
uv add langsmith langfuse logfire
```

### Testing
```bash
uv add --dev pytest pytest-asyncio pytest-cov httpx
```

### Dev Tools
```bash
uv add --dev ruff mypy pre-commit ipykernel jupyter
```

---

## 6. IDE Setup

### VS Code (Recommended)

Install extensions:
- **Python** (Microsoft)
- **Pylance**
- **Ruff** (linter/formatter)
- **GitHub Copilot** or **Cursor** for AI assist
- **Jupyter** for notebooks

**settings.json:**
```json
{
    "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
    "python.analysis.typeCheckingMode": "basic",
    "editor.formatOnSave": true,
    "[python]": {
        "editor.defaultFormatter": "charliermarsh.ruff"
    }
}
```

### Cursor (Alternative)
AI-first IDE built on VS Code. Has built-in chat with Claude/GPT-4.

### PyCharm
Heavyweight but powerful. Good for large projects.

---

## 7. Linting & Formatting

### Ruff (Modern Choice)

`pyproject.toml`:
```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "C4", "UP"]
ignore = ["E501"]  # Line too long
```

Run:
```bash
ruff check .       # Lint
ruff format .      # Format
```

### mypy (Type Checking)

`pyproject.toml`:
```toml
[tool.mypy]
python_version = "3.11"
strict = true
ignore_missing_imports = true
```

Run:
```bash
mypy src/
```

---

## 8. Pre-commit Hooks

Auto-check before every commit.

`.pre-commit-config.yaml`:
```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.0
    hooks:
      - id: ruff
      - id: ruff-format
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
```

Install:
```bash
pre-commit install
```

---

## 9. Tokenizer Playground

For understanding tokens:
```python
# tools/tokenize.py
import tiktoken

def count(text: str, model: str = "gpt-4o-mini") -> int:
    # `model` arg ko use karo (hardcode "gpt-4o" mat karo) — warna non-4o model pe galat encoding milti hai
    enc = tiktoken.encoding_for_model(model)
    tokens = enc.encode(text)
    print(f"Text: {text[:60]}...")
    print(f"Tokens: {len(tokens)}")
    print(f"Cost (4o-mini): ${len(tokens) * 0.15 / 1_000_000:.6f}")
    return len(tokens)

count("Hello world")
count("Hello dünya")  # Non-English uses more tokens
```

Online playground: https://platform.openai.com/tokenizer

---

## 10. First "Hello World" — Verify Setup

```python
# scripts/hello_world.py
from dotenv import load_dotenv
from openai import OpenAI
from anthropic import Anthropic

load_dotenv()

# OpenAI
openai_client = OpenAI()
resp = openai_client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Say 'OpenAI working'"}]
)
print(f"OpenAI: {resp.choices[0].message.content}")

# Anthropic
anthropic_client = Anthropic()
resp = anthropic_client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=50,
    messages=[{"role": "user", "content": "Say 'Claude working'"}]
)
print(f"Claude: {resp.content[0].text}")

print("\n✅ Dev env set up correctly!")
```

Run: `python scripts/hello_world.py`

---

## 11. Useful CLI Tools

```bash
# Async LLM REPL
pip install llm
llm chat -m gpt-4o "What's 2+2?"

# Code search
pip install ripgrep  # rg (faster grep)

# JSON pretty
brew install jq

# HTTP client
brew install httpie
http GET https://api.openai.com/v1/models Authorization:"Bearer $OPENAI_API_KEY"
```

---

## 12. Docker (Production)

`Dockerfile`:
```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install deps
RUN uv sync --frozen

# Copy code
COPY src/ ./src/

# Run
CMD ["uv", "run", "python", "src/main.py"]
```

`docker-compose.yml`:
```yaml
services:
  agent:
    build: .
    env_file: .env
    ports:
      - "8000:8000"
  redis:
    image: redis:7-alpine
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_PASSWORD: dev
```

---

## 13. Monitoring & Tracing (Bonus)

### LangSmith
```bash
uv add langsmith
```
```python
# Set env vars (already in .env)
# LANGCHAIN_TRACING_V2=true
# LANGCHAIN_API_KEY=ls__...

# Use any LangChain/LangGraph call — auto-traced
```

### Langfuse (Open source)
```bash
uv add langfuse
```

---

## 14. Common Gotchas

❌ Committing `.env`: Always check `.gitignore`
❌ Mixing global pip + venv: Use venv consistently
❌ Old Python (3.8-3.9): Pydantic v2 features need 3.10+
❌ No API rate limiting: Always wrap with `tenacity`
❌ No `.env.example`: Onboarding becomes painful

---

## 15. Quick Checklist

- [ ] Python 3.10+ installed
- [ ] uv (or Poetry) installed
- [ ] Project structure created
- [ ] `.env` with API keys
- [ ] `.env.example` committed
- [ ] `.gitignore` excludes `.env`, `.venv`
- [ ] Core packages installed
- [ ] IDE configured (VS Code/Cursor)
- [ ] Ruff + mypy configured
- [ ] Pre-commit hooks installed
- [ ] Hello world script works for OpenAI + Claude
- [ ] Tokenizer playground working

---

## 16. Key Takeaways

✅ Use Python 3.10+ and **uv** for package management
✅ Standard project structure (src/, tests/, prompts/)
✅ NEVER commit `.env` — use `.env.example` for templates
✅ Install core packages: openai, anthropic, litellm, pydantic, tiktoken
✅ Use Ruff for linting + mypy for types
✅ Set up pre-commit hooks early
✅ Test with hello world before building anything complex

**Next:** [07_first_api_calls.md](07_first_api_calls.md) — Your first real API calls (basic + advanced)
