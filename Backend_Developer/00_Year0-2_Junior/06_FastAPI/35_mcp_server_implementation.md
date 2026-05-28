# FastAPI — MCP (Model Context Protocol) Server Implementation
**FastAPI · Year 0-2 | Senior Backend + Agentic AI**

## Quick Concepts
- **MCP** = Model Context Protocol — Anthropic's open standard (2024-26) for LLM ↔ external systems
- **Why MCP** = Same way HTTP standardized web APIs, MCP standardizes AI tools
- **MCP Server** = your backend exposes capabilities (tools, resources, prompts) via MCP
- **MCP Client** = Claude Desktop, IDEs, agents — connect to multiple MCP servers
- **Transports** = `stdio` (local), `SSE` (HTTP-based), `streamable HTTP` (newer)
- **Primitives**:
  - **Tools** — functions LLM can call (like `function calling`, but standardized)
  - **Resources** — data LLM can read (files, DB rows, APIs)
  - **Prompts** — reusable prompt templates
- **Bidirectional** = server can request LLM completions too (sampling)

---

## Why Backend Devs Care

Without MCP:
```
Each AI tool needs custom integration → exponential N × M problem
ChatGPT × Slack, ChatGPT × GitHub, Claude × Slack, Claude × GitHub...
```

With MCP:
```
Build ONE MCP server → works with Claude, Cursor, Continue, etc.
Standard protocol = portable AI integrations
```

---

## Architecture

```
┌──────────────────┐         ┌──────────────────┐
│  MCP Client      │ <─────> │  MCP Server      │
│  (Claude Desktop │  JSON   │  (Your FastAPI)  │
│   IDE, Agent)    │  RPC    │                  │
└──────────────────┘         └──────────────────┘
        │                            │
        │                            ├── Tools (functions)
        │                            ├── Resources (data)
        │                            └── Prompts (templates)
        ↓
┌──────────────────┐
│  LLM (Claude/    │
│   GPT-4, etc.)   │
└──────────────────┘
```

---

## Interview Questions & Answers

### Q1: Basic MCP server in Python — minimal example?

**Answer:** Use the official `mcp` SDK.

```bash
pip install mcp
```

```python
# server.py
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("acme-backend")

@mcp.tool()
def get_user_orders(user_id: int, limit: int = 10) -> list[dict]:
    """Fetch order history for a user."""
    # Your DB logic
    return [
        {"id": 1, "total": 999.99, "status": "shipped"},
        {"id": 2, "total": 49.99, "status": "delivered"},
    ][:limit]

@mcp.resource("config://settings")
def get_settings() -> str:
    """Application settings."""
    return "max_users=1000\ntimeout=30"

@mcp.prompt()
def order_analysis_prompt(user_id: int) -> str:
    """Generate prompt for analyzing user orders."""
    return f"Analyze the order patterns for user {user_id} and suggest improvements."

if __name__ == "__main__":
    mcp.run(transport="stdio")  # local; use "sse" for HTTP
```

**Test with Claude Desktop:**
```json
// ~/Library/Application Support/Claude/claude_desktop_config.json
{
  "mcpServers": {
    "acme-backend": {
      "command": "python",
      "args": ["/path/to/server.py"]
    }
  }
}
```

---

### Q2: MCP server as HTTP/SSE (production deployment)?

**Answer:** Use SSE transport — runs as web service.

```python
# server_sse.py
from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.requests import Request

mcp = FastMCP("acme-backend-http")

@mcp.tool()
async def search_products(query: str, limit: int = 10) -> list[dict]:
    """Search products by name."""
    # Async DB call
    from app.db import async_session
    async with async_session() as session:
        result = await session.execute(
            "SELECT id, name, price FROM products WHERE name ILIKE :q LIMIT :l",
            {"q": f"%{query}%", "l": limit},
        )
        return [dict(r._mapping) for r in result.all()]

# ─── Wrap in Starlette/FastAPI app ───
sse_transport = SseServerTransport("/messages/")

async def handle_sse(request: Request):
    async with sse_transport.connect_sse(
        request.scope, request.receive, request._send
    ) as (read_stream, write_stream):
        await mcp._mcp_server.run(
            read_stream,
            write_stream,
            mcp._mcp_server.create_initialization_options(),
        )

app = Starlette(routes=[
    Route("/sse", endpoint=handle_sse),
    Mount("/messages/", app=sse_transport.handle_post_message),
])

# Run: uvicorn server_sse:app --port 8080
```

**Mount inside FastAPI:**
```python
from fastapi import FastAPI

api = FastAPI()

# Your normal API routes
@api.get("/health")
def health():
    return {"ok": True}

# Mount MCP at /mcp
api.mount("/mcp", app)
```

---

### Q3: Tools with rich parameters + Pydantic?

**Answer:** FastMCP auto-derives schema from type hints (Pydantic-compatible).

```python
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

class OrderStatus(str, Enum):
    PENDING = "pending"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"

class OrderFilter(BaseModel):
    status: OrderStatus | None = Field(None, description="Filter by status")
    min_amount: float = Field(0, description="Minimum order amount")
    max_amount: float = Field(1_000_000, description="Maximum order amount")
    after_date: datetime | None = Field(None, description="Orders after this date")
    limit: int = Field(20, ge=1, le=100)

@mcp.tool()
async def search_orders(filter: OrderFilter) -> list[dict]:
    """Search orders with filters. Returns matching orders sorted by date desc."""
    conditions = ["total >= :min_amt", "total <= :max_amt"]
    params = {"min_amt": filter.min_amount, "max_amt": filter.max_amount, "lim": filter.limit}

    if filter.status:
        conditions.append("status = :status")
        params["status"] = filter.status.value
    if filter.after_date:
        conditions.append("created_at >= :after")
        params["after"] = filter.after_date

    where = " AND ".join(conditions)
    async with async_session() as session:
        result = await session.execute(
            f"SELECT id, total, status, created_at FROM orders WHERE {where} ORDER BY created_at DESC LIMIT :lim",
            params,
        )
        return [dict(r._mapping) for r in result.all()]
```

The LLM sees:
```json
{
  "name": "search_orders",
  "description": "Search orders with filters...",
  "inputSchema": {
    "type": "object",
    "properties": {
      "filter": {
        "$ref": "#/$defs/OrderFilter"
      }
    },
    "$defs": {
      "OrderFilter": {
        "properties": {
          "status": {"enum": ["pending", "shipped", ...]},
          "min_amount": {"type": "number"},
          ...
        }
      }
    }
  }
}
```

---

### Q4: Resources (data exposure) — when to use vs tools?

**Answer:**
- **Tool** = action LLM can perform (POST/mutate or compute)
- **Resource** = data LLM can read (GET-like, no side effects)

```python
@mcp.resource("orders://recent")
async def recent_orders() -> str:
    """Last 50 orders across the system (admin view)."""
    async with async_session() as session:
        result = await session.execute(
            "SELECT id, user_id, total, status FROM orders ORDER BY created_at DESC LIMIT 50"
        )
        rows = [dict(r._mapping) for r in result.all()]
    return json.dumps(rows, default=str)

# Dynamic resource (URI template)
@mcp.resource("user://{user_id}/profile")
async def user_profile(user_id: int) -> str:
    """Full profile for a specific user."""
    async with async_session() as session:
        result = await session.execute(
            "SELECT id, name, email, created_at FROM users WHERE id = :uid",
            {"uid": user_id},
        )
        row = result.first()
    return json.dumps(dict(row._mapping), default=str) if row else "{}"

@mcp.resource("docs://api-reference")
def api_reference() -> str:
    """API documentation in markdown."""
    with open("docs/api.md") as f:
        return f.read()
```

**Client usage:** LLM/user explicitly requests resources via URI, unlike tools which LLM picks autonomously.

---

### Q5: Prompts — reusable templates with arguments?

**Answer:** Server-defined templates that clients can invoke.

```python
@mcp.prompt()
def analyze_order(user_id: int, time_period: str = "30 days") -> list[dict]:
    """Generate a structured prompt to analyze a user's orders."""
    return [
        {
            "role": "user",
            "content": {
                "type": "text",
                "text": f"""Analyze the order patterns for user {user_id} over the last {time_period}.

Specifically look for:
1. Average order value trends
2. Category preferences
3. Frequency patterns
4. Suggestions for upselling

Use the `search_orders` tool to fetch data first.""",
            },
        }
    ]

@mcp.prompt()
def code_review(repo: str, pr_number: int) -> list[dict]:
    """Code review prompt template."""
    return [
        {
            "role": "user",
            "content": {
                "type": "text",
                "text": f"Review PR #{pr_number} in {repo}. Check for: security, performance, style, tests.",
            },
        }
    ]
```

**Client picks prompt** → fills args → sends to LLM → LLM may call tools to fulfill.

---

### Q6: Authentication for MCP server?

**Answer:** OAuth 2.1 (MCP standard) or bearer tokens for production.

```python
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Skip auth for public endpoints
        if request.url.path in ("/health", "/.well-known/oauth-authorization-server"):
            return await call_next(request)

        # Validate bearer token
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse({"error": "Missing token"}, status_code=401)

        token = auth_header[7:]
        user = await validate_token(token)  # JWT or DB lookup
        if not user:
            return JSONResponse({"error": "Invalid token"}, status_code=401)

        # Attach user to request state
        request.state.user = user
        return await call_next(request)

app = Starlette(
    routes=[
        Route("/sse", endpoint=handle_sse),
        Mount("/messages/", app=sse_transport.handle_post_message),
    ],
    middleware=[Middleware(AuthMiddleware)],
)

# ─── Per-tool authorization ───
@mcp.tool()
async def admin_delete_user(user_id: int, ctx) -> dict:
    """Delete a user — admin only."""
    user = ctx.request_context.lifespan_context.get("user")
    if not user or user.role != "admin":
        return {"error": "Permission denied"}
    # ... delete
    return {"deleted": True}
```

**OAuth 2.1 metadata endpoint:**
```python
@app.route("/.well-known/oauth-authorization-server")
async def oauth_metadata(request):
    return JSONResponse({
        "issuer": "https://your-mcp-server.com",
        "authorization_endpoint": "https://your-mcp-server.com/oauth/authorize",
        "token_endpoint": "https://your-mcp-server.com/oauth/token",
        "registration_endpoint": "https://your-mcp-server.com/oauth/register",
        "scopes_supported": ["read", "write", "admin"],
    })
```

---

### Q7: MCP client — how does your FastAPI consume MCP servers?

**Answer:** Your backend can also be an MCP client (e.g., connecting to GitHub MCP).

```python
from mcp import ClientSession
from mcp.client.sse import sse_client

async def query_github_mcp():
    """Connect to a remote MCP server (GitHub's official one)."""
    async with sse_client("https://api.github.com/mcp") as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # List available tools
            tools = await session.list_tools()
            print("Available tools:", [t.name for t in tools.tools])

            # Call a tool
            result = await session.call_tool(
                "list_repositories",
                arguments={"org": "anthropic"},
            )
            return result.content
```

**Pattern: Multi-MCP backend**
```python
class MCPMultiClient:
    def __init__(self):
        self.sessions: dict[str, ClientSession] = {}

    async def connect(self, name: str, url: str):
        read, write = await sse_client(url).__aenter__()
        session = ClientSession(read, write)
        await session.initialize()
        self.sessions[name] = session

    async def call(self, server: str, tool: str, args: dict):
        if server not in self.sessions:
            raise ValueError(f"Unknown server: {server}")
        return await self.sessions[server].call_tool(tool, args)

mcp_client = MCPMultiClient()

@app.on_event("startup")
async def init_mcp():
    await mcp_client.connect("github", "https://api.github.com/mcp")
    await mcp_client.connect("linear", "https://api.linear.app/mcp")
    await mcp_client.connect("slack", "https://slack.com/mcp")

@app.post("/agent/run")
async def agent_orchestrator(task: str):
    # LLM picks which MCP server's tool to use
    # ... full agent loop
    pass
```

---

### Q8: Production deployment + monitoring?

**Answer:** Same patterns as any FastAPI service.

```python
# server_production.py
import logging
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP
from prometheus_client import Counter, Histogram, make_asgi_app

# ─── Metrics ───
tool_calls_total = Counter("mcp_tool_calls_total", "Total tool calls", ["tool", "status"])
tool_call_duration = Histogram("mcp_tool_call_duration_seconds", "Tool call duration", ["tool"])

mcp = FastMCP("production-server")

# ─── Wrap tools with metrics ───
def monitored_tool(name: str):
    def decorator(fn):
        @mcp.tool(name=name)
        async def wrapper(*args, **kwargs):
            with tool_call_duration.labels(tool=name).time():
                try:
                    result = await fn(*args, **kwargs)
                    tool_calls_total.labels(tool=name, status="success").inc()
                    return result
                except Exception as e:
                    tool_calls_total.labels(tool=name, status="error").inc()
                    logging.exception(f"Tool {name} failed")
                    raise
        return wrapper
    return decorator

@monitored_tool("search_orders")
async def search_orders(filter: OrderFilter) -> list[dict]:
    # ...
    pass

# ─── Mount metrics endpoint ───
metrics_app = make_asgi_app()

app = Starlette(routes=[
    Route("/sse", endpoint=handle_sse),
    Mount("/messages/", app=sse_transport.handle_post_message),
    Mount("/metrics", app=metrics_app),  # Prometheus scrape
])
```

**Dockerfile:**
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8080
CMD ["uvicorn", "server_production:app", "--host", "0.0.0.0", "--port", "8080"]
```

**Kubernetes deployment:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mcp-server
spec:
  replicas: 3
  selector:
    matchLabels:
      app: mcp-server
  template:
    metadata:
      labels:
        app: mcp-server
    spec:
      containers:
      - name: mcp
        image: yourorg/mcp-server:latest
        ports:
        - containerPort: 8080
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-creds
              key: url
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
        readinessProbe:
          httpGet:
            path: /health
            port: 8080
```

---

## When to Build an MCP Server vs Plain FastAPI

| Use MCP when... | Use plain FastAPI when... |
|---|---|
| Want Claude Desktop/Cursor/IDE integration | Building user-facing web/mobile app |
| Tools need to work across multiple LLM clients | Single LLM provider integration |
| Standardization matters (open ecosystem) | Custom protocol is fine |
| Bidirectional (server requests LLM completion) | Request-response only |
| Want to expose tools to agents broadly | Closed product |

**Common pattern:** Build BOTH — plain FastAPI for your app + MCP server for AI integrations.

---

## Production Gotchas

| Gotcha | Fix |
|---|---|
| stdio only works locally | Use SSE/HTTP for production |
| No auth in default examples | Add OAuth 2.1 or bearer middleware |
| Tools return huge JSON | Paginate; respect MCP message size limits |
| Long-running tools block | Use async + progress notifications |
| Schema changes break clients | Version your server (`v1`, `v2`) |
| No observability | Add Prometheus + structured logs |
| Client disconnects mid-call | Idempotent tool design |
| Resource URIs collide | Namespace properly (`repo://`, `user://`) |

---

## Senior-level Checklist

- [ ] Use `FastMCP` SDK (official Python)
- [ ] SSE transport for HTTP deployment
- [ ] Pydantic models for tool parameters
- [ ] Resources for read-only data (vs tools for actions)
- [ ] Prompts for reusable LLM templates
- [ ] OAuth 2.1 or bearer auth middleware
- [ ] Per-tool authorization (RBAC inside tools)
- [ ] Async tools (don't block server)
- [ ] Prometheus metrics + structured logging
- [ ] Kubernetes deployment with health checks
- [ ] Versioned server (`/mcp/v1`, `/mcp/v2`)
- [ ] OAuth metadata endpoint for discovery
- [ ] Pagination for large result sets

---

## Related Docs
- `31_llm_integration_fastapi.md` — base LLM patterns
- `32_function_calling_endpoints.md` — non-MCP tool calling
- `33_prompt_injection_security.md` — securing MCP tool inputs
- `01_Year3-4_Mid/05_Microservices/02_api_gateway_service_comm.md` — service mesh
- `01_Year3-4_Mid/04_DevOps/06_kubernetes_helm.md` — K8s deployment

## External References
- MCP spec: https://modelcontextprotocol.io
- Python SDK: https://github.com/modelcontextprotocol/python-sdk
- Anthropic MCP: https://docs.anthropic.com/en/docs/agents-and-tools/mcp
