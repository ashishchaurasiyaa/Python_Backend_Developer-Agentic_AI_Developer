# MCP Server for FastAPI — Starter

Spec: [../10_MCP_Server_FastAPI.md](../10_MCP_Server_FastAPI.md)

## What to build

Production-grade Model Context Protocol (MCP) server that exposes your company's tools/data/prompts to Claude Desktop, Cursor, and any MCP-compatible AI client.  Includes OAuth 2.1 + PKCE auth, per-user RBAC, audit logging, rate limiting, and SSE transport mounted inside FastAPI.

## How to run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Infrastructure
docker run -d --name pg -e POSTGRES_PASSWORD=dev -p 5432:5432 postgres:16
docker run -d --name redis -p 6379:6379 redis:7

uvicorn main:api --reload
```

Test with the MCP inspector:
```bash
npx @modelcontextprotocol/inspector http://localhost:8000/mcp/sse
```

Connect from Claude Desktop — add to `~/Library/Application Support/Claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "my-server": {
      "url": "http://localhost:8000/mcp/sse",
      "transport": "sse"
    }
  }
}
```

## Milestones (from spec)

- **Phase 1** (Days 1-3) — Install `mcp` SDK, define 5 tools + 2 resources + 2 prompt templates, test with `mcp inspector`
- **Phase 2** (Days 4-5) — SSE transport mounted in FastAPI, `/health` endpoint, Claude Desktop manual connection
- **Phase 3** (Days 6-8) — OAuth 2.1 endpoints (`/.well-known`, `/oauth/authorize`, `/oauth/token`, `/oauth/register`), JWT middleware, per-user context
- **Phase 4** (Days 9-11) — Rate limiting, audit log to Postgres, RBAC tool filtering, multi-tenant tool isolation
- **Phase 5** (Days 12-14) — Docker image, Kubernetes manifests, Cloudflare in front, Prometheus metrics, documentation

## Key patterns to implement

1. Tools decorated with `@mcp.tool()` + Pydantic input models; MCP SDK handles JSON schema generation automatically.
2. OAuth 2.1 PKCE: `code_challenge = base64url(sha256(code_verifier))`; verify on token exchange before issuing JWT.
3. Per-user context: OAuth middleware attaches `request.state.user`; tools receive `ctx` parameter and call `get_user_from_context(ctx)`.
4. Audit log every tool call: `(timestamp, user_id, tool_name, arguments, result_status, duration_ms)` — GDPR retention 90 days.
5. Multi-tenant filtering: tool registry checks `user.tenant_id` before exposing tools; different orgs see different tool sets.
