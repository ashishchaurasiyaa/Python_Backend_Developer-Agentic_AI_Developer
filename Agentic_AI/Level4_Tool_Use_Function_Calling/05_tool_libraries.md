# Level 4 — Doc 5: Building Tool Libraries

> **Goal:** Common tools that production agents need — web search, calculator, file I/O, HTTP, DB queries, email, calendar. Build once, reuse everywhere.

---

## 1. Standard Tool Categories

Every production agent needs tools from these categories:

| Category | Examples |
|---|---|
| **Information retrieval** | web search, KB search, RAG |
| **Computation** | calculator, code execution, data analysis |
| **File I/O** | read file, write file, list directory |
| **HTTP** | GET/POST requests, API calls |
| **Database** | SQL queries, NoSQL queries |
| **Communication** | email, SMS, Slack, push notifications |
| **User actions** | calendar, reminders, contacts |
| **Multimedia** | image gen, OCR, speech-to-text |

---

## 2. Web Search Tools (Most Common Need)

### Option A: Tavily (LangChain default, AI-optimized)
```python
from tavily import TavilyClient

client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

def search_web(query: str, max_results: int = 5) -> dict:
    """Search the web using Tavily (AI-optimized search)."""
    result = client.search(query=query, max_results=max_results)
    return {
        "results": [
            {"title": r["title"], "url": r["url"], "content": r["content"]}
            for r in result["results"]
        ]
    }
```

### Option B: SerpAPI (Google results)
```python
import requests

def search_google(query: str) -> dict:
    params = {
        "q": query,
        "api_key": os.getenv("SERPAPI_KEY")
    }
    response = requests.get("https://serpapi.com/search", params=params)
    return response.json()
```

### Option C: Brave Search (Privacy-focused)
```python
def search_brave(query: str) -> dict:
    headers = {"X-Subscription-Token": os.getenv("BRAVE_API_KEY")}
    response = requests.get(
        "https://api.search.brave.com/res/v1/web/search",
        params={"q": query},
        headers=headers
    )
    return response.json()
```

### Option D: DuckDuckGo (Free, no key)
```python
from duckduckgo_search import DDGS

def search_ddg(query: str, max_results: int = 5) -> list:
    with DDGS() as ddgs:
        return list(ddgs.text(query, max_results=max_results))
```

**Recommendation:** Tavily for production agents (AI-optimized). DuckDuckGo for free experiments.

---

## 3. Calculator (Safe Math)

**Never use raw `eval()`** — security risk.

### Safe approach 1: `sympy`
```python
from sympy import sympify

def calculator(expression: str) -> dict:
    """Safe math evaluator."""
    try:
        result = float(sympify(expression).evalf())
        return {"expression": expression, "result": result}
    except Exception as e:
        return {"error": str(e)}

calculator("2 + 3 * 4")     # 14
calculator("sqrt(16) + 5")  # 9
calculator("sin(pi/2)")     # 1.0
```

### Safe approach 2: `ast.literal_eval` (for basic math)
```python
import ast
import operator

OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}

def safe_eval(node):
    if isinstance(node, ast.Constant):
        return node.value
    elif isinstance(node, ast.BinOp):
        return OPERATORS[type(node.op)](safe_eval(node.left), safe_eval(node.right))
    raise ValueError("Unsafe expression")

def calculator(expr: str):
    return safe_eval(ast.parse(expr, mode='eval').body)
```

---

## 4. Code Execution (Sandboxed)

**Production:** Never run untrusted code in your environment. Use:

### Option A: E2B (Best for production)
```python
from e2b import Sandbox

def execute_python(code: str) -> dict:
    """Execute Python code in isolated sandbox."""
    with Sandbox() as sandbox:
        result = sandbox.run_code(code)
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.exit_code
        }
```

### Option B: Daytona, Modal, Replicate

### Option C: Docker (DIY)
```python
import docker

def execute_python(code: str) -> dict:
    client = docker.from_env()
    container = client.containers.run(
        "python:3.11-slim",
        command=f"python -c '{code}'",
        detach=False,
        remove=True,
        timeout=30,
        mem_limit="256m"
    )
    return {"output": container.decode()}
```

**NEVER do this:**
```python
def bad_executor(code):
    exec(code)  # ← Code runs in YOUR process. Catastrophic.
```

---

## 5. File System Tools

```python
import os
from pathlib import Path

ALLOWED_BASE = Path("/safe/data/dir").resolve()  # Restrict to safe directory


def safe_path(path: str) -> Path:
    """Prevent directory traversal attacks."""
    resolved = (ALLOWED_BASE / path).resolve()
    if not str(resolved).startswith(str(ALLOWED_BASE)):
        raise ValueError("Path outside allowed directory")
    return resolved


def read_file(path: str) -> dict:
    """Read file contents."""
    p = safe_path(path)
    if not p.exists():
        return {"error": "file not found"}
    return {"path": str(p), "content": p.read_text()}


def write_file(path: str, content: str) -> dict:
    """Write content to file."""
    p = safe_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return {"path": str(p), "bytes_written": len(content)}


def list_directory(path: str = ".") -> dict:
    """List files in directory."""
    p = safe_path(path)
    if not p.is_dir():
        return {"error": "not a directory"}
    return {"files": [f.name for f in p.iterdir()]}
```

**Critical:** Always validate paths to prevent directory traversal (../../etc/passwd).

---

## 6. HTTP / API Tools

```python
import requests
from typing import Optional

ALLOWED_DOMAINS = {"api.github.com", "api.openai.com", "your-domain.com"}


def http_get(url: str, headers: Optional[dict] = None) -> dict:
    """Make HTTP GET request to allowed domain."""
    # Security check
    from urllib.parse import urlparse
    domain = urlparse(url).netloc
    if domain not in ALLOWED_DOMAINS:
        return {"error": f"domain {domain} not allowed"}
    
    try:
        response = requests.get(url, headers=headers or {}, timeout=10)
        return {
            "status": response.status_code,
            "body": response.text[:5000],  # Truncate to avoid huge results
            "headers": dict(response.headers)
        }
    except Exception as e:
        return {"error": str(e)}


def http_post(url: str, json_body: dict, headers: Optional[dict] = None) -> dict:
    """Make HTTP POST request."""
    # Same security checks
    try:
        response = requests.post(url, json=json_body, headers=headers or {}, timeout=10)
        return {"status": response.status_code, "body": response.text[:5000]}
    except Exception as e:
        return {"error": str(e)}
```

**Security:** Allowlist domains. Set timeouts. Truncate responses.

---

## 7. Database Tools

```python
import psycopg2
from sqlalchemy import create_engine, text

engine = create_engine(os.getenv("DATABASE_URL"))


def query_database(sql: str) -> dict:
    """Execute SELECT query (read-only). NEVER allow INSERT/UPDATE/DELETE."""
    # CRITICAL: validate query is read-only
    sql_lower = sql.lower().strip()
    forbidden = ["insert", "update", "delete", "drop", "alter", "create"]
    if any(f in sql_lower for f in forbidden):
        return {"error": "Only SELECT queries allowed"}
    
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            rows = [dict(row._mapping) for row in result]
            return {"rows": rows[:100], "total": len(rows)}  # Limit results
    except Exception as e:
        return {"error": str(e)}
```

**Better:** Use **parameterized queries** + give LLM a schema-aware tool:

```python
def query_orders(user_id: int, limit: int = 10) -> dict:
    """Get user's recent orders (safe, parameterized)."""
    sql = text("SELECT * FROM orders WHERE user_id = :uid ORDER BY created_at DESC LIMIT :lim")
    with engine.connect() as conn:
        result = conn.execute(sql, {"uid": user_id, "lim": limit})
        return {"orders": [dict(r._mapping) for r in result]}
```

**Pattern:** Don't expose raw SQL. Build **specific tools** per query type.

---

## 8. Email / Communication Tools

```python
import smtplib
from email.message import EmailMessage


def send_email(to: str, subject: str, body: str, cc: list = None) -> dict:
    """Send an email."""
    msg = EmailMessage()
    msg["From"] = os.getenv("SMTP_FROM")
    msg["To"] = to
    msg["Subject"] = subject
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg.set_content(body)
    
    try:
        with smtplib.SMTP(os.getenv("SMTP_HOST"), 587) as smtp:
            smtp.starttls()
            smtp.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASS"))
            smtp.send_message(msg)
        return {"status": "sent", "to": to}
    except Exception as e:
        return {"error": str(e)}


def send_slack_message(channel: str, text: str) -> dict:
    """Send Slack message via webhook."""
    response = requests.post(
        os.getenv("SLACK_WEBHOOK"),
        json={"channel": channel, "text": text}
    )
    return {"status": "sent" if response.ok else "failed"}
```

**For action tools** (send_email, etc.), **always confirm with user** before destructive ops:
```python
def send_email_with_confirmation(to, subject, body):
    print(f"About to send email to {to}: {subject}")
    confirm = input("Proceed? (y/n): ")
    if confirm.lower() != "y":
        return {"status": "cancelled by user"}
    return send_email(to, subject, body)
```

---

## 9. Calendar / Scheduling Tools

```python
from datetime import datetime, timedelta
# Google Calendar API setup
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


def get_calendar_events(start_date: str, end_date: str) -> dict:
    """Get calendar events between dates."""
    creds = Credentials.from_authorized_user_file('token.json')
    service = build('calendar', 'v3', credentials=creds)
    events = service.events().list(
        calendarId='primary',
        timeMin=start_date,
        timeMax=end_date,
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    return {"events": events.get('items', [])}


def create_event(title: str, start: str, end: str, attendees: list = None) -> dict:
    """Create calendar event."""
    creds = Credentials.from_authorized_user_file('token.json')
    service = build('calendar', 'v3', credentials=creds)
    event = {
        'summary': title,
        'start': {'dateTime': start, 'timeZone': 'UTC'},
        'end': {'dateTime': end, 'timeZone': 'UTC'},
    }
    if attendees:
        event['attendees'] = [{'email': a} for a in attendees]
    created = service.events().insert(calendarId='primary', body=event).execute()
    return {"event_id": created.get('id'), "link": created.get('htmlLink')}
```

---

## 10. Tool Library Architecture

```
tools/
├── __init__.py             # Register all tools
├── search.py               # Web search tools
├── compute.py              # Calculator, code execution
├── files.py                # File I/O
├── http.py                 # HTTP requests
├── database.py             # DB queries
├── communication.py        # Email, Slack, SMS
├── calendar.py             # Calendar tools
├── schemas.py              # OpenAI/Claude schemas
└── registry.py             # Tool registry pattern
```

### Registry pattern:
```python
# tools/registry.py
class ToolRegistry:
    def __init__(self):
        self._tools = {}
        self._schemas = []
    
    def register(self, func, schema):
        self._tools[func.__name__] = func
        self._schemas.append(schema)
    
    def get_function(self, name):
        return self._tools.get(name)
    
    def get_all_schemas(self):
        return self._schemas

# Usage
registry = ToolRegistry()
registry.register(search_web, SEARCH_WEB_SCHEMA)
registry.register(calculator, CALCULATOR_SCHEMA)
# ...
```

---

## 11. Cross-Cutting Concerns

### Logging
```python
def with_logging(tool_func):
    """Decorator to log every tool call."""
    def wrapper(*args, **kwargs):
        start = time.time()
        try:
            result = tool_func(*args, **kwargs)
            logger.info(f"{tool_func.__name__}({kwargs}) → success in {time.time()-start:.2f}s")
            return result
        except Exception as e:
            logger.error(f"{tool_func.__name__}({kwargs}) → error: {e}")
            return {"error": str(e)}
    return wrapper
```

### Rate Limiting
```python
from functools import wraps
from collections import defaultdict
from time import time

call_history = defaultdict(list)

def rate_limit(max_per_minute: int):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            now = time()
            history = call_history[func.__name__]
            history[:] = [t for t in history if now - t < 60]
            if len(history) >= max_per_minute:
                return {"error": "rate limit exceeded"}
            history.append(now)
            return func(*args, **kwargs)
        return wrapper
    return decorator

@rate_limit(max_per_minute=60)
def search_web(query): ...
```

### Caching
```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def cached_search(query: str) -> tuple:
    # Convert dict to tuple for hashability
    result = search_web(query)
    return tuple(result.items())
```

---

## 12. Production Checklist

For every tool in production:
- [ ] Input validation (Pydantic)
- [ ] Output structured (consistent format)
- [ ] Error handling (return dict with `error` key)
- [ ] Logging (every call traced)
- [ ] Rate limiting (prevent abuse)
- [ ] Security (path traversal, SQL injection, etc.)
- [ ] Timeouts (don't hang forever)
- [ ] Resource limits (memory, CPU, file size)
- [ ] Confirmation for destructive ops (delete, send)
- [ ] Tests (unit + integration)

---

## 13. Interview Questions

1. **Q: How do you secure code execution tools?**
   - Sandboxed (E2B, Docker), never `exec()` directly, resource limits, timeout

2. **Q: How do you prevent path traversal in file tools?**
   - Restrict to allowlist directory, validate resolved paths

3. **Q: How do you handle long-running tool calls?**
   - Set timeouts, async execution, return partial results, queue for async retrieval

4. **Q: Why specific DB tools over raw SQL exposure?**
   - Security (no DROP TABLE), predictability, easier to test

---

## 14. Exercises

1. **Easy:** Build calculator + safe file read tools. Test with malicious inputs (path traversal, code injection).
2. **Medium:** Build a tool registry with logging + rate limiting decorators.
3. **Hard:** Build a sandbox for code execution using Docker.
4. **Pro:** Build a "tool marketplace" — plugin system where users can install/uninstall tools.

---

## 15. Key Takeaways

✅ Build a **library** — reuse tools across agents
✅ Categories: search, compute, files, HTTP, DB, comm, calendar
✅ Security first: sandboxes, allowlists, validation, no raw eval
✅ Cross-cutting: logging, rate limiting, caching, timeouts
✅ Destructive ops → require confirmation
✅ Prefer **specific tools** (get_user_orders) over generic (run_sql)
✅ Each tool: structured output (dict with error key)

**Next:** [06_parallel_tool_calls.md](06_parallel_tool_calls.md) — Parallel execution patterns
