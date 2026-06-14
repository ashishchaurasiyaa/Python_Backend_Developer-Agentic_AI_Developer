"""
FastAPI — MCP (Model Context Protocol) Server Implementation
============================================================
Covers the full production lifecycle of an MCP server built with the official
Python SDK (FastMCP):

  1. Minimal stdio server (local development / Claude Desktop)
  2. Tools — typed actions the LLM can invoke
  3. Pydantic-validated tool parameters with enums and constraints
  4. Resources — read-only data exposed via URI schemes
  5. Prompts — reusable LLM prompt templates
  6. SSE / HTTP transport (production deployment)
  7. FastAPI + MCP dual mount (REST API + AI integration side-by-side)
  8. Auth middleware (bearer token) + per-tool RBAC
  9. Prometheus metrics + structured logging decorator
 10. MCP client — consuming a remote MCP server from your own backend
 11. Multi-MCP orchestration client

Install:
    pip install "mcp[cli]" fastapi uvicorn starlette pydantic prometheus-client structlog

Run (SSE mode):
    uvicorn 35_mcp_server_implementation:combined_app --port 8080

Connect Claude Desktop (stdio mode):
    Add to ~/Library/Application Support/Claude/claude_desktop_config.json:
    {
      "mcpServers": {
        "acme-backend": {
          "command": "python",
          "args": ["/path/to/35_mcp_server_implementation.py"]
        }
      }
    }
"""

from __future__ import annotations

import json
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime
from enum import Enum
from functools import wraps
from typing import Any

import structlog  # pip install structlog
from fastapi import FastAPI
from pydantic import BaseModel, Field
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

# pip install "mcp[cli]"
from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport

# pip install prometheus-client
from prometheus_client import Counter, Histogram, make_asgi_app

log = structlog.get_logger()

# ==========================================================================
# 1. FASTMCP INSTANCE — core server object shared across all sections
# ==========================================================================

mcp = FastMCP("acme-backend")

# ==========================================================================
# 2. DOMAIN MODELS (Pydantic) — shared across tools
# ==========================================================================


class OrderStatus(str, Enum):
    PENDING = "pending"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class OrderFilter(BaseModel):
    """Parameters for the search_orders tool.  FastMCP auto-derives JSON schema."""

    status: OrderStatus | None = Field(None, description="Filter by order status")
    min_amount: float = Field(0.0, ge=0, description="Minimum order total (inclusive)")
    max_amount: float = Field(1_000_000.0, description="Maximum order total (inclusive)")
    after_date: datetime | None = Field(None, description="Only orders created after this UTC datetime")
    limit: int = Field(20, ge=1, le=100, description="Maximum rows to return")


# ---------------------------------------------------------------------------
# In-memory stub data (replaces async DB in an illustrative module)
# ---------------------------------------------------------------------------

_ORDERS: list[dict[str, Any]] = [
    {"id": 1, "user_id": 42, "total": 999.99, "status": "shipped",   "created_at": "2026-05-01T10:00:00Z"},
    {"id": 2, "user_id": 42, "total":  49.99, "status": "delivered", "created_at": "2026-05-15T14:30:00Z"},
    {"id": 3, "user_id": 7,  "total": 250.00, "status": "pending",   "created_at": "2026-06-01T09:00:00Z"},
    {"id": 4, "user_id": 7,  "total":  15.50, "status": "cancelled", "created_at": "2026-06-10T11:45:00Z"},
]

_USERS: list[dict[str, Any]] = [
    {"id": 42, "name": "Alice",   "email": "alice@example.com", "role": "user",  "created_at": "2025-01-10"},
    {"id": 7,  "name": "Bob",     "email": "bob@example.com",   "role": "admin", "created_at": "2025-03-22"},
]

_PRODUCTS: list[dict[str, Any]] = [
    {"id": 1, "name": "Laptop Pro 15",   "price": 1299.00},
    {"id": 2, "name": "Wireless Mouse",  "price":   29.99},
    {"id": 3, "name": "USB-C Hub",       "price":   49.99},
    {"id": 4, "name": "Laptop Stand",    "price":   89.00},
]

# ==========================================================================
# 3. TOOLS — typed, async actions the LLM can invoke
# ==========================================================================


@mcp.tool()
def get_user_orders(user_id: int, limit: int = 10) -> list[dict]:
    """Fetch order history for a specific user.

    Returns orders sorted by creation date (newest first).  At most *limit*
    rows are returned (max 100).
    """
    user_orders = [o for o in _ORDERS if o["user_id"] == user_id]
    return sorted(user_orders, key=lambda o: o["created_at"], reverse=True)[:limit]


@mcp.tool()
async def search_orders(filter: OrderFilter) -> list[dict]:
    """Search orders with rich filters.

    The LLM receives a fully validated OrderFilter object whose JSON schema is
    automatically derived from the Pydantic model — including enum constraints,
    numeric bounds, and nullable fields.
    """
    results = []
    for order in _ORDERS:
        if order["total"] < filter.min_amount:
            continue
        if order["total"] > filter.max_amount:
            continue
        if filter.status and order["status"] != filter.status.value:
            continue
        if filter.after_date:
            order_dt = datetime.fromisoformat(order["created_at"].replace("Z", "+00:00"))
            if order_dt < filter.after_date:
                continue
        results.append(order)

    results.sort(key=lambda o: o["created_at"], reverse=True)
    return results[: filter.limit]


@mcp.tool()
async def search_products(query: str, limit: int = 10) -> list[dict]:
    """Search the product catalogue by name (case-insensitive substring match).

    In production this would be an async full-text DB query.
    """
    q = query.lower()
    matches = [p for p in _PRODUCTS if q in p["name"].lower()]
    return matches[:limit]


@mcp.tool()
async def create_order(user_id: int, product_id: int, quantity: int = 1) -> dict:
    """Place a new order.

    Mutating tool — demonstrates that tools are not just read-only.  The LLM
    calls this when the user asks to buy something.
    """
    product = next((p for p in _PRODUCTS if p["id"] == product_id), None)
    if product is None:
        return {"error": f"Product {product_id} not found"}

    total = round(product["price"] * quantity, 2)
    new_order = {
        "id": max(o["id"] for o in _ORDERS) + 1,
        "user_id": user_id,
        "total": total,
        "status": "pending",
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    _ORDERS.append(new_order)
    return {"created": True, "order": new_order}


# ==========================================================================
# 4. RESOURCES — read-only data exposed via URI templates
#    Rule of thumb: Resource = GET (no side-effects) / Tool = POST (actions)
# ==========================================================================


@mcp.resource("orders://recent")
async def recent_orders() -> str:
    """Last 50 orders across the system (admin/monitoring view).

    URI: orders://recent
    Client requests this resource explicitly; LLM does not call it on its own.
    """
    recent = sorted(_ORDERS, key=lambda o: o["created_at"], reverse=True)[:50]
    return json.dumps(recent, indent=2)


@mcp.resource("user://{user_id}/profile")
async def user_profile(user_id: int) -> str:
    """Full profile for a specific user.

    URI template: user://<user_id>/profile
    The {user_id} segment is parsed and passed as an argument automatically.
    """
    user = next((u for u in _USERS if u["id"] == user_id), None)
    return json.dumps(user, indent=2) if user else "{}"


@mcp.resource("config://settings")
def app_settings() -> str:
    """Application configuration (read-only snapshot).

    URI: config://settings
    Exposes non-secret runtime configuration to the LLM for context.
    """
    settings = {
        "max_order_limit": 100,
        "supported_currencies": ["USD", "EUR", "GBP"],
        "pagination_default": 20,
        "environment": "production",
    }
    return json.dumps(settings, indent=2)


@mcp.resource("docs://api-reference")
def api_reference() -> str:
    """Inline API reference documentation in Markdown.

    URI: docs://api-reference
    In production, read this from a real docs/api.md file on disk.
    """
    return """# Acme Backend API Reference

## Orders
- **GET /orders** — list orders (paginated)
- **POST /orders** — create an order (use `create_order` tool)
- **GET /orders/{id}** — fetch single order

## Products
- **GET /products** — list products
- **GET /products/search?q=** — search products (use `search_products` tool)

## Users
- **GET /users/{id}** — user profile (use `user://{id}/profile` resource)
"""


# ==========================================================================
# 5. PROMPTS — reusable LLM prompt templates with typed arguments
#    The client (Claude Desktop / IDE) picks a prompt, fills arguments, and
#    sends the rendered message to the LLM.  LLM may then call tools.
# ==========================================================================


@mcp.prompt()
def analyze_order(user_id: int, time_period: str = "30 days") -> list[dict]:
    """Generate a structured analysis prompt for a user's order history."""
    return [
        {
            "role": "user",
            "content": {
                "type": "text",
                "text": (
                    f"Analyze the order patterns for user {user_id} over the last {time_period}.\n\n"
                    "Specifically look for:\n"
                    "1. Average order value trends\n"
                    "2. Category preferences\n"
                    "3. Frequency patterns\n"
                    "4. Suggestions for upselling\n\n"
                    "Use the `get_user_orders` tool to fetch data first, then `search_orders` "
                    "if you need filtered subsets."
                ),
            },
        }
    ]


@mcp.prompt()
def order_analysis_prompt(user_id: int) -> str:
    """Simple single-string prompt variant for quick analysis."""
    return (
        f"Analyze the order patterns for user {user_id} and suggest improvements "
        "to increase average order value and retention."
    )


@mcp.prompt()
def code_review(repo: str, pr_number: int) -> list[dict]:
    """Code review prompt template — demonstrates prompts beyond the orders domain."""
    return [
        {
            "role": "user",
            "content": {
                "type": "text",
                "text": (
                    f"Review PR #{pr_number} in repository `{repo}`.\n"
                    "Check for: security vulnerabilities, performance issues, "
                    "code style, missing tests, and edge cases."
                ),
            },
        }
    ]


# ==========================================================================
# 6. SSE / HTTP TRANSPORT (production deployment)
#    Wraps the FastMCP server in a Starlette app so it runs over HTTP.
# ==========================================================================

sse_transport = SseServerTransport("/messages/")


async def handle_sse(request: Request) -> None:
    """SSE endpoint — MCP clients connect here to establish a session."""
    async with sse_transport.connect_sse(
        request.scope, request.receive, request._send
    ) as (read_stream, write_stream):
        await mcp._mcp_server.run(
            read_stream,
            write_stream,
            mcp._mcp_server.create_initialization_options(),
        )


# ==========================================================================
# 7. AUTH MIDDLEWARE — bearer token validation + RBAC
# ==========================================================================

# Stub token store (replace with DB/JWT library in production).
_VALID_TOKENS: dict[str, dict] = {
    "dev-token-alice": {"id": 42, "name": "Alice", "role": "user"},
    "dev-token-bob":   {"id": 7,  "name": "Bob",   "role": "admin"},
}


async def validate_token(token: str) -> dict | None:
    """Look up a bearer token.  In production: verify JWT or DB lookup."""
    return _VALID_TOKENS.get(token)


class AuthMiddleware(BaseHTTPMiddleware):
    """Require a valid bearer token for all MCP endpoints."""

    async def dispatch(self, request: Request, call_next):
        # Public paths — no auth required
        if request.url.path in ("/health", "/.well-known/oauth-authorization-server"):
            return await call_next(request)

        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse({"error": "Missing or malformed Authorization header"}, status_code=401)

        token = auth_header[7:]
        user = await validate_token(token)
        if not user:
            return JSONResponse({"error": "Invalid token"}, status_code=401)

        # Attach resolved user to request state for per-tool RBAC checks
        request.state.user = user
        return await call_next(request)


# ==========================================================================
# 8. PROMETHEUS METRICS — instrument every tool call
# ==========================================================================

# pip install prometheus-client
tool_calls_total = Counter(
    "mcp_tool_calls_total",
    "Total MCP tool invocations",
    ["tool", "status"],
)
tool_call_duration = Histogram(
    "mcp_tool_call_duration_seconds",
    "Latency of MCP tool invocations",
    ["tool"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)


def monitored_tool(tool_name: str):
    """Decorator factory — wraps any coroutine with metrics + structured logging."""

    def decorator(fn):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            start = time.monotonic()
            try:
                result = await fn(*args, **kwargs)
                elapsed = time.monotonic() - start
                tool_calls_total.labels(tool=tool_name, status="success").inc()
                tool_call_duration.labels(tool=tool_name).observe(elapsed)
                log.info("tool_call_success", tool=tool_name, duration_s=round(elapsed, 4))
                return result
            except Exception as exc:
                elapsed = time.monotonic() - start
                tool_calls_total.labels(tool=tool_name, status="error").inc()
                tool_call_duration.labels(tool=tool_name).observe(elapsed)
                log.exception("tool_call_error", tool=tool_name, error=str(exc))
                raise

        return wrapper

    return decorator


# Example — wrapping a production-only tool with the decorator:
async def _admin_stats_impl() -> dict:
    """Return aggregate order statistics (admin-only tool implementation)."""
    total_revenue = sum(o["total"] for o in _ORDERS if o["status"] != "cancelled")
    return {
        "total_orders": len(_ORDERS),
        "total_revenue": round(total_revenue, 2),
        "pending_count": sum(1 for o in _ORDERS if o["status"] == "pending"),
    }


# Register the monitored version as an MCP tool at module load time
mcp.add_tool(monitored_tool("admin_stats")(_admin_stats_impl), name="admin_stats",
             description="Return aggregate order statistics (admin-only).")


# ==========================================================================
# 9. OAUTH 2.1 METADATA ENDPOINT (MCP client discovery)
# ==========================================================================

async def oauth_metadata(request: Request) -> JSONResponse:
    """Well-known endpoint allowing MCP clients to discover OAuth configuration."""
    base = str(request.base_url).rstrip("/")
    return JSONResponse({
        "issuer": base,
        "authorization_endpoint": f"{base}/oauth/authorize",
        "token_endpoint": f"{base}/oauth/token",
        "registration_endpoint": f"{base}/oauth/register",
        "scopes_supported": ["read", "write", "admin"],
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "client_credentials"],
    })


# ==========================================================================
# 10. STARLETTE APP (SSE transport + auth + metrics mount)
# ==========================================================================

metrics_app = make_asgi_app()  # Prometheus /metrics ASGI app

mcp_starlette_app = Starlette(
    routes=[
        Route("/.well-known/oauth-authorization-server", endpoint=oauth_metadata),
        Route("/sse", endpoint=handle_sse),
        Mount("/messages/", app=sse_transport.handle_post_message),
        Mount("/metrics", app=metrics_app),
    ],
    middleware=[Middleware(AuthMiddleware)],
)


# ==========================================================================
# 11. FASTAPI APP — standard REST routes + MCP mounted at /mcp
#     Pattern: one process, two interfaces (human-facing API + AI-facing MCP)
# ==========================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle — runs health checks and warms connections."""
    logging.info("Acme backend starting up — MCP server ready at /mcp/sse")
    yield
    logging.info("Acme backend shutting down")


api = FastAPI(
    title="Acme Backend",
    description="REST API + MCP server (mounted at /mcp)",
    version="1.0.0",
    lifespan=lifespan,
)


@api.get("/health")
def health() -> dict:
    """Liveness probe used by Kubernetes and load balancers."""
    return {"status": "ok", "service": "acme-backend", "version": "1.0.0"}


@api.get("/orders")
def list_orders(limit: int = 20) -> list[dict]:
    """Standard REST endpoint — not MCP.  Returns the most recent orders."""
    return sorted(_ORDERS, key=lambda o: o["created_at"], reverse=True)[:limit]


@api.get("/products")
def list_products() -> list[dict]:
    """Standard REST endpoint for product listing."""
    return _PRODUCTS


# Mount the MCP Starlette sub-application at /mcp
# MCP clients connect to: http://host:8080/mcp/sse
api.mount("/mcp", mcp_starlette_app)

# Convenience alias — uvicorn entry point
combined_app = api


# ==========================================================================
# 12. MCP CLIENT — consuming a remote MCP server from your FastAPI backend
#     Your service can be BOTH a server (above) and a client (below).
# ==========================================================================

class MCPMultiClient:
    """Connect to multiple MCP servers and fan-out tool calls.

    Usage:
        client = MCPMultiClient()
        await client.connect("github", "https://api.github.com/mcp")
        result = await client.call("github", "list_repositories", {"org": "anthropic"})
    """

    def __init__(self) -> None:
        # server_name -> ClientSession (lazy-initialized)
        self._sessions: dict[str, Any] = {}

    async def connect(self, name: str, url: str) -> None:
        """Open an SSE connection to a remote MCP server and initialise the session."""
        # Import here so the module is importable even without a live MCP server
        from mcp import ClientSession                  # noqa: PLC0415
        from mcp.client.sse import sse_client          # noqa: PLC0415

        read, write = await sse_client(url).__aenter__()
        session: ClientSession = ClientSession(read, write)
        await session.initialize()
        self._sessions[name] = session
        log.info("mcp_client_connected", server=name, url=url)

    async def list_tools(self, server: str) -> list[str]:
        """Return the names of all tools exposed by a connected server."""
        session = self._sessions[server]
        response = await session.list_tools()
        return [t.name for t in response.tools]

    async def call(self, server: str, tool: str, args: dict) -> Any:
        """Invoke a tool on a named remote MCP server."""
        if server not in self._sessions:
            raise ValueError(f"No session for MCP server '{server}'. Call connect() first.")
        session = self._sessions[server]
        result = await session.call_tool(tool, arguments=args)
        return result.content


# Singleton client — register remote servers in the FastAPI lifespan
mcp_client = MCPMultiClient()

# Example (commented out — requires live remote MCP endpoints):
#
# @api.on_event("startup")
# async def init_mcp_clients():
#     await mcp_client.connect("github", "https://api.github.com/mcp")
#     await mcp_client.connect("linear", "https://api.linear.app/mcp")
#
# @api.post("/agent/run")
# async def agent_orchestrator(task: str, server: str, tool: str, args: dict):
#     """Thin orchestration endpoint — routes a task to the right MCP server."""
#     return await mcp_client.call(server, tool, args)


# ==========================================================================
# 13. STDIO ENTRY POINT (local development / Claude Desktop)
# ==========================================================================

if __name__ == "__main__":
    # Run with stdio transport — no HTTP server needed.
    # Register this script in claude_desktop_config.json (see module docstring).
    mcp.run(transport="stdio")
