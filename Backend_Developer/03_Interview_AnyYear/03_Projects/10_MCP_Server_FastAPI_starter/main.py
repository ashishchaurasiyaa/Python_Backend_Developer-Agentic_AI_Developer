"""
MCP Server for FastAPI — skeleton entry point.
Spec: ../10_MCP_Server_FastAPI.md

Run:
    uvicorn main:api --reload

Connect from Claude Desktop:
    See README.md for claude_desktop_config.json snippet.
"""

import json
import time
import secrets
import hashlib
import base64
import os
from fastapi import FastAPI, Request, HTTPException, Form
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse as StarletteJSON
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# FastMCP server
# ---------------------------------------------------------------------------
try:
    from mcp.server.fastmcp import FastMCP
    from mcp.server.sse import SseServerTransport
    from starlette.applications import Starlette
    from starlette.routing import Route, Mount
    _mcp_available = True
except ImportError:
    _mcp_available = False

api = FastAPI(title="MCP Server (FastAPI)", version="0.1.0")


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@api.get("/health")
async def health():
    return {"status": "ok", "mcp_sdk_available": _mcp_available}


# ---------------------------------------------------------------------------
# OAuth 2.1 metadata  (Phase 3 milestone)
# ---------------------------------------------------------------------------

@api.get("/.well-known/oauth-authorization-server")
async def oauth_metadata(request: Request):
    base = str(request.base_url).rstrip("/")
    return {
        "issuer": base,
        "authorization_endpoint": f"{base}/oauth/authorize",
        "token_endpoint": f"{base}/oauth/token",
        "registration_endpoint": f"{base}/oauth/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "scopes_supported": ["read", "write", "admin"],
    }


@api.get("/oauth/authorize")
async def authorize(
    client_id: str,
    redirect_uri: str,
    response_type: str = "code",
    code_challenge: str = "",
    code_challenge_method: str = "S256",
    state: str = "",
    scope: str = "read",
):
    """
    Show consent page or auto-approve trusted clients.
    Issue authorization code stored in Redis with TTL 600s.
    """
    # TODO: verify client_id is registered in oauth_clients table
    # TODO: show consent page (or auto-approve if trusted)
    # TODO: generate code via secrets.token_urlsafe(32)
    # TODO: store in Redis: oauth_code:{code} -> {user_id, client_id, code_challenge, scope}
    # TODO: return RedirectResponse(f"{redirect_uri}?code={code}&state={state}")
    return JSONResponse({"detail": "TODO: consent page not implemented"}, status_code=501)


@api.post("/oauth/token")
async def token(
    grant_type: str = Form(...),
    code: str = Form(...),
    redirect_uri: str = Form(...),
    client_id: str = Form(...),
    code_verifier: str = Form(...),
):
    """
    Exchange authorization code for JWT access token (PKCE verification).
    """
    # TODO: retrieve and delete oauth_code:{code} from Redis
    # TODO: verify PKCE: sha256(code_verifier) == stored code_challenge (base64url)
    # TODO: issue RS256 JWT (sub=user_id, scope, exp=now+3600)
    return JSONResponse({"detail": "TODO: token endpoint not implemented"}, status_code=501)


@api.post("/oauth/register")
async def register_client(body: dict):
    """Dynamic client registration (MCP clients self-register)."""
    # TODO: validate body (client_name, redirect_uris)
    # TODO: generate client_id + client_secret; store in oauth_clients table
    return {"detail": "TODO: client registration not implemented"}


# ---------------------------------------------------------------------------
# OAuth middleware (validates Bearer token on MCP routes)
# ---------------------------------------------------------------------------

PUBLIC_PATHS = [
    "/health",
    "/.well-known/oauth-authorization-server",
    "/oauth/authorize",
    "/oauth/token",
    "/oauth/register",
]


class OAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if any(request.url.path.startswith(p) for p in PUBLIC_PATHS):
            return await call_next(request)

        auth = request.headers.get("authorization", "")
        if not auth.startswith("Bearer "):
            return StarletteJSON({"error": "missing_token"}, status_code=401)

        # TODO: jwt.decode(token, PUBLIC_KEY, algorithms=["RS256"])
        # TODO: load user from DB; attach to request.state.user
        # Placeholder: allow all for development
        return await call_next(request)


# ---------------------------------------------------------------------------
# MCP tools, resources, and prompts  (Phase 1 milestone)
# ---------------------------------------------------------------------------

if _mcp_available:
    mcp = FastMCP("starter-mcp-server")

    # --- Tool 1: Echo (hello-world sanity check) ---------------------------

    @mcp.tool()
    async def echo(message: str) -> str:
        """Echo back the message. Used for testing connectivity."""
        return f"echo: {message}"

    # --- Tool 2: Placeholder CRUD tool -------------------------------------

    class SearchRequest(BaseModel):
        query: str = Field(..., description="Full-text search query")
        limit: int = Field(10, ge=1, le=100)

    @mcp.tool()
    async def search_records(req: SearchRequest) -> list[dict]:
        """
        Search internal records matching the query.
        TODO: replace stub with real DB query or API call.
        """
        # TODO: inject user from MCP context (ctx parameter)
        # TODO: audit_log(user_id, "search_records", req.dict())
        # TODO: check user permissions (RBAC)
        # TODO: query DB / external API
        return [{"id": "TODO", "summary": "implement search_records"}]

    # TODO: Tool 3: create_record(...)
    # TODO: Tool 4: update_record(id, ...)
    # TODO: Tool 5: delete_record(id) — require admin permission

    # --- Resource: static policy document ----------------------------------

    @mcp.resource("policy://example")
    async def example_policy() -> str:
        """Example company policy (markdown). Replace with real content."""
        return "# Example Policy\n\nTODO: populate with real policy content."

    # --- Resource: dynamic per-ID resource ---------------------------------

    @mcp.resource("record://{record_id}")
    async def get_record(record_id: str) -> str:
        """Fetch a single record by ID."""
        # TODO: query DB for record; check tenant + permission
        return json.dumps({"id": record_id, "detail": "TODO: not implemented"})

    # --- Prompt template ---------------------------------------------------

    @mcp.prompt()
    def triage_prompt(item_id: str) -> list[dict]:
        """Triage an item using the available tools."""
        return [
            {
                "role": "user",
                "content": {
                    "type": "text",
                    "text": (
                        f"Triage item {item_id}:\n"
                        "1. Use `search_records` to gather context.\n"
                        "2. Categorise severity (low/medium/high/critical).\n"
                        "3. Suggest next action and assignee.\n"
                        "Be concise."
                    ),
                },
            }
        ]

    # --- Mount MCP SSE transport inside FastAPI ----------------------------

    sse_transport = SseServerTransport("/mcp/messages/")

    async def _handle_sse(request: Request):
        async with sse_transport.connect_sse(
            request.scope, request.receive, request._send
        ) as (read_stream, write_stream):
            await mcp._mcp_server.run(
                read_stream,
                write_stream,
                mcp._mcp_server.create_initialization_options(),
            )

    mcp_app = Starlette(
        routes=[
            Route("/sse", endpoint=_handle_sse),
            Mount("/messages/", app=sse_transport.handle_post_message),
        ],
        # TODO: add OAuthMiddleware here for production
    )

    api.mount("/mcp", mcp_app)

else:
    @api.get("/mcp")
    async def mcp_unavailable():
        return JSONResponse(
            {"error": "mcp package not installed. Run: pip install mcp"},
            status_code=503,
        )


# ---------------------------------------------------------------------------
# Audit log schema (Postgres)  — implement in models/audit.py
# ---------------------------------------------------------------------------
# CREATE TABLE mcp_audit_log (
#     id              BIGSERIAL PRIMARY KEY,
#     timestamp       TIMESTAMPTZ DEFAULT NOW(),
#     user_id         BIGINT,
#     client_id       TEXT,
#     request_type    TEXT,   -- 'tool_call', 'resource_read', 'prompt_get'
#     tool_or_resource_name TEXT,
#     arguments       JSONB,
#     result_status   TEXT,   -- 'success', 'error', 'denied'
#     error_message   TEXT,
#     duration_ms     INT,
#     ip              INET
# ) PARTITION BY RANGE (timestamp);
