# MCP Advanced — Server Development, Transport & Security

**Agentic AI · Modern Topics | Senior AI Engineer**

---

## Quick Concepts

**WHAT:**
- **MCP (Model Context Protocol)** = Anthropic ka open standard jisse Claude ya koi bhi LLM external tools/resources se connect ho sake
- **MCP Server** = tumhara custom tool server — Claude isse tools, resources, prompts expose kar sakta hai
- **Transport** = server aur client ke beech communication ka mechanism (stdio, SSE, HTTP)

**WHY Advanced MCP matters (2025 job market):**
- Har company AI agents build kar rahi hai — MCP integration skill bahut valuable hai
- Custom MCP servers banana = tumhara company-specific data LLM ko de sakte ho securely
- Claude Desktop, Cursor, VSCode — sab MCP support karte hain

**Relation to `04_mcp_complete.md`:**
Woh file MCP basics + client-side usage cover karti hai.
Yeh file = server banano + production deploy karo + security harden karo.

---

## Part 1: MCP Architecture Deep Dive

```
┌─────────────────────────────────────────────────────┐
│              MCP Host (Claude Desktop, etc.)         │
│                                                       │
│  ┌─────────────┐    MCP Protocol    ┌──────────────┐ │
│  │  LLM (Claude)│◄──────────────────►│ MCP Client   │ │
│  └─────────────┘                    └──────┬───────┘ │
└────────────────────────────────────────────┼─────────┘
                                             │ Transport
                              ┌──────────────┼──────────────┐
                              │              │              │
                         stdio (local)   SSE (web)   HTTP Streamable
                              │              │              │
                    ┌─────────▼──────────────▼──────────────▼─────────┐
                    │                   MCP Server                      │
                    │                                                   │
                    │  Tools      Resources      Prompts                │
                    │  ──────    ──────────    ──────────               │
                    │  list()    read()         get()                   │
                    │  call()    subscribe()                            │
                    └───────────────────────────────────────────────────┘
```

### MCP Primitives
| Primitive   | Kya Hai                              | Claude ke liye                         |
|-------------|--------------------------------------|----------------------------------------|
| **Tools**   | Functions jo Claude call kar sakta hai | `execute_sql()`, `send_email()`        |
| **Resources** | Read-only data expose karna         | files, DB rows, API data               |
| **Prompts** | Reusable prompt templates             | "Code review template"                 |
| **Sampling** | Server Claude se text generate karwata hai | Server-side LLM calls        |

---

## Part 2: Building Your First MCP Server (Python)

### Install
```bash
pip install mcp[cli]
```

### Basic Tool Server
```python
# server.py
import asyncio
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp import types

# Server instance create karo
server = Server("my-company-tools")

# --- TOOLS ---
@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """Claude ko batao kaunse tools available hain."""
    return [
        types.Tool(
            name="query_database",
            description="Company database se data query karo. SQL SELECT statements only.",
            inputSchema={
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "SQL SELECT query",
                    },
                    "database": {
                        "type": "string",
                        "enum": ["users_db", "orders_db"],
                        "description": "Database name",
                    }
                },
                "required": ["sql", "database"],
            },
        ),
        types.Tool(
            name="get_employee_info",
            description="Employee information fetch karo by employee ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "employee_id": {"type": "string"},
                },
                "required": ["employee_id"],
            },
        ),
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Tool execute karo."""
    if name == "query_database":
        sql = arguments["sql"]
        database = arguments["database"]

        # SECURITY: Sirf SELECT allow karo
        if not sql.strip().upper().startswith("SELECT"):
            raise ValueError("Only SELECT queries allowed")

        result = await execute_db_query(database, sql)
        return [types.TextContent(type="text", text=str(result))]

    elif name == "get_employee_info":
        employee_id = arguments["employee_id"]
        # Authorization check (neeche dekho)
        info = await fetch_employee(employee_id)
        return [types.TextContent(type="text", text=str(info))]

    else:
        raise ValueError(f"Unknown tool: {name}")


# --- RESOURCES ---
@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    return [
        types.Resource(
            uri="company://docs/api-guide",
            name="API Documentation",
            description="Company internal API guide",
            mimeType="text/markdown",
        ),
    ]

@server.read_resource()
async def handle_read_resource(uri: str) -> str:
    if uri == "company://docs/api-guide":
        with open("docs/api-guide.md") as f:
            return f.read()
    raise ValueError(f"Unknown resource: {uri}")


# --- RUN ---
async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="my-company-tools",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=None,
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Part 3: Transport Options

### stdio Transport (Local — simplest)
```json
// Claude Desktop config: ~/Library/Application Support/Claude/claude_desktop_config.json
{
    "mcpServers": {
        "my-company-tools": {
            "command": "python",
            "args": ["/path/to/server.py"],
            "env": {
                "DB_URL": "postgresql://...",
                "API_KEY": "sk-..."
            }
        }
    }
}
```
- Local process — Claude Desktop subprocess spawn karta hai
- IPC via stdin/stdout
- Best for: local development, personal tools

### SSE Transport (HTTP — web-deployable)
```python
# sse_server.py
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Route, Mount

# SSE transport
sse = SseServerTransport("/messages/")

async def handle_sse(request):
    async with sse.connect_sse(
        request.scope, request.receive, request._send
    ) as streams:
        await server.run(
            streams[0], streams[1],
            InitializationOptions(...),
        )

async def handle_messages(request):
    await sse.handle_post_message(request.scope, request.receive, request._send)

app = Starlette(
    routes=[
        Route("/sse", endpoint=handle_sse),
        Mount("/messages/", app=sse.handle_post_message),
    ]
)

# Run: uvicorn sse_server:app --host 0.0.0.0 --port 8000
```

```json
// Claude Desktop config for remote SSE
{
    "mcpServers": {
        "remote-tools": {
            "url": "https://mcp.yourcompany.com/sse",
            "apiKey": "your-api-key"
        }
    }
}
```

### HTTP Streamable Transport (Latest — 2025)
```python
# Recommended for production web deployments
from mcp.server.streamable_http import StreamableHTTPServerTransport

transport = StreamableHTTPServerTransport(path="/mcp")
# Single endpoint, bidirectional streaming, stateless possible
```

---

## Part 4: Security — Production Hardening

### Authentication
```python
# API Key validation middleware
from starlette.middleware.base import BaseHTTPMiddleware
import hmac

VALID_KEYS = {"sk-mcp-prod-xxxxx", "sk-mcp-staging-xxxxx"}

class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        api_key = request.headers.get("Authorization", "").removeprefix("Bearer ")
        if api_key not in VALID_KEYS:
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        return await call_next(request)
```

### Input Validation (Tool arguments)
```python
from pydantic import BaseModel, validator

class QueryDatabaseArgs(BaseModel):
    sql: str
    database: str

    @validator("sql")
    def validate_sql(cls, v):
        sql_upper = v.strip().upper()
        # Only SELECT
        if not sql_upper.startswith("SELECT"):
            raise ValueError("Only SELECT queries allowed")
        # No subversion attempts
        forbidden = ["DROP", "DELETE", "INSERT", "UPDATE", "EXEC", "--", "/*"]
        if any(kw in sql_upper for kw in forbidden):
            raise ValueError("Forbidden SQL keyword detected")
        # Length limit
        if len(v) > 1000:
            raise ValueError("Query too long")
        return v

    @validator("database")
    def validate_database(cls, v):
        allowed = {"users_db", "orders_db", "products_db"}
        if v not in allowed:
            raise ValueError(f"Database must be one of: {allowed}")
        return v
```

### Authorization (Per-user access control)
```python
@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    # Context me user info extract karo (request se inject kiya)
    user_id = request_context.get("user_id")
    user_role = await get_user_role(user_id)

    if name == "get_employee_info":
        target_employee_id = arguments["employee_id"]

        # HR role ya khud hi dekh sakte hain
        if user_role != "hr" and user_id != target_employee_id:
            raise PermissionError("Access denied: insufficient permissions")

        info = await fetch_employee(target_employee_id)
        # PII masking for non-HR users
        if user_role != "hr":
            info.pop("salary", None)
            info.pop("ssn", None)
        return [types.TextContent(type="text", text=str(info))]
```

### Rate Limiting
```python
from collections import defaultdict
import time

class RateLimiter:
    def __init__(self, max_calls: int = 100, window_seconds: int = 60):
        self.max_calls = max_calls
        self.window = window_seconds
        self.calls: dict[str, list] = defaultdict(list)

    def is_allowed(self, user_id: str) -> bool:
        now = time.time()
        user_calls = self.calls[user_id]
        # Window ke bahar ke calls remove karo
        self.calls[user_id] = [t for t in user_calls if now - t < self.window]
        if len(self.calls[user_id]) >= self.max_calls:
            return False
        self.calls[user_id].append(now)
        return True
```

### Audit Logging (Every tool call log karo)
```python
import json
import logging

audit_logger = logging.getLogger("mcp.audit")

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    user_id = request_context.get("user_id", "unknown")

    # Log BEFORE execution
    audit_logger.info(json.dumps({
        "event": "tool_call",
        "tool": name,
        "user_id": user_id,
        "args": {k: "[REDACTED]" if "key" in k or "password" in k else v
                 for k, v in arguments.items()},
        "timestamp": time.time(),
    }))

    try:
        result = await execute_tool(name, arguments)
        audit_logger.info(json.dumps({"event": "tool_success", "tool": name, "user_id": user_id}))
        return result
    except Exception as e:
        audit_logger.error(json.dumps({"event": "tool_error", "tool": name, "error": str(e)}))
        raise
```

---

## Part 5: Deployment (Docker + Production)

```dockerfile
# Dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt --no-cache-dir
COPY . .
EXPOSE 8000
CMD ["uvicorn", "sse_server:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.yml
services:
  mcp-server:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DB_URL=${DB_URL}
      - MCP_API_KEYS=${MCP_API_KEYS}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf
      - /etc/letsencrypt:/etc/letsencrypt:ro
```

```nginx
# nginx.conf — TLS termination + rate limiting
upstream mcp_backend {
    server mcp-server:8000;
}

limit_req_zone $http_authorization zone=mcp_limit:10m rate=10r/s;

server {
    listen 443 ssl;
    server_name mcp.yourcompany.com;

    ssl_certificate /etc/letsencrypt/live/.../fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/.../privkey.pem;

    location /sse {
        limit_req zone=mcp_limit burst=20 nodelay;
        proxy_pass http://mcp_backend;
        proxy_http_version 1.1;
        proxy_set_header Connection "";   # SSE ke liye important
        proxy_buffering off;
        proxy_read_timeout 3600s;         # SSE long-lived connection
    }
}
```

---

## Part 6: Testing Your MCP Server

```python
# test_server.py
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

@pytest.mark.asyncio
async def test_query_database_tool():
    server_params = StdioServerParameters(
        command="python",
        args=["server.py"],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Tools list check
            tools = await session.list_tools()
            tool_names = [t.name for t in tools.tools]
            assert "query_database" in tool_names

            # Valid query
            result = await session.call_tool(
                "query_database",
                {"sql": "SELECT id, name FROM users LIMIT 5", "database": "users_db"}
            )
            assert result.content[0].type == "text"

            # Invalid query (should fail)
            with pytest.raises(Exception):
                await session.call_tool(
                    "query_database",
                    {"sql": "DROP TABLE users", "database": "users_db"}
                )
```

---

## Interview Q&A

**Q: MCP Server banane me sabse bada security risk kya hai?**
A: Tool poisoning aur excessive permissions. MCP server ke tools agar bahut broad access dete hain (jaise full DB write access), aur agar Claude manipulated prompt se unhe call kare, to serious data damage ho sakta hai. Defense: whitelist-only tools, input validation (Pydantic), authorization checks per call, audit logging mandatory.

**Q: stdio vs SSE transport kab choose karo?**
A: stdio = local only, sirf same machine pe. SSE = remote, multi-user, web deploy possible. Team me share karna hai? → SSE. Personal development tool? → stdio. Production AI platform? → SSE ya HTTP Streamable + HTTPS + auth.

**Q: MCP Resources aur Tools me kya fark hai?**
A: Resources = read-only data exposed karta hai (files, DB rows, API responses) — Claude context me use karta hai. Tools = functions jo execute hoti hain side effects ke saath (DB write, API call, email send). Dono useful hain, par tools = higher risk.

**Q: Multiple MCP servers ek saath use karna possible hai?**
A: Haan, Claude Desktop me multiple MCP servers configure kar sakte ho — har ek ka apna namespace hota hai. Tools from different servers by name access hotey hain. Conflict resolution: latest registered tool wins (generally avoid naming conflicts).

---

## Related Topics
- `04_mcp_complete.md` (Level7) — MCP basics + client usage
- `09_ai_security_threats.md` (Modern_Topics) — Tool poisoning defense
- `02_langgraph_complete.md` (Level7) — LangGraph + MCP integration
