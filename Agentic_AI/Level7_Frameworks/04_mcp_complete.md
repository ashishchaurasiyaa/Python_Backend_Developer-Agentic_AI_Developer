# MCP (Model Context Protocol) — Architecture, FastMCP Server, Tools & Resources

## Quick Concepts
- **MCP** = Anthropic ka open protocol — AI models ko external tools aur data sources se connect karo
- **MCP Server** = tools/resources expose karta hai (e.g., database access, file system, APIs)
- **MCP Client** = Claude/AI model jo server se connect karta hai aur tools use karta hai
- **FastMCP** = Python library — MCP server banana easy — decorator-based API
- **Tools** = functions AI call kar sakti hai | **Resources** = data AI read kar sakti hai

---

## Interview Questions & Answers

### Q1: MCP architecture kya hai? Client-Server model kaise kaam karta hai?
**Answer:**
```
MCP Architecture:

┌─────────────────────────────────────────────────────┐
│                    HOST APPLICATION                  │
│  (Claude Desktop / Claude Code / Custom AI App)      │
│                                                      │
│   ┌────────────┐         ┌────────────────────────┐  │
│   │   Claude   │◄───────►│      MCP Client        │  │
│   │   Model    │ tool    │  (protocol handler)    │  │
│   └────────────┘  calls  └──────────┬─────────────┘  │
└──────────────────────────────────────┼─────────────────┘
                                       │ stdio / SSE / HTTP
                    ┌──────────────────┼──────────────────┐
                    │                  ▼                   │
                    │        ┌─────────────────┐          │
                    │        │   MCP SERVER    │          │
                    │        │                 │          │
                    │        │  Tools:         │          │
                    │        │  - execute_sql  │          │
                    │        │  - read_file    │          │
                    │        │  - send_email   │          │
                    │        │                 │          │
                    │        │  Resources:     │          │
                    │        │  - database://  │          │
                    │        │  - file://      │          │
                    │        └────────┬────────┘          │
                    │                 │                   │
                    │       ┌─────────▼────────┐         │
                    │       │  External Systems │         │
                    │       │  (DB, APIs, Files)│         │
                    │       └──────────────────┘         │
                    └────────────────────────────────────┘

KEY CONCEPTS:
- Transport: stdio (local process), SSE (server-sent events, HTTP)
- Protocol: JSON-RPC 2.0
- Server capabilities: tools, resources, prompts, sampling
- Tools: AI calls them; Resources: AI reads them (like files/DB tables)
```

---

### Q2: FastMCP server kaise banate hain? Basic tools?
**Answer:**
```python
# pip install fastmcp

from fastmcp import FastMCP
from pydantic import BaseModel
import json
import asyncpg
import httpx
from pathlib import Path

# MCP Server create karo
mcp = FastMCP(
    name="my-tools-server",
    version="1.0.0",
    description="Tools for Python development and data access",
)

# ===== TOOLS =====

# Simple tool
@mcp.tool()
def add_numbers(a: float, b: float) -> float:
    """Add two numbers together."""
    return a + b

# Tool with complex types
@mcp.tool()
def analyze_code(code: str, language: str = "python") -> dict:
    """Analyze code for potential issues and provide feedback.
    
    Args:
        code: The source code to analyze
        language: Programming language (default: python)
    
    Returns:
        Analysis results with issues and suggestions
    """
    # Simplified analysis
    issues = []
    
    if language == "python":
        if "print(" in code and "import logging" not in code:
            issues.append({"type": "warning", "message": "Use logging instead of print()"})
        if "except:" in code and "except Exception" not in code:
            issues.append({"type": "error", "message": "Bare except clause catches everything"})
    
    return {
        "language": language,
        "lines": len(code.split("\n")),
        "issues": issues,
        "score": max(0, 100 - len(issues) * 10),
    }

# Async tool (database access)
@mcp.tool()
async def query_database(sql: str, limit: int = 10) -> list[dict]:
    """Execute a read-only SQL query on the database.
    
    Args:
        sql: SELECT query to execute (only SELECT allowed)
        limit: Maximum rows to return (default: 10)
    """
    if not sql.strip().upper().startswith("SELECT"):
        raise ValueError("Only SELECT queries are allowed")
    
    conn = await asyncpg.connect("postgresql://user:pass@localhost/mydb")
    try:
        # Add LIMIT clause for safety
        safe_sql = f"SELECT * FROM ({sql}) q LIMIT {limit}"
        rows = await conn.fetch(safe_sql)
        return [dict(row) for row in rows]
    finally:
        await conn.close()

# Tool with file operations
@mcp.tool()
def read_log_file(filename: str, last_n_lines: int = 50) -> str:
    """Read the last N lines from a log file.
    
    Args:
        filename: Log file name (in /var/log/ directory)
        last_n_lines: Number of lines to return
    """
    log_path = Path("/var/log") / filename
    
    if not log_path.exists():
        return f"File not found: {filename}"
    
    # Security: only allow .log files in /var/log
    if not log_path.suffix == ".log" or ".." in filename:
        raise ValueError("Invalid filename")
    
    lines = log_path.read_text().splitlines()
    return "\n".join(lines[-last_n_lines:])

# Tool with external API
@mcp.tool()
async def get_github_repo_info(owner: str, repo: str) -> dict:
    """Get information about a GitHub repository.
    
    Args:
        owner: Repository owner username
        repo: Repository name
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}",
            headers={"Accept": "application/vnd.github.v3+json"},
        )
        response.raise_for_status()
        data = response.json()
        
        return {
            "name": data["full_name"],
            "description": data["description"],
            "stars": data["stargazers_count"],
            "language": data["language"],
            "open_issues": data["open_issues_count"],
            "last_updated": data["updated_at"],
        }

# ===== Run server =====
if __name__ == "__main__":
    # stdio transport (local tools)
    mcp.run()
    
    # HTTP/SSE transport (remote access)
    # mcp.run(transport="sse", host="0.0.0.0", port=8080)
```

---

### Q3: MCP Resources kaise expose karte hain?
**Answer:**
```python
from fastmcp import FastMCP
from fastmcp.resources import FileResource, FunctionResource
import asyncpg

mcp = FastMCP("data-server")

# ===== RESOURCES =====

# Static resource (file)
@mcp.resource("config://app-config")
def get_app_config() -> str:
    """Get application configuration."""
    return """
    DATABASE_URL: postgresql://localhost/myapp
    REDIS_URL: redis://localhost:6379
    DEBUG: false
    MAX_WORKERS: 4
    """

# Dynamic resource (database table)
@mcp.resource("db://users")
async def get_users_schema() -> str:
    """Get users table schema and sample data."""
    conn = await asyncpg.connect("postgresql://user:pass@localhost/mydb")
    
    # Schema
    schema = await conn.fetch("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'users'
        ORDER BY ordinal_position
    """)
    
    # Sample data
    sample = await conn.fetch("SELECT * FROM users LIMIT 5")
    await conn.close()
    
    schema_str = "\n".join([f"  {r['column_name']}: {r['data_type']}" for r in schema])
    sample_str = "\n".join([str(dict(r)) for r in sample])
    
    return f"Schema:\n{schema_str}\n\nSample Data:\n{sample_str}"

# Resource with URI template (parameterized)
@mcp.resource("user://{user_id}/profile")
async def get_user_profile(user_id: int) -> str:
    """Get profile for a specific user."""
    conn = await asyncpg.connect("postgresql://user:pass@localhost/mydb")
    user = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
    await conn.close()
    
    if not user:
        return f"User {user_id} not found"
    
    return json.dumps(dict(user), default=str)

# List available resources
@mcp.list_resources()
async def list_resources():
    return [
        {"uri": "config://app-config", "name": "App Config", "mimeType": "text/plain"},
        {"uri": "db://users", "name": "Users Table", "mimeType": "text/plain"},
    ]
```

---

### Q4: Claude Code se MCP server kaise connect karte hain?
**Answer:**
```json
// ~/.claude/claude_desktop_config.json (Claude Desktop)
// OR
// ~/.config/claude/claude_code_config.json (Claude Code CLI)

{
  "mcpServers": {
    "my-tools": {
      "command": "python",
      "args": ["/path/to/my_mcp_server.py"],
      "env": {
        "DATABASE_URL": "postgresql://user:pass@localhost/mydb",
        "GITHUB_TOKEN": "ghp_..."
      }
    },
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/Users/myuser/Documents"]
    },
    "postgres": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-postgres"],
      "env": {
        "POSTGRES_CONNECTION_STRING": "postgresql://user:pass@localhost/mydb"
      }
    }
  }
}
```

```python
# Claude SDK se MCP server use karna (programmatic)
import anthropic

client = anthropic.Anthropic()

# Tool definitions include karo jo MCP server expose karta hai
# (Real MCP SDK integration alag hoti hai)

# Manual MCP-style tool use with Anthropic API
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    tools=[
        {
            "name": "query_database",
            "description": "Execute a SELECT query on the database",
            "input_schema": {
                "type": "object",
                "properties": {
                    "sql": {"type": "string"},
                    "limit": {"type": "integer", "default": 10}
                },
                "required": ["sql"]
            }
        }
    ],
    messages=[
        {"role": "user", "content": "How many users registered this month?"}
    ]
)
```

---

### Q5: Production MCP server — authentication aur security?
**Answer:**
```python
from fastmcp import FastMCP
from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader
import hashlib
import hmac
import os

mcp = FastMCP("secure-server")

# API Key authentication
API_KEY = os.getenv("MCP_API_KEY", "")
api_key_header = APIKeyHeader(name="X-API-Key")

def verify_api_key(api_key: str = Security(api_key_header)) -> bool:
    if not hmac.compare_digest(api_key, API_KEY):
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return True

# Rate-limited tool
import asyncio
from collections import defaultdict
import time

request_counts = defaultdict(list)

def rate_limit(client_id: str, max_per_minute: int = 60):
    now = time.time()
    minute_ago = now - 60
    
    request_counts[client_id] = [
        t for t in request_counts[client_id] if t > minute_ago
    ]
    
    if len(request_counts[client_id]) >= max_per_minute:
        raise ValueError(f"Rate limit exceeded for {client_id}")
    
    request_counts[client_id].append(now)

@mcp.tool()
async def sensitive_operation(data: str, client_id: str = "default") -> str:
    """Perform a sensitive operation with rate limiting."""
    rate_limit(client_id)
    
    # Input sanitization
    if len(data) > 10000:
        raise ValueError("Data too large (max 10000 chars)")
    
    # Audit log
    print(f"[AUDIT] {client_id} called sensitive_operation at {time.time()}")
    
    return f"Processed {len(data)} characters"

# Tool with context/permissions
@mcp.tool()
def read_file(path: str, allowed_dirs: list[str] = None) -> str:
    """Read a file with path restrictions."""
    from pathlib import Path
    
    allowed_dirs = allowed_dirs or ["/safe/directory"]
    file_path = Path(path).resolve()
    
    # Security check
    if not any(str(file_path).startswith(d) for d in allowed_dirs):
        raise PermissionError(f"Access denied to {path}")
    
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    
    return file_path.read_text()

if __name__ == "__main__":
    mcp.run(transport="sse", host="0.0.0.0", port=8080)
```

---

### Q6: MCP aur agentic workflow mein integration?
**Answer:**
```python
# MCP tools + LangGraph agent
from langgraph.prebuilt import create_react_agent
from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool, StructuredTool
import asyncpg

# MCP tools ko LangChain tools mein wrap karo
@tool
async def mcp_query_database(sql: str) -> str:
    """Query the production database (SELECT only)."""
    if not sql.strip().upper().startswith("SELECT"):
        return "Error: Only SELECT queries allowed"
    
    conn = await asyncpg.connect("postgresql://user:pass@localhost/mydb")
    rows = await conn.fetch(sql + " LIMIT 10")
    await conn.close()
    return str([dict(r) for r in rows])

@tool
async def mcp_analyze_code(code: str) -> str:
    """Analyze Python code for issues."""
    issues = []
    if "bare_except" in code:
        issues.append("Bare except clause detected")
    return str({"issues": issues, "score": 100 - len(issues) * 10})

# Create ReAct agent with MCP tools
model = ChatAnthropic(model="claude-sonnet-4-6")
tools = [mcp_query_database, mcp_analyze_code]

agent = create_react_agent(model, tools)

# Run agent
result = agent.invoke({
    "messages": [("user", "How many users signed up today? Also check this code: def foo(): pass")]
})

# KEY CONCEPT: MCP vs direct tool use
# Direct tool use: Tools hardcoded in application
# MCP: Tools are in a separate server process
#      - Can be shared across multiple AI applications
#      - Server can be updated without changing AI app
#      - Multiple AI apps share one database tool server
#      - Better security isolation (separate process)
```
