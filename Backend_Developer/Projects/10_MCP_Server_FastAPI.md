# Project 10: MCP Server for FastAPI (AI Tool Platform)

**Stack:** FastAPI + Python MCP SDK + Starlette + PostgreSQL + OAuth 2.1 + Docker + Cloudflare
**Build Time:** 1-2 weeks
**Difficulty:** ⭐⭐⭐⭐ (Emerging standard; deep async)
**Resume Strength:** ⭐⭐⭐⭐⭐ (Cutting-edge — very few engineers have this on resume)

---

## 1. Project Overview & Business Problem

### What it is
A production-grade **Model Context Protocol (MCP) server** that exposes your company's tools/data/prompts to Claude Desktop, Cursor, ChatGPT, and any other MCP-compatible AI client. Think "OAuth for AI tools" — write once, every LLM can use.

### Why build this
- **MCP is the emerging 2026 standard** — Anthropic + adoption by OpenAI, IDEs
- **Few engineers know it** — most AI engineers haven't built one yet
- **Highly portable** — same server works with Claude Desktop, Cursor, Continue, Cline, etc.
- **Real business value** — connect existing APIs to AI agents

### Real-world analogues
- GitHub MCP server (official)
- Linear MCP server
- Slack MCP server
- Anthropic's filesystem MCP
- Google Drive MCP

---

## 2. Requirements

### Functional
- **Tool exposure**: Functions LLM can call (CRUD on your data)
- **Resource exposure**: Read-only data LLM can fetch (docs, configs)
- **Prompt templates**: Reusable prompts for common tasks
- **Authentication**: OAuth 2.1 (Authorization Code + PKCE)
- **Authorization**: Per-user RBAC; tools filtered by permission
- **Multi-tenant**: Different orgs can have isolated tools
- **Audit log**: Every tool call traced + persisted
- **Rate limiting**: Per-user + per-tool
- **Streaming**: Long-running tool outputs streamed
- **Sampling**: Server can request LLM completions (bidirectional)
- **Tool versioning**: V1/V2 endpoints; deprecation
- **Discovery**: `.well-known/oauth-authorization-server` endpoint
- **Health checks**: For load balancer

### Non-Functional
- 1000+ concurrent MCP clients
- P95 tool execution < 500ms (excluding tool's external API)
- 99.95% uptime
- Audit logs retained 90 days (DPDP)
- Stateless (horizontally scalable)
- SSE transport (HTTP-friendly)

---

## 3. Use Case Examples

```
Use case A: Internal company assistant
- Tool: search_jira_tickets(query, project)
- Tool: get_engineering_metrics(timeframe)
- Tool: create_pr(repo, branch, title, body)
- Resource: company_handbook
- Resource: oncall_schedule

Use case B: Customer support AI
- Tool: lookup_customer(email)
- Tool: get_order_history(customer_id)
- Tool: issue_refund(order_id, amount, reason)
- Resource: refund_policy
- Resource: shipping_policy

Use case C: DevOps automation
- Tool: deploy_service(service, env, version)
- Tool: rollback_deployment(service)
- Tool: check_service_health(service)
- Tool: scale_replicas(service, count)
```

---

## 4. Architecture

```
                ┌────────────────────────┐
   Claude Desktop ─┐                      │
   Cursor IDE   ──┼──→ MCP Client SDKs   │
   Continue     ──┤                      │
   Custom Agent ──┘                      │
                                          │
                ┌───────────▼────────────┐
                │ HTTPS / SSE              │
                │ (OAuth 2.1 protected)    │
                └───────────┬────────────┘
                            │
                ┌───────────▼────────────┐
                │  Cloudflare              │ DDoS, WAF
                └───────────┬────────────┘
                            │
                ┌───────────▼────────────┐
                │  MCP Server (FastAPI)    │
                │  ├── Auth middleware     │
                │  ├── Rate limit          │
                │  ├── Tool registry       │
                │  ├── Resource handler    │
                │  └── Prompt handler      │
                └───────────┬────────────┘
                            │
        ┌───────────────────┼───────────────┐
        │                   │                │
┌───────▼──────┐    ┌───────▼──────┐  ┌────▼────────┐
│ Internal     │    │ External     │  │ PostgreSQL  │
│ APIs         │    │ APIs         │  │ (audit log) │
│ (CRM, etc)   │    │ (Stripe etc) │  │             │
└──────────────┘    └──────────────┘  └─────────────┘
```

---

## 5. Implementation Phases

### Phase 1: Basic MCP Server (Days 1-3)
- [ ] Install `mcp` Python SDK + FastMCP
- [ ] Define 5 basic tools (CRUD on your data)
- [ ] Define 2-3 resources (read-only data)
- [ ] Define 2 prompt templates
- [ ] Test with `mcp inspector` CLI

### Phase 2: HTTP Transport + FastAPI Mounting (Day 4-5)
- [ ] SSE transport setup
- [ ] Mount inside FastAPI app
- [ ] Health endpoint
- [ ] Connect Claude Desktop manually

### Phase 3: OAuth 2.1 + Auth (Day 6-8)
- [ ] `.well-known/oauth-authorization-server` endpoint
- [ ] Authorization endpoint (`/oauth/authorize`)
- [ ] Token endpoint (`/oauth/token`)
- [ ] Dynamic client registration (`/oauth/register`)
- [ ] JWT validation middleware
- [ ] Per-user context injection

### Phase 4: Production Patterns (Day 9-11)
- [ ] Rate limiting (per-user + per-tool)
- [ ] Audit logging
- [ ] Error handling + structured responses
- [ ] Tool authorization (RBAC)
- [ ] Multi-tenant tool filtering
- [ ] Long-running tool support

### Phase 5: Deployment (Day 12-14)
- [ ] Docker image
- [ ] Kubernetes manifests
- [ ] Cloudflare in front
- [ ] Monitoring (Prometheus + Grafana)
- [ ] Health/readiness probes
- [ ] Documentation + sample Claude Desktop config

---

## 6. Core Code

### Tool registry with Pydantic schemas

```python
from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport
from pydantic import BaseModel, Field
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from fastapi import FastAPI

# Initialize
mcp = FastMCP("acme-corporate-mcp")

# ─── Tool 1: Search tickets ───
class TicketFilter(BaseModel):
    project: str = Field(..., description="Project key (e.g., 'BACKEND')")
    status: str | None = Field(None, description="open, in_progress, done")
    assignee: str | None = None
    keyword: str | None = None

@mcp.tool()
async def search_tickets(filter: TicketFilter, ctx) -> list[dict]:
    """Search Jira tickets matching the filter."""
    # Inject user from context
    user = get_user_from_context(ctx)

    # Authorization
    if not await user_can_access_project(user.id, filter.project):
        return {"error": "Permission denied"}

    # Audit log
    await audit_log(user.id, "search_tickets", filter.dict())

    # Call Jira API
    tickets = await jira_client.search(
        jql=build_jql(filter),
        max_results=50,
    )
    return [
        {"key": t.key, "summary": t.summary, "status": t.status, "assignee": t.assignee}
        for t in tickets
    ]

# ─── Tool 2: Issue refund ───
class RefundRequest(BaseModel):
    order_id: str
    amount: float = Field(..., gt=0)
    reason: str = Field(..., max_length=500)

@mcp.tool()
async def issue_refund(req: RefundRequest, ctx) -> dict:
    """Issue a refund for an order. Requires manager role."""
    user = get_user_from_context(ctx)

    if "manager" not in user.permissions:
        return {"error": "Manager role required"}

    # Validate order
    order = await db.fetch_one("SELECT * FROM orders WHERE id = :id", {"id": req.order_id})
    if not order:
        return {"error": "Order not found"}

    if req.amount > order.total:
        return {"error": f"Refund exceeds order total ({order.total})"}

    # Process via Stripe
    refund = await stripe.Refund.create_async(
        payment_intent=order.payment_intent_id,
        amount=int(req.amount * 100),
        reason="requested_by_customer",
        metadata={"reason": req.reason, "approver_id": user.id},
    )

    await audit_log(user.id, "issue_refund", {**req.dict(), "refund_id": refund.id})

    return {
        "refund_id": refund.id,
        "amount": refund.amount / 100,
        "status": refund.status,
    }

# ─── Resource: Refund policy ───
@mcp.resource("policy://refunds")
async def refund_policy() -> str:
    """Company refund policy (markdown)."""
    with open("docs/refund_policy.md") as f:
        return f.read()

# ─── Dynamic resource ───
@mcp.resource("customer://{customer_id}/orders")
async def customer_orders(customer_id: str) -> str:
    """Recent orders for a customer."""
    rows = await db.fetch_all(
        "SELECT id, total, status, created_at FROM orders WHERE customer_id = :id ORDER BY created_at DESC LIMIT 20",
        {"id": customer_id},
    )
    return json.dumps([dict(r._mapping) for r in rows], default=str)

# ─── Prompt template ───
@mcp.prompt()
def triage_ticket(ticket_id: str) -> list[dict]:
    """Generate a prompt for triaging a Jira ticket."""
    return [
        {
            "role": "user",
            "content": {
                "type": "text",
                "text": f"""Triage Jira ticket {ticket_id}:

1. Use `search_tickets` to get details
2. Identify category (bug/feature/improvement)
3. Estimate priority (P0-P4)
4. Suggest assignee based on file owners
5. Draft a comment summarizing the issue

Be concise. Tag potential breaking changes.""",
            },
        }
    ]
```

### OAuth 2.1 + authentication middleware

```python
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import jwt

class OAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Public endpoints
        public = [
            "/health",
            "/.well-known/oauth-authorization-server",
            "/oauth/authorize",
            "/oauth/token",
            "/oauth/register",
        ]
        if any(request.url.path.startswith(p) for p in public):
            return await call_next(request)

        # Validate bearer token
        auth = request.headers.get("authorization", "")
        if not auth.startswith("Bearer "):
            return JSONResponse({"error": "missing_token"}, status_code=401)

        token = auth[7:]
        try:
            claims = jwt.decode(token, JWT_PUBLIC_KEY, algorithms=["RS256"])
        except jwt.InvalidTokenError as e:
            return JSONResponse({"error": "invalid_token", "detail": str(e)}, status_code=401)

        # Attach user to request
        user = await load_user(claims["sub"])
        request.state.user = user

        return await call_next(request)

# OAuth metadata endpoint
async def oauth_metadata(request):
    return JSONResponse({
        "issuer": "https://mcp.acme.com",
        "authorization_endpoint": "https://mcp.acme.com/oauth/authorize",
        "token_endpoint": "https://mcp.acme.com/oauth/token",
        "registration_endpoint": "https://mcp.acme.com/oauth/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "scopes_supported": ["read", "write", "admin"],
    })

# OAuth flow endpoints
@app.get("/oauth/authorize")
async def authorize(
    client_id: str,
    redirect_uri: str,
    response_type: str = "code",
    code_challenge: str = ...,
    code_challenge_method: str = "S256",
    state: str = ...,
    scope: str = "read",
):
    # Verify client_id is registered
    client = await db.fetch_one("SELECT * FROM oauth_clients WHERE id = :id", {"id": client_id})
    if not client:
        raise HTTPException(400, "Unknown client")

    # Show consent page to user (or auto-approve trusted apps)
    # ... user authenticates ...

    # Issue authorization code
    code = secrets.token_urlsafe(32)
    await redis.setex(
        f"oauth_code:{code}",
        600,  # 10 min
        json.dumps({
            "user_id": user.id,
            "client_id": client_id,
            "code_challenge": code_challenge,
            "scope": scope,
        }),
    )

    return RedirectResponse(f"{redirect_uri}?code={code}&state={state}")

@app.post("/oauth/token")
async def token(
    grant_type: str = Form(...),
    code: str = Form(...),
    redirect_uri: str = Form(...),
    client_id: str = Form(...),
    code_verifier: str = Form(...),
):
    # Validate code
    stored = await redis.get(f"oauth_code:{code}")
    if not stored:
        raise HTTPException(400, "Invalid code")
    data = json.loads(stored)

    # Verify PKCE
    expected_challenge = hashlib.sha256(code_verifier.encode()).digest()
    expected_b64 = base64.urlsafe_b64encode(expected_challenge).decode().rstrip("=")
    if expected_b64 != data["code_challenge"]:
        raise HTTPException(400, "Invalid PKCE")

    # Issue tokens
    access_token = jwt.encode(
        {
            "sub": data["user_id"],
            "scope": data["scope"],
            "exp": int(time.time()) + 3600,
        },
        JWT_PRIVATE_KEY,
        algorithm="RS256",
    )

    await redis.delete(f"oauth_code:{code}")

    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": 3600,
    }
```

### Mount MCP inside FastAPI

```python
# Combine MCP server with regular FastAPI app
sse_transport = SseServerTransport("/messages/")

async def handle_sse(request):
    async with sse_transport.connect_sse(
        request.scope, request.receive, request._send
    ) as (read_stream, write_stream):
        await mcp._mcp_server.run(
            read_stream,
            write_stream,
            mcp._mcp_server.create_initialization_options(),
        )

# Regular FastAPI app for OAuth endpoints + admin
api = FastAPI()

# OAuth routes
@api.get("/.well-known/oauth-authorization-server")
async def metadata(request: Request):
    return await oauth_metadata(request)

# MCP routes mounted as Starlette sub-app
mcp_app = Starlette(
    routes=[
        Route("/sse", endpoint=handle_sse),
        Mount("/messages/", app=sse_transport.handle_post_message),
    ],
    middleware=[Middleware(OAuthMiddleware)],
)

api.mount("/mcp", mcp_app)

# Run
# uvicorn main:api --host 0.0.0.0 --port 8000
```

---

## 7. Claude Desktop Configuration

```json
// ~/Library/Application Support/Claude/claude_desktop_config.json
{
  "mcpServers": {
    "acme-corporate": {
      "url": "https://mcp.acme.com/mcp/sse",
      "transport": "sse",
      "auth": {
        "type": "oauth2",
        "authorization_endpoint": "https://mcp.acme.com/oauth/authorize",
        "token_endpoint": "https://mcp.acme.com/oauth/token",
        "scope": "read write"
      }
    }
  }
}
```

User restarts Claude Desktop → OAuth flow prompts → grants access → all tools available.

---

## 8. Audit Logging Schema

```sql
CREATE TABLE mcp_audit_log (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    user_id BIGINT,
    client_id TEXT,             -- which AI client (Claude Desktop, Cursor)
    request_type TEXT,           -- 'tool_call', 'resource_read', 'prompt_get'
    tool_or_resource_name TEXT,
    arguments JSONB,
    result_status TEXT,          -- 'success', 'error', 'denied'
    error_message TEXT,
    duration_ms INT,
    ip INET,
    user_agent TEXT
) PARTITION BY RANGE (timestamp);

-- Monthly partitions
CREATE TABLE mcp_audit_log_2026_05 PARTITION OF mcp_audit_log
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
```

---

## 9. Testing Strategy

```python
# Unit test tools
def test_search_tickets_authorization():
    user = make_user(permissions={"project:BACKEND"})
    result = asyncio.run(search_tickets(
        TicketFilter(project="DESIGN"),
        ctx=make_ctx(user),
    ))
    assert "error" in result

# Integration test with MCP client
async def test_mcp_e2e():
    from mcp import ClientSession
    from mcp.client.sse import sse_client

    async with sse_client("http://localhost:8000/mcp/sse", auth_token=TEST_TOKEN) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            assert any(t.name == "search_tickets" for t in tools.tools)

            result = await session.call_tool(
                "search_tickets",
                arguments={"filter": {"project": "BACKEND"}},
            )
            assert len(result.content) > 0

# Load test (k6)
# 1000 concurrent MCP sessions, 1 tool call per minute
# Assert p99 < 1s, error rate < 0.1%
```

---

## 10. Deployment

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen
COPY . .
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "main:api", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mcp-server
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: mcp
        image: acme/mcp-server:latest
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef: { name: db-creds, key: url }
        - name: JWT_PRIVATE_KEY
          valueFrom:
            secretKeyRef: { name: jwt-keys, key: private }
        livenessProbe:
          httpGet: { path: /health, port: 8000 }
        readinessProbe:
          httpGet: { path: /health, port: 8000 }
        resources:
          limits: { cpu: "1", memory: "512Mi" }

---
apiVersion: v1
kind: Service
metadata:
  name: mcp-server
spec:
  selector: { app: mcp-server }
  ports:
  - port: 443
    targetPort: 8000
```

---

## 11. Monitoring

Key metrics:
- `mcp_tool_calls_total{tool, status}` — tool invocations
- `mcp_tool_duration_seconds{tool}` — execution time
- `mcp_active_sessions` — concurrent MCP clients
- `mcp_authentication_failures_total` — security signal
- `mcp_rate_limit_hits_total{user, tool}` — abuse signal

---

## 12. Stretch Goals

- [ ] Tool marketplace (multiple MCP servers in one platform)
- [ ] Tool versioning + migration (V1 → V2)
- [ ] Sampling (server requests LLM completion)
- [ ] Tool composition (one tool calls another)
- [ ] Real-time tool updates (hot-reload without restart)
- [ ] Multi-language SDKs (TypeScript, Go MCP clients)
- [ ] Integration with Cursor + Continue.dev
- [ ] Internal "tools as a service" platform for company

---

## 13. Resume Bullets

- Built **production MCP server** exposing 20+ tools to Claude Desktop / Cursor / custom agents
- Implemented **OAuth 2.1 + PKCE** authentication with dynamic client registration
- Designed **per-user tool authorization** (RBAC) with audit logging
- Deployed on **Kubernetes with horizontal scaling**, 1K+ concurrent MCP sessions
- Reduced developer onboarding time **70%** by enabling AI assistant access to internal tools
- Open-sourced **company-specific MCP server** as reusable template

---

## 14. Related Resources
- `Phase2_FastAPI/35_mcp_server_implementation.md` — implementation deep dive
- `Phase2_FastAPI/32_function_calling_endpoints.md` — tool patterns
- `Phase3_Security/17_india_dpdp_compliance.md` — audit requirements
- `PythonBackend_SystemDesign/HLD_Problems/Design_Agent_Orchestration.md` — agents using MCP
- MCP spec: https://modelcontextprotocol.io
- Python SDK: https://github.com/modelcontextprotocol/python-sdk
- Example servers: https://github.com/modelcontextprotocol/servers
